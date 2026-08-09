"""Temporal hand-swipe detection using the existing MediaPipe landmarks."""

from collections import deque
import time
from typing import Deque, Dict, Optional, Tuple

import numpy as np


class SwipeGestureDetector:
    """Detect one deliberate, fast swipe to the right.

    Coordinates are normalized to the camera frame and wrist movement is
    measured relative to the shoulder center. That keeps a sideways step or a
    small camera bump from looking like a hand gesture.
    """

    WRIST_INDICES = {"left": 9, "right": 10}
    SHOULDER_INDICES = (5, 6)

    def __init__(
        self,
        window_seconds: float = 0.9,
        cooldown_seconds: float = 2.5,
        minimum_distance: float = 0.24,
        minimum_speed: float = 0.55,
    ):
        self.window_seconds = window_seconds
        self.cooldown_seconds = cooldown_seconds
        self.minimum_distance = minimum_distance
        self.minimum_speed = minimum_speed
        self.histories: Dict[str, Deque[Tuple[float, float, float, float]]] = {
            side: deque() for side in self.WRIST_INDICES
        }
        self.last_trigger_time = float("-inf")

    def reset(self, preserve_cooldown: bool = True):
        for history in self.histories.values():
            history.clear()
        if not preserve_cooldown:
            self.last_trigger_time = float("-inf")

    def update(
        self,
        keypoints: Optional[np.ndarray],
        frame_shape: Tuple[int, ...],
        now: Optional[float] = None,
    ) -> Optional[Dict]:
        """Return gesture metadata once when a right swipe is confirmed."""
        timestamp = time.monotonic() if now is None else now
        if keypoints is None or keypoints.shape != (17, 3):
            # Fast hand motion can blur a frame. Keep the recent trail so one
            # missed detection does not erase an otherwise clear swipe.
            return None

        height, width = frame_shape[:2]
        if width <= 0 or height <= 0:
            return None

        shoulders = keypoints[np.asarray(self.SHOULDER_INDICES)]
        visible_shoulders = shoulders[:, 2] >= 0.20
        if not np.any(visible_shoulders):
            return None
        shoulder_x = float(np.mean(shoulders[visible_shoulders, 0]) / width)

        for side, wrist_index in self.WRIST_INDICES.items():
            wrist = keypoints[wrist_index]
            history = self.histories[side]
            if wrist[2] < 0.20:
                continue

            x = float(wrist[0] / width)
            y = float(wrist[1] / height)
            # Store raw x for screen coverage and torso-relative x for motion.
            history.append((timestamp, x, y, x - shoulder_x))
            while history and timestamp - history[0][0] > self.window_seconds:
                history.popleft()

            event = self._match_history(side, history, timestamp)
            if event is not None:
                self.last_trigger_time = timestamp
                self.reset(preserve_cooldown=True)
                return event

        return None

    def _match_history(
        self,
        side: str,
        history: Deque[Tuple[float, float, float, float]],
        now: float,
    ) -> Optional[Dict]:
        if now - self.last_trigger_time < self.cooldown_seconds or len(history) < 3:
            return None

        points = list(history)
        end_time, end_x, end_y, end_relative_x = points[-1]

        # Try every plausible start point so a short wind-up does not hide the
        # actual fast part of the swipe.
        for start_index, (start_time, start_x, start_y, start_relative_x) in enumerate(points[:-2]):
            duration = end_time - start_time
            if duration < 0.10 or duration > self.window_seconds:
                continue

            relative_dx = end_relative_x - start_relative_x
            raw_dx = end_x - start_x
            vertical_drift = abs(end_y - start_y)
            speed = relative_dx / duration

            # The hand must travel a substantial portion of the view, finish
            # on its right side, and be overwhelmingly horizontal.
            if relative_dx < self.minimum_distance or raw_dx < self.minimum_distance * 0.85:
                continue
            if end_x < 0.55 or start_x > 0.62:
                continue
            if speed < self.minimum_speed:
                continue
            if vertical_drift > max(0.16, relative_dx * 0.55):
                continue

            segment = points[start_index:]
            relative_positions = np.asarray([point[3] for point in segment])
            steps = np.diff(relative_positions)
            forward_motion = float(np.sum(np.clip(steps, 0.0, None)))
            total_motion = float(np.sum(np.abs(steps)))
            if total_motion <= 0 or forward_motion / total_motion < 0.70:
                continue

            return {
                "type": "swipe_right",
                "hand": side,
                "distance": round(relative_dx, 3),
                "speed": round(speed, 3),
            }

        return None

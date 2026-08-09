"""Adaptive reference-skeleton overlay and spatial coaching."""

from collections import deque
import os
import time
from typing import Dict, Optional, Tuple

import cv2
import numpy as np

from pose_detector import FULL_POSE_CONNECTIONS, PoseDetector


BODY_CLUSTERS = {
    "head": (0, 1, 2, 3, 4),
    "left hand": (9,),
    "right hand": (10,),
    "left arm": (7,),
    "right arm": (8,),
    "torso": (5, 6, 11, 12),
    "left leg": (13, 15),
    "right leg": (14, 16),
}


class ReferencePoseCoach:
    """Draw a target pose fitted to the user's body center and camera distance."""

    def __init__(self, update_interval: float = 3.0, history_size: int = 30):
        try:
            # References are unrelated still images, so tracking must be off.
            self.detector = PoseDetector(video_mode=False)
        except Exception as error:
            print(f"⚠️ Reference skeleton disabled: {error}")
            self.detector = None

        self.update_interval = update_interval
        self.history = deque(maxlen=history_size)
        self.full_history = deque(maxlen=history_size)
        self.reference_normalized: Optional[np.ndarray] = None
        self.reference_full_normalized: Optional[np.ndarray] = None
        self.reference_pose_name: Optional[str] = None
        self.last_instruction = "Line up with the gray reference skeleton."
        self.last_update_time = 0.0
        self.last_live_time = 0.0

        # Uniform scale + translation are smoothed separately from joint motion.
        # The guide follows distance/position without copying the user's pose.
        self.transform_scale: Optional[float] = None
        self.transform_offset: Optional[np.ndarray] = None
        self.transform_alpha = 0.22
        self.current_tolerance_px = 22.0

    def _reset_live_state(self):
        self.history.clear()
        self.full_history.clear()
        self.last_update_time = 0.0
        self.last_live_time = 0.0
        self.transform_scale = None
        self.transform_offset = None
        self.current_tolerance_px = 22.0

    def load_pose(self, pose_name: str, image_path: Optional[str]) -> bool:
        """Extract normalized 17- and 33-point targets from a reference photo."""
        self._reset_live_state()
        self.reference_normalized = None
        self.reference_full_normalized = None
        self.reference_pose_name = pose_name
        self.last_instruction = "Line up with the gray reference skeleton."

        if self.detector is None:
            self.last_instruction = "The reference skeleton is unavailable."
            return False
        if not image_path:
            self.last_instruction = "No skeleton reference is available for this pose yet."
            return False

        pose_directory = os.path.dirname(image_path)
        candidates = [image_path]
        try:
            siblings = sorted(
                os.path.join(pose_directory, name)
                for name in os.listdir(pose_directory)
                if name.lower().endswith((".jpg", ".jpeg", ".png"))
            )
            candidates.extend(path for path in siblings if path != image_path)
        except OSError:
            pass

        common = None
        full = None
        for candidate in candidates[:5]:
            image = cv2.imread(candidate)
            if image is None:
                continue
            detected = self.detector.detect_pose(image)
            detected_full = self.detector.last_full_keypoints
            if (
                detected is not None
                and detected_full is not None
                and detected_full.shape == (33, 3)
                and np.count_nonzero(detected_full[:, 2] >= 0.2) >= 12
            ):
                common = detected
                full = detected_full.copy()
                break

        if common is None or full is None:
            self.last_instruction = "No clear skeleton reference was found for this pose."
            return False

        visible = full[:, 2] >= 0.2
        visible_points = full[visible, :2]
        minimum = visible_points.min(axis=0)
        maximum = visible_points.max(axis=0)
        center = (minimum + maximum) / 2.0
        size = max(float(np.max(maximum - minimum)), 1.0)

        self.reference_full_normalized = full.copy()
        self.reference_full_normalized[:, :2] = (full[:, :2] - center) / size
        self.reference_normalized = common.copy()
        self.reference_normalized[:, :2] = (common[:, :2] - center) / size
        return True

    def _default_transform(self, frame_shape: Tuple[int, ...]) -> Tuple[float, np.ndarray]:
        height, width = frame_shape[:2]
        scale = min(width * 0.54, height * 0.82)
        return scale, np.array([width / 2.0, height / 2.0], dtype=np.float32)

    def _transform(self, normalized: Optional[np.ndarray], frame_shape: Tuple[int, ...]) -> Optional[np.ndarray]:
        if normalized is None:
            return None
        default_scale, default_offset = self._default_transform(frame_shape)
        scale = self.transform_scale if self.transform_scale is not None else default_scale
        offset = self.transform_offset if self.transform_offset is not None else default_offset
        result = normalized.copy()
        result[:, :2] = result[:, :2] * scale + offset
        return result

    def _reference_for_frame(self, frame_shape: Tuple[int, ...]) -> Optional[np.ndarray]:
        return self._transform(self.reference_normalized, frame_shape)

    def _full_reference_for_frame(self, frame_shape: Tuple[int, ...]) -> Optional[np.ndarray]:
        return self._transform(self.reference_full_normalized, frame_shape)

    @staticmethod
    def _distance(points: np.ndarray, first: int, second: int) -> float:
        return float(np.linalg.norm(points[first, :2] - points[second, :2]))

    def _fit_to_live_body(self, live: np.ndarray, frame_shape: Tuple[int, ...]):
        """Fit target scale/translation using torso dimensions, not limb pose."""
        if self.reference_normalized is None:
            return

        reference = self.reference_normalized
        ratios = []
        # Shoulder width, hip width, and shoulder-to-hip length respond to
        # camera distance but are mostly independent of arm/leg pose.
        for first, second in ((5, 6), (11, 12)):
            if live[first, 2] >= 0.2 and live[second, 2] >= 0.2:
                ref_distance = self._distance(reference, first, second)
                if ref_distance >= 0.025:
                    ratios.append(self._distance(live, first, second) / ref_distance)

        shoulder_ids = np.array((5, 6))
        hip_ids = np.array((11, 12))
        if np.all(live[np.concatenate((shoulder_ids, hip_ids)), 2] >= 0.2):
            live_torso = float(np.linalg.norm(
                live[shoulder_ids, :2].mean(axis=0) - live[hip_ids, :2].mean(axis=0)
            ))
            ref_torso = float(np.linalg.norm(
                reference[shoulder_ids, :2].mean(axis=0) - reference[hip_ids, :2].mean(axis=0)
            ))
            if ref_torso >= 0.025:
                ratios.append(live_torso / ref_torso)

        if not ratios:
            return

        height, width = frame_shape[:2]
        desired_scale = float(np.clip(np.median(ratios), 90.0, max(width, height) * 1.5))

        anchor_ids = np.array((5, 6, 11, 12))
        usable = (live[anchor_ids, 2] >= 0.2) & (reference[anchor_ids, 2] >= 0.2)
        if not np.any(usable):
            return
        ids = anchor_ids[usable]
        live_anchor = live[ids, :2].mean(axis=0)
        reference_anchor = reference[ids, :2].mean(axis=0)
        desired_offset = live_anchor - reference_anchor * desired_scale

        if self.transform_scale is None or self.transform_offset is None:
            self.transform_scale = desired_scale
            self.transform_offset = desired_offset.astype(np.float32)
        else:
            alpha = self.transform_alpha
            self.transform_scale = alpha * desired_scale + (1.0 - alpha) * self.transform_scale
            self.transform_offset = (
                alpha * desired_offset + (1.0 - alpha) * self.transform_offset
            ).astype(np.float32)

        # Scale the acceptance radius with apparent body size, with a generous
        # minimum for ordinary webcam landmark noise.
        self.current_tolerance_px = max(22.0, self.transform_scale * 0.05)

    def update(
        self,
        live_keypoints: Optional[np.ndarray],
        frame_shape: Tuple[int, ...],
        live_full_keypoints: Optional[np.ndarray] = None,
        form_status: str = "unknown",
        in_pose: bool = False,
    ) -> Dict:
        """Adapt the guide every frame and refresh coaching every few seconds."""
        if self.reference_normalized is None:
            return self.state(frame_shape)

        now = time.monotonic()
        valid_common = live_keypoints is not None and live_keypoints.shape == (17, 3)
        valid_full = live_full_keypoints is not None and live_full_keypoints.shape == (33, 3)
        if valid_common:
            self.history.append(live_keypoints.copy())
            self.last_live_time = now
            if valid_full:
                self.full_history.append(live_full_keypoints.copy())

            # A short median window follows distance/body position promptly but
            # removes single-frame jumps.
            recent = list(self.history)[-7:]
            smoothed_for_fit = np.median(np.stack(recent, axis=0), axis=0)
            self._fit_to_live_body(smoothed_for_fit, frame_shape)
        elif self.last_live_time and now - self.last_live_time > 1.0:
            self.history.clear()
            self.full_history.clear()

        # The green/perfect state is authoritative. Never contradict it with a
        # pixel correction, even if one noisy landmark is outside the guide.
        if in_pose:
            self.last_instruction = "Nice work — keep holding."
            return self.state(frame_shape)

        if now - self.last_update_time < self.update_interval:
            return self.state(frame_shape)
        self.last_update_time = now

        if len(self.history) < 5:
            self.last_instruction = "Step into view and line up with the gray skeleton."
            return self.state(frame_shape)

        smoothed = np.median(np.stack(self.history, axis=0), axis=0)
        reference = self._reference_for_frame(frame_shape)
        if reference is None:
            return self.state(frame_shape)

        best = None
        for cluster_name, indices in BODY_CLUSTERS.items():
            idx = np.asarray(indices, dtype=int)
            usable = (smoothed[idx, 2] >= 0.2) & (reference[idx, 2] >= 0.2)
            if not np.any(usable):
                continue
            live_center = smoothed[idx[usable], :2].mean(axis=0)
            target_center = reference[idx[usable], :2].mean(axis=0)
            delta = target_center - live_center
            distance = float(np.linalg.norm(delta))
            if best is None or distance > best[0]:
                best = (distance, cluster_name, delta)

        if best is None:
            self.last_instruction = "Keep your full body visible so I can compare it."
            return self.state(frame_shape)

        distance, cluster_name, delta = best
        tolerance = self.current_tolerance_px
        if distance <= tolerance:
            self.last_instruction = "Great alignment — hold steady."
            return self.state(frame_shape)

        dx, dy = float(delta[0]), float(delta[1])
        axis_tolerance = tolerance * 0.65

        def movement_phrase(value: float, positive: str, negative: str) -> str:
            if abs(value) <= axis_tolerance:
                return ""
            strength = abs(value) / max(tolerance, 1.0)
            if strength < 1.6:
                amount = "a little bit"
            elif strength < 3.0:
                amount = "a bit"
            else:
                amount = "a lot"
            direction = positive if value > 0 else negative
            return f"{direction} {amount}"

        horizontal = movement_phrase(dx, "right", "left")
        vertical = movement_phrase(dy, "down", "up")
        movement = " and ".join(part for part in (horizontal, vertical) if part)
        self.last_instruction = (
            f"Move your {cluster_name} {movement}."
            if movement
            else "Within range — hold steady."
        )
        return self.state(frame_shape)

    def state(self, frame_shape: Tuple[int, ...]) -> Dict:
        return {
            "available": self._full_reference_for_frame(frame_shape) is not None,
            "instruction": self.last_instruction,
            "update_interval": self.update_interval,
        }

    def draw(self, frame: np.ndarray) -> np.ndarray:
        """Draw the adaptive gray guide using all 33 MediaPipe points."""
        reference = self._full_reference_for_frame(frame.shape)
        if reference is None:
            return frame

        visible = reference[:, 2] >= 0.2
        for start, end in FULL_POSE_CONNECTIONS:
            if visible[start] and visible[end]:
                p1 = tuple(np.rint(reference[start, :2]).astype(int))
                p2 = tuple(np.rint(reference[end, :2]).astype(int))
                cv2.line(frame, p1, p2, (70, 70, 70), 7, cv2.LINE_AA)
                cv2.line(frame, p1, p2, (170, 170, 170), 4, cv2.LINE_AA)

        for index in np.flatnonzero(visible):
            point = tuple(np.rint(reference[index, :2]).astype(int))
            cv2.circle(frame, point, 9, (70, 70, 70), -1, cv2.LINE_AA)
            cv2.circle(frame, point, 6, (170, 170, 170), -1, cv2.LINE_AA)
        return frame

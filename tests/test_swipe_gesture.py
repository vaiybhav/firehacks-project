import unittest

import numpy as np

from swipe_gesture import SwipeGestureDetector


FRAME_SHAPE = (720, 1280, 3)


def pose(wrist_x, wrist_y=0.45, shoulder_x=0.50, hand="left"):
    """Build only the landmarks needed by the gesture detector."""
    points = np.zeros((17, 3), dtype=np.float32)
    for shoulder_index in (5, 6):
        points[shoulder_index] = (shoulder_x * 1280, 0.42 * 720, 0.95)
    active_wrist = 9 if hand == "left" else 10
    inactive_wrist = 10 if hand == "left" else 9
    points[active_wrist] = (wrist_x * 1280, wrist_y * 720, 0.95)
    points[inactive_wrist] = (0.50 * 1280, 0.50 * 720, 0.10)
    return points


class SwipeGestureDetectorTests(unittest.TestCase):
    def setUp(self):
        self.detector = SwipeGestureDetector()

    def feed(
        self, xs, duration=0.4, ys=None, shoulder_xs=None,
        start_time=10.0, hand="left"
    ):
        ys = ys or [0.45] * len(xs)
        shoulder_xs = shoulder_xs or [0.50] * len(xs)
        event = None
        for index, (x, y, shoulder_x) in enumerate(zip(xs, ys, shoulder_xs)):
            timestamp = start_time + duration * index / max(len(xs) - 1, 1)
            detected = self.detector.update(
                pose(x, y, shoulder_x, hand), FRAME_SHAPE, now=timestamp
            )
            event = detected or event
        return event

    def test_fast_wide_right_swipe_triggers(self):
        event = self.feed([0.22, 0.30, 0.41, 0.55, 0.68, 0.78])
        self.assertIsNotNone(event)
        self.assertEqual(event["type"], "swipe_right")
        self.assertEqual(event["hand"], "left")

    def test_left_swipe_does_not_trigger(self):
        event = self.feed([0.78, 0.68, 0.55, 0.41, 0.30, 0.22])
        self.assertIsNone(event)

    def test_right_hand_can_trigger(self):
        event = self.feed(
            [0.22, 0.30, 0.41, 0.55, 0.68, 0.78], hand="right"
        )
        self.assertIsNotNone(event)
        self.assertEqual(event["hand"], "right")

    def test_brief_tracking_dropout_keeps_swipe_history(self):
        event = None
        samples = [
            (10.00, pose(0.25)),
            (10.10, pose(0.38)),
            (10.18, None),
            (10.27, pose(0.56)),
            (10.36, pose(0.70)),
        ]
        for timestamp, points in samples:
            detected = self.detector.update(points, FRAME_SHAPE, now=timestamp)
            event = detected or event
        self.assertIsNotNone(event)

    def test_slow_rightward_motion_does_not_trigger(self):
        event = self.feed(
            [0.22, 0.28, 0.34, 0.40, 0.46, 0.52, 0.58, 0.64, 0.70, 0.78],
            duration=1.4,
        )
        self.assertIsNone(event)

    def test_mostly_vertical_motion_does_not_trigger(self):
        event = self.feed(
            [0.24, 0.31, 0.40, 0.51, 0.62, 0.74],
            ys=[0.20, 0.31, 0.43, 0.56, 0.68, 0.80],
        )
        self.assertIsNone(event)

    def test_body_translation_does_not_look_like_a_swipe(self):
        shoulder_xs = [0.30, 0.36, 0.43, 0.50, 0.57, 0.64]
        wrist_xs = [value - 0.10 for value in shoulder_xs]
        event = self.feed(wrist_xs, shoulder_xs=shoulder_xs)
        self.assertIsNone(event)

    def test_cooldown_blocks_a_second_swipe(self):
        first = self.feed([0.22, 0.30, 0.41, 0.55, 0.68, 0.78])
        second = self.feed(
            [0.22, 0.30, 0.41, 0.55, 0.68, 0.78], start_time=11.0
        )
        self.assertIsNotNone(first)
        self.assertIsNone(second)


if __name__ == "__main__":
    unittest.main()

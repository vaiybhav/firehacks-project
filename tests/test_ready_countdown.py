import time
import unittest

from guided_session import GuidedSession


class ReadyCountdownTests(unittest.TestCase):
    def test_countdown_starts_at_five_and_expires_cleanly(self):
        session = GuidedSession.__new__(GuidedSession)
        session.ready_countdown_end = None
        session.hold_start_time = None
        session.accumulated_hold_time = 0.0
        session.in_pose = True
        session.pose_entered = True
        session.pose_stability_frames = [True, True, True]

        session.start_ready_countdown(5)

        self.assertEqual(session.get_ready_countdown(), 5)
        self.assertFalse(session.in_pose)
        self.assertFalse(session.pose_entered)
        self.assertEqual(session.pose_stability_frames, [])

        session.ready_countdown_end = time.monotonic() - 0.01
        self.assertEqual(session.get_ready_countdown(), 0)
        self.assertIsNone(session.ready_countdown_end)


if __name__ == "__main__":
    unittest.main()

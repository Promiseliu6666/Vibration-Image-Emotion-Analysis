import sys
import unittest
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'fatigue_model_bundle'))
from fatigue_pipeline.realtime_clock import RealtimeClock


@dataclass
class Sample:
    frame_idx: int = 0
    timestamp_s: float = 0
    face_detected: bool = True
    p_eye_left_closed: float = .2
    p_eye_right_closed: float = .2
    p_mouth_open: float = .1
    keypoints: object = None


class ClockTests(unittest.TestCase):
    def test_real_aggregator_produces_thirty_valid_steps_by_ninety_seconds(self):
        from fatigue_pipeline.feature_aggregator import FeatureAggregator
        aggregator = FeatureAggregator(fps=12)
        clock = RealtimeClock(12)
        steps = []
        for i in range(226):
            for row in clock.sample(Sample(), 100 + i * .4):
                step = aggregator.add(row)
                if step is not None:
                    steps.append(step)
        self.assertGreaterEqual(len(steps), 30)
        self.assertTrue(all(step.features.valid for step in steps))
        self.assertLessEqual(steps[29].timestamp_s, 90)

    def test_slow_camera_still_fills_ninety_second_window_in_real_time(self):
        clock = RealtimeClock(12)
        rows = []
        for i in range(226):  # 2.5 actual observations/sec for 90 sec
            rows.extend(clock.sample(Sample(), 100 + i * .4))
        self.assertEqual(len(rows), 1081)
        self.assertAlmostEqual(rows[-1].timestamp_s, 90)
        self.assertEqual(rows[-1].frame_idx, 1080)

    def test_long_camera_gap_does_not_invent_valid_observations(self):
        clock = RealtimeClock(12)
        clock.sample(Sample(), 0)
        rows = clock.sample(Sample(), 10)
        self.assertTrue(any(row.p_eye_left_closed is None for row in rows))
        self.assertFalse(rows[50].face_detected)
        self.assertTrue(rows[-1].face_detected)

    def test_two_sessions_have_independent_clocks(self):
        first, second = RealtimeClock(12), RealtimeClock(12)
        first.sample(Sample(), 0)
        self.assertEqual(second.sample(Sample(), 500)[0].timestamp_s, 0)


if __name__ == '__main__':
    unittest.main()

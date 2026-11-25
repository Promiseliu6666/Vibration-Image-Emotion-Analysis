"""Exercise the deployed temporal weights with a slow, timed observation stream."""
import sys
import unittest
from collections import deque
from pathlib import Path
import math

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'fatigue_model_bundle'))
import torch
from platform_service import (
    FatigueRuntime, FatigueSessionState, FeatureAggregator, FrameProbs,
    load_temporal_checkpoint, load_normalization, resolve_asset,
    TEMPORAL_MODEL_PATH, NORMALIZATION_PATH,
)


class ScoringTests(unittest.TestCase):
    def test_slow_observations_produce_and_refresh_real_model_scores(self):
        runtime = FatigueRuntime.__new__(FatigueRuntime)
        runtime.device = torch.device('cpu')
        runtime.temporal_model = load_temporal_checkpoint(resolve_asset(TEMPORAL_MODEL_PATH), runtime.device)
        norm = load_normalization(resolve_asset(NORMALIZATION_PATH))
        runtime.norm_mean = torch.from_numpy(norm['mean'])
        runtime.norm_std = torch.from_numpy(norm['std'])
        state = FatigueSessionState(FeatureAggregator(fps=12), deque(maxlen=30))
        scores = []
        for i in range(241):  # 96 seconds at 2.5 observations/sec
            observation = FrameProbs(i, 0, True, .2, .2, .1)
            for row in state.clock.sample(observation, 100 + i * .4):
                step = state.aggregator.add(row)
                if step and step.features.valid:
                    state.feature_buffer.append(step.features.to_array())
                    if len(state.feature_buffer) == 30:
                        runtime._score_window(state)
                        scores.append((row.timestamp_s, state.score_ema))
        self.assertGreater(len(scores), 5)
        self.assertLessEqual(scores[0][0], 90)
        self.assertGreater(scores[-1][0], 94)
        self.assertTrue(all(math.isfinite(score) and 0 <= score <= 1 for _, score in scores))


if __name__ == '__main__':
    unittest.main()

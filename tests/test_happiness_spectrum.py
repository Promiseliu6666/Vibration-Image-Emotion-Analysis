import sys
import unittest
from pathlib import Path
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'ruoyi-fastapi-backend'))
from hik_vision.Vibration_image_algorithm import VibraimageCore


class SpectrumTests(unittest.TestCase):
    def score(self, copies, peak=2):
        core = VibraimageCore()
        frequency = np.arange(11, dtype=float)
        power = np.zeros(11)
        power[peak] = 1
        core.frequency_data = [frequency.copy() for _ in range(copies)]
        core.power_spectrum = [power.copy() for _ in range(copies)]
        return core._calculate_all_parameters()

    def test_identical_spectra_do_not_lower_happiness_as_monitoring_runs(self):
        early, later = self.score(1), self.score(60)
        self.assertAlmostEqual(early['e7'], later['e7'], places=2)
        self.assertAlmostEqual(early['e12'], later['e12'], places=2)

    def test_energy_uses_observed_spectral_power_not_just_frequency_bins(self):
        self.assertGreater(self.score(3, peak=8)['e7'], self.score(3, peak=2)['e7'])

    def test_energy_is_independent_of_frequency_units_and_power_scale(self):
        core = VibraimageCore()
        core.frequency_data = [np.arange(11, dtype=float)]
        core.power_spectrum = [np.array([0, 1, 4, 2, 0, 0, 0, 0, 0, 0, 0], dtype=float)]
        expected = core._spectral_energy()
        core.frequency_data = [core.frequency_data[0] * .2]
        core.power_spectrum = [core.power_spectrum[0] * 100]
        self.assertAlmostEqual(core._spectral_energy(), expected)

    def test_missing_or_zero_power_remains_finite(self):
        core = VibraimageCore()
        core.frequency_data = [np.arange(11, dtype=float)]
        core.power_spectrum = [np.zeros(11)]
        self.assertEqual(core._spectral_energy(), 0)


if __name__ == '__main__':
    unittest.main()

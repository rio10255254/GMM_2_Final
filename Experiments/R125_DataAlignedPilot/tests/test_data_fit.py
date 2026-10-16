"""Failure-sensitive checks of the independent data-fit audit calculations."""
import importlib.util
from pathlib import Path
import unittest

import numpy as np

SOURCE = Path(__file__).resolve().parents[1] / "scripts" / "audit_data_fit.py"
SPEC = importlib.util.spec_from_file_location("r125_data_audit_test", SOURCE)
audit = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(audit)


class DataFitTests(unittest.TestCase):
    def test_area_mean_is_physical_average_not_decimation(self):
        source = np.arange(64, dtype=np.float32).reshape(1, 8, 8)
        measured = audit.area_mean(source, 2)
        expected = np.array([[(source[0, 2*y:2*y+2, 2*x:2*x+2].sum() / 4) for x in range(4)] for y in range(4)])
        np.testing.assert_array_equal(measured[0], expected)
        self.assertFalse(np.array_equal(measured[0], source[0, ::2, ::2]))
        with self.assertRaises(ValueError):
            audit.area_mean(np.zeros((3, 7)), 2)

    def test_screen_preserves_large_or_localized_mismatch_as_failure(self):
        low = audit.discrepancy_stats(np.full((128, 128), 0.1), sigma=1)
        self.assertTrue(audit.model_discrepancy_admissible(low))
        systematic = audit.discrepancy_stats(np.full((128, 128), 0.3), sigma=1)
        self.assertFalse(audit.model_discrepancy_admissible(systematic))
        localized = np.zeros(10000)
        localized[:150] = 1.1
        summary = audit.discrepancy_stats(localized, sigma=1)
        self.assertLess(summary["rms_over_declared_sigma"], 0.25)
        self.assertFalse(audit.model_discrepancy_admissible(summary))

    def test_statistics_do_not_cancel_positive_and_negative_errors(self):
        stats = audit.discrepancy_stats(np.array([-1, 1], dtype=float), sigma=2)
        self.assertEqual(stats["mean_signed"], 0)
        self.assertEqual(stats["rms"], 1)
        self.assertEqual(stats["rms_over_declared_sigma"], 0.5)
        self.assertEqual(stats["max_abs_gray"], 255)
        for values in (np.array([]), np.array([np.nan])):
            with self.assertRaises(ValueError):
                audit.discrepancy_stats(values)

    def test_known_translation_sign_has_independent_diagnostic(self):
        yy, xx = np.mgrid[:40, :40]
        a = np.exp(-((xx - 20)**2 + (yy - 20)**2) / 25).astype(np.float32)
        b = np.roll(np.roll(a, 2, axis=1), -1, axis=0)
        sdf_a = (8 - np.sqrt((xx - 20)**2 + (yy - 20)**2)).astype(np.float32)
        sdf_b = np.roll(np.roll(sdf_a, 2, axis=1), -1, axis=0)
        result = audit.motion_diagnostic(np.stack((a, b)), np.stack((sdf_a, sdf_b)), [2, -1], (10, 30, 10, 30))
        self.assertEqual(result["target_expected_shift_rms"], 0)
        self.assertGreater(result["target_opposite_shift_rms"], result["target_unshifted_rms"])

    def test_profile_operator_matches_identity_core_without_halo_contamination(self):
        profile = {"calibration_id": "r125_audit_test", "qualification": "unqualified_diagnostic", "kernel_convention": "physical_psf", "kernel": {"type": "identity"}, "sampling_factor": 2, "gain": 1, "bias": 0, "noise_variance": 0.01}
        rng = np.random.default_rng(1259901)
        latent = rng.random((2, 48, 48), dtype=np.float32)
        predicted = audit.operator_core_prediction(latent, profile, (4, 20, 4, 20))
        expected = audit.area_mean(latent, 2)[:, 4:20, 4:20]
        np.testing.assert_allclose(predicted, expected, atol=1e-7, rtol=0)
        with self.assertRaises(ValueError):
            audit.operator_core_prediction(latent, profile, (0, 20, 0, 20))

    def test_package_paths_cannot_reach_evaluation_sources(self):
        base = Path(__file__).resolve().parents[1] / "data" / "package"
        self.assertEqual(audit.confined_path(base, "scenes/test.npz"), (base / "scenes/test.npz").resolve())
        with self.assertRaises(ValueError):
            audit.confined_path(base, "../../../../R124_RealFirstPrototype/results/file.npz")

    def test_independent_shape_and_texture_move_with_physical_object(self):
        shape = {"category": "textured_edges", "center_xy": [30, 31], "rotation_rad": 0.3, "wave_amplitude": 5, "wave_period": 43}
        photo = {"polarity": -1, "low": 0.2, "high": 0.8, "texture_amplitude": 0.04, "texture_angle_rad": -0.6, "texture_period1": 7, "texture_period2": 13, "texture_phase": 0.7}
        x, y = np.meshgrid(np.arange(64) + 0.125, np.arange(64) + 0.375)
        shifted, foreground_shifted = audit.independent_intensity(x, y, shape, photo, (0.3, -0.7))
        reference, foreground_reference = audit.independent_intensity(x - 0.3, y + 0.7, shape, photo, (0, 0))
        np.testing.assert_allclose(shifted, reference, atol=1e-14, rtol=0)
        np.testing.assert_array_equal(foreground_shifted, foreground_reference)
        self.assertLess(float(np.median(shifted[foreground_shifted])), float(np.median(shifted[~foreground_shifted])))


if __name__ == "__main__":
    unittest.main(verbosity=2)

"""Small independent-contract tests; actual 64-scene audit is a separate task."""
from __future__ import annotations

import sys
import unittest
from collections import Counter
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from data.generator_v2 import BASE_SEED, CATEGORIES, _parameters, area_average, gaussian_kernel, generate_scene, intensity_at, object_score


class GeneratorV2Tests(unittest.TestCase):
    def test_category_schedule_is_balanced_and_interleaved(self):
        counts = Counter(CATEGORIES)
        self.assertEqual(len(CATEGORIES), 64)
        for name in CATEGORIES[:4]:
            self.assertEqual(counts[name], 13)
        self.assertEqual(counts["clean_identity"], 6)
        self.assertEqual(counts["flat_negative"], 6)
        self.assertEqual(len(set(CATEGORIES[:6])), 6)

    def test_kernel_is_centered_normalized_and_preserves_rotated_covariance(self):
        kernel = gaussian_kernel((0.8, 1.5), 0.6, 8, 7)
        self.assertAlmostEqual(float(kernel.sum()), 1, places=6)
        self.assertTrue((kernel >= 0).all())
        np.testing.assert_allclose(kernel, kernel[::-1, ::-1], atol=0, rtol=0)
        axis = np.arange(-56, 57) / 8
        xx, yy = np.meshgrid(axis, axis)
        self.assertLess(abs(float((kernel * xx).sum())), 1e-7)
        self.assertLess(abs(float((kernel * yy).sum())), 1e-7)
        self.assertGreater(abs(float((kernel * xx * yy).sum())), 0.2)

    def test_each_category_has_actual_admitted_core_content(self):
        for index in range(6):
            with self.subTest(category=CATEGORIES[index]):
                arrays, metadata = generate_scene(index, native_size=128, supervised_size=64)
                self.assertTrue(metadata["admission"]["passed"])
                self.assertEqual(arrays["source"].shape, (2, 128, 128))
                self.assertEqual(arrays["source"].dtype, np.uint8)
                self.assertEqual(arrays["latent_target"].shape, (2, 512, 512))
                for key in ("target", "sdf", "boundary", "noiseless"):
                    self.assertEqual(arrays[key].shape, (2, 128, 128))
                    self.assertEqual(arrays[key].dtype, np.float32)
                    self.assertTrue(np.isfinite(arrays[key]).all())
                for view in range(2):
                    np.testing.assert_allclose(area_average(arrays["latent_target"][view], 4), arrays["target"][view], atol=2e-7, rtol=0)
                self.assertEqual(metadata["source_ancestors"], [metadata["parent_latent_id"]])
                self.assertEqual(metadata["external_training_inputs"], [])
                self.assertEqual(metadata["profile"]["qualification"], "unqualified_diagnostic")
                self.assertTrue(metadata["profile"]["simulation_known_operator"])
                self.assertTrue(all(stat["source_saturated_pixels"] == 0 for stat in metadata["core_stats"]))

    def test_repeat_generation_is_identical_and_pair_noise_is_independent(self):
        first, meta1 = generate_scene(0, native_size=96, supervised_size=64)
        second, meta2 = generate_scene(0, native_size=96, supervised_size=64)
        self.assertEqual(meta1, meta2)
        for key in first:
            np.testing.assert_array_equal(first[key], second[key])
        residual = first["source"].astype(np.float32) / 255 - first["noiseless"]
        self.assertFalse(np.array_equal(residual[0], residual[1]))
        self.assertGreater(np.hypot(*meta1["exact_delta_xy"]), 0.1)

    def test_identity_is_exact_and_flat_is_marked_motion_unobservable(self):
        arrays, metadata = generate_scene(4, native_size=96, supervised_size=64)
        np.testing.assert_array_equal(arrays["target"], arrays["source"].astype(np.float32) / np.float32(255))
        np.testing.assert_array_equal(arrays["noiseless"], arrays["target"])
        self.assertEqual(metadata["noise_sigma_gray"], 0)
        self.assertEqual(metadata["exact_delta_xy"], [0.0, 0.0])
        flat, flat_meta = generate_scene(5, native_size=96, supervised_size=64)
        self.assertFalse(flat_meta["motion_observable"])
        self.assertTrue(np.all(np.abs(flat["sdf"]) == 16))

    def test_continuous_translation_occurs_before_sensor_sampling(self):
        _, metadata = generate_scene(3, native_size=96, supervised_size=64)
        shape, photo = metadata["shape_params"], metadata["photometry"]
        axis = (np.arange(512, dtype=np.float64) + 0.5) / 8
        dx, dy = 0.375, -0.625
        moved, moved_fg, _ = intensity_at(axis[None, :], axis[:, None], shape, photo, (dx, dy))
        coordinate_shifted, foreground, _ = intensity_at(axis[None, :] - dx, axis[:, None] - dy, shape, photo, (0, 0))
        np.testing.assert_allclose(moved, coordinate_shifted, atol=2e-6, rtol=0)
        np.testing.assert_array_equal(moved_fg, foreground)
        self.assertEqual(metadata["rendering_order"][0], "evaluate_continuous_shifted_object_at_8x_cell_centers_float64")

    def test_near_boundary_precision_regression_uses_float64_geometry(self):
        # The independent v1 audit found this point classified on the wrong
        # side by Float32 arithmetic, changing a surrounding optical sample.
        # Reconstruct parameters from the seed; do not consume old image data.
        children = np.random.SeedSequence(BASE_SEED + 7).spawn(6)
        shape = _parameters(7, CATEGORIES[7], np.random.default_rng(children[0]), 640, 128)
        motion = np.random.default_rng(children[3])
        delta = tuple(motion.uniform(-0.85, 0.85, size=2))
        if np.hypot(*delta) < 0.15:
            delta = (delta[0] + 0.35, delta[1])
        score = object_score(np.array([[315.625]], dtype=np.float32),
                             np.array([[316.125]], dtype=np.float32), shape, delta)
        self.assertEqual(score.dtype, np.float64)
        self.assertLess(float(score[0, 0]), 0)
        self.assertAlmostEqual(float(score[0, 0]), -2.50735557e-6, places=12)


if __name__ == "__main__":
    unittest.main(verbosity=2)

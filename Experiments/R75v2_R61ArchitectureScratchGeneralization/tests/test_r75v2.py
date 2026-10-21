from __future__ import annotations

import copy
import json
import sys
import unittest
from pathlib import Path

import numpy as np
import scipy.io


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

import r75v2_dataset  # noqa: E402


class R75v2PreparationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.config = json.loads((ROOT / "config" / "experiment.json").read_text(encoding="utf-8"))
        cls.package, cls.manifest, cls.audit = r75v2_dataset.build_package("smoke")

    def test_01_source_contract_is_procedural_only(self) -> None:
        contract = self.manifest["training_data_contract"]
        self.assertTrue(contract["procedural_pixels_only"])
        self.assertTrue(contract["analytic_and_stochastic_primitives_only"])
        self.assertFalse(contract["legacy_pairs_imported"])
        self.assertFalse(contract["measured_sample_templates_imported"])
        self.assertFalse(contract["radius_lists_imported"])
        self.assertFalse(contract["checkpoint_outputs_imported"])
        self.assertFalse(contract["pseudo_labels_imported"])
        self.assertEqual(float(contract["target_boundary_bias_px"]), 0.0)
        self.assertTrue(self.audit["passed"])
        self.assertFalse(self.audit["real_image_pixels_used"])
        self.assertFalse(self.audit["measured_shape_templates_used"])
        self.assertFalse(self.audit["pseudo_labels_used"])

    def test_02_formal_population_is_exact(self) -> None:
        plan = r75v2_dataset.build_plan("formal")
        self.assertEqual(plan["expected_pairs"], 5120)
        self.assertEqual(plan["geometry_count"], 608)
        self.assertEqual(
            plan["pair_split_counts"],
            {"train": 4096, "validation": 512, "internal_test": 512},
        )
        self.assertEqual(
            plan["role_pair_counts"],
            {
                "basic_geometry": 896,
                "fine_noncircular": 1152,
                "multi_object_layout": 768,
                "exposure_sequence": 1280,
                "boundary_fade_mixed": 512,
                "identity_guard": 512,
            },
        )

    def test_03_smoke_has_all_six_roles(self) -> None:
        self.assertEqual(self.manifest["total_pairs"], 150)
        self.assertEqual(self.manifest["geometry_count"], 18)
        self.assertEqual(set(self.audit["training_role_counts"]), set(r75v2_dataset.ROLE_ORDER))
        self.assertEqual(
            self.audit["split_counts"],
            {"internal_test": 50, "train": 50, "validation": 50},
        )

    def test_04_geometry_groups_do_not_cross_splits(self) -> None:
        split_by_geometry: dict[str, set[str]] = {}
        for row in self.manifest["pairs"]:
            split_by_geometry.setdefault(row["geometry_id"], set()).add(row["split"])
        self.assertTrue(all(len(splits) == 1 for splits in split_by_geometry.values()))
        self.assertEqual(self.audit["geometry_split_overlap_count"], 0)
        split_meta = json.loads(
            (self.package / self.manifest["fixed_split_dir"] / "split_meta.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(split_meta["geometry_overlap_count"], 0)

    def test_05_internal_test_is_never_in_trainer_indices(self) -> None:
        split_dir = self.package / self.manifest["fixed_split_dir"]
        train_idx = set(np.load(split_dir / "train_idx.npy").tolist())
        val_idx = set(np.load(split_dir / "val_idx.npy").tolist())
        test_idx = set(np.load(split_dir / "test_idx.npy").tolist())
        self.assertFalse(train_idx & val_idx)
        self.assertFalse(train_idx & test_idx)
        self.assertFalse(val_idx & test_idx)
        self.assertEqual(len(train_idx | val_idx | test_idx), self.manifest["total_pairs"])

    def test_06_psf_bank_is_analytic_and_normalized(self) -> None:
        metadata = self.manifest["analytic_psf"]
        self.assertEqual(metadata["source_kind"], "analytic_gaussian_only")
        self.assertFalse(metadata["measured_data_used"])
        matrix = scipy.io.loadmat(self.package / metadata["relative_path"])["psf_grid"]
        self.assertEqual(matrix.shape, (21, 21, 3, 3))
        np.testing.assert_allclose(
            matrix.sum(axis=(0, 1)),
            np.ones((3, 3)),
            rtol=1e-5,
            atol=1e-5,
        )

    def test_07_forbidden_sources_are_rejected(self) -> None:
        invalid_key = copy.deepcopy(self.manifest["pairs"][:1])
        invalid_key[0]["sem_reference_id"] = "forbidden"
        with self.assertRaisesRegex(RuntimeError, "Forbidden source key"):
            r75v2_dataset.assert_record_provenance(invalid_key)
        invalid_value = copy.deepcopy(self.manifest["pairs"][:1])
        invalid_value[0]["provenance"]["note"] = "copied from a real_microscope image"
        with self.assertRaisesRegex(RuntimeError, "Forbidden source token"):
            r75v2_dataset.assert_record_provenance(invalid_value)

    def test_08_identity_and_near_identity_are_present(self) -> None:
        self.assertEqual(self.audit["identity_mode_counts"], {"exact": 12, "near": 12, "none": 126})
        self.assertEqual(self.audit["exact_identity_max_abs_difference"], 0)
        exact = [
            row for row in self.manifest["pairs"] if row["identity_mode"] == "exact"
        ]
        self.assertTrue(exact)
        for row in exact:
            source = r75v2_dataset._read_gray(self.package / row["package_src"])
            label = r75v2_dataset._read_gray(self.package / row["package_lbl"])
            np.testing.assert_array_equal(source, label)

    def test_09_exposure_and_composite_degradation_coverage(self) -> None:
        self.assertEqual(
            set(self.audit["exposure_level_counts"]),
            set(r75v2_dataset.EXPOSURE_LEVELS),
        )
        self.assertGreater(self.audit["dark_object_dark_background_count"], 0)
        self.assertGreater(self.audit["very_low_contrast_count"], 0)
        self.assertLess(self.audit["source_mean_distribution"]["min"], 50.0)
        self.assertGreater(self.audit["source_mean_distribution"]["max"], 185.0)
        self.assertGreater(self.audit["source_std_distribution"]["min"], 0.25)
        self.assertLess(self.audit["source_clipped_fraction_distribution"]["max"], 0.90)
        self.assertGreaterEqual(self.audit["composite_component_count_min_non_identity"], 2)
        self.assertLessEqual(self.audit["composite_component_count_max_non_identity"], 5)

    def test_10_labels_are_drawn_at_8x_then_downsampled(self) -> None:
        self.assertEqual(self.manifest["drawing_size"], [2048, 2048])
        self.assertEqual(self.manifest["image_size"], [256, 256])
        self.assertEqual(self.manifest["label_supersample_factor"], 8)
        self.assertEqual(self.manifest["label_downsample_method"], "cv2.INTER_AREA")
        self.assertEqual(self.audit["label_supersample_factor"], 8)
        self.assertGreater(self.audit["anti_alias_edge_pixel_count_min"], 0)
        for row in self.manifest["pairs"][:20]:
            exact = r75v2_dataset._read_gray(self.package / row["geometry_mask_aa"])
            soft = r75v2_dataset._read_gray(self.package / row["geometry_mask_soft"])
            self.assertTrue(np.any((exact > 0) & (exact < 255)))
            self.assertFalse(np.array_equal(exact, soft))

    def test_11_model_runtime_is_self_contained_and_unchanged(self) -> None:
        contract = json.loads(
            (ROOT / "config" / "architecture_contract.json").read_text(encoding="utf-8")
        )
        for key in ("architecture_source", "utility_source", "analytic_psf_source", "trainer_source"):
            self.assertFalse(Path(contract[key]).is_absolute(), key)
            local = (ROOT / contract[key]).resolve()
            self.assertTrue(local.is_relative_to(ROOT.resolve()))
            self.assertTrue(local.is_file())
        self.assertEqual(
            r75v2_dataset._sha256(ROOT / contract["architecture_source"]),
            contract["architecture_source_sha256"],
        )
        self.assertEqual(
            r75v2_dataset._sha256(ROOT / contract["trainer_source"]),
            contract["trainer_source_sha256"],
        )

    def test_12_operator_files_and_previews_exist(self) -> None:
        for key in (
            "preview_roles",
            "preview_exposure_sequence",
            "preview_identity_guard",
            "preview_shape_atlas",
            "antialias_zoom",
        ):
            self.assertTrue((self.package / self.manifest[key]).is_file(), key)
        required = (
            ROOT / "README.md",
            ROOT / "reports" / "R75V2_DESIGN.md",
            ROOT / "training" / "train_r75v2.py",
            ROOT / "inference" / "infer_r75v2.py",
            ROOT / "tools" / "prepare_dataset.py",
            ROOT / "scripts" / "start_r75v2_formal_training.ps1",
            ROOT / "scripts" / "start_r75v2_background.ps1",
            ROOT / "scripts" / "check_r75v2_status.ps1",
        )
        for path in required:
            self.assertTrue(path.is_file(), path)

    def test_13_live_validation_is_observation_only(self) -> None:
        live = self.config["live_validation"]
        self.assertTrue(live["enabled"])
        self.assertEqual(live["every_n_epochs"], 5)
        self.assertEqual(
            live["role"],
            "observation_only_no_loss_no_selection_no_training_control",
        )
        image_path = ROOT / live["relative_image_path"]
        metadata_path = image_path.parent / "metadata.json"
        self.assertTrue(image_path.is_file())
        self.assertTrue(metadata_path.is_file())
        image = r75v2_dataset._read_gray(image_path)
        self.assertEqual(image.shape, (232, 232))
        self.assertFalse(image_path.resolve().is_relative_to(self.package.resolve()))


if __name__ == "__main__":
    unittest.main()

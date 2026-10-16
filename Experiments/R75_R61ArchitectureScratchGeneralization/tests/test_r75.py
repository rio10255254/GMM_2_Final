from __future__ import annotations

import copy
import importlib.util
import json
import sys
import unittest
from pathlib import Path

import numpy as np
import scipy.io


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

import r75_dataset  # noqa: E402


class R75PreparationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.config = json.loads((ROOT / "config" / "experiment.json").read_text(encoding="utf-8"))
        cls.package, cls.manifest, cls.audit = r75_dataset.build_package("smoke")

    def test_01_source_contract_is_pure_procedural(self) -> None:
        contract = self.manifest["training_data_contract"]
        self.assertTrue(contract["procedural_pixels_only"])
        self.assertTrue(contract["analytic_primitives_only"])
        self.assertFalse(contract["legacy_pairs_imported"])
        self.assertFalse(contract["measured_sample_templates_imported"])
        self.assertFalse(contract["radius_lists_imported"])
        self.assertFalse(contract["checkpoint_outputs_imported"])
        self.assertEqual(float(contract["target_boundary_bias_px"]), 0.0)
        self.assertTrue(self.audit["passed"])
        self.assertFalse(self.audit["real_image_pixels_used"])
        self.assertFalse(self.audit["measured_shape_templates_used"])

    def test_02_smoke_population_and_balance(self) -> None:
        self.assertEqual(self.manifest["total_pairs"], 160)
        self.assertEqual(self.manifest["geometry_count"], 80)
        self.assertEqual(self.audit["split_counts"], {
            "internal_test": 32,
            "train": 96,
            "validation": 32,
        })
        self.assertEqual(set(self.audit["shape_family_counts"].values()), {10})
        self.assertEqual(self.audit["polarity_counts"], {"bright": 80, "dark": 80})
        self.assertEqual(len(self.audit["shape_family_counts"]), 16)
        self.assertEqual(len(self.manifest["degradation_families"]), 8)
        self.assertGreaterEqual(len(self.audit["degradation_family_counts"]), 6)

    def test_03_geometry_groups_do_not_cross_splits(self) -> None:
        split_by_geometry: dict[str, set[str]] = {}
        for row in self.manifest["pairs"]:
            split_by_geometry.setdefault(row["geometry_id"], set()).add(row["split"])
        self.assertTrue(all(len(splits) == 1 for splits in split_by_geometry.values()))
        self.assertEqual(self.audit["geometry_split_overlap_count"], 0)
        split_meta = json.loads(
            (self.package / self.manifest["fixed_split_dir"] / "split_meta.json").read_text(encoding="utf-8")
        )
        self.assertEqual(split_meta["geometry_overlap_count"], 0)

    def test_04_internal_test_is_never_in_trainer_indices(self) -> None:
        split_dir = self.package / self.manifest["fixed_split_dir"]
        train_idx = set(np.load(split_dir / "train_idx.npy").tolist())
        val_idx = set(np.load(split_dir / "val_idx.npy").tolist())
        test_idx = set(np.load(split_dir / "test_idx.npy").tolist())
        self.assertFalse(train_idx & val_idx)
        self.assertFalse(train_idx & test_idx)
        self.assertFalse(val_idx & test_idx)
        self.assertEqual(len(train_idx | val_idx | test_idx), self.manifest["total_pairs"])

    def test_05_psf_bank_is_analytic_and_normalized(self) -> None:
        metadata = self.manifest["analytic_psf"]
        self.assertEqual(metadata["source_kind"], "analytic_gaussian_only")
        self.assertFalse(metadata["measured_data_used"])
        matrix = scipy.io.loadmat(self.package / metadata["relative_path"])["psf_grid"]
        self.assertEqual(matrix.shape, (21, 21, 3, 3))
        sums = matrix.sum(axis=(0, 1))
        np.testing.assert_allclose(sums, np.ones((3, 3)), rtol=1e-5, atol=1e-5)

    def test_06_forbidden_source_key_is_rejected(self) -> None:
        invalid = copy.deepcopy(self.manifest["pairs"][:1])
        invalid[0]["sem_reference_id"] = "forbidden"
        with self.assertRaisesRegex(RuntimeError, "Forbidden source key"):
            r75_dataset.assert_record_provenance(invalid)

    def test_07_forbidden_source_value_is_rejected(self) -> None:
        invalid = copy.deepcopy(self.manifest["pairs"][:1])
        invalid[0]["provenance"]["note"] = "copied from a real_microscope image"
        with self.assertRaisesRegex(RuntimeError, "Forbidden source token"):
            r75_dataset.assert_record_provenance(invalid)

    def test_08_formal_plan_is_exact_and_keeps_test_separate(self) -> None:
        plan = r75_dataset.build_plan("formal")
        self.assertEqual(plan["expected_pairs"], 5120)
        self.assertEqual(plan["pair_split_counts"], {
            "train": 4096,
            "validation": 512,
            "internal_test": 512,
        })
        self.assertEqual(plan["shape_family_count"], 16)
        self.assertEqual(plan["renderings_per_geometry"], 4)
        self.assertFalse(plan["contains_real_pixels"])
        self.assertFalse(plan["contains_measured_shapes"])
        self.assertFalse(plan["contains_checkpoint_data"])

    def test_09_architecture_audit_proves_scratch_initialization(self) -> None:
        audit_path = ROOT / "reports" / "architecture_audit_smoke.json"
        self.assertTrue(audit_path.is_file())
        audit = json.loads(audit_path.read_text(encoding="utf-8"))
        self.assertTrue(audit["passed"])
        self.assertFalse(audit["checkpoint_loaded"])
        self.assertFalse(audit["teacher_loaded"])
        self.assertTrue(audit["all_learnable_layers_trainable"])
        self.assertEqual(audit["class_name"], "GeoEdgeAlignSR_v1_v5_NoCoord")
        self.assertAlmostEqual(float(audit["boundary_adapter_max_residual"]), 0.018, places=8)
        self.assertEqual(set(audit["fixed_architecture_kernels"]), {
            "u1.blur.weight",
            "u2.blur.weight",
            "u3.blur.weight",
        })

    def test_10_preview_and_operator_docs_exist(self) -> None:
        self.assertTrue((self.package / self.manifest["preview"]).is_file())
        self.assertTrue((self.package / self.manifest["antialias_zoom"]).is_file())
        self.assertTrue((ROOT / "README.md").is_file())
        self.assertTrue((ROOT / "reports" / "R75_DESIGN.md").is_file())
        self.assertTrue((ROOT / "training" / "train_r75.py").is_file())
        self.assertTrue((ROOT / "inference" / "infer_r75.py").is_file())
        self.assertTrue((ROOT / "tools" / "prepare_dataset.py").is_file())
        self.assertTrue((ROOT / "scripts" / "start_r75_formal_training.ps1").is_file())

    def test_11_labels_are_drawn_large_then_area_downsampled(self) -> None:
        self.assertEqual(self.manifest["drawing_size"], [1024, 1024])
        self.assertEqual(self.manifest["image_size"], [256, 256])
        self.assertEqual(self.manifest["label_supersample_factor"], 4)
        self.assertEqual(self.manifest["label_downsample_method"], "cv2.INTER_AREA")
        self.assertEqual(self.audit["label_supersample_factor"], 4)
        self.assertGreater(self.audit["anti_alias_edge_pixel_count_min"], 0)
        one_mask_per_geometry = {
            row["geometry_id"]: row["geometry_mask_aa"]
            for row in self.manifest["pairs"]
        }
        self.assertEqual(len(one_mask_per_geometry), self.manifest["geometry_count"])
        for relative_path in sorted(one_mask_per_geometry.values()):
            coverage = r75_dataset._read_gray(self.package / relative_path)
            self.assertTrue(np.any((coverage > 0) & (coverage < 255)), relative_path)

    def test_12_model_training_and_inference_are_self_contained(self) -> None:
        contract = json.loads((ROOT / "config" / "architecture_contract.json").read_text(encoding="utf-8"))
        for key in ("architecture_source", "utility_source", "analytic_psf_source", "trainer_source"):
            self.assertFalse(Path(contract[key]).is_absolute(), key)

        def local_path(value: str) -> Path:
            path = Path(value)
            return path.resolve() if path.is_absolute() else (ROOT / path).resolve()

        model_path = local_path(contract["architecture_source"])
        utility_path = local_path(contract["utility_source"])
        analytic_psf_path = local_path(contract["analytic_psf_source"])
        trainer_path = local_path(contract["trainer_source"])
        self.assertTrue(model_path.is_relative_to(ROOT.resolve()))
        self.assertTrue(utility_path.is_relative_to(ROOT.resolve()))
        self.assertTrue(analytic_psf_path.is_relative_to(ROOT.resolve()))
        self.assertTrue(trainer_path.is_relative_to(ROOT.resolve()))
        self.assertTrue(model_path.is_file())
        self.assertTrue(utility_path.is_file())
        self.assertTrue(analytic_psf_path.is_file())
        self.assertTrue(trainer_path.is_file())
        self.assertEqual(r75_dataset._sha256(model_path), contract["architecture_source_sha256"])
        self.assertEqual(r75_dataset._sha256(utility_path), contract["utility_source_sha256"])
        self.assertEqual(r75_dataset._sha256(analytic_psf_path), contract["analytic_psf_source_sha256"])
        self.assertEqual(r75_dataset._sha256(trainer_path), contract["trainer_source_sha256"])
        local_psf = scipy.io.loadmat(analytic_psf_path)["psf_grid"]
        package_psf = scipy.io.loadmat(self.package / self.manifest["analytic_psf"]["relative_path"])["psf_grid"]
        np.testing.assert_array_equal(local_psf, package_psf)

    def test_13_real_smoke_training_completed_and_exported_weights(self) -> None:
        report = json.loads((ROOT / "reports" / "smoke_training_verification.json").read_text(encoding="utf-8"))
        self.assertTrue(report["passed"])
        self.assertFalse(report["checkpoint_loaded"])
        self.assertFalse(report["teacher_loaded"])
        self.assertEqual(report["training_batches_executed"], 1)
        self.assertGreater(report["changed_parameter_tensors_after_one_batch"], 0)
        self.assertEqual(report["checkpoint_boundary_adapter"]["max_residual"], 0.018)
        self.assertEqual(report["generator_version"], self.config["dataset"]["generator_version"])
        self.assertEqual(report["dataset_total_pairs"], 160)
        exported = Path(report["exported_best_checkpoint"])
        self.assertTrue(exported.is_relative_to((ROOT / "weights" / "smoke").resolve()))
        self.assertTrue(exported.is_file())
        self.assertEqual(r75_dataset._sha256(exported), report["best_checkpoint_sha256"])
        self.assertFalse(report["formal_training_started"])
        self.assertFalse(report["performance_interpretation_allowed"])

    def test_14_center_nine_live_validation_is_observation_only(self) -> None:
        live = self.config["live_validation"]
        self.assertTrue(live["enabled"])
        self.assertEqual(live["every_n_epochs"], 5)
        self.assertEqual(live["role"], "observation_only_no_loss_no_selection_no_training_control")
        self.assertEqual(live["pillar_ids"], [22, 23, 24, 28, 29, 30, 34, 35, 36])
        image_path = ROOT / live["relative_image_path"]
        metadata_path = image_path.parent / "metadata.json"
        self.assertTrue(image_path.is_file())
        self.assertTrue(metadata_path.is_file())
        image = r75_dataset._read_gray(image_path)
        self.assertEqual(image.shape, (232, 232))
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        self.assertEqual(metadata["role"], live["role"])
        self.assertEqual(metadata["pillar_ids"], live["pillar_ids"])
        self.assertFalse(image_path.resolve().is_relative_to(self.package.resolve()))
        self.assertFalse(any("live_validation" in row["package_src"] for row in self.manifest["pairs"]))

    def test_15_safe_precision_and_zero_update_guard_are_enabled(self) -> None:
        self.assertFalse(self.config["training"]["amp_enabled"])
        manual_entry = (ROOT / "training" / "train_r75.py").read_text(encoding="utf-8")
        self.assertIn("USE_AMP = False", manual_entry)
        trainer = (ROOT / "training" / "runtime" / "GeoEdgeAlignSR_v1_Train_v5_NoCoord_return_v2_SimpleTest.py").read_text(encoding="utf-8")
        self.assertIn("No optimizer update was applied in this epoch", trainer)
        self.assertIn("optimizer_steps_applied", trainer)


if __name__ == "__main__":
    unittest.main()

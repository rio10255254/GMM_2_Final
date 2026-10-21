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
sys.path.insert(0, str(ROOT / "scripts"))
import r83_dataset  # noqa: E402


class R83PreparationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.config = json.loads((ROOT / "config" / "experiment.json").read_text(encoding="utf-8"))
        cls.package, cls.manifest, cls.audit = r83_dataset.build_package("smoke")

    def test_01_procedural_source_contract(self) -> None:
        contract = self.manifest["training_data_contract"]
        self.assertTrue(contract["procedural_pixels_only"])
        self.assertFalse(contract["legacy_pairs_imported"])
        self.assertFalse(contract["measured_sample_templates_imported"])
        self.assertFalse(contract["pseudo_labels_imported"])
        self.assertFalse(contract["exact_geometry_used_as_training_loss"])
        self.assertTrue(self.audit["passed"])
        self.assertFalse(self.audit["real_image_pixels_used"])
        self.assertFalse(self.audit["measured_shape_templates_used"])

    def test_02_formal_population_is_exact(self) -> None:
        plan = r83_dataset.build_plan("formal")
        self.assertEqual(plan["expected_pairs"], 5120)
        self.assertEqual(plan["geometry_count"], 640)
        self.assertEqual(plan["pair_split_counts"], {"train": 4096, "validation": 512, "internal_test": 512})
        self.assertEqual(
            plan["role_pair_counts"],
            {
                "basic_geometry": 640,
                "fine_noncircular": 800,
                "dense_periodic_layout": 800,
                "multiscale_field": 800,
                "boundary_fade_mixed": 1280,
                "identity_guard": 800,
            },
        )

    def test_03_smoke_roles_and_split(self) -> None:
        self.assertEqual(self.manifest["total_pairs"], 144)
        self.assertEqual(set(self.audit["training_role_counts"]), set(r83_dataset.ROLE_ORDER))
        self.assertEqual(self.audit["split_counts"], {"train": 48, "validation": 48, "internal_test": 48})
        self.assertEqual(self.audit["geometry_split_overlap_count"], 0)

    def test_04_locked_holdout_is_selection_ineligible(self) -> None:
        plan = r83_dataset.build_plan("locked_holdout")
        self.assertEqual(plan["expected_pairs"], 384)
        self.assertEqual(plan["pair_split_counts"], {"train": 0, "validation": 0, "internal_test": 384})
        self.assertFalse(self.config["locked_confirmation"]["selection_use_allowed"])
        formal_seed = self.config["dataset"]["profile_seed_offsets"]["formal"]
        holdout_seed = self.config["dataset"]["profile_seed_offsets"]["locked_holdout"]
        self.assertNotEqual(formal_seed, holdout_seed)

    def test_05_fixed_indices_do_not_overlap(self) -> None:
        split_dir = self.package / self.manifest["fixed_split_dir"]
        train_idx = set(np.load(split_dir / "train_idx.npy").tolist())
        val_idx = set(np.load(split_dir / "val_idx.npy").tolist())
        test_idx = set(np.load(split_dir / "test_idx.npy").tolist())
        self.assertFalse(train_idx & val_idx)
        self.assertFalse(train_idx & test_idx)
        self.assertFalse(val_idx & test_idx)
        self.assertEqual(len(train_idx | val_idx | test_idx), 144)

    def test_06_psf_bank_is_analytic(self) -> None:
        metadata = self.manifest["analytic_psf"]
        self.assertEqual(metadata["source_kind"], "analytic_gaussian_only")
        self.assertFalse(metadata["measured_data_used"])
        matrix = scipy.io.loadmat(self.package / metadata["relative_path"])["psf_grid"]
        np.testing.assert_allclose(matrix.sum(axis=(0, 1)), np.ones((3, 3)), rtol=1e-5, atol=1e-5)

    def test_07_forbidden_sources_are_rejected(self) -> None:
        invalid_key = copy.deepcopy(self.manifest["pairs"][:1])
        invalid_key[0]["sem_reference_id"] = "forbidden"
        with self.assertRaisesRegex(RuntimeError, "Forbidden source key"):
            r83_dataset.assert_record_provenance(invalid_key)
        invalid_value = copy.deepcopy(self.manifest["pairs"][:1])
        invalid_value[0]["provenance"]["note"] = "copied from a real_microscope image"
        with self.assertRaisesRegex(RuntimeError, "Forbidden source token"):
            r83_dataset.assert_record_provenance(invalid_value)

    def test_08_identity_and_ambiguity_guards(self) -> None:
        self.assertEqual(self.audit["identity_mode_counts"], {"exact": 12, "near": 12, "none": 120})
        self.assertEqual(self.audit["target_policy_counts"], {"clean_analytic": 120, "conservative_blend": 12, "identity": 12})
        self.assertEqual(self.audit["observability_class_counts"], {"ambiguous": 12, "anchor": 24, "recoverable": 12, "replay": 96})
        self.assertEqual(self.audit["exact_identity_max_abs_difference"], 0)

    def test_09_severe_boundary_contract(self) -> None:
        boundary = [row for row in self.manifest["pairs"] if row["training_role"] == "boundary_fade_mixed"]
        self.assertEqual(len(boundary), 24)
        self.assertEqual(sum(row["target_policy"] == "conservative_blend" for row in boundary), 12)
        self.assertEqual(sum(row["observability_class"] == "recoverable" for row in boundary), 12)
        self.assertGreaterEqual(self.audit["boundary_fade_zone_count_distribution"]["min"], 3)
        self.assertLessEqual(self.audit["boundary_fade_zone_count_distribution"]["max"], 14)
        self.assertGreater(self.audit["boundary_gaussian_sigma_distribution"]["max"], 6.0)
        self.assertGreater(self.audit["boundary_read_noise_sigma_distribution"]["max"], 8.0)
        weights = self.audit["conservative_clean_target_weight_distribution"]
        self.assertGreaterEqual(weights["min"], 0.15)
        self.assertLessEqual(weights["max"], 0.45)

    def test_10_labels_are_supersampled(self) -> None:
        self.assertEqual(self.manifest["drawing_size"], [2048, 2048])
        self.assertEqual(self.manifest["image_size"], [256, 256])
        self.assertEqual(self.manifest["label_supersample_factor"], 8)
        self.assertGreater(self.audit["anti_alias_edge_pixel_count_min"], 0)
        for row in self.manifest["pairs"][:20]:
            exact = r83_dataset._read_gray(self.package / row["geometry_mask_aa"])
            self.assertTrue(np.any((exact > 0) & (exact < 255)))

    def test_11_runtime_is_self_contained_and_unchanged(self) -> None:
        contract = json.loads((ROOT / "config" / "architecture_contract.json").read_text(encoding="utf-8"))
        for key in ("architecture_source", "utility_source", "analytic_psf_source", "trainer_source"):
            path = ROOT / contract[key]
            self.assertTrue(path.is_file())
            self.assertTrue(path.resolve().is_relative_to(ROOT.resolve()))
            self.assertEqual(r83_dataset._sha256(path), contract[f"{key}_sha256"])

    def test_12_operator_files_and_observation_images_exist(self) -> None:
        required = (
            ROOT / "README.md",
            ROOT / "MANIFEST.md",
            ROOT / "reports" / "R83_DESIGN.md",
            ROOT / "training" / "train_r83.py",
            ROOT / "inference" / "infer_r83.py",
            ROOT / "tools" / "prepare_dataset.py",
            ROOT / "scripts" / "prepare_r83_seed.py",
            ROOT / "scripts" / "start_r83_training.ps1",
            ROOT / "scripts" / "start_r83_background.ps1",
            ROOT / "scripts" / "foreground_r83_monitor.ps1",
        )
        for path in required:
            self.assertTrue(path.is_file(), path)
        live = self.config["live_validation"]
        self.assertEqual(live["role"], "observation_only_no_loss_no_selection_no_training_control")
        for row in live["images"]:
            self.assertTrue((ROOT / row["relative_image_path"]).is_file())

    def test_13_checkpoint_and_confirmation_scopes_are_locked(self) -> None:
        selection = self.config["formal_checkpoint_selection"]
        self.assertEqual(selection["eligible_epochs"], [0, 5, 10, 15, 20, 25, 30])
        development = set(self.config["locked_confirmation"]["sem_acm"]["development_pillar_ids"])
        reserved = set(self.config["final_confirmation_protocol"]["sem_reserved"]["pillar_ids"])
        self.assertFalse(development & reserved)
        self.assertEqual(development | reserved, set(range(1, 37)))
        self.assertTrue((ROOT / "reports" / "formal_selection_lock.json").is_file())
        self.assertTrue((ROOT / "reports" / "final_confirmation_lock.json").is_file())

    def test_14_final_confirmation_scripts_exist(self) -> None:
        required = (
            ROOT / "scripts" / "prepare_formal_checkpoint_screen.py",
            ROOT / "scripts" / "analyze_formal_checkpoint_screen.py",
            ROOT / "scripts" / "run_formal_checkpoint_screen.ps1",
            ROOT / "scripts" / "run_sem_acm_selected_pillars.m",
            ROOT / "scripts" / "prepare_final_confirmation.py",
            ROOT / "scripts" / "evaluate_final_real_motion.py",
            ROOT / "scripts" / "analyze_final_confirmation.py",
            ROOT / "scripts" / "run_final_confirmation.ps1",
            ROOT / "scripts" / "freeze_epoch_zero_safety_candidate.py",
        )
        for path in required:
            self.assertTrue(path.is_file(), path)

    def test_15_locked_holdout_acm_cohort_is_predeclared(self) -> None:
        package = ROOT / "data" / "r83_locked_holdout_severe_microscopy"
        manifest_path = package / "manifest.json"
        self.assertEqual(
            r83_dataset._sha256(manifest_path),
            "1a7768fb1afd23829c3b9c75617b1d66be4df42703be865f6eef26cfccf9baf9",
        )
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        eligible = [
            row for row in manifest["pairs"]
            if row["training_role"] in {"basic_geometry", "fine_noncircular"}
            or (row["training_role"] == "boundary_fade_mixed" and row["target_policy"] == "clean_analytic")
        ]
        self.assertEqual(len(manifest["pairs"]), 384)
        self.assertEqual(len(eligible), 160)

    def test_16_final_decision_preserves_r79(self) -> None:
        decision = json.loads(
            (ROOT / "results" / "final_confirmation" / "final_decision.json").read_text(encoding="utf-8")
        )
        self.assertEqual(decision["recommended_mode"], "R79")
        self.assertFalse(decision["research_candidate_confirmed"])
        self.assertTrue(decision["restricted_full_frame_safe_mode_available"])
        self.assertFalse(decision["gates"]["R83Direct"]["tile_consistency"])
        self.assertFalse(decision["gates"]["R83Safe"]["tile_consistency"])
        self.assertTrue(decision["gates"]["R83Safe"]["real_fov_6_of_6"])

    def test_17_inference_defaults_to_selected_direct_full_frame(self) -> None:
        path = ROOT / "inference" / "infer_r83.py"
        spec = importlib.util.spec_from_file_location("r83_inference_test", path)
        self.assertIsNotNone(spec)
        self.assertIsNotNone(spec.loader if spec else None)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        self.assertEqual(module.INFERENCE_MODE, "direct")
        self.assertEqual(module.TILE_SIZE, 4096)
        self.assertFalse(module.ALLOW_TILED_INFERENCE)
        self.assertEqual(module.find_latest_formal_checkpoint(), ROOT / "weights" / "selected" / "r83_model.pth.tar")
        raw = np.full((16, 16), 100, dtype=np.uint8)
        direct = np.full((16, 16), 200, dtype=np.uint8)
        safe = module.safe_output(raw, direct, 0.25)
        self.assertTrue(np.all(safe == 125))

    def test_18_closeout_manifest_counts(self) -> None:
        closeout = json.loads((ROOT / "reports" / "closeout_manifest.json").read_text(encoding="utf-8"))
        counts = closeout["counts"]
        self.assertEqual(closeout["recommended_mode"], "R79")
        self.assertEqual(counts["formal_pairs"], 5120)
        self.assertEqual(counts["locked_holdout_pairs"], 384)
        self.assertEqual(counts["locked_synthetic_metric_rows"], 1536)
        self.assertEqual(counts["reserved_sem_pillars"], 24)
        self.assertEqual(counts["reserved_sem_exposures"], 12)
        self.assertEqual(counts["real_motion_sequences_per_method"], {"R79": 6, "R83Direct": 6, "R83Safe": 6})
        self.assertEqual(counts["invalidated_runs"], 5)


if __name__ == "__main__":
    unittest.main()

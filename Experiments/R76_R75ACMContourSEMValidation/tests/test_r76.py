from __future__ import annotations

import hashlib
import json
from pathlib import Path
import unittest

import numpy as np
import pandas as pd
from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
CONFIG = json.loads((ROOT / "config" / "experiment.json").read_text(encoding="utf-8"))
R69 = Path(CONFIG["paired_evidence"]["r69_root"])
TABLES = ROOT / "results" / "tables"
RECON = Path(CONFIG["inference"]["reconstruction_dir"])


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


class R76ValidationTests(unittest.TestCase):
    def test_source_and_checkpoint_audit_passed(self) -> None:
        audit = json.loads((ROOT / "results" / "input_audit.json").read_text(encoding="utf-8"))
        self.assertEqual(audit["status"], "passed")
        self.assertEqual(audit["optical_files_verified"], 12)
        self.assertEqual(audit["sem_files_verified"], 18)
        self.assertEqual(audit["physical_pillars_verified"], 36)
        self.assertTrue(audit["mapping_matches_r69"])
        self.assertFalse(audit["sem_used_for_checkpoint_selection"])
        self.assertFalse(audit["checkpoint_loaded_during_training"])
        self.assertFalse(audit["teacher_loaded_during_training"])
        self.assertEqual(audit["training_completed_epochs"], 100)
        self.assertGreaterEqual(audit["selected_checkpoint_epoch"], 1)
        self.assertLessEqual(audit["selected_checkpoint_epoch"], 100)
        self.assertEqual(audit["selected_checkpoint_state"], "ema_state_dict")
        checkpoint = Path(audit["checkpoint"])
        final_epoch = Path(audit["final_epoch_checkpoint"])
        self.assertTrue(checkpoint.is_file())
        self.assertTrue(final_epoch.is_file())
        self.assertEqual(sha256(checkpoint), audit["checkpoint_sha256"])
        self.assertEqual(sha256(final_epoch), audit["final_epoch_checkpoint_sha256"])

    def test_verified_mapping_has_the_expected_36_physical_pillars(self) -> None:
        mapping = pd.read_csv(TABLES / "verified_pillar_mapping.csv")
        self.assertEqual(len(mapping), 36)
        self.assertEqual(mapping["pillar_id"].nunique(), 36)
        self.assertEqual(mapping[["grid_row", "grid_col"]].drop_duplicates().shape[0], 36)
        self.assertTrue((mapping.groupby("sem_file").size() == 4).all())
        actual = mapping.pivot(index="grid_row", columns="grid_col", values="pillar_id").to_numpy(int)
        expected = np.array(
            [
                [6, 5, 4, 3, 2, 1],
                [12, 11, 10, 9, 8, 7],
                [18, 17, 16, 15, 14, 13],
                [24, 23, 22, 21, 20, 19],
                [30, 29, 28, 27, 26, 25],
                [36, 35, 34, 33, 32, 31],
            ]
        )
        np.testing.assert_array_equal(actual, expected)
        prior = pd.read_csv(R69 / "results" / "tables" / "pillar_mapping.csv")
        columns = ["pillar_id", "grid_row", "grid_col", "sem_file", "sem_corner"]
        pd.testing.assert_frame_equal(
            mapping[columns].sort_values("pillar_id").reset_index(drop=True),
            prior[columns].sort_values("pillar_id").reset_index(drop=True),
            check_dtype=False,
        )

    def test_all_reconstructions_use_the_locked_checkpoint(self) -> None:
        audit = json.loads((ROOT / "results" / "input_audit.json").read_text(encoding="utf-8"))
        manifest = json.loads((RECON / "inference_manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["checkpoint_sha256"], audit["checkpoint_sha256"])
        self.assertEqual(manifest["state_key"], "ema_state_dict")
        self.assertEqual(manifest["image_count"], 12)
        for exposure in range(13, 25):
            path = RECON / f"{exposure}.bmp"
            self.assertTrue(path.is_file(), path)
            with Image.open(path) as image:
                self.assertEqual(image.size, (821, 821))

    def test_acm_tables_are_complete_and_raw_is_reproducible(self) -> None:
        primary = pd.read_csv(TABLES / "primary_contour_metrics.csv")
        sensitivity = pd.read_csv(TABLES / "acm_sensitivity_metrics.csv")
        self.assertEqual(len(primary), 864)
        self.assertEqual(len(sensitivity), 648)
        self.assertEqual(set(primary["method"]), {"Raw", "R75"})
        self.assertEqual(set(sensitivity["method"]), {"Raw", "R75"})
        self.assertFalse(primary.isna().any().any())
        self.assertFalse(sensitivity.isna().any().any())

        prior = pd.read_csv(R69 / "results" / "tables" / "primary_contour_metrics.csv")
        columns = [
            "iou",
            "dice",
            "mean_boundary_distance_pitch_pct",
            "hd95_pitch_pct",
            "area_error_pct",
            "perimeter_error_pct",
            "circularity_abs_error",
            "centroid_alignment_shift_px",
        ]
        key = ["exposure", "pillar_id"]
        current_raw = primary[primary["method"] == "Raw"].sort_values(key).reset_index(drop=True)
        prior_raw = prior[prior["method"] == "Raw"].sort_values(key).reset_index(drop=True)
        np.testing.assert_allclose(current_raw[columns], prior_raw[columns], rtol=0, atol=1e-12)

    def test_four_method_outputs_have_the_locked_statistical_grain(self) -> None:
        primary = pd.read_csv(TABLES / "four_method_primary_contour_metrics.csv")
        per_pillar = pd.read_csv(TABLES / "four_method_per_pillar_summary.csv")
        comparisons = pd.read_csv(TABLES / "r75_paired_comparison_summary.csv")
        exposure = pd.read_csv(TABLES / "four_method_per_exposure_summary.csv")
        sensitivity = pd.read_csv(TABLES / "four_method_sensitivity_summary.csv")
        self.assertEqual(len(primary), 12 * 36 * 4)
        self.assertEqual(primary.groupby(["exposure", "pillar_id", "method"]).size().max(), 1)
        self.assertEqual(set(primary["method"]), {"Raw", "R61v16", "V42E120", "R75"})
        self.assertEqual(len(per_pillar), 36)
        self.assertEqual(len(comparisons), 3 * 7)
        self.assertEqual(len(exposure), 12)
        self.assertEqual(len(sensitivity), 3 * 3)

    def test_decision_matches_saved_statistics(self) -> None:
        decision = json.loads((ROOT / "results" / "decision.json").read_text(encoding="utf-8"))
        comparisons = pd.read_csv(TABLES / "r75_paired_comparison_summary.csv")
        raw = comparisons[comparisons["comparison"] == "Raw_to_R75"].set_index("metric")
        expected_coarse = all(
            raw.loc[metric, "bootstrap_ci95_low"] > 0
            and raw.loc[metric, "improved_fraction"] >= 0.60
            for metric in ["iou", "mean_boundary_distance_pitch_pct"]
        )
        self.assertEqual(decision["primary_coarse_contour_gate"], expected_coarse)
        self.assertIn(
            decision["status"],
            {
                "pass_universal_full_shape",
                "pass_coarse_universal_fine_shape_not_proven",
                "conditional_pass_not_universal",
                "coarse_improvement_not_proven",
            },
        )

    def test_report_and_all_figures_are_readable(self) -> None:
        report = ROOT / "reports" / "R76_RESULTS_TW.md"
        self.assertTrue(report.is_file())
        self.assertIn("結論先行", report.read_text(encoding="utf-8"))
        figures = sorted((ROOT / "results" / "figures").glob("*.png"))
        self.assertGreaterEqual(len(figures), 7)
        for path in figures:
            with Image.open(path) as image:
                image.verify()

    def test_epoch100_audit_is_complete_and_independent(self) -> None:
        audit_root = ROOT / "results" / "epoch100_audit"
        table_dir = audit_root / "results" / "tables"
        primary = pd.read_csv(table_dir / "primary_contour_metrics.csv")
        sensitivity = pd.read_csv(table_dir / "acm_sensitivity_metrics.csv")
        comparisons = pd.read_csv(table_dir / "epoch100_paired_comparison_summary.csv")
        per_pillar = pd.read_csv(table_dir / "five_method_per_pillar_summary.csv")
        exposure = pd.read_csv(table_dir / "five_method_per_exposure_summary.csv")
        self.assertEqual(len(primary), 864)
        self.assertEqual(len(sensitivity), 648)
        self.assertEqual(set(primary["method"]), {"Raw", "R75E100"})
        self.assertEqual(len(comparisons), 4 * 7)
        self.assertEqual(len(per_pillar), 36)
        self.assertEqual(len(exposure), 12)
        decision = json.loads((audit_root / "decision.json").read_text(encoding="utf-8"))
        self.assertIn("epoch100_coarse_contour_gate_vs_raw", decision)
        self.assertTrue((ROOT / "reports" / "R76_EPOCH100_AUDIT_TW.md").is_file())
        self.assertTrue((ROOT / "reports" / "R76_FINAL_SYNTHESIS_TW.md").is_file())
        self.assertTrue((ROOT / "results" / "figures" / "07_r75_best_vs_epoch100_paired_comparison.png").is_file())
        self.assertTrue((ROOT / "results" / "figures" / "08_r75_checkpoint_exposure_comparison.png").is_file())
        self.assertTrue((ROOT / "results" / "figures" / "09_raw_epoch100_reconstruction_comparison.png").is_file())
        self.assertTrue((ROOT / "results" / "figures" / "10_epoch100_center36_contour_overlay_exp18.png").is_file())

    def test_final_synthesis_numbers_match_saved_tables(self) -> None:
        table = pd.read_csv(
            ROOT
            / "results"
            / "epoch100_audit"
            / "results"
            / "tables"
            / "five_method_per_pillar_summary.csv"
        )
        report = (ROOT / "reports" / "R76_FINAL_SYNTHESIS_TW.md").read_text(encoding="utf-8")
        expected = {
            "raw": ["0.949", "0.570", "5.336", "2.865", "0.016"],
            "r61v16": ["0.958", "0.441", "4.131", "3.710", "0.025"],
            "v42e120": ["0.953", "0.523", "4.847", "3.031", "0.019"],
            "r75_best_e21": ["0.914", "1.041", "9.454", "5.233", "0.029"],
            "r75_e100": ["0.951", "0.530", "5.041", "3.490", "0.029"],
        }
        metrics = [
            "iou",
            "mean_boundary_distance_pitch_pct",
            "area_error_pct",
            "perimeter_error_pct",
            "circularity_abs_error",
        ]
        for method, displayed in expected.items():
            computed = [f"{table[f'{method}_{metric}'].median():.3f}" for metric in metrics]
            self.assertEqual(computed, displayed)
            for value in computed:
                self.assertIn(value, report)


if __name__ == "__main__":
    unittest.main()

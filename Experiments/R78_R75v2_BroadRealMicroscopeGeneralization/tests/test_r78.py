from __future__ import annotations

import json
import unittest
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "results"
TABLES = RESULTS / "tables"


class R78ValidationTests(unittest.TestCase):
    def test_locked_input_and_output_coverage(self) -> None:
        audit = json.loads((RESULTS / "input_audit.json").read_text(encoding="utf-8"))
        self.assertEqual(audit["total_frames"], 301)
        self.assertTrue(audit["source_hashes_verified"])
        self.assertEqual(audit["r75v2_output_validation"]["frames_checked"], 301)
        self.assertTrue(audit["r75v2_output_validation"]["all_shapes_match"])
        self.assertEqual(set(audit["sequences"]), {
            "5x_0p5um", "5x_1um", "20x_0p5um", "20x_1um", "50x_0p5um", "50x_1um"
        })

    def test_primary_comparison_is_paired_and_complete(self) -> None:
        summary = pd.read_csv(TABLES / "sequence_method_summary.csv")
        self.assertEqual(len(summary), 12)
        self.assertEqual(set(summary["method"]), {"R61v16", "R75v2E100"})
        self.assertTrue((summary.groupby("sequence")["method"].nunique() == 2).all())
        paired_counts = summary.pivot(index="sequence", columns="method", values="raw_reference_measurements")
        self.assertTrue((paired_counts["R61v16"] == paired_counts["R75v2E100"]).all())
        self.assertTrue(summary["sequence_pass"].all())

    def test_locked_r61_result_reproduced(self) -> None:
        decision = json.loads((RESULTS / "decision.json").read_text(encoding="utf-8"))
        self.assertTrue(decision["r61_locked_result_reproduced"]["passed"])
        self.assertLessEqual(
            decision["r61_locked_result_reproduced"]["maximum_absolute_difference"], 1e-12
        )

    def test_acm_sem_arm_and_claim_boundary(self) -> None:
        acm = pd.read_csv(TABLES / "acm_sem_truth_summary.csv")
        self.assertEqual(set(acm["method"]), {"Raw", "R61v16", "R75v2E100"})
        self.assertTrue((acm["independent_pillars"] == 36).all())
        decision = json.loads((RESULTS / "decision.json").read_text(encoding="utf-8"))
        self.assertTrue(decision["r75v2_acm_sem"]["coarse_contour_gate_vs_raw"])
        self.assertFalse(decision["r75v2_acm_sem"]["fine_shape_gate_vs_raw"])
        self.assertFalse(decision["universal_cross_sample_pass"])
        self.assertEqual(
            decision["current_recommendation"]["project_generalization_baseline"], "R61v16"
        )

    def test_post_hoc_5x_confirmation_is_disclosed(self) -> None:
        summary = pd.read_csv(TABLES / "followup_5x_summary.csv")
        self.assertEqual(len(summary), 6)
        self.assertTrue((summary["frames"] == 50).all())
        decision = json.loads((RESULTS / "followup_5x_decision.json").read_text(encoding="utf-8"))
        self.assertEqual(decision["evidence_role"], "post_hoc_confirmatory")
        self.assertTrue(decision["r75v2_5x_anomaly_repeated_in_both_sequences"])
        self.assertTrue(decision["larger_tiles_reduce_warning_in_both_sequences"])
        self.assertFalse(decision["larger_tiles_fully_restore_fine_detail"])
        motion = json.loads(
            (RESULTS / "followup_5x_tile1024_motion_decision.json").read_text(encoding="utf-8")
        )
        self.assertTrue(motion["tile1024_both_5x_sequences_pass_motion"])

    def test_figures_and_report_exist(self) -> None:
        expected = [
            "01_motion_comparison.png",
            "02_artifact_diagnostic.png",
            "03_acm_sem_truth_comparison.png",
            "04_fixed_raw_r61_r75_contact_sheet.png",
            "05_followup_5x_tile_sensitivity.png",
        ]
        for name in expected:
            path = RESULTS / "figures" / name
            self.assertTrue(path.is_file(), name)
            self.assertGreater(path.stat().st_size, 10_000, name)
        report = (ROOT / "reports" / "R78_RESULTS_TW.md").read_text(encoding="utf-8")
        self.assertIn("301 張真實顯微影像", report)
        self.assertIn("R61 仍保留為廣泛場景基準", report)
        self.assertIn("5 倍異常的追加確認", report)


if __name__ == "__main__":
    unittest.main()

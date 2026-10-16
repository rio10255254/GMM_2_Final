from __future__ import annotations

import json
import unittest
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "results"
TABLES = RESULTS / "tables"


class R71OutputTests(unittest.TestCase):
    def test_input_audit_is_independent_and_complete(self) -> None:
        audit = json.loads((RESULTS / "input_audit.json").read_text(encoding="utf-8"))
        self.assertEqual(audit["total_images"], 100)
        self.assertEqual(set(audit["family_counts"].values()), {20})
        self.assertTrue(audit["independent_of_r61_training"])
        self.assertEqual(audit["training_path_reference_hits"], 0)
        self.assertEqual(audit["exact_content_overlap_hashes"], 0)

    def test_all_reconstructions_exist(self) -> None:
        manifest = json.loads((RESULTS / "inference_manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["reconstructed_images"], 100)
        self.assertEqual(len(manifest["output_dirs"]), 5)
        for directory in manifest["output_dirs"].values():
            self.assertEqual(len(list(Path(directory).glob("*.bmp"))), 20)

    def test_metric_tables_have_locked_grain(self) -> None:
        metrics = pd.read_csv(TABLES / "per_image_metrics.csv")
        paired = pd.read_csv(TABLES / "paired_image_comparisons.csv")
        self.assertEqual(len(metrics), 300)
        self.assertEqual(metrics["image_id"].nunique(), 100)
        self.assertEqual(set(metrics["method"]), {"raw", "combo", "r61"})
        self.assertEqual(len(paired), 100)
        self.assertFalse(metrics[["psnr_db", "ssim", "edge_f1_t2", "highpass_corr"]].isna().any().any())
        self.assertTrue(metrics["ssim"].between(-1, 1).all())
        self.assertTrue(metrics["edge_f1_t2"].between(0, 1).all())

    def test_decision_and_report_are_complete(self) -> None:
        decision = json.loads((RESULTS / "decision.json").read_text(encoding="utf-8"))
        self.assertIn(decision["verdict"], {"PASS_GENERALIZATION_PILOT", "PARTIAL_AGGREGATE_ONLY", "FAIL_GENERALIZATION_PILOT"})
        self.assertEqual(len(decision["gates"]), 4)
        self.assertEqual(len(decision["family_checks"]), 5)
        self.assertTrue((ROOT / "reports" / "R71_RESULTS_TW.md").is_file())
        sensitivity = pd.read_csv(TABLES / "edge_sensitivity_summary.csv")
        self.assertEqual(len(sensitivity), 16)

    def test_figures_exist_and_are_nonempty(self) -> None:
        expected = [
            "01_representative_reconstructions.png",
            "02_metric_comparison_by_family.png",
            "03_paired_improvement_distributions.png",
            "04_defect_focus_examples.png",
            "05_worst_failure_cases.png",
            "06_edge_sensitivity_heatmap.png",
        ]
        for name in expected:
            path = RESULTS / "figures" / name
            self.assertTrue(path.is_file(), name)
            self.assertGreater(path.stat().st_size, 20_000, name)


if __name__ == "__main__":
    unittest.main()

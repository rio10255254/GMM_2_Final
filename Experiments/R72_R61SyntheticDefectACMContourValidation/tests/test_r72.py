from __future__ import annotations

import json
import unittest
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.io import loadmat


ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "results"
TABLES = RESULTS / "tables"


class R72ValidationTests(unittest.TestCase):
    def test_input_audit(self) -> None:
        audit = json.loads((RESULTS / "input_audit.json").read_text(encoding="utf-8"))
        self.assertTrue(audit["independent_of_r61_training"])
        self.assertTrue(audit["source_filenames_match"])
        self.assertEqual(audit["independent_image_count"], 20)
        self.assertTrue(all(count == 20 for count in audit["source_counts"].values()))
        self.assertFalse(audit["acm_initialization_uses_truth_shape"])
        self.assertFalse(audit["scale_fitting"])
        self.assertFalse(audit["rotation_fitting"])

    def test_primary_table_is_complete(self) -> None:
        frame = pd.read_csv(TABLES / "primary_contour_metrics.csv")
        self.assertEqual(len(frame), 120)
        counts = frame.groupby(["method", "alignment"]).size()
        self.assertEqual(set(counts.index.get_level_values("method")), {"Raw", "COMBO", "R61v16"})
        self.assertEqual(set(counts.index.get_level_values("alignment")), {"translation_only", "fixed_pixel_coordinates"})
        self.assertTrue((counts == 20).all())
        self.assertFalse(frame.isna().any().any())

    def test_sensitivity_table_is_complete(self) -> None:
        frame = pd.read_csv(TABLES / "acm_sensitivity_metrics.csv")
        self.assertEqual(len(frame), 54)
        self.assertEqual(set(frame["preset"]), {"low_smooth", "primary", "high_smooth"})
        self.assertEqual(set(frame["method"]), {"Raw", "COMBO", "R61v16"})
        self.assertFalse(frame.isna().any().any())

    def test_decision_matches_measured_result(self) -> None:
        decision = json.loads((RESULTS / "decision.json").read_text(encoding="utf-8"))
        self.assertEqual(decision["verdict"], "CONDITIONAL_COARSE_CONTOUR_PASS")
        self.assertTrue(decision["coarse_contour_pass"])
        self.assertTrue(decision["sensitivity_pass"])
        self.assertFalse(decision["fine_shape_pass"])

    def test_masks_are_binary_and_complete(self) -> None:
        masks = loadmat(RESULTS / "masks" / "acm_primary_masks.mat")
        for key in ("truth_masks", "raw_masks", "combo_masks", "r61_masks"):
            self.assertIn(key, masks)
            self.assertEqual(masks[key].shape, (512, 512, 20))
            self.assertTrue(np.isin(np.unique(masks[key]), [0, 1]).all())

    def test_figures_and_report_exist(self) -> None:
        expected = {
            "00_truth_and_method_acm_qa.png",
            "01_acm_contour_examples.png",
            "02_acm_metric_comparison.png",
            "03_paired_contour_improvement.png",
            "04_acm_sensitivity.png",
            "05_worst_acm_cases.png",
            "06_alignment_effect.png",
        }
        found = {path.name for path in (RESULTS / "figures").glob("*.png") if path.stat().st_size > 10_000}
        self.assertTrue(expected.issubset(found))
        report = (ROOT / "reports" / "R72_RESULTS_TW.md").read_text(encoding="utf-8")
        self.assertIn("ACM", report)
        self.assertIn("20", report)
        self.assertIn("亮度", report)
        self.assertIn("粗外框有條件通過", report)


if __name__ == "__main__":
    unittest.main()

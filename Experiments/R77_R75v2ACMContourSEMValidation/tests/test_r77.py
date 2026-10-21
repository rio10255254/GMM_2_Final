from __future__ import annotations

import json
from pathlib import Path
import unittest

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]


class R77ValidationTests(unittest.TestCase):
    def test_input_audit_passed(self) -> None:
        audit = json.loads((ROOT / "results" / "input_audit.json").read_text(encoding="utf-8"))
        self.assertEqual(audit["status"], "passed")
        self.assertEqual(audit["selected_checkpoint_epoch"], 84)
        self.assertFalse(audit["sem_used_for_checkpoint_selection"])
        self.assertEqual(audit["physical_pillars_verified"], 36)

    def test_acm_outputs_complete(self) -> None:
        best = pd.read_csv(ROOT / "results" / "tables" / "primary_contour_metrics.csv")
        final = pd.read_csv(ROOT / "results" / "epoch100_audit" / "results" / "tables" / "primary_contour_metrics.csv")
        self.assertEqual(len(best), 864)
        self.assertEqual(len(final), 864)
        self.assertEqual(set(best["method"]), {"Raw", "R75v2Best"})
        self.assertEqual(set(final["method"]), {"Raw", "R75v2E100"})
        self.assertFalse(best.isna().any().any())
        self.assertFalse(final.isna().any().any())

    def test_raw_reproducible(self) -> None:
        best = pd.read_csv(ROOT / "results" / "tables" / "primary_contour_metrics.csv")
        final = pd.read_csv(ROOT / "results" / "epoch100_audit" / "results" / "tables" / "primary_contour_metrics.csv")
        columns = ["iou", "mean_boundary_distance_pitch_pct", "hd95_pitch_pct", "area_error_pct", "circularity_abs_error"]
        key = ["exposure", "pillar_id"]
        a = best[best["method"] == "Raw"].sort_values(key).reset_index(drop=True)
        b = final[final["method"] == "Raw"].sort_values(key).reset_index(drop=True)
        self.assertTrue(np.allclose(a[columns], b[columns], rtol=0, atol=1e-12))

    def test_final_analysis_complete(self) -> None:
        decision = json.loads((ROOT / "results" / "decision.json").read_text(encoding="utf-8"))
        self.assertEqual(decision["status"], "complete")
        self.assertIn("best_e84", decision)
        self.assertIn("final_e100", decision)
        self.assertTrue((ROOT / "reports" / "R77_RESULTS_TW.md").is_file())
        for name in [
            "01_all_models_paired_comparison.png",
            "02_exposure_stability.png",
            "03_checkpoint_comparison.png",
            "04_raw_best_e100_image_comparison.png",
            "05_center36_contour_overlay_exp18.png",
        ]:
            self.assertTrue((ROOT / "results" / "figures" / name).is_file())


if __name__ == "__main__":
    unittest.main()

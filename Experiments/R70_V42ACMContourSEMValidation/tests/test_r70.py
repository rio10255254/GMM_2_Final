from __future__ import annotations

import json
from pathlib import Path
import unittest

import numpy as np
import pandas as pd
from PIL import Image
PROJECT_ROOT = Path(__file__).resolve().parents[3]


ROOT = Path(__file__).resolve().parents[1]
R69 = Path(str(PROJECT_ROOT / 'Experiments/R69_ACMContourSEMValidation'))
TABLES = ROOT / "results" / "tables"
RECON = (
    ROOT
    / "results"
    / "inference_runs"
    / "reconstruct_progress_epoch_120_in_sem_paired_50x_exposure_stack_20260709_202713"
    / "v42e120_sem_paired_50x"
)


class R70ValidationTests(unittest.TestCase):
    def test_all_reconstructions_exist_with_original_size(self) -> None:
        for exposure in range(13, 25):
            path = RECON / f"{exposure}.bmp"
            self.assertTrue(path.is_file(), path)
            with Image.open(path) as image:
                self.assertEqual(image.size, (821, 821))

    def test_v42_primary_and_sensitivity_tables_are_complete(self) -> None:
        primary = pd.read_csv(TABLES / "primary_contour_metrics.csv")
        sensitivity = pd.read_csv(TABLES / "acm_sensitivity_metrics.csv")
        self.assertEqual(len(primary), 864)
        self.assertEqual(len(sensitivity), 648)
        self.assertEqual(set(primary["method"]), {"Raw", "V42E120"})
        self.assertFalse(primary.isna().any().any())
        self.assertFalse(sensitivity.isna().any().any())

    def test_rerun_raw_metrics_match_r69_exactly(self) -> None:
        current = pd.read_csv(TABLES / "primary_contour_metrics.csv")
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
        a = current[current["method"] == "Raw"].sort_values(key).reset_index(drop=True)
        b = prior[prior["method"] == "Raw"].sort_values(key).reset_index(drop=True)
        np.testing.assert_allclose(a[columns], b[columns], rtol=0, atol=1e-12)

    def test_three_method_outputs_have_locked_grain(self) -> None:
        primary = pd.read_csv(TABLES / "three_method_primary_contour_metrics.csv")
        per_pillar = pd.read_csv(TABLES / "three_method_per_pillar_summary.csv")
        comparison = pd.read_csv(TABLES / "v42_paired_comparison_summary.csv")
        exposure = pd.read_csv(TABLES / "three_method_per_exposure_summary.csv")
        self.assertEqual(len(primary), 12 * 36 * 3)
        self.assertEqual(primary.groupby(["exposure", "pillar_id", "method"]).size().max(), 1)
        self.assertEqual(len(per_pillar), 36)
        self.assertEqual(len(comparison), 14)
        self.assertEqual(len(exposure), 12)

    def test_decision_and_visuals_exist(self) -> None:
        decision = json.loads((ROOT / "results" / "decision.json").read_text(encoding="utf-8"))
        self.assertIn("status_vs_raw", decision)
        figures = list((ROOT / "results" / "figures").glob("*.png"))
        self.assertGreaterEqual(len(figures), 6)
        self.assertTrue((ROOT / "reports" / "R70_RESULTS_TW.md").is_file())


if __name__ == "__main__":
    unittest.main()

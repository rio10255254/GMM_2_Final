from __future__ import annotations

import json
from pathlib import Path
import unittest

import numpy as np
import pandas as pd
from scipy.io import loadmat


ROOT = Path(__file__).resolve().parents[1]
TABLES = ROOT / "results" / "tables"
FIGURES = ROOT / "results" / "figures"


class R69ValidationTests(unittest.TestCase):
    def test_input_and_reconstruction_counts(self) -> None:
        inputs = ROOT / "inputs" / "sem_paired_50x_exposure_stack"
        recon = (
            ROOT
            / "results"
            / "inference_runs"
            / "reconstruct_progress_best_tradeoff_in_sem_paired_50x_exposure_stack_20260623_200020"
            / "r61v16_psfoff_sem_paired_50x"
        )
        self.assertEqual({path.stem for path in inputs.glob("*.bmp")}, {str(i) for i in range(13, 25)})
        self.assertEqual({path.stem for path in recon.glob("*.bmp")}, {str(i) for i in range(13, 25)})

    def test_primary_table_is_complete_and_physical(self) -> None:
        data = pd.read_csv(TABLES / "primary_contour_metrics.csv")
        self.assertEqual(len(data), 864)
        self.assertEqual(data.duplicated(["exposure", "pillar_id", "method"]).sum(), 0)
        self.assertEqual(set(data["exposure"]), set(range(13, 25)))
        self.assertEqual(set(data["pillar_id"]), set(range(1, 37)))
        self.assertEqual(set(data["method"]), {"Raw", "R61v16"})
        self.assertFalse(data.isna().any().any())
        self.assertTrue(data["truth_circularity"].between(0, 1).all())
        self.assertTrue(data["pred_circularity"].between(0, 1).all())

    def test_sensitivity_table_is_complete(self) -> None:
        data = pd.read_csv(TABLES / "acm_sensitivity_metrics.csv")
        self.assertEqual(len(data), 648)
        self.assertEqual(
            data.duplicated(["preset", "exposure", "pillar_id", "method"]).sum(), 0
        )
        self.assertEqual(set(data["preset"]), {"less_smooth", "primary", "more_smooth"})
        self.assertEqual(set(data["exposure"]), {13, 18, 24})
        self.assertFalse(data.isna().any().any())

    def test_qa_masks_do_not_touch_outer_guard(self) -> None:
        data = loadmat(ROOT / "results" / "masks" / "acm_qa_masks.mat", squeeze_me=True)
        support = float(data["support_radius"])
        truth = data["truth_masks"].astype(bool)
        height, width, _ = truth.shape
        yy, xx = np.indices((height, width))
        radius = np.hypot(xx - (width - 1) / 2, yy - (height - 1) / 2)
        for name in ["truth_masks", "raw_masks", "recon_masks"]:
            masks = data[name].astype(bool)
            if masks.ndim == 3:
                masks = masks[..., np.newaxis]
            self.assertFalse(np.any(masks & (radius[:, :, np.newaxis, np.newaxis] >= support - 0.5)))

    def test_derived_outputs_and_decision(self) -> None:
        expected_tables = [
            "per_pillar_summary.csv",
            "per_exposure_summary.csv",
            "paired_metric_summary.csv",
            "acm_sensitivity_summary.csv",
        ]
        for name in expected_tables:
            self.assertTrue((TABLES / name).is_file(), name)
        for index in range(1, 8):
            matches = list(FIGURES.glob(f"{index:02d}_*.png"))
            self.assertEqual(len(matches), 1, f"figure {index:02d}")
            self.assertGreater(matches[0].stat().st_size, 50_000)
        self.assertTrue((ROOT / "reports" / "R69_RESULTS_TW.md").is_file())

        decision = json.loads((ROOT / "results" / "decision.json").read_text(encoding="utf-8"))
        self.assertEqual(decision["status"], "conditional_pass_not_universal")
        self.assertTrue(decision["primary_coarse_contour_gate"])
        self.assertTrue(decision["normal_exposure_range_pass"])
        self.assertFalse(decision["all_exposure_universal_gate"])
        self.assertFalse(decision["darkest_exposures_pass"])
        self.assertFalse(decision["fine_shape_fidelity_gate"])
        self.assertEqual(
            decision["acm_sensitivity_direction_consistent"],
            {"13": True, "18": True, "24": False},
        )


if __name__ == "__main__":
    unittest.main()

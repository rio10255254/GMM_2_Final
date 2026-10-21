from __future__ import annotations

import json
import unittest
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "results"
TABLES = RESULTS / "tables"


class R80ValidationTests(unittest.TestCase):
    def test_input_audit_is_complete(self) -> None:
        audit = json.loads((RESULTS / "input_audit.json").read_text(encoding="utf-8"))
        self.assertEqual(audit["status"], "pass")
        self.assertEqual(audit["internal_test"]["images"], 512)
        self.assertEqual(audit["internal_test"]["geometry_ids"], 64)
        self.assertEqual(audit["internal_test"]["geometry_overlap_with_train_or_validation"], 0)
        self.assertEqual(audit["real_fov"]["total_frames"], 301)
        self.assertEqual(audit["sem_acm"]["physical_pillars"], 36)
        self.assertEqual(audit["sem_acm"]["optical_exposures"], 12)

    def test_internal_test_is_paired_and_complete(self) -> None:
        frame = pd.read_csv(TABLES / "internal_test_per_image.csv")
        self.assertEqual(len(frame), 1024)
        self.assertEqual(set(frame["model"]), {"R79E23", "R79E100"})
        counts = frame.groupby("pair_id")["model"].nunique()
        self.assertEqual(len(counts), 512)
        self.assertTrue((counts == 2).all())
        self.assertFalse(frame.isna().any().any())

    def test_real_fov_uses_all_locked_sequences(self) -> None:
        summary = pd.read_csv(TABLES / "real_motion_summary.csv")
        self.assertEqual(len(summary), 12)
        self.assertEqual(summary["sequence"].nunique(), 6)
        self.assertEqual(set(summary["method"]), {"R79E23", "R79E100"})
        tile = pd.read_csv(TABLES / "real_5x_tile_sensitivity.csv")
        self.assertEqual(len(tile), 400)
        self.assertEqual(set(tile["tile_size"]), {512, 1024})
        self.assertEqual(tile.groupby(["sequence", "method", "tile_size"]).size().nunique(), 1)

    def test_external_acm_is_fully_paired(self) -> None:
        frame = pd.read_csv(TABLES / "external_acm_primary_combined.csv")
        translated = frame.loc[frame["alignment"] == "translation_only"]
        self.assertEqual(len(translated), 600)
        self.assertEqual(set(translated["method"]), {"Raw", "R79E23", "R79E100"})
        counts = translated.groupby(["suite", "image_id"])["method"].nunique()
        self.assertEqual(len(counts), 200)
        self.assertTrue((counts == 3).all())
        self.assertFalse(translated.isna().any().any())

    def test_sem_acm_has_36_independent_pillars(self) -> None:
        per_pillar = pd.read_csv(TABLES / "sem_acm_per_pillar.csv")
        self.assertEqual(len(per_pillar), 108)
        self.assertEqual(per_pillar["pillar_id"].nunique(), 36)
        self.assertEqual(set(per_pillar["method"]), {"Raw", "R79E23", "R79E100"})
        self.assertTrue((per_pillar["exposures"] == 12).all())
        self.assertFalse(per_pillar.isna().any().any())

    def test_decision_and_handoff_are_consistent(self) -> None:
        decision = json.loads((RESULTS / "decision.json").read_text(encoding="utf-8"))
        self.assertEqual(decision["status"], "complete")
        recommendation = decision["selection"]["recommended_r79_checkpoint"]
        self.assertIn(recommendation, {"R79E23", "R79E100", "unresolved"})
        self.assertTrue((ROOT / "reports" / "R80_RESULTS_TW.md").is_file())
        for name in (
            "01_truth_based_summary.png",
            "02_real_motion_summary.png",
            "03_5x_tile_sensitivity.png",
            "04_fixed_real_contact_sheet.png",
            "05_R73_expanded_shapes_fixed_examples.png",
            "05_R74_hard_microscopy_fixed_examples.png",
            "06_sem_paired_exposure18.png",
            "07_R74_acm_contour_overlays.png",
            "08_sem_acm_contour_overlays.png",
        ):
            self.assertTrue((RESULTS / "figures" / name).is_file(), name)


if __name__ == "__main__":
    unittest.main()

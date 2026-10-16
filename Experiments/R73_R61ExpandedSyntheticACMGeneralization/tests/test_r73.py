from __future__ import annotations

import json
import unittest
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "results"
TABLES = RESULTS / "tables"


class R73ValidationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.config = json.loads((ROOT / "config" / "experiment.json").read_text(encoding="utf-8"))
        cls.audit = json.loads((RESULTS / "input_audit.json").read_text(encoding="utf-8"))
        cls.inference = json.loads((RESULTS / "inference_manifest.json").read_text(encoding="utf-8"))
        cls.decision = json.loads((RESULTS / "decision.json").read_text(encoding="utf-8"))
        cls.primary = pd.read_csv(TABLES / "primary_contour_metrics.csv")
        cls.truth_qa = pd.read_csv(TABLES / "truth_acm_geometry_qa.csv")
        cls.sensitivity = pd.read_csv(TABLES / "acm_sensitivity_metrics.csv")
        cls.summary = pd.read_csv(TABLES / "paired_metric_summary.csv")

    def test_frozen_population_and_training_independence(self) -> None:
        self.assertEqual(self.audit["total_images"], 100)
        self.assertEqual(set(self.audit["family_counts"].values()), {20})
        self.assertTrue(self.audit["one_closed_connected_object_per_image"])
        self.assertTrue(self.audit["binary_exact_geometry_masks"])
        self.assertTrue(self.audit["dataset_created_after_checkpoint"])
        self.assertTrue(self.audit["independent_of_r61_training"])
        self.assertEqual(self.audit["training_path_reference_hits"], 0)
        self.assertEqual(self.audit["exact_content_overlap_hashes"], 0)
        self.assertEqual(self.audit["checkpoint_sha256"], self.config["model"]["checkpoint_sha256"])

    def test_all_reconstructions_and_measurements_exist(self) -> None:
        self.assertEqual(self.inference["reconstructed_images"], 100)
        self.assertEqual(len(self.inference["output_dirs"]), 5)
        self.assertEqual(len(self.primary), 400)
        self.assertEqual(len(self.truth_qa), 100)
        self.assertEqual(len(self.sensitivity), 90)
        self.assertTrue(np.isfinite(self.primary.select_dtypes(include=[np.number]).to_numpy()).all())

    def test_clean_image_acm_is_valid_against_exact_geometry(self) -> None:
        threshold = float(self.config["statistics"]["truth_acm_minimum_iou"])
        self.assertGreaterEqual(float(self.truth_qa["iou"].min()), threshold)
        self.assertTrue(self.decision["truth_acm_extraction_gate"]["passed"])
        self.assertEqual(int(self.truth_qa["acm_iterations"].nunique()), 1)
        self.assertEqual(int(self.truth_qa["acm_iterations"].iloc[0]), 100)

    def test_primary_summary_recomputes_from_image_rows(self) -> None:
        primary = self.primary.loc[self.primary["alignment"] == "translation_only"]
        overall = self.summary.loc[(self.summary["alignment"] == "translation_only") & (self.summary["scope"] == "overall")].set_index("metric")
        for metric, direction in (("iou", "higher"), ("mean_boundary_distance_px", "lower")):
            pivot = primary.pivot(index="image_id", columns="method", values=metric)
            delta = pivot["R61v16"] - pivot["Raw"] if direction == "higher" else pivot["Raw"] - pivot["R61v16"]
            self.assertAlmostEqual(float(np.median(delta)), float(overall.loc[metric, "median_improvement"]), places=12)
            self.assertAlmostEqual(float(np.mean(delta > 0)), float(overall.loc[metric, "improved_fraction"]), places=12)

    def test_decision_family_values_match_summary(self) -> None:
        family = self.summary.loc[(self.summary["alignment"] == "translation_only") & (self.summary["scope"] == "family")]
        for name, metrics in self.decision["family_median_improvements"].items():
            for metric, value in metrics.items():
                actual = family.loc[(family["family"] == name) & (family["metric"] == metric), "median_improvement"].iloc[0]
                self.assertAlmostEqual(float(value), float(actual), places=12)

    def test_figures_and_plain_language_report_are_complete(self) -> None:
        chart_map = json.loads((RESULTS / "chart_map.json").read_text(encoding="utf-8"))
        self.assertEqual(len(chart_map), 6)
        for path in chart_map.values():
            figure = Path(path)
            self.assertTrue(figure.is_file())
            self.assertGreater(figure.stat().st_size, 20_000)
        report = ROOT / "reports" / "R73_RESULTS_TW.md"
        self.assertTrue(report.is_file())
        text = report.read_text(encoding="utf-8")
        self.assertIn("100 張", text)
        for label in ("多瓣外形", "深凹口", "細頸連接", "月牙形", "粗糙邊界"):
            self.assertIn(label, text)


if __name__ == "__main__":
    unittest.main()

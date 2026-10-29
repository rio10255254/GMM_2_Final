from __future__ import annotations

import hashlib
import json
import unittest
from collections import Counter
from pathlib import Path

import cv2
import numpy as np
import pandas as pd
PROJECT_ROOT = Path(__file__).resolve().parents[3]


ROOT = Path(__file__).resolve().parents[1]
CONFIG = json.loads((ROOT / "config" / "experiment.json").read_text(encoding="utf-8"))
DATA = Path(PROJECT_ROOT / CONFIG["dataset"]["root"])
RESULTS = ROOT / "results"
TABLES = RESULTS / "tables"


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


class R74ValidationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.manifest = read_json(DATA / "manifest.json")
        cls.audit = read_json(RESULTS / "input_audit.json")
        cls.inference = read_json(RESULTS / "inference_manifest.json")
        cls.difficulty = read_json(TABLES / "raw_difficulty_summary.json")
        cls.decision = read_json(RESULTS / "decision.json")
        cls.primary = pd.read_csv(TABLES / "primary_contour_metrics.csv")
        cls.truth = pd.read_csv(TABLES / "truth_acm_geometry_qa.csv")
        cls.sensitivity = pd.read_csv(TABLES / "acm_sensitivity_metrics.csv")
        cls.summary = pd.read_csv(TABLES / "paired_metric_summary.csv")
        cls.per_image = pd.read_csv(TABLES / "per_image_paired_metrics.csv")
        cls.shapes = pd.read_csv(TABLES / "shape_family_summary.csv")

    def test_01_raw_only_set_was_frozen_before_r61(self) -> None:
        self.assertEqual(self.manifest["difficulty_status"], "frozen_passed_raw_only_gate")
        self.assertTrue(self.difficulty["passed"])
        self.assertFalse(self.difficulty["uses_r61"])
        self.assertFalse(self.manifest["difficulty_calibration_uses_r61"])
        self.assertEqual(self.audit["difficulty_status"], "frozen_passed_raw_only_gate")

    def test_02_frozen_hash_and_balance(self) -> None:
        families = CONFIG["dataset"]["families"]
        names = [f"{index:04d}.bmp" for index in range(20)]
        files = sorted(
            DATA / kind / family["stage"] / name
            for kind in ("src", "lbl", "mask")
            for family in families
            for name in names
        )
        content_hash = hashlib.sha256("".join(sha256(path) for path in files).encode("ascii")).hexdigest()
        self.assertEqual(len(files), 300)
        self.assertEqual(content_hash, self.manifest["frozen_content_sha256"])
        group_shape = Counter((row["family"], row["shape_family"]) for row in self.manifest["records"])
        self.assertEqual(set(group_shape.values()), {4})

    def test_03_training_independence_and_checkpoint(self) -> None:
        self.assertTrue(self.audit["independent_of_r61_training"])
        self.assertEqual(self.audit["training_path_reference_hits"], 0)
        self.assertEqual(self.audit["exact_content_overlap_hashes"], 0)
        self.assertEqual(self.inference["checkpoint_sha256"], CONFIG["model"]["checkpoint_sha256"])
        self.assertEqual(self.inference["reconstructed_images"], 100)

    def test_04_raw_difficulty_gate_is_non_ceiling(self) -> None:
        overall = float(self.difficulty["overall_median_raw_iou"])
        self.assertGreaterEqual(overall, .70)
        self.assertLessEqual(overall, .95)
        family = pd.read_csv(TABLES / "raw_difficulty_family_summary.csv")
        medians = family["median_raw_iou_translation"].to_numpy(float)
        self.assertTrue(np.all(medians < .97))
        self.assertGreaterEqual(int(np.count_nonzero((medians >= .65) & (medians <= .95))), 4)

    def test_05_acm_extraction_quality_and_counts(self) -> None:
        self.assertEqual(len(self.primary), 400)
        self.assertEqual(len(self.truth), 100)
        self.assertEqual(len(self.sensitivity), 90)
        self.assertGreaterEqual(float(self.truth["iou"].min()), .97)
        for frame in (self.primary, self.truth, self.sensitivity):
            numeric = frame.select_dtypes(include=[np.number]).to_numpy(float)
            self.assertTrue(np.isfinite(numeric).all())

    def test_06_primary_summary_recomputes(self) -> None:
        aligned = self.primary.loc[self.primary["alignment"] == "translation_only"]
        pivot_iou = aligned.pivot(index="image_id", columns="method", values="iou")
        pivot_boundary = aligned.pivot(index="image_id", columns="method", values="mean_boundary_distance_px")
        iou_delta = pivot_iou["R61v16"] - pivot_iou["Raw"]
        boundary_delta = pivot_boundary["Raw"] - pivot_boundary["R61v16"]
        overall = self.summary.loc[(self.summary["alignment"] == "translation_only") & (self.summary["scope"] == "overall")].set_index("metric")
        self.assertAlmostEqual(float(overall.loc["iou", "median_improvement"]), float(iou_delta.median()), places=12)
        self.assertAlmostEqual(float(overall.loc["mean_boundary_distance_px", "median_improvement"]), float(boundary_delta.median()), places=12)
        self.assertEqual(int(overall.loc["iou", "improved_count"]), int((iou_delta > 0).sum()))
        self.assertEqual(int(overall.loc["mean_boundary_distance_px", "improved_count"]), int((boundary_delta > 0).sum()))

    def test_07_challenge_and_shape_summaries_are_complete(self) -> None:
        primary = {"iou", "mean_boundary_distance_px"}
        family_rows = self.summary.loc[(self.summary["alignment"] == "translation_only") & (self.summary["scope"] == "family") & self.summary["metric"].isin(primary)]
        shape_rows = self.shapes.loc[self.shapes["metric"].isin(primary)]
        self.assertEqual(len(family_rows), 10)
        self.assertEqual(len(shape_rows), 10)
        self.assertEqual(set(self.per_image["shape_family"]), set(CONFIG["dataset"]["shape_families"]))

    def test_08_decision_matches_gates(self) -> None:
        core = all((
            self.decision["raw_only_difficulty_gate"]["passed"],
            self.decision["truth_acm_extraction_gate"]["passed"],
            self.decision["coarse_overall_gate"],
            self.decision["challenge_consistency_gate"],
            self.decision["shape_consistency_gate"],
            self.decision["sensitivity_gate"],
        ))
        expected = "PASS_HARD_ACM_GENERALIZATION" if core and self.decision["fine_shape_gate"] else (
            "CONDITIONAL_HARD_ACM_PASS" if core else "FAIL_HARD_ACM_GENERALIZATION"
        )
        self.assertEqual(self.decision["verdict"], expected)

    def test_09_visual_and_written_outputs_exist(self) -> None:
        chart_map = read_json(RESULTS / "chart_map.json")
        self.assertEqual(len(chart_map), 7)
        for path in chart_map.values():
            image = cv2.imdecode(np.fromfile(path, dtype=np.uint8), cv2.IMREAD_COLOR)
            self.assertIsNotNone(image)
            self.assertGreater(image.shape[0], 500)
            self.assertGreater(image.shape[1], 700)
        report = ROOT / "reports" / "R74_RESULTS_TW.md"
        self.assertGreater(report.stat().st_size, 1500)
        self.assertIn("R61 困難顯微影像 ACM 泛化測試", report.read_text(encoding="utf-8"))

    def test_10_locked_inference_mode(self) -> None:
        self.assertEqual(self.inference["locked_mode"], {
            "psf_from_checkpoint": False,
            "weak_psf": False,
            "psf_deconv_reg": 30,
            "psf_phys_alpha": 0,
        })


if __name__ == "__main__":
    unittest.main()

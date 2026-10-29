"""Re-analyse the locked R73 ACM extraction as an independent clean-image ceiling."""
from __future__ import annotations

import csv
import json
import os
from collections import defaultdict
from pathlib import Path
from typing import Any

import numpy as np
PROJECT_ROOT = Path(__file__).resolve().parents[3]


ROOT = Path(__file__).resolve().parents[1]
R73_TABLES = Path(
    str(PROJECT_ROOT / 'Experiments/R73_R61ExpandedSyntheticACMGeneralization/results/tables')
)


def rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def summarize(values: list[float]) -> dict[str, float]:
    array = np.asarray(values, np.float64)
    return {
        "count": int(array.size),
        "mean": float(array.mean()),
        "median": float(np.median(array)),
        "p05": float(np.percentile(array, 5)),
        "p95": float(np.percentile(array, 95)),
    }


def metric_summary(
    pairs: list[tuple[dict[str, str], dict[str, str]]], name: str, *, higher_is_better: bool
) -> dict[str, Any]:
    raw = np.asarray([float(pair[0][name]) for pair in pairs], np.float64)
    clean = np.asarray([float(pair[1][name]) for pair in pairs], np.float64)
    signed_improvement = clean - raw if higher_is_better else raw - clean
    return {
        "higher_is_better": higher_is_better,
        "raw": summarize(raw.tolist()),
        "clean_truth_image": summarize(clean.tolist()),
        "signed_improvement": summarize(signed_improvement.tolist()),
        "improved_fraction": float(np.mean(signed_improvement > 1e-12)),
        "unchanged_fraction": float(np.mean(np.abs(signed_improvement) <= 1e-12)),
        "worsened_fraction": float(np.mean(signed_improvement < -1e-12)),
    }


def main() -> int:
    primary = rows(R73_TABLES / "primary_contour_metrics.csv")
    truth = rows(R73_TABLES / "truth_acm_geometry_qa.csv")
    raw_lookup = {
        row["image_id"]: row
        for row in primary
        if row["method"] == "Raw" and row["alignment"] == "translation_only"
    }
    truth_lookup = {row["image_id"]: row for row in truth}
    image_ids = sorted(set(raw_lookup) & set(truth_lookup))
    if len(image_ids) != 100:
        raise RuntimeError(f"Expected 100 locked pairs, found {len(image_ids)}")
    pairs = [(raw_lookup[image_id], truth_lookup[image_id]) for image_id in image_ids]
    metrics = {
        "iou": True,
        "mean_boundary_distance_px": False,
        "hd95_px": False,
        "area_error_pct": False,
        "perimeter_error_pct": False,
        "solidity_abs_error": False,
        "roughness_abs_error": False,
    }
    global_summary = {
        name: metric_summary(pairs, name, higher_is_better=higher)
        for name, higher in metrics.items()
    }
    grouped: dict[str, list[tuple[dict[str, str], dict[str, str]]]] = defaultdict(list)
    for pair in pairs:
        grouped[pair[0]["family"]].append(pair)
    family_summary = {
        family: {
            name: metric_summary(family_pairs, name, higher_is_better=higher)
            for name, higher in metrics.items()
        }
        for family, family_pairs in sorted(grouped.items())
    }
    truth_iou = np.asarray([float(pair[1]["iou"]) for pair in pairs], np.float64)
    report = {
        "analysis_id": "R95_LOCKED_R73_ACM_CLEAN_CEILING_V1",
        "meaning": (
            "Independent downstream check using the already frozen R73 Chan-Vese ACM settings. "
            "It compares ACM on Raw versus the procedural clean image against the exact generator mask. "
            "It validates the usefulness of a clean reconstruction target, not untrained R95 performance."
        ),
        "source_experiment": str(R73_TABLES.parent.parent),
        "locked_method": {
            "implementation": "MATLAB activecontour Chan-Vese",
            "iterations": 100,
            "smooth_factor": 1.0,
            "initialization_uses_truth_shape": False,
            "raw_alignment": "translation_only",
            "clean_alignment": "fixed_pixel_coordinates",
            "scale_fitting": False,
            "rotation_fitting": False,
        },
        "paired_images": len(pairs),
        "families": sorted(grouped),
        "truth_extraction_qa": {
            "iou": summarize(truth_iou.tolist()),
            "fraction_iou_at_least_0_97": float(np.mean(truth_iou >= 0.97)),
        },
        "global": global_summary,
        "by_family": family_summary,
        "conclusion": {
            "clean_ceiling_improves_iou": global_summary["iou"]["signed_improvement"]["median"] > 0.0,
            "clean_ceiling_improves_mean_boundary_distance": (
                global_summary["mean_boundary_distance_px"]["signed_improvement"]["median"] > 0.0
            ),
            "all_families_positive_median_iou": all(
                family_summary[family]["iou"]["signed_improvement"]["median"] > 0.0
                for family in family_summary
            ),
            "all_families_positive_median_boundary_distance": all(
                family_summary[family]["mean_boundary_distance_px"]["signed_improvement"]["median"] > 0.0
                for family in family_summary
            ),
        },
    }
    output = ROOT / "reports" / "locked_acm_clean_ceiling.json"
    temporary = output.with_suffix(output.suffix + ".tmp")
    temporary.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    os.replace(temporary, output)
    print(json.dumps({
        "paired_images": report["paired_images"],
        "truth_extraction_qa": report["truth_extraction_qa"],
        "iou": report["global"]["iou"],
        "mean_boundary_distance_px": report["global"]["mean_boundary_distance_px"],
        "by_family": {
            family: {
                "iou_median_improvement": values["iou"]["signed_improvement"]["median"],
                "boundary_distance_median_improvement_px": values["mean_boundary_distance_px"]["signed_improvement"]["median"],
            }
            for family, values in report["by_family"].items()
        },
        "conclusion": report["conclusion"],
    }, indent=2, ensure_ascii=False))
    return 0 if all(report["conclusion"].values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())


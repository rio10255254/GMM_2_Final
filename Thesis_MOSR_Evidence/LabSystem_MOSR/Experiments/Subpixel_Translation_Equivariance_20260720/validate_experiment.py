from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

import cv2
import numpy as np
import pandas as pd
PROJECT_ROOT = Path(__file__).resolve().parents[4]


EXPERIMENT = Path(__file__).resolve().parent
TABLES = EXPERIMENT / "analysis" / "tables"
QA = EXPERIMENT / "qa"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def assert_close(actual: float, expected: float, tolerance: float, label: str) -> None:
    if not np.isfinite(actual) or abs(actual - expected) > tolerance:
        raise RuntimeError(f"{label}: actual={actual}, expected={expected}")


def main() -> None:
    design_path = EXPERIMENT / "predeclared_design.json"
    input_meta = json.loads(
        (EXPERIMENT / "inputs" / "input_manifest.json").read_text(encoding="utf-8")
    )
    with (EXPERIMENT / "inputs" / "input_manifest.csv").open(
        "r", encoding="utf-8-sig", newline=""
    ) as handle:
        inputs = list(csv.DictReader(handle))
    output_map = {
        key: Path(PROJECT_ROOT / value)
        for key, value in json.loads(
            (EXPERIMENT / "results" / "method_outputs.json").read_text(encoding="utf-8")
        ).items()
    }
    cluster = pd.read_csv(TABLES / "cluster_translation_metrics.csv")
    summary = pd.read_csv(TABLES / "primary_translation_summary_by_method.csv")
    circular = pd.read_csv(TABLES / "circular_feature_measurements.csv")
    lines = pd.read_csv(TABLES / "line_edge_measurements.csv")

    checks: dict[str, object] = {}
    checks["predeclared_design_hash_matches"] = (
        sha256_file(design_path) == input_meta["design_sha256"]
    )
    checks["input_count_is_126"] = len(inputs) == 126
    expected_names = {row["filename"] for row in inputs}
    checks["all_methods_have_exact_filenames"] = True
    checks["all_method_images_are_uint16_512"] = True
    method_image_checks = {}
    for method, directory in output_map.items():
        actual_names = {path.name for path in directory.glob("*.png")}
        filename_match = actual_names == expected_names
        dtype_match = True
        for name in expected_names:
            image = cv2.imread(str(directory / name), cv2.IMREAD_UNCHANGED)
            if image is None or image.dtype != np.uint16 or image.shape != (512, 512):
                dtype_match = False
                break
        method_image_checks[method] = {
            "count": len(actual_names),
            "filename_match": filename_match,
            "uint16_512": dtype_match,
        }
        checks["all_methods_have_exact_filenames"] &= filename_match
        checks["all_method_images_are_uint16_512"] &= dtype_match
    checks["method_images"] = method_image_checks

    primary = cluster.loc[cluster.primary_endpoint & cluster.valid].copy()
    methods = ["raw", "base_unet", "edsr", "nafnet", "mosr"]
    expected_cluster_ids = None
    checks["primary_cluster_counts"] = {}
    checks["paired_cluster_ids_match"] = True
    checks["reported_summaries_recompute"] = True
    recomputed = {}
    for method in methods:
        subset = primary.loc[primary.method_key == method].copy()
        cluster_ids = set(subset.cluster_id)
        if expected_cluster_ids is None:
            expected_cluster_ids = cluster_ids
        else:
            checks["paired_cluster_ids_match"] &= cluster_ids == expected_cluster_ids
        checks["primary_cluster_counts"][method] = len(subset)
        reported = summary.loc[summary.method_key == method].iloc[0]
        values = subset.absolute_error_px.to_numpy(float)
        local = {
            "median_absolute_error_px": float(np.median(values)),
            "p95_absolute_error_px": float(np.percentile(values, 95.0)),
            "mean_absolute_error_px": float(np.mean(values)),
            "rmse_px": float(np.sqrt(np.mean(subset.signed_error_px.to_numpy(float) ** 2))),
        }
        recomputed[method] = local
        for key, value in local.items():
            try:
                assert_close(value, float(reported[key]), 1e-12, f"{method}.{key}")
            except RuntimeError:
                checks["reported_summaries_recompute"] = False
                raise

    checks["recomputed_primary_summary"] = recomputed
    checks["each_method_has_100_primary_clusters"] = all(
        count == 100 for count in checks["primary_cluster_counts"].values()
    )
    checks["physical_unit_conversion_matches"] = bool(
        np.allclose(
            primary.absolute_error_nm.to_numpy(float),
            primary.absolute_error_px.to_numpy(float)
            * primary.scale_nm_per_px.to_numpy(float),
            rtol=0.0,
            atol=1e-10,
        )
    )

    raw_integer = primary.loc[
        (primary.method_key == "raw") & np.isclose(primary.shift_magnitude_px, 1.0)
    ]
    checks["raw_integer_shift_sanity"] = {
        "cluster_count": len(raw_integer),
        "maximum_absolute_error_px": float(raw_integer.absolute_error_px.max()),
        "passed": bool(float(raw_integer.absolute_error_px.max()) <= 1e-12),
    }

    # Independently reproduce one circular and one line cluster directly from
    # their feature-level tables.
    circular_target = cluster.loc[
        (cluster.method_key == "mosr")
        & (cluster.case_id == "50x_pillar")
        & (cluster.axis == "x")
        & np.isclose(cluster.shift_px, 0.25)
    ].iloc[0]
    circular_features = circular.loc[
        (circular.method_key == "mosr")
        & (circular.case_id == "50x_pillar")
        & (circular.axis == "x")
        & np.isclose(circular.shift_px, 0.25)
        & circular.valid
    ]
    circular_estimate = float(np.median(circular_features.along_axis_shift_px))
    assert_close(
        circular_estimate,
        float(circular_target.measured_shift_px),
        1e-12,
        "circular cluster aggregation",
    )

    line_target = cluster.loc[
        (cluster.method_key == "edsr")
        & (cluster.case_id == "50x_vertical_lines")
        & (cluster.axis == "x")
        & np.isclose(cluster.shift_px, -0.50)
    ].iloc[0]
    line_features = lines.loc[
        (lines.method_key == "edsr")
        & (lines.case_id == "50x_vertical_lines")
        & (lines.command_axis == "x")
        & np.isclose(lines.shift_px, -0.50)
        & lines.valid
    ]
    line_estimate = float(np.median(line_features.measured_shift_px))
    assert_close(
        line_estimate,
        float(line_target.measured_shift_px),
        1e-12,
        "line cluster aggregation",
    )
    checks["feature_to_cluster_aggregation_matches"] = True

    prior_qa_files = [
        QA / "inference_output_qa.json",
        QA / "analysis_qa.json",
    ]
    checks["prior_qa_passed"] = all(
        json.loads(path.read_text(encoding="utf-8"))["passed"] for path in prior_qa_files
    )
    boolean_checks = [
        value
        for key, value in checks.items()
        if isinstance(value, bool) and key != "passed"
    ]
    nested_passes = [checks["raw_integer_shift_sanity"]["passed"]]
    checks["passed"] = bool(all(boolean_checks) and all(nested_passes))
    output = QA / "independent_validation.json"
    output.write_text(json.dumps(checks, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(checks, ensure_ascii=False, indent=2))
    if not checks["passed"]:
        raise RuntimeError("Independent validation failed")


if __name__ == "__main__":
    main()

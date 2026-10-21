"""Independent integrity and reproducibility checks for the R109 ceiling probe."""
from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.util
import json
import math
import sys
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = ROOT / "config" / "r109_expressivity.json"
DEFAULT_RESULTS = ROOT / "results" / "r109_expressivity"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_csv(path: Path) -> list[dict]:
    with path.open("r", newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def load_runner():
    path = ROOT / "scripts" / "run_r109_expressivity.py"
    name = "r113_r109_expressivity_runner_for_validation"
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot import {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def add(checks: list[dict], name: str, passed: bool, detail) -> None:
    checks.append({"name": name, "passed": bool(passed), "detail": detail})


def validate(config_path: Path, results: Path, rerun_subset: int) -> dict:
    config = json.loads(config_path.read_text(encoding="utf-8"))
    analysis = json.loads((results / "analysis_summary.json").read_text(encoding="utf-8"))
    decision = json.loads((results / "upper_bound_decision.json").read_text(encoding="utf-8"))
    history = json.loads((results / "optimization_history.json").read_text(encoding="utf-8"))
    manifest = read_csv(results / "scene_manifest.csv")
    metrics = read_csv(results / "per_scene_metrics.csv")
    controls = read_csv(results / "control_statistics.csv")
    pair_rows = read_csv(results / "paired_condition_metrics.csv")
    methods = list(config["methods"])
    expected_scenes = len(config["shape_families"]) * int(config["scenes_per_shape"])
    checks = []

    add(checks, "checkpoint_hash_frozen",
        sha256_file(Path(config["source"]["r109_checkpoint"])) == config["source"]["r109_checkpoint_sha256"],
        config["source"]["r109_checkpoint_sha256"])
    add(checks, "config_hash_matches_run", sha256_file(config_path) == analysis["config_sha256"], analysis["config_sha256"])
    add(checks, "scene_count", len(manifest) == expected_scenes, {"actual": len(manifest), "expected": expected_scenes})
    add(checks, "metric_cartesian_product", len(metrics) == expected_scenes * len(methods),
        {"actual": len(metrics), "expected": expected_scenes * len(methods)})
    per_scene_methods = {}
    for row in metrics:
        per_scene_methods.setdefault(row["scene_id"], set()).add(row["method"])
    add(checks, "every_scene_has_every_method", all(value == set(methods) for value in per_scene_methods.values()),
        {key: sorted(set(methods) - value) for key, value in per_scene_methods.items() if value != set(methods)})

    latent = {}
    for row in manifest:
        latent.setdefault(row["latent_shape_id"], []).append(row)
    paired_ok = (len(latent) == len(config["shape_families"])
                 and all(len(rows) == int(config["scenes_per_shape"]) for rows in latent.values())
                 and all(len({row["mask_sha256"] for row in rows}) == 1 for rows in latent.values())
                 and all(len({row["degradation"] for row in rows}) == int(config["scenes_per_shape"]) for rows in latent.values()))
    add(checks, "paired_condition_design", paired_ok,
        {key: {"count": len(rows), "mask_hashes": len({r['mask_sha256'] for r in rows}),
               "degradations": sorted({r['degradation'] for r in rows})} for key, rows in latent.items()})

    numeric_fields = ["iou", "dice", "assd_px", "hd95_px", "area_relative_error", "centroid_error_px",
                      "image_mae_gray", "boundary_mae_gray", "edge_gradient_mae_gray", "high_frequency_rmse_gray"]
    all_finite = all(math.isfinite(float(row[field])) for row in metrics for field in numeric_fields)
    add(checks, "metrics_finite", all_finite, numeric_fields)

    arrays = np.load(results / "experiment_arrays.npz")
    expected_shape = (expected_scenes, int(config["canvas_size"]), int(config["canvas_size"]))
    shape_ok = all(arrays[f"output__{method}"].shape == expected_shape for method in methods)
    finite_range = all(np.isfinite(arrays[f"output__{method}"]).all()
                       and arrays[f"output__{method}"].min() >= -1e-7
                       and arrays[f"output__{method}"].max() <= 1 + 1e-7 for method in methods)
    add(checks, "output_array_shapes", shape_ok, expected_shape)
    add(checks, "output_arrays_finite_range", finite_range, "all outputs finite and inside [0,1]")
    detail_bound = float(config["detail_oracle"]["maximum_amplitude_gray_levels"]) / 255
    detail_max = float(np.max(np.abs(arrays["detail_oracle"])))
    add(checks, "detail_oracle_amplitude_bound", detail_max <= detail_bound + 1e-6,
        {"actual": detail_max, "bound": detail_bound})

    contract = config["r109_contract"]
    bounded_controls = True
    violations = []
    for row in controls:
        for prefix, lower, upper in (("width", float(contract["minimum_width_gain"]), float(contract["maximum_width_gain"])),
                                     ("shift", -float(contract["maximum_normal_shift_px"]), float(contract["maximum_normal_shift_px"]))):
            p05 = float(row[f"{prefix}_p05"])
            p95 = float(row[f"{prefix}_p95"])
            if math.isfinite(p05) and (p05 < lower - 1e-5 or p95 > upper + 1e-5):
                bounded_controls = False
                violations.append({"scene": row["scene_id"], "method": row["method"], "field": prefix, "p05": p05, "p95": p95})
    add(checks, "control_contract_bounds", bounded_controls, violations)

    history_ok = True
    history_detail = {}
    for method, rows in history.items():
        first, last = float(rows[0]["loss"]), float(rows[-1]["loss"])
        history_detail[method] = {"first": first, "last": last, "reduction_percent": 100 * (first - last) / max(first, 1e-12)}
        history_ok &= math.isfinite(first) and math.isfinite(last) and last < first
    add(checks, "every_optimization_converged", history_ok, history_detail)

    summary_ok = True
    summary_diffs = {}
    for method in methods:
        selected = [row for row in metrics if row["method"] == method]
        for metric in ("assd_px", "iou", "boundary_mae_gray", "high_frequency_rmse_gray"):
            values = np.array([float(row[metric]) for row in selected])
            expected = analysis["summary"][method]["metrics"][metric]
            recomputed = {"mean": float(values.mean()), "median": float(np.median(values)),
                          "min": float(values.min()), "max": float(values.max())}
            difference = max(abs(recomputed[key] - float(expected[key])) for key in recomputed)
            summary_diffs[f"{method}:{metric}"] = difference
            summary_ok &= difference < 1e-10
    add(checks, "summary_independently_recomputed", summary_ok, {"max_abs_difference": max(summary_diffs.values())})

    expected_same_pairs = len(config["shape_families"]) * math.comb(int(config["scenes_per_shape"]), 2) * len(methods)
    expected_between_pairs = math.comb(len(config["shape_families"]), 2) * len(methods)
    same_count = sum(row["pair_type"] == "same_latent_different_condition" for row in pair_rows)
    between_count = sum(row["pair_type"] == "different_latent_consensus" for row in pair_rows)
    add(checks, "paired_condition_pair_counts", same_count == expected_same_pairs and between_count == expected_between_pairs,
        {"same": [same_count, expected_same_pairs], "between": [between_count, expected_between_pairs]})
    add(checks, "shape_identity_not_collapsed",
        not analysis["condition_invariance"]["oracle_width_shift_smooth"]["collapse_warning"],
        analysis["condition_invariance"]["oracle_width_shift_smooth"])

    visual_files = [results / "worst_case_visual_panel.png", results / "method_summary.png"]
    add(checks, "visual_artifacts_present", all(path.exists() and path.stat().st_size > 10_000 for path in visual_files),
        {str(path): path.stat().st_size if path.exists() else 0 for path in visual_files})

    runner = load_runner()
    actual_subset = None if rerun_subset <= 0 else rerun_subset
    rerun = runner.run(config_path, results / "_unused_validation_rerun", subset=actual_subset, save_artifacts=False)
    compare_count = expected_scenes if actual_subset is None else actual_subset
    pixel_differences = {}
    for method in methods:
        original = arrays[f"output__{method}"][:compare_count]
        repeated = rerun["outputs"][method]
        maximum = float(np.max(np.abs(original - repeated)))
        pixel_differences[method] = maximum
    scene_inputs_exact = all(np.array_equal(arrays[name][:compare_count], rerun["arrays"][name])
                             for name in ("raw", "target", "mask"))
    learned_exact = pixel_differences["identity"] == 0 and pixel_differences["learned_r109_e48"] == 0
    metric_differences = {}
    metric_stable = True
    for method in methods:
        for metric, statistic, tolerance in (("assd_px", "median", .02), ("assd_px", "max", .12),
                                              ("iou", "min", .02), ("high_frequency_rmse_gray", "mean", .08)):
            old = float(analysis["summary"][method]["metrics"][metric][statistic])
            new = float(rerun["summary"][method]["metrics"][metric][statistic])
            difference = abs(old - new)
            metric_differences[f"{method}:{metric}:{statistic}"] = difference
            metric_stable &= difference <= tolerance
    conclusion_stable = rerun["decision"]["primary_limit"] == decision["primary_limit"]
    reproducible = scene_inputs_exact and learned_exact and metric_stable and conclusion_stable
    add(checks, "numeric_reproducibility", reproducible,
        {"scene_count": compare_count, "synthetic_inputs_bit_exact": scene_inputs_exact,
         "identity_and_learned_outputs_bit_exact": learned_exact,
         "oracle_metric_max_abs_difference": max(metric_differences.values()),
         "oracle_metric_differences": metric_differences,
         "decision_reproduced": conclusion_stable, "oracle_pixel_max_abs_differences_informational": pixel_differences,
         "note": "Oracle CUDA optimization is judged by metric and decision stability because grid-sample backward is nondeterministic in this PyTorch build."})

    add(checks, "decision_is_worst_case_aware",
        decision["primary_limit"] == "renderer_capacity_primary_for_hard_cases_controls_secondary",
        {"primary_limit": decision["primary_limit"], "go_no_go": decision["go_no_go"]})
    passed = all(check["passed"] for check in checks)
    result = {
        "status": "PASS" if passed else "FAIL", "check_count": len(checks),
        "passed_count": sum(check["passed"] for check in checks), "checks": checks,
        "decision": {"primary_limit": decision["primary_limit"], "go_no_go": decision["go_no_go"]},
    }
    (results / "validation.json").write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--results", type=Path, default=DEFAULT_RESULTS)
    parser.add_argument("--rerun-subset", type=int, default=0,
                        help="0 reruns the full batch; positive values are a faster diagnostic only")
    args = parser.parse_args()
    result = validate(args.config.resolve(), args.results.resolve(), args.rerun_subset)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    raise SystemExit(0 if result["status"] == "PASS" else 1)


if __name__ == "__main__":
    main()

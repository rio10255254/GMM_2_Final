"""Validate scaffold and the latest two-arm smoke capability run."""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
PROJECT_ROOT = Path(__file__).resolve().parents[4]


ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "config" / "experiment.json"
CONFIG = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def add(checks, name, passed, detail):
    checks.append({"name": name, "passed": bool(passed), "detail": detail})


def main() -> int:
    checks = []
    selection_path = ROOT / CONFIG["data"]["selection_file"]
    selection = json.loads(selection_path.read_text(encoding="utf-8"))
    source_manifest = Path(PROJECT_ROOT / CONFIG["data"]["package_root"]) / "manifest.json"
    add(checks, "source_manifest_frozen",
        sha256_file(source_manifest).lower() == CONFIG["data"]["source_manifest_sha256"].lower(),
        sha256_file(source_manifest))
    canonical = json.dumps(selection["records"], sort_keys=True, separators=(",", ":")).encode("utf-8")
    add(checks, "selection_records_hash", hashlib.sha256(canonical).hexdigest() == selection["records_sha256"],
        selection["records_sha256"])
    file_hash_ok = True; failures = []; package = Path(PROJECT_ROOT / CONFIG["data"]["package_root"])
    for row in selection["records"]:
        for field, expected in row["source_file_hashes"].items():
            actual = sha256_file(package / row[field])
            if actual != expected:
                file_hash_ok = False; failures.append({"scene_id": row["scene_id"], "field": field})
    add(checks, "selected_source_arrays_frozen", file_hash_ok, failures)
    add(checks, "formal_training_still_blocked", CONFIG["formal_training_authorized"] is False,
        CONFIG["formal_training_authorized"])

    registry_path = ROOT / "runs" / "latest_smoke_registry.json"
    registry = json.loads(registry_path.read_text(encoding="utf-8"))
    states = {}
    for item in registry["runs"]:
        state = json.loads(Path(item["run_state"]).read_text(encoding="utf-8")); states[item["arm"]] = state
    add(checks, "both_smoke_arms_complete", set(states) == set(CONFIG["reference_arms"])
        and all(state["status"] == "complete" and state["mode"] == "smoke" for state in states.values()), states)
    baseline = states["width_shift"]; detail = states["bounded_detail"]
    add(checks, "matched_initial_state", baseline["initial_state_sha256"] == detail["initial_state_sha256"],
        {arm: state["initial_state_sha256"] for arm, state in states.items()})
    add(checks, "matched_parameter_count", baseline["parameters"] == detail["parameters"],
        {arm: state["parameters"] for arm, state in states.items()})
    add(checks, "matched_post_detector_state", baseline["post_detector_state_sha256"] == detail["post_detector_state_sha256"],
        {arm: state["post_detector_state_sha256"] for arm, state in states.items()})
    add(checks, "matched_optimizer_steps", baseline["global_step"] == detail["global_step"],
        {arm: state["global_step"] for arm, state in states.items()})
    add(checks, "gpu_headroom_preserved",
        all(state["estimated_minimum_free_gib"] >= CONFIG["training"]["minimum_gpu_free_before_start_gib"] for state in states.values()),
        {arm: {"estimated_minimum_free_gib": state["estimated_minimum_free_gib"],
               "peak_reserved_gib": state["gpu_peak_reserved_gib"]} for arm, state in states.items()})

    bound = float(CONFIG["model"]["detail"]["maximum_amplitude_gray_levels"])
    baseline_detail = baseline["locked_challenge"]["detail_abs_mean_gray"]
    extension_detail = detail["locked_challenge"]["detail_abs_mean_gray"]
    extension_dc = detail["locked_challenge"]["detail_local_mean_gray"]
    add(checks, "baseline_detail_disabled", baseline_detail == 0.0, baseline_detail)
    add(checks, "extension_detail_learns_nonzero", extension_detail > 0.0, extension_detail)
    add(checks, "extension_detail_local_mean_suppressed", extension_dc < extension_detail,
        {"detail_abs_mean_gray": extension_detail, "local_mean_gray": extension_dc})
    add(checks, "extension_detail_below_absolute_bound", extension_detail < bound, {"mean": extension_detail, "bound": bound})
    metric_names = ["assd_median_px", "assd_p95_px", "assd_worst_px", "iou_mean", "iou_worst",
                    "boundary_mae_mean_gray", "high_frequency_rmse_mean_gray", "same_shape_condition_assd_mean_px",
                    "shape_retention_ratio", "shape_distance_spearman"]
    finite_metrics = all(math.isfinite(float(state["locked_challenge"][metric])) for state in states.values() for metric in metric_names)
    add(checks, "locked_physical_metrics_finite", finite_metrics, metric_names)

    deltas = {metric: float(detail["locked_challenge"][metric]) - float(baseline["locked_challenge"][metric])
              for metric in metric_names}
    comparison = {
        "status": "smoke_capability_only", "scientific_decision_allowed": False,
        "reason": "Three smoke epochs with two batches each only verify plumbing and matched control; they cannot rank renderers.",
        "baseline": baseline["locked_challenge"], "bounded_detail": detail["locked_challenge"],
        "bounded_detail_minus_width_shift": deltas,
        "formal_training_started": False,
    }
    output_root = ROOT / "results"; output_root.mkdir(parents=True, exist_ok=True)
    (output_root / "smoke_comparison.json").write_text(json.dumps(comparison, indent=2, ensure_ascii=False), encoding="utf-8")
    passed = all(check["passed"] for check in checks)
    validation = {"status": "PASS" if passed else "FAIL", "checks": checks,
                  "formal_training_started": False, "scientific_decision_allowed": False}
    (output_root / "validation.json").write_text(json.dumps(validation, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(validation, indent=2, ensure_ascii=False))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())

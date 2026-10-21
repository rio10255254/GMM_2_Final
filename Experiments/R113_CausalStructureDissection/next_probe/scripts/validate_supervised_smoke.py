"""Capability/readiness checks for the final supervised scratch arm."""
from __future__ import annotations

import json
import math
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CONFIG = json.loads((ROOT / "config" / "experiment.json").read_text(encoding="utf-8"))


def add(checks, name, passed, detail):
    checks.append({"name": name, "passed": bool(passed), "detail": detail})


def main() -> int:
    checks = []
    registry = json.loads((ROOT / "runs" / "latest_supervised_smoke_registry.json").read_text(encoding="utf-8"))
    add(checks, "single_supervised_smoke_arm", len(registry["runs"]) == 1
        and registry["runs"][0]["arm"] == "bounded_detail_supervised", registry)
    run_dir = Path(registry["runs"][0]["run_dir"])
    state = json.loads((run_dir / "run_state.json").read_text(encoding="utf-8"))
    history = json.loads((run_dir / "training_history.json").read_text(encoding="utf-8"))
    reference_smoke = json.loads((ROOT / "runs" / "smoke_capability_bounded_detail" / "run_state.json").read_text(encoding="utf-8"))
    formal = json.loads((ROOT / "results" / "formal_comparison.json").read_text(encoding="utf-8"))
    capability = json.loads((ROOT / "results" / "supervision_learning_capability.json").read_text(encoding="utf-8"))
    add(checks, "smoke_complete_scratch", state["status"] == "complete" and state["mode"] == "smoke"
        and state["scratch"] and state["global_step"] == 6, state)
    add(checks, "same_initial_state_as_matched_formal",
        state["initial_state_sha256"] == formal["arms"]["width_shift"]["initial_state_sha256"],
        {"supervised": state["initial_state_sha256"], "formal_reference": formal["arms"]["width_shift"]["initial_state_sha256"]})
    add(checks, "same_smoke_detector_state",
        state["post_detector_state_sha256"] == reference_smoke["post_detector_state_sha256"],
        {"supervised": state["post_detector_state_sha256"], "reference": reference_smoke["post_detector_state_sha256"]})
    add(checks, "same_parameter_count", state["parameters"] == reference_smoke["parameters"],
        {"supervised": state["parameters"], "reference": reference_smoke["parameters"]})
    add(checks, "smoke_did_not_start_formal", registry["mode"] == "smoke"
        and registry["formal_confirmed"] is False and state["mode"] == "smoke",
        {"config_authorized": CONFIG["formal_training_authorized"], "registry_mode": registry["mode"],
         "formal_confirmed": registry["formal_confirmed"]})
    add(checks, "learning_signal_capability_passed", capability["status"] == "PASS"
        and capability["formal_training"] is False, capability)
    add(checks, "gpu_headroom", state["estimated_minimum_free_gib"] >= CONFIG["training"]["minimum_gpu_free_before_start_gib"],
        {"estimated_minimum_free_gib": state["estimated_minimum_free_gib"], "peak_reserved_gib": state["gpu_peak_reserved_gib"]})

    renderer_rows = [row for row in history if row["stage"] == "renderer"]
    expected_weights = CONFIG["training"]["bounded_detail_supervision"]["renderer_epoch_weights"][:len(renderer_rows)]
    actual_weights = [row["train_detail_supervision_weight"] for row in renderer_rows]
    add(checks, "staged_supervision_active", actual_weights == expected_weights,
        {"actual": actual_weights, "expected": expected_weights})
    add(checks, "supervision_losses_finite",
        all(math.isfinite(row["train_detail_supervision"]) and row["train_detail_supervision"] > 0
            and math.isfinite(row["train_detail_carrier_supervision"])
            and row["train_detail_carrier_supervision"] > 0 for row in renderer_rows),
        [{"projected": row["train_detail_supervision"], "carrier": row["train_detail_carrier_supervision"]}
         for row in renderer_rows])
    locked = state["locked_challenge"]
    add(checks, "target_and_prediction_nonzero",
        locked["detail_target_abs_mean_gray"] > 0 and locked["detail_abs_mean_gray"] > 0,
        {"target_gray": locked["detail_target_abs_mean_gray"], "prediction_gray": locked["detail_abs_mean_gray"],
         "utilization": locked["detail_target_utilization_ratio"]})
    add(checks, "detail_remains_bounded", locked["detail_abs_mean_gray"] < 18.0,
        locked["detail_abs_mean_gray"])
    add(checks, "local_mean_suppressed", locked["detail_local_mean_gray"] < locked["detail_abs_mean_gray"],
        {"local_mean": locked["detail_local_mean_gray"], "detail": locked["detail_abs_mean_gray"]})
    final_row = history[-1]
    add(checks, "identity_detail_small_in_smoke",
        final_row["validation_detail_identity"] * 255 < .05,
        final_row["validation_detail_identity"] * 255)
    metric_names = ("assd_median_px", "assd_p95_px", "assd_worst_px", "iou_mean", "iou_worst",
                    "boundary_mae_mean_gray", "high_frequency_rmse_mean_gray", "same_shape_condition_assd_mean_px",
                    "shape_retention_ratio", "shape_distance_spearman", "detail_supervision_mae_gray")
    add(checks, "all_locked_metrics_finite", all(math.isfinite(float(locked[name])) for name in metric_names),
        {name: locked[name] for name in metric_names})
    passed = all(check["passed"] for check in checks)
    result = {
        "status": "PASS" if passed else "FAIL", "checks": checks,
        "ready_for_formal_when_explicitly_authorized": passed,
        "formal_training_started_by_this_smoke_task": False,
        "formal_training_managed_separately_by_parent_task": True,
        "scientific_decision_allowed_from_smoke": False,
        "formal_training_authorized_in_current_config": CONFIG["formal_training_authorized"],
        "formal_reference": str(ROOT / "results" / "formal_comparison.json"),
        "supervised_smoke_run": str(run_dir),
    }
    (ROOT / "results" / "supervised_smoke_readiness.json").write_text(
        json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())

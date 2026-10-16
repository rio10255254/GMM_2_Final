"""Compare the directly supervised detail arm with both matched formal references."""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "results"
REFERENCE_REGISTRY = ROOT / "runs" / "latest_formal_registry.json"
SUPERVISED_REGISTRY = ROOT / "runs" / "latest_supervised_formal_registry.json"


def load_registry(path: Path) -> tuple[dict[str, dict], dict[str, pd.DataFrame], dict[str, Path]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    states, metrics, roots = {}, {}, {}
    for item in payload["runs"]:
        arm = item["arm"]
        run_dir = Path(item["run_dir"])
        roots[arm] = run_dir
        states[arm] = json.loads((run_dir / "run_state.json").read_text(encoding="utf-8"))
        metrics[arm] = pd.read_csv(run_dir / "locked_challenge_metrics.csv", encoding="utf-8-sig")
    return states, metrics, roots


def compare(left: pd.DataFrame, right: pd.DataFrame, label: str) -> dict[str, object]:
    joined = left.merge(right, on="scene_id", suffixes=("_left", "_right"), validate="one_to_one")
    metrics = {"assd_px": "lower", "iou": "higher", "boundary_mae_gray": "lower", "high_frequency_rmse_gray": "lower"}
    rng = np.random.default_rng(113999 + sum(ord(value) for value in label))
    indices = rng.integers(0, len(joined), size=(20_000, len(joined)))
    result = {}
    for metric, direction in metrics.items():
        difference = joined[f"{metric}_right"].to_numpy(float) - joined[f"{metric}_left"].to_numpy(float)
        sampled = np.median(difference[indices], axis=1)
        low, high = np.percentile(sampled, [2.5, 97.5])
        improved = difference < 0 if direction == "lower" else difference > 0
        result[metric] = {
            "direction": direction,
            "median_right_minus_left": float(np.median(difference)),
            "mean_right_minus_left": float(np.mean(difference)),
            "ci95_of_paired_median": [float(low), float(high)],
            "improved_scenes": int(improved.sum()),
            "scenes": len(difference),
        }
    return {"comparison": label, "paired_scenes": len(joined), "metrics": result}


def main() -> int:
    if not SUPERVISED_REGISTRY.is_file():
        raise RuntimeError("Supervised formal registry missing")
    reference_states, reference_metrics, _ = load_registry(REFERENCE_REGISTRY)
    supervised_states, supervised_metrics, supervised_roots = load_registry(SUPERVISED_REGISTRY)
    failures = []
    if set(supervised_states) != {"bounded_detail_supervised"}:
        failures.append(f"unexpected supervised arms: {sorted(supervised_states)}")
    supervised = supervised_states["bounded_detail_supervised"]
    baseline = reference_states["width_shift"]
    unsupervised = reference_states["bounded_detail"]
    if supervised.get("status") != "complete" or supervised.get("epochs_completed") != 8 or supervised.get("global_step") != 1360:
        failures.append("supervised formal run is incomplete")
    for name, reference in (("baseline", baseline), ("unsupervised", unsupervised)):
        if supervised["initial_state_sha256"] != reference["initial_state_sha256"]:
            failures.append(f"initial state differs from {name}")
        if supervised["post_detector_state_sha256"] != reference["post_detector_state_sha256"]:
            failures.append(f"post-detector state differs from {name}")
        if supervised["parameters"] != reference["parameters"] or supervised["global_step"] != reference["global_step"]:
            failures.append(f"parameters or steps differ from {name}")
    if supervised["estimated_minimum_free_gib"] < 7:
        failures.append("GPU headroom contract failed")

    comparisons = [
        compare(reference_metrics["width_shift"], supervised_metrics["bounded_detail_supervised"], "baseline_to_supervised"),
        compare(reference_metrics["bounded_detail"], supervised_metrics["bounded_detail_supervised"], "unsupervised_to_supervised"),
    ]
    summaries = {"width_shift": baseline["locked_challenge"], "bounded_detail": unsupervised["locked_challenge"], "bounded_detail_supervised": supervised["locked_challenge"]}
    supervised_summary = summaries["bounded_detail_supervised"]
    utilization = float(supervised_summary.get("detail_target_utilization_ratio", 0.0))
    amplitude = float(supervised_summary["detail_abs_mean_gray"])
    baseline_summary = summaries["width_shift"]
    directional = {
        "worst_assd_improved": supervised_summary["assd_worst_px"] < baseline_summary["assd_worst_px"],
        "p95_assd_improved": supervised_summary["assd_p95_px"] < baseline_summary["assd_p95_px"],
        "worst_iou_improved": supervised_summary["iou_worst"] > baseline_summary["iou_worst"],
        "hf_rmse_improved": supervised_summary["high_frequency_rmse_mean_gray"] < baseline_summary["high_frequency_rmse_mean_gray"],
        "boundary_mae_improved": supervised_summary["boundary_mae_mean_gray"] < baseline_summary["boundary_mae_mean_gray"],
        "condition_consistency_improved": supervised_summary["same_shape_condition_assd_mean_px"] < baseline_summary["same_shape_condition_assd_mean_px"],
    }
    if amplitude < 0.5 or utilization < 0.05:
        assessment = "direct supervision still fails to activate enough bounded detail"
        next_action = "change support/parameterization rather than increasing epochs"
    elif sum(directional.values()) >= 4:
        assessment = "directly supervised bounded detail is a supported architecture mechanism"
        next_action = "include it in the next full scratch design, then validate SEM/LSC/real images"
    else:
        assessment = "direct supervision activates detail but its target or support is not physically selective enough"
        next_action = "redesign target/support before a full model"

    result = {
        "status": "complete",
        "generated_local": datetime.now().astimezone().isoformat(),
        "scope": "same seed/data/order/steps scratch mechanism comparison",
        "summaries": summaries,
        "comparisons": comparisons,
        "detail_target_utilization_ratio": utilization,
        "detail_abs_mean_gray": amplitude,
        "directional_checks": directional,
        "assessment": assessment,
        "next_action": next_action,
        "formal_candidate_promoted": False,
    }
    OUTPUT.mkdir(parents=True, exist_ok=True)
    (OUTPUT / "supervised_formal_comparison.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    validation = {
        "status": "pass" if not failures else "fail",
        "validated_local": datetime.now().astimezone().isoformat(),
        "matched_initial_state": not any("initial state" in value for value in failures),
        "matched_post_detector_state": not any("post-detector" in value for value in failures),
        "matched_parameters_and_steps": not any("parameters or steps" in value for value in failures),
        "paired_scenes": comparisons[0]["paired_scenes"],
        "minimum_estimated_free_gib": float(supervised["estimated_minimum_free_gib"]),
        "final_checkpoint_exists": (supervised_roots["bounded_detail_supervised"] / "epoch_008.pth").is_file(),
        "failures": failures,
    }
    if not validation["final_checkpoint_exists"]:
        validation["failures"].append("supervised final checkpoint missing")
        validation["status"] = "fail"
    (OUTPUT / "supervised_formal_validation.json").write_text(json.dumps(validation, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"comparison": result, "validation": validation}, ensure_ascii=False, indent=2))
    return 0 if validation["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())

"""Validate and compare the matched two-arm formal renderer microprobe."""
from __future__ import annotations

import hashlib
import json
import math
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "results"
REGISTRY = ROOT / "runs" / "latest_formal_registry.json"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(4 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> int:
    if not REGISTRY.is_file():
        raise RuntimeError("Formal registry is not present; formal run is incomplete")
    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
    failures: list[str] = []
    if not registry.get("formal_confirmed") or registry.get("status") != "complete":
        failures.append("formal registry is not complete and confirmed")
    states = {}
    metrics = {}
    histories = {}
    run_dirs = {}
    for item in registry["runs"]:
        arm = item["arm"]
        run_dir = Path(item["run_dir"])
        run_dirs[arm] = run_dir
        states[arm] = json.loads((run_dir / "run_state.json").read_text(encoding="utf-8"))
        metrics[arm] = pd.read_csv(run_dir / "locked_challenge_metrics.csv", encoding="utf-8-sig")
        histories[arm] = json.loads((run_dir / "training_history.json").read_text(encoding="utf-8"))
    if set(states) != {"width_shift", "bounded_detail"}:
        failures.append(f"unexpected formal arms: {sorted(states)}")
    baseline, detail = states["width_shift"], states["bounded_detail"]
    for arm, state in states.items():
        if state.get("status") != "complete" or state.get("mode") != "formal" or state.get("epochs_completed") != 8:
            failures.append(f"{arm}: incomplete formal state")
        if len(histories[arm]) != 8:
            failures.append(f"{arm}: expected eight history rows")
        checkpoint = run_dirs[arm] / "epoch_008.pth"
        if not checkpoint.is_file():
            failures.append(f"{arm}: final checkpoint missing")
    if baseline["initial_state_sha256"] != detail["initial_state_sha256"]:
        failures.append("initial states differ")
    if baseline["post_detector_state_sha256"] != detail["post_detector_state_sha256"]:
        failures.append("post-detector states differ")
    if baseline["parameters"] != detail["parameters"]:
        failures.append("parameter counts differ")
    if baseline["global_step"] != detail["global_step"]:
        failures.append("optimizer step counts differ")
    if min(state["estimated_minimum_free_gib"] for state in states.values()) < 7:
        failures.append("GPU headroom contract failed")

    key = "scene_id"
    joined = metrics["width_shift"].merge(metrics["bounded_detail"], on=key, suffixes=("_baseline", "_detail"), validate="one_to_one")
    if len(joined) != 24:
        failures.append(f"expected 24 paired locked scenes, found {len(joined)}")
    numeric = joined.select_dtypes(include=[np.number]).to_numpy(float)
    if not np.isfinite(numeric).all():
        failures.append("non-finite locked challenge metric")

    metric_directions = {
        "assd_px": "lower",
        "iou": "higher",
        "boundary_mae_gray": "lower",
        "high_frequency_rmse_gray": "lower",
    }
    rng = np.random.default_rng(113888)
    indices = rng.integers(0, len(joined), size=(20_000, len(joined)))
    paired_results = {}
    for metric, direction in metric_directions.items():
        difference = joined[f"{metric}_detail"].to_numpy(float) - joined[f"{metric}_baseline"].to_numpy(float)
        sampled = np.median(difference[indices], axis=1)
        low, high = np.percentile(sampled, [2.5, 97.5])
        improved = difference < 0 if direction == "lower" else difference > 0
        paired_results[metric] = {
            "direction": direction,
            "median_detail_minus_baseline": float(np.median(difference)),
            "mean_detail_minus_baseline": float(np.mean(difference)),
            "ci95_of_paired_median": [float(low), float(high)],
            "improved_scenes": int(improved.sum()),
            "scenes": len(difference),
        }

    b = baseline["locked_challenge"]
    d = detail["locked_challenge"]
    headline = {
        name: {"baseline": float(b[name]), "bounded_detail": float(d[name]), "difference": float(d[name] - b[name])}
        for name in (
            "assd_median_px", "assd_p95_px", "assd_worst_px", "iou_mean", "iou_worst",
            "boundary_mae_mean_gray", "high_frequency_rmse_mean_gray", "same_shape_condition_assd_mean_px",
            "shape_retention_ratio", "shape_distance_spearman", "detail_abs_mean_gray", "detail_local_mean_gray",
        )
    }
    detail_amplitude = float(d["detail_abs_mean_gray"])
    directionally_better = sum([
        d["assd_worst_px"] < b["assd_worst_px"],
        d["assd_p95_px"] < b["assd_p95_px"],
        d["high_frequency_rmse_mean_gray"] < b["high_frequency_rmse_mean_gray"],
        d["iou_worst"] > b["iou_worst"],
    ])
    if detail_amplitude < 0.5:
        assessment = "bounded detail remained weakly used; current loss does not test its full capacity"
        next_action = "add direct staged supervision for the bounded residual before judging the branch"
    elif directionally_better >= 3 and abs(d["shape_retention_ratio"] - 1.0) <= abs(b["shape_retention_ratio"] - 1.0) + 0.03:
        assessment = "bounded detail is supported as a mechanism, not yet as a deployable candidate"
        next_action = "carry the branch into a full scratch design with SEM/LSC/real-image validation"
    else:
        assessment = "bounded detail is active but does not consistently beat the matched renderer"
        next_action = "revise detail supervision or support logic before any larger training"

    comparison = {
        "status": "complete",
        "generated_local": datetime.now().astimezone().isoformat(),
        "scientific_scope": "matched eight-epoch synthetic mechanism probe",
        "arms": {arm: states[arm] for arm in states},
        "headline": headline,
        "paired_scene_results": paired_results,
        "assessment": assessment,
        "next_action": next_action,
        "formal_candidate_promoted": False,
        "checkpoint_sha256": {arm: sha256(run_dirs[arm] / "epoch_008.pth") for arm in run_dirs},
    }
    OUTPUT.mkdir(parents=True, exist_ok=True)
    (OUTPUT / "formal_comparison.json").write_text(json.dumps(comparison, ensure_ascii=False, indent=2), encoding="utf-8")
    validation = {
        "status": "pass" if not failures else "fail",
        "validated_local": datetime.now().astimezone().isoformat(),
        "formal_confirmed": bool(registry.get("formal_confirmed")),
        "matched_initial_state": baseline["initial_state_sha256"] == detail["initial_state_sha256"],
        "matched_post_detector_state": baseline["post_detector_state_sha256"] == detail["post_detector_state_sha256"],
        "matched_parameters": baseline["parameters"] == detail["parameters"],
        "matched_steps": baseline["global_step"] == detail["global_step"],
        "paired_locked_scenes": len(joined),
        "minimum_estimated_free_gib": float(min(state["estimated_minimum_free_gib"] for state in states.values())),
        "failures": failures,
    }
    (OUTPUT / "formal_validation.json").write_text(json.dumps(validation, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"comparison": comparison, "validation": validation}, ensure_ascii=False, indent=2))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())

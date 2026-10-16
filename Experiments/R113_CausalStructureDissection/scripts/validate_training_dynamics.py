"""Independent QA and decision-oriented summary for training trajectories."""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "results" / "training_dynamics"
OUTPUT = SOURCE / "validation.json"
KEY = ["model", "epoch", "scene_index", "observation"]
METRICS = [
    "mae_to_target_gray",
    "mae_change_from_source_gray",
    "low_frequency_change_gray",
    "gradient_mae_gray",
    "high_frequency_energy_ratio",
    "dice",
    "boundary_distance_px",
    "centroid_error_px",
    "area_error_fraction",
]


def row(frame: pd.DataFrame, model: str, epoch: int, observation: str) -> pd.Series:
    subset = frame.loc[
        frame["model"].eq(model)
        & frame["epoch"].eq(epoch)
        & frame["observation"].eq(observation)
    ]
    if len(subset) != 1:
        raise RuntimeError(f"Expected one row for {model} E{epoch} {observation}, found {len(subset)}")
    return subset.iloc[0]


def main() -> int:
    failures: list[str] = []
    detail = pd.read_csv(SOURCE / "per_sample.csv")
    summary = pd.read_csv(SOURCE / "summary.csv")
    challenges = pd.read_csv(SOURCE / "challenge_summary.csv")
    if len(detail) != 1344:
        failures.append(f"expected 1344 detail rows, found {len(detail)}")
    duplicates = int(detail.duplicated(KEY).sum())
    if duplicates:
        failures.append(f"duplicate trajectory keys: {duplicates}")
    always_finite = [metric for metric in METRICS if metric not in {"boundary_distance_px", "centroid_error_px"}]
    if not np.isfinite(detail[always_finite].to_numpy(float)).all():
        failures.append("non-finite always-defined metric in trajectory detail")
    geometry_missing = detail[["boundary_distance_px", "centroid_error_px"]].isna().any(axis=1)
    invalid_geometry_missing = geometry_missing & ~detail["role"].eq("flat_negative")
    if invalid_geometry_missing.any():
        failures.append(f"geometry metric missing outside flat negatives: {int(invalid_geometry_missing.sum())}")

    expected_population = set(zip(detail.loc[(detail.model == "R109") & (detail.epoch == 4), "scene_index"], detail.loc[(detail.model == "R109") & (detail.epoch == 4), "observation"]))
    population_mismatches: list[str] = []
    for (model, epoch), group in detail.groupby(["model", "epoch"]):
        population = set(zip(group["scene_index"], group["observation"]))
        if population != expected_population:
            population_mismatches.append(f"{model}_E{int(epoch)}")
    if population_mismatches:
        failures.append(f"population mismatch: {population_mismatches}")

    recomputed = detail.groupby(["model", "epoch", "observation"], as_index=False)[METRICS].median()
    merged = summary.merge(recomputed, on=["model", "epoch", "observation"], suffixes=("_saved", "_recomputed"), validate="one_to_one")
    max_difference = 0.0
    for metric in METRICS:
        difference = np.max(np.abs(merged[f"{metric}_saved"].to_numpy(float) - merged[f"{metric}_recomputed"].to_numpy(float)))
        max_difference = max(max_difference, float(difference))
    if max_difference > 1e-10:
        failures.append(f"summary recomputation mismatch: {max_difference}")

    endpoints: dict[str, dict[str, float]] = {}
    for model, start_epoch, end_epoch in (("R109", 4, 48), ("V42", 1, 120)):
        start = row(summary, model, start_epoch, "degraded")
        end = row(summary, model, end_epoch, "degraded")
        clear_start = row(summary, model, start_epoch, "clear")
        clear_end = row(summary, model, end_epoch, "clear")
        endpoints[model] = {
            "boundary_distance_start_px": float(start["boundary_distance_px"]),
            "boundary_distance_end_px": float(end["boundary_distance_px"]),
            "boundary_distance_change_pct": float((end["boundary_distance_px"] / start["boundary_distance_px"] - 1.0) * 100.0),
            "target_mae_start_gray": float(start["mae_to_target_gray"]),
            "target_mae_end_gray": float(end["mae_to_target_gray"]),
            "low_frequency_change_start_gray": float(start["low_frequency_change_gray"]),
            "low_frequency_change_end_gray": float(end["low_frequency_change_gray"]),
            "clear_identity_change_start_gray": float(clear_start["mae_change_from_source_gray"]),
            "clear_identity_change_end_gray": float(clear_end["mae_change_from_source_gray"]),
        }

    challenge_endpoints: list[dict[str, object]] = []
    for model, start_epoch, end_epoch in (("R109", 4, 48), ("V42", 1, 120)):
        start = challenges.loc[(challenges.model == model) & (challenges.epoch == start_epoch)].set_index("challenge")
        end = challenges.loc[(challenges.model == model) & (challenges.epoch == end_epoch)].set_index("challenge")
        for challenge in sorted(set(start.index) & set(end.index)):
            challenge_endpoints.append(
                {
                    "model": model,
                    "challenge": challenge,
                    "start_epoch": start_epoch,
                    "end_epoch": end_epoch,
                    "boundary_start_px": float(start.loc[challenge, "boundary_distance_px"]),
                    "boundary_end_px": float(end.loc[challenge, "boundary_distance_px"]),
                    "boundary_change_pct": float((end.loc[challenge, "boundary_distance_px"] / max(float(start.loc[challenge, "boundary_distance_px"]), 1e-9) - 1.0) * 100.0),
                    "low_frequency_change_end_gray": float(end.loc[challenge, "low_frequency_change_gray"]),
                }
            )
    endpoint_frame = pd.DataFrame(challenge_endpoints)
    endpoint_frame.to_csv(SOURCE / "challenge_endpoint_changes.csv", index=False, encoding="utf-8-sig")

    result = {
        "status": "pass" if not failures else "fail",
        "validated_local": datetime.now().astimezone().isoformat(),
        "detail_rows": len(detail),
        "summary_rows": len(summary),
        "challenge_rows": len(challenges),
        "duplicate_keys": duplicates,
        "population_mismatches": population_mismatches,
        "summary_recompute_max_abs_difference": max_difference,
        "expected_flat_negative_geometry_missing_rows": int(geometry_missing.sum()),
        "endpoints": endpoints,
        "challenge_endpoint_rows": len(endpoint_frame),
        "failures": failures,
        "interpretation_boundary": "Trajectory comparisons are within model; V42 and R109 used different training programs, so endpoint differences do not isolate architecture.",
    }
    OUTPUT.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())

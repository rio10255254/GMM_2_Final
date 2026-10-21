"""Summarize R97 training continuity, validation trajectory, and late-stage behavior."""
from __future__ import annotations

import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
RUN = ROOT / "runs" / "training_R97_scratch_seed970043_20260813_200802"
LOG = RUN / "training_log.csv"
SUMMARY = RUN / "run_summary.json"
OUTPUT = ROOT / "results" / "posttraining_validation" / "training_dynamics"
LOWER_IS_BETTER = ["val_texture", "val_contour", "val_identity_gray", "val_motion"]
HIGHER_IS_BETTER = ["val_periodic_margin"]


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    temporary.replace(path)


def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    frame = pd.read_csv(LOG)
    summary = json.loads(SUMMARY.read_text(encoding="utf-8"))
    numeric = frame.select_dtypes(include=[np.number])
    numeric_values = numeric.to_numpy(dtype=float)
    present_numeric_values = numeric_values[~np.isnan(numeric_values)]
    epochs = frame["epoch"].astype(int).tolist()
    expected = list(range(1, 49))
    validation = frame.loc[frame["val_texture"].notna()].copy()
    validation_epochs = validation["epoch"].astype(int).tolist()
    best: dict[str, dict[str, float | int]] = {}
    for metric in LOWER_IS_BETTER:
        index = validation[metric].idxmin()
        best[metric] = {"epoch": int(frame.loc[index, "epoch"]), "value": float(frame.loc[index, metric])}
    for metric in HIGHER_IS_BETTER:
        index = validation[metric].idxmax()
        best[metric] = {"epoch": int(frame.loc[index, "epoch"]), "value": float(frame.loc[index, metric])}
    first = validation.iloc[0]
    final = validation.iloc[-1]
    late = validation.loc[validation["epoch"] == 44].iloc[0]
    change_first_to_final: dict[str, float] = {}
    change_e44_to_final: dict[str, float] = {}
    for metric in LOWER_IS_BETTER + HIGHER_IS_BETTER:
        change_first_to_final[metric] = float((final[metric] - first[metric]) / max(abs(float(first[metric])), 1e-12))
        change_e44_to_final[metric] = float((final[metric] - late[metric]) / max(abs(float(late[metric])), 1e-12))
    phase_summary = frame.groupby("phase", sort=False).agg(
        epoch_start=("epoch", "min"),
        epoch_end=("epoch", "max"),
        epochs=("epoch", "count"),
        mean_epoch_seconds=("seconds", "mean"),
        mean_train_total=("train_total", "mean"),
        mean_abs_periodic_margin=("train_periodic_margin", lambda s: float(np.mean(np.abs(s)))),
        peak_gpu_gib=("gpu_peak_gib", "max"),
        minimum_reported_free_gib=("gpu_peak_free_gib", "min"),
    ).reset_index()
    phase_summary.to_csv(OUTPUT / "phase_summary.csv", index=False)
    validation.to_csv(OUTPUT / "validation_trajectory.csv", index=False)

    figure, axes = plt.subplots(3, 2, figsize=(13, 12), sharex=True)
    plots = [
        ("val_texture", "Texture error", "lower is better"),
        ("val_contour", "Contour error", "lower is better"),
        ("val_identity_gray", "Clear-image change", "gray levels; lower is better"),
        ("val_motion", "Motion consistency error", "lower is better"),
        ("val_periodic_margin", "True-vs-wrong-period margin", "higher is better"),
        ("val_wrong_pitch_rate", "Wrong-period match rate", "lower is better"),
    ]
    for axis, (metric, title, ylabel) in zip(axes.ravel(), plots):
        axis.plot(validation["epoch"], validation[metric], marker="o", color="#2563EB")
        axis.axvline(44, color="#9CA3AF", linestyle="--", linewidth=1)
        axis.axvline(48, color="#111827", linestyle=":", linewidth=1)
        axis.set_title(title)
        axis.set_ylabel(ylabel)
        axis.grid(alpha=.2)
    for axis in axes[-1]:
        axis.set_xlabel("Epoch")
    figure.tight_layout()
    figure.savefig(OUTPUT / "validation_trajectory.png", dpi=180)
    plt.close(figure)

    result = {
        "status": "complete",
        "run_status": summary["status"],
        "planned_epochs": 48,
        "logged_epochs": len(frame),
        "epochs_contiguous": epochs == expected,
        "validation_epochs": validation_epochs,
        "validation_schedule_complete": validation_epochs == [1] + list(range(4, 49, 4)),
        "all_present_numeric_values_finite": bool(np.isfinite(present_numeric_values).all()),
        "all_wrong_pitch_rates_zero": bool((validation["val_wrong_pitch_rate"] == 0.0).all()),
        "total_logged_seconds": float(frame["seconds"].sum()),
        "mean_epoch_seconds": float(frame["seconds"].mean()),
        "maximum_gpu_peak_gib": float(frame["gpu_peak_gib"].max()),
        "minimum_reported_gpu_free_gib": float(frame["gpu_peak_free_gib"].min()),
        "best_validation": best,
        "relative_change_e1_to_e48": change_first_to_final,
        "relative_change_e44_to_e48": change_e44_to_final,
        "final_validation": {metric: float(final[metric]) for metric in LOWER_IS_BETTER + HIGHER_IS_BETTER + ["val_wrong_pitch_rate"]},
        "phase_summary": phase_summary.to_dict(orient="records"),
        "interpretation_guard": "Training loss mixes scheduled roles and phases; compare fixed validation rows rather than raw epoch loss across phases.",
    }
    write_json(OUTPUT / "summary.json", result)
    print(json.dumps(result, indent=2), flush=True)


if __name__ == "__main__":
    main()

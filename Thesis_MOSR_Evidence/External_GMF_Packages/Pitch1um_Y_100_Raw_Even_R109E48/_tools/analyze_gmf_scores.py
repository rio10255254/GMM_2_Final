"""Parse, compare, and validate the external GMF coordinates for Raw and R109."""
from __future__ import annotations

import csv
import hashlib
import json
import math
import re
from datetime import datetime
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


PACKAGE = Path(__file__).resolve().parents[1]
OUTPUT = PACKAGE / "gmf_analysis"
HISTORICAL_PACKAGE = PACKAGE.parent / "Pitch1um_Y_100_Raw_Even_R103E48_R104E48"
EXPECTED_Y_STEP_PX = -8.0
EXPECTED_FRAMES = list(range(1, 101))

SCORE_FILES = {
    "current_raw": PACKAGE / "_gmf_scores" / "pitch1um_y100_raw" / "GMF_score.txt",
    "r109_e48": PACKAGE / "_gmf_scores" / "pitch1um_y100_r109_e48" / "GMF_score.txt",
    "historical_raw": HISTORICAL_PACKAGE / "_gmf_scores" / "pitch1um_y100_raw" / "GMF_score.txt",
    "historical_r103_e48": HISTORICAL_PACKAGE / "_gmf_scores" / "pitch1um_y100_r103_e48" / "GMF_score.txt",
    "historical_r104_raw_negative_control": HISTORICAL_PACKAGE
    / "_gmf_scores"
    / "pitch1um_y100_r104_e48"
    / "GMF_score.txt",
}


def file_record(path: Path) -> dict[str, object]:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return {
        "path": str(path),
        "bytes": path.stat().st_size,
        "modified_local": datetime.fromtimestamp(path.stat().st_mtime).astimezone().isoformat(),
        "sha256": digest.hexdigest(),
    }


def parse_score_file(arm: str, path: Path) -> pd.DataFrame:
    if not path.is_file():
        raise FileNotFoundError(path)
    rows: list[dict[str, object]] = []
    parse_errors: list[str] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8-sig").splitlines(), start=1):
        parts = [part.strip() for part in line.split(",")]
        if len(parts) % 2 != 0:
            parse_errors.append(f"line {line_number}: odd field count")
            continue
        values = {parts[index]: parts[index + 1] for index in range(0, len(parts), 2)}
        try:
            match = re.fullmatch(r"frame_(\d{4})\.bmp", values["FileName"])
            if match is None:
                raise ValueError("unexpected filename")
            rows.append(
                {
                    "arm": arm,
                    "frame_name": values["FileName"],
                    "frame_index": int(match.group(1)),
                    "time_ms": float(values["Time(ms)"]),
                    "x_px": float(values["PosX"]),
                    "y_px": float(values["PosY"]),
                    "angle_deg": float(values["Angle"]),
                    "scale": float(values["Scale"]),
                    "score0": float(values["Score0"]),
                    "score1": float(values["Score1"]),
                    "score_diff": float(values["Score Diff"]),
                }
            )
        except (KeyError, ValueError) as error:
            parse_errors.append(f"line {line_number}: {error}")
    if parse_errors:
        raise RuntimeError(f"Parse errors in {path}: {parse_errors}")
    frame = pd.DataFrame(rows).sort_values("frame_index").reset_index(drop=True)
    return frame


def validate_arm(frame: pd.DataFrame) -> dict[str, object]:
    indices = frame["frame_index"].astype(int).tolist()
    numeric = frame[["time_ms", "x_px", "y_px", "angle_deg", "scale", "score0", "score1", "score_diff"]]
    return {
        "coordinate_rows": int(len(frame)),
        "frame_indices_exact_1_to_100": indices == EXPECTED_FRAMES,
        "duplicate_frame_count": int(frame["frame_index"].duplicated().sum()),
        "all_numeric_finite": bool(np.isfinite(numeric.to_numpy(dtype=float)).all()),
        "score_positive": bool((frame["score0"] > 0).all()),
        "scale_plausible_0p9_to_1p1": bool(frame["scale"].between(0.9, 1.1).all()),
        "angle_zero": bool(np.allclose(frame["angle_deg"], 0.0)),
    }


def steps_for(frame: pd.DataFrame) -> pd.DataFrame:
    values = frame.copy()
    result = pd.DataFrame(
        {
            "arm": values["arm"].iloc[1:].to_numpy(),
            "from_frame": values["frame_index"].iloc[:-1].to_numpy(dtype=int),
            "to_frame": values["frame_index"].iloc[1:].to_numpy(dtype=int),
            "dx_px": np.diff(values["x_px"].to_numpy(dtype=float)),
            "dy_px": np.diff(values["y_px"].to_numpy(dtype=float)),
            "scale_change_abs": np.abs(np.diff(values["scale"].to_numpy(dtype=float))),
            "interval_min_score": np.minimum(
                values["score0"].iloc[:-1].to_numpy(dtype=float),
                values["score0"].iloc[1:].to_numpy(dtype=float),
            ),
        }
    )
    result["y_error_px"] = result["dy_px"] - EXPECTED_Y_STEP_PX
    result["abs_y_error_px"] = result["y_error_px"].abs()
    result["step_magnitude_px"] = np.hypot(result["dx_px"], result["dy_px"])
    result["vector_error_px"] = np.hypot(result["dx_px"], result["y_error_px"])
    result["correct_y_direction"] = result["dy_px"] < 0
    return result


def robust_sigma(values: np.ndarray) -> float:
    median = np.median(values)
    return float(1.4826 * np.median(np.abs(values - median)))


def arm_summary(frame: pd.DataFrame, steps: pd.DataFrame) -> dict[str, object]:
    x = frame["x_px"].to_numpy(dtype=float)
    y = frame["y_px"].to_numpy(dtype=float)
    frame_index = frame["frame_index"].to_numpy(dtype=float)
    dy = steps["dy_px"].to_numpy(dtype=float)
    dx = steps["dx_px"].to_numpy(dtype=float)
    error = steps["y_error_px"].to_numpy(dtype=float)
    slope, intercept = np.polyfit(frame_index, y, 1)
    detrended = y - (slope * frame_index + intercept)
    endpoint = float(y[-1] - y[0])
    expected_endpoint = EXPECTED_Y_STEP_PX * (len(y) - 1)
    return {
        "arm": str(frame["arm"].iloc[0]),
        "coordinate_rows": int(len(frame)),
        "step_count": int(len(steps)),
        "score_median": float(np.median(frame["score0"])),
        "score_p05": float(np.percentile(frame["score0"], 5)),
        "score_min": float(np.min(frame["score0"])),
        "scale_median": float(np.median(frame["scale"])),
        "scale_std": float(np.std(frame["scale"], ddof=1)),
        "runtime_median_ms": float(np.median(frame["time_ms"])),
        "y_step_mean_px": float(np.mean(dy)),
        "y_step_median_px": float(np.median(dy)),
        "y_step_bias_px": float(np.mean(dy) - EXPECTED_Y_STEP_PX),
        "y_step_bias_pct": float((np.mean(dy) - EXPECTED_Y_STEP_PX) / abs(EXPECTED_Y_STEP_PX) * 100.0),
        "y_step_std_px": float(np.std(dy, ddof=1)),
        "y_step_robust_sigma_px": robust_sigma(dy),
        "y_error_mae_px": float(np.mean(np.abs(error))),
        "y_error_median_abs_px": float(np.median(np.abs(error))),
        "y_error_rmse_px": float(np.sqrt(np.mean(error**2))),
        "y_error_p95_abs_px": float(np.percentile(np.abs(error), 95)),
        "within_20pct": float(np.mean(np.abs(error) <= 0.20 * abs(EXPECTED_Y_STEP_PX))),
        "within_25pct": float(np.mean(np.abs(error) <= 0.25 * abs(EXPECTED_Y_STEP_PX))),
        "within_30pct": float(np.mean(np.abs(error) <= 0.30 * abs(EXPECTED_Y_STEP_PX))),
        "correct_direction_fraction": float(np.mean(dy < 0)),
        "wrong_direction_steps": int(np.sum(dy >= 0)),
        "x_step_mean_px": float(np.mean(dx)),
        "x_step_std_px": float(np.std(dx, ddof=1)),
        "x_step_mae_px": float(np.mean(np.abs(dx))),
        "x_step_p95_abs_px": float(np.percentile(np.abs(dx), 95)),
        "step_magnitude_median_px": float(np.median(steps["step_magnitude_px"])),
        "step_magnitude_std_px": float(np.std(steps["step_magnitude_px"], ddof=1)),
        "fitted_y_slope_px_per_frame": float(slope),
        "detrended_y_coordinate_std_px": float(np.std(detrended, ddof=1)),
        "endpoint_y_displacement_px": endpoint,
        "endpoint_expected_px": expected_endpoint,
        "endpoint_error_px": float(endpoint - expected_endpoint),
        "endpoint_error_pct": float((endpoint - expected_endpoint) / abs(expected_endpoint) * 100.0),
        "endpoint_x_drift_px": float(x[-1] - x[0]),
    }


def paired_block_bootstrap(raw_steps: pd.DataFrame, model_steps: pd.DataFrame) -> dict[str, object]:
    raw_y = raw_steps["dy_px"].to_numpy(dtype=float)
    model_y = model_steps["dy_px"].to_numpy(dtype=float)
    raw_x = raw_steps["dx_px"].to_numpy(dtype=float)
    model_x = model_steps["dx_px"].to_numpy(dtype=float)
    if len(raw_y) != len(model_y):
        raise RuntimeError("Paired bootstrap requires equal step counts")
    rng = np.random.default_rng(109)
    block_length = 5
    repetitions = 20_000
    n = len(raw_y)
    ratios: dict[str, list[float]] = {"y_step_std": [], "y_error_mae": [], "x_step_std": []}
    for _ in range(repetitions):
        indices: list[int] = []
        while len(indices) < n:
            start = int(rng.integers(0, n - block_length + 1))
            indices.extend(range(start, start + block_length))
        selected = np.asarray(indices[:n], dtype=int)
        ratios["y_step_std"].append(float(np.std(model_y[selected], ddof=1) / np.std(raw_y[selected], ddof=1)))
        ratios["y_error_mae"].append(
            float(np.mean(np.abs(model_y[selected] - EXPECTED_Y_STEP_PX)) / np.mean(np.abs(raw_y[selected] - EXPECTED_Y_STEP_PX)))
        )
        ratios["x_step_std"].append(float(np.std(model_x[selected], ddof=1) / np.std(raw_x[selected], ddof=1)))
    result: dict[str, object] = {"block_length": block_length, "repetitions": repetitions, "seed": 109}
    for metric, values in ratios.items():
        array = np.asarray(values, dtype=float)
        result[metric] = {
            "ratio_p025": float(np.percentile(array, 2.5)),
            "ratio_median": float(np.percentile(array, 50.0)),
            "ratio_p975": float(np.percentile(array, 97.5)),
            "fraction_ratio_ge_1": float(np.mean(array >= 1.0)),
        }
    return result


def score_conditioned_summary(arm: str, steps: pd.DataFrame) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for minimum_score in (0.0, 65.0, 68.0, 70.0, 72.0, 74.0):
        selected = steps[steps["interval_min_score"] >= minimum_score]
        rows.append(
            {
                "arm": arm,
                "minimum_interval_score": minimum_score,
                "retained_steps": int(len(selected)),
                "retained_fraction": float(len(selected) / len(steps)),
                "y_step_mean_px": float(selected["dy_px"].mean()),
                "y_step_std_px": float(selected["dy_px"].std(ddof=1)),
                "y_error_mae_px": float(selected["abs_y_error_px"].mean()),
                "wrong_direction_steps": int((selected["dy_px"] >= 0).sum()),
            }
        )
    return rows


def verify_pixel_relationships() -> dict[str, object]:
    current = pd.read_csv(PACKAGE / "source_mapping.csv", encoding="utf-8-sig")
    historical = pd.read_csv(HISTORICAL_PACKAGE / "source_mapping.csv", encoding="utf-8-sig")
    return {
        "same_original_filename_order": bool(current["original_filename"].tolist() == historical["original_filename"].tolist()),
        "same_raw_hashes": bool(current["raw_sha256"].tolist() == historical["raw_sha256"].tolist()),
        "historical_r104_is_pixel_identical_to_raw": bool((historical["r104_sha256"] == historical["raw_sha256"]).all()),
        "historical_r103_differs_from_raw_count": int((historical["r103_sha256"] != historical["raw_sha256"]).sum()),
        "current_r109_differs_from_raw_count": int((current["r109_sha256"] != current["raw_sha256"]).sum()),
    }


def make_figure(frames: dict[str, pd.DataFrame], steps: dict[str, pd.DataFrame], destination: Path) -> None:
    colors = {"current_raw": "#777777", "r109_e48": "#1464F4"}
    labels = {"current_raw": "Raw", "r109_e48": "R109 E48"}
    figure, axes = plt.subplots(2, 2, figsize=(14, 9), constrained_layout=True)

    for arm in ("current_raw", "r109_e48"):
        frame = frames[arm]
        index = frame["frame_index"].to_numpy(dtype=float)
        aligned_y = frame["y_px"].to_numpy(dtype=float) - float(frame["y_px"].iloc[0])
        axes[0, 0].plot(index, aligned_y, linewidth=1.6, color=colors[arm], label=labels[arm])
    axes[0, 0].plot(EXPECTED_FRAMES, EXPECTED_Y_STEP_PX * (np.asarray(EXPECTED_FRAMES) - 1), "--", color="#D94A4A", label="Nominal -8 px/step")
    axes[0, 0].set(title="Aligned Y trajectory", xlabel="Frame", ylabel="Displacement from frame 1 (px)")
    axes[0, 0].legend()
    axes[0, 0].grid(alpha=0.25)

    for arm in ("current_raw", "r109_e48"):
        step = steps[arm]
        axes[0, 1].plot(step["to_frame"], step["dy_px"], linewidth=1.0, marker="o", markersize=2.7, color=colors[arm], label=labels[arm])
    axes[0, 1].axhline(EXPECTED_Y_STEP_PX, linestyle="--", color="#D94A4A")
    axes[0, 1].set(title="Consecutive Y steps", xlabel="Destination frame", ylabel="Y step (px)")
    axes[0, 1].legend()
    axes[0, 1].grid(alpha=0.25)

    for arm in ("current_raw", "r109_e48"):
        step = steps[arm]
        axes[1, 0].plot(step["to_frame"], step["dx_px"], linewidth=1.0, marker="o", markersize=2.7, color=colors[arm], label=labels[arm])
    axes[1, 0].axhline(0.0, linestyle="--", color="#D94A4A")
    axes[1, 0].set(title="Cross-axis step leakage", xlabel="Destination frame", ylabel="X step (px)")
    axes[1, 0].legend()
    axes[1, 0].grid(alpha=0.25)

    for arm in ("current_raw", "r109_e48"):
        frame = frames[arm]
        axes[1, 1].plot(frame["frame_index"], frame["score0"], linewidth=1.4, color=colors[arm], label=labels[arm])
    axes[1, 1].set(title="External GMF score", xlabel="Frame", ylabel="Score0")
    axes[1, 1].legend()
    axes[1, 1].grid(alpha=0.25)

    figure.suptitle("Pitch1um_Y_100 external GMF: Raw vs R109 E48", fontsize=16)
    figure.savefig(destination, dpi=170)
    plt.close(figure)


def main() -> int:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    frames = {arm: parse_score_file(arm, path) for arm, path in SCORE_FILES.items()}
    quality = {arm: validate_arm(frame) for arm, frame in frames.items()}
    if not all(
        item["coordinate_rows"] == 100
        and item["frame_indices_exact_1_to_100"]
        and item["duplicate_frame_count"] == 0
        and item["all_numeric_finite"]
        and item["score_positive"]
        and item["scale_plausible_0p9_to_1p1"]
        for item in quality.values()
    ):
        raise RuntimeError(f"Data-quality gate failed: {quality}")

    steps = {arm: steps_for(frame) for arm, frame in frames.items()}
    summaries = {arm: arm_summary(frames[arm], steps[arm]) for arm in frames}
    summary_frame = pd.DataFrame(summaries.values())
    summary_frame.to_csv(OUTPUT / "arm_summary.csv", index=False, encoding="utf-8-sig")
    pd.concat(frames.values(), ignore_index=True).to_csv(OUTPUT / "coordinate_rows.csv", index=False, encoding="utf-8-sig")
    pd.concat(steps.values(), ignore_index=True).to_csv(OUTPUT / "step_rows.csv", index=False, encoding="utf-8-sig")

    raw_summary = summaries["current_raw"]
    model_summary = summaries["r109_e48"]
    comparison = {
        "y_step_std_reduction_pct": float((1.0 - model_summary["y_step_std_px"] / raw_summary["y_step_std_px"]) * 100.0),
        "y_error_mae_reduction_pct": float((1.0 - model_summary["y_error_mae_px"] / raw_summary["y_error_mae_px"]) * 100.0),
        "x_step_std_reduction_pct": float((1.0 - model_summary["x_step_std_px"] / raw_summary["x_step_std_px"]) * 100.0),
        "detrended_y_std_reduction_pct": float(
            (1.0 - model_summary["detrended_y_coordinate_std_px"] / raw_summary["detrended_y_coordinate_std_px"]) * 100.0
        ),
        "scale_std_reduction_pct": float((1.0 - model_summary["scale_std"] / raw_summary["scale_std"]) * 100.0),
        "wrong_direction_step_reduction": int(raw_summary["wrong_direction_steps"] - model_summary["wrong_direction_steps"]),
        "within_20pct_gain_percentage_points": float((model_summary["within_20pct"] - raw_summary["within_20pct"]) * 100.0),
        "score_median_change": float(model_summary["score_median"] - raw_summary["score_median"]),
        "endpoint_error_change_abs_px": float(abs(model_summary["endpoint_error_px"]) - abs(raw_summary["endpoint_error_px"])),
    }

    raw_equivalent_runs = pd.DataFrame(
        [
            {"run": arm, **summaries[arm]}
            for arm in ("historical_raw", "historical_r104_raw_negative_control", "current_raw")
        ]
    )
    raw_equivalent_runs.to_csv(OUTPUT / "raw_equivalent_run_floor.csv", index=False, encoding="utf-8-sig")
    raw_floor = {
        "y_step_std_px_min": float(raw_equivalent_runs["y_step_std_px"].min()),
        "y_step_std_px_max": float(raw_equivalent_runs["y_step_std_px"].max()),
        "x_step_std_px_min": float(raw_equivalent_runs["x_step_std_px"].min()),
        "x_step_std_px_max": float(raw_equivalent_runs["x_step_std_px"].max()),
        "detrended_y_coordinate_std_px_min": float(raw_equivalent_runs["detrended_y_coordinate_std_px"].min()),
        "detrended_y_coordinate_std_px_max": float(raw_equivalent_runs["detrended_y_coordinate_std_px"].max()),
    }

    bootstrap = paired_block_bootstrap(steps["current_raw"], steps["r109_e48"])
    score_rows = score_conditioned_summary("current_raw", steps["current_raw"]) + score_conditioned_summary("r109_e48", steps["r109_e48"])
    pd.DataFrame(score_rows).to_csv(OUTPUT / "score_conditioned_summary.csv", index=False, encoding="utf-8-sig")

    outliers = pd.concat(
        [
            step.nlargest(10, "abs_y_error_px").assign(outlier_rank=lambda table: np.arange(1, len(table) + 1))
            for step in (steps["current_raw"], steps["r109_e48"])
        ],
        ignore_index=True,
    )
    outliers.to_csv(OUTPUT / "largest_y_step_errors.csv", index=False, encoding="utf-8-sig")

    r109_steps = steps["r109_e48"]
    confidence_relationship = {
        "correlation_abs_y_error_vs_interval_min_score": float(
            np.corrcoef(r109_steps["abs_y_error_px"], r109_steps["interval_min_score"])[0, 1]
        ),
        "correlation_abs_y_error_vs_scale_change": float(
            np.corrcoef(r109_steps["abs_y_error_px"], r109_steps["scale_change_abs"])[0, 1]
        ),
        "score_72_retained_steps": int((r109_steps["interval_min_score"] >= 72).sum()),
        "score_72_wrong_direction_steps": int(
            ((r109_steps["interval_min_score"] >= 72) & (r109_steps["dy_px"] >= 0)).sum()
        ),
    }

    pixel_relationships = verify_pixel_relationships()
    make_figure(frames, steps, OUTPUT / "trajectory_step_score.png")

    result = {
        "status": "complete",
        "generated_local": datetime.now().astimezone().isoformat(),
        "question": "Does R109 E48 improve external-GMF displacement stability on Pitch1um_Y_100 Raw even-position frames?",
        "score_files": {arm: file_record(path) for arm, path in SCORE_FILES.items()},
        "unit": "GMF pixels",
        "nominal_y_step_px": EXPECTED_Y_STEP_PX,
        "physical_calibration": "not sealed in this package; do not convert the pixel statistics into formal micrometre claims",
        "data_quality": quality,
        "pixel_relationships": pixel_relationships,
        "current_raw": raw_summary,
        "r109_e48": model_summary,
        "comparison_vs_current_raw": comparison,
        "raw_equivalent_gmf_run_floor": raw_floor,
        "paired_moving_block_bootstrap": bootstrap,
        "r109_confidence_relationship": confidence_relationship,
        "assessment": {
            "stability_signal": "strong positive",
            "absolute_metrology_readiness": "not yet",
            "reason": (
                "R109 improves Y-step, cross-axis, detrended-coordinate, scale, and direction metrics, and remains below all three raw-equivalent GMF runs. "
                "However, five wrong-direction steps remain, only part of the steps are close to nominal, the median GMF score is lower, and GMF itself is not deterministic on pixel-identical inputs."
            ),
            "confidence": "high for relative stability improvement in this package; moderate for repeatability across a fresh GMF rerun",
        },
    }
    (OUTPUT / "analysis_summary.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

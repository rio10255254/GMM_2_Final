"""Parse and compare external GMF coordinates for the x_1um counterfactual set."""
from __future__ import annotations

import json
import math
import re
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
RESULT = ROOT / "results" / "x1um_counterfactual_reconstruction"
UM_PER_PX = 0.069
TRUSTED_SCORE = 90.0
ARMS = {
    "00_raw": "Raw",
    "01_r96": "R96 E44",
    "02_detail_gate_open": "Detail gate open",
    "03_all_gate_open": "All gates open",
    "04_phase_safe_detail": "Phase-safe detail",
}
PRIMARY_ARMS = tuple(list(ARMS)[:4])


def parse_file(arm: str) -> pd.DataFrame:
    records: list[dict[str, object]] = []
    path = RESULT / arm / "GMF_score.txt"
    for line_number, line in enumerate(path.read_text(encoding="utf-8-sig").splitlines(), start=1):
        parts = [value.strip() for value in line.split(",")]
        if len(parts) % 2 != 0:
            raise RuntimeError(f"{path}:{line_number}: odd token count")
        values = {parts[index]: parts[index + 1] for index in range(0, len(parts), 2)}
        name = values["FileName"]
        match = re.fullmatch(r"frame_(\d{4})\.bmp", name, flags=re.IGNORECASE)
        frame = int(match.group(1)) if match else math.nan
        x, y = float(values["PosX"]), float(values["PosY"])
        score, scale = float(values["Score0"]), float(values["Scale"])
        valid = bool(match and score > 0.0 and scale > 0.0 and not (x == 0.0 and y == 0.0))
        trusted = bool(valid and score >= TRUSTED_SCORE)
        records.append({
            "arm": arm, "label": ARMS[arm], "line_number": line_number,
            "file_name": name, "frame": frame, "is_reference_row": match is None,
            "time_ms": float(values["Time(ms)"]), "x_px": x, "y_px": y,
            "angle": float(values["Angle"]), "scale": scale, "score": score,
            "valid": valid, "trusted": trusted,
        })
    return pd.DataFrame(records)


def robust_mad(values: pd.Series | np.ndarray) -> float:
    array = np.asarray(values, dtype=float)
    median = np.median(array)
    return float(1.4826 * np.median(np.abs(array - median)))


def summarize_arm(group: pd.DataFrame) -> dict[str, object]:
    frames = group.loc[group["frame"].between(1, 49, inclusive="both")].copy()
    valid = frames.loc[frames["trusted"]].sort_values("frame")
    steps = valid.assign(next_frame=valid["frame"].shift(-1), next_x=valid["x_px"].shift(-1), next_y=valid["y_px"].shift(-1))
    steps = steps.loc[steps["next_frame"] == steps["frame"] + 1].copy()
    steps["dx_px"] = steps["next_x"] - steps["x_px"]
    steps["dy_px"] = steps["next_y"] - steps["y_px"]
    steps["x_step_um"] = -steps["dx_px"] * UM_PER_PX
    steps["vector_step_um"] = np.hypot(steps["dx_px"], steps["dy_px"]) * UM_PER_PX
    if len(steps):
        x_step = steps["x_step_um"]
        slope = np.polyfit(valid["frame"], valid["x_px"], 1)[0] if len(valid) >= 2 else math.nan
        endpoint = -(float(valid["x_px"].iloc[-1]) - float(valid["x_px"].iloc[0])) * UM_PER_PX
    else:
        x_step, slope, endpoint = pd.Series(dtype=float), math.nan, math.nan
    return {
        "arm": str(group["arm"].iloc[0]), "label": str(group["label"].iloc[0]),
        "coordinate_rows_expected": 49, "coordinate_rows_present": int(len(frames)),
        "nonzero_coordinate_rows": int(frames["valid"].sum()),
        "trusted_coordinate_rows": int(len(valid)), "trusted_coordinate_fraction": float(len(valid) / 49),
        "low_score_nonzero_rows": int((frames["valid"] & ~frames["trusted"]).sum()),
        "zero_failure_rows": int((~frames["valid"]).sum()),
        "consecutive_steps": int(len(steps)),
        "median_score_trusted": float(valid["score"].median()) if len(valid) else math.nan,
        "minimum_score_trusted": float(valid["score"].min()) if len(valid) else math.nan,
        "median_time_ms": float(frames["time_ms"].median()) if len(frames) else math.nan,
        "median_scale": float(valid["scale"].median()) if len(valid) else math.nan,
        "scale_std": float(valid["scale"].std(ddof=1)) if len(valid) > 1 else math.nan,
        "mean_x_step_um": float(x_step.mean()) if len(x_step) else math.nan,
        "median_x_step_um": float(x_step.median()) if len(x_step) else math.nan,
        "x_step_std_um": float(x_step.std(ddof=1)) if len(x_step) > 1 else math.nan,
        "x_step_robust_mad_um": robust_mad(x_step) if len(x_step) else math.nan,
        "mean_bias_from_1um": float(x_step.mean() - 1.0) if len(x_step) else math.nan,
        "rmse_from_1um": float(np.sqrt(np.mean((x_step - 1.0) ** 2))) if len(x_step) else math.nan,
        "p95_abs_error_from_1um": float(np.quantile(np.abs(x_step - 1.0), .95)) if len(x_step) else math.nan,
        "median_abs_y_step_um": float(np.median(np.abs(steps["dy_px"])) * UM_PER_PX) if len(steps) else math.nan,
        "endpoint_x_span_um": endpoint,
        "linear_fit_x_step_um": float(-slope * UM_PER_PX) if math.isfinite(slope) else math.nan,
    }


def main() -> None:
    tables = [parse_file(arm) for arm in ARMS]
    coordinates = pd.concat(tables, ignore_index=True)
    coordinates.to_csv(RESULT / "external_gmf_coordinates.csv", index=False)

    # A fair comparison uses frame_0001..frame_0049, present in every export.
    fair = coordinates.loc[coordinates["frame"].between(1, 49, inclusive="both")].copy()
    expected = pd.MultiIndex.from_product([ARMS, range(1, 50)], names=["arm", "frame"])
    actual = fair.set_index(["arm", "frame"]).index
    missing = expected.difference(actual)
    duplicates = int(fair.duplicated(["arm", "frame"]).sum())

    summary = pd.DataFrame([summarize_arm(table) for table in tables])

    wide = fair.pivot(index="frame", columns="arm", values=["x_px", "y_px", "score", "valid"])
    pair_records: list[dict[str, object]] = []
    raw = fair.loc[(fair["arm"] == "00_raw") & fair["trusted"]].set_index("frame")
    def consecutive_x_steps(table: pd.DataFrame) -> pd.Series:
        ordered = table.sort_index()
        step = -ordered["x_px"].diff() * UM_PER_PX
        return step.loc[ordered.index.to_series().diff() == 1].dropna()

    raw_step = consecutive_x_steps(raw)
    for arm in PRIMARY_ARMS[1:]:
        model = fair.loc[(fair["arm"] == arm) & fair["trusted"]].set_index("frame")
        joined = raw[["x_px", "y_px"]].join(model[["x_px", "y_px"]], lsuffix="_raw", rsuffix="_model", how="inner")
        joined["offset_x_um"] = (joined["x_px_model"] - joined["x_px_raw"]) * UM_PER_PX
        joined["offset_y_um"] = (joined["y_px_model"] - joined["y_px_raw"]) * UM_PER_PX
        model_step = consecutive_x_steps(model)
        paired_steps = pd.concat([raw_step.rename("raw"), model_step.rename("model")], axis=1).dropna()
        delta = paired_steps["model"] - paired_steps["raw"]
        pair_records.append({
            "arm": arm, "label": ARMS[arm], "paired_coordinates": int(len(joined)),
            "median_x_offset_vs_raw_um": float(joined["offset_x_um"].median()),
            "x_offset_variation_std_um": float(joined["offset_x_um"].std(ddof=1)),
            "median_y_offset_vs_raw_um": float(joined["offset_y_um"].median()),
            "y_offset_variation_std_um": float(joined["offset_y_um"].std(ddof=1)),
            "paired_steps": int(len(delta)), "mean_step_difference_vs_raw_um": float(delta.mean()),
            "median_abs_step_difference_vs_raw_um": float(np.median(np.abs(delta))),
            "p95_abs_step_difference_vs_raw_um": float(np.quantile(np.abs(delta), .95)),
            "step_difference_std_um": float(delta.std(ddof=1)),
        })
    pair_summary = pd.DataFrame(pair_records)

    # Step-level table for exact review and plots.
    step_records: list[dict[str, object]] = []
    for arm in PRIMARY_ARMS:
        frame_table = fair.loc[(fair["arm"] == arm) & fair["trusted"]].sort_values("frame")
        for (_, first), (_, second) in zip(frame_table.iloc[:-1].iterrows(), frame_table.iloc[1:].iterrows()):
            if int(second["frame"]) != int(first["frame"]) + 1:
                continue
            step_records.append({
                "arm": arm, "label": ARMS[arm], "from_frame": int(first["frame"]),
                "to_frame": int(second["frame"]),
                "x_step_um": -(float(second["x_px"]) - float(first["x_px"])) * UM_PER_PX,
                "y_step_um": (float(second["y_px"]) - float(first["y_px"])) * UM_PER_PX,
            })
    steps = pd.DataFrame(step_records)
    steps.to_csv(RESULT / "external_gmf_adjacent_steps.csv", index=False)
    key_sets = [
        set(zip(group["from_frame"].astype(int), group["to_frame"].astype(int)))
        for _, group in steps.groupby("arm", sort=False)
    ]
    common_keys = set.intersection(*key_sets)
    common_records: list[dict[str, object]] = []
    for arm, group in steps.groupby("arm", sort=False):
        mask = [(int(first), int(second)) in common_keys for first, second in zip(group["from_frame"], group["to_frame"])]
        values = group.loc[mask, "x_step_um"].astype(float)
        common_records.append({
            "arm": arm, "label": ARMS[arm], "common_steps": int(len(values)),
            "mean_x_step_um": float(values.mean()), "median_x_step_um": float(values.median()),
            "x_step_std_um": float(values.std(ddof=1)), "x_step_robust_mad_um": robust_mad(values),
            "rmse_from_1um": float(np.sqrt(np.mean((values - 1.0) ** 2))),
            "p95_abs_error_from_1um": float(np.quantile(np.abs(values - 1.0), .95)),
        })
    common_summary = pd.DataFrame(common_records)
    common_summary.to_csv(RESULT / "external_gmf_common_step_summary.csv", index=False)
    summary.to_csv(RESULT / "external_gmf_arm_summary.csv", index=False)
    pair_summary.to_csv(RESULT / "external_gmf_vs_raw_summary.csv", index=False)

    colors = {"00_raw": "#4b5563", "01_r96": "#2563eb", "02_detail_gate_open": "#d97706", "03_all_gate_open": "#7c3aed", "04_phase_safe_detail": "#be123c"}
    figure, axes = plt.subplots(2, 2, figsize=(15, 9), constrained_layout=True)
    for arm in PRIMARY_ARMS:
        subset = steps.loc[steps["arm"] == arm]
        axes[0, 0].plot(subset["to_frame"], subset["x_step_um"], marker="o", markersize=2.5, linewidth=1.2, label=ARMS[arm], color=colors[arm])
    axes[0, 0].axhline(1.0, color="black", linestyle="--", linewidth=1, label="Nominal 1.0 um")
    axes[0, 0].set(title="External GMF adjacent X displacement", xlabel="Destination frame", ylabel="Displacement (um)")
    axes[0, 0].legend(ncol=2, fontsize=8)
    axes[0, 0].grid(alpha=.2)

    for arm in ARMS:
        subset = fair.loc[fair["arm"] == arm].sort_values("frame")
        axes[0, 1].plot(subset["frame"], subset["score"], marker="o", markersize=2.5, linewidth=1.1, label=ARMS[arm], color=colors[arm])
    axes[0, 1].set(title="External GMF score by frame", xlabel="Frame", ylabel="Score", ylim=(-4, 104))
    axes[0, 1].legend(ncol=2, fontsize=8)
    axes[0, 1].grid(alpha=.2)

    positions = np.arange(len(PRIMARY_ARMS))
    primary_summary = summary.set_index("arm").loc[list(PRIMARY_ARMS)]
    axes[1, 0].bar(positions, primary_summary["x_step_std_um"], color=[colors[arm] for arm in PRIMARY_ARMS])
    axes[1, 0].set(title="Variation of adjacent X displacement", ylabel="Standard deviation (um)", xticks=positions, xticklabels=[ARMS[arm] for arm in PRIMARY_ARMS])
    axes[1, 0].tick_params(axis="x", rotation=15)
    axes[1, 0].grid(axis="y", alpha=.2)

    pair_plot = pair_summary.set_index("arm").loc[list(PRIMARY_ARMS[1:])]
    x = np.arange(len(pair_plot))
    width = .36
    axes[1, 1].bar(x - width / 2, pair_plot["median_x_offset_vs_raw_um"], width, label="X offset", color="#2563eb")
    axes[1, 1].bar(x + width / 2, pair_plot["median_y_offset_vs_raw_um"], width, label="Y offset", color="#d97706")
    axes[1, 1].axhline(0, color="black", linewidth=.8)
    axes[1, 1].set(title="Median absolute-coordinate offset from Raw", ylabel="Offset (um)", xticks=x, xticklabels=pair_plot["label"])
    axes[1, 1].tick_params(axis="x", rotation=15)
    axes[1, 1].legend()
    axes[1, 1].grid(axis="y", alpha=.2)
    figure.suptitle("50x x_1um external GMF comparison (frame_0001 to frame_0049)", fontsize=15)
    plot_path = RESULT / "preview" / "external_gmf_analysis.png"
    figure.savefig(plot_path, dpi=160)
    plt.close(figure)

    phase_rows = fair.loc[fair["arm"] == "04_phase_safe_detail"]
    success_frames = phase_rows.loc[phase_rows["valid"], "frame"].astype(int).tolist()
    trusted_frames = phase_rows.loc[phase_rows["trusted"], "frame"].astype(int).tolist()
    detail = fair.loc[fair["arm"] == "02_detail_gate_open"].set_index("frame")
    raw_by_frame = fair.loc[fair["arm"] == "00_raw"].set_index("frame")
    detail_low = detail.loc[detail["valid"] & ~detail["trusted"]].copy()
    detail_low["x_offset_vs_raw_px"] = detail_low["x_px"] - raw_by_frame.loc[detail_low.index, "x_px"]
    payload = {
        "status": "complete",
        "calibration_um_per_px": UM_PER_PX,
        "trusted_score_threshold": TRUSTED_SCORE,
        "fair_frame_range": [1, 49],
        "data_quality": {
            "missing_arm_frame_rows": [list(item) for item in missing],
            "duplicate_arm_frame_rows": duplicates,
            "raw_reference_rows_excluded": int(tables[0]["is_reference_row"].sum()),
            "phase_safe_success_frames": success_frames,
            "phase_safe_trusted_frames": trusted_frames,
            "detail_low_score_frames": detail_low.reset_index()[["frame", "score", "x_offset_vs_raw_px"]].to_dict(orient="records"),
        },
        "arm_summary": summary.to_dict(orient="records"),
        "common_step_summary": common_summary.to_dict(orient="records"),
        "common_steps_excluded": sorted(set(range(1, 49)) - {first for first, _ in common_keys}),
        "versus_raw": pair_summary.to_dict(orient="records"),
        "claim_boundary": "Coordinate offsets assume every GMF export used the same template, ROI, calibration, and settings; the text exports do not contain configuration hashes.",
    }
    (RESULT / "external_gmf_analysis.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()

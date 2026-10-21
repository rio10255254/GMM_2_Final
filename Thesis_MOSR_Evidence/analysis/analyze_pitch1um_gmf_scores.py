"""Analyze the external GMF score files for the Pitch1um_Y_100 package."""
from __future__ import annotations

import argparse
import csv
import json
import math
import re
from pathlib import Path

import numpy as np
import matplotlib.pyplot as plt
import cv2


LINE_RE = re.compile(
    r"FileName,\s*(?P<file>[^,]+),\s*Time\(ms\),\s*(?P<time>[-+0-9.eE]+),"
    r"\s*PosX,\s*(?P<x>[-+0-9.eE]+),\s*PosY,\s*(?P<y>[-+0-9.eE]+),"
    r"\s*Angle,\s*(?P<angle>[-+0-9.eE]+),\s*Scale,\s*(?P<scale>[-+0-9.eE]+),"
    r"\s*Score0,\s*(?P<score0>[-+0-9.eE]+),\s*Score1,\s*(?P<score1>[-+0-9.eE]+),"
    r"\s*Score Diff,\s*(?P<score_diff>[-+0-9.eE]+)"
)


def finite_stats(values: np.ndarray) -> dict:
    values = np.asarray(values, dtype=np.float64)
    if values.size == 0:
        return {"count": 0}
    median = float(np.median(values))
    mad = float(np.median(np.abs(values - median)))
    return {
        "count": int(values.size),
        "mean": float(np.mean(values)),
        "median": median,
        "std": float(np.std(values, ddof=1)) if values.size > 1 else 0.0,
        "mad": mad,
        "mad_sigma": 1.4826 * mad,
        "p05": float(np.percentile(values, 5)),
        "p95": float(np.percentile(values, 95)),
        "min": float(np.min(values)),
        "max": float(np.max(values)),
    }


def line_slope(values: np.ndarray, indices: np.ndarray) -> dict:
    if values.size < 2:
        return {"slope_per_frame": 0.0, "residual_std": 0.0}
    slope, intercept = np.polyfit(indices.astype(np.float64), values.astype(np.float64), 1)
    residual = values - (slope * indices + intercept)
    return {"slope_per_frame": float(slope), "residual_std": float(np.std(residual, ddof=1))}


def parse_score_file(path: Path) -> tuple[list[dict], list[dict]]:
    rows: list[dict] = []
    errors: list[dict] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8-sig", errors="replace").splitlines(), 1):
        if not line.strip():
            continue
        match = LINE_RE.fullmatch(line.strip())
        if not match:
            errors.append({"line": line_number, "text": line})
            continue
        item = match.groupdict()
        frame_match = re.search(r"(\d+)", item["file"])
        if frame_match is None:
            errors.append({"line": line_number, "text": line, "error": "no frame index"})
            continue
        rows.append({
            "frame_name": item["file"].strip(),
            "frame_index": int(frame_match.group(1)),
            "time_ms": float(item["time"]),
            "x_px": float(item["x"]),
            "y_px": float(item["y"]),
            "angle_deg": float(item["angle"]),
            "scale": float(item["scale"]),
            "score0": float(item["score0"]),
            "score1": float(item["score1"]),
            "score_diff": float(item["score_diff"]),
        })
    rows.sort(key=lambda row: row["frame_index"])
    return rows, errors


def rows_to_arrays(rows: list[dict]) -> dict[str, np.ndarray]:
    return {key: np.asarray([row[key] for row in rows], dtype=np.float64) for key in ("frame_index", "x_px", "y_px", "scale", "score_diff")}


def arm_summary(arm: str, rows: list[dict], errors: list[dict], expected_frames: list[int], expected_dy_px: float | None) -> tuple[dict, list[dict]]:
    arrays = rows_to_arrays(rows)
    frame_indices = arrays["frame_index"].astype(int)
    duplicate_frames = sorted({int(v) for v in frame_indices if np.sum(frame_indices == v) > 1})
    missing_frames = sorted(set(expected_frames) - set(frame_indices.tolist()))
    finite = all(np.isfinite(values).all() for values in arrays.values())
    dx = np.diff(arrays["x_px"])
    dy = np.diff(arrays["y_px"])
    magnitude = np.hypot(dx, dy)
    direction_sign = -1.0 if np.median(dy) < 0 else 1.0
    step_rows = []
    for index in range(len(dx)):
        step_rows.append({
            "arm": arm,
            "from_frame": int(frame_indices[index]),
            "to_frame": int(frame_indices[index + 1]),
            "dx_px": float(dx[index]),
            "dy_px": float(dy[index]),
            "step_magnitude_px": float(magnitude[index]),
            "same_direction_as_median": bool(dy[index] * direction_sign > 0),
        })
    coordinate_indices = frame_indices.astype(np.float64)
    summary = {
        "arm": arm,
        "coordinate_rows": len(rows),
        "frame_min": int(frame_indices.min()) if len(rows) else None,
        "frame_max": int(frame_indices.max()) if len(rows) else None,
        "missing_frames_against_package_0_to_100": missing_frames,
        "duplicate_frames": duplicate_frames,
        "parse_error_count": len(errors),
        "finite": bool(finite),
        "score_diff": finite_stats(arrays["score_diff"]),
        "score_diff_below_70_count": int(np.sum(arrays["score_diff"] < 70.0)),
        "scale": finite_stats(arrays["scale"]),
        "scale_abs_error_from_1": finite_stats(np.abs(arrays["scale"] - 1.0)),
        "position": {
            "x_start_px": float(arrays["x_px"][0]),
            "x_end_px": float(arrays["x_px"][-1]),
            "y_start_px": float(arrays["y_px"][0]),
            "y_end_px": float(arrays["y_px"][-1]),
            "x_span_px": float(np.ptp(arrays["x_px"])),
            "y_span_px": float(np.ptp(arrays["y_px"])),
            "x_trend": line_slope(arrays["x_px"], coordinate_indices),
            "y_trend": line_slope(arrays["y_px"], coordinate_indices),
        },
        "steps": {
            "count": len(magnitude),
            "dx_px": finite_stats(dx),
            "dy_px": finite_stats(dy),
            "magnitude_px": finite_stats(magnitude),
            "direction_agreement_fraction": float(np.mean(dy * direction_sign > 0)) if len(dy) else 0.0,
        },
    }
    if expected_dy_px is not None:
        dy_error = dy - float(expected_dy_px)
        summary["steps"]["expected_dy_px"] = float(expected_dy_px)
        summary["steps"]["dy_error_px"] = finite_stats(dy_error)
        summary["steps"]["within_expected_tolerance_fraction"] = {
            f"{int(tolerance * 100)}pct": float(np.mean(np.abs(dy_error) <= abs(expected_dy_px) * tolerance))
            for tolerance in (0.20, 0.25, 0.30)
        }
        summary["steps"]["expected_direction_fraction"] = float(np.mean(np.sign(dy) == np.sign(expected_dy_px)))
    return summary, step_rows


def pair_summary(target: str, raw_rows: list[dict], target_rows: list[dict], raw_steps: list[dict], target_steps: list[dict]) -> dict:
    raw_by_frame = {row["frame_index"]: row for row in raw_rows}
    target_by_frame = {row["frame_index"]: row for row in target_rows}
    common_frames = sorted(set(raw_by_frame) & set(target_by_frame))
    x_offset = np.asarray([target_by_frame[i]["x_px"] - raw_by_frame[i]["x_px"] for i in common_frames], dtype=np.float64)
    y_offset = np.asarray([target_by_frame[i]["y_px"] - raw_by_frame[i]["y_px"] for i in common_frames], dtype=np.float64)
    offset_magnitude = np.hypot(x_offset, y_offset)
    raw_step_by_from = {row["from_frame"]: row for row in raw_steps}
    target_step_by_from = {row["from_frame"]: row for row in target_steps}
    common_step_starts = sorted(set(raw_step_by_from) & set(target_step_by_from))
    dx_delta = np.asarray([target_step_by_from[i]["dx_px"] - raw_step_by_from[i]["dx_px"] for i in common_step_starts], dtype=np.float64)
    dy_delta = np.asarray([target_step_by_from[i]["dy_px"] - raw_step_by_from[i]["dy_px"] for i in common_step_starts], dtype=np.float64)
    magnitude_delta = np.asarray([target_step_by_from[i]["step_magnitude_px"] - raw_step_by_from[i]["step_magnitude_px"] for i in common_step_starts], dtype=np.float64)
    vector_delta = np.hypot(dx_delta, dy_delta)
    raw_magnitude = np.asarray([raw_step_by_from[i]["step_magnitude_px"] for i in common_step_starts], dtype=np.float64)
    target_magnitude = np.asarray([target_step_by_from[i]["step_magnitude_px"] for i in common_step_starts], dtype=np.float64)
    raw_dy = np.asarray([raw_step_by_from[i]["dy_px"] for i in common_step_starts], dtype=np.float64)
    target_dy = np.asarray([target_step_by_from[i]["dy_px"] for i in common_step_starts], dtype=np.float64)
    offset_indices = np.asarray(common_frames, dtype=np.float64)
    return {
        "target": target,
        "common_coordinate_frames": len(common_frames),
        "common_step_count": len(common_step_starts),
        "coordinate_offset_target_minus_raw": {
            "x_px": finite_stats(x_offset),
            "y_px": finite_stats(y_offset),
            "magnitude_px": finite_stats(offset_magnitude),
            "x_trend": line_slope(x_offset, offset_indices),
            "y_trend": line_slope(y_offset, offset_indices),
            "endpoint_x_offset_px": float(x_offset[-1] - x_offset[0]),
            "endpoint_y_offset_px": float(y_offset[-1] - y_offset[0]),
        },
        "step_vector_difference_target_minus_raw": {
            "dx_px": finite_stats(dx_delta),
            "dy_px": finite_stats(dy_delta),
            "vector_magnitude_px": finite_stats(vector_delta),
            "step_magnitude_delta_px": finite_stats(magnitude_delta),
        },
        "stability_ratios_target_over_raw": {
            "step_magnitude_std": float(np.std(target_magnitude, ddof=1) / np.std(raw_magnitude, ddof=1)),
            "step_magnitude_mad": float(np.median(np.abs(target_magnitude - np.median(target_magnitude))) / np.median(np.abs(raw_magnitude - np.median(raw_magnitude)))),
            "dy_step_std": float(np.std(target_dy, ddof=1) / np.std(raw_dy, ddof=1)),
        },
        "score_difference_target_minus_raw": finite_stats(
            np.asarray([target_by_frame[i]["score_diff"] - raw_by_frame[i]["score_diff"] for i in common_frames], dtype=np.float64)
        ),
    }


def write_csv(path: Path, rows: list[dict]) -> None:
    if not rows:
        return
    fields = list(rows[0].keys())
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def write_plot(path: Path, parsed: dict[str, list[dict]], expected_dy_px: float | None) -> None:
    colors = {
        "pitch1um_y100_raw": "#444444",
        "pitch1um_y100_r103_e48": "#1f77b4",
        "pitch1um_y100_r104_e48": "#d62728",
    }
    labels = {
        "pitch1um_y100_raw": "Raw",
        "pitch1um_y100_r103_e48": "R103 E48",
        "pitch1um_y100_r104_e48": "R104 E48",
    }
    fig, axes = plt.subplots(3, 1, figsize=(11, 10), sharex=False, constrained_layout=True)
    for arm, rows in parsed.items():
        indices = np.asarray([row["frame_index"] for row in rows])
        y = np.asarray([row["y_px"] for row in rows])
        dy = np.diff(y)
        score = np.asarray([row["score_diff"] for row in rows])
        axes[0].plot(indices, y, label=labels[arm], color=colors[arm], linewidth=1.2)
        axes[1].plot(indices[1:], dy, label=labels[arm], color=colors[arm], linewidth=0.9, alpha=0.85)
        axes[2].plot(indices, score, label=labels[arm], color=colors[arm], linewidth=1.0)
    axes[0].set_title("GMF Y-coordinate trajectory (common coordinates frame_0001-frame_0100)")
    axes[0].set_ylabel("PosY (px)")
    axes[1].set_title("GMF adjacent Y-step")
    axes[1].set_ylabel("ΔY (px)")
    if expected_dy_px is not None:
        axes[1].axhline(expected_dy_px, color="#111111", linestyle="--", linewidth=1.0, label=f"expected {expected_dy_px:g} px")
    axes[2].set_title("GMF Score Diff")
    axes[2].set_ylabel("Score")
    axes[2].set_xlabel("GMF frame index")
    for axis in axes:
        axis.grid(alpha=0.25)
        axis.legend(loc="best")
    fig.savefig(path, dpi=180)
    plt.close(fig)


def image_parity(package: Path) -> dict:
    raw_files = sorted((package / "pitch1um_y100_raw" / "bmp").glob("frame_*.bmp"))
    result = {}
    for arm in ("pitch1um_y100_r103_e48", "pitch1um_y100_r104_e48"):
        target_files = sorted((package / arm / "bmp").glob("frame_*.bmp"))
        diffs = []
        exact = 0
        max_difference = 0
        for raw_path, target_path in zip(raw_files, target_files):
            raw = cv2.imread(str(raw_path), cv2.IMREAD_GRAYSCALE)
            target = cv2.imread(str(target_path), cv2.IMREAD_GRAYSCALE)
            if raw is None or target is None or raw.shape != target.shape:
                raise RuntimeError(f"Image parity read/shape failure: {raw_path} / {target_path}")
            difference = np.abs(raw.astype(np.int16) - target.astype(np.int16))
            diffs.append(float(np.mean(difference)))
            max_difference = max(max_difference, int(np.max(difference)))
            exact += int(np.array_equal(raw, target))
        result[arm] = {
            "paired_frames": len(diffs),
            "exact_pixel_frames": exact,
            "changed_pixel_frames": len(diffs) - exact,
            "mean_abs_change_gray_median": float(np.median(diffs)) if diffs else 0.0,
            "mean_abs_change_gray_p95": float(np.percentile(diffs, 95)) if diffs else 0.0,
            "max_uint8_difference": max_difference,
        }
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--package", type=Path, required=True)
    parser.add_argument("--expected-dy-px", type=float, default=None)
    args = parser.parse_args()
    package = args.package.resolve()
    scores_root = package / "_gmf_scores"
    arms = ["pitch1um_y100_raw", "pitch1um_y100_r103_e48", "pitch1um_y100_r104_e48"]
    expected_frames = list(range(0, 101))
    parsed: dict[str, list[dict]] = {}
    parse_errors: dict[str, list[dict]] = {}
    summaries: dict[str, dict] = {}
    step_rows: list[dict] = []
    for arm in arms:
        path = scores_root / arm / "GMF_score.txt"
        if not path.is_file():
            raise FileNotFoundError(path)
        rows, errors = parse_score_file(path)
        parsed[arm] = rows
        parse_errors[arm] = errors
        summary, steps = arm_summary(arm, rows, errors, expected_frames, args.expected_dy_px)
        summaries[arm] = summary
        step_rows.extend(steps)

    raw = arms[0]
    pairwise = [
        pair_summary(arm, parsed[raw], parsed[arm], [row for row in step_rows if row["arm"] == raw], [row for row in step_rows if row["arm"] == arm])
        for arm in arms[1:]
    ]
    pairwise.append(
        pair_summary(arms[2], parsed[arms[1]], parsed[arms[2]], [row for row in step_rows if row["arm"] == arms[1]], [row for row in step_rows if row["arm"] == arms[2]])
        | {"reference": arms[1]}
    )
    parity = image_parity(package)

    row_out = []
    for arm, rows in parsed.items():
        for row in rows:
            row_out.append({"arm": arm, **row})
    analysis_dir = package / "gmf_analysis"
    analysis_dir.mkdir(parents=True, exist_ok=True)
    write_csv(analysis_dir / "gmf_coordinate_rows.csv", row_out)
    write_csv(analysis_dir / "gmf_step_rows.csv", step_rows)
    write_csv(analysis_dir / "gmf_arm_summary.csv", [
        {"arm": arm, "coordinate_rows": summary["coordinate_rows"], "frame_min": summary["frame_min"], "frame_max": summary["frame_max"], "missing_frames": ",".join(map(str, summary["missing_frames_against_package_0_to_100"])), "parse_error_count": summary["parse_error_count"], "finite": summary["finite"], "score_median": summary["score_diff"]["median"], "score_std": summary["score_diff"]["std"], "scale_median": summary["scale"]["median"], "scale_std": summary["scale"]["std"], "step_count": summary["steps"]["count"], "step_magnitude_median_px": summary["steps"]["magnitude_px"]["median"], "step_magnitude_std_px": summary["steps"]["magnitude_px"]["std"], "dy_median_px": summary["steps"]["dy_px"]["median"], "dy_std_px": summary["steps"]["dy_px"]["std"], "dy_error_median_px": summary["steps"].get("dy_error_px", {}).get("median"), "dy_error_p95_abs_px": (float(np.percentile(np.abs(np.asarray([row["dy_px"] for row in step_rows if row["arm"] == arm], dtype=np.float64) - float(args.expected_dy_px)), 95)) if args.expected_dy_px is not None else None), "within_20pct": summary["steps"].get("within_expected_tolerance_fraction", {}).get("20pct"), "within_25pct": summary["steps"].get("within_expected_tolerance_fraction", {}).get("25pct"), "within_30pct": summary["steps"].get("within_expected_tolerance_fraction", {}).get("30pct"), "direction_agreement_fraction": summary["steps"]["direction_agreement_fraction"]}
        for arm, summary in summaries.items()
    ])
    write_csv(analysis_dir / "gmf_pairwise_summary.csv", [
        {"reference": item.get("reference", raw), "target": item["target"], "common_coordinate_frames": item["common_coordinate_frames"], "common_step_count": item["common_step_count"], "offset_x_median_px": item["coordinate_offset_target_minus_raw"]["x_px"]["median"], "offset_y_median_px": item["coordinate_offset_target_minus_raw"]["y_px"]["median"], "offset_magnitude_median_px": item["coordinate_offset_target_minus_raw"]["magnitude_px"]["median"], "offset_x_trend_px_per_frame": item["coordinate_offset_target_minus_raw"]["x_trend"]["slope_per_frame"], "offset_y_trend_px_per_frame": item["coordinate_offset_target_minus_raw"]["y_trend"]["slope_per_frame"], "step_delta_vector_median_px": item["step_vector_difference_target_minus_raw"]["vector_magnitude_px"]["median"], "step_delta_vector_p95_px": item["step_vector_difference_target_minus_raw"]["vector_magnitude_px"]["p95"], "step_magnitude_delta_median_px": item["step_vector_difference_target_minus_raw"]["step_magnitude_delta_px"]["median"], "step_magnitude_std_ratio": item["stability_ratios_target_over_raw"]["step_magnitude_std"], "step_magnitude_mad_ratio": item["stability_ratios_target_over_raw"]["step_magnitude_mad"], "dy_step_std_ratio": item["stability_ratios_target_over_raw"]["dy_step_std"], "score_delta_median": item["score_difference_target_minus_raw"]["median"]}
        for item in pairwise
    ])

    report = {
        "status": "complete",
        "package": str(package),
        "score_files": {arm: str(scores_root / arm / "GMF_score.txt") for arm in arms},
        "expected_package_frames": expected_frames,
        "arms": summaries,
        "pairwise": pairwise,
        "expected_dy_px": args.expected_dy_px,
        "image_parity": parity,
        "interpretation_rules": {
            "coordinate_unit": "GMF output pixels; no um conversion applied because no verified calibration was supplied for this package.",
            "missing_first_frame": "GMF output begins at frame_0001 for all three arms; frame_0000 is excluded from step statistics rather than imputed.",
            "stability": "Lower step spread and lower target-minus-Raw step-vector difference indicate closer displacement repeatability; Raw is the paired reference, not independent absolute stage truth.",
            "score": "Score Diff is reported descriptively; no absolute pass threshold was imposed because this package has no locked GMF threshold metadata.",
            "expected_step": "When supplied, expected_dy_px is the locked Pitch1um_Y_100 direction convention from the project sequence configuration; tolerance fractions use 20%, 25%, and 30% of its absolute magnitude.",
        },
        "parse_errors": parse_errors,
    }
    (analysis_dir / "gmf_analysis.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    plot_path = analysis_dir / "gmf_trajectory_step_score.png"
    write_plot(plot_path, parsed, args.expected_dy_px)

    def v(item: dict, path: list[str]):
        value = item
        for key in path:
            value = value[key]
        return value

    lines = [
        "# Pitch1um_Y_100 external GMF analysis",
        "",
        "## Scope",
        "",
        "The score files contain frame_0001 through frame_0100 for all three arms. The package frame_0000 coordinate is absent from the external output, so all step statistics use the common 100 coordinates and 99 consecutive steps only.",
        "",
        "Coordinates are reported in GMF pixels. No physical-unit conversion is applied because this package does not carry a verified pixel calibration.",
        "",
        "## Arm summary",
        "",
        f"Expected Y step: `{args.expected_dy_px:.3f} px`" if args.expected_dy_px is not None else "Expected Y step: not supplied",
        "",
        "| Arm | Coordinates | Missing | Score median | Scale median | Step median (px) | Step SD (px) | Y-step median (px) | Y-step SD (px) | Within 20% | Within 25% | Within 30% |",
        "|---|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for arm in arms:
        summary = summaries[arm]
        lines.append(
            f"| {arm} | {summary['coordinate_rows']} | {','.join(map(str, summary['missing_frames_against_package_0_to_100'])) or 'none'} | "
            f"{summary['score_diff']['median']:.3f} | {summary['scale']['median']:.6f} | "
            f"{summary['steps']['magnitude_px']['median']:.3f} | {summary['steps']['magnitude_px']['std']:.3f} | "
            f"{summary['steps']['dy_px']['median']:.3f} | {summary['steps']['dy_px']['std']:.3f} | "
            f"{summary['steps'].get('within_expected_tolerance_fraction', {}).get('20pct', float('nan')):.3f} | "
            f"{summary['steps'].get('within_expected_tolerance_fraction', {}).get('25pct', float('nan')):.3f} | "
            f"{summary['steps'].get('within_expected_tolerance_fraction', {}).get('30pct', float('nan')):.3f} |"
        )
    lines += ["", "## Pairwise results", "", "| Reference | Target | Median coordinate offset (px) | Offset drift slope Y (px/frame) | Median step-vector difference (px) | P95 step-vector difference (px) | Step magnitude SD ratio | Y-step SD ratio | Score median change |", "|---|---|---:|---:|---:|---:|---:|---:|---:|"]
    for item in pairwise:
        reference = item.get("reference", raw)
        lines.append(
            f"| {reference} | {item['target']} | {item['coordinate_offset_target_minus_raw']['magnitude_px']['median']:.3f} | "
            f"{item['coordinate_offset_target_minus_raw']['y_trend']['slope_per_frame']:.6f} | "
            f"{item['step_vector_difference_target_minus_raw']['vector_magnitude_px']['median']:.3f} | "
            f"{item['step_vector_difference_target_minus_raw']['vector_magnitude_px']['p95']:.3f} | "
            f"{item['stability_ratios_target_over_raw']['step_magnitude_std']:.3f} | "
            f"{item['stability_ratios_target_over_raw']['dy_step_std']:.3f} | "
            f"{item['score_difference_target_minus_raw']['median']:.3f} |"
        )
    lines += ["", "## Image parity check", "", f"- R103 E48 exact pixel-equal frames to Raw: {parity['pitch1um_y100_r103_e48']['exact_pixel_frames']}/{parity['pitch1um_y100_r103_e48']['paired_frames']}", f"- R104 E48 exact pixel-equal frames to Raw: {parity['pitch1um_y100_r104_e48']['exact_pixel_frames']}/{parity['pitch1um_y100_r104_e48']['paired_frames']}", "", "## Caveats", "", "- The missing first GMF coordinate is a file-output omission common to all three arms; it is not filled in or counted as a model failure.", "- Raw is used as the paired reference for repeatability. This tests consistency relative to Raw, not independent absolute stage truth.", "- Score Diff values are shown for diagnostics only because no locked acceptance threshold was included with this package.", "- If an arm is pixel-identical to Raw but its GMF coordinates differ, that difference is a GMF run/template/repeatability issue, not an image-reconstruction effect; rerun both arms with the same locked GMF state before attributing it to the model."]
    (analysis_dir / "GMF_ANALYSIS.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

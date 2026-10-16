from __future__ import annotations

import csv
import math
import re
from collections import defaultdict
from pathlib import Path
from statistics import mean, median, pstdev


ANALYSIS_ROOT = Path(r"D:\GMM_2_Final\20260704_20x_5x_analysis")
PACKAGE_ROOTS = [
    ANALYSIS_ROOT
    / "external_gmf_packages"
    / "gmf_20260704_20x_5x_full_sequences",
    ANALYSIS_ROOT
    / "external_gmf_packages"
    / "gmf_20260704_20x_5x_stable_segments",
]
OUT_ROOT = ANALYSIS_ROOT / "external_gmf_packages" / "external_gmf_analysis"


def parse_key_value_line(line: str) -> dict[str, str]:
    parts = [part.strip() for part in line.split(",")]
    row: dict[str, str] = {}
    for idx in range(0, len(parts) - 1, 2):
        row[parts[idx]] = parts[idx + 1]
    return row


def as_float(value: str | None) -> float:
    if value is None or value == "":
        return math.nan
    try:
        return float(value)
    except ValueError:
        return math.nan


def package_mode(package_root: Path) -> str:
    name = package_root.name.lower()
    if "stable" in name:
        return "stable_segments"
    if "full" in name:
        return "full_sequences"
    return package_root.name


def read_manifest(package_root: Path) -> list[dict[str, str]]:
    path = package_root / "case_manifest.csv"
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        rows = list(csv.DictReader(fh))
    for row in rows:
        row["package_root"] = str(package_root)
        row["package_mode"] = package_mode(package_root)
    return rows


def parse_score_file(score_file: Path, manifest_row: dict[str, str]) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for line_no, line in enumerate(
        score_file.read_text(encoding="utf-8", errors="replace").splitlines(), start=1
    ):
        if not line.strip():
            continue
        raw = parse_key_value_line(line)
        file_name = raw.get("FileName", "")
        match = re.search(r"frame_(\d+)", file_name)
        frame = int(match.group(1)) if match else None
        pos_x = as_float(raw.get("PosX"))
        pos_y = as_float(raw.get("PosY"))
        scale = as_float(raw.get("Scale"))
        score0 = as_float(raw.get("Score0"))
        success = (
            frame is not None
            and not math.isnan(pos_x)
            and not math.isnan(pos_y)
            and not math.isnan(scale)
            and scale > 0
            and not math.isnan(score0)
            and score0 > 0
            and not (pos_x == 0 and pos_y == 0)
        )
        rows.append(
            {
                "package_mode": manifest_row["package_mode"],
                "case": manifest_row["case"],
                "group": manifest_row["group"],
                "magnification": manifest_row["magnification"],
                "variant": manifest_row["variant"],
                "segment": manifest_row["segment"],
                "nominal_step_um": as_float(manifest_row.get("nominal_step_um")),
                "expected_step_px": as_float(manifest_row.get("expected_step_px")),
                "score_file": str(score_file),
                "line_no": line_no,
                "file_name": file_name,
                "frame": frame,
                "time_ms": as_float(raw.get("Time(ms)")),
                "pos_x": pos_x,
                "pos_y": pos_y,
                "angle": as_float(raw.get("Angle")),
                "scale": scale,
                "score0": score0,
                "score1": as_float(raw.get("Score1")),
                "score_diff": as_float(raw.get("Score Diff")),
                "success": success,
            }
        )
    return rows


def finite(values: list[float]) -> list[float]:
    return [value for value in values if not math.isnan(value)]


def safe_median(values: list[float]) -> float:
    vals = finite(values)
    return median(vals) if vals else math.nan


def safe_mean(values: list[float]) -> float:
    vals = finite(values)
    return mean(vals) if vals else math.nan


def safe_std(values: list[float]) -> float:
    vals = finite(values)
    return pstdev(vals) if len(vals) > 1 else math.nan


def safe_min(values: list[float]) -> float:
    vals = finite(values)
    return min(vals) if vals else math.nan


def safe_max(values: list[float]) -> float:
    vals = finite(values)
    return max(vals) if vals else math.nan


def fmt(value: object, digits: int = 4) -> str:
    if isinstance(value, bool):
        return "yes" if value else "no"
    if value is None:
        return "NA"
    try:
        number = float(value)
    except (TypeError, ValueError):
        return str(value)
    if math.isnan(number):
        return "NA"
    return f"{number:.{digits}f}"


def fmt_pct(value: object, digits: int = 1) -> str:
    text = fmt(value, digits)
    return text if text == "NA" else text + "%"


def build_steps(score_rows: list[dict[str, object]]) -> list[dict[str, object]]:
    rows_by_case: dict[str, list[dict[str, object]]] = defaultdict(list)
    for row in score_rows:
        if row["success"]:
            rows_by_case[str(row["case"])].append(row)

    steps: list[dict[str, object]] = []
    for case, case_rows in rows_by_case.items():
        by_frame = {int(row["frame"]): row for row in case_rows if row["frame"] is not None}
        for frame_b in sorted(by_frame):
            frame_a = frame_b - 1
            if frame_a not in by_frame:
                continue
            a = by_frame[frame_a]
            b = by_frame[frame_b]
            dx = float(b["pos_x"]) - float(a["pos_x"])
            dy = float(b["pos_y"]) - float(a["pos_y"])
            expected = float(a["expected_step_px"])
            plausible = (
                not math.isnan(expected)
                and 0.5 * expected <= abs(dx) <= 1.5 * expected
                and abs(dy) <= max(1.0, 0.5 * expected)
            )
            steps.append(
                {
                    "package_mode": a["package_mode"],
                    "case": case,
                    "group": a["group"],
                    "magnification": a["magnification"],
                    "variant": a["variant"],
                    "segment": a["segment"],
                    "nominal_step_um": a["nominal_step_um"],
                    "expected_step_px": expected,
                    "frame_a": frame_a,
                    "frame_b": frame_b,
                    "dx_px": dx,
                    "dy_px": dy,
                    "abs_dx_px": abs(dx),
                    "abs_dy_px": abs(dy),
                    "magnitude_px": math.hypot(dx, dy),
                    "abs_dx_minus_expected_px": abs(dx) - expected,
                    "abs_dx_error_pct": ((abs(dx) - expected) / expected * 100.0)
                    if expected and not math.isnan(expected)
                    else math.nan,
                    "plausible_x_motion_step": plausible,
                    "score0_a": a["score0"],
                    "score0_b": b["score0"],
                }
            )
    return steps


def summarize_case(
    manifest_rows: list[dict[str, str]],
    score_rows: list[dict[str, object]],
    steps: list[dict[str, object]],
) -> list[dict[str, object]]:
    scores_by_case: dict[str, list[dict[str, object]]] = defaultdict(list)
    steps_by_case: dict[str, list[dict[str, object]]] = defaultdict(list)
    for row in score_rows:
        scores_by_case[str(row["case"])].append(row)
    for step in steps:
        steps_by_case[str(step["case"])].append(step)

    summary: list[dict[str, object]] = []
    for row in manifest_rows:
        case = row["case"]
        score_file = Path(row["score_folder"]) / "GMF_score.txt"
        case_scores = scores_by_case.get(case, [])
        case_steps = steps_by_case.get(case, [])
        successful_scores = [score for score in case_scores if score["success"]]
        expected_rows = max(0, int(row["image_count"]) - 1)
        frames = [int(score["frame"]) for score in successful_scores if score["frame"] is not None]
        abs_dx = [float(step["abs_dx_px"]) for step in case_steps]
        abs_dy = [float(step["abs_dy_px"]) for step in case_steps]
        dx = [float(step["dx_px"]) for step in case_steps]
        dy = [float(step["dy_px"]) for step in case_steps]
        score0 = [float(score["score0"]) for score in successful_scores]
        scale = [float(score["scale"]) for score in successful_scores]
        expected = as_float(row.get("expected_step_px"))
        median_abs_dx = safe_median(abs_dx)
        summary.append(
            {
                "package_mode": row["package_mode"],
                "case": case,
                "group": row["group"],
                "magnification": row["magnification"],
                "variant": row["variant"],
                "segment": row["segment"],
                "nominal_step_um": as_float(row.get("nominal_step_um")),
                "expected_step_px": expected,
                "score_file_present": score_file.exists(),
                "score_rows": len(case_scores),
                "expected_score_rows": expected_rows,
                "score_row_coverage_pct": len(case_scores) / expected_rows * 100.0
                if expected_rows
                else math.nan,
                "success_rows": len(successful_scores),
                "success_rate_pct": len(successful_scores) / len(case_scores) * 100.0
                if case_scores
                else math.nan,
                "first_scored_frame": min(frames) if frames else math.nan,
                "last_scored_frame": max(frames) if frames else math.nan,
                "frame0_absent_from_gmf": bool(frames and min(frames) > int(row["first_frame"])),
                "consecutive_steps": len(case_steps),
                "plausible_steps": sum(1 for step in case_steps if step["plausible_x_motion_step"]),
                "plausible_step_rate_pct": sum(1 for step in case_steps if step["plausible_x_motion_step"])
                / len(case_steps)
                * 100.0
                if case_steps
                else math.nan,
                "median_dx_px": safe_median(dx),
                "mean_dx_px": safe_mean(dx),
                "std_dx_px": safe_std(dx),
                "median_abs_dx_px": median_abs_dx,
                "mean_abs_dx_px": safe_mean(abs_dx),
                "std_abs_dx_px": safe_std(abs_dx),
                "median_abs_dx_error_px": median_abs_dx - expected
                if not math.isnan(median_abs_dx) and not math.isnan(expected)
                else math.nan,
                "median_abs_dx_error_pct": (median_abs_dx - expected) / expected * 100.0
                if not math.isnan(median_abs_dx)
                and not math.isnan(expected)
                and expected != 0
                else math.nan,
                "median_dy_px": safe_median(dy),
                "std_dy_px": safe_std(dy),
                "median_abs_dy_px": safe_median(abs_dy),
                "mean_abs_dy_px": safe_mean(abs_dy),
                "std_abs_dy_px": safe_std(abs_dy),
                "median_score0": safe_median(score0),
                "min_score0": safe_min(score0),
                "median_scale": safe_median(scale),
                "min_scale": safe_min(scale),
                "max_scale": safe_max(scale),
            }
        )
    return summary


def compare_raw_v16(summary: list[dict[str, object]]) -> list[dict[str, object]]:
    grouped: dict[tuple[str, str, str, str], dict[str, dict[str, object]]] = defaultdict(dict)
    for row in summary:
        if not row["score_file_present"]:
            continue
        key = (
            str(row["package_mode"]),
            str(row["group"]),
            str(row["magnification"]),
            str(row["segment"]),
        )
        grouped[key][str(row["variant"])] = row

    comparisons: list[dict[str, object]] = []
    for (mode, group, magnification, segment), pair in sorted(grouped.items()):
        if "raw" not in pair or "v16" not in pair:
            continue
        raw = pair["raw"]
        v16 = pair["v16"]
        raw_std = float(raw["std_abs_dx_px"])
        v16_std = float(v16["std_abs_dx_px"])
        raw_err = abs(float(raw["median_abs_dx_error_px"]))
        v16_err = abs(float(v16["median_abs_dx_error_px"]))
        comparisons.append(
            {
                "package_mode": mode,
                "group": group,
                "magnification": magnification,
                "segment": segment,
                "nominal_step_um": raw["nominal_step_um"],
                "expected_step_px": raw["expected_step_px"],
                "raw_success_rate_pct": raw["success_rate_pct"],
                "v16_success_rate_pct": v16["success_rate_pct"],
                "raw_consecutive_steps": raw["consecutive_steps"],
                "v16_consecutive_steps": v16["consecutive_steps"],
                "raw_median_abs_dx_px": raw["median_abs_dx_px"],
                "v16_median_abs_dx_px": v16["median_abs_dx_px"],
                "raw_abs_median_error_px": raw_err,
                "v16_abs_median_error_px": v16_err,
                "v16_error_change_px": v16_err - raw_err,
                "raw_std_abs_dx_px": raw_std,
                "v16_std_abs_dx_px": v16_std,
                "v16_std_change_px": v16_std - raw_std,
                "v16_std_improvement_pct": (raw_std - v16_std) / raw_std * 100.0
                if raw_std and not math.isnan(raw_std)
                else math.nan,
                "raw_median_abs_dy_px": raw["median_abs_dy_px"],
                "v16_median_abs_dy_px": v16["median_abs_dy_px"],
                "raw_median_score0": raw["median_score0"],
                "v16_median_score0": v16["median_score0"],
                "v16_score0_change": float(v16["median_score0"]) - float(raw["median_score0"]),
            }
        )
    return comparisons


def summarize_step_filters(steps: list[dict[str, object]]) -> list[dict[str, object]]:
    grouped: dict[str, list[dict[str, object]]] = defaultdict(list)
    for step in steps:
        grouped[str(step["case"])].append(step)

    rows: list[dict[str, object]] = []
    filters = [
        ("all_steps", lambda step: True),
        ("remove_abs_dy_gt_1px", lambda step: abs(float(step["dy_px"])) <= 1.0),
        ("plausible_x_motion_only", lambda step: bool(step["plausible_x_motion_step"])),
    ]
    for case, case_steps in sorted(grouped.items()):
        for filter_name, predicate in filters:
            selected = [step for step in case_steps if predicate(step)]
            if not selected:
                continue
            abs_dx = [float(step["abs_dx_px"]) for step in selected]
            abs_dy = [float(step["abs_dy_px"]) for step in selected]
            dx = [float(step["dx_px"]) for step in selected]
            expected = float(selected[0]["expected_step_px"])
            median_abs_dx = safe_median(abs_dx)
            rows.append(
                {
                    "package_mode": selected[0]["package_mode"],
                    "case": case,
                    "group": selected[0]["group"],
                    "magnification": selected[0]["magnification"],
                    "variant": selected[0]["variant"],
                    "segment": selected[0]["segment"],
                    "filter": filter_name,
                    "step_count": len(selected),
                    "expected_step_px": expected,
                    "median_dx_px": safe_median(dx),
                    "median_abs_dx_px": median_abs_dx,
                    "std_abs_dx_px": safe_std(abs_dx),
                    "median_abs_dx_error_px": median_abs_dx - expected,
                    "median_abs_dx_error_pct": (median_abs_dx - expected) / expected * 100.0
                    if expected
                    else math.nan,
                    "median_abs_dy_px": safe_median(abs_dy),
                    "std_abs_dy_px": safe_std(abs_dy),
                }
            )
    return rows


def find_anomalous_steps(steps: list[dict[str, object]]) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for step in steps:
        expected = float(step["expected_step_px"])
        abs_dx_error = abs(float(step["abs_dx_px"]) - expected)
        abs_dy = abs(float(step["dy_px"]))
        if (
            not bool(step["plausible_x_motion_step"])
            or abs_dy > 1.0
            or abs_dx_error > 0.5
        ):
            row = dict(step)
            row["abs_dx_error_px"] = abs_dx_error
            row["large_y_step"] = abs_dy > 1.0
            rows.append(row)
    rows.sort(
        key=lambda row: (
            str(row["group"]),
            str(row["variant"]),
            -abs(float(row["abs_dx_error_px"])),
            int(row["frame_b"]),
        )
    )
    return rows


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames: list[str] = []
    for row in rows:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(key)
    with path.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def make_plots(summary: list[dict[str, object]], steps: list[dict[str, object]], out_root: Path) -> None:
    try:
        import matplotlib.pyplot as plt
    except Exception as exc:
        (out_root / "plot_error.txt").write_text(str(exc), encoding="utf-8")
        return

    full_20x = [
        row
        for row in summary
        if row["package_mode"] == "full_sequences"
        and row["magnification"] == "20x"
        and row["score_file_present"]
    ]
    if full_20x:
        labels = [f"{row['group']}\n{row['variant']}" for row in full_20x]
        medians = [float(row["median_abs_dx_px"]) for row in full_20x]
        errors = [float(row["std_abs_dx_px"]) for row in full_20x]
        colors = ["#d74c4c" if row["variant"] == "raw" else "#3569d4" for row in full_20x]
        plt.figure(figsize=(9, 5), dpi=160)
        bars = plt.bar(labels, medians, yerr=errors, capsize=4, color=colors)
        for row in full_20x:
            plt.axhline(float(row["expected_step_px"]), color="#777777", linestyle="--", linewidth=0.8)
        plt.ylabel("Median |dx| per step (px)")
        plt.title("External GMF 20x displacement summary")
        for bar, med in zip(bars, medians):
            plt.text(bar.get_x() + bar.get_width() / 2, bar.get_height(), f"{med:.3f}", ha="center", va="bottom")
        plt.tight_layout()
        plt.savefig(out_root / "external_gmf_20x_summary.png")
        plt.close()

    full_20x_steps = [
        step
        for step in steps
        if step["package_mode"] == "full_sequences" and step["magnification"] == "20x"
    ]
    groups = sorted({str(step["group"]) for step in full_20x_steps})
    if groups:
        fig, axes = plt.subplots(len(groups), 1, figsize=(9, 4.2 * len(groups)), dpi=160, squeeze=False)
        for ax, group in zip(axes[:, 0], groups):
            group_steps = [step for step in full_20x_steps if step["group"] == group]
            expected = float(group_steps[0]["expected_step_px"]) if group_steps else math.nan
            for variant, color, marker in [("raw", "#d74c4c", "s"), ("v16", "#3569d4", "o")]:
                variant_steps = [step for step in group_steps if step["variant"] == variant]
                xs = [int(step["frame_b"]) for step in variant_steps]
                ys = [float(step["abs_dx_px"]) for step in variant_steps]
                if xs:
                    ax.plot(xs, ys, marker=marker, markersize=3, linewidth=1.2, color=color, label=variant)
            if not math.isnan(expected):
                ax.axhline(expected, color="#333333", linestyle="--", linewidth=0.9, label="expected")
            ax.set_title(f"{group}: external GMF consecutive |dx|")
            ax.set_xlabel("Frame index")
            ax.set_ylabel("|dx| (px)")
            ax.grid(True, alpha=0.25)
            ax.legend()
        fig.tight_layout()
        fig.savefig(out_root / "external_gmf_20x_step_traces.png")
        plt.close(fig)


def write_report(
    manifest_rows: list[dict[str, str]],
    summary: list[dict[str, object]],
    comparisons: list[dict[str, object]],
    sensitivity: list[dict[str, object]],
    anomalies: list[dict[str, object]],
    out_root: Path,
) -> None:
    scored_cases = [row for row in summary if row["score_file_present"]]
    missing_cases = [row for row in summary if not row["score_file_present"]]
    lines: list[str] = []
    lines.append("# External GMF Readout - 20260704 20x/5x Package")
    lines.append("")
    lines.append("## What Was Found")
    lines.append("")
    lines.append(f"- Manifest cases: {len(manifest_rows)}")
    lines.append(f"- Cases with returned GMF_score.txt: {len(scored_cases)}")
    lines.append(f"- Cases without returned score file: {len(missing_cases)}")
    lines.append(
        "- Important: the returned 20x files start at frame_0001, so the frame_0000 to frame_0001 interval is not available from external GMF."
    )
    lines.append("")
    lines.append("## Returned Score Summary")
    lines.append("")
    lines.append(
        "| Case | Success rows | Step count | Expected px | Median abs(dx) px | Std abs(dx) px | Median abs(dy) px | Median score |"
    )
    lines.append("|---|---:|---:|---:|---:|---:|---:|---:|")
    for row in scored_cases:
        lines.append(
            "| "
            + " | ".join(
                [
                    str(row["case"]),
                    f"{int(row['success_rows'])}/{int(row['score_rows'])} ({fmt_pct(row['success_rate_pct'])})",
                    str(int(row["consecutive_steps"])),
                    fmt(row["expected_step_px"]),
                    fmt(row["median_abs_dx_px"]),
                    fmt(row["std_abs_dx_px"]),
                    fmt(row["median_abs_dy_px"]),
                    fmt(row["median_score0"]),
                ]
            )
            + " |"
        )
    lines.append("")
    lines.append("## Raw vs R61 v16 Comparison")
    lines.append("")
    lines.append(
        "| Group | Expected px | Raw median abs(dx) | R61 median abs(dx) | Raw std | R61 std | Std improvement | Raw median score | R61 median score |"
    )
    lines.append("|---|---:|---:|---:|---:|---:|---:|---:|---:|")
    for row in comparisons:
        lines.append(
            "| "
            + " | ".join(
                [
                    str(row["group"]),
                    fmt(row["expected_step_px"]),
                    fmt(row["raw_median_abs_dx_px"]),
                    fmt(row["v16_median_abs_dx_px"]),
                    fmt(row["raw_std_abs_dx_px"]),
                    fmt(row["v16_std_abs_dx_px"]),
                    fmt_pct(row["v16_std_improvement_pct"]),
                    fmt(row["raw_median_score0"]),
                    fmt(row["v16_median_score0"]),
                ]
            )
            + " |"
        )
    lines.append("")
    lines.append("## Sensitivity Check")
    lines.append("")
    lines.append(
        "| Case | Filter | Step count | Median abs(dx) px | Std abs(dx) px | Median abs(dy) px |"
    )
    lines.append("|---|---|---:|---:|---:|---:|")
    for row in sensitivity:
        if row["case"] not in {scored["case"] for scored in scored_cases}:
            continue
        lines.append(
            "| "
            + " | ".join(
                [
                    str(row["case"]),
                    str(row["filter"]),
                    str(int(row["step_count"])),
                    fmt(row["median_abs_dx_px"]),
                    fmt(row["std_abs_dx_px"]),
                    fmt(row["median_abs_dy_px"]),
                ]
            )
            + " |"
        )
    lines.append("")
    lines.append("## Main Anomalous Steps")
    lines.append("")
    if anomalies:
        lines.append("| Case | Frame step | dx px | dy px | abs(dx) error px | Reason |")
        lines.append("|---|---:|---:|---:|---:|---|")
        for row in anomalies[:20]:
            reasons = []
            if not bool(row["plausible_x_motion_step"]):
                reasons.append("not plausible x step")
            if bool(row["large_y_step"]):
                reasons.append("large y step")
            if float(row["abs_dx_error_px"]) > 0.5:
                reasons.append("large x error")
            lines.append(
                "| "
                + " | ".join(
                    [
                        str(row["case"]),
                        f"{int(row['frame_a'])}->{int(row['frame_b'])}",
                        fmt(row["dx_px"]),
                        fmt(row["dy_px"]),
                        fmt(row["abs_dx_error_px"]),
                        ", ".join(reasons),
                    ]
                )
                + " |"
            )
    else:
        lines.append("- None")
    lines.append("")
    lines.append("## Missing Returned Scores")
    lines.append("")
    if missing_cases:
        for row in missing_cases:
            lines.append(f"- {row['case']}")
    else:
        lines.append("- None")
    lines.append("")
    lines.append("## Output Files")
    lines.append("")
    lines.append("- external_gmf_rows.csv: parsed GMF positions")
    lines.append("- external_gmf_consecutive_steps.csv: frame-to-frame displacement table")
    lines.append("- external_gmf_summary.csv: per-case readout")
    lines.append("- external_gmf_raw_vs_v16_comparison.csv: Raw/R61 comparison")
    lines.append("- external_gmf_sensitivity_summary.csv: same metrics after removing obvious large-y jumps")
    lines.append("- external_gmf_anomalous_steps.csv: steps that deserve manual inspection")
    lines.append("- external_gmf_20x_step_traces.png: displacement trace plot")
    lines.append("- external_gmf_20x_summary.png: median displacement summary plot")
    lines.append("")
    (out_root / "EXTERNAL_GMF_READOUT.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    OUT_ROOT.mkdir(parents=True, exist_ok=True)
    manifest_rows: list[dict[str, str]] = []
    for root in PACKAGE_ROOTS:
        manifest_rows.extend(read_manifest(root))

    score_rows: list[dict[str, object]] = []
    for row in manifest_rows:
        score_file = Path(row["score_folder"]) / "GMF_score.txt"
        if score_file.exists():
            score_rows.extend(parse_score_file(score_file, row))

    steps = build_steps(score_rows)
    summary = summarize_case(manifest_rows, score_rows, steps)
    comparisons = compare_raw_v16(summary)
    sensitivity = summarize_step_filters(steps)
    anomalies = find_anomalous_steps(steps)

    write_csv(OUT_ROOT / "external_gmf_rows.csv", score_rows)
    write_csv(OUT_ROOT / "external_gmf_consecutive_steps.csv", steps)
    write_csv(OUT_ROOT / "external_gmf_summary.csv", summary)
    write_csv(OUT_ROOT / "external_gmf_raw_vs_v16_comparison.csv", comparisons)
    write_csv(OUT_ROOT / "external_gmf_sensitivity_summary.csv", sensitivity)
    write_csv(OUT_ROOT / "external_gmf_anomalous_steps.csv", anomalies)
    make_plots(summary, steps, OUT_ROOT)
    write_report(manifest_rows, summary, comparisons, sensitivity, anomalies, OUT_ROOT)

    print(f"Wrote analysis to {OUT_ROOT}")
    print(f"Scored cases: {sum(1 for row in summary if row['score_file_present'])}")
    print(f"Missing cases: {sum(1 for row in summary if not row['score_file_present'])}")
    print(f"Step rows: {len(steps)}")
    print(f"Anomalous step rows: {len(anomalies)}")


if __name__ == "__main__":
    main()

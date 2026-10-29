from __future__ import annotations

import csv
import math
from collections import defaultdict
from pathlib import Path
from statistics import mean, median, pstdev
PROJECT_ROOT = Path(__file__).resolve().parents[3]


ANALYSIS_DIR = Path(
    str(PROJECT_ROOT / 'Analyses/20260704_20x_5x_analysis/external_gmf_packages/external_gmf_analysis')
)
STEPS_CSV = ANALYSIS_DIR / "external_gmf_consecutive_steps.csv"

CAMERA_PIXEL_UM = 3.45
OBJECTIVE_MAGNIFICATION = 20.0
OBJECT_PLANE_PIXEL_UM = CAMERA_PIXEL_UM / OBJECTIVE_MAGNIFICATION

# These are diagnostic gates, not a formal score. The main gate requires the
# same physical step to pass in both Raw and R61 before comparing them.
CRITERIA = [
    {
        "criterion": "perfect_main_0p15dx_0p25dy",
        "abs_dx_error_px_max": 0.15,
        "abs_dy_px_max": 0.25,
        "note": "main strict gate; about 26 nm x-error and 43 nm y-drift at the sample plane",
    },
    {
        "criterion": "very_strict_0p10dx_0p20dy",
        "abs_dx_error_px_max": 0.10,
        "abs_dy_px_max": 0.20,
        "note": "stricter sensitivity gate",
    },
    {
        "criterion": "moderate_0p20dx_0p25dy",
        "abs_dx_error_px_max": 0.20,
        "abs_dy_px_max": 0.25,
        "note": "slightly looser sensitivity gate",
    },
]


def as_float(value: str) -> float:
    try:
        return float(value)
    except ValueError:
        return math.nan


def safe_median(values: list[float]) -> float:
    vals = [v for v in values if not math.isnan(v)]
    return median(vals) if vals else math.nan


def safe_mean(values: list[float]) -> float:
    vals = [v for v in values if not math.isnan(v)]
    return mean(vals) if vals else math.nan


def safe_std(values: list[float]) -> float:
    vals = [v for v in values if not math.isnan(v)]
    return pstdev(vals) if len(vals) > 1 else math.nan


def fmt(value: object, digits: int = 4) -> str:
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


def read_steps() -> list[dict[str, object]]:
    with STEPS_CSV.open("r", encoding="utf-8-sig", newline="") as fh:
        rows = list(csv.DictReader(fh))
    parsed: list[dict[str, object]] = []
    for row in rows:
        if row["magnification"] != "20x":
            continue
        parsed.append(
            {
                **row,
                "frame_a": int(row["frame_a"]),
                "frame_b": int(row["frame_b"]),
                "nominal_step_um": as_float(row["nominal_step_um"]),
                "expected_step_px": as_float(row["expected_step_px"]),
                "dx_px": as_float(row["dx_px"]),
                "dy_px": as_float(row["dy_px"]),
                "abs_dx_px": as_float(row["abs_dx_px"]),
                "abs_dy_px": as_float(row["abs_dy_px"]),
            }
        )
    return parsed


def passes(step: dict[str, object], criterion: dict[str, object]) -> bool:
    expected = float(step["expected_step_px"])
    abs_dx_error = abs(float(step["abs_dx_px"]) - expected)
    abs_dy = abs(float(step["dy_px"]))
    return (
        abs_dx_error <= float(criterion["abs_dx_error_px_max"])
        and abs_dy <= float(criterion["abs_dy_px_max"])
    )


def summarize_steps(
    selected: list[dict[str, object]],
    total_steps: int,
    criterion: dict[str, object],
    group: str,
    variant: str,
    selection_mode: str,
) -> dict[str, object]:
    expected = float(selected[0]["expected_step_px"]) if selected else math.nan
    abs_dx = [float(step["abs_dx_px"]) for step in selected]
    abs_dy = [abs(float(step["dy_px"])) for step in selected]
    dx_error_px = [float(step["abs_dx_px"]) - float(step["expected_step_px"]) for step in selected]
    median_abs_dx = safe_median(abs_dx)
    median_error_px = median_abs_dx - expected if selected else math.nan
    return {
        "criterion": criterion["criterion"],
        "selection_mode": selection_mode,
        "group": group,
        "variant": variant,
        "selected_steps": len(selected),
        "total_steps": total_steps,
        "selected_rate_pct": len(selected) / total_steps * 100.0 if total_steps else math.nan,
        "expected_step_px": expected,
        "expected_step_um": expected * OBJECT_PLANE_PIXEL_UM if selected else math.nan,
        "median_abs_dx_px": median_abs_dx,
        "mean_abs_dx_px": safe_mean(abs_dx),
        "std_abs_dx_px": safe_std(abs_dx),
        "median_abs_dx_error_px": median_error_px,
        "median_abs_dx_error_nm": median_error_px * OBJECT_PLANE_PIXEL_UM * 1000.0
        if selected
        else math.nan,
        "std_abs_dx_nm": safe_std(abs_dx) * OBJECT_PLANE_PIXEL_UM * 1000.0
        if selected
        else math.nan,
        "median_abs_dy_px": safe_median(abs_dy),
        "std_abs_dy_px": safe_std(abs_dy),
        "median_abs_dy_nm": safe_median(abs_dy) * OBJECT_PLANE_PIXEL_UM * 1000.0
        if selected
        else math.nan,
        "mean_signed_dx_error_px": safe_mean(dx_error_px),
        "criterion_abs_dx_error_px_max": criterion["abs_dx_error_px_max"],
        "criterion_abs_dy_px_max": criterion["abs_dy_px_max"],
        "criterion_note": criterion["note"],
    }


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    fieldnames: list[str] = []
    for row in rows:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(key)
    with path.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def make_plot(summary_rows: list[dict[str, object]]) -> None:
    try:
        import matplotlib.pyplot as plt
    except Exception as exc:
        (ANALYSIS_DIR / "perfect_step_plot_error.txt").write_text(str(exc), encoding="utf-8")
        return

    rows = [
        row
        for row in summary_rows
        if row["criterion"] == "perfect_main_0p15dx_0p25dy"
        and row["selection_mode"] == "common_physical_steps"
    ]
    if not rows:
        return
    labels = [f"{row['group']}\n{row['variant']}" for row in rows]
    values = [float(row["median_abs_dx_px"]) for row in rows]
    errors = [float(row["std_abs_dx_px"]) for row in rows]
    colors = ["#d74c4c" if row["variant"] == "raw" else "#3569d4" for row in rows]
    plt.figure(figsize=(9, 5), dpi=160)
    bars = plt.bar(labels, values, yerr=errors, color=colors, capsize=4)
    for row in rows:
        plt.axhline(float(row["expected_step_px"]), color="#777777", linestyle="--", linewidth=0.8)
    for bar, value in zip(bars, values):
        plt.text(bar.get_x() + bar.get_width() / 2, value, f"{value:.3f}", ha="center", va="bottom")
    plt.ylabel("Median abs(dx) per perfect step (px)")
    plt.title("20x external GMF, common perfect physical steps only")
    plt.tight_layout()
    plt.savefig(ANALYSIS_DIR / "external_gmf_20x_perfect_steps_summary.png")
    plt.close()


def write_report(summary_rows: list[dict[str, object]], common_rows: list[dict[str, object]]) -> None:
    main_rows = [
        row
        for row in summary_rows
        if row["criterion"] == "perfect_main_0p15dx_0p25dy"
        and row["selection_mode"] == "common_physical_steps"
    ]
    lines: list[str] = []
    lines.append("# 20x Perfect-Step External GMF Readout")
    lines.append("")
    lines.append("## Calibration Used")
    lines.append("")
    lines.append(f"- Camera pixel size: {CAMERA_PIXEL_UM:.2f} um")
    lines.append(f"- Objective magnification: {OBJECTIVE_MAGNIFICATION:.1f}x")
    lines.append(f"- Object-plane pixel size: {OBJECT_PLANE_PIXEL_UM:.4f} um/px")
    lines.append("- Expected 1.0 um step: 5.7971 px")
    lines.append("- Expected 0.5 um step: 2.8986 px")
    lines.append("")
    lines.append("## Main Gate")
    lines.append("")
    lines.append(
        "- A physical step is counted only if the same frame interval passes in both Raw and R61."
    )
    lines.append(
        "- Main perfect-step gate: abs(dx error) <= 0.15 px and abs(dy) <= 0.25 px."
    )
    lines.append("")
    lines.append("## Main Result, Common Perfect Physical Steps")
    lines.append("")
    lines.append(
        "| Group | Variant | Selected steps | Expected px | Median abs(dx) px | Error nm | Std nm | Median abs(dy) nm |"
    )
    lines.append("|---|---|---:|---:|---:|---:|---:|---:|")
    for row in main_rows:
        lines.append(
            "| "
            + " | ".join(
                [
                    str(row["group"]),
                    str(row["variant"]),
                    f"{int(row['selected_steps'])}/{int(row['total_steps'])}",
                    fmt(row["expected_step_px"], 4),
                    fmt(row["median_abs_dx_px"], 4),
                    fmt(row["median_abs_dx_error_nm"], 2),
                    fmt(row["std_abs_dx_nm"], 2),
                    fmt(row["median_abs_dy_nm"], 2),
                ]
            )
            + " |"
        )
    lines.append("")
    lines.append("## Common Step Indices")
    lines.append("")
    for group in sorted({row["group"] for row in common_rows if row["criterion"] == "perfect_main_0p15dx_0p25dy"}):
        frames = [
            f"{row['frame_a']}->{row['frame_b']}"
            for row in common_rows
            if row["criterion"] == "perfect_main_0p15dx_0p25dy" and row["group"] == group
        ]
        lines.append(f"- {group}: {len(frames)} common steps")
        lines.append("  " + ", ".join(frames))
    lines.append("")
    lines.append("## Sensitivity Gates")
    lines.append("")
    lines.append(
        "The CSV includes stricter and looser gates so this diagnostic is not tied to one arbitrary threshold."
    )
    lines.append("")
    lines.append("## Output Files")
    lines.append("")
    lines.append("- external_gmf_perfect_step_summary.csv")
    lines.append("- external_gmf_perfect_common_steps.csv")
    lines.append("- external_gmf_20x_perfect_steps_summary.png")
    (ANALYSIS_DIR / "PERFECT_STEP_READOUT.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    steps = read_steps()
    grouped: dict[tuple[str, str], list[dict[str, object]]] = defaultdict(list)
    for step in steps:
        grouped[(str(step["group"]), str(step["variant"]))].append(step)

    summary_rows: list[dict[str, object]] = []
    common_rows: list[dict[str, object]] = []
    for criterion in CRITERIA:
        for group in sorted({key[0] for key in grouped}):
            raw_steps = grouped[(group, "raw")]
            v16_steps = grouped[(group, "v16")]
            raw_pass = [step for step in raw_steps if passes(step, criterion)]
            v16_pass = [step for step in v16_steps if passes(step, criterion)]
            for variant, selected, total in [
                ("raw", raw_pass, len(raw_steps)),
                ("v16", v16_pass, len(v16_steps)),
            ]:
                summary_rows.append(
                    summarize_steps(selected, total, criterion, group, variant, "independent_pass")
                )

            common_frames = {
                (int(step["frame_a"]), int(step["frame_b"])) for step in raw_pass
            } & {(int(step["frame_a"]), int(step["frame_b"])) for step in v16_pass}
            for frame_a, frame_b in sorted(common_frames):
                common_rows.append(
                    {
                        "criterion": criterion["criterion"],
                        "group": group,
                        "frame_a": frame_a,
                        "frame_b": frame_b,
                    }
                )
            for variant, all_steps in [("raw", raw_steps), ("v16", v16_steps)]:
                selected = [
                    step
                    for step in all_steps
                    if (int(step["frame_a"]), int(step["frame_b"])) in common_frames
                ]
                summary_rows.append(
                    summarize_steps(
                        selected,
                        len(all_steps),
                        criterion,
                        group,
                        variant,
                        "common_physical_steps",
                    )
                )

    write_csv(ANALYSIS_DIR / "external_gmf_perfect_step_summary.csv", summary_rows)
    write_csv(ANALYSIS_DIR / "external_gmf_perfect_common_steps.csv", common_rows)
    make_plot(summary_rows)
    write_report(summary_rows, common_rows)
    print(f"Wrote perfect-step analysis to {ANALYSIS_DIR}")
    print(f"Summary rows: {len(summary_rows)}")
    print(f"Common frame rows: {len(common_rows)}")


if __name__ == "__main__":
    main()

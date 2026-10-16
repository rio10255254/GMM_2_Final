from __future__ import annotations

import csv
import json
import math
import re
from collections import defaultdict
from pathlib import Path
from statistics import mean, median, pstdev


ANALYSIS_ROOT = Path(r"D:\GMM_2_Final\20260702_100MG_displacement_analysis")
PACKAGE_ROOTS = [
    Path(
        r"D:\GMM_2_Final\20260702_100MG_displacement_analysis\external_gmf_packages\gmf_20260702_100mg_x_motion_full_sequences"
    ),
    Path(
        r"D:\GMM_2_Final\20260702_100MG_displacement_analysis\external_gmf_packages\gmf_20260702_100mg_x_motion_stable_segments"
    ),
]
OUT_ROOT = ANALYSIS_ROOT / "external_gmf_packages" / "external_gmf_analysis"

# Expected motion in image pixels, measured from the same capture with the local
# dark-pattern phase-correlation method. External GMF is judged against this only
# as a plausibility guard, not as a calibration correction.
EXPECTED_STEP_PX = {
    "x_1um": 14.6,
    "x_0p5um": 7.25,
}


def parse_key_value_line(line: str) -> dict[str, str]:
    parts = [p.strip() for p in line.split(",")]
    row: dict[str, str] = {}
    for i in range(0, len(parts) - 1, 2):
        row[parts[i]] = parts[i + 1]
    return row


def as_float(value: str | None) -> float:
    if value is None or value == "":
        return math.nan
    try:
        return float(value)
    except ValueError:
        return math.nan


def parse_score_file(score_file: Path, case: str) -> list[dict[str, object]]:
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
        score1 = as_float(raw.get("Score1"))
        score_diff = as_float(raw.get("Score Diff"))
        success = (
            not math.isnan(score0)
            and score0 > 0
            and not math.isnan(scale)
            and scale > 0
            and not (pos_x == 0 and pos_y == 0)
        )
        rows.append(
            {
                "case": case,
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
                "score1": score1,
                "score_diff": score_diff,
                "success": success,
            }
        )
    return rows


def read_case_manifest(package_root: Path) -> list[dict[str, str]]:
    manifest = package_root / "case_manifest.csv"
    if not manifest.exists():
        return []
    with manifest.open("r", encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


def write_csv(path: Path, rows: list[dict[str, object]], fieldnames: list[str] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if fieldnames is None:
        keys: list[str] = []
        for row in rows:
            for key in row:
                if key not in keys:
                    keys.append(key)
        fieldnames = keys
    with path.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def safe_median(values: list[float]) -> float:
    return median(values) if values else math.nan


def safe_mean(values: list[float]) -> float:
    return mean(values) if values else math.nan


def safe_std(values: list[float]) -> float:
    return pstdev(values) if len(values) > 1 else math.nan


def fmt(value: object, digits: int = 3) -> str:
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


def build_steps(rows: list[dict[str, object]], dataset: str) -> list[dict[str, object]]:
    expected_px = EXPECTED_STEP_PX.get(dataset, math.nan)
    by_frame = {
        int(row["frame"]): row
        for row in rows
        if row.get("success") and row.get("frame") is not None
    }
    steps: list[dict[str, object]] = []
    for frame_b in sorted(by_frame):
        frame_a = frame_b - 1
        if frame_a not in by_frame:
            continue
        a = by_frame[frame_a]
        b = by_frame[frame_b]
        dx = float(b["pos_x"]) - float(a["pos_x"])
        dy = float(b["pos_y"]) - float(a["pos_y"])
        mag = math.hypot(dx, dy)
        if math.isnan(expected_px):
            plausible = False
        else:
            plausible = (
                0.6 * expected_px <= abs(dx) <= 1.6 * expected_px
                and abs(dy) <= 0.8 * expected_px
            )
        steps.append(
            {
                "case": a["case"],
                "dataset": dataset,
                "frame_a": frame_a,
                "frame_b": frame_b,
                "dx_px": dx,
                "dy_px": dy,
                "magnitude_px": mag,
                "expected_step_px": expected_px,
                "plausible_x_motion_step": plausible,
                "score0_a": a["score0"],
                "score0_b": b["score0"],
            }
        )
    return steps


def make_plots(summary_rows: list[dict[str, object]], steps: list[dict[str, object]], out_root: Path) -> None:
    try:
        import matplotlib.pyplot as plt
    except Exception as exc:
        (out_root / "plot_error.txt").write_text(str(exc), encoding="utf-8")
        return

    full_rows = [r for r in summary_rows if r.get("package_mode") == "full_sequences"]
    if full_rows:
        labels = [f"{r['dataset']}\n{r['variant']}" for r in full_rows]
        rates = [float(r["success_rate_pct"]) for r in full_rows]
        colors = ["#d34b4b" if r["variant"] == "raw" else "#3366cc" for r in full_rows]
        plt.figure(figsize=(8.5, 4.8), dpi=160)
        bars = plt.bar(labels, rates, color=colors)
        plt.ylabel("Successful GMF rows (%)")
        plt.title("External GMF success rate")
        plt.ylim(0, max(45, max(rates) * 1.25))
        for bar, rate in zip(bars, rates):
            plt.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 1, f"{rate:.1f}%", ha="center")
        plt.tight_layout()
        plt.savefig(out_root / "external_gmf_success_rate.png")
        plt.close()

    if steps:
        plt.figure(figsize=(8.5, 4.8), dpi=160)
        grouped: dict[str, list[dict[str, object]]] = defaultdict(list)
        for step in steps:
            grouped[str(step["case"])].append(step)
        for case, case_steps in sorted(grouped.items()):
            xs = [int(s["frame_b"]) for s in case_steps]
            ys = [float(s["dx_px"]) for s in case_steps]
            marker = "o" if "r61" in case else "s"
            plt.plot(xs, ys, marker=marker, linewidth=1.2, label=case)
        for dataset, expected in EXPECTED_STEP_PX.items():
            if any(s["dataset"] == dataset for s in steps):
                plt.axhline(expected, color="#999999", linestyle="--", linewidth=0.8)
                plt.axhline(-expected, color="#999999", linestyle="--", linewidth=0.8)
        plt.xlabel("Frame index")
        plt.ylabel("Consecutive successful-step dx (px)")
        plt.title("External GMF consecutive successful positions")
        plt.legend(fontsize=7)
        plt.tight_layout()
        plt.savefig(out_root / "external_gmf_consecutive_dx.png")
        plt.close()


def build_stability_summary(steps: list[dict[str, object]]) -> list[dict[str, object]]:
    grouped: dict[str, list[dict[str, object]]] = defaultdict(list)
    for step in steps:
        grouped[str(step["case"])].append(step)

    stability_rows: list[dict[str, object]] = []
    for case, case_steps in sorted(grouped.items()):
        if not case_steps:
            continue
        dataset = str(case_steps[0]["dataset"])
        variant = "v16" if "r61" in case else "raw"
        nominal_step_um = 1.0 if dataset == "x_1um" else 0.5 if dataset == "x_0p5um" else math.nan
        filters = [
            ("all_steps", case_steps),
            ("plausible_only", [s for s in case_steps if s["plausible_x_motion_step"]]),
        ]
        for filter_name, selected_steps in filters:
            if not selected_steps:
                continue
            dx_values = [float(s["dx_px"]) for s in selected_steps]
            abs_dx_values = [abs(v) for v in dx_values]
            abs_dy_values = [abs(float(s["dy_px"])) for s in selected_steps]
            stability_rows.append(
                {
                    "case": case,
                    "dataset": dataset,
                    "variant": variant,
                    "nominal_step_um": nominal_step_um,
                    "filter": filter_name,
                    "step_count": len(selected_steps),
                    "median_abs_dx_px": safe_median(abs_dx_values),
                    "mean_abs_dx_px": safe_mean(abs_dx_values),
                    "std_abs_dx_px": safe_std(abs_dx_values),
                    "median_dx_px": safe_median(dx_values),
                    "mean_dx_px": safe_mean(dx_values),
                    "std_dx_px": safe_std(dx_values),
                    "median_abs_dy_px": safe_median(abs_dy_values),
                    "mean_abs_dy_px": safe_mean(abs_dy_values),
                    "std_abs_dy_px": safe_std(abs_dy_values),
                    "outlier_steps_excluded": len(case_steps) - len(selected_steps),
                }
            )
    return stability_rows


def main() -> None:
    OUT_ROOT.mkdir(parents=True, exist_ok=True)
    all_rows: list[dict[str, object]] = []
    all_steps: list[dict[str, object]] = []
    summary_rows: list[dict[str, object]] = []
    package_status: list[dict[str, object]] = []

    for package_root in PACKAGE_ROOTS:
        mode = "full_sequences" if "full" in package_root.name else "stable_segments"
        manifest_rows = read_case_manifest(package_root)
        score_files = sorted((package_root / "_gmf_scores").rglob("GMF_score.txt"))
        package_status.append(
            {
                "package_mode": mode,
                "package_root": str(package_root),
                "manifest_cases": len(manifest_rows),
                "score_files_found": len(score_files),
            }
        )
        cases_by_name = {row["case"]: row for row in manifest_rows}
        for case_name, case_meta in cases_by_name.items():
            score_folder = Path(case_meta["score_folder"])
            case_score_files = sorted(score_folder.glob("GMF_score.txt"))
            if not case_score_files:
                summary_rows.append(
                    {
                        "package_mode": mode,
                        "case": case_name,
                        "dataset": case_meta["dataset"],
                        "variant": case_meta["variant"],
                        "nominal_step_um": float(case_meta["nominal_step_um"]),
                        "expected_image_count": int(case_meta["image_count"]),
                        "score_rows": 0,
                        "expected_score_rows": int(case_meta["image_count"]) - 1,
                        "score_file_present": False,
                        "success_rows": 0,
                        "success_rate_pct": math.nan,
                        "median_score0_success": math.nan,
                        "min_score0_success": math.nan,
                        "max_score0_success": math.nan,
                        "consecutive_success_steps": 0,
                        "plausible_x_motion_steps": 0,
                        "median_dx_px_all_consecutive_success": math.nan,
                        "std_dx_px_all_consecutive_success": math.nan,
                        "median_abs_dy_px_all_consecutive_success": math.nan,
                    }
                )
                continue

            score_file = case_score_files[0]
            rows = parse_score_file(score_file, case_name)
            for row in rows:
                row.update(
                    {
                        "package_mode": mode,
                        "dataset": case_meta["dataset"],
                        "variant": case_meta["variant"],
                        "nominal_step_um": float(case_meta["nominal_step_um"]),
                    }
                )
            all_rows.extend(rows)
            steps = build_steps(rows, case_meta["dataset"])
            all_steps.extend(steps)
            success_rows = [row for row in rows if row["success"]]
            score_values = [float(row["score0"]) for row in success_rows]
            dx_values = [float(step["dx_px"]) for step in steps]
            abs_dy_values = [abs(float(step["dy_px"])) for step in steps]
            plausible_steps = [s for s in steps if s["plausible_x_motion_step"]]
            summary_rows.append(
                {
                    "package_mode": mode,
                    "case": case_name,
                    "dataset": case_meta["dataset"],
                    "variant": case_meta["variant"],
                    "nominal_step_um": float(case_meta["nominal_step_um"]),
                    "expected_image_count": int(case_meta["image_count"]),
                    "score_rows": len(rows),
                    "expected_score_rows": int(case_meta["image_count"]) - 1,
                    "score_file_present": True,
                    "success_rows": len(success_rows),
                    "success_rate_pct": 100 * len(success_rows) / len(rows) if rows else 0.0,
                    "median_score0_success": safe_median(score_values),
                    "min_score0_success": min(score_values) if score_values else math.nan,
                    "max_score0_success": max(score_values) if score_values else math.nan,
                    "consecutive_success_steps": len(steps),
                    "plausible_x_motion_steps": len(plausible_steps),
                    "median_dx_px_all_consecutive_success": safe_median(dx_values),
                    "std_dx_px_all_consecutive_success": safe_std(dx_values),
                    "median_abs_dy_px_all_consecutive_success": safe_median(abs_dy_values),
                }
            )

    comparisons: list[dict[str, object]] = []
    by_dataset_mode: dict[tuple[str, str], dict[str, dict[str, object]]] = defaultdict(dict)
    for row in summary_rows:
        if not row.get("score_file_present"):
            continue
        by_dataset_mode[(str(row["package_mode"]), str(row["dataset"]))][str(row["variant"])] = row
    for (mode, dataset), variants in sorted(by_dataset_mode.items()):
        raw = variants.get("raw")
        v16 = variants.get("v16")
        if not raw or not v16:
            continue
        comparisons.append(
            {
                "package_mode": mode,
                "dataset": dataset,
                "nominal_step_um": raw["nominal_step_um"],
                "raw_success_rate_pct": raw["success_rate_pct"],
                "v16_success_rate_pct": v16["success_rate_pct"],
                "success_rate_gain_pct_point": float(v16["success_rate_pct"]) - float(raw["success_rate_pct"]),
                "success_rate_multiplier": (
                    float(v16["success_rate_pct"]) / float(raw["success_rate_pct"])
                    if float(raw["success_rate_pct"]) > 0
                    else math.nan
                ),
                "raw_success_rows": raw["success_rows"],
                "v16_success_rows": v16["success_rows"],
                "raw_plausible_x_motion_steps": raw["plausible_x_motion_steps"],
                "v16_plausible_x_motion_steps": v16["plausible_x_motion_steps"],
                "raw_median_score0_success": raw["median_score0_success"],
                "v16_median_score0_success": v16["median_score0_success"],
            }
        )
    stability_rows = build_stability_summary(all_steps)

    write_csv(OUT_ROOT / "external_gmf_rows.csv", all_rows)
    write_csv(OUT_ROOT / "external_gmf_consecutive_steps.csv", all_steps)
    write_csv(OUT_ROOT / "external_gmf_summary.csv", summary_rows)
    write_csv(OUT_ROOT / "external_gmf_raw_vs_v16_comparison.csv", comparisons)
    write_csv(OUT_ROOT / "external_gmf_displacement_stability_filtered.csv", stability_rows)
    write_csv(OUT_ROOT / "external_gmf_package_status.csv", package_status)
    make_plots(summary_rows, all_steps, OUT_ROOT)

    readout_lines = [
        "# External GMF Returned-Score Readout",
        "",
        "## Package Status",
        "",
        "| package | manifest cases | score files found |",
        "|---|---:|---:|",
    ]
    for row in package_status:
        readout_lines.append(
            f"| {row['package_mode']} | {row['manifest_cases']} | {row['score_files_found']} |"
        )
    readout_lines.extend(
        [
            "",
            "## Case Summary",
            "",
            "| case | rows | success rows | success rate | median successful score | consecutive success steps | plausible x-motion steps |",
            "|---|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for row in summary_rows:
        readout_lines.append(
            "| "
            + " | ".join(
                [
                    str(row["case"]),
                    str(row["score_rows"]) if row.get("score_file_present") else "missing",
                    str(row["success_rows"]) if row.get("score_file_present") else "missing",
                    fmt_pct(row["success_rate_pct"], 1),
                    fmt(row["median_score0_success"], 3),
                    str(row["consecutive_success_steps"]),
                    str(row["plausible_x_motion_steps"]),
                ]
            )
            + " |"
        )
    readout_lines.extend(
        [
            "",
            "## Raw vs R61 v16",
            "",
            "| dataset | nominal step | Raw success | v16 success | gain | multiplier | Raw plausible steps | v16 plausible steps |",
            "|---|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for row in comparisons:
        readout_lines.append(
            "| "
            + " | ".join(
                [
                    str(row["dataset"]),
                    fmt(row["nominal_step_um"], 1) + " um",
                    fmt_pct(row["raw_success_rate_pct"], 1),
                    fmt_pct(row["v16_success_rate_pct"], 1),
                    fmt(row["success_rate_gain_pct_point"], 1) + " pp",
                    fmt(row["success_rate_multiplier"], 2) + "x",
                    str(row["raw_plausible_x_motion_steps"]),
                    str(row["v16_plausible_x_motion_steps"]),
                ]
            )
            + " |"
        )
    readout_lines.extend(
        [
            "",
            "## Displacement Stability",
            "",
            "| case | filter | steps | median abs dx | std abs dx | median abs dy | excluded steps |",
            "|---|---|---:|---:|---:|---:|---:|",
        ]
    )
    for row in stability_rows:
        readout_lines.append(
            "| "
            + " | ".join(
                [
                    str(row["case"]),
                    str(row["filter"]),
                    str(row["step_count"]),
                    fmt(row["median_abs_dx_px"], 4),
                    fmt(row["std_abs_dx_px"], 4),
                    fmt(row["median_abs_dy_px"], 4),
                    str(row["outlier_steps_excluded"]),
                ]
            )
            + " |"
        )
    readout_lines.extend(
        [
            "",
            "## Interpretation Guard",
            "",
            "- A row is counted as a successful GMF row only when Score0, scale, and position are non-zero.",
            "- A plausible x-motion step requires two adjacent frames to both be successful and the x shift to match the expected direction/magnitude band.",
            "- The stable-segment package is reported separately because it needs its own returned score files.",
        ]
    )
    (OUT_ROOT / "EXTERNAL_GMF_READOUT.md").write_text("\n".join(readout_lines) + "\n", encoding="utf-8")

    summary_json = {
        "out_root": str(OUT_ROOT),
        "package_status": package_status,
        "summary": summary_rows,
        "comparisons": comparisons,
        "stability": stability_rows,
    }
    (OUT_ROOT / "external_gmf_summary.json").write_text(
        json.dumps(summary_json, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    print(f"Wrote {OUT_ROOT}")
    for row in comparisons:
        print(
            f"{row['dataset']}: Raw {row['raw_success_rate_pct']:.1f}% -> "
            f"v16 {row['v16_success_rate_pct']:.1f}% "
            f"({row['success_rate_gain_pct_point']:.1f} pp)"
        )


if __name__ == "__main__":
    main()

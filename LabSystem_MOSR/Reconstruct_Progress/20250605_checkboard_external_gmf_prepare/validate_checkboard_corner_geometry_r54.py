from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


RUN_DIR = Path(__file__).resolve().parent
LAB_ROOT = RUN_DIR.parents[1]
BASE_VALIDATOR = RUN_DIR / "validate_checkboard_corner_geometry.py"
OUTPUT_DIR = RUN_DIR / "corner_geometry_validation_r54_20260616"
REPORT_PATH = (
    LAB_ROOT
    / "Experiments"
    / "R54_GeometryRootCauseProbe"
    / "reports"
    / "R54_CHECKBOARD_VALIDATION.md"
)

CASES = [
    ("raw_input", "Raw input"),
    ("lab_r40_best_tradeoff", "Lab R40 tradeoff"),
    ("lab_r53_realistic_best_tradeoff", "Lab R53 realistic best"),
    ("lab_r53_realistic_latest", "Lab R53 realistic latest"),
    ("lab_r54_edgeband_epoch020", "Lab R54 edge-band epoch20"),
]


def load_base_validator():
    spec = importlib.util.spec_from_file_location("lab_corner_validator_base", BASE_VALIDATOR)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load base validator: {BASE_VALIDATOR}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def fmt(value: object, ndigits: int = 3) -> str:
    try:
        return f"{float(value):.{ndigits}f}"
    except (TypeError, ValueError):
        return str(value)


def _as_float(value: object) -> float:
    return float(value)


def _as_key(row: dict[str, object]) -> tuple[str, str]:
    return (str(row["frame"]), str(row["corner_id"]))


def _summary_by_case(summaries: list[dict[str, object]]) -> dict[str, dict[str, object]]:
    return {str(row["case"]): row for row in summaries}


def compute_package_check(base) -> dict[str, dict[str, object]]:
    cases_dir = RUN_DIR / "gmf_cases"
    raw_dir = cases_dir / "raw_input"
    raw_names = sorted(path.name for path in raw_dir.glob("*.bmp"))
    checks: dict[str, dict[str, object]] = {}
    for case_name, _ in CASES:
        case_dir = cases_dir / case_name
        files = sorted(case_dir.glob("*.bmp"))
        mae_values: list[float] = []
        if case_name != "raw_input":
            for path in files:
                raw = base.read_gray(raw_dir / path.name).astype("float32")
                image = base.read_gray(path).astype("float32")
                mae_values.append(float(abs(image - raw).mean()))
        checks[case_name] = {
            "count": len(files),
            "filename_identity": [path.name for path in files] == raw_names,
            "mean_abs_change_vs_raw": float(sum(mae_values) / len(mae_values)) if mae_values else 0.0,
        }
    return checks


def compute_pairwise(rows: list[dict[str, object]]) -> dict[str, object]:
    by_key_case = {
        (_as_key(row)[0], _as_key(row)[1], str(row["case"])): row
        for row in rows
    }
    keys = sorted({_as_key(row) for row in rows})

    def shift(key: tuple[str, str], case: str) -> float:
        return _as_float(by_key_case[(key[0], key[1], case)]["corner_peak_shift_px"])

    def summarize_pair(candidate: str, baseline: str) -> dict[str, object]:
        deltas = [shift(key, candidate) - shift(key, baseline) for key in keys]
        cand = [shift(key, candidate) for key in keys]
        base_vals = [shift(key, baseline) for key in keys]
        better = sum(delta < 0 for delta in deltas)
        equal = sum(abs(delta) < 1e-9 for delta in deltas)
        worse = sum(delta > 0 for delta in deltas)
        sorted_deltas = sorted(deltas)
        median_delta = sorted_deltas[len(sorted_deltas) // 2]
        return {
            "candidate": candidate,
            "baseline": baseline,
            "measurements": len(keys),
            "candidate_better_count": better,
            "candidate_equal_count": equal,
            "candidate_worse_count": worse,
            "candidate_better_pct": 100.0 * better / len(keys),
            "median_delta_px": median_delta,
            "mean_delta_px": sum(deltas) / len(deltas),
            "candidate_gt5_baseline_le5_count": sum(
                c > 5.0 and b <= 5.0 for c, b in zip(cand, base_vals)
            ),
            "candidate_le5_baseline_gt5_count": sum(
                c <= 5.0 and b > 5.0 for c, b in zip(cand, base_vals)
            ),
            "candidate_gt10_count": sum(c > 10.0 for c in cand),
            "baseline_gt10_count": sum(b > 10.0 for b in base_vals),
            "max_candidate_shift_px": max(cand),
            "max_baseline_shift_px": max(base_vals),
        }

    pairwise = [
        summarize_pair("lab_r54_edgeband_epoch020", "raw_input"),
        summarize_pair("lab_r54_edgeband_epoch020", "lab_r40_best_tradeoff"),
        summarize_pair("lab_r54_edgeband_epoch020", "lab_r53_realistic_best_tradeoff"),
        summarize_pair("lab_r54_edgeband_epoch020", "lab_r53_realistic_latest"),
    ]

    outliers: list[dict[str, object]] = []
    for key in keys:
        r54 = shift(key, "lab_r54_edgeband_epoch020")
        r40 = shift(key, "lab_r40_best_tradeoff")
        if r54 <= 5.0 or r40 > 5.0:
            continue
        raw = by_key_case[(key[0], key[1], "raw_input")]
        outliers.append(
            {
                "frame": key[0],
                "corner_id": key[1],
                "x": raw["x"],
                "y": raw["y"],
                "raw_shift": shift(key, "raw_input"),
                "r40_shift": r40,
                "r53_best_shift": shift(key, "lab_r53_realistic_best_tradeoff"),
                "r53_latest_shift": shift(key, "lab_r53_realistic_latest"),
                "r54_shift": r54,
            }
        )
    outliers.sort(key=lambda row: _as_float(row["r54_shift"]), reverse=True)
    return {
        "pairwise": pairwise,
        "r54_fails_where_r40_succeeds_count": len(outliers),
        "r54_fails_where_r40_succeeds": outliers,
    }


def make_focus_contact_sheet(rows: list[dict[str, object]], pairwise_payload: dict[str, object]) -> None:
    cases = [
        ("raw_input", "Raw"),
        ("lab_r40_best_tradeoff", "R40"),
        ("lab_r53_realistic_best_tradeoff", "R53 best"),
        ("lab_r53_realistic_latest", "R53 latest"),
        ("lab_r54_edgeband_epoch020", "R54 edge"),
    ]
    by_key_case = {
        (_as_key(row)[0], _as_key(row)[1], str(row["case"])): row
        for row in rows
    }
    selected = [
        (str(row["frame"]), str(row["corner_id"]))
        for row in pairwise_payload["r54_fails_where_r40_succeeds"][:6]
    ]
    if not selected:
        worst = sorted(
            (row for row in rows if str(row["case"]) == "lab_r54_edgeband_epoch020"),
            key=lambda row: _as_float(row["corner_peak_shift_px"]),
            reverse=True,
        )[:6]
        selected = [(str(row["frame"]), str(row["corner_id"])) for row in worst]
    if not selected:
        return

    crop = 128
    pad = crop // 2
    tile_h = crop + 34
    left_w = 210
    header_h = 46
    sheet = Image.new("RGB", (left_w + len(cases) * crop, header_h + len(selected) * tile_h), "white")
    draw = ImageDraw.Draw(sheet)
    try:
        font = ImageFont.truetype("arial.ttf", 14)
        small = ImageFont.truetype("arial.ttf", 11)
    except Exception:
        font = ImageFont.load_default()
        small = ImageFont.load_default()

    for col, (_, label) in enumerate(cases):
        draw.text((left_w + col * crop + 6, 10), label, fill="black", font=font)

    cases_root = RUN_DIR / "gmf_cases"
    for row_idx, key in enumerate(selected):
        frame, corner_id = key
        raw_row = by_key_case[(frame, corner_id, "raw_input")]
        x = int(float(raw_row["x"]))
        y = int(float(raw_row["y"]))
        y0 = header_h + row_idx * tile_h
        draw.text((6, y0 + 8), frame.replace("Image__", "").replace(".bmp", ""), fill="black", font=small)
        draw.text((6, y0 + 24), f"corner {corner_id} xy=({x},{y})", fill="black", font=small)
        for col, (case_name, _) in enumerate(cases):
            path = cases_root / case_name / frame
            image = Image.open(path).convert("L")
            canvas = Image.new("L", (image.width + 2 * pad, image.height + 2 * pad), 0)
            canvas.paste(image, (pad, pad))
            patch = canvas.crop((x, y, x + crop, y + crop)).convert("RGB")
            patch_draw = ImageDraw.Draw(patch)
            center = crop // 2
            patch_draw.line((center - 6, center, center + 6, center), fill=(255, 220, 0), width=1)
            patch_draw.line((center, center - 6, center, center + 6), fill=(255, 220, 0), width=1)
            metric_row = by_key_case[(frame, corner_id, case_name)]
            shift = _as_float(metric_row["corner_peak_shift_px"])
            x0 = left_w + col * crop
            sheet.paste(patch, (x0, y0))
            draw.text((x0 + 5, y0 + crop + 3), f"shift {shift:.2f}px", fill="black", font=small)

    sheet.save(OUTPUT_DIR / "r54_focus_corner_comparison.png")


def render_verdict(summaries: list[dict[str, object]]) -> list[str]:
    by_case = _summary_by_case(summaries)
    control_median = float(by_case["lab_r40_best_tradeoff"]["median_corner_peak_shift_px"])
    control_pct = float(by_case["lab_r40_best_tradeoff"]["pct_peak_shift_gt_5px"])
    r54_median = float(by_case["lab_r54_edgeband_epoch020"]["median_corner_peak_shift_px"])
    r54_pct = float(by_case["lab_r54_edgeband_epoch020"]["pct_peak_shift_gt_5px"])
    if r54_median < control_median and r54_pct <= control_pct:
        return [
            "R54 passes this real checkboard corner gate: it beats the Lab R40",
            "corner-shift control without increasing the >5 px corner outlier rate.",
        ]
    if r54_median < control_median:
        return [
            "R54 improves the median corner shift but still raises the large-shift",
            "corner rate. Treat it as directional evidence, not a pass.",
        ]
    return [
        "R54 does not pass the real checkboard corner gate. The edge-band",
        "small-overfit checkpoint does not beat the Lab R40 corner control.",
    ]


def render_report(
    summaries: list[dict[str, object]],
    frame_count: int,
    raw_corner_count: int,
    package_check: dict[str, dict[str, object]],
    pairwise_payload: dict[str, object],
) -> str:
    lines = [
        "# Lab R54 Edge-Band Probe Checkboard Validation - 2026-06-16",
        "",
        "## Verdict",
        "",
        *render_verdict(summaries),
        "",
        "## Image Evidence Scope",
        "",
        f"- Frames checked: {frame_count}",
        f"- Raw checker corners accepted by the detector: {raw_corner_count}",
        f"- Case measurements: {raw_corner_count * len(CASES)}",
        "- All case folders must preserve the original 51 BMP filenames.",
        "",
        "## Corner Geometry Result",
        "",
        "| Case | Median corner shift (px) | P75 shift (px) | Corners > 5 px shift | Median local change vs raw | Median edge strength | Harris gain vs raw |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for row in summaries:
        lines.append(
            "| "
            + " | ".join(
                [
                    str(row["label"]),
                    fmt(row["median_corner_peak_shift_px"]),
                    fmt(row["p75_corner_peak_shift_px"]),
                    fmt(row["pct_peak_shift_gt_5px"]) + "%",
                    fmt(row["median_norm_mae_vs_raw"]),
                    fmt(row["median_gradient_p95"]),
                    fmt(row["harris_gain_vs_raw_median"], 1) + "x",
                ]
            )
            + " |"
        )

    pairwise_by_name = {
        (str(row["candidate"]), str(row["baseline"])): row
        for row in pairwise_payload["pairwise"]
    }
    lines.extend(["", "## Pairwise Diagnosis", ""])
    for candidate, baseline, label in (
        ("lab_r54_edgeband_epoch020", "raw_input", "R54 versus raw input"),
        ("lab_r54_edgeband_epoch020", "lab_r40_best_tradeoff", "R54 versus Lab R40 tradeoff"),
        ("lab_r54_edgeband_epoch020", "lab_r53_realistic_best_tradeoff", "R54 versus R53 best"),
        ("lab_r54_edgeband_epoch020", "lab_r53_realistic_latest", "R54 versus R53 latest"),
    ):
        row = pairwise_by_name[(candidate, baseline)]
        lines.extend(
            [
                f"{label}:",
                "",
                "| Result | Count |",
                "|---|---:|",
                f"| Candidate better | {row['candidate_better_count']} |",
                f"| Equal | {row['candidate_equal_count']} |",
                f"| Candidate worse | {row['candidate_worse_count']} |",
                f"| Candidate > 5 px while baseline <= 5 px | {row['candidate_gt5_baseline_le5_count']} |",
                f"| Candidate <= 5 px while baseline > 5 px | {row['candidate_le5_baseline_gt5_count']} |",
                f"| Candidate > 10 px | {row['candidate_gt10_count']} |",
                f"| Baseline > 10 px | {row['baseline_gt10_count']} |",
                "",
            ]
        )

    lines.extend(
        [
            "## Package Verification",
            "",
            "| Case | Count | Filename identity | Mean absolute change vs raw |",
            "|---|---:|---|---:|",
        ]
    )
    for case_name, _ in CASES:
        check = package_check[case_name]
        lines.append(
            f"| {case_name} | {check['count']} | {check['filename_identity']} | {fmt(check['mean_abs_change_vs_raw'], 4)} |"
        )

    lines.extend(
        [
            "",
            "## Interpretation Rule",
            "",
            "- The R54 small-overfit package is allowed to prove local learning ability only.",
            "- A usable real-checkboard result must still beat Lab R40 on real captured corners.",
            "- If R54 improves the masked CAD package but worsens real checkboard corners, the small probe is not a deployable model.",
            "",
            "## Artifacts",
            "",
            f"- Corner metrics table: `{OUTPUT_DIR / 'corner_metrics_per_measurement.csv'}`",
            f"- Corner summary table: `{OUTPUT_DIR / 'corner_metrics_summary.csv'}`",
            f"- Summary JSON: `{OUTPUT_DIR / 'corner_validation_summary.json'}`",
            f"- Visual corner sheet: `{OUTPUT_DIR / 'corner_patch_contact_sheet.png'}`",
            f"- Focused corner comparison: `{OUTPUT_DIR / 'r54_focus_corner_comparison.png'}`",
            f"- Pairwise comparison JSON: `{OUTPUT_DIR / 'r54_pairwise_corner_comparison.json'}`",
            f"- Metric chart: `{OUTPUT_DIR / 'corner_metric_summary.png'}`",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> None:
    base = load_base_validator()
    base.CASES = CASES
    base.OUTPUT_DIR = OUTPUT_DIR

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    rows, summaries, frame_count, raw_corner_count = base.analyze_corner_images()
    package_check = compute_package_check(base)
    pairwise_payload = compute_pairwise(rows)

    base.write_csv(OUTPUT_DIR / "corner_metrics_per_measurement.csv", rows)
    base.write_csv(OUTPUT_DIR / "corner_metrics_summary.csv", summaries)
    base.write_csv(OUTPUT_DIR / "r54_pairwise_corner_comparison.csv", pairwise_payload["pairwise"])
    base.write_csv(
        OUTPUT_DIR / "r54_outlier_examples_vs_r40.csv",
        pairwise_payload["r54_fails_where_r40_succeeds"],
    )
    (OUTPUT_DIR / "r54_gmf_package_check.json").write_text(
        json.dumps(package_check, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    (OUTPUT_DIR / "r54_pairwise_corner_comparison.json").write_text(
        json.dumps(pairwise_payload, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    summary_payload = {
        "frames_checked": frame_count,
        "raw_corners_checked": raw_corner_count,
        "case_count": len(CASES),
        "summaries": summaries,
        "package_check": package_check,
        "pairwise": pairwise_payload,
    }
    (OUTPUT_DIR / "corner_validation_summary.json").write_text(
        json.dumps(summary_payload, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    base.make_corner_contact_sheet(rows)
    base.make_summary_plot(summaries)
    make_focus_contact_sheet(rows, pairwise_payload)

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(
        render_report(summaries, frame_count, raw_corner_count, package_check, pairwise_payload),
        encoding="utf-8",
    )

    print(f"frames_checked={frame_count}")
    print(f"raw_corners_checked={raw_corner_count}")
    for row in summaries:
        print(
            f"{row['label']}: median_shift={fmt(row['median_corner_peak_shift_px'])} px, "
            f"pct_gt5={fmt(row['pct_peak_shift_gt_5px'])}%, "
            f"mae={fmt(row['median_norm_mae_vs_raw'])}"
        )
    print(f"report={REPORT_PATH}")


if __name__ == "__main__":
    main()

"""Validate R55 real-checkboard corner geometry against Lab controls."""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve()
LAB_ROOT = SCRIPT_PATH.parents[3]
RECON_PREP_ROOT = LAB_ROOT / "Reconstruct_Progress" / "20250605_checkboard_external_gmf_prepare"
BASE_VALIDATOR = RECON_PREP_ROOT / "validate_checkboard_corner_geometry.py"
OUTPUT_DIR = RECON_PREP_ROOT / "corner_geometry_validation_r55_20260618"
REPORT_PATH = LAB_ROOT / "Experiments" / "R55_SourceStyleRealisticTraining" / "reports" / "R55_CHECKBOARD_VALIDATION.md"

CASES = [
    ("raw_input", "Raw input"),
    ("lab_r40_best_tradeoff", "Lab R40 tradeoff"),
    ("lab_r51_mixed_psf_best_tradeoff", "Lab R51 mixed-PSF best"),
    ("lab_r52_stability_latest", "Lab R52 latest"),
    ("lab_r53_realistic_best_tradeoff", "Lab R53 best"),
    ("lab_r53_realistic_latest", "Lab R53 latest"),
    ("lab_r55_source_style_best_tradeoff", "Lab R55 best"),
    ("lab_r55_source_style_latest", "Lab R55 latest"),
]


def load_base_validator():
    spec = importlib.util.spec_from_file_location("lab_corner_validator_base_r55", BASE_VALIDATOR)
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


def _summary_by_case(summaries: list[dict[str, object]]) -> dict[str, dict[str, object]]:
    return {str(row["case"]): row for row in summaries}


def _as_float(row: dict[str, object], key: str) -> float:
    return float(row[key])


def _tail_key(row: dict[str, object]) -> str:
    return "p90_corner_peak_shift_px" if "p90_corner_peak_shift_px" in row else "p75_corner_peak_shift_px"


def gate_against_control(candidate: dict[str, object], control: dict[str, object]) -> dict[str, object]:
    failures = []
    cand_tail_key = _tail_key(candidate)
    control_tail_key = _tail_key(control)
    if _as_float(candidate, "median_corner_peak_shift_px") >= _as_float(control, "median_corner_peak_shift_px"):
        failures.append("median_not_better")
    if _as_float(candidate, "pct_peak_shift_gt_5px") > _as_float(control, "pct_peak_shift_gt_5px"):
        failures.append("large_shift_rate_worse")
    if _as_float(candidate, cand_tail_key) > _as_float(control, control_tail_key):
        failures.append("tail_worse")
    return {
        "candidate": candidate["case"],
        "control": control["case"],
        "pass": not failures,
        "failures": failures,
        "candidate_median_px": _as_float(candidate, "median_corner_peak_shift_px"),
        "control_median_px": _as_float(control, "median_corner_peak_shift_px"),
        "candidate_gt5_pct": _as_float(candidate, "pct_peak_shift_gt_5px"),
        "control_gt5_pct": _as_float(control, "pct_peak_shift_gt_5px"),
        "tail_metric": cand_tail_key,
        "candidate_tail_px": _as_float(candidate, cand_tail_key),
        "control_tail_px": _as_float(control, control_tail_key),
    }


def package_check(base) -> dict[str, dict[str, object]]:
    cases_dir = RECON_PREP_ROOT / "gmf_cases"
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


def pairwise_corner_deltas(rows: list[dict[str, object]], candidate: str, baseline: str) -> dict[str, object]:
    by_key_case = {
        (str(row["frame"]), str(row["corner_id"]), str(row["case"])): row
        for row in rows
    }
    keys = sorted((frame, corner) for frame, corner, case in by_key_case if case == candidate)
    deltas = []
    for key in keys:
        cand = float(by_key_case[(key[0], key[1], candidate)]["corner_peak_shift_px"])
        base = float(by_key_case[(key[0], key[1], baseline)]["corner_peak_shift_px"])
        deltas.append(cand - base)
    better = sum(delta < 0 for delta in deltas)
    worse = sum(delta > 0 for delta in deltas)
    sorted_deltas = sorted(deltas)
    return {
        "candidate": candidate,
        "baseline": baseline,
        "measurements": len(deltas),
        "better_count": better,
        "worse_count": worse,
        "better_pct": 100.0 * better / len(deltas),
        "median_delta_px": sorted_deltas[len(sorted_deltas) // 2],
        "mean_delta_px": sum(deltas) / len(deltas),
    }


def render_report(
    summaries: list[dict[str, object]],
    gates: list[dict[str, object]],
    package_checks: dict[str, dict[str, object]],
    pairwise: list[dict[str, object]],
    frame_count: int,
    raw_corner_count: int,
) -> str:
    lines = [
        "# R55 Checkboard Validation",
        "",
        "## Scope",
        "",
        f"- Frames checked: {frame_count}",
        f"- Raw checker corners accepted by detector: {raw_corner_count}",
        "- Same real Lab 20250605 checkboard sequence as R53/R54 validation.",
        "",
        "## Corner Geometry Summary",
        "",
        "| Case | Median shift px | Tail shift px | Corners > 5 px | Median local change vs raw | Median edge strength |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for row in summaries:
        lines.append(
            "| "
            + " | ".join(
                [
                    str(row["label"]),
                    fmt(row["median_corner_peak_shift_px"]),
                    fmt(row[_tail_key(row)]),
                    fmt(row["pct_peak_shift_gt_5px"]) + "%",
                    fmt(row["median_norm_mae_vs_raw"]),
                    fmt(row["median_gradient_p95"]),
                ]
            )
            + " |"
        )

    lines.extend(["", "## Guard Result", "", "| Candidate | Control | Pass | Failed rules |", "|---|---|---:|---|"])
    for gate in gates:
        lines.append(
            f"| {gate['candidate']} | {gate['control']} | {gate['pass']} | {', '.join(gate['failures']) or 'none'} |"
        )

    lines.extend(["", "## Pairwise Delta", "", "| Candidate | Baseline | Better corners | Median delta px | Mean delta px |", "|---|---|---:|---:|---:|"])
    for row in pairwise:
        lines.append(
            f"| {row['candidate']} | {row['baseline']} | {fmt(row['better_pct'], 1)}% | {fmt(row['median_delta_px'])} | {fmt(row['mean_delta_px'])} |"
        )

    lines.extend(["", "## Package Check", "", "| Case | BMP count | Filenames match raw | Mean abs change vs raw |", "|---|---:|---:|---:|"])
    for case_name, check in package_checks.items():
        lines.append(
            f"| {case_name} | {check['count']} | {check['filename_identity']} | {fmt(check['mean_abs_change_vs_raw'])} |"
        )

    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            "- R55 is judged only after this real-checkboard validation, not by internal training PSNR alone.",
            "- The selected Lab candidate must improve the median corner response and must not increase the large-shift tail against the Lab R40 control.",
            "- The training log already warned about oversmoothing, so the latest checkpoint is especially suspicious until the real-corner numbers prove otherwise.",
            "",
            "## Artifacts",
            "",
            f"- Per-corner table: `{OUTPUT_DIR / 'corner_metrics_per_measurement.csv'}`",
            f"- Summary table: `{OUTPUT_DIR / 'corner_metrics_summary.csv'}`",
            f"- Package check: `{OUTPUT_DIR / 'r55_gmf_package_check.json'}`",
            f"- Guard JSON: `{OUTPUT_DIR / 'r55_corner_gate.json'}`",
            f"- Visual corner sheet: `{OUTPUT_DIR / 'corner_patch_contact_sheet.png'}`",
            f"- Metric chart: `{OUTPUT_DIR / 'corner_metric_summary.png'}`",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> int:
    base = load_base_validator()
    base.CASES = CASES
    base.OUTPUT_DIR = OUTPUT_DIR
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    rows, summaries, frame_count, raw_corner_count = base.analyze_corner_images()
    by_case = _summary_by_case(summaries)
    checks = package_check(base)
    gates = [
        gate_against_control(by_case["lab_r55_source_style_best_tradeoff"], by_case["lab_r40_best_tradeoff"]),
        gate_against_control(by_case["lab_r55_source_style_latest"], by_case["lab_r40_best_tradeoff"]),
    ]
    pairwise = [
        pairwise_corner_deltas(rows, "lab_r55_source_style_best_tradeoff", "lab_r40_best_tradeoff"),
        pairwise_corner_deltas(rows, "lab_r55_source_style_latest", "lab_r40_best_tradeoff"),
        pairwise_corner_deltas(rows, "lab_r55_source_style_best_tradeoff", "lab_r53_realistic_best_tradeoff"),
        pairwise_corner_deltas(rows, "lab_r55_source_style_latest", "lab_r53_realistic_latest"),
        pairwise_corner_deltas(rows, "lab_r55_source_style_best_tradeoff", "lab_r52_stability_latest"),
    ]

    base.write_csv(OUTPUT_DIR / "corner_metrics_per_measurement.csv", rows)
    base.write_csv(OUTPUT_DIR / "corner_metrics_summary.csv", summaries)
    base.write_csv(OUTPUT_DIR / "r55_pairwise_corner_comparison.csv", pairwise)
    (OUTPUT_DIR / "r55_gmf_package_check.json").write_text(
        json.dumps(checks, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    summary_payload = {
        "frames_checked": frame_count,
        "raw_corners_checked": raw_corner_count,
        "case_count": len(CASES),
        "summaries": summaries,
        "gates": gates,
        "pairwise": pairwise,
        "package_check": checks,
    }
    (OUTPUT_DIR / "corner_validation_summary.json").write_text(
        json.dumps(summary_payload, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    (OUTPUT_DIR / "r55_corner_gate.json").write_text(
        json.dumps(gates, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    base.make_corner_contact_sheet(rows)
    base.make_summary_plot(summaries)

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(
        render_report(summaries, gates, checks, pairwise, frame_count, raw_corner_count),
        encoding="utf-8",
    )

    print(f"frames_checked={frame_count}")
    print(f"raw_corners_checked={raw_corner_count}")
    for row in summaries:
        print(
            f"{row['label']}: median_shift={fmt(row['median_corner_peak_shift_px'])} px, "
            f"tail={fmt(row[_tail_key(row)])} px, "
            f"pct_gt5={fmt(row['pct_peak_shift_gt_5px'])}%"
        )
    print(json.dumps({"gates": gates, "report": str(REPORT_PATH)}, indent=2, ensure_ascii=False))
    return 0 if all(gate["pass"] for gate in gates) else 2


if __name__ == "__main__":
    raise SystemExit(main())

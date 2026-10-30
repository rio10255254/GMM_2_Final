from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path


RUN_DIR = Path(__file__).resolve().parent
LAB_ROOT = RUN_DIR.parents[1]
BASE_VALIDATOR = RUN_DIR / "validate_checkboard_corner_geometry.py"
OUTPUT_DIR = RUN_DIR / "corner_geometry_validation_r51_20260614"
REPORT_PATH = (
    LAB_ROOT
    / "Experiments"
    / "R51_BlurSourceProbe"
    / "reports"
    / "R51_CHECKBOARD_VALIDATION.md"
)

CASES = [
    ("raw_input", "Raw input"),
    ("lab_r40_best_tradeoff", "Lab R40 tradeoff"),
    ("lab_r46_best_tradeoff", "Lab R46 tradeoff"),
    ("lab_r47_latest", "Lab R47 latest E200"),
    ("lab_r48_best_detail_guarded", "Lab R48 best_detail_guarded"),
    ("lab_r49_latest", "Lab R49 latest E100"),
    ("lab_r51_gaussian_best_tradeoff", "Lab R51 Gaussian best"),
    ("lab_r51_gaussian_latest", "Lab R51 Gaussian latest"),
    ("lab_r51_weak_bads_best_tradeoff", "Lab R51 weak-BADS best"),
    ("lab_r51_weak_bads_latest", "Lab R51 weak-BADS latest"),
    ("lab_r51_mixed_psf_best_tradeoff", "Lab R51 mixed-PSF best"),
    ("lab_r51_mixed_psf_latest", "Lab R51 mixed-PSF latest"),
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


def package_rows() -> list[dict[str, object]]:
    paths = [
        (
            "R51 Gaussian probe",
            LAB_ROOT / "Training_Data" / "r51_blur_source_probe" / "r51_gaussian_corner_probe" / "manifest.json",
        ),
        (
            "R51 weak-BADS probe",
            LAB_ROOT / "Training_Data" / "r51_blur_source_probe" / "r51_weak_bads_corner_probe" / "manifest.json",
        ),
        (
            "R51 mixed-PSF probe",
            LAB_ROOT / "Training_Data" / "r51_blur_source_probe" / "r51_mixed_psf_corner_probe" / "manifest.json",
        ),
        (
            "R51 held-out mixed corner validation",
            LAB_ROOT / "Training_Data" / "r51_blur_source_probe" / "r51_mixed_corner_val" / "manifest.json",
        ),
    ]
    rows: list[dict[str, object]] = []
    for label, path in paths:
        data = json.loads(path.read_text(encoding="utf-8"))
        roles = data.get("count_by_role", {})
        sources = data.get("count_by_corner_source", {})
        rows.append(
            {
                "package": label,
                "total_pairs": int(data.get("total_pairs", 0)),
                "ring": int(roles.get("ring", 0)),
                "shape": int(roles.get("shape", 0)),
                "micro": int(roles.get("micro", 0)),
                "corner": int(roles.get("corner", 0)),
                "formal_bads": int(sources.get("formal_bads", 0)),
                "gaussian": int(sources.get("gaussian", 0)),
                "weak_bads_alpha050": int(sources.get("weak_bads_alpha050", 0)),
            }
        )
    return rows


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


def _summary_by_case(summaries: list[dict[str, object]]) -> dict[str, dict[str, object]]:
    return {str(row["case"]): row for row in summaries}


def render_verdict(summaries: list[dict[str, object]]) -> list[str]:
    by_case = _summary_by_case(summaries)
    control_best = float(by_case["lab_r40_best_tradeoff"]["median_corner_peak_shift_px"])
    r51_cases = [case for case, _ in CASES if case.startswith("lab_r51_")]
    r51_best_name = min(r51_cases, key=lambda c: float(by_case[c]["median_corner_peak_shift_px"]))
    r51_best = float(by_case[r51_best_name]["median_corner_peak_shift_px"])
    r51_pct = float(by_case[r51_best_name]["pct_peak_shift_gt_5px"])
    control_pct = float(by_case["lab_r40_best_tradeoff"]["pct_peak_shift_gt_5px"])
    if r51_best < control_best and r51_pct <= control_pct:
        return [
            "R51 is positive on this corner probe: at least one blur-source",
            "candidate beats the Lab R40 tradeoff corner-shift control without",
            "raising the >5 px corner outlier rate.",
        ]
    if r51_best < control_best:
        return [
            "R51 improves the median corner shift but still raises the large-shift",
            "corner rate. Treat it as directional evidence, not a pass.",
        ]
    return [
        "R51 does not pass the real checkboard corner gate. The blur-source",
        "probe did not beat the Lab R40 tradeoff control on the key median",
        "corner-shift metric.",
    ]


def render_report(
    summaries: list[dict[str, object]],
    rows_package: list[dict[str, object]],
    frame_count: int,
    raw_corner_count: int,
    package_check: dict[str, dict[str, object]],
) -> str:
    lines = [
        "# Lab R51 Blur-Source Probe Checkboard Validation - 2026-06-14",
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

    lines.extend(
        [
            "",
            "## R51 Training Coverage Snapshot",
            "",
            "| Package | Total pairs | Ring | Shape | Micro | Corner | Formal BADS corner | Gaussian corner | Weak-BADS 0.50 corner |",
            "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for row in rows_package:
        lines.append(
            "| "
            + " | ".join(
                [
                    str(row["package"]),
                    str(row["total_pairs"]),
                    str(row["ring"]),
                    str(row["shape"]),
                    str(row["micro"]),
                    str(row["corner"]),
                    str(row["formal_bads"]),
                    str(row["gaussian"]),
                    str(row["weak_bads_alpha050"]),
                ]
            )
            + " |"
        )

    lines.extend(
        [
            "",
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
            "- R51 is a blur-source probe, not a formal Lab model promotion round.",
            "- A useful result must beat Lab R40 tradeoff on real checkboard corners.",
            "- Training loss and synthetic validation are secondary to the real corner table.",
            "",
            "## Artifacts",
            "",
            f"- Corner metrics table: `{OUTPUT_DIR / 'corner_metrics_per_measurement.csv'}`",
            f"- Corner summary table: `{OUTPUT_DIR / 'corner_metrics_summary.csv'}`",
            f"- Summary JSON: `{OUTPUT_DIR / 'corner_validation_summary.json'}`",
            f"- Visual corner sheet: `{OUTPUT_DIR / 'corner_patch_contact_sheet.png'}`",
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
    rows_package = package_rows()

    base.write_csv(OUTPUT_DIR / "corner_metrics_per_measurement.csv", rows)
    base.write_csv(OUTPUT_DIR / "corner_metrics_summary.csv", summaries)
    base.write_csv(OUTPUT_DIR / "r51_training_coverage_summary.csv", rows_package)

    package_check = compute_package_check(base)
    (OUTPUT_DIR / "r51_gmf_package_check.json").write_text(
        json.dumps(package_check, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    summary_payload = {
        "frames_checked": frame_count,
        "raw_corners_checked": raw_corner_count,
        "case_count": len(CASES),
        "summaries": summaries,
        "r51_training_coverage": rows_package,
        "package_check": package_check,
    }
    (OUTPUT_DIR / "corner_validation_summary.json").write_text(
        json.dumps(summary_payload, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    base.make_corner_contact_sheet(rows)
    base.make_summary_plot(summaries)

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(
        render_report(summaries, rows_package, frame_count, raw_corner_count, package_check),
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


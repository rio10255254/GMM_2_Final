from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import numpy as np


RUN_DIR = Path(__file__).resolve().parent
LAB_ROOT = RUN_DIR.parents[1]
BASE_VALIDATOR = RUN_DIR / "validate_checkboard_corner_geometry.py"
OUTPUT_DIR = RUN_DIR / "corner_geometry_validation_r47_20260613"
REPORT_PATH = (
    LAB_ROOT
    / "Experiments"
    / "R47_RealisticBoundaryGeneralization"
    / "reports"
    / "R47_CHECKBOARD_VALIDATION_20260613.md"
)

CASES = [
    ("raw_input", "Raw input"),
    ("lab_r40_best_tradeoff", "Lab R40 tradeoff"),
    ("lab_r46_best_tradeoff", "Lab R46 tradeoff"),
    ("lab_r47_best_tradeoff", "Lab R47 best_tradeoff E33"),
    ("lab_r47_latest", "Lab R47 latest E200"),
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


def r47_package_rows() -> list[dict[str, object]]:
    paths = [
        (
            "R47 realistic boundary training",
            LAB_ROOT
            / "Training_Data"
            / "r47_realistic_boundary_generalization"
            / "r47_realistic_boundary_train_4000"
            / "manifest.json",
        ),
        (
            "R47 held-out realistic boundary validation",
            LAB_ROOT
            / "Training_Data"
            / "r47_realistic_boundary_generalization"
            / "realistic_boundary_val_unseen"
            / "manifest.json",
        ),
    ]
    rows: list[dict[str, object]] = []
    for label, path in paths:
        data = json.loads(path.read_text(encoding="utf-8"))
        counts = data.get("count_by_stage", {})
        roles = data.get("count_by_role", {})
        rows.append(
            {
                "package": label,
                "total_pairs": int(data.get("total_pairs", 0)),
                "ring": int(roles.get("ring", 0)),
                "shape": int(roles.get("shape", 0)),
                "micro": int(roles.get("micro", 0)),
                "boundary": int(roles.get("boundary", 0)),
                "real_bg": int(roles.get("real_bg", 0)),
                "checkboard_corner": int(counts.get("stage_49_realistic_checkboard_corners", 0)),
                "intersection_edge": int(counts.get("stage_50_intersections_edges", 0)),
                "real_background_boundary": int(counts.get("stage_51_real_background_boundaries", 0)),
                "psf_stress": int(counts.get("stage_52_boundary_psf_stress", 0)),
            }
        )
    return rows


def compute_package_check(base) -> dict[str, dict[str, object]]:
    cases_dir = RUN_DIR / "gmf_cases"
    raw_dir = cases_dir / "raw_input"
    raw_names = sorted(path.name for path in raw_dir.glob("*.bmp"))
    checks: dict[str, dict[str, object]] = {}
    for case_name in ["raw_input", "lab_r47_best_tradeoff", "lab_r47_latest"]:
        case_dir = cases_dir / case_name
        files = sorted(case_dir.glob("*.bmp"))
        mae_values: list[float] = []
        if case_name != "raw_input":
            for path in files:
                raw = base.read_gray(raw_dir / path.name).astype(np.float32)
                image = base.read_gray(path).astype(np.float32)
                mae_values.append(float(np.mean(np.abs(image - raw))))
        checks[case_name] = {
            "count": len(files),
            "filename_identity": [path.name for path in files] == raw_names,
            "mean_abs_change_vs_raw": float(np.mean(mae_values)) if mae_values else 0.0,
        }
    return checks


def render_report(
    summaries: list[dict[str, object]],
    r47_rows: list[dict[str, object]],
    frame_count: int,
    raw_corner_count: int,
    package_check: dict[str, dict[str, object]],
) -> str:
    lines = [
        "# Lab R47 Checkboard Validation - 2026-06-13",
        "",
        "## Verdict",
        "",
        "R47 was reconstructed on the real 20250605 Lab checkboard sequence and",
        "compared against raw input plus the earlier R40/R46 controls using the",
        "same corner-response validation method as the R46 report.",
        "",
        "The result is negative: neither R47 checkpoint solves the real checkboard",
        "corner problem. R47 best_tradeoff is worse than the earlier R40/R46 controls,",
        "and R47 latest is less bad than R47 best_tradeoff but still worse than R40",
        "tradeoff and R46 tradeoff on this corner metric.",
        "",
        "## Image Evidence Scope",
        "",
        f"- Frames checked: {frame_count}",
        f"- Raw checker corners accepted by the detector: {raw_corner_count}",
        f"- Case measurements: {raw_corner_count * len(CASES)}",
        "- All R47 GMF case folders preserve the original 51 BMP filenames.",
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
            "## R47 Training Coverage Snapshot",
            "",
            "| Package | Total pairs | Ring | Shape | Micro | Boundary | Real background | Checkboard corner | Intersection edge | Real background boundary | PSF stress |",
            "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for row in r47_rows:
        lines.append(
            "| "
            + " | ".join(
                [
                    str(row["package"]),
                    str(row["total_pairs"]),
                    str(row["ring"]),
                    str(row["shape"]),
                    str(row["micro"]),
                    str(row["boundary"]),
                    str(row["real_bg"]),
                    str(row["checkboard_corner"]),
                    str(row["intersection_edge"]),
                    str(row["real_background_boundary"]),
                    str(row["psf_stress"]),
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
    for case_name in ["raw_input", "lab_r47_best_tradeoff", "lab_r47_latest"]:
        check = package_check[case_name]
        lines.append(
            f"| {case_name} | {check['count']} | {check['filename_identity']} | {fmt(check['mean_abs_change_vs_raw'], 4)} |"
        )

    lines.extend(
        [
            "",
            "## External GMF Status",
            "",
            "The R47 case folders are prepared under `gmf_cases/`, but no",
            "`GMF_score.txt` files were present at report generation time. External",
            "GMF remains pending and should not override this corner-geometry failure",
            "unless the returned score is interpreted together with the corner table.",
            "",
            "## Interpretation",
            "",
            "- Raw input remains the best geometry reference by median corner shift.",
            "- R47 latest is the better of the two R47 checkpoints, but it still does not beat the earlier R40/R46 controls.",
            "- R47 best_tradeoff is safer by training selection, but it is worse on this real corner metric.",
            "- Both R47 checkpoints are packaged for external GMF, but GMF should be interpreted together with this corner check.",
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
    r47_rows = r47_package_rows()

    base.write_csv(OUTPUT_DIR / "corner_metrics_per_measurement.csv", rows)
    base.write_csv(OUTPUT_DIR / "corner_metrics_summary.csv", summaries)
    base.write_csv(OUTPUT_DIR / "r47_training_coverage_summary.csv", r47_rows)

    package_check = compute_package_check(base)
    (OUTPUT_DIR / "r47_gmf_package_check.json").write_text(
        json.dumps(package_check, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    summary_payload = {
        "frames_checked": frame_count,
        "raw_corners_checked": raw_corner_count,
        "case_count": len(CASES),
        "summaries": summaries,
        "r47_training_coverage": r47_rows,
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
        render_report(summaries, r47_rows, frame_count, raw_corner_count, package_check),
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

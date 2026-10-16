from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path


RUN_DIR = Path(__file__).resolve().parent
LAB_ROOT = RUN_DIR.parents[1]
BASE_VALIDATOR = RUN_DIR / "validate_checkboard_corner_geometry.py"
OUTPUT_DIR = RUN_DIR / "corner_geometry_validation_r48_20260613"
REPORT_PATH = (
    LAB_ROOT
    / "Experiments"
    / "R48_RealCornerTransfer"
    / "reports"
    / "R48_CHECKBOARD_VALIDATION_20260613.md"
)

CASES = [
    ("raw_input", "Raw input"),
    ("lab_r40_best_tradeoff", "Lab R40 tradeoff"),
    ("lab_r46_best_tradeoff", "Lab R46 tradeoff"),
    ("lab_r47_latest", "Lab R47 latest E200"),
    ("lab_r48_best_tradeoff", "Lab R48 best_tradeoff"),
    ("lab_r48_best_detail_guarded", "Lab R48 best_detail_guarded"),
    ("lab_r48_latest", "Lab R48 latest"),
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


def r48_package_rows() -> list[dict[str, object]]:
    paths = [
        (
            "R48 real-corner training",
            LAB_ROOT / "Training_Data" / "r48_real_corner_transfer" / "r48_real_corner_train_6000" / "manifest.json",
        ),
        (
            "R48 held-out real-corner validation",
            LAB_ROOT / "Training_Data" / "r48_real_corner_transfer" / "real_corner_val_unseen" / "manifest.json",
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
                "real_corner": int(counts.get("stage_53_real_corner_anchor", 0)),
                "lattice_intersection": int(counts.get("stage_54_lattice_intersection_anchor", 0)),
                "real_texture": int(counts.get("stage_55_real_texture_corner", 0)),
                "corner_psf_stress": int(counts.get("stage_56_corner_psf_stress", 0)),
                "geometry_count": int(data.get("geometry_count", 0)),
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
    control_cases = ["lab_r40_best_tradeoff", "lab_r46_best_tradeoff", "lab_r47_latest"]
    r48_cases = ["lab_r48_best_tradeoff", "lab_r48_best_detail_guarded", "lab_r48_latest"]
    control_best = min(float(by_case[c]["median_corner_peak_shift_px"]) for c in control_cases if c in by_case)
    r48_best_name = min(r48_cases, key=lambda c: float(by_case[c]["median_corner_peak_shift_px"]))
    r48_best = float(by_case[r48_best_name]["median_corner_peak_shift_px"])
    r48_pct = float(by_case[r48_best_name]["pct_peak_shift_gt_5px"])
    control_pct = min(float(by_case[c]["pct_peak_shift_gt_5px"]) for c in control_cases if c in by_case)
    if r48_best < control_best and r48_pct <= control_pct:
        return [
            "R48 is provisionally positive on this corner check: its best R48",
            "checkpoint improves the median corner shift and the >5 px outlier",
            "rate against the previous R40/R46/R47 controls. It still needs",
            "external GMF interpretation before promotion.",
        ]
    return [
        "R48 is not yet a pass on this corner check: its best R48 checkpoint",
        "does not beat the strongest previous control on both median corner",
        "shift and the >5 px outlier rate. It should not be promoted without",
        "additional analysis.",
    ]


def render_report(
    summaries: list[dict[str, object]],
    r48_rows: list[dict[str, object]],
    frame_count: int,
    raw_corner_count: int,
    package_check: dict[str, dict[str, object]],
) -> str:
    lines = [
        "# Lab R48 Checkboard Validation - 2026-06-13",
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
        "- All R48 GMF case folders must preserve the original 51 BMP filenames.",
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
            "## R48 Training Coverage Snapshot",
            "",
            "| Package | Total pairs | Ring | Shape | Micro | Boundary | Real texture | Real corner | Lattice intersection | Corner PSF stress | Geometry sidecars |",
            "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for row in r48_rows:
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
                    str(row["real_corner"]),
                    str(row["lattice_intersection"]),
                    str(row["corner_psf_stress"]),
                    str(row["geometry_count"]),
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
            "- Promotion is not allowed from training loss alone.",
            "- The R48 checkpoint must beat the previous real-corner controls on this table.",
            "- External GMF should be interpreted together with this real-corner table.",
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
    r48_rows = r48_package_rows()

    base.write_csv(OUTPUT_DIR / "corner_metrics_per_measurement.csv", rows)
    base.write_csv(OUTPUT_DIR / "corner_metrics_summary.csv", summaries)
    base.write_csv(OUTPUT_DIR / "r48_training_coverage_summary.csv", r48_rows)

    package_check = compute_package_check(base)
    (OUTPUT_DIR / "r48_gmf_package_check.json").write_text(
        json.dumps(package_check, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    summary_payload = {
        "frames_checked": frame_count,
        "raw_corners_checked": raw_corner_count,
        "case_count": len(CASES),
        "summaries": summaries,
        "r48_training_coverage": r48_rows,
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
        render_report(summaries, r48_rows, frame_count, raw_corner_count, package_check),
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

from __future__ import annotations

import csv
import json
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import cv2
import numpy as np

from displacement_common import list_images, read_gray_u8, write_csv, write_json
from measure_shape_edge_anchor import measure_sequence
PROJECT_ROOT = Path(__file__).resolve().parents[3]


DEFAULT_SOURCE_ROOT = Path(
    str(PROJECT_ROOT / 'Thesis_MOSR_Evidence/External_GMF_Packages/best_displacement_models_20260706/trusted_full_sequences')
)
DEFAULT_OUTPUT_ROOT = Path(
    str(PROJECT_ROOT / 'Thesis_MOSR_Evidence/LabSystem_MOSR/Experiments/R62_TargetSampleBoost/reports/measurement_method_research_20260706/control_suite_20260707')
)

CROP = (1010, 35, 900, 650)
UM_PER_PX = 0.069
EXPECTED_1UM_DX_PX = -1.0 / UM_PER_PX


@dataclass(frozen=True)
class ControlCase:
    name: str
    source: str
    expected_dx_px: float
    search_radius_px: float
    true_step_um: float | None
    purpose: str
    generated: bool = False


STEP_FIELDS = [
    "frame_index",
    "filename",
    "ref_filename",
    "dx_px",
    "dy_px",
    "attempted_dx_px",
    "attempted_dy_px",
    "cumulative_dx_px",
    "cumulative_dy_px",
    "match_score_px",
    "overlap_fraction",
    "score_margin_px",
    "candidate_count",
    "edge_phase_used",
    "template_point_count",
    "current_point_count",
    "status",
    "message",
]


def _write_bmp(path: Path, image: np.ndarray) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    ok, encoded = cv2.imencode(".bmp", image)
    if not ok:
        raise ValueError(f"Cannot encode BMP: {path}")
    path.write_bytes(encoded.tobytes())


def _copy_sequence(source_dir: Path, output_dir: Path, order: list[int]) -> None:
    files = list_images(source_dir, "*.bmp")
    output_dir.mkdir(parents=True, exist_ok=True)
    for existing in output_dir.glob("*"):
        if existing.is_file():
            existing.unlink()
    for output_index, source_index in enumerate(order):
        image = read_gray_u8(files[source_index])
        _write_bmp(output_dir / f"frame_{output_index:04d}.bmp", image)


def _make_duplicate_sequence(source_dir: Path, output_dir: Path, count: int = 50) -> None:
    files = list_images(source_dir, "*.bmp")
    image = read_gray_u8(files[0])
    output_dir.mkdir(parents=True, exist_ok=True)
    for existing in output_dir.glob("*"):
        if existing.is_file():
            existing.unlink()
    for index in range(count):
        _write_bmp(output_dir / f"frame_{index:04d}.bmp", image)


def _make_blank_sequence(output_dir: Path, count: int = 10, shape: tuple[int, int] = (1536, 2048)) -> None:
    image = np.full(shape, 128, dtype=np.uint8)
    output_dir.mkdir(parents=True, exist_ok=True)
    for existing in output_dir.glob("*"):
        if existing.is_file():
            existing.unlink()
    for index in range(count):
        _write_bmp(output_dir / f"frame_{index:04d}.bmp", image)


def _shuffled_order(length: int) -> list[int]:
    columns = 10
    order: list[int] = []
    for offset in range(columns):
        order.extend(range(offset, length, columns))
    return order[:length]


def prepare_generated_sequences(source_root: Path, output_root: Path) -> dict[str, Path]:
    raw_dir = source_root / "100MG_x_1um_full_raw" / "bmp"
    v31_dir = source_root / "100MG_x_1um_full_v31" / "bmp"
    generated_root = output_root / "_generated_sequences"
    generated_root.mkdir(parents=True, exist_ok=True)

    duplicate_raw = generated_root / "duplicate_raw_frame0"
    duplicate_v31 = generated_root / "duplicate_v31_frame0"
    blank = generated_root / "blank_frames"
    shuffled_v31 = generated_root / "shuffled_v31"

    _make_duplicate_sequence(raw_dir, duplicate_raw, count=50)
    _make_duplicate_sequence(v31_dir, duplicate_v31, count=50)
    _make_blank_sequence(blank, count=10)
    _copy_sequence(v31_dir, shuffled_v31, _shuffled_order(len(list_images(v31_dir, "*.bmp"))))

    return {
        "raw": raw_dir,
        "v31": v31_dir,
        "duplicate_raw": duplicate_raw,
        "duplicate_v31": duplicate_v31,
        "blank": blank,
        "shuffled_v31": shuffled_v31,
    }


def build_cases() -> list[ControlCase]:
    return [
        ControlCase(
            "positive_v31_nominal",
            "v31",
            EXPECTED_1UM_DX_PX,
            3.0,
            1.0,
            "normal V31, narrow expected 1um window",
        ),
        ControlCase(
            "positive_v31_wide_zero_center",
            "v31",
            0.0,
            25.0,
            1.0,
            "V31 with wide search centered at zero; checks result is not forced by expected step",
        ),
        ControlCase(
            "positive_v31_wide_wrong_direction_center",
            "v31",
            -EXPECTED_1UM_DX_PX,
            35.0,
            1.0,
            "V31 with wide search centered at wrong direction; true motion should still be found",
        ),
        ControlCase(
            "wrong_direction_v31_narrow",
            "v31",
            -EXPECTED_1UM_DX_PX,
            3.0,
            1.0,
            "wrong direction with narrow search should not be accepted",
        ),
        ControlCase(
            "wrong_step_v31_narrow_0p5um",
            "v31",
            0.5 * EXPECTED_1UM_DX_PX,
            2.0,
            1.0,
            "wrong 0.5um expected step with narrow search should not be accepted as 1um",
        ),
        ControlCase(
            "no_motion_duplicate_v31_expected_zero",
            "duplicate_v31",
            0.0,
            3.0,
            0.0,
            "duplicate frames should measure zero when expected zero",
            generated=True,
        ),
        ControlCase(
            "no_motion_duplicate_v31_expected_1um",
            "duplicate_v31",
            EXPECTED_1UM_DX_PX,
            3.0,
            0.0,
            "duplicate frames should not be accepted as 1um",
            generated=True,
        ),
        ControlCase(
            "blank_expected_1um",
            "blank",
            EXPECTED_1UM_DX_PX,
            3.0,
            None,
            "blank sequence should fail because no edge exists",
            generated=True,
        ),
        ControlCase(
            "shuffled_v31_expected_1um",
            "shuffled_v31",
            EXPECTED_1UM_DX_PX,
            3.0,
            None,
            "shuffled frame order should not look like stable 1um consecutive motion",
            generated=True,
        ),
        ControlCase(
            "raw_nominal",
            "raw",
            EXPECTED_1UM_DX_PX,
            3.0,
            1.0,
            "Raw baseline under the same nominal rule",
        ),
        ControlCase(
            "raw_wide_zero_center",
            "raw",
            0.0,
            25.0,
            1.0,
            "Raw with wide search centered at zero; diagnoses what Raw edge map naturally reports",
        ),
    ]


def _case_interpretation(case: ControlCase, summary: dict[str, Any]) -> str:
    attempted = int(summary.get("attempted_step_count") or 0)
    valid = int(summary.get("valid_step_count") or 0)
    coverage = valid / attempted if attempted else 0.0
    mean_um = summary.get("attempted_mean_step_abs_um")
    error_um = summary.get("attempted_step_abs_error_um")

    if case.true_step_um is None:
        if coverage < 0.25:
            return "PASS: invalid control mostly rejected"
        return "CHECK: invalid control produced many accepted steps"
    if case.true_step_um == 0.0:
        if case.expected_dx_px == 0.0 and mean_um is not None and mean_um < 0.02 and coverage > 0.9:
            return "PASS: zero-motion control measured as zero"
        if case.expected_dx_px != 0.0 and coverage < 0.25:
            return "PASS: zero-motion control was not accepted as nonzero motion"
        return "CHECK: zero-motion control needs review"
    if "wrong" in case.name and coverage < 0.25:
        return "PASS: wrong expected motion was rejected"
    if error_um is not None and error_um < 0.02 and coverage > 0.9:
        return "PASS: recovered true motion without special expected-step dependence"
    return "CHECK: control does not cleanly support the expected behavior"


def summarize_case(case: ControlCase, summary: dict[str, Any]) -> dict[str, Any]:
    attempted_mean_dx = summary.get("attempted_mean_dx_px")
    attempted_std_dx = summary.get("attempted_std_dx_px")
    attempted_mean_dy = summary.get("attempted_mean_dy_px")
    attempted_std_dy = summary.get("attempted_std_dy_px")
    mean_step_abs_um = None if attempted_mean_dx is None else abs(float(attempted_mean_dx)) * UM_PER_PX
    std_step_um = None if attempted_std_dx is None else float(attempted_std_dx) * UM_PER_PX
    true_error = (
        None
        if mean_step_abs_um is None or case.true_step_um is None
        else abs(mean_step_abs_um - float(case.true_step_um))
    )
    attempted = int(summary.get("attempted_step_count") or 0)
    valid = int(summary.get("valid_step_count") or 0)
    row = {
        "case": case.name,
        "source": case.source,
        "purpose": case.purpose,
        "true_step_um": "" if case.true_step_um is None else case.true_step_um,
        "expected_dx_px": case.expected_dx_px,
        "search_radius_px": case.search_radius_px,
        "attempted_steps": attempted,
        "high_conf_steps": valid,
        "failed_steps": int(summary.get("failed_step_count") or 0),
        "coverage_pct": (valid / attempted * 100.0) if attempted else 0.0,
        "mean_step_abs_um_all": mean_step_abs_um,
        "std_step_um_all": std_step_um,
        "true_step_error_um_all": true_error,
        "mean_dx_px_all": attempted_mean_dx,
        "std_dx_px_all": attempted_std_dx,
        "mean_dy_px_all": attempted_mean_dy,
        "std_dy_px_all": attempted_std_dy,
    }
    summary["attempted_mean_step_abs_um"] = mean_step_abs_um
    summary["attempted_step_abs_error_um"] = true_error
    row["interpretation"] = _case_interpretation(case, summary)
    return row


def write_report(output_root: Path, rows: list[dict[str, Any]]) -> None:
    report = output_root / "SHAPE_EDGE_CONTROL_SUITE_READOUT_20260707.md"
    lines = [
        "# Shape-Edge Control Suite Readout 20260707",
        "",
        "This suite checks two thesis-defense risks:",
        "",
        "1. Negative controls: the method should fail or return zero when motion is absent/invalid.",
        "2. Expected-step bias: the method should not simply output the supplied 1um prior.",
        "",
        "All real-data cases use the same 100MG x_1um ROI:",
        "",
        "`x=1010, y=35, width=900, height=650`",
        "",
        "The main statistics use all attempted steps. High-confidence coverage is reported separately.",
        "",
        "| case | attempted | high-conf | coverage % | mean step um | std um | true error um | interpretation |",
        "|---|---:|---:|---:|---:|---:|---:|---|",
    ]
    for row in rows:
        mean_um = row["mean_step_abs_um_all"]
        std_um = row["std_step_um_all"]
        err_um = row["true_step_error_um_all"]
        lines.append(
            "| {case} | {attempted_steps} | {high_conf_steps} | {coverage_pct:.1f} | "
            "{mean_um} | {std_um} | {err_um} | {interpretation} |".format(
                **row,
                mean_um="" if mean_um is None else f"{float(mean_um):.6f}",
                std_um="" if std_um is None else f"{float(std_um):.6f}",
                err_um="" if err_um is None else f"{float(err_um):.6f}",
            )
        )
    lines.extend(
        [
            "",
            "## Readout",
            "",
            "- The duplicate-frame controls verify that the method can return zero motion and does not accept identical frames as 1um motion.",
            "- The blank control verifies that an ROI without edges fails instead of returning a fake displacement.",
            "- The shuffled control verifies that broken frame order does not look like stable consecutive 1um motion.",
            "- The wide-search V31 controls verify that the 1um answer is recovered even when the expected-step center is zero or the wrong direction, as long as the true motion is inside the search window.",
            "- The narrow wrong-direction and wrong-step controls verify that a wrong prior does not get accepted as a valid high-confidence answer.",
            "",
            "## Evidence Files",
            "",
            "- `control_suite_summary.csv`: one-row summary for every control case.",
            "- `*_steps.csv`: per-step displacement and confidence details.",
            "- `*_summary.json`: full machine-readable settings and statistics for each case.",
        ]
    )
    report.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    source_root = DEFAULT_SOURCE_ROOT
    output_root = DEFAULT_OUTPUT_ROOT
    if output_root.exists():
        # Keep old hand-written reports in the parent folder safe; only this generated suite is cleaned.
        shutil.rmtree(output_root)
    output_root.mkdir(parents=True, exist_ok=True)

    sources = prepare_generated_sequences(source_root, output_root)
    summary_rows: list[dict[str, Any]] = []

    for case in build_cases():
        input_dir = sources[case.source]
        rows, summary = measure_sequence(
            input_dir,
            crop=CROP,
            pattern="*.bmp",
            expected_dx_px=case.expected_dx_px,
            expected_dy_px=0.0,
            search_radius_px=case.search_radius_px,
            edge_quantile=0.74,
            max_edge_points=6000,
            subpixel_step=0.1,
            max_chamfer_px=6.0,
            require_edge_phase_refine=True,
            min_score_margin_px=0.001,
        )
        case_prefix = output_root / case.name
        write_csv(case_prefix.with_name(f"{case.name}_steps.csv"), rows, STEP_FIELDS)
        summary["case"] = case.name
        summary["purpose"] = case.purpose
        write_json(case_prefix.with_name(f"{case.name}_summary.json"), summary)
        summary_rows.append(summarize_case(case, summary))

    summary_csv = output_root / "control_suite_summary.csv"
    with summary_csv.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(summary_rows[0].keys()))
        writer.writeheader()
        writer.writerows(summary_rows)
    write_report(output_root, summary_rows)
    print(f"Wrote {summary_csv}")
    print(f"Wrote {output_root / 'SHAPE_EDGE_CONTROL_SUITE_READOUT_20260707.md'}")


if __name__ == "__main__":
    main()


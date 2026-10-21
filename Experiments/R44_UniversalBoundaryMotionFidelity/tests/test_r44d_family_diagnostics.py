import csv
from pathlib import Path
import sys


REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT_DIR = REPO_ROOT / "Experiments" / "R44_UniversalBoundaryMotionFidelity" / "scripts"
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))


def _write_rows(root: Path, folder: str, rows: list[dict]) -> None:
    out = root / folder
    out.mkdir(parents=True)
    fields = sorted({key for row in rows for key in row})
    with (out / "motion_rows.csv").open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def test_r44d_diagnostics_selects_family_specific_winners(tmp_path):
    import r44d_family_diagnostics

    _write_rows(
        tmp_path,
        "model_a",
        [
            {
                "feature_family": "thin_lines",
                "frame_b": 1,
                "expected_dx_px": 0.08,
                "expected_dy_px": 0.0,
                "motion_vector_error_px": 0.10,
                "boundary_motion_distance_px": 2.0,
            },
            {
                "feature_family": "grids",
                "frame_b": 6,
                "expected_dx_px": 6.0,
                "expected_dy_px": 0.0,
                "motion_vector_error_px": 4.0,
                "boundary_motion_distance_px": 5.0,
                "grid_phase_motion_error_px": 0.8,
            },
        ],
    )
    _write_rows(
        tmp_path,
        "model_b",
        [
            {
                "feature_family": "thin_lines",
                "frame_b": 1,
                "expected_dx_px": 0.08,
                "expected_dy_px": 0.0,
                "motion_vector_error_px": 0.40,
                "boundary_motion_distance_px": 1.0,
            },
            {
                "feature_family": "grids",
                "frame_b": 6,
                "expected_dx_px": 6.0,
                "expected_dy_px": 0.0,
                "motion_vector_error_px": 2.0,
                "boundary_motion_distance_px": 3.0,
                "grid_phase_motion_error_px": 0.2,
            },
        ],
    )

    rows = r44d_family_diagnostics.load_all_rows(tmp_path, {"A": "model_a", "B": "model_b"})
    diagnostics = r44d_family_diagnostics.build_diagnostics(rows)

    best = {(r["feature_family"], r["metric"]): r for r in diagnostics["best_by_family"]}
    assert best[("thin_lines", "boundary_motion_distance_px")]["best_model"] == "B"
    assert best[("thin_lines", "motion_vector_error_px")]["best_model"] == "A"
    assert best[("grids", "grid_phase_motion_error_px")]["best_model"] == "B"

    shift_rows = diagnostics["shift_scorecard"]
    assert {r["target_position_px"] for r in shift_rows if r["feature_family"] == "grids"} == {8.0}


def test_r44d_diagnostics_reports_single_model_gap_against_family_oracle(tmp_path):
    import r44d_family_diagnostics

    _write_rows(
        tmp_path,
        "model_a",
        [
            {"feature_family": "thin_lines", "frame_b": 1, "expected_dx_px": 0.08, "motion_vector_error_px": 0.1, "boundary_motion_distance_px": 10.0},
            {"feature_family": "large_regions", "frame_b": 1, "expected_dx_px": 0.08, "motion_vector_error_px": 0.1, "boundary_motion_distance_px": 1.0},
        ],
    )
    _write_rows(
        tmp_path,
        "model_b",
        [
            {"feature_family": "thin_lines", "frame_b": 1, "expected_dx_px": 0.08, "motion_vector_error_px": 0.1, "boundary_motion_distance_px": 2.0},
            {"feature_family": "large_regions", "frame_b": 1, "expected_dx_px": 0.08, "motion_vector_error_px": 0.1, "boundary_motion_distance_px": 8.0},
        ],
    )

    rows = r44d_family_diagnostics.load_all_rows(tmp_path, {"A": "model_a", "B": "model_b"})
    diagnostics = r44d_family_diagnostics.build_diagnostics(rows)

    assert diagnostics["oracle_boundary"]["family_oracle_boundary_avg_px"] == 1.5
    assert diagnostics["oracle_boundary"]["best_single_model_boundary_avg_px"] == 5.0
    assert diagnostics["oracle_boundary"]["best_single_model"] == "B"


def test_r44d_diagnostics_flags_non_discriminative_metric(tmp_path):
    import r44d_family_diagnostics

    _write_rows(
        tmp_path,
        "model_a",
        [
            {"feature_family": "grids", "frame_b": 1, "expected_dx_px": 0.08, "motion_vector_error_px": 1.0, "boundary_motion_distance_px": 1.0, "grid_phase_motion_error_px": 0.24},
        ],
    )
    _write_rows(
        tmp_path,
        "model_b",
        [
            {"feature_family": "grids", "frame_b": 1, "expected_dx_px": 0.08, "motion_vector_error_px": 2.0, "boundary_motion_distance_px": 2.0, "grid_phase_motion_error_px": 0.24},
        ],
    )

    rows = r44d_family_diagnostics.load_all_rows(tmp_path, {"A": "model_a", "B": "model_b"})
    diagnostics = r44d_family_diagnostics.build_diagnostics(rows)
    discrim = {(r["feature_family"], r["metric"]): r for r in diagnostics["metric_discrimination"]}

    assert discrim[("grids", "grid_phase_motion_error_px")]["model_discriminative"] is False
    assert discrim[("grids", "motion_vector_error_px")]["model_discriminative"] is True

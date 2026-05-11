from pathlib import Path
import json
import sys

import numpy as np


REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT_DIR = REPO_ROOT / "Experiments" / "R44_UniversalBoundaryMotionFidelity" / "scripts"
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))


def _row(model: str, family: str, seq: int, frame_b: int, boundary: float, motion: float = 0.1) -> dict:
    return {
        "model": model,
        "recon_folder": model.lower().replace(" ", "_"),
        "stage": f"stage_{family}",
        "feature_family": family,
        "sequence_id": seq,
        "frame_a": frame_b - 1,
        "frame_b": frame_b,
        "expected_dx_px": 0.08,
        "expected_dy_px": 0.0,
        "motion_vector_error_px": motion,
        "boundary_motion_distance_px": boundary,
        "boundary_pred_px": 100,
        "boundary_expected_px": 100,
    }


def test_select_case_groups_keeps_named_contrasts():
    import r44f_diagnostics

    rows = []
    for model, boundary in {
        "R42 best": 2.0,
        "R44B from R42": 5.0,
        "R44E repair from R44B/R42": 4.5,
    }.items():
        rows.append(_row(model, "large_regions", 1, 6, boundary))
    for model, boundary in {
        "R42 best": 6.0,
        "R44B from R42": 3.0,
        "R44E repair from R44B/R42": 2.5,
    }.items():
        rows.append(_row(model, "mixed_fields", 2, 6, boundary))

    selected = r44f_diagnostics.select_case_groups(rows, cases_per_reason=1)
    reasons = {row["reason"] for row in selected}

    assert "r42_much_better_than_r44b" in reasons
    assert "r44e_repair_improves_mixed_or_region" in reasons


def test_metric_stress_detects_ordered_pixel_shifts():
    import r44f_diagnostics

    mask = np.zeros((48, 48), dtype=np.uint8)
    mask[10:38, 18] = 255
    mask[10:38, 32] = 255
    mask[10, 18:33] = 255
    mask[37, 18:33] = 255

    rows = r44f_diagnostics.metric_stress_for_mask(mask, feature_family="large_regions", sample_id="synthetic")
    by_variant = {row["variant"]: row["boundary_motion_distance_px"] for row in rows}

    assert by_variant["exact"] == 0.0
    assert by_variant["shift_1px"] < by_variant["shift_2px"] < by_variant["shift_5px"]


def test_boundary_amount_label_flags_thick_and_sparse_edges():
    import r44f_diagnostics

    assert r44f_diagnostics.boundary_amount_label(pred_px=180, expected_px=100) == "too_thick_or_noisy"
    assert r44f_diagnostics.boundary_amount_label(pred_px=45, expected_px=100) == "too_sparse_or_missing"
    assert r44f_diagnostics.boundary_amount_label(pred_px=105, expected_px=100) == "similar_density"


def test_json_safe_replaces_non_finite_numbers():
    import r44f_diagnostics

    payload = r44f_diagnostics.json_safe({"bad": float("inf"), "rows": [{"bad": float("nan"), "ok": 1.0}]})

    assert payload == {"bad": None, "rows": [{"bad": None, "ok": 1.0}]}
    json.dumps(payload, allow_nan=False)

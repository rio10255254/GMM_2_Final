from pathlib import Path
import sys

import torch


REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT_DIR = REPO_ROOT / "Experiments" / "R44_UniversalBoundaryMotionFidelity" / "scripts"
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))


def test_weighted_average_uses_primary_for_non_float_tensors():
    import r44h_family_average as r44h

    primary = {
        "conv.weight": torch.full((2, 2), 10.0),
        "bn.num_batches_tracked": torch.tensor(7, dtype=torch.long),
    }
    second = {
        "conv.weight": torch.full((2, 2), 20.0),
        "bn.num_batches_tracked": torch.tensor(99, dtype=torch.long),
    }
    third = {
        "conv.weight": torch.full((2, 2), 30.0),
        "bn.num_batches_tracked": torch.tensor(123, dtype=torch.long),
    }

    averaged = r44h.weighted_average_state_dicts(
        [primary, second, third],
        [0.5, 0.25, 0.25],
    )

    assert torch.allclose(averaged["conv.weight"], torch.full((2, 2), 17.5))
    assert averaged["bn.num_batches_tracked"].item() == 7


def test_family_average_rejects_mismatched_state_dicts():
    import r44h_family_average as r44h

    good = {"a": torch.ones(1)}
    bad = {"b": torch.ones(1)}

    try:
        r44h.validate_state_dicts_compatible([good, bad])
    except ValueError as exc:
        assert "state_dict keys differ" in str(exc)
    else:
        raise AssertionError("expected incompatible state_dicts to be rejected")


def test_stepa_gate_has_strong_weak_and_fail_verdicts():
    import r44h_family_average as r44h

    refs = r44h.StepAReferences(
        r44b_r42_target_shape_error=0.3384,
        r44b_r42_motion_error_px=0.3813,
        r44b_r40_target_shape_error=0.3110,
    )

    strong = r44h.stepa_gate_verdict(target_shape_error=0.3000, motion_error_px=0.4000, refs=refs)
    weak = r44h.stepa_gate_verdict(target_shape_error=0.3270, motion_error_px=0.4000, refs=refs)
    fail = r44h.stepa_gate_verdict(target_shape_error=0.3400, motion_error_px=0.4000, refs=refs)
    motion_fail = r44h.stepa_gate_verdict(target_shape_error=0.3000, motion_error_px=0.4300, refs=refs)

    assert strong["verdict"] == "strong_pass"
    assert weak["verdict"] == "weak_pass"
    assert fail["verdict"] == "fail"
    assert motion_fail["verdict"] == "fail_motion_regression"


def test_r44c_cleanliness_flags_static_heavy_as_clean_mixed_teacher():
    import r44h_family_average as r44h

    motion_rows = [
        {"model": "R44B from R42", "feature_family": "grids", "avg_motion_vector_error_px": 2.2457},
        {"model": "R44B from R42", "feature_family": "mixed_fields", "avg_motion_vector_error_px": 0.3000},
        {"model": "R44C static heavy", "feature_family": "grids", "avg_motion_vector_error_px": 2.3820},
        {"model": "R44C static heavy", "feature_family": "mixed_fields", "avg_motion_vector_error_px": 0.3120},
    ]
    target_shape_rows = [
        {"model": "R44B from R42", "target_shape_error_score": 0.3384},
        {"model": "R44C static heavy", "target_shape_error_score": 0.3314},
    ]
    shape_rows = [
        {"model": "R44B from R42", "feature_family": "mixed_fields", "avg_shape_error_score": 0.2230},
        {"model": "R44C static heavy", "feature_family": "mixed_fields", "avg_shape_error_score": 0.2181},
    ]

    result = r44h.assess_r44c_cleanliness(
        motion_family_rows=motion_rows,
        target_shape_rows=target_shape_rows,
        shape_score_rows=shape_rows,
    )

    assert result["clean_enough_for_mixed_teacher"] is True
    assert result["mixed_shape_improved"] is True
    assert result["max_motion_regression_pct"] < 10.0


def test_build_r44h_model_map_keeps_baselines_and_adds_stepa_candidates():
    import r44h_family_average as r44h

    model_map = r44h.build_r44h_model_map()

    assert model_map["R44B from R42"] == "r44_motion_from_r42_best_e24"
    assert model_map["R44C static heavy"] == "r44c_static_heavy_all_motion"
    assert model_map["R44H r44h_b42_b40_a030"] == "r44h_b42_b40_a030"

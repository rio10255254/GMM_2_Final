from __future__ import annotations

import importlib.util
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "launch_r63.py"


def load_module():
    spec = importlib.util.spec_from_file_location("launch_r63", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_factorial_variants_are_complete_and_psf_is_not_ablated():
    module = load_module()
    expected = {
        "full_control",
        "no_geometry_anchor",
        "no_motion_consistency",
        "no_geometry_no_motion",
        "no_shape_geometry",
        "no_global_boundary_position",
        "no_identity_boundary_guard",
        "no_region_boundary_teacher",
        "no_sequence_consistency",
        "no_known_shift_motion",
        "no_shift_equivariance",
        "no_boundary_residual_adapter",
        "no_raw_position_anchor",
        "no_quality_gate",
        "shift_safe_matched",
        "standard_upsample_matched",
    }
    assert set(module.VARIANTS) == expected
    for overrides in module.VARIANTS.values():
        assert not any("PSF" in key or "PHYS" in key for key in overrides)


def test_no_geometry_and_no_motion_is_exact_union():
    module = load_module()
    union = {**module.GEOMETRY_OFF, **module.MOTION_OFF}
    assert module.VARIANTS["no_geometry_no_motion"] == union


def test_group_removals_are_exact_unions_of_predeclared_components():
    module = load_module()
    assert module.GEOMETRY_OFF == {
        "BOUNDARY_GEOM_ENABLE": False,
        **module.SHAPE_GEOMETRY_OFF,
        **module.GLOBAL_POSITION_OFF,
        **module.IDENTITY_GUARD_OFF,
        **module.REGION_BOUNDARY_TEACHER_OFF,
    }
    assert module.MOTION_OFF == {
        **module.SEQUENCE_OFF,
        **module.KNOWN_SHIFT_MOTION_OFF,
        **module.SHIFT_EQUIVARIANCE_OFF,
    }
    assert module.VARIANTS["no_shape_geometry"] == module.SHAPE_GEOMETRY_OFF
    assert module.VARIANTS["no_global_boundary_position"] == module.GLOBAL_POSITION_OFF
    assert module.VARIANTS["no_identity_boundary_guard"] == module.IDENTITY_GUARD_OFF
    assert module.VARIANTS["no_region_boundary_teacher"] == module.REGION_BOUNDARY_TEACHER_OFF
    assert module.VARIANTS["no_sequence_consistency"] == module.SEQUENCE_OFF
    assert module.VARIANTS["no_known_shift_motion"] == module.KNOWN_SHIFT_MOTION_OFF
    assert module.VARIANTS["no_shift_equivariance"] == module.SHIFT_EQUIVARIANCE_OFF


def test_architecture_pair_has_identical_trainable_parameters():
    module = load_module()
    safe = module.VARIANTS["shift_safe_matched"]["TRAINABLE_NAME_PATTERNS"]
    standard = module.VARIANTS["standard_upsample_matched"]["TRAINABLE_NAME_PATTERNS"]
    assert safe == standard == module.ARCH_TRAINABLE


def test_output_module_removals_change_only_the_declared_output_path():
    module = load_module()
    assert module.VARIANTS["no_boundary_residual_adapter"] == {
        "BOUNDARY_RESIDUAL_ADAPTER_ENABLE": False
    }
    assert module.VARIANTS["no_raw_position_anchor"] == {
        "RAW_ANCHOR_OUTPUT_MODE": "none"
    }
    assert module.VARIANTS["no_quality_gate"] == {"QUALITY_GATE_ENABLE": False}

from __future__ import annotations

import importlib.util
from pathlib import Path

import numpy as np
import pandas as pd


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "aggregate_r63_results.py"


def load_module():
    spec = importlib.util.spec_from_file_location("aggregate_r63_results", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_factorial_component_and_architecture_effects_are_aligned():
    module = load_module()
    base_values = {
        "full_control": 1.0,
        "no_geometry_anchor": 2.0,
        "no_motion_consistency": 3.0,
        "no_geometry_no_motion": 4.0,
        "no_shape_geometry": 1.1,
        "no_global_boundary_position": 1.2,
        "no_identity_boundary_guard": 1.3,
        "no_region_boundary_teacher": 1.35,
        "no_sequence_consistency": 1.4,
        "no_known_shift_motion": 1.5,
        "no_shift_equivariance": 1.45,
        "no_boundary_residual_adapter": 1.25,
        "no_raw_position_anchor": 1.15,
        "no_quality_gate": 1.05,
        "shift_safe_matched": 1.1,
        "standard_upsample_matched": 1.6,
    }
    records = []
    for seed_offset, seed in enumerate(module.SEEDS):
        for unit_index in range(3):
            unit_offset = 0.01 * unit_index + 0.001 * seed_offset
            for variant, value in base_values.items():
                records.append(
                    {
                        "metric": "test_metric",
                        "stratum": "test_stratum",
                        "variant": variant,
                        "seed": seed,
                        "unit": f"U{unit_index}",
                        "value": value + unit_offset,
                        "aggregate": "mean",
                    }
                )
    units = pd.DataFrame(records)
    seed_summary, factorial, architecture, components = module.bootstrap_effects(units, 100)

    assert len(seed_summary) == len(module.SEEDS) * len(module.VARIANTS)
    assert set(factorial["mechanism"]) == {
        "geometry_anchor",
        "motion_consistency",
        "geometry_motion_interaction",
    }
    geometry = factorial.loc[factorial["mechanism"].eq("geometry_anchor")].iloc[0]
    motion = factorial.loc[factorial["mechanism"].eq("motion_consistency")].iloc[0]
    assert abs(geometry["mean_removal_penalty"] - 1.0) < 1e-12
    assert abs(motion["mean_removal_penalty"] - 2.0) < 1e-12

    assert len(architecture) == 1
    assert abs(architecture.iloc[0]["mean_standard_penalty"] - 0.5) < 1e-12
    assert set(components["component"]) == set(module.COMPONENTS)
    known_shift = components.loc[components["component"].eq("known_shift_motion")].iloc[0]
    assert abs(known_shift["mean_removal_penalty"] - 0.5) < 1e-12


def test_combined_displacement_stability_removes_command_size_difference():
    module = load_module()
    displacement = pd.DataFrame(
        {
            "sequence": ["step_0p5"] * 4 + ["step_1p0"] * 4,
            "method_boundary_dx_um": [0.49, 0.50, 0.51, 0.50, 0.99, 1.00, 1.01, 1.00],
        }
    )
    centered = module.add_sequence_centered_step(displacement)
    pooled_raw_sd = displacement["method_boundary_dx_um"].abs().mul(1000.0).std(ddof=1)
    pooled_stability_sd = centered["method_step_residual_nm_internal"].std(ddof=1)

    assert pooled_raw_sd > 250.0
    assert pooled_stability_sd < 10.0
    assert hasattr(next(centered.itertuples(index=False)), "method_step_residual_nm_internal")
    for _, group in centered.groupby("sequence"):
        assert abs(group["method_step_residual_nm_internal"].mean()) < 1e-12


def test_combined_bootstrap_preserves_each_sequence_count():
    module = load_module()
    index = pd.Index([f"A:F{i}" for i in range(3)] + [f"B:F{i}" for i in range(5)])
    positions = module.bootstrap_sample_positions(
        index, "all_sequences", np.random.default_rng(63)
    )
    sampled_labels = [str(index[position]).split(":", 1)[0] for position in positions]
    assert sampled_labels.count("A") == 3
    assert sampled_labels.count("B") == 5


def test_bootstrap_step_sd_recenters_each_sequence_after_resampling():
    module = load_module()
    series = pd.Series(
        [5.0, 5.0, -5.0, -5.0],
        index=["A:F1", "A:F1", "B:F2", "B:F2"],
    )
    combined = module.aggregate_series(
        series, "std", "displacement_step_magnitude_nm", "all_sequences"
    )
    uncentered = series.std(ddof=1)
    assert combined == 0.0
    assert uncentered > 5.0

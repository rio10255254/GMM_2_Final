"""Apply the predeclared R63 claim rules to the aggregate evidence tables."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd


EXPERIMENT_ROOT = Path(__file__).resolve().parents[1]
AGGREGATE_ROOT = EXPERIMENT_ROOT / "results" / "evaluation" / "aggregate"
GUARDRAIL_LIMIT_PCT = -15.0


def as_bool(value) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"true", "1", "yes"}


def select_one(table: pd.DataFrame, **filters) -> pd.Series:
    rows = table
    for key, value in filters.items():
        rows = rows.loc[rows[key].eq(value)]
    if len(rows) != 1:
        raise RuntimeError(f"Expected one row for {filters}, found {len(rows)}")
    return rows.iloc[0]


def primary_pass(row: pd.Series) -> bool:
    return as_bool(row["protocol_support"])


def expected_direction(row: pd.Series, effect_column: str = "mean_removal_penalty") -> bool:
    return float(row[effect_column]) > 0.0 and as_bool(row["direction_consistent_both_seeds"])


def guardrail_check(
    table: pd.DataFrame,
    *,
    selector_column: str,
    selector_value: str,
    percent_column: str,
    metrics: tuple[str, ...],
    strata: tuple[str, ...],
) -> tuple[bool, list[dict[str, object]]]:
    rows = table.loc[
        table[selector_column].eq(selector_value)
        & table["metric"].isin(metrics)
        & table["stratum"].isin(strata)
    ]
    expected_count = len(metrics) * len(strata)
    if len(rows) != expected_count:
        raise RuntimeError(
            f"Guardrail population mismatch for {selector_value}: "
            f"expected {expected_count}, found {len(rows)}"
        )
    details = []
    passed = True
    for row in rows.itertuples(index=False):
        percent = float(getattr(row, percent_column))
        row_passed = percent >= GUARDRAIL_LIMIT_PCT
        passed = passed and row_passed
        details.append(
            {
                "metric": row.metric,
                "stratum": row.stratum,
                "retained_vs_removed_guardrail_pct": percent,
                "passed": row_passed,
            }
        )
    return passed, details


def motion_direction_check(table: pd.DataFrame, selector_column: str, selector_value: str) -> bool:
    for metric in ("displacement_step_magnitude_nm", "displacement_within_grid_nm"):
        for stratum in ("50x_all", "20x_all"):
            row = select_one(
                table,
                **{
                    selector_column: selector_value,
                    "metric": metric,
                    "stratum": stratum,
                },
            )
            if not expected_direction(row):
                return False
    return True


def status(primary_direction: bool, supported: bool) -> str:
    if supported:
        return "supported"
    if primary_direction:
        return "suggestive"
    return "unsupported"


def main() -> None:
    factorial = pd.read_csv(AGGREGATE_ROOT / "factorial_effects.csv")
    components = pd.read_csv(AGGREGATE_ROOT / "component_effects.csv")
    architecture = pd.read_csv(AGGREGATE_ROOT / "architecture_effects.csv")
    claims: list[dict[str, object]] = []

    geometry_50 = select_one(
        factorial,
        mechanism="geometry_anchor",
        metric="cd_median_abs_error_nm",
        stratum="50x",
    )
    geometry_20 = select_one(
        factorial,
        mechanism="geometry_anchor",
        metric="cd_median_abs_error_nm",
        stratum="20x",
    )
    geometry_guard_pass, geometry_guard = guardrail_check(
        factorial,
        selector_column="mechanism",
        selector_value="geometry_anchor",
        percent_column="effect_vs_full_pct",
        metrics=("edge_width_10_90_nm", "outer_ringing_energy", "cd_bound_width_nm"),
        strata=("50x", "20x"),
    )
    geometry_supported = (
        primary_pass(geometry_50)
        and expected_direction(geometry_20)
        and geometry_guard_pass
    )
    claims.append(
        {
            "claim": "static_geometry_anchor",
            "status": status(expected_direction(geometry_50), geometry_supported),
            "supported": geometry_supported,
            "primary_effect": float(geometry_50["mean_removal_penalty"]),
            "primary_effect_pct": float(geometry_50["effect_vs_full_pct"]),
            "primary_ci_low": float(geometry_50["bootstrap_ci_low"]),
            "primary_ci_high": float(geometry_50["bootstrap_ci_high"]),
            "conditions": {
                "50x_primary_pass": primary_pass(geometry_50),
                "20x_direction_consistent": expected_direction(geometry_20),
                "guardrails_pass": geometry_guard_pass,
                "guardrails": geometry_guard,
            },
        }
    )

    motion_step = select_one(
        factorial,
        mechanism="motion_consistency",
        metric="displacement_step_magnitude_nm",
        stratum="all_sequences",
    )
    motion_grid = select_one(
        factorial,
        mechanism="motion_consistency",
        metric="displacement_within_grid_nm",
        stratum="all_sequences",
    )
    motion_command = select_one(
        factorial,
        mechanism="motion_consistency",
        metric="displacement_command_abs_error_nm",
        stratum="all_sequences",
    )
    motion_guard_pass = float(motion_command["effect_vs_full_pct"]) >= GUARDRAIL_LIMIT_PCT
    motion_mag_pass = motion_direction_check(factorial, "mechanism", "motion_consistency")
    motion_supported = (
        primary_pass(motion_step)
        and primary_pass(motion_grid)
        and motion_mag_pass
        and motion_guard_pass
    )
    claims.append(
        {
            "claim": "relative_motion_consistency",
            "status": status(
                expected_direction(motion_step) and expected_direction(motion_grid),
                motion_supported,
            ),
            "supported": motion_supported,
            "primary_effect": float(motion_step["mean_removal_penalty"]),
            "primary_effect_pct": float(motion_step["effect_vs_full_pct"]),
            "primary_ci_low": float(motion_step["bootstrap_ci_low"]),
            "primary_ci_high": float(motion_step["bootstrap_ci_high"]),
            "conditions": {
                "combined_step_sd_pass": primary_pass(motion_step),
                "combined_grid_disagreement_pass": primary_pass(motion_grid),
                "both_magnifications_direction_consistent": motion_mag_pass,
                "command_error_guardrail_pass": motion_guard_pass,
                "command_error_removal_penalty_pct": float(motion_command["effect_vs_full_pct"]),
            },
        }
    )

    geometry_components = (
        "shape_geometry",
        "global_boundary_position",
        "identity_boundary_guard",
        "region_boundary_teacher",
        "boundary_residual_adapter",
    )
    for component in geometry_components:
        primary = select_one(
            components,
            component=component,
            metric="cd_median_abs_error_nm",
            stratum="50x",
        )
        supporting = select_one(
            components,
            component=component,
            metric="cd_median_abs_error_nm",
            stratum="20x",
        )
        guard_pass, guard_details = guardrail_check(
            components,
            selector_column="component",
            selector_value=component,
            percent_column="effect_vs_full_pct",
            metrics=("edge_width_10_90_nm", "outer_ringing_energy", "cd_bound_width_nm"),
            strata=("50x", "20x"),
        )
        supported = primary_pass(primary) and expected_direction(supporting) and guard_pass
        claims.append(
            {
                "claim": component,
                "status": status(expected_direction(primary), supported),
                "supported": supported,
                "primary_effect": float(primary["mean_removal_penalty"]),
                "primary_effect_pct": float(primary["effect_vs_full_pct"]),
                "primary_ci_low": float(primary["bootstrap_ci_low"]),
                "primary_ci_high": float(primary["bootstrap_ci_high"]),
                "conditions": {
                    "50x_primary_pass": primary_pass(primary),
                    "20x_direction_consistent": expected_direction(supporting),
                    "guardrails_pass": guard_pass,
                    "guardrails": guard_details,
                },
            }
        )

    for component in (
        "adjacent_frame_consistency",
        "known_shift_motion",
        "shift_equivariance",
        "raw_position_anchor",
    ):
        step = select_one(
            components,
            component=component,
            metric="displacement_step_magnitude_nm",
            stratum="all_sequences",
        )
        grid = select_one(
            components,
            component=component,
            metric="displacement_within_grid_nm",
            stratum="all_sequences",
        )
        command = select_one(
            components,
            component=component,
            metric="displacement_command_abs_error_nm",
            stratum="all_sequences",
        )
        command_pass = float(command["effect_vs_full_pct"]) >= GUARDRAIL_LIMIT_PCT
        mag_pass = motion_direction_check(components, "component", component)
        supported = primary_pass(step) and primary_pass(grid) and mag_pass and command_pass
        claims.append(
            {
                "claim": component,
                "status": status(expected_direction(step) and expected_direction(grid), supported),
                "supported": supported,
                "primary_effect": float(step["mean_removal_penalty"]),
                "primary_effect_pct": float(step["effect_vs_full_pct"]),
                "primary_ci_low": float(step["bootstrap_ci_low"]),
                "primary_ci_high": float(step["bootstrap_ci_high"]),
                "conditions": {
                    "combined_step_sd_pass": primary_pass(step),
                    "combined_grid_disagreement_pass": primary_pass(grid),
                    "both_magnifications_direction_consistent": mag_pass,
                    "command_error_guardrail_pass": command_pass,
                    "command_error_removal_penalty_pct": float(command["effect_vs_full_pct"]),
                },
            }
        )

    quality_grid = select_one(
        components,
        component="quality_gate",
        metric="displacement_within_grid_nm",
        stratum="all_sequences",
    )
    quality_step = select_one(
        components,
        component="quality_gate",
        metric="displacement_step_magnitude_nm",
        stratum="all_sequences",
    )
    quality_command = select_one(
        components,
        component="quality_gate",
        metric="displacement_command_abs_error_nm",
        stratum="all_sequences",
    )
    quality_bound_50 = select_one(
        components,
        component="quality_gate",
        metric="cd_bound_width_nm",
        stratum="50x",
    )
    quality_bound_20 = select_one(
        components,
        component="quality_gate",
        metric="cd_bound_width_nm",
        stratum="20x",
    )
    quality_guard_pass, quality_guard_details = guardrail_check(
        components,
        selector_column="component",
        selector_value="quality_gate",
        percent_column="effect_vs_full_pct",
        metrics=("edge_width_10_90_nm", "outer_ringing_energy"),
        strata=("50x", "20x"),
    )
    quality_motion_mag_pass = motion_direction_check(components, "component", "quality_gate")
    quality_bound_pass = expected_direction(quality_bound_50) and expected_direction(quality_bound_20)
    quality_command_pass = (
        float(quality_command["effect_vs_full_pct"]) >= GUARDRAIL_LIMIT_PCT
    )
    quality_supported = (
        primary_pass(quality_grid)
        and primary_pass(quality_step)
        and quality_motion_mag_pass
        and quality_bound_pass
        and quality_command_pass
        and quality_guard_pass
    )
    claims.append(
        {
            "claim": "quality_gate",
            "status": status(
                expected_direction(quality_grid) and expected_direction(quality_step),
                quality_supported,
            ),
            "supported": quality_supported,
            "primary_effect": float(quality_grid["mean_removal_penalty"]),
            "primary_effect_pct": float(quality_grid["effect_vs_full_pct"]),
            "primary_ci_low": float(quality_grid["bootstrap_ci_low"]),
            "primary_ci_high": float(quality_grid["bootstrap_ci_high"]),
            "conditions": {
                "combined_grid_disagreement_pass": primary_pass(quality_grid),
                "combined_step_sd_pass": primary_pass(quality_step),
                "both_magnifications_motion_direction_consistent": quality_motion_mag_pass,
                "both_magnifications_cd_bound_direction_consistent": quality_bound_pass,
                "command_error_guardrail_pass": quality_command_pass,
                "edge_and_ringing_guardrails_pass": quality_guard_pass,
                "edge_and_ringing_guardrails": quality_guard_details,
            },
        }
    )

    shift_vector = select_one(
        architecture,
        comparison="standard_minus_shift_safe",
        metric="synthetic_vector_error_px",
        stratum="primary_subpixel",
    )
    shift_radius = select_one(
        architecture,
        comparison="standard_minus_shift_safe",
        metric="synthetic_edge_radius_change_px",
        stratum="primary_subpixel",
    )
    shift_p95 = select_one(
        architecture,
        comparison="standard_minus_shift_safe",
        metric="synthetic_vector_p95_error_px",
        stratum="primary_subpixel",
    )
    shift_direction_spread = select_one(
        architecture,
        comparison="standard_minus_shift_safe",
        metric="synthetic_direction_spread_px",
        stratum="primary_subpixel",
    )
    shift_ringing_change = select_one(
        architecture,
        comparison="standard_minus_shift_safe",
        metric="synthetic_ringing_change_abs",
        stratum="primary_subpixel",
    )
    ringing_pass, ringing_details = guardrail_check(
        architecture,
        selector_column="comparison",
        selector_value="standard_minus_shift_safe",
        percent_column="effect_vs_shift_safe_pct",
        metrics=("outer_ringing_energy",),
        strata=("50x", "20x"),
    )
    radius_pass = float(shift_radius["effect_vs_shift_safe_pct"]) >= GUARDRAIL_LIMIT_PCT
    p95_pass = float(shift_p95["effect_vs_shift_safe_pct"]) >= GUARDRAIL_LIMIT_PCT
    direction_spread_pass = (
        float(shift_direction_spread["effect_vs_shift_safe_pct"]) >= GUARDRAIL_LIMIT_PCT
    )
    shift_ringing_change_pass = (
        float(shift_ringing_change["effect_vs_shift_safe_pct"]) >= GUARDRAIL_LIMIT_PCT
    )
    shift_supported = (
        primary_pass(shift_vector)
        and radius_pass
        and p95_pass
        and direction_spread_pass
        and shift_ringing_change_pass
        and ringing_pass
    )
    claims.append(
        {
            "claim": "shift_safe_upsampling",
            "status": status(
                expected_direction(shift_vector, "mean_standard_penalty"),
                shift_supported,
            ),
            "supported": shift_supported,
            "primary_effect": float(shift_vector["mean_standard_penalty"]),
            "primary_effect_pct": float(shift_vector["effect_vs_shift_safe_pct"]),
            "primary_ci_low": float(shift_vector["bootstrap_ci_low"]),
            "primary_ci_high": float(shift_vector["bootstrap_ci_high"]),
            "conditions": {
                "primary_subpixel_vector_pass": primary_pass(shift_vector),
                "edge_radius_guardrail_pass": radius_pass,
                "direction_p95_guardrail_pass": p95_pass,
                "direction_spread_guardrail_pass": direction_spread_pass,
                "shift_ringing_change_guardrail_pass": shift_ringing_change_pass,
                "ringing_guardrails_pass": ringing_pass,
                "ringing_guardrails": ringing_details,
            },
        }
    )

    table = pd.DataFrame(
        [
            {
                key: json.dumps(value, ensure_ascii=False) if key == "conditions" else value
                for key, value in claim.items()
            }
            for claim in claims
        ]
    )
    output_table = AGGREGATE_ROOT / "claim_support_audit.csv"
    table.to_csv(output_table, index=False, float_format="%.12g")
    output_json = AGGREGATE_ROOT / "claim_support_audit.json"
    output_json.write_text(
        json.dumps(
            {
                "guardrail_limit_pct": GUARDRAIL_LIMIT_PCT,
                "claims": claims,
            },
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    print(table.to_string(index=False))


if __name__ == "__main__":
    main()

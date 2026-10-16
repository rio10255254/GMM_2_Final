"""Aggregate R63 metrics into factorial, architecture, and support tables."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd


EXPERIMENT_ROOT = Path(__file__).resolve().parents[1]
METRIC_ROOT = EXPERIMENT_ROOT / "results" / "evaluation" / "metrics"
OUTPUT_ROOT = EXPERIMENT_ROOT / "results" / "evaluation" / "aggregate"
VARIANTS = (
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
)
SEEDS = (1261200, 1261217)
FACTORIAL = (
    "full_control",
    "no_geometry_anchor",
    "no_motion_consistency",
    "no_geometry_no_motion",
)
ARCHITECTURE = ("shift_safe_matched", "standard_upsample_matched")
COMPONENTS = {
    "shape_geometry": "no_shape_geometry",
    "global_boundary_position": "no_global_boundary_position",
    "identity_boundary_guard": "no_identity_boundary_guard",
    "region_boundary_teacher": "no_region_boundary_teacher",
    "adjacent_frame_consistency": "no_sequence_consistency",
    "known_shift_motion": "no_known_shift_motion",
    "shift_equivariance": "no_shift_equivariance",
    "boundary_residual_adapter": "no_boundary_residual_adapter",
    "raw_position_anchor": "no_raw_position_anchor",
    "quality_gate": "no_quality_gate",
}


def metric_dir(variant: str, seed: int) -> Path:
    return METRIC_ROOT / variant / f"seed{seed}"


def add_sequence_centered_step(displacement: pd.DataFrame) -> pd.DataFrame:
    """Add a within-sequence step residual for the displacement-stability SD.

    The four real sequences contain two different commanded step sizes.  Pooling
    their absolute step magnitudes directly would make the 0.5-vs-1.0 um command
    difference look like instability.  Centering within each sequence preserves
    each sequence's own SD while allowing magnification and all-sequence strata
    to estimate only within-sequence variation.  Command accuracy remains a
    separate absolute-error endpoint.
    """
    result = displacement.copy()
    result["method_step_nm_internal"] = result["method_boundary_dx_um"].abs() * 1000.0
    result["method_step_residual_nm_internal"] = result["method_step_nm_internal"] - result.groupby(
        "sequence"
    )["method_step_nm_internal"].transform("mean")
    return result


def load_units() -> pd.DataFrame:
    records: list[dict[str, object]] = []
    for variant in VARIANTS:
        for seed in SEEDS:
            root = metric_dir(variant, seed)
            static_measurements = pd.read_csv(root / "static_cd" / "static_cd_per_measurement.csv")
            static_method = static_measurements.loc[static_measurements["method"].eq("Method")]
            for (magnification, pillar), group in static_method.groupby(["magnification", "pillar_id"]):
                records.append({"metric": "cd_median_abs_error_nm", "stratum": magnification, "variant": variant, "seed": seed, "unit": f"P{pillar}", "value": float(group["abs_error_nm"].median()), "aggregate": "median"})
                records.append({"metric": "cd_bound_width_nm", "stratum": magnification, "variant": variant, "seed": seed, "unit": f"P{pillar}", "value": float((group["diameter_um"].max() - group["diameter_um"].min()) * 1000.0), "aggregate": "median"})

            edge = pd.read_csv(root / "static_cd" / "static_edge_guardrails.csv")
            edge = edge.loc[edge["method"].eq("Method")]
            for row in edge.itertuples(index=False):
                records.append({"metric": "edge_width_10_90_nm", "stratum": row.magnification, "variant": variant, "seed": seed, "unit": f"P{row.pillar_id}", "value": float(row.edge_width_10_90_nm), "aggregate": "median"})
                records.append({"metric": "outer_ringing_energy", "stratum": row.magnification, "variant": variant, "seed": seed, "unit": f"P{row.pillar_id}", "value": float(row.outer_ringing_energy), "aggregate": "median"})

            synthetic = pd.read_csv(root / "synthetic_shift" / "synthetic_shift_per_case.csv")
            synthetic = synthetic.loc[synthetic["method"].eq(variant)]
            for (magnitude, pillar), group in synthetic.groupby(["magnitude_px", "pillar_id"]):
                source_stratum = f"{magnitude:g}px"
                source_unit = f"P{pillar}"
                vector_value = float(group["vector_error_px"].median())
                vector_p95 = float(np.percentile(group["vector_error_px"].to_numpy(float), 95))
                direction_spread = float(
                    group["vector_error_px"].max() - group["vector_error_px"].min()
                )
                radius_value = float(group["edge_radius_change_px"].abs().median())
                shift_ringing_value = float(group["ringing_change"].abs().median())
                records.append({"metric": "synthetic_vector_error_px", "stratum": source_stratum, "variant": variant, "seed": seed, "unit": source_unit, "value": vector_value, "aggregate": "median"})
                records.append({"metric": "synthetic_vector_p95_error_px", "stratum": source_stratum, "variant": variant, "seed": seed, "unit": source_unit, "value": vector_p95, "aggregate": "median"})
                records.append({"metric": "synthetic_direction_spread_px", "stratum": source_stratum, "variant": variant, "seed": seed, "unit": source_unit, "value": direction_spread, "aggregate": "median"})
                records.append({"metric": "synthetic_edge_radius_change_px", "stratum": source_stratum, "variant": variant, "seed": seed, "unit": source_unit, "value": radius_value, "aggregate": "median"})
                records.append({"metric": "synthetic_ringing_change_abs", "stratum": source_stratum, "variant": variant, "seed": seed, "unit": source_unit, "value": shift_ringing_value, "aggregate": "median"})
                if any(
                    np.isclose(float(magnitude), target)
                    for target in (0.08, 0.4, 0.8)
                ):
                    combined_unit = f"{source_stratum}:{source_unit}"
                    records.append({"metric": "synthetic_vector_error_px", "stratum": "primary_subpixel", "variant": variant, "seed": seed, "unit": combined_unit, "value": vector_value, "aggregate": "median"})
                    records.append({"metric": "synthetic_vector_p95_error_px", "stratum": "primary_subpixel", "variant": variant, "seed": seed, "unit": combined_unit, "value": vector_p95, "aggregate": "median"})
                    records.append({"metric": "synthetic_direction_spread_px", "stratum": "primary_subpixel", "variant": variant, "seed": seed, "unit": combined_unit, "value": direction_spread, "aggregate": "median"})
                    records.append({"metric": "synthetic_edge_radius_change_px", "stratum": "primary_subpixel", "variant": variant, "seed": seed, "unit": combined_unit, "value": radius_value, "aggregate": "median"})
                    records.append({"metric": "synthetic_ringing_change_abs", "stratum": "primary_subpixel", "variant": variant, "seed": seed, "unit": combined_unit, "value": shift_ringing_value, "aggregate": "median"})

            displacement = pd.read_csv(root / "displacement" / "displacement_per_step_top30.csv")
            if not displacement["method_valid"].astype(str).str.lower().isin({"true", "1"}).all():
                invalid = displacement.loc[~displacement["method_valid"].astype(str).str.lower().isin({"true", "1"})]
                raise RuntimeError(f"{variant}/seed{seed}: {len(invalid)} invalid locked displacement steps")
            displacement = add_sequence_centered_step(displacement)
            for row in displacement.itertuples(index=False):
                sequence = str(row.sequence)
                unit = f"F{int(row.end_frame_index):03d}"
                command_error = abs(abs(float(row.method_boundary_dx_um)) - float(row.nominal_step_um)) * 1000.0
                magnification_stratum = "50x_all" if sequence.startswith("50x") else "20x_all"
                for stratum in (sequence, magnification_stratum, "all_sequences"):
                    aggregate_unit = unit if stratum == sequence else f"{sequence}:{unit}"
                    records.append({"metric": "displacement_command_abs_error_nm", "stratum": stratum, "variant": variant, "seed": seed, "unit": aggregate_unit, "value": command_error, "aggregate": "mean"})
                    records.append({"metric": "displacement_within_grid_nm", "stratum": stratum, "variant": variant, "seed": seed, "unit": aggregate_unit, "value": float(row.method_within_grid_nm), "aggregate": "mean"})
                    records.append({"metric": "displacement_step_magnitude_nm", "stratum": stratum, "variant": variant, "seed": seed, "unit": aggregate_unit, "value": float(row.method_step_residual_nm_internal), "aggregate": "std"})
    units = pd.DataFrame(records)
    if not np.isfinite(units["value"].to_numpy(float)).all():
        raise RuntimeError("Non-finite aggregate unit values")
    return units


def aggregate_values(values: np.ndarray, method: str) -> float:
    if method == "mean":
        return float(np.mean(values))
    if method == "median":
        return float(np.median(values))
    if method == "std":
        return float(np.std(values, ddof=1))
    raise ValueError(method)


def aggregate_series(
    series: pd.Series,
    method: str,
    metric: str,
    stratum: str,
) -> float:
    values = series.to_numpy(float)
    if (
        method == "std"
        and metric == "displacement_step_magnitude_nm"
        and stratum in {"all_sequences", "50x_all", "20x_all"}
    ):
        labels = np.asarray([str(value).split(":", 1)[0] for value in series.index])
        values = values.copy()
        for label in dict.fromkeys(labels.tolist()):
            selected = labels == label
            values[selected] -= float(np.mean(values[selected]))
    return aggregate_values(values, method)


def aligned_pivot(group: pd.DataFrame, variants: tuple[str, ...]) -> tuple[pd.DataFrame, str]:
    methods = group["aggregate"].unique().tolist()
    if len(methods) != 1:
        raise RuntimeError(f"Mixed aggregation rules: {methods}")
    pivot = group.pivot(index="unit", columns="variant", values="value")
    missing = set(variants) - set(pivot.columns)
    if missing:
        raise RuntimeError(f"Missing variants: {sorted(missing)}")
    pivot = pivot[list(variants)].dropna()
    if len(pivot) != group.loc[group["variant"].eq(variants[0]), "unit"].nunique():
        raise RuntimeError("Unit mismatch across variants")
    return pivot, methods[0]


def bootstrap_sample_positions(
    index: pd.Index,
    stratum: str,
    rng: np.random.Generator,
) -> np.ndarray:
    """Return paired bootstrap positions, stratified for combined populations."""
    labels = np.asarray([str(value).split(":", 1)[0] for value in index])
    combined = stratum in {"all_sequences", "50x_all", "20x_all", "primary_subpixel"}
    if not combined:
        return rng.integers(0, len(index), size=len(index))
    sampled: list[np.ndarray] = []
    for label in dict.fromkeys(labels.tolist()):
        positions = np.flatnonzero(labels == label)
        sampled.append(rng.choice(positions, size=len(positions), replace=True))
    return np.concatenate(sampled)


def factorial_effect(values: dict[str, float]) -> tuple[float, float, float]:
    full = values["full_control"]
    no_g = values["no_geometry_anchor"]
    no_m = values["no_motion_consistency"]
    neither = values["no_geometry_no_motion"]
    geometry = 0.5 * ((no_g - full) + (neither - no_m))
    motion = 0.5 * ((no_m - full) + (neither - no_g))
    interaction = neither - no_g - no_m + full
    return geometry, motion, interaction


def bootstrap_effects(
    units: pd.DataFrame,
    bootstrap_count: int,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    rng = np.random.default_rng(630016)
    seed_rows: list[dict[str, object]] = []
    factorial_rows: list[dict[str, object]] = []
    architecture_rows: list[dict[str, object]] = []
    component_rows: list[dict[str, object]] = []
    for (metric, stratum), metric_group in units.groupby(["metric", "stratum"], sort=False):
        aggregate = str(metric_group["aggregate"].iloc[0])
        seed_factorial: dict[int, tuple[float, float, float, float]] = {}
        seed_arch: dict[int, tuple[float, float]] = {}
        seed_components: dict[int, dict[str, float]] = {}
        aligned_by_seed: dict[int, pd.DataFrame] = {}
        for seed in SEEDS:
            seed_group = metric_group.loc[metric_group["seed"].eq(seed)]
            pivot, _ = aligned_pivot(seed_group, VARIANTS)
            aligned_by_seed[seed] = pivot
            values = {
                variant: aggregate_series(pivot[variant], aggregate, metric, stratum)
                for variant in VARIANTS
            }
            geometry, motion, interaction = factorial_effect(values)
            architecture = values["standard_upsample_matched"] - values["shift_safe_matched"]
            seed_factorial[seed] = (geometry, motion, interaction, values["full_control"])
            seed_arch[seed] = (architecture, values["shift_safe_matched"])
            seed_components[seed] = {
                component: values[variant] - values["full_control"]
                for component, variant in COMPONENTS.items()
            }
            for variant, value in values.items():
                seed_rows.append({"metric": metric, "stratum": stratum, "seed": seed, "variant": variant, "value": value, "unit_count": len(pivot), "aggregate": aggregate})

        reference_index = aligned_by_seed[SEEDS[0]].index
        for seed in SEEDS[1:]:
            if not aligned_by_seed[seed].index.equals(reference_index):
                raise RuntimeError(
                    f"Evaluation-unit mismatch across seeds for {metric}/{stratum}"
                )

        boot_geometry: list[float] = []
        boot_motion: list[float] = []
        boot_interaction: list[float] = []
        boot_architecture: list[float] = []
        boot_components: dict[str, list[float]] = {component: [] for component in COMPONENTS}
        for _ in range(bootstrap_count):
            sampled_index = bootstrap_sample_positions(reference_index, stratum, rng)
            per_seed_factorial = []
            per_seed_arch = []
            for seed in SEEDS:
                pivot = aligned_by_seed[seed]
                sampled = pivot.iloc[sampled_index]
                values = {
                    variant: aggregate_series(sampled[variant], aggregate, metric, stratum)
                    for variant in VARIANTS
                }
                per_seed_factorial.append(factorial_effect(values))
                per_seed_arch.append(values["standard_upsample_matched"] - values["shift_safe_matched"])
                for component, variant in COMPONENTS.items():
                    boot_components[component].append(values[variant] - values["full_control"])
            boot_geometry.append(float(np.mean([value[0] for value in per_seed_factorial])))
            boot_motion.append(float(np.mean([value[1] for value in per_seed_factorial])))
            boot_interaction.append(float(np.mean([value[2] for value in per_seed_factorial])))
            boot_architecture.append(float(np.mean(per_seed_arch)))

        def ci(values: list[float]) -> tuple[float, float]:
            return float(np.percentile(values, 2.5)), float(np.percentile(values, 97.5))

        geometry_seed = [seed_factorial[seed][0] for seed in SEEDS]
        motion_seed = [seed_factorial[seed][1] for seed in SEEDS]
        interaction_seed = [seed_factorial[seed][2] for seed in SEEDS]
        full_reference = float(np.mean([seed_factorial[seed][3] for seed in SEEDS]))
        for mechanism, values, boot in (
            ("geometry_anchor", geometry_seed, boot_geometry),
            ("motion_consistency", motion_seed, boot_motion),
            ("geometry_motion_interaction", interaction_seed, boot_interaction),
        ):
            low, high = ci(boot)
            effect = float(np.mean(values))
            percent = 100.0 * effect / full_reference if abs(full_reference) > 1e-12 else float("nan")
            direction_consistent = bool(all(value > 0 for value in values))
            supported = bool(
                mechanism != "geometry_motion_interaction"
                and direction_consistent
                and percent >= 10.0
                and low > 0.0
            )
            factorial_rows.append({
                "metric": metric,
                "stratum": stratum,
                "mechanism": mechanism,
                "effect_seed1261200": values[0],
                "effect_seed1261217": values[1],
                "mean_removal_penalty": effect,
                "effect_vs_full_pct": percent,
                "bootstrap_ci_low": low,
                "bootstrap_ci_high": high,
                "direction_consistent_both_seeds": direction_consistent,
                "protocol_support": supported,
            })

        arch_values = [seed_arch[seed][0] for seed in SEEDS]
        shift_reference = float(np.mean([seed_arch[seed][1] for seed in SEEDS]))
        low, high = ci(boot_architecture)
        effect = float(np.mean(arch_values))
        percent = 100.0 * effect / shift_reference if abs(shift_reference) > 1e-12 else float("nan")
        architecture_rows.append({
            "metric": metric,
            "stratum": stratum,
            "comparison": "standard_minus_shift_safe",
            "effect_seed1261200": arch_values[0],
            "effect_seed1261217": arch_values[1],
            "mean_standard_penalty": effect,
            "effect_vs_shift_safe_pct": percent,
            "bootstrap_ci_low": low,
            "bootstrap_ci_high": high,
            "direction_consistent_both_seeds": bool(all(value > 0 for value in arch_values)),
            "protocol_support": bool(all(value > 0 for value in arch_values) and percent >= 10.0 and low > 0.0),
        })

        for component, variant in COMPONENTS.items():
            values = [seed_components[seed][component] for seed in SEEDS]
            # Bootstrap values were appended once per seed and iteration. Average the
            # matched seeds within each bootstrap iteration before taking the CI.
            flat = np.asarray(boot_components[component], dtype=float).reshape(bootstrap_count, len(SEEDS))
            boot = flat.mean(axis=1)
            low, high = ci(boot.tolist())
            effect = float(np.mean(values))
            percent = 100.0 * effect / full_reference if abs(full_reference) > 1e-12 else float("nan")
            direction_consistent = bool(all(value > 0 for value in values))
            component_rows.append({
                "metric": metric,
                "stratum": stratum,
                "component": component,
                "removed_variant": variant,
                "effect_seed1261200": values[0],
                "effect_seed1261217": values[1],
                "mean_removal_penalty": effect,
                "effect_vs_full_pct": percent,
                "bootstrap_ci_low": low,
                "bootstrap_ci_high": high,
                "direction_consistent_both_seeds": direction_consistent,
                "protocol_support": bool(direction_consistent and percent >= 10.0 and low > 0.0),
            })
    return (
        pd.DataFrame(seed_rows),
        pd.DataFrame(factorial_rows),
        pd.DataFrame(architecture_rows),
        pd.DataFrame(component_rows),
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--bootstrap", type=int, default=4000)
    args = parser.parse_args()
    units = load_units()
    seed_summary, factorial, architecture, components = bootstrap_effects(units, args.bootstrap)
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    units.to_csv(OUTPUT_ROOT / "analysis_units.csv", index=False, float_format="%.12g")
    seed_summary.to_csv(OUTPUT_ROOT / "candidate_seed_summary.csv", index=False, float_format="%.12g")
    factorial.to_csv(OUTPUT_ROOT / "factorial_effects.csv", index=False, float_format="%.12g")
    architecture.to_csv(OUTPUT_ROOT / "architecture_effects.csv", index=False, float_format="%.12g")
    components.to_csv(OUTPUT_ROOT / "component_effects.csv", index=False, float_format="%.12g")
    verdict = {
        "bootstrap_count": args.bootstrap,
        "positive_effect_definition": "removing the mechanism increases a lower-is-better metric",
        "factorial_supported_rows": factorial.loc[factorial["protocol_support"]].to_dict("records"),
        "architecture_supported_rows": architecture.loc[architecture["protocol_support"]].to_dict("records"),
        "component_supported_rows": components.loc[components["protocol_support"]].to_dict("records"),
        "claim_rule": "A thesis claim requires cross-seed direction consistency, at least 10 percent effect, CI above zero, and guardrail review.",
    }
    (OUTPUT_ROOT / "aggregate_verdict.json").write_text(
        json.dumps(verdict, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(factorial.loc[factorial["protocol_support"]].to_string(index=False))
    print(architecture.loc[architecture["protocol_support"]].to_string(index=False))
    print(components.loc[components["protocol_support"]].to_string(index=False))


if __name__ == "__main__":
    main()

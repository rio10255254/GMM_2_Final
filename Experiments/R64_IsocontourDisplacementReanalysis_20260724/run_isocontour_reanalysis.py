from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
PROJECT_ROOT = Path(__file__).resolve().parents[2]


ROOT = Path(str(PROJECT_ROOT))
FORMAL = (
    ROOT
    / "Thesis_MOSR_Evidence"
    / "Final_Data_Figures"
    / "01_CURRENT_THESIS_RESULTS_V42_CENTER9"
)
FIGURE_ROOT = (
    ROOT
    / "Thesis_MOSR_Evidence"
    / "Final_Data_Figures"
    / "06_DISPLACEMENT_EXPERIMENTS_ISOCONTOUR_20260724"
)
R63 = ROOT / "Experiments" / "R63_CausalBoundaryMotionAblation"
MODERN = (
    ROOT
    / "LabSystem_MOSR"
    / "Experiments"
    / "Modern_Restoration_Benchmarks_20260719"
)
WIENER = (
    ROOT
    / "Thesis_MOSR_Evidence"
    / "Final_Data_Figures"
    / "04_V42_NEURAL_NETWORK_RESULTS"
    / "source_validation"
    / "wiener_baseline_20260715"
)
TOP30 = (
    ROOT
    / "Thesis_MOSR_Evidence"
    / "Final_Data_Figures"
    / "04_V42_NEURAL_NETWORK_RESULTS"
    / "tables"
    / "top30_raw_motion_selection.csv"
)
PILLAR_CONFIG = FORMAL / "config" / "sequence_center9_50x20x.json"
VIA_CONFIG = MODERN / "evaluation" / "via_reference" / "via_center9_reference.json"
MOSR_RECON = (
    ROOT
    / "Thesis_MOSR_Evidence"
    / "Final_Data_Figures"
    / "02_V42_E120_SOURCE_MATERIAL"
    / "reconstructions"
)
AUDIT_SCRIPTS = FORMAL / "scripts"
if str(AUDIT_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(AUDIT_SCRIPTS))

from audit_all_displacement_sequences import (  # noqa: E402
    APPROVED_SEQUENCES,
    _load_mapping,
    _raw_segment_measurements,
)


def load_boundary_module():
    path = MODERN / "analyze_isocontour_boundary_displacement.py"
    spec = importlib.util.spec_from_file_location("isocontour_boundary", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


ISO = load_boundary_module()

SEEDS = (1261200, 1261217)
ABLATION_VARIANTS = (
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
ABLATION_COMPARISONS = {
    "geometry_anchor": ("full_control", "no_geometry_anchor"),
    "motion_consistency": ("full_control", "no_motion_consistency"),
    "geometry_and_motion": ("full_control", "no_geometry_no_motion"),
    "shape_geometry": ("full_control", "no_shape_geometry"),
    "global_boundary_position": ("full_control", "no_global_boundary_position"),
    "identity_boundary_guard": ("full_control", "no_identity_boundary_guard"),
    "region_boundary_teacher": ("full_control", "no_region_boundary_teacher"),
    "adjacent_frame_consistency": ("full_control", "no_sequence_consistency"),
    "known_shift_motion": ("full_control", "no_known_shift_motion"),
    "shift_equivariance": ("full_control", "no_shift_equivariance"),
    "boundary_residual_adapter": ("full_control", "no_boundary_residual_adapter"),
    "raw_position_anchor": ("full_control", "no_raw_position_anchor"),
    "quality_gate": ("full_control", "no_quality_gate"),
    "shift_safe_upsampling": ("shift_safe_matched", "standard_upsample_matched"),
}


def read_configs(path: Path, morphology: str) -> dict[str, dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))["sequences"]
    if morphology == "pillar":
        return payload
    converted: dict[str, dict[str, Any]] = {}
    for sequence_name, source in payload.items():
        item = dict(source)
        item["min_valid_pillars"] = int(item.pop("min_valid_features"))
        item["min_edge_strength"] = 1.0
        item["centers"] = [
            [index, center["x"], center["y"]]
            for index, center in enumerate(item["centers"], start=1)
        ]
        converted[sequence_name] = item
    return converted


def locked_selection() -> pd.DataFrame:
    selection = pd.read_csv(TOP30)
    selection = selection.loc[
        selection["top30_raw_motion_selected"].astype(bool)
        & selection["sequence"].isin(APPROVED_SEQUENCES)
    ].copy()
    counts = selection.groupby("sequence").size()
    if set(counts.index) != set(APPROVED_SEQUENCES) or not counts.eq(30).all():
        raise RuntimeError("The locked population must contain exactly 30 steps per sequence")
    return selection


def method_directory(method: str, sequence: str, sequence_cfg: dict[str, Any]) -> Path:
    if method == "Raw":
        return Path(sequence_cfg["raw_dir"])
    if method == "Wiener":
        wiener_cfg = json.loads(
            (WIENER / "wiener_displacement_config.json").read_text(encoding="utf-8")
        )["sequences"][sequence]
        return Path(wiener_cfg["v42_dir"])
    if method == "MOSR":
        mapped = {
            "50x_x_0p5um": "50x_0p5um",
            "50x_x_1um": "50x_1um",
            "20x_0p5um": "20x_0p5um",
            "20x_1um": "20x_1um",
        }[sequence]
        return MOSR_RECON / mapped
    raise KeyError(method)


def measure_one(
    *,
    label: str,
    image_dir: Path,
    sequence_name: str,
    sequence_cfg: dict[str, Any],
    raw_images: list[np.ndarray],
    sessions: pd.DataFrame,
    runtime: dict[int, dict[str, Any]],
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    frame_count = int(sequence_cfg["frame_count"])
    images = raw_images if label == "Raw" else ISO.load_frames(image_dir, frame_count)
    initial_ids = [str(int(row[0])) for row in sequence_cfg["centers"]]
    frames_out: list[pd.DataFrame] = []
    steps_out: list[pd.DataFrame] = []
    features_out: list[pd.DataFrame] = []
    for session_id, start_frame, end_frame in ISO.session_bounds(sessions):
        state = runtime[session_id]
        raw_tracking = state.get("raw_result")
        shifted_centers = state.get("shifted_centers")
        if raw_tracking is None or shifted_centers is None or end_frame <= start_frame:
            continue
        frames, steps, features, _ = ISO.measure_method_session(
            images[start_frame : end_frame + 1],
            initial_centers=np.asarray(shifted_centers, dtype=float),
            feature_ids=initial_ids,
            prediction_shifts=raw_tracking.prediction_shifts,
            radius_px=float(sequence_cfg["radius_px"]),
            search_radius_px=float(sequence_cfg["search_radius_px"]),
            expected_dx_px=float(sequence_cfg["expected_signed_dx_px"]),
            min_valid_features=int(sequence_cfg["min_valid_pillars"]),
            global_start_frame=start_frame,
        )
        for table in (frames, steps, features):
            table["session_id"] = session_id
        frames_out.append(frames)
        steps_out.append(steps)
        features_out.append(features)
    frame_table = pd.concat(frames_out, ignore_index=True)
    step_table = pd.concat(steps_out, ignore_index=True)
    feature_table = pd.concat(features_out, ignore_index=True)
    scale = float(sequence_cfg["object_um_per_px"])
    expected_signed_um = float(sequence_cfg["expected_signed_dx_px"]) * scale
    step_table["sequence"] = sequence_name
    step_table["magnification"] = sequence_cfg["magnification"]
    step_table["method"] = label
    step_table["expected_signed_step_um"] = expected_signed_um
    step_table["measured_signed_step_um"] = step_table["signed_step_px"] * scale
    step_table["measured_step_um"] = step_table["measured_signed_step_um"].abs()
    step_table["reference_step_um"] = abs(expected_signed_um)
    step_table["signed_error_nm"] = (
        step_table["measured_step_um"] - step_table["reference_step_um"]
    ) * 1000.0
    step_table["absolute_error_nm"] = step_table["signed_error_nm"].abs()
    step_table["within_grid_mad_nm"] = (
        step_table["within_grid_mad_px"] * scale * 1000.0
    )
    step_table["threshold_sensitivity_nm"] = (
        step_table["threshold_sensitivity_px"] * scale * 1000.0
    )
    feature_table["sequence"] = sequence_name
    feature_table["magnification"] = sequence_cfg["magnification"]
    feature_table["method"] = label
    feature_table["signed_step_nm"] = feature_table["signed_step_px"] * scale * 1000.0
    return frame_table, step_table, feature_table


def summarize_steps(table: pd.DataFrame, group_columns: list[str]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for key, group in table.groupby(group_columns, sort=False, dropna=False):
        if not isinstance(key, tuple):
            key = (key,)
        valid = group.loc[group["common_valid"]].copy()
        values = valid["measured_step_um"].to_numpy(float) * 1000.0
        errors = valid["signed_error_nm"].to_numpy(float)
        row = dict(zip(group_columns, key, strict=True))
        row.update(
            {
                "n": len(valid),
                "mean_step_nm": float(np.mean(values)),
                "step_sd_nm": float(np.std(values, ddof=1)),
                "bias_nm": float(np.mean(errors)),
                "mae_nm": float(np.mean(np.abs(errors))),
                "rmse_nm": float(np.sqrt(np.mean(errors**2))),
                "p95_absolute_error_nm": float(np.percentile(np.abs(errors), 95)),
                "mean_within_grid_mad_nm": float(
                    valid["within_grid_mad_nm"].mean()
                ),
                "median_within_grid_mad_nm": float(
                    valid["within_grid_mad_nm"].median()
                ),
                "median_threshold_sensitivity_nm": float(
                    valid["threshold_sensitivity_nm"].median()
                ),
            }
        )
        rows.append(row)
    return pd.DataFrame(rows)


def add_common_valid(
    table: pd.DataFrame, *, key_columns: list[str], expected_methods: int
) -> pd.DataFrame:
    valid_counts = (
        table.loc[table["valid"]]
        .groupby(key_columns, sort=False)["method"]
        .nunique()
        .rename("valid_method_count")
    )
    output = table.merge(valid_counts, on=key_columns, how="left")
    output["valid_method_count"] = output["valid_method_count"].fillna(0).astype(int)
    output["common_valid"] = (
        output["valid"] & output["valid_method_count"].eq(expected_methods)
    )
    return output


def run_displacement_improvement() -> dict[str, Any]:
    output = FIGURE_ROOT / "01_displacement_improvement"
    tables = output / "tables"
    tables.mkdir(parents=True, exist_ok=True)
    selection = locked_selection()
    all_steps: list[pd.DataFrame] = []
    all_features: list[pd.DataFrame] = []
    qa_rows: list[dict[str, Any]] = []
    # The archived Wiener baseline was reconstructed only over the pillar
    # evaluation region. Its 20x via pixels are byte-identical to Raw, so the
    # displacement-improvement experiment must remain pillar-only.
    for morphology, path in (("pillar", PILLAR_CONFIG),):
        configs = read_configs(path, morphology)
        for sequence_name in APPROVED_SEQUENCES:
            cfg = configs[sequence_name]
            raw_images = ISO.load_frames(Path(cfg["raw_dir"]), int(cfg["frame_count"]))
            sessions = _load_mapping(sequence_name)
            _, runtime = _raw_segment_measurements(
                sequence_name, cfg, sessions, raw_images
            )
            for method in ("Raw", "Wiener", "MOSR"):
                directory = method_directory(method, sequence_name, cfg)
                _, steps, features = measure_one(
                    label=method,
                    image_dir=directory,
                    sequence_name=sequence_name,
                    sequence_cfg=cfg,
                    raw_images=raw_images,
                    sessions=sessions,
                    runtime=runtime,
                )
                steps["morphology"] = morphology
                features["morphology"] = morphology
                all_steps.append(steps)
                all_features.append(features)
                qa_rows.append(
                    {
                        "experiment": "displacement_improvement",
                        "morphology": morphology,
                        "sequence": sequence_name,
                        "method": method,
                        "available_steps": len(steps),
                        "valid_steps": int(steps["valid"].sum()),
                        "source_dir": str(directory),
                    }
                )
                print(
                    f"improvement {morphology} {sequence_name} {method}: "
                    f"{int(steps['valid'].sum())}/{len(steps)}",
                    flush=True,
                )
            del raw_images
    step_table = pd.concat(all_steps, ignore_index=True)
    step_table = step_table.merge(
        selection[
            ["sequence", "end_frame_index", "raw_motion_quality_rank"]
        ],
        on=["sequence", "end_frame_index"],
        how="inner",
        validate="many_to_one",
    )
    step_table = add_common_valid(
        step_table,
        key_columns=["morphology", "sequence", "end_frame_index"],
        expected_methods=3,
    )
    feature_table = pd.concat(all_features, ignore_index=True)
    feature_table = feature_table.merge(
        selection[["sequence", "end_frame_index"]],
        on=["sequence", "end_frame_index"],
        how="inner",
        validate="many_to_one",
    )
    summary = summarize_steps(
        step_table,
        ["morphology", "sequence", "magnification", "method"],
    )
    pooled = summarize_steps(
        step_table,
        ["morphology", "magnification", "method"],
    )
    step_table.to_csv(tables / "displacement_per_step.csv", index=False)
    feature_table.to_csv(tables / "displacement_per_feature.csv", index=False)
    summary.to_csv(tables / "displacement_summary_by_sequence.csv", index=False)
    pooled.to_csv(tables / "displacement_summary_by_magnification.csv", index=False)
    pd.DataFrame(qa_rows).to_csv(tables / "source_and_validity_audit.csv", index=False)
    return {
        "step_rows": len(step_table),
        "feature_rows": len(feature_table),
        "common_valid_rows": int(step_table["common_valid"].sum()),
        "summary_rows": len(summary),
    }


def r63_config(variant: str, seed: int) -> dict[str, dict[str, Any]]:
    path = (
        R63
        / "results"
        / "evaluation"
        / "metrics"
        / variant
        / f"seed{seed}"
        / "displacement"
        / "audit_config.json"
    )
    return json.loads(path.read_text(encoding="utf-8"))["sequences"]


def run_ablation() -> dict[str, Any]:
    output = FIGURE_ROOT / "02_ablation"
    tables = output / "tables"
    tables.mkdir(parents=True, exist_ok=True)
    selection = locked_selection()
    all_steps: list[pd.DataFrame] = []
    all_features: list[pd.DataFrame] = []
    qa_rows: list[dict[str, Any]] = []
    for seed in SEEDS:
        # Raw tracking is identical across every ablation condition.
        base_configs = r63_config("full_control", seed)
        runtime_by_sequence: dict[
            str, tuple[dict[str, Any], pd.DataFrame, dict[int, dict[str, Any]], list[np.ndarray]]
        ] = {}
        for sequence_name in APPROVED_SEQUENCES:
            cfg = base_configs[sequence_name]
            raw_images = ISO.load_frames(Path(cfg["raw_dir"]), int(cfg["frame_count"]))
            sessions = _load_mapping(sequence_name)
            _, runtime = _raw_segment_measurements(
                sequence_name, cfg, sessions, raw_images
            )
            runtime_by_sequence[sequence_name] = (cfg, sessions, runtime, raw_images)
        for variant in ABLATION_VARIANTS:
            variant_configs = r63_config(variant, seed)
            for sequence_name in APPROVED_SEQUENCES:
                cfg, sessions, runtime, raw_images = runtime_by_sequence[sequence_name]
                candidate_cfg = variant_configs[sequence_name]
                image_dir = Path(candidate_cfg["v42_dir"])
                _, steps, features = measure_one(
                    label=variant,
                    image_dir=image_dir,
                    sequence_name=sequence_name,
                    sequence_cfg=cfg,
                    raw_images=raw_images,
                    sessions=sessions,
                    runtime=runtime,
                )
                steps["seed"] = seed
                steps["variant"] = variant
                features["seed"] = seed
                features["variant"] = variant
                all_steps.append(steps)
                all_features.append(features)
                qa_rows.append(
                    {
                        "experiment": "ablation",
                        "seed": seed,
                        "variant": variant,
                        "sequence": sequence_name,
                        "available_steps": len(steps),
                        "valid_steps": int(steps["valid"].sum()),
                        "source_dir": str(image_dir),
                    }
                )
                print(
                    f"ablation {seed} {variant} {sequence_name}: "
                    f"{int(steps['valid'].sum())}/{len(steps)}",
                    flush=True,
                )
        runtime_by_sequence.clear()
    step_table = pd.concat(all_steps, ignore_index=True)
    step_table = step_table.merge(
        selection[
            ["sequence", "end_frame_index", "raw_motion_quality_rank"]
        ],
        on=["sequence", "end_frame_index"],
        how="inner",
        validate="many_to_one",
    )
    # "method" is the generic measurement label and equals the variant here.
    step_table = add_common_valid(
        step_table,
        key_columns=["seed", "sequence", "end_frame_index"],
        expected_methods=len(ABLATION_VARIANTS),
    )
    feature_table = pd.concat(all_features, ignore_index=True)
    feature_table = feature_table.merge(
        selection[["sequence", "end_frame_index"]],
        on=["sequence", "end_frame_index"],
        how="inner",
        validate="many_to_one",
    )
    summary = summarize_steps(
        step_table,
        ["seed", "sequence", "magnification", "variant"],
    )
    pooled = summarize_steps(
        step_table,
        ["seed", "magnification", "variant"],
    )
    step_table.to_csv(tables / "ablation_displacement_per_step.csv", index=False)
    feature_table.to_csv(tables / "ablation_displacement_per_feature.csv", index=False)
    summary.to_csv(tables / "ablation_summary_by_sequence.csv", index=False)
    pooled.to_csv(tables / "ablation_summary_by_magnification.csv", index=False)
    effects = calculate_ablation_effects(step_table)
    effects.to_csv(tables / "ablation_removal_effects.csv", index=False)
    pd.DataFrame(qa_rows).to_csv(tables / "source_and_validity_audit.csv", index=False)
    return {
        "step_rows": len(step_table),
        "feature_rows": len(feature_table),
        "common_valid_rows": int(step_table["common_valid"].sum()),
        "summary_rows": len(summary),
        "effect_rows": len(effects),
    }


def scope_filter(table: pd.DataFrame, scope: str) -> pd.DataFrame:
    if scope == "all_sequences":
        return table
    if scope == "50x_all":
        return table.loc[table["magnification"].eq("50x")]
    if scope == "20x_all":
        return table.loc[table["magnification"].eq("20x")]
    return table.loc[table["sequence"].eq(scope)]


def metric_value(table: pd.DataFrame, metric: str) -> float:
    if metric == "mae_nm":
        return float(table["absolute_error_nm"].mean())
    if metric == "within_grid_nm":
        return float(table["within_grid_mad_nm"].mean())
    if metric == "step_sd_nm":
        centered = (
            table["measured_step_um"] * 1000.0
            - table.groupby("sequence")["measured_step_um"].transform("mean") * 1000.0
        )
        return float(centered.std(ddof=1))
    if metric == "threshold_sensitivity_nm":
        return float(table["threshold_sensitivity_nm"].median())
    raise KeyError(metric)


def bootstrap_effect_draws(
    control: pd.DataFrame,
    ablated: pd.DataFrame,
    metric: str,
    rng: np.random.Generator,
    n_draws: int = 3000,
) -> np.ndarray:
    control_parts: list[np.ndarray] = []
    ablated_parts: list[np.ndarray] = []
    if metric == "mae_nm":
        column = "absolute_error_nm"
    elif metric == "within_grid_nm":
        column = "within_grid_mad_nm"
    elif metric == "threshold_sensitivity_nm":
        column = "threshold_sensitivity_nm"
    elif metric == "step_sd_nm":
        column = "measured_step_um"
    else:
        raise KeyError(metric)

    for sequence_name, positions in control.groupby("sequence", sort=False).indices.items():
        indices = np.asarray(positions, dtype=int)
        sample_index = rng.integers(0, len(indices), size=(n_draws, len(indices)))
        c_values = control.iloc[indices][column].to_numpy(float)[sample_index]
        a_values = ablated.iloc[indices][column].to_numpy(float)[sample_index]
        if metric == "step_sd_nm":
            c_values = 1000.0 * (c_values - c_values.mean(axis=1, keepdims=True))
            a_values = 1000.0 * (a_values - a_values.mean(axis=1, keepdims=True))
        control_parts.append(c_values)
        ablated_parts.append(a_values)

    c_draws = np.concatenate(control_parts, axis=1)
    a_draws = np.concatenate(ablated_parts, axis=1)
    if metric in {"mae_nm", "within_grid_nm"}:
        return a_draws.mean(axis=1) - c_draws.mean(axis=1)
    if metric == "threshold_sensitivity_nm":
        return np.median(a_draws, axis=1) - np.median(c_draws, axis=1)
    return a_draws.std(axis=1, ddof=1) - c_draws.std(axis=1, ddof=1)


def calculate_ablation_effects(step_table: pd.DataFrame) -> pd.DataFrame:
    rng = np.random.default_rng(20260724)
    scopes = (*APPROVED_SEQUENCES, "50x_all", "20x_all", "all_sequences")
    metrics = (
        "step_sd_nm",
        "mae_nm",
        "within_grid_nm",
        "threshold_sensitivity_nm",
    )
    rows: list[dict[str, Any]] = []
    for comparison, (control, ablated) in ABLATION_COMPARISONS.items():
        for scope in scopes:
            for metric in metrics:
                seed_effects: list[float] = []
                seed_control: list[float] = []
                bootstrap_inputs: list[tuple[pd.DataFrame, pd.DataFrame]] = []
                for seed in SEEDS:
                    scoped = scope_filter(
                        step_table.loc[
                            step_table["seed"].eq(seed)
                            & step_table["variant"].isin([control, ablated])
                            & step_table["common_valid"]
                        ],
                        scope,
                    )
                    wide = scoped.pivot_table(
                        index=["sequence", "end_frame_index"],
                        columns="variant",
                        values=[
                            "measured_step_um",
                            "absolute_error_nm",
                            "within_grid_mad_nm",
                            "threshold_sensitivity_nm",
                        ],
                    )
                    if control not in wide.columns.get_level_values(1) or ablated not in wide.columns.get_level_values(1):
                        continue
                    c = pd.DataFrame(
                        {
                            "sequence": wide.index.get_level_values("sequence"),
                            "measured_step_um": wide[("measured_step_um", control)].to_numpy(),
                            "absolute_error_nm": wide[("absolute_error_nm", control)].to_numpy(),
                            "within_grid_mad_nm": wide[("within_grid_mad_nm", control)].to_numpy(),
                            "threshold_sensitivity_nm": wide[("threshold_sensitivity_nm", control)].to_numpy(),
                        }
                    )
                    a = pd.DataFrame(
                        {
                            "sequence": wide.index.get_level_values("sequence"),
                            "measured_step_um": wide[("measured_step_um", ablated)].to_numpy(),
                            "absolute_error_nm": wide[("absolute_error_nm", ablated)].to_numpy(),
                            "within_grid_mad_nm": wide[("within_grid_mad_nm", ablated)].to_numpy(),
                            "threshold_sensitivity_nm": wide[("threshold_sensitivity_nm", ablated)].to_numpy(),
                        }
                    )
                    c_value = metric_value(c, metric)
                    a_value = metric_value(a, metric)
                    seed_control.append(c_value)
                    seed_effects.append(a_value - c_value)
                    bootstrap_inputs.append((c, a))
                if len(seed_effects) != len(SEEDS):
                    continue
                draws = np.mean(
                    np.vstack(
                        [
                            bootstrap_effect_draws(c, a, metric, rng)
                            for c, a in bootstrap_inputs
                        ]
                    ),
                    axis=0,
                )
                mean_effect = float(np.mean(seed_effects))
                control_value = float(np.mean(seed_control))
                rows.append(
                    {
                        "comparison": comparison,
                        "control": control,
                        "ablated": ablated,
                        "scope": scope,
                        "metric": metric,
                        "control_mean": control_value,
                        "effect_seed1261200": seed_effects[0],
                        "effect_seed1261217": seed_effects[1],
                        "mean_removal_penalty": mean_effect,
                        "relative_penalty_pct": (
                            100.0 * mean_effect / control_value
                            if abs(control_value) > 1e-12
                            else np.nan
                        ),
                        "bootstrap_ci_low": float(np.percentile(draws, 2.5)),
                        "bootstrap_ci_high": float(np.percentile(draws, 97.5)),
                        "both_seeds_expected_direction": bool(
                            all(value > 0 for value in seed_effects)
                        ),
                        "ci_excludes_zero": bool(
                            np.percentile(draws, 2.5) > 0
                            or np.percentile(draws, 97.5) < 0
                        ),
                    }
                )
    return pd.DataFrame(rows)


def data_quality_audit(results: dict[str, Any]) -> dict[str, Any]:
    improvement = pd.read_csv(
        FIGURE_ROOT
        / "01_displacement_improvement"
        / "tables"
        / "displacement_per_step.csv"
    )
    ablation = pd.read_csv(
        FIGURE_ROOT
        / "02_ablation"
        / "tables"
        / "ablation_displacement_per_step.csv"
    )
    improvement_counts = improvement.groupby(
        ["morphology", "sequence", "method"]
    ).size().astype(int)
    ablation_counts = ablation.groupby(
        ["seed", "sequence", "variant"]
    ).size().astype(int)
    audit = {
        "results": results,
        "top30_sha256_source": str(TOP30),
        "improvement_duplicate_keys": int(
            improvement.duplicated(
                ["morphology", "sequence", "end_frame_index", "method"]
            ).sum()
        ),
        "ablation_duplicate_keys": int(
            ablation.duplicated(
                ["seed", "sequence", "end_frame_index", "variant"]
            ).sum()
        ),
        "improvement_selected_counts": {
            "|".join(map(str, key)): int(value)
            for key, value in improvement_counts.items()
        },
        "ablation_selected_counts": {
            "|".join(map(str, key)): int(value)
            for key, value in ablation_counts.items()
        },
        "improvement_primary_nulls": int(
            improvement.loc[
                improvement["common_valid"],
                ["measured_step_um", "absolute_error_nm", "within_grid_mad_nm"],
            ]
            .isna()
            .sum()
            .sum()
        ),
        "ablation_primary_nulls": int(
            ablation.loc[
                ablation["common_valid"],
                ["measured_step_um", "absolute_error_nm", "within_grid_mad_nm"],
            ]
            .isna()
            .sum()
            .sum()
        ),
    }
    audit["passed"] = bool(
        audit["improvement_duplicate_keys"] == 0
        and audit["ablation_duplicate_keys"] == 0
        and audit["improvement_primary_nulls"] == 0
        and audit["ablation_primary_nulls"] == 0
        and set(audit["improvement_selected_counts"].values()) == {30}
        and set(audit["ablation_selected_counts"].values()) == {30}
    )
    return audit


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--experiment",
        choices=("all", "improvement", "ablation"),
        default="all",
    )
    args = parser.parse_args()
    FIGURE_ROOT.mkdir(parents=True, exist_ok=True)
    summary_path = FIGURE_ROOT / "run_summary.json"
    if summary_path.is_file():
        results: dict[str, Any] = json.loads(summary_path.read_text(encoding="utf-8"))
    else:
        results = {}
    if args.experiment in ("all", "improvement"):
        results["displacement_improvement"] = run_displacement_improvement()
    if args.experiment in ("all", "ablation"):
        results["ablation"] = run_ablation()
    improvement_file = (
        FIGURE_ROOT
        / "01_displacement_improvement"
        / "tables"
        / "displacement_per_step.csv"
    )
    ablation_file = (
        FIGURE_ROOT
        / "02_ablation"
        / "tables"
        / "ablation_displacement_per_step.csv"
    )
    if improvement_file.is_file() and ablation_file.is_file():
        audit = data_quality_audit(results)
        (FIGURE_ROOT / "data_quality_audit.json").write_text(
            json.dumps(audit, ensure_ascii=False, indent=2, default=str) + "\n",
            encoding="utf-8",
        )
        if not audit["passed"]:
            raise RuntimeError("Data-quality audit failed")
    summary_path.write_text(
        json.dumps(results, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()

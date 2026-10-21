from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import wilcoxon

import analyze_circular_cd_sharpness as circular
import analyze_line_multimethod as line
import analyze_multimethod_displacement as displacement


ROOT = Path(__file__).resolve().parent
EVAL = ROOT / "evaluation"
OUT = EVAL / "calculation_audit"


def max_numeric_difference(
    calculated: pd.DataFrame,
    saved: pd.DataFrame,
    keys: list[str],
) -> tuple[float, list[str]]:
    merged = calculated.merge(saved, on=keys, how="outer", suffixes=("_calc", "_saved"), indicator=True)
    if not merged["_merge"].eq("both").all():
        return math.inf, ["row_identity_mismatch"]
    shared = sorted(
        set(calculated.select_dtypes(include=[np.number]).columns)
        & set(saved.select_dtypes(include=[np.number]).columns)
        - set(keys)
    )
    differences: list[float] = []
    for column in shared:
        left = merged[f"{column}_calc"].to_numpy(dtype=float)
        right = merged[f"{column}_saved"].to_numpy(dtype=float)
        mask = np.isfinite(left) | np.isfinite(right)
        if not np.array_equal(np.isnan(left[mask]), np.isnan(right[mask])):
            return math.inf, [column]
        finite = np.isfinite(left) & np.isfinite(right)
        if finite.any():
            differences.append(float(np.max(np.abs(left[finite] - right[finite]))))
    return (max(differences) if differences else 0.0), shared


def audit_circular() -> dict[str, object]:
    base = EVAL / "circular_cd_sharpness"
    detailed = pd.read_csv(base / "circular_feature_threshold_measurements.csv")
    saved_intervals = pd.read_csv(base / "circular_feature_cd_intervals.csv")
    saved_summary = pd.read_csv(base / "circular_feature_method_summary.csv")

    calculated_intervals = circular.interval_summary(detailed)
    calculated_summary = circular.method_summary(calculated_intervals)
    interval_diff, interval_columns = max_numeric_difference(
        calculated_intervals,
        saved_intervals,
        ["magnification", "morphology", "method", "feature_id"],
    )
    summary_diff, summary_columns = max_numeric_difference(
        calculated_summary,
        saved_summary,
        ["magnification", "morphology", "method"],
    )
    thresholds = sorted(detailed["contrast_fraction"].unique().tolist())
    return {
        "status": "PASS" if max(interval_diff, summary_diff) < 1e-9 else "FAIL",
        "thresholds": thresholds,
        "feature_count": int(saved_intervals.shape[0]),
        "interval_max_abs_difference": interval_diff,
        "summary_max_abs_difference": summary_diff,
        "interval_numeric_columns_checked": interval_columns,
        "summary_numeric_columns_checked": summary_columns,
        "interpretation_limit": (
            "The arithmetic is reproducible. The 35%-65% threshold band is an analysis choice; "
            "unless it was fixed before inspecting outcomes, its midpoint should be described as exploratory."
        ),
    }


def audit_displacement() -> dict[str, object]:
    base = EVAL / "displacement"
    long_table = pd.read_csv(base / "displacement_step_measurements.csv")
    saved_pooled = pd.read_csv(base / "displacement_pooled_common_valid.csv")
    methods = list(dict.fromkeys(long_table["method"].astype(str).tolist()))
    calculated_parts: list[pd.DataFrame] = []
    for morphology in list(dict.fromkeys(long_table["morphology"].astype(str).tolist())):
        subset = long_table.loc[long_table["morphology"].eq(morphology)].copy()
        _, _, pooled = displacement.build_summaries(morphology, subset, methods)
        calculated_parts.append(pooled)
    calculated_pooled = pd.concat(calculated_parts, ignore_index=True)
    pooled_diff, pooled_columns = max_numeric_difference(
        calculated_pooled,
        saved_pooled,
        ["morphology", "sequence", "method", "population"],
    )

    manifest = json.loads((ROOT / "evaluation_manifest.json").read_text(encoding="utf-8"))
    selection = pd.read_csv(manifest["top30_selection"])
    score_calc = (
        np.hypot(
            selection["raw_local_dx_um"].to_numpy(dtype=float)
            - selection["expected_signed_step_um"].to_numpy(dtype=float),
            selection["raw_local_dy_um"].to_numpy(dtype=float),
        )
        * 1000.0
    )
    score_diff = float(
        np.max(
            np.abs(
                score_calc
                - selection["raw_motion_quality_score_nm"].to_numpy(dtype=float)
            )
        )
    )
    selected = selection.loc[selection["top30_raw_motion_selected"].astype(bool)]
    selected_counts = {
        str(key): int(value)
        for key, value in selected.groupby("sequence").size().to_dict().items()
    }
    feedback_columns = [
        column
        for column in selection.columns
        if any(token in column.lower() for token in ("feedback", "encoder", "position_actual", "measured_stage"))
    ]
    return {
        "status": "PASS_WITH_METHOD_CAVEATS" if pooled_diff < 1e-9 and score_diff < 1e-8 else "FAIL",
        "pooled_metric_max_abs_difference": pooled_diff,
        "pooled_numeric_columns_checked": pooled_columns,
        "selected_counts": selected_counts,
        "raw_ranking_score_formula_max_abs_difference": score_diff,
        "selection_rule": (
            "The formal 30-step subset is ranked by Raw deviation from the nominal command, "
            "so it is a stable-step subset and is not an unbiased method-ranking sample."
        ),
        "reference_columns_found": feedback_columns,
        "reference_limit": (
            "The analysis table contains nominal commanded displacement but no numeric per-frame PI feedback. "
            "The current errors therefore quantify agreement with the command, not independently logged stage truth."
        ),
    }


def audit_line() -> dict[str, object]:
    base = EVAL / "line" / "tables"
    step_table = pd.read_csv(base / "line_displacement_per_step.csv")
    saved_by_sequence = pd.read_csv(base / "line_displacement_by_sequence.csv")
    saved_pooled = pd.read_csv(base / "line_displacement_pooled.csv")
    calculated_by_sequence, calculated_pooled = line.displacement_summary(step_table)
    seq_diff, seq_columns = max_numeric_difference(
        calculated_by_sequence,
        saved_by_sequence,
        ["sequence", "method"],
    )
    pooled_diff, pooled_columns = max_numeric_difference(
        calculated_pooled,
        saved_pooled,
        ["method"],
    )
    return {
        "status": "PASS_WITH_METHOD_CAVEATS" if max(seq_diff, pooled_diff) < 1e-9 else "FAIL",
        "by_sequence_max_abs_difference": seq_diff,
        "pooled_max_abs_difference": pooled_diff,
        "by_sequence_numeric_columns_checked": seq_columns,
        "pooled_numeric_columns_checked": pooled_columns,
        "interpretation_limit": (
            "The line result uses the same Raw-ranked step subset and Raw-defined candidate edges for all methods. "
            "This preserves identity matching but does not constitute an independent selection rule."
        ),
    }


def audit_sem_and_scale() -> dict[str, object]:
    manifest = json.loads((ROOT / "evaluation_manifest.json").read_text(encoding="utf-8"))
    via = json.loads(Path(manifest["via_config"]).read_text(encoding="utf-8"))
    via_radius = np.asarray(
        [[cell["radius_nm"] for cell in row] for row in via["sem_reference"]],
        dtype=float,
    )
    via_diameter = np.asarray(
        [[cell["diameter_um"] * 1000.0 for cell in row] for row in via["sem_reference"]],
        dtype=float,
    )
    via_diff = float(np.max(np.abs(via_diameter - 2.0 * via_radius)))

    pillar_reports = {}
    physical_reference = None
    for magnification in ("50x", "20x"):
        meta = json.loads(circular.PILLAR_SEM_META[magnification].read_text(encoding="utf-8"))
        radius = np.asarray(meta["image_oriented_sem_radius_nm"], dtype=float)
        diameter = np.asarray(meta["image_oriented_sem_cd_nm"], dtype=float)
        if physical_reference is None:
            physical_reference = np.asarray(meta["physical_sem_radius_nm"], dtype=float)
        pillar_reports[magnification] = {
            "radius_to_diameter_max_abs_difference_nm": float(np.max(np.abs(diameter - 2.0 * radius))),
            "same_nine_physical_radii": bool(
                np.allclose(np.sort(radius.reshape(-1)), np.sort(physical_reference.reshape(-1)), atol=1e-9)
            ),
            "object_um_per_px": float(meta["object_pixel_um"]),
        }

    nominal_scales = {"50x": 3.45 / 50.0, "20x": 3.45 / 20.0}
    scale_diff = max(
        abs(pillar_reports[magnification]["object_um_per_px"] - nominal)
        for magnification, nominal in nominal_scales.items()
    )
    all_pass = (
        via_diff < 1e-9
        and scale_diff < 1e-12
        and all(
            row["radius_to_diameter_max_abs_difference_nm"] < 1e-9
            and row["same_nine_physical_radii"]
            for row in pillar_reports.values()
        )
    )
    return {
        "status": "PASS_WITH_CALIBRATION_CAVEAT" if all_pass else "FAIL",
        "pillar": pillar_reports,
        "via_radius_to_diameter_max_abs_difference_nm": via_diff,
        "via_mean_diameter_nm": float(np.mean(via_diameter)),
        "nominal_pixel_scales_um_per_px": nominal_scales,
        "pixel_scale_formula_max_abs_difference_um_per_px": float(scale_diff),
        "orientation_check": "Both magnifications contain the same nine SEM radii after their recorded image-orientation transform.",
        "scale_limit": (
            "The conversion 3.45 um divided by nominal magnification is arithmetically correct, "
            "but no independent effective-magnification calibration was found in this benchmark package."
        ),
    }


def audit_runtime() -> dict[str, object]:
    fair = pd.read_csv(EVAL / "runtime_fair_modes" / "fair_runtime_modes.csv")
    pixels = 2048 * 1536
    throughput_calc = pixels / (fair["direct_median_ms"].to_numpy(dtype=float) / 1000.0) / 1e6
    throughput_diff = float(
        np.max(
            np.abs(
                throughput_calc
                - fair["direct_megapixels_per_second"].to_numpy(dtype=float)
            )
        )
    )
    direct_rank = (
        fair.sort_values("direct_median_ms")[["method", "direct_median_ms", "direct_peak_gpu_memory_mb"]]
        .to_dict(orient="records")
    )
    patch_rank = (
        fair.sort_values("patch_median_ms")[["method", "patch_median_ms"]]
        .to_dict(orient="records")
    )
    return {
        "status": "PASS_WITH_COMPARISON_CAVEAT" if throughput_diff < 1e-9 else "FAIL",
        "throughput_formula_max_abs_difference": throughput_diff,
        "direct_full_frame_ranking": direct_rank,
        "same_patch_ranking": patch_rank,
        "interpretation_limit": (
            "The original deployment table compares MOSR direct full-frame inference with tiled baseline inference. "
            "It is a practical pipeline-latency comparison, not a same-input architecture-speed comparison."
        ),
    }


def formal_paired_comparisons() -> pd.DataFrame:
    table = pd.read_csv(EVAL / "displacement" / "displacement_step_measurements.csv")
    method_order = ["Raw", "Base U-Net", "NAFNet", "EDSR", "MOSR"]
    records: list[dict[str, object]] = []
    rng = np.random.default_rng(20260719)
    for morphology in ("pillar", "via"):
        morphology_table = table.loc[table["morphology"].eq(morphology)].copy()
        common_pieces: list[pd.DataFrame] = []
        for _, sequence_table in morphology_table.groupby("sequence", sort=False):
            validity = sequence_table.pivot(
                index="end_frame_index", columns="method", values="evaluable"
            )
            common_indices = validity.index[
                validity.reindex(columns=method_order).fillna(False).all(axis=1)
            ]
            common_pieces.append(
                sequence_table.loc[sequence_table["end_frame_index"].isin(common_indices)]
            )
        common = pd.concat(common_pieces, ignore_index=True)
        common["absolute_error_nm"] = (
            common["signed_step_um"] - common["expected_signed_step_um"]
        ).abs() * 1000.0
        paired = common.pivot(
            index=["sequence", "end_frame_index"],
            columns="method",
            values="absolute_error_nm",
        )
        for comparator in ("Raw", "Base U-Net", "NAFNet", "EDSR"):
            difference = (
                paired["MOSR"].to_numpy(dtype=float)
                - paired[comparator].to_numpy(dtype=float)
            )
            bootstrap_indices = rng.integers(
                0, len(difference), size=(20000, len(difference))
            )
            bootstrap_means = difference[bootstrap_indices].mean(axis=1)
            records.append(
                {
                    "morphology": morphology,
                    "reference_method": comparator,
                    "candidate_method": "MOSR",
                    "common_step_count": len(difference),
                    "candidate_minus_reference_mean_absolute_error_nm": float(
                        difference.mean()
                    ),
                    "paired_bootstrap_95ci_lower_nm": float(
                        np.percentile(bootstrap_means, 2.5)
                    ),
                    "paired_bootstrap_95ci_upper_nm": float(
                        np.percentile(bootstrap_means, 97.5)
                    ),
                    "wilcoxon_p_value": float(wilcoxon(difference).pvalue),
                }
            )
    return pd.DataFrame(records)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    paired = formal_paired_comparisons()
    paired.to_csv(OUT / "FORMAL_PAIRED_COMPARISONS.csv", index=False)
    report = {
        "audit_version": 1,
        "benchmark_root": str(ROOT),
        "overall_status": "PASS_WITH_MATERIAL_METHOD_CAVEATS",
        "circular_cd_and_sharpness": audit_circular(),
        "displacement": audit_displacement(),
        "line": audit_line(),
        "sem_and_pixel_scale": audit_sem_and_scale(),
        "runtime": audit_runtime(),
        "formal_paired_comparisons": paired.to_dict(orient="records"),
        "overall_interpretation": [
            "Saved aggregate values reproduce from their underlying rows.",
            "The main risks are experimental-reference and comparison-design issues, not arithmetic errors.",
            "Do not call nominal commanded motion per-frame PI feedback unless a numeric feedback log is joined to the evaluation.",
            "Do not present the Raw-ranked 30-step subset as an unbiased ranking population.",
            "Do not describe the original mixed direct/tiled runtime as intrinsic network speed.",
        ],
    }
    path = OUT / "CALCULATION_AUDIT.json"
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(path)
    print(report["overall_status"])


if __name__ == "__main__":
    main()

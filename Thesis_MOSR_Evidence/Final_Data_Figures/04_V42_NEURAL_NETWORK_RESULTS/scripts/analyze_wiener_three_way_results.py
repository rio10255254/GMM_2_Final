"""Build same-system Raw/Wiener/MOSR comparison tables for Chapter 6."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
from PIL import Image
from scipy.ndimage import map_coordinates
from scipy.stats import spearmanr


PACKAGE = Path(__file__).resolve().parents[1]
EVIDENCE = PACKAGE.parent
CURRENT = EVIDENCE / "01_CURRENT_THESIS_RESULTS_V42_CENTER9"
WIENER = PACKAGE / "source_validation" / "wiener_baseline_20260715"
OUTPUT = WIENER / "tables"
OUTPUT.mkdir(parents=True, exist_ok=True)

SEQUENCE_ORDER = ["50x_x_0p5um", "50x_x_1um", "20x_0p5um", "20x_1um"]
CONDITION_LABELS = {
    "50x_x_0p5um": "50x, 0.5 um",
    "50x_x_1um": "50x, 1.0 um",
    "20x_0p5um": "20x, 0.5 um",
    "20x_1um": "20x, 1.0 um",
}


def _logical(values: pd.Series) -> pd.Series:
    if values.dtype == bool:
        return values
    return values.astype(str).str.lower().isin({"true", "1", "yes"})


def _read_gray(path: str | Path) -> np.ndarray:
    with Image.open(path) as image:
        return np.asarray(image.convert("L"), dtype=np.float64)


def _interpolate_crossing(
    x: np.ndarray, y: np.ndarray, i0: int, i1: int, threshold: float
) -> float:
    x0, x1 = float(x[i0]), float(x[i1])
    y0, y1 = float(y[i0]), float(y[i1])
    if abs(y1 - y0) < 1e-8:
        return (x0 + x1) * 0.5
    fraction = np.clip((threshold - y0) / (y1 - y0), 0.0, 1.0)
    return x0 + float(fraction) * (x1 - x0)


def _measure_half_height_width(
    image: np.ndarray,
    center_x: float,
    center_y: float,
    radius_px: float,
    threshold_fraction: float = 0.5,
) -> dict[str, float | str]:
    height, width = image.shape
    margin = max(28.0, radius_px * 1.35)
    x0 = max(0, int(np.floor(center_x - radius_px - margin)))
    x1 = min(width, int(np.ceil(center_x + radius_px + margin)))
    center_row = int(round(center_y))
    y0 = max(0, center_row - 3)
    y1 = min(height, center_row + 4)
    profile = (1.0 - image[y0:y1, x0:x1] / 255.0).mean(axis=0)
    x = np.arange(x0, x1, dtype=np.float64)
    center_mask = np.abs(x - center_x) <= max(3.0, radius_px * 0.42)
    background_mask = (x < center_x - radius_px * 1.45) | (
        x > center_x + radius_px * 1.45
    )
    if center_mask.sum() < 3 or background_mask.sum() < 3:
        return {"status": "bad_window"}
    high = float(np.percentile(profile[center_mask], 80))
    low = float(np.percentile(profile[background_mask], 20))
    if high <= low + 1e-5:
        return {"status": "bad_contrast"}
    threshold = low + threshold_fraction * (high - low)
    left_candidates = np.where(
        (x[:-1] < center_x)
        & (profile[:-1] < threshold)
        & (profile[1:] >= threshold)
    )[0]
    right_candidates = np.where(
        (x[:-1] > center_x)
        & (profile[:-1] >= threshold)
        & (profile[1:] < threshold)
    )[0]
    if len(left_candidates) == 0 or len(right_candidates) == 0:
        return {"status": "bad_crossing"}
    left_index = int(
        left_candidates[np.argmin(np.abs(x[left_candidates] - center_x))]
    )
    right_index = int(
        right_candidates[np.argmin(np.abs(x[right_candidates] - center_x))]
    )
    left = _interpolate_crossing(x, profile, left_index, left_index + 1, threshold)
    right = _interpolate_crossing(x, profile, right_index, right_index + 1, threshold)
    if right <= left:
        return {"status": "bad_crossing"}
    return {
        "status": "ok",
        "left_edge_px": left,
        "right_edge_px": right,
        "width_px": right - left,
        "threshold": threshold,
    }


def _measure_radial_width(
    image: np.ndarray,
    center_x: float,
    center_y: float,
    radius_px: float,
    threshold_fraction: float,
) -> dict[str, float | str]:
    """Measure apparent diameter from an azimuthally averaged radial profile."""
    margin = max(28.0, radius_px * 1.35)
    radial_limit = radius_px + margin
    radii = np.arange(0.0, radial_limit + 0.125, 0.25, dtype=np.float64)
    angles = np.linspace(0.0, 2.0 * np.pi, 720, endpoint=False)
    sample_x = center_x + np.outer(np.cos(angles), radii)
    sample_y = center_y + np.outer(np.sin(angles), radii)
    if (
        sample_x.min() < 0
        or sample_x.max() > image.shape[1] - 1
        or sample_y.min() < 0
        or sample_y.max() > image.shape[0] - 1
    ):
        return {"status": "bad_window"}
    darkness = 1.0 - image / 255.0
    samples = map_coordinates(
        darkness,
        [sample_y.ravel(), sample_x.ravel()],
        order=1,
        mode="nearest",
    ).reshape(sample_y.shape)
    profile = samples.mean(axis=0)
    center_mask = radii <= max(3.0, radius_px * 0.42)
    background_mask = radii >= radius_px * 1.45
    if center_mask.sum() < 3 or background_mask.sum() < 3:
        return {"status": "bad_window"}
    high = float(np.percentile(profile[center_mask], 80))
    low = float(np.percentile(profile[background_mask], 20))
    if high <= low + 1e-5:
        return {"status": "bad_contrast"}
    threshold = low + threshold_fraction * (high - low)
    candidates = np.where(
        (profile[:-1] >= threshold) & (profile[1:] < threshold)
    )[0]
    if len(candidates) == 0:
        return {"status": "bad_crossing"}
    edge_index = int(candidates[np.argmin(np.abs(radii[candidates] - radius_px))])
    edge_radius = _interpolate_crossing(
        radii, profile, edge_index, edge_index + 1, threshold
    )
    if edge_radius <= 0:
        return {"status": "bad_crossing"}
    return {
        "status": "ok",
        "edge_radius_px": edge_radius,
        "width_px": 2.0 * edge_radius,
        "threshold": threshold,
    }


def build_cd_sensitivity_tables() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Audit whether the CD ranking survives threshold and profile choices."""
    source = pd.read_csv(CURRENT / "cd" / "tables" / "center9_cd_per_pillar.csv")
    case_paths = {
        "raw": Path(source["raw_source_image"].iloc[0]),
        "wiener": WIENER / "static_cd" / "Image__2026-06-18__17-10-31_wiener.bmp",
        "v42_e120": Path(source["v42_source_image"].iloc[0]),
    }
    labels = {
        "raw": "Raw",
        "wiener": "Wiener deconvolution",
        "v42_e120": "V42 epoch 120",
    }
    images = {case: _read_gray(path) for case, path in case_paths.items()}
    thresholds = np.round(np.arange(0.35, 0.651, 0.05), 2)
    measurement_functions = {
        "horizontal_strip": _measure_half_height_width,
        "radial_mean": _measure_radial_width,
    }
    records: list[dict[str, object]] = []
    for mode, measure in measurement_functions.items():
        for threshold_fraction in thresholds:
            for case, image in images.items():
                for row in source.itertuples(index=False):
                    result = measure(
                        image,
                        float(row.raw_x_px),
                        float(row.raw_y_px),
                        float(row.reference_radius_px),
                        float(threshold_fraction),
                    )
                    diameter_um = float(result.get("width_px", np.nan)) * 0.069
                    signed_error_nm = (diameter_um - float(row.sem_diameter_um)) * 1000.0
                    records.append(
                        {
                            "measurement_mode": mode,
                            "threshold_fraction": float(threshold_fraction),
                            "case": case,
                            "case_label": labels[case],
                            "center9_position": int(row.center9_position),
                            "sem_index": int(row.sem_index),
                            "sem_diameter_um": float(row.sem_diameter_um),
                            "diameter_um": diameter_um,
                            "signed_error_nm": signed_error_nm,
                            "abs_error_nm": abs(signed_error_nm),
                            "status": str(result["status"]),
                        }
                    )
    per_measurement = pd.DataFrame(records)
    if not (per_measurement["status"] == "ok").all():
        failed = per_measurement.loc[per_measurement["status"] != "ok"]
        raise RuntimeError(f"CD sensitivity audit has {len(failed)} failed crossings")
    if not np.isfinite(
        per_measurement[["diameter_um", "signed_error_nm", "abs_error_nm"]].to_numpy(float)
    ).all():
        raise RuntimeError("CD sensitivity audit contains non-finite measurements")

    summary_records: list[dict[str, object]] = []
    for (mode, threshold_fraction, case, label), group in per_measurement.groupby(
        ["measurement_mode", "threshold_fraction", "case", "case_label"], sort=False
    ):
        signed = group["signed_error_nm"].to_numpy(float)
        absolute = np.abs(signed)
        summary_records.append(
            {
                "measurement_mode": mode,
                "threshold_fraction": threshold_fraction,
                "case": case,
                "case_label": label,
                "pillar_count": len(group),
                "mean_abs_error_nm": float(np.mean(absolute)),
                "median_abs_error_nm": float(np.median(absolute)),
                "rmse_nm": float(np.sqrt(np.mean(np.square(signed)))),
                "mean_signed_bias_nm": float(np.mean(signed)),
                "max_abs_error_nm": float(np.max(absolute)),
            }
        )
    sensitivity_summary = pd.DataFrame(summary_records)

    per_pillar_records: list[dict[str, object]] = []
    for (case, label, position, sem_index), group in per_measurement.groupby(
        ["case", "case_label", "center9_position", "sem_index"], sort=False
    ):
        absolute = group["abs_error_nm"].to_numpy(float)
        per_pillar_records.append(
            {
                "case": case,
                "case_label": label,
                "center9_position": position,
                "sem_index": sem_index,
                "sensitivity_check_count": len(group),
                "median_abs_error_nm": float(np.median(absolute)),
                "mean_abs_error_nm": float(np.mean(absolute)),
                "max_abs_error_nm": float(np.max(absolute)),
            }
        )
    robust_per_pillar = pd.DataFrame(per_pillar_records)

    robust_records: list[dict[str, object]] = []
    raw_group = per_measurement.loc[per_measurement["case"] == "raw"]
    raw_pooled_median = float(raw_group["abs_error_nm"].median())
    for (case, label), group in per_measurement.groupby(["case", "case_label"], sort=False):
        absolute = group["abs_error_nm"].to_numpy(float)
        signed = group["signed_error_nm"].to_numpy(float)
        per_pillar = robust_per_pillar.loc[robust_per_pillar["case"] == case]
        pooled_median = float(np.median(absolute))
        robust_records.append(
            {
                "case": case,
                "case_label": label,
                "measurement_mode_count": int(group["measurement_mode"].nunique()),
                "threshold_count": int(group["threshold_fraction"].nunique()),
                "pillar_count": int(group["center9_position"].nunique()),
                "sensitivity_observation_count": len(group),
                "pooled_median_abs_error_nm": pooled_median,
                "pooled_mean_abs_error_nm": float(np.mean(absolute)),
                "mean_of_pillar_median_abs_error_nm": float(per_pillar["median_abs_error_nm"].mean()),
                "pooled_rmse_nm": float(np.sqrt(np.mean(np.square(signed)))),
                "pooled_mean_signed_bias_nm": float(np.mean(signed)),
                "median_abs_improvement_vs_raw_nm": raw_pooled_median - pooled_median,
                "median_abs_improvement_vs_raw_pct": 100.0 * (raw_pooled_median - pooled_median) / raw_pooled_median,
            }
        )
    robust_summary = pd.DataFrame(robust_records)
    return per_measurement, sensitivity_summary, robust_per_pillar, robust_summary


def build_cd_tables() -> tuple[pd.DataFrame, pd.DataFrame]:
    source = pd.read_csv(CURRENT / "cd" / "tables" / "center9_cd_per_pillar.csv")
    case_paths = {
        "raw": Path(source["raw_source_image"].iloc[0]),
        "wiener": WIENER
        / "static_cd"
        / "Image__2026-06-18__17-10-31_wiener.bmp",
        "v42_e120": Path(source["v42_source_image"].iloc[0]),
    }
    images = {case: _read_gray(path) for case, path in case_paths.items()}
    output = source[
        [
            "center9_position",
            "sem_index",
            "sem_excel_cell",
            "optical_grid_row",
            "optical_grid_col",
            "capture_transform",
            "sem_radius_nm",
            "sem_diameter_um",
            "raw_x_px",
            "raw_y_px",
            "reference_radius_px",
        ]
    ].copy()
    for case, image in images.items():
        widths: list[float] = []
        statuses: list[str] = []
        left_edges: list[float] = []
        right_edges: list[float] = []
        for row in source.itertuples(index=False):
            result = _measure_half_height_width(
                image,
                float(row.raw_x_px),
                float(row.raw_y_px),
                float(row.reference_radius_px),
            )
            statuses.append(str(result["status"]))
            widths.append(float(result.get("width_px", np.nan)))
            left_edges.append(float(result.get("left_edge_px", np.nan)))
            right_edges.append(float(result.get("right_edge_px", np.nan)))
        output[f"{case}_status"] = statuses
        output[f"{case}_left_edge_px"] = left_edges
        output[f"{case}_right_edge_px"] = right_edges
        output[f"{case}_diameter_um"] = np.asarray(widths) * 0.069
        output[f"{case}_signed_error_nm"] = (
            output[f"{case}_diameter_um"] - output["sem_diameter_um"]
        ) * 1000.0
        output[f"{case}_abs_error_nm"] = output[f"{case}_signed_error_nm"].abs()

    if not all((output[f"{case}_status"] == "ok").all() for case in case_paths):
        raise RuntimeError("At least one center-nine CD crossing failed")
    raw_difference = np.max(
        np.abs(output["raw_diameter_um"] - source["raw_diameter_um"])
    )
    v42_difference = np.max(
        np.abs(output["v42_e120_diameter_um"] - source["v42_e120_diameter_um"])
    )
    if raw_difference > 1e-6 or v42_difference > 1e-6:
        raise RuntimeError(
            f"CD method mismatch: Raw={raw_difference}, V42={v42_difference} um"
        )
    raw_absolute = output["raw_abs_error_nm"]
    for case in ("wiener", "v42_e120"):
        output[f"{case}_abs_improvement_nm"] = (
            raw_absolute - output[f"{case}_abs_error_nm"]
        )
        output[f"{case}_improved_vs_raw"] = (
            output[f"{case}_abs_error_nm"] < raw_absolute
        )

    labels = {
        "raw": "Raw",
        "wiener": "Wiener deconvolution",
        "v42_e120": "V42 epoch 120",
    }
    records: list[dict[str, object]] = []
    raw_mae = float(output["raw_abs_error_nm"].mean())
    for case, label in labels.items():
        signed = output[f"{case}_signed_error_nm"].to_numpy(float)
        absolute = np.abs(signed)
        mae = float(np.mean(absolute))
        records.append(
            {
                "case": case,
                "case_label": label,
                "pillar_count": len(output),
                "mean_diameter_um": float(output[f"{case}_diameter_um"].mean()),
                "mean_abs_error_nm": mae,
                "median_abs_error_nm": float(np.median(absolute)),
                "rmse_nm": float(np.sqrt(np.mean(np.square(signed)))),
                "mean_signed_bias_nm": float(np.mean(signed)),
                "max_abs_error_nm": float(np.max(absolute)),
                "improved_vs_raw_count": (
                    int(output[f"{case}_improved_vs_raw"].sum())
                    if case != "raw"
                    else 0
                ),
                "mean_abs_improvement_nm": raw_mae - mae,
                "mean_abs_improvement_pct": 100.0 * (raw_mae - mae) / raw_mae,
            }
        )
    return output, pd.DataFrame(records)


def build_displacement_tables() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    selection = pd.read_csv(PACKAGE / "tables" / "top30_raw_motion_selection.csv")
    selection = selection.loc[_logical(selection["top30_raw_motion_selected"])].copy()
    if len(selection) != 120:
        raise RuntimeError(f"Expected 120 locked steps, found {len(selection)}")
    original = pd.read_csv(
        CURRENT
        / "diagnostics"
        / "unified_displacement_step_audit"
        / "tables"
        / "all_adjacent_pairs_audit.csv"
    )
    wiener = pd.read_csv(
        WIENER
        / "displacement_audit"
        / "tables"
        / "all_adjacent_pairs_audit.csv"
    )
    keys = ["sequence", "end_frame_index"]
    original_fields = keys + [
        "magnification",
        "nominal_step_um",
        "expected_signed_step_um",
        "raw_boundary_dx_um",
        "raw_within_grid_nm",
        "raw_boundary_valid_pillars",
        "v42_evaluable",
        "v42_boundary_dx_um",
        "v42_within_grid_nm",
        "v42_boundary_valid_pillars",
    ]
    wiener_fields = keys + [
        "raw_boundary_dx_um",
        "raw_within_grid_nm",
        "v42_evaluable",
        "v42_boundary_dx_um",
        "v42_within_grid_nm",
        "v42_boundary_valid_pillars",
    ]
    table = selection[
        keys + ["raw_motion_quality_score_nm", "raw_motion_quality_rank"]
    ].merge(original[original_fields], on=keys, how="left", validate="one_to_one")
    wiener_part = wiener[wiener_fields].rename(
        columns={
            "raw_boundary_dx_um": "wiener_audit_raw_boundary_dx_um",
            "raw_within_grid_nm": "wiener_audit_raw_within_grid_nm",
            "v42_evaluable": "wiener_evaluable",
            "v42_boundary_dx_um": "wiener_boundary_dx_um",
            "v42_within_grid_nm": "wiener_within_grid_nm",
            "v42_boundary_valid_pillars": "wiener_boundary_valid_pillars",
        }
    )
    table = table.merge(wiener_part, on=keys, how="left", validate="one_to_one")
    if np.max(
        np.abs(
            table["raw_boundary_dx_um"]
            - table["wiener_audit_raw_boundary_dx_um"]
        )
    ) > 1e-12:
        raise RuntimeError("Raw displacement values differ between the V42 and Wiener audits")
    if not _logical(table["v42_evaluable"]).all() or not _logical(
        table["wiener_evaluable"]
    ).all():
        raise RuntimeError("A locked top-30 displacement step is not evaluable")
    for case in ("raw", "wiener", "v42"):
        if case == "raw":
            dx = table["raw_boundary_dx_um"]
            within = table["raw_within_grid_nm"]
        else:
            dx = table[f"{case}_boundary_dx_um"]
            within = table[f"{case}_within_grid_nm"]
        if not np.isfinite(dx).all() or not np.isfinite(within).all():
            raise RuntimeError(f"Missing {case} primary displacement values")
        table[f"{case}_command_abs_error_nm"] = (
            dx - table["expected_signed_step_um"]
        ).abs() * 1000.0
    table["wiener_closer_to_command"] = (
        table["wiener_command_abs_error_nm"] < table["raw_command_abs_error_nm"]
    )
    table["v42_closer_to_command"] = (
        table["v42_command_abs_error_nm"] < table["raw_command_abs_error_nm"]
    )
    table["wiener_lower_within"] = (
        table["wiener_within_grid_nm"] < table["raw_within_grid_nm"]
    )
    table["v42_lower_within"] = (
        table["v42_within_grid_nm"] < table["raw_within_grid_nm"]
    )

    config = json.loads(
        (CURRENT / "config" / "sequence_center9_50x20x.json").read_text(
            encoding="utf-8"
        )
    )["sequences"]
    calibration = pd.read_csv(WIENER / "tables" / "wiener_selected_nsr.csv").set_index(
        "magnification"
    )
    center_x: list[float] = []
    center_y: list[float] = []
    calibration_x: list[float] = []
    calibration_y: list[float] = []
    distance_px: list[float] = []
    distance_um: list[float] = []
    for row in table.itertuples(index=False):
        sequence = config[row.sequence]
        centers = np.asarray(sequence["centers"], dtype=float)[:, 1:3]
        midpoint = centers.mean(axis=0) + np.asarray(
            [float(sequence["expected_signed_dx_px"]), 0.0]
        ) * (float(row.end_frame_index) - 0.5)
        cal = calibration.loc[str(row.magnification)]
        cal_xy = np.asarray(
            [float(cal["pillar_center_x_px"]), float(cal["pillar_center_y_px"])]
        )
        distance = float(np.linalg.norm(midpoint - cal_xy))
        center_x.append(float(midpoint[0]))
        center_y.append(float(midpoint[1]))
        calibration_x.append(float(cal_xy[0]))
        calibration_y.append(float(cal_xy[1]))
        distance_px.append(distance)
        distance_um.append(distance * float(sequence["object_um_per_px"]))
    table["target_midpoint_x_px"] = center_x
    table["target_midpoint_y_px"] = center_y
    table["psf_calibration_x_px"] = calibration_x
    table["psf_calibration_y_px"] = calibration_y
    table["psf_distance_px"] = distance_px
    table["psf_distance_object_um"] = distance_um
    table["psf_distance_group"] = ""
    for magnification in ("50x", "20x"):
        indices = table.index[table["magnification"] == magnification]
        ordered = table.loc[indices, "psf_distance_object_um"].sort_values().index
        labels = np.repeat(["Near", "Middle", "Far"], len(ordered) // 3)
        if len(labels) != len(ordered):
            raise RuntimeError("Distance groups are not equally divisible")
        table.loc[ordered, "psf_distance_group"] = labels

    records: list[dict[str, object]] = []
    for sequence in SEQUENCE_ORDER:
        group = table.loc[table["sequence"] == sequence]
        raw = group["raw_boundary_dx_um"].to_numpy(float)
        wiener_dx = group["wiener_boundary_dx_um"].to_numpy(float)
        v42 = group["v42_boundary_dx_um"].to_numpy(float)
        raw_error = group["raw_command_abs_error_nm"].to_numpy(float)
        wiener_error = group["wiener_command_abs_error_nm"].to_numpy(float)
        v42_error = group["v42_command_abs_error_nm"].to_numpy(float)
        raw_within = group["raw_within_grid_nm"].to_numpy(float)
        wiener_within = group["wiener_within_grid_nm"].to_numpy(float)
        v42_within = group["v42_within_grid_nm"].to_numpy(float)
        record: dict[str, object] = {
            "sequence": sequence,
            "condition": CONDITION_LABELS[sequence],
            "magnification": str(group["magnification"].iloc[0]),
            "nominal_step_um": abs(float(group["expected_signed_step_um"].iloc[0])),
            "paired_count": len(group),
        }
        for case, dx, error, within in (
            ("raw", raw, raw_error, raw_within),
            ("wiener", wiener_dx, wiener_error, wiener_within),
            ("v42", v42, v42_error, v42_within),
        ):
            record.update(
                {
                    f"{case}_mean_magnitude_um": abs(float(np.mean(dx))),
                    f"{case}_mean_command_bias_nm": (
                        abs(float(np.mean(dx)))
                        - abs(float(group["expected_signed_step_um"].iloc[0]))
                    )
                    * 1000.0,
                    f"{case}_step_sd_nm": float(np.std(dx, ddof=1) * 1000.0),
                    f"{case}_command_mae_nm": float(np.mean(error)),
                    f"{case}_command_median_ae_nm": float(np.median(error)),
                    f"{case}_command_p90_ae_nm": float(np.percentile(error, 90)),
                    f"{case}_within_mean_nm": float(np.mean(within)),
                    f"{case}_within_median_nm": float(np.median(within)),
                    f"{case}_within_p90_nm": float(np.percentile(within, 90)),
                }
            )
        for case in ("wiener", "v42"):
            record[f"{case}_step_sd_reduction_pct"] = 100.0 * (
                1.0 - float(record[f"{case}_step_sd_nm"]) / float(record["raw_step_sd_nm"])
            )
            record[f"{case}_command_mae_reduction_pct"] = 100.0 * (
                1.0
                - float(record[f"{case}_command_mae_nm"])
                / float(record["raw_command_mae_nm"])
            )
            record[f"{case}_within_reduction_pct"] = 100.0 * (
                1.0
                - float(record[f"{case}_within_mean_nm"])
                / float(record["raw_within_mean_nm"])
            )
            record[f"{case}_closer_to_command_count"] = int(
                group[f"{case}_closer_to_command"].sum()
            )
            record[f"{case}_closer_to_command_pct"] = 100.0 * float(
                group[f"{case}_closer_to_command"].mean()
            )
            record[f"{case}_lower_within_count"] = int(
                group[f"{case}_lower_within"].sum()
            )
            record[f"{case}_lower_within_pct"] = 100.0 * float(
                group[f"{case}_lower_within"].mean()
            )
        records.append(record)
    summary = pd.DataFrame(records)

    pooled_records: list[dict[str, object]] = []
    for population, mask in (
        ("All paired steps", np.ones(len(table), dtype=bool)),
        ("50x", table["magnification"].eq("50x")),
        ("20x", table["magnification"].eq("20x")),
    ):
        group = table.loc[mask]
        record = {"population": population, "paired_count": len(group)}
        for case in ("raw", "wiener", "v42"):
            record[f"{case}_command_mae_nm"] = float(
                group[f"{case}_command_abs_error_nm"].mean()
            )
            record[f"{case}_within_mean_nm"] = float(
                group[f"{case}_within_grid_nm"].mean()
            )
        for case in ("wiener", "v42"):
            record[f"{case}_command_mae_reduction_pct"] = 100.0 * (
                1.0
                - record[f"{case}_command_mae_nm"] / record["raw_command_mae_nm"]
            )
            record[f"{case}_within_reduction_pct"] = 100.0 * (
                1.0
                - record[f"{case}_within_mean_nm"] / record["raw_within_mean_nm"]
            )
            record[f"{case}_closer_to_command_count"] = int(
                group[f"{case}_closer_to_command"].sum()
            )
            record[f"{case}_lower_within_count"] = int(
                group[f"{case}_lower_within"].sum()
            )
        pooled_records.append(record)
    return table, summary, pd.DataFrame(pooled_records)


def build_spatial_tables(
    per_step: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    rows: list[dict[str, object]] = []
    correlations: list[dict[str, object]] = []
    for magnification in ("50x", "20x"):
        magnification_rows = per_step.loc[per_step["magnification"] == magnification]
        for distance_group in ("Near", "Middle", "Far"):
            group = magnification_rows.loc[
                magnification_rows["psf_distance_group"] == distance_group
            ]
            row: dict[str, object] = {
                "magnification": magnification,
                "distance_group": distance_group,
                "step_count": len(group),
                "distance_min_object_um": float(group["psf_distance_object_um"].min()),
                "distance_mean_object_um": float(group["psf_distance_object_um"].mean()),
                "distance_max_object_um": float(group["psf_distance_object_um"].max()),
            }
            for case in ("raw", "wiener", "v42"):
                row[f"{case}_command_mae_nm"] = float(
                    group[f"{case}_command_abs_error_nm"].mean()
                )
                row[f"{case}_within_mean_nm"] = float(
                    group[f"{case}_within_grid_nm"].mean()
                )
            for case in ("wiener", "v42"):
                row[f"{case}_command_mae_reduction_pct"] = 100.0 * (
                    1.0
                    - float(row[f"{case}_command_mae_nm"])
                    / float(row["raw_command_mae_nm"])
                )
                row[f"{case}_within_reduction_pct"] = 100.0 * (
                    1.0
                    - float(row[f"{case}_within_mean_nm"])
                    / float(row["raw_within_mean_nm"])
                )
            rows.append(row)
        distance = magnification_rows["psf_distance_object_um"].to_numpy(float)
        for metric, values in (
            (
                "wiener_command_abs_error_nm",
                magnification_rows["wiener_command_abs_error_nm"].to_numpy(float),
            ),
            (
                "wiener_command_benefit_nm",
                (
                    magnification_rows["raw_command_abs_error_nm"]
                    - magnification_rows["wiener_command_abs_error_nm"]
                ).to_numpy(float),
            ),
            (
                "wiener_within_grid_nm",
                magnification_rows["wiener_within_grid_nm"].to_numpy(float),
            ),
        ):
            rho, p_value = spearmanr(distance, values)
            correlations.append(
                {
                    "magnification": magnification,
                    "metric": metric,
                    "step_count": len(values),
                    "spearman_rho": float(rho),
                    "p_value": float(p_value),
                }
            )
    return pd.DataFrame(rows), pd.DataFrame(correlations)


def main() -> None:
    cd_per_pillar, cd_summary = build_cd_tables()
    (
        cd_sensitivity_per_measurement,
        cd_threshold_sensitivity,
        cd_robust_per_pillar,
        cd_robust_summary,
    ) = build_cd_sensitivity_tables()
    displacement, displacement_summary, pooled_summary = build_displacement_tables()
    spatial_summary, spatial_correlations = build_spatial_tables(displacement)
    outputs = {
        "cd_per_pillar": cd_per_pillar,
        "cd_summary": cd_summary,
        "cd_sensitivity_per_measurement": cd_sensitivity_per_measurement,
        "cd_threshold_sensitivity": cd_threshold_sensitivity,
        "cd_robust_per_pillar": cd_robust_per_pillar,
        "cd_robust_summary": cd_robust_summary,
        "displacement_per_step": displacement,
        "displacement_summary": displacement_summary,
        "displacement_pooled": pooled_summary,
        "spatial_summary": spatial_summary,
        "spatial_correlations": spatial_correlations,
    }
    for name, table in outputs.items():
        table.to_csv(OUTPUT / f"three_way_{name}.csv", index=False, float_format="%.12g")
    qa = {
        "locked_steps": int(len(displacement)),
        "steps_per_sequence": displacement.groupby("sequence").size().to_dict(),
        "all_three_way_steps_finite": bool(
            np.isfinite(
                displacement[
                    [
                        "raw_boundary_dx_um",
                        "wiener_boundary_dx_um",
                        "v42_boundary_dx_um",
                        "raw_within_grid_nm",
                        "wiener_within_grid_nm",
                        "v42_within_grid_nm",
                    ]
                ].to_numpy(float)
            ).all()
        ),
        "all_cd_status_ok": bool(
            all((cd_per_pillar[f"{case}_status"] == "ok").all() for case in ("raw", "wiener", "v42_e120"))
        ),
        "all_cd_sensitivity_status_ok": bool(
            (cd_sensitivity_per_measurement["status"] == "ok").all()
        ),
        "cd_sensitivity_check_count_per_case": int(
            len(cd_sensitivity_per_measurement) / 3
        ),
        "cd_raw_reproduction_max_abs_difference_um": float(
            np.max(
                np.abs(
                    cd_per_pillar["raw_diameter_um"]
                    - pd.read_csv(
                        CURRENT / "cd" / "tables" / "center9_cd_per_pillar.csv"
                    )["raw_diameter_um"]
                )
            )
        ),
        "evaluation_scope": (
            "same-system consistency validation; PSF calibration frames are outside "
            "the locked top-30 displacement lists and CD/displacement outcomes do not select NSR"
        ),
    }
    (WIENER / "three_way_analysis_qa.json").write_text(
        json.dumps(qa, indent=2), encoding="utf-8"
    )
    print(json.dumps(qa, indent=2))
    print(cd_summary.to_string(index=False))
    print(cd_robust_summary.to_string(index=False))
    print(displacement_summary.to_string(index=False))
    print(spatial_summary.to_string(index=False))
    print(spatial_correlations.to_string(index=False))


if __name__ == "__main__":
    main()

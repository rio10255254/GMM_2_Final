from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import cv2
import numpy as np
import pandas as pd


@dataclass(frozen=True)
class AnchorResult:
    success: bool
    offset_x_px: float
    offset_y_px: float
    peak_score: float
    uniqueness_margin: float
    failure_reason: str


def detect_sessions(mapping: pd.DataFrame, *, threshold_seconds: float = 60.0) -> pd.DataFrame:
    required = {"frame_index", "timestamp"}
    if not required.issubset(mapping):
        raise ValueError("mapping must contain frame_index and timestamp")
    result = mapping.copy().sort_values("frame_index").reset_index(drop=True)
    result["timestamp"] = pd.to_datetime(result["timestamp"], errors="raise")
    gaps = result["timestamp"].diff().dt.total_seconds()
    if (gaps.dropna() <= 0).any():
        raise ValueError("timestamps must be strictly increasing")
    result["gap_from_previous_seconds"] = gaps
    result["session_start"] = gaps.isna() | (gaps > float(threshold_seconds))
    result["session_id"] = result["session_start"].cumsum().astype(int)
    return result


def subpixel_axis_peak(values: np.ndarray, index: int) -> float | None:
    array = np.asarray(values, dtype=float)
    if index <= 0 or index >= len(array) - 1:
        return None
    left, center, right = array[index - 1 : index + 2]
    denominator = float(left - 2.0 * center + right)
    if not np.isfinite(denominator) or denominator >= -1e-12:
        return float(index)
    offset = 0.5 * float(left - right) / denominator
    if not np.isfinite(offset):
        return float(index)
    return float(index) + float(np.clip(offset, -1.0, 1.0))


def locate_session_anchor(
    reference_image: np.ndarray,
    target_image: np.ndarray,
    centers: np.ndarray,
    *,
    pitch_px: float,
) -> AnchorResult:
    centroid = np.asarray(centers, dtype=float).mean(axis=0)
    side = max(3, int(round(7.0 * float(pitch_px))))
    template = cv2.getRectSubPix(
        np.asarray(reference_image),
        (side, side),
        tuple(centroid.astype(np.float32)),
    )
    score = cv2.matchTemplate(
        np.asarray(target_image), template, cv2.TM_CCOEFF_NORMED
    )
    _, peak_score, _, peak = cv2.minMaxLoc(score)
    x0, y0 = int(peak[0]), int(peak[1])
    refined_x = subpixel_axis_peak(score[y0, :], x0)
    refined_y = subpixel_axis_peak(score[:, x0], y0)
    if refined_x is None or refined_y is None:
        return AnchorResult(False, np.nan, np.nan, float(peak_score), np.nan, "anchor_peak_at_border")

    yy, xx = np.ogrid[: score.shape[0], : score.shape[1]]
    outside = (xx - x0) ** 2 + (yy - y0) ** 2 > float(pitch_px) ** 2
    if not np.any(outside):
        return AnchorResult(False, np.nan, np.nan, float(peak_score), np.nan, "anchor_uniqueness_unavailable")
    second_peak = float(np.max(score[outside]))
    margin = float(peak_score) - second_peak
    if float(peak_score) < 0.80:
        return AnchorResult(False, np.nan, np.nan, float(peak_score), margin, "anchor_low_score")
    if margin < 0.01:
        return AnchorResult(False, np.nan, np.nan, float(peak_score), margin, "anchor_not_unique")

    anchor_center = np.asarray(
        [refined_x + (side - 1) / 2.0, refined_y + (side - 1) / 2.0]
    )
    offset = anchor_center - centroid
    return AnchorResult(
        True,
        float(offset[0]),
        float(offset[1]),
        float(peak_score),
        margin,
        "",
    )


def track_local_2d(
    images: list[np.ndarray],
    centers: np.ndarray,
    *,
    radius_px: float,
    expected_signed_dx_px: float,
    object_um_per_px: float,
) -> pd.DataFrame:
    positions = np.asarray(centers, dtype=float).copy()
    template_half = int(np.ceil(float(radius_px) + 2.0))
    search_radius = int(np.ceil(max(5.0, 0.25 * float(radius_px))))
    template_size = (2 * template_half + 1,) * 2
    search_size = (2 * (template_half + search_radius) + 1,) * 2
    records: list[dict[str, Any]] = []
    for step_index in range(1, len(images)):
        measurements: list[dict[str, Any]] = []
        next_positions: list[np.ndarray] = []
        for pillar_index, (x_px, y_px) in enumerate(positions):
            template = cv2.getRectSubPix(
                images[step_index - 1],
                template_size,
                (float(x_px), float(y_px)),
            )
            predicted = np.asarray(
                [x_px + float(expected_signed_dx_px), y_px], dtype=float
            )
            search = cv2.getRectSubPix(
                images[step_index],
                search_size,
                tuple(predicted.astype(np.float32)),
            )
            score = cv2.matchTemplate(search, template, cv2.TM_CCOEFF_NORMED)
            _, peak_score, _, peak = cv2.minMaxLoc(score)
            x0, y0 = int(peak[0]), int(peak[1])
            refined_x = subpixel_axis_peak(score[y0, :], x0)
            refined_y = subpixel_axis_peak(score[:, x0], y0)
            interior = refined_x is not None and refined_y is not None
            integer_offset = np.asarray(
                [x0 - search_radius, y0 - search_radius], dtype=float
            )
            if interior:
                offset = np.asarray(
                    [refined_x - search_radius, refined_y - search_radius],
                    dtype=float,
                )
            else:
                offset = integer_offset
            current = predicted + offset
            next_positions.append(current)
            measurements.append(
                {
                    "pillar_index": pillar_index,
                    "valid": bool(interior and float(peak_score) >= 0.95),
                    "score": float(peak_score),
                    "dx_px": float(current[0] - x_px),
                    "dy_px": float(current[1] - y_px),
                }
            )
        positions = np.asarray(next_positions, dtype=float)
        table = pd.DataFrame(measurements)
        valid = table["valid"].astype(bool)
        records.append(
            {
                "step_index": step_index,
                "local_valid_pillars": int(valid.sum()),
                "local_min_match_score": float(table["score"].min()),
                "local_dx_px": float(table["dx_px"].median()),
                "local_dy_px": float(table["dy_px"].median()),
                "local_dx_um": float(table["dx_px"].median()) * object_um_per_px,
                "local_dy_um": float(table["dy_px"].median()) * object_um_per_px,
                "local_pillar_dx_sd_nm": float(
                    table["dx_px"].std(ddof=1) * object_um_per_px * 1000.0
                ),
            }
        )
    return pd.DataFrame(records)


def apply_raw_eligibility(
    table: pd.DataFrame, *, tolerance_fraction: float
) -> pd.DataFrame:
    result = table.copy()
    eligible: list[bool] = []
    reasons_text: list[str] = []
    tolerance = float(tolerance_fraction)
    for row in result.to_dict(orient="records"):
        reasons: list[str] = []
        if bool(row["cross_session"]):
            reasons.append("cross_acquisition_session")
        else:
            if not bool(row["anchor_success"]):
                reasons.append("anchor_failed")
            if not bool(row["raw_boundary_valid"]):
                reasons.append("raw_boundary_invalid")
            if int(row["raw_boundary_valid_pillars"]) != 9:
                reasons.append("not_all_nine_raw_boundary")
            if int(row["raw_local_valid_pillars"]) != 9 or float(
                row["raw_local_min_match_score"]
            ) < 0.95:
                reasons.append("raw_local_invalid")
            nominal = float(row["nominal_step_um"])
            limit = tolerance * nominal
            if abs(
                float(row["raw_local_dx_um"])
                - float(row["expected_signed_step_um"])
            ) > limit:
                reasons.append("raw_x_command_incomplete")
            if abs(float(row["raw_local_dy_um"])) > limit:
                reasons.append("raw_y_cross_axis_excess")
            if abs(
                float(row["raw_boundary_dx_um"])
                - float(row["raw_local_dx_um"])
            ) > limit:
                reasons.append("raw_cross_method_disagreement")
        eligible.append(len(reasons) == 0)
        reasons_text.append(";".join(reasons))
    result["raw_eligible"] = eligible
    result["raw_exclusion_reasons"] = reasons_text
    return result


def classify_nm_difference(
    raw_nm: float, v42_nm: float, *, tie_margin_nm: float = 1.0
) -> str:
    difference = float(v42_nm) - float(raw_nm)
    if abs(difference) <= float(tie_margin_nm):
        return "tie"
    return "improved" if difference < 0 else "worse"


def robust_disagreement_nm(
    pillar_dx_px: np.ndarray, *, object_um_per_px: float
) -> float:
    values = np.asarray(pillar_dx_px, dtype=float)
    median = float(np.median(values))
    return float(
        1.4826
        * np.median(np.abs(values - median))
        * float(object_um_per_px)
        * 1000.0
    )


def summarize_paired_population(table: pd.DataFrame) -> dict[str, float | int]:
    paired = table.loc[table["v42_evaluable"].astype(bool)].copy()
    raw_values = paired["raw_boundary_dx_um"].dropna().to_numpy(dtype=float)
    v42_values = paired["v42_boundary_dx_um"].dropna().to_numpy(dtype=float)
    if len(raw_values) != len(v42_values):
        raise ValueError("paired Raw and V42 values must have identical counts")
    return {
        "paired_count": len(paired),
        "raw_mean_signed_step_um": float(np.mean(raw_values)) if len(raw_values) else np.nan,
        "v42_mean_signed_step_um": float(np.mean(v42_values)) if len(v42_values) else np.nan,
        "raw_signed_step_sd_nm": float(np.std(raw_values, ddof=1) * 1000.0)
        if len(raw_values) >= 2
        else np.nan,
        "v42_signed_step_sd_nm": float(np.std(v42_values, ddof=1) * 1000.0)
        if len(v42_values) >= 2
        else np.nan,
        "raw_mean_within_grid_nm": float(paired["raw_within_grid_nm"].mean()),
        "v42_mean_within_grid_nm": float(paired["v42_within_grid_nm"].mean()),
    }

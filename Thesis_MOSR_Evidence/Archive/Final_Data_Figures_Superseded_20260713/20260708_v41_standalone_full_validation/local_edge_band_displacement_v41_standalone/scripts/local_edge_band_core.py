from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy import ndimage


@dataclass(frozen=True)
class EdgeBandMeasurement:
    signed_dx_px: float
    usable_edges: int
    boundary_confidence: float
    localization_uncertainty_px: float
    edge_positions_px: tuple[float, ...]
    edge_shifts_px: tuple[float, ...]
    edge_weights: tuple[float, ...]


def normalize_image(image: np.ndarray) -> np.ndarray:
    arr = np.asarray(image, dtype=np.float64)
    lo, hi = np.nanpercentile(arr, [1.0, 99.0])
    if not np.isfinite(lo) or not np.isfinite(hi) or hi <= lo:
        return np.zeros_like(arr, dtype=np.float64)
    arr = np.clip((arr - lo) / (hi - lo), 0.0, 1.0)
    return arr


def crop_roi(image: np.ndarray, roi: tuple[int, int, int, int]) -> np.ndarray:
    x, y, w, h = [int(round(v)) for v in roi]
    if w <= 8 or h <= 8:
        raise ValueError(f"ROI is too small: {roi}")
    return np.asarray(image, dtype=np.float64)[y : y + h, x : x + w]


def choose_vertical_edge_centers(
    ref_roi: np.ndarray,
    expected_signed_dx_px: float,
    max_edges: int = 16,
    min_separation_px: int = 12,
    margin_px: int = 18,
) -> list[int]:
    smooth = ndimage.gaussian_filter(ref_roi, sigma=1.0)
    gx = np.abs(np.gradient(smooth, axis=1))
    col_strength = np.nanmean(gx, axis=0)
    move_margin = int(np.ceil(abs(expected_signed_dx_px))) + margin_px
    valid = np.zeros_like(col_strength, dtype=bool)
    valid[move_margin : len(valid) - move_margin] = True
    if valid.sum() <= 0:
        return []
    values = col_strength.copy()
    values[~valid] = -np.inf
    order = np.argsort(values)[::-1]
    centers: list[int] = []
    threshold = np.nanpercentile(col_strength[valid], 65.0)
    for idx in order:
        if not np.isfinite(values[idx]) or values[idx] <= threshold:
            break
        if all(abs(int(idx) - prev) >= min_separation_px for prev in centers):
            centers.append(int(idx))
            if len(centers) >= max_edges:
                break
    centers.sort()
    return centers


def row_weighted_profile(
    roi_img: np.ndarray,
    center_x: int,
    band_half_width_px: int = 6,
) -> tuple[np.ndarray, np.ndarray]:
    h, w = roi_img.shape
    left = max(0, int(center_x) - band_half_width_px)
    right = min(w, int(center_x) + band_half_width_px + 1)
    smooth = ndimage.gaussian_filter(roi_img, sigma=(1.0, 0.8))
    gx = np.abs(np.gradient(smooth, axis=1))
    row_strength = np.nanmean(gx[:, left:right], axis=1)
    cutoff = np.nanpercentile(row_strength, 35.0)
    weights = np.maximum(row_strength - cutoff, 0.0)
    if np.sum(weights) <= 1e-12:
        weights = np.ones(h, dtype=np.float64)
    weights = weights / np.sum(weights)
    profile = np.sum(roi_img * weights[:, None], axis=0)
    return profile, weights


def parabolic_peak_offset(y_minus: float, y0: float, y_plus: float) -> float:
    denom = y_minus - 2.0 * y0 + y_plus
    if abs(denom) < 1e-12:
        return 0.0
    offset = 0.5 * (y_minus - y_plus) / denom
    return float(np.clip(offset, -1.0, 1.0))


def locate_edge_position(
    profile: np.ndarray,
    expected_x: float,
    radius_px: int = 8,
) -> tuple[float, float, float]:
    profile = np.asarray(profile, dtype=np.float64)
    smoothed = ndimage.gaussian_filter1d(profile, sigma=0.9)
    derivative = np.gradient(smoothed)
    strength = np.abs(derivative)
    lo = max(1, int(np.floor(expected_x - radius_px)))
    hi = min(len(profile) - 2, int(np.ceil(expected_x + radius_px)))
    if hi <= lo:
        raise ValueError("edge search window is outside the profile")
    local = strength[lo : hi + 1]
    idx = int(np.argmax(local)) + lo
    offset = parabolic_peak_offset(strength[idx - 1], strength[idx], strength[idx + 1])
    pos = idx + offset
    peak = float(strength[idx])

    half = peak * 0.5
    left = idx
    while left > lo and strength[left] > half:
        left -= 1
    right = idx
    while right < hi and strength[right] > half:
        right += 1
    width = max(1.0, float(right - left))
    return float(pos), peak, width


def weighted_median(values: np.ndarray, weights: np.ndarray) -> float:
    if len(values) == 0:
        return float("nan")
    order = np.argsort(values)
    values = values[order]
    weights = weights[order]
    total = np.sum(weights)
    if total <= 1e-12:
        return float(np.median(values))
    cumsum = np.cumsum(weights)
    return float(values[np.searchsorted(cumsum, total * 0.5)])


def measure_pair_local_edge_displacement(
    ref_image: np.ndarray,
    mov_image: np.ndarray,
    expected_signed_dx_px: float,
    roi: tuple[int, int, int, int],
    max_edges: int = 18,
    min_edges: int = 3,
    band_half_width_px: int = 6,
    edge_search_radius_px: int = 8,
    edge_centers: tuple[int, ...] | list[int] | None = None,
) -> EdgeBandMeasurement:
    ref_roi = normalize_image(crop_roi(ref_image, roi))
    mov_roi = normalize_image(crop_roi(mov_image, roi))
    if edge_centers is None:
        centers = choose_vertical_edge_centers(
            ref_roi,
            expected_signed_dx_px=expected_signed_dx_px,
            max_edges=max_edges,
        )
    else:
        centers = [int(round(c)) for c in edge_centers][:max_edges]
    shifts: list[float] = []
    weights: list[float] = []
    positions: list[float] = []
    uncertainty_terms: list[float] = []
    for center in centers:
        try:
            ref_profile, _ = row_weighted_profile(ref_roi, center, band_half_width_px)
            mov_profile, _ = row_weighted_profile(mov_roi, center, band_half_width_px)
            ref_pos, ref_peak, ref_width = locate_edge_position(
                ref_profile, center, radius_px=edge_search_radius_px
            )
            mov_pos, mov_peak, mov_width = locate_edge_position(
                mov_profile,
                center + expected_signed_dx_px,
                radius_px=edge_search_radius_px + int(np.ceil(abs(expected_signed_dx_px) * 0.10)),
            )
        except ValueError:
            continue
        shift = mov_pos - ref_pos
        if abs(shift - expected_signed_dx_px) > max(2.5, abs(expected_signed_dx_px) * 0.45):
            continue
        sharpness = 1.0 / max(1.0, 0.5 * (ref_width + mov_width))
        peak = min(ref_peak, mov_peak)
        weight = max(0.0, peak) * sharpness
        if weight <= 1e-8:
            continue
        shifts.append(float(shift))
        weights.append(float(weight))
        positions.append(float(ref_pos))
        uncertainty_terms.append(float(0.5 * (ref_width + mov_width) / max(peak, 1e-6)))

    if len(shifts) < min_edges:
        return EdgeBandMeasurement(
            signed_dx_px=float("nan"),
            usable_edges=len(shifts),
            boundary_confidence=0.0,
            localization_uncertainty_px=float("inf"),
            edge_positions_px=tuple(positions),
            edge_shifts_px=tuple(shifts),
            edge_weights=tuple(weights),
        )

    shift_arr = np.asarray(shifts, dtype=np.float64)
    weight_arr = np.asarray(weights, dtype=np.float64)
    signed_dx = weighted_median(shift_arr, weight_arr)
    mad = weighted_median(np.abs(shift_arr - signed_dx), weight_arr)
    confidence = float(np.sum(weight_arr) / len(weight_arr))
    edge_uncertainty = float(np.median(uncertainty_terms) * 0.02 + mad)
    return EdgeBandMeasurement(
        signed_dx_px=float(signed_dx),
        usable_edges=len(shifts),
        boundary_confidence=confidence,
        localization_uncertainty_px=edge_uncertainty,
        edge_positions_px=tuple(positions),
        edge_shifts_px=tuple(shifts),
        edge_weights=tuple(weights),
    )

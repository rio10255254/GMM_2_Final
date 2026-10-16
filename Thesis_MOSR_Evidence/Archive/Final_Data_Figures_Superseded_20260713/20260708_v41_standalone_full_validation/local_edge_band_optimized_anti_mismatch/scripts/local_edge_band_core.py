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
    candidate_edges: int = 0
    rejected_edges: int = 0
    ambiguity_score: float = float("nan")
    consensus_mad_px: float = float("nan")


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


@dataclass(frozen=True)
class EdgeLocation:
    position_px: float
    peak: float
    width_px: float
    polarity: float
    ambiguity_ratio: float


def _edge_location_from_index(
    profile: np.ndarray,
    idx: int,
    lo: int,
    hi: int,
    ambiguity_radius_px: int,
    exclusion_radius_px: int,
) -> EdgeLocation:
    smoothed = ndimage.gaussian_filter1d(profile, sigma=0.9)
    derivative = np.gradient(smoothed)
    strength = np.abs(derivative)
    idx = int(np.clip(idx, 1, len(profile) - 2))
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

    amb_lo = max(1, idx - ambiguity_radius_px)
    amb_hi = min(len(profile) - 2, idx + ambiguity_radius_px)
    alt = strength[amb_lo : amb_hi + 1].copy()
    exc_lo = max(0, idx - exclusion_radius_px - amb_lo)
    exc_hi = min(len(alt), idx + exclusion_radius_px - amb_lo + 1)
    alt[exc_lo:exc_hi] = 0.0
    second_peak = float(np.nanmax(alt)) if len(alt) else 0.0
    ambiguity_ratio = second_peak / max(peak, 1e-9)
    polarity = float(np.sign(derivative[idx]))
    return EdgeLocation(
        position_px=float(pos),
        peak=peak,
        width_px=width,
        polarity=polarity,
        ambiguity_ratio=float(np.clip(ambiguity_ratio, 0.0, 2.0)),
    )


def locate_edge_position_detailed(
    profile: np.ndarray,
    expected_x: float,
    radius_px: int = 8,
    ambiguity_radius_px: int = 14,
    exclusion_radius_px: int = 2,
) -> EdgeLocation:
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
    return _edge_location_from_index(
        profile,
        idx=idx,
        lo=lo,
        hi=hi,
        ambiguity_radius_px=ambiguity_radius_px,
        exclusion_radius_px=exclusion_radius_px,
    )


def locate_edge_candidates(
    profile: np.ndarray,
    expected_x: float,
    radius_px: int = 8,
    max_candidates: int = 6,
    min_separation_px: int = 2,
) -> list[EdgeLocation]:
    profile = np.asarray(profile, dtype=np.float64)
    smoothed = ndimage.gaussian_filter1d(profile, sigma=0.9)
    strength = np.abs(np.gradient(smoothed))
    lo = max(1, int(np.floor(expected_x - radius_px)))
    hi = min(len(profile) - 2, int(np.ceil(expected_x + radius_px)))
    if hi <= lo:
        raise ValueError("edge search window is outside the profile")
    values = strength[lo : hi + 1]
    threshold = max(float(np.nanpercentile(values, 55.0)), float(np.nanmax(values)) * 0.18)
    order = np.argsort(values)[::-1]
    locations: list[EdgeLocation] = []
    used: list[int] = []
    for local_idx in order:
        idx = int(local_idx) + lo
        if strength[idx] < threshold:
            break
        if any(abs(idx - prev) < min_separation_px for prev in used):
            continue
        used.append(idx)
        locations.append(
            _edge_location_from_index(
                profile,
                idx=idx,
                lo=lo,
                hi=hi,
                ambiguity_radius_px=14,
                exclusion_radius_px=2,
            )
        )
        if len(locations) >= max_candidates:
            break
    if not locations:
        locations.append(locate_edge_position_detailed(profile, expected_x, radius_px=radius_px))
    return locations


def _sample_profile(profile: np.ndarray, center_x: float, half_width_px: int) -> np.ndarray:
    x = np.arange(len(profile), dtype=np.float64)
    coords = center_x + np.arange(-half_width_px, half_width_px + 1, dtype=np.float64)
    return np.interp(coords, x, profile, left=np.nan, right=np.nan)


def _safe_corr(a: np.ndarray, b: np.ndarray) -> float:
    mask = np.isfinite(a) & np.isfinite(b)
    if mask.sum() < 5:
        return 0.0
    a = a[mask].astype(np.float64)
    b = b[mask].astype(np.float64)
    a = a - np.mean(a)
    b = b - np.mean(b)
    denom = np.linalg.norm(a) * np.linalg.norm(b)
    if denom <= 1e-12:
        return 0.0
    return float(np.clip(np.dot(a, b) / denom, -1.0, 1.0))


def local_edge_profile_similarity(
    ref_profile: np.ndarray,
    mov_profile: np.ndarray,
    ref_pos: float,
    mov_pos: float,
    half_width_px: int = 9,
) -> float:
    ref_smooth = ndimage.gaussian_filter1d(np.asarray(ref_profile, dtype=np.float64), sigma=0.8)
    mov_smooth = ndimage.gaussian_filter1d(np.asarray(mov_profile, dtype=np.float64), sigma=0.8)
    ref_patch = _sample_profile(ref_smooth, ref_pos, half_width_px)
    mov_patch = _sample_profile(mov_smooth, mov_pos, half_width_px)
    ref_deriv = _sample_profile(np.gradient(ref_smooth), ref_pos, half_width_px)
    mov_deriv = _sample_profile(np.gradient(mov_smooth), mov_pos, half_width_px)
    intensity_corr = _safe_corr(ref_patch, mov_patch)
    derivative_corr = _safe_corr(ref_deriv, mov_deriv)
    score = 0.55 * max(0.0, intensity_corr) + 0.45 * max(0.0, derivative_corr)
    return float(np.clip(score, 0.0, 1.0))


def refine_shift_by_profile_alignment(
    ref_profile: np.ndarray,
    mov_profile: np.ndarray,
    ref_pos: float,
    expected_signed_dx_px: float,
    search_radius_px: float,
    half_width_px: int = 12,
    step_px: float = 0.10,
) -> tuple[float, float]:
    ref_smooth = ndimage.gaussian_filter1d(np.asarray(ref_profile, dtype=np.float64), sigma=0.8)
    mov_smooth = ndimage.gaussian_filter1d(np.asarray(mov_profile, dtype=np.float64), sigma=0.8)
    coords = np.arange(-half_width_px, half_width_px + 1, dtype=np.float64)
    ref_patch = _sample_profile(ref_smooth, ref_pos, half_width_px)
    shifts = np.arange(
        expected_signed_dx_px - search_radius_px,
        expected_signed_dx_px + search_radius_px + step_px * 0.5,
        step_px,
        dtype=np.float64,
    )
    scores = []
    x = np.arange(len(mov_smooth), dtype=np.float64)
    for shift in shifts:
        mov_patch = np.interp(ref_pos + shift + coords, x, mov_smooth, left=np.nan, right=np.nan)
        scores.append(_safe_corr(ref_patch, mov_patch))
    scores_arr = np.asarray(scores, dtype=np.float64)
    if len(scores_arr) == 0 or not np.isfinite(scores_arr).any():
        return float(expected_signed_dx_px), 0.0
    best_idx = int(np.nanargmax(scores_arr))
    best_shift = float(shifts[best_idx])
    if 0 < best_idx < len(scores_arr) - 1:
        offset = parabolic_peak_offset(
            float(scores_arr[best_idx - 1]),
            float(scores_arr[best_idx]),
            float(scores_arr[best_idx + 1]),
        )
        best_shift += float(offset * step_px)
    return best_shift, float(np.clip(scores_arr[best_idx], -1.0, 1.0))


def choose_motion_edge_candidate(
    ref_profile: np.ndarray,
    mov_profile: np.ndarray,
    ref_loc: EdgeLocation,
    mov_candidates: list[EdgeLocation],
    expected_signed_dx_px: float,
    shift_tolerance_px: float,
) -> tuple[EdgeLocation, float, float, int] | None:
    best: tuple[float, EdgeLocation, float, float, int] | None = None
    broad_tolerance = max(shift_tolerance_px * 2.8, 1.8)
    for candidate_index, mov_loc in enumerate(mov_candidates):
        if ref_loc.polarity != 0 and mov_loc.polarity != 0 and ref_loc.polarity != mov_loc.polarity:
            continue
        shift = mov_loc.position_px - ref_loc.position_px
        shift_error = abs(shift - expected_signed_dx_px)
        if shift_error > broad_tolerance:
            continue
        similarity = local_edge_profile_similarity(
            ref_profile,
            mov_profile,
            ref_loc.position_px,
            mov_loc.position_px,
            half_width_px=9,
        )
        ambiguity = max(ref_loc.ambiguity_ratio, mov_loc.ambiguity_ratio)
        expected_score = np.exp(-0.5 * (shift_error / max(shift_tolerance_px, 1e-6)) ** 2)
        clarity_score = float(np.clip(1.0 - ambiguity * 0.55, 0.25, 1.0))
        score = float(expected_score * (0.25 + 0.75 * similarity) * clarity_score)
        if best is None or score > best[0]:
            best = (score, mov_loc, similarity, ambiguity, candidate_index)
    if best is None:
        return None
    _, mov_loc, similarity, ambiguity, candidate_index = best
    return mov_loc, similarity, ambiguity, candidate_index


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
    max_ambiguity_ratio: float = 0.88,
    min_profile_similarity: float = 0.22,
    strict_expected_gate: bool = True,
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
    ambiguity_terms: list[float] = []
    candidate_edges = len(centers)
    rejected_edges = 0
    shift_tolerance = max(0.75, min(2.35, abs(expected_signed_dx_px) * 0.20 + 0.45))
    for center in centers:
        try:
            ref_profile, _ = row_weighted_profile(ref_roi, center, band_half_width_px)
            mov_profile, _ = row_weighted_profile(mov_roi, center, band_half_width_px)
            ref_loc = locate_edge_candidates(
                ref_profile,
                center,
                radius_px=edge_search_radius_px,
                max_candidates=3,
            )[0]
            mov_candidates = locate_edge_candidates(
                mov_profile,
                center + expected_signed_dx_px,
                radius_px=edge_search_radius_px + int(np.ceil(abs(expected_signed_dx_px) * 0.10)),
                max_candidates=7,
            )
        except ValueError:
            rejected_edges += 1
            continue
        chosen = choose_motion_edge_candidate(
            ref_profile,
            mov_profile,
            ref_loc,
            mov_candidates,
            expected_signed_dx_px,
            shift_tolerance,
        )
        if chosen is None:
            rejected_edges += 1
            continue
        mov_loc, similarity, ambiguity, candidate_index = chosen
        if candidate_index > 0:
            rejected_edges += int(candidate_index)
        profile_shift, profile_score = refine_shift_by_profile_alignment(
            ref_profile,
            mov_profile,
            ref_loc.position_px,
            expected_signed_dx_px,
            search_radius_px=max(0.75, min(1.45, shift_tolerance)),
        )
        shift = profile_shift if profile_score >= min_profile_similarity else mov_loc.position_px - ref_loc.position_px
        similarity = max(similarity, profile_score)
        if strict_expected_gate and abs(shift - expected_signed_dx_px) > shift_tolerance:
            rejected_edges += 1
            continue
        if ambiguity > max_ambiguity_ratio and similarity < 0.55:
            rejected_edges += 1
            continue
        if similarity < min_profile_similarity:
            rejected_edges += 1
            continue
        sharpness = 1.0 / max(1.0, 0.5 * (ref_loc.width_px + mov_loc.width_px))
        peak = min(ref_loc.peak, mov_loc.peak)
        uniqueness_weight = float(np.clip(1.0 - ambiguity * 0.65, 0.15, 1.0))
        similarity_weight = float(np.clip(similarity, 0.15, 1.0))
        weight = max(0.0, peak) * sharpness * uniqueness_weight * similarity_weight
        if weight <= 1e-8:
            rejected_edges += 1
            continue
        shifts.append(float(shift))
        weights.append(float(weight))
        positions.append(float(ref_loc.position_px))
        uncertainty_terms.append(float(0.5 * (ref_loc.width_px + mov_loc.width_px) / max(peak, 1e-6)))
        mismatch_risk = (
            abs(shift - expected_signed_dx_px)
            / max(shift_tolerance, 1e-6)
            * ambiguity
            * (1.0 - similarity)
        )
        ambiguity_terms.append(float(np.clip(mismatch_risk, 0.0, 2.0)))

    if len(shifts) < min_edges:
        return EdgeBandMeasurement(
            signed_dx_px=float("nan"),
            usable_edges=len(shifts),
            boundary_confidence=0.0,
            localization_uncertainty_px=float("inf"),
            edge_positions_px=tuple(positions),
            edge_shifts_px=tuple(shifts),
            edge_weights=tuple(weights),
            candidate_edges=candidate_edges,
            rejected_edges=rejected_edges,
            ambiguity_score=float(np.nanmedian(ambiguity_terms)) if ambiguity_terms else float("inf"),
            consensus_mad_px=float("inf"),
        )

    shift_arr = np.asarray(shifts, dtype=np.float64)
    weight_arr = np.asarray(weights, dtype=np.float64)
    signed_dx_initial = weighted_median(shift_arr, weight_arr)
    consensus_tolerance = max(0.45, min(1.65, abs(expected_signed_dx_px) * 0.12 + 0.35))
    consensus_keep = np.abs(shift_arr - signed_dx_initial) <= consensus_tolerance
    expected_keep = np.abs(shift_arr - expected_signed_dx_px) <= shift_tolerance
    keep = consensus_keep & expected_keep
    if np.sum(keep) >= min_edges:
        rejected_edges += int(np.sum(~keep))
        shifts = [v for v, ok in zip(shifts, keep) if ok]
        weights = [v for v, ok in zip(weights, keep) if ok]
        positions = [v for v, ok in zip(positions, keep) if ok]
        uncertainty_terms = [v for v, ok in zip(uncertainty_terms, keep) if ok]
        ambiguity_terms = [v for v, ok in zip(ambiguity_terms, keep) if ok]
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
        candidate_edges=candidate_edges,
        rejected_edges=rejected_edges,
        ambiguity_score=float(np.nanmedian(ambiguity_terms)) if ambiguity_terms else float("inf"),
        consensus_mad_px=float(mad),
    )

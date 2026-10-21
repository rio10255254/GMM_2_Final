from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

import cv2
import numpy as np
from scipy import ndimage, optimize
from scipy.signal import fftconvolve
from skimage import measure, morphology, segmentation


@dataclass(frozen=True)
class Circle:
    cx: float
    cy: float
    radius: float


@dataclass(frozen=True)
class ReferenceCircleResult:
    lsc: Circle
    mzc: Circle
    mic: Circle
    mcc: Circle
    mzc_zone_width: float
    center_spread: float
    harmonic2_amplitude: float
    harmonic4_amplitude: float


@dataclass(frozen=True)
class BoundaryMeasurement:
    coarse_contour_xy: np.ndarray
    inflection_points_xy: np.ndarray
    coarse_mask: np.ndarray
    circles: ReferenceCircleResult
    signed_gradient_strength: np.ndarray


@dataclass(frozen=True)
class InflectionLSCMeasurement:
    coarse_contour_xy: np.ndarray
    inflection_points_xy: np.ndarray
    coarse_mask: np.ndarray
    lsc: Circle
    signed_gradient_strength: np.ndarray


def _normalized_image(image: np.ndarray) -> np.ndarray:
    values = np.asarray(image, dtype=np.float64)
    finite = values[np.isfinite(values)]
    if finite.size == 0:
        raise ValueError("image contains no finite values")
    lo, hi = np.percentile(finite, [1.0, 99.0])
    if hi <= lo:
        hi = lo + 1.0
    return np.clip((values - lo) / (hi - lo), 0.0, 1.0)


def _initial_circle(shape: tuple[int, int], center_xy: tuple[float, float], radius: float) -> np.ndarray:
    yy, xx = np.mgrid[: shape[0], : shape[1]]
    cx, cy = center_xy
    return (xx - cx) ** 2 + (yy - cy) ** 2 <= radius**2


def _component_nearest_center(mask: np.ndarray, center_xy: tuple[float, float]) -> np.ndarray:
    labels = measure.label(mask.astype(bool), connectivity=2)
    regions = measure.regionprops(labels)
    if not regions:
        return mask.astype(bool)
    cx, cy = center_xy
    selected = min(
        regions,
        key=lambda region: (region.centroid[1] - cx) ** 2 + (region.centroid[0] - cy) ** 2,
    )
    return labels == selected.label


def acm_coarse_mask(
    image: np.ndarray,
    center_xy: tuple[float, float],
    radius_px: float,
    *,
    iterations: int = 24,
    smoothing: int = 1,
) -> np.ndarray:
    """Return a Chan-Vese active-contour mask initialized by a geometric circle."""

    normalized = _normalized_image(image)
    initial = _initial_circle(normalized.shape, center_xy, radius_px)
    evolved = segmentation.morphological_chan_vese(
        normalized,
        num_iter=int(iterations),
        init_level_set=initial,
        smoothing=int(smoothing),
        lambda1=1.0,
        lambda2=1.0,
    )
    selected = _component_nearest_center(evolved, center_xy)
    selected = morphology.remove_small_holes(selected, area_threshold=max(4, int(radius_px)))
    return selected.astype(bool)


def _largest_contour_xy(mask: np.ndarray, center_xy: tuple[float, float]) -> np.ndarray:
    contours = measure.find_contours(mask.astype(np.float64), 0.5)
    if not contours:
        raise ValueError("active contour produced no closed boundary")
    cx, cy = center_xy

    def score(contour_rc: np.ndarray) -> tuple[float, float]:
        x = contour_rc[:, 1]
        y = contour_rc[:, 0]
        distance = (float(np.mean(x)) - cx) ** 2 + (float(np.mean(y)) - cy) ** 2
        return distance, -float(len(contour_rc))

    contour = min(contours, key=score)
    return np.column_stack([contour[:, 1], contour[:, 0]])


def resample_closed_contour(points_xy: np.ndarray, sample_count: int) -> np.ndarray:
    points = np.asarray(points_xy, dtype=np.float64)
    if points.shape[0] < 8:
        raise ValueError("contour is too short")
    closed = np.vstack([points, points[0]])
    segment = np.linalg.norm(np.diff(closed, axis=0), axis=1)
    cumulative = np.concatenate([[0.0], np.cumsum(segment)])
    total = float(cumulative[-1])
    if total <= 0:
        raise ValueError("contour has zero length")
    targets = np.linspace(0.0, total, int(sample_count), endpoint=False)
    x = np.interp(targets, cumulative, closed[:, 0])
    y = np.interp(targets, cumulative, closed[:, 1])
    return np.column_stack([x, y])


def _outward_normals(points_xy: np.ndarray) -> np.ndarray:
    points = np.asarray(points_xy, dtype=np.float64)
    tangent = np.roll(points, -1, axis=0) - np.roll(points, 1, axis=0)
    tangent_norm = np.linalg.norm(tangent, axis=1, keepdims=True)
    tangent_norm[tangent_norm == 0] = 1.0
    tangent /= tangent_norm
    normal = np.column_stack([-tangent[:, 1], tangent[:, 0]])
    centroid = np.mean(points, axis=0)
    radial = points - centroid
    flip = np.sum(normal * radial, axis=1) < 0
    normal[flip] *= -1.0
    return normal


def refine_to_inflection_points(
    image: np.ndarray,
    coarse_contour_xy: np.ndarray,
    *,
    normal_half_width_px: float,
    profile_step_px: float = 0.10,
    profile_sigma_px: float = 0.65,
    polarity: str = "auto",
) -> tuple[np.ndarray, np.ndarray]:
    """Select the correct-polarity maximum-gradient point on each contour normal."""

    values = np.asarray(image, dtype=np.float64)
    points = np.asarray(coarse_contour_xy, dtype=np.float64)
    normals = _outward_normals(points)
    offsets = np.arange(
        -float(normal_half_width_px),
        float(normal_half_width_px) + profile_step_px * 0.5,
        float(profile_step_px),
    )
    refined: list[np.ndarray] = []
    strengths: list[float] = []
    sigma_samples = max(0.01, float(profile_sigma_px) / float(profile_step_px))

    for point, normal in zip(points, normals):
        sample_xy = point[None, :] + offsets[:, None] * normal[None, :]
        profile = ndimage.map_coordinates(
            values,
            [sample_xy[:, 1], sample_xy[:, 0]],
            order=3,
            mode="reflect",
        )
        smooth = ndimage.gaussian_filter1d(profile, sigma=sigma_samples, mode="nearest")
        derivative = np.gradient(smooth, offsets)
        if polarity == "dark":
            signed = derivative
        elif polarity == "bright":
            signed = -derivative
        elif polarity == "auto":
            direction = 1.0 if np.median(smooth[-5:]) >= np.median(smooth[:5]) else -1.0
            signed = direction * derivative
        else:
            raise ValueError(f"unknown polarity: {polarity}")

        peak_index = int(np.argmax(signed))
        peak_offset = float(offsets[peak_index])
        peak_strength = float(signed[peak_index])
        if 0 < peak_index < len(offsets) - 1:
            left, middle, right = signed[peak_index - 1 : peak_index + 2]
            denominator = left - 2.0 * middle + right
            if abs(float(denominator)) > np.finfo(float).eps:
                delta = 0.5 * float(left - right) / float(denominator)
                delta = float(np.clip(delta, -1.0, 1.0))
                peak_offset += delta * float(profile_step_px)
                peak_strength = float(middle - 0.25 * (left - right) * delta)
        refined.append(point + peak_offset * normal)
        strengths.append(peak_strength)

    return np.asarray(refined), np.asarray(strengths)


def fit_lsc(points_xy: np.ndarray) -> Circle:
    points = np.asarray(points_xy, dtype=np.float64)
    initial_center = np.mean(points, axis=0)
    initial_radius = float(np.mean(np.linalg.norm(points - initial_center, axis=1)))

    def residual(parameters: np.ndarray) -> np.ndarray:
        cx, cy, radius = parameters
        return np.linalg.norm(points - np.array([cx, cy]), axis=1) - radius

    fit = optimize.least_squares(
        residual,
        np.array([initial_center[0], initial_center[1], initial_radius]),
        method="trf",
    )
    return Circle(float(fit.x[0]), float(fit.x[1]), float(abs(fit.x[2])))


def fit_mzc(points_xy: np.ndarray, initial: Circle) -> tuple[Circle, float]:
    points = np.asarray(points_xy, dtype=np.float64)

    def zone(center: np.ndarray) -> float:
        radii = np.linalg.norm(points - center[None, :], axis=1)
        return float(np.max(radii) - np.min(radii))

    fit = optimize.minimize(
        zone,
        np.array([initial.cx, initial.cy]),
        method="Nelder-Mead",
        options={"xatol": 1e-8, "fatol": 1e-8, "maxiter": 4000},
    )
    center = fit.x
    radii = np.linalg.norm(points - center[None, :], axis=1)
    radius = 0.5 * (float(np.max(radii)) + float(np.min(radii)))
    return Circle(float(center[0]), float(center[1]), radius), float(np.ptp(radii))


def fit_mcc(points_xy: np.ndarray) -> Circle:
    points = np.asarray(points_xy, dtype=np.float32).reshape(-1, 1, 2)
    (cx, cy), radius = cv2.minEnclosingCircle(points)
    return Circle(float(cx), float(cy), float(radius))


def fit_mic(points_xy: np.ndarray, initial: Circle) -> Circle:
    polygon = np.asarray(points_xy, dtype=np.float32).reshape(-1, 1, 2)
    points = polygon[:, 0, :].astype(np.float64)
    x_min, y_min = np.min(points, axis=0)
    x_max, y_max = np.max(points, axis=0)
    xs = np.linspace(x_min, x_max, 25)
    ys = np.linspace(y_min, y_max, 25)
    candidates: list[tuple[float, float, float]] = []
    for y in ys:
        for x in xs:
            distance = float(cv2.pointPolygonTest(polygon, (float(x), float(y)), True))
            candidates.append((distance, float(x), float(y)))
    candidates.append(
        (
            float(cv2.pointPolygonTest(polygon, (initial.cx, initial.cy), True)),
            initial.cx,
            initial.cy,
        )
    )
    best = max(candidates, key=lambda item: item[0])

    def objective(center: np.ndarray) -> float:
        x = float(np.clip(center[0], x_min, x_max))
        y = float(np.clip(center[1], y_min, y_max))
        return -float(cv2.pointPolygonTest(polygon, (x, y), True))

    fit = optimize.minimize(
        objective,
        np.array([best[1], best[2]], dtype=float),
        method="Nelder-Mead",
        options={"xatol": 1e-7, "fatol": 1e-7, "maxiter": 1500},
    )
    cx = float(np.clip(fit.x[0], x_min, x_max))
    cy = float(np.clip(fit.x[1], y_min, y_max))
    radius = float(cv2.pointPolygonTest(polygon, (cx, cy), True))
    return Circle(cx, cy, max(0.0, radius))


def _harmonic_amplitude(points_xy: np.ndarray, circle: Circle, order: int) -> float:
    delta = np.asarray(points_xy, dtype=np.float64) - np.array([circle.cx, circle.cy])
    angle = np.arctan2(delta[:, 1], delta[:, 0])
    radius = np.linalg.norm(delta, axis=1)
    residual = radius - float(np.mean(radius))
    design = np.column_stack([np.cos(order * angle), np.sin(order * angle)])
    coefficients, *_ = np.linalg.lstsq(design, residual, rcond=None)
    return float(np.linalg.norm(coefficients))


def fit_reference_circles(points_xy: np.ndarray) -> ReferenceCircleResult:
    lsc = fit_lsc(points_xy)
    mzc, zone = fit_mzc(points_xy, lsc)
    mic = fit_mic(points_xy, lsc)
    mcc = fit_mcc(points_xy)
    centers = np.array(
        [[lsc.cx, lsc.cy], [mzc.cx, mzc.cy], [mic.cx, mic.cy], [mcc.cx, mcc.cy]],
        dtype=float,
    )
    center_spread = float(
        max(np.linalg.norm(left - right) for left in centers for right in centers)
    )
    return ReferenceCircleResult(
        lsc=lsc,
        mzc=mzc,
        mic=mic,
        mcc=mcc,
        mzc_zone_width=zone,
        center_spread=center_spread,
        harmonic2_amplitude=_harmonic_amplitude(points_xy, lsc, 2),
        harmonic4_amplitude=_harmonic_amplitude(points_xy, lsc, 4),
    )


def measure_boundary_and_circles(
    image: np.ndarray,
    center_xy: tuple[float, float],
    radius_px: float,
    *,
    coarse_mask: np.ndarray | None = None,
    sample_count: int = 144,
    acm_iterations: int = 24,
    normal_half_width_px: float | None = None,
    polarity: str = "dark",
) -> BoundaryMeasurement:
    if coarse_mask is None:
        coarse_mask = acm_coarse_mask(
            image,
            center_xy,
            radius_px,
            iterations=acm_iterations,
            smoothing=1,
        )
    else:
        coarse_mask = _component_nearest_center(np.asarray(coarse_mask, dtype=bool), center_xy)
    contour = _largest_contour_xy(coarse_mask, center_xy)
    contour = resample_closed_contour(contour, sample_count)
    if normal_half_width_px is None:
        normal_half_width_px = max(2.0, min(5.5, radius_px * 0.32))
    refined, strength = refine_to_inflection_points(
        image,
        contour,
        normal_half_width_px=normal_half_width_px,
        profile_step_px=0.10,
        profile_sigma_px=0.65,
        polarity=polarity,
    )
    circles = fit_reference_circles(refined)
    return BoundaryMeasurement(
        coarse_contour_xy=contour,
        inflection_points_xy=refined,
        coarse_mask=np.asarray(coarse_mask, dtype=bool),
        circles=circles,
        signed_gradient_strength=strength,
    )


def measure_inflection_lsc(
    image: np.ndarray,
    center_xy: tuple[float, float],
    radius_px: float,
    *,
    sample_count: int = 96,
    acm_iterations: int = 16,
    normal_half_width_px: float | None = None,
    polarity: str = "dark",
) -> InflectionLSCMeasurement:
    coarse_mask = acm_coarse_mask(
        image,
        center_xy,
        radius_px,
        iterations=acm_iterations,
        smoothing=1,
    )
    contour = _largest_contour_xy(coarse_mask, center_xy)
    contour = resample_closed_contour(contour, sample_count)
    if normal_half_width_px is None:
        normal_half_width_px = max(2.0, min(5.5, radius_px * 0.32))
    refined, strength = refine_to_inflection_points(
        image,
        contour,
        normal_half_width_px=normal_half_width_px,
        profile_step_px=0.10,
        profile_sigma_px=0.65,
        polarity=polarity,
    )
    return InflectionLSCMeasurement(
        coarse_contour_xy=contour,
        inflection_points_xy=refined,
        coarse_mask=coarse_mask,
        lsc=fit_lsc(refined),
        signed_gradient_strength=strength,
    )


def crop_around(
    image: np.ndarray,
    center_xy: tuple[float, float],
    half_size: int,
) -> tuple[np.ndarray, tuple[float, float], tuple[int, int]]:
    values = np.asarray(image)
    cx, cy = center_xy
    x0 = max(0, int(np.floor(cx)) - int(half_size))
    y0 = max(0, int(np.floor(cy)) - int(half_size))
    x1 = min(values.shape[1], int(np.floor(cx)) + int(half_size) + 1)
    y1 = min(values.shape[0], int(np.floor(cy)) + int(half_size) + 1)
    crop = values[y0:y1, x0:x1]
    return crop, (cx - x0, cy - y0), (x0, y0)


def wiener_contrast_restore(
    image: np.ndarray,
    psf: np.ndarray,
    nsr: float,
    *,
    pitch_px: float,
) -> np.ndarray:
    """Background-preserving Wiener restoration used for the compact baseline."""

    values = np.asarray(image, dtype=np.float64)
    radius = max(2, int(round(0.36 * float(pitch_px))))
    background = ndimage.grey_closing(values, footprint=morphology.disk(radius))
    contrast = np.maximum(background - values, 0.0)
    contrast_scale = float(np.percentile(contrast, 99.5))
    if contrast_scale <= 0:
        return values.copy()
    normalized = contrast / contrast_scale
    kernel = np.asarray(psf, dtype=np.float64)
    kernel = np.maximum(kernel, 0.0)
    kernel_sum = float(np.sum(kernel))
    if kernel_sum <= 0:
        raise ValueError("PSF has no positive energy")
    kernel /= kernel_sum
    pad_y = kernel.shape[0] // 2
    pad_x = kernel.shape[1] // 2
    padded = np.pad(normalized, ((pad_y, pad_y), (pad_x, pad_x)), mode="symmetric")
    impulse = np.zeros_like(padded)
    impulse[: kernel.shape[0], : kernel.shape[1]] = kernel
    impulse = np.roll(impulse, -pad_y, axis=0)
    impulse = np.roll(impulse, -pad_x, axis=1)
    transfer = np.fft.fft2(impulse)
    restored_frequency = np.conj(transfer) / (np.abs(transfer) ** 2 + float(nsr)) * np.fft.fft2(padded)
    restored_contrast = np.real(np.fft.ifft2(restored_frequency))
    restored_contrast = restored_contrast[pad_y : pad_y + values.shape[0], pad_x : pad_x + values.shape[1]]
    return background - contrast_scale * restored_contrast


def circle_to_row(prefix: str, circle: Circle, scale_um_per_px: float) -> dict[str, float]:
    return {
        f"{prefix}_center_x_px": circle.cx,
        f"{prefix}_center_y_px": circle.cy,
        f"{prefix}_radius_px": circle.radius,
        f"{prefix}_diameter_um": 2.0 * circle.radius * float(scale_um_per_px),
    }


def summarize_reference_circles(
    measurement: BoundaryMeasurement,
    *,
    scale_um_per_px: float,
) -> dict[str, float]:
    circles = measurement.circles
    result: dict[str, float] = {}
    for name, circle in (
        ("lsc", circles.lsc),
        ("mzc", circles.mzc),
        ("mic", circles.mic),
        ("mcc", circles.mcc),
    ):
        result.update(circle_to_row(name, circle, scale_um_per_px))
    result.update(
        {
            "mzc_roundness_um": circles.mzc_zone_width * float(scale_um_per_px),
            "center_spread_um": circles.center_spread * float(scale_um_per_px),
            "harmonic2_amplitude_um": circles.harmonic2_amplitude * float(scale_um_per_px),
            "harmonic4_amplitude_um": circles.harmonic4_amplitude * float(scale_um_per_px),
            "harmonic2_relative_pct": 100.0 * circles.harmonic2_amplitude / circles.lsc.radius,
            "harmonic4_relative_pct": 100.0 * circles.harmonic4_amplitude / circles.lsc.radius,
            "gradient_strength_median": float(np.median(measurement.signed_gradient_strength)),
        }
    )
    return result

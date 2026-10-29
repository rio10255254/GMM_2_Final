"""
GeoEdge R26 Single-Image Reconstruction Analysis
=================================================
Analyzes single-image reconstruction quality from the perspective of
geometric localization accuracy.
"""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import cv2
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from scipy import ndimage, optimize

sys.path.insert(
    0,
    str(Path(__file__).resolve().parents[5] / "Model"),
)
from GeoEdgeAlignSR_v1_Utils import imread_unicode


ROOT_DIR = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT_DIR / "results"
REPORT_PATH = ROOT_DIR / "reports" / "R26_SingleImage_Analysis_Report.md"
INPUT_PATH = ROOT_DIR / "inputs" / "VisionTop_20251029182653732.bmp"


def _find_default_recon_path() -> Path:
    matches = sorted((ROOT_DIR / "recon").glob("reconstruct_progress_*/*.bmp"))
    if not matches:
        raise FileNotFoundError("No reconstruction BMP found under recon/reconstruct_progress_*/")
    return matches[0]


RECON_PATH = _find_default_recon_path()


def load_image(path: str | Path) -> np.ndarray:
    return imread_unicode(str(path)).astype(np.float64)


def safe_mean(arr: np.ndarray) -> float:
    return float(np.nanmean(arr)) if len(arr) > 0 else float("nan")


def safe_std(arr: np.ndarray) -> float:
    return float(np.nanstd(arr)) if len(arr) > 0 else float("nan")


def subpix_peak(arr: np.ndarray, idx: int) -> float:
    if idx <= 0 or idx >= len(arr) - 1:
        return float(idx)
    a, b, c = float(arr[idx - 1]), float(arr[idx]), float(arr[idx + 1])
    denom = 2.0 * (2.0 * b - a - c)
    if abs(denom) < 1e-10:
        return float(idx)
    return idx + (a - c) / denom


def radial_profile(image: np.ndarray, cx: float, cy: float) -> np.ndarray:
    yy, xx = np.indices(image.shape)
    rr = np.sqrt((xx - cx) ** 2 + (yy - cy) ** 2)
    ridx = np.floor(rr).astype(np.int32)
    sums = np.bincount(ridx.ravel(), weights=image.ravel().astype(np.float64))
    counts = np.bincount(ridx.ravel())
    return sums / np.maximum(counts, 1)


def profile_half_value_edges(profile: np.ndarray) -> dict[str, object]:
    smooth_profile = ndimage.uniform_filter1d(profile.astype(np.float64), size=7, mode="nearest")
    start = min(10, len(smooth_profile) - 1)
    peak_r = int(np.argmax(smooth_profile[start:])) + start
    peak_val = float(smooth_profile[peak_r])
    left_slice = smooth_profile[max(0, peak_r - 120) : max(peak_r - 20, 1)]
    right_slice = smooth_profile[
        min(peak_r + 20, len(smooth_profile) - 1) : min(peak_r + 120, len(smooth_profile))
    ]
    if len(left_slice) == 0 or len(right_slice) == 0:
        raise RuntimeError("Ring profile does not contain enough support for edge detection.")
    baseline = float(np.mean([np.percentile(left_slice, 20), np.percentile(right_slice, 20)]))
    half_value = baseline + (peak_val - baseline) * 0.5
    inner_edge_r = peak_r
    while inner_edge_r > 1 and smooth_profile[inner_edge_r] > half_value:
        inner_edge_r -= 1
    outer_edge_r = peak_r
    while outer_edge_r < len(smooth_profile) - 2 and smooth_profile[outer_edge_r] > half_value:
        outer_edge_r += 1
    return {
        "peak_r": float(peak_r),
        "inner_edge_r": float(inner_edge_r),
        "outer_edge_r": float(outer_edge_r),
        "baseline_value": baseline,
        "peak_value": peak_val,
        "half_value": half_value,
        "smooth_profile": smooth_profile,
    }


def fit_circle(
    points_xy: list[tuple[float, float]] | np.ndarray,
    weights: np.ndarray | None = None,
    robust_loss: str | None = None,
) -> dict[str, object]:
    """Fit a circle to 2D points via least squares.

    Parameters
    ----------
    weights : optional per-point weights for weighted least squares.
    robust_loss : optional scipy loss name ('soft_l1', 'cauchy', etc.).
        When set, scipy handles outlier downweighting automatically.
    """
    pts = np.asarray(points_xy, dtype=np.float64)
    if len(pts) < 3:
        raise ValueError("Need at least 3 points for circle fit.")
    x = pts[:, 0]
    y = pts[:, 1]

    if weights is not None:
        w = np.asarray(weights, dtype=np.float64)
        sqrt_w = np.sqrt(np.maximum(w, 1e-12))
    else:
        w = None
        sqrt_w = None

    def calc_r(xc: float, yc: float) -> np.ndarray:
        return np.sqrt((x - xc) ** 2 + (y - yc) ** 2)

    def residual_func(center: np.ndarray) -> np.ndarray:
        radii = calc_r(center[0], center[1])
        if w is not None:
            mean_r = float(np.sum(w * radii) / np.sum(w))
            return sqrt_w * (radii - mean_r)
        return radii - radii.mean()

    loss = robust_loss if robust_loss else "linear"
    result = optimize.least_squares(residual_func, [np.mean(x), np.mean(y)], loss=loss)
    xc, yc = result.x
    radii = calc_r(xc, yc)
    if w is not None:
        mean_r = float(np.sum(w * radii) / np.sum(w))
    else:
        mean_r = float(radii.mean())
    residuals = radii - mean_r
    return {
        "cx": float(xc),
        "cy": float(yc),
        "r": mean_r,
        "residuals": residuals,
        "res_std": float(np.std(residuals)),
        "res_max": float(np.max(np.abs(residuals))),
    }


def circle_from_contour(contour: np.ndarray) -> dict[str, float]:
    pts = contour[:, 0, :].astype(np.float64)
    circle = fit_circle(pts)
    return {"cx": float(circle["cx"]), "cy": float(circle["cy"]), "r": float(circle["r"])}


# -- seed detection --


def gradient_centroid_seed(img: np.ndarray) -> dict[str, object]:
    gy, gx = np.gradient(img)
    gmag = np.sqrt(gx**2 + gy**2)
    gmag_w = gmag**2
    total = float(gmag_w.sum())
    if total <= 0:
        raise RuntimeError("Gradient centroid seed failed: zero gradient weight.")

    ys, xs = np.mgrid[: img.shape[0], : img.shape[1]]
    cx = float((xs * gmag_w).sum() / total)
    cy = float((ys * gmag_w).sum() / total)
    profile_info = profile_half_value_edges(radial_profile(img, cx, cy))
    return {
        "cx": cx,
        "cy": cy,
        "r_inner": float(profile_info["inner_edge_r"]),
        "r_outer": float(profile_info["outer_edge_r"]),
        "method": "gradient_centroid_seed",
        "warnings": ["fallback_gradient_seed"],
    }


def detect_annulus_seed_from_mask(img: np.ndarray) -> dict[str, object]:
    blur = cv2.GaussianBlur(np.clip(img, 0, 255).astype(np.uint8), (0, 0), 3.0)
    otsu, _ = cv2.threshold(blur, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    bright_threshold = int(max(float(otsu), float(np.percentile(blur, 84))))
    mask = (blur >= bright_threshold).astype(np.uint8) * 255
    kernel = np.ones((3, 3), np.uint8)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)

    count, labels, stats, centers = cv2.connectedComponentsWithStats(mask, 8)
    min_area = max(300, int(img.size * 0.003))
    best_contour = None
    best_score = -1.0
    best_center = None
    for label in range(1, count):
        area = int(stats[label, cv2.CC_STAT_AREA])
        if area < min_area:
            continue
        component = (labels == label).astype(np.uint8)
        contours, _ = cv2.findContours(component, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not contours:
            continue
        perimeter = cv2.arcLength(contours[0], True)
        if perimeter <= 0:
            continue
        circularity = 4.0 * math.pi * area / (perimeter * perimeter)
        cx, cy = centers[label]
        border_margin = min(cx, cy, img.shape[1] - cx, img.shape[0] - cy)
        score = area * max(circularity, 0.05) * max(border_margin, 1.0)
        if score > best_score:
            best_score = score
            best_contour = contours[0]
            best_center = (float(cx), float(cy))

    if best_contour is None or best_center is None:
        raise RuntimeError("Failed to detect annulus from bright mask.")

    coarse_circle = circle_from_contour(best_contour)
    profile_info = profile_half_value_edges(
        radial_profile(img, coarse_circle["cx"], coarse_circle["cy"])
    )
    return {
        "cx": float(coarse_circle["cx"]),
        "cy": float(coarse_circle["cy"]),
        "r_inner": float(profile_info["inner_edge_r"]),
        "r_outer": float(profile_info["outer_edge_r"]),
        "method": "coarse_mask_seed",
        "warnings": [],
        "mask_threshold": bright_threshold,
        "seed_score": float(best_score),
    }


def evaluate_annulus_candidate(
    img: np.ndarray,
    cx: float,
    cy: float,
    r_inner: float,
    r_outer: float,
    *,
    n_angles: int = 120,
) -> dict[str, float]:
    edge_data = extract_radial_edge_candidates(
        img,
        cx,
        cy,
        r_inner,
        r_outer,
        n_angles=n_angles,
        search_half_window=16.0,
        padding=24.0,
        smooth_window=5,
        thresholds=None,
    )
    rows = edge_data["angles"]
    both_rows = [row for row in rows if bool(row["both_valid"])]
    if len(both_rows) < max(18, n_angles // 6):
        return {
            "score": float("inf"),
            "coverage_ratio": 0.0,
            "r_inner": float(r_inner),
            "r_outer": float(r_outer),
            "inner_std": float("inf"),
            "outer_std": float("inf"),
        }

    inner_r = np.asarray([row["inner_r"] for row in both_rows], dtype=np.float64)
    outer_r = np.asarray([row["outer_r"] for row in both_rows], dtype=np.float64)
    coverage_ratio = float(len(both_rows) / max(len(rows), 1))
    inner_std = float(np.std(inner_r))
    outer_std = float(np.std(outer_r))
    ring_width = float(np.median(outer_r - inner_r))
    width_penalty = 0.0 if ring_width > 5 else 50.0
    score = float((1.0 - coverage_ratio) * 220.0 + inner_std + outer_std + width_penalty)
    return {
        "score": score,
        "coverage_ratio": coverage_ratio,
        "r_inner": float(np.median(inner_r)),
        "r_outer": float(np.median(outer_r)),
        "inner_std": inner_std,
        "outer_std": outer_std,
    }


def refine_annulus_reference(img: np.ndarray, seed: dict[str, object]) -> dict[str, object]:
    best = {
        "cx": float(seed["cx"]),
        "cy": float(seed["cy"]),
        "r_inner": float(seed["r_inner"]),
        "r_outer": float(seed["r_outer"]),
    }
    initial = evaluate_annulus_candidate(img, best["cx"], best["cy"], best["r_inner"], best["r_outer"])
    best.update(initial)

    for step in (12.0, 6.0, 3.0):
        candidate_best = dict(best)
        for dx in (-step, 0.0, step):
            for dy in (-step, 0.0, step):
                cand_cx = best["cx"] + dx
                cand_cy = best["cy"] + dy
                evaluation = evaluate_annulus_candidate(
                    img,
                    cand_cx,
                    cand_cy,
                    best["r_inner"],
                    best["r_outer"],
                )
                if evaluation["score"] < candidate_best["score"]:
                    candidate_best = {
                        "cx": float(cand_cx),
                        "cy": float(cand_cy),
                        **evaluation,
                    }
        best = candidate_best

    warnings: list[str] = []
    if best["coverage_ratio"] < 0.80:
        warnings.append("low_refine_coverage")
    if best["inner_std"] > 10.0 or best["outer_std"] > 10.0:
        warnings.append("high_refine_radius_spread")

    status = "ok"
    if best["coverage_ratio"] < 0.40 or not np.isfinite(best["score"]):
        status = "failed"
    elif warnings:
        status = "warning"

    return {
        "cx": float(best["cx"]),
        "cy": float(best["cy"]),
        "r_inner": float(best["r_inner"]),
        "r_outer": float(best["r_outer"]),
        "score": float(best["score"]),
        "coverage_ratio": float(best["coverage_ratio"]),
        "inner_std": float(best["inner_std"]),
        "outer_std": float(best["outer_std"]),
        "status": status,
        "warnings": warnings,
    }


def detect_annulus_reference(img: np.ndarray) -> dict[str, object]:
    coarse_error = None
    try:
        coarse_seed = detect_annulus_seed_from_mask(img)
        refined = refine_annulus_reference(img, coarse_seed)
        refined["method"] = "coarse_mask_seed+local_refine"
        refined["warnings"] = list(coarse_seed.get("warnings", [])) + list(refined["warnings"])
        if refined["status"] != "failed":
            return refined
    except Exception as exc:  # pragma: no cover - fallback path
        coarse_error = str(exc)

    fallback_seed = gradient_centroid_seed(img)
    refined = refine_annulus_reference(img, fallback_seed)
    refined["method"] = "gradient_centroid_fallback+local_refine"
    fallback_warnings = list(fallback_seed.get("warnings", [])) + list(refined["warnings"])
    if coarse_error:
        fallback_warnings.insert(0, "coarse_mask_seed_failed")
    refined["warnings"] = fallback_warnings
    if refined["status"] == "ok":
        refined["status"] = "warning"
    return refined


# -- edge extraction and fit summaries --


def detect_edge_in_window(
    radii: np.ndarray,
    gradient: np.ndarray,
    target_r: float,
    half_window: float,
    sign: float,
) -> tuple[float, float]:
    mask = (radii >= target_r - half_window) & (radii <= target_r + half_window)
    idxs = np.where(mask)[0]
    if len(idxs) < 3:
        return float("nan"), 0.0

    signed_grad = sign * gradient
    window = signed_grad[idxs]
    best_local_idx = int(np.argmax(window))
    peak_mag = float(window[best_local_idx])
    if peak_mag <= 0:
        return float("nan"), 0.0

    global_idx = idxs[best_local_idx]
    sub_idx = subpix_peak(signed_grad, global_idx)
    peak_r = float(np.interp(sub_idx, np.arange(len(radii)), radii))
    return peak_r, peak_mag


def derive_edge_thresholds(angle_rows: list[dict[str, float]]) -> dict[str, float]:
    thresholds: dict[str, float] = {}
    for boundary in ("inner", "outer"):
        mags = np.asarray([max(row[f"{boundary}_mag"], 0.0) for row in angle_rows], dtype=np.float64)
        mags = mags[np.isfinite(mags)]
        if mags.size == 0:
            thresholds[boundary] = float("inf")
            continue
        q10 = float(np.quantile(mags, 0.10))
        median = float(np.median(mags))
        thresholds[boundary] = float(max(q10, median * 0.35, 0.25))
    return thresholds


def extract_radial_edge_candidates(
    img: np.ndarray,
    cx: float,
    cy: float,
    r_inner: float,
    r_outer: float,
    *,
    n_angles: int = 360,
    search_half_window: float = 16.0,
    padding: float = 24.0,
    smooth_window: int = 5,
    thresholds: dict[str, float] | None = None,
) -> dict[str, object]:
    angles = np.linspace(0, 2 * np.pi, n_angles, endpoint=False)
    r_start = max(1.0, r_inner - padding)
    r_end = r_outer + padding
    n_radial = int(max((r_end - r_start) * 2, 180))
    radii = np.linspace(r_start, r_end, n_radial)

    rows: list[dict[str, float]] = []
    for idx, theta in enumerate(angles):
        xs = cx + radii * np.cos(theta)
        ys = cy + radii * np.sin(theta)
        profile = ndimage.map_coordinates(img, [ys, xs], order=1, mode="nearest")
        smooth = ndimage.uniform_filter1d(profile.astype(np.float64), size=smooth_window, mode="nearest")
        gradient = np.gradient(smooth, radii)

        inner_r, inner_mag = detect_edge_in_window(radii, gradient, r_inner, search_half_window, 1.0)
        outer_r, outer_mag = detect_edge_in_window(radii, gradient, r_outer, search_half_window, -1.0)
        thickness = float(outer_r - inner_r) if np.isfinite(inner_r) and np.isfinite(outer_r) else float("nan")
        rows.append(
            {
                "index": float(idx),
                "theta": float(theta),
                "theta_deg": float(np.degrees(theta) % 360.0),
                "inner_r": float(inner_r),
                "outer_r": float(outer_r),
                "inner_mag": float(inner_mag),
                "outer_mag": float(outer_mag),
                "thickness": thickness,
            }
        )

    if thresholds is None:
        thresholds = derive_edge_thresholds(rows)

    for row in rows:
        row["inner_valid"] = float(
            np.isfinite(row["inner_r"]) and row["inner_mag"] >= thresholds["inner"]
        )
        row["outer_valid"] = float(
            np.isfinite(row["outer_r"]) and row["outer_mag"] >= thresholds["outer"]
        )
        row["both_valid"] = float(
            bool(row["inner_valid"]) and bool(row["outer_valid"]) and row["thickness"] > 1.0
        )

    return {
        "cx": float(cx),
        "cy": float(cy),
        "r_inner": float(r_inner),
        "r_outer": float(r_outer),
        "thresholds": thresholds,
        "angles": rows,
    }


def summarize_boundary_fit(
    edge_data: dict[str, object],
    boundary: str,
    cx: float,
    cy: float,
) -> dict[str, object]:
    rows = edge_data["angles"]
    valid_key = f"{boundary}_valid"
    radius_key = f"{boundary}_r"
    valid_rows = [row for row in rows if bool(row[valid_key])]
    total_angles = len(rows)
    valid_angles = len(valid_rows)
    coverage_ratio = float(valid_angles / max(total_angles, 1))
    warnings: list[str] = []

    if valid_angles < 24:
        return {
            "center": [float("nan"), float("nan")],
            "radius": float("nan"),
            "residual_std_px": float("nan"),
            "residual_max_px": float("nan"),
            "valid_angles": valid_angles,
            "total_angles": total_angles,
            "coverage_ratio": coverage_ratio,
            "status": "failed",
            "warnings": ["insufficient_valid_angles"],
            "residuals": np.asarray([], dtype=np.float64),
            "angles_deg": np.asarray([], dtype=np.float64),
            "points_xy": np.asarray([], dtype=np.float64),
        }

    points_xy = np.asarray(
        [
            (
                cx + row[radius_key] * math.cos(row["theta"]),
                cy + row[radius_key] * math.sin(row["theta"]),
            )
            for row in valid_rows
        ],
        dtype=np.float64,
    )
    circle = fit_circle(points_xy)
    if coverage_ratio < 0.90:
        warnings.append("low_coverage")
    if circle["res_std"] > 12.0:
        warnings.append("high_residual_spread")

    status = "warning" if warnings else "ok"
    return {
        "center": [float(circle["cx"]), float(circle["cy"])],
        "radius": float(circle["r"]),
        "residual_std_px": float(circle["res_std"]),
        "residual_max_px": float(circle["res_max"]),
        "valid_angles": valid_angles,
        "total_angles": total_angles,
        "coverage_ratio": coverage_ratio,
        "status": status,
        "warnings": warnings,
        "residuals": np.asarray(circle["residuals"], dtype=np.float64),
        "angles_deg": np.asarray([row["theta_deg"] for row in valid_rows], dtype=np.float64),
        "points_xy": points_xy,
    }


def summarize_circle_fits(edge_data: dict[str, object], cx: float, cy: float) -> dict[str, object]:
    inner = summarize_boundary_fit(edge_data, "inner", cx, cy)
    outer = summarize_boundary_fit(edge_data, "outer", cx, cy)
    warnings: list[str] = []

    if inner["status"] == "failed" or outer["status"] == "failed":
        status = "failed"
        center_offset = float("nan")
    else:
        dx = inner["center"][0] - outer["center"][0]
        dy = inner["center"][1] - outer["center"][1]
        center_offset = float(np.hypot(dx, dy))
        if center_offset > 4.0:
            warnings.append("center_mismatch")
        status = "warning" if warnings or inner["status"] == "warning" or outer["status"] == "warning" else "ok"

    return {
        "status": status,
        "warnings": warnings,
        "center_offset_px": center_offset,
        "inner": inner,
        "outer": outer,
    }


# -- rendering helpers --


def sample_profile_for_angle(
    img: np.ndarray,
    cx: float,
    cy: float,
    theta: float,
    r_inner: float,
    r_outer: float,
    *,
    padding: float = 24.0,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    r_start = max(1.0, r_inner - padding)
    r_end = r_outer + padding
    n_radial = int(max((r_end - r_start) * 2, 180))
    radii = np.linspace(r_start, r_end, n_radial)
    xs = cx + radii * np.cos(theta)
    ys = cy + radii * np.sin(theta)
    profile = ndimage.map_coordinates(img, [ys, xs], order=1, mode="nearest")
    gradient = np.gradient(
        ndimage.uniform_filter1d(profile.astype(np.float64), size=5, mode="nearest"),
        radii,
    )
    return radii, profile, gradient


def choose_profile_indices(edge_data: dict[str, object], count: int = 4) -> list[int]:
    rows = edge_data["angles"]
    both_valid = [idx for idx, row in enumerate(rows) if bool(row["both_valid"])]
    source = both_valid if both_valid else list(range(len(rows)))
    if not source:
        return [0, 90, 180, 270]
    picks = np.linspace(0, len(source) - 1, min(count, len(source)), dtype=int)
    selected = [source[idx] for idx in picks]
    while len(selected) < count:
        selected.append(source[len(selected) % len(source)])
    return selected


def validity_label(row: dict[str, float]) -> str:
    if bool(row["both_valid"]):
        return "both-valid"
    flags: list[str] = []
    if bool(row["inner_valid"]):
        flags.append("inner")
    if bool(row["outer_valid"]):
        flags.append("outer")
    return "+".join(flags) if flags else "invalid"


def render_edge_profiles(
    inp: np.ndarray,
    out: np.ndarray,
    ref: dict[str, object],
    edge_in: dict[str, object],
    edge_out: dict[str, object],
    sample_indices: list[int],
    out_path: Path,
) -> None:
    fig, axes = plt.subplots(2, 4, figsize=(20, 8))
    fig.suptitle("Radial Edge Profiles: Input (blue) vs Output (red)", fontsize=14)

    for plot_idx, sample_idx in enumerate(sample_indices[:4]):
        row_in = edge_in["angles"][sample_idx]
        row_out = edge_out["angles"][sample_idx]
        theta = row_out["theta"]
        radii_i, prof_i, grad_i = sample_profile_for_angle(
            inp,
            float(ref["cx"]),
            float(ref["cy"]),
            float(theta),
            float(ref["r_inner"]),
            float(ref["r_outer"]),
        )
        radii_o, prof_o, grad_o = sample_profile_for_angle(
            out,
            float(ref["cx"]),
            float(ref["cy"]),
            float(theta),
            float(ref["r_inner"]),
            float(ref["r_outer"]),
        )
        angle_label_deg = row_out["theta_deg"]
        validity = f"in={validity_label(row_in)} / out={validity_label(row_out)}"

        axes[0, plot_idx].plot(radii_i, prof_i, "b-", alpha=0.7, label="Input")
        axes[0, plot_idx].plot(radii_o, prof_o, "r-", alpha=0.7, label="Output")
        axes[0, plot_idx].axvline(float(ref["r_inner"]), color="g", linestyle="--", alpha=0.3, label="ref inner")
        axes[0, plot_idx].axvline(float(ref["r_outer"]), color="m", linestyle="--", alpha=0.3, label="ref outer")
        axes[0, plot_idx].set_title(f"Intensity - {angle_label_deg:.0f}° | {validity}")
        axes[0, plot_idx].set_xlabel("Radius (px)")
        axes[0, plot_idx].set_ylabel("Intensity")
        axes[0, plot_idx].legend(fontsize=7)
        axes[0, plot_idx].grid(True, alpha=0.3)

        axes[1, plot_idx].plot(radii_i, grad_i, "b-", alpha=0.7, label="Input")
        axes[1, plot_idx].plot(radii_o, grad_o, "r-", alpha=0.7, label="Output")
        axes[1, plot_idx].axvline(float(ref["r_inner"]), color="g", linestyle="--", alpha=0.3)
        axes[1, plot_idx].axvline(float(ref["r_outer"]), color="m", linestyle="--", alpha=0.3)
        axes[1, plot_idx].set_title(f"Gradient - {angle_label_deg:.0f}° | {validity}")
        axes[1, plot_idx].set_xlabel("Radius (px)")
        axes[1, plot_idx].set_ylabel("dI/dr")
        axes[1, plot_idx].legend(fontsize=7)
        axes[1, plot_idx].grid(True, alpha=0.3)

    plt.tight_layout()
    plt.savefig(out_path, dpi=150)
    plt.close()


def render_circle_fit(
    inp: np.ndarray,
    out: np.ndarray,
    fit_results: dict[str, dict[str, object]],
    out_path: Path,
) -> None:
    fig, axes = plt.subplots(1, 2, figsize=(16, 10))
    circle_t = np.linspace(0, 2 * np.pi, 500)

    for ax, img, title, name in [(axes[0], inp, "Input", "input"), (axes[1], out, "Output", "output")]:
        fit_summary = fit_results[name]
        ax.imshow(img, cmap="gray", vmin=0, vmax=255)
        for boundary, color in [("inner", "lime"), ("outer", "yellow")]:
            info = fit_summary[boundary]
            pts = np.asarray(info["points_xy"], dtype=np.float64)
            if len(pts) > 0:
                ax.scatter(pts[:, 0], pts[:, 1], s=5, alpha=0.25, color=color)
            if info["status"] == "failed":
                continue
            center_x, center_y = info["center"]
            radius = info["radius"]
            linestyle = "--" if info["status"] == "warning" else "-"
            ax.plot(
                center_x + radius * np.cos(circle_t),
                center_y + radius * np.sin(circle_t),
                color=color,
                linestyle=linestyle,
                linewidth=1.5,
                label=(
                    f"{boundary} cov={info['coverage_ratio']:.2f}, "
                    f"σ={info['residual_std_px']:.2f}, {info['status']}"
                ),
            )
        ax.set_title(f"{title} — Circle Fit ({fit_summary['status']})", fontsize=13)
        ax.legend(fontsize=9, loc="upper right")
        ax.axis("off")

    plt.tight_layout()
    plt.savefig(out_path, dpi=150)
    plt.close()


def render_angular_consistency(
    edge_in: dict[str, object],
    edge_out: dict[str, object],
    fit_results: dict[str, dict[str, object]],
    out_path: Path,
) -> None:
    fig, axes = plt.subplots(2, 1, figsize=(14, 8))
    fig.suptitle("Angular Edge Position Consistency (Circle Fit Residuals)", fontsize=14)

    for ax_idx, boundary, title in [(0, "outer", "Outer Boundary"), (1, "inner", "Inner Boundary")]:
        ax = axes[ax_idx]
        for edge_data, fit_summary, label, color in [
            (edge_in, fit_results["input"], "Input", "blue"),
            (edge_out, fit_results["output"], "Output", "red"),
        ]:
            rows = edge_data["angles"]
            angles_deg = np.asarray([row["theta_deg"] for row in rows], dtype=np.float64)
            valid_key = f"{boundary}_valid"
            valid_mask = np.asarray([bool(row[valid_key]) for row in rows], dtype=bool)
            residual_series = np.full(len(rows), np.nan, dtype=np.float64)
            fit_boundary = fit_summary[boundary]
            if fit_boundary["status"] != "failed":
                residual_series[valid_mask] = np.asarray(fit_boundary["residuals"], dtype=np.float64)
                ax.plot(
                    angles_deg,
                    residual_series,
                    ".",
                    markersize=2.5,
                    alpha=0.65,
                    color=color,
                    label=f"{label} cov={fit_boundary['coverage_ratio']:.2f}, {fit_boundary['status']}",
                )
            invalid_angles = angles_deg[~valid_mask]
            if invalid_angles.size:
                ax.plot(
                    invalid_angles,
                    np.zeros_like(invalid_angles),
                    "x",
                    markersize=3,
                    alpha=0.35,
                    color=color,
                )
        ax.axhline(0, color="k", linestyle="--", alpha=0.3)
        ax.set_title(title, fontsize=12)
        ax.set_xlabel("Angle (degrees)")
        ax.set_ylabel("Radial residual (px)")
        ax.legend(fontsize=9)
        ax.grid(True, alpha=0.3)
        ax.set_xlim(0, 360)

    plt.tight_layout()
    plt.savefig(out_path, dpi=150)
    plt.close()


def serialize_circle_summary(fit_summary: dict[str, object]) -> dict[str, object]:
    serial = {
        "status": fit_summary["status"],
        "warnings": list(fit_summary["warnings"]),
        "center_offset_px": (
            round(float(fit_summary["center_offset_px"]), 4)
            if np.isfinite(fit_summary["center_offset_px"])
            else None
        ),
    }
    for boundary in ("inner", "outer"):
        info = fit_summary[boundary]
        serial[boundary] = {
            "center": [round(float(info["center"][0]), 3), round(float(info["center"][1]), 3)]
            if np.all(np.isfinite(info["center"]))
            else [None, None],
            "radius": round(float(info["radius"]), 3) if np.isfinite(info["radius"]) else None,
            "residual_std_px": round(float(info["residual_std_px"]), 4)
            if np.isfinite(info["residual_std_px"])
            else None,
            "residual_max_px": round(float(info["residual_max_px"]), 4)
            if np.isfinite(info["residual_max_px"])
            else None,
            "valid_angles": int(info["valid_angles"]),
            "total_angles": int(info["total_angles"]),
            "coverage_ratio": round(float(info["coverage_ratio"]), 4),
            "status": info["status"],
            "warnings": list(info["warnings"]),
        }
    return serial


# -- analysis pipeline --


def measure_edge_width(
    img: np.ndarray,
    cx: float,
    cy: float,
    r_edge: float,
    *,
    n_angles: int = 72,
    half_span: float = 25.0,
) -> tuple[np.ndarray, np.ndarray]:
    angles = np.linspace(0, 2 * np.pi, n_angles, endpoint=False)
    widths = []
    max_grads = []
    for theta in angles:
        radii = np.linspace(r_edge - half_span, r_edge + half_span, 200)
        xs = cx + radii * np.cos(theta)
        ys = cy + radii * np.sin(theta)
        profile = ndimage.map_coordinates(img, [ys, xs], order=1, mode="nearest")
        pmin, pmax = profile.min(), profile.max()
        if pmax - pmin < 3:
            continue
        pnorm = (profile - pmin) / (pmax - pmin)
        try:
            if pnorm[-1] > pnorm[0]:
                idx_10 = np.where(pnorm >= 0.1)[0][0]
                idx_90 = np.where(pnorm >= 0.9)[0][0]
            else:
                idx_90 = np.where(pnorm <= 0.9)[0][0]
                idx_10 = np.where(pnorm <= 0.1)[0][0]
            width = abs(radii[idx_90] - radii[idx_10])
            if 0 < width < half_span * 2:
                widths.append(width)
        except IndexError:
            pass
        max_grads.append(np.max(np.abs(np.gradient(profile))))
    return np.asarray(widths, dtype=np.float64), np.asarray(max_grads, dtype=np.float64)


def edge_width_by_angle(
    img: np.ndarray,
    cx: float,
    cy: float,
    r_edge: float,
    *,
    n_angles: int = 72,
    half_span: float = 25.0,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    angles_deg = np.linspace(0, 360, n_angles, endpoint=False)
    widths = []
    grads = []
    for theta_deg in angles_deg:
        theta = np.radians(theta_deg)
        radii = np.linspace(r_edge - half_span, r_edge + half_span, 200)
        xs = cx + radii * np.cos(theta)
        ys = cy + radii * np.sin(theta)
        profile = ndimage.map_coordinates(img, [ys, xs], order=1, mode="nearest")
        pmin, pmax = profile.min(), profile.max()
        if pmax - pmin < 3:
            widths.append(np.nan)
            grads.append(np.nan)
            continue
        pnorm = (profile - pmin) / (pmax - pmin)
        try:
            if pnorm[-1] > pnorm[0]:
                idx_10 = np.where(pnorm >= 0.1)[0][0]
                idx_90 = np.where(pnorm >= 0.9)[0][0]
            else:
                idx_90 = np.where(pnorm <= 0.9)[0][0]
                idx_10 = np.where(pnorm <= 0.1)[0][0]
            width = abs(radii[idx_90] - radii[idx_10])
            widths.append(width if 0 < width < half_span * 2 else np.nan)
        except IndexError:
            widths.append(np.nan)
        grads.append(np.max(np.abs(np.gradient(profile))))
    return angles_deg, np.asarray(widths, dtype=np.float64), np.asarray(grads, dtype=np.float64)


def detect_ringing(
    img: np.ndarray,
    cx: float,
    cy: float,
    r_edge: float,
    *,
    n_angles: int = 72,
    span: float = 25.0,
) -> np.ndarray:
    angles = np.linspace(0, 2 * np.pi, n_angles, endpoint=False)
    scores = []
    for theta in angles:
        radii = np.linspace(r_edge + 3, r_edge + span, 80)
        xs = cx + radii * np.cos(theta)
        ys = cy + radii * np.sin(theta)
        profile = ndimage.map_coordinates(img, [ys, xs], order=1, mode="nearest")
        detrend = profile - ndimage.uniform_filter1d(profile, size=15)
        scores.append(np.std(detrend))
    return np.asarray(scores, dtype=np.float64)


def azimuthal_avg_psd(img: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    fft = np.fft.fft2(img - img.mean())
    fft_shift = np.fft.fftshift(fft)
    psd = np.abs(fft_shift) ** 2
    cy_f, cx_f = psd.shape[0] // 2, psd.shape[1] // 2
    max_r = min(cy_f, cx_f)
    yy, xx = np.ogrid[: psd.shape[0], : psd.shape[1]]
    dist = np.sqrt((xx - cx_f) ** 2 + (yy - cy_f) ** 2)

    radii = np.arange(1, max_r)
    avg_psd = np.zeros(len(radii), dtype=np.float64)
    for idx, radius in enumerate(radii):
        mask = (dist >= radius - 0.5) & (dist < radius + 0.5)
        if mask.any():
            avg_psd[idx] = psd[mask].mean()
    freq = radii / max_r * 0.5
    return freq, avg_psd


def _build_360_signal(fit_boundary: dict[str, object]) -> tuple[np.ndarray | None, np.ndarray | None]:
    """Build a uniformly-sampled 360-point residual signal from sparse valid angles."""
    residuals = np.asarray(fit_boundary.get("residuals", []), dtype=np.float64)
    angles_deg = np.asarray(fit_boundary.get("angles_deg", []), dtype=np.float64)
    if len(residuals) < 12 or len(residuals) != len(angles_deg):
        return None, None

    full = np.full(360, np.nan)
    for theta, res in zip(angles_deg, residuals):
        idx = int(round(theta)) % 360
        full[idx] = res

    valid_idx = np.where(~np.isnan(full))[0]
    if len(valid_idx) < 12:
        return None, None

    interp = np.interp(np.arange(360), valid_idx, full[valid_idx])
    interp -= interp.mean()  # remove DC
    return interp, valid_idx


def _energy_split(fft_coefs: np.ndarray, k_boundary: int = 3) -> dict[str, float]:
    """Split DFT energy into low-order (k=1..k_boundary) and high-order (k>k_boundary)."""
    power = np.abs(fft_coefs) ** 2
    total = float(power[1:].sum())  # exclude DC
    if total < 1e-12:
        return {"lo_pct": 0.0, "hi_pct": 0.0, "total_power": 0.0}
    lo = float(power[1:k_boundary + 1].sum())
    hi = float(power[k_boundary + 1:].sum())
    return {
        "lo_pct": round(lo / total * 100, 2),
        "hi_pct": round(hi / total * 100, 2),
        "total_power": round(total, 4),
    }


def _bootstrap_energy_ci(
    interp: np.ndarray,
    valid_idx: np.ndarray,
    k_boundary: int = 3,
    n_boot: int = 2000,
    ci_level: float = 0.95,
) -> dict[str, tuple[float, float]]:
    """Bootstrap CI for low/high energy percentages by resampling valid angles."""
    rng = np.random.default_rng(42)
    n_valid = len(valid_idx)
    lo_pcts: list[float] = []
    hi_pcts: list[float] = []

    for _ in range(n_boot):
        # Resample valid indices with replacement
        boot_idx = rng.choice(valid_idx, size=n_valid, replace=True)
        boot_idx = np.unique(boot_idx)
        boot_vals = interp[boot_idx]  # interp already has values at all 360 points
        # Re-interpolate from resampled subset
        boot_full = np.interp(np.arange(360), boot_idx, boot_vals)
        boot_full -= boot_full.mean()
        coefs = np.fft.rfft(boot_full)
        split = _energy_split(coefs, k_boundary)
        lo_pcts.append(split["lo_pct"])
        hi_pcts.append(split["hi_pct"])

    alpha = (1 - ci_level) / 2
    lo_arr = np.array(lo_pcts)
    hi_arr = np.array(hi_pcts)
    return {
        "lo_ci": (round(float(np.percentile(lo_arr, alpha * 100)), 2),
                  round(float(np.percentile(lo_arr, (1 - alpha) * 100)), 2)),
        "hi_ci": (round(float(np.percentile(hi_arr, alpha * 100)), 2),
                  round(float(np.percentile(hi_arr, (1 - alpha) * 100)), 2)),
    }


def compute_residual_harmonics(
    fit_boundary: dict[str, object],
    max_k: int = 18,
    n_boot: int = 2000,
) -> dict[str, object]:
    """DFT harmonic decomposition with energy split and bootstrap CI."""
    empty = {
        "harmonics": [], "amplitudes": [], "phases_deg": [], "dominant_k": None,
        "reconstructed_signal": [], "low_order_reconstruction": [],
        "energy_split": {"lo_pct": 0.0, "hi_pct": 0.0, "total_power": 0.0},
        "bootstrap_ci": {"lo_ci": (0.0, 0.0), "hi_ci": (0.0, 0.0)},
    }
    interp, valid_idx = _build_360_signal(fit_boundary)
    if interp is None:
        return empty

    fft_coefs = np.fft.rfft(interp)
    ks = np.arange(len(fft_coefs))
    amps = np.abs(fft_coefs) / 180.0  # normalized amplitude in px
    phases = np.degrees(np.angle(fft_coefs))

    upper = min(max_k + 1, len(amps))
    dominant_k = int(np.argmax(amps[1:upper]) + 1)

    # Low-order reconstruction (k=1..5)
    lo_coefs = np.where(ks <= 5, fft_coefs, 0.0)
    lo_recon = np.real(np.fft.irfft(lo_coefs, n=360))

    # Energy split (k≤3 low-order geometric vs k>3 high-order/local)
    esplit = _energy_split(fft_coefs, k_boundary=3)

    # Bootstrap CI on energy percentages
    bci = _bootstrap_energy_ci(interp, valid_idx, k_boundary=3, n_boot=n_boot)

    return {
        "harmonics": ks[:upper].tolist(),
        "amplitudes": [round(float(a), 4) for a in amps[:upper]],
        "phases_deg": [round(float(p), 2) for p in phases[:upper]],
        "dominant_k": dominant_k,
        "reconstructed_signal": [round(float(v), 4) for v in interp],
        "low_order_reconstruction": [round(float(v), 4) for v in lo_recon],
        "energy_split": esplit,
        "bootstrap_ci": bci,
    }


def render_residual_harmonics(
    fit_results: dict[str, dict[str, object]],
    out_path: Path,
) -> None:
    """Plot 07: 3-column layout — signal+recon | harmonic spectrum | energy split with CI."""
    max_k = 18
    boundary_cfg = [("outer", "Outer Boundary"), ("inner", "Inner Boundary")]
    fig, axes = plt.subplots(2, 3, figsize=(22, 12))
    fig.suptitle(
        "Angular Residual Harmonic Decomposition — Error Structure Analysis\n"
        "(k=1 [360°]: center-shift  |  k=2 [180°]: elliptical  |  k=3 [120°]: trefoil  |  k≥4: local defects)",
        fontsize=13,
    )

    style = {
        "input":  {"color": "steelblue",  "label": "Input",  "bar_offset": -0.33},
        "output": {"color": "crimson",    "label": "Output", "bar_offset":  0.33},
    }

    for row, (boundary, btitle) in enumerate(boundary_cfg):
        ax_sig = axes[row, 0]
        ax_spe = axes[row, 1]
        ax_eng = axes[row, 2]
        angles_full = np.arange(360)
        amp_ymax = 0.0

        # Collect energy data for the bar chart
        energy_data: dict[str, dict] = {}

        for name, st in style.items():
            fit_b = fit_results[name][boundary]
            hdata = compute_residual_harmonics(fit_b, max_k=max_k)
            if not hdata["harmonics"]:
                continue

            ks   = np.array(hdata["harmonics"])
            amps = np.array(hdata["amplitudes"])
            sig  = np.array(hdata["reconstructed_signal"])
            lo   = np.array(hdata["low_order_reconstruction"])
            dk   = hdata["dominant_k"]
            amp_ymax = max(amp_ymax, float(amps[1:].max()) if len(amps) > 1 else 0.0)

            energy_data[name] = {
                "lo_pct": hdata["energy_split"]["lo_pct"],
                "hi_pct": hdata["energy_split"]["hi_pct"],
                "lo_ci": hdata["bootstrap_ci"]["lo_ci"],
                "hi_ci": hdata["bootstrap_ci"]["hi_ci"],
            }

            # Col 0: Signal + low-order overlay
            ax_sig.plot(angles_full, sig, color=st["color"], alpha=0.45, linewidth=0.9,
                        label=f"{st['label']} residual")
            ax_sig.plot(angles_full, lo, color=st["color"], alpha=0.92, linewidth=2.0,
                        linestyle="--",
                        label=f"{st['label']} k≤5 recon  (dom. k={dk})")

            # Col 1: Harmonic spectrum (bar, k=1 onwards)
            ax_spe.bar(ks[1:] + st["bar_offset"], amps[1:], width=0.60,
                       color=st["color"], alpha=0.78, label=st["label"])

        # --- Col 0 formatting ---
        ax_sig.axhline(0, color="k", linestyle="--", alpha=0.25)
        ax_sig.set_title(f"{btitle} — Residual Signal & k≤5 Reconstruction", fontsize=11)
        ax_sig.set_xlabel("Angle (degrees)")
        ax_sig.set_ylabel("Radial residual (px)")
        ax_sig.set_xlim(0, 359)
        ax_sig.legend(fontsize=8)
        ax_sig.grid(True, alpha=0.25)

        # --- Col 1 formatting ---
        for k_mark, k_label in [(1, "center\nshift\n[360°]"), (2, "elliptical\n[180°]"), (3, "trefoil\n[120°]")]:
            ax_spe.axvline(k_mark, color="dimgray", linestyle=":", alpha=0.5)
            ax_spe.text(k_mark + 0.08, amp_ymax * 0.96, k_label,
                        fontsize=7, color="dimgray", va="top")
        ax_spe.axvline(3.5, color="orange", linestyle="--", alpha=0.6, linewidth=1.5)
        ax_spe.text(3.7, amp_ymax * 0.80, "← geometric | local →",
                    fontsize=7, color="darkorange", va="top")
        ax_spe.set_title(f"{btitle} — Harmonic Amplitude Spectrum", fontsize=11)
        ax_spe.set_xlabel("Harmonic number  k")
        ax_spe.set_ylabel("Amplitude (px)")
        ax_spe.set_xlim(0.5, max_k + 0.5)
        ax_spe.set_xticks(range(1, max_k + 1))
        ax_spe.legend(fontsize=9)
        ax_spe.grid(True, alpha=0.25)

        # --- Col 2: Energy decomposition bar with bootstrap CI ---
        if energy_data:
            x_pos = np.array([0, 1])
            width_bar = 0.35
            for name, st in style.items():
                if name not in energy_data:
                    continue
                ed = energy_data[name]
                offset = -width_bar / 2 if name == "input" else width_bar / 2
                lo_val = ed["lo_pct"]
                hi_val = ed["hi_pct"]
                lo_ci = ed["lo_ci"]
                hi_ci = ed["hi_ci"]
                lo_err = [[lo_val - lo_ci[0]], [lo_ci[1] - lo_val]]
                hi_err = [[hi_val - hi_ci[0]], [hi_ci[1] - hi_val]]

                ax_eng.bar(x_pos[0] + offset, lo_val, width_bar,
                           color=st["color"], alpha=0.78,
                           label=f"{st['label']}",
                           yerr=[[lo_err[0][0]], [lo_err[1][0]]],
                           capsize=4, error_kw={"linewidth": 1.2})
                ax_eng.bar(x_pos[1] + offset, hi_val, width_bar,
                           color=st["color"], alpha=0.78,
                           yerr=[[hi_err[0][0]], [hi_err[1][0]]],
                           capsize=4, error_kw={"linewidth": 1.2})

                # Value labels on bars
                ax_eng.text(x_pos[0] + offset, lo_val + lo_err[1][0] + 1.5,
                            f"{lo_val:.1f}%", ha="center", va="bottom",
                            fontsize=8, fontweight="bold", color=st["color"])
                ax_eng.text(x_pos[1] + offset, hi_val + hi_err[1][0] + 1.5,
                            f"{hi_val:.1f}%", ha="center", va="bottom",
                            fontsize=8, fontweight="bold", color=st["color"])

            ax_eng.set_xticks(x_pos)
            ax_eng.set_xticklabels(["Low-order\n(k≤3: geometric)", "High-order\n(k>3: local defects)"],
                                   fontsize=9)
            ax_eng.set_ylabel("% of total DFT energy (excl. DC)")
            ax_eng.set_title(f"{btitle} — Error Energy Decomposition\n(bars = point estimate, whiskers = 95% bootstrap CI)",
                             fontsize=11)
            ax_eng.legend(fontsize=9)
            ax_eng.grid(True, axis="y", alpha=0.25)
            ax_eng.set_ylim(0, 105)

    plt.tight_layout()
    plt.savefig(out_path, dpi=150)
    plt.close()


def compute_hotspot_clusters(
    fit_boundary: dict,
    threshold_pct: float = 75.0,
    gap_deg: float = 5.0,
) -> dict:
    """Identify contiguous arcs of high-|residual| boundary angles.

    Returns n_clusters, total_arc_deg, max_cluster_deg, threshold_px, n_high_res.
    Threshold = threshold_pct-th percentile of |residuals|.
    Two high-residual angles separated by > gap_deg degrees are in different clusters.
    """
    residuals = np.asarray(fit_boundary.get("residuals", []), dtype=np.float64)
    angles_deg = np.asarray(fit_boundary.get("angles_deg", []), dtype=np.float64)
    empty: dict = {"n_clusters": 0, "total_arc_deg": 0.0, "max_cluster_deg": 0.0,
                   "threshold_px": 0.0, "n_high_res": 0}
    if len(residuals) < 3 or len(residuals) != len(angles_deg):
        return empty

    threshold = float(np.percentile(np.abs(residuals), threshold_pct))
    high_mask = np.abs(residuals) >= threshold
    high_angles = np.sort(angles_deg[high_mask])

    if len(high_angles) == 0:
        return {**empty, "threshold_px": round(threshold, 3)}

    # Split into clusters wherever the gap between consecutive angles exceeds gap_deg
    diffs = np.diff(high_angles)
    split_pos = np.where(diffs > gap_deg)[0]
    starts = np.concatenate([[high_angles[0]], high_angles[split_pos + 1]])
    ends = np.concatenate([high_angles[split_pos], [high_angles[-1]]])
    spans = list(ends - starts)

    # Wrap-around: last cluster and first cluster may be adjacent across 0°/360°
    if len(starts) > 1:
        wrap_gap = 360.0 - ends[-1] + starts[0]
        if wrap_gap <= gap_deg:
            spans = [spans[0] + spans[-1] + wrap_gap] + spans[1:-1]

    spans_arr = np.array(spans, dtype=np.float64)
    return {
        "threshold_px": round(threshold, 3),
        "n_high_res": int(high_mask.sum()),
        "total_arc_deg": round(float(spans_arr.sum()), 1),
        "n_clusters": int(len(spans_arr)),
        "max_cluster_deg": round(float(spans_arr.max()), 1),
    }


def render_residual_hotspot(
    inp: np.ndarray,
    out: np.ndarray,
    edge_in: dict[str, object],
    edge_out: dict[str, object],
    fit_results: dict[str, dict[str, object]],
    ref: dict[str, object],
    out_path: Path,
) -> None:
    """Plot 08: boundary residual hotspot map overlaid on annulus image crop."""
    cx   = float(ref["cx"])
    cy   = float(ref["cy"])
    r_in  = float(ref["r_inner"])
    r_out = float(ref["r_outer"])
    pad  = 60
    x0 = max(0, int(cx - r_out - pad))
    x1 = min(inp.shape[1], int(cx + r_out + pad))
    y0 = max(0, int(cy - r_out - pad))
    y1 = min(inp.shape[0], int(cy + r_out + pad))

    fig, axes = plt.subplots(1, 2, figsize=(20, 11))
    fig.suptitle(
        "Boundary Residual Hotspot Map\n"
        "(color = |residual| from circle fit;  ○ outer  □ inner  × invalid)",
        fontsize=13,
    )

    # Unified colormap scale across both images
    all_abs_res = []
    for name in ("input", "output"):
        for boundary in ("outer", "inner"):
            fb = fit_results[name][boundary]
            if len(fb.get("residuals", [])) > 0:
                all_abs_res.extend(np.abs(np.asarray(fb["residuals"])).tolist())
    vmax_r = float(np.percentile(all_abs_res, 95)) if all_abs_res else 15.0
    vmax_r = max(vmax_r, 3.0)

    scatter_ref = None
    for ax, img, name, edge_data, title in [
        (axes[0], inp, "input",  edge_in,  "Input"),
        (axes[1], out, "output", edge_out, "Output"),
    ]:
        crop = img[y0:y1, x0:x1]
        ax.imshow(crop, cmap="gray", vmin=0, vmax=255,
                  extent=[x0, x1, y1, y0], origin="upper")

        boundary_cfg2 = [
            ("outer", "o", "x",  10, r_out),
            ("inner", "s", "+",   6, r_in),
        ]
        for boundary, mrk_v, mrk_i, sz_v, r_ref in boundary_cfg2:
            fb = fit_results[name][boundary]
            pts = np.asarray(fb.get("points_xy", []), dtype=np.float64)
            res = np.asarray(fb.get("residuals",  []), dtype=np.float64)

            if len(pts) > 0:
                sc = ax.scatter(
                    pts[:, 0], pts[:, 1],
                    c=np.abs(res), cmap="RdYlGn_r",
                    vmin=0, vmax=vmax_r,
                    s=sz_v, alpha=0.80, marker=mrk_v,
                    label=f"{boundary} valid ({len(pts)})",
                    linewidths=0,
                )
                scatter_ref = sc

            # Invalid angles at reference radius
            rows     = edge_data["angles"]
            vkey     = f"{boundary}_valid"
            inv_rows = [r for r in rows if not bool(r[vkey])]
            if inv_rows:
                ix = [cx + r_ref * math.cos(r["theta"]) for r in inv_rows]
                iy = [cy + r_ref * math.sin(r["theta"]) for r in inv_rows]
                ax.scatter(ix, iy, s=20, alpha=0.30, c="silver",
                           marker=mrk_i,
                           label=f"{boundary} invalid ({len(inv_rows)})")

        # Cluster quantification annotation
        cl_out = compute_hotspot_clusters(fit_results[name]["outer"])
        cl_in = compute_hotspot_clusters(fit_results[name]["inner"])
        ann = (
            f"Outer  n={cl_out['n_clusters']}  arc={cl_out['total_arc_deg']}°  max={cl_out['max_cluster_deg']}°\n"
            f"Inner  n={cl_in['n_clusters']}  arc={cl_in['total_arc_deg']}°  max={cl_in['max_cluster_deg']}°"
        )
        ax.text(
            0.02, 0.98, ann,
            transform=ax.transAxes,
            va="top", ha="left", fontsize=7.5,
            bbox=dict(boxstyle="round,pad=0.3", facecolor="white", alpha=0.80),
        )

        ax.set_xlim(x0, x1)
        ax.set_ylim(y1, y0)
        ax.set_title(f"{title} — Residual Hotspot Map", fontsize=12)
        ax.set_xlabel("x (px)")
        ax.set_ylabel("y (px)")
        ax.legend(
            fontsize=8,
            loc="upper center",
            bbox_to_anchor=(0.5, -0.06),
            ncol=2,
            markerscale=2.0,
            framealpha=0.92,
            borderpad=0.6,
        )

    axes[1].set_ylabel("")
    axes[1].tick_params(labelleft=False)
    fig.subplots_adjust(left=0.06, right=0.88, bottom=0.12, top=0.92, wspace=0.06)
    if scatter_ref is not None:
        cbar_ax = fig.add_axes([0.905, 0.15, 0.018, 0.70])
        cbar = fig.colorbar(scatter_ref, cax=cbar_ax)
        cbar.set_label("|Residual| (px)", fontsize=11)

    plt.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close()


def _build_harmonic_summary(fit_results: dict) -> dict:
    """Build residual_harmonics section for the summary JSON."""
    result: dict = {}
    for name in ("input", "output"):
        for boundary in ("outer", "inner"):
            key = f"{name}_{boundary}"
            hdata = compute_residual_harmonics(fit_results[name][boundary])
            result[f"{key}_dominant_k"] = hdata.get("dominant_k")
            result[f"{key}_energy"] = {
                "lo_pct": hdata["energy_split"]["lo_pct"],
                "hi_pct": hdata["energy_split"]["hi_pct"],
                "lo_ci_95": list(hdata["bootstrap_ci"]["lo_ci"]),
                "hi_ci_95": list(hdata["bootstrap_ci"]["hi_ci"]),
            }
    return result


def _build_hotspot_cluster_summary(fit_results: dict) -> dict:
    """Build hotspot_clusters section for the summary JSON."""
    result: dict = {"threshold_pct": 75}
    for name in ("input", "output"):
        for boundary in ("outer", "inner"):
            result[f"{name}_{boundary}"] = compute_hotspot_clusters(
                fit_results[name][boundary]
            )
    return result


def main(
    *,
    input_path: str | Path = INPUT_PATH,
    recon_path: str | Path = RECON_PATH,
    out_dir: str | Path = OUT_DIR,
    verbose: bool = True,
) -> dict[str, object]:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    log = print if verbose else (lambda *args, **kwargs: None)

    inp = load_image(input_path)
    out = load_image(recon_path)
    log(f"Input:  {inp.shape}, range [{inp.min():.0f}, {inp.max():.0f}]")
    log(f"Output: {out.shape}, range [{out.min():.0f}, {out.max():.0f}]")

    ref = detect_annulus_reference(out)
    log(
        "\nAnnulus detected: "
        f"center=({ref['cx']:.1f}, {ref['cy']:.1f}), "
        f"r_inner={ref['r_inner']:.1f}, r_outer={ref['r_outer']:.1f}, "
        f"status={ref['status']}, method={ref['method']}"
    )
    if ref["warnings"]:
        log(f"  warnings: {', '.join(ref['warnings'])}")

    edge_in = extract_radial_edge_candidates(inp, ref["cx"], ref["cy"], ref["r_inner"], ref["r_outer"])
    edge_out = extract_radial_edge_candidates(out, ref["cx"], ref["cy"], ref["r_inner"], ref["r_outer"])
    fit_results = {
        "input": summarize_circle_fits(edge_in, ref["cx"], ref["cy"]),
        "output": summarize_circle_fits(edge_out, ref["cx"], ref["cy"]),
    }

    log("\n" + "=" * 60)
    log("ANALYSIS 1: Edge Sharpness Quantification")
    log("=" * 60)
    inner_in_valid = sum(bool(row["inner_valid"]) for row in edge_in["angles"])
    outer_in_valid = sum(bool(row["outer_valid"]) for row in edge_in["angles"])
    inner_out_valid = sum(bool(row["inner_valid"]) for row in edge_out["angles"])
    outer_out_valid = sum(bool(row["outer_valid"]) for row in edge_out["angles"])
    log(f"  Valid edges - Input:  {inner_in_valid} inner, {outer_in_valid} outer")
    log(f"  Valid edges - Output: {inner_out_valid} inner, {outer_out_valid} outer")

    w_in_outer, g_in_outer = measure_edge_width(inp, ref["cx"], ref["cy"], ref["r_outer"])
    w_out_outer, g_out_outer = measure_edge_width(out, ref["cx"], ref["cy"], ref["r_outer"])
    w_in_inner, g_in_inner = measure_edge_width(inp, ref["cx"], ref["cy"], ref["r_inner"])
    w_out_inner, g_out_inner = measure_edge_width(out, ref["cx"], ref["cy"], ref["r_inner"])

    log("\n  Outer edge width (10-90%):")
    log(f"    Input:  {safe_mean(w_in_outer):.2f} ± {safe_std(w_in_outer):.2f} px")
    log(f"    Output: {safe_mean(w_out_outer):.2f} ± {safe_std(w_out_outer):.2f} px")
    if safe_mean(w_out_outer) > 0:
        log(f"    Sharpening: {safe_mean(w_in_outer) / safe_mean(w_out_outer):.2f}x narrower")
    log("  Inner edge width (10-90%):")
    log(f"    Input:  {safe_mean(w_in_inner):.2f} ± {safe_std(w_in_inner):.2f} px")
    log(f"    Output: {safe_mean(w_out_inner):.2f} ± {safe_std(w_out_inner):.2f} px")
    if safe_mean(w_out_inner) > 0:
        log(f"    Sharpening: {safe_mean(w_in_inner) / safe_mean(w_out_inner):.2f}x narrower")
    log("  Max gradient at outer edge:")
    log(f"    Input:  {safe_mean(g_in_outer):.2f} ± {safe_std(g_in_outer):.2f}")
    log(f"    Output: {safe_mean(g_out_outer):.2f} ± {safe_std(g_out_outer):.2f}")
    if safe_mean(g_in_outer) > 0:
        log(f"    Gradient boost: {safe_mean(g_out_outer) / safe_mean(g_in_outer):.2f}x steeper")

    sample_indices = choose_profile_indices(edge_out)
    render_edge_profiles(inp, out, ref, edge_in, edge_out, sample_indices, out_dir / "01_edge_profiles.png")
    log("  -> Saved 01_edge_profiles.png")

    log("\n" + "=" * 60)
    log("ANALYSIS 2: Boundary Geometry & Circle Fitting")
    log("=" * 60)
    for name, label in [("input", "Input"), ("output", "Output")]:
        fit_summary = fit_results[name]
        for boundary, title in [("inner", "Inner"), ("outer", "Outer")]:
            info = fit_summary[boundary]
            if info["status"] == "failed":
                log(f"  [{label} {title}] fit failed ({', '.join(info['warnings'])})")
                continue
            log(
                f"  [{label} {title}] center=({info['center'][0]:.2f}, {info['center'][1]:.2f}), "
                f"r={info['radius']:.2f}, residual std={info['residual_std_px']:.4f} px, "
                f"coverage={info['coverage_ratio']:.2f}, status={info['status']}"
            )
        if np.isfinite(fit_summary["center_offset_px"]):
            log(f"  [{label}] inner-outer center offset: {fit_summary['center_offset_px']:.3f} px ({fit_summary['status']})")

    for boundary in ("inner", "outer"):
        in_info = fit_results["input"][boundary]
        out_info = fit_results["output"][boundary]
        if in_info["status"] == "ok" and out_info["status"] == "ok":
            pct = (1.0 - out_info["residual_std_px"] / in_info["residual_std_px"]) * 100.0
            log(
                f"  {boundary.capitalize()} circle-fit residual change: "
                f"{in_info['residual_std_px']:.4f} → {out_info['residual_std_px']:.4f} px ({pct:+.1f}%)"
            )
        else:
            log(
                f"  {boundary.capitalize()} circle-fit comparison skipped due confidence: "
                f"input={in_info['status']}, output={out_info['status']}"
            )

    render_circle_fit(inp, out, fit_results, out_dir / "02_circle_fit.png")
    log("  -> Saved 02_circle_fit.png")

    log("\n" + "=" * 60)
    log("ANALYSIS 3: Angular Edge Position Consistency")
    log("=" * 60)
    render_angular_consistency(edge_in, edge_out, fit_results, out_dir / "03_angular_consistency.png")
    log("  -> Saved 03_angular_consistency.png")

    log("\n" + "=" * 60)
    log("ANALYSIS 7: Residual Harmonic Decomposition")
    log("=" * 60)
    render_residual_harmonics(fit_results, out_dir / "07_residual_harmonics.png")
    log("  -> Saved 07_residual_harmonics.png")

    log("\n" + "=" * 60)
    log("ANALYSIS 8: Residual Hotspot Map")
    log("=" * 60)
    render_residual_hotspot(inp, out, edge_in, edge_out, fit_results, ref, out_dir / "08_residual_hotspot.png")
    log("  -> Saved 08_residual_hotspot.png")

    log("\n" + "=" * 60)
    log("ANALYSIS 4: Spatial Frequency Spectrum")
    log("=" * 60)
    freq_in, psd_in = azimuthal_avg_psd(inp)
    freq_out, psd_out = azimuthal_avg_psd(out)

    fig, axes = plt.subplots(1, 2, figsize=(16, 6))
    axes[0].semilogy(freq_in, psd_in, "b-", alpha=0.7, linewidth=0.8, label="Input")
    axes[0].semilogy(freq_out, psd_out, "r-", alpha=0.7, linewidth=0.8, label="Output")
    axes[0].set_xlabel("Spatial Frequency (cycles/pixel)")
    axes[0].set_ylabel("Power Spectral Density")
    axes[0].set_title("Azimuthally-Averaged Power Spectrum")
    axes[0].legend()
    axes[0].grid(True, alpha=0.3)

    ratio = psd_out / (psd_in + 1e-10)
    ratio_smooth = np.convolve(ratio, np.ones(7) / 7, mode="same")
    axes[1].plot(freq_in, ratio_smooth, "g-", linewidth=1.2)
    axes[1].axhline(1.0, color="k", linestyle="--", alpha=0.3, label="No change")
    axes[1].set_xlabel("Spatial Frequency (cycles/pixel)")
    axes[1].set_ylabel("Output / Input PSD Ratio")
    axes[1].set_title("Frequency-Domain Amplification (PSF Deconvolution Effect)")
    axes[1].set_ylim(0, min(10, np.percentile(ratio_smooth[freq_in < 0.45], 98) * 1.3))
    axes[1].legend()
    axes[1].grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(out_dir / "04_frequency_spectrum.png", dpi=150)
    plt.close()
    log("  -> Saved 04_frequency_spectrum.png")

    hf_mask = freq_in > 0.2
    hf_energy_in = np.sum(psd_in[hf_mask])
    hf_energy_out = np.sum(psd_out[hf_mask])
    total_in = np.sum(psd_in)
    total_out = np.sum(psd_out)
    mf_mask = (freq_in > 0.05) & (freq_in <= 0.2)
    mf_in = np.sum(psd_in[mf_mask])
    mf_out = np.sum(psd_out[mf_mask])
    log(f"  HF energy (>0.2 cyc/px): input={hf_energy_in / total_in * 100:.2f}%, output={hf_energy_out / total_out * 100:.2f}%")
    log(f"  HF energy boost: {hf_energy_out / hf_energy_in:.2f}x")
    log(f"  MF energy (0.05-0.2 cyc/px): input={mf_in / total_in * 100:.2f}%, output={mf_out / total_out * 100:.2f}%")

    log("\n" + "=" * 60)
    log("ANALYSIS 5: Background Uniformity & Artifacts")
    log("=" * 60)
    ys_grid, xs_grid = np.mgrid[: inp.shape[0], : inp.shape[1]]
    dist_from_center = np.sqrt((xs_grid - ref["cx"]) ** 2 + (ys_grid - ref["cy"]) ** 2)
    bg_mask = (
        (dist_from_center > ref["r_outer"] + 30)
        & (xs_grid > 20)
        & (xs_grid < inp.shape[1] - 20)
        & (ys_grid > 20)
        & (ys_grid < inp.shape[0] - 20)
    )
    interior_mask = dist_from_center < ref["r_inner"] - 15
    ring_mask = (dist_from_center >= ref["r_inner"] - 5) & (dist_from_center <= ref["r_outer"] + 5)

    bg_in_vals = inp[bg_mask]
    bg_out_vals = out[bg_mask]
    int_in_vals = inp[interior_mask]
    int_out_vals = out[interior_mask]
    ring_in_vals = inp[ring_mask]
    ring_out_vals = out[ring_mask]
    bg_std_change = (1 - np.std(bg_out_vals) / np.std(bg_in_vals)) * 100
    contrast_in = np.mean(ring_in_vals) - np.mean(bg_in_vals)
    contrast_out = np.mean(ring_out_vals) - np.mean(bg_out_vals)
    log(f"  Background: input μ={np.mean(bg_in_vals):.2f} σ={np.std(bg_in_vals):.2f}, output μ={np.mean(bg_out_vals):.2f} σ={np.std(bg_out_vals):.2f}")
    log(f"  Interior:   input μ={np.mean(int_in_vals):.2f} σ={np.std(int_in_vals):.2f}, output μ={np.mean(int_out_vals):.2f} σ={np.std(int_out_vals):.2f}")
    log(f"  Ring:       input μ={np.mean(ring_in_vals):.2f} σ={np.std(ring_in_vals):.2f}, output μ={np.mean(ring_out_vals):.2f} σ={np.std(ring_out_vals):.2f}")
    log(f"  Background uniformity change: {bg_std_change:+.1f}% σ")
    log(f"  Ring-background contrast: input={contrast_in:.2f}, output={contrast_out:.2f}")

    ring_score_in = detect_ringing(inp, ref["cx"], ref["cy"], ref["r_outer"])
    ring_score_out = detect_ringing(out, ref["cx"], ref["cy"], ref["r_outer"])
    ringing_ratio = float(np.mean(ring_score_out) / np.mean(ring_score_in))
    log(f"  Ringing score (outer, outward): input={np.mean(ring_score_in):.3f}, output={np.mean(ring_score_out):.3f}, ratio={ringing_ratio:.2f}x")
    log("  [OK] No significant ringing artifacts" if ringing_ratio <= 1.5 else "  [!] Possible ringing artifacts detected")

    diff = out - inp
    fig, axes = plt.subplots(2, 3, figsize=(18, 12))
    axes[0, 0].imshow(inp, cmap="gray", vmin=0, vmax=255)
    axes[0, 0].set_title("Input (Original)", fontsize=12)
    axes[0, 0].axis("off")
    axes[0, 1].imshow(out, cmap="gray", vmin=0, vmax=255)
    axes[0, 1].set_title("Output (R26 Reconstructed)", fontsize=12)
    axes[0, 1].axis("off")
    vmax_diff = np.percentile(np.abs(diff), 99)
    diff_im = axes[0, 2].imshow(diff, cmap="RdBu_r", vmin=-vmax_diff, vmax=vmax_diff)
    axes[0, 2].set_title("Difference (Output − Input)", fontsize=12)
    axes[0, 2].axis("off")
    plt.colorbar(diff_im, ax=axes[0, 2], fraction=0.046, pad=0.04)
    edges_in_vis = cv2.Canny(np.clip(inp, 0, 255).astype(np.uint8), 30, 80)
    edges_out_vis = cv2.Canny(np.clip(out, 0, 255).astype(np.uint8), 30, 80)
    dilate_kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
    edges_in_vis = cv2.dilate(edges_in_vis, dilate_kernel, iterations=1)
    edges_out_vis = cv2.dilate(edges_out_vis, dilate_kernel, iterations=1)
    axes[1, 0].imshow(edges_in_vis, cmap="gray")
    axes[1, 0].set_title(f"Input Edges (Canny, n={np.sum(edges_in_vis > 0)})", fontsize=12)
    axes[1, 0].axis("off")
    axes[1, 1].imshow(edges_out_vis, cmap="gray")
    axes[1, 1].set_title(f"Output Edges (Canny, n={np.sum(edges_out_vis > 0)})", fontsize=12)
    axes[1, 1].axis("off")
    axes[1, 2].hist(bg_in_vals, bins=60, alpha=0.5, color="blue", density=True, label=f"Input (σ={np.std(bg_in_vals):.2f})")
    axes[1, 2].hist(bg_out_vals, bins=60, alpha=0.5, color="red", density=True, label=f"Output (σ={np.std(bg_out_vals):.2f})")
    axes[1, 2].set_title("Background Intensity Distribution", fontsize=12)
    axes[1, 2].set_xlabel("Intensity")
    axes[1, 2].legend()
    axes[1, 2].grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(out_dir / "05_overview_and_artifacts.png", dpi=150)
    plt.close()
    log("  -> Saved 05_overview_and_artifacts.png")

    log("\n" + "=" * 60)
    log("ANALYSIS 6: Edge Width Angular Distribution")
    log("=" * 60)
    ang_in, ew_in, _ = edge_width_by_angle(inp, ref["cx"], ref["cy"], ref["r_outer"])
    ang_out, ew_out, _ = edge_width_by_angle(out, ref["cx"], ref["cy"], ref["r_outer"])
    ang_in2, ew_in2, _ = edge_width_by_angle(inp, ref["cx"], ref["cy"], ref["r_inner"])
    ang_out2, ew_out2, _ = edge_width_by_angle(out, ref["cx"], ref["cy"], ref["r_inner"])

    fig, axes = plt.subplots(2, 1, figsize=(14, 10))
    v_in = ~np.isnan(ew_in)
    v_out = ~np.isnan(ew_out)
    axes[0].plot(ang_in[v_in], ew_in[v_in], "b-o", markersize=3, alpha=0.7, label=f"Input (μ={np.nanmean(ew_in):.2f}, σ={np.nanstd(ew_in):.2f})")
    axes[0].plot(ang_out[v_out], ew_out[v_out], "r-o", markersize=3, alpha=0.7, label=f"Output (μ={np.nanmean(ew_out):.2f}, σ={np.nanstd(ew_out):.2f})")
    axes[0].set_title("Outer Boundary — Edge Width vs Angle", fontsize=12)
    axes[0].set_xlabel("Angle (degrees)")
    axes[0].set_ylabel("Edge Width (10-90%, px)")
    axes[0].legend()
    axes[0].grid(True, alpha=0.3)
    axes[0].set_xlim(0, 360)
    v_in2 = ~np.isnan(ew_in2)
    v_out2 = ~np.isnan(ew_out2)
    axes[1].plot(ang_in2[v_in2], ew_in2[v_in2], "b-o", markersize=3, alpha=0.7, label=f"Input (μ={np.nanmean(ew_in2):.2f}, σ={np.nanstd(ew_in2):.2f})")
    axes[1].plot(ang_out2[v_out2], ew_out2[v_out2], "r-o", markersize=3, alpha=0.7, label=f"Output (μ={np.nanmean(ew_out2):.2f}, σ={np.nanstd(ew_out2):.2f})")
    axes[1].set_title("Inner Boundary — Edge Width vs Angle", fontsize=12)
    axes[1].set_xlabel("Angle (degrees)")
    axes[1].set_ylabel("Edge Width (10-90%, px)")
    axes[1].legend()
    axes[1].grid(True, alpha=0.3)
    axes[1].set_xlim(0, 360)
    plt.tight_layout()
    plt.savefig(out_dir / "06_edge_width_angular.png", dpi=150)
    plt.close()
    log("  -> Saved 06_edge_width_angular.png")

    ew_uniformity_in = np.nanstd(ew_in) / np.nanmean(ew_in) * 100 if np.nanmean(ew_in) > 0 else float("nan")
    ew_uniformity_out = np.nanstd(ew_out) / np.nanmean(ew_out) * 100 if np.nanmean(ew_out) > 0 else float("nan")
    log(f"  Outer edge width uniformity (CV%): input={ew_uniformity_in:.1f}%, output={ew_uniformity_out:.1f}%")

    summary = {
        "image": "VisionTop_20251029182653732.bmp",
        "model": "r26_sm035 (R26 正式交付版, Whole-FOV PSF)",
        "image_size_hw": list(inp.shape),
        "annulus_geometry": {
            "center_xy": [round(float(ref["cx"]), 2), round(float(ref["cy"]), 2)],
            "r_inner": round(float(ref["r_inner"]), 2),
            "r_outer": round(float(ref["r_outer"]), 2),
            "ring_width": round(float(ref["r_outer"] - ref["r_inner"]), 2),
            "status": ref["status"],
            "method": ref["method"],
            "warnings": list(ref["warnings"]),
        },
        "edge_sharpness": {
            "outer_edge_width_input_px": round(safe_mean(w_in_outer), 3),
            "outer_edge_width_output_px": round(safe_mean(w_out_outer), 3),
            "inner_edge_width_input_px": round(safe_mean(w_in_inner), 3),
            "inner_edge_width_output_px": round(safe_mean(w_out_inner), 3),
            "outer_sharpening_ratio": round(safe_mean(w_in_outer) / safe_mean(w_out_outer), 3) if safe_mean(w_out_outer) > 0 else None,
            "gradient_boost_ratio": round(safe_mean(g_out_outer) / safe_mean(g_in_outer), 3) if safe_mean(g_in_outer) > 0 else None,
        },
        "circle_fit": {
            "input": serialize_circle_summary(fit_results["input"]),
            "output": serialize_circle_summary(fit_results["output"]),
        },
        "frequency_analysis": {
            "hf_energy_pct_input": round(float(hf_energy_in / total_in * 100), 3),
            "hf_energy_pct_output": round(float(hf_energy_out / total_out * 100), 3),
            "hf_boost": round(float(hf_energy_out / hf_energy_in), 3),
        },
        "background": {
            "std_input": round(float(np.std(bg_in_vals)), 3),
            "std_output": round(float(np.std(bg_out_vals)), 3),
            "uniformity_change_pct": round(float(bg_std_change), 2),
            "contrast_input": round(float(contrast_in), 2),
            "contrast_output": round(float(contrast_out), 2),
        },
        "artifacts": {
            "ringing_score_input": round(float(np.mean(ring_score_in)), 4),
            "ringing_score_output": round(float(np.mean(ring_score_out)), 4),
            "ringing_ratio": round(float(ringing_ratio), 3),
        },
        "edge_width_uniformity_cv_pct": {
            "outer_input": round(float(ew_uniformity_in), 2),
            "outer_output": round(float(ew_uniformity_out), 2),
        },
        "residual_harmonics": _build_harmonic_summary(fit_results),
        "hotspot_clusters": _build_hotspot_cluster_summary(fit_results),
    }

    with open(out_dir / "analysis_summary.json", "w", encoding="utf-8") as file:
        json.dump(summary, file, indent=2, ensure_ascii=False)

    log("\n" + "=" * 60)
    log("ALL ANALYSES COMPLETE")
    log("=" * 60)
    log(f"Results saved to: {out_dir}")
    return summary


if __name__ == "__main__":
    main()

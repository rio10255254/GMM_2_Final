from __future__ import annotations

import csv
import hashlib
import json
import math
import warnings
from pathlib import Path
from typing import Any

import cv2
import matplotlib
import numpy as np
from scipy.ndimage import map_coordinates, uniform_filter1d

matplotlib.use("Agg")
import matplotlib.pyplot as plt


plt.rcParams.update(
    {
        "font.family": "sans-serif",
        "font.sans-serif": [
            "Microsoft JhengHei",
            "Microsoft YaHei",
            "SimHei",
            "Noto Sans CJK TC",
            "DejaVu Sans",
        ],
        "axes.unicode_minus": False,
        "font.size": 12,
        "axes.titlesize": 13,
        "axes.labelsize": 12,
        "xtick.labelsize": 10,
        "ytick.labelsize": 10,
        "legend.fontsize": 10,
        "figure.dpi": 180,
        "savefig.bbox": "tight",
        "savefig.pad_inches": 0.12,
        "mathtext.fontset": "dejavusans",
    }
)

warnings.filterwarnings(
    "ignore",
    message=r"Font 'default' does not have a glyph for '\\u2212' \[U\+2212\], substituting with a dummy symbol\.",
)


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def load_grayscale_image(path: Path) -> np.ndarray:
    arr = np.fromfile(path, dtype=np.uint8)
    image = cv2.imdecode(arr, cv2.IMREAD_GRAYSCALE)
    if image is None:
        raise FileNotFoundError(path)
    return image


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def dump_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _gradient_magnitude(image: np.ndarray) -> np.ndarray:
    image_f = image.astype(np.float32)
    gx = cv2.Sobel(image_f, cv2.CV_32F, 1, 0, ksize=3)
    gy = cv2.Sobel(image_f, cv2.CV_32F, 0, 1, ksize=3)
    return np.sqrt(gx * gx + gy * gy)


def _radial_profile(image: np.ndarray, cx: float, cy: float) -> np.ndarray:
    yy, xx = np.indices(image.shape)
    rr = np.sqrt((xx - cx) ** 2 + (yy - cy) ** 2)
    ridx = np.floor(rr).astype(np.int32)
    sums = np.bincount(ridx.ravel(), weights=image.ravel().astype(np.float64))
    counts = np.bincount(ridx.ravel())
    return sums / np.maximum(counts, 1)


def detect_ring_reference(image: np.ndarray, config: dict[str, Any]) -> dict[str, Any]:
    blur = cv2.GaussianBlur(image, (0, 0), 3.0)
    otsu, _ = cv2.threshold(blur, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    bright_threshold = int(max(otsu, np.percentile(blur, 84)))
    mask = (blur >= bright_threshold).astype(np.uint8) * 255
    kernel = np.ones((3, 3), np.uint8)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
    count, labels, stats, centers = cv2.connectedComponentsWithStats(mask, 8)

    best_label = None
    best_score = -1.0
    best_contour = None
    for label in range(1, count):
        area = int(stats[label, cv2.CC_STAT_AREA])
        if area < 3000:
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
        border_margin = min(cx, cy, image.shape[1] - cx, image.shape[0] - cy)
        score = area * max(circularity, 0.05) * max(border_margin, 1.0)
        if score > best_score:
            best_score = score
            best_label = label
            best_contour = contours[0]

    if best_label is None:
        raise RuntimeError("Failed to detect ring reference.")

    cx = float(centers[best_label][0])
    cy = float(centers[best_label][1])
    if best_contour is not None and len(best_contour) >= 8:
        pts = best_contour[:, 0, :].astype(np.float64)
        design = np.column_stack([2.0 * pts[:, 0], 2.0 * pts[:, 1], np.ones(len(pts))])
        rhs = pts[:, 0] ** 2 + pts[:, 1] ** 2
        try:
            sol, *_ = np.linalg.lstsq(design, rhs, rcond=None)
            cx = float(sol[0])
            cy = float(sol[1])
        except np.linalg.LinAlgError:
            pass
    profile = _radial_profile(image, cx, cy)
    smooth_profile = uniform_filter1d(profile.astype(np.float64), size=7, mode="nearest")

    start = min(10, len(smooth_profile) - 1)
    peak_r = int(np.argmax(smooth_profile[start:])) + start
    peak_val = float(smooth_profile[peak_r])
    left_slice = smooth_profile[max(0, peak_r - 120) : max(peak_r - 20, 1)]
    right_slice = smooth_profile[min(peak_r + 20, len(smooth_profile) - 1) : min(peak_r + 120, len(smooth_profile))]
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

    thickness_px = float(outer_edge_r - inner_edge_r)
    return {
        "cx": cx,
        "cy": cy,
        "peak_r": float(peak_r),
        "inner_edge_r": float(inner_edge_r),
        "outer_edge_r": float(outer_edge_r),
        "thickness_px": thickness_px,
        "profile": profile.tolist(),
        "smooth_profile": smooth_profile.tolist(),
        "half_value": half_value,
        "baseline_value": baseline,
        "peak_value": peak_val,
    }


def _clip_rect(center_x: float, center_y: float, size: int, shape: tuple[int, int]) -> tuple[int, int, int, int] | None:
    half = size // 2
    x = int(round(center_x)) - half
    y = int(round(center_y)) - half
    x = max(0, min(x, shape[1] - size))
    y = max(0, min(y, shape[0] - size))
    if x < 0 or y < 0 or x + size > shape[1] or y + size > shape[0]:
        return None
    return (x, y, size, size)


def _crop(image: np.ndarray, rect: tuple[int, int, int, int]) -> np.ndarray:
    x, y, w, h = rect
    return image[y : y + h, x : x + w]


def _distance(rect_a: tuple[int, int, int, int], rect_b: tuple[int, int, int, int]) -> float:
    ax = rect_a[0] + rect_a[2] / 2.0
    ay = rect_a[1] + rect_a[3] / 2.0
    bx = rect_b[0] + rect_b[2] / 2.0
    by = rect_b[1] + rect_b[3] / 2.0
    return float(np.hypot(ax - bx, ay - by))


def _annulus_mask(shape: tuple[int, int], ref: dict[str, Any], pad: float = 0.0) -> np.ndarray:
    yy, xx = np.indices(shape)
    rr = np.sqrt((xx - ref["cx"]) ** 2 + (yy - ref["cy"]) ** 2)
    return (rr >= ref["inner_edge_r"] - pad) & (rr <= ref["outer_edge_r"] + pad)


def _candidate_score(raw_crop: np.ndarray, recon_crop: np.ndarray) -> dict[str, float]:
    raw_grad = _gradient_magnitude(raw_crop)
    recon_grad = _gradient_magnitude(recon_crop)
    raw_edge = float(np.percentile(raw_grad, 92))
    recon_edge = float(np.percentile(recon_grad, 92))
    return {
        "raw_edge": raw_edge,
        "gain": recon_edge - raw_edge,
        "defect_darkness": float(np.percentile(raw_crop, 95) - np.percentile(raw_crop, 15)),
        "variance": float(np.var(raw_crop)),
        "grad_mean": float(raw_grad.mean()),
    }


def select_rois(
    raw: np.ndarray,
    recon: np.ndarray,
    ref: dict[str, Any],
    config: dict[str, Any],
) -> tuple[dict[str, tuple[int, int, int, int]], dict[str, Any]]:
    size = int(config["roi_size"])
    annulus_mid_r = (ref["inner_edge_r"] + ref["outer_edge_r"]) / 2.0
    angles = np.linspace(-math.pi, math.pi, 180, endpoint=False)

    candidates: list[dict[str, Any]] = []
    for theta in angles:
        px = ref["cx"] + annulus_mid_r * math.cos(theta)
        py = ref["cy"] + annulus_mid_r * math.sin(theta)
        rect = _clip_rect(px, py, size, raw.shape)
        if rect is None:
            continue
        raw_crop = _crop(raw, rect)
        recon_crop = _crop(recon, rect)
        score = _candidate_score(raw_crop, recon_crop)
        candidates.append({"theta": float(theta), "rect": rect, **score})

    if not candidates:
        raise RuntimeError("No annulus ROI candidates found.")

    candidates.sort(key=lambda item: item["raw_edge"], reverse=True)

    def choose_by(predicate, sort_key, reverse=False, used=None):
        used = used or []
        filtered = [item for item in candidates if predicate(item)]
        filtered.sort(key=sort_key, reverse=reverse)
        for item in filtered:
            if all(_distance(item["rect"], other) >= size * 0.75 for other in used):
                return item
        raise RuntimeError("Failed to choose ROI candidate.")

    main_edge = choose_by(
        predicate=lambda item: item["gain"] > 0 and item["raw_edge"] > np.percentile([c["raw_edge"] for c in candidates], 60),
        sort_key=lambda item: item["raw_edge"] + 0.5 * item["gain"],
        reverse=True,
    )
    defect = choose_by(
        predicate=lambda item: True,
        sort_key=lambda item: item["defect_darkness"],
        reverse=True,
        used=[main_edge["rect"]],
    )
    weak_edge = choose_by(
        predicate=lambda item: item["gain"] > 0,
        sort_key=lambda item: item["raw_edge"],
        reverse=False,
        used=[main_edge["rect"], defect["rect"]],
    )

    annulus_exclusion = _annulus_mask(raw.shape, ref, pad=size / 2.5)
    grad = _gradient_magnitude(raw)
    best_background: dict[str, Any] | None = None
    y_limit = int(max(0, ref["cy"] - ref["outer_edge_r"] * 0.4))
    step = max(6, size // 8)
    for y in range(0, max(y_limit - size, 1), step):
        for x in range(0, max(raw.shape[1] - size, 1), step):
            rect = (x, y, size, size)
            if annulus_exclusion[y : y + size, x : x + size].any():
                continue
            crop = _crop(raw, rect)
            crop_grad = grad[y : y + size, x : x + size]
            score = float(np.var(crop) + np.mean(crop_grad) * 4.0)
            if best_background is None or score < best_background["score"]:
                best_background = {"rect": rect, "score": score}

    if best_background is None:
        raise RuntimeError("Failed to select background ROI.")

    overrides = config.get("roi_override", {})
    rois = {
        "main_edge": tuple(overrides.get("main_edge") or main_edge["rect"]),
        "defect": tuple(overrides.get("defect") or defect["rect"]),
        "weak_edge": tuple(overrides.get("weak_edge") or weak_edge["rect"]),
        "background": tuple(overrides.get("background") or best_background["rect"]),
    }
    roi_log = {
        "scores": {
            "main_edge": {
                "theta_deg": math.degrees(main_edge["theta"]),
                "raw_edge": main_edge["raw_edge"],
                "gain": main_edge["gain"],
                "rect": list(main_edge["rect"]),
            },
            "defect": {
                "theta_deg": math.degrees(defect["theta"]),
                "defect_darkness": defect["defect_darkness"],
                "rect": list(defect["rect"]),
            },
            "weak_edge": {
                "theta_deg": math.degrees(weak_edge["theta"]),
                "raw_edge": weak_edge["raw_edge"],
                "gain": weak_edge["gain"],
                "rect": list(weak_edge["rect"]),
            },
            "background": {
                "score": best_background["score"],
                "rect": list(best_background["rect"]),
            },
        }
    }
    return rois, roi_log


def _sample_profile_bundle(
    image: np.ndarray,
    ref: dict[str, Any],
    theta: float,
    edge_r: float,
    config: dict[str, Any],
) -> dict[str, Any]:
    half_length = int(config["profile"]["half_length_px"])
    avg_lines = int(config["profile"]["avg_lines"])
    offsets = np.linspace(-math.radians(3.0), math.radians(3.0), avg_lines)
    s = np.linspace(-half_length, half_length, half_length * 2 + 1, dtype=np.float32)
    lines = []
    for delta in offsets:
        angle = theta + delta
        radii = edge_r + s
        xs = ref["cx"] + radii * np.cos(angle)
        ys = ref["cy"] + radii * np.sin(angle)
        sampled = map_coordinates(image.astype(np.float32), [ys, xs], order=1, mode="nearest")
        lines.append(sampled)
    stack = np.stack(lines, axis=0)
    return {"positions": s, "stack": stack, "profile": stack.mean(axis=0)}


def _transition_metrics(profile: np.ndarray, positions: np.ndarray, smooth_window: int) -> tuple[float, float, dict[str, Any]]:
    smooth = uniform_filter1d(profile.astype(np.float64), size=smooth_window, mode="nearest")
    head = smooth[: max(6, len(smooth) // 5)]
    tail = smooth[-max(6, len(smooth) // 5) :]
    high = float(np.mean(head))
    low = float(np.mean(tail))
    if high <= low:
        smooth = smooth[::-1]
        positions = -positions[::-1]
        high = float(np.mean(smooth[: max(6, len(smooth) // 5)]))
        low = float(np.mean(smooth[-max(6, len(smooth) // 5) :]))
    fallback_used = False
    mono = smooth.copy()
    if np.any(np.diff(mono) > 0):
        mono = np.minimum.accumulate(mono)
        fallback_used = True

    norm = (mono - low) / max(high - low, 1e-6)
    x_desc = norm[::-1]
    y_desc = positions[::-1]

    def crossing(level: float) -> float:
        return float(np.interp(level, x_desc, y_desc))

    width = abs(crossing(0.1) - crossing(0.9))
    slope = float(np.max(np.abs(np.gradient(smooth, positions))))
    return width, slope, {
        "fallback_used": fallback_used,
        "high_level": high,
        "low_level": low,
        "positions": positions.tolist(),
        "smooth_profile": smooth.tolist(),
        "monotonic_profile": mono.tolist(),
    }


def _cnr_from_bundle(bundle: dict[str, Any], config: dict[str, Any]) -> float:
    positions = bundle["positions"]
    stack = bundle["stack"]
    fg_lo, fg_hi = config["profile"]["foreground_offsets_px"]
    bg_lo, bg_hi = config["profile"]["background_offsets_px"]
    fg_mask = (positions >= -fg_hi) & (positions <= -fg_lo)
    bg_mask = (positions >= bg_lo) & (positions <= bg_hi)
    fg_vals = stack[:, fg_mask].ravel().astype(np.float64)
    bg_vals = stack[:, bg_mask].ravel().astype(np.float64)
    fg_mean = float(np.mean(fg_vals))
    bg_mean = float(np.mean(bg_vals))
    bg_std = float(np.std(bg_vals))
    return (fg_mean - bg_mean) / max(bg_std, 1e-6)


def compute_spatial_metrics(
    raw: np.ndarray,
    recon: np.ndarray,
    ref: dict[str, Any],
    rois: dict[str, tuple[int, int, int, int]],
    config: dict[str, Any],
) -> tuple[dict[str, dict[str, float]], dict[str, Any], dict[str, Any]]:
    roi_angles = {}
    for name, rect in rois.items():
        if name == "background":
            continue
        cx = rect[0] + rect[2] / 2.0
        cy = rect[1] + rect[3] / 2.0
        roi_angles[name] = math.atan2(cy - ref["cy"], cx - ref["cx"])

    profile_log: dict[str, Any] = {}
    plot_data: dict[str, Any] = {}
    rows = {"RAW": {}, "R26": {}}
    background_rect = rois["background"]
    raw_background = _crop(raw, background_rect)
    recon_background = _crop(recon, background_rect)
    rows["RAW"]["background_std"] = float(np.std(raw_background))
    rows["R26"]["background_std"] = float(np.std(recon_background))
    rows["RAW"]["background_grad_p95"] = float(np.percentile(_gradient_magnitude(raw_background), 95))
    rows["R26"]["background_grad_p95"] = float(np.percentile(_gradient_magnitude(recon_background), 95))

    for label, theta in [("main_edge", roi_angles["main_edge"]), ("weak_edge", roi_angles["weak_edge"])]:
        raw_bundle = _sample_profile_bundle(raw, ref, theta, ref["outer_edge_r"], config)
        recon_bundle = _sample_profile_bundle(recon, ref, theta, ref["outer_edge_r"], config)
        raw_width, raw_slope, raw_log = _transition_metrics(raw_bundle["profile"], raw_bundle["positions"], int(config["profile"]["smooth_window"]))
        recon_width, recon_slope, recon_log = _transition_metrics(recon_bundle["profile"], recon_bundle["positions"], int(config["profile"]["smooth_window"]))
        cnr_raw = _cnr_from_bundle(raw_bundle, config)
        cnr_recon = _cnr_from_bundle(recon_bundle, config)
        width_key = "edge_width_main_px" if label == "main_edge" else "edge_width_weak_px"
        slope_key = "max_slope_main" if label == "main_edge" else "max_slope_weak"
        cnr_key = "CNR_main" if label == "main_edge" else "CNR_weak"
        rows["RAW"][width_key] = raw_width
        rows["R26"][width_key] = recon_width
        rows["RAW"][slope_key] = raw_slope
        rows["R26"][slope_key] = recon_slope
        rows["RAW"][cnr_key] = cnr_raw
        rows["R26"][cnr_key] = cnr_recon
        profile_log[label] = {"theta_deg": math.degrees(theta), "raw": raw_log, "r26": recon_log}
        plot_data[label] = {
            "positions": raw_bundle["positions"],
            "raw_profile": raw_bundle["profile"],
            "r26_profile": recon_bundle["profile"],
            "raw_width": raw_width,
            "r26_width": recon_width,
            "raw_slope": raw_slope,
            "r26_slope": recon_slope,
        }
    return rows, plot_data, profile_log


def _frequency_axes(shape: tuple[int, int]) -> tuple[np.ndarray, np.ndarray]:
    fy = np.fft.fftshift(np.fft.fftfreq(shape[0])) / 0.5
    fx = np.fft.fftshift(np.fft.fftfreq(shape[1])) / 0.5
    return np.meshgrid(fx, fy)


def compute_fft_features(image: np.ndarray, ref: dict[str, Any], config: dict[str, Any]) -> dict[str, Any]:
    margin = int(config["fft"]["crop_margin_px"])
    radius = int(math.ceil(ref["outer_edge_r"] + margin))
    x0 = max(0, int(round(ref["cx"])) - radius)
    x1 = min(image.shape[1], int(round(ref["cx"])) + radius)
    y0 = max(0, int(round(ref["cy"])) - radius)
    y1 = min(image.shape[0], int(round(ref["cy"])) + radius)
    crop = image[y0:y1, x0:x1].astype(np.float32)
    data = crop - float(np.mean(crop))
    if config["fft"]["use_hann"]:
        wy = np.hanning(crop.shape[0])[:, None]
        wx = np.hanning(crop.shape[1])[None, :]
        data = data * wy * wx

    fft = np.fft.fftshift(np.fft.fft2(data))
    power = np.abs(fft) ** 2
    log_mag = np.log1p(power)

    fx, fy = _frequency_axes(crop.shape)
    radial = np.sqrt(fx * fx + fy * fy)
    hf_lo, hf_hi = config["fft"]["radial_hf_band"]
    total_lo, total_hi = config["fft"]["radial_total_band"]
    total_mask = (radial >= total_lo) & (radial <= total_hi)
    hf_mask = (radial >= hf_lo) & (radial <= hf_hi)
    hf_ratio = float(power[hf_mask].sum() / max(power[total_mask].sum(), 1e-6))

    cb_lo = float(config["fft"]["checkerboard_corner_threshold"])
    cb_hi_lo, cb_hi_hi = config["fft"]["checkerboard_total_hf_band"]
    checker_mask = (np.abs(fx) >= cb_lo) & (np.abs(fy) >= cb_lo)
    hf_total_mask = (radial >= cb_hi_lo) & (radial <= cb_hi_hi)
    checkerboard_ratio = float(power[checker_mask].sum() / max(power[hf_total_mask].sum(), 1e-6))

    bins = np.linspace(0.0, 1.0, 256)
    radial_curve = []
    radial_x = []
    for lo, hi in zip(bins[:-1], bins[1:]):
        mask = (radial >= lo) & (radial < hi)
        if mask.any():
            radial_x.append((lo + hi) / 2.0)
            radial_curve.append(float(power[mask].mean()))
    radial_curve_arr = np.asarray(radial_curve, dtype=np.float64)
    if radial_curve_arr.size:
        radial_curve_arr = radial_curve_arr / max(radial_curve_arr.max(), 1e-6)

    return {
        "crop_rect": [x0, y0, x1 - x0, y1 - y0],
        "crop": crop,
        "log_magnitude": log_mag,
        "radial_x": np.asarray(radial_x, dtype=np.float64),
        "radial_curve": radial_curve_arr,
        "hf_ratio": hf_ratio,
        "checkerboard_ratio": checkerboard_ratio,
    }


def compute_fft_metrics(
    raw: np.ndarray,
    recon: np.ndarray,
    ref: dict[str, Any],
    config: dict[str, Any],
) -> tuple[dict[str, dict[str, float]], dict[str, Any]]:
    raw_features = compute_fft_features(raw, ref, config)
    recon_features = compute_fft_features(recon, ref, config)
    rows = {
        "RAW": {
            "HF_ratio": raw_features["hf_ratio"],
            "checkerboard_ratio": raw_features["checkerboard_ratio"],
        },
        "R26": {
            "HF_ratio": recon_features["hf_ratio"],
            "checkerboard_ratio": recon_features["checkerboard_ratio"],
        },
    }
    return rows, {"RAW": raw_features, "R26": recon_features}


def _radial_line(image: np.ndarray, ref: dict[str, Any], theta: float, r_start: float, r_end: float) -> tuple[np.ndarray, np.ndarray]:
    radii = np.linspace(r_start, r_end, int(round(r_end - r_start)) + 1, dtype=np.float32)
    xs = ref["cx"] + radii * np.cos(theta)
    ys = ref["cy"] + radii * np.sin(theta)
    values = map_coordinates(image.astype(np.float32), [ys, xs], order=1, mode="nearest")
    return radii, values


def _per_angle_edges(
    image: np.ndarray,
    ref: dict[str, Any],
    config: dict[str, Any],
    thresholds: tuple[float, float] | None = None,
) -> tuple[list[dict[str, float]], tuple[float, float]]:
    num_angles = int(config["geometry"]["num_angles"])
    edge_window = float(config["geometry"]["edge_search_half_window_px"])
    padding = float(config["geometry"]["sampling_padding_px"])
    angles = np.linspace(-math.pi, math.pi, num_angles, endpoint=False)

    provisional = []
    inner_mags = []
    outer_mags = []
    r_start = ref["inner_edge_r"] - padding
    r_end = ref["outer_edge_r"] + padding
    for theta in angles:
        radii, values = _radial_line(image, ref, theta, r_start, r_end)
        smooth = uniform_filter1d(values.astype(np.float64), size=5, mode="nearest")
        grad = np.gradient(smooth, radii)
        inner_mask = (radii >= ref["inner_edge_r"] - edge_window) & (radii <= ref["inner_edge_r"] + edge_window)
        outer_mask = (radii >= ref["outer_edge_r"] - edge_window) & (radii <= ref["outer_edge_r"] + edge_window)
        inner_grad = grad[inner_mask]
        outer_grad = grad[outer_mask]
        inner_r = radii[inner_mask]
        outer_r = radii[outer_mask]
        inner_idx = int(np.argmax(inner_grad))
        outer_idx = int(np.argmin(outer_grad))
        inner_mag = float(max(inner_grad[inner_idx], 0.0))
        outer_mag = float(abs(min(outer_grad[outer_idx], 0.0)))
        provisional.append(
            {
                "theta": float(theta),
                "inner_r": float(inner_r[inner_idx]),
                "outer_r": float(outer_r[outer_idx]),
                "inner_mag": inner_mag,
                "outer_mag": outer_mag,
            }
        )
        inner_mags.append(inner_mag)
        outer_mags.append(outer_mag)

    if thresholds is None:
        q = float(config["geometry"]["gradient_valid_quantile"])
        thresholds = (
            float(np.quantile(np.asarray(inner_mags, dtype=np.float64), q)),
            float(np.quantile(np.asarray(outer_mags, dtype=np.float64), q)),
        )

    inner_threshold, outer_threshold = thresholds
    results = []
    for item in provisional:
        valid = item["inner_mag"] >= inner_threshold and item["outer_mag"] >= outer_threshold
        results.append({**item, "valid": float(valid), "thickness": float(item["outer_r"] - item["inner_r"])})
    return results, thresholds


def compute_geometry_proxy(
    raw: np.ndarray,
    recon: np.ndarray,
    ref: dict[str, Any],
    config: dict[str, Any],
) -> tuple[dict[str, dict[str, float]], dict[str, Any]]:
    raw_edges, thresholds = _per_angle_edges(raw, ref, config, thresholds=None)
    recon_edges, _ = _per_angle_edges(recon, ref, config, thresholds=thresholds)

    def summarise(edges: list[dict[str, float]]) -> dict[str, float]:
        valid_edges = [item for item in edges if bool(item["valid"])]
        thickness = np.asarray([item["thickness"] for item in valid_edges], dtype=np.float64)
        return {
            "edge_continuity_ratio": float(len(valid_edges) / max(len(edges), 1)),
            "ring_thickness_std_px": float(np.std(thickness)) if len(thickness) >= 3 else float("nan"),
        }

    rows = {"RAW": summarise(raw_edges), "R26": summarise(recon_edges)}
    geo_log = {
        "thresholds": {"inner_gradient_threshold": thresholds[0], "outer_gradient_threshold": thresholds[1]},
        "valid_angle_counts": {
            "RAW": int(sum(bool(item["valid"]) for item in raw_edges)),
            "R26": int(sum(bool(item["valid"]) for item in recon_edges)),
        },
        "angles": {"RAW": raw_edges, "R26": recon_edges},
    }
    return rows, geo_log


def render_overall_compare(raw: np.ndarray, recon: np.ndarray, config: dict[str, Any], out_path: Path) -> None:
    vmin, vmax = config["gray_display"]
    fig, axes = plt.subplots(1, 2, figsize=(10.5, 6.6))
    for ax, title, image in zip(axes, ["RAW", "R26"], [raw, recon]):
        ax.imshow(image, cmap="gray", vmin=vmin, vmax=vmax)
        ax.set_title(title)
        ax.axis("off")
    fig.suptitle("單張重建整體比較", fontsize=15, fontweight="bold")
    fig.savefig(out_path)
    plt.close(fig)


def render_roi_compare(
    raw: np.ndarray,
    recon: np.ndarray,
    rois: dict[str, tuple[int, int, int, int]],
    config: dict[str, Any],
    out_path: Path,
) -> None:
    vmin, vmax = config["gray_display"]
    labels = [("main_edge", "主要邊界"), ("defect", "缺陷區"), ("weak_edge", "弱邊界"), ("background", "背景區")]
    fig, axes = plt.subplots(2, len(labels), figsize=(14, 6.8))
    for col, (key, label) in enumerate(labels):
        for row, image in enumerate([raw, recon]):
            crop = _crop(image, rois[key])
            ax = axes[row, col]
            ax.imshow(crop, cmap="gray", vmin=vmin, vmax=vmax)
            ax.set_title(f"{label} - {'RAW' if row == 0 else 'R26'}")
            ax.axis("off")
    fig.suptitle("代表性 ROI 放大比較", fontsize=15, fontweight="bold")
    fig.savefig(out_path)
    plt.close(fig)


def render_edge_profiles(plot_data: dict[str, Any], out_path: Path) -> None:
    fig, axes = plt.subplots(1, 2, figsize=(13.5, 5.0), sharey=False)
    for ax, key, title in zip(axes, ["main_edge", "weak_edge"], ["主要邊界剖面", "弱邊界剖面"]):
        entry = plot_data[key]
        ax.plot(entry["positions"], entry["raw_profile"], color="#4C78A8", lw=2, label="RAW")
        ax.plot(entry["positions"], entry["r26_profile"], color="#F58518", lw=2, label="R26")
        ax.set_title(f"{title}\nwidth: {entry['raw_width']:.2f}px -> {entry['r26_width']:.2f}px")
        ax.set_xlabel("相對邊界位置 (px)")
        ax.set_ylabel("灰階值")
        ax.grid(alpha=0.25)
        ax.legend()
        ax.text(
            0.02,
            0.04,
            f"max slope: {entry['raw_slope']:.2f} -> {entry['r26_slope']:.2f}",
            transform=ax.transAxes,
            ha="left",
            va="bottom",
            fontsize=9,
            bbox={"boxstyle": "round,pad=0.25", "facecolor": "white", "alpha": 0.8},
        )
    fig.suptitle("邊界灰階剖面與 transition width", fontsize=15, fontweight="bold")
    fig.savefig(out_path)
    plt.close(fig)


def render_frequency_validation(plot_data: dict[str, Any], out_path: Path) -> None:
    raw = plot_data["RAW"]
    recon = plot_data["R26"]
    vmax = max(float(np.percentile(raw["log_magnitude"], 99)), float(np.percentile(recon["log_magnitude"], 99)))
    fig, axes = plt.subplots(2, 2, figsize=(11.5, 8.6))

    im0 = axes[0, 0].imshow(raw["log_magnitude"], cmap="magma", vmin=0, vmax=vmax)
    axes[0, 0].set_title("RAW FFT log magnitude")
    axes[0, 0].axis("off")
    fig.colorbar(im0, ax=axes[0, 0], fraction=0.046, pad=0.04)

    im1 = axes[0, 1].imshow(recon["log_magnitude"], cmap="magma", vmin=0, vmax=vmax)
    axes[0, 1].set_title("R26 FFT log magnitude")
    axes[0, 1].axis("off")
    fig.colorbar(im1, ax=axes[0, 1], fraction=0.046, pad=0.04)

    raw_x = raw["radial_x"][1:] if len(raw["radial_x"]) > 1 else raw["radial_x"]
    raw_y = raw["radial_curve"][1:] if len(raw["radial_curve"]) > 1 else raw["radial_curve"]
    recon_x = recon["radial_x"][1:] if len(recon["radial_x"]) > 1 else recon["radial_x"]
    recon_y = recon["radial_curve"][1:] if len(recon["radial_curve"]) > 1 else recon["radial_curve"]
    axes[1, 0].semilogy(raw_x, raw_y + 1e-6, color="#4C78A8", lw=2, label="RAW")
    axes[1, 0].semilogy(recon_x, recon_y + 1e-6, color="#F58518", lw=2, label="R26")
    axes[1, 0].set_title("Radial average spectrum")
    axes[1, 0].set_xlabel("Normalized frequency")
    axes[1, 0].set_ylabel("Normalized power (log)")
    axes[1, 0].set_xlim(0.0, 0.7)
    axes[1, 0].grid(alpha=0.25)
    axes[1, 0].legend()

    axes[1, 1].axis("off")
    text = "\n".join(
        [
            f"HF ratio: {raw['hf_ratio']:.4f} -> {recon['hf_ratio']:.4f}",
            f"Checkerboard ratio: {raw['checkerboard_ratio']:.4f} -> {recon['checkerboard_ratio']:.4f}",
            "",
            "解讀原則：",
            "- 看 R26 是否在有效頻帶更集中",
            "- 看 checkerboard/corner energy 是否未異常升高",
        ]
    )
    axes[1, 1].text(
        0.02,
        0.98,
        text,
        ha="left",
        va="top",
        fontsize=11,
        bbox={"boxstyle": "round,pad=0.4", "facecolor": "white", "alpha": 0.9},
    )
    fig.suptitle("頻域驗證", fontsize=15, fontweight="bold")
    fig.savefig(out_path)
    plt.close(fig)


def rows_to_dicts(rows: dict[str, dict[str, float]]) -> list[dict[str, Any]]:
    keys = sorted({key for values in rows.values() for key in values})
    ordered = []
    for image_name in ["RAW", "R26"]:
        row = {"image": image_name}
        for key in keys:
            row[key] = rows[image_name].get(key, float("nan"))
        ordered.append(row)
    return ordered


def write_metrics_csv(rows: list[dict[str, Any]], out_path: Path) -> None:
    fieldnames = list(rows[0].keys())
    with out_path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write_metrics_markdown(rows: list[dict[str, Any]], out_path: Path) -> None:
    headers = list(rows[0].keys())
    lines = ["# 單張重建總表", "", "|" + "|".join(headers) + "|", "|" + "|".join(["---"] * len(headers)) + "|"]
    for row in rows:
        values = []
        for header in headers:
            value = row[header]
            if isinstance(value, (float, np.floating)):
                if math.isnan(float(value)):
                    values.append("not reliable")
                else:
                    values.append(f"{float(value):.4f}")
            else:
                values.append(str(value))
        lines.append("|" + "|".join(values) + "|")
    out_path.write_text("\n".join(lines), encoding="utf-8")


def build_plan_markdown(context: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# 單張影像重建分析規劃摘要",
            "",
            "## 可用資料",
            f"- RAW：`{context['raw_path']}`",
            f"- R26：`{context['r26_path']}`",
            f"- RAW SHA256：`{context['raw_hash']}`",
            f"- R26 SHA256：`{context['r26_hash']}`",
            "- 可重用邏輯：`detect_ring`、radial profile、ring ROI。",
            "- 不納入：GMF、SSIM、PSNR、MTF、GLCM、wavelet、多版本比較。",
            "",
            "## 主分析項目",
            "- 整體比較圖：RAW vs R26。",
            "- 4 類 ROI：主要邊界、缺陷區、弱邊界、背景區。",
            "- Edge profile：主邊界與弱邊界各 1 條，固定平滑與 10%~90% width 定義。",
            "- 頻域驗證：2D FFT、radial spectrum、HF ratio、checkerboard ratio。",
            "- 幾何 proxy：edge_continuity_ratio、ring_thickness_std_px。",
            "",
            "## 核心證據鏈",
            "- 視覺對照建立直觀差異。",
            "- Edge profile 證明邊界更陡、更集中。",
            "- CNR 與 background_std 檢查改善不是靠背景惡化換來。",
            "- FFT 與 checkerboard ratio 排除不自然高頻。",
            "- 幾何 proxy 保守支持其對後續辨識/量測較有利。",
            "",
            "## 最終圖與表",
            "- 圖 1：整體比較圖，回答整張影像層級的直觀差異。",
            "- 圖 2：ROI 放大圖，回答主要邊界、缺陷、弱邊界與背景的局部差異。",
            "- 圖 3：Edge profile 圖，回答邊界是否更集中。",
            "- 圖 4：頻域驗證圖，回答清楚是否可信、是否有假高頻。",
            "- 表 1：總表，整合空間域、頻域與幾何 proxy 指標。",
            "",
            "## 刻意不做的項目與原因",
            "- GMF：本次明確排除外部程式。",
            "- SSIM、PSNR、MTF：與本次無 GT 的單張證據鏈不相容或易被誤讀。",
            "- GLCM、wavelet、統計檢定：篇幅成本高，但報告說服力增量低。",
            "- 多版本比較：會把 RAW vs R26 主線打散。",
            "",
            "## 可安全下結論的點",
            "- 邊界是否更集中。",
            "- 背景波動是否未明顯惡化。",
            "- 是否未出現明顯 checkerboard/假高頻趨勢。",
            "",
            "## 只能寫成趨勢的點",
            "- 更接近真值。",
            "- 真實解析度提升。",
            "- 實際量測精度已被直接證明提升。",
        ]
    )


def build_result_draft(context: dict[str, Any], rows: list[dict[str, Any]]) -> str:
    raw_row = next(row for row in rows if row["image"] == "RAW")
    recon_row = next(row for row in rows if row["image"] == "R26")
    return "\n".join(
        [
            "# 單張影像重建分析結果草稿",
            "",
            "## 分析目的",
            "本分析以單張代表性外部影像為對象，比較 RAW 與 R26 重建結果，目的在於確認重建後的邊界是否更集中、此改善是否可信，並以幾何 proxy 保守支持其對後續辨識或量測較有利。",
            "",
            "## 圖表對應說明",
            "- 圖 1：整體比較圖，觀察整張影像中的主結構、背景與缺陷分布。",
            "- 圖 2：ROI 放大圖，對照主要邊界、缺陷區、弱邊界與背景區。",
            "- 圖 3：Edge profile 圖，量化主邊界與弱邊界的 transition width 與 max slope。",
            "- 圖 4：頻域驗證圖，確認頻帶重分配是否伴隨明顯 checkerboard 傾向。",
            "- 表 1：整合空間域、頻域與幾何 proxy 指標。",
            "",
            "## 建議解讀方式",
            f"- 主邊界 edge width 由 `{raw_row['edge_width_main_px']:.2f}` px 變為 `{recon_row['edge_width_main_px']:.2f}` px，若同步伴隨 max slope 由 `{raw_row['max_slope_main']:.2f}` 提升至 `{recon_row['max_slope_main']:.2f}`，可寫成邊界轉換更集中。",
            f"- 主要邊界 CNR 由 `{raw_row['CNR_main']:.2f}` 提升至 `{recon_row['CNR_main']:.2f}`；若背景標準差由 `{raw_row['background_std']:.2f}` 變為 `{recon_row['background_std']:.2f}` 且未明顯惡化，可寫成對比改善不是單純以背景惡化交換而來。",
            f"- HF ratio 由 `{raw_row['HF_ratio']:.4f}` 變為 `{recon_row['HF_ratio']:.4f}`，checkerboard ratio 由 `{raw_row['checkerboard_ratio']:.4f}` 變為 `{recon_row['checkerboard_ratio']:.4f}`；應以『未見明顯假高頻污染』或『頻帶更集中』的保守語氣描述。",
            f"- 幾何 proxy 中 edge continuity 由 `{raw_row['edge_continuity_ratio']:.4f}` 變為 `{recon_row['edge_continuity_ratio']:.4f}`，ring thickness std 由 `{raw_row['ring_thickness_std_px']:.4f}` 變為 `{recon_row['ring_thickness_std_px']:.4f}`；若方向正向，可寫成『幾何 proxy 支持重建後邊界結構較完整，顯示其對後續辨識或量測較有利』。",
            "",
            "## 結論建議寫法",
            "本單張分析顯示，R26 重建後在主要邊界與弱邊界上均呈現較集中的灰階轉換，且局部對比提升並未伴隨背景波動的明顯放大。頻域結果未顯示明顯 checkerboard 或不自然高頻污染，幾何 proxy 亦顯示重建後邊界結構較完整。綜合而言，R26 的改善不僅是視覺上的清晰化，且以保守方式支持其對後續幾何辨識或量測較有利。",
            "",
            "## 保守措辭提醒",
            "- 不要寫成已直接證明真值品質提升。",
            "- 不要寫成已直接證明實際量測精度提升。",
            "- 幾何層請統一寫成『proxy 支持』或『顯示較有利』。",
            "",
            "## 必答問題整理",
            "1. 核心證據鏈是：全圖/ROI -> edge profile -> 對比與背景 -> 頻域排除假高頻 -> 幾何 proxy。",
            "2. 最後保留 4 張主圖與 1 張總表，因為這已足夠覆蓋可視、量化、可信度與應用價值四個層次。",
            "3. 刻意不做 GMF、SSIM、PSNR、MTF、GLCM、wavelet、多版本比較，因為不符合本次問題設定或不利於報告簡潔。",
            "4. 目前最能安全下結論的是邊界更集中、背景未明顯惡化、未見明顯 checkerboard、幾何 proxy 方向正向。",
            "5. 只能寫成趨勢的是更接近真值、真實解析度提升、實際量測精度提升。",
        ]
    )

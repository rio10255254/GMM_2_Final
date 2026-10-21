from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

import cv2
import numpy as np

from displacement_common import (
    apply_crop,
    list_images,
    parse_crop,
    read_gray_u8,
    summarize_steps,
    write_csv,
    write_json,
)


def _float01(image: np.ndarray) -> np.ndarray:
    arr = image.astype(np.float32)
    lo = float(np.percentile(arr, 1.0))
    hi = float(np.percentile(arr, 99.0))
    if hi <= lo:
        lo = float(arr.min())
        hi = float(arr.max())
    if hi <= lo:
        return np.zeros_like(arr, dtype=np.float32)
    return np.clip((arr - lo) / (hi - lo), 0.0, 1.0).astype(np.float32)


def feature_signal(
    image: np.ndarray,
    *,
    polarity: str,
    signal_mode: str = "intensity",
    blur_sigma: float = 0.8,
) -> np.ndarray:
    arr = _float01(image)
    if polarity == "dark":
        signal = 1.0 - arr
    elif polarity == "bright":
        signal = arr
    else:
        raise ValueError("polarity must be dark or bright")
    if blur_sigma > 0:
        signal = cv2.GaussianBlur(signal, (0, 0), blur_sigma)
    if signal_mode == "edge":
        grad_x = cv2.Sobel(signal, cv2.CV_32F, 1, 0, ksize=3)
        grad_y = cv2.Sobel(signal, cv2.CV_32F, 0, 1, ksize=3)
        signal = cv2.magnitude(grad_x, grad_y)
        peak = float(signal.max())
        if peak > 1e-8:
            signal = signal / peak
    elif signal_mode != "intensity":
        raise ValueError("signal_mode must be intensity or edge")
    return signal.astype(np.float32, copy=False)


def _weights_from_signal(signal: np.ndarray, threshold_quantile: float) -> np.ndarray:
    threshold = float(np.quantile(signal, threshold_quantile))
    weights = np.maximum(signal - threshold, 0.0)
    if float(weights.sum()) <= 1e-8:
        weights = np.maximum(signal - float(signal.min()), 0.0)
    return weights.astype(np.float32, copy=False)


def weighted_center(
    weights: np.ndarray,
    *,
    offset_x: float = 0.0,
    offset_y: float = 0.0,
) -> tuple[tuple[float, float], dict[str, float]]:
    total = float(weights.sum())
    if total <= 1e-8:
        raise ValueError("not enough feature weight for GMF-like center fitting")
    yy, xx = np.indices(weights.shape, dtype=np.float32)
    cx = float((weights * xx).sum() / total) + float(offset_x)
    cy = float((weights * yy).sum() / total) + float(offset_y)
    var_x = float((weights * (xx - (cx - offset_x)) ** 2).sum() / total)
    var_y = float((weights * (yy - (cy - offset_y)) ** 2).sum() / total)
    quality = {
        "total_weight": total,
        "peak_weight": float(weights.max()),
        "sigma_x_px": float(np.sqrt(max(var_x, 0.0))),
        "sigma_y_px": float(np.sqrt(max(var_y, 0.0))),
    }
    return (cx, cy), quality


def estimate_single_center(
    image: np.ndarray,
    *,
    polarity: str = "dark",
    signal_mode: str = "intensity",
    blur_sigma: float = 0.8,
    threshold_quantile: float = 0.65,
) -> tuple[tuple[float, float], dict[str, float]]:
    signal = feature_signal(image, polarity=polarity, signal_mode=signal_mode, blur_sigma=blur_sigma)
    weights = _weights_from_signal(signal, threshold_quantile)
    return weighted_center(weights)


def detect_component_centers(
    image: np.ndarray,
    *,
    polarity: str,
    signal_mode: str,
    blur_sigma: float,
    threshold_quantile: float,
    min_area: int,
    max_components: int,
) -> list[tuple[float, float]]:
    signal = feature_signal(image, polarity=polarity, signal_mode=signal_mode, blur_sigma=blur_sigma)
    weights = _weights_from_signal(signal, threshold_quantile)
    scaled = np.clip(weights / max(float(weights.max()), 1e-8) * 255.0, 0, 255).astype(np.uint8)
    _, binary = cv2.threshold(scaled, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    count, labels, stats, _ = cv2.connectedComponentsWithStats(binary, connectivity=8)
    centers: list[tuple[float, float, float]] = []
    for label in range(1, count):
        area = int(stats[label, cv2.CC_STAT_AREA])
        if area < min_area:
            continue
        mask = labels == label
        component_weights = np.where(mask, weights, 0.0)
        try:
            (cx, cy), quality = weighted_center(component_weights)
        except ValueError:
            continue
        centers.append((cx, cy, float(quality["total_weight"])))
    centers.sort(key=lambda item: item[2], reverse=True)
    return [(cx, cy) for cx, cy, _ in centers[:max_components]]


def _local_patch(
    image: np.ndarray,
    center: tuple[float, float],
    radius: int,
) -> tuple[np.ndarray, int, int] | None:
    cx, cy = center
    x0 = max(0, int(round(cx)) - radius)
    y0 = max(0, int(round(cy)) - radius)
    x1 = min(image.shape[1], int(round(cx)) + radius + 1)
    y1 = min(image.shape[0], int(round(cy)) + radius + 1)
    if x1 - x0 < 5 or y1 - y0 < 5:
        return None
    return image[y0:y1, x0:x1], x0, y0


def robust_shift_from_components(
    shifts: list[tuple[float, float]],
    *,
    cluster_radius: float = 1.5,
) -> tuple[float, float, int]:
    indices = robust_shift_cluster_indices(shifts, cluster_radius=cluster_radius)
    arr = np.array(shifts, dtype=np.float64)
    cluster = arr[indices]
    return float(np.median(cluster[:, 0])), float(np.median(cluster[:, 1])), int(len(cluster))


def robust_shift_cluster_indices(
    shifts: list[tuple[float, float]],
    *,
    cluster_radius: float = 1.5,
) -> list[int]:
    if not shifts:
        raise ValueError("no component shifts to summarize")
    arr = np.array(shifts, dtype=np.float64)
    if len(arr) <= 2:
        return list(range(len(arr)))

    best_mask: np.ndarray | None = None
    best_count = -1
    for point in arr:
        dist = np.sqrt(np.sum((arr - point) ** 2, axis=1))
        mask = dist <= cluster_radius
        count = int(np.sum(mask))
        if count > best_count:
            best_count = count
            best_mask = mask

    assert best_mask is not None
    return [int(index) for index in np.flatnonzero(best_mask)]


def pairwise_component_shifts(
    previous_centers: list[tuple[float, float]],
    current_centers: list[tuple[float, float]],
    *,
    max_shift_px: float,
) -> list[tuple[float, float]]:
    shifts: list[tuple[float, float]] = []
    for px, py in previous_centers:
        for cx, cy in current_centers:
            dx = float(cx - px)
            dy = float(cy - py)
            if abs(dx) > max_shift_px or abs(dy) > max_shift_px:
                continue
            if float(np.hypot(dx, dy)) > max_shift_px:
                continue
            shifts.append((dx, dy))
    return shifts


def _read_sequence(input_dir: Path, pattern: str, crop: tuple[int, int, int, int] | None) -> tuple[list[Path], list[np.ndarray]]:
    files = list_images(input_dir, pattern)
    images = [apply_crop(read_gray_u8(path), crop) for path in files]
    return files, images


def parse_seed_centers(values: list[str] | None) -> list[tuple[float, float]] | None:
    if not values:
        return None
    centers: list[tuple[float, float]] = []
    for value in values:
        parts = [part.strip() for part in value.split(",")]
        if len(parts) != 2:
            raise ValueError("--seed-center must be x,y; repeat the option for multiple centers")
        centers.append((float(parts[0]), float(parts[1])))
    return centers


def measure_sequence(
    input_dir: Path,
    *,
    crop: tuple[int, int, int, int] | None,
    polarity: str,
    mode: str = "multi",
    pattern: str = "*",
    signal_mode: str = "intensity",
    blur_sigma: float = 0.8,
    threshold_quantile: float = 0.65,
    min_area: int = 20,
    max_components: int = 60,
    local_radius: int = 24,
    cluster_radius: float = 1.5,
    seed_centers: list[tuple[float, float]] | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    files, images = _read_sequence(Path(input_dir), pattern, crop)
    if mode not in {"single", "multi", "pairwise"}:
        raise ValueError("mode must be single, multi, or pairwise")
    if signal_mode not in {"intensity", "edge"}:
        raise ValueError("signal_mode must be intensity or edge")
    if seed_centers is not None and mode != "multi":
        raise ValueError("seed_centers are only supported in multi mode")

    if mode == "single":
        first_center, first_quality = estimate_single_center(
            images[0],
            polarity=polarity,
            signal_mode=signal_mode,
            blur_sigma=blur_sigma,
            threshold_quantile=threshold_quantile,
        )
        previous_centers = [first_center]
        first_weight = first_quality["total_weight"]
    elif seed_centers is not None:
        if not seed_centers:
            raise ValueError("seed_centers must contain at least one center")
        previous_centers = [(float(cx), float(cy)) for cx, cy in seed_centers]
        first_weight = 0.0
    else:
        previous_centers = detect_component_centers(
            images[0],
            polarity=polarity,
            signal_mode=signal_mode,
            blur_sigma=blur_sigma,
            threshold_quantile=threshold_quantile,
            min_area=min_area,
            max_components=max_components,
        )
        if not previous_centers:
            raise ValueError(f"no GMF-like components found in first image: {files[0]}")
        first_weight = 0.0

    cumulative_dx = 0.0
    cumulative_dy = 0.0
    rows: list[dict[str, Any]] = [
        {
            "frame_index": 0,
            "filename": files[0].name,
            "ref_filename": "",
            "mode": mode,
            "dx_px": 0.0,
            "dy_px": 0.0,
            "cumulative_dx_px": 0.0,
            "cumulative_dy_px": 0.0,
            "feature_count": len(previous_centers),
            "median_feature_weight": first_weight,
            "status": "reference",
            "message": "",
        }
    ]
    pairwise_centers_by_index: list[list[tuple[float, float]]] | None = None
    if mode == "pairwise":
        pairwise_centers_by_index = [
            detect_component_centers(
                frame,
                polarity=polarity,
                signal_mode=signal_mode,
                blur_sigma=blur_sigma,
                threshold_quantile=threshold_quantile,
                min_area=min_area,
                max_components=max_components,
            )
            for frame in images
        ]

    for index, image in enumerate(images[1:], start=1):
        current_centers: list[tuple[float, float]] = []
        shifts: list[tuple[float, float]] = []
        weights: list[float] = []
        message = ""
        status = "ok"

        if mode == "single":
            center, quality = estimate_single_center(
                image,
                polarity=polarity,
                signal_mode=signal_mode,
                blur_sigma=blur_sigma,
                threshold_quantile=threshold_quantile,
            )
            px, py = previous_centers[0]
            shifts.append((center[0] - px, center[1] - py))
            current_centers.append(center)
            weights.append(float(quality["total_weight"]))
        elif mode == "multi":
            for center in previous_centers:
                patch = _local_patch(image, center, local_radius)
                if patch is None:
                    continue
                patch_image, x0, y0 = patch
                try:
                    local_center, quality = estimate_single_center(
                        patch_image,
                        polarity=polarity,
                        signal_mode=signal_mode,
                        blur_sigma=blur_sigma,
                        threshold_quantile=threshold_quantile,
                    )
                except ValueError:
                    continue
                new_center = (local_center[0] + x0, local_center[1] + y0)
                shifts.append((new_center[0] - center[0], new_center[1] - center[1]))
                current_centers.append(new_center)
                weights.append(float(quality["total_weight"]))
        else:
            assert pairwise_centers_by_index is not None
            pair_previous_centers = pairwise_centers_by_index[index - 1]
            pair_current_centers = pairwise_centers_by_index[index]
            shifts = pairwise_component_shifts(
                pair_previous_centers,
                pair_current_centers,
                max_shift_px=float(local_radius),
            )
            current_centers = pair_current_centers
            weights = [1.0] * len(shifts)

        if not shifts:
            dx = dy = median_weight = 0.0
            inlier_count = 0
            status = "failed"
            message = "no tracked GMF-like components"
            current_centers = previous_centers
        else:
            inlier_indices = robust_shift_cluster_indices(shifts, cluster_radius=cluster_radius)
            inlier_shifts = [shifts[i] for i in inlier_indices]
            dx, dy, inlier_count = robust_shift_from_components(inlier_shifts, cluster_radius=cluster_radius)
            median_weight = float(np.median(weights)) if weights else 0.0
            if mode == "pairwise":
                previous_centers = current_centers
            else:
                previous_centers = [current_centers[i] for i in inlier_indices]
            cumulative_dx += dx
            cumulative_dy += dy

        rows.append(
            {
                "frame_index": index,
                "filename": files[index].name,
                "ref_filename": files[index - 1].name,
                "mode": mode,
                "dx_px": dx,
                "dy_px": dy,
                "cumulative_dx_px": cumulative_dx,
                "cumulative_dy_px": cumulative_dy,
                "feature_count": inlier_count,
                "tracked_feature_count": len(shifts),
                "median_feature_weight": median_weight,
                "status": status,
                "message": message,
            }
        )

    summary: dict[str, Any] = {
        "algorithm": "gmf_like_gaussian_template_fit",
        "input_dir": str(input_dir),
        "image_count": len(files),
        "crop": crop,
        "polarity": polarity,
        "mode": mode,
        "signal_mode": signal_mode,
        "blur_sigma": blur_sigma,
        "threshold_quantile": threshold_quantile,
        "min_area": min_area,
        "max_components": max_components,
        "local_radius": local_radius,
        "cluster_radius": cluster_radius,
        "seed_centers": None
        if seed_centers is None
        else [[float(cx), float(cy)] for cx, cy in seed_centers],
        "failed_step_count": sum(1 for row in rows if row["status"] == "failed"),
    }
    summary.update(summarize_steps(rows))
    return rows, summary


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Measure displacement with an open GMF-like Gaussian template fit."
    )
    parser.add_argument("--input", required=True)
    parser.add_argument("--output-csv", required=True)
    parser.add_argument("--output-json")
    parser.add_argument("--pattern", default="*")
    parser.add_argument("--crop", help="Optional ROI as x,y,width,height.")
    parser.add_argument("--polarity", choices=["dark", "bright"], default="dark")
    parser.add_argument("--mode", choices=["single", "multi", "pairwise"], default="multi")
    parser.add_argument("--signal-mode", choices=["intensity", "edge"], default="intensity")
    parser.add_argument("--blur-sigma", type=float, default=0.8)
    parser.add_argument("--threshold-quantile", type=float, default=0.65)
    parser.add_argument("--min-area", type=int, default=20)
    parser.add_argument("--max-components", type=int, default=60)
    parser.add_argument("--local-radius", type=int, default=24)
    parser.add_argument("--cluster-radius", type=float, default=1.5)
    parser.add_argument(
        "--seed-center",
        action="append",
        default=[],
        help="Initial feature center as x,y in cropped coordinates; repeat for multiple centers. Only for multi mode.",
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()
    rows, summary = measure_sequence(
        Path(args.input),
        crop=parse_crop(args.crop),
        polarity=args.polarity,
        mode=args.mode,
        pattern=args.pattern,
        signal_mode=args.signal_mode,
        blur_sigma=args.blur_sigma,
        threshold_quantile=args.threshold_quantile,
        min_area=args.min_area,
        max_components=args.max_components,
        local_radius=args.local_radius,
        cluster_radius=args.cluster_radius,
        seed_centers=parse_seed_centers(args.seed_center),
    )
    fields = [
        "frame_index",
        "filename",
        "ref_filename",
        "mode",
        "dx_px",
        "dy_px",
        "cumulative_dx_px",
        "cumulative_dy_px",
        "feature_count",
        "tracked_feature_count",
        "median_feature_weight",
        "status",
        "message",
    ]
    write_csv(Path(args.output_csv), rows, fields)
    if args.output_json:
        summary["output_csv"] = str(Path(args.output_csv))
        write_json(Path(args.output_json), summary)
    print(f"Wrote {args.output_csv}")
    if args.output_json:
        print(f"Wrote {args.output_json}")


if __name__ == "__main__":
    main()

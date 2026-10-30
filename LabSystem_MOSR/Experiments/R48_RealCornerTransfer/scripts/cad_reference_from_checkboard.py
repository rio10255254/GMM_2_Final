"""Create CAD-like reference images from real Lab checkboard frames.

This is a conservative first-pass tool: it redraws high-confidence bright
checkboard regions from the observed pixels, removes small bright speckles, and
writes a same-size reference image plus a reliability mask for inspection.
"""
from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np


IMAGE_EXTENSIONS = {".bmp", ".png", ".tif", ".tiff"}


@dataclass(frozen=True)
class CadReferenceResult:
    gt: np.ndarray
    reliable_mask: np.ndarray
    overlay: np.ndarray
    metrics: dict[str, object]


def _as_gray(image: np.ndarray) -> np.ndarray:
    if image.ndim == 2:
        return image
    if image.ndim == 3:
        return cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    raise ValueError(f"unsupported image shape: {image.shape}")


def _odd_kernel(size: int) -> np.ndarray:
    size = max(1, int(size))
    if size % 2 == 0:
        size += 1
    return cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (size, size))


def _component_rectangles(
    mask: np.ndarray,
    *,
    min_component_area: int,
    min_rect_fill_ratio: float,
    max_rect_aspect_ratio: float,
    min_rect_solidity: float,
) -> tuple[list[np.ndarray], dict[str, int]]:
    num, labels, stats, _centroids = cv2.connectedComponentsWithStats(mask, connectivity=4)
    rectangles: list[np.ndarray] = []
    rejected_small = 0
    rejected_shape = 0
    rejected_frame_clipped = 0
    frame_height, frame_width = mask.shape
    for idx in range(1, num):
        area = int(stats[idx, cv2.CC_STAT_AREA])
        if area < int(min_component_area):
            rejected_small += 1
            continue
        left = int(stats[idx, cv2.CC_STAT_LEFT])
        top = int(stats[idx, cv2.CC_STAT_TOP])
        width_stat = int(stats[idx, cv2.CC_STAT_WIDTH])
        height_stat = int(stats[idx, cv2.CC_STAT_HEIGHT])
        if left <= 0 or top <= 0 or left + width_stat >= frame_width or top + height_stat >= frame_height:
            rejected_frame_clipped += 1
            continue
        component = np.zeros(mask.shape, dtype=np.uint8)
        component[labels == idx] = 255
        found, _hierarchy = cv2.findContours(component, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        for contour in found:
            rect = cv2.minAreaRect(contour)
            width, height = rect[1]
            rect_area = float(width) * float(height)
            fill_ratio = float(area) / rect_area if rect_area > 0 else 0.0
            min_side = max(1.0, min(float(width), float(height)))
            aspect_ratio = max(float(width), float(height)) / min_side
            hull = cv2.convexHull(contour)
            hull_area = cv2.contourArea(hull)
            solidity = cv2.contourArea(contour) / hull_area if hull_area > 0 else 0.0
            if (
                fill_ratio < float(min_rect_fill_ratio)
                or aspect_ratio > float(max_rect_aspect_ratio)
                or solidity < float(min_rect_solidity)
            ):
                rejected_shape += 1
                continue
            box = cv2.boxPoints(rect)
            rectangles.append(box.astype(np.float32).reshape(-1, 1, 2))
    return rectangles, {
        "rejected_small_components": int(rejected_small),
        "rejected_nonrect_components": int(rejected_shape),
        "rejected_frame_clipped_components": int(rejected_frame_clipped),
    }


def _redraw_rectangles(
    shape: tuple[int, int],
    rectangles: list[np.ndarray],
    *,
    rectangle_shrink_px: float,
) -> tuple[np.ndarray, list[int]]:
    gt = np.zeros(shape, dtype=np.uint8)
    vertex_counts: list[int] = []
    for rectangle in rectangles:
        if rectangle.size == 0:
            continue
        points = rectangle.reshape(-1, 2).astype(np.float32)
        shrink = float(rectangle_shrink_px)
        if shrink > 0:
            center = np.mean(points, axis=0, keepdims=True)
            vectors = points - center
            lengths = np.linalg.norm(vectors, axis=1, keepdims=True)
            scale = np.maximum((lengths - shrink) / np.maximum(lengths, 1e-6), 0.0)
            points = center + vectors * scale
        rectangle_i32 = np.round(points).astype(np.int32).reshape(-1, 1, 2)
        vertex_counts.append(int(len(rectangle)))
        cv2.fillPoly(gt, [rectangle_i32], 255)
    return gt, vertex_counts


def _frame_border_mask(shape: tuple[int, int], size: int) -> np.ndarray:
    mask = np.zeros(shape, dtype=np.uint8)
    size = max(0, int(size))
    if size == 0:
        return mask
    mask[:size, :] = 255
    mask[-size:, :] = 255
    mask[:, :size] = 255
    mask[:, -size:] = 255
    return mask


def _edge_distance_metrics(
    gt: np.ndarray,
    observed_mask: np.ndarray,
    *,
    frame_border_ignore_size: int,
) -> dict[str, object]:
    cad_boundary = cv2.morphologyEx(gt, cv2.MORPH_GRADIENT, _odd_kernel(3))
    observed_boundary = cv2.morphologyEx(observed_mask, cv2.MORPH_GRADIENT, _odd_kernel(3))
    border_mask = _frame_border_mask(gt.shape, frame_border_ignore_size)
    border_points = (cad_boundary > 0) & (border_mask > 0)
    cad_points = (cad_boundary > 0) & (border_mask == 0)
    if not np.any(cad_points) or not np.any(observed_boundary):
        return {
            "edge_sample_px": int(np.count_nonzero(cad_points)),
            "edge_ignored_border_px": int(np.count_nonzero(border_points)),
            "edge_median_px": None,
            "edge_p90_px": None,
            "edge_p95_px": None,
            "edge_max_px": None,
            "edge_within_2px_ratio": None,
            "edge_within_5px_ratio": None,
        }

    distance_input = np.full(gt.shape, 255, dtype=np.uint8)
    distance_input[observed_boundary > 0] = 0
    distances = cv2.distanceTransform(distance_input, cv2.DIST_L2, 3)
    samples = distances[cad_points]
    return {
        "edge_sample_px": int(samples.size),
        "edge_ignored_border_px": int(np.count_nonzero(border_points)),
        "edge_median_px": float(np.median(samples)),
        "edge_p90_px": float(np.percentile(samples, 90)),
        "edge_p95_px": float(np.percentile(samples, 95)),
        "edge_max_px": float(np.max(samples)),
        "edge_within_2px_ratio": float(np.mean(samples <= 2.0)),
        "edge_within_5px_ratio": float(np.mean(samples <= 5.0)),
    }


def _make_reliable_mask(
    gt: np.ndarray,
    raw_bright: np.ndarray,
    *,
    mask_context_dilate_size: int,
    boundary_band_size: int,
    defect_dilate_size: int,
    frame_border_ignore_size: int,
) -> tuple[np.ndarray, dict[str, int]]:
    domain = gt.copy()
    if mask_context_dilate_size > 1:
        domain = cv2.dilate(domain, _odd_kernel(mask_context_dilate_size), iterations=1)

    cad_boundary = cv2.morphologyEx(gt, cv2.MORPH_GRADIENT, _odd_kernel(3))
    boundary_band = cad_boundary
    if boundary_band_size > 1:
        boundary_band = cv2.dilate(boundary_band, _odd_kernel(boundary_band_size), iterations=1)

    disagreement = (((raw_bright > 0) != (gt > 0)).astype(np.uint8)) * 255
    defect_band = disagreement
    if defect_dilate_size > 1:
        defect_band = cv2.dilate(defect_band, _odd_kernel(defect_dilate_size), iterations=1)

    reliable_mask = domain.copy()
    border_band = _frame_border_mask(gt.shape, frame_border_ignore_size)
    unreliable = (boundary_band > 0) | ((defect_band > 0) & (domain > 0)) | (border_band > 0)
    reliable_mask[unreliable] = 0
    stats = {
        "mask_domain_px": int(np.count_nonzero(domain)),
        "masked_boundary_px": int(np.count_nonzero((boundary_band > 0) & (domain > 0))),
        "masked_disagreement_px": int(np.count_nonzero((defect_band > 0) & (domain > 0))),
        "masked_frame_border_px": int(np.count_nonzero((border_band > 0) & (domain > 0))),
    }
    return reliable_mask, stats


def _make_overlay(gray: np.ndarray, gt: np.ndarray, reliable_mask: np.ndarray) -> np.ndarray:
    base = cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)
    tinted = base.copy()
    tinted[gt > 0] = (40, 220, 40)
    overlay = cv2.addWeighted(base, 0.65, tinted, 0.35, 0.0)
    contours, _hierarchy = cv2.findContours(gt, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    cv2.drawContours(overlay, contours, -1, (0, 255, 255), 2)
    low_conf = (reliable_mask == 0) & (gt > 0)
    overlay[low_conf] = (0, 0, 255)
    return overlay


def extract_cad_reference_from_array(
    image: np.ndarray,
    *,
    min_component_area: int = 2000,
    blur_sigma: float = 2.0,
    open_kernel_size: int = 3,
    close_kernel_size: int = 9,
    polygon_epsilon_ratio: float = 0.004,
    min_polygon_epsilon_px: float = 18.0,
    small_component_area_for_min_epsilon: float = 100000.0,
    small_component_min_epsilon_px: float = 14.0,
    min_rect_fill_ratio: float = 0.82,
    max_rect_aspect_ratio: float = 2.2,
    min_rect_solidity: float = 0.95,
    rectangle_shrink_px: float = 2.0,
    edge_defect_close_size: int = 31,
    small_component_edge_defect_close_size: int = 7,
    mask_context_dilate_size: int = 45,
    boundary_band_size: int = 9,
    defect_dilate_size: int = 9,
    frame_border_ignore_size: int = 9,
) -> CadReferenceResult:
    """Redraw high-confidence bright checkboard regions as a clean reference."""
    gray = _as_gray(image)
    if gray.dtype != np.uint8:
        gray = np.clip(gray, 0, 255).astype(np.uint8)

    blurred = cv2.GaussianBlur(gray, (0, 0), sigmaX=float(blur_sigma))
    threshold_value, raw_bright = cv2.threshold(blurred, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    bright = cv2.morphologyEx(raw_bright, cv2.MORPH_OPEN, _odd_kernel(open_kernel_size))

    rectangles, rectangle_metrics = _component_rectangles(
        bright,
        min_component_area=min_component_area,
        min_rect_fill_ratio=min_rect_fill_ratio,
        max_rect_aspect_ratio=max_rect_aspect_ratio,
        min_rect_solidity=min_rect_solidity,
    )
    gt, vertex_counts = _redraw_rectangles(
        gray.shape,
        rectangles,
        rectangle_shrink_px=rectangle_shrink_px,
    )
    reliable_mask, mask_metrics = _make_reliable_mask(
        gt,
        raw_bright,
        mask_context_dilate_size=mask_context_dilate_size,
        boundary_band_size=boundary_band_size,
        defect_dilate_size=defect_dilate_size,
        frame_border_ignore_size=frame_border_ignore_size,
    )
    overlay = _make_overlay(gray, gt, reliable_mask)
    edge_metrics = _edge_distance_metrics(gt, bright, frame_border_ignore_size=frame_border_ignore_size)

    metrics: dict[str, object] = {
        "source_shape": [int(v) for v in gray.shape],
        "threshold_value": float(threshold_value),
        "component_count": int(len(rectangles)),
        "white_area_px": int(np.count_nonzero(gt)),
        "reliable_area_px": int(np.count_nonzero(reliable_mask)),
        "coverage": float(np.count_nonzero(gt) / gt.size),
        "vertex_counts": vertex_counts,
        "close_kernel_size": int(close_kernel_size),
        "small_component_area_for_min_epsilon": float(small_component_area_for_min_epsilon),
        "small_component_min_epsilon_px": float(small_component_min_epsilon_px),
        "min_rect_fill_ratio": float(min_rect_fill_ratio),
        "max_rect_aspect_ratio": float(max_rect_aspect_ratio),
        "min_rect_solidity": float(min_rect_solidity),
        "rectangle_shrink_px": float(rectangle_shrink_px),
        "edge_defect_close_size": int(edge_defect_close_size),
        "small_component_edge_defect_close_size": int(small_component_edge_defect_close_size),
        "mask_context_dilate_size": int(mask_context_dilate_size),
        "boundary_band_size": int(boundary_band_size),
        "defect_dilate_size": int(defect_dilate_size),
        "frame_border_ignore_size": int(frame_border_ignore_size),
    }
    metrics.update(rectangle_metrics)
    metrics.update(mask_metrics)
    metrics.update(edge_metrics)
    return CadReferenceResult(gt=gt, reliable_mask=reliable_mask, overlay=overlay, metrics=metrics)


def _image_paths(input_dir: Path) -> list[Path]:
    return sorted(p for p in input_dir.iterdir() if p.is_file() and p.suffix.lower() in IMAGE_EXTENSIONS)


def _write_image(path: Path, image: np.ndarray) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    ok, encoded = cv2.imencode(path.suffix, image)
    if not ok:
        raise RuntimeError(f"failed to write image: {path}")
    path.write_bytes(encoded.tobytes())


def build_cad_references(
    input_dir: Path | str,
    output_dir: Path | str,
    *,
    min_component_area: int = 2000,
    blur_sigma: float = 2.0,
    polygon_epsilon_ratio: float = 0.004,
    min_polygon_epsilon_px: float = 18.0,
    small_component_area_for_min_epsilon: float = 100000.0,
    small_component_min_epsilon_px: float = 14.0,
    min_rect_fill_ratio: float = 0.82,
    max_rect_aspect_ratio: float = 2.2,
    min_rect_solidity: float = 0.95,
    rectangle_shrink_px: float = 2.0,
    edge_defect_close_size: int = 31,
    small_component_edge_defect_close_size: int = 7,
    mask_context_dilate_size: int = 45,
    boundary_band_size: int = 9,
    defect_dilate_size: int = 9,
    frame_border_ignore_size: int = 9,
) -> dict[str, object]:
    input_root = Path(input_dir)
    output_root = Path(output_dir)
    paths = _image_paths(input_root)
    if not paths:
        raise FileNotFoundError(f"no supported images found under {input_root}")

    entries: list[dict[str, object]] = []
    failed = 0
    for path in paths:
        gray = cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)
        if gray is None:
            failed += 1
            entries.append({"source": str(path), "status": "failed_read"})
            continue
        result = extract_cad_reference_from_array(
            gray,
            min_component_area=min_component_area,
            blur_sigma=blur_sigma,
            polygon_epsilon_ratio=polygon_epsilon_ratio,
            min_polygon_epsilon_px=min_polygon_epsilon_px,
            small_component_area_for_min_epsilon=small_component_area_for_min_epsilon,
            small_component_min_epsilon_px=small_component_min_epsilon_px,
            min_rect_fill_ratio=min_rect_fill_ratio,
            max_rect_aspect_ratio=max_rect_aspect_ratio,
            min_rect_solidity=min_rect_solidity,
            rectangle_shrink_px=rectangle_shrink_px,
            edge_defect_close_size=edge_defect_close_size,
            small_component_edge_defect_close_size=small_component_edge_defect_close_size,
            mask_context_dilate_size=mask_context_dilate_size,
            boundary_band_size=boundary_band_size,
            defect_dilate_size=defect_dilate_size,
            frame_border_ignore_size=frame_border_ignore_size,
        )
        stem = path.stem
        gt_rel = Path("gt") / f"{stem}_cad_gt.bmp"
        mask_rel = Path("mask") / f"{stem}_reliable_mask.bmp"
        overlay_rel = Path("overlay") / f"{stem}_overlay.png"
        _write_image(output_root / gt_rel, result.gt)
        _write_image(output_root / mask_rel, result.reliable_mask)
        _write_image(output_root / overlay_rel, result.overlay)
        entries.append(
            {
                "source": str(path),
                "status": "ok",
                "gt": str(gt_rel),
                "mask": str(mask_rel),
                "overlay": str(overlay_rel),
                "metrics": result.metrics,
            }
        )

    ok_entries = [entry for entry in entries if entry.get("status") == "ok"]
    edge_p95_values = [
        e["metrics"]["edge_p95_px"] for e in ok_entries if e["metrics"].get("edge_p95_px") is not None
    ]
    edge_within_2px_values = [
        e["metrics"]["edge_within_2px_ratio"]
        for e in ok_entries
        if e["metrics"].get("edge_within_2px_ratio") is not None
    ]
    edge_within_5px_values = [
        e["metrics"]["edge_within_5px_ratio"]
        for e in ok_entries
        if e["metrics"].get("edge_within_5px_ratio") is not None
    ]
    manifest: dict[str, object] = {
        "tool": "cad_reference_from_checkboard",
        "input_dir": str(input_root),
        "output_dir": str(output_root),
        "total_images": len(paths),
        "ok_images": len(ok_entries),
        "failed_images": int(failed),
        "min_component_area": int(min_component_area),
        "blur_sigma": float(blur_sigma),
        "polygon_epsilon_ratio": float(polygon_epsilon_ratio),
        "min_polygon_epsilon_px": float(min_polygon_epsilon_px),
        "small_component_area_for_min_epsilon": float(small_component_area_for_min_epsilon),
        "small_component_min_epsilon_px": float(small_component_min_epsilon_px),
        "min_rect_fill_ratio": float(min_rect_fill_ratio),
        "max_rect_aspect_ratio": float(max_rect_aspect_ratio),
        "min_rect_solidity": float(min_rect_solidity),
        "rectangle_shrink_px": float(rectangle_shrink_px),
        "edge_defect_close_size": int(edge_defect_close_size),
        "small_component_edge_defect_close_size": int(small_component_edge_defect_close_size),
        "mask_context_dilate_size": int(mask_context_dilate_size),
        "boundary_band_size": int(boundary_band_size),
        "defect_dilate_size": int(defect_dilate_size),
        "frame_border_ignore_size": int(frame_border_ignore_size),
        "mean_component_count": float(np.mean([e["metrics"]["component_count"] for e in ok_entries]))
        if ok_entries
        else 0.0,
        "mean_coverage": float(np.mean([e["metrics"]["coverage"] for e in ok_entries])) if ok_entries else 0.0,
        "mean_reliable_area_px": float(np.mean([e["metrics"]["reliable_area_px"] for e in ok_entries]))
        if ok_entries
        else 0.0,
        "mean_edge_p95_px": float(np.mean(edge_p95_values))
        if edge_p95_values
        else None,
        "max_edge_p95_px": float(np.max(edge_p95_values))
        if edge_p95_values
        else None,
        "mean_edge_within_2px_ratio": float(np.mean(edge_within_2px_values))
        if edge_within_2px_values
        else None,
        "mean_edge_within_5px_ratio": float(np.mean(edge_within_5px_values))
        if edge_within_5px_values
        else None,
        "entries": entries,
    }
    output_root.mkdir(parents=True, exist_ok=True)
    (output_root / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build CAD-like checkboard references from real frames.")
    parser.add_argument("--input-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--min-component-area", type=int, default=2000)
    parser.add_argument("--blur-sigma", type=float, default=2.0)
    parser.add_argument("--polygon-epsilon-ratio", type=float, default=0.004)
    parser.add_argument("--min-polygon-epsilon-px", type=float, default=18.0)
    parser.add_argument("--small-component-area-for-min-epsilon", type=float, default=100000.0)
    parser.add_argument("--small-component-min-epsilon-px", type=float, default=14.0)
    parser.add_argument("--min-rect-fill-ratio", type=float, default=0.82)
    parser.add_argument("--max-rect-aspect-ratio", type=float, default=2.2)
    parser.add_argument("--min-rect-solidity", type=float, default=0.95)
    parser.add_argument("--rectangle-shrink-px", type=float, default=2.0)
    parser.add_argument("--edge-defect-close-size", type=int, default=31)
    parser.add_argument("--small-component-edge-defect-close-size", type=int, default=7)
    parser.add_argument("--mask-context-dilate-size", type=int, default=45)
    parser.add_argument("--boundary-band-size", type=int, default=9)
    parser.add_argument("--defect-dilate-size", type=int, default=9)
    parser.add_argument("--frame-border-ignore-size", type=int, default=9)
    args = parser.parse_args(argv)

    manifest = build_cad_references(
        args.input_dir,
        args.output_dir,
        min_component_area=args.min_component_area,
        blur_sigma=args.blur_sigma,
        polygon_epsilon_ratio=args.polygon_epsilon_ratio,
        min_polygon_epsilon_px=args.min_polygon_epsilon_px,
        small_component_area_for_min_epsilon=args.small_component_area_for_min_epsilon,
        small_component_min_epsilon_px=args.small_component_min_epsilon_px,
        min_rect_fill_ratio=args.min_rect_fill_ratio,
        max_rect_aspect_ratio=args.max_rect_aspect_ratio,
        min_rect_solidity=args.min_rect_solidity,
        rectangle_shrink_px=args.rectangle_shrink_px,
        edge_defect_close_size=args.edge_defect_close_size,
        small_component_edge_defect_close_size=args.small_component_edge_defect_close_size,
        mask_context_dilate_size=args.mask_context_dilate_size,
        boundary_band_size=args.boundary_band_size,
        defect_dilate_size=args.defect_dilate_size,
        frame_border_ignore_size=args.frame_border_ignore_size,
    )
    print(
        json.dumps(
            {
                k: manifest[k]
                for k in (
                    "total_images",
                    "ok_images",
                    "failed_images",
                    "mean_component_count",
                    "mean_coverage",
                    "mean_edge_p95_px",
                    "max_edge_p95_px",
                    "mean_edge_within_2px_ratio",
                )
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import cv2
import numpy as np
from skimage.registration import phase_cross_correlation

from displacement_common import (
    list_images,
    parse_crop,
    read_gray_u8,
    summarize_steps,
    to_float01,
    write_csv,
    write_json,
)


@dataclass(frozen=True)
class EdgeTemplate:
    edge: np.ndarray
    distance: np.ndarray
    points_x: np.ndarray
    points_y: np.ndarray
    weights: np.ndarray
    threshold: float
    valid: bool
    message: str = ""

    @property
    def point_count(self) -> int:
        return int(len(self.points_x))


@dataclass(frozen=True)
class MatchResult:
    dx_px: float
    dy_px: float
    score_px: float
    overlap_fraction: float
    score_margin_px: float
    candidate_count: int
    edge_phase_used: bool
    status: str
    message: str


def edge_magnitude(image: np.ndarray, *, blur_sigma: float) -> np.ndarray:
    arr = to_float01(image)
    if blur_sigma > 0:
        arr = cv2.GaussianBlur(arr, (0, 0), blur_sigma)
    grad_x = cv2.Sobel(arr, cv2.CV_32F, 1, 0, ksize=3)
    grad_y = cv2.Sobel(arr, cv2.CV_32F, 0, 1, ksize=3)
    edge = cv2.magnitude(grad_x, grad_y)
    peak = float(edge.max())
    if peak <= 1e-8:
        return np.zeros_like(edge, dtype=np.float32)
    return (edge / peak).astype(np.float32, copy=False)


def _top_weighted_points(
    edge: np.ndarray,
    *,
    threshold: float,
    max_edge_points: int,
    min_edge_points: int,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, str]:
    weights_image = np.maximum(edge - threshold, 0.0)
    ys, xs = np.nonzero(weights_image > 0)
    if len(xs) < min_edge_points:
        positive = edge > 1e-8
        ys, xs = np.nonzero(positive)
        if len(xs) < min_edge_points:
            return (
                np.empty(0, dtype=np.float32),
                np.empty(0, dtype=np.float32),
                np.empty(0, dtype=np.float32),
                "too few edge points",
            )
        values = edge[ys, xs]
    else:
        values = weights_image[ys, xs]

    if len(xs) > max_edge_points:
        order = np.argsort(values)[-max_edge_points:]
        xs = xs[order]
        ys = ys[order]
        values = values[order]

    values = values.astype(np.float32, copy=False)
    total = float(values.sum())
    if total <= 1e-8:
        values = np.ones_like(values, dtype=np.float32)
        total = float(values.sum())
    weights = values / total
    return (
        xs.astype(np.float32, copy=False),
        ys.astype(np.float32, copy=False),
        weights.astype(np.float32, copy=False),
        "",
    )


def build_edge_template(
    image: np.ndarray,
    *,
    blur_sigma: float = 0.8,
    edge_quantile: float = 0.74,
    max_edge_points: int = 8000,
    min_edge_points: int = 30,
) -> EdgeTemplate:
    if not 0.0 <= edge_quantile < 1.0:
        raise ValueError("edge_quantile must be in [0, 1)")
    edge = edge_magnitude(image, blur_sigma=blur_sigma)
    positive = edge[edge > 1e-8]
    if positive.size < min_edge_points:
        empty = np.empty(0, dtype=np.float32)
        return EdgeTemplate(edge, edge, empty, empty, empty, 0.0, False, "too few edge points")

    threshold = float(np.quantile(positive, edge_quantile))
    points_x, points_y, weights, message = _top_weighted_points(
        edge,
        threshold=threshold,
        max_edge_points=max_edge_points,
        min_edge_points=min_edge_points,
    )
    if len(points_x) < min_edge_points:
        empty = np.empty(0, dtype=np.float32)
        return EdgeTemplate(edge, edge, empty, empty, empty, threshold, False, message)

    edge_mask = edge >= threshold
    distance_input = np.where(edge_mask, 0, 255).astype(np.uint8)
    distance = cv2.distanceTransform(distance_input, cv2.DIST_L2, 3).astype(np.float32)
    return EdgeTemplate(edge, distance, points_x, points_y, weights, threshold, True)


def _bilinear_sample(
    image: np.ndarray,
    xs: np.ndarray,
    ys: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    height, width = image.shape[:2]
    mask = (xs >= 0.0) & (ys >= 0.0) & (xs <= width - 1.001) & (ys <= height - 1.001)
    if not np.any(mask):
        return np.empty(0, dtype=np.float32), mask

    x = xs[mask]
    y = ys[mask]
    x0 = np.floor(x).astype(np.int32)
    y0 = np.floor(y).astype(np.int32)
    x1 = np.clip(x0 + 1, 0, width - 1)
    y1 = np.clip(y0 + 1, 0, height - 1)
    wx = x - x0.astype(np.float32)
    wy = y - y0.astype(np.float32)

    v00 = image[y0, x0]
    v10 = image[y0, x1]
    v01 = image[y1, x0]
    v11 = image[y1, x1]
    values = (
        (1.0 - wx) * (1.0 - wy) * v00
        + wx * (1.0 - wy) * v10
        + (1.0 - wx) * wy * v01
        + wx * wy * v11
    )
    return values.astype(np.float32, copy=False), mask


def chamfer_score(
    reference: EdgeTemplate,
    current: EdgeTemplate,
    dx_px: float,
    dy_px: float,
    *,
    bidirectional: bool = True,
) -> tuple[float, float]:
    current_values, forward_mask = _bilinear_sample(
        current.distance,
        reference.points_x + float(dx_px),
        reference.points_y + float(dy_px),
    )
    forward_overlap = float(np.mean(forward_mask)) if len(forward_mask) else 0.0
    if current_values.size == 0:
        return float("inf"), 0.0
    forward_weights = reference.weights[forward_mask]
    forward_weights = forward_weights / max(float(forward_weights.sum()), 1e-8)
    forward_score = float(np.sum(current_values * forward_weights))

    if not bidirectional:
        return forward_score, forward_overlap

    reference_values, reverse_mask = _bilinear_sample(
        reference.distance,
        current.points_x - float(dx_px),
        current.points_y - float(dy_px),
    )
    reverse_overlap = float(np.mean(reverse_mask)) if len(reverse_mask) else 0.0
    if reference_values.size == 0:
        return float("inf"), min(forward_overlap, reverse_overlap)
    reverse_weights = current.weights[reverse_mask]
    reverse_weights = reverse_weights / max(float(reverse_weights.sum()), 1e-8)
    reverse_score = float(np.sum(reference_values * reverse_weights))
    return 0.5 * (forward_score + reverse_score), min(forward_overlap, reverse_overlap)


def _axis_values(center: float, radius: float, step: float) -> np.ndarray:
    if radius < 0:
        raise ValueError("search radius must be non-negative")
    if step <= 0:
        raise ValueError("step must be positive")
    low = float(center) - float(radius)
    high = float(center) + float(radius)
    values = np.arange(np.floor(low), np.ceil(high) + step * 0.5, step, dtype=np.float64)
    values = values[(values >= low - 1e-9) & (values <= high + 1e-9)]
    if values.size == 0:
        values = np.array([float(center)], dtype=np.float64)
    return np.unique(np.round(values, 6))


def _score_grid(
    reference: EdgeTemplate,
    current: EdgeTemplate,
    xs: np.ndarray,
    ys: np.ndarray,
    *,
    bidirectional: bool,
) -> list[tuple[float, float, float, float]]:
    scored: list[tuple[float, float, float, float]] = []
    for dy in ys:
        for dx in xs:
            score, overlap = chamfer_score(
                reference,
                current,
                float(dx),
                float(dy),
                bidirectional=bidirectional,
            )
            scored.append((float(score), float(dx), float(dy), float(overlap)))
    scored.sort(key=lambda item: item[0])
    return scored


def _filter_search_window(
    values: np.ndarray,
    *,
    expected: float,
    search_radius: float,
) -> np.ndarray:
    low = float(expected) - float(search_radius)
    high = float(expected) + float(search_radius)
    filtered = values[(values >= low - 1e-9) & (values <= high + 1e-9)]
    if filtered.size == 0:
        return np.array([float(np.clip(expected, low, high))], dtype=np.float64)
    return filtered


def _edge_phase_shift(
    reference: EdgeTemplate,
    current: EdgeTemplate,
    *,
    upsample_factor: int,
) -> tuple[float, float] | None:
    if upsample_factor <= 0:
        return None
    if reference.edge.shape != current.edge.shape:
        return None
    try:
        shift, _, _ = phase_cross_correlation(
            reference.edge.astype(np.float32, copy=False),
            current.edge.astype(np.float32, copy=False),
            upsample_factor=upsample_factor,
            normalization="phase",
        )
    except Exception:
        return None
    dy_px = -float(shift[0])
    dx_px = -float(shift[1])
    if not np.isfinite(dx_px) or not np.isfinite(dy_px):
        return None
    return dx_px, dy_px


def _inside_search_window(
    dx_px: float,
    dy_px: float,
    *,
    expected_dx_px: float,
    expected_dy_px: float,
    search_radius_px: float,
) -> bool:
    return (
        abs(float(dx_px) - float(expected_dx_px)) <= float(search_radius_px)
        and abs(float(dy_px) - float(expected_dy_px)) <= float(search_radius_px)
    )


def summarize_attempted_steps(rows: list[dict[str, Any]]) -> dict[str, float | int | None]:
    attempted = [row for row in rows if row.get("frame_index") != 0 and "attempted_dx_px" in row]
    if not attempted:
        return {
            "attempted_step_count": 0,
            "attempted_mean_dx_px": None,
            "attempted_std_dx_px": None,
            "attempted_mean_dy_px": None,
            "attempted_std_dy_px": None,
            "attempted_rms_step_px": None,
        }
    dx = np.array([float(row["attempted_dx_px"]) for row in attempted], dtype=np.float64)
    dy = np.array([float(row["attempted_dy_px"]) for row in attempted], dtype=np.float64)
    mag = np.sqrt(dx * dx + dy * dy)
    return {
        "attempted_step_count": int(len(attempted)),
        "attempted_mean_dx_px": float(np.mean(dx)),
        "attempted_std_dx_px": float(np.std(dx, ddof=1)) if len(dx) > 1 else 0.0,
        "attempted_mean_dy_px": float(np.mean(dy)),
        "attempted_std_dy_px": float(np.std(dy, ddof=1)) if len(dy) > 1 else 0.0,
        "attempted_rms_step_px": float(np.sqrt(np.mean(mag * mag))),
    }


def estimate_shift(
    reference: EdgeTemplate,
    current: EdgeTemplate,
    *,
    expected_dx_px: float = 0.0,
    expected_dy_px: float = 0.0,
    search_radius_px: float = 4.0,
    subpixel_step: float = 0.1,
    refinement_radius_px: float = 0.8,
    bidirectional: bool = True,
    edge_phase_refine: bool = True,
    phase_upsample_factor: int = 100,
    phase_score_tolerance_px: float = 0.35,
) -> MatchResult:
    if not reference.valid:
        return MatchResult(0.0, 0.0, float("inf"), 0.0, 0.0, 0, False, "failed", reference.message)
    if not current.valid:
        return MatchResult(0.0, 0.0, float("inf"), 0.0, 0.0, 0, False, "failed", current.message)

    coarse_x = _axis_values(expected_dx_px, search_radius_px, 1.0)
    coarse_y = _axis_values(expected_dy_px, search_radius_px, 1.0)
    coarse = _score_grid(reference, current, coarse_x, coarse_y, bidirectional=bidirectional)
    if not coarse or not np.isfinite(coarse[0][0]):
        return MatchResult(0.0, 0.0, float("inf"), 0.0, 0.0, len(coarse), False, "failed", "no finite match")

    _, best_x, best_y, _ = coarse[0]
    fine_x = _filter_search_window(
        _axis_values(best_x, refinement_radius_px, subpixel_step),
        expected=expected_dx_px,
        search_radius=search_radius_px,
    )
    fine_y = _filter_search_window(
        _axis_values(best_y, refinement_radius_px, subpixel_step),
        expected=expected_dy_px,
        search_radius=search_radius_px,
    )
    fine = _score_grid(reference, current, fine_x, fine_y, bidirectional=bidirectional)
    if not fine or not np.isfinite(fine[0][0]):
        return MatchResult(0.0, 0.0, float("inf"), 0.0, 0.0, len(coarse) + len(fine), False, "failed", "no finite refined match")

    best_score, dx, dy, overlap = fine[0]
    second_score = next((item[0] for item in fine[1:] if np.isfinite(item[0])), best_score)
    candidate_count = int(len(coarse) + len(fine))
    message = ""
    edge_phase_used = False

    if edge_phase_refine:
        phase_shift = _edge_phase_shift(
            reference,
            current,
            upsample_factor=phase_upsample_factor,
        )
        if phase_shift is not None:
            phase_dx, phase_dy = phase_shift
            if _inside_search_window(
                phase_dx,
                phase_dy,
                expected_dx_px=expected_dx_px,
                expected_dy_px=expected_dy_px,
                search_radius_px=search_radius_px,
            ):
                phase_score, phase_overlap = chamfer_score(
                    reference,
                    current,
                    phase_dx,
                    phase_dy,
                    bidirectional=bidirectional,
                )
                candidate_count += 1
                if np.isfinite(phase_score) and phase_score <= best_score + phase_score_tolerance_px:
                    dx = float(phase_dx)
                    dy = float(phase_dy)
                    overlap = float(phase_overlap)
                    second_score = max(second_score, best_score)
                    best_score = float(phase_score)
                    message = "edge-phase refined"
                    edge_phase_used = True

    return MatchResult(
        float(dx),
        float(dy),
        float(best_score),
        float(overlap),
        float(second_score - best_score),
        candidate_count,
        edge_phase_used,
        "ok",
        message,
    )


def measure_sequence(
    input_dir: Path,
    *,
    crop: tuple[int, int, int, int] | None,
    pattern: str = "*",
    expected_dx_px: float = 0.0,
    expected_dy_px: float = 0.0,
    search_radius_px: float = 4.0,
    reference_mode: str = "consecutive",
    blur_sigma: float = 0.8,
    edge_quantile: float = 0.74,
    max_edge_points: int = 8000,
    min_edge_points: int = 30,
    subpixel_step: float = 0.1,
    refinement_radius_px: float = 0.8,
    min_overlap: float = 0.65,
    max_chamfer_px: float = 4.0,
    bidirectional: bool = True,
    edge_phase_refine: bool = True,
    phase_upsample_factor: int = 100,
    phase_score_tolerance_px: float = 0.35,
    require_edge_phase_refine: bool = False,
    min_score_margin_px: float = 0.0,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    if reference_mode not in {"consecutive", "first"}:
        raise ValueError("reference_mode must be consecutive or first")
    files = list_images(Path(input_dir), pattern)
    images = [read_gray_u8(path, crop) for path in files]
    templates = [
        build_edge_template(
            image,
            blur_sigma=blur_sigma,
            edge_quantile=edge_quantile,
            max_edge_points=max_edge_points,
            min_edge_points=min_edge_points,
        )
        for image in images
    ]

    cumulative_dx = 0.0
    cumulative_dy = 0.0
    rows: list[dict[str, Any]] = [
        {
            "frame_index": 0,
            "filename": files[0].name,
            "ref_filename": "",
            "dx_px": 0.0,
            "dy_px": 0.0,
            "attempted_dx_px": 0.0,
            "attempted_dy_px": 0.0,
            "cumulative_dx_px": 0.0,
            "cumulative_dy_px": 0.0,
            "match_score_px": 0.0,
            "overlap_fraction": 1.0 if templates[0].valid else 0.0,
            "score_margin_px": 0.0,
            "candidate_count": 0,
            "edge_phase_used": False,
            "template_point_count": templates[0].point_count,
            "current_point_count": templates[0].point_count,
            "status": "reference",
            "message": templates[0].message,
        }
    ]

    for index in range(1, len(files)):
        ref_index = index - 1 if reference_mode == "consecutive" else 0
        result = estimate_shift(
            templates[ref_index],
            templates[index],
            expected_dx_px=expected_dx_px if reference_mode == "consecutive" else expected_dx_px * index,
            expected_dy_px=expected_dy_px if reference_mode == "consecutive" else expected_dy_px * index,
            search_radius_px=search_radius_px,
            subpixel_step=subpixel_step,
            refinement_radius_px=refinement_radius_px,
            bidirectional=bidirectional,
            edge_phase_refine=edge_phase_refine,
            phase_upsample_factor=phase_upsample_factor,
            phase_score_tolerance_px=phase_score_tolerance_px,
        )
        status = result.status
        message = result.message
        if status == "ok" and result.overlap_fraction < min_overlap:
            status = "failed"
            message = f"overlap below threshold: {result.overlap_fraction:.3f}"
        if status == "ok" and result.score_px > max_chamfer_px:
            status = "failed"
            message = f"chamfer score above threshold: {result.score_px:.3f}"
        if status == "ok" and require_edge_phase_refine and not result.edge_phase_used:
            status = "failed"
            message = "edge-phase refinement was not accepted"
        if (
            status == "ok"
            and not result.edge_phase_used
            and result.score_margin_px < min_score_margin_px
        ):
            status = "failed"
            message = f"ambiguous shape match: margin {result.score_margin_px:.6f}"

        dx = result.dx_px if status == "ok" else 0.0
        dy = result.dy_px if status == "ok" else 0.0
        attempted_dx = result.dx_px
        attempted_dy = result.dy_px
        if status == "ok":
            if reference_mode == "first":
                cumulative_dx = dx
                cumulative_dy = dy
            else:
                cumulative_dx += dx
                cumulative_dy += dy

        rows.append(
            {
                "frame_index": index,
                "filename": files[index].name,
                "ref_filename": files[ref_index].name,
                "dx_px": dx,
                "dy_px": dy,
                "attempted_dx_px": attempted_dx,
                "attempted_dy_px": attempted_dy,
                "cumulative_dx_px": cumulative_dx,
                "cumulative_dy_px": cumulative_dy,
                "match_score_px": result.score_px,
                "overlap_fraction": result.overlap_fraction,
                "score_margin_px": result.score_margin_px,
                "candidate_count": result.candidate_count,
                "edge_phase_used": result.edge_phase_used,
                "template_point_count": templates[ref_index].point_count,
                "current_point_count": templates[index].point_count,
                "status": status,
                "message": message,
            }
        )

    summary: dict[str, Any] = {
        "algorithm": "shape_aware_edge_chamfer_anchor",
        "input_dir": str(input_dir),
        "image_count": len(files),
        "crop": crop,
        "pattern": pattern,
        "expected_dx_px": expected_dx_px,
        "expected_dy_px": expected_dy_px,
        "search_radius_px": search_radius_px,
        "reference_mode": reference_mode,
        "blur_sigma": blur_sigma,
        "edge_quantile": edge_quantile,
        "max_edge_points": max_edge_points,
        "min_edge_points": min_edge_points,
        "subpixel_step": subpixel_step,
        "refinement_radius_px": refinement_radius_px,
        "min_overlap": min_overlap,
        "max_chamfer_px": max_chamfer_px,
        "bidirectional": bidirectional,
        "edge_phase_refine": edge_phase_refine,
        "phase_upsample_factor": phase_upsample_factor,
        "phase_score_tolerance_px": phase_score_tolerance_px,
        "require_edge_phase_refine": require_edge_phase_refine,
        "min_score_margin_px": min_score_margin_px,
        "failed_step_count": sum(1 for row in rows if row["status"] == "failed"),
    }
    summary.update(summarize_steps(rows))
    summary.update(summarize_attempted_steps(rows))
    return rows, summary


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Measure displacement with shape-aware edge/chamfer anchor matching."
    )
    parser.add_argument("--input", required=True, help="Folder containing ordered images.")
    parser.add_argument("--output-csv", required=True, help="CSV output path.")
    parser.add_argument("--output-json", help="Optional summary JSON output path.")
    parser.add_argument("--pattern", default="*", help="Input image glob.")
    parser.add_argument("--crop", help="Optional ROI as x,y,width,height.")
    parser.add_argument("--expected-dx-px", type=float, default=0.0)
    parser.add_argument("--expected-dy-px", type=float, default=0.0)
    parser.add_argument("--search-radius-px", type=float, default=4.0)
    parser.add_argument("--reference-mode", choices=["consecutive", "first"], default="consecutive")
    parser.add_argument("--blur-sigma", type=float, default=0.8)
    parser.add_argument("--edge-quantile", type=float, default=0.74)
    parser.add_argument("--max-edge-points", type=int, default=8000)
    parser.add_argument("--min-edge-points", type=int, default=30)
    parser.add_argument("--subpixel-step", type=float, default=0.1)
    parser.add_argument("--refinement-radius-px", type=float, default=0.8)
    parser.add_argument("--min-overlap", type=float, default=0.65)
    parser.add_argument("--max-chamfer-px", type=float, default=4.0)
    parser.add_argument("--one-way", action="store_true", help="Disable bidirectional chamfer check.")
    parser.add_argument("--no-edge-phase-refine", action="store_true", help="Disable boundary-only phase refinement.")
    parser.add_argument("--phase-upsample-factor", type=int, default=100)
    parser.add_argument("--phase-score-tolerance-px", type=float, default=0.35)
    parser.add_argument("--require-edge-phase-refine", action="store_true")
    parser.add_argument("--min-score-margin-px", type=float, default=0.0)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    rows, summary = measure_sequence(
        Path(args.input),
        crop=parse_crop(args.crop),
        pattern=args.pattern,
        expected_dx_px=args.expected_dx_px,
        expected_dy_px=args.expected_dy_px,
        search_radius_px=args.search_radius_px,
        reference_mode=args.reference_mode,
        blur_sigma=args.blur_sigma,
        edge_quantile=args.edge_quantile,
        max_edge_points=args.max_edge_points,
        min_edge_points=args.min_edge_points,
        subpixel_step=args.subpixel_step,
        refinement_radius_px=args.refinement_radius_px,
        min_overlap=args.min_overlap,
        max_chamfer_px=args.max_chamfer_px,
        bidirectional=not args.one_way,
        edge_phase_refine=not args.no_edge_phase_refine,
        phase_upsample_factor=args.phase_upsample_factor,
        phase_score_tolerance_px=args.phase_score_tolerance_px,
        require_edge_phase_refine=args.require_edge_phase_refine,
        min_score_margin_px=args.min_score_margin_px,
    )
    fields = [
        "frame_index",
        "filename",
        "ref_filename",
        "dx_px",
        "dy_px",
        "attempted_dx_px",
        "attempted_dy_px",
        "cumulative_dx_px",
        "cumulative_dy_px",
        "match_score_px",
        "overlap_fraction",
        "score_margin_px",
        "candidate_count",
        "edge_phase_used",
        "template_point_count",
        "current_point_count",
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

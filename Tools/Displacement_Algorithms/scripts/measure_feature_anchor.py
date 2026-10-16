from __future__ import annotations

import argparse
from pathlib import Path

import cv2
import numpy as np

from displacement_common import (
    list_images,
    parse_crop,
    read_gray_u8,
    summarize_steps,
    to_float01,
    write_csv,
    write_json,
)


def checkerboard_size(value: str) -> tuple[int, int]:
    parts = value.lower().replace(",", "x").split("x")
    if len(parts) != 2:
        raise ValueError("--checkerboard-size must look like 5x5")
    cols, rows = int(parts[0]), int(parts[1])
    if cols <= 1 or rows <= 1:
        raise ValueError("Checkerboard inner-corner counts must be greater than 1")
    return cols, rows


def track_corners(
    prev: np.ndarray,
    curr: np.ndarray,
    max_corners: int,
    quality_level: float,
    min_distance: float,
    lk_window: int,
) -> tuple[float, float, int, float, float, str]:
    prev_float = to_float01(prev)
    points = cv2.goodFeaturesToTrack(
        prev_float,
        maxCorners=max_corners,
        qualityLevel=quality_level,
        minDistance=min_distance,
        blockSize=5,
        useHarrisDetector=False,
    )
    if points is None or len(points) < 4:
        return 0.0, 0.0, 0, 0.0, 0.0, "not enough corners"

    next_points, status, _ = cv2.calcOpticalFlowPyrLK(
        prev,
        curr,
        points,
        None,
        winSize=(lk_window, lk_window),
        maxLevel=3,
        criteria=(cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 30, 0.01),
    )
    if next_points is None or status is None:
        return 0.0, 0.0, 0, 0.0, 0.0, "tracking failed"

    good = status.reshape(-1) == 1
    p0 = points.reshape(-1, 2)[good]
    p1 = next_points.reshape(-1, 2)[good]
    if len(p0) < 4:
        return 0.0, 0.0, int(len(p0)), 0.0, 0.0, "too few tracked corners"

    displacement = p1 - p0
    dx = displacement[:, 0]
    dy = displacement[:, 1]
    return (
        float(np.median(dx)),
        float(np.median(dy)),
        int(len(dx)),
        float(np.std(dx, ddof=1)) if len(dx) > 1 else 0.0,
        float(np.std(dy, ddof=1)) if len(dy) > 1 else 0.0,
        "",
    )


def detect_circle_center(
    image: np.ndarray,
    min_radius: int,
    max_radius: int,
    previous: tuple[float, float] | None = None,
) -> tuple[float, float, int, str]:
    blurred = cv2.medianBlur(image, 5)
    height, width = blurred.shape[:2]
    if min_radius <= 0:
        min_radius = max(3, min(height, width) // 30)
    if max_radius <= 0:
        max_radius = max(min_radius + 1, min(height, width) // 2)

    circles = cv2.HoughCircles(
        blurred,
        cv2.HOUGH_GRADIENT,
        dp=1.2,
        minDist=max(20, min(height, width) // 4),
        param1=80,
        param2=24,
        minRadius=min_radius,
        maxRadius=max_radius,
    )
    if circles is None:
        return 0.0, 0.0, 0, "circle not found"
    candidates = circles[0].astype(float)
    if previous is not None:
        px, py = previous
        distances = (candidates[:, 0] - px) ** 2 + (candidates[:, 1] - py) ** 2
        circle = candidates[int(np.argmin(distances))]
    else:
        circle = candidates[int(np.argmax(candidates[:, 2]))]
    return float(circle[0]), float(circle[1]), 1, ""


def detect_checkerboard_anchor(
    image: np.ndarray,
    size: tuple[int, int],
) -> tuple[float, float, int, str]:
    found, corners = cv2.findChessboardCorners(image, size)
    if not found or corners is None:
        return 0.0, 0.0, 0, "checkerboard not found"
    refined = cv2.cornerSubPix(
        image,
        corners,
        winSize=(7, 7),
        zeroZone=(-1, -1),
        criteria=(cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 30, 0.01),
    )
    points = refined.reshape(-1, 2)
    center = np.mean(points, axis=0)
    return float(center[0]), float(center[1]), int(len(points)), ""


def measure(args: argparse.Namespace) -> tuple[list[dict[str, object]], dict[str, object]]:
    input_dir = Path(args.input)
    crop = parse_crop(args.crop)
    files = list_images(input_dir, args.pattern)
    cb_size = checkerboard_size(args.checkerboard_size)

    prev = read_gray_u8(files[0], crop)
    cumulative_dx = 0.0
    cumulative_dy = 0.0
    rows: list[dict[str, object]] = [
        {
            "frame_index": 0,
            "filename": files[0].name,
            "ref_filename": "",
            "method": args.method,
            "dx_px": 0.0,
            "dy_px": 0.0,
            "cumulative_dx_px": 0.0,
            "cumulative_dy_px": 0.0,
            "feature_count": 0,
            "spread_x_px": 0.0,
            "spread_y_px": 0.0,
            "status": "reference",
            "message": "",
        }
    ]

    prev_anchor: tuple[float, float] | None = None
    if args.method == "circle":
        cx, cy, count, message = detect_circle_center(
        prev, args.circle_min_radius, args.circle_max_radius
        )
        if count == 0:
            raise ValueError(f"Cannot find reference circle in {files[0]}: {message}")
        prev_anchor = (cx, cy)
    elif args.method == "checkerboard":
        cx, cy, count, message = detect_checkerboard_anchor(prev, cb_size)
        if count == 0:
            raise ValueError(f"Cannot find reference checkerboard in {files[0]}: {message}")
        prev_anchor = (cx, cy)

    for index, path in enumerate(files[1:], start=1):
        curr = read_gray_u8(path, crop)
        dx = dy = spread_x = spread_y = 0.0
        count = 0
        status = "ok"
        message = ""

        if args.method == "corners":
            dx, dy, count, spread_x, spread_y, message = track_corners(
                prev,
                curr,
                args.max_corners,
                args.quality_level,
                args.min_distance,
                args.lk_window,
            )
            if count < 4:
                status = "failed"
        elif args.method == "circle":
            assert prev_anchor is not None
            cx, cy, count, message = detect_circle_center(
                curr, args.circle_min_radius, args.circle_max_radius, previous=prev_anchor
            )
            if count == 0:
                status = "failed"
            else:
                dx = cx - prev_anchor[0]
                dy = cy - prev_anchor[1]
                prev_anchor = (cx, cy)
        elif args.method == "checkerboard":
            assert prev_anchor is not None
            cx, cy, count, message = detect_checkerboard_anchor(curr, cb_size)
            if count == 0:
                status = "failed"
            else:
                dx = cx - prev_anchor[0]
                dy = cy - prev_anchor[1]
                prev_anchor = (cx, cy)
        else:
            raise ValueError(f"Unsupported method: {args.method}")

        if status == "ok":
            cumulative_dx += dx
            cumulative_dy += dy
        rows.append(
            {
                "frame_index": index,
                "filename": path.name,
                "ref_filename": files[index - 1].name,
                "method": args.method,
                "dx_px": dx,
                "dy_px": dy,
                "cumulative_dx_px": cumulative_dx,
                "cumulative_dy_px": cumulative_dy,
                "feature_count": count,
                "spread_x_px": spread_x,
                "spread_y_px": spread_y,
                "status": status,
                "message": message,
            }
        )
        prev = curr

    summary: dict[str, object] = {
        "algorithm": "feature_corner_geometry",
        "method": args.method,
        "input_dir": str(input_dir),
        "image_count": len(files),
        "crop": crop,
        "failed_step_count": sum(1 for row in rows if row.get("status") == "failed"),
    }
    summary.update(summarize_steps(rows))
    return rows, summary


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Measure image displacement with open feature/corner anchor methods."
    )
    parser.add_argument("--input", required=True, help="Folder containing ordered images.")
    parser.add_argument("--output-csv", required=True, help="CSV output path.")
    parser.add_argument("--output-json", help="Optional summary JSON output path.")
    parser.add_argument("--pattern", default="*", help="Input file glob pattern.")
    parser.add_argument("--crop", help="Optional ROI crop as x,y,width,height.")
    parser.add_argument(
        "--method",
        choices=["corners", "circle", "checkerboard"],
        default="corners",
        help="Anchor method: tracked corners, circle center, or checkerboard center.",
    )
    parser.add_argument("--max-corners", type=int, default=300)
    parser.add_argument("--quality-level", type=float, default=0.01)
    parser.add_argument("--min-distance", type=float, default=5.0)
    parser.add_argument("--lk-window", type=int, default=31)
    parser.add_argument("--checkerboard-size", default="5x5")
    parser.add_argument("--circle-min-radius", type=int, default=0)
    parser.add_argument("--circle-max-radius", type=int, default=0)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    rows, summary = measure(args)
    fields = [
        "frame_index",
        "filename",
        "ref_filename",
        "method",
        "dx_px",
        "dy_px",
        "cumulative_dx_px",
        "cumulative_dy_px",
        "feature_count",
        "spread_x_px",
        "spread_y_px",
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

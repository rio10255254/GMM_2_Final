from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable

import numpy as np
from PIL import Image
from scipy import ndimage


@dataclass(frozen=True)
class PositionRecord:
    position_index: int
    row: int
    col: int
    frames: tuple[Path, ...]


def old_standard_positions(grid_rows: int, grid_cols: int) -> list[int]:
    """Return the old L0 nine-point pattern for a row-major grid."""
    mid_row = (grid_rows + 1) // 2
    mid_col = (grid_cols + 1) // 2
    rows = [1, mid_row, grid_rows]
    cols = [1, mid_col, grid_cols]
    return [(row - 1) * grid_cols + col for row in rows for col in cols]


def split_position_repeats(
    files: Iterable[Path],
    *,
    grid_rows: int,
    grid_cols: int,
    repeats_per_position: int,
) -> list[PositionRecord]:
    paths = tuple(files)
    expected = grid_rows * grid_cols * repeats_per_position
    if len(paths) != expected:
        raise ValueError(
            f"Expected {expected} files for {grid_rows}x{grid_cols} with "
            f"{repeats_per_position} repeats, got {len(paths)}"
        )

    records: list[PositionRecord] = []
    for zero_based_pos in range(grid_rows * grid_cols):
        start = zero_based_pos * repeats_per_position
        row = zero_based_pos // grid_cols + 1
        col = zero_based_pos % grid_cols + 1
        records.append(
            PositionRecord(
                position_index=zero_based_pos + 1,
                row=row,
                col=col,
                frames=tuple(paths[start : start + repeats_per_position]),
            )
        )
    return records


def _as_gray_array(image_or_array: Image.Image | np.ndarray) -> np.ndarray:
    if isinstance(image_or_array, Image.Image):
        image_or_array = image_or_array.convert("L")
        return np.asarray(image_or_array)
    array = np.asarray(image_or_array)
    if array.ndim != 2:
        raise ValueError(f"Expected a grayscale image, got shape {array.shape}")
    return array


def _largest_component(mask: np.ndarray) -> np.ndarray:
    labels, count = ndimage.label(mask)
    if count == 0:
        raise ValueError("No foreground component found")
    sizes = ndimage.sum(mask, labels, index=np.arange(1, count + 1))
    largest_label = int(np.argmax(sizes) + 1)
    return labels == largest_label


def circle_region_from_gt(gt_image: Image.Image | np.ndarray) -> np.ndarray:
    gt = _as_gray_array(gt_image)
    threshold = (float(gt.min()) + float(gt.max())) / 2.0
    bright = gt > threshold
    main = _largest_component(bright)
    return ndimage.binary_fill_holes(main)


def make_circle_only_gt(gt_image: Image.Image | np.ndarray) -> np.ndarray:
    gt = _as_gray_array(gt_image)
    circle = circle_region_from_gt(gt)
    threshold = (float(gt.min()) + float(gt.max())) / 2.0
    foreground = gt[gt > threshold]
    background = gt[gt <= threshold]
    circle_value = int(np.median(foreground)) if foreground.size else int(gt.max())
    background_value = int(np.median(background)) if background.size else int(gt.min())
    return np.where(circle, circle_value, background_value).astype(np.uint8)


def build_circle_edge_mask(gt_image: Image.Image | np.ndarray, edge_width: int = 6) -> np.ndarray:
    if edge_width < 1:
        raise ValueError("edge_width must be >= 1")
    circle = circle_region_from_gt(gt_image)
    dilated = ndimage.binary_dilation(circle, iterations=edge_width)
    eroded = ndimage.binary_erosion(circle, iterations=edge_width)
    return dilated & ~eroded


def build_inner_block_mask(gt_image: Image.Image | np.ndarray, dilation: int = 35) -> np.ndarray:
    gt = _as_gray_array(gt_image)
    circle = circle_region_from_gt(gt)
    threshold = (float(gt.min()) + float(gt.max())) / 2.0
    holes = circle & (gt <= threshold)
    if not np.any(holes):
        return holes

    ys, xs = np.where(holes)
    y0 = max(int(ys.min()) - dilation, 0)
    y1 = min(int(ys.max()) + dilation + 1, gt.shape[0])
    x0 = max(int(xs.min()) - dilation, 0)
    x1 = min(int(xs.max()) + dilation + 1, gt.shape[1])
    mask = np.zeros_like(holes, dtype=bool)
    mask[y0:y1, x0:x1] = True
    return mask & circle


def fill_inner_blocks(
    image: Image.Image | np.ndarray,
    *,
    gt_image: Image.Image | np.ndarray,
    dilation: int = 80,
) -> np.ndarray:
    arr = _as_gray_array(image).astype(np.uint8, copy=True)
    circle = circle_region_from_gt(gt_image)
    block_mask = build_inner_block_mask(gt_image, dilation=dilation)
    fill_source = circle & ~block_mask
    fill_value = int(np.median(arr[fill_source])) if np.any(fill_source) else int(np.median(arr))
    arr[block_mask] = fill_value
    return arr


def _read_gray(path: Path) -> np.ndarray:
    with Image.open(path) as img:
        return np.asarray(img.convert("L"))


def _save_gray(path: Path, image: np.ndarray) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(np.asarray(image, dtype=np.uint8), mode="L").save(path)


def detect_inner_disk_candidates(image: np.ndarray, *, scale: int = 8) -> list[dict]:
    import cv2

    if scale < 1:
        raise ValueError("scale must be >= 1")
    height, width = image.shape
    small = cv2.resize(
        image,
        (max(width // scale, 1), max(height // scale, 1)),
        interpolation=cv2.INTER_AREA,
    )
    blurred = cv2.GaussianBlur(small, (5, 5), 0)
    _, mask = cv2.threshold(blurred, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    count, _labels, stats, centroids = cv2.connectedComponentsWithStats(mask, 8)

    candidates: list[dict] = []
    for label in range(1, count):
        x, y, w, h, area = stats[label]
        aspect = w / h if h else 0.0
        if 45 <= w <= 145 and 45 <= h <= 145 and 0.65 <= aspect <= 1.55 and area >= 1200:
            cx, cy = centroids[label]
            candidates.append(
                {
                    "center": (float(cx * scale), float(cy * scale)),
                    "bbox": (
                        int(x * scale),
                        int(y * scale),
                        int(w * scale),
                        int(h * scale),
                    ),
                    "area": int(area),
                }
            )
    return candidates


def _choose_corner_candidate(candidates: list[dict], corner: str) -> tuple[float, float]:
    if not candidates:
        raise ValueError(f"No disk candidates for corner {corner}")

    def center(candidate: dict) -> tuple[float, float]:
        return candidate["center"]

    if corner == "top_left":
        chosen = min(candidates, key=lambda c: center(c)[0] + center(c)[1])
    elif corner == "top_right":
        chosen = max(candidates, key=lambda c: center(c)[0] - center(c)[1])
    elif corner == "bottom_left":
        chosen = max(candidates, key=lambda c: center(c)[1] - center(c)[0])
    elif corner == "bottom_right":
        chosen = max(candidates, key=lambda c: center(c)[0] + center(c)[1])
    else:
        raise ValueError(f"Unknown corner: {corner}")
    return chosen["center"]


def _interpolate_grid_center(
    row: int,
    col: int,
    *,
    grid_rows: int,
    grid_cols: int,
    corners: dict[str, tuple[float, float]],
) -> tuple[float, float]:
    u = 0.0 if grid_cols == 1 else (col - 1) / (grid_cols - 1)
    v = 0.0 if grid_rows == 1 else (row - 1) / (grid_rows - 1)
    top = np.array(corners["top_left"]) * (1.0 - u) + np.array(corners["top_right"]) * u
    bottom = np.array(corners["bottom_left"]) * (1.0 - u) + np.array(corners["bottom_right"]) * u
    point = top * (1.0 - v) + bottom * v
    return float(point[0]), float(point[1])


def detect_round_grid_centers(
    records: list[PositionRecord],
    *,
    grid_rows: int,
    grid_cols: int,
    frame_index: int = 0,
) -> dict[int, dict]:
    by_position = {record.position_index: record for record in records}
    corner_positions = {
        "top_left": 1,
        "top_right": grid_cols,
        "bottom_left": (grid_rows - 1) * grid_cols + 1,
        "bottom_right": grid_rows * grid_cols,
    }
    corners: dict[str, tuple[float, float]] = {}
    for name, position_index in corner_positions.items():
        image = _read_gray(by_position[position_index].frames[frame_index])
        candidates = detect_inner_disk_candidates(image)
        corners[name] = _choose_corner_candidate(candidates, name)

    centers: dict[int, dict] = {}
    for record in records:
        image = _read_gray(record.frames[frame_index])
        candidates = detect_inner_disk_candidates(image)
        expected = _interpolate_grid_center(
            record.row,
            record.col,
            grid_rows=grid_rows,
            grid_cols=grid_cols,
            corners=corners,
        )
        if candidates:
            chosen = min(
                candidates,
                key=lambda c: (c["center"][0] - expected[0]) ** 2
                + (c["center"][1] - expected[1]) ** 2,
            )
            center = chosen["center"]
            distance = float(
                np.hypot(center[0] - expected[0], center[1] - expected[1])
            )
            detected = True
        else:
            center = expected
            distance = None
            detected = False
        centers[record.position_index] = {
            "center": center,
            "expected_center": expected,
            "distance_from_expected": distance,
            "detected": detected,
        }
    return centers


def crop_centered(
    image: Image.Image | np.ndarray,
    center: tuple[float, float],
    *,
    crop_size: int = 901,
    pad_value: int = 20,
) -> np.ndarray:
    arr = _as_gray_array(image)
    if crop_size <= 0:
        raise ValueError("crop_size must be positive")
    cx, cy = center
    x0 = int(round(cx - (crop_size - 1) / 2))
    y0 = int(round(cy - (crop_size - 1) / 2))
    x1 = x0 + crop_size
    y1 = y0 + crop_size

    output = np.full((crop_size, crop_size), pad_value, dtype=arr.dtype)
    src_x0 = max(x0, 0)
    src_y0 = max(y0, 0)
    src_x1 = min(x1, arr.shape[1])
    src_y1 = min(y1, arr.shape[0])
    dst_x0 = src_x0 - x0
    dst_y0 = src_y0 - y0
    output[
        dst_y0 : dst_y0 + (src_y1 - src_y0),
        dst_x0 : dst_x0 + (src_x1 - src_x0),
    ] = arr[src_y0:src_y1, src_x0:src_x1]
    return output


def prepare_round_inputs(
    *,
    round_dir: Path,
    output_dir: Path,
    gt_path: Path,
    grid_rows: int = 11,
    grid_cols: int = 11,
    repeats_per_position: int = 2,
    frame_number: int = 1,
    crop_size: int = 901,
) -> dict:
    files = sorted(round_dir.glob("VisionTop_*.bmp"))
    records = split_position_repeats(
        files,
        grid_rows=grid_rows,
        grid_cols=grid_cols,
        repeats_per_position=repeats_per_position,
    )
    if frame_number < 1 or frame_number > repeats_per_position:
        raise ValueError(f"frame_number must be in 1..{repeats_per_position}")
    frame_index = frame_number - 1

    output_dir.mkdir(parents=True, exist_ok=True)
    gt = _read_gray(gt_path)
    gt_dir = output_dir / "GT"
    _save_gray(gt_dir / "GT_901_original_with_blocks.bmp", gt)
    _save_gray(gt_dir / "GT_901_with_Block_proc.bmp", make_circle_only_gt(gt))
    _save_gray(gt_dir / "circle_edge_mask.bmp", build_circle_edge_mask(gt).astype(np.uint8) * 255)

    centers = detect_round_grid_centers(
        records,
        grid_rows=grid_rows,
        grid_cols=grid_cols,
        frame_index=frame_index,
    )

    prepared = []
    for record in records:
        source_path = record.frames[frame_index]
        image = _read_gray(source_path)
        center = tuple(centers[record.position_index]["center"])
        crop = crop_centered(image, center, crop_size=crop_size)
        crop = fill_inner_blocks(crop, gt_image=gt)
        output_name = f"VisionTop_{round_dir.name}_{record.position_index:03d}.bmp"
        output_path = output_dir / output_name
        _save_gray(output_path, crop)
        prepared.append(
            {
                "position_index": record.position_index,
                "row": record.row,
                "col": record.col,
                "source_frame": str(source_path),
                "output_file": str(output_path),
                **centers[record.position_index],
            }
        )

    manifest = {
        "round_dir": str(round_dir),
        "output_dir": str(output_dir),
        "gt_path": str(gt_path),
        "grid_rows": grid_rows,
        "grid_cols": grid_cols,
        "repeats_per_position": repeats_per_position,
        "frame_number_used": frame_number,
        "crop_size": crop_size,
        "old_standard_positions": old_standard_positions(grid_rows, grid_cols),
        "prepared_images": prepared,
    }
    (output_dir / "prep_manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return manifest


def _json_default(value):
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, np.generic):
        return value.item()
    if dataclass_is_instance(value):
        return asdict(value)
    raise TypeError(f"Cannot serialize {type(value)!r}")


def dataclass_is_instance(value) -> bool:
    return hasattr(value, "__dataclass_fields__")


def main() -> None:
    parser = argparse.ArgumentParser(description="Prepare Circle_Round data for new L0 runs.")
    parser.add_argument("--round-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--gt-path", type=Path, required=True)
    parser.add_argument("--frame-number", type=int, default=1)
    parser.add_argument("--grid-rows", type=int, default=11)
    parser.add_argument("--grid-cols", type=int, default=11)
    parser.add_argument("--repeats-per-position", type=int, default=2)
    parser.add_argument("--crop-size", type=int, default=901)
    args = parser.parse_args()

    manifest = prepare_round_inputs(
        round_dir=args.round_dir,
        output_dir=args.output_dir,
        gt_path=args.gt_path,
        grid_rows=args.grid_rows,
        grid_cols=args.grid_cols,
        repeats_per_position=args.repeats_per_position,
        frame_number=args.frame_number,
        crop_size=args.crop_size,
    )
    print(json.dumps(manifest, ensure_ascii=False, default=_json_default)[:1000])


if __name__ == "__main__":
    main()

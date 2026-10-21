from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Iterable

import numpy as np


SCRIPT_DIR = Path(__file__).resolve().parent
LAB_ROOT = Path(__file__).resolve().parents[3]
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from prepare_r62_selfshift_motion_dataset import (  # noqa: E402
    clone_base_package,
    image_files,
    write_selfshift_pair,
)
from prepare_r62_target_motion_dataset import MOTION_SPECS  # noqa: E402
from prepare_r62_target_sample_dataset import _read_gray  # noqa: E402


OUTPUT_ROOT = LAB_ROOT / "Training_Data" / "r62_target_sample_boost" / "hs100mg_basler"
SOURCE_PACKAGE = OUTPUT_ROOT / "r62_target_sample_boost_v4_motion_clean"
PACKAGE_NAME = "r62_target_sample_boost_v5_gmf_roi_motion_clean"
PACKAGE_DIR = OUTPUT_ROOT / PACKAGE_NAME
GMF_ROI_STAGE = "stage_40_r62_gmf_roi_selfshift_motion_pair"
GMF_ROI_ROLE = "target_real_gmf_roi_selfshift_motion_pair"


DEFAULT_GMF_ROI_CROPS: dict[tuple[str, str], list[tuple[int, int, int]]] = {
    ("20260702_100MG", "x_1um"): [(1080, 40, 512)],
    ("20260702_100MG", "x_0p5um"): [(1080, 40, 512)],
    ("20260704_20x_5x", "20x_1um"): [(650, 150, 512)],
    ("20260704_20x_5x", "20x_0p5um"): [(650, 150, 512)],
    ("20260704_20x_5x", "5x_1um"): [(650, 150, 512)],
    ("20260704_20x_5x", "5x_0p5um"): [(650, 150, 512)],
}


def gmf_roi_crops_for_spec(
    spec: dict[str, object],
    *,
    crop_map: dict[tuple[str, str], list[tuple[int, int, int]]] | None = None,
) -> list[tuple[int, int, int]]:
    crop_map = crop_map or DEFAULT_GMF_ROI_CROPS
    key = (str(spec["dataset"]), str(spec["sequence"]))
    if key not in crop_map:
        raise KeyError(f"no GMF ROI crop configured for {key[0]}/{key[1]}")
    return list(crop_map[key])


def _select_frame_pairs(raw_dir: Path, teacher_dir: Path, max_frames: int) -> list[tuple[Path, Path]]:
    raw_paths = image_files(Path(raw_dir))
    teacher_by_name = {path.name: path for path in image_files(Path(teacher_dir))}
    pairs = [(path, teacher_by_name[path.name]) for path in raw_paths if path.name in teacher_by_name]
    if max_frames > 0 and len(pairs) > max_frames:
        positions = np.linspace(0, len(pairs) - 1, int(max_frames), dtype=int)
        pairs = [pairs[int(pos)] for pos in positions]
    return pairs


def _checked_crop(image: Any, *, x: int, y: int, crop_size: int, image_name: str) -> Any:
    if x < 0 or y < 0 or crop_size <= 0:
        raise ValueError(f"invalid crop for {image_name}: x={x} y={y} size={crop_size}")
    h, w = image.shape[:2]
    if x + crop_size > w or y + crop_size > h:
        raise ValueError(f"crop exceeds image bounds for {image_name}: image={w}x{h}, crop=({x},{y},{crop_size})")
    return image[y : y + crop_size, x : x + crop_size]


def _mark_gmf_roi_record(record: dict[str, object]) -> dict[str, object]:
    out = dict(record)
    out["role"] = GMF_ROI_ROLE
    out["domain"] = "real_target_texture_exact_selfshift_motion_at_gmf_validation_roi"
    out["gmf_roi_training"] = True
    return out


def build_gmf_roi_records(
    package_dir: Path,
    *,
    specs: Iterable[dict[str, object]] = MOTION_SPECS,
    crop_map: dict[tuple[str, str], list[tuple[int, int, int]]] | None = None,
    max_frames_per_sequence: int = 30,
) -> tuple[list[dict[str, object]], dict[str, object]]:
    records: list[dict[str, object]] = []
    summary: dict[str, object] = {}
    sequence_index = 0
    for spec in specs:
        dataset = str(spec["dataset"])
        sequence = str(spec["sequence"])
        frame_pairs = _select_frame_pairs(Path(spec["raw_dir"]), Path(spec["teacher_dir"]), int(max_frames_per_sequence))
        crops = gmf_roi_crops_for_spec(spec, crop_map=crop_map)
        written_pairs = 0
        for frame_index, (raw_path, teacher_path) in enumerate(frame_pairs):
            raw = _read_gray(raw_path)
            teacher = _read_gray(teacher_path)
            for patch_index, (x, y, crop_size) in enumerate(crops):
                raw_crop = _checked_crop(raw, x=int(x), y=int(y), crop_size=int(crop_size), image_name=raw_path.name)
                teacher_crop = _checked_crop(
                    teacher,
                    x=int(x),
                    y=int(y),
                    crop_size=int(crop_size),
                    image_name=teacher_path.name,
                )
                pair_records = write_selfshift_pair(
                    package_dir=Path(package_dir),
                    stage=GMF_ROI_STAGE,
                    dataset=dataset,
                    sequence=sequence,
                    raw_crop=raw_crop,
                    teacher_crop=teacher_crop,
                    dx=float(spec["target_dx_px"]),
                    dy=float(spec["target_dy_px"]),
                    sequence_index=sequence_index,
                    patch_index=patch_index,
                    source_frame_name=raw_path.name,
                    crop_x=int(x),
                    crop_y=int(y),
                    feature_family=f"{spec['feature_family']}_gmf_roi",
                )
                records.extend(_mark_gmf_roi_record(record) for record in pair_records)
                sequence_index += 1
                written_pairs += 1
        summary[f"{dataset}/{sequence}"] = {
            "matched_frames_used": len(frame_pairs),
            "configured_roi_count": len(crops),
            "gmf_roi_pairs": written_pairs,
            "gmf_roi_frames": written_pairs * 2,
            "crops": [{"x": int(x), "y": int(y), "crop_size": int(crop)} for x, y, crop in crops],
            "target_dx_px": float(spec["target_dx_px"]),
            "target_dy_px": float(spec["target_dy_px"]),
        }
    return records, summary


def update_manifest_with_gmf_roi_records(
    package_dir: Path,
    records: list[dict[str, object]],
    *,
    summary: dict[str, object],
    package_name: str = PACKAGE_NAME,
) -> None:
    manifest_path = Path(package_dir) / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    pairs = list(manifest.get("pairs", [])) + list(records)
    role_counts = Counter(str(row.get("role", "unknown")) for row in pairs)
    manifest["profile"] = str(package_name) if manifest.get("profile") != "toy" else manifest.get("profile")
    manifest["r62_gmf_roi_motion_boost"] = True
    manifest["r62_gmf_roi_motion_stage"] = GMF_ROI_STAGE
    manifest["r62_gmf_roi_motion_summary"] = summary
    manifest["r62_gmf_roi_motion_frame_count"] = len(records)
    manifest["r62_gmf_roi_motion_pair_count"] = len(records) // 2
    manifest["pairs"] = pairs
    manifest["role_counts"] = dict(sorted(role_counts.items()))
    manifest["total_pairs"] = len(pairs)
    manifest["geometry_sidecars"] = True
    manifest["geometry_count"] = len(pairs)
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")


def create_gmf_roi_package(
    *,
    source_package: Path = SOURCE_PACKAGE,
    dest_package: Path = PACKAGE_DIR,
    max_frames_per_sequence: int = 30,
) -> dict[str, object]:
    source_package = Path(source_package)
    dest_package = Path(dest_package)
    clone_base_package(source_package, dest_package)
    records, summary = build_gmf_roi_records(
        dest_package,
        specs=MOTION_SPECS,
        max_frames_per_sequence=int(max_frames_per_sequence),
    )
    update_manifest_with_gmf_roi_records(dest_package, records, summary=summary, package_name=dest_package.name)
    output = {
        "source_package": str(source_package),
        "dest_package": str(dest_package),
        "stage": GMF_ROI_STAGE,
        "role": GMF_ROI_ROLE,
        "added_frames": len(records),
        "added_pairs": len(records) // 2,
        "summary": summary,
        "manifest_path": str(dest_package / "manifest.json"),
    }
    (dest_package / "gmf_roi_package_summary.json").write_text(
        json.dumps(output, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return output


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Add exact self-shift pairs cropped at the GMF validation ROIs.")
    parser.add_argument("--source-package", default=str(SOURCE_PACKAGE))
    parser.add_argument("--dest-package", default=str(PACKAGE_DIR))
    parser.add_argument("--max-frames-per-sequence", type=int, default=30)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    summary = create_gmf_roi_package(
        source_package=Path(args.source_package),
        dest_package=Path(args.dest_package),
        max_frames_per_sequence=int(args.max_frames_per_sequence),
    )
    print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()

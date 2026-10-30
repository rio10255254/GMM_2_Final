from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Iterable


SCRIPT_DIR = Path(__file__).resolve().parent
LAB_ROOT = Path(__file__).resolve().parents[3]
R61_SCRIPT_DIR = LAB_ROOT / "Experiments" / "R61_BoundaryGeneralizationUniversal" / "scripts"
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))
if str(R61_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(R61_SCRIPT_DIR))

from prepare_r62_selfshift_motion_dataset import (  # noqa: E402
    clone_base_package,
    image_files,
    write_selfshift_pair,
)
from prepare_r62_target_motion_dataset import MOTION_SPECS  # noqa: E402
from prepare_r62_target_sample_dataset import _read_gray  # noqa: E402
from prepare_r61_universal_dataset import prepare_grouped_fixed_split  # noqa: E402


OUTPUT_ROOT = LAB_ROOT / "Training_Data" / "r62_target_sample_boost" / "hs100mg_basler"
SOURCE_PACKAGE = OUTPUT_ROOT / "r62_target_sample_boost_v5_gmf_roi_motion_clean"
PACKAGE_NAME = "r62_target_sample_boost_v6_lowmag_dualroi_gmf_shape"
PACKAGE_DIR = OUTPUT_ROOT / PACKAGE_NAME
LOWMAG_DUALROI_STAGE = "stage_40_r62_lowmag_dualroi_selfshift_pair"
LOWMAG_DOT_ROLE = "target_real_lowmag_gmf_dot_r61_motion_pair"
LOWMAG_SQUARE_ROLE = "target_real_lowmag_square_raw_shape_pair"


DEFAULT_LOWMAG_DOT_ROIS: dict[tuple[str, str], list[tuple[int, int, int]]] = {
    ("20260704_20x_5x", "5x_1um"): [(650, 150, 256), (810, 150, 256), (650, 285, 256)],
    ("20260704_20x_5x", "5x_0p5um"): [(650, 150, 256), (810, 150, 256), (650, 285, 256)],
}
DEFAULT_LOWMAG_SQUARE_ROIS: dict[tuple[str, str], list[tuple[int, int, int]]] = {
    ("20260704_20x_5x", "5x_1um"): [(985, 395, 256)],
    ("20260704_20x_5x", "5x_0p5um"): [(985, 395, 256)],
}


def lowmag_dot_rois_for_spec(
    spec: dict[str, object],
    *,
    crop_map: dict[tuple[str, str], list[tuple[int, int, int]]] | None = None,
) -> list[tuple[int, int, int]]:
    crop_map = crop_map or DEFAULT_LOWMAG_DOT_ROIS
    return list(crop_map.get((str(spec["dataset"]), str(spec["sequence"])), []))


def lowmag_square_rois_for_spec(
    spec: dict[str, object],
    *,
    crop_map: dict[tuple[str, str], list[tuple[int, int, int]]] | None = None,
) -> list[tuple[int, int, int]]:
    crop_map = crop_map or DEFAULT_LOWMAG_SQUARE_ROIS
    return list(crop_map.get((str(spec["dataset"]), str(spec["sequence"])), []))


def _select_frame_pairs(raw_dir: Path, teacher_dir: Path, max_frames: int) -> list[tuple[Path, Path]]:
    raw_paths = image_files(Path(raw_dir))
    teacher_by_name = {path.name: path for path in image_files(Path(teacher_dir))}
    pairs = [(path, teacher_by_name[path.name]) for path in raw_paths if path.name in teacher_by_name]
    if max_frames > 0 and len(pairs) > max_frames:
        # Keep chronological coverage.  These sequences can have warm-up and late-step behavior.
        import numpy as np

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


def _mark_record(record: dict[str, object], *, role: str, domain: str, training_kind: str) -> dict[str, object]:
    out = dict(record)
    out["role"] = role
    out["domain"] = domain
    out["lowmag_dualroi_training"] = True
    out["lowmag_dualroi_kind"] = training_kind
    return out


def build_lowmag_dualroi_records(
    package_dir: Path,
    *,
    specs: Iterable[dict[str, object]] = MOTION_SPECS,
    dot_crop_map: dict[tuple[str, str], list[tuple[int, int, int]]] | None = None,
    square_crop_map: dict[tuple[str, str], list[tuple[int, int, int]]] | None = None,
    max_frames_per_sequence: int = 50,
) -> tuple[list[dict[str, object]], dict[str, object]]:
    records: list[dict[str, object]] = []
    summary: dict[str, object] = {}
    sequence_index = 0
    for spec in specs:
        dataset = str(spec["dataset"])
        sequence = str(spec["sequence"])
        dot_rois = lowmag_dot_rois_for_spec(spec, crop_map=dot_crop_map)
        square_rois = lowmag_square_rois_for_spec(spec, crop_map=square_crop_map)
        if not dot_rois and not square_rois:
            continue
        frame_pairs = _select_frame_pairs(Path(spec["raw_dir"]), Path(spec["teacher_dir"]), int(max_frames_per_sequence))
        dot_pairs = 0
        square_pairs = 0
        for frame_index, (raw_path, teacher_path) in enumerate(frame_pairs):
            raw = _read_gray(raw_path)
            r61_teacher = _read_gray(teacher_path)
            for patch_index, (x, y, crop_size) in enumerate(dot_rois):
                raw_crop = _checked_crop(raw, x=int(x), y=int(y), crop_size=int(crop_size), image_name=raw_path.name)
                teacher_crop = _checked_crop(
                    r61_teacher,
                    x=int(x),
                    y=int(y),
                    crop_size=int(crop_size),
                    image_name=teacher_path.name,
                )
                pair_records = write_selfshift_pair(
                    package_dir=Path(package_dir),
                    stage=LOWMAG_DUALROI_STAGE,
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
                    feature_family=f"{spec['feature_family']}_lowmag_dot_r61_gmf",
                )
                records.extend(
                    _mark_record(
                        record,
                        role=LOWMAG_DOT_ROLE,
                        domain="lowmag_dot_grid_r61_gmf_center_motion",
                        training_kind="dot_r61_gmf",
                    )
                    for record in pair_records
                )
                sequence_index += 1
                dot_pairs += 1
            for patch_index, (x, y, crop_size) in enumerate(square_rois, start=len(dot_rois)):
                raw_crop = _checked_crop(raw, x=int(x), y=int(y), crop_size=int(crop_size), image_name=raw_path.name)
                pair_records = write_selfshift_pair(
                    package_dir=Path(package_dir),
                    stage=LOWMAG_DUALROI_STAGE,
                    dataset=dataset,
                    sequence=sequence,
                    raw_crop=raw_crop,
                    teacher_crop=raw_crop,
                    dx=float(spec["target_dx_px"]),
                    dy=float(spec["target_dy_px"]),
                    sequence_index=sequence_index,
                    patch_index=patch_index,
                    source_frame_name=raw_path.name,
                    crop_x=int(x),
                    crop_y=int(y),
                    feature_family=f"{spec['feature_family']}_lowmag_square_raw_shape",
                )
                records.extend(
                    _mark_record(
                        record,
                        role=LOWMAG_SQUARE_ROLE,
                        domain="lowmag_square_raw_shape_motion_guard",
                        training_kind="square_raw_shape",
                    )
                    for record in pair_records
                )
                sequence_index += 1
                square_pairs += 1
        summary[f"{dataset}/{sequence}"] = {
            "matched_frames_used": len(frame_pairs),
            "dot_roi_count": len(dot_rois),
            "square_roi_count": len(square_rois),
            "dot_pairs": dot_pairs,
            "square_pairs": square_pairs,
            "dot_rois": [{"x": int(x), "y": int(y), "crop_size": int(crop)} for x, y, crop in dot_rois],
            "square_rois": [{"x": int(x), "y": int(y), "crop_size": int(crop)} for x, y, crop in square_rois],
            "target_dx_px": float(spec["target_dx_px"]),
            "target_dy_px": float(spec["target_dy_px"]),
        }
    return records, summary


def update_manifest_with_lowmag_dualroi_records(
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
    manifest["r62_lowmag_dualroi_boost"] = True
    manifest["r62_lowmag_dualroi_stage"] = LOWMAG_DUALROI_STAGE
    manifest["r62_lowmag_dualroi_summary"] = summary
    manifest["r62_lowmag_dualroi_frame_count"] = len(records)
    manifest["r62_lowmag_dualroi_pair_count"] = len(records) // 2
    manifest["pairs"] = pairs
    manifest["role_counts"] = dict(sorted(role_counts.items()))
    manifest["total_pairs"] = len(pairs)
    manifest["geometry_sidecars"] = True
    manifest["geometry_count"] = len(pairs)
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")


def refresh_grouped_split(
    package_dir: Path,
    manifest: dict[str, object],
    *,
    val_ratio: float = 0.10,
    seed: int = 1337,
) -> dict[str, object]:
    return prepare_grouped_fixed_split(
        package_dir=Path(package_dir),
        manifest=manifest,
        val_ratio=float(val_ratio),
        seed=int(seed),
    )


def create_lowmag_dualroi_package(
    *,
    source_package: Path = SOURCE_PACKAGE,
    dest_package: Path = PACKAGE_DIR,
    max_frames_per_sequence: int = 50,
) -> dict[str, object]:
    source_package = Path(source_package)
    dest_package = Path(dest_package)
    clone_base_package(source_package, dest_package)
    records, summary = build_lowmag_dualroi_records(
        dest_package,
        specs=MOTION_SPECS,
        max_frames_per_sequence=int(max_frames_per_sequence),
    )
    update_manifest_with_lowmag_dualroi_records(dest_package, records, summary=summary, package_name=dest_package.name)
    updated_manifest = json.loads((dest_package / "manifest.json").read_text(encoding="utf-8"))
    split_info = refresh_grouped_split(dest_package, updated_manifest)
    output = {
        "source_package": str(source_package),
        "dest_package": str(dest_package),
        "stage": LOWMAG_DUALROI_STAGE,
        "dot_role": LOWMAG_DOT_ROLE,
        "square_role": LOWMAG_SQUARE_ROLE,
        "added_frames": len(records),
        "added_pairs": len(records) // 2,
        "summary": summary,
        "manifest_path": str(dest_package / "manifest.json"),
        "split_info": split_info,
    }
    (dest_package / "lowmag_dualroi_package_summary.json").write_text(
        json.dumps(output, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return output


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Add low-magnification dot GMF and square-shape guard ROI pairs.")
    parser.add_argument("--source-package", default=str(SOURCE_PACKAGE))
    parser.add_argument("--dest-package", default=str(PACKAGE_DIR))
    parser.add_argument("--max-frames-per-sequence", type=int, default=50)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    summary = create_lowmag_dualroi_package(
        source_package=Path(args.source_package),
        dest_package=Path(args.dest_package),
        max_frames_per_sequence=int(args.max_frames_per_sequence),
    )
    print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()

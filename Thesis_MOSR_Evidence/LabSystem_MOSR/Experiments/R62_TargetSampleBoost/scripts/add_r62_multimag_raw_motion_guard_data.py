from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from dataclasses import dataclass
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
SOURCE_PACKAGE = OUTPUT_ROOT / "r62_target_sample_boost_v6_lowmag_dualroi_gmf_shape"
PACKAGE_NAME = "r62_target_sample_boost_v8_multimag_raw_motion_guard"
PACKAGE_DIR = OUTPUT_ROOT / PACKAGE_NAME
MULTIMAG_RAW_GUARD_STAGE = "stage_40_r62_multimag_raw_motion_guard_pair"
MULTIMAG_RAW_GUARD_ROLE = "target_real_multimag_raw_motion_guard_pair"


@dataclass(frozen=True)
class RawGuardRoi:
    tag: str
    x: int
    y: int
    crop_size: int


DEFAULT_RAW_GUARD_ROIS: dict[tuple[str, str], list[RawGuardRoi]] = {
    ("20260704_20x_5x", "20x_1um"): [
        RawGuardRoi("dot_grid_a", 650, 150, 256),
        RawGuardRoi("dot_grid_b", 810, 150, 256),
        RawGuardRoi("dot_grid_c", 650, 285, 256),
        RawGuardRoi("dot_grid_d", 985, 395, 256),
    ],
    ("20260704_20x_5x", "20x_0p5um"): [
        RawGuardRoi("dot_grid_a", 650, 150, 256),
        RawGuardRoi("dot_grid_b", 810, 150, 256),
        RawGuardRoi("dot_grid_c", 650, 285, 256),
        RawGuardRoi("dot_grid_d", 985, 395, 256),
    ],
    ("20260704_20x_5x", "5x_1um"): [
        RawGuardRoi("dot_grid_a", 650, 150, 256),
        RawGuardRoi("dot_grid_b", 810, 150, 256),
        RawGuardRoi("dot_grid_c", 650, 285, 256),
        RawGuardRoi("square_block", 985, 395, 256),
    ],
    ("20260704_20x_5x", "5x_0p5um"): [
        RawGuardRoi("dot_grid_a", 650, 150, 256),
        RawGuardRoi("dot_grid_b", 810, 150, 256),
        RawGuardRoi("dot_grid_c", 650, 285, 256),
        RawGuardRoi("square_block", 985, 395, 256),
    ],
}


def raw_guard_rois_for_spec(
    spec: dict[str, object],
    *,
    roi_map: dict[tuple[str, str], list[RawGuardRoi]] | None = None,
) -> list[RawGuardRoi]:
    roi_map = roi_map or DEFAULT_RAW_GUARD_ROIS
    return list(roi_map.get((str(spec["dataset"]), str(spec["sequence"])), []))


def _select_frames(raw_dir: Path, max_frames: int) -> list[Path]:
    paths = image_files(Path(raw_dir))
    if max_frames > 0 and len(paths) > max_frames:
        import numpy as np

        positions = np.linspace(0, len(paths) - 1, int(max_frames), dtype=int)
        paths = [paths[int(pos)] for pos in positions]
    return paths


def _checked_crop(image: Any, roi: RawGuardRoi, *, image_name: str) -> Any:
    if roi.x < 0 or roi.y < 0 or roi.crop_size <= 0:
        raise ValueError(f"invalid crop for {image_name}: {roi}")
    h, w = image.shape[:2]
    if roi.x + roi.crop_size > w or roi.y + roi.crop_size > h:
        raise ValueError(f"crop exceeds image bounds for {image_name}: image={w}x{h}, crop={roi}")
    return image[roi.y : roi.y + roi.crop_size, roi.x : roi.x + roi.crop_size]


def _mark_record(record: dict[str, object], *, roi: RawGuardRoi) -> dict[str, object]:
    out = dict(record)
    out["role"] = MULTIMAG_RAW_GUARD_ROLE
    out["domain"] = "multimagnification_raw_shape_preserving_motion_guard"
    out["multimag_raw_motion_guard"] = True
    out["teacher_source"] = "raw_same_frame"
    out["crop_tag"] = roi.tag
    return out


def build_multimag_raw_guard_records(
    package_dir: Path,
    *,
    specs: Iterable[dict[str, object]] = MOTION_SPECS,
    roi_map: dict[tuple[str, str], list[RawGuardRoi]] | None = None,
    max_frames_per_sequence: int = 50,
) -> tuple[list[dict[str, object]], dict[str, object]]:
    records: list[dict[str, object]] = []
    summary: dict[str, object] = {}
    sequence_index = 0
    for spec in specs:
        dataset = str(spec["dataset"])
        sequence = str(spec["sequence"])
        rois = raw_guard_rois_for_spec(spec, roi_map=roi_map)
        if not rois:
            continue
        raw_paths = _select_frames(Path(spec["raw_dir"]), int(max_frames_per_sequence))
        written_pairs = 0
        for raw_path in raw_paths:
            raw = _read_gray(raw_path)
            for patch_index, roi in enumerate(rois):
                raw_crop = _checked_crop(raw, roi, image_name=raw_path.name)
                pair_records = write_selfshift_pair(
                    package_dir=Path(package_dir),
                    stage=MULTIMAG_RAW_GUARD_STAGE,
                    dataset=dataset,
                    sequence=sequence,
                    raw_crop=raw_crop,
                    teacher_crop=raw_crop,
                    dx=float(spec["target_dx_px"]),
                    dy=float(spec["target_dy_px"]),
                    sequence_index=sequence_index,
                    patch_index=patch_index,
                    source_frame_name=raw_path.name,
                    crop_x=int(roi.x),
                    crop_y=int(roi.y),
                    feature_family=f"{spec['feature_family']}_raw_guard_{roi.tag}",
                )
                records.extend(_mark_record(record, roi=roi) for record in pair_records)
                sequence_index += 1
                written_pairs += 1
        summary[f"{dataset}/{sequence}"] = {
            "matched_frames_used": len(raw_paths),
            "roi_count": len(rois),
            "raw_guard_pairs": written_pairs,
            "raw_guard_frames": written_pairs * 2,
            "rois": [
                {"tag": roi.tag, "x": int(roi.x), "y": int(roi.y), "crop_size": int(roi.crop_size)}
                for roi in rois
            ],
            "target_dx_px": float(spec["target_dx_px"]),
            "target_dy_px": float(spec["target_dy_px"]),
        }
    return records, summary


def update_manifest_with_multimag_raw_guard_records(
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
    manifest["r62_multimag_raw_guard_boost"] = True
    manifest["r62_multimag_raw_guard_stage"] = MULTIMAG_RAW_GUARD_STAGE
    manifest["r62_multimag_raw_guard_summary"] = summary
    manifest["r62_multimag_raw_guard_frame_count"] = len(records)
    manifest["r62_multimag_raw_guard_pair_count"] = len(records) // 2
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


def create_multimag_raw_guard_package(
    *,
    source_package: Path = SOURCE_PACKAGE,
    dest_package: Path = PACKAGE_DIR,
    max_frames_per_sequence: int = 50,
) -> dict[str, object]:
    source_package = Path(source_package)
    dest_package = Path(dest_package)
    clone_base_package(source_package, dest_package)
    records, summary = build_multimag_raw_guard_records(
        dest_package,
        specs=MOTION_SPECS,
        max_frames_per_sequence=int(max_frames_per_sequence),
    )
    update_manifest_with_multimag_raw_guard_records(dest_package, records, summary=summary, package_name=dest_package.name)
    updated_manifest = json.loads((dest_package / "manifest.json").read_text(encoding="utf-8"))
    split_info = refresh_grouped_split(dest_package, updated_manifest)
    output = {
        "source_package": str(source_package),
        "dest_package": str(dest_package),
        "stage": MULTIMAG_RAW_GUARD_STAGE,
        "role": MULTIMAG_RAW_GUARD_ROLE,
        "added_frames": len(records),
        "added_pairs": len(records) // 2,
        "summary": summary,
        "manifest_path": str(dest_package / "manifest.json"),
        "split_info": split_info,
    }
    (dest_package / "multimag_raw_guard_package_summary.json").write_text(
        json.dumps(output, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return output


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Add raw-shape preserving motion guard pairs for 20x and 5x thesis data.")
    parser.add_argument("--source-package", default=str(SOURCE_PACKAGE))
    parser.add_argument("--dest-package", default=str(PACKAGE_DIR))
    parser.add_argument("--max-frames-per-sequence", type=int, default=50)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    summary = create_multimag_raw_guard_package(
        source_package=Path(args.source_package),
        dest_package=Path(args.dest_package),
        max_frames_per_sequence=int(args.max_frames_per_sequence),
    )
    print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()


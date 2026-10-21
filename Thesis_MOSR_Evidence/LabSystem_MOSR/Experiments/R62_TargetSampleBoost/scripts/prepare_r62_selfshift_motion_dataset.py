from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from collections import Counter
from pathlib import Path
from typing import Iterable

import cv2
import numpy as np


SCRIPT_DIR = Path(__file__).resolve().parent
LAB_ROOT = Path(__file__).resolve().parents[3]
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from prepare_r62_target_motion_dataset import MOTION_SPECS, safe_name  # noqa: E402
from prepare_r62_target_sample_dataset import (  # noqa: E402
    _candidate_tiles,
    _geometry_from_label,
    _pseudo_label_from_teacher,
    _read_gray,
    _write_geometry_arrays,
    _write_image,
)


OUTPUT_ROOT = LAB_ROOT / "Training_Data" / "r62_target_sample_boost" / "hs100mg_basler"
BASE_PACKAGE = OUTPUT_ROOT / "r62_target_sample_boost_v2_real_motion"
PACKAGE_NAME = "r62_target_sample_boost_v3_selfshift_motion"
PACKAGE_DIR = OUTPUT_ROOT / PACKAGE_NAME
SELF_SHIFT_STAGE = "stage_40_r62_target_selfshift_motion_pair"
SELF_SHIFT_ROLE = "target_real_selfshift_motion_pair"


def hardlink_or_copy(src: Path, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    if dst.exists():
        dst.unlink()
    if src.suffix.lower() in {".json", ".csv", ".tsv", ".txt", ".md"}:
        shutil.copy2(src, dst)
        return
    try:
        os.link(src, dst)
    except OSError:
        shutil.copy2(src, dst)


def clone_base_package(base_package: Path, package_dir: Path) -> None:
    base_package = Path(base_package)
    package_dir = Path(package_dir)
    if not base_package.is_dir():
        raise FileNotFoundError(base_package)
    if package_dir.exists():
        shutil.rmtree(package_dir)
    for src in base_package.rglob("*"):
        rel = src.relative_to(base_package)
        dst = package_dir / rel
        if src.is_dir():
            dst.mkdir(parents=True, exist_ok=True)
        else:
            hardlink_or_copy(src, dst)


def shift_image_subpixel(image: np.ndarray, *, dx: float, dy: float) -> np.ndarray:
    h, w = image.shape[:2]
    matrix = np.array([[1.0, 0.0, float(dx)], [0.0, 1.0, float(dy)]], dtype=np.float32)
    shifted = cv2.warpAffine(
        image,
        matrix,
        (w, h),
        flags=cv2.INTER_LINEAR,
        borderMode=cv2.BORDER_REFLECT101,
    )
    return np.clip(shifted, 0, 255).astype(np.uint8)


def write_geometry(package_dir: Path, lbl_rel: Path) -> dict[str, str]:
    label = _read_gray(package_dir / lbl_rel)
    boundary, centerline, distance = _geometry_from_label(label)
    return _write_geometry_arrays(package_dir, lbl_rel, boundary, centerline, distance)


def write_motion_meta(
    package_dir: Path,
    src_rel: Path,
    *,
    dx: float,
    dy: float,
    dataset: str,
    sequence: str,
    sequence_index: int,
    frame_index: int,
    feature_family: str,
) -> str:
    rel_no_ext = src_rel.relative_to("src").with_suffix(".json")
    meta_rel = Path("geom") / "meta" / rel_no_ext
    meta_path = package_dir / meta_rel
    meta_path.parent.mkdir(parents=True, exist_ok=True)
    meta = {
        "delta_from_prev_px": {"dx": float(dx), "dy": float(dy)},
        "feature_family": str(feature_family),
        "target_dataset": str(dataset),
        "target_sequence": str(sequence),
        "motion_sequence_id": f"r62self:{dataset}:{sequence}:seq{sequence_index:05d}",
        "motion_frame": int(frame_index),
        "selfshift_pair": True,
    }
    meta_path.write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")
    return meta_rel.as_posix()


def write_selfshift_pair(
    *,
    package_dir: Path,
    stage: str,
    dataset: str,
    sequence: str,
    raw_crop: np.ndarray,
    teacher_crop: np.ndarray,
    dx: float,
    dy: float,
    sequence_index: int,
    patch_index: int,
    source_frame_name: str,
    crop_x: int,
    crop_y: int,
    feature_family: str,
) -> list[dict[str, object]]:
    package_dir = Path(package_dir)
    pseudo_a = _pseudo_label_from_teacher(raw_crop, teacher_crop)
    raw_b = shift_image_subpixel(raw_crop, dx=float(dx), dy=float(dy))
    pseudo_b = shift_image_subpixel(pseudo_a, dx=float(dx), dy=float(dy))
    records: list[dict[str, object]] = []
    seq_token = f"seq{int(sequence_index):05d}"
    base_dir = Path(stage) / safe_name(str(dataset)) / safe_name(str(sequence)) / seq_token
    for frame_index, (src_img, lbl_img, frame_dx, frame_dy) in enumerate(
        ((raw_crop, pseudo_a, 0.0, 0.0), (raw_b, pseudo_b, float(dx), float(dy)))
    ):
        stem = (
            f"r62self_{safe_name(str(dataset))}_{safe_name(str(sequence))}"
            f"_seq{int(sequence_index):05d}_p{int(patch_index):03d}_f{frame_index:03d}.bmp"
        )
        rel = base_dir / stem
        src_rel = Path("src") / rel
        lbl_rel = Path("lbl") / rel
        _write_image(package_dir / src_rel, src_img)
        _write_image(package_dir / lbl_rel, lbl_img)
        geom = write_geometry(package_dir, lbl_rel)
        meta_rel = write_motion_meta(
            package_dir,
            src_rel,
            dx=frame_dx,
            dy=frame_dy,
            dataset=str(dataset),
            sequence=str(sequence),
            sequence_index=int(sequence_index),
            frame_index=int(frame_index),
            feature_family=str(feature_family),
        )
        records.append(
            {
                "package_src": src_rel.as_posix(),
                "package_lbl": lbl_rel.as_posix(),
                "role": SELF_SHIFT_ROLE,
                "domain": "real_target_texture_exact_selfshift_motion",
                "feature": str(feature_family),
                "shape_family": str(feature_family),
                "polarity": "mixed",
                "source_group": f"target_selfshift:{dataset}:{sequence}",
                "template_id": f"target_selfshift:{dataset}:{sequence}",
                "geometry_id": f"target_selfshift:{dataset}:{sequence}:seq{int(sequence_index):05d}:f{frame_index:03d}",
                "label_source": "r61_teacher_pseudo_shifted_exactly_with_raw_texture",
                "pseudo_label": True,
                "target_dataset": str(dataset),
                "target_sequence": str(sequence),
                "motion_sequence_id": f"r62self:{dataset}:{sequence}:seq{int(sequence_index):05d}",
                "motion_frame": int(frame_index),
                "motion_dx_px": float(frame_dx),
                "motion_dy_px": float(frame_dy),
                "motion_meta": meta_rel,
                "selfshift_pair": True,
                "source_frame_name": str(source_frame_name),
                "crop_x": int(crop_x),
                "crop_y": int(crop_y),
                "crop_size": int(raw_crop.shape[0]),
                **geom,
            }
        )
    return records


def update_manifest_with_selfshift_records(
    package_dir: Path,
    records: list[dict[str, object]],
    *,
    stage: str,
    summary: dict[str, object],
) -> None:
    manifest_path = Path(package_dir) / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    pairs = list(manifest.get("pairs", [])) + list(records)
    role_counts = Counter(str(row.get("role", "unknown")) for row in pairs)
    manifest["profile"] = PACKAGE_NAME if manifest.get("profile") != "toy" else manifest.get("profile")
    manifest["r62_selfshift_motion_boost"] = True
    manifest["r62_selfshift_motion_stage"] = str(stage)
    manifest["r62_selfshift_motion_summary"] = summary
    manifest["r62_selfshift_motion_frame_count"] = len(records)
    manifest["r62_selfshift_motion_pair_count"] = len(records) // 2
    manifest["pairs"] = pairs
    manifest["role_counts"] = dict(sorted(role_counts.items()))
    manifest["total_pairs"] = len(pairs)
    manifest["geometry_sidecars"] = True
    manifest["geometry_count"] = len(pairs)
    manifest["pseudo_label_warning"] = (
        "Target real patches are pseudo labels. Self-shift motion pairs use exact synthetic displacement on real target textures."
    )
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")


def image_files(path: Path) -> list[Path]:
    exts = {".bmp", ".png", ".jpg", ".jpeg", ".tif", ".tiff"}
    return sorted(p for p in Path(path).iterdir() if p.is_file() and p.suffix.lower() in exts)


def build_selfshift_records(
    package_dir: Path,
    *,
    crop_size: int,
    stride: int,
    patches_per_frame: int,
    max_frames_per_sequence: int,
    border: int,
) -> tuple[list[dict[str, object]], dict[str, object]]:
    records: list[dict[str, object]] = []
    summary: dict[str, object] = {}
    sequence_index = 0
    for spec in MOTION_SPECS:
        raw_paths = image_files(Path(spec["raw_dir"]))
        teacher_by_name = {p.name: p for p in image_files(Path(spec["teacher_dir"]))}
        pairs = [(p, teacher_by_name[p.name]) for p in raw_paths if p.name in teacher_by_name]
        if max_frames_per_sequence > 0 and len(pairs) > max_frames_per_sequence:
            positions = np.linspace(0, len(pairs) - 1, int(max_frames_per_sequence), dtype=int)
            pairs = [pairs[int(pos)] for pos in positions]
        written_pairs = 0
        for frame_idx, (raw_path, teacher_path) in enumerate(pairs):
            raw = _read_gray(raw_path)
            teacher = _read_gray(teacher_path)
            tiles = _candidate_tiles(raw, crop=int(crop_size), stride=int(stride), border=int(border))
            chosen: list[tuple[int, int]] = []
            patch_index = 0
            for _score, x, y, _stats in tiles:
                if any(abs(x - sx) < crop_size // 2 and abs(y - sy) < crop_size // 2 for sx, sy in chosen):
                    continue
                raw_crop = raw[y : y + crop_size, x : x + crop_size]
                teacher_crop = teacher[y : y + crop_size, x : x + crop_size]
                if raw_crop.shape != (crop_size, crop_size) or teacher_crop.shape != (crop_size, crop_size):
                    continue
                chosen.append((x, y))
                records.extend(
                    write_selfshift_pair(
                        package_dir=package_dir,
                        stage=SELF_SHIFT_STAGE,
                        dataset=str(spec["dataset"]),
                        sequence=str(spec["sequence"]),
                        raw_crop=raw_crop,
                        teacher_crop=teacher_crop,
                        dx=float(spec["target_dx_px"]),
                        dy=float(spec["target_dy_px"]),
                        sequence_index=sequence_index,
                        patch_index=patch_index,
                        source_frame_name=raw_path.name,
                        crop_x=int(x),
                        crop_y=int(y),
                        feature_family=str(spec["feature_family"]),
                    )
                )
                sequence_index += 1
                patch_index += 1
                written_pairs += 1
                if patch_index >= patches_per_frame:
                    break
        summary[f"{spec['dataset']}/{spec['sequence']}"] = {
            "matched_frames_used": len(pairs),
            "selfshift_pairs": written_pairs,
            "target_dx_px": float(spec["target_dx_px"]),
            "target_dy_px": float(spec["target_dy_px"]),
            "crop_size": int(crop_size),
            "patches_per_frame": int(patches_per_frame),
        }
    return records, summary


def prepare_package(
    *,
    base_package: Path = BASE_PACKAGE,
    output_root: Path = OUTPUT_ROOT,
    package_name: str = PACKAGE_NAME,
    crop_size: int = 512,
    stride: int = 256,
    patches_per_frame: int = 2,
    max_frames_per_sequence: int = 30,
    border: int = 16,
) -> dict[str, object]:
    output_root = Path(output_root)
    package_dir = output_root / str(package_name)
    clone_base_package(Path(base_package), package_dir)
    records, summary = build_selfshift_records(
        package_dir,
        crop_size=int(crop_size),
        stride=int(stride),
        patches_per_frame=int(patches_per_frame),
        max_frames_per_sequence=int(max_frames_per_sequence),
        border=int(border),
    )
    update_manifest_with_selfshift_records(package_dir, records, stage=SELF_SHIFT_STAGE, summary=summary)
    return {
        "package": str(package_dir),
        "selfshift_frames": len(records),
        "selfshift_pairs": len(records) // 2,
        "summary": summary,
    }


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Add exact self-shift target-texture motion pairs to R62 data")
    parser.add_argument("--base-package", type=Path, default=BASE_PACKAGE)
    parser.add_argument("--output-root", type=Path, default=OUTPUT_ROOT)
    parser.add_argument("--package-name", default=PACKAGE_NAME)
    parser.add_argument("--crop-size", type=int, default=512)
    parser.add_argument("--stride", type=int, default=256)
    parser.add_argument("--patches-per-frame", type=int, default=2)
    parser.add_argument("--max-frames-per-sequence", type=int, default=30)
    parser.add_argument("--border", type=int, default=16)
    return parser


def main(argv: Iterable[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    result = prepare_package(
        base_package=args.base_package,
        output_root=args.output_root,
        package_name=args.package_name,
        crop_size=args.crop_size,
        stride=args.stride,
        patches_per_frame=args.patches_per_frame,
        max_frames_per_sequence=args.max_frames_per_sequence,
        border=args.border,
    )
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Prepare R62 target-sample boost data for LabSystem_MOSR.

R62 is a thesis-candidate fine-tuning package.  It reuses a bounded subset of
R61 v16 anchors, then adds real microscope patches from the July 2026 target
sample sequences.  Real patches use conservative pseudo labels built from the
existing R61 reconstruction plus edge sharpening; they are marked as pseudo
labels in the manifest and should not be described as SEM truth.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable

import cv2
import numpy as np
PROJECT_ROOT = Path(__file__).resolve().parents[5]


EXPERIMENT_DIR = Path(__file__).resolve().parents[1]
LAB_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_OUTPUT_ROOT = LAB_ROOT / "Training_Data" / "r62_target_sample_boost" / "hs100mg_basler"
DEFAULT_PACKAGE_NAME = "r62_target_sample_boost_v1"
R61_V16_PACKAGE = (
    LAB_ROOT
    / "Training_Data"
    / "r61_universal_boundary_generalization"
    / "hs100mg_basler"
    / "r61_universal_boundary_train_motion_texture_step_guard_v16"
)
# The trainer only role-labels stage_34..stage_40 as boundary-domain data.
# Keep the R62 identity in the suffix/manifest while using a recognized prefix.
TARGET_STAGE = "stage_40_r62_target_real_pseudo"
IMAGE_EXTENSIONS = {".bmp", ".png", ".jpg", ".jpeg", ".tif", ".tiff"}


ANCHOR_LIMITS = {
    "legacy_shape": 240,
    "sequence_guard": 420,
    "sem_truth_anchor": 640,
    "universal_synthetic": 760,
    "motion_synthetic": 760,
    "motion_texture_synthetic": 760,
    "step_guard_motion_texture_synthetic": 760,
}


@dataclass(frozen=True)
class TargetSequence:
    dataset: str
    sequence: str
    raw_dir: Path
    teacher_dir: Path
    feature_hint: str
    magnification_hint: str
    step_hint_um: float


TARGET_SEQUENCES = (
    TargetSequence(
        dataset="20260702_100MG",
        sequence="x_1um",
        raw_dir=Path(str(PROJECT_ROOT / '20260702_100MG_displacement_analysis/raw_inputs/x_1um/bmp')),
        teacher_dir=Path(str(PROJECT_ROOT / '20260702_100MG_displacement_analysis/r61_v16_psfoff_x_1um/bmp')),
        feature_hint="mixed_pillar_line_square",
        magnification_hint="lab_100mg_sequence",
        step_hint_um=1.0,
    ),
    TargetSequence(
        dataset="20260702_100MG",
        sequence="x_0p5um",
        raw_dir=Path(str(PROJECT_ROOT / '20260702_100MG_displacement_analysis/raw_inputs/x_0p5um/bmp')),
        teacher_dir=Path(str(PROJECT_ROOT / '20260702_100MG_displacement_analysis/r61_v16_psfoff_x_0p5um/bmp')),
        feature_hint="mixed_pillar_line_square",
        magnification_hint="lab_100mg_sequence",
        step_hint_um=0.5,
    ),
    TargetSequence(
        dataset="20260704_20x_5x",
        sequence="20x_1um",
        raw_dir=Path(str(PROJECT_ROOT / '20260704_20x_5x_analysis/raw_inputs/20x_1um/bmp')),
        teacher_dir=Path(str(PROJECT_ROOT / '20260704_20x_5x_analysis/r61_v16_psfoff_20x_1um/bmp')),
        feature_hint="circle_square_line",
        magnification_hint="olympus_20x",
        step_hint_um=1.0,
    ),
    TargetSequence(
        dataset="20260704_20x_5x",
        sequence="20x_0p5um",
        raw_dir=Path(str(PROJECT_ROOT / '20260704_20x_5x_analysis/raw_inputs/20x_0p5um/bmp')),
        teacher_dir=Path(str(PROJECT_ROOT / '20260704_20x_5x_analysis/r61_v16_psfoff_20x_0p5um/bmp')),
        feature_hint="circle_square_line",
        magnification_hint="olympus_20x",
        step_hint_um=0.5,
    ),
    TargetSequence(
        dataset="20260704_20x_5x",
        sequence="5x_1um",
        raw_dir=Path(str(PROJECT_ROOT / '20260704_20x_5x_analysis/raw_inputs/5x_1um/bmp')),
        teacher_dir=Path(str(PROJECT_ROOT / '20260704_20x_5x_analysis/r61_v16_psfoff_5x_1um/bmp')),
        feature_hint="circle_square_line_lowmag",
        magnification_hint="lowmag_5x",
        step_hint_um=1.0,
    ),
    TargetSequence(
        dataset="20260704_20x_5x",
        sequence="5x_0p5um",
        raw_dir=Path(str(PROJECT_ROOT / '20260704_20x_5x_analysis/raw_inputs/5x_0p5um/bmp')),
        teacher_dir=Path(str(PROJECT_ROOT / '20260704_20x_5x_analysis/r61_v16_psfoff_5x_0p5um/bmp')),
        feature_hint="circle_square_line_lowmag",
        magnification_hint="lowmag_5x",
        step_hint_um=0.5,
    ),
)


def _read_gray(path: Path) -> np.ndarray:
    data = np.fromfile(str(path), dtype=np.uint8)
    img = cv2.imdecode(data, cv2.IMREAD_GRAYSCALE)
    if img is None:
        raise RuntimeError(f"failed to read image: {path}")
    return img


def _write_image(path: Path, img: np.ndarray) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    ext = path.suffix or ".bmp"
    ok, encoded = cv2.imencode(ext, np.clip(img, 0, 255).astype(np.uint8))
    if not ok:
        raise RuntimeError(f"failed to encode image: {path}")
    path.write_bytes(encoded.tobytes())


def _copy_or_link(src: Path, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    if dst.exists():
        dst.unlink()
    try:
        os.link(src, dst)
    except OSError:
        shutil.copy2(src, dst)


def _safe_clean_package_dir(package_dir: Path, output_root: Path) -> None:
    package_resolved = package_dir.resolve()
    output_resolved = output_root.resolve()
    try:
        within_output = package_resolved.is_relative_to(output_resolved)
    except AttributeError:
        within_output = str(package_resolved).lower().startswith(str(output_resolved).lower() + os.sep)
    if not within_output or package_resolved == output_resolved:
        raise RuntimeError(f"refusing to clean package outside output root: {package_resolved}")
    if package_dir.exists():
        shutil.rmtree(package_dir)


def _load_manifest(package_dir: Path) -> dict:
    path = Path(package_dir) / "manifest.json"
    if not path.exists():
        raise FileNotFoundError(path)
    return json.loads(path.read_text(encoding="utf-8"))


def _normalize_rel(path: str | Path) -> str:
    return str(path).replace("\\", "/").lstrip("./")


def _count_by_key(rows: list[dict], key: str) -> dict[str, int]:
    return dict(sorted(Counter(str(row.get(key, "unknown")) for row in rows).items()))


def _geometry_from_label(img: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    gray = img.astype(np.uint8, copy=False)
    blur = cv2.GaussianBlur(gray, (3, 3), 0)
    gx = cv2.Sobel(blur, cv2.CV_32F, 1, 0, ksize=3)
    gy = cv2.Sobel(blur, cv2.CV_32F, 0, 1, ksize=3)
    mag = cv2.magnitude(gx, gy)
    threshold = max(4.0, float(np.percentile(mag, 88)))
    centerline = (mag >= threshold).astype(np.uint8) * 255
    centerline = cv2.morphologyEx(centerline, cv2.MORPH_OPEN, np.ones((2, 2), np.uint8))
    if np.count_nonzero(centerline) == 0:
        centerline = cv2.Canny(gray, 40, 120)
    boundary = cv2.dilate(centerline, np.ones((3, 3), np.uint8), iterations=1)
    distance = cv2.distanceTransform((boundary == 0).astype(np.uint8), cv2.DIST_L2, 3).astype(np.float32)
    return boundary.astype(np.uint8), centerline.astype(np.uint8), distance


def _write_geometry_arrays(
    package_dir: Path,
    lbl_rel: Path,
    boundary: np.ndarray,
    centerline: np.ndarray,
    distance: np.ndarray,
) -> dict[str, str]:
    role_rel = lbl_rel.relative_to("lbl")
    boundary_rel = Path("geom") / "boundary" / role_rel
    centerline_rel = Path("geom") / "centerline" / role_rel
    distance_rel = Path("geom") / "distance" / role_rel.with_suffix(".npy")
    _write_image(package_dir / boundary_rel, boundary)
    _write_image(package_dir / centerline_rel, centerline)
    distance_path = package_dir / distance_rel
    distance_path.parent.mkdir(parents=True, exist_ok=True)
    np.save(distance_path, distance.astype(np.float32, copy=False))
    return {
        "geometry_boundary": boundary_rel.as_posix(),
        "geometry_centerline": centerline_rel.as_posix(),
        "geometry_distance": distance_rel.as_posix(),
    }


def _write_geometry_for_label(package_dir: Path, lbl_rel: Path) -> dict[str, str]:
    label = _read_gray(package_dir / lbl_rel)
    boundary, centerline, distance = _geometry_from_label(label)
    return _write_geometry_arrays(package_dir, lbl_rel, boundary, centerline, distance)


def _select_evenly(rows: list[dict], limit: int) -> list[dict]:
    if limit <= 0 or len(rows) <= limit:
        return list(rows[: max(0, limit)]) if limit > 0 else []
    positions = np.linspace(0, len(rows) - 1, int(limit), dtype=int)
    seen = set()
    selected = []
    for pos in positions:
        if int(pos) in seen:
            continue
        seen.add(int(pos))
        selected.append(rows[int(pos)])
    return selected


def _select_r61_role_rows(role: str, rows: list[dict], limit: int) -> list[dict]:
    if limit <= 0:
        return []
    if "motion" not in str(role):
        return _select_evenly(rows, int(limit))
    grouped: dict[str, list[dict]] = {}
    for row in rows:
        seq_id = str(row.get("motion_sequence_id") or row.get("geometry_id") or row.get("package_src"))
        grouped.setdefault(seq_id, []).append(row)
    sequence_ids = sorted(grouped)
    max_sequences = max(1, int(limit) // 2)
    selected_sequence_ids = _select_evenly([{"id": seq_id} for seq_id in sequence_ids], max_sequences)
    selected_ids = [str(row["id"]) for row in selected_sequence_ids]
    selected: list[dict] = []
    for seq_id in selected_ids:
        seq_rows = sorted(grouped[seq_id], key=lambda row: int(row.get("motion_frame", 0)))
        selected.extend(seq_rows)
    return selected[: int(limit)]


def _import_r61_anchor_pairs(package_out: Path, *, limits: dict[str, int]) -> list[dict]:
    src_manifest = _load_manifest(R61_V16_PACKAGE)
    by_role: dict[str, list[dict]] = {}
    for pair in src_manifest.get("pairs", []):
        by_role.setdefault(str(pair.get("role", "unknown")), []).append(pair)

    imported: list[dict] = []
    for role, limit in limits.items():
        for idx, pair in enumerate(_select_r61_role_rows(role, by_role.get(role, []), int(limit))):
            src_rel_old = Path(_normalize_rel(pair["package_src"]))
            lbl_rel_old = Path(_normalize_rel(pair["package_lbl"]))
            src_old = R61_V16_PACKAGE / src_rel_old
            lbl_old = R61_V16_PACKAGE / lbl_rel_old
            if not src_old.exists() or not lbl_old.exists():
                continue
            src_new_rel = src_rel_old
            lbl_new_rel = lbl_rel_old
            _copy_or_link(src_old, package_out / src_new_rel)
            _copy_or_link(lbl_old, package_out / lbl_new_rel)
            geom = {}
            for key in ("geometry_boundary", "geometry_centerline", "geometry_distance"):
                rel_old = pair.get(key)
                if rel_old:
                    rel_path = Path(_normalize_rel(rel_old))
                    old_path = R61_V16_PACKAGE / rel_path
                    if old_path.exists():
                        _copy_or_link(old_path, package_out / rel_path)
                        geom[key] = rel_path.as_posix()
            if set(geom) != {"geometry_boundary", "geometry_centerline", "geometry_distance"}:
                geom = _write_geometry_for_label(package_out, lbl_new_rel)
            motion_meta_rel = None
            if pair.get("motion_meta"):
                meta_rel_path = Path(_normalize_rel(pair["motion_meta"]))
                meta_old = R61_V16_PACKAGE / meta_rel_path
                if meta_old.exists():
                    _copy_or_link(meta_old, package_out / meta_rel_path)
                    motion_meta_rel = meta_rel_path.as_posix()
            imported.append(
                {
                    **{
                        k: v
                        for k, v in pair.items()
                        if k
                        not in {
                            "package_src",
                            "package_lbl",
                            "geometry_boundary",
                            "geometry_centerline",
                            "geometry_distance",
                        }
                    },
                    "package_src": src_new_rel.as_posix(),
                    "package_lbl": lbl_new_rel.as_posix(),
                    "role": role,
                    "source_group": str(pair.get("source_group", role)),
                    "source_package": str(R61_V16_PACKAGE),
                    "source_index": int(idx),
                    "r62_anchor_replay": True,
                    **({"motion_meta": motion_meta_rel} if motion_meta_rel else {}),
                    **geom,
                }
            )
    return imported


def _frame_index_from_name(path: Path, fallback: int) -> int:
    stem = path.stem
    digits = "".join(ch if ch.isdigit() else " " for ch in stem).split()
    return int(digits[-1]) if digits else int(fallback)


def _candidate_tiles(img: np.ndarray, *, crop: int, stride: int, border: int) -> list[tuple[float, int, int, dict]]:
    h, w = img.shape[:2]
    blur = cv2.GaussianBlur(img, (3, 3), 0)
    gx = cv2.Sobel(blur, cv2.CV_32F, 1, 0, ksize=3)
    gy = cv2.Sobel(blur, cv2.CV_32F, 0, 1, ksize=3)
    mag = cv2.magnitude(gx, gy)
    tiles: list[tuple[float, int, int, dict]] = []
    y_stop = max(border + 1, h - crop - border + 1)
    x_stop = max(border + 1, w - crop - border + 1)
    for y in range(border, y_stop, stride):
        for x in range(border, x_stop, stride):
            patch = img[y : y + crop, x : x + crop]
            g = mag[y : y + crop, x : x + crop]
            if patch.shape != (crop, crop):
                continue
            p1, p99 = np.percentile(patch, (1, 99))
            contrast = float(p99 - p1)
            if contrast < 18.0:
                continue
            edge_cut = max(3.0, float(np.percentile(g, 88)))
            edge_frac = float(np.mean(g >= edge_cut))
            if edge_frac < 0.012:
                continue
            sat_frac = float(np.mean((patch <= 2) | (patch >= 253)))
            score = float(np.mean(g) + 0.28 * contrast + 18.0 * edge_frac - 20.0 * sat_frac)
            tiles.append(
                (
                    score,
                    int(x),
                    int(y),
                    {
                        "contrast_p01_p99": contrast,
                        "edge_fraction": edge_frac,
                        "mean_intensity": float(np.mean(patch)),
                        "std_intensity": float(np.std(patch)),
                    },
                )
            )
    tiles.sort(key=lambda row: row[0], reverse=True)
    return tiles


def _too_close(x: int, y: int, chosen: list[tuple[int, int]], *, min_dist: int) -> bool:
    return any(abs(x - cx) < min_dist and abs(y - cy) < min_dist for cx, cy in chosen)


def _pseudo_label_from_teacher(raw: np.ndarray, teacher: np.ndarray) -> np.ndarray:
    raw_f = raw.astype(np.float32)
    teacher_f = teacher.astype(np.float32)
    # Conservative teacher-led target: keep the R61 boundary position, but restore
    # local contrast and edge steepness using the real raw patch.
    raw_blur = cv2.GaussianBlur(raw_f, (0, 0), 1.2)
    teacher_blur = cv2.GaussianBlur(teacher_f, (0, 0), 1.0)
    raw_detail = raw_f - raw_blur
    teacher_sharp = teacher_f + 0.85 * (teacher_f - teacher_blur)
    target = 0.82 * teacher_sharp + 0.18 * (teacher_f + raw_detail)
    lo, hi = np.percentile(target, (0.5, 99.5))
    if hi > lo:
        target = (target - lo) * (255.0 / (hi - lo))
        # Pull back slightly so labels do not become pure binary cartoons.
        target = 0.92 * target + 0.08 * teacher_f
    target = cv2.bilateralFilter(np.clip(target, 0, 255).astype(np.uint8), 5, 18, 18)
    return target


def _paired_frames(seq: TargetSequence) -> list[tuple[Path, Path]]:
    raw = sorted(p for p in seq.raw_dir.glob("*") if p.suffix.lower() in IMAGE_EXTENSIONS)
    teacher = sorted(p for p in seq.teacher_dir.glob("*") if p.suffix.lower() in IMAGE_EXTENSIONS)
    teacher_by_name = {p.name: p for p in teacher}
    pairs = [(p, teacher_by_name[p.name]) for p in raw if p.name in teacher_by_name]
    if not pairs:
        raise RuntimeError(f"no matched raw/teacher frames for {seq.sequence}: {seq.raw_dir} vs {seq.teacher_dir}")
    return pairs


def _write_target_patch(
    *,
    package_dir: Path,
    seq: TargetSequence,
    raw_path: Path,
    teacher_path: Path,
    frame_idx: int,
    patch_idx: int,
    x: int,
    y: int,
    crop_size: int,
    stats: dict,
) -> dict:
    raw = _read_gray(raw_path)
    teacher = _read_gray(teacher_path)
    if raw.shape != teacher.shape:
        raise RuntimeError(f"shape mismatch: {raw_path} {raw.shape} vs {teacher_path} {teacher.shape}")
    raw_crop = raw[y : y + crop_size, x : x + crop_size]
    teacher_crop = teacher[y : y + crop_size, x : x + crop_size]
    pseudo = _pseudo_label_from_teacher(raw_crop, teacher_crop)
    frame_bucket = int(frame_idx // 5)
    stem = f"{seq.dataset}_{seq.sequence}_f{frame_idx:04d}_p{patch_idx:02d}_x{x:04d}_y{y:04d}.bmp"
    rel = Path(TARGET_STAGE) / seq.dataset / seq.sequence / f"bucket_{frame_bucket:03d}" / stem
    src_rel = Path("src") / rel
    lbl_rel = Path("lbl") / rel
    _write_image(package_dir / src_rel, raw_crop)
    _write_image(package_dir / lbl_rel, pseudo)
    geom = _write_geometry_for_label(package_dir, lbl_rel)
    return {
        "package_src": src_rel.as_posix(),
        "package_lbl": lbl_rel.as_posix(),
        "role": "target_real_pseudo_boundary",
        "source_group": f"target_real:{seq.dataset}:{seq.sequence}:bucket_{frame_bucket:03d}",
        "domain": "real_microscope_target_sample_pseudo_boundary",
        "feature": seq.feature_hint,
        "shape_family": seq.feature_hint,
        "polarity": "mixed",
        "template_id": f"{seq.dataset}:{seq.sequence}:bucket_{frame_bucket:03d}",
        "geometry_id": f"target:{seq.dataset}:{seq.sequence}:f{frame_idx:04d}:p{patch_idx:02d}",
        "label_source": "r61_teacher_edge_sharpened_pseudo",
        "pseudo_label": True,
        "anti_answer_leakage": True,
        "validation_grouping": "five_frame_bucket",
        "target_dataset": seq.dataset,
        "target_sequence": seq.sequence,
        "magnification_hint": seq.magnification_hint,
        "step_hint_um": float(seq.step_hint_um),
        "source_frame_name": raw_path.name,
        "teacher_frame_name": teacher_path.name,
        "crop_x": int(x),
        "crop_y": int(y),
        "crop_size": int(crop_size),
        **{f"patch_{k}": v for k, v in stats.items()},
        **geom,
    }


def _write_target_real_pairs(
    package_dir: Path,
    *,
    crop_size: int,
    stride: int,
    patches_per_frame: int,
    max_frames_per_sequence: int,
    border: int,
) -> tuple[list[dict], dict]:
    records: list[dict] = []
    sequence_summary = {}
    for seq in TARGET_SEQUENCES:
        pairs = _paired_frames(seq)
        if max_frames_per_sequence > 0 and len(pairs) > max_frames_per_sequence:
            positions = np.linspace(0, len(pairs) - 1, int(max_frames_per_sequence), dtype=int)
            pairs = [pairs[int(pos)] for pos in positions]
        written_for_sequence = 0
        for fallback_idx, (raw_path, teacher_path) in enumerate(pairs):
            raw = _read_gray(raw_path)
            tiles = _candidate_tiles(raw, crop=crop_size, stride=stride, border=border)
            chosen: list[tuple[int, int]] = []
            frame_idx = _frame_index_from_name(raw_path, fallback_idx)
            patch_idx = 0
            for _, x, y, stats in tiles:
                if _too_close(x, y, chosen, min_dist=max(48, crop_size // 2)):
                    continue
                chosen.append((x, y))
                records.append(
                    _write_target_patch(
                        package_dir=package_dir,
                        seq=seq,
                        raw_path=raw_path,
                        teacher_path=teacher_path,
                        frame_idx=frame_idx,
                        patch_idx=patch_idx,
                        x=x,
                        y=y,
                        crop_size=crop_size,
                        stats=stats,
                    )
                )
                patch_idx += 1
                written_for_sequence += 1
                if patch_idx >= patches_per_frame:
                    break
        sequence_summary[f"{seq.dataset}/{seq.sequence}"] = {
            "matched_frames_used": len(pairs),
            "patches_written": written_for_sequence,
            "raw_dir": str(seq.raw_dir),
            "teacher_dir": str(seq.teacher_dir),
            "feature_hint": seq.feature_hint,
            "magnification_hint": seq.magnification_hint,
            "step_hint_um": seq.step_hint_um,
        }
    return records, sequence_summary


def prepare_package(
    *,
    output_root: Path = DEFAULT_OUTPUT_ROOT,
    package_name: str = DEFAULT_PACKAGE_NAME,
    crop_size: int = 256,
    stride: int = 160,
    patches_per_frame: int = 5,
    max_frames_per_sequence: int = 50,
    border: int = 12,
    anchor_limits: dict[str, int] | None = None,
) -> dict:
    output_root = Path(output_root).resolve()
    package_dir = output_root / str(package_name)
    _safe_clean_package_dir(package_dir, output_root)
    package_dir.mkdir(parents=True, exist_ok=True)

    limits = dict(anchor_limits or ANCHOR_LIMITS)
    records = _import_r61_anchor_pairs(package_dir, limits=limits)
    target_records, target_summary = _write_target_real_pairs(
        package_dir,
        crop_size=int(crop_size),
        stride=int(stride),
        patches_per_frame=int(patches_per_frame),
        max_frames_per_sequence=int(max_frames_per_sequence),
        border=int(border),
    )
    records.extend(target_records)
    if not records:
        raise RuntimeError("R62 package has no pairs")
    manifest = {
        "profile": str(package_name),
        "r61_universal_boundary_training": True,
        "r62_target_sample_boost": True,
        "target": "thesis_target_sample_boundary_and_displacement_domain_boost",
        "anti_answer_leakage_design": True,
        "old_data_reused": True,
        "real_target_pseudo_labels": True,
        "pseudo_label_warning": "Target real patches are R61-teacher edge-sharpened pseudo labels, not SEM truth.",
        "anchor_source_package": str(R61_V16_PACKAGE),
        "anchor_limits": limits,
        "target_stage": TARGET_STAGE,
        "total_pairs": len(records),
        "target_real_pair_count": len(target_records),
        "role_counts": _count_by_key(records, "role"),
        "polarity_counts": _count_by_key(records, "polarity"),
        "shape_family_counts": _count_by_key(records, "shape_family"),
        "geometry_sidecars": True,
        "geometry_count": len(records),
        "crop_size": int(crop_size),
        "target_patch_selection": {
            "stride": int(stride),
            "patches_per_frame": int(patches_per_frame),
            "max_frames_per_sequence": int(max_frames_per_sequence),
            "border": int(border),
            "criterion": "high edge density plus local contrast on raw microscope images",
        },
        "target_sequence_summary": target_summary,
        "pairs": records,
        "generator": "prepare_r62_target_sample_dataset_v1",
        "generated_at": datetime.now().replace(microsecond=0).isoformat(),
    }
    manifest_path = package_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    return {
        "package_dir": str(package_dir),
        "manifest": str(manifest_path),
        "total_pairs": len(records),
        "target_real_pair_count": len(target_records),
        "role_counts": manifest["role_counts"],
        "target_sequence_summary": target_summary,
    }


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Prepare R62 target-sample boost data")
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--package-name", default=DEFAULT_PACKAGE_NAME)
    parser.add_argument("--crop-size", type=int, default=256)
    parser.add_argument("--stride", type=int, default=160)
    parser.add_argument("--patches-per-frame", type=int, default=5)
    parser.add_argument("--max-frames-per-sequence", type=int, default=50)
    parser.add_argument("--border", type=int, default=12)
    return parser


def main(argv: Iterable[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    summary = prepare_package(
        output_root=args.output_root,
        package_name=args.package_name,
        crop_size=args.crop_size,
        stride=args.stride,
        patches_per_frame=args.patches_per_frame,
        max_frames_per_sequence=args.max_frames_per_sequence,
        border=args.border,
    )
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

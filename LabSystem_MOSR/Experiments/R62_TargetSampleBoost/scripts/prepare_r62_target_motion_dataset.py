from __future__ import annotations

import json
import os
import shutil
from collections import Counter
from pathlib import Path

import cv2
import numpy as np

from prepare_r62_target_sample_dataset import (
    _geometry_from_label,
    _pseudo_label_from_teacher,
    _read_gray,
    _write_geometry_arrays,
    _write_image,
)
PROJECT_ROOT = Path(__file__).resolve().parents[4]


LAB_ROOT = Path(__file__).resolve().parents[3]
OUTPUT_ROOT = LAB_ROOT / "Training_Data" / "r62_target_sample_boost" / "hs100mg_basler"
BASE_PACKAGE = OUTPUT_ROOT / "r62_target_sample_boost_v1"
PACKAGE_NAME = "r62_target_sample_boost_v2_real_motion"
PACKAGE_DIR = OUTPUT_ROOT / PACKAGE_NAME
REAL_MOTION_STAGE = "stage_40_r62_real_motion_pair"

MOTION_SPECS = [
    {
        "dataset": "20260702_100MG",
        "sequence": "x_1um",
        "raw_dir": Path(str(PROJECT_ROOT / 'Analyses/20260702_100MG_displacement_analysis/raw_inputs/x_1um/bmp')),
        "teacher_dir": Path(str(PROJECT_ROOT / 'Analyses/20260702_100MG_displacement_analysis/r61_v16_psfoff_x_1um/bmp')),
        "target_dx_px": -14.608419476714516,
        "target_dy_px": 0.0,
        "feature_family": "mixed_pillar_line_square_real_motion",
        "max_frames": 50,
        "roi_count": 4,
    },
    {
        "dataset": "20260702_100MG",
        "sequence": "x_0p5um",
        "raw_dir": Path(str(PROJECT_ROOT / 'Analyses/20260702_100MG_displacement_analysis/raw_inputs/x_0p5um/bmp')),
        "teacher_dir": Path(str(PROJECT_ROOT / 'Analyses/20260702_100MG_displacement_analysis/r61_v16_psfoff_x_0p5um/bmp')),
        "target_dx_px": -7.2481475673746445,
        "target_dy_px": 0.0,
        "feature_family": "mixed_pillar_line_square_real_motion",
        "max_frames": 50,
        "roi_count": 4,
    },
    {
        "dataset": "20260704_20x_5x",
        "sequence": "20x_1um",
        "raw_dir": Path(str(PROJECT_ROOT / 'Analyses/20260704_20x_5x_analysis/raw_inputs/20x_1um/bmp')),
        "teacher_dir": Path(str(PROJECT_ROOT / 'Analyses/20260704_20x_5x_analysis/r61_v16_psfoff_20x_1um/bmp')),
        "target_dx_px": -(1.0 / (3.45 / 20.0)),
        "target_dy_px": 0.0,
        "feature_family": "circle_square_line_real_motion",
        "max_frames": 50,
        "roi_count": 4,
    },
    {
        "dataset": "20260704_20x_5x",
        "sequence": "20x_0p5um",
        "raw_dir": Path(str(PROJECT_ROOT / 'Analyses/20260704_20x_5x_analysis/raw_inputs/20x_0p5um/bmp')),
        "teacher_dir": Path(str(PROJECT_ROOT / 'Analyses/20260704_20x_5x_analysis/r61_v16_psfoff_20x_0p5um/bmp')),
        "target_dx_px": -(0.5 / (3.45 / 20.0)),
        "target_dy_px": 0.0,
        "feature_family": "circle_square_line_real_motion",
        "max_frames": 50,
        "roi_count": 4,
    },
    {
        "dataset": "20260704_20x_5x",
        "sequence": "5x_1um",
        "raw_dir": Path(str(PROJECT_ROOT / 'Analyses/20260704_20x_5x_analysis/raw_inputs/5x_1um/bmp')),
        "teacher_dir": Path(str(PROJECT_ROOT / 'Analyses/20260704_20x_5x_analysis/r61_v16_psfoff_5x_1um/bmp')),
        "target_dx_px": -(1.0 / (3.45 / 5.0)),
        "target_dy_px": 0.0,
        "feature_family": "circle_square_line_lowmag_real_motion",
        "max_frames": 50,
        "roi_count": 4,
    },
    {
        "dataset": "20260704_20x_5x",
        "sequence": "5x_0p5um",
        "raw_dir": Path(str(PROJECT_ROOT / 'Analyses/20260704_20x_5x_analysis/raw_inputs/5x_0p5um/bmp')),
        "teacher_dir": Path(str(PROJECT_ROOT / 'Analyses/20260704_20x_5x_analysis/r61_v16_psfoff_5x_0p5um/bmp')),
        "target_dx_px": -(0.5 / (3.45 / 5.0)),
        "target_dy_px": 0.0,
        "feature_family": "circle_square_line_lowmag_real_motion",
        "max_frames": 50,
        "roi_count": 4,
    },
]


def safe_name(text: str) -> str:
    return "".join(ch if ch.isalnum() else "_" for ch in text)


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


def clone_base_package() -> None:
    if not BASE_PACKAGE.is_dir():
        raise FileNotFoundError(f"base package not found: {BASE_PACKAGE}")
    if PACKAGE_DIR.exists():
        shutil.rmtree(PACKAGE_DIR)
    for src in BASE_PACKAGE.rglob("*"):
        rel = src.relative_to(BASE_PACKAGE)
        dst = PACKAGE_DIR / rel
        if src.is_dir():
            dst.mkdir(parents=True, exist_ok=True)
        else:
            hardlink_or_copy(src, dst)


def image_files(path: Path) -> list[Path]:
    exts = {".bmp", ".png", ".jpg", ".jpeg", ".tif", ".tiff"}
    return sorted(p for p in path.iterdir() if p.is_file() and p.suffix.lower() in exts)


def rank_rois(image: np.ndarray, *, crop_size: int, count: int) -> list[tuple[int, int]]:
    h, w = image.shape
    stride = max(128, crop_size // 2)
    blur = cv2.GaussianBlur(image.astype(np.float32), (0, 0), 1.0)
    gx = cv2.Sobel(blur, cv2.CV_32F, 1, 0, ksize=3)
    gy = cv2.Sobel(blur, cv2.CV_32F, 0, 1, ksize=3)
    edge = cv2.magnitude(gx, gy)
    candidates: list[tuple[float, int, int]] = []
    for y in range(0, max(1, h - crop_size + 1), stride):
        for x in range(0, max(1, w - crop_size + 1), stride):
            patch = image[y : y + crop_size, x : x + crop_size]
            edge_patch = edge[y : y + crop_size, x : x + crop_size]
            score = float(np.percentile(edge_patch, 92)) + 0.35 * float(np.std(patch))
            candidates.append((score, x, y))
    candidates.sort(reverse=True)
    selected: list[tuple[int, int]] = []
    for _, x, y in candidates:
        if all(abs(x - sx) >= crop_size // 2 or abs(y - sy) >= crop_size // 2 for sx, sy in selected):
            selected.append((x, y))
            if len(selected) >= count:
                break
    if not selected:
        selected.append((max(0, (w - crop_size) // 2), max(0, (h - crop_size) // 2)))
    return selected


def write_geom(lbl_rel: Path) -> dict[str, str]:
    label = _read_gray(PACKAGE_DIR / lbl_rel)
    boundary, centerline, distance = _geometry_from_label(label)
    return _write_geometry_arrays(PACKAGE_DIR, lbl_rel, boundary, centerline, distance)


def write_meta(src_rel: Path, *, dx: float, dy: float, spec: dict[str, object], seq_id: int, frame_idx: int) -> str:
    rel_no_ext = src_rel.relative_to("src").with_suffix(".json")
    meta_rel = Path("geom") / "meta" / rel_no_ext
    meta_path = PACKAGE_DIR / meta_rel
    meta_path.parent.mkdir(parents=True, exist_ok=True)
    meta = {
        "delta_from_prev_px": {"dx": float(dx), "dy": float(dy)},
        "feature_family": str(spec["feature_family"]),
        "target_dataset": str(spec["dataset"]),
        "target_sequence": str(spec["sequence"]),
        "motion_sequence_id": f"r62real:{spec['dataset']}:{spec['sequence']}:roi{seq_id:02d}",
        "motion_frame": int(frame_idx),
    }
    meta_path.write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")
    return meta_rel.as_posix()


def build_real_motion_pairs() -> tuple[list[dict[str, object]], dict[str, object]]:
    records: list[dict[str, object]] = []
    summary: dict[str, object] = {}
    global_seq = 0
    crop_size = 512
    for spec in MOTION_SPECS:
        raw_paths = image_files(Path(spec["raw_dir"]))[: int(spec["max_frames"])]
        teacher_paths = image_files(Path(spec["teacher_dir"]))[: int(spec["max_frames"])]
        teacher_by_name = {p.name: p for p in teacher_paths}
        pairs = [(p, teacher_by_name[p.name]) for p in raw_paths if p.name in teacher_by_name]
        if len(pairs) < 2:
            raise RuntimeError(f"not enough matched frames for {spec['dataset']} {spec['sequence']}")
        first = _read_gray(pairs[0][0])
        rois = rank_rois(first, crop_size=crop_size, count=int(spec["roi_count"]))
        seq_records = 0
        for roi_idx, (x, y) in enumerate(rois):
            seq_id = global_seq
            global_seq += 1
            for frame_idx, (raw_path, teacher_path) in enumerate(pairs):
                raw = _read_gray(raw_path)
                teacher = _read_gray(teacher_path)
                raw_crop = raw[y : y + crop_size, x : x + crop_size]
                teacher_crop = teacher[y : y + crop_size, x : x + crop_size]
                pseudo = _pseudo_label_from_teacher(raw_crop, teacher_crop)
                stem = (
                    f"r62real_{safe_name(str(spec['dataset']))}_{safe_name(str(spec['sequence']))}"
                    f"_roi{roi_idx:02d}_seq{seq_id:03d}_f{frame_idx:03d}.bmp"
                )
                rel = Path(REAL_MOTION_STAGE) / safe_name(str(spec["dataset"])) / safe_name(str(spec["sequence"])) / f"roi_{roi_idx:02d}" / stem
                src_rel = Path("src") / rel
                lbl_rel = Path("lbl") / rel
                _write_image(PACKAGE_DIR / src_rel, raw_crop)
                _write_image(PACKAGE_DIR / lbl_rel, pseudo)
                geom = write_geom(lbl_rel)
                dx = 0.0 if frame_idx == 0 else float(spec["target_dx_px"])
                dy = 0.0 if frame_idx == 0 else float(spec["target_dy_px"])
                meta_rel = write_meta(src_rel, dx=dx, dy=dy, spec=spec, seq_id=seq_id, frame_idx=frame_idx)
                records.append(
                    {
                        "package_src": src_rel.as_posix(),
                        "package_lbl": lbl_rel.as_posix(),
                        "role": "target_real_motion_pair",
                        "domain": "real_microscope_target_sample_motion",
                        "feature": str(spec["feature_family"]),
                        "shape_family": str(spec["feature_family"]),
                        "polarity": "mixed",
                        "source_group": f"target_real_motion:{spec['dataset']}:{spec['sequence']}:roi{roi_idx:02d}",
                        "template_id": f"target_real_motion:{spec['dataset']}:{spec['sequence']}:roi{roi_idx:02d}",
                        "geometry_id": f"target_motion:{spec['dataset']}:{spec['sequence']}:roi{roi_idx:02d}:f{frame_idx:03d}",
                        "label_source": "r61_teacher_edge_sharpened_pseudo_with_real_motion_meta",
                        "pseudo_label": True,
                        "target_dataset": str(spec["dataset"]),
                        "target_sequence": str(spec["sequence"]),
                        "motion_sequence_id": f"r62real:{spec['dataset']}:{spec['sequence']}:roi{roi_idx:02d}",
                        "motion_frame": int(frame_idx),
                        "motion_dx_px": float(dx),
                        "motion_dy_px": float(dy),
                        "motion_meta": meta_rel,
                        "source_frame_name": raw_path.name,
                        "teacher_frame_name": teacher_path.name,
                        "crop_x": int(x),
                        "crop_y": int(y),
                        "crop_size": int(crop_size),
                        **geom,
                    }
                )
                seq_records += 1
        summary[f"{spec['dataset']}/{spec['sequence']}"] = {
            "matched_frames": len(pairs),
            "roi_count": len(rois),
            "frames_written": seq_records,
            "motion_pairs": seq_records - len(rois),
            "target_dx_px": float(spec["target_dx_px"]),
            "target_dy_px": float(spec["target_dy_px"]),
            "rois": [{"x": int(x), "y": int(y), "crop_size": int(crop_size)} for x, y in rois],
        }
    return records, summary


def update_manifest(records: list[dict[str, object]], motion_summary: dict[str, object]) -> None:
    manifest_path = PACKAGE_DIR / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["profile"] = PACKAGE_NAME
    manifest["r62_real_motion_boost"] = True
    manifest["r62_real_motion_stage"] = REAL_MOTION_STAGE
    manifest["pairs"] = list(manifest.get("pairs", [])) + records
    role_counts = Counter(str(row.get("role", "unknown")) for row in manifest["pairs"])
    manifest["role_counts"] = dict(sorted(role_counts.items()))
    manifest["total_pairs"] = len(manifest["pairs"])
    manifest["geometry_sidecars"] = True
    manifest["geometry_count"] = len(manifest["pairs"])
    manifest["r62_real_motion_frame_count"] = len(records)
    manifest["r62_real_motion_pair_count"] = sum(max(0, int(v["motion_pairs"])) for v in motion_summary.values())
    manifest["r62_real_motion_sequence_count"] = sum(int(v["roi_count"]) for v in motion_summary.values())
    manifest["r62_real_motion_summary"] = motion_summary
    manifest["pseudo_label_warning"] = (
        "Target real patches remain pseudo labels. Real motion pairs add commanded/measured displacement consistency, not SEM truth."
    )
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")


def main() -> None:
    clone_base_package()
    records, motion_summary = build_real_motion_pairs()
    update_manifest(records, motion_summary)
    print(
        json.dumps(
            {
                "package": str(PACKAGE_DIR),
                "added_real_motion_frames": len(records),
                "real_motion_sequences": sum(int(v["roi_count"]) for v in motion_summary.values()),
                "real_motion_pairs": sum(max(0, int(v["motion_pairs"])) for v in motion_summary.values()),
            },
            indent=2,
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()

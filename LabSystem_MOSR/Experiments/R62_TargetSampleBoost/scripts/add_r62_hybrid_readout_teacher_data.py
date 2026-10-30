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
R61_SCRIPT_DIR = LAB_ROOT / "Experiments" / "R61_BoundaryGeneralizationUniversal" / "scripts"
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))
if str(R61_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(R61_SCRIPT_DIR))

from add_r62_anchor_blend_teacher_data import (  # noqa: E402
    DEFAULT_ANCHOR_TEACHER_ROIS,
    _checked_crop,
    _select_frame_pairs,
)
from prepare_r62_selfshift_motion_dataset import (  # noqa: E402
    clone_base_package,
    shift_image_subpixel,
    write_geometry,
    write_motion_meta,
)
from prepare_r62_target_motion_dataset import MOTION_SPECS, safe_name  # noqa: E402
from prepare_r62_target_sample_dataset import _read_gray, _write_image  # noqa: E402
from prepare_r61_universal_dataset import prepare_grouped_fixed_split  # noqa: E402
PROJECT_ROOT = Path(__file__).resolve().parents[4]


OUTPUT_ROOT = LAB_ROOT / "Training_Data" / "r62_target_sample_boost" / "hs100mg_basler"
SOURCE_PACKAGE = OUTPUT_ROOT / "r62_target_sample_boost_v8_multimag_raw_motion_guard"
PACKAGE_NAME = "r62_target_sample_boost_v9_hybrid_readout_teacher"
PACKAGE_DIR = OUTPUT_ROOT / PACKAGE_NAME
HYBRID_TEACHER_STAGE = "stage_40_r62_hybrid_readout_teacher_pair"
HYBRID_TEACHER_ROLE = "target_real_hybrid_readout_teacher_pair"


DEFAULT_HYBRID_TEACHER_SOURCES: dict[tuple[str, str], str] = {
    ("20260702_100MG", "x_1um"): "v20",
    ("20260702_100MG", "x_0p5um"): "v28",
    ("20260704_20x_5x", "20x_1um"): "v31_externaldetail35",
    ("20260704_20x_5x", "20x_0p5um"): "v28",
    ("20260704_20x_5x", "5x_1um"): "v31_externaldetail35",
    ("20260704_20x_5x", "5x_0p5um"): "v31_externaldetail35",
}


DEFAULT_HYBRID_TEACHER_DIRS: dict[tuple[str, str], Path] = {
    ("20260702_100MG", "x_1um"): Path(
        str(PROJECT_ROOT / 'Analyses/20260702_100MG_displacement_analysis/r62_v20_gmfroi_e1_mtb200_psfoff_x_1um/bmp')
    ),
    ("20260702_100MG", "x_0p5um"): Path(
        str(PROJECT_ROOT / 'Analyses/20260702_100MG_displacement_analysis/r62_v28_multimagraw_latest_psfoff_x_0p5um/bmp')
    ),
    ("20260704_20x_5x", "20x_1um"): Path(
        str(PROJECT_ROOT / 'Analyses/20260704_20x_5x_analysis/r62_v31_v28_externaldetail35_psfoff_20x_1um/bmp')
    ),
    ("20260704_20x_5x", "20x_0p5um"): Path(
        str(PROJECT_ROOT / 'Analyses/20260704_20x_5x_analysis/r62_v28_multimagraw_latest_psfoff_20x_0p5um/bmp')
    ),
    ("20260704_20x_5x", "5x_1um"): Path(
        str(PROJECT_ROOT / 'Analyses/20260704_20x_5x_analysis/r62_v31_v28_externaldetail35_psfoff_5x_1um/bmp')
    ),
    ("20260704_20x_5x", "5x_0p5um"): Path(
        str(PROJECT_ROOT / 'Analyses/20260704_20x_5x_analysis/r62_v31_v28_externaldetail35_psfoff_5x_0p5um/bmp')
    ),
}

DEFAULT_HYBRID_TEACHER_ROIS = DEFAULT_ANCHOR_TEACHER_ROIS


def hybrid_teacher_source_for_key(
    key: tuple[str, str],
    *,
    source_map: dict[tuple[str, str], str] | None = None,
) -> str:
    source_map = source_map or DEFAULT_HYBRID_TEACHER_SOURCES
    if key not in source_map:
        raise KeyError(f"no hybrid teacher source configured for {key[0]}/{key[1]}")
    return str(source_map[key])


def hybrid_teacher_dir_for_spec(
    spec: dict[str, object],
    *,
    teacher_dir_map: dict[tuple[str, str], Path] | None = None,
) -> Path:
    teacher_dir_map = teacher_dir_map or DEFAULT_HYBRID_TEACHER_DIRS
    key = (str(spec["dataset"]), str(spec["sequence"]))
    if key not in teacher_dir_map:
        raise KeyError(f"no hybrid teacher directory configured for {key[0]}/{key[1]}")
    return Path(teacher_dir_map[key])


def hybrid_teacher_rois_for_spec(
    spec: dict[str, object],
    *,
    roi_map: dict[tuple[str, str], list[dict[str, object]]] | None = None,
) -> list[dict[str, object]]:
    roi_map = roi_map or DEFAULT_HYBRID_TEACHER_ROIS
    key = (str(spec["dataset"]), str(spec["sequence"]))
    if key not in roi_map:
        raise KeyError(f"no hybrid teacher ROI configured for {key[0]}/{key[1]}")
    return [dict(row) for row in roi_map[key]]


def write_hybrid_teacher_pair(
    *,
    package_dir: Path,
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
    crop_tag: str,
    feature_family: str,
    teacher_source: str,
) -> list[dict[str, object]]:
    package_dir = Path(package_dir)
    raw_b = shift_image_subpixel(raw_crop, dx=float(dx), dy=float(dy))
    teacher_b = shift_image_subpixel(teacher_crop, dx=float(dx), dy=float(dy))
    records: list[dict[str, object]] = []
    seq_token = f"seq{int(sequence_index):05d}"
    base_dir = Path(HYBRID_TEACHER_STAGE) / safe_name(str(dataset)) / safe_name(str(sequence)) / seq_token
    for frame_index, (src_img, lbl_img, frame_dx, frame_dy) in enumerate(
        ((raw_crop, teacher_crop, 0.0, 0.0), (raw_b, teacher_b, float(dx), float(dy)))
    ):
        stem = (
            f"r62hybrid_{safe_name(str(dataset))}_{safe_name(str(sequence))}"
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
            feature_family=f"{feature_family}_{crop_tag}",
        )
        records.append(
            {
                "package_src": src_rel.as_posix(),
                "package_lbl": lbl_rel.as_posix(),
                "role": HYBRID_TEACHER_ROLE,
                "domain": "real_target_texture_exact_selfshift_motion_hybrid_best_readout_teacher",
                "feature": f"{feature_family}_{crop_tag}",
                "shape_family": f"{feature_family}_{crop_tag}",
                "polarity": "mixed",
                "source_group": f"hybrid_readout_teacher:{dataset}:{sequence}:{crop_tag}",
                "template_id": f"hybrid_readout_teacher:{dataset}:{sequence}:{crop_tag}",
                "geometry_id": (
                    f"hybrid_readout_teacher:{dataset}:{sequence}:"
                    f"seq{int(sequence_index):05d}:f{frame_index:03d}"
                ),
                "label_source": "hybrid_best_readout_teacher_shifted_exactly_with_raw_texture",
                "pseudo_label": False,
                "target_dataset": str(dataset),
                "target_sequence": str(sequence),
                "motion_sequence_id": f"r62hybrid:{dataset}:{sequence}:{crop_tag}:seq{int(sequence_index):05d}",
                "motion_frame": int(frame_index),
                "motion_dx_px": float(frame_dx),
                "motion_dy_px": float(frame_dy),
                "motion_meta": meta_rel,
                "selfshift_pair": True,
                "hybrid_readout_teacher_training": True,
                "teacher_source": str(teacher_source),
                "source_frame_name": str(source_frame_name),
                "crop_x": int(crop_x),
                "crop_y": int(crop_y),
                "crop_size": int(raw_crop.shape[0]),
                "crop_tag": str(crop_tag),
                **geom,
            }
        )
    return records


def build_hybrid_teacher_records(
    package_dir: Path,
    *,
    specs: Iterable[dict[str, object]] = MOTION_SPECS,
    teacher_dir_map: dict[tuple[str, str], Path] | None = None,
    source_map: dict[tuple[str, str], str] | None = None,
    roi_map: dict[tuple[str, str], list[dict[str, object]]] | None = None,
    max_frames_per_sequence: int = 50,
) -> tuple[list[dict[str, object]], dict[str, object]]:
    records: list[dict[str, object]] = []
    summary: dict[str, object] = {}
    sequence_index = 0
    for spec in specs:
        dataset = str(spec["dataset"])
        sequence = str(spec["sequence"])
        key = (dataset, sequence)
        teacher_dir = hybrid_teacher_dir_for_spec(spec, teacher_dir_map=teacher_dir_map)
        teacher_source = hybrid_teacher_source_for_key(key, source_map=source_map)
        frame_pairs = _select_frame_pairs(Path(spec["raw_dir"]), teacher_dir, int(max_frames_per_sequence))
        rois = hybrid_teacher_rois_for_spec(spec, roi_map=roi_map)
        written_pairs = 0
        for raw_path, teacher_path in frame_pairs:
            raw = _read_gray(raw_path)
            teacher = _read_gray(teacher_path)
            if raw.shape != teacher.shape:
                raise RuntimeError(f"shape mismatch: {raw_path} {raw.shape} vs {teacher_path} {teacher.shape}")
            for patch_index, roi in enumerate(rois):
                x = int(roi["x"])
                y = int(roi["y"])
                crop_size = int(roi["crop_size"])
                tag = str(roi.get("tag", f"roi{patch_index:03d}"))
                raw_crop = _checked_crop(raw, x=x, y=y, crop_size=crop_size, image_name=raw_path.name)
                teacher_crop = _checked_crop(teacher, x=x, y=y, crop_size=crop_size, image_name=teacher_path.name)
                records.extend(
                    write_hybrid_teacher_pair(
                        package_dir=package_dir,
                        dataset=dataset,
                        sequence=sequence,
                        raw_crop=raw_crop,
                        teacher_crop=teacher_crop,
                        dx=float(spec["target_dx_px"]),
                        dy=float(spec["target_dy_px"]),
                        sequence_index=sequence_index,
                        patch_index=patch_index,
                        source_frame_name=raw_path.name,
                        crop_x=x,
                        crop_y=y,
                        crop_tag=tag,
                        feature_family=str(spec["feature_family"]),
                        teacher_source=teacher_source,
                    )
                )
                sequence_index += 1
                written_pairs += 1
        summary[f"{dataset}/{sequence}"] = {
            "matched_frames_used": len(frame_pairs),
            "configured_roi_count": len(rois),
            "hybrid_teacher_pairs": written_pairs,
            "hybrid_teacher_frames": written_pairs * 2,
            "teacher_dir": str(teacher_dir),
            "teacher_source": teacher_source,
            "rois": [
                {
                    "x": int(row["x"]),
                    "y": int(row["y"]),
                    "crop_size": int(row["crop_size"]),
                    "tag": str(row.get("tag", "")),
                }
                for row in rois
            ],
            "target_dx_px": float(spec["target_dx_px"]),
            "target_dy_px": float(spec["target_dy_px"]),
        }
    return records, summary


def update_manifest_with_hybrid_teacher_records(
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
    manifest["r62_hybrid_readout_teacher_boost"] = True
    manifest["r62_hybrid_readout_teacher_stage"] = HYBRID_TEACHER_STAGE
    manifest["r62_hybrid_readout_teacher_summary"] = summary
    manifest["r62_hybrid_readout_teacher_frame_count"] = len(records)
    manifest["r62_hybrid_readout_teacher_pair_count"] = len(records) // 2
    manifest["r62_hybrid_readout_teacher_label_policy"] = (
        "Direct labels from per-sequence best verified readout outputs; no same-sample CD calibration is applied."
    )
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


def create_hybrid_teacher_package(
    *,
    source_package: Path = SOURCE_PACKAGE,
    dest_package: Path = PACKAGE_DIR,
    max_frames_per_sequence: int = 50,
) -> dict[str, object]:
    source_package = Path(source_package)
    dest_package = Path(dest_package)
    clone_base_package(source_package, dest_package)
    records, summary = build_hybrid_teacher_records(
        dest_package,
        specs=MOTION_SPECS,
        max_frames_per_sequence=int(max_frames_per_sequence),
    )
    update_manifest_with_hybrid_teacher_records(
        dest_package,
        records,
        summary=summary,
        package_name=dest_package.name,
    )
    updated_manifest = json.loads((dest_package / "manifest.json").read_text(encoding="utf-8"))
    split_info = refresh_grouped_split(dest_package, updated_manifest)
    output = {
        "source_package": str(source_package),
        "dest_package": str(dest_package),
        "stage": HYBRID_TEACHER_STAGE,
        "role": HYBRID_TEACHER_ROLE,
        "added_frames": len(records),
        "added_pairs": len(records) // 2,
        "summary": summary,
        "manifest_path": str(dest_package / "manifest.json"),
        "split_info": split_info,
    }
    (dest_package / "hybrid_readout_teacher_package_summary.json").write_text(
        json.dumps(output, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return output


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Add per-sequence best-readout hybrid teacher self-shift pairs.")
    parser.add_argument("--source-package", default=str(SOURCE_PACKAGE))
    parser.add_argument("--dest-package", default=str(PACKAGE_DIR))
    parser.add_argument("--max-frames-per-sequence", type=int, default=50)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    summary = create_hybrid_teacher_package(
        source_package=Path(args.source_package),
        dest_package=Path(args.dest_package),
        max_frames_per_sequence=int(args.max_frames_per_sequence),
    )
    print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()

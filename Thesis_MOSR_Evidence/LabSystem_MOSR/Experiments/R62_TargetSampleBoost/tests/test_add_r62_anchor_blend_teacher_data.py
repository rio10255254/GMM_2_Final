from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import cv2
import numpy as np


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "add_r62_anchor_blend_teacher_data.py"


def load_module():
    spec = importlib.util.spec_from_file_location("add_r62_anchor_blend_teacher_data", SCRIPT_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _write_minimal_manifest(package: Path) -> None:
    for leaf in ("src", "lbl", "geom/boundary", "geom/centerline", "geom/distance", "geom/meta"):
        (package / leaf).mkdir(parents=True, exist_ok=True)
    manifest = {
        "profile": "toy",
        "r61_universal_boundary_training": True,
        "anti_answer_leakage_design": True,
        "geometry_sidecars": True,
        "geometry_count": 0,
        "total_pairs": 0,
        "pairs": [],
        "role_counts": {},
    }
    (package / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")


def test_anchor_teacher_defaults_target_verified_blend_outputs_and_square_roi():
    module = load_module()

    dir_100mg = module.anchor_teacher_dir_for_spec({"dataset": "20260702_100MG", "sequence": "x_1um"})
    dir_5x = module.anchor_teacher_dir_for_spec({"dataset": "20260704_20x_5x", "sequence": "5x_1um"})
    rois_5x = module.anchor_teacher_rois_for_spec({"dataset": "20260704_20x_5x", "sequence": "5x_1um"})

    assert "r62_v7_anchor_blend10_x_1um" in str(dir_100mg)
    assert "r62_v7_anchor_blend10_5x_1um" in str(dir_5x)
    assert any(roi["tag"] == "5x_square_block" for roi in rois_5x)
    assert module.ANCHOR_TEACHER_STAGE.startswith("stage_40_")


def test_build_anchor_teacher_records_use_teacher_pixels_directly(tmp_path: Path):
    module = load_module()
    package = tmp_path / "pkg"
    _write_minimal_manifest(package)
    raw_dir = tmp_path / "raw"
    teacher_dir = tmp_path / "teacher"
    raw_dir.mkdir()
    teacher_dir.mkdir()
    raw = np.full((96, 96), 40, dtype=np.uint8)
    teacher = np.full((96, 96), 90, dtype=np.uint8)
    cv2.rectangle(raw, (24, 24), (72, 72), 180, -1)
    cv2.rectangle(teacher, (24, 24), (72, 72), 210, -1)
    cv2.imwrite(str(raw_dir / "frame_0000.bmp"), raw)
    cv2.imwrite(str(teacher_dir / "frame_0000.bmp"), teacher)
    specs = [
        {
            "dataset": "toy_dataset",
            "sequence": "toy_sequence",
            "raw_dir": raw_dir,
            "teacher_dir": tmp_path / "unused_r61_teacher",
            "target_dx_px": 0.0,
            "target_dy_px": 0.0,
            "feature_family": "toy_anchor",
        }
    ]

    records, summary = module.build_anchor_teacher_records(
        package,
        specs=specs,
        teacher_dir_map={("toy_dataset", "toy_sequence"): teacher_dir},
        roi_map={("toy_dataset", "toy_sequence"): [{"x": 16, "y": 16, "crop_size": 64, "tag": "toy_square"}]},
        max_frames_per_sequence=1,
    )
    module.update_manifest_with_anchor_teacher_records(package, records, summary=summary)

    first_label = cv2.imread(str(package / records[0]["package_lbl"]), cv2.IMREAD_GRAYSCALE)
    expected = teacher[16:80, 16:80]
    manifest = json.loads((package / "manifest.json").read_text(encoding="utf-8"))
    assert len(records) == 2
    assert np.array_equal(first_label, expected)
    assert records[0]["role"] == module.ANCHOR_TEACHER_ROLE
    assert records[0]["anchor_blend10_teacher_training"] is True
    assert records[0]["teacher_source"] == "v7_anchor_blend10"
    assert records[0]["crop_tag"] == "toy_square"
    assert manifest["role_counts"][module.ANCHOR_TEACHER_ROLE] == 2
    assert manifest["r62_anchor_blend10_teacher_pair_count"] == 1
    assert summary["toy_dataset/toy_sequence"]["anchor_teacher_pairs"] == 1

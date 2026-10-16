from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import cv2
import numpy as np


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "add_r62_gmf_roi_selfshift_data.py"


def load_module():
    spec = importlib.util.spec_from_file_location("add_r62_gmf_roi_selfshift_data", SCRIPT_PATH)
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


def test_gmf_roi_crop_map_targets_validation_rois():
    module = load_module()

    assert module.gmf_roi_crops_for_spec({"dataset": "20260702_100MG", "sequence": "x_1um"}) == [(1080, 40, 512)]
    assert module.gmf_roi_crops_for_spec({"dataset": "20260704_20x_5x", "sequence": "20x_1um"}) == [(650, 150, 512)]


def test_gmf_roi_stage_stays_in_trainer_boundary_role_range():
    module = load_module()

    assert module.GMF_ROI_STAGE.startswith("stage_40_")


def test_build_gmf_roi_records_marks_role_and_manifest(tmp_path: Path):
    module = load_module()
    package = tmp_path / "pkg"
    _write_minimal_manifest(package)
    raw_dir = tmp_path / "raw"
    teacher_dir = tmp_path / "teacher"
    raw_dir.mkdir()
    teacher_dir.mkdir()
    image = np.full((96, 96), 20, dtype=np.uint8)
    cv2.circle(image, (48, 48), 10, 220, -1)
    cv2.imwrite(str(raw_dir / "frame_0000.bmp"), image)
    cv2.imwrite(str(teacher_dir / "frame_0000.bmp"), image)
    specs = [
        {
            "dataset": "toy_dataset",
            "sequence": "toy_sequence",
            "raw_dir": raw_dir,
            "teacher_dir": teacher_dir,
            "target_dx_px": -2.0,
            "target_dy_px": 0.0,
            "feature_family": "toy_feature",
        }
    ]

    records, summary = module.build_gmf_roi_records(
        package,
        specs=specs,
        crop_map={("toy_dataset", "toy_sequence"): [(16, 16, 64)]},
        max_frames_per_sequence=1,
    )
    module.update_manifest_with_gmf_roi_records(package, records, summary=summary)

    manifest = json.loads((package / "manifest.json").read_text(encoding="utf-8"))
    assert len(records) == 2
    assert records[0]["role"] == module.GMF_ROI_ROLE
    assert records[0]["gmf_roi_training"] is True
    assert records[0]["crop_x"] == 16
    assert records[0]["crop_y"] == 16
    assert manifest["role_counts"][module.GMF_ROI_ROLE] == 2
    assert manifest["r62_gmf_roi_motion_pair_count"] == 1
    assert manifest["r62_gmf_roi_motion_summary"]["toy_dataset/toy_sequence"]["gmf_roi_pairs"] == 1

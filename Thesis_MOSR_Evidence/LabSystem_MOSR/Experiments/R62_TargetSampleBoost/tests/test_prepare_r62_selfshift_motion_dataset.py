from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import cv2
import numpy as np


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "prepare_r62_selfshift_motion_dataset.py"


def load_module():
    spec = importlib.util.spec_from_file_location("prepare_r62_selfshift_motion_dataset", SCRIPT_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _center_of_mass_x(image: np.ndarray) -> float:
    yy, xx = np.mgrid[: image.shape[0], : image.shape[1]]
    weight = image.astype(np.float64)
    return float((xx * weight).sum() / max(float(weight.sum()), 1.0))


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
        "polarity_counts": {"bright": 1, "dark": 1},
    }
    (package / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")


def test_negative_dx_selfshift_moves_pattern_left():
    module = load_module()
    image = np.zeros((48, 48), dtype=np.uint8)
    cv2.circle(image, (26, 24), 4, 255, -1)

    shifted = module.shift_image_subpixel(image, dx=-3.0, dy=0.0)

    assert _center_of_mass_x(shifted) < _center_of_mass_x(image) - 2.5


def test_write_selfshift_pair_updates_manifest_counts(tmp_path: Path):
    module = load_module()
    package = tmp_path / "pkg"
    _write_minimal_manifest(package)
    raw = np.full((64, 64), 25, dtype=np.uint8)
    cv2.rectangle(raw, (20, 18), (44, 46), 210, -1)
    teacher = raw.copy()

    records = module.write_selfshift_pair(
        package_dir=package,
        stage="stage_40_test_selfshift",
        dataset="toy_ds",
        sequence="toy_seq",
        raw_crop=raw,
        teacher_crop=teacher,
        dx=-2.5,
        dy=0.0,
        sequence_index=7,
        patch_index=3,
        source_frame_name="toy.bmp",
        crop_x=11,
        crop_y=13,
        feature_family="toy_feature",
    )
    module.update_manifest_with_selfshift_records(
        package,
        records,
        stage="stage_40_test_selfshift",
        summary={"toy_ds/toy_seq": {"selfshift_pairs": 1}},
    )

    manifest = json.loads((package / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["total_pairs"] == 2
    assert manifest["geometry_count"] == 2
    assert manifest["role_counts"]["target_real_selfshift_motion_pair"] == 2
    assert manifest["r62_selfshift_motion_pair_count"] == 1
    assert (package / records[0]["package_src"]).exists()
    assert (package / records[1]["motion_meta"]).exists()

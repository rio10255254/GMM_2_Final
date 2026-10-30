from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import cv2
import numpy as np


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "add_r62_lowmag_dualroi_data.py"


def load_module():
    spec = importlib.util.spec_from_file_location("add_r62_lowmag_dualroi_data", SCRIPT_PATH)
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


def test_lowmag_dualroi_defaults_split_dot_and_square_rois():
    module = load_module()

    assert module.LOWMAG_DUALROI_STAGE.startswith("stage_40_")
    dot_rois = module.lowmag_dot_rois_for_spec({"dataset": "20260704_20x_5x", "sequence": "5x_1um"})
    square_rois = module.lowmag_square_rois_for_spec({"dataset": "20260704_20x_5x", "sequence": "5x_1um"})

    assert dot_rois
    assert square_rois
    assert dot_rois != square_rois


def test_build_lowmag_dualroi_records_marks_dot_and_square_roles(tmp_path: Path):
    module = load_module()
    package = tmp_path / "pkg"
    _write_minimal_manifest(package)
    raw_dir = tmp_path / "raw"
    r61_dir = tmp_path / "r61"
    raw_dir.mkdir()
    r61_dir.mkdir()
    raw = np.full((96, 96), 120, dtype=np.uint8)
    cv2.rectangle(raw, (20, 20), (76, 76), 180, -1)
    r61 = raw.copy()
    cv2.circle(r61, (48, 48), 12, 230, -1)
    cv2.imwrite(str(raw_dir / "frame_0000.bmp"), raw)
    cv2.imwrite(str(r61_dir / "frame_0000.bmp"), r61)
    specs = [
        {
            "dataset": "toy_dataset",
            "sequence": "toy_sequence",
            "raw_dir": raw_dir,
            "teacher_dir": r61_dir,
            "target_dx_px": -1.5,
            "target_dy_px": 0.0,
            "feature_family": "toy_lowmag",
        }
    ]

    records, summary = module.build_lowmag_dualroi_records(
        package,
        specs=specs,
        dot_crop_map={("toy_dataset", "toy_sequence"): [(0, 0, 64)]},
        square_crop_map={("toy_dataset", "toy_sequence"): [(16, 16, 64)]},
        max_frames_per_sequence=1,
    )
    module.update_manifest_with_lowmag_dualroi_records(package, records, summary=summary)

    roles = {record["role"] for record in records}
    manifest = json.loads((package / "manifest.json").read_text(encoding="utf-8"))
    assert len(records) == 4
    assert module.LOWMAG_DOT_ROLE in roles
    assert module.LOWMAG_SQUARE_ROLE in roles
    assert manifest["role_counts"][module.LOWMAG_DOT_ROLE] == 2
    assert manifest["role_counts"][module.LOWMAG_SQUARE_ROLE] == 2
    assert manifest["r62_lowmag_dualroi_pair_count"] == 2
    assert summary["toy_dataset/toy_sequence"]["dot_pairs"] == 1
    assert summary["toy_dataset/toy_sequence"]["square_pairs"] == 1


def test_refresh_grouped_split_uses_updated_manifest(monkeypatch, tmp_path: Path):
    module = load_module()
    captured: dict[str, object] = {}

    def fake_prepare_grouped_fixed_split(*, package_dir, manifest, val_ratio, seed):
        captured["package_dir"] = package_dir
        captured["manifest"] = manifest
        captured["val_ratio"] = val_ratio
        captured["seed"] = seed
        return {"split_dir": str(tmp_path / "split"), "train_count": 8, "val_count": 2}

    monkeypatch.setattr(module, "prepare_grouped_fixed_split", fake_prepare_grouped_fixed_split)
    manifest = {"pairs": [{"package_src": "src/new_record.bmp"}]}

    info = module.refresh_grouped_split(tmp_path, manifest, val_ratio=0.2, seed=7)

    assert info["train_count"] == 8
    assert captured["package_dir"] == tmp_path
    assert captured["manifest"] is manifest
    assert captured["val_ratio"] == 0.2
    assert captured["seed"] == 7

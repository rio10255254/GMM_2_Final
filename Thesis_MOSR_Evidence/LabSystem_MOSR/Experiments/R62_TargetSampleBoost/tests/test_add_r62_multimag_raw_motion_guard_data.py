from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import cv2
import numpy as np


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "add_r62_multimag_raw_motion_guard_data.py"


def load_module():
    spec = importlib.util.spec_from_file_location("add_r62_multimag_raw_motion_guard_data", SCRIPT_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _write_frame(path: Path, *, value: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    image = np.full((96, 96), value, dtype=np.uint8)
    image[24:72, 36:60] = min(255, value + 40)
    cv2.imwrite(str(path), image)


def test_default_guard_rois_include_20x_dot_and_5x_square_regions():
    module = load_module()

    assert module.raw_guard_rois_for_spec({"dataset": "20260704_20x_5x", "sequence": "20x_1um"})
    tags = [roi.tag for roi in module.raw_guard_rois_for_spec({"dataset": "20260704_20x_5x", "sequence": "5x_1um"})]

    assert "dot_grid_a" in tags
    assert "square_block" in tags
    assert module.MULTIMAG_RAW_GUARD_STAGE.startswith("stage_40_")


def test_build_raw_guard_records_use_raw_as_teacher_and_mark_role(tmp_path: Path):
    module = load_module()
    package = tmp_path / "pkg"
    (package / "src").mkdir(parents=True)
    (package / "lbl").mkdir(parents=True)
    (package / "geom").mkdir(parents=True)
    (package / "manifest.json").write_text(
        json.dumps({"profile": "toy", "pairs": [], "role_counts": {}, "total_pairs": 0}),
        encoding="utf-8",
    )
    raw_dir = tmp_path / "raw"
    _write_frame(raw_dir / "frame_0000.bmp", value=30)
    _write_frame(raw_dir / "frame_0001.bmp", value=35)
    specs = [
        {
            "dataset": "toy_dataset",
            "sequence": "toy_sequence",
            "raw_dir": raw_dir,
            "target_dx_px": -2.0,
            "target_dy_px": 0.0,
            "feature_family": "toy_multimag",
        }
    ]

    records, summary = module.build_multimag_raw_guard_records(
        package,
        specs=specs,
        roi_map={("toy_dataset", "toy_sequence"): [module.RawGuardRoi("toy_roi", 8, 8, 64)]},
        max_frames_per_sequence=2,
    )
    module.update_manifest_with_multimag_raw_guard_records(package, records, summary=summary)

    manifest = json.loads((package / "manifest.json").read_text(encoding="utf-8"))
    assert len(records) == 4
    assert {record["role"] for record in records} == {module.MULTIMAG_RAW_GUARD_ROLE}
    assert records[0]["teacher_source"] == "raw_same_frame"
    assert records[0]["multimag_raw_motion_guard"] is True
    assert records[0]["crop_tag"] == "toy_roi"
    assert manifest["role_counts"][module.MULTIMAG_RAW_GUARD_ROLE] == 4
    assert manifest["r62_multimag_raw_guard_pair_count"] == 2
    assert summary["toy_dataset/toy_sequence"]["raw_guard_pairs"] == 2


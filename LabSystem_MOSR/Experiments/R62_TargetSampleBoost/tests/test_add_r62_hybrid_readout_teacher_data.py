from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import numpy as np


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "add_r62_hybrid_readout_teacher_data.py"


def load_module():
    spec = importlib.util.spec_from_file_location("add_r62_hybrid_readout_teacher_data", SCRIPT_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_hybrid_teacher_mapping_uses_best_readout_sources() -> None:
    module = load_module()

    assert module.hybrid_teacher_source_for_key(("20260702_100MG", "x_1um")) == "v20"
    assert module.hybrid_teacher_source_for_key(("20260704_20x_5x", "5x_0p5um")) == "v31_externaldetail35"
    assert "r62_v20_gmfroi" in str(module.DEFAULT_HYBRID_TEACHER_DIRS[("20260702_100MG", "x_1um")])
    assert "r62_v31_v28_externaldetail35" in str(
        module.DEFAULT_HYBRID_TEACHER_DIRS[("20260704_20x_5x", "5x_0p5um")]
    )


def test_write_hybrid_teacher_pair_uses_dedicated_role_stage_and_source(tmp_path: Path) -> None:
    module = load_module()
    raw = np.zeros((16, 16), dtype=np.uint8)
    raw[4:12, 4:12] = 64
    teacher = np.zeros((16, 16), dtype=np.uint8)
    teacher[4:12, 4:12] = 128

    records = module.write_hybrid_teacher_pair(
        package_dir=tmp_path,
        dataset="toy_dataset",
        sequence="toy_seq",
        raw_crop=raw,
        teacher_crop=teacher,
        dx=1.25,
        dy=0.0,
        sequence_index=3,
        patch_index=2,
        source_frame_name="frame_0000.bmp",
        crop_x=10,
        crop_y=20,
        crop_tag="toy_roi",
        feature_family="dot_grid",
        teacher_source="v31_externaldetail35",
    )

    assert len(records) == 2
    assert records[0]["role"] == module.HYBRID_TEACHER_ROLE
    assert records[0]["package_src"].startswith(f"src/{module.HYBRID_TEACHER_STAGE}/")
    assert records[0]["label_source"] == "hybrid_best_readout_teacher_shifted_exactly_with_raw_texture"
    assert records[0]["teacher_source"] == "v31_externaldetail35"
    assert records[1]["motion_dx_px"] == 1.25
    assert (tmp_path / records[0]["package_src"]).is_file()
    assert (tmp_path / records[0]["package_lbl"]).is_file()

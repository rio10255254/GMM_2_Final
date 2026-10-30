from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import numpy as np


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "add_r62_stability_shape_teacher_data.py"


def load_module():
    spec = importlib.util.spec_from_file_location("add_r62_stability_shape_teacher_data", SCRIPT_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_stability_teacher_mapping_excludes_untrusted_5x_1um() -> None:
    module = load_module()

    keys = [(str(spec["dataset"]), str(spec["sequence"])) for spec in module.stability_teacher_specs()]

    assert ("20260704_20x_5x", "5x_1um") not in keys
    assert ("20260702_100MG", "x_1um") in keys
    assert module.stability_teacher_source_for_key(("20260702_100MG", "x_1um")) == "v20"
    assert module.stability_teacher_source_for_key(("20260702_100MG", "x_0p5um")) == "v20_detail50"
    assert module.stability_teacher_source_for_key(("20260704_20x_5x", "20x_0p5um")) == "v28"
    assert module.stability_teacher_source_for_key(("20260704_20x_5x", "5x_0p5um")) == "v28_detail35"


def test_v20_shape_teacher_preset_routes_square_sequences_to_v20() -> None:
    module = load_module()

    sources = module.TEACHER_PRESET_SOURCES[module.V20_SHAPE_TEACHER_PRESET]
    dirs = module.TEACHER_PRESET_DIRS[module.V20_SHAPE_TEACHER_PRESET]

    assert sources[("20260704_20x_5x", "20x_1um")] == "v20"
    assert sources[("20260704_20x_5x", "20x_0p5um")] == "v20"
    assert sources[("20260704_20x_5x", "5x_0p5um")] == "v20"
    assert "r62_v20_gmfroi" in str(dirs[("20260704_20x_5x", "5x_0p5um")])
    assert ("20260704_20x_5x", "5x_1um") not in sources


def test_measurement_view_teacher_preset_routes_each_sequence_to_best_trusted_readout() -> None:
    module = load_module()

    sources = module.TEACHER_PRESET_SOURCES[module.MEASUREMENT_VIEW_TEACHER_PRESET]
    dirs = module.TEACHER_PRESET_DIRS[module.MEASUREMENT_VIEW_TEACHER_PRESET]

    assert sources[("20260702_100MG", "x_1um")] == "unsharp_v35"
    assert sources[("20260702_100MG", "x_0p5um")] == "dog_raw"
    assert sources[("20260704_20x_5x", "20x_1um")] == "morph_raw"
    assert sources[("20260704_20x_5x", "20x_0p5um")] == "unsharp_v35"
    assert sources[("20260704_20x_5x", "5x_0p5um")] == "v31"
    assert "proc_dog_raw_x_0p5um" in str(dirs[("20260702_100MG", "x_0p5um")])
    assert "proc_morph_raw_20x_1um" in str(dirs[("20260704_20x_5x", "20x_1um")])
    assert "r62_v31_v28_externaldetail35" in str(dirs[("20260704_20x_5x", "5x_0p5um")])
    assert ("20260704_20x_5x", "5x_1um") not in sources


def test_safe_measurement_view_teacher_preset_keeps_100mg_1um_on_v35_teacher() -> None:
    module = load_module()

    sources = module.TEACHER_PRESET_SOURCES[module.SAFE_MEASUREMENT_VIEW_TEACHER_PRESET]
    dirs = module.TEACHER_PRESET_DIRS[module.SAFE_MEASUREMENT_VIEW_TEACHER_PRESET]

    assert sources[("20260702_100MG", "x_1um")] == "v35"
    assert sources[("20260702_100MG", "x_0p5um")] == "dog_raw"
    assert sources[("20260704_20x_5x", "20x_1um")] == "morph_raw"
    assert sources[("20260704_20x_5x", "20x_0p5um")] == "unsharp_v35"
    assert sources[("20260704_20x_5x", "5x_0p5um")] == "v31"
    assert "r62_v35_aggressive_mtb500_psfoff_x_1um" in str(dirs[("20260702_100MG", "x_1um")])
    assert ("20260704_20x_5x", "5x_1um") not in sources


def test_write_stability_teacher_pair_uses_dedicated_stage_and_role(tmp_path: Path) -> None:
    module = load_module()
    raw = np.zeros((16, 16), dtype=np.uint8)
    raw[3:13, 3:13] = 64
    teacher = np.zeros((16, 16), dtype=np.uint8)
    teacher[4:12, 4:12] = 128

    records = module.write_stability_teacher_pair(
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
        feature_family="square_grid",
        teacher_source="v28_detail35",
    )

    assert len(records) == 2
    assert records[0]["role"] == module.STABILITY_TEACHER_ROLE
    assert records[0]["package_src"].startswith(f"src/{module.STABILITY_TEACHER_STAGE}/")
    assert records[0]["label_source"] == "stability_shape_teacher_shifted_exactly_with_raw_texture"
    assert records[0]["teacher_source"] == "v28_detail35"
    assert records[1]["motion_dx_px"] == 1.25
    assert (tmp_path / records[0]["package_src"]).is_file()
    assert (tmp_path / records[0]["package_lbl"]).is_file()

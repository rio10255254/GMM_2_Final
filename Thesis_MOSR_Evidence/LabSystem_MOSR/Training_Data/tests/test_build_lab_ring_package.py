from __future__ import annotations

import importlib.util
from pathlib import Path

import cv2
import numpy as np
import pytest


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "build_lab_ring_package.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("build_lab_ring_package", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _write_img(path: Path, value: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    img = np.full((8, 8), value, dtype=np.uint8)
    assert cv2.imwrite(str(path), img)


def test_build_ring_package_pairs_lab_generated_images(tmp_path: Path) -> None:
    mod = _load_module()
    training_root = tmp_path / "Training_Data"
    for stage in ("stage_08_annulus_focus", "stage_09_annulus_non_overlap"):
        for idx in range(2):
            name = f"{idx:04d}.bmp"
            _write_img(training_root / "generated" / stage / name, 20 + idx)
            _write_img(training_root / "generated_convolved" / stage / name, 40 + idx)

    manifest = mod.build_ring_package(
        training_root=training_root,
        stages=("stage_08_annulus_focus", "stage_09_annulus_non_overlap"),
        max_pairs=3,
        force=True,
        link_mode="copy",
    )

    src_files = sorted((training_root / "tra_src_ring").glob("*"))
    lbl_files = sorted((training_root / "tra_lbl_ring").glob("*"))
    assert manifest["total_pairs"] == 3
    assert len(src_files) == 3
    assert [p.name for p in src_files] == [p.name for p in lbl_files]
    assert all("stage_" in p.name for p in src_files)


def test_build_ring_package_rejects_missing_label(tmp_path: Path) -> None:
    mod = _load_module()
    training_root = tmp_path / "Training_Data"
    _write_img(
        training_root / "generated_convolved" / "stage_08_annulus_focus" / "0000.bmp",
        40,
    )

    with pytest.raises(ValueError, match="missing labels"):
        mod.build_ring_package(
            training_root=training_root,
            stages=("stage_08_annulus_focus",),
            max_pairs=None,
            force=True,
            link_mode="copy",
        )

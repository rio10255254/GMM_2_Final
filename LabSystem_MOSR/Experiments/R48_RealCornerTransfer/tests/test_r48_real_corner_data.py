from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import cv2
import numpy as np
import pytest


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "r48_real_corner_data.py"


def load_module():
    spec = importlib.util.spec_from_file_location("r48_real_corner_data", SCRIPT_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _write_image(path: Path, value: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    img = np.full((64, 64), value, dtype=np.uint8)
    ok, encoded = cv2.imencode(path.suffix, img)
    assert ok
    path.write_bytes(encoded.tobytes())


def _write_array(path: Path, image: np.ndarray) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    ok, encoded = cv2.imencode(path.suffix, image)
    assert ok
    path.write_bytes(encoded.tobytes())


def _write_pair(root: Path, stage: str, name: str, value: int = 128) -> None:
    src = root / "Training_Data" / "generated_convolved" / stage / name
    lbl = root / "Training_Data" / "generated" / stage / name
    _write_image(src, max(0, value - 20))
    _write_image(lbl, value)


def _write_ring_pair(root: Path, name: str) -> None:
    src = root / "Training_Data" / "tra_src_ring" / name
    lbl = root / "Training_Data" / "tra_lbl_ring" / name
    _write_image(src, 64)
    _write_image(lbl, 200)


def _fake_repo(tmp_path: Path) -> Path:
    module = load_module()
    for idx in range(1000):
        _write_ring_pair(tmp_path, f"{idx:04d}.bmp")
    for stage, quota in module.TRAIN_SHAPE_QUOTAS.items():
        for idx in range(quota):
            _write_pair(tmp_path, stage, f"{idx:04d}.bmp", 120)
    for stage, quota in module.TRAIN_MICRO_QUOTAS.items():
        for idx in range(quota):
            _write_pair(tmp_path, stage, f"{idx:04d}.bmp", 140)
    for stage, quota in module.TRAIN_BOUNDARY_QUOTAS.items():
        val_quota = module.VAL_BOUNDARY_QUOTAS.get(stage, 0)
        for idx in range(quota + val_quota):
            _write_pair(tmp_path, stage, f"{idx:04d}.bmp", 220)
    for stage, quota in module.TRAIN_REAL_BG_QUOTAS.items():
        val_quota = module.VAL_REAL_BG_QUOTAS.get(stage, 0)
        for idx in range(quota + val_quota):
            _write_pair(tmp_path, stage, f"{idx:04d}.bmp", 180)
    return tmp_path


def test_real_corner_sample_is_deterministic_and_has_geometry():
    module = load_module()

    a = module.generate_real_corner_sample(
        index=13,
        stage=module.STAGE_53_REAL_CORNER,
        size=192,
        base_seed=4848,
    )
    b = module.generate_real_corner_sample(
        index=13,
        stage=module.STAGE_53_REAL_CORNER,
        size=192,
        base_seed=4848,
    )

    assert a.clean.dtype == np.uint8
    assert a.clean.shape == (192, 192)
    assert np.array_equal(a.clean, b.clean)
    assert np.array_equal(a.boundary, b.boundary)
    assert np.array_equal(a.centerline, b.centerline)
    assert np.array_equal(a.distance, b.distance)
    assert int(a.clean.max()) - int(a.clean.min()) >= 120
    assert module.estimate_corner_count(a.clean) >= 12
    assert 0 < np.count_nonzero(a.boundary) < a.boundary.size
    assert 0 < np.count_nonzero(a.centerline) < a.centerline.size
    assert a.distance.dtype == np.float32
    assert float(a.distance.max()) > 1.0


def test_real_texture_stage_uses_real_patch_style(tmp_path: Path):
    module = load_module()
    real_root = tmp_path / "real"
    real_root.mkdir()
    yy, xx = np.mgrid[0:256, 0:256]
    real = ((xx * 0.65 + yy * 0.25) % 255).astype(np.uint8)
    _write_array(real_root / "real_000.bmp", real)

    sample = module.generate_real_corner_sample(
        index=3,
        stage=module.STAGE_55_REAL_TEXTURE,
        size=160,
        base_seed=4848,
        real_image_root=real_root,
    )

    assert sample.clean.shape == (160, 160)
    assert int(sample.clean.max()) - int(sample.clean.min()) >= 80
    assert module.estimate_edge_density(sample.clean) >= 0.015
    assert np.count_nonzero(sample.boundary) > 0


def test_train_profile_is_6000_pairs_and_validation_is_disjoint(tmp_path: Path):
    module = load_module()
    repo = _fake_repo(tmp_path)

    train = module.build_plan(repo, module.PROFILES["r48_real_corner_train_6000"])
    val = module.build_plan(repo, module.PROFILES["real_corner_val_unseen"])

    assert len(train.pairs) == 6000
    assert train.count_by_role == {
        "ring": 800,
        "shape": 700,
        "micro": 700,
        "boundary": 3000,
        "real_bg": 800,
    }
    assert len(val.pairs) == 1200
    assert val.count_by_role == {"boundary": 700, "real_bg": 500}
    assert set(train.source_paths).isdisjoint(val.source_paths)
    module.assert_disjoint_plans(train, val)


def test_materialize_plan_writes_geometry_sidecars_and_manifest(tmp_path: Path):
    module = load_module()
    repo = _fake_repo(tmp_path / "repo")
    out = tmp_path / "pkg"
    plan = module.build_plan(repo, module.PROFILES["r48_real_corner_train_6000"])

    manifest = module.materialize_plan(plan, out, force=False, link_mode="copy")

    assert manifest["profile"] == "r48_real_corner_train_6000"
    assert manifest["total_pairs"] == 6000
    assert manifest["geometry_sidecars"] is True
    assert Path(manifest["geom_dir"]) == out / "geom"
    first = manifest["pairs"][0]
    src_rel = Path(first["package_src"]).relative_to("src")
    assert (out / first["package_src"]).exists()
    assert (out / first["package_lbl"]).exists()
    assert (out / "geom" / "boundary" / src_rel).exists()
    assert (out / "geom" / "centerline" / src_rel).exists()
    assert (out / "geom" / "distance" / src_rel.with_suffix(".npy")).exists()
    assert manifest["geometry_count"] == 6000


def test_build_plan_rejects_missing_label(tmp_path: Path):
    module = load_module()
    stage = module.STAGE_53_REAL_CORNER
    _write_pair(tmp_path, stage, "0000.bmp")
    missing = tmp_path / "Training_Data" / "generated" / stage / "0000.bmp"
    missing.unlink()

    with pytest.raises(ValueError, match="missing labels"):
        module.build_plan(tmp_path, module.PROFILES["real_corner_val_unseen"])

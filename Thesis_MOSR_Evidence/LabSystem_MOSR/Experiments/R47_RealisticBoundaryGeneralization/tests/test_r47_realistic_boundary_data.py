from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import numpy as np
import pytest


SCRIPT_PATH = (
    Path(__file__).resolve().parents[1] / "scripts" / "r47_realistic_boundary_data.py"
)


def load_module():
    spec = importlib.util.spec_from_file_location("r47_realistic_boundary_data", SCRIPT_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _write_pair(root: Path, stage: str, name: str, payload: str = "x") -> None:
    src = root / "Training_Data" / "generated_convolved" / stage / name
    lbl = root / "Training_Data" / "generated" / stage / name
    src.parent.mkdir(parents=True, exist_ok=True)
    lbl.parent.mkdir(parents=True, exist_ok=True)
    src.write_text(f"src-{payload}", encoding="utf-8")
    lbl.write_text(f"lbl-{payload}", encoding="utf-8")


def _write_ring_pair(root: Path, name: str) -> None:
    src = root / "Training_Data" / "tra_src_ring" / name
    lbl = root / "Training_Data" / "tra_lbl_ring" / name
    src.parent.mkdir(parents=True, exist_ok=True)
    lbl.parent.mkdir(parents=True, exist_ok=True)
    src.write_text("src-ring", encoding="utf-8")
    lbl.write_text("lbl-ring", encoding="utf-8")


def _fake_repo(tmp_path: Path) -> Path:
    module = load_module()
    for idx in range(800):
        _write_ring_pair(tmp_path, f"{idx:04d}.bmp")
    for stage, quota in module.TRAIN_SHAPE_QUOTAS.items():
        for idx in range(quota):
            _write_pair(tmp_path, stage, f"{idx:04d}.bmp", f"{stage}-{idx}")
    for stage, quota in module.TRAIN_MICRO_QUOTAS.items():
        for idx in range(quota):
            _write_pair(tmp_path, stage, f"{idx:04d}.bmp", f"{stage}-{idx}")
    for stage, quota in module.TRAIN_BOUNDARY_QUOTAS.items():
        val_quota = module.VAL_BOUNDARY_QUOTAS.get(stage, 0)
        for idx in range(quota + val_quota):
            _write_pair(tmp_path, stage, f"{idx:04d}.bmp", f"{stage}-{idx}")
    for stage, quota in module.TRAIN_REAL_BG_QUOTAS.items():
        val_quota = module.VAL_REAL_BG_QUOTAS.get(stage, 0)
        for idx in range(quota + val_quota):
            _write_pair(tmp_path, stage, f"{idx:04d}.bmp", f"{stage}-{idx}")
    return tmp_path


def test_realistic_boundary_images_are_deterministic_and_edge_rich():
    module = load_module()

    a = module.generate_realistic_boundary_image(
        index=11,
        stage=module.STAGE_49_CHECKBOARD,
        size=160,
        base_seed=4747,
    )
    b = module.generate_realistic_boundary_image(
        index=11,
        stage=module.STAGE_49_CHECKBOARD,
        size=160,
        base_seed=4747,
    )

    assert a.dtype == np.uint8
    assert a.shape == (160, 160)
    assert np.array_equal(a, b)
    assert int(a.max()) - int(a.min()) >= 120
    assert module.estimate_corner_count(a) >= 10
    assert module.estimate_edge_density(a) >= 0.02


def test_real_background_stage_uses_real_patch_style(tmp_path: Path):
    module = load_module()
    real_root = tmp_path / "real"
    real_root.mkdir()
    yy, xx = np.mgrid[0:256, 0:256]
    real = ((xx * 0.6 + yy * 0.3) % 255).astype(np.uint8)
    import cv2

    assert cv2.imwrite(str(real_root / "real_000.bmp"), real)

    img = module.generate_realistic_boundary_image(
        index=3,
        stage=module.STAGE_51_REAL_BG,
        size=128,
        base_seed=4747,
        real_image_root=real_root,
    )

    assert img.dtype == np.uint8
    assert img.shape == (128, 128)
    assert int(img.max()) - int(img.min()) >= 80
    assert module.estimate_edge_density(img) >= 0.015


def test_train_profile_is_exactly_4000_pairs_and_validation_is_disjoint(tmp_path: Path):
    module = load_module()
    repo = _fake_repo(tmp_path)

    train = module.build_plan(repo, module.PROFILES["r47_realistic_boundary_train_4000"])
    val = module.build_plan(repo, module.PROFILES["realistic_boundary_val_unseen"])

    assert len(train.pairs) == 4000
    assert train.count_by_role == {
        "ring": 700,
        "shape": 700,
        "micro": 700,
        "boundary": 1200,
        "real_bg": 700,
    }
    assert val.count_by_role == {"boundary": 600, "real_bg": 200}
    assert set(train.source_paths).isdisjoint(val.source_paths)
    module.assert_disjoint_plans(train, val)


def test_build_plan_rejects_missing_label(tmp_path: Path):
    module = load_module()
    stage = module.STAGE_49_CHECKBOARD
    _write_pair(tmp_path, stage, "0000.bmp")
    missing = tmp_path / "Training_Data" / "generated" / stage / "0000.bmp"
    missing.unlink()

    with pytest.raises(ValueError, match="missing labels"):
        module.build_plan(tmp_path, module.PROFILES["realistic_boundary_val_unseen"])


def test_materialize_plan_writes_parallel_tree_and_manifest(tmp_path: Path):
    module = load_module()
    repo = _fake_repo(tmp_path / "repo")
    out = tmp_path / "pkg"
    plan = module.build_plan(repo, module.PROFILES["r47_realistic_boundary_train_4000"])

    manifest = module.materialize_plan(plan, out, force=False, link_mode="copy")

    assert manifest["profile"] == "r47_realistic_boundary_train_4000"
    assert manifest["total_pairs"] == 4000
    assert manifest["count_by_role"]["boundary"] == 1200
    assert (out / "src" / "ring" / "0000.bmp").read_text(encoding="utf-8") == "src-ring"
    boundary_rows = [row for row in manifest["pairs"] if row["role"] == "boundary"]
    real_bg_rows = [row for row in manifest["pairs"] if row["role"] == "real_bg"]
    assert boundary_rows
    assert real_bg_rows
    assert all("stage_40_boundary_mixed" in row["package_src"] for row in boundary_rows)
    assert all("stage_40_boundary_mixed" in row["package_src"] for row in real_bg_rows)


def test_materialized_paths_use_trainer_recognized_role_directories(tmp_path: Path):
    module = load_module()
    repo = _fake_repo(tmp_path / "repo")
    out = tmp_path / "pkg"
    plan = module.build_plan(repo, module.PROFILES["r47_realistic_boundary_train_4000"])

    manifest = module.materialize_plan(plan, out, force=False, link_mode="copy")

    recognized_prefixes = tuple(
        [f"stage_{idx:02d}" for idx in range(1, 8)]
        + [f"stage_{idx:02d}" for idx in range(29, 34)]
        + [f"stage_{idx:02d}" for idx in range(34, 41)]
    )
    bad_paths = [
        row["package_src"]
        for row in manifest["pairs"]
        if not (
            Path(row["package_src"]).parts[1] == "ring"
            or Path(row["package_src"]).parts[1].startswith(recognized_prefixes)
        )
    ]
    assert bad_paths == []

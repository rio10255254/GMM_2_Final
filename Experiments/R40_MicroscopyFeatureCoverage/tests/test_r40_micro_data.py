from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import numpy as np
import pytest


REPO = Path(__file__).resolve().parents[3]
SCRIPT_PATH = REPO / "Experiments" / "R40_MicroscopyFeatureCoverage" / "scripts" / "r40_micro_data.py"


def load_module():
    spec = importlib.util.spec_from_file_location("r40_micro_data", SCRIPT_PATH)
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
    for idx in range(6):
        _write_ring_pair(tmp_path, f"{idx:04d}.bmp")
    for stage in (*module.SHAPE_STAGES, *module.MICRO_STAGES):
        for idx in range(100):
            _write_pair(tmp_path, stage, f"{idx:04d}.bmp", f"{stage}-{idx}")
    return tmp_path


def test_generate_micro_images_are_deterministic_and_nonblank():
    module = load_module()

    for spec in module.MICRO_STAGE_SPECS:
        a = module.generate_micro_image(spec, index=7, size=128, base_seed=1234)
        b = module.generate_micro_image(spec, index=7, size=128, base_seed=1234)

        assert a.dtype == np.uint8
        assert a.shape == (128, 128)
        assert np.array_equal(a, b)
        assert int(a.max()) - int(a.min()) >= 40


def test_capacity_train_and_validation_splits_are_disjoint(tmp_path: Path):
    module = load_module()
    repo = _fake_repo(tmp_path)

    train = module.build_plan(repo, module.PROFILES["r40_micro_capacity_train"])
    val = module.build_plan(repo, module.PROFILES["micro_val_unseen"])

    assert train.count_by_role["ring"] == 6
    assert train.count_by_role["shape"] == (
        module.PROFILES["r40_micro_capacity_train"].shape_per_stage * len(module.SHAPE_STAGES)
    )
    assert train.count_by_role["micro"] == (
        module.PROFILES["r40_micro_capacity_train"].micro_per_stage * len(module.MICRO_STAGES)
    )
    assert val.count_by_role == {"micro": 100}
    assert set(train.source_paths).isdisjoint(val.source_paths)
    module.assert_disjoint_plans(train, val)


def test_build_plan_rejects_missing_micro_label(tmp_path: Path):
    module = load_module()
    _write_pair(tmp_path, module.MICRO_STAGES[0], "0000.bmp")
    missing = tmp_path / "Training_Data" / "generated" / module.MICRO_STAGES[0] / "0000.bmp"
    missing.unlink()

    with pytest.raises(ValueError, match="missing labels"):
        module.build_plan(tmp_path, module.PROFILES["micro_val_unseen"])


def test_materialize_plan_writes_parallel_tree_and_manifest(tmp_path: Path):
    module = load_module()
    repo = _fake_repo(tmp_path / "repo")
    out = tmp_path / "pkg"
    plan = module.build_plan(repo, module.PROFILES["r40_micro_capacity_train"])

    manifest = module.materialize_plan(plan, out, force=False, link_mode="copy")

    assert (out / "src" / "ring" / "0000.bmp").read_text(encoding="utf-8") == "src-ring"
    assert (out / "lbl" / "ring" / "0000.bmp").read_text(encoding="utf-8") == "lbl-ring"
    assert manifest["profile"] == "r40_micro_capacity_train"
    assert manifest["total_pairs"] == len(plan.pairs)
    assert manifest["count_by_role"]["micro"] == (
        module.PROFILES["r40_micro_capacity_train"].micro_per_stage * len(module.MICRO_STAGES)
    )

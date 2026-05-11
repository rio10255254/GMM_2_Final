from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest


REPO = Path(__file__).resolve().parents[3]
SCRIPT_PATH = REPO / "Experiments" / "R39_ShapeGeneralization" / "scripts" / "r39_shape_data.py"


def load_module():
    spec = importlib.util.spec_from_file_location("r39_shape_data", SCRIPT_PATH)
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
    for idx in range(2):
        _write_ring_pair(tmp_path, f"{idx:04d}.bmp")
    module = load_module()
    for stage in module.SHAPE_STAGES:
        for idx in range(100):
            _write_pair(tmp_path, stage, f"{idx:04d}.tif", f"{stage}-{idx}")
    return tmp_path


def test_profile_plans_keep_shape_validation_unseen(tmp_path: Path):
    module = load_module()
    repo = _fake_repo(tmp_path)

    safe = module.build_plan(repo, module.PROFILES["r39_shape_mix_safe"])
    strong = module.build_plan(repo, module.PROFILES["r39_shape_mix_strong"])
    val = module.build_plan(repo, module.PROFILES["shape_val_unseen"])

    assert safe.count_by_role["ring"] == 2
    assert strong.count_by_role["ring"] == 2
    assert val.count_by_role.get("ring", 0) == 0
    assert safe.count_by_role["shape"] < strong.count_by_role["shape"]
    assert set(safe.source_paths).isdisjoint(val.source_paths)
    assert set(strong.source_paths).isdisjoint(val.source_paths)


def test_validate_plan_rejects_missing_label(tmp_path: Path):
    module = load_module()
    _write_pair(tmp_path, module.SHAPE_STAGES[0], "0000.tif")
    missing = tmp_path / "Training_Data" / "generated" / module.SHAPE_STAGES[0] / "0000.tif"
    missing.unlink()

    with pytest.raises(ValueError, match="missing labels"):
        module.build_plan(tmp_path, module.PROFILES["shape_val_unseen"])


def test_materialize_plan_creates_parallel_tree_and_manifest(tmp_path: Path):
    module = load_module()
    repo = _fake_repo(tmp_path / "repo")
    out = tmp_path / "pkg"
    plan = module.build_plan(repo, module.PROFILES["r39_shape_mix_safe"])

    manifest = module.materialize_plan(plan, out, force=False, link_mode="copy")

    assert (out / "src" / "ring" / "0000.bmp").read_text(encoding="utf-8") == "src-ring"
    assert (out / "lbl" / "ring" / "0000.bmp").read_text(encoding="utf-8") == "lbl-ring"
    assert manifest["profile"] == "r39_shape_mix_safe"
    assert manifest["total_pairs"] == len(plan.pairs)
    assert manifest["count_by_role"]["ring"] == 2
    assert manifest["count_by_role"]["shape"] == module.PROFILES["r39_shape_mix_safe"].shape_train_per_stage * len(module.SHAPE_STAGES)

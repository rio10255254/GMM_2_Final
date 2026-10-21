from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import numpy as np
import torch
from torch import nn


ROOT = Path(__file__).resolve().parents[1]


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def test_01_locked_counts_and_splits() -> None:
    config = json.loads((ROOT / "config" / "experiment.json").read_text(encoding="utf-8"))
    assert sum(config["dataset"]["roles"].values()) == 1280
    assert sum(config["dataset"]["degradation_quota_per_2560_renderings"].values()) == 2560
    assert config["dataset"]["total_views"] == 5120
    assert config["dataset"]["split_counts"]["train_views"] == 4096


def test_02_scratch_trainer_has_no_load_or_resume_surface() -> None:
    source = (ROOT / "training" / "train_r87.py").read_text(encoding="utf-8")
    assert "torch.load(" not in source
    assert "add_argument(\"--checkpoint\"" not in source
    assert "add_argument(\"--resume\"" not in source
    assert "checkpoint_loaded\": False" in source


def test_03_launcher_artifact_identity() -> None:
    source = (ROOT / "scripts" / "launch_r87.py").read_text(encoding="utf-8")
    assert "trainer.MODEL_NAME_BASE = trainer.CFG.MODEL_NAME" in source


def test_04_model_has_no_imagewide_module() -> None:
    model_module = load_module("r87_test_model_modules", ROOT / "model" / "r87_model.py")
    model = model_module.build_model(base=16)
    forbidden = (nn.GroupNorm, nn.BatchNorm2d, nn.InstanceNorm2d, nn.AdaptiveAvgPool2d, nn.AdaptiveMaxPool2d)
    assert not any(isinstance(module, forbidden) for module in model.modules())


def test_05_random_initialization_is_raw_identity() -> None:
    model_module = load_module("r87_test_model_identity", ROOT / "model" / "r87_model.py")
    torch.manual_seed(870031)
    model = model_module.build_model(base=16).eval()
    source = torch.rand(1, 1, 128, 160).clamp(1e-3, 1 - 1e-3)
    with torch.no_grad():
        output = model(source)
    assert torch.max(torch.abs(output - source)).item() < 1e-6


def test_06_smoke_dataset_audit_and_scene_isolation() -> None:
    package = ROOT / "data" / "r87_smoke_scene_pairs"
    audit = json.loads((package / "audit.json").read_text(encoding="utf-8"))
    manifest = json.loads((package / "manifest.json").read_text(encoding="utf-8"))
    assert audit["passed"] is True
    scene_splits: dict[str, set[str]] = {}
    for record in manifest["records"]:
        scene_splits.setdefault(record["scene_id"], set()).add(record["split"])
    assert all(len(splits) == 1 for splits in scene_splits.values())
    assert all(record["real_pixels_used"] is False for record in manifest["records"])


def test_07_pair_origins_are_aligned_and_overlapping() -> None:
    trainer = load_module("r87_test_trainer_dataset", ROOT / "training" / "train_r87.py")
    package = ROOT / "data" / "r87_smoke_scene_pairs"
    trainer.DATASET_DIR = package
    manifest = json.loads((package / "manifest.json").read_text(encoding="utf-8"))
    dataset = trainer.ScenePairDataset(manifest, "train", 896, 512, 51, include_both_renderings=False)
    _, _, origins, _, _ = dataset[0]
    assert torch.all(origins % 8 == 0)
    delta = torch.abs(origins[0] - origins[1])
    assert int(delta.max()) <= 256
    assert int(delta.sum()) > 0


def test_08_float32_aligned_tile_core_matches_full() -> None:
    model_module = load_module("r87_test_model_tile", ROOT / "model" / "r87_model.py")
    torch.manual_seed(19)
    model = model_module.build_model(base=8).eval()
    with torch.no_grad():
        nn.init.normal_(model.residual_head.weight, 0.0, 0.02)
        nn.init.normal_(model.boundary_head[-1].weight, 0.0, 0.02)
    image = torch.from_numpy(np.random.default_rng(3).random((1, 1, 512, 512), dtype=np.float32))
    with torch.no_grad():
        full = model(image)
        tile = model(image[:, :, 64:448, 64:448])
    full_core = full[:, :, 192:320, 192:320]
    tile_core = tile[:, :, 128:256, 128:256]
    assert torch.max(torch.abs(full_core - tile_core)).item() < 1e-6


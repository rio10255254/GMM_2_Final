from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import torch
from torch.utils.data import WeightedRandomSampler
import cv2
import numpy as np


MODEL_DIR = Path(__file__).resolve().parents[5] / "Model"
TRAINER_PATH = MODEL_DIR / "GeoEdgeAlignSR_v1_Train_v5_NoCoord_return_v2_SimpleTest.py"


def load_trainer_module():
    sys.path.insert(0, str(MODEL_DIR))
    spec = importlib.util.spec_from_file_location("geoedge_trainer_group_sampler_test", TRAINER_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _write_manifest(package: Path, pairs: list[dict]) -> Path:
    manifest = {
        "profile": package.name,
        "r61_universal_boundary_training": True,
        "pairs": pairs,
    }
    path = package / "manifest.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return path


def _write_bmp(path: Path, value: int = 96) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    img = np.full((24, 24), value, np.uint8)
    ok, encoded = cv2.imencode(".bmp", img)
    assert ok
    path.write_bytes(encoded.tobytes())


def test_group_balance_weights_equalize_manifest_groups(tmp_path: Path):
    trainer = load_trainer_module()
    package = tmp_path / "r61_fixture"
    src_dir = package / "src"
    paths = [
        src_dir / "stage_37_r61_universal_synthetic" / "bright" / "rect" / "a.bmp",
        src_dir / "stage_37_r61_universal_synthetic" / "bright" / "rect" / "b.bmp",
        src_dir / "stage_37_r61_universal_synthetic" / "bright" / "rect" / "c.bmp",
        src_dir / "stage_37_r61_universal_synthetic" / "dark" / "ellipse" / "d.bmp",
    ]
    for path in paths:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"x")
    manifest_path = _write_manifest(
        package,
        [
            {
                "package_src": path.relative_to(package).as_posix(),
                "role": "universal_synthetic",
                "polarity": "bright" if idx < 3 else "dark",
                "shape_family": "rect" if idx < 3 else "ellipse",
                "bias_px": 2.0 if idx < 3 else 0.0,
            }
            for idx, path in enumerate(paths)
        ],
    )

    weights, summary = trainer._build_group_balance_weights(
        [str(path) for path in paths],
        src_dir=str(src_dir),
        manifest_path=str(manifest_path),
        key_fields=("shape_family", "bias_px"),
    )

    assert torch.isclose(weights[:3].sum(), weights[3], rtol=0, atol=1e-12)
    assert summary["group_count"] == 2
    assert summary["missing_manifest_rows"] == 0


def test_group_balanced_sampler_uses_weighted_sampler_with_replacement(tmp_path: Path):
    trainer = load_trainer_module()
    package = tmp_path / "r61_fixture"
    src_dir = package / "src"
    paths = []
    pairs = []
    for idx, shape in enumerate(["rect", "rect", "ellipse"]):
        path = src_dir / "stage_37_r61_universal_synthetic" / "bright" / shape / f"{idx}.bmp"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"x")
        paths.append(str(path))
        pairs.append(
            {
                "package_src": path.relative_to(package).as_posix(),
                "role": "universal_synthetic",
                "polarity": "bright",
                "shape_family": shape,
                "bias_px": 1.0,
            }
        )
    manifest_path = _write_manifest(package, pairs)

    sampler, summary = trainer._build_group_balanced_sampler(
        paths,
        src_dir=str(src_dir),
        manifest_path=str(manifest_path),
        key_fields=("shape_family", "bias_px"),
        num_samples_mult=1.5,
        generator=torch.Generator().manual_seed(7),
    )

    assert isinstance(sampler, WeightedRandomSampler)
    assert sampler.replacement is True
    assert sampler.num_samples == 4
    assert summary["enabled"] is True
    assert summary["group_count"] == 2


def test_paired_folder_exposes_manifest_bias_for_identity_guard(tmp_path: Path):
    trainer = load_trainer_module()
    package = tmp_path / "r61_fixture"
    src_dir = package / "src"
    lbl_dir = package / "lbl"
    geom_dir = package / "geom"
    rel = Path("stage_37_r61_universal_synthetic") / "bright" / "rect" / "sample.bmp"
    _write_bmp(src_dir / rel, value=90)
    _write_bmp(lbl_dir / rel, value=120)
    _write_bmp(geom_dir / "boundary" / rel, value=255)
    _write_bmp(geom_dir / "centerline" / rel, value=255)
    (geom_dir / "distance" / rel.with_suffix(".npy")).parent.mkdir(parents=True, exist_ok=True)
    np.save(geom_dir / "distance" / rel.with_suffix(".npy"), np.zeros((24, 24), np.float32))
    manifest_path = _write_manifest(
        package,
        [
            {
                "package_src": (Path("src") / rel).as_posix(),
                "role": "universal_synthetic",
                "polarity": "bright",
                "shape_family": "rect",
                "bias_px": 0.5,
            }
        ],
    )
    trainer.CFG.IDENTITY_GUARD_ENABLE = True
    trainer.CFG.TRAIN_GROUP_BALANCE_MANIFEST = str(manifest_path)

    ds = trainer.PairedGrayFolder(
        str(src_dir),
        str(lbl_dir),
        crop_size=16,
        src_paths=[str(src_dir / rel)],
        random_crop=False,
        geom_dir=str(geom_dir),
    )
    item = ds[0]

    assert "bias_px" in item["geom"]
    assert item["geom"]["bias_px"].item() == 0.5


def test_identity_guard_kd_loss_only_uses_small_bias_samples():
    trainer = load_trainer_module()
    pred = torch.zeros(2, 1, 4, 4)
    teacher = torch.ones(2, 1, 4, 4)
    geom = {
        "distance": torch.zeros(2, 1, 4, 4),
        "bias_px": torch.tensor([0.5, 2.0]),
    }

    loss = trainer.identity_guard_region_kd_loss(
        pred,
        teacher,
        geom,
        weight=3.0,
        bias_max=0.5,
        band_px=1.0,
    )

    assert torch.isclose(loss, torch.tensor(3.0))


def test_identity_guard_position_loss_ignores_large_bias_samples():
    trainer = load_trainer_module()
    pred = torch.zeros(2, 1, 16, 16)
    pred[:, :, :, 10:] = 1.0
    yy, xx = torch.meshgrid(torch.arange(16), torch.arange(16), indexing="ij")
    distance = torch.abs(xx.float() - 8.0).unsqueeze(0).unsqueeze(0).repeat(2, 1, 1, 1)
    centerline = torch.zeros(2, 1, 16, 16)
    centerline[:, :, :, 8] = 1.0

    small_geom = {
        "distance": distance,
        "centerline": centerline,
        "bias_px": torch.tensor([0.5, 2.0]),
    }
    large_geom = {
        "distance": distance,
        "centerline": centerline,
        "bias_px": torch.tensor([2.0, 2.0]),
    }

    small_loss = trainer.identity_guard_boundary_position_loss(
        pred,
        small_geom,
        weight=2.0,
        bias_max=0.5,
    )
    large_loss = trainer.identity_guard_boundary_position_loss(
        pred,
        large_geom,
        weight=2.0,
        bias_max=0.5,
    )

    assert small_loss > 0
    assert large_loss.item() == 0.0

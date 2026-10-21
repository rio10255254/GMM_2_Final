from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import cv2
import numpy as np
import pytest
import torch


ROOT = Path(__file__).resolve().parents[1]


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


MODEL = load_module("r99_test_model", ROOT / "model" / "r99_model.py")
TRAINER = load_module("r99_test_trainer", ROOT / "training" / "train_r99.py")
INFERENCE = load_module("r99_test_inference", ROOT / "inference" / "reconstruct.py")
DESIGN = json.loads((ROOT / "config" / "experiment_design.json").read_text(encoding="utf-8"))


def test_architecture_and_exact_initial_identity() -> None:
    torch.manual_seed(99)
    model = MODEL.build_model(base=24).eval()
    contract = MODEL.architecture_contract(model)
    assert contract["parameter_count"] == DESIGN["architecture"]["parameter_count"] == 2_414_795
    assert contract["geometry_is_actionable"]
    assert contract["detail_subbands"] == 6
    assert not any(isinstance(layer, torch.nn.modules.batchnorm._BatchNorm) for layer in model.modules())
    source = torch.rand(2, 1, 96, 104)
    with torch.inference_mode():
        output = model(source)
    assert torch.equal(output, source)


def test_signed_transport_direction_is_causal() -> None:
    model = MODEL.build_model(base=24).eval()
    yy, xx = torch.meshgrid(torch.arange(96), torch.arange(96), indexing="ij")
    radius = torch.sqrt((xx - 47.5).square() + (yy - 47.5).square())
    probability = torch.sigmoid((25.0 - radius) / 1.2).view(1, 1, 96, 96)
    image = probability.clone()
    positive = model._geometry_transport(image, probability, torch.ones_like(image))[0]
    negative = model._geometry_transport(image, probability, -torch.ones_like(image))[0]
    base_area = int((image >= 0.5).sum())
    assert int((positive >= 0.5).sum()) > base_area
    assert int((negative >= 0.5).sum()) < base_area


def test_crop_before_warp_matches_old_full_canvas_core() -> None:
    package = Path(DESIGN["dataset"]["source_package"])
    manifest = json.loads((package / "manifest.json").read_text(encoding="utf-8"))
    dataset = TRAINER.R99SceneDataset(package, manifest, "train", 512, 256, 3)
    index = next(i for i in range(len(dataset)) if dataset.role_at(i) == "signed_subpixel_motion")
    item = dataset[index]
    record = next(row for row in manifest["records"] if row["scene_id"] == item["scene_id"])
    target = np.load(package / record["target"], mmap_mode="r", allow_pickle=False)
    mask = np.load(package / record["mask"], mmap_mode="r", allow_pickle=False)
    sdf_q4 = np.load(package / record["sdf_q4"], mmap_mode="r", allow_pickle=False)
    sdf = cv2.resize(np.asarray(sdf_q4, np.float32) * 4.0, (dataset.canvas_size, dataset.canvas_size), interpolation=cv2.INTER_LINEAR)
    halo = 128
    core = (slice(halo, halo + 256), slice(halo, halo + 256))
    for view, observation_index in enumerate(item["observation_indices"].tolist()):
        observation = record["observations"][observation_index]
        dx, dy = float(observation["motion_dx_px"]), float(observation["motion_dy_px"])
        old_target = TRAINER.warp_u8(target, dx, dy, cv2.INTER_LANCZOS4)
        old_mask = TRAINER.warp_u8(mask, dx, dy, cv2.INTER_LINEAR)
        if abs(dx) + abs(dy) > 0:
            matrix = np.asarray([[1.0, 0.0, dx], [0.0, 1.0, dy]], np.float32)
            old_sdf = cv2.warpAffine(sdf, matrix, (dataset.canvas_size, dataset.canvas_size), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT_101)
        else:
            old_sdf = sdf
        y0, x0 = item["origins"][view].tolist()
        expected = (slice(y0 + halo, y0 + halo + 256), slice(x0 + halo, x0 + halo + 256))
        np.testing.assert_array_equal(item["target"][view, 0].numpy()[core] * 255.0, old_target[expected].astype(np.float32))
        np.testing.assert_array_equal(item["mask"][view, 0].numpy()[core] * 255.0, old_mask[expected].astype(np.float32))
        np.testing.assert_array_equal(item["sdf"][view, 0].numpy()[core], old_sdf[expected])


@pytest.mark.skipif(not torch.cuda.is_available(), reason="CUDA parity check")
def test_nonidentity_full_and_tiled_paths_match() -> None:
    torch.manual_seed(990099)
    model = MODEL.build_model(base=24).cuda().eval()
    # Activate every output branch so this is not a trivial initial-identity test.
    with torch.no_grad():
        for head in (model.low_head[-1], model.geometry_head[-1], model.transport_head[-1], model.edge_head[-1], model.texture_head[-1]):
            head.weight.normal_(0.0, 0.002)
            head.bias.normal_(0.0, 0.002)
    source = torch.rand(1, 1, 333, 517, device="cuda")
    full = INFERENCE.reconstruct_full_reference(model, source, core_size=256, halo=192)
    tiled = INFERENCE.reconstruct_tensor(model, source, core_size=256, halo=192, tile_batch=2)
    difference = (full - tiled).abs()
    assert float(difference.max()) <= 2e-6
    assert float(difference.mean()) <= 1e-8


def test_dataset_is_the_locked_procedural_package() -> None:
    package = Path(DESIGN["dataset"]["source_package"])
    manifest = json.loads((package / "manifest.json").read_text(encoding="utf-8"))
    audit = json.loads((package / "audit.json").read_text(encoding="utf-8"))
    assert audit["passed"] and audit["source_isolation_pass"] and audit["full_array_hash_audit"]
    assert manifest["content_sha256"] == DESIGN["dataset"]["source_content_sha256"]
    assert manifest["scene_count"] == 1250
    assert manifest["total_observations"] == 5000
    assert DESIGN["dataset"]["label_supersample_factor"] == 8

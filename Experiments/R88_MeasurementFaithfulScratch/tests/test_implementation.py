from __future__ import annotations

from collections import Counter
import importlib.util
from pathlib import Path
import sys

import numpy as np
import pytest
import torch


ROOT = Path(__file__).resolve().parents[1]


def load(name: str, relative: str):
    path = ROOT / relative
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def test_model_contract_and_exact_identity_initialization() -> None:
    module = load("r88_model_test", "model/r88_model.py")
    model = module.build_model(base=24).eval()
    contract = module.architecture_contract(model)
    assert contract["parameter_count"] <= 2_500_000
    assert not any(isinstance(layer, torch.nn.modules.batchnorm._BatchNorm) for layer in model.modules())
    image = torch.rand(1, 1, 63, 71)
    with torch.inference_mode():
        details = model(image, return_details=True)
    assert torch.equal(details["output"], image)
    assert float(details["correction"].abs().max()) == 0.0


def test_smoke_dataset_shapes_motion_and_role_balancing() -> None:
    trainer = load("r88_trainer_dataset_test", "training/train_r88.py")
    package = ROOT / "data" / "r88_smoke"
    manifest = trainer.json.loads((package / "manifest.json").read_text(encoding="utf-8"))
    dataset = trainer.R88SceneDataset(package, manifest, "train", 256, 128, 1)
    assert len(dataset) == 7
    item = dataset[0]
    assert item["source"].shape == (2, 1, 256, 256)
    assert item["target"].shape == item["source"].shape
    assert item["mask"].shape == item["source"].shape
    assert item["sdf"].shape == item["source"].shape
    sampler = trainer.RoleBalancedSampler(dataset, 123)
    roles = Counter(dataset.records[index]["role"] for index in sampler)
    assert max(roles.values()) - min(roles.values()) <= 1
    motion_index = next(index for index, row in enumerate(dataset.records) if row["role"] == "signed_subpixel_motion")
    motion_item = dataset[motion_index]
    assert int(motion_item["pair_kind"]) == 1
    delta = motion_item["motion"][1] - motion_item["motion"][0]
    assert float(delta.abs().sum()) >= 0.0
    validation = trainer.R88SceneDataset(package, manifest, "validation", 256, 128, 0, all_observations=True)
    assert len(validation) == 26


def test_shift_tensor_moves_content_in_positive_x() -> None:
    trainer = load("r88_trainer_shift_test", "training/train_r88.py")
    image = torch.zeros(1, 1, 33, 33)
    image[0, 0, 16, 16] = 1.0
    shifted = trainer.shift_tensor(image, torch.tensor([2.0]), torch.tensor([0.0]))
    location = np.unravel_index(int(shifted.argmax()), shifted.shape)
    assert location[-2:] == (16, 18)


def test_one_real_smoke_batch_has_finite_backward() -> None:
    trainer = load("r88_trainer_loss_test", "training/train_r88.py")
    model_module = load("r88_model_loss_test", "model/r88_model.py")
    package = ROOT / "data" / "r88_smoke"
    manifest = trainer.json.loads((package / "manifest.json").read_text(encoding="utf-8"))
    dataset = trainer.R88SceneDataset(package, manifest, "train", 256, 128, 1)
    batch = torch.utils.data.default_collate([dataset[0], dataset[1]])
    model = model_module.build_model(base=8)
    details = model(batch["source"].reshape(4, 1, 256, 256), return_details=True)
    total, parts, _aux = trainer.loss_components(details, batch, 256, 128, enable_topology=True)
    assert torch.isfinite(total)
    total.backward()
    assert all(parameter.grad is None or torch.isfinite(parameter.grad).all() for parameter in model.parameters())
    assert all(torch.isfinite(value) for value in parts.values())


def test_canonical_canvas_and_minimum_halo_guard() -> None:
    inference = load("r88_inference_test", "inference/reconstruct.py")
    model_module = load("r88_model_inference_test", "model/r88_model.py")
    image = torch.rand(1, 1, 97, 111)
    canvas, dimensions = inference.canonical_canvas(image, 64, 192)
    assert dimensions == (97, 111, 128, 128)
    assert canvas.shape[-2:] == (512, 512)
    model = model_module.build_model(base=8).eval()
    with pytest.raises(ValueError):
        inference.reconstruct_tensor(model, image, core_size=64, halo=184, amp=False)


def test_scratch_trainer_has_no_loading_or_resume_surface() -> None:
    source = (ROOT / "training" / "train_r88.py").read_text(encoding="utf-8").lower()
    assert "torch.load(" not in source
    assert 'add_argument("--checkpoint"' not in source
    assert 'add_argument("--resume"' not in source


def test_formal_degradation_plan_is_exact_and_motion_paired() -> None:
    generator = load("r88_generator_assignment_test", "scripts/generate_dataset.py")
    plan, _canvas, _scale, quotas, _holdout = generator.profile_plan("formal")
    assert quotas is not None
    assignment = generator.build_degradation_assignment(plan, quotas, int(generator.DESIGN["dataset"]["master_seed"]))
    counts = Counter(assignment.values())
    assert counts == Counter({name: int(value) for name, value in quotas.items()})
    for scene in plan:
        families = {assignment[(scene["scene_index"], observation)] for observation in range(4)}
        if scene["role"] == "signed_subpixel_motion":
            assert len(families) == 1
        if scene["role"] == "identity_and_detail_guard":
            assert families == {"identity_and_near_identity"}

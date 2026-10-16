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


def test_model_contract_is_direct_bounded_and_tile_safe() -> None:
    module = load("r91_model_test", "model/r91_model.py")
    model = module.build_model(base=24).eval()
    contract = module.architecture_contract(model)
    assert contract["parameter_count"] <= 2_800_000
    assert contract["r90_backbone_preserved"] is True
    assert contract["low_branch_quarter_resolution_lowpass"] is True
    assert contract["detail_branch_multiscale_zero_dc"] is True
    assert contract["binary_confidence_gate"] is False
    assert contract["auxiliary_geometry_head"] is True
    assert not any(isinstance(layer, torch.nn.modules.batchnorm._BatchNorm) for layer in model.modules())
    image = torch.rand(1, 1, 63, 71)
    with torch.inference_mode():
        details = model(image, return_details=True)
    assert details["output"].shape == image.shape
    assert details["geometry_logits"].shape == image.shape
    assert details["detail_fine_delta"].shape == image.shape
    assert details["detail_medium_delta"].shape == image.shape
    assert bool(torch.isfinite(details["output"]).all())
    assert 0.0 < float(details["correction"].abs().max()) <= 0.35 + 1e-6


def test_smoke_dataset_structure_motion_and_goal_balancing() -> None:
    trainer = load("r91_trainer_dataset_test", "training/train_r91.py")
    package = ROOT / "data" / "r91_smoke"
    manifest = trainer.json.loads((package / "manifest.json").read_text(encoding="utf-8"))
    dataset = trainer.R91SceneDataset(package, manifest, "train", 256, 128, 1)
    assert len(dataset) == 7
    item = dataset[0]
    assert item["source"].shape == (2, 1, 256, 256)
    assert item["target"].shape == item["source"].shape
    assert item["mask"].shape == item["source"].shape
    assert item["sdf"].shape == item["source"].shape
    sampler = trainer.BundleAwareBatchSampler(dataset, 4, 123)
    for batch in sampler:
        roles = {dataset.role_at(index) for index in batch}
        if "exposure_coherent_bundle" in roles:
            assert roles == {"exposure_coherent_bundle"}
        else:
            assert "signed_subpixel_motion" in roles
            assert "identity_and_detail_guard" in roles
    motion_index = next(index for index, row in enumerate(dataset.records) if row["role"] == "signed_subpixel_motion")
    motion_item = dataset[motion_index]
    assert int(motion_item["pair_kind"]) == 1
    assert float(motion_item["crop_foreground_fraction"]) >= 0.015
    assert int(motion_item["crop_boundary_pixels"]) >= 96
    exposure_index = next(index for index, row in enumerate(dataset.records) if row["role"] == "exposure_coherent_bundle")
    exposure_item = dataset[exposure_index]
    assert int(exposure_item["pair_kind"]) == 3
    assert exposure_item["source"].shape == (4, 1, 256, 256)
    assert len({tuple(row.tolist()) for row in exposure_item["origins"]}) == 1
    assert exposure_item["observation_indices"].tolist() == [0, 1, 2, 3]
    validation = trainer.R91SceneDataset(package, manifest, "validation", 256, 128, 0, all_observations=True)
    assert len(validation) == 27


def test_shift_tensor_moves_content_in_positive_x() -> None:
    trainer = load("r91_trainer_shift_test", "training/train_r91.py")
    image = torch.zeros(1, 1, 33, 33)
    image[0, 0, 16, 16] = 1.0
    shifted = trainer.shift_tensor(image, torch.tensor([2.0]), torch.tensor([0.0]))
    location = np.unravel_index(int(shifted.argmax()), shifted.shape)
    assert location[-2:] == (16, 18)


def test_one_real_smoke_batch_has_finite_backward() -> None:
    trainer = load("r91_trainer_loss_test", "training/train_r91.py")
    model_module = load("r91_model_loss_test", "model/r91_model.py")
    package = ROOT / "data" / "r91_smoke"
    manifest = trainer.json.loads((package / "manifest.json").read_text(encoding="utf-8"))
    dataset = trainer.R91SceneDataset(package, manifest, "train", 256, 128, 1)
    sampler = trainer.BundleAwareBatchSampler(dataset, 4, 456)
    batch = torch.utils.data.default_collate([dataset[index] for index in next(iter(sampler))])
    model = model_module.build_model(base=8)
    scenes, views = batch["source"].shape[:2]
    details = model(batch["source"].reshape(scenes * views, 1, 256, 256), return_details=True)
    total, parts, _aux = trainer.loss_components(details, batch, 256, 128, 1, enable_topology=False)
    assert torch.isfinite(total)
    total.backward()
    assert all(parameter.grad is None or bool(torch.isfinite(parameter.grad).all()) for parameter in model.parameters())
    assert all(bool(torch.isfinite(value)) for value in parts.values())
    assert float(parts["topology"]) < 2.0


def test_canonical_canvas_and_minimum_halo_guard() -> None:
    inference = load("r91_inference_test", "inference/reconstruct.py")
    model_module = load("r91_model_inference_test", "model/r91_model.py")
    image = torch.rand(1, 1, 97, 111)
    canvas, dimensions = inference.canonical_canvas(image, 64, 192)
    assert dimensions == (97, 111, 128, 128)
    assert canvas.shape[-2:] == (512, 512)
    model = model_module.build_model(base=8).eval()
    with pytest.raises(ValueError):
        inference.reconstruct_tensor(model, image, core_size=64, halo=184, amp=False)


def test_inference_reads_and_writes_unicode_paths(tmp_path: Path) -> None:
    inference = load("r91_inference_unicode_test", "inference/reconstruct.py")
    for dtype, extension in ((np.uint8, ".bmp"), (np.uint16, ".tif")):
        source = np.arange(35 * 41, dtype=dtype).reshape(35, 41)
        path = tmp_path / f"位移影像_測試{extension}"
        inference.write_image(path, source)
        restored, restored_dtype = inference.read_gray(path)
        assert restored_dtype == dtype
        assert np.array_equal(restored, source)


def test_scratch_trainer_has_no_loading_or_resume_surface() -> None:
    source = (ROOT / "training" / "train_r91.py").read_text(encoding="utf-8").lower()
    assert "torch.load(" not in source
    assert 'add_argument("--checkpoint"' not in source
    assert 'add_argument("--resume"' not in source


def test_formal_degradation_plan_is_exact_and_motion_paired() -> None:
    generator = load("r91_generator_assignment_test", "scripts/generate_dataset.py")
    plan, _canvas, _scale, quotas, _holdout = generator.profile_plan("formal")
    assert quotas is not None
    assignment = generator.build_degradation_assignment(plan, quotas, int(generator.DESIGN["dataset"]["master_seed"]))
    counts = Counter(assignment.values())
    assert counts == Counter({name: int(value) for name, value in quotas.items()})
    for scene in plan:
        families = {assignment[(scene["scene_index"], observation)] for observation in range(4)}
        if scene["role"] in {"signed_subpixel_motion", "exposure_coherent_bundle"}:
            assert len(families) == 1
        if scene["role"] == "identity_and_detail_guard":
            assert families == {"identity_and_near_identity"}


def test_smoke_recoverability_has_no_target_shaped_clipping_leakage() -> None:
    generator = load("r91_generator_recoverability_test", "scripts/generate_dataset.py")
    package = ROOT / "data" / "r91_smoke"
    manifest = generator.json.loads((package / "manifest.json").read_text(encoding="utf-8"))
    audit = generator.json.loads((package / "audit.json").read_text(encoding="utf-8"))
    contract = generator.DESIGN["dataset"]["recoverability_contract"]
    assert audit["recoverability_metadata_failure_count"] == 0
    assert audit["recoverability_final_clip_fraction_max"] <= contract["maximum_final_pixelwise_clip_fraction"]
    assert audit["recoverability_global_scale_min"] >= contract["minimum_global_degradation_scale"]
    for record in manifest["records"]:
        for observation in record["observations"]:
            degradation = observation["degradation"]
            assert "recoverability_global_scale" in degradation
            assert degradation["recoverability_clip_fraction"] <= contract["maximum_final_pixelwise_clip_fraction"]


@pytest.mark.parametrize(
    ("module_name", "relative"),
    (("r91_generator_json_retry", "scripts/generate_dataset.py"), ("r91_trainer_json_retry", "training/train_r91.py")),
)
def test_progress_json_retries_windows_reader_lock(module_name: str, relative: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    module = load(module_name, relative)
    real_replace = module.os.replace
    attempts = {"count": 0}

    def temporarily_locked(source, destination):
        attempts["count"] += 1
        if attempts["count"] <= 3:
            raise PermissionError("simulated Windows reader lock")
        return real_replace(source, destination)

    monkeypatch.setattr(module.os, "replace", temporarily_locked)
    monkeypatch.setattr(module.time, "sleep", lambda _seconds: None)
    destination = tmp_path / "progress.json"
    module.json_dump(destination, {"completed_epoch": 5})
    assert module.json.loads(destination.read_text(encoding="utf-8")) == {"completed_epoch": 5}
    assert attempts["count"] == 4

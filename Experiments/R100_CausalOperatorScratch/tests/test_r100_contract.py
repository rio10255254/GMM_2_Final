from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import cv2
import numpy as np
import pytest
import torch
PROJECT_ROOT = Path(__file__).resolve().parents[3]


ROOT = Path(__file__).resolve().parents[1]


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


MODEL = load_module("r100_test_model", ROOT / "model" / "r100_model.py")
TRAINER = load_module("r100_test_trainer", ROOT / "training" / "train_r100.py")
INFERENCE = load_module("r100_test_inference", ROOT / "inference" / "reconstruct.py")
DESIGN = json.loads((ROOT / "config" / "experiment_design.json").read_text(encoding="utf-8"))


def test_architecture_has_only_bounded_causal_operations() -> None:
    torch.manual_seed(100)
    model = MODEL.build_model(base=24).eval()
    contract = MODEL.architecture_contract(model)
    assert contract["parameter_count"] == DESIGN["architecture"]["parameter_count"] == 2_390_360
    assert contract["spatial_transport_exists"] is False
    assert contract["free_image_residual_exists"] is False
    assert contract["stage_order"] == ["radiometry", "flat_denoise", "symmetric_edge", "material_texture"]
    assert contract["edge_operation_is_zero_phase"]
    assert contract["texture_excludes_structural_edges"]
    assert contract["texture_is_source_supported"]
    assert not any(isinstance(layer, torch.nn.modules.batchnorm._BatchNorm) for layer in model.modules())

    source = torch.rand(2, 1, 96, 104)
    with torch.inference_mode():
        details = model(source, return_details=True)
    initial_change_gray = (details["output"] - source).abs() * 255.0
    assert float(initial_change_gray.mean()) < 1.2
    assert float(initial_change_gray.max()) < 3.5
    for key in ("transport_delta", "transport_offset_px", "transport_dx_px", "transport_dy_px", "geometry_logits"):
        assert torch.count_nonzero(details[key]) == 0
    assert float(details["correction"].abs().max()) <= 0.35 + 1e-6
    assert float(details["edge_delta"].abs().max()) <= 0.12 + 1e-6
    assert float(details["texture_delta"].abs().max()) <= 0.18 + 1e-6


def test_latent_truth_is_unchanged_and_detail_view_is_source_supported() -> None:
    rng = np.random.default_rng(100)
    target = rng.integers(8, 248, size=(192, 192), dtype=np.uint8)
    yy, xx = np.mgrid[:192, :192]
    sdf = np.sqrt((xx - 95.5) ** 2 + (yy - 95.5) ** 2).astype(np.float32) - 48.0
    adapted_a, gain_a = TRAINER.adapt_r100_target(target, sdf, "textured_general_geometry", 17)
    adapted_b, gain_b = TRAINER.adapt_r100_target(target, sdf, "textured_general_geometry", 17)
    boundary = np.abs(sdf) <= float(DESIGN["dataset"]["target_adapter"]["boundary_margin_px"])
    np.testing.assert_array_equal(adapted_a[boundary], target[boundary])
    np.testing.assert_array_equal(adapted_a, adapted_b)
    assert gain_a == gain_b == 0.0
    np.testing.assert_array_equal(adapted_a, target)

    identity, identity_gain = TRAINER.adapt_r100_target(target, sdf, "identity_and_detail_guard", 17)
    np.testing.assert_array_equal(identity, target)
    assert identity_gain == 0.0

    detail_a = TRAINER.synthesize_detail_recovery_source(target, 17, 3, 0)
    detail_b = TRAINER.synthesize_detail_recovery_source(target, 17, 3, 0)
    detail_other_view = TRAINER.synthesize_detail_recovery_source(target, 17, 3, 1)
    np.testing.assert_array_equal(detail_a, detail_b)
    assert not np.array_equal(detail_a, detail_other_view)
    source = detail_a.astype(np.float32) / 255.0
    truth = target.astype(np.float32) / 255.0
    source_fine = source - cv2.GaussianBlur(source, (0, 0), 1.2)
    truth_fine = truth - cv2.GaussianBlur(truth, (0, 0), 1.2)
    scale = float(np.mean(source_fine * truth_fine) / max(np.mean(source_fine * source_fine), 1e-9))
    assert scale > 1.05

    augmented_a, material_gain_a = TRAINER.augment_detail_recovery_truth(target, sdf, 17, 3)
    augmented_b, material_gain_b = TRAINER.augment_detail_recovery_truth(target, sdf, 17, 3)
    np.testing.assert_array_equal(augmented_a, augmented_b)
    np.testing.assert_array_equal(augmented_a[boundary], target[boundary])
    assert material_gain_a == material_gain_b > 0.0
    assert np.mean(np.abs(augmented_a.astype(np.float32) - target.astype(np.float32))[~boundary]) > 0.1


def test_all_four_operator_heads_receive_finite_learning_signal() -> None:
    torch.manual_seed(10001)
    model = MODEL.build_model(base=24).train()
    source = torch.rand(1, 1, 96, 104)
    target = torch.clamp(source + 0.04 * torch.sin(torch.arange(104).float())[None, None, None, :], 0.0, 1.0)
    details = model(source, return_details=True)
    loss = (details["output"] - target).square().mean()
    loss.backward()
    for head in (model.radiometry_head[-1], model.denoise_head[-1], model.edge_head[-1], model.texture_head[-1]):
        assert head.weight.grad is not None
        assert bool(torch.isfinite(head.weight.grad).all())
        assert float(head.weight.grad.abs().sum()) > 0.0


@pytest.mark.skipif(not torch.cuda.is_available(), reason="CUDA parity check")
def test_nonidentity_full_and_tiled_paths_match() -> None:
    torch.manual_seed(1000100)
    model = MODEL.build_model(base=24).cuda().eval()
    with torch.no_grad():
        model.radiometry_head[-1].weight.normal_(0.0, 0.002)
        model.radiometry_head[-1].bias.normal_(0.0, 0.02)
        for head in (model.denoise_head[-1], model.edge_head[-1], model.texture_head[-1]):
            head.weight.normal_(0.0, 0.002)
            head.bias.fill_(-1.0)
    source = torch.rand(1, 1, 333, 517, device="cuda")
    full = INFERENCE.reconstruct_full_reference(model, source, core_size=256, halo=192)
    tiled = INFERENCE.reconstruct_tensor(model, source, core_size=256, halo=192, tile_batch=2)
    difference = (full - tiled).abs()
    assert float(difference.max()) <= 3e-6
    assert float(difference.mean()) <= 2e-8
    assert float((full - source).abs().mean()) > 1e-4


def test_dataset_is_locked_isolated_and_unchanged() -> None:
    package = Path(PROJECT_ROOT / DESIGN["dataset"]["source_package"])
    manifest = json.loads((package / "manifest.json").read_text(encoding="utf-8"))
    audit = json.loads((package / "audit.json").read_text(encoding="utf-8"))
    assert audit["passed"] and audit["source_isolation_pass"] and audit["full_array_hash_audit"]
    assert manifest["content_sha256"] == DESIGN["dataset"]["source_content_sha256"]
    assert manifest["scene_count"] == 1250
    assert manifest["total_observations"] == 5000
    assert DESIGN["dataset"]["reuse_existing_arrays_without_regeneration"]
    assert DESIGN["dataset"]["label_supersample_factor"] == 8
    assert DESIGN["source_isolation"]["sem_pixels_allowed"] is False
    assert DESIGN["source_isolation"]["hs100mg_structure_allowed"] is False
    assert DESIGN["dataset"]["target_adapter"]["enabled"] is False

    train = TRAINER.R100SceneDataset(package, manifest, "train", 128, 64, 3)
    index = next(
        i for i in range(len(train))
        if train.role_at(i) == "textured_general_geometry"
        and (3 + int(train.items[i][0]["scene_index"])) % 2 == 0
    )
    item = train[index]
    assert bool(item["detail_recovery_view"].all())
    validation = TRAINER.R100SceneDataset(package, manifest, "validation", 128, 64, 3)
    validation_item = validation[next(i for i in range(len(validation)) if validation.role_at(i) == "textured_general_geometry")]
    assert not bool(validation_item["detail_recovery_view"].any())

    sampler = TRAINER.BundleAwareBatchSampler(train, batch_size=18, seed=100)
    assert abs(sampler.exposure_update_share - DESIGN["dataset"]["sampling"]["exposure_bundle_update_share"]) < 0.02
    assert abs(sampler.detail_update_share - DESIGN["dataset"]["sampling"]["detail_recovery_update_share"]) < 0.02
    batches = list(iter(sampler))
    dedicated = [batch for batch in batches if len(batch) == 18 and all(train.detail_recovery_at(i) for i in batch)]
    assert len(dedicated) == sampler.detail_batch_count


def test_scratch_trainer_exposes_no_checkpoint_or_resume_argument() -> None:
    source = (ROOT / "training" / "train_r100.py").read_text(encoding="utf-8").lower()
    assert 'add_argument("--checkpoint"' not in source
    assert 'add_argument("--resume"' not in source
    assert DESIGN["training"]["scratch_guards"]["checkpoint_argument_exists"] is False
    assert DESIGN["training"]["scratch_guards"]["resume_argument_exists"] is False


def test_epoch_boundary_cleanup_and_recovery_are_explicit() -> None:
    source = (ROOT / "training" / "train_r100.py").read_text(encoding="utf-8")
    assert "del batch, source, flat, details, total, parts, _aux, scaled, gradient_norm" in source
    assert "torch.cuda.empty_cache()" in source
    assert "epoch_heartbeat.json" in source
    assert "total_validation_batches = len(loader)" in source
    assert '"phase": "synthetic_preview"' in source
    assert '"phase": "real_preview"' in source
    assert '"synthetic_preview_paths": preview_paths' in source
    assert '"real_preview_paths": real_preview_paths' in source
    assert "update_matching_launcher_state(status" in source
    assert 'update_matching_launcher_state("failed"' in source

    model = MODEL.build_model(base=24)
    ema = MODEL.build_model(base=24)
    optimizer = TRAINER.build_optimizer(model)
    payload = TRAINER.checkpoint_payload(model, ema, optimizer, 1, {"validation": None}, {"checkpoint_loaded": False})
    assert "optimizer_state_dict" in payload
    assert payload["epoch"] == 1

    recovery = (ROOT / "training" / "run_recovery_training.py").read_text(encoding="utf-8")
    assert "R100_scratch_seed1000053_20260814_180143" in recovery
    assert "epoch_036.pth.tar" in recovery

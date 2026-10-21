from __future__ import annotations

from collections import Counter
import importlib.util
import inspect
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
    module = load("r92_model_test", "model/r92_model.py")
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
    trainer = load("r92_trainer_dataset_test", "training/train_r92.py")
    package = ROOT / "data" / "r92_smoke"
    manifest = trainer.json.loads((package / "manifest.json").read_text(encoding="utf-8"))
    dataset = trainer.R92SceneDataset(package, manifest, "train", 256, 128, 1)
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
    positions = exposure_item["exposure_path_position"].tolist()
    assert len(positions) == 4
    assert min(positions) == pytest.approx(0.0)
    assert max(positions) == pytest.approx(1.0)
    validation = trainer.R92SceneDataset(package, manifest, "validation", 256, 128, 0, all_observations=True)
    assert len(validation) == 24
    validation_exposure_index = next(index for index in range(len(validation)) if validation.role_at(index) == "exposure_coherent_bundle")
    validation_exposure = validation[validation_exposure_index]
    assert validation_exposure["source"].shape == (4, 1, 256, 256)
    validation_sampler = trainer.HomogeneousViewBatchSampler(validation, batch_size=2)
    assert all(len({validation.view_count_at(index) for index in batch}) == 1 for batch in validation_sampler)


def test_shift_tensor_moves_content_in_positive_x() -> None:
    trainer = load("r92_trainer_shift_test", "training/train_r92.py")
    image = torch.zeros(1, 1, 33, 33)
    image[0, 0, 16, 16] = 1.0
    shifted = trainer.shift_tensor(image, torch.tensor([2.0]), torch.tensor([0.0]))
    location = np.unravel_index(int(shifted.argmax()), shifted.shape)
    assert location[-2:] == (16, 18)


def test_one_real_smoke_batch_has_finite_backward() -> None:
    trainer = load("r92_trainer_loss_test", "training/train_r92.py")
    model_module = load("r92_model_loss_test", "model/r92_model.py")
    package = ROOT / "data" / "r92_smoke"
    manifest = trainer.json.loads((package / "manifest.json").read_text(encoding="utf-8"))
    dataset = trainer.R92SceneDataset(package, manifest, "train", 256, 128, 1)
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
    assert "raw_geometry_preservation" in parts
    assert "low_branch_geometry_neutrality" in parts
    assert float(parts["topology"]) < 2.0


def test_continuous_geometry_guard_penalizes_only_regression() -> None:
    trainer = load("r92_trainer_geometry_guard_test", "training/train_r92.py")
    target = torch.zeros(1, 1, 64, 64)
    target[..., 16:48, 16:48] = 1.0
    raw = target.clone()
    worse = torch.roll(raw, shifts=3, dims=-1)
    preserved, low_preserved, diagnostics = trainer.continuous_raw_geometry_preservation(raw, raw, raw, target)
    regressed, low_regressed, _ = trainer.continuous_raw_geometry_preservation(worse, raw, worse, target)
    assert float(preserved) == pytest.approx(0.0)
    assert float(low_preserved) == pytest.approx(0.0)
    assert float(regressed) > 0.0
    assert float(low_regressed) > 0.0
    assert 0.0 < float(diagnostics["raw_geometry_confidence"].min()) <= 1.0


def test_recoverability_projection_is_global_and_reaches_contract() -> None:
    repair = load("r92_recoverability_projection_test", "scripts/repair_recoverability.py")
    design = repair.json.loads((ROOT / "config" / "experiment_design.json").read_text(encoding="utf-8"))
    contract = design["dataset"]["recoverability_contract"]
    target = np.full((96, 96), 12, dtype=np.uint8)
    target[20:76, 20:76] = 243
    source = np.full((96, 96), 104, dtype=np.uint8)
    source[20:76, 20:76] = 151
    original = source.copy()
    before = repair.recoverability_metrics(source, target, contract)
    assert not repair.metrics_pass(before, contract)
    projected = repair.project_candidate(source, target, {"requested_source_contrast_gray": None}, contract)
    assert projected is not None
    candidate, details = projected
    assert np.array_equal(source, original)
    assert repair.metrics_pass(repair.recoverability_metrics(candidate, target, contract), contract)
    assert 0.0 < details["projection_fraction"] <= contract["maximum_projection_fraction"]
    assert details["mean_absolute_projection_gray"] <= contract["maximum_mean_absolute_projection_gray"]


def test_same_family_rerender_seed_schedule_is_deterministic_and_distinct() -> None:
    repair = load("r92_same_family_rerender_test", "scripts/repair_unprojectable_observations.py")
    assert repair.deterministic_seed(1000, 1, 100003) == 101003
    assert repair.deterministic_seed(1000, 2, 100003) == 201006
    assert repair.deterministic_seed(1000, 1, 100019) != repair.deterministic_seed(1000, 1, 100003)


def test_exposure_span_rerender_is_ordered_and_hits_target() -> None:
    repair = load("r92_exposure_span_repair_test", "scripts/repair_exposure_span.py")
    design = repair.json.loads((ROOT / "config" / "experiment_design.json").read_text(encoding="utf-8"))
    config = design["dataset"]["continuous_exposure_path"]
    positions = [0.0, 0.3, 0.7, 1.0]
    observations = [
        {"degradation": {"exposure_coherent_profile": label, "exposure_path_position": position, "exposure": 0.86 + 0.25 * position}}
        for label, position in zip(config["labels"], positions)
    ]
    exposures = repair.normalized_exposures(observations, config)
    ordered = [exposures[label] for label in config["labels"]]
    assert all(left < right for left, right in zip(ordered, ordered[1:]))
    assert ordered[-1] - ordered[0] == pytest.approx(config["span_repair_target"])
    assert config["dark_exposure_range"][0] <= ordered[0] <= config["dark_exposure_range"][1]
    assert config["bright_exposure_range"][0] <= ordered[-1] <= config["bright_exposure_range"][1]


def test_canonical_canvas_and_minimum_halo_guard() -> None:
    inference = load("r92_inference_test", "inference/reconstruct.py")
    model_module = load("r92_model_inference_test", "model/r92_model.py")
    image = torch.rand(1, 1, 97, 111)
    canvas, dimensions = inference.canonical_canvas(image, 64, 192)
    assert dimensions == (97, 111, 128, 128)
    assert canvas.shape[-2:] == (512, 512)
    model = model_module.build_model(base=8).eval()
    with pytest.raises(ValueError):
        inference.reconstruct_tensor(model, image, core_size=64, halo=184, amp=False)


def test_nonidentity_model_has_exact_full_vs_tiled_parity() -> None:
    inference = load("r92_inference_parity_test", "inference/reconstruct.py")
    model_module = load("r92_model_parity_test", "model/r92_model.py")
    torch.manual_seed(920041)
    model = model_module.build_model(base=8).eval()
    with torch.no_grad():
        for head in (model.low_head[-1], model.detail_head[-1], model.edge_head[-1]):
            head.weight.mul_(100.0)
    image = torch.rand(1, 1, 257, 299)
    with torch.inference_mode():
        full = inference.reconstruct_full_reference(model, image, core_size=128, halo=192, amp=False)
        tiled = inference.reconstruct_tensor(model, image, core_size=128, halo=192, tile_batch=2, amp=False)
    assert float((full - image).abs().mean() * 255.0) > 0.5
    assert torch.equal(full, tiled)


def test_inference_reads_and_writes_unicode_paths(tmp_path: Path) -> None:
    inference = load("r92_inference_unicode_test", "inference/reconstruct.py")
    for dtype, extension in ((np.uint8, ".bmp"), (np.uint16, ".tif")):
        source = np.arange(35 * 41, dtype=dtype).reshape(35, 41)
        path = tmp_path / f"位移影像_測試{extension}"
        inference.write_image(path, source)
        restored, restored_dtype = inference.read_gray(path)
        assert restored_dtype == dtype
        assert np.array_equal(restored, source)


def test_inference_defaults_to_traceable_float32() -> None:
    inference = load("r92_inference_precision_test", "inference/reconstruct.py")
    tensor_signature = inspect.signature(inference.reconstruct_tensor)
    reference_signature = inspect.signature(inference.reconstruct_full_reference)
    assert tensor_signature.parameters["amp"].default is False
    assert reference_signature.parameters["amp"].default is False
    source = (ROOT / "inference" / "reconstruct.py").read_text(encoding="utf-8")
    assert 'add_argument("--amp"' in source
    assert '"precision": "bfloat16" if amp_enabled else "float32"' in source
    assert '"tile_batch": int(args.tile_batch)' in source


def test_scratch_trainer_has_no_loading_or_resume_surface() -> None:
    source = (ROOT / "training" / "train_r92.py").read_text(encoding="utf-8").lower()
    assert "torch.load(" not in source
    assert 'add_argument("--checkpoint"' not in source
    assert 'add_argument("--resume"' not in source


def test_formal_degradation_plan_is_exact_and_motion_paired() -> None:
    generator = load("r92_generator_assignment_test", "scripts/generate_dataset.py")
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
    generator = load("r92_generator_recoverability_test", "scripts/generate_dataset.py")
    package = ROOT / "data" / "r92_smoke"
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
            assert degradation["recoverability_repair_fraction"] == 0.0
            assert degradation["recoverability_clip_fraction"] <= contract["maximum_final_pixelwise_clip_fraction"]


def test_physical_transition_and_exposure_contrast_are_traceable() -> None:
    generator = load("r92_generator_transition_test", "scripts/generate_dataset.py")
    package = ROOT / "data" / "r92_smoke"
    manifest = generator.json.loads((package / "manifest.json").read_text(encoding="utf-8"))
    transition = generator.DESIGN["dataset"]["physical_transition_profile"]
    exposure_bands = generator.DESIGN["dataset"]["continuous_exposure_path"]["source_contrast_gray_bands"]
    for record in manifest["records"]:
        fraction = record["texture"]["physical_boundary_intensity_fraction"]
        assert transition["boundary_intensity_fraction_range"][0] <= fraction <= transition["boundary_intensity_fraction_range"][1]
        if record["role"] == "exposure_coherent_bundle":
            requested = sorted(round(float(obs["degradation"]["requested_source_contrast_gray"]), 3) for obs in record["observations"])
            assert len(requested) == len(exposure_bands)
            assert all(any(low <= value <= high for low, high in exposure_bands) for value in requested)


@pytest.mark.parametrize(
    ("module_name", "relative"),
    (("r92_generator_json_retry", "scripts/generate_dataset.py"), ("r92_trainer_json_retry", "training/train_r92.py")),
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

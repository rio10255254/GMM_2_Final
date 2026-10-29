"""One-batch checkpointed benchmark for R95's 896-pixel split objective path."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import time

import torch
from torch.utils.data import DataLoader
PROJECT_ROOT = Path(__file__).resolve().parents[3]


ROOT = Path(__file__).resolve().parents[1]


def load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main() -> int:
    train = load("r95_train_benchmark", ROOT / "training" / "train_r95.py")
    design = json.loads((ROOT / "config" / "experiment_design.json").read_text(encoding="utf-8"))
    recovery = json.loads((ROOT / "config" / "interruption_recovery.json").read_text(encoding="utf-8"))
    package = Path(PROJECT_ROOT / design["data"]["source_package"])
    manifest = json.loads((package / "manifest.json").read_text(encoding="utf-8"))
    checkpoint_path = (
        ROOT / "weights" / "formal" / "seed_950041"
        / "R95_scratch_seed950041_20260813_003125" / "weights" / "latest.pth.tar"
    )
    checkpoint = torch.load(checkpoint_path, map_location="cpu", weights_only=False)
    if int(checkpoint["epoch"]) != 32:
        raise RuntimeError(f"Expected epoch 32, got {checkpoint['epoch']}")

    device = torch.device("cuda:0")
    model = train.MODEL.build_model(base=int(design["architecture"]["model_width"]))
    model.load_state_dict(checkpoint["model_state_dict"], strict=True)
    model.to(device).train()
    torch.backends.cudnn.benchmark = True
    model.set_active_training_groups(None)
    stage = train.patch_for_epoch(33, recovery_policy=recovery)
    patch, core = stage["patch_size"], stage["core_size"]
    scene_batch = stage["scene_batch"]
    accumulation = stage["gradient_accumulation"]
    fraction = train.stage_truth_fraction(33)
    dataset = train.DATA.R95SceneDataset(
        package, manifest, "train", patch, core, 33,
        all_observations=False, master_seed=int(design["independence"]["seed"]),
    )
    sampler = train.DATA.RoleBalancedBatchSampler(
        dataset, scene_batch, int(design["independence"]["seed"]) + 33 * 101,
    )
    loader = DataLoader(dataset, batch_sampler=sampler, num_workers=0, pin_memory=True)
    raw_batch = next(iter(loader))
    batch, scenes, views = train.flatten_batch(raw_batch, device)
    source = batch["source"]
    divisor = float(accumulation)
    parameters = [parameter for parameter in model.parameters() if parameter.requires_grad]

    warmup = torch.zeros((1, 1, 64, 64), device=device)
    with torch.no_grad(), torch.autocast(device_type="cuda", dtype=torch.bfloat16):
        model.forward_controls(warmup)
    del warmup
    torch.cuda.synchronize(device)
    torch.cuda.empty_cache()
    free_before, total_memory = torch.cuda.mem_get_info(device)
    torch.cuda.reset_peak_memory_stats(device)
    started = time.perf_counter()

    with torch.autocast(device_type="cuda", dtype=torch.bfloat16):
        control_total, _control_values = train.control_triplet(model, batch, patch, core)
    control_prefix = train.detached_objective_gradients(
        0.55 * control_total, parameters, divisor,
    )
    del control_total, _control_values

    with torch.autocast(device_type="cuda", dtype=torch.bfloat16):
        translation = train.translation_consistency(model, source[:1])
    translation_prefixes = []
    if translation.requires_grad and float(translation.detach().abs()) > 0.0:
        translation_prefixes.append(train.detached_objective_gradients(
            0.15 * translation, parameters, divisor,
        ))
    del translation

    with torch.autocast(device_type="cuda", dtype=torch.bfloat16):
        stage_truth = {
            "sensor_clean_base": batch["noise_free_source"],
            "restoration_base": batch["optical_source"],
            "contrast_restored_base": batch["optical_source"] + batch["local_contrast_target"],
            "need_truth": batch["need_truth_s"],
            "evidence_truth": batch["evidence_truth_s"],
        }
        details = model(source, return_details=True, stage_truth=stage_truth, stage_truth_fraction=fraction)
        branch_total, _ = train.branch_losses(details, batch, patch, core)
        output_total, _ = train.full_output_losses(details, batch, patch, core)
        motion = train.motion_loss(details, batch, patch, core, scenes, views)
        cross_noise = train.cross_noise_consistency(details, batch, patch, core, scenes, views)
        primary = branch_total + output_total
        auxiliaries = [0.30 * motion, 0.25 * cross_noise]
    train.backward_common_descent(
        primary, auxiliaries, list(model.parameters()), divisor,
        return_diagnostics=False,
        primary_gradient_prefix=control_prefix,
        auxiliary_gradient_prefixes=translation_prefixes,
    )
    torch.cuda.synchronize(device)
    elapsed = time.perf_counter() - started
    free_after, _ = torch.cuda.mem_get_info(device)
    peak_allocated = torch.cuda.max_memory_allocated(device)
    peak_reserved = torch.cuda.max_memory_reserved(device)
    result = {
        "passed": all(
            parameter.grad is None or bool(torch.isfinite(parameter.grad).all())
            for parameter in model.parameters()
        ),
        "checkpoint_epoch": int(checkpoint["epoch"]),
        "patch": int(patch),
        "core": int(core),
        "scenes": int(scenes),
        "views": int(views),
        "seconds": elapsed,
        "peak_allocated_gib": peak_allocated / 2**30,
        "peak_reserved_gib": peak_reserved / 2**30,
        "free_before_gib": free_before / 2**30,
        "free_after_gib": free_after / 2**30,
        "physical_total_gib": total_memory / 2**30,
    }
    print(json.dumps(result, indent=2))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

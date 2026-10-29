"""One real 896-pixel late-phase batch, including every protected objective."""
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
    train = load("r96_large_patch_benchmark", ROOT / "training" / "train_r96.py")
    design = json.loads((ROOT / "config" / "experiment_design.json").read_text(encoding="utf-8"))
    execution = json.loads((ROOT / "config" / "execution_policy.json").read_text(encoding="utf-8"))
    package = Path(PROJECT_ROOT / design["data"]["source_package"])
    manifest = json.loads((package / "manifest.json").read_text(encoding="utf-8"))
    device = torch.device("cuda:0")
    epoch = 31
    stage = train.patch_for_epoch(epoch, recovery_policy=execution)
    patch, core = stage["patch_size"], stage["core_size"]
    scene_batch = stage["scene_batch"]
    accumulation = stage["gradient_accumulation"]
    model = train.MODEL.build_model(base=int(design["architecture"]["model_width"])).to(device).train()
    model.set_active_training_groups(None)
    dataset = train.DATA.R96SceneDataset(
        package, manifest, "train", patch, core, epoch,
        master_seed=int(design["independence"]["seed"]),
    )
    sampler = train.DATA.RoleBalancedBatchSampler(
        dataset, scene_batch, int(design["independence"]["seed"]) + epoch * 101,
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
        control_total, _ = train.control_triplet(model, batch, patch, core)
    control_prefix = train.detached_objective_gradients(0.55 * control_total, parameters, divisor)
    del control_total

    with torch.autocast(device_type="cuda", dtype=torch.bfloat16):
        clean_identity = train.clean_counterfactual_loss(model, batch, patch, core)
    protected_prefixes = [train.detached_objective_gradients(
        0.35 * clean_identity, parameters, divisor,
    )]
    del clean_identity

    with torch.autocast(device_type="cuda", dtype=torch.bfloat16):
        stage_truth = {
            "sensor_clean_base": batch["noise_free_source"],
            "restoration_base": batch["optical_source"],
            "contrast_restored_base": batch["optical_source"] + batch["local_contrast_target"],
            "need_truth": batch["need_truth_s"],
            "evidence_truth": batch["evidence_truth_s"],
        }
        details = model(source, return_details=True, stage_truth=stage_truth, stage_truth_fraction=0.0)
        branch_total, branch_values = train.branch_losses(details, batch, patch, core)
        output_total, _ = train.full_output_losses(details, batch, patch, core)
        motion = train.motion_loss(details, batch, patch, core, scenes, views)
        cross_noise = train.cross_noise_consistency(details, batch, patch, core, scenes, views)
    groups = model.parameter_groups()
    branch_names = ("nuisance", "radiometry", "local_contrast", "boundary", "texture")
    for name in branch_names:
        protected_prefixes.append(train.protected_group_gradients(
            branch_values[name], parameters, groups[name], divisor, retain_graph=True,
        ))
    train.backward_common_descent(
        branch_total + output_total,
        [0.30 * motion, 0.25 * cross_noise],
        parameters, divisor, return_diagnostics=False,
        primary_gradient_prefix=control_prefix,
        auxiliary_gradient_prefixes=protected_prefixes,
    )
    torch.cuda.synchronize(device)
    elapsed = time.perf_counter() - started
    free_after, _ = torch.cuda.mem_get_info(device)
    peak_allocated = torch.cuda.max_memory_allocated(device)
    peak_reserved = torch.cuda.max_memory_reserved(device)
    finite = all(
        parameter.grad is None or bool(torch.isfinite(parameter.grad).all())
        for parameter in model.parameters()
    )
    applied = torch.cat([
        (torch.zeros_like(parameter) if parameter.grad is None else parameter.grad).reshape(-1)
        for parameter in parameters
    ])
    branch_task_dots = {}
    for name, values in zip(branch_names, protected_prefixes[1:]):
        task = torch.cat([
            (torch.zeros_like(parameter) if value is None else value).reshape(-1)
            for parameter, value in zip(parameters, values)
        ])
        branch_task_dots[name] = float(torch.dot(applied, task))
    nonzero_groups = {
        name: any(
            parameter.grad is not None and float(parameter.grad.abs().sum()) > 0.0
            for parameter in groups[name]
        )
        for name in branch_names
    }
    result = {
        "passed": (
            finite and all(nonzero_groups.values())
            and min(branch_task_dots.values()) >= -1e-7
        ),
        "fresh_random_initialization": True,
        "checkpoint_loaded": False,
        "epoch_design": epoch,
        "patch": int(patch),
        "core": int(core),
        "scene_batch": int(scene_batch),
        "views": int(views),
        "seconds": elapsed,
        "peak_allocated_gib": peak_allocated / 2**30,
        "peak_reserved_gib": peak_reserved / 2**30,
        "free_before_gib": free_before / 2**30,
        "free_after_gib": free_after / 2**30,
        "physical_total_gib": total_memory / 2**30,
        "finite_gradients": finite,
        "nonzero_private_branch_gradients": nonzero_groups,
        "applied_update_dot_private_task": branch_task_dots,
    }
    output = ROOT / "reports" / "large_patch_preflight.json"
    output.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

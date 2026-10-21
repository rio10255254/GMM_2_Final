"""Run the D/E repair ablation after the initial R101 A/B/C falsification."""
from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.util
import json
import math
import os
import random
import sys
import time
from datetime import datetime
from pathlib import Path

import numpy as np
import torch
import torch.nn.functional as F


ROOT = Path(__file__).resolve().parents[1]


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


MODELS = load_module("r101_repair_models", ROOT / "model" / "repaired_models.py")
BASE = load_module("r101_repair_training_base", ROOT / "training" / "run_short_ablation.py")


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(temporary, path)


def state_hash(model: torch.nn.Module, common_only: bool = False) -> str:
    digest = hashlib.sha256()
    for name, value in sorted(model.state_dict().items()):
        if common_only and name.startswith("edge_mix_head."):
            continue
        digest.update(name.encode("utf-8"))
        digest.update(value.detach().cpu().contiguous().numpy().tobytes())
    return digest.hexdigest()


def charbonnier(error: torch.Tensor, weight: torch.Tensor | None = None) -> torch.Tensor:
    value = torch.sqrt(error.float().square() + 1e-6)
    if weight is None:
        return value.mean()
    return torch.sum(value * weight.float()) / torch.sum(weight.float()).clamp_min(1e-6)


def branch_supervision(
    model: torch.nn.Module,
    details: dict[str, torch.Tensor],
    batch: dict[str, torch.Tensor],
) -> tuple[torch.Tensor, dict[str, float]]:
    source = batch["source"].float()
    target = batch["target"].float()
    boundary = batch["boundary"].float().clamp(0.0, 1.0)
    material = 1.0 - boundary
    residual = target - source
    low_target = model.blur15(target) - model.blur15(source)
    high_target = residual - low_target
    low = charbonnier(details["low_delta"].float() - low_target)
    edge = charbonnier(details["edge_delta"].float() - high_target, boundary)
    predicted_detail = details["denoise_delta"].float() + details["texture_delta"].float()
    material_detail = charbonnier(predicted_detail - high_target, material)
    output = details["output"].float()
    output3, output7, output15 = model.blur3(output), model.blur7(output), model.blur15(output)
    target3, target7, target15 = model.blur3(target), model.blur7(target), model.blur15(target)
    output_bands = (output - output3, output3 - output7, output7 - output15)
    target_bands = (target - target3, target3 - target7, target7 - target15)
    highpass_output = sum(charbonnier(left - right, 0.35 + boundary) for left, right in zip(output_bands, target_bands)) / 3.0
    phase_terms, energy_terms = [], []
    for left, right in zip(output_bands, target_bands):
        left_flat, right_flat = left.flatten(1), right.flatten(1)
        similarity = torch.sum(left_flat * right_flat, dim=1) / torch.sqrt(
            torch.sum(left_flat.square(), dim=1) * torch.sum(right_flat.square(), dim=1) + 1e-8,
        )
        phase_terms.append(1.0 - similarity)
        left_rms = torch.sqrt(torch.mean(left_flat.square(), dim=1) + 1e-8)
        right_rms = torch.sqrt(torch.mean(right_flat.square(), dim=1) + 1e-8)
        energy_terms.append(torch.abs(torch.log(left_rms / right_rms)))
    highpass_phase = torch.stack(phase_terms).mean()
    highpass_energy = torch.stack(energy_terms).mean()
    identity_selected = batch["identity"] > 0
    clear_identity = charbonnier(output[identity_selected] - source[identity_selected]) if bool(identity_selected.any()) else output.new_tensor(0.0)
    innovation = details.get("innovation_delta", torch.zeros_like(output)).float()
    base_without_innovation = (output - innovation).detach()
    needed = target - base_without_innovation
    needed_highpass = needed - BASE.blur3(needed)
    innovation_residual = charbonnier(innovation - needed_highpass, 0.35 + boundary)
    parts = {
        "branch_low": float(low.detach()),
        "branch_edge": float(edge.detach()),
        "branch_material": float(material_detail.detach()),
        "branch_highpass": float(highpass_output.detach()),
        "branch_phase": float(highpass_phase.detach()),
        "branch_energy": float(highpass_energy.detach()),
        "branch_identity": float(clear_identity.detach()),
        "branch_innovation": float(innovation_residual.detach()),
    }
    return torch.stack([low, edge, material_detail, highpass_output, highpass_phase, highpass_energy, clear_identity, innovation_residual]), parts


def parameter_groups(model: torch.nn.Module, config: dict) -> list[dict]:
    base_lr = float(config["training"]["learning_rate"])
    multipliers = config["branch_learning_rate_multipliers"]
    buckets: dict[str, list[torch.nn.Parameter]] = {key: [] for key in multipliers}
    for name, parameter in model.named_parameters():
        group = "backbone"
        for candidate in ("radiometry_head", "denoise_head", "edge_head", "edge_mix_head", "band_gain_head", "innovation_head", "texture_head"):
            if name.startswith(candidate + "."):
                group = candidate
                break
        buckets[group].append(parameter)
    return [
        {"params": values, "lr": base_lr * float(multipliers[name]), "name": name, "multiplier": float(multipliers[name])}
        for name, values in buckets.items() if values
    ]


def gradient_norms(model: torch.nn.Module) -> dict[str, float]:
    totals: dict[str, float] = {}
    for name, parameter in model.named_parameters():
        if parameter.grad is None:
            continue
        group = "backbone"
        for candidate in ("radiometry_head", "denoise_head", "edge_head", "edge_mix_head", "band_gain_head", "innovation_head", "texture_head"):
            if name.startswith(candidate + "."):
                group = candidate
                break
        totals[group] = totals.get(group, 0.0) + float(parameter.grad.detach().float().square().sum().cpu())
    return {name: math.sqrt(value) for name, value in totals.items()}


def run_arm(arm: str, config: dict, arrays: dict[str, np.ndarray], schedule: np.ndarray, device: torch.device) -> dict:
    training = config["training"]
    seed = int(training["seed"])
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)
    model = MODELS.build_model(arm, base=int(training["model_width"])).to(device).to(memory_format=torch.channels_last)
    initial_hash = state_hash(model)
    common_initial_hash = state_hash(model, common_only=True)
    groups = parameter_groups(model, config)
    optimizer = torch.optim.AdamW(groups, weight_decay=float(training["weight_decay"]), fused=(device.type == "cuda"))
    weights = config["branch_supervision_weights"]
    steps = int(training["steps_per_arm"])
    checkpoints = set(map(int, training["checkpoint_steps"]))
    run_dir = ROOT / "runs" / f"repair_seed{seed}" / f"arm_{arm}"
    weight_dir = ROOT / "weights" / f"repair_arm_{arm}"
    preview_dir = ROOT / "results" / "repair_training_previews" / f"arm_{arm}"
    if (run_dir / "run_summary.json").is_file():
        raise RuntimeError(f"Completed arm {arm} already exists")
    run_dir.mkdir(parents=True, exist_ok=True)
    weight_dir.mkdir(parents=True, exist_ok=True)
    preview_dir.mkdir(parents=True, exist_ok=True)
    torch.save({"arm": arm, "step": 0, "model": model.state_dict(), "initial_hash": initial_hash, "common_initial_hash": common_initial_hash}, weight_dir / "step_000.pth.tar")
    BASE.save_preview(model, arrays, device, preview_dir / "step_000.png", 0)
    fields = ["step", "stream", "lr", "seconds", "total", "base_total", "branch_low", "branch_edge", "branch_material", "branch_highpass", "branch_phase", "branch_energy", "branch_identity", "branch_innovation", "grad_backbone", "grad_radiometry", "grad_edge", "grad_texture", "gpu_peak_gib", "gpu_free_gib"]
    log_path = run_dir / "training_log.csv"
    with log_path.open("w", newline="", encoding="utf-8") as handle:
        csv.DictWriter(handle, fieldnames=fields).writeheader()
    if device.type == "cuda":
        torch.cuda.reset_peak_memory_stats(device)
    started = time.perf_counter()
    model.train()
    for step in range(1, steps + 1):
        step_started = time.perf_counter()
        fraction = (step - 1) / max(steps - 1, 1)
        base_lr = float(training["minimum_learning_rate"]) + 0.5 * (float(training["learning_rate"]) - float(training["minimum_learning_rate"])) * (1.0 + math.cos(math.pi * fraction))
        for group in optimizer.param_groups:
            group["lr"] = base_lr * float(group["multiplier"])
        batch = BASE.tensor_batch(arrays, schedule[step - 1], device)
        stream = training["stream_cycle"][(step - 1) % len(training["stream_cycle"])]
        optimizer.zero_grad(set_to_none=True)
        with torch.autocast(device_type="cuda", dtype=torch.bfloat16, enabled=(device.type == "cuda")):
            details = model(batch["source"].contiguous(memory_format=torch.channels_last), return_details=True)
            base_total, _base_parts = BASE.loss_components(arm, details, batch, stream, 0.25)
            branch_values, branch_parts = branch_supervision(model, details, batch)
            branch_total = (
                float(weights["low"]) * branch_values[0]
                + float(weights["edge"]) * branch_values[1]
                + float(weights["material_detail"]) * branch_values[2]
                + float(weights["highpass_output"]) * branch_values[3]
                + float(weights["highpass_phase"]) * branch_values[4]
                + float(weights["highpass_energy"]) * branch_values[5]
                + float(weights["clear_identity"]) * branch_values[6]
                + float(weights["innovation_residual"]) * branch_values[7]
            )
            total = base_total.float() + branch_total
        if not bool(torch.isfinite(total)):
            raise FloatingPointError(f"Non-finite loss at {arm}:{step}")
        total.backward()
        norms = gradient_norms(model)
        total_norm = torch.nn.utils.clip_grad_norm_(model.parameters(), float(training["gradient_clip"]))
        if not bool(torch.isfinite(total_norm)):
            raise FloatingPointError(f"Non-finite gradient at {arm}:{step}")
        optimizer.step()
        if device.type == "cuda":
            torch.cuda.synchronize(device)
            peak = torch.cuda.max_memory_allocated(device) / 2**30
            free = torch.cuda.mem_get_info(device)[0] / 2**30
        else:
            peak = free = 0.0
        row = {
            "step": step, "stream": stream, "lr": base_lr, "seconds": time.perf_counter() - step_started,
            "total": float(total.detach()), "base_total": float(base_total.detach()), **branch_parts,
            "grad_backbone": norms.get("backbone", 0.0), "grad_radiometry": norms.get("radiometry_head", 0.0),
            "grad_edge": norms.get("innovation_head", norms.get("band_gain_head", norms.get("edge_mix_head", norms.get("edge_head", 0.0)))), "grad_texture": norms.get("texture_head", 0.0),
            "gpu_peak_gib": peak, "gpu_free_gib": free,
        }
        with log_path.open("a", newline="", encoding="utf-8") as handle:
            csv.DictWriter(handle, fieldnames=fields).writerow(row)
        if step in checkpoints:
            checkpoint = {"arm": arm, "step": step, "model": model.state_dict(), "optimizer": optimizer.state_dict(), "initial_hash": initial_hash, "common_initial_hash": common_initial_hash, "config": config}
            torch.save(checkpoint, weight_dir / f"step_{step:03d}.pth.tar")
            torch.save(checkpoint, weight_dir / "latest.pth.tar")
            BASE.save_preview(model, arrays, device, preview_dir / f"step_{step:03d}.png", step)
        if step % 25 == 0 or step == 1:
            progress = {"status": "active", "arm": arm, "step": step, "steps": steps, "loss": float(total.detach()), "gpu_peak_gib": peak, "gpu_free_gib": free, "updated_at": datetime.now().isoformat()}
            write_json(run_dir / "progress.json", progress)
            write_json(ROOT / "runs" / "repair_active_run.json", progress)
            print(json.dumps(progress), flush=True)
    summary = {"status": "complete", "arm": arm, "steps": steps, "elapsed_seconds": time.perf_counter() - started, "initial_hash": initial_hash, "common_initial_hash": common_initial_hash, "final_hash": state_hash(model), "gpu_peak_gib": peak, "checkpoint": str(weight_dir / "latest.pth.tar"), "finished_at": datetime.now().isoformat()}
    write_json(run_dir / "run_summary.json", summary)
    return summary


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--arms", nargs="+", choices=list("DEFG"), default=["D", "E"])
    args = parser.parse_args()
    config = json.loads((ROOT / "config" / "repair_ablation.json").read_text(encoding="utf-8"))
    with np.load(ROOT / "data" / "continuous_pairs.npz") as loaded:
        arrays = {name: loaded[name] for name in loaded.files}
    schedule = np.load(ROOT / "data" / "batch_schedule.npy")
    device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")
    if device.type == "cuda":
        torch.backends.cuda.matmul.allow_tf32 = True
        torch.backends.cudnn.allow_tf32 = True
    summaries = [run_arm(arm, config, arrays, schedule, device) for arm in args.arms]
    result = {"status": "training_complete", "summaries": summaries, "finished_at": datetime.now().isoformat()}
    write_json(ROOT / "runs" / "repair_training_summary.json", result)
    write_json(ROOT / "runs" / "repair_active_run.json", result)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

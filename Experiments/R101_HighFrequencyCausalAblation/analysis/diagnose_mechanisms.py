"""Measure whether each R101 prototype can usefully move source toward target."""
from __future__ import annotations

import importlib.util
import json
import math
import sys
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


MODELS = load_module("r101_diag_models", ROOT / "model" / "prototype_models.py")
TRAINING = load_module("r101_diag_training", ROOT / "training" / "run_short_ablation.py")


def cosine(a: torch.Tensor, b: torch.Tensor, weight: torch.Tensor | None = None) -> float:
    if weight is not None:
        a, b = a * weight, b * weight
    numerator = torch.sum(a * b)
    denominator = torch.sqrt(torch.sum(a.square()) * torch.sum(b.square()) + 1e-12)
    return float((numerator / denominator).detach().cpu())


def mean_abs_gray(x: torch.Tensor, weight: torch.Tensor | None = None) -> float:
    if weight is None:
        return float(x.abs().mean().detach().cpu() * 255.0)
    return float((torch.sum(x.abs() * weight) / torch.sum(weight).clamp_min(1e-6)).detach().cpu() * 255.0)


def rms(x: torch.Tensor) -> float:
    return float(torch.sqrt(torch.mean(x.square()) + 1e-12).detach().cpu())


def group_name(name: str) -> str:
    for prefix in ("radiometry_head", "denoise_head", "edge_head", "texture_head", "renderer_head"):
        if name.startswith(prefix):
            return prefix
    return "backbone"


def gradient_groups(model: torch.nn.Module, loss: torch.Tensor) -> dict[str, float]:
    model.zero_grad(set_to_none=True)
    loss.backward()
    squared: dict[str, float] = {}
    for name, parameter in model.named_parameters():
        if parameter.grad is None:
            continue
        group = group_name(name)
        squared[group] = squared.get(group, 0.0) + float(torch.sum(parameter.grad.detach().float().square()).cpu())
    return {key: math.sqrt(value) for key, value in squared.items()}


@torch.inference_mode()
def checkpoint_stats(model: torch.nn.Module, source: torch.Tensor, target: torch.Tensor, boundary: torch.Tensor) -> dict[str, float]:
    details = model(source, return_details=True)
    output = details["output"].float()
    source = source.float()
    target = target.float()
    residual = target - source
    correction = output - source
    material = 1.0 - boundary
    source_error = torch.mean(residual.square())
    output_error = torch.mean((target - output).square())
    hp_source = source - TRAINING.blur3(source)
    hp_target = target - TRAINING.blur3(target)
    hp_output = output - TRAINING.blur3(output)
    stats = {
        "source_target_gap_gray": mean_abs_gray(residual),
        "output_target_mae_gray": mean_abs_gray(target - output),
        "applied_correction_gray": mean_abs_gray(correction),
        "residual_removed_fraction": float((1.0 - output_error / source_error.clamp_min(1e-12)).cpu()),
        "correction_residual_cosine": cosine(correction, residual),
        "boundary_correction_residual_cosine": cosine(correction, residual, boundary),
        "material_correction_residual_cosine": cosine(correction, residual, material),
        "hp_source_rms": rms(hp_source),
        "hp_target_rms": rms(hp_target),
        "hp_output_rms": rms(hp_output),
        "edge_support_boundary_mean": float((torch.sum(details["edge_support"].float() * boundary) / torch.sum(boundary)).cpu()),
        "edge_support_material_mean": float((torch.sum(details["edge_support"].float() * material) / torch.sum(material)).cpu()),
    }
    for name in ("low_delta", "denoise_delta", "edge_delta", "texture_delta", "renderer_delta"):
        stats[f"{name}_abs_gray"] = mean_abs_gray(details[name].float())
    for name in ("edge_strength", "denoise_strength", "width_strength", "render_blend", "normal_offset_px"):
        stats[f"{name}_mean"] = float(details[name].float().mean().cpu())

    # Reachability check for the fixed zero-phase edge direction used by A/B.
    denoised = torch.clamp(source + details["low_delta"].float() + details["denoise_delta"].float(), 0.0, 1.0)
    fixed_edge_candidate = denoised - model.blur7(denoised)
    stats["fixed_edge_candidate_residual_cosine_boundary"] = cosine(fixed_edge_candidate, residual, boundary)
    return stats


def main() -> int:
    config = json.loads((ROOT / "config" / "experiment.json").read_text(encoding="utf-8"))
    with np.load(ROOT / "data" / "continuous_pairs.npz") as loaded:
        arrays = {name: loaded[name] for name in loaded.files}
    schedule = np.load(ROOT / "data" / "batch_schedule.npy")
    device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")
    selected = np.flatnonzero(arrays["split"] == 1)
    source = torch.from_numpy(np.asarray(arrays["source"][selected], dtype=np.float32))[:, None].to(device)
    target = torch.from_numpy(np.asarray(arrays["target"][selected], dtype=np.float32))[:, None].to(device)
    boundary = torch.from_numpy(np.asarray(arrays["boundary"][selected], dtype=np.float32))[:, None].to(device)
    report: dict[str, object] = {"validation_samples": int(len(selected)), "arms": {}}
    for arm in ("A", "B", "C"):
        arm_report: dict[str, object] = {"checkpoints": {}}
        for step in (0, 100, 200, 300, 400):
            checkpoint = torch.load(ROOT / "weights" / f"arm_{arm}" / f"step_{step:03d}.pth.tar", map_location="cpu")
            model = MODELS.build_model(arm, base=int(config["training"]["model_width"])).to(device)
            model.load_state_dict(checkpoint["model"], strict=True)
            model.eval()
            arm_report["checkpoints"][str(step)] = checkpoint_stats(model, source, target, boundary)

        checkpoint = torch.load(ROOT / "weights" / f"arm_{arm}" / "step_400.pth.tar", map_location="cpu")
        model = MODELS.build_model(arm, base=int(config["training"]["model_width"])).to(device)
        model.load_state_dict(checkpoint["model"], strict=True)
        model.train()
        gradients: dict[str, object] = {}
        for stream_index, stream in enumerate(config["training"]["stream_cycle"]):
            batch = TRAINING.tensor_batch(arrays, schedule[397 + stream_index], device)
            details = model(batch["source"], return_details=True)
            loss, parts = TRAINING.loss_components(arm, details, batch, stream, float(config["data"]["reference_psf_sigma_px"]))
            gradients[stream] = {"loss": float(loss.detach().cpu()), "groups": gradient_groups(model, loss), "parts": parts}
        arm_report["final_gradient_groups"] = gradients
        report["arms"][arm] = arm_report
        if device.type == "cuda":
            torch.cuda.empty_cache()

    output = ROOT / "results" / "mechanism_diagnostics.json"
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

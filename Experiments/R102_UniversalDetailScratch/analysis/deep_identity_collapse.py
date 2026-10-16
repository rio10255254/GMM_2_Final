"""Reproducible causal audit of the stopped R102 identity-collapse run."""
from __future__ import annotations

import json
import math
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np
import torch
from torch.utils.data._utils.collate import default_collate


ROOT = Path(__file__).resolve().parents[1]
for folder in (ROOT / "model", ROOT / "training"):
    sys.path.insert(0, str(folder))

from r102_model import build_model  # noqa: E402
from r102_dataset import R102Dataset  # noqa: E402
from losses import highpass, loss_components  # noqa: E402


CONFIG = json.loads((ROOT / "config" / "experiment.json").read_text(encoding="utf-8"))
ACTIVE = json.loads((ROOT / "runs" / "active_run.json").read_text(encoding="utf-8"))
RUN_DIR = ROOT / "runs" / ACTIVE["run_id"]
PROGRESS = json.loads((RUN_DIR / "run_progress.json").read_text(encoding="utf-8"))
WEIGHT_DIR = ROOT / "weights" / "formal" / f"seed_{ACTIVE['seed']}" / ACTIVE["run_id"]
DEVICE = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")


def model_instance() -> torch.nn.Module:
    bounds = CONFIG["model"]["branch_bounds"]
    return build_model(
        base=int(CONFIG["model"]["base_channels"]),
        low_bound=float(bounds["radiometry"]),
        contour_bound=float(bounds["contour"]),
        texture_bound=float(bounds["texture"]),
        combined_bound=float(bounds["combined"]),
    )


def prepare_batch(indices: list[int], patch: int = 192) -> dict[str, object]:
    dataset = R102Dataset("validation", patch, 0, validation_limit=max(indices) + 1)
    batch = default_collate([dataset[index] for index in indices])
    for key in ("source", "target", "mask", "motion", "identity", "mode", "midpoint", "polarity"):
        batch[key] = batch[key].to(DEVICE)
    source = batch["source"]
    b, v, c, h, w = source.shape
    batch["flat_source"] = source.reshape(b * v, c, h, w).contiguous(memory_format=torch.channels_last)
    batch["flat_target"] = batch["target"].reshape(b * v, c, h, w)
    batch["flat_mask"] = batch["mask"].reshape(b * v, c, h, w)
    batch["flat_motion"] = batch["motion"].reshape(-1, 2)
    batch["flat_identity"] = batch["identity"].reshape(-1)
    batch["flat_mode"] = batch["mode"].repeat_interleave(v)
    batch["flat_midpoint"] = batch["midpoint"].repeat_interleave(v)
    batch["flat_polarity"] = batch["polarity"].repeat_interleave(v)
    return batch


def scalar_metrics(model: torch.nn.Module, batch: dict[str, object]) -> dict[str, object]:
    model.eval()
    source = batch["flat_source"]
    target = batch["flat_target"]
    mode = batch["flat_mode"]
    with torch.inference_mode(), torch.autocast(device_type="cuda", dtype=torch.bfloat16, enabled=DEVICE.type == "cuda"):
        details = model.forward_details(source)
    prediction = details.output.float()
    source = source.float()
    target = target.float()
    source_error = (source - target).abs().flatten(1).mean(1)
    prediction_error = (prediction - target).abs().flatten(1).mean(1)
    source_hf_error = (highpass(source, 3) - highpass(target, 3)).abs().flatten(1).mean(1)
    prediction_hf_error = (highpass(prediction, 3) - highpass(target, 3)).abs().flatten(1).mean(1)
    result: dict[str, object] = {
        "change_gray_mean": float((prediction - source).abs().mean() * 255.0),
        "change_gray_p99": float(torch.quantile((prediction - source).abs().flatten(), 0.99) * 255.0),
        "low_gray_mean": float(details.low_delta.float().abs().mean() * 255.0),
        "contour_gray_mean": float(details.contour_delta.float().abs().mean() * 255.0),
        "texture_gray_mean": float(details.texture_delta.float().abs().mean() * 255.0),
        "mae_improvement": float((1.0 - prediction_error.mean() / source_error.mean().clamp_min(1e-8))),
        "hf_improvement": float((1.0 - prediction_hf_error.mean() / source_hf_error.mean().clamp_min(1e-8))),
    }
    for mode_id, name in R102Dataset.mode_names.items():
        rows = mode == mode_id
        if bool(rows.any()):
            result[f"{name}_count"] = int(rows.sum())
            result[f"{name}_change_gray"] = float((prediction[rows] - source[rows]).abs().mean() * 255.0)
            denominator = source_error[rows].mean().clamp_min(1e-8)
            result[f"{name}_mae_improvement"] = float(1.0 - prediction_error[rows].mean() / denominator)
            hf_denominator = source_hf_error[rows].mean().clamp_min(1e-8)
            result[f"{name}_hf_improvement"] = float(1.0 - prediction_hf_error[rows].mean() / hf_denominator)
    return result


def data_contract(batch: dict[str, object]) -> dict[str, object]:
    source = batch["flat_source"].float()
    target = batch["flat_target"].float()
    mode = batch["flat_mode"]
    result: dict[str, object] = {}
    for mode_id, name in R102Dataset.mode_names.items():
        rows = mode == mode_id
        if not bool(rows.any()):
            continue
        source_gap = (source[rows] - target[rows]).abs().flatten(1).mean(1)
        hf_source = highpass(source[rows], 3).flatten(1)
        hf_target = highpass(target[rows], 3).flatten(1)
        a = hf_source - hf_source.mean(1, keepdim=True)
        b = hf_target - hf_target.mean(1, keepdim=True)
        correlation = (a * b).sum(1) / torch.sqrt(a.square().sum(1) * b.square().sum(1) + 1e-8)
        result[name] = {
            "views": int(rows.sum()),
            "source_target_mae_gray": float(source_gap.mean() * 255.0),
            "source_hf_abs_gray": float(hf_source.abs().mean() * 255.0),
            "target_hf_abs_gray": float(hf_target.abs().mean() * 255.0),
            "source_target_hf_correlation": float(correlation.mean()),
        }
    return result


def parameter_group(name: str) -> str:
    if name.startswith("low_"):
        return "low"
    if name.startswith("contour_"):
        return "contour"
    if name.startswith("texture_"):
        return "texture"
    return "shared"


def gradient_audit(model: torch.nn.Module, batch: dict[str, object]) -> dict[str, object]:
    model.train()
    names = [
        "reconstruction", "low_frequency", "gradient", "high_frequency", "high_frequency_correlation",
        "contour", "branch_targets", "paired_observation", "identity", "flat_negative",
    ]
    weights = CONFIG["training"]["loss_weights"]
    factors = PROGRESS["objective_balance_factors"]
    head_parameters = [
        (name, parameter) for name, parameter in model.named_parameters()
        if name.startswith(("low_head", "contour_head", "texture_head"))
    ]
    group_norms: dict[str, dict[str, float]] = {}
    vectors: dict[str, torch.Tensor] = {}
    for objective in names:
        model.zero_grad(set_to_none=True)
        with torch.autocast(device_type="cuda", dtype=torch.bfloat16, enabled=DEVICE.type == "cuda"):
            details = model.forward_details(batch["flat_source"])
            components = loss_components(
                details, batch["flat_source"], batch["flat_target"], batch["flat_mask"],
                batch["flat_midpoint"], batch["flat_polarity"], batch["flat_mode"],
                batch["flat_identity"], batch["flat_motion"], 128,
            )
            value = components[objective]
        value.backward()
        norms: defaultdict[str, float] = defaultdict(float)
        for name, parameter in model.named_parameters():
            if parameter.grad is not None:
                norms[parameter_group(name)] += float(parameter.grad.detach().float().square().sum())
        group_norms[objective] = {key: math.sqrt(value) for key, value in norms.items()}
        flat = []
        for _name, parameter in head_parameters:
            grad = parameter.grad
            flat.append(torch.zeros_like(parameter).flatten() if grad is None else grad.detach().float().flatten())
        vectors[objective] = torch.cat(flat).cpu()

    weighted = {
        name: vectors[name] * float(weights.get(name, 0.0)) * float(factors.get(name, 1.0))
        for name in names
    }
    vector_sum = torch.stack(list(weighted.values())).sum(0)
    norm_sum = sum(float(vector.norm()) for vector in weighted.values())
    cancellation_ratio = float(vector_sum.norm()) / max(norm_sum, 1e-12)
    strongest_conflicts = []
    for i, left in enumerate(names):
        for right in names[i + 1:]:
            a, b = weighted[left], weighted[right]
            denominator = float(a.norm() * b.norm())
            if denominator > 1e-12:
                cosine = float(torch.dot(a, b)) / denominator
                strongest_conflicts.append({"left": left, "right": right, "cosine": cosine})
    strongest_conflicts.sort(key=lambda row: row["cosine"])
    return {
        "component_group_gradient_norms": group_norms,
        "weighted_head_gradient_cancellation_ratio": cancellation_ratio,
        "strongest_weighted_head_conflicts": strongest_conflicts[:12],
    }


def main() -> int:
    torch.set_num_threads(8)
    batch = prepare_batch(list(range(12)))
    report: dict[str, object] = {
        "experiment_id": CONFIG["experiment_id"],
        "run_id": ACTIVE["run_id"],
        "device": str(DEVICE),
        "data_contract": data_contract(batch),
        "checkpoint_trajectory": [],
    }
    checkpoints = [1, 8, 16, 24, 32, 40]
    for epoch in checkpoints:
        path = WEIGHT_DIR / f"epoch_{epoch:03d}.pth.tar"
        if not path.is_file():
            continue
        payload = torch.load(path, map_location="cpu", weights_only=False)
        for state_name in ("model_state_dict", "ema_state_dict"):
            model = model_instance().to(DEVICE).to(memory_format=torch.channels_last)
            model.load_state_dict(payload[state_name], strict=True)
            row = {"epoch": epoch, "state": "raw" if state_name == "model_state_dict" else "ema"}
            row.update(scalar_metrics(model, batch))
            report["checkpoint_trajectory"].append(row)
            del model
    fresh = model_instance().to(DEVICE).to(memory_format=torch.channels_last)
    final_payload = torch.load(WEIGHT_DIR / "epoch_040.pth.tar", map_location="cpu", weights_only=False)
    final = model_instance().to(DEVICE).to(memory_format=torch.channels_last)
    final.load_state_dict(final_payload["model_state_dict"], strict=True)
    report["fresh_gradient_audit"] = gradient_audit(fresh, batch)
    report["epoch40_raw_gradient_audit"] = gradient_audit(final, batch)
    report_path = ROOT / "reports" / "deep_identity_collapse.json"
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({
        "report": str(report_path),
        "data_contract": report["data_contract"],
        "checkpoint_trajectory": report["checkpoint_trajectory"],
        "fresh_cancellation": report["fresh_gradient_audit"]["weighted_head_gradient_cancellation_ratio"],
        "epoch40_cancellation": report["epoch40_raw_gradient_audit"]["weighted_head_gradient_cancellation_ratio"],
        "epoch40_conflicts": report["epoch40_raw_gradient_audit"]["strongest_weighted_head_conflicts"][:6],
    }, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

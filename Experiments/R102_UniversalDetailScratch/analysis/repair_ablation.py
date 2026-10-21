"""Small held-out ablation to falsify proposed R102 identity-collapse repairs."""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

import numpy as np
import torch
from torch.utils.data import DataLoader, Subset


ROOT = Path(__file__).resolve().parents[1]
for folder in (ROOT / "model", ROOT / "training"):
    sys.path.insert(0, str(folder))

from r102_model import build_model  # noqa: E402
from r102_dataset import R102Dataset  # noqa: E402
from losses import gaussian_blur, highpass, loss_components  # noqa: E402
from train_r102 import ObjectiveBalancer  # noqa: E402


DEVICE = torch.device("cuda:0")
torch.backends.cudnn.benchmark = True
torch.backends.cuda.matmul.allow_tf32 = True
torch.backends.cudnn.allow_tf32 = True


def flatten(batch: dict[str, object]) -> dict[str, torch.Tensor]:
    source = batch["source"].to(DEVICE)
    target = batch["target"].to(DEVICE)
    mask = batch["mask"].to(DEVICE)
    b, v, c, h, w = source.shape
    return {
        "source": source.reshape(b * v, c, h, w).contiguous(memory_format=torch.channels_last),
        "target": target.reshape(b * v, c, h, w),
        "mask": mask.reshape(b * v, c, h, w),
        "motion": batch["motion"].to(DEVICE).reshape(-1, 2),
        "identity": batch["identity"].to(DEVICE).reshape(-1),
        "mode": batch["mode"].to(DEVICE).repeat_interleave(v),
        "midpoint": batch["midpoint"].to(DEVICE).repeat_interleave(v),
        "polarity": batch["polarity"].to(DEVICE).repeat_interleave(v),
    }


def make_recoverable(flat: dict[str, torch.Tensor], *, training: bool) -> dict[str, torch.Tensor]:
    result = dict(flat)
    source, target, mode = flat["source"], flat["target"], flat["mode"]
    rows = (mode == 0) | (mode == 1)
    target_low = gaussian_blur(target, 9)
    target_detail = target - target_low
    source_low = gaussian_blur(source, 9)
    controlled = target_low + 0.28 * (source_low - target_low) + 0.58 * gaussian_blur(target_detail, 3)
    if training:
        controlled = controlled + 0.004 * torch.randn_like(controlled)
    result["source"] = torch.where(rows.view(-1, 1, 1, 1), controlled.clamp(0.0, 1.0), source)
    return result


def initialize_active_heads(model: torch.nn.Module) -> None:
    for head_name in ("low_head", "contour_head", "texture_head"):
        head = getattr(model, head_name)
        torch.nn.init.normal_(head.weight, mean=0.0, std=0.0015)
        torch.nn.init.zeros_(head.bias)


def parameter_groups(model: torch.nn.Module, base_lr: float) -> list[dict[str, object]]:
    groups: dict[str, list[torch.nn.Parameter]] = {"shared": [], "low": [], "contour": [], "texture": []}
    for name, parameter in model.named_parameters():
        if name.startswith("low_"):
            groups["low"].append(parameter)
        elif name.startswith("contour_"):
            groups["contour"].append(parameter)
        elif name.startswith("texture_"):
            groups["texture"].append(parameter)
        else:
            groups["shared"].append(parameter)
    return [
        {"params": groups["shared"], "lr": base_lr},
        {"params": groups["low"], "lr": base_lr * 0.25},
        {"params": groups["contour"], "lr": base_lr * 5.0},
        {"params": groups["texture"], "lr": base_lr * 7.0},
    ]


def fixed_total(components: dict[str, torch.Tensor], details, flat: dict[str, torch.Tensor]) -> torch.Tensor:
    identity_rows = flat["identity"] | (flat["mode"] == 2)
    flat_rows = flat["mode"] == 3
    smooth_identity = details.output.new_zeros(())
    smooth_flat = details.output.new_zeros(())
    if bool(identity_rows.any()):
        residual = details.output.float()[identity_rows] - flat["source"].float()[identity_rows]
        smooth_identity = torch.sqrt(residual.square() + 0.002**2).mean() - 0.002
    if bool(flat_rows.any()):
        residual = details.output.float()[flat_rows] - flat["target"].float()[flat_rows]
        smooth_flat = torch.sqrt(residual.square() + 0.003**2).mean() - 0.003
    return (
        0.65 * components["reconstruction"]
        + 0.08 * components["low_frequency"]
        + 0.55 * components["gradient"]
        + 1.30 * components["high_frequency"]
        + 0.18 * components["high_frequency_correlation"]
        + 0.55 * components["contour"]
        + 1.20 * components["branch_targets"]
        + 0.035 * smooth_identity
        + 0.035 * smooth_flat
    )


@torch.inference_mode()
def evaluate(model: torch.nn.Module, loader: DataLoader, recoverable: bool) -> dict[str, float]:
    model.eval()
    values: dict[str, list[float]] = {key: [] for key in (
        "change_gray", "mae_improvement", "hf_improvement", "identity_change_gray",
        "innovation_improvement", "innovation_hf_improvement", "low_gray", "contour_gray", "texture_gray",
    )}
    correlations = []
    for batch in loader:
        flat = flatten(batch)
        if recoverable:
            flat = make_recoverable(flat, training=False)
        with torch.autocast(device_type="cuda", dtype=torch.bfloat16):
            details = model.forward_details(flat["source"])
        source, target, prediction = flat["source"].float(), flat["target"].float(), details.output.float()
        raw_error = (source - target).abs().flatten(1).mean(1)
        pred_error = (prediction - target).abs().flatten(1).mean(1)
        raw_hf = (highpass(source, 3) - highpass(target, 3)).abs().flatten(1).mean(1)
        pred_hf = (highpass(prediction, 3) - highpass(target, 3)).abs().flatten(1).mean(1)
        values["change_gray"].extend(((prediction - source).abs().flatten(1).mean(1) * 255).cpu().tolist())
        values["mae_improvement"].extend((1.0 - pred_error / raw_error.clamp_min(1e-6)).cpu().tolist())
        values["hf_improvement"].extend((1.0 - pred_hf / raw_hf.clamp_min(1e-6)).cpu().tolist())
        values["low_gray"].append(float(details.low_delta.float().abs().mean() * 255))
        values["contour_gray"].append(float(details.contour_delta.float().abs().mean() * 255))
        values["texture_gray"].append(float(details.texture_delta.float().abs().mean() * 255))
        identity = flat["identity"] | (flat["mode"] == 2)
        if bool(identity.any()):
            values["identity_change_gray"].extend(((prediction[identity] - source[identity]).abs().flatten(1).mean(1) * 255).cpu().tolist())
        innovation = flat["mode"] == 1
        if bool(innovation.any()):
            values["innovation_improvement"].extend((1.0 - pred_error[innovation] / raw_error[innovation].clamp_min(1e-6)).cpu().tolist())
            values["innovation_hf_improvement"].extend((1.0 - pred_hf[innovation] / raw_hf[innovation].clamp_min(1e-6)).cpu().tolist())
        a, b = highpass(source, 3).flatten(1), highpass(target, 3).flatten(1)
        a, b = a - a.mean(1, keepdim=True), b - b.mean(1, keepdim=True)
        correlations.extend(((a * b).sum(1) / torch.sqrt(a.square().sum(1) * b.square().sum(1) + 1e-8)).cpu().tolist())
    result = {key: float(np.mean(rows)) if rows else float("nan") for key, rows in values.items()}
    result["source_target_hf_correlation"] = float(np.mean(correlations))
    return result


def run_arm(name: str, recoverable: bool, repaired_training: bool, seed: int) -> dict[str, object]:
    torch.manual_seed(seed)
    np.random.seed(seed)
    train_dataset = R102Dataset("train", 128, 5)
    validation_dataset = R102Dataset("validation", 128, 0, validation_limit=32)
    train_loader = DataLoader(Subset(train_dataset, list(range(128))), batch_size=8, shuffle=True, num_workers=0, drop_last=True)
    val_loader = DataLoader(validation_dataset, batch_size=8, shuffle=False, num_workers=0)
    model = build_model(base=16).to(DEVICE).to(memory_format=torch.channels_last)
    if repaired_training:
        initialize_active_heads(model)
        optimizer = torch.optim.AdamW(parameter_groups(model, 1.5e-4), weight_decay=5e-5)
        balancer = None
    else:
        optimizer = torch.optim.AdamW(model.parameters(), lr=1.5e-4, weight_decay=8e-5)
        balancer = ObjectiveBalancer({
            "reconstruction": 1.0, "low_frequency": 0.22, "gradient": 0.32, "high_frequency": 0.52,
            "high_frequency_correlation": 0.20, "contour": 0.34, "branch_targets": 0.34,
            "paired_observation": 0.10, "identity": 0.22, "flat_negative": 0.18,
        })
    before = evaluate(model, val_loader, recoverable)
    iterator = iter(train_loader)
    losses = []
    for step in range(160):
        try:
            batch = next(iterator)
        except StopIteration:
            iterator = iter(train_loader)
            batch = next(iterator)
        flat = flatten(batch)
        if recoverable:
            flat = make_recoverable(flat, training=True)
        optimizer.zero_grad(set_to_none=True)
        with torch.autocast(device_type="cuda", dtype=torch.bfloat16):
            details = model.forward_details(flat["source"])
            components = loss_components(
                details, flat["source"], flat["target"], flat["mask"], flat["midpoint"],
                flat["polarity"], flat["mode"], flat["identity"], flat["motion"], 96,
            )
            total = fixed_total(components, details, flat) if repaired_training else balancer.combine(components)
        total.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), 3.0)
        optimizer.step()
        losses.append(float(total.detach()))
    after = evaluate(model, val_loader, recoverable)
    return {
        "name": name,
        "recoverable_data": recoverable,
        "repaired_training": repaired_training,
        "steps": 160,
        "loss_first_20": float(np.mean(losses[:20])),
        "loss_last_20": float(np.mean(losses[-20:])),
        "before": before,
        "after": after,
    }


def main() -> int:
    arms = [
        run_arm("A_current", False, False, 10301),
        run_arm("B_data_only", True, False, 10302),
        run_arm("C_training_only", False, True, 10303),
        run_arm("D_joint_repair", True, True, 10304),
    ]
    output = ROOT / "reports" / "repair_ablation.json"
    output.write_text(json.dumps({"arms": arms}, indent=2), encoding="utf-8")
    print(json.dumps({"report": str(output), "arms": arms}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

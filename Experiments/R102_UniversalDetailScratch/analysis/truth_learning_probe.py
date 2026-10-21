"""Probe whether R102 can learn a recoverable forward model with a non-conflicting loss.

This is intentionally a disposable, held-out diagnostic.  It does not write a
checkpoint and cannot launch formal training.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import torch
import torch.nn.functional as F
from torch.utils.data import DataLoader, Subset


ROOT = Path(__file__).resolve().parents[1]
for folder in (ROOT / "model", ROOT / "training"):
    sys.path.insert(0, str(folder))

from r102_model import build_model  # noqa: E402
from r102_dataset import R102Dataset  # noqa: E402
from losses import boundary_support, gaussian_blur, highpass  # noqa: E402
from candidate_r103_model import build_candidate  # noqa: E402


DEVICE = torch.device("cuda:0")
torch.backends.cudnn.benchmark = True
torch.backends.cuda.matmul.allow_tf32 = True
torch.backends.cudnn.allow_tf32 = True


def flatten(batch: dict[str, object]) -> dict[str, torch.Tensor]:
    source = batch["source"].to(DEVICE)
    target = batch["target"].to(DEVICE)
    b, v, c, h, w = source.shape
    return {
        "source": source.reshape(b * v, c, h, w).contiguous(memory_format=torch.channels_last),
        "target": target.reshape(b * v, c, h, w),
        "mode": batch["mode"].to(DEVICE).repeat_interleave(v),
        "identity": batch["identity"].to(DEVICE).reshape(-1),
        "mask": batch["mask"].to(DEVICE).reshape(b * v, c, h, w),
    }


def recoverable_source(flat: dict[str, torch.Tensor], *, noisy: bool) -> dict[str, torch.Tensor]:
    """Create a proper forward observation from the procedural target.

    The target is blurred and photometrically perturbed; it is never blended
    back into an unrelated stored observation.  This preserves the target
    phase while leaving a real inverse problem for the network.
    """
    result = dict(flat)
    source, target, mode = flat["source"], flat["target"], flat["mode"]
    degraded_rows = (mode == 0) | (mode == 1)
    blur3 = gaussian_blur(target, 3)
    blur5 = gaussian_blur(target, 5)
    # Deterministic mixture of two local PSFs.  Photometry is shared by source
    # and target: a one-frame model must not be asked to guess an unobservable
    # source-only exposure correction.
    target_observation = 0.35 * blur3 + 0.65 * blur5
    if noisy:
        target_observation = target_observation + 0.003 * torch.randn_like(target_observation)
    target_observation = target_observation.clamp(0.0, 1.0)
    result["source"] = torch.where(
        degraded_rows.view(-1, 1, 1, 1), target_observation, source
    ).contiguous(memory_format=torch.channels_last)
    return result


def counterfactual_bundle(flat: dict[str, torch.Tensor]) -> dict[str, object]:
    """Pair every degraded observation with the exact same content kept clear."""
    selector = flat["mode"] != 2
    selected = {key: value[selector] for key, value in flat.items() if torch.is_tensor(value)}
    count = int(selected["source"].shape[0])
    result: dict[str, object] = {}
    for key, value in selected.items():
        if key == "source":
            result[key] = torch.cat([value, selected["target"]], dim=0).contiguous(memory_format=torch.channels_last)
        elif key == "mode":
            result[key] = torch.cat([value, torch.full_like(value, 2)], dim=0)
        elif key == "identity":
            result[key] = torch.cat([torch.zeros_like(value), torch.ones_like(value)], dim=0)
        else:
            result[key] = torch.cat([value, value], dim=0)
    result["counterfactual_count"] = count
    return result


def active_initialize(model: torch.nn.Module) -> None:
    for head_name in ("low_head", "contour_head", "texture_head"):
        head = getattr(model, head_name)
        torch.nn.init.normal_(head.weight, mean=0.0, std=0.00035)
        torch.nn.init.zeros_(head.bias)


def objective(details, flat: dict[str, torch.Tensor]) -> torch.Tensor:
    prediction = details.output.float()
    target = flat["target"].float()
    source = flat["source"].float()
    mode = flat["mode"]
    degraded = mode != 2

    # Only degraded rows teach the inverse.  Exact identity and flat rows are
    # a smooth, vanishing-gradient preservation term rather than an L1 clamp.
    pred = prediction[degraded]
    truth = target[degraded]
    pixel = F.smooth_l1_loss(pred, truth, beta=2.0 / 255.0)
    pgx = pred[..., 1:] - pred[..., :-1]
    pgy = pred[..., 1:, :] - pred[..., :-1, :]
    tgx = truth[..., 1:] - truth[..., :-1]
    tgy = truth[..., 1:, :] - truth[..., :-1, :]
    gradient = F.smooth_l1_loss(pgx, tgx, beta=1.0 / 255.0)
    gradient = gradient + F.smooth_l1_loss(pgy, tgy, beta=1.0 / 255.0)
    detail = F.smooth_l1_loss(highpass(pred, 3), highpass(truth, 3), beta=0.5 / 255.0)
    detail = detail + 0.65 * F.smooth_l1_loss(highpass(pred, 5), highpass(truth, 5), beta=0.75 / 255.0)

    preserve = mode == 2
    guard = prediction.new_zeros(())
    if bool(preserve.any()):
        residual = prediction[preserve] - source[preserve]
        guard = (torch.sqrt(residual.square() + (1.5 / 255.0) ** 2) - 1.5 / 255.0).mean()
    return pixel + 0.75 * gradient + 1.15 * detail + 3.00 * guard


def candidate_objective(details, flat: dict[str, torch.Tensor]) -> torch.Tensor:
    """Non-overlapping responsibility targets plus an end-to-end image loss."""
    base = objective(details, flat)
    source, target, mode = flat["source"].float(), flat["target"].float(), flat["mode"]
    supervised = mode != 2
    residual = target - source
    low_target = gaussian_blur(residual, 9)
    detail_target = residual - low_target
    support = boundary_support(flat["mask"].float())
    contour_target = support * detail_target
    texture_target = detail_target - contour_target
    branches = F.smooth_l1_loss(details.low_delta.float()[supervised], low_target[supervised], beta=1.0 / 255.0)
    branches = branches + 1.5 * F.smooth_l1_loss(
        details.contour_delta.float()[supervised], contour_target[supervised], beta=0.5 / 255.0
    )
    branches = branches + 1.5 * F.smooth_l1_loss(
        details.texture_delta.float()[supervised], texture_target[supervised], beta=0.5 / 255.0
    )
    gate_loss = details.output.new_zeros(())
    if hasattr(details, "need_confidence") and not bool(flat.get("disable_gate_loss", False)):
        need_target = F.avg_pool2d(residual.abs(), 9, stride=1, padding=4)
        need_target = (need_target / (4.0 / 255.0)).clamp(0.0, 1.0)
        need_target = torch.where((mode == 2).view(-1, 1, 1, 1), torch.zeros_like(need_target), need_target)
        gate_loss = F.mse_loss(details.need_confidence.float(), need_target.float())
        pair_count = int(flat.get("counterfactual_count", 0))
        if pair_count:
            gate_mean = details.need_confidence.float().flatten(1).mean(1)
            degraded_gate = gate_mean[:pair_count]
            clear_gate = gate_mean[pair_count:pair_count * 2]
            gate_loss = gate_loss + 0.50 * F.relu(0.30 - (degraded_gate - clear_gate)).mean()
    counterfactual_loss = details.output.new_zeros(())
    pair_count = int(flat.get("counterfactual_count", 0))
    if pair_count:
        degraded_delta = details.total_delta.float()[:pair_count]
        clear_delta = details.total_delta.float()[pair_count:pair_count * 2]
        counterfactual_loss = F.smooth_l1_loss(
            degraded_delta - clear_delta, residual[:pair_count], beta=1.0 / 255.0
        )
        counterfactual_loss = counterfactual_loss + 0.50 * (
            torch.sqrt(clear_delta.square() + (1.0 / 255.0) ** 2) - 1.0 / 255.0
        ).mean()
    return base + 0.65 * branches + 0.30 * gate_loss + 0.50 * counterfactual_loss


def remove_pixel_normalization(model: torch.nn.Module) -> None:
    """Restoration features must retain local amplitude and absolute level."""
    for module in model.modules():
        if hasattr(module, "norm") and module.norm.__class__.__name__ == "PixelGroupNorm":
            module.norm = torch.nn.Identity()


@torch.inference_mode()
def evaluate(model: torch.nn.Module, loader: DataLoader) -> dict[str, float]:
    model.eval()
    rows: dict[str, list[float]] = {
        "raw_mae_gray": [], "prediction_mae_gray": [], "raw_hf_gray": [],
        "prediction_hf_gray": [], "change_gray": [], "identity_change_gray": [],
        "flat_raw_mae_gray": [], "flat_prediction_mae_gray": [],
        "contour_gray": [], "texture_gray": [], "low_gray": [],
        "degraded_need": [], "identity_need": [], "flat_need": [],
    }
    correlations: list[float] = []
    for batch in loader:
        flat = recoverable_source(flatten(batch), noisy=False)
        with torch.autocast(device_type="cuda", dtype=torch.bfloat16):
            details = model.forward_details(flat["source"])
        source = flat["source"].float()
        target = flat["target"].float()
        prediction = details.output.float()
        degraded = (flat["mode"] == 0) | (flat["mode"] == 1)
        identity = flat["mode"] == 2
        flat_rows = flat["mode"] == 3
        raw_error = (source[degraded] - target[degraded]).abs().flatten(1).mean(1) * 255
        pred_error = (prediction[degraded] - target[degraded]).abs().flatten(1).mean(1) * 255
        raw_hf = (highpass(source[degraded], 3) - highpass(target[degraded], 3)).abs().flatten(1).mean(1) * 255
        pred_hf = (highpass(prediction[degraded], 3) - highpass(target[degraded], 3)).abs().flatten(1).mean(1) * 255
        rows["raw_mae_gray"].extend(raw_error.cpu().tolist())
        rows["prediction_mae_gray"].extend(pred_error.cpu().tolist())
        rows["raw_hf_gray"].extend(raw_hf.cpu().tolist())
        rows["prediction_hf_gray"].extend(pred_hf.cpu().tolist())
        rows["change_gray"].extend(((prediction[degraded] - source[degraded]).abs().flatten(1).mean(1) * 255).cpu().tolist())
        if bool(identity.any()):
            rows["identity_change_gray"].extend(((prediction[identity] - source[identity]).abs().flatten(1).mean(1) * 255).cpu().tolist())
        if bool(flat_rows.any()):
            rows["flat_raw_mae_gray"].extend(((source[flat_rows] - target[flat_rows]).abs().flatten(1).mean(1) * 255).cpu().tolist())
            rows["flat_prediction_mae_gray"].extend(((prediction[flat_rows] - target[flat_rows]).abs().flatten(1).mean(1) * 255).cpu().tolist())
        rows["low_gray"].append(float(details.low_delta.float().abs().mean() * 255))
        rows["contour_gray"].append(float(details.contour_delta.float().abs().mean() * 255))
        rows["texture_gray"].append(float(details.texture_delta.float().abs().mean() * 255))
        if hasattr(details, "need_confidence"):
            need = details.need_confidence.float().flatten(1).mean(1)
            rows["degraded_need"].extend(need[degraded].cpu().tolist())
            rows["identity_need"].extend(need[identity].cpu().tolist())
            rows["flat_need"].extend(need[flat_rows].cpu().tolist())
        a = highpass(source[degraded], 3).flatten(1)
        b = highpass(target[degraded], 3).flatten(1)
        a, b = a - a.mean(1, keepdim=True), b - b.mean(1, keepdim=True)
        correlations.extend(((a * b).sum(1) / torch.sqrt(a.square().sum(1) * b.square().sum(1) + 1e-8)).cpu().tolist())
    result = {key: float(np.mean(value)) for key, value in rows.items()}
    result["mae_improvement_fraction"] = 1.0 - result["prediction_mae_gray"] / result["raw_mae_gray"]
    result["hf_improvement_fraction"] = 1.0 - result["prediction_hf_gray"] / result["raw_hf_gray"]
    result["source_target_hf_correlation"] = float(np.mean(correlations))
    return result


def train_probe(seed: int = 10321, steps: int = 600) -> dict[str, object]:
    torch.manual_seed(seed)
    np.random.seed(seed)
    train_dataset = R102Dataset("train", 128, 11)
    validation_dataset = R102Dataset("validation", 128, 0, validation_limit=48)
    train_loader = DataLoader(Subset(train_dataset, list(range(256))), batch_size=8, shuffle=True, num_workers=0, drop_last=True)
    validation_loader = DataLoader(validation_dataset, batch_size=8, shuffle=False, num_workers=0)
    model = build_model(base=16).to(DEVICE).to(memory_format=torch.channels_last)
    active_initialize(model)
    optimizer = torch.optim.AdamW(model.parameters(), lr=3.0e-4, weight_decay=2.0e-5)
    before = evaluate(model, validation_loader)
    iterator = iter(train_loader)
    trace: list[dict[str, float]] = []
    for step in range(1, steps + 1):
        try:
            batch = next(iterator)
        except StopIteration:
            iterator = iter(train_loader)
            batch = next(iterator)
        flat = recoverable_source(flatten(batch), noisy=True)
        optimizer.zero_grad(set_to_none=True)
        with torch.autocast(device_type="cuda", dtype=torch.bfloat16):
            details = model.forward_details(flat["source"])
            loss = objective(details, flat)
        loss.backward()
        norm = torch.nn.utils.clip_grad_norm_(model.parameters(), 3.0)
        optimizer.step()
        if step in {1, 25, 100, 300, steps}:
            trace.append({"step": step, "loss": float(loss.detach()), "gradient_norm": float(norm)})
    after = evaluate(model, validation_loader)
    return {"seed": seed, "steps": steps, "before": before, "after": after, "trace": trace}


def train_candidate_probe(seed: int = 10323, steps: int = 800) -> dict[str, object]:
    torch.manual_seed(seed)
    np.random.seed(seed)
    train_dataset = R102Dataset("train", 128, 11)
    validation_dataset = R102Dataset("validation", 128, 0, validation_limit=48)
    train_loader = DataLoader(Subset(train_dataset, list(range(384))), batch_size=12, shuffle=True, num_workers=0, drop_last=True)
    validation_loader = DataLoader(validation_dataset, batch_size=8, shuffle=False, num_workers=0)
    model = build_model(base=16)
    remove_pixel_normalization(model)
    model = model.to(DEVICE).to(memory_format=torch.channels_last)
    active_initialize(model)
    optimizer = torch.optim.AdamW(model.parameters(), lr=1.2e-4, weight_decay=2.0e-5)
    before = evaluate(model, validation_loader)
    iterator = iter(train_loader)
    trace: list[dict[str, float]] = []
    for step in range(1, steps + 1):
        try:
            batch = next(iterator)
        except StopIteration:
            iterator = iter(train_loader)
            batch = next(iterator)
        flat = recoverable_source(flatten(batch), noisy=True)
        optimizer.zero_grad(set_to_none=True)
        with torch.autocast(device_type="cuda", dtype=torch.bfloat16):
            details = model.forward_details(flat["source"])
            loss = candidate_objective(details, flat)
        loss.backward()
        norm = torch.nn.utils.clip_grad_norm_(model.parameters(), 10.0)
        optimizer.step()
        if step in {1, 25, 100, 300, 600, steps}:
            trace.append({"step": step, "loss": float(loss.detach()), "gradient_norm": float(norm)})
    after = evaluate(model, validation_loader)
    return {"seed": seed, "steps": steps, "before": before, "after": after, "trace": trace}


def train_nogate_counterfactual_probe(seed: int = 10333, steps: int = 1200) -> dict[str, object]:
    torch.manual_seed(seed)
    np.random.seed(seed)
    train_dataset = R102Dataset("train", 128, 11)
    validation_dataset = R102Dataset("validation", 128, 0, validation_limit=48)
    train_loader = DataLoader(Subset(train_dataset, list(range(512))), batch_size=12, shuffle=True, num_workers=0, drop_last=True)
    validation_loader = DataLoader(validation_dataset, batch_size=8, shuffle=False, num_workers=0)
    model = build_model(base=16)
    remove_pixel_normalization(model)
    model = model.to(DEVICE).to(memory_format=torch.channels_last)
    active_initialize(model)
    optimizer = torch.optim.AdamW(model.parameters(), lr=1.0e-4, weight_decay=1.0e-5)
    before = evaluate(model, validation_loader)
    iterator = iter(train_loader)
    trace: list[dict[str, float]] = []
    for step in range(1, steps + 1):
        try:
            batch = next(iterator)
        except StopIteration:
            iterator = iter(train_loader); batch = next(iterator)
        flat = counterfactual_bundle(recoverable_source(flatten(batch), noisy=True))
        optimizer.zero_grad(set_to_none=True)
        with torch.autocast(device_type="cuda", dtype=torch.bfloat16):
            details = model.forward_details(flat["source"])
            loss = candidate_objective(details, flat)
        loss.backward(); norm = torch.nn.utils.clip_grad_norm_(model.parameters(), 10.0); optimizer.step()
        if step in {1, 100, 300, 600, 900, steps}:
            trace.append({"step": step, "loss": float(loss.detach()), "gradient_norm": float(norm)})
    after = evaluate(model, validation_loader)
    return {"seed": seed, "steps": steps, "before": before, "after": after, "trace": trace}


def train_gated_candidate_probe(seed: int = 10327, steps: int = 1000) -> dict[str, object]:
    torch.manual_seed(seed)
    np.random.seed(seed)
    train_dataset = R102Dataset("train", 128, 11)
    validation_dataset = R102Dataset("validation", 128, 0, validation_limit=48)
    train_loader = DataLoader(Subset(train_dataset, list(range(512))), batch_size=16, shuffle=True, num_workers=0, drop_last=True)
    validation_loader = DataLoader(validation_dataset, batch_size=8, shuffle=False, num_workers=0)
    model = build_candidate(base=16).to(DEVICE).to(memory_format=torch.channels_last)
    optimizer = torch.optim.AdamW(model.parameters(), lr=1.2e-4, weight_decay=2.0e-5)
    before = evaluate(model, validation_loader)
    iterator = iter(train_loader)
    trace: list[dict[str, float]] = []
    for step in range(1, steps + 1):
        try:
            batch = next(iterator)
        except StopIteration:
            iterator = iter(train_loader)
            batch = next(iterator)
        flat = counterfactual_bundle(recoverable_source(flatten(batch), noisy=True))
        optimizer.zero_grad(set_to_none=True)
        with torch.autocast(device_type="cuda", dtype=torch.bfloat16):
            details = model.forward_details(flat["source"])
            loss = candidate_objective(details, flat)
        loss.backward()
        norm = torch.nn.utils.clip_grad_norm_(model.parameters(), 10.0)
        optimizer.step()
        if step in {1, 25, 100, 300, 600, steps}:
            trace.append({
                "step": step,
                "loss": float(loss.detach()),
                "gradient_norm": float(norm),
                "need_mean": float(details.need_confidence.detach().float().mean()),
            })
    after = evaluate(model, validation_loader)
    return {"seed": seed, "steps": steps, "before": before, "after": after, "trace": trace}


def train_staged_candidate_probe(seed: int = 10330) -> dict[str, object]:
    torch.manual_seed(seed)
    np.random.seed(seed)
    train_dataset = R102Dataset("train", 128, 11)
    validation_dataset = R102Dataset("validation", 128, 0, validation_limit=48)
    train_loader = DataLoader(Subset(train_dataset, list(range(512))), batch_size=16, shuffle=True, num_workers=0, drop_last=True)
    validation_loader = DataLoader(validation_dataset, batch_size=8, shuffle=False, num_workers=0)
    model = build_candidate(base=16).to(DEVICE).to(memory_format=torch.channels_last)
    before = evaluate(model, validation_loader)
    trace: list[dict[str, float]] = []

    # Stage A: learn the inverse itself with the blend fully open.
    model.force_need = 1.0
    for parameter in model.need_body.parameters():
        parameter.requires_grad_(False)
    optimizer = torch.optim.AdamW((p for p in model.parameters() if p.requires_grad), lr=1.2e-4, weight_decay=2.0e-5)
    iterator = iter(train_loader)
    for step in range(1, 701):
        try:
            batch = next(iterator)
        except StopIteration:
            iterator = iter(train_loader); batch = next(iterator)
        flat = recoverable_source(flatten(batch), noisy=True)
        selector = flat["mode"] != 2
        flat = {key: value[selector] for key, value in flat.items()}
        flat["disable_gate_loss"] = True
        optimizer.zero_grad(set_to_none=True)
        with torch.autocast(device_type="cuda", dtype=torch.bfloat16):
            details = model.forward_details(flat["source"])
            loss = candidate_objective(details, flat)
        loss.backward(); norm = torch.nn.utils.clip_grad_norm_(model.parameters(), 10.0); optimizer.step()
        if step in {1, 100, 300, 500, 700}:
            trace.append({"stage": "inverse", "step": step, "loss": float(loss.detach()), "gradient_norm": float(norm)})
    inverse_learned = evaluate(model, validation_loader)

    # Stage B: freeze the learned inverse and teach only the blend gate from
    # same-content degraded/clear counterfactuals.
    model.force_need = None
    for parameter in model.parameters():
        parameter.requires_grad_(False)
    for parameter in model.need_body.parameters():
        parameter.requires_grad_(True)
    optimizer = torch.optim.AdamW(model.need_body.parameters(), lr=3.0e-4, weight_decay=1.0e-5)
    iterator = iter(train_loader)
    for step in range(1, 501):
        try:
            batch = next(iterator)
        except StopIteration:
            iterator = iter(train_loader); batch = next(iterator)
        flat = counterfactual_bundle(recoverable_source(flatten(batch), noisy=True))
        count = int(flat["counterfactual_count"])
        optimizer.zero_grad(set_to_none=True)
        with torch.autocast(device_type="cuda", dtype=torch.bfloat16):
            details = model.forward_details(flat["source"])
            residual = flat["target"].float() - flat["source"].float()
            desired = (F.avg_pool2d(residual.abs(), 9, stride=1, padding=4) / (3.0 / 255.0)).clamp(0.0, 1.0)
            desired[count:count * 2] = 0.0
            gate = details.need_confidence.float()
            gate_loss = F.mse_loss(gate, desired)
            degraded_gate = gate[:count].flatten(1).mean(1)
            clear_gate = gate[count:count * 2].flatten(1).mean(1)
            gate_loss = gate_loss + F.relu(0.35 - (degraded_gate - clear_gate)).mean()
            clear_delta = details.total_delta.float()[count:count * 2]
            gate_loss = gate_loss + 0.30 * clear_delta.abs().mean()
        gate_loss.backward(); norm = torch.nn.utils.clip_grad_norm_(model.need_body.parameters(), 10.0); optimizer.step()
        if step in {1, 100, 250, 500}:
            trace.append({
                "stage": "gate", "step": step, "loss": float(gate_loss.detach()),
                "gradient_norm": float(norm), "degraded_gate": float(degraded_gate.mean().detach()),
                "clear_gate": float(clear_gate.mean().detach()),
            })
    gate_learned = evaluate(model, validation_loader)

    # Stage C: short low-rate joint settlement.
    for parameter in model.parameters():
        parameter.requires_grad_(True)
    gate_parameters = list(model.need_body.parameters())
    gate_ids = {id(parameter) for parameter in gate_parameters}
    body_parameters = [parameter for parameter in model.parameters() if id(parameter) not in gate_ids]
    optimizer = torch.optim.AdamW([
        {"params": body_parameters, "lr": 3.0e-5},
        {"params": gate_parameters, "lr": 8.0e-5},
    ], weight_decay=1.0e-5)
    iterator = iter(train_loader)
    for step in range(1, 301):
        try:
            batch = next(iterator)
        except StopIteration:
            iterator = iter(train_loader); batch = next(iterator)
        flat = counterfactual_bundle(recoverable_source(flatten(batch), noisy=True))
        optimizer.zero_grad(set_to_none=True)
        with torch.autocast(device_type="cuda", dtype=torch.bfloat16):
            details = model.forward_details(flat["source"])
            loss = candidate_objective(details, flat)
        loss.backward(); norm = torch.nn.utils.clip_grad_norm_(model.parameters(), 10.0); optimizer.step()
        if step in {1, 100, 200, 300}:
            trace.append({"stage": "joint", "step": step, "loss": float(loss.detach()), "gradient_norm": float(norm)})
    after = evaluate(model, validation_loader)
    return {
        "seed": seed,
        "stages": {"inverse": 700, "gate": 500, "joint": 300},
        "before": before,
        "inverse_learned": inverse_learned,
        "gate_learned": gate_learned,
        "after": after,
        "trace": trace,
    }


def single_sample_overfit(seed: int = 10322, steps: int = 800) -> dict[str, object]:
    """A reconstruction network must be able to memorize one fixed inverse pair."""
    torch.manual_seed(seed)
    np.random.seed(seed)
    dataset = R102Dataset("train", 128, 11)
    index = next(i for i in range(len(dataset)) if int(dataset[i]["mode"]) in (0, 1))
    batch = next(iter(DataLoader(Subset(dataset, [index]), batch_size=1, num_workers=0)))
    fixed = recoverable_source(flatten(batch), noisy=False)
    model = build_model(base=16).to(DEVICE).to(memory_format=torch.channels_last)
    active_initialize(model)
    optimizer = torch.optim.AdamW(model.parameters(), lr=8.0e-5, weight_decay=0.0)

    def measure() -> dict[str, float]:
        model.eval()
        with torch.inference_mode(), torch.autocast(device_type="cuda", dtype=torch.bfloat16):
            details = model.forward_details(fixed["source"])
        prediction = details.output.float()
        source, target = fixed["source"].float(), fixed["target"].float()
        return {
            "raw_mae_gray": float((source - target).abs().mean() * 255),
            "prediction_mae_gray": float((prediction - target).abs().mean() * 255),
            "change_gray": float((prediction - source).abs().mean() * 255),
            "low_gray": float(details.low_delta.float().abs().mean() * 255),
            "contour_gray": float(details.contour_delta.float().abs().mean() * 255),
            "texture_gray": float(details.texture_delta.float().abs().mean() * 255),
        }

    before = measure()
    trace: list[dict[str, float]] = []
    model.train()
    for step in range(1, steps + 1):
        optimizer.zero_grad(set_to_none=True)
        with torch.autocast(device_type="cuda", dtype=torch.bfloat16):
            details = model.forward_details(fixed["source"])
            loss = objective(details, fixed)
        loss.backward()
        norm = torch.nn.utils.clip_grad_norm_(model.parameters(), 20.0)
        optimizer.step()
        if step in {1, 10, 50, 200, 500, steps}:
            trace.append({"step": step, "loss": float(loss.detach()), "gradient_norm": float(norm)})
    after = measure()
    return {"seed": seed, "steps": steps, "scene_index": index, "before": before, "after": after, "trace": trace}


def main() -> int:
    report = {
        "single_sample_overfit": single_sample_overfit(),
        "held_out_learning": train_probe(),
    }
    output = ROOT / "reports" / "truth_learning_probe.json"
    output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({"report": str(output), **report}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

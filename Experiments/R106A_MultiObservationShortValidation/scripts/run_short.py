from __future__ import annotations

import json
import math
import random
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import cv2
import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
from PIL import Image, ImageDraw, ImageFont
from scipy import ndimage
from scipy.stats import spearmanr


ROOT = Path(__file__).resolve().parents[1]
CONFIG = json.loads((ROOT / "config" / "experiment.json").read_text(encoding="utf-8"))
RESULTS = ROOT / "results"
REPORTS = ROOT / "reports"
WEIGHTS = ROOT / "weights"


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2), encoding="utf-8")


def seed_all(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)
    torch.backends.cudnn.deterministic = True
    torch.backends.cudnn.benchmark = False


def sigmoid_np(x: np.ndarray) -> np.ndarray:
    return 1.0 / (1.0 + np.exp(-np.clip(x, -40.0, 40.0)))


def polygon_points(center, radius, count, phase, radial=None):
    angles = phase + np.arange(count, dtype=np.float32) * 2.0 * math.pi / count
    radii = np.full(count, radius, dtype=np.float32) if radial is None else radial.astype(np.float32)
    return np.stack([center[0] + radii * np.cos(angles), center[1] + radii * np.sin(angles)], axis=1).round().astype(np.int32)


def draw_high_mask(size: int, factor: int, family: str, rng: np.random.Generator) -> np.ndarray:
    high = size * factor
    mask = np.zeros((high, high), dtype=np.uint8)
    cx, cy = float(rng.uniform(0.41, 0.59) * high), float(rng.uniform(0.41, 0.59) * high)
    radius = float(rng.uniform(0.17, 0.29) * high)
    if family == "circle":
        cv2.circle(mask, (round(cx), round(cy)), round(radius), 255, -1, cv2.LINE_AA)
    elif family == "ellipse":
        axes = (round(radius * rng.uniform(0.72, 1.28)), round(radius * rng.uniform(0.52, 0.94)))
        cv2.ellipse(mask, (round(cx), round(cy)), axes, float(rng.uniform(-45, 45)), 0, 360, 255, -1, cv2.LINE_AA)
    elif family == "rectangle":
        rect = ((cx, cy), (radius * rng.uniform(1.25, 2.0), radius * rng.uniform(0.95, 1.65)), float(rng.uniform(-45, 45)))
        cv2.fillConvexPoly(mask, cv2.boxPoints(rect).round().astype(np.int32), 255, cv2.LINE_AA)
    elif family == "polygon":
        count = int(rng.integers(5, 10))
        radial = radius * rng.uniform(0.78, 1.16, count)
        cv2.fillPoly(mask, [polygon_points((cx, cy), radius, count, float(rng.uniform(0, math.pi)), radial)], 255, cv2.LINE_AA)
    elif family == "ring":
        cv2.circle(mask, (round(cx), round(cy)), round(radius), 255, -1, cv2.LINE_AA)
        cv2.circle(mask, (round(cx), round(cy)), round(radius * rng.uniform(0.45, 0.72)), 0, -1, cv2.LINE_AA)
    elif family == "crescent":
        cv2.circle(mask, (round(cx), round(cy)), round(radius), 255, -1, cv2.LINE_AA)
        cv2.circle(mask, (round(cx + radius * rng.uniform(0.28, 0.52)), round(cy + rng.uniform(-0.12, 0.12) * radius)), round(radius * rng.uniform(0.82, 0.92)), 0, -1, cv2.LINE_AA)
    elif family == "lobed":
        count = 128
        angles = np.arange(count, dtype=np.float32) * 2.0 * math.pi / count
        lobes = int(rng.integers(4, 9))
        radial = radius * (1.0 + rng.uniform(0.12, 0.25) * np.sin(lobes * angles + rng.uniform(-math.pi, math.pi)))
        cv2.fillPoly(mask, [polygon_points((cx, cy), radius, count, 0.0, radial)], 255, cv2.LINE_AA)
    elif family == "thin_neck":
        left, right = (round(cx - 0.54 * radius), round(cy)), (round(cx + 0.54 * radius), round(cy))
        disk = round(radius * rng.uniform(0.54, 0.68))
        cv2.circle(mask, left, disk, 255, -1, cv2.LINE_AA)
        cv2.circle(mask, right, disk, 255, -1, cv2.LINE_AA)
        neck = max(2, round(radius * rng.uniform(0.09, 0.22)))
        cv2.rectangle(mask, (left[0], round(cy - neck)), (right[0], round(cy + neck)), 255, -1)
    else:
        raise ValueError(family)
    return mask


def warp_np(image: np.ndarray, dx: float, dy: float) -> np.ndarray:
    matrix = np.asarray([[1.0, 0.0, dx], [0.0, 1.0, dy]], dtype=np.float32)
    return cv2.warpAffine(image, matrix, (image.shape[1], image.shape[0]), flags=cv2.INTER_LANCZOS4, borderMode=cv2.BORDER_REFLECT_101)


def latent_from_mask(mask: np.ndarray, factor: int, inside: float, outside: float, width: float):
    binary = mask >= 128
    sdf_high = (ndimage.distance_transform_edt(binary) - ndimage.distance_transform_edt(~binary)).astype(np.float32)
    target_high = outside + (inside - outside) * sigmoid_np(sdf_high / (width * factor))
    return target_high.astype(np.float32), sdf_high


def generate_sample(index: int, split: str, force_identity: bool | None = None) -> dict[str, Any]:
    size, factor, observations = int(CONFIG["data"]["image_size"]), int(CONFIG["data"]["supersample"]), 4
    salt = {"train": 100_000, "validation": 200_000, "test": 300_000}[split]
    rng = np.random.default_rng(int(CONFIG["training"]["seed"]) + salt + index * 7919)
    families = CONFIG["data"]["heldout_shape_families"] if split == "test" else CONFIG["data"]["train_shape_families"]
    family = str(families[index % len(families)])
    mask_high = draw_high_mask(size, factor, family, rng)
    width = float(rng.uniform(0.48, 1.18))
    polarity = 1.0 if rng.random() < 0.5 else -1.0
    outside = float(rng.uniform(0.12, 0.40))
    inside = float(np.clip(outside + polarity * rng.uniform(0.32, 0.62), 0.04, 0.96))
    if abs(inside - outside) < 0.24:
        inside = float(np.clip(outside + polarity * 0.34, 0.04, 0.96))
    target_high, sdf_high = latent_from_mask(mask_high, factor, inside, outside, width)
    target = cv2.resize(target_high, (size, size), interpolation=cv2.INTER_AREA)
    sdf = cv2.resize(sdf_high / factor, (size, size), interpolation=cv2.INTER_AREA)
    coverage = cv2.resize(mask_high.astype(np.float32) / 255.0, (size, size), interpolation=cv2.INTER_AREA)
    identity = bool(force_identity) if force_identity is not None else bool(rng.random() < float(CONFIG["data"]["identity_fraction"]))
    bad_index = -1
    bad_kind = "none"
    if not identity and rng.random() < float(CONFIG["data"]["bad_bundle_fraction"]):
        bad_index = int(rng.integers(1, observations))
        bad_kind = str(rng.choice(["wrong_structure", "occlusion", "severe_noise"]))
    alternate_high = None
    if bad_kind == "wrong_structure":
        alternate_family = str(rng.choice([name for name in CONFIG["data"]["train_shape_families"] + CONFIG["data"]["heldout_shape_families"] if name != family]))
        alternate_mask = draw_high_mask(size, factor, alternate_family, rng)
        alternate_high, _ = latent_from_mask(alternate_mask, factor, inside, outside, width)

    xx, yy = np.meshgrid(np.linspace(-1, 1, size * factor, dtype=np.float32), np.linspace(-1, 1, size * factor, dtype=np.float32))
    aligned, usable = [], np.ones(observations, dtype=np.float32)
    true_shifts, estimated_shifts = [], []
    for observation in range(observations):
        if observation == 0:
            dx = dy = 0.0
            residual_dx = residual_dy = 0.0
        elif observation == 1:
            angle = float(rng.uniform(0, 2 * math.pi))
            magnitude = float(abs(rng.normal(float(CONFIG["data"]["junhua_within_pair_shift_median_px"]), 0.05)))
            dx, dy = magnitude * math.cos(angle), magnitude * math.sin(angle)
            residual_dx, residual_dy = float(rng.uniform(-0.08, 0.08)), float(rng.uniform(-0.08, 0.08))
        else:
            base_dx, base_dy = map(float, CONFIG["data"]["junhua_cross_shift_px"])
            within = float(rng.normal(0.0, 0.06))
            dx = base_dx + float(rng.normal(0.0, 0.06))
            dy = base_dy + within
            residual_dx, residual_dy = float(rng.uniform(-0.30, 0.30)), float(rng.uniform(-0.30, 0.30))
        source_high = alternate_high if observation == bad_index and bad_kind == "wrong_structure" else target_high
        sigma = float(rng.uniform(0.75, 2.1))
        blurred = cv2.GaussianBlur(source_high, (0, 0), sigma * factor, borderType=cv2.BORDER_REFLECT_101)
        shifted = warp_np(blurred, dx * factor, dy * factor)
        exposure = 1.0 if identity else float(rng.uniform(0.78, 1.22))
        gain_center = float(CONFIG["data"]["junhua_pair_gain_median"])
        gain = 1.0 if observation == 0 or identity else float(np.clip(rng.normal(gain_center, 0.012), 0.90, 1.08))
        illumination = np.ones_like(shifted) if identity else np.clip(1.0 + rng.uniform(-0.04, 0.04) * xx + rng.uniform(-0.04, 0.04) * yy, 0.90, 1.10)
        observed_high = np.clip((0.5 + exposure * (shifted - 0.5)) * gain * illumination, 0.0, 1.0)
        low = cv2.resize(observed_high, (size, size), interpolation=cv2.INTER_AREA)
        noise = 0.0 if identity else float(rng.uniform(0.002, 0.014))
        if observation == bad_index and bad_kind == "severe_noise":
            noise = float(rng.uniform(0.05, 0.09))
        low = np.clip(low + rng.normal(0.0, noise, low.shape).astype(np.float32), 0.0, 1.0)
        estimate_dx, estimate_dy = dx + residual_dx, dy + residual_dy
        low = warp_np(low, -estimate_dx, -estimate_dy)
        if observation == bad_index and bad_kind == "occlusion":
            top = int(rng.integers(size // 5, size * 3 // 5))
            left = int(rng.integers(size // 5, size * 3 // 5))
            low[top : top + size // 4, left : left + size // 4] = float(rng.uniform(0.0, 1.0))
        if observation == bad_index:
            usable[observation] = 0.0
        aligned.append(low.astype(np.float32))
        true_shifts.append((dx, dy))
        estimated_shifts.append((estimate_dx, estimate_dy))
    if identity:
        aligned = [target.copy() for _ in range(observations)]
    return {
        "aligned": np.stack(aligned),
        "target": target.astype(np.float32),
        "sdf": sdf.astype(np.float32),
        "width": np.float32(width),
        "inside": np.float32(inside),
        "outside": np.float32(outside),
        "mask": (coverage >= 0.5).astype(np.float32),
        "edge": np.exp(-np.abs(sdf) / 2.5).astype(np.float32),
        "usable": usable,
        "identity": identity,
        "family": family,
        "bad_kind": bad_kind,
        "true_shifts": np.asarray(true_shifts, dtype=np.float32),
        "estimated_shifts": np.asarray(estimated_shifts, dtype=np.float32),
    }


@dataclass
class TensorPopulation:
    aligned: torch.Tensor
    target: torch.Tensor
    sdf: torch.Tensor
    width: torch.Tensor
    inside: torch.Tensor
    outside: torch.Tensor
    mask: torch.Tensor
    edge: torch.Tensor
    usable: torch.Tensor
    identity: torch.Tensor
    families: list[str]
    bad_kinds: list[str]

    def batch(self, indices: np.ndarray, device: torch.device) -> dict[str, torch.Tensor]:
        idx = torch.as_tensor(indices, dtype=torch.long)
        return {name: getattr(self, name)[idx].to(device, non_blocking=True) for name in ["aligned", "target", "sdf", "width", "inside", "outside", "mask", "edge", "usable", "identity"]}


def build_population(count: int, split: str) -> TensorPopulation:
    rows = [generate_sample(index, split) for index in range(count)]
    def stack(name, channel=False):
        value = np.stack([row[name] for row in rows])
        if channel:
            value = value[:, None]
        return torch.from_numpy(value)
    return TensorPopulation(
        aligned=stack("aligned"), target=stack("target", True), sdf=stack("sdf", True),
        width=torch.tensor([row["width"] for row in rows]), inside=torch.tensor([row["inside"] for row in rows]),
        outside=torch.tensor([row["outside"] for row in rows]), mask=stack("mask", True), edge=stack("edge", True),
        usable=stack("usable"), identity=torch.tensor([row["identity"] for row in rows], dtype=torch.bool),
        families=[row["family"] for row in rows], bad_kinds=[row["bad_kind"] for row in rows],
    )


class ConvBlock(nn.Module):
    def __init__(self, c_in, c_out, stride=1, dilation=1):
        super().__init__(); self.conv = nn.Conv2d(c_in, c_out, 3, stride=stride, padding=dilation, dilation=dilation); self.act = nn.SiLU()
    def forward(self, x): return self.act(self.conv(x))


class ResBlock(nn.Module):
    def __init__(self, channels, dilation=1):
        super().__init__(); self.a = ConvBlock(channels, channels, dilation=dilation); self.b = nn.Conv2d(channels, channels, 3, padding=dilation, dilation=dilation)
    def forward(self, x): return F.silu(x + self.b(self.a(x)))


class ReferenceEvidenceNet(nn.Module):
    def __init__(self):
        super().__init__()
        base = int(CONFIG["model"]["base_channels"])
        self.e1 = nn.Sequential(ConvBlock(1, base), ResBlock(base))
        self.down = ConvBlock(base, base * 2, stride=2)
        self.mid = nn.Sequential(ResBlock(base * 2), ResBlock(base * 2, 2))
        self.up = ConvBlock(base * 2, base)
        self.frame_fuse = nn.Sequential(ConvBlock(base * 2, base), ResBlock(base))
        self.compatibility = nn.Sequential(ConvBlock(base * 3, base), nn.Conv2d(base, 1, 1))
        self.evidence_fuse = nn.Sequential(ConvBlock(base * 4 + 1, base), ResBlock(base), ResBlock(base, 2))
        self.residual_head = nn.Sequential(ConvBlock(base, base), nn.Conv2d(base, 1, 1))
        self.sdf_head = nn.Sequential(ConvBlock(base, base), nn.Conv2d(base, 1, 1))
        nn.init.zeros_(self.residual_head[-1].weight); nn.init.zeros_(self.residual_head[-1].bias)
        nn.init.zeros_(self.sdf_head[-1].weight); nn.init.zeros_(self.sdf_head[-1].bias)

    def encode(self, x):
        skip = self.e1(x); low = self.mid(self.down(skip)); up = F.interpolate(low, size=x.shape[-2:], mode="bilinear", align_corners=False)
        return self.frame_fuse(torch.cat([self.up(up), skip], dim=1))

    def forward(self, frames: torch.Tensor, valid: torch.Tensor) -> dict[str, torch.Tensor]:
        batch, observations, height, width = frames.shape
        feature = self.encode(frames.reshape(batch * observations, 1, height, width)).reshape(batch, observations, -1, height, width)
        reference = feature[:, 0]
        logits = []
        for observation in range(observations):
            current = feature[:, observation]
            logits.append(self.compatibility(torch.cat([reference, current, (reference - current).abs()], dim=1)))
        logits = torch.stack(logits, dim=1)[:, :, 0]
        learned = torch.sigmoid(logits) * valid[:, :, None, None]
        reference_weight = valid[:, 0:1, None, None].expand(-1, -1, height, width)
        weights = torch.cat([reference_weight, learned[:, 1:]], dim=1)
        denominator = weights.sum(dim=1, keepdim=True).clamp_min(1e-5)
        mean = (feature * weights[:, :, None]).sum(dim=1) / denominator
        variance = ((feature - mean[:, None]).square() * weights[:, :, None]).sum(dim=1) / denominator
        count_map = (denominator / float(observations)).expand(-1, 1, height, width)
        fused = self.evidence_fuse(torch.cat([reference, mean, torch.sqrt(variance + 1e-8), reference - mean, count_map], dim=1))
        residual = float(CONFIG["model"]["residual_bound"]) * torch.tanh(self.residual_head(fused))
        output = (frames[:, 0:1] + residual).clamp(0.0, 1.0)
        sdf = 24.0 * torch.tanh(self.sdf_head(fused))
        return {"output": output, "sdf": sdf, "compatibility_logits": logits, "weights": weights, "residual": residual}


def make_valid(batch: int, used: int, device) -> torch.Tensor:
    value = torch.zeros((batch, 4), device=device); value[:, :used] = 1.0; return value


def gradients(x): return x[..., 1:, :] - x[..., :-1, :], x[..., :, 1:] - x[..., :, :-1]


def soft_centroid(image, inside, outside):
    denominator = (inside - outside)[:, None, None, None]
    normalized = (image - outside[:, None, None, None]) / torch.where(denominator.abs() > 1e-5, denominator, torch.ones_like(denominator))
    probability = torch.sigmoid((normalized - 0.5) * 12.0)
    height, width = image.shape[-2:]
    yy, xx = torch.meshgrid(torch.arange(height, device=image.device, dtype=image.dtype), torch.arange(width, device=image.device, dtype=image.dtype), indexing="ij")
    total = probability.sum(dim=(2, 3)).clamp_min(1e-5)
    return (probability * xx).sum(dim=(2, 3)) / total, (probability * yy).sum(dim=(2, 3)) / total


def loss_parts(model, batch, valid):
    details = model(batch["aligned"], valid); output, target = details["output"], batch["target"]
    output_error = torch.sqrt((output - target).square() + 1e-6).mean()
    oy, ox = gradients(output); ty, tx = gradients(target); gradient = (oy - ty).abs().mean() + (ox - tx).abs().mean()
    edge_weight = 0.15 + 0.85 * batch["edge"]
    sdf = F.smooth_l1_loss(details["sdf"] / 24.0, batch["sdf"].clamp(-24, 24) / 24.0, reduction="none", beta=0.04)
    sdf = (sdf * edge_weight).sum() / edge_weight.sum().clamp_min(1.0)
    compatibility_target = batch["usable"] * valid
    compatibility = F.binary_cross_entropy_with_logits(details["compatibility_logits"], compatibility_target[:, :, None, None].expand_as(details["compatibility_logits"]), reduction="none")
    compatibility = (compatibility * valid[:, :, None, None]).sum() / (valid.sum() * output.shape[-1] * output.shape[-2]).clamp_min(1.0)
    px, py = soft_centroid(output, batch["inside"], batch["outside"]); txc, tyc = soft_centroid(target, batch["inside"], batch["outside"])
    center = (px - txc).abs().mean() + (py - tyc).abs().mean()
    identity = (output[batch["identity"]] - batch["aligned"][batch["identity"], 0:1]).abs().mean() if batch["identity"].any() else output_error.new_zeros(())
    total = output_error + 0.24 * gradient + 0.30 * sdf + 0.10 * compatibility + 0.08 * center + 0.20 * identity
    return {"total": total, "output": output_error, "gradient": gradient, "sdf": sdf, "compatibility": compatibility, "center": center, "identity": identity}


def make_schedule(count):
    rng = np.random.default_rng(int(CONFIG["training"]["seed"]) + 55); steps = int(CONFIG["training"]["steps"])
    batches = rng.integers(0, count, size=(steps, int(CONFIG["training"]["batch_size"])), endpoint=False)
    used = rng.choice(np.asarray([1, 2, 4]), size=steps, p=[0.30, 0.30, 0.40])
    return batches, used


def train_model(train_population, validation, device):
    seed_all(int(CONFIG["training"]["seed"])); model = ReferenceEvidenceNet().to(device)
    optimizer = torch.optim.AdamW(model.parameters(), lr=float(CONFIG["training"]["learning_rate"]), weight_decay=float(CONFIG["training"]["weight_decay"]))
    schedule, used_schedule = make_schedule(len(train_population.families)); history = []; started = time.perf_counter()
    for step, indices in enumerate(schedule, start=1):
        batch = train_population.batch(indices, device); valid = make_valid(len(indices), int(used_schedule[step - 1]), device)
        optimizer.zero_grad(set_to_none=True); parts = loss_parts(model, batch, valid); parts["total"].backward(); torch.nn.utils.clip_grad_norm_(model.parameters(), 5.0); optimizer.step()
        if step == 1 or step % int(CONFIG["training"]["log_every"]) == 0 or step == len(schedule):
            with torch.inference_mode():
                ids = np.arange(min(36, len(validation.families))); vb = validation.batch(ids, device)
                vals = {n: loss_parts(model, vb, make_valid(len(ids), n, device)) for n in [1, 2, 4]}
            row = {"step": step, "used": int(used_schedule[step - 1]), "train_total": float(parts["total"].detach().cpu()), "train_output": float(parts["output"].detach().cpu()), "train_compatibility": float(parts["compatibility"].detach().cpu()), "seconds": time.perf_counter() - started}
            for n in [1, 2, 4]: row[f"validation_n{n}_total"] = float(vals[n]["total"].detach().cpu()); row[f"validation_n{n}_output"] = float(vals[n]["output"].detach().cpu())
            history.append(row); print(json.dumps({"arm": "r106a", **row}), flush=True)
    WEIGHTS.mkdir(parents=True, exist_ok=True); torch.save({"model": model.state_dict(), "config": CONFIG, "seed": int(CONFIG["training"]["seed"])}, WEIGHTS / "r106a_step1500.pth")
    return model, history, used_schedule


@torch.inference_mode()
def predict(model, population, used, device, mismatch=False):
    outputs, weights = [], []
    batch_size = int(CONFIG["training"]["batch_size"])
    for start in range(0, len(population.families), batch_size):
        ids = np.arange(start, min(len(population.families), start + batch_size)); batch = population.batch(ids, device)
        if mismatch:
            changed = batch["aligned"].clone()
            for observation in range(1, 4): changed[:, observation] = torch.roll(changed[:, observation], shifts=observation, dims=0)
            batch["aligned"] = changed
        details = model(batch["aligned"], make_valid(len(ids), used, device))
        outputs.append(details["output"].cpu().numpy()[:, 0]); weights.append(details["weights"].mean(dim=(2, 3)).cpu().numpy())
    return np.concatenate(outputs), np.concatenate(weights)


def binary_metrics(output, mask, sdf, width_true, inside, outside):
    denominator = inside - outside; normalized = np.clip((output - outside) / (denominator if abs(denominator) > 1e-5 else 1.0), 0, 1)
    pred, truth = normalized >= 0.5, mask >= 0.5; intersection = np.logical_and(pred, truth).sum(); union = np.logical_or(pred, truth).sum()
    def center(value):
        y, x = np.nonzero(value); return (float(x.mean()), float(y.mean())) if len(x) else (999.0, 999.0)
    px, py = center(pred); tx, ty = center(truth); centroid = math.hypot(px - tx, py - ty)
    pe, te = np.logical_xor(pred, ndimage.binary_erosion(pred)), np.logical_xor(truth, ndimage.binary_erosion(truth))
    if pe.any() and te.any():
        boundary = 0.5 * (float(ndimage.distance_transform_edt(~te)[pe].mean()) + float(ndimage.distance_transform_edt(~pe)[te].mean()))
    else: boundary = 999.0
    valid = (np.abs(sdf) <= 5) & (normalized > 0.02) & (normalized < 0.98)
    if valid.sum() >= 48:
        x = sdf[valid]; y = np.log(normalized[valid] / np.clip(1 - normalized[valid], 1e-5, None)); slope, intercept = np.linalg.lstsq(np.stack([x, np.ones_like(x)], 1), y, rcond=None)[0]
        transition_center = abs(float(-intercept / slope)) if abs(slope) > 1e-5 else 99.0; inferred_width = abs(float(1 / slope)) if abs(slope) > 1e-5 else 99.0
    else: transition_center = inferred_width = 99.0
    return {"iou": float(intersection / max(union, 1)), "boundary_distance_px": boundary, "centroid_error_px": centroid, "transition_center_error_px": transition_center, "transition_width_error_px": abs(inferred_width - width_true)}


def summarize(outputs, population):
    target, mask, sdf = population.target.numpy()[:, 0], population.mask.numpy()[:, 0], population.sdf.numpy()[:, 0]
    result = {}
    for name, images in outputs.items():
        rows = [binary_metrics(images[i], mask[i], sdf[i], float(population.width[i]), float(population.inside[i]), float(population.outside[i])) for i in range(len(images))]
        value = {key: float(np.median([row[key] for row in rows])) for key in rows[0]}; value["mean_abs_error_gray"] = float(np.mean(np.abs(images - target)) * 255); value["images"] = len(images)
        result[name] = {"summary": value, "per_image": rows}
    return result


@torch.inference_mode()
def jackknife(model, population, device):
    outputs = []
    for observation in range(4):
        values = []
        for start in range(0, len(population.families), int(CONFIG["training"]["batch_size"])):
            ids = np.arange(start, min(len(population.families), start + int(CONFIG["training"]["batch_size"]))); batch = population.batch(ids, device); frames = batch["aligned"].clone()
            frames[:, 0], frames[:, observation] = batch["aligned"][:, observation].clone(), batch["aligned"][:, 0].clone()
            values.append(model(frames, make_valid(len(ids), 1, device))["output"].cpu().numpy()[:, 0])
        outputs.append(np.concatenate(values))
    stack = np.stack(outputs, 1); return stack.std(axis=1), stack


def centroid_np(output, inside, outside):
    norm = (output - outside) / (inside - outside if abs(inside - outside) > 1e-5 else 1); y, x = np.nonzero(norm >= 0.5); return (float(x.mean()), float(y.mean())) if len(x) else (np.nan, np.nan)


@torch.inference_mode()
def motion_exposure(model, population, device):
    modes = {"n1": 1, "n2": 2, "n4": 4}; motion = {k: [] for k in modes}; exposure = {k: [] for k in modes}; shifts = [(0.5, -0.75), (-0.65, 0.4), (0.9, 0.55), (-0.4, -0.9)]
    for i in range(min(24, len(population.families))):
        batch = population.batch(np.asarray([i]), device); dx, dy = shifts[i % 4]; frames = batch["aligned"].cpu().numpy(); shifted = frames.copy()
        for j in range(4): shifted[0, j] = warp_np(shifted[0, j], dx, dy)
        shifted = torch.from_numpy(shifted).to(device); inside, outside = float(population.inside[i]), float(population.outside[i])
        for name, n in modes.items():
            a = model(batch["aligned"], make_valid(1, n, device))["output"][0, 0].cpu().numpy(); b = model(shifted, make_valid(1, n, device))["output"][0, 0].cpu().numpy(); ca, cb = centroid_np(a, inside, outside), centroid_np(b, inside, outside); motion[name].append(math.hypot((cb[0]-ca[0])-dx, (cb[1]-ca[1])-dy))
    for i in range(min(16, len(population.families))):
        batch = population.batch(np.asarray([i]), device); inside, outside = float(population.inside[i]), float(population.outside[i])
        for name, n in modes.items():
            centers=[]
            for scale in [0.78,0.90,1.0,1.12,1.24]:
                frames=torch.clamp(0.5+scale*(batch["aligned"]-0.5),0,1); out=model(frames,make_valid(1,n,device))["output"][0,0].cpu().numpy(); centers.append(centroid_np(out,float(np.clip(0.5+scale*(inside-0.5),0,1)),float(np.clip(0.5+scale*(outside-0.5),0,1))))
            x=np.asarray([c[0] for c in centers]); y=np.asarray([c[1] for c in centers]); exposure[name].append(float(np.sqrt(np.nanvar(x)+np.nanvar(y))))
    return {name:{"motion_median_px":float(np.median(motion[name])),"motion_p95_px":float(np.percentile(motion[name],95)),"exposure_median_px":float(np.median(exposure[name])),"exposure_p95_px":float(np.percentile(exposure[name],95))} for name in modes}


@torch.inference_mode()
def tile_metrics(model, population, used, device):
    core, halo = 48, 32; maxima=[]
    for i in range(min(8,len(population.families))):
        frames=population.aligned[i:i+1].to(device); padded=F.pad(frames,(halo,halo,halo,halo),mode="reflect"); full=model(padded,make_valid(1,used,device))["output"][...,halo:-halo,halo:-halo]; tiled=torch.empty_like(full)
        for top in [0,48]:
            for left in [0,48]:
                tile=padded[...,top:top+core+2*halo,left:left+core+2*halo]; pred=model(tile,make_valid(1,used,device))["output"]; tiled[...,top:top+core,left:left+core]=pred[...,halo:halo+core,halo:halo+core]
        maxima.append(float(((full-tiled).abs()*255).max().cpu()))
    return {"max_abs_gray":max(maxima)}


def render_visual(population, outputs, summary):
    indices=[0,1,2,30,60,90,120,143]; columns=["Reference","Target","N=1","N=2","N=4","N4 error x8"]; panel=150; gap=10; canvas=Image.new("RGB",(gap+len(columns)*(panel+gap),32+len(indices)*184+gap),"white"); draw=ImageDraw.Draw(canvas); font=ImageFont.load_default()
    for c,label in enumerate(columns): draw.text((gap+c*(panel+gap),10),label,fill="black",font=font)
    source=population.aligned.numpy()[:,0]; target=population.target.numpy()[:,0]
    for r,i in enumerate(indices):
        values=[source[i],target[i],outputs["n1"][i],outputs["n2"][i],outputs["n4"][i],np.abs(outputs["n4"][i]-target[i])*8]; top=32+r*184
        for c,v in enumerate(values):
            clipped=np.clip(v,0,1); rgb=np.stack([clipped,clipped*.18,np.zeros_like(clipped)],-1) if c==5 else np.repeat(clipped[...,None],3,-1); image=Image.fromarray(np.round(rgb*255).astype(np.uint8),"RGB").resize((panel,panel),Image.Resampling.BICUBIC); canvas.paste(image,(gap+c*(panel+gap),top))
        draw.text((gap,top+panel+7),f"{population.families[i]} | bad={population.bad_kinds[i]}",fill="black",font=font)
    REPORTS.mkdir(parents=True,exist_ok=True); canvas.save(REPORTS/"R106A_SYNTHETIC_QA.png",optimize=True)


def main():
    RESULTS.mkdir(parents=True,exist_ok=True); REPORTS.mkdir(parents=True,exist_ok=True); WEIGHTS.mkdir(parents=True,exist_ok=True)
    if not torch.cuda.is_available(): raise RuntimeError("CUDA required")
    device=torch.device("cuda:0"); seed_all(int(CONFIG["training"]["seed"])); print(json.dumps({"stage":"build_populations","device":torch.cuda.get_device_name(0)}),flush=True)
    train_population=build_population(int(CONFIG["data"]["train_samples"]),"train"); print(json.dumps({"stage":"train_ready","samples":len(train_population.families)}),flush=True)
    validation=build_population(int(CONFIG["data"]["validation_samples"]),"validation"); test=build_population(int(CONFIG["data"]["test_samples"]),"test"); print(json.dumps({"stage":"holdouts_ready","validation":len(validation.families),"test":len(test.families)}),flush=True)
    write_json(RESULTS/"population_manifest.json",{"train":len(train_population.families),"validation":len(validation.families),"test":len(test.families),"test_families":{f:test.families.count(f) for f in sorted(set(test.families))},"bad_test":{k:test.bad_kinds.count(k) for k in sorted(set(test.bad_kinds))}})
    model,history,used=train_model(train_population,validation,device); write_json(RESULTS/"training_history.json",history)
    outputs={}; weights={}
    for n in [1,2,4]: outputs[f"n{n}"],weights[f"n{n}"]=predict(model,test,n,device)
    mismatch,mismatch_weights=predict(model,test,4,device,mismatch=True); outputs["mismatch_n4"]=mismatch; outputs["raw_reference"]=test.aligned.numpy()[:,0]
    decomposition=summarize(outputs,test); jack,individual=jackknife(model,test,device); target=test.target.numpy()[:,0]; predicted=jack.mean(axis=(1,2)); actual=np.abs(outputs["n4"]-target).mean(axis=(1,2)); corr=spearmanr(predicted,actual).statistic
    usable=test.usable.numpy(); valid_bad=usable[:,1:]<0.5; valid_good=usable[:,1:]>0.5
    admission={"good_weight_median":float(np.median(weights["n4"][:,1:][valid_good])),"bad_weight_median":float(np.median(weights["n4"][:,1:][valid_bad])) if valid_bad.any() else 0.0,"mismatch_nonreference_weight_median":float(np.median(mismatch_weights[:,1:])),"jackknife_median_gray":float(np.median(predicted)*255),"jackknife_spearman_vs_mae":float(corr if np.isfinite(corr) else 0.0)}
    motion=motion_exposure(model,test,device); tile={f"n{n}":tile_metrics(model,test,n,device) for n in [1,2,4]}
    n1,n2,n4=[decomposition[f"n{n}"]["summary"] for n in [1,2,4]]; mismatch_summary=decomposition["mismatch_n4"]["summary"]
    directions={"n2_boundary":n2["boundary_distance_px"]<n1["boundary_distance_px"],"n4_boundary":n4["boundary_distance_px"]<n2["boundary_distance_px"],"n2_center":n2["transition_center_error_px"]<n1["transition_center_error_px"],"n4_center":n4["transition_center_error_px"]<n2["transition_center_error_px"],"n2_mae":n2["mean_abs_error_gray"]<n1["mean_abs_error_gray"],"n4_mae":n4["mean_abs_error_gray"]<n2["mean_abs_error_gray"],"bad_weight":admission["bad_weight_median"]<admission["good_weight_median"],"mismatch_fallback":mismatch_summary["boundary_distance_px"]<=n1["boundary_distance_px"]*1.25,"jackknife":admission["jackknife_spearman_vs_mae"]>0.2,"tile":tile["n4"]["max_abs_gray"]<0.1,"motion":motion["n4"]["motion_p95_px"]<=motion["n1"]["motion_p95_px"]*1.15,"exposure":motion["n4"]["exposure_median_px"]<=motion["n1"]["exposure_median_px"]*1.15}
    decision={"directions":directions,"synthetic_gate_passed":all(directions.values()),"full_r106_authorized":False,"interpretation":"Synthetic short gate passed; JunHua locked validation is still required." if all(directions.values()) else "Synthetic short gate failed; do not start full R106."}
    summary={"status":"complete","device":torch.cuda.get_device_name(0),"parameter_count":sum(p.numel() for p in model.parameters()),"decomposition":decomposition,"admission":admission,"motion_exposure":motion,"tile":tile,"decision":decision}; write_json(RESULTS/"synthetic_summary.json",summary); render_visual(test,outputs,summary)
    (REPORTS/"R106A_SYNTHETIC_RESULTS.md").write_text("# R106A Synthetic Short Gate\n\n```json\n"+json.dumps({"metrics":{k:v["summary"] for k,v in decomposition.items()},"admission":admission,"motion_exposure":motion,"tile":tile,"decision":decision},indent=2)+"\n```\n",encoding="utf-8")
    print(json.dumps({"status":"complete","decision":decision}),flush=True); return 0


if __name__=="__main__": raise SystemExit(main())

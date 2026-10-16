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
from scipy import ndimage
import torch
from torch import nn
import torch.nn.functional as F


ROOT = Path(__file__).resolve().parents[1]
CONFIG = json.loads((ROOT / "config" / "experiment.json").read_text(encoding="utf-8"))
RESULTS = ROOT / "results"
WEIGHTS = ROOT / "weights"
REPORTS = ROOT / "reports"


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def seed_all(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)


def sigmoid_np(x: np.ndarray) -> np.ndarray:
    return 1.0 / (1.0 + np.exp(-np.clip(x, -40.0, 40.0)))


def _polygon_points(
    center: tuple[float, float],
    radius: float,
    count: int,
    phase: float,
    radial: np.ndarray | None = None,
) -> np.ndarray:
    angles = phase + np.arange(count, dtype=np.float32) * (2.0 * math.pi / count)
    radii = np.full(count, radius, dtype=np.float32) if radial is None else radial.astype(np.float32)
    x = center[0] + radii * np.cos(angles)
    y = center[1] + radii * np.sin(angles)
    return np.stack([x, y], axis=1).round().astype(np.int32)


def draw_shape(size: int, factor: int, family: str, rng: np.random.Generator) -> tuple[np.ndarray, np.ndarray]:
    high = size * factor
    mask = np.zeros((high, high), dtype=np.uint8)
    cx = float(rng.uniform(0.42, 0.58) * high)
    cy = float(rng.uniform(0.42, 0.58) * high)
    radius = float(rng.uniform(0.18, 0.30) * high)
    color = 255
    if family == "circle":
        cv2.circle(mask, (round(cx), round(cy)), round(radius), color, -1, lineType=cv2.LINE_AA)
    elif family == "ellipse":
        axes = (round(radius * rng.uniform(0.70, 1.25)), round(radius * rng.uniform(0.55, 0.95)))
        cv2.ellipse(mask, (round(cx), round(cy)), axes, float(rng.uniform(-40, 40)), 0, 360, color, -1, cv2.LINE_AA)
    elif family == "rectangle":
        width = radius * rng.uniform(1.3, 2.0)
        height = radius * rng.uniform(1.0, 1.7)
        rect = ((cx, cy), (width, height), float(rng.uniform(-40, 40)))
        cv2.fillConvexPoly(mask, cv2.boxPoints(rect).round().astype(np.int32), color, lineType=cv2.LINE_AA)
    elif family == "polygon":
        count = int(rng.integers(5, 9))
        radial = radius * rng.uniform(0.82, 1.12, size=count)
        cv2.fillPoly(mask, [_polygon_points((cx, cy), radius, count, float(rng.uniform(0, math.pi)), radial)], color, lineType=cv2.LINE_AA)
    elif family == "ring":
        outer = round(radius)
        inner = round(radius * rng.uniform(0.48, 0.70))
        cv2.circle(mask, (round(cx), round(cy)), outer, color, -1, cv2.LINE_AA)
        cv2.circle(mask, (round(cx), round(cy)), inner, 0, -1, cv2.LINE_AA)
    elif family == "crescent":
        cv2.circle(mask, (round(cx), round(cy)), round(radius), color, -1, cv2.LINE_AA)
        offset = radius * rng.uniform(0.30, 0.50)
        cv2.circle(mask, (round(cx + offset), round(cy - 0.08 * radius)), round(radius * 0.88), 0, -1, cv2.LINE_AA)
    elif family == "lobed":
        count = 96
        angles = np.arange(count, dtype=np.float32) * 2.0 * math.pi / count
        lobes = int(rng.integers(4, 8))
        phase = float(rng.uniform(-math.pi, math.pi))
        radial = radius * (1.0 + rng.uniform(0.12, 0.24) * np.sin(lobes * angles + phase))
        cv2.fillPoly(mask, [_polygon_points((cx, cy), radius, count, 0.0, radial)], color, lineType=cv2.LINE_AA)
    elif family == "thin_neck":
        left = (round(cx - 0.52 * radius), round(cy))
        right = (round(cx + 0.52 * radius), round(cy))
        r = round(radius * 0.62)
        cv2.circle(mask, left, r, color, -1, cv2.LINE_AA)
        cv2.circle(mask, right, r, color, -1, cv2.LINE_AA)
        neck = max(2, round(radius * rng.uniform(0.12, 0.24)))
        cv2.rectangle(mask, (left[0], round(cy - neck)), (right[0], round(cy + neck)), color, -1)
    else:
        raise ValueError(family)
    high_binary = mask >= 128
    high_sdf = (
        ndimage.distance_transform_edt(high_binary)
        - ndimage.distance_transform_edt(~high_binary)
    ).astype(np.float32)
    coverage = cv2.resize(
        mask.astype(np.float32) / 255.0,
        (size, size),
        interpolation=cv2.INTER_AREA,
    )
    return coverage, high_sdf


def motion_blur(image: np.ndarray, length: int, angle: float) -> np.ndarray:
    if length <= 1:
        return image
    kernel = np.zeros((length, length), dtype=np.float32)
    center = (length - 1) / 2.0
    dx = math.cos(angle) * center
    dy = math.sin(angle) * center
    cv2.line(
        kernel,
        (round(center - dx), round(center - dy)),
        (round(center + dx), round(center + dy)),
        1.0,
        1,
        cv2.LINE_AA,
    )
    kernel /= max(float(kernel.sum()), 1e-6)
    return cv2.filter2D(image, -1, kernel, borderType=cv2.BORDER_REFLECT_101)


def generate_sample(
    index: int,
    split: str,
    *,
    force_family: str | None = None,
    force_identity: bool | None = None,
) -> dict[str, np.ndarray | float | bool | str]:
    size = int(CONFIG["data"]["image_size"])
    factor = int(CONFIG["data"]["supersample"])
    split_salt = {"train": 100_000, "validation": 200_000, "test": 300_000}[split]
    rng = np.random.default_rng(int(CONFIG["training"]["seed"]) + split_salt + index * 7919)
    families = (
        CONFIG["data"]["train_shape_families"]
        if split != "test"
        else CONFIG["data"]["heldout_shape_families"]
    )
    family = force_family or str(families[index % len(families)])
    coverage, high_sdf = draw_shape(size, factor, family, rng)
    binary = coverage >= 0.5
    sdf = cv2.resize(
        high_sdf / float(factor),
        (size, size),
        interpolation=cv2.INTER_AREA,
    )
    width = float(rng.uniform(0.65, 1.75))
    polarity = 1.0 if rng.random() < 0.5 else -1.0
    outside = float(rng.uniform(0.10, 0.42))
    contrast = float(rng.uniform(0.28, 0.62))
    inside = float(np.clip(outside + polarity * contrast, 0.05, 0.95))
    if abs(inside - outside) < 0.20:
        inside = float(np.clip(outside + polarity * 0.30, 0.05, 0.95))
    exposure = float(CONFIG["data"]["exposure_levels"][index % len(CONFIG["data"]["exposure_levels"])])
    midpoint = 0.5 * (inside + outside)
    inside = float(np.clip(midpoint + exposure * (inside - midpoint), 0.03, 0.97))
    outside = float(np.clip(midpoint + exposure * (outside - midpoint), 0.03, 0.97))
    probability_high = sigmoid_np(high_sdf / (width * float(factor)))
    target_high = outside + (inside - outside) * probability_high
    target = cv2.resize(
        target_high.astype(np.float32),
        (size, size),
        interpolation=cv2.INTER_AREA,
    )
    identity = (
        bool(force_identity)
        if force_identity is not None
        else bool(rng.random() < float(CONFIG["data"]["identity_fraction"]))
    )
    if identity:
        source = target.copy()
    else:
        sigma = float(rng.uniform(0.9, 2.6))
        source = cv2.GaussianBlur(target, (0, 0), sigma, borderType=cv2.BORDER_REFLECT_101)
        if rng.random() < 0.45:
            source = motion_blur(source, int(rng.choice([3, 5, 7])), float(rng.uniform(0, math.pi)))
        if rng.random() < 0.40:
            ghost = np.roll(source, (int(rng.integers(-2, 3)), int(rng.integers(-2, 3))), axis=(0, 1))
            source = np.clip(0.94 * source + 0.06 * ghost, 0.0, 1.0)
        noise = float(rng.uniform(0.004, 0.020))
        source = np.clip(source + rng.normal(0.0, noise, source.shape).astype(np.float32), 0.0, 1.0)
    edge = np.exp(-np.abs(sdf) / 3.0).astype(np.float32)
    return {
        "source": source.astype(np.float32),
        "target": target.astype(np.float32),
        "sdf": sdf.astype(np.float32),
        "width": np.full_like(source, width, dtype=np.float32),
        "inside": np.full_like(source, inside, dtype=np.float32),
        "outside": np.full_like(source, outside, dtype=np.float32),
        "mask": binary.astype(np.float32),
        "edge": edge,
        "identity": identity,
        "family": family,
    }


@dataclass
class TensorPopulation:
    source: torch.Tensor
    target: torch.Tensor
    sdf: torch.Tensor
    width: torch.Tensor
    inside: torch.Tensor
    outside: torch.Tensor
    mask: torch.Tensor
    edge: torch.Tensor
    identity: torch.Tensor
    families: list[str]

    def batch(self, indices: np.ndarray, device: torch.device) -> dict[str, torch.Tensor]:
        idx = torch.as_tensor(indices, dtype=torch.long)
        return {
            "source": self.source[idx].to(device, non_blocking=True),
            "target": self.target[idx].to(device, non_blocking=True),
            "sdf": self.sdf[idx].to(device, non_blocking=True),
            "width": self.width[idx].to(device, non_blocking=True),
            "inside": self.inside[idx].to(device, non_blocking=True),
            "outside": self.outside[idx].to(device, non_blocking=True),
            "mask": self.mask[idx].to(device, non_blocking=True),
            "edge": self.edge[idx].to(device, non_blocking=True),
            "identity": self.identity[idx].to(device, non_blocking=True),
        }


def build_population(count: int, split: str) -> TensorPopulation:
    rows = [generate_sample(index, split) for index in range(count)]
    def stack(name: str) -> torch.Tensor:
        return torch.from_numpy(np.stack([row[name] for row in rows])[:, None])
    return TensorPopulation(
        source=stack("source"),
        target=stack("target"),
        sdf=stack("sdf"),
        width=stack("width"),
        inside=stack("inside"),
        outside=stack("outside"),
        mask=stack("mask"),
        edge=stack("edge"),
        identity=torch.tensor([bool(row["identity"]) for row in rows], dtype=torch.bool),
        families=[str(row["family"]) for row in rows],
    )


class ConvBlock(nn.Module):
    def __init__(self, c_in: int, c_out: int, *, stride: int = 1, dilation: int = 1):
        super().__init__()
        self.conv = nn.Conv2d(c_in, c_out, 3, stride=stride, padding=dilation, dilation=dilation)
        self.act = nn.SiLU()

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.act(self.conv(x))


class ResBlock(nn.Module):
    def __init__(self, channels: int, dilation: int = 1):
        super().__init__()
        self.a = ConvBlock(channels, channels, dilation=dilation)
        self.b = nn.Conv2d(channels, channels, 3, padding=dilation, dilation=dilation)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return F.silu(x + self.b(self.a(x)))


class ProbeModel(nn.Module):
    def __init__(self, output_mode: str):
        super().__init__()
        if output_mode not in {"residual", "renderer"}:
            raise ValueError(output_mode)
        base = int(CONFIG["model"]["base_channels"])
        self.output_mode = output_mode
        self.e1 = nn.Sequential(ConvBlock(1, base), ResBlock(base))
        self.down = ConvBlock(base, base * 2, stride=2)
        self.mid = nn.Sequential(ResBlock(base * 2, 1), ResBlock(base * 2, 2))
        self.up = ConvBlock(base * 2, base)
        self.fuse = nn.Sequential(ConvBlock(base * 2, base), ResBlock(base))
        self.residual_head = nn.Sequential(ConvBlock(base, base), nn.Conv2d(base, 1, 1))
        self.sdf_head = nn.Sequential(ConvBlock(base, base), nn.Conv2d(base, 1, 1))
        self.width_head = nn.Sequential(ConvBlock(base, base), nn.Conv2d(base, 1, 1))
        self.inside_head = nn.Sequential(ConvBlock(base, base), nn.Conv2d(base, 1, 1))
        self.outside_head = nn.Sequential(ConvBlock(base, base), nn.Conv2d(base, 1, 1))
        for head in [self.residual_head[-1], self.sdf_head[-1], self.width_head[-1], self.inside_head[-1], self.outside_head[-1]]:
            nn.init.zeros_(head.weight)
            nn.init.zeros_(head.bias)

    def forward(self, source: torch.Tensor) -> dict[str, torch.Tensor]:
        skip = self.e1(source)
        low = self.mid(self.down(skip))
        up = F.interpolate(low, size=source.shape[-2:], mode="bilinear", align_corners=False)
        features = self.fuse(torch.cat([self.up(up), skip], dim=1))
        residual = float(CONFIG["model"]["residual_bound"]) * torch.tanh(self.residual_head(features))
        sdf = float(CONFIG["model"]["sdf_bound_px"]) * torch.tanh(self.sdf_head(features))
        width = 0.45 + 2.55 * torch.sigmoid(self.width_head(features))
        inside = torch.sigmoid(self.inside_head(features))
        outside = torch.sigmoid(self.outside_head(features))
        profile = outside + (inside - outside) * torch.sigmoid(sdf / width.clamp_min(0.2))
        band = torch.exp(-sdf.abs() / float(CONFIG["model"]["renderer_band_px"]))
        rendered = source * (1.0 - band) + profile * band
        residual_output = (source + residual).clamp(0.0, 1.0)
        output = residual_output if self.output_mode == "residual" else rendered.clamp(0.0, 1.0)
        return {
            "output": output,
            "residual_output": residual_output,
            "renderer_output": rendered.clamp(0.0, 1.0),
            "sdf": sdf,
            "width": width,
            "inside": inside,
            "outside": outside,
        }


def gradients(x: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
    return x[..., 1:, :] - x[..., :-1, :], x[..., :, 1:] - x[..., :, :-1]


def losses(details: dict[str, torch.Tensor], batch: dict[str, torch.Tensor]) -> dict[str, torch.Tensor]:
    eps = 1e-3
    output_error = torch.sqrt((details["output"] - batch["target"]).square() + eps * eps).mean()
    oy, ox = gradients(details["output"])
    ty, tx = gradients(batch["target"])
    grad = (oy - ty).abs().mean() + (ox - tx).abs().mean()
    edge_weight = 0.15 + 0.85 * batch["edge"]
    sdf = F.smooth_l1_loss(
        details["sdf"] / float(CONFIG["model"]["sdf_bound_px"]),
        batch["sdf"].clamp(-24.0, 24.0) / float(CONFIG["model"]["sdf_bound_px"]),
        reduction="none",
        beta=0.04,
    )
    sdf = (sdf * edge_weight).sum() / edge_weight.sum().clamp_min(1.0)
    width = ((details["width"] - batch["width"]).abs() * batch["edge"]).sum() / batch["edge"].sum().clamp_min(1.0)
    inside_mask = (batch["mask"] > 0.95).float()
    outside_mask = (batch["mask"] < 0.05).float()
    inside = ((details["inside"] - batch["inside"]).abs() * inside_mask).sum() / inside_mask.sum().clamp_min(1.0)
    outside = ((details["outside"] - batch["outside"]).abs() * outside_mask).sum() / outside_mask.sum().clamp_min(1.0)
    if batch["identity"].any():
        identity = (details["output"][batch["identity"]] - batch["source"][batch["identity"]]).abs().mean()
    else:
        identity = output_error.new_zeros(())
    weights = CONFIG["loss_weights"]
    total = (
        float(weights["output_charbonnier"]) * output_error
        + float(weights["output_gradient"]) * grad
        + float(weights["sdf"]) * sdf
        + float(weights["width"]) * width
        + float(weights["inside_level"]) * inside
        + float(weights["outside_level"]) * outside
        + float(weights["identity"]) * identity
    )
    return {
        "total": total,
        "output": output_error,
        "gradient": grad,
        "sdf": sdf,
        "width": width,
        "inside": inside,
        "outside": outside,
        "identity": identity,
    }


def make_schedule(sample_count: int) -> np.ndarray:
    rng = np.random.default_rng(int(CONFIG["training"]["seed"]) + 55)
    return rng.integers(
        0,
        sample_count,
        size=(int(CONFIG["training"]["steps"]), int(CONFIG["training"]["batch_size"])),
        endpoint=False,
    )


def train_arm(
    mode: str,
    train: TensorPopulation,
    validation: TensorPopulation,
    schedule: np.ndarray,
    device: torch.device,
) -> tuple[ProbeModel, list[dict[str, float]]]:
    seed_all(int(CONFIG["training"]["seed"]))
    model = ProbeModel(mode).to(device)
    optimizer = torch.optim.AdamW(
        model.parameters(),
        lr=float(CONFIG["training"]["learning_rate"]),
        weight_decay=float(CONFIG["training"]["weight_decay"]),
    )
    history: list[dict[str, float]] = []
    started = time.perf_counter()
    for step, indices in enumerate(schedule, start=1):
        batch = train.batch(indices, device)
        optimizer.zero_grad(set_to_none=True)
        details = model(batch["source"])
        parts = losses(details, batch)
        parts["total"].backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), 5.0)
        optimizer.step()
        if step == 1 or step % int(CONFIG["training"]["log_every"]) == 0 or step == len(schedule):
            with torch.inference_mode():
                val_indices = np.arange(min(64, validation.source.shape[0]))
                val_batch = validation.batch(val_indices, device)
                val_parts = losses(model(val_batch["source"]), val_batch)
            row = {
                "step": step,
                "train_total": float(parts["total"].detach().cpu()),
                "train_output": float(parts["output"].detach().cpu()),
                "train_sdf": float(parts["sdf"].detach().cpu()),
                "validation_total": float(val_parts["total"].detach().cpu()),
                "validation_output": float(val_parts["output"].detach().cpu()),
                "validation_sdf": float(val_parts["sdf"].detach().cpu()),
                "seconds": time.perf_counter() - started,
            }
            history.append(row)
            print(json.dumps({"arm": mode, **row}), flush=True)
    torch.save(
        {
            "model": model.state_dict(),
            "mode": mode,
            "config": CONFIG,
            "seed": int(CONFIG["training"]["seed"]),
        },
        WEIGHTS / f"{mode}_step{len(schedule):04d}.pth",
    )
    return model, history


def compose_renderer(
    source: torch.Tensor,
    sdf: torch.Tensor,
    width: torch.Tensor,
    inside: torch.Tensor,
    outside: torch.Tensor,
) -> torch.Tensor:
    profile = outside + (inside - outside) * torch.sigmoid(sdf / width.clamp_min(0.2))
    band = torch.exp(-sdf.abs() / float(CONFIG["model"]["renderer_band_px"]))
    return (source * (1.0 - band) + profile * band).clamp(0.0, 1.0)


def binary_metrics(
    output: np.ndarray,
    mask: np.ndarray,
    sdf: np.ndarray,
    width_true: float,
    inside: float,
    outside: float,
) -> dict[str, float]:
    denom = inside - outside
    normalized = np.clip((output - outside) / (denom if abs(denom) > 1e-5 else 1.0), 0.0, 1.0)
    pred = normalized >= 0.5
    truth = mask >= 0.5
    intersection = int(np.logical_and(pred, truth).sum())
    union = int(np.logical_or(pred, truth).sum())
    iou = intersection / max(union, 1)
    def centroid(binary: np.ndarray) -> tuple[float, float]:
        ys, xs = np.nonzero(binary)
        if len(xs) == 0:
            return float("nan"), float("nan")
        return float(xs.mean()), float(ys.mean())
    px, py = centroid(pred)
    tx, ty = centroid(truth)
    centroid_error = math.hypot(px - tx, py - ty) if np.isfinite(px + tx) else 999.0
    pred_edge = np.logical_xor(pred, ndimage.binary_erosion(pred))
    truth_edge = np.logical_xor(truth, ndimage.binary_erosion(truth))
    if pred_edge.any() and truth_edge.any():
        d_truth = ndimage.distance_transform_edt(~truth_edge)
        d_pred = ndimage.distance_transform_edt(~pred_edge)
        boundary = 0.5 * (float(d_truth[pred_edge].mean()) + float(d_pred[truth_edge].mean()))
    else:
        boundary = 999.0
    valid = (np.abs(sdf) <= 6.0) & (normalized > 0.02) & (normalized < 0.98)
    if valid.sum() >= 64:
        x = sdf[valid].reshape(-1)
        y = np.log(normalized[valid] / np.clip(1.0 - normalized[valid], 1e-5, None)).reshape(-1)
        design = np.stack([x, np.ones_like(x)], axis=1)
        slope, intercept = np.linalg.lstsq(design, y, rcond=None)[0]
        center = float(-intercept / slope) if abs(slope) > 1e-5 else 99.0
        inferred_width = float(abs(1.0 / slope)) if abs(slope) > 1e-5 else 99.0
    else:
        center, inferred_width = 99.0, 99.0
    lower = min(inside, outside) - 0.02
    upper = max(inside, outside) + 0.02
    halo = float(np.mean((output < lower) | (output > upper)))
    return {
        "iou": float(iou),
        "boundary_distance_px": float(boundary),
        "centroid_error_px": float(centroid_error),
        "transition_center_error_px": float(abs(center)),
        "transition_width_error_px": float(abs(inferred_width - width_true)),
        "halo_overshoot_fraction": halo,
    }


@torch.inference_mode()
def predict_population(
    renderer: ProbeModel,
    residual: ProbeModel,
    population: TensorPopulation,
    device: torch.device,
) -> dict[str, np.ndarray]:
    count = population.source.shape[0]
    outputs: dict[str, list[np.ndarray]] = {
        "oracle_renderer": [],
        "learned_sdf_true_width_true_levels": [],
        "learned_sdf_learned_width_true_levels": [],
        "full_learned_renderer": [],
        "matched_residual": [],
    }
    batch_size = 16
    for start in range(0, count, batch_size):
        indices = np.arange(start, min(count, start + batch_size))
        batch = population.batch(indices, device)
        rd = renderer(batch["source"])
        bd = residual(batch["source"])
        outputs["oracle_renderer"].append(
            compose_renderer(batch["source"], batch["sdf"], batch["width"], batch["inside"], batch["outside"]).cpu().numpy()
        )
        outputs["learned_sdf_true_width_true_levels"].append(
            compose_renderer(batch["source"], rd["sdf"], batch["width"], batch["inside"], batch["outside"]).cpu().numpy()
        )
        outputs["learned_sdf_learned_width_true_levels"].append(
            compose_renderer(batch["source"], rd["sdf"], rd["width"], batch["inside"], batch["outside"]).cpu().numpy()
        )
        outputs["full_learned_renderer"].append(rd["output"].cpu().numpy())
        outputs["matched_residual"].append(bd["output"].cpu().numpy())
    return {name: np.concatenate(chunks, axis=0)[:, 0] for name, chunks in outputs.items()}


def summarize_outputs(outputs: dict[str, np.ndarray], population: TensorPopulation) -> dict[str, Any]:
    result: dict[str, Any] = {}
    source_np = population.source.numpy()[:, 0]
    target_np = population.target.numpy()[:, 0]
    mask_np = population.mask.numpy()[:, 0]
    sdf_np = population.sdf.numpy()[:, 0]
    width_np = population.width.numpy()[:, 0, 0, 0]
    inside_np = population.inside.numpy()[:, 0, 0, 0]
    outside_np = population.outside.numpy()[:, 0, 0, 0]
    identity_np = population.identity.numpy()
    for name, images in outputs.items():
        rows = [
            binary_metrics(images[i], mask_np[i], sdf_np[i], float(width_np[i]), float(inside_np[i]), float(outside_np[i]))
            for i in range(len(images))
        ]
        summary = {
            key: float(np.median([row[key] for row in rows]))
            for key in rows[0]
        }
        summary["mean_abs_error_gray"] = float(np.mean(np.abs(images - target_np)) * 255.0)
        summary["identity_mae_gray"] = (
            float(np.mean(np.abs(images[identity_np] - source_np[identity_np])) * 255.0)
            if identity_np.any()
            else 0.0
        )
        summary["images"] = int(len(images))
        result[name] = {"summary": summary, "per_image": rows}
    return result


def canonical_full(model: ProbeModel, image: torch.Tensor, halo: int = 32) -> torch.Tensor:
    padded = F.pad(image, (halo, halo, halo, halo), mode="reflect")
    return model(padded)["output"][..., halo:-halo, halo:-halo]


def canonical_tiled(model: ProbeModel, image: torch.Tensor, core: int = 64, halo: int = 32) -> torch.Tensor:
    _, _, height, width = image.shape
    grid_h = math.ceil(height / core) * core
    grid_w = math.ceil(width / core) * core
    canvas = F.pad(image, (halo, halo + grid_w - width, halo, halo + grid_h - height), mode="reflect")
    output = torch.empty((1, 1, grid_h, grid_w), device=image.device)
    for top in range(0, grid_h, core):
        for left in range(0, grid_w, core):
            tile = canvas[..., top : top + core + 2 * halo, left : left + core + 2 * halo]
            pred = model(tile)["output"][..., halo : halo + core, halo : halo + core]
            output[..., top : top + core, left : left + core] = pred
    return output[..., :height, :width]


@torch.inference_mode()
def tile_metrics(model: ProbeModel, population: TensorPopulation, device: torch.device) -> dict[str, float]:
    maxima, means = [], []
    for index in range(min(12, population.source.shape[0])):
        image = population.source[index : index + 1].to(device)
        full = canonical_full(model, image)
        tiled = canonical_tiled(model, image)
        delta = (full - tiled).abs() * 255.0
        maxima.append(float(delta.max().cpu()))
        means.append(float(delta.mean().cpu()))
    return {"max_abs_gray": max(maxima), "max_mean_abs_gray": max(means)}


def warp_np(image: np.ndarray, dx: float, dy: float, interpolation: int) -> np.ndarray:
    matrix = np.array([[1.0, 0.0, dx], [0.0, 1.0, dy]], dtype=np.float32)
    return cv2.warpAffine(
        image,
        matrix,
        (image.shape[1], image.shape[0]),
        flags=interpolation,
        borderMode=cv2.BORDER_REFLECT_101,
    )


def mask_centroid(output: np.ndarray, inside: float, outside: float) -> tuple[float, float]:
    normalized = (output - outside) / (inside - outside if abs(inside - outside) > 1e-5 else 1.0)
    binary = normalized >= 0.5
    ys, xs = np.nonzero(binary)
    return (float(xs.mean()), float(ys.mean())) if len(xs) else (float("nan"), float("nan"))


@torch.inference_mode()
def motion_and_exposure_metrics(
    models: dict[str, ProbeModel],
    device: torch.device,
) -> dict[str, Any]:
    motion_results: dict[str, list[float]] = {name: [] for name in models}
    exposure_centers: dict[str, list[float]] = {name: [] for name in models}
    shifts = [(0.5, -0.75), (-0.65, 0.4), (1.0, 0.5), (-0.4, -1.0)]
    for case in range(24):
        row = generate_sample(50_000 + case, "test", force_identity=False)
        source = row["source"]
        inside, outside = float(row["inside"][0, 0]), float(row["outside"][0, 0])
        dx, dy = shifts[case % len(shifts)]
        shifted = warp_np(source, dx, dy, cv2.INTER_LANCZOS4)
        pair = torch.from_numpy(np.stack([source, shifted])[:, None]).to(device)
        for name, model in models.items():
            pred = model(pair)["output"].cpu().numpy()[:, 0]
            c0 = mask_centroid(pred[0], inside, outside)
            c1 = mask_centroid(pred[1], inside, outside)
            measured = (c1[0] - c0[0], c1[1] - c0[1])
            motion_results[name].append(math.hypot(measured[0] - dx, measured[1] - dy))
    exposures = [0.70, 0.85, 1.00, 1.15, 1.30]
    for case in range(16):
        row = generate_sample(70_000 + case, "test", force_identity=False)
        base = row["source"]
        inside, outside = float(row["inside"][0, 0]), float(row["outside"][0, 0])
        midpoint = 0.5 * (inside + outside)
        for name, model in models.items():
            centers = []
            for exposure in exposures:
                image = np.clip(midpoint + exposure * (base - midpoint), 0.0, 1.0)
                pred = model(torch.from_numpy(image[None, None]).to(device))["output"][0, 0].cpu().numpy()
                in_e = float(np.clip(midpoint + exposure * (inside - midpoint), 0.0, 1.0))
                out_e = float(np.clip(midpoint + exposure * (outside - midpoint), 0.0, 1.0))
                centers.append(mask_centroid(pred, in_e, out_e))
            xs = np.array([value[0] for value in centers])
            ys = np.array([value[1] for value in centers])
            exposure_centers[name].append(float(np.sqrt(np.nanvar(xs) + np.nanvar(ys))))
    return {
        name: {
            "known_motion_error_px_median": float(np.median(motion_results[name])),
            "known_motion_error_px_p95": float(np.percentile(motion_results[name], 95)),
            "exposure_center_spread_px_median": float(np.median(exposure_centers[name])),
            "exposure_center_spread_px_p95": float(np.percentile(exposure_centers[name], 95)),
        }
        for name in models
    }


def decision(summary: dict[str, Any]) -> dict[str, Any]:
    renderer = summary["decomposition"]["full_learned_renderer"]["summary"]
    residual = summary["decomposition"]["matched_residual"]["summary"]
    directions = {
        "boundary_distance": renderer["boundary_distance_px"] < residual["boundary_distance_px"],
        "centroid_error": renderer["centroid_error_px"] < residual["centroid_error_px"],
        "transition_center": renderer["transition_center_error_px"] < residual["transition_center_error_px"],
        "transition_width": renderer["transition_width_error_px"] < residual["transition_width_error_px"],
        "halo": renderer["halo_overshoot_fraction"] <= residual["halo_overshoot_fraction"],
        "identity": renderer["identity_mae_gray"] <= residual["identity_mae_gray"],
    }
    core_wins = sum(int(directions[key]) for key in ["boundary_distance", "centroid_error", "transition_center", "transition_width", "halo"])
    eligible = core_wins >= 4 and directions["transition_center"] and directions["halo"]
    return {
        "directions": directions,
        "core_wins": core_wins,
        "full_r105_authorized": bool(eligible),
        "interpretation": (
            "Renderer shows a consistent geometry/width/halo advantage; a full R105 design is eligible for a separate review."
            if eligible
            else "Actionable renderer did not consistently dominate the matched residual arm; do not start a full R105."
        ),
    }


def render_report(summary: dict[str, Any]) -> str:
    rows = []
    for name, payload in summary["decomposition"].items():
        value = payload["summary"]
        rows.append(
            f"| {name} | {value['iou']:.5f} | {value['boundary_distance_px']:.4f} | "
            f"{value['centroid_error_px']:.4f} | {value['transition_center_error_px']:.4f} | "
            f"{value['transition_width_error_px']:.4f} | {value['halo_overshoot_fraction']:.5f} | "
            f"{value['identity_mae_gray']:.3f} |"
        )
    motion_rows = []
    for name, value in summary["motion_exposure"].items():
        motion_rows.append(
            f"| {name} | {value['known_motion_error_px_median']:.4f} | "
            f"{value['known_motion_error_px_p95']:.4f} | "
            f"{value['exposure_center_spread_px_median']:.4f} | "
            f"{summary['tile'][name]['max_abs_gray']:.6f} |"
        )
    return "\n".join(
        [
            "# R105A Geometry Renderer Falsification Results",
            "",
            f"Status: {summary['status']}",
            "",
            "## Matched held-out geometry results",
            "",
            "| Arm | IoU | Boundary distance px | Centroid error px | Transition-center error px | Width error px | Halo fraction | Identity MAE gray |",
            "|---|---:|---:|---:|---:|---:|---:|---:|",
            *rows,
            "",
            "## Motion, exposure and tile checks",
            "",
            "| Arm | Motion median px | Motion p95 px | Exposure center spread px | Full/tiled max gray |",
            "|---|---:|---:|---:|---:|",
            *motion_rows,
            "",
            "## Decision",
            "",
            summary["decision"]["interpretation"],
            "",
            f"Core directions won: {summary['decision']['core_wins']} / 5",
            "",
            "This is a procedural mechanism probe. It does not establish real SEM or external-GMF improvement.",
        ]
    )


def main() -> int:
    RESULTS.mkdir(parents=True, exist_ok=True)
    WEIGHTS.mkdir(parents=True, exist_ok=True)
    REPORTS.mkdir(parents=True, exist_ok=True)
    if not torch.cuda.is_available():
        raise RuntimeError("R105A requires CUDA for the matched probe")
    device = torch.device("cuda:0")
    seed_all(int(CONFIG["training"]["seed"]))
    print(json.dumps({"stage": "build_populations", "device": torch.cuda.get_device_name(0)}), flush=True)
    train = build_population(int(CONFIG["data"]["train_samples"]), "train")
    print(json.dumps({"stage": "train_population_ready", "samples": int(train.source.shape[0])}), flush=True)
    validation = build_population(int(CONFIG["data"]["validation_samples"]), "validation")
    print(json.dumps({"stage": "validation_population_ready", "samples": int(validation.source.shape[0])}), flush=True)
    test = build_population(int(CONFIG["data"]["test_samples"]), "test")
    print(json.dumps({"stage": "test_population_ready", "samples": int(test.source.shape[0])}), flush=True)
    schedule = make_schedule(train.source.shape[0])
    print(json.dumps({"stage": "schedule_ready", "steps": int(schedule.shape[0])}), flush=True)
    write_json(
        RESULTS / "population_manifest.json",
        {
            "train": int(train.source.shape[0]),
            "validation": int(validation.source.shape[0]),
            "test": int(test.source.shape[0]),
            "test_families": {name: test.families.count(name) for name in sorted(set(test.families))},
            "schedule_shape": list(schedule.shape),
            "seed": int(CONFIG["training"]["seed"]),
        },
    )
    residual, residual_history = train_arm("residual", train, validation, schedule, device)
    renderer, renderer_history = train_arm("renderer", train, validation, schedule, device)
    write_json(RESULTS / "training_history.json", {"residual": residual_history, "renderer": renderer_history})
    print(json.dumps({"stage": "decomposition_evaluation_started"}), flush=True)
    outputs = predict_population(renderer, residual, test, device)
    decomposition = summarize_outputs(outputs, test)
    print(json.dumps({"stage": "decomposition_evaluation_complete"}), flush=True)
    models = {"matched_residual": residual, "full_learned_renderer": renderer}
    print(json.dumps({"stage": "motion_exposure_evaluation_started"}), flush=True)
    motion_exposure = motion_and_exposure_metrics(models, device)
    print(json.dumps({"stage": "motion_exposure_evaluation_complete"}), flush=True)
    tile = {name: tile_metrics(model, test, device) for name, model in models.items()}
    print(json.dumps({"stage": "tile_evaluation_complete"}), flush=True)
    summary: dict[str, Any] = {
        "status": "complete",
        "experiment_id": CONFIG["experiment_id"],
        "device": torch.cuda.get_device_name(0),
        "parameter_count": sum(parameter.numel() for parameter in renderer.parameters()),
        "matched_parameter_counts_equal": (
            sum(parameter.numel() for parameter in renderer.parameters())
            == sum(parameter.numel() for parameter in residual.parameters())
        ),
        "decomposition": decomposition,
        "motion_exposure": motion_exposure,
        "tile": tile,
    }
    summary["decision"] = decision(summary)
    write_json(RESULTS / "summary.json", summary)
    (REPORTS / "R105A_RESULTS.md").write_text(render_report(summary), encoding="utf-8")
    print(json.dumps({"status": "complete", "decision": summary["decision"]}), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

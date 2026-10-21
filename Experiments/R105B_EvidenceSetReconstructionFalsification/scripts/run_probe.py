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


def polygon_points(
    center: tuple[float, float],
    radius: float,
    count: int,
    phase: float,
    radial: np.ndarray | None = None,
) -> np.ndarray:
    angles = phase + np.arange(count, dtype=np.float32) * (2.0 * math.pi / count)
    radii = np.full(count, radius, dtype=np.float32) if radial is None else radial.astype(np.float32)
    points = np.stack(
        [center[0] + radii * np.cos(angles), center[1] + radii * np.sin(angles)],
        axis=1,
    )
    return points.round().astype(np.int32)


def draw_high_mask(size: int, factor: int, family: str, rng: np.random.Generator) -> np.ndarray:
    high = size * factor
    mask = np.zeros((high, high), dtype=np.uint8)
    cx = float(rng.uniform(0.41, 0.59) * high)
    cy = float(rng.uniform(0.41, 0.59) * high)
    radius = float(rng.uniform(0.17, 0.29) * high)
    white = 255
    if family == "circle":
        cv2.circle(mask, (round(cx), round(cy)), round(radius), white, -1, cv2.LINE_AA)
    elif family == "ellipse":
        axes = (round(radius * rng.uniform(0.72, 1.28)), round(radius * rng.uniform(0.52, 0.94)))
        cv2.ellipse(mask, (round(cx), round(cy)), axes, float(rng.uniform(-45, 45)), 0, 360, white, -1, cv2.LINE_AA)
    elif family == "rectangle":
        rect = (
            (cx, cy),
            (radius * rng.uniform(1.25, 2.0), radius * rng.uniform(0.95, 1.65)),
            float(rng.uniform(-45, 45)),
        )
        cv2.fillConvexPoly(mask, cv2.boxPoints(rect).round().astype(np.int32), white, cv2.LINE_AA)
    elif family == "polygon":
        count = int(rng.integers(5, 10))
        radial = radius * rng.uniform(0.78, 1.16, count)
        cv2.fillPoly(mask, [polygon_points((cx, cy), radius, count, float(rng.uniform(0, math.pi)), radial)], white, cv2.LINE_AA)
    elif family == "ring":
        cv2.circle(mask, (round(cx), round(cy)), round(radius), white, -1, cv2.LINE_AA)
        cv2.circle(mask, (round(cx), round(cy)), round(radius * rng.uniform(0.45, 0.72)), 0, -1, cv2.LINE_AA)
    elif family == "crescent":
        cv2.circle(mask, (round(cx), round(cy)), round(radius), white, -1, cv2.LINE_AA)
        offset = radius * rng.uniform(0.28, 0.52)
        cv2.circle(
            mask,
            (round(cx + offset), round(cy + rng.uniform(-0.12, 0.12) * radius)),
            round(radius * rng.uniform(0.82, 0.92)),
            0,
            -1,
            cv2.LINE_AA,
        )
    elif family == "lobed":
        count = 128
        angles = np.arange(count, dtype=np.float32) * 2.0 * math.pi / count
        lobes = int(rng.integers(4, 9))
        radial = radius * (1.0 + rng.uniform(0.12, 0.25) * np.sin(lobes * angles + rng.uniform(-math.pi, math.pi)))
        cv2.fillPoly(mask, [polygon_points((cx, cy), radius, count, 0.0, radial)], white, cv2.LINE_AA)
    elif family == "thin_neck":
        left = (round(cx - 0.54 * radius), round(cy))
        right = (round(cx + 0.54 * radius), round(cy))
        disk = round(radius * rng.uniform(0.54, 0.68))
        cv2.circle(mask, left, disk, white, -1, cv2.LINE_AA)
        cv2.circle(mask, right, disk, white, -1, cv2.LINE_AA)
        neck = max(2, round(radius * rng.uniform(0.09, 0.22)))
        cv2.rectangle(mask, (left[0], round(cy - neck)), (right[0], round(cy + neck)), white, -1)
    else:
        raise ValueError(family)
    return mask


def warp_np(image: np.ndarray, dx: float, dy: float, interpolation: int = cv2.INTER_LANCZOS4) -> np.ndarray:
    matrix = np.array([[1.0, 0.0, dx], [0.0, 1.0, dy]], dtype=np.float32)
    return cv2.warpAffine(
        image,
        matrix,
        (image.shape[1], image.shape[0]),
        flags=interpolation,
        borderMode=cv2.BORDER_REFLECT_101,
    )


def generate_sample(index: int, split: str, force_identity: bool | None = None) -> dict[str, Any]:
    size = int(CONFIG["data"]["image_size"])
    factor = int(CONFIG["data"]["supersample"])
    count = int(CONFIG["data"]["observations"])
    split_salt = {"train": 100_000, "validation": 200_000, "test": 300_000}[split]
    rng = np.random.default_rng(int(CONFIG["training"]["seed"]) + split_salt + index * 7919)
    families = CONFIG["data"]["heldout_shape_families"] if split == "test" else CONFIG["data"]["train_shape_families"]
    family = str(families[index % len(families)])
    high_mask = draw_high_mask(size, factor, family, rng)
    high_binary = high_mask >= 128
    high_sdf = (
        ndimage.distance_transform_edt(high_binary) - ndimage.distance_transform_edt(~high_binary)
    ).astype(np.float32)
    width = float(rng.uniform(0.48, 1.18))
    polarity = 1.0 if rng.random() < 0.5 else -1.0
    outside = float(rng.uniform(0.12, 0.40))
    contrast = float(rng.uniform(0.32, 0.62))
    inside = float(np.clip(outside + polarity * contrast, 0.04, 0.96))
    if abs(inside - outside) < 0.24:
        inside = float(np.clip(outside + polarity * 0.34, 0.04, 0.96))
    target_high = outside + (inside - outside) * sigmoid_np(high_sdf / (width * factor))
    target = cv2.resize(target_high.astype(np.float32), (size, size), interpolation=cv2.INTER_AREA)
    sdf = cv2.resize(high_sdf / float(factor), (size, size), interpolation=cv2.INTER_AREA)
    coverage = cv2.resize(high_mask.astype(np.float32) / 255.0, (size, size), interpolation=cv2.INTER_AREA)
    mask = coverage >= 0.5
    edge = np.exp(-np.abs(sdf) / 2.5).astype(np.float32)
    identity = bool(force_identity) if force_identity is not None else bool(rng.random() < float(CONFIG["data"]["identity_fraction"]))

    sigmas = list(map(float, CONFIG["data"]["blur_sigmas_px"]))
    order = rng.permutation(len(sigmas))
    raw_frames, aligned_frames, illumination = [], [], []
    sigma_index, dx_values, dy_values, exposures = [], [], [], []
    yy, xx = np.mgrid[0 : size * factor, 0 : size * factor].astype(np.float32)
    xx = (xx / max(size * factor - 1, 1) - 0.5) * 2.0
    yy = (yy / max(size * factor - 1, 1) - 0.5) * 2.0
    for observation in range(count):
        if identity:
            sigma_id = -1
            dx = dy = 0.0
            exposure = 1.0
            illum_high = np.ones_like(target_high, dtype=np.float32)
            raw = target.copy()
        else:
            sigma_id = int(order[observation])
            sigma = sigmas[sigma_id]
            dx = 0.0 if observation == 0 else float(rng.uniform(-0.90, 0.90))
            dy = 0.0 if observation == 0 else float(rng.uniform(-0.90, 0.90))
            exposure = float(rng.uniform(0.76, 1.24))
            ax, ay = float(rng.uniform(-0.045, 0.045)), float(rng.uniform(-0.045, 0.045))
            illum_high = np.clip(1.0 + ax * xx + ay * yy, 0.90, 1.10).astype(np.float32)
            blurred = cv2.GaussianBlur(
                target_high.astype(np.float32),
                (0, 0),
                sigmaX=sigma * factor,
                sigmaY=sigma * factor,
                borderType=cv2.BORDER_REFLECT_101,
            )
            shifted = warp_np(blurred, dx * factor, dy * factor)
            observed_high = np.clip((0.5 + exposure * (shifted - 0.5)) * illum_high, 0.0, 1.0)
            raw = cv2.resize(observed_high, (size, size), interpolation=cv2.INTER_AREA)
            noise = float(rng.uniform(0.004, 0.018))
            raw = np.clip(raw + rng.normal(0.0, noise, raw.shape).astype(np.float32), 0.0, 1.0)
        illum_low = cv2.resize(illum_high, (size, size), interpolation=cv2.INTER_AREA)
        aligned = warp_np(raw, -dx, -dy)
        raw_frames.append(raw.astype(np.float32))
        aligned_frames.append(aligned.astype(np.float32))
        illumination.append(illum_low.astype(np.float32))
        sigma_index.append(sigma_id)
        dx_values.append(dx)
        dy_values.append(dy)
        exposures.append(exposure)
    return {
        "raw": np.stack(raw_frames),
        "aligned": np.stack(aligned_frames),
        "target": target.astype(np.float32),
        "sdf": sdf.astype(np.float32),
        "width": np.float32(width),
        "inside": np.float32(inside),
        "outside": np.float32(outside),
        "mask": mask.astype(np.float32),
        "edge": edge,
        "illumination": np.stack(illumination),
        "sigma_index": np.asarray(sigma_index, dtype=np.int64),
        "dx": np.asarray(dx_values, dtype=np.float32),
        "dy": np.asarray(dy_values, dtype=np.float32),
        "exposure": np.asarray(exposures, dtype=np.float32),
        "identity": identity,
        "family": family,
    }


@dataclass
class TensorPopulation:
    raw: torch.Tensor
    aligned: torch.Tensor
    target: torch.Tensor
    sdf: torch.Tensor
    width: torch.Tensor
    inside: torch.Tensor
    outside: torch.Tensor
    mask: torch.Tensor
    edge: torch.Tensor
    illumination: torch.Tensor
    sigma_index: torch.Tensor
    dx: torch.Tensor
    dy: torch.Tensor
    exposure: torch.Tensor
    identity: torch.Tensor
    families: list[str]

    def batch(self, indices: np.ndarray, device: torch.device) -> dict[str, torch.Tensor]:
        idx = torch.as_tensor(indices, dtype=torch.long)
        return {
            "raw": self.raw[idx].to(device, non_blocking=True),
            "aligned": self.aligned[idx].to(device, non_blocking=True),
            "target": self.target[idx].to(device, non_blocking=True),
            "sdf": self.sdf[idx].to(device, non_blocking=True),
            "width": self.width[idx].to(device, non_blocking=True),
            "inside": self.inside[idx].to(device, non_blocking=True),
            "outside": self.outside[idx].to(device, non_blocking=True),
            "mask": self.mask[idx].to(device, non_blocking=True),
            "edge": self.edge[idx].to(device, non_blocking=True),
            "illumination": self.illumination[idx].to(device, non_blocking=True),
            "sigma_index": self.sigma_index[idx].to(device, non_blocking=True),
            "dx": self.dx[idx].to(device, non_blocking=True),
            "dy": self.dy[idx].to(device, non_blocking=True),
            "exposure": self.exposure[idx].to(device, non_blocking=True),
            "identity": self.identity[idx].to(device, non_blocking=True),
        }


def build_population(count: int, split: str) -> TensorPopulation:
    rows = [generate_sample(index, split) for index in range(count)]
    def stack(name: str, add_channel: bool = False) -> torch.Tensor:
        array = np.stack([row[name] for row in rows])
        if add_channel:
            array = array[:, None]
        return torch.from_numpy(array)
    return TensorPopulation(
        raw=stack("raw"),
        aligned=stack("aligned"),
        target=stack("target", True),
        sdf=stack("sdf", True),
        width=torch.tensor([row["width"] for row in rows], dtype=torch.float32),
        inside=torch.tensor([row["inside"] for row in rows], dtype=torch.float32),
        outside=torch.tensor([row["outside"] for row in rows], dtype=torch.float32),
        mask=stack("mask", True),
        edge=stack("edge", True),
        illumination=stack("illumination"),
        sigma_index=stack("sigma_index"),
        dx=stack("dx"),
        dy=stack("dy"),
        exposure=stack("exposure"),
        identity=torch.tensor([row["identity"] for row in rows], dtype=torch.bool),
        families=[str(row["family"]) for row in rows],
    )


class ConvBlock(nn.Module):
    def __init__(self, c_in: int, c_out: int, stride: int = 1, dilation: int = 1):
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


class EvidenceSetNet(nn.Module):
    def __init__(self):
        super().__init__()
        base = int(CONFIG["model"]["base_channels"])
        candidates = int(CONFIG["model"]["candidates"])
        self.e1 = nn.Sequential(ConvBlock(1, base), ResBlock(base))
        self.down = ConvBlock(base, base * 2, stride=2)
        self.mid = nn.Sequential(ResBlock(base * 2, 1), ResBlock(base * 2, 2))
        self.up = ConvBlock(base * 2, base)
        self.frame_fuse = nn.Sequential(ConvBlock(base * 2, base), ResBlock(base))
        self.evidence_fuse = nn.Sequential(ConvBlock(base * 2 + 1, base), ResBlock(base), ResBlock(base, 2))
        self.candidate_head = nn.Sequential(ConvBlock(base, base), nn.Conv2d(base, candidates, 1))
        nn.init.zeros_(self.candidate_head[-1].weight)
        bias = torch.linspace(-0.08, 0.08, candidates)
        with torch.no_grad():
            self.candidate_head[-1].bias.copy_(bias)

    def encode_frame(self, frame: torch.Tensor) -> torch.Tensor:
        skip = self.e1(frame)
        low = self.mid(self.down(skip))
        up = F.interpolate(low, size=frame.shape[-2:], mode="bilinear", align_corners=False)
        return self.frame_fuse(torch.cat([self.up(up), skip], dim=1))

    def forward(self, frames: torch.Tensor, valid: torch.Tensor) -> dict[str, torch.Tensor]:
        batch, observations, height, width = frames.shape
        features = self.encode_frame(frames.reshape(batch * observations, 1, height, width))
        channels = features.shape[1]
        features = features.reshape(batch, observations, channels, height, width)
        weights = valid[:, :, None, None, None]
        count = weights.sum(dim=1).clamp_min(1.0)
        mean = (features * weights).sum(dim=1) / count
        variance = ((features - mean[:, None]).square() * weights).sum(dim=1) / count
        count_map = (count[:, :1] / float(observations)).expand(-1, 1, height, width)
        fused = self.evidence_fuse(torch.cat([mean, torch.sqrt(variance + 1e-8), count_map], dim=1))
        residual = float(CONFIG["model"]["residual_bound"]) * torch.tanh(self.candidate_head(fused))
        anchor = (frames * valid[:, :, None, None]).sum(dim=1, keepdim=True) / valid.sum(dim=1)[:, None, None, None].clamp_min(1.0)
        candidates = (anchor[:, None] + residual[:, :, None]).clamp(0.0, 1.0)
        return {"candidates": candidates, "anchor": anchor}


_KERNEL_CACHE: dict[tuple[float, str, torch.dtype], torch.Tensor] = {}


def gaussian_kernel(sigma: float, device: torch.device, dtype: torch.dtype) -> torch.Tensor:
    key = (sigma, str(device), dtype)
    if key in _KERNEL_CACHE:
        return _KERNEL_CACHE[key]
    radius = max(1, int(math.ceil(3.0 * sigma)))
    coordinates = torch.arange(-radius, radius + 1, device=device, dtype=dtype)
    kernel_1d = torch.exp(-0.5 * (coordinates / sigma).square())
    kernel_1d /= kernel_1d.sum()
    kernel = torch.outer(kernel_1d, kernel_1d)[None, None]
    _KERNEL_CACHE[key] = kernel
    return kernel


def blur_candidates(candidates: torch.Tensor, sigma_index: torch.Tensor) -> torch.Tensor:
    batch, count, channels, height, width = candidates.shape
    output = torch.empty_like(candidates)
    sigmas = list(map(float, CONFIG["data"]["blur_sigmas_px"]))
    for index in torch.unique(sigma_index).tolist():
        selected = sigma_index == int(index)
        values = candidates[selected]
        if int(index) < 0:
            output[selected] = values
            continue
        flat = values.reshape(-1, channels, height, width)
        kernel = gaussian_kernel(sigmas[int(index)], candidates.device, candidates.dtype)
        radius = kernel.shape[-1] // 2
        flat = F.pad(flat, (radius, radius, radius, radius), mode="reflect")
        output[selected] = F.conv2d(flat, kernel).reshape(values.shape)
    return output


def warp_candidates(candidates: torch.Tensor, dx: torch.Tensor, dy: torch.Tensor) -> torch.Tensor:
    batch, count, channels, height, width = candidates.shape
    flat = candidates.reshape(batch * count, channels, height, width)
    dx_flat = dx[:, None].expand(batch, count).reshape(-1)
    dy_flat = dy[:, None].expand(batch, count).reshape(-1)
    theta = torch.zeros((batch * count, 2, 3), device=candidates.device, dtype=candidates.dtype)
    theta[:, 0, 0] = 1.0
    theta[:, 1, 1] = 1.0
    theta[:, 0, 2] = -2.0 * dx_flat / max(width - 1, 1)
    theta[:, 1, 2] = -2.0 * dy_flat / max(height - 1, 1)
    grid = F.affine_grid(theta, flat.shape, align_corners=True)
    warped = F.grid_sample(flat, grid, mode="bilinear", padding_mode="reflection", align_corners=True)
    return warped.reshape(batch, count, channels, height, width)


def physics_evidence(
    candidates: torch.Tensor,
    batch: dict[str, torch.Tensor],
    valid: torch.Tensor,
) -> dict[str, torch.Tensor]:
    batch_size, candidate_count, _, height, width = candidates.shape
    error_sum = candidates.new_zeros((batch_size, candidate_count, height, width))
    valid_count = valid.sum(dim=1).clamp_min(1.0)
    for observation in range(batch["raw"].shape[1]):
        active = valid[:, observation]
        blurred = blur_candidates(candidates, batch["sigma_index"][:, observation])
        shifted = warp_candidates(blurred, batch["dx"][:, observation], batch["dy"][:, observation])
        exposure = batch["exposure"][:, observation, None, None, None, None]
        illumination = batch["illumination"][:, observation, None]
        rendered = ((0.5 + exposure * (shifted - 0.5)) * illumination[:, None]).clamp(0.0, 1.0)
        raw = batch["raw"][:, observation, None, None]
        error_sum = error_sum + (rendered - raw).abs()[:, :, 0] * active[:, None, None, None]
    error = error_sum / valid_count[:, None, None, None]
    window = int(CONFIG["model"]["local_evidence_window"])
    local = F.avg_pool2d(
        error.reshape(batch_size * candidate_count, 1, height, width),
        kernel_size=window,
        stride=1,
        padding=window // 2,
    ).reshape(batch_size, candidate_count, height, width)
    temperature = float(CONFIG["model"]["physics_temperature"])
    weights = torch.softmax(-local / temperature, dim=1)
    output = (weights[:, :, None] * candidates).sum(dim=1)
    variance = (weights[:, :, None] * (candidates - output[:, None]).square()).sum(dim=1)
    uncertainty = torch.sqrt(variance + 1e-8)
    return {"output": output, "uncertainty": uncertainty, "weights": weights, "physics_error": local}


def gradients(x: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
    return x[..., 1:, :] - x[..., :-1, :], x[..., :, 1:] - x[..., :, :-1]


def make_valid(batch_size: int, observations: int, used: int, device: torch.device) -> torch.Tensor:
    valid = torch.zeros((batch_size, observations), device=device)
    valid[:, :used] = 1.0
    return valid


def loss_parts(
    model: EvidenceSetNet,
    batch: dict[str, torch.Tensor],
    valid: torch.Tensor,
    mode: str,
) -> dict[str, torch.Tensor]:
    details = model(batch["aligned"], valid)
    evidence = physics_evidence(details["candidates"], batch, valid)
    candidates = details["candidates"]
    output = evidence["output"]
    target = batch["target"]
    epsilon = 1e-3
    candidate_errors = torch.sqrt((candidates - target[:, None]).square() + epsilon * epsilon).mean(dim=(2, 3, 4))
    coverage = candidate_errors.min(dim=1).values.mean()
    all_candidates = candidate_errors.mean()
    output_error = torch.sqrt((output - target).square() + epsilon * epsilon).mean()
    oy, ox = gradients(output)
    ty, tx = gradients(target)
    gradient = (oy - ty).abs().mean() + (ox - tx).abs().mean()
    physics = (evidence["weights"] * evidence["physics_error"]).sum(dim=1).mean()
    calibration_target = (output - target).abs().detach()
    calibration = (evidence["uncertainty"] - calibration_target).abs().mean()
    spread = candidates.std(dim=1, unbiased=False).mean()
    if batch["identity"].any():
        identity = (output[batch["identity"]] - target[batch["identity"]]).abs().mean()
    else:
        identity = output_error.new_zeros(())
    if mode == "point":
        total = (
            1.00 * output_error
            + 0.45 * all_candidates
            + 0.22 * gradient
            + 0.12 * physics
            + 0.20 * spread
            + 0.22 * identity
        )
    elif mode == "evidence":
        diversity_credit = torch.clamp(spread, max=0.025)
        total = (
            0.80 * output_error
            + 0.72 * coverage
            + 0.06 * all_candidates
            + 0.22 * gradient
            + 0.16 * physics
            + 0.12 * calibration
            + 0.22 * identity
            - 0.05 * diversity_credit
        )
    else:
        raise ValueError(mode)
    return {
        "total": total,
        "output": output_error,
        "coverage": coverage,
        "all_candidates": all_candidates,
        "gradient": gradient,
        "physics": physics,
        "calibration": calibration,
        "spread": spread,
        "identity": identity,
    }


def make_schedule(sample_count: int) -> tuple[np.ndarray, np.ndarray]:
    rng = np.random.default_rng(int(CONFIG["training"]["seed"]) + 55)
    steps = int(CONFIG["training"]["steps"])
    batches = rng.integers(
        0,
        sample_count,
        size=(steps, int(CONFIG["training"]["batch_size"])),
        endpoint=False,
    )
    observation_choices = rng.choice(
        np.asarray(CONFIG["training"]["evidence_observation_schedule"], dtype=np.int64),
        size=steps,
        p=np.asarray([0.34, 0.26, 0.40]),
    )
    return batches, observation_choices


def train_arm(
    mode: str,
    train: TensorPopulation,
    validation: TensorPopulation,
    schedule: np.ndarray,
    observation_schedule: np.ndarray,
    device: torch.device,
) -> tuple[EvidenceSetNet, list[dict[str, float]]]:
    seed_all(int(CONFIG["training"]["seed"]))
    model = EvidenceSetNet().to(device)
    optimizer = torch.optim.AdamW(
        model.parameters(),
        lr=float(CONFIG["training"]["learning_rate"]),
        weight_decay=float(CONFIG["training"]["weight_decay"]),
    )
    history = []
    started = time.perf_counter()
    log_every = int(CONFIG["training"]["log_every"])
    for step, indices in enumerate(schedule, start=1):
        batch = train.batch(indices, device)
        used = 1 if mode == "point" else int(observation_schedule[step - 1])
        valid = make_valid(len(indices), batch["aligned"].shape[1], used, device)
        optimizer.zero_grad(set_to_none=True)
        parts = loss_parts(model, batch, valid, mode)
        parts["total"].backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), 5.0)
        optimizer.step()
        if step == 1 or step % log_every == 0 or step == len(schedule):
            with torch.inference_mode():
                val_indices = np.arange(min(36, validation.target.shape[0]))
                val_batch = validation.batch(val_indices, device)
                val_valid_1 = make_valid(len(val_indices), val_batch["aligned"].shape[1], 1, device)
                val_1 = loss_parts(model, val_batch, val_valid_1, mode)
                val_valid_4 = make_valid(len(val_indices), val_batch["aligned"].shape[1], 4, device)
                val_4 = loss_parts(model, val_batch, val_valid_4, mode)
            row = {
                "step": step,
                "observations_used": used,
                "train_total": float(parts["total"].detach().cpu()),
                "train_output": float(parts["output"].detach().cpu()),
                "train_spread": float(parts["spread"].detach().cpu()),
                "validation_n1_total": float(val_1["total"].detach().cpu()),
                "validation_n1_output": float(val_1["output"].detach().cpu()),
                "validation_n4_total": float(val_4["total"].detach().cpu()),
                "validation_n4_output": float(val_4["output"].detach().cpu()),
                "seconds": time.perf_counter() - started,
            }
            history.append(row)
            print(json.dumps({"arm": mode, **row}), flush=True)
    WEIGHTS.mkdir(parents=True, exist_ok=True)
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


@torch.inference_mode()
def infer_batch(
    model: EvidenceSetNet,
    batch: dict[str, torch.Tensor],
    used: int,
) -> dict[str, torch.Tensor]:
    valid = make_valid(batch["aligned"].shape[0], batch["aligned"].shape[1], used, batch["aligned"].device)
    details = model(batch["aligned"], valid)
    evidence = physics_evidence(details["candidates"], batch, valid)
    global_physics = evidence["physics_error"].mean(dim=(2, 3))
    physics_index = global_physics.argmin(dim=1)
    target_error = (details["candidates"] - batch["target"][:, None]).abs().mean(dim=(2, 3, 4))
    oracle_index = target_error.argmin(dim=1)
    rows = torch.arange(batch["aligned"].shape[0], device=batch["aligned"].device)
    physics_candidate = details["candidates"][rows, physics_index]
    oracle_candidate = details["candidates"][rows, oracle_index]
    return {
        "output": evidence["output"],
        "uncertainty": evidence["uncertainty"],
        "physics_candidate": physics_candidate,
        "oracle_candidate": oracle_candidate,
        "candidates": details["candidates"],
    }


@torch.inference_mode()
def predict_population(
    model: EvidenceSetNet,
    population: TensorPopulation,
    used: int,
    device: torch.device,
) -> dict[str, np.ndarray]:
    chunks: dict[str, list[np.ndarray]] = {name: [] for name in ["output", "uncertainty", "physics_candidate", "oracle_candidate"]}
    batch_size = int(CONFIG["training"]["batch_size"])
    for start in range(0, population.target.shape[0], batch_size):
        indices = np.arange(start, min(population.target.shape[0], start + batch_size))
        batch = population.batch(indices, device)
        details = infer_batch(model, batch, used)
        for name in chunks:
            chunks[name].append(details[name].cpu().numpy()[:, 0])
    return {name: np.concatenate(values, axis=0) for name, values in chunks.items()}


def binary_metrics(
    output: np.ndarray,
    mask: np.ndarray,
    sdf: np.ndarray,
    width_true: float,
    inside: float,
    outside: float,
) -> dict[str, float]:
    denominator = inside - outside
    normalized = np.clip((output - outside) / (denominator if abs(denominator) > 1e-5 else 1.0), 0.0, 1.0)
    prediction = normalized >= 0.5
    truth = mask >= 0.5
    intersection = int(np.logical_and(prediction, truth).sum())
    union = int(np.logical_or(prediction, truth).sum())
    iou = intersection / max(union, 1)
    def centroid(binary: np.ndarray) -> tuple[float, float]:
        ys, xs = np.nonzero(binary)
        return (float(xs.mean()), float(ys.mean())) if len(xs) else (float("nan"), float("nan"))
    px, py = centroid(prediction)
    tx, ty = centroid(truth)
    centroid_error = math.hypot(px - tx, py - ty) if np.isfinite(px + tx) else 999.0
    pred_edge = np.logical_xor(prediction, ndimage.binary_erosion(prediction))
    true_edge = np.logical_xor(truth, ndimage.binary_erosion(truth))
    if pred_edge.any() and true_edge.any():
        d_truth = ndimage.distance_transform_edt(~true_edge)
        d_pred = ndimage.distance_transform_edt(~pred_edge)
        boundary = 0.5 * (float(d_truth[pred_edge].mean()) + float(d_pred[true_edge].mean()))
    else:
        boundary = 999.0
    valid = (np.abs(sdf) <= 5.0) & (normalized > 0.02) & (normalized < 0.98)
    if valid.sum() >= 48:
        x = sdf[valid].reshape(-1)
        y = np.log(normalized[valid] / np.clip(1.0 - normalized[valid], 1e-5, None)).reshape(-1)
        design = np.stack([x, np.ones_like(x)], axis=1)
        slope, intercept = np.linalg.lstsq(design, y, rcond=None)[0]
        center = float(-intercept / slope) if abs(slope) > 1e-5 else 99.0
        inferred_width = float(abs(1.0 / slope)) if abs(slope) > 1e-5 else 99.0
    else:
        center = inferred_width = 99.0
    lower, upper = min(inside, outside) - 0.02, max(inside, outside) + 0.02
    halo = float(np.mean((output < lower) | (output > upper)))
    return {
        "iou": float(iou),
        "boundary_distance_px": float(boundary),
        "centroid_error_px": float(centroid_error),
        "transition_center_error_px": float(abs(center)),
        "transition_width_error_px": float(abs(inferred_width - width_true)),
        "halo_overshoot_fraction": halo,
    }


def summarize_outputs(outputs: dict[str, np.ndarray], population: TensorPopulation) -> dict[str, Any]:
    target = population.target.numpy()[:, 0]
    mask = population.mask.numpy()[:, 0]
    sdf = population.sdf.numpy()[:, 0]
    width = population.width.numpy()
    inside = population.inside.numpy()
    outside = population.outside.numpy()
    identity = population.identity.numpy()
    aligned_first = population.aligned.numpy()[:, 0]
    result = {}
    for name, images in outputs.items():
        rows = [
            binary_metrics(images[index], mask[index], sdf[index], float(width[index]), float(inside[index]), float(outside[index]))
            for index in range(len(images))
        ]
        summary = {key: float(np.median([row[key] for row in rows])) for key in rows[0]}
        summary["mean_abs_error_gray"] = float(np.mean(np.abs(images - target)) * 255.0)
        summary["identity_mae_gray"] = float(np.mean(np.abs(images[identity] - aligned_first[identity])) * 255.0) if identity.any() else 0.0
        summary["images"] = len(images)
        result[name] = {"summary": summary, "per_image": rows}
    return result


def uncertainty_analysis(
    output: np.ndarray,
    uncertainty: np.ndarray,
    metrics: list[dict[str, float]],
    population: TensorPopulation,
) -> dict[str, float]:
    target = population.target.numpy()[:, 0]
    predicted = uncertainty.mean(axis=(1, 2))
    actual_mae = np.abs(output - target).mean(axis=(1, 2))
    boundary = np.asarray([row["boundary_distance_px"] for row in metrics])
    mae_correlation = spearmanr(predicted, actual_mae).statistic
    boundary_correlation = spearmanr(predicted, boundary).statistic
    return {
        "median_uncertainty_gray": float(np.median(predicted) * 255.0),
        "p95_uncertainty_gray": float(np.percentile(predicted, 95) * 255.0),
        "spearman_uncertainty_vs_image_mae": float(mae_correlation if np.isfinite(mae_correlation) else 0.0),
        "spearman_uncertainty_vs_boundary_distance": float(boundary_correlation if np.isfinite(boundary_correlation) else 0.0),
    }


def centroid_from_output(output: np.ndarray, inside: float, outside: float) -> tuple[float, float]:
    normalized = (output - outside) / (inside - outside if abs(inside - outside) > 1e-5 else 1.0)
    binary = normalized >= 0.5
    ys, xs = np.nonzero(binary)
    return (float(xs.mean()), float(ys.mean())) if len(xs) else (float("nan"), float("nan"))


def transform_batch_spatial(batch: dict[str, torch.Tensor], dx: float, dy: float, exposure_scale: float = 1.0) -> dict[str, torch.Tensor]:
    result = {key: value.clone() for key, value in batch.items()}
    for name in ["raw", "aligned", "illumination"]:
        array = result[name].cpu().numpy()
        for b in range(array.shape[0]):
            for n in range(array.shape[1]):
                if name != "illumination":
                    array[b, n] = np.clip(0.5 + exposure_scale * (array[b, n] - 0.5), 0.0, 1.0)
                array[b, n] = warp_np(array[b, n], dx, dy)
        result[name] = torch.from_numpy(array).to(batch[name].device)
    result["exposure"] = result["exposure"] * exposure_scale
    return result


@torch.inference_mode()
def motion_exposure_metrics(models: dict[str, tuple[EvidenceSetNet, int]], population: TensorPopulation, device: torch.device) -> dict[str, Any]:
    motion_errors = {name: [] for name in models}
    exposure_spreads = {name: [] for name in models}
    shifts = [(0.50, -0.75), (-0.65, 0.40), (0.90, 0.55), (-0.40, -0.90)]
    for index in range(min(24, population.target.shape[0])):
        batch = population.batch(np.asarray([index]), device)
        dx, dy = shifts[index % len(shifts)]
        shifted = transform_batch_spatial(batch, dx, dy)
        inside = float(population.inside[index])
        outside = float(population.outside[index])
        for name, (model, used) in models.items():
            first = infer_batch(model, batch, used)["output"][0, 0].cpu().numpy()
            second = infer_batch(model, shifted, used)["output"][0, 0].cpu().numpy()
            c0, c1 = centroid_from_output(first, inside, outside), centroid_from_output(second, inside, outside)
            measured = (c1[0] - c0[0], c1[1] - c0[1])
            motion_errors[name].append(math.hypot(measured[0] - dx, measured[1] - dy))
    exposure_levels = [0.78, 0.90, 1.00, 1.12, 1.24]
    for index in range(min(16, population.target.shape[0])):
        batch = population.batch(np.asarray([index]), device)
        inside = float(population.inside[index])
        outside = float(population.outside[index])
        for name, (model, used) in models.items():
            centers = []
            for scale in exposure_levels:
                changed = transform_batch_spatial(batch, 0.0, 0.0, scale)
                output = infer_batch(model, changed, used)["output"][0, 0].cpu().numpy()
                inside_scaled = float(np.clip(0.5 + scale * (inside - 0.5), 0.0, 1.0))
                outside_scaled = float(np.clip(0.5 + scale * (outside - 0.5), 0.0, 1.0))
                centers.append(centroid_from_output(output, inside_scaled, outside_scaled))
            xs, ys = np.asarray([c[0] for c in centers]), np.asarray([c[1] for c in centers])
            exposure_spreads[name].append(float(np.sqrt(np.nanvar(xs) + np.nanvar(ys))))
    return {
        name: {
            "known_motion_error_px_median": float(np.median(motion_errors[name])),
            "known_motion_error_px_p95": float(np.percentile(motion_errors[name], 95)),
            "exposure_center_spread_px_median": float(np.median(exposure_spreads[name])),
            "exposure_center_spread_px_p95": float(np.percentile(exposure_spreads[name], 95)),
        }
        for name in models
    }


def pad_spatial_batch(batch: dict[str, torch.Tensor], left: int, right: int, top: int, bottom: int) -> dict[str, torch.Tensor]:
    result = {}
    spatial_names = {"raw", "aligned", "target", "sdf", "mask", "edge", "illumination"}
    for name, value in batch.items():
        if name in spatial_names:
            if value.ndim == 4:
                result[name] = F.pad(value, (left, right, top, bottom), mode="reflect")
            else:
                result[name] = value
        else:
            result[name] = value
    return result


def crop_spatial_batch(batch: dict[str, torch.Tensor], top: int, left: int, height: int, width: int) -> dict[str, torch.Tensor]:
    result = {}
    spatial_names = {"raw", "aligned", "target", "sdf", "mask", "edge", "illumination"}
    for name, value in batch.items():
        result[name] = value[..., top : top + height, left : left + width] if name in spatial_names else value
    return result


@torch.inference_mode()
def tile_metrics(model: EvidenceSetNet, population: TensorPopulation, used: int, device: torch.device) -> dict[str, float]:
    core, halo = 48, 32
    maxima, means = [], []
    for index in range(min(8, population.target.shape[0])):
        batch = population.batch(np.asarray([index]), device)
        height, width = batch["target"].shape[-2:]
        full_batch = pad_spatial_batch(batch, halo, halo, halo, halo)
        full = infer_batch(model, full_batch, used)["output"][..., halo:-halo, halo:-halo]
        grid_h, grid_w = math.ceil(height / core) * core, math.ceil(width / core) * core
        canvas = pad_spatial_batch(batch, halo, halo + grid_w - width, halo, halo + grid_h - height)
        tiled = torch.empty((1, 1, grid_h, grid_w), device=device)
        for top in range(0, grid_h, core):
            for left in range(0, grid_w, core):
                tile = crop_spatial_batch(canvas, top, left, core + 2 * halo, core + 2 * halo)
                prediction = infer_batch(model, tile, used)["output"]
                tiled[..., top : top + core, left : left + core] = prediction[..., halo : halo + core, halo : halo + core]
        delta = (full - tiled[..., :height, :width]).abs() * 255.0
        maxima.append(float(delta.max().cpu()))
        means.append(float(delta.mean().cpu()))
    return {"max_abs_gray": max(maxima), "max_mean_abs_gray": max(means)}


def render_visual_qa(
    population: TensorPopulation,
    outputs: dict[str, np.ndarray],
    uncertainties: dict[str, np.ndarray],
    summary: dict[str, Any],
) -> None:
    target = population.target.numpy()[:, 0]
    source = population.aligned.numpy()[:, 0]
    point_rows = summary["decomposition"]["matched_point_single"]["per_image"]
    multi_rows = summary["decomposition"]["evidence_set_four"]["per_image"]
    selected = []
    for family in sorted(set(population.families)):
        indices = [i for i, value in enumerate(population.families) if value == family]
        delta = np.asarray([multi_rows[i]["boundary_distance_px"] - point_rows[i]["boundary_distance_px"] for i in indices])
        order = np.argsort(delta)
        selected.extend([(indices[int(order[0])], "best"), (indices[int(order[len(order) // 2])], "median"), (indices[int(order[-1])], "worst")])
    columns = ["Single obs", "Target", "Point N=1", "Evidence N=1", "Evidence N=4", "N=4 error x8", "N=4 uncertainty x8"]
    panel, gap, label_h, row_h = 160, 10, 32, 194
    canvas = Image.new("RGB", (gap + len(columns) * (panel + gap), label_h + len(selected) * row_h + gap), "white")
    draw = ImageDraw.Draw(canvas)
    font = ImageFont.load_default()
    for column, label in enumerate(columns):
        draw.text((gap + column * (panel + gap), 10), label, fill="black", font=font)
    def panel_image(array: np.ndarray, heat: bool = False) -> Image.Image:
        value = np.clip(array, 0.0, 1.0)
        rgb = np.stack([value, value * 0.18, np.zeros_like(value)], axis=-1) if heat else np.repeat(value[..., None], 3, axis=-1)
        return Image.fromarray(np.round(rgb * 255).astype(np.uint8), "RGB").resize((panel, panel), Image.Resampling.BICUBIC)
    for row, (index, kind) in enumerate(selected):
        top = label_h + row * row_h
        values = [
            (source[index], False),
            (target[index], False),
            (outputs["matched_point_single"][index], False),
            (outputs["evidence_set_single"][index], False),
            (outputs["evidence_set_four"][index], False),
            (np.abs(outputs["evidence_set_four"][index] - target[index]) * 8.0, True),
            (uncertainties["evidence_set_four"][index] * 8.0, True),
        ]
        for column, (value, heat) in enumerate(values):
            canvas.paste(panel_image(value, heat), (gap + column * (panel + gap), top))
        before = point_rows[index]["boundary_distance_px"]
        after = multi_rows[index]["boundary_distance_px"]
        draw.text(
            (gap, top + panel + 7),
            f"{population.families[index]} | {kind} | sample {index} | point {before:.3f}px | multi {after:.3f}px",
            fill="black",
            font=font,
        )
    REPORTS.mkdir(parents=True, exist_ok=True)
    canvas.save(REPORTS / "R105B_VISUAL_QA.png", optimize=True)


def decision(summary: dict[str, Any]) -> dict[str, Any]:
    point = summary["decomposition"]["matched_point_single"]["summary"]
    single = summary["decomposition"]["evidence_set_single"]["summary"]
    multi = summary["decomposition"]["evidence_set_four"]["summary"]
    multi_vs_single = {
        "boundary": multi["boundary_distance_px"] < single["boundary_distance_px"],
        "centroid": multi["centroid_error_px"] < single["centroid_error_px"],
        "transition_center": multi["transition_center_error_px"] < single["transition_center_error_px"],
        "transition_width": multi["transition_width_error_px"] < single["transition_width_error_px"],
        "image_mae": multi["mean_abs_error_gray"] < single["mean_abs_error_gray"],
        "identity": multi["identity_mae_gray"] <= single["identity_mae_gray"] + 0.05,
    }
    multi_vs_point = {
        "boundary": multi["boundary_distance_px"] < point["boundary_distance_px"],
        "centroid": multi["centroid_error_px"] < point["centroid_error_px"],
        "transition_center": multi["transition_center_error_px"] < point["transition_center_error_px"],
        "image_mae": multi["mean_abs_error_gray"] < point["mean_abs_error_gray"],
    }
    geometry_wins = sum(int(multi_vs_single[key]) for key in ["boundary", "centroid", "transition_center", "transition_width"])
    point_wins = sum(int(value) for value in multi_vs_point.values())
    uncertainty = summary["uncertainty"]
    uncertainty_coherent = (
        uncertainty["evidence_set_four"]["median_uncertainty_gray"]
        < uncertainty["evidence_set_single"]["median_uncertainty_gray"]
        and uncertainty["evidence_set_four"]["spearman_uncertainty_vs_image_mae"] > 0.20
    )
    motion = summary["motion_exposure"]
    behavior_safe = (
        motion["evidence_set_four"]["known_motion_error_px_p95"]
        <= motion["matched_point_single"]["known_motion_error_px_p95"] * 1.15
        and summary["tile"]["evidence_set_four"]["max_abs_gray"] < 0.10
    )
    authorized = geometry_wins >= 3 and point_wins >= 3 and uncertainty_coherent and behavior_safe
    return {
        "multi_vs_single": multi_vs_single,
        "multi_vs_point": multi_vs_point,
        "geometry_wins_vs_single": geometry_wins,
        "wins_vs_point": point_wins,
        "uncertainty_coherent": bool(uncertainty_coherent),
        "motion_and_tile_safe": bool(behavior_safe),
        "full_model_authorized": bool(authorized),
        "interpretation": (
            "Variable-observation evidence reconstruction is supported for a larger experiment."
            if authorized
            else "The mechanism did not yet demonstrate a reliable held-out advantage; do not start a full model."
        ),
    }


def render_report(summary: dict[str, Any]) -> str:
    rows = []
    for name, payload in summary["decomposition"].items():
        value = payload["summary"]
        rows.append(
            f"| {name} | {value['iou']:.5f} | {value['boundary_distance_px']:.4f} | "
            f"{value['centroid_error_px']:.4f} | {value['transition_center_error_px']:.4f} | "
            f"{value['transition_width_error_px']:.4f} | {value['mean_abs_error_gray']:.3f} | "
            f"{value['identity_mae_gray']:.3f} |"
        )
    return "\n".join(
        [
            "# R105B Evidence-Set Reconstruction Results",
            "",
            f"Status: {summary['status']}",
            "",
            "| Arm | IoU | Boundary px | Centroid px | Transition center px | Width px | MAE gray | Identity gray |",
            "|---|---:|---:|---:|---:|---:|---:|---:|",
            *rows,
            "",
            "## Uncertainty",
            "",
            "```json",
            json.dumps(summary["uncertainty"], indent=2),
            "```",
            "",
            "## Motion, exposure and tile",
            "",
            "```json",
            json.dumps({"motion_exposure": summary["motion_exposure"], "tile": summary["tile"]}, indent=2),
            "```",
            "",
            "## Decision",
            "",
            summary["decision"]["interpretation"],
            "",
            "This is a procedural mechanism probe. It does not establish real SEM or external-GMF improvement.",
        ]
    )


def main() -> int:
    RESULTS.mkdir(parents=True, exist_ok=True)
    REPORTS.mkdir(parents=True, exist_ok=True)
    WEIGHTS.mkdir(parents=True, exist_ok=True)
    if not torch.cuda.is_available():
        raise RuntimeError("R105B requires CUDA for the matched probe")
    device = torch.device("cuda:0")
    seed_all(int(CONFIG["training"]["seed"]))
    print(json.dumps({"stage": "build_populations", "device": torch.cuda.get_device_name(0)}), flush=True)
    train = build_population(int(CONFIG["data"]["train_samples"]), "train")
    print(json.dumps({"stage": "train_population_ready", "samples": len(train.families)}), flush=True)
    validation = build_population(int(CONFIG["data"]["validation_samples"]), "validation")
    print(json.dumps({"stage": "validation_population_ready", "samples": len(validation.families)}), flush=True)
    test = build_population(int(CONFIG["data"]["test_samples"]), "test")
    print(json.dumps({"stage": "test_population_ready", "samples": len(test.families)}), flush=True)
    schedule, observation_schedule = make_schedule(len(train.families))
    write_json(
        RESULTS / "population_manifest.json",
        {
            "train": len(train.families),
            "validation": len(validation.families),
            "test": len(test.families),
            "test_families": {name: test.families.count(name) for name in sorted(set(test.families))},
            "schedule_shape": list(schedule.shape),
            "evidence_observation_counts": {str(value): int((observation_schedule == value).sum()) for value in sorted(set(observation_schedule))},
            "seed": int(CONFIG["training"]["seed"]),
        },
    )
    point, point_history = train_arm("point", train, validation, schedule, observation_schedule, device)
    evidence, evidence_history = train_arm("evidence", train, validation, schedule, observation_schedule, device)
    write_json(RESULTS / "training_history.json", {"point": point_history, "evidence": evidence_history})
    print(json.dumps({"stage": "heldout_evaluation_started"}), flush=True)
    point_n1 = predict_population(point, test, 1, device)
    evidence_n1 = predict_population(evidence, test, 1, device)
    evidence_n4 = predict_population(evidence, test, 4, device)
    outputs = {
        "matched_point_single": point_n1["output"],
        "evidence_set_single": evidence_n1["output"],
        "evidence_set_four": evidence_n4["output"],
        "evidence_set_four_physics_candidate": evidence_n4["physics_candidate"],
        "evidence_set_four_oracle_candidate": evidence_n4["oracle_candidate"],
    }
    decomposition = summarize_outputs(outputs, test)
    uncertainties = {
        "evidence_set_single": uncertainty_analysis(
            evidence_n1["output"], evidence_n1["uncertainty"], decomposition["evidence_set_single"]["per_image"], test
        ),
        "evidence_set_four": uncertainty_analysis(
            evidence_n4["output"], evidence_n4["uncertainty"], decomposition["evidence_set_four"]["per_image"], test
        ),
    }
    model_modes = {
        "matched_point_single": (point, 1),
        "evidence_set_single": (evidence, 1),
        "evidence_set_four": (evidence, 4),
    }
    motion_exposure = motion_exposure_metrics(model_modes, test, device)
    tile = {name: tile_metrics(model, test, used, device) for name, (model, used) in model_modes.items()}
    summary: dict[str, Any] = {
        "status": "complete",
        "experiment_id": CONFIG["experiment_id"],
        "device": torch.cuda.get_device_name(0),
        "parameter_count": sum(parameter.numel() for parameter in evidence.parameters()),
        "matched_parameter_counts_equal": sum(parameter.numel() for parameter in evidence.parameters()) == sum(parameter.numel() for parameter in point.parameters()),
        "decomposition": decomposition,
        "uncertainty": uncertainties,
        "motion_exposure": motion_exposure,
        "tile": tile,
    }
    summary["decision"] = decision(summary)
    write_json(RESULTS / "summary.json", summary)
    (REPORTS / "R105B_RESULTS.md").write_text(render_report(summary), encoding="utf-8")
    render_visual_qa(
        test,
        outputs,
        {"evidence_set_single": evidence_n1["uncertainty"], "evidence_set_four": evidence_n4["uncertainty"]},
        summary,
    )
    print(json.dumps({"status": "complete", "decision": summary["decision"]}), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

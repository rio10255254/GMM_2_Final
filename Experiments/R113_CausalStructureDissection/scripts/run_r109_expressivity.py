"""Deterministic, no-training expressivity ceiling for the frozen R109 renderer.

The oracle methods see synthetic truth.  They are representation tests, not
deployable estimators and must never be reported as model accuracy.
"""
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
from collections import defaultdict
from pathlib import Path

import cv2
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
os.environ.setdefault("CUBLAS_WORKSPACE_CONFIG", ":4096:8")
import torch
import torch.nn.functional as F
from scipy.ndimage import binary_erosion, distance_transform_edt
from scipy.stats import spearmanr


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = ROOT / "config" / "r109_expressivity.json"
DEFAULT_OUT = ROOT / "results" / "r109_expressivity"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def sha256_array(value: np.ndarray) -> str:
    value = np.ascontiguousarray(value)
    return hashlib.sha256(value.view(np.uint8)).hexdigest()


def seed_everything(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)
    torch.backends.cudnn.benchmark = False
    torch.backends.cudnn.deterministic = True
    torch.backends.cuda.matmul.allow_tf32 = False
    torch.backends.cudnn.allow_tf32 = False
    # CUDA grid-sample backward has no deterministic kernel in this PyTorch
    # build.  Warn-only keeps every other deterministic guard active; the
    # validator separately reruns a subset and enforces a numeric tolerance.
    torch.use_deterministic_algorithms(True, warn_only=True)


def radial_polygon(center, base_radius, angle, radial_fn, points=1440):
    theta = np.linspace(0, 2 * np.pi, points, endpoint=False, dtype=np.float64)
    radius = base_radius * radial_fn(theta)
    x = center[0] + radius * np.cos(theta + angle)
    y = center[1] + radius * np.sin(theta + angle)
    return np.stack([x, y], axis=1)


def fill_polygon(mask: np.ndarray, points: np.ndarray, value: int = 255) -> None:
    cv2.fillPoly(mask, [np.rint(points).astype(np.int32)], value, lineType=cv2.LINE_8)


def build_shape_mask(family: str, size: int, ss: int, rep: int, rng: np.random.Generator) -> np.ndarray:
    high = size * ss
    mask = np.zeros((high, high), np.uint8)
    cx = (size / 2 + [-0.37, 0.21, 0.43][rep]) * ss
    cy = (size / 2 + [0.29, -0.41, 0.13][rep]) * ss
    angle = math.radians([11, 37, 68][rep])
    center = (cx, cy)
    if family == "ellipse":
        cv2.ellipse(mask, (round(cx), round(cy)), (round((36 - rep) * ss), round((25 + rep) * ss)),
                    math.degrees(angle), 0, 360, 255, -1, cv2.LINE_8)
    elif family == "lobed":
        points = radial_polygon(center, 31 * ss, angle,
                                lambda t: 1 + .16 * np.cos(3 * t + .3 * rep) + .075 * np.sin(5 * t))
        fill_polygon(mask, points)
    elif family == "rough_fourier":
        phases = rng.uniform(0, 2 * np.pi, 4)
        def rough(t):
            return (1 + .075 * np.sin(7 * t + phases[0]) + .048 * np.sin(13 * t + phases[1])
                    + .032 * np.cos(19 * t + phases[2]) + .020 * np.sin(29 * t + phases[3]))
        fill_polygon(mask, radial_polygon(center, 30 * ss, angle, rough, points=2400))
    elif family == "concave_star":
        fill_polygon(mask, radial_polygon(center, 32 * ss, angle,
                                           lambda t: .84 + .22 * np.cos(5 * t) + .055 * np.cos(10 * t), 1800))
    elif family == "superellipse":
        t = np.linspace(0, 2 * np.pi, 1800, endpoint=False)
        exponent = 2 / (4.3 + .5 * rep)
        x = np.sign(np.cos(t)) * np.abs(np.cos(t)) ** exponent * (35 * ss)
        y = np.sign(np.sin(t)) * np.abs(np.sin(t)) ** exponent * ((25 + rep) * ss)
        ca, sa = np.cos(angle), np.sin(angle)
        points = np.stack([cx + ca * x - sa * y, cy + sa * x + ca * y], 1)
        fill_polygon(mask, points)
    elif family == "crescent":
        cv2.ellipse(mask, (round(cx - 3 * ss), round(cy)), (round(34 * ss), round(29 * ss)),
                    math.degrees(angle), 0, 360, 255, -1)
        dx = (10 + rep) * ss * np.cos(angle)
        dy = (10 + rep) * ss * np.sin(angle)
        cv2.ellipse(mask, (round(cx + dx), round(cy + dy)), (round(29 * ss), round(24 * ss)),
                    math.degrees(angle), 0, 360, 0, -1)
    elif family == "thin_ring":
        axes = (round(35 * ss), round((27 + rep) * ss))
        inner = (round((29 - .5 * rep) * ss), round((21 + .5 * rep) * ss))
        cv2.ellipse(mask, (round(cx), round(cy)), axes, math.degrees(angle), 0, 360, 255, -1)
        cv2.ellipse(mask, (round(cx), round(cy)), inner, math.degrees(angle), 0, 360, 0, -1)
    elif family == "close_pair":
        sep = (17.0 + .5 * rep) * ss
        dx, dy = sep * np.cos(angle), sep * np.sin(angle)
        for sign in (-1, 1):
            cv2.ellipse(mask, (round(cx + sign * dx), round(cy + sign * dy)),
                        (round(14.5 * ss), round(22 * ss)), math.degrees(angle), 0, 360, 255, -1)
    else:
        raise ValueError(f"Unknown family: {family}")
    return mask


def make_clean_target(mask_high: np.ndarray, size: int, ss: int, polarity: int,
                      texture_kind: str, rng: np.random.Generator) -> tuple[np.ndarray, np.ndarray]:
    high = size * ss
    yy, xx = np.mgrid[:high, :high].astype(np.float32) / ss
    alpha = mask_high.astype(np.float32) / 255.0
    background = .18 if polarity > 0 else .82
    foreground = .82 if polarity > 0 else .18
    texture = np.zeros_like(alpha)
    if texture_kind == "striations":
        texture = .030 * np.sin(2 * np.pi * (.135 * xx + .053 * yy) + .7)
    elif texture_kind == "mottled":
        noise = rng.normal(size=(high, high)).astype(np.float32)
        texture = cv2.GaussianBlur(noise, (0, 0), 1.1 * ss)
        texture /= max(float(texture.std()), 1e-6)
        texture *= .026
    elif texture_kind == "micro_ridges":
        texture = (.022 * np.sin(2 * np.pi * (.205 * xx - .041 * yy))
                   + .012 * np.sin(2 * np.pi * (.071 * xx + .179 * yy)))
    clean_high = background + (foreground - background) * alpha + texture * alpha
    clean = cv2.resize(clean_high, (size, size), interpolation=cv2.INTER_AREA).astype(np.float32)
    mask_soft = cv2.resize(alpha, (size, size), interpolation=cv2.INTER_AREA).astype(np.float32)
    return np.clip(clean, 0, 1), np.clip(mask_soft, 0, 1)


def motion_blur(image: np.ndarray, length: int, angle_degrees: float) -> np.ndarray:
    kernel = np.zeros((length, length), np.float32)
    kernel[length // 2, :] = 1.0
    matrix = cv2.getRotationMatrix2D(((length - 1) / 2, (length - 1) / 2), angle_degrees, 1)
    kernel = cv2.warpAffine(kernel, matrix, (length, length), flags=cv2.INTER_LINEAR)
    kernel /= max(float(kernel.sum()), 1e-8)
    return cv2.filter2D(image, -1, kernel, borderType=cv2.BORDER_REFLECT_101)


def shifted(image: np.ndarray, dx: float, dy: float) -> np.ndarray:
    matrix = np.float32([[1, 0, dx], [0, 1, dy]])
    return cv2.warpAffine(image, matrix, (image.shape[1], image.shape[0]), flags=cv2.INTER_LINEAR,
                          borderMode=cv2.BORDER_REFLECT_101)


def degrade(clean: np.ndarray, family: str, rng: np.random.Generator, rep: int) -> np.ndarray:
    if family == "clear":
        value = cv2.GaussianBlur(clean, (0, 0), .55)
        noise_sigma = .0015
    elif family == "standard":
        value = cv2.GaussianBlur(clean, (0, 0), 1.65 + .15 * rep)
        noise_sigma = .006
    elif family == "strong_blur":
        value = cv2.GaussianBlur(clean, (0, 0), 3.4 + .45 * rep)
        noise_sigma = .008
    elif family == "anisotropic_motion":
        value = cv2.GaussianBlur(clean, (0, 0), sigmaX=2.7 + .3 * rep, sigmaY=.85)
        value = motion_blur(value, 7 + 2 * rep, 23 + 21 * rep)
        noise_sigma = .006
    elif family == "halo_ghost":
        base = cv2.GaussianBlur(clean, (0, 0), 1.8)
        halo = cv2.GaussianBlur(clean, (0, 0), 4.2) - cv2.GaussianBlur(clean, (0, 0), 1.0)
        value = .94 * (base + .36 * halo) + .06 * shifted(base, 2.2 + rep, -1.2)
        noise_sigma = .0065
    elif family == "low_contrast_uneven":
        base = cv2.GaussianBlur(clean, (0, 0), 2.1)
        yy, xx = np.mgrid[:clean.shape[0], :clean.shape[1]].astype(np.float32)
        illumination = .075 * ((xx / (clean.shape[1] - 1)) - .5) + .045 * np.sin(2 * np.pi * yy / clean.shape[0])
        value = .5 + (.46 + .05 * rep) * (base - .5) + illumination
        noise_sigma = .009
    elif family == "boundary_fade":
        sharp = cv2.GaussianBlur(clean, (0, 0), 1.1)
        soft = cv2.GaussianBlur(clean, (0, 0), 4.8)
        yy, xx = np.mgrid[:clean.shape[0], :clean.shape[1]].astype(np.float32)
        fade = .5 + .5 * np.sin(2 * np.pi * (xx * .0067 + yy * .0041) + rep)
        fade = cv2.GaussianBlur(fade, (0, 0), 9)
        value = sharp * (1 - .82 * fade) + soft * (.82 * fade)
        noise_sigma = .007
    elif family == "mixed_hard":
        value = cv2.GaussianBlur(clean, (0, 0), sigmaX=4.4, sigmaY=1.3)
        value = motion_blur(value, 11, 49 + 13 * rep)
        halo = cv2.GaussianBlur(clean, (0, 0), 5.0) - cv2.GaussianBlur(clean, (0, 0), 1.3)
        value = .5 + .58 * (value - .5) + .30 * halo
        value = .95 * value + .05 * shifted(value, -3.0, 1.8)
        yy, xx = np.mgrid[:clean.shape[0], :clean.shape[1]].astype(np.float32)
        value += .055 * ((xx + .7 * yy) / (1.7 * (clean.shape[0] - 1)) - .5)
        noise_sigma = .012
    else:
        raise ValueError(f"Unknown degradation: {family}")
    noise = rng.normal(0, noise_sigma, clean.shape).astype(np.float32)
    row = rng.normal(0, noise_sigma * .18, (clean.shape[0], 1)).astype(np.float32)
    return np.clip(value + noise + row, 0, 1).astype(np.float32)


def build_scenes(config: dict) -> list[dict]:
    seed = int(config["seed"])
    size = int(config["canvas_size"])
    ss = int(config["supersample_factor"])
    degradations = list(config["degradation_families"])
    texture_names = ["none", "striations", "mottled", "micro_ridges"]
    scenes = []
    for shape_index, family in enumerate(config["shape_families"]):
        # One fixed latent geometry per family.  Its three observations change
        # only imaging condition, so condition invariance cannot be confused
        # with differences in ground-truth shape.
        latent_seed = seed + shape_index * 1009
        latent_rng = np.random.default_rng(latent_seed)
        latent_variant = shape_index % int(config["scenes_per_shape"])
        mask_high = build_shape_mask(family, size, ss, latent_variant, latent_rng)
        latent_shape_id = f"latent_{shape_index:02d}_{family}"
        texture = texture_names[shape_index % len(texture_names)]
        for rep in range(int(config["scenes_per_shape"])):
            scene_seed = seed + shape_index * 1009 + rep * 97
            rng = np.random.default_rng(scene_seed)
            polarity = 1 if (shape_index + rep) % 2 == 0 else -1
            # Reset texture RNG so the same latent surface is retained while
            # polarity and degradation change.
            texture_rng = np.random.default_rng(latent_seed + 41)
            clean, mask_soft = make_clean_target(mask_high, size, ss, polarity, texture, texture_rng)
            degradation = degradations[(shape_index * 3 + rep * 5) % len(degradations)]
            raw = degrade(clean, degradation, rng, rep)
            scene_id = f"{shape_index:02d}_{family}_r{rep}_{degradation}_{'bright' if polarity > 0 else 'dark'}"
            scenes.append({
                "scene_id": scene_id,
                "shape": family,
                "latent_shape_id": latent_shape_id,
                "rep": rep,
                "seed": scene_seed,
                "degradation": degradation,
                "polarity": polarity,
                "texture": texture,
                "raw": raw,
                "target": clean,
                "mask": mask_soft,
            })
    return scenes


def gaussian_kernel(sigma: float, device, dtype):
    radius = max(1, int(math.ceil(3 * sigma)))
    axis = torch.arange(-radius, radius + 1, device=device, dtype=dtype)
    kernel = torch.exp(-.5 * (axis / sigma).square())
    return kernel / kernel.sum(), radius


def gaussian_blur(value: torch.Tensor, sigma: float) -> torch.Tensor:
    kernel, radius = gaussian_kernel(float(sigma), value.device, value.dtype)
    horizontal = kernel.view(1, 1, 1, -1)
    vertical = kernel.view(1, 1, -1, 1)
    channels = value.shape[1]
    horizontal = horizontal.expand(channels, 1, 1, -1)
    vertical = vertical.expand(channels, 1, -1, 1)
    mode = "reflect" if min(value.shape[-2:]) > radius else "replicate"
    output = F.conv2d(F.pad(value, (radius, radius, 0, 0), mode=mode), horizontal, groups=channels)
    return F.conv2d(F.pad(output, (0, 0, radius, radius), mode=mode), vertical, groups=channels)


def gradients(value: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
    gx = F.pad(value[..., 1:] - value[..., :-1], (0, 1, 0, 0))
    gy = F.pad(value[..., 1:, :] - value[..., :-1, :], (0, 0, 0, 1))
    return gx, gy


def warp(value: torch.Tensor, flow: torch.Tensor) -> torch.Tensor:
    n, _, h, w = value.shape
    yy, xx = torch.meshgrid(torch.linspace(-1, 1, h, device=value.device, dtype=value.dtype),
                            torch.linspace(-1, 1, w, device=value.device, dtype=value.dtype), indexing="ij")
    grid = torch.stack([xx, yy], -1).unsqueeze(0).expand(n, -1, -1, -1).clone()
    grid[..., 0] += flow[:, 0] * (2 / max(w - 1, 1))
    grid[..., 1] += flow[:, 1] * (2 / max(h - 1, 1))
    return F.grid_sample(value, grid, mode="bilinear", padding_mode="reflection", align_corners=True)


def renderer_context(raw: torch.Tensor, mask: torch.Tensor, contract: dict) -> dict:
    gx, gy = gradients(raw)
    magnitude = torch.sqrt(gx.square() + gy.square() + 1e-8)
    local_mean = gaussian_blur(raw, float(contract["context_blur_sigma_px"]))
    local_scale = torch.sqrt(gaussian_blur((raw - local_mean).square(), float(contract["context_blur_sigma_px"]))
                             + (2 / 255) ** 2)
    source_support = ((magnitude / (local_scale + 2 / 255) - .05) / 1.10).clamp(0, 1)
    mgx, mgy = gradients(mask)
    oracle_boundary = torch.sqrt(mgx.square() + mgy.square() + 1e-8).clamp(0, 1)
    dilation = int(contract["boundary_support_dilation_px"])
    if dilation % 2 == 0:
        dilation += 1
    oracle_support = float(contract["boundary_support_scale"]) * F.max_pool2d(
        oracle_boundary, dilation, 1, dilation // 2)
    support = torch.maximum(source_support, oracle_support).clamp(0, 1)
    smooth = gaussian_blur(raw, float(contract["normal_blur_sigma_px"]))
    sgx, sgy = gradients(smooth)
    smag = torch.sqrt(sgx.square() + sgy.square() + 1e-8)
    return {
        "support": support,
        "normal_x": sgx / smag,
        "normal_y": sgy / smag,
        "boundary": oracle_boundary,
    }


def render_r109(raw: torch.Tensor, width_gain: torch.Tensor, normal_shift: torch.Tensor,
                context: dict, contract: dict) -> torch.Tensor:
    flow = torch.cat([normal_shift * context["normal_x"], normal_shift * context["normal_y"]], 1)
    warped = warp(raw, flow * context["support"])
    window = int(contract["local_range_window_px"])
    radius = window // 2
    local_max = F.max_pool2d(warped, window, 1, radius)
    local_min = -F.max_pool2d(-warped, window, 1, radius)
    dynamic = (local_max - local_min).clamp_min(2 / 255)
    unit = ((warped - local_min) / dynamic).clamp(1e-3, 1 - 1e-3)
    corrected = torch.sigmoid(width_gain * (torch.log(unit) - torch.log1p(-unit)))
    proposal = local_min + dynamic * corrected
    return (raw + context["support"] * (proposal - raw)).clamp(0, 1)


def control_fields(parameters: dict, variant: str, target_shape, config: dict) -> tuple[torch.Tensor, torch.Tensor]:
    contract = config["r109_contract"]
    minimum = float(contract["minimum_width_gain"])
    maximum = float(contract["maximum_width_gain"])
    max_shift = float(contract["maximum_normal_shift_px"])
    width_param = parameters.get("width")
    shift_param = parameters.get("shift")
    if width_param is None:
        width = torch.full(target_shape, minimum, device=shift_param.device, dtype=shift_param.dtype)
    else:
        if width_param.shape[-2:] != target_shape[-2:]:
            width_param = F.interpolate(width_param, size=target_shape[-2:], mode="bicubic", align_corners=True)
        if "smooth" in variant:
            width_param = gaussian_blur(width_param, float(config["optimization"]["smooth_control_sigma_px"]))
        width = minimum + (maximum - minimum) * torch.sigmoid(width_param)
    if shift_param is None:
        shift = torch.zeros(target_shape, device=width_param.device, dtype=width_param.dtype)
    else:
        if shift_param.shape[-2:] != target_shape[-2:]:
            shift_param = F.interpolate(shift_param, size=target_shape[-2:], mode="bicubic", align_corners=True)
        if "smooth" in variant:
            shift_param = gaussian_blur(shift_param, float(config["optimization"]["smooth_control_sigma_px"]))
        shift = max_shift * torch.tanh(shift_param)
    return width, shift


def per_scene_loss(output: torch.Tensor, target: torch.Tensor, mask: torch.Tensor,
                   polarity: torch.Tensor, context: dict, config: dict) -> torch.Tensor:
    weights = config["optimization"]["loss_weights"]
    boundary = F.max_pool2d(context["boundary"], 9, 1, 4).clamp(0, 1)
    image = torch.abs(output - target).mean((1, 2, 3))
    edge_image = (torch.abs(output - target) * boundary).sum((1, 2, 3)) / boundary.sum((1, 2, 3)).clamp_min(1)
    ogx, ogy = gradients(output)
    tgx, tgy = gradients(target)
    gradient = ((torch.abs(ogx - tgx) + torch.abs(ogy - tgy)) * (0.2 + boundary)).mean((1, 2, 3))
    probability = torch.sigmoid(32 * polarity * (output - .5)).clamp(1e-5, 1 - 1e-5)
    bce = F.binary_cross_entropy(probability, mask, reduction="none").mean((1, 2, 3))
    intersection = (probability * mask).sum((1, 2, 3))
    dice = 1 - (2 * intersection + 1e-6) / (probability.sum((1, 2, 3)) + mask.sum((1, 2, 3)) + 1e-6)
    return (float(weights["image"]) * image + float(weights["edge_image"]) * edge_image
            + float(weights["gradient"]) * gradient + float(weights["contour_bce"]) * bce
            + float(weights["contour_dice"]) * dice)


def optimize_variant(raw: torch.Tensor, target: torch.Tensor, mask: torch.Tensor, polarity: torch.Tensor,
                     context: dict, variant: str, config: dict) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor, list[dict]]:
    n, _, h, w = raw.shape
    if variant == "oracle_global_width_shift":
        shape = (n, 1, 1, 1)
        lr = float(config["optimization"]["learning_rate_global"])
    elif variant == "oracle_width_shift_smooth":
        grid = int(config["optimization"]["smooth_control_grid"])
        shape = (n, 1, grid, grid)
        lr = float(config["optimization"]["learning_rate_smooth"])
    else:
        shape = (n, 1, h, w)
        lr = float(config["optimization"]["learning_rate_dense"])
    parameters = {}
    if variant not in {"oracle_shift_only"}:
        parameters["width"] = torch.nn.Parameter(torch.full(shape, -3.1, device=raw.device))
    if variant not in {"oracle_width_only"}:
        parameters["shift"] = torch.nn.Parameter(torch.zeros(shape, device=raw.device))
    optimizer = torch.optim.Adam(list(parameters.values()), lr=lr)
    total_steps = int(config["optimization"]["steps"])
    history = []
    best_loss = float("inf")
    best = None
    for step in range(total_steps):
        fraction = step / max(total_steps - 1, 1)
        current_lr = lr * (.08 + .92 * .5 * (1 + math.cos(math.pi * fraction)))
        for group in optimizer.param_groups:
            group["lr"] = current_lr
        optimizer.zero_grad(set_to_none=True)
        width, shift = control_fields(parameters, variant, raw.shape, config)
        output = render_r109(raw, width, shift, context, config["r109_contract"])
        scene_losses = per_scene_loss(output, target, mask, polarity, context, config)
        loss = scene_losses.mean()
        if not torch.isfinite(loss):
            raise RuntimeError(f"Non-finite optimization at {variant} step {step}")
        loss.backward()
        torch.nn.utils.clip_grad_norm_(list(parameters.values()), 5.0)
        optimizer.step()
        numeric = float(loss.detach().cpu())
        if numeric < best_loss:
            best_loss = numeric
            best = {name: value.detach().clone() for name, value in parameters.items()}
        if step == 0 or (step + 1) % 20 == 0 or step + 1 == total_steps:
            history.append({"step": step + 1, "loss": numeric, "learning_rate": current_lr,
                            "scene_loss_max": float(scene_losses.max().detach().cpu())})
    assert best is not None
    width, shift = control_fields(best, variant, raw.shape, config)
    output = render_r109(raw, width, shift, context, config["r109_contract"])
    return output.detach(), width.detach(), shift.detach(), history


def load_learned_r109(raw: torch.Tensor, config: dict):
    source = config["source"]
    model_path = Path(source["r109_model_root"]) / "model" / "r109_model.py"
    module_name = "r113_frozen_r109_model"
    spec = importlib.util.spec_from_file_location(module_name, model_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load {model_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    model = module.build_model().to(raw.device)
    checkpoint = torch.load(source["r109_checkpoint"], map_location=raw.device)
    model.load_state_dict(checkpoint["model"], strict=True)
    model.eval()
    with torch.inference_mode():
        details = model.forward_details(raw)
    return details.output.float(), details.width_gain.float(), details.normal_shift.float(), details.support.float()


def bounded_detail_oracle(base: torch.Tensor, target: torch.Tensor, mask: torch.Tensor,
                          context: dict, config: dict) -> tuple[torch.Tensor, torch.Tensor]:
    detail_config = config["detail_oracle"]
    residual = target - base
    highpass = residual - gaussian_blur(residual, float(detail_config["zero_mean_sigma_px"]))
    highpass = highpass - gaussian_blur(highpass, float(detail_config["zero_mean_sigma_px"]))
    bound = float(detail_config["maximum_amplitude_gray_levels"]) / 255.0
    highpass = highpass.clamp(-bound, bound)
    dilation = int(detail_config["support_dilation_px"])
    if dilation % 2 == 0:
        dilation += 1
    boundary_support = F.max_pool2d(context["boundary"], dilation, 1, dilation // 2)
    target_hp = target - gaussian_blur(target, float(detail_config["zero_mean_sigma_px"]))
    texture_support = (torch.abs(target_hp) / (4 / 255)).clamp(0, 1)
    support = torch.maximum(boundary_support, texture_support * mask).clamp(0, 1)
    detail = highpass * support
    return (base + detail).clamp(0, 1), detail


def binary_boundary(mask: np.ndarray) -> np.ndarray:
    mask_u8 = mask.astype(np.uint8)
    kernel = np.ones((3, 3), np.uint8)
    return cv2.morphologyEx(mask_u8, cv2.MORPH_GRADIENT, kernel).astype(bool)


def contour_distances(prediction: np.ndarray, truth: np.ndarray) -> tuple[float, float]:
    pb = binary_boundary(prediction)
    tb = binary_boundary(truth)
    if not pb.any() or not tb.any():
        return 1e3, 1e3
    distance_to_truth = distance_transform_edt(~tb)
    distance_to_prediction = distance_transform_edt(~pb)
    distances = np.concatenate([distance_to_truth[pb], distance_to_prediction[tb]])
    assd = .5 * (float(distance_to_truth[pb].mean()) + float(distance_to_prediction[tb].mean()))
    return assd, float(np.percentile(distances, 95))


def evaluate_image(image: np.ndarray, target: np.ndarray, mask_soft: np.ndarray, polarity: int,
                   config: dict) -> dict:
    truth = mask_soft >= float(config["evaluation"]["contour_threshold"])
    prediction = polarity * (image - .5) >= 0
    intersection = np.logical_and(prediction, truth).sum()
    union = np.logical_or(prediction, truth).sum()
    iou = float(intersection / max(union, 1))
    dice = float(2 * intersection / max(prediction.sum() + truth.sum(), 1))
    assd, hd95 = contour_distances(prediction, truth)
    area_error = float(abs(int(prediction.sum()) - int(truth.sum())) / max(int(truth.sum()), 1))
    yy, xx = np.mgrid[:truth.shape[0], :truth.shape[1]]
    if prediction.any() and truth.any():
        centroid_error = float(math.hypot(float(xx[prediction].mean() - xx[truth].mean()),
                                          float(yy[prediction].mean() - yy[truth].mean())))
    else:
        centroid_error = 1e3
    truth_boundary = binary_boundary(truth)
    band = distance_transform_edt(~truth_boundary) <= int(config["evaluation"]["boundary_band_px"])
    image_mae = float(np.mean(np.abs(image - target)) * 255)
    boundary_mae = float(np.mean(np.abs(image[band] - target[band])) * 255)
    igy, igx = np.gradient(image)
    tgy, tgx = np.gradient(target)
    image_grad = np.sqrt(igx ** 2 + igy ** 2)
    target_grad = np.sqrt(tgx ** 2 + tgy ** 2)
    gradient_mae = float(np.mean(np.abs(image_grad[band] - target_grad[band])) * 255)
    sigma = float(config["evaluation"]["highpass_sigma_px"])
    image_hp = image - cv2.GaussianBlur(image, (0, 0), sigma)
    target_hp = target - cv2.GaussianBlur(target, (0, 0), sigma)
    hf_rmse = float(np.sqrt(np.mean((image_hp - target_hp) ** 2)) * 255)
    erosion = int(config["evaluation"]["texture_interior_erosion_px"])
    interior = binary_erosion(truth, iterations=erosion)
    texture_rmse = (float(np.sqrt(np.mean((image_hp[interior] - target_hp[interior]) ** 2)) * 255)
                    if interior.any() else float("nan"))
    return {
        "iou": iou, "dice": dice, "assd_px": assd, "hd95_px": hd95,
        "area_relative_error": area_error, "centroid_error_px": centroid_error,
        "image_mae_gray": image_mae, "boundary_mae_gray": boundary_mae,
        "edge_gradient_mae_gray": gradient_mae, "high_frequency_rmse_gray": hf_rmse,
        "interior_texture_rmse_gray": texture_rmse,
    }


def control_statistics(width: np.ndarray | None, shift: np.ndarray | None, support: np.ndarray,
                       scene_index: int) -> dict:
    selected = support[scene_index, 0] >= .5
    row = {}
    for name, value in (("width", width), ("shift", shift)):
        if value is None:
            for suffix in ("mean", "std", "p05", "p95", "tv"):
                row[f"{name}_{suffix}"] = float("nan")
            continue
        field = value[scene_index, 0]
        sample = field[selected] if selected.any() else field.ravel()
        row[f"{name}_mean"] = float(np.mean(sample))
        row[f"{name}_std"] = float(np.std(sample))
        row[f"{name}_p05"] = float(np.percentile(sample, 5))
        row[f"{name}_p95"] = float(np.percentile(sample, 95))
        row[f"{name}_tv"] = float(np.mean(np.abs(np.diff(field, axis=0))) + np.mean(np.abs(np.diff(field, axis=1))))
    return row


def aggregate_metrics(rows: list[dict], methods: list[str]) -> dict:
    metric_directions = {
        "iou": "higher", "dice": "higher", "assd_px": "lower", "hd95_px": "lower",
        "area_relative_error": "lower", "centroid_error_px": "lower", "image_mae_gray": "lower",
        "boundary_mae_gray": "lower", "edge_gradient_mae_gray": "lower",
        "high_frequency_rmse_gray": "lower", "interior_texture_rmse_gray": "lower",
    }
    summary = {}
    for method in methods:
        selected = [row for row in rows if row["method"] == method]
        method_summary = {"scene_count": len(selected), "metrics": {}}
        for metric, direction in metric_directions.items():
            values = np.array([float(row[metric]) for row in selected], np.float64)
            finite = values[np.isfinite(values)]
            data = {
                "mean": float(np.mean(finite)), "median": float(np.median(finite)),
                "p05": float(np.percentile(finite, 5)), "p95": float(np.percentile(finite, 95)),
                "min": float(np.min(finite)), "max": float(np.max(finite)), "direction": direction,
            }
            method_summary["metrics"][metric] = data
        worst_assd = max(selected, key=lambda row: float(row["assd_px"]))
        worst_iou = min(selected, key=lambda row: float(row["iou"]))
        method_summary["worst_assd_scene"] = {"scene_id": worst_assd["scene_id"], "value": float(worst_assd["assd_px"])}
        method_summary["worst_iou_scene"] = {"scene_id": worst_iou["scene_id"], "value": float(worst_iou["iou"])}
        summary[method] = method_summary
    return summary


def stratified_metrics(rows: list[dict], methods: list[str]) -> list[dict]:
    output = []
    for field in ("shape", "degradation", "polarity_name"):
        values = sorted({row[field] for row in rows})
        for value in values:
            for method in methods:
                group = [row for row in rows if row[field] == value and row["method"] == method]
                output.append({
                    "stratum_type": field, "stratum": value, "method": method, "count": len(group),
                    "assd_mean_px": float(np.mean([float(row["assd_px"]) for row in group])),
                    "assd_worst_px": float(np.max([float(row["assd_px"]) for row in group])),
                    "iou_mean": float(np.mean([float(row["iou"]) for row in group])),
                    "iou_worst": float(np.min([float(row["iou"]) for row in group])),
                    "boundary_mae_mean_gray": float(np.mean([float(row["boundary_mae_gray"]) for row in group])),
                    "hf_rmse_mean_gray": float(np.mean([float(row["high_frequency_rmse_gray"]) for row in group])),
                })
    return output


def mask_iou(a: np.ndarray, b: np.ndarray) -> float:
    intersection = np.logical_and(a, b).sum()
    union = np.logical_or(a, b).sum()
    return float(intersection / max(union, 1))


def analyze_condition_invariance(scenes: list[dict], methods: list[str], outputs: dict) -> tuple[list[dict], dict]:
    """Separate stability to imaging condition from retention of shape identity."""
    by_latent = defaultdict(list)
    for index, scene in enumerate(scenes):
        by_latent[scene["latent_shape_id"]].append(index)
    pair_rows = []
    summary = {}
    truth_consensus = {
        latent: np.mean(np.stack([scenes[i]["mask"] >= .5 for i in indices]), axis=0) >= .5
        for latent, indices in by_latent.items()
    }
    latent_names = sorted(by_latent)
    truth_between = []
    for a_index, latent_a in enumerate(latent_names):
        for latent_b in latent_names[a_index + 1:]:
            truth_between.append(1 - mask_iou(truth_consensus[latent_a], truth_consensus[latent_b]))
    for method in methods:
        predicted = []
        for index, scene in enumerate(scenes):
            predicted.append(scene["polarity"] * (outputs[method][index] - .5) >= 0)
        within_assd, within_iou, within_distance = [], [], []
        for latent, indices in sorted(by_latent.items()):
            for ia, first in enumerate(indices):
                for second in indices[ia + 1:]:
                    assd, hd95 = contour_distances(predicted[first], predicted[second])
                    iou = mask_iou(predicted[first], predicted[second])
                    within_assd.append(assd); within_iou.append(iou); within_distance.append(1 - iou)
                    pair_rows.append({
                        "pair_type": "same_latent_different_condition", "method": method,
                        "latent_a": latent, "latent_b": latent,
                        "scene_a": scenes[first]["scene_id"], "scene_b": scenes[second]["scene_id"],
                        "assd_px": assd, "hd95_px": hd95, "iou": iou,
                        "iou_distance": 1 - iou, "truth_iou_distance": 0.0,
                    })
        consensus = {
            latent: np.mean(np.stack([predicted[i] for i in indices]), axis=0) >= .5
            for latent, indices in by_latent.items()
        }
        reconstructed_between = []
        truth_distances = []
        for a_index, latent_a in enumerate(latent_names):
            for latent_b in latent_names[a_index + 1:]:
                truth_distance = 1 - mask_iou(truth_consensus[latent_a], truth_consensus[latent_b])
                reconstructed_distance = 1 - mask_iou(consensus[latent_a], consensus[latent_b])
                assd, hd95 = contour_distances(consensus[latent_a], consensus[latent_b])
                reconstructed_between.append(reconstructed_distance)
                truth_distances.append(truth_distance)
                pair_rows.append({
                    "pair_type": "different_latent_consensus", "method": method,
                    "latent_a": latent_a, "latent_b": latent_b, "scene_a": "", "scene_b": "",
                    "assd_px": assd, "hd95_px": hd95,
                    "iou": 1 - reconstructed_distance, "iou_distance": reconstructed_distance,
                    "truth_iou_distance": truth_distance,
                })
        correlation = spearmanr(truth_distances, reconstructed_between).statistic
        within_mean = float(np.mean(within_distance))
        between_mean = float(np.mean(reconstructed_between))
        truth_between_mean = float(np.mean(truth_between))
        summary[method] = {
            "same_latent_pair_count": len(within_assd),
            "same_latent_condition_assd_mean_px": float(np.mean(within_assd)),
            "same_latent_condition_assd_p95_px": float(np.percentile(within_assd, 95)),
            "same_latent_condition_iou_mean": float(np.mean(within_iou)),
            "same_latent_condition_iou_worst": float(np.min(within_iou)),
            "within_latent_iou_distance_mean": within_mean,
            "between_latent_iou_distance_mean": between_mean,
            "truth_between_latent_iou_distance_mean": truth_between_mean,
            "shape_retention_ratio": between_mean / max(truth_between_mean, 1e-8),
            "condition_separation_margin": between_mean - within_mean,
            "truth_vs_reconstruction_shape_distance_spearman": float(correlation),
            "collapse_warning": bool(between_mean < .65 * truth_between_mean or correlation < .75),
        }
    return pair_rows, summary


def write_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    keys = list(rows[0].keys())
    with path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=keys)
        writer.writeheader()
        writer.writerows(rows)


def save_visuals(out_dir: Path, scenes: list[dict], methods: list[str], outputs: dict,
                 metric_rows: list[dict], summary: dict) -> None:
    images_root = out_dir / "images"
    images_root.mkdir(parents=True, exist_ok=True)
    for index, scene in enumerate(scenes):
        scene_root = images_root / scene["scene_id"]
        scene_root.mkdir(parents=True, exist_ok=True)
        cv2.imwrite(str(scene_root / "raw.png"), np.rint(scene["raw"] * 255).astype(np.uint8))
        cv2.imwrite(str(scene_root / "target.png"), np.rint(scene["target"] * 255).astype(np.uint8))
        cv2.imwrite(str(scene_root / "truth_mask.png"), np.rint(scene["mask"] * 255).astype(np.uint8))
        for method in methods:
            cv2.imwrite(str(scene_root / f"{method}.png"), np.rint(outputs[method][index] * 255).astype(np.uint8))

    smooth_rows = [row for row in metric_rows if row["method"] == "oracle_width_shift_smooth"]
    worst = sorted(smooth_rows, key=lambda row: float(row["assd_px"]), reverse=True)
    chosen, seen_shapes = [], set()
    for row in worst:
        if row["shape"] not in seen_shapes or len(chosen) >= 4:
            chosen.append(next(i for i, scene in enumerate(scenes) if scene["scene_id"] == row["scene_id"]))
            seen_shapes.add(row["shape"])
        if len(chosen) == 6:
            break
    display_methods = ["learned_r109_e48", "oracle_width_only", "oracle_shift_only",
                       "oracle_width_shift_dense", "oracle_width_shift_smooth",
                       "oracle_smooth_plus_bounded_detail"]
    columns = ["raw", "target", *display_methods]
    fig, axes = plt.subplots(len(chosen), len(columns), figsize=(2.25 * len(columns), 2.25 * len(chosen)), squeeze=False)
    lookup = {(row["scene_id"], row["method"]): row for row in metric_rows}
    for r, scene_index in enumerate(chosen):
        scene = scenes[scene_index]
        for c, column in enumerate(columns):
            ax = axes[r, c]
            image = scene[column] if column in {"raw", "target"} else outputs[column][scene_index]
            ax.imshow(image, cmap="gray", vmin=0, vmax=1, interpolation="nearest")
            if r == 0:
                ax.set_title(column.replace("oracle_", "").replace("_", "\n"), fontsize=8)
            if c == 0:
                ax.set_ylabel(f"{scene['shape']}\n{scene['degradation']}\n{'bright' if scene['polarity'] > 0 else 'dark'}", fontsize=8)
            if column not in {"raw", "target"}:
                row = lookup[(scene["scene_id"], column)]
                ax.text(.02, .02, f"A={float(row['assd_px']):.2f} I={float(row['iou']):.3f}",
                        transform=ax.transAxes, color="yellow", fontsize=6,
                        bbox={"facecolor": "black", "alpha": .55, "pad": 1})
            ax.set_xticks([]); ax.set_yticks([])
    fig.suptitle("R109 renderer expressivity: hardest smooth-control cases (A=ASSD px, I=IoU)")
    fig.tight_layout(rect=(0, 0, 1, .985))
    fig.savefig(out_dir / "worst_case_visual_panel.png", dpi=180)
    plt.close(fig)

    figure_metrics = [("assd_px", "ASSD median / p95 (px)", "lower"),
                      ("iou", "IoU mean / worst", "higher"),
                      ("boundary_mae_gray", "Boundary MAE mean / p95 (gray)", "lower"),
                      ("high_frequency_rmse_gray", "HF RMSE mean / p95 (gray)", "lower")]
    fig, axes = plt.subplots(2, 2, figsize=(14, 9))
    short = [m.replace("oracle_", "o-").replace("width_shift", "w+s").replace("learned_r109_e48", "learned") for m in methods]
    x = np.arange(len(methods))
    for ax, (metric, title, direction) in zip(axes.ravel(), figure_metrics):
        values = []
        secondary = []
        for method in methods:
            data = summary[method]["metrics"][metric]
            values.append(data["median"] if metric == "assd_px" else data["mean"])
            secondary.append(data["p95"] if direction == "lower" else data["min"])
        ax.bar(x - .18, values, .36, label="median" if metric == "assd_px" else "mean")
        ax.bar(x + .18, secondary, .36, label="p95" if direction == "lower" else "worst")
        ax.set_title(title); ax.set_xticks(x); ax.set_xticklabels(short, rotation=32, ha="right", fontsize=7)
        ax.grid(axis="y", alpha=.25); ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(out_dir / "method_summary.png", dpi=180)
    plt.close(fig)


def build_decision(rows: list[dict], summary: dict, scenes: list[dict], invariance: dict) -> dict:
    lookup = defaultdict(dict)
    for row in rows:
        lookup[row["scene_id"]][row["method"]] = row
    learned = summary["learned_r109_e48"]["metrics"]
    dense = summary["oracle_width_shift_dense"]["metrics"]
    smooth = summary["oracle_width_shift_smooth"]["metrics"]
    detail = summary["oracle_smooth_plus_bounded_detail"]["metrics"]
    learned_assd = learned["assd_px"]["median"]
    dense_assd = dense["assd_px"]["median"]
    learned_gap_absolute_px = learned_assd - dense_assd
    learned_gap_percent = 100 * (learned_assd - dense_assd) / max(learned_assd, 1e-8)
    detail_hf_gain = 100 * (smooth["high_frequency_rmse_gray"]["mean"]
                            - detail["high_frequency_rmse_gray"]["mean"]) / max(
                                smooth["high_frequency_rmse_gray"]["mean"], 1e-8)
    limited = []
    control_gap = []
    width_wins = shift_wins = 0
    for scene in scenes:
        data = lookup[scene["scene_id"]]
        if float(data["oracle_width_only"]["assd_px"]) < float(data["oracle_shift_only"]["assd_px"]):
            width_wins += 1
        else:
            shift_wins += 1
        if float(data["oracle_width_shift_dense"]["assd_px"]) > 1.0 or float(data["oracle_width_shift_dense"]["iou"]) < .92:
            limited.append({
                "scene_id": scene["scene_id"], "shape": scene["shape"], "degradation": scene["degradation"],
                "assd_px": float(data["oracle_width_shift_dense"]["assd_px"]),
                "iou": float(data["oracle_width_shift_dense"]["iou"]),
            })
        lvalue = float(data["learned_r109_e48"]["assd_px"])
        dvalue = float(data["oracle_width_shift_dense"]["assd_px"])
        if lvalue > 0 and (lvalue - dvalue) / lvalue > .25:
            control_gap.append({"scene_id": scene["scene_id"], "learned_assd_px": lvalue,
                                "oracle_dense_assd_px": dvalue, "relative_improvement_percent": 100 * (lvalue - dvalue) / lvalue})
    limited.sort(key=lambda item: item["assd_px"], reverse=True)
    control_gap.sort(key=lambda item: item["relative_improvement_percent"], reverse=True)
    hard_fraction = len(limited) / max(len(scenes), 1)
    # Universal deployment is worst-case-first.  A very large relative gain
    # from 0.09 px to 0.006 px is not allowed to hide a 3.24 px oracle failure.
    if len(limited) > 0 and dense["assd_px"]["max"] > 1.0:
        primary_limit = "renderer_capacity_primary_for_hard_cases_controls_secondary"
        go_no_go = ("NO-GO for control-only retraining: the current renderer still fails known-truth hard cases "
                    "even with dense oracle controls; test a bounded detail/geometry extension first.")
    elif learned_gap_absolute_px > .25 and hard_fraction <= .25:
        primary_limit = "learned_controls_primary"
        go_no_go = "GO: test a control-estimation/training repair before changing the renderer."
    elif hard_fraction >= .40 or dense_assd > 1.0:
        primary_limit = "renderer_capacity_primary"
        go_no_go = "NO-GO for control-only retraining: extend the renderer representation first."
    else:
        primary_limit = "mixed_control_and_renderer_limits"
        go_no_go = "NO-GO for a large training run: first test a minimal renderer extension plus control repair."
    smooth_invariance = invariance["oracle_width_shift_smooth"]
    if smooth_invariance["collapse_warning"]:
        go_no_go += " The smooth-control arm also risks shape collapse and cannot be promoted as-is."
    return {
        "question": "Can the current R109 renderer express the desired known-truth reconstruction if controls are perfect?",
        "learned_to_dense_oracle_median_assd_improvement_percent": learned_gap_percent,
        "learned_to_dense_oracle_median_assd_improvement_absolute_px": learned_gap_absolute_px,
        "smooth_to_bounded_detail_mean_hf_rmse_improvement_percent": detail_hf_gain,
        "dense_oracle_median_assd_px": dense_assd,
        "dense_oracle_worst_assd_px": dense["assd_px"]["max"],
        "dense_oracle_worst_iou": dense["iou"]["min"],
        "smooth_oracle_median_assd_px": smooth["assd_px"]["median"],
        "smooth_oracle_worst_assd_px": smooth["assd_px"]["max"],
        "single_control_scene_wins": {"width_only": width_wins, "shift_only": shift_wins},
        "renderer_limited_case_count": len(limited),
        "renderer_limited_cases": limited,
        "learned_control_gap_case_count": len(control_gap),
        "largest_learned_control_gaps": control_gap[:10],
        "interpretation": {
            "learned_controls": ("A material learned-to-oracle gap means current training/control prediction leaves usable renderer capacity untapped."
                                 if learned_gap_percent > 20 else
                                 "The learned-to-oracle contour gap is small; renderer capacity is the more likely bottleneck."),
            "renderer": ("The dense truth-optimized renderer still has hard cases, so width/normal-shift remapping is not universally expressive."
                         if limited else "The dense truth-optimized renderer met the predeclared descriptive limits on every synthetic case."),
            "detail_branch": ("A bounded zero-local-mean detail path closes a material high-frequency gap without changing the renderer controls."
                              if detail_hf_gain > 10 else "The bounded detail oracle provides little additional high-frequency capacity."),
        },
        "primary_limit": primary_limit,
        "go_no_go": go_no_go,
        "paired_condition_guardrail": {
            "smooth_same_latent_condition_assd_mean_px": smooth_invariance["same_latent_condition_assd_mean_px"],
            "smooth_shape_retention_ratio": smooth_invariance["shape_retention_ratio"],
            "smooth_shape_distance_spearman": smooth_invariance["truth_vs_reconstruction_shape_distance_spearman"],
            "smooth_collapse_warning": smooth_invariance["collapse_warning"],
        },
        "guardrail": "Oracle methods see target truth. They diagnose representation capacity only and are not achievable deployment results.",
    }


def run(config_path: Path, out_dir: Path, subset: int | None = None, save_artifacts: bool = True) -> dict:
    config = json.loads(config_path.read_text(encoding="utf-8"))
    seed_everything(int(config["seed"]))
    scenes = build_scenes(config)
    if subset is not None:
        scenes = scenes[:subset]
    checkpoint = Path(config["source"]["r109_checkpoint"])
    actual_hash = sha256_file(checkpoint)
    if actual_hash.lower() != config["source"]["r109_checkpoint_sha256"].lower():
        raise RuntimeError(f"Frozen checkpoint hash mismatch: {actual_hash}")
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    raw = torch.from_numpy(np.stack([scene["raw"] for scene in scenes])[:, None]).to(device)
    target = torch.from_numpy(np.stack([scene["target"] for scene in scenes])[:, None]).to(device)
    mask = torch.from_numpy(np.stack([scene["mask"] for scene in scenes])[:, None]).to(device)
    polarity = torch.tensor([scene["polarity"] for scene in scenes], dtype=torch.float32, device=device)[:, None, None, None]
    context = renderer_context(raw, mask, config["r109_contract"])
    outputs_t = {"identity": raw.detach()}
    controls = {"identity": (None, None)}
    histories = {}
    learned, learned_width, learned_shift, learned_support = load_learned_r109(raw, config)
    outputs_t["learned_r109_e48"] = learned.detach()
    controls["learned_r109_e48"] = (learned_width.detach(), learned_shift.detach())
    for variant in ("oracle_global_width_shift", "oracle_width_only", "oracle_shift_only",
                    "oracle_width_shift_dense", "oracle_width_shift_smooth"):
        output, width, shift, history = optimize_variant(raw, target, mask, polarity, context, variant, config)
        outputs_t[variant] = output
        controls[variant] = (width, shift)
        histories[variant] = history
    detail_output, detail = bounded_detail_oracle(outputs_t["oracle_width_shift_smooth"], target, mask, context, config)
    outputs_t["oracle_smooth_plus_bounded_detail"] = detail_output.detach()
    controls["oracle_smooth_plus_bounded_detail"] = controls["oracle_width_shift_smooth"]
    methods = list(config["methods"])
    outputs = {name: outputs_t[name].detach().cpu().numpy()[:, 0].astype(np.float32) for name in methods}
    support = context["support"].detach().cpu().numpy().astype(np.float32)
    learned_support_np = learned_support.detach().cpu().numpy().astype(np.float32)
    metric_rows, control_rows = [], []
    for index, scene in enumerate(scenes):
        for method in methods:
            row = {
                "scene_id": scene["scene_id"], "shape": scene["shape"], "rep": scene["rep"],
                "latent_shape_id": scene["latent_shape_id"],
                "degradation": scene["degradation"], "polarity": scene["polarity"],
                "polarity_name": "bright" if scene["polarity"] > 0 else "dark",
                "texture": scene["texture"], "method": method,
            }
            row.update(evaluate_image(outputs[method][index], scene["target"], scene["mask"], scene["polarity"], config))
            metric_rows.append(row)
            width_t, shift_t = controls[method]
            width_np = width_t.detach().cpu().numpy() if width_t is not None else None
            shift_np = shift_t.detach().cpu().numpy() if shift_t is not None else None
            support_for_stats = learned_support_np if method == "learned_r109_e48" else support
            control_row = {"scene_id": scene["scene_id"], "method": method}
            control_row.update(control_statistics(width_np, shift_np, support_for_stats, index))
            if method == "oracle_smooth_plus_bounded_detail":
                detail_np = detail.detach().cpu().numpy()[index, 0]
                control_row["detail_abs_mean_gray"] = float(np.mean(np.abs(detail_np)) * 255)
                control_row["detail_abs_p95_gray"] = float(np.percentile(np.abs(detail_np), 95) * 255)
            else:
                control_row["detail_abs_mean_gray"] = float("nan")
                control_row["detail_abs_p95_gray"] = float("nan")
            control_rows.append(control_row)
    summary = aggregate_metrics(metric_rows, methods)
    condition_pairs, condition_invariance = analyze_condition_invariance(scenes, methods, outputs)
    decision = build_decision(metric_rows, summary, scenes, condition_invariance)
    arrays = {
        "raw": raw.detach().cpu().numpy()[:, 0].astype(np.float32),
        "target": target.detach().cpu().numpy()[:, 0].astype(np.float32),
        "mask": mask.detach().cpu().numpy()[:, 0].astype(np.float32),
        "support": support[:, 0],
        "detail_oracle": detail.detach().cpu().numpy()[:, 0].astype(np.float32),
    }
    for method in methods:
        arrays[f"output__{method}"] = outputs[method]
    if save_artifacts:
        out_dir.mkdir(parents=True, exist_ok=True)
        manifest_rows = []
        for scene in scenes:
            manifest_rows.append({
                "scene_id": scene["scene_id"], "shape": scene["shape"], "rep": scene["rep"],
                "latent_shape_id": scene["latent_shape_id"],
                "seed": scene["seed"], "degradation": scene["degradation"], "polarity": scene["polarity"],
                "texture": scene["texture"], "raw_sha256": sha256_array(scene["raw"]),
                "target_sha256": sha256_array(scene["target"]), "mask_sha256": sha256_array(scene["mask"]),
            })
        write_csv(out_dir / "scene_manifest.csv", manifest_rows)
        write_csv(out_dir / "per_scene_metrics.csv", metric_rows)
        write_csv(out_dir / "control_statistics.csv", control_rows)
        write_csv(out_dir / "paired_condition_metrics.csv", condition_pairs)
        strata = stratified_metrics(metric_rows, methods)
        write_csv(out_dir / "stratified_metrics.csv", strata)
        (out_dir / "analysis_summary.json").write_text(json.dumps({
            "experiment": config["experiment"], "device": str(device), "scene_count": len(scenes),
            "method_count": len(methods), "checkpoint_sha256": actual_hash,
            "config_sha256": sha256_file(config_path), "summary": summary,
            "condition_invariance": condition_invariance,
        }, indent=2, ensure_ascii=False), encoding="utf-8")
        (out_dir / "upper_bound_decision.json").write_text(json.dumps(decision, indent=2, ensure_ascii=False), encoding="utf-8")
        (out_dir / "optimization_history.json").write_text(json.dumps(histories, indent=2), encoding="utf-8")
        np.savez_compressed(out_dir / "experiment_arrays.npz", **arrays)
        save_visuals(out_dir, scenes, methods, outputs, metric_rows, summary)
        lines = [
            "# R109 Renderer Expressivity Upper Bound", "",
            "This is a deterministic no-training representation test. Oracle controls see target truth; they are not deployment results.", "",
            f"- Scenes: {len(scenes)} ({len(config['shape_families'])} shape families; bright and dark polarity; supersampled labels)",
            f"- Learned R109 median ASSD: {summary['learned_r109_e48']['metrics']['assd_px']['median']:.4f} px",
            f"- Dense truth-optimized median / worst ASSD: {decision['dense_oracle_median_assd_px']:.4f} / {decision['dense_oracle_worst_assd_px']:.4f} px",
            f"- Smooth truth-optimized median / worst ASSD: {decision['smooth_oracle_median_assd_px']:.4f} / {decision['smooth_oracle_worst_assd_px']:.4f} px",
            f"- Learned-to-dense median ASSD improvement: {decision['learned_to_dense_oracle_median_assd_improvement_percent']:.2f}%",
            f"- Smooth-to-bounded-detail HF RMSE improvement: {decision['smooth_to_bounded_detail_mean_hf_rmse_improvement_percent']:.2f}%",
            f"- Dense-oracle hard cases (ASSD > 1 px or IoU < .92): {decision['renderer_limited_case_count']}/{len(scenes)}",
            f"- Smooth-control same-shape condition ASSD: {decision['paired_condition_guardrail']['smooth_same_latent_condition_assd_mean_px']:.4f} px",
            f"- Smooth-control shape retention ratio: {decision['paired_condition_guardrail']['smooth_shape_retention_ratio']:.4f}",
            f"- Primary limit: {decision['primary_limit']}",
            f"- Go / no-go: {decision['go_no_go']}",
            "", "## Interpretation", "",
            f"- Learned controls: {decision['interpretation']['learned_controls']}",
            f"- Renderer: {decision['interpretation']['renderer']}",
            f"- Detail path: {decision['interpretation']['detail_branch']}",
            "", "External GMF is deliberately absent. This experiment asks what the renderer can physically express against known truth.",
        ]
        (out_dir / "FINDINGS.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return {"config": config, "scenes": scenes, "outputs": outputs, "arrays": arrays,
            "metrics": metric_rows, "summary": summary, "condition_invariance": condition_invariance,
            "decision": decision}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--subset", type=int)
    parser.add_argument("--no-artifacts", action="store_true")
    args = parser.parse_args()
    result = run(args.config.resolve(), args.output.resolve(), args.subset, not args.no_artifacts)
    print(json.dumps({
        "status": "complete", "scene_count": len(result["scenes"]),
        "learned_median_assd_px": result["summary"]["learned_r109_e48"]["metrics"]["assd_px"]["median"],
        "dense_oracle_median_assd_px": result["decision"]["dense_oracle_median_assd_px"],
        "dense_oracle_hard_cases": result["decision"]["renderer_limited_case_count"],
    }, indent=2))


if __name__ == "__main__":
    main()

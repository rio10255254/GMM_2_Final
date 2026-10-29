"""Train and falsify a contour-conserving local profile renderer from scratch."""
from __future__ import annotations

import hashlib
import importlib.util
import json
import math
import random
import sys
from pathlib import Path

import cv2
import numpy as np
import pandas as pd
import torch
import torch.nn.functional as F
from torch import nn
PROJECT_ROOT = Path(__file__).resolve().parents[3]


ROOT = Path(__file__).resolve().parents[1]
DATA, WEIGHTS, RESULTS, REPORTS = (ROOT / name for name in ("data", "weights", "results", "reports"))
for folder in (DATA, WEIGHTS, RESULTS, REPORTS):
    folder.mkdir(parents=True, exist_ok=True)
BASE = Path(str(PROJECT_ROOT / 'Experiments/R108B_StagedParallelOpticalExpertsMicroprobe/data/microprobe_data.npz'))
BASE_SHA = "e01a97bc2b361195d550a6f3c5262e354b2424f8676ae9045c6abed765d39185"
R108D_CORE = Path(str(PROJECT_ROOT / 'Experiments/R108D_MultiscaleNormalGeometryMicroprobe/scripts/run_probe.py'))
R108D_WEIGHT = Path(str(PROJECT_ROOT / 'Experiments/R108D_MultiscaleNormalGeometryMicroprobe/weights/multiscale_normal_geometry.pth'))
R108C_CORE = Path(str(PROJECT_ROOT / 'Experiments/R108C_IndependentOpticalSpecialistsMicroprobe/scripts/run_specialists.py'))
R108C_WEIGHT = Path(str(PROJECT_ROOT / 'Experiments/R108C_IndependentOpticalSpecialistsMicroprobe/weights/edge.pth'))
DEVICE = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")
CHALLENGES = ("identity", "low_contrast", "uneven_illumination", "asymmetric_blur_halo", "boundary_fade", "mixed_hard")
REAL_IMAGES = (
    Path(str(PROJECT_ROOT / 'Experiments/R100_CausalOperatorScratch/data/live_validation/5x_dense_raw.bmp')),
    Path(str(PROJECT_ROOT / 'Experiments/R100_CausalOperatorScratch/data/live_validation/20x_mixed_raw.bmp')),
    Path(str(PROJECT_ROOT / 'Experiments/R100_CausalOperatorScratch/data/live_validation/50x_array_raw.bmp')),
    Path(str(PROJECT_ROOT / 'Experiments/R100_CausalOperatorScratch/data/live_validation/pillar_center9_50x_raw.bmp')),
)
SEM_ROOT = Path(str(PROJECT_ROOT / 'Experiments/R69_ACMContourSEMValidation/inputs/sem_paired_50x_exposure_stack'))


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


dcore = load_module("r108e_r108d_utilities", R108D_CORE)


def seed_all(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def low_field(rng: np.random.Generator, side: int, amplitude: float) -> np.ndarray:
    coarse = rng.normal(0, 1, (7, 7)).astype(np.float32)
    field = cv2.resize(coarse, (side, side), interpolation=cv2.INTER_CUBIC)
    field = cv2.GaussianBlur(field, (0, 0), side / 14.0)
    field -= float(field.mean())
    return field * (amplitude / max(float(field.std()), 1e-6))


def motion_kernel(length: int, angle: float) -> np.ndarray:
    length = max(1, int(length) | 1)
    kernel = np.zeros((length, length), np.float32)
    kernel[length // 2, :] = 1.0
    matrix = cv2.getRotationMatrix2D((length / 2 - 0.5, length / 2 - 0.5), angle, 1.0)
    kernel = cv2.warpAffine(kernel, matrix, (length, length), flags=cv2.INTER_LINEAR)
    return kernel / max(float(kernel.sum()), 1e-8)


def angular_wedge(mask: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    side = mask.shape[0]
    yy, xx = np.mgrid[0:side, 0:side].astype(np.float32)
    ys, xs = np.nonzero(mask > 0.5)
    cx, cy = (float(xs.mean()), float(ys.mean())) if len(xs) else (side / 2, side / 2)
    angle = np.arctan2(yy - cy, xx - cx)
    center = float(rng.uniform(-np.pi, np.pi))
    width = float(rng.uniform(0.25, 0.75))
    distance = np.abs(np.angle(np.exp(1j * (angle - center))))
    return np.exp(-(distance**2) / (2 * width**2)).astype(np.float32)


def render(target: np.ndarray, mask: np.ndarray, challenge: str, rng: np.random.Generator, severe: bool) -> np.ndarray:
    if challenge == "identity":
        return target.copy()
    side = target.shape[0]
    image = target.copy()
    background = float(np.median(target[mask < 0.10])) if np.any(mask < 0.10) else float(target.mean())
    midpoint = float(np.median(target))
    contrast_scale = float(rng.uniform(0.38, 0.72) if severe else rng.uniform(0.50, 0.88))
    if challenge in {"low_contrast", "boundary_fade", "mixed_hard"}:
        image = midpoint + contrast_scale * (image - midpoint)
    if challenge in {"boundary_fade", "mixed_hard"}:
        strength = float(rng.uniform(0.58, 0.90) if severe else rng.uniform(0.38, 0.78))
        wedge = angular_wedge(mask, rng) * mask
        image = image * (1.0 - strength * wedge) + background * (strength * wedge)
        boundary = cv2.morphologyEx((mask > 0.5).astype(np.uint8), cv2.MORPH_GRADIENT, np.ones((7, 7), np.uint8)) > 0
        ys, xs = np.nonzero(boundary)
        for _ in range(int(rng.integers(3, 9))):
            pick = int(rng.integers(0, len(xs)))
            cv2.circle(image, (int(xs[pick]), int(ys[pick])), int(rng.integers(2, 7)), background + float(rng.uniform(-0.04, 0.04)), -1)
    if challenge in {"uneven_illumination", "mixed_hard"}:
        image += low_field(rng, side, float(rng.uniform(0.05, 0.14) if severe else rng.uniform(0.025, 0.10)))
    blur = float(rng.uniform(3.8, 6.8) if severe else rng.uniform(1.2, 4.8))
    image = cv2.GaussianBlur(image.astype(np.float32), (0, 0), blur, borderType=cv2.BORDER_REFLECT_101)
    if challenge in {"asymmetric_blur_halo", "mixed_hard"}:
        length = int(rng.choice((11, 15, 19, 23)) if severe else rng.choice((5, 9, 13, 17)))
        image = cv2.filter2D(image, cv2.CV_32F, motion_kernel(length, float(rng.uniform(-180, 180))), borderType=cv2.BORDER_REFLECT_101)
        halo = float(rng.uniform(0.35, 0.72) if severe else rng.uniform(0.18, 0.58))
        broad = cv2.GaussianBlur(image, (0, 0), float(rng.uniform(3.0, 6.5)), borderType=cv2.BORDER_REFLECT_101)
        image = image + halo * (broad - image)
    noise = float(rng.uniform(0.018, 0.040) if severe else rng.uniform(0.006, 0.030))
    image += rng.normal(0, noise, image.shape).astype(np.float32)
    return np.clip(image, 0.0, 1.0)


def build_data() -> dict[str, dict[str, np.ndarray]]:
    path = DATA / "profile_renderer_data.npz"
    keys = ("source", "target", "mask", "edge", "midpoint", "polarity", "identity", "family", "challenge")
    if path.exists():
        loaded = np.load(path, allow_pickle=False)
        return {split: {key: loaded[f"{split}_{key}"] for key in keys} for split in ("train", "validation", "holdout")}
    if not BASE.exists() or sha256(BASE) != BASE_SHA:
        raise RuntimeError("Verified generic target package changed")
    base = np.load(BASE, allow_pickle=False)
    result, payload = {}, {}
    for split_index, split in enumerate(("train", "validation", "holdout")):
        rng = np.random.default_rng(109020 + split_index)
        variants = 2
        rows = {key: [] for key in keys}
        count = len(base[f"{split}_target"])
        for index in range(count):
            target = base[f"{split}_target"][index].astype(np.float32) / 255.0
            mask = base[f"{split}_mask"][index].astype(np.float32) / 255.0
            for variant in range(variants):
                challenge = CHALLENGES[(index * variants + variant) % len(CHALLENGES)]
                source = render(target, mask, challenge, rng, split == "holdout")
                rows["source"].append(np.round(source * 255.0).astype(np.uint8))
                for key in ("target", "mask", "edge"):
                    rows[key].append(base[f"{split}_{key}"][index])
                for key in ("midpoint", "polarity", "family"):
                    rows[key].append(base[f"{split}_{key}"][index])
                rows["identity"].append(challenge == "identity")
                rows["challenge"].append(challenge)
        data = {key: np.asarray(value) for key, value in rows.items()}
        result[split] = data
        for key, value in data.items():
            payload[f"{split}_{key}"] = value
    np.savez_compressed(path, **payload)
    manifest = {
        "status": "complete",
        "source": str(BASE),
        "source_sha256": BASE_SHA,
        "counts": {split: len(data["source"]) for split, data in result.items()},
        "challenges": list(CHALLENGES),
        "target_generation": "verified 4x supersampled generic shapes",
        "real_or_sem_training_pixels": False,
        "old_weight_or_teacher_used_for_training": False,
        "sha256": sha256(path),
    }
    (DATA / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return result


class ContourProfileRenderer(nn.Module):
    def __init__(self):
        super().__init__()
        self.blurs = nn.ModuleList([dcore.Blur(sigma) for sigma in (0.8, 1.6, 3.2, 6.4)])
        self.context = dcore.Blur(6.4)
        channels = 48
        self.detector_stem = nn.Conv2d(15, channels, 3, padding=1)
        self.detector_tower = nn.Sequential(*[dcore.Residual(channels, dilation) for dilation in (1, 2, 4, 8, 8, 4, 2, 1)])
        self.renderer_stem = nn.Conv2d(15, channels, 3, padding=1)
        self.renderer_tower = nn.Sequential(*[dcore.Residual(channels, dilation) for dilation in (1, 2, 4, 8, 8, 4, 2, 1)])
        self.boundary_head = nn.Conv2d(channels, 1, 1)
        self.necessity_head = nn.Conv2d(channels, 1, 1)
        self.residual_head = nn.Conv2d(channels, 1, 1)
        nn.init.zeros_(self.boundary_head.weight)
        nn.init.constant_(self.boundary_head.bias, -2.0)
        nn.init.zeros_(self.necessity_head.weight)
        nn.init.constant_(self.necessity_head.bias, -1.0)
        nn.init.zeros_(self.residual_head.weight)
        nn.init.zeros_(self.residual_head.bias)

    def forward(self, x: torch.Tensor):
        blurred = [layer(x) for layer in self.blurs]
        highpasses = [x - value for value in blurred]
        gx, gy = dcore.gradients(x)
        magnitude = torch.sqrt(gx.square() + gy.square() + 1e-8)
        local_mean = blurred[-1]
        local_scale = torch.sqrt(self.context((x - local_mean).square()) + (2 / 255) ** 2)
        normalized = (x - local_mean) / (local_scale + 2 / 255)
        cues = torch.cat([x, *blurred, *highpasses, gx, gy, magnitude, local_mean, local_scale, normalized], dim=1)
        detector_features = self.detector_tower(F.silu(self.detector_stem(cues)))
        renderer_features = self.renderer_tower(F.silu(self.renderer_stem(cues)))
        boundary_logits = self.boundary_head(detector_features)
        boundary_probability = torch.sigmoid(boundary_logits)
        necessity = torch.sigmoid(self.necessity_head(detector_features))
        source_support = ((magnitude / (local_scale + 2 / 255) - 0.05) / 1.10).clamp(0.0, 1.0)
        predicted_support = F.max_pool2d(boundary_probability, 9, 1, 4)
        support = torch.maximum(source_support, 0.85 * predicted_support).clamp(0.0, 1.0)
        raw_delta = 0.35 * torch.tanh(self.residual_head(renderer_features))
        delta = support * necessity * raw_delta
        output = (x + delta).clamp(0.0, 1.0)
        return output, delta, boundary_logits, boundary_probability, necessity, support


def tensors(data: dict[str, np.ndarray]) -> dict[str, torch.Tensor]:
    result = {}
    for key in ("source", "target", "mask", "edge"):
        result[key] = torch.from_numpy(data[key].astype(np.float32) / 255.0).unsqueeze(1).to(DEVICE)
    for key in ("midpoint", "polarity"):
        result[key] = torch.from_numpy(data[key].astype(np.float32)).to(DEVICE)
    result["identity"] = torch.from_numpy(data["identity"]).to(DEVICE)
    return result


def weighted_mean(value: torch.Tensor, weight: torch.Tensor) -> torch.Tensor:
    return (value * weight).sum() / weight.sum().clamp_min(1e-8)


def soft_dice(prediction: torch.Tensor, target: torch.Tensor) -> torch.Tensor:
    numerator = 2.0 * (prediction * target).sum(dim=(1, 2, 3)) + 1e-6
    denominator = prediction.sum(dim=(1, 2, 3)) + target.sum(dim=(1, 2, 3)) + 1e-6
    return 1.0 - (numerator / denominator).mean()


def centroid_loss(prediction: torch.Tensor, target: torch.Tensor) -> torch.Tensor:
    height, width = prediction.shape[-2:]
    yy, xx = torch.meshgrid(
        torch.linspace(-1.0, 1.0, height, device=prediction.device),
        torch.linspace(-1.0, 1.0, width, device=prediction.device),
        indexing="ij",
    )
    xx, yy = xx.view(1, 1, height, width), yy.view(1, 1, height, width)
    pred_mass = prediction.sum(dim=(2, 3)).clamp_min(1e-6)
    target_mass = target.sum(dim=(2, 3)).clamp_min(1e-6)
    pred_x = (prediction * xx).sum(dim=(2, 3)) / pred_mass
    pred_y = (prediction * yy).sum(dim=(2, 3)) / pred_mass
    target_x = (target * xx).sum(dim=(2, 3)) / target_mass
    target_y = (target * yy).sum(dim=(2, 3)) / target_mass
    return (torch.abs(pred_x - target_x) + torch.abs(pred_y - target_y)).mean()


def balanced_need_loss(prediction: torch.Tensor, target: torch.Tensor) -> torch.Tensor:
    losses = []
    for selection in (target < 0.05, (target >= 0.05) & (target < 0.95), target >= 0.95):
        if bool(selection.any()):
            losses.append(F.smooth_l1_loss(prediction[selection], target[selection], beta=0.05))
    return torch.stack(losses).mean()


def train(model: ContourProfileRenderer, data: dict[str, torch.Tensor], steps: int = 2100):
    generator = torch.Generator(device=DEVICE).manual_seed(109011)
    trace = []
    clear_pool = torch.nonzero(data["identity"], as_tuple=False).flatten()
    degraded_pool = torch.nonzero(~data["identity"], as_tuple=False).flatten()

    def batch_indices() -> torch.Tensor:
        clear = clear_pool[torch.randint(0, len(clear_pool), (12,), generator=generator, device=DEVICE)]
        degraded = degraded_pool[torch.randint(0, len(degraded_pool), (12,), generator=generator, device=DEVICE)]
        return torch.cat([clear, degraded])

    detector_parameters = [
        *model.detector_stem.parameters(),
        *model.detector_tower.parameters(),
        *model.boundary_head.parameters(),
        *model.necessity_head.parameters(),
    ]
    detector_optimizer = torch.optim.AdamW(detector_parameters, lr=3.5e-4, weight_decay=1e-5)
    detector_steps = 900
    for step in range(1, detector_steps + 1):
        index = batch_indices()
        source, target, edge = (data[key][index] for key in ("source", "target", "edge"))
        identity = data["identity"][index]
        _, _, boundary_logits, boundary_probability, necessity, support = model(source)
        boundary_target = F.max_pool2d(edge, 5, 1, 2).clamp(0.0, 1.0)
        local_need = F.avg_pool2d(torch.abs(target - source), 9, 1, 4)
        need_target = ((local_need - 0.5 / 255.0) / (5.0 / 255.0)).clamp(0.0, 1.0)
        need_target = need_target * F.max_pool2d(boundary_target, 11, 1, 5)
        need_target[identity] = 0.0
        need_fraction = need_target.mean().detach().clamp(1e-4, 0.9999)
        need_weight = 1.0 + need_target * ((1.0 - need_fraction) / need_fraction)
        necessity_loss = F.binary_cross_entropy(
            necessity.clamp(1e-5, 1 - 1e-5), need_target, weight=need_weight
        ) + 0.35 * balanced_need_loss(necessity, need_target)
        positive_weight = (1.0 - boundary_target.mean()).detach() / boundary_target.mean().clamp_min(1e-4).detach()
        boundary_bce = F.binary_cross_entropy_with_logits(boundary_logits, boundary_target, pos_weight=positive_weight)
        boundary_dice = soft_dice(boundary_probability, boundary_target)
        loss = 0.45 * boundary_bce + 0.30 * boundary_dice + necessity_loss
        detector_optimizer.zero_grad(set_to_none=True)
        loss.backward()
        norm = torch.nn.utils.clip_grad_norm_(detector_parameters, 5.0)
        detector_optimizer.step()
        if not torch.isfinite(loss) or not torch.isfinite(norm):
            raise FloatingPointError(f"detector {step}")
        if step == 1 or step % 100 == 0:
            row = {
                "phase": "detector",
                "step": step,
                "loss": float(loss.detach()),
                "boundary_dice": float(boundary_dice.detach()),
                "necessity": float(necessity_loss.detach()),
                "necessity_mean": float(necessity.mean().detach()),
                "necessity_target_mean": float(need_target.mean().detach()),
                "identity_necessity": float(necessity[identity].mean().detach()),
                "degraded_necessity": float(necessity[~identity].mean().detach()),
                "support_mean": float(support.mean().detach()),
            }
            trace.append(row)
            print(json.dumps(row), flush=True)

    with torch.inference_mode():
        scene_need = []
        for start in range(0, len(data["source"]), 24):
            necessity = model(data["source"][start:start + 24])[4]
            scene_need.append(necessity.mean(dim=(1, 2, 3)).cpu())
        scene_need_tensor = torch.cat(scene_need)
        identity_cpu = data["identity"].cpu()
        detector_audit = {
            "identity_mean": float(scene_need_tensor[identity_cpu].mean()),
            "degraded_mean": float(scene_need_tensor[~identity_cpu].mean()),
        }
    detector_audit["separation"] = detector_audit["degraded_mean"] - detector_audit["identity_mean"]
    print(json.dumps({"phase": "detector_audit", **detector_audit}), flush=True)
    if detector_audit["separation"] <= 0.02:
        (RESULTS / "detector_stage_failure.json").write_text(
            json.dumps({"status": "failed", **detector_audit}, indent=2), encoding="utf-8"
        )
        raise RuntimeError("Detector did not separate degraded from identity inputs")

    for parameter in detector_parameters:
        parameter.requires_grad_(False)
    renderer_parameters = [
        *model.renderer_stem.parameters(),
        *model.renderer_tower.parameters(),
        *model.residual_head.parameters(),
    ]
    renderer_optimizer = torch.optim.AdamW(renderer_parameters, lr=3.5e-4, weight_decay=1e-5)
    renderer_steps = steps - detector_steps
    for local_step in range(1, renderer_steps + 1):
        index = batch_indices()
        source, target, mask, edge = (data[key][index] for key in ("source", "target", "mask", "edge"))
        midpoint = data["midpoint"][index, None, None, None]
        polarity = data["polarity"][index, None, None, None]
        identity = data["identity"][index]
        output, delta, _, _, necessity, _ = model(source)
        boundary_target = F.max_pool2d(edge, 5, 1, 2).clamp(0.0, 1.0)
        soft_mask = torch.sigmoid(42.0 * polarity * (output - midpoint))
        contour_dice = soft_dice(soft_mask, mask)
        contour_bce = F.binary_cross_entropy(soft_mask.clamp(1e-5, 1 - 1e-5), mask)
        area = torch.abs(soft_mask.mean(dim=(1, 2, 3)) - mask.mean(dim=(1, 2, 3))).mean()
        centroid = centroid_loss(soft_mask, mask)
        band = 0.06 + 0.94 * boundary_target
        direct = weighted_mean(F.smooth_l1_loss(delta, target - source, beta=1 / 255, reduction="none"), band)
        image = weighted_mean(torch.abs(output - target), band)
        out_gx, out_gy = dcore.gradients(output)
        target_gx, target_gy = dcore.gradients(target)
        gradient = weighted_mean(torch.abs(out_gx - target_gx) + torch.abs(out_gy - target_gy), band)
        flat = weighted_mean(delta.abs(), (1.0 - F.max_pool2d(boundary_target, 9, 1, 4)).clamp_min(0.02))
        identity_action = delta[identity].abs().mean()
        loss = (
            0.60 * contour_dice
            + 0.12 * contour_bce
            + 0.22 * area
            + 0.16 * centroid
            + 0.90 * direct
            + 0.42 * image
            + 0.18 * gradient
            + 0.12 * flat
            + 1.50 * identity_action
        )
        renderer_optimizer.zero_grad(set_to_none=True)
        loss.backward()
        norm = torch.nn.utils.clip_grad_norm_(renderer_parameters, 5.0)
        renderer_optimizer.step()
        if not torch.isfinite(loss) or not torch.isfinite(norm):
            raise FloatingPointError(f"renderer {local_step}")
        if local_step == 1 or local_step % 100 == 0:
            row = {
                "phase": "renderer",
                "step": local_step,
                "global_step": detector_steps + local_step,
                "loss": float(loss.detach()),
                "contour_dice": float(contour_dice.detach()),
                "area": float(area.detach()),
                "centroid": float(centroid.detach()),
                "direct": float(direct.detach()),
                "action_gray": float(delta.abs().mean().detach() * 255.0),
                "identity_action_gray": float(identity_action.detach() * 255.0),
                "identity_necessity": float(necessity[identity].mean().detach()),
                "degraded_necessity": float(necessity[~identity].mean().detach()),
            }
            trace.append(row)
            print(json.dumps(row), flush=True)
    torch.save(
        {
            "model": model.state_dict(),
            "steps": steps,
            "detector_steps": detector_steps,
            "renderer_steps": renderer_steps,
            "seed": 109010,
        },
        WEIGHTS / "contour_profile_renderer.pth",
    )
    return trace, detector_audit


def load_comparators():
    ccore = load_module("r108e_r108c_comparator", R108C_CORE)
    old = ccore.EdgeExpert().to(DEVICE)
    old.load_state_dict(torch.load(R108C_WEIGHT, map_location=DEVICE, weights_only=False)["model"])
    old.eval()
    multiscale = dcore.MultiscaleNormalGeometry().to(DEVICE)
    multiscale.load_state_dict(torch.load(R108D_WEIGHT, map_location=DEVICE, weights_only=False)["model"])
    multiscale.eval()
    return old, multiscale


@torch.inference_mode()
def predict(model, source: torch.Tensor) -> np.ndarray:
    values = []
    for start in range(0, len(source), 24):
        values.append(model(source[start:start + 24])[0].cpu())
    return torch.cat(values).numpy()[:, 0]


def component_count(mask: np.ndarray) -> int:
    return max(0, cv2.connectedComponents(mask.astype(np.uint8), connectivity=8)[0] - 1)


def evaluate(name: str, output: np.ndarray, data: dict[str, np.ndarray]) -> dict[str, object]:
    source = data["source"].astype(np.float32) / 255.0
    target = data["target"].astype(np.float32) / 255.0
    edge = data["edge"].astype(np.float32) / 255.0
    raw_error, error = np.abs(source - target), np.abs(output - target)
    weight = 0.06 + 0.94 * edge
    midpoint = data["midpoint"][:, None, None]
    polarity = data["polarity"][:, None, None]
    truth = data["mask"] > 127
    predicted = np.where(polarity > 0, output > midpoint, output < midpoint)
    ious, centroids, topology = [], [], 0
    for prediction, truth_mask in zip(predicted, truth):
        intersection = np.logical_and(prediction, truth_mask).sum()
        union = np.logical_or(prediction, truth_mask).sum()
        ious.append(float(intersection / max(union, 1)))
        py, px = np.nonzero(prediction)
        ty, tx = np.nonzero(truth_mask)
        centroids.append(float(np.hypot((px.mean() if len(px) else 0) - tx.mean(), (py.mean() if len(py) else 0) - ty.mean())))
        topology += component_count(prediction) > component_count(truth_mask)
    identity = data["identity"]
    return {
        "name": name,
        "images": len(source),
        "raw_mae_gray": float(raw_error.mean() * 255.0),
        "model_mae_gray": float(error.mean() * 255.0),
        "raw_edge_mae_gray": float((raw_error * weight).sum() / weight.sum() * 255.0),
        "model_edge_mae_gray": float((error * weight).sum() / weight.sum() * 255.0),
        "improved_fraction": float(np.mean(error.reshape(len(error), -1).mean(1) < raw_error.reshape(len(raw_error), -1).mean(1))),
        "median_iou": float(np.median(ious)),
        "median_centroid_error_px": float(np.median(centroids)),
        "added_topology_failures": int(topology),
        "identity_change_gray": float(np.abs(output[identity] - source[identity]).mean() * 255.0),
        "output_change_gray": float(np.abs(output - source).mean() * 255.0),
    }


@torch.inference_mode()
def tiled(model, image: np.ndarray, core: int = 256, halo: int = 192) -> np.ndarray:
    tensor = torch.from_numpy(image[None, None]).to(DEVICE)
    height, width = image.shape
    padded = F.pad(tensor, (halo, halo, halo, halo), mode="reflect")
    output = torch.zeros_like(tensor)
    for y in range(0, height, core):
        for x in range(0, width, core):
            crop_h, crop_w = min(core, height - y), min(core, width - x)
            tile = padded[..., y:y + crop_h + 2 * halo, x:x + crop_w + 2 * halo]
            value = model(tile)[0]
            output[..., y:y + crop_h, x:x + crop_w] = value[..., halo:halo + crop_h, halo:halo + crop_w]
    return output[0, 0].cpu().numpy()


def appearance(raw: np.ndarray, output: np.ndarray) -> dict[str, float]:
    gx, gy = cv2.Sobel(raw, cv2.CV_32F, 1, 0, ksize=3), cv2.Sobel(raw, cv2.CV_32F, 0, 1, ksize=3)
    magnitude = np.hypot(gx, gy)
    support = magnitude >= np.quantile(magnitude, 0.90)
    gx2, gy2 = cv2.Sobel(output, cv2.CV_32F, 1, 0, ksize=3), cv2.Sobel(output, cv2.CV_32F, 0, 1, ksize=3)
    raw_detail, out_detail = raw - cv2.GaussianBlur(raw, (0, 0), 1.0), output - cv2.GaussianBlur(output, (0, 0), 1.0)
    return {
        "change_gray": float(np.mean(np.abs(output - raw)) * 255.0),
        "edge_gain": float(np.hypot(gx2, gy2)[support].mean() / max(float(magnitude[support].mean()), 1e-9)),
        "detail_ratio": float(np.mean(np.abs(out_detail)) / max(float(np.mean(np.abs(raw_detail))), 1e-9)),
    }


def real_and_sem(model) -> dict[str, object]:
    real_rows, previews = [], []
    for path in REAL_IMAGES:
        raw = dcore.read_gray(path)
        output = tiled(model, raw)
        dcore.write_gray(RESULTS / "real" / path.name, output)
        real_rows.append({"image": path.name, **appearance(raw, output)})
        previews.append(np.concatenate([cv2.resize(raw, (480, 360), interpolation=cv2.INTER_AREA), cv2.resize(output, (480, 360), interpolation=cv2.INTER_AREA)], axis=1))
    frame = pd.DataFrame(real_rows)
    frame.to_csv(RESULTS / "real_appearance.csv", index=False)
    cv2.imencode(".png", np.round(np.clip(np.concatenate(previews, axis=0), 0, 1) * 255).astype(np.uint8))[1].tofile(str(RESULTS / "real_comparison.png"))
    sem_rows = []
    for path in sorted(SEM_ROOT.glob("*.bmp")):
        raw = dcore.read_gray(path)
        output = tiled(model, raw)
        dcore.write_gray(RESULTS / "sem_reconstruction" / path.name, output)
        sem_rows.append({"exposure": int(path.stem), **appearance(raw, output)})
    sem = pd.DataFrame(sem_rows)
    sem.to_csv(RESULTS / "sem_appearance.csv", index=False)
    return {
        "real_median": {key: float(frame[key].median()) for key in ("change_gray", "edge_gain", "detail_ratio")},
        "sem_median": {key: float(sem[key].median()) for key in ("change_gray", "edge_gain", "detail_ratio")},
    }


@torch.inference_mode()
def tile_parity(model) -> dict[str, float]:
    generator = torch.Generator(device=DEVICE).manual_seed(109012)
    image = torch.rand((1, 1, 512, 512), generator=generator, device=DEVICE)
    full = model(image)[0]
    halo, core = 192, 128
    padded = F.pad(image, (halo, halo, halo, halo), mode="reflect")
    canvas = torch.zeros_like(image)
    for y in range(0, 512, core):
        for x in range(0, 512, core):
            value = model(padded[..., y:y + core + 2 * halo, x:x + core + 2 * halo])[0]
            canvas[..., y:y + core, x:x + core] = value[..., halo:halo + core, halo:halo + core]
    difference = torch.abs(full - canvas) * 255.0
    interior = difference[..., halo:-halo, halo:-halo]
    return {"interior_mean_gray": float(interior.mean()), "interior_p99_gray": float(torch.quantile(interior, 0.99)), "interior_max_gray": float(interior.max())}


def main() -> int:
    seed_all(109010)
    splits = build_data()
    model = ContourProfileRenderer().to(DEVICE)
    trace, detector_audit = train(model, tensors(splits["train"]), 2100)
    model.eval()
    old, multiscale = load_comparators()
    evaluations = {}
    for split in ("validation", "holdout"):
        source = torch.from_numpy(splits[split]["source"].astype(np.float32) / 255.0).unsqueeze(1).to(DEVICE)
        outputs = {
            "Raw": splits[split]["source"].astype(np.float32) / 255.0,
            "R108C_fixed_scale": predict(old, source),
            "R108D_multiscale": predict(multiscale, source),
            "R108E_contour_renderer": predict(model, source),
        }
        evaluations[split] = {name: evaluate(name, output, splits[split]) for name, output in outputs.items()}
        if split == "holdout":
            rows = []
            for challenge in CHALLENGES:
                selection = splits[split]["challenge"] == challenge
                subset = {key: value[selection] for key, value in splits[split].items()}
                rows.append({"challenge": challenge, **evaluate("R108E_contour_renderer", outputs["R108E_contour_renderer"][selection], subset)})
            pd.DataFrame(rows).to_csv(RESULTS / "holdout_by_challenge.csv", index=False)
    audit = real_and_sem(model)
    summary = {
        "status": "complete",
        "device": str(DEVICE),
        "training": {"steps": 2100, "detector_steps": 900, "renderer_steps": 1200, "seed": 109010, "detector_audit": detector_audit, "trace": trace},
        "data_manifest": json.loads((DATA / "manifest.json").read_text(encoding="utf-8")),
        "evaluations": evaluations,
        "tile_parity": tile_parity(model),
        "sealed_real_audit": audit,
        "formal_training_authorized": False,
    }
    (RESULTS / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

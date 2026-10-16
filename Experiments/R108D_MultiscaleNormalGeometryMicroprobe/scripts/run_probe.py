"""Train and falsify a tile-safe multiscale edge-profile and normal-shift specialist."""
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


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
WEIGHTS = ROOT / "weights"
RESULTS = ROOT / "results"
REPORTS = ROOT / "reports"
for folder in (DATA, WEIGHTS, RESULTS, REPORTS):
    folder.mkdir(parents=True, exist_ok=True)

BASE = Path(r"D:\GMM_2_Final\Experiments\R108B_StagedParallelOpticalExpertsMicroprobe\data\microprobe_data.npz")
BASE_SHA = "e01a97bc2b361195d550a6f3c5262e354b2424f8676ae9045c6abed765d39185"
R108C_ROOT = Path(r"D:\GMM_2_Final\Experiments\R108C_IndependentOpticalSpecialistsMicroprobe")
R108C_SCRIPT = R108C_ROOT / "scripts" / "run_specialists.py"
R108C_WEIGHT = R108C_ROOT / "weights" / "edge.pth"
DEVICE = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")
SCALES = (0.6, 1.2, 2.4, 4.8)
REAL_IMAGES = (
    Path(r"D:\GMM_2_Final\Experiments\R100_CausalOperatorScratch\data\live_validation\5x_dense_raw.bmp"),
    Path(r"D:\GMM_2_Final\Experiments\R100_CausalOperatorScratch\data\live_validation\20x_mixed_raw.bmp"),
    Path(r"D:\GMM_2_Final\Experiments\R100_CausalOperatorScratch\data\live_validation\50x_array_raw.bmp"),
    Path(r"D:\GMM_2_Final\Experiments\R100_CausalOperatorScratch\data\live_validation\pillar_center9_50x_raw.bmp"),
)
SEM_ROOT = Path(r"D:\GMM_2_Final\Experiments\R69_ACMContourSEMValidation\inputs\sem_paired_50x_exposure_stack")


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


def read_gray(path: Path) -> np.ndarray:
    value = cv2.imdecode(np.fromfile(str(path), np.uint8), cv2.IMREAD_GRAYSCALE)
    if value is None:
        raise RuntimeError(path)
    return value.astype(np.float32) / 255.0


def write_gray(path: Path, value: np.ndarray) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    ok, encoded = cv2.imencode(".bmp", np.round(np.clip(value, 0.0, 1.0) * 255.0).astype(np.uint8))
    if not ok:
        raise RuntimeError(path)
    encoded.tofile(str(path))


def make_psf(
    size: int,
    sigma_major: float,
    sigma_minor: float,
    angle: float,
    dx: float,
    dy: float,
    halo_weight: float,
    halo_dx: float,
    halo_dy: float,
) -> np.ndarray:
    axis = np.arange(size, dtype=np.float32) - (size - 1) / 2
    xx, yy = np.meshgrid(axis, axis)

    def component(offset_x: float, offset_y: float, sx: float, sy: float) -> np.ndarray:
        x = xx - offset_x
        y = yy - offset_y
        cosine, sine = math.cos(angle), math.sin(angle)
        xr = cosine * x + sine * y
        yr = -sine * x + cosine * y
        return np.exp(-0.5 * ((xr / sx) ** 2 + (yr / sy) ** 2))

    primary = component(dx, dy, sigma_major, sigma_minor)
    halo = component(dx + halo_dx, dy + halo_dy, sigma_major * 1.35, sigma_minor * 1.20)
    kernel = (1.0 - halo_weight) * primary + halo_weight * halo
    kernel /= max(float(kernel.sum()), 1e-12)
    return kernel.astype(np.float32)


def build_data() -> dict[str, dict[str, np.ndarray]]:
    path = DATA / "multiscale_geometry_data.npz"
    keys = ("source", "target", "mask", "edge", "midpoint", "polarity", "identity", "family", "sigma_major", "centroid_shift", "halo_weight")
    if path.exists():
        loaded = np.load(path, allow_pickle=False)
        return {split: {key: loaded[f"{split}_{key}"] for key in keys} for split in ("train", "validation", "holdout")}
    if not BASE.exists() or sha256(BASE) != BASE_SHA:
        raise RuntimeError("Verified R108B target package changed")
    loaded = np.load(BASE, allow_pickle=False)
    result = {}
    payload = {}
    for split_index, split in enumerate(("train", "validation", "holdout")):
        rng = np.random.default_rng(108920 + split_index)
        targets = loaded[f"{split}_target"].astype(np.float32) / 255.0
        count = len(targets)
        sources, identities, major_values, shifts, halos = [], [], [], [], []
        for index, target in enumerate(targets):
            identity = index % 5 == 0
            if identity:
                source = target.copy()
                sigma_major = 0.0
                shift = 0.0
                halo_weight = 0.0
            else:
                severe = split == "holdout"
                sigma_major = float(rng.uniform(2.8, 6.4) if severe else rng.uniform(0.55, 4.8))
                sigma_minor = float(rng.uniform(0.55, min(sigma_major, 3.2 if severe else 3.8)))
                angle = float(rng.uniform(-math.pi, math.pi))
                shift_limit = 2.4 if severe else 1.7
                dx, dy = (float(rng.uniform(-shift_limit, shift_limit)) for _ in range(2))
                shift = float(math.hypot(dx, dy))
                halo_weight = float(rng.uniform(0.12, 0.42) if severe else rng.uniform(0.0, 0.32))
                halo_limit = 3.8 if severe else 2.8
                halo_dx, halo_dy = (float(rng.uniform(-halo_limit, halo_limit)) for _ in range(2))
                kernel_size = 55 if severe else 45
                kernel = make_psf(kernel_size, sigma_major, sigma_minor, angle, dx, dy, halo_weight, halo_dx, halo_dy)
                source = cv2.filter2D(target, cv2.CV_32F, kernel, borderType=cv2.BORDER_REFLECT_101)
            sources.append(np.round(np.clip(source, 0.0, 1.0) * 255.0).astype(np.uint8))
            identities.append(identity)
            major_values.append(sigma_major)
            shifts.append(shift)
            halos.append(halo_weight)
        data = {
            "source": np.stack(sources),
            "target": loaded[f"{split}_target"],
            "mask": loaded[f"{split}_mask"],
            "edge": loaded[f"{split}_edge"],
            "midpoint": loaded[f"{split}_midpoint"],
            "polarity": loaded[f"{split}_polarity"],
            "identity": np.asarray(identities, np.bool_),
            "family": loaded[f"{split}_family"],
            "sigma_major": np.asarray(major_values, np.float32),
            "centroid_shift": np.asarray(shifts, np.float32),
            "halo_weight": np.asarray(halos, np.float32),
        }
        if len(data["source"]) != count:
            raise RuntimeError(split)
        result[split] = data
        for key, value in data.items():
            payload[f"{split}_{key}"] = value
    np.savez_compressed(path, **payload)
    manifest = {
        "status": "complete",
        "source": str(BASE),
        "source_sha256": BASE_SHA,
        "target_generation": "4x supersampled then INTER_AREA downsampled in verified source package",
        "degradation": "new anisotropic multiscale shifted PSFs with independent asymmetric halo",
        "counts": {split: len(data["source"]) for split, data in result.items()},
        "identity_fraction": {split: float(data["identity"].mean()) for split, data in result.items()},
        "real_training_pixels": False,
        "old_weight_or_teacher_used_for_training": False,
        "sha256": sha256(path),
    }
    (DATA / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return result


class Blur(nn.Module):
    def __init__(self, sigma: float):
        super().__init__()
        radius = max(1, int(math.ceil(3 * sigma)))
        axis = torch.arange(-radius, radius + 1, dtype=torch.float32)
        kernel = torch.exp(-0.5 * (axis / sigma) ** 2)
        kernel /= kernel.sum()
        self.register_buffer("horizontal", kernel.view(1, 1, 1, -1))
        self.register_buffer("vertical", kernel.view(1, 1, -1, 1))
        self.radius = radius

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        mode = "reflect" if min(x.shape[-2:]) > self.radius else "replicate"
        value = F.conv2d(F.pad(x, (self.radius, self.radius, 0, 0), mode=mode), self.horizontal.to(x.dtype))
        return F.conv2d(F.pad(value, (0, 0, self.radius, self.radius), mode=mode), self.vertical.to(x.dtype))


class Residual(nn.Module):
    def __init__(self, channels: int, dilation: int):
        super().__init__()
        self.first = nn.Conv2d(channels, channels, 3, padding=dilation, dilation=dilation)
        self.second = nn.Conv2d(channels, channels, 3, padding=dilation, dilation=dilation)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return F.silu(x + 0.15 * self.second(F.silu(self.first(x))))


def gradients(x: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
    gx = F.pad(x[..., 1:] - x[..., :-1], (0, 1, 0, 0))
    gy = F.pad(x[..., 1:, :] - x[..., :-1, :], (0, 0, 0, 1))
    return gx, gy


class MultiscaleNormalGeometry(nn.Module):
    def __init__(self):
        super().__init__()
        self.blurs = nn.ModuleList([Blur(sigma) for sigma in SCALES])
        self.context_blur = Blur(4.8)
        channels = 40
        self.stem = nn.Conv2d(13, channels, 3, padding=1)
        self.tower = nn.Sequential(*[Residual(channels, dilation) for dilation in (1, 2, 4, 8, 4, 2, 1)])
        self.head = nn.Conv2d(channels, 6, 1)
        nn.init.zeros_(self.head.weight)
        with torch.no_grad():
            self.head.bias[:4].copy_(torch.tensor((-1.10, -1.40, -1.65, -1.85)))
            self.head.bias[4:6].zero_()

    def forward(self, x: torch.Tensor):
        blurred = [layer(x) for layer in self.blurs]
        highpasses = [x - value for value in blurred]
        gx, gy = gradients(x)
        magnitude = torch.sqrt(gx.square() + gy.square() + 1e-8)
        local_scale = torch.sqrt(self.context_blur((x - blurred[-1]).square()) + (2 / 255) ** 2)
        support = ((magnitude / (local_scale + 2 / 255) - 0.08) / 1.25).clamp(0.0, 1.0)
        cues = torch.cat([x, *blurred, *highpasses, gx, gy, magnitude, local_scale], dim=1)
        logits = self.head(self.tower(F.silu(self.stem(cues))))
        scale_limits = x.new_tensor((1.4, 1.8, 2.2, 2.6)).view(1, 4, 1, 1)
        coefficients = torch.sigmoid(logits[:, :4]) * scale_limits
        shifts = 1.75 * torch.tanh(logits[:, 4:6])
        unsharp = sum(coefficients[:, index:index + 1] * highpasses[index] for index in range(4))
        normal_shift = shifts[:, :1] * gx + shifts[:, 1:2] * gy
        # No learned master gate is permitted in this probe.  The fixed local
        # edge support keeps the action local, while every basis coefficient is
        # supervised directly below.  This removes the zero-gate escape route.
        delta = support * (unsharp + normal_shift)
        output = (x + delta).clamp(0.0, 1.0)
        bases = torch.cat([*highpasses, gx, gy], dim=1)
        return output, delta, support, coefficients, shifts, bases


def tensors(data: dict[str, np.ndarray]) -> dict[str, torch.Tensor]:
    result = {}
    for key in ("source", "target", "edge"):
        result[key] = torch.from_numpy(data[key].astype(np.float32) / 255.0).unsqueeze(1).to(DEVICE)
    result["identity"] = torch.from_numpy(data["identity"]).to(DEVICE)
    return result


def weighted_mean(value: torch.Tensor, weight: torch.Tensor) -> torch.Tensor:
    return (value * weight).sum() / weight.sum().clamp_min(1e-8)


@torch.no_grad()
def oracle_actions(
    bases: torch.Tensor,
    desired: torch.Tensor,
    edge: torch.Tensor,
    support: torch.Tensor,
) -> tuple[torch.Tensor, torch.Tensor]:
    band = F.max_pool2d(edge, 11, 1, 5)
    coefficient_targets = []
    limits = desired.new_tensor((1.4, 1.8, 2.2, 2.6, 1.75, 1.75))
    for index in range(6):
        basis = bases[:, index:index + 1]
        numerator = F.avg_pool2d(basis * desired, 11, 1, 5)
        denominator = F.avg_pool2d(basis.square(), 11, 1, 5) + 1e-8
        value = numerator / denominator
        if index < 4:
            value = value.clamp(0.0, float(limits[index]))
        else:
            value = value.clamp(-float(limits[index]), float(limits[index]))
        coefficient_targets.append(value * band * support)
    target = torch.cat(coefficient_targets, dim=1)
    return target[:, :4], target[:, 4:]


def train(model: MultiscaleNormalGeometry, data: dict[str, torch.Tensor], steps: int = 1600):
    optimizer = torch.optim.AdamW(model.parameters(), lr=3.5e-4, weight_decay=1e-5)
    generator = torch.Generator(device=DEVICE).manual_seed(108911)
    trace = []
    batch_size = 24
    for step in range(1, steps + 1):
        index = torch.randint(0, len(data["source"]), (batch_size,), generator=generator, device=DEVICE)
        source, target, edge = data["source"][index], data["target"][index], data["edge"][index]
        identity = data["identity"][index]
        output, delta, support, coefficients, shifts, bases = model(source)
        desired = target - source
        band = (0.08 + 0.92 * edge).clamp_min(0.08)
        coefficient_target, shift_target = oracle_actions(bases, desired, edge, support)
        effective_coefficients = coefficients * support
        effective_shifts = shifts * support
        coefficient_loss = F.smooth_l1_loss(effective_coefficients, coefficient_target, beta=0.05)
        shift_loss = F.smooth_l1_loss(effective_shifts, shift_target, beta=0.05)
        direct = weighted_mean(F.smooth_l1_loss(delta, desired, beta=1 / 255, reduction="none"), band)
        image = weighted_mean(torch.abs(output - target), band)
        out_gx, out_gy = gradients(output)
        target_gx, target_gy = gradients(target)
        gradient = weighted_mean(torch.abs(out_gx - target_gx) + torch.abs(out_gy - target_gy), band)
        edge_dilated = F.max_pool2d(edge, 9, 1, 4)
        flat = weighted_mean(delta.abs(), (1.0 - edge_dilated).clamp_min(0.02))
        identity_loss = delta[identity].abs().mean() if bool(identity.any()) else delta.new_zeros(())
        action_regularizer = 0.0002 * (coefficients.mean() + shifts.abs().mean())
        loss = coefficient_loss + 0.45 * shift_loss + 0.75 * direct + 0.45 * image + 0.18 * gradient + 0.10 * flat + 0.70 * identity_loss + action_regularizer
        optimizer.zero_grad(set_to_none=True)
        loss.backward()
        norm = torch.nn.utils.clip_grad_norm_(model.parameters(), 5.0)
        optimizer.step()
        if not torch.isfinite(loss) or not torch.isfinite(norm):
            raise FloatingPointError(step)
        if step == 1 or step % 100 == 0:
            row = {
                "step": step,
                "loss": float(loss.detach()),
                "coefficient": float(coefficient_loss.detach()),
                "shift": float(shift_loss.detach()),
                "direct": float(direct.detach()),
                "edge_image": float(image.detach()),
                "gradient": float(gradient.detach()),
                "identity_action_gray": float(identity_loss.detach() * 255.0),
                "action_gray": float(delta.abs().mean().detach() * 255.0),
                "support_mean": float(support.mean().detach()),
                "normal_shift_mean_px": float(shifts.abs().mean().detach()),
            }
            trace.append(row)
            print(json.dumps(row), flush=True)
    torch.save({"model": model.state_dict(), "steps": steps, "seed": 108910, "scales": SCALES}, WEIGHTS / "multiscale_normal_geometry.pth")
    return trace


def load_old_comparator():
    spec = importlib.util.spec_from_file_location("r108c_edge_comparator", R108C_SCRIPT)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    assert spec.loader is not None
    spec.loader.exec_module(module)
    model = module.EdgeExpert().to(DEVICE)
    model.load_state_dict(torch.load(R108C_WEIGHT, map_location=DEVICE, weights_only=False)["model"])
    model.eval()
    return model


@torch.inference_mode()
def predict(model, source: torch.Tensor, old: bool = False) -> np.ndarray:
    values = []
    for start in range(0, len(source), 24):
        result = model(source[start:start + 24])[0]
        values.append(result.cpu())
    return torch.cat(values).numpy()[:, 0]


def component_count(mask: np.ndarray) -> int:
    return max(0, cv2.connectedComponents(mask.astype(np.uint8), connectivity=8)[0] - 1)


def evaluate(name: str, output: np.ndarray, data: dict[str, np.ndarray]) -> dict[str, object]:
    source = data["source"].astype(np.float32) / 255.0
    target = data["target"].astype(np.float32) / 255.0
    edge = data["edge"].astype(np.float32) / 255.0
    raw_error = np.abs(source - target)
    error = np.abs(output - target)
    weight = 0.08 + 0.92 * edge
    midpoint = data["midpoint"][:, None, None]
    polarity = data["polarity"][:, None, None]
    truth_mask = data["mask"] > 127
    predicted = np.where(polarity > 0, output > midpoint, output < midpoint)
    ious, centroids, topology = [], [], 0
    for prediction, truth in zip(predicted, truth_mask):
        intersection = np.logical_and(prediction, truth).sum()
        union = np.logical_or(prediction, truth).sum()
        ious.append(float(intersection / max(union, 1)))
        py, px = np.nonzero(prediction)
        ty, tx = np.nonzero(truth)
        centroids.append(float(np.hypot((px.mean() if len(px) else 0) - tx.mean(), (py.mean() if len(py) else 0) - ty.mean())))
        topology += component_count(prediction) > component_count(truth)
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
def tiled(model, image: np.ndarray, core: int = 256, halo: int = 128) -> np.ndarray:
    tensor = torch.from_numpy(image[None, None]).to(DEVICE)
    height, width = image.shape
    padded = F.pad(tensor, (halo, halo, halo, halo), mode="reflect")
    output = torch.zeros_like(tensor)
    for y in range(0, height, core):
        for x in range(0, width, core):
            crop_h = min(core, height - y)
            crop_w = min(core, width - x)
            tile = padded[..., y:y + crop_h + 2 * halo, x:x + crop_w + 2 * halo]
            value = model(tile)[0]
            output[..., y:y + crop_h, x:x + crop_w] = value[..., halo:halo + crop_h, halo:halo + crop_w]
    return output[0, 0].cpu().numpy()


@torch.inference_mode()
def tile_parity(model) -> dict[str, float]:
    generator = torch.Generator(device=DEVICE).manual_seed(108912)
    image = torch.rand((1, 1, 512, 512), generator=generator, device=DEVICE)
    full = model(image)[0]
    halo, core = 128, 128
    padded = F.pad(image, (halo, halo, halo, halo), mode="reflect")
    canvas = torch.zeros_like(image)
    for y in range(0, 512, core):
        for x in range(0, 512, core):
            value = model(padded[..., y:y + core + 2 * halo, x:x + core + 2 * halo])[0]
            canvas[..., y:y + core, x:x + core] = value[..., halo:halo + core, halo:halo + core]
    difference = torch.abs(full - canvas) * 255.0
    interior = difference[..., halo:-halo, halo:-halo]
    return {
        "interior_mean_gray": float(interior.mean()),
        "interior_p99_gray": float(torch.quantile(interior, 0.99)),
        "interior_max_gray": float(interior.max()),
    }


def appearance(raw: np.ndarray, output: np.ndarray) -> dict[str, float]:
    gx = cv2.Sobel(raw, cv2.CV_32F, 1, 0, ksize=3)
    gy = cv2.Sobel(raw, cv2.CV_32F, 0, 1, ksize=3)
    magnitude = np.hypot(gx, gy)
    support = magnitude >= np.quantile(magnitude, 0.90)
    gx2 = cv2.Sobel(output, cv2.CV_32F, 1, 0, ksize=3)
    gy2 = cv2.Sobel(output, cv2.CV_32F, 0, 1, ksize=3)
    raw_detail = raw - cv2.GaussianBlur(raw, (0, 0), 1.0)
    out_detail = output - cv2.GaussianBlur(output, (0, 0), 1.0)
    return {
        "change_gray": float(np.mean(np.abs(output - raw)) * 255.0),
        "edge_gain": float(np.hypot(gx2, gy2)[support].mean() / max(float(magnitude[support].mean()), 1e-9)),
        "detail_ratio": float(np.mean(np.abs(out_detail)) / max(float(np.mean(np.abs(raw_detail))), 1e-9)),
    }


def real_and_sem(model) -> dict[str, object]:
    rows = []
    preview_rows = []
    for path in REAL_IMAGES:
        raw = read_gray(path)
        output = tiled(model, raw)
        rows.append({"image": path.name, **appearance(raw, output)})
        preview_rows.append(np.concatenate([cv2.resize(raw, (480, 360), interpolation=cv2.INTER_AREA), cv2.resize(output, (480, 360), interpolation=cv2.INTER_AREA)], axis=1))
    frame = pd.DataFrame(rows)
    frame.to_csv(RESULTS / "real_appearance.csv", index=False)
    cv2.imencode(".png", np.round(np.clip(np.concatenate(preview_rows, axis=0), 0.0, 1.0) * 255.0).astype(np.uint8))[1].tofile(str(RESULTS / "real_comparison.png"))
    sem_rows = []
    for path in sorted(SEM_ROOT.glob("*.bmp")):
        raw = read_gray(path)
        output = tiled(model, raw)
        write_gray(RESULTS / "sem_reconstruction" / path.name, output)
        sem_rows.append({"exposure": int(path.stem), **appearance(raw, output)})
    sem_frame = pd.DataFrame(sem_rows)
    sem_frame.to_csv(RESULTS / "sem_appearance.csv", index=False)
    return {
        "real_median": {key: float(frame[key].median()) for key in ("change_gray", "edge_gain", "detail_ratio")},
        "sem_median": {key: float(sem_frame[key].median()) for key in ("change_gray", "edge_gain", "detail_ratio")},
    }


def main() -> int:
    seed_all(108910)
    splits = build_data()
    train_data = tensors(splits["train"])
    model = MultiscaleNormalGeometry().to(DEVICE)
    trace = train(model, train_data, 1600)
    model.eval()
    old = load_old_comparator()
    evaluations = {}
    per_family = []
    for split in ("validation", "holdout"):
        source_tensor = torch.from_numpy(splits[split]["source"].astype(np.float32) / 255.0).unsqueeze(1).to(DEVICE)
        new_output = predict(model, source_tensor)
        old_output = predict(old, source_tensor, old=True)
        evaluations[split] = {
            "Raw": evaluate("Raw", splits[split]["source"].astype(np.float32) / 255.0, splits[split]),
            "R108C_fixed_scale": evaluate("R108C_fixed_scale", old_output, splits[split]),
            "R108D_multiscale_normal": evaluate("R108D_multiscale_normal", new_output, splits[split]),
        }
        if split == "holdout":
            for family in np.unique(splits[split]["family"]):
                mask = splits[split]["family"] == family
                subset = {key: value[mask] for key, value in splits[split].items()}
                per_family.append({"family": str(family), **evaluate("R108D_multiscale_normal", new_output[mask], subset)})
    pd.DataFrame(per_family).to_csv(RESULTS / "holdout_by_family.csv", index=False)
    audit = real_and_sem(model)
    summary = {
        "status": "complete",
        "device": str(DEVICE),
        "training": {"steps": 1600, "seed": 108910, "trace": trace},
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

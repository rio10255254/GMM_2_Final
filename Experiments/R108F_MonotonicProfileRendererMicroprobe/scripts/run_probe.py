"""Train a staged, monotonic, no-overshoot contour renderer from scratch."""
from __future__ import annotations

import hashlib
import importlib.util
import json
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
DATA, WEIGHTS, RESULTS = (ROOT / name for name in ("data", "weights", "results"))
for folder in (DATA, WEIGHTS, RESULTS):
    folder.mkdir(parents=True, exist_ok=True)
ECORE_PATH = Path(str(PROJECT_ROOT / 'Experiments/R108E_ContourConservingProfileRendererMicroprobe/scripts/run_probe.py'))
SOURCE_DATA = Path(str(PROJECT_ROOT / 'Experiments/R108E_ContourConservingProfileRendererMicroprobe/data/profile_renderer_data.npz'))
SOURCE_DATA_SHA = "3e3ed993a03a0b354888b3d28edc4d2edcc26ee624f317e4615bfcb5a41b7663"
R108E_WEIGHT = Path(str(PROJECT_ROOT / 'Experiments/R108E_ContourConservingProfileRendererMicroprobe/weights/contour_profile_renderer.pth'))
DEVICE = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


ecore = load_module("r108f_r108e_utilities", ECORE_PATH)
dcore = ecore.dcore


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_data() -> dict[str, dict[str, np.ndarray]]:
    if not SOURCE_DATA.exists() or sha256(SOURCE_DATA) != SOURCE_DATA_SHA:
        raise RuntimeError("Verified R108E procedural data changed")
    keys = ("source", "target", "mask", "edge", "midpoint", "polarity", "identity", "family", "challenge")
    loaded = np.load(SOURCE_DATA, allow_pickle=False)
    result = {split: {key: loaded[f"{split}_{key}"] for key in keys} for split in ("train", "validation", "holdout")}
    manifest = {
        "status": "complete",
        "source": str(SOURCE_DATA),
        "source_sha256": SOURCE_DATA_SHA,
        "counts": {split: len(data["source"]) for split, data in result.items()},
        "training_pixels": "procedural generic only",
        "old_weight_or_teacher_used": False,
    }
    (DATA / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return result


class MonotonicProfileRenderer(nn.Module):
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
        self.coefficient_head = nn.Conv2d(channels, 4, 1)
        self.flow_head = nn.Conv2d(channels, 2, 1)
        nn.init.zeros_(self.boundary_head.weight)
        nn.init.constant_(self.boundary_head.bias, -2.0)
        nn.init.zeros_(self.necessity_head.weight)
        nn.init.constant_(self.necessity_head.bias, -1.0)
        nn.init.zeros_(self.coefficient_head.weight)
        nn.init.constant_(self.coefficient_head.bias, -2.2)
        nn.init.zeros_(self.flow_head.weight)
        nn.init.zeros_(self.flow_head.bias)

    def cues(self, x: torch.Tensor):
        blurred = [layer(x) for layer in self.blurs]
        highpasses = [x - value for value in blurred]
        gx, gy = dcore.gradients(x)
        magnitude = torch.sqrt(gx.square() + gy.square() + 1e-8)
        local_mean = blurred[-1]
        local_scale = torch.sqrt(self.context((x - local_mean).square()) + (2 / 255) ** 2)
        normalized = (x - local_mean) / (local_scale + 2 / 255)
        cues = torch.cat([x, *blurred, *highpasses, gx, gy, magnitude, local_mean, local_scale, normalized], dim=1)
        return cues, magnitude, local_scale

    @staticmethod
    def warp(x: torch.Tensor, flow: torch.Tensor) -> torch.Tensor:
        height, width = x.shape[-2:]
        yy, xx = torch.meshgrid(
            torch.linspace(-1.0, 1.0, height, device=x.device, dtype=x.dtype),
            torch.linspace(-1.0, 1.0, width, device=x.device, dtype=x.dtype),
            indexing="ij",
        )
        grid = torch.stack([xx, yy], dim=-1).unsqueeze(0).expand(x.shape[0], -1, -1, -1).clone()
        grid[..., 0] += flow[:, 0] * (2.0 / max(width - 1, 1))
        grid[..., 1] += flow[:, 1] * (2.0 / max(height - 1, 1))
        return F.grid_sample(x, grid, mode="bilinear", padding_mode="reflection", align_corners=True)

    def forward(self, x: torch.Tensor):
        cues, magnitude, local_scale = self.cues(x)
        detector = self.detector_tower(F.silu(self.detector_stem(cues)))
        renderer = self.renderer_tower(F.silu(self.renderer_stem(cues)))
        boundary_logits = self.boundary_head(detector)
        boundary_probability = torch.sigmoid(boundary_logits)
        necessity = torch.sigmoid(self.necessity_head(detector))
        source_support = ((magnitude / (local_scale + 2 / 255) - 0.05) / 1.10).clamp(0.0, 1.0)
        predicted_support = F.max_pool2d(boundary_probability, 9, 1, 4)
        support = torch.maximum(source_support, 0.85 * predicted_support).clamp(0.0, 1.0)
        flow = 1.5 * torch.tanh(self.flow_head(renderer))
        effective = necessity * support
        warped = self.warp(x, flow * effective)
        warped_blurs = [layer(warped) for layer in self.blurs]
        scale_limits = x.new_tensor((1.0, 1.4, 1.8, 2.2)).view(1, 4, 1, 1)
        coefficients = torch.sigmoid(self.coefficient_head(renderer)) * scale_limits
        unsharp = sum(coefficients[:, index:index + 1] * (warped - warped_blurs[index]) for index in range(4))
        proposal = warped + unsharp
        local_max = F.max_pool2d(warped, 15, 1, 7)
        local_min = -F.max_pool2d(-warped, 15, 1, 7)
        proposal = torch.maximum(local_min, torch.minimum(local_max, proposal))
        output = (x + effective * (proposal - x)).clamp(0.0, 1.0)
        delta = output - x
        return output, delta, boundary_logits, boundary_probability, necessity, support, coefficients, flow


def balanced_batch(data: dict[str, torch.Tensor], generator: torch.Generator) -> torch.Tensor:
    clear_pool = torch.nonzero(data["identity"], as_tuple=False).flatten()
    degraded_pool = torch.nonzero(~data["identity"], as_tuple=False).flatten()
    clear = clear_pool[torch.randint(0, len(clear_pool), (12,), generator=generator, device=DEVICE)]
    degraded = degraded_pool[torch.randint(0, len(degraded_pool), (12,), generator=generator, device=DEVICE)]
    return torch.cat([clear, degraded])


def need_target(target: torch.Tensor, source: torch.Tensor, edge: torch.Tensor, identity: torch.Tensor) -> torch.Tensor:
    boundary = F.max_pool2d(edge, 5, 1, 2).clamp(0.0, 1.0)
    local = F.avg_pool2d(torch.abs(target - source), 9, 1, 4)
    need = ((local - 0.5 / 255.0) / (5.0 / 255.0)).clamp(0.0, 1.0)
    need = need * F.max_pool2d(boundary, 11, 1, 5)
    need[identity] = 0.0
    return need


def train(model: MonotonicProfileRenderer, data: dict[str, torch.Tensor]):
    generator = torch.Generator(device=DEVICE).manual_seed(109111)
    trace = []
    detector_parameters = [
        *model.detector_stem.parameters(), *model.detector_tower.parameters(),
        *model.boundary_head.parameters(), *model.necessity_head.parameters(),
    ]
    optimizer = torch.optim.AdamW(detector_parameters, lr=3.5e-4, weight_decay=1e-5)
    for step in range(1, 901):
        index = balanced_batch(data, generator)
        source, target, edge = (data[key][index] for key in ("source", "target", "edge"))
        identity = data["identity"][index]
        _, _, boundary_logits, boundary_probability, necessity, support, _, _ = model(source)
        boundary_target = F.max_pool2d(edge, 5, 1, 2).clamp(0.0, 1.0)
        need = need_target(target, source, edge, identity)
        fraction = need.mean().detach().clamp(1e-4, 0.9999)
        weight = 1.0 + need * ((1.0 - fraction) / fraction)
        need_loss = F.binary_cross_entropy(necessity.clamp(1e-5, 1 - 1e-5), need, weight=weight) + 0.35 * ecore.balanced_need_loss(necessity, need)
        positive_weight = (1.0 - boundary_target.mean()).detach() / boundary_target.mean().clamp_min(1e-4).detach()
        boundary_bce = F.binary_cross_entropy_with_logits(boundary_logits, boundary_target, pos_weight=positive_weight)
        boundary_dice = ecore.soft_dice(boundary_probability, boundary_target)
        loss = 0.45 * boundary_bce + 0.30 * boundary_dice + need_loss
        optimizer.zero_grad(set_to_none=True)
        loss.backward()
        norm = torch.nn.utils.clip_grad_norm_(detector_parameters, 5.0)
        optimizer.step()
        if not torch.isfinite(loss) or not torch.isfinite(norm):
            raise FloatingPointError(f"detector {step}")
        if step == 1 or step % 100 == 0:
            row = {"phase": "detector", "step": step, "loss": float(loss.detach()), "boundary_dice": float(boundary_dice.detach()), "need_loss": float(need_loss.detach()), "identity_need": float(necessity[identity].mean().detach()), "degraded_need": float(necessity[~identity].mean().detach()), "support_mean": float(support.mean().detach())}
            trace.append(row); print(json.dumps(row), flush=True)
    with torch.inference_mode():
        scene = []
        for start in range(0, len(data["source"]), 24):
            scene.append(model(data["source"][start:start + 24])[4].mean(dim=(1, 2, 3)).cpu())
        scene = torch.cat(scene); identity_cpu = data["identity"].cpu()
        detector_audit = {"identity_mean": float(scene[identity_cpu].mean()), "degraded_mean": float(scene[~identity_cpu].mean())}
        detector_audit["separation"] = detector_audit["degraded_mean"] - detector_audit["identity_mean"]
    print(json.dumps({"phase": "detector_audit", **detector_audit}), flush=True)
    if detector_audit["separation"] <= 0.02:
        raise RuntimeError("Detector separation failed")
    for parameter in detector_parameters:
        parameter.requires_grad_(False)
    renderer_parameters = [
        *model.renderer_stem.parameters(), *model.renderer_tower.parameters(),
        *model.coefficient_head.parameters(), *model.flow_head.parameters(),
    ]
    optimizer = torch.optim.AdamW(renderer_parameters, lr=3.5e-4, weight_decay=1e-5)
    for step in range(1, 1201):
        index = balanced_batch(data, generator)
        source, target, mask, edge = (data[key][index] for key in ("source", "target", "mask", "edge"))
        midpoint = data["midpoint"][index, None, None, None]
        polarity = data["polarity"][index, None, None, None]
        identity = data["identity"][index]
        output, delta, _, _, necessity, _, coefficients, flow = model(source)
        boundary = F.max_pool2d(edge, 5, 1, 2).clamp(0.0, 1.0)
        soft_mask = torch.sigmoid(42.0 * polarity * (output - midpoint))
        contour = ecore.soft_dice(soft_mask, mask)
        contour_bce = F.binary_cross_entropy(soft_mask.clamp(1e-5, 1 - 1e-5), mask)
        area = torch.abs(soft_mask.mean(dim=(1, 2, 3)) - mask.mean(dim=(1, 2, 3))).mean()
        centroid = ecore.centroid_loss(soft_mask, mask)
        band = 0.06 + 0.94 * boundary
        direct = ecore.weighted_mean(F.smooth_l1_loss(delta, target - source, beta=1 / 255, reduction="none"), band)
        image = ecore.weighted_mean(torch.abs(output - target), band)
        out_gx, out_gy = dcore.gradients(output); target_gx, target_gy = dcore.gradients(target)
        gradient = ecore.weighted_mean(torch.abs(out_gx - target_gx) + torch.abs(out_gy - target_gy), band)
        identity_action = delta[identity].abs().mean()
        flow_smooth = torch.abs(flow[..., 1:] - flow[..., :-1]).mean() + torch.abs(flow[..., 1:, :] - flow[..., :-1, :]).mean()
        loss = 0.60 * contour + 0.12 * contour_bce + 0.22 * area + 0.16 * centroid + 0.90 * direct + 0.42 * image + 0.18 * gradient + 1.50 * identity_action + 0.025 * flow_smooth + 0.0005 * coefficients.mean()
        optimizer.zero_grad(set_to_none=True); loss.backward(); norm = torch.nn.utils.clip_grad_norm_(renderer_parameters, 5.0); optimizer.step()
        if not torch.isfinite(loss) or not torch.isfinite(norm):
            raise FloatingPointError(f"renderer {step}")
        if step == 1 or step % 100 == 0:
            row = {"phase": "renderer", "step": step, "loss": float(loss.detach()), "contour_dice": float(contour.detach()), "area": float(area.detach()), "centroid": float(centroid.detach()), "direct": float(direct.detach()), "action_gray": float(delta.abs().mean().detach() * 255.0), "identity_action_gray": float(identity_action.detach() * 255.0), "flow_abs_px": float(flow.abs().mean().detach()), "coefficient_mean": float(coefficients.mean().detach()), "identity_need": float(necessity[identity].mean().detach()), "degraded_need": float(necessity[~identity].mean().detach())}
            trace.append(row); print(json.dumps(row), flush=True)
    torch.save({"model": model.state_dict(), "seed": 109110, "detector_steps": 900, "renderer_steps": 1200}, WEIGHTS / "monotonic_profile_renderer.pth")
    return trace, detector_audit


@torch.inference_mode()
def predict(model, source: torch.Tensor) -> np.ndarray:
    values = []
    for start in range(0, len(source), 24):
        values.append(model(source[start:start + 24])[0].cpu())
    return torch.cat(values).numpy()[:, 0]


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


def real_and_sem(model):
    real_rows, previews = [], []
    for path in ecore.REAL_IMAGES:
        raw = dcore.read_gray(path); output = tiled(model, raw)
        dcore.write_gray(RESULTS / "real" / path.name, output)
        real_rows.append({"image": path.name, **ecore.appearance(raw, output)})
        previews.append(np.concatenate([cv2.resize(raw, (480, 360), interpolation=cv2.INTER_AREA), cv2.resize(output, (480, 360), interpolation=cv2.INTER_AREA)], axis=1))
    frame = pd.DataFrame(real_rows); frame.to_csv(RESULTS / "real_appearance.csv", index=False)
    cv2.imencode(".png", np.round(np.clip(np.concatenate(previews, axis=0), 0, 1) * 255).astype(np.uint8))[1].tofile(str(RESULTS / "real_comparison.png"))
    sem_rows = []
    for path in sorted(ecore.SEM_ROOT.glob("*.bmp")):
        raw = dcore.read_gray(path); output = tiled(model, raw)
        dcore.write_gray(RESULTS / "sem_reconstruction" / path.name, output)
        sem_rows.append({"exposure": int(path.stem), **ecore.appearance(raw, output)})
    sem = pd.DataFrame(sem_rows); sem.to_csv(RESULTS / "sem_appearance.csv", index=False)
    return {"real_median": {key: float(frame[key].median()) for key in ("change_gray", "edge_gain", "detail_ratio")}, "sem_median": {key: float(sem[key].median()) for key in ("change_gray", "edge_gain", "detail_ratio")}}


@torch.inference_mode()
def tile_parity(model):
    generator = torch.Generator(device=DEVICE).manual_seed(109112)
    image = torch.rand((1, 1, 512, 512), generator=generator, device=DEVICE)
    full = model(image)[0]; halo = 192; core = 128; padded = F.pad(image, (halo, halo, halo, halo), mode="reflect"); canvas = torch.zeros_like(image)
    for y in range(0, 512, core):
        for x in range(0, 512, core):
            value = model(padded[..., y:y + core + 2 * halo, x:x + core + 2 * halo])[0]
            canvas[..., y:y + core, x:x + core] = value[..., halo:halo + core, halo:halo + core]
    difference = torch.abs(full - canvas) * 255.0; interior = difference[..., halo:-halo, halo:-halo]
    return {"interior_mean_gray": float(interior.mean()), "interior_p99_gray": float(torch.quantile(interior, 0.99)), "interior_max_gray": float(interior.max())}


def main() -> int:
    dcore.seed_all(109110)
    splits = load_data(); tensor_train = ecore.tensors(splits["train"])
    model = MonotonicProfileRenderer().to(DEVICE); trace, detector_audit = train(model, tensor_train); model.eval()
    e_model = ecore.ContourProfileRenderer().to(DEVICE); e_model.load_state_dict(torch.load(R108E_WEIGHT, map_location=DEVICE, weights_only=False)["model"]); e_model.eval()
    evaluations = {}
    for split in ("validation", "holdout"):
        source = torch.from_numpy(splits[split]["source"].astype(np.float32) / 255.0).unsqueeze(1).to(DEVICE)
        outputs = {"Raw": splits[split]["source"].astype(np.float32) / 255.0, "R108E_free_renderer": predict(e_model, source), "R108F_monotonic": predict(model, source)}
        evaluations[split] = {name: ecore.evaluate(name, output, splits[split]) for name, output in outputs.items()}
    audit = real_and_sem(model)
    summary = {"status": "complete", "device": str(DEVICE), "training": {"seed": 109110, "detector_steps": 900, "renderer_steps": 1200, "detector_audit": detector_audit, "trace": trace}, "data_manifest": json.loads((DATA / "manifest.json").read_text(encoding="utf-8")), "evaluations": evaluations, "tile_parity": tile_parity(model), "sealed_real_audit": audit, "formal_training_authorized": False}
    (RESULTS / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8"); print(json.dumps(summary), flush=True); return 0


if __name__ == "__main__":
    raise SystemExit(main())

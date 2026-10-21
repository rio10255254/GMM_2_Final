"""Train midpoint-shift and monotonic-width correction as separate physical factors."""
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


ROOT = Path(__file__).resolve().parents[1]
DATA, WEIGHTS, RESULTS = (ROOT / name for name in ("data", "weights", "results"))
for folder in (DATA, WEIGHTS, RESULTS):
    folder.mkdir(parents=True, exist_ok=True)
FCORE_PATH = Path(r"D:\GMM_2_Final\Experiments\R108F_MonotonicProfileRendererMicroprobe\scripts\run_probe.py")
SOURCE_DATA = Path(r"D:\GMM_2_Final\Experiments\R108E_ContourConservingProfileRendererMicroprobe\data\profile_renderer_data.npz")
SOURCE_DATA_SHA = "3e3ed993a03a0b354888b3d28edc4d2edcc26ee624f317e4615bfcb5a41b7663"
R108E_WEIGHT = Path(r"D:\GMM_2_Final\Experiments\R108E_ContourConservingProfileRendererMicroprobe\weights\contour_profile_renderer.pth")
R108F_WEIGHT = Path(r"D:\GMM_2_Final\Experiments\R108F_MonotonicProfileRendererMicroprobe\weights\monotonic_profile_renderer.pth")
DEVICE = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


fcore = load_module("r108g_r108f_utilities", FCORE_PATH)
ecore, dcore = fcore.ecore, fcore.dcore


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_data():
    if not SOURCE_DATA.exists() or sha256(SOURCE_DATA) != SOURCE_DATA_SHA:
        raise RuntimeError("Verified procedural data changed")
    keys = ("source", "target", "mask", "edge", "midpoint", "polarity", "identity", "family", "challenge")
    loaded = np.load(SOURCE_DATA, allow_pickle=False)
    result = {split: {key: loaded[f"{split}_{key}"] for key in keys} for split in ("train", "validation", "holdout")}
    manifest = {"status": "complete", "source": str(SOURCE_DATA), "source_sha256": SOURCE_DATA_SHA, "counts": {split: len(data["source"]) for split, data in result.items()}, "old_weight_or_teacher_used": False, "real_or_sem_training_pixels": False}
    (DATA / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return result


class MidpointWidthOperator(nn.Module):
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
        self.coefficient_head = nn.Conv2d(channels, 1, 1)  # monotonic width gain
        self.flow_head = nn.Conv2d(channels, 1, 1)  # signed normal displacement
        nn.init.zeros_(self.boundary_head.weight); nn.init.constant_(self.boundary_head.bias, -2.0)
        nn.init.zeros_(self.necessity_head.weight); nn.init.constant_(self.necessity_head.bias, -1.0)
        nn.init.zeros_(self.coefficient_head.weight); nn.init.constant_(self.coefficient_head.bias, -4.0)
        nn.init.zeros_(self.flow_head.weight); nn.init.zeros_(self.flow_head.bias)

    def cues(self, x: torch.Tensor):
        blurred = [layer(x) for layer in self.blurs]
        highpasses = [x - value for value in blurred]
        gx, gy = dcore.gradients(x)
        magnitude = torch.sqrt(gx.square() + gy.square() + 1e-8)
        local_mean = blurred[-1]
        local_scale = torch.sqrt(self.context((x - local_mean).square()) + (2 / 255) ** 2)
        normalized = (x - local_mean) / (local_scale + 2 / 255)
        cues = torch.cat([x, *blurred, *highpasses, gx, gy, magnitude, local_mean, local_scale, normalized], dim=1)
        return cues, blurred, magnitude, local_scale

    @staticmethod
    def warp(x: torch.Tensor, flow: torch.Tensor) -> torch.Tensor:
        height, width = x.shape[-2:]
        yy, xx = torch.meshgrid(torch.linspace(-1, 1, height, device=x.device, dtype=x.dtype), torch.linspace(-1, 1, width, device=x.device, dtype=x.dtype), indexing="ij")
        grid = torch.stack([xx, yy], dim=-1).unsqueeze(0).expand(x.shape[0], -1, -1, -1).clone()
        grid[..., 0] += flow[:, 0] * (2.0 / max(width - 1, 1)); grid[..., 1] += flow[:, 1] * (2.0 / max(height - 1, 1))
        return F.grid_sample(x, grid, mode="bilinear", padding_mode="reflection", align_corners=True)

    def forward(self, x: torch.Tensor):
        cues, blurred, magnitude, local_scale = self.cues(x)
        detector = self.detector_tower(F.silu(self.detector_stem(cues)))
        renderer = self.renderer_tower(F.silu(self.renderer_stem(cues)))
        boundary_logits = self.boundary_head(detector); boundary = torch.sigmoid(boundary_logits); necessity = torch.sigmoid(self.necessity_head(detector))
        source_support = ((magnitude / (local_scale + 2 / 255) - 0.05) / 1.10).clamp(0, 1)
        support = torch.maximum(source_support, 0.85 * F.max_pool2d(boundary, 9, 1, 4)).clamp(0, 1)
        effective = necessity * support
        smooth_gx, smooth_gy = dcore.gradients(blurred[1])
        smooth_magnitude = torch.sqrt(smooth_gx.square() + smooth_gy.square() + 1e-8)
        normal_x, normal_y = smooth_gx / smooth_magnitude, smooth_gy / smooth_magnitude
        normal_shift = 1.5 * torch.tanh(self.flow_head(renderer))
        flow = torch.cat([normal_shift * normal_x, normal_shift * normal_y], dim=1)
        warped = self.warp(x, flow * effective)
        local_max = F.max_pool2d(warped, 21, 1, 10); local_min = -F.max_pool2d(-warped, 21, 1, 10)
        dynamic = (local_max - local_min).clamp_min(2 / 255)
        unit = ((warped - local_min) / dynamic).clamp(1e-3, 1 - 1e-3)
        width_gain = 1.0 + 2.5 * torch.sigmoid(self.coefficient_head(renderer))
        corrected_unit = torch.sigmoid(width_gain * (torch.log(unit) - torch.log1p(-unit)))
        proposal = local_min + dynamic * corrected_unit
        output = (x + effective * (proposal - x)).clamp(0, 1); delta = output - x
        return output, delta, boundary_logits, boundary, necessity, support, width_gain, flow


def load_comparators():
    e_model = ecore.ContourProfileRenderer().to(DEVICE); e_model.load_state_dict(torch.load(R108E_WEIGHT, map_location=DEVICE, weights_only=False)["model"]); e_model.eval()
    f_model = fcore.MonotonicProfileRenderer().to(DEVICE); f_model.load_state_dict(torch.load(R108F_WEIGHT, map_location=DEVICE, weights_only=False)["model"]); f_model.eval()
    return e_model, f_model


def real_and_sem(model):
    real_rows, previews = [], []
    for path in ecore.REAL_IMAGES:
        raw = dcore.read_gray(path); output = fcore.tiled(model, raw)
        dcore.write_gray(RESULTS / "real" / path.name, output); real_rows.append({"image": path.name, **ecore.appearance(raw, output)})
        previews.append(np.concatenate([cv2.resize(raw, (480, 360), interpolation=cv2.INTER_AREA), cv2.resize(output, (480, 360), interpolation=cv2.INTER_AREA)], axis=1))
    frame = pd.DataFrame(real_rows); frame.to_csv(RESULTS / "real_appearance.csv", index=False)
    cv2.imencode(".png", np.round(np.clip(np.concatenate(previews, axis=0), 0, 1) * 255).astype(np.uint8))[1].tofile(str(RESULTS / "real_comparison.png"))
    sem_rows = []
    for path in sorted(ecore.SEM_ROOT.glob("*.bmp")):
        raw = dcore.read_gray(path); output = fcore.tiled(model, raw); dcore.write_gray(RESULTS / "sem_reconstruction" / path.name, output); sem_rows.append({"exposure": int(path.stem), **ecore.appearance(raw, output)})
    sem = pd.DataFrame(sem_rows); sem.to_csv(RESULTS / "sem_appearance.csv", index=False)
    return {"real_median": {key: float(frame[key].median()) for key in ("change_gray", "edge_gain", "detail_ratio")}, "sem_median": {key: float(sem[key].median()) for key in ("change_gray", "edge_gain", "detail_ratio")}}


def main() -> int:
    dcore.seed_all(109210); splits = load_data(); model = MidpointWidthOperator().to(DEVICE)
    # Redirect the reused training routine's checkpoint write into this
    # independent experiment; the R108F checkpoint is never touched.
    fcore.WEIGHTS = WEIGHTS
    trace, detector_audit = fcore.train(model, ecore.tensors(splits["train"]))
    temporary_checkpoint = WEIGHTS / "monotonic_profile_renderer.pth"
    final_checkpoint = WEIGHTS / "midpoint_width_operator.pth"
    temporary_checkpoint.replace(final_checkpoint)
    model.eval(); e_model, f_model = load_comparators(); evaluations = {}
    for split in ("validation", "holdout"):
        source = torch.from_numpy(splits[split]["source"].astype(np.float32) / 255.0).unsqueeze(1).to(DEVICE)
        outputs = {"Raw": splits[split]["source"].astype(np.float32) / 255.0, "R108E_free": fcore.predict(e_model, source), "R108F_multiscale": fcore.predict(f_model, source), "R108G_midpoint_width": fcore.predict(model, source)}
        evaluations[split] = {name: ecore.evaluate(name, output, splits[split]) for name, output in outputs.items()}
    audit = real_and_sem(model)
    summary = {"status": "complete", "device": str(DEVICE), "training": {"seed": 109210, "detector_steps": 900, "renderer_steps": 1200, "detector_audit": detector_audit, "trace": trace}, "data_manifest": json.loads((DATA / "manifest.json").read_text(encoding="utf-8")), "evaluations": evaluations, "tile_parity": fcore.tile_parity(model), "sealed_real_audit": audit, "formal_training_authorized": False}
    (RESULTS / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8"); print(json.dumps(summary), flush=True); return 0


if __name__ == "__main__":
    raise SystemExit(main())

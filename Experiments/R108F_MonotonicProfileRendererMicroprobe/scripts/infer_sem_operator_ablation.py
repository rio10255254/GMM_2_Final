"""Separate R108F local warp from positive multiscale sharpening on SEM."""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import torch
import torch.nn.functional as F


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "results" / "sem_operator_ablation"
CORE_PATH = ROOT / "scripts" / "run_probe.py"


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


core = load_module("r108f_sem_ablation_core", CORE_PATH)


@torch.inference_mode()
def forward_variant(model, x: torch.Tensor, variant: str):
    cues, magnitude, local_scale = model.cues(x)
    detector = model.detector_tower(F.silu(model.detector_stem(cues)))
    renderer = model.renderer_tower(F.silu(model.renderer_stem(cues)))
    boundary = torch.sigmoid(model.boundary_head(detector))
    necessity = torch.sigmoid(model.necessity_head(detector))
    source_support = ((magnitude / (local_scale + 2 / 255) - 0.05) / 1.10).clamp(0.0, 1.0)
    support = torch.maximum(source_support, 0.85 * F.max_pool2d(boundary, 9, 1, 4)).clamp(0.0, 1.0)
    effective = necessity * support
    flow = 1.5 * torch.tanh(model.flow_head(renderer))
    if variant == "sharpen_only":
        flow = torch.zeros_like(flow)
    warped = model.warp(x, flow * effective)
    limits = x.new_tensor((1.0, 1.4, 1.8, 2.2)).view(1, 4, 1, 1)
    coefficients = torch.sigmoid(model.coefficient_head(renderer)) * limits
    if variant == "flow_only":
        coefficients = torch.zeros_like(coefficients)
    blurs = [layer(warped) for layer in model.blurs]
    proposal = warped + sum(coefficients[:, index:index + 1] * (warped - blurs[index]) for index in range(4))
    local_max = F.max_pool2d(warped, 15, 1, 7)
    local_min = -F.max_pool2d(-warped, 15, 1, 7)
    proposal = torch.maximum(local_min, torch.minimum(local_max, proposal))
    output = (x + effective * (proposal - x)).clamp(0.0, 1.0)
    return output, necessity, flow, coefficients


@torch.inference_mode()
def tiled(model, image: np.ndarray, variant: str, core_size: int = 256, halo: int = 192):
    tensor = torch.from_numpy(image[None, None]).to(core.DEVICE)
    height, width = image.shape
    padded = F.pad(tensor, (halo, halo, halo, halo), mode="reflect")
    output = torch.zeros_like(tensor)
    stats = []
    for y in range(0, height, core_size):
        for x in range(0, width, core_size):
            crop_h, crop_w = min(core_size, height - y), min(core_size, width - x)
            tile = padded[..., y:y + crop_h + 2 * halo, x:x + crop_w + 2 * halo]
            value, necessity, flow, coefficients = forward_variant(model, tile, variant)
            output[..., y:y + crop_h, x:x + crop_w] = value[..., halo:halo + crop_h, halo:halo + crop_w]
            interior = (..., slice(halo, halo + crop_h), slice(halo, halo + crop_w))
            stats.append(
                {
                    "necessity": float(necessity[interior].mean()),
                    "flow_x": float(flow[:, :1][interior].mean()),
                    "flow_y": float(flow[:, 1:2][interior].mean()),
                    "flow_abs": float(flow[interior].abs().mean()),
                    "coefficient": float(coefficients[interior].mean()),
                }
            )
    return output[0, 0].cpu().numpy(), stats


def main() -> int:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    model = core.MonotonicProfileRenderer().to(core.DEVICE)
    model.load_state_dict(torch.load(core.WEIGHTS / "monotonic_profile_renderer.pth", map_location=core.DEVICE, weights_only=False)["model"])
    model.eval()
    rows = []
    for path in sorted(core.ecore.SEM_ROOT.glob("*.bmp")):
        raw = core.dcore.read_gray(path)
        for variant in ("flow_only", "sharpen_only"):
            output, stats = tiled(model, raw, variant)
            core.dcore.write_gray(OUTPUT / variant / path.name, output)
            rows.append(
                {
                    "exposure": int(path.stem),
                    "variant": variant,
                    "change_gray": float(np.mean(np.abs(output - raw)) * 255.0),
                    **{key: float(np.mean([row[key] for row in stats])) for key in stats[0]},
                }
            )
    table = pd.DataFrame(rows)
    table.to_csv(OUTPUT / "action_summary.csv", index=False)
    summary = {"status": "complete", "variants": ["flow_only", "sharpen_only"], "exposures": 12, "median": table.groupby("variant").median(numeric_only=True).to_dict(orient="index")}
    (OUTPUT / "state.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

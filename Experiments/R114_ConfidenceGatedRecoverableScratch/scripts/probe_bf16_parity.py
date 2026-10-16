"""Check BF16 forward and gradient parity before enabling faster training."""
from __future__ import annotations

import copy
import json
from pathlib import Path
import sys

import torch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from model.full_model import build_full_model
from model.r114_model import build_model as build_controller
from training.dataset import R114Dataset
from training.losses import controller_components, geometry_parameter_components, render_components
from training.targets import build_spatial_targets


def batch(device: torch.device, count: int = 3) -> dict:
    dataset = R114Dataset("train", epoch=1, limit=count)
    rows = [dataset[index] for index in range(count)]
    result = {}
    for key in rows[0]:
        if isinstance(rows[0][key], torch.Tensor):
            result[key] = torch.stack([row[key] for row in rows]).to(device)
        else:
            result[key] = [row[key] for row in rows]
    return result


def controller_loss(model, values, use_bf16: bool):
    with torch.autocast("cuda", dtype=torch.bfloat16, enabled=use_bf16):
        details = model(values["source"])
    targets = build_spatial_targets(values["source"], values["target"], values["mask"], values["sdf"], values["identity"], values["flat"])
    components = controller_components(details, targets)
    loss = components["sdf"] + 0.7 * components["normal"] + components["boundary_bce"] + 0.7 * components["boundary_dice"] + components["need"] + 0.65 * components["recoverability"]
    maps = {name: getattr(details, name).float() for name in ("normalized_sdf", "normal_x", "normal_y", "boundary_confidence", "correction_need", "recoverability")}
    return loss, maps


def full_loss(model, values, use_bf16: bool):
    with torch.autocast("cuda", dtype=torch.bfloat16, enabled=use_bf16):
        details = model.forward_details(values["source"])
    targets = build_spatial_targets(values["source"], values["target"], values["mask"], values["sdf"], values["identity"], values["flat"])
    controller = controller_components(details, targets)
    geometry = geometry_parameter_components(details, targets)
    render = render_components(details, values, targets)
    loss = controller["boundary_bce"] + controller["need"] + geometry["width"] + geometry["shift"] + render["contour_dice"] + render["reconstruction"]
    maps = {name: getattr(details, name).float() for name in ("output", "boundary_confidence", "correction_need", "width_gain", "normal_shift")}
    return loss, maps


def gradient_vector(model: torch.nn.Module) -> torch.Tensor:
    return torch.cat([parameter.grad.detach().float().reshape(-1) for parameter in model.parameters() if parameter.grad is not None])


def compare(name: str, model, values, objective) -> dict:
    fp32 = model
    bf16 = copy.deepcopy(model)
    fp32.zero_grad(set_to_none=True)
    loss32, maps32 = objective(fp32, values, False)
    loss32.backward()
    grad32 = gradient_vector(fp32)
    bf16.zero_grad(set_to_none=True)
    loss16, maps16 = objective(bf16, values, True)
    loss16.backward()
    grad16 = gradient_vector(bf16)
    map_errors = {key: float((maps32[key] - maps16[key]).abs().mean().cpu()) for key in maps32}
    cosine = float(torch.nn.functional.cosine_similarity(grad32, grad16, dim=0).cpu())
    result = {
        "name": name,
        "fp32_loss": float(loss32.detach().cpu()),
        "bf16_loss": float(loss16.detach().cpu()),
        "relative_loss_error": float(abs(loss32.detach() - loss16.detach()).cpu() / loss32.detach().abs().clamp_min(1e-8).cpu()),
        "gradient_cosine": cosine,
        "map_mae": map_errors,
        "all_finite": bool(torch.isfinite(loss16) and torch.isfinite(grad16).all() and all(torch.isfinite(value).all() for value in maps16.values())),
    }
    result["pass"] = result["all_finite"] and result["relative_loss_error"] < 0.02 and cosine > 0.98 and max(map_errors.values()) < 0.005
    return result


def main() -> int:
    if not torch.cuda.is_available() or not torch.cuda.is_bf16_supported():
        raise RuntimeError("CUDA BF16 is unavailable")
    torch.manual_seed(11430)
    device = torch.device("cuda:0")
    values = batch(device)
    results = [
        compare("controller", build_controller().to(device), values, controller_loss),
        compare("full_geometry", build_full_model(False).to(device), values, full_loss),
    ]
    payload = {"status": "pass" if all(row["pass"] for row in results) else "fail", "results": results}
    output = ROOT / "results" / "bf16_parity.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(json.dumps(payload, indent=2))
    return 0 if payload["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())

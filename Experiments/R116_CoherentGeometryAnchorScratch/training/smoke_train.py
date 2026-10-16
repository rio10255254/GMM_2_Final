"""Run one finite optimization step through every independent R116 path."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

import torch
import torch.nn.functional as F


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from model.r116_model import R116Config, build_model, count_parameters
from training.losses import (
    detector_components,
    detail_components,
    geometry_components,
    shift_action_components,
    width_action_components,
)


def fixture(side: int, device: torch.device) -> dict[str, torch.Tensor]:
    yy, xx = torch.meshgrid(
        torch.arange(side, device=device, dtype=torch.float32),
        torch.arange(side, device=device, dtype=torch.float32),
        indexing="ij",
    )
    cx, cy = side * 0.51, side * 0.48
    sdf = torch.sqrt((xx - cx) ** 2 + (yy - cy) ** 2 + 1.0e-6) - side * 0.25
    target = 0.24 + 0.52 * torch.sigmoid(-sdf / 0.85)
    shifted_sdf = torch.sqrt((xx - (cx + 0.75)) ** 2 + (yy - (cy - 0.35)) ** 2 + 1.0e-6) - side * 0.25
    source = 0.24 + 0.52 * torch.sigmoid(-shifted_sdf / 2.4)
    source = F.avg_pool2d(source[None, None], 3, stride=1, padding=1)
    target = target[None, None]
    sdf = sdf[None, None]
    mask = (sdf <= 0).to(torch.float32)
    boundary = torch.exp(-sdf.abs() / 1.5)
    return {
        "source": source.clamp(0, 1),
        "target": target.clamp(0, 1),
        "sdf": sdf,
        "mask": mask,
        "boundary": boundary,
        "midpoint": torch.tensor([0.50], device=device),
        "polarity": torch.tensor([-1.0], device=device),
        "identity": torch.tensor([False], device=device),
    }


def small_config() -> R116Config:
    return R116Config(
        base_channels=16,
        action_channels=12,
        detail_channels=12,
        detector_dilations=(1, 2, 1),
        action_dilations=(1, 2, 1),
        detail_dilations=(1, 2, 1),
        blur_scales_px=(0.6, 1.0, 1.5, 2.0),
        profile_offsets_px=(-4, -2, 0, 2, 4),
        coherence_offsets_px=(-2, 0, 2),
        coherence_sigma_px=2.0,
        maximum_predicted_sdf_px=4.0,
        local_range_window_px=9,
        low_frequency_anchor_sigma_px=1.2,
        minimum_halo_px=48,
    )


def set_trainable(model, active: str) -> list[torch.nn.Parameter]:
    groups = model.parameter_groups()
    for name, parameters in groups.items():
        for parameter in parameters:
            parameter.requires_grad_(name == active)
    return groups[active]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--device", default="cuda:0" if torch.cuda.is_available() else "cpu")
    parser.add_argument("--full-config", action="store_true")
    parser.add_argument("--side", type=int, default=0)
    parser.add_argument("--output-name", default="architecture_smoke.json")
    args = parser.parse_args()
    torch.manual_seed(1163001)
    device = torch.device(args.device)
    selected_config = None if args.full_config else small_config()
    model = build_model(selected_config).to(device).train()
    side = int(args.side) if args.side > 0 else (128 if args.full_config else 80)
    batch = fixture(side, device)
    stage_results = {}
    for stage in ("detector", "width", "shift", "detail"):
        parameters = set_trainable(model, stage)
        optimizer = torch.optim.Adam(parameters, lr=1.0e-4)
        optimizer.zero_grad(set_to_none=True)
        details = model.forward_details(batch["source"])
        if stage == "detector":
            components = detector_components(details, batch["sdf"], batch["boundary"])
            objective = components["boundary_bce"] + components["boundary_dice"] + 0.1 * components["sdf"]
        elif stage in {"width", "shift"}:
            components = geometry_components(
                details,
                batch["target"],
                batch["mask"],
                batch["midpoint"],
                batch["polarity"],
                batch["identity"],
            )
            if stage == "width":
                target_gain = 1.0 + 1.2 * batch["boundary"]
                action = width_action_components(
                    details, target_gain, batch["boundary"], batch["boundary"],
                )
            else:
                target_shift = 0.75 * batch["boundary"]
                action = shift_action_components(
                    details, target_shift, batch["boundary"], batch["boundary"],
                )
            objective = (
                action["fit"]
                + 0.35 * action["confidence"]
                + 0.20 * action["neutral"]
                + 0.10 * components["reconstruction"]
                + 0.05 * components["contour"]
                + 0.05 * components["centroid"]
                + 0.25 * components["anchor_low_frequency"]
            )
        else:
            components = detail_components(details, batch["target"], batch["identity"])
            objective = (
                components["high_frequency"]
                + components["reconstruction"]
                + components["local_mean"]
                + components["identity"]
                + components["bound"]
            )
        if not bool(torch.isfinite(objective)):
            raise FloatingPointError(f"non-finite {stage} objective")
        objective.backward()
        gradients = [parameter.grad for parameter in parameters if parameter.grad is not None]
        if not gradients:
            raise RuntimeError(f"no gradient reached {stage}")
        gradient_norm = torch.sqrt(sum(value.detach().float().square().sum() for value in gradients))
        if not bool(torch.isfinite(gradient_norm)) or float(gradient_norm) <= 5.0e-6:
            raise RuntimeError(f"invalid {stage} gradient")
        optimizer.step()
        stage_results[stage] = {
            "objective": float(objective.detach().cpu()),
            "gradient_norm": float(gradient_norm.cpu()),
            "parameters_with_gradient": len(gradients),
        }
    for parameter in model.parameters():
        parameter.requires_grad_(True)
    model.eval()
    with torch.inference_mode():
        final = model.forward_details(batch["source"])
    result = {
        "status": "passed",
        "device": str(device),
        "config": "full" if args.full_config else "small",
        "parameter_count": count_parameters(model),
        "side": side,
        "stages": stage_results,
        "output_min": float(final.output.min().cpu()),
        "output_max": float(final.output.max().cpu()),
        "output_finite": bool(torch.isfinite(final.output).all()),
        "maximum_detail_abs": float(final.bounded_detail.abs().max().cpu()),
        "low_frequency_leakage_mean_abs": float(final.low_frequency_leakage.abs().mean().cpu()),
        "formal_training_authorized": False,
    }
    output = ROOT / "results" / args.output_name
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(result, indent=2, allow_nan=False), encoding="utf-8")
    temporary.replace(output)
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

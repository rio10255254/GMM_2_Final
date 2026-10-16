"""Explain whether each R116 path actually activated in a scratch probe."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

import numpy as np
import torch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from model.r116_model import build_model
from training.dataset import R116Dataset


def summary(value: torch.Tensor, mask: torch.Tensor | None = None) -> dict[str, float]:
    values = value.detach().float()
    if mask is not None:
        selected = mask.expand_as(values)
        values = values[selected]
    values = values.flatten().cpu().numpy()
    return {
        "mean": float(values.mean()),
        "mean_abs": float(np.abs(values).mean()),
        "p50": float(np.percentile(values, 50)),
        "p90": float(np.percentile(values, 90)),
        "p99": float(np.percentile(values, 99)),
        "maximum_abs": float(np.abs(values).max()),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--checkpoint", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")
    checkpoint_path = Path(args.checkpoint)
    checkpoint = torch.load(checkpoint_path, map_location="cpu")
    torch.manual_seed(int(checkpoint["config"]["seed"]))
    reference = build_model()
    trained = build_model()
    trained.load_state_dict(checkpoint["model"], strict=True)

    group_deltas = {}
    reference_state = reference.state_dict()
    trained_state = trained.state_dict()
    for group, parameters in trained.parameter_groups().items():
        names = {
            name for name, parameter in trained.named_parameters()
            if any(parameter is item for item in parameters)
        }
        delta_square = sum(
            float((trained_state[name].float() - reference_state[name].float()).square().sum())
            for name in names
        )
        reference_square = sum(float(reference_state[name].float().square().sum()) for name in names)
        group_deltas[group] = {
            "absolute_l2": float(delta_square ** 0.5),
            "relative_l2": float((delta_square / max(reference_square, 1.0e-12)) ** 0.5),
        }

    dataset = R116Dataset(
        "validation", epoch=0, limit=12,
        challenge_override="mixed_hard", role_filter="degraded",
    )
    source = torch.stack([dataset[index]["source"][0] for index in range(len(dataset))]).to(device)
    edge = torch.stack([dataset[index]["edge"][0] for index in range(len(dataset))]).to(device)
    trained = trained.to(device).eval()
    with torch.inference_mode():
        details = trained.forward_details(source)
    boundary = edge > 0.20
    maps = {
        "boundary_confidence": details.boundary_confidence,
        "predicted_sdf_abs": details.predicted_sdf_px.abs(),
        "source_support": details.source_support,
        "width_confidence": details.width_confidence,
        "width_gate": details.width_gate,
        "width_gain_minus_one": details.width_gain - 1.0,
        "shift_confidence": details.shift_confidence,
        "shift_gate": details.shift_gate,
        "normal_shift": details.normal_shift,
        "detail_coefficient_abs": details.detail_coefficients.abs().mean(dim=1, keepdim=True),
        "detail_confidence": details.detail_confidence,
        "bounded_detail": details.bounded_detail,
        "output_minus_raw": details.output - source,
    }
    payload = {
        "status": "complete",
        "checkpoint": str(checkpoint_path),
        "epoch": int(checkpoint["epoch"]),
        "group_parameter_deltas": group_deltas,
        "boundary_fraction": float(boundary.float().mean().cpu()),
        "maps_all_pixels": {name: summary(value) for name, value in maps.items()},
        "maps_true_boundary": {name: summary(value, boundary) for name, value in maps.items()},
    }
    output = ROOT / args.output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2, allow_nan=False), encoding="utf-8")
    print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

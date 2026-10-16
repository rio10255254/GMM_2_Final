from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from typing import Any

import numpy as np
import torch
import torch.nn.functional as F


ROOT = Path(__file__).resolve().parents[1]
TRAIN_PATH = ROOT / "training" / "train_r99.py"
OUTPUT_PATH = ROOT / "reports" / "deep_dive" / "transport_target_audit.json"


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def weighted_summary(target: torch.Tensor, weight: torch.Tensor) -> dict[str, float]:
    target = target.detach().float()
    weight = weight.detach().float()
    denominator = weight.sum().clamp_min(1.0)
    smooth_l1_at_zero = F.smooth_l1_loss(
        torch.zeros_like(target), target, beta=0.10, reduction="none"
    )
    return {
        "weight_sum": float(denominator),
        "weighted_abs_target_px": float((target.abs() * weight).sum() / denominator),
        "weighted_signed_target_px": float((target * weight).sum() / denominator),
        "zero_offset_smooth_l1": float((smooth_l1_at_zero * weight).sum() / denominator),
        "positive_weight_fraction": float(weight[target > 1e-6].sum() / denominator),
        "negative_weight_fraction": float(weight[target < -1e-6].sum() / denominator),
        "zero_weight_fraction": float(weight[target.abs() <= 1e-6].sum() / denominator),
    }


def combine(rows: list[dict[str, float]]) -> dict[str, Any]:
    if not rows:
        return {"count": 0}
    keys = [key for key in rows[0] if key != "weight_sum"]
    return {
        "count": len(rows),
        **{
            key: {
                "mean": float(np.mean([row[key] for row in rows])),
                "median": float(np.median([row[key] for row in rows])),
                "p10": float(np.quantile([row[key] for row in rows], 0.10)),
                "p90": float(np.quantile([row[key] for row in rows], 0.90)),
            }
            for key in keys
        },
    }


def main() -> None:
    trainer = load_module("r99_transport_audit_trainer", TRAIN_PATH)
    package = Path(trainer.DESIGN["dataset"]["source_package"])
    manifest = json.loads((package / "manifest.json").read_text(encoding="utf-8"))
    dataset = trainer.R99SceneDataset(
        package, manifest, "validation", 256, 128, 0, all_observations=True
    )

    identity_source_rows: list[dict[str, float]] = []
    perfect_target_rows: list[dict[str, float]] = []
    core = slice(64, 192)

    for index in range(len(dataset)):
        item = dataset[index]
        boundary_level = item["boundary_level"].reshape(1, 1, 1, 1)
        polarity = item["polarity"].reshape(1, 1, 1, 1)
        for view in range(int(item["source"].shape[0])):
            source = item["source"][view : view + 1, :, core, core]
            target_image = item["target"][view : view + 1, :, core, core]
            sdf = item["sdf"][view : view + 1, :, core, core]
            transport_target = sdf.clamp(-1.5, 1.5)
            distance_confidence = torch.exp(-sdf.abs() / 4.0)

            # Counterfactual 1: the source belongs to the explicit identity set.
            if bool(item["identity"][view]):
                probability = trainer.foreground_probability(source, boundary_level, polarity)
                raw_boundary = trainer.soft_boundary(probability).detach()
                identity_source_rows.append(
                    weighted_summary(transport_target, raw_boundary * distance_confidence)
                )

            # Counterfactual 2: feed the exact target image as the observed image.
            # A correct displacement target must be exactly zero in this case.
            probability = trainer.foreground_probability(target_image, boundary_level, polarity)
            target_boundary = trainer.soft_boundary(probability).detach()
            perfect_target_rows.append(
                weighted_summary(transport_target, target_boundary * distance_confidence)
            )

    result = {
        "definition": {
            "current_target": "clamp(target_signed_distance, -1.5, 1.5)",
            "required_identity_property": "aligned input and target must imply zero displacement",
            "interpretation": (
                "Any nonzero result for the perfect-target counterfactual proves that the "
                "current target encodes signed distance across the object boundary rather "
                "than a physical boundary displacement."
            ),
        },
        "identity_source": combine(identity_source_rows),
        "perfect_target_counterfactual": combine(perfect_target_rows),
    }
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()

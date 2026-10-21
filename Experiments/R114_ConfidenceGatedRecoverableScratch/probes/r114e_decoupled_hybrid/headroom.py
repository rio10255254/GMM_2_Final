"""Pre-training fixed-128 causal headroom gate for the R114E hybrid."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np
import torch
from torch.utils.data import DataLoader

from probes.r114d_action_selector.targets import TargetConfig, build_selector_targets
from training.dataset import R114Dataset

from .model import PROBE_ROOT, build_hybrid, parameter_counts


def _target_config(payload: dict[str, Any]) -> TargetConfig:
    return TargetConfig(**{
        key: payload[key]
        for key in (
            "boundary_band_px",
            "gain_margin_gray_squared",
            "clear_error_gray",
            "minimum_candidate_delta_gray",
            "minimum_positive_alpha",
            "identity_hard_negative_max_ratio_to_true_band",
        )
    })


def _mean(values: list[float]) -> float | None:
    finite = [value for value in values if np.isfinite(value)]
    return float(np.mean(finite)) if finite else None


@torch.inference_mode()
def run(
    device: torch.device,
    output_dir: Path,
    batch_size: int = 8,
    workers: int = 0,
) -> dict[str, Any]:
    config = json.loads((PROBE_ROOT / "config.json").read_text(encoding="utf-8"))
    gate = config["headroom_gate"]
    limit = int(gate["fixed_validation_scenes"])
    model = build_hybrid(device).eval()
    if any(parameter.requires_grad for parameter in model.geometry_model.parameters()):
        raise RuntimeError("E20 geometry source is not frozen")
    if any(parameter.requires_grad for parameter in model.profile_model.parameters()):
        raise RuntimeError("E24 profile source is not frozen")
    if torch.count_nonzero(model.selector.acceptance_head.weight) or torch.count_nonzero(
        model.selector.amount_head.weight
    ):
        raise RuntimeError("headroom gate requires an exact-zero selector")
    dataset = R114Dataset("validation", epoch=0, limit=limit)
    loader = DataLoader(
        dataset,
        batch_size=batch_size,
        shuffle=False,
        num_workers=workers,
        pin_memory=device.type == "cuda",
    )
    target_config = _target_config(config)
    rows: list[dict[str, Any]] = []
    record_ids: list[str] = []
    total_positive = 0
    total_actionable = 0
    total_boundary = 0
    total_oracle_sq_gain = 0.0
    exact_e20 = True
    exact_base = True
    max_e20_abs = 0.0
    max_base_abs = 0.0

    for batch in loader:
        source = batch["source"].to(device, non_blocking=True)
        target = batch["target"].to(device, non_blocking=True)
        sdf = batch["sdf"].to(device, non_blocking=True)
        identity = batch["identity"].to(device, non_blocking=True)
        hybrid = model.forward_details(source)
        e20 = model.geometry_model.forward_details(source)
        max_e20_abs = max(max_e20_abs, float((hybrid.output - e20.output).abs().max()))
        max_base_abs = max(max_base_abs, float((hybrid.output - hybrid.base_output).abs().max()))
        exact_e20 = exact_e20 and torch.equal(hybrid.output, e20.output)
        exact_base = exact_base and torch.equal(hybrid.output, hybrid.base_output)
        labels = build_selector_targets(hybrid, target, sdf, identity, target_config)
        actionable = labels.boundary_band & (
            labels.candidate_delta.abs()
            >= target_config.minimum_candidate_delta_gray / 255.0
        )
        best = (hybrid.base_output + labels.best_alpha * labels.candidate_delta).clamp(0, 1)
        base_abs = (hybrid.base_output - target).abs()
        oracle_abs = (best - target).abs()
        base_sq = (hybrid.base_output - target).square()
        oracle_sq = (best - target).square()
        for index in range(source.shape[0]):
            band = labels.boundary_band[index]
            act = actionable[index]
            positive = labels.positive_mask[index]
            band_count = int(band.sum())
            actionable_count = int(act.sum())
            positive_count = int((positive & act).sum())
            sq_gain = float((base_sq[index][band] - oracle_sq[index][band]).mean() * 255.0**2)
            mae_gain = float((base_abs[index][band] - oracle_abs[index][band]).mean() * 255.0)
            total_positive += positive_count
            total_actionable += actionable_count
            total_boundary += band_count
            total_oracle_sq_gain += float((base_sq[index][band] - oracle_sq[index][band]).sum() * 255.0**2)
            row = {
                "record_id": str(batch["record_id"][index]),
                "family": str(batch["family"][index]),
                "challenge": str(batch["challenge"][index]),
                "identity": bool(identity[index]),
                "boundary_pixels": band_count,
                "actionable_pixels": actionable_count,
                "positive_pixels": positive_count,
                "direction_useful_fraction": positive_count / actionable_count if actionable_count else 0.0,
                "oracle_best_boundary_squared_gain_gray2": sq_gain,
                "oracle_best_boundary_mae_gain_gray": mae_gain,
                "candidate_delta_mean_gray": float(hybrid.candidate_delta[index].abs().mean() * 255.0),
                "candidate_delta_max_gray": float(hybrid.candidate_delta[index].abs().max() * 255.0),
                "profile_visibility_mean": float(hybrid.profile_visibility[index].mean()),
            }
            rows.append(row)
            record_ids.append(row["record_id"])

    if len(rows) != limit:
        raise RuntimeError(f"expected {limit} fixed scenes, got {len(rows)}")
    overall_useful = total_positive / max(total_actionable, 1)
    overall_oracle_sq_gain = total_oracle_sq_gain / max(total_boundary, 1)
    positive_scene_fraction = float(np.mean([
        row["oracle_best_boundary_squared_gain_gray2"] > 0.0
        for row in rows if not row["identity"]
    ]))
    family: dict[str, Any] = {}
    for name in sorted({row["family"] for row in rows}):
        selected = [row for row in rows if row["family"] == name]
        family[name] = {
            "scenes": len(selected),
            "direction_useful_fraction_mean": _mean([row["direction_useful_fraction"] for row in selected]),
            "oracle_best_boundary_squared_gain_gray2_mean": _mean([
                row["oracle_best_boundary_squared_gain_gray2"] for row in selected
            ]),
            "oracle_best_boundary_mae_gain_gray_mean": _mean([
                row["oracle_best_boundary_mae_gain_gray"] for row in selected
            ]),
        }
    checks = {
        "selector_zero_output_exactly_e20": exact_e20,
        "selector_zero_output_exactly_base": exact_base,
        "direction_useful_fraction": overall_useful >= float(gate["minimum_direction_useful_fraction"]),
        "oracle_best_gain": overall_oracle_sq_gain >= float(gate["minimum_oracle_best_gain_gray_squared"]),
        "positive_scene_fraction": positive_scene_fraction >= float(gate["minimum_scenes_with_positive_oracle_gain_fraction"]),
    }
    summary = {
        "status": "pass_headroom_gate" if all(checks.values()) else "stop_no_material_headroom",
        "research_probe_only": True,
        "fixed_validation_epoch": 0,
        "evaluated_scenes": len(rows),
        "record_id_sha256": hashlib.sha256("\n".join(record_ids).encode()).hexdigest(),
        "source_provenance": model.provenance,
        "parameter_counts": parameter_counts(model),
        "counterfactual_neutrality": {
            "exact_e20": exact_e20,
            "max_abs_vs_e20": max_e20_abs,
            "exact_base": exact_base,
            "max_abs_vs_base": max_base_abs,
        },
        "headroom": {
            "direction_useful_fraction": overall_useful,
            "oracle_best_boundary_squared_gain_gray2": overall_oracle_sq_gain,
            "scenes_with_positive_oracle_gain_fraction_nonidentity": positive_scene_fraction,
            "total_actionable_pixels": total_actionable,
            "total_positive_pixels": total_positive,
        },
        "thresholds": gate,
        "checks": checks,
        "by_family": family,
        "training_authorized": all(checks.values()),
        "long_or_formal_training_authorized": False,
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    with (output_dir / "per_scene.csv").open("w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    (output_dir / "headroom.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    return summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--device", default="cuda:0" if torch.cuda.is_available() else "cpu")
    parser.add_argument("--output", default=str(PROBE_ROOT / "results" / "fixed128_headroom"))
    parser.add_argument("--batch-size", type=int, default=8)
    parser.add_argument("--workers", type=int, default=0)
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    result = run(torch.device(args.device), Path(args.output), args.batch_size, args.workers)
    print(json.dumps(result, indent=2, ensure_ascii=False))


"""Read-only fixed-validation evaluator for an R114D selector checkpoint."""

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

from probes.r114d_action_selector.adapter import load_selector_model
from probes.r114d_action_selector.targets import TargetConfig, build_selector_targets
from training.dataset import R114Dataset


PROBE_ROOT = Path(__file__).resolve().parent


def _auc(scores: np.ndarray, labels: np.ndarray) -> float | None:
    labels = labels.astype(bool)
    positive = int(labels.sum())
    negative = int((~labels).sum())
    if positive == 0 or negative == 0:
        return None
    order = np.argsort(scores, kind="mergesort")
    sorted_scores = scores[order]
    ranks = np.empty(len(scores), dtype=np.float64)
    start = 0
    while start < len(scores):
        end = start + 1
        while end < len(scores) and sorted_scores[end] == sorted_scores[start]:
            end += 1
        ranks[order[start:end]] = 0.5 * (start + 1 + end)
        start = end
    rank_sum = float(ranks[labels].sum())
    return (rank_sum - positive * (positive + 1) / 2.0) / (positive * negative)


def _ece(scores: np.ndarray, labels: np.ndarray, bins: int = 10) -> float | None:
    if scores.size == 0:
        return None
    total = float(scores.size)
    value = 0.0
    for index in range(bins):
        low, high = index / bins, (index + 1) / bins
        mask = (scores >= low) & (scores < high if index < bins - 1 else scores <= high)
        if not mask.any():
            continue
        value += float(mask.sum()) / total * abs(float(scores[mask].mean()) - float(labels[mask].mean()))
    return value


def _safe_mean(values: list[float | None]) -> float | None:
    finite = [value for value in values if value is not None and np.isfinite(value)]
    return float(np.mean(finite)) if finite else None


def _safe_max(values: list[float]) -> float | None:
    return float(np.max(values)) if values else None


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


@torch.inference_mode()
def evaluate(
    checkpoint: Path,
    output_dir: Path,
    device: torch.device,
    limit: int = 128,
    batch_size: int = 8,
    workers: int = 0,
) -> dict[str, Any]:
    if not 1 <= limit <= 128:
        raise ValueError("fixed R114D evaluator limit must be in [1, 128]")
    model = load_selector_model(checkpoint, device)
    if any(parameter.requires_grad for parameter in model.parameters()):
        raise RuntimeError("read-only evaluator loaded trainable parameters")
    dataset = R114Dataset("validation", epoch=0, limit=limit)
    loader = DataLoader(
        dataset,
        batch_size=batch_size,
        shuffle=False,
        num_workers=workers,
        pin_memory=device.type == "cuda",
    )
    target_config = TargetConfig.from_json()
    scene_rows: list[dict[str, Any]] = []
    calibration_scores: list[np.ndarray] = []
    calibration_labels: list[np.ndarray] = []
    amount_scores: list[np.ndarray] = []
    amount_labels: list[np.ndarray] = []
    identity_selector_mean: list[float] = []
    identity_selector_max: list[float] = []
    identity_base_mae: list[float] = []
    identity_final_mae: list[float] = []
    record_ids: list[str] = []

    for batch in loader:
        source = batch["source"].to(device, non_blocking=True)
        target = batch["target"].to(device, non_blocking=True)
        sdf = batch["sdf"].to(device, non_blocking=True)
        identity = batch["identity"].to(device, non_blocking=True)
        prediction = model.forward_details(source)
        labels = build_selector_targets(prediction, target, sdf, identity, target_config)
        boundary = labels.boundary_band
        base_abs = (prediction.base_output - target).abs()
        final_abs = (prediction.output - target).abs()
        base_sq = (prediction.base_output - target).square()
        final_sq = (prediction.output - target).square()
        for index in range(source.shape[0]):
            band = boundary[index]
            band_count = int(band.sum())
            base_band = (
                float(base_abs[index][band].mean() * 255.0) if band_count else None
            )
            final_band = (
                float(final_abs[index][band].mean() * 255.0) if band_count else None
            )
            realized_sq_gain = (
                float(
                    (base_sq[index][band] - final_sq[index][band]).mean()
                    * (255.0 ** 2)
                )
                if band_count
                else None
            )
            selected = prediction.selected_delta[index].abs() > 0
            selected_band = selected & band
            helpful = (
                (target[index] - prediction.base_output[index])
                * prediction.selected_delta[index]
            ) > 0
            selected_count = int(selected_band.sum())
            actionable = band & (
                labels.candidate_delta[index].abs()
                >= target_config.minimum_candidate_delta_gray / 255.0
            )
            actionable_count = int(actionable.sum())
            positive = labels.positive_mask[index]
            positive_count = int(positive.sum())
            scene_rows.append(
                {
                    "record_id": batch["record_id"][index],
                    "family": batch["family"][index],
                    "challenge": batch["challenge"][index],
                    "identity": bool(identity[index]),
                    "base_mae_gray": float(base_abs[index].mean() * 255.0),
                    "final_mae_gray": float(final_abs[index].mean() * 255.0),
                    "base_boundary_mae_gray": base_band,
                    "final_boundary_mae_gray": final_band,
                    "boundary_mae_gain_gray": (
                        base_band - final_band if band_count else None
                    ),
                    "boundary_squared_gain_gray2": realized_sq_gain,
                    "direction_helpful_fraction_when_selected": (
                        float(helpful[selected_band].float().mean()) if selected_count else None
                    ),
                    "proposal_direction_useful_fraction": (
                        positive_count / actionable_count if actionable_count else None
                    ),
                    "proposal_best_gain_gray2": (
                        float(labels.signed_gain[index][actionable].mean() * (255.0 ** 2))
                        if actionable_count
                        else None
                    ),
                    "proposal_best_alpha_mean": (
                        float(labels.best_alpha[index][positive].mean())
                        if positive_count
                        else None
                    ),
                    "acceptance_mean": float(prediction.acceptance[index].mean()),
                    "amount_mean": float(prediction.amount[index].mean()),
                    "selector_delta_mean_gray": float(
                        prediction.selected_delta[index].abs().mean() * 255.0
                    ),
                    "selector_delta_max_gray": float(
                        prediction.selected_delta[index].abs().max() * 255.0
                    ),
                }
            )
            record_ids.append(str(batch["record_id"][index]))
            support = labels.supervision_mask[index]
            if bool(support.any()):
                calibration_scores.append(
                    prediction.acceptance[index][support].float().cpu().numpy()
                )
                calibration_labels.append(
                    labels.acceptance[index][support].float().cpu().numpy()
                )
            positive = labels.positive_mask[index]
            if bool(positive.any()):
                amount_scores.append(prediction.amount[index][positive].float().cpu().numpy())
                amount_labels.append(labels.amount[index][positive].float().cpu().numpy())
            if bool(identity[index]):
                identity_selector_mean.append(
                    float(prediction.selected_delta[index].abs().mean() * 255.0)
                )
                identity_selector_max.append(
                    float(prediction.selected_delta[index].abs().max() * 255.0)
                )
                identity_base_mae.append(float(base_abs[index].mean() * 255.0))
                identity_final_mae.append(float(final_abs[index].mean() * 255.0))

    if len(scene_rows) != limit:
        raise RuntimeError(f"evaluator produced {len(scene_rows)} rows for requested {limit}")
    scores = np.concatenate(calibration_scores) if calibration_scores else np.empty(0)
    binary = np.concatenate(calibration_labels) if calibration_labels else np.empty(0)
    amounts = np.concatenate(amount_scores) if amount_scores else np.empty(0)
    amount_truth = np.concatenate(amount_labels) if amount_labels else np.empty(0)
    positive_mask = binary > 0.5
    negative_mask = ~positive_mask
    amount_correlation = None
    if amounts.size > 1 and float(amounts.std()) > 0 and float(amount_truth.std()) > 0:
        amount_correlation = float(np.corrcoef(amounts, amount_truth)[0, 1])
    summary = {
        "status": "complete",
        "read_only": True,
        "fixed_validation_epoch": 0,
        "requested_scenes": limit,
        "evaluated_scenes": len(scene_rows),
        "record_id_sha256": hashlib.sha256("\n".join(record_ids).encode("utf-8")).hexdigest(),
        "checkpoint": getattr(model, "checkpoint_metadata", {}),
        "mae": {
            "base_gray": _safe_mean([row["base_mae_gray"] for row in scene_rows]),
            "final_gray": _safe_mean([row["final_mae_gray"] for row in scene_rows]),
            "base_boundary_gray": _safe_mean([row["base_boundary_mae_gray"] for row in scene_rows]),
            "final_boundary_gray": _safe_mean([row["final_boundary_mae_gray"] for row in scene_rows]),
            "boundary_gain_gray": _safe_mean([row["boundary_mae_gain_gray"] for row in scene_rows]),
        },
        "direction_and_gain": {
            "mean_boundary_squared_gain_gray2": _safe_mean(
                [row["boundary_squared_gain_gray2"] for row in scene_rows]
            ),
            "mean_helpful_fraction_when_selected": _safe_mean(
                [row["direction_helpful_fraction_when_selected"] for row in scene_rows]
            ),
            "proposal_direction_useful_fraction": _safe_mean(
                [row["proposal_direction_useful_fraction"] for row in scene_rows]
            ),
            "proposal_best_gain_gray2": _safe_mean(
                [row["proposal_best_gain_gray2"] for row in scene_rows]
            ),
            "proposal_best_alpha_mean": _safe_mean(
                [row["proposal_best_alpha_mean"] for row in scene_rows]
            ),
            "scenes_with_positive_boundary_mae_gain_fraction": float(
                np.mean([
                    row["boundary_mae_gain_gray"] > 0
                    for row in scene_rows
                    if row["boundary_mae_gain_gray"] is not None
                ])
            ),
            "scenes_with_negative_boundary_mae_gain_fraction": float(
                np.mean([
                    row["boundary_mae_gain_gray"] < 0
                    for row in scene_rows
                    if row["boundary_mae_gain_gray"] is not None
                ])
            ),
        },
        "acceptance_calibration": {
            "support_pixels": int(scores.size),
            "positive_pixels": int(positive_mask.sum()),
            "negative_pixels": int(negative_mask.sum()),
            "auc": _auc(scores, binary) if scores.size else None,
            "brier": float(np.mean((scores - binary) ** 2)) if scores.size else None,
            "ece_10bin": _ece(scores, binary),
            "positive_mean": float(scores[positive_mask].mean()) if positive_mask.any() else None,
            "negative_mean": float(scores[negative_mask].mean()) if negative_mask.any() else None,
            "active_fraction": float(np.mean(scores > 0)) if scores.size else None,
        },
        "amount_calibration_on_positive": {
            "pixels": int(amounts.size),
            "mae": float(np.mean(np.abs(amounts - amount_truth))) if amounts.size else None,
            "prediction_mean": float(amounts.mean()) if amounts.size else None,
            "target_mean": float(amount_truth.mean()) if amount_truth.size else None,
            "pearson": amount_correlation,
        },
        "identity": {
            "scenes": len(identity_selector_mean),
            "selector_delta_mean_gray": _safe_mean(identity_selector_mean),
            "selector_delta_max_gray": _safe_max(identity_selector_max),
            "base_mae_gray": _safe_mean(identity_base_mae),
            "final_mae_gray": _safe_mean(identity_final_mae),
        },
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    _write_csv(output_dir / "per_scene.csv", scene_rows)
    (output_dir / "evaluation.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    return summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--checkpoint", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--device", default="cuda:0" if torch.cuda.is_available() else "cpu")
    parser.add_argument("--limit", type=int, default=128)
    parser.add_argument("--batch-size", type=int, default=8)
    parser.add_argument("--workers", type=int, default=0)
    return parser.parse_args()


if __name__ == "__main__":
    arguments = parse_args()
    result = evaluate(
        checkpoint=Path(arguments.checkpoint),
        output_dir=Path(arguments.output),
        device=torch.device(arguments.device),
        limit=arguments.limit,
        batch_size=arguments.batch_size,
        workers=arguments.workers,
    )
    print(json.dumps(result, indent=2, ensure_ascii=False))

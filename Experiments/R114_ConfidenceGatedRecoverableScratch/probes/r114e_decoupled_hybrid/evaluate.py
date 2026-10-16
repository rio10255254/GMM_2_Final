"""Read-only fixed-validation evaluator for an R114E selector checkpoint."""

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

from training.dataset import R114Dataset

from .adapter import load_selector_model
from .targets import build_selector_targets, load_target_config


def _auc(scores: np.ndarray, labels: np.ndarray) -> float | None:
    labels = labels.astype(bool)
    positives = int(labels.sum())
    negatives = int((~labels).sum())
    if positives == 0 or negatives == 0:
        return None
    order = np.argsort(scores, kind="mergesort")
    sorted_scores = scores[order]
    ranks = np.empty(scores.size, dtype=np.float64)
    start = 0
    while start < scores.size:
        end = start + 1
        while end < scores.size and sorted_scores[end] == sorted_scores[start]:
            end += 1
        ranks[order[start:end]] = 0.5 * (start + 1 + end)
        start = end
    return float(
        (ranks[labels].sum() - positives * (positives + 1) / 2.0)
        / (positives * negatives)
    )


def _mean(values: list[float]) -> float | None:
    finite = [value for value in values if np.isfinite(value)]
    return float(np.mean(finite)) if finite else None


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
        raise ValueError("fixed R114E evaluator limit must be in [1, 128]")
    model = load_selector_model(checkpoint, device)
    if any(parameter.requires_grad for parameter in model.parameters()):
        raise RuntimeError("read-only evaluator loaded trainable parameters")
    dataset = R114Dataset("validation", epoch=0, limit=limit)
    loader = DataLoader(
        dataset, batch_size=batch_size, shuffle=False, num_workers=workers,
        pin_memory=device.type == "cuda",
    )
    target_config = load_target_config()
    rows: list[dict[str, Any]] = []
    score_parts: list[np.ndarray] = []
    label_parts: list[np.ndarray] = []
    amount_parts: list[np.ndarray] = []
    amount_truth_parts: list[np.ndarray] = []
    record_ids: list[str] = []
    for batch in loader:
        source = batch["source"].to(device, non_blocking=True)
        target = batch["target"].to(device, non_blocking=True)
        sdf = batch["sdf"].to(device, non_blocking=True)
        identity = batch["identity"].to(device, non_blocking=True)
        prediction = model.forward_details(source)
        labels = build_selector_targets(prediction, target, sdf, identity, target_config)
        base_abs = (prediction.base_output - target).abs()
        final_abs = (prediction.output - target).abs()
        base_sq = (prediction.base_output - target).square()
        final_sq = (prediction.output - target).square()
        for index in range(source.shape[0]):
            band = labels.boundary_band[index]
            selected = band & (prediction.selected_delta[index].abs() > 0)
            helpful = (
                (target[index] - prediction.base_output[index])
                * prediction.selected_delta[index]
            ) > 0
            base_band = float(base_abs[index][band].mean() * 255.0)
            final_band = float(final_abs[index][band].mean() * 255.0)
            rows.append({
                "record_id": str(batch["record_id"][index]),
                "family": str(batch["family"][index]),
                "challenge": str(batch["challenge"][index]),
                "identity": bool(identity[index]),
                "base_mae_gray": float(base_abs[index].mean() * 255.0),
                "final_mae_gray": float(final_abs[index].mean() * 255.0),
                "base_boundary_mae_gray": base_band,
                "final_boundary_mae_gray": final_band,
                "boundary_mae_gain_gray": base_band - final_band,
                "boundary_squared_gain_gray2": float(
                    (base_sq[index][band] - final_sq[index][band]).mean() * 255.0**2
                ),
                "selected_helpful_fraction": float(helpful[selected].float().mean()) if bool(selected.any()) else None,
                "acceptance_mean": float(prediction.acceptance[index].mean()),
                "amount_mean": float(prediction.amount[index].mean()),
                "selected_delta_mean_gray": float(prediction.selected_delta[index].abs().mean() * 255.0),
                "selected_delta_max_gray": float(prediction.selected_delta[index].abs().max() * 255.0),
            })
            record_ids.append(rows[-1]["record_id"])
            support = labels.supervision_mask[index]
            if bool(support.any()):
                score_parts.append(prediction.acceptance[index][support].float().cpu().numpy())
                label_parts.append(labels.acceptance[index][support].float().cpu().numpy())
            positive = labels.positive_mask[index]
            if bool(positive.any()):
                amount_parts.append(prediction.amount[index][positive].float().cpu().numpy())
                amount_truth_parts.append(labels.amount[index][positive].float().cpu().numpy())
    if len(rows) != limit:
        raise RuntimeError(f"expected {limit} rows, got {len(rows)}")
    scores = np.concatenate(score_parts) if score_parts else np.empty(0)
    labels_np = np.concatenate(label_parts) if label_parts else np.empty(0)
    amounts = np.concatenate(amount_parts) if amount_parts else np.empty(0)
    amounts_true = np.concatenate(amount_truth_parts) if amount_truth_parts else np.empty(0)
    identity_rows = [row for row in rows if row["identity"]]
    summary = {
        "status": "complete",
        "read_only": True,
        "fixed_validation_epoch": 0,
        "evaluated_scenes": len(rows),
        "record_id_sha256": hashlib.sha256("\n".join(record_ids).encode()).hexdigest(),
        "checkpoint": model.checkpoint_metadata,
        "mae": {
            "base_gray": _mean([row["base_mae_gray"] for row in rows]),
            "final_gray": _mean([row["final_mae_gray"] for row in rows]),
            "base_boundary_gray": _mean([row["base_boundary_mae_gray"] for row in rows]),
            "final_boundary_gray": _mean([row["final_boundary_mae_gray"] for row in rows]),
            "boundary_gain_gray": _mean([row["boundary_mae_gain_gray"] for row in rows]),
        },
        "selection": {
            "boundary_squared_gain_gray2": _mean([row["boundary_squared_gain_gray2"] for row in rows]),
            "selected_helpful_fraction": _mean([
                row["selected_helpful_fraction"] for row in rows
                if row["selected_helpful_fraction"] is not None
            ]),
            "positive_scene_fraction": float(np.mean([row["boundary_mae_gain_gray"] > 0 for row in rows])),
            "negative_scene_fraction": float(np.mean([row["boundary_mae_gain_gray"] < 0 for row in rows])),
        },
        "acceptance": {
            "support_pixels": int(scores.size),
            "positive_pixels": int((labels_np > 0.5).sum()),
            "negative_pixels": int((labels_np <= 0.5).sum()),
            "auc": _auc(scores, labels_np) if scores.size else None,
            "brier": float(np.mean((scores - labels_np) ** 2)) if scores.size else None,
        },
        "amount_on_positive": {
            "pixels": int(amounts.size),
            "mae": float(np.mean(np.abs(amounts - amounts_true))) if amounts.size else None,
            "prediction_mean": float(amounts.mean()) if amounts.size else None,
            "target_mean": float(amounts_true.mean()) if amounts.size else None,
        },
        "identity": {
            "scenes": len(identity_rows),
            "selected_delta_mean_gray": _mean([row["selected_delta_mean_gray"] for row in identity_rows]),
            "selected_delta_max_gray": max([row["selected_delta_max_gray"] for row in identity_rows], default=None),
            "boundary_gain_gray": _mean([row["boundary_mae_gain_gray"] for row in identity_rows]),
        },
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    with (output_dir / "per_scene.csv").open("w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
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
    args = parse_args()
    result = evaluate(
        Path(args.checkpoint), Path(args.output), torch.device(args.device),
        args.limit, args.batch_size, args.workers,
    )
    print(json.dumps(result, indent=2, ensure_ascii=False))


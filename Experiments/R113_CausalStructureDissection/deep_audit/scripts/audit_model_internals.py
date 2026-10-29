"""Checkpoint, representation-invariance, and effective-receptive-field audit."""
from __future__ import annotations

import json
import math
import sys
from datetime import datetime
from pathlib import Path

import cv2
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import torch
import torch.nn.functional as F
from sklearn.metrics import average_precision_score, roc_auc_score
PROJECT_ROOT = Path(__file__).resolve().parents[4]


ROOT = Path(__file__).resolve().parents[1]
CONFIG = json.loads((ROOT / "config" / "experiment.json").read_text(encoding="utf-8"))
R109 = Path(PROJECT_ROOT / CONFIG["sources"]["r109_root"])
OUTPUT = ROOT / "results" / "model_internals"
OUTPUT.mkdir(parents=True, exist_ok=True)
sys.path.insert(0, str(R109 / "model"))
sys.path.insert(0, str(R109 / "training"))
from r109_model import build_model, gradients
from r109_dataset import R109Dataset


DEVICE = torch.device("cpu")
CHECKPOINT_ROOT = R109 / "runs" / "r109_formal_scratch_continuous_b8_20260826" / "weights"


def selected_indices(limit: int = 24) -> list[int]:
    dataset = R109Dataset("validation", epoch=0)
    selected = []
    family_counts = {}
    for index, record in enumerate(dataset.records):
        family = str(record["family"])
        if family_counts.get(family, 0) < 2:
            selected.append(index)
            family_counts[family] = family_counts.get(family, 0) + 1
        if len(selected) >= limit:
            break
    return selected


def batch_for(indices: list[int], epoch: int, observation: int = 0) -> tuple[dict[str, torch.Tensor], list[dict[str, object]]]:
    dataset = R109Dataset("validation", epoch=epoch)
    tensors = {name: [] for name in ("source", "target", "mask", "edge", "identity", "midpoint", "polarity")}
    metadata = []
    for index in indices:
        item = dataset[index]
        for name in tensors:
            tensors[name].append(item[name][observation : observation + 1])
        metadata.append({"scene_index": int(item["scene_index"]), "family": str(item["family"]), "role": str(item["role"]), "challenge": str(item["challenge"])})
    return {name: torch.cat(values, 0).to(DEVICE) for name, values in tensors.items()}, metadata


def source_and_learned_support(model, source: torch.Tensor, boundary: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
    cues = model.cues(source)
    magnitude = cues["magnitude"].float()
    local_scale = cues["local_scale"].float()
    source_support = ((magnitude / (local_scale + 2 / 255) - .05) / 1.10).clamp(0, 1)
    learned = (.85 * F.max_pool2d(boundary.float(), 9, 1, 4)).clamp(0, 1)
    return source_support, learned


def feature_activations(model, source: torch.Tensor) -> dict[str, torch.Tensor]:
    cues = model.cues(source)
    detector_stem = F.silu(model.detector_stem(cues["features"]))
    detector_tower = model.detector_tower(detector_stem)
    renderer_stem = F.silu(model.renderer_stem(cues["features"]))
    renderer_tower = model.renderer_tower(renderer_stem)
    return {
        "cues": cues["features"],
        "detector_stem": detector_stem,
        "detector_tower": detector_tower,
        "renderer_stem": renderer_stem,
        "renderer_tower": renderer_tower,
    }


def checkpoint_row(model, batch: dict, epoch: int) -> dict[str, object]:
    with torch.no_grad():
        activations = feature_activations(model, batch["source"])
        details = model.forward_details(batch["source"])
        target_boundary = F.max_pool2d(batch["edge"], 5, 1, 2).clamp(0, 1)
        source_support, learned_support = source_and_learned_support(model, batch["source"], details.boundary)
        truth = (target_boundary > .5).cpu().numpy().ravel().astype(np.uint8)
        score = details.boundary.cpu().numpy().ravel()
        if truth.min() == truth.max():
            auc = ap = float("nan")
        else:
            auc = float(roc_auc_score(truth, score))
            ap = float(average_precision_score(truth, score))
        predicted = details.boundary > .5
        target_binary = target_boundary > .5
        intersection = float((predicted & target_binary).sum())
        dice = (2 * intersection + 1) / (float(predicted.sum() + target_binary.sum()) + 1)
        outside = target_boundary < .05
        inside = target_boundary > .5
        detector_raw = activations["detector_tower"]
        renderer_raw = activations["renderer_tower"]
        row = {
            "epoch": epoch,
            "cases": len(batch["source"]),
            "boundary_mean": float(details.boundary.mean()),
            "boundary_spatial_std": float(details.boundary.flatten(1).std(dim=1).mean()),
            "boundary_p05": float(torch.quantile(details.boundary, .05)),
            "boundary_p95": float(torch.quantile(details.boundary, .95)),
            "boundary_auc": auc,
            "boundary_average_precision": ap,
            "boundary_dice_at_0p5": float(dice),
            "target_boundary_fraction": float(target_binary.float().mean()),
            "learned_support_mean": float(learned_support.mean()),
            "learned_support_spatial_std": float(learned_support.flatten(1).std(dim=1).mean()),
            "source_support_mean": float(source_support.mean()),
            "learned_support_dominance_fraction": float((learned_support > source_support).float().mean()),
            "final_support_outside_boundary_mean": float(details.support[outside].mean()),
            "final_support_inside_boundary_mean": float(details.support[inside].mean()),
            "width_gain_mean": float(details.width_gain.mean()),
            "width_gain_spatial_std": float(details.width_gain.flatten(1).std(dim=1).mean()),
            "width_gain_p05": float(torch.quantile(details.width_gain, .05)),
            "width_gain_p95": float(torch.quantile(details.width_gain, .95)),
            "shift_abs_mean_px": float(details.normal_shift.abs().mean()),
            "shift_abs_p95_px": float(torch.quantile(details.normal_shift.abs(), .95)),
            "delta_abs_mean_gray": float(details.delta.abs().mean() * 255),
            "delta_low_frequency_abs_mean_gray": float(F.avg_pool2d(details.delta, 17, 1, 8).abs().mean() * 255),
            "detector_tanh_saturation_fraction": float((torch.tanh(detector_raw).abs() > .95).float().mean()),
            "renderer_tanh_saturation_fraction": float((torch.tanh(renderer_raw).abs() > .95).float().mean()),
            "boundary_head_weight_norm": float(model.boundary_head.weight.norm()),
            "boundary_head_bias": float(model.boundary_head.bias),
            "width_head_weight_norm": float(model.width_head.weight.norm()),
            "width_head_bias": float(model.width_head.bias),
            "shift_head_weight_norm": float(model.shift_head.weight.norm()),
            "shift_head_bias": float(model.shift_head.bias),
        }
        return row


def downsample_vector(value: torch.Tensor, size: int = 16) -> np.ndarray:
    reduced = F.adaptive_avg_pool2d(value.float(), (size, size)).cpu().numpy()
    return reduced.reshape(reduced.shape[0], -1)


def vector_cosine(first: np.ndarray, second: np.ndarray) -> float:
    first = first - first.mean()
    second = second - second.mean()
    denominator = float(np.linalg.norm(first) * np.linalg.norm(second))
    return 0.0 if denominator <= 1e-12 else float(np.dot(first, second) / denominator)


def representation_invariance(model, indices: list[int]) -> tuple[pd.DataFrame, dict[str, object]]:
    storage: dict[int, dict[str, dict[str, np.ndarray]]] = {index: {} for index in indices}
    challenge_by_index: dict[int, dict[str, int]] = {index: {} for index in indices}
    with torch.no_grad():
        for epoch in range(6):
            batch, metadata = batch_for(indices, epoch, 0)
            activations = feature_activations(model, batch["source"])
            details = model.forward_details(batch["source"])
            maps = {
                **activations,
                "boundary": details.boundary,
                "support": details.support,
                "width": details.width_gain,
                "shift": details.normal_shift,
                "delta": details.delta,
            }
            vectors = {name: downsample_vector(value) for name, value in maps.items()}
            for batch_index, original_index in enumerate(indices):
                challenge = metadata[batch_index]["challenge"]
                storage[original_index][challenge] = {name: value[batch_index] for name, value in vectors.items()}
                challenge_by_index[original_index][challenge] = epoch
    rows = []
    layers = next(iter(next(iter(storage.values())).values())).keys()
    for original_index in indices:
        challenges = sorted(storage[original_index])
        for left_index, left in enumerate(challenges):
            for right in challenges[left_index + 1 :]:
                for layer in layers:
                    rows.append({
                        "relation": "same_shape_different_condition",
                        "scene_index": int(R109Dataset("validation", epoch=0).records[original_index]["scene_index"]),
                        "left": left,
                        "right": right,
                        "layer": layer,
                        "cosine": vector_cosine(storage[original_index][left][layer], storage[original_index][right][layer]),
                        "mean_abs_difference": float(np.mean(np.abs(storage[original_index][left][layer] - storage[original_index][right][layer]))),
                    })
    canonical = {}
    for original_index in indices:
        challenge = "standard" if "standard" in storage[original_index] else sorted(storage[original_index])[0]
        canonical[original_index] = storage[original_index][challenge]
    for left_position, left in enumerate(indices):
        for right in indices[left_position + 1 :]:
            for layer in layers:
                rows.append({
                    "relation": "different_shape",
                    "scene_index": -1,
                    "left": str(left),
                    "right": str(right),
                    "layer": layer,
                    "cosine": vector_cosine(canonical[left][layer], canonical[right][layer]),
                    "mean_abs_difference": float(np.mean(np.abs(canonical[left][layer] - canonical[right][layer]))),
                })
    frame = pd.DataFrame(rows)
    summary = {}
    for layer in layers:
        same = frame.loc[(frame.layer == layer) & (frame.relation == "same_shape_different_condition")]
        different = frame.loc[(frame.layer == layer) & (frame.relation == "different_shape")]
        summary[layer] = {
            "same_shape_condition_cosine_median": float(same.cosine.median()),
            "different_shape_cosine_median": float(different.cosine.median()),
            "condition_invariance_margin": float(same.cosine.median() - different.cosine.median()),
            "same_shape_mean_abs_difference_median": float(same.mean_abs_difference.median()),
            "different_shape_mean_abs_difference_median": float(different.mean_abs_difference.median()),
        }
    return frame, summary


def erf_statistics(gradient: np.ndarray, center: tuple[int, int]) -> dict[str, float]:
    energy = np.abs(gradient).astype(np.float64)
    total = float(energy.sum())
    if total <= 1e-20:
        return {
            "radius_50pct_px": 0.0,
            "radius_90pct_px": 0.0,
            "radius_99pct_px": 0.0,
            "support_max_radius_px": 0.0,
            "support_height_px": 0,
            "support_width_px": 0,
            "gradient_total": total,
        }
    yy, xx = np.indices(energy.shape)
    radius = np.sqrt((yy - center[0]) ** 2 + (xx - center[1]) ** 2)
    order = np.argsort(radius.ravel())
    cumulative = np.cumsum(energy.ravel()[order]) / max(total, 1e-20)
    sorted_radius = radius.ravel()[order]
    result = {}
    for fraction in (.5, .9, .99):
        position = min(int(np.searchsorted(cumulative, fraction)), len(sorted_radius) - 1)
        result[f"radius_{int(fraction * 100)}pct_px"] = float(sorted_radius[position])
    threshold = energy.max() * 1e-7
    support = energy > threshold
    sy, sx = np.nonzero(support)
    result["support_max_radius_px"] = float(radius[support].max()) if support.any() else 0.0
    result["support_height_px"] = int(sy.max() - sy.min() + 1) if len(sy) else 0
    result["support_width_px"] = int(sx.max() - sx.min() + 1) if len(sx) else 0
    result["gradient_total"] = total
    return result


def effective_receptive_field(model, index: int) -> tuple[dict[str, object], Path]:
    item = R109Dataset("validation", epoch=0)[index]
    edge = item["edge"][0, 0].numpy()
    central = edge.copy()
    central[:48] = 0; central[-48:] = 0; central[:, :48] = 0; central[:, -48:] = 0
    y, x = np.unravel_index(np.argmax(central), central.shape)
    fields = ("delta", "boundary", "width_gain", "normal_shift")
    maps = {}
    summary = {}
    for field in fields:
        source = item["source"][0:1].clone().to(DEVICE).requires_grad_(True)
        details = model.forward_details(source)
        scalar = getattr(details, field)[0, 0, y, x]
        gradient = torch.autograd.grad(scalar, source, retain_graph=False)[0][0, 0].detach().cpu().numpy()
        maps[field] = gradient
        summary[field] = erf_statistics(gradient, (y, x))
    figure, axes = plt.subplots(1, len(fields), figsize=(16, 4))
    for axis, field in zip(axes, fields):
        image = np.log10(np.abs(maps[field]) + 1e-12)
        axis.imshow(image, cmap="magma")
        axis.scatter([x], [y], s=15, c="cyan")
        axis.set_title(field)
        axis.axis("off")
    figure.tight_layout()
    path = OUTPUT / "effective_receptive_field.png"
    figure.savefig(path, dpi=180)
    plt.close(figure)
    theoretical_radius = 3 * max(R109_CONFIG["model"]["blur_scales_px"]) + 1 + 2 * sum(R109_CONFIG["model"]["dilations"]) + R109_CONFIG["model"]["local_range_window_px"] // 2 + R109_CONFIG["model"]["maximum_normal_shift_px"]
    return {"scene_index": int(item["scene_index"]), "probe_y": int(y), "probe_x": int(x), "fields": summary, "conservative_theoretical_radius_px": float(theoretical_radius)}, path


R109_CONFIG = json.loads((R109 / "config" / "experiment.json").read_text(encoding="utf-8"))


def main() -> int:
    indices = selected_indices(int(CONFIG["representation_cases"]) // 2)
    checkpoint_indices = indices[:8]
    base_batch, _ = batch_for(checkpoint_indices, 0, 0)
    rows = []
    model = build_model().to(DEVICE).eval()
    for epoch in CONFIG["checkpoint_epochs"]:
        checkpoint = torch.load(CHECKPOINT_ROOT / f"epoch_{int(epoch):03d}.pth", map_location=DEVICE, weights_only=False)
        model.load_state_dict(checkpoint["model"])
        rows.append(checkpoint_row(model, base_batch, int(epoch)))
        print(json.dumps({"checkpoint_epoch": epoch}), flush=True)
    checkpoint_frame = pd.DataFrame(rows)
    checkpoint_frame.to_csv(OUTPUT / "checkpoint_internal_dynamics.csv", index=False, encoding="utf-8-sig")

    final_checkpoint = torch.load(Path(PROJECT_ROOT / CONFIG["sources"]["r109_checkpoint"]), map_location=DEVICE, weights_only=False)
    model.load_state_dict(final_checkpoint["model"])
    invariance, invariance_summary = representation_invariance(model, indices[:12])
    invariance.to_csv(OUTPUT / "representation_invariance_pairs.csv", index=False, encoding="utf-8-sig")
    erf, erf_path = effective_receptive_field(model, indices[0])
    result = {
        "status": "complete",
        "generated_local": datetime.now().astimezone().isoformat(),
        "device": str(DEVICE),
        "checkpoint_cases": len(checkpoint_indices),
        "checkpoint_dynamics": rows,
        "representation_invariance": invariance_summary,
        "effective_receptive_field": erf,
        "erf_figure": str(erf_path),
        "interpretation_boundary": "ERF measures local differential sensitivity at one representative boundary pixel. It does not describe every nonlinear input region.",
    }
    (OUTPUT / "analysis_summary.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

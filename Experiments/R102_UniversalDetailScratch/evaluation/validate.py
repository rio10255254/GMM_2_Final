"""Eight-axis synthetic validation and fixed real-image previews for R102."""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path
from typing import Any

import cv2
import numpy as np
import torch
import torch.nn.functional as F


ROOT = Path(__file__).resolve().parents[1]
for folder in (ROOT / "training", ROOT / "inference"):
    if str(folder) not in sys.path:
        sys.path.insert(0, str(folder))

from losses import central_crop, gradient_magnitude, highpass, warp_tensor  # noqa: E402
PROJECT_ROOT = Path(__file__).resolve().parents[3]


CONFIG = json.loads((ROOT / "config" / "experiment.json").read_text(encoding="utf-8"))


def _centroid(probability: torch.Tensor) -> torch.Tensor:
    n, _c, h, w = probability.shape
    yy = torch.arange(h, device=probability.device, dtype=probability.dtype).view(1, 1, h, 1)
    xx = torch.arange(w, device=probability.device, dtype=probability.dtype).view(1, 1, 1, w)
    mass = probability.sum(dim=(-2, -1), keepdim=True).clamp_min(1e-6)
    cx = (probability * xx).sum(dim=(-2, -1), keepdim=True) / mass
    cy = (probability * yy).sum(dim=(-2, -1), keepdim=True) / mass
    return torch.cat([cx.flatten(1), cy.flatten(1)], dim=1)


def _probability(image: torch.Tensor, midpoint: torch.Tensor, polarity: torch.Tensor) -> torch.Tensor:
    return torch.sigmoid(polarity.view(-1, 1, 1, 1) * (image - midpoint.view(-1, 1, 1, 1)) / 0.035)


@torch.inference_mode()
def evaluate(model: torch.nn.Module, loader: Any, device: torch.device, core_size: int, amp_enabled: bool) -> dict[str, Any]:
    model.eval()
    sums: dict[str, float] = {
        "absolute_error": 0.0,
        "squared_error": 0.0,
        "contour_iou": 0.0,
        "texture_recovery": 0.0,
        "identity_change": 0.0,
        "flat_false_detail": 0.0,
        "paired_error": 0.0,
        "centroid_error_px": 0.0,
    }
    counts = {key: 0 for key in sums}
    first_source: torch.Tensor | None = None
    for batch in loader:
        source = batch["source"].to(device, non_blocking=True)
        target = batch["target"].to(device, non_blocking=True)
        mask = batch["mask"].to(device, non_blocking=True)
        b, v, c, h, w = source.shape
        flat_source = source.reshape(b * v, c, h, w).contiguous(memory_format=torch.channels_last)
        flat_target = target.reshape(b * v, c, h, w)
        flat_mask = mask.reshape(b * v, c, h, w)
        midpoint = batch["midpoint"].to(device).repeat_interleave(v)
        polarity = batch["polarity"].to(device).repeat_interleave(v)
        mode = batch["mode"].to(device).repeat_interleave(v)
        identity = batch["identity"].to(device).reshape(-1)
        motion = batch["motion"].to(device).reshape(-1, 2)
        with torch.autocast(device_type="cuda", dtype=torch.bfloat16, enabled=amp_enabled):
            prediction = model(flat_source)
        prediction = central_crop(prediction.float(), core_size)
        source_core = central_crop(flat_source.float(), core_size)
        target_core = central_crop(flat_target.float(), core_size)
        mask_core = central_crop(flat_mask.float(), core_size)
        if first_source is None:
            first_source = flat_source[:1].detach()

        error = prediction - target_core
        sums["absolute_error"] += float(error.abs().sum())
        sums["squared_error"] += float(error.square().sum())
        counts["absolute_error"] += error.numel()
        counts["squared_error"] += error.numel()

        probability = _probability(prediction, midpoint, polarity)
        binary = probability >= 0.5
        truth = mask_core >= 0.5
        intersection = (binary & truth).flatten(1).sum(dim=1).float()
        union = (binary | truth).flatten(1).sum(dim=1).float()
        valid = union > 0
        if bool(valid.any()):
            sums["contour_iou"] += float(((intersection[valid] + 1.0) / (union[valid] + 1.0)).sum())
            counts["contour_iou"] += int(valid.sum())
            centroid_error = torch.linalg.vector_norm(_centroid(probability[valid]) - _centroid(mask_core[valid]), dim=1)
            sums["centroid_error_px"] += float(centroid_error.sum())
            counts["centroid_error_px"] += int(valid.sum())

        source_gap = (highpass(source_core, 3) - highpass(target_core, 3)).abs().flatten(1).mean(dim=1)
        prediction_gap = (highpass(prediction, 3) - highpass(target_core, 3)).abs().flatten(1).mean(dim=1)
        recoverable = source_gap > 2e-4
        if bool(recoverable.any()):
            recovery = 1.0 - prediction_gap[recoverable] / source_gap[recoverable].clamp_min(1e-6)
            sums["texture_recovery"] += float(recovery.clamp(-2.0, 1.0).sum())
            counts["texture_recovery"] += int(recoverable.sum())

        identity_rows = identity | (mode == 2)
        if bool(identity_rows.any()):
            change = (prediction[identity_rows] - source_core[identity_rows]).abs().flatten(1).mean(dim=1)
            sums["identity_change"] += float(change.sum())
            counts["identity_change"] += int(change.numel())
        flat_rows = mode == 3
        if bool(flat_rows.any()):
            false_detail = highpass(prediction[flat_rows], 3).abs().flatten(1).mean(dim=1)
            sums["flat_false_detail"] += float(false_detail.sum())
            counts["flat_false_detail"] += int(false_detail.numel())

        first, second = prediction[0::2], prediction[1::2]
        m0, m1 = motion[0::2], motion[1::2]
        aligned = warp_tensor(first, m1[:, 0] - m0[:, 0], m1[:, 1] - m0[:, 1])
        margin = 12
        pair_error = (aligned[..., margin:-margin, margin:-margin] - second[..., margin:-margin, margin:-margin]).abs().flatten(1).mean(dim=1)
        sums["paired_error"] += float(pair_error.sum())
        counts["paired_error"] += int(pair_error.numel())

    metrics = {key: sums[key] / max(counts[key], 1) for key in sums}
    metrics["psnr_db"] = -10.0 * math.log10(max(metrics["squared_error"], 1e-12))

    tile_error = float("nan")
    if first_source is not None and first_source.shape[-1] >= 224:
        with torch.autocast(device_type="cuda", dtype=torch.bfloat16, enabled=amp_enabled):
            full = model(first_source).float()
            crop_input = first_source[..., 16:-16, 16:-16]
            crop = model(crop_input).float()
        margin = 64
        reference = full[..., 16 + margin:-16 - margin, 16 + margin:-16 - margin]
        comparison = crop[..., margin:-margin, margin:-margin]
        if reference.numel() and reference.shape == comparison.shape:
            tile_error = float((reference - comparison).abs().mean())

    metrics["tile_error"] = tile_error
    axes = {
        "reconstruction": 1.0 / (1.0 + 25.0 * metrics["absolute_error"]),
        "contour": metrics["contour_iou"],
        "texture": metrics["texture_recovery"],
        "identity": 1.0 / (1.0 + 100.0 * metrics["identity_change"]),
        "flat_negative": 1.0 / (1.0 + 100.0 * metrics["flat_false_detail"]),
        "paired_observation": 1.0 / (1.0 + 100.0 * metrics["paired_error"]),
        "displacement": 1.0 / (1.0 + metrics["centroid_error_px"]),
        "tile_consistency": 1.0 / (1.0 + 1000.0 * max(tile_error, 0.0)) if math.isfinite(tile_error) else 0.0,
    }
    return {"metrics": metrics, "axes": axes, "counts": counts}


def _u8(image: torch.Tensor | np.ndarray) -> np.ndarray:
    if isinstance(image, torch.Tensor):
        image = image.detach().float().cpu().squeeze().numpy()
    return np.clip(np.asarray(image) * 255.0 + 0.5, 0, 255).astype(np.uint8)


def _label_panel(image: np.ndarray, label: str) -> np.ndarray:
    panel = cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)
    cv2.rectangle(panel, (0, 0), (panel.shape[1], 27), (18, 18, 18), -1)
    cv2.putText(panel, label, (8, 19), cv2.FONT_HERSHEY_SIMPLEX, 0.52, (245, 245, 245), 1, cv2.LINE_AA)
    return panel


@torch.inference_mode()
def save_synthetic_preview(model: torch.nn.Module, dataset: Any, device: torch.device, epoch: int, amp_enabled: bool) -> str:
    model.eval()
    rows: list[np.ndarray] = []
    indices = [0, 2, 3, 4, 6, 8]
    for index in indices:
        sample = dataset[index % len(dataset)]
        source = sample["source"][0:1].to(device)
        target = sample["target"][0]
        with torch.autocast(device_type="cuda", dtype=torch.bfloat16, enabled=amp_enabled):
            prediction = model(source).float()[0]
        raw = _u8(source[0])
        pred = _u8(prediction)
        truth = _u8(target)
        difference = cv2.applyColorMap(np.clip(np.abs(pred.astype(np.int16) - truth.astype(np.int16)) * 5, 0, 255).astype(np.uint8), cv2.COLORMAP_TURBO)
        row = np.concatenate([
            _label_panel(raw, f"RAW | {sample['scene_id'][-18:]}") ,
            _label_panel(pred, "R102"),
            _label_panel(truth, "TRUTH"),
            difference,
        ], axis=1)
        rows.append(row)
    output_dir = ROOT / "previews" / "synthetic" / f"epoch_{epoch:03d}"
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / "comparison.png"
    if not cv2.imwrite(str(path), np.concatenate(rows, axis=0)):
        raise RuntimeError(f"Unable to save {path}")
    return str(path)


@torch.inference_mode()
def save_real_previews(model: torch.nn.Module, device: torch.device, epoch: int, amp_enabled: bool) -> list[str]:
    model.eval()
    output_dir = ROOT / "previews" / "real" / f"epoch_{epoch:03d}"
    output_dir.mkdir(parents=True, exist_ok=True)
    paths: list[str] = []
    for source_name in CONFIG["validation"]["real_preview_sources"]:
        source_path = Path(PROJECT_ROOT / source_name)
        image = cv2.imread(str(source_path), cv2.IMREAD_GRAYSCALE)
        if image is None:
            raise FileNotFoundError(source_path)
        tensor = torch.from_numpy(image.astype(np.float32) / 255.0).view(1, 1, *image.shape).to(device)
        with torch.autocast(device_type="cuda", dtype=torch.bfloat16, enabled=amp_enabled):
            prediction = model(tensor).float()
        pred = _u8(prediction)
        residual = np.clip(128 + 5 * (pred.astype(np.int16) - image.astype(np.int16)), 0, 255).astype(np.uint8)
        comparison = np.concatenate([
            _label_panel(image, "RAW"),
            _label_panel(pred, "R102"),
            _label_panel(residual, "CHANGE x5 + 128"),
        ], axis=1)
        output_path = output_dir / f"{source_path.stem}_comparison.png"
        if not cv2.imwrite(str(output_path), comparison):
            raise RuntimeError(f"Unable to save {output_path}")
        paths.append(str(output_path))
    return paths

"""Single-run scratch trainer for R90.

There is deliberately no checkpoint, resume, teacher, or pseudo-label input.
Formal training can be registered only once and uses only the procedural-latent
R90 formal dataset.  The sealed holdout is never opened by this trainer.
"""
from __future__ import annotations

import argparse
import copy
import csv
import hashlib
import importlib.util
import json
import math
import os
import random
import sys
import time
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

import cv2
import numpy as np
import torch
from torch import nn
import torch.nn.functional as F
from torch.utils.data import DataLoader, Dataset, Sampler


ROOT = Path(__file__).resolve().parents[1]
DESIGN_PATH = ROOT / "config" / "experiment_design.json"
GATES_PATH = ROOT / "config" / "acceptance_gates.json"
AUTH_PATH = ROOT / "config" / "execution_authorization.json"
IMPLEMENTATION_LOCK_PATH = ROOT / "config" / "implementation_lock.json"
MODEL_PATH = ROOT / "model" / "r90_model.py"
OPTICAL_PATH = ROOT / "config" / "optical_statistics.json"
DESIGN = json.loads(DESIGN_PATH.read_text(encoding="utf-8"))
GATES = json.loads(GATES_PATH.read_text(encoding="utf-8"))
AUTH = json.loads(AUTH_PATH.read_text(encoding="utf-8"))
RUNS_DIR = ROOT / "runs"
RESULTS_DIR = ROOT / "results"


def json_dump(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    for attempt in range(100):
        try:
            os.replace(temporary, path)
            return
        except PermissionError:
            if attempt == 99:
                raise
            time.sleep(0.05)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def state_sha256(model: nn.Module) -> str:
    digest = hashlib.sha256()
    for name, value in sorted(model.state_dict().items()):
        digest.update(name.encode("utf-8"))
        digest.update(value.detach().cpu().contiguous().numpy().tobytes())
    return digest.hexdigest()


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load module: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def stage_for_epoch(epoch: int, run_kind: str) -> dict[str, int]:
    if run_kind == "smoke":
        return {"epoch_start": 1, "epoch_end": 1, "patch_size": 256, "core_size": 128, "scene_batch_size": 4, "gradient_accumulation": 1, "effective_scene_batch": 4}
    for stage in DESIGN["training"]["stages"]:
        if int(stage["epoch_start"]) <= epoch <= int(stage["epoch_end"]):
            selected = {
                "epoch_start": int(stage["epoch_start"]),
                "epoch_end": int(stage["epoch_end"]),
                "patch_size": int(stage["patch_size"]),
                "core_size": int(stage["core_size"]),
                "scene_batch_size": int(stage["scene_batch_size"]),
                "gradient_accumulation": int(stage["gradient_accumulation"]),
                "effective_scene_batch": int(stage["effective_scene_batch"]),
            }
            every = int(stage.get("alternate_every_epochs", 0))
            if every > 0 and (epoch - int(stage["epoch_start"]) + 1) % every == 0:
                selected["patch_size"] = int(stage["alternate_patch_size"])
                selected["core_size"] = int(stage["alternate_core_size"])
                selected["scene_batch_size"] = int(stage["alternate_scene_batch_size"])
                selected["effective_scene_batch"] = selected["scene_batch_size"] * selected["gradient_accumulation"]
            return selected
    raise ValueError(f"No stage for epoch {epoch}")


def curriculum_for_epoch(epoch: int) -> dict[str, float]:
    anchors = DESIGN["training"]["curriculum_anchors"]
    if epoch <= int(anchors[0]["epoch"]):
        return {key: float(value) for key, value in anchors[0].items() if key != "epoch"}
    for left, right in zip(anchors[:-1], anchors[1:]):
        if int(left["epoch"]) <= epoch <= int(right["epoch"]):
            span = max(int(right["epoch"]) - int(left["epoch"]), 1)
            fraction = (epoch - int(left["epoch"])) / span
            return {
                key: float(left[key]) + fraction * (float(right[key]) - float(left[key]))
                for key in left
                if key != "epoch"
            }
    return {key: float(value) for key, value in anchors[-1].items() if key != "epoch"}


def warp_u8(array: np.ndarray, dx: float, dy: float, interpolation: int) -> np.ndarray:
    if abs(dx) < 1e-12 and abs(dy) < 1e-12:
        return np.asarray(array)
    matrix = np.asarray([[1.0, 0.0, dx], [0.0, 1.0, dy]], dtype=np.float32)
    return cv2.warpAffine(np.asarray(array), matrix, (array.shape[1], array.shape[0]), flags=interpolation, borderMode=cv2.BORDER_REFLECT_101)


class R90SceneDataset(Dataset):
    def __init__(self, package: Path, manifest: dict[str, Any], split: str, patch_size: int, core_size: int, epoch: int, *, all_observations: bool = False):
        self.package = Path(package)
        self.records = [record for record in manifest["records"] if record["split"] == split]
        self.records.sort(key=lambda row: int(row["scene_index"]))
        self.patch_size = int(patch_size)
        self.core_size = int(core_size)
        self.canvas_size = int(manifest["canvas_size"])
        self.epoch = int(epoch)
        self.all_observations = bool(all_observations)
        self.items: list[tuple[dict[str, Any], tuple[int, int] | None]] = []
        for record in self.records:
            if not self.all_observations:
                self.items.append((record, None))
            elif record["role"] == "signed_subpixel_motion":
                self.items.extend(((record, (0, 1)), (record, (0, 2)), (record, (0, 3))))
            elif record["role"] == "exposure_coherent_bundle":
                self.items.extend(((record, (0, 1)), (record, (0, 2)), (record, (0, 3)), (record, (1, 3))))
            else:
                self.items.extend((record, (observation, observation)) for observation in range(4))
        if self.patch_size > self.canvas_size or self.patch_size % 8 or self.core_size % 8:
            raise ValueError("Patch and core must fit the canvas and align to 8 pixels")
        if self.patch_size < self.core_size or (self.patch_size - self.core_size) % 2:
            raise ValueError("Invalid patch/core pair")

    def __len__(self) -> int:
        return len(self.items)

    def role_at(self, index: int) -> str:
        return str(self.items[index][0]["role"])

    @staticmethod
    def _aligned_random(rng: np.random.Generator, maximum: int) -> int:
        return int(rng.integers(0, maximum // 8 + 1)) * 8

    def _random_origins(self, scene_index: int) -> np.ndarray:
        rng = np.random.default_rng(int(DESIGN["dataset"]["master_seed"]) * 1000003 + scene_index * 10007 + self.epoch * 7919 + self.patch_size * 17)
        maximum = self.canvas_size - self.patch_size
        y0, x0 = self._aligned_random(rng, maximum), self._aligned_random(rng, maximum)
        maximum_offset = max(8, min(self.core_size // 2, maximum))
        choices = np.arange(8, maximum_offset + 1, 8, dtype=np.int32)
        for _ in range(32):
            dy, dx = int(rng.choice(choices)) * int(rng.choice([-1, 1])), int(rng.choice(choices)) * int(rng.choice([-1, 1]))
            y1, x1 = int(np.clip(y0 + dy, 0, maximum) // 8 * 8), int(np.clip(x0 + dx, 0, maximum) // 8 * 8)
            if (y1 != y0 or x1 != x0) and self.core_size - abs(y1 - y0) >= self.core_size // 2 and self.core_size - abs(x1 - x0) >= self.core_size // 2:
                return np.asarray([[y0, x0], [y1, x1]], dtype=np.int64)
        y1 = min(maximum, y0 + min(64, max(0, maximum - y0))) // 8 * 8
        if y1 == y0:
            y1 = max(0, y0 - min(64, y0)) // 8 * 8
        return np.asarray([[y0, x0], [y1, x0]], dtype=np.int64)

    def _structure_origin(self, mask: np.ndarray, scene_index: int) -> tuple[int, int, float, int]:
        maximum = self.canvas_size - self.patch_size
        if maximum <= 0:
            binary = mask >= 128
            boundary = cv2.morphologyEx(binary.astype(np.uint8), cv2.MORPH_GRADIENT, np.ones((3, 3), np.uint8))
            return 0, 0, float(np.mean(binary)), int(np.count_nonzero(boundary))
        binary = mask >= 128
        boundary = cv2.morphologyEx(binary.astype(np.uint8), cv2.MORPH_GRADIENT, np.ones((3, 3), np.uint8))
        coordinates = np.argwhere(boundary > 0)
        if not len(coordinates):
            coordinates = np.argwhere(binary)
        if not len(coordinates):
            raise RuntimeError("Structure-aware crop received an empty procedural mask")
        rng = np.random.default_rng(int(DESIGN["dataset"]["master_seed"]) * 1000033 + scene_index * 10009 + self.epoch * 7937 + self.patch_size * 19)
        order = rng.permutation(len(coordinates))[: min(96, len(coordinates))]
        motion_cfg = DESIGN["dataset"]["motion"]
        minimum_fraction = float(motion_cfg["crop_foreground_fraction_min"])
        maximum_fraction = float(motion_cfg["crop_foreground_fraction_max"])
        minimum_boundary = int(motion_cfg["crop_boundary_pixels_min"])
        best: tuple[float, int, int, float, int] | None = None
        for candidate in order:
            cy, cx = coordinates[int(candidate)]
            y0 = int(np.clip(int(cy) - self.patch_size // 2, 0, maximum) // 8 * 8)
            x0 = int(np.clip(int(cx) - self.patch_size // 2, 0, maximum) // 8 * 8)
            crop = binary[y0:y0 + self.patch_size, x0:x0 + self.patch_size]
            boundary_crop = boundary[y0:y0 + self.patch_size, x0:x0 + self.patch_size]
            fraction = float(np.mean(crop))
            boundary_count = int(np.count_nonzero(boundary_crop))
            penalty = max(minimum_fraction - fraction, 0.0) + max(fraction - maximum_fraction, 0.0)
            penalty += max(minimum_boundary - boundary_count, 0) / max(minimum_boundary, 1)
            row = (penalty, y0, x0, fraction, boundary_count)
            if best is None or row[0] < best[0]:
                best = row
            if penalty <= 0:
                break
        if best is None:
            raise RuntimeError("Unable to select a structure-aware crop")
        _penalty, y0, x0, fraction, boundary_count = best
        return int(y0), int(x0), float(fraction), int(boundary_count)

    def _origins(self, record: dict[str, Any], mask: np.ndarray, pair_kind: int) -> tuple[np.ndarray, float, int]:
        scene_index = int(record["scene_index"])
        structure_required = pair_kind in {1, 2} or record["role"] in {"difficult_contour", "clean_contour_anchor"}
        structure_preferred = (scene_index + self.epoch) % 4 != 0 and record["role"] != "identity_and_detail_guard"
        if structure_required or structure_preferred:
            y0, x0, fraction, boundary_count = self._structure_origin(mask, scene_index)
            if pair_kind in {1, 2}:
                origins = np.asarray([[y0, x0], [y0, x0]], dtype=np.int64)
            else:
                origins = self._random_origins(scene_index)
                delta = origins[1] - origins[0]
                maximum = self.canvas_size - self.patch_size
                y1 = int(np.clip(y0 + int(delta[0]), 0, maximum) // 8 * 8)
                x1 = int(np.clip(x0 + int(delta[1]), 0, maximum) // 8 * 8)
                origins = np.asarray([[y0, x0], [y1, x1]], dtype=np.int64)
            return origins, fraction, boundary_count
        origins = self._random_origins(scene_index)
        y0, x0 = origins[0]
        binary = mask[y0:y0 + self.patch_size, x0:x0 + self.patch_size] >= 128
        boundary = cv2.morphologyEx(binary.astype(np.uint8), cv2.MORPH_GRADIENT, np.ones((3, 3), np.uint8))
        return origins, float(np.mean(binary)), int(np.count_nonzero(boundary))

    def motion_kind_at(self, index: int) -> str:
        record, fixed = self.items[index]
        if record["role"] != "signed_subpixel_motion":
            return "none"
        if fixed is not None:
            return "zero" if fixed == (0, 3) else "signed"
        return "zero" if (self.epoch + int(record["scene_index"])) % 4 == 0 else "signed"

    def __getitem__(self, index: int):
        record, fixed_observations = self.items[index]
        scene_index = int(record["scene_index"])
        is_motion = record["role"] == "signed_subpixel_motion"
        is_exposure_bundle = record["role"] == "exposure_coherent_bundle"
        if is_motion:
            pair_kind = 1
        elif is_exposure_bundle or (fixed_observations is not None and fixed_observations[0] != fixed_observations[1]):
            pair_kind = 2
        elif record["role"] == "cross_tile_and_dense":
            pair_kind = 0
        else:
            pair_kind = 2 if (self.epoch + scene_index) % 2 == 0 else 0
        if fixed_observations is not None:
            observation_indices = fixed_observations
        elif is_motion:
            selector = (self.epoch + scene_index) % 4
            observation_indices = (0, 3) if selector == 0 else ((0, 1) if selector % 2 else (0, 2))
        elif pair_kind == 2:
            first = (self.epoch + scene_index) % 4
            second = (first + 1 + (scene_index % 2)) % 4
            observation_indices = (first, second)
        else:
            selected = (self.epoch + scene_index) % 4
            observation_indices = (selected, selected)
        target_base = np.load(self.package / record["target"], mmap_mode="r", allow_pickle=False)
        mask_base = np.load(self.package / record["mask"], mmap_mode="r", allow_pickle=False)
        origins, crop_foreground_fraction, crop_boundary_pixels = self._origins(record, np.asarray(mask_base), pair_kind)
        sdf_small = np.load(self.package / record["sdf_q4"], mmap_mode="r", allow_pickle=False)
        sdf_base = cv2.resize(np.asarray(sdf_small, dtype=np.float32) * 4.0, (self.canvas_size, self.canvas_size), interpolation=cv2.INTER_LINEAR)
        source_views, target_views, mask_views, sdf_views, motions, identities = [], [], [], [], [], []
        transformed: dict[int, tuple[np.ndarray, np.ndarray, np.ndarray]] = {}
        for view, obs_index in enumerate(observation_indices):
            observation = record["observations"][obs_index]
            dx, dy = float(observation["motion_dx_px"]), float(observation["motion_dy_px"])
            if obs_index not in transformed:
                transformed[obs_index] = (
                    warp_u8(target_base, dx, dy, cv2.INTER_LANCZOS4),
                    warp_u8(mask_base, dx, dy, cv2.INTER_LINEAR),
                    cv2.warpAffine(sdf_base, np.asarray([[1.0, 0.0, dx], [0.0, 1.0, dy]], np.float32), (self.canvas_size, self.canvas_size), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT_101) if abs(dx) + abs(dy) > 0 else sdf_base,
                )
            target_full, mask_full, sdf_full = transformed[obs_index]
            source = np.load(self.package / observation["source"], mmap_mode="r", allow_pickle=False)
            y0, x0 = origins[view]
            source_views.append(np.asarray(source[y0:y0 + self.patch_size, x0:x0 + self.patch_size]).copy())
            target_views.append(np.asarray(target_full[y0:y0 + self.patch_size, x0:x0 + self.patch_size]).copy())
            mask_views.append(np.asarray(mask_full[y0:y0 + self.patch_size, x0:x0 + self.patch_size]).copy())
            sdf_views.append(np.asarray(sdf_full[y0:y0 + self.patch_size, x0:x0 + self.patch_size]).copy())
            motions.append((dx, dy))
            identities.append(observation["degradation_family"] == "identity_and_near_identity")
        texture = record["texture"]
        midpoint = 0.5 * (float(texture["foreground_mean"]) + float(texture["background_mean"]))
        polarity = 1.0 if bool(texture["bright_foreground"]) else -1.0
        to_float = lambda rows: torch.from_numpy(np.stack(rows)).unsqueeze(1).float()
        gap_values = [float(np.mean(np.abs(source.astype(np.float32) - target.astype(np.float32)))) / 255.0 for source, target in zip(source_views, target_views)]
        maximum_gap = float(DESIGN["dataset"]["recoverability_contract"]["maximum_source_target_gap"])
        consistency_confidence = float(np.clip(1.0 - max(gap_values) / max(maximum_gap, 1e-6), 0.25, 1.0))
        return {
            "source": to_float(source_views).div_(255.0),
            "target": to_float(target_views).div_(255.0),
            "mask": to_float(mask_views).div_(255.0),
            "sdf": to_float(sdf_views),
            "origins": torch.from_numpy(origins),
            "motion": torch.tensor(motions, dtype=torch.float32),
            "identity": torch.tensor(identities, dtype=torch.bool),
            "pair_kind": torch.tensor(pair_kind, dtype=torch.int64),
            "observation_indices": torch.tensor(observation_indices, dtype=torch.int64),
            "consistency_confidence": torch.tensor(consistency_confidence, dtype=torch.float32),
            "midpoint": torch.tensor(midpoint, dtype=torch.float32),
            "polarity": torch.tensor(polarity, dtype=torch.float32),
            "crop_foreground_fraction": torch.tensor(crop_foreground_fraction, dtype=torch.float32),
            "crop_boundary_pixels": torch.tensor(crop_boundary_pixels, dtype=torch.int64),
            "role": record["role"],
            "scene_id": record["scene_id"],
        }


class GoalBalancedBatchSampler(Sampler[list[int]]):
    """Put motion, identity and exposure supervision in every full batch."""

    def __init__(self, dataset: R90SceneDataset, batch_size: int, seed: int):
        self.seed = int(seed)
        self.batch_size = int(batch_size)
        if dataset.all_observations:
            raise ValueError("GoalBalancedBatchSampler is only for training views")
        grouped: defaultdict[str, list[int]] = defaultdict(list)
        self.epoch = int(dataset.epoch)
        self.scene_indices: dict[int, int] = {}
        for index, record in enumerate(dataset.records):
            grouped[str(record["role"])].append(index)
            self.scene_indices[index] = int(record["scene_index"])
        self.groups = {name: grouped[name] for name in sorted(grouped)}
        self.dataset = dataset
        if self.batch_size < 3 or not self.groups or any(not group for group in self.groups.values()):
            raise ValueError("Role-balanced sampling requires at least one scene per role")
        self.batch_count = math.ceil(len(dataset) / self.batch_size)

    def __len__(self) -> int:
        return self.batch_count

    def __iter__(self):
        generator = torch.Generator().manual_seed(self.seed)

        def shuffled_cycle(group: list[int]):
            while True:
                order = torch.randperm(len(group), generator=generator).tolist()
                for local in order:
                    yield group[local]

        cycles = {name: shuffled_cycle(group) for name, group in self.groups.items()}
        motion_cycle = cycles.get("signed_subpixel_motion")
        identity_cycle = cycles.get("identity_and_detail_guard")
        exposure_cycle = cycles.get("exposure_coherent_bundle")
        fill_roles = [name for name in sorted(self.groups) if name not in {"signed_subpixel_motion", "identity_and_detail_guard", "exposure_coherent_bundle"}]
        role_cursor = 0
        batches: list[list[int]] = []
        for _ in range(self.batch_count):
            batch: list[int] = []
            if motion_cycle is not None:
                batch.append(next(motion_cycle))
            if identity_cycle is not None:
                batch.append(next(identity_cycle))
            if exposure_cycle is not None:
                batch.append(next(exposure_cycle))
            while len(batch) < self.batch_size:
                role = fill_roles[role_cursor % len(fill_roles)]
                role_cursor += 1
                batch.append(next(cycles[role]))
            order = torch.randperm(len(batch), generator=generator).tolist()
            batches.append([batch[i] for i in order])
        return iter(batches)


def gradient_xy(x: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
    kernel = torch.tensor([[-1.0, 0.0, 1.0], [-2.0, 0.0, 2.0], [-1.0, 0.0, 1.0]], device=x.device, dtype=x.dtype).view(1, 1, 3, 3) / 8.0
    padded = F.pad(x, (1, 1, 1, 1), mode="reflect")
    return F.conv2d(padded, kernel), F.conv2d(padded, kernel.transpose(-1, -2))


def gradient_magnitude(x: torch.Tensor) -> torch.Tensor:
    gx, gy = gradient_xy(x)
    return torch.sqrt(gx.square() + gy.square() + 1e-8)


def lowpass(x: torch.Tensor, size: int = 9) -> torch.Tensor:
    return F.avg_pool2d(F.pad(x, (size // 2,) * 4, mode="reflect"), size, stride=1)


def foreground_probability(image: torch.Tensor, midpoint: torch.Tensor, polarity: torch.Tensor) -> torch.Tensor:
    return torch.sigmoid(polarity.view(-1, 1, 1, 1) * (image - midpoint.view(-1, 1, 1, 1)) / 0.04)


def soft_boundary(probability: torch.Tensor) -> torch.Tensor:
    maximum = F.max_pool2d(probability, 5, stride=1, padding=2)
    minimum = -F.max_pool2d(-probability, 5, stride=1, padding=2)
    return (maximum - minimum).clamp(0.0, 1.0)


def soft_euler(probability: torch.Tensor) -> torch.Tensor:
    probability = F.adaptive_avg_pool2d(probability, (64, 64)).clamp(0.0, 1.0)
    vertices = probability.sum(dim=(-2, -1))
    horizontal = (probability[..., :, :-1] * probability[..., :, 1:]).sum(dim=(-2, -1))
    vertical = (probability[..., :-1, :] * probability[..., 1:, :]).sum(dim=(-2, -1))
    faces = (probability[..., :-1, :-1] * probability[..., 1:, :-1] * probability[..., :-1, 1:] * probability[..., 1:, 1:]).sum(dim=(-2, -1))
    return vertices - horizontal - vertical + faces


def centroid(probability: torch.Tensor) -> torch.Tensor:
    h, w = probability.shape[-2:]
    yy = torch.arange(h, device=probability.device, dtype=probability.dtype).view(1, 1, h, 1)
    xx = torch.arange(w, device=probability.device, dtype=probability.dtype).view(1, 1, 1, w)
    mass = probability.sum(dim=(-2, -1)).clamp_min(1e-4)
    cx = (probability * xx).sum(dim=(-2, -1)) / mass
    cy = (probability * yy).sum(dim=(-2, -1)) / mass
    return torch.cat([cx, cy], dim=1)


def supported_edge_centroid(probability: torch.Tensor, support: torch.Tensor) -> torch.Tensor:
    edge = soft_boundary(probability) * support
    return centroid(edge + 1e-6 * support)


def shift_tensor(x: torch.Tensor, dx: torch.Tensor, dy: torch.Tensor) -> torch.Tensor:
    n, _c, h, w = x.shape
    theta = torch.zeros((n, 2, 3), device=x.device, dtype=x.dtype)
    theta[:, 0, 0], theta[:, 1, 1] = 1.0, 1.0
    theta[:, 0, 2] = -2.0 * dx.to(x.dtype) / max(w - 1, 1)
    theta[:, 1, 2] = -2.0 * dy.to(x.dtype) / max(h - 1, 1)
    grid = F.affine_grid(theta, x.shape, align_corners=True)
    return F.grid_sample(x, grid, mode="bilinear", padding_mode="border", align_corners=True)


def detail_losses(prediction: torch.Tensor, target: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
    prediction_detail = prediction - lowpass(prediction, 5)
    target_detail = target - lowpass(target, 5)
    detail_l1 = F.l1_loss(prediction_detail, target_detail)
    pred_flat = prediction_detail.flatten(1)
    target_flat = target_detail.flatten(1)
    pred_flat = pred_flat - pred_flat.mean(dim=1, keepdim=True)
    target_flat = target_flat - target_flat.mean(dim=1, keepdim=True)
    pred_norm = torch.sqrt(torch.mean(pred_flat.square(), dim=1) + 1e-8)
    target_norm = torch.sqrt(torch.mean(target_flat.square(), dim=1) + 1e-8)
    correlation = torch.mean(pred_flat * target_flat, dim=1) / (pred_norm * target_norm).clamp_min(1e-6)
    valid = target_norm > (0.5 / 255.0)
    correlation_loss = (1.0 - correlation[valid]).mean() if bool(valid.any()) else prediction.new_zeros(())
    energy_loss = torch.abs(torch.log((pred_norm + 1e-5) / (target_norm + 1e-5))).clamp_max(2.0)
    energy_loss = energy_loss[valid].mean() if bool(valid.any()) else prediction.new_zeros(())
    return detail_l1, correlation_loss, energy_loss


def overlap_consistency(prediction: torch.Tensor, origins: torch.Tensor, pair_kind: torch.Tensor, patch_size: int, core_size: int) -> torch.Tensor:
    halo = (patch_size - core_size) // 2
    terms = []
    origins_cpu = origins.detach().cpu().numpy()
    for item in range(int(prediction.shape[0])):
        if int(pair_kind[item]) != 0:
            continue
        y0a, x0a = origins_cpu[item, 0]
        y0b, x0b = origins_cpu[item, 1]
        a_y0, a_x0, b_y0, b_x0 = int(y0a + halo), int(x0a + halo), int(y0b + halo), int(x0b + halo)
        iy0, ix0 = max(a_y0, b_y0), max(a_x0, b_x0)
        iy1, ix1 = min(a_y0 + core_size, b_y0 + core_size), min(a_x0 + core_size, b_x0 + core_size)
        if iy1 <= iy0 or ix1 <= ix0:
            raise RuntimeError("Paired supervised cores do not overlap")
        a = prediction[item, 0, :, iy0 - int(y0a):iy1 - int(y0a), ix0 - int(x0a):ix1 - int(x0a)]
        b = prediction[item, 1, :, iy0 - int(y0b):iy1 - int(y0b), ix0 - int(x0b):ix1 - int(x0b)]
        terms.append(F.l1_loss(a, b))
    return torch.stack(terms).mean() if terms else prediction.new_zeros(())


def cross_observation_consistency(
    prediction: torch.Tensor,
    probability: torch.Tensor,
    sdf: torch.Tensor,
    pair_kind: torch.Tensor,
    confidence: torch.Tensor,
) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
    selector = pair_kind == 2
    if not bool(selector.any()):
        zero = prediction.new_zeros(())
        return zero, zero, zero
    selected_prediction = prediction[selector]
    selected_probability = probability[selector]
    selected_sdf = sdf[selector]
    selected_confidence = confidence[selector].to(prediction.dtype)
    low_difference = torch.abs(lowpass(selected_prediction[:, 0], 9) - lowpass(selected_prediction[:, 1], 9)).mean(dim=(1, 2, 3))
    boundary_weight = torch.exp(-torch.abs(selected_sdf[:, 0]) / 9.0)
    contour_difference = torch.abs(selected_probability[:, 0] - selected_probability[:, 1])
    contour_difference = (contour_difference * boundary_weight).sum(dim=(1, 2, 3)) / boundary_weight.sum(dim=(1, 2, 3)).clamp_min(1.0)
    normalizer = selected_confidence.sum().clamp_min(1e-6)
    low_term = (low_difference * selected_confidence).sum() / normalizer
    contour_term = (contour_difference * selected_confidence).sum() / normalizer
    return 0.55 * low_term + 0.45 * contour_term, low_term, contour_term


def low_branch_edge_leakage(low_delta: torch.Tensor, sdf: torch.Tensor) -> torch.Tensor:
    narrow_component = torch.abs(low_delta - lowpass(low_delta, 11))
    boundary_weight = torch.exp(-torch.abs(sdf) / 7.0)
    return (narrow_component * boundary_weight).sum() / boundary_weight.sum().clamp_min(1.0)


def loss_components(details: dict[str, torch.Tensor], batch: dict[str, Any], patch_size: int, core_size: int, epoch: int, *, enable_topology: bool = True) -> tuple[torch.Tensor, dict[str, torch.Tensor], dict[str, torch.Tensor]]:
    weights = DESIGN["training"]["loss_weights"]
    curriculum = curriculum_for_epoch(epoch)
    scenes = int(batch["source"].shape[0])
    halo = (patch_size - core_size) // 2
    core = slice(halo, halo + core_size)
    output = details["output"].reshape(scenes, 2, 1, patch_size, patch_size).float()
    low_delta = details["low_delta"].reshape(scenes, 2, 1, patch_size, patch_size).float()
    geometry_logits = details["geometry_logits"].reshape(scenes, 2, 1, patch_size, patch_size).float()
    target = batch["target"].to(output.device).float()
    source = batch["source"].to(output.device).float()
    mask = batch["mask"].to(output.device).float()
    sdf = batch["sdf"].to(output.device).float()
    pred_core = output[..., core, core].reshape(scenes * 2, 1, core_size, core_size)
    target_core = target[..., core, core].reshape(scenes * 2, 1, core_size, core_size)
    source_core = source[..., core, core].reshape(scenes * 2, 1, core_size, core_size)
    mask_core = mask[..., core, core].reshape(scenes * 2, 1, core_size, core_size)
    sdf_core = sdf[..., core, core].reshape(scenes * 2, 1, core_size, core_size)
    geometry_logits_core = geometry_logits[..., core, core].reshape(scenes * 2, 1, core_size, core_size)
    low_delta_core = low_delta[..., core, core].reshape(scenes * 2, 1, core_size, core_size)
    midpoint = batch["midpoint"].to(output.device).repeat_interleave(2)
    polarity = batch["polarity"].to(output.device).repeat_interleave(2)
    probability = foreground_probability(pred_core, midpoint, polarity)

    difference = pred_core - target_core
    pixel = torch.sqrt(difference.square() + 1e-6).mean()
    low_band = F.l1_loss(lowpass(pred_core), lowpass(target_core))
    gradient = F.l1_loss(gradient_magnitude(pred_core), gradient_magnitude(target_core))
    detail_l1, detail_correlation, detail_energy = detail_losses(pred_core, target_core)
    boundary_weight = torch.exp(-torch.abs(sdf_core) / 8.0)
    signed_distance = (torch.abs(probability - mask_core) * boundary_weight).sum() / boundary_weight.sum().clamp_min(1.0)
    pred_boundary, target_boundary = soft_boundary(probability), soft_boundary(mask_core)
    intersection = (pred_boundary * target_boundary).sum(dim=(-2, -1))
    union = (pred_boundary + target_boundary - pred_boundary * target_boundary).sum(dim=(-2, -1))
    boundary_iou = 1.0 - ((intersection + 1e-5) / (union + 1e-5)).mean()
    geometry_probability = torch.sigmoid(geometry_logits_core)
    geometry_bce = F.binary_cross_entropy_with_logits(geometry_logits_core, mask_core)
    geometry_intersection = (geometry_probability * mask_core).sum(dim=(-2, -1))
    geometry_dice = 1.0 - ((2.0 * geometry_intersection + 1.0) / (geometry_probability.sum(dim=(-2, -1)) + mask_core.sum(dim=(-2, -1)) + 1.0)).mean()
    auxiliary_geometry = 0.5 * (geometry_bce + geometry_dice)
    # The soft Euler surrogate is computed on a 64x64 field and therefore has
    # a much larger raw scale than pixel or boundary losses.  Normalize it so
    # topology remains a guard instead of overwhelming reconstruction.
    topology = F.smooth_l1_loss(soft_euler(geometry_probability), soft_euler(mask_core), beta=0.5) / 512.0 if enable_topology else pred_core.new_zeros(())

    pair_kind = batch["pair_kind"].to(output.device)
    motion_selector = pair_kind == 1
    translation = pred_core.new_zeros(())
    displacement = pred_core.new_zeros(())
    signed_bias_loss = pred_core.new_zeros(())
    signed_bias = pred_core.new_zeros((2,))
    if bool(motion_selector.any()):
        selected_pred = pred_core.reshape(scenes, 2, 1, core_size, core_size)[motion_selector]
        selected_mask = mask_core.reshape(scenes, 2, 1, core_size, core_size)[motion_selector]
        selected_probability = probability.reshape(scenes, 2, 1, core_size, core_size)[motion_selector]
        selected_motion = batch["motion"].to(output.device)[motion_selector]
        selected_fraction = batch["crop_foreground_fraction"].to(output.device)[motion_selector]
        selected_boundaries = batch["crop_boundary_pixels"].to(output.device)[motion_selector]
        motion_cfg = DESIGN["dataset"]["motion"]
        if bool((selected_fraction < float(motion_cfg["crop_foreground_fraction_min"]) * 0.75).any()) or bool((selected_boundaries < int(motion_cfg["crop_boundary_pixels_min"]) * 0.75).any()):
            raise RuntimeError("A motion crop failed the structure qualification contract")
        delta = selected_motion[:, 1] - selected_motion[:, 0]
        warped = shift_tensor(lowpass(selected_pred[:, 0], 7), delta[:, 0], delta[:, 1])
        translation = F.l1_loss(warped[..., 6:-6, 6:-6], lowpass(selected_pred[:, 1], 7)[..., 6:-6, 6:-6])
        support = F.max_pool2d(selected_mask.reshape(-1, 1, core_size, core_size), 49, stride=1, padding=24)
        pred_centers = supported_edge_centroid(selected_probability.reshape(-1, 1, core_size, core_size), support).reshape(-1, 2, 2)
        target_centers = supported_edge_centroid(selected_mask.reshape(-1, 1, core_size, core_size), support).reshape(-1, 2, 2)
        error = (pred_centers[:, 1] - pred_centers[:, 0]) - (target_centers[:, 1] - target_centers[:, 0])
        displacement = F.smooth_l1_loss(error, torch.zeros_like(error), beta=0.05)
        signed_bias = error.mean(dim=0)
        signed_bias_loss = F.smooth_l1_loss(signed_bias, torch.zeros_like(signed_bias), beta=0.02)

    consistency = overlap_consistency(output, batch["origins"], pair_kind, patch_size, core_size)
    paired_prediction = pred_core.reshape(scenes, 2, 1, core_size, core_size)
    paired_probability = probability.reshape(scenes, 2, 1, core_size, core_size)
    paired_sdf = sdf_core.reshape(scenes, 2, 1, core_size, core_size)
    cross_observation, cross_observation_low, cross_observation_contour = cross_observation_consistency(
        paired_prediction,
        paired_probability,
        paired_sdf,
        pair_kind,
        batch["consistency_confidence"].to(output.device),
    )
    branch_edge_leakage = low_branch_edge_leakage(low_delta_core, sdf_core)
    identity_mask = batch["identity"].to(output.device).reshape(-1)
    identity = F.l1_loss(pred_core[identity_mask], source_core[identity_mask]) if bool(identity_mask.any()) else pred_core.new_zeros(())
    model_error = torch.abs(pred_core - target_core).mean(dim=(-3, -2, -1))
    raw_error = torch.abs(source_core - target_core).mean(dim=(-3, -2, -1))
    clear_mask = raw_error <= (3.0 / 255.0)
    clear_input_guard = torch.relu(model_error[clear_mask] - raw_error[clear_mask] - 0.25 / 255.0).mean() if bool(clear_mask.any()) else pred_core.new_zeros(())

    geometry_factor = float(curriculum["geometry_factor"])
    motion_factor = float(curriculum["motion_factor"])
    topology_factor = float(curriculum["topology_factor"])
    exposure_factor = float(curriculum["exposure_factor"])
    branch_separation_factor = float(curriculum["branch_separation_factor"])

    total = (
        float(weights["pixel_charbonnier"]) * pixel
        + float(weights["low_band_l1"]) * low_band
        + float(weights["gradient"]) * gradient
        + float(weights["detail_l1"]) * detail_l1
        + float(weights["detail_correlation"]) * detail_correlation
        + float(weights["detail_energy"]) * detail_energy
        + geometry_factor * float(weights["signed_distance_boundary"]) * signed_distance
        + geometry_factor * float(weights["soft_boundary_iou"]) * boundary_iou
        + geometry_factor * float(weights["auxiliary_geometry"]) * auxiliary_geometry
        + geometry_factor * topology_factor * float(weights["topology"]) * topology
        + motion_factor * float(weights["translation_equivariance"]) * translation
        + motion_factor * float(weights["signed_displacement"]) * displacement
        + motion_factor * float(weights["signed_bias"]) * signed_bias_loss
        + float(weights["overlap_tile_consistency"]) * consistency
        + exposure_factor * float(weights["cross_observation_consistency"]) * cross_observation
        + branch_separation_factor * float(weights["low_branch_edge_leakage"]) * branch_edge_leakage
        + float(weights["identity_guard"]) * identity
        + float(weights["clear_input_guard"]) * clear_input_guard
    )
    parts = {
        "total": total.detach(), "pixel": pixel.detach(), "low_band": low_band.detach(), "gradient": gradient.detach(),
        "detail_l1": detail_l1.detach(), "detail_correlation": detail_correlation.detach(), "detail_energy": detail_energy.detach(),
        "signed_distance": signed_distance.detach(), "boundary_iou": boundary_iou.detach(), "auxiliary_geometry": auxiliary_geometry.detach(),
        "topology": topology.detach(), "translation": translation.detach(), "displacement": displacement.detach(),
        "signed_bias_loss": signed_bias_loss.detach(), "consistency": consistency.detach(), "identity": identity.detach(),
        "cross_observation": cross_observation.detach(), "cross_observation_low": cross_observation_low.detach(),
        "cross_observation_contour": cross_observation_contour.detach(), "low_branch_edge_leakage": branch_edge_leakage.detach(),
        "clear_input_guard": clear_input_guard.detach(), "signed_bias_x": signed_bias[0].detach(), "signed_bias_y": signed_bias[1].detach(),
    }
    aux = {"pred_core": pred_core, "target_core": target_core, "source_core": source_core, "mask_core": mask_core, "probability": probability, "geometry_probability": geometry_probability}
    return total, parts, aux


@torch.no_grad()
def update_ema(model: nn.Module, ema: nn.Module, decay: float | None = None) -> None:
    decay = float(DESIGN["training"]["ema_decay"] if decay is None else decay)
    current = model.state_dict()
    for name, value in ema.state_dict().items():
        source = current[name].detach()
        if value.dtype.is_floating_point:
            value.mul_(decay).add_(source, alpha=1.0 - decay)
        else:
            value.copy_(source)


def topology_signature(binary: np.ndarray) -> tuple[int, int]:
    binary = np.asarray(binary, dtype=np.uint8)
    components, _ = cv2.connectedComponents(binary, connectivity=8)
    _contours, hierarchy = cv2.findContours(binary, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_SIMPLE)
    holes = int(sum(1 for item in ([] if hierarchy is None else hierarchy[0]) if int(item[3]) >= 0))
    return int(max(0, components - 1)), holes


@torch.no_grad()
def evaluate(model: nn.Module, loader: DataLoader, device: torch.device, patch_size: int, core_size: int, epoch: int, amp_enabled: bool, max_batches: int = 0) -> dict[str, Any]:
    model.eval()
    sums: defaultdict[str, float] = defaultdict(float)
    count = 0
    role_values: defaultdict[str, defaultdict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
    topology_mismatches = 0
    raw_topology_mismatches = 0
    raw_clear_added_topology_failures = 0
    identity_changes: list[float] = []
    motion_errors: list[tuple[float, float]] = []
    raw_motion_errors: list[tuple[float, float]] = []
    for batch_index, batch in enumerate(loader, start=1):
        scenes = int(batch["source"].shape[0])
        source = batch["source"].to(device, non_blocking=True)
        flat = source.reshape(scenes * 2, 1, patch_size, patch_size)
        with torch.autocast(device_type="cuda", dtype=torch.bfloat16, enabled=amp_enabled):
            details = model(flat, return_details=True)
        _total, parts, aux = loss_components(details, batch, patch_size, core_size, epoch, enable_topology=True)
        for name, value in parts.items():
            sums[name] += float(value) * scenes
        count += scenes
        pred = aux["pred_core"].reshape(scenes, 2, 1, core_size, core_size)
        target = aux["target_core"].reshape(scenes, 2, 1, core_size, core_size)
        raw = aux["source_core"].reshape(scenes, 2, 1, core_size, core_size)
        probability = aux["probability"].reshape(scenes, 2, 1, core_size, core_size)
        target_mask = aux["mask_core"].reshape(scenes, 2, 1, core_size, core_size)
        model_pixel = torch.abs(pred - target).mean(dim=(1, 2, 3, 4)).cpu().numpy()
        raw_pixel = torch.abs(raw - target).mean(dim=(1, 2, 3, 4)).cpu().numpy()
        model_boundary = torch.abs(soft_boundary(probability.reshape(-1, 1, core_size, core_size)) - soft_boundary(target_mask.reshape(-1, 1, core_size, core_size))).mean(dim=(1, 2, 3)).reshape(scenes, 2).mean(1).cpu().numpy()
        raw_probability = foreground_probability(raw.reshape(-1, 1, core_size, core_size), batch["midpoint"].to(device).repeat_interleave(2), batch["polarity"].to(device).repeat_interleave(2))
        raw_boundary = torch.abs(soft_boundary(raw_probability) - soft_boundary(target_mask.reshape(-1, 1, core_size, core_size))).mean(dim=(1, 2, 3)).reshape(scenes, 2).mean(1).cpu().numpy()
        paired_raw_probability = raw_probability.reshape(scenes, 2, 1, core_size, core_size)
        cross_selector = batch["pair_kind"].numpy() == 2
        if cross_selector.any():
            sdf = batch["sdf"][..., (patch_size - core_size) // 2:(patch_size + core_size) // 2, (patch_size - core_size) // 2:(patch_size + core_size) // 2].to(device)
            cross_weight = torch.exp(-torch.abs(sdf[cross_selector, 0]) / 9.0)
            model_cross = torch.abs(probability[cross_selector, 0] - probability[cross_selector, 1])
            raw_cross = torch.abs(paired_raw_probability[cross_selector, 0] - paired_raw_probability[cross_selector, 1])
            model_cross = ((model_cross * cross_weight).sum(dim=(1, 2, 3)) / cross_weight.sum(dim=(1, 2, 3)).clamp_min(1.0)).cpu().numpy()
            raw_cross = ((raw_cross * cross_weight).sum(dim=(1, 2, 3)) / cross_weight.sum(dim=(1, 2, 3)).clamp_min(1.0)).cpu().numpy()
            cross_indices = np.flatnonzero(cross_selector)
            for local, item in enumerate(cross_indices):
                role = batch["role"][int(item)]
                role_values[role]["model_cross_boundary"].append(float(model_cross[local]))
                role_values[role]["raw_cross_boundary"].append(float(raw_cross[local]))
        pred_flat = pred.reshape(scenes * 2, 1, core_size, core_size)
        target_flat = target.reshape(scenes * 2, 1, core_size, core_size)
        raw_flat = raw.reshape(scenes * 2, 1, core_size, core_size)
        model_texture = torch.abs((pred_flat - lowpass(pred_flat, 9)) - (target_flat - lowpass(target_flat, 9))).mean(dim=(1, 2, 3)).reshape(scenes, 2).mean(1).cpu().numpy()
        raw_texture = torch.abs((raw_flat - lowpass(raw_flat, 9)) - (target_flat - lowpass(target_flat, 9))).mean(dim=(1, 2, 3)).reshape(scenes, 2).mean(1).cpu().numpy()
        for item, role in enumerate(batch["role"]):
            role_values[role]["model_pixel"].append(float(model_pixel[item])); role_values[role]["raw_pixel"].append(float(raw_pixel[item]))
            role_values[role]["model_boundary"].append(float(model_boundary[item])); role_values[role]["raw_boundary"].append(float(raw_boundary[item]))
            role_values[role]["model_texture"].append(float(model_texture[item])); role_values[role]["raw_texture"].append(float(raw_texture[item]))
            for view in range(2):
                pred_sig = topology_signature((probability[item, view, 0].cpu().numpy() >= 0.5).astype(np.uint8))
                raw_sig = topology_signature((raw_probability.reshape(scenes, 2, 1, core_size, core_size)[item, view, 0].cpu().numpy() >= 0.5).astype(np.uint8))
                target_sig = topology_signature((target_mask[item, view, 0].cpu().numpy() >= 0.5).astype(np.uint8))
                topology_mismatches += int(pred_sig != target_sig)
                raw_topology_mismatches += int(raw_sig != target_sig)
                raw_clear_added_topology_failures += int(raw_sig == target_sig and pred_sig != target_sig)
        identity_mask = batch["identity"].reshape(-1).numpy().astype(bool)
        if identity_mask.any():
            changes = torch.abs(pred.reshape(-1, 1, core_size, core_size) - raw.reshape(-1, 1, core_size, core_size)).mean(dim=(1, 2, 3)).cpu().numpy()
            identity_changes.extend((changes[identity_mask] * 255.0).tolist())
        motion_selector = batch["pair_kind"].numpy() == 1
        if motion_selector.any():
            selected_target = target_mask[motion_selector]
            support = F.max_pool2d(selected_target.reshape(-1, 1, core_size, core_size), 49, stride=1, padding=24)
            pred_centers = supported_edge_centroid(probability[motion_selector].reshape(-1, 1, core_size, core_size), support).reshape(-1, 2, 2)
            raw_centers = supported_edge_centroid(raw_probability.reshape(scenes, 2, 1, core_size, core_size)[motion_selector].reshape(-1, 1, core_size, core_size), support).reshape(-1, 2, 2)
            target_centers = supported_edge_centroid(selected_target.reshape(-1, 1, core_size, core_size), support).reshape(-1, 2, 2)
            target_delta = target_centers[:, 1] - target_centers[:, 0]
            errors = ((pred_centers[:, 1] - pred_centers[:, 0]) - target_delta).cpu().numpy()
            raw_errors = ((raw_centers[:, 1] - raw_centers[:, 0]) - target_delta).cpu().numpy()
            motion_errors.extend((float(row[0]), float(row[1])) for row in errors)
            raw_motion_errors.extend((float(row[0]), float(row[1])) for row in raw_errors)
        if max_batches and batch_index >= max_batches:
            break

    role_summary: dict[str, Any] = {}
    ratios: dict[str, float] = {}
    for role, values in role_values.items():
        summary = {name: float(np.mean(rows)) for name, rows in values.items()}
        summary.update(
            pixel_ratio=summary["model_pixel"] / max(summary["raw_pixel"], 1e-8),
            boundary_ratio=summary["model_boundary"] / max(summary["raw_boundary"], 1e-8),
            texture_ratio=summary["model_texture"] / max(summary["raw_texture"], 1e-8),
        )
        role_summary[role] = summary
    boundary_roles = [name for name in ("difficult_contour", "clean_contour_anchor", "cross_tile_and_dense") if name in role_summary]
    texture_roles = [name for name in ("textured_general_geometry", "identity_and_detail_guard") if name in role_summary]
    photometry_roles = [name for name in ("exposure_coherent_bundle",) if name in role_summary]
    ratios["boundary"] = max((role_summary[name]["boundary_ratio"] for name in boundary_roles), default=1.0)
    ratios["texture"] = max((role_summary[name]["texture_ratio"] for name in texture_roles), default=1.0)
    ratios["photometry"] = max((role_summary[name]["pixel_ratio"] for name in photometry_roles), default=1.0)
    ratios["exposure_stability"] = max(
        (
            role_summary[name].get("model_cross_boundary", 0.0)
            / max(role_summary[name].get("raw_cross_boundary", 0.0), 0.002)
            for name in photometry_roles
        ),
        default=1.0,
    )
    if motion_errors and raw_motion_errors:
        motion_array = np.asarray(motion_errors)
        raw_motion_array = np.asarray(raw_motion_errors)
        motion_mae = float(np.mean(np.abs(motion_array)))
        raw_motion_mae = float(np.mean(np.abs(raw_motion_array)))
        motion_p95 = float(np.percentile(np.abs(motion_array), 95))
        ratios["motion"] = motion_mae / max(raw_motion_mae, 0.04)
        signed_bias = np.mean(motion_array, axis=0)
    else:
        ratios["motion"], signed_bias = 1.0, np.asarray([0.0, 0.0])
        motion_mae, raw_motion_mae, motion_p95 = 0.0, 0.0, 0.0
    mean_parts = {name: value / max(count, 1) for name, value in sums.items()}
    safety = {
        "tile_mean_abs_gray": float(mean_parts.get("consistency", 0.0) * 255.0),
        "identity_mean_abs_gray": float(np.mean(identity_changes)) if identity_changes else 0.0,
        "topology_mismatch_count": int(topology_mismatches),
        "raw_topology_mismatch_count": int(raw_topology_mismatches),
        "raw_clear_added_topology_failures": int(raw_clear_added_topology_failures),
        "motion_mae_px": motion_mae,
        "raw_motion_mae_px": raw_motion_mae,
        "motion_p95_px": motion_p95,
        "motion_regression_to_raw_px": motion_mae - raw_motion_mae,
        "signed_motion_bias_x_px": float(signed_bias[0]),
        "signed_motion_bias_y_px": float(signed_bias[1]),
        "cross_observation_contour_gray": float(mean_parts.get("cross_observation_contour", 0.0) * 255.0),
        "low_branch_edge_leakage_gray": float(mean_parts.get("low_branch_edge_leakage", 0.0) * 255.0),
    }
    references = GATES["training_diagnostic_references"]
    diagnostic_flags = []
    reference_pairs = {
        "tile_mean_abs_gray": "tile_mean_abs_gray",
        "identity_mean_abs_gray": "identity_mean_abs_gray",
        "raw_clear_added_topology_failures": "raw_clear_added_topology_failures",
        "motion_mae_px": "motion_mae_px",
        "motion_p95_px": "motion_p95_px",
        "cross_observation_boundary_gray": "cross_observation_contour_gray",
        "low_branch_edge_leakage_gray": "low_branch_edge_leakage_gray",
    }
    for reference_name, metric_name in reference_pairs.items():
        if float(safety[metric_name]) > float(references[reference_name]):
            diagnostic_flags.append(metric_name)
    if max(abs(safety["signed_motion_bias_x_px"]), abs(safety["signed_motion_bias_y_px"])) > float(references["absolute_signed_bias_each_axis_px"]):
        diagnostic_flags.append("signed_motion_bias")
    safety["diagnostic_flags"] = diagnostic_flags
    ratio_values = list(ratios.values())
    worst_ratio = max(ratio_values)
    mean_ratio = float(np.mean(ratio_values))
    balanced_score = 0.60 * worst_ratio + 0.40 * mean_ratio
    return {"losses": mean_parts, "roles": role_summary, "normalized_domain_ratios": ratios, "worst_normalized_domain_error": worst_ratio, "mean_normalized_domain_error": mean_ratio, "balanced_score": balanced_score, "diagnostics": safety, "safety": safety, "evaluated_cases": count, "evaluated_views": count * 2, "evaluated_scenes": len(loader.dataset.records)}


@torch.no_grad()
def save_synthetic_preview(model: nn.Module, dataset: R90SceneDataset, device: torch.device, epoch: int, amp_enabled: bool) -> list[str]:
    output_dir = RESULTS_DIR / "synthetic_live_validation" / f"epoch_{epoch:03d}"
    output_dir.mkdir(parents=True, exist_ok=True)
    for stale in output_dir.glob("validation_*.png"):
        stale.unlink()
    outputs = []
    preview_indices: list[int] = []
    seen_roles: set[str] = set()
    for index in range(len(dataset)):
        role = dataset.role_at(index)
        if role not in seen_roles:
            preview_indices.append(index)
            seen_roles.add(role)
        if len(preview_indices) == 7:
            break
    for output_index, index in enumerate(preview_indices):
        item = dataset[index]
        source = item["source"][0:1].to(device)
        with torch.autocast(device_type="cuda", dtype=torch.bfloat16, enabled=amp_enabled):
            prediction = model(source)[0, 0].float().cpu().numpy()
        raw = item["source"][0, 0].numpy(); target = item["target"][0, 0].numpy(); mask = item["mask"][0, 0].numpy()
        sheet = np.concatenate([raw, prediction, target, mask], axis=1)
        sheet = np.rint(np.clip(sheet, 0, 1) * 255).astype(np.uint8)
        cv2.putText(sheet, "RAW", (8, 24), cv2.FONT_HERSHEY_SIMPLEX, 0.6, 255, 2, cv2.LINE_AA)
        cv2.putText(sheet, f"R90 E{epoch}", (item["source"].shape[-1] + 8, 24), cv2.FONT_HERSHEY_SIMPLEX, 0.6, 255, 2, cv2.LINE_AA)
        cv2.putText(sheet, "TARGET", (item["source"].shape[-1] * 2 + 8, 24), cv2.FONT_HERSHEY_SIMPLEX, 0.6, 255, 2, cv2.LINE_AA)
        cv2.putText(sheet, "MASK", (item["source"].shape[-1] * 3 + 8, 24), cv2.FONT_HERSHEY_SIMPLEX, 0.6, 255, 2, cv2.LINE_AA)
        path = output_dir / f"validation_{output_index:02d}_{item['role']}.png"
        cv2.imwrite(str(path), sheet)
        outputs.append(str(path))
    return outputs


def read_grayscale(path: Path) -> np.ndarray:
    encoded = np.fromfile(path, dtype=np.uint8)
    image = cv2.imdecode(encoded, cv2.IMREAD_UNCHANGED)
    if image is None:
        raise RuntimeError(f"Cannot read live-validation image: {path}")
    if image.ndim == 3:
        image = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    if image.dtype == np.uint16:
        return image.astype(np.float32) / 65535.0
    if np.issubdtype(image.dtype, np.integer):
        return image.astype(np.float32) / float(np.iinfo(image.dtype).max)
    image = image.astype(np.float32)
    maximum = float(np.nanmax(image))
    return image / maximum if maximum > 1.0 else image


@torch.no_grad()
def save_real_live_preview(model: nn.Module, device: torch.device, epoch: int, amp_enabled: bool) -> list[str]:
    input_dir = ROOT / "data" / "live_validation"
    output_dir = RESULTS_DIR / "real_live_validation" / f"epoch_{epoch:03d}"
    output_dir.mkdir(parents=True, exist_ok=True)
    outputs: list[str] = []
    model.eval()
    for source_path in sorted(input_dir.glob("*.bmp")):
        raw = np.clip(read_grayscale(source_path), 0.0, 1.0)
        tensor = torch.from_numpy(raw).unsqueeze(0).unsqueeze(0).to(device)
        halo = int(DESIGN["architecture"]["tile_contract"]["minimum_halo_px"])
        tensor = F.pad(tensor, (halo, halo, halo, halo), mode="reflect")
        with torch.autocast(device_type="cuda", dtype=torch.bfloat16, enabled=amp_enabled):
            prediction = model(tensor)[0, 0].float().cpu().numpy()
        prediction = np.clip(prediction[halo:halo + raw.shape[0], halo:halo + raw.shape[1]], 0.0, 1.0)
        difference = np.clip(np.abs(prediction - raw) * 8.0, 0.0, 1.0)
        sheet = np.concatenate([raw, prediction, difference], axis=1)
        sheet_u8 = np.rint(sheet * 255.0).astype(np.uint8)
        width = raw.shape[1]
        cv2.putText(sheet_u8, "RAW", (8, 24), cv2.FONT_HERSHEY_SIMPLEX, 0.6, 255, 2, cv2.LINE_AA)
        cv2.putText(sheet_u8, f"R90 E{epoch}", (width + 8, 24), cv2.FONT_HERSHEY_SIMPLEX, 0.6, 255, 2, cv2.LINE_AA)
        cv2.putText(sheet_u8, "ABS DIFF x8", (2 * width + 8, 24), cv2.FONT_HERSHEY_SIMPLEX, 0.6, 255, 2, cv2.LINE_AA)
        output_path = output_dir / f"{source_path.stem}_raw_r90_diff.png"
        if not cv2.imwrite(str(output_path), sheet_u8):
            raise RuntimeError(f"Cannot save live-validation preview: {output_path}")
        outputs.append(str(output_path))
    if not outputs:
        raise RuntimeError(f"No live-validation BMP files found in {input_dir}")
    return outputs


def learning_rate(epoch: int, total_epochs: int) -> float:
    maximum = float(DESIGN["training"]["learning_rate"])
    minimum = float(DESIGN["training"]["minimum_learning_rate"])
    if epoch <= 3:
        return maximum * epoch / 3.0
    progress = (epoch - 3) / max(total_epochs - 3, 1)
    return minimum + 0.5 * (maximum - minimum) * (1.0 + math.cos(math.pi * progress))


def checkpoint_payload(model: nn.Module, ema: nn.Module, epoch: int, metrics: dict[str, Any], metadata: dict[str, Any]) -> dict[str, Any]:
    return {"experiment_id": DESIGN["experiment_id"], "epoch": int(epoch), "model_state_dict": model.state_dict(), "ema_state_dict": ema.state_dict(), "metrics": metrics, "metadata": metadata, "checkpoint_loaded": False, "resume_source": None}


def register_formal_run(run_id: str, metadata: dict[str, Any]) -> None:
    path = ROOT / AUTH["run_registry"]
    registry = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {"experiment_id": DESIGN["experiment_id"], "formal_run_limit": 1, "formal_runs": []}
    if registry["formal_runs"]:
        raise RuntimeError("The single authorized R90 formal run has already been registered")
    registry["formal_runs"].append({"run_id": run_id, "registered_at": datetime.now().isoformat(), "status": "starting", **metadata})
    json_dump(path, registry)


def update_formal_registry(run_id: str, status: str, **fields: Any) -> None:
    path = ROOT / AUTH["run_registry"]
    registry = json.loads(path.read_text(encoding="utf-8"))
    row = next(item for item in registry["formal_runs"] if item["run_id"] == run_id)
    row.update(status=status, **fields)
    json_dump(path, registry)


def preflight(run_kind: str) -> tuple[Path, dict[str, Any], dict[str, Any]]:
    if any(token in " ".join(sys.argv).lower() for token in ("checkpoint", "resume", "pretrain", "teacher", "pseudo")):
        raise RuntimeError("Scratch guard rejected a forbidden launcher token")
    package = ROOT / "data" / ("r90_formal" if run_kind == "formal" else "r90_smoke")
    manifest_path, audit_path = package / "manifest.json", package / "audit.json"
    if not manifest_path.is_file() or not audit_path.is_file():
        raise FileNotFoundError(f"Dataset and audit are required: {package}")
    manifest, audit = json.loads(manifest_path.read_text(encoding="utf-8")), json.loads(audit_path.read_text(encoding="utf-8"))
    if not audit.get("passed"):
        raise RuntimeError("Dataset audit did not pass")
    if not IMPLEMENTATION_LOCK_PATH.is_file():
        raise RuntimeError("The implementation must be frozen before training")
    implementation_lock = json.loads(IMPLEMENTATION_LOCK_PATH.read_text(encoding="utf-8"))
    if implementation_lock.get("status") != "frozen_before_formal_data":
        raise RuntimeError("Implementation lock is not active")
    for relative, expected in implementation_lock.get("files", {}).items():
        if sha256_file(ROOT / relative) != expected:
            raise RuntimeError(f"Implementation changed after freezing: {relative}")
    generator_hash = implementation_lock["files"]["scripts/generate_dataset.py"]
    if manifest.get("generator_sha256") != generator_hash or not audit.get("generator_hash_pass"):
        raise RuntimeError("Dataset was not produced by the frozen generator")
    if run_kind == "formal":
        if int(manifest["scene_count"]) != 1280 or int(manifest["total_observations"]) != 5120 or not audit.get("full_array_hash_audit"):
            raise RuntimeError("Formal dataset lock failed")
        seal_path = ROOT / "data" / "r90_locked_holdout" / "SEALED.json"
        if not seal_path.is_file():
            raise RuntimeError("The locked holdout must be generated and sealed before formal training")
        seal = json.loads(seal_path.read_text(encoding="utf-8"))
        if seal.get("status") != "sealed_unread_until_checkpoint_frozen" or seal.get("training_access_allowed"):
            raise RuntimeError("Locked holdout seal is invalid")
    return package, manifest, audit


def run(args: argparse.Namespace) -> int:
    package, manifest, audit = preflight(args.run_kind)
    seed = int(args.seed)
    random.seed(seed); np.random.seed(seed); torch.manual_seed(seed); torch.cuda.manual_seed_all(seed)
    torch.backends.cuda.matmul.allow_tf32 = True; torch.backends.cudnn.allow_tf32 = True; torch.backends.cudnn.benchmark = True
    device = torch.device(args.device)
    if device.type == "cuda" and not torch.cuda.is_available():
        raise RuntimeError("CUDA was requested but is unavailable")
    model_module = load_module("r90_model_runtime", MODEL_PATH)
    model = model_module.build_model(base=24).to(device)
    parameter_count = int(model_module.count_parameters(model))
    if parameter_count > int(DESIGN["architecture"]["parameter_budget_max"]):
        raise RuntimeError("Model exceeds the locked parameter budget")
    initial_hash = state_sha256(model)
    ema = copy.deepcopy(model).eval().requires_grad_(False)
    optimizer = torch.optim.AdamW(model.parameters(), lr=float(DESIGN["training"]["learning_rate"]), weight_decay=float(DESIGN["training"]["weight_decay"]))
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_id = f"R90_scratch_seed{seed}_{timestamp}"
    run_dir = ROOT / "weights" / args.run_kind / f"seed_{seed}" / run_id
    if run_dir.exists():
        raise FileExistsError(f"Output already exists: {run_dir}")
    weight_dir = run_dir / "weights"; weight_dir.mkdir(parents=True)
    run_record_dir = RUNS_DIR / (("training_" if args.run_kind == "formal" else "smoke_") + run_id)
    run_record_dir.mkdir(parents=True)
    metadata = {
        "experiment_id": DESIGN["experiment_id"], "run_id": run_id, "run_kind": args.run_kind, "seed": seed, "device": str(device),
        "parameter_count": parameter_count, "initial_parameter_sha256": initial_hash, "architecture_sha256": sha256_file(MODEL_PATH),
        "trainer_sha256": sha256_file(Path(__file__)), "locked_design_sha256": sha256_file(DESIGN_PATH), "acceptance_gates_sha256": sha256_file(GATES_PATH),
        "authorization_sha256": sha256_file(AUTH_PATH), "dataset_content_sha256": manifest["content_sha256"], "dataset_audit": audit,
        "optical_statistics_sha256": sha256_file(OPTICAL_PATH), "real_optical_aggregate_statistics_only": True,
        "implementation_lock_sha256": sha256_file(IMPLEMENTATION_LOCK_PATH),
        "checkpoint_loaded": False, "resume_source": None, "teacher_used": False, "real_training_pixels": False, "optimizer_fresh": True,
        "ema_initialized_from_random_model": True, "started_at": datetime.now().isoformat(), "run_dir": str(run_dir),
    }
    if args.run_kind == "formal":
        register_formal_run(run_id, {"seed": seed, "initial_parameter_sha256": initial_hash, "dataset_content_sha256": manifest["content_sha256"]})
    json_dump(run_record_dir / "scratch_initialization_audit.json", metadata)
    active_path = RUNS_DIR / "launcher_logs" / ("active_formal_run.json" if args.run_kind == "formal" else "active_smoke_run.json")
    total_epochs = 1 if args.run_kind == "smoke" else int(DESIGN["training"]["epochs"])
    json_dump(active_path, {**metadata, "status": "active", "planned_epochs": total_epochs, "completed_epoch": 0})
    amp_enabled = device.type == "cuda" and not args.no_amp
    names = ["total", "pixel", "low_band", "gradient", "detail_l1", "detail_correlation", "detail_energy", "signed_distance", "boundary_iou", "auxiliary_geometry", "topology", "translation", "displacement", "signed_bias_loss", "consistency", "cross_observation", "cross_observation_low", "cross_observation_contour", "low_branch_edge_leakage", "identity", "clear_input_guard", "signed_bias_x", "signed_bias_y"]
    fields = ["epoch", "lr", "seconds", "patch", "core", "scene_batch", "accumulation", "gpu_peak_gib"] + [f"train_{name}" for name in names] + ["val_balanced_score", "val_worst_domain", "val_mean_domain", "val_diagnostic_flags", "val_tile_gray", "val_cross_observation_gray", "val_low_branch_leakage_gray", "val_identity_gray", "val_topology_mismatch", "val_added_topology_failures", "val_motion_mae", "val_motion_p95", "val_motion_regression_to_raw", "val_motion_bias_x", "val_motion_bias_y"]
    log_path = run_record_dir / "training_log.csv"
    with log_path.open("w", newline="", encoding="utf-8") as handle:
        csv.DictWriter(handle, fieldnames=fields).writeheader()
    best_balanced, best_balanced_epoch = float("inf"), 0
    latest_validation: dict[str, Any] = {}
    try:
        for epoch in range(1, total_epochs + 1):
            started = time.perf_counter(); stage = stage_for_epoch(epoch, args.run_kind)
            patch_size, core_size = stage["patch_size"], stage["core_size"]
            dataset = R90SceneDataset(package, manifest, "train", patch_size, core_size, epoch)
            sampler = GoalBalancedBatchSampler(dataset, stage["scene_batch_size"], seed + epoch * 101)
            loader = DataLoader(dataset, batch_sampler=sampler, num_workers=int(args.num_workers), pin_memory=device.type == "cuda", persistent_workers=False)
            lr = learning_rate(epoch, total_epochs)
            for group in optimizer.param_groups:
                group["lr"] = lr
            model.train(); optimizer.zero_grad(set_to_none=True)
            sums: defaultdict[str, float] = defaultdict(float); seen = 0
            if device.type == "cuda":
                torch.cuda.reset_peak_memory_stats(device)
            for batch_index, batch in enumerate(loader, start=1):
                scenes = int(batch["source"].shape[0])
                source = batch["source"].to(device, non_blocking=True)
                flat = source.reshape(scenes * 2, 1, patch_size, patch_size)
                with torch.autocast(device_type="cuda", dtype=torch.bfloat16, enabled=amp_enabled):
                    details = model(flat, return_details=True)
                    total, parts, _aux = loss_components(details, batch, patch_size, core_size, epoch, enable_topology=(batch_index % 4 == 0))
                    scaled = total / stage["gradient_accumulation"]
                scaled.backward()
                if batch_index % stage["gradient_accumulation"] == 0 or batch_index == len(loader):
                    torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
                    optimizer.step(); optimizer.zero_grad(set_to_none=True); update_ema(model, ema)
                for name, value in parts.items():
                    sums[name] += float(value) * scenes
                seen += scenes
                if args.max_train_batches and batch_index >= args.max_train_batches:
                    break
            train_metrics = {name: value / max(seen, 1) for name, value in sums.items()}
            validate_now = epoch == 1 or epoch % int(DESIGN["training"]["validation_every_epochs"]) == 0 or epoch == total_epochs
            preview_paths: list[str] = []
            real_preview_paths: list[str] = []
            if validate_now:
                val_patch, val_core = (256, 128) if args.run_kind == "smoke" else (768, 384)
                val_dataset = R90SceneDataset(package, manifest, "validation", val_patch, val_core, 0, all_observations=True)
                val_loader = DataLoader(val_dataset, batch_size=2, shuffle=False, num_workers=int(args.num_workers), pin_memory=device.type == "cuda", persistent_workers=False)
                latest_validation = evaluate(ema, val_loader, device, val_patch, val_core, epoch, amp_enabled, max_batches=int(args.max_validation_batches))
                preview_paths = save_synthetic_preview(ema, val_dataset, device, epoch, amp_enabled)
                real_preview_paths = save_real_live_preview(ema, device, epoch, amp_enabled)
                score = float(latest_validation["balanced_score"])
                metrics = {"train": train_metrics, "validation": latest_validation, "stage": stage, "lr": lr}
                if score < best_balanced * (1.0 - float(DESIGN["training"]["checkpoint_selection"]["if_tied_within_fraction_choose_earlier_epoch"])):
                    best_balanced, best_balanced_epoch = score, epoch
                    torch.save(checkpoint_payload(model, ema, epoch, metrics, metadata), weight_dir / "best_balanced.pth.tar")
            elapsed = time.perf_counter() - started
            gpu_peak = torch.cuda.max_memory_allocated(device) / 2**30 if device.type == "cuda" else 0.0
            row: dict[str, Any] = {"epoch": epoch, "lr": lr, "seconds": elapsed, "patch": patch_size, "core": core_size, "scene_batch": stage["scene_batch_size"], "accumulation": stage["gradient_accumulation"], "gpu_peak_gib": gpu_peak}
            for name in names:
                row[f"train_{name}"] = train_metrics.get(name, "")
            if validate_now:
                safety = latest_validation["safety"]
                row.update(val_balanced_score=latest_validation["balanced_score"], val_worst_domain=latest_validation["worst_normalized_domain_error"], val_mean_domain=latest_validation["mean_normalized_domain_error"], val_diagnostic_flags="|".join(safety["diagnostic_flags"]), val_tile_gray=safety["tile_mean_abs_gray"], val_cross_observation_gray=safety["cross_observation_contour_gray"], val_low_branch_leakage_gray=safety["low_branch_edge_leakage_gray"], val_identity_gray=safety["identity_mean_abs_gray"], val_topology_mismatch=safety["topology_mismatch_count"], val_added_topology_failures=safety["raw_clear_added_topology_failures"], val_motion_mae=safety["motion_mae_px"], val_motion_p95=safety["motion_p95_px"], val_motion_regression_to_raw=safety["motion_regression_to_raw_px"], val_motion_bias_x=safety["signed_motion_bias_x_px"], val_motion_bias_y=safety["signed_motion_bias_y_px"])
            with log_path.open("a", newline="", encoding="utf-8") as handle:
                csv.DictWriter(handle, fieldnames=fields).writerow(row)
            metrics = {"train": train_metrics, "validation": latest_validation if validate_now else None, "stage": stage, "lr": lr, "seconds": elapsed, "gpu_peak_gib": gpu_peak}
            if epoch % int(DESIGN["training"]["checkpoint_every_epochs"]) == 0 or epoch == total_epochs:
                torch.save(checkpoint_payload(model, ema, epoch, metrics, metadata), weight_dir / f"epoch_{epoch:03d}.pth.tar")
                torch.save(checkpoint_payload(model, ema, epoch, metrics, metadata), weight_dir / "latest.pth.tar")
            progress = {**metadata, "status": "active", "planned_epochs": total_epochs, "completed_epoch": epoch, "best_balanced_epoch": best_balanced_epoch, "best_balanced_score": best_balanced if math.isfinite(best_balanced) else None, "latest_metrics": metrics, "synthetic_preview_paths": preview_paths, "real_preview_paths": real_preview_paths}
            json_dump(active_path, progress); json_dump(run_record_dir / "run_progress.json", progress)
            if args.run_kind == "formal":
                update_formal_registry(run_id, "active", completed_epoch=epoch, best_balanced_epoch=best_balanced_epoch)
            print(json.dumps({"epoch": epoch, "stage": stage, "train": train_metrics, "validation": latest_validation if validate_now else None, "seconds": elapsed, "gpu_peak_gib": gpu_peak, "best_balanced_epoch": best_balanced_epoch}), flush=True)
            if args.max_train_batches:
                break
        completed_epoch = epoch
        complete = completed_epoch == total_epochs and not args.max_train_batches
        status = "complete" if complete else "smoke_complete"
        summary = {**metadata, "status": status, "planned_epochs": total_epochs, "completed_epoch": completed_epoch, "best_balanced_epoch": best_balanced_epoch, "best_balanced_score": best_balanced if math.isfinite(best_balanced) else None, "final_validation": latest_validation, "finished_at": datetime.now().isoformat(), "weights_dir": str(weight_dir), "training_log": str(log_path)}
        json_dump(run_record_dir / "run_summary.json", summary); json_dump(active_path, summary)
        if args.run_kind == "formal":
            update_formal_registry(run_id, status, completed_epoch=completed_epoch, best_balanced_epoch=best_balanced_epoch, finished_at=summary["finished_at"])
        print(json.dumps(summary, indent=2, ensure_ascii=False), flush=True)
        return 0
    except BaseException as exc:
        failure = {**metadata, "status": "failed", "error": repr(exc), "failed_at": datetime.now().isoformat()}
        json_dump(active_path, failure); json_dump(run_record_dir / "failure.json", failure)
        if args.run_kind == "formal":
            update_formal_registry(run_id, "failed", error=repr(exc), failed_at=failure["failed_at"])
        raise


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--device", default="cuda:0")
    parser.add_argument("--seed", type=int, default=int(DESIGN["training"]["seed"]))
    parser.add_argument("--num-workers", type=int, default=4)
    parser.add_argument("--run-kind", choices=("smoke", "formal"), default="smoke")
    parser.add_argument("--no-amp", action="store_true")
    parser.add_argument("--max-train-batches", type=int, default=0)
    parser.add_argument("--max-validation-batches", type=int, default=0)
    return run(parser.parse_args())


if __name__ == "__main__":
    raise SystemExit(main())

"""Recoverable procedural observations and same-content clear counterfactuals."""
from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

import cv2
import numpy as np
import torch
from torch.utils.data import Dataset
PROJECT_ROOT = Path(__file__).resolve().parents[3]


ROOT = Path(__file__).resolve().parents[1]
CONFIG = json.loads((ROOT / "config" / "experiment.json").read_text(encoding="utf-8"))


def warp_array(array: np.ndarray, dx: float, dy: float, interpolation: int) -> np.ndarray:
    if abs(dx) + abs(dy) < 1e-10:
        return np.asarray(array).copy()
    matrix = np.asarray([[1.0, 0.0, dx], [0.0, 1.0, dy]], dtype=np.float32)
    return cv2.warpAffine(
        np.asarray(array), matrix, (array.shape[1], array.shape[0]),
        flags=interpolation, borderMode=cv2.BORDER_REFLECT_101,
    )


def analytic_texture(height: int, width: int, global_y: int, global_x: int, rng: np.random.Generator) -> np.ndarray:
    yy, xx = np.mgrid[0:height, 0:width].astype(np.float32)
    yy += float(global_y) + 0.5
    xx += float(global_x) + 0.5
    texture = np.zeros((height, width), dtype=np.float32)
    lo, hi = CONFIG["data"]["augmentation"]["analytic_texture_period_px"]
    for _ in range(int(rng.integers(2, 5))):
        angle = float(rng.uniform(0.0, math.pi))
        period = float(np.exp(rng.uniform(np.log(lo), np.log(hi))))
        phase = float(rng.uniform(-math.pi, math.pi))
        coordinate = xx * math.cos(angle) + yy * math.sin(angle)
        texture += float(rng.uniform(0.4, 1.0)) * np.sin(2.0 * math.pi * coordinate / period + phase)
    if rng.random() < 0.70:
        for _ in range(int(rng.integers(1, 4))):
            angle = float(rng.uniform(0.0, math.pi))
            cx = float(global_x + rng.uniform(0, width))
            cy = float(global_y + rng.uniform(0, height))
            distance = np.abs((xx - cx) * math.sin(angle) - (yy - cy) * math.cos(angle))
            sigma = float(rng.uniform(0.38, 1.30))
            texture += float(rng.uniform(-1.1, 1.1)) * np.exp(-0.5 * (distance / sigma) ** 2)
    texture -= float(texture.mean())
    scale = float(np.percentile(np.abs(texture), 99.0))
    if scale > 1e-6:
        texture /= scale
    return np.clip(texture, -1.0, 1.0).astype(np.float32)


def flat_field(height: int, width: int, rng: np.random.Generator) -> np.ndarray:
    yy, xx = np.mgrid[0:height, 0:width].astype(np.float32)
    xx = (xx + 0.5) / max(width, 1) - 0.5
    yy = (yy + 0.5) / max(height, 1) - 0.5
    base = float(rng.uniform(0.16, 0.86))
    field = base + float(rng.uniform(-0.09, 0.09)) * xx + float(rng.uniform(-0.09, 0.09)) * yy
    field += float(rng.uniform(-0.025, 0.025)) * (xx * xx + yy * yy - 1.0 / 6.0)
    return np.clip(field, 0.04, 0.96).astype(np.float32)


def shared_photometry(image: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    """Exposure diversity shared by input and label, never source-only."""
    aug = CONFIG["data"]["augmentation"]
    contrast = float(rng.uniform(*aug["shared_contrast"]))
    gamma = float(rng.uniform(*aug["shared_gamma"]))
    amplitude = float(rng.uniform(*aug["shared_illumination_amplitude"]))
    result = np.power(np.clip(image, 0.0, 1.0), gamma).astype(np.float32)
    centre = float(np.median(result))
    result = centre + contrast * (result - centre)
    if amplitude > 0:
        yy, xx = np.mgrid[0:image.shape[0], 0:image.shape[1]].astype(np.float32)
        xx = (xx + 0.5) / image.shape[1] - 0.5
        yy = (yy + 0.5) / image.shape[0] - 0.5
        angle = float(rng.uniform(0.0, 2.0 * math.pi))
        illumination = 1.0 + amplitude * 2.0 * (math.cos(angle) * xx + math.sin(angle) * yy)
        result *= illumination
    return np.clip(result, 0.0, 1.0).astype(np.float32)


def motion_kernel(length: int, angle: float) -> np.ndarray:
    size = max(3, int(length) | 1)
    kernel = np.zeros((size, size), dtype=np.float32)
    centre = (size - 1) * 0.5
    radius = centre
    dx, dy = math.cos(angle) * radius, math.sin(angle) * radius
    cv2.line(
        kernel,
        (int(round(centre - dx)), int(round(centre - dy))),
        (int(round(centre + dx)), int(round(centre + dy))),
        1.0, 1, cv2.LINE_AA,
    )
    return kernel / max(float(kernel.sum()), 1e-6)


def degrade_target(target: np.ndarray, rng: np.random.Generator, progress: float, flat: bool) -> np.ndarray:
    """Local PSF/noise forward model with retained target phase and radiometry."""
    aug = CONFIG["data"]["augmentation"]
    sigma_min, sigma_max = map(float, aug["blur_sigma_px"])
    active_max = 0.95 + progress * (sigma_max - 0.95)
    sigma_x = float(np.exp(rng.uniform(np.log(max(sigma_min, 0.2)), np.log(max(active_max, sigma_min + 1e-3)))))
    sigma_y = float(np.clip(sigma_x * rng.uniform(0.68, 1.42), sigma_min, active_max))
    observed = cv2.GaussianBlur(target, (0, 0), sigmaX=sigma_x, sigmaY=sigma_y, borderType=cv2.BORDER_REFLECT_101)

    if not flat and rng.random() < 0.08 + 0.30 * progress:
        length = int(rng.choice([3, 5, 7]))
        observed = cv2.filter2D(observed, -1, motion_kernel(length, float(rng.uniform(0.0, math.pi))), borderType=cv2.BORDER_REFLECT_101)
    if not flat and rng.random() < 0.06 + 0.20 * progress:
        ghost = warp_array(observed, float(rng.uniform(-1.4, 1.4)), float(rng.uniform(-1.4, 1.4)), cv2.INTER_LINEAR)
        mix = float(rng.uniform(0.025, 0.085))
        observed = (1.0 - mix) * observed + mix * ghost

    noise_min, noise_max = map(float, aug["noise_sigma"])
    active_noise = noise_min + progress * (noise_max - noise_min)
    sigma_noise = float(rng.uniform(noise_min, max(noise_min, active_noise)))
    if flat:
        sigma_noise = min(noise_max, sigma_noise * 1.25)
    noise = rng.normal(0.0, sigma_noise, target.shape).astype(np.float32)
    row = rng.normal(0.0, 0.0015 + 0.0025 * progress, (target.shape[0], 1)).astype(np.float32)
    column = rng.normal(0.0, 0.0008 + 0.0015 * progress, (1, target.shape[1])).astype(np.float32)
    return np.clip(observed + noise + row + column, 0.0, 1.0).astype(np.float32)


class R103Dataset(Dataset):
    """Each item is one degraded observation plus its exact clear counterpart."""

    mode_names = {0: "base", 1: "innovation", 3: "flat_negative"}

    def __init__(self, split: str, patch_size: int, epoch: int, *, validation_limit: int = 0):
        self.package = Path(PROJECT_ROOT / CONFIG["data"]["base_package"])
        self.manifest = json.loads((self.package / "manifest.json").read_text(encoding="utf-8"))
        self.records = sorted(
            (record for record in self.manifest["records"] if record["split"] == split),
            key=lambda row: int(row["scene_index"]),
        )
        if validation_limit > 0:
            self.records = self.records[: int(validation_limit)]
        self.split = str(split)
        self.patch_size = int(patch_size)
        self.epoch = int(epoch)
        self.canvas_size = int(self.manifest["canvas_size"])
        if self.patch_size > self.canvas_size or self.patch_size % 8:
            raise ValueError("patch_size must fit the canvas and be divisible by 8")

    def __len__(self) -> int:
        return len(self.records)

    def _rng(self, scene_index: int, salt: int = 0) -> np.random.Generator:
        seed = (
            int(CONFIG["data"]["augmentation_seed"]) * 1000003
            + int(scene_index) * 10007 + int(self.epoch) * 7919
            + int(salt) * 104729 + self.patch_size * 31
        ) % (2**63 - 1)
        return np.random.default_rng(seed)

    def _mode(self, index: int, rng: np.random.Generator) -> int:
        aug = CONFIG["data"]["augmentation"]
        if self.split != "train":
            cycle = index % 10
            return 3 if cycle == 0 else (1 if cycle in (1, 2, 3, 4) else 0)
        value = float(rng.random())
        if value < float(aug["flat_negative_probability"]):
            return 3
        if value < float(aug["flat_negative_probability"]) + float(aug["innovation_probability"]):
            return 1
        return 0

    def _origin(self, mask: np.ndarray, rng: np.random.Generator, prefer_edge: bool) -> tuple[int, int]:
        maximum = self.canvas_size - self.patch_size
        if maximum <= 0:
            return 0, 0
        best: tuple[float, int, int] | None = None
        for _ in range(14 if prefer_edge else 5):
            y = int(rng.integers(0, maximum // 8 + 1)) * 8
            x = int(rng.integers(0, maximum // 8 + 1)) * 8
            crop = np.asarray(mask[y:y + self.patch_size, x:x + self.patch_size]) >= 128
            fraction = float(crop.mean())
            boundary = int(np.count_nonzero(crop[1:] != crop[:-1]) + np.count_nonzero(crop[:, 1:] != crop[:, :-1]))
            score = float(boundary) - 5000.0 * max(0.02 - fraction, 0.0) - 5000.0 * max(fraction - 0.90, 0.0)
            if not prefer_edge:
                score = -abs(fraction - 0.35) + 0.00001 * boundary
            candidate = (score, y, x)
            if best is None or candidate[0] > best[0]:
                best = candidate
        assert best is not None
        return int(best[1]), int(best[2])

    @staticmethod
    def _to_tensor(rows: list[np.ndarray]) -> torch.Tensor:
        return torch.from_numpy(np.stack(rows).astype(np.float32, copy=False)).unsqueeze(1)

    def __getitem__(self, index: int) -> dict[str, Any]:
        record = self.records[index]
        scene_index = int(record["scene_index"])
        rng = self._rng(scene_index)
        mode = self._mode(index, rng)
        target_base = np.load(self.package / record["target"], mmap_mode="r", allow_pickle=False)
        mask_base = np.load(self.package / record["mask"], mmap_mode="r", allow_pickle=False)
        y0, x0 = self._origin(mask_base, rng, prefer_edge=(mode != 3))
        target = np.asarray(target_base[y0:y0 + self.patch_size, x0:x0 + self.patch_size], dtype=np.float32) / 255.0
        mask = np.asarray(mask_base[y0:y0 + self.patch_size, x0:x0 + self.patch_size], dtype=np.float32) / 255.0

        if mode == 1:
            texture = analytic_texture(self.patch_size, self.patch_size, y0, x0, rng)
            amplitude = float(rng.uniform(*CONFIG["data"]["augmentation"]["target_texture_amplitude"]))
            selector = int(rng.integers(0, 3))
            modulation = (0.20 + 0.80 * mask) if selector == 0 else ((1.0 - 0.80 * mask) if selector == 1 else 1.0)
            target = np.clip(target + amplitude * texture * modulation, 0.0, 1.0)
        elif mode == 3:
            target = flat_field(self.patch_size, self.patch_size, rng)
            mask = np.zeros_like(target)

        target = shared_photometry(target, rng)
        observation = record["observations"][(self.epoch + scene_index) % len(record["observations"])]
        dx = float(observation.get("motion_dx_px", 0.0))
        dy = float(observation.get("motion_dy_px", 0.0))
        target_view = warp_array(target, dx, dy, cv2.INTER_LANCZOS4).astype(np.float32)
        mask_view = warp_array(mask, dx, dy, cv2.INTER_LINEAR).astype(np.float32)
        progress = 1.0 if self.split != "train" else float(np.clip((self.epoch - 1) / 10.0, 0.0, 1.0))
        degraded = degrade_target(target_view, self._rng(scene_index, 101), progress, flat=(mode == 3))

        foreground = target_view[mask_view >= 0.5]
        background = target_view[mask_view < 0.5]
        if foreground.size and background.size:
            foreground_mean, background_mean = float(foreground.mean()), float(background.mean())
            midpoint = 0.5 * (foreground_mean + background_mean)
            polarity = 1.0 if foreground_mean > background_mean else -1.0
        else:
            midpoint, polarity = 0.5, -1.0

        return {
            "source": self._to_tensor([degraded, target_view]),
            "target": self._to_tensor([target_view, target_view]),
            "mask": self._to_tensor([mask_view, mask_view]),
            "motion": torch.tensor([(dx, dy), (dx, dy)], dtype=torch.float32),
            "identity": torch.tensor([False, True], dtype=torch.bool),
            "mode": torch.tensor(mode, dtype=torch.int64),
            "midpoint": torch.tensor(midpoint, dtype=torch.float32),
            "polarity": torch.tensor(polarity, dtype=torch.float32),
            "role": str(record["role"]),
            "scene_id": str(record["scene_id"]),
            "scene_index": torch.tensor(scene_index, dtype=torch.int64),
            "origin": torch.tensor((y0, x0), dtype=torch.int64),
        }

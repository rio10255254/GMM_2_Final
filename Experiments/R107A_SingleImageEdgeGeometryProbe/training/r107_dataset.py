"""R107 deterministic single-image degraded/clear training pairs."""
from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

import cv2
import numpy as np
import torch
from torch.utils.data import Dataset


ROOT = Path(__file__).resolve().parents[1]
CONFIG = json.loads((ROOT / "config" / "experiment.json").read_text(encoding="utf-8"))


def motion_kernel(length: int, angle: float) -> np.ndarray:
    size = max(3, int(length) | 1); kernel = np.zeros((size, size), dtype=np.float32); center = (size - 1) * 0.5
    dx, dy = math.cos(angle) * center, math.sin(angle) * center
    cv2.line(kernel, (round(center - dx), round(center - dy)), (round(center + dx), round(center + dy)), 1.0, 1, cv2.LINE_AA)
    return kernel / max(float(kernel.sum()), 1e-6)


def warp_array(array: np.ndarray, dx: float, dy: float) -> np.ndarray:
    matrix = np.asarray([[1.0, 0.0, dx], [0.0, 1.0, dy]], dtype=np.float32)
    return cv2.warpAffine(array, matrix, (array.shape[1], array.shape[0]), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT_101)


def degrade_target(target: np.ndarray, rng: np.random.Generator, flat: bool) -> tuple[np.ndarray, dict[str, float]]:
    cfg = CONFIG["data"]["degradation"]
    sigma_x = float(np.exp(rng.uniform(np.log(cfg["blur_sigma_px"][0]), np.log(cfg["blur_sigma_px"][1]))))
    sigma_y = float(np.clip(sigma_x * rng.uniform(*cfg["anisotropy"]), cfg["blur_sigma_px"][0], cfg["blur_sigma_px"][1]))
    observed = cv2.GaussianBlur(target, (0, 0), sigmaX=sigma_x, sigmaY=sigma_y, borderType=cv2.BORDER_REFLECT_101)
    if not flat and rng.random() < float(cfg["motion_blur_probability"]):
        length = int(rng.choice(cfg["motion_blur_lengths"])); observed = cv2.filter2D(observed, -1, motion_kernel(length, float(rng.uniform(0, math.pi))), borderType=cv2.BORDER_REFLECT_101)
    if not flat and rng.random() < float(cfg["ghost_probability"]):
        ghost = warp_array(observed, float(rng.uniform(-1.5, 1.5)), float(rng.uniform(-1.5, 1.5))); mix = float(rng.uniform(*cfg["ghost_mix"])); observed = (1.0 - mix) * observed + mix * ghost
    if not flat and rng.random() < float(cfg["halo_probability"]):
        broad = cv2.GaussianBlur(observed, (0, 0), sigmaX=float(rng.uniform(2.5, 5.0)), borderType=cv2.BORDER_REFLECT_101)
        observed = np.clip(observed + float(rng.uniform(-0.06, 0.06)) * (broad - observed), 0.0, 1.0)
    noise_sigma = float(rng.uniform(*cfg["noise_sigma"])); noise = rng.normal(0.0, noise_sigma, target.shape).astype(np.float32)
    row_sigma = float(rng.uniform(*cfg["row_noise_sigma"])); column_sigma = float(rng.uniform(*cfg["column_noise_sigma"])); row = rng.normal(0.0, row_sigma, (target.shape[0], 1)).astype(np.float32); column = rng.normal(0.0, column_sigma, (1, target.shape[1])).astype(np.float32)
    return np.clip(observed + noise + row + column, 0.0, 1.0).astype(np.float32), {"sigma_x": sigma_x, "sigma_y": sigma_y, "noise_sigma": noise_sigma}


class R107Dataset(Dataset):
    def __init__(self, split: str, epoch: int = 0, patch_size: int | None = None, limit: int = 0):
        self.package = ROOT / CONFIG["data"]["package_root"]
        self.manifest = json.loads((self.package / "manifest.json").read_text(encoding="utf-8"))
        self.records = [row for row in self.manifest["records"] if row["split"] == split]
        self.records.sort(key=lambda row: int(row["scene_index"]))
        if limit > 0:
            self.records = self.records[: int(limit)]
        self.split = split; self.epoch = int(epoch); self.patch_size = int(patch_size or CONFIG["data"]["training_patch_size"]); self.canvas = int(self.manifest["canvas_size"])
        if self.patch_size > self.canvas or self.patch_size % 8:
            raise ValueError("patch_size must fit the canvas and be divisible by 8")

    def __len__(self) -> int:
        return len(self.records)

    def _rng(self, scene_index: int, salt: int = 0) -> np.random.Generator:
        seed = int(CONFIG["data"]["seed"]) * 1000003 + int(scene_index) * 10007 + self.epoch * 7919 + salt * 104729
        return np.random.default_rng(seed % (2**63 - 1))

    def _origin(self, mask: np.ndarray, rng: np.random.Generator, prefer_edge: bool) -> tuple[int, int]:
        maximum = self.canvas - self.patch_size
        if maximum <= 0:
            return 0, 0
        best = None
        for _ in range(16 if prefer_edge else 6):
            y = int(rng.integers(0, maximum // 8 + 1)) * 8; x = int(rng.integers(0, maximum // 8 + 1)) * 8
            crop = mask[y:y + self.patch_size, x:x + self.patch_size] >= 128
            boundary = int(np.count_nonzero(crop[1:] != crop[:-1]) + np.count_nonzero(crop[:, 1:] != crop[:, :-1])); fraction = float(crop.mean())
            score = boundary - 4000.0 * max(0.01 - fraction, 0.0) - 4000.0 * max(fraction - 0.94, 0.0) if prefer_edge else -abs(fraction - 0.35)
            candidate = (score, y, x)
            if best is None or candidate[0] > best[0]: best = candidate
        return int(best[1]), int(best[2])

    @staticmethod
    def _stack(rows: list[np.ndarray]) -> torch.Tensor:
        return torch.from_numpy(np.stack(rows).astype(np.float32, copy=False)).unsqueeze(1)

    def __getitem__(self, index: int) -> dict[str, Any]:
        record = self.records[index]; scene_index = int(record["scene_index"]); rng = self._rng(scene_index)
        target_full = np.load(self.package / record["target"], mmap_mode="r", allow_pickle=False)
        mask_full = np.load(self.package / record["mask"], mmap_mode="r", allow_pickle=False)
        sdf_full = np.load(self.package / record["sdf"], mmap_mode="r", allow_pickle=False)
        prefer_edge = record["role"] not in ("flat_negative",)
        y0, x0 = self._origin(mask_full, rng, prefer_edge)
        target = np.asarray(target_full[y0:y0 + self.patch_size, x0:x0 + self.patch_size], dtype=np.float32) / 255.0
        mask = np.asarray(mask_full[y0:y0 + self.patch_size, x0:x0 + self.patch_size], dtype=np.float32) / 255.0
        sdf = np.asarray(sdf_full[y0:y0 + self.patch_size, x0:x0 + self.patch_size], dtype=np.float32)
        degraded, degradation = degrade_target(target, self._rng(scene_index, 101), flat=(record["role"] == "flat_negative"))
        target_width = float(record["target_width_px"]); source_width = math.sqrt(target_width * target_width + degradation["sigma_x"] * degradation["sigma_y"]); width_scale = float(np.clip(target_width / max(source_width, 1e-6), CONFIG["model"]["minimum_width_scale"], 1.0))
        edge_target = np.exp(-np.abs(sdf) / 2.5).astype(np.float32) if prefer_edge else np.zeros_like(target, dtype=np.float32)
        reliability_target = (edge_target * (mask > 0.02) * (mask < 0.98)).astype(np.float32)
        return {
            "source": self._stack([degraded, target]),
            "target": self._stack([target, target]),
            "mask": self._stack([mask, mask]),
            "sdf": self._stack([sdf, sdf]),
            "edge_target": self._stack([edge_target, np.zeros_like(edge_target)]),
            "reliability_target": self._stack([reliability_target, np.zeros_like(reliability_target)]),
            "width_scale_target": torch.tensor([width_scale, 1.0], dtype=torch.float32),
            "identity": torch.tensor([False, True], dtype=torch.bool),
            "midpoint": torch.tensor([float(record["midpoint"]), float(record["midpoint"])], dtype=torch.float32),
            "polarity": torch.tensor([float(record["polarity"]), float(record["polarity"])], dtype=torch.float32),
            "role": str(record["role"]),
            "family": str(record["family"]),
            "scene_index": torch.tensor(scene_index, dtype=torch.int64),
            "origin": torch.tensor([y0, x0], dtype=torch.int64),
            "blur_sigma": torch.tensor([math.sqrt(degradation["sigma_x"] * degradation["sigma_y"]), 0.0], dtype=torch.float32),
        }


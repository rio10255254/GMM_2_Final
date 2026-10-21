"""Deterministic three-view procedural dataset for R116.

Each scene yields two independently degraded observations with a known
subpixel translation plus one clear identity view.  Training still deploys a
single-image model; the extra views exist only to supervise consistency.
"""

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
DEGRADATIONS = (
    "standard",
    "low_contrast",
    "uneven_illumination",
    "asymmetric_blur_halo",
    "boundary_fade",
    "mixed_hard",
)


def motion_kernel(length: int, angle: float) -> np.ndarray:
    size = max(3, int(length) | 1)
    kernel = np.zeros((size, size), np.float32)
    center = (size - 1) * 0.5
    dx, dy = math.cos(angle) * center, math.sin(angle) * center
    cv2.line(
        kernel,
        (round(center - dx), round(center - dy)),
        (round(center + dx), round(center + dy)),
        1.0,
        1,
        cv2.LINE_AA,
    )
    return kernel / max(float(kernel.sum()), 1.0e-6)


def low_field(rng: np.random.Generator, side: int, amplitude: float) -> np.ndarray:
    coarse = rng.normal(0, 1, (7, 7)).astype(np.float32)
    field = cv2.resize(coarse, (side, side), interpolation=cv2.INTER_CUBIC)
    field = cv2.GaussianBlur(field, (0, 0), side / 14)
    field -= float(field.mean())
    return field * (amplitude / max(float(field.std()), 1.0e-6))


def angular_wedge(mask: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    side = mask.shape[0]
    yy, xx = np.mgrid[0:side, 0:side].astype(np.float32)
    ys, xs = np.nonzero(mask > 0.5)
    cx, cy = (float(xs.mean()), float(ys.mean())) if len(xs) else (side / 2, side / 2)
    angle = np.arctan2(yy - cy, xx - cx)
    center = float(rng.uniform(-np.pi, np.pi))
    width = float(rng.uniform(0.25, 0.75))
    distance = np.abs(np.angle(np.exp(1j * (angle - center))))
    return np.exp(-(distance ** 2) / (2 * width ** 2)).astype(np.float32)


def translate(value: np.ndarray, dx: float, dy: float,
              interpolation: int = cv2.INTER_LINEAR) -> np.ndarray:
    matrix = np.asarray([[1, 0, dx], [0, 1, dy]], np.float32)
    return cv2.warpAffine(
        value,
        matrix,
        (value.shape[1], value.shape[0]),
        flags=interpolation,
        borderMode=cv2.BORDER_REFLECT_101,
    ).astype(np.float32)


def degrade(target: np.ndarray, mask: np.ndarray, rng: np.random.Generator,
            challenge: str, flat: bool = False) -> np.ndarray:
    if challenge == "identity":
        return target.copy()
    image = target.copy()
    midpoint = float(np.median(target))
    sigma_x = float(np.exp(rng.uniform(np.log(0.65), np.log(5.5))))
    sigma_y = float(np.clip(sigma_x * rng.uniform(0.55, 1.60), 0.65, 5.5))
    if challenge in {"low_contrast", "boundary_fade", "mixed_hard"}:
        image = midpoint + float(rng.uniform(0.42, 0.92)) * (image - midpoint)
    if challenge in {"boundary_fade", "mixed_hard"}:
        background = float(np.median(target[mask < 0.1])) if np.any(mask < 0.1) else float(target.mean())
        fade = angular_wedge(mask, rng) * mask
        strength = float(rng.uniform(0.25, 0.85))
        image = image * (1.0 - strength * fade) + background * strength * fade
    if challenge in {"uneven_illumination", "mixed_hard"}:
        image += low_field(rng, target.shape[0], float(rng.uniform(0.0, 0.13)))
    image = cv2.GaussianBlur(
        image.astype(np.float32), (0, 0), sigmaX=sigma_x, sigmaY=sigma_y,
        borderType=cv2.BORDER_REFLECT_101,
    )
    if not flat and (
        challenge in {"asymmetric_blur_halo", "mixed_hard"} or rng.random() < 0.35
    ):
        image = cv2.filter2D(
            image,
            -1,
            motion_kernel(int(rng.choice([3, 5, 7, 9, 13, 17])), float(rng.uniform(0, math.pi))),
            borderType=cv2.BORDER_REFLECT_101,
        )
    if not flat and rng.random() < 0.20:
        ghost = translate(image, float(rng.uniform(-2, 2)), float(rng.uniform(-2, 2)))
        mix = float(rng.uniform(0.02, 0.12))
        image = (1.0 - mix) * image + mix * ghost
    if challenge in {"asymmetric_blur_halo", "mixed_hard"} or rng.random() < 0.28:
        broad = cv2.GaussianBlur(image, (0, 0), float(rng.uniform(3, 7)))
        image = image + float(rng.uniform(0.12, 0.65)) * (broad - image)
    image += rng.normal(0, float(rng.uniform(0.0015, 0.035)), image.shape).astype(np.float32)
    image += rng.normal(0, float(rng.uniform(0.0, 0.0045)), (image.shape[0], 1)).astype(np.float32)
    image += rng.normal(0, float(rng.uniform(0.0, 0.0030)), (1, image.shape[1])).astype(np.float32)
    return np.clip(image, 0, 1).astype(np.float32)


class R116Dataset(Dataset):
    def __init__(self, split: str, epoch: int = 0, limit: int = 0,
                 challenge_override: str | None = None,
                 role_filter: str | None = None):
        self.package = (ROOT / CONFIG["data"]["package_root"]).resolve()
        manifest = json.loads((self.package / "manifest.json").read_text(encoding="utf-8"))
        def include(row: dict[str, Any]) -> bool:
            if row["split"] != split:
                return False
            if role_filter is None:
                return True
            if role_filter == "degraded":
                return row["role"] in {"edge", "textured_edge"}
            if role_filter == "identity":
                return row["role"] == "identity"
            if role_filter == "flat_negative":
                return row["role"] == "flat_negative"
            return row["role"] == role_filter
        self.records = sorted(
            (row for row in manifest["records"] if include(row)),
            key=lambda row: int(row["scene_index"]),
        )
        if limit > 0:
            self.records = self.records[:limit]
        self.epoch = int(epoch)
        self.seed = int(CONFIG["seed"])
        self.challenge_override = challenge_override
        self.shift_range = tuple(float(value) for value in CONFIG["data"]["paired_training"]["known_subpixel_translation_px"])

    def set_epoch(self, epoch: int) -> None:
        self.epoch = int(epoch)

    def __len__(self) -> int:
        return len(self.records)

    def rng(self, scene: int, salt: int) -> np.random.Generator:
        seed = (
            self.seed * 1000003 + int(scene) * 10007 + self.epoch * 7919 + salt * 104729
        ) % (2**63 - 1)
        return np.random.default_rng(seed)

    @staticmethod
    def tensor(value: np.ndarray) -> torch.Tensor:
        return torch.from_numpy(np.asarray(value, np.float32)).unsqueeze(0)

    def __getitem__(self, index: int) -> dict[str, Any]:
        record = self.records[index]
        scene = int(record["scene_index"])
        target = np.asarray(np.load(self.package / record["target"], mmap_mode="r"), np.float32) / 255.0
        mask = np.asarray(np.load(self.package / record["mask"], mmap_mode="r"), np.float32) / 255.0
        sdf = np.asarray(np.load(self.package / record["sdf"], mmap_mode="r"), np.float32)
        flat = record["role"] == "flat_negative"
        challenge = self.challenge_override or (
            "identity" if record["role"] == "identity"
            else DEGRADATIONS[(scene + self.epoch) % len(DEGRADATIONS)]
        )
        pair_rng = self.rng(scene, 17)
        dx = float(pair_rng.uniform(*self.shift_range))
        dy = float(pair_rng.uniform(*self.shift_range))
        shifted_target = translate(target, dx, dy)
        shifted_mask = translate(mask, dx, dy)
        shifted_sdf = translate(sdf, dx, dy)
        source_a = degrade(target, mask, self.rng(scene, 101), challenge, flat=flat)
        source_b = degrade(shifted_target, shifted_mask, self.rng(scene, 211), challenge, flat=flat)
        edge_a = np.exp(-np.abs(sdf) / 2.5).astype(np.float32) if not flat else np.zeros_like(target)
        edge_b = np.exp(-np.abs(shifted_sdf) / 2.5).astype(np.float32) if not flat else np.zeros_like(target)
        return {
            "source": torch.stack((self.tensor(source_a), self.tensor(source_b), self.tensor(target))),
            "target": torch.stack((self.tensor(target), self.tensor(shifted_target), self.tensor(target))),
            "mask": torch.stack((self.tensor(mask), self.tensor(shifted_mask), self.tensor(mask))),
            "sdf": torch.stack((self.tensor(sdf), self.tensor(shifted_sdf), self.tensor(sdf))),
            "edge": torch.stack((self.tensor(edge_a), self.tensor(edge_b), self.tensor(edge_a))),
            "identity": torch.tensor([challenge == "identity", challenge == "identity", True]),
            "flat": torch.tensor([flat, flat, flat]),
            "midpoint": torch.tensor([float(record["midpoint"])] * 3, dtype=torch.float32),
            "polarity": torch.tensor([float(record["polarity"])] * 3, dtype=torch.float32),
            "pair_shift_px": torch.tensor([dx, dy], dtype=torch.float32),
            "scene_index": torch.tensor(scene),
            "role": str(record["role"]),
            "family": str(record["family"]),
            "challenge": challenge,
        }

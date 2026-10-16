"""Locked synthetic paired data for the matched R113 microprobe."""
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
DCFG = CONFIG["data"]["degradation"]
CHALLENGES = tuple(CONFIG["data"]["challenge_families"])


def motion_kernel(length: int, angle: float) -> np.ndarray:
    size = max(3, int(length) | 1)
    kernel = np.zeros((size, size), np.float32)
    center = (size - 1) * .5
    dx, dy = math.cos(angle) * center, math.sin(angle) * center
    cv2.line(kernel, (round(center - dx), round(center - dy)),
             (round(center + dx), round(center + dy)), 1, 1, cv2.LINE_AA)
    return kernel / max(float(kernel.sum()), 1e-6)


def low_field(rng: np.random.Generator, side: int, amplitude: float) -> np.ndarray:
    coarse = rng.normal(0, 1, (7, 7)).astype(np.float32)
    field = cv2.resize(coarse, (side, side), interpolation=cv2.INTER_CUBIC)
    field = cv2.GaussianBlur(field, (0, 0), side / 14)
    field -= float(field.mean())
    return field * (amplitude / max(float(field.std()), 1e-6))


def angular_wedge(mask: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    side = mask.shape[0]
    yy, xx = np.mgrid[0:side, 0:side].astype(np.float32)
    ys, xs = np.nonzero(mask > .5)
    cx, cy = (float(xs.mean()), float(ys.mean())) if len(xs) else (side / 2, side / 2)
    angle = np.arctan2(yy - cy, xx - cx)
    center = float(rng.uniform(-np.pi, np.pi)); width = float(rng.uniform(.25, .75))
    distance = np.abs(np.angle(np.exp(1j * (angle - center))))
    return np.exp(-(distance ** 2) / (2 * width ** 2)).astype(np.float32)


def degrade(target: np.ndarray, mask: np.ndarray, rng: np.random.Generator,
            challenge: str, flat: bool = False) -> tuple[np.ndarray, dict]:
    if challenge == "identity":
        return target.copy(), {"sigma": 0.0}
    low, high = DCFG["blur_sigma_px"]
    sigma_x = float(np.exp(rng.uniform(np.log(low), np.log(high))))
    sigma_y = float(np.clip(sigma_x * rng.uniform(*DCFG["anisotropy"]), low, high))
    image = target.copy(); midpoint = float(np.median(target))
    if challenge in {"low_contrast", "boundary_fade", "mixed_hard"}:
        image = midpoint + float(rng.uniform(*DCFG["contrast_scale"])) * (image - midpoint)
    if challenge in {"boundary_fade", "mixed_hard"}:
        background = float(np.median(target[mask < .1])) if np.any(mask < .1) else float(target.mean())
        strength = float(rng.uniform(*DCFG["boundary_fade_strength"]))
        fade = angular_wedge(mask, rng) * mask
        image = image * (1 - strength * fade) + background * (strength * fade)
    if challenge in {"uneven_illumination", "mixed_hard"}:
        image += low_field(rng, target.shape[0], float(rng.uniform(*DCFG["illumination_amplitude"])))
    image = cv2.GaussianBlur(image.astype(np.float32), (0, 0), sigmaX=sigma_x, sigmaY=sigma_y,
                             borderType=cv2.BORDER_REFLECT_101)
    if not flat and (challenge in {"asymmetric_blur_halo", "mixed_hard"}
                     or rng.random() < float(DCFG["motion_blur_probability"])):
        image = cv2.filter2D(image, -1, motion_kernel(int(rng.choice(DCFG["motion_blur_lengths"])),
                                                      float(rng.uniform(0, math.pi))),
                             borderType=cv2.BORDER_REFLECT_101)
    if not flat and rng.random() < float(DCFG["ghost_probability"]):
        dx, dy = float(rng.uniform(-2, 2)), float(rng.uniform(-2, 2))
        ghost = cv2.warpAffine(image, np.asarray([[1, 0, dx], [0, 1, dy]], np.float32),
                               (image.shape[1], image.shape[0]), flags=cv2.INTER_LINEAR,
                               borderMode=cv2.BORDER_REFLECT_101)
        mix = float(rng.uniform(*DCFG["ghost_mix"])); image = (1 - mix) * image + mix * ghost
    if challenge in {"asymmetric_blur_halo", "mixed_hard"} or rng.random() < float(DCFG["halo_probability"]):
        broad = cv2.GaussianBlur(image, (0, 0), float(rng.uniform(3, 7)))
        image = image + float(rng.uniform(*DCFG["halo_strength"])) * (broad - image)
    noise = float(rng.uniform(*DCFG["noise_sigma"]))
    image += rng.normal(0, noise, image.shape).astype(np.float32)
    image += rng.normal(0, float(rng.uniform(*DCFG["row_noise_sigma"])), (image.shape[0], 1)).astype(np.float32)
    image += rng.normal(0, float(rng.uniform(*DCFG["column_noise_sigma"])), (1, image.shape[1])).astype(np.float32)
    return np.clip(image, 0, 1).astype(np.float32), {"sigma": math.sqrt(sigma_x * sigma_y)}


class ProbeDataset(Dataset):
    def __init__(self, split: str, epoch: int = 0, limit: int = 0):
        self.package = Path(CONFIG["data"]["package_root"])
        selection = json.loads((ROOT / CONFIG["data"]["selection_file"]).read_text(encoding="utf-8"))
        self.records = [row for row in selection["records"] if row["split"] == split]
        if limit > 0:
            self.records = self.records[:limit]
        self.epoch = int(epoch)

    def __len__(self) -> int:
        return len(self.records)

    def rng(self, scene: int, salt: int = 0) -> np.random.Generator:
        value = (int(CONFIG["seed"]) * 1000003 + scene * 10007 + self.epoch * 7919 + salt * 104729) % (2 ** 63 - 1)
        return np.random.default_rng(value)

    @staticmethod
    def stack(rows: list[np.ndarray]) -> torch.Tensor:
        return torch.from_numpy(np.stack(rows).astype(np.float32, copy=False)).unsqueeze(1)

    def __getitem__(self, index: int) -> dict[str, Any]:
        record = self.records[index]; scene = int(record["scene_index"])
        target = np.asarray(np.load(self.package / record["target"], mmap_mode="r"), np.float32) / 255
        mask = np.asarray(np.load(self.package / record["mask"], mmap_mode="r"), np.float32) / 255
        sdf = np.asarray(np.load(self.package / record["sdf"], mmap_mode="r"), np.float32)
        challenge = "identity" if record["role"] == "identity" else CHALLENGES[(scene + self.epoch) % len(CHALLENGES)]
        source, meta = degrade(target, mask, self.rng(scene, 101), challenge, flat=record["role"] == "flat_negative")
        target_width = float(record["target_width_px"])
        source_width = math.sqrt(target_width ** 2 + meta["sigma"] ** 2)
        width_gain = float(np.clip(source_width / max(target_width, 1e-6),
                                   CONFIG["model"]["minimum_width_gain"], CONFIG["model"]["maximum_width_gain"]))
        edge = np.exp(-np.abs(sdf) / 2.5).astype(np.float32) if record["role"] != "flat_negative" else np.zeros_like(target)
        is_clear = challenge == "identity"
        return {
            "source": self.stack([source, target]), "target": self.stack([target, target]),
            "mask": self.stack([mask, mask]), "sdf": self.stack([sdf, sdf]),
            "edge": self.stack([edge, edge]), "identity": torch.tensor([is_clear, True]),
            "midpoint": torch.tensor([float(record["midpoint"])] * 2, dtype=torch.float32),
            "polarity": torch.tensor([float(record["polarity"])] * 2, dtype=torch.float32),
            "width_gain_target": torch.tensor([width_gain, 1.0], dtype=torch.float32),
            "scene_index": torch.tensor(scene), "role": record["role"],
            "family": record["family"], "challenge": challenge,
        }

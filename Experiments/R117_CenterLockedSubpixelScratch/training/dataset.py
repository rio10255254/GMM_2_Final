"""Deterministic three-view R117 dataset with exact supersampled pair labels."""

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
DEGRADATIONS = ("standard", "low_contrast", "uneven_illumination", "asymmetric_blur_halo", "boundary_fade", "mixed_hard")


def motion_kernel(length: int, angle: float) -> np.ndarray:
    size = max(3, int(length) | 1)
    kernel = np.zeros((size, size), np.float32)
    center = 0.5 * (size - 1)
    dx, dy = math.cos(angle) * center, math.sin(angle) * center
    cv2.line(kernel, (round(center - dx), round(center - dy)), (round(center + dx), round(center + dy)), 1.0, 1, cv2.LINE_AA)
    return kernel / max(float(kernel.sum()), 1.0e-6)


def low_field(rng: np.random.Generator, side: int, amplitude: float) -> np.ndarray:
    field = cv2.resize(rng.normal(0, 1, (7, 7)).astype(np.float32), (side, side), interpolation=cv2.INTER_CUBIC)
    field = cv2.GaussianBlur(field, (0, 0), side / 14)
    field -= float(field.mean())
    return field * amplitude / max(float(field.std()), 1.0e-6)


def angular_wedge(mask: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    side = mask.shape[0]
    yy, xx = np.mgrid[0:side, 0:side].astype(np.float32)
    ys, xs = np.nonzero(mask > 0.5)
    cx, cy = (float(xs.mean()), float(ys.mean())) if len(xs) else (side / 2, side / 2)
    angle = np.arctan2(yy - cy, xx - cx)
    center, width = float(rng.uniform(-np.pi, np.pi)), float(rng.uniform(0.25, 0.75))
    distance = np.abs(np.angle(np.exp(1j * (angle - center))))
    return np.exp(-(distance ** 2) / (2 * width ** 2)).astype(np.float32)


def translate(value: np.ndarray, dx: float, dy: float) -> np.ndarray:
    matrix = np.asarray(((1, 0, dx), (0, 1, dy)), np.float32)
    return cv2.warpAffine(value, matrix, (value.shape[1], value.shape[0]), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT_101)


def degrade(target: np.ndarray, mask: np.ndarray, rng: np.random.Generator, challenge: str, flat: bool) -> tuple[np.ndarray, dict[str, float]]:
    if challenge == "identity":
        return target.copy(), {"sigma_x": 0.0, "sigma_y": 0.0, "motion_length": 0.0, "motion_angle": 0.0, "reliability": 1.0}
    image = target.copy()
    midpoint = float(np.median(target))
    sigma_x = float(np.exp(rng.uniform(np.log(0.65), np.log(5.5))))
    sigma_y = float(np.clip(sigma_x * rng.uniform(0.55, 1.60), 0.65, 5.5))
    reliability = 1.0
    if challenge in {"low_contrast", "boundary_fade", "mixed_hard"}:
        image = midpoint + float(rng.uniform(0.42, 0.92)) * (image - midpoint)
        reliability *= 0.82
    if challenge in {"boundary_fade", "mixed_hard"}:
        background = float(np.median(target[mask < 0.1])) if np.any(mask < 0.1) else float(target.mean())
        fade = angular_wedge(mask, rng) * mask
        strength = float(rng.uniform(0.25, 0.85))
        image = image * (1.0 - strength * fade) + background * strength * fade
        reliability *= 0.65
    if challenge in {"uneven_illumination", "mixed_hard"}:
        image += low_field(rng, target.shape[0], float(rng.uniform(0.0, 0.13)))
        reliability *= 0.90
    image = cv2.GaussianBlur(image.astype(np.float32), (0, 0), sigmaX=sigma_x, sigmaY=sigma_y, borderType=cv2.BORDER_REFLECT_101)
    motion_length, motion_angle = 0.0, 0.0
    if not flat and (challenge in {"asymmetric_blur_halo", "mixed_hard"} or rng.random() < 0.35):
        motion_length = float(rng.choice((3, 5, 7, 9, 13, 17)))
        motion_angle = float(rng.uniform(0, math.pi))
        image = cv2.filter2D(image, -1, motion_kernel(int(motion_length), motion_angle), borderType=cv2.BORDER_REFLECT_101)
        reliability *= 0.82
    if not flat and rng.random() < 0.20:
        ghost = translate(image, float(rng.uniform(-2, 2)), float(rng.uniform(-2, 2)))
        mix = float(rng.uniform(0.02, 0.12))
        image = (1.0 - mix) * image + mix * ghost
        reliability *= 0.82
    if challenge in {"asymmetric_blur_halo", "mixed_hard"} or rng.random() < 0.28:
        broad = cv2.GaussianBlur(image, (0, 0), float(rng.uniform(3, 7)))
        image = image + float(rng.uniform(0.12, 0.65)) * (broad - image)
        reliability *= 0.78
    image += rng.normal(0, float(rng.uniform(0.0015, 0.035)), image.shape).astype(np.float32)
    image += rng.normal(0, float(rng.uniform(0.0, 0.0045)), (image.shape[0], 1)).astype(np.float32)
    image += rng.normal(0, float(rng.uniform(0.0, 0.0030)), (1, image.shape[1])).astype(np.float32)
    return np.clip(image, 0, 1).astype(np.float32), {
        "sigma_x": sigma_x, "sigma_y": sigma_y, "motion_length": motion_length,
        "motion_angle": motion_angle, "reliability": reliability,
    }


def known_width_gain(sdf: np.ndarray, target_width: float, meta: dict[str, float], maximum: float) -> tuple[np.ndarray, np.ndarray]:
    gx = cv2.Sobel(sdf.astype(np.float32), cv2.CV_32F, 1, 0, ksize=3) / 8.0
    gy = cv2.Sobel(sdf.astype(np.float32), cv2.CV_32F, 0, 1, ksize=3) / 8.0
    norm = np.sqrt(gx * gx + gy * gy + 1.0e-8)
    nx, ny = gx / norm, gy / norm
    variance = (nx * float(meta["sigma_x"])) ** 2 + (ny * float(meta["sigma_y"])) ** 2
    length = float(meta["motion_length"])
    if length > 0:
        mx, my = math.cos(float(meta["motion_angle"])), math.sin(float(meta["motion_angle"]))
        variance += (length * length / 12.0) * (nx * mx + ny * my) ** 2
    gain = np.sqrt(target_width * target_width + variance) / max(target_width, 0.35)
    gain = np.clip(gain, 1.0, maximum).astype(np.float32)
    reliability = np.full_like(gain, float(meta["reliability"]), np.float32)
    return gain, reliability


class R117Dataset(Dataset):
    def __init__(self, split: str, epoch: int = 0, limit: int = 0, challenge_override: str | None = None, role_filter: str | None = None):
        self.package = ROOT / CONFIG["data"]["package_root"]
        manifest = json.loads((self.package / "manifest.json").read_text(encoding="utf-8"))
        def include(row: dict[str, Any]) -> bool:
            if row["split"] != split:
                return False
            if role_filter is None:
                return True
            if role_filter == "degraded":
                return row["role"] in {"edge", "textured_edge"}
            return row["role"] == role_filter
        self.records = sorted((row for row in manifest["records"] if include(row)), key=lambda row: int(row["scene_index"]))
        if limit > 0:
            self.records = self.records[:limit]
        self.epoch, self.challenge_override = int(epoch), challenge_override

    def __len__(self) -> int:
        return len(self.records)

    def rng(self, scene: int, salt: int) -> np.random.Generator:
        seed = (int(CONFIG["seed"]) * 1000003 + scene * 10007 + self.epoch * 7919 + salt * 104729) % (2**63 - 1)
        return np.random.default_rng(seed)

    def load(self, relative: str, scale: float = 1.0) -> np.ndarray:
        return np.asarray(np.load(self.package / relative, mmap_mode="r"), np.float32) / scale

    @staticmethod
    def tensor(value: np.ndarray) -> torch.Tensor:
        return torch.from_numpy(np.asarray(value, np.float32)).unsqueeze(0)

    def __getitem__(self, index: int) -> dict[str, Any]:
        row = self.records[index]
        scene = int(row["scene_index"])
        ta, tb = self.load(row["target_a"], 255.0), self.load(row["target_b"], 255.0)
        ma, mb = self.load(row["mask_a"], 255.0), self.load(row["mask_b"], 255.0)
        sa, sb = self.load(row["sdf_a"]), self.load(row["sdf_b"])
        m2a, m2b = self.load(row["mask2_a"], 255.0), self.load(row["mask2_b"], 255.0)
        s2a, s2b = self.load(row["sdf2_a"]), self.load(row["sdf2_b"])
        flat = row["role"] == "flat_negative"
        challenge = self.challenge_override or ("identity" if row["role"] == "identity" else DEGRADATIONS[(scene + self.epoch) % len(DEGRADATIONS)])
        source_a, meta_a = degrade(ta, ma, self.rng(scene, 101), challenge, flat)
        source_b, meta_b = degrade(tb, mb, self.rng(scene, 211), challenge, flat)
        maximum = float(CONFIG["model"]["maximum_width_gain"])
        gain_a, rel_a = known_width_gain(sa, float(row["target_width_px"]), meta_a, maximum)
        gain_b, rel_b = known_width_gain(sb, float(row["target_width_px"]), meta_b, maximum)
        one = np.ones_like(sa, np.float32)
        edge_a = np.zeros_like(sa) if flat else np.exp(-np.abs(sa) / 2.5).astype(np.float32)
        edge_b = np.zeros_like(sb) if flat else np.exp(-np.abs(sb) / 2.5).astype(np.float32)
        return {
            "source": torch.stack((self.tensor(source_a), self.tensor(source_b), self.tensor(ta))),
            "target": torch.stack((self.tensor(ta), self.tensor(tb), self.tensor(ta))),
            "mask": torch.stack((self.tensor(ma), self.tensor(mb), self.tensor(ma))),
            "sdf": torch.stack((self.tensor(sa), self.tensor(sb), self.tensor(sa))),
            "edge": torch.stack((self.tensor(edge_a), self.tensor(edge_b), self.tensor(edge_a))),
            "mask_2x": torch.stack((self.tensor(m2a), self.tensor(m2b), self.tensor(m2a))),
            "sdf_2x": torch.stack((self.tensor(s2a), self.tensor(s2b), self.tensor(s2a))),
            "known_width_gain": torch.stack((self.tensor(gain_a), self.tensor(gain_b), self.tensor(one))),
            "known_width_reliability": torch.stack((self.tensor(rel_a), self.tensor(rel_b), self.tensor(one))),
            "identity": torch.tensor((challenge == "identity", challenge == "identity", True)),
            "flat": torch.tensor((flat, flat, flat)),
            "midpoint": torch.tensor([float(row["midpoint"])] * 3),
            "polarity": torch.tensor([float(row["polarity"])] * 3),
            "pair_shift_px": torch.tensor((float(row["pair_dx_px"]), float(row["pair_dy_px"]))),
            "scene_index": torch.tensor(scene), "role": row["role"], "family": row["family"], "challenge": challenge,
        }

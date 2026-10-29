"""Deterministic R115 data with explicit R109/R114 ablation arms."""
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
DATA = CONFIG["data"]
DCFG = DATA["degradation"]
CHALLENGES = tuple(DATA["degradation_families"])


def motion_kernel(length: int, angle: float) -> np.ndarray:
    size = max(3, int(length) | 1)
    kernel = np.zeros((size, size), np.float32)
    center = (size - 1) * 0.5
    dx, dy = math.cos(angle) * center, math.sin(angle) * center
    cv2.line(
        kernel,
        (round(center - dx), round(center - dy)),
        (round(center + dx), round(center + dy)),
        1,
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


def degrade(
    target: np.ndarray,
    mask: np.ndarray,
    rng: np.random.Generator,
    challenge: str,
    flat: bool = False,
) -> tuple[np.ndarray, dict[str, float]]:
    if challenge == "identity":
        return target.copy(), {"sigma": 0.0}
    low, high = DCFG["blur_sigma_px"]
    sigma_x = float(np.exp(rng.uniform(np.log(low), np.log(high))))
    sigma_y = float(np.clip(sigma_x * rng.uniform(*DCFG["anisotropy"]), low, high))
    image = target.copy()
    midpoint = float(np.median(target))
    if challenge in {"low_contrast", "boundary_fade", "mixed_hard", "five_x_dense"}:
        image = midpoint + float(rng.uniform(*DCFG["contrast_scale"])) * (image - midpoint)
    if challenge in {"boundary_fade", "mixed_hard"}:
        background = float(np.median(target[mask < 0.1])) if np.any(mask < 0.1) else float(target.mean())
        strength = float(rng.uniform(*DCFG["boundary_fade_strength"]))
        fade = angular_wedge(mask, rng) * mask
        image = image * (1 - strength * fade) + background * (strength * fade)
    if challenge in {"uneven_illumination", "mixed_hard", "five_x_dense"}:
        image += low_field(rng, target.shape[0], float(rng.uniform(*DCFG["illumination_amplitude"])))
    if challenge == "nonuniform_psf":
        delta = float(rng.uniform(*DCFG["nonuniform_psf_sigma_delta"]))
        first = cv2.GaussianBlur(image.astype(np.float32), (0, 0), sigmaX=sigma_x, sigmaY=sigma_y)
        second = cv2.GaussianBlur(
            image.astype(np.float32), (0, 0),
            sigmaX=min(high, sigma_x + delta), sigmaY=min(high, sigma_y + delta),
        )
        blend = 0.5 + 0.5 * np.tanh(low_field(rng, target.shape[0], 1.4))
        image = first * blend + second * (1 - blend)
    else:
        image = cv2.GaussianBlur(
            image.astype(np.float32), (0, 0), sigmaX=sigma_x, sigmaY=sigma_y,
            borderType=cv2.BORDER_REFLECT_101,
        )
    if not flat and (
        challenge in {"asymmetric_blur_halo", "mixed_hard"}
        or rng.random() < float(DCFG["motion_blur_probability"])
    ):
        image = cv2.filter2D(
            image,
            -1,
            motion_kernel(int(rng.choice(DCFG["motion_blur_lengths"])), float(rng.uniform(0, math.pi))),
            borderType=cv2.BORDER_REFLECT_101,
        )
    if not flat and rng.random() < float(DCFG["ghost_probability"]):
        dx, dy = float(rng.uniform(-2, 2)), float(rng.uniform(-2, 2))
        ghost = cv2.warpAffine(
            image,
            np.asarray([[1, 0, dx], [0, 1, dy]], np.float32),
            (image.shape[1], image.shape[0]),
            flags=cv2.INTER_LINEAR,
            borderMode=cv2.BORDER_REFLECT_101,
        )
        mix = float(rng.uniform(*DCFG["ghost_mix"]))
        image = (1 - mix) * image + mix * ghost
    if challenge in {"asymmetric_blur_halo", "mixed_hard"} or rng.random() < float(DCFG["halo_probability"]):
        broad = cv2.GaussianBlur(image, (0, 0), float(rng.uniform(3, 7)))
        image = image + float(rng.uniform(*DCFG["halo_strength"])) * (broad - image)
    white = float(rng.uniform(*DCFG["white_noise_sigma"]))
    image += rng.normal(0, white, image.shape).astype(np.float32)
    if challenge in {"colored_noise", "mixed_hard"}:
        colored = cv2.GaussianBlur(rng.normal(0, 1, image.shape).astype(np.float32), (0, 0), 1.2)
        image += colored * float(rng.uniform(*DCFG["colored_noise_sigma"]))
    if challenge == "band_limited_noise":
        band = cv2.GaussianBlur(rng.normal(0, 1, image.shape).astype(np.float32), (0, 0), 2.4)
        band -= cv2.GaussianBlur(band, (0, 0), 5.0)
        image += band * float(rng.uniform(*DCFG["band_limited_noise_sigma"]))
    image += rng.normal(0, float(rng.uniform(*DCFG["row_noise_sigma"])), (image.shape[0], 1)).astype(np.float32)
    image += rng.normal(0, float(rng.uniform(*DCFG["column_noise_sigma"])), (1, image.shape[1])).astype(np.float32)
    if challenge in {"fixed_pattern", "five_x_dense"}:
        amplitude = float(rng.uniform(*DCFG["fixed_pattern_amplitude"]))
        phase = float(rng.uniform(0, 2 * math.pi))
        stripe = np.sin(np.linspace(phase, phase + 10 * math.pi, image.shape[1], dtype=np.float32))[None]
        image += amplitude * stripe
    return np.clip(image, 0, 1).astype(np.float32), {"sigma": math.sqrt(sigma_x * sigma_y)}


def normalize_original_record(row: dict) -> dict:
    return {
        **row,
        "record_id": f"r109_{row['split']}_{int(row['scene_index']):06d}",
        "_package_root": str(Path(PROJECT_ROOT / DATA["r109_package_root"])),
    }


class R115Dataset(Dataset):
    def __init__(self, split: str, epoch: int = 0, arm: str = "B", limit: int = 0):
        self.arm = arm.upper()
        if self.arm in {"A", "A_FULL", "ORIGINAL"}:
            self.package = Path(PROJECT_ROOT / DATA["r109_package_root"])
            manifest = json.loads(Path(PROJECT_ROOT / DATA["r109_manifest"]).read_text(encoding="utf-8"))
            records = [normalize_original_record(row) for row in manifest["records"]]
            subset_path = ROOT / "data" / "ablation_a_r109_original.json"
        elif self.arm in {"B", "FORMAL"}:
            self.package = ROOT / DATA["package_root"]
            manifest = json.loads((self.package / "manifest.json").read_text(encoding="utf-8"))
            records = [{**row, "_package_root": str(self.package)} for row in manifest["records"]]
            subset_path = ROOT / "data" / "ablation_b_r114_balanced.json"
        elif self.arm == "MIXED":
            original_manifest = json.loads(Path(PROJECT_ROOT / DATA["r109_manifest"]).read_text(encoding="utf-8"))
            records = [normalize_original_record(row) for row in original_manifest["records"]]
            local_package = ROOT / DATA["package_root"]
            local_manifest = json.loads((local_package / "manifest.json").read_text(encoding="utf-8"))
            supplemental = set(DATA["supplemental_families"])
            source_additions = [
                row for row in local_manifest["records"]
                if row["split"] == "train" and row["family"] in supplemental
            ]
            records.extend([
                {**row, "scene_index": 5000 + index, "_package_root": str(local_package)}
                for index, row in enumerate(source_additions)
            ])
            self.package = local_package
            subset_path = ROOT / "data" / "ablation_b_r114_balanced.json"
        elif self.arm == "C":
            original_manifest = json.loads(Path(PROJECT_ROOT / DATA["r109_manifest"]).read_text(encoding="utf-8"))
            selected = set(json.loads((ROOT / "data" / "ablation_a_r109_original.json").read_text(encoding="utf-8"))["record_ids"])
            records = [
                row for row in (normalize_original_record(item) for item in original_manifest["records"])
                if row["split"] != "train" or row["record_id"] in selected
            ]
            local_package = ROOT / DATA["package_root"]
            local_manifest = json.loads((local_package / "manifest.json").read_text(encoding="utf-8"))
            supplemental = set(DATA["supplemental_families"])
            additions = [
                row for row in local_manifest["records"]
                if row["split"] == "train" and row["family"] in supplemental
            ]
            records.extend([
                {**row, "scene_index": 5000 + index, "_package_root": str(local_package)}
                for index, row in enumerate(additions)
            ])
            self.package = local_package
            subset_path = ROOT / "data" / "ablation_a_r109_original.json"
        elif self.arm == "D":
            original_manifest = json.loads(Path(PROJECT_ROOT / DATA["r109_manifest"]).read_text(encoding="utf-8"))
            selected = set(json.loads((ROOT / "data" / "ablation_a_r109_original.json").read_text(encoding="utf-8"))["record_ids"])
            records = [
                row for row in (normalize_original_record(item) for item in original_manifest["records"])
                if row["split"] != "train" or row["record_id"] in selected
            ]
            local_package = ROOT / DATA["package_root"]
            local_manifest = json.loads((local_package / "manifest.json").read_text(encoding="utf-8"))
            additions = []
            for family in DATA["supplemental_families"]:
                family_rows = [
                    row for row in local_manifest["records"]
                    if row["split"] == "train" and row["family"] == family
                ]
                additions.extend(sorted(family_rows, key=lambda row: row["record_id"])[:20])
            records.extend([
                {**row, "scene_index": 5000 + index, "_package_root": str(local_package)}
                for index, row in enumerate(additions)
            ])
            self.package = local_package
            subset_path = ROOT / "data" / "ablation_a_r109_original.json"
        else:
            raise ValueError("arm must be A, A_FULL, B, C, D, FORMAL, or MIXED")
        records = [row for row in records if row["split"] == split]
        if split == "train" and self.arm in {"A", "B"} and subset_path.is_file():
            selected = set(json.loads(subset_path.read_text(encoding="utf-8"))["record_ids"])
            records = [row for row in records if row["record_id"] in selected]
        self.records = sorted(records, key=lambda row: int(row["scene_index"]))
        if limit > 0:
            self.records = self.records[:limit]
        self.epoch = int(epoch)

    def set_epoch(self, epoch: int) -> None:
        self.epoch = int(epoch)

    def __len__(self) -> int:
        return len(self.records)

    def rng(self, scene: int, salt: int = 0) -> np.random.Generator:
        seed = (
            int(CONFIG["seed"]) * 1000003
            + int(scene) * 10007
            + self.epoch * 7919
            + salt * 104729
        ) % (2**63 - 1)
        return np.random.default_rng(seed)

    @staticmethod
    def tensor(value: np.ndarray) -> torch.Tensor:
        return torch.from_numpy(np.asarray(value, np.float32)).unsqueeze(0)

    def __getitem__(self, index: int) -> dict[str, Any]:
        record = self.records[index]
        scene = int(record["scene_index"])
        package_root = Path(record.get("_package_root", self.package))
        target = np.asarray(np.load(package_root / record["target"], mmap_mode="r"), np.float32) / 255.0
        mask = np.asarray(np.load(package_root / record["mask"], mmap_mode="r"), np.float32) / 255.0
        sdf = np.asarray(np.load(package_root / record["sdf"], mmap_mode="r"), np.float32)
        challenge = "identity" if record["role"] == "identity" else CHALLENGES[(scene + self.epoch) % len(CHALLENGES)]
        source, meta = degrade(
            target, mask, self.rng(scene, 101), challenge,
            flat=record["role"] == "flat_negative",
        )
        target_width = float(record["target_width_px"])
        source_width = math.sqrt(target_width**2 + meta["sigma"]**2)
        width_gain = float(
            np.clip(
                source_width / max(target_width, 1.0e-6),
                CONFIG["model"]["minimum_width_gain"],
                CONFIG["model"]["maximum_width_gain"],
            )
        )
        edge = (
            np.exp(-np.abs(sdf) / 2.5).astype(np.float32)
            if record["role"] != "flat_negative"
            else np.zeros_like(target)
        )
        clear = target.copy()
        return {
            "source": torch.stack([self.tensor(source), self.tensor(clear)]),
            "target": torch.stack([self.tensor(target), self.tensor(target)]),
            "mask": torch.stack([self.tensor(mask), self.tensor(mask)]),
            "sdf": torch.stack([self.tensor(sdf), self.tensor(sdf)]),
            "edge": torch.stack([self.tensor(edge), self.tensor(edge)]),
            "identity": torch.tensor([challenge == "identity", True]),
            "midpoint": torch.tensor([float(record["midpoint"])] * 2, dtype=torch.float32),
            "polarity": torch.tensor([float(record["polarity"])] * 2, dtype=torch.float32),
            "width_gain_target": torch.tensor([width_gain, 1.0], dtype=torch.float32),
            "scene_index": torch.tensor(scene),
            "record_id": record["record_id"],
            "role": str(record["role"]),
            "family": str(record["family"]),
            "challenge": challenge,
        }

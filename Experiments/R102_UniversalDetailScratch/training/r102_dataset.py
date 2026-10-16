"""Read-only R92 procedural scenes plus deterministic R102 corrective views."""
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


def warp_array(array: np.ndarray, dx: float, dy: float, interpolation: int) -> np.ndarray:
    if abs(dx) + abs(dy) < 1e-10:
        return np.asarray(array).copy()
    matrix = np.asarray([[1.0, 0.0, dx], [0.0, 1.0, dy]], dtype=np.float32)
    return cv2.warpAffine(
        np.asarray(array), matrix, (array.shape[1], array.shape[0]),
        flags=interpolation, borderMode=cv2.BORDER_REFLECT_101,
    )


def _analytic_texture(
    height: int,
    width: int,
    global_y: int,
    global_x: int,
    rng: np.random.Generator,
) -> np.ndarray:
    """Continuous pixel-centre texture with no rasterized shape edges."""
    yy, xx = np.mgrid[0:height, 0:width].astype(np.float32)
    yy += float(global_y) + 0.5
    xx += float(global_x) + 0.5
    texture = np.zeros((height, width), dtype=np.float32)
    component_count = int(rng.integers(2, 5))
    lo, hi = CONFIG["data"]["augmentation"]["analytic_texture_period_px"]
    for _ in range(component_count):
        angle = float(rng.uniform(0.0, math.pi))
        period = float(np.exp(rng.uniform(np.log(lo), np.log(hi))))
        phase = float(rng.uniform(-math.pi, math.pi))
        coordinate = xx * math.cos(angle) + yy * math.sin(angle)
        texture += float(rng.uniform(0.45, 1.0)) * np.sin(2.0 * math.pi * coordinate / period + phase)

    # Analytic ridges create scratches/fibres without drawing at native
    # resolution. Their Gaussian distance profile is already antialiased.
    if rng.random() < 0.65:
        for _ in range(int(rng.integers(1, 4))):
            angle = float(rng.uniform(0.0, math.pi))
            cx = float(global_x + rng.uniform(0, width))
            cy = float(global_y + rng.uniform(0, height))
            distance = np.abs((xx - cx) * math.sin(angle) - (yy - cy) * math.cos(angle))
            sigma = float(rng.uniform(0.38, 1.25))
            texture += float(rng.uniform(-1.1, 1.1)) * np.exp(-0.5 * (distance / sigma) ** 2)

    texture -= float(texture.mean())
    scale = float(np.percentile(np.abs(texture), 99.0))
    if scale > 1e-6:
        texture /= scale
    return np.clip(texture, -1.0, 1.0).astype(np.float32)


def _flat_field(height: int, width: int, rng: np.random.Generator) -> np.ndarray:
    yy, xx = np.mgrid[0:height, 0:width].astype(np.float32)
    xx = (xx + 0.5) / max(width, 1) - 0.5
    yy = (yy + 0.5) / max(height, 1) - 0.5
    base = float(rng.uniform(0.18, 0.84))
    field = base + float(rng.uniform(-0.10, 0.10)) * xx + float(rng.uniform(-0.10, 0.10)) * yy
    field += float(rng.uniform(-0.035, 0.035)) * (xx * xx + yy * yy - 1.0 / 6.0)
    return np.clip(field, 0.05, 0.95).astype(np.float32)


class R102Dataset(Dataset):
    """One scene per item, always returning two independent observations."""

    mode_names = {0: "base", 1: "innovation", 2: "identity", 3: "flat_negative"}

    def __init__(
        self,
        split: str,
        patch_size: int,
        epoch: int,
        *,
        validation_limit: int = 0,
    ):
        self.package = Path(CONFIG["data"]["base_package"])
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
            + int(scene_index) * 10007
            + int(self.epoch) * 7919
            + int(salt) * 104729
            + self.patch_size * 31
        ) % (2**63 - 1)
        return np.random.default_rng(seed)

    def _mode(self, index: int, rng: np.random.Generator) -> int:
        if self.split != "train":
            cycle = index % 12
            if cycle in (0, 1):
                return 2
            if cycle == 2:
                return 3
            if cycle in (3, 4, 5, 6, 7):
                return 1
            return 0
        value = float(rng.random())
        aug = CONFIG["data"]["augmentation"]
        if value < float(aug["flat_negative_probability"]):
            return 3
        if value < float(aug["flat_negative_probability"]) + float(aug["identity_probability"]):
            return 2
        if value < (
            float(aug["flat_negative_probability"])
            + float(aug["identity_probability"])
            + float(aug["innovation_probability"])
        ):
            return 1
        return 0

    def _origin(self, mask: np.ndarray, scene_index: int, rng: np.random.Generator, prefer_edge: bool) -> tuple[int, int]:
        maximum = self.canvas_size - self.patch_size
        if maximum <= 0:
            return 0, 0
        best: tuple[float, int, int] | None = None
        tries = 14 if prefer_edge else 5
        for _ in range(tries):
            y = int(rng.integers(0, maximum // 8 + 1)) * 8
            x = int(rng.integers(0, maximum // 8 + 1)) * 8
            crop = np.asarray(mask[y:y + self.patch_size, x:x + self.patch_size]) >= 128
            fraction = float(crop.mean())
            boundary = int(np.count_nonzero(crop[1:] != crop[:-1]) + np.count_nonzero(crop[:, 1:] != crop[:, :-1]))
            if prefer_edge:
                score = float(boundary) - 5000.0 * max(0.02 - fraction, 0.0) - 5000.0 * max(fraction - 0.90, 0.0)
            else:
                score = -abs(fraction - 0.35) + 0.00001 * boundary
            candidate = (score, y, x)
            if best is None or candidate[0] > best[0]:
                best = candidate
        assert best is not None
        return int(best[1]), int(best[2])

    @staticmethod
    def _to_tensor(rows: list[np.ndarray]) -> torch.Tensor:
        array = np.stack(rows).astype(np.float32, copy=False)
        return torch.from_numpy(array).unsqueeze(1)

    def __getitem__(self, index: int) -> dict[str, Any]:
        record = self.records[index]
        scene_index = int(record["scene_index"])
        rng = self._rng(scene_index)
        mode = self._mode(index, rng)
        target_base = np.load(self.package / record["target"], mmap_mode="r", allow_pickle=False)
        mask_base = np.load(self.package / record["mask"], mmap_mode="r", allow_pickle=False)
        prefer_edge = mode != 3 and record["role"] not in {"identity_and_detail_guard"}
        y0, x0 = self._origin(mask_base, scene_index, rng, prefer_edge)

        first = (self.epoch + scene_index) % 4
        second = (first + 1 + scene_index % 2) % 4
        if record["role"] == "signed_subpixel_motion":
            first, second = 0, 1 + ((self.epoch + scene_index) % 2)
        observation_indices = (first, second)

        target_crop = np.asarray(
            target_base[y0:y0 + self.patch_size, x0:x0 + self.patch_size], dtype=np.float32
        ) / 255.0
        mask_crop = np.asarray(
            mask_base[y0:y0 + self.patch_size, x0:x0 + self.patch_size], dtype=np.float32
        ) / 255.0

        innovation = np.zeros_like(target_crop, dtype=np.float32)
        target_reference = target_crop.copy()
        innovation_amplitude = 0.0
        if mode == 1:
            innovation = _analytic_texture(self.patch_size, self.patch_size, y0, x0, rng)
            lo, hi = CONFIG["data"]["augmentation"]["target_texture_amplitude"]
            innovation_amplitude = float(rng.uniform(lo, hi))
            selector = int(rng.integers(0, 3))
            if selector == 0:
                modulation = 0.20 + 0.80 * mask_crop
            elif selector == 1:
                modulation = 1.0 - 0.80 * mask_crop
            else:
                modulation = np.ones_like(mask_crop)
            target_reference = np.clip(target_crop + innovation_amplitude * innovation * modulation, 0.0, 1.0)
        elif mode == 3:
            target_reference = _flat_field(self.patch_size, self.patch_size, rng)
            mask_crop = np.zeros_like(target_reference)

        sources: list[np.ndarray] = []
        targets: list[np.ndarray] = []
        masks: list[np.ndarray] = []
        motions: list[tuple[float, float]] = []
        identities: list[bool] = []
        for view, observation_index in enumerate(observation_indices):
            observation = record["observations"][observation_index]
            dx = float(observation.get("motion_dx_px", 0.0))
            dy = float(observation.get("motion_dy_px", 0.0))
            view_rng = self._rng(scene_index, salt=100 + view)
            target_view = warp_array(target_reference, dx, dy, cv2.INTER_LANCZOS4)
            mask_view = warp_array(mask_crop, dx, dy, cv2.INTER_LINEAR)

            if mode == 2:
                source_view = target_view.copy()
                identity = True
            elif mode == 3:
                noise = view_rng.normal(0.0, float(view_rng.uniform(0.002, 0.018)), target_view.shape).astype(np.float32)
                row = view_rng.normal(0.0, 0.003, (target_view.shape[0], 1)).astype(np.float32)
                source_view = np.clip(cv2.GaussianBlur(target_view, (0, 0), float(view_rng.uniform(0.2, 1.1))) + noise + row, 0.0, 1.0)
                identity = False
            else:
                source_array = np.load(self.package / observation["source"], mmap_mode="r", allow_pickle=False)
                source_view = np.asarray(
                    source_array[y0:y0 + self.patch_size, x0:x0 + self.patch_size], dtype=np.float32
                ) / 255.0
                if mode == 1:
                    modulation = np.divide(
                        target_reference - target_crop,
                        innovation_amplitude * innovation + 1e-6,
                        out=np.ones_like(target_crop),
                        where=np.abs(innovation) > 1e-4,
                    )
                    modulation = np.clip(modulation, 0.15, 1.0)
                    hint = warp_array(innovation * modulation, dx, dy, cv2.INTER_LANCZOS4)
                    hint = cv2.GaussianBlur(hint, (0, 0), float(view_rng.uniform(0.45, 1.45)))
                    transfer_lo, transfer_hi = CONFIG["data"]["augmentation"]["source_texture_transfer"]
                    transfer = float(view_rng.uniform(transfer_lo, transfer_hi))
                    source_view = np.clip(source_view + innovation_amplitude * transfer * hint, 0.0, 1.0)
                identity = observation["degradation_family"] == "identity_and_near_identity"

            sources.append(source_view.astype(np.float32, copy=False))
            targets.append(target_view.astype(np.float32, copy=False))
            masks.append(mask_view.astype(np.float32, copy=False))
            motions.append((dx, dy))
            identities.append(bool(identity))

        texture_meta = record["texture"]
        foreground_mean = float(texture_meta["foreground_mean"])
        background_mean = float(texture_meta["background_mean"])
        midpoint = 0.5 * (foreground_mean + background_mean)
        polarity = 1.0 if bool(texture_meta["bright_foreground"]) else -1.0
        if mode == 3:
            midpoint, polarity = 0.5, -1.0
        return {
            "source": self._to_tensor(sources),
            "target": self._to_tensor(targets),
            "mask": self._to_tensor(masks),
            "motion": torch.tensor(motions, dtype=torch.float32),
            "identity": torch.tensor(identities, dtype=torch.bool),
            "mode": torch.tensor(mode, dtype=torch.int64),
            "midpoint": torch.tensor(midpoint, dtype=torch.float32),
            "polarity": torch.tensor(polarity, dtype=torch.float32),
            "innovation_amplitude": torch.tensor(innovation_amplitude, dtype=torch.float32),
            "role": str(record["role"]),
            "scene_id": str(record["scene_id"]),
            "scene_index": torch.tensor(scene_index, dtype=torch.int64),
            "origin": torch.tensor((y0, x0), dtype=torch.int64),
        }

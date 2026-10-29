"""R104 procedural dataset with exposure bundles and correctable local illumination."""
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


def sdf_window(
    quarter: np.ndarray, y0: int, x0: int, height: int, width: int, canvas_size: int,
) -> np.ndarray:
    """Read an exact full-resolution SDF window without resizing the full canvas."""
    scale_y = float(quarter.shape[0]) / float(canvas_size)
    scale_x = float(quarter.shape[1]) / float(canvas_size)
    map_x = ((x0 + np.arange(width, dtype=np.float32) + 0.5) * scale_x - 0.5)[None, :]
    map_y = ((y0 + np.arange(height, dtype=np.float32) + 0.5) * scale_y - 0.5)[:, None]
    map_x = np.broadcast_to(map_x, (height, width)).copy()
    map_y = np.broadcast_to(map_y, (height, width)).copy()
    return cv2.remap(
        np.asarray(quarter, dtype=np.float32) * 4.0, map_x, map_y,
        interpolation=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE,
    ).astype(np.float32)


def supersampled_texture(
    height: int, width: int, global_y: int, global_x: int, rng: np.random.Generator,
) -> np.ndarray:
    cfg = CONFIG["data"]["texture"]
    factor = int(CONFIG["data"]["added_texture_supersample_factor"])
    yy, xx = np.mgrid[0:height * factor, 0:width * factor].astype(np.float32)
    yy = float(global_y) + (yy + 0.5) / factor
    xx = float(global_x) + (xx + 0.5) / factor
    texture = np.zeros_like(xx, dtype=np.float32)
    lo, hi = map(float, cfg["period_px"])
    for _ in range(int(rng.integers(2, 5))):
        angle = float(rng.uniform(0.0, math.pi))
        period = float(np.exp(rng.uniform(np.log(lo), np.log(hi))))
        phase = float(rng.uniform(-math.pi, math.pi))
        coordinate = xx * math.cos(angle) + yy * math.sin(angle)
        texture += float(rng.uniform(0.35, 1.0)) * np.sin(2.0 * math.pi * coordinate / period + phase)
    for _ in range(int(rng.integers(1, 4))):
        angle = float(rng.uniform(0.0, math.pi))
        cx = float(global_x + rng.uniform(0, width))
        cy = float(global_y + rng.uniform(0, height))
        distance = np.abs((xx - cx) * math.sin(angle) - (yy - cy) * math.cos(angle))
        sigma = float(rng.uniform(0.32, 1.25))
        texture += float(rng.uniform(-1.0, 1.0)) * np.exp(-0.5 * (distance / sigma) ** 2)
    texture -= float(texture.mean())
    scale = float(np.percentile(np.abs(texture), 99.0))
    if scale > 1e-6:
        texture /= scale
    down = cv2.resize(texture, (width, height), interpolation=cv2.INTER_AREA)
    return np.clip(down, -1.0, 1.0).astype(np.float32)


def flat_field(height: int, width: int, rng: np.random.Generator) -> np.ndarray:
    yy, xx = np.mgrid[0:height, 0:width].astype(np.float32)
    xx = (xx + 0.5) / width - 0.5
    yy = (yy + 0.5) / height - 0.5
    base = float(rng.uniform(0.12, 0.88))
    result = base + float(rng.uniform(-0.07, 0.07)) * xx + float(rng.uniform(-0.07, 0.07)) * yy
    return np.clip(result, 0.03, 0.97).astype(np.float32)


def global_photometry(image: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    cfg = CONFIG["data"]["photometry"]
    gamma = float(rng.uniform(*cfg["shared_gamma"]))
    gain = float(rng.uniform(*cfg["shared_global_gain"]))
    offset = float(rng.uniform(*cfg["shared_global_offset"]))
    contrast = float(rng.uniform(*cfg["shared_contrast"]))
    result = np.power(np.clip(image, 0.0, 1.0), gamma).astype(np.float32)
    centre = float(np.median(result))
    result = centre + contrast * (result - centre)
    result = gain * result + offset
    return np.clip(result, 0.0, 1.0).astype(np.float32)


def spatial_illumination(
    shape: tuple[int, int], rng: np.random.Generator, global_y: int = 0, global_x: int = 0,
) -> np.ndarray:
    cfg = CONFIG["data"]["photometry"]
    amplitude = float(rng.uniform(*cfg["correctable_spatial_illumination_amplitude"]))
    if amplitude <= 1e-8:
        return np.ones(shape, dtype=np.float32)
    height, width = shape
    yy, xx = np.mgrid[0:height, 0:width].astype(np.float32)
    xx += float(global_x) + 0.5
    yy += float(global_y) + 0.5
    scale_lo, scale_hi = map(float, cfg["correctable_spatial_scale_px"])
    field = np.zeros(shape, dtype=np.float32)
    for weight in (0.70, 0.38):
        angle = float(rng.uniform(0.0, 2.0 * math.pi))
        scale = float(np.exp(rng.uniform(np.log(scale_lo), np.log(scale_hi))))
        phase = float(rng.uniform(-math.pi, math.pi))
        coordinate = math.cos(angle) * xx + math.sin(angle) * yy
        field += weight * np.sin(2.0 * math.pi * coordinate / scale + phase)
    canvas_centre = 0.5 * float(CONFIG["data"]["canvas_size"])
    ramp_angle = float(rng.uniform(0.0, 2.0 * math.pi))
    field += 0.28 * (
        math.cos(ramp_angle) * (xx - canvas_centre)
        + math.sin(ramp_angle) * (yy - canvas_centre)
    ) / max(scale_hi, 1.0)
    field -= float(field.mean())
    scale = float(np.percentile(np.abs(field), 99.0))
    if scale > 1e-6:
        field /= scale
    return np.clip(1.0 + amplitude * field, 0.55, 1.45).astype(np.float32)


def motion_kernel(length: int, angle: float) -> np.ndarray:
    size = max(3, int(length) | 1)
    kernel = np.zeros((size, size), dtype=np.float32)
    centre = (size - 1) * 0.5
    dx, dy = math.cos(angle) * centre, math.sin(angle) * centre
    cv2.line(
        kernel,
        (int(round(centre - dx)), int(round(centre - dy))),
        (int(round(centre + dx)), int(round(centre + dy))),
        1.0, 1, cv2.LINE_AA,
    )
    return kernel / max(float(kernel.sum()), 1e-6)


def degrade(image: np.ndarray, rng: np.random.Generator, severity: float, identity: bool) -> np.ndarray:
    if identity:
        return np.asarray(image, dtype=np.float32).copy()
    cfg = CONFIG["data"]["degradation"]
    sigma_min, sigma_max = map(float, cfg["blur_sigma_px"])
    sigma_x = float(np.exp(rng.uniform(np.log(sigma_min), np.log(sigma_min + severity * (sigma_max - sigma_min)))))
    anisotropy = float(rng.uniform(*cfg["anisotropy_ratio"]))
    sigma_y = float(np.clip(sigma_x * anisotropy, sigma_min, sigma_max))
    angle = float(rng.uniform(0.0, 180.0))
    observed = cv2.GaussianBlur(image, (0, 0), sigmaX=sigma_x, sigmaY=sigma_y, borderType=cv2.BORDER_REFLECT_101)
    if rng.random() < 0.22 * severity:
        length = int(rng.choice([3, 5, 7]))
        observed = cv2.filter2D(
            observed, -1, motion_kernel(length, math.radians(angle)), borderType=cv2.BORDER_REFLECT_101
        )
    if rng.random() < 0.18 * severity:
        ghost = warp_array(
            observed, float(rng.uniform(-1.5, 1.5)), float(rng.uniform(-1.5, 1.5)), cv2.INTER_LINEAR
        )
        mix = float(rng.uniform(0.02, cfg["ghost_mix"][1]))
        observed = (1.0 - mix) * observed + mix * ghost
    noise = float(rng.uniform(cfg["noise_sigma"][0], cfg["noise_sigma"][0] + severity * (cfg["noise_sigma"][1] - cfg["noise_sigma"][0])))
    observed += rng.normal(0.0, noise, image.shape).astype(np.float32)
    row_sigma = severity * float(cfg["row_column_noise_sigma"][1])
    observed += rng.normal(0.0, row_sigma, (image.shape[0], 1)).astype(np.float32)
    observed += rng.normal(0.0, row_sigma * 0.55, (1, image.shape[1])).astype(np.float32)
    return np.clip(observed, 0.0, 1.0).astype(np.float32)


class R104Dataset(Dataset):
    mode_names = {
        0: "recoverable_blur_noise", 1: "recoverable_microtexture",
        2: "exposure_coherent_bundle", 3: "zero_mean_spatial_illumination",
        4: "identity_or_near_identity", 5: "flat_negative",
    }
    pair_names = {
        0: "degraded_and_same_photometry_clear", 1: "same_geometry_different_photometry",
        2: "known_subpixel_motion", 3: "cross_tile_context",
    }

    def __init__(self, split: str, patch_size: int, epoch: int, *, validation_limit: int = 0):
        self.package = Path(PROJECT_ROOT / CONFIG["data"]["base_package"])
        self.manifest = json.loads((self.package / "manifest.json").read_text(encoding="utf-8"))
        self.records = sorted(
            (row for row in self.manifest["records"] if row["split"] == split),
            key=lambda row: int(row["scene_index"]),
        )
        if validation_limit:
            self.records = self.records[: int(validation_limit)]
        self.split, self.patch_size, self.epoch = str(split), int(patch_size), int(epoch)
        self.canvas_size = int(self.manifest["canvas_size"])
        if self.patch_size % 8 or self.patch_size > self.canvas_size:
            raise ValueError("patch_size must be divisible by 8 and fit the canvas")

    def __len__(self) -> int:
        if self.split == "train":
            return int(CONFIG["data"]["observations_per_epoch"]) // 2
        return len(self.records)

    def _rng(self, scene_index: int, salt: int = 0) -> np.random.Generator:
        seed = (1040047 * 1000003 + scene_index * 10007 + self.epoch * 7919 + salt * 104729 + self.patch_size * 31)
        return np.random.default_rng(seed % (2**63 - 1))

    @staticmethod
    def _choice(probabilities: dict[str, float], rng: np.random.Generator) -> int:
        names, values = list(probabilities), np.asarray(list(probabilities.values()), dtype=np.float64)
        values /= values.sum()
        return int(rng.choice(len(names), p=values))

    def _active_probabilities(self) -> tuple[dict[str, float], dict[str, float]]:
        if self.split == "train":
            for stage in CONFIG["training"].get("curriculum", []):
                if int(stage["start"]) <= self.epoch <= int(stage["end"]):
                    return stage["online_mode_probabilities"], stage["pair_type_probabilities"]
        return CONFIG["data"]["online_mode_probabilities"], CONFIG["data"]["pair_type_probabilities"]

    def _origin(self, mask: np.ndarray, rng: np.random.Generator, prefer_edge: bool) -> tuple[int, int]:
        maximum = self.canvas_size - self.patch_size
        if maximum <= 0:
            return 0, 0
        best = None
        for _ in range(14 if prefer_edge else 6):
            y = int(rng.integers(0, maximum // 8 + 1)) * 8
            x = int(rng.integers(0, maximum // 8 + 1)) * 8
            crop = mask[y:y + self.patch_size, x:x + self.patch_size] >= 128
            fraction = float(crop.mean())
            boundary = int(np.count_nonzero(crop[1:] != crop[:-1]) + np.count_nonzero(crop[:, 1:] != crop[:, :-1]))
            score = boundary - 4000.0 * max(0.015 - fraction, 0.0) - 4000.0 * max(fraction - 0.92, 0.0)
            if not prefer_edge:
                score = -abs(fraction - 0.35) + boundary * 1e-5
            if best is None or score > best[0]:
                best = (score, y, x)
        assert best is not None
        return int(best[1]), int(best[2])

    @staticmethod
    def _tensor(rows: list[np.ndarray]) -> torch.Tensor:
        return torch.from_numpy(np.stack(rows).astype(np.float32, copy=False)).unsqueeze(1)

    def __getitem__(self, index: int) -> dict[str, Any]:
        if self.split == "train":
            # A virtual epoch contains 2,500 distinct scene-pairs.  The coprime
            # stride spreads repeated scenes evenly, while the sample salt
            # prevents a repeated scene from receiving duplicate augmentation.
            record_index = (int(index) * 977 + self.epoch * 37) % len(self.records)
            sample_salt = int(index) + 1
        else:
            record_index = int(index)
            sample_salt = 0
        record = self.records[record_index]
        scene_index = int(record["scene_index"])
        salt_base = sample_salt * 1000
        rng = self._rng(scene_index, salt_base)
        if self.split == "train":
            mode_probabilities, pair_probabilities = self._active_probabilities()
            mode = self._choice(mode_probabilities, rng)
            pair_type = self._choice(pair_probabilities, rng)
        else:
            # The first 24 validation scenes cover the full 6 x 4 cross-product.
            mode, pair_type = index % 6, (index // 6) % 4
        target_base = np.load(self.package / record["target"], mmap_mode="r", allow_pickle=False)
        mask_base = np.load(self.package / record["mask"], mmap_mode="r", allow_pickle=False)
        y0, x0 = self._origin(np.asarray(mask_base), rng, prefer_edge=(mode != 5))
        target = np.asarray(target_base[y0:y0 + self.patch_size, x0:x0 + self.patch_size], dtype=np.float32) / 255.0
        mask = np.asarray(mask_base[y0:y0 + self.patch_size, x0:x0 + self.patch_size], dtype=np.float32) / 255.0
        sdf_small = np.load(self.package / record["sdf_q4"], mmap_mode="r", allow_pickle=False)
        sdf = sdf_window(
            sdf_small, y0, x0, self.patch_size, self.patch_size, self.canvas_size
        )

        if mode == 1:
            texture = supersampled_texture(self.patch_size, self.patch_size, y0, x0, rng)
            amplitude = float(rng.uniform(*CONFIG["data"]["texture"]["amplitude"]))
            modulation = 0.25 + 0.75 * (mask if rng.random() < 0.5 else 1.0 - mask)
            target = np.clip(target + amplitude * texture * modulation, 0.0, 1.0)
        elif mode == 5:
            target = flat_field(self.patch_size, self.patch_size, rng)
            mask = np.zeros_like(target)
            sdf = np.full_like(target, -24.0)

        # Tile-context pairs must contain the same physical pixels viewed with
        # different surrounding context.  Build one coherent observation over
        # the union first, then crop two overlapping windows from it.  Merely
        # degrading the same crop twice would test noise robustness, not seams.
        if pair_type == 3:
            shift_y = int(rng.choice((-16, -8, 8, 16)))
            shift_x = int(rng.choice((-16, -8, 8, 16)))
            y1 = int(np.clip(y0 + shift_y, 0, self.canvas_size - self.patch_size))
            x1 = int(np.clip(x0 + shift_x, 0, self.canvas_size - self.patch_size))
            if y1 == y0:
                y1 = y0 + 8 if y0 + self.patch_size + 8 <= self.canvas_size else y0 - 8
            if x1 == x0:
                x1 = x0 + 8 if x0 + self.patch_size + 8 <= self.canvas_size else x0 - 8

            union_y0, union_x0 = min(y0, y1), min(x0, x1)
            union_y1 = max(y0, y1) + self.patch_size
            union_x1 = max(x0, x1) + self.patch_size
            union_h, union_w = union_y1 - union_y0, union_x1 - union_x0
            target_union = np.asarray(
                target_base[union_y0:union_y1, union_x0:union_x1], dtype=np.float32
            ) / 255.0
            mask_union = np.asarray(
                mask_base[union_y0:union_y1, union_x0:union_x1], dtype=np.float32
            ) / 255.0
            sdf_union = sdf_window(
                sdf_small, union_y0, union_x0, union_h, union_w, self.canvas_size
            )
            if mode == 1:
                texture = supersampled_texture(union_h, union_w, union_y0, union_x0, rng)
                amplitude = float(rng.uniform(*CONFIG["data"]["texture"]["amplitude"]))
                modulation = 0.25 + 0.75 * (mask_union if rng.random() < 0.5 else 1.0 - mask_union)
                target_union = np.clip(target_union + amplitude * texture * modulation, 0.0, 1.0)
            elif mode == 5:
                target_union = flat_field(union_h, union_w, rng)
                mask_union = np.zeros_like(target_union)
                sdf_union = np.full_like(target_union, -24.0)

            target_photo = global_photometry(target_union, self._rng(scene_index, salt_base + 300))
            identity = mode == 4
            use_spatial = mode in (2, 3)
            field = (
                spatial_illumination(
                    target_photo.shape, self._rng(scene_index, salt_base + 500), union_y0, union_x0
                )
                if use_spatial else np.ones_like(target_photo)
            )
            illuminated = np.clip(target_photo * field, 0.0, 1.0)
            severity = 0.0 if identity else float(rng.uniform(0.25, 1.0))
            source_union = degrade(illuminated, self._rng(scene_index, salt_base + 700), severity, identity)
            illumination_union = target_photo - illuminated
            if identity:
                source_union = target_photo.copy()
                illumination_union.fill(0.0)

            view_targets, view_sources, view_masks, view_sdfs = [], [], [], []
            view_illumination = []
            origins = ((y0, x0), (y1, x1))
            for view_y, view_x in origins:
                local_y, local_x = view_y - union_y0, view_x - union_x0
                window = np.s_[local_y:local_y + self.patch_size, local_x:local_x + self.patch_size]
                view_targets.append(target_photo[window])
                view_sources.append(source_union[window])
                view_masks.append(mask_union[window])
                view_sdfs.append(sdf_union[window])
                view_illumination.append(illumination_union[window])
            motion_values = ((0.0, 0.0), (float(x0 - x1), float(y0 - y1)))
            return {
                "source": self._tensor(view_sources), "target": self._tensor(view_targets),
                "mask": self._tensor(view_masks), "sdf": self._tensor(view_sdfs),
                "illumination_target": self._tensor(view_illumination),
                "motion": torch.tensor(motion_values, dtype=torch.float32),
                "identity": torch.tensor((identity, identity), dtype=torch.bool),
                "mode": torch.tensor(mode, dtype=torch.int64),
                "pair_type": torch.tensor(pair_type, dtype=torch.int64),
                "scene_index": torch.tensor(scene_index, dtype=torch.int64),
                "sample_index": torch.tensor(index, dtype=torch.int64),
                "origin": torch.tensor((y0, x0), dtype=torch.int64),
                "view_origins": torch.tensor(origins, dtype=torch.int64),
                "scene_id": str(record["scene_id"]), "role": str(record["role"]),
            }

        view_targets, view_sources, view_masks, view_sdfs = [], [], [], []
        view_illumination, motions, identities = [], [], []
        observation_indices = (
            self.epoch + scene_index + sample_salt,
            self.epoch + scene_index + sample_salt + 1,
        )
        motion_values = []
        shared_exposure_severity = float(rng.uniform(0.25, 1.0)) if pair_type == 1 else None
        for view in range(2):
            if pair_type == 2:
                observation = record["observations"][observation_indices[view] % len(record["observations"])]
                dx, dy = float(observation.get("motion_dx_px", 0.0)), float(observation.get("motion_dy_px", 0.0))
            else:
                dx = dy = 0.0
            target_view = warp_array(target, dx, dy, cv2.INTER_LANCZOS4)
            mask_view = warp_array(mask, dx, dy, cv2.INTER_LINEAR)
            sdf_view = warp_array(sdf, dx, dy, cv2.INTER_LINEAR)
            photo_rng = self._rng(
                scene_index, salt_base + 300 + (view if pair_type == 1 else 0)
            )
            target_photo = global_photometry(target_view, photo_rng)
            identity = mode == 4 or (pair_type == 0 and view == 1)
            use_spatial = mode == 3 or (mode == 2 and (pair_type == 1 or view == 1))
            field_salt = 500 if pair_type == 1 else 500 + view
            field = spatial_illumination(
                target_photo.shape, self._rng(scene_index, salt_base + field_salt), y0, x0
            ) if use_spatial else np.ones_like(target_photo)
            illuminated = np.clip(target_photo * field, 0.0, 1.0)
            severity = 0.0 if identity else (
                float(shared_exposure_severity) if shared_exposure_severity is not None
                else float(rng.uniform(0.25, 1.0))
            )
            degradation_salt = 700 if pair_type == 1 else 700 + view
            source = degrade(
                illuminated, self._rng(scene_index, salt_base + degradation_salt), severity, identity
            )
            illumination_target = target_photo - illuminated
            if identity:
                source = target_photo.copy()
                illumination_target.fill(0.0)
            view_sources.append(source)
            view_targets.append(target_photo)
            view_masks.append(mask_view)
            view_sdfs.append(sdf_view)
            view_illumination.append(illumination_target)
            motion_values.append((dx, dy))
            identities.append(identity)

        return {
            "source": self._tensor(view_sources), "target": self._tensor(view_targets),
            "mask": self._tensor(view_masks), "sdf": self._tensor(view_sdfs),
            "illumination_target": self._tensor(view_illumination),
            "motion": torch.tensor(motion_values, dtype=torch.float32),
            "identity": torch.tensor(identities, dtype=torch.bool),
            "mode": torch.tensor(mode, dtype=torch.int64),
            "pair_type": torch.tensor(pair_type, dtype=torch.int64),
            "scene_index": torch.tensor(scene_index, dtype=torch.int64),
            "sample_index": torch.tensor(index, dtype=torch.int64),
            "origin": torch.tensor((y0, x0), dtype=torch.int64),
            "view_origins": torch.tensor(((y0, x0), (y0, x0)), dtype=torch.int64),
            "scene_id": str(record["scene_id"]), "role": str(record["role"]),
        }

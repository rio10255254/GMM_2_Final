"""R114 read-only target dataset and synthetic microscope forward process."""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
from typing import Any, Iterator

import cv2
import numpy as np
import torch
from torch.utils.data import Dataset, Sampler


ROOT = Path(__file__).resolve().parents[1]
DATA_CONFIG = json.loads((ROOT / "config" / "data.json").read_text(encoding="utf-8"))
DEGRADATION = DATA_CONFIG["degradation"]
CHALLENGES = tuple(DATA_CONFIG["degradation_families"])


def _motion_kernel(length: int, angle: float) -> np.ndarray:
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


def _low_field(rng: np.random.Generator, shape: tuple[int, int], amplitude: float) -> np.ndarray:
    coarse = rng.normal(0, 1, (7, 7)).astype(np.float32)
    field = cv2.resize(coarse, (shape[1], shape[0]), interpolation=cv2.INTER_CUBIC)
    field = cv2.GaussianBlur(field, (0, 0), max(shape) / 14.0)
    field -= float(field.mean())
    return field * (amplitude / max(float(field.std()), 1.0e-6))


def _angular_wedge(mask: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    height, width = mask.shape
    yy, xx = np.mgrid[0:height, 0:width].astype(np.float32)
    ys, xs = np.nonzero(mask > 0.5)
    cx, cy = (float(xs.mean()), float(ys.mean())) if len(xs) else (width / 2, height / 2)
    angle = np.arctan2(yy - cy, xx - cx)
    center = float(rng.uniform(-np.pi, np.pi))
    spread = float(rng.uniform(0.25, 0.75))
    distance = np.abs(np.angle(np.exp(1j * (angle - center))))
    return np.exp(-(distance ** 2) / (2 * spread ** 2)).astype(np.float32)


def _colored_noise(rng: np.random.Generator, shape: tuple[int, int], beta: float) -> np.ndarray:
    white = rng.normal(0, 1, shape).astype(np.float32)
    spectrum = np.fft.rfft2(white)
    fy = np.fft.fftfreq(shape[0])[:, None]
    fx = np.fft.rfftfreq(shape[1])[None, :]
    radius = np.sqrt(fx * fx + fy * fy)
    scale = np.maximum(radius, 1.0 / max(shape)) ** (-0.5 * beta)
    scale[0, 0] = 0
    value = np.fft.irfft2(spectrum * scale, s=shape).real.astype(np.float32)
    value -= float(np.median(value))
    robust = float(np.median(np.abs(value))) * 1.4826
    return value / max(robust, 1.0e-6)


def _band_limited_noise(rng: np.random.Generator, shape: tuple[int, int]) -> np.ndarray:
    white = rng.normal(0, 1, shape).astype(np.float32)
    small = float(rng.uniform(0.7, 3.0))
    large = float(rng.uniform(max(2.0, small * 1.8), 12.0))
    value = cv2.GaussianBlur(white, (0, 0), small) - cv2.GaussianBlur(white, (0, 0), large)
    value -= float(value.mean())
    return value / max(float(value.std()), 1.0e-6)


def _nonuniform_blur(image: np.ndarray, rng: np.random.Generator, base_sigma: float) -> tuple[np.ndarray, float]:
    delta = float(rng.uniform(*DEGRADATION["nonuniform_psf_sigma_delta"]))
    first_sigma = max(0.35, base_sigma - 0.5 * delta)
    second_sigma = base_sigma + 0.5 * delta
    first = cv2.GaussianBlur(image, (0, 0), first_sigma, borderType=cv2.BORDER_REFLECT_101)
    second = cv2.GaussianBlur(image, (0, 0), second_sigma, borderType=cv2.BORDER_REFLECT_101)
    field = _low_field(rng, image.shape, 1.0)
    blend = 1.0 / (1.0 + np.exp(-1.5 * field))
    return (blend * first + (1.0 - blend) * second).astype(np.float32), second_sigma


def degrade(
    target: np.ndarray,
    mask: np.ndarray,
    rng: np.random.Generator,
    challenge: str,
    flat: bool,
) -> tuple[np.ndarray, dict[str, float]]:
    if challenge == "identity":
        return target.copy(), {"sigma": 0.0, "recoverability_prior": 1.0}

    low, high = DEGRADATION["blur_sigma_px"]
    sigma_x = float(np.exp(rng.uniform(np.log(low), np.log(high))))
    sigma_y = float(np.clip(sigma_x * rng.uniform(*DEGRADATION["anisotropy"]), low, high))
    effective_sigma = math.sqrt(sigma_x * sigma_y)
    image = target.copy()
    midpoint = float(np.median(target))

    if challenge in {"low_contrast", "boundary_fade", "mixed_hard", "five_x_dense"}:
        image = midpoint + float(rng.uniform(*DEGRADATION["contrast_scale"])) * (image - midpoint)
    if challenge in {"boundary_fade", "mixed_hard"} and not flat:
        background = float(np.median(target[mask < 0.1])) if np.any(mask < 0.1) else float(target.mean())
        strength = float(rng.uniform(*DEGRADATION["boundary_fade_strength"]))
        fade = _angular_wedge(mask, rng) * mask
        image = image * (1.0 - strength * fade) + background * strength * fade
    if challenge in {"uneven_illumination", "mixed_hard", "five_x_dense", "fixed_pattern"}:
        image += _low_field(rng, target.shape, float(rng.uniform(*DEGRADATION["illumination_amplitude"])))

    if challenge == "nonuniform_psf":
        image, effective_sigma = _nonuniform_blur(image.astype(np.float32), rng, effective_sigma)
    else:
        image = cv2.GaussianBlur(
            image.astype(np.float32),
            (0, 0),
            sigmaX=sigma_x,
            sigmaY=sigma_y,
            borderType=cv2.BORDER_REFLECT_101,
        )

    if not flat and (
        challenge in {"asymmetric_blur_halo", "mixed_hard"}
        or rng.random() < float(DEGRADATION["motion_blur_probability"])
    ):
        kernel = _motion_kernel(
            int(rng.choice(DEGRADATION["motion_blur_lengths"])),
            float(rng.uniform(0, math.pi)),
        )
        image = cv2.filter2D(image, -1, kernel, borderType=cv2.BORDER_REFLECT_101)
    if not flat and rng.random() < float(DEGRADATION["ghost_probability"]):
        dx, dy = float(rng.uniform(-2, 2)), float(rng.uniform(-2, 2))
        ghost = cv2.warpAffine(
            image,
            np.asarray([[1, 0, dx], [0, 1, dy]], np.float32),
            (image.shape[1], image.shape[0]),
            flags=cv2.INTER_LINEAR,
            borderMode=cv2.BORDER_REFLECT_101,
        )
        mix = float(rng.uniform(*DEGRADATION["ghost_mix"]))
        image = (1.0 - mix) * image + mix * ghost
    if challenge in {"asymmetric_blur_halo", "mixed_hard"} or rng.random() < float(DEGRADATION["halo_probability"]):
        broad = cv2.GaussianBlur(image, (0, 0), float(rng.uniform(3, 7)))
        image += float(rng.uniform(*DEGRADATION["halo_strength"])) * (broad - image)

    if challenge == "colored_noise" or rng.random() < 0.20:
        sigma = float(rng.uniform(*DEGRADATION["colored_noise_sigma"]))
        image += sigma * _colored_noise(rng, image.shape, float(rng.uniform(0.7, 2.2)))
    if challenge == "band_limited_noise" or rng.random() < 0.15:
        sigma = float(rng.uniform(*DEGRADATION["band_limited_noise_sigma"]))
        image += sigma * _band_limited_noise(rng, image.shape)
    if challenge == "fixed_pattern" or rng.random() < 0.18:
        amplitude = float(rng.uniform(*DEGRADATION["fixed_pattern_amplitude"]))
        phase = float(rng.uniform(0, 2 * math.pi))
        period = float(rng.uniform(5, 80))
        yy, xx = np.mgrid[0:image.shape[0], 0:image.shape[1]]
        angle = float(rng.uniform(0, math.pi))
        image += amplitude * np.sin(2 * math.pi * (xx * math.cos(angle) + yy * math.sin(angle)) / period + phase)

    white_sigma = float(rng.uniform(*DEGRADATION["white_noise_sigma"]))
    image += rng.normal(0, white_sigma, image.shape).astype(np.float32)
    image += rng.normal(0, float(rng.uniform(*DEGRADATION["row_noise_sigma"])), (image.shape[0], 1)).astype(np.float32)
    image += rng.normal(0, float(rng.uniform(*DEGRADATION["column_noise_sigma"])), (1, image.shape[1])).astype(np.float32)
    recoverability_prior = float(np.exp(-max(effective_sigma - 0.65, 0) / 3.2))
    return np.clip(image, 0, 1).astype(np.float32), {
        "sigma": effective_sigma,
        "recoverability_prior": recoverability_prior,
    }


class R114Dataset(Dataset):
    def __init__(self, split: str, epoch: int = 0, limit: int = 0):
        manifest_path = ROOT / "data" / "manifest.json"
        if not manifest_path.is_file():
            raise FileNotFoundError("R114 data is not materialized; run scripts/prepare_data.py --mode materialize")
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
        self.records = [row for row in payload["records"] if row["split"] == split]
        self.records.sort(key=lambda row: int(row["logical_index"]))
        if limit > 0:
            groups: dict[tuple[str, str], list[dict[str, Any]]] = {}
            for row in self.records:
                groups.setdefault((str(row["family"]), str(row["role"])), []).append(row)
            selected: list[dict[str, Any]] = []
            depth = 0
            keys = sorted(groups)
            while len(selected) < min(limit, len(self.records)):
                added = False
                for key in keys:
                    if depth < len(groups[key]) and len(selected) < limit:
                        selected.append(groups[key][depth])
                        added = True
                if not added:
                    break
                depth += 1
            self.records = sorted(selected, key=lambda row: int(row["logical_index"]))
        self.index_by_id = {row["record_id"]: index for index, row in enumerate(self.records)}
        self.split = split
        self.epoch = int(epoch)

    def set_epoch(self, epoch: int) -> None:
        self.epoch = int(epoch)

    def __len__(self) -> int:
        return len(self.records)

    def _rng(self, row: dict[str, Any], salt: int = 0) -> np.random.Generator:
        logical = int(row["logical_index"])
        seed = (
            int(DATA_CONFIG["seed"]) * 1_000_003
            + logical * 10_007
            + self.epoch * 7_919
            + salt * 104_729
        ) % (2 ** 63 - 1)
        return np.random.default_rng(seed)

    @staticmethod
    def _load(row: dict[str, Any], key: str) -> np.ndarray:
        path = Path(row["artifact_root"]) / row[key]
        if not path.is_file():
            raise FileNotFoundError(path)
        return np.asarray(np.load(path, mmap_mode="r"))

    def __getitem__(self, index: int) -> dict[str, Any]:
        row = self.records[index]
        target = self._load(row, "target").astype(np.float32) / 255.0
        mask = self._load(row, "mask").astype(np.float32) / 255.0
        sdf = self._load(row, "sdf").astype(np.float32)
        is_identity = row["role"] == "identity"
        is_flat = row["role"] == "flat_negative"
        general_challenges = tuple(value for value in CHALLENGES if value != "five_x_dense")
        challenge = "identity" if is_identity else general_challenges[
            (int(row["logical_index"]) + self.epoch) % len(general_challenges)
        ]
        if row["family"] == "dense_array" and (int(row["logical_index"]) + self.epoch) % 3 == 0:
            challenge = "five_x_dense"
        source, meta = degrade(target, mask, self._rng(row, 101), challenge, flat=is_flat)
        return {
            "source": torch.from_numpy(source[None]),
            "target": torch.from_numpy(target[None]),
            "mask": torch.from_numpy(mask[None]),
            "sdf": torch.from_numpy(sdf[None]),
            "identity": torch.tensor(is_identity, dtype=torch.bool),
            "flat": torch.tensor(is_flat, dtype=torch.bool),
            "midpoint": torch.tensor(float(row["midpoint"]), dtype=torch.float32),
            "polarity": torch.tensor(float(row["polarity"]), dtype=torch.float32),
            "recoverability_prior": torch.tensor(meta["recoverability_prior"], dtype=torch.float32),
            "scene_index": torch.tensor(int(row["logical_index"]), dtype=torch.int64),
            "record_id": str(row["record_id"]),
            "role": str(row["role"]),
            "family": str(row["family"]),
            "challenge": challenge,
        }


class ManifestBatchSampler(Sampler[list[int]]):
    """Use the audited composition schedule while changing order every epoch."""

    def __init__(self, dataset: R114Dataset, batch_size: int, epoch: int, shuffle: bool):
        schedule_path = ROOT / "data" / "batches" / f"formal_{dataset.split}_bs{batch_size}_epoch0.jsonl"
        if not schedule_path.is_file():
            raise FileNotFoundError(schedule_path)
        rows = [json.loads(line) for line in schedule_path.read_text(encoding="utf-8").splitlines() if line.strip()]
        batches = []
        for row in rows:
            indices = [dataset.index_by_id[record_id] for record_id in row["record_ids"] if record_id in dataset.index_by_id]
            if indices:
                batches.append(indices)
        if shuffle:
            rng = np.random.default_rng(int(DATA_CONFIG["seed"]) + int(epoch) * 17_171)
            batches = [batches[int(index)] for index in rng.permutation(len(batches))]
            batches = [[batch[int(index)] for index in rng.permutation(len(batch))] for batch in batches]
        self.batches = batches

    def __iter__(self) -> Iterator[list[int]]:
        yield from self.batches

    def __len__(self) -> int:
        return len(self.batches)


def manifest_sha256() -> str:
    path = ROOT / "data" / "manifest.json"
    return hashlib.sha256(path.read_bytes()).hexdigest()

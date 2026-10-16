"""Generate phase-consistent continuous-scene pairs for the R101 A/B/C test."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path

import cv2
import numpy as np


ROOT = Path(__file__).resolve().parents[1]


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    os.replace(temporary, path)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def normalized_pattern(rng: np.random.Generator, height: int, width: int, family: int) -> np.ndarray:
    noise = rng.normal(0.0, 1.0, (height, width)).astype(np.float32)
    fine = cv2.GaussianBlur(noise, (0, 0), 2.0, borderType=cv2.BORDER_REFLECT_101)
    medium = cv2.GaussianBlur(noise, (0, 0), 8.0, borderType=cv2.BORDER_REFLECT_101)
    coarse = cv2.GaussianBlur(noise, (0, 0), 20.0, borderType=cv2.BORDER_REFLECT_101)
    yy, xx = np.mgrid[:height, :width].astype(np.float32)
    angle = float(rng.uniform(0.0, np.pi))
    period = float(rng.uniform(36.0, 120.0))
    phase = float(rng.uniform(0.0, 2.0 * np.pi))
    ridges = np.sin(2.0 * np.pi * (np.cos(angle) * xx + np.sin(angle) * yy) / period + phase)
    if family == 0:
        pattern = 0.75 * ridges + 0.25 * medium
    elif family == 1:
        pattern = 0.65 * fine + 0.35 * medium
    elif family == 2:
        pattern = medium - coarse
    else:
        pattern = 0.35 * ridges + 0.40 * fine + 0.25 * (medium - coarse)
    pattern = pattern.astype(np.float32)
    pattern -= float(np.mean(pattern))
    scale = float(np.percentile(np.abs(pattern), 97.0))
    return np.clip(pattern / max(scale, 1e-6), -1.5, 1.5)


def irregular_polygon(
    rng: np.random.Generator,
    center: tuple[float, float],
    radius: tuple[float, float],
    count: int,
) -> np.ndarray:
    angles = np.sort(rng.uniform(0.0, 2.0 * np.pi, count))
    radial = rng.uniform(0.72, 1.18, count)
    x = center[0] + radius[0] * radial * np.cos(angles)
    y = center[1] + radius[1] * radial * np.sin(angles)
    return np.stack([x, y], axis=1).round().astype(np.int32)


def draw_mask(rng: np.random.Generator, size: int, family: int) -> np.ndarray:
    mask = np.zeros((size, size), np.uint8)
    margin = int(size * 0.12)
    center = (int(rng.uniform(0.40, 0.60) * size), int(rng.uniform(0.40, 0.60) * size))
    if family == 0:
        points = irregular_polygon(
            rng,
            center,
            (rng.uniform(0.20, 0.34) * size, rng.uniform(0.16, 0.30) * size),
            48,
        )
        cv2.fillPoly(mask, [points], 255, lineType=cv2.LINE_AA)
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (17, 17))
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
    elif family == 1:
        points = irregular_polygon(
            rng,
            center,
            (rng.uniform(0.22, 0.36) * size, rng.uniform(0.20, 0.34) * size),
            int(rng.integers(5, 11)),
        )
        cv2.fillPoly(mask, [points], 255, lineType=cv2.LINE_AA)
    elif family == 2:
        x0 = int(rng.uniform(0.16, 0.30) * size)
        y0 = int(rng.uniform(0.16, 0.30) * size)
        x1 = int(rng.uniform(0.70, 0.84) * size)
        y1 = int(rng.uniform(0.70, 0.84) * size)
        radius = int(rng.uniform(0.04, 0.10) * size)
        cv2.rectangle(mask, (x0 + radius, y0), (x1 - radius, y1), 255, -1)
        cv2.rectangle(mask, (x0, y0 + radius), (x1, y1 - radius), 255, -1)
        for cx, cy in ((x0 + radius, y0 + radius), (x1 - radius, y0 + radius), (x0 + radius, y1 - radius), (x1 - radius, y1 - radius)):
            cv2.circle(mask, (cx, cy), radius, 255, -1, lineType=cv2.LINE_AA)
    elif family == 3:
        thickness = int(rng.uniform(0.05, 0.10) * size)
        length = int(rng.uniform(0.24, 0.38) * size)
        angles = [float(rng.uniform(0.0, np.pi)), float(rng.uniform(0.0, np.pi))]
        for angle in angles:
            delta = (int(np.cos(angle) * length), int(np.sin(angle) * length))
            cv2.line(mask, (center[0] - delta[0], center[1] - delta[1]), (center[0] + delta[0], center[1] + delta[1]), 255, thickness, cv2.LINE_AA)
        cv2.circle(mask, center, thickness, 255, -1, lineType=cv2.LINE_AA)
    elif family == 4:
        count = int(rng.integers(4, 8))
        thickness = int(rng.uniform(0.012, 0.030) * size)
        angle = float(rng.uniform(0.0, np.pi))
        normal = np.array([-np.sin(angle), np.cos(angle)])
        tangent = np.array([np.cos(angle), np.sin(angle)])
        spacing = float(rng.uniform(0.035, 0.065) * size)
        for index in range(count):
            offset = (index - (count - 1) / 2.0) * spacing
            c = np.asarray(center, np.float32) + normal * offset
            half = tangent * rng.uniform(0.22, 0.38) * size
            p0, p1 = np.rint(c - half).astype(int), np.rint(c + half).astype(int)
            cv2.line(mask, tuple(p0), tuple(p1), 255, thickness, cv2.LINE_AA)
    elif family == 5:
        period = int(rng.uniform(0.035, 0.065) * size)
        thickness = max(4, int(period * rng.uniform(0.28, 0.52)))
        angle = float(rng.uniform(0.0, np.pi))
        normal = np.array([-np.sin(angle), np.cos(angle)])
        tangent = np.array([np.cos(angle), np.sin(angle)])
        for offset in range(-size, size + period, period):
            c = np.asarray(center, np.float32) + normal * offset
            half = tangent * size
            p0, p1 = np.rint(c - half).astype(int), np.rint(c + half).astype(int)
            cv2.line(mask, tuple(p0), tuple(p1), 255, thickness, cv2.LINE_AA)
        aperture = np.zeros_like(mask)
        cv2.ellipse(aperture, center, (int(0.38 * size), int(0.34 * size)), 0, 0, 360, 255, -1, cv2.LINE_AA)
        mask = cv2.bitwise_and(mask, aperture)
    else:
        for _ in range(int(rng.integers(2, 6))):
            c = (int(rng.uniform(0.20, 0.80) * size), int(rng.uniform(0.20, 0.80) * size))
            axes = (int(rng.uniform(0.055, 0.16) * size), int(rng.uniform(0.045, 0.14) * size))
            cv2.ellipse(mask, c, axes, float(rng.uniform(0, 180)), 0, 360, 255, -1, cv2.LINE_AA)
    if np.mean(mask > 127) < 0.02:
        cv2.circle(mask, center, max(8, int(size * 0.12)), 255, -1, lineType=cv2.LINE_AA)
    mask[:margin // 3] = 0
    mask[-margin // 3:] = 0
    mask[:, :margin // 3] = 0
    mask[:, -margin // 3:] = 0
    return mask


def warp(array: np.ndarray, dx: float, dy: float, interpolation: int) -> np.ndarray:
    matrix = np.asarray([[1.0, 0.0, dx], [0.0, 1.0, dy]], np.float32)
    return cv2.warpAffine(array, matrix, (array.shape[1], array.shape[0]), flags=interpolation, borderMode=cv2.BORDER_REFLECT_101)


def signed_distance(mask: np.ndarray) -> np.ndarray:
    inside = (mask >= 0.5).astype(np.uint8)
    outside = 1 - inside
    return cv2.distanceTransform(inside, cv2.DIST_L2, 5) - cv2.distanceTransform(outside, cv2.DIST_L2, 5)


def make_scene(rng: np.random.Generator, patch: int, supersample: int, scene_index: int, identity: bool) -> list[dict[str, object]]:
    high = patch * supersample
    family = scene_index % 7
    texture_family = scene_index % 4
    mask_hi_u8 = draw_mask(rng, high, family)
    mask_hi = mask_hi_u8.astype(np.float32) / 255.0
    pattern = normalized_pattern(rng, high, high, texture_family)

    background = float(rng.uniform(0.18, 0.82))
    contrast = float(rng.uniform(0.18, 0.62))
    bright_foreground = bool(rng.integers(0, 2))
    foreground = float(np.clip(background + (contrast if bright_foreground else -contrast), 0.04, 0.96))
    if abs(foreground - background) < 0.14:
        foreground = float(np.clip(background + (0.18 if bright_foreground else -0.18), 0.04, 0.96))
    texture_amplitude = float(rng.uniform(0.018, 0.060))
    latent_hi = background + mask_hi * (foreground - background)
    latent_hi += texture_amplitude * pattern * (0.25 + 0.75 * mask_hi)
    latent_hi = np.clip(latent_hi, 0.0, 1.0).astype(np.float32)

    base_shift = rng.uniform(-0.35, 0.35, 2)
    magnitude = float(rng.uniform(0.25, 0.90))
    angle = float(rng.uniform(0.0, 2.0 * np.pi))
    relative = magnitude * np.asarray([np.cos(angle), np.sin(angle)])
    shifts = [base_shift, base_shift + relative]
    rows: list[dict[str, object]] = []
    reference_sigma = 0.25
    levels = [0.85, 1.20, 1.60]

    for observation, shift in enumerate(shifts):
        shifted_latent = warp(latent_hi, float(shift[0] * supersample), float(shift[1] * supersample), cv2.INTER_CUBIC)
        shifted_mask = warp(mask_hi, float(shift[0] * supersample), float(shift[1] * supersample), cv2.INTER_LINEAR)
        target_hi = cv2.GaussianBlur(shifted_latent, (0, 0), reference_sigma * supersample, borderType=cv2.BORDER_REFLECT_101)
        target = cv2.resize(target_hi, (patch, patch), interpolation=cv2.INTER_AREA).astype(np.float32)
        mask = cv2.resize(shifted_mask, (patch, patch), interpolation=cv2.INTER_AREA).astype(np.float32)

        if identity:
            source_sigma = 0.35
            exposure, gamma, bias = 1.0, 1.0, 0.0
            read_noise = float(rng.uniform(0.0002, 0.0010))
        else:
            source_sigma = float(levels[(scene_index + observation) % len(levels)])
            exposure = float(rng.uniform(0.82, 1.18))
            gamma = float(rng.uniform(0.88, 1.14))
            bias = float(rng.uniform(-0.025, 0.025))
            read_noise = float(rng.uniform(0.0015, 0.0090))
        source_hi = cv2.GaussianBlur(shifted_latent, (0, 0), source_sigma * supersample, borderType=cv2.BORDER_REFLECT_101)
        source_linear = cv2.resize(source_hi, (patch, patch), interpolation=cv2.INTER_AREA).astype(np.float32)
        source_clean = np.power(np.clip(source_linear * exposure + bias, 0.0, 1.0), gamma).astype(np.float32)
        shot_peak = float(rng.uniform(2500.0, 16000.0))
        shot = rng.poisson(np.clip(source_clean, 0.0, 1.0) * shot_peak).astype(np.float32) / shot_peak
        source = np.clip(shot + rng.normal(0.0, read_noise, shot.shape).astype(np.float32), 0.0, 1.0)
        sdf = signed_distance(mask)
        boundary = np.exp(-np.abs(sdf) / 1.6).astype(np.float32)
        rows.append({
            "source": source,
            "source_clean": source_clean,
            "target": target,
            "mask": mask,
            "sdf": sdf,
            "boundary": boundary,
            "source_sigma": source_sigma,
            "exposure": exposure,
            "gamma": gamma,
            "bias": bias,
            "foreground": foreground,
            "background": background,
            "dx": float(shift[0]),
            "dy": float(shift[1]),
            "identity": identity,
            "shape_family": family,
            "texture_family": texture_family,
            "observation": observation,
        })
    return rows


def montage(path: Path, arrays: dict[str, np.ndarray], count: int = 6) -> None:
    panels = []
    for index in range(min(count, len(arrays["source"]))):
        source = np.clip(arrays["source"][index] * 255.0, 0, 255).astype(np.uint8)
        target = np.clip(arrays["target"][index] * 255.0, 0, 255).astype(np.uint8)
        mask = np.clip(arrays["mask"][index] * 255.0, 0, 255).astype(np.uint8)
        panels.append(np.concatenate([source, target, mask], axis=1))
    canvas = np.concatenate(panels, axis=0)
    path.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(path), canvas)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=ROOT / "config" / "experiment.json")
    args = parser.parse_args()
    config = json.loads(args.config.read_text(encoding="utf-8"))
    data_config = config["data"]
    seed = int(data_config["seed"])
    patch = int(data_config["patch_size"])
    supersample = int(data_config["supersample_factor"])
    split_counts = {"train": int(data_config["train_scenes"]), "validation": int(data_config["validation_scenes"])}

    collected: dict[str, list[object]] = {
        name: [] for name in (
            "source", "source_clean", "target", "mask", "sdf", "boundary", "source_sigma", "exposure", "gamma", "bias",
            "foreground", "background", "dx", "dy", "identity", "shape_family", "texture_family", "observation", "scene_id", "split",
        )
    }
    scene_cursor = 0
    for split_name, scene_count in split_counts.items():
        for local_scene in range(scene_count):
            scene_seed = seed + scene_cursor * 10007
            rng = np.random.default_rng(scene_seed)
            identity = local_scene % 7 == 0
            for row in make_scene(rng, patch, supersample, scene_cursor, identity):
                for name in row:
                    collected[name].append(row[name])
                collected["scene_id"].append(scene_cursor)
                collected["split"].append(0 if split_name == "train" else 1)
            scene_cursor += 1

    arrays: dict[str, np.ndarray] = {}
    image_names = {"source", "source_clean", "target", "mask", "sdf", "boundary"}
    for name, values in collected.items():
        if name in image_names:
            arrays[name] = np.asarray(values, dtype=np.float16)
        elif name in {"identity"}:
            arrays[name] = np.asarray(values, dtype=np.uint8)
        elif name in {"shape_family", "texture_family", "observation", "scene_id", "split"}:
            arrays[name] = np.asarray(values, dtype=np.int32)
        else:
            arrays[name] = np.asarray(values, dtype=np.float32)

    output = ROOT / "data" / "continuous_pairs.npz"
    temporary = output.with_name(output.stem + ".tmp.npz")
    output.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(temporary, **arrays)
    os.replace(temporary, output)

    train_indices = np.flatnonzero(arrays["split"] == 0)
    schedule_rng = np.random.default_rng(int(config["training"]["seed"]) + 77)
    steps = int(config["training"]["steps_per_arm"])
    batch_size = int(config["training"]["batch_size"])
    schedule = np.empty((steps, batch_size), dtype=np.int32)
    pool = np.empty(0, dtype=np.int32)
    for step in range(steps):
        if len(pool) < batch_size:
            pool = np.concatenate([pool, schedule_rng.permutation(train_indices)])
        schedule[step], pool = pool[:batch_size], pool[batch_size:]
    np.save(ROOT / "data" / "batch_schedule.npy", schedule)

    montage(ROOT / "data" / "dataset_preview.png", arrays)
    metadata = {
        "status": "complete",
        "experiment_id": config["experiment_id"],
        "procedural_only": True,
        "contains_real_sem_or_hs100mg_pixels": False,
        "continuous_latent_supersample_factor": supersample,
        "patch_size": patch,
        "scene_counts": split_counts,
        "sample_counts": {"train": int(np.sum(arrays["split"] == 0)), "validation": int(np.sum(arrays["split"] == 1))},
        "observations_per_scene": int(data_config["observations_per_scene"]),
        "source_and_target_share_latent_geometry_and_texture_phase": True,
        "source_sha256": sha256(Path(__file__)),
        "dataset_sha256": sha256(output),
        "schedule_sha256": sha256(ROOT / "data" / "batch_schedule.npy"),
        "array_shapes": {name: list(value.shape) for name, value in arrays.items()},
    }
    write_json(ROOT / "data" / "dataset_manifest.json", metadata)
    print(json.dumps(metadata, indent=2, ensure_ascii=False), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


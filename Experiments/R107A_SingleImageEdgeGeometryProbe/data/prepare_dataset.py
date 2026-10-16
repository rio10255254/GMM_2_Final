"""Generate the self-contained R107 procedural base package.

Clear targets and geometry are materialized once.  Degraded observations are
generated deterministically by the Dataset per epoch, preserving a compact
package while providing broad optical diversity.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
from typing import Any

import cv2
import numpy as np


ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "config" / "experiment.json"
CONFIG = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))


def atomic_json(path: Path, payload: Any) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    temporary.replace(path)


def polygon_points(center, radius, count, phase, radial=None):
    angles = phase + np.arange(count, dtype=np.float32) * 2.0 * math.pi / count
    radii = np.full(count, radius, dtype=np.float32) if radial is None else np.asarray(radial, dtype=np.float32)
    return np.stack([center[0] + radii * np.cos(angles), center[1] + radii * np.sin(angles)], axis=1).round().astype(np.int32)


def draw_single(mask: np.ndarray, family: str, rng: np.random.Generator, *, scale: float = 1.0) -> None:
    h, w = mask.shape
    cx, cy = float(rng.uniform(0.28, 0.72) * w), float(rng.uniform(0.28, 0.72) * h)
    radius = float(rng.uniform(0.12, 0.27) * min(h, w) * scale)
    if family == "circle":
        cv2.circle(mask, (round(cx), round(cy)), max(2, round(radius)), 255, -1, cv2.LINE_AA)
    elif family == "ellipse":
        axes = (max(2, round(radius * rng.uniform(0.65, 1.35))), max(2, round(radius * rng.uniform(0.42, 0.92))))
        cv2.ellipse(mask, (round(cx), round(cy)), axes, float(rng.uniform(-70, 70)), 0, 360, 255, -1, cv2.LINE_AA)
    elif family == "rectangle":
        rect = ((cx, cy), (radius * rng.uniform(1.1, 2.2), radius * rng.uniform(0.8, 1.8)), float(rng.uniform(-70, 70)))
        cv2.fillConvexPoly(mask, cv2.boxPoints(rect).round().astype(np.int32), 255, cv2.LINE_AA)
    elif family == "polygon":
        count = int(rng.integers(4, 10)); radial = radius * rng.uniform(0.72, 1.20, count)
        cv2.fillPoly(mask, [polygon_points((cx, cy), radius, count, float(rng.uniform(0, math.pi)), radial)], 255, cv2.LINE_AA)
    elif family == "ring":
        cv2.circle(mask, (round(cx), round(cy)), max(3, round(radius)), 255, -1, cv2.LINE_AA)
        cv2.circle(mask, (round(cx), round(cy)), max(1, round(radius * rng.uniform(0.42, 0.74))), 0, -1, cv2.LINE_AA)
    elif family == "crescent":
        cv2.circle(mask, (round(cx), round(cy)), max(3, round(radius)), 255, -1, cv2.LINE_AA)
        offset = radius * rng.uniform(0.25, 0.52)
        cv2.circle(mask, (round(cx + offset), round(cy + rng.uniform(-0.15, 0.15) * radius)), max(2, round(radius * rng.uniform(0.80, 0.94))), 0, -1, cv2.LINE_AA)
    elif family == "lobed":
        count = 160; angle = np.arange(count, dtype=np.float32) * 2.0 * math.pi / count
        radial = radius * (1.0 + rng.uniform(0.10, 0.28) * np.sin(int(rng.integers(3, 10)) * angle + rng.uniform(-math.pi, math.pi)))
        cv2.fillPoly(mask, [polygon_points((cx, cy), radius, count, 0.0, radial)], 255, cv2.LINE_AA)
    elif family == "thin_neck":
        left, right = (round(cx - 0.52 * radius), round(cy)), (round(cx + 0.52 * radius), round(cy))
        disk = max(2, round(radius * rng.uniform(0.48, 0.68)))
        cv2.circle(mask, left, disk, 255, -1, cv2.LINE_AA); cv2.circle(mask, right, disk, 255, -1, cv2.LINE_AA)
        neck = max(1, round(radius * rng.uniform(0.07, 0.20)))
        cv2.rectangle(mask, (left[0], round(cy - neck)), (right[0], round(cy + neck)), 255, -1)
    elif family == "thin_bar":
        length = radius * rng.uniform(2.0, 4.2); thickness = max(2.0, radius * rng.uniform(0.10, 0.28))
        rect = ((cx, cy), (length, thickness), float(rng.uniform(-90, 90)))
        cv2.fillConvexPoly(mask, cv2.boxPoints(rect).round().astype(np.int32), 255, cv2.LINE_AA)
    elif family == "irregular_blob":
        count = int(rng.integers(10, 24)); radial = radius * rng.uniform(0.58, 1.28, count)
        radial = np.convolve(np.r_[radial[-2:], radial, radial[:2]], np.ones(5) / 5.0, mode="valid")
        cv2.fillPoly(mask, [polygon_points((cx, cy), radius, count, float(rng.uniform(0, math.pi)), radial)], 255, cv2.LINE_AA)
    else:
        raise ValueError(family)


def draw_mask(size: int, factor: int, family: str, rng: np.random.Generator) -> np.ndarray:
    high = size * factor
    mask = np.zeros((high, high), dtype=np.uint8)
    if family == "dense_array":
        pitch = int(rng.integers(max(12, factor * 5), max(18, factor * 13)))
        radius = max(2, int(pitch * rng.uniform(0.22, 0.42)))
        offset_x, offset_y = int(rng.integers(0, pitch)), int(rng.integers(0, pitch))
        for y in range(offset_y - pitch, high + pitch, pitch):
            for x in range(offset_x - pitch, high + pitch, pitch):
                if rng.random() > 0.08:
                    cv2.circle(mask, (x, y), radius, 255, -1, cv2.LINE_AA)
        if rng.random() < 0.45:
            cv2.circle(mask, (int(rng.uniform(0.2, 0.8) * high), int(rng.uniform(0.2, 0.8) * high)), radius, 0, -1, cv2.LINE_AA)
    elif family == "mixed_field":
        choices = ["circle", "ellipse", "rectangle", "polygon", "ring", "thin_bar", "irregular_blob"]
        for _ in range(int(rng.integers(3, 9))):
            draw_single(mask, str(rng.choice(choices)), rng, scale=float(rng.uniform(0.40, 0.82)))
    else:
        draw_single(mask, family, rng)
    return mask


def analytic_texture(size: int, rng: np.random.Generator) -> np.ndarray:
    yy, xx = np.mgrid[0:size, 0:size].astype(np.float32)
    texture = np.zeros((size, size), dtype=np.float32)
    for _ in range(int(rng.integers(2, 6))):
        angle = float(rng.uniform(0, math.pi)); period = float(np.exp(rng.uniform(np.log(2.6), np.log(22.0)))); phase = float(rng.uniform(-math.pi, math.pi))
        coordinate = xx * math.cos(angle) + yy * math.sin(angle)
        texture += float(rng.uniform(0.3, 1.0)) * np.sin(2.0 * math.pi * coordinate / period + phase)
    texture -= float(texture.mean()); scale = float(np.percentile(np.abs(texture), 99.0))
    return (texture / max(scale, 1e-6)).clip(-1.0, 1.0)


def shared_photometry(image: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    cfg = CONFIG["data"]["target"]
    gamma = float(rng.uniform(*cfg["shared_gamma"])); contrast = float(rng.uniform(*cfg["shared_contrast"])); amplitude = float(rng.uniform(*cfg["shared_illumination_amplitude"]))
    result = np.power(np.clip(image, 0, 1), gamma).astype(np.float32); midpoint = float(np.median(result)); result = midpoint + contrast * (result - midpoint)
    if amplitude > 0:
        yy, xx = np.mgrid[0:image.shape[0], 0:image.shape[1]].astype(np.float32); xx = (xx + 0.5) / image.shape[1] - 0.5; yy = (yy + 0.5) / image.shape[0] - 0.5
        angle = float(rng.uniform(0, 2 * math.pi)); result *= 1.0 + 2.0 * amplitude * (math.cos(angle) * xx + math.sin(angle) * yy)
    return np.clip(result, 0, 1)


def choose_role(rng: np.random.Generator) -> str:
    names = list(CONFIG["data"]["role_weights"]); probabilities = np.asarray([CONFIG["data"]["role_weights"][name] for name in names], dtype=np.float64); probabilities /= probabilities.sum()
    return str(rng.choice(names, p=probabilities))


def generate_scene(scene_index: int, split: str, package: Path) -> dict[str, Any]:
    seed = int(CONFIG["data"]["seed"]) + scene_index * 104729 + (0 if split == "train" else 1_000_000_007)
    rng = np.random.default_rng(seed)
    size, factor = int(CONFIG["data"]["canvas_size"]), int(CONFIG["data"]["label_supersample_factor"])
    role = choose_role(rng)
    family = "flat_negative" if role == "flat_negative" else str(rng.choice(CONFIG["data"]["families"]))
    if role == "flat_negative":
        yy, xx = np.mgrid[0:size, 0:size].astype(np.float32); xx = (xx + 0.5) / size - 0.5; yy = (yy + 0.5) / size - 0.5
        target = np.clip(float(rng.uniform(0.12, 0.88)) + rng.uniform(-0.10, 0.10) * xx + rng.uniform(-0.10, 0.10) * yy, 0.03, 0.97)
        mask = np.zeros((size, size), dtype=np.uint8); sdf = np.full((size, size), -32.0, dtype=np.float32); width = 1.0; midpoint = float(np.median(target)); polarity = 1.0
    else:
        high_mask = draw_mask(size, factor, family, rng); binary = (high_mask >= 128).astype(np.uint8)
        inside_distance = cv2.distanceTransform(binary, cv2.DIST_L2, cv2.DIST_MASK_5)
        outside_distance = cv2.distanceTransform(1 - binary, cv2.DIST_L2, cv2.DIST_MASK_5)
        sdf_high = inside_distance - outside_distance
        width = float(rng.uniform(*CONFIG["data"]["target"]["transition_width_px"]))
        polarity = 1.0 if rng.random() < 0.5 else -1.0; outside = float(rng.uniform(0.10, 0.42)); contrast = float(rng.uniform(*CONFIG["data"]["target"]["contrast"])); inside = float(np.clip(outside + polarity * contrast, 0.03, 0.97))
        probability = 1.0 / (1.0 + np.exp(-np.clip(sdf_high / (width * factor), -40, 40)))
        target_high = outside + (inside - outside) * probability
        if role == "textured_edge":
            texture = analytic_texture(size, rng); texture_high = cv2.resize(texture, (size * factor, size * factor), interpolation=cv2.INTER_CUBIC)
            modulation = (0.20 + 0.80 * (high_mask.astype(np.float32) / 255.0)) if rng.random() < 0.5 else (1.0 - 0.75 * (high_mask.astype(np.float32) / 255.0))
            target_high += float(rng.uniform(*CONFIG["data"]["target"]["texture_amplitude"])) * texture_high * modulation
        target = cv2.resize(target_high.astype(np.float32), (size, size), interpolation=cv2.INTER_AREA)
        target = shared_photometry(target, rng)
        coverage = cv2.resize(high_mask.astype(np.float32) / 255.0, (size, size), interpolation=cv2.INTER_AREA)
        mask = np.round(coverage * 255.0).astype(np.uint8)
        sdf = cv2.resize((sdf_high / factor).astype(np.float32), (size, size), interpolation=cv2.INTER_AREA)
        foreground, background = target[coverage >= 0.5], target[coverage < 0.5]
        midpoint = float(0.5 * (foreground.mean() + background.mean())) if foreground.size and background.size else float(np.median(target))

    stem = f"{scene_index:06d}"
    target_rel = f"targets/{stem}.npy"; mask_rel = f"masks/{stem}.npy"; sdf_rel = f"sdf/{stem}.npy"
    np.save(package / target_rel, np.round(np.clip(target, 0, 1) * 255.0).astype(np.uint8), allow_pickle=False)
    np.save(package / mask_rel, mask.astype(np.uint8), allow_pickle=False)
    np.save(package / sdf_rel, sdf.astype(np.float16), allow_pickle=False)
    return {
        "scene_index": int(scene_index), "scene_id": f"r107_{split}_{stem}", "split": split, "role": role, "family": family,
        "target": target_rel, "mask": mask_rel, "sdf": sdf_rel, "target_width_px": width,
        "midpoint": midpoint, "polarity": polarity, "seed": int(seed),
    }


def render_preview(package: Path, records: list[dict[str, Any]]) -> None:
    selected = records[:24]
    tile = 128; canvas = np.zeros((6 * tile, 4 * tile), dtype=np.uint8)
    for index, record in enumerate(selected):
        image = np.load(package / record["target"], allow_pickle=False)
        image = cv2.resize(image, (tile, tile), interpolation=cv2.INTER_AREA)
        row, column = divmod(index, 4); canvas[row * tile:(row + 1) * tile, column * tile:(column + 1) * tile] = image
    cv2.imencode(".png", canvas)[1].tofile(str(package / "preview_targets.png"))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=0, help="Generate only the first N total scenes for smoke testing")
    args = parser.parse_args()
    package = ROOT / CONFIG["data"]["package_root"]
    package.mkdir(parents=True, exist_ok=True)
    for folder in ("targets", "masks", "sdf"):
        (package / folder).mkdir(parents=True, exist_ok=True)
    config_hash = hashlib.sha256(CONFIG_PATH.read_bytes()).hexdigest()
    counts = [("train", int(CONFIG["data"]["train_scenes"])), ("validation", int(CONFIG["data"]["validation_scenes"]))]
    configured_total = sum(value for _name, value in counts)
    if args.limit > 0 and int(args.limit) < configured_total:
        smoke_validation = min(4, max(1, int(args.limit) // 4))
        counts = [("train", max(1, int(args.limit) - smoke_validation)), ("validation", smoke_validation)]
    total = sum(value for _name, value in counts)
    records = []
    global_index = 0
    for split, count in counts:
        for _local in range(count):
            if global_index >= total:
                break
            records.append(generate_scene(global_index, split, package)); global_index += 1
            if global_index == 1 or global_index % 25 == 0 or global_index == total:
                print(json.dumps({"stage": "generate", "completed": global_index, "total": total}), flush=True)
        if global_index >= total:
            break
    manifest = {
        "status": "complete" if total == configured_total else "smoke_partial",
        "experiment_id": CONFIG["experiment_id"], "config_sha256": config_hash,
        "canvas_size": int(CONFIG["data"]["canvas_size"]), "supersample_factor": int(CONFIG["data"]["label_supersample_factor"]),
        "records": records,
        "counts": {split: sum(record["split"] == split for record in records) for split, _count in counts},
        "group_overlap_count": 0,
        "training_uses_real_pixels": False,
    }
    atomic_json(package / "manifest.json", manifest)
    render_preview(package, records)
    print(json.dumps({"status": manifest["status"], "records": len(records), "package": str(package)}), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

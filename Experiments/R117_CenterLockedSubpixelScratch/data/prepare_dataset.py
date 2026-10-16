"""Build 5,512 pure-synthetic scenes with true 8x-rendered translated labels."""

from __future__ import annotations

import argparse
from concurrent.futures import ProcessPoolExecutor, as_completed
import hashlib
import json
import math
from pathlib import Path
import sys

import cv2
import numpy as np


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
CONFIG_PATH = ROOT / "config" / "experiment.json"
CONFIG = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
from data.geometry import analytic_texture, draw_mask, translate_high


def atomic_json(path: Path, payload) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2, allow_nan=False), encoding="utf-8")
    temporary.replace(path)


def choose_role(rng: np.random.Generator) -> str:
    weights = CONFIG["data"]["role_weights"]
    names = list(weights)
    values = np.asarray([weights[name] for name in names], np.float64)
    return str(rng.choice(names, p=values / values.sum()))


def photometry_high(image: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    cfg = CONFIG["data"]["target"]
    gamma = float(rng.uniform(*cfg["shared_gamma"]))
    contrast = float(rng.uniform(*cfg["shared_contrast"]))
    amplitude = float(rng.uniform(*cfg["shared_illumination_amplitude"]))
    result = np.power(np.clip(image, 0, 1), gamma).astype(np.float32)
    midpoint = float(np.median(result))
    result = midpoint + contrast * (result - midpoint)
    if amplitude > 0:
        yy, xx = np.mgrid[0:image.shape[0], 0:image.shape[1]].astype(np.float32)
        xx = (xx + 0.5) / image.shape[1] - 0.5
        yy = (yy + 0.5) / image.shape[0] - 0.5
        angle = float(rng.uniform(0, 2 * math.pi))
        result *= 1.0 + 2.0 * amplitude * (math.cos(angle) * xx + math.sin(angle) * yy)
    return np.clip(result, 0, 1).astype(np.float32)


def down(value: np.ndarray, size: int) -> np.ndarray:
    return cv2.resize(value.astype(np.float32), (size, size), interpolation=cv2.INTER_AREA)


def save_array(package: Path, relative: str, value: np.ndarray) -> None:
    path = package / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    np.save(path, value, allow_pickle=False)


def generate_scene(scene_index: int, split: str, package: Path) -> dict:
    data = CONFIG["data"]
    seed = int(data["seed"]) + scene_index * 104729 + (0 if split == "train" else 1_000_000_007)
    rng = np.random.default_rng(seed)
    size, factor = int(data["canvas_size"]), int(data["label_supersample_factor"])
    high = size * factor
    role = choose_role(rng)
    family = "flat_negative" if role == "flat_negative" else str(rng.choice(data["families"]))
    pair_rng = np.random.default_rng(int(CONFIG["seed"]) * 1000003 + scene_index * 10007 + 17 * 104729)
    dx = float(pair_rng.uniform(*data["translation_range_px"]))
    dy = float(pair_rng.uniform(*data["translation_range_px"]))
    if role == "flat_negative":
        yy, xx = np.mgrid[0:high, 0:high].astype(np.float32)
        xx = (xx + 0.5) / high - 0.5
        yy = (yy + 0.5) / high - 0.5
        target_high = np.clip(float(rng.uniform(0.12, 0.88)) + rng.uniform(-0.10, 0.10) * xx + rng.uniform(-0.10, 0.10) * yy, 0.03, 0.97)
        mask_high = np.zeros((high, high), np.float32)
        sdf_high = np.full((high, high), -32.0 * factor, np.float32)
        width, polarity = 1.0, 1.0
    else:
        high_mask_u8 = draw_mask(size, factor, family, rng)
        binary = (high_mask_u8 >= 128).astype(np.uint8)
        inside = cv2.distanceTransform(binary, cv2.DIST_L2, cv2.DIST_MASK_5)
        outside = cv2.distanceTransform(1 - binary, cv2.DIST_L2, cv2.DIST_MASK_5)
        sdf_high = inside - outside
        width = float(rng.uniform(*data["target"]["transition_width_px"]))
        polarity = 1.0 if rng.random() < 0.5 else -1.0
        low = float(rng.uniform(0.10, 0.42))
        contrast = float(rng.uniform(*data["target"]["contrast"]))
        high_value = float(np.clip(low + polarity * contrast, 0.03, 0.97))
        probability = 1.0 / (1.0 + np.exp(-np.clip(sdf_high / (width * factor), -40, 40)))
        target_high = low + (high_value - low) * probability
        mask_high = high_mask_u8.astype(np.float32) / 255.0
        if role == "textured_edge":
            texture = analytic_texture(size, rng)
            texture_high = cv2.resize(texture, (high, high), interpolation=cv2.INTER_CUBIC)
            modulation = (0.20 + 0.80 * mask_high) if rng.random() < 0.5 else (1.0 - 0.75 * mask_high)
            target_high += float(rng.uniform(*data["target"]["texture_amplitude"])) * texture_high * modulation
        target_high = photometry_high(target_high, rng)
    shifted_target_high = translate_high(target_high, dx, dy, factor, cv2.INTER_LINEAR)
    shifted_mask_high = translate_high(mask_high, dx, dy, factor, cv2.INTER_LINEAR)
    shifted_sdf_high = translate_high(sdf_high, dx, dy, factor, cv2.INTER_LINEAR)
    target_a, target_b = down(target_high, size), down(shifted_target_high, size)
    mask_a, mask_b = down(mask_high, size), down(shifted_mask_high, size)
    sdf_a, sdf_b = down(sdf_high / factor, size), down(shifted_sdf_high / factor, size)
    mask2_a, mask2_b = down(mask_high, size * 2), down(shifted_mask_high, size * 2)
    sdf2_a, sdf2_b = down(sdf_high / factor, size * 2), down(shifted_sdf_high / factor, size * 2)
    foreground, background = target_a[mask_a >= 0.5], target_a[mask_a < 0.5]
    midpoint = float(0.5 * (foreground.mean() + background.mean())) if foreground.size and background.size else float(np.median(target_a))
    stem = f"{scene_index:06d}"
    relatives = {
        "target_a": f"targets_a/{stem}.npy", "target_b": f"targets_b/{stem}.npy",
        "mask_a": f"masks_a/{stem}.npy", "mask_b": f"masks_b/{stem}.npy",
        "sdf_a": f"sdf_a/{stem}.npy", "sdf_b": f"sdf_b/{stem}.npy",
        "mask2_a": f"masks_2x_a/{stem}.npy", "mask2_b": f"masks_2x_b/{stem}.npy",
        "sdf2_a": f"sdf_2x_a/{stem}.npy", "sdf2_b": f"sdf_2x_b/{stem}.npy",
    }
    save_array(package, relatives["target_a"], np.rint(np.clip(target_a, 0, 1) * 255).astype(np.uint8))
    save_array(package, relatives["target_b"], np.rint(np.clip(target_b, 0, 1) * 255).astype(np.uint8))
    save_array(package, relatives["mask_a"], np.rint(np.clip(mask_a, 0, 1) * 255).astype(np.uint8))
    save_array(package, relatives["mask_b"], np.rint(np.clip(mask_b, 0, 1) * 255).astype(np.uint8))
    save_array(package, relatives["sdf_a"], sdf_a.astype(np.float16))
    save_array(package, relatives["sdf_b"], sdf_b.astype(np.float16))
    save_array(package, relatives["mask2_a"], np.rint(np.clip(mask2_a, 0, 1) * 255).astype(np.uint8))
    save_array(package, relatives["mask2_b"], np.rint(np.clip(mask2_b, 0, 1) * 255).astype(np.uint8))
    save_array(package, relatives["sdf2_a"], sdf2_a.astype(np.float16))
    save_array(package, relatives["sdf2_b"], sdf2_b.astype(np.float16))
    return {
        "scene_index": scene_index, "split": split, "role": role, "family": family,
        **relatives, "target_width_px": width, "midpoint": midpoint, "polarity": polarity,
        "pair_dx_px": dx, "pair_dy_px": dy, "seed": seed,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--workers", type=int, default=6)
    args = parser.parse_args()
    package = ROOT / CONFIG["data"]["package_root"]
    package.mkdir(parents=True, exist_ok=True)
    configured = int(CONFIG["data"]["train_scenes"]) + int(CONFIG["data"]["validation_scenes"])
    total = configured if args.limit <= 0 else min(int(args.limit), configured)
    validation = int(CONFIG["data"]["validation_scenes"]) if total == configured else min(32, max(8, total // 4))
    train = total - validation
    records = []
    jobs = [(index, "train" if index < train else "validation", package) for index in range(total)]
    if int(args.workers) <= 1:
        iterator = (generate_scene(*job) for job in jobs)
        for completed, record in enumerate(iterator, 1):
            records.append(record)
            if completed == 1 or completed % 25 == 0 or completed == total:
                print(json.dumps({"stage": "generate", "completed": completed, "total": total}), flush=True)
    else:
        with ProcessPoolExecutor(max_workers=int(args.workers)) as pool:
            futures = [pool.submit(generate_scene, *job) for job in jobs]
            for completed, future in enumerate(as_completed(futures), 1):
                records.append(future.result())
                if completed == 1 or completed % 25 == 0 or completed == total:
                    print(json.dumps({"stage": "generate", "completed": completed, "total": total}), flush=True)
    records.sort(key=lambda row: int(row["scene_index"]))
    manifest = {
        "status": "complete" if total == configured else "smoke_partial",
        "experiment_id": CONFIG["experiment_id"],
        "config_sha256": hashlib.sha256(CONFIG_PATH.read_bytes()).hexdigest(),
        "records": records, "counts": {"train": train, "validation": validation},
        "supersample_factor": int(CONFIG["data"]["label_supersample_factor"]),
        "translation_rendered_before_downsampling": True,
        "group_overlap_count": 0, "training_uses_real_pixels": False,
    }
    atomic_json(package / "manifest.json", manifest)
    print(json.dumps({"status": manifest["status"], "records": total, "package": str(package)}), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

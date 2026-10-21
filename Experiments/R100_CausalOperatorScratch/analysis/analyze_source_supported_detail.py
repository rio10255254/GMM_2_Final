"""Measure when stored observations contain recoverable material detail."""
from __future__ import annotations

import collections
import importlib.util
import json
import sys
from pathlib import Path

import cv2
import numpy as np


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "reports" / "source_supported_detail_audit.json"


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


TRAINER = load_module("r100_detail_audit_trainer", ROOT / "training" / "train_r100.py")
DESIGN = TRAINER.DESIGN


def highpass(image: np.ndarray) -> np.ndarray:
    return image - cv2.GaussianBlur(image, (0, 0), 1.2, borderType=cv2.BORDER_REFLECT_101)


def metrics(source_u8: np.ndarray, target_u8: np.ndarray, mask_u8: np.ndarray) -> dict[str, float]:
    source = cv2.resize(source_u8, (384, 384), interpolation=cv2.INTER_AREA).astype(np.float32) / 255.0
    target = cv2.resize(target_u8, (384, 384), interpolation=cv2.INTER_AREA).astype(np.float32) / 255.0
    mask = cv2.resize(mask_u8, (384, 384), interpolation=cv2.INTER_AREA) >= 128
    inside = cv2.distanceTransform(mask.astype(np.uint8), cv2.DIST_L2, 3)
    outside = cv2.distanceTransform((~mask).astype(np.uint8), cv2.DIST_L2, 3)
    material = (inside > 2.0) | (outside > 2.0)
    source_fine, target_fine = highpass(source), highpass(target)
    s, t = source_fine[material], target_fine[material]
    s = s - np.mean(s)
    t = t - np.mean(t)
    covariance = float(np.mean(s * t))
    source_energy = float(np.mean(s * s))
    target_energy = float(np.mean(t * t))
    scale = covariance / max(source_energy, 1e-10)
    correlation = covariance / max(np.sqrt(source_energy * target_energy), 1e-10)
    return {
        "correlation": correlation,
        "optimal_source_detail_scale": scale,
        "positive_sharpen_gain": max(scale - 1.0, 0.0),
        "source_fine_rms_gray": float(np.sqrt(source_energy) * 255.0),
        "target_fine_rms_gray": float(np.sqrt(target_energy) * 255.0),
        "source_supported_sharpen": float(correlation > 0.45 and scale > 1.05),
        "source_supported_denoise": float(correlation > 0.30 and scale < 0.90),
    }


def summarize(rows: list[dict]) -> dict:
    result = {"count": len(rows)}
    for key in ("correlation", "optimal_source_detail_scale", "positive_sharpen_gain", "source_fine_rms_gray", "target_fine_rms_gray"):
        values = np.asarray([row[key] for row in rows], np.float64)
        result[key] = {
            "p10": float(np.percentile(values, 10)),
            "median": float(np.median(values)),
            "p90": float(np.percentile(values, 90)),
        }
    result["source_supported_sharpen_fraction"] = float(np.mean([row["source_supported_sharpen"] for row in rows]))
    result["source_supported_denoise_fraction"] = float(np.mean([row["source_supported_denoise"] for row in rows]))
    return result


def main() -> int:
    package, manifest, audit = TRAINER.preflight("smoke")
    if not audit.get("passed"):
        raise RuntimeError("Locked data audit failed")
    by_family: dict[str, list[tuple[dict, dict]]] = collections.defaultdict(list)
    for record in manifest["records"]:
        if record["split"] != "train":
            continue
        for observation in record["observations"]:
            by_family[observation["degradation_family"]].append((record, observation))
    rng = np.random.default_rng(1000053)
    sampled: dict[str, list[tuple[dict, dict]]] = {}
    for family, candidates in by_family.items():
        selected = rng.choice(len(candidates), size=min(48, len(candidates)), replace=False)
        sampled[family] = [candidates[int(index)] for index in selected]

    rows: list[dict] = []
    for family, pairs in sampled.items():
        for record, observation in pairs:
            source = np.load(package / observation["source"], mmap_mode="r", allow_pickle=False)
            target = np.load(package / record["target"], mmap_mode="r", allow_pickle=False)
            mask = np.load(package / record["mask"], mmap_mode="r", allow_pickle=False)
            dx, dy = float(observation["motion_dx_px"]), float(observation["motion_dy_px"])
            if abs(dx) + abs(dy) > 0:
                target = TRAINER.warp_u8(target, dx, dy, cv2.INTER_LANCZOS4)
                mask = TRAINER.warp_u8(mask, dx, dy, cv2.INTER_LINEAR)
            row = metrics(np.asarray(source), np.asarray(target), np.asarray(mask))
            row.update(
                family=family,
                role=record["role"],
                scene_index=int(record["scene_index"]),
                observation=int(observation["observation"]),
                blur_sigma=float(max(observation["degradation"].get("blur_sigma_x", 0.0), observation["degradation"].get("blur_sigma_y", 0.0))),
                read_noise_sigma=float(observation["degradation"].get("read_noise_sigma", 0.0)),
                poisson_peak=float(observation["degradation"].get("poisson_peak", 1e9)),
            )
            rows.append(row)

    family_summary = {family: summarize([row for row in rows if row["family"] == family]) for family in sorted(sampled)}
    role_summary = {role: summarize([row for row in rows if row["role"] == role]) for role in sorted({row["role"] for row in rows})}
    report = {
        "experiment_id": DESIGN["experiment_id"],
        "purpose": "Determine which procedural observations genuinely support source-based sharpening rather than denoising.",
        "sample_count": len(rows),
        "sample_per_family": 48,
        "definition": {"sharpen": "fine-band correlation > 0.45 and optimal source-detail scale > 1.05", "denoise": "correlation > 0.30 and optimal scale < 0.90"},
        "overall": summarize(rows),
        "by_family": family_summary,
        "by_role": role_summary,
        "rows": rows,
    }
    OUTPUT.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({"sample_count": len(rows), "overall": report["overall"], "by_family": family_summary}, indent=2), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

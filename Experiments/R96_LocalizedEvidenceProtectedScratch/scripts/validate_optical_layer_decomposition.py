"""Validate additive shape/material decomposition of procedural optical error."""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
from collections import defaultdict
from pathlib import Path
import sys
from typing import Any

import cv2
import numpy as np
PROJECT_ROOT = Path(__file__).resolve().parents[3]


ROOT = Path(__file__).resolve().parents[1]
SOURCE = Path(str(PROJECT_ROOT / 'Experiments/R93_RecoverableDetailSeparatedScratch/data/r93_formal'))


def load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def warp(array: np.ndarray, dx: float, dy: float, interpolation: int) -> np.ndarray:
    if abs(dx) + abs(dy) <= 1e-12:
        return np.asarray(array)
    matrix = np.asarray([[1.0, 0.0, dx], [0.0, 1.0, dy]], np.float32)
    return cv2.warpAffine(
        np.asarray(array), matrix, (array.shape[1], array.shape[0]),
        flags=interpolation, borderMode=cv2.BORDER_REFLECT_101,
    )


def summarize(values: list[float]) -> dict[str, float]:
    array = np.asarray(values, np.float64)
    return {
        "mean": float(array.mean()) if array.size else 0.0,
        "median": float(np.median(array)) if array.size else 0.0,
        "p95": float(np.percentile(array, 95)) if array.size else 0.0,
        "max": float(array.max()) if array.size else 0.0,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--scenes-per-role", type=int, default=2)
    parser.add_argument("--report", default=str(ROOT / "reports" / "optical_layer_decomposition_validation.json"))
    args = parser.parse_args()
    replay = load("r96_layer_decomposition", ROOT / "training" / "causal_stage_replay.py")
    manifest = json.loads((SOURCE / "manifest.json").read_text(encoding="utf-8"))
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in manifest["records"]:
        grouped[str(record["role"])].append(record)

    records: list[dict[str, Any]] = []
    for role, rows in sorted(grouped.items()):
        count = min(int(args.scenes_per_role), len(rows))
        for index in np.linspace(0, len(rows) - 1, num=count, dtype=np.int64):
            record = rows[int(index)]
            target_base = np.load(SOURCE / record["target"], mmap_mode="r", allow_pickle=False)
            mask_base = np.load(SOURCE / record["mask"], mmap_mode="r", allow_pickle=False)
            for observation in record["observations"]:
                dx, dy = float(observation["motion_dx_px"]), float(observation["motion_dy_px"])
                target = warp(target_base, dx, dy, cv2.INTER_LANCZOS4)
                mask = warp(mask_base, dx, dy, cv2.INTER_LINEAR)
                layers = replay.decompose_optical_layers(
                    target, mask, record["texture"], observation["degradation"],
                    int(observation["degradation_parameter_seed"]),
                )
                patch = min(384, target.shape[0])
                core = min(128, patch // 2)
                halo = (patch - core) // 2
                maximum = target.shape[0] - patch
                rng = np.random.default_rng(int(record["scene_index"]) * 1009 + int(observation["observation"]))
                y0 = int(rng.integers(0, maximum + 1) // 8 * 8) if maximum > 0 else 0
                x0 = int(rng.integers(0, maximum + 1) // 8 * 8) if maximum > 0 else 0
                hidden = replay.replay_causal_stages(
                    target,
                    mask,
                    observation["degradation"],
                    int(observation["degradation_parameter_seed"]),
                ).hidden_parameters
                patch_layers = replay.decompose_optical_layers(
                    target[y0 : y0 + patch, x0 : x0 + patch],
                    mask[y0 : y0 + patch, x0 : x0 + patch],
                    record["texture"],
                    observation["degradation"],
                    int(observation["degradation_parameter_seed"]),
                    canvas_shape=target.shape,
                    crop_yx=(y0, x0),
                    hidden_parameters=hidden,
                )
                core_slice = np.s_[halo : halo + core, halo : halo + core]
                full_slice = np.s_[y0 + halo : y0 + halo + core, x0 + halo : x0 + halo + core]
                boundary_patch_error = float(np.max(np.abs(
                    patch_layers.boundary_target[core_slice] - layers.boundary_target[full_slice]
                )))
                texture_patch_error = float(np.max(np.abs(
                    patch_layers.texture_target[core_slice] - layers.texture_target[full_slice]
                )))
                contrast_patch_error = float(np.max(np.abs(
                    patch_layers.local_contrast_target[core_slice] - layers.local_contrast_target[full_slice]
                )))
                boundary_energy = float(np.mean(np.abs(layers.boundary_target)) * 255.0)
                texture_energy = float(np.mean(np.abs(layers.texture_target)) * 255.0)
                contrast_energy = float(np.mean(np.abs(layers.local_contrast_target)) * 255.0)
                total_energy = float(np.mean(np.abs(
                    layers.local_contrast_target + layers.boundary_target + layers.texture_target
                )) * 255.0)
                full_target = target.astype(np.float32) / 255.0
                optical = layers.shape_optical + layers.texture_optical
                target_recomposition_error = float(np.max(np.abs(
                    optical + layers.local_contrast_target + layers.boundary_target + layers.texture_target
                    - full_target
                )))
                records.append({
                    "role": role,
                    "scene_id": record["scene_id"],
                    "observation": int(observation["observation"]),
                    "recomposition_max_abs_float": layers.recomposition_max_abs,
                    "patch_core_boundary_max_abs_float": boundary_patch_error,
                    "patch_core_texture_max_abs_float": texture_patch_error,
                    "patch_core_local_contrast_max_abs_float": contrast_patch_error,
                    "target_recomposition_max_abs_float": target_recomposition_error,
                    "boundary_target_mean_abs_gray": boundary_energy,
                    "texture_target_mean_abs_gray": texture_energy,
                    "local_contrast_target_mean_abs_gray": contrast_energy,
                    "total_optical_target_mean_abs_gray": total_energy,
                    "texture_share": texture_energy / max(boundary_energy + texture_energy + contrast_energy, 1e-8),
                    "local_contrast_share": contrast_energy / max(boundary_energy + texture_energy + contrast_energy, 1e-8),
                })

    by_role: dict[str, dict[str, Any]] = {}
    for role in sorted(grouped):
        selected = [row for row in records if row["role"] == role]
        by_role[role] = {
            name: summarize([float(row[name]) for row in selected])
            for name in (
                "boundary_target_mean_abs_gray", "texture_target_mean_abs_gray",
                "local_contrast_target_mean_abs_gray", "total_optical_target_mean_abs_gray",
                "texture_share", "local_contrast_share"
            )
        }
    report = {
        "analysis_id": "R96_OPTICAL_LAYER_DECOMPOSITION_V1",
        "tested_views": len(records),
        "maximum_recomposition_abs_float": max((row["recomposition_max_abs_float"] for row in records), default=0.0),
        "additive_decomposition_is_numerically_exact": max((row["recomposition_max_abs_float"] for row in records), default=0.0) < 1e-5,
        "patch_core_boundary_max_abs_float": max((row["patch_core_boundary_max_abs_float"] for row in records), default=0.0),
        "patch_core_texture_max_abs_float": max((row["patch_core_texture_max_abs_float"] for row in records), default=0.0),
        "patch_core_local_contrast_max_abs_float": max((row["patch_core_local_contrast_max_abs_float"] for row in records), default=0.0),
        "target_recomposition_max_abs_float": max((row["target_recomposition_max_abs_float"] for row in records), default=0.0),
        "roles": by_role,
        "records": records,
    }
    output = Path(args.report)
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(output.suffix + ".tmp")
    temporary.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    os.replace(temporary, output)
    print(json.dumps({
        "tested_views": report["tested_views"],
        "maximum_recomposition_abs_float": report["maximum_recomposition_abs_float"],
        "additive_decomposition_is_numerically_exact": report["additive_decomposition_is_numerically_exact"],
        "patch_core_boundary_max_abs_float": report["patch_core_boundary_max_abs_float"],
        "patch_core_texture_max_abs_float": report["patch_core_texture_max_abs_float"],
        "patch_core_local_contrast_max_abs_float": report["patch_core_local_contrast_max_abs_float"],
        "target_recomposition_max_abs_float": report["target_recomposition_max_abs_float"],
        "roles": report["roles"],
    }, indent=2))
    patch_parity = max(
        report["patch_core_boundary_max_abs_float"],
        report["patch_core_texture_max_abs_float"],
        report["patch_core_local_contrast_max_abs_float"],
    ) < (0.02 / 255.0)
    target_exact = report["target_recomposition_max_abs_float"] < 1e-5
    return 0 if report["additive_decomposition_is_numerically_exact"] and patch_parity and target_exact else 1


if __name__ == "__main__":
    raise SystemExit(main())


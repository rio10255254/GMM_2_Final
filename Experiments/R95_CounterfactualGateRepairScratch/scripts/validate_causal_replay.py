"""Verify causal stage replay against stored B without writing data payloads."""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
from collections import defaultdict
from pathlib import Path
import sys
from typing import Any

import cv2
import numpy as np


ROOT = Path(__file__).resolve().parents[1]
SOURCE = Path(r"D:\GMM_2_Final\Experiments\R93_RecoverableDetailSeparatedScratch\data\r93_formal")


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


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--scenes-per-role", type=int, default=2)
    parser.add_argument("--report", default=str(ROOT / "reports" / "causal_replay_validation.json"))
    args = parser.parse_args()
    replay = load("r95_causal_replay_validation", ROOT / "training" / "causal_stage_replay.py")
    manifest = json.loads((SOURCE / "manifest.json").read_text(encoding="utf-8"))
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in manifest["records"]:
        grouped[str(record["role"])].append(record)

    records: list[dict[str, Any]] = []
    for role, rows in sorted(grouped.items()):
        count = min(int(args.scenes_per_role), len(rows))
        indices = np.linspace(0, len(rows) - 1, num=count, dtype=np.int64)
        for index in indices:
            record = rows[int(index)]
            target_base = np.load(SOURCE / record["target"], mmap_mode="r", allow_pickle=False)
            mask_base = np.load(SOURCE / record["mask"], mmap_mode="r", allow_pickle=False)
            for observation in record["observations"]:
                dx, dy = float(observation["motion_dx_px"]), float(observation["motion_dy_px"])
                target = warp(target_base, dx, dy, cv2.INTER_LANCZOS4)
                mask = warp(mask_base, dx, dy, cv2.INTER_LINEAR)
                result = replay.replay_causal_stages(
                    target, mask, observation["degradation"], int(observation["degradation_parameter_seed"])
                )
                stored = np.load(SOURCE / observation["noise_free_source"], mmap_mode="r", allow_pickle=False)
                difference = np.abs(result.replayed_noise_free_u8.astype(np.int16) - np.asarray(stored).astype(np.int16))
                inverse = replay.invert_radiometry(
                    np.asarray(stored),
                    observation["degradation"],
                    result.hidden_parameters,
                    canvas_shape=target.shape,
                )
                inverse_difference = np.abs(inverse - result.optical_source) * 255.0
                records.append({
                    "role": role,
                    "scene_id": record["scene_id"],
                    "observation": int(observation["observation"]),
                    "family": observation["degradation_family"],
                    "max_abs_gray": int(difference.max()),
                    "mean_abs_gray": float(difference.mean()),
                    "mismatch_pixels": int(np.count_nonzero(difference)),
                    "inverse_mean_abs_gray": float(inverse_difference.mean()),
                    "inverse_p95_abs_gray": float(np.percentile(inverse_difference, 95)),
                    "inverse_max_abs_gray": float(inverse_difference.max()),
                    "optical_min": float(result.optical_source.min()),
                    "optical_max": float(result.optical_source.max()),
                    "boundary_support_mean": float(result.boundary_support.mean()),
                })

    inverse_mean_values = [row["inverse_mean_abs_gray"] for row in records]
    inverse_p95_values = [row["inverse_p95_abs_gray"] for row in records]
    report = {
        "analysis_id": "R95_CAUSAL_STAGE_REPLAY_VALIDATION_V1",
        "source_manifest_sha256": sha256(SOURCE / "manifest.json"),
        "tested_views": len(records),
        "exact_view_count": sum(row["mismatch_pixels"] == 0 for row in records),
        "all_replayed_noise_free_views_are_pixel_exact": all(row["mismatch_pixels"] == 0 for row in records),
        "maximum_abs_gray": max((row["max_abs_gray"] for row in records), default=0),
        "inverse_mean_abs_gray": float(np.mean(inverse_mean_values)) if records else 0.0,
        "inverse_p95_abs_gray": float(np.percentile(inverse_p95_values, 95)) if records else 0.0,
        "inverse_max_abs_gray": max((row["inverse_max_abs_gray"] for row in records), default=0.0),
        "records": records,
    }
    output = Path(args.report)
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(output.suffix + ".tmp")
    temporary.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    os.replace(temporary, output)
    print(json.dumps({key: report[key] for key in (
        "tested_views", "exact_view_count", "all_replayed_noise_free_views_are_pixel_exact", "maximum_abs_gray",
        "inverse_mean_abs_gray", "inverse_p95_abs_gray", "inverse_max_abs_gray"
    )}, indent=2))
    return 0 if report["all_replayed_noise_free_views_are_pixel_exact"] else 1


if __name__ == "__main__":
    raise SystemExit(main())


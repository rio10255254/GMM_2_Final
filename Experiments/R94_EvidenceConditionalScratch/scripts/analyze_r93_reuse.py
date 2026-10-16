"""Read-only analysis of R93 arrays under the proposed R94 targets."""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
from collections import defaultdict
from pathlib import Path
import sys

import numpy as np
import torch
import cv2


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


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def quantiles(values: list[float]) -> dict[str, float]:
    array = np.asarray(values, dtype=np.float64)
    return {name: float(np.percentile(array, p)) for name, p in (("min", 0), ("p10", 10), ("median", 50), ("p90", 90), ("max", 100))}


def warp_u8(array: np.ndarray, dx: float, dy: float, interpolation: int) -> np.ndarray:
    if abs(dx) + abs(dy) <= 1e-12:
        return np.asarray(array)
    matrix = np.asarray([[1.0, 0.0, dx], [0.0, 1.0, dy]], dtype=np.float32)
    return cv2.warpAffine(
        np.asarray(array), matrix, (array.shape[1], array.shape[0]),
        flags=interpolation, borderMode=cv2.BORDER_REFLECT_101,
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--scenes-per-role", type=int, default=8)
    parser.add_argument("--crop", type=int, default=192)
    parser.add_argument("--report", default=str(ROOT / "reports" / "r93_reuse_analysis.json"))
    args = parser.parse_args()
    torch.set_num_threads(2)
    targets = load("r94_reuse_targets", ROOT / "training" / "counterfactual_targets.py")
    manifest = json.loads((SOURCE / "manifest.json").read_text(encoding="utf-8"))
    expected_hash = json.loads((ROOT / "config" / "experiment_design.json").read_text(encoding="utf-8"))["data"]["source_content_sha256"]
    grouped: dict[str, list[dict]] = defaultdict(list)
    for record in manifest["records"]:
        if record["split"] == "train":
            grouped[record["role"]].append(record)

    metrics: dict[str, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
    selected = []
    for role, records in sorted(grouped.items()):
        take = min(int(args.scenes_per_role), len(records))
        indices = np.linspace(0, len(records) - 1, num=take, dtype=np.int64) if take else np.empty(0, dtype=np.int64)
        for local, record_index in enumerate(indices):
            record = records[int(record_index)]
            observation = record["observations"][(local * 3 + int(record["scene_index"])) % 4]
            t_base = np.load(SOURCE / record["target"], mmap_mode="r")
            b = np.load(SOURCE / observation["noise_free_source"], mmap_mode="r")
            s = np.load(SOURCE / observation["source"], mmap_mode="r")
            m_base = np.load(SOURCE / record["mask"], mmap_mode="r")
            dx = float(observation["motion_dx_px"])
            dy = float(observation["motion_dy_px"])
            t = warp_u8(t_base, dx, dy, cv2.INTER_LANCZOS4)
            m = warp_u8(m_base, dx, dy, cv2.INTER_LINEAR)
            maximum = t.shape[0] - args.crop
            rng = np.random.default_rng(940041 + int(record["scene_index"]) * 97)
            y = int(rng.integers(0, maximum + 1) // 8 * 8)
            x = int(rng.integers(0, maximum + 1) // 8 * 8)
            tensor = lambda a: torch.from_numpy(np.asarray(a[y : y + args.crop, x : x + args.crop]).copy()).float()[None, None] / 255.0
            # This read-only reuse analysis validates generic target algebra.
            # Exact cause-based replay is validated separately and will feed O
            # in the formal R94 dataset overlay.
            support = targets.boundary_support_from_mask(tensor(m), radius=7)
            views = targets.build_counterfactual_views(
                tensor(t), tensor(b), tensor(s), boundary_support=support,
                optical_source=tensor(b),
            )
            for view_name, view in views.items():
                row = metrics[f"{role}/{view_name}"]
                row["need_radiometry_mean"].append(float(view.need_radiometry.mean()))
                row["need_noise_mean"].append(float(view.need_noise.mean()))
                row["need_boundary_mean"].append(float(view.need_boundary.mean()))
                row["boundary_evidence_mean"].append(float(view.boundary_evidence.mean()))
                row["need_texture_mean"].append(float(view.need_texture.mean()))
                row["texture_recoverability_mean"].append(float(view.texture_recoverability.mean()))
                row["effective_boundary_gray"].append(float(view.boundary_effective.abs().mean() * 255.0))
                row["effective_texture_gray"].append(float(view.texture_effective.abs().mean() * 255.0))
                row["effective_restoration_gray"].append(float(view.restoration_effective.abs().mean() * 255.0))
                row["supervised_change_gray"].append(float((view.target - view.source).abs().mean() * 255.0))
                recomposed = (view.source + view.radiometry_effective + view.nuisance_effective + view.restoration_effective).clamp(0.0, 1.0)
                row["recomposition_max_gray"].append(float((recomposed - view.target).abs().max() * 255.0))
            selected.append({"scene_id": record["scene_id"], "role": role, "observation": int(observation["observation"]), "crop": [y, x, args.crop]})

    summary = {group: {name: quantiles(values) for name, values in rows.items()} for group, rows in metrics.items()}
    all_recomposition = [values for rows in metrics.values() for name, values in rows.items() if name == "recomposition_max_gray"]
    max_recomposition = max((max(values) for values in all_recomposition), default=0.0)
    report = {
        "analysis_id": "R94_R93_REUSE_TARGET_ANALYSIS_V1",
        "read_only": True,
        "source_manifest_content_sha256": manifest["content_sha256"],
        "expected_source_content_sha256": expected_hash,
        "source_hash_matches_design": manifest["content_sha256"] == expected_hash,
        "manifest_file_sha256": sha256_file(SOURCE / "manifest.json"),
        "scene_count": manifest["scene_count"],
        "observation_count": manifest["total_observations"],
        "sampled_scene_count": len(selected),
        "maximum_target_recomposition_error_gray": max_recomposition,
        "groups": summary,
        "selection": selected,
    }
    output = Path(args.report)
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(output.suffix + ".tmp")
    temporary.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    os.replace(temporary, output)
    print(json.dumps({key: report[key] for key in ("source_hash_matches_design", "sampled_scene_count", "maximum_target_recomposition_error_gray")}, indent=2))
    return 0 if report["source_hash_matches_design"] and max_recomposition < 1e-5 else 1


if __name__ == "__main__":
    raise SystemExit(main())

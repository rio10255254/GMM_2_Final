"""Zero-shot eligibility probe using already-developmental procedural evidence."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import cv2
import numpy as np
import pandas as pd
import torch


ROOT = Path(__file__).resolve().parents[1]
R82 = Path(r"D:\GMM_2_Final\Experiments\R82_R39R40CrossSceneGeneralizationBenchmark")
R84 = Path(r"D:\GMM_2_Final\Experiments\R84_R79TileStableRootRepair")
HOLDOUT = R84 / "data" / "r84_locked_holdout_tile_stable_confirmation"
OUTPUT = ROOT / "results" / "zero_shot_probe"
DEVICE = "cuda:0"


def load_module():
    path = ROOT / "inference" / "infer_r86.py"
    spec = importlib.util.spec_from_file_location("r86_zero_shot_inference", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def metrics(reference: np.ndarray, prediction: np.ndarray) -> tuple[float, float]:
    ref = reference.astype(np.float32)
    pred = prediction.astype(np.float32)
    gx_ref = cv2.Sobel(ref, cv2.CV_32F, 1, 0, ksize=3)
    gy_ref = cv2.Sobel(ref, cv2.CV_32F, 0, 1, ksize=3)
    gx_pred = cv2.Sobel(pred, cv2.CV_32F, 1, 0, ksize=3)
    gy_pred = cv2.Sobel(pred, cv2.CV_32F, 0, 1, ksize=3)
    return float(np.mean(np.abs(ref - pred))), float(np.mean(np.abs(cv2.magnitude(gx_ref, gy_ref) - cv2.magnitude(gx_pred, gy_pred))))


def infer_r79(module, model, image: np.ndarray) -> np.ndarray:
    canvas, original_shape = module.canonical_canvas(image)
    output = module._run(model, canvas, DEVICE)
    height, width = original_shape
    return np.clip(np.rint(output[:height, :width] * 255.0), 0, 255).astype(np.uint8)


def main() -> int:
    module = load_module()
    checkpoint = ROOT / "weights" / "seed" / "r79e23_parent.pth.tar"
    r79 = module.build_model(checkpoint, DEVICE, tile_stable=False, use_ema=True)[0]
    r86 = module.build_model(checkpoint, DEVICE, tile_stable=True, use_ema=True)[0]
    manifest = json.loads((HOLDOUT / "manifest.json").read_text(encoding="utf-8"))
    rows = []
    for index, pair in enumerate(manifest["pairs"], start=1):
        raw = module.read_gray(HOLDOUT / pair["package_src"])
        label = module.read_gray(HOLDOUT / pair["package_lbl"])
        outputs = {"R79": infer_r79(module, r79, raw), "R86": module.infer_canonical_full(r86, raw, DEVICE)}
        for method, output in outputs.items():
            mae, edge = metrics(label, output)
            rows.append({"pair_id": pair["pair_id"], "method": method, "mae": mae, "edge_mae": edge})
        if index % 64 == 0:
            print(f"zero-shot {index}/{len(manifest['pairs'])}", flush=True)
    table = pd.DataFrame(rows)
    summary = table.groupby("method", as_index=False).agg(median_mae=("mae", "median"), median_edge_mae=("edge_mae", "median"))

    config = json.loads((R82 / "config" / "experiment.json").read_text(encoding="utf-8"))
    raw_root = Path(config["real_fov"]["locked_raw_root"])
    sem_root = Path(config["sem_acm"]["raw_input_dir"])
    fixtures = [raw_root / "5x_0p5um" / "frame_0000.bmp", raw_root / "50x_0p5um" / "frame_0050.bmp", sem_root / "18.bmp"]
    tile_rows = []
    for source in fixtures:
        raw = module.read_gray(source)
        full = module.infer_canonical_full(r86, raw, DEVICE)
        tiled = module.infer_phase_locked_tiled(r86, raw, DEVICE)
        tile_rows.append({"sample": str(source), **module.difference_metrics(full, tiled)})
    tiles = pd.DataFrame(tile_rows)
    base = summary.loc[summary["method"] == "R79"].iloc[0]
    candidate = summary.loc[summary["method"] == "R86"].iloc[0]
    limits = json.loads((ROOT / "config" / "experiment.json").read_text(encoding="utf-8"))["zero_shot_eligibility"]
    decision = {
        "status": "complete",
        "training_updates_applied": False,
        "mae_ratio": float(candidate["median_mae"] / base["median_mae"]),
        "edge_ratio": float(candidate["median_edge_mae"] / base["median_edge_mae"]),
        "worst_tile_mean": float(tiles["mean_abs_gray"].max()),
        "worst_tile_p99": float(tiles["p99_abs_gray"].max()),
        "worst_tile_max": float(tiles["max_abs_gray"].max()),
    }
    decision["eligible"] = bool(
        decision["mae_ratio"] <= limits["procedural_median_mae_relative_to_R79_max"]
        and decision["edge_ratio"] <= limits["procedural_median_edge_relative_to_R79_max"]
        and decision["worst_tile_mean"] <= limits["tile_mean_max"]
        and decision["worst_tile_p99"] <= limits["tile_p99_max"]
        and decision["worst_tile_max"] <= limits["tile_max_max"]
    )
    OUTPUT.mkdir(parents=True, exist_ok=True)
    table.to_csv(OUTPUT / "metrics.csv", index=False)
    summary.to_csv(OUTPUT / "summary.csv", index=False)
    tiles.to_csv(OUTPUT / "tile_metrics.csv", index=False)
    (OUTPUT / "decision.json").write_text(json.dumps(decision, indent=2), encoding="utf-8")
    print(json.dumps(decision, indent=2), flush=True)
    return 0 if decision["eligible"] else 2


if __name__ == "__main__":
    raise SystemExit(main())

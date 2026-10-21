"""Development-only sweep to determine whether retraining is avoidable."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import cv2
import numpy as np
import pandas as pd
import torch


ROOT = Path(__file__).resolve().parents[1]
HOLDOUT = ROOT / "data" / "r84_locked_holdout_tile_stable_confirmation"
OUTPUT = ROOT / "results" / "shared_global_preconditioner_probe" / "strength_sweep"
DEVICE = "cuda:0"
GAMMAS = [0.0, 0.05, 0.10, 0.20, 0.30, 0.40, 0.50, 1.0]


def load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
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
    return (
        float(np.mean(np.abs(ref - pred))),
        float(np.mean(np.abs(cv2.magnitude(gx_ref, gy_ref) - cv2.magnitude(gx_pred, gy_pred)))),
    )


def main() -> int:
    inference = load(ROOT / "inference" / "infer_r84.py", "r84_inference_strength_sweep")
    model = inference.build_model(ROOT / "weights" / "selected" / "r84_tile_stable_model.pth.tar", DEVICE, tile_stable=True, use_ema=True)[0]
    manifest = json.loads((HOLDOUT / "manifest.json").read_text(encoding="utf-8"))
    records = []
    for index, pair in enumerate(manifest["pairs"], start=1):
        raw = inference.read_gray(HOLDOUT / pair["package_src"])
        label = inference.read_gray(HOLDOUT / pair["package_lbl"])
        canvas, original_shape = inference.canonical_canvas(raw)
        tensor = torch.from_numpy(canvas.astype(np.float32) / 255.0)[None, None].to(DEVICE)
        with torch.no_grad(), torch.cuda.amp.autocast(enabled=False):
            physics = model.physics_layer(tensor).float()
            for gamma in GAMMAS:
                conditioned = tensor + gamma * (physics - tensor)
                prediction = model(conditioned).float().clamp(0.0, 1.0)[0, 0]
                height, width = original_shape
                image = np.clip(np.rint(prediction[:height, :width].cpu().numpy() * 255.0), 0, 255).astype(np.uint8)
                mae, edge = metrics(label, image)
                records.append({"pair_id": pair["pair_id"], "gamma": gamma, "mae": mae, "edge_mae": edge})
        if index % 64 == 0:
            print(f"gamma sweep {index}/{len(manifest['pairs'])}", flush=True)
    frame = pd.DataFrame(records)
    summary = frame.groupby("gamma", as_index=False).agg(median_mae=("mae", "median"), median_edge_mae=("edge_mae", "median"))
    OUTPUT.mkdir(parents=True, exist_ok=True)
    frame.to_csv(OUTPUT / "per_pair.csv", index=False)
    summary.to_csv(OUTPUT / "summary.csv", index=False)
    print(summary.to_json(orient="records", indent=2), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

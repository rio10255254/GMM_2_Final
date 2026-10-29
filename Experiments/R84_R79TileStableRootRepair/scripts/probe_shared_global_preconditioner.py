"""Diagnose the minimal shared-canvas optical preconditioner repair after R84 closeout."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import cv2
import numpy as np
import pandas as pd
import torch
PROJECT_ROOT = Path(__file__).resolve().parents[3]


ROOT = Path(__file__).resolve().parents[1]
R82 = Path(str(PROJECT_ROOT / 'Experiments/R82_R39R40CrossSceneGeneralizationBenchmark'))
HOLDOUT = ROOT / "data" / "r84_locked_holdout_tile_stable_confirmation"
OUTPUT = ROOT / "results" / "shared_global_preconditioner_probe"
DEVICE = "cuda:0"


def load_module():
    path = ROOT / "inference" / "infer_r84.py"
    spec = importlib.util.spec_from_file_location("r84_shared_physics_probe", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def preprocess_canvas(module, model, image: np.ndarray) -> tuple[torch.Tensor, tuple[int, int]]:
    canvas, original_shape = module.canonical_canvas(image)
    tensor = torch.from_numpy(canvas.astype(np.float32) / 255.0)[None, None].to(DEVICE)
    with torch.no_grad(), torch.cuda.amp.autocast(enabled=False):
        conditioned = model.physics_layer(tensor).float()
    return conditioned, original_shape


def run_tensor(model, tensor: torch.Tensor) -> torch.Tensor:
    with torch.no_grad(), torch.cuda.amp.autocast(enabled=False):
        return model(tensor).float().clamp(0.0, 1.0)


def infer_shared_full(module, model, image: np.ndarray) -> np.ndarray:
    conditioned, original_shape = preprocess_canvas(module, model, image)
    prediction = run_tensor(model, conditioned)[0, 0]
    height, width = original_shape
    return np.clip(np.rint(prediction[:height, :width].cpu().numpy() * 255.0), 0, 255).astype(np.uint8)


def infer_shared_tiled(module, model, image: np.ndarray, core: int = 512, halo: int = 192) -> np.ndarray:
    conditioned, original_shape = preprocess_canvas(module, model, image)
    _, _, height, width = conditioned.shape
    output = torch.empty((height, width), dtype=torch.float32, device="cpu")
    for core_y in range(0, height, core):
        for core_x in range(0, width, core):
            y0 = max(0, core_y - halo)
            x0 = max(0, core_x - halo)
            y1 = min(height, core_y + core + halo)
            x1 = min(width, core_x + core + halo)
            prediction = run_tensor(model, conditioned[:, :, y0:y1, x0:x1])[0, 0].cpu()
            crop_y = core_y - y0
            crop_x = core_x - x0
            output[core_y:core_y + core, core_x:core_x + core] = prediction[
                crop_y:crop_y + core, crop_x:crop_x + core
            ]
    original_height, original_width = original_shape
    return np.clip(np.rint(output[:original_height, :original_width].numpy() * 255.0), 0, 255).astype(np.uint8)


def metrics(reference: np.ndarray, prediction: np.ndarray) -> dict[str, float]:
    ref = reference.astype(np.float32)
    pred = prediction.astype(np.float32)
    gx_ref = cv2.Sobel(ref, cv2.CV_32F, 1, 0, ksize=3)
    gy_ref = cv2.Sobel(ref, cv2.CV_32F, 0, 1, ksize=3)
    gx_pred = cv2.Sobel(pred, cv2.CV_32F, 1, 0, ksize=3)
    gy_pred = cv2.Sobel(pred, cv2.CV_32F, 0, 1, ksize=3)
    return {
        "mae": float(np.mean(np.abs(ref - pred))),
        "edge_mae": float(np.mean(np.abs(cv2.magnitude(gx_ref, gy_ref) - cv2.magnitude(gx_pred, gy_pred)))),
    }


def main() -> int:
    module = load_module()
    checkpoint = ROOT / "weights" / "selected" / "r84_tile_stable_model.pth.tar"
    model = module.build_model(checkpoint, DEVICE, tile_stable=True, use_ema=True)[0]
    manifest = json.loads((HOLDOUT / "manifest.json").read_text(encoding="utf-8"))
    rows = []
    tile_rows = []
    for index, pair in enumerate(manifest["pairs"], start=1):
        raw = module.read_gray(HOLDOUT / pair["package_src"])
        label = module.read_gray(HOLDOUT / pair["package_lbl"])
        full = infer_shared_full(module, model, raw)
        tiled = infer_shared_tiled(module, model, raw)
        rows.append({"pair_id": pair["pair_id"], **metrics(label, tiled)})
        tile_rows.append({"sample": pair["pair_id"], **module.difference_metrics(full, tiled)})
        target = OUTPUT / "reconstructions" / "locked_synthetic" / Path(pair["package_src"]).relative_to("src")
        module.write_bmp(target, tiled)
        if index % 64 == 0:
            print(f"shared-precondition holdout {index}/{len(manifest['pairs'])}", flush=True)

    r82_config = json.loads((R82 / "config" / "experiment.json").read_text(encoding="utf-8"))
    sem_root = Path(PROJECT_ROOT / r82_config["sem_acm"]["raw_input_dir"])
    for exposure in r82_config["sem_acm"]["optical_exposures"]:
        source = sem_root / f"{exposure}.bmp"
        image = module.read_gray(source)
        module.write_bmp(OUTPUT / "reconstructions" / "SEM" / source.name, infer_shared_tiled(module, model, image))

    fixtures = [
        Path(PROJECT_ROOT / r82_config["real_fov"]["locked_raw_root"]) / "5x_0p5um" / "frame_0000.bmp",
        Path(PROJECT_ROOT / r82_config["real_fov"]["locked_raw_root"]) / "50x_0p5um" / "frame_0050.bmp",
        sem_root / "18.bmp",
    ]
    for source in fixtures:
        image = module.read_gray(source)
        full = infer_shared_full(module, model, image)
        tiled = infer_shared_tiled(module, model, image)
        tile_rows.append({"sample": str(source), **module.difference_metrics(full, tiled)})

    OUTPUT.mkdir(parents=True, exist_ok=True)
    frame = pd.DataFrame(rows)
    tiles = pd.DataFrame(tile_rows)
    frame.to_csv(OUTPUT / "locked_synthetic_metrics.csv", index=False)
    tiles.to_csv(OUTPUT / "tile_metrics.csv", index=False)
    baseline = pd.read_csv(ROOT / "results" / "final_confirmation" / "tables" / "locked_synthetic_summary.csv")
    summary = {
        "role": "post-closeout architectural diagnosis; not confirmatory evidence",
        "shared_preconditioner": {
            "median_mae": float(frame["mae"].median()),
            "median_edge_mae": float(frame["edge_mae"].median()),
            "worst_tile_mean": float(tiles["mean_abs_gray"].max()),
            "worst_tile_p99": float(tiles["p99_abs_gray"].max()),
            "worst_tile_max": float(tiles["max_abs_gray"].max()),
        },
        "R79_reference": baseline.loc[baseline["method"] == "R79"].iloc[0].to_dict(),
        "R84_reference": baseline.loc[baseline["method"] == "R84"].iloc[0].to_dict(),
    }
    (OUTPUT / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

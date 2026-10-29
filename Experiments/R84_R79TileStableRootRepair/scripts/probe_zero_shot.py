"""Zero-update feasibility probe for the R84 structural repair."""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import cv2
import numpy as np
import pandas as pd
import torch
PROJECT_ROOT = Path(__file__).resolve().parents[3]


ROOT = Path(__file__).resolve().parents[1]
R82 = Path(str(PROJECT_ROOT / 'Experiments/R82_R39R40CrossSceneGeneralizationBenchmark'))
R83 = Path(str(PROJECT_ROOT / 'Experiments/R83_R79SevereMicroscopyStrengthening'))
OUTPUT = ROOT / "results" / "zero_shot_probe"


def load_module():
    path = ROOT / "inference" / "infer_r84.py"
    spec = importlib.util.spec_from_file_location("r84_inference_probe", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def image_metrics(reference: np.ndarray, prediction: np.ndarray) -> dict[str, float]:
    reference = reference.astype(np.float32)
    prediction = prediction.astype(np.float32)
    gx_ref = cv2.Sobel(reference, cv2.CV_32F, 1, 0, ksize=3)
    gy_ref = cv2.Sobel(reference, cv2.CV_32F, 0, 1, ksize=3)
    gx_pred = cv2.Sobel(prediction, cv2.CV_32F, 1, 0, ksize=3)
    gy_pred = cv2.Sobel(prediction, cv2.CV_32F, 0, 1, ksize=3)
    return {
        "mae": float(np.mean(np.abs(reference - prediction))),
        "edge_mae": float(np.mean(np.abs(cv2.magnitude(gx_ref, gy_ref) - cv2.magnitude(gx_pred, gy_pred)))),
    }


def main() -> int:
    module = load_module()
    checkpoint = ROOT / "weights" / "seed" / "r79e23_ema_seed.pth.tar"
    repaired, _ = module.build_model(checkpoint, "cuda:0", tile_stable=True, use_ema=True)
    parent, _ = module.build_model(checkpoint, "cuda:0", tile_stable=False, use_ema=True)
    r82 = json.loads((R82 / "config" / "experiment.json").read_text(encoding="utf-8"))
    raw_root = Path(PROJECT_ROOT / r82["real_fov"]["locked_raw_root"])
    sem_root = Path(PROJECT_ROOT / r82["sem_acm"]["raw_input_dir"])
    samples = [
        ("real_5x", raw_root / "5x_0p5um" / "frame_0000.bmp"),
        ("real_50x", raw_root / "50x_0p5um" / "frame_0050.bmp"),
        ("SEM", sem_root / "18.bmp"),
    ]
    tile_rows = []
    for name, path in samples:
        raw = module.read_gray(path)
        full = module.infer_canonical_full(repaired, raw, "cuda:0")
        tiled = module.infer_phase_locked_tiled(repaired, raw, "cuda:0")
        row = {"sample": name, **module.difference_metrics(full, tiled)}
        tile_rows.append(row)
        print(row, flush=True)

    pilot = Path(PROJECT_ROOT / json.loads((ROOT / "config" / "experiment.json").read_text(encoding="utf-8"))["data"]["pilot_package"])
    manifest = json.loads((pilot / "manifest.json").read_text(encoding="utf-8"))
    validation_pairs = [row for row in manifest["pairs"] if row["split"] == "validation"][:64]
    metric_rows = []
    for index, pair in enumerate(validation_pairs, start=1):
        raw = module.read_gray(pilot / pair["package_src"])
        label = module.read_gray(pilot / pair["package_lbl"])
        parent_output = module.infer_canonical_full(parent, raw, "cuda:0")
        repaired_output = module.infer_canonical_full(repaired, raw, "cuda:0")
        metric_rows.extend([
            {"pair_id": pair["pair_id"], "method": "R79", **image_metrics(label, parent_output)},
            {"pair_id": pair["pair_id"], "method": "R84Zero", **image_metrics(label, repaired_output)},
        ])
        if index % 16 == 0:
            print(f"validation {index}/{len(validation_pairs)}", flush=True)

    OUTPUT.mkdir(parents=True, exist_ok=True)
    tile = pd.DataFrame(tile_rows)
    metrics = pd.DataFrame(metric_rows)
    tile.to_csv(OUTPUT / "tile_consistency.csv", index=False)
    metrics.to_csv(OUTPUT / "pilot_validation_metrics.csv", index=False)
    summary = metrics.groupby("method", as_index=False).agg(
        median_mae=("mae", "median"), median_edge_mae=("edge_mae", "median")
    )
    summary.to_csv(OUTPUT / "pilot_validation_summary.csv", index=False)
    result = {
        "tile_gate_pass": bool(
            tile["mean_abs_gray"].max() <= 0.1
            and tile["p99_abs_gray"].max() <= 1.0
            and tile["max_abs_gray"].max() <= 3.0
        ),
        "tile_rows": tile.to_dict(orient="records"),
        "validation_summary": summary.to_dict(orient="records"),
    }
    (OUTPUT / "decision.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2), flush=True)
    del repaired, parent
    torch.cuda.empty_cache()
    return 0 if result["tile_gate_pass"] else 2


if __name__ == "__main__":
    raise SystemExit(main())

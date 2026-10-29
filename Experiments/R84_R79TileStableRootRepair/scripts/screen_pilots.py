"""Apply the predeclared R84 pilot ranking using procedural validation only."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import cv2
import numpy as np
import pandas as pd
PROJECT_ROOT = Path(__file__).resolve().parents[3]


ROOT = Path(__file__).resolve().parents[1]
R82 = Path(str(PROJECT_ROOT / 'Experiments/R82_R39R40CrossSceneGeneralizationBenchmark'))
OUTPUT = ROOT / "results" / "pilot_screen"


def load_module():
    path = ROOT / "inference" / "infer_r84.py"
    spec = importlib.util.spec_from_file_location("r84_inference_pilot_screen", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def image_metrics(reference: np.ndarray, prediction: np.ndarray) -> dict[str, float]:
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
    config = json.loads((ROOT / "config" / "experiment.json").read_text(encoding="utf-8"))
    package = Path(PROJECT_ROOT / config["data"]["pilot_package"])
    manifest = json.loads((package / "manifest.json").read_text(encoding="utf-8"))
    validation = [row for row in manifest["pairs"] if row["split"] == "validation"]
    candidates = {
        "norm_tail": ROOT / "weights" / "pilot" / "norm_tail" / "pilot_norm_tail_e5" / "best.pth.tar",
        "all_low_lr": ROOT / "weights" / "pilot" / "all_low_lr" / "pilot_all_low_lr_e5" / "best.pth.tar",
    }
    parameter_counts = {
        name: json.loads((ROOT / "runs" / f"pilot_{name}_e5" / "run_summary.json").read_text(encoding="utf-8"))["trainable_audit"]["trainable_parameter_count"]
        for name in candidates
    }
    models = {name: module.build_model(path, "cuda:0", tile_stable=True, use_ema=True)[0] for name, path in candidates.items()}
    parent = module.build_model(ROOT / "weights" / "seed" / "r79e23_ema_seed.pth.tar", "cuda:0", tile_stable=False, use_ema=True)[0]

    metric_rows = []
    for index, pair in enumerate(validation, start=1):
        raw = module.read_gray(package / pair["package_src"])
        label = module.read_gray(package / pair["package_lbl"])
        outputs = {"R79": module.infer_canonical_full(parent, raw, "cuda:0")}
        outputs.update({name: module.infer_canonical_full(model, raw, "cuda:0") for name, model in models.items()})
        for name, output in outputs.items():
            metric_rows.append({"pair_id": pair["pair_id"], "method": name, **image_metrics(label, output)})
        if index % 24 == 0:
            print(f"validation {index}/{len(validation)}", flush=True)

    r82 = json.loads((R82 / "config" / "experiment.json").read_text(encoding="utf-8"))
    raw_root = Path(PROJECT_ROOT / r82["real_fov"]["locked_raw_root"])
    sem_root = Path(PROJECT_ROOT / r82["sem_acm"]["raw_input_dir"])
    tile_samples = [
        ("real_5x", raw_root / "5x_0p5um" / "frame_0000.bmp"),
        ("real_50x", raw_root / "50x_0p5um" / "frame_0050.bmp"),
        ("SEM", sem_root / "18.bmp"),
    ]
    tile_rows = []
    for candidate, model in models.items():
        for sample, path in tile_samples:
            raw = module.read_gray(path)
            full = module.infer_canonical_full(model, raw, "cuda:0")
            tiled = module.infer_phase_locked_tiled(model, raw, "cuda:0")
            tile_rows.append({"candidate": candidate, "sample": sample, **module.difference_metrics(full, tiled)})

    OUTPUT.mkdir(parents=True, exist_ok=True)
    metrics = pd.DataFrame(metric_rows)
    tiles = pd.DataFrame(tile_rows)
    metrics.to_csv(OUTPUT / "validation_metrics.csv", index=False)
    tiles.to_csv(OUTPUT / "tile_metrics.csv", index=False)
    summary = metrics.groupby("method", as_index=False).agg(
        median_mae=("mae", "median"), median_edge_mae=("edge_mae", "median")
    )
    rows = []
    for candidate in candidates:
        metric = summary.loc[summary["method"] == candidate].iloc[0]
        tile = tiles.loc[tiles["candidate"] == candidate]
        rows.append({
            "candidate": candidate,
            "median_mae": float(metric["median_mae"]),
            "median_edge_mae": float(metric["median_edge_mae"]),
            "trainable_parameter_count": int(parameter_counts[candidate]),
            "worst_tile_mean": float(tile["mean_abs_gray"].max()),
            "worst_tile_p99": float(tile["p99_abs_gray"].max()),
            "worst_tile_max": float(tile["max_abs_gray"].max()),
            "tile_gate_pass": bool(
                tile["mean_abs_gray"].max() <= 0.1
                and tile["p99_abs_gray"].max() <= 1.0
                and tile["max_abs_gray"].max() <= 3.0
            ),
        })
    eligible = [row for row in rows if row["tile_gate_pass"]]
    eligible.sort(key=lambda row: (row["median_edge_mae"], row["median_mae"], row["trainable_parameter_count"]))
    selected = eligible[0]["candidate"] if eligible else None
    decision = {
        "status": "complete",
        "selection_inputs": "procedural validation plus structural full-versus-tile differences only",
        "external_or_reserved_results_used": False,
        "ranking": ["tile gate", "lowest edge MAE", "lowest MAE", "least trainable parameters"],
        "selected_candidate": selected,
        "rows": rows,
        "reference_rows": summary.to_dict(orient="records"),
    }
    summary.to_csv(OUTPUT / "validation_summary.csv", index=False)
    (OUTPUT / "decision.json").write_text(json.dumps(decision, indent=2), encoding="utf-8")
    print(json.dumps(decision, indent=2), flush=True)
    return 0 if selected else 2


if __name__ == "__main__":
    raise SystemExit(main())

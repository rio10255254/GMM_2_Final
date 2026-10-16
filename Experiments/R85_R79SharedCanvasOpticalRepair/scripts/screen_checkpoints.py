"""Select R85 epoch 5 or 10 without opening confirmation evidence."""
from __future__ import annotations

import gc
import importlib.util
import json
from pathlib import Path

import cv2
import numpy as np
import pandas as pd
import torch


ROOT = Path(__file__).resolve().parents[1]
R82 = Path(r"D:\GMM_2_Final\Experiments\R82_R39R40CrossSceneGeneralizationBenchmark")
OUTPUT = ROOT / "results" / "checkpoint_screen"
DEVICE = "cuda:0"


def load_module():
    path = ROOT / "inference" / "infer_r85.py"
    spec = importlib.util.spec_from_file_location("r85_checkpoint_screen", path)
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


def infer_r79_canonical(module, model, image: np.ndarray) -> np.ndarray:
    canvas, original_shape = module.canonical_canvas(image)
    prediction = module._run(model, canvas, DEVICE)
    height, width = original_shape
    return np.clip(np.rint(prediction[:height, :width] * 255.0), 0, 255).astype(np.uint8)


def main() -> int:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    config = json.loads((ROOT / "config" / "experiment.json").read_text(encoding="utf-8"))
    module = load_module()
    package = Path(config["data"]["formal_package"])
    manifest_path = package / "manifest.json"
    if module.sha256(manifest_path) != config["data"]["formal_manifest_sha256"]:
        raise RuntimeError("Formal procedural manifest changed.")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    validation = [row for row in manifest["pairs"] if row["split"] == "validation"]
    if len(validation) != 512:
        raise RuntimeError(f"Expected 512 validation pairs, found {len(validation)}")
    root = ROOT / "weights" / "formal" / "formal_shared_canvas_e10"
    candidates = {f"R85_E{epoch:02d}": root / f"epoch_{epoch:03d}.pth.tar" for epoch in config["training"]["eligible_epochs"]}

    frames = []
    teacher = module.build_model(ROOT / config["teacher"]["checkpoint"], DEVICE, tile_stable=False, use_ema=True)[0]
    records = []
    for index, pair in enumerate(validation, start=1):
        raw = module.read_gray(package / pair["package_src"])
        label = module.read_gray(package / pair["package_lbl"])
        output = infer_r79_canonical(module, teacher, raw)
        mae, edge = metrics(label, output)
        records.append({"pair_id": pair["pair_id"], "method": "R79", "mae": mae, "edge_mae": edge})
        if index % 128 == 0:
            print(f"R79 {index}/{len(validation)}", flush=True)
    frames.append(pd.DataFrame(records))
    del teacher
    torch.cuda.empty_cache()

    r82_config = json.loads((R82 / "config" / "experiment.json").read_text(encoding="utf-8"))
    raw_root = Path(r82_config["real_fov"]["locked_raw_root"])
    sem_root = Path(r82_config["sem_acm"]["raw_input_dir"])
    fixtures = [
        ("real_5x", raw_root / "5x_0p5um" / "frame_0000.bmp"),
        ("real_50x", raw_root / "50x_0p5um" / "frame_0050.bmp"),
        ("SEM", sem_root / "18.bmp"),
    ]
    tile_records = []
    for name, checkpoint in candidates.items():
        model = module.build_model(checkpoint, DEVICE, tile_stable=True, use_ema=True)[0]
        records = []
        for index, pair in enumerate(validation, start=1):
            raw = module.read_gray(package / pair["package_src"])
            label = module.read_gray(package / pair["package_lbl"])
            output = module.infer_canonical_full(model, raw, DEVICE)
            mae, edge = metrics(label, output)
            records.append({"pair_id": pair["pair_id"], "method": name, "mae": mae, "edge_mae": edge})
            if index % 128 == 0:
                print(f"{name} {index}/{len(validation)}", flush=True)
        frames.append(pd.DataFrame(records))
        for sample, path in fixtures:
            raw = module.read_gray(path)
            full = module.infer_canonical_full(model, raw, DEVICE)
            tiled = module.infer_phase_locked_tiled(model, raw, DEVICE)
            tile_records.append({"method": name, "sample": sample, **module.difference_metrics(full, tiled)})
        del model
        gc.collect()
        torch.cuda.empty_cache()

    table = pd.concat(frames, ignore_index=True)
    tiles = pd.DataFrame(tile_records)
    summary = table.groupby("method", as_index=False).agg(median_mae=("mae", "median"), median_edge_mae=("edge_mae", "median"))
    reference = summary.loc[summary["method"] == "R79"].iloc[0]
    limits = config["selection"]["eligibility"]
    rows = []
    for epoch in config["training"]["eligible_epochs"]:
        name = f"R85_E{epoch:02d}"
        metric = summary.loc[summary["method"] == name].iloc[0]
        tile = tiles.loc[tiles["method"] == name]
        mae_ratio = float(metric["median_mae"] / reference["median_mae"])
        edge_ratio = float(metric["median_edge_mae"] / reference["median_edge_mae"])
        tile_pass = bool(
            tile["mean_abs_gray"].max() <= limits["tile_mean_max"]
            and tile["p99_abs_gray"].max() <= limits["tile_p99_max"]
            and tile["max_abs_gray"].max() <= limits["tile_max_max"]
        )
        eligible = bool(
            mae_ratio <= limits["median_mae_relative_to_R79_max"]
            and edge_ratio <= limits["median_edge_mae_relative_to_R79_max"]
            and tile_pass
        )
        rows.append({
            "method": name,
            "epoch": epoch,
            "checkpoint": str(candidates[name]),
            "median_mae": float(metric["median_mae"]),
            "median_edge_mae": float(metric["median_edge_mae"]),
            "mae_relative_to_R79": mae_ratio,
            "edge_relative_to_R79": edge_ratio,
            "worst_tile_mean": float(tile["mean_abs_gray"].max()),
            "worst_tile_p99": float(tile["p99_abs_gray"].max()),
            "worst_tile_max": float(tile["max_abs_gray"].max()),
            "tile_pass": tile_pass,
            "eligible": eligible,
        })
    eligible = [row for row in rows if row["eligible"]]
    eligible.sort(key=lambda row: (row["median_edge_mae"], row["median_mae"], row["epoch"]))
    selected = eligible[0] if eligible else None
    decision = {
        "status": "complete",
        "selection_inputs": "procedural validation plus three fixed tile fixtures only",
        "external_or_reserved_results_used": False,
        "reference": {"median_mae": float(reference["median_mae"]), "median_edge_mae": float(reference["median_edge_mae"])},
        "rows": rows,
        "selected_method": selected["method"] if selected else None,
        "selected_checkpoint": selected["checkpoint"] if selected else None,
        "fallback": "R79" if selected is None else None,
    }
    table.to_csv(OUTPUT / "validation_metrics.csv", index=False)
    summary.to_csv(OUTPUT / "validation_summary.csv", index=False)
    tiles.to_csv(OUTPUT / "tile_metrics.csv", index=False)
    (OUTPUT / "decision.json").write_text(json.dumps(decision, indent=2), encoding="utf-8")
    print(json.dumps(decision, indent=2), flush=True)
    return 0 if selected else 2


if __name__ == "__main__":
    raise SystemExit(main())

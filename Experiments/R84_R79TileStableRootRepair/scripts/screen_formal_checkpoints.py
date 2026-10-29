"""Select the R84 formal checkpoint using only predeclared development evidence."""
from __future__ import annotations

import argparse
import gc
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
OUTPUT = ROOT / "results" / "formal_checkpoint_screen"
DEVICE = "cuda:0"


def load_module():
    path = ROOT / "inference" / "infer_r84.py"
    spec = importlib.util.spec_from_file_location("r84_inference_formal_screen", path)
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
        "edge_mae": float(
            np.mean(
                np.abs(
                    cv2.magnitude(gx_ref, gy_ref)
                    - cv2.magnitude(gx_pred, gy_pred)
                )
            )
        ),
    }


def evaluate_method(module, name: str, checkpoint: Path, tile_stable: bool, package: Path, rows: list[dict]) -> pd.DataFrame:
    cache = OUTPUT / f"{name}_validation_metrics.csv"
    if cache.exists():
        frame = pd.read_csv(cache)
        if len(frame) == len(rows) and set(frame["pair_id"]) == {row["pair_id"] for row in rows}:
            print(f"reuse {name}: {len(frame)} rows", flush=True)
            return frame
    model = module.build_model(checkpoint, DEVICE, tile_stable=tile_stable, use_ema=True)[0]
    records = []
    for index, pair in enumerate(rows, start=1):
        raw = module.read_gray(package / pair["package_src"])
        label = module.read_gray(package / pair["package_lbl"])
        output = module.infer_canonical_full(model, raw, DEVICE)
        records.append({"pair_id": pair["pair_id"], "method": name, **image_metrics(label, output)})
        if index % 64 == 0:
            print(f"{name}: {index}/{len(rows)}", flush=True)
    frame = pd.DataFrame(records)
    frame.to_csv(cache, index=False)
    del model
    gc.collect()
    torch.cuda.empty_cache()
    return frame


def tile_metrics(module, name: str, checkpoint: Path, tile_stable: bool, fixtures: list[tuple[str, Path]]) -> list[dict]:
    model = module.build_model(checkpoint, DEVICE, tile_stable=tile_stable, use_ema=True)[0]
    records = []
    for sample, path in fixtures:
        raw = module.read_gray(path)
        full = module.infer_canonical_full(model, raw, DEVICE)
        tiled = module.infer_phase_locked_tiled(model, raw, DEVICE)
        records.append({"method": name, "sample": sample, **module.difference_metrics(full, tiled)})
    del model
    gc.collect()
    torch.cuda.empty_cache()
    return records


def main(argv: list[str] | None = None) -> int:
    global OUTPUT
    parser = argparse.ArgumentParser(description="Screen locked R84 development checkpoints")
    parser.add_argument("--phase", choices=("initial", "recovery", "continuation"), default="initial")
    args = parser.parse_args(argv)
    if args.phase == "continuation":
        OUTPUT = ROOT / "results" / "formal_continuation_checkpoint_screen"
        lock_path = ROOT / "reports" / "R84_CONTINUATION_AMENDMENT_LOCK.json"
        weight_root = ROOT / "weights" / "formal" / "all_low_lr" / "formal_recovery_continuation_e10"
        method_prefix = "R84C"
        epoch_section = "continuation"
    elif args.phase == "recovery":
        OUTPUT = ROOT / "results" / "formal_recovery_checkpoint_screen"
        lock_path = ROOT / "reports" / "R84_RECOVERY_AMENDMENT_LOCK.json"
        weight_root = ROOT / "weights" / "formal" / "all_low_lr" / "formal_recovery_all_local_e20"
        method_prefix = "R84B"
        epoch_section = "recovery"
    else:
        lock_path = ROOT / "reports" / "R84_FORMAL_SELECTION_LOCK.json"
        weight_root = ROOT / "weights" / "formal" / "norm_tail" / "formal_norm_tail_e20"
        method_prefix = "R84"
        epoch_section = ""
    OUTPUT.mkdir(parents=True, exist_ok=True)
    module = load_module()
    experiment = json.loads((ROOT / "config" / "experiment.json").read_text(encoding="utf-8"))
    selection_lock = json.loads(lock_path.read_text(encoding="utf-8"))
    package = Path(PROJECT_ROOT / experiment["data"]["formal_package"])
    manifest_path = package / "manifest.json"
    if module.sha256(manifest_path) != experiment["data"]["formal_manifest_sha256"]:
        raise RuntimeError("Formal procedural manifest changed after protocol lock.")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    validation = [row for row in manifest["pairs"] if row["split"] == "validation"]
    if len(validation) != 512:
        raise RuntimeError(f"Expected 512 formal validation pairs, found {len(validation)}")

    eligible_epochs = selection_lock["eligible_epochs"] if not epoch_section else selection_lock[epoch_section]["eligible_epochs"]
    candidates = {
        f"{method_prefix}_E{epoch:02d}": weight_root / f"epoch_{epoch:03d}.pth.tar"
        for epoch in eligible_epochs
    }
    methods = {
        "R79": (ROOT / "weights" / "seed" / "r79e23_ema_seed.pth.tar", False),
        **{name: (path, True) for name, path in candidates.items()},
    }
    for name, (path, _) in methods.items():
        if not path.is_file():
            raise FileNotFoundError(f"Missing {name}: {path}")

    all_metrics = []
    for name, (path, tile_stable) in methods.items():
        all_metrics.append(evaluate_method(module, name, path, tile_stable, package, validation))
    metrics = pd.concat(all_metrics, ignore_index=True)
    metrics.to_csv(OUTPUT / "validation_metrics.csv", index=False)
    summary = metrics.groupby("method", as_index=False).agg(
        median_mae=("mae", "median"),
        median_edge_mae=("edge_mae", "median"),
        p95_mae=("mae", lambda values: float(np.quantile(values, 0.95))),
        p95_edge_mae=("edge_mae", lambda values: float(np.quantile(values, 0.95))),
    )

    r82 = json.loads((R82 / "config" / "experiment.json").read_text(encoding="utf-8"))
    raw_root = Path(PROJECT_ROOT / r82["real_fov"]["locked_raw_root"])
    sem_root = Path(PROJECT_ROOT / r82["sem_acm"]["raw_input_dir"])
    fixtures = [
        ("real_5x", raw_root / "5x_0p5um" / "frame_0000.bmp"),
        ("real_50x", raw_root / "50x_0p5um" / "frame_0050.bmp"),
        ("SEM", sem_root / "18.bmp"),
    ]
    tile_records = []
    for name, path in candidates.items():
        tile_records.extend(tile_metrics(module, name, path, True, fixtures))
    tiles = pd.DataFrame(tile_records)
    tiles.to_csv(OUTPUT / "tile_metrics.csv", index=False)

    reference = summary.loc[summary["method"] == "R79"].iloc[0]
    mae_limit = float(selection_lock["eligibility"]["procedural_validation_median_mae_relative_to_R79_max"])
    edge_limit = float(selection_lock["eligibility"]["procedural_validation_median_edge_mae_relative_to_R79_max"])
    decision_rows = []
    for epoch in eligible_epochs:
        name = f"{method_prefix}_E{epoch:02d}"
        metric = summary.loc[summary["method"] == name].iloc[0]
        tile = tiles.loc[tiles["method"] == name]
        tile_pass = bool(
            float(tile["mean_abs_gray"].max()) <= 0.1
            and float(tile["p99_abs_gray"].max()) <= 1.0
            and float(tile["max_abs_gray"].max()) <= 3.0
        )
        mae_ratio = float(metric["median_mae"] / reference["median_mae"])
        edge_ratio = float(metric["median_edge_mae"] / reference["median_edge_mae"])
        eligible = bool(tile_pass and mae_ratio <= mae_limit and edge_ratio <= edge_limit)
        decision_rows.append({
            "method": name,
            "epoch": int(epoch),
            "checkpoint": str(candidates[name]),
            "median_mae": float(metric["median_mae"]),
            "median_edge_mae": float(metric["median_edge_mae"]),
            "mae_relative_to_R79": mae_ratio,
            "edge_mae_relative_to_R79": edge_ratio,
            "worst_tile_mean": float(tile["mean_abs_gray"].max()),
            "worst_tile_p99": float(tile["p99_abs_gray"].max()),
            "worst_tile_max": float(tile["max_abs_gray"].max()),
            "tile_gate_pass": tile_pass,
            "quality_gate_pass": bool(mae_ratio <= mae_limit and edge_ratio <= edge_limit),
            "eligible": eligible,
        })
    eligible_rows = [row for row in decision_rows if row["eligible"]]
    eligible_rows.sort(key=lambda row: (row["median_edge_mae"], row["median_mae"], row["epoch"]))
    selected = eligible_rows[0] if eligible_rows else None
    decision = {
        "status": "complete",
        "selection_inputs": "formal procedural validation and fixed structural tile fixtures only",
        "external_or_reserved_results_used": False,
        "reference": {
            "method": "R79",
            "median_mae": float(reference["median_mae"]),
            "median_edge_mae": float(reference["median_edge_mae"]),
        },
        "limits": {"mae_relative_to_R79_max": mae_limit, "edge_mae_relative_to_R79_max": edge_limit},
        "rows": decision_rows,
        "selected_method": selected["method"] if selected else None,
        "selected_checkpoint": selected["checkpoint"] if selected else None,
        "fallback": "R79" if selected is None else None,
    }
    summary.to_csv(OUTPUT / "validation_summary.csv", index=False)
    (OUTPUT / "decision.json").write_text(json.dumps(decision, indent=2), encoding="utf-8")
    print(json.dumps(decision, indent=2), flush=True)
    return 0 if selected else 2


if __name__ == "__main__":
    raise SystemExit(main())

"""Isolate which R79 global-context blocks cause full-frame/tiled drift."""
from __future__ import annotations

import copy
import importlib.util
import json
from pathlib import Path

import cv2
import numpy as np
import pandas as pd
import torch
from torch import nn


ROOT = Path(__file__).resolve().parents[1]
R82 = Path(r"D:\GMM_2_Final\Experiments\R82_R39R40CrossSceneGeneralizationBenchmark")
OUTPUT = ROOT / "results" / "tile_context_diagnosis"


def load_inference_module():
    path = ROOT / "inference" / "infer_r83.py"
    spec = importlib.util.spec_from_file_location("r83_inference_tile_diagnosis", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def metrics(left: np.ndarray, right: np.ndarray) -> dict[str, float]:
    diff = np.abs(left.astype(np.float32) - right.astype(np.float32))
    return {
        "mean_abs_gray": float(diff.mean()),
        "p99_abs_gray": float(np.quantile(diff, 0.99)),
        "max_abs_gray": float(diff.max()),
        "changed_fraction": float(np.mean(diff > 0)),
    }


def main() -> int:
    config = json.loads((ROOT / "config" / "experiment.json").read_text(encoding="utf-8"))
    r82 = json.loads((R82 / "config" / "experiment.json").read_text(encoding="utf-8"))
    checkpoint = ROOT / "weights" / "selected" / "r83_model.pth.tar"
    module = load_inference_module()

    raw_root = Path(r82["real_fov"]["locked_raw_root"])
    sem_root = Path(r82["sem_acm"]["raw_input_dir"])
    samples = [
        ("real_5x", raw_root / "5x_0p5um" / "frame_0000.bmp"),
        ("real_50x", raw_root / "50x_0p5um" / "frame_0050.bmp"),
        ("SEM", sem_root / "18.bmp"),
    ]

    base_model, state_key = module.build_model(checkpoint, "cuda:0", True)
    if state_key != "ema_state_dict":
        raise RuntimeError("Tile diagnosis requires the selected EMA state.")

    variants = {
        "full_r79": (True, True),
        "no_input_physics": (False, True),
        "no_weak_psf": (True, False),
        "local_only": (False, False),
    }
    rows: list[dict] = []
    state = copy.deepcopy(base_model.state_dict())
    for variant, (physics_enabled, weak_psf_enabled) in variants.items():
        model, _ = module.build_model(checkpoint, "cuda:0", True)
        model.load_state_dict(state, strict=True)
        if not physics_enabled:
            model.physics_layer = nn.Identity()
        if not weak_psf_enabled:
            model.weak_psf_block = None
        model.eval()
        for sample_name, path in samples:
            raw = module.read_gray(path)
            whole = module.infer_tiled(model, raw, "cuda:0", 4096, 0)
            tiled = module.infer_tiled(model, raw, "cuda:0", 512, 64)
            record = {
                "variant": variant,
                "sample": sample_name,
                "height": int(raw.shape[0]),
                "width": int(raw.shape[1]),
                **metrics(whole, tiled),
            }
            rows.append(record)
            print(record, flush=True)
        del model
        torch.cuda.empty_cache()

    OUTPUT.mkdir(parents=True, exist_ok=True)
    frame = pd.DataFrame(rows)
    frame.to_csv(OUTPUT / "tile_context_ablation.csv", index=False)
    summary = frame.groupby("variant", as_index=False).agg(
        worst_mean_abs_gray=("mean_abs_gray", "max"),
        worst_p99_abs_gray=("p99_abs_gray", "max"),
        worst_max_abs_gray=("max_abs_gray", "max"),
    )
    summary.to_csv(OUTPUT / "tile_context_ablation_summary.csv", index=False)
    (OUTPUT / "diagnosis_manifest.json").write_text(
        json.dumps({
            "experiment_id": config["experiment_id"],
            "checkpoint": str(checkpoint),
            "state_key": state_key,
            "tile_comparison": {"whole": [4096, 0], "tiled": [512, 64]},
            "samples": [{"name": name, "path": str(path)} for name, path in samples],
            "variants": variants,
        }, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print(summary.to_json(orient="records", indent=2), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Stress R97 E48 on many unseen periodic scenes and hard one-period alternatives."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys

import numpy as np
import pandas as pd
import torch


ROOT = Path(__file__).resolve().parents[1]
MODEL_PATH = ROOT / "model" / "r97_model.py"
PERIODIC_PATH = ROOT / "training" / "periodic_disambiguation.py"
DESIGN_PATH = ROOT / "config" / "experiment_design.json"
PROTOCOL_PATH = ROOT / "config" / "posttraining_validation_protocol.json"
OUTPUT = ROOT / "results" / "posttraining_validation" / "periodic_stress"


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


MODEL = load_module("r97_post_periodic_model", MODEL_PATH)
PERIODIC = load_module("r97_post_periodic_helpers", PERIODIC_PATH)


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    temporary.replace(path)


def main() -> None:
    if OUTPUT.exists() and any(OUTPUT.iterdir()):
        raise RuntimeError(f"Refusing to overwrite periodic stress output: {OUTPUT}")
    OUTPUT.mkdir(parents=True, exist_ok=True)
    design = read_json(DESIGN_PATH)
    protocol = read_json(PROTOCOL_PATH)
    checkpoint = torch.load(Path(protocol["checkpoint"]), map_location="cpu", weights_only=False)
    model = MODEL.build_model(base=int(design["architecture"]["model_width"]))
    model.load_state_dict(checkpoint[protocol["checkpoint_state"]], strict=True)
    device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")
    model.eval().to(device)
    rows: list[dict] = []
    batch_size, batches = 8, 32
    with torch.inference_mode():
        for batch_index in range(batches):
            seed = 979000 + batch_index * 1009
            batch = PERIODIC.make_periodic_batch(batch_size, 256, seed, device=device)
            model_output = model(batch.source)
            for method, image in (("Raw", batch.source), ("R97E48", model_output), ("CleanTarget", batch.target)):
                loss, metrics = PERIODIC.wrong_period_margin_loss(image, batch.shift_xy, batch.period_xy)
                rows.append({
                    "batch": batch_index,
                    "seed": seed,
                    "method": method,
                    "scenes": batch_size,
                    "loss": float(loss),
                    **{name: float(value) for name, value in metrics.items()},
                })
            print(f"[periodic] {batch_index + 1}/{batches}", flush=True)
    table = pd.DataFrame(rows)
    table.to_csv(OUTPUT / "batch_metrics.csv", index=False)
    summaries: list[dict] = []
    for method, group in table.groupby("method", sort=False):
        summaries.append({
            "method": method,
            "scenes": int(group["scenes"].sum()),
            "mean_true_score": float(group["true_score"].mean()),
            "mean_hardest_wrong_score": float(group["hardest_wrong_score"].mean()),
            "mean_match_margin": float(group["match_margin"].mean()),
            "minimum_batch_match_margin": float(group["match_margin"].min()),
            "p05_batch_match_margin": float(np.quantile(group["match_margin"], 0.05)),
            "mean_wrong_pitch_rate": float(group["wrong_pitch_rate"].mean()),
            "maximum_batch_wrong_pitch_rate": float(group["wrong_pitch_rate"].max()),
        })
    result = {
        "status": "complete",
        "checkpoint_epoch": 48,
        "checkpoint_state": protocol["checkpoint_state"],
        "unseen_scenes_per_method": batch_size * batches,
        "summaries": summaries,
        "claim_boundary": "This is a synthetic periodic ambiguity stress test; real adjacent-frame and external GMF results remain separate evidence.",
    }
    write_json(OUTPUT / "summary.json", result)
    print(json.dumps(result, indent=2), flush=True)


if __name__ == "__main__":
    main()

"""Evaluate a frozen R116 causal intervention on the locked SEM ACM audit."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys

import cv2
import numpy as np
import pandas as pd
import torch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from validation import intervention_adapter
from validation.interventions import MODES
import validation.run_sem_shortlist as sem


def read_gray(path: Path) -> np.ndarray:
    value = cv2.imdecode(np.fromfile(str(path), np.uint8), cv2.IMREAD_GRAYSCALE)
    if value is None:
        raise RuntimeError(f"Could not read {path}")
    return value


def write_gray(path: Path, value: np.ndarray) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    success, encoded = cv2.imencode(".bmp", value.astype(np.uint8))
    if not success:
        raise RuntimeError(f"Could not encode {path}")
    encoded.tofile(str(path))


@torch.inference_mode()
def reconstruct(checkpoint: Path, mode: str, destination: Path, device: torch.device) -> None:
    os.environ["R116_INTERVENTION_MODE"] = mode
    model = intervention_adapter.load_model(str(checkpoint), device)
    for exposure in range(13, 25):
        source = sem.RAW_DIR / f"{exposure}.bmp"
        raw = read_gray(source)
        tensor = torch.from_numpy(raw.astype(np.float32) / 255.0)[None, None].to(device)
        prediction = intervention_adapter.predict_canonical_tiled(
            model, tensor, intervention_adapter.canonical_tile_config(model, core=512, halo=224),
        )
        image = np.rint(prediction.output[0, 0].clamp(0, 1).cpu().numpy() * 255.0).astype(np.uint8)
        write_gray(destination / source.name, image)
        print(json.dumps({"mode": mode, "exposure": exposure}), flush=True)
    del model
    torch.cuda.empty_cache()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--checkpoint", required=True)
    parser.add_argument("--intervention", required=True, choices=MODES)
    parser.add_argument("--output", required=True)
    parser.add_argument("--method-name", required=True)
    parser.add_argument("--device", default="cuda:0")
    args = parser.parse_args()
    root = Path(args.output).resolve()
    destination = root / "reconstructions"
    sem.OUTPUT = root
    reconstruct(Path(args.checkpoint), args.intervention, destination, torch.device(args.device))
    primary_path, sensitivity_path = sem.run_acm(args.method_name, destination)
    primary = pd.read_csv(primary_path)
    sensitivity = pd.read_csv(sensitivity_path)
    metric_rows, exposure_rows = sem.summarize_primary(primary, args.method_name, "causal intervention")
    sensitivity_rows = sem.summarize_sensitivity(sensitivity, args.method_name)
    payload = {
        "status": "complete",
        "intervention": args.intervention,
        "method": args.method_name,
        "metrics": metric_rows,
        "exposures": exposure_rows,
        "sensitivity": sensitivity_rows,
    }
    (root / "intervention_summary.json").write_text(
        json.dumps(payload, indent=2, allow_nan=False), encoding="utf-8",
    )
    print(json.dumps(payload, indent=2), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

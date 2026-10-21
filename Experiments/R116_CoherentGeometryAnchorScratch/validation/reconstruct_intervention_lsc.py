"""Reconstruct the Raw-locked LSC frame subset with one R116 intervention."""

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

V42_CONFIG = Path(r"D:\GMM_2_Final\Thesis_MOSR_Evidence\Final_Data_Figures\01_CURRENT_THESIS_RESULTS_V42_CENTER9\config\sequence_center9_50x20x.json")
TOP30 = Path(r"D:\GMM_2_Final\Thesis_MOSR_Evidence\Final_Data_Figures\04_V42_NEURAL_NETWORK_RESULTS\tables\top30_raw_motion_selection.csv")
SEQUENCE_MAP = {
    "50x_x_0p5um": "50x_0p5um",
    "50x_x_1um": "50x_1um",
    "20x_0p5um": "20x_0p5um",
    "20x_1um": "20x_1um",
}


def read_gray(path: Path) -> np.ndarray:
    value = cv2.imdecode(np.fromfile(str(path), np.uint8), cv2.IMREAD_GRAYSCALE)
    if value is None:
        raise RuntimeError(f"Could not read {path}")
    return value


def write_gray(path: Path, value: np.ndarray) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    ok, encoded = cv2.imencode(".bmp", value.astype(np.uint8))
    if not ok:
        raise RuntimeError(f"Could not encode {path}")
    encoded.tofile(str(path))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--checkpoint", required=True)
    parser.add_argument("--intervention", required=True, choices=MODES)
    parser.add_argument("--output", required=True)
    parser.add_argument("--device", default="cuda:0")
    args = parser.parse_args()
    destination = Path(args.output).resolve()
    os.environ["R116_INTERVENTION_MODE"] = args.intervention
    device = torch.device(args.device)
    model = intervention_adapter.load_model(args.checkpoint, device)
    config = json.loads(V42_CONFIG.read_text(encoding="utf-8"))
    selected = pd.read_csv(TOP30)
    selected = selected.loc[
        selected["top30_raw_motion_selected"].astype(str).str.lower().isin({"true", "1", "yes"})
    ]
    count = 0
    for sequence, destination_name in SEQUENCE_MAP.items():
        rows = selected.loc[selected["sequence"].eq(sequence)]
        indices = sorted(set(rows["end_frame_index"].astype(int)) | set(rows["end_frame_index"].astype(int) - 1))
        raw_dir = Path(config["sequences"][sequence]["raw_dir"])
        for frame_index in indices:
            source = raw_dir / f"frame_{frame_index:04d}.bmp"
            raw = read_gray(source)
            tensor = torch.from_numpy(raw.astype(np.float32) / 255.0)[None, None].to(device)
            with torch.inference_mode():
                prediction = intervention_adapter.predict_canonical_tiled(
                    model, tensor,
                    intervention_adapter.canonical_tile_config(model, core=1024, halo=224),
                )
            output = np.rint(prediction.output[0, 0].clamp(0, 1).cpu().numpy() * 255.0).astype(np.uint8)
            write_gray(destination / destination_name / source.name, output)
            count += 1
            if count % 10 == 0:
                print(json.dumps({"mode": args.intervention, "completed": count}), flush=True)
    manifest = {"status": "complete", "intervention": args.intervention, "frames": count}
    (destination / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps(manifest), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

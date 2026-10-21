"""Post-training, no-retraining PSF switch and candidate sensitivity on four real frames."""
from __future__ import annotations

import sys
import types
from pathlib import Path

import cv2
import numpy as np
import pandas as pd
import torch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from evaluation.measurement_interface import measure_image
from model import Model
from utils import load, model_config, now, save, setup, sha


def main() -> None:
    cp_path = ROOT / "runs/formal_8192/checkpoints/step08192.pth"
    complete = load(ROOT / "runs/formal_8192/training_complete.json")
    assert complete["updates"] == 8192 and sha(cp_path) == complete["checkpoint"]["sha256"]
    setup(1309001)
    device = "cuda" if torch.cuda.is_available() else "cpu"
    model = Model(model_config(), ROOT).to(device).eval()
    model.load_state_dict(torch.load(cp_path, map_location="cpu", weights_only=False)["model"], strict=True)
    plan = load(ROOT / "evaluation/capture_plan.json")
    cfg = load(ROOT / "evaluation/measurement_config.json")
    tracking = pd.read_csv(ROOT / "evaluation/tracking.csv")
    block = model.refiner.optics
    original_select = block.select
    output = []
    for frame_no in (0, 30, 899, 929):
        frame = plan["frames"][frame_no]
        raw = cv2.imread(frame["source"]["path"], cv2.IMREAD_UNCHANGED)
        x = torch.from_numpy(raw.astype(np.float32)[None, None] / 255).to(device)
        seeds = tracking[(tracking.run == frame["run"]) & (tracking["index"] == frame["index"])].sort_values("pillar_id")[["seed_x_px", "seed_y_px"]].to_numpy()
        result = {}
        with torch.inference_mode():
            on = model(x)
            result["selected_indices"] = block.last_indices[0].cpu().tolist()
            model.optical_enabled = False
            off = model(x)
            model.optical_enabled = True
            forced = {}
            for index in (0, 24):
                def select_force(self, features, chosen=index):
                    weights = torch.zeros((features.shape[0], self.expected_count), device=features.device)
                    weights[:, chosen] = 1
                    indices = torch.full((features.shape[0], 1), chosen, dtype=torch.long, device=features.device)
                    self.last_indices = indices
                    self.last_sparse_weights = weights
                    return weights, indices
                block.select = types.MethodType(select_force, block)
                forced[index] = model(x)
            block.select = original_select
        def rms_gray(a, b):
            return float((a-b).square().mean().sqrt()*255)
        result.update(frame_no=frame_no, run=frame["run"], index=frame["index"],
                      on_off_rms_gray=rms_gray(on, off),
                      forced_0_vs_24_rms_gray=rms_gray(forced[0], forced[24]),
                      selected_vs_forced_0_rms_gray=rms_gray(on, forced[0]))
        measures = {}
        for name, tensor in (("on", on), ("off", off), ("psf0", forced[0]), ("psf24", forced[24])):
            rows, _ = measure_image(tensor.cpu().numpy()[0, 0].astype(np.float64), seeds, cfg)
            measures[name] = np.array([[r["center_x_px"], r["center_y_px"], r["radius_px"]] for r in rows])
        result["on_off_center_rms_nm"] = float(np.sqrt(np.mean((measures["on"][:, :2]-measures["off"][:, :2])**2))*172.5)
        result["psf0_psf24_center_rms_nm"] = float(np.sqrt(np.mean((measures["psf0"][:, :2]-measures["psf24"][:, :2])**2))*172.5)
        output.append(result)
        print("PSF_PROBE", frame_no, result["on_off_rms_gray"], result["forced_0_vs_24_rms_gray"], flush=True)
    save(ROOT / "results/real_psf_effect.json",
         dict(model=model_config()["model_name"], checkpoint_sha256=sha(cp_path),
              script_sha256=sha(Path(__file__)),
              note="Frozen trained model, in-memory switch only; not retrained ablation",
              frames=output, completed_utc=now()))


if __name__ == "__main__":
    main()

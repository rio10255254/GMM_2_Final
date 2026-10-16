"""Measure the trained optical branch's actual effect across twelve real frames."""
from __future__ import annotations

import sys
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


FRAME_NUMBERS = (0, 30, 100, 130, 300, 330, 500, 530, 700, 730, 899, 929)


def main() -> None:
    setup(1309001)
    cfg = model_config()
    path = ROOT / "runs/formal_8192/checkpoints/step08192.pth"
    cp = torch.load(path, map_location="cpu", weights_only=False)
    assert cp["checkpoint_kind"] == "trained_model"
    assert cp["bank_sha256"] == sha(ROOT / cfg["psf_bank"])
    device = "cuda" if torch.cuda.is_available() else "cpu"
    model = Model(cfg, ROOT).to(device).eval()
    model.load_state_dict(cp["model"], strict=True)
    plan = load(ROOT / "evaluation/capture_plan.json")
    measure_cfg = load(ROOT / "evaluation/measurement_config.json")
    tracking = pd.read_csv(ROOT / "evaluation/tracking.csv")
    rows = []
    for frame_no in FRAME_NUMBERS:
        frame = plan["frames"][frame_no]
        raw = cv2.imread(frame["source"]["path"], cv2.IMREAD_GRAYSCALE)
        assert raw is not None and raw.shape == (1544, 2064)
        x = torch.from_numpy(raw.astype(np.float32)[None, None] / 255).to(device)
        selected = tracking[(tracking.run == frame["run"]) & (tracking["index"] == frame["index"])]
        seeds = selected.sort_values("pillar_id")[["seed_x_px", "seed_y_px"]].to_numpy()
        feature = {}

        def capture(_module, input_tuple, output):
            incoming = input_tuple[0].float()
            feature["input_rms"] = float(incoming.square().mean().sqrt())
            feature["change_rms"] = float((output.float()-incoming).square().mean().sqrt())

        hook = model.refiner.optics.register_forward_hook(capture)
        with torch.inference_mode():
            on = model(x)
        hook.remove()
        assert feature
        indices = model.refiner.optics.last_indices[0].cpu().tolist()
        model.optical_enabled = False
        with torch.inference_mode():
            off = model(x)
        model.optical_enabled = True
        on_image = on.cpu().numpy()[0, 0].astype(np.float64)
        off_image = off.cpu().numpy()[0, 0].astype(np.float64)
        on_circles, _ = measure_image(on_image, seeds, measure_cfg)
        off_circles, _ = measure_image(off_image, seeds, measure_cfg)
        on_values = np.asarray([[r["center_x_px"], r["center_y_px"], r["radius_px"]] for r in on_circles])
        off_values = np.asarray([[r["center_x_px"], r["center_y_px"], r["radius_px"]] for r in off_circles])
        centers_nm = np.linalg.norm(on_values[:, :2]-off_values[:, :2], axis=1)*172.5
        diameter_nm = (on_values[:, 2]-off_values[:, 2])*345
        rows.append(dict(frame_no=frame_no, run=frame["run"], index=frame["index"],
                         selected_indices=indices,
                         image_rms_difference_gray=float(np.sqrt(np.mean((on_image-off_image)**2))*255),
                         mean_center_difference_nm=float(centers_nm.mean()),
                         max_center_difference_nm=float(centers_nm.max()),
                         mean_diameter_difference_nm=float(diameter_nm.mean()),
                         max_absolute_diameter_difference_nm=float(np.abs(diameter_nm).max()),
                         feature_input_rms=feature["input_rms"],
                         feature_change_rms=feature["change_rms"],
                         feature_relative_change=feature["change_rms"]/feature["input_rms"]))
        print("FRAME", frame_no, rows[-1]["mean_center_difference_nm"],
              rows[-1]["mean_diameter_difference_nm"], flush=True)
    out = ROOT / "results/deep_diagnosis"
    out.mkdir(parents=True, exist_ok=True)
    save(out / "optical_branch_12.json", dict(frames=rows, checkpoint_sha256=sha(path),
                                               script_sha256=sha(Path(__file__)), completed_utc=now()))
    print("SUMMARY", dict(frames=len(rows),
                          median_image_rms_gray=float(np.median([x["image_rms_difference_gray"] for x in rows])),
                          max_center_nm=max(x["max_center_difference_nm"] for x in rows),
                          max_diameter_nm=max(x["max_absolute_diameter_difference_nm"] for x in rows),
                          median_feature_relative_change=float(np.median([x["feature_relative_change"] for x in rows]))),
          flush=True)


if __name__ == "__main__":
    main()

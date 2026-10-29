"""Fourier-shift robustness check for subpixel movement of real frames."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import cv2
import numpy as np
import pandas as pd
import torch
from scipy.ndimage import fourier_shift
PROJECT_ROOT = Path(__file__).resolve().parents[3]

R143 = Path(str(PROJECT_ROOT / 'Experiments/R143_PSF25_MatchedPairs'))
R140 = Path(str(PROJECT_ROOT / 'Experiments/R140v2_StableUNet'))
FRAMES = (0, 744, 899)
SHIFTS_X_PX = (0.0, .2, .4, .6, .8, 1.0)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", required=True, choices=("r140", "r143"))
    args = parser.parse_args()
    package = R140 if args.model == "r140" else R143
    sys.path.insert(0, str(package))
    from utils import setup, sha, now, save, model_config
    from evaluation.measurement_interface import measure_image
    setup(1309001)
    cv2.setNumThreads(1)
    checkpoint = package / "runs/formal_8192/checkpoints/step08192.pth"
    if args.model == "r140":
        from infer_model import load_own_model
        model, _ = load_own_model(checkpoint)
    else:
        from model import Model
        model = Model(model_config(), package).to("cuda").eval()
        model.load_state_dict(torch.load(checkpoint, map_location="cpu", weights_only=False)["model"], strict=True)
    capture = json.loads((R143 / "evaluation/capture_plan.json").read_text(encoding="utf-8"))
    cfg = json.loads((R143 / "evaluation/measurement_config.json").read_text(encoding="utf-8"))
    cal = json.loads((R143 / "evaluation/calibration.json").read_text(encoding="utf-8"))
    u = np.asarray(cal["axis_unit_vector"])
    tracking = pd.read_csv(R143 / "evaluation/tracking.csv")
    records = []
    with torch.inference_mode():
        for frame_no in FRAMES:
            frame = capture["frames"][frame_no]
            raw = cv2.imread(frame["source"]["path"], cv2.IMREAD_GRAYSCALE).astype(np.float32) / 255
            padded = np.pad(raw, ((32,32),(32,32)), mode="reflect")
            spectrum = np.fft.fft2(padded)
            original_seeds = tracking[(tracking.run == frame["run"]) &
                                      (tracking["index"] == frame["index"])].sort_values("pillar_id")[["seed_x_px", "seed_y_px"]].to_numpy()
            model_origin = raw_origin = None
            for dx in SHIFTS_X_PX:
                shifted = np.fft.ifft2(fourier_shift(spectrum, (0,dx))).real[32:-32,32:-32]
                shifted = np.clip(shifted, 0, 1).astype(np.float32)
                seeds = original_seeds + np.array([dx, 0])
                raw_rows, _ = measure_image(shifted.astype(np.float64), seeds, cfg)
                x = torch.from_numpy(shifted[None, None]).to("cuda")
                restored = model(x).cpu().numpy()[0, 0].astype(np.float64)
                model_rows, _ = measure_image(restored, seeds, cfg)
                raw_centers = np.array([[r["center_x_px"], r["center_y_px"]] for r in raw_rows])
                model_centers = np.array([[r["center_x_px"], r["center_y_px"]] for r in model_rows])
                if dx == 0:
                    model_origin = model_centers
                    raw_origin = raw_centers
                expected = dx*u[0]*172.5
                model_error = float(np.dot(np.median(model_centers-model_origin,axis=0),u)*172.5 - expected)
                raw_error = float(np.dot(np.median(raw_centers-raw_origin,axis=0),u)*172.5 - expected)
                model_minus_raw = float(np.dot(np.median(model_centers-raw_centers,axis=0),u)*172.5)
                records.append(dict(frame_no=frame_no, run=frame["run"], index=frame["index"],
                                    shift_x_px=dx, model_shift_error_nm=model_error,
                                    raw_shift_error_nm=raw_error,
                                    model_minus_raw_center_nm=model_minus_raw))
                print("SUBPIXEL", args.model, frame_no, dx, flush=True)
    dest = R143 / "results/stability_diagnosis"
    dest.mkdir(exist_ok=True)
    save(dest / ("subpixel_fourier_" + args.model + ".json"),
         dict(model=args.model, checkpoint_sha256=sha(checkpoint),
              script_sha256=sha(Path(__file__)),
              note="same real image shifted on reflected padded Fourier grid; diagnostic only",
              frames=list(FRAMES), shifts_x_px=list(SHIFTS_X_PX),
              rows=records, completed_utc=now()))
    print("SUBPIXEL_PROBE_COMPLETE", args.model)


if __name__ == "__main__":
    main()

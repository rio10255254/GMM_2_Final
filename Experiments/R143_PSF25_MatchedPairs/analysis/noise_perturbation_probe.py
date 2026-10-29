"""Matched added-noise test for frozen R140v2 or R143 real-image localization.

This is a diagnostic on selected pairs, not a replacement for the 30-scan
evaluation. Both models receive the same deterministic quantized noise draws.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import cv2
import numpy as np
import pandas as pd
import torch
PROJECT_ROOT = Path(__file__).resolve().parents[3]

R143 = Path(str(PROJECT_ROOT / 'Experiments/R143_PSF25_MatchedPairs'))
R140 = Path(str(PROJECT_ROOT / 'Experiments/R140v2_StableUNet'))
PAIRS = ((0, 1), (899, 900), (924, 925))
NOISE_SIGMA_GRAY = 1.5
REPEATS = 8


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
    if args.model == "r140":
        from infer_model import load_own_model
        checkpoint = package / "runs/formal_8192/checkpoints/step08192.pth"
        model, _ = load_own_model(checkpoint)
    else:
        from model import Model
        checkpoint = package / "runs/formal_8192/checkpoints/step08192.pth"
        model = Model(model_config(), package).to("cuda").eval()
        model.load_state_dict(torch.load(checkpoint, map_location="cpu", weights_only=False)["model"], strict=True)
    import json
    capture = json.loads((R143 / "evaluation/capture_plan.json").read_text(encoding="utf-8"))
    config = json.loads((R143 / "evaluation/measurement_config.json").read_text(encoding="utf-8"))
    cal = json.loads((R143 / "evaluation/calibration.json").read_text(encoding="utf-8"))
    u = np.array(cal["axis_unit_vector"])
    tracking = pd.read_csv(R143 / "evaluation/tracking.csv")
    records = []
    with torch.inference_mode():
        for pair_no, (first, second) in enumerate(PAIRS):
            frames = [capture["frames"][first], capture["frames"][second]]
            assert frames[0]["run"] == frames[1]["run"]
            pi = frames[1]["pi_y_um"] - frames[0]["pi_y_um"]
            errors = []
            for repeat in range(REPEATS):
                centers = []
                for frame_no, frame in zip((first, second), frames):
                    raw = cv2.imread(frame["source"]["path"], cv2.IMREAD_GRAYSCALE)
                    rng = np.random.default_rng(14300000 + frame_no * 100 + repeat)
                    noisy = np.rint(np.clip(raw.astype(float) + rng.normal(0, NOISE_SIGMA_GRAY, raw.shape), 0, 255)).astype(np.uint8)
                    image = torch.from_numpy(noisy.astype(np.float32)[None, None] / 255).to("cuda")
                    output = model(image).cpu().numpy()[0, 0].astype(np.float64)
                    seeds = tracking[(tracking.run == frame["run"]) &
                                     (tracking["index"] == frame["index"])].sort_values("pillar_id")[["seed_x_px", "seed_y_px"]].to_numpy()
                    rows, _ = measure_image(output, seeds, config)
                    centers.append(np.array([[row["center_x_px"], row["center_y_px"]] for row in rows]))
                delta = np.median(centers[1] - centers[0], axis=0)
                errors.append(float((np.dot(delta, u) * .1725 - pi) * 1000))
                print("NOISE", args.model, pair_no, repeat + 1, "/", REPEATS, flush=True)
            records.append(dict(frame_pair=[first, second], run=frames[0]["run"],
                                steps=[frames[0]["index"], frames[1]["index"]],
                                errors_nm=errors, mean_error_nm=float(np.mean(errors)),
                                noise_induced_sd_nm=float(np.std(errors, ddof=1))))
    dest = R143 / "results/stability_diagnosis"
    dest.mkdir(exist_ok=True)
    save(dest / ("noise_probe_" + args.model + ".json"),
         dict(model=args.model, checkpoint_sha256=sha(checkpoint),
              script_sha256=sha(Path(__file__)), noise_sigma_gray=NOISE_SIGMA_GRAY,
              repeats=REPEATS, note="selected real pairs with added quantized noise; no model changes",
              pairs=records, completed_utc=now()))
    print("NOISE_PROBE_COMPLETE", args.model)


if __name__ == "__main__":
    main()

"""Controlled broad-halo blur response of reconstructed circle edge width."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import cv2
import numpy as np
import pandas as pd
import torch
from scipy.ndimage import gaussian_filter1d, map_coordinates

R143 = Path(r"D:\GMM_2_Final\Experiments\R143_PSF25_MatchedPairs")
R140 = Path(r"D:\GMM_2_Final\Experiments\R140v2_StableUNet")
PAIRS = ((0, 1), (12, 13))
LEVELS = (0.0, 0.25, 0.5)
ANGLES = np.linspace(0, 2*np.pi, 64, endpoint=False)
RADII = np.arange(4.0, 13.01, .1)


def edge_width(image: np.ndarray, rows: list[dict]) -> float:
    widths = []
    for row in rows:
        cx, cy = float(row["center_x_px"]), float(row["center_y_px"])
        xx = cx+np.cos(ANGLES[:,None])*RADII[None,:]
        yy = cy+np.sin(ANGLES[:,None])*RADII[None,:]
        values = map_coordinates(image, [yy.ravel(),xx.ravel()],order=1,mode="reflect").reshape(len(ANGLES),len(RADII))
        radial = gaussian_filter1d(np.median(values,axis=0),1.0)
        dark = float(np.mean(radial[RADII<=5]));light=float(np.mean(radial[RADII>=11.5]))
        profile = (radial-dark)/max(light-dark,1e-8)
        def crossing(level):
            ids=np.flatnonzero((RADII>=5)&(RADII<=11.5)&(profile>=level))
            j=int(ids[0]);fraction=(level-profile[j-1])/max(profile[j]-profile[j-1],1e-8)
            return RADII[j-1]+fraction*(RADII[j]-RADII[j-1])
        widths.append(float(crossing(.8)-crossing(.2)))
    return float(np.mean(widths))


def local_contrast(image: np.ndarray, seeds: np.ndarray) -> float:
    values = []
    for x, y in seeds:
        xx = np.arange(int(round(x)) - 14, int(round(x)) + 15)
        yy = np.arange(int(round(y)) - 14, int(round(y)) + 15)
        patch = image[np.ix_(yy, xx)]
        radius = np.hypot(xx[None, :] - x, yy[:, None] - y)
        values.append(float(np.median(patch[(radius >= 10.5) & (radius <= 13.5)]) -
                            np.median(patch[radius <= 5.5])))
    return float(np.median(values))


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
    plan = json.loads((R143 / "evaluation/capture_plan.json").read_text(encoding="utf-8"))
    cfg = json.loads((R143 / "evaluation/measurement_config.json").read_text(encoding="utf-8"))
    cal = json.loads((R143 / "evaluation/calibration.json").read_text(encoding="utf-8"))
    u = np.asarray(cal["axis_unit_vector"])
    tracking = pd.read_csv(R143 / "evaluation/tracking.csv")
    results = []
    with torch.inference_mode():
        for first, second in PAIRS:
            frames = [plan["frames"][first], plan["frames"][second]]
            assert frames[0]["run"] == frames[1]["run"]
            truth = frames[1]["pi_y_um"] - frames[0]["pi_y_um"]
            for level in LEVELS:
                centers = []
                diameters = []
                shifts = []
                contrasts = []
                output_widths = []
                raw_widths = []
                for frame in frames:
                    raw = cv2.imread(frame["source"]["path"], cv2.IMREAD_GRAYSCALE).astype(np.float64)
                    broad = cv2.GaussianBlur(raw.astype(np.float32), (0, 0), 5.0).astype(np.float64)
                    transformed = np.rint(np.clip((1-level)*raw + level*broad, 0, 255)).astype(np.uint8)
                    seeds = tracking[(tracking.run == frame["run"]) &
                                     (tracking["index"] == frame["index"])].sort_values("pillar_id")[["seed_x_px", "seed_y_px"]].to_numpy()
                    contrasts.append(local_contrast(transformed, seeds))
                    raw_rows, _ = measure_image(transformed.astype(np.float64)/255, seeds, cfg)
                    x = torch.from_numpy(transformed.astype(np.float32)[None, None]/255).to("cuda")
                    image = model(x).cpu().numpy()[0, 0].astype(np.float64)
                    rows, _ = measure_image(image, seeds, cfg)
                    output_widths.append(edge_width(image*255, rows))
                    raw_widths.append(edge_width(transformed.astype(np.float64), raw_rows))
                    model_centers = np.array([[r["center_x_px"], r["center_y_px"]] for r in rows])
                    raw_centers = np.array([[r["center_x_px"], r["center_y_px"]] for r in raw_rows])
                    centers.append(model_centers)
                    diameters.append(float(np.mean([2*r["radius_px"]*172.5 for r in rows])))
                    shifts.append(float(np.median((model_centers-raw_centers)@u)*172.5))
                v = np.median(centers[1]-centers[0], axis=0)
                error = (np.dot(v,u)*.1725-truth)*1000
                results.append(dict(frame_pair=[first, second], run=frames[0]["run"],
                                    level=level, contrast_gray=float(np.mean(contrasts)),
                                    diameter_mean_nm=float(np.mean(diameters)),
                                    output_edge_width_px=float(np.mean(output_widths)),
                                    raw_edge_width_px=float(np.mean(raw_widths)),
                                    model_minus_raw_center_shift_nm=float(np.mean(shifts)),
                                    adjacent_PI_error_nm=float(error)))
                print("BLUR_EDGE", args.model, first, level, flush=True)
    dest = R143 / "results/stability_diagnosis"
    dest.mkdir(exist_ok=True)
    save(dest / ("blur_edge_probe_" + args.model + ".json"),
         dict(model=args.model, checkpoint_sha256=sha(checkpoint),
              script_sha256=sha(Path(__file__)),
              note="fixed frames with artificial sigma5 broad-halo mixture; diagnostic only",
              pairs=[list(x) for x in PAIRS], levels=list(LEVELS),
              rows=results, completed_utc=now()))
    print("BLUR_EDGE_PROBE_COMPLETE", args.model)


if __name__ == "__main__":
    main()

"""Measure saved reconstructed circle edge width without changing the LSC reader."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.ndimage import gaussian_filter1d, map_coordinates
PROJECT_ROOT = Path(__file__).resolve().parents[3]

ROOT = Path(__file__).resolve().parents[1]
R140 = Path(str(PROJECT_ROOT / 'Experiments/R140v2_StableUNet'))
sys.path.insert(0, str(ROOT / "analysis"))
from measure_raw_edge_width import ANGLES, RADII, crossing
sys.path.insert(0, str(ROOT))
from utils import now, save


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", choices=("r140", "r143"), required=True)
    args = parser.parse_args()
    base = R140 if args.model == "r140" else ROOT
    tag = "R140v2-StableUNet" if args.model == "r140" else "R143-PSF25-MatchedPairs"
    plan = json.loads((ROOT / "evaluation/capture_plan.json").read_text(encoding="utf-8"))
    circles = pd.read_csv(ROOT / "results/comparison/all_circles.csv")
    circles = circles[circles.model == tag].set_index(["run", "index", "pillar_id"]).sort_index()
    rows = []
    for n, frame in enumerate(plan["frames"], 1):
        path = base / "results/reconstruction" / frame["run"] / f"{frame['index']+1:02d}.npz"
        with np.load(path, allow_pickle=False) as z:
            image = z["output"].astype(np.float32)*255
        for pillar in range(1, 10):
            circle = circles.loc[(frame["run"], frame["index"], pillar)]
            cx, cy = float(circle.center_x_px), float(circle.center_y_px)
            xx = cx+np.cos(ANGLES[:, None])*RADII[None, :]
            yy = cy+np.sin(ANGLES[:, None])*RADII[None, :]
            p = map_coordinates(image, [yy.ravel(), xx.ravel()], order=1, mode="reflect").reshape(len(ANGLES), len(RADII))
            profile = gaussian_filter1d(np.median(p, axis=0), 1.0)
            dark = float(np.mean(profile[RADII <= 5]))
            light = float(np.mean(profile[RADII >= 11.5]))
            contrast = light-dark
            normalized = (profile-dark)/max(contrast, 1e-8)
            r20 = crossing(RADII, normalized, .2)
            r50 = crossing(RADII, normalized, .5)
            r80 = crossing(RADII, normalized, .8)
            rows.append(dict(run=frame["run"], run_index=frame["run_index"], index=frame["index"],
                             pillar_id=pillar, edge_width_px=r80-r20,
                             r50_px=r50, edge_contrast_gray=contrast))
        if n % 100 == 0:
            print("OUTPUT_EDGE", args.model, n, "/ 930", flush=True)
    dest = ROOT / "results/stability_diagnosis"
    dest.mkdir(exist_ok=True)
    data = pd.DataFrame(rows)
    data.to_csv(dest / ("output_edge_width_" + args.model + ".csv"), index=False)
    save(dest / ("output_edge_width_" + args.model + "_complete.json"),
         dict(model=tag, circles=len(rows), finite_widths=int(np.isfinite(data.edge_width_px).sum()),
              mean_width_px=float(np.nanmean(data.edge_width_px)), completed_utc=now()))
    print("OUTPUT_EDGE_COMPLETE", args.model, len(rows))


if __name__ == "__main__":
    main()

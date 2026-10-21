"""Read fixed nine-pillar raw patches for stability diagnosis only."""
from __future__ import annotations

import sys
from pathlib import Path

import cv2
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from utils import load, save, now


def main() -> None:
    plan = load(ROOT / "evaluation/capture_plan.json")
    tracking = pd.read_csv(ROOT / "evaluation/tracking.csv")
    rows = []
    for n, frame in enumerate(plan["frames"], 1):
        image = cv2.imread(frame["source"]["path"], cv2.IMREAD_GRAYSCALE)
        if image is None or image.shape != (1544, 2064):
            raise RuntimeError("Capture unavailable: " + frame["source"]["path"])
        seeds = tracking[(tracking.run == frame["run"]) &
                         (tracking["index"] == frame["index"])].sort_values("pillar_id")
        assert len(seeds) == 9
        background = []
        center = []
        contrast = []
        local_std = []
        for seed in seeds.itertuples():
            x, y = float(seed.seed_x_px), float(seed.seed_y_px)
            xx = np.arange(int(round(x)) - 14, int(round(x)) + 15)
            yy = np.arange(int(round(y)) - 14, int(round(y)) + 15)
            patch = image[np.ix_(yy, xx)].astype(float)
            rad = np.hypot(xx[None, :] - x, yy[:, None] - y)
            core = patch[rad <= 5.5]
            bg = patch[(rad >= 10.5) & (rad <= 13.5)]
            background.append(float(np.median(bg)))
            center.append(float(np.median(core)))
            contrast.append(float(np.median(bg) - np.median(core)))
            local_std.append(float(patch.std()))
        rows.append(dict(run=frame["run"], run_index=frame["run_index"], index=frame["index"],
                         background_gray=float(np.median(background)),
                         center_gray=float(np.median(center)),
                         contrast_gray=float(np.median(contrast)),
                         local_std_gray=float(np.median(local_std)),
                         full_mean_gray=float(image.mean()), full_std_gray=float(image.std())))
        if n % 100 == 0:
            print("RAW_PHOTOMETRY", n, "/ 930", flush=True)
    output = ROOT / "results/stability_diagnosis"
    output.mkdir(exist_ok=True)
    pd.DataFrame(rows).to_csv(output / "raw_photometry.csv", index=False)
    save(output / "raw_photometry_complete.json",
         dict(frames=len(rows), measured_pillars=9, core_radius_px=5.5,
              annulus_radius_px=[10.5, 13.5], completed_utc=now()))


if __name__ == "__main__":
    main()

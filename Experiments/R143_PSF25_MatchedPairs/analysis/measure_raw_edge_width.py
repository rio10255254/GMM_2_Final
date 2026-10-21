"""Measure raw circle edge width across the fixed 30-scan capture set."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import cv2
import numpy as np
import pandas as pd
from scipy.ndimage import gaussian_filter1d, map_coordinates

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from utils import now, save


ANGLES = np.linspace(0, 2*np.pi, 64, endpoint=False)
RADII = np.arange(4.0, 13.01, .1)


def crossing(radius: np.ndarray, value: np.ndarray, level: float) -> float:
    ids = np.flatnonzero((radius >= 5.0) & (radius <= 11.5) & (value >= level))
    if not len(ids):
        return float("nan")
    j = int(ids[0])
    if j == 0:
        return float(radius[0])
    frac = (level - value[j-1]) / max(value[j] - value[j-1], 1e-8)
    return float(radius[j-1] + frac*(radius[j] - radius[j-1]))


def main() -> None:
    plan = json.loads((ROOT / "evaluation/capture_plan.json").read_text(encoding="utf-8"))
    centers = {}
    for run in plan["runs"]:
        name = run["run"]
        table = pd.read_csv(ROOT / "evaluation/baseline_centers/Raw" / (name + ".csv"))
        centers[name] = table.set_index(["index", "pillar_id"])
    rows = []
    for n, frame in enumerate(plan["frames"], 1):
        image = cv2.imread(frame["source"]["path"], cv2.IMREAD_GRAYSCALE)
        if image is None:
            raise RuntimeError("Missing source " + frame["source"]["path"])
        image = image.astype(np.float32)
        table = centers[frame["run"]]
        for pillar in range(1, 10):
            circle = table.loc[(frame["index"], pillar)]
            x = float(circle.center_x_px) + np.cos(ANGLES[:, None])*RADII[None, :]
            y = float(circle.center_y_px) + np.sin(ANGLES[:, None])*RADII[None, :]
            profile = map_coordinates(image, [y.ravel(), x.ravel()], order=1, mode="reflect").reshape(len(ANGLES), len(RADII))
            radial = gaussian_filter1d(np.median(profile, axis=0), 1.0)
            dark = float(np.mean(radial[RADII <= 5]))
            light = float(np.mean(radial[RADII >= 11.5]))
            contrast = light-dark
            normalized = (radial-dark)/max(contrast, 1e-8)
            r20 = crossing(RADII, normalized, .2)
            r50 = crossing(RADII, normalized, .5)
            r80 = crossing(RADII, normalized, .8)
            width = r80-r20
            rows.append(dict(run=frame["run"], run_index=frame["run_index"],
                             index=frame["index"], pillar_id=pillar,
                             edge_width_px=width, r50_px=r50,
                             edge_contrast_gray=contrast,
                             normalized_peak_slope_per_px=float(np.max(np.gradient(normalized, RADII)))))
        if n % 100 == 0:
            print("RAW_EDGE", n, "/ 930", flush=True)
    dest = ROOT / "results/stability_diagnosis"
    dest.mkdir(exist_ok=True)
    data = pd.DataFrame(rows)
    data.to_csv(dest / "raw_edge_width.csv", index=False)
    save(dest / "raw_edge_width_complete.json",
         dict(circles=len(rows), finite_widths=int(np.isfinite(data.edge_width_px).sum()),
              median_width_px=float(np.nanmedian(data.edge_width_px)),
              completed_utc=now()))
    print("RAW_EDGE_COMPLETE", len(rows), "finite", int(np.isfinite(data.edge_width_px).sum()))


if __name__ == "__main__":
    main()

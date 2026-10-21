"""Compare output edge position and transition width on all fixed real circles."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.ndimage import gaussian_filter1d, map_coordinates

ROOT = Path(__file__).resolve().parents[1]
R145 = ROOT.parent / "R145_Center9PSF25_CorrectedPairs"
sys.path.insert(0, str(ROOT))
from utils import load, now, save, sha

ANGLES = np.linspace(0, 2*np.pi, 64, endpoint=False)
RADII = np.arange(4, 13.01, .1)
MODELS = {"R145-Center9PSF25-CorrectedPairs": R145,
          "R146-SEMCoreHaloPSF25-MatchedPairs": ROOT}


def crossing(value: np.ndarray, level: float) -> float:
    ids = np.flatnonzero((RADII >= 5) & (RADII <= 11.5) & (value >= level))
    if not len(ids):
        return float("nan")
    j = int(ids[0])
    return float(RADII[j-1]+(level-value[j-1])*(RADII[j]-RADII[j-1]) /
                 max(value[j]-value[j-1], 1e-8))


def main() -> None:
    plan = load(ROOT / "evaluation/capture_plan.json")
    circles = pd.read_csv(ROOT / "results/comparison/all_circles.csv")
    circles = circles[circles.model.isin(MODELS)].set_index(["model", "run", "index", "pillar_id"]).sort_index()
    rows = []
    for model, package in MODELS.items():
        for count, frame in enumerate(plan["frames"], 1):
            path = package / "results/reconstruction" / frame["run"] / f"{frame['index']+1:02d}.npz"
            with np.load(path, allow_pickle=False) as z:
                image = z["output"].astype(np.float32)*255
            for pillar in range(1, 10):
                circle = circles.loc[(model, frame["run"], frame["index"], pillar)]
                cx, cy = float(circle.center_x_px), float(circle.center_y_px)
                xx = cx + np.cos(ANGLES[:, None])*RADII[None, :]
                yy = cy + np.sin(ANGLES[:, None])*RADII[None, :]
                samples = map_coordinates(image, [yy.ravel(), xx.ravel()], order=1,
                                          mode="reflect").reshape(len(ANGLES), len(RADII))
                profile = gaussian_filter1d(np.median(samples, axis=0), 1.0)
                dark = float(np.mean(profile[RADII <= 5]))
                light = float(np.mean(profile[RADII >= 11.5]))
                contrast = light-dark
                normalized = (profile-dark)/max(contrast, 1e-8)
                r20, r50, r80 = (crossing(normalized, level) for level in (.2, .5, .8))
                rows.append(dict(model=model, run=frame["run"], run_index=frame["run_index"],
                                 index=frame["index"], pillar_id=pillar,
                                 edge_width_px=r80-r20, r50_px=r50,
                                 edge_contrast_gray=contrast))
            if count % 100 == 0:
                print("EDGE", model, count, "/ 930", flush=True)
    table = pd.DataFrame(rows)
    assert len(table) == 2*8370 and table.edge_width_px.notna().all()
    destination = ROOT / "results/edge_response_r145_r146.csv"
    table.to_csv(destination, index=False)
    old = table[table.model == "R145-Center9PSF25-CorrectedPairs"].sort_values(["run", "index", "pillar_id"])
    new = table[table.model == "R146-SEMCoreHaloPSF25-MatchedPairs"].sort_values(["run", "index", "pillar_id"])
    summary = {}
    for model, group in (("R145", old), ("R146", new)):
        summary[model] = dict(circles=len(group), median_width_px=float(group.edge_width_px.median()),
                              mean_width_px=float(group.edge_width_px.mean()),
                              median_contrast_gray=float(group.edge_contrast_gray.median()),
                              mean_r50_px=float(group.r50_px.mean()),
                              repeat_r50_sd_px=float(np.sqrt(group.groupby(["index", "pillar_id"]).r50_px.var(ddof=1).mean())))
    r50_delta = new.r50_px.to_numpy()-old.r50_px.to_numpy()
    width_delta = new.edge_width_px.to_numpy()-old.edge_width_px.to_numpy()
    summary["R146_minus_R145"] = dict(mean_r50_change_px=float(r50_delta.mean()),
                                        mean_width_change_px=float(width_delta.mean()),
                                        positive_r50_fraction=float(np.mean(r50_delta > 0)),
                                        positive_width_fraction=float(np.mean(width_delta > 0)))
    output = dict(summary=summary, script_sha256=sha(Path(__file__)), completed_utc=now())
    save(ROOT / "results/edge_response_comparison.json", output)
    print("EDGE_COMPARISON", output, flush=True)


if __name__ == "__main__":
    main()

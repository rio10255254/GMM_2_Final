"""Compare local raw pillar appearance in PSF-fit and evaluation captures."""
from __future__ import annotations

import sys
from pathlib import Path

import cv2
import numpy as np
import pandas as pd
from scipy.ndimage import gaussian_filter1d, map_coordinates

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from utils import now, save, sha

PROJECT = Path(r"D:\GMM_2_Final")
FITTING = PROJECT / "PSF_Fitting/output/20260924_center9_psf"
R143 = PROJECT / "Experiments/R143_PSF25_MatchedPairs"
ANGLES = np.linspace(0, 2*np.pi, 64, endpoint=False)
RADII = np.arange(4.0, 13.01, .1)


def crossing(value: np.ndarray, level: float) -> float:
    matches = np.flatnonzero((RADII >= 5) & (RADII <= 11.5) & (value >= level))
    if not len(matches):
        return float("nan")
    j = int(matches[0])
    return float(RADII[j-1] + (level-value[j-1])*(RADII[j]-RADII[j-1]) /
                 max(value[j]-value[j-1], 1e-8))


def main() -> None:
    locations = pd.read_csv(FITTING / "center9_locations.csv")
    assert len(locations) == 225
    rows = []
    for image_index, group in locations.groupby("image_index"):
        path = PROJECT / "20260924" / group.image.iloc[0]
        image = cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)
        assert image is not None and image.shape == (1544, 2064)
        for row in group.itertuples():
            # Fitting coordinates are MATLAB one-based; image arrays are zero-based.
            x, y = float(row.x)-1, float(row.y)-1
            xx = np.arange(int(round(x))-14, int(round(x))+15)
            yy = np.arange(int(round(y))-14, int(round(y))+15)
            patch = image[np.ix_(yy, xx)].astype(float)
            radial_distance = np.hypot(xx[None, :]-x, yy[:, None]-y)
            core = np.median(patch[radial_distance <= 5.5])
            background = np.median(patch[(radial_distance >= 10.5) & (radial_distance <= 13.5)])
            sample_x = x + np.cos(ANGLES[:, None])*RADII[None, :]
            sample_y = y + np.sin(ANGLES[:, None])*RADII[None, :]
            sampled = map_coordinates(image.astype(float), [sample_y.ravel(), sample_x.ravel()],
                                      order=1, mode="reflect").reshape(len(ANGLES), len(RADII))
            profile = gaussian_filter1d(np.median(sampled, axis=0), 1.0)
            dark = float(np.mean(profile[RADII <= 5]))
            light = float(np.mean(profile[RADII >= 11.5]))
            normalized = (profile-dark)/max(light-dark, 1e-8)
            width = crossing(normalized, .8)-crossing(normalized, .2)
            rows.append(dict(image_index=int(image_index), source_image=group.image.iloc[0],
                             sem_id=int(row.sem_id_working), background_gray=float(background),
                             contrast_gray=float(background-core), edge_width_px=width))
    source = pd.DataFrame(rows)
    assert len(source) == 225 and source.edge_width_px.notna().all()
    out = ROOT / "results/deep_diagnosis"
    out.mkdir(parents=True, exist_ok=True)
    source.to_csv(out / "psf_fit_capture_appearance.csv", index=False)
    original = pd.read_csv(R143 / "results/stability_diagnosis/raw_photometry.csv")
    edge = pd.read_csv(R143 / "results/stability_diagnosis/raw_edge_width.csv")
    assert len(original) == 930 and len(edge) == 8370
    summary = dict(psf_fit_capture=dict(frames=25, pillars=225,
                                        median_background_gray=float(source.background_gray.median()),
                                        median_contrast_gray=float(source.contrast_gray.median()),
                                        median_edge_width_px=float(source.edge_width_px.median())),
                   fixed_real_evaluation=dict(frames=930, pillars=8370,
                                              median_background_gray=float(original.background_gray.median()),
                                              median_contrast_gray=float(original.contrast_gray.median()),
                                              median_edge_width_px=float(edge.edge_width_px.median()),
                                              early_five_scan_edge_width_px=float(edge[edge.run_index <= 5].edge_width_px.median()),
                                              late_five_scan_edge_width_px=float(edge[edge.run_index >= 26].edge_width_px.median())),
                   readout="identical local core, background annulus, and radial 20-80% edge width",
                   limitation="Different acquisition sessions; appearance difference does not uniquely identify optical cause",
                   source_locations_sha256=sha(FITTING / "center9_locations.csv"),
                   real_photometry_sha256=sha(R143 / "results/stability_diagnosis/raw_photometry.csv"),
                   script_sha256=sha(Path(__file__)), completed_utc=now())
    save(out / "capture_condition_shift.json", summary)
    print(summary, flush=True)


if __name__ == "__main__":
    main()

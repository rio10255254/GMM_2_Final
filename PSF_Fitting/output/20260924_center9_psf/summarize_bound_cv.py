"""Score fitted PSFs on the three pillars reserved from BADS fitting."""

from __future__ import annotations

import csv
import json
from pathlib import Path

import cv2
import numpy as np
from scipy.io import loadmat
from scipy.signal import fftconvolve


ROOT = Path(__file__).resolve().parent
LOWER = np.array([-.3, -.3, -.1, 0, -.1, -.05, -.05, -.05, -.05, -.01, -.01, 0, -.01, -.01, .8])
UPPER = np.array([.3, .3, .1, 1, .1, .05, .05, .05, .05, .01, .01, .3, .01, .01, 1.25])


def main():
    gt = cv2.imread(str(ROOT / "fit_input" / "GT" / "gt_sem_cd.bmp"), 0) / 255
    masks = {
        "train6": cv2.imread(str(ROOT / "fit_input" / "loss_mask_train6.bmp"), 0) > 0,
        "hold3": cv2.imread(str(ROOT / "fit_input" / "loss_mask_hold3.bmp"), 0) > 0,
    }
    rows = []
    for scale in [1, 2, 4, 8]:
        result = ROOT / f"cv_bounds_{scale}" / "PSF_fitted_2D_FOVstack.mat"
        data = loadmat(result)
        psfs = data["psf_grid"].reshape(101, 101, 3)
        coefs = data["coef_grid"].reshape(15, 3).T
        for j, frame in enumerate([1, 13, 25]):
            img = cv2.imread(str(ROOT / "fit_input" / f"fit_input_{frame:02d}.bmp"), 0) / 255
            psf = psfs[:, :, j]
            prediction = fftconvolve(gt, psf, mode="same")
            r = {"scale": scale, "frame": frame, "bads_loss_train6": float(data["fval_map"].ravel()[j])}
            for name, mask in masks.items():
                a, p = img[mask], prediction[mask]
                r[f"{name}_mse"] = float(np.mean((a - p) ** 2))
                r[f"{name}_correlation"] = float(np.corrcoef(a, p)[0, 1])
            shape_prediction = prediction / psf.sum()
            train_observed = img[masks["train6"]]
            train_shape = shape_prediction[masks["train6"]]
            train_brightness = float(np.dot(train_observed, train_shape) / np.dot(train_shape, train_shape))
            r["train6_brightness_factor"] = train_brightness
            r["hold3_mse_after_train6_brightness"] = float(np.mean(
                (img[masks["hold3"]] - train_brightness * shape_prediction[masks["hold3"]]) ** 2
            ))
            x = coefs[j]
            r["bound_hits_of_12"] = int(np.sum(np.minimum(x[2:14] - scale * LOWER[2:14], scale * UPPER[2:14] - x[2:14]) < 1e-4))
            yy, xx = np.mgrid[-50:51, -50:51]
            radius = np.hypot(xx, yy)
            order = np.argsort(radius.ravel())
            cum = np.cumsum(psf.ravel()[order]) / psf.sum()
            r["psf_r50_px"] = float(radius.ravel()[order][np.searchsorted(cum, .5)])
            r["psf_r90_px"] = float(radius.ravel()[order][np.searchsorted(cum, .9)])
            rows.append(r)
    with (ROOT / "bound_cv_summary.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    agg = []
    for scale in [1, 2, 4, 8]:
        subset = [r for r in rows if r["scale"] == scale]
        agg.append({
            "scale": scale,
            "mean_hold3_mse": float(np.mean([r["hold3_mse"] for r in subset])),
            "mean_hold3_mse_after_train6_brightness": float(np.mean([
                r["hold3_mse_after_train6_brightness"] for r in subset
            ])),
            "mean_hold3_correlation": float(np.mean([r["hold3_correlation"] for r in subset])),
            "median_bound_hits_of_12": float(np.median([r["bound_hits_of_12"] for r in subset])),
            "median_psf_r50_px": float(np.median([r["psf_r50_px"] for r in subset])),
            "median_psf_r90_px": float(np.median([r["psf_r90_px"] for r in subset])),
        })
    (ROOT / "bound_cv_aggregate.json").write_text(json.dumps(agg, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(agg, indent=2))


if __name__ == "__main__":
    main()

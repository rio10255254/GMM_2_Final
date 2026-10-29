"""Normalize the validated 25 PSFs and audit their forward predictions."""

from __future__ import annotations

import csv
import json
from pathlib import Path

import cv2
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from scipy.io import loadmat, savemat
from scipy.signal import fftconvolve
PROJECT_ROOT = Path(__file__).resolve().parents[3]


ROOT = Path(__file__).resolve().parent
JULY = Path(str(PROJECT_ROOT / 'PSF_Fitting/output/pillar_via_junction_psf_20260713/20x/fit_result/PSF_fitted_2D_FOVstack.mat'))
LOWER = np.array([-.3, -.3, -.1, 0, -.1, -.05, -.05, -.05, -.05, -.01, -.01, 0, -.01, -.01, .8])
UPPER = np.array([.3, .3, .1, 1, .1, .05, .05, .05, .05, .01, .01, .3, .01, .01, 1.25])


def prediction_metrics(gt, img, mask, psf):
    normalized = psf / psf.sum()
    prediction = fftconvolve(gt, normalized, mode="same")
    y = img[mask]
    p = prediction[mask]
    brightness = float(np.dot(y, p) / np.dot(p, p))
    fitted = brightness * prediction
    mse = float(np.mean((y - fitted[mask]) ** 2))
    corr = float(np.corrcoef(y, p)[0, 1])
    return normalized, brightness, fitted, mse, corr


def main():
    gt = cv2.imread(str(ROOT / "fit_input" / "GT" / "gt_sem_cd.bmp"), 0).astype(float) / 255
    mask = cv2.imread(str(ROOT / "fit_input" / "loss_mask.bmp"), 0) > 0
    final = loadmat(ROOT / "fit_wide2" / "PSF_fitted_2D_FOVstack.mat")
    july = loadmat(JULY)
    final_psfs = final["psf_grid"].reshape(101, 101, 25)
    july_psf = july["psf_grid"]
    coefficients = final["coef_grid"].reshape(15, 25).T
    with (ROOT / "center9_locations.csv").open(newline="", encoding="utf-8") as f:
        locations = list(csv.DictReader(f))
    files = [locations[i * 9]["image"] for i in range(25)]
    with (ROOT / "fit_wide2" / "batch_results.csv").open(newline="", encoding="utf-8") as f:
        batch = list(csv.DictReader(f))
    if len(batch) != 25 or len(set(files)) != 25:
        raise RuntimeError("Incomplete or duplicate final fit records")

    normalized_psfs = np.empty_like(final_psfs)
    rows = []
    yy, xx = np.mgrid[-50:51, -50:51]
    radii = np.hypot(xx, yy)
    order = np.argsort(radii.ravel())
    example = None
    for i in range(25):
        img = cv2.imread(str(ROOT / "fit_input" / f"fit_input_{i + 1:02d}.bmp"), 0).astype(float) / 255
        psf, brightness, fitted, mse, corr = prediction_metrics(gt, img, mask, final_psfs[:, :, i])
        _, _, july_fitted, july_mse, july_corr = prediction_metrics(gt, img, mask, july_psf)
        normalized_psfs[:, :, i] = psf
        cumulative = np.cumsum(psf.ravel()[order])
        r50 = float(radii.ravel()[order][np.searchsorted(cumulative, .5)])
        r90 = float(radii.ravel()[order][np.searchsorted(cumulative, .9)])
        x = coefficients[i]
        bound_hits = int(np.sum(np.minimum(x[2:14] - 2 * LOWER[2:14], 2 * UPPER[2:14] - x[2:14]) < 1e-4))
        rows.append({
            "image_index": i + 1,
            "source_image": files[i],
            "fitting_loss": float(batch[i]["fval"]),
            "brightness_factor": brightness,
            "mse_final": mse,
            "mse_july_psf": july_mse,
            "correlation_final": corr,
            "correlation_july_psf": july_corr,
            "r50_px": r50,
            "r90_px": r90,
            "bound_hits_of_12": bound_hits,
            "peak_offset_x": float(batch[i]["peak_offset_x"]),
            "peak_offset_y": float(batch[i]["peak_offset_y"]),
            "touches_edge": int(batch[i]["touches_edge"]),
        })
        if i == 12:
            example = (img, fitted, july_fitted)
    if not np.isfinite(normalized_psfs).all() or (normalized_psfs < 0).any():
        raise RuntimeError("Non-finite or negative PSF values")
    if not np.allclose(normalized_psfs.sum(axis=(0, 1)), 1, atol=1e-10):
        raise RuntimeError("PSF normalization failed")
    with (ROOT / "final_fit_qa.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    grid = np.empty((101, 101, 5, 5), dtype=np.float64)
    for i in range(25):
        grid[:, :, i // 5, i % 5] = normalized_psfs[:, :, i]
    savemat(ROOT / "PSF_20260924_center9_25_normalized.mat", {
        "psf_grid": grid,
        "source_image_names_row_major": np.asarray(files, dtype=object).reshape(5, 5),
        "sem_ids_image_rows": np.array([[36, 35, 34], [30, 29, 28], [24, 23, 22]], dtype=np.int32),
        "brightness_factor_row_major": np.array([r["brightness_factor"] for r in rows]).reshape(5, 5),
        "object_pixel_um": np.array([[3.45 / 20]]),
        "aberration_bound_scale": np.array([[2]]),
    }, do_compression=True)

    def median(key):
        return float(np.median([r[key] for r in rows]))
    summary = {
        "image_count": 25,
        "sem_pillar_count_per_image": 9,
        "final_better_than_july_mse_count": sum(r["mse_final"] < r["mse_july_psf"] for r in rows),
        "median_mse_final": median("mse_final"),
        "median_mse_july_psf": median("mse_july_psf"),
        "median_correlation_final": median("correlation_final"),
        "median_correlation_july_psf": median("correlation_july_psf"),
        "median_brightness_factor": median("brightness_factor"),
        "median_r50_px": median("r50_px"),
        "median_r90_px": median("r90_px"),
        "min_bound_hits_of_12": min(r["bound_hits_of_12"] for r in rows),
        "max_bound_hits_of_12": max(r["bound_hits_of_12"] for r in rows),
        "all_peaks_centered": all(r["peak_offset_x"] == 0 and r["peak_offset_y"] == 0 for r in rows),
        "any_psf_touches_edge": any(r["touches_edge"] for r in rows),
    }
    (ROOT / "final_fit_qa_summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))

    # A fixed color scale makes field changes visible without rescaling each PSF.
    fig, axes = plt.subplots(5, 5, figsize=(10, 10), constrained_layout=True)
    vmax = float(np.percentile(normalized_psfs[40:61, 40:61, :], 99.5))
    for i, ax in enumerate(axes.flat):
        ax.imshow(normalized_psfs[35:66, 35:66, i], cmap="magma", vmin=0, vmax=vmax)
        ax.set_title(f"{i + 1:02d}  {files[i].removesuffix('.bmp')}", fontsize=8)
        ax.set_xticks([])
        ax.set_yticks([])
    fig.savefig(ROOT / "psf_grid_25.png", dpi=160)
    plt.close(fig)

    img, final_prediction, july_prediction = example
    fig, axes = plt.subplots(1, 3, figsize=(9, 3), constrained_layout=True)
    area = np.s_[50:90, 50:90]
    for ax, data, title in zip(axes, [img, july_prediction, final_prediction],
                               ["New photo", "July PSF", "Selected bounds"]):
        ax.imshow(data[area], cmap="gray", vmin=0, vmax=1)
        ax.set_title(title)
        ax.set_xticks([])
        ax.set_yticks([])
    fig.savefig(ROOT / "forward_fit_example_13.png", dpi=160)
    plt.close(fig)


if __name__ == "__main__":
    main()

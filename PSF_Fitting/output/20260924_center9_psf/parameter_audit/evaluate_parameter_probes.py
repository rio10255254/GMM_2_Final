"""Score BADS parameter variants on held-out real SEM pillar silhouettes."""

from __future__ import annotations

import csv
import json
from pathlib import Path

import cv2
import numpy as np
from scipy.io import loadmat
from scipy.signal import fftconvolve


ROOT = Path(__file__).resolve().parent
RUN = ROOT.parent
FRAMES = [1, 13, 25]
LOWER = np.array([-.3, -.3, -.1, 0, -.1, -.05, -.05, -.05, -.05, -.01, -.01, 0, -.01, -.01, .8])
UPPER = np.array([.3, .3, .1, 1, .1, .05, .05, .05, .05, .01, .01, .3, .01, .01, 1.25])


def read_csv(path):
    with path.open(newline="", encoding="utf-8-sig") as source:
        return list(csv.DictReader(source))


def main():
    truth = np.load(RUN / "sem_shape_forward_validation" / "gt_sem_contour_20x_float.npz")["image"]
    train = cv2.imread(str(RUN / "fit_input" / "loss_mask_train6.bmp"), 0) > 0
    heldout = cv2.imread(str(RUN / "fit_input" / "loss_mask_hold3.bmp"), 0) > 0
    cases = [("original", RUN / "cv_bounds_2")]
    for directory in sorted(ROOT.iterdir()):
        if directory.is_dir() and (directory / "batch_results.csv").exists():
            if len(read_csv(directory / "batch_results.csv")) == 3:
                cases.append((directory.name, directory))
    rows = []
    for name, directory in cases:
        data = loadmat(directory / "PSF_fitted_2D_FOVstack.mat")
        psfs = data["psf_grid"].reshape(101, 101, 3)
        coefs = data["coef_grid"].reshape(15, 3)
        batch = read_csv(directory / "batch_results.csv")
        config = json.loads((directory / "reasonable_config.json").read_text(encoding="utf-8"))
        assert [int(r["file_index"]) for r in batch] == FRAMES
        for index, frame in enumerate(FRAMES):
            observed = cv2.imread(str(RUN / "fit_input" / f"fit_input_{frame:02d}.bmp"), 0).astype(float) / 255
            psf = psfs[:, :, index] / psfs[:, :, index].sum()
            predicted = fftconvolve(truth, psf, mode="same")
            gain = float(np.dot(observed[train], predicted[train]) / np.dot(predicted[train], predicted[train]))
            y = observed[heldout]
            p = gain * predicted[heldout]
            peak_y, peak_x = np.unravel_index(np.argmax(psf), psf.shape)
            yy, xx = np.mgrid[:101, :101]
            wave = coefs[:, index]
            scale = float(config["aberration_bound_scale"])
            bound_hits = int(np.sum(np.minimum(wave[2:14] - scale * LOWER[2:14],
                                                scale * UPPER[2:14] - wave[2:14]) < 1e-4))
            rows.append({
                "case": name,
                "frame": frame,
                "fit_gt": config["gt_path"],
                "gradient_weight": float(config.get("gradient_weight", 8e4)),
                "rho_divisor": float(config.get("rho_divisor", 2)),
                "bads_calls": int(batch[index]["iterations"]),
                "fit_seconds": float(batch[index]["seconds"]),
                "fit_objective": float(batch[index]["fval"]),
                "heldout_mse": float(np.mean((y - p)**2)),
                "heldout_mae": float(np.mean(np.abs(y - p))),
                "heldout_correlation": float(np.corrcoef(y, p)[0, 1]),
                "peak_offset_px": float(np.hypot(peak_x - 50, peak_y - 50)),
                "centroid_offset_px": float(np.hypot(np.sum((xx - 50) * psf), np.sum((yy - 50) * psf))),
                "edge_energy_fraction": float(psf[:3].sum() + psf[-3:].sum() + psf[3:-3, :3].sum() + psf[3:-3, -3:].sum()),
                "bound_hits_of_12": bound_hits,
            })
    with (ROOT / "parameter_probe_metrics.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    summary = []
    for name, _ in cases:
        subset = [r for r in rows if r["case"] == name]
        summary.append({
            "case": name,
            "mean_heldout_mse": float(np.mean([r["heldout_mse"] for r in subset])),
            "mean_heldout_correlation": float(np.mean([r["heldout_correlation"] for r in subset])),
            "max_peak_offset_px": max(r["peak_offset_px"] for r in subset),
            "max_centroid_offset_px": max(r["centroid_offset_px"] for r in subset),
            "mean_bads_calls": float(np.mean([r["bads_calls"] for r in subset])),
            "max_bound_hits_of_12": max(r["bound_hits_of_12"] for r in subset),
        })
    (ROOT / "parameter_probe_summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()

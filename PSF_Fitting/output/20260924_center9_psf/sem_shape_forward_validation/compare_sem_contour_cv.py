"""Compare SEM-contour BADS fits to disk-trained BADS and Gaussian controls."""

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


def score(gt, psfs, model_name, scale, train, hold):
    rows = []
    for index, frame in enumerate(FRAMES):
        observed = cv2.imread(str(RUN / "fit_input" / f"fit_input_{frame:02d}.bmp"), 0).astype(float) / 255
        psf = psfs[:, :, index] / psfs[:, :, index].sum()
        prediction = fftconvolve(gt, psf, mode="same")
        gain = float(np.dot(observed[train], prediction[train]) / np.dot(prediction[train], prediction[train]))
        y, p = observed[hold], gain * prediction[hold]
        peak_y, peak_x = np.unravel_index(np.argmax(psf), psf.shape)
        yy, xx = np.mgrid[:101, :101]
        rows.append({"frame": frame, "model": model_name, "bound_scale": scale,
                     "brightness_from_train6": gain,
                     "heldout3_mse": float(np.mean((y-p)**2)),
                     "heldout3_mae": float(np.mean(np.abs(y-p))),
                     "heldout3_correlation": float(np.corrcoef(y,p)[0,1]),
                     "peak_offset_px": float(np.hypot(peak_x-50,peak_y-50)),
                     "centroid_offset_px": float(np.hypot(np.sum((xx-50)*psf),np.sum((yy-50)*psf)))})
    return rows


def main():
    gt = np.load(ROOT / "gt_sem_contour_20x_float.npz")["image"]
    train = cv2.imread(str(RUN / "fit_input" / "loss_mask_train6.bmp"), 0) > 0
    hold = cv2.imread(str(RUN / "fit_input" / "loss_mask_hold3.bmp"), 0) > 0
    rows = []
    for scale in [1,2,4,8]:
        mat = loadmat(ROOT / f"cv_sem_bounds_{scale}" / "PSF_fitted_2D_FOVstack.mat")
        psfs = mat["psf_grid"].reshape(101,101,3)
        rows.extend(score(gt,psfs,f"SEM_contour_BADS_{scale}",scale,train,hold))
    disk = loadmat(RUN / "cv_bounds_2" / "PSF_fitted_2D_FOVstack.mat")
    rows.extend(score(gt,disk["psf_grid"].reshape(101,101,3),"workbook_disk_BADS_2",2,train,hold))
    with (ROOT / "sem_contour_cv_metrics.csv").open("w",newline="",encoding="utf-8") as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
    summary=[]
    for name in dict.fromkeys(r["model"] for r in rows):
        subset=[r for r in rows if r["model"]==name]
        summary.append({"model":name,
                        "mean_heldout3_mse":float(np.mean([r["heldout3_mse"] for r in subset])),
                        "mean_heldout3_correlation":float(np.mean([r["heldout3_correlation"] for r in subset])),
                        "max_peak_offset_px":max(r["peak_offset_px"] for r in subset),
                        "max_centroid_offset_px":max(r["centroid_offset_px"] for r in subset)})
    (ROOT / "sem_contour_cv_summary.json").write_text(json.dumps(summary,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(summary,indent=2))


if __name__=="__main__":main()

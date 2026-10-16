"""Package and compare the isolated 25-frame gain-profiled research candidate."""

from __future__ import annotations

import csv
import json
from pathlib import Path

import cv2
import numpy as np
from scipy.io import loadmat, savemat
from scipy.signal import fftconvolve


ROOT = Path(__file__).resolve().parent
RUN = ROOT.parent
NAME = "profile_gain_0p1_full25"


def rows(path):
    with path.open(newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def main():
    candidate_path = ROOT / NAME / "PSF_fitted_2D_FOVstack.mat"
    candidate_data = loadmat(candidate_path)
    raw = candidate_data["psf_grid"].reshape(101, 101, 25)
    candidate = raw / raw.sum(axis=(0, 1), keepdims=True)
    accepted = loadmat(RUN / "PSF_20260924_center9_25_normalized.mat")["psf_grid"].reshape(101, 101, 25)
    batch = rows(ROOT / NAME / "batch_results.csv")
    accepted_batch = rows(RUN / "fit_wide2" / "batch_results.csv")
    assert len(batch) == 25
    config = json.loads((ROOT / NAME / "reasonable_config.json").read_text(encoding="utf-8"))
    assert config["gradient_weight"] == .1 and config["profile_gain"] is True
    assert config["fix_amplitude_in_bads"] is True and config["fix_locked_tilt_in_bads"] is True
    assert config["aberration_bound_scale"] == 2
    assert np.isfinite(candidate).all() and (candidate >= 0).all()
    assert np.allclose(candidate.sum(axis=(0, 1)), 1, atol=1e-10)
    assert len(accepted_batch) == 25
    lower = np.array([-.3,-.3,-.1,0,-.1,-.05,-.05,-.05,-.05,-.01,-.01,0,-.01,-.01,.8])
    upper = np.array([.3,.3,.1,1,.1,.05,.05,.05,.05,.01,.01,.3,.01,.01,1.25])
    accepted_coef = loadmat(RUN / "fit_wide2" / "PSF_fitted_2D_FOVstack.mat")["coef_grid"].reshape(15,25).T
    candidate_coef = candidate_data["coef_grid"].reshape(15,25).T
    def bound_hits(coefs):
        return np.sum(np.minimum(coefs[:,2:14] - 2*lower[2:14],
                                 2*upper[2:14] - coefs[:,2:14]) < 1e-4,axis=1)
    truth = np.load(RUN / "sem_shape_forward_validation" / "gt_sem_contour_20x_float.npz")["image"]
    mask = cv2.imread(str(RUN / "fit_input" / "loss_mask.bmp"), 0) > 0
    yy, xx = np.mgrid[:101, :101]
    centers = []
    old_centers = []
    candidate_errors = []
    accepted_errors = []
    brightness = []
    peaks = []
    for i in range(25):
        image = cv2.imread(str(RUN / "fit_input" / f"fit_input_{i+1:02d}.bmp"), 0).astype(float) / 255
        for psf, errors, center_list in ((candidate[:, :, i], candidate_errors, centers),
                                         (accepted[:, :, i], accepted_errors, old_centers)):
            prediction = fftconvolve(truth, psf, mode="same")
            gain = float(np.dot(image[mask], prediction[mask]) / np.dot(prediction[mask], prediction[mask]))
            errors.append(float(np.mean((image[mask] - gain * prediction[mask])**2)))
            center_list.append([float(np.sum((xx-50)*psf)), float(np.sum((yy-50)*psf))])
            if len(errors) > len(brightness):
                brightness.append(gain)
        py, px = np.unravel_index(np.argmax(candidate[:, :, i]), (101,101))
        peaks.append([px-50, py-50])
    centers = np.asarray(centers)
    old_centers = np.asarray(old_centers)
    assert np.all(np.asarray(peaks) == 0)
    def max_pair_distance(points):
        return max(float(np.linalg.norm(points[i]-points[j])) for i in range(25) for j in range(i+1,25))
    summary = {
        "status": "research_candidate_not_promoted",
        "frames": 25,
        "all25_sem_shape_in_sample_median_mse_candidate": float(np.median(candidate_errors)),
        "all25_sem_shape_in_sample_median_mse_accepted": float(np.median(accepted_errors)),
        "candidate_better_in_sample_frames": int(sum(a<b for a,b in zip(candidate_errors,accepted_errors))),
        "candidate_max_peak_offset_px": 0,
        "candidate_max_centroid_radial_offset_px": float(np.linalg.norm(centers,axis=1).max()),
        "accepted_max_centroid_radial_offset_px": float(np.linalg.norm(old_centers,axis=1).max()),
        "candidate_max_centroid_difference_across_25_px": max_pair_distance(centers),
        "accepted_max_centroid_difference_across_25_px": max_pair_distance(old_centers),
        "mean_BADS_calls_candidate": float(np.mean([int(r["iterations"]) for r in batch])),
        "mean_BADS_calls_accepted": float(np.mean([int(r["iterations"]) for r in accepted_batch])),
        "median_bound_hits_of_12_candidate": float(np.median(bound_hits(candidate_coef))),
        "median_bound_hits_of_12_accepted": float(np.median(bound_hits(accepted_coef))),
        "all_candidate_psfs_normalized": True,
    }
    names = [r["image"] for r in rows(RUN / "center9_locations.csv")[::9]]
    grid = np.empty((101,101,5,5))
    for i in range(25):
        grid[:,:,i//5,i%5] = candidate[:,:,i]
    savemat(ROOT / "PSF_20260924_profile_gain_0p1_RESEARCH.mat", {
        "psf_grid": grid,
        "source_image_names_row_major": np.asarray(names,dtype=object).reshape(5,5),
        "sem_ids_image_rows": np.array([[36,35,34],[30,29,28],[24,23,22]],dtype=np.int32),
        "brightness_factor_row_major": np.asarray(brightness).reshape(5,5),
        "object_pixel_um": np.array([[.1725]]),
        "gradient_weight": np.array([[.1]]),
        "bound_scale": np.array([[2]]),
        "research_only": np.array([[1]],dtype=np.uint8),
    }, do_compression=True)
    (ROOT / "full25_candidate_summary.json").write_text(json.dumps(summary,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(summary,indent=2))


if __name__=="__main__": main()

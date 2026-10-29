"""Forward-project real P-pillar SEM contours through the frozen fitted PSFs."""

from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

import cv2
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from scipy.io import loadmat
from scipy.ndimage import center_of_mass, gaussian_filter
from scipy.signal import fftconvolve
PROJECT_ROOT = Path(__file__).resolve().parents[4]


PROJECT = Path(str(PROJECT_ROOT))
RUN = PROJECT / "PSF_Fitting" / "output" / "20260924_center9_psf"
OUT = Path(__file__).resolve().parent
SEM_MAT = PROJECT / "Experiments" / "R69_ACMContourSEMValidation" / "results" / "masks" / "acm_primary_masks.mat"
JULY_PSF = PROJECT / "PSF_Fitting" / "output" / "pillar_via_junction_psf_20260713" / "20x" / "fit_result" / "PSF_fitted_2D_FOVstack.mat"
IDS = np.array([[36, 35, 34], [30, 29, 28], [24, 23, 22]])
TILE_CENTERS = [69, 150, 231]  # zero-based locations of MATLAB [70,151,232]
CV_FRAMES = [1, 13, 25]
HELDOUT_INDICES = [0, 4, 8]


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def read_csv(path: Path):
    with path.open(newline="", encoding="utf-8-sig") as source:
        return list(csv.DictReader(source))


def optical_sem_mask(sem_mask: np.ndarray, sem_nm_per_px: float, flip_y: bool):
    """Area-sample an unscaled SEM outline at the nominal 20x pixel scale."""
    height = width = 41
    samples_per_pixel = 8
    center_y, center_x = center_of_mass(sem_mask)
    subpixel = (np.arange(width * samples_per_pixel, dtype=np.float32) + .5) / samples_per_pixel - width / 2
    ratio = 172.5 / sem_nm_per_px
    map_x = np.broadcast_to((center_x + subpixel * ratio)[None, :],
                            (height * samples_per_pixel, width * samples_per_pixel)).astype(np.float32)
    y_sign = -1 if flip_y else 1
    map_y = np.broadcast_to((center_y + y_sign * subpixel * ratio)[:, None],
                            (height * samples_per_pixel, width * samples_per_pixel)).astype(np.float32)
    high = cv2.remap(sem_mask.astype(np.float32), map_x, map_y,
                     interpolation=cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT)
    return high.reshape(height, samples_per_pixel, width, samples_per_pixel).mean(axis=(1, 3))


def make_canvas(masks: np.ndarray, sem_nm_per_px: float, flip_y: bool):
    canvas = np.zeros((301, 301), dtype=np.float64)
    per_pillar = []
    for index, pillar_id in enumerate(IDS.ravel()):
        rendered = optical_sem_mask(masks[:, :, pillar_id - 1], sem_nm_per_px, flip_y)
        row, col = divmod(index, 3)
        y, x = TILE_CENTERS[row], TILE_CENTERS[col]
        canvas[y - 20:y + 21, x - 20:x + 21] = rendered
        per_pillar.append(rendered)
    return canvas, per_pillar


def gain_and_metrics(observed, prediction, train_mask, test_mask):
    tr_y, tr_p = observed[train_mask], prediction[train_mask]
    gain = float(np.dot(tr_y, tr_p) / np.dot(tr_p, tr_p))
    y, p = observed[test_mask], gain * prediction[test_mask]
    return gain, {
        "mse": float(np.mean((y - p) ** 2)),
        "mae": float(np.mean(np.abs(y - p))),
        "correlation": float(np.corrcoef(y, p)[0, 1]),
    }


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    reference = loadmat(SEM_MAT, variable_names=["truth_masks", "truth_cells", "opt_pitch", "global_index"])
    masks = reference["truth_masks"].astype(bool)
    assert masks.shape == (104, 104, 36)
    sem_nm_per_px = 5000.0 / float(reference["opt_pitch"].item())
    assert 36 < sem_nm_per_px < 39
    assert reference["global_index"].shape == (6, 6)
    sem_mapping = read_csv(RUN / "sem_9_mapping.csv")
    assert [int(r["sem_id_working"]) for r in sem_mapping] == IDS.ravel().tolist()
    for index, pillar_id in enumerate(IDS.ravel()):
        assert masks[:, :, pillar_id - 1].sum() > 3000
        assert not np.any(masks[[0, -1], :, pillar_id - 1])
        assert not np.any(masks[:, [0, -1], pillar_id - 1])
        contour_area_nm2 = float(masks[:, :, pillar_id - 1].sum()) * sem_nm_per_px**2
        workbook_diameter_nm = float(sem_mapping[index]["sem_diameter_nm"])
        circle_area_nm2 = np.pi * (workbook_diameter_nm / 2)**2
        assert abs(contour_area_nm2 / circle_area_nm2 - 1) < .1

    sem_ideal, sem_tiles = make_canvas(masks, sem_nm_per_px, flip_y=True)
    unflipped_ideal, _ = make_canvas(masks, sem_nm_per_px, flip_y=False)
    assert cv2.imwrite(str(OUT / "gt_sem_contour_20x.bmp"),
                       np.rint(sem_ideal * 255).clip(0, 255).astype(np.uint8))
    np.savez_compressed(OUT / "gt_sem_contour_20x_float.npz", image=sem_ideal)
    disk_ideal = cv2.imread(str(RUN / "fit_input" / "GT" / "gt_sem_cd.bmp"), 0).astype(float) / 255
    train6 = cv2.imread(str(RUN / "fit_input" / "loss_mask_train6.bmp"), 0) > 0
    hold3 = cv2.imread(str(RUN / "fit_input" / "loss_mask_hold3.bmp"), 0) > 0
    all9 = train6 | hold3
    assert all9.sum() == 9 * 317 and train6.sum() == 6 * 317 and hold3.sum() == 3 * 317

    current = loadmat(RUN / "PSF_20260924_center9_25_normalized.mat")["psf_grid"]
    assert current.shape == (101, 101, 5, 5)
    july = loadmat(JULY_PSF, variable_names=["psf_grid"])["psf_grid"]
    july = july / july.sum()
    cv = loadmat(RUN / "cv_bounds_2" / "PSF_fitted_2D_FOVstack.mat", variable_names=["psf_grid", "subset_indices"])
    cv_psfs = cv["psf_grid"].reshape(101, 101, 3)
    assert np.array_equal(cv["subset_indices"].ravel(), CV_FRAMES)
    cv_psfs = cv_psfs / cv_psfs.sum(axis=(0, 1), keepdims=True)

    cv_rows = []
    per_pillar_rows = []
    predictions_frame13 = None
    for cv_index, frame in enumerate(CV_FRAMES):
        observed = cv2.imread(str(RUN / "fit_input" / f"fit_input_{frame:02d}.bmp"), 0).astype(float) / 255
        models = {
            "new_heldout_psf_sem_shape": fftconvolve(sem_ideal, cv_psfs[:, :, cv_index], mode="same"),
            "july_psf_sem_shape": fftconvolve(sem_ideal, july, mode="same"),
            "new_heldout_psf_workbook_disks": fftconvolve(disk_ideal, cv_psfs[:, :, cv_index], mode="same"),
            "new_heldout_psf_sem_unflipped": fftconvolve(unflipped_ideal, cv_psfs[:, :, cv_index], mode="same"),
            "unblurred_sem_shape": sem_ideal,
        }
        # A generic Gaussian is tuned only on the six training pillars.
        gaussian_choices = []
        for sigma in np.arange(1.0, 10.01, .1):
            candidate = gaussian_filter(sem_ideal, sigma=float(sigma), mode="constant")
            gain, train_metrics = gain_and_metrics(observed, candidate, train6, train6)
            gaussian_choices.append((train_metrics["mse"], float(sigma), candidate, gain))
        _, best_sigma, gaussian_prediction, _ = min(gaussian_choices, key=lambda r: r[0])
        models["gaussian_tuned_on_train6"] = gaussian_prediction
        model_display = {}
        for model_name, prediction in models.items():
            gain, test_metrics = gain_and_metrics(observed, prediction, train6, hold3)
            _, train_metrics = gain_and_metrics(observed, prediction, train6, train6)
            cv_rows.append({"frame": frame, "model": model_name, "brightness_from_train6": gain,
                            "gaussian_sigma_px_if_applicable": best_sigma if model_name == "gaussian_tuned_on_train6" else "",
                            "train6_mse": train_metrics["mse"],
                            "heldout3_mse": test_metrics["mse"],
                            "heldout3_mae": test_metrics["mae"],
                            "heldout3_correlation": test_metrics["correlation"]})
            model_display[model_name] = gain * prediction
            for index in HELDOUT_INDICES:
                row, col = divmod(index, 3)
                y, x = TILE_CENTERS[row], TILE_CENTERS[col]
                region = np.s_[y - 10:y + 11, x - 10:x + 11]
                truth, predicted = observed[region], model_display[model_name][region]
                per_pillar_rows.append({"frame": frame, "sem_id": int(IDS.flat[index]), "model": model_name,
                                        "mse": float(np.mean((truth - predicted)**2)),
                                        "mae": float(np.mean(np.abs(truth - predicted))),
                                        "correlation": float(np.corrcoef(truth.ravel(), predicted.ravel())[0, 1])})
        if frame == 13:
            predictions_frame13 = (observed, model_display)

    with (OUT / "heldout_forward_metrics.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(cv_rows[0]))
        writer.writeheader()
        writer.writerows(cv_rows)
    with (OUT / "heldout_per_pillar.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(per_pillar_rows[0]))
        writer.writeheader()
        writer.writerows(per_pillar_rows)

    all25_rows = []
    for index in range(25):
        frame = index + 1
        observed = cv2.imread(str(RUN / "fit_input" / f"fit_input_{frame:02d}.bmp"), 0).astype(float) / 255
        models = {
            "new_psf_sem_shape": fftconvolve(sem_ideal, current[:, :, index // 5, index % 5], mode="same"),
            "new_psf_workbook_disks": fftconvolve(disk_ideal, current[:, :, index // 5, index % 5], mode="same"),
            "july_psf_sem_shape": fftconvolve(sem_ideal, july, mode="same"),
        }
        for name, prediction in models.items():
            gain, metrics = gain_and_metrics(observed, prediction, all9, all9)
            all25_rows.append({"frame": frame, "model": name, "brightness_from_all9": gain,
                               "all9_mse": metrics["mse"], "all9_mae": metrics["mae"],
                               "all9_correlation": metrics["correlation"]})
    with (OUT / "all25_forward_metrics.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(all25_rows[0]))
        writer.writeheader()
        writer.writerows(all25_rows)

    # Fixed display range. Input is the directly derived local optical signal.
    observed, model_display = predictions_frame13
    fig, axes = plt.subplots(3, 5, figsize=(13, 7.8), constrained_layout=True)
    for row, index in enumerate(HELDOUT_INDICES):
        grid_row, grid_col = divmod(index, 3)
        y, x = TILE_CENTERS[grid_row], TILE_CENTERS[grid_col]
        area = np.s_[y - 12:y + 13, x - 12:x + 13]
        sem_area = sem_tiles[index][8:33, 8:33]
        panels = [sem_area, observed[area], model_display["new_heldout_psf_sem_shape"][area],
                  model_display["july_psf_sem_shape"][area],
                  np.abs(observed[area] - model_display["new_heldout_psf_sem_shape"][area])]
        titles = ["SEM outline at 20x", "New photo", "SEM + new PSF", "SEM + July PSF", "Absolute difference"]
        for col, (panel, title) in enumerate(zip(panels, titles)):
            ax = axes[row, col]
            ax.imshow(panel, cmap="magma" if col == 4 else "gray", vmin=0,
                      vmax=.35 if col == 4 else 1, interpolation="nearest")
            if row == 0:
                ax.set_title(title, fontsize=10)
            if col == 0:
                ax.set_ylabel(f"SEM {int(IDS.flat[index])}", fontsize=10)
            ax.set_xticks([])
            ax.set_yticks([])
    fig.suptitle("Frame 13: SEM contour forward check on pillars excluded from PSF fitting", fontsize=12)
    fig.savefig(OUT / "heldout_sem_forward_frame13.png", dpi=170)
    plt.close(fig)

    model_names = list(dict.fromkeys(r["model"] for r in cv_rows))
    aggregate = {}
    for name in model_names:
        subset = [r for r in cv_rows if r["model"] == name]
        aggregate[name] = {"mean_heldout3_mse": float(np.mean([r["heldout3_mse"] for r in subset])),
                           "mean_heldout3_mae": float(np.mean([r["heldout3_mae"] for r in subset])),
                           "mean_heldout3_correlation": float(np.mean([r["heldout3_correlation"] for r in subset]))}
    summary = {
        "status": "complete",
        "SEM_truth_source": str(SEM_MAT),
        "SEM_truth_sha256": sha256(SEM_MAT),
        "SEM_truth_is_actual_P_TIFF_contour_not_workbook_disk": True,
        "SEM_nm_per_pixel": sem_nm_per_px,
        "optical_nm_per_pixel_nominal": 172.5,
        "fixed_orientation": "vertical flip from locked current 20x sequence; no per-pillar rotation fitted",
        "cv_frames": CV_FRAMES,
        "heldout_sem_ids": [int(IDS.flat[i]) for i in HELDOUT_INDICES],
        "fit_pillars_per_cv_frame": 6,
        "gain_fit_scope": "One scalar gain per model and frame, estimated from six training pillars; no heldout-pillar fitting, shifts, or size changes",
        "headline": aggregate,
        "all25_comparison_is_in_sample": True,
        "SEM_grayscale_note": "SEM TIFF brightness is electron-detector contrast, not optical reflectance. Binary SEM contours were used as shape and convolved with the optical PSF.",
    }
    (OUT / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(aggregate, indent=2))


if __name__ == "__main__":
    main()

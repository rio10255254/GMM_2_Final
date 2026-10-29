"""Install the exact research-only SEM core-halo 25-PSF grid, row major."""
from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

import numpy as np
from scipy.io import loadmat
PROJECT_ROOT = Path(__file__).resolve().parents[3]

ROOT = Path(__file__).resolve().parents[1]
PROJECT = Path(str(PROJECT_ROOT))
SOURCE = PROJECT / "PSF_Fitting/output/20260924_center9_psf/model_search"
MAT = SOURCE / "PSF_20260924_SEM_core_halo_25_RESEARCH.mat"
EXPECTED_MAT_SHA = "0d85d63c08a943a56d6fd74d2ce250b0d656d1170e7ab185e95d2ff369a797e6"
sys.path.insert(0, str(ROOT))
from utils import now, save, sha


def checked_source_files() -> int:
    with (SOURCE / "source_sha256.csv").open(newline="", encoding="utf-8-sig") as handle:
        rows = list(csv.DictReader(handle))
    if len(rows) != 9:
        raise RuntimeError("Expected the nine frozen model-search source files")
    for row in rows:
        path = Path(row["absolute_path"])
        if not path.is_file() or path.stat().st_size != int(row["bytes"]) or sha(path) != row["sha256"]:
            raise RuntimeError("Source hash mismatch: " + str(path))
    return len(rows)


def main() -> None:
    if sha(MAT) != EXPECTED_MAT_SHA:
        raise RuntimeError("User-provided normalized MAT changed")
    verification = json.loads((SOURCE / "verification.json").read_text(encoding="utf-8"))
    quality = json.loads((SOURCE / "full25_core_halo_summary.json").read_text(encoding="utf-8"))
    heldout = json.loads((SOURCE / "E_full_patch_verdict.json").read_text(encoding="utf-8"))
    if (verification["status"] != "PASS" or verification["research_PSF_kernels"] != 25 or
            verification["accepted_PSF_replaced"] is not False or
            quality["status"] != "research_candidate_not_formal_baseline" or
            quality["all_25_BADs_exitflags_positive"] is not True or
            heldout["status"] != "PASS_predictive_research_PSF" or
            heldout["gates"]["better_than_gaussian_all_six_frames"] is not True):
        raise RuntimeError("The research PSF has not passed its frozen held-out QA")
    checked = checked_source_files()
    z = loadmat(MAT, squeeze_me=False, struct_as_record=False)
    grid = z["psf_grid"]
    if grid.shape != (101, 101, 5, 5) or grid.dtype.kind != "f":
        raise ValueError("Unexpected measured PSF grid")
    if not np.isfinite(grid).all() or (grid < 0).any():
        raise ValueError("Measured PSF has invalid pixels")
    sums = grid.sum(axis=(0, 1))
    if not np.allclose(sums, 1.0, rtol=0, atol=1e-10):
        raise ValueError("The supplied PSFs are not unit normalized")
    if abs(float(z["object_pixel_um"].item()) - .1725) > 1e-12:
        raise ValueError("PSF and real evaluation have different object pixel scale")
    if int(z["research_only"].item()) != 1:
        raise ValueError("User-specified PSF must retain its research-only status")
    if any(z[key].shape != (5,5) for key in
           ("sigma_core_px", "sigma_halo_px", "core_energy_weight", "brightness_gain_row_major")):
        raise ValueError("Missing core-halo fit parameters")
    ids = z["sem_ids_image_rows"].astype(int).tolist()
    if ids != [[36,35,34],[30,29,28],[24,23,22]]:
        raise ValueError("SEM working identities differ from source calibration")
    names = [str(z["source_image_names_row_major"][r,c][0]) for r in range(5) for c in range(5)]
    if len(set(names)) != 25:
        raise ValueError("Duplicate capture image name in PSF source")
    # Explicit C-order row-major mapping: index = row*5 + column.
    kernels = np.transpose(grid, (2,3,0,1)).reshape(25,101,101).copy()
    if not np.array_equal(kernels[0], grid[:,:,0,0]) or not np.array_equal(kernels[24], grid[:,:,4,4]):
        raise RuntimeError("PSF index order changed")
    y, x = np.mgrid[:101,:101]
    center_x = (kernels*x).sum((1,2))-50
    center_y = (kernels*y).sum((1,2))-50
    flat = kernels.reshape(25,-1)
    norms = np.linalg.norm(flat,axis=1)
    cosines = (flat@flat.T)/np.outer(norms,norms)
    minimum_cosine = float(cosines[np.triu_indices(25,1)].min())
    destination = ROOT / "calibration/measured_psf_bank.npz"
    if destination.exists():
        raise FileExistsError("Calibration bank already installed")
    np.savez_compressed(destination, all_kernels=kernels,
                        mean=kernels.mean(0), candidates=kernels[[0,8,16,24]])
    with np.load(destination, allow_pickle=False) as check:
        if not np.array_equal(check["all_kernels"], kernels):
            raise RuntimeError("PSF copy changed values")
    lock = dict(count=25, kernel_shape=[101,101], bank_sha256=sha(destination),
                source_mat_path=str(MAT), source_mat_sha256=EXPECTED_MAT_SHA,
                origin="2026-09-24 actual P-SEM silhouette centered core-halo 25-frame research fit",
                index_order="row-major 5x5, index=row*5+column",
                source_image_names_row_major=names,
                object_um_per_px=.1725,
                psf_calibration_uses_sem_diameters=False,
                psf_calibration_uses_sem_geometry=True,
                sem_size_targets_in_training=False,
                sem_reference="R69 actual P-SEM silhouette masks, nine identified pillars",
                research_only=True,
                frozen_E_heldout_views=6,
                frozen_E_heldout_appearances=18,
                frozen_E_mean_mse_core_halo=float(heldout["summary"]["selected_core_halo_BADs"]["mean_heldout_mse"]),
                frozen_E_mean_mse_gaussian=float(heldout["summary"]["gaussian"]["mean_heldout_mse"]),
                source_files_hash_verified=checked,
                retained_brightness_factors_outside_kernel=True,
                intensity_centroid_x_mean_px=float(center_x.mean()),
                intensity_centroid_y_mean_px=float(center_y.mean()),
                intensity_centroid_x_range_px=[float(center_x.min()),float(center_x.max())],
                intensity_centroid_y_range_px=[float(center_y.min()),float(center_y.max())],
                minimum_pairwise_cosine=minimum_cosine,
                warning="Actual P-SEM silhouettes calibrated this research-only PSF; synthetic clear images remain the neural targets. Reuse of the same physical nine pillars for size checking is calibration-conditioned, not independent external validation",
                created_utc=now())
    save(ROOT / "calibration/BANK_LOCK.json", lock)
    print("INSTALLED_CENTER9_PSF25", destination, lock["bank_sha256"], flush=True)


if __name__ == "__main__":
    main()

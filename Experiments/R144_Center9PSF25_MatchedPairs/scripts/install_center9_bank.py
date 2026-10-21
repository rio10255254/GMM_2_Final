"""Install the exact normalized 2026-09-24 center-nine PSF grid, row major."""
from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

import numpy as np
from scipy.io import loadmat

ROOT = Path(__file__).resolve().parents[1]
PROJECT = Path(r"D:\GMM_2_Final")
SOURCE = PROJECT / "PSF_Fitting/output/20260924_center9_psf"
MAT = SOURCE / "PSF_20260924_center9_25_normalized.mat"
EXPECTED_MAT_SHA = "3e6889b5c36488e426415c01e99df12c5a12fd9a908d52cb20f4fd1434c201c5"
sys.path.insert(0, str(ROOT))
from utils import now, save, sha


def checked_source_files() -> int:
    with (SOURCE / "source_sha256.csv").open(newline="", encoding="utf-8-sig") as handle:
        rows = list(csv.DictReader(handle))
    if len(rows) != 28:
        raise RuntimeError("Expected 25 capture photos and 3 reference sources")
    for row in rows:
        path = PROJECT / row["source_relative_to_project"]
        if not path.is_file() or path.stat().st_size != int(row["bytes"]) or sha(path) != row["sha256"]:
            raise RuntimeError("Source hash mismatch: " + str(path))
    return len(rows)


def main() -> None:
    if sha(MAT) != EXPECTED_MAT_SHA:
        raise RuntimeError("User-provided normalized MAT changed")
    verification = json.loads((SOURCE / "verification.json").read_text(encoding="utf-8"))
    quality = json.loads((SOURCE / "final_fit_qa_summary.json").read_text(encoding="utf-8"))
    if verification["status"] != "PASS" or quality["image_count"] != 25:
        raise RuntimeError("The 25-fit deliverable has not passed source QA")
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
    if int(z["aberration_bound_scale"].item()) != 2:
        raise ValueError("Wrong fitted coefficient bound regime")
    ids = z["sem_ids_image_rows"].astype(int).tolist()
    if ids != [[36,30,24],[35,29,23],[34,28,22]]:
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
                origin="2026-09-24 new 20x center-nine 25-frame fit",
                index_order="row-major 5x5, index=row*5+column",
                source_image_names_row_major=names,
                object_um_per_px=.1725,
                psf_calibration_uses_sem_diameters=True,
                sem_size_targets_in_training=False,
                sem_reference="SEM data!J8:L10, nine pillar diameter disks",
                source_files_hash_verified=checked,
                retained_brightness_factors_outside_kernel=True,
                intensity_centroid_x_mean_px=float(center_x.mean()),
                intensity_centroid_y_mean_px=float(center_y.mean()),
                intensity_centroid_x_range_px=[float(center_x.min()),float(center_x.max())],
                intensity_centroid_y_range_px=[float(center_y.min()),float(center_y.max())],
                minimum_pairwise_cosine=minimum_cosine,
                fitter_bound_scale=2,
                warning="Known SEM disk diameters calibrate the PSF; synthetic clear images remain the neural training targets. Reuse of the same SEM table is a calibration-conditioned size check, not independent external validation",
                created_utc=now())
    save(ROOT / "calibration/BANK_LOCK.json", lock)
    print("INSTALLED_CENTER9_PSF25", destination, lock["bank_sha256"], flush=True)


if __name__ == "__main__":
    main()

"""Verify source integrity, SEM mapping, and the completed 25-kernel package."""

from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

import cv2
import numpy as np
from scipy.io import loadmat


ROOT = Path(__file__).resolve().parent
PROJECT = Path(r"D:\GMM_2_Final")


def read_csv(path):
    with path.open(newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main():
    sources = read_csv(ROOT / "source_sha256.csv")
    assert len(sources) == 28
    for row in sources:
        path = PROJECT / row["source_relative_to_project"]
        assert path.is_file() and path.stat().st_size == int(row["bytes"])
        assert sha256(path) == row["sha256"], f"Source changed: {path}"
    identity_sources = read_csv(ROOT / "identity_source_sha256.csv")
    assert len(identity_sources) == 9
    for row in identity_sources:
        path = Path(row["absolute_path"])
        assert path.is_file() and path.stat().st_size == int(row["bytes"])
        assert sha256(path) == row["sha256"], f"Identity source changed: {path}"

    locations = read_csv(ROOT / "center9_locations.csv")
    mapping = read_csv(ROOT / "sem_9_mapping.csv")
    assert len(locations) == 25 * 9 and len(mapping) == 9
    expected_ids = [36, 35, 34, 30, 29, 28, 24, 23, 22]
    assert [int(r["sem_id_working"]) for r in mapping] == expected_ids
    assert [int(r["sem_id_working"]) for r in locations[:9]] == expected_ids
    assert all(int(r["sem_id_working"]) == expected_ids[i % 9] for i, r in enumerate(locations))
    registration = json.loads((ROOT / "registration_manifest.json").read_text(encoding="utf-8"))
    assert registration["center_coordinates"] == "MATLAB one-based image coordinates"
    assert registration["max_loop_error_px"] < 0.5
    transfer = json.loads((ROOT / "current_20x_identity_transfer.json").read_text(encoding="utf-8"))
    assert transfer["sem_ids_image_rows"] == [[36, 35, 34], [30, 29, 28], [24, 23, 22]]
    assert transfer["max_center_residual_px"] < 1.5
    sem_audit = json.loads((ROOT / "sem_mapping_audit.json").read_text(encoding="utf-8"))
    assert sem_audit["status"] == "PASS" and sem_audit["P_pillar_data_count"] == 9

    inputs = sorted((ROOT / "fit_input").glob("fit_input_*.bmp"))
    assert len(inputs) == 25
    assert all(cv2.imread(str(path), 0).shape == (301, 301) for path in inputs)
    alignment = read_csv(ROOT / "input_center_alignment.csv")
    assert len(alignment) == 225
    max_center_offset = max(float(r["offset_px"]) for r in alignment)
    assert max_center_offset < 0.5

    fit_rows = read_csv(ROOT / "fit_wide2" / "batch_results.csv")
    assert len(fit_rows) == 25
    assert [r["filename"] for r in fit_rows] == [f"fit_input_{i:02d}.bmp" for i in range(1, 26)]
    assert all(np.isfinite(float(r["fval"])) and int(r["touches_edge"]) == 0 for r in fit_rows)
    config = json.loads((ROOT / "fit_wide2" / "reasonable_config.json").read_text(encoding="utf-8"))
    assert config["aberration_bound_scale"] == 2
    assert config["warm_start"] is False and config["lock_tilt"] is True

    package = loadmat(ROOT / "PSF_20260924_center9_25_normalized.mat")
    kernels = package["psf_grid"]
    assert kernels.shape == (101, 101, 5, 5)
    assert np.isfinite(kernels).all() and (kernels >= 0).all()
    assert np.allclose(kernels.sum(axis=(0, 1)), 1, atol=1e-10)
    assert np.array_equal(package["sem_ids_image_rows"], np.array([[36, 35, 34], [30, 29, 28], [24, 23, 22]]))
    qa = json.loads((ROOT / "final_fit_qa_summary.json").read_text(encoding="utf-8"))
    assert qa["image_count"] == 25
    assert qa["all_peaks_centered"] is True and qa["any_psf_touches_edge"] is False
    center_audit = json.loads((ROOT / "psf_center_audit_summary.json").read_text(encoding="utf-8"))
    assert center_audit["psf_count"] == 25
    assert center_audit["max_peak_radial_offset_px"] == 0
    assert center_audit["max_centroid_radial_offset_px"] < 0.3
    assert center_audit["max_outer_3px_energy_fraction"] < 0.001
    assert (ROOT / "psf_grid_25.png").is_file()
    assert (ROOT / "forward_fit_example_13.png").is_file()
    assert (ROOT / "README.md").is_file()
    sem_shape = json.loads((ROOT / "sem_shape_forward_validation" / "verification.json").read_text(encoding="utf-8"))
    assert sem_shape["status"] == "PASS" and sem_shape["SEM_contour_BADS_fits_complete"] == 12
    parameter_audit = json.loads((ROOT / "parameter_audit" / "verification.json").read_text(encoding="utf-8"))
    assert parameter_audit["status"] == "PASS" and parameter_audit["research_candidate_kernels"] == 25
    model_search = json.loads((ROOT / "model_search" / "verification.json").read_text(encoding="utf-8"))
    assert model_search["status"] == "PASS" and model_search["research_PSF_kernels"] == 25

    report = {
        "status": "PASS",
        "source_files_hash_verified": len(sources),
        "identity_sources_hash_verified": len(identity_sources),
        "capture_frames": len(inputs),
        "source_pillar_locations": len(locations),
        "sem_reference_pillars": len(mapping),
        "fit_rows": len(fit_rows),
        "normalized_kernels": 25,
        "max_input_center_offset_px": max_center_offset,
        "max_psf_centroid_radial_offset_px": center_audit["max_centroid_radial_offset_px"],
        "actual_SEM_contour_forward_check": sem_shape["status"],
        "fitter_parameter_audit": parameter_audit["status"],
        "full_patch_core_halo_model_search": model_search["status"],
    }
    (ROOT / "verification.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()

"""Independently measure peak and energy-center offsets of the 25 final PSFs."""

from __future__ import annotations

import csv
import json
from pathlib import Path

import numpy as np
from scipy.io import loadmat


ROOT = Path(__file__).resolve().parent
OBJECT_NM_PER_PX = 172.5


def main():
    fitted = loadmat(ROOT / "fit_wide2" / "PSF_fitted_2D_FOVstack.mat")["psf_grid"].reshape(101, 101, 25)
    delivered = loadmat(ROOT / "PSF_20260924_center9_25_normalized.mat")["psf_grid"]
    with (ROOT / "fit_wide2" / "batch_results.csv").open(newline="", encoding="utf-8") as f:
        batch = list(csv.DictReader(f))
    assert len(batch) == 25 and delivered.shape == (101, 101, 5, 5)
    yy, xx = np.mgrid[:101, :101]
    edge = np.ones((101, 101), dtype=bool)
    edge[3:-3, 3:-3] = False
    rows = []
    for i in range(25):
        psf = delivered[:, :, i // 5, i % 5]
        assert np.allclose(psf, fitted[:, :, i] / fitted[:, :, i].sum(), atol=1e-12)
        peak_y, peak_x = np.unravel_index(np.argmax(psf), psf.shape)
        peak_dx, peak_dy = int(peak_x - 50), int(peak_y - 50)
        centroid_dx = float(np.sum((xx - 50) * psf))
        centroid_dy = float(np.sum((yy - 50) * psf))
        centroid_radius = float(np.hypot(centroid_dx, centroid_dy))
        edge_energy = float(psf[edge].sum())
        record = {
            "image_index": i + 1,
            "fitted_input": batch[i]["filename"],
            "peak_offset_x_px": peak_dx,
            "peak_offset_y_px": peak_dy,
            "centroid_offset_x_px": centroid_dx,
            "centroid_offset_y_px": centroid_dy,
            "centroid_radial_offset_px": centroid_radius,
            "centroid_radial_offset_nm_nominal": centroid_radius * OBJECT_NM_PER_PX,
            "outer_3px_energy_fraction": edge_energy,
            "fitter_centroid_x_delta_px": centroid_dx - float(batch[i]["centroid_offset_x"]),
            "fitter_centroid_y_delta_px": centroid_dy - float(batch[i]["centroid_offset_y"]),
        }
        assert abs(record["fitter_centroid_x_delta_px"]) < 1e-8
        assert abs(record["fitter_centroid_y_delta_px"]) < 1e-8
        rows.append(record)
    with (ROOT / "psf_center_audit.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    centroid_offsets = np.asarray([[r["centroid_offset_x_px"], r["centroid_offset_y_px"]] for r in rows])
    all_pair_deltas = [float(np.linalg.norm(centroid_offsets[i] - centroid_offsets[j]))
                       for i in range(25) for j in range(i + 1, 25)]
    grid_offsets = centroid_offsets.reshape(5, 5, 2)
    neighbor_deltas = [float(np.linalg.norm(grid_offsets[row, col] - grid_offsets[row + 1, col]))
                       for row in range(4) for col in range(5)]
    neighbor_deltas += [float(np.linalg.norm(grid_offsets[row, col] - grid_offsets[row, col + 1]))
                        for row in range(5) for col in range(4)]
    summary = {
        "psf_count": len(rows),
        "center_pixel_matlab_1_based": [51, 51],
        "max_peak_radial_offset_px": float(max(np.hypot(r["peak_offset_x_px"], r["peak_offset_y_px"]) for r in rows)),
        "median_centroid_radial_offset_px": float(np.median([r["centroid_radial_offset_px"] for r in rows])),
        "max_centroid_radial_offset_px": float(max(r["centroid_radial_offset_px"] for r in rows)),
        "max_centroid_radial_offset_nm_nominal": float(max(r["centroid_radial_offset_nm_nominal"] for r in rows)),
        "max_centroid_change_between_any_two_psfs_px": max(all_pair_deltas),
        "max_centroid_change_between_neighbor_psfs_px": max(neighbor_deltas),
        "max_outer_3px_energy_fraction": float(max(r["outer_3px_energy_fraction"] for r in rows)),
        "all_centroid_offsets_match_fitter": True,
        "any_peak_touches_edge": any(abs(int(r["peak_offset_x_px"])) >= 48 or abs(int(r["peak_offset_y_px"])) >= 48 for r in rows),
    }
    (ROOT / "psf_center_audit_summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()

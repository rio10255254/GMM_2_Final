"""Check provenance, held-out rows, and completed SEM-contour fit comparisons."""

from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

import cv2
import numpy as np


ROOT = Path(__file__).resolve().parent
RUN = ROOT.parent


def records(path):
    with path.open(newline="", encoding="utf-8-sig") as source:
        return list(csv.DictReader(source))


def digest(path):
    h = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def main():
    summary = json.loads((ROOT / "summary.json").read_text(encoding="utf-8"))
    source = Path(summary["SEM_truth_source"])
    assert source.is_file() and digest(source) == summary["SEM_truth_sha256"]
    optical_gt = np.load(ROOT / "gt_sem_contour_20x_float.npz")["image"]
    optical_gt_bmp = cv2.imread(str(ROOT / "gt_sem_contour_20x.bmp"), 0).astype(float) / 255
    assert optical_gt.shape == optical_gt_bmp.shape == (301, 301)
    assert np.max(np.abs(optical_gt - optical_gt_bmp)) <= .5 / 255 + 1e-12
    assert np.isfinite(optical_gt).all() and 0 <= optical_gt.min() <= optical_gt.max() <= 1

    heldout = records(ROOT / "heldout_forward_metrics.csv")
    per_pillar = records(ROOT / "heldout_per_pillar.csv")
    all25 = records(ROOT / "all25_forward_metrics.csv")
    sem_cv = records(ROOT / "sem_contour_cv_metrics.csv")
    assert len(heldout) == 3 * 6
    assert len(per_pillar) == 3 * 3 * 6
    assert len(all25) == 25 * 3
    assert len(sem_cv) == 3 * 5
    assert set(int(r["sem_id"]) for r in per_pillar) == {36, 29, 22}
    assert set(int(r["frame"]) for r in heldout) == {1, 13, 25}
    assert all(np.isfinite(float(r["heldout3_mse"])) for r in heldout)
    assert all(np.isfinite(float(r["heldout3_mse"])) for r in sem_cv)

    for scale in (1, 2, 4, 8):
        config = json.loads((ROOT / f"cv_sem_bounds_{scale}" / "reasonable_config.json").read_text(encoding="utf-8"))
        assert config["aberration_bound_scale"] == scale
        assert config["gt_path"] == str(ROOT / "gt_sem_contour_20x.bmp")
        assert config["loss_mask_path"] == str(RUN / "fit_input" / "loss_mask_train6.bmp")
        assert config["subset_indices"] == [1, 13, 25]
        assert config["warm_start"] is False and config["lock_tilt"] is True
        assert len(records(ROOT / f"cv_sem_bounds_{scale}" / "batch_results.csv")) == 3
    log = (ROOT / "sem_cv_console.log").read_text(encoding="utf-8", errors="replace")
    assert log.count("Beginning optimization") == 12
    assert log.count("Optimization terminated") == 12

    cases = {(int(r["frame"]), int(r["sem_id"])) for r in per_pillar}
    assert len(cases) == 9
    by_key = {(int(r["frame"]), int(r["sem_id"]), r["model"]): float(r["mse"]) for r in per_pillar}
    new_better_july = sum(by_key[(f, i, "new_heldout_psf_sem_shape")] < by_key[(f, i, "july_psf_sem_shape")]
                          for f, i in cases)
    gaussian_better_new = sum(by_key[(f, i, "gaussian_tuned_on_train6")] < by_key[(f, i, "new_heldout_psf_sem_shape")]
                              for f, i in cases)
    assert new_better_july == gaussian_better_new == 9
    assert (ROOT / "heldout_sem_forward_frame13.png").is_file()
    assert (ROOT / "README_TW.md").is_file()
    report = {
        "status": "PASS",
        "SEM_contour_source_sha256_verified": True,
        "SEM_contour_target_shape": [301, 301],
        "reserved_frames": 3,
        "reserved_pillar_ids": [36, 29, 22],
        "heldout_pillar_appearances": 9,
        "SEM_contour_BADS_fits_complete": 12,
        "new_BADS_better_than_july_per_pillar": new_better_july,
        "gaussian_better_than_new_BADS_per_pillar": gaussian_better_new,
    }
    (ROOT / "verification.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()

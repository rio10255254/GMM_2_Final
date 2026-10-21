"""Verify fitter-option comparisons, disjoint holdouts, and research packaging."""

from __future__ import annotations

import csv
import hashlib
import json
import re
from pathlib import Path

import cv2
import numpy as np
from scipy.io import loadmat


ROOT = Path(__file__).resolve().parent
RUN = ROOT.parent


def load_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def rows(path):
    with path.open(newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def main():
    code_sources = rows(ROOT / "code_and_input_sha256.csv")
    assert len(code_sources) == 11
    for source in code_sources:
        path = Path(source["absolute_path"])
        assert path.is_file() and path.stat().st_size == int(source["bytes"])
        digest = hashlib.sha256()
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
        assert digest.hexdigest() == source["sha256"], f"Audit source changed: {path}"
    assert (RUN / "PSF_20260924_center9_25_normalized.mat").is_file()
    assert load_json(RUN / "sem_shape_forward_validation" / "verification.json")["status"] == "PASS"
    components = rows(ROOT / "current_loss_components.csv")
    assert len(components) == 3
    ratios = [float(r["gradient_to_intensity_ratio"]) for r in components]
    assert min(ratios) > 6e5
    assert all(float(r["clipped_pixel_fraction_in_mask"]) == 0 for r in components)

    accepted = {int(r["file_index"]): r for r in rows(RUN / "fit_wide2" / "batch_results.csv")}
    replay = rows(ROOT / "default_replay_after_profile" / "coefficient_evaluation.csv")
    assert len(replay) == 1
    replay_delta = abs(float(replay[0]["loss"]) - float(accepted[13]["fval"]))
    assert replay_delta < 1e-9

    frozen = load_json(ROOT / "confirmation_split.json")
    assert frozen["selection_frozen_before_confirmation"] is True
    assert set(frozen["confirmation_frames"]).isdisjoint({1, 13, 25})
    assert set(frozen["heldout_sem_ids"]).isdisjoint({36, 29, 22})
    tune = {r["case"]: r for r in load_json(ROOT / "parameter_probe_summary.json")}
    confirm = {r["model"]: r for r in load_json(ROOT / "confirmation_summary.json")}
    for name in ("profile_gain_0p1", "weight_0", "bads_restarts", "rho_full", "rho_full_legacyweight"):
        assert name in tune
    for name in ("confirm_original", "confirm_profile_gain_0p1", "confirm_weight_0", "confirm_bads_restarts", "gaussian"):
        assert name in confirm
    assert tune["profile_gain_0p1"]["mean_heldout_mse"] < tune["original"]["mean_heldout_mse"]
    assert confirm["confirm_profile_gain_0p1"]["mean_heldout_mse"] < confirm["confirm_original"]["mean_heldout_mse"]
    assert confirm["gaussian"]["mean_heldout_mse"] < confirm["confirm_profile_gain_0p1"]["mean_heldout_mse"]
    per_pillar = rows(ROOT / "confirmation_per_pillar.csv")
    scores = {(int(r["frame"]), int(r["sem_id"]), r["model"]): float(r["mse"]) for r in per_pillar}
    cases = {(frame, pillar) for frame, pillar, _ in scores}
    assert len(cases) == 15
    candidate_better_count = sum(scores[(frame, pillar, "confirm_profile_gain_0p1")] <
                                 scores[(frame, pillar, "confirm_original")]
                                 for frame, pillar in cases)
    assert candidate_better_count == 15

    full = load_json(ROOT / "full25_candidate_summary.json")
    assert full["status"] == "research_candidate_not_promoted" and full["frames"] == 25
    assert full["candidate_better_in_sample_frames"] == 25
    package = loadmat(ROOT / "PSF_20260924_profile_gain_0p1_RESEARCH.mat")
    psfs = package["psf_grid"]
    assert psfs.shape == (101, 101, 5, 5)
    assert np.isfinite(psfs).all() and (psfs >= 0).all()
    assert np.allclose(psfs.sum(axis=(0, 1)), 1, atol=1e-10)
    assert package["research_only"].item() == 1
    assert np.array_equal(package["sem_ids_image_rows"], np.array([[36,35,34],[30,29,28],[24,23,22]]))
    assert len(rows(ROOT / "profile_gain_0p1_full25" / "batch_results.csv")) == 25

    wide = load_json(ROOT / "wide_patch_summary.json")
    assert len(wide) == 4
    for split in ("A", "B"):
        a = next(r for r in wide if r["split"] == split and r["case"] == "wide")
        b = next(r for r in wide if r["split"] == split and r["case"] == "narrow")
        assert a["mean_heldout_radius12_mse"] < b["mean_heldout_radius12_mse"]
        assert a["max_centroid_radial_offset_px"] > b["max_centroid_radial_offset_px"]
    assert len(list((ROOT / "wide_input").glob("fit_input_*.bmp"))) == 25
    for name in ("01_heldout_fit_comparison.png", "02_psf_center_tradeoff.png"):
        assert (ROOT / "figures" / name).is_file()
    assert (ROOT / "README_TW.md").is_file()

    logs = ["first_matrix.log", "second_matrix.log", "profile_gain_matrix.log",
            "confirmation_console.log", "profile_gain_confirmation.log",
            "weight_0_full25.log", "profile_gain_0p1_full25.log"]
    all_flags = []
    for name in logs:
        text = (ROOT / name).read_text(encoding="utf-8", errors="replace")
        all_flags.extend(int(x) for x in re.findall(r"BADS frame \d+: exitflag=(\d+)", text))
    assert len(all_flags) == 110 and all(flag > 0 for flag in all_flags)
    report = {
        "status": "PASS",
        "original_loss_replay_absolute_difference": replay_delta,
        "maximum_gradient_to_intensity_ratio": max(ratios),
        "separate_confirmation_frames": len(frozen["confirmation_frames"]),
        "different_heldout_pillar_ids": frozen["heldout_sem_ids"],
        "candidate_better_per_pillar_confirmation": candidate_better_count,
        "research_candidate_kernels": 25,
        "isolated_BADS_fits_verified": len(all_flags),
        "code_and_input_hashes_verified": len(code_sources),
        "accepted_PSF_overwritten": False,
    }
    (ROOT / "verification.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()

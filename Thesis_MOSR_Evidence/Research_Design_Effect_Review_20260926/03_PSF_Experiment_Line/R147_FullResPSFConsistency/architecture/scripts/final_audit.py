"""Audit complete training, 930 real outputs, 8370 contours, and comparisons."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
PROJECT_ROOT = Path(__file__).resolve().parents[6]

ROOT = Path(__file__).resolve().parents[1]
R146 = Path(str(PROJECT_ROOT / 'Experiments/R146_SEMCoreHaloPSF25_MatchedPairs'))
sys.path.insert(0, str(ROOT))
from utils import load, now, save, sha
from verify_package import verify_source_lock
from evaluation_lock import verify as verify_evaluation_lock


def main() -> None:
    verify_source_lock()
    verify_evaluation_lock()
    pre = load(ROOT / "results/preflight.json")
    complete = load(ROOT / "runs/formal_8192/training_complete.json")
    checkpoint = complete["checkpoint"]
    assert pre["passed"] and complete["updates"] == checkpoint["step"] == 8192
    assert sha(checkpoint["path"]) == checkpoint["sha256"]
    assert len((ROOT / "runs/formal_8192/updates.jsonl").read_text(encoding="utf-8").splitlines()) == 8192
    assert load(ROOT / "results/reconstruction_complete.json")["images"] == 930
    assert load(ROOT / "results/measurement_complete.json")["circles"] == 8370
    synthetic_physics = load(ROOT / "results/physics_evaluation.json")
    real_physics = load(ROOT / "results/real_physics_effect_12.json")
    assert synthetic_physics["sampled_test_parents"] == 32
    assert len(real_physics["frames"]) == 12
    assert synthetic_physics["checkpoint_sha256"] == real_physics["checkpoint_sha256"] == checkpoint["sha256"]
    plan = load(ROOT / "evaluation/capture_plan.json")
    receipts = []
    for frame in plan["frames"]:
        stem = f"{frame['index'] + 1:02d}"
        base = ROOT / "results/reconstruction" / frame["run"] / stem
        receipt = load(base.with_suffix(".json"))
        assert receipt["checkpoint_sha256"] == checkpoint["sha256"]
        assert receipt["source"]["sha256"] == frame["source"]["sha256"]
        assert sha(base.with_suffix(".npz")) == receipt["output_sha256"]
        assert receipt["psf_mode"] == "fixed_bank_mean_native_pixel_data_consistency"
        assert receipt["fixed_psf_bank_count"] == 25
        assert len(receipt["physical_step_strengths"]) == 4
        assert all(0 < value < .8 for value in receipt["physical_step_strengths"])
        receipts.append(receipt)
    assert len(receipts) == 930
    centers = ROOT / "results/centers"
    for run in plan["runs"]:
        name = run["run"]
        assert len(pd.read_csv(centers / (name + ".csv"))) == 279
        with np.load(centers / (name + ".npz"), allow_pickle=False) as z:
            assert z["points"].shape == (31, 9, 64, 2)
    comp = ROOT / "results/comparison"
    for run in plan["runs"]:
        for suffix in (".csv", ".npz"):
            name = run["run"] + suffix
            assert sha(ROOT / "evaluation/baseline_centers/R146-SEMCoreHaloPSF25-MatchedPairs" / name) == sha(R146 / "results/centers" / name)
    assert len(pd.read_csv(comp / "all_displacements.csv")) == 19800
    assert len(pd.read_csv(comp / "all_circles.csv")) == 92070
    assert len(pd.read_csv(comp / "paired_scan_intervals.csv")) == 50
    assert len(pd.read_csv(comp / "SEM_comparison.csv")) == 22
    corrected = pd.read_csv(comp / "SEM_corrected_size_by_pillar.csv")
    assert len(corrected) == 99
    assert corrected[corrected.model == "R147-FullResPSFConsistency"].sem_id.tolist() == [36,35,34,30,29,28,24,23,22]
    assert len(pd.read_csv(comp / "SEM_corrected_size_summary.csv")) == 11
    contour = pd.read_csv(comp / "SEM_contour_size_by_pillar.csv")
    assert len(contour) == 99
    assert contour[contour.model == "R147-FullResPSFConsistency"].sem_id.tolist() == [36,35,34,30,29,28,24,23,22]
    assert len(pd.read_csv(comp / "SEM_contour_size_summary.csv")) == 11
    check = load(comp / "complete.json")
    assert check["independent_new_circle_refits"] == 8370
    assert check["baseline_summary_max_difference_nm"] < 1e-4
    model = "R147-FullResPSFConsistency"
    real = pd.read_csv(comp / "displacement_summary.csv")
    assert len(real[real.model == model]) == 2
    old_real = pd.read_csv(R146 / "results/comparison/displacement_summary.csv")
    for kind in ("adjacent", "start"):
        row = real[(real.model == "R146-SEMCoreHaloPSF25-MatchedPairs") & (real.kind == kind)].iloc[0]
        earlier = old_real[(old_real.model == "R146-SEMCoreHaloPSF25-MatchedPairs") & (old_real.kind == kind)].iloc[0]
        for key in ("mae_nm", "repeatability_nm", "maximum_error_nm"):
            assert abs(row[key] - earlier[key]) < 1e-4
    result = dict(passed=True, model=model, updates=8192, generated_parents=768,
                  real_images=len(receipts), real_circles=8370,
                  psf_mode=receipts[0]["psf_mode"],
                  physical_step_strengths=receipts[0]["physical_step_strengths"],
                  checkpoint_sha256=checkpoint["sha256"],
                  complete_comparison=check, completed_utc=now())
    save(ROOT / "results/final_audit.json", result)
    print("FINAL_AUDIT_PASS", result["updates"], result["real_images"], result["real_circles"])


if __name__ == "__main__":
    main()

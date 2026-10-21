"""Audit complete training, 930 real outputs, 8370 contours, and comparisons."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
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
    plan = load(ROOT / "evaluation/capture_plan.json")
    receipts = []
    for frame in plan["frames"]:
        stem = f"{frame['index'] + 1:02d}"
        base = ROOT / "results/reconstruction" / frame["run"] / stem
        receipt = load(base.with_suffix(".json"))
        assert receipt["checkpoint_sha256"] == checkpoint["sha256"]
        assert receipt["source"]["sha256"] == frame["source"]["sha256"]
        assert sha(base.with_suffix(".npz")) == receipt["output_sha256"]
        assert len(receipt["PSF_indices"]) == len(receipt["PSF_weights"]) == 4
        assert len(set(receipt["PSF_indices"])) == 4
        assert abs(sum(receipt["PSF_weights"]) - 1) < 1e-5
        receipts.append(receipt)
    assert len(receipts) == 930
    centers = ROOT / "results/centers"
    for run in plan["runs"]:
        name = run["run"]
        assert len(pd.read_csv(centers / (name + ".csv"))) == 279
        with np.load(centers / (name + ".npz"), allow_pickle=False) as z:
            assert z["points"].shape == (31, 9, 64, 2)
    comp = ROOT / "results/comparison"
    assert len(pd.read_csv(comp / "all_displacements.csv")) == 16200
    assert len(pd.read_csv(comp / "all_circles.csv")) == 75330
    assert len(pd.read_csv(comp / "paired_scan_intervals.csv")) == 40
    assert len(pd.read_csv(comp / "SEM_comparison.csv")) == 18
    corrected = pd.read_csv(comp / "SEM_corrected_size_by_pillar.csv")
    assert len(corrected) == 81
    assert corrected[corrected.model == "R145-Center9PSF25-CorrectedPairs"].sem_id.tolist() == [36,35,34,30,29,28,24,23,22]
    assert len(pd.read_csv(comp / "SEM_corrected_size_summary.csv")) == 9
    check = load(comp / "complete.json")
    assert check["independent_new_circle_refits"] == 8370
    assert check["baseline_summary_max_difference_nm"] < 1e-4
    model = "R145-Center9PSF25-CorrectedPairs"
    real = pd.read_csv(comp / "displacement_summary.csv")
    assert len(real[real.model == model]) == 2
    result = dict(passed=True, model=model, updates=8192, generated_parents=768,
                  real_images=len(receipts), real_circles=8370,
                  distinct_top1_psfs=len({r["PSF_indices"][0] for r in receipts}),
                  checkpoint_sha256=checkpoint["sha256"],
                  complete_comparison=check, completed_utc=now())
    save(ROOT / "results/final_audit.json", result)
    print("FINAL_AUDIT_PASS", result["updates"], result["real_images"], result["real_circles"])


if __name__ == "__main__":
    main()

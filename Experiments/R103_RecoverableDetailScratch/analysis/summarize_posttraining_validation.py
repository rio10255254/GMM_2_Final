"""Audit all R103 post-training evidence and write one durable verdict."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "results" / "posttraining_validation"
RUN_ID = "training_R103_scratch_seed1030053_20260815_151436"
CHECKPOINT = ROOT / "weights" / "formal" / "seed_1030053" / RUN_ID / "epoch_048.pth.tar"


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def records(frame: pd.DataFrame) -> list[dict]:
    return json.loads(frame.to_json(orient="records"))


def main() -> None:
    registry = read_json(ROOT / "runs" / "formal_run_registry.json")
    formal = registry["formal_runs"]
    assert len(formal) == 1 and formal[0]["status"] == "completed"
    assert formal[0]["completed_epoch"] == 48 and formal[0]["run_id"] == RUN_ID
    assert formal[0]["source_audit"]["passed"] is True
    assert formal[0]["checkpoint_loaded"] is False
    assert formal[0]["teacher_used"] is False
    assert formal[0]["real_training_pixels"] is False
    assert formal[0]["optimizer_fresh"] is True

    summaries = {
        name: read_json(RESULTS / name / "summary.json")
        for name in (
            "candidate_selection", "real_sequences", "large_tile_parity",
            "model_internals", "sem_contour", "external_acm",
        )
    }
    assert all(item["status"] == "complete" for item in summaries.values())
    expected_hash = "68d367aad179adc4549f86ce850338eaeb723e727fe1e4c0475ea95e5938d5ff"
    assert sha256(CHECKPOINT) == expected_hash
    assert summaries["candidate_selection"]["internal_test_scenes"] == 125
    assert summaries["real_sequences"]["frames"] == 301
    assert summaries["real_sequences"]["motion_measurements"] == 6672
    assert summaries["real_sequences"]["all_sequences_pass"] is True
    assert summaries["large_tile_parity"]["frames"] == 3
    assert summaries["sem_contour"]["physical_pillars"] == 36
    assert summaries["sem_contour"]["exposures"] == 12
    assert summaries["external_acm"]["total_images"] == 200

    candidate = pd.read_csv(RESULTS / "candidate_selection" / "internal_test_metrics.csv")
    assert set(candidate["epoch"]) == {24, 32, 40, 48}
    e48 = candidate.loc[candidate["epoch"] == 48].iloc[0]

    motion = pd.read_csv(RESULTS / "real_sequences" / "motion_sequence_summary.csv")
    motion_wide = motion.pivot(index="sequence", columns="method", values="step_std_um")
    assert bool((motion_wide["R103E48"] < motion_wide["R61v16"]).all())
    r103_motion = motion.loc[motion["method"] == "R103E48"].copy()

    appearance = pd.read_csv(RESULTS / "real_sequences" / "appearance_sequence_summary.csv")
    appearance_wide = appearance.pivot(index="sequence", columns="method")
    assert bool((appearance_wide["mean_abs_change_flat_region_gray"]["R103E48"]
                 < appearance_wide["mean_abs_change_flat_region_gray"]["R61v16"]).all())

    sem_exposure = pd.read_csv(
        RESULTS / "sem_contour" / "results" / "tables" / "per_exposure_summary.csv"
    )
    sem_iou = sem_exposure.pivot(index="exposure", columns="method", values="iou")
    best_r103_exposures = [int(value) for value in sem_iou.index[sem_iou["R103E48"] > sem_iou["Raw"]]]
    worst_exposure = int((sem_iou["R103E48"] - sem_iou["Raw"]).idxmin())

    external_family: dict[str, list[dict]] = {}
    for suite in ("R73_novel_shapes", "R74_hard_microscopy"):
        family = pd.read_csv(
            RESULTS / "external_acm" / suite / "results" / "tables" / "family_summary.csv"
        )
        external_family[suite] = records(family)

    verdict = {
        "status": "complete",
        "formal_run": {
            "run_id": RUN_ID,
            "epochs": 48,
            "scratch_training_proven": True,
            "checkpoint": str(CHECKPOINT),
            "checkpoint_sha256": expected_hash,
            "parameter_count": int(formal[0]["parameter_count"]),
        },
        "selected_checkpoint": {
            "epoch": 48,
            "reason": "Best full internal-test PSNR, MAE, contour overlap, texture recovery, and paired observation score; E40 only had negligible identity and tile-consistency edges.",
            "internal_test": {key: float(e48[key]) for key in e48.index if key != "epoch"},
        },
        "evidence_counts": {
            "internal_synthetic_scenes": 125,
            "real_frames": 301,
            "real_motion_measurements": 6672,
            "sem_pillars": 36,
            "sem_exposures": 12,
            "external_exact_truth_images": 200,
            "large_frames_for_direct_tile_parity": 3,
        },
        "real_motion": {
            "all_six_sequences_pass": True,
            "r103_step_std_lower_than_r61_in_all_six": True,
            "r103_rows": records(r103_motion),
        },
        "large_frame_tile_parity": summaries["large_tile_parity"],
        "model_internal_behavior": summaries["model_internals"],
        "sem_shape": {
            "aggregate": summaries["sem_contour"]["method_summary"],
            "r103_better_than_raw_iou_exposures": best_r103_exposures,
            "worst_r103_exposure": worst_exposure,
            "interpretation": "R103 improves SEM overlap at exposures 13-17, fails sharply at exposure 18, and is approximately Raw at 19-24. R61 remains stronger in aggregate SEM overlap, while R103 usually preserves perimeter/circularity better than R61.",
        },
        "external_shape_truth": {
            "suite_summary": {
                key: value["method_summary"] for key, value in summaries["external_acm"]["suites"].items()
            },
            "family_summary": external_family,
            "interpretation": "R103 slightly harms already-clean novel shapes; on hard microscopy it improves area error and boundary-fade cases, but uneven illumination remains a major weakness and aggregate contour remains behind R61.",
        },
        "final_assessment": {
            "strengths": [
                "Real 5x/20x/50x motion is stable and at least as repeatable as R61.",
                "Flat regions and off-source areas are much less altered than by R61.",
                "All correction branches are active and mostly cooperate.",
                "Large tiled reconstruction is effectively identical to whole-frame reconstruction.",
                "Texture and edge detail are visibly restored without broad background remapping.",
            ],
            "limitations": [
                "Aggregate SEM coarse contour overlap remains behind R61.",
                "SEM contour response changes with exposure, with a clear failure at exposure 18.",
                "Uneven illumination is not corrected reliably.",
                "Clean inputs can receive small unnecessary contour changes.",
                "R103 should not replace R61 for the current SEM-contour thesis claim without another repair round.",
            ],
            "role": "Best current clean-scratch general-purpose research candidate for texture, real-image preservation, motion, and tiled deployment; not yet the universal or SEM-contour replacement model.",
        },
    }
    output = RESULTS / "final_summary.json"
    output.write_text(json.dumps(verdict, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({
        "status": "complete", "output": str(output),
        "checkpoint_sha256": expected_hash,
        "all_six_motion_sequences_pass": True,
        "worst_sem_exposure": worst_exposure,
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

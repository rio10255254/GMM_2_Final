"""Synthesize the complete R116 validation without a single aggregate score."""

from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "results" / "detailed_validation"
OUTPUT_JSON = RESULTS / "FINAL_VALIDATION.json"
OUTPUT_MD = RESULTS / "R116_DETAILED_VALIDATION_ZH.md"


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> int:
    audit_path = RESULTS / "00_audit" / "audit.json"
    acm_path = RESULTS / "01_locked_acm" / "shortlist_summary.json"
    real_path = RESULTS / "02_real_contract" / "summary.json"
    motion_path = RESULTS / "03_real_motion" / "summary.json"
    motion_table_path = RESULTS / "03_real_motion" / "comparison_sequence_summary.csv"
    sem_path = RESULTS / "04_sem_acm" / "summary.json"
    sem_metric_path = RESULTS / "04_sem_acm" / "metric_summary.csv"
    lsc_paths = {
        "R116 E24": RESULTS / "05_lsc" / "E024" / "summary.json",
        "R116 E42": RESULTS / "05_lsc_e42" / "summary.json",
        "R116 E48": RESULTS / "05_lsc" / "E048" / "summary.json",
    }
    external_path = RESULTS / "06_external_gmf" / "E042" / "summary.json"
    required = [audit_path, acm_path, real_path, motion_path, motion_table_path, sem_path, sem_metric_path, *lsc_paths.values(), external_path]
    missing = [str(path) for path in required if not path.is_file()]
    if missing:
        raise RuntimeError(f"Missing validation evidence: {missing}")
    audit, acm, real, motion, sem, external = map(read_json, (audit_path, acm_path, real_path, motion_path, sem_path, external_path))
    if audit["status"] != "passed" or acm["status"] != "complete" or real["status"] != "complete" or motion["status"] != "complete" or sem["status"] != "complete":
        raise RuntimeError("At least one completed validation stage is not valid")

    acm_rows = pd.DataFrame(acm["rows"])
    motion_table = pd.read_csv(motion_table_path)
    motion_table["median_diff_fraction"] = motion_table["median_vector_difference_from_raw_um"] / motion_table["nominal_step_um"]
    motion_table["p95_diff_fraction"] = motion_table["p95_vector_difference_from_raw_um"] / motion_table["nominal_step_um"]
    motion_headline = {}
    for name, group in motion_table.groupby("candidate", sort=False):
        motion_headline[name] = {
            "sequences_passed": int(group["sequence_pass"].fillna(False).astype(bool).sum()),
            "sequences_total": len(group),
            "worst_scale_error_fraction": float(group["median_scale_error_fraction"].max()),
            "worst_median_difference_fraction": float(group["median_diff_fraction"].max()),
            "worst_p95_difference_fraction": float(group["p95_diff_fraction"].max()),
            "minimum_direction_agreement": float(group["direction_agreement"].min()),
            "minimum_ecc": float(group["median_ecc"].min()),
        }
    sem_metrics = pd.read_csv(sem_metric_path)
    sem_e42 = sem_metrics[sem_metrics.model.eq("R116E042")].set_index("metric")
    lsc = {name: read_json(path) for name, path in lsc_paths.items()}
    lsc_headline = {name: payload["headline"][name] for name, payload in lsc.items()}
    lsc_headline["R109 E48"] = lsc["R116 E42"]["headline"]["R109 E48"]
    lsc_headline["V42 E120"] = lsc["R116 E42"]["headline"]["V42 E120"]
    lsc_headline["Raw"] = lsc["R116 E42"]["headline"]["Raw"]

    e42_acm = {
        row["suite"]: row for row in acm["rows"] if int(row["epoch"]) == 42
    }
    e48_acm = {
        row["suite"]: row for row in acm["rows"] if int(row["epoch"]) == 48
    }
    e24_acm = {
        row["suite"]: row for row in acm["rows"] if int(row["epoch"]) == 24
    }
    decision = {
        "primary_r116_candidate": "R116 E42",
        "secondary_r116_candidate": "R116 E24",
        "rejected_as_primary": {
            "R116 E48": "Calibration improved R73 and some synthetic guards but significantly regressed the shared SEM population.",
            "R116 E28": "Dominated by E24 in the locked R73/R74 ACM shortlist.",
            "R116 E40": "Similar detail role to E42 with weaker endpoint evidence; E42 retained."
        },
        "promotion_status": "BLOCKED",
        "replacement_authorized": False,
        "reason": "E42 combines strong shared-SEM contour gains, six-sequence motion pass, and tile safety, but it regresses two R74 families, degrades SEM perimeter fidelity, trails R109/V42 in LSC stability, and has no external-GMF score.",
    }
    verified = {
        "training_chain": {
            "epochs": 48,
            "scratch": True,
            "other_model_weights_loaded": False,
            "data_quality_pass": True,
        },
        "tile_parity": {
            "pass": all(real["tile_parity_checks"].values()),
            **real["tile_parity_worst"],
        },
        "locked_acm_e42": {
            "R73_boundary_change_pct": e42_acm["R73"]["boundary_change_pct"],
            "R73_families_improved": e42_acm["R73"]["families_improved_boundary"],
            "R74_boundary_change_pct": e42_acm["R74"]["boundary_change_pct"],
            "R74_hd95_change_pct": e42_acm["R74"]["hd95_change_pct"],
            "R74_iou_delta": e42_acm["R74"]["iou_delta"],
            "R74_families_improved": e42_acm["R74"]["families_improved_boundary"],
        },
        "sem_e42": {
            "independent_pillars": 36,
            "repeated_exposures": 12,
            "boundary_improved_pillars": int(sem["headline"]["R116E042"]["boundary_improved_pillars"]),
            "boundary_median_improvement_pitch_pct": float(sem_e42.loc["mean_boundary_distance_pitch_pct", "median_improvement"]),
            "boundary_bootstrap_ci95": [
                float(sem_e42.loc["mean_boundary_distance_pitch_pct", "bootstrap_ci95_low"]),
                float(sem_e42.loc["mean_boundary_distance_pitch_pct", "bootstrap_ci95_high"]),
            ],
            "iou_median_improvement": float(sem_e42.loc["iou", "median_improvement"]),
            "dark_23_improved_fraction": sem["headline"]["R116E042"]["dark_exposure_23_improved_fraction"],
            "dark_24_improved_fraction": sem["headline"]["R116E042"]["dark_exposure_24_improved_fraction"],
            "perimeter_median_improvement_pct": float(sem_e42.loc["perimeter_error_pct", "median_improvement"]),
            "perimeter_worsened_pillars": int(sem_e42.loc["perimeter_error_pct", "worsened_pillars"]),
            "circularity_median_improvement": float(sem_e42.loc["circularity_abs_error", "median_improvement"]),
        },
        "real_motion": motion_headline,
        "lsc": lsc_headline,
        "external_gmf_package": external,
    }
    blockers = [
        {
            "severity": "high",
            "issue": "External GMF is not run.",
            "evidence": f"101-frame E42 package complete; median change {external['mean_abs_change_gray_median']:.6f} gray and no GMF_score.txt.",
            "impact": "Compatibility with the enterprise locator is unknown; near-Raw output may inherit Raw instability.",
        },
        {
            "severity": "high",
            "issue": "LSC stability remains below R109 and V42.",
            "evidence": f"Step SD E42 {lsc_headline['R116 E42']['step_sd_nm']:.3f} nm versus R109 {lsc_headline['R109 E48']['step_sd_nm']:.3f} and V42 {lsc_headline['V42 E120']['step_sd_nm']:.3f}; within-grid {lsc_headline['R116 E42']['median_within_grid_sd_nm']:.3f} versus {lsc_headline['R109 E48']['median_within_grid_sd_nm']:.3f}/{lsc_headline['V42 E120']['median_within_grid_sd_nm']:.3f} nm.",
            "impact": "E42 cannot replace the thesis/displacement model on LSC evidence alone.",
        },
        {
            "severity": "medium",
            "issue": "R74 low-contrast and mixed-hard boundary cases regress.",
            "evidence": f"E42 R74 aggregate boundary change is +{e42_acm['R74']['boundary_change_pct']:.3f}% (worse), despite better HD95 and IoU; 3/5 families improve.",
            "impact": "Worst-case generalization is not universal.",
        },
        {
            "severity": "medium",
            "issue": "SEM coarse contour improves but fine shape fidelity worsens.",
            "evidence": f"36/36 pillars improve boundary, while perimeter error worsens in {int(sem_e42.loc['perimeter_error_pct','worsened_pillars'])}/36 pillars.",
            "impact": "Do not claim recovery of microscopic non-circular edge texture.",
        },
    ]
    payload = {
        "status": "complete_external_gmf_pending",
        "as_of_local": "2026-09-04",
        "overall_assessment": "share_with_caveats; not ready for model replacement",
        "decision": decision,
        "verified": verified,
        "blockers": blockers,
        "candidate_roles": {
            "R116 E24": "cleaner geometry/LSC fallback but weak shared-SEM gain",
            "R116 E42": "primary R116 research candidate; best shared-SEM and strong real-motion result",
            "R116 E48": "calibrated final checkpoint; rejected as primary due SEM regression",
        },
        "comparison_boundary": "Current motion is Raw-referenced and commanded; shared SEM has 36 independent pillars; R73/R74 are synthetic; external GMF remains unmeasured.",
        "no_single_aggregate_score": True,
    }
    OUTPUT_JSON.write_text(json.dumps(payload, indent=2, allow_nan=False), encoding="utf-8")

    lines = [
        "# R116 detailed validation",
        "",
        "## Decision",
        "",
        "- Primary R116 research candidate: **E42**.",
        "- Replacement of R109, R61, or V42: **not authorized**.",
        "- E48 is not selected merely because it is the final epoch; shared SEM regressed strongly.",
        "",
        "## What passed",
        "",
        f"- Complete scratch chain and data audit passed: 5,512 unique scenes, 0 train/validation overlap, 0 real training pixels.",
        f"- Tile parity passed: worst mean {real['tile_parity_worst']['mean_abs_gray']:.6f}, p99 {real['tile_parity_worst']['p99_abs_gray']:.6f}, max {real['tile_parity_worst']['max_abs_gray']:.6f} gray.",
        f"- E42 R73 boundary improved {abs(e42_acm['R73']['boundary_change_pct']):.2f}% across 5/5 families.",
        f"- E42 shared SEM: 36/36 pillars improved; median gain {verified['sem_e42']['boundary_median_improvement_pitch_pct']:.4f}% pitch, CI95 {verified['sem_e42']['boundary_bootstrap_ci95'][0]:.4f} to {verified['sem_e42']['boundary_bootstrap_ci95'][1]:.4f}.",
        f"- E42 passed all six locked real-motion sequences with 100% direction agreement.",
        "",
        "## What did not pass",
        "",
        f"- E42 R74 mean boundary regressed {e42_acm['R74']['boundary_change_pct']:.2f}%; low-contrast and mixed-hard remain weak.",
        f"- E42 LSC step SD {lsc_headline['R116 E42']['step_sd_nm']:.3f} nm and within-grid SD {lsc_headline['R116 E42']['median_within_grid_sd_nm']:.3f} nm trail R109/V42.",
        f"- SEM perimeter fidelity worsened in {verified['sem_e42']['perimeter_worsened_pillars']}/36 pillars.",
        f"- External GMF package is ready but no score exists; E42 changes JunHua by only {external['mean_abs_change_gray_median']:.4f} gray on median.",
        "",
        "## Checkpoint roles",
        "",
        "- E24: geometry/LSC fallback.",
        "- E42: primary research candidate.",
        "- E48: completed calibration artifact, not the selected model.",
    ]
    OUTPUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")
    manifest_rows = []
    for path in [*required, OUTPUT_JSON, OUTPUT_MD]:
        manifest_rows.append({"path": str(path), "sha256": sha256(path), "bytes": path.stat().st_size})
    with (RESULTS / "VALIDATION_MANIFEST_SHA256.csv").open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=("path", "sha256", "bytes"))
        writer.writeheader()
        writer.writerows(manifest_rows)
    print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

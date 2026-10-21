"""Final integrity audit for the R90 E55 validation evidence."""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / "reports" / "full_validation_epoch055"
RESULTS = ROOT / "results" / "full_validation_epoch055"
OUTPUT = REPORTS / "validation_audit.json"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def finite_payload(value) -> bool:
    if isinstance(value, dict):
        return all(finite_payload(item) for item in value.values())
    if isinstance(value, list):
        return all(finite_payload(item) for item in value)
    if isinstance(value, float):
        return math.isfinite(value)
    return True


def main() -> int:
    protocol = read_json(REPORTS / "validation_protocol.json")
    freeze = read_json(REPORTS / "checkpoint_freeze.json")
    checks: dict[str, bool] = {}
    candidate = protocol["comparison_models"]["R90E55"]
    checks["candidate_checkpoint_hash"] = sha256_file(Path(candidate["checkpoint"])) == candidate["checkpoint_sha256"] == freeze["checkpoint_sha256"]
    checks["candidate_frozen_before_holdout"] = freeze["status"] == "frozen_before_holdout_access" and bool(freeze["checkpoint_selection_from_holdout_forbidden"])
    checks["formal_baseline_not_reassigned"] = protocol["formal_project_baseline_unchanged"] == "COMBO"

    for label in ("r90e55", "r89e100"):
        report = read_json(REPORTS / f"sealed_holdout_{label}.json")
        metrics = report["metrics"]
        checks[f"holdout_{label}_complete"] = (
            report["status"] == "complete" and report["holdout_audit_passed"]
            and metrics["evaluated_scenes"] == 384 and metrics["evaluated_cases"] == 1504
            and finite_payload(report)
        )

    expected_frames = {"5x_0p5um": 50, "5x_1um": 50, "20x_0p5um": 50, "20x_1um": 50, "50x_0p5um": 51, "50x_1um": 50}
    for label in ("R89E100", "R90E55"):
        total = 0
        hash_ok = True
        identity_ok = True
        for sequence, expected in expected_frames.items():
            manifest = read_json(RESULTS / "reconstructions" / label / sequence / "reconstruction_manifest.json")
            total += len(manifest["records"])
            identity_ok &= len(manifest["records"]) == expected
            identity_ok &= manifest["checkpoint_sha256"] == protocol["comparison_models"][label]["checkpoint_sha256"]
            for record in manifest["records"]:
                source, output = Path(record["input"]), Path(record["output"])
                hash_ok &= source.is_file() and output.is_file()
                hash_ok &= sha256_file(source) == record["input_sha256"]
                hash_ok &= sha256_file(output) == record["output_sha256"]
        checks[f"{label}_real_reconstruction_301_frames"] = total == 301 and identity_ok
        checks[f"{label}_all_manifest_hashes_reproduced"] = hash_ok

    appearance = pd.read_csv(RESULTS / "tables" / "real_appearance_all_frames.csv")
    appearance_summary = pd.read_csv(RESULTS / "tables" / "real_appearance_sequence_summary.csv")
    checks["appearance_301_frames_three_methods"] = len(appearance) == 903 and len(appearance_summary) == 18 and appearance[["sequence", "frame_index"]].drop_duplicates().shape[0] == 301
    checks["appearance_values_finite"] = not appearance.isna().any().any()

    motion = pd.read_csv(RESULTS / "tables" / "real_motion_tile_measurements.csv")
    motion_summary = pd.read_csv(RESULTS / "tables" / "real_motion_sequence_summary.csv")
    checks["motion_locked_population_three_methods"] = len(motion) == 20016 and len(motion_summary) == 18
    reference_counts = motion.groupby(["sequence", "method"])["raw_reference_valid"].sum().unstack("method")
    checks["motion_raw_eligibility_identical_between_methods"] = bool((reference_counts.nunique(axis=1) == 1).all())
    r90_motion = motion_summary.loc[motion_summary["method"] == "R90E55"]
    checks["r90_real_motion_all_evaluable_and_direction_consistent"] = bool(
        (r90_motion["valid_fraction_within_raw_reference"] == 1.0).all()
        and (r90_motion["direction_agreement_fraction"] == 1.0).all()
    )

    tile = read_json(RESULTS / "tile_consistency.json")
    checks["tile_full_and_cross_scheme_exact"] = bool(tile["exactness"]["visually_lossless_below_0p1_gray"] and tile["exactness"]["maximum_tiled_vs_full_gray"] == 0.0 and tile["exactness"]["maximum_cross_scheme_gray"] == 0.0)

    sem = read_json(REPORTS / "sem_acm" / "summary.json")
    sem_methods = pd.read_csv(REPORTS / "sem_acm" / "method_summary.csv")
    sem_comparisons = pd.read_csv(REPORTS / "sem_acm" / "r90_paired_comparisons.csv")
    checks["sem_36_pillars_12_exposures_complete"] = bool(sem["audit"]["physical_pillars"] == 36 and sem["audit"]["exposures"] == 12 and len(sem_methods) == 4 and len(sem_comparisons) == 21)
    checks["sem_raw_reference_reproduced_exactly"] = bool(sem["audit"]["raw_reference_exact_between_r69_and_r89"])
    checks["sem_sensitivity_reproduced_and_exposure18_failure_robust"] = bool(
        sem["sensitivity_audit"]["primary_reproduction_within_1e_6"]
        and sem["sensitivity_audit"]["exposure_18_worsens_all_presets"]
    )
    radial = read_json(REPORTS / "sem_acm" / "radial_transition_diagnostic.json")
    checks["sem_exposure18_acm_failure_has_independent_edge_shift_support"] = bool(radial["acm_exposure_18_failure_has_independent_edge_shift_support"])

    checks["all_representative_figures_exist"] = all(
        (RESULTS / "figures" / f"{sequence}_representative.png").is_file()
        for sequence in expected_frames
    ) and all(Path(path).is_file() for path in sem["overlay_files"] + sem["full_comparison_files"])
    passed = all(checks.values())
    report = {
        "status": "passed" if passed else "failed",
        "protocol_id": protocol["protocol_id"],
        "checks": checks,
        "check_count": len(checks),
        "failed_checks": [name for name, value in checks.items() if not value],
        "scientific_conclusion_not_audit_gate": "R90 E55 is a strong balanced research candidate but not a universal stable release because exposure 18 and 19 show reproducible contour expansion and clean-input alteration remains non-zero.",
    }
    OUTPUT.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())

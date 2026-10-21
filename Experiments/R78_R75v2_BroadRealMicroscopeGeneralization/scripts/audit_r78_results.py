from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "results"
TABLES = RESULTS / "tables"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    motion = pd.read_csv(TABLES / "sequence_method_summary.csv")
    acm = pd.read_csv(TABLES / "acm_sem_truth_summary.csv")
    followup = pd.read_csv(TABLES / "followup_5x_summary.csv")
    decision = json.loads((RESULTS / "decision.json").read_text(encoding="utf-8"))
    paired = motion.pivot(index="sequence", columns="method", values="raw_reference_measurements")
    checks = {
        "primary_rows_are_6_sequences_x_2_models": len(motion) == 12
        and motion["sequence"].nunique() == 6
        and motion["method"].nunique() == 2,
        "primary_keys_unique": not motion.duplicated(["sequence", "method"]).any(),
        "primary_summary_has_no_missing_values": not motion.isna().any().any(),
        "raw_reference_population_identical_between_models": bool(
            (paired["R61v16"] == paired["R75v2E100"]).all()
        ),
        "both_models_have_six_primary_passes": bool(
            (motion.groupby("method")["sequence_pass"].sum() == 6).all()
        ),
        "acm_has_36_independent_pillars_per_method": bool(
            len(acm) == 3 and (acm["independent_pillars"] == 36).all()
        ),
        "followup_has_50_frames_per_sequence_setting": bool(
            len(followup) == 6 and (followup["frames"] == 50).all()
        ),
        "followup_disclosed_as_post_hoc": bool(
            decision["post_hoc_5x_confirmation"]["evidence_role"] == "post_hoc_confirmatory"
        ),
        "universal_claim_not_made": not bool(decision["universal_cross_sample_pass"]),
        "recommendation_matches_worst_case_result": bool(
            decision["worst_case_first_preference"] == "R61v16"
            and decision["current_recommendation"]["project_generalization_baseline"] == "R61v16"
        ),
    }
    output = {
        "status": "pass" if all(checks.values()) else "fail",
        "checks": checks,
        "checks_passed": sum(checks.values()),
        "checks_total": len(checks),
        "table_sha256": {
            name: digest(TABLES / name)
            for name in [
                "sequence_method_summary.csv",
                "acm_sem_truth_summary.csv",
                "followup_5x_summary.csv",
            ]
        },
    }
    (RESULTS / "data_quality_audit.json").write_text(
        json.dumps(output, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(json.dumps(output, indent=2, ensure_ascii=False))
    if output["status"] != "pass":
        raise SystemExit(1)


if __name__ == "__main__":
    main()

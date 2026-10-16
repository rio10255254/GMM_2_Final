"""Finalize replacement status with LSC, ACM, and external GMF as primary evidence."""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "results"
POLICY = ROOT / "config" / "replacement_metric_policy_v3_lsc_primary.json"


def main() -> int:
    lsc = json.loads((RESULTS / "lsc_current_top30" / "lsc_current_top30_summary.json").read_text(encoding="utf-8"))
    gmf = json.loads((RESULTS / "external_gmf_three_way" / "analysis_summary.json").read_text(encoding="utf-8"))
    previous = json.loads((RESULTS / "replacement_decision_v2_acm_displacement_primary.json").read_text(encoding="utf-8"))
    sem = previous["primary_outcomes"]["sem_acm_full_contour"]
    boundary = previous["primary_outcomes"]["frozen_thesis_displacement"]
    cd = previous["supporting_evidence"]["cd_secondary_only"]

    decision = {
        "status": "complete",
        "generated_local": datetime.now().astimezone().isoformat(),
        "metric_policy": str(POLICY),
        "decision": "retain V42 E120 as the current thesis-results model",
        "replacement_approved": False,
        "confidence": "high for external GMF; shared/tied for LSC; mixed for ACM",
        "primary_outcomes": {
            "sem_acm_full_contour": sem,
            "thesis_lsc_displacement": {
                "outcome": "equivalent",
                "method": lsc["method"],
                "selection": lsc["selection"],
                "v42": lsc["v42"],
                "r109": lsc["r109"],
                "comparison": lsc["comparison"],
                "uncertainty": lsc["uncertainty"],
                "determinism_spot_check_max_px": lsc["determinism_spot_check_max_px"],
            },
            "external_gmf_displacement": {
                "winner": "V42 E120",
                "v42": gmf["arms"]["V42 E120"],
                "r109": gmf["arms"]["R109 E48"],
                "comparison": gmf["comparison"]["v42_vs_r109"],
                "uncertainty": gmf["paired_moving_block_bootstrap"]["V42_vs_R109"],
            },
        },
        "supporting_evidence": {
            "boundary_consensus_120_steps": {
                "role": "secondary diagnostic because the thesis displacement readout is LSC",
                "result": boundary,
            },
            "cd": cd,
            "line_pattern": previous["supporting_evidence"]["line_pattern"],
            "engineering": previous["supporting_evidence"]["engineering"],
        },
        "corrected_interpretation": [
            "The earlier claim that R109 was weaker on the thesis 120-step displacement came from the boundary-consensus readout, not LSC.",
            "With the current Chapter 6.2 top-30 population and deterministic LSC execution, V42 and R109 are statistically equivalent on displacement.",
            "R109 is better on LSC nine-pillar dispersion by a small amount, while V42 is slightly better on nominal error and cross-axis displacement; none of these differences is statistically resolved.",
            "V42 remains selected because its same-frame external-GMF stability is decisively stronger, while ACM is mixed rather than a clear R109 win.",
        ],
        "recommended_thesis_use": {
            "primary_model": "V42 E120",
            "r109_role": "co-equal LSC displacement candidate and stronger dark-exposure/generalization extension",
            "replacement_condition": "R109 would need to close the external-GMF gap while retaining its ACM worst-case and line-pattern advantages.",
        },
        "lsc_methodology_warning": {
            "historical_r80_issue": "skimage Chan-Vese uses a stateful alternating curvature operator; uncontrolled method order can alternate answers between calls",
            "r111_fix": "reset the curvature cycle before every pillar and method measurement",
            "historical_r80_selection_overlap_with_current_top30": "87 of 120 steps"
        }
    }
    path = RESULTS / "replacement_decision_v3_lsc_primary.json"
    path.write_text(json.dumps(decision, ensure_ascii=False, indent=2), encoding="utf-8")
    (RESULTS / "replacement_decision.json").write_text(json.dumps(decision, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(decision, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Finalize the R109-versus-V42 decision with ACM and displacement as primary outcomes."""
from __future__ import annotations

import json
import shutil
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "results"
POLICY_PATH = ROOT / "config" / "replacement_metric_policy_v2.json"
R70 = Path(r"D:\GMM_2_Final\Experiments\R70_V42ACMContourSEMValidation")
R109 = Path(r"D:\GMM_2_Final\Experiments\R109_StagedMidpointWidthScratch")


def sem_comparison() -> dict[str, object]:
    v42_paired = pd.read_csv(R70 / "results" / "tables" / "v42_paired_comparison_summary.csv")
    v42_values = {
        row.metric: float(row.target_median)
        for row in v42_paired.loc[v42_paired["comparison"] == "Raw_to_V42E120"].itertuples(index=False)
    }
    r109_selection = json.loads((R109 / "results" / "FINAL_SELECTION.json").read_text(encoding="utf-8"))
    r109 = r109_selection["external_acm"]["SEM_per_pillar"]

    v42_exposure = pd.read_csv(R70 / "results" / "tables" / "three_method_per_exposure_summary.csv")
    r109_metrics = pd.read_csv(
        R109
        / "results"
        / "posttraining_acm"
        / "E048"
        / "SEM"
        / "results"
        / "tables"
        / "primary_contour_metrics.csv"
    )
    r109_exposure = (
        r109_metrics.groupby(["exposure", "method"])[["iou", "mean_boundary_distance_pitch_pct"]]
        .median()
        .unstack("method")
    )
    exposure_rows: list[dict[str, object]] = []
    for exposure in range(13, 25):
        current = r109_exposure.loc[exposure].xs("R109_E048", level=1)
        prior = v42_exposure.loc[v42_exposure["exposure"] == exposure].iloc[0]
        v42_boundary = float(prior["v42e120_median_mean_boundary_distance_pitch_pct"])
        r109_boundary = float(current["mean_boundary_distance_pitch_pct"])
        exposure_rows.append(
            {
                "exposure": exposure,
                "v42_iou": float(prior["v42e120_median_iou"]),
                "r109_iou": float(current["iou"]),
                "v42_boundary": v42_boundary,
                "r109_boundary": r109_boundary,
                "winner": "R109" if r109_boundary < v42_boundary else "V42",
            }
        )
    exposure_table = pd.DataFrame(exposure_rows)
    exposure_table.to_csv(RESULTS / "sem_acm_exposure_v42_vs_r109.csv", index=False, encoding="utf-8-sig")
    return {
        "aggregate": {
            "v42_boundary_pitch_pct": v42_values["mean_boundary_distance_pitch_pct"],
            "r109_boundary_pitch_pct": float(r109["model_boundary_pitch_pct"]),
            "v42_iou": v42_values["iou"],
            "r109_iou": float(r109["model_iou"]),
            "v42_area_error_pct": v42_values["area_error_pct"],
            "r109_area_error_pct": float(r109["model_area_error_pct"]),
            "v42_perimeter_error_pct": v42_values["perimeter_error_pct"],
            "r109_perimeter_error_pct": float(r109["model_perimeter_error_pct"]),
            "main_boundary_winner": "V42",
            "perimeter_winner": "R109",
        },
        "exposure": {
            "v42_wins": int((exposure_table["winner"] == "V42").sum()),
            "r109_wins": int((exposure_table["winner"] == "R109").sum()),
            "v42_winning_range": "13-19",
            "r109_winning_range": "20-24",
            "v42_worst_boundary": float(exposure_table["v42_boundary"].max()),
            "r109_worst_boundary": float(exposure_table["r109_boundary"].max()),
            "worst_case_winner": "R109",
        },
        "outcome": "split: V42 leads aggregate/normal exposure; R109 leads dark exposure, perimeter, and worst case",
    }


def main() -> int:
    policy = json.loads(POLICY_PATH.read_text(encoding="utf-8"))
    gmf = json.loads((RESULTS / "external_gmf_three_way" / "analysis_summary.json").read_text(encoding="utf-8"))
    displacement = pd.read_csv(RESULTS / "thesis_displacement_comparison" / "summary.csv")
    displacement_qa = json.loads((RESULTS / "thesis_displacement_comparison" / "qa.json").read_text(encoding="utf-8"))
    line = pd.read_csv(RESULTS / "line_pattern_comparison" / "tables" / "line_displacement_pooled.csv", encoding="utf-8-sig").set_index("method")
    cd = pd.read_csv(RESULTS / "thesis_cd_comparison" / "cd_threshold_robust_summary.csv").set_index("case")
    pooled = displacement.loc[displacement["population"] == "All paired steps"].iloc[0]
    sem = sem_comparison()

    primary = {
        "sem_acm_full_contour": sem,
        "external_gmf_displacement": {
            "winner": "V42 E120",
            "v42": gmf["arms"]["V42 E120"],
            "r109": gmf["arms"]["R109 E48"],
            "v42_reduction_vs_r109": gmf["comparison"]["v42_vs_r109"],
            "bootstrap": gmf["paired_moving_block_bootstrap"]["V42_vs_R109"],
        },
        "frozen_thesis_displacement": {
            "winner": "V42 E120",
            "steps": 120,
            "v42_command_mae_nm": float(pooled["v42_command_mae_nm"]),
            "r109_command_mae_nm": float(pooled["r109_command_mae_nm"]),
            "v42_within_grid_mean_nm": float(pooled["v42_within_mean_nm"]),
            "r109_within_grid_mean_nm": float(pooled["r109_within_mean_nm"]),
            "r109_better_command_steps": displacement_qa["r109_better_command_than_v42_count"],
            "r109_better_within_steps": displacement_qa["r109_better_within_than_v42_count"],
            "r109_evaluable_steps": displacement_qa["r109_evaluable_steps"],
        },
    }
    supporting = {
        "line_pattern": {
            "winner": "R109 E48",
            "v42_boundary_mae_nm": float(line.loc["V42 E120", "boundary_mae_nm"]),
            "r109_boundary_mae_nm": float(line.loc["R109 E48", "boundary_mae_nm"]),
            "v42_profile_mae_nm": float(line.loc["V42 E120", "profile_mae_nm"]),
            "r109_profile_mae_nm": float(line.loc["R109 E48", "profile_mae_nm"]),
        },
        "cd_secondary_only": {
            "role": policy["cd_role"],
            "v42_robust_median_abs_error_nm": float(cd.loc["v42_e120", "pooled_median_abs_error_nm"]),
            "r109_robust_median_abs_error_nm": float(cd.loc["r109_e48", "pooled_median_abs_error_nm"]),
            "does_not_control_decision": True,
        },
        "engineering": {
            "r109_parameters": 678291,
            "v42_parameters": 4024238,
            "r109_is_smaller": True,
            "v42_full_5120_execution": "failed; requested about 84.38 GiB",
            "v42_tiled_execution": "complete; tested grid comparison max 1 gray level",
            "r109_tiled_execution": "complete; tested grid comparison max 1 gray level",
        },
    }

    previous = RESULTS / "replacement_decision.json"
    archived = RESULTS / "replacement_decision_v1_cd_influenced.json"
    if previous.is_file() and not archived.is_file():
        shutil.copy2(previous, archived)

    decision = {
        "status": "complete",
        "generated_local": datetime.now().astimezone().isoformat(),
        "metric_policy": str(POLICY_PATH),
        "decision": "retain V42 E120 as the current thesis-results model",
        "replacement_approved": False,
        "confidence": "high",
        "primary_outcomes": primary,
        "supporting_evidence": supporting,
        "reasoning_summary": [
            "CD was demoted to a secondary compatibility check and does not control this decision.",
            "SEM ACM is split: V42 is slightly better overall and in normal exposures, while R109 is better in dark exposures, perimeter, and worst-case boundary distance.",
            "V42 decisively outperforms R109 on the same-frame external GMF stability test.",
            "V42 also retains better nine-pillar consistency and slightly better command MAE on the exact frozen 120 thesis steps.",
            "R109 is the stronger generalization and engineering research model, but replacing V42 would weaken the thesis's main displacement evidence.",
        ],
        "recommended_thesis_use": {
            "primary_model": "V42 E120",
            "r109_role": "new generalization and worst-case robustness extension; not a replacement for the current numerical thesis tables",
            "suggested_story": "V42 provides the strongest current metrology result, while R109 demonstrates a synthetic-only path toward broader shape, dark-exposure, line-pattern, and tiled-image generalization.",
        },
    }
    (RESULTS / "replacement_decision_v2_acm_displacement_primary.json").write_text(
        json.dumps(decision, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    previous.write_text(json.dumps(decision, ensure_ascii=False, indent=2), encoding="utf-8")

    local_path = RESULTS / "local_qualification_summary.json"
    local = json.loads(local_path.read_text(encoding="utf-8"))
    local["status"] = "complete"
    local["external_gmf"]["v42_coordinates"] = "complete"
    local["external_gmf"]["analysis"] = str(RESULTS / "external_gmf_three_way" / "analysis_summary.json")
    local["external_gmf"]["replacement_decision"] = str(RESULTS / "replacement_decision_v2_acm_displacement_primary.json")
    local_path.write_text(json.dumps(local, ensure_ascii=False, indent=2), encoding="utf-8")

    print(json.dumps(decision, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

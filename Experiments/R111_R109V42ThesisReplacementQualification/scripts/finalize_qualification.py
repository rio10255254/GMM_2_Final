"""Consolidate the local thesis qualification and the pending V42 GMF handoff."""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "results"
THESIS_RESULTS = Path(
    r"D:\GMM_2_Final\Thesis_MOSR_Evidence\Final_Data_Figures\04_V42_NEURAL_NETWORK_RESULTS"
)
R109_ROOT = Path(r"D:\GMM_2_Final\Experiments\R109_StagedMidpointWidthScratch")
R70_ROOT = Path(r"D:\GMM_2_Final\Experiments\R70_V42ACMContourSEMValidation")
V42_GMF = ROOT / "external_gmf_v42"


def lower_row(metric: str, unit: str, v42: float, r109: float, scope: str, note: str = "") -> dict[str, object]:
    return {
        "metric": metric,
        "unit": unit,
        "v42": v42,
        "r109": r109,
        "better": "lower",
        "winner": "R109" if r109 < v42 else "V42" if v42 < r109 else "tie",
        "r109_change_vs_v42_pct": (r109 / v42 - 1.0) * 100.0 if v42 != 0 else np.nan,
        "scope": scope,
        "note": note,
    }


def main() -> int:
    cd50 = pd.read_csv(RESULTS / "thesis_cd_comparison" / "cd_50pct_summary.csv")
    cdrobust = pd.read_csv(RESULTS / "thesis_cd_comparison" / "cd_threshold_robust_summary.csv")
    displacement = pd.read_csv(RESULTS / "thesis_displacement_comparison" / "summary.csv")
    line_sharp = pd.read_csv(RESULTS / "line_pattern_comparison" / "tables" / "line_sharpness_summary.csv", encoding="utf-8-sig")
    line_disp = pd.read_csv(RESULTS / "line_pattern_comparison" / "tables" / "line_displacement_pooled.csv", encoding="utf-8-sig")
    circular = pd.read_csv(RESULTS / "circular_edge_comparison" / "circular_feature_method_summary.csv")
    v42_sem = pd.read_csv(R70_ROOT / "results" / "tables" / "v42_paired_comparison_summary.csv")
    r109_selection = json.loads((R109_ROOT / "results" / "FINAL_SELECTION.json").read_text(encoding="utf-8"))
    v42_gmf_manifest = json.loads((V42_GMF / "package_manifest.json").read_text(encoding="utf-8"))

    rows: list[dict[str, object]] = []
    get_cd50 = lambda case: float(cd50.loc[cd50["case"] == case, "mean_abs_error_nm"].iloc[0])
    get_cdrobust = lambda case: float(cdrobust.loc[cdrobust["case"] == case, "pooled_median_abs_error_nm"].iloc[0])
    rows.append(lower_row("Center-nine CD at 50%", "nm MAE", get_cd50("v42_e120"), get_cd50("r109_e48"), "exact thesis static image and centers"))
    rows.append(lower_row("Center-nine threshold-robust CD", "nm median absolute error", get_cdrobust("v42_e120"), get_cdrobust("r109_e48"), "exact thesis image, 35%-65%, two profile modes"))

    pooled = displacement.loc[displacement["population"] == "All paired steps"].iloc[0]
    rows.append(lower_row("Frozen 120-step command error", "nm MAE", float(pooled["v42_command_mae_nm"]), float(pooled["r109_command_mae_nm"]), "same Raw-selected 30 steps x four sequences"))
    rows.append(lower_row("Frozen 120-step nine-pillar disagreement", "nm mean", float(pooled["v42_within_mean_nm"]), float(pooled["r109_within_mean_nm"]), "same Raw-selected 30 steps x four sequences"))

    for orientation in ("horizontal_lines", "vertical_lines"):
        subset = line_sharp.loc[line_sharp["orientation"] == orientation].set_index("method")
        rows.append(lower_row(f"{orientation} edge width", "nm", float(subset.loc["V42 E120", "median_transition_width_nm"]), float(subset.loc["R109 E48", "median_transition_width_nm"]), "same 60 Raw-selected 50x line frames"))
    line_index = line_disp.set_index("method")
    rows.append(lower_row("Line boundary displacement", "nm MAE", float(line_index.loc["V42 E120", "boundary_mae_nm"]), float(line_index.loc["R109 E48", "boundary_mae_nm"]), "same 60 Raw-selected 50x steps"))
    rows.append(lower_row("Line full-profile displacement", "nm MAE", float(line_index.loc["V42 E120", "profile_mae_nm"]), float(line_index.loc["R109 E48", "profile_mae_nm"]), "same 60 Raw-selected 50x steps"))

    circ = circular.set_index(["magnification", "morphology", "method"])
    for magnification in ("50x", "20x"):
        for morphology in ("pillar", "via"):
            rows.append(
                lower_row(
                    f"{magnification} {morphology} radial CD midpoint",
                    "nm MAE",
                    float(circ.loc[(magnification, morphology, "V42 E120"), "midpoint_mae_nm"]),
                    float(circ.loc[(magnification, morphology, "R109 E48"), "midpoint_mae_nm"]),
                    "same first sequence frame, 35%-65% radial interval",
                )
            )

    v42_values = {
        row.metric: float(row.target_median)
        for row in v42_sem.loc[v42_sem["comparison"] == "Raw_to_V42E120"].itertuples(index=False)
    }
    r109_sem = r109_selection["external_acm"]["SEM_per_pillar"]
    rows.append(lower_row("Shared SEM mean boundary distance", "% pillar pitch", v42_values["mean_boundary_distance_pitch_pct"], float(r109_sem["model_boundary_pitch_pct"]), "same 36 pillars and 12 exposures"))
    rows.append(lower_row("Shared SEM perimeter error", "%", v42_values["perimeter_error_pct"], float(r109_sem["model_perimeter_error_pct"]), "same 36 pillars and 12 exposures"))

    comparison = pd.DataFrame(rows)
    comparison.to_csv(RESULTS / "capability_comparison.csv", index=False, encoding="utf-8-sig")

    displacement_qa = json.loads((RESULTS / "thesis_displacement_comparison" / "qa.json").read_text(encoding="utf-8"))
    v42_score = V42_GMF / "_gmf_scores" / "pitch1um_y100_v42_e120_tiled" / "GMF_score.txt"
    decision = {
        "status": "local_complete_external_v42_gmf_pending" if not v42_score.is_file() else "external_v42_gmf_present_needs_analysis",
        "generated_local": datetime.now().astimezone().isoformat(),
        "current_recommendation": "retain V42 as the thesis-results model; keep R109 as the stronger generalization/application candidate",
        "replacement_approved": False,
        "why_not_yet": [
            "R109 is worse than V42 on both the nominal and threshold-robust center-nine CD readouts.",
            "R109 is slightly worse on command MAE and materially worse on nine-pillar disagreement across the frozen 120 thesis steps.",
            "The same-101-frame V42 external-GMF coordinates are still missing.",
        ],
        "where_r109_is_stronger": [
            "50x line sharpness and line displacement preservation",
            "50x and 20x pillar radial midpoint accuracy on the displacement-sequence first frames",
            "dark-exposure SEM robustness and SEM perimeter error",
            "model size, synthetic-only scratch lineage, and practical tiled large-image execution",
        ],
        "frozen_population_integrity": {
            "steps": displacement_qa["frozen_steps"],
            "r109_evaluable_steps": displacement_qa["r109_evaluable_steps"],
            "raw_dx_reproduction_difference_um": displacement_qa["raw_recomputed_max_dx_difference_um"],
            "raw_within_reproduction_difference_nm": displacement_qa["raw_recomputed_max_within_difference_nm"],
        },
        "external_gmf": {
            "v42_image_folder": str(V42_GMF / "pitch1um_y100_v42_e120_tiled" / "bmp"),
            "v42_score_folder": str(V42_GMF / "_gmf_scores" / "pitch1um_y100_v42_e120_tiled"),
            "v42_coordinate_present": v42_score.is_file(),
            "v42_full_frame_5120": v42_gmf_manifest["full_frame_5120_status"],
            "v42_tested_tile_parity": v42_gmf_manifest["tile_grid_sensitivity"],
        },
        "comparison_table": str(RESULTS / "capability_comparison.csv"),
    }
    (RESULTS / "replacement_decision.json").write_text(json.dumps(decision, ensure_ascii=False, indent=2), encoding="utf-8")

    local_summary_path = RESULTS / "local_qualification_summary.json"
    local_summary = json.loads(local_summary_path.read_text(encoding="utf-8"))
    local_summary["external_gmf"] = {
        "r109": "complete",
        "v42_images": "complete",
        "v42_coordinates": "present" if v42_score.is_file() else "pending external tool",
        "package": str(V42_GMF),
        "replacement_decision": decision["status"],
    }
    local_summary_path.write_text(json.dumps(local_summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(decision, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

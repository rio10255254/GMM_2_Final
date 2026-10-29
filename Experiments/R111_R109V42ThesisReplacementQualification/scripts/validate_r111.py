"""Independent completion checks for R111 local evidence and V42 GMF handoff."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime
from pathlib import Path

import cv2
import numpy as np
import pandas as pd
PROJECT_ROOT = Path(__file__).resolve().parents[3]


ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "results"
CONFIG = json.loads((ROOT / "config" / "qualification.json").read_text(encoding="utf-8"))
V42_GMF = ROOT / "external_gmf_v42"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    failures: list[str] = []
    checks: dict[str, object] = {}

    for key, path_field, hash_field in (
        ("r109_checkpoint", str(PROJECT_ROOT / CONFIG["models"]["r109_e48"]["checkpoint"]), CONFIG["models"]["r109_e48"]["sha256"]),
        ("v42_checkpoint", str(PROJECT_ROOT / CONFIG["models"]["v42_e120"]["checkpoint"]), CONFIG["models"]["v42_e120"]["sha256"]),
        ("sequence_config", str(PROJECT_ROOT / CONFIG["frozen_contract"]["sequence_config"]), CONFIG["frozen_contract"]["sequence_config_sha256"]),
        ("top30_selection", str(PROJECT_ROOT / CONFIG["frozen_contract"]["top30_selection"]), CONFIG["frozen_contract"]["top30_selection_sha256"]),
    ):
        path = Path(path_field)
        actual = sha256(path) if path.is_file() else "missing"
        checks[key] = {"exists": path.is_file(), "sha256": actual, "matches": actual == hash_field}
        if actual != hash_field:
            failures.append(f"{key} hash mismatch")

    raw_lock = RESULTS / "thesis_displacement_r109" / "tables" / "raw_eligibility_locked_before_v42.csv"
    expected_raw_lock = CONFIG["frozen_contract"]["raw_lock_sha256"]
    checks["raw_lock"] = {"sha256": sha256(raw_lock), "matches": sha256(raw_lock) == expected_raw_lock}
    if sha256(raw_lock) != expected_raw_lock:
        failures.append("Raw lock changed")

    steps = pd.read_csv(RESULTS / "thesis_displacement_comparison" / "frozen_120_steps.csv")
    summary = pd.read_csv(RESULTS / "thesis_displacement_comparison" / "summary.csv")
    checks["displacement"] = {
        "rows": len(steps),
        "unique_keys": int(steps[["sequence", "end_frame_index"]].drop_duplicates().shape[0]),
        "r109_evaluable": int(steps["r109_evaluable"].astype(str).str.lower().isin({"true", "1", "yes"}).sum()),
        "sequence_counts": steps.groupby("sequence").size().to_dict(),
    }
    if len(steps) != 120 or checks["displacement"]["unique_keys"] != 120 or checks["displacement"]["r109_evaluable"] != 120:
        failures.append("Frozen displacement population incomplete")
    pooled = summary.loc[summary["population"] == "All paired steps"].iloc[0]
    independent_r109_mae = float(
        np.mean(np.abs(steps["r109_boundary_dx_um"].abs() - steps["nominal_step_um"])) * 1000.0
    )
    if abs(independent_r109_mae - float(pooled["r109_command_mae_nm"])) > 1e-10:
        failures.append("R109 displacement MAE mismatch")

    cd50 = pd.read_csv(RESULTS / "thesis_cd_comparison" / "cd_50pct_summary.csv")
    cdrobust = pd.read_csv(RESULTS / "thesis_cd_comparison" / "cd_threshold_robust_summary.csv")
    cdmeasure = pd.read_csv(RESULTS / "thesis_cd_comparison" / "cd_threshold_measurements.csv")
    checks["cd"] = {
        "nominal_cases": sorted(cd50["case"].tolist()),
        "robust_cases": sorted(cdrobust["case"].tolist()),
        "threshold_rows": len(cdmeasure),
        "failed_crossings": int((cdmeasure["status"] != "ok").sum()),
    }
    if len(cd50) != 3 or len(cdrobust) != 3 or len(cdmeasure) != 378 or checks["cd"]["failed_crossings"]:
        failures.append("CD evidence incomplete")

    circular = pd.read_csv(RESULTS / "circular_edge_comparison" / "circular_feature_threshold_measurements.csv")
    line_frame = pd.read_csv(RESULTS / "line_pattern_comparison" / "tables" / "line_frame_metrics.csv", encoding="utf-8-sig")
    line_step = pd.read_csv(RESULTS / "line_pattern_comparison" / "tables" / "line_displacement_per_step.csv", encoding="utf-8-sig")
    checks["transfer"] = {
        "circular_rows": len(circular),
        "circular_methods": sorted(circular["method"].unique().tolist()),
        "line_frame_rows": len(line_frame),
        "line_step_rows": len(line_step),
        "line_methods": sorted(line_step["method"].unique().tolist()),
        "line_missing_steps": int(line_step[["boundary_step_um", "profile_step_um"]].isna().any(axis=1).sum()),
    }
    if len(circular) != 756 or len(line_frame) != 360 or len(line_step) != 180 or checks["transfer"]["line_missing_steps"]:
        failures.append("Transfer evidence incomplete")

    v42_dir = V42_GMF / "pitch1um_y100_v42_e120_tiled" / "bmp"
    names = sorted(path.name for path in v42_dir.glob("*.bmp"))
    expected_names = [f"frame_{index:04d}.bmp" for index in range(101)]
    bad_shapes = 0
    for name in names:
        image = cv2.imdecode(np.fromfile(str(v42_dir / name), np.uint8), cv2.IMREAD_GRAYSCALE)
        bad_shapes += int(image is None or image.shape != (5120, 5120))
    manifest = json.loads((V42_GMF / "package_manifest.json").read_text(encoding="utf-8"))
    checks["v42_gmf"] = {
        "images": len(names),
        "exact_names": names == expected_names,
        "bad_shapes": bad_shapes,
        "non_bmp_files_in_image_folder": len([path for path in v42_dir.iterdir() if path.is_file() and path.suffix.lower() != ".bmp"]),
        "tile_parity_max_gray": manifest["tile_grid_sensitivity"]["max_gray_difference"],
        "full_frame_status": manifest["full_frame_5120_status"],
        "score_present": (V42_GMF / "_gmf_scores" / "pitch1um_y100_v42_e120_tiled" / "GMF_score.txt").is_file(),
    }
    if names != expected_names or bad_shapes or checks["v42_gmf"]["non_bmp_files_in_image_folder"]:
        failures.append("V42 GMF image package invalid")

    gmf_summary = json.loads((RESULTS / "external_gmf_three_way" / "analysis_summary.json").read_text(encoding="utf-8"))
    gmf_table = pd.read_csv(RESULTS / "external_gmf_three_way" / "arm_summary.csv", encoding="utf-8-sig")
    checks["three_way_gmf"] = {
        "arms": sorted(gmf_table["arm"].tolist()),
        "all_coordinate_rows": bool((gmf_table["coordinate_rows"] == 100).all()),
        "all_step_rows": bool((gmf_table["step_count"] == 99).all()),
        "winner": gmf_summary["assessment"]["winner"],
        "v42_y_step_std_px": gmf_summary["arms"]["V42 E120"]["y_step_std_px"],
        "r109_y_step_std_px": gmf_summary["arms"]["R109 E48"]["y_step_std_px"],
    }
    if (
        checks["three_way_gmf"]["arms"] != ["R109 E48", "Raw", "V42 E120"]
        or not checks["three_way_gmf"]["all_coordinate_rows"]
        or not checks["three_way_gmf"]["all_step_rows"]
        or checks["three_way_gmf"]["winner"] != "V42 E120"
    ):
        failures.append("Three-way GMF evidence invalid")

    lsc_summary = json.loads((RESULTS / "lsc_current_top30" / "lsc_current_top30_summary.json").read_text(encoding="utf-8"))
    lsc_validation = json.loads((RESULTS / "lsc_current_top30" / "lsc_validation.json").read_text(encoding="utf-8"))
    lsc_pairs = pd.read_csv(RESULTS / "lsc_current_top30" / "tables" / "four_method_lsc_per_pair_current_top30.csv", encoding="utf-8-sig")
    checks["lsc_current_top30"] = {
        "validation": lsc_validation["status"],
        "rows": len(lsc_pairs),
        "methods": sorted(lsc_pairs["method"].unique().tolist()),
        "determinism_spot_check_max_px": lsc_summary["determinism_spot_check_max_px"],
        "assessment": lsc_summary["assessment"]["result"],
        "all_uncertainty_intervals_include_zero": lsc_validation["all_uncertainty_intervals_include_zero"],
    }
    if (
        lsc_validation["status"] != "pass"
        or len(lsc_pairs) != 480
        or lsc_summary["determinism_spot_check_max_px"] != 0.0
        or not lsc_validation["all_uncertainty_intervals_include_zero"]
    ):
        failures.append("Current-top30 deterministic LSC evidence invalid")

    decision = json.loads((RESULTS / "replacement_decision.json").read_text(encoding="utf-8"))
    policy = json.loads((ROOT / "config" / "replacement_metric_policy_v3_lsc_primary.json").read_text(encoding="utf-8"))
    checks["decision"] = {
        "status": decision["status"],
        "replacement_approved": decision["replacement_approved"],
        "cd_secondary": policy["cd_role"] == "secondary legacy dimensional-compatibility evidence only",
        "external_winner": decision["primary_outcomes"]["external_gmf_displacement"]["winner"],
        "lsc_outcome": decision["primary_outcomes"]["thesis_lsc_displacement"]["outcome"],
        "v42_score_present": checks["v42_gmf"]["score_present"],
    }
    if (
        decision["status"] != "complete"
        or decision["replacement_approved"]
        or not checks["decision"]["cd_secondary"]
        or checks["decision"]["external_winner"] != "V42 E120"
        or checks["decision"]["lsc_outcome"] != "equivalent"
        or not checks["decision"]["v42_score_present"]
    ):
        failures.append("Final ACM/displacement-primary decision is inconsistent")

    result = {
        "status": "pass" if not failures else "fail",
        "validated_local": datetime.now().astimezone().isoformat(),
        "failures": failures,
        "checks": checks,
        "independent_spot_checks": {"r109_120_step_command_mae_nm": independent_r109_mae},
    }
    (RESULTS / "final_validation.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())

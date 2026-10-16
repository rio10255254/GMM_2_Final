"""Self-consistency checks for the read-only R114C E024 causal diagnosis."""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "results" / "split_profile_repair" / "E024_deep_failure_diagnosis"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def all_finite(value: Any) -> bool:
    if value is None or isinstance(value, (str, bool)):
        return True
    if isinstance(value, (int, float)):
        return math.isfinite(float(value))
    if isinstance(value, list):
        return all(all_finite(item) for item in value)
    if isinstance(value, dict):
        return all(all_finite(item) for item in value.values())
    return False


def main() -> None:
    diagnosis_path = OUT / "diagnosis.json"
    diagnosis = json.loads(diagnosis_path.read_text(encoding="utf-8"))
    audits = diagnosis["audits"]
    b = audits["R114B_E24"]
    c = audits["R114C_E24"]
    bo = b["overall"]
    co = c["overall"]

    checks: dict[str, bool] = {
        "json_is_finite": all_finite(diagnosis),
        "read_only_flag": diagnosis.get("read_only_forensics") is True,
        "fixed_128_scene_contract": diagnosis["fixed_validation_contract"]["limit"] == 128,
        "both_checkpoints_are_e24_scratch": all(
            audit["checkpoint"]["epoch"] == 24
            and audit["checkpoint"]["stage"] == "profile"
            and audit["checkpoint"]["scratch"] is True
            for audit in audits.values()
        ),
        "checkpoint_hashes_match": all(
            sha256(Path(audit["checkpoint"]["path"])) == audit["checkpoint"]["sha256"]
            for audit in audits.values()
        ),
        "runtime_replay_matches_stored_b": abs(
            bo["runtime_actual_mae"] - b["stored_validation"]["mae"]
        ) < 1.0e-6,
        "runtime_replay_matches_stored_c": abs(
            co["runtime_actual_mae"] - c["stored_validation"]["mae"]
        ) < 1.0e-6,
        "stored_total_delta_replayed_b": abs(
            bo["total_reconstruction_delta_abs_gray_global"] / 255.0
            - b["stored_validation"]["delta_abs"]
        ) < 1.0e-6,
        "stored_total_delta_replayed_c": abs(
            co["total_reconstruction_delta_abs_gray_global"] / 255.0
            - c["stored_validation"]["delta_abs"]
        ) < 1.0e-6,
        "scale_curves_have_41_points": all(
            len(audit["scale_sweep_0_to_1"]["curve"]) == 41 for audit in audits.values()
        ),
        "scale_zero_matches_base": all(
            abs(audit["scale_sweep_0_to_1"]["curve"][0]["global_mae"] - audit["overall"]["base_mae"])
            < 1.0e-6
            for audit in audits.values()
        ),
        "scale_one_matches_runtime": all(
            abs(audit["scale_sweep_0_to_1"]["curve"][-1]["global_mae"] - audit["overall"]["runtime_actual_mae"])
            < 1.0e-6
            for audit in audits.values()
        ),
        "c_best_global_scale_is_zero": c["scale_sweep_0_to_1"]["best_global"]["alpha"] == 0.0,
        "c_best_band_scale_is_zero": c["scale_sweep_0_to_1"]["best_true_band"]["alpha"] == 0.0,
        "c_runtime_direction_below_half": co["runtime_direction_agreement_weighted"] < 0.5,
        "c_runtime_is_net_harmful": co["runtime_actual_mae"] > co["base_mae"],
        "c_old_triple_gate_removes_most_regression": (
            diagnosis["comparison"]["r114c_gate_causal_decomposition"]
            ["fraction_of_current_regression_removed_by_old_triple_gate"]
            > 0.75
        ),
        "c_target_visibility_makes_learned_action_positive": (
            co["oracle_visibility_learned_pred_coordinate_mae"] < co["base_mae"]
        ),
        "c_target_parameters_and_visibility_improve": (
            co["oracle_parameters_visibility_pred_coordinate_mae"] < co["base_mae"]
        ),
        "c_true_coordinate_oracle_improves_further": (
            co["oracle_coordinate_parameters_visibility_mae"]
            < co["oracle_parameters_visibility_pred_coordinate_mae"]
        ),
        "c_optimal_learned_visibility_has_large_headroom": (
            co["optimal_visibility_learned_pred_coordinate_mae"]
            < co["oracle_visibility_learned_pred_coordinate_mae"]
        ),
        "predicted_profile_band_is_global_not_local": co["predicted_band_support_fraction"] > 0.999,
        "visibility_supervision_is_global_not_local": co["visibility_supervision_support_fraction"] > 0.999,
        "counterfactual_positive_pixels_are_sparse": co["target_visibility_positive_fraction"] < 0.15,
        "c_contrast_correlation_improved_over_b": (
            c["correlations_and_calibration"]["signed_contrast"]["spearman"]
            > b["correlations_and_calibration"]["signed_contrast"]["spearman"]
        ),
        "c_width_correlation_improved_over_b": (
            c["correlations_and_calibration"]["profile_width"]["spearman"]
            > b["correlations_and_calibration"]["profile_width"]["spearman"]
        ),
        "c_visibility_calibration_improved_over_b": (
            c["correlations_and_calibration"]["profile_visibility"]["weighted_mae"]
            < b["correlations_and_calibration"]["profile_visibility"]["weighted_mae"]
        ),
        "scene_csv_exists_and_nonempty": (OUT / "scene_metrics.csv").stat().st_size > 1000,
    }

    source_hash_checks: dict[str, bool] = {}
    for relative, expected in diagnosis["source_hashes_at_analysis"].items():
        path = ROOT / relative
        source_hash_checks[relative] = path.exists() and sha256(path) == expected
    checks["analysis_sources_unchanged"] = all(source_hash_checks.values())

    report = {
        "schema_version": 1,
        "diagnosis_sha256": sha256(diagnosis_path),
        "checks": checks,
        "source_hash_checks": source_hash_checks,
        "passed": sum(checks.values()),
        "total": len(checks),
        "all_passed": all(checks.values()),
    }
    temporary = (OUT / "validation_report.json.tmp")
    temporary.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    temporary.replace(OUT / "validation_report.json")
    print(json.dumps(report, indent=2, ensure_ascii=False))
    if not report["all_passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()

"""Independent consistency checks for the E024 profile-failure diagnosis."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "results" / "split_profile_probe" / "E024_failure_diagnosis"
RUN = ROOT / "runs" / "r114b_split_profile_probe_scratch_20260830"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    diagnosis = json.loads((OUT / "diagnosis.json").read_text(encoding="utf-8"))
    training = json.loads((RUN / "validation" / "epoch_024.json").read_text(encoding="utf-8"))["summary"]
    overall = diagnosis["overall"]
    checkpoint = Path(diagnosis["checkpoint"]["path"])
    checks = {
        "checkpoint_hash_matches": sha256(checkpoint) == diagnosis["checkpoint"]["sha256"],
        "exact_128_scene_population": overall["scenes"] == training["scenes"] == 128,
        "mae_matches_training_validation": abs(overall["output_mae"] - training["mae"]) < 2.0e-7,
        "base_mae_matches_training_validation": abs(overall["base_mae"] - training["base_mae"]) < 2.0e-7,
        "profile_regression_reproduced": overall["output_mae"] > overall["base_mae"],
        "actual_direction_below_chance": overall["direction_sign_agreement_action"] < 0.5,
        "same_magnitude_oracle_direction_is_helpful": overall["oracle_same_magnitude_gain_band"] > 0.0,
        "oracle_clipped_direction_is_helpful": overall["oracle_clipped_gain_band"] > 0.0,
        "target_parameters_and_true_sdf_beat_base": overall["target_params_true_sdf_mae"] < overall["base_mae"],
        "target_parameters_with_predicted_sdf_do_not_beat_base": overall["target_params_pred_sdf_mae"] > overall["base_mae"],
        "visibility_is_over_open": overall["visibility_pred_band"] > overall["visibility_target_band"],
        "identity_gate_is_near_zero": diagnosis["by_role"]["identity"]["profile_gate_band_mean"] < 0.001,
        "scene_table_exists": (OUT / "scene_metrics.csv").is_file(),
        "root_causes_ranked": len(diagnosis["root_cause_ranking"]) == 4,
    }
    result = {
        "passed": sum(bool(value) for value in checks.values()),
        "total": len(checks),
        "all_passed": all(checks.values()),
        "checks": checks,
    }
    (OUT / "validation_report.json").write_text(
        json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(json.dumps(result, indent=2, ensure_ascii=False))
    if not result["all_passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()

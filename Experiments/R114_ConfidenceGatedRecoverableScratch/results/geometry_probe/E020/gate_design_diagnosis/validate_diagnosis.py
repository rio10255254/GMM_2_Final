"""Validate the gate diagnosis artifacts and record read-only source hashes."""
from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

import cv2


ROOT = Path(r"D:\GMM_2_Final\Experiments\R114_ConfidenceGatedRecoverableScratch")
HERE = ROOT / "results" / "geometry_probe" / "E020" / "gate_design_diagnosis"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def main() -> int:
    summary = json.loads((HERE / "diagnosis_summary.json").read_text(encoding="utf-8"))
    contract = json.loads((HERE / "implementation_contract.json").read_text(encoding="utf-8"))
    samples = read_csv(HERE / "sample_statistics.csv")
    families = read_csv(HERE / "family_statistics.csv")
    by_family = {row["family"]: row for row in families}
    separation = summary["separation"]
    effect = separation["kruskal_shift_reliability_p25"]
    auc = separation["safe_halo_uneven_vs_unsafe_lowcontrast_fade_auc"]
    correlations = summary["correlations"]

    checks = {
        "summary_complete": summary["status"] == "complete",
        "exactly_100_frozen_records": len(samples) == 100 == int(summary["records"]),
        "five_families_present": set(by_family) == set(summary["families"]) and len(families) == 5,
        "all_samples_have_points": all(int(row["points"]) > 0 for row in samples),
        "family_effect_is_material": float(effect["epsilon_squared"]) > 0.30,
        "family_difference_is_significant": float(effect["p_value"]) < 1.0e-6,
        "safe_vs_unsafe_auc_is_useful": float(auc["shift_reliability_p25"]) >= 0.80,
        "suppression_auc_is_useful": float(auc["negative_shift_suppressed_fraction"]) >= 0.80,
        "low_contrast_shift_below_halo": float(by_family["low_contrast"]["shift_reliability_median_median"]) < float(by_family["asymmetric_blur_halo"]["shift_reliability_median_median"]),
        "low_contrast_shift_below_uneven": float(by_family["low_contrast"]["shift_reliability_median_median"]) < float(by_family["uneven_illumination"]["shift_reliability_median_median"]),
        "uneven_preserved_above_fade": float(by_family["uneven_illumination"]["shift_reliability_median_median"]) > float(by_family["boundary_fade"]["shift_reliability_median_median"]),
        "low_contrast_suppression_exceeds_uneven": float(by_family["low_contrast"]["shift_suppressed_fraction_median"]) > float(by_family["uneven_illumination"]["shift_suppressed_fraction_median"]) + 0.40,
        "width_and_shift_not_identical": abs(float(correlations["width_reliability_vs_shift_reliability"]["rho"])) < 0.90,
        "current_shift_fails_oracle_alignment": abs(float(correlations["current_normal_shift_vs_normal_shift_target"]["rho"])) < 0.05,
        "split_controller_outputs_declared": set(contract["controller_outputs_add"]) == {"width_reliability", "shift_reliability"},
        "split_renderer_gates_declared": {"width_gate", "shift_gate"}.issubset(contract["renderer_contract"]),
        "new_scratch_required": "continue E20 weights" in contract["prohibited"],
        "no_model_or_training_output_written": all(
            path.is_relative_to(HERE) for path in HERE.rglob("*") if path.is_file()
        ),
    }

    panel = cv2.imread(str(HERE / "representative_target_maps.png"), cv2.IMREAD_UNCHANGED)
    checks["representative_panel_readable"] = panel is not None and panel.shape[0] >= 1000 and panel.shape[1] >= 1500
    required = {
        "analyze_gate_targets.py",
        "sample_statistics.csv",
        "family_statistics.csv",
        "diagnosis_summary.json",
        "representative_target_maps.png",
        "DIAGNOSIS_AND_EXECUTABLE_DESIGN_ZH.md",
        "implementation_contract.json",
        "validate_diagnosis.py",
    }
    checks["required_artifacts_present"] = all((HERE / name).is_file() for name in required)

    source_files = [
        ROOT / "model" / "full_model.py",
        ROOT / "model" / "r114_model.py",
        ROOT / "training" / "targets.py",
        ROOT / "training" / "losses.py",
        ROOT / "training" / "train.py",
        ROOT / "results" / "geometry_probe" / "E020" / "locked_acm" / "analysis_summary.json",
        ROOT / "results" / "geometry_probe" / "E020" / "r74_interventions" / "analysis_summary.json",
    ]
    validation = {
        "status": "passed" if all(checks.values()) else "failed",
        "scope": "gate_design_diagnosis_only_no_training_no_model_changes",
        "checks": checks,
        "check_count": len(checks),
        "passed_count": sum(bool(value) for value in checks.values()),
        "source_file_sha256": {str(path): sha256(path) for path in source_files},
        "output_file_sha256": {
            name: sha256(HERE / name)
            for name in sorted(required)
            if (HERE / name).is_file()
        },
    }
    (HERE / "validation.json").write_text(
        json.dumps(validation, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(validation, ensure_ascii=False, indent=2))
    return 0 if validation["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())

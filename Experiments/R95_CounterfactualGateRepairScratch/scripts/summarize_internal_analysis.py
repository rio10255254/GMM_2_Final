"""Independent QA and compact summary for R95 internal-analysis artifacts."""
from __future__ import annotations

import json
import math
from pathlib import Path
import statistics


ROOT = Path(__file__).resolve().parents[1]
AUDIT = ROOT / "reports" / "model_internal_analysis_epoch40" / "internal_causal_audit.json"
INTERVENTIONS = ROOT / "reports" / "model_internal_analysis_epoch40" / "branch_interventions.json"
OUTPUT = ROOT / "reports" / "model_internal_analysis_epoch40" / "verified_summary.json"
BRANCHES = ("radiometry", "nuisance", "local_contrast", "boundary", "texture")


def mean(rows, getter):
    return statistics.mean(getter(row) for row in rows)


def main() -> int:
    audit = json.loads(AUDIT.read_text(encoding="utf-8"))
    interventions = json.loads(INTERVENTIONS.read_text(encoding="utf-8"))
    epoch = audit["epochs"]["40"]
    real = list(epoch["real"].values())
    synthetic = list(epoch["synthetic"].values())
    recomposition_errors = []
    for result in real + synthetic:
        branch_sum_abs = result["sum_branch_abs_mean_gray"]
        if not math.isfinite(branch_sum_abs) or branch_sum_abs < 0:
            raise RuntimeError("Invalid branch magnitude")
        if result["output_clamp_fraction"] != 0.0:
            raise RuntimeError("Unexpected output clamp invalidates simple intervention interpretation")
        recomposition_errors.append(abs(
            result["effective_abs_mean_gray"] - result["output_change_gray"]["abs_mean"]
        ))
    if max(recomposition_errors) > 1e-9:
        raise RuntimeError("Output change summary is internally inconsistent")

    branch_summary = {}
    for branch in BRANCHES:
        branch_summary[branch] = {
            "real_ungated_abs_gray": mean(real, lambda row: row["branches"][branch]["ungated_gray"]["abs_mean"]),
            "real_gated_abs_gray": mean(real, lambda row: row["branches"][branch]["gated_gray"]["abs_mean"]),
            "synthetic_ungated_abs_gray": mean(synthetic, lambda row: row["branches"][branch]["ungated_gray"]["abs_mean"]),
            "synthetic_gated_abs_gray": mean(synthetic, lambda row: row["branches"][branch]["gated_gray"]["abs_mean"]),
            "synthetic_gate_ratio": mean(synthetic, lambda row: row["branches"][branch]["effective_gate_ratio"]),
        }

    roles = interventions["rows"]
    deficient = [row for row in roles if row["role"] != "clear_detail_guard"]
    intervention_summary = {}
    for branch in BRANCHES:
        intervention_summary[branch] = {
            key: mean(deficient, lambda row, key=key: row["branches"][branch][key]["improvement_vs_current_gray"])
            for key in ("removed", "double_current", "fully_open", "oracle_scalar_sweep")
        }
        intervention_summary[branch]["best_scales_by_role"] = {
            row["role"]: row["branches"][branch]["oracle_scalar_sweep"]["best_scale"]
            for row in roles
        }
    clear = next(row for row in roles if row["role"] == "clear_detail_guard")
    payload = {
        "validation": {
            "status": "ready_with_caveat",
            "device": "cpu",
            "checkpoint_epoch": 40,
            "real_samples": len(real),
            "synthetic_roles": len(synthetic),
            "no_output_clamping_in_samples": True,
            "max_summary_recomposition_error": max(recomposition_errors),
            "caveat": "Real images have no direct ground truth; accuracy claims use synthetic validation roles only.",
        },
        "overall": {
            "real_output_abs_gray": mean(real, lambda row: row["output_change_gray"]["abs_mean"]),
            "synthetic_output_abs_gray": mean(synthetic, lambda row: row["output_change_gray"]["abs_mean"]),
            "defect_role_raw_mae_gray": mean(deficient, lambda row: row["raw_mae_gray"]),
            "defect_role_model_mae_gray": mean(deficient, lambda row: row["model_mae_gray"]),
            "defect_role_improvement_gray": mean(deficient, lambda row: row["model_improvement_gray"]),
            "clear_raw_mae_gray": clear["raw_mae_gray"],
            "clear_model_mae_gray": clear["model_mae_gray"],
        },
        "branches": branch_summary,
        "interventions_on_defect_roles": intervention_summary,
    }
    temporary = OUTPUT.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    temporary.replace(OUTPUT)
    print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

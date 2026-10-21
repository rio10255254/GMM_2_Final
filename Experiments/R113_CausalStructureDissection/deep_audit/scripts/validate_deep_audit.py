"""Independent integrity and calculation checks for the R113 deep audit."""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import nbformat
import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "results"


def main() -> int:
    checks = {}
    profile = pd.read_csv(RESULTS / "data_profile" / "per_record_profile.csv")
    checks["profile_population"] = len(profile) == 5512 and profile.scene_index.nunique() == 5512
    checks["split_population"] = profile.split.value_counts().to_dict() == {"train": 5000, "validation": 512}
    checks["structural_antialias"] = bool((profile.loc[~profile.role.eq("flat_negative"), "antialias_fraction"] > 0).all())
    duplicates = pd.read_csv(RESULTS / "data_profile" / "duplicate_groups.csv")
    checks["no_exact_combined_cross_split_duplicate"] = not bool(((duplicates.key_type == "combined_hash") & duplicates.cross_split.astype(bool)).any())

    observations = pd.read_csv(RESULTS / "degradation_recoverability" / "per_observation_metrics.csv")
    checks["observation_population"] = len(observations) == 33072 and not observations.duplicated(["scene_index", "epoch"]).any()
    checks["observation_metrics_finite"] = bool(np.isfinite(observations.select_dtypes(include=[np.number]).to_numpy()).all())
    recoverability = json.loads((RESULTS / "degradation_recoverability" / "analysis_summary.json").read_text(encoding="utf-8"))
    checks["effective_identity_recomputed"] = abs(recoverability["effective_training_composition"]["effective_clear_identity_fraction_after_flatten"] - (0.5 + 0.5 * 515 / 5512)) < 1e-12

    boundary_weight = pd.read_csv(RESULTS / "training_contract" / "family_effective_boundary_weight.csv")
    checks["boundary_weight_sums"] = abs(boundary_weight.edge_weight_share.sum() - 1) < 1e-10 and abs(boundary_weight.record_share.sum() - 1) < 1e-10
    dense = boundary_weight.set_index("family").loc["dense_array"]
    checks["dense_share_recomputed"] = 0.67 < dense.edge_weight_share < 0.69

    internal = pd.read_csv(RESULTS / "model_internals" / "checkpoint_internal_dynamics.csv")
    checks["checkpoint_population"] = len(internal) == 12 and internal.epoch.tolist() == list(range(4, 49, 4))
    checks["boundary_constant_all_checkpoints"] = float(internal.boundary_spatial_std.max()) < 1e-4 and float(internal.boundary_auc.max()) < .51
    model_summary = json.loads((RESULTS / "model_internals" / "analysis_summary.json").read_text(encoding="utf-8"))
    checks["boundary_zero_erf"] = model_summary["effective_receptive_field"]["fields"]["boundary"]["gradient_total"] == 0

    gradient = pd.read_csv(RESULTS / "loss_gradients" / "pooled_loss_gradient_summary.csv")
    cosine = pd.read_csv(RESULTS / "loss_gradients" / "pooled_pairwise_gradient_cosines.csv")
    strata = pd.read_csv(RESULTS / "loss_gradients" / "stratum_gradient_norms.csv")
    checks["gradient_populations"] = len(gradient) == 65 and len(cosine) == 234 and len(strata) == 140
    checks["gradient_numeric_finite"] = bool(np.isfinite(gradient.select_dtypes(include=[np.number]).to_numpy()).all() and np.isfinite(cosine.select_dtypes(include=[np.number]).to_numpy()).all())
    clear = pd.read_csv(RESULTS / "loss_gradients" / "clear_degraded_gradient_conflict.csv")
    shift_total = clear.loc[(clear.parameter_group == "shift_head") & (clear.loss == "expected_sum_of_six_base_losses")].iloc[0]
    checks["clear_shift_ratio_recomputed"] = abs(shift_total.clear_over_degraded_norm - shift_total.clear_gradient_norm / shift_total.degraded_gradient_norm) < 1e-9

    detect = json.loads((RESULTS / "boundary_detectability" / "analysis_summary.json").read_text(encoding="utf-8"))
    checks["cue_probe_scene_disjoint"] = detect["overall"]["test_pixels"] > 100000 and detect["overall"]["test_auc"] > .85
    checks["cue_probe_exceeds_dead_head"] = detect["overall"]["test_auc"] - detect["current_r109_boundary_auc_reference"] > .35

    domain = pd.read_csv(RESULTS / "domain_gap" / "per_patch_metrics.csv")
    checks["domain_rows"] = len(domain) == 1830 and domain.domain.nunique() == 8
    checks["domain_metrics_finite"] = bool(np.isfinite(domain.select_dtypes(include=[np.number]).to_numpy()).all())

    notebook = nbformat.read(ROOT / "R113_DEEP_AUDIT.ipynb", as_version=4)
    code_cells = [cell for cell in notebook.cells if cell.cell_type == "code"]
    errors = [output for cell in code_cells for output in cell.get("outputs", []) if output.get("output_type") == "error"]
    checks["notebook_executed"] = len(code_cells) == 8 and all(cell.get("execution_count") is not None for cell in code_cells) and not errors

    checks = {name: bool(passed) for name, passed in checks.items()}
    failures = [name for name, passed in checks.items() if not passed]
    result = {
        "status": "pass" if not failures else "fail",
        "validated_local": datetime.now().astimezone().isoformat(),
        "checks": checks,
        "failures": failures,
        "scope": "full training-image, information, model-internal, gradient, and domain-gap audit",
    }
    (RESULTS / "final_validation.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())

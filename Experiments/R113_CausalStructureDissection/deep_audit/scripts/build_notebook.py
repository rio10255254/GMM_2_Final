"""Build the executable companion notebook for the R113 deep audit."""
from __future__ import annotations

import json
from pathlib import Path

import nbformat as nbf


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "R113_DEEP_AUDIT.ipynb"


def main() -> int:
    decision = json.loads((ROOT / "results" / "FINAL_DEEP_AUDIT.json").read_text(encoding="utf-8"))
    notebook = nbf.v4.new_notebook()
    notebook["metadata"]["kernelspec"] = {"display_name": "Python 3", "language": "python", "name": "python3"}
    notebook["cells"] = [
        nbf.v4.new_markdown_cell(
            "# R113 deep model and training-image audit\n\n## tl;dr\n\n"
            "- The main bottleneck is not model size or patch size.\n"
            "- The boundary/necessity controller is dead, despite strong boundary information in the fixed input cues.\n"
            "- Dense arrays dominate boundary-weighted training; more than half of flattened observations are clear/identity-like.\n"
            "- Width and shift receive strongly conflicting gradients, while some mixed-hard labels are not identifiable from one image.\n"
            "- Synthetic texture/noise does not match real 5x/20x/50x microscopy.\n"
            "- The next authorized action is a small geometry/confidence-head microprobe, not a full model run."
        ),
        nbf.v4.new_markdown_cell(
            "## Context & Methods\n\n"
            "The audit reads all 5,512 target/mask/SDF triplets, recreates six deterministic degradations per record, traces twelve checkpoints, measures loss gradients, and compares held-out microscopy texture.\n\n"
            "### Key Assumptions\n\n"
            "- Exact combined hashes control split leakage; normalized-shape hashes are only a collision screen.\n"
            "- Threshold recoverability is favorable because it uses true polarity and midpoint.\n"
            "- Gradient norms diagnose local optimization pressure, not exact AdamW attribution over all training steps."
        ),
        nbf.v4.new_code_cell(
            "from pathlib import Path\nimport json, pandas as pd\n"
            f"ROOT = Path(r'{ROOT}')\n"
            "def load(rel): return json.loads((ROOT / rel).read_text(encoding='utf-8'))\n"
            "decision = load('results/FINAL_DEEP_AUDIT.json')\nvalidation = load('results/final_validation.json')\nvalidation"
        ),
        nbf.v4.new_markdown_cell("## Data\n\nFull-record quality and effective boundary weighting."),
        nbf.v4.new_code_cell(
            "profile = load('results/data_profile/analysis_summary.json')\n"
            "boundary_weight = pd.read_csv(ROOT / 'results/training_contract/family_effective_boundary_weight.csv')\n"
            "boundary_weight.sort_values('edge_weight_share', ascending=False)[['family','records','record_share','edge_weight_share','perimeter_share']].head(8)"
        ),
        nbf.v4.new_code_cell(
            "recoverability = pd.DataFrame(load('results/degradation_recoverability/analysis_summary.json')['challenge_summary'])\n"
            "recoverability[['challenge','records','source_threshold_iou_median','boundary_visibility_median','target_aligned_highfrequency_gain_median','unexplained_boundary_highfrequency_rms_median_gray']]"
        ),
        nbf.v4.new_markdown_cell("## Results\n\nInternal dynamics, gradient routing, boundary detectability, and real-domain distance."),
        nbf.v4.new_code_cell(
            "internal = pd.read_csv(ROOT / 'results/model_internals/checkpoint_internal_dynamics.csv')\n"
            "internal[['epoch','boundary_auc','boundary_spatial_std','learned_support_mean','learned_support_dominance_fraction','width_gain_mean','shift_abs_mean_px','renderer_tanh_saturation_fraction']]"
        ),
        nbf.v4.new_code_cell(
            "gradients = pd.read_csv(ROOT / 'results/loss_gradients/pooled_loss_gradient_summary.csv')\n"
            "gradients.sort_values(['parameter_group','effective_gradient_norm'], ascending=[True,False]).groupby('parameter_group').head(5)[['parameter_group','loss','effective_gradient_norm','alignment_with_expected_total']]"
        ),
        nbf.v4.new_code_cell(
            "conflict = pd.read_csv(ROOT / 'results/loss_gradients/clear_degraded_gradient_conflict.csv')\n"
            "conflict[conflict.loss == 'expected_sum_of_six_base_losses'][['parameter_group','clear_over_degraded_norm','clear_vs_degraded_cosine']]"
        ),
        nbf.v4.new_code_cell(
            "detect = load('results/boundary_detectability/analysis_summary.json')\n"
            "{'current_R109_boundary_AUC': detect['current_r109_boundary_auc_reference'], 'fixed_cue_logistic_test_AUC': detect['overall']['test_auc'], 'dense_array_median_AUC': next(row['auc_median'] for row in detect['family_results'] if row['family']=='dense_array')}"
        ),
        nbf.v4.new_code_cell(
            "domain = load('results/domain_gap/analysis_summary.json')['distance_analysis']['real_domains']\n"
            "pd.DataFrame(domain).T[['patches','distance_over_synthetic_self_median']]"
        ),
        nbf.v4.new_markdown_cell(
            "## Takeaways\n\n"
            "1. Rebalance by per-scene boundary mass and isolate dense-array quotas.\n"
            "2. Remove automatic clear pairing from every record; schedule smaller dedicated identity batches.\n"
            "3. Replace constant-prone boundary BCE/Dice with joint SDF, normal, confidence, and recoverability supervision.\n"
            "4. Keep the controller trainable with the renderer and remove mandatory raw-gradient support floors.\n"
            "5. Train width/shift from spatial geometry targets, then train bounded detail separately only where information is recoverable.\n"
            "6. Use correlated multiscale microscopy-like texture/noise; do not use real SEM as labels.\n"
            "7. Run the small controller microprobe before any full new model."
        ),
    ]
    OUTPUT.write_text(nbf.writes(notebook), encoding="utf-8")
    print(OUTPUT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Build the reproducible R113 companion notebook after finalization."""
from __future__ import annotations

import json
from pathlib import Path

import nbformat as nbf


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "R113_CAUSAL_DISSECTION.ipynb"


def main() -> int:
    decision = json.loads((ROOT / "results" / "FINAL_DECISION.json").read_text(encoding="utf-8"))
    supervised = decision["key_findings"]["detail_microprobes"]["supervised"]
    assessment = supervised["assessment"]
    notebook = nbf.v4.new_notebook()
    notebook["metadata"]["kernelspec"] = {"display_name": "Python 3", "language": "python", "name": "python3"}
    notebook["cells"] = [
        nbf.v4.new_markdown_cell(
            "# R113 causal structure dissection\n\n"
            "## tl;dr\n\n"
            "- V42 is a targeted continuation of R61 whose dominant new behavior is the final Raw anchor.\n"
            "- R109's learned support collapsed and its necessity map is hard-coded, while difficult thin structures exceed the current renderer.\n"
            "- Fixed smoothing improves real SEM contours but harms broad synthetic shapes and line sharpness, so coherence must be conditional and boundary-directed.\n"
            f"- Final bounded-detail microprobe assessment: **{assessment}**.\n"
            "- No R113 checkpoint is promoted; the output is a validated next-architecture design."
        ),
        nbf.v4.new_markdown_cell(
            "## Context & Methods\n\n"
            "This notebook is a compact, executable index of the machine-readable R113 results. "
            "All source checkpoints were frozen by SHA-256. Synthetic truth, SEM ACM, deterministic LSC, real-image safety, line behavior and tile parity control the scientific decision; GMF is compatibility only.\n\n"
            "### Key Assumptions\n\n"
            "- SEM pillars are repeated across exposure, so the independent unit is the physical pillar.\n"
            "- Commanded motion is nominal, not independent stage truth.\n"
            "- Oracle controls see truth and are capacity ceilings, not deployable outputs."
        ),
        nbf.v4.new_code_cell(
            "from pathlib import Path\n"
            "import json, pandas as pd\n"
            f"ROOT = Path(r'{ROOT}')\n"
            "def load(rel): return json.loads((ROOT / rel).read_text(encoding='utf-8'))\n"
            "final = load('results/FINAL_DECISION.json')\n"
            "validation = load('results/final_validation.json')\n"
            "validation"
        ),
        nbf.v4.new_markdown_cell("## Data\n\nThe following cells expose the corrected measurement, physical intervention and formal microprobe tables used in the decision."),
        nbf.v4.new_code_cell(
            "measurement = pd.read_csv(ROOT / 'results/measurement_qa/corrected_arm_summary.csv')\n"
            "measurement[['arm','ring_center_radius_std_px','ring_width_std_px','annulus_high_frequency_rms_median_gray']]"
        ),
        nbf.v4.new_code_cell(
            "sem = pd.read_csv(ROOT / 'results/physical_validation/sem_acm_contract/results/acm_sem/tables/intervention_method_summary.csv')\n"
            "sem.sort_values('mean_boundary_distance_pitch_pct')"
        ),
        nbf.v4.new_code_cell(
            "r73 = pd.read_csv(ROOT / 'results/physical_validation/synthetic_acm/R73_contract/results/tables/intervention_method_summary.csv')\n"
            "r74 = pd.read_csv(ROOT / 'results/physical_validation/synthetic_acm/R74_contract/results/tables/intervention_method_summary.csv')\n"
            "pd.concat({'R73': r73.set_index('method'), 'R74': r74.set_index('method')})[['mean_boundary_distance_px','iou']]"
        ),
        nbf.v4.new_markdown_cell("## Results\n\nThe exact causal findings and next-design decision are loaded directly from the finalized JSON artifact."),
        nbf.v4.new_code_cell(
            "structure = load('results/structure/structure_findings.json')\n"
            "{\n"
            " 'R61_V42_exact_shared_fraction': structure['architecture_relation']['exact_shared_fraction'],\n"
            " 'R109_learned_support_mean_range': structure['r109_causal_decomposition']['learned_support_statistics']['mean_range'],\n"
            " 'R109_hardcoded_necessity': structure['r109_causal_decomposition']['hardcoded_necessity'],\n"
            "}"
        ),
        nbf.v4.new_code_cell(
            "lsc = load('results/physical_validation/lsc_interventions/analysis_summary.json')\n"
            "pd.DataFrame(lsc['headline']).T"
        ),
        nbf.v4.new_code_cell(
            "detail = load('next_probe/results/supervised_formal_comparison.json')\n"
            "pd.DataFrame(detail['summaries']).T[['assd_median_px','assd_p95_px','assd_worst_px','iou_worst','high_frequency_rmse_mean_gray','detail_abs_mean_gray']]"
        ),
        nbf.v4.new_markdown_cell(
            "## Takeaways\n\n"
            "1. Keep the local single-image width/shift geometry path.\n"
            "2. Replace the collapsed support and hard-coded necessity with a gate that can activate and veto correction.\n"
            "3. Enforce along-boundary coherence conditionally; do not apply fixed isotropic smoothing.\n"
            "4. Use a bounded zero-local-mean detail branch only with explicit staged supervision.\n"
            "5. The next full run must start from scratch and repeat every physical validation before GMF compatibility."
        ),
    ]
    OUTPUT.write_text(nbf.writes(notebook), encoding="utf-8")
    print(OUTPUT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

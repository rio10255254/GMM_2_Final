"""Create the reproducible, reader-facing GMF analysis notebook."""
from __future__ import annotations

from pathlib import Path

import nbformat as nbf


PACKAGE = Path(__file__).resolve().parents[1]
OUTPUT = PACKAGE / "gmf_analysis"
NOTEBOOK = OUTPUT / "R109_external_GMF_analysis.ipynb"
ANALYZER = PACKAGE / "_tools" / "analyze_gmf_scores.py"


def code(source: str):
    return nbf.v4.new_code_cell(source.strip())


def markdown(source: str):
    return nbf.v4.new_markdown_cell(source.strip())


def main() -> int:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    notebook = nbf.v4.new_notebook()
    notebook["metadata"]["kernelspec"] = {
        "display_name": "Python 3",
        "language": "python",
        "name": "python3",
    }
    notebook["metadata"]["language_info"] = {"name": "python", "version": "3"}
    notebook["cells"] = [
        markdown(
            """
# R109 E48 external-GMF displacement analysis

## tl;dr

This notebook compares the same 99 measurable Y-direction intervals in Raw and
R109 E48, checks the files and frame alignment first, and then tests whether the
stability improvement remains visible against prior GMF reruns of pixel-identical
Raw images.
"""
        ),
        code(
            f"""
from pathlib import Path
from IPython.display import Markdown, Image, display
import contextlib, importlib.util, io, json
import pandas as pd

package = Path(r"{PACKAGE}")
analysis_dir = package / "gmf_analysis"
analyzer_path = Path(r"{ANALYZER}")
spec = importlib.util.spec_from_file_location("r109_gmf_analysis", analyzer_path)
analyzer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(analyzer)
with contextlib.redirect_stdout(io.StringIO()):
    analyzer.main()
summary = json.loads((analysis_dir / "analysis_summary.json").read_text(encoding="utf-8"))
raw = summary["current_raw"]
model = summary["r109_e48"]
change = summary["comparison_vs_current_raw"]
display(Markdown(
    f"**Observed result:** R109 reduced Y-step standard deviation by "
    f"{{change['y_step_std_reduction_pct']:.1f}}%, Y-step mean absolute error by "
    f"{{change['y_error_mae_reduction_pct']:.1f}}%, and cross-axis standard deviation by "
    f"{{change['x_step_std_reduction_pct']:.1f}}%. Wrong-direction intervals fell from "
    f"{{raw['wrong_direction_steps']}} to {{model['wrong_direction_steps']}}. "
    f"The result is a strong relative stability improvement, but it is not yet an absolute metrology pass."
))
"""
        ),
        markdown(
            """
## Context & Methods

- Source: external `GMF_score.txt` files returned for the prepared Raw and R109 E48 folders.
- Grain: one coordinate per reported frame; 100 coordinates yield 99 consecutive steps.
- `frame_0000.bmp` is the external tool's reference and is absent from both score files.
- The nominal Y step is -8 px, inherited from the established package convention.
- Pixel values are not converted into a formal micrometre claim because this package does not contain a sealed physical calibration.
- Historical Raw and the historical R104 negative control are included only to measure GMF rerun variability; R104 is pixel-identical to Raw in this package.
- Uncertainty uses a paired moving-block bootstrap with blocks of five adjacent intervals.
"""
        ),
        markdown("## Data"),
        code(
            """
quality_rows = []
for arm, checks in summary["data_quality"].items():
    quality_rows.append({"arm": arm, **checks})
quality = pd.DataFrame(quality_rows)
display(quality)
display(pd.DataFrame([summary["pixel_relationships"]]))
"""
        ),
        markdown("## Results"),
        code(
            """
metric_rows = [
    ("Y-step mean (px)", raw["y_step_mean_px"], model["y_step_mean_px"]),
    ("Y-step SD (px)", raw["y_step_std_px"], model["y_step_std_px"]),
    ("Y error MAE (px)", raw["y_error_mae_px"], model["y_error_mae_px"]),
    ("Y error median absolute (px)", raw["y_error_median_abs_px"], model["y_error_median_abs_px"]),
    ("Y error P95 absolute (px)", raw["y_error_p95_abs_px"], model["y_error_p95_abs_px"]),
    ("Cross-axis SD (px)", raw["x_step_std_px"], model["x_step_std_px"]),
    ("Detrended Y coordinate SD (px)", raw["detrended_y_coordinate_std_px"], model["detrended_y_coordinate_std_px"]),
    ("Scale SD", raw["scale_std"], model["scale_std"]),
    ("Wrong-direction steps", raw["wrong_direction_steps"], model["wrong_direction_steps"]),
    ("Within 20% of nominal", raw["within_20pct"], model["within_20pct"]),
    ("Median GMF score", raw["score_median"], model["score_median"]),
    ("Endpoint error (px)", raw["endpoint_error_px"], model["endpoint_error_px"]),
]
comparison_table = pd.DataFrame(metric_rows, columns=["metric", "Raw", "R109 E48"])
display(comparison_table.style.format({"Raw": "{:.4f}", "R109 E48": "{:.4f}"}))
"""
        ),
        code(
            """
display(Image(filename=str(analysis_dir / "trajectory_step_score.png")))
"""
        ),
        code(
            """
raw_floor = pd.read_csv(analysis_dir / "raw_equivalent_run_floor.csv", encoding="utf-8-sig")
display(raw_floor[[
    "run", "y_step_std_px", "y_error_mae_px", "x_step_std_px",
    "detrended_y_coordinate_std_px", "score_median"
]])
"""
        ),
        code(
            """
bootstrap_rows = []
for metric in ("y_step_std", "y_error_mae", "x_step_std"):
    item = summary["paired_moving_block_bootstrap"][metric]
    bootstrap_rows.append({"metric": metric, **item})
display(pd.DataFrame(bootstrap_rows).style.format({
    "ratio_p025": "{:.3f}", "ratio_median": "{:.3f}",
    "ratio_p975": "{:.3f}", "fraction_ratio_ge_1": "{:.5f}"
}))
"""
        ),
        code(
            """
outliers = pd.read_csv(analysis_dir / "largest_y_step_errors.csv", encoding="utf-8-sig")
display(outliers[[
    "arm", "outlier_rank", "from_frame", "to_frame", "dx_px", "dy_px",
    "abs_y_error_px", "interval_min_score", "scale_change_abs"
]])
"""
        ),
        code(
            """
score_conditioned = pd.read_csv(analysis_dir / "score_conditioned_summary.csv", encoding="utf-8-sig")
display(score_conditioned[score_conditioned["arm"] == "r109_e48"])
"""
        ),
        markdown("## Takeaways"),
        code(
            """
assessment = summary["assessment"]
confidence = summary["r109_confidence_relationship"]
display(Markdown(
    f'''
1. **Relative stability improved strongly.** R109 is lower than the current Raw run and all three Raw-equivalent GMF runs on Y-step SD, cross-axis SD, and detrended coordinate variation.
2. **The gain is not only an endpoint-average effect.** Median absolute Y error fell from {raw['y_error_median_abs_px']:.2f} px to {model['y_error_median_abs_px']:.2f} px, and the robust Y spread fell from {raw['y_step_robust_sigma_px']:.2f} px to {model['y_step_robust_sigma_px']:.2f} px.
3. **Absolute single-step reliability is still insufficient.** Five intervals move in the wrong Y direction and only {model['within_20pct']*100:.1f}% fall within 20% of nominal.
4. **GMF score is an informative confidence signal for R109.** Its correlation with absolute Y error is {confidence['correlation_abs_y_error_vs_interval_min_score']:.3f}; intervals whose two endpoint scores are both at least 72 contain no wrong-direction steps in this run. This is diagnostic evidence, not a newly imposed production threshold.
5. **Caveat:** GMF itself changes coordinates when rerun on pixel-identical images. Confidence is high that R109 improved this package, but only moderate that the exact amount will repeat without a second locked rerun.
'''
))
"""
        ),
    ]
    nbf.write(notebook, NOTEBOOK)
    print(NOTEBOOK)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Consolidate verified R112 findings and the model-side improvement design."""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "results"
R111 = Path(r"D:\GMM_2_Final\Experiments\R111_R109V42ThesisReplacementQualification\results")


def row(table: pd.DataFrame, key: str, value: str) -> dict[str, object]:
    return table.loc[table[key] == value].iloc[0].to_dict()


def main() -> int:
    external = json.loads((R111 / "external_gmf_three_way" / "analysis_summary.json").read_text(encoding="utf-8"))
    lsc = json.loads((R111 / "lsc_current_top30" / "lsc_current_top30_summary.json").read_text(encoding="utf-8"))
    image = json.loads((RESULTS / "image_mechanisms" / "analysis_summary.json").read_text(encoding="utf-8"))
    component = pd.read_csv(RESULTS / "component_probes" / "component_probe_summary.csv", encoding="utf-8-sig")
    internal = pd.read_csv(RESULTS / "component_probes" / "internal_state_per_frame.csv", encoding="utf-8-sig")
    residual = pd.read_csv(RESULTS / "residual_bands" / "residual_band_summary.csv", encoding="utf-8-sig")
    dynamics = json.loads((RESULTS / "internal_dynamics" / "analysis_summary.json").read_text(encoding="utf-8"))
    counterfactual = pd.read_csv(RESULTS / "counterfactual_stability" / "counterfactual_stability_summary.csv", encoding="utf-8-sig")

    v42_component = row(component, "variant", "V42 full crop")
    v42_no_anchor = row(component, "variant", "V42 no raw anchor")
    r109_component = row(component, "variant", "R109 full crop")
    v42_residual = row(residual, "arm", "V42 E120")
    r109_residual = row(residual, "arm", "R109 E48")
    r109_current = row(counterfactual, "variant", "R109 current")
    r109_hp05 = row(counterfactual, "variant", "R109 high-pass residual gain 0.5")
    predictor_anchor = row(counterfactual, "variant", "R109 predictor high-pass anchor")

    r109_internal = internal.loc[internal["model"] == "R109 E48"]
    v42_internal = internal.loc[internal["model"] == "V42 E120"]
    shift_correlation = dynamics["correlations"]["r109_step_error"]["abs_delta_r109_shift_annulus_abs_p95_px"]

    findings = {
        "status": "complete",
        "generated_local": datetime.now().astimezone().isoformat(),
        "diagnostic_question": "Why does V42 outperform R109 on external GMF, and can model changes close the gap without sacrificing R109 strengths?",
        "verified": {
            "metric_pattern": {
                "external_gmf_v42_y_step_std_px": external["arms"]["V42 E120"]["y_step_std_px"],
                "external_gmf_r109_y_step_std_px": external["arms"]["R109 E48"]["y_step_std_px"],
                "lsc_result": lsc["assessment"]["result"],
                "interpretation": "The gap is external-GMF compatibility, not a general inability to preserve LSC displacement."
            },
            "surrogate_failure": {
                "fixed_template_ranking_valid": image["surrogate_ranking_valid"],
                "surrogate_order": image["surrogate_arm_order_best_to_worst"],
                "external_order": image["external_arm_order_best_to_worst"],
                "consequence": "No counterfactual is promoted as a GMF result without an external run."
            },
            "v42_output_mechanism": {
                "low_frequency_residual_fraction_median": v42_residual["low_fraction_median"],
                "no_raw_anchor_residual_mae_gray": v42_no_anchor["residual_mae_gray"],
                "full_residual_mae_gray": v42_component["residual_mae_gray"],
                "no_raw_anchor_low_frequency_mae_gray": v42_no_anchor["low_frequency_residual_mae_gray"],
                "full_low_frequency_mae_gray": v42_component["low_frequency_residual_mae_gray"],
                "quality_scale_mean": float(v42_internal["quality_scale"].mean()),
                "quality_scale_std": float(v42_internal["quality_scale"].std(ddof=1)),
                "weak_psf_beta_scale": float(v42_internal["weak_psf_beta_scale"].median()),
                "interpretation": "The Raw low-frequency anchor is the dominant final-output constraint; weak PSF is inactive and other V42 ablations are much smaller."
            },
            "r109_output_mechanism": {
                "low_frequency_residual_fraction_median": r109_residual["low_fraction_median"],
                "annulus_low_frequency_std_gray": r109_residual["annulus_low_std_median"],
                "annulus_high_frequency_rms_gray": r109_residual["annulus_high_rms_median"],
                "annulus_width_gain_mean": float(r109_internal["width_gain_mean"].mean()),
                "annulus_normal_shift_abs_mean_px": float(r109_internal["normal_shift_abs_mean_px"].mean()),
                "annulus_normal_shift_abs_p95_px": float(r109_internal["normal_shift_abs_p95_px"].mean()),
                "shift_upper_tail_change_vs_gmf_error_spearman": shift_correlation["spearman"],
                "shift_upper_tail_change_vs_gmf_error_p": shift_correlation["p_value"],
                "interpretation": "R109 rewrites substantially more low-frequency content and uses spatially varying width/shift maps; changes in the shift upper tail are associated with external step error."
            },
            "nontrained_counterfactual": {
                "r109_current_ncc_p05": r109_current["ncc_p05"],
                "highpass_gain_0p5_ncc_p05": r109_hp05["ncc_p05"],
                "r109_current_ring_width_std_px": r109_current["ring_width_std_px"],
                "highpass_gain_0p5_ring_width_std_px": r109_hp05["ring_width_std_px"],
                "predictor_anchor_low_fraction": predictor_anchor["residual_low_fraction_median"],
                "interpretation": "Low-frequency projection improves template appearance stability but degrades ring-width stability; a simple post-processing wrapper is not sufficient."
            }
        },
        "likely_mechanism": [
            "V42 converts a high-capacity prediction into a mostly Raw-low-frequency, bounded-detail image before the external tool sees it.",
            "This canonicalizes the ring profile across frames and suppresses appearance changes that GMF interprets as scale or position changes.",
            "R109 directly exposes per-pixel logistic width correction and normal warp. The geometry is LSC-stable overall, but frame-dependent local control changes can disturb the external template model.",
            "The external-GMF advantage is therefore more likely an output-parameterization effect than a need to copy the full V42 backbone or increase capacity."
        ],
        "unresolved": [
            "The exact contribution of V42 Raw anchor, physics, quality gate, and boundary adapter to external GMF cannot be proven without external scores for those ablations.",
            "The internal fixed-template surrogate failed the arm-ranking gate and cannot select a final counterfactual.",
            "The current associations do not prove that normal shift alone causes all R109 outliers."
        ],
        "model_side_opportunity": {
            "assessment": "high, but targeted",
            "reason": "R109 already matches V42 on deterministic LSC and improves several ACM worst cases; the remaining gap is concentrated in the final image representation seen by GMF.",
            "proposed_architecture": {
                "name": "tile-safe geometric anchor plus coherent detail residual",
                "steps": [
                    "Keep the R109 detector and midpoint/width factorization.",
                    "Generate normal-shift and width-gain fields at lower resolution, then smoothly upsample them so one physical boundary receives a coherent correction instead of independent per-pixel actions.",
                    "Warp Raw with the smoothed normal-shift field to form a geometry anchor.",
                    "Form the reconstruction residual relative to that geometry anchor, remove its local low-frequency component with a fixed tile-safe Gaussian operator, and add back only a bounded detail band.",
                    "Use a bounded local quality gain for the detail band; do not use full-image pooling or a global statistic that would break tile parity.",
                    "Keep the output range bounded and preserve the geometry-anchor local mean."
                ],
                "training_changes": [
                    "For synthetic observations of the same latent geometry under exposure, noise, halo, and blur changes, align by known motion and penalize variation of the normal edge profile, 50% position, transition width, and contrast.",
                    "Add a local low-frequency identity loss between output and geometry anchor.",
                    "Penalize along-boundary variation and upper-tail jumps of the normal-shift map, not merely whole-image parameter smoothness.",
                    "Include synthetic bright annuli and template-like structures, but do not use real JunHua or SEM structures as training labels.",
                    "Continue scratch training with no V42 weight inheritance."
                ]
            },
            "pretraining_probes": [
                "External-GMF package A: R109 with normal shift disabled, to test whether the shift branch drives coordinate jitter.",
                "External-GMF package B: Raw plus 0.5 times the high-frequency R109 residual, to test low-frequency anchoring without a new training run.",
                "Run SEM ACM, deterministic LSC, line-pattern, and tile-parity checks on the same probes before selecting an architecture."
            ]
        }
    }
    (RESULTS / "mechanism_findings.json").write_text(json.dumps(findings, ensure_ascii=False, indent=2), encoding="utf-8")

    design = f"""# R112 model-side GMF mechanism conclusion

## Outcome

There is a credible model-side path to improve R109. The evidence points to
output parameterization, not a need to copy the full V42 model.

## Strongest evidence

- Deterministic LSC: V42 and R109 are equivalent.
- External GMF Y-step SD: V42 {findings['verified']['metric_pattern']['external_gmf_v42_y_step_std_px']:.3f} px; R109 {findings['verified']['metric_pattern']['external_gmf_r109_y_step_std_px']:.3f} px.
- Median low-frequency residual share: V42 {100*v42_residual['low_fraction_median']:.1f}%; R109 {100*r109_residual['low_fraction_median']:.1f}%.
- V42 without its Raw anchor changes the crop by {v42_no_anchor['residual_mae_gray']:.1f} gray levels instead of {v42_component['residual_mae_gray']:.1f}; the anchor is the dominant final-output constraint.
- R109 upper-tail normal-shift changes correlate with external step error (Spearman {shift_correlation['spearman']:.3f}, p={shift_correlation['p_value']:.4f}).

## Recommended model change

Keep R109's geometric detector. Predict smoother low-resolution width and shift
fields, warp Raw to create a geometry anchor, and add only a bounded local
high-frequency residual whose local mean remains tied to that anchor. Train
normal-profile consistency across synthetic exposure/noise/blur pairs.

## What not to do

- Do not simply append the V42 Raw-anchor formula to the current R109 output;
  the current predictor carries too much high-frequency energy and the simple
  wrapper trades template consistency against ring-width stability.
- Do not enlarge the full backbone first.
- Do not trust the internal fixed-template surrogate; it failed to reproduce
  the observed external-GMF ranking.

## Before training

Externally test only two cheap counterfactuals: R109 without normal shift, and
Raw plus 0.5 times the high-frequency R109 residual. Promote the architecture
only if one improves GMF without weakening ACM, deterministic LSC, line, or
tile-parity behavior.
"""
    (ROOT / "MODEL_IMPROVEMENT_DESIGN.md").write_text(design, encoding="utf-8")
    print(json.dumps({"status": "complete", "findings": str(RESULTS / "mechanism_findings.json"), "design": str(ROOT / "MODEL_IMPROVEMENT_DESIGN.md")}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

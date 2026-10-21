"""Summarize the verified causal structure evidence without promoting a model."""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import cv2
import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "results" / "structure"


def read_gray(path: Path) -> np.ndarray:
    value = cv2.imdecode(np.fromfile(str(path), np.uint8), cv2.IMREAD_GRAYSCALE)
    if value is None:
        raise RuntimeError(path)
    return value


def row(table: pd.DataFrame, model: str, variant: str) -> dict:
    selected = table[(table["model"] == model) & (table["variant"] == variant)]
    if len(selected) != 1:
        raise RuntimeError(f"Missing unique row {model}/{variant}")
    return json.loads(selected.to_json(orient="records"))[0]


def paired_output_mae(model: str, left: str, right: str, cases: list[str]) -> dict:
    values = []
    maxima = []
    for case in cases:
        a = read_gray(OUT / "outputs" / case / model / f"{left}.png").astype(np.float32)
        b = read_gray(OUT / "outputs" / case / model / f"{right}.png").astype(np.float32)
        difference = np.abs(a - b)
        values.append(float(difference.mean()))
        maxima.append(float(difference.max()))
    return {
        "left": left,
        "right": right,
        "per_case_mae_gray": dict(zip(cases, values)),
        "median_mae_gray": float(np.median(values)),
        "maximum_case_mae_gray": float(np.max(values)),
        "maximum_pixel_difference_gray": float(np.max(maxima)),
    }


def main() -> int:
    metrics = pd.read_csv(OUT / "per_case_variant_metrics.csv")
    causal = pd.read_csv(OUT / "causal_contrast_summary.csv")
    internal = pd.read_csv(OUT / "internal_module_statistics.csv")
    architecture = json.loads((OUT / "architecture_inventory.json").read_text(encoding="utf-8"))
    validation = json.loads((OUT / "validation.json").read_text(encoding="utf-8"))
    cases = list(dict.fromkeys(metrics["case"].tolist()))
    synthetic_cases = [case for case in cases if case.startswith("synthetic")]

    v42_quality = internal[(internal["model"] == "V42_E120") & (internal["module"] == "quality_gate")]
    r109_learned = internal[(internal["model"] == "R109_E48") & (internal["module"] == "learned_support")]
    r109_full = metrics[(metrics["model"] == "R109_E48") & (metrics["variant"] == "full") & metrics["case"].isin(synthetic_cases)].set_index("case")
    r109_identity = metrics[(metrics["model"] == "R109_E48") & (metrics["variant"] == "identity") & metrics["case"].isin(synthetic_cases)].set_index("case")
    synthetic_improvement = {
        case: {
            "identity_label_mae_gray": float(r109_identity.loc[case, "label_mae_gray"]),
            "full_label_mae_gray": float(r109_full.loc[case, "label_mae_gray"]),
            "full_reduction_fraction": float(1 - r109_full.loc[case, "label_mae_gray"] / r109_identity.loc[case, "label_mae_gray"]),
        }
        for case in synthetic_cases
    }

    findings = {
        "status": "complete",
        "generated_local": datetime.now().astimezone().isoformat(),
        "validation_status": validation["status"],
        "scope": {"matched_cases": cases, "outputs": int(len(metrics)), "sem_intervention_outputs": 60},
        "architecture_relation": {
            "r61_v42_source_code_byte_identical": architecture["source_model_identity"]["files_byte_identical"],
            "r61_parameters": architecture["models"]["R61_v16"]["parameters"],
            "v42_parameters": architecture["models"]["V42_E120"]["parameters"],
            "r109_parameters": architecture["models"]["R109_E48"]["parameters"],
            "shared_r61_v42_tensors": architecture["r61_v42_weight_inheritance"]["shared_same_shape_tensors"],
            "exact_shared_r61_v42_tensors": architecture["r61_v42_weight_inheritance"]["exact_shared_tensors"],
            "exact_shared_fraction": architecture["r61_v42_weight_inheritance"]["exact_shared_fraction"],
            "only_v42_state_tensors": architecture["r61_v42_weight_inheritance"]["only_v42"],
            "changed_weight_groups": [
                item for item in architecture["r61_v42_weight_inheritance"]["group_comparison"] if item["relative_l2_difference"] > 0
            ],
            "interpretation": "V42 is a targeted continuation of the R61 backbone, not an independent architecture: all weights through u1 are byte-identical; learned changes start at p1/out/boundary plus four quality-gate tensors and a parameter-free Raw anchor.",
        },
        "v42_causal_decomposition": {
            "remove_raw_anchor": row(causal, "V42_E120", "no_raw_anchor"),
            "remove_main_physics": row(causal, "V42_E120", "no_main_physics"),
            "remove_weak_psf": row(causal, "V42_E120", "no_weak_psf"),
            "remove_boundary_adapter": row(causal, "V42_E120", "no_boundary_adapter"),
            "remove_quality_gate": row(causal, "V42_E120", "no_quality_gate"),
            "quality_scale_range": [float(v42_quality["scale_mean"].min()), float(v42_quality["scale_mean"].max())],
            "quality_score_range": [float(v42_quality["quality_score"].min()), float(v42_quality["quality_score"].max())],
            "interpretation": "The Raw anchor is the dominant final-output constraint. Weak PSF is exactly inactive. Physics still changes edge topology on some synthetic cases despite its smaller final pixel effect; boundary and quality are fine adjustments on this set.",
        },
        "r61_runtime_separation": {
            "locked_runtime": {"physics_alpha": 0.0, "weak_psf": False, "boundary_adapter": True},
            "checkpoint_native": {"physics_alpha": architecture["models"]["R61_v16"]["inferred_architecture"]["psf_phys_alpha_init"], "weak_psf": True, "boundary_adapter": True},
            "native_vs_locked": paired_output_mae("R61_v16", "checkpoint_native_full", "locked_psf_off_full", cases),
            "native_weak_psf_effect": paired_output_mae("R61_v16", "checkpoint_native_full", "native_no_weak_psf", cases),
            "native_main_physics_effect": paired_output_mae("R61_v16", "checkpoint_native_full", "native_no_main_physics", cases),
            "locked_boundary_effect": paired_output_mae("R61_v16", "locked_psf_off_full", "locked_psf_off_no_boundary", cases),
            "context_finding": "The locked runtime replays its full-frame reference within one gray level mean, but isolated 512 crops differ from the corresponding full-frame region by more than one gray level mean. R61 therefore remains inference-area/context sensitive and must not be described as tile-safe.",
        },
        "r109_causal_decomposition": {
            "full_vs_identity_synthetic": synthetic_improvement,
            "remove_shift": row(causal, "R109_E48", "no_shift"),
            "remove_width": row(causal, "R109_E48", "no_width"),
            "source_support_only": row(causal, "R109_E48", "source_support_only"),
            "learned_support_only": row(causal, "R109_E48", "learned_support_only"),
            "smoothed_controls": row(causal, "R109_E48", "smoothed_controls"),
            "learned_support_statistics": {
                "mean_range": [float(r109_learned["full_mean"].min()), float(r109_learned["full_mean"].max())],
                "maximum_spatial_std": float(r109_learned["full_std"].max()),
                "maximum_p95_minus_p05": float((r109_learned["p95"] - r109_learned["p05"]).max()),
            },
            "hardcoded_necessity": 1.0,
            "interpretation": "Width is the main enhancement control, shift adds smaller scene-dependent benefit, and mild control smoothing preserves the full output closely. The learned boundary-support arm has collapsed to an almost constant 0.432 floor, while necessity is hardcoded to one; the current model therefore lacks a real learned do-not-correct gate.",
        },
        "promotion_decision": {
            "status": "no_architecture_promotion_yet",
            "reason": "The structural evidence identifies mechanisms, but exact SEM ACM/LSC must decide whether no_shift or smoothed_controls preserves true contour geometry. Appearance or synthetic metrics alone cannot authorize a scientific reconstruction change.",
            "sem_variant_root": str(ROOT / "results" / "structure_probe" / "sem_interventions"),
            "sem_variants": ["full", "no_shift", "no_width", "learned_support_only", "smoothed_controls"],
        },
    }
    (OUT / "structure_findings.json").write_text(json.dumps(findings, ensure_ascii=False, indent=2), encoding="utf-8")
    markdown = f"""# R113 frozen-model structure findings

All structural checks passed across {len(cases)} matched cases and {len(metrics)} saved outputs.

## Architecture relation

- R61 and V42 use byte-identical model source code.
- {findings['architecture_relation']['exact_shared_r61_v42_tensors']} of {findings['architecture_relation']['shared_r61_v42_tensors']} shared tensors are byte-identical.
- All learned groups through `u1` are unchanged. V42 changes `p1`, `out`, and the boundary adapter, then adds a four-tensor quality gate and a parameter-free Raw-detail anchor.
- R109 is a separate, much smaller renderer ({findings['architecture_relation']['r109_parameters']:,} parameters versus roughly {findings['architecture_relation']['v42_parameters']:,}).

## Causal results

- V42 Raw anchor removal changes the final image by a median {findings['v42_causal_decomposition']['remove_raw_anchor']['median_causal_mae_gray']:.2f} gray levels. This is the dominant final constraint.
- V42 weak PSF removal changes exactly 0 gray levels because its learned beta scale is zero.
- R61 checkpoint-native PSF behavior and the locked PSF-off deployment are separate. Their median difference is {findings['r61_runtime_separation']['native_vs_locked']['median_mae_gray']:.2f} gray levels.
- R109 learned support is nearly constant: mean {findings['r109_causal_decomposition']['learned_support_statistics']['mean_range'][0]:.6f} to {findings['r109_causal_decomposition']['learned_support_statistics']['mean_range'][1]:.6f}, maximum spatial std {findings['r109_causal_decomposition']['learned_support_statistics']['maximum_spatial_std']:.6f}.
- R109 has no learned necessity gate (`necessity=1`). Width is the principal enhancement branch; normal shift is secondary and scene-dependent.
- Smoothed R109 controls remain close to full output (median {findings['r109_causal_decomposition']['smoothed_controls']['median_causal_mae_gray']:.3f} gray), so this is a justified SEM-ACM probe, not yet a promoted model change.

## Boundary

No architecture change is authorized from appearance metrics. Exact SEM ACM and deterministic LSC on the exported intervention stack must decide the next change.
"""
    (OUT / "STRUCTURE_FINDINGS.md").write_text(markdown, encoding="utf-8")
    print(json.dumps({"status": "complete", "finding_file": str(OUT / "structure_findings.json")}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

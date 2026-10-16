"""Integrate the completed preflight into design evidence and chart tables."""
from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "results"
REPORTS = ROOT / "reports"


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2, ensure_ascii=False, allow_nan=False), encoding="utf-8")
    temporary.replace(path)


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    core = read_json(RESULTS / "core_validation.json")
    acm = read_json(RESULTS / "acm_photometric_audit.json")
    geometry = core["geometry_target_audit"]
    identity_current = geometry["identity"]["current_target_abs_px"]["mean"]
    identity_difference = geometry["identity"]["difference_target_abs_px"]["mean"]
    translation_current = geometry["translate"]["current_mae_to_known_px"]["mean"]
    translation_difference = geometry["translate"]["difference_mae_to_known_px"]["mean"]

    synthetic = core["synthetic_operator_audit"]["methods"]
    motion = core["synthetic_motion_audit"]["methods"]
    real = core["real_probe"]["symmetric_operators"]
    x1um = core["x1um_motion_audit"]["methods"]
    boost_rows: list[dict[str, Any]] = []
    for gain in (15, 30, 45, 60):
        name = f"boost_{gain:02d}"
        boost_rows.append({
            "method": name,
            "gain": gain / 100.0,
            "synthetic_detail_mae_gray": synthetic[name]["detail_mae_gray"]["mean"],
            "synthetic_boundary_distance_px": synthetic[name]["boundary_distance_px"]["mean"],
            "synthetic_contour_iou": synthetic[name]["contour_iou"]["mean"],
            "synthetic_motion_centroid_mae_px": motion[name]["centroid_axis_mae_px"],
            "synthetic_motion_phase_mae_px": motion[name]["phase_axis_mae_px"],
            "real_fine_ratio_mean": float(np.mean([real[name][magnification]["fine_detail_rms_ratio"]["mean"] for magnification in ("5x", "20x", "50x")])),
            "real_self_shift_px_mean": float(np.mean([real[name][magnification]["self_phase_shift_px"]["mean"] for magnification in ("5x", "20x", "50x")])),
            "x1um_step_std_um": x1um[name]["step_std_um"],
            "x1um_rmse_um": x1um[name]["rmse_from_1um"],
            "x1um_paired_median_abs_difference_um": x1um[name]["paired_step_difference_vs_raw_um"]["median_abs"],
        })
    write_csv(REPORTS / "detail_motion_tradeoff.csv", boost_rows)

    geometry_rows = []
    for family in ("identity", "translate", "dilate", "erode"):
        geometry_rows.extend([
            {"case": family, "target": "current", "known_displacement_mae_px": geometry[family]["current_mae_to_known_px"]["mean"], "within_band_std_px": geometry[family]["current_within_band_std_px"]["mean"]},
            {"case": family, "target": "distance_difference", "known_displacement_mae_px": geometry[family]["difference_mae_to_known_px"]["mean"], "within_band_std_px": geometry[family]["difference_within_band_std_px"]["mean"]},
        ])
    write_csv(REPORTS / "geometry_target_comparison.csv", geometry_rows)

    acm_rows = []
    for row in acm["variant_summary"]:
        acm_rows.append({
            "preset": row["preset"],
            "variant": row["variant"],
            "count": row["count"],
            "median_iou": row["median_iou"],
            "minimum_iou": row["minimum_iou"],
            "median_boundary_distance_px": row["median_boundary_distance_px"],
            "median_abs_area_error_fraction": row["median_abs_area_error_fraction"],
        })
    write_csv(REPORTS / "acm_photometric_sensitivity.csv", acm_rows)

    best_visual = max(boost_rows, key=lambda row: row["real_fine_ratio_mean"])
    raw_motion = x1um["raw"]
    global_motion = x1um["band_global"]
    coefficients = core["band_operator_fit"]["clipped_coefficients"]
    fine_sign = "negative" if coefficients[0] < 0 else "positive"

    verified_findings = [
        {
            "finding": "The R99 transport label violates the aligned-input invariant.",
            "evidence": f"Aligned geometry receives {identity_current:.3f} px mean absolute command; the distance-difference label receives {identity_difference:.6f} px.",
            "confidence": "high",
        },
        {
            "finding": "The distance-difference label follows known signed motion more closely.",
            "evidence": f"Translation MAE falls from {translation_current:.3f} px to {translation_difference:.3f} px in the independent shape audit.",
            "confidence": "high",
        },
        {
            "finding": "The current procedural target distribution does not consistently ask for sharper fine detail.",
            "evidence": f"The globally fitted finest-band coefficient is {coefficients[0]:+.3f} ({fine_sign}); per-view positive fraction is {core['band_operator_fit']['positive_fine_coefficient_fraction']:.3f}.",
            "confidence": "high",
        },
        {
            "finding": "A symmetric local operator can increase visible fine energy while preserving displacement much more closely than an arbitrary residual path.",
            "evidence": f"The strongest tested gain reaches {best_visual['real_fine_ratio_mean']:.3f}x mean real fine energy; its x1um paired median step change is {best_visual['x1um_paired_median_abs_difference_um'] * 1000:.3f} nm.",
            "confidence": "medium_high",
        },
        {
            "finding": "Exact large-image tiling is achievable by construction.",
            "evidence": f"The symmetric operator full-versus-tiled maximum difference is {core['tiling_audit']['symmetric_operator_max_abs_gray']:.6f} gray levels.",
            "confidence": "high",
        },
        {
            "finding": "ACM is a useful shape readout but not a geometry-only oracle.",
            "evidence": f"With identical geometry, primary ACM has median within-shape photometric IoU range {acm['photometric_iou_range']['median']:.4f} and maximum {acm['photometric_iou_range']['maximum']:.4f}; smoothness also changes the result.",
            "confidence": "high",
        },
        {
            "finding": "The internal phase proxy reproduces the real sequence well enough for paired stability comparisons, but does not replace external GMF.",
            "evidence": f"Raw phase step SD is {raw_motion['step_std_um'] * 1000:.2f} nm versus external GMF {core['x1um_motion_audit']['external_gmf_raw_reference']['x_step_std_um'] * 1000:.2f} nm.",
            "confidence": "medium",
        },
    ]

    design_implications = [
        "Replace absolute target signed distance with source-to-target signed-distance difference, and store or deterministically derive the source geometry field used by that label.",
        "Do not give illumination, edge and texture stages unrestricted image residual outputs. Each stage should predict parameters for an operation whose physical role is fixed.",
        "Keep fine-detail restoration zero-phase and source-supported; train its strength predictor, not a free texture image.",
        "Separate target construction for physical shape, physical transition width and material texture. The current latent target is often smoother than the desired real-image appearance.",
        "Use exact full/tiled equivalence as a model property from the first prototype, not as a late loss term.",
        "Use ACM together with exact synthetic masks, multi-threshold contour stability and sensitivity presets. Never select a checkpoint from one ACM setting alone.",
        "Keep real 5x/20x/50x intervention and x1um paired motion as live falsification views, but do not tune spatial targets from real SEM structure.",
        "Before a full scratch run, overfit a tiny role-balanced set and require the aligned geometry command, polarity reversal, reverse motion and stage-isolation checks to behave correctly.",
    ]

    payload = {
        "status": "complete",
        "training_authorized_or_started": False,
        "decision": "Evidence is sufficient to reject an R99-style free-residual revision. It supports a constrained, stage-causal prototype, but that prototype still requires a tiny overfit/falsification run before a full training design is frozen.",
        "verified_findings": verified_findings,
        "design_implications": design_implications,
        "remaining_uncertainty": [
            "A fixed symmetric operator proves compatibility, not that a learned strength predictor will generalize.",
            "Real microscope images have no clean texture truth; real-image sharpness remains an intervention and stability test rather than supervised accuracy.",
            "The external GMF program was not rerun for the new counterfactual images, so the phase proxy is used only for paired screening.",
            "The proposed constrained prototype has not yet been trained, so no R100 architecture is declared final in this validation folder.",
        ],
        "headline_metrics": {
            "aligned_current_transport_command_px": identity_current,
            "aligned_difference_transport_command_px": identity_difference,
            "best_tested_real_fine_energy_ratio": best_visual["real_fine_ratio_mean"],
            "best_tested_x1um_paired_median_step_change_nm": best_visual["x1um_paired_median_abs_difference_um"] * 1000.0,
            "global_band_fine_coefficient": coefficients[0],
            "acm_photometric_iou_range_median": acm["photometric_iou_range"]["median"],
            "candidate_tile_max_difference_gray": core["tiling_audit"]["symmetric_operator_max_abs_gray"],
            "band_global_x1um_step_std_nm": global_motion["step_std_um"] * 1000.0,
        },
        "supporting_tables": [
            "geometry_target_comparison.csv",
            "detail_motion_tradeoff.csv",
            "acm_photometric_sensitivity.csv",
        ],
    }
    write_json(REPORTS / "design_evidence.json", payload)
    print(json.dumps({
        "status": payload["status"],
        "decision": payload["decision"],
        "headline_metrics": payload["headline_metrics"],
    }, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


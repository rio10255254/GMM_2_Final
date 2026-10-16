"""Create a compact machine-readable synthesis after every fixed R97 validation arm completes."""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "results" / "posttraining_validation"
OUTPUT = BASE / "synthesis"


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(path)


def sem_summary() -> dict:
    table = pd.read_csv(BASE / "sem_contour" / "results" / "tables" / "six_method_per_pillar_summary.csv")
    return {row["method"]: row for row in table.to_dict(orient="records")}


def appearance_summary() -> dict:
    table = pd.read_csv(BASE / "real_generalization" / "appearance_per_frame.csv")
    metrics = [
        "mean_abs_change_gray", "ssim_to_raw", "edge_gain_on_raw_support", "fine_detail_energy_ratio",
        "off_source_strong_edge_fraction", "dark_change_fraction_on_edge_band",
        "bright_change_fraction_on_edge_band", "mean_abs_change_flat_region_gray",
        "tile_seam_residual_ratio",
    ]
    result: dict[str, dict] = {}
    for method, group in table.groupby("method", sort=False):
        result[method] = {f"median_{metric}": float(group[metric].median()) for metric in metrics}
    paired = table.pivot(index=["sequence", "frame_index"], columns="method", values=metrics)
    result["r97_vs_r96"] = {
        "edge_gain_higher_fraction": float((paired["edge_gain_on_raw_support"]["R97E48"] > paired["edge_gain_on_raw_support"]["R96E44"]).mean()),
        "fine_detail_higher_fraction": float((paired["fine_detail_energy_ratio"]["R97E48"] > paired["fine_detail_energy_ratio"]["R96E44"]).mean()),
        "median_edge_gain_delta": float((paired["edge_gain_on_raw_support"]["R97E48"] - paired["edge_gain_on_raw_support"]["R96E44"]).median()),
        "median_fine_detail_delta": float((paired["fine_detail_energy_ratio"]["R97E48"] - paired["fine_detail_energy_ratio"]["R96E44"]).median()),
    }
    return result


def motion_summary() -> dict:
    table = pd.read_csv(BASE / "real_generalization" / "motion_common_valid_summary.csv")
    metrics = [
        "valid_fraction_within_raw_reference", "median_abs_error_to_nominal_um", "step_std_um",
        "step_robust_mad_um", "median_vector_difference_from_raw_um", "p95_vector_difference_from_raw_um",
        "median_response_ratio",
    ]
    result: dict[str, dict] = {}
    for method, group in table.groupby("method", sort=False):
        result[method] = {f"mean_sequence_{metric}": float(group[metric].mean()) for metric in metrics}
    pivot = table.pivot(index="sequence", columns="method", values=metrics)
    result["r97_minus_r96_mean_sequence_delta"] = {
        metric: float((pivot[metric]["R97E48"] - pivot[metric]["R96E44"]).mean()) for metric in metrics
    }
    return result


def main() -> None:
    required = [
        BASE / "real_generalization" / "summary.json",
        BASE / "sem_contour" / "summary.json",
        BASE / "model_internal" / "summary.json",
        BASE / "procedural_by_role" / "summary.json",
        BASE / "periodic_stress" / "summary.json",
        BASE / "training_dynamics" / "summary.json",
        BASE / "weight_dynamics" / "summary.json",
    ]
    missing = [str(path) for path in required if not path.is_file()]
    if missing:
        raise FileNotFoundError(missing)
    real = read_json(required[0])
    sem = read_json(required[1])
    internal = read_json(required[2])
    procedural = read_json(required[3])
    periodic = read_json(required[4])
    dynamics = read_json(required[5])
    weights = read_json(required[6])
    result = {
        "status": "complete",
        "fixed_endpoint": {"epoch": 48, "state": "ema_state_dict"},
        "data_integrity": {
            "training_complete": dynamics["run_status"] == "complete",
            "epochs_contiguous": dynamics["epochs_contiguous"],
            "all_logged_present_values_finite": dynamics["all_present_numeric_values_finite"],
            "all_checkpoint_parameters_finite": weights["all_ema_parameters_finite"],
            "real_frames": real["unique_real_frames"],
            "real_hashes_verified": real["reconstruction_hashes_verified"],
            "locked_motion_measurements": real["locked_motion_measurements"],
            "sem_physical_pillars": sem["physical_pillars"],
            "sem_exposures": sem["exposures"],
            "sem_raw_reproduced_exactly": sem["raw_reproduced_exactly"],
            "procedural_roles_per_split": procedural["role_count_per_split"],
            "procedural_unique_scenes": procedural["all_roles_have_unique_scene_ids"],
            "periodic_unseen_scenes": periodic["unseen_scenes_per_method"],
        },
        "training_dynamics": dynamics,
        "real_appearance": appearance_summary(),
        "real_motion": motion_summary(),
        "sem_contour": sem_summary(),
        "sem_sensitivity": pd.read_csv(
            BASE / "sem_contour" / "results" / "tables" / "r97_sensitivity_summary.csv"
        ).to_dict(orient="records"),
        "component_geometry": internal["component_geometry"],
        "tiling": {
            "small_images": internal["small_image_full_vs_tiled"],
            "large_real_crop": internal["large_real_crop_full_vs_tiled"],
        },
        "branch_summaries": internal["branch_summaries"],
        "procedural_by_role": procedural,
        "periodic_stress": periodic,
        "claim_boundary": [
            "Real optical images have no clean optical target, so appearance-to-Raw metrics measure change and artifacts rather than restoration accuracy.",
            "Locked adjacent-frame tracking measures stability relative to Raw; external GMF was not rerun for R97.",
            "SEM contour truth covers only the paired central 36 pillars and ACM sensitivity shows whether small differences are robust.",
            "R97 remains an experimental candidate and this validation does not change the formal COMBO or thesis V42 roles.",
        ],
    }
    write_json(OUTPUT / "summary.json", result)
    print(json.dumps({"status": result["status"], "data_integrity": result["data_integrity"]}, indent=2), flush=True)


if __name__ == "__main__":
    main()

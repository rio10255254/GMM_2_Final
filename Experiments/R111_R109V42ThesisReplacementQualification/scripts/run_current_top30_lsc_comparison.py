"""Compare V42 and R109 with LSC centers on the current Chapter 6.2 top-30 list."""
from __future__ import annotations

import importlib.util
import json
import sys
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
import skimage.segmentation.morphsnakes as morphsnakes
PROJECT_ROOT = Path(__file__).resolve().parents[3]


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "results" / "lsc_current_top30"
TABLES = OUTPUT / "tables"
TABLES.mkdir(parents=True, exist_ok=True)

R80_ROOT = Path(str(PROJECT_ROOT / 'Experiments/R80_InflectionReferenceCircleSEMValidation'))
R80_SCRIPT = R80_ROOT / "scripts" / "run_displacement_lsc.py"
V42_CONFIG = Path(
    str(PROJECT_ROOT / 'Thesis_MOSR_Evidence/Final_Data_Figures/01_CURRENT_THESIS_RESULTS_V42_CENTER9/config/sequence_center9_50x20x.json')
)
R109_CONFIG = ROOT / "config" / "r109_thesis_sequence_config.json"
TOP30 = Path(
    str(PROJECT_ROOT / 'Thesis_MOSR_Evidence/Final_Data_Figures/04_V42_NEURAL_NETWORK_RESULTS/tables/top30_raw_motion_selection.csv')
)


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot import {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def truthy(values: pd.Series) -> pd.Series:
    if values.dtype == bool:
        return values
    return values.astype(str).str.lower().isin({"true", "1", "yes"})


def reset_curvature_cycle() -> None:
    """Reset skimage's stateful alternating curvature operator for fair calls."""
    morphsnakes._curvop = morphsnakes._fcycle(
        [
            lambda values: morphsnakes.sup_inf(morphsnakes.inf_sup(values)),
            lambda values: morphsnakes.inf_sup(morphsnakes.sup_inf(values)),
        ]
    )


def main() -> int:
    sys.path.insert(0, str(R80_ROOT / "scripts"))
    module = load_module(R80_SCRIPT, "r111_current_top30_lsc")
    top = pd.read_csv(TOP30)
    top = top.loc[truthy(top["top30_raw_motion_selected"]), ["sequence", "end_frame_index"]].copy()
    top["start_frame_index"] = top["end_frame_index"].astype(int) - 1
    audit = pd.read_csv(module.AUDIT_TABLE)

    def selected_pairs_current(sequence: str, limit_pairs: int = 30) -> pd.DataFrame:
        keys = top.loc[top["sequence"] == sequence, ["start_frame_index", "end_frame_index"]]
        current = audit.loc[audit["sequence"] == sequence].merge(
            keys, on=["start_frame_index", "end_frame_index"], how="inner", validate="one_to_one"
        )
        if len(current) != 30:
            raise RuntimeError(f"{sequence}: expected 30 current top-30 pairs, found {len(current)}")
        return current.sort_values("start_frame_index").reset_index(drop=True)

    sequences = ["50x_x_0p5um", "50x_x_1um", "20x_0p5um", "20x_1um"]
    v42_config = json.loads(V42_CONFIG.read_text(encoding="utf-8"))
    r109_config = json.loads(R109_CONFIG.read_text(encoding="utf-8"))
    centers_all: list[pd.DataFrame] = []
    pairs_all: list[pd.DataFrame] = []
    determinism_differences: list[float] = []

    for sequence in sequences:
        print(f"four-method pass: processing {sequence}", flush=True)
        specification = v42_config["sequences"][sequence]
        r109_specification = r109_config["sequences"][sequence]
        for key, value in specification.items():
            if key == "v42_dir":
                continue
            if str(PROJECT_ROOT / r109_specification.get(key)) != str(PROJECT_ROOT / value):
                raise RuntimeError(f"{sequence}: V42/R109 config differs at {key}")
        pairs = selected_pairs_current(sequence)
        frame_indices = sorted(
            set(pairs["start_frame_index"].astype(int))
            | set(pairs["end_frame_index"].astype(int))
        )
        base_centers = np.asarray(specification["centers"], dtype=float)
        raw_dir = Path(PROJECT_ROOT / specification["raw_dir"])
        v42_dir = Path(PROJECT_ROOT / specification["v42_dir"])
        r109_dir = Path(PROJECT_ROOT / r109_specification["v42_dir"])
        magnification = specification["magnification"]
        pitch = float(specification["pitch_px"])
        radius = float(specification["radius_px"])
        scale = float(specification["object_um_per_px"])
        expected_dx_px = float(specification["expected_signed_dx_px"])
        patch_half = int(np.ceil(0.46 * pitch))
        sample_count = 64 if magnification == "20x" else 96
        acm_iterations = 13 if magnification == "20x" else 15
        normal_half = 2.4 if magnification == "20x" else 4.0
        psf = np.asarray(
            module.loadmat(module.SWEEP_ROOT / f"{magnification}_deconvolution_sweep.mat", squeeze_me=True)["psf"],
            dtype=float,
        )

        center_rows: list[dict[str, object]] = []
        for frame_index in frame_indices:
            filename = f"frame_{frame_index:04d}.bmp"
            raw = module.load_grayscale(raw_dir / filename)
            v42 = module.load_grayscale(v42_dir / filename)
            r109 = module.load_grayscale(r109_dir / filename)
            predicted = module.session_prediction(
                sequence, frame_index, base_centers, expected_dx_px
            )
            margin = int(np.ceil(0.55 * pitch))
            x0 = max(0, int(np.floor(np.min(predicted[:, 1]))) - margin)
            x1 = min(raw.shape[1], int(np.ceil(np.max(predicted[:, 1]))) + margin + 1)
            y0 = max(0, int(np.floor(np.min(predicted[:, 2]))) - margin)
            y1 = min(raw.shape[0], int(np.ceil(np.max(predicted[:, 2]))) + margin + 1)
            raw_roi = raw[y0:y1, x0:x1]
            wiener_roi = module.wiener_contrast_restore(raw_roi, psf, module.NSR, pitch_px=pitch)
            method_images = {
                "Raw": raw_roi,
                "Wiener": wiener_roi,
                "V42 E120": v42[y0:y1, x0:x1],
                "R109 E48": r109[y0:y1, x0:x1],
            }
            for method, image in method_images.items():
                for pillar_id, predicted_x, predicted_y in predicted:
                    local_center = (float(predicted_x - x0), float(predicted_y - y0))
                    patch, patch_center, patch_origin = module.crop_around(
                        image, local_center, patch_half
                    )
                    reset_curvature_cycle()
                    measurement = module.measure_inflection_lsc(
                        patch,
                        patch_center,
                        radius,
                        sample_count=sample_count,
                        acm_iterations=acm_iterations,
                        normal_half_width_px=normal_half,
                        polarity="dark",
                    )
                    if not determinism_differences:
                        reset_curvature_cycle()
                        repeated = module.measure_inflection_lsc(
                            patch,
                            patch_center,
                            radius,
                            sample_count=sample_count,
                            acm_iterations=acm_iterations,
                            normal_half_width_px=normal_half,
                            polarity="dark",
                        )
                        determinism_differences.extend(
                            [
                                abs(measurement.lsc.cx - repeated.lsc.cx),
                                abs(measurement.lsc.cy - repeated.lsc.cy),
                                abs(measurement.lsc.radius - repeated.lsc.radius),
                            ]
                        )
                    center_rows.append(
                        {
                            "sequence": sequence,
                            "magnification": magnification,
                            "frame_index": frame_index,
                            "method": method,
                            "pillar_id": int(pillar_id),
                            "predicted_x_px": float(predicted_x),
                            "predicted_y_px": float(predicted_y),
                            "lsc_center_x_px": measurement.lsc.cx + patch_origin[0] + x0,
                            "lsc_center_y_px": measurement.lsc.cy + patch_origin[1] + y0,
                            "lsc_radius_px": measurement.lsc.radius,
                            "gradient_strength_median": float(
                                np.median(measurement.signed_gradient_strength)
                            ),
                            "object_um_per_px": scale,
                        }
                    )
        centers = pd.DataFrame(center_rows)
        indexed = centers.set_index(["method", "frame_index", "pillar_id"])
        pair_rows: list[dict[str, object]] = []
        for pair_rank, pair in pairs.iterrows():
            start = int(pair["start_frame_index"])
            end = int(pair["end_frame_index"])
            for method in method_images:
                pillar_dx: list[float] = []
                pillar_dy: list[float] = []
                for pillar_id in base_centers[:, 0].astype(int):
                    before = indexed.loc[(method, start, pillar_id)]
                    after = indexed.loc[(method, end, pillar_id)]
                    pillar_dx.append(
                        (float(after["lsc_center_x_px"]) - float(before["lsc_center_x_px"]))
                        * scale
                    )
                    pillar_dy.append(
                        (float(after["lsc_center_y_px"]) - float(before["lsc_center_y_px"]))
                        * scale
                    )
                aggregate_dx = float(np.median(pillar_dx))
                aggregate_dy = float(np.median(pillar_dy))
                nominal = float(specification["nominal_step_um"])
                pair_rows.append(
                    {
                        "sequence": sequence,
                        "magnification": magnification,
                        "pair_rank_raw_locked": pair_rank + 1,
                        "start_frame_index": start,
                        "end_frame_index": end,
                        "method": method,
                        "nominal_step_um": nominal,
                        "aggregate_dx_um": aggregate_dx,
                        "aggregate_dy_um": aggregate_dy,
                        "measured_step_um": abs(aggregate_dx),
                        "nominal_abs_error_nm": abs(abs(aggregate_dx) - nominal) * 1000.0,
                        "within_grid_sd_nm": float(np.std(pillar_dx, ddof=1) * 1000.0),
                        "cross_axis_abs_nm": abs(aggregate_dy) * 1000.0,
                    }
                )
        centers_all.append(centers)
        pairs_all.append(pd.DataFrame(pair_rows))
        print(
            json.dumps(
                {
                    "sequence": sequence,
                    "frames": len(frame_indices),
                    "centers": len(centers),
                    "pairs": len(pair_rows),
                }
            ),
            flush=True,
        )

    centers = pd.concat(centers_all, ignore_index=True)
    combined = pd.concat(pairs_all, ignore_index=True)
    summary = module.summarize_pairs(combined)
    centers.to_csv(TABLES / "four_method_lsc_centers_current_top30.csv", index=False, encoding="utf-8-sig")
    combined.to_csv(TABLES / "four_method_lsc_per_pair_current_top30.csv", index=False, encoding="utf-8-sig")
    summary.to_csv(TABLES / "four_method_lsc_summary_current_top30.csv", index=False, encoding="utf-8-sig")

    combined_summary = summary.loc[summary["scope"] == "all_four_sequences"].set_index("method")
    result = {
        "status": "complete",
        "generated_local": datetime.now().astimezone().isoformat(),
        "method": "ACM coarse contour + maximum-gradient inflection points + least-squares-circle center",
        "selection": "current Chapter 6.2 top-30 Raw-motion list",
        "total_pairs": 120,
        "pairs_per_sequence": 30,
        "single_pass_shared_prediction_centers": True,
        "curvature_cycle_reset_before_every_measurement": True,
        "determinism_spot_check_max_px": float(max(determinism_differences)),
        "v42": {
            metric: float(combined_summary.loc["V42 E120", metric])
            for metric in ("step_sd_nm", "mean_nominal_abs_error_nm", "median_within_grid_sd_nm", "median_cross_axis_abs_nm")
        },
        "r109": {
            metric: float(combined_summary.loc["R109 E48", metric])
            for metric in ("step_sd_nm", "mean_nominal_abs_error_nm", "median_within_grid_sd_nm", "median_cross_axis_abs_nm")
        },
    }
    result["comparison"] = {
        "step_sd_change_r109_vs_v42_pct": (result["r109"]["step_sd_nm"] / result["v42"]["step_sd_nm"] - 1.0) * 100.0,
        "nominal_mae_change_r109_vs_v42_pct": (result["r109"]["mean_nominal_abs_error_nm"] / result["v42"]["mean_nominal_abs_error_nm"] - 1.0) * 100.0,
        "within_grid_change_r109_vs_v42_pct": (result["r109"]["median_within_grid_sd_nm"] / result["v42"]["median_within_grid_sd_nm"] - 1.0) * 100.0,
        "cross_axis_change_r109_vs_v42_pct": (result["r109"]["median_cross_axis_abs_nm"] / result["v42"]["median_cross_axis_abs_nm"] - 1.0) * 100.0,
    }
    result["winner_by_metric"] = {
        metric: "R109 E48" if result["r109"][metric] < result["v42"][metric] else "V42 E120"
        for metric in result["v42"]
    }
    (OUTPUT / "lsc_current_top30_summary.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

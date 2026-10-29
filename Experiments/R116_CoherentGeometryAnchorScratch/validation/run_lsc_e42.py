"""Apply the locked ACM-inflection-LSC protocol to R116 E42."""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import skimage.segmentation.morphsnakes as morphsnakes
PROJECT_ROOT = Path(__file__).resolve().parents[3]


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "results" / "detailed_validation" / "05_lsc_e42"
TABLES = OUTPUT / "tables"
TABLES.mkdir(parents=True, exist_ok=True)
R80_SCRIPT = Path(str(PROJECT_ROOT / 'Experiments/R80_InflectionReferenceCircleSEMValidation/scripts/run_displacement_lsc.py'))
V42_CONFIG = Path(str(PROJECT_ROOT / 'Thesis_MOSR_Evidence/Final_Data_Figures/01_CURRENT_THESIS_RESULTS_V42_CENTER9/config/sequence_center9_50x20x.json'))
TOP30 = Path(str(PROJECT_ROOT / 'Thesis_MOSR_Evidence/Final_Data_Figures/04_V42_NEURAL_NETWORK_RESULTS/tables/top30_raw_motion_selection.csv'))
REFERENCE_PAIRS = Path(str(PROJECT_ROOT / 'Experiments/R111_R109V42ThesisReplacementQualification/results/lsc_current_top30/tables/four_method_lsc_per_pair_current_top30.csv'))
RECON_ROOT = ROOT / "results" / "detailed_validation" / "03_real_motion" / "R116_E042" / "reconstructions"
METHOD = "R116 E42"
SEQUENCE_MAP = {
    "50x_x_0p5um": "50x_0p5um",
    "50x_x_1um": "50x_1um",
    "20x_0p5um": "20x_0p5um",
    "20x_1um": "20x_1um",
}


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot import {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def reset_curvature_cycle() -> None:
    morphsnakes._curvop = morphsnakes._fcycle([
        lambda values: morphsnakes.sup_inf(morphsnakes.inf_sup(values)),
        lambda values: morphsnakes.inf_sup(morphsnakes.sup_inf(values)),
    ])


def bootstrap(reference: pd.DataFrame, candidate: pd.DataFrame,
              repetitions: int = 10000) -> dict[str, object]:
    keys = ["sequence", "start_frame_index", "end_frame_index"]
    paired = reference.merge(candidate, on=keys, suffixes=("_reference", "_candidate"), validate="one_to_one")
    groups = [group for _, group in paired.groupby("sequence", sort=False)]
    rng = np.random.default_rng(116542)
    values = np.empty((repetitions, 4), float)
    for index in range(repetitions):
        sampled = [group.iloc[rng.integers(0, len(group), len(group))] for group in groups]
        values[index] = [
            np.mean([g["measured_step_um_candidate"].std(ddof=1) * 1000 for g in sampled])
            - np.mean([g["measured_step_um_reference"].std(ddof=1) * 1000 for g in sampled]),
            np.mean(np.concatenate([g["nominal_abs_error_nm_candidate"].to_numpy() for g in sampled]))
            - np.mean(np.concatenate([g["nominal_abs_error_nm_reference"].to_numpy() for g in sampled])),
            np.median(np.concatenate([g["within_grid_sd_nm_candidate"].to_numpy() for g in sampled]))
            - np.median(np.concatenate([g["within_grid_sd_nm_reference"].to_numpy() for g in sampled])),
            np.median(np.concatenate([g["cross_axis_abs_nm_candidate"].to_numpy() for g in sampled]))
            - np.median(np.concatenate([g["cross_axis_abs_nm_reference"].to_numpy() for g in sampled])),
        ]
    labels = ("step_sd_nm", "nominal_mae_nm", "within_grid_median_nm", "cross_axis_median_nm")
    return {
        label: {
            "candidate_minus_reference_ci95": [float(value) for value in np.percentile(values[:, column], [2.5, 97.5])],
            "fraction_candidate_worse": float(np.mean(values[:, column] > 0)),
        }
        for column, label in enumerate(labels)
    }


def main() -> int:
    global OUTPUT, TABLES, RECON_ROOT, METHOD
    parser = argparse.ArgumentParser()
    parser.add_argument("--method", default=METHOD)
    parser.add_argument("--recon-root", default=str(RECON_ROOT))
    parser.add_argument("--output", default=str(OUTPUT))
    args = parser.parse_args()
    METHOD = str(args.method)
    RECON_ROOT = Path(args.recon_root).resolve()
    OUTPUT = Path(args.output).resolve()
    TABLES = OUTPUT / "tables"
    TABLES.mkdir(parents=True, exist_ok=True)
    module = load_module(R80_SCRIPT, "r116_lsc_e42")
    config = json.loads(V42_CONFIG.read_text(encoding="utf-8"))
    top = pd.read_csv(TOP30)
    top = top.loc[
        top["top30_raw_motion_selected"].astype(str).str.lower().isin({"true", "1", "yes"}),
        ["sequence", "end_frame_index"],
    ].copy()
    top["start_frame_index"] = top["end_frame_index"].astype(int) - 1
    audit = pd.read_csv(module.AUDIT_TABLE)
    center_tables = []
    pair_tables = []
    determinism = []
    for sequence in SEQUENCE_MAP:
        specification = config["sequences"][sequence]
        keys = top.loc[top["sequence"].eq(sequence), ["start_frame_index", "end_frame_index"]]
        pairs = audit.loc[audit["sequence"].eq(sequence)].merge(
            keys, on=["start_frame_index", "end_frame_index"], how="inner", validate="one_to_one",
        ).sort_values("start_frame_index").reset_index(drop=True)
        if len(pairs) != 30:
            raise RuntimeError(f"{sequence}: expected 30 Raw-locked pairs, found {len(pairs)}")
        frame_indices = sorted(set(pairs["start_frame_index"].astype(int)) | set(pairs["end_frame_index"].astype(int)))
        base_centers = np.asarray(specification["centers"], dtype=float)
        raw_dir = Path(PROJECT_ROOT / specification["raw_dir"])
        model_dir = RECON_ROOT / SEQUENCE_MAP[sequence]
        magnification = specification["magnification"]
        pitch = float(specification["pitch_px"])
        radius = float(specification["radius_px"])
        scale = float(specification["object_um_per_px"])
        expected_dx_px = float(specification["expected_signed_dx_px"])
        patch_half = int(np.ceil(0.46 * pitch))
        sample_count = 64 if magnification == "20x" else 96
        acm_iterations = 13 if magnification == "20x" else 15
        normal_half = 2.4 if magnification == "20x" else 4.0
        rows = []
        for frame_index in frame_indices:
            filename = f"frame_{frame_index:04d}.bmp"
            raw = module.load_grayscale(raw_dir / filename)
            model_image = module.load_grayscale(model_dir / filename)
            predicted = module.session_prediction(sequence, frame_index, base_centers, expected_dx_px)
            margin = int(np.ceil(0.55 * pitch))
            x0 = max(0, int(np.floor(np.min(predicted[:, 1]))) - margin)
            x1 = min(raw.shape[1], int(np.ceil(np.max(predicted[:, 1]))) + margin + 1)
            y0 = max(0, int(np.floor(np.min(predicted[:, 2]))) - margin)
            y1 = min(raw.shape[0], int(np.ceil(np.max(predicted[:, 2]))) + margin + 1)
            image = model_image[y0:y1, x0:x1]
            for pillar_id, predicted_x, predicted_y in predicted:
                local_center = (float(predicted_x - x0), float(predicted_y - y0))
                patch, patch_center, patch_origin = module.crop_around(image, local_center, patch_half)
                reset_curvature_cycle()
                measurement = module.measure_inflection_lsc(
                    patch, patch_center, radius, sample_count=sample_count,
                    acm_iterations=acm_iterations, normal_half_width_px=normal_half,
                    polarity="dark",
                )
                if not determinism:
                    reset_curvature_cycle()
                    repeated = module.measure_inflection_lsc(
                        patch, patch_center, radius, sample_count=sample_count,
                        acm_iterations=acm_iterations, normal_half_width_px=normal_half,
                        polarity="dark",
                    )
                    determinism.extend([
                        abs(measurement.lsc.cx - repeated.lsc.cx),
                        abs(measurement.lsc.cy - repeated.lsc.cy),
                        abs(measurement.lsc.radius - repeated.lsc.radius),
                    ])
                rows.append({
                    "sequence": sequence,
                    "magnification": magnification,
                    "frame_index": frame_index,
                    "method": METHOD,
                    "pillar_id": int(pillar_id),
                    "lsc_center_x_px": measurement.lsc.cx + patch_origin[0] + x0,
                    "lsc_center_y_px": measurement.lsc.cy + patch_origin[1] + y0,
                    "lsc_radius_px": measurement.lsc.radius,
                    "gradient_strength_median": float(np.median(measurement.signed_gradient_strength)),
                    "object_um_per_px": scale,
                })
        centers = pd.DataFrame(rows)
        indexed = centers.set_index(["frame_index", "pillar_id"])
        pair_rows = []
        for pair_rank, pair in pairs.iterrows():
            start, end = int(pair["start_frame_index"]), int(pair["end_frame_index"])
            pillar_dx, pillar_dy = [], []
            for pillar_id in base_centers[:, 0].astype(int):
                before, after = indexed.loc[(start, pillar_id)], indexed.loc[(end, pillar_id)]
                pillar_dx.append((float(after["lsc_center_x_px"]) - float(before["lsc_center_x_px"])) * scale)
                pillar_dy.append((float(after["lsc_center_y_px"]) - float(before["lsc_center_y_px"])) * scale)
            aggregate_dx, aggregate_dy = float(np.median(pillar_dx)), float(np.median(pillar_dy))
            nominal = float(specification["nominal_step_um"])
            pair_rows.append({
                "sequence": sequence,
                "magnification": magnification,
                "pair_rank_raw_locked": pair_rank + 1,
                "start_frame_index": start,
                "end_frame_index": end,
                "method": METHOD,
                "nominal_step_um": nominal,
                "aggregate_dx_um": aggregate_dx,
                "aggregate_dy_um": aggregate_dy,
                "measured_step_um": abs(aggregate_dx),
                "nominal_abs_error_nm": abs(abs(aggregate_dx) - nominal) * 1000,
                "within_grid_sd_nm": float(np.std(pillar_dx, ddof=1) * 1000),
                "cross_axis_abs_nm": abs(aggregate_dy) * 1000,
            })
        center_tables.append(centers)
        pair_tables.append(pd.DataFrame(pair_rows))
        print(json.dumps({"sequence": sequence, "frames": len(frame_indices), "centers": len(centers), "pairs": len(pair_rows)}), flush=True)
    centers = pd.concat(center_tables, ignore_index=True)
    candidate_pairs = pd.concat(pair_tables, ignore_index=True)
    reference = pd.read_csv(REFERENCE_PAIRS)
    combined = pd.concat([reference, candidate_pairs], ignore_index=True)
    summary = module.summarize_pairs(combined)
    centers.to_csv(TABLES / "candidate_lsc_centers.csv", index=False, encoding="utf-8-sig")
    candidate_pairs.to_csv(TABLES / "candidate_lsc_per_pair.csv", index=False, encoding="utf-8-sig")
    combined.to_csv(TABLES / "combined_lsc_per_pair.csv", index=False, encoding="utf-8-sig")
    summary.to_csv(TABLES / "combined_lsc_summary.csv", index=False, encoding="utf-8-sig")
    all_scope = summary.loc[summary["scope"].eq("all_four_sequences")].set_index("method")
    metrics = ("step_sd_nm", "mean_nominal_abs_error_nm", "median_within_grid_sd_nm", "median_cross_axis_abs_nm")
    methods = ["Raw", "V42 E120", "R109 E48", METHOD]
    headline = {
        method: {metric: float(all_scope.loc[method, metric]) for metric in metrics}
        for method in methods
    }
    uncertainty = {
        baseline: bootstrap(
            reference.loc[reference.method.eq(baseline)], candidate_pairs,
        )
        for baseline in ("R109 E48", "V42 E120")
    }
    payload = {
        "status": "complete",
        "method": "corrected deterministic ACM-inflection-LSC",
        "selection": "current Chapter 6.2 Raw-locked top30",
        "candidate_pair_rows": len(candidate_pairs),
        "combined_pair_rows": len(combined),
        "determinism_spot_check_max_px": float(max(determinism)),
        "headline": headline,
        "paired_sequence_stratified_bootstrap": uncertainty,
        "claim_boundary": "Commanded displacement is nominal rather than independent stage truth; compare stability and consistency, not absolute accuracy."
    }
    (OUTPUT / "summary.json").write_text(json.dumps(payload, indent=2, allow_nan=False), encoding="utf-8")
    if len(candidate_pairs) != 120 or len(combined) != 600 or max(determinism) != 0:
        raise RuntimeError(f"LSC validation failed: {payload}")
    print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

import analyze_shift_safe_50x_cd_alternatives as common


EVALUATION_ROOT = Path(
    r"D:\GMM_2_Final\Experiments\R63_CausalBoundaryMotionAblation\results\evaluation"
)
SEQUENCE_CONFIG = Path(
    r"D:\GMM_2_Final\Thesis_MOSR_Evidence\Final_Data_Figures"
    r"\01_CURRENT_THESIS_RESULTS_V42_CENTER9\config\sequence_center9_50x20x.json"
)
FIXED_20X_MANIFEST = Path(
    r"D:\GMM_2_Final\Thesis_MOSR_Evidence\Final_Data_Figures"
    r"\04_V42_NEURAL_NETWORK_RESULTS\source_validation\wiener_baseline_20260715"
    r"\supplementary_20x_cd\manifest.json"
)
OUTPUT_ROOT = Path(
    r"D:\GMM_2_Final\Thesis_MOSR_Evidence\Final_Data_Figures"
    r"\12_V25_20X_CD_PRESENTATION_CANDIDATE_20260727"
)
VARIANTS = common.VARIANTS
SEEDS = common.SEEDS
OBJECT_UM_PER_PX = 0.1725


def load_20x_geometry() -> tuple[pd.DataFrame, np.ndarray, np.ndarray, float, Path]:
    sem = pd.read_csv(common.SEM_TABLE)
    config = json.loads(SEQUENCE_CONFIG.read_text(encoding="utf-8"))["sequences"][
        "20x_1um"
    ]
    fixed = json.loads(FIXED_20X_MANIFEST.read_text(encoding="utf-8"))
    pillar_ids = np.asarray([int(row[0]) for row in config["centers"]], dtype=int)
    centers = np.asarray([[row[1], row[2]] for row in config["centers"]], dtype=float)
    centers[:, 0] += float(fixed["cumulative_raw_dx_px"])
    centers += np.asarray(fixed["shared_center_shift_xy_px"], dtype=float)
    return sem, pillar_ids, centers, float(config["radius_px"]), Path(fixed["raw_image"])


def load_locked_threshold_scores() -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for variant in VARIANTS:
        for seed in SEEDS:
            path = (
                EVALUATION_ROOT
                / "metrics"
                / variant
                / f"seed{seed}"
                / "static_cd"
                / "static_cd_per_measurement.csv"
            )
            data = pd.read_csv(path)
            data = data.loc[
                data["magnification"].eq("20x")
                & data["method"].eq("Method")
                & data["status"].eq("ok")
            ]
            per_pillar = data.groupby("pillar_id")["abs_error_nm"].median()
            rows.append(
                {
                    "variant": variant,
                    "seed": seed,
                    "locked_cd_median_abs_error_nm": float(per_pillar.median()),
                }
            )
    return pd.DataFrame(rows)


def load_raw_locked_threshold_score() -> float:
    path = (
        EVALUATION_ROOT
        / "metrics"
        / VARIANTS[0]
        / f"seed{SEEDS[0]}"
        / "static_cd"
        / "static_cd_per_measurement.csv"
    )
    data = pd.read_csv(path)
    data = data.loc[
        data["magnification"].eq("20x")
        & data["method"].eq("Raw")
        & data["status"].eq("ok")
    ]
    return float(data.groupby("pillar_id")["abs_error_nm"].median().median())


def measure_gradient_cd() -> pd.DataFrame:
    sem, pillar_ids, centers, reference_radius_px, raw_path = load_20x_geometry()
    sem_by_id = sem.set_index("sem_index")["sem_diameter_um"].to_dict()
    common.OBJECT_UM_PER_PX = OBJECT_UM_PER_PX
    rows: list[dict[str, object]] = []
    for variant in VARIANTS:
        for seed in SEEDS:
            image_path = (
                EVALUATION_ROOT
                / "reconstructions"
                / variant
                / f"seed{seed}"
                / "20x_1um"
                / raw_path.name
            )
            if not image_path.is_file():
                raise FileNotFoundError(image_path)
            image = common.read_gray(image_path)
            for sigma_px in (0.75, 1.0, 1.5):
                seed_rows: list[dict[str, object]] = []
                for pillar_id, (center_x, center_y) in zip(pillar_ids, centers):
                    radii, darkness = common.radial_samples(
                        image,
                        float(center_x),
                        float(center_y),
                        reference_radius_px,
                    )
                    edge_radius = common.radial_gradient_radius(
                        radii, darkness, reference_radius_px, sigma_px
                    )
                    diameter_um = 2.0 * edge_radius * OBJECT_UM_PER_PX
                    sem_diameter_um = float(sem_by_id[int(pillar_id)])
                    seed_rows.append(
                        {
                            "variant": variant,
                            "seed": seed,
                            "sigma_px": sigma_px,
                            "pillar_id": int(pillar_id),
                            "sem_diameter_um": sem_diameter_um,
                            "gradient_diameter_um": diameter_um,
                            "uncorrected_signed_error_nm": (
                                diameter_um - sem_diameter_um
                            )
                            * 1000.0,
                            "angular_edge_mad_nm": common.angular_edge_mad_nm(
                                radii,
                                darkness,
                                reference_radius_px,
                                sigma_px,
                            ),
                        }
                    )
                seed_table = pd.DataFrame(seed_rows).set_index("pillar_id")
                seed_table["loocv_corrected_error_nm"] = common.leave_one_pillar_out(
                    seed_table["uncorrected_signed_error_nm"]
                )
                rows.extend(seed_table.reset_index().to_dict("records"))
    return pd.DataFrame(rows)


def main() -> None:
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    locked = load_locked_threshold_scores()
    gradient = measure_gradient_cd()
    summary = common.summarize_gradient(gradient)
    locked.to_csv(OUTPUT_ROOT / "locked_threshold_20x_cd.csv", index=False)
    gradient.to_csv(OUTPUT_ROOT / "gradient_20x_cd_per_pillar.csv", index=False)
    summary.to_csv(OUTPUT_ROOT / "gradient_20x_cd_summary.csv", index=False)

    locked_means = locked.groupby("variant")["locked_cd_median_abs_error_nm"].mean()
    sigma_one = summary.loc[summary["sigma_px"].eq(1.0)]
    sigma_one_means = sigma_one.groupby("variant").mean(numeric_only=True)
    raw_locked = load_raw_locked_threshold_score()

    pd.DataFrame(
        {
            "method": ["Raw", "Anti-aliased upsampling", "Standard upsampling"],
            "median_abs_error_nm": [
                raw_locked,
                locked_means[VARIANTS[0]],
                locked_means[VARIANTS[1]],
            ],
        }
    ).to_csv(OUTPUT_ROOT / "presentation_locked_cd.csv", index=False)

    presentation = pd.DataFrame(
        {
            "metric": ["Median absolute error", "RMSE", "Maximum absolute error"],
            "shift_safe_nm": [
                sigma_one_means.loc[VARIANTS[0], "loocv_median_abs_error_nm"],
                sigma_one_means.loc[VARIANTS[0], "loocv_rmse_nm"],
                sigma_one_means.loc[VARIANTS[0], "loocv_max_abs_error_nm"],
            ],
            "standard_nm": [
                sigma_one_means.loc[VARIANTS[1], "loocv_median_abs_error_nm"],
                sigma_one_means.loc[VARIANTS[1], "loocv_rmse_nm"],
                sigma_one_means.loc[VARIANTS[1], "loocv_max_abs_error_nm"],
            ],
        }
    )
    presentation.to_csv(OUTPUT_ROOT / "presentation_bias_corrected_cd.csv", index=False)

    sensitivity = (
        summary.pivot_table(
            index="sigma_px", columns="variant", values="loocv_rmse_nm", aggfunc="mean"
        )
        .reset_index()
        .rename(
            columns={
                VARIANTS[0]: "shift_safe_rmse_nm",
                VARIANTS[1]: "standard_rmse_nm",
            }
        )
    )
    sensitivity.to_csv(OUTPUT_ROOT / "presentation_smoothing_sensitivity.csv", index=False)

    metadata = {
        "magnification": "20x",
        "object_um_per_px": OBJECT_UM_PER_PX,
        "source_frame": "20x 1.0 um sequence, frame 49",
        "edge_rule": "radial maximum gradient",
        "central_smoothing_sigma_px": 1.0,
        "bias_rule": (
            "Each held-out pillar is corrected only by the median signed bias "
            "estimated from the other eight pillars."
        ),
        "presentation_metrics": presentation.to_dict("records"),
    }
    (OUTPUT_ROOT / "analysis_metadata.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(metadata, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

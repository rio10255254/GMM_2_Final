from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
from PIL import Image


EVALUATION_ROOT = Path(
    r"D:\GMM_2_Final\Experiments\R63_CausalBoundaryMotionAblation\results\evaluation"
)
SEM_TABLE = Path(
    r"D:\GMM_2_Final\Thesis_MOSR_Evidence\Final_Data_Figures"
    r"\01_CURRENT_THESIS_RESULTS_V42_CENTER9\cd\tables\center9_cd_per_pillar.csv"
)
OUTPUT_ROOT = Path(
    r"D:\GMM_2_Final\Thesis_MOSR_Evidence\Final_Data_Figures"
    r"\10_V23_50X_CD_PRESENTATION_CANDIDATES_20260727"
)
VARIANTS = ("shift_safe_matched", "standard_upsample_matched")
SEEDS = (1261200, 1261217)
OBJECT_UM_PER_PX = 0.069
RADIAL_STEP_PX = 0.03
RADIAL_ANGLES = 720


def read_gray(path: Path) -> np.ndarray:
    with Image.open(path) as image:
        return np.asarray(image.convert("L"), dtype=np.float64)


def bilinear(image: np.ndarray, x: np.ndarray, y: np.ndarray) -> np.ndarray:
    height, width = image.shape
    x = np.clip(x, 0, width - 1.001)
    y = np.clip(y, 0, height - 1.001)
    x0 = np.floor(x).astype(int)
    y0 = np.floor(y).astype(int)
    x1 = x0 + 1
    y1 = y0 + 1
    dx = x - x0
    dy = y - y0
    return (
        image[y0, x0] * (1.0 - dx) * (1.0 - dy)
        + image[y0, x1] * dx * (1.0 - dy)
        + image[y1, x0] * (1.0 - dx) * dy
        + image[y1, x1] * dx * dy
    )


def gaussian_smooth(profile: np.ndarray, sigma_samples: float) -> np.ndarray:
    radius = max(1, int(np.ceil(4.0 * sigma_samples)))
    coordinate = np.arange(-radius, radius + 1)
    kernel = np.exp(-0.5 * np.square(coordinate / sigma_samples))
    kernel /= kernel.sum()
    padded = np.pad(profile, radius, mode="edge")
    return np.convolve(padded, kernel, mode="same")[radius:-radius]


def radial_samples(
    image: np.ndarray,
    center_x: float,
    center_y: float,
    reference_radius_px: float,
    angle_count: int = RADIAL_ANGLES,
) -> tuple[np.ndarray, np.ndarray]:
    radii = np.arange(
        0.0, reference_radius_px * 2.2 + RADIAL_STEP_PX * 0.5, RADIAL_STEP_PX
    )
    angles = np.linspace(0.0, 2.0 * np.pi, angle_count, endpoint=False)
    xx = center_x + np.outer(np.cos(angles), radii)
    yy = center_y + np.outer(np.sin(angles), radii)
    darkness = 1.0 - bilinear(image, xx, yy) / 255.0
    return radii, darkness


def quadratic_minimum(x: np.ndarray, y: np.ndarray, index: int) -> float:
    if index <= 0 or index >= len(x) - 1:
        return float(x[index])
    coefficients = np.polyfit(x[index - 1 : index + 2], y[index - 1 : index + 2], 2)
    if coefficients[0] <= 0:
        return float(x[index])
    location = -coefficients[1] / (2.0 * coefficients[0])
    if x[index - 1] <= location <= x[index + 1]:
        return float(location)
    return float(x[index])


def radial_gradient_radius(
    radii: np.ndarray,
    darkness: np.ndarray,
    reference_radius_px: float,
    sigma_px: float,
) -> float:
    profile = darkness.mean(axis=0)
    smoothed = gaussian_smooth(profile, sigma_px / RADIAL_STEP_PX)
    gradient = np.gradient(smoothed, radii)
    search = (radii >= reference_radius_px * 0.65) & (
        radii <= reference_radius_px * 1.4
    )
    search_radii = radii[search]
    search_gradient = gradient[search]
    index = int(np.argmin(search_gradient))
    return quadratic_minimum(search_radii, search_gradient, index)


def angular_edge_mad_nm(
    radii: np.ndarray,
    darkness: np.ndarray,
    reference_radius_px: float,
    sigma_px: float,
) -> float:
    sigma_samples = sigma_px / RADIAL_STEP_PX
    edge_radii = []
    search = (radii >= reference_radius_px * 0.65) & (
        radii <= reference_radius_px * 1.4
    )
    search_radii = radii[search]
    for profile in darkness[::4]:
        smoothed = gaussian_smooth(profile, sigma_samples)
        gradient = np.gradient(smoothed, radii)[search]
        index = int(np.argmin(gradient))
        edge_radii.append(quadratic_minimum(search_radii, gradient, index))
    edge_radii = np.asarray(edge_radii)
    radius_mad = np.median(np.abs(edge_radii - np.median(edge_radii)))
    return float(2.0 * radius_mad * OBJECT_UM_PER_PX * 1000.0)


def leave_one_pillar_out(errors: pd.Series) -> pd.Series:
    corrected = {}
    for pillar_id, error in errors.items():
        correction = float(errors.drop(pillar_id).median())
        corrected[pillar_id] = float(error - correction)
    return pd.Series(corrected, name="loocv_corrected_error_nm")


def load_locked_threshold_scores() -> pd.DataFrame:
    rows = []
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
                data["magnification"].eq("50x")
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
        data["magnification"].eq("50x")
        & data["method"].eq("Raw")
        & data["status"].eq("ok")
    ]
    return float(data.groupby("pillar_id")["abs_error_nm"].median().median())


def measure_gradient_cd() -> pd.DataFrame:
    sem = pd.read_csv(SEM_TABLE)
    reference_radius_px = float(sem["reference_radius_px"].median())
    rows = []
    for variant in VARIANTS:
        for seed in SEEDS:
            recon_dir = (
                EVALUATION_ROOT
                / "reconstructions"
                / variant
                / f"seed{seed}"
                / "static_50x_sem"
            )
            images = list(recon_dir.glob("*.bmp"))
            assert len(images) == 1, recon_dir
            image = read_gray(images[0])
            for sigma_px in (0.75, 1.0, 1.5):
                seed_rows = []
                for pillar in sem.itertuples():
                    radii, darkness = radial_samples(
                        image,
                        float(pillar.raw_x_px),
                        float(pillar.raw_y_px),
                        reference_radius_px,
                    )
                    edge_radius = radial_gradient_radius(
                        radii, darkness, reference_radius_px, sigma_px
                    )
                    diameter_um = 2.0 * edge_radius * OBJECT_UM_PER_PX
                    signed_error_nm = (
                        diameter_um - float(pillar.sem_diameter_um)
                    ) * 1000.0
                    seed_rows.append(
                        {
                            "variant": variant,
                            "seed": seed,
                            "sigma_px": sigma_px,
                            "pillar_id": int(pillar.sem_index),
                            "sem_diameter_um": float(pillar.sem_diameter_um),
                            "gradient_diameter_um": diameter_um,
                            "uncorrected_signed_error_nm": signed_error_nm,
                            "angular_edge_mad_nm": angular_edge_mad_nm(
                                radii,
                                darkness,
                                reference_radius_px,
                                sigma_px,
                            ),
                        }
                    )
                seed_table = pd.DataFrame(seed_rows).set_index("pillar_id")
                corrected = leave_one_pillar_out(
                    seed_table["uncorrected_signed_error_nm"]
                )
                seed_table["loocv_corrected_error_nm"] = corrected
                rows.extend(seed_table.reset_index().to_dict("records"))
    return pd.DataFrame(rows)


def summarize_gradient(data: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for (variant, sigma_px, seed), group in data.groupby(
        ["variant", "sigma_px", "seed"]
    ):
        corrected = group["loocv_corrected_error_nm"].to_numpy(float)
        rows.append(
            {
                "variant": variant,
                "sigma_px": sigma_px,
                "seed": seed,
                "uncorrected_median_abs_error_nm": float(
                    group["uncorrected_signed_error_nm"].abs().median()
                ),
                "global_signed_bias_nm": float(
                    group["uncorrected_signed_error_nm"].median()
                ),
                "loocv_median_abs_error_nm": float(np.median(np.abs(corrected))),
                "loocv_mean_abs_error_nm": float(np.mean(np.abs(corrected))),
                "loocv_rmse_nm": float(np.sqrt(np.mean(np.square(corrected)))),
                "loocv_max_abs_error_nm": float(np.max(np.abs(corrected))),
                "median_angular_edge_mad_nm": float(
                    group["angular_edge_mad_nm"].median()
                ),
            }
        )
    return pd.DataFrame(rows)


def main() -> None:
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    locked = load_locked_threshold_scores()
    gradient = measure_gradient_cd()
    summary = summarize_gradient(gradient)
    locked.to_csv(OUTPUT_ROOT / "locked_threshold_50x_cd.csv", index=False)
    gradient.to_csv(OUTPUT_ROOT / "gradient_50x_cd_per_pillar.csv", index=False)
    summary.to_csv(OUTPUT_ROOT / "gradient_50x_cd_summary.csv", index=False)

    locked_means = locked.groupby("variant")[
        "locked_cd_median_abs_error_nm"
    ].mean()
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
    pd.DataFrame(
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
    ).to_csv(OUTPUT_ROOT / "presentation_bias_corrected_cd.csv", index=False)
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
    comparison = {
        "locked_common_threshold_protocol": {
            "shift_safe_nm": float(locked_means[VARIANTS[0]]),
            "standard_nm": float(locked_means[VARIANTS[1]]),
            "shift_safe_minus_standard_nm": float(
                locked_means[VARIANTS[0]] - locked_means[VARIANTS[1]]
            ),
            "difference_in_50x_pixels": float(
                (locked_means[VARIANTS[0]] - locked_means[VARIANTS[1]])
                / (OBJECT_UM_PER_PX * 1000.0)
            ),
        },
        "radial_maximum_gradient_sigma_1px_with_loocv_bias_correction": {
            metric: {
                "shift_safe": float(sigma_one_means.loc[VARIANTS[0], metric]),
                "standard": float(sigma_one_means.loc[VARIANTS[1], metric]),
            }
            for metric in (
                "uncorrected_median_abs_error_nm",
                "global_signed_bias_nm",
                "loocv_median_abs_error_nm",
                "loocv_mean_abs_error_nm",
                "loocv_rmse_nm",
                "loocv_max_abs_error_nm",
                "median_angular_edge_mad_nm",
            )
        },
        "sensitivity_rule": (
            "The same maximum-gradient method is repeated at 0.75, 1.0, and 1.5 px "
            "smoothing. The 1.0 px result is the central prespecified readout, not the "
            "best post-hoc setting. Each held-out pillar is corrected only by the median "
            "signed bias estimated from the other eight pillars."
        ),
        "recommended_presentation": (
            "Keep the locked uncorrected CD result, but present it as a 2.811 nm (0.041 px) "
            "global-offset difference. Add the leave-one-pillar-out bias-corrected maximum-"
            "gradient result to show relative CD transfer after one scalar calibration. "
            "Do not replace the primary result with a single favorable threshold."
        ),
    }
    (OUTPUT_ROOT / "comparison_summary.json").write_text(
        json.dumps(comparison, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(comparison, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

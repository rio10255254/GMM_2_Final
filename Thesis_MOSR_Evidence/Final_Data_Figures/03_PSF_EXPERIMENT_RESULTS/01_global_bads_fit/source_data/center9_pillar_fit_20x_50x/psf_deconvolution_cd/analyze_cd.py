from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from scipy.io import loadmat
from scipy.ndimage import gaussian_filter1d, map_coordinates


FIGURE_ROOT = Path(
    r"D:\GMM_2_Final\Thesis_MOSR_Evidence\Final_Data_Figures"
    r"\03_PSF_EXPERIMENT_RESULTS\01_global_bads_fit\figures"
    r"\center9_pillar_fit_20x_50x"
)
FIT_ROOT = Path(r"D:\GMM_2_Final\PSF_Fitting\output\deconvolution_baseline_psf_20260715")
SOURCE_ROOT = Path(__file__).resolve().parent
TABLE_ROOT = (
    FIGURE_ROOT.parent.parent / "tables" / "center9_pillar_fit_20x_50x"
)

CONFIGS = {"20x": {}, "50x": {}}


@dataclass(frozen=True)
class CdMeasurement:
    cd_px: float
    angle_median_px: float
    angle_mad_px: float
    core_level: float
    background_level: float
    threshold: float
    radii_px: np.ndarray
    edge_width_px: float
    ringing_ratio: float
    inverted_center: bool


def crossing_radius(profile: np.ndarray, radii: np.ndarray, threshold: float) -> float:
    smoothed = gaussian_filter1d(profile, sigma=6.0, mode="nearest")
    above = smoothed >= threshold
    crossings = np.flatnonzero((~above[:-1]) & above[1:])
    if crossings.size == 0:
        return float("nan")
    idx = int(crossings[0])
    y0, y1 = smoothed[idx], smoothed[idx + 1]
    if y1 == y0:
        return float(radii[idx])
    fraction = (threshold - y0) / (y1 - y0)
    return float(radii[idx] + fraction * (radii[idx + 1] - radii[idx]))


def measure_cd(
    image: np.ndarray,
    center_xy: np.ndarray,
    pitch_px: float,
    contrast_fraction: float = 0.5,
) -> CdMeasurement:
    # The same half-contrast rule is used before and after deconvolution.
    radial_step = 0.05
    # Leave extra room beyond the background annulus so noisy 20x traces can
    # complete their 90% crossing without approaching the neighbouring pillar.
    radii = np.arange(0.0, 0.38 * pitch_px + radial_step, radial_step)
    angles = np.linspace(0.0, 2.0 * np.pi, 360, endpoint=False)
    cos_a = np.cos(angles)[:, None]
    sin_a = np.sin(angles)[:, None]
    x = center_xy[0] + cos_a * radii[None, :]
    y = center_xy[1] + sin_a * radii[None, :]
    samples = map_coordinates(image, [y, x], order=3, mode="reflect")

    core_mask = radii <= 0.07 * pitch_px
    background_mask = (radii >= 0.30 * pitch_px) & (radii <= 0.36 * pitch_px)
    core_level = float(np.median(samples[:, core_mask]))
    background_level = float(np.median(samples[:, background_mask]))
    threshold = core_level + contrast_fraction * (background_level - core_level)

    edge_radii_10 = np.array(
        [
            crossing_radius(
                profile,
                radii,
                core_level + 0.10 * (background_level - core_level),
            )
            for profile in samples
        ],
        dtype=float,
    )
    edge_radii = np.array(
        [crossing_radius(profile, radii, threshold) for profile in samples],
        dtype=float,
    )
    edge_radii_90 = np.array(
        [
            crossing_radius(
                profile,
                radii,
                core_level + 0.90 * (background_level - core_level),
            )
            for profile in samples
        ],
        dtype=float,
    )
    for name, values in (
        ("10%", edge_radii_10),
        ("50%", edge_radii),
        ("90%", edge_radii_90),
    ):
        if np.count_nonzero(np.isfinite(values)) < 324:
            raise RuntimeError(f"Fewer than 90% of angular traces crossed {name} contrast")

    # Pair opposite radii so that small centre offsets do not bias the diameter.
    paired_diameters = edge_radii[:180] + edge_radii[180:]
    paired_diameters = paired_diameters[np.isfinite(paired_diameters)]
    median_cd = float(np.median(paired_diameters))
    mad_cd = float(np.median(np.abs(paired_diameters - median_cd)))
    edge_widths = edge_radii_90 - edge_radii_10
    edge_widths = edge_widths[np.isfinite(edge_widths) & (edge_widths >= 0)]
    if edge_widths.size < 324:
        raise RuntimeError("Fewer than 90% of angular traces produced a valid 10-90 edge width")
    edge_width_px = float(np.median(edge_widths))

    median_profile = np.median(samples, axis=0)
    median_profile = gaussian_filter1d(median_profile, sigma=6.0, mode="nearest")
    normalized_profile = (median_profile - core_level) / max(
        background_level - core_level, np.finfo(float).eps
    )
    changes = np.diff(normalized_profile[radii <= 0.30 * pitch_px])
    outward_rise = float(np.sum(changes[changes > 0]))
    inward_dip = float(-np.sum(changes[changes < 0]))
    ringing_ratio = inward_dip / max(outward_rise, np.finfo(float).eps)
    return CdMeasurement(
        cd_px=median_cd,
        angle_median_px=median_cd,
        angle_mad_px=mad_cd,
        core_level=core_level,
        background_level=background_level,
        threshold=threshold,
        radii_px=edge_radii,
        edge_width_px=edge_width_px,
        ringing_ratio=ringing_ratio,
        inverted_center=bool(core_level >= background_level),
    )


def save_overlay(
    image: np.ndarray,
    centers: np.ndarray,
    measurements: list[CdMeasurement],
    path: Path,
    display_limits: tuple[float, float],
) -> None:
    lo, hi = display_limits
    fig, ax = plt.subplots(figsize=(5.2, 5.2), dpi=240)
    ax.imshow(image, cmap="gray", vmin=lo, vmax=hi, interpolation="nearest")
    angles = np.linspace(0.0, 2.0 * np.pi, 360, endpoint=False)
    for idx, (center, measurement) in enumerate(zip(centers, measurements), start=1):
        # Draw the actual angular half-contrast crossings used by the CD
        # measurement. This avoids implying that a visibly non-circular edge
        # was measured as a perfect circle.
        contour_x = center[0] + measurement.radii_px * np.cos(angles)
        contour_y = center[1] + measurement.radii_px * np.sin(angles)
        ax.plot(contour_x, contour_y, color="#E69F00", linewidth=1.35)
        ax.text(
            center[0],
            center[1],
            str(idx),
            color="white",
            fontsize=8,
            ha="center",
            va="center",
            weight="bold",
        )
    ax.set_xlim(-0.5, image.shape[1] - 0.5)
    ax.set_ylim(image.shape[0] - 0.5, -0.5)
    ax.axis("off")
    fig.subplots_adjust(left=0, right=1, bottom=0, top=1)
    fig.savefig(path, bbox_inches="tight", pad_inches=0)
    plt.close(fig)


def save_cd_comparison(rows: list[dict[str, float]], magnification: str, path: Path) -> None:
    ids = np.arange(1, 10)
    sem = np.array([row["sem_cd_nm"] for row in rows])
    raw = np.array([row["raw_cd_nm"] for row in rows])
    restored = np.array([row["deconvolved_cd_nm"] for row in rows])

    fig, ax = plt.subplots(figsize=(7.2, 4.3), dpi=240)
    ax.plot(ids, sem, color="#9A6B00", linewidth=1.6, marker="s", markersize=5, label="SEM")
    ax.scatter(ids, raw, facecolors="white", edgecolors="#5B6573", s=42, linewidth=1.4, label="Captured")
    ax.scatter(ids, restored, color="#3973B7", s=42, label="Deconvolved")
    ax.set_title(f"{magnification} pillar CD: captured and deconvolved vs SEM", loc="left", fontsize=12)
    ax.set_xlabel("Pillar position (image order, 1-9)")
    ax.set_ylabel("CD (nm)")
    ax.set_xticks(ids)
    ax.grid(axis="y", color="#D9DEE5", linewidth=0.7)
    ax.spines[["top", "right"]].set_visible(False)
    ax.legend(frameon=False, ncols=3, loc="upper left")
    fig.tight_layout()
    fig.savefig(path, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def save_error_summary(rows: list[dict[str, float]], magnification: str, path: Path) -> None:
    raw_mae = float(np.mean([row["raw_abs_error_nm"] for row in rows]))
    restored_mae = float(np.mean([row["deconvolved_abs_error_nm"] for row in rows]))
    values = [raw_mae, restored_mae]

    fig, ax = plt.subplots(figsize=(4.8, 4.1), dpi=240)
    bars = ax.bar(
        ["Captured", "Deconvolved"],
        values,
        color=["#D9DEE5", "#3973B7"],
        edgecolor=["#5B6573", "#244D7B"],
        linewidth=1.0,
        width=0.62,
    )
    for bar, value in zip(bars, values):
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            value,
            f"{value:.1f}",
            ha="center",
            va="bottom",
            fontsize=10,
        )
    ax.set_title(f"{magnification} mean absolute CD error", loc="left", fontsize=12)
    ax.set_ylabel("Absolute error vs SEM (nm)")
    ax.set_ylim(0, max(values) * 1.22 if max(values) > 0 else 1)
    ax.grid(axis="y", color="#D9DEE5", linewidth=0.7)
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    fig.savefig(path, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def save_edge_width_summary(rows: list[dict[str, float]], magnification: str, path: Path) -> None:
    raw_width = float(np.mean([row["raw_edge_width_px"] for row in rows]))
    restored_width = float(np.mean([row["deconvolved_edge_width_px"] for row in rows]))
    values = [raw_width, restored_width]

    fig, ax = plt.subplots(figsize=(4.8, 4.1), dpi=240)
    bars = ax.bar(
        ["Captured", "Deconvolved"],
        values,
        color=["#D9DEE5", "#3973B7"],
        edgecolor=["#5B6573", "#244D7B"],
        linewidth=1.0,
        width=0.62,
    )
    for bar, value in zip(bars, values):
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            value,
            f"{value:.2f}",
            ha="center",
            va="bottom",
            fontsize=10,
        )
    ax.set_title(f"{magnification} mean 10-90% edge width", loc="left", fontsize=12)
    ax.set_ylabel("Edge-transition width (pixels; lower is sharper)")
    ax.set_ylim(0, max(values) * 1.22 if max(values) > 0 else 1)
    ax.grid(axis="y", color="#D9DEE5", linewidth=0.7)
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    fig.savefig(path, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def summarize(
    rows: list[dict[str, float]],
    calibrated_common_nsr: float,
    noise_nsr: float,
    label: str,
) -> dict[str, float | str | int | bool]:
    sem = np.array([row["sem_cd_nm"] for row in rows])
    raw = np.array([row["raw_cd_nm"] for row in rows])
    restored = np.array([row["deconvolved_cd_nm"] for row in rows])
    raw_error = raw - sem
    restored_error = restored - sem
    raw_mae = float(np.mean(np.abs(raw_error)))
    restored_mae = float(np.mean(np.abs(restored_error)))
    raw_edge_width = float(np.mean([row["raw_edge_width_px"] for row in rows]))
    restored_edge_width = float(
        np.mean([row["deconvolved_edge_width_px"] for row in rows])
    )
    return {
        "magnification": label,
        "n_pillars": 9,
        "noise_estimated_nsr": noise_nsr,
        "calibrated_common_nsr": calibrated_common_nsr,
        "raw_mean_edge_width_px": raw_edge_width,
        "deconvolved_mean_edge_width_px": restored_edge_width,
        "edge_width_change_px": restored_edge_width - raw_edge_width,
        "edge_width_change_percent": 100.0
        * (restored_edge_width / raw_edge_width - 1.0),
        "raw_max_ringing_ratio": float(max(row["raw_ringing_ratio"] for row in rows)),
        "deconvolved_max_ringing_ratio": float(
            max(row["deconvolved_ringing_ratio"] for row in rows)
        ),
        "raw_inverted_centers": int(
            sum(bool(row["raw_inverted_center"]) for row in rows)
        ),
        "deconvolved_inverted_centers": int(
            sum(bool(row["deconvolved_inverted_center"]) for row in rows)
        ),
        "raw_mean_cd_nm": float(np.mean(raw)),
        "deconvolved_mean_cd_nm": float(np.mean(restored)),
        "sem_mean_cd_nm": float(np.mean(sem)),
        "raw_bias_nm": float(np.mean(raw_error)),
        "deconvolved_bias_nm": float(np.mean(restored_error)),
        "raw_mae_nm": raw_mae,
        "deconvolved_mae_nm": restored_mae,
        "raw_median_abs_error_nm": float(np.median(np.abs(raw_error))),
        "deconvolved_median_abs_error_nm": float(np.median(np.abs(restored_error))),
        "raw_rmse_nm": float(np.sqrt(np.mean(raw_error**2))),
        "deconvolved_rmse_nm": float(np.sqrt(np.mean(restored_error**2))),
        "pillars_improved": int(np.count_nonzero(np.abs(restored_error) < np.abs(raw_error))),
        "mae_improved": bool(restored_mae < raw_mae),
        "mae_change_nm": float(restored_mae - raw_mae),
        "mae_change_percent": float(100.0 * (restored_mae - raw_mae) / raw_mae),
    }


def write_csv(path: Path, rows: list[dict]) -> None:
    if not rows:
        raise ValueError("No rows to write")
    for row in rows:
        for key, value in row.items():
            if isinstance(value, (float, np.floating)) and not np.isfinite(value):
                raise ValueError(f"Non-finite value for {key} in {path}: {value}")
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    TABLE_ROOT.mkdir(parents=True, exist_ok=True)
    all_rows: list[dict] = []
    summaries: list[dict] = []
    sensitivity_rows: list[dict] = []

    for label, cfg in CONFIGS.items():
        result = loadmat(SOURCE_ROOT / f"{label}_wiener_deconvolution.mat")
        raw = np.asarray(result["I"], dtype=float)
        restored = np.asarray(result["restored"], dtype=float)
        nsr = float(np.asarray(result["nsr"]).squeeze())
        noise_nsr = float(np.asarray(result["noise_nsr"]).squeeze())
        calibrated_common_nsr = float(
            np.asarray(result["calibrated_common_nsr"]).squeeze()
        )
        if not np.isclose(nsr, calibrated_common_nsr) or not np.isclose(nsr, 0.05):
            raise RuntimeError(f"{label} did not use the fixed NSR 0.05")
        with (FIT_ROOT / label / "selected_frame.json").open(encoding="utf-8") as handle:
            meta = json.load(handle)

        centers = np.asarray(result["centers_xy"], dtype=float)
        sem_radius = np.asarray(
            meta["image_oriented_sem_radius_nm"], dtype=float
        ).reshape(-1)
        sem_cd = np.asarray(meta["image_oriented_sem_cd_nm"], dtype=float).reshape(-1)
        if not np.allclose(sem_cd, 2.0 * sem_radius, rtol=0.0, atol=1e-9):
            raise RuntimeError(f"{label} SEM diameters are not twice the fitted radii")
        pitch_px = float(meta["pitch_px"])
        nm_per_px = float(meta["object_pixel_um"]) * 1000.0

        raw_measurements = [measure_cd(raw, center, pitch_px) for center in centers]
        restored_measurements = [measure_cd(restored, center, pitch_px) for center in centers]

        rows: list[dict] = []
        for idx, (radius, sem, raw_m, restored_m) in enumerate(
            zip(sem_radius, sem_cd, raw_measurements, restored_measurements), start=1
        ):
            raw_nm = raw_m.cd_px * nm_per_px
            restored_nm = restored_m.cd_px * nm_per_px
            row = {
                "magnification": label,
                "pillar_image_index": idx,
                "image_row": (idx - 1) // 3 + 1,
                "image_column": (idx - 1) % 3 + 1,
                "sem_radius_nm": float(radius),
                "sem_cd_nm": float(sem),
                "raw_cd_nm": float(raw_nm),
                "deconvolved_cd_nm": float(restored_nm),
                "raw_error_nm": float(raw_nm - sem),
                "deconvolved_error_nm": float(restored_nm - sem),
                "raw_abs_error_nm": float(abs(raw_nm - sem)),
                "deconvolved_abs_error_nm": float(abs(restored_nm - sem)),
                "raw_angular_mad_nm": float(raw_m.angle_mad_px * nm_per_px),
                "deconvolved_angular_mad_nm": float(restored_m.angle_mad_px * nm_per_px),
                "raw_edge_width_px": raw_m.edge_width_px,
                "deconvolved_edge_width_px": restored_m.edge_width_px,
                "edge_width_change_percent": float(
                    100.0 * (restored_m.edge_width_px / raw_m.edge_width_px - 1.0)
                ),
                "raw_ringing_ratio": raw_m.ringing_ratio,
                "deconvolved_ringing_ratio": restored_m.ringing_ratio,
                "raw_inverted_center": raw_m.inverted_center,
                "deconvolved_inverted_center": restored_m.inverted_center,
                "error_improved": bool(abs(restored_nm - sem) < abs(raw_nm - sem)),
            }
            rows.append(row)
            all_rows.append(row)

        out_dir = FIGURE_ROOT / label
        display_limits = tuple(
            float(value)
            for value in np.percentile(
                np.concatenate((raw.ravel(), restored.ravel())), [0.5, 99.5]
            )
        )
        save_overlay(
            raw,
            centers,
            raw_measurements,
            out_dir / "10_cd_measurement_overlay_captured.png",
            display_limits,
        )
        save_overlay(
            restored,
            centers,
            restored_measurements,
            out_dir / "11_cd_measurement_overlay_deconvolved.png",
            display_limits,
        )
        save_cd_comparison(rows, label, out_dir / "12_cd_before_after_vs_sem.png")
        save_error_summary(rows, label, out_dir / "13_cd_error_before_after.png")
        save_edge_width_summary(rows, label, out_dir / "14_edge_width_before_after.png")
        summaries.append(summarize(rows, calibrated_common_nsr, noise_nsr, label))

        for contrast_fraction in (0.4, 0.5, 0.6):
            raw_sensitivity = np.array(
                [
                    measure_cd(raw, center, pitch_px, contrast_fraction).cd_px * nm_per_px
                    for center in centers
                ]
            )
            restored_sensitivity = np.array(
                [
                    measure_cd(restored, center, pitch_px, contrast_fraction).cd_px
                    * nm_per_px
                    for center in centers
                ]
            )
            raw_abs_error = np.abs(raw_sensitivity - sem_cd)
            restored_abs_error = np.abs(restored_sensitivity - sem_cd)
            sensitivity_rows.append(
                {
                    "magnification": label,
                    "contrast_fraction": contrast_fraction,
                    "raw_mae_nm": float(np.mean(raw_abs_error)),
                    "deconvolved_mae_nm": float(np.mean(restored_abs_error)),
                    "mae_change_nm": float(np.mean(restored_abs_error - raw_abs_error)),
                    "mae_change_percent": float(
                        100.0
                        * (np.mean(restored_abs_error) - np.mean(raw_abs_error))
                        / np.mean(raw_abs_error)
                    ),
                    "pillars_improved": int(
                        np.count_nonzero(restored_abs_error < raw_abs_error)
                    ),
                }
            )

    write_csv(TABLE_ROOT / "cd_before_after_per_pillar.csv", all_rows)
    write_csv(TABLE_ROOT / "cd_before_after_summary.csv", summaries)
    write_csv(TABLE_ROOT / "cd_threshold_sensitivity.csv", sensitivity_rows)
    with (SOURCE_ROOT / "analysis_manifest.json").open("w", encoding="utf-8") as handle:
        json.dump(
            {
                "method": "background-normalized Wiener deconvolution with fitted PSF and one fixed scalar NSR",
                "sem_source": r"D:\GMM_2_Final\Thesis_MOSR_Evidence\20260618_100MG\SEM_data\via_pilar.xlsx, SEM data!J8:L10",
                "sem_conversion": "SEM CD = 2 x fitted SEM radius",
                "cd_rule": "median opposite-angle half-contrast diameter, identical before and after",
                "edge_rule": "median angular 10-90% transition width; lower is sharper",
                "ringing_rule": "inward-dip magnitude divided by outward-rise magnitude on median radial profile",
                "nsr_rule": "fixed NSR 0.05 for both magnifications; selected on held-out calibration imagery without using CD results",
                "nsr_validation": r"D:\GMM_2_Final\Thesis_MOSR_Evidence\Final_Data_Figures\04_V42_NEURAL_NETWORK_RESULTS\tables\wiener_nsr_calibration_sweep.csv",
                "overlay_boundary_rule": "orange contour is the actual 360-angle half-contrast crossing used for CD measurement",
                "overlay_display_rule": "captured and deconvolved overlays share the combined 0.5-99.5 percentile grayscale range within each magnification; display only",
                "sem_usage": "The known SEM diameter is reused as a consistency reference after deconvolution; it does not select the fixed NSR",
                "threshold_sensitivity": sensitivity_rows,
                "summary": summaries,
            },
            handle,
            ensure_ascii=False,
            indent=2,
        )

    for summary in summaries:
        print(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    main()

from __future__ import annotations

import json
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.patches import Circle as PlotCircle
from scipy.io import loadmat
from scipy.stats import iqr, wilcoxon


SCRIPT_DIR = Path(__file__).resolve().parent
PACKAGE = SCRIPT_DIR.parent
RESULTS = PACKAGE / "results"
TABLES = RESULTS / "tables"
FIGURES = RESULTS / "figures"
QA = RESULTS / "qa"
for directory in (TABLES, FIGURES, QA):
    directory.mkdir(parents=True, exist_ok=True)

sys.path.insert(0, str(SCRIPT_DIR))
from reference_circle_core import (  # noqa: E402
    measure_boundary_and_circles,
    summarize_reference_circles,
)
PROJECT_ROOT = Path(__file__).resolve().parents[3]


SOURCE_MAT = Path(
    str(PROJECT_ROOT / 'Experiments/R70_V42ACMContourSEMValidation/results/masks/acm_primary_masks.mat')
)


plt.rcParams["font.sans-serif"] = ["Microsoft JhengHei", "Microsoft YaHei", "DejaVu Sans"]
plt.rcParams["axes.unicode_minus"] = False

COLORS = {"Raw": "#555555", "MOSR": "#2878B5", "SEM": "#111111"}


def mask_center_radius(mask: np.ndarray) -> tuple[tuple[float, float], float]:
    yy, xx = np.nonzero(mask)
    if len(xx) < 8:
        raise ValueError("mask is empty")
    center = (float(np.mean(xx)), float(np.mean(yy)))
    radius = float(np.sqrt(len(xx) / np.pi))
    return center, radius


def radial_signature(measurement, samples: int = 720) -> np.ndarray:
    circle = measurement.circles.lsc
    points = measurement.inflection_points_xy
    delta = points - np.array([circle.cx, circle.cy])
    angle = np.mod(np.arctan2(delta[:, 1], delta[:, 0]), 2.0 * np.pi)
    radius = np.linalg.norm(delta, axis=1)
    order = np.argsort(angle)
    angle = angle[order]
    radius = radius[order]
    angle = np.concatenate([angle[-1:] - 2.0 * np.pi, angle, angle[:1] + 2.0 * np.pi])
    radius = np.concatenate([radius[-1:], radius, radius[:1]])
    targets = np.linspace(0.0, 2.0 * np.pi, samples, endpoint=False)
    return np.interp(targets, angle, radius)


def analyze() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, dict, dict]:
    data = loadmat(SOURCE_MAT, squeeze_me=True, struct_as_record=False)
    exposures = np.asarray(data["exposures"], dtype=int).reshape(-1)
    opt_pitch = float(data["opt_pitch"])
    scale_um_per_px = 5.0 / opt_pitch
    global_index = np.asarray(data["global_index"], dtype=int)
    flagged = {int(value) for value in np.asarray(data["sem_edge_cleanup_ids"]).reshape(-1)}

    truth_cells = np.asarray(data["truth_cells"])
    truth_masks = np.asarray(data["truth_masks"], dtype=bool)
    raw_cells = np.asarray(data["raw_cells"])
    raw_masks = np.asarray(data["raw_masks"], dtype=bool)
    mosr_cells = np.asarray(data["recon_cells"])
    mosr_masks = np.asarray(data["recon_masks"], dtype=bool)

    truth_measurements: dict[int, object] = {}
    truth_rows: list[dict[str, object]] = []
    for pillar_zero in range(36):
        pillar = pillar_zero + 1
        mask = truth_masks[:, :, pillar_zero]
        center, radius = mask_center_radius(mask)
        measurement = measure_boundary_and_circles(
            truth_cells[:, :, pillar_zero],
            center,
            radius,
            coarse_mask=mask,
            sample_count=180,
            normal_half_width_px=3.0,
            polarity="auto",
        )
        truth_measurements[pillar] = measurement
        location = np.argwhere(global_index == pillar)
        if location.shape != (1, 2):
            raise ValueError(f"global index {pillar} is not unique")
        row_index, column_index = location[0] + 1
        metrics = summarize_reference_circles(measurement, scale_um_per_px=scale_um_per_px)
        truth_rows.append(
            {
                "pillar_id": pillar,
                "grid_row": int(row_index),
                "grid_column": int(column_index),
                "field_group": ("inner" if max(abs(row_index - 3.5), abs(column_index - 3.5)) < 1 else "middle" if max(abs(row_index - 3.5), abs(column_index - 3.5)) < 2 else "outer"),
                "sem_edge_cleanup_flag": pillar in flagged,
                **metrics,
            }
        )
    truth_table = pd.DataFrame(truth_rows)

    rows: list[dict[str, object]] = []
    measurements: dict[tuple[str, int, int], object] = {}
    for method, cells, masks in (
        ("Raw", raw_cells, raw_masks),
        ("MOSR", mosr_cells, mosr_masks),
    ):
        for exposure_zero, exposure in enumerate(exposures):
            for pillar_zero in range(36):
                pillar = pillar_zero + 1
                mask = masks[:, :, pillar_zero, exposure_zero]
                center, radius = mask_center_radius(mask)
                measurement = measure_boundary_and_circles(
                    cells[:, :, pillar_zero, exposure_zero],
                    center,
                    radius,
                    coarse_mask=mask,
                    sample_count=144,
                    normal_half_width_px=3.0,
                    polarity="auto",
                )
                measurements[(method, int(exposure), pillar)] = measurement
                metrics = summarize_reference_circles(measurement, scale_um_per_px=scale_um_per_px)
                truth_measurement = truth_measurements[pillar]
                truth_metrics = truth_table.loc[truth_table["pillar_id"] == pillar].iloc[0]
                measured_signature = radial_signature(measurement)
                truth_signature = radial_signature(truth_measurement)
                radial_error = float(
                    np.mean(np.abs(measured_signature - truth_signature))
                    * scale_um_per_px
                    * 1000.0
                )
                centered_measured = measured_signature - np.mean(measured_signature)
                centered_truth = truth_signature - np.mean(truth_signature)
                contour_correlation = float(np.corrcoef(centered_measured, centered_truth)[0, 1])
                rows.append(
                    {
                        "method": method,
                        "exposure": int(exposure),
                        "pillar_id": pillar,
                        "grid_row": int(truth_metrics["grid_row"]),
                        "grid_column": int(truth_metrics["grid_column"]),
                        "field_group": truth_metrics["field_group"],
                        "sem_edge_cleanup_flag": bool(truth_metrics["sem_edge_cleanup_flag"]),
                        "effective_um_per_px": scale_um_per_px,
                        **metrics,
                        "sem_lsc_diameter_um": float(truth_metrics["lsc_diameter_um"]),
                        "sem_mzc_roundness_um": float(truth_metrics["mzc_roundness_um"]),
                        "sem_harmonic4_relative_pct": float(truth_metrics["harmonic4_relative_pct"]),
                        "lsc_signed_error_nm": (metrics["lsc_diameter_um"] - float(truth_metrics["lsc_diameter_um"])) * 1000.0,
                        "lsc_abs_error_nm": abs(metrics["lsc_diameter_um"] - float(truth_metrics["lsc_diameter_um"])) * 1000.0,
                        "mzc_roundness_abs_error_nm": abs(metrics["mzc_roundness_um"] - float(truth_metrics["mzc_roundness_um"])) * 1000.0,
                        "harmonic4_abs_error_pct": abs(metrics["harmonic4_relative_pct"] - float(truth_metrics["harmonic4_relative_pct"])),
                        "radial_shape_mae_nm": radial_error,
                        "contour_correlation": contour_correlation,
                    }
                )
    per_exposure = pd.DataFrame(rows)

    metric_columns = [
        "lsc_signed_error_nm",
        "lsc_abs_error_nm",
        "mzc_roundness_abs_error_nm",
        "harmonic4_abs_error_pct",
        "radial_shape_mae_nm",
        "contour_correlation",
        "lsc_diameter_um",
        "mzc_roundness_um",
        "harmonic4_relative_pct",
        "center_spread_um",
    ]
    per_pillar = (
        per_exposure.groupby(
            ["method", "pillar_id", "grid_row", "grid_column", "field_group", "sem_edge_cleanup_flag"],
            as_index=False,
        )[metric_columns]
        .median()
    )

    summaries: list[dict[str, object]] = []
    for method, group in per_pillar.groupby("method", sort=False):
        summaries.append(
            {
                "population": "all_36",
                "method": method,
                "n_pillars": len(group),
                "median_lsc_abs_error_nm": float(np.median(group["lsc_abs_error_nm"])),
                "iqr_lsc_abs_error_nm": float(iqr(group["lsc_abs_error_nm"])),
                "mean_lsc_abs_error_nm": float(np.mean(group["lsc_abs_error_nm"])),
                "sd_lsc_abs_error_nm": float(np.std(group["lsc_abs_error_nm"], ddof=1)),
                "median_radial_shape_mae_nm": float(np.median(group["radial_shape_mae_nm"])),
                "median_contour_correlation": float(np.median(group["contour_correlation"])),
                "median_mzc_roundness_abs_error_nm": float(np.median(group["mzc_roundness_abs_error_nm"])),
                "median_harmonic4_abs_error_pct": float(np.median(group["harmonic4_abs_error_pct"])),
            }
        )
        clean = group[~group["sem_edge_cleanup_flag"]]
        summaries.append(
            {
                "population": "exclude_preflagged_17_28",
                "method": method,
                "n_pillars": len(clean),
                "median_lsc_abs_error_nm": float(np.median(clean["lsc_abs_error_nm"])),
                "iqr_lsc_abs_error_nm": float(iqr(clean["lsc_abs_error_nm"])),
                "mean_lsc_abs_error_nm": float(np.mean(clean["lsc_abs_error_nm"])),
                "sd_lsc_abs_error_nm": float(np.std(clean["lsc_abs_error_nm"], ddof=1)),
                "median_radial_shape_mae_nm": float(np.median(clean["radial_shape_mae_nm"])),
                "median_contour_correlation": float(np.median(clean["contour_correlation"])),
                "median_mzc_roundness_abs_error_nm": float(np.median(clean["mzc_roundness_abs_error_nm"])),
                "median_harmonic4_abs_error_pct": float(np.median(clean["harmonic4_abs_error_pct"])),
            }
        )
    summary = pd.DataFrame(summaries)

    tests: list[dict[str, object]] = []
    raw = per_pillar[per_pillar["method"] == "Raw"].set_index("pillar_id")
    mosr = per_pillar[per_pillar["method"] == "MOSR"].set_index("pillar_id")
    for metric in (
        "lsc_abs_error_nm",
        "radial_shape_mae_nm",
        "contour_correlation",
        "mzc_roundness_abs_error_nm",
        "harmonic4_abs_error_pct",
    ):
        statistic, p_value = wilcoxon(raw[metric], mosr[metric], zero_method="wilcox", alternative="two-sided")
        tests.append(
            {
                "metric": metric,
                "n_pillars": 36,
                "raw_median": float(np.median(raw[metric])),
                "mosr_median": float(np.median(mosr[metric])),
                "mosr_minus_raw_median": float(np.median(mosr[metric] - raw[metric])),
                "wilcoxon_statistic": float(statistic),
                "p_value_two_sided": float(p_value),
            }
        )
    tests_table = pd.DataFrame(tests)
    metadata = {
        "source_mat": str(SOURCE_MAT),
        "optical_pitch_px": opt_pitch,
        "effective_um_per_px_from_5um_pitch": scale_um_per_px,
        "native_scale_warning": "This legacy SEM-paired stack is resampled and must not use the native 50x scale of 0.069 um/px.",
        "exposures": exposures.tolist(),
        "sem_edge_cleanup_ids": sorted(flagged),
        "grayscale_threshold_used": False,
    }
    return per_exposure, per_pillar, summary, tests_table, {
        "metadata": metadata,
        "truth_measurements": truth_measurements,
        "measurements": measurements,
        "data": data,
    }


def plot_sem_example(bundle: dict) -> None:
    data = bundle["data"]
    truth_measurements = bundle["truth_measurements"]
    measurements = bundle["measurements"]
    pillar = 29
    exposure = 18
    panels = [
        ("SEM", np.asarray(data["truth_cells"])[:, :, pillar - 1], truth_measurements[pillar]),
        ("Raw", np.asarray(data["raw_cells"])[:, :, pillar - 1, list(np.asarray(data["exposures"]).reshape(-1)).index(exposure)], measurements[("Raw", exposure, pillar)]),
        ("MOSR", np.asarray(data["recon_cells"])[:, :, pillar - 1, list(np.asarray(data["exposures"]).reshape(-1)).index(exposure)], measurements[("MOSR", exposure, pillar)]),
    ]
    fig, axes = plt.subplots(1, 3, figsize=(9.5, 3.2), constrained_layout=True)
    for ax, (label, image, measurement) in zip(axes, panels):
        ax.imshow(image, cmap="gray")
        points = measurement.inflection_points_xy
        ax.plot(points[:, 0], points[:, 1], ".", color="#00E5FF", ms=2.0)
        circle = measurement.circles.lsc
        ax.add_patch(PlotCircle((circle.cx, circle.cy), circle.radius, fill=False, lw=1.3, color="#39FF88"))
        ax.set_title(label)
        ax.set_axis_off()
    fig.savefig(FIGURES / "05_sem_raw_mosr_inflection_lsc_example.png", dpi=300, bbox_inches="tight")
    plt.close(fig)


def plot_exposure_trends(per_exposure: pd.DataFrame) -> None:
    metrics = [
        ("lsc_abs_error_nm", "LSC直徑絕對誤差 (nm)"),
        ("radial_shape_mae_nm", "相對SEM輪廓之徑向誤差 (nm)"),
        ("harmonic4_abs_error_pct", "四重對稱分量誤差 (百分點)"),
    ]
    fig, axes = plt.subplots(1, 3, figsize=(12.2, 3.8), constrained_layout=True)
    for ax, (metric, label) in zip(axes, metrics):
        for method in ("Raw", "MOSR"):
            grouped = per_exposure[per_exposure["method"] == method].groupby("exposure")[metric]
            median = grouped.median()
            q1 = grouped.quantile(0.25)
            q3 = grouped.quantile(0.75)
            ax.plot(median.index, median.values, "-o", color=COLORS[method], label=method, ms=3)
            ax.fill_between(median.index, q1.values, q3.values, color=COLORS[method], alpha=0.16)
        ax.axvline(19.5, color="#999999", ls="--", lw=0.9)
        ax.set_xlabel("曝光編號")
        ax.set_ylabel(label)
        ax.grid(alpha=0.25)
    axes[0].legend(frameon=False)
    fig.savefig(FIGURES / "06_sem36_exposure_trends.png", dpi=300, bbox_inches="tight")
    plt.close(fig)


def plot_field_position(per_pillar: pd.DataFrame) -> None:
    fig, axes = plt.subplots(1, 2, figsize=(8.5, 3.8), constrained_layout=True)
    for ax, metric, label in (
        (axes[0], "lsc_abs_error_nm", "LSC直徑絕對誤差 (nm)"),
        (axes[1], "radial_shape_mae_nm", "相對SEM輪廓之徑向誤差 (nm)"),
    ):
        categories = ["inner", "middle", "outer"]
        x = np.arange(len(categories))
        width = 0.36
        for method_index, method in enumerate(("Raw", "MOSR")):
            values = [
                float(np.median(per_pillar[(per_pillar["method"] == method) & (per_pillar["field_group"] == group)][metric]))
                for group in categories
            ]
            ax.bar(x + (method_index - 0.5) * width, values, width, label=method, color=COLORS[method], alpha=0.85)
        ax.set_xticks(x, ["中心", "中圈", "外圈"])
        ax.set_ylabel(label)
        ax.grid(axis="y", alpha=0.25)
    axes[0].legend(frameon=False)
    fig.savefig(FIGURES / "07_sem36_field_position_sensitivity.png", dpi=300, bbox_inches="tight")
    plt.close(fig)


def write_readout(summary: pd.DataFrame, tests: pd.DataFrame) -> None:
    primary = summary[summary["population"] == "all_36"]
    lines = [
        "# R80 36顆 SEM 輪廓驗證",
        "",
        "此資料是依 5 µm 週期重新取樣的 SEM 配對堆疊，量測比例為 5 µm / 實測週期；不可套用原生 50× 的 0.069 µm/px。",
        "",
        "SEM、Raw與MOSR均由既有Chan–Vese ACM提供粗輪廓，再沿法線取正確極性的最大梯度轉折點。沒有使用灰階閾值。",
        "",
    ]
    for row in primary.itertuples(index=False):
        lines.append(
            f"- {row.method}: 36顆pillar跨12曝光後的逐顆中位LSC直徑誤差為 {row.median_lsc_abs_error_nm:.1f} nm，"
            f"相對SEM輪廓徑向誤差為 {row.median_radial_shape_mae_nm:.1f} nm，輪廓相關係數中位數為 {row.median_contour_correlation:.3f}。"
        )
    lines.extend(["", "配對檢定："])
    for row in tests.itertuples(index=False):
        lines.append(
            f"- {row.metric}: Raw中位數 {row.raw_median:.3f}，MOSR中位數 {row.mosr_median:.3f}，p={row.p_value_two_sided:.4g}。"
        )
    (RESULTS / "SEM36_READOUT_TW.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    per_exposure, per_pillar, summary, tests, bundle = analyze()
    per_exposure.to_csv(TABLES / "sem36_per_exposure_reference_circles.csv", index=False, encoding="utf-8-sig")
    per_pillar.to_csv(TABLES / "sem36_per_pillar_median_reference_circles.csv", index=False, encoding="utf-8-sig")
    summary.to_csv(TABLES / "sem36_summary.csv", index=False, encoding="utf-8-sig")
    tests.to_csv(TABLES / "sem36_paired_tests.csv", index=False, encoding="utf-8-sig")
    (RESULTS / "sem36_metadata.json").write_text(
        json.dumps(bundle["metadata"], ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    plot_sem_example(bundle)
    plot_exposure_trends(per_exposure)
    plot_field_position(per_pillar)
    write_readout(summary, tests)
    print(summary.to_string(index=False))
    print(tests.to_string(index=False))


if __name__ == "__main__":
    main()

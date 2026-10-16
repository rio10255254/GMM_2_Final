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
from PIL import Image
from scipy.io import loadmat
from scipy.stats import iqr


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


PSF_ROOT = Path(
    r"D:\GMM_2_Final\Thesis_MOSR_Evidence\Final_Data_Figures"
    r"\03_PSF_EXPERIMENT_RESULTS\01_global_bads_fit"
)
FIGURE_ROOT = PSF_ROOT / "figures" / "center9_pillar_fit_20x_50x"
SOURCE_ROOT = PSF_ROOT / "source_data" / "center9_pillar_fit_20x_50x" / "psf_deconvolution_cd"
SWEEP_ROOT = Path(r"D:\GMM_2_Final\PSF_Fitting\tests\artifacts\cd_verification_20260714")
SEM_TABLE = PSF_ROOT / "tables" / "center9_pillar_fit_20x_50x" / "cd_before_after_per_pillar.csv"

NSR = 0.0565
SCALE = {"20x": 0.1725, "50x": 0.0690}
EXPECTED_RADIUS = {"20x": 7.6, "50x": 19.5}
SAMPLE_COUNT = {"20x": 72, "50x": 144}
ACM_ITERATIONS = {"20x": 18, "50x": 24}

COLORS = {"Raw": "#555555", "Wiener": "#D97904", "MOSR": "#2878B5", "SEM": "#111111"}

plt.rcParams["font.sans-serif"] = ["Microsoft JhengHei", "Microsoft YaHei", "DejaVu Sans"]
plt.rcParams["axes.unicode_minus"] = False


def load_static_case(magnification: str) -> tuple[dict[str, np.ndarray], np.ndarray]:
    metadata = loadmat(SOURCE_ROOT / f"{magnification}_wiener_deconvolution.mat", squeeze_me=True)
    centers = np.asarray(metadata["centers_xy"], dtype=float)
    sweep = loadmat(SWEEP_ROOT / f"{magnification}_deconvolution_sweep.mat", squeeze_me=True)
    raw = np.asarray(sweep["I"], dtype=float)
    crop_root = PSF_ROOT / "source_data" / "center9_pillar_fit_20x_50x" / "v42_crop_rerun"
    mosr_path = (
        crop_root
        / "outputs"
        / "reconstruct_progress_epoch_120_in_inputs_20260709_202713"
        / "reconstructed"
        / f"{magnification}_original_pillar_3x3.bmp"
    )
    mosr = np.asarray(Image.open(mosr_path), dtype=float) / 255.0
    nsr_values = np.asarray(sweep["nsr_values"], dtype=float).reshape(-1)
    index = int(np.argmin(np.abs(nsr_values - NSR)))
    if abs(float(nsr_values[index]) - NSR) > 1e-12:
        raise ValueError(f"{magnification} sweep does not contain NSR={NSR}")
    wiener = np.asarray(sweep["contrast_wiener"][:, :, index], dtype=float)
    if raw.shape != wiener.shape or raw.shape != mosr.shape:
        raise ValueError(f"shape mismatch for {magnification}: {raw.shape}, {wiener.shape}, {mosr.shape}")
    return {"Raw": raw, "Wiener": wiener, "MOSR": mosr}, centers


def analyze() -> tuple[pd.DataFrame, pd.DataFrame, dict[tuple[str, str, int], object], dict[str, dict[str, np.ndarray]]]:
    sem = pd.read_csv(SEM_TABLE)
    rows: list[dict[str, object]] = []
    measurements: dict[tuple[str, str, int], object] = {}
    images_by_mag: dict[str, dict[str, np.ndarray]] = {}

    for magnification in ("20x", "50x"):
        images, centers = load_static_case(magnification)
        images_by_mag[magnification] = images
        truth = sem[sem["magnification"] == magnification].sort_values("pillar_image_index")
        if len(truth) != 9:
            raise ValueError(f"expected nine SEM values for {magnification}")
        for method, image in images.items():
            for pillar_index, (center_xy, truth_row) in enumerate(
                zip(centers, truth.itertuples(index=False)), start=1
            ):
                measurement = measure_boundary_and_circles(
                    image,
                    (float(center_xy[0]), float(center_xy[1])),
                    EXPECTED_RADIUS[magnification],
                    sample_count=SAMPLE_COUNT[magnification],
                    acm_iterations=ACM_ITERATIONS[magnification],
                    polarity="dark",
                )
                measurements[(magnification, method, pillar_index)] = measurement
                metrics = summarize_reference_circles(
                    measurement, scale_um_per_px=SCALE[magnification]
                )
                sem_cd_um = float(truth_row.sem_cd_nm) / 1000.0
                row: dict[str, object] = {
                    "magnification": magnification,
                    "method": method,
                    "pillar_image_index": pillar_index,
                    "image_row": int(truth_row.image_row),
                    "image_column": int(truth_row.image_column),
                    "sem_cd_um": sem_cd_um,
                    "object_um_per_px": SCALE[magnification],
                    "wiener_nsr": NSR if method == "Wiener" else np.nan,
                }
                row.update(metrics)
                row["lsc_signed_error_nm"] = (float(row["lsc_diameter_um"]) - sem_cd_um) * 1000.0
                row["lsc_abs_error_nm"] = abs(float(row["lsc_signed_error_nm"]))
                row["mic_mcc_envelope_um"] = float(row["mcc_diameter_um"]) - float(row["mic_diameter_um"])
                rows.append(row)

    per_pillar = pd.DataFrame(rows)
    summaries: list[dict[str, object]] = []
    for (magnification, method), group in per_pillar.groupby(["magnification", "method"], sort=False):
        error = group["lsc_abs_error_nm"].to_numpy(float)
        summaries.append(
            {
                "magnification": magnification,
                "method": method,
                "n_pillars": len(group),
                "median_abs_error_nm": float(np.median(error)),
                "iqr_abs_error_nm": float(iqr(error)),
                "mean_abs_error_nm": float(np.mean(error)),
                "sd_abs_error_nm": float(np.std(error, ddof=1)),
                "median_signed_error_nm": float(np.median(group["lsc_signed_error_nm"])),
                "median_mzc_roundness_nm": float(np.median(group["mzc_roundness_um"]) * 1000.0),
                "median_mic_mcc_envelope_nm": float(np.median(group["mic_mcc_envelope_um"]) * 1000.0),
                "median_center_spread_nm": float(np.median(group["center_spread_um"]) * 1000.0),
                "median_harmonic4_relative_pct": float(np.median(group["harmonic4_relative_pct"])),
            }
        )
    summary = pd.DataFrame(summaries)
    return per_pillar, summary, measurements, images_by_mag


def add_scale_bar(ax: plt.Axes, magnification: str, image_shape: tuple[int, int]) -> None:
    length_um = 5.0
    length_px = length_um / SCALE[magnification]
    x1 = image_shape[1] - 7
    x0 = x1 - length_px
    y = image_shape[0] - 7
    ax.plot([x0, x1], [y, y], color="white", lw=3, solid_capstyle="butt")
    ax.text((x0 + x1) / 2, y - 4, "5 µm", color="white", ha="center", va="bottom", fontsize=8)


def draw_measurement(ax: plt.Axes, measurement, *, offset=(0.0, 0.0), show_all=True) -> None:
    ox, oy = offset
    points = measurement.inflection_points_xy
    ax.plot(points[:, 0] + ox, points[:, 1] + oy, ".", color="#00E5FF", ms=1.7, alpha=0.9)
    circle_colors = {"lsc": "#00FF66", "mzc": "#FFD400", "mic": "#FF4FB3", "mcc": "#FF3030"}
    for name in ("lsc", "mzc", "mic", "mcc"):
        if not show_all and name != "lsc":
            continue
        circle = getattr(measurement.circles, name)
        ax.add_patch(
            PlotCircle(
                (circle.cx + ox, circle.cy + oy),
                circle.radius,
                fill=False,
                lw=1.1,
                color=circle_colors[name],
                label=name.upper(),
            )
        )


def plot_workflow(images, measurements) -> None:
    magnification = "50x"
    method = "MOSR"
    pillar = 5
    image = images[magnification][method]
    measurement = measurements[(magnification, method, pillar)]
    fig, axes = plt.subplots(1, 4, figsize=(13.2, 3.4), constrained_layout=True)
    for ax in axes:
        ax.imshow(image, cmap="gray", vmin=0, vmax=1)
        ax.set_axis_off()
    axes[0].set_title("(a) MOSR影像")
    axes[1].imshow(measurement.coarse_mask, cmap="Blues", alpha=0.35)
    coarse = measurement.coarse_contour_xy
    axes[1].plot(coarse[:, 0], coarse[:, 1], color="#00A6FF", lw=1.3)
    axes[1].set_title("(b) ACM完整粗輪廓")
    axes[2].plot(coarse[:, 0], coarse[:, 1], color="#00A6FF", lw=0.8, alpha=0.7)
    points = measurement.inflection_points_xy
    axes[2].plot(points[:, 0], points[:, 1], ".", color="#FFE000", ms=2.4)
    axes[2].set_title("(c) 最大梯度轉折點")
    draw_measurement(axes[3], measurement, show_all=True)
    axes[3].set_title("(d) 四種參考圓")
    handles, labels = axes[3].get_legend_handles_labels()
    axes[3].legend(handles, labels, loc="lower right", fontsize=7, framealpha=0.8)
    fig.savefig(FIGURES / "01_acm_inflection_reference_circle_workflow.png", dpi=300, bbox_inches="tight")
    plt.close(fig)


def plot_static_overview(images, measurements) -> None:
    fig, axes = plt.subplots(2, 3, figsize=(9.6, 6.5), constrained_layout=True)
    for row, magnification in enumerate(("20x", "50x")):
        for col, method in enumerate(("Raw", "Wiener", "MOSR")):
            ax = axes[row, col]
            image = images[magnification][method]
            ax.imshow(image, cmap="gray", vmin=0, vmax=1)
            for pillar in range(1, 10):
                draw_measurement(ax, measurements[(magnification, method, pillar)], show_all=False)
            add_scale_bar(ax, magnification, image.shape)
            ax.set_title(f"{magnification} {method}")
            ax.set_axis_off()
    fig.savefig(FIGURES / "02_native_scale_three_method_lsc_overlay.png", dpi=300, bbox_inches="tight")
    plt.close(fig)


def plot_cd_error(per_pillar: pd.DataFrame) -> None:
    fig, axes = plt.subplots(1, 2, figsize=(9.5, 4.1), sharey=True, constrained_layout=True)
    rng = np.random.default_rng(20260805)
    for ax, magnification in zip(axes, ("20x", "50x")):
        subset = per_pillar[per_pillar["magnification"] == magnification]
        for index, method in enumerate(("Raw", "Wiener", "MOSR")):
            values = subset[subset["method"] == method]["lsc_abs_error_nm"].to_numpy(float)
            ax.boxplot(
                values,
                positions=[index],
                widths=0.55,
                patch_artist=True,
                showfliers=False,
                boxprops={"facecolor": COLORS[method], "alpha": 0.45, "edgecolor": COLORS[method]},
                medianprops={"color": "black", "linewidth": 1.5},
                whiskerprops={"color": COLORS[method]},
                capprops={"color": COLORS[method]},
            )
            jitter = rng.normal(index, 0.045, size=len(values))
            ax.scatter(jitter, values, s=18, color=COLORS[method], edgecolor="white", linewidth=0.35, zorder=3)
        ax.set_xticks(range(3), ["Raw", "Wiener", "MOSR"])
        ax.set_title(magnification)
        ax.grid(axis="y", alpha=0.25)
    axes[0].set_ylabel("LSC直徑相對SEM之絕對誤差 (nm)")
    fig.savefig(FIGURES / "03_lsc_cd_error_vs_sem.png", dpi=300, bbox_inches="tight")
    plt.close(fig)


def plot_reference_metrics(per_pillar: pd.DataFrame) -> None:
    fig, axes = plt.subplots(1, 3, figsize=(12, 4.0), constrained_layout=True)
    metrics = [
        ("mzc_roundness_um", "MZC圓度 (nm)", 1000.0),
        ("mic_mcc_envelope_um", "MIC–MCC尺寸包絡 (nm)", 1000.0),
        ("harmonic4_relative_pct", "四重對稱分量 / LSC半徑 (%)", 1.0),
    ]
    x = np.arange(3)
    width = 0.36
    for ax, (column, label, factor) in zip(axes, metrics):
        for mag_index, magnification in enumerate(("20x", "50x")):
            medians = []
            for method in ("Raw", "Wiener", "MOSR"):
                values = per_pillar[
                    (per_pillar["magnification"] == magnification)
                    & (per_pillar["method"] == method)
                ][column]
                medians.append(float(np.median(values)) * factor)
            ax.bar(
                x + (mag_index - 0.5) * width,
                medians,
                width,
                label=magnification,
                color="#73A9D8" if magnification == "20x" else "#2F5D8A",
                alpha=0.88,
            )
        ax.set_xticks(x, ["Raw", "Wiener", "MOSR"])
        ax.set_ylabel(label)
        ax.grid(axis="y", alpha=0.25)
    axes[0].legend(frameon=False)
    fig.savefig(FIGURES / "04_roundness_envelope_square_component.png", dpi=300, bbox_inches="tight")
    plt.close(fig)


def write_readout(summary: pd.DataFrame) -> None:
    lines = [
        "# R80 靜態九顆 pillar 結果",
        "",
        "量測規則固定為 ACM 粗輪廓、沿法線的正極性最大梯度轉折點、LSC 主直徑與圓心、MZC 圓度、MIC/MCC 尺寸包絡。全流程不使用灰階閾值。",
        "",
        f"Wiener 僅作固定傳統影像基準，兩倍率共用已校準 NSR = {NSR:.4f}。",
        "",
    ]
    for row in summary.itertuples(index=False):
        lines.append(
            f"- {row.magnification} {row.method}: LSC-CD 絕對誤差中位數 {row.median_abs_error_nm:.1f} nm "
            f"(IQR {row.iqr_abs_error_nm:.1f} nm)，MZC 圓度中位數 {row.median_mzc_roundness_nm:.1f} nm，"
            f"四重對稱分量 {row.median_harmonic4_relative_pct:.3f}%。"
        )
    (RESULTS / "STATIC_CENTER9_READOUT_TW.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    per_pillar, summary, measurements, images = analyze()
    per_pillar.to_csv(TABLES / "static_center9_reference_circles_per_pillar.csv", index=False, encoding="utf-8-sig")
    summary.to_csv(TABLES / "static_center9_reference_circles_summary.csv", index=False, encoding="utf-8-sig")
    plot_workflow(images, measurements)
    plot_static_overview(images, measurements)
    plot_cd_error(per_pillar)
    plot_reference_metrics(per_pillar)
    write_readout(summary)
    metadata = {
        "analysis": "ACM coarse contour plus correct-polarity maximum-gradient inflection points",
        "primary_circle": "least-squares circle (LSC)",
        "roundness_circle": "minimum-zone circle (MZC)",
        "size_envelope": "maximum-inscribed and minimum-circumscribed circles (MIC/MCC)",
        "grayscale_threshold_used": False,
        "wiener_nsr": NSR,
        "scales_um_per_px": SCALE,
        "n_pillars_per_magnification": 9,
    }
    (RESULTS / "static_center9_metadata.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(summary.to_string(index=False))


if __name__ == "__main__":
    main()

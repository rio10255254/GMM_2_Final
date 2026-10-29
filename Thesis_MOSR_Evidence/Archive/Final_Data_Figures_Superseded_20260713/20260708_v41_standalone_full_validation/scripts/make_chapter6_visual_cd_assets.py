from __future__ import annotations

import csv
import json
import math
from pathlib import Path

import cv2
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from PIL import Image, ImageOps
PROJECT_ROOT = Path(__file__).resolve().parents[5]


ROOT = Path(str(PROJECT_ROOT / 'Thesis_MOSR_Evidence'))
SCRIPT_DIR = Path(__file__).resolve().parent
ASSET_ROOT = SCRIPT_DIR.parent if SCRIPT_DIR.name == "scripts" else SCRIPT_DIR
IMAGE_DIR = ASSET_ROOT / "images"
FIG_DIR = ASSET_ROOT / "figures"
TABLE_DIR = ASSET_ROOT / "tables"

OLD_ASSET_ROOT = ROOT / "Experiments" / "20260626_individual_raw_combo_r61_assets"

IMAGE_CASES_100MG = {
    "raw": ROOT / "20260618_100MG" / "Image__2026-06-18__17-10-31.bmp",
    "combo_psf_bypass": OLD_ASSET_ROOT / "recon_combo_psf_bypass" / "Image__2026-06-18__17-10-31.bmp",
    "r61_v16": ROOT
    / "Experiments"
    / "20260626_training_data_real_slide_assets"
    / "recon_100mg_r61_v16"
    / "reconstruct_progress_best_tradeoff_in_inputs_100mg_single_20260623_200020"
    / "r61_v16_best_tradeoff_100mg"
    / "Image__2026-06-18__17-10-31.bmp",
    "v41_current": ASSET_ROOT
    / "reconstruction_runs"
    / "final_v41_psfoff"
    / "100mg"
    / "Image__2026-06-18__17-10-31.bmp",
}

STEP_FRAME = "VisionTop_20260615173931287.bmp"
IMAGE_CASES_CONCENTRIC = {
    "raw": Path(str(PROJECT_ROOT / 'Analyses/Step_analysis_20260623/clean_step_audit_from_original_pos10_20260623_2218/center2048_bmp'))
    / STEP_FRAME,
    "combo_psf_bypass": OLD_ASSET_ROOT / "recon_combo_psf_bypass_concentric" / STEP_FRAME,
    "r61_v16": Path(str(PROJECT_ROOT / 'Analyses/Step_analysis_20260623/clean_step_audit_from_original_pos10_20260623_2218'))
    / "clean_reconstruction_outputs"
    / "reconstruct_progress_best_tradeoff_in_center2048_bmp_20260623_200020"
    / "03_v16_clean_pos10_center2048"
    / STEP_FRAME,
    "v41_current": ASSET_ROOT
    / "reconstruction_runs"
    / "final_v41_psfoff"
    / "concentric"
    / STEP_FRAME,
}

RAW_CD = ROOT / "LabSystem_MOSR" / "Reconstruct_Progress" / "20260618_100MG_user_recon" / "cd_measurement_20260624_corrected_69nm" / "raw_original" / "cd_measurement_per_feature.csv"
SEM_CD = ROOT / ".tmp" / "sem_data" / "sem_cd_36_records.csv"
PILLAR = "\u5713\u67f1"
NM_PER_PX = 69.0


def read_gray(path: Path) -> np.ndarray:
    data = np.fromfile(str(path), dtype=np.uint8)
    img = cv2.imdecode(data, cv2.IMREAD_GRAYSCALE)
    if img is None:
        raise RuntimeError(f"cannot read image: {path}")
    return img


def normalize_u8(arr: np.ndarray) -> np.ndarray:
    arr = arr.astype(np.float32)
    lo, hi = np.percentile(arr, [0.5, 99.5])
    if hi <= lo:
        return np.clip(arr, 0, 255).astype(np.uint8)
    out = (arr - lo) / (hi - lo) * 255.0
    return np.clip(out, 0, 255).astype(np.uint8)


def save_crop_png(src: Path, dst: Path, crop: tuple[int, int, int, int], max_side: int = 1500) -> None:
    arr = read_gray(src)
    x0, y0, x1, y1 = crop
    arr = arr[y0:y1, x0:x1]
    img = Image.fromarray(normalize_u8(arr))
    img = ImageOps.autocontrast(img)
    if max(img.size) > max_side:
        img.thumbnail((max_side, max_side), Image.Resampling.LANCZOS)
    dst.parent.mkdir(parents=True, exist_ok=True)
    img.save(dst)


def read_feature_rows(path: Path) -> list[dict[str, object]]:
    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        rows = list(csv.DictReader(fh))
    out: list[dict[str, object]] = []
    for row in rows:
        out.append(
            {
                "id": int(float(row["id"])),
                "feature": str(row["feature"]),
                "x_px": float(row["x_px"]),
                "y_px": float(row["y_px"]),
                "radius_px": float(row["radius_px"]),
                "clean": int(float(row["clean_for_summary"])),
            }
        )
    return out


def read_sem_pillar_diameter_nm() -> dict[int, float]:
    with SEM_CD.open("r", encoding="utf-8-sig", newline="") as fh:
        return {int(row["index"]): float(row["pillar_diameter_nm"]) for row in csv.DictReader(fh)}


def select_center_pillars(top_n: int = 9) -> pd.DataFrame:
    sem = read_sem_pillar_diameter_nm()
    rows: list[dict[str, object]] = []
    for row in read_feature_rows(RAW_CD):
        if row["feature"] != PILLAR or int(row["clean"]) != 1 or int(row["id"]) not in sem:
            continue
        dist = math.hypot(float(row["x_px"]) - 1024.0, float(row["y_px"]) - 768.0)
        rows.append({**row, "center_distance_px": dist, "sem_diameter_nm": sem[int(row["id"])]})
    return pd.DataFrame(sorted(rows, key=lambda item: float(item["center_distance_px"]))[:top_n])


def crop_for_100mg(selected: pd.DataFrame) -> tuple[int, int, int, int]:
    pad = 115
    x0 = max(0, int(selected["x_px"].min() - pad))
    x1 = min(2048, int(selected["x_px"].max() + pad))
    y0 = max(0, int(selected["y_px"].min() - pad))
    y1 = min(1536, int(selected["y_px"].max() + pad))
    return x0, y0, x1, y1


def crop_for_concentric() -> tuple[int, int, int, int]:
    arr = read_gray(IMAGE_CASES_CONCENTRIC["raw"])
    h, w = arr.shape
    size = min(1600, h, w)
    x0 = (w - size) // 2
    y0 = (h - size) // 2
    return x0, y0, x0 + size, y0 + size


def estimate_radius_px_fast(
    grad_mag: np.ndarray,
    *,
    x_px: float,
    y_px: float,
    expected_radius_px: float,
    radial_window: float = 0.35,
    radius_step_px: float = 0.05,
    angle_count: int = 240,
) -> float:
    r0 = max(2.0, float(expected_radius_px))
    r_min = max(2.0, r0 * (1.0 - radial_window))
    r_max = max(r_min + radius_step_px, r0 * (1.0 + radial_window))
    radii = np.arange(r_min, r_max + radius_step_px * 0.5, radius_step_px, dtype=np.float32)
    theta = np.linspace(0.0, 2.0 * np.pi, int(angle_count), endpoint=False, dtype=np.float32)
    xs = float(x_px) + radii[:, None] * np.cos(theta)[None, :]
    ys = float(y_px) + radii[:, None] * np.sin(theta)[None, :]
    samples = cv2.remap(
        grad_mag.astype(np.float32),
        xs.astype(np.float32),
        ys.astype(np.float32),
        cv2.INTER_LINEAR,
        borderMode=cv2.BORDER_REPLICATE,
    )
    scores = samples.mean(axis=1)
    return float(radii[int(np.argmax(scores))])


def measure_center9_for_case(case: str, image_path: Path, selected: pd.DataFrame) -> pd.DataFrame:
    img = read_gray(image_path).astype(np.float32) / 255.0
    grad_x = cv2.Sobel(img, cv2.CV_32F, 1, 0, ksize=3)
    grad_y = cv2.Sobel(img, cv2.CV_32F, 0, 1, ksize=3)
    grad_mag = cv2.magnitude(grad_x, grad_y)
    rows: list[dict[str, object]] = []
    for position, row in enumerate(selected.to_dict("records"), start=1):
        radius_px = estimate_radius_px_fast(
            grad_mag,
            x_px=float(row["x_px"]),
            y_px=float(row["y_px"]),
            expected_radius_px=float(row["radius_px"]),
        )
        rows.append(
            {
                "case": case,
                "position": position,
                "pillar_id": int(row["id"]),
                "x_px": float(row["x_px"]),
                "y_px": float(row["y_px"]),
                "radius_px": radius_px,
                "diameter_um": radius_px * NM_PER_PX * 2.0 / 1000.0,
                "sem_truth_um": float(row["sem_diameter_nm"]) / 1000.0,
                "abs_error_nm": abs(radius_px * NM_PER_PX * 2.0 - float(row["sem_diameter_nm"])),
            }
        )
    return pd.DataFrame(rows)


def export_visual_images(selected: pd.DataFrame) -> dict[str, str]:
    crop100 = crop_for_100mg(selected)
    crop_concentric = crop_for_concentric()
    outputs: dict[str, str] = {}
    for case, path in IMAGE_CASES_100MG.items():
        out = IMAGE_DIR / f"100mg_{case}.png"
        save_crop_png(path, out, crop100)
        outputs[f"100mg_{case}"] = str(out)
    for case, path in IMAGE_CASES_CONCENTRIC.items():
        out = IMAGE_DIR / f"concentric_{case}.png"
        save_crop_png(path, out, crop_concentric)
        outputs[f"concentric_{case}"] = str(out)
    return outputs


def save_table_png(df: pd.DataFrame, out_path: Path, title: str, width: float = 15.0) -> None:
    fig, ax = plt.subplots(figsize=(width, 0.7 + 0.44 * (len(df) + 1)), dpi=180)
    ax.axis("off")
    ax.text(0.0, 1.04, title, transform=ax.transAxes, fontsize=14, fontweight="bold", va="bottom")
    table = ax.table(
        cellText=df.values,
        colLabels=df.columns,
        loc="upper left",
        cellLoc="center",
        colLoc="center",
        bbox=[0, 0, 1, 0.96],
    )
    table.auto_set_font_size(False)
    table.set_fontsize(8.3)
    table.scale(1, 1.18)
    for (r, _c), cell in table.get_celld().items():
        cell.set_edgecolor("#D7DBE7")
        if r == 0:
            cell.set_facecolor("#EAF1FE")
            cell.set_text_props(weight="bold", color="#1F2430")
        else:
            cell.set_facecolor("#FFFFFF" if r % 2 else "#F7F8FB")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def _style_cd_axes(ax) -> None:
    ax.set_xlabel("Pillar position near image center", fontsize=14)
    ax.set_ylabel("Diameter (um)", fontsize=14)
    ax.grid(True, axis="y", alpha=0.25)


def plot_cd_line(wide: pd.DataFrame, out_path: Path) -> None:
    fig, ax = plt.subplots(figsize=(11, 6.6), dpi=180)
    x = wide["position"].to_numpy()
    ax.plot(x, wide["sem_truth_um"], color="black", linestyle=(0, (6, 4)), marker=".", linewidth=1.4, label="SEM truth")
    ax.plot(x, wide["raw_um"], color="#E41A1C", marker="s", fillstyle="none", linewidth=1.2, label="Raw")
    ax.plot(x, wide["combo_psf_bypass_um"], color="#984EA3", marker="^", fillstyle="none", linewidth=1.2, label="COMBO PSF off")
    ax.plot(x, wide["r61_v16_um"], color="#377EB8", marker="o", fillstyle="none", linewidth=1.2, label="R61 v16")
    ax.plot(x, wide["v41_current_um"], color="#4DAF4A", marker="D", fillstyle="none", linewidth=1.2, label="V41 current")
    ax.set_title("100MG center-nine pillar CD measurement", fontsize=18, fontweight="bold")
    _style_cd_axes(ax)
    ax.legend(loc="best", fontsize=10.5, frameon=True, fancybox=False, edgecolor="black")
    fig.tight_layout()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, facecolor="white")
    plt.close(fig)


def plot_cd_line_zoom(wide: pd.DataFrame, out_path: Path) -> None:
    fig, ax = plt.subplots(figsize=(11, 6.6), dpi=180)
    x = wide["position"].to_numpy()
    ax.plot(x, wide["sem_truth_um"], color="black", linestyle=(0, (6, 4)), marker=".", linewidth=1.4, label="SEM truth")
    ax.plot(x, wide["raw_um"], color="#E41A1C", marker="s", fillstyle="none", linewidth=1.2, label="Raw")
    ax.plot(x, wide["r61_v16_um"], color="#377EB8", marker="o", fillstyle="none", linewidth=1.2, label="R61 v16")
    ax.plot(x, wide["v41_current_um"], color="#4DAF4A", marker="D", fillstyle="none", linewidth=1.2, label="V41 current")
    ax.set_title("100MG CD measurement zoom: Raw / R61 / V41", fontsize=18, fontweight="bold")
    _style_cd_axes(ax)
    ymin = min(wide[["sem_truth_um", "raw_um", "r61_v16_um", "v41_current_um"]].min()) - 0.025
    ymax = max(wide[["sem_truth_um", "raw_um", "r61_v16_um", "v41_current_um"]].max()) + 0.025
    ax.set_ylim(float(ymin), float(ymax))
    ax.legend(loc="best", fontsize=10.5, frameon=True, fancybox=False, edgecolor="black")
    fig.tight_layout()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, facecolor="white")
    plt.close(fig)


def plot_error_bar(summary: pd.DataFrame, out_path: Path) -> None:
    order = ["raw", "combo_psf_bypass", "r61_v16", "v41_current"]
    labels = ["Raw", "COMBO off", "R61 v16", "V41"]
    values = [float(summary.loc[summary["case"] == case, "mean_abs_error_nm"].iloc[0]) for case in order]
    fig, ax = plt.subplots(figsize=(8.5, 5.2), dpi=180)
    ax.bar(labels, values, color=["#E41A1C", "#984EA3", "#377EB8", "#4DAF4A"], edgecolor="#222222", linewidth=0.8)
    ax.set_title("Mean absolute CD error, center-nine pillars", fontsize=16, fontweight="bold", pad=14)
    ax.set_ylabel("Mean absolute error (nm)", fontsize=13)
    ax.grid(True, axis="y", alpha=0.25)
    ax.set_ylim(0, max(values) * 1.18)
    for i, val in enumerate(values):
        ax.text(i, val + max(values) * 0.02, f"{val:.1f}", ha="center", va="bottom", fontsize=11)
    fig.tight_layout()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, facecolor="white")
    plt.close(fig)


def export_cd_tables(selected: pd.DataFrame) -> dict[str, str]:
    long_frames = [measure_center9_for_case(case, path, selected) for case, path in IMAGE_CASES_100MG.items()]
    long_df = pd.concat(long_frames, ignore_index=True)
    long_csv = TABLE_DIR / "100mg_center9_cd_measurements_long.csv"
    long_df.to_csv(long_csv, index=False, encoding="utf-8-sig", float_format="%.9f")

    wide = selected[["id"]].copy()
    wide["position"] = np.arange(1, len(selected) + 1)
    wide = wide.rename(columns={"id": "pillar_id"})
    wide["sem_truth_um"] = selected["sem_diameter_nm"].astype(float).to_numpy() / 1000.0
    for case in IMAGE_CASES_100MG:
        case_df = long_df[long_df["case"] == case].sort_values("position")
        wide[f"{case}_um"] = case_df["diameter_um"].to_numpy()
        wide[f"{case}_abs_error_nm"] = case_df["abs_error_nm"].to_numpy()
    error_cols = [f"{case}_abs_error_nm" for case in IMAGE_CASES_100MG]
    labels = {"raw": "Raw", "combo_psf_bypass": "COMBO off", "r61_v16": "R61 v16", "v41_current": "V41"}
    wide["closest"] = [
        labels[min(IMAGE_CASES_100MG.keys(), key=lambda case: float(row[f"{case}_abs_error_nm"]))]
        for row in wide.to_dict("records")
    ]
    wide_csv = TABLE_DIR / "100mg_center9_cd_raw_combo_r61_v41.csv"
    wide.to_csv(wide_csv, index=False, encoding="utf-8-sig", float_format="%.9f")

    summary_rows = []
    for case in IMAGE_CASES_100MG:
        errors = wide[f"{case}_abs_error_nm"].astype(float)
        summary_rows.append(
            {
                "case": case,
                "mean_abs_error_nm": float(errors.mean()),
                "median_abs_error_nm": float(errors.median()),
                "max_abs_error_nm": float(errors.max()),
                "closest_count": int((wide["closest"] == labels[case]).sum()),
            }
        )
    summary = pd.DataFrame(summary_rows)
    summary_csv = TABLE_DIR / "100mg_center9_cd_error_summary.csv"
    summary.to_csv(summary_csv, index=False, encoding="utf-8-sig", float_format="%.6f")

    display = wide[
        [
            "position",
            "pillar_id",
            "sem_truth_um",
            "raw_um",
            "combo_psf_bypass_um",
            "r61_v16_um",
            "v41_current_um",
            "raw_abs_error_nm",
            "combo_psf_bypass_abs_error_nm",
            "r61_v16_abs_error_nm",
            "v41_current_abs_error_nm",
            "closest",
        ]
    ].copy()
    for col in ["sem_truth_um", "raw_um", "combo_psf_bypass_um", "r61_v16_um", "v41_current_um"]:
        display[col] = display[col].map(lambda v: f"{float(v):.4f}")
    for col in [
        "raw_abs_error_nm",
        "combo_psf_bypass_abs_error_nm",
        "r61_v16_abs_error_nm",
        "v41_current_abs_error_nm",
    ]:
        display[col] = display[col].map(lambda v: f"{float(v):.1f}")
    display = display.rename(
        columns={
            "position": "Pos",
            "pillar_id": "ID",
            "sem_truth_um": "SEM um",
            "raw_um": "Raw um",
            "combo_psf_bypass_um": "COMBO off um",
            "r61_v16_um": "R61 um",
            "v41_current_um": "V41 um",
            "raw_abs_error_nm": "Raw err nm",
            "combo_psf_bypass_abs_error_nm": "COMBO err nm",
            "r61_v16_abs_error_nm": "R61 err nm",
            "v41_current_abs_error_nm": "V41 err nm",
            "closest": "Closest",
        }
    )
    table_png = FIG_DIR / "100mg_center9_cd_table.png"
    save_table_png(display, table_png, "100MG center-nine pillar CD vs SEM truth", width=19.0)

    line_png = FIG_DIR / "100mg_center9_cd_line.png"
    plot_cd_line(wide, line_png)
    zoom_png = FIG_DIR / "100mg_center9_cd_line_zoom_raw_r61_v41.png"
    plot_cd_line_zoom(wide, zoom_png)
    error_png = FIG_DIR / "100mg_center9_cd_error_bar.png"
    plot_error_bar(summary, error_png)
    return {
        "long_csv": str(long_csv),
        "wide_csv": str(wide_csv),
        "summary_csv": str(summary_csv),
        "table_png": str(table_png),
        "line_png": str(line_png),
        "line_zoom_png": str(zoom_png),
        "error_bar_png": str(error_png),
    }


def write_readme(images: dict[str, str], cd: dict[str, str]) -> None:
    manifest = {
        "purpose": "Chapter 6 experiments 1 and 2: reconstruction visual comparison and 100MG center-nine pillar CD validation.",
        "model_under_test": "V41 current strongest PSF-off reconstruction",
        "pixel_scale_for_100mg_cd_nm_per_px": NM_PER_PX,
        "image_cases_100mg": {k: str(v) for k, v in IMAGE_CASES_100MG.items()},
        "image_cases_concentric": {k: str(v) for k, v in IMAGE_CASES_CONCENTRIC.items()},
        "exported_images": images,
        "cd_outputs": cd,
    }
    (TABLE_DIR / "asset_manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")

    summary = pd.read_csv(cd["summary_csv"])
    best = summary.sort_values("mean_abs_error_nm").iloc[0]
    lines = [
        "# Chapter 6 Visual Reconstruction and CD Validation Package",
        "",
        "This folder centralizes the first two Chapter 6 experiment groups:",
        "",
        "1. visual reconstruction comparison on the 100MG sample and concentric Step sample;",
        "2. center-nine 100MG pillar CD comparison against SEM-derived diameter truth.",
        "",
        "## Main Outputs",
        "",
        "- Independent visual crops: `images/`",
        "- CD measurement tables: `tables/100mg_center9_cd_raw_combo_r61_v41.csv` and `tables/100mg_center9_cd_error_summary.csv`",
        "- Thesis-ready CD figures: `figures/100mg_center9_cd_line.png`, `figures/100mg_center9_cd_line_zoom_raw_r61_v41.png`, `figures/100mg_center9_cd_error_bar.png`, `figures/100mg_center9_cd_table.png`",
        "",
        "## Method Notes",
        "",
        "- All 100MG CD values use the same nine pillar centers selected from the raw-template feature table.",
        "- The SEM reference is read from the SEM-derived 36-record diameter table.",
        "- The V41 reconstruction is generated in this package with PSF disabled during inference.",
        "- The COMBO comparison uses the PSF-bypass image because the PSF-on version was previously observed to over-expand the measured pillars.",
        "",
        "## Quick Result",
        "",
        f"- Lowest mean absolute CD error in this focused center-nine test: `{best['case']}` at `{float(best['mean_abs_error_nm']):.2f} nm`.",
    ]
    (ASSET_ROOT / "README.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    IMAGE_DIR.mkdir(parents=True, exist_ok=True)
    FIG_DIR.mkdir(parents=True, exist_ok=True)
    TABLE_DIR.mkdir(parents=True, exist_ok=True)
    for path in list(IMAGE_CASES_100MG.values()) + list(IMAGE_CASES_CONCENTRIC.values()) + [RAW_CD, SEM_CD]:
        if not Path(path).is_file():
            raise FileNotFoundError(path)
    selected = select_center_pillars(9)
    images = export_visual_images(selected)
    cd = export_cd_tables(selected)
    write_readme(images, cd)
    print(json.dumps({"images": images, "cd": cd, "root": str(ASSET_ROOT)}, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()

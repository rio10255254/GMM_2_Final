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
PROJECT_ROOT = Path(__file__).resolve().parents[3]


ROOT = Path(str(PROJECT_ROOT / 'Thesis_MOSR_Evidence'))
ASSET_ROOT = ROOT / "Experiments" / "20260626_individual_raw_combo_r61_assets"
IMAGE_DIR = ASSET_ROOT / "images"
FIG_DIR = ASSET_ROOT / "figures"
TABLE_DIR = ASSET_ROOT / "tables"

RAW_100MG = ROOT / "20260618_100MG" / "Image__2026-06-18__17-10-31.bmp"
COMBO_100MG_PSF_ON = (
    ASSET_ROOT
    / "recon_combo"
    / "reconstruct_progress_best_tradeoff_in_inputs_100mg_single_20260408_003525"
    / "combo_100mg"
    / "Image__2026-06-18__17-10-31.bmp"
)
COMBO_100MG = ASSET_ROOT / "recon_combo_psf_bypass" / "Image__2026-06-18__17-10-31.bmp"
R61_100MG = (
    ROOT
    / "Experiments"
    / "20260626_training_data_real_slide_assets"
    / "recon_100mg_r61_v16"
    / "reconstruct_progress_best_tradeoff_in_inputs_100mg_single_20260623_200020"
    / "r61_v16_best_tradeoff_100mg"
    / "Image__2026-06-18__17-10-31.bmp"
)

STEP_FRAME = "VisionTop_20260615173931287.bmp"
STEP_RAW = Path(str(PROJECT_ROOT / 'Analyses/Step_analysis_20260623/clean_step_audit_from_original_pos10_20260623_2218/center2048_bmp')) / STEP_FRAME
STEP_COMBO_PSF_ON = (
    ASSET_ROOT
    / "recon_combo"
    / "reconstruct_progress_best_tradeoff_in_inputs_concentric_single_20260408_003525"
    / "combo_concentric_step"
    / STEP_FRAME
)
STEP_COMBO = ASSET_ROOT / "recon_combo_psf_bypass_concentric" / STEP_FRAME
STEP_R61 = (
    Path(str(PROJECT_ROOT / 'Analyses/Step_analysis_20260623/clean_step_audit_from_original_pos10_20260623_2218'))
    / "clean_reconstruction_outputs"
    / "reconstruct_progress_best_tradeoff_in_center2048_bmp_20260623_200020"
    / "03_v16_clean_pos10_center2048"
    / STEP_FRAME
)

RAW_CD = ROOT / ".." / "LabSystem_MOSR" / "Reconstruct_Progress" / "20260618_100MG_user_recon" / "cd_measurement_20260624_corrected_69nm" / "raw_original" / "cd_measurement_per_feature.csv"
COMBO_CD_PSF_ON = ASSET_ROOT / "cd_measurement_100mg_combo" / "cd_measurement_per_feature.csv"
COMBO_CD = ASSET_ROOT / "cd_measurement_100mg_combo_psf_bypass" / "cd_measurement_per_feature.csv"
R61_CD = ROOT / "Experiments" / "20260626_training_data_real_slide_assets" / "cd_measurement_100mg_r61_v16" / "cd_measurement_per_feature.csv"
SEM_CD = ROOT / ".tmp" / "sem_data" / "sem_cd_36_records.csv"

GMF_1UM = Path(str(PROJECT_ROOT / 'Analyses/Step_analysis_20260623/_curated_final_20260624/02_gmf_validation/1um/analysis_center_square_raw_vs_v16_rep0_20260624_0916/gmf_center_square_1um_steps.csv'))
GMF_0P5UM = Path(str(PROJECT_ROOT / 'Analyses/Step_analysis_20260623/_curated_final_20260624/02_gmf_validation/0p5um/analysis_center_square_raw_vs_v16_rep0_20260624_0p5um/gmf_center_square_0p5um_steps.csv'))

PILLAR = "\u5713\u67f1"


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


def save_individual_image(src: Path, dst: Path, crop: tuple[int, int, int, int] | None, max_side: int = 1500) -> None:
    arr = read_gray(src)
    if crop is not None:
        x0, y0, x1, y1 = crop
        arr = arr[y0:y1, x0:x1]
    img = Image.fromarray(normalize_u8(arr))
    img = ImageOps.autocontrast(img)
    if max(img.size) > max_side:
        img.thumbnail((max_side, max_side), Image.Resampling.LANCZOS)
    dst.parent.mkdir(parents=True, exist_ok=True)
    img.save(dst)


def read_feature_rows(path: Path) -> list[dict]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    out: list[dict] = []
    for row in rows:
        out.append(
            {
                "id": int(float(row["id"])),
                "feature": row["feature"],
                "x_px": float(row["x_px"]),
                "y_px": float(row["y_px"]),
                "clean": int(float(row["clean_for_summary"])),
                "diameter_nm": float(row["diameter_nm_basler_50x"]),
            }
        )
    return out


def read_sem_pillar_diameter() -> dict[int, float]:
    with SEM_CD.open("r", encoding="utf-8-sig", newline="") as f:
        return {int(row["index"]): float(row["pillar_diameter_nm"]) for row in csv.DictReader(f)}


def select_center_sem_pillars(top_n: int = 9) -> pd.DataFrame:
    sem = read_sem_pillar_diameter()
    rows = []
    for row in read_feature_rows(RAW_CD):
        if row["feature"] != PILLAR or row["clean"] != 1 or row["id"] not in sem:
            continue
        dist = math.hypot(row["x_px"] - 1024.0, row["y_px"] - 768.0)
        rows.append({**row, "center_distance_px": dist})
    return pd.DataFrame(sorted(rows, key=lambda r: r["center_distance_px"])[:top_n])


def build_100mg_crop(selected: pd.DataFrame) -> tuple[int, int, int, int]:
    pad = 95
    x0 = max(0, int(selected["x_px"].min() - pad))
    x1 = min(2048, int(selected["x_px"].max() + pad))
    y0 = max(0, int(selected["y_px"].min() - pad))
    y1 = min(1536, int(selected["y_px"].max() + pad))
    return x0, y0, x1, y1


def build_step_crop() -> tuple[int, int, int, int]:
    arr = read_gray(STEP_RAW)
    h, w = arr.shape
    size = min(1600, h, w)
    x0 = (w - size) // 2
    y0 = (h - size) // 2
    return x0, y0, x0 + size, y0 + size


def export_individual_images() -> dict[str, str]:
    selected = select_center_sem_pillars(9)
    crop_100 = build_100mg_crop(selected)
    crop_step = build_step_crop()
    outputs = {
        "100mg_raw": IMAGE_DIR / "100mg_raw.png",
        "100mg_combo": IMAGE_DIR / "100mg_combo.png",
        "100mg_combo_psf_on": IMAGE_DIR / "100mg_combo_psf_on.png",
        "100mg_r61_v16": IMAGE_DIR / "100mg_r61_v16.png",
        "concentric_raw": IMAGE_DIR / "concentric_raw.png",
        "concentric_combo": IMAGE_DIR / "concentric_combo.png",
        "concentric_combo_psf_on": IMAGE_DIR / "concentric_combo_psf_on.png",
        "concentric_r61_v16": IMAGE_DIR / "concentric_r61_v16.png",
    }
    save_individual_image(RAW_100MG, outputs["100mg_raw"], crop_100)
    save_individual_image(COMBO_100MG, outputs["100mg_combo"], crop_100)
    save_individual_image(COMBO_100MG_PSF_ON, outputs["100mg_combo_psf_on"], crop_100)
    save_individual_image(R61_100MG, outputs["100mg_r61_v16"], crop_100)
    save_individual_image(STEP_RAW, outputs["concentric_raw"], crop_step)
    save_individual_image(STEP_COMBO, outputs["concentric_combo"], crop_step)
    save_individual_image(STEP_COMBO_PSF_ON, outputs["concentric_combo_psf_on"], crop_step)
    save_individual_image(STEP_R61, outputs["concentric_r61_v16"], crop_step)
    return {k: str(v) for k, v in outputs.items()}


def build_cd_table() -> pd.DataFrame:
    selected = select_center_sem_pillars(9)
    raw = {r["id"]: r for r in read_feature_rows(RAW_CD) if r["feature"] == PILLAR}
    combo = {r["id"]: r for r in read_feature_rows(COMBO_CD) if r["feature"] == PILLAR}
    r61 = {r["id"]: r for r in read_feature_rows(R61_CD) if r["feature"] == PILLAR}
    sem = read_sem_pillar_diameter()
    out = []
    for pos, row in enumerate(selected.to_dict("records"), start=1):
        rid = int(row["id"])
        sem_nm = sem[rid]
        raw_nm = raw[rid]["diameter_nm"]
        combo_nm = combo[rid]["diameter_nm"]
        r61_nm = r61[rid]["diameter_nm"]
        out.append(
            {
                "position": pos,
                "pillar_id": rid,
                "sem_truth_um": sem_nm / 1000.0,
                "raw_um": raw_nm / 1000.0,
                "combo_um": combo_nm / 1000.0,
                "r61_v16_um": r61_nm / 1000.0,
                "raw_abs_error_nm": abs(raw_nm - sem_nm),
                "combo_abs_error_nm": abs(combo_nm - sem_nm),
                "r61_v16_abs_error_nm": abs(r61_nm - sem_nm),
                "closest_model": min(
                    [
                        ("Raw", abs(raw_nm - sem_nm)),
                        ("Combo", abs(combo_nm - sem_nm)),
                        ("R61 v16", abs(r61_nm - sem_nm)),
                    ],
                    key=lambda item: item[1],
                )[0],
            }
        )
    return pd.DataFrame(out)


def save_table_png(df: pd.DataFrame, out_path: Path, title: str, width: float = 13.0) -> None:
    fig, ax = plt.subplots(figsize=(width, 0.7 + 0.42 * (len(df) + 1)), dpi=180)
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
    table.set_fontsize(8.5)
    table.scale(1, 1.2)
    for (r, c), cell in table.get_celld().items():
        cell.set_edgecolor("#D7DBE7")
        if r == 0:
            cell.set_facecolor("#EAF1FE")
            cell.set_text_props(weight="bold", color="#1F2430")
        else:
            cell.set_facecolor("#FFFFFF" if r % 2 else "#F7F8FB")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def export_cd_table() -> dict[str, str]:
    df = build_cd_table()
    out_csv = TABLE_DIR / "100mg_center9_pillar_cd_raw_combo_r61.csv"
    df.to_csv(out_csv, index=False, encoding="utf-8-sig", float_format="%.6f")
    display = df.copy()
    for col in ["sem_truth_um", "raw_um", "combo_um", "r61_v16_um"]:
        display[col] = display[col].map(lambda v: f"{v:.4f}")
    for col in ["raw_abs_error_nm", "combo_abs_error_nm", "r61_v16_abs_error_nm"]:
        display[col] = display[col].map(lambda v: f"{v:.1f}")
    display = display.rename(
        columns={
            "position": "Pos",
            "pillar_id": "ID",
            "sem_truth_um": "SEM um",
            "raw_um": "Raw um",
            "combo_um": "Combo off um",
            "r61_v16_um": "R61 v16 um",
            "raw_abs_error_nm": "Raw err nm",
            "combo_abs_error_nm": "Combo err nm",
            "r61_v16_abs_error_nm": "R61 err nm",
            "closest_model": "Closest",
        }
    )
    out_png = FIG_DIR / "100mg_center9_pillar_cd_table.png"
    save_table_png(display, out_png, "100MG nearest-center SEM-truthed pillar CD (Combo PSF bypass)", width=16.0)
    return {"csv": str(out_csv), "png": str(out_png)}


def step_summary_one(csv_path: Path, expected_um: float, label: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    df = pd.read_csv(csv_path)
    raw = df[df["case_short"] == "raw_rep0"].copy().reset_index(drop=True)
    v16 = df[df["case_short"] == "v16_rep0"].copy().reset_index(drop=True)
    n = min(len(raw), len(v16))
    per_step = pd.DataFrame(
        {
            "position": np.arange(1, n + 1),
            "expected_um": expected_um,
            "raw_dx_um": raw.loc[: n - 1, "dx_um"].to_numpy(),
            "r61_v16_dx_um": v16.loc[: n - 1, "dx_um"].to_numpy(),
        }
    )
    per_step["raw_abs_error_um"] = (per_step["raw_dx_um"] - expected_um).abs()
    per_step["r61_v16_abs_error_um"] = (per_step["r61_v16_dx_um"] - expected_um).abs()
    raw_std = float(per_step["raw_dx_um"].std(ddof=1))
    v16_std = float(per_step["r61_v16_dx_um"].std(ddof=1))
    summary = pd.DataFrame(
        [
            {
                "step_set": label,
                "expected_um": expected_um,
                "n_steps": n,
                "raw_mean_um": float(per_step["raw_dx_um"].mean()),
                "raw_std_um": raw_std,
                "raw_mae_um": float(per_step["raw_abs_error_um"].mean()),
                "r61_v16_mean_um": float(per_step["r61_v16_dx_um"].mean()),
                "r61_v16_std_um": v16_std,
                "r61_v16_mae_um": float(per_step["r61_v16_abs_error_um"].mean()),
                "std_reduction_um": raw_std - v16_std,
                "std_reduction_pct": (raw_std - v16_std) / raw_std * 100.0 if raw_std else 0.0,
                "r61_v16_closer_steps": int((per_step["r61_v16_abs_error_um"] < per_step["raw_abs_error_um"]).sum()),
            }
        ]
    )
    return per_step, summary


def plot_step_line(per_step: pd.DataFrame, expected_um: float, out_path: Path, title: str) -> None:
    fig, ax = plt.subplots(figsize=(10.5, 6.5), dpi=170)
    x = per_step["position"]
    ax.plot(x, per_step["raw_dx_um"], color="red", marker="s", markersize=4.8, fillstyle="none", linewidth=1.2, label="Raw image")
    ax.plot(x, per_step["r61_v16_dx_um"], color="blue", marker="o", markersize=4.8, fillstyle="none", linewidth=1.2, label="R61 v16 reconstruction")
    ax.axhline(expected_um, color="black", linestyle=(0, (6, 4)), linewidth=1.2, label="Ground truth")
    ax.set_title(title, fontsize=18, fontweight="bold")
    ax.set_xlabel("Position", fontsize=14)
    ax.set_ylabel("Measured displacement (um)", fontsize=14)
    ax.grid(True, axis="y", alpha=0.25)
    ax.legend(loc="upper right", fontsize=11, frameon=True, fancybox=False, edgecolor="black")
    fig.tight_layout()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, facecolor="white")
    plt.close(fig)


def export_step_results() -> dict[str, str]:
    per_1, sum_1 = step_summary_one(GMF_1UM, 1.0, "1.0 um")
    per_05, sum_05 = step_summary_one(GMF_0P5UM, 0.5, "0.5 um")
    per_1.to_csv(TABLE_DIR / "step_displacement_1um_per_step.csv", index=False, encoding="utf-8-sig", float_format="%.9f")
    per_05.to_csv(TABLE_DIR / "step_displacement_0p5um_per_step.csv", index=False, encoding="utf-8-sig", float_format="%.9f")
    summary = pd.concat([sum_1, sum_05], ignore_index=True)
    summary_csv = TABLE_DIR / "step_displacement_summary_with_std.csv"
    summary.to_csv(summary_csv, index=False, encoding="utf-8-sig", float_format="%.9f")

    display = summary.copy()
    for col in display.columns:
        if col.endswith("_um") or col.endswith("_pct"):
            display[col] = display[col].map(lambda v: f"{v:.5f}" if "pct" not in col else f"{v:.1f}%")
    display = display.rename(
        columns={
            "step_set": "Step",
            "expected_um": "Truth um",
            "n_steps": "N",
            "raw_mean_um": "Raw mean",
            "raw_std_um": "Raw std",
            "raw_mae_um": "Raw MAE",
            "r61_v16_mean_um": "R61 mean",
            "r61_v16_std_um": "R61 std",
            "r61_v16_mae_um": "R61 MAE",
            "std_reduction_um": "Std drop",
            "std_reduction_pct": "Std %",
            "r61_v16_closer_steps": "R61 closer",
        }
    )
    summary_png = FIG_DIR / "step_displacement_summary_table.png"
    save_table_png(display, summary_png, "Step displacement result summary", width=18.0)

    fig_1 = FIG_DIR / "step_displacement_1um_line.png"
    fig_05 = FIG_DIR / "step_displacement_0p5um_line.png"
    plot_step_line(per_1, 1.0, fig_1, "Step displacement result - 1.0 um")
    plot_step_line(per_05, 0.5, fig_05, "Step displacement result - 0.5 um")
    return {
        "summary_csv": str(summary_csv),
        "summary_png": str(summary_png),
        "line_1um": str(fig_1),
        "line_0p5um": str(fig_05),
    }


def write_index(images: dict[str, str], cd: dict[str, str], step: dict[str, str]) -> None:
    summary = {
        "images": images,
        "center9_cd": cd,
        "step_displacement": step,
    }
    (TABLE_DIR / "asset_manifest.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    lines = [
        "# Individual Raw / Combo / R61 v16 Assets",
        "",
        "All sample images are exported as independent PNG files, not combined panels.",
        "",
        "## 100MG sample",
        f"- Raw: `{Path(images['100mg_raw']).name}`",
        f"- Combo PSF bypass: `{Path(images['100mg_combo']).name}`",
        f"- Combo PSF on backup: `{Path(images['100mg_combo_psf_on']).name}`",
        f"- R61 v16: `{Path(images['100mg_r61_v16']).name}`",
        "",
        "## Concentric Step sample",
        f"- Raw: `{Path(images['concentric_raw']).name}`",
        f"- Combo PSF bypass: `{Path(images['concentric_combo']).name}`",
        f"- Combo PSF on backup: `{Path(images['concentric_combo_psf_on']).name}`",
        f"- R61 v16: `{Path(images['concentric_r61_v16']).name}`",
        "",
        "## Tables and charts",
        f"- Center 9 pillar CD CSV: `{Path(cd['csv']).name}`",
        f"- Center 9 pillar CD table image: `{Path(cd['png']).name}`",
        f"- Step displacement summary CSV: `{Path(step['summary_csv']).name}`",
        f"- Step displacement summary table image: `{Path(step['summary_png']).name}`",
        f"- Step displacement 1.0 um line chart: `{Path(step['line_1um']).name}`",
        f"- Step displacement 0.5 um line chart: `{Path(step['line_0p5um']).name}`",
    ]
    (ASSET_ROOT / "asset_index.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    IMAGE_DIR.mkdir(parents=True, exist_ok=True)
    FIG_DIR.mkdir(parents=True, exist_ok=True)
    TABLE_DIR.mkdir(parents=True, exist_ok=True)
    images = export_individual_images()
    cd = export_cd_table()
    step = export_step_results()
    write_index(images, cd, step)
    print(json.dumps({"images": images, "center9_cd": cd, "step": step}, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()

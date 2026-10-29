from __future__ import annotations

import csv
import json
import math
import shutil
from pathlib import Path

import cv2
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from PIL import Image, ImageDraw, ImageEnhance, ImageFont, ImageOps
PROJECT_ROOT = Path(__file__).resolve().parents[3]


ROOT = Path(str(PROJECT_ROOT / 'Thesis_MOSR_Evidence'))
ASSET_ROOT = ROOT / "Experiments" / "20260626_training_data_real_slide_assets"
FIG_DIR = ASSET_ROOT / "figures"
TABLE_DIR = ASSET_ROOT / "tables"

R61_DATASET = (
    ROOT
    / "LabSystem_MOSR"
    / "Training_Data"
    / "r61_universal_boundary_generalization"
    / "hs100mg_basler"
    / "r61_universal_boundary_train_motion_texture_step_guard_v16"
)
R61_MANIFEST = R61_DATASET / "manifest.json"

STEP_ROOT = Path(str(PROJECT_ROOT / 'Step_analysis_20260623/clean_step_audit_from_original_pos10_20260623_2218'))
STEP_RAW_DIR = STEP_ROOT / "center2048_bmp"
STEP_R39_DIR = STEP_ROOT / "clean_reconstruction_outputs" / "reconstruct_progress_r39_best_latest_a970_in_center2048_bmp_20260623" / "01_r39_clean_pos10_center2048"
STEP_V14_DIR = STEP_ROOT / "clean_reconstruction_outputs" / "reconstruct_progress_best_tradeoff_in_center2048_bmp_20260623_150217" / "02_v14_clean_pos10_center2048"
STEP_V16_DIR = STEP_ROOT / "clean_reconstruction_outputs" / "reconstruct_progress_best_tradeoff_in_center2048_bmp_20260623_200020" / "03_v16_clean_pos10_center2048"
STEP_FRAME = "VisionTop_20260615173931287.bmp"

GMF_1UM = Path(str(PROJECT_ROOT / 'Step_analysis_20260623/_curated_final_20260624/02_gmf_validation/1um/analysis_center_square_raw_vs_v16_rep0_20260624_0916/gmf_center_square_1um_steps.csv'))
GMF_0P5UM = Path(str(PROJECT_ROOT / 'Step_analysis_20260623/_curated_final_20260624/02_gmf_validation/0p5um/analysis_center_square_raw_vs_v16_rep0_20260624_0p5um/gmf_center_square_0p5um_steps.csv'))

RAW_100MG = ROOT / "20260618_100MG" / "Image__2026-06-18__17-10-31.bmp"
OLD_R57_100MG = (
    ROOT
    / "LabSystem_MOSR"
    / "Reconstruct_Progress"
    / "20260618_100MG_user_recon"
    / "reconstruct_progress_best_tradeoff_in_20260618_100MG_20260620_163628"
    / "r57_1_asym_cd_aligned_best_tradeoff_weakpsf_off"
    / "Image__2026-06-18__17-10-31.bmp"
)
NEW_R61_100MG = (
    ASSET_ROOT
    / "recon_100mg_r61_v16"
    / "reconstruct_progress_best_tradeoff_in_inputs_100mg_single_20260623_200020"
    / "r61_v16_best_tradeoff_100mg"
    / "Image__2026-06-18__17-10-31.bmp"
)

RAW_CD = ROOT / "LabSystem_MOSR" / "Reconstruct_Progress" / "20260618_100MG_user_recon" / "cd_measurement_20260624_corrected_69nm" / "raw_original" / "cd_measurement_per_feature.csv"
OLD_R57_CD = ROOT / "LabSystem_MOSR" / "Reconstruct_Progress" / "20260618_100MG_user_recon" / "cd_measurement_20260621_r57_1_asym_cd_aligned_best_tradeoff" / "cd_measurement_per_feature.csv"
NEW_R61_CD = ASSET_ROOT / "cd_measurement_100mg_r61_v16" / "cd_measurement_per_feature.csv"
SEM_CD = ROOT / ".tmp" / "sem_data" / "sem_cd_36_records.csv"
SEM_CONTACT = ROOT / ".tmp" / "sem_data" / "sem_contact_sheet.png"

PILLAR = "\u5713\u67f1"


def font(size: int, bold: bool = False) -> ImageFont.ImageFont:
    candidates = [
        r"C:\Windows\Fonts\arialbd.ttf" if bold else r"C:\Windows\Fonts\arial.ttf",
        r"C:\Windows\Fonts\calibrib.ttf" if bold else r"C:\Windows\Fonts\calibri.ttf",
    ]
    for candidate in candidates:
        try:
            return ImageFont.truetype(candidate, size)
        except OSError:
            pass
    return ImageFont.load_default()


def read_gray(path: Path) -> np.ndarray:
    data = np.fromfile(str(path), dtype=np.uint8)
    img = cv2.imdecode(data, cv2.IMREAD_GRAYSCALE)
    if img is None:
        raise RuntimeError(f"Cannot read image: {path}")
    return img


def panel_image(path: Path, size: tuple[int, int] = (320, 320), crop: tuple[int, int, int, int] | None = None) -> Image.Image:
    arr = read_gray(path)
    im = Image.fromarray(arr)
    if crop is not None:
        im = im.crop(crop)
    im = ImageOps.autocontrast(im)
    im = ImageEnhance.Contrast(im).enhance(1.12)
    im.thumbnail(size, Image.Resampling.LANCZOS)
    canvas = Image.new("RGB", size, "white")
    canvas.paste(im.convert("RGB"), ((size[0] - im.width) // 2, (size[1] - im.height) // 2))
    return canvas


def overlay_boundary(src_path: Path, boundary_path: Path, size: tuple[int, int] = (320, 320)) -> Image.Image:
    src = read_gray(src_path)
    boundary = read_gray(boundary_path)
    src_img = ImageOps.autocontrast(Image.fromarray(src)).convert("RGB")
    b = cv2.resize(boundary, (src.shape[1], src.shape[0]), interpolation=cv2.INTER_NEAREST)
    rgb = np.asarray(src_img).copy()
    mask = b > 20
    rgb[mask] = [235, 45, 45]
    im = Image.fromarray(rgb)
    im.thumbnail(size, Image.Resampling.LANCZOS)
    canvas = Image.new("RGB", size, "white")
    canvas.paste(im, ((size[0] - im.width) // 2, (size[1] - im.height) // 2))
    return canvas


def make_sheet(title: str, rows: list[tuple[str, list[tuple[str, Image.Image]]]], out_path: Path) -> None:
    title_font = font(32, bold=True)
    row_font = font(19, bold=True)
    cell_font = font(18)
    panel_w, panel_h = 320, 320
    label_h = 34
    left_w = 260
    margin = 24
    row_gap = 24
    columns = max(len(cols) for _, cols in rows)
    width = margin * 2 + left_w + columns * panel_w
    height = margin * 2 + 48 + len(rows) * (label_h + panel_h) + (len(rows) - 1) * row_gap
    canvas = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(canvas)
    draw.text((margin, margin), title, fill=(20, 20, 20), font=title_font)
    y = margin + 58
    for row_label, cols in rows:
        draw.text((margin, y + label_h + 8), row_label, fill=(20, 20, 20), font=row_font)
        x = margin + left_w
        for cell_label, image in cols:
            draw.rectangle((x, y, x + panel_w - 1, y + label_h + panel_h - 1), outline=(210, 210, 210), width=1)
            draw.text((x + 8, y + 7), cell_label, fill=(35, 35, 35), font=cell_font)
            canvas.paste(image, (x, y + label_h))
            x += panel_w
        y += label_h + panel_h + row_gap
    out_path.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(out_path, quality=95)


def load_manifest() -> dict:
    return json.loads(R61_MANIFEST.read_text(encoding="utf-8"))


def find_pair(manifest: dict, role: str, feature: str | None = None, sequence_id: str | None = None, frame: int | None = None) -> dict:
    for pair in manifest["pairs"]:
        if pair.get("role") != role:
            continue
        if feature is not None and pair.get("feature") != feature:
            continue
        if sequence_id is not None and pair.get("motion_sequence_id") != sequence_id:
            continue
        if frame is not None and int(pair.get("motion_frame", -1)) != frame:
            continue
        return pair
    raise KeyError((role, feature, sequence_id, frame))


def make_training_sheets() -> list[Path]:
    manifest = load_manifest()
    outputs: list[Path] = []

    sem_rows = []
    for feature in ["pillar", "via"]:
        pair = find_pair(manifest, "sem_truth_anchor", feature=feature)
        src = R61_DATASET / pair["package_src"]
        lbl = R61_DATASET / pair["package_lbl"]
        bnd = R61_DATASET / pair["geometry_boundary"]
        sem_rows.append(
            (
                f"SEM anchor: {feature}",
                [
                    ("real input crop", panel_image(src)),
                    ("SEM-guided target", panel_image(lbl)),
                    ("boundary overlay", overlay_boundary(src, bnd)),
                ],
            )
        )
    out = FIG_DIR / "01_training_real_sem_truth_anchor_examples.png"
    make_sheet("R61 training data: real 100MG SEM-truth anchors", sem_rows, out)
    outputs.append(out)

    guard_rows = []
    for feature in ["pillar", "via"]:
        pair = find_pair(manifest, "sequence_guard", feature=feature)
        src = R61_DATASET / pair["package_src"]
        lbl = R61_DATASET / pair["package_lbl"]
        bnd = R61_DATASET / pair["geometry_boundary"]
        guard_rows.append(
            (
                f"Sequence guard: {feature}",
                [
                    ("real input crop", panel_image(src)),
                    ("guarded target", panel_image(lbl)),
                    ("boundary overlay", overlay_boundary(src, bnd)),
                ],
            )
        )
    out = FIG_DIR / "02_training_real_sequence_guard_examples.png"
    make_sheet("R61 training data: real sequence guard examples", guard_rows, out)
    outputs.append(out)

    f0 = find_pair(manifest, "motion_synthetic", frame=0)
    seq = f0["motion_sequence_id"]
    f1 = find_pair(manifest, "motion_synthetic", sequence_id=seq, frame=1)
    rows = [
        (
            "Known-motion pair",
            [
                ("frame 0 input", panel_image(R61_DATASET / f0["package_src"])),
                ("frame 1 input", panel_image(R61_DATASET / f1["package_src"])),
                ("frame 1 target", panel_image(R61_DATASET / f1["package_lbl"])),
                ("frame 1 boundary", overlay_boundary(R61_DATASET / f1["package_src"], R61_DATASET / f1["geometry_boundary"])),
            ],
        )
    ]
    out = FIG_DIR / "03_training_motion_synthetic_pair_example.png"
    make_sheet("R61 training data: known-motion synthetic supervision", rows, out)
    outputs.append(out)

    if SEM_CONTACT.exists():
        copied = FIG_DIR / "04_100mg_sem_reference_contact_sheet.png"
        shutil.copy2(SEM_CONTACT, copied)
        outputs.append(copied)
    return outputs


def center_crop_for(path: Path, crop_size: int) -> tuple[int, int, int, int]:
    arr = read_gray(path)
    h, w = arr.shape
    half = crop_size // 2
    cx, cy = w // 2, h // 2
    return (max(0, cx - half), max(0, cy - half), min(w, cx + half), min(h, cy + half))


def make_reconstruction_sheets() -> list[Path]:
    outputs: list[Path] = []
    crop = center_crop_for(STEP_RAW_DIR / STEP_FRAME, 1150)
    rows = [
        (
            "Step sample",
            [
                ("Raw", panel_image(STEP_RAW_DIR / STEP_FRAME, crop=crop)),
                ("Old R39", panel_image(STEP_R39_DIR / STEP_FRAME, crop=crop)),
                ("R61 v14", panel_image(STEP_V14_DIR / STEP_FRAME, crop=crop)),
                ("R61 v16", panel_image(STEP_V16_DIR / STEP_FRAME, crop=crop)),
            ],
        )
    ]
    out = FIG_DIR / "05_step_real_reconstruction_raw_old_new_contact.png"
    make_sheet("Real reconstruction comparison: Step sample center crop", rows, out)
    outputs.append(out)

    raw_rows = read_feature_rows(RAW_CD)
    selected = select_center_sem_pillars(raw_rows, top_n=12)
    xs = [r["x_px"] for r in selected]
    ys = [r["y_px"] for r in selected]
    pad = 100
    x0, x1 = max(0, int(min(xs) - pad)), min(2048, int(max(xs) + pad))
    y0, y1 = max(0, int(min(ys) - pad)), min(1536, int(max(ys) + pad))
    crop100 = (x0, y0, x1, y1)
    rows = [
        (
            "100MG center pillars",
            [
                ("Raw", panel_image(RAW_100MG, crop=crop100)),
                ("Old R57", panel_image(OLD_R57_100MG, crop=crop100)),
                ("R61 v16", panel_image(NEW_R61_100MG, crop=crop100)),
            ],
        )
    ]
    out = FIG_DIR / "06_100mg_real_reconstruction_raw_old_v16_center_crop.png"
    make_sheet("Real reconstruction comparison: 100MG measured region", rows, out)
    outputs.append(out)
    return outputs


def read_feature_rows(path: Path) -> list[dict]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    out = []
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


def read_sem() -> dict[int, float]:
    with SEM_CD.open("r", encoding="utf-8-sig", newline="") as f:
        return {int(row["index"]): float(row["pillar_diameter_nm"]) for row in csv.DictReader(f)}


def select_center_sem_pillars(raw_rows: list[dict], top_n: int) -> list[dict]:
    sem = read_sem()
    candidates = []
    for row in raw_rows:
        if row["feature"] != PILLAR or row["clean"] != 1 or row["id"] not in sem:
            continue
        dist = math.hypot(row["x_px"] - 1024.0, row["y_px"] - 768.0)
        candidates.append({**row, "center_distance_px": dist})
    return sorted(candidates, key=lambda r: r["center_distance_px"])[:top_n]


def join_cd_table(top_n: int | None = None) -> pd.DataFrame:
    raw = read_feature_rows(RAW_CD)
    r57 = {r["id"]: r for r in read_feature_rows(OLD_R57_CD) if r["feature"] == PILLAR}
    v16 = {r["id"]: r for r in read_feature_rows(NEW_R61_CD) if r["feature"] == PILLAR}
    sem = read_sem()
    selected = select_center_sem_pillars(raw, top_n=999)
    if top_n is not None:
        selected = selected[:top_n]
    rows = []
    for pos, row in enumerate(selected, start=1):
        rid = row["id"]
        sem_nm = sem[rid]
        raw_nm = row["diameter_nm"]
        r57_nm = r57[rid]["diameter_nm"]
        v16_nm = v16[rid]["diameter_nm"]
        rows.append(
            {
                "position": pos,
                "pillar_id": rid,
                "x_px": row["x_px"],
                "y_px": row["y_px"],
                "center_distance_px": row["center_distance_px"],
                "sem_truth_um": sem_nm / 1000.0,
                "raw_um": raw_nm / 1000.0,
                "old_r57_um": r57_nm / 1000.0,
                "r61_v16_um": v16_nm / 1000.0,
                "raw_abs_error_nm": abs(raw_nm - sem_nm),
                "old_r57_abs_error_nm": abs(r57_nm - sem_nm),
                "r61_v16_abs_error_nm": abs(v16_nm - sem_nm),
                "r61_v16_closer_than_raw": abs(v16_nm - sem_nm) < abs(raw_nm - sem_nm),
                "r61_v16_closer_than_old_r57": abs(v16_nm - sem_nm) < abs(r57_nm - sem_nm),
            }
        )
    return pd.DataFrame(rows)


def plot_cd(df: pd.DataFrame, out_path: Path, title: str) -> None:
    fig, ax = plt.subplots(figsize=(10.5, 7.0), dpi=160)
    x = df["position"]
    ax.plot(x, df["raw_um"], color="red", marker="s", markersize=6, fillstyle="none", linewidth=1.4, label="Raw image")
    ax.plot(x, df["old_r57_um"], color="#9a6a00", marker="^", markersize=6, fillstyle="none", linewidth=1.3, label="Old reconstruction (R57)")
    ax.plot(x, df["r61_v16_um"], color="blue", marker="o", markersize=6, fillstyle="none", linewidth=1.4, label="R61 v16 reconstruction")
    ax.plot(x, df["sem_truth_um"], color="black", linestyle=(0, (6, 4)), linewidth=1.3, marker=".", markersize=4, label="SEM ground truth")
    ax.set_title(title, fontsize=18, weight="bold")
    ax.set_xlabel("Position (nearest SEM-truthed pillars)", fontsize=14)
    ax.set_ylabel("Critical dimension result (um)", fontsize=14)
    ax.set_xticks(x)
    ax.set_xticklabels([f"{p}\nID {i}" for p, i in zip(df["position"], df["pillar_id"])], fontsize=9)
    ax.tick_params(axis="y", labelsize=12)
    ax.grid(True, axis="y", alpha=0.22)
    ax.legend(loc="upper right", fontsize=11, frameon=True, fancybox=False, edgecolor="black")
    fig.tight_layout()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path)
    plt.close(fig)


def plot_cd_raw_v16_only(df: pd.DataFrame, out_path: Path, title: str) -> None:
    fig, ax = plt.subplots(figsize=(10.5, 7.0), dpi=160)
    x = df["position"]
    ax.plot(x, df["raw_um"], color="red", marker="s", markersize=6, fillstyle="none", linewidth=1.4, label="Raw image")
    ax.plot(x, df["r61_v16_um"], color="blue", marker="o", markersize=6, fillstyle="none", linewidth=1.4, label="R61 v16 reconstruction")
    ax.plot(x, df["sem_truth_um"], color="black", linestyle=(0, (6, 4)), linewidth=1.3, marker=".", markersize=4, label="SEM ground truth")
    ax.set_title(title, fontsize=18, weight="bold")
    ax.set_xlabel("Position (nearest SEM-truthed pillars)", fontsize=14)
    ax.set_ylabel("Critical dimension result (um)", fontsize=14)
    ax.set_xticks(x)
    ax.set_xticklabels([f"{p}\nID {i}" for p, i in zip(df["position"], df["pillar_id"])], fontsize=9)
    ax.tick_params(axis="y", labelsize=12)
    ax.grid(True, axis="y", alpha=0.22)
    ax.legend(loc="upper right", fontsize=11, frameon=True, fancybox=False, edgecolor="black")
    fig.tight_layout()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path)
    plt.close(fig)


def plot_gmf(csv_path: Path, expected_um: float, out_path: Path, title: str) -> dict:
    df = pd.read_csv(csv_path)
    raw = df[df["case_short"] == "raw_rep0"].copy().reset_index(drop=True)
    v16 = df[df["case_short"] == "v16_rep0"].copy().reset_index(drop=True)
    raw["position"] = np.arange(1, len(raw) + 1)
    v16["position"] = np.arange(1, len(v16) + 1)
    n = min(len(raw), len(v16))
    fig, ax = plt.subplots(figsize=(10.5, 7.0), dpi=160)
    ax.plot(raw["position"], raw["dx_um"], color="red", marker="s", markersize=5.5, fillstyle="none", linewidth=1.2, label="Raw image")
    ax.plot(v16["position"], v16["dx_um"], color="blue", marker="o", markersize=5.5, fillstyle="none", linewidth=1.2, label="R61 v16 reconstruction")
    ax.axhline(expected_um, color="black", linestyle=(0, (6, 4)), linewidth=1.2, label="Ground truth")
    ax.set_title(title, fontsize=18, weight="bold")
    ax.set_xlabel("Position", fontsize=14)
    ax.set_ylabel("Measured displacement (um)", fontsize=14)
    ax.set_xlim(0.5, max(len(raw), len(v16)) + 0.5)
    ax.grid(True, axis="y", alpha=0.22)
    ax.legend(loc="upper right", fontsize=11, frameon=True, fancybox=False, edgecolor="black")
    fig.tight_layout()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path)
    plt.close(fig)
    paired = pd.DataFrame(
        {
            "position": np.arange(1, n + 1),
            "raw_dx_um": raw.loc[: n - 1, "dx_um"].to_numpy(),
            "v16_dx_um": v16.loc[: n - 1, "dx_um"].to_numpy(),
        }
    )
    paired["expected_um"] = expected_um
    paired["raw_abs_error_um"] = (paired["raw_dx_um"] - expected_um).abs()
    paired["v16_abs_error_um"] = (paired["v16_dx_um"] - expected_um).abs()
    paired["v16_closer_than_raw"] = paired["v16_abs_error_um"] < paired["raw_abs_error_um"]
    table_path = TABLE_DIR / (out_path.stem + ".csv")
    paired.to_csv(table_path, index=False, encoding="utf-8-sig")
    return {
        "points": int(n),
        "raw_mae_um": float(paired["raw_abs_error_um"].mean()),
        "v16_mae_um": float(paired["v16_abs_error_um"].mean()),
        "v16_closer_count": int(paired["v16_closer_than_raw"].sum()),
        "table": str(table_path),
    }


def make_cd_outputs() -> dict:
    df12 = join_cd_table(top_n=12)
    df36 = join_cd_table(top_n=None)
    center_delta = df12["r61_v16_abs_error_nm"] - df12["raw_abs_error_nm"]
    all_delta = df36["r61_v16_abs_error_nm"] - df36["raw_abs_error_nm"]
    TABLE_DIR.mkdir(parents=True, exist_ok=True)
    df12.to_csv(TABLE_DIR / "100mg_center12_sem_truthed_pillar_cd.csv", index=False, encoding="utf-8-sig")
    df36.to_csv(TABLE_DIR / "100mg_sem_truthed_pillar_cd_all_clean.csv", index=False, encoding="utf-8-sig")
    plot_cd(df12, FIG_DIR / "07_100mg_center12_pillar_cd_position_line.png", "100MG pillar CD result - center SEM-truthed positions")
    plot_cd_raw_v16_only(df12, FIG_DIR / "07b_100mg_center12_pillar_cd_raw_v16_truth_line.png", "100MG pillar CD result - Raw vs R61 v16")
    plot_cd(df36, FIG_DIR / "08_100mg_all_sem_truthed_pillar_cd_position_line.png", "100MG pillar CD result - all clean SEM-truthed positions")
    return {
        "center12_points": int(len(df12)),
        "all_sem_clean_points": int(len(df36)),
        "center12_v16_closer_than_raw": int(df12["r61_v16_closer_than_raw"].sum()),
        "center12_v16_equal_to_raw": int((center_delta.abs() <= 1e-9).sum()),
        "center12_v16_worse_than_raw": int((center_delta > 1e-9).sum()),
        "center12_v16_closer_than_old": int(df12["r61_v16_closer_than_old_r57"].sum()),
        "center12_raw_mae_nm": float(df12["raw_abs_error_nm"].mean()),
        "center12_old_r57_mae_nm": float(df12["old_r57_abs_error_nm"].mean()),
        "center12_r61_v16_mae_nm": float(df12["r61_v16_abs_error_nm"].mean()),
        "all_v16_closer_than_raw": int(df36["r61_v16_closer_than_raw"].sum()),
        "all_v16_equal_to_raw": int((all_delta.abs() <= 1e-9).sum()),
        "all_v16_worse_than_raw": int((all_delta > 1e-9).sum()),
        "all_v16_closer_than_old": int(df36["r61_v16_closer_than_old_r57"].sum()),
        "all_raw_mae_nm": float(df36["raw_abs_error_nm"].mean()),
        "all_old_r57_mae_nm": float(df36["old_r57_abs_error_nm"].mean()),
        "all_r61_v16_mae_nm": float(df36["r61_v16_abs_error_nm"].mean()),
    }


def write_index(summary: dict, figures: list[Path]) -> None:
    lines = [
        "# 20260626 Real Slide Assets",
        "",
        "This folder collects slide-ready assets for the R61 v16 training-data and validation story.",
        "",
        "## Figures",
    ]
    for fig in sorted(figures):
        lines.append(f"- `{fig.name}`")
    lines += [
        "",
        "## Numeric checks",
        f"- 100MG center 12 SEM-truthed pillars: R61 v16 is closer than Raw on {summary['cd']['center12_v16_closer_than_raw']} / {summary['cd']['center12_points']} points.",
        f"- 100MG center 12 SEM-truthed pillars: R61 v16 is equal to Raw on {summary['cd']['center12_v16_equal_to_raw']} / {summary['cd']['center12_points']} points and worse on {summary['cd']['center12_v16_worse_than_raw']} / {summary['cd']['center12_points']} points.",
        f"- 100MG center 12 SEM-truthed pillars: R61 v16 is closer than old R57 on {summary['cd']['center12_v16_closer_than_old']} / {summary['cd']['center12_points']} points.",
        f"- Center 12 MAE: Raw {summary['cd']['center12_raw_mae_nm']:.2f} nm, old R57 {summary['cd']['center12_old_r57_mae_nm']:.2f} nm, R61 v16 {summary['cd']['center12_r61_v16_mae_nm']:.2f} nm.",
        f"- 1.0 um Step MAE: Raw {summary['gmf_1um']['raw_mae_um']:.5f} um, R61 v16 {summary['gmf_1um']['v16_mae_um']:.5f} um.",
        f"- 0.5 um Step MAE: Raw {summary['gmf_0p5um']['raw_mae_um']:.5f} um, R61 v16 {summary['gmf_0p5um']['v16_mae_um']:.5f} um.",
        "",
        "## Tables",
        "- `100mg_center12_sem_truthed_pillar_cd.csv`",
        "- `100mg_sem_truthed_pillar_cd_all_clean.csv`",
        "- `09_step_displacement_1um_position_line.csv`",
        "- `10_step_displacement_0p5um_position_line.csv`",
        "- `summary.json`",
    ]
    (ASSET_ROOT / "asset_index.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    FIG_DIR.mkdir(parents=True, exist_ok=True)
    TABLE_DIR.mkdir(parents=True, exist_ok=True)
    figures: list[Path] = []
    figures += make_training_sheets()
    figures += make_reconstruction_sheets()
    cd_summary = make_cd_outputs()
    gmf_1 = plot_gmf(GMF_1UM, 1.0, FIG_DIR / "09_step_displacement_1um_position_line.png", "Displacement measurement result - 1.0 um step")
    gmf_05 = plot_gmf(GMF_0P5UM, 0.5, FIG_DIR / "10_step_displacement_0p5um_position_line.png", "Displacement measurement result - 0.5 um step")
    figures += [
        FIG_DIR / "07_100mg_center12_pillar_cd_position_line.png",
        FIG_DIR / "07b_100mg_center12_pillar_cd_raw_v16_truth_line.png",
        FIG_DIR / "08_100mg_all_sem_truthed_pillar_cd_position_line.png",
        FIG_DIR / "09_step_displacement_1um_position_line.png",
        FIG_DIR / "10_step_displacement_0p5um_position_line.png",
    ]
    summary = {"cd": cd_summary, "gmf_1um": gmf_1, "gmf_0p5um": gmf_05, "figures": [str(p) for p in figures]}
    (TABLE_DIR / "summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    write_index(summary, figures)
    print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()

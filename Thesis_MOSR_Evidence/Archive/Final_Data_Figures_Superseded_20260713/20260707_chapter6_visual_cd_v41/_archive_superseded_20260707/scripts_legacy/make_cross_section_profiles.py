from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import cv2
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
from matplotlib.patches import Rectangle
from PIL import Image, ImageDraw


SCRIPT_DIR = Path(__file__).resolve().parent
THIS_DIR = SCRIPT_DIR.parent if SCRIPT_DIR.name == "scripts" else SCRIPT_DIR
BASE_SCRIPT = SCRIPT_DIR / "make_chapter6_visual_cd_assets.py"
FIG_DIR = THIS_DIR / "figures"
TABLE_DIR = THIS_DIR / "tables"
IMAGE_DIR = THIS_DIR / "images"


TOKENS = {
    "surface": "#FCFCFD",
    "panel": "#FFFFFF",
    "ink": "#1F2430",
    "muted": "#6F768A",
    "grid": "#E6E8F0",
    "axis": "#D7DBE7",
}

SERIES_STYLE = {
    "Raw": {"color": "#E41A1C", "linestyle": "-", "linewidth": 1.35},
    "COMBO off": {"color": "#984EA3", "linestyle": "-", "linewidth": 1.05},
    "R61 v16": {"color": "#377EB8", "linestyle": "-", "linewidth": 1.20},
    "V41": {"color": "#4DAF4A", "linestyle": "-", "linewidth": 1.20},
}


def load_base_module():
    spec = importlib.util.spec_from_file_location("chapter6_assets", BASE_SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {BASE_SCRIPT}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def use_chart_theme() -> None:
    sns.set_theme(
        style="whitegrid",
        rc={
            "figure.facecolor": TOKENS["surface"],
            "axes.facecolor": TOKENS["panel"],
            "axes.edgecolor": TOKENS["axis"],
            "axes.labelcolor": TOKENS["ink"],
            "grid.color": TOKENS["grid"],
            "grid.linewidth": 0.8,
            "font.family": "sans-serif",
            "font.sans-serif": ["Aptos", "Inter", "Segoe UI", "DejaVu Sans", "Arial", "sans-serif"],
        },
    )


def add_header(fig, ax, title: str, subtitle: str) -> None:
    ax.set_title("")
    fig.subplots_adjust(top=0.84)
    left = ax.get_position().x0
    fig.text(left, 0.975, title, ha="left", va="top", fontsize=15, fontweight="semibold", color=TOKENS["ink"])
    fig.text(left, 0.925, subtitle, ha="left", va="top", fontsize=9.5, color=TOKENS["muted"])
    sns.despine(ax=ax)


def robust_profile(signal: np.ndarray, y_px: int, x0: int, x1: int, half_band: int) -> np.ndarray:
    y0 = max(0, y_px - half_band)
    y1 = min(signal.shape[0], y_px + half_band + 1)
    band = signal[y0:y1, x0:x1]
    return np.nanmean(band, axis=0)


def normalize_profile(profile: np.ndarray) -> np.ndarray:
    lo, hi = np.nanpercentile(profile, [2.0, 98.0])
    if hi <= lo:
        return np.zeros_like(profile, dtype=np.float32)
    return np.clip((profile - lo) / (hi - lo), 0.0, 1.05).astype(np.float32)


def choose_cross_section(base) -> dict[str, object]:
    rows = pd.DataFrame(base.read_feature_rows(base.RAW_CD))
    rows = rows[(rows["feature"] == base.PILLAR) & (rows["clean"] == 1)].copy()
    rows["y_bin"] = (rows["y_px"] / 80.0).round().astype(int)
    grouped = (
        rows.groupby("y_bin")
        .agg(count=("id", "count"), y_px=("y_px", "median"), x_min=("x_px", "min"), x_max=("x_px", "max"))
        .reset_index()
    )
    grouped = grouped[grouped["count"] >= 4].copy()
    if grouped.empty:
        raise RuntimeError("cannot find a stable pillar row for cross-section")
    grouped["center_score"] = (grouped["y_px"] - 768.0).abs()
    row_info = grouped.sort_values(["center_score", "count"], ascending=[True, False]).iloc[0]
    selected_row = rows[rows["y_bin"] == int(row_info["y_bin"])].sort_values("x_px").copy()
    y_px = int(round(float(selected_row["y_px"].median())))
    x0 = max(0, int(float(selected_row["x_px"].min()) - 95))
    x1 = min(2048, int(float(selected_row["x_px"].max()) + 95))
    row_mid_x = float(selected_row["x_px"].median())
    center_pillar = selected_row.iloc[(selected_row["x_px"] - row_mid_x).abs().to_numpy().argmin()]
    edge_x = int(round(float(center_pillar["x_px"]) - float(center_pillar["radius_px"])))
    zoom_x0 = max(x0, edge_x - 38)
    zoom_x1 = min(x1, edge_x + 38)
    return {
        "y_px": y_px,
        "x0": x0,
        "x1": x1,
        "zoom_x0": zoom_x0,
        "zoom_x1": zoom_x1,
        "half_band": 3,
        "row_pillars": selected_row[["id", "x_px", "y_px", "radius_px"]].to_dict("records"),
        "zoom_pillar_id": int(center_pillar["id"]),
        "zoom_edge_x_px": edge_x,
    }


def build_profile_table(base, section: dict[str, object]) -> pd.DataFrame:
    x0 = int(section["x0"])
    x1 = int(section["x1"])
    y_px = int(section["y_px"])
    half_band = int(section["half_band"])
    x = np.arange(x0, x1)
    out = pd.DataFrame({"x_px": x})
    case_labels = {
        "raw": "Raw",
        "combo_psf_bypass": "COMBO off",
        "r61_v16": "R61 v16",
        "v41_current": "V41",
    }
    for case, label in case_labels.items():
        img = base.read_gray(base.IMAGE_CASES_100MG[case]).astype(np.float32) / 255.0
        signal = 1.0 - img
        profile = robust_profile(signal, y_px, x0, x1, half_band)
        out[label] = normalize_profile(profile)
    return out


def plot_profile(df: pd.DataFrame, section: dict[str, object], out_stem: Path, *, zoom: bool) -> None:
    use_chart_theme()
    if zoom:
        plot_df = df[(df["x_px"] >= int(section["zoom_x0"])) & (df["x_px"] <= int(section["zoom_x1"]))].copy()
        title = "100MG boundary cross-section profile, zoom"
        subtitle = (
            f"Same horizontal line as full profile; zoom around pillar {section['zoom_pillar_id']} "
            f"left edge near x={section['zoom_edge_x_px']} px."
        )
        figsize = (8.2, 5.2)
    else:
        plot_df = df.copy()
        title = "100MG cross-section profile"
        subtitle = (
            f"Horizontal profile at y={section['y_px']} px, averaged across "
            f"{int(section['half_band']) * 2 + 1} rows; dark pillars are plotted as higher intensity."
        )
        figsize = (12.5, 5.6)

    fig, ax = plt.subplots(figsize=figsize, dpi=180)
    for label, style in SERIES_STYLE.items():
        sns.lineplot(
            data=plot_df,
            x="x_px",
            y=label,
            ax=ax,
            color=style["color"],
            linestyle=style["linestyle"],
            linewidth=style["linewidth"],
            label=label,
            errorbar=None,
        )
    if not zoom:
        rect = Rectangle(
            (int(section["zoom_x0"]), 0.04),
            int(section["zoom_x1"]) - int(section["zoom_x0"]),
            1.02,
            fill=False,
            edgecolor="#D62728",
            linewidth=1.6,
        )
        ax.add_patch(rect)
    ax.set_xlabel("Horizontal position (pixel)")
    ax.set_ylabel("Normalized dark intensity")
    ax.set_ylim(-0.02, 1.10)
    ax.legend(
        loc="lower right" if zoom else "upper right",
        frameon=True,
        fancybox=False,
        edgecolor=TOKENS["ink"],
    )
    add_header(fig, ax, title, subtitle)
    fig.savefig(out_stem.with_suffix(".png"), bbox_inches="tight", facecolor=TOKENS["surface"])
    fig.savefig(out_stem.with_suffix(".svg"), bbox_inches="tight", facecolor=TOKENS["surface"])
    plt.close(fig)


def save_overlay(base, section: dict[str, object], out_path: Path) -> None:
    img = Image.fromarray(base.normalize_u8(base.read_gray(base.IMAGE_CASES_100MG["raw"]))).convert("RGB")
    draw = ImageDraw.Draw(img)
    y = int(section["y_px"])
    x0 = int(section["x0"])
    x1 = int(section["x1"])
    half_band = int(section["half_band"])
    draw.rectangle([x0, y - half_band, x1, y + half_band], outline=(230, 30, 30), width=3)
    draw.rectangle(
        [int(section["zoom_x0"]), y - 45, int(section["zoom_x1"]), y + 45],
        outline=(30, 100, 230),
        width=3,
    )
    crop = img.crop((max(0, x0 - 80), max(0, y - 190), min(img.width, x1 + 80), min(img.height, y + 190)))
    out_path.parent.mkdir(parents=True, exist_ok=True)
    crop.save(out_path)


def main() -> None:
    base = load_base_module()
    FIG_DIR.mkdir(parents=True, exist_ok=True)
    TABLE_DIR.mkdir(parents=True, exist_ok=True)
    IMAGE_DIR.mkdir(parents=True, exist_ok=True)

    section = choose_cross_section(base)
    df = build_profile_table(base, section)
    csv_path = TABLE_DIR / "100mg_cross_section_profile_raw_combo_r61_v41.csv"
    df.to_csv(csv_path, index=False, encoding="utf-8-sig", float_format="%.6f")

    meta_path = TABLE_DIR / "100mg_cross_section_profile_metadata.json"
    meta_path.write_text(json.dumps(section, indent=2, ensure_ascii=False), encoding="utf-8")

    full_stem = FIG_DIR / "100mg_cross_section_profile_full"
    zoom_stem = FIG_DIR / "100mg_cross_section_profile_zoom"
    plot_profile(df, section, full_stem, zoom=False)
    plot_profile(df, section, zoom_stem, zoom=True)
    overlay_path = IMAGE_DIR / "100mg_cross_section_overlay_raw.png"
    save_overlay(base, section, overlay_path)

    print(
        json.dumps(
            {
                "profile_csv": str(csv_path),
                "metadata": str(meta_path),
                "full_png": str(full_stem.with_suffix(".png")),
                "zoom_png": str(zoom_stem.with_suffix(".png")),
                "overlay": str(overlay_path),
            },
            indent=2,
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()

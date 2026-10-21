from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import cv2
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


SCRIPT_DIR = Path(__file__).resolve().parent
THIS_DIR = SCRIPT_DIR.parent if SCRIPT_DIR.name == "scripts" else SCRIPT_DIR
BASE_SCRIPT = SCRIPT_DIR / "make_chapter6_visual_cd_assets.py"
FIG_DIR = THIS_DIR / "figures"
TABLE_DIR = THIS_DIR / "tables"

CASE_LABELS = {
    "raw": "Raw",
    "combo_psf_bypass": "COMBO off",
    "r61_v16": "R61 v16",
    "v41_current": "V41",
}

CASE_COLORS = {
    "Raw": "#E41A1C",
    "COMBO off": "#984EA3",
    "R61 v16": "#377EB8",
    "V41": "#4DAF4A",
}


def load_base_module():
    spec = importlib.util.spec_from_file_location("chapter6_assets", BASE_SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {BASE_SCRIPT}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def sample_profile(img: np.ndarray, x_px: float, y_px: float, radius_px: float, half_band: int = 3) -> tuple[np.ndarray, np.ndarray]:
    h, w = img.shape
    margin = max(28.0, radius_px * 1.35)
    x0 = max(0, int(np.floor(x_px - radius_px - margin)))
    x1 = min(w, int(np.ceil(x_px + radius_px + margin)))
    yy = int(round(y_px))
    y0 = max(0, yy - half_band)
    y1 = min(h, yy + half_band + 1)
    dark = 1.0 - img.astype(np.float32) / 255.0
    profile = dark[y0:y1, x0:x1].mean(axis=0)
    return np.arange(x0, x1, dtype=np.float32), profile.astype(np.float32)


def interpolate_crossing(x: np.ndarray, y: np.ndarray, idx0: int, idx1: int, thr: float) -> float:
    x0, x1 = float(x[idx0]), float(x[idx1])
    y0, y1 = float(y[idx0]), float(y[idx1])
    if abs(y1 - y0) < 1e-8:
        return (x0 + x1) * 0.5
    t = (thr - y0) / (y1 - y0)
    return x0 + float(np.clip(t, 0.0, 1.0)) * (x1 - x0)


def find_crossing(profile_x: np.ndarray, profile_y: np.ndarray, threshold: float, *, side: str, center_x: float) -> float | None:
    if side == "left":
        candidates = np.where((profile_x[:-1] < center_x) & (profile_y[:-1] < threshold) & (profile_y[1:] >= threshold))[0]
        if len(candidates) == 0:
            return None
        idx = candidates[np.argmin(np.abs(profile_x[candidates] - center_x))]
        return interpolate_crossing(profile_x, profile_y, int(idx), int(idx + 1), threshold)
    if side == "right":
        candidates = np.where((profile_x[:-1] > center_x) & (profile_y[:-1] >= threshold) & (profile_y[1:] < threshold))[0]
        if len(candidates) == 0:
            return None
        idx = candidates[np.argmin(np.abs(profile_x[candidates] - center_x))]
        return interpolate_crossing(profile_x, profile_y, int(idx), int(idx + 1), threshold)
    raise ValueError(side)


def measure_width(profile_x: np.ndarray, profile_y: np.ndarray, center_x: float, radius_px: float) -> dict[str, float | str]:
    center_mask = np.abs(profile_x - center_x) <= max(3.0, radius_px * 0.42)
    bg_mask = (profile_x < center_x - radius_px * 1.45) | (profile_x > center_x + radius_px * 1.45)
    if center_mask.sum() < 3 or bg_mask.sum() < 3:
        return {"status": "bad_window"}
    high = float(np.percentile(profile_y[center_mask], 80))
    low = float(np.percentile(profile_y[bg_mask], 20))
    if high <= low + 1e-5:
        return {"status": "bad_contrast", "high": high, "low": low}
    threshold = low + 0.5 * (high - low)
    left = find_crossing(profile_x, profile_y, threshold, side="left", center_x=center_x)
    right = find_crossing(profile_x, profile_y, threshold, side="right", center_x=center_x)
    if left is None or right is None or right <= left:
        return {"status": "bad_crossing", "high": high, "low": low, "threshold": threshold}
    return {
        "status": "ok",
        "left_edge_px": float(left),
        "right_edge_px": float(right),
        "width_px": float(right - left),
        "high": high,
        "low": low,
        "threshold": threshold,
    }


def measure_case(base, case: str, img: np.ndarray, selected: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for position, row in enumerate(selected.to_dict("records"), start=1):
        xs, prof = sample_profile(img, float(row["x_px"]), float(row["y_px"]), float(row["radius_px"]))
        result = measure_width(xs, prof, float(row["x_px"]), float(row["radius_px"]))
        status = str(result.get("status"))
        width_px = float(result.get("width_px", np.nan))
        diameter_um = width_px * base.NM_PER_PX / 1000.0 if np.isfinite(width_px) else np.nan
        sem_um = float(row["sem_diameter_nm"]) / 1000.0
        rows.append(
            {
                "case": case,
                "case_label": CASE_LABELS[case],
                "position": position,
                "pillar_id": int(row["id"]),
                "x_px": float(row["x_px"]),
                "y_px": float(row["y_px"]),
                "status": status,
                "left_edge_px": result.get("left_edge_px", np.nan),
                "right_edge_px": result.get("right_edge_px", np.nan),
                "width_px": width_px,
                "diameter_um": diameter_um,
                "sem_truth_um": sem_um,
                "abs_error_nm": abs(diameter_um - sem_um) * 1000.0 if np.isfinite(diameter_um) else np.nan,
                "threshold": result.get("threshold", np.nan),
                "local_dark": result.get("high", np.nan),
                "local_background": result.get("low", np.nan),
            }
        )
    return pd.DataFrame(rows)


def build_tables(base) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    selected = base.select_center_pillars(9)
    long_frames = []
    for case, path in base.IMAGE_CASES_100MG.items():
        img = base.read_gray(path)
        long_frames.append(measure_case(base, case, img, selected))
    long_df = pd.concat(long_frames, ignore_index=True)

    wide = selected[["id"]].rename(columns={"id": "pillar_id"}).copy()
    wide["position"] = np.arange(1, len(selected) + 1)
    wide["sem_truth_um"] = selected["sem_diameter_nm"].astype(float).to_numpy() / 1000.0
    for case, label in CASE_LABELS.items():
        part = long_df[long_df["case"] == case].sort_values("position")
        wide[f"{case}_um"] = part["diameter_um"].to_numpy()
        wide[f"{case}_abs_error_nm"] = part["abs_error_nm"].to_numpy()
        wide[f"{case}_status"] = part["status"].to_numpy()
    labels = {case: label for case, label in CASE_LABELS.items()}
    wide["closest"] = [
        labels[min(CASE_LABELS.keys(), key=lambda case: float(row[f"{case}_abs_error_nm"]))]
        for row in wide.to_dict("records")
    ]
    summary = (
        long_df.groupby(["case", "case_label"], as_index=False)
        .agg(
            mean_abs_error_nm=("abs_error_nm", "mean"),
            median_abs_error_nm=("abs_error_nm", "median"),
            max_abs_error_nm=("abs_error_nm", "max"),
            ok_count=("status", lambda s: int((s == "ok").sum())),
        )
        .sort_values("mean_abs_error_nm")
    )
    closest_counts = wide["closest"].value_counts().to_dict()
    summary["closest_count"] = summary["case_label"].map(lambda label: int(closest_counts.get(label, 0)))
    return long_df, wide, summary


def save_table_png(display: pd.DataFrame, out_path: Path) -> None:
    fig, ax = plt.subplots(figsize=(19, 5.0), dpi=180)
    ax.axis("off")
    ax.text(
        0.0,
        1.05,
        "100MG center-nine CD by horizontal cross-section",
        transform=ax.transAxes,
        fontsize=14,
        fontweight="bold",
        va="bottom",
    )
    table = ax.table(
        cellText=display.values,
        colLabels=display.columns,
        loc="upper left",
        cellLoc="center",
        colLoc="center",
        bbox=[0, 0, 1, 0.96],
    )
    table.auto_set_font_size(False)
    table.set_fontsize(8.2)
    table.scale(1, 1.18)
    for (r, _c), cell in table.get_celld().items():
        cell.set_edgecolor("#D7DBE7")
        if r == 0:
            cell.set_facecolor("#EAF1FE")
            cell.set_text_props(weight="bold", color="#1F2430")
        else:
            cell.set_facecolor("#FFFFFF" if r % 2 else "#F7F8FB")
    fig.savefig(out_path, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def plot_cd_line(wide: pd.DataFrame, out_path: Path) -> None:
    fig, ax = plt.subplots(figsize=(11, 6.4), dpi=180)
    x = wide["position"].to_numpy()
    ax.plot(x, wide["sem_truth_um"], color="black", linestyle=(0, (6, 4)), marker=".", linewidth=1.4, label="SEM truth")
    for case, label in CASE_LABELS.items():
        ax.plot(
            x,
            wide[f"{case}_um"],
            color=CASE_COLORS[label],
            marker="o",
            fillstyle="none",
            linewidth=1.2,
            label=label,
        )
    ax.set_title("100MG CD by horizontal cross-section", fontsize=17, fontweight="bold")
    ax.set_xlabel("Pillar position near image center", fontsize=13)
    ax.set_ylabel("Diameter (um)", fontsize=13)
    ax.grid(True, axis="y", alpha=0.25)
    ax.legend(loc="best", frameon=True, fancybox=False, edgecolor="black")
    fig.tight_layout()
    fig.savefig(out_path, facecolor="white")
    plt.close(fig)


def plot_cd_line_zoom(wide: pd.DataFrame, out_path: Path) -> None:
    fig, ax = plt.subplots(figsize=(11, 6.4), dpi=180)
    x = wide["position"].to_numpy()
    ax.plot(x, wide["sem_truth_um"], color="black", linestyle=(0, (6, 4)), marker=".", linewidth=1.4, label="SEM truth")
    for case, label in {"raw": "Raw", "r61_v16": "R61 v16", "v41_current": "V41"}.items():
        ax.plot(
            x,
            wide[f"{case}_um"],
            color=CASE_COLORS[label],
            marker="o",
            fillstyle="none",
            linewidth=1.2,
            label=label,
        )
    ax.set_title("100MG cross-section CD zoom: Raw / R61 / V41", fontsize=17, fontweight="bold")
    ax.set_xlabel("Pillar position near image center", fontsize=13)
    ax.set_ylabel("Diameter (um)", fontsize=13)
    vals = wide[["sem_truth_um", "raw_um", "r61_v16_um", "v41_current_um"]]
    ax.set_ylim(float(vals.min().min()) - 0.025, float(vals.max().max()) + 0.025)
    ax.grid(True, axis="y", alpha=0.25)
    ax.legend(loc="best", frameon=True, fancybox=False, edgecolor="black")
    fig.tight_layout()
    fig.savefig(out_path, facecolor="white")
    plt.close(fig)


def write_outputs(base, long_df: pd.DataFrame, wide: pd.DataFrame, summary: pd.DataFrame) -> dict[str, str]:
    TABLE_DIR.mkdir(parents=True, exist_ok=True)
    FIG_DIR.mkdir(parents=True, exist_ok=True)
    long_csv = TABLE_DIR / "100mg_center9_cross_section_cd_measurements_long.csv"
    wide_csv = TABLE_DIR / "100mg_center9_cross_section_cd_raw_combo_r61_v41.csv"
    summary_csv = TABLE_DIR / "100mg_center9_cross_section_cd_error_summary.csv"
    long_df.to_csv(long_csv, index=False, encoding="utf-8-sig", float_format="%.9f")
    wide.to_csv(wide_csv, index=False, encoding="utf-8-sig", float_format="%.9f")
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
    table_png = FIG_DIR / "100mg_center9_cross_section_cd_table.png"
    line_png = FIG_DIR / "100mg_center9_cross_section_cd_line.png"
    line_zoom_png = FIG_DIR / "100mg_center9_cross_section_cd_line_zoom_raw_r61_v41.png"
    save_table_png(display, table_png)
    plot_cd_line(wide, line_png)
    plot_cd_line_zoom(wide, line_zoom_png)

    meta = {
        "method": "Horizontal cross-section width at each pillar center using a 7-row averaged dark-intensity profile and local half-height left/right edge crossings.",
        "pixel_scale_nm_per_px": base.NM_PER_PX,
        "note": "This is a one-dimensional edge-width measurement; the previous CD table used circular boundary search.",
        "outputs": {
            "long_csv": str(long_csv),
            "wide_csv": str(wide_csv),
            "summary_csv": str(summary_csv),
            "table_png": str(table_png),
            "line_png": str(line_png),
            "line_zoom_png": str(line_zoom_png),
        },
    }
    meta_path = TABLE_DIR / "100mg_center9_cross_section_cd_metadata.json"
    meta_path.write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")
    meta["outputs"]["metadata"] = str(meta_path)
    return meta["outputs"]


def main() -> None:
    base = load_base_module()
    long_df, wide, summary = build_tables(base)
    outputs = write_outputs(base, long_df, wide, summary)
    print(json.dumps({"outputs": outputs, "summary": summary.to_dict("records")}, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()

from __future__ import annotations

import importlib.util
import json
import shutil
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
from PIL import Image, ImageOps


SCRIPT_DIR = Path(__file__).resolve().parent
THIS_DIR = SCRIPT_DIR.parent if SCRIPT_DIR.name == "scripts" else SCRIPT_DIR
CD36_SCRIPT = SCRIPT_DIR / "measure_center36_pillar_via_raw_v41_cross_section.py"
ROW_FIG_DIR = THIS_DIR / "figures" / "center36_row_profiles"
ZOOM_FIG_DIR = THIS_DIR / "figures" / "center36_representative_zooms"
INDIVIDUAL_ZOOM_DIR = ZOOM_FIG_DIR / "individual_crops"
PROFILE_TABLE_DIR = THIS_DIR / "tables" / "center36_row_profiles"
DETAIL_FIG_DIR = THIS_DIR / "figures" / "center36_detail_profiles"
DETAIL_TABLE_DIR = THIS_DIR / "tables" / "center36_detail_profiles"
EDGE_FIG_DIR = THIS_DIR / "figures" / "center36_edge_aligned_profiles"
EDGE_TABLE_DIR = THIS_DIR / "tables" / "center36_edge_aligned_profiles"

TOKENS = {
    "surface": "#FCFCFD",
    "panel": "#FFFFFF",
    "ink": "#1F2430",
    "muted": "#6F768A",
    "grid": "#E6E8F0",
    "axis": "#D7DBE7",
}

COLORS = {
    "raw": "#5477C4",
    "v41_current": "#CC6F47",
    "sem": "#464C55",
    "center": "#C5CAD3",
}


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {path}")
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


def add_header(fig, ax, title: str, subtitle: str, *, title_size: float = 13.5) -> None:
    ax.set_title("")
    fig.subplots_adjust(top=0.82)
    left = ax.get_position().x0
    fig.text(left, 0.985, title, ha="left", va="top", fontsize=title_size, fontweight="semibold", color=TOKENS["ink"])
    fig.text(left, 0.935, subtitle, ha="left", va="top", fontsize=9, color=TOKENS["muted"])
    sns.despine(ax=ax)


def clear_output_dir(path: Path) -> None:
    path = path.resolve()
    allowed_roots = [
        ROW_FIG_DIR.resolve(),
        ZOOM_FIG_DIR.resolve(),
        PROFILE_TABLE_DIR.resolve(),
        DETAIL_FIG_DIR.resolve(),
        DETAIL_TABLE_DIR.resolve(),
        EDGE_FIG_DIR.resolve(),
        EDGE_TABLE_DIR.resolve(),
    ]
    if path in allowed_roots or any(path.is_relative_to(root) for root in allowed_roots):
        if path.exists():
            shutil.rmtree(path)
        path.mkdir(parents=True, exist_ok=True)
        return
    raise RuntimeError(f"refusing to clear unexpected path: {path}")


def normalize_profile(profile: np.ndarray) -> np.ndarray:
    arr = np.asarray(profile, dtype=np.float32)
    lo, hi = np.percentile(arr[np.isfinite(arr)], [1.0, 99.0])
    if hi <= lo:
        return np.zeros_like(arr)
    return np.clip((arr - lo) / (hi - lo), 0.0, 1.0)


def normalize_crop(crop: np.ndarray) -> Image.Image:
    arr = crop.astype(np.float32)
    lo, hi = np.percentile(arr, [0.5, 99.5])
    if hi > lo:
        arr = (arr - lo) / (hi - lo) * 255.0
    arr = np.clip(arr, 0, 255).astype(np.uint8)
    return ImageOps.autocontrast(Image.fromarray(arr))


def row_profile_signal(img: np.ndarray, feature_key: str, x0: int, x1: int, y_px: float, *, half_band: int = 3) -> np.ndarray:
    normalized = img.astype(np.float32) / 255.0
    if feature_key == "pillar":
        signal = 1.0 - normalized
    elif feature_key == "via":
        signal = normalized
    else:
        raise ValueError(feature_key)
    yy = int(round(float(y_px)))
    y0 = max(0, yy - half_band)
    y1 = min(signal.shape[0], yy + half_band + 1)
    return signal[y0:y1, x0:x1].mean(axis=0)


def load_inputs(cd36):
    base = cd36.load_module(cd36.BASE_SCRIPT, "chapter6_assets_for_rows")
    wide = pd.read_csv(THIS_DIR / "tables" / "100mg_center36_pillar_via_cross_section_cd_raw_v41_wide.csv")
    long = pd.read_csv(THIS_DIR / "tables" / "100mg_center36_pillar_via_cross_section_cd_raw_v41_long.csv")
    images = {case: base.read_gray(base.IMAGE_CASES_100MG[case]) for case in cd36.CASES}
    return base, wide, long, images


def make_row_profiles(cd36, base, wide: pd.DataFrame, long: pd.DataFrame, images: dict[str, np.ndarray]) -> pd.DataFrame:
    rows = []
    profile_catalog = []
    for feature_key, feature_info in cd36.FEATURES.items():
        feature_label = feature_info["label"]
        for row_idx in range(1, 7):
            part = (
                wide[(wide["feature_key"] == feature_key) & (wide["grid_row"] == row_idx)]
                .sort_values("grid_col")
                .reset_index(drop=True)
            )
            x0 = max(0, int(np.floor((part["x_px"] - part["radius_px"] * 2.9).min())))
            x1 = min(images["raw"].shape[1], int(np.ceil((part["x_px"] + part["radius_px"] * 2.9).max())))
            y_px = float(part["y_px"].median())
            xs = np.arange(x0, x1, dtype=np.float32)
            profile_df = pd.DataFrame({"x_px": xs})
            fig, ax = plt.subplots(figsize=(11.8, 4.8), dpi=180)

            for case, label in cd36.CASES.items():
                signal = row_profile_signal(images[case], feature_key, x0, x1, y_px)
                norm = normalize_profile(signal)
                profile_df[f"{case}_signal"] = signal
                profile_df[f"{case}_normalized"] = norm
                ax.plot(xs, norm, color=COLORS[case], linewidth=1.25, label=label)

            row_long = long[(long["feature_key"] == feature_key) & (long["grid_row"] == row_idx)]
            for _, item in part.iterrows():
                col = int(item["grid_col"])
                center_x = float(item["x_px"])
                ax.axvline(center_x, color=COLORS["center"], linestyle=":", linewidth=0.8, alpha=0.85)
                ax.text(center_x, -0.085, str(col), ha="center", va="top", fontsize=8, color=TOKENS["muted"], clip_on=False)
                v41_edges = row_long[(row_long["grid_col"] == col) & (row_long["case"] == "v41_current")]
                if not v41_edges.empty:
                    edge_row = v41_edges.iloc[0]
                    ax.axvspan(
                        float(edge_row["left_edge_px"]),
                        float(edge_row["right_edge_px"]),
                        color=COLORS["v41_current"],
                        alpha=0.055,
                        linewidth=0,
                    )

            ax.set_xlim(x0, x1)
            ax.set_ylim(-0.12, 1.08)
            ax.set_xlabel("Horizontal position (pixel)")
            ax.set_ylabel("Normalized intensity")
            ax.legend(loc="lower left", bbox_to_anchor=(0, 1.01), ncol=2, frameon=False, borderaxespad=0)
            ax.grid(axis="y", alpha=0.75)
            ax.grid(axis="x", alpha=0.2)
            add_header(
                fig,
                ax,
                f"100MG center 6x6 {feature_label.lower()} row {row_idx} cross-section profile",
                "Raw and V41 profiles are normalized inside the plotted row window. Column numbers mark the six SEM-matched positions.",
            )

            png_path = ROW_FIG_DIR / f"100mg_center36_{feature_key}_row{row_idx}_profile.png"
            svg_path = png_path.with_suffix(".svg")
            csv_path = PROFILE_TABLE_DIR / f"100mg_center36_{feature_key}_row{row_idx}_profile.csv"
            fig.savefig(png_path, bbox_inches="tight", facecolor=TOKENS["surface"])
            fig.savefig(svg_path, bbox_inches="tight", facecolor=TOKENS["surface"])
            plt.close(fig)
            profile_df.to_csv(csv_path, index=False, encoding="utf-8-sig", float_format="%.9f")

            profile_catalog.append(
                {
                    "feature_key": feature_key,
                    "feature_label": feature_label,
                    "grid_row": row_idx,
                    "y_px": y_px,
                    "x0_px": x0,
                    "x1_px": x1,
                    "png": str(png_path),
                    "svg": str(svg_path),
                    "csv": str(csv_path),
                }
            )
            rows.extend(profile_df.assign(feature_key=feature_key, grid_row=row_idx).to_dict("records"))

    pd.DataFrame(profile_catalog).to_csv(
        PROFILE_TABLE_DIR / "100mg_center36_row_profile_catalog.csv",
        index=False,
        encoding="utf-8-sig",
        float_format="%.9f",
    )
    return pd.DataFrame(rows)


def sample_normalized_feature_profile(cd36, images: dict[str, np.ndarray], case: str, feature_key: str, row: pd.Series) -> tuple[np.ndarray, np.ndarray]:
    xs, profile = cd36.sample_profile_for_feature(
        images[case],
        x_px=float(row["x_px"]),
        y_px=float(row["y_px"]),
        radius_px=float(row["radius_px"]),
        polarity=cd36.FEATURES[feature_key]["polarity"],
    )
    return xs.astype(np.float32), normalize_profile(profile)


def interpolated_centered_profile(cd36, images: dict[str, np.ndarray], case: str, feature_key: str, row: pd.Series, rel_grid: np.ndarray) -> np.ndarray:
    xs, norm = sample_normalized_feature_profile(cd36, images, case, feature_key, row)
    rel = xs - float(row["x_px"])
    return np.interp(rel_grid, rel, norm, left=np.nan, right=np.nan)


def make_detail_profiles(cd36, wide: pd.DataFrame, long: pd.DataFrame, images: dict[str, np.ndarray]) -> tuple[pd.DataFrame, pd.DataFrame]:
    detail_rows = []
    catalog = []
    for feature_key, feature_info in cd36.FEATURES.items():
        feature_label = feature_info["label"]
        for row_idx in range(1, 7):
            part = (
                wide[(wide["feature_key"] == feature_key) & (wide["grid_row"] == row_idx)]
                .sort_values("grid_col")
                .reset_index(drop=True)
            )
            if len(part) != 6:
                raise RuntimeError(f"expected 6 cells for {feature_key} row {row_idx}, got {len(part)}")

            fig = plt.figure(figsize=(18.6, 7.1), dpi=190)
            grid = fig.add_gridspec(2, 6, height_ratios=[1.0, 0.42], hspace=0.12, wspace=0.18)
            axes_top = []
            axes_delta = []
            for col_idx, (_, item) in enumerate(part.iterrows()):
                grid_col = int(item["grid_col"])
                radius = float(item["radius_px"])
                rel_window = float(np.clip(radius * 1.95, 38.0, 62.0))
                rel_grid = np.linspace(-rel_window, rel_window, 260, dtype=np.float32)
                raw_norm = interpolated_centered_profile(cd36, images, "raw", feature_key, item, rel_grid)
                v41_norm = interpolated_centered_profile(cd36, images, "v41_current", feature_key, item, rel_grid)
                delta = v41_norm - raw_norm

                ax = fig.add_subplot(grid[0, col_idx])
                axd = fig.add_subplot(grid[1, col_idx], sharex=ax)
                axes_top.append(ax)
                axes_delta.append(axd)

                ax.plot(rel_grid, raw_norm, color=COLORS["raw"], linewidth=1.15, label="Raw")
                ax.plot(rel_grid, v41_norm, color=COLORS["v41_current"], linewidth=1.15, linestyle="-", label="V41")
                ax.axvline(0, color=COLORS["center"], linestyle=":", linewidth=0.85)

                cell_long = long[
                    (long["feature_key"] == feature_key)
                    & (long["grid_row"] == row_idx)
                    & (long["grid_col"] == grid_col)
                ]
                for case in ["raw", "v41_current"]:
                    edge_row = cell_long[cell_long["case"] == case].iloc[0]
                    line_style = ":" if case == "raw" else "--"
                    for edge_col in ["left_edge_px", "right_edge_px"]:
                        rel_edge = float(edge_row[edge_col]) - float(item["x_px"])
                        ax.axvline(rel_edge, color=COLORS[case], linestyle=line_style, linewidth=0.82, alpha=0.78)

                raw_err = float(item["raw_abs_error_nm"])
                v41_err = float(item["v41_current_abs_error_nm"])
                sem_cd = float(item["sem_truth_um"])
                ax.set_title(f"c{grid_col}: SEM {sem_cd:.3f} um\nRaw {raw_err:.0f} nm | V41 {v41_err:.0f} nm", fontsize=8.3)
                ax.set_ylim(-0.06, 1.06)
                ax.grid(axis="y", alpha=0.55)
                ax.grid(axis="x", alpha=0.14)

                axd.axhline(0, color=TOKENS["axis"], linewidth=0.75)
                axd.plot(rel_grid, delta, color="#A84F35", linewidth=1.05)
                axd.fill_between(rel_grid, 0, delta, color="#D98C66", alpha=0.18, linewidth=0)
                axd.set_ylim(-0.34, 0.34)
                axd.grid(axis="y", alpha=0.45)
                axd.grid(axis="x", alpha=0.12)
                axd.set_xlabel("Center-relative x (px)", fontsize=8.4)

                if col_idx == 0:
                    ax.set_ylabel("Normalized\nintensity", fontsize=8.7)
                    axd.set_ylabel("V41 - Raw", fontsize=8.2)
                else:
                    ax.set_yticklabels([])
                    axd.set_yticklabels([])
                ax.tick_params(labelsize=7.8, length=2)
                axd.tick_params(labelsize=7.8, length=2)
                sns.despine(ax=ax)
                sns.despine(ax=axd)

                for rel_x, raw_value, v41_value, delta_value in zip(rel_grid, raw_norm, v41_norm, delta):
                    detail_rows.append(
                        {
                            "feature_key": feature_key,
                            "feature_label": feature_label,
                            "grid_row": row_idx,
                            "grid_col": grid_col,
                            "sem_excel_cell": item["sem_excel_cell"],
                            "sem_truth_um": sem_cd,
                            "rel_x_px": float(rel_x),
                            "raw_normalized": float(raw_value),
                            "v41_current_normalized": float(v41_value),
                            "delta_v41_minus_raw": float(delta_value),
                        }
                    )

            axes_top[0].legend(loc="lower left", bbox_to_anchor=(0, 1.14), frameon=False, ncol=2, borderaxespad=0, fontsize=9)
            fig.suptitle(
                f"100MG center 6x6 {feature_label.lower()} row {row_idx}: separated detailed profiles",
                x=0.055,
                y=0.995,
                ha="left",
                va="top",
                fontsize=13.8,
                fontweight="semibold",
                color=TOKENS["ink"],
            )
            fig.text(
                0.055,
                0.958,
                "Each cell is centered independently. Dashed/dotted vertical lines mark measured Raw/V41 edges; lower panels show local V41 minus Raw.",
                ha="left",
                va="top",
                fontsize=9,
                color=TOKENS["muted"],
            )
            fig.subplots_adjust(top=0.82)
            png_path = DETAIL_FIG_DIR / f"100mg_center36_{feature_key}_row{row_idx}_detail_profiles.png"
            svg_path = png_path.with_suffix(".svg")
            csv_path = DETAIL_TABLE_DIR / f"100mg_center36_{feature_key}_row{row_idx}_detail_profiles.csv"
            row_df = pd.DataFrame([r for r in detail_rows if r["feature_key"] == feature_key and r["grid_row"] == row_idx])
            row_df.to_csv(csv_path, index=False, encoding="utf-8-sig", float_format="%.9f")
            fig.savefig(png_path, bbox_inches="tight", facecolor=TOKENS["surface"])
            fig.savefig(svg_path, bbox_inches="tight", facecolor=TOKENS["surface"])
            plt.close(fig)

            catalog.append(
                {
                    "feature_key": feature_key,
                    "feature_label": feature_label,
                    "grid_row": row_idx,
                    "png": str(png_path),
                    "svg": str(svg_path),
                    "csv": str(csv_path),
                }
            )

    detail_df = pd.DataFrame(detail_rows)
    catalog_df = pd.DataFrame(catalog)
    detail_df.to_csv(
        DETAIL_TABLE_DIR / "100mg_center36_detail_profiles_all.csv",
        index=False,
        encoding="utf-8-sig",
        float_format="%.9f",
    )
    catalog_df.to_csv(
        DETAIL_TABLE_DIR / "100mg_center36_detail_profile_catalog.csv",
        index=False,
        encoding="utf-8-sig",
    )
    return detail_df, catalog_df


def first_crossing_x(x: np.ndarray, y: np.ndarray, level: float) -> float:
    x = np.asarray(x, dtype=np.float64)
    y = np.asarray(y, dtype=np.float64)
    finite = np.isfinite(x) & np.isfinite(y)
    x = x[finite]
    y = y[finite]
    if len(x) < 2:
        return float("nan")
    diff = y - float(level)
    crossings = np.where((diff[:-1] <= 0) & (diff[1:] >= 0) | ((diff[:-1] >= 0) & (diff[1:] <= 0)))[0]
    if len(crossings) == 0:
        return float("nan")
    midpoints = (x[crossings] + x[crossings + 1]) / 2.0
    idx = int(crossings[np.argmin(np.abs(midpoints))])
    y0 = y[idx]
    y1 = y[idx + 1]
    x0 = x[idx]
    x1 = x[idx + 1]
    if y1 == y0:
        return float((x0 + x1) / 2.0)
    return float(x0 + (float(level) - y0) * (x1 - x0) / (y1 - y0))


def make_edge_aligned_profiles(cd36, long: pd.DataFrame, images: dict[str, np.ndarray]) -> tuple[pd.DataFrame, pd.DataFrame]:
    rel_grid = np.linspace(-24.0, 24.0, 241, dtype=np.float32)
    profile_records = []
    mean_records = []
    summary_records = []

    for feature_key, feature_info in cd36.FEATURES.items():
        feature_label = feature_info["label"]
        fig, axes = plt.subplots(1, 2, figsize=(11.8, 4.6), dpi=190, sharey=True)
        for ax, edge_side in zip(axes, ["left", "right"]):
            for case, label in cd36.CASES.items():
                aligned_profiles = []
                rows = long[(long["feature_key"] == feature_key) & (long["case"] == case)].sort_values(["grid_row", "grid_col"])
                for _, item in rows.iterrows():
                    xs, norm = sample_normalized_feature_profile(cd36, images, case, feature_key, item)
                    edge_px = float(item[f"{edge_side}_edge_px"])
                    if edge_side == "left":
                        rel = xs - edge_px
                    else:
                        rel = edge_px - xs
                    order = np.argsort(rel)
                    rel = rel[order]
                    norm = norm[order]
                    vals = np.interp(rel_grid, rel, norm, left=np.nan, right=np.nan)
                    aligned_profiles.append(vals)
                    for rel_x, value in zip(rel_grid, vals):
                        profile_records.append(
                            {
                                "feature_key": feature_key,
                                "feature_label": feature_label,
                                "case": case,
                                "case_label": label,
                                "edge_side": edge_side,
                                "grid_row": int(item["grid_row"]),
                                "grid_col": int(item["grid_col"]),
                                "rel_x_px": float(rel_x),
                                "normalized": float(value),
                            }
                        )

                arr = np.vstack(aligned_profiles)
                mean = np.nanmean(arr, axis=0)
                std = np.nanstd(arr, axis=0)
                sem = std / np.sqrt(arr.shape[0])
                x20 = first_crossing_x(rel_grid, mean, 0.2)
                x80 = first_crossing_x(rel_grid, mean, 0.8)
                width_20_80 = abs(x80 - x20) if np.isfinite(x20) and np.isfinite(x80) else float("nan")

                for rel_x, mean_value, std_value, sem_value in zip(rel_grid, mean, std, sem):
                    mean_records.append(
                        {
                            "feature_key": feature_key,
                            "feature_label": feature_label,
                            "case": case,
                            "case_label": label,
                            "edge_side": edge_side,
                            "rel_x_px": float(rel_x),
                            "mean_normalized": float(mean_value),
                            "std_normalized": float(std_value),
                            "sem_normalized": float(sem_value),
                        }
                    )

                summary_records.append(
                    {
                        "feature_key": feature_key,
                        "feature_label": feature_label,
                        "case": case,
                        "case_label": label,
                        "edge_side": edge_side,
                        "profile_count": int(arr.shape[0]),
                        "x20_px": x20,
                        "x80_px": x80,
                        "width_20_80_px": width_20_80,
                    }
                )

                ax.plot(rel_grid, mean, color=COLORS[case], linewidth=1.35, label=label)
                ax.fill_between(rel_grid, mean - sem, mean + sem, color=COLORS[case], alpha=0.16, linewidth=0)

            ax.axvline(0, color=COLORS["center"], linestyle=":", linewidth=0.9)
            ax.set_title(f"{edge_side.capitalize()} edge aligned", fontsize=10.5, fontweight="semibold")
            ax.set_xlabel("Distance from measured edge (px)\ninside is to the right")
            ax.set_xlim(-24, 24)
            ax.set_ylim(-0.06, 1.06)
            ax.grid(axis="y", alpha=0.65)
            ax.grid(axis="x", alpha=0.18)
            sns.despine(ax=ax)

        axes[0].set_ylabel("Mean normalized intensity")
        axes[0].legend(loc="lower left", bbox_to_anchor=(0, 1.02), frameon=False, ncol=2, borderaxespad=0)
        fig.suptitle(
            f"100MG center 6x6 {feature_label.lower()}: edge-aligned average profile",
            x=0.09,
            y=0.995,
            ha="left",
            va="top",
            fontsize=13.5,
            fontweight="semibold",
            color=TOKENS["ink"],
        )
        fig.text(
            0.09,
            0.945,
            "All 36 cells are aligned by the measured boundary; shaded bands show standard error across cells.",
            ha="left",
            va="top",
            fontsize=9,
            color=TOKENS["muted"],
        )
        fig.subplots_adjust(top=0.78, wspace=0.18)
        png_path = EDGE_FIG_DIR / f"100mg_center36_{feature_key}_edge_aligned_profile.png"
        svg_path = png_path.with_suffix(".svg")
        fig.savefig(png_path, bbox_inches="tight", facecolor=TOKENS["surface"])
        fig.savefig(svg_path, bbox_inches="tight", facecolor=TOKENS["surface"])
        plt.close(fig)

    profiles_df = pd.DataFrame(profile_records)
    means_df = pd.DataFrame(mean_records)
    summary_df = pd.DataFrame(summary_records)
    profiles_df.to_csv(
        EDGE_TABLE_DIR / "100mg_center36_edge_aligned_profiles_all.csv",
        index=False,
        encoding="utf-8-sig",
        float_format="%.9f",
    )
    means_df.to_csv(
        EDGE_TABLE_DIR / "100mg_center36_edge_aligned_mean_profiles.csv",
        index=False,
        encoding="utf-8-sig",
        float_format="%.9f",
    )
    summary_df.to_csv(
        EDGE_TABLE_DIR / "100mg_center36_edge_aligned_summary.csv",
        index=False,
        encoding="utf-8-sig",
        float_format="%.9f",
    )
    return means_df, summary_df


def choose_representatives(wide: pd.DataFrame) -> pd.DataFrame:
    picks = []
    for feature_key in ["pillar", "via"]:
        group = wide[wide["feature_key"] == feature_key].copy()
        criteria = [
            ("best_improvement", group["improvement_nm_raw_minus_v41"].idxmax()),
            ("median_improvement", (group["improvement_nm_raw_minus_v41"] - group["improvement_nm_raw_minus_v41"].median()).abs().idxmin()),
            ("largest_v41_error", group["v41_current_abs_error_nm"].idxmax()),
        ]
        used = set()
        for reason, idx in criteria:
            candidates = group.copy()
            if reason == "best_improvement":
                candidates = candidates.sort_values("improvement_nm_raw_minus_v41", ascending=False)
            elif reason == "median_improvement":
                median = float(group["improvement_nm_raw_minus_v41"].median())
                candidates = candidates.assign(_rank=(candidates["improvement_nm_raw_minus_v41"] - median).abs()).sort_values("_rank")
            else:
                candidates = candidates.sort_values("v41_current_abs_error_nm", ascending=False)
            chosen = None
            for _, row in candidates.iterrows():
                key = int(row["sem_index"])
                if key not in used:
                    chosen = row.copy()
                    used.add(key)
                    break
            if chosen is None:
                chosen = group.loc[idx].copy()
            chosen["representative_reason"] = reason
            picks.append(chosen)
    return pd.DataFrame(picks).reset_index(drop=True)


def crop_bounds(img: np.ndarray, row: pd.Series, *, scale: float = 4.6) -> tuple[int, int, int, int]:
    radius = float(row["radius_px"])
    pad = max(70.0, radius * scale)
    x0 = max(0, int(np.floor(float(row["x_px"]) - pad)))
    x1 = min(img.shape[1], int(np.ceil(float(row["x_px"]) + pad)))
    y0 = max(0, int(np.floor(float(row["y_px"]) - pad)))
    y1 = min(img.shape[0], int(np.ceil(float(row["y_px"]) + pad)))
    return x0, y0, x1, y1


def draw_crop_axis(ax, crop: np.ndarray, row: pd.Series, edge_row: pd.Series, bounds: tuple[int, int, int, int], title: str) -> None:
    x0, y0, _, _ = bounds
    ax.imshow(normalize_crop(crop), cmap="gray", interpolation="nearest")
    y_local = float(row["y_px"]) - y0
    ax.axhline(y_local, color="#FFE15B", linewidth=1.1)
    for edge_col, color in [("left_edge_px", "#F0986E"), ("right_edge_px", "#F0986E")]:
        value = float(edge_row[edge_col])
        ax.axvline(value - x0, color=color, linewidth=1.0, linestyle="--")
    ax.set_title(title, fontsize=10.5, fontweight="semibold")
    ax.set_xticks([])
    ax.set_yticks([])


def make_single_crop_file(img: np.ndarray, row: pd.Series, edge_row: pd.Series, out_path: Path, title: str) -> None:
    bounds = crop_bounds(img, row)
    x0, y0, x1, y1 = bounds
    crop = img[y0:y1, x0:x1]
    fig, ax = plt.subplots(figsize=(3.8, 3.8), dpi=180)
    draw_crop_axis(ax, crop, row, edge_row, bounds, title)
    fig.savefig(out_path, bbox_inches="tight", facecolor=TOKENS["surface"])
    plt.close(fig)


def make_representative_zooms(cd36, base, wide: pd.DataFrame, long: pd.DataFrame, images: dict[str, np.ndarray]) -> pd.DataFrame:
    reps = choose_representatives(wide)
    catalog = []
    for _, row in reps.iterrows():
        feature_key = str(row["feature_key"])
        feature_label = str(row["feature_label"])
        reason = str(row["representative_reason"])
        grid_row = int(row["grid_row"])
        grid_col = int(row["grid_col"])
        stem = f"100mg_center36_{feature_key}_r{grid_row}c{grid_col}_{reason}"
        feature_long = long[
            (long["feature_key"] == feature_key)
            & (long["grid_row"] == grid_row)
            & (long["grid_col"] == grid_col)
        ]

        fig = plt.figure(figsize=(8.8, 7.8), dpi=180)
        grid = fig.add_gridspec(2, 2, height_ratios=[1.05, 0.72], hspace=0.38, wspace=0.24)
        crop_axes = [fig.add_subplot(grid[0, 0]), fig.add_subplot(grid[0, 1])]
        axp = fig.add_subplot(grid[1, :])
        for col_idx, (case, label) in enumerate(cd36.CASES.items()):
            img = images[case]
            bounds = crop_bounds(img, row)
            x0, y0, x1, y1 = bounds
            crop = img[y0:y1, x0:x1]
            edge_row = feature_long[feature_long["case"] == case].iloc[0]
            title = f"{label}: CD {float(edge_row['diameter_um']):.3f} um, err {float(edge_row['abs_error_nm']):.0f} nm"
            draw_crop_axis(crop_axes[col_idx], crop, row, edge_row, bounds, title)

            single_path = INDIVIDUAL_ZOOM_DIR / f"{stem}_{case}.png"
            make_single_crop_file(img, row, edge_row, single_path, title)

        for case, label in cd36.CASES.items():
            img = images[case]
            xs, profile = cd36.sample_profile_for_feature(
                img,
                x_px=float(row["x_px"]),
                y_px=float(row["y_px"]),
                radius_px=float(row["radius_px"]),
                polarity=cd36.FEATURES[feature_key]["polarity"],
            )
            axp.plot(xs - float(row["x_px"]), normalize_profile(profile), color=COLORS[case], linewidth=1.35, label=label)
            edge_row = feature_long[feature_long["case"] == case].iloc[0]
            axp.axvline(float(edge_row["left_edge_px"]) - float(row["x_px"]), color=COLORS[case], linestyle="--", linewidth=0.9, alpha=0.85)
            axp.axvline(float(edge_row["right_edge_px"]) - float(row["x_px"]), color=COLORS[case], linestyle="--", linewidth=0.9, alpha=0.85)
        axp.axvline(0, color=COLORS["center"], linestyle=":", linewidth=0.9)
        axp.set_xlabel("Position relative to detected center (pixel)")
        axp.set_ylabel("Normalized intensity")
        axp.set_ylim(-0.05, 1.08)
        axp.legend(loc="upper left", ncol=2, frameon=False, borderaxespad=0.4)
        sns.despine(ax=axp)

        fig.suptitle(
            f"100MG {feature_label.lower()} representative zoom: row {grid_row}, column {grid_col}",
            x=0.12,
            y=0.995,
            ha="left",
            va="top",
            fontsize=13.5,
            fontweight="semibold",
            color=TOKENS["ink"],
        )
        fig.text(
            0.12,
            0.955,
            f"Reason: {reason.replace('_', ' ')}. SEM cell {row['sem_excel_cell']}; SEM CD {float(row['sem_truth_um']):.3f} um.",
            ha="left",
            va="top",
            fontsize=9,
            color=TOKENS["muted"],
        )
        fig.subplots_adjust(top=0.86)
        out_png = ZOOM_FIG_DIR / f"{stem}.png"
        out_svg = out_png.with_suffix(".svg")
        fig.savefig(out_png, bbox_inches="tight", facecolor=TOKENS["surface"])
        fig.savefig(out_svg, bbox_inches="tight", facecolor=TOKENS["surface"])
        plt.close(fig)

        catalog.append(
            {
                "feature_key": feature_key,
                "feature_label": feature_label,
                "representative_reason": reason,
                "grid_row": grid_row,
                "grid_col": grid_col,
                "sem_excel_cell": row["sem_excel_cell"],
                "sem_truth_um": float(row["sem_truth_um"]),
                "raw_um": float(row["raw_um"]),
                "v41_current_um": float(row["v41_current_um"]),
                "raw_abs_error_nm": float(row["raw_abs_error_nm"]),
                "v41_current_abs_error_nm": float(row["v41_current_abs_error_nm"]),
                "improvement_nm_raw_minus_v41": float(row["improvement_nm_raw_minus_v41"]),
                "comparison_png": str(out_png),
                "comparison_svg": str(out_svg),
                "raw_crop_png": str(INDIVIDUAL_ZOOM_DIR / f"{stem}_raw.png"),
                "v41_crop_png": str(INDIVIDUAL_ZOOM_DIR / f"{stem}_v41_current.png"),
            }
        )
    catalog_df = pd.DataFrame(catalog)
    catalog_df.to_csv(
        THIS_DIR / "tables" / "100mg_center36_representative_zoom_catalog.csv",
        index=False,
        encoding="utf-8-sig",
        float_format="%.9f",
    )
    return catalog_df


def main() -> None:
    use_chart_theme()
    for path in [ROW_FIG_DIR, ZOOM_FIG_DIR, PROFILE_TABLE_DIR, DETAIL_FIG_DIR, DETAIL_TABLE_DIR, EDGE_FIG_DIR, EDGE_TABLE_DIR]:
        clear_output_dir(path)
    INDIVIDUAL_ZOOM_DIR.mkdir(parents=True, exist_ok=True)

    cd36 = load_module(CD36_SCRIPT, "cd36_measurement")
    base, wide, long, images = load_inputs(cd36)
    row_profiles = make_row_profiles(cd36, base, wide, long, images)
    detail_profiles, detail_catalog = make_detail_profiles(cd36, wide, long, images)
    edge_means, edge_summary = make_edge_aligned_profiles(cd36, long, images)
    zoom_catalog = make_representative_zooms(cd36, base, wide, long, images)

    metadata = {
        "method": "Generate per-row cross-section profile figures, separated detail profile panels, edge-aligned average boundary profiles, and representative zoom figures from the corrected center-6x6 SEM-matched Raw/V41 CD table.",
        "row_profile_count": 12,
        "detail_profile_figure_count": int(len(detail_catalog)),
        "edge_aligned_figure_count": 2,
        "representative_zoom_count": int(len(zoom_catalog)),
        "profile_sample_rows": int(len(row_profiles)),
        "detail_profile_sample_rows": int(len(detail_profiles)),
        "edge_aligned_mean_rows": int(len(edge_means)),
        "edge_aligned_summary": edge_summary.to_dict("records"),
        "outputs": {
            "row_figures": str(ROW_FIG_DIR),
            "detail_figures": str(DETAIL_FIG_DIR),
            "edge_aligned_figures": str(EDGE_FIG_DIR),
            "zoom_figures": str(ZOOM_FIG_DIR),
            "profile_tables": str(PROFILE_TABLE_DIR),
            "detail_profile_tables": str(DETAIL_TABLE_DIR),
            "edge_aligned_tables": str(EDGE_TABLE_DIR),
            "zoom_catalog": str(THIS_DIR / "tables" / "100mg_center36_representative_zoom_catalog.csv"),
        },
    }
    meta_path = THIS_DIR / "tables" / "100mg_center36_row_profiles_and_zooms_metadata.json"
    meta_path.write_text(json.dumps(metadata, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(metadata, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()

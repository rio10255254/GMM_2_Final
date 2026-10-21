from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import cv2
import matplotlib.pyplot as plt
import numpy as np
import openpyxl
import pandas as pd
import seaborn as sns


SCRIPT_DIR = Path(__file__).resolve().parent
THIS_DIR = SCRIPT_DIR.parent if SCRIPT_DIR.name == "scripts" else SCRIPT_DIR
BASE_SCRIPT = SCRIPT_DIR / "make_chapter6_visual_cd_assets.py"
CROSS_SECTION_SCRIPT = SCRIPT_DIR / "measure_cd_by_cross_section.py"
FIG_DIR = THIS_DIR / "figures" / "center36_cd_maps"
TABLE_DIR = THIS_DIR / "tables"
SEM_LAYOUT_XLSX = THIS_DIR.parents[1] / "20260618_100MG" / "SEM_data" / "via_pilar.xlsx"

CASES = {"raw": "Raw", "v41_current": "V41"}
FEATURES = {
    "pillar": {
        "label": "Pillar",
        "feature_name": "圓柱",
        "sem_block_rows": (5, 10),
        "sem_block_cols": (10, 15),
        "polarity": "dark",
    },
    "via": {
        "label": "Via",
        "feature_name": "圓孔",
        "sem_block_rows": (11, 16),
        "sem_block_cols": (4, 9),
        "polarity": "bright",
    },
}

TOKENS = {
    "surface": "#FCFCFD",
    "panel": "#FFFFFF",
    "ink": "#1F2430",
    "muted": "#6F768A",
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
        style="white",
        rc={
            "figure.facecolor": TOKENS["surface"],
            "axes.facecolor": TOKENS["panel"],
            "axes.labelcolor": TOKENS["ink"],
            "font.family": "sans-serif",
            "font.sans-serif": ["Aptos", "Inter", "Segoe UI", "DejaVu Sans", "Arial", "sans-serif"],
        },
    )


def add_header(fig, ax, title: str, subtitle: str, *, title_size: float = 14) -> None:
    ax.set_title("")
    fig.subplots_adjust(top=0.86)
    left = ax.get_position().x0
    fig.text(left, 0.985, title, ha="left", va="top", fontsize=title_size, fontweight="semibold", color=TOKENS["ink"])
    fig.text(left, 0.935, subtitle, ha="left", va="top", fontsize=9, color=TOKENS["muted"])


def excel_column_name(col_idx: int) -> str:
    name = ""
    value = int(col_idx)
    while value:
        value, rem = divmod(value - 1, 26)
        name = chr(65 + rem) + name
    return name


def read_sem_layouts() -> dict[str, pd.DataFrame]:
    workbook = openpyxl.load_workbook(SEM_LAYOUT_XLSX, data_only=True)
    sheet = workbook["SEM data"]
    layouts: dict[str, pd.DataFrame] = {}
    for feature_key, info in FEATURES.items():
        row_start, row_end = info["sem_block_rows"]
        col_start, col_end = info["sem_block_cols"]
        records = []
        for grid_row, excel_row in enumerate(range(row_start, row_end + 1), start=1):
            for grid_col, excel_col in enumerate(range(col_start, col_end + 1), start=1):
                radius_nm = float(sheet.cell(excel_row, excel_col).value)
                records.append(
                    {
                        "feature_key": feature_key,
                        "grid_row": grid_row,
                        "grid_col": grid_col,
                        "sem_excel_cell": f"{excel_column_name(excel_col)}{excel_row}",
                        "sem_radius_nm": radius_nm,
                        "sem_diameter_nm": radius_nm * 2.0,
                    }
                )
        layouts[feature_key] = pd.DataFrame(records)
    return layouts


def read_feature_table(base) -> pd.DataFrame:
    rows = pd.DataFrame(base.read_feature_rows(base.RAW_CD))
    return rows.rename(columns={"id": "feature_id"})


def cluster_values(values: pd.Series, tol: float = 35.0) -> list[dict[str, object]]:
    sorted_values = sorted(float(v) for v in values)
    groups: list[list[float]] = []
    for value in sorted_values:
        if not groups or abs(value - float(np.median(groups[-1]))) > tol:
            groups.append([value])
        else:
            groups[-1].append(value)
    return [{"group": idx, "center": float(np.median(group)), "values": group} for idx, group in enumerate(groups)]


def assign_axis_groups(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    for axis, col in [("x", "x_px"), ("y", "y_px")]:
        groups = cluster_values(out[col], tol=35.0)
        centers = np.array([g["center"] for g in groups], dtype=float)
        assigned = []
        for value in out[col].astype(float):
            assigned.append(int(np.argmin(np.abs(centers - value))))
        out[f"{axis}_group"] = assigned
        out[f"{axis}_group_center"] = [float(centers[g]) for g in assigned]
    return out


def select_center_6x6(base, feature_key: str) -> pd.DataFrame:
    feature_info = FEATURES[feature_key]
    features = read_feature_table(base)
    part = features[features["feature"] == feature_info["feature_name"]].copy()
    part = assign_axis_groups(part)
    x_centers = part.groupby("x_group")["x_group_center"].first()
    y_centers = part.groupby("y_group")["y_group_center"].first()
    selected_x_groups = (
        (x_centers - 1024.0).abs().sort_values().head(6).index.tolist()
    )
    selected_y_groups = (
        (y_centers - 768.0).abs().sort_values().head(6).index.tolist()
    )
    selected_x_groups = sorted(selected_x_groups, key=lambda g: float(x_centers.loc[g]))
    selected_y_groups = sorted(selected_y_groups, key=lambda g: float(y_centers.loc[g]))

    grid_rows = []
    for row_idx, y_group in enumerate(selected_y_groups, start=1):
        for col_idx, x_group in enumerate(selected_x_groups, start=1):
            cell = part[(part["x_group"] == x_group) & (part["y_group"] == y_group)].copy()
            if cell.empty:
                raise RuntimeError(f"missing {feature_key} cell row={row_idx} col={col_idx}")
            target_x = float(x_centers.loc[x_group])
            target_y = float(y_centers.loc[y_group])
            cell["cell_distance"] = np.hypot(cell["x_px"] - target_x, cell["y_px"] - target_y)
            item = cell.sort_values("cell_distance").iloc[0].to_dict()
            sem_index = (row_idx - 1) * 6 + col_idx
            grid_rows.append(
                {
                    **item,
                    "feature_key": feature_key,
                    "feature_label": feature_info["label"],
                    "grid_row": row_idx,
                    "grid_col": col_idx,
                    "sem_index": sem_index,
                }
            )
    return pd.DataFrame(grid_rows).sort_values("sem_index").reset_index(drop=True)


def sample_profile_for_feature(
    img: np.ndarray,
    *,
    x_px: float,
    y_px: float,
    radius_px: float,
    polarity: str,
    half_band: int = 3,
) -> tuple[np.ndarray, np.ndarray]:
    h, w = img.shape
    margin = max(28.0, float(radius_px) * 1.35)
    x0 = max(0, int(np.floor(float(x_px) - float(radius_px) - margin)))
    x1 = min(w, int(np.ceil(float(x_px) + float(radius_px) + margin)))
    yy = int(round(float(y_px)))
    y0 = max(0, yy - half_band)
    y1 = min(h, yy + half_band + 1)
    normalized = img.astype(np.float32) / 255.0
    if polarity == "dark":
        signal = 1.0 - normalized
    elif polarity == "bright":
        signal = normalized
    else:
        raise ValueError(polarity)
    profile = signal[y0:y1, x0:x1].mean(axis=0)
    return np.arange(x0, x1, dtype=np.float32), profile.astype(np.float32)


def measure_feature_case(base, cross, sem_layout: pd.DataFrame, selected: pd.DataFrame, feature_key: str, case: str) -> pd.DataFrame:
    feature_info = FEATURES[feature_key]
    img = base.read_gray(base.IMAGE_CASES_100MG[case])
    case_rows = []
    for row in selected.to_dict("records"):
        xs, profile = sample_profile_for_feature(
            img,
            x_px=float(row["x_px"]),
            y_px=float(row["y_px"]),
            radius_px=float(row["radius_px"]),
            polarity=feature_info["polarity"],
        )
        result = cross.measure_width(xs, profile, float(row["x_px"]), float(row["radius_px"]))
        width_px = float(result.get("width_px", np.nan))
        diameter_um = width_px * base.NM_PER_PX / 1000.0 if np.isfinite(width_px) else np.nan
        sem_record = sem_layout[
            (sem_layout["grid_row"] == int(row["grid_row"])) & (sem_layout["grid_col"] == int(row["grid_col"]))
        ].iloc[0]
        sem_nm = float(sem_record["sem_diameter_nm"])
        sem_um = sem_nm / 1000.0
        case_rows.append(
            {
                "feature_key": feature_key,
                "feature_label": feature_info["label"],
                "case": case,
                "case_label": CASES[case],
                "sem_index": int(row["sem_index"]),
                "sem_excel_cell": str(sem_record["sem_excel_cell"]),
                "sem_radius_nm": float(sem_record["sem_radius_nm"]),
                "grid_row": int(row["grid_row"]),
                "grid_col": int(row["grid_col"]),
                "detected_feature_id": int(row["feature_id"]),
                "x_px": float(row["x_px"]),
                "y_px": float(row["y_px"]),
                "radius_px": float(row["radius_px"]),
                "clean_for_summary": int(row["clean"]),
                "status": str(result.get("status")),
                "diameter_um": diameter_um,
                "sem_truth_um": sem_um,
                "abs_error_nm": abs(diameter_um - sem_um) * 1000.0 if np.isfinite(diameter_um) else np.nan,
                "left_edge_px": result.get("left_edge_px", np.nan),
                "right_edge_px": result.get("right_edge_px", np.nan),
                "threshold": result.get("threshold", np.nan),
            }
        )
    return pd.DataFrame(case_rows)


def measure_all(base, cross) -> pd.DataFrame:
    sem_layouts = read_sem_layouts()
    frames = []
    for feature_key in FEATURES:
        selected = select_center_6x6(base, feature_key)
        for case in CASES:
            frames.append(measure_feature_case(base, cross, sem_layouts[feature_key], selected, feature_key, case))
    return pd.concat(frames, ignore_index=True)


def make_wide(long_df: pd.DataFrame) -> pd.DataFrame:
    base_cols = [
        "feature_key",
        "feature_label",
        "sem_index",
        "grid_row",
        "grid_col",
        "sem_excel_cell",
        "sem_radius_nm",
        "detected_feature_id",
        "x_px",
        "y_px",
        "radius_px",
        "clean_for_summary",
        "sem_truth_um",
    ]
    wide_parts = []
    for feature_key in FEATURES:
        base_part = long_df[(long_df["feature_key"] == feature_key) & (long_df["case"] == "raw")][base_cols].copy()
        for case, label in CASES.items():
            part = long_df[(long_df["feature_key"] == feature_key) & (long_df["case"] == case)].sort_values("sem_index")
            base_part[f"{case}_um"] = part["diameter_um"].to_numpy()
            base_part[f"{case}_abs_error_nm"] = part["abs_error_nm"].to_numpy()
            base_part[f"{case}_status"] = part["status"].to_numpy()
        base_part["improvement_nm_raw_minus_v41"] = base_part["raw_abs_error_nm"] - base_part["v41_current_abs_error_nm"]
        base_part["winner"] = np.where(base_part["v41_current_abs_error_nm"] < base_part["raw_abs_error_nm"], "V41", "Raw")
        wide_parts.append(base_part)
    return pd.concat(wide_parts, ignore_index=True).sort_values(["feature_key", "sem_index"]).reset_index(drop=True)


def make_summary(wide: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for feature_key, group in wide.groupby("feature_key", sort=False):
        for case, label in CASES.items():
            errors = group[f"{case}_abs_error_nm"].astype(float)
            rows.append(
                {
                    "feature_key": feature_key,
                    "feature_label": FEATURES[feature_key]["label"],
                    "case": case,
                    "case_label": label,
                    "mean_abs_error_nm": float(errors.mean()),
                    "median_abs_error_nm": float(errors.median()),
                    "max_abs_error_nm": float(errors.max()),
                    "ok_count": int((group[f"{case}_status"] == "ok").sum()),
                    "winner_count": int((group["winner"] == label).sum()),
                }
            )
    return pd.DataFrame(rows)


def matrix_for(wide: pd.DataFrame, feature_key: str, value_col: str) -> pd.DataFrame:
    part = wide[wide["feature_key"] == feature_key]
    return part.pivot(index="grid_row", columns="grid_col", values=value_col).sort_index().sort_index(axis=1)


def plot_feature_heatmaps(wide: pd.DataFrame, feature_key: str, out_path: Path, *, clipped: bool = False) -> None:
    use_chart_theme()
    feature_label = FEATURES[feature_key]["label"]
    raw_matrix = matrix_for(wide, feature_key, "raw_abs_error_nm")
    v41_matrix = matrix_for(wide, feature_key, "v41_current_abs_error_nm")
    observed_vmax = float(np.nanmax([raw_matrix.to_numpy(), v41_matrix.to_numpy()]))
    if clipped:
        vmax = 160.0 if feature_key == "pillar" else 260.0
        subtitle_extra = f"Color clipped at {vmax:.0f} nm for readability; cell labels show actual error."
    else:
        vmax = max(80.0, np.ceil(observed_vmax / 20.0) * 20.0)
        subtitle_extra = "Full color scale uses the largest error in this feature group."
    fig, axes = plt.subplots(1, 2, figsize=(10.6, 5.2), dpi=180)
    cmap = sns.color_palette("viridis", as_cmap=True)
    for ax, matrix, label, letter in [
        (axes[0], raw_matrix, "Raw", "(a)"),
        (axes[1], v41_matrix, "V41", "(b)"),
    ]:
        sns.heatmap(
            matrix,
            ax=ax,
            cmap=cmap,
            vmin=0,
            vmax=vmax,
            annot=True,
            fmt=".0f",
            linewidths=1.0,
            linecolor="#FFFFFF",
            square=True,
            cbar=True,
            cbar_kws={"label": "Absolute error (nm)", "shrink": 0.82},
        )
        ax.set_title(label, fontsize=12, fontweight="semibold", pad=8)
        ax.set_xlabel("Position column")
        ax.set_ylabel("Position row")
        ax.tick_params(axis="both", labelrotation=0)
        ax.text(0.5, -0.21, letter, transform=ax.transAxes, ha="center", va="center", fontsize=13)
    add_header(
        fig,
        axes[0],
        f"100MG center 6x6 {feature_label.lower()} CD error",
        f"Horizontal cross-section measurement versus SEM, unit nm. {subtitle_extra}",
    )
    fig.savefig(out_path.with_suffix(".png"), bbox_inches="tight", facecolor=TOKENS["surface"])
    fig.savefig(out_path.with_suffix(".svg"), bbox_inches="tight", facecolor=TOKENS["surface"])
    plt.close(fig)


def plot_combined_heatmaps(wide: pd.DataFrame, out_path: Path) -> None:
    use_chart_theme()
    fig, axes = plt.subplots(2, 2, figsize=(10.6, 9.2), dpi=180)
    cmap = sns.color_palette("viridis", as_cmap=True)
    panel_specs = [
        ("pillar", "raw_abs_error_nm", "Pillar Raw", "(a)"),
        ("pillar", "v41_current_abs_error_nm", "Pillar V41", "(b)"),
        ("via", "raw_abs_error_nm", "Via Raw", "(c)"),
        ("via", "v41_current_abs_error_nm", "Via V41", "(d)"),
    ]
    for ax, (feature_key, value_col, title, letter) in zip(axes.flat, panel_specs):
        matrix = matrix_for(wide, feature_key, value_col)
        vmax = 160.0 if feature_key == "pillar" else 260.0
        sns.heatmap(
            matrix,
            ax=ax,
            cmap=cmap,
            vmin=0,
            vmax=vmax,
            annot=True,
            fmt=".0f",
            linewidths=1.0,
            linecolor="#FFFFFF",
            square=True,
            cbar=True,
            cbar_kws={"label": "Abs. error (nm)", "shrink": 0.75},
        )
        ax.set_title(title, fontsize=11.5, fontweight="semibold", pad=7)
        ax.set_xlabel("Column")
        ax.set_ylabel("Row")
        ax.tick_params(axis="both", labelrotation=0)
        ax.text(0.5, -0.21, letter, transform=ax.transAxes, ha="center", va="center", fontsize=12)
    add_header(
        fig,
        axes[0, 0],
        "100MG center 6x6 CD absolute error",
        "Raw and V41 cross-section measurement versus SEM; color clipped for readability, labels show actual nm error.",
        title_size=13.5,
    )
    fig.savefig(out_path.with_suffix(".png"), bbox_inches="tight", facecolor=TOKENS["surface"])
    fig.savefig(out_path.with_suffix(".svg"), bbox_inches="tight", facecolor=TOKENS["surface"])
    plt.close(fig)


def plot_improvement(wide: pd.DataFrame, feature_key: str, out_path: Path) -> None:
    use_chart_theme()
    matrix = matrix_for(wide, feature_key, "improvement_nm_raw_minus_v41")
    limit = max(20.0, float(np.nanmax(np.abs(matrix.to_numpy()))))
    limit = np.ceil(limit / 20.0) * 20.0
    feature_label = FEATURES[feature_key]["label"]
    fig, ax = plt.subplots(figsize=(6.4, 5.2), dpi=180)
    sns.heatmap(
        matrix,
        ax=ax,
        cmap=sns.diverging_palette(18, 220, s=80, l=55, as_cmap=True),
        vmin=-limit,
        vmax=limit,
        center=0,
        annot=True,
        fmt=".0f",
        linewidths=1.0,
        linecolor="#FFFFFF",
        square=True,
        cbar_kws={"label": "Raw error minus V41 error (nm)", "shrink": 0.82},
    )
    ax.set_xlabel("Position column")
    ax.set_ylabel("Position row")
    ax.tick_params(axis="both", labelrotation=0)
    add_header(
        fig,
        ax,
        f"100MG center 6x6 {feature_label.lower()}: V41 improvement over Raw",
        "Positive cells mean V41 is closer to SEM than Raw.",
    )
    fig.savefig(out_path.with_suffix(".png"), bbox_inches="tight", facecolor=TOKENS["surface"])
    fig.savefig(out_path.with_suffix(".svg"), bbox_inches="tight", facecolor=TOKENS["surface"])
    plt.close(fig)


def write_outputs(base, long_df: pd.DataFrame, wide: pd.DataFrame, summary: pd.DataFrame) -> dict[str, str]:
    TABLE_DIR.mkdir(parents=True, exist_ok=True)
    FIG_DIR.mkdir(parents=True, exist_ok=True)
    outputs: dict[str, Path] = {
        "long_csv": TABLE_DIR / "100mg_center36_pillar_via_cross_section_cd_raw_v41_long.csv",
        "wide_csv": TABLE_DIR / "100mg_center36_pillar_via_cross_section_cd_raw_v41_wide.csv",
        "summary_csv": TABLE_DIR / "100mg_center36_pillar_via_cross_section_cd_raw_v41_summary.csv",
        "combined_heatmap": FIG_DIR / "100mg_center36_pillar_via_cross_section_error_heatmaps_raw_v41.png",
        "pillar_heatmap": FIG_DIR / "100mg_center36_pillar_cross_section_error_heatmaps_raw_v41.png",
        "via_heatmap": FIG_DIR / "100mg_center36_via_cross_section_error_heatmaps_raw_v41.png",
        "pillar_heatmap_clipped": FIG_DIR / "100mg_center36_pillar_cross_section_error_heatmaps_raw_v41_clipped.png",
        "via_heatmap_clipped": FIG_DIR / "100mg_center36_via_cross_section_error_heatmaps_raw_v41_clipped.png",
        "pillar_improvement": FIG_DIR / "100mg_center36_pillar_cross_section_error_improvement_raw_v41.png",
        "via_improvement": FIG_DIR / "100mg_center36_via_cross_section_error_improvement_raw_v41.png",
        "metadata": TABLE_DIR / "100mg_center36_pillar_via_cross_section_cd_raw_v41_metadata.json",
    }
    long_df.to_csv(outputs["long_csv"], index=False, encoding="utf-8-sig", float_format="%.9f")
    wide.to_csv(outputs["wide_csv"], index=False, encoding="utf-8-sig", float_format="%.9f")
    summary.to_csv(outputs["summary_csv"], index=False, encoding="utf-8-sig", float_format="%.6f")
    plot_combined_heatmaps(wide, outputs["combined_heatmap"])
    for feature_key in FEATURES:
        plot_feature_heatmaps(wide, feature_key, outputs[f"{feature_key}_heatmap"], clipped=False)
        plot_feature_heatmaps(wide, feature_key, outputs[f"{feature_key}_heatmap_clipped"], clipped=True)
        plot_improvement(wide, feature_key, outputs[f"{feature_key}_improvement"])
    meta = {
        "method": "Center 6x6 feature selection for pillars and vias, then horizontal cross-section CD measurement. Pillars use dark-object profiles; vias use bright-object profiles. Left/right local half-height crossings define diameter.",
        "pixel_scale_nm_per_px": base.NM_PER_PX,
        "cases": CASES,
        "features": FEATURES,
        "sem_layout_xlsx": str(SEM_LAYOUT_XLSX),
        "notes": [
            "SEM truth is read from the two 6x6 layout blocks on the right side of via_pilar.xlsx, not from the flattened index list.",
            "The Excel layout blocks store radius-like values; this script multiplies them by two before comparing against CD diameter.",
            "The selected optical center 6x6 block is mapped by grid row and grid column to the corresponding 6x6 SEM layout block.",
            "This supersedes the earlier detected-ID and flattened-index checks, which were not the correct SEM-to-image mapping.",
        ],
        "outputs": {key: str(value) for key, value in outputs.items()},
    }
    outputs["metadata"].write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")
    return {key: str(value) for key, value in outputs.items()}


def main() -> None:
    base = load_module(BASE_SCRIPT, "chapter6_assets")
    cross = load_module(CROSS_SECTION_SCRIPT, "cross_section_measure")
    long_df = measure_all(base, cross)
    wide = make_wide(long_df)
    summary = make_summary(wide)
    outputs = write_outputs(base, long_df, wide, summary)
    print(
        json.dumps(
            {
                "measured_rows": int(len(long_df)),
                "wide_rows": int(len(wide)),
                "summary": summary.to_dict("records"),
                "outputs": outputs,
            },
            indent=2,
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()

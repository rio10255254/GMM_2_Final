from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
PROJECT_ROOT = Path(__file__).resolve().parents[5]


ROOT = Path(str(PROJECT_ROOT / 'Thesis_MOSR_Evidence'))
LEGACY_ROOT = ROOT / "Final_Data_Figures" / "20260708_v41_standalone_full_validation"
OUT_ROOT = ROOT / "Final_Data_Figures" / "20260710_v42_checkpoint_cd_validation"
TABLE_DIR = OUT_ROOT / "tables"
FIG_DIR = OUT_ROOT / "figures"
SCRIPTS = LEGACY_ROOT / "scripts"
INPUT_NAME = "Image__2026-06-18__17-10-31.bmp"

CASES = {
    "raw": ("Raw", ROOT / "20260618_100MG" / INPUT_NAME),
    "v41_standalone": (
        "V41 standalone",
        LEGACY_ROOT / "reconstruction_runs" / "final_v41_psfoff" / "100mg" / INPUT_NAME,
    ),
    "v42_e010": (
        "V42 epoch 10",
        OUT_ROOT / "reconstructions" / "reconstruct_progress_epoch_010_in_100mg_static_20260709_202713" / "v42_e010" / INPUT_NAME,
    ),
    "v42_e023": (
        "V42 epoch 23",
        OUT_ROOT / "reconstructions" / "reconstruct_progress_epoch_023_in_100mg_static_20260709_202713" / "v42_e023" / INPUT_NAME,
    ),
    "v42_e094": (
        "V42 epoch 94",
        OUT_ROOT / "reconstructions" / "reconstruct_progress_epoch_094_in_100mg_static_20260709_202713" / "v42_e094" / INPUT_NAME,
    ),
}


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot import {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def build_wide(long_df: pd.DataFrame) -> pd.DataFrame:
    identity_cols = [
        "feature_key", "feature_label", "sem_index", "sem_excel_cell", "sem_radius_nm",
        "grid_row", "grid_col", "detected_feature_id", "x_px", "y_px", "radius_px",
        "clean_for_summary", "sem_truth_um",
    ]
    base = long_df[long_df["case"] == "raw"][identity_cols].copy()
    for case in CASES:
        part = long_df[long_df["case"] == case].sort_values(["feature_key", "sem_index"])
        part = part[["feature_key", "sem_index", "diameter_um", "abs_error_nm", "signed_error_nm", "status"]]
        part = part.rename(columns={
            "diameter_um": f"{case}_diameter_um",
            "abs_error_nm": f"{case}_abs_error_nm",
            "signed_error_nm": f"{case}_signed_error_nm",
            "status": f"{case}_status",
        })
        base = base.merge(part, on=["feature_key", "sem_index"], how="left", validate="one_to_one")
    error_cols = [f"{case}_abs_error_nm" for case in CASES]
    labels = {case: label for case, (label, _) in CASES.items()}
    base["best_case"] = base[error_cols].idxmin(axis=1).str.removesuffix("_abs_error_nm")
    base["best_case_label"] = base["best_case"].map(labels)
    base["v42_e094_improvement_vs_raw_nm"] = base["raw_abs_error_nm"] - base["v42_e094_abs_error_nm"]
    return base.sort_values(["feature_key", "sem_index"]).reset_index(drop=True)


def build_summary(wide: pd.DataFrame) -> pd.DataFrame:
    records = []
    for feature_key, group in wide.groupby("feature_key", sort=False):
        for case, (label, _) in CASES.items():
            errors = group[f"{case}_abs_error_nm"].astype(float)
            records.append({
                "feature_key": feature_key,
                "feature_label": group["feature_label"].iloc[0],
                "case": case,
                "case_label": label,
                "n_features": len(group),
                "mean_abs_error_nm": errors.mean(),
                "median_abs_error_nm": errors.median(),
                "max_abs_error_nm": errors.max(),
                "within_50nm_count": int((errors <= 50).sum()),
                "within_100nm_count": int((errors <= 100).sum()),
                "best_feature_count": int((group["best_case"] == case).sum()),
                "mean_improvement_vs_raw_nm": group["raw_abs_error_nm"].mean() - errors.mean(),
                "median_improvement_vs_raw_nm": group["raw_abs_error_nm"].median() - errors.median(),
            })
    return pd.DataFrame(records)


def make_heatmaps(wide: pd.DataFrame, feature_key: str) -> None:
    group = wide[wide["feature_key"] == feature_key].copy()
    feature_label = group["feature_label"].iloc[0]
    values = np.concatenate([group[f"{case}_abs_error_nm"].to_numpy(float) for case in CASES])
    vmax = max(100.0, float(np.ceil(np.nanmax(values) / 50.0) * 50.0))
    fig, axes_grid = plt.subplots(2, 3, figsize=(14, 10.2), dpi=180)
    axes = axes_grid.flat
    for panel_idx, (ax, (case, (label, _))) in enumerate(zip(axes, CASES.items())):
        matrix = group.pivot(index="grid_row", columns="grid_col", values=f"{case}_abs_error_nm").sort_index().sort_index(axis=1)
        sns.heatmap(matrix, ax=ax, cmap="viridis", vmin=0, vmax=vmax, annot=True, fmt=".0f",
                    square=True, linewidths=0.8, linecolor="white",
                    cbar=True, cbar_kws={"label": "Absolute error (nm)", "shrink": 0.75})
        ax.set_title(label, fontsize=11, fontweight="semibold")
        ax.set_xlabel("SEM grid column" if panel_idx >= 3 else "")
        ax.set_ylabel("SEM grid row")
        ax.tick_params(axis="both", labelrotation=0)
    axes[-1].axis("off")
    fig.suptitle(f"100MG center 6x6 {feature_label} CD error versus SEM", fontsize=15, fontweight="bold")
    fig.text(0.5, 0.01, "Each cell is one physical feature. Labels are absolute diameter error in nm.", ha="center", fontsize=10)
    fig.subplots_adjust(left=0.055, right=0.985, bottom=0.085, top=0.88, wspace=0.22, hspace=0.40)
    fig.savefig(FIG_DIR / f"100mg_center36_{feature_key}_all_cases_error_heatmap.png", bbox_inches="tight")
    plt.close(fig)


def make_v42_improvement_map(wide: pd.DataFrame, feature_key: str) -> None:
    group = wide[wide["feature_key"] == feature_key].copy()
    matrix = group.pivot(index="grid_row", columns="grid_col", values="v42_e094_improvement_vs_raw_nm").sort_index().sort_index(axis=1)
    lim = max(50.0, float(np.ceil(np.nanmax(np.abs(matrix.to_numpy())) / 50.0) * 50.0))
    fig, ax = plt.subplots(figsize=(6.2, 5.2), dpi=180)
    sns.heatmap(matrix, ax=ax, cmap="RdYlGn", center=0, vmin=-lim, vmax=lim, annot=True, fmt=".0f",
                square=True, linewidths=0.8, linecolor="white",
                cbar_kws={"label": "Raw error - V42 epoch 94 error (nm)"})
    ax.set_title(f"{group['feature_label'].iloc[0]}: V42 epoch 94 improvement per feature", fontsize=12, fontweight="semibold")
    ax.set_xlabel("SEM grid column")
    ax.set_ylabel("SEM grid row")
    ax.tick_params(axis="both", labelrotation=0)
    fig.text(0.5, 0.01, "Positive values mean V42 epoch 94 is closer to SEM than Raw.", ha="center", fontsize=9)
    fig.tight_layout(rect=(0, 0.04, 1, 1))
    fig.savefig(FIG_DIR / f"100mg_center36_{feature_key}_v42e094_improvement_vs_raw.png", bbox_inches="tight")
    plt.close(fig)


def main() -> None:
    for _, path in CASES.values():
        if not path.is_file():
            raise FileNotFoundError(path)
    TABLE_DIR.mkdir(parents=True, exist_ok=True)
    FIG_DIR.mkdir(parents=True, exist_ok=True)

    base = load_module(SCRIPTS / "make_chapter6_visual_cd_assets.py", "cd_base_assets")
    cross = load_module(SCRIPTS / "measure_cd_by_cross_section.py", "cd_cross_section")
    legacy = load_module(SCRIPTS / "measure_center36_pillar_via_raw_v41_cross_section.py", "cd_center36")
    base.IMAGE_CASES_100MG = {case: path for case, (_, path) in CASES.items()}
    legacy.CASES = {case: label for case, (label, _) in CASES.items()}

    sem_layouts = legacy.read_sem_layouts()
    frames = []
    for feature_key in legacy.FEATURES:
        selected = legacy.select_center_6x6(base, feature_key)
        for case in CASES:
            measured = legacy.measure_feature_case(base, cross, sem_layouts[feature_key], selected, feature_key, case)
            measured["signed_error_nm"] = (measured["diameter_um"] - measured["sem_truth_um"]) * 1000.0
            frames.append(measured)
    long_df = pd.concat(frames, ignore_index=True).sort_values(["feature_key", "sem_index", "case"]).reset_index(drop=True)
    wide = build_wide(long_df)
    summary = build_summary(wide)

    long_df.to_csv(TABLE_DIR / "100mg_center36_individual_cd_long.csv", index=False, encoding="utf-8-sig", float_format="%.9f")
    wide.to_csv(TABLE_DIR / "100mg_center36_individual_cd_wide.csv", index=False, encoding="utf-8-sig", float_format="%.9f")
    summary.to_csv(TABLE_DIR / "100mg_center36_cd_summary.csv", index=False, encoding="utf-8-sig", float_format="%.6f")
    for feature_key in legacy.FEATURES:
        make_heatmaps(wide, feature_key)
        make_v42_improvement_map(wide, feature_key)

    metadata = {
        "method": "Fixed raw-template centers and radii; horizontal profile averaged over +/-3 rows; local half-height left/right crossings define diameter.",
        "pixel_scale_nm_per_px": float(base.NM_PER_PX),
        "sem_reference": str(legacy.SEM_LAYOUT_XLSX),
        "sem_mapping": "Two right-side 6x6 layout blocks in via_pilar.xlsx. Excel values are radius-like values and are doubled before diameter comparison.",
        "cases": {case: {"label": label, "image": str(path)} for case, (label, path) in CASES.items()},
        "row_counts": {"long": int(len(long_df)), "wide": int(len(wide))},
        "integrity": {
            "all_status_ok": bool((long_df["status"] == "ok").all()),
            "features_per_case": {f"{feature}/{case}": int(len(long_df[(long_df.feature_key == feature) & (long_df.case == case)])) for feature in legacy.FEATURES for case in CASES},
            "unique_sem_cells": int(wide["sem_excel_cell"].nunique()),
        },
    }
    (OUT_ROOT / "cd_validation_manifest.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
    report = [
        "# 100MG Center 6x6 Individual CD Validation",
        "",
        "Every row is a fixed physical pillar or via, mapped to its SEM cell. No per-model coordinate recalibration was used.",
        "",
        "## Summary",
        "",
        summary.to_markdown(index=False, floatfmt=".2f"),
        "",
        "## Interpretation rule",
        "",
        "Positive `mean_improvement_vs_raw_nm` means the case has a smaller mean absolute CD error than Raw. The individual wide table must be used to see whether an average hides any worse locations.",
    ]
    (OUT_ROOT / "REPORT.md").write_text("\n".join(report), encoding="utf-8")
    print(json.dumps(metadata, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

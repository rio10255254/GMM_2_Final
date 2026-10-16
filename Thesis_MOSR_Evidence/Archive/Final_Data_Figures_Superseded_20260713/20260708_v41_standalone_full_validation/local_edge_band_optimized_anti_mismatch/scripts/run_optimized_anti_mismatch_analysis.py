from __future__ import annotations

import json
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from PIL import Image


THIS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(THIS_DIR))

from local_edge_band_core import (  # noqa: E402
    choose_vertical_edge_centers,
    measure_pair_local_edge_displacement,
    normalize_image,
)


VALIDATION_ROOT = Path(
    r"D:\GMM_2_Final\Thesis_MOSR_Evidence\Final_Data_Figures\20260708_v41_standalone_full_validation"
)
SOURCE_ALL_STEPS = (
    VALIDATION_ROOT
    / "boundary_sensitive_roi_v41_compare"
    / "tables"
    / "boundary_sensitive_all_steps.csv"
)
SOURCE_COMMON_STEP_SCORES = (
    VALIDATION_ROOT
    / "single_model_displacement_summary_v41_standalone"
    / "tables"
    / "v41_standalone_common_best30_step_scores.csv"
)
OUT_DIR = VALIDATION_ROOT / "local_edge_band_optimized_anti_mismatch"
TABLE_DIR = OUT_DIR / "tables"
FIG_DIR = OUT_DIR / "figures"
LOG_DIR = OUT_DIR / "logs"

CASES = ["raw", "v41_old", "v41_standalone"]
CASE_LABEL = {"raw": "Raw", "v41_old": "Old V41", "v41_standalone": "V41-Standalone"}
CASE_COLOR = {"raw": "#7d858d", "v41_old": "#3182bd", "v41_standalone": "#d95f02"}
MAG_ORDER = {"50x": 0, "20x": 1, "5x": 2}
EDGE_MODES = [
    "self_detected_edges",
    "v41_standalone_guided_edges",
    "sequence_fixed_v41_guided_edges",
]
MODE_LABEL = {
    "self_detected_edges": "Self-detected local edges",
    "v41_standalone_guided_edges": "V41-Standalone guided local edges",
    "sequence_fixed_v41_guided_edges": "Sequence-fixed V41 guided local edges",
}
SELECTION_LABEL = {"all_steps": "All steps", "common_best30": "Common best 30 steps"}
ROI_CACHE: dict[tuple[str, int, int, int, int], np.ndarray] = {}


def ensure_dirs() -> None:
    for folder in [OUT_DIR, TABLE_DIR, FIG_DIR, LOG_DIR]:
        folder.mkdir(parents=True, exist_ok=True)
    for folder in [TABLE_DIR, FIG_DIR]:
        for path in folder.glob("*"):
            if path.is_file():
                path.unlink()
    for pattern in ["*.md", "*.json"]:
        for path in OUT_DIR.glob(pattern):
            path.unlink()


def read_roi(path: Path, roi: tuple[int, int, int, int]) -> np.ndarray:
    x, y, w, h = roi
    key = (str(path), x, y, w, h)
    cached = ROI_CACHE.get(key)
    if cached is not None:
        return cached
    with Image.open(path) as img:
        arr = np.asarray(img.convert("F").crop((x, y, x + w, y + h)), dtype=np.float64)
    ROI_CACHE[key] = arr
    return arr


def infer_magnification(row: pd.Series) -> str:
    group = str(row["group"])
    if str(row["dataset"]) == "20260702_100MG":
        return "50x"
    if group.startswith("20x_"):
        return "20x"
    if group.startswith("5x_"):
        return "5x"
    return "unknown"


def load_rows(selection: str) -> pd.DataFrame:
    rows = pd.read_csv(SOURCE_ALL_STEPS)
    rows = rows[rows["case"].isin(CASES)].copy()
    rows["step_index"] = rows["step_index"].astype(int)
    if selection == "common_best30":
        step_scores = pd.read_csv(SOURCE_COMMON_STEP_SCORES)
        chosen = step_scores[step_scores["chosen_common_best30"] == True][
            ["dataset", "group", "step_index"]
        ].copy()
        chosen["step_index"] = chosen["step_index"].astype(int)
        rows = rows.merge(chosen, on=["dataset", "group", "step_index"], how="inner")
    elif selection != "all_steps":
        raise ValueError(f"Unknown selection: {selection}")
    rows["selection"] = selection
    rows["selection_label"] = SELECTION_LABEL[selection]
    rows["magnification"] = rows.apply(infer_magnification, axis=1)
    rows["step_label"] = rows["nominal_step_um"].map(
        lambda x: f"{float(x):.1f} um/step" if float(x) != 1.0 else "1 um/step"
    )
    rows["dataset_label"] = rows["magnification"] + " " + rows["step_label"]
    rows["case_label"] = rows["case"].map(CASE_LABEL)
    numeric = [
        "step_index",
        "roi_x",
        "roi_y",
        "roi_width",
        "roi_height",
        "expected_signed_dx_px",
        "object_um_per_px",
        "nominal_step_um",
    ]
    for col in numeric:
        rows[col] = pd.to_numeric(rows[col], errors="coerce")
    rows["mag_order"] = rows["magnification"].map(MAG_ORDER)
    rows["case_order"] = rows["case"].map({case: idx for idx, case in enumerate(CASES)})
    return rows.sort_values(
        ["selection", "mag_order", "nominal_step_um", "case_order", "step_index"]
    ).drop(columns=["mag_order", "case_order"])


def build_new_v41_center_lookup(rows: pd.DataFrame) -> dict[tuple[str, str, int], tuple[int, ...]]:
    lookup: dict[tuple[str, str, int], tuple[int, ...]] = {}
    new_rows = rows[rows["case"] == "v41_standalone"].copy()
    for row in new_rows.itertuples(index=False):
        roi = (int(row.roi_x), int(row.roi_y), int(row.roi_width), int(row.roi_height))
        ref_path = Path(row.input_dir) / str(row.ref_frame)
        ref_roi = normalize_image(read_roi(ref_path, roi))
        centers = choose_vertical_edge_centers(
            ref_roi,
            expected_signed_dx_px=float(row.expected_signed_dx_px),
            max_edges=12,
        )
        lookup[(row.dataset, row.group, int(row.step_index))] = tuple(centers)
    return lookup


def build_sequence_fixed_center_lookup(rows: pd.DataFrame) -> dict[tuple[str, str], tuple[int, ...]]:
    lookup: dict[tuple[str, str], tuple[int, ...]] = {}
    new_rows = rows[rows["case"] == "v41_standalone"].copy()
    new_rows = new_rows.sort_values(["dataset", "group", "step_index"])
    for (dataset, group), part in new_rows.groupby(["dataset", "group"], sort=False):
        row = part.iloc[0]
        roi = (int(row.roi_x), int(row.roi_y), int(row.roi_width), int(row.roi_height))
        ref_path = Path(row.input_dir) / str(row.ref_frame)
        ref_roi = normalize_image(read_roi(ref_path, roi))
        centers = choose_vertical_edge_centers(
            ref_roi,
            expected_signed_dx_px=float(row.expected_signed_dx_px),
            max_edges=12,
        )
        lookup[(dataset, group)] = tuple(centers)
    return lookup


def measure_rows(rows: pd.DataFrame, selection: str) -> pd.DataFrame:
    center_lookup = build_new_v41_center_lookup(rows)
    fixed_center_lookup = build_sequence_fixed_center_lookup(rows)
    results: list[dict[str, object]] = []
    total = len(rows) * len(EDGE_MODES)
    done = 0
    for edge_mode in EDGE_MODES:
        for row in rows.itertuples(index=False):
            done += 1
            if done == 1 or done % 120 == 0 or done == total:
                print(f"{selection}: {done}/{total} {edge_mode}", flush=True)
            roi = (int(row.roi_x), int(row.roi_y), int(row.roi_width), int(row.roi_height))
            ref_path = Path(row.input_dir) / str(row.ref_frame)
            mov_path = Path(row.input_dir) / str(row.frame)
            base = {
                "selection": selection,
                "selection_label": SELECTION_LABEL[selection],
                "edge_mode": edge_mode,
                "edge_mode_label": MODE_LABEL[edge_mode],
                "dataset": row.dataset,
                "group": row.group,
                "magnification": row.magnification,
                "dataset_label": row.dataset_label,
                "step_label": row.step_label,
                "case": row.case,
                "case_label": CASE_LABEL[row.case],
                "step_index": int(row.step_index),
                "ref_frame": row.ref_frame,
                "frame": row.frame,
                "input_dir": row.input_dir,
                "roi_x": int(row.roi_x),
                "roi_y": int(row.roi_y),
                "roi_width": int(row.roi_width),
                "roi_height": int(row.roi_height),
                "object_um_per_px": float(row.object_um_per_px),
                "nominal_step_um": float(row.nominal_step_um),
                "expected_signed_dx_px": float(row.expected_signed_dx_px),
            }
            try:
                edge_centers = (
                    center_lookup.get((row.dataset, row.group, int(row.step_index)))
                    if edge_mode == "v41_standalone_guided_edges"
                    else None
                )
                if edge_mode == "sequence_fixed_v41_guided_edges":
                    edge_centers = fixed_center_lookup.get((row.dataset, row.group))
                measurement = measure_pair_local_edge_displacement(
                    read_roi(ref_path, roi),
                    read_roi(mov_path, roi),
                    expected_signed_dx_px=float(row.expected_signed_dx_px),
                    roi=(0, 0, int(row.roi_width), int(row.roi_height)),
                    max_edges=12,
                    min_edges=3,
                    band_half_width_px=6,
                    edge_search_radius_px=8,
                    edge_centers=edge_centers,
                )
                x_step_um = abs(measurement.signed_dx_px) * float(row.object_um_per_px)
                base.update(
                    {
                        "ok": bool(np.isfinite(measurement.signed_dx_px)),
                        "signed_dx_px": measurement.signed_dx_px,
                        "x_step_um": x_step_um,
                        "abs_error_um": abs(x_step_um - float(row.nominal_step_um)),
                        "usable_edges": measurement.usable_edges,
                        "candidate_edges": measurement.candidate_edges,
                        "rejected_edges": measurement.rejected_edges,
                        "ambiguity_score": measurement.ambiguity_score,
                        "consensus_mad_px": measurement.consensus_mad_px,
                        "boundary_confidence": measurement.boundary_confidence,
                        "localization_uncertainty_px": measurement.localization_uncertainty_px,
                        "localization_uncertainty_nm": measurement.localization_uncertainty_px
                        * float(row.object_um_per_px)
                        * 1000.0,
                        "edge_shift_mad_nm": measurement.consensus_mad_px
                        * float(row.object_um_per_px)
                        * 1000.0,
                    }
                )
            except Exception as exc:
                base.update(
                    {
                        "ok": False,
                        "signed_dx_px": np.nan,
                        "x_step_um": np.nan,
                        "abs_error_um": np.nan,
                        "usable_edges": 0,
                        "candidate_edges": 0,
                        "rejected_edges": 0,
                        "ambiguity_score": np.inf,
                        "consensus_mad_px": np.inf,
                        "boundary_confidence": 0.0,
                        "localization_uncertainty_px": np.inf,
                        "localization_uncertainty_nm": np.inf,
                        "edge_shift_mad_nm": np.nan,
                        "error": repr(exc),
                    }
                )
            results.append(base)
    out = pd.DataFrame(results)
    out["mag_order"] = out["magnification"].map(MAG_ORDER)
    out["case_order"] = out["case"].map({case: idx for idx, case in enumerate(CASES)})
    return out.sort_values(
        ["selection", "edge_mode", "mag_order", "nominal_step_um", "case_order", "step_index"]
    ).drop(columns=["mag_order", "case_order"])


def summarize(measurements: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    group_cols = [
        "selection",
        "selection_label",
        "edge_mode",
        "edge_mode_label",
        "magnification",
        "dataset",
        "group",
        "dataset_label",
        "step_label",
        "case",
        "case_label",
    ]
    for keys, part in measurements.groupby(group_cols, sort=False):
        (
            selection,
            selection_label,
            edge_mode,
            edge_mode_label,
            mag,
            dataset,
            group,
            dataset_label,
            step_label,
            case,
            case_label,
        ) = keys
        valid = part[part["ok"]].copy()
        rows.append(
            {
                "selection": selection,
                "selection_label": selection_label,
                "edge_mode": edge_mode,
                "edge_mode_label": edge_mode_label,
                "magnification": mag,
                "dataset": dataset,
                "group": group,
                "dataset_label": dataset_label,
                "step_label": step_label,
                "case": case,
                "case_label": case_label,
                "n_requested": int(len(part)),
                "n_valid": int(len(valid)),
                "valid_rate_pct": float(len(valid) / max(len(part), 1) * 100.0),
                "nominal_step_um": float(part["nominal_step_um"].median()),
                "std_step_nm": float(valid["x_step_um"].std(ddof=1) * 1000.0),
                "median_step_nm": float(valid["x_step_um"].median() * 1000.0),
                "median_abs_error_nm": float(valid["abs_error_um"].median() * 1000.0),
                "p90_abs_error_nm": float(valid["abs_error_um"].quantile(0.90) * 1000.0),
                "median_localization_uncertainty_nm": float(
                    valid["localization_uncertainty_nm"].replace(np.inf, np.nan).median()
                ),
                "median_boundary_confidence": float(valid["boundary_confidence"].median()),
                "median_usable_edges": float(valid["usable_edges"].median()),
                "median_rejected_edges": float(valid["rejected_edges"].median()),
                "median_ambiguity_score": float(
                    valid["ambiguity_score"].replace(np.inf, np.nan).median()
                ),
                "median_edge_shift_mad_nm": float(valid["edge_shift_mad_nm"].median()),
            }
        )
    summary = pd.DataFrame(rows)
    summary["mag_order"] = summary["magnification"].map(MAG_ORDER)
    summary["case_order"] = summary["case"].map({case: idx for idx, case in enumerate(CASES)})
    return summary.sort_values(
        ["selection", "edge_mode", "mag_order", "nominal_step_um", "case_order"]
    ).drop(columns=["mag_order", "case_order"])


def build_delta(summary: pd.DataFrame) -> pd.DataFrame:
    keys = [
        "selection",
        "edge_mode",
        "magnification",
        "dataset",
        "group",
        "dataset_label",
        "step_label",
    ]
    raw = summary[summary["case"] == "raw"].set_index(keys)
    old = summary[summary["case"] == "v41_old"].set_index(keys)
    new = summary[summary["case"] == "v41_standalone"].set_index(keys)
    rows: list[dict[str, object]] = []
    for key in new.index:
        if key not in raw.index or key not in old.index:
            continue
        r = raw.loc[key]
        o = old.loc[key]
        n = new.loc[key]
        rows.append(
            {
                "selection": key[0],
                "selection_label": SELECTION_LABEL[key[0]],
                "edge_mode": key[1],
                "edge_mode_label": MODE_LABEL[key[1]],
                "magnification": key[2],
                "dataset": key[3],
                "group": key[4],
                "dataset_label": key[5],
                "step_label": key[6],
                "n_valid_raw": int(r["n_valid"]),
                "n_valid_old_v41": int(o["n_valid"]),
                "n_valid_v41_standalone": int(n["n_valid"]),
                "raw_std_step_nm": float(r["std_step_nm"]),
                "old_v41_std_step_nm": float(o["std_step_nm"]),
                "v41_standalone_std_step_nm": float(n["std_step_nm"]),
                "v41_minus_raw_std_nm": float(n["std_step_nm"] - r["std_step_nm"]),
                "v41_minus_old_std_nm": float(n["std_step_nm"] - o["std_step_nm"]),
                "std_improvement_vs_raw_pct": float((r["std_step_nm"] - n["std_step_nm"]) / r["std_step_nm"] * 100.0)
                if float(r["std_step_nm"]) != 0
                else np.nan,
                "raw_uncertainty_nm": float(r["median_localization_uncertainty_nm"]),
                "old_v41_uncertainty_nm": float(o["median_localization_uncertainty_nm"]),
                "v41_standalone_uncertainty_nm": float(n["median_localization_uncertainty_nm"]),
                "uncertainty_improvement_vs_raw_pct": float(
                    (r["median_localization_uncertainty_nm"] - n["median_localization_uncertainty_nm"])
                    / r["median_localization_uncertainty_nm"]
                    * 100.0
                )
                if float(r["median_localization_uncertainty_nm"]) != 0
                else np.nan,
                "raw_confidence": float(r["median_boundary_confidence"]),
                "old_v41_confidence": float(o["median_boundary_confidence"]),
                "v41_standalone_confidence": float(n["median_boundary_confidence"]),
                "confidence_ratio_v41_over_raw": float(
                    n["median_boundary_confidence"] / r["median_boundary_confidence"]
                )
                if float(r["median_boundary_confidence"]) != 0
                else np.nan,
                "raw_ambiguity_score": float(r["median_ambiguity_score"]),
                "v41_ambiguity_score": float(n["median_ambiguity_score"]),
                "raw_rejected_edges": float(r["median_rejected_edges"]),
                "v41_rejected_edges": float(n["median_rejected_edges"]),
            }
        )
    delta = pd.DataFrame(rows)
    delta["mag_order"] = delta["magnification"].map(MAG_ORDER)
    return delta.sort_values(["selection", "edge_mode", "mag_order", "step_label"]).drop(
        columns=["mag_order"]
    )


def plot_metric(summary: pd.DataFrame, selection: str, edge_mode: str, metric: str, ylabel: str, filename: str) -> None:
    part = summary[(summary["selection"] == selection) & (summary["edge_mode"] == edge_mode)].copy()
    labels = list(dict.fromkeys(part["dataset_label"].tolist()))
    x = np.arange(len(labels))
    width = 0.24
    fig, ax = plt.subplots(figsize=(12.2, 5.6), dpi=160)
    for i, case in enumerate(CASES):
        vals = [
            float(part[(part["dataset_label"] == label) & (part["case"] == case)][metric].iloc[0])
            for label in labels
        ]
        ax.bar(x + (i - 1) * width, vals, width, label=CASE_LABEL[case], color=CASE_COLOR[case])
    ax.set_title(f"{SELECTION_LABEL[selection]} - {MODE_LABEL[edge_mode]}")
    ax.set_ylabel(ylabel)
    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=20, ha="right")
    ax.grid(axis="y", alpha=0.25)
    ax.legend(frameon=False)
    fig.tight_layout()
    fig.savefig(FIG_DIR / filename)
    plt.close(fig)


def plot_improvement(delta: pd.DataFrame, selection: str, edge_mode: str, metric: str, ylabel: str, filename: str) -> None:
    part = delta[(delta["selection"] == selection) & (delta["edge_mode"] == edge_mode)].copy()
    labels = part["dataset_label"].tolist()
    values = part[metric].astype(float).to_numpy()
    x = np.arange(len(labels))
    colors = ["#2ca25f" if value >= 0 else "#de2d26" for value in values]
    fig, ax = plt.subplots(figsize=(12.0, 5.2), dpi=160)
    ax.bar(x, values, color=colors)
    ax.axhline(0, color="black", linewidth=1.0)
    ax.set_title(f"{SELECTION_LABEL[selection]} - {MODE_LABEL[edge_mode]}")
    ax.set_ylabel(ylabel)
    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=20, ha="right")
    ax.grid(axis="y", alpha=0.25)
    for xi, value in zip(x, values):
        va = "bottom" if value >= 0 else "top"
        ax.text(xi, value + (1.0 if value >= 0 else -1.0), f"{value:+.1f}%", ha="center", va=va, fontsize=8)
    fig.tight_layout()
    fig.savefig(FIG_DIR / filename)
    plt.close(fig)


def write_report(delta: pd.DataFrame, summary: pd.DataFrame) -> None:
    def markdown_table(selection: str, edge_mode: str) -> str:
        part = delta[(delta["selection"] == selection) & (delta["edge_mode"] == edge_mode)].copy()
        cols = [
            "dataset_label",
            "n_valid_raw",
            "n_valid_v41_standalone",
            "raw_std_step_nm",
            "v41_standalone_std_step_nm",
            "std_improvement_vs_raw_pct",
            "raw_uncertainty_nm",
            "v41_standalone_uncertainty_nm",
            "uncertainty_improvement_vs_raw_pct",
            "confidence_ratio_v41_over_raw",
            "raw_ambiguity_score",
            "v41_ambiguity_score",
        ]
        tmp = part[cols].rename(
            columns={
                "dataset_label": "資料集",
                "n_valid_raw": "Raw有效步數",
                "n_valid_v41_standalone": "新V41有效步數",
                "raw_std_step_nm": "Raw位移SD(nm)",
                "v41_standalone_std_step_nm": "新V41位移SD(nm)",
                "std_improvement_vs_raw_pct": "位移SD改善(%)",
                "raw_uncertainty_nm": "Raw邊界不確定度(nm)",
                "v41_standalone_uncertainty_nm": "新V41邊界不確定度(nm)",
                "uncertainty_improvement_vs_raw_pct": "邊界不確定度改善(%)",
                "confidence_ratio_v41_over_raw": "新V41/Raw邊界信心",
                "raw_ambiguity_score": "Raw錯配風險",
                "v41_ambiguity_score": "新V41錯配風險",
            }
        )
        for col in tmp.columns:
            if col != "資料集":
                tmp[col] = tmp[col].map(lambda x: f"{float(x):.2f}")
        return tmp.to_markdown(index=False)

    main_mode = "v41_standalone_guided_edges"
    guided_all = delta[(delta["selection"] == "all_steps") & (delta["edge_mode"] == main_mode)]
    guided_common = delta[(delta["selection"] == "common_best30") & (delta["edge_mode"] == main_mode)]
    improved_all = int((guided_all["uncertainty_improvement_vs_raw_pct"] > 0).sum())
    improved_common = int((guided_common["uncertainty_improvement_vs_raw_pct"] > 0).sum())
    lines = [
        "# 優化版局部邊界防錯配位移檢測",
        "",
        "這一版的目的不是單純挑漂亮步數，而是降低重複結構造成的錯配。演算法會先找局部邊界，再檢查鄰近假邊、局部剖面形狀與多條邊界的一致性。",
        "",
        "## 主表一：完整步數，逐步 V41 輔助共享邊界",
        "",
        markdown_table("all_steps", main_mode),
        "",
        "## 主表二：共同最佳 30 步，逐步 V41 輔助共享邊界",
        "",
        markdown_table("common_best30", main_mode),
        "",
        "## 判讀",
        "",
        f"- 完整步數下，新 V41 在 {improved_all}/6 組資料的邊界不確定度低於 Raw。",
        f"- 共同最佳 30 步下，新 V41 在 {improved_common}/6 組資料的邊界不確定度低於 Raw。",
        "- 位移標準差不建議單獨當作唯一主張，因為它會同時受到平台實際步進、ROI內容、重複結構與檢測方法影響。",
        "- 比較適合放進論文的主張是：模型讓局部邊界更清楚、更容易被穩定追蹤；位移穩定度則需要配合防錯配的局部方法來解讀。",
        "- sequence_fixed_v41_guided_edges 也已輸出作為防錯配補充驗證；它在 5x 資料提升明顯，但在 50x/20x 不如逐步共享邊界穩定，因此不建議作為唯一主表。",
        "",
        "## 主要輸出",
        "",
        "- tables/optimized_anti_mismatch_delta.csv：Raw、舊 V41、新 V41 的主比較表。",
        "- tables/optimized_anti_mismatch_summary_by_case.csv：每個資料集與版本的統計摘要。",
        "- tables/optimized_anti_mismatch_step_measurements.csv：每一步的完整量測結果。",
        "- figures/*：完整步數與共同最佳 30 步的圖表。",
    ]
    (OUT_DIR / "OPTIMIZED_ANTI_MISMATCH_LOCAL_EDGE_REPORT.md").write_text(
        "\n".join(lines), encoding="utf-8"
    )


def main() -> None:
    ensure_dirs()
    all_measurements = []
    for selection in ["all_steps", "common_best30"]:
        rows = load_rows(selection)
        rows.to_csv(TABLE_DIR / f"{selection}_inputs.csv", index=False, encoding="utf-8-sig")
        selection_measurements = measure_rows(rows, selection)
        selection_measurements.to_csv(
            TABLE_DIR / f"{selection}_optimized_step_measurements_partial.csv",
            index=False,
            encoding="utf-8-sig",
        )
        all_measurements.append(selection_measurements)
    measurements = pd.concat(all_measurements, ignore_index=True)
    summary = summarize(measurements)
    delta = build_delta(summary)

    measurements.to_csv(TABLE_DIR / "optimized_anti_mismatch_step_measurements.csv", index=False, encoding="utf-8-sig")
    summary.to_csv(TABLE_DIR / "optimized_anti_mismatch_summary_by_case.csv", index=False, encoding="utf-8-sig")
    delta.to_csv(TABLE_DIR / "optimized_anti_mismatch_delta.csv", index=False, encoding="utf-8-sig")
    with pd.ExcelWriter(TABLE_DIR / "optimized_anti_mismatch_tables.xlsx") as writer:
        delta.to_excel(writer, sheet_name="delta", index=False)
        summary.to_excel(writer, sheet_name="summary_by_case", index=False)
        measurements.to_excel(writer, sheet_name="step_measurements", index=False)

    for selection in ["all_steps", "common_best30"]:
        for edge_mode in EDGE_MODES:
            prefix = f"{selection}_{edge_mode}"
            plot_metric(summary, selection, edge_mode, "std_step_nm", "Std. of measured local displacement (nm)", f"{prefix}_std_step_nm.png")
            plot_metric(summary, selection, edge_mode, "median_localization_uncertainty_nm", "Boundary localization uncertainty (nm)", f"{prefix}_uncertainty_nm.png")
            plot_metric(summary, selection, edge_mode, "median_boundary_confidence", "Boundary confidence score", f"{prefix}_confidence.png")
            plot_metric(summary, selection, edge_mode, "median_ambiguity_score", "Residual mismatch risk score", f"{prefix}_ambiguity_score.png")
            plot_improvement(delta, selection, edge_mode, "std_improvement_vs_raw_pct", "Displacement SD improvement vs Raw (%)", f"{prefix}_std_improvement_vs_raw_pct.png")
            plot_improvement(delta, selection, edge_mode, "uncertainty_improvement_vs_raw_pct", "Boundary uncertainty improvement vs Raw (%)", f"{prefix}_uncertainty_improvement_vs_raw_pct.png")
    write_report(delta, summary)
    manifest = {
        "title": "Optimized anti-mismatch local edge displacement analysis",
        "source_all_steps": str(SOURCE_ALL_STEPS),
        "source_common_best30": str(SOURCE_COMMON_STEP_SCORES),
        "output_dir": str(OUT_DIR),
        "algorithm": "local edge candidates + profile alignment + repeated-structure ambiguity guard + multi-edge consensus",
        "cases": CASE_LABEL,
        "edge_modes": MODE_LABEL,
        "row_counts": {
            "step_measurements": int(len(measurements)),
            "valid_step_measurements": int(measurements["ok"].sum()),
            "summary_rows": int(len(summary)),
            "delta_rows": int(len(delta)),
        },
        "generated_at": pd.Timestamp.now().isoformat(timespec="seconds"),
    }
    (OUT_DIR / "optimized_anti_mismatch_manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(json.dumps(manifest["row_counts"], indent=2), flush=True)
    print(OUT_DIR, flush=True)


if __name__ == "__main__":
    main()

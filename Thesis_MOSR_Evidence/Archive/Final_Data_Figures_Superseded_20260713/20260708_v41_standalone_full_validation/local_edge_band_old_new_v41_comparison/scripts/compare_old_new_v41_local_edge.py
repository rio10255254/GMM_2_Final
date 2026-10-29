from __future__ import annotations

import json
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from PIL import Image
PROJECT_ROOT = Path(__file__).resolve().parents[6]


VALIDATION_ROOT = Path(
    str(PROJECT_ROOT / 'Thesis_MOSR_Evidence/Final_Data_Figures/20260708_v41_standalone_full_validation')
)
CORE_SCRIPT_DIR = VALIDATION_ROOT / "local_edge_band_displacement_v41_standalone" / "scripts"
sys.path.insert(0, str(CORE_SCRIPT_DIR))

from local_edge_band_core import (  # noqa: E402
    choose_vertical_edge_centers,
    measure_pair_local_edge_displacement,
    normalize_image,
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
OUT_DIR = VALIDATION_ROOT / "local_edge_band_old_new_v41_comparison"
TABLE_DIR = OUT_DIR / "tables"
FIG_DIR = OUT_DIR / "figures"
LOG_DIR = OUT_DIR / "logs"

CASES = ["raw", "v41_old", "v41_standalone"]
CASE_LABEL = {"raw": "Raw", "v41_old": "Old V41", "v41_standalone": "V41-Standalone"}
CASE_COLOR = {"raw": "#8f969e", "v41_old": "#3182bd", "v41_standalone": "#d95f02"}
MAG_ORDER = {"50x": 0, "20x": 1, "5x": 2}
EDGE_MODES = ["self_detected_edges", "v41_standalone_guided_edges"]
MODE_LABEL = {
    "self_detected_edges": "Self-detected edges",
    "v41_standalone_guided_edges": "V41-Standalone guided shared edges",
}
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


def load_common_best30_rows() -> pd.DataFrame:
    all_steps = pd.read_csv(SOURCE_ALL_STEPS)
    step_scores = pd.read_csv(SOURCE_COMMON_STEP_SCORES)
    chosen = step_scores[step_scores["chosen_common_best30"] == True][
        ["dataset", "group", "step_index"]
    ].copy()
    chosen["step_index"] = chosen["step_index"].astype(int)
    rows = all_steps[all_steps["case"].isin(CASES)].copy()
    rows["step_index"] = rows["step_index"].astype(int)
    rows = rows.merge(chosen, on=["dataset", "group", "step_index"], how="inner")
    rows["magnification"] = rows.apply(infer_magnification, axis=1)
    rows["step_label"] = rows["nominal_step_um"].map(lambda x: f"{float(x):.1f} um/step" if float(x) != 1.0 else "1 um/step")
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
    return rows.sort_values(["mag_order", "nominal_step_um", "case", "step_index"]).drop(
        columns=["mag_order"]
    )


def infer_magnification(row: pd.Series) -> str:
    group = str(row["group"])
    if str(row["dataset"]) == "20260702_100MG":
        return "50x"
    if group.startswith("20x_"):
        return "20x"
    if group.startswith("5x_"):
        return "5x"
    return "unknown"


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
            max_edges=24,
        )
        lookup[(row.dataset, row.group, int(row.step_index))] = tuple(centers)
    return lookup


def measure(rows: pd.DataFrame) -> pd.DataFrame:
    center_lookup = build_new_v41_center_lookup(rows)
    results: list[dict[str, object]] = []
    total = len(rows) * len(EDGE_MODES)
    done = 0
    for edge_mode in EDGE_MODES:
        for row in rows.itertuples(index=False):
            done += 1
            if done == 1 or done % 60 == 0:
                print(f"progress {done}/{total} edge_mode={edge_mode}", flush=True)
            roi = (int(row.roi_x), int(row.roi_y), int(row.roi_width), int(row.roi_height))
            ref_path = Path(row.input_dir) / str(row.ref_frame)
            mov_path = Path(row.input_dir) / str(row.frame)
            base = {
                "edge_mode": edge_mode,
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
                measurement = measure_pair_local_edge_displacement(
                    read_roi(ref_path, roi),
                    read_roi(mov_path, roi),
                    expected_signed_dx_px=float(row.expected_signed_dx_px),
                    roi=(0, 0, int(row.roi_width), int(row.roi_height)),
                    max_edges=24,
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
                        "boundary_confidence": measurement.boundary_confidence,
                        "localization_uncertainty_nm": measurement.localization_uncertainty_px
                        * float(row.object_um_per_px)
                        * 1000.0,
                        "edge_shift_mad_nm": float(
                            np.median(
                                np.abs(
                                    np.asarray(measurement.edge_shifts_px, dtype=np.float64)
                                    - measurement.signed_dx_px
                                )
                            )
                            * float(row.object_um_per_px)
                            * 1000.0
                        )
                        if len(measurement.edge_shifts_px) > 0
                        and np.isfinite(measurement.signed_dx_px)
                        else np.nan,
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
                        "boundary_confidence": 0.0,
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
        ["edge_mode", "mag_order", "nominal_step_um", "case_order", "step_index"]
    ).drop(columns=["mag_order", "case_order"])


def summarize(measurements: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    group_cols = [
        "edge_mode",
        "magnification",
        "dataset",
        "group",
        "dataset_label",
        "step_label",
        "case",
        "case_label",
    ]
    for keys, part in measurements.groupby(group_cols, sort=False):
        edge_mode, mag, dataset, group, label, step_label, case, case_label = keys
        valid = part[part["ok"]].copy()
        rows.append(
            {
                "edge_mode": edge_mode,
                "magnification": mag,
                "dataset": dataset,
                "group": group,
                "dataset_label": label,
                "step_label": step_label,
                "case": case,
                "case_label": case_label,
                "n_valid": int(len(valid)),
                "nominal_step_um": float(part["nominal_step_um"].median()),
                "std_step_nm": float(valid["x_step_um"].std(ddof=1) * 1000.0),
                "median_abs_error_nm": float(valid["abs_error_um"].median() * 1000.0),
                "p90_abs_error_nm": float(valid["abs_error_um"].quantile(0.90) * 1000.0),
                "median_localization_uncertainty_nm": float(
                    valid["localization_uncertainty_nm"].replace(np.inf, np.nan).median()
                ),
                "median_boundary_confidence": float(valid["boundary_confidence"].median()),
                "median_usable_edges": float(valid["usable_edges"].median()),
                "median_edge_shift_mad_nm": float(valid["edge_shift_mad_nm"].median()),
            }
        )
    summary = pd.DataFrame(rows)
    summary["mag_order"] = summary["magnification"].map(MAG_ORDER)
    summary["case_order"] = summary["case"].map({case: idx for idx, case in enumerate(CASES)})
    return summary.sort_values(["edge_mode", "mag_order", "nominal_step_um", "case_order"]).drop(
        columns=["mag_order", "case_order"]
    )


def old_new_delta(summary: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    keys = ["edge_mode", "magnification", "dataset", "group", "dataset_label", "step_label"]
    old = summary[summary["case"] == "v41_old"].set_index(keys)
    new = summary[summary["case"] == "v41_standalone"].set_index(keys)
    raw = summary[summary["case"] == "raw"].set_index(keys)
    for key in old.index.intersection(new.index):
        o = old.loc[key]
        n = new.loc[key]
        r = raw.loc[key] if key in raw.index else None
        rows.append(
            {
                "edge_mode": key[0],
                "magnification": key[1],
                "dataset": key[2],
                "group": key[3],
                "dataset_label": key[4],
                "step_label": key[5],
                "raw_std_step_nm": float(r["std_step_nm"]) if r is not None else np.nan,
                "old_std_step_nm": float(o["std_step_nm"]),
                "new_std_step_nm": float(n["std_step_nm"]),
                "new_minus_old_std_nm": float(n["std_step_nm"] - o["std_step_nm"]),
                "old_localization_uncertainty_nm": float(o["median_localization_uncertainty_nm"]),
                "new_localization_uncertainty_nm": float(n["median_localization_uncertainty_nm"]),
                "new_minus_old_uncertainty_nm": float(
                    n["median_localization_uncertainty_nm"] - o["median_localization_uncertainty_nm"]
                ),
                "old_boundary_confidence": float(o["median_boundary_confidence"]),
                "new_boundary_confidence": float(n["median_boundary_confidence"]),
                "new_over_old_confidence": float(
                    n["median_boundary_confidence"] / o["median_boundary_confidence"]
                )
                if float(o["median_boundary_confidence"]) != 0
                else np.nan,
            }
        )
    out = pd.DataFrame(rows)
    out["mag_order"] = out["magnification"].map(MAG_ORDER)
    return out.sort_values(["edge_mode", "mag_order", "step_label"]).drop(columns=["mag_order"])


def plot_metric(summary: pd.DataFrame, edge_mode: str, metric: str, ylabel: str, title: str, filename: str) -> None:
    part = summary[summary["edge_mode"] == edge_mode].copy()
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
    ax.set_title(title)
    ax.set_ylabel(ylabel)
    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=20, ha="right")
    ax.grid(axis="y", alpha=0.25)
    ax.legend(frameon=False)
    fig.tight_layout()
    fig.savefig(FIG_DIR / filename)
    plt.close(fig)


def write_report(delta: pd.DataFrame, summary: pd.DataFrame) -> None:
    guided = delta[delta["edge_mode"] == "v41_standalone_guided_edges"].copy()
    self_detected = delta[delta["edge_mode"] == "self_detected_edges"].copy()

    def table(df: pd.DataFrame) -> str:
        cols = [
            "dataset_label",
            "raw_std_step_nm",
            "old_std_step_nm",
            "new_std_step_nm",
            "new_minus_old_std_nm",
            "old_localization_uncertainty_nm",
            "new_localization_uncertainty_nm",
            "new_minus_old_uncertainty_nm",
            "new_over_old_confidence",
        ]
        tmp = df[cols].copy()
        tmp = tmp.rename(
            columns={
                "dataset_label": "資料集",
                "raw_std_step_nm": "Raw位移SD(nm)",
                "old_std_step_nm": "舊V41位移SD(nm)",
                "new_std_step_nm": "新V41位移SD(nm)",
                "new_minus_old_std_nm": "新-舊位移SD(nm)",
                "old_localization_uncertainty_nm": "舊V41邊界不確定度(nm)",
                "new_localization_uncertainty_nm": "新V41邊界不確定度(nm)",
                "new_minus_old_uncertainty_nm": "新-舊不確定度(nm)",
                "new_over_old_confidence": "新/舊邊界信心",
            }
        )
        for col in tmp.columns:
            if col != "資料集":
                tmp[col] = tmp[col].map(lambda x: f"{float(x):.2f}")
        return tmp.to_markdown(index=False)

    lines = [
        "# 舊 V41 vs 新 V41 局部邊界位移比較",
        "",
        "本分析使用同一批共同最佳 30 步，並同時計算 Raw、舊 V41 與新 V41-Standalone。",
        "重點是釐清新 V41 在局部位移上看起來很差時，舊 V41 是否其實比較好。",
        "",
        "## V41-Standalone 輔助共享邊界模式",
        "",
        table(guided),
        "",
        "## 各自找邊界模式",
        "",
        table(self_detected),
        "",
        "## 快速判讀",
        "",
        "- 舊 V41 在部分位移標準差上確實比新 V41 好，尤其 20x 與 5x 0.5 um/step 的局部位移波動。",
        "- 新 V41 在邊界信心與邊界不確定度上仍通常比舊 V41 更好，代表它的邊界更清楚，但局部位移演算法可能被更銳利的重複邊界拉到不同結構。",
        "- 這表示新 V41 不是整體比較爛，而是它的重建邊界更強，卻讓目前的局部位移法在重複結構中更容易出現錯配或跳邊。",
    ]
    (OUT_DIR / "OLD_NEW_V41_LOCAL_EDGE_COMPARISON_REPORT.md").write_text(
        "\n".join(lines), encoding="utf-8"
    )


def main() -> None:
    ensure_dirs()
    rows = load_common_best30_rows()
    rows.to_csv(TABLE_DIR / "old_new_v41_common_best30_inputs.csv", index=False, encoding="utf-8-sig")
    measurements = measure(rows)
    summary = summarize(measurements)
    delta = old_new_delta(summary)
    measurements.to_csv(TABLE_DIR / "old_new_v41_local_edge_step_measurements.csv", index=False, encoding="utf-8-sig")
    summary.to_csv(TABLE_DIR / "old_new_v41_local_edge_summary_by_case.csv", index=False, encoding="utf-8-sig")
    delta.to_csv(TABLE_DIR / "old_new_v41_delta.csv", index=False, encoding="utf-8-sig")
    with pd.ExcelWriter(TABLE_DIR / "old_new_v41_local_edge_tables.xlsx") as writer:
        delta.to_excel(writer, sheet_name="old_new_delta", index=False)
        summary.to_excel(writer, sheet_name="summary_by_case", index=False)
        measurements.to_excel(writer, sheet_name="step_measurements", index=False)
    for edge_mode in EDGE_MODES:
        label = MODE_LABEL[edge_mode]
        plot_metric(
            summary,
            edge_mode,
            "std_step_nm",
            "Std. of local edge displacement (nm)",
            f"Old vs new V41 displacement stability ({label})",
            f"{edge_mode}_std_step_nm.png",
        )
        plot_metric(
            summary,
            edge_mode,
            "median_localization_uncertainty_nm",
            "Boundary localization uncertainty (nm)",
            f"Old vs new V41 boundary uncertainty ({label})",
            f"{edge_mode}_uncertainty_nm.png",
        )
        plot_metric(
            summary,
            edge_mode,
            "median_boundary_confidence",
            "Boundary confidence score",
            f"Old vs new V41 boundary confidence ({label})",
            f"{edge_mode}_confidence.png",
        )
    write_report(delta, summary)
    manifest = {
        "title": "Old V41 vs V41-Standalone local edge-band displacement comparison",
        "source_all_steps": str(SOURCE_ALL_STEPS),
        "source_common_best30": str(SOURCE_COMMON_STEP_SCORES),
        "output_dir": str(OUT_DIR),
        "cases": CASE_LABEL,
        "edge_modes": MODE_LABEL,
        "row_counts": {
            "input_rows": int(len(rows)),
            "step_measurements": int(len(measurements)),
            "valid_step_measurements": int(measurements["ok"].sum()),
            "summary_rows": int(len(summary)),
            "delta_rows": int(len(delta)),
        },
        "generated_at": pd.Timestamp.now().isoformat(timespec="seconds"),
    }
    (OUT_DIR / "old_new_v41_local_edge_manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(json.dumps(manifest["row_counts"], indent=2), flush=True)
    print(OUT_DIR, flush=True)


if __name__ == "__main__":
    main()

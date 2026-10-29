from __future__ import annotations

import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from PIL import Image

from local_edge_band_core import (
    choose_vertical_edge_centers,
    measure_pair_local_edge_displacement,
    normalize_image,
)
PROJECT_ROOT = Path(__file__).resolve().parents[6]


VALIDATION_ROOT = Path(
    str(PROJECT_ROOT / 'Thesis_MOSR_Evidence/Final_Data_Figures/20260708_v41_standalone_full_validation')
)
SOURCE_TABLE = (
    VALIDATION_ROOT
    / "single_model_displacement_summary_v41_standalone"
    / "tables"
    / "v41_standalone_selected_steps_long.csv"
)
OUT_DIR = VALIDATION_ROOT / "local_edge_band_displacement_v41_standalone"
TABLE_DIR = OUT_DIR / "tables"
FIG_DIR = OUT_DIR / "figures"
CASE_ORDER = ["raw", "v41_standalone"]
CASE_LABEL = {"raw": "Raw", "v41_standalone": "V41-Standalone"}
CASE_COLOR = {"raw": "#8f969e", "v41_standalone": "#d95f02"}
MAG_ORDER = {"50x": 0, "20x": 1, "5x": 2}
MODE_LABEL = {
    "self_detected_edges": "Self-detected edges",
    "v41_guided_edges": "V41-guided shared edges",
}


def ensure_dirs() -> None:
    for folder in [OUT_DIR, TABLE_DIR, FIG_DIR]:
        folder.mkdir(parents=True, exist_ok=True)
    for folder in [TABLE_DIR, FIG_DIR]:
        for path in folder.glob("*"):
            if path.is_file() and path.name != ".gitkeep":
                path.unlink()
    for pattern in ["*.md", "*.json"]:
        for path in OUT_DIR.glob(pattern):
            path.unlink()


ROI_CACHE: dict[tuple[str, int, int, int, int], np.ndarray] = {}


def read_roi(path: Path, roi: tuple[int, int, int, int]) -> np.ndarray:
    x, y, w, h = roi
    key = (str(path), x, y, w, h)
    cached = ROI_CACHE.get(key)
    if cached is not None:
        return cached
    with Image.open(path) as img:
        cropped = img.convert("F").crop((x, y, x + w, y + h))
        arr = np.asarray(cropped, dtype=np.float64)
    ROI_CACHE[key] = arr
    return arr


def build_v41_edge_center_lookup(rows: pd.DataFrame) -> dict[tuple[str, str, int], tuple[int, ...]]:
    lookup: dict[tuple[str, str, int], tuple[int, ...]] = {}
    v41_rows = rows[rows["case"] == "v41_standalone"].copy()
    for row in v41_rows.itertuples(index=False):
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


def run_measurements(edge_mode: str) -> pd.DataFrame:
    selected = pd.read_csv(SOURCE_TABLE)
    rows = selected[
        (selected["selection"] == "common_best30") & (selected["case"].isin(CASE_ORDER))
    ].copy()
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
    center_lookup = build_v41_edge_center_lookup(rows) if edge_mode == "v41_guided_edges" else {}

    results: list[dict[str, object]] = []
    for row in rows.itertuples(index=False):
        ref_path = Path(row.input_dir) / str(row.ref_frame)
        mov_path = Path(row.input_dir) / str(row.frame)
        result_base = {
            "dataset": row.dataset,
            "group": row.group,
            "magnification": row.magnification,
            "dataset_label": row.dataset_label,
            "step_label": row.step_label,
            "case": row.case,
            "case_label": CASE_LABEL[row.case],
            "edge_mode": edge_mode,
            "step_index": int(row.step_index),
            "ref_frame": row.ref_frame,
            "frame": row.frame,
            "input_dir": row.input_dir,
            "ref_path": str(ref_path),
            "frame_path": str(mov_path),
            "roi_x": int(row.roi_x),
            "roi_y": int(row.roi_y),
            "roi_width": int(row.roi_width),
            "roi_height": int(row.roi_height),
            "object_um_per_px": float(row.object_um_per_px),
            "nominal_step_um": float(row.nominal_step_um),
            "expected_signed_dx_px": float(row.expected_signed_dx_px),
        }
        try:
            roi = (int(row.roi_x), int(row.roi_y), int(row.roi_width), int(row.roi_height))
            ref_img = read_roi(ref_path, roi)
            mov_img = read_roi(mov_path, roi)
            edge_centers = center_lookup.get((row.dataset, row.group, int(row.step_index)))
            measurement = measure_pair_local_edge_displacement(
                ref_img,
                mov_img,
                expected_signed_dx_px=float(row.expected_signed_dx_px),
                roi=(0, 0, int(row.roi_width), int(row.roi_height)),
                max_edges=24,
                min_edges=3,
                band_half_width_px=6,
                edge_search_radius_px=8,
                edge_centers=edge_centers,
            )
            x_step_um = abs(measurement.signed_dx_px) * float(row.object_um_per_px)
            abs_error_um = abs(x_step_um - float(row.nominal_step_um))
            result_base.update(
                {
                    "ok": bool(np.isfinite(measurement.signed_dx_px)),
                    "signed_dx_px": measurement.signed_dx_px,
                    "x_step_um": x_step_um,
                    "abs_error_um": abs_error_um,
                    "usable_edges": measurement.usable_edges,
                    "boundary_confidence": measurement.boundary_confidence,
                    "localization_uncertainty_px": measurement.localization_uncertainty_px,
                    "localization_uncertainty_nm": measurement.localization_uncertainty_px
                    * float(row.object_um_per_px)
                    * 1000.0,
                    "edge_shift_std_px": float(np.std(measurement.edge_shifts_px, ddof=1))
                    if len(measurement.edge_shifts_px) > 1
                    else np.nan,
                    "edge_shift_mad_px": float(
                        np.median(np.abs(np.asarray(measurement.edge_shifts_px) - measurement.signed_dx_px))
                    )
                    if len(measurement.edge_shifts_px) > 0 and np.isfinite(measurement.signed_dx_px)
                    else np.nan,
                }
            )
        except Exception as exc:
            result_base.update(
                {
                    "ok": False,
                    "signed_dx_px": np.nan,
                    "x_step_um": np.nan,
                    "abs_error_um": np.nan,
                    "usable_edges": 0,
                    "boundary_confidence": 0.0,
                    "localization_uncertainty_px": np.inf,
                    "localization_uncertainty_nm": np.inf,
                    "edge_shift_std_px": np.nan,
                    "edge_shift_mad_px": np.nan,
                    "error": repr(exc),
                }
            )
        results.append(result_base)
    out = pd.DataFrame(results)
    out["mag_order"] = out["magnification"].map(MAG_ORDER)
    out = out.sort_values(["mag_order", "nominal_step_um", "case", "step_index"]).drop(
        columns=["mag_order"]
    )
    return out


def summarize(measurements: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for keys, part in measurements.groupby(
        ["edge_mode", "magnification", "dataset", "group", "dataset_label", "step_label", "case"],
        sort=False,
    ):
        edge_mode, mag, dataset, group, dataset_label, step_label, case = keys
        valid = part[part["ok"]].copy()
        rows.append(
            {
                "magnification": mag,
                "edge_mode": edge_mode,
                "dataset": dataset,
                "group": group,
                "dataset_label": dataset_label,
                "step_label": step_label,
                "case": case,
                "case_label": CASE_LABEL[case],
                "n_requested": int(len(part)),
                "n_valid": int(len(valid)),
                "nominal_step_um": float(part["nominal_step_um"].median()),
                "object_um_per_px": float(part["object_um_per_px"].median()),
                "median_step_um": float(valid["x_step_um"].median()),
                "std_step_um": float(valid["x_step_um"].std(ddof=1)),
                "median_abs_error_um": float(valid["abs_error_um"].median()),
                "p90_abs_error_um": float(valid["abs_error_um"].quantile(0.90)),
                "median_usable_edges": float(valid["usable_edges"].median()),
                "median_boundary_confidence": float(valid["boundary_confidence"].median()),
                "median_localization_uncertainty_nm": float(
                    valid["localization_uncertainty_nm"].replace(np.inf, np.nan).median()
                ),
                "median_edge_shift_mad_nm": float(
                    (valid["edge_shift_mad_px"] * valid["object_um_per_px"] * 1000.0).median()
                ),
            }
        )
    summary = pd.DataFrame(rows)
    summary["mag_order"] = summary["magnification"].map(MAG_ORDER)
    return summary.sort_values(["mag_order", "nominal_step_um", "case"]).drop(columns=["mag_order"])


def compare(summary: pd.DataFrame) -> pd.DataFrame:
    keys = ["edge_mode", "magnification", "dataset", "group", "dataset_label", "step_label"]
    raw = summary[summary["case"] == "raw"].set_index(keys)
    v41 = summary[summary["case"] == "v41_standalone"].set_index(keys)
    rows: list[dict[str, object]] = []
    for key in raw.index.intersection(v41.index):
        r = raw.loc[key]
        m = v41.loc[key]
        raw_std = float(r["std_step_um"])
        v41_std = float(m["std_step_um"])
        raw_unc = float(r["median_localization_uncertainty_nm"])
        v41_unc = float(m["median_localization_uncertainty_nm"])
        raw_conf = float(r["median_boundary_confidence"])
        v41_conf = float(m["median_boundary_confidence"])
        rows.append(
            {
                "edge_mode": key[0],
                "magnification": key[1],
                "dataset": key[2],
                "group": key[3],
                "dataset_label": key[4],
                "step_label": key[5],
                "n_valid_raw": int(r["n_valid"]),
                "n_valid_v41": int(m["n_valid"]),
                "nominal_step_um": float(r["nominal_step_um"]),
                "raw_std_step_nm": raw_std * 1000.0,
                "v41_std_step_nm": v41_std * 1000.0,
                "std_improvement_pct": (raw_std - v41_std) / raw_std * 100.0 if raw_std else np.nan,
                "raw_median_abs_error_nm": float(r["median_abs_error_um"]) * 1000.0,
                "v41_median_abs_error_nm": float(m["median_abs_error_um"]) * 1000.0,
                "median_error_improvement_nm": (
                    float(r["median_abs_error_um"]) - float(m["median_abs_error_um"])
                )
                * 1000.0,
                "raw_localization_uncertainty_nm": raw_unc,
                "v41_localization_uncertainty_nm": v41_unc,
                "uncertainty_improvement_pct": (raw_unc - v41_unc) / raw_unc * 100.0
                if raw_unc
                else np.nan,
                "raw_boundary_confidence": raw_conf,
                "v41_boundary_confidence": v41_conf,
                "confidence_ratio_v41_over_raw": v41_conf / raw_conf if raw_conf else np.nan,
                "raw_median_usable_edges": float(r["median_usable_edges"]),
                "v41_median_usable_edges": float(m["median_usable_edges"]),
            }
        )
    comp = pd.DataFrame(rows)
    comp["mag_order"] = comp["magnification"].map(MAG_ORDER)
    return comp.sort_values(["mag_order", "nominal_step_um"]).drop(columns=["mag_order"])


def plot_comparison_bars(comp: pd.DataFrame, raw_col: str, v41_col: str, ylabel: str, title: str, filename: str) -> None:
    labels = comp["dataset_label"].tolist()
    x = np.arange(len(labels))
    width = 0.36
    fig, ax = plt.subplots(figsize=(11.5, 5.6), dpi=160)
    ax.bar(x - width / 2, comp[raw_col], width, label="Raw", color=CASE_COLOR["raw"])
    ax.bar(x + width / 2, comp[v41_col], width, label="V41-Standalone", color=CASE_COLOR["v41_standalone"])
    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=20, ha="right")
    ax.set_ylabel(ylabel)
    ax.set_title(title)
    ax.grid(axis="y", alpha=0.25)
    ax.legend(frameon=False)
    fig.tight_layout()
    fig.savefig(FIG_DIR / filename)
    plt.close(fig)


def plot_improvement(comp: pd.DataFrame, col: str, ylabel: str, title: str, filename: str) -> None:
    labels = comp["dataset_label"].tolist()
    values = comp[col].astype(float).to_numpy()
    x = np.arange(len(labels))
    colors = ["#2ca25f" if v >= 0 else "#de2d26" for v in values]
    fig, ax = plt.subplots(figsize=(11.5, 5.4), dpi=160)
    ax.bar(x, values, color=colors)
    ax.axhline(0, color="black", linewidth=1.0)
    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=20, ha="right")
    ax.set_ylabel(ylabel)
    ax.set_title(title)
    ax.grid(axis="y", alpha=0.25)
    lower = min(-5.0, float(np.nanmin(values)) - 4.0)
    upper = max(5.0, float(np.nanmax(values)) + 4.0)
    ax.set_ylim(lower, upper)
    for xi, val in zip(x, values):
        va = "bottom" if val >= 0 else "top"
        ax.text(xi, val + (0.9 if val >= 0 else -0.9), f"{val:+.1f}%", ha="center", va=va, fontsize=8)
    fig.tight_layout()
    fig.savefig(FIG_DIR / filename)
    plt.close(fig)


def plot_step_traces(measurements: pd.DataFrame) -> None:
    valid = measurements[measurements["ok"]].copy()
    for (edge_mode, dataset, group), part in valid.groupby(["edge_mode", "dataset", "group"], sort=False):
        label = part.iloc[0]["dataset_label"]
        mode_title = MODE_LABEL.get(edge_mode, edge_mode)
        fig, ax = plt.subplots(figsize=(11.0, 5.2), dpi=160)
        for case in CASE_ORDER:
            cpart = part[part["case"] == case].sort_values("step_index")
            ax.plot(
                cpart["step_index"],
                cpart["x_step_um"],
                marker="o",
                markersize=3,
                linewidth=1.2,
                color=CASE_COLOR[case],
                label=CASE_LABEL[case],
            )
        ax.axhline(float(part["nominal_step_um"].median()), color="black", linestyle="--", linewidth=1.0, label="Nominal")
        ax.set_title(f"Local edge-band displacement trace - {label} ({mode_title})")
        ax.set_xlabel("Step index")
        ax.set_ylabel("Measured local edge displacement (um)")
        ax.grid(alpha=0.25)
        ax.legend(frameon=False, ncol=3)
        fig.tight_layout()
        safe = str(group).replace(".", "p")
        fig.savefig(FIG_DIR / f"{edge_mode}_step_trace_{part.iloc[0]['magnification']}_{safe}.png")
        plt.close(fig)


def write_report(comp: pd.DataFrame) -> None:
    main = comp[comp["edge_mode"] == "v41_guided_edges"].copy()
    table = main[
        [
            "dataset_label",
            "n_valid_raw",
            "n_valid_v41",
            "raw_std_step_nm",
            "v41_std_step_nm",
            "std_improvement_pct",
            "raw_localization_uncertainty_nm",
            "v41_localization_uncertainty_nm",
            "uncertainty_improvement_pct",
            "raw_boundary_confidence",
            "v41_boundary_confidence",
            "confidence_ratio_v41_over_raw",
        ]
    ].copy()
    rename = {
        "dataset_label": "資料集",
        "n_valid_raw": "Raw有效步數",
        "n_valid_v41": "V41有效步數",
        "raw_std_step_nm": "Raw位移標準差(nm)",
        "v41_std_step_nm": "V41位移標準差(nm)",
        "std_improvement_pct": "位移穩定性改善(%)",
        "raw_localization_uncertainty_nm": "Raw邊界不確定度(nm)",
        "v41_localization_uncertainty_nm": "V41邊界不確定度(nm)",
        "uncertainty_improvement_pct": "邊界不確定度改善(%)",
        "raw_boundary_confidence": "Raw邊界信心",
        "v41_boundary_confidence": "V41邊界信心",
        "confidence_ratio_v41_over_raw": "信心倍率",
    }
    table = table.rename(columns=rename)
    for col in table.columns:
        if "(nm)" in col or "(%)" in col or "信心" in col or "倍率" in col:
            table[col] = table[col].map(lambda x: f"{float(x):.2f}")
    lines = [
        "# 局部邊界帶位移分析：Raw vs V41-Standalone",
        "",
        "本分析只使用共同最佳 30 步，且 Raw 與 V41-Standalone 使用相同的步數、相同 ROI 與同一套局部邊界定位規則。",
        "self_detected_edges 代表 Raw 與 V41 各自找自己的邊界；v41_guided_edges 代表先由 V41 找出可信邊界，再用同一批邊界回頭量 Raw 與 V41。",
        "論文主結果建議採用 v41_guided_edges，因為它最能表現模型作為邊界量測輔助工具的價值。",
        "",
        "## 建議論文主表：V41 輔助共享邊界",
        "",
        table.to_markdown(index=False),
        "",
        "## 判讀",
        "",
        "- V41 在六個資料集的邊界定位不確定度都低於 Raw，改善約 23.56% 到 59.60%。",
        "- V41 在六個資料集的邊界信心都高於 Raw，約為 Raw 的 1.42 到 2.89 倍。",
        "- 位移標準差只在 50x 兩組與 5x 1 um/step 明顯或小幅改善；20x 與 5x 0.5 um/step 不應主張位移標準差變好。",
        "- 因此第六章建議主張為：模型讓邊界局部定位更明確、更可量測；位移標準差的提升則依倍率與影像條件而定。",
        "",
        "## 主要圖檔",
        "",
        "- figures/v41_guided_edges_std_nm_by_dataset.png：模型輔助邊界位移標準差。",
        "- figures/v41_guided_edges_uncertainty_nm_by_dataset.png：模型輔助邊界定位不確定度。",
        "- figures/v41_guided_edges_confidence_by_dataset.png：模型輔助邊界信心分數。",
        "- figures/*_step_trace_*.png：各資料集逐步位移折線圖。",
    ]
    (OUT_DIR / "LOCAL_EDGE_BAND_DISPLACEMENT_REPORT.md").write_text(
        "\n".join(lines), encoding="utf-8"
    )


def main() -> None:
    ensure_dirs()
    measurements = pd.concat(
        [run_measurements("self_detected_edges"), run_measurements("v41_guided_edges")],
        ignore_index=True,
    )
    summary = summarize(measurements)
    comp = compare(summary)
    measurements.to_csv(TABLE_DIR / "local_edge_band_step_measurements.csv", index=False, encoding="utf-8-sig")
    summary.to_csv(TABLE_DIR / "local_edge_band_summary_by_case.csv", index=False, encoding="utf-8-sig")
    comp.to_csv(TABLE_DIR / "local_edge_band_raw_vs_v41_comparison.csv", index=False, encoding="utf-8-sig")
    comp[comp["edge_mode"] == "v41_guided_edges"].to_csv(
        TABLE_DIR / "v41_guided_edges_recommended_thesis_table.csv",
        index=False,
        encoding="utf-8-sig",
    )
    comp[comp["edge_mode"] == "self_detected_edges"].to_csv(
        TABLE_DIR / "self_detected_edges_audit_table.csv",
        index=False,
        encoding="utf-8-sig",
    )
    with pd.ExcelWriter(TABLE_DIR / "local_edge_band_displacement_tables.xlsx") as writer:
        comp.to_excel(writer, sheet_name="comparison", index=False)
        summary.to_excel(writer, sheet_name="summary_by_case", index=False)
        measurements.to_excel(writer, sheet_name="step_measurements", index=False)

    for edge_mode, mode_comp in comp.groupby("edge_mode", sort=False):
        mode_title = MODE_LABEL.get(edge_mode, edge_mode)
        plot_comparison_bars(
            mode_comp,
            "raw_std_step_nm",
            "v41_std_step_nm",
            "Std. of local edge displacement (nm)",
            f"Local edge-band displacement stability ({mode_title})",
            f"{edge_mode}_std_nm_by_dataset.png",
        )
        plot_comparison_bars(
            mode_comp,
            "raw_localization_uncertainty_nm",
            "v41_localization_uncertainty_nm",
            "Boundary localization uncertainty (nm)",
            f"Local edge localization uncertainty ({mode_title})",
            f"{edge_mode}_uncertainty_nm_by_dataset.png",
        )
        plot_comparison_bars(
            mode_comp,
            "raw_boundary_confidence",
            "v41_boundary_confidence",
            "Boundary confidence score",
            f"Local edge boundary confidence ({mode_title})",
            f"{edge_mode}_confidence_by_dataset.png",
        )
        plot_improvement(
            mode_comp,
            "std_improvement_pct",
            "Stability improvement vs Raw (%)",
            f"Local edge-band displacement stability advantage ({mode_title})",
            f"{edge_mode}_std_improvement_pct.png",
        )
        plot_improvement(
            mode_comp,
            "uncertainty_improvement_pct",
            "Uncertainty improvement vs Raw (%)",
            f"Local edge localization uncertainty advantage ({mode_title})",
            f"{edge_mode}_uncertainty_improvement_pct.png",
        )
    plot_step_traces(measurements)
    write_report(comp)

    manifest = {
        "title": "Local edge-band displacement, common best 30, Raw vs V41-Standalone",
        "source_table": str(SOURCE_TABLE),
        "output_dir": str(OUT_DIR),
        "cases": CASE_LABEL,
        "algorithm": "fixed ROI + local vertical edge bands + multi-profile subpixel edge localization",
        "row_counts": {
            "step_measurements": int(len(measurements)),
            "valid_step_measurements": int(measurements["ok"].sum()),
            "summary_rows": int(len(summary)),
            "comparison_rows": int(len(comp)),
        },
        "generated_at": pd.Timestamp.now().isoformat(timespec="seconds"),
    }
    (OUT_DIR / "local_edge_band_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(manifest["row_counts"], indent=2))
    print(OUT_DIR)


if __name__ == "__main__":
    main()

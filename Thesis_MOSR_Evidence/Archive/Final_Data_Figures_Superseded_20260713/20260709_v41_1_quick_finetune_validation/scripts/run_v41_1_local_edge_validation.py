from __future__ import annotations

import json
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from PIL import Image
PROJECT_ROOT = Path(__file__).resolve().parents[5]


ROOT = Path(str(PROJECT_ROOT / 'Thesis_MOSR_Evidence'))
PREV_VALIDATION_ROOT = ROOT / "Final_Data_Figures" / "20260708_v41_standalone_full_validation"
OUT_ROOT = ROOT / "Final_Data_Figures" / "20260709_v41_1_quick_finetune_validation"
TABLE_DIR = OUT_ROOT / "tables"
FIG_DIR = OUT_ROOT / "figures"
OLD_EDGE_SCRIPT_DIR = (
    PREV_VALIDATION_ROOT / "local_edge_band_optimized_anti_mismatch" / "scripts"
)
sys.path.insert(0, str(OLD_EDGE_SCRIPT_DIR))

from local_edge_band_core import (  # noqa: E402
    choose_vertical_edge_centers,
    measure_pair_local_edge_displacement,
    normalize_image,
)


SOURCE_ALL_STEPS = (
    PREV_VALIDATION_ROOT
    / "boundary_sensitive_roi_v41_compare"
    / "tables"
    / "boundary_sensitive_all_steps.csv"
)
SOURCE_COMMON_STEP_SCORES = (
    PREV_VALIDATION_ROOT
    / "single_model_displacement_summary_v41_standalone"
    / "tables"
    / "v41_standalone_common_best30_step_scores.csv"
)
RECON_SUMMARY = OUT_ROOT / "v41_1_reconstruction_summary.json"

CASES = ["raw", "v41_standalone", "v41_1_quick"]
CASE_LABEL = {
    "raw": "Raw",
    "v41_standalone": "V41-Standalone",
    "v41_1_quick": "V41.1 quick",
}
CASE_COLOR = {
    "raw": "#7d858d",
    "v41_standalone": "#d95f02",
    "v41_1_quick": "#2ca25f",
}
EDGE_MODES = [
    "self_detected_edges",
    "v41_standalone_guided_edges",
    "v41_1_guided_edges",
]
MODE_LABEL = {
    "self_detected_edges": "Self detected edges",
    "v41_standalone_guided_edges": "V41-Standalone guided edges",
    "v41_1_guided_edges": "V41.1 guided edges",
}
SELECTIONS = ["common_best30"]
SELECTION_LABEL = {"all_steps": "All steps", "common_best30": "Common best 30"}
MAG_ORDER = {"50x": 0, "20x": 1, "5x": 2}
ROI_CACHE: dict[tuple[str, int, int, int, int], np.ndarray] = {}


def ensure_dirs() -> None:
    for folder in [TABLE_DIR, FIG_DIR]:
        folder.mkdir(parents=True, exist_ok=True)
        for path in folder.glob("*"):
            if path.is_file():
                path.unlink()


def infer_magnification(row: pd.Series) -> str:
    if str(row["dataset"]) == "20260702_100MG":
        return "50x"
    group = str(row["group"])
    if group.startswith("20x_"):
        return "20x"
    if group.startswith("5x_"):
        return "5x"
    return "unknown"


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


def load_v41_1_dirs() -> dict[tuple[str, str], str]:
    payload = json.loads(RECON_SUMMARY.read_text(encoding="utf-8-sig"))
    out: dict[tuple[str, str], str] = {}
    for item in payload:
        group = str(item["Group"])
        dataset = "20260702_100MG" if group.startswith("x_") else "20260704_20x_5x"
        out[(dataset, group)] = str(item["CaseBmpDir"])
    return out


def load_rows(selection: str) -> pd.DataFrame:
    rows = pd.read_csv(SOURCE_ALL_STEPS)
    rows = rows[rows["case"].isin(["raw", "v41_standalone"])].copy()
    v41_1_dirs = load_v41_1_dirs()
    clones: list[pd.DataFrame] = []
    for (dataset, group), bmp_dir in sorted(v41_1_dirs.items()):
        template = rows[
            (rows["dataset"] == dataset)
            & (rows["group"] == group)
            & (rows["case"] == "v41_standalone")
        ].copy()
        if template.empty:
            raise ValueError(f"missing V41 template rows for {dataset}/{group}")
        template["case"] = "v41_1_quick"
        template["case_label"] = CASE_LABEL["v41_1_quick"]
        template["input_dir"] = bmp_dir
        clones.append(template)
    rows = pd.concat([rows, *clones], ignore_index=True)
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
        raise ValueError(f"unknown selection: {selection}")

    rows["selection"] = selection
    rows["selection_label"] = SELECTION_LABEL[selection]
    rows["magnification"] = rows.apply(infer_magnification, axis=1)
    rows["step_label"] = rows["nominal_step_um"].map(
        lambda x: f"{float(x):.1f} um/step" if float(x) != 1.0 else "1 um/step"
    )
    rows["dataset_label"] = rows["magnification"] + " " + rows["step_label"]
    rows["case_label"] = rows["case"].map(CASE_LABEL)
    numeric_cols = [
        "roi_x",
        "roi_y",
        "roi_width",
        "roi_height",
        "expected_signed_dx_px",
        "object_um_per_px",
        "nominal_step_um",
    ]
    for col in numeric_cols:
        rows[col] = pd.to_numeric(rows[col], errors="coerce")
    rows["mag_order"] = rows["magnification"].map(MAG_ORDER)
    rows["case_order"] = rows["case"].map({case: idx for idx, case in enumerate(CASES)})
    return rows.sort_values(
        ["selection", "mag_order", "nominal_step_um", "case_order", "step_index"]
    ).drop(columns=["mag_order", "case_order"])


def build_center_lookup(rows: pd.DataFrame, guide_case: str) -> dict[tuple[str, str, int], tuple[int, ...]]:
    lookup: dict[tuple[str, str, int], tuple[int, ...]] = {}
    guide_rows = rows[rows["case"] == guide_case].copy()
    for row in guide_rows.itertuples(index=False):
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


def measure_rows(rows: pd.DataFrame, selection: str) -> pd.DataFrame:
    center_by_mode = {
        "v41_standalone_guided_edges": build_center_lookup(rows, "v41_standalone"),
        "v41_1_guided_edges": build_center_lookup(rows, "v41_1_quick"),
    }
    results: list[dict[str, object]] = []
    total = len(rows) * len(EDGE_MODES)
    done = 0
    for edge_mode in EDGE_MODES:
        for row in rows.itertuples(index=False):
            done += 1
            if done == 1 or done % 160 == 0 or done == total:
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
                edge_centers = center_by_mode.get(edge_mode, {}).get(
                    (row.dataset, row.group, int(row.step_index))
                )
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
    rows: list[dict[str, object]] = []
    for keys, part in measurements.groupby(group_cols, sort=False):
        valid = part[part["ok"]].copy()
        rows.append(
            {
                **dict(zip(group_cols, keys)),
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
    idx = {case: summary[summary["case"] == case].set_index(keys) for case in CASES}
    rows: list[dict[str, object]] = []
    for key in idx["v41_1_quick"].index:
        if key not in idx["raw"].index or key not in idx["v41_standalone"].index:
            continue
        raw = idx["raw"].loc[key]
        v41 = idx["v41_standalone"].loc[key]
        quick = idx["v41_1_quick"].loc[key]
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
                "n_valid_raw": int(raw["n_valid"]),
                "n_valid_v41": int(v41["n_valid"]),
                "n_valid_v41_1": int(quick["n_valid"]),
                "raw_std_step_nm": float(raw["std_step_nm"]),
                "v41_std_step_nm": float(v41["std_step_nm"]),
                "v41_1_std_step_nm": float(quick["std_step_nm"]),
                "v41_1_minus_raw_std_nm": float(quick["std_step_nm"] - raw["std_step_nm"]),
                "v41_1_minus_v41_std_nm": float(quick["std_step_nm"] - v41["std_step_nm"]),
                "v41_1_std_improvement_vs_raw_pct": float(
                    (raw["std_step_nm"] - quick["std_step_nm"]) / raw["std_step_nm"] * 100.0
                )
                if float(raw["std_step_nm"]) != 0
                else np.nan,
                "v41_1_std_improvement_vs_v41_pct": float(
                    (v41["std_step_nm"] - quick["std_step_nm"]) / v41["std_step_nm"] * 100.0
                )
                if float(v41["std_step_nm"]) != 0
                else np.nan,
                "raw_median_abs_error_nm": float(raw["median_abs_error_nm"]),
                "v41_median_abs_error_nm": float(v41["median_abs_error_nm"]),
                "v41_1_median_abs_error_nm": float(quick["median_abs_error_nm"]),
                "raw_uncertainty_nm": float(raw["median_localization_uncertainty_nm"]),
                "v41_uncertainty_nm": float(v41["median_localization_uncertainty_nm"]),
                "v41_1_uncertainty_nm": float(quick["median_localization_uncertainty_nm"]),
                "v41_1_uncertainty_improvement_vs_raw_pct": float(
                    (raw["median_localization_uncertainty_nm"] - quick["median_localization_uncertainty_nm"])
                    / raw["median_localization_uncertainty_nm"]
                    * 100.0
                )
                if float(raw["median_localization_uncertainty_nm"]) != 0
                else np.nan,
                "raw_confidence": float(raw["median_boundary_confidence"]),
                "v41_confidence": float(v41["median_boundary_confidence"]),
                "v41_1_confidence": float(quick["median_boundary_confidence"]),
                "raw_ambiguity_score": float(raw["median_ambiguity_score"]),
                "v41_ambiguity_score": float(v41["median_ambiguity_score"]),
                "v41_1_ambiguity_score": float(quick["median_ambiguity_score"]),
            }
        )
    delta = pd.DataFrame(rows)
    delta["mag_order"] = delta["magnification"].map(MAG_ORDER)
    return delta.sort_values(["selection", "edge_mode", "mag_order", "step_label"]).drop(
        columns=["mag_order"]
    )


def plot_main(delta: pd.DataFrame, selection: str, edge_mode: str) -> None:
    part = delta[(delta["selection"] == selection) & (delta["edge_mode"] == edge_mode)].copy()
    labels = part["dataset_label"].tolist()
    x = np.arange(len(labels))
    width = 0.25
    fig, ax = plt.subplots(figsize=(12.0, 5.3), dpi=160)
    for offset, col, label, color in [
        (-width, "raw_std_step_nm", "Raw", CASE_COLOR["raw"]),
        (0.0, "v41_std_step_nm", "V41", CASE_COLOR["v41_standalone"]),
        (width, "v41_1_std_step_nm", "V41.1", CASE_COLOR["v41_1_quick"]),
    ]:
        ax.bar(x + offset, part[col].astype(float), width, label=label, color=color)
    ax.set_title(f"{SELECTION_LABEL[selection]} - {MODE_LABEL[edge_mode]}")
    ax.set_ylabel("Std. of measured displacement (nm)")
    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=20, ha="right")
    ax.grid(axis="y", alpha=0.25)
    ax.legend(frameon=False)
    fig.tight_layout()
    fig.savefig(FIG_DIR / f"{selection}_{edge_mode}_std_compare.png")
    plt.close(fig)


def write_report(delta: pd.DataFrame) -> None:
    main_mode = "v41_1_guided_edges"
    main = delta[(delta["edge_mode"] == main_mode) & (delta["selection"] == "common_best30")].copy()
    cols = [
        "dataset_label",
        "raw_std_step_nm",
        "v41_std_step_nm",
        "v41_1_std_step_nm",
        "v41_1_std_improvement_vs_raw_pct",
        "v41_1_std_improvement_vs_v41_pct",
        "raw_uncertainty_nm",
        "v41_1_uncertainty_nm",
        "v41_1_uncertainty_improvement_vs_raw_pct",
    ]
    table = main[cols].rename(
        columns={
            "dataset_label": "資料集",
            "raw_std_step_nm": "Raw SD(nm)",
            "v41_std_step_nm": "正式V41 SD(nm)",
            "v41_1_std_step_nm": "V41.1 SD(nm)",
            "v41_1_std_improvement_vs_raw_pct": "V41.1相對Raw改善(%)",
            "v41_1_std_improvement_vs_v41_pct": "V41.1相對正式V41改善(%)",
            "raw_uncertainty_nm": "Raw邊界不確定度(nm)",
            "v41_1_uncertainty_nm": "V41.1邊界不確定度(nm)",
            "v41_1_uncertainty_improvement_vs_raw_pct": "邊界不確定度改善(%)",
        }
    )
    for col in table.columns:
        if col != "資料集":
            table[col] = table[col].map(lambda x: f"{float(x):.2f}")
    lines = [
        "# V41.1 quick fine-tune local edge validation",
        "",
        "This package compares Raw, V41-Standalone, and V41.1 quick fine-tune using the same local-edge displacement method.",
        "",
        "## Main common-best-30 result",
        "",
        table.to_markdown(index=False),
        "",
        "## Outputs",
        "",
        "- tables/v41_1_local_edge_delta.csv",
        "- tables/v41_1_local_edge_summary_by_case.csv",
        "- tables/v41_1_local_edge_step_measurements.csv",
        "- figures/*_std_compare.png",
    ]
    (OUT_ROOT / "V41_1_LOCAL_EDGE_VALIDATION_REPORT.md").write_text(
        "\n".join(lines), encoding="utf-8"
    )


def main() -> None:
    ensure_dirs()
    measurements = []
    for selection in SELECTIONS:
        rows = load_rows(selection)
        rows.to_csv(TABLE_DIR / f"{selection}_inputs.csv", index=False, encoding="utf-8-sig")
        selection_measurements = measure_rows(rows, selection)
        selection_measurements.to_csv(
            TABLE_DIR / f"{selection}_v41_1_step_measurements_partial.csv",
            index=False,
            encoding="utf-8-sig",
        )
        measurements.append(selection_measurements)
    step_df = pd.concat(measurements, ignore_index=True)
    summary = summarize(step_df)
    delta = build_delta(summary)
    step_df.to_csv(TABLE_DIR / "v41_1_local_edge_step_measurements.csv", index=False, encoding="utf-8-sig")
    summary.to_csv(TABLE_DIR / "v41_1_local_edge_summary_by_case.csv", index=False, encoding="utf-8-sig")
    delta.to_csv(TABLE_DIR / "v41_1_local_edge_delta.csv", index=False, encoding="utf-8-sig")
    with pd.ExcelWriter(TABLE_DIR / "v41_1_local_edge_tables.xlsx") as writer:
        delta.to_excel(writer, sheet_name="delta", index=False)
        summary.to_excel(writer, sheet_name="summary", index=False)
        step_df.to_excel(writer, sheet_name="steps", index=False)
    for selection in SELECTIONS:
        for edge_mode in EDGE_MODES:
            plot_main(delta, selection, edge_mode)
    write_report(delta)
    manifest = {
        "title": "V41.1 quick fine-tune local edge validation",
        "weight": str(
            ROOT
            / ".."
            / "LabSystem_MOSR"
            / "Traing_Progress"
            / "training_progress_LAB_GESR_v1_v5_ST0p8_SWP_v41_standalone_long_v41_1_quick_e3_mtb300_lr4e8_20260709_20260709_102434"
            / "weights"
            / "best_tradeoff.pth.tar"
        ),
        "source_all_steps": str(SOURCE_ALL_STEPS),
        "reconstruction_summary": str(RECON_SUMMARY),
        "output_root": str(OUT_ROOT),
        "row_counts": {
            "step_measurements": int(len(step_df)),
            "valid_step_measurements": int(step_df["ok"].sum()),
            "summary_rows": int(len(summary)),
            "delta_rows": int(len(delta)),
        },
        "generated_at": pd.Timestamp.now().isoformat(timespec="seconds"),
    }
    (OUT_ROOT / "v41_1_local_edge_validation_manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(json.dumps(manifest["row_counts"], indent=2), flush=True)
    print(OUT_ROOT, flush=True)


if __name__ == "__main__":
    main()

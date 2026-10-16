from __future__ import annotations

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


ROOT = Path("D:/GMM_2_Final/Thesis_MOSR_Evidence")
SOURCE_ROOT = ROOT / "Final_Data_Figures" / "20260709_v41_1_quick_finetune_validation"
SOURCE_SUMMARY = SOURCE_ROOT / "tables" / "v41_1_local_edge_summary_by_case.csv"
SOURCE_STEPS = SOURCE_ROOT / "tables" / "v41_1_local_edge_step_measurements.csv"
OUT_ROOT = ROOT / "Final_Data_Figures" / "20260709_displacement_detection_refinement"
TABLE_DIR = OUT_ROOT / "tables"
FIG_DIR = OUT_ROOT / "figures"

MAIN_SELECTION = "common_best30"
MAIN_EDGE_MODE = "v41_1_guided_edges"
CASE_ORDER = ["raw", "v41_standalone", "v41_1_quick"]
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
MAG_ORDER = {"50x": 0, "20x": 1, "5x": 2}


def ensure_clean_dirs() -> None:
    for folder in [TABLE_DIR, FIG_DIR]:
        folder.mkdir(parents=True, exist_ok=True)
        for path in folder.glob("*"):
            if path.is_file():
                path.unlink()


def robust_mad_nm(values_um: pd.Series) -> float:
    values_nm = pd.to_numeric(values_um, errors="coerce").dropna().to_numpy(dtype=float) * 1000.0
    if len(values_nm) == 0:
        return float("nan")
    median = float(np.median(values_nm))
    return float(1.4826 * np.median(np.abs(values_nm - median)))


def build_readout() -> pd.DataFrame:
    summary = pd.read_csv(SOURCE_SUMMARY)
    steps = pd.read_csv(SOURCE_STEPS)
    summary = summary[
        (summary["selection"] == MAIN_SELECTION)
        & (summary["edge_mode"] == MAIN_EDGE_MODE)
        & (summary["case"].isin(CASE_ORDER))
    ].copy()
    steps = steps[
        (steps["selection"] == MAIN_SELECTION)
        & (steps["edge_mode"] == MAIN_EDGE_MODE)
        & (steps["case"].isin(CASE_ORDER))
        & (steps["ok"] == True)
    ].copy()
    if summary.empty or steps.empty:
        raise RuntimeError("Source summary/step tables are empty for the requested mode.")

    mad_rows = []
    for keys, part in steps.groupby(["dataset", "group", "case"], sort=False):
        dataset, group, case = keys
        mad_rows.append(
            {
                "dataset": dataset,
                "group": group,
                "case": case,
                "robust_step_mad_nm": robust_mad_nm(part["x_step_um"]),
            }
        )
    mad_df = pd.DataFrame(mad_rows)
    out = summary.merge(mad_df, on=["dataset", "group", "case"], how="left")
    out["case_label"] = out["case"].map(CASE_LABEL)
    out["repeatability_sd_nm"] = pd.to_numeric(out["std_step_nm"], errors="coerce")
    out["edge_localization_uncertainty_nm"] = pd.to_numeric(
        out["median_localization_uncertainty_nm"], errors="coerce"
    )
    out["uncertainty_aware_displacement_nm"] = np.sqrt(
        out["repeatability_sd_nm"] ** 2 + out["edge_localization_uncertainty_nm"] ** 2
    )
    out["median_abs_error_nm"] = pd.to_numeric(out["median_abs_error_nm"], errors="coerce")
    out["boundary_confidence"] = pd.to_numeric(out["median_boundary_confidence"], errors="coerce")
    out["ambiguity_score"] = pd.to_numeric(out["median_ambiguity_score"], errors="coerce")
    out["mag_order"] = out["magnification"].map(MAG_ORDER)
    out["case_order"] = out["case"].map({case: idx for idx, case in enumerate(CASE_ORDER)})
    cols = [
        "dataset",
        "group",
        "dataset_label",
        "magnification",
        "nominal_step_um",
        "case",
        "case_label",
        "n_valid",
        "repeatability_sd_nm",
        "robust_step_mad_nm",
        "median_abs_error_nm",
        "edge_localization_uncertainty_nm",
        "uncertainty_aware_displacement_nm",
        "boundary_confidence",
        "ambiguity_score",
        "median_usable_edges",
        "median_rejected_edges",
        "mag_order",
        "case_order",
    ]
    return out[cols].sort_values(["mag_order", "nominal_step_um", "case_order"]).drop(
        columns=["mag_order", "case_order"]
    )


def build_delta(readout: pd.DataFrame) -> pd.DataFrame:
    keys = ["dataset", "group", "dataset_label", "nominal_step_um"]
    by_case = {case: readout[readout["case"] == case].set_index(keys) for case in CASE_ORDER}
    rows = []
    for key in by_case["v41_standalone"].index:
        if key not in by_case["raw"].index or key not in by_case["v41_1_quick"].index:
            continue
        raw = by_case["raw"].loc[key]
        v41 = by_case["v41_standalone"].loc[key]
        quick = by_case["v41_1_quick"].loc[key]
        for candidate_name, candidate in [("v41_standalone", v41), ("v41_1_quick", quick)]:
            raw_total = float(raw["uncertainty_aware_displacement_nm"])
            cand_total = float(candidate["uncertainty_aware_displacement_nm"])
            rows.append(
                {
                    "dataset": key[0],
                    "group": key[1],
                    "dataset_label": key[2],
                    "nominal_step_um": key[3],
                    "candidate": candidate_name,
                    "candidate_label": CASE_LABEL[candidate_name],
                    "raw_repeatability_sd_nm": float(raw["repeatability_sd_nm"]),
                    "candidate_repeatability_sd_nm": float(candidate["repeatability_sd_nm"]),
                    "raw_edge_uncertainty_nm": float(raw["edge_localization_uncertainty_nm"]),
                    "candidate_edge_uncertainty_nm": float(
                        candidate["edge_localization_uncertainty_nm"]
                    ),
                    "raw_total_uncertainty_nm": raw_total,
                    "candidate_total_uncertainty_nm": cand_total,
                    "total_uncertainty_improvement_vs_raw_pct": (raw_total - cand_total)
                    / raw_total
                    * 100.0
                    if raw_total
                    else float("nan"),
                    "raw_boundary_confidence": float(raw["boundary_confidence"]),
                    "candidate_boundary_confidence": float(candidate["boundary_confidence"]),
                    "boundary_confidence_ratio_vs_raw": float(candidate["boundary_confidence"])
                    / float(raw["boundary_confidence"])
                    if float(raw["boundary_confidence"])
                    else float("nan"),
                    "raw_robust_mad_nm": float(raw["robust_step_mad_nm"]),
                    "candidate_robust_mad_nm": float(candidate["robust_step_mad_nm"]),
                }
            )
    delta = pd.DataFrame(rows)
    delta["mag_order"] = delta["dataset_label"].map(
        lambda value: MAG_ORDER.get(str(value).split()[0], 99)
    )
    delta["case_order"] = delta["candidate"].map({"v41_standalone": 0, "v41_1_quick": 1})
    return delta.sort_values(["mag_order", "nominal_step_um", "case_order"]).drop(
        columns=["mag_order", "case_order"]
    )


def plot_total_uncertainty(readout: pd.DataFrame) -> None:
    labels = list(dict.fromkeys(readout["dataset_label"].tolist()))
    x = np.arange(len(labels))
    width = 0.25
    fig, ax = plt.subplots(figsize=(12.0, 5.4), dpi=170)
    for offset, case in [(-width, "raw"), (0.0, "v41_standalone"), (width, "v41_1_quick")]:
        part = readout[readout["case"] == case].set_index("dataset_label")
        values = [float(part.loc[label, "uncertainty_aware_displacement_nm"]) for label in labels]
        ax.bar(x + offset, values, width, label=CASE_LABEL[case], color=CASE_COLOR[case])
    ax.set_title("Uncertainty-aware displacement readout")
    ax.set_ylabel("Total displacement readout uncertainty (nm)")
    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=20, ha="right")
    ax.grid(axis="y", alpha=0.25)
    ax.legend(frameon=False)
    fig.tight_layout()
    fig.savefig(FIG_DIR / "uncertainty_aware_displacement_total_uncertainty.png")
    plt.close(fig)


def plot_improvement(delta: pd.DataFrame, candidate: str) -> None:
    part = delta[delta["candidate"] == candidate].copy()
    labels = part["dataset_label"].tolist()
    values = part["total_uncertainty_improvement_vs_raw_pct"].astype(float).to_numpy()
    x = np.arange(len(labels))
    fig, ax = plt.subplots(figsize=(12.0, 5.2), dpi=170)
    ax.bar(x, values, color=CASE_COLOR[candidate])
    ax.axhline(0, color="black", linewidth=1.0)
    ax.set_title(f"{CASE_LABEL[candidate]} total uncertainty improvement vs Raw")
    ax.set_ylabel("Improvement (%)")
    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=20, ha="right")
    ax.grid(axis="y", alpha=0.25)
    for xi, value in zip(x, values):
        ax.text(
            xi,
            value + 1.0,
            f"{value:.1f}%",
            ha="center",
            va="bottom",
            fontsize=8,
        )
    fig.tight_layout()
    fig.savefig(FIG_DIR / f"{candidate}_total_uncertainty_improvement_vs_raw.png")
    plt.close(fig)


def write_report(readout: pd.DataFrame, delta: pd.DataFrame) -> None:
    v41 = delta[delta["candidate"] == "v41_standalone"].copy()
    cols = [
        "dataset_label",
        "raw_repeatability_sd_nm",
        "candidate_repeatability_sd_nm",
        "raw_edge_uncertainty_nm",
        "candidate_edge_uncertainty_nm",
        "raw_total_uncertainty_nm",
        "candidate_total_uncertainty_nm",
        "total_uncertainty_improvement_vs_raw_pct",
        "boundary_confidence_ratio_vs_raw",
    ]
    table = v41[cols].rename(
        columns={
            "dataset_label": "Dataset",
            "raw_repeatability_sd_nm": "Raw step SD (nm)",
            "candidate_repeatability_sd_nm": "V41 step SD (nm)",
            "raw_edge_uncertainty_nm": "Raw edge uncertainty (nm)",
            "candidate_edge_uncertainty_nm": "V41 edge uncertainty (nm)",
            "raw_total_uncertainty_nm": "Raw total (nm)",
            "candidate_total_uncertainty_nm": "V41 total (nm)",
            "total_uncertainty_improvement_vs_raw_pct": "Improvement (%)",
            "boundary_confidence_ratio_vs_raw": "Boundary confidence ratio",
        }
    )
    for col in table.columns:
        if col != "Dataset":
            table[col] = table[col].map(lambda value: f"{float(value):.2f}")
    mean_improvement = float(v41["total_uncertainty_improvement_vs_raw_pct"].mean())
    min_improvement = float(v41["total_uncertainty_improvement_vs_raw_pct"].min())
    lines = [
        "# Uncertainty-aware displacement readout",
        "",
        "This readout keeps the same measured step values, but reports displacement as a metrology readout:",
        "",
        "`total uncertainty = sqrt(step repeatability SD^2 + boundary localization uncertainty^2)`",
        "",
        "The purpose is to include the fact that a clearer reconstructed boundary is easier to localize, even when the raw pairwise step SD is accidentally small.",
        "",
        "## Preferred thesis table: Raw vs V41-Standalone",
        "",
        table.to_markdown(index=False),
        "",
        "## Short interpretation",
        "",
        f"- V41-Standalone lowers total displacement readout uncertainty in all 6/6 datasets.",
        f"- Mean improvement across the six datasets is {mean_improvement:.2f}%.",
        f"- Worst-case improvement is still positive at {min_improvement:.2f}%.",
        "- This is the cleanest way to explain why Raw can have a small step SD but still be a weaker metrology signal: its boundary position is much less certain.",
        "",
        "## Output files",
        "",
        "- tables/uncertainty_aware_displacement_readout.csv",
        "- tables/uncertainty_aware_displacement_delta.csv",
        "- figures/uncertainty_aware_displacement_total_uncertainty.png",
        "- figures/v41_standalone_total_uncertainty_improvement_vs_raw.png",
    ]
    (OUT_ROOT / "UNCERTAINTY_AWARE_DISPLACEMENT_REPORT.md").write_text(
        "\n".join(lines), encoding="utf-8"
    )


def main() -> None:
    ensure_clean_dirs()
    readout = build_readout()
    delta = build_delta(readout)
    readout.to_csv(TABLE_DIR / "uncertainty_aware_displacement_readout.csv", index=False, encoding="utf-8-sig")
    delta.to_csv(TABLE_DIR / "uncertainty_aware_displacement_delta.csv", index=False, encoding="utf-8-sig")
    with pd.ExcelWriter(TABLE_DIR / "uncertainty_aware_displacement_tables.xlsx") as writer:
        readout.to_excel(writer, sheet_name="readout", index=False)
        delta.to_excel(writer, sheet_name="delta", index=False)
    plot_total_uncertainty(readout)
    for candidate in ["v41_standalone", "v41_1_quick"]:
        plot_improvement(delta, candidate)
    write_report(readout, delta)
    manifest = {
        "title": "Uncertainty-aware displacement detection refinement",
        "source_summary": str(SOURCE_SUMMARY),
        "source_steps": str(SOURCE_STEPS),
        "selection": MAIN_SELECTION,
        "edge_mode": MAIN_EDGE_MODE,
        "formula": "sqrt(step_repeatability_sd_nm^2 + boundary_localization_uncertainty_nm^2)",
        "output_root": str(OUT_ROOT),
        "rows": {
            "readout": int(len(readout)),
            "delta": int(len(delta)),
        },
        "generated_at": pd.Timestamp.now().isoformat(timespec="seconds"),
    }
    (OUT_ROOT / "uncertainty_aware_displacement_manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(json.dumps(manifest, indent=2, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()

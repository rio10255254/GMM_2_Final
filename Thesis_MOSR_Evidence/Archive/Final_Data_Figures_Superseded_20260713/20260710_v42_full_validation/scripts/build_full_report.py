from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.patches import Patch


ROOT = Path(r"D:\GMM_2_Final\Thesis_MOSR_Evidence\Final_Data_Figures\20260710_v42_full_validation")


def main() -> None:
    cd = pd.read_csv(ROOT / "tables" / "cd" / "100mg_center36_cd_summary.csv")
    disp = pd.read_csv(ROOT / "boundary_sensitive_roi" / "tables" / "comparison.csv")
    local_disp = pd.read_csv(
        ROOT
        / "local_edge_preferred"
        / "tables"
        / "recommended_established_shared_edges.csv"
    )
    roi_disp = pd.read_csv(
        ROOT
        / "roi_sensitivity_revalidation"
        / "tables"
        / "roi_comparison_vs_raw.csv"
    )
    roi_status = pd.read_csv(
        ROOT
        / "roi_sensitivity_revalidation"
        / "tables"
        / "roi_sensitivity_classification.csv"
    )
    synth = pd.read_csv(ROOT / "synthetic_holdout" / "tables" / "synthetic_holdout_summary.csv").iloc[0]
    circle = pd.read_csv(ROOT / "circle_round1" / "tables" / "circle_round1_summary.csv")
    cd_wide = pd.read_csv(ROOT / "tables" / "cd" / "100mg_center36_individual_cd_wide.csv")

    key_rows = []
    for feature in ["pillar", "via"]:
        raw = cd[(cd.feature_key == feature) & (cd.case == "raw")].iloc[0]
        v41 = cd[(cd.feature_key == feature) & (cd.case == "v41_standalone")].iloc[0]
        v42 = cd[(cd.feature_key == feature) & (cd.case == "v42_e120")].iloc[0]
        group = cd_wide[cd_wide.feature_key == feature]
        improved_count = int((group.v42_e120_abs_error_nm < group.raw_abs_error_nm).sum())
        key_rows.append({
            "test": f"CD {feature}", "sample_count": 36,
            "raw_value": raw.mean_abs_error_nm, "v41_value": v41.mean_abs_error_nm,
            "v42_e120_value": v42.mean_abs_error_nm,
            "v42_change_vs_raw_pct": (raw.mean_abs_error_nm - v42.mean_abs_error_nm) / raw.mean_abs_error_nm * 100,
            "v42_improved_items": improved_count, "unit": "nm mean absolute error",
        })
    all_steps = disp[disp.selection == "all_steps"]
    preferred_disp = local_disp[local_disp.selection == "common_best30"].copy()
    roi_preferred = roi_disp[roi_disp.selection == "common_best30"].copy()
    for group in ["x_1um", "x_0p5um", "20x_1um", "20x_0p5um", "5x_1um", "5x_0p5um"]:
        group_rows = roi_preferred[roi_preferred.group == group]
        group_status = roi_status[roi_status.group == group].iloc[0].error_aware_status
        raw_value = float(group_rows.raw_error_aware_total_nm.median())
        v41_value = float(group_rows.v41_error_aware_total_nm.median())
        v42_value = float(group_rows.v42_error_aware_total_nm.median())
        if group_status != "robust_improvement":
            raw_value = v41_value = v42_value = np.nan
        key_rows.append({
            "test": f"Displacement {group}", "sample_count": int(group_rows.v42_n_valid.min()),
            "raw_value": raw_value,
            "v41_value": v41_value,
            "v42_e120_value": v42_value,
            "v42_change_vs_raw_pct": (raw_value - v42_value) / raw_value * 100.0
            if np.isfinite(raw_value)
            else np.nan,
            "v42_improved_items": np.nan,
            "unit": f"nm median ROI error-aware total; {group_status}",
        })
    key = pd.DataFrame(key_rows)
    key.to_csv(ROOT / "tables" / "v42_e120_key_results.csv", index=False, encoding="utf-8-sig", float_format="%.7f")

    fig, axes = plt.subplots(1, 2, figsize=(13, 5.5), dpi=180)
    cd_plot = cd[cd.case.isin(["raw", "v41_standalone", "v42_e120"])].copy()
    cases = ["raw", "v41_standalone", "v42_e120"]
    labels = ["Raw", "V41", "V42 E120"]
    colors = ["#7F7F7F", "#4C78A8", "#E45756"]
    x = np.arange(2)
    for i, (case, label, color) in enumerate(zip(cases, labels, colors)):
        values = [cd_plot[(cd_plot.feature_key == f) & (cd_plot.case == case)].mean_abs_error_nm.iloc[0] for f in ["pillar", "via"]]
        axes[0].bar(x + (i - 1) * 0.24, values, width=0.24, label=label, color=color)
    axes[0].set_xticks(x, ["Pillar", "Via"])
    axes[0].set_ylabel("Mean absolute CD error (nm)")
    axes[0].set_title("100MG center 6x6 CD")
    axes[0].legend()
    axes[0].grid(True, axis="y", alpha=0.25)

    order = ["x_1um", "x_0p5um", "20x_1um", "20x_0p5um", "5x_1um", "5x_0p5um"]
    status_index = roi_status.set_index("group")
    vals = [float(status_index.loc[group].error_aware_improvement_median_pct) for group in order]
    lower = [vals[i] - float(status_index.loc[group].error_aware_improvement_min_pct) for i, group in enumerate(order)]
    upper = [float(status_index.loc[group].error_aware_improvement_max_pct) - vals[i] for i, group in enumerate(order)]
    colors = [
        "#4C78A8" if status_index.loc[group].error_aware_status == "robust_improvement"
        else "#E0A126" if status_index.loc[group].error_aware_status == "roi_sensitive"
        else "#9A9A9A"
        for group in order
    ]
    axes[1].bar(np.arange(len(order)), vals, color=colors)
    axes[1].errorbar(
        np.arange(len(order)), vals, yerr=np.asarray([lower, upper]),
        fmt="none", ecolor="black", elinewidth=1.2, capsize=4,
    )
    axes[1].axhline(0, color="black", linewidth=1)
    axes[1].set_xticks(np.arange(len(order)), order, rotation=30, ha="right")
    axes[1].set_ylabel("Error-aware improvement vs Raw (%)")
    axes[1].set_title("Three-ROI sensitivity (bar=median, whisker=range)")
    axes[1].legend(
        handles=[
            Patch(facecolor="#4C78A8", label="Robust improvement"),
            Patch(facecolor="#E0A126", label="ROI-sensitive"),
            Patch(facecolor="#9A9A9A", label="Incomplete"),
        ],
        frameon=False,
        loc="lower left",
    )
    axes[1].grid(True, axis="y", alpha=0.25)
    fig.suptitle("V42 epoch 120 verified performance", fontsize=15, fontweight="bold")
    fig.tight_layout(rect=(0, 0, 1, 0.95))
    fig.savefig(
        ROOT / "figures" / "v42_e120_verified_overview.png",
        bbox_inches="tight",
        facecolor="white",
        transparent=False,
    )
    plt.close(fig)

    raw_circle = circle[circle.case == "raw"].iloc[0]
    v42_circle = circle[circle.case == "v42_e120"].iloc[0]
    lines = [
        "# V42 Epoch 120 Comprehensive Validation",
        "",
        "Primary displacement rule: Raw, V41, and V42 use identical frame pairs and frozen-V41 shared edge positions. Three ROIs are reported per dataset, and search-boundary saturation is rejected. No sample-specific scale correction is used.",
        "",
        "## 1. Traceable 100MG CD",
        "",
        "| Feature | Raw MAE (nm) | V41 MAE (nm) | V42 E120 MAE (nm) | V42 improvement vs Raw | Per-feature improved |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for feature in ["pillar", "via"]:
        row = key[key.test == f"CD {feature}"].iloc[0]
        lines.append(f"| {feature} | {row.raw_value:.2f} | {row.v41_value:.2f} | {row.v42_e120_value:.2f} | {row.v42_change_vs_raw_pct:+.2f}% | {int(row.v42_improved_items)}/36 |")
    lines += [
        "",
        "V42 improves nearly every individual feature versus Raw, but V41 remains better on the mean CD error.",
        "",
        "## 2. Real displacement, three-ROI sensitivity revalidation",
        "",
        "Common-best-30 selection is case symmetric: the same frame pairs are used for Raw, V41, and V42. The primary metric combines step RMSE to commanded motion with boundary-localization uncertainty, preventing a stable but biased result from appearing artificially strong.",
        "",
        "| Sequence | Error-aware status | Minimum improvement | Median improvement | Maximum improvement | Step-SD status |",
        "|---|---|---:|---:|---:|---|",
    ]
    for group in ["x_1um", "x_0p5um", "20x_1um", "20x_0p5um", "5x_1um", "5x_0p5um"]:
        row = roi_status[roi_status.group == group].iloc[0]
        lines.append(
            f"| {group} | {row.error_aware_status} | "
            f"{row.error_aware_improvement_min_pct:+.2f}% | "
            f"{row.error_aware_improvement_median_pct:+.2f}% | "
            f"{row.error_aware_improvement_max_pct:+.2f}% | {row.step_sd_status} |"
        )
    robust_groups = int((roi_status.error_aware_status == "robust_improvement").sum())
    sensitive_groups = int((roi_status.error_aware_status == "roi_sensitive").sum())
    incomplete_groups = int((roi_status.error_aware_status == "incomplete").sum())
    lines += [
        "",
        f"Across the six sequences, {robust_groups} are robust improvements across all three ROIs, {sensitive_groups} is ROI-sensitive, and {incomplete_groups} is incomplete because one ROI fails the detector validity gate. Step-SD results are reported separately because edge reconstruction cannot make the physical stage itself more stable.",
        "",
        "The previous single-ROI result is retained only as an audit. Exact ROI overlays, edge locations, step traces, and per-ROI tables are in roi_sensitivity_revalidation.",
        "",
        "## 3. Held-out synthetic shapes",
        "",
        f"- Mean boundary distance: Raw {synth.raw_mean_boundary_distance_px:.4f} px; V42 {synth.v42_mean_boundary_distance_px:.4f} px.",
        f"- V42 improves {int(synth.boundary_improved_count)}/20 images.",
        "- Symmetric Gaussian blur preserves its half-height boundary, so this test mainly acts as a no-harm/generalization check. V42 does not pass that check on these out-of-domain shapes.",
        "",
        "## 4. Unseen concentric-circle captures",
        "",
        f"- Complete-circle frames: {int(raw_circle.n_frames)} selected by Raw visibility from the first 50 captures.",
        f"- Radius standard deviation: Raw {raw_circle.radius_std_px:.5f} px; V42 {v42_circle.radius_std_px:.5f} px.",
        f"- Mean radial RMS residual: Raw {raw_circle.mean_radial_rms_px:.5f} px; V42 {v42_circle.mean_radial_rms_px:.5f} px.",
        "- V42 is essentially tied on radius repeatability and slightly worse on roundness residual.",
        "",
        "## Overall conclusion",
        "",
        "V42 E120 gives traceable 100MG CD improvement and usually produces steeper, easier-to-localize boundaries. The three-ROI revalidation shows that this advantage is robust in four displacement sequences, ROI-sensitive in 20x 0.5 um/step, and incomplete in 50x 0.5 um/step. It does not consistently reduce physical step-to-step variation, synthetic out-of-domain error, or concentric-circle roundness residual. The defensible conclusion is target-domain boundary-localization improvement, not universal displacement-stability superiority.",
    ]
    (ROOT / "FULL_VALIDATION_REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(key.to_string(index=False))


if __name__ == "__main__":
    main()

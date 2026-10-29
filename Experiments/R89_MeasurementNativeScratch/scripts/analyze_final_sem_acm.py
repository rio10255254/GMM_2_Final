"""Summarize the frozen R89 epoch-100 SEM-paired ACM validation."""
from __future__ import annotations

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.stats import wilcoxon
PROJECT_ROOT = Path(__file__).resolve().parents[3]


ROOT = Path(__file__).resolve().parents[1]
REPORT_ROOT = ROOT / "reports" / "final_validation" / "sem_acm_epoch100"
R89_TABLE_ROOT = ROOT / "results" / "final_validation" / "sem_acm_epoch100" / "acm_validation" / "results" / "tables"

SOURCES = {
    "Raw": (R89_TABLE_ROOT / "primary_contour_metrics.csv", "Raw"),
    "R89E100": (R89_TABLE_ROOT / "primary_contour_metrics.csv", "R89E100"),
    "R61v16": (Path(str(PROJECT_ROOT / 'Experiments/R69_ACMContourSEMValidation/results/tables/primary_contour_metrics.csv')), "R61v16"),
    "V42E120": (Path(str(PROJECT_ROOT / 'Experiments/R70_V42ACMContourSEMValidation/results/tables/primary_contour_metrics.csv')), "V42E120"),
    "R75v2Best": (Path(str(PROJECT_ROOT / 'Experiments/R77_R75v2ACMContourSEMValidation/results/tables/primary_contour_metrics.csv')), "R75v2Best"),
    "R75v2E100": (Path(str(PROJECT_ROOT / 'Experiments/R77_R75v2ACMContourSEMValidation/results/epoch100_audit/results/tables/primary_contour_metrics.csv')), "R75v2E100"),
}
METRICS = {
    "iou": "higher",
    "dice": "higher",
    "mean_boundary_distance_pitch_pct": "lower",
    "hd95_pitch_pct": "lower",
    "area_error_pct": "lower",
    "perimeter_error_pct": "lower",
    "circularity_abs_error": "lower",
}


def holm(values: list[float]) -> list[float]:
    values_array = np.asarray(values, dtype=float)
    order = np.argsort(values_array)
    adjusted = np.empty_like(values_array)
    running = 0.0
    for rank, index in enumerate(order):
        running = max(running, (len(values_array) - rank) * values_array[index])
        adjusted[index] = min(1.0, running)
    return adjusted.tolist()


def load_combined() -> tuple[pd.DataFrame, bool, float]:
    parts = []
    raw_reference = None
    raw_columns = list(METRICS) + ["centroid_alignment_shift_px"]
    exact = True
    maximum_difference = 0.0
    for method, (path, source_label) in SOURCES.items():
        frame = pd.read_csv(path)
        if len(frame) != 864 or frame.isna().any().any():
            raise RuntimeError(f"Invalid ACM table: {path}")
        raw = frame[frame["method"] == "Raw"].sort_values(["exposure", "pillar_id"]).reset_index(drop=True)
        if raw_reference is None:
            raw_reference = raw
        else:
            difference = float(np.max(np.abs(raw_reference[raw_columns].to_numpy() - raw[raw_columns].to_numpy())))
            maximum_difference = max(maximum_difference, difference)
            exact = exact and difference == 0.0
        selected = frame[frame["method"] == source_label].copy()
        selected["method"] = method
        parts.append(selected)
    combined = pd.concat(parts, ignore_index=True)
    if len(combined) != 432 * len(SOURCES):
        raise RuntimeError("Combined ACM table is incomplete")
    return combined, exact, maximum_difference


def main() -> int:
    REPORT_ROOT.mkdir(parents=True, exist_ok=True)
    combined, raw_exact, raw_max_difference = load_combined()
    metrics = list(METRICS)
    pillar = combined.groupby(["pillar_id", "method"], observed=True)[metrics].median().unstack("method")

    method_rows = []
    for method in SOURCES:
        row = {"method": method, "independent_pillars": 36, "repeated_exposures": 12}
        for metric in metrics:
            values = pillar[(metric, method)].to_numpy(float)
            row[f"median_{metric}"] = float(np.median(values))
            row[f"mean_{metric}"] = float(np.mean(values))
        method_rows.append(row)
    method_summary = pd.DataFrame(method_rows)
    method_summary.to_csv(REPORT_ROOT / "method_summary.csv", index=False, encoding="utf-8-sig")

    comparisons = []
    for source in ["Raw", "R61v16", "V42E120", "R75v2Best", "R75v2E100"]:
        p_values = []
        pending = []
        for metric, direction in METRICS.items():
            source_values = pillar[(metric, source)].to_numpy(float)
            r89_values = pillar[(metric, "R89E100")].to_numpy(float)
            improvement = r89_values - source_values if direction == "higher" else source_values - r89_values
            try:
                _statistic, p_value = wilcoxon(r89_values, source_values, alternative="two-sided", zero_method="wilcox")
            except ValueError:
                p_value = 1.0
            pending.append(
                {
                    "comparison": f"{source}_to_R89E100",
                    "source": source,
                    "metric": metric,
                    "direction": direction,
                    "source_median": float(np.median(source_values)),
                    "r89_median": float(np.median(r89_values)),
                    "median_improvement_positive_is_r89_better": float(np.median(improvement)),
                    "improved_pillars": int(np.count_nonzero(improvement > 0)),
                    "unchanged_pillars": int(np.count_nonzero(improvement == 0)),
                    "worsened_pillars": int(np.count_nonzero(improvement < 0)),
                    "improved_fraction": float(np.mean(improvement > 0)),
                    "wilcoxon_p_two_sided": float(p_value),
                }
            )
            p_values.append(float(p_value))
        adjusted = holm(p_values)
        for row, value in zip(pending, adjusted):
            row["wilcoxon_p_holm_within_comparison"] = value
            comparisons.append(row)
    comparison_frame = pd.DataFrame(comparisons)
    comparison_frame.to_csv(REPORT_ROOT / "r89_paired_comparisons.csv", index=False, encoding="utf-8-sig")

    sensitivity = pd.read_csv(R89_TABLE_ROOT / "acm_sensitivity_metrics.csv")
    if len(sensitivity) != 648 or set(sensitivity["method"]) != {"Raw", "R89E100"} or sensitivity.isna().any().any():
        raise RuntimeError("Sensitivity ACM table is invalid")
    sensitivity_pillar = sensitivity.groupby(["preset", "pillar_id", "method"], observed=True)[
        ["iou", "mean_boundary_distance_pitch_pct", "hd95_pitch_pct", "area_error_pct", "circularity_abs_error"]
    ].median().unstack("method")
    sensitivity_rows = []
    for preset in sorted(sensitivity["preset"].unique()):
        block = sensitivity_pillar.loc[preset]
        for metric in ["iou", "mean_boundary_distance_pitch_pct", "hd95_pitch_pct", "area_error_pct", "circularity_abs_error"]:
            raw = block[(metric, "Raw")].to_numpy(float)
            model = block[(metric, "R89E100")].to_numpy(float)
            direction = METRICS[metric]
            improvement = model - raw if direction == "higher" else raw - model
            sensitivity_rows.append(
                {
                    "preset": preset,
                    "metric": metric,
                    "raw_median": float(np.median(raw)),
                    "r89_median": float(np.median(model)),
                    "r89_improved_pillars": int(np.count_nonzero(improvement > 0)),
                    "r89_improved_fraction": float(np.mean(improvement > 0)),
                    "median_improvement_positive_is_r89_better": float(np.median(improvement)),
                }
            )
    sensitivity_summary = pd.DataFrame(sensitivity_rows)
    sensitivity_summary.to_csv(REPORT_ROOT / "sensitivity_summary.csv", index=False, encoding="utf-8-sig")

    primary = comparison_frame[comparison_frame["source"] == "Raw"].set_index("metric")
    rankings = {}
    for metric, direction in METRICS.items():
        ordered = method_summary.sort_values(f"median_{metric}", ascending=direction == "lower")
        rankings[metric] = ordered["method"].tolist()
    summary = {
        "status": "complete",
        "checkpoint_epoch": 100,
        "method": "Chan-Vese active contour with fixed settings and translation-only alignment",
        "physical_pillars": 36,
        "repeated_exposures": 12,
        "primary_rows": 864,
        "sensitivity_rows": 648,
        "raw_reproduced_exactly_across_prior_experiments": raw_exact,
        "raw_max_absolute_difference": raw_max_difference,
        "r89_vs_raw": {
            metric: {
                "raw_median": float(primary.loc[metric, "source_median"]),
                "r89_median": float(primary.loc[metric, "r89_median"]),
                "improved_pillars": int(primary.loc[metric, "improved_pillars"]),
                "worsened_pillars": int(primary.loc[metric, "worsened_pillars"]),
                "improved_fraction": float(primary.loc[metric, "improved_fraction"]),
                "holm_p": float(primary.loc[metric, "wilcoxon_p_holm_within_comparison"]),
            }
            for metric in METRICS
        },
        "method_rankings_best_to_worst": rankings,
        "promotion_conclusion": "fail",
        "failure_reason": "R89 worsens the SEM-paired complete contour for nearly all physical pillars despite improving synthetic degraded scenes.",
    }
    (REPORT_ROOT / "summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")

    methods = list(SOURCES)
    colors = ["#D97706", "#DC2626", "#2563EB", "#059669", "#7C3AED", "#64748B"]
    fig, axes = plt.subplots(1, 2, figsize=(13, 5))
    axes[0].bar(methods, [float(method_summary.set_index("method").loc[m, "median_iou"]) for m in methods], color=colors)
    axes[0].set_ylabel("Median contour IoU")
    axes[0].set_title("SEM-paired complete contour (higher is better)")
    axes[0].tick_params(axis="x", rotation=35)
    axes[0].set_ylim(0.93, 0.965)
    axes[1].bar(methods, [float(method_summary.set_index("method").loc[m, "median_mean_boundary_distance_pitch_pct"]) for m in methods], color=colors)
    axes[1].set_ylabel("Median boundary distance (% pitch)")
    axes[1].set_title("SEM-paired boundary error (lower is better)")
    axes[1].tick_params(axis="x", rotation=35)
    fig.tight_layout()
    fig.savefig(REPORT_ROOT / "method_comparison.png", dpi=180)
    plt.close(fig)

    raw_iou = pillar[("iou", "Raw")].to_numpy(float)
    r89_iou = pillar[("iou", "R89E100")].to_numpy(float)
    fig, ax = plt.subplots(figsize=(6, 6))
    ax.scatter(raw_iou, r89_iou, color="#DC2626")
    low = min(raw_iou.min(), r89_iou.min()) - 0.002
    high = max(raw_iou.max(), r89_iou.max()) + 0.002
    ax.plot([low, high], [low, high], "k--", lw=1)
    ax.set_xlim(low, high)
    ax.set_ylim(low, high)
    ax.set_xlabel("Raw pillar-median contour IoU")
    ax.set_ylabel("R89 epoch-100 pillar-median contour IoU")
    ax.set_title("Each point is one physical pillar")
    ax.grid(alpha=0.25)
    fig.tight_layout()
    fig.savefig(REPORT_ROOT / "r89_vs_raw_per_pillar_iou.png", dpi=180)
    plt.close(fig)
    print(json.dumps(summary, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

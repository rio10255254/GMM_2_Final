"""R46 Rayleigh diagnostic:對合併後的 csv(R46 + COMBO + a030 + a043 + a025)跑 Rayleigh 分桶分析。

直接 import 既有的 rayleigh_diagnostic 模組函式,但加 R46 到 model list,並覆寫輸出位置到 R46。

讀:
- R46/results/capability_eval/per_pair_metrics_combined.csv(R46 + COMBO + a030 + a043 + a025)

寫:
- R46/results/rayleigh_diagnostic/per_pair_with_width.csv
- R46/results/rayleigh_diagnostic/aggregate_by_class.csv
- R46/results/rayleigh_diagnostic/rayleigh_summary.md
- R46/results/rayleigh_diagnostic/feature_width_scatter.png
- R46/results/rayleigh_diagnostic/validation/paired_tests_*.csv
- R46/results/rayleigh_diagnostic/plots/*.png
"""
from __future__ import annotations

import argparse
import csv
import math
import sys
from collections import defaultdict
from pathlib import Path


REPO_ROOT = Path("D:/GMM_2_Final")
R39_SCRIPTS = REPO_ROOT / "Experiments" / "R39_ShapeGeneralization" / "scripts"
sys.path.insert(0, str(R39_SCRIPTS))

import rayleigh_diagnostic as rd  # noqa: E402


R46_OUT = REPO_ROOT / "Experiments" / "R46_CornerAwareFineTune" / "results" / "rayleigh_diagnostic"
R46_CSV = (
    REPO_ROOT / "Experiments" / "R46_CornerAwareFineTune"
    / "results" / "capability_eval" / "per_pair_metrics_combined.csv"
)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="R46 Rayleigh diagnostic wrapper")
    parser.add_argument("--csv", type=Path, default=R46_CSV)
    parser.add_argument("--out", type=Path, default=R46_OUT)
    parser.add_argument("--rayleigh-px", type=float, default=11.7)
    args = parser.parse_args(argv)

    # 把 R46 加進 rayleigh_diagnostic 模組級常數(讓 summary table 出 5 行)
    rd.MODELS_ORDER = ["COMBO", "a030", "a043", "R39R40_a025", "R46_a025_corner_finetune"]
    rd.RAYLEIGH_PX = args.rayleigh_px

    fields, rows = rd.load_csv_rows(args.csv)
    print(f"Loaded {len(rows)} rows from {args.csv}")

    widths = rd.augment_with_widths(rows)
    print(f"Computed widths for {len(widths)} unique GT images")

    args.out.mkdir(parents=True, exist_ok=True)
    rd.write_augmented_csv(args.out / "per_pair_with_width.csv", fields, rows, widths)
    agg = rd.aggregate_by_class(rows, widths)
    rd.write_aggregate_csv(args.out / "aggregate_by_class.csv", agg)
    rd.write_summary_md(args.out / "rayleigh_summary.md", agg, args.rayleigh_px)
    rd.write_scatter_plot(args.out / "feature_width_scatter.png", rows, widths, args.rayleigh_px)
    print(f"Wrote core outputs to {args.out}")

    # 套用既有的 plots / validate 腳本(也指向 R46 csv 跟輸出位置)
    try:
        import rayleigh_diagnostic_plots as rdp  # noqa: E402
        rdp.MODEL_ORDER = rd.MODELS_ORDER
        rdp.MODEL_COLORS["R46_a025_corner_finetune"] = "#AA4488"
        plots_out = args.out / "plots"
        plots_out.mkdir(parents=True, exist_ok=True)
        rows_w = rdp.load_rows(args.out / "per_pair_with_width.csv")
        rdp.fig1_feature_width_distribution(rows_w, plots_out / "1_feature_width_distribution.png")
        rdp.fig2_a043_vs_a025_delta(rows_w, plots_out / "2_a043_vs_a025_delta_scatter.png")
        rdp.fig3_box_per_class(rows_w, plots_out / "3_box_per_class.png")
        rdp.fig4_per_stage_bars(rows_w, plots_out / "4_per_stage_metric_bars.png")
        rdp.fig5_a043_minus_a025_per_stage(rows_w, plots_out / "5_a043_minus_a025_per_stage.png")
        rdp.fig6_corner_retention_distributions(rows_w, plots_out / "6_corner_retention_distributions.png")
        rdp.fig7_stage_overview_scatter(rows_w, plots_out / "7_stage_overview_scatter.png")
        print(f"Wrote plots to {plots_out}")
    except Exception as e:
        print(f"  WARN plots failed: {e}")

    # 跑 paired tests
    try:
        import rayleigh_diagnostic_validate as rdv  # noqa: E402
        val_out = args.out / "validation"
        val_out.mkdir(parents=True, exist_ok=True)
        rows_for_val = rdv.load_rows(args.out / "per_pair_with_width.csv")
        by_key = rdv.build_pair_index(rows_for_val)

        stages = sorted({r["stage"] for r in rows_for_val})
        per_stage = rdv.paired_tests(by_key, "stage", stages)
        per_class = rdv.paired_tests(by_key, "rayleigh_class", ["supra", "mixed", "sub"])
        rdv.write_csv(val_out / "paired_tests_per_stage.csv", per_stage)
        rdv.write_csv(val_out / "paired_tests_per_class.csv", per_class)

        revised = rdv.revised_expected_gain(by_key, rdv.CLASS_WEIGHTS)
        rdv.write_csv(val_out / "revised_expected_gain.csv", revised)

        twl = rdv.top_wins_losses(by_key, metric="psnr", top_n=15)
        rdv.write_csv(val_out / "top_wins_losses_psnr.csv", twl)
        print(f"Wrote validation to {val_out}")
    except Exception as e:
        print(f"  WARN validation failed: {e}")

    # 額外:R46 vs a025 配對檢定(本實驗最關鍵的對比)
    try:
        from scipy import stats as scistats  # noqa: E402
        import numpy as np  # noqa: E402

        rows_for_r46 = rdv.load_rows(args.out / "per_pair_with_width.csv")
        by_key_r46 = rdv.build_pair_index(rows_for_r46)

        print("\n=== R46 vs a025 paired t-test ===")
        print(f"{'metric':28} {'class':6} {'n':>4} {'mean_d':>10} {'t':>7} {'p':>10} sig")

        metrics_with_direction = [
            ("psnr", "+"),
            ("ssim", "+"),
            ("boundary_f_score", "+"),
            ("corner_retention", "+"),
            ("straight_edge_coverage", "+"),
            ("high_frequency_retention", "+"),
            ("edge_retention", "+"),
            ("shape_error_score", "-"),
        ]
        r46_vs_a025_rows = []
        for col, _direction in metrics_with_direction:
            for cls in ("supra", "mixed", "sub", "all"):
                deltas = []
                for k, mdict in by_key_r46.items():
                    if "R46_a025_corner_finetune" not in mdict or "R39R40_a025" not in mdict:
                        continue
                    if cls != "all" and mdict["R46_a025_corner_finetune"].get("rayleigh_class") != cls:
                        continue
                    v_r46 = rdv.fnum(mdict["R46_a025_corner_finetune"].get(col))
                    v_a025 = rdv.fnum(mdict["R39R40_a025"].get(col))
                    if math.isfinite(v_r46) and math.isfinite(v_a025):
                        deltas.append(v_r46 - v_a025)
                if len(deltas) < 2:
                    continue
                arr = np.array(deltas)
                mean_d = float(arr.mean())
                t_stat, p_val = scistats.ttest_1samp(arr, 0)
                sig = "***" if p_val < 0.001 else "**" if p_val < 0.01 else "*" if p_val < 0.05 else "n.s."
                print(f"{col:28} {cls:6} {len(arr):4d} {mean_d:+10.4f} {float(t_stat):+7.2f} {float(p_val):10.2e} {sig}")
                r46_vs_a025_rows.append({
                    "metric": col,
                    "rayleigh_class": cls,
                    "n": len(arr),
                    "mean_delta_r46_minus_a025": round(mean_d, 6),
                    "t_stat": round(float(t_stat), 4),
                    "p_value": float(p_val),
                    "sig_at_05": "yes" if p_val < 0.05 else "no",
                })

        rdv.write_csv(args.out / "r46_vs_a025_paired_test.csv", r46_vs_a025_rows)
        print(f"\nWrote r46_vs_a025_paired_test.csv")
    except Exception as e:
        print(f"  WARN R46 vs a025 paired test failed: {e}")
        import traceback
        traceback.print_exc()

    print(f"\n[R46 diagnostic] done -> {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

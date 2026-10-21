"""step6_aggregate.py — 彙總所有模組結果為 ring_analysis_summary.json"""
from pathlib import Path
import json, numpy as np

DEST = Path(r"D:\GMM_2_Final\_deployment_package\GeoEdge_R26_使用包\輸出結果\驗證分析\R26_validation_complete")

import csv as csv_mod

with open(DEST / "data" / "step2_results.json", encoding="utf-8") as f:
    s2 = json.load(f)
with open(DEST / "data" / "step3_results.json", encoding="utf-8") as f:
    s3 = json.load(f)
with open(DEST / "data" / "step4_results.json", encoding="utf-8") as f:
    s4 = json.load(f)
with open(DEST / "data" / "ring_geometry_per_image.json", encoding="utf-8") as f:
    geom = json.load(f)

# 讀取 batch_metrics.csv 取 Module 4 所需指標
csv_rows = {}
with open(DEST / "data" / "batch_metrics.csv", encoding="utf-8-sig") as f:
    for row in csv_mod.DictReader(f):
        csv_rows[row["name"]] = row

names = sorted(s2.keys())

# 統計摘要
slope_impr  = [s2[n]["slope_improvement_pct"] for n in names]
snr_delta   = [s4[n]["output_roi_snr"]   - s4[n]["input_roi_snr"]   for n in names]
weber_delta = [s4[n]["output_roi_weber"] - s4[n]["input_roi_weber"] for n in names]

# Module 4 — 熱圖六指標各案例值（改善量）
m4_per_image = {}
for n in names:
    r2, r4, row = s2[n], s4[n], csv_rows[n]
    m4_per_image[n] = {
        "peak_contrast_gain":     float(row["peak_contrast_gain"]),
        "edge_slope_impr_pct":    r2["slope_improvement_pct"],
        "roi_snr_delta":          r4["output_roi_snr"]   - r4["input_roi_snr"],
        "roi_weber_delta":        r4["output_roi_weber"] - r4["input_roi_weber"],
        "gradient_p95_ratio":     float(row["gradient_p95_ratio"]),   # <1 = 抑制（改善）
        "entropy_delta":          float(row["entropy_delta"]),         # <0 = 抑制（改善）
    }

m4_vals = {k: [m4_per_image[n][k] for n in names]
           for k in list(m4_per_image[names[0]].keys())}

summary = {
    "module1_edge_slope": {
        "mean_improvement_pct": float(np.mean(slope_impr)),
        "min_improvement_pct":  float(np.min(slope_impr)),
        "max_improvement_pct":  float(np.max(slope_impr)),
        "per_image": {n: s2[n] for n in names},
    },
    "module2_radial_consistency": s3,
    "module3_ring_roi": {
        "mean_snr_delta":   float(np.mean(snr_delta)),
        "mean_weber_delta": float(np.mean(weber_delta)),
        "per_image": {n: s4[n] for n in names},
    },
    "module4_heatmap_metrics": {
        "summary": {k: {"mean": float(np.mean(v)), "std": float(np.std(v))}
                    for k, v in m4_vals.items()},
        "per_image": m4_per_image,
    },
    "ring_geometry": geom,
}

with open(DEST / "data" / "ring_analysis_summary.json", "w", encoding="utf-8") as f:
    json.dump(summary, f, indent=2, ensure_ascii=False)

print("Task 6 完成 — ring_analysis_summary.json 已寫入")
print(f"Module 1 邊緣斜率改善均值:      {np.mean(slope_impr):.1f}%")
print(f"Module 2 AUC-std 改善:          {s3['consistency_improvement_pct']:.1f}%")
print(f"Module 3 ROI SNR 均值 Δ:       {np.mean(snr_delta):+.3f}")
print(f"Module 3 ROI Weber 均值 Δ:     {np.mean(weber_delta):+.3f}")
print(f"Module 4 環峰值對比增益均值:    {np.mean(m4_vals['peak_contrast_gain']):.2f} gray")
print(f"Module 4 梯度P95比值均值:       {np.mean(m4_vals['gradient_p95_ratio']):.3f} (目標<1)")

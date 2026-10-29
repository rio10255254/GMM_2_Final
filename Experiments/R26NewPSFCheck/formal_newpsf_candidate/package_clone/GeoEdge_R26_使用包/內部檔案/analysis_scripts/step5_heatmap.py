"""step5_heatmap.py — 10 案例 × 6 指標改善幅度熱圖"""
import cv2, math, json, csv
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from pathlib import Path
PROJECT_ROOT = Path(__file__).resolve().parents[7]

plt.rcParams.update({
    "font.family": "sans-serif",
    "font.sans-serif": ["Microsoft JhengHei", "Microsoft YaHei", "DejaVu Sans"],
    "axes.unicode_minus": False,
    "font.size": 11, "axes.titlesize": 12, "axes.labelsize": 11,
    "xtick.labelsize": 10, "ytick.labelsize": 10,
    "figure.dpi": 150, "savefig.bbox": "tight",
    "axes.spines.top": False, "axes.spines.right": False,
})

PKG   = Path(str(PROJECT_ROOT / '_deployment_package/GeoEdge_R26_使用包'))
DEST  = PKG / "輸出結果" / "驗證分析" / "R26_validation_complete"
NAMES = sorted([f.name for f in (PKG / "輸出結果" / "驗證分析" /
                "R26_external_batch_bundle" / "input_subset").glob("*.bmp")])

# 載入各步驟結果
with open(DEST / "data" / "batch_summary.json", encoding="utf-8") as f:
    batch = json.load(f)
with open(DEST / "data" / "step2_results.json", encoding="utf-8") as f:
    step2 = json.load(f)
with open(DEST / "data" / "step4_results.json", encoding="utf-8") as f:
    step4 = json.load(f)

# 讀取 batch_metrics.csv
csv_data = {}
with open(DEST / "data" / "batch_metrics.csv", encoding="utf-8-sig") as f:
    for row in csv.DictReader(f):
        csv_data[row["name"]] = row

# 6 個指標：(label, value_func)
# 正值 = 改善，負值 = 退步
def get_metrics(name):
    r2 = step2[name]
    r4 = step4[name]
    row = csv_data[name]
    return {
        "環峰值對比增益\n(gray)":      float(row["peak_contrast_gain"]),
        "邊緣斜率改善\n(%)":           r2["slope_improvement_pct"],
        "ROI SNR 改善\n(Δ)":          r4["output_roi_snr"] - r4["input_roi_snr"],
        "ROI Weber Contrast\n改善(Δ)": r4["output_roi_weber"] - r4["input_roi_weber"],
        "梯度P95比值\n(out/in,<1=抑制)": float(row["gradient_p95_ratio"]),
        "熵變化量\n(bits,<0=抑制)":    float(row["entropy_delta"]),
    }

metric_labels = list(get_metrics(NAMES[0]).keys())
matrix = np.array([[list(get_metrics(n).values())[i]
                    for n in NAMES]
                   for i in range(len(metric_labels))])

# 正規化至 [-1, 1]（對每個指標獨立正規化）
matrix_norm = np.zeros_like(matrix)
for i, row in enumerate(matrix):
    vmax = np.abs(row).max()
    if vmax > 0:
        matrix_norm[i] = row / vmax
    # 梯度比值和熵：值越小越好，需翻轉
    if i in [4, 5]:
        matrix_norm[i] = -matrix_norm[i]

# ── 圖表 ──
short_names = [n[10:22] for n in NAMES]  # 短標籤
fig, ax = plt.subplots(figsize=(11, 5))
im = ax.imshow(matrix_norm, cmap="RdBu", vmin=-1, vmax=1, aspect="auto")

ax.set_xticks(range(len(NAMES)))
ax.set_xticklabels(short_names, rotation=45, ha="right", fontsize=9)
ax.set_yticks(range(len(metric_labels)))
ax.set_yticklabels(metric_labels, fontsize=10)

# 格內原始數值
for i in range(len(metric_labels)):
    for j in range(len(NAMES)):
        val = matrix[i, j]
        fmt = f"{val:+.2f}" if abs(val) < 100 else f"{val:+.0f}"
        ax.text(j, i, fmt, ha="center", va="center", fontsize=8,
                color="white" if abs(matrix_norm[i,j]) > 0.6 else "black")

plt.colorbar(im, ax=ax, label="正規化改善幅度（藍=改善，紅=退步）", shrink=0.8)
ax.set_title("R26 批次驗證指標熱圖（n=10）", fontsize=13)
plt.tight_layout()
fig.savefig(DEST / "figures" / "05_batch_metric_heatmap.png")
plt.close(fig)

print("Task 5 完成 — 05_batch_metric_heatmap.png 已儲存")

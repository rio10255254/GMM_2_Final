"""step4_roi_metrics.py — 環形 ROI 內局部指標（SNR、Weber Contrast、Gradient P95）"""
import cv2, json
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from pathlib import Path
PROJECT_ROOT = Path(__file__).resolve().parents[5]

plt.rcParams.update({
    "font.family": "sans-serif",
    "font.sans-serif": ["Microsoft JhengHei", "Microsoft YaHei", "DejaVu Sans"],
    "axes.unicode_minus": False,
    "font.size": 11, "axes.titlesize": 12, "axes.labelsize": 11,
    "xtick.labelsize": 10, "ytick.labelsize": 10,
    "figure.dpi": 150, "savefig.bbox": "tight",
    "axes.spines.top": False, "axes.spines.right": False,
})

PKG     = Path(str(PROJECT_ROOT / '_deployment_package/GeoEdge_R26_使用包'))
IN_DIR  = PKG / "輸出結果" / "驗證分析" / "R26_external_batch_bundle" / "input_subset"
OUT_BMP = PKG / "輸出結果" / "推論結果" / "reconstruct_progress_r26_sm035_best_tradeoff_in_input_subset_20260317_162050"
DEST    = PKG / "輸出結果" / "驗證分析" / "R26_validation_complete"
NAMES   = sorted([f.name for f in IN_DIR.glob("*.bmp")])

with open(DEST / "data" / "ring_geometry_per_image.json", encoding="utf-8") as f:
    GEOM = json.load(f)

def imread_gray(p):
    arr = np.fromfile(str(p), dtype=np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_GRAYSCALE)
    if img is None:
        raise FileNotFoundError(p)
    return img

def ring_roi_metrics(img, cx, cy, peak_r, fwhm):
    yy, xx = np.indices(img.shape)
    rr = np.sqrt((xx - cx)**2 + (yy - cy)**2)
    half_bw = fwhm / 2.0
    roi_mask = (rr >= peak_r - half_bw) & (rr <= peak_r + half_bw)
    roi_vals = img[roi_mask].astype(np.float64)
    if len(roi_vals) == 0:
        return 0.0, 0.0, 0.0
    peak_val = float(np.percentile(roi_vals, 95))
    bg_mask  = rr < (peak_r - half_bw * 2)
    bg_vals  = img[bg_mask].astype(np.float64) if bg_mask.any() else roi_vals
    mad = float(np.median(np.abs(bg_vals - np.median(bg_vals)))) * 1.4826
    snr = peak_val / max(mad, 1e-6)
    bg_mean = float(np.mean(bg_vals))
    weber = (peak_val - bg_mean) / max(bg_mean, 1e-6)
    sobel = cv2.Sobel(img, cv2.CV_64F, 1, 0)**2 + cv2.Sobel(img, cv2.CV_64F, 0, 1)**2
    grad_mag = np.sqrt(sobel)
    roi_grad_p95 = float(np.percentile(grad_mag[roi_mask], 95))
    return snr, weber, roi_grad_p95

results = {}
in_snr, out_snr = [], []
in_weber, out_weber = [], []
in_grad, out_grad = [], []

for name in NAMES:
    g = GEOM[name]
    cx, cy, peak_r, fwhm = g["cx"], g["cy"], g["peak_r"], g["fwhm"]
    img_in  = imread_gray(IN_DIR / name)
    img_out = imread_gray(OUT_BMP / name)
    s1, w1, g1 = ring_roi_metrics(img_in,  cx, cy, peak_r, fwhm)
    s2, w2, g2 = ring_roi_metrics(img_out, cx, cy, peak_r, fwhm)
    in_snr.append(s1);    out_snr.append(s2)
    in_weber.append(w1);  out_weber.append(w2)
    in_grad.append(g1);   out_grad.append(g2)
    results[name] = {
        "input_roi_snr": s1,   "output_roi_snr": s2,
        "input_roi_weber": w1, "output_roi_weber": w2,
        "input_roi_grad_p95": g1, "output_roi_grad_p95": g2,
    }
    print(f"{name[:30]}: SNR {s1:.2f}→{s2:.2f}, Weber {w1:.3f}→{w2:.3f}")

x = np.arange(len(NAMES))
fig, axes = plt.subplots(3, 1, figsize=(10, 10), sharex=True)

for ax, y_in, y_out, ylabel, title in [
    (axes[0], in_snr,   out_snr,   "SNR",             "環 ROI 訊號雜訊比（SNR）"),
    (axes[1], in_weber, out_weber, "Weber Contrast",  "環 ROI Weber 對比"),
    (axes[2], in_grad,  out_grad,  "梯度 P95",        "環 ROI Sobel 梯度 P95"),
]:
    for i in range(len(NAMES)):
        color = "#2ecc71" if y_out[i] >= y_in[i] else "#e74c3c"
        ax.plot([x[i] - 0.15, x[i] + 0.15], [y_in[i], y_out[i]],
                color=color, lw=1.5, alpha=0.7)
        ax.scatter(x[i] - 0.15, y_in[i],  s=40, color="gray",  zorder=3)
        ax.scatter(x[i] + 0.15, y_out[i], s=40, color="black", zorder=3)
    ax.set_ylabel(ylabel)
    ax.set_title(title)

axes[2].set_xticks(x)
axes[2].set_xticklabels([n[10:29] for n in NAMES], rotation=45, ha="right", fontsize=9)
axes[0].legend(handles=[
    Line2D([0], [0], color="gray",  marker="o", ms=5, label="Input"),
    Line2D([0], [0], color="black", marker="o", ms=5, label="Output"),
], loc="upper right")

fig.suptitle("環形 ROI 局部品質指標（n=10）", fontsize=13)
plt.tight_layout()
fig.savefig(DEST / "figures" / "04_ring_roi_metrics.png")
plt.close(fig)

with open(DEST / "data" / "step4_results.json", "w", encoding="utf-8") as f:
    json.dump(results, f, indent=2, ensure_ascii=False)

print("Task 4 完成 — 04_ring_roi_metrics.png 已儲存")

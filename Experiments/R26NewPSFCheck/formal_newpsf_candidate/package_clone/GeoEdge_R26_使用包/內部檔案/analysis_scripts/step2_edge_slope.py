"""step2_edge_slope.py — 邊緣最大斜率與 FWHM 分析"""
import cv2, json
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from pathlib import Path
from scipy.ndimage import uniform_filter1d
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

def edge_metrics(img, cx, cy, peak_r, fwhm):
    yy, xx = np.indices(img.shape)
    rr = np.sqrt((xx - cx)**2 + (yy - cy)**2)
    ridx = np.floor(rr).astype(np.int32)
    rsum = np.bincount(ridx.ravel(), weights=img.ravel().astype(np.float64))
    rcnt = np.bincount(ridx.ravel())
    profile = rsum / np.maximum(rcnt, 1.0)
    smooth = uniform_filter1d(profile.astype(np.float64), size=5)
    grad = np.gradient(smooth)
    r0 = max(0, int(peak_r) - int(fwhm))
    r1 = min(len(grad) - 1, int(peak_r) + int(fwhm))
    region = grad[r0:r1]
    max_rising  = float(np.max(region))
    max_falling = float(abs(np.min(region)))
    # Background-subtracted FWHM
    peak_v = profile[int(peak_r)]
    bg_start = max(0, int(peak_r) - 400)
    bg_end   = max(1, int(peak_r) - 200)
    bg_val   = float(np.median(profile[bg_start:bg_end])) if bg_end > bg_start else float(np.median(profile[:50]))
    half_v = (peak_v - bg_val) / 2.0 + bg_val
    left = int(peak_r)
    while left > 0 and profile[left] > half_v:
        left -= 1
    right = int(peak_r)
    while right < len(profile) - 1 and profile[right] > half_v:
        right += 1
    fwhm_out = float(right - left)
    return max_rising, max_falling, fwhm_out

results = {}
in_rising, out_rising = [], []
in_fwhm, out_fwhm = [], []

for name in NAMES:
    g = GEOM[name]
    cx, cy, peak_r, fwhm = g["cx"], g["cy"], g["peak_r"], g["fwhm"]
    img_in  = imread_gray(IN_DIR / name)
    img_out = imread_gray(OUT_BMP / name)
    r1, f1, w1 = edge_metrics(img_in,  cx, cy, peak_r, fwhm)
    r2, f2, w2 = edge_metrics(img_out, cx, cy, peak_r, fwhm)
    in_rising.append(r1);  out_rising.append(r2)
    in_fwhm.append(w1);    out_fwhm.append(w2)
    impr = (r2 - r1) / r1 * 100 if r1 > 0 else 0.0
    results[name] = {
        "input_rising_slope": r1,
        "output_rising_slope": r2,
        "slope_improvement_pct": impr,
        "input_fwhm": w1,
        "output_fwhm": w2,
    }
    print(f"{name[:30]}: rising {r1:.3f}→{r2:.3f} ({impr:+.1f}%), fwhm {w1:.1f}→{w2:.1f}")

x = np.arange(len(NAMES))
w = 0.35
fig, axes = plt.subplots(2, 1, figsize=(10, 7), sharex=True)

axes[0].bar(x - w/2, in_rising,  w, label="Input",  color="#888888")
axes[0].bar(x + w/2, out_rising, w, label="Output", color="#222222")
axes[0].axhline(np.mean(in_rising),  ls="--", lw=1, color="#888888", alpha=0.7)
axes[0].axhline(np.mean(out_rising), ls="--", lw=1, color="#222222", alpha=0.7)
axes[0].set_ylabel("最大上升斜率（灰階/px）")
axes[0].set_title("環邊緣銳利度分析 — 最大上升斜率（主指標）")
axes[0].legend()

axes[1].bar(x - w/2, in_fwhm,  w, label="Input",  color="#888888")
axes[1].bar(x + w/2, out_fwhm, w, label="Output", color="#222222")
axes[1].axhline(np.mean(in_fwhm),  ls="--", lw=1, color="#888888", alpha=0.7)
axes[1].axhline(np.mean(out_fwhm), ls="--", lw=1, color="#222222", alpha=0.7)
axes[1].set_ylabel("FWHM（px）")
axes[1].set_title("環邊緣銳利度分析 — 半高全寬 FWHM（輔助）")
axes[1].set_xticks(x)
axes[1].set_xticklabels([n[10:29] for n in NAMES], rotation=45, ha="right", fontsize=9)
axes[1].legend()

plt.tight_layout()
fig.savefig(DEST / "figures" / "03_edge_sharpness_slope.png")
plt.close(fig)

with open(DEST / "data" / "step2_results.json", "w", encoding="utf-8") as f:
    json.dump(results, f, indent=2, ensure_ascii=False)

print("Task 2 完成 — 03_edge_sharpness_slope.png 已儲存")

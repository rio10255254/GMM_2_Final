"""step3_radial.py — 跨 10 案例徑向輪廓對齊與一致性分析"""
import cv2, json
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
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

HALF_WIN = 100

def imread_gray(p):
    arr = np.fromfile(str(p), dtype=np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_GRAYSCALE)
    if img is None:
        raise FileNotFoundError(p)
    return img

def get_radial_profile(img, cx, cy):
    yy, xx = np.indices(img.shape)
    rr = np.sqrt((xx - cx)**2 + (yy - cy)**2)
    ridx = np.floor(rr).astype(np.int32)
    rsum = np.bincount(ridx.ravel(), weights=img.ravel().astype(np.float64))
    rcnt = np.bincount(ridx.ravel())
    return rsum / np.maximum(rcnt, 1.0)

profiles_in, profiles_out = [], []
skipped = []

for name in NAMES:
    g = GEOM[name]
    cx, cy, peak_r = g["cx"], g["cy"], g["peak_r"]
    peak_i = int(peak_r)
    lo = max(0, peak_i - HALF_WIN)
    hi = min(10000, peak_i + HALF_WIN + 1)

    for img_path, lst in [(IN_DIR / name, profiles_in), (OUT_BMP / name, profiles_out)]:
        img = imread_gray(img_path)
        profile = get_radial_profile(img, cx, cy)
        # Extend profile if needed
        if hi > len(profile):
            hi = len(profile)
        seg = profile[lo:hi]
        expected_len = 2 * HALF_WIN + 1
        if len(seg) == expected_len:
            lst.append(seg)
        else:
            print(f"WARNING: {name} 輪廓窗口長度不足（{len(seg)} < {expected_len}），已跳過")
            if name not in skipped:
                skipped.append(name)

n_included = len(profiles_in)
if n_included < 10:
    print(f"WARNING: 僅 {n_included}/10 張圖納入分析")
else:
    print(f"所有 {n_included} 張圖均納入分析")

profiles_in  = np.array(profiles_in)
profiles_out = np.array(profiles_out)
x_axis = np.arange(-HALF_WIN, HALF_WIN + 1)
mean_in,  std_in  = profiles_in.mean(0),  profiles_in.std(0)
mean_out, std_out = profiles_out.mean(0), profiles_out.std(0)

auc_in  = float(np.trapz(std_in,  x_axis))
auc_out = float(np.trapz(std_out, x_axis))
improvement = (auc_in - auc_out) / auc_in * 100 if auc_in > 0 else 0.0
print(f"AUC-std  Input: {auc_in:.2f}  Output: {auc_out:.2f}  改善: {improvement:.1f}%")

fig, axes = plt.subplots(1, 2, figsize=(12, 5), sharey=True)
for ax, profiles, mean, std, title in [
    (axes[0], profiles_in,  mean_in,  std_in,  "Input（模型輸入）"),
    (axes[1], profiles_out, mean_out, std_out, "Output（R26 輸出）"),
]:
    for p in profiles:
        ax.plot(x_axis, p, color="gray", alpha=0.25, lw=0.8)
    ax.plot(x_axis, mean, color="black", lw=2.0, label="均值")
    ax.fill_between(x_axis, mean - std, mean + std, color="black", alpha=0.15, label="±1 std")
    ax.set_title(title)
    ax.set_xlabel("相對環峰值位置（px）")
    ax.legend(fontsize=10)

axes[0].set_ylabel("灰階強度")
fig.suptitle("跨案例徑向輪廓一致性（n=10）", fontsize=13)
axes[1].text(0.97, 0.05,
    f"AUC-std 改善: {improvement:.1f}%\n(Input:{auc_in:.1f} → Output:{auc_out:.1f})",
    transform=axes[1].transAxes, ha="right", va="bottom", fontsize=9,
    bbox=dict(boxstyle="round,pad=0.3", facecolor="white", edgecolor="gray"))

plt.tight_layout()
fig.savefig(DEST / "figures" / "02_radial_profile_crosscase.png")
plt.close(fig)

with open(DEST / "data" / "step3_results.json", "w", encoding="utf-8") as f:
    json.dump({
        "n_images_included": n_included,
        "skipped_images": skipped,
        "auc_std_input": auc_in,
        "auc_std_output": auc_out,
        "consistency_improvement_pct": improvement,
    }, f, indent=2, ensure_ascii=False)

print("Task 3 完成 — 02_radial_profile_crosscase.png 已儲存")

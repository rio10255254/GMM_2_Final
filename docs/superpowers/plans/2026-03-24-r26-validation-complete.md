# R26 統一驗證包 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 將現有分散的 R26 驗證材料整合為單一學術級驗證包（`R26_validation_complete\`），並新增四個環形結構專項分析模組與對應圖表。

**Architecture:** 以五個獨立 Python 腳本分別執行前置環形偵測、四個分析模組，最後由整合腳本彙總 JSON 並複製精選圖表，再手動撰寫主報告 markdown。所有腳本複用既有 `generate_advanced_analysis.py` 中的 `detect_ring()` 函數。

**Tech Stack:** Python 3.x（portable runtime）、cv2 4.10、numpy 1.26、scipy 1.13、matplotlib 3.9

---

## 常數定義（所有腳本共用）

```python
PKG    = Path(r"D:\GMM_2_Final\_deployment_package\GeoEdge_R26_使用包")
PYTHON = PKG / "內部檔案" / "portable_runtime" / "python.exe"
IN_DIR = PKG / "輸出結果" / "驗證分析" / "R26_external_batch_bundle" / "input_subset"
OUT_DIR_BMP = PKG / "輸出結果" / "推論結果" / "reconstruct_progress_r26_sm035_best_tradeoff_in_input_subset_20260317_162050"
DEST   = PKG / "輸出結果" / "驗證分析" / "R26_validation_complete"
SRC_SINGLE = PKG / "輸出結果" / "驗證分析" / "R26_external_single_bundle"
SRC_BATCH  = PKG / "輸出結果" / "驗證分析" / "R26_external_batch_bundle"
NAMES  = sorted([f.name for f in IN_DIR.glob("*.bmp")])   # 10 個檔名，已排序
```

---

## 共用工具程式（貼入所有腳本開頭）

```python
import cv2, math, json
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from pathlib import Path

# CJK + 學術風格
plt.rcParams.update({
    "font.family": "sans-serif",
    "font.sans-serif": ["Microsoft JhengHei", "Microsoft YaHei", "DejaVu Sans"],
    "axes.unicode_minus": False,
    "font.size": 11, "axes.titlesize": 12, "axes.labelsize": 11,
    "xtick.labelsize": 10, "ytick.labelsize": 10,
    "figure.dpi": 150, "savefig.bbox": "tight",
    "axes.spines.top": False, "axes.spines.right": False,
})

def imread_gray(p):
    arr = np.fromfile(str(p), dtype=np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_GRAYSCALE)
    if img is None:
        raise FileNotFoundError(p)
    return img

def detect_ring(img):
    """複製自 generate_advanced_analysis.py — 不修改"""
    blur = cv2.GaussianBlur(img, (0,0), 3.0)
    otsu, _ = cv2.threshold(blur, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    pct = np.percentile(blur, 85)
    mask = (blur >= int(max(otsu, pct))).astype(np.uint8) * 255
    k = np.ones((3,3), np.uint8)
    mask = cv2.morphologyEx(cv2.morphologyEx(mask, cv2.MORPH_OPEN, k), cv2.MORPH_CLOSE, k)
    n, labels, stats, cents = cv2.connectedComponentsWithStats(mask, 8)
    best, best_s = None, -1.0
    for lb in range(1, n):
        a = int(stats[lb, cv2.CC_STAT_AREA])
        if a < 4000:
            continue
        comp = (labels == lb).astype(np.uint8)
        cnts, _ = cv2.findContours(comp, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not cnts:
            continue
        p_len = cv2.arcLength(cnts[0], True)
        if p_len <= 0:
            continue
        circ = 4.0 * math.pi * a / (p_len * p_len)
        cx, cy = cents[lb]
        bm = min(cx, cy, img.shape[1]-cx, img.shape[0]-cy)
        s = a * max(circ, 0.05) * max(bm, 1.0)
        if s > best_s:
            best_s, best = s, lb
    if best is None:
        return {"cx": img.shape[1]/2.0, "cy": img.shape[0]/2.0, "peak_r": 500.0, "profile": np.zeros(1)}
    cx, cy = float(cents[best][0]), float(cents[best][1])
    yy, xx = np.indices(img.shape)
    rr = np.sqrt((xx-cx)**2 + (yy-cy)**2)
    ridx = np.floor(rr).astype(np.int32)
    rsum = np.bincount(ridx.ravel(), weights=img.ravel().astype(np.float64))
    rcnt = np.bincount(ridx.ravel())
    profile = rsum / np.maximum(rcnt, 1)
    start = min(10, len(profile)-1)
    peak = int(np.argmax(profile[start:])) + start
    return {"cx": cx, "cy": cy, "peak_r": float(peak), "profile": profile}
```

---

## File Structure

```
輸出結果\驗證分析\R26_validation_complete\
├── R26_完整驗證總報告.md              ← Task 7（手寫）
├── figures\
│   ├── 01_batch_contact_sheet.png    ← Task 0（複製）
│   ├── 02_radial_profile_crosscase.png ← Task 3
│   ├── 03_edge_sharpness_slope.png   ← Task 2
│   ├── 04_ring_roi_metrics.png       ← Task 4
│   ├── 05_batch_metric_heatmap.png   ← Task 5
│   ├── 06_histogram_comparison.png   ← Task 0（複製）
│   ├── 07_frequency_spectrum.png     ← Task 0（複製）
│   ├── 08_ssim_map.png               ← Task 0（複製）
│   ├── 09_mtf_comparison.png         ← Task 0（複製）
│   └── 10_difference_spatial_analysis.png ← Task 0（複製）
└── data\
    ├── batch_metrics.csv             ← Task 0（複製）
    ├── batch_summary.json            ← Task 0（複製）
    ├── basic_metrics.json            ← Task 0（複製）
    ├── ring_geometry_per_image.json  ← Task 1
    ├── ring_analysis_summary.json    ← Task 6
    └── input_integrity_check.json   ← Task 0（複製）

內部檔案\analysis_scripts\
├── step0_setup.py       ← Task 0
├── step1_ring_geom.py   ← Task 1
├── step2_edge_slope.py  ← Task 2
├── step3_radial.py      ← Task 3
├── step4_roi_metrics.py ← Task 4
├── step5_heatmap.py     ← Task 5
└── step6_aggregate.py   ← Task 6
```

---

## Task 0：建立目錄結構並複製精選既有圖表

**Files:**
- Create: `內部檔案\analysis_scripts\step0_setup.py`

- [ ] **Step 1：寫 step0_setup.py**

```python
"""step0_setup.py — 建立輸出目錄並複製精選圖表與資料"""
import shutil
from pathlib import Path

PKG        = Path(r"D:\GMM_2_Final\_deployment_package\GeoEdge_R26_使用包")
DEST       = PKG / "輸出結果" / "驗證分析" / "R26_validation_complete"
SRC_SINGLE = PKG / "輸出結果" / "驗證分析" / "R26_external_single_bundle"
SRC_BATCH  = PKG / "輸出結果" / "驗證分析" / "R26_external_batch_bundle"

(DEST / "figures").mkdir(parents=True, exist_ok=True)
(DEST / "data").mkdir(parents=True, exist_ok=True)

# 複製精選圖表（既有）
copies = [
    (SRC_BATCH  / "batch_contact_sheet.png",         DEST / "figures" / "01_batch_contact_sheet.png"),
    (SRC_SINGLE / "histogram_comparison.png",         DEST / "figures" / "06_histogram_comparison.png"),
    (SRC_SINGLE / "frequency_spectrum_comparison.png",DEST / "figures" / "07_frequency_spectrum.png"),
    (SRC_SINGLE / "ssim_analysis.png",                DEST / "figures" / "08_ssim_map.png"),
    (SRC_SINGLE / "mtf_comparison.png",               DEST / "figures" / "09_mtf_comparison.png"),
    (SRC_SINGLE / "difference_spatial_analysis.png",  DEST / "figures" / "10_difference_spatial_analysis.png"),
]
for src, dst in copies:
    shutil.copy2(src, dst)
    print(f"copied: {dst.name}")

# 複製資料檔
data_copies = [
    (SRC_BATCH  / "batch_metrics.csv",          DEST / "data" / "batch_metrics.csv"),
    (SRC_BATCH  / "batch_summary.json",          DEST / "data" / "batch_summary.json"),
    (SRC_SINGLE / "basic_metrics.json",          DEST / "data" / "basic_metrics.json"),
    (SRC_SINGLE / "input_integrity_check.json",  DEST / "data" / "input_integrity_check.json"),
]
for src, dst in data_copies:
    shutil.copy2(src, dst)
    print(f"copied: {dst.name}")

print("Task 0 完成")
```

- [ ] **Step 2：執行並確認**

```
"D:\GMM_2_Final\_deployment_package\GeoEdge_R26_使用包\內部檔案\portable_runtime\python.exe" "D:\GMM_2_Final\_deployment_package\GeoEdge_R26_使用包\內部檔案\analysis_scripts\step0_setup.py"
```

預期輸出：10 行 `copied: ...` 並顯示「Task 0 完成」

- [ ] **Step 3：確認目錄結構**

```
ls "D:\GMM_2_Final\_deployment_package\GeoEdge_R26_使用包\輸出結果\驗證分析\R26_validation_complete\figures"
```

預期：`01_batch_contact_sheet.png`、`06_histogram_comparison.png` 等 6 個檔案

- [ ] **Step 4：Commit**

```bash
git add 內部檔案/analysis_scripts/step0_setup.py
git commit -m "feat(validation): task0 - setup directory and copy curated figures"
```

---

## Task 1：環形幾何偵測（所有後續模組的前置條件）

**Files:**
- Create: `內部檔案\analysis_scripts\step1_ring_geom.py`
- Output: `輸出結果\驗證分析\R26_validation_complete\data\ring_geometry_per_image.json`

- [ ] **Step 1：寫 step1_ring_geom.py**

```python
"""step1_ring_geom.py — 對 10 張 input BMP 偵測環形幾何，輸出 ring_geometry_per_image.json"""
# [貼入共用工具程式區塊]

PKG    = Path(r"D:\GMM_2_Final\_deployment_package\GeoEdge_R26_使用包")
IN_DIR = PKG / "輸出結果" / "驗證分析" / "R26_external_batch_bundle" / "input_subset"
DEST   = PKG / "輸出結果" / "驗證分析" / "R26_validation_complete"
NAMES  = sorted([f.name for f in IN_DIR.glob("*.bmp")])

results = {}
FALLBACK = {"cx": 773.3, "cy": 1512.3, "peak_r": 539.0}

for name in NAMES:
    img = imread_gray(IN_DIR / name)
    ring = detect_ring(img)

    # 從 radial profile 計算 FWHM
    prof = ring["profile"]
    peak_r = int(ring["peak_r"])
    peak_v = prof[peak_r]
    half_v = peak_v / 2.0
    # 左側半高點
    left = peak_r
    while left > 0 and prof[left] > half_v:
        left -= 1
    # 右側半高點
    right = peak_r
    while right < len(prof)-1 and prof[right] > half_v:
        right += 1
    fwhm = float(right - left)

    results[name] = {
        "cx": ring["cx"],
        "cy": ring["cy"],
        "peak_r": ring["peak_r"],
        "fwhm": fwhm,
    }
    print(f"{name}: cx={ring['cx']:.1f}, cy={ring['cy']:.1f}, r={ring['peak_r']:.1f}, fwhm={fwhm:.1f}")

with open(DEST / "data" / "ring_geometry_per_image.json", "w", encoding="utf-8") as f:
    json.dump(results, f, indent=2, ensure_ascii=False)

print("Task 1 完成 — ring_geometry_per_image.json 已寫入")
```

- [ ] **Step 2：執行**

```
"...\portable_runtime\python.exe" "...\analysis_scripts\step1_ring_geom.py"
```

預期：10 行各圖幾何資訊，peak_r 應在 500–580 範圍，fwhm 應在 80–130 範圍

- [ ] **Step 3：人工確認第一筆是否接近 case 01 已知值**

`basic_metrics.json` 中 case 01 的 peak_radius=539、fwhm=109。
確認 `ring_geometry_per_image.json` 中 VisionTop_20251029182653732.bmp 的 peak_r ≈ 539、fwhm ≈ 109（誤差 ±5 可接受）

- [ ] **Step 4：Commit**

```bash
git add 內部檔案/analysis_scripts/step1_ring_geom.py
git commit -m "feat(validation): task1 - ring geometry detection for all 10 images"
```

---

## Task 2：Module 1 — 邊緣銳利度（Edge Slope + FWHM）

**Files:**
- Create: `內部檔案\analysis_scripts\step2_edge_slope.py`
- Output: `figures\03_edge_sharpness_slope.png`、JSON 寫入 `ring_analysis_summary.json`（暫存於 step2_results.json）

- [ ] **Step 1：寫 step2_edge_slope.py**

```python
"""step2_edge_slope.py — 邊緣最大斜率與 FWHM 分析"""
# [貼入共用工具程式區塊]
from scipy.ndimage import uniform_filter1d

PKG     = Path(r"D:\GMM_2_Final\_deployment_package\GeoEdge_R26_使用包")
IN_DIR  = PKG / "輸出結果" / "驗證分析" / "R26_external_batch_bundle" / "input_subset"
OUT_BMP = PKG / "輸出結果" / "推論結果" / "reconstruct_progress_r26_sm035_best_tradeoff_in_input_subset_20260317_162050"
DEST    = PKG / "輸出結果" / "驗證分析" / "R26_validation_complete"
NAMES   = sorted([f.name for f in IN_DIR.glob("*.bmp")])

with open(DEST / "data" / "ring_geometry_per_image.json", encoding="utf-8") as f:
    GEOM = json.load(f)

def edge_metrics(img, cx, cy, peak_r, fwhm):
    """從徑向 profile 計算邊緣最大斜率與 FWHM"""
    yy, xx = np.indices(img.shape)
    rr = np.sqrt((xx - cx)**2 + (yy - cy)**2)
    ridx = np.floor(rr).astype(np.int32)
    rsum = np.bincount(ridx.ravel(), weights=img.ravel().astype(np.float64))
    rcnt = np.bincount(ridx.ravel())
    profile = rsum / np.maximum(rcnt, 1.0)

    # 平滑後微分
    smooth = uniform_filter1d(profile, size=5)
    grad = np.gradient(smooth)

    r0 = max(0, int(peak_r) - int(fwhm))
    r1 = min(len(grad)-1, int(peak_r) + int(fwhm))
    region = grad[r0:r1]

    max_rising  = float(np.max(region))    # 上升最大斜率
    max_falling = float(abs(np.min(region)))  # 下降最大斜率（取絕對值）

    # FWHM
    peak_v = profile[int(peak_r)]
    half_v = peak_v / 2.0
    left = int(peak_r)
    while left > 0 and profile[left] > half_v:
        left -= 1
    right = int(peak_r)
    while right < len(profile)-1 and profile[right] > half_v:
        right += 1
    fwhm_out = float(right - left)

    return max_rising, max_falling, fwhm_out

results = {}
labels_short = [n[:19] for n in NAMES]  # 短標籤用於圖表

in_rising, out_rising = [], []
in_falling, out_falling = [], []
in_fwhm, out_fwhm = [], []

for name in NAMES:
    g = GEOM[name]
    cx, cy, peak_r, fwhm = g["cx"], g["cy"], g["peak_r"], g["fwhm"]
    img_in  = imread_gray(IN_DIR / name)
    img_out = imread_gray(OUT_BMP / name)
    r1, f1, w1 = edge_metrics(img_in,  cx, cy, peak_r, fwhm)
    r2, f2, w2 = edge_metrics(img_out, cx, cy, peak_r, fwhm)
    in_rising.append(r1);  out_rising.append(r2)
    in_falling.append(f1); out_falling.append(f2)
    in_fwhm.append(w1);    out_fwhm.append(w2)
    results[name] = {
        "input_rising_slope": r1,  "output_rising_slope": r2,
        "slope_improvement_pct": (r2-r1)/r1*100 if r1>0 else 0,
        "input_fwhm": w1, "output_fwhm": w2,
    }
    print(f"{name[:30]}: rising {r1:.3f}→{r2:.3f}, fwhm {w1:.1f}→{w2:.1f}")

# ── 圖表 ──
x = np.arange(len(NAMES))
w = 0.35
fig, axes = plt.subplots(2, 1, figsize=(10, 7), sharex=True)

# 上圖：最大上升斜率（主指標）
axes[0].bar(x - w/2, in_rising,  w, label="Input",  color="#888888")
axes[0].bar(x + w/2, out_rising, w, label="Output", color="#222222")
axes[0].axhline(np.mean(in_rising),  ls="--", lw=1, color="#888888", alpha=0.7)
axes[0].axhline(np.mean(out_rising), ls="--", lw=1, color="#222222", alpha=0.7)
axes[0].set_ylabel("最大上升斜率（灰階/px）")
axes[0].set_title("環邊緣銳利度分析 — 最大上升斜率（主指標）")
axes[0].legend()

# 下圖：FWHM（輔助指標）
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
```

- [ ] **Step 2：執行並確認**

```
"...\portable_runtime\python.exe" "...\analysis_scripts\step2_edge_slope.py"
```

預期：rising slope output 應普遍大於 input（參考 case 01 已知：2.05→5.25）

- [ ] **Step 3：Commit**

```bash
git add 內部檔案/analysis_scripts/step2_edge_slope.py
git commit -m "feat(validation): task2 - edge slope sharpness analysis (module 1)"
```

---

## Task 3：Module 2 — 跨案例徑向輪廓一致性

**Files:**
- Create: `內部檔案\analysis_scripts\step3_radial.py`
- Output: `figures\02_radial_profile_crosscase.png`

- [ ] **Step 1：寫 step3_radial.py**

```python
"""step3_radial.py — 跨 10 案例徑向輪廓對齊與一致性分析"""
# [貼入共用工具程式區塊]

PKG     = Path(r"D:\GMM_2_Final\_deployment_package\GeoEdge_R26_使用包")
IN_DIR  = PKG / "輸出結果" / "驗證分析" / "R26_external_batch_bundle" / "input_subset"
OUT_BMP = PKG / "輸出結果" / "推論結果" / "reconstruct_progress_r26_sm035_best_tradeoff_in_input_subset_20260317_162050"
DEST    = PKG / "輸出結果" / "驗證分析" / "R26_validation_complete"
NAMES   = sorted([f.name for f in IN_DIR.glob("*.bmp")])

with open(DEST / "data" / "ring_geometry_per_image.json", encoding="utf-8") as f:
    GEOM = json.load(f)

HALF_WIN = 100   # 峰值前後各 100px 的窗口
profiles_in, profiles_out = [], []

for name in NAMES:
    g = GEOM[name]
    cx, cy, peak_r = g["cx"], g["cy"], g["peak_r"]

    for img, lst in [(imread_gray(IN_DIR/name), profiles_in),
                     (imread_gray(OUT_BMP/name), profiles_out)]:
        yy, xx = np.indices(img.shape)
        rr = np.sqrt((xx-cx)**2 + (yy-cy)**2)
        ridx = np.floor(rr).astype(np.int32)
        rsum = np.bincount(ridx.ravel(), weights=img.ravel().astype(np.float64))
        rcnt = np.bincount(ridx.ravel())
        profile = rsum / np.maximum(rcnt, 1.0)
        # 以峰值對齊，截取 ±HALF_WIN 窗口
        peak_i = int(peak_r)
        lo, hi = max(0, peak_i-HALF_WIN), min(len(profile), peak_i+HALF_WIN+1)
        seg = profile[lo:hi]
        # 統一長度（長度不足代表環心太靠近影像邊緣，跳過並警告）
        if len(seg) == 2*HALF_WIN+1:
            lst.append(seg)
        else:
            print(f"WARNING: {name} 輪廓窗口長度不足（{len(seg)} < {2*HALF_WIN+1}），已跳過")

profiles_in  = np.array(profiles_in)
profiles_out = np.array(profiles_out)

x_axis = np.arange(-HALF_WIN, HALF_WIN+1)
mean_in,  std_in  = profiles_in.mean(0),  profiles_in.std(0)
mean_out, std_out = profiles_out.mean(0), profiles_out.std(0)

# 一致性指標：std 曲線下面積
auc_in  = float(np.trapz(std_in,  x_axis))
auc_out = float(np.trapz(std_out, x_axis))
improvement = (auc_in - auc_out) / auc_in * 100

print(f"AUC-std  Input: {auc_in:.2f}  Output: {auc_out:.2f}  改善: {improvement:.1f}%")

# ── 圖表 ──
fig, axes = plt.subplots(1, 2, figsize=(12, 5), sharey=True)

for ax, profiles, mean, std, title in [
    (axes[0], profiles_in,  mean_in,  std_in,  "Input（模型輸入）"),
    (axes[1], profiles_out, mean_out, std_out, "Output（R26 輸出）"),
]:
    for p in profiles:
        ax.plot(x_axis, p, color="gray", alpha=0.25, lw=0.8)
    ax.plot(x_axis, mean, color="black", lw=2.0, label="均值")
    ax.fill_between(x_axis, mean-std, mean+std, color="black", alpha=0.15, label="±1 std")
    ax.set_title(title)
    ax.set_xlabel("相對環峰值位置（px）")
    ax.legend(fontsize=10)

axes[0].set_ylabel("灰階強度")
fig.suptitle("跨案例徑向輪廓一致性（n=10）", fontsize=13)

# 加入一致性指標標註
axes[1].text(0.97, 0.05,
    f"AUC-std 改善: {improvement:.1f}%\n(Input:{auc_in:.1f} → Output:{auc_out:.1f})",
    transform=axes[1].transAxes, ha="right", va="bottom", fontsize=9,
    bbox=dict(boxstyle="round,pad=0.3", facecolor="white", edgecolor="gray"))

plt.tight_layout()
fig.savefig(DEST / "figures" / "02_radial_profile_crosscase.png")
plt.close(fig)

# 寫入暫存結果
with open(DEST / "data" / "step3_results.json", "w", encoding="utf-8") as f:
    json.dump({"auc_std_input": auc_in, "auc_std_output": auc_out,
               "consistency_improvement_pct": improvement}, f, indent=2)

n_included = len(profiles_in)
if n_included < 10:
    print(f"WARNING: 僅 {n_included}/10 張圖納入分析（部分圖窗口不足）")
print("Task 3 完成 — 02_radial_profile_crosscase.png 已儲存")
```

- [ ] **Step 2：執行並確認**

```
"...\portable_runtime\python.exe" "...\analysis_scripts\step3_radial.py"
```

預期：output 的 std 帶應明顯窄於 input，AUC-std 改善 > 0%

- [ ] **Step 3：Commit**

```bash
git add 內部檔案/analysis_scripts/step3_radial.py
git commit -m "feat(validation): task3 - cross-case radial profile consistency (module 2)"
```

---

## Task 4：Module 3 — 環 ROI 局部指標

**Files:**
- Create: `內部檔案\analysis_scripts\step4_roi_metrics.py`
- Output: `figures\04_ring_roi_metrics.png`

- [ ] **Step 1：寫 step4_roi_metrics.py**

```python
"""step4_roi_metrics.py — 環形 ROI 內局部指標（SNR、Weber Contrast、Gradient P95）"""
# [貼入共用工具程式區塊]

PKG     = Path(r"D:\GMM_2_Final\_deployment_package\GeoEdge_R26_使用包")
IN_DIR  = PKG / "輸出結果" / "驗證分析" / "R26_external_batch_bundle" / "input_subset"
OUT_BMP = PKG / "輸出結果" / "推論結果" / "reconstruct_progress_r26_sm035_best_tradeoff_in_input_subset_20260317_162050"
DEST    = PKG / "輸出結果" / "驗證分析" / "R26_validation_complete"
NAMES   = sorted([f.name for f in IN_DIR.glob("*.bmp")])

with open(DEST / "data" / "ring_geometry_per_image.json", encoding="utf-8") as f:
    GEOM = json.load(f)

def ring_roi_metrics(img, cx, cy, peak_r, fwhm):
    """計算環形 ROI（radius ± fwhm/2）內的三個指標"""
    yy, xx = np.indices(img.shape)
    rr = np.sqrt((xx-cx)**2 + (yy-cy)**2)
    half_bw = fwhm / 2.0
    roi_mask = (rr >= peak_r - half_bw) & (rr <= peak_r + half_bw)
    roi_vals = img[roi_mask].astype(np.float64)
    if len(roi_vals) == 0:
        return 0.0, 0.0, 0.0

    # SNR：ROI 峰值 / ROI 背景 MAD
    peak_val = float(np.percentile(roi_vals, 95))
    bg_mask  = rr < (peak_r - half_bw * 2)
    bg_vals  = img[bg_mask].astype(np.float64) if bg_mask.any() else roi_vals
    mad = float(np.median(np.abs(bg_vals - np.median(bg_vals)))) * 1.4826
    snr = peak_val / max(mad, 1e-6)

    # Weber Contrast：(環峰值 − 背景均值) / 背景均值
    bg_mean = float(np.mean(bg_vals)) if bg_mask.any() else float(np.mean(roi_vals))
    weber = (peak_val - bg_mean) / max(bg_mean, 1e-6)

    # Gradient P95：ROI 內 Sobel 梯度
    sobel = cv2.Sobel(img, cv2.CV_64F, 1, 0) ** 2 + cv2.Sobel(img, cv2.CV_64F, 0, 1) ** 2
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

# ── 圖表：三行子圖，配對連線 ──
x = np.arange(len(NAMES))
fig, axes = plt.subplots(3, 1, figsize=(10, 10), sharex=True)

for ax, y_in, y_out, ylabel, title in [
    (axes[0], in_snr,   out_snr,   "SNR",              "環 ROI 訊號雜訊比（SNR）"),
    (axes[1], in_weber, out_weber, "Weber Contrast",   "環 ROI Weber 對比"),
    (axes[2], in_grad,  out_grad,  "梯度 P95",         "環 ROI Sobel 梯度 P95"),
]:
    for i in range(len(NAMES)):
        color = "#2ecc71" if y_out[i] >= y_in[i] else "#e74c3c"
        ax.plot([x[i]-0.15, x[i]+0.15], [y_in[i], y_out[i]],
                color=color, lw=1.5, alpha=0.7)
        ax.scatter(x[i]-0.15, y_in[i],  s=40, color="gray",  zorder=3)
        ax.scatter(x[i]+0.15, y_out[i], s=40, color="black", zorder=3)
    ax.set_ylabel(ylabel)
    ax.set_title(title)

axes[2].set_xticks(x)
axes[2].set_xticklabels([n[10:29] for n in NAMES], rotation=45, ha="right", fontsize=9)

# 圖例（只在第一個子圖加）
from matplotlib.lines import Line2D
axes[0].legend(handles=[
    Line2D([0],[0], color="gray",  marker="o", ms=5, label="Input"),
    Line2D([0],[0], color="black", marker="o", ms=5, label="Output"),
], loc="upper right")

fig.suptitle("環形 ROI 局部品質指標（n=10）", fontsize=13)
plt.tight_layout()
fig.savefig(DEST / "figures" / "04_ring_roi_metrics.png")
plt.close(fig)

with open(DEST / "data" / "step4_results.json", "w", encoding="utf-8") as f:
    json.dump(results, f, indent=2, ensure_ascii=False)

print("Task 4 完成 — 04_ring_roi_metrics.png 已儲存")
```

- [ ] **Step 2：執行並確認**

```
"...\portable_runtime\python.exe" "...\analysis_scripts\step4_roi_metrics.py"
```

預期：SNR 和 Weber contrast 的 output 應普遍高於 input（綠色連線為多數）

- [ ] **Step 3：Commit**

```bash
git add 內部檔案/analysis_scripts/step4_roi_metrics.py
git commit -m "feat(validation): task4 - ring ROI local metrics (module 3)"
```

---

## Task 5：Module 4 — 批次指標熱圖

**Files:**
- Create: `內部檔案\analysis_scripts\step5_heatmap.py`
- Output: `figures\05_batch_metric_heatmap.png`

- [ ] **Step 1：寫 step5_heatmap.py**

```python
"""step5_heatmap.py — 10 案例 × 6 指標改善幅度熱圖"""
# [貼入共用工具程式區塊]
import csv

PKG   = Path(r"D:\GMM_2_Final\_deployment_package\GeoEdge_R26_使用包")
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
```

- [ ] **Step 2：執行並確認**

```
"...\portable_runtime\python.exe" "...\analysis_scripts\step5_heatmap.py"
```

預期：熱圖藍色格應占多數（改善），梯度比值和熵的格應反轉為藍（值<1、<0 代表改善）

- [ ] **Step 3：Commit**

```bash
git add 內部檔案/analysis_scripts/step5_heatmap.py
git commit -m "feat(validation): task5 - batch metric heatmap (module 4)"
```

---

## Task 6：彙總 ring_analysis_summary.json

**Files:**
- Create: `內部檔案\analysis_scripts\step6_aggregate.py`
- Output: `data\ring_analysis_summary.json`

- [ ] **Step 1：寫 step6_aggregate.py**

```python
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
```

- [ ] **Step 2：執行**

```
"...\portable_runtime\python.exe" "...\analysis_scripts\step6_aggregate.py"
```

預期：列印三個模組的彙總數字

- [ ] **Step 3：Commit**

```bash
git add 內部檔案/analysis_scripts/step6_aggregate.py
git commit -m "feat(validation): task6 - aggregate ring_analysis_summary.json"
```

---

## Task 7：撰寫 R26_完整驗證總報告.md

**Files:**
- Create: `輸出結果\驗證分析\R26_validation_complete\R26_完整驗證總報告.md`

此 markdown 由 Codex 依據所有已產生數字撰寫，**不手寫**。

- [ ] **Step 1：讀取所有數字後撰寫報告**

讀取以下文件獲取所有數值，填入報告：
- `data\ring_analysis_summary.json`（Module 1-3 數字）
- `data\batch_summary.json`（批次統計）
- `data\basic_metrics.json`（單圖統計）
- `R26_OBJECTIVE_VALIDATION_ANALYSIS_20260324.md`（GMF 外部比較數字）

報告結構照設計規格中的章節架構（第 1–8 章），每個圖以 `![圖說](figures/XX_name.png)` 語法嵌入。

- [ ] **Step 2：確認報告引用的每個數字都有對應 JSON 來源**

每個關鍵數字旁標記來源，例如：
- `環峰值對比增益：+21.95 灰階（來源：batch_summary.json）`
- `邊緣斜率改善均值：XX%（來源：ring_analysis_summary.json）`

- [ ] **Step 3：最終 Commit**

```bash
git add .
git commit -m "feat(validation): task7 - complete R26 validation bundle with ring analysis"
```

---

## 驗收清單

執行完所有 Task 後，確認：

- [ ] `R26_validation_complete\figures\` 內有 10 張圖（01–10）
- [ ] `R26_validation_complete\data\` 內有 6 個檔案（含 `ring_analysis_summary.json`）
- [ ] `ring_analysis_summary.json` 中 module1 均值改善 > 0%
- [ ] `02_radial_profile_crosscase.png` output 組的 std 帶明顯窄於 input
- [ ] `04_ring_roi_metrics.png` 大多數連線為綠色（SNR/Weber 改善）
- [ ] `05_batch_metric_heatmap.png` 藍色格佔多數
- [ ] `R26_完整驗證總報告.md` 能獨立閱讀（含所有圖表嵌入與數字來源）

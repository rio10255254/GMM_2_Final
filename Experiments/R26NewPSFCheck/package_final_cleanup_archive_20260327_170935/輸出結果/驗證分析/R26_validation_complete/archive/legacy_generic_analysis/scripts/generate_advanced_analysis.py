"""
R26 Advanced Validation Analysis — Professional Image Processing Perspectives
==============================================================================
Complete rewrite with polished figures, Chinese titles, and robust metrics.

Analysis dimensions:
1. SSIM (Structural Similarity — Wang et al. 2004)
2. MTF  (Modulation Transfer Function — optical resolution)
3. SNR  (Signal-to-Noise Ratio — Donoho-Johnstone MAD)
4. ESF / LSF (Edge / Line Spread Function)
5. Wavelet Multi-Scale Decomposition (Haar)
6. GLCM Texture Analysis (Haralick 1973)
7. Local Contrast Mapping (Weber / Michelson)
8. Difference Image Spatial Analysis
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

import cv2
import matplotlib
import numpy as np

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.gridspec import GridSpec
PROJECT_ROOT = Path(__file__).resolve().parents[9]

# ── Global plot style with CJK font ───────────────────────────────
plt.rcParams.update({
    "font.family": "sans-serif",
    "font.sans-serif": ["Microsoft JhengHei", "Microsoft YaHei", "SimHei",
                         "Noto Sans CJK TC", "DejaVu Sans"],
    "axes.unicode_minus": False,
    "font.size": 13,
    "axes.titlesize": 14,
    "axes.labelsize": 12,
    "xtick.labelsize": 11,
    "ytick.labelsize": 11,
    "legend.fontsize": 11,
    "figure.dpi": 170,
    "savefig.bbox": "tight",
    "savefig.pad_inches": 0.15,
})

# ── Paths ──────────────────────────────────────────────────────────
BUNDLE = Path(
    str(PROJECT_ROOT / '_deployment_package/GeoEdge_R26_使用包/輸出結果/驗證分析/R26_external_single_bundle')
)
INPUT_PATH = BUNDLE / "input_image.bmp"
OUTPUT_PATH = BUNDLE / "model_output.bmp"


def imread_gray(p: Path) -> np.ndarray:
    arr = np.fromfile(p, dtype=np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_GRAYSCALE)
    if img is None:
        raise FileNotFoundError(p)
    return img


# ===================================================================
# Ring detection (shared utility)
# ===================================================================
def detect_ring(img: np.ndarray) -> dict:
    blur = cv2.GaussianBlur(img, (0, 0), 3.0)
    otsu, _ = cv2.threshold(blur, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    pct = np.percentile(blur, 85)
    mask = (blur >= int(max(otsu, pct))).astype(np.uint8) * 255
    k = np.ones((3, 3), np.uint8)
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
        p = cv2.arcLength(cnts[0], True)
        if p <= 0:
            continue
        circ = 4.0 * math.pi * a / (p * p)
        cx, cy = cents[lb]
        bm = min(cx, cy, img.shape[1] - cx, img.shape[0] - cy)
        s = a * max(circ, 0.05) * max(bm, 1.0)
        if s > best_s:
            best_s, best = s, lb
    if best is None:
        return {"cx": img.shape[1] / 2.0, "cy": img.shape[0] / 2.0, "peak_r": 500.0, "profile": np.zeros(1)}
    cx, cy = float(cents[best][0]), float(cents[best][1])
    yy, xx = np.indices(img.shape)
    rr = np.sqrt((xx - cx) ** 2 + (yy - cy) ** 2)
    ridx = np.floor(rr).astype(np.int32)
    rsum = np.bincount(ridx.ravel(), weights=img.ravel().astype(np.float64))
    rcnt = np.bincount(ridx.ravel())
    profile = rsum / np.maximum(rcnt, 1)
    start = min(10, len(profile) - 1)
    peak = int(np.argmax(profile[start:])) + start
    return {"cx": cx, "cy": cy, "peak_r": float(peak), "profile": profile}


# ===================================================================
# 1. SSIM
# ===================================================================
def compute_ssim(img1: np.ndarray, img2: np.ndarray, k: int = 11):
    C1, C2 = (0.01 * 255) ** 2, (0.03 * 255) ** 2
    f1, f2 = img1.astype(np.float64), img2.astype(np.float64)
    mu1 = cv2.GaussianBlur(f1, (k, k), 1.5)
    mu2 = cv2.GaussianBlur(f2, (k, k), 1.5)
    s1sq = cv2.GaussianBlur(f1 * f1, (k, k), 1.5) - mu1 * mu1
    s2sq = cv2.GaussianBlur(f2 * f2, (k, k), 1.5) - mu2 * mu2
    s12 = cv2.GaussianBlur(f1 * f2, (k, k), 1.5) - mu1 * mu2
    smap = ((2 * mu1 * mu2 + C1) * (2 * s12 + C2)) / ((mu1**2 + mu2**2 + C1) * (s1sq + s2sq + C2))
    # decompose
    C3 = C2 / 2
    gmu1, gmu2 = f1.mean(), f2.mean()
    gs1, gs2 = f1.std(), f2.std()
    gcov = float(((f1 - gmu1) * (f2 - gmu2)).mean())
    L = (2 * gmu1 * gmu2 + C1) / (gmu1**2 + gmu2**2 + C1)
    C = (2 * gs1 * gs2 + C2) / (gs1**2 + gs2**2 + C2)
    S = (gcov + C3) / (gs1 * gs2 + C3)
    return float(smap.mean()), smap, {"luminance": float(L), "contrast": float(C), "structure": float(S)}


def plot_ssim(smap, mean_ssim, path):
    fig, axes = plt.subplots(1, 2, figsize=(13, 5.5))
    im = axes[0].imshow(smap, cmap="RdYlGn", vmin=0.65, vmax=1.0)
    axes[0].set_title(f"局部 SSIM 空間分布圖  (均值 = {mean_ssim:.4f})")
    axes[0].axis("off")
    fig.colorbar(im, ax=axes[0], fraction=0.046, pad=0.04, label="SSIM")
    axes[1].hist(smap.ravel(), bins=250, density=True, color="steelblue", edgecolor="none", alpha=0.85)
    axes[1].axvline(mean_ssim, color="red", linestyle="--", lw=1.8, label=f"均值 = {mean_ssim:.4f}")
    p5 = float(np.percentile(smap, 5))
    axes[1].axvline(p5, color="orange", linestyle=":", lw=1.5, label=f"P5 = {p5:.4f}")
    axes[1].set_title("SSIM 值分布直方圖")
    axes[1].set_xlabel("SSIM 值")
    axes[1].set_ylabel("密度")
    axes[1].legend(loc="upper left")
    axes[1].grid(alpha=0.25)
    fig.suptitle("圖 1 — 結構相似性 (SSIM) 分析", fontsize=15, fontweight="bold", y=1.01)
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


# ===================================================================
# 2. MTF (smoothed)
# ===================================================================
def esf_to_mtf(profile: np.ndarray, smooth_sigma: float = 3.0):
    """ESF → smoothed LSF → MTF."""
    from scipy.ndimage import gaussian_filter1d
    esf = profile.astype(np.float64)
    esf = (esf - esf.min()) / max(esf.max() - esf.min(), 1e-9)
    lsf = np.gradient(esf)
    lsf = gaussian_filter1d(lsf, sigma=smooth_sigma)
    n = max(len(lsf) * 8, 2048)
    mtf = np.abs(np.fft.rfft(lsf, n=n))
    mtf = mtf / max(mtf[0], 1e-9)
    freq = np.fft.rfftfreq(n, d=1.0)
    return freq, mtf, lsf


def mtf_cutoff(freq, mtf, level):
    idx = np.where(mtf <= level)[0]
    return float(freq[idx[0]]) if len(idx) > 0 else None


def plot_mtf(fi, mi, fo, mo, si, so, path):
    fig, axes = plt.subplots(1, 2, figsize=(14, 5.5))
    fmax = 0.5
    # left: MTF
    ax = axes[0]
    mask_i, mask_o = fi <= fmax, fo <= fmax
    ax.plot(fi[mask_i], mi[mask_i], label="輸入", lw=2, alpha=0.9)
    ax.plot(fo[mask_o], mo[mask_o], label="輸出", lw=2, alpha=0.9)
    ax.axhline(0.5, color="gray", ls=":", alpha=0.5)
    ax.axhline(0.1, color="gray", ls="--", alpha=0.3)
    ax.text(0.42, 0.52, "MTF50", fontsize=9, color="gray")
    ax.text(0.42, 0.12, "MTF10", fontsize=9, color="gray")
    for s, c in [(si, "tab:blue"), (so, "tab:orange")]:
        if s["mtf50"]:
            ax.axvline(s["mtf50"], color=c, ls=":", alpha=0.6, lw=1.2)
    ax.set_title("MTF 曲線對比 (由環邊緣徑向輪廓估算)")
    ax.set_xlabel("空間頻率 (cycles/pixel)")
    ax.set_ylabel("歸一化 MTF")
    ax.set_xlim(0, fmax)
    ax.set_ylim(0, 1.05)
    ax.legend()
    ax.grid(alpha=0.25)
    # right: table
    ax2 = axes[1]
    ax2.axis("off")
    rows = [
        ["MTF50 (cycles/px)", f"{si['mtf50']:.6f}" if si["mtf50"] else "N/A",
         f"{so['mtf50']:.6f}" if so["mtf50"] else "N/A"],
        ["MTF10 (cycles/px)", f"{si['mtf10']:.6f}" if si["mtf10"] else "N/A",
         f"{so['mtf10']:.6f}" if so["mtf10"] else "N/A"],
    ]
    tbl = ax2.table(cellText=rows, colLabels=["指標", "輸入", "輸出"],
                    loc="center", cellLoc="center")
    tbl.auto_set_font_size(False)
    tbl.set_fontsize(12)
    tbl.scale(1.0, 2.0)
    for (r, c), cell in tbl.get_celld().items():
        if r == 0:
            cell.set_facecolor("#4472C4")
            cell.set_text_props(color="white", fontweight="bold")
        cell.set_edgecolor("#cccccc")
    ax2.set_title("MTF 截止頻率摘要", pad=20)
    fig.suptitle("圖 2 — 調變傳遞函數 (MTF) 分析", fontsize=15, fontweight="bold", y=1.01)
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


# ===================================================================
# 3. SNR
# ===================================================================
def noise_std_mad(img: np.ndarray) -> float:
    lap = cv2.Laplacian(img.astype(np.float64), cv2.CV_64F, ksize=3)
    med = float(np.median(np.abs(lap)))
    return med / 0.6745 if med > 0 else float(np.std(lap)) / 20.0  # fallback


def snr_metrics(img: np.ndarray) -> dict:
    ns = noise_std_mad(img)
    mu = float(img.astype(np.float64).mean())
    sig = float(img.astype(np.float64).std())
    # cap SNR to avoid infinity
    snr_m = min(20 * math.log10(mu / max(ns, 1e-3)), 80.0)
    snr_s = min(20 * math.log10(sig / max(ns, 1e-3)), 80.0)
    return {"noise_std": round(ns, 4), "signal_mean": round(mu, 4),
            "signal_std": round(sig, 4), "snr_mean_dB": round(snr_m, 2),
            "snr_std_dB": round(snr_s, 2)}


def local_snr_map(img: np.ndarray, blk: int = 32) -> np.ndarray:
    f = img.astype(np.float64)
    h, w = f.shape
    R, C = h // blk, w // blk
    m = np.zeros((R, C))
    for r in range(R):
        for c in range(C):
            p = f[r*blk:(r+1)*blk, c*blk:(c+1)*blk]
            m[r, c] = p.mean() / max(p.std(), 1e-3)
    return m


def plot_snr(si, so, mi, mo, path):
    fig, axes = plt.subplots(2, 3, figsize=(15, 9))
    # Top row: local SNR maps
    vmax = float(np.percentile(np.concatenate([mi.ravel(), mo.ravel()]), 97))
    im0 = axes[0, 0].imshow(mi, cmap="viridis", vmin=0, vmax=vmax)
    axes[0, 0].set_title("輸入 — 局部 SNR 分布")
    axes[0, 0].axis("off")
    fig.colorbar(im0, ax=axes[0, 0], fraction=0.046, pad=0.04)

    im1 = axes[0, 1].imshow(mo, cmap="viridis", vmin=0, vmax=vmax)
    axes[0, 1].set_title("輸出 — 局部 SNR 分布")
    axes[0, 1].axis("off")
    fig.colorbar(im1, ax=axes[0, 1], fraction=0.046, pad=0.04)

    diff = mo - mi
    vabs = max(abs(float(np.percentile(diff, 3))), abs(float(np.percentile(diff, 97))))
    im2 = axes[0, 2].imshow(diff, cmap="coolwarm", vmin=-vabs, vmax=vabs)
    axes[0, 2].set_title("SNR 變化量 (輸出 − 輸入)")
    axes[0, 2].axis("off")
    fig.colorbar(im2, ax=axes[0, 2], fraction=0.046, pad=0.04)

    # Bottom row: distributions + summary table
    axes[1, 0].hist(mi.ravel(), bins=80, density=True, alpha=0.7, color="steelblue", label="輸入")
    axes[1, 0].hist(mo.ravel(), bins=80, density=True, alpha=0.7, color="coral", label="輸出")
    axes[1, 0].set_title("局部 SNR 值分布")
    axes[1, 0].set_xlabel("SNR (均值/標準差)")
    axes[1, 0].set_ylabel("密度")
    axes[1, 0].legend()
    axes[1, 0].grid(alpha=0.25)

    axes[1, 1].hist(diff.ravel(), bins=80, density=True, color="mediumpurple", edgecolor="none")
    axes[1, 1].axvline(0, color="red", ls="--", lw=1.2)
    axes[1, 1].set_title("局部 SNR 變化量分布")
    axes[1, 1].set_xlabel("ΔSNR")
    axes[1, 1].set_ylabel("密度")
    axes[1, 1].grid(alpha=0.25)

    ax_t = axes[1, 2]
    ax_t.axis("off")
    rows = [
        ["雜訊標準差 (MAD)", f"{si['noise_std']:.4f}", f"{so['noise_std']:.4f}"],
        ["SNR (mean, dB)", f"{si['snr_mean_dB']:.2f}", f"{so['snr_mean_dB']:.2f}"],
        ["SNR (std, dB)", f"{si['snr_std_dB']:.2f}", f"{so['snr_std_dB']:.2f}"],
    ]
    tbl = ax_t.table(cellText=rows, colLabels=["指標", "輸入", "輸出"],
                     loc="center", cellLoc="center")
    tbl.auto_set_font_size(False)
    tbl.set_fontsize(12)
    tbl.scale(1.0, 2.2)
    for (r, c), cell in tbl.get_celld().items():
        if r == 0:
            cell.set_facecolor("#4472C4")
            cell.set_text_props(color="white", fontweight="bold")
        cell.set_edgecolor("#cccccc")
    ax_t.set_title("全域 SNR 摘要", pad=20)

    fig.suptitle("圖 3 — 信噪比 (SNR) 分析", fontsize=15, fontweight="bold", y=1.01)
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


# ===================================================================
# 4. ESF / LSF
# ===================================================================
def extract_esf(img, cx, cy, peak_r, width=80):
    yy, xx = np.indices(img.shape)
    rr = np.sqrt((xx - cx) ** 2 + (yy - cy) ** 2)
    bins = np.arange(int(peak_r - width), int(peak_r + width) + 1)
    esf = np.zeros(len(bins) - 1)
    for i in range(len(bins) - 1):
        sel = (rr >= bins[i]) & (rr < bins[i + 1])
        if sel.any():
            esf[i] = img[sel].astype(np.float64).mean()
    return esf, bins[:-1]


def plot_esf_lsf(esf_in, esf_out, bins_in, bins_out, path):
    # Normalize for LSF comparison
    def norm(e):
        return (e - e.min()) / max(e.max() - e.min(), 1e-9)
    n_in, n_out = norm(esf_in), norm(esf_out)
    lsf_in, lsf_out = np.gradient(n_in), np.gradient(n_out)

    fig, axes = plt.subplots(1, 3, figsize=(16, 5))
    # ESF (raw values)
    axes[0].plot(bins_in, esf_in, lw=2, label="輸入", color="steelblue")
    axes[0].plot(bins_out, esf_out, lw=2, label="輸出", color="coral")
    axes[0].set_title("邊緣擴散函數 (ESF)")
    axes[0].set_xlabel("徑向位置 (像素)")
    axes[0].set_ylabel("平均灰階值")
    axes[0].legend()
    axes[0].grid(alpha=0.25)
    # ESF normalized
    axes[1].plot(bins_in, n_in, lw=2, label="輸入 (歸一化)", color="steelblue")
    axes[1].plot(bins_out, n_out, lw=2, label="輸出 (歸一化)", color="coral")
    axes[1].set_title("歸一化 ESF")
    axes[1].set_xlabel("徑向位置 (像素)")
    axes[1].set_ylabel("歸一化強度")
    axes[1].legend()
    axes[1].grid(alpha=0.25)
    # LSF
    axes[2].plot(bins_in, lsf_in, lw=2, label="輸入 LSF", color="steelblue")
    axes[2].plot(bins_out, lsf_out, lw=2, label="輸出 LSF", color="coral")
    axes[2].set_title("線擴散函數 (LSF)")
    axes[2].set_xlabel("徑向位置 (像素)")
    axes[2].set_ylabel("歸一化梯度")
    axes[2].legend()
    axes[2].grid(alpha=0.25)

    fig.suptitle("圖 4 — 邊緣擴散函數 (ESF) 與線擴散函數 (LSF) 分析", fontsize=15, fontweight="bold", y=1.01)
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


# ===================================================================
# 5. Wavelet
# ===================================================================
def haar_decompose(img, levels=4):
    f = img.astype(np.float64)
    results = []
    for lv in range(levels):
        h, w = f.shape
        if h < 4 or w < 4:
            break
        h2, w2 = h // 2 * 2, w // 2 * 2
        f = f[:h2, :w2]
        lo = (f[:, 0::2] + f[:, 1::2]) / 2.0
        hi = (f[:, 0::2] - f[:, 1::2]) / 2.0
        ll = (lo[0::2, :] + lo[1::2, :]) / 2.0
        lh = (lo[0::2, :] - lo[1::2, :]) / 2.0
        hl = (hi[0::2, :] + hi[1::2, :]) / 2.0
        hh = (hi[0::2, :] - hi[1::2, :]) / 2.0
        total = float(f.size) * max(float((f ** 2).mean()), 1e-12)
        lh_e, hl_e, hh_e = float((lh**2).sum()), float((hl**2).sum()), float((hh**2).sum())
        results.append({
            "level": lv + 1, "ll": float((ll**2).sum()),
            "lh": lh_e, "hl": hl_e, "hh": hh_e,
            "detail_ratio": (lh_e + hl_e + hh_e) / total,
        })
        f = ll
    return results


def plot_wavelet(wi, wo, path):
    fig, axes = plt.subplots(1, 3, figsize=(16, 5))
    levels = [d["level"] for d in wi]
    x = np.arange(len(levels))
    w = 0.35

    # Detail energy ratio
    dr_in = [d["detail_ratio"] for d in wi]
    dr_out = [d["detail_ratio"] for d in wo]
    axes[0].bar(x - w/2, dr_in, w, label="輸入", color="steelblue")
    axes[0].bar(x + w/2, dr_out, w, label="輸出", color="coral")
    axes[0].set_xticks(x)
    axes[0].set_xticklabels([f"Level {l}" for l in levels])
    axes[0].set_title("各層級細節能量比")
    axes[0].set_ylabel("Detail / Total")
    axes[0].legend()
    axes[0].grid(alpha=0.25, axis="y")
    axes[0].ticklabel_format(axis="y", style="sci", scilimits=(-4, -4))

    # Level-1 sub-band
    bands_in = [wi[0]["lh"], wi[0]["hl"], wi[0]["hh"]]
    bands_out = [wo[0]["lh"], wo[0]["hl"], wo[0]["hh"]]
    ti, to = sum(bands_in) or 1, sum(bands_out) or 1
    x2 = np.arange(3)
    axes[1].bar(x2 - w/2, [v/ti for v in bands_in], w, label="輸入", color="steelblue")
    axes[1].bar(x2 + w/2, [v/to for v in bands_out], w, label="輸出", color="coral")
    axes[1].set_xticks(x2)
    axes[1].set_xticklabels(["LH\n(水平邊緣)", "HL\n(垂直邊緣)", "HH\n(對角邊緣)"])
    axes[1].set_title("Level-1 方向性子帶能量分布")
    axes[1].set_ylabel("歸一化能量")
    axes[1].legend()
    axes[1].grid(alpha=0.25, axis="y")

    # Input vs output ratio (log scale)
    ratios = []
    for i, o in zip(wi, wo):
        if i["detail_ratio"] > 0:
            ratios.append(o["detail_ratio"] / i["detail_ratio"])
        else:
            ratios.append(1.0)
    colors = ["#2ecc71" if r < 1 else "#e74c3c" for r in ratios]
    axes[2].bar(x, ratios, 0.5, color=colors)
    axes[2].axhline(1.0, color="gray", ls="--", lw=1.2, alpha=0.7)
    axes[2].set_xticks(x)
    axes[2].set_xticklabels([f"Level {l}" for l in levels])
    axes[2].set_title("細節能量比變化倍率 (輸出/輸入)")
    axes[2].set_ylabel("倍率")
    axes[2].set_yscale("log")
    axes[2].grid(alpha=0.25, axis="y")
    axes[2].text(0.02, 0.92, "綠 = 細節能量下降 (降噪)\n紅 = 細節能量上升 (強化)",
                 transform=axes[2].transAxes, fontsize=9, va="top",
                 bbox=dict(boxstyle="round,pad=0.3", facecolor="white", alpha=0.8))

    fig.suptitle("圖 5 — 小波多尺度分解分析 (Haar)", fontsize=15, fontweight="bold", y=1.01)
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


# ===================================================================
# 6. GLCM
# ===================================================================
def compute_glcm(img, levels=64, distances=None):
    if distances is None:
        distances = [1, 3, 5]
    q = np.clip((img.astype(np.float64) / 256.0 * levels).astype(np.int32), 0, levels - 1)
    h, w = q.shape
    feats = {k: [] for k in ["contrast", "dissimilarity", "homogeneity", "energy", "correlation", "entropy"]}
    for d in distances:
        g = np.zeros((levels, levels), np.float64)
        for r in range(h):
            for c in range(w - d):
                i, j = q[r, c], q[r, c + d]
                g[i, j] += 1; g[j, i] += 1
        t = g.sum()
        if t > 0:
            g /= t
        ii, jj = np.meshgrid(np.arange(levels), np.arange(levels), indexing="ij")
        df = np.abs(ii - jj).astype(np.float64)
        feats["contrast"].append(float((g * df**2).sum()))
        feats["dissimilarity"].append(float((g * df).sum()))
        feats["homogeneity"].append(float((g / (1.0 + df)).sum()))
        feats["energy"].append(float((g**2).sum()))
        nz = g[g > 0]
        feats["entropy"].append(float(-(nz * np.log2(nz)).sum()))
        mi = float((ii * g).sum()); mj = float((jj * g).sum())
        si = math.sqrt(max(float(((ii - mi)**2 * g).sum()), 1e-12))
        sj = math.sqrt(max(float(((jj - mj)**2 * g).sum()), 1e-12))
        feats["correlation"].append(float(((ii - mi) * (jj - mj) * g).sum() / (si * sj)))
    return {"distances": distances, **{k: [round(v, 6) for v in vs] for k, vs in feats.items()}}


def plot_glcm(gi, go, path):
    dists = gi["distances"]
    metrics = ["contrast", "dissimilarity", "homogeneity", "energy", "correlation", "entropy"]
    titles_zh = ["Contrast\n(對比度)", "Dissimilarity\n(差異性)", "Homogeneity\n(均勻性)",
                 "Energy\n(能量/ASM)", "Correlation\n(相關性)", "Entropy\n(熵)"]

    fig, axes = plt.subplots(2, 3, figsize=(16, 9))
    axes = axes.flatten()
    w = 0.25
    for idx, (met, tzh) in enumerate(zip(metrics, titles_zh)):
        ax = axes[idx]
        x = np.arange(len(dists))
        vi = gi[met]
        vo = go[met]
        ax.bar(x - w/2, vi, w, label="輸入", color="steelblue")
        ax.bar(x + w/2, vo, w, label="輸出", color="coral")
        ax.set_xticks(x)
        ax.set_xticklabels([f"d={d}" for d in dists])
        ax.set_title(tzh)
        ax.legend(fontsize=9)
        ax.grid(alpha=0.25, axis="y")
        # Annotate values
        for i, (v1, v2) in enumerate(zip(vi, vo)):
            ax.text(i - w/2, v1, f"{v1:.3f}", ha="center", va="bottom", fontsize=8)
            ax.text(i + w/2, v2, f"{v2:.3f}", ha="center", va="bottom", fontsize=8)

    fig.suptitle("圖 6 — GLCM 紋理特徵分析 (Haralick, 1973)", fontsize=15, fontweight="bold", y=1.01)
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


# ===================================================================
# 7. Local Contrast
# ===================================================================
def local_contrast_maps(img, blk=32):
    f = img.astype(np.float64)
    h, w = f.shape
    R, C = h // blk, w // blk
    weber, michel = np.zeros((R, C)), np.zeros((R, C))
    for r in range(R):
        for c in range(C):
            p = f[r*blk:(r+1)*blk, c*blk:(c+1)*blk]
            mn, mx, mu = p.min(), p.max(), p.mean()
            weber[r, c] = (mx - mu) / max(mu, 1e-9)
            michel[r, c] = (mx - mn) / max(mx + mn, 1e-9)
    return weber, michel


def lc_stats(m, name):
    return {f"{name}_mean": round(float(m.mean()), 6), f"{name}_std": round(float(m.std()), 6),
            f"{name}_p05": round(float(np.percentile(m, 5)), 6),
            f"{name}_p50": round(float(np.percentile(m, 50)), 6),
            f"{name}_p95": round(float(np.percentile(m, 95)), 6)}


def plot_local_contrast(wi, wo, mi, mo, path):
    fig, axes = plt.subplots(2, 4, figsize=(18, 9))

    # Weber row
    vmax_w = max(float(np.percentile(wi, 97)), float(np.percentile(wo, 97)))
    im00 = axes[0, 0].imshow(wi, cmap="inferno", vmin=0, vmax=vmax_w)
    axes[0, 0].set_title("輸入 Weber Contrast")
    fig.colorbar(im00, ax=axes[0, 0], fraction=0.046)
    im01 = axes[0, 1].imshow(wo, cmap="inferno", vmin=0, vmax=vmax_w)
    axes[0, 1].set_title("輸出 Weber Contrast")
    fig.colorbar(im01, ax=axes[0, 1], fraction=0.046)
    dw = wo - wi
    va_w = max(abs(float(np.percentile(dw, 3))), abs(float(np.percentile(dw, 97))))
    im02 = axes[0, 2].imshow(dw, cmap="coolwarm", vmin=-va_w, vmax=va_w)
    axes[0, 2].set_title("Weber 變化量")
    fig.colorbar(im02, ax=axes[0, 2], fraction=0.046)
    # Weber histogram
    axes[0, 3].hist(wi.ravel(), bins=60, density=True, alpha=0.7, color="steelblue", label="輸入")
    axes[0, 3].hist(wo.ravel(), bins=60, density=True, alpha=0.7, color="coral", label="輸出")
    axes[0, 3].set_title("Weber 分布")
    axes[0, 3].legend(fontsize=9)
    axes[0, 3].grid(alpha=0.25)

    # Michelson row
    vmax_m = max(float(np.percentile(mi, 97)), float(np.percentile(mo, 97)))
    im10 = axes[1, 0].imshow(mi, cmap="inferno", vmin=0, vmax=vmax_m)
    axes[1, 0].set_title("輸入 Michelson Contrast")
    fig.colorbar(im10, ax=axes[1, 0], fraction=0.046)
    im11 = axes[1, 1].imshow(mo, cmap="inferno", vmin=0, vmax=vmax_m)
    axes[1, 1].set_title("輸出 Michelson Contrast")
    fig.colorbar(im11, ax=axes[1, 1], fraction=0.046)
    dm = mo - mi
    va_m = max(abs(float(np.percentile(dm, 3))), abs(float(np.percentile(dm, 97))))
    im12 = axes[1, 2].imshow(dm, cmap="coolwarm", vmin=-va_m, vmax=va_m)
    axes[1, 2].set_title("Michelson 變化量")
    fig.colorbar(im12, ax=axes[1, 2], fraction=0.046)
    axes[1, 3].hist(mi.ravel(), bins=60, density=True, alpha=0.7, color="steelblue", label="輸入")
    axes[1, 3].hist(mo.ravel(), bins=60, density=True, alpha=0.7, color="coral", label="輸出")
    axes[1, 3].set_title("Michelson 分布")
    axes[1, 3].legend(fontsize=9)
    axes[1, 3].grid(alpha=0.25)

    for r in range(2):
        for c in range(3):
            axes[r, c].axis("off")

    fig.suptitle("圖 7 — 局部對比分析 (Weber / Michelson)", fontsize=15, fontweight="bold", y=1.01)
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


# ===================================================================
# 8. Difference Image Spatial Analysis
# ===================================================================
def diff_metrics(inp, out):
    d = out.astype(np.float64) - inp.astype(np.float64)
    ad = np.abs(d)
    std = max(d.std(), 1e-9)
    return {
        "mean": round(float(d.mean()), 4),
        "std": round(float(d.std()), 4),
        "skewness": round(float(((d - d.mean())**3).mean() / std**3), 4),
        "kurtosis": round(float(((d - d.mean())**4).mean() / std**4 - 3.0), 4),
        "abs_p50": round(float(np.percentile(ad, 50)), 2),
        "abs_p90": round(float(np.percentile(ad, 90)), 2),
        "abs_p99": round(float(np.percentile(ad, 99)), 2),
        "pos_ratio": round(float((d > 0).sum() / d.size), 4),
        "neg_ratio": round(float((d < 0).sum() / d.size), 4),
        "zero_ratio": round(float((d == 0).sum() / d.size), 4),
    }


def plot_difference(inp, out, path):
    d = out.astype(np.float64) - inp.astype(np.float64)
    ad = np.abs(d)

    fig = plt.figure(figsize=(16, 10))
    gs = GridSpec(2, 3, figure=fig, hspace=0.35, wspace=0.3)

    # Signed diff
    ax0 = fig.add_subplot(gs[0, 0])
    vabs = float(np.percentile(ad, 99))
    im0 = ax0.imshow(d, cmap="coolwarm", vmin=-vabs, vmax=vabs)
    ax0.set_title("帶符號差異圖 (輸出 − 輸入)")
    ax0.axis("off")
    fig.colorbar(im0, ax=ax0, fraction=0.046, pad=0.04)

    # Abs diff
    ax1 = fig.add_subplot(gs[0, 1])
    im1 = ax1.imshow(ad, cmap="hot", vmin=0, vmax=vabs)
    ax1.set_title("絕對差異圖")
    ax1.axis("off")
    fig.colorbar(im1, ax=ax1, fraction=0.046, pad=0.04)

    # Histogram
    ax2 = fig.add_subplot(gs[0, 2])
    ax2.hist(d.ravel(), bins=250, density=True, color="steelblue", edgecolor="none", alpha=0.85)
    ax2.axvline(0, color="red", ls="--", lw=1.2, alpha=0.7)
    ax2.axvline(d.mean(), color="orange", ls="-", lw=1.5, label=f"均值={d.mean():.2f}")
    ax2.set_title("差異值分布")
    ax2.set_xlabel("像素差異值")
    ax2.set_ylabel("密度")
    ax2.legend()
    ax2.grid(alpha=0.25)

    # Row/col trend
    ax3 = fig.add_subplot(gs[1, 0:2])
    row_m = d.mean(axis=1)
    col_m = d.mean(axis=0)
    ax3.plot(row_m, lw=1.5, alpha=0.85, label="行方向均值差異 (沿 Y 軸)", color="steelblue")
    ax3.plot(col_m, lw=1.5, alpha=0.85, label="列方向均值差異 (沿 X 軸)", color="coral")
    ax3.set_title("差異之空間趨勢")
    ax3.set_xlabel("位置 (像素)")
    ax3.set_ylabel("均值差異")
    ax3.legend()
    ax3.grid(alpha=0.25)

    # Radial average
    ax4 = fig.add_subplot(gs[1, 2])
    h, w = ad.shape
    yy, xx = np.indices((h, w))
    # use ring center if available
    cy, cx = h / 2.0, w / 2.0
    rr = np.sqrt((xx - cx)**2 + (yy - cy)**2).astype(np.int32)
    rad = np.bincount(rr.ravel(), weights=ad.ravel()) / np.maximum(np.bincount(rr.ravel()), 1)
    rmax = min(len(rad), int(min(h, w) / 2))
    ax4.plot(rad[:rmax], color="darkorange", lw=1.8)
    ax4.set_title("徑向平均 |差異|")
    ax4.set_xlabel("半徑 (像素)")
    ax4.set_ylabel("均值 |差異|")
    ax4.grid(alpha=0.25)

    fig.suptitle("圖 8 — 差異影像空間分析", fontsize=15, fontweight="bold", y=1.01)
    fig.savefig(path)
    plt.close(fig)


# ===================================================================
# Also regenerate improved basic analysis figures
# ===================================================================
def plot_histogram(inp, out, path):
    fig, axes = plt.subplots(1, 2, figsize=(14, 5.5))
    bins = np.arange(257)
    axes[0].hist(inp.ravel(), bins=bins, density=True, histtype="stepfilled", alpha=0.5, label="輸入", color="steelblue")
    axes[0].hist(out.ravel(), bins=bins, density=True, histtype="stepfilled", alpha=0.5, label="輸出", color="coral")
    axes[0].set_title("灰階直方圖 (線性尺度)")
    axes[0].set_xlabel("灰階值")
    axes[0].set_ylabel("歸一化密度")
    axes[0].legend()
    axes[0].grid(alpha=0.25)

    # Log scale for detail
    axes[1].hist(inp.ravel(), bins=bins, density=True, histtype="step", lw=1.8, label="輸入", color="steelblue")
    axes[1].hist(out.ravel(), bins=bins, density=True, histtype="step", lw=1.8, label="輸出", color="coral")
    axes[1].set_yscale("log")
    axes[1].set_title("灰階直方圖 (對數尺度)")
    axes[1].set_xlabel("灰階值")
    axes[1].set_ylabel("歸一化密度 (log)")
    axes[1].legend()
    axes[1].grid(alpha=0.25)

    fig.suptitle("圖 A — 全域灰階分布比較", fontsize=15, fontweight="bold", y=1.01)
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def plot_gradient(inp, out, path):
    fi, fo = inp.astype(np.float32)/255.0, out.astype(np.float32)/255.0
    gi = np.sqrt(cv2.Sobel(fi, cv2.CV_32F, 1, 0, ksize=3)**2 + cv2.Sobel(fi, cv2.CV_32F, 0, 1, ksize=3)**2)
    go = np.sqrt(cv2.Sobel(fo, cv2.CV_32F, 1, 0, ksize=3)**2 + cv2.Sobel(fo, cv2.CV_32F, 0, 1, ksize=3)**2)
    vmax = max(float(np.percentile(gi, 99)), float(np.percentile(go, 99)))

    fig, axes = plt.subplots(1, 4, figsize=(18, 5))
    im0 = axes[0].imshow(gi, cmap="magma", vmin=0, vmax=vmax)
    axes[0].set_title("輸入梯度圖")
    axes[0].axis("off")
    fig.colorbar(im0, ax=axes[0], fraction=0.046)

    im1 = axes[1].imshow(go, cmap="magma", vmin=0, vmax=vmax)
    axes[1].set_title("輸出梯度圖")
    axes[1].axis("off")
    fig.colorbar(im1, ax=axes[1], fraction=0.046)

    dd = go - gi
    va = max(abs(float(np.percentile(dd, 1))), abs(float(np.percentile(dd, 99))))
    im2 = axes[2].imshow(dd, cmap="coolwarm", vmin=-va, vmax=va)
    axes[2].set_title("梯度差異 (輸出 − 輸入)")
    axes[2].axis("off")
    fig.colorbar(im2, ax=axes[2], fraction=0.046)

    axes[3].hist(gi.ravel(), bins=200, density=True, histtype="step", lw=1.5, label="輸入", color="steelblue")
    axes[3].hist(go.ravel(), bins=200, density=True, histtype="step", lw=1.5, label="輸出", color="coral")
    axes[3].set_title("梯度值分布")
    axes[3].set_xlabel("梯度強度")
    axes[3].set_yscale("log")
    axes[3].legend()
    axes[3].grid(alpha=0.25)

    fig.suptitle("圖 B — 邊緣強度 (Sobel 梯度) 分析", fontsize=15, fontweight="bold", y=1.01)
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def plot_frequency(inp, out, path):
    def fft_power(img):
        f = img.astype(np.float32) / 255.0
        f = f - f.mean()
        wy = np.hanning(img.shape[0])[:, None]
        wx = np.hanning(img.shape[1])[None, :]
        fft = np.fft.fftshift(np.fft.fft2(f * wy * wx))
        pwr = np.abs(fft)**2
        return np.log1p(pwr), pwr

    lp_in, pw_in = fft_power(inp)
    lp_out, pw_out = fft_power(out)

    h, w = inp.shape
    yy, xx = np.indices((h, w))
    rr = np.sqrt((yy - (h-1)/2)**2 + (xx - (w-1)/2)**2)
    rr_n = rr / rr.max()
    ridx = np.minimum((rr_n * 255).astype(np.int32), 255)
    rp_in = np.bincount(ridx.ravel(), weights=pw_in.ravel(), minlength=256) / np.maximum(np.bincount(ridx.ravel(), minlength=256), 1)
    rp_out = np.bincount(ridx.ravel(), weights=pw_out.ravel(), minlength=256) / np.maximum(np.bincount(ridx.ravel(), minlength=256), 1)

    vmax = max(float(np.percentile(lp_in, 99.5)), float(np.percentile(lp_out, 99.5)))
    radii = np.linspace(0, 1, 256)

    fig, axes = plt.subplots(1, 4, figsize=(18, 5))
    im0 = axes[0].imshow(lp_in, cmap="viridis", vmax=vmax)
    axes[0].set_title("輸入頻譜 (log)")
    axes[0].axis("off")
    fig.colorbar(im0, ax=axes[0], fraction=0.046)

    im1 = axes[1].imshow(lp_out, cmap="viridis", vmax=vmax)
    axes[1].set_title("輸出頻譜 (log)")
    axes[1].axis("off")
    fig.colorbar(im1, ax=axes[1], fraction=0.046)

    # Linear scale
    axes[2].plot(radii, rp_in / max(rp_in.max(), 1e-9), lw=1.8, label="輸入", color="steelblue")
    axes[2].plot(radii, rp_out / max(rp_out.max(), 1e-9), lw=1.8, label="輸出", color="coral")
    axes[2].set_title("歸一化徑向功率譜")
    axes[2].set_xlabel("歸一化頻率")
    axes[2].set_ylabel("相對功率")
    axes[2].legend()
    axes[2].grid(alpha=0.25)

    # Log scale for visibility
    axes[3].semilogy(radii, rp_in + 1e-12, lw=1.8, label="輸入", color="steelblue")
    axes[3].semilogy(radii, rp_out + 1e-12, lw=1.8, label="輸出", color="coral")
    axes[3].set_title("徑向功率譜 (對數尺度)")
    axes[3].set_xlabel("歸一化頻率")
    axes[3].set_ylabel("功率 (log)")
    axes[3].legend()
    axes[3].grid(alpha=0.25)

    fig.suptitle("圖 C — 頻域能量分布分析", fontsize=15, fontweight="bold", y=1.01)
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def plot_ring_roi(inp, out, ri, ro, path):
    pad = 80
    x0 = max(0, min(ri["cx"], ro["cx"]) - ri["peak_r"] - pad)
    y0 = max(0, min(ri["cy"], ro["cy"]) - ri["peak_r"] - pad)
    x1 = min(inp.shape[1], max(ri["cx"], ro["cx"]) + ri["peak_r"] + pad)
    y1 = min(inp.shape[0], max(ri["cy"], ro["cy"]) + ri["peak_r"] + pad)
    x0, y0, x1, y1 = int(x0), int(y0), int(x1), int(y1)

    fig, axes = plt.subplots(1, 3, figsize=(16, 5.5))
    axes[0].imshow(inp[y0:y1, x0:x1], cmap="gray", vmin=0, vmax=255)
    c0 = plt.Circle((ri["cx"]-x0, ri["cy"]-y0), ri["peak_r"], ec="red", fc="none", lw=1.5, ls="--")
    axes[0].add_patch(c0)
    axes[0].set_title("輸入 — 環狀結構 ROI")
    axes[0].axis("off")

    axes[1].imshow(out[y0:y1, x0:x1], cmap="gray", vmin=0, vmax=255)
    c1 = plt.Circle((ro["cx"]-x0, ro["cy"]-y0), ro["peak_r"], ec="red", fc="none", lw=1.5, ls="--")
    axes[1].add_patch(c1)
    axes[1].set_title("輸出 — 環狀結構 ROI")
    axes[1].axis("off")

    # Zoomed edge comparison
    cx_avg = (ri["cx"] + ro["cx"]) / 2 - x0
    cy_avg = (ri["cy"] + ro["cy"]) / 2 - y0
    pr = ri["peak_r"]
    # Get a horizontal slice through the ring edge
    row = int(cy_avg - pr * 0.5)
    row = max(0, min(row, y1 - y0 - 1))
    axes[2].plot(inp[y0 + row, x0:x1], lw=1.8, label="輸入", color="steelblue")
    axes[2].plot(out[y0 + row, x0:x1], lw=1.8, label="輸出", color="coral")
    axes[2].set_title(f"水平截面灰階輪廓 (y={y0+row})")
    axes[2].set_xlabel("X 位置 (像素)")
    axes[2].set_ylabel("灰階值")
    axes[2].legend()
    axes[2].grid(alpha=0.25)

    fig.suptitle("圖 D — 環狀結構 ROI 與截面對比", fontsize=15, fontweight="bold", y=1.01)
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def plot_radial_profile(ri, ro, path):
    fig, axes = plt.subplots(1, 3, figsize=(16, 5))

    pi, po = ri["profile"], ro["profile"]
    x_in, x_out = np.arange(len(pi)), np.arange(len(po))

    axes[0].plot(x_in, pi, lw=2, label="輸入", color="steelblue")
    axes[0].plot(x_out, po, lw=2, label="輸出", color="coral")
    axes[0].axvline(ri["peak_r"], color="steelblue", ls="--", lw=1, alpha=0.7)
    axes[0].axvline(ro["peak_r"], color="coral", ls="--", lw=1, alpha=0.7)
    axes[0].set_title("完整徑向強度輪廓")
    axes[0].set_xlabel("半徑 (像素)")
    axes[0].set_ylabel("平均灰階值")
    axes[0].legend()
    axes[0].grid(alpha=0.25)

    # Zoomed around peak
    pr = int(ri["peak_r"])
    lo, hi = max(0, pr - 150), min(len(pi), pr + 150)
    axes[1].plot(x_in[lo:hi], pi[lo:hi], lw=2, label="輸入", color="steelblue")
    lo2, hi2 = max(0, pr - 150), min(len(po), pr + 150)
    axes[1].plot(x_out[lo2:hi2], po[lo2:hi2], lw=2, label="輸出", color="coral")
    axes[1].axvline(ri["peak_r"], color="steelblue", ls="--", lw=1, alpha=0.7)
    axes[1].set_title("環峰值區域放大")
    axes[1].set_xlabel("半徑 (像素)")
    axes[1].set_ylabel("平均灰階值")
    axes[1].legend()
    axes[1].grid(alpha=0.25)

    # Difference
    mn = min(len(pi), len(po))
    diff_p = po[:mn] - pi[:mn]
    axes[2].plot(np.arange(mn), diff_p, lw=1.5, color="mediumpurple")
    axes[2].axhline(0, color="gray", ls="--", lw=1)
    axes[2].fill_between(np.arange(mn), diff_p, 0, alpha=0.3, color="mediumpurple")
    axes[2].set_title("徑向輪廓差異 (輸出 − 輸入)")
    axes[2].set_xlabel("半徑 (像素)")
    axes[2].set_ylabel("灰階差異")
    axes[2].grid(alpha=0.25)

    fig.suptitle("圖 E — 徑向強度輪廓分析", fontsize=15, fontweight="bold", y=1.01)
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


# ===================================================================
# Main
# ===================================================================
def main():
    print("Loading images...")
    inp = imread_gray(INPUT_PATH)
    out = imread_gray(OUTPUT_PATH)
    metrics: dict[str, Any] = {}

    # Ring detection
    ri = detect_ring(inp)
    ro = detect_ring(out)

    # 1. SSIM
    print("[1/8] SSIM...")
    ms, smap, lcs = compute_ssim(inp, out)
    metrics["ssim"] = {
        "mean": ms, "p05": float(np.percentile(smap, 5)),
        "p25": float(np.percentile(smap, 25)), "p50": float(np.percentile(smap, 50)),
        "std": float(smap.std()), **lcs,
    }
    plot_ssim(smap, ms, BUNDLE / "ssim_analysis.png")

    # 2. MTF
    print("[2/8] MTF...")
    try:
        from scipy.ndimage import gaussian_filter1d  # noqa: F401
        fi, mi, _ = esf_to_mtf(ri["profile"])
        fo, mo, _ = esf_to_mtf(ro["profile"])
    except ImportError:
        # fallback without scipy smoothing
        def simple_mtf(profile):
            esf = (profile - profile.min()) / max(profile.max() - profile.min(), 1e-9)
            lsf = np.gradient(esf)
            # simple moving average smooth
            kernel = np.ones(7) / 7
            lsf = np.convolve(lsf, kernel, mode="same")
            n = max(len(lsf) * 8, 2048)
            mtf = np.abs(np.fft.rfft(lsf, n=n))
            mtf = mtf / max(mtf[0], 1e-9)
            return np.fft.rfftfreq(n, d=1.0), mtf
        fi, mi = simple_mtf(ri["profile"])
        fo, mo = simple_mtf(ro["profile"])
    si = {"mtf50": mtf_cutoff(fi, mi, 0.5), "mtf10": mtf_cutoff(fi, mi, 0.1)}
    so = {"mtf50": mtf_cutoff(fo, mo, 0.5), "mtf10": mtf_cutoff(fo, mo, 0.1)}
    metrics["mtf"] = {"input": si, "output": so}
    plot_mtf(fi, mi, fo, mo, si, so, BUNDLE / "mtf_comparison.png")

    # 3. SNR
    print("[3/8] SNR...")
    snr_i = snr_metrics(inp)
    snr_o = snr_metrics(out)
    sm_i = local_snr_map(inp)
    sm_o = local_snr_map(out)
    metrics["snr"] = {"input": snr_i, "output": snr_o}
    plot_snr(snr_i, snr_o, sm_i, sm_o, BUNDLE / "snr_analysis.png")

    # 4. ESF/LSF
    print("[4/8] ESF/LSF...")
    esf_in, bins_in = extract_esf(inp, ri["cx"], ri["cy"], ri["peak_r"])
    esf_out, bins_out = extract_esf(out, ro["cx"], ro["cy"], ro["peak_r"])
    n_in = (esf_in - esf_in.min()) / max(esf_in.max() - esf_in.min(), 1e-9)
    n_out = (esf_out - esf_out.min()) / max(esf_out.max() - esf_out.min(), 1e-9)
    lsf_in_v = np.gradient(n_in)
    lsf_out_v = np.gradient(n_out)
    metrics["esf_lsf"] = {
        "input_esf_range": round(float(esf_in.max() - esf_in.min()), 4),
        "output_esf_range": round(float(esf_out.max() - esf_out.min()), 4),
        "input_lsf_peak": round(float(np.abs(lsf_in_v).max()), 6),
        "output_lsf_peak": round(float(np.abs(lsf_out_v).max()), 6),
        "input_lsf_fwhm": round(float(np.sum(np.abs(lsf_in_v) >= np.abs(lsf_in_v).max()/2)), 1),
        "output_lsf_fwhm": round(float(np.sum(np.abs(lsf_out_v) >= np.abs(lsf_out_v).max()/2)), 1),
    }
    plot_esf_lsf(esf_in, esf_out, bins_in, bins_out, BUNDLE / "esf_lsf_analysis.png")

    # 5. Wavelet
    print("[5/8] Wavelet...")
    wi = haar_decompose(inp)
    wo = haar_decompose(out)
    metrics["wavelet"] = {"input": wi, "output": wo}
    plot_wavelet(wi, wo, BUNDLE / "wavelet_decomposition.png")

    # 6. GLCM
    print("[6/8] GLCM...")
    gi = compute_glcm(inp)
    go = compute_glcm(out)
    metrics["glcm"] = {"input": gi, "output": go}
    plot_glcm(gi, go, BUNDLE / "glcm_texture_analysis.png")

    # 7. Local Contrast
    print("[7/8] Local contrast...")
    wb_i, mc_i = local_contrast_maps(inp)
    wb_o, mc_o = local_contrast_maps(out)
    metrics["local_contrast"] = {
        "input_weber": lc_stats(wb_i, "weber"), "output_weber": lc_stats(wb_o, "weber"),
        "input_michelson": lc_stats(mc_i, "michelson"), "output_michelson": lc_stats(mc_o, "michelson"),
    }
    plot_local_contrast(wb_i, wb_o, mc_i, mc_o, BUNDLE / "local_contrast_analysis.png")

    # 8. Difference
    print("[8/8] Difference spatial...")
    dm = diff_metrics(inp, out)
    metrics["difference"] = dm
    plot_difference(inp, out, BUNDLE / "difference_spatial_analysis.png")

    # Regenerate improved basic figures
    print("Regenerating basic figures...")
    plot_histogram(inp, out, BUNDLE / "histogram_comparison.png")
    plot_gradient(inp, out, BUNDLE / "gradient_comparison.png")
    plot_frequency(inp, out, BUNDLE / "frequency_spectrum_comparison.png")
    plot_ring_roi(inp, out, ri, ro, BUNDLE / "ring_roi_comparison.png")
    plot_radial_profile(ri, ro, BUNDLE / "radial_profile_comparison.png")

    # Save metrics
    mp = BUNDLE / "advanced_metrics.json"
    mp.write_text(json.dumps(metrics, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print(f"Metrics: {mp}")
    print("All figures generated.")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
R26 GMF 可定位性分析腳本
分析 6 個對 external GMF 幾何定位有效的指標，替代舊的通用影像品質分析。
"""
from pathlib import Path
import sys, json
import numpy as np
import cv2
import matplotlib
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
PROJECT_ROOT = Path(__file__).resolve().parents[7]

# Add Model dir for CenterEstDiag
sys.path.insert(0, str(Path(str(PROJECT_ROOT / 'Model'))))
try:
    from GeoEdgeAlignSR_v1_CenterEstDiag import (
        load_image as diag_load_image,
        compute_sobel_magnitude,
        estimate_center_edge_centroid,
        estimate_center_soft_centroid,
        estimate_center_algebraic_fit,
    )
    CENTROID_AVAILABLE = True
except ImportError:
    CENTROID_AVAILABLE = False
    print("WARNING: CenterEstDiag not available, centroid analysis will be skipped")

# CJK font fallback
import matplotlib.font_manager as fm
for _font in ["Microsoft JhengHei", "Microsoft YaHei", "SimHei", "Noto Sans CJK TC", "DejaVu Sans"]:
    try:
        fm.findfont(_font, fallback_to_default=False)
        plt.rcParams["font.family"] = _font
        break
    except Exception:
        pass
plt.rcParams["axes.unicode_minus"] = False

np.seterr(divide='ignore', invalid='ignore')

def imread_gray(path) -> np.ndarray:
    """cv2.imread 在 Windows 下不支援中文路徑，改用 np.fromfile + imdecode。"""
    buf = np.fromfile(str(path), dtype=np.uint8)
    img = cv2.imdecode(buf, cv2.IMREAD_GRAYSCALE)
    if img is None:
        raise FileNotFoundError(f"Cannot decode image: {path}")
    return img

BASE        = Path(str(PROJECT_ROOT / 'Deliverables/Company_Packages/GeoEdge_R26_正式交付版/GeoEdge_R26_使用包/輸出結果/驗證分析/R26_validation_complete'))
INPUT_PATH  = BASE / "data/case01/input_image.bmp"
OUTPUT_PATH = BASE / "data/case01/model_output.bmp"
BASIC_JSON  = BASE / "data/basic_metrics.json"
OUT_FIGURES = BASE / "figures"
OUT_JSON    = BASE / "data/case01/gmf_metrics.json"


def _safe_float(x):
    """Convert numpy scalar to Python float, returning None for NaN/inf."""
    if x is None:
        return None
    try:
        v = float(x)
        if np.isnan(v) or np.isinf(v):
            return None
        return v
    except Exception:
        return None


def _safe_list(arr):
    """Convert array-like to list of safe floats."""
    return [_safe_float(v) for v in arr]


# ---------------------------------------------------------------------------
# ANALYSIS 1: AZIMUTHAL UNIFORMITY
# ---------------------------------------------------------------------------

def analyze_azimuthal_uniformity(img_in, img_out, cx, cy, peak_r, fwhm, rr, angle_map):
    """Analyse azimuthal uniformity across 16 angular sectors."""
    N_SECTORS = 16
    sector_size = 22.5  # degrees per sector
    sector_centers_deg = [-180 + (i + 0.5) * sector_size for i in range(N_SECTORS)]

    ring_inner = peak_r - fwhm / 2.0
    ring_outer = peak_r + fwhm / 2.0
    ring_mask = (rr >= ring_inner) & (rr <= ring_outer)

    # Global background fallback
    bg_mask_global = rr > (ring_outer + 25)
    fallback_bg_in  = float(np.mean(img_in[bg_mask_global]))  if np.any(bg_mask_global) else 0.0
    fallback_bg_out = float(np.mean(img_out[bg_mask_global])) if np.any(bg_mask_global) else 0.0

    in_sector_peaks     = []
    out_sector_peaks    = []
    in_sector_contrasts = []
    out_sector_contrasts= []

    for i in range(N_SECTORS):
        sector_start = -180.0 + i * sector_size
        sector_end   = sector_start + sector_size

        if i < N_SECTORS - 1:
            in_sector = (angle_map >= sector_start) & (angle_map < sector_end)
        else:
            # Last sector: up to and including +180
            in_sector = (angle_map >= sector_start) & (angle_map <= 180.0)

        sector_ring = ring_mask & in_sector
        sector_bg_annulus = (rr >= ring_outer + 5) & (rr <= ring_outer + 30) & in_sector

        for img, peaks_list, contrasts_list, fallback_bg in [
            (img_in,  in_sector_peaks,  in_sector_contrasts,  fallback_bg_in),
            (img_out, out_sector_peaks, out_sector_contrasts, fallback_bg_out),
        ]:
            n_ring = int(np.sum(sector_ring))
            n_bg   = int(np.sum(sector_bg_annulus))

            if n_ring > 10:
                local_peak = float(np.percentile(img[sector_ring], 90))
            else:
                local_peak = np.nan

            if n_bg > 10:
                local_bg = float(np.mean(img[sector_bg_annulus]))
            else:
                local_bg = fallback_bg

            sector_contrast = local_peak - local_bg
            peaks_list.append(local_peak)
            contrasts_list.append(sector_contrast)

    # Replace NaN peaks with sector mean
    in_sector_peaks  = np.array(in_sector_peaks,  dtype=np.float64)
    out_sector_peaks = np.array(out_sector_peaks, dtype=np.float64)
    in_sector_contrasts  = np.array(in_sector_contrasts,  dtype=np.float64)
    out_sector_contrasts = np.array(out_sector_contrasts, dtype=np.float64)

    in_mean_peak  = np.nanmean(in_sector_peaks)
    out_mean_peak = np.nanmean(out_sector_peaks)
    in_sector_peaks  = np.where(np.isnan(in_sector_peaks),  in_mean_peak,  in_sector_peaks)
    out_sector_peaks = np.where(np.isnan(out_sector_peaks), out_mean_peak, out_sector_peaks)

    in_contrast_mean  = np.nanmean(in_sector_contrasts)
    out_contrast_mean = np.nanmean(out_sector_contrasts)
    in_sector_contrasts  = np.where(np.isnan(in_sector_contrasts),  in_contrast_mean,  in_sector_contrasts)
    out_sector_contrasts = np.where(np.isnan(out_sector_contrasts), out_contrast_mean, out_sector_contrasts)

    in_peak_std  = float(np.std(in_sector_peaks))
    out_peak_std = float(np.std(out_sector_peaks))
    in_contrast_std  = float(np.std(in_sector_contrasts))
    out_contrast_std = float(np.std(out_sector_contrasts))

    # ---- Plot ----
    fig = plt.figure(figsize=(14, 6))
    ax_polar = fig.add_subplot(121, projection='polar')
    ax_bar   = fig.add_subplot(122)

    theta_bars = np.array([np.deg2rad(-180 + i * sector_size) for i in range(N_SECTORS)])
    bar_width  = 2 * np.pi / N_SECTORS

    # Normalize for polar display
    all_peaks = np.concatenate([in_sector_peaks, out_sector_peaks])
    max_all   = np.max(all_peaks) + 1e-12
    in_norm   = in_sector_peaks  / max_all
    out_norm  = out_sector_peaks / max_all

    ax_polar.bar(theta_bars, in_norm,  width=bar_width, bottom=0.5,
                 color='steelblue', alpha=0.7, label='Input')
    ax_polar.bar(theta_bars, out_norm, width=bar_width, bottom=0.75,
                 color='orangered', alpha=0.7, label='Output')
    ax_polar.legend(loc='upper right', bbox_to_anchor=(1.3, 1.1), fontsize=8)
    ax_polar.set_title("方位角均勻性\n(16扇區峰值灰階)", pad=12)

    x = np.arange(N_SECTORS)
    width = 0.35
    ax_bar.bar(x - width/2, in_sector_contrasts,  width, color='steelblue', alpha=0.8, label='Input')
    ax_bar.bar(x + width/2, out_sector_contrasts, width, color='orangered', alpha=0.8, label='Output')
    ax_bar.axhline(in_contrast_mean,  color='steelblue', linestyle='--', alpha=0.6)
    ax_bar.axhline(out_contrast_mean, color='orangered', linestyle='--', alpha=0.6)
    ax_bar.text(0.98, 0.97,
                f"In contrast_std={in_contrast_std:.2f}\nOut contrast_std={out_contrast_std:.2f}",
                transform=ax_bar.transAxes, ha='right', va='top', fontsize=9,
                bbox=dict(boxstyle='round,pad=0.3', facecolor='lightyellow', alpha=0.8))
    ax_bar.set_xlabel("扇區編號")
    ax_bar.set_ylabel("局部對比度 (peak−bg)")
    ax_bar.set_title("各扇區局部對比度")
    ax_bar.legend(fontsize=9)
    ax_bar.set_xticks(x)

    fig.suptitle(
        f"環帶方位均勻性分析\nInput peak_std={in_peak_std:.2f}  Output peak_std={out_peak_std:.2f}",
        fontsize=12
    )
    fig.tight_layout()
    fig.savefig(OUT_FIGURES / "01_azimuthal_uniformity.png", dpi=120, bbox_inches='tight')
    plt.close(fig)

    return {
        "n_sectors": N_SECTORS,
        "input_sector_peak_std":      _safe_float(in_peak_std),
        "output_sector_peak_std":     _safe_float(out_peak_std),
        "input_sector_contrast_std":  _safe_float(in_contrast_std),
        "output_sector_contrast_std": _safe_float(out_contrast_std),
        "input_sector_peaks":         _safe_list(in_sector_peaks),
        "output_sector_peaks":        _safe_list(out_sector_peaks),
        "input_sector_contrasts":     _safe_list(in_sector_contrasts),
        "output_sector_contrasts":    _safe_list(out_sector_contrasts),
    }


# ---------------------------------------------------------------------------
# ANALYSIS 2: BACKGROUND DIRECTIONAL ANISOTROPY
# ---------------------------------------------------------------------------

def analyze_background_anisotropy(img_in, img_out, bg_mask):
    """Analyse directional anisotropy of background gradients."""
    N_BINS = 36
    bin_edges = np.linspace(-180, 180, N_BINS + 1)
    bin_centers_deg = np.linspace(-180 + (360 / N_BINS) / 2,
                                   180 - (360 / N_BINS) / 2, N_BINS)
    bin_centers_rad = np.deg2rad(bin_centers_deg)

    results = {}

    fig, axes = plt.subplots(1, 2, figsize=(12, 5), subplot_kw={'projection': 'polar'})

    for img, label, ax, key_prefix in [
        (img_in,  "Input 背景梯度方向",  axes[0], "input"),
        (img_out, "Output 背景梯度方向", axes[1], "output"),
    ]:
        gx = cv2.Sobel(img.astype(np.float32), cv2.CV_32F, 1, 0, ksize=3)
        gy = cv2.Sobel(img.astype(np.float32), cv2.CV_32F, 0, 1, ksize=3)
        mag = np.sqrt(gx**2 + gy**2)

        gx_bg  = gx[bg_mask]
        gy_bg  = gy[bg_mask]
        mag_bg = mag[bg_mask]

        keep_mask = mag_bg > 0.5
        if np.sum(keep_mask) < 10:
            # Not enough background gradient pixels — produce zeros
            hist_norm = np.zeros(N_BINS)
            dai = 0.0
            R   = 0.0
            dominant_angle = 0.0
        else:
            gx_k  = gx_bg[keep_mask]
            gy_k  = gy_bg[keep_mask]
            mag_k = mag_bg[keep_mask]
            theta_deg = np.degrees(np.arctan2(gy_k, gx_k))  # -180..180

            hist, _ = np.histogram(theta_deg, bins=bin_edges, weights=mag_k)
            hist_sum = hist.sum() + 1e-12
            hist_norm = hist / hist_sum

            mean_val = hist_norm.mean() + 1e-12
            dai = float((hist_norm.max() - hist_norm.mean()) / mean_val)

            C = float(np.sum(hist_norm * np.cos(bin_centers_rad)))
            S = float(np.sum(hist_norm * np.sin(bin_centers_rad)))
            R = float(np.sqrt(C**2 + S**2))
            dominant_angle = float(bin_centers_deg[np.argmax(hist_norm)])

        results[f"{key_prefix}_dai"]                  = _safe_float(dai)
        results[f"{key_prefix}_resultant_length"]     = _safe_float(R)
        results[f"{key_prefix}_dominant_angle_deg"]   = _safe_float(dominant_angle)

        # Polar bar chart — display from 0..2pi
        theta_display = (bin_centers_rad + np.pi) % (2 * np.pi)
        bar_width_rad = 2 * np.pi / N_BINS

        # Sort by display angle for a clean plot
        sort_idx  = np.argsort(theta_display)
        theta_plot = theta_display[sort_idx]
        hist_plot  = hist_norm[sort_idx]

        colors = plt.cm.RdYlBu_r(hist_plot / (hist_plot.max() + 1e-12))
        ax.bar(theta_plot, hist_plot, width=bar_width_rad, color=colors, alpha=0.85)
        ax.set_title(label, pad=12)
        textstr = (f"DAI={dai:.3f}\nR={R:.3f}\n"
                   f"主方向={dominant_angle:.1f}°")
        ax.text(0.05, 0.95, textstr, transform=ax.transAxes, fontsize=8,
                va='top', bbox=dict(boxstyle='round,pad=0.3', facecolor='white', alpha=0.7))

    fig.suptitle(
        f"背景方向性梯度分析\n"
        f"Input DAI={results['input_dai']:.3f}  "
        f"Output DAI={results['output_dai']:.3f}",
        fontsize=12
    )
    fig.tight_layout()
    fig.savefig(OUT_FIGURES / "02_background_anisotropy.png", dpi=120, bbox_inches='tight')
    plt.close(fig)

    return results


# ---------------------------------------------------------------------------
# ANALYSIS 3: RING PROFILE ASYMMETRY
# ---------------------------------------------------------------------------

def analyze_profile_asymmetry(img_in, img_out, cx, cy, peak_r, fwhm, rr, yy, xx):
    """Analyse left/right/top/bottom asymmetry of the ring profile."""
    ring_inner = peak_r - fwhm / 2.0
    ring_outer = peak_r + fwhm / 2.0
    ring_mask  = (rr >= ring_inner) & (rr <= ring_outer)
    bg_annulus = (rr >= ring_outer + 5) & (rr <= ring_outer + 30)

    half_masks = {
        "left":   xx < cx,
        "right":  xx > cx,
        "top":    yy < cy,
        "bottom": yy > cy,
    }

    def compute_quadrant_stats(img, global_bg):
        peaks = {}
        contrasts = {}
        for half_name, half_mask in half_masks.items():
            px_ring = img[ring_mask & half_mask]
            px_bg   = img[bg_annulus & half_mask]
            local_peak = float(np.percentile(px_ring, 90)) if len(px_ring) > 10 else np.nan
            local_bg   = float(np.mean(px_bg))             if len(px_bg) > 10  else global_bg
            peaks[half_name]    = local_peak
            contrasts[half_name] = local_peak - local_bg
        return peaks, contrasts

    # Global background
    bg_global_in  = float(np.mean(img_in[rr  > (ring_outer + 25)])) if np.any(rr > (ring_outer + 25)) else 0.0
    bg_global_out = float(np.mean(img_out[rr > (ring_outer + 25)])) if np.any(rr > (ring_outer + 25)) else 0.0

    in_peaks,  in_contrasts  = compute_quadrant_stats(img_in,  bg_global_in)
    out_peaks, out_contrasts = compute_quadrant_stats(img_out, bg_global_out)

    def asymmetry(peaks, a, b):
        va, vb = peaks.get(a, np.nan), peaks.get(b, np.nan)
        if np.isnan(va) or np.isnan(vb):
            return np.nan
        denom = (va + vb) / 2.0 + 1e-12
        return float(abs(va - vb) / denom)

    in_h  = asymmetry(in_peaks,  "right", "left")
    in_v  = asymmetry(in_peaks,  "bottom", "top")
    out_h = asymmetry(out_peaks, "right", "left")
    out_v = asymmetry(out_peaks, "bottom", "top")

    # Radial profiles per half
    r_bins = np.arange(peak_r - 70, peak_r + 71, 2.0)
    colors = ['#2196F3', '#F44336', '#4CAF50', '#FF9800']
    half_order = ["left", "right", "top", "bottom"]

    def build_profiles(img):
        profiles = {}
        for half_name, half_mask in half_masks.items():
            prof = []
            for rb in r_bins:
                annulus_slice = (rr >= rb - 1) & (rr < rb + 1) & half_mask
                if np.any(annulus_slice):
                    prof.append(float(np.mean(img[annulus_slice])))
                else:
                    prof.append(np.nan)
            profiles[half_name] = prof
        return profiles

    in_profiles  = build_profiles(img_in)
    out_profiles = build_profiles(img_out)
    r_offsets    = r_bins - peak_r

    half_labels = {"left": "左", "right": "右", "top": "上", "bottom": "下"}

    fig, axes = plt.subplots(2, 2, figsize=(14, 10))

    for col_idx, (img_label, profiles, peaks, contrasts, h_asym, v_asym) in enumerate([
        ("Input",  in_profiles,  in_peaks,  in_contrasts,  in_h,  in_v),
        ("Output", out_profiles, out_peaks, out_contrasts, out_h, out_v),
    ]):
        ax_top = axes[0, col_idx]
        for ci, half_name in enumerate(half_order):
            ax_top.plot(r_offsets, profiles[half_name],
                        color=colors[ci], alpha=0.8,
                        label=half_labels[half_name], linewidth=1.5)
        ax_top.set_title(f"{img_label} 四方向徑向輪廓")
        ax_top.set_xlabel("半徑偏移 (px)")
        ax_top.set_ylabel("平均灰階")
        ax_top.legend(fontsize=9)
        ax_top.grid(True, alpha=0.3)

        ax_bot = axes[1, col_idx]
        half_keys = half_order
        peak_vals = [peaks.get(k, 0) for k in half_keys]
        half_tick_labels = [half_labels[k] for k in half_keys]
        ax_bot.bar(range(4), peak_vals, color=colors, alpha=0.8)
        ax_bot.axhline(np.nanmean([v for v in peak_vals if not np.isnan(v)]),
                       color='gray', linestyle='--', alpha=0.6, label='平均')
        ax_bot.set_xticks(range(4))
        ax_bot.set_xticklabels(half_tick_labels)
        ax_bot.set_title(f"{img_label} 各半平面峰值灰階")
        ax_bot.text(0.98, 0.97,
                    f"H-asym={h_asym:.4f}\nV-asym={v_asym:.4f}",
                    transform=ax_bot.transAxes, ha='right', va='top', fontsize=9,
                    bbox=dict(boxstyle='round,pad=0.3', facecolor='lightyellow', alpha=0.8))
        ax_bot.legend(fontsize=8)
        ax_bot.grid(True, alpha=0.3)

    fig.suptitle(
        f"環形輪廓非對稱性分析\n"
        f"Input H={in_h:.4f} V={in_v:.4f} | Output H={out_h:.4f} V={out_v:.4f}",
        fontsize=12
    )
    fig.tight_layout()
    fig.savefig(OUT_FIGURES / "03_profile_asymmetry.png", dpi=120, bbox_inches='tight')
    plt.close(fig)

    return {
        "input_horizontal_asymmetry_index":  _safe_float(in_h),
        "output_horizontal_asymmetry_index": _safe_float(out_h),
        "input_vertical_asymmetry_index":    _safe_float(in_v),
        "output_vertical_asymmetry_index":   _safe_float(out_v),
        "input_quadrant_peaks":    {k: _safe_float(v) for k, v in in_peaks.items()},
        "output_quadrant_peaks":   {k: _safe_float(v) for k, v in out_peaks.items()},
        "input_quadrant_contrasts":  {k: _safe_float(v) for k, v in in_contrasts.items()},
        "output_quadrant_contrasts": {k: _safe_float(v) for k, v in out_contrasts.items()},
    }


# ---------------------------------------------------------------------------
# ANALYSIS 4: RINGING ARTIFACT DETECTION
# ---------------------------------------------------------------------------

def analyze_ringing_artifact(img_in, img_out, cx, cy, peak_r, fwhm,
                              rr, bg_gray_in, bg_gray_out,
                              peak_gray_in, peak_gray_out):
    """Detect ringing artifacts in the radial profile around the ring edge."""
    r_max = int(peak_r + 100)
    H, W  = rr.shape

    def radial_profile_bincount(img):
        rr_int = np.clip(np.round(rr).astype(np.int32), 0, r_max)
        weights = img.ravel().astype(np.float64)
        counts  = np.bincount(rr_int.ravel(), minlength=r_max + 1)
        sums    = np.bincount(rr_int.ravel(), weights=weights, minlength=r_max + 1)
        profile = np.where(counts > 0, sums / counts, 0.0)
        return profile  # length r_max+1, index = radius

    profile_in  = radial_profile_bincount(img_in)
    profile_out = radial_profile_bincount(img_out)

    outer_start = int(np.clip(peak_r + fwhm / 2 + 2,  0, r_max))
    outer_end   = int(np.clip(peak_r + fwhm / 2 + 30, 0, r_max))
    inner_start = int(np.clip(peak_r - fwhm / 2 - 30, 0, r_max))
    inner_end   = int(np.clip(peak_r - fwhm / 2 - 2,  0, r_max))

    def compute_ringing(profile, bg_gray, peak_gray):
        prof_outer = profile[outer_start:outer_end + 1]
        prof_inner = profile[inner_start:inner_end + 1]
        denom = (peak_gray - bg_gray) + 1e-12

        if len(prof_outer) > 0:
            overshoot       = max(0.0, float(np.max(prof_outer)) - bg_gray)
            overshoot_ratio = overshoot / denom
        else:
            overshoot = overshoot_ratio = 0.0

        if len(prof_inner) > 0:
            undershoot       = max(0.0, bg_gray - float(np.min(prof_inner)))
            undershoot_ratio = undershoot / denom
        else:
            undershoot = undershoot_ratio = 0.0

        return overshoot_ratio, undershoot_ratio

    in_over,  in_under  = compute_ringing(profile_in,  bg_gray_in,  peak_gray_in)
    out_over, out_under = compute_ringing(profile_out, bg_gray_out, peak_gray_out)

    ringing_flag = bool(out_over > 0.05)

    # ---- Plot ----
    r_axis = np.arange(r_max + 1)

    fig, (ax_full, ax_zoom) = plt.subplots(1, 2, figsize=(14, 5))

    # Full profile
    ax_full.plot(r_axis, profile_in,  color='steelblue',  label='Input',  linewidth=1.2)
    ax_full.plot(r_axis, profile_out, color='darkorange',  label='Output', linewidth=1.2)
    ax_full.axvspan(outer_start, outer_end, alpha=0.2, color='yellow',  label='外側觀察帶')
    ax_full.axvspan(inner_start, inner_end, alpha=0.2, color='cyan',    label='內側觀察帶')
    ax_full.axvline(peak_r, color='red', linestyle='--', alpha=0.6, label=f'peak_r={peak_r:.1f}')
    ax_full.set_title("完整徑向輪廓（含觀察帶）")
    ax_full.set_xlabel("半徑 (px)")
    ax_full.set_ylabel("平均灰階")
    ax_full.legend(fontsize=8)
    ax_full.grid(True, alpha=0.3)

    # Zoomed view
    z_start = max(0, int(peak_r) - 70)
    z_end   = min(r_max, int(peak_r) + 60)
    ax_zoom.plot(r_axis[z_start:z_end + 1], profile_in[z_start:z_end + 1],
                 color='steelblue', label='Input', linewidth=1.5)
    ax_zoom.plot(r_axis[z_start:z_end + 1], profile_out[z_start:z_end + 1],
                 color='darkorange', label='Output', linewidth=1.5)
    ax_zoom.axhline(bg_gray_in,   color='steelblue', linestyle='--', alpha=0.5, label='In BG')
    ax_zoom.axhline(bg_gray_out,  color='darkorange', linestyle='--', alpha=0.5, label='Out BG')
    ax_zoom.axhline(peak_gray_in, color='steelblue', linestyle=':',  alpha=0.5, label='In Peak')
    ax_zoom.axhline(peak_gray_out,color='darkorange', linestyle=':',  alpha=0.5, label='Out Peak')

    # Annotate overshoot / undershoot
    if outer_end < len(r_axis):
        ax_zoom.annotate(
            f"overshoot={out_over:.4f}",
            xy=(outer_start + (outer_end - outer_start) // 2, bg_gray_out + (peak_gray_out - bg_gray_out) * 0.3),
            fontsize=8, color='darkred',
            bbox=dict(boxstyle='round,pad=0.2', facecolor='lightyellow', alpha=0.8)
        )
    if inner_start >= z_start:
        ax_zoom.annotate(
            f"undershoot={out_under:.4f}",
            xy=(inner_start + (inner_end - inner_start) // 2, bg_gray_out * 0.85),
            fontsize=8, color='darkblue',
            bbox=dict(boxstyle='round,pad=0.2', facecolor='lightcyan', alpha=0.8)
        )
    ax_zoom.set_title("邊界放大：振鈴觀察帶")
    ax_zoom.set_xlabel("半徑 (px)")
    ax_zoom.set_ylabel("平均灰階")
    ax_zoom.legend(fontsize=8)
    ax_zoom.grid(True, alpha=0.3)

    flag_text = "⚠ 振鈴比率 > 5%" if ringing_flag else "✓ 振鈴未超過閾值"
    fig.suptitle(
        f"邊界振鈴偽影偵測 | Output overshoot={out_over:.4f}  undershoot={out_under:.4f}  {flag_text}",
        fontsize=11
    )
    fig.tight_layout()
    fig.savefig(OUT_FIGURES / "04_ringing_detection.png", dpi=120, bbox_inches='tight')
    plt.close(fig)

    return {
        "input_overshoot_ratio":   _safe_float(in_over),
        "output_overshoot_ratio":  _safe_float(out_over),
        "input_undershoot_ratio":  _safe_float(in_under),
        "output_undershoot_ratio": _safe_float(out_under),
        "output_ringing_flag":     ringing_flag,
    }


# ---------------------------------------------------------------------------
# ANALYSIS 5: CENTROID ESTIMATOR COMPARISON
# ---------------------------------------------------------------------------

def analyze_centroid_estimators(img_in_path, img_out_path, cx_ref, cy_ref, peak_r):
    """Compare multiple centroid estimator results between input and output."""
    if not CENTROID_AVAILABLE:
        return None

    # Load as float [0,1]
    img_in_f  = diag_load_image(str(img_in_path))
    img_out_f = diag_load_image(str(img_out_path))

    # Load as uint8 for display
    img_in_u8  = imread_gray(img_in_path)
    img_out_u8 = imread_gray(img_out_path)
    H, W = img_in_u8.shape

    edge_in  = compute_sobel_magnitude(img_in_f)
    edge_out = compute_sobel_magnitude(img_out_f)

    estimators = {
        "edge_centroid":    (estimate_center_edge_centroid,    "red"),
        "soft_centroid":    (estimate_center_soft_centroid,    "lime"),
        "algebraic_fit":    (estimate_center_algebraic_fit,    "dodgerblue"),
    }

    results_in  = {}
    results_out = {}

    for name, (func, _) in estimators.items():
        try:
            cy_i, cx_i = func(edge_in)
            results_in[name]  = (float(cx_i), float(cy_i))
        except Exception:
            results_in[name]  = (float(cx_ref), float(cy_ref))
        try:
            cy_o, cx_o = func(edge_out)
            results_out[name] = (float(cx_o), float(cy_o))
        except Exception:
            results_out[name] = (float(cx_ref), float(cy_ref))

    # Inter-estimator spread
    cx_in_vals  = [results_in[n][0]  for n in estimators]
    cy_in_vals  = [results_in[n][1]  for n in estimators]
    cx_out_vals = [results_out[n][0] for n in estimators]
    cy_out_vals = [results_out[n][1] for n in estimators]

    spread_cx_in  = float(np.std(cx_in_vals))
    spread_cy_in  = float(np.std(cy_in_vals))
    spread_cx_out = float(np.std(cx_out_vals))
    spread_cy_out = float(np.std(cy_out_vals))

    # Max pairwise inter-estimator distance
    names_list = list(estimators.keys())

    def max_pairwise(results):
        pts = [results[n] for n in names_list]
        max_d = 0.0
        for i in range(len(pts)):
            for j in range(i + 1, len(pts)):
                d = float(np.sqrt((pts[i][0] - pts[j][0])**2 + (pts[i][1] - pts[j][1])**2))
                max_d = max(max_d, d)
        return max_d

    max_dist_in  = max_pairwise(results_in)
    max_dist_out = max_pairwise(results_out)

    # Per-estimator centroid shift (in->out)
    centroid_shifts = {}
    for n in names_list:
        dx = results_out[n][0] - results_in[n][0]
        dy = results_out[n][1] - results_in[n][1]
        centroid_shifts[n] = float(np.sqrt(dx**2 + dy**2))

    # ---- Plot ----
    crop_half = 100
    y0 = max(0, int(cy_ref) - crop_half)
    y1 = min(H, int(cy_ref) + crop_half)
    x0 = max(0, int(cx_ref) - crop_half)
    x1 = min(W, int(cx_ref) + crop_half)

    fig = plt.figure(figsize=(16, 7))
    gs  = gridspec.GridSpec(1, 3, width_ratios=[0.4, 0.4, 0.2], figure=fig)
    ax_left  = fig.add_subplot(gs[0])
    ax_mid   = fig.add_subplot(gs[1])
    ax_right = fig.add_subplot(gs[2])

    for ax, img_u8, est_results, title in [
        (ax_left,  img_in_u8,  results_in,  "Input: 估算器質心位置"),
        (ax_mid,   img_out_u8, results_out, "Output: 估算器質心位置"),
    ]:
        crop = img_u8[y0:y1, x0:x1]
        ax.imshow(crop, cmap='gray', interpolation='nearest')
        for name, (func, color) in estimators.items():
            cx_e, cy_e = est_results[name]
            # Convert to crop coords
            cx_crop = cx_e - x0
            cy_crop = cy_e - y0
            ax.scatter(cx_crop, cy_crop, s=80, color=color,
                       label=name, zorder=5, edgecolors='white', linewidths=0.5)
        ax.set_title(title, fontsize=10)
        ax.legend(fontsize=7, loc='lower right')
        ax.axis('on')

    # Text table
    ax_right.axis('off')
    col_labels = ["估算器", "In cx", "In cy", "Out cx", "Out cy", "位移px"]
    cell_text  = []
    for n in names_list:
        cx_i, cy_i = results_in[n]
        cx_o, cy_o = results_out[n]
        shift = centroid_shifts[n]
        cell_text.append([n, f"{cx_i:.1f}", f"{cy_i:.1f}", f"{cx_o:.1f}", f"{cy_o:.1f}", f"{shift:.2f}"])
    # Spread row
    cell_text.append([
        "spread(std)",
        f"cx:{spread_cx_in:.2f}",
        f"cy:{spread_cy_in:.2f}",
        f"cx:{spread_cx_out:.2f}",
        f"cy:{spread_cy_out:.2f}",
        f"max:{max(max_dist_in, max_dist_out):.2f}",
    ])

    table = ax_right.table(cellText=cell_text, colLabels=col_labels,
                           loc='center', cellLoc='center')
    table.auto_set_font_size(False)
    table.set_fontsize(9)
    table.scale(1, 2)
    ax_right.set_title("數值對比", pad=12)

    fig.suptitle("Centroid 估算器比較分析", fontsize=13)
    fig.tight_layout()
    fig.savefig(OUT_FIGURES / "05_centroid_comparison.png", dpi=120, bbox_inches='tight')
    plt.close(fig)

    return {
        "input_centroid_results":    {n: list(results_in[n])  for n in names_list},
        "output_centroid_results":   {n: list(results_out[n]) for n in names_list},
        "spread_cx_in":    _safe_float(spread_cx_in),
        "spread_cy_in":    _safe_float(spread_cy_in),
        "spread_cx_out":   _safe_float(spread_cx_out),
        "spread_cy_out":   _safe_float(spread_cy_out),
        "max_pairwise_distance_in":  _safe_float(max_dist_in),
        "max_pairwise_distance_out": _safe_float(max_dist_out),
        "centroid_shifts_px":        {n: _safe_float(v) for n, v in centroid_shifts.items()},
    }


# ---------------------------------------------------------------------------
# ANALYSIS 6: RADIAL PSD
# ---------------------------------------------------------------------------

def analyze_radial_psd(img_in, img_out, H, W, peak_r, fwhm):
    """Compute and compare azimuthally-averaged radial Power Spectral Density."""
    min_dim = min(H, W)
    max_freq_bins = min_dim // 2

    fy = np.fft.fftfreq(H)
    fx = np.fft.fftfreq(W)
    FX, FY = np.meshgrid(fx, fy)
    freq_rr = np.sqrt(FX**2 + FY**2)

    freq_bin_idx = np.round(freq_rr * min_dim).astype(np.int64)
    freq_bin_idx = np.clip(freq_bin_idx, 0, max_freq_bins).ravel()

    def compute_psd(img):
        win  = np.outer(np.hanning(H), np.hanning(W))
        win_mean = win.mean() + 1e-12
        fft2 = np.fft.fft2(img * win / win_mean)
        psd2d = (np.abs(fft2)**2).ravel()

        radial_sum = np.bincount(freq_bin_idx, weights=psd2d, minlength=max_freq_bins + 1)
        radial_cnt = np.bincount(freq_bin_idx, minlength=max_freq_bins + 1)
        radial_psd = radial_sum / (radial_cnt + 1e-12)
        return radial_psd[1:]  # skip DC bin 0

    psd_in  = compute_psd(img_in)
    psd_out = compute_psd(img_out)

    freq_axis = np.arange(1, max_freq_bins + 1) / min_dim  # cycles/pixel

    # Normalize to value at lowest non-DC bin
    psd_in_norm  = psd_in  / (psd_in[0]  + 1e-12)
    psd_out_norm = psd_out / (psd_out[0] + 1e-12)

    ratio = psd_out_norm / (psd_in_norm + 1e-12)

    ring_structure_freq = 1.0 / (2.0 * fwhm)

    # -3dB crossover: first index where ratio < 0.5
    crossover_idx = np.where(ratio < 0.5)[0]
    crossover_3db_freq = float(freq_axis[crossover_idx[0]]) if len(crossover_idx) > 0 else None

    psd_ratio_at_ring_freq = float(np.interp(ring_structure_freq, freq_axis, ratio))
    high_freq_mask = freq_axis > 0.1
    psd_ratio_at_high_freq = float(np.mean(ratio[high_freq_mask])) if np.any(high_freq_mask) else None

    # ---- Plot ----
    fig, (ax_top, ax_bot) = plt.subplots(2, 1, figsize=(12, 8))

    ax_top.plot(freq_axis, np.log10(psd_in_norm  + 1e-20),
                color='steelblue', linewidth=1.5, label='Input')
    ax_top.plot(freq_axis, np.log10(psd_out_norm + 1e-20),
                color='darkorange', linewidth=1.5, label='Output')
    ax_top.set_xscale('log')
    ax_top.axvline(ring_structure_freq, color='green', linestyle='--', alpha=0.7,
                   label=f"ring結構頻率={ring_structure_freq:.4f}")
    if crossover_3db_freq is not None:
        ax_top.axvline(crossover_3db_freq, color='red', linestyle=':', alpha=0.7,
                       label=f"-3dB交叉={crossover_3db_freq:.4f}")
    ax_top.set_xlabel("空間頻率 (cycles/pixel)")
    ax_top.set_ylabel("log₁₀(正規化功率)")
    ax_top.set_title("徑向功率譜密度（完整曲線）")
    ax_top.legend(fontsize=9)
    ax_top.grid(True, alpha=0.3)

    ax_bot.plot(freq_axis, ratio, color='purple', linewidth=1.5, label='PSD ratio')
    ax_bot.set_xscale('log')
    ax_bot.axhline(1.0, color='gray', linestyle='--', alpha=0.5, label="ratio=1.0 (基準)")
    ax_bot.axhline(0.5, color='red',  linestyle='--', alpha=0.5, label="-3dB (ratio=0.5)")
    if crossover_3db_freq is not None:
        ax_bot.axvline(crossover_3db_freq, color='red', linestyle=':', alpha=0.7)
        ax_bot.plot(crossover_3db_freq, 0.5, 'ro', markersize=8,
                    label=f"crossover={crossover_3db_freq:.4f}")
    ax_bot.set_xlabel("空間頻率 (cycles/pixel)")
    ax_bot.set_ylabel("PSD 比率 (output/input)")
    ax_bot.set_title("PSD 比率曲線 (output/input)")
    ax_bot.legend(fontsize=9)
    ax_bot.grid(True, alpha=0.3)

    crossover_str = f"{crossover_3db_freq:.4f}" if crossover_3db_freq is not None else "未找到"
    fig.suptitle(
        f"完整徑向功率譜密度分析\n"
        f"-3dB crossover={crossover_str} c/px | ring頻率={ring_structure_freq:.4f} c/px",
        fontsize=12
    )
    fig.tight_layout()
    fig.savefig(OUT_FIGURES / "06_radial_psd.png", dpi=120, bbox_inches='tight')
    plt.close(fig)

    return {
        "crossover_3db_freq":       _safe_float(crossover_3db_freq),
        "ring_structure_freq":      _safe_float(ring_structure_freq),
        "psd_ratio_at_ring_freq":   _safe_float(psd_ratio_at_ring_freq),
        "psd_ratio_at_high_freq":   _safe_float(psd_ratio_at_high_freq),
    }


# ---------------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------------

def main():
    OUT_FIGURES.mkdir(parents=True, exist_ok=True)
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)

    # Load images
    img_in  = imread_gray(INPUT_PATH)
    img_out = imread_gray(OUTPUT_PATH)

    img_in  = img_in.astype(np.float32)
    img_out = img_out.astype(np.float32)
    H, W    = img_in.shape

    # Load ring geometry from basic_metrics.json
    with open(BASIC_JSON, encoding="utf-8") as f:
        bm = json.load(f)

    cx            = float(bm["output_ring"]["center_x"])
    cy            = float(bm["output_ring"]["center_y"])
    peak_r        = float(bm["output_ring"]["peak_radius"])
    fwhm          = float(bm["output_ring"]["fwhm"])
    peak_gray_in  = float(bm["input_ring_profile"]["peak_gray"])
    peak_gray_out = float(bm["output_ring_profile"]["peak_gray"])
    bg_gray_in    = float(bm["input_ring_profile"]["local_background_gray"])
    bg_gray_out   = float(bm["output_ring_profile"]["local_background_gray"])

    # Build coordinate grids
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    rr     = np.sqrt((xx - cx)**2 + (yy - cy)**2)
    angle_map = np.degrees(np.arctan2(yy - cy, xx - cx))  # -180..180

    # Build masks
    ring_inner_r = peak_r - fwhm / 2.0
    ring_outer_r = peak_r + fwhm / 2.0
    ring_mask = (rr >= ring_inner_r) & (rr <= ring_outer_r)  # noqa: F841
    bg_mask   = rr > (ring_outer_r + 25)

    metrics = {}

    analysis_tasks = [
        ("azimuthal_uniformity",  analyze_azimuthal_uniformity,
         (img_in, img_out, cx, cy, peak_r, fwhm, rr, angle_map)),
        ("background_anisotropy", analyze_background_anisotropy,
         (img_in, img_out, bg_mask)),
        ("profile_asymmetry",     analyze_profile_asymmetry,
         (img_in, img_out, cx, cy, peak_r, fwhm, rr, yy, xx)),
        ("ringing_artifact",      analyze_ringing_artifact,
         (img_in, img_out, cx, cy, peak_r, fwhm, rr,
          bg_gray_in, bg_gray_out, peak_gray_in, peak_gray_out)),
        ("centroid_estimators",   analyze_centroid_estimators,
         (INPUT_PATH, OUTPUT_PATH, cx, cy, peak_r)),
        ("radial_psd",            analyze_radial_psd,
         (img_in, img_out, H, W, peak_r, fwhm)),
    ]

    for name, func, args in analysis_tasks:
        print(f"Running {name}...")
        try:
            result = func(*args)
            metrics[name] = result if result is not None else {"status": "unavailable"}
            print(f"  OK")
        except Exception as e:
            import traceback
            print(f"  ERROR: {e}")
            traceback.print_exc()
            metrics[name] = {"error": str(e)}

    # JSON serializer for numpy types
    def json_default(obj):
        if isinstance(obj, (np.integer,)):
            return int(obj)
        if isinstance(obj, (np.floating,)):
            v = float(obj)
            return None if (np.isnan(v) or np.isinf(v)) else v
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        raise TypeError(f"Object of type {type(obj)} is not JSON serializable")

    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump(metrics, f, indent=2, ensure_ascii=False, default=json_default)

    print(f"\nAll analyses complete. Metrics saved to:\n  {OUT_JSON}")
    print(f"Figures saved to:\n  {OUT_FIGURES}")


if __name__ == "__main__":
    main()

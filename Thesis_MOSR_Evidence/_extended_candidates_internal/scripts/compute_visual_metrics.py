"""Compute 4 visual metrics for all 13 candidates' r26 sequence recon BMPs.

Visual metrics (matching a025 capability_eval convention):
  - gradient_magnitude_mean (Sobel magnitude, mean over image)
  - edge_steepness_p95     (mean Sobel mag in top-5% gradient pixels)
  - contrast_std           (std of normalised intensity)
  - edge_contrast_p99_minus_p1 (P99 - P1 intensity range)

For each (candidate, pitch), averages over all frames in the recon dir.

Output:
  results/visual_metrics_table.csv  — long format (candidate, pitch, metric, value)
  results/visual_metrics_pivot.csv  — wide format (one row per candidate, columns = pitch x metric)
  results/visual_metrics_avg.csv    — per-candidate avg across 3 pitches

Usage:
    python compute_visual_metrics.py
"""

from __future__ import annotations

import csv
import sys
from pathlib import Path

import cv2
import numpy as np


REPO_ROOT = Path(__file__).resolve().parents[3]
WORK_ROOT = REPO_ROOT / "Thesis_MOSR_Evidence" / "_extended_candidates_internal"
OUT_ROOT = WORK_ROOT / "results"

# Candidate -> base recon dir (the dir that contains pitch{1um,0p1um,0p01um}_y_*_odd subdirs)
# Existing baselines:
BASELINE_RECON = {
    # R30 / R33 / R38v2 / COMBO: 來自 720angle_analysis dir 內的 recon BMP (這個 dir 通常只有 analysis png,
    # 但 720-angle 跑前必須有 recon BMP source dir;讓 script 嘗試從這個 sequence_analysis dir 反推 recon dir)
    "R30":   REPO_ROOT / "Experiments/R38v2SeqFixed/results/720angle_analysis_recon/R30",  # 不一定存在;若不存在跳過
    "R33":   REPO_ROOT / "Experiments/R38v2SeqFixed/results/720angle_analysis_recon/R33",
    "R38v2": REPO_ROOT / "Experiments/R38v2SeqFixed/results/720angle_analysis_recon/R38v2",
    "COMBO": REPO_ROOT / "Experiments/R38v2SeqFixed/results/720angle_analysis_recon/COMBO",
}

# Extended candidates (recon under this script's _recon root):
EXTENDED_RECON = {
    "a030":         WORK_ROOT / "_recon" / "a030",
    "a025":         WORK_ROOT / "_recon" / "a025",
    "R40_a045":     WORK_ROOT / "_recon" / "R40_a045",
    "R42_r41best":  WORK_ROOT / "_recon" / "R42_r41best",
    "R46":          WORK_ROOT / "_recon" / "R46",
}

# Ablation candidates (recon under method_ablations/_ablation_recon):
ABLATION_RECON = {
    "ABLA_NO_SEQ":  REPO_ROOT / "Thesis_MOSR_Evidence/method_ablations/_ablation_recon/NO_SEQ",
    "ABLA_NO_EQ":   REPO_ROOT / "Thesis_MOSR_Evidence/method_ablations/_ablation_recon/NO_EQ",
    "ABLA_NO_EDGE": REPO_ROOT / "Thesis_MOSR_Evidence/method_ablations/_ablation_recon/NO_EDGE",
    "ABLA_NO_FREQ": REPO_ROOT / "Thesis_MOSR_Evidence/method_ablations/_ablation_recon/NO_FREQ",
}

PITCHES = [
    {"short": "pitch1um_y_100",   "gmf_label": "8px"},
    {"short": "pitch0p1um_y_60",  "gmf_label": "0p8px"},
    {"short": "pitch0p01um_y_40", "gmf_label": "0p08px"},
]

METRIC_KEYS = ("gradient_magnitude_mean", "edge_steepness_p95",
               "contrast_std", "edge_contrast_p99_minus_p1")


def visual_stats(folder: Path) -> dict:
    accs = {k: 0.0 for k in METRIC_KEYS}
    n = 0
    for p in sorted(folder.glob("*.bmp")):
        img = cv2.imread(str(p), cv2.IMREAD_GRAYSCALE)
        if img is None:
            continue
        f = img.astype(np.float32) / 255.0
        gx = cv2.Sobel(f, cv2.CV_32F, 1, 0, ksize=3)
        gy = cv2.Sobel(f, cv2.CV_32F, 0, 1, ksize=3)
        gmag = np.sqrt(gx * gx + gy * gy)
        edge_mask = gmag > np.percentile(gmag, 95)
        accs["gradient_magnitude_mean"] += float(gmag.mean())
        accs["edge_steepness_p95"] += float(gmag[edge_mask].mean()) if edge_mask.any() else 0.0
        accs["contrast_std"] += float(f.std())
        accs["edge_contrast_p99_minus_p1"] += float(np.percentile(f, 99) - np.percentile(f, 1))
        n += 1
    return {k: v / n for k, v in accs.items()} if n else {k: float("nan") for k in accs}


def find_pitch_dir(base: Path, pitch_short: str) -> Path | None:
    """Find <base>/.../<pitch_short>_odd dir containing BMPs."""
    # Try direct subdir
    direct = base / f"{pitch_short}_odd"
    if direct.exists() and any(direct.glob("*.bmp")):
        return direct
    # Try nested under reconstruct_progress_*
    for sub in base.rglob(f"{pitch_short}_odd"):
        if sub.is_dir() and any(sub.glob("*.bmp")):
            return sub
    # Try without _odd suffix (some recon dirs use plain pitch_short)
    plain = base / pitch_short
    if plain.exists() and any(plain.glob("*.bmp")):
        return plain
    return None


def main():
    OUT_ROOT.mkdir(parents=True, exist_ok=True)
    long_rows = []
    pivot_rows = []
    avg_rows = []

    all_candidates = list(BASELINE_RECON.items()) + list(EXTENDED_RECON.items()) + list(ABLATION_RECON.items())

    print(f"{'cand':<14} {'pitch':<22} {'n_frames':>8} {'grad_mean':>10} {'edge_p95':>10} {'contrast':>10} {'p99-p1':>10}")
    print("-" * 90)

    for cand, base in all_candidates:
        pivot = {"candidate": cand}
        avg_accs = {k: [] for k in METRIC_KEYS}
        for pitch in PITCHES:
            recon_dir = find_pitch_dir(base, pitch["short"])
            if recon_dir is None:
                print(f"{cand:<14} {pitch['short']:<22} {'MISSING':>8}")
                for k in METRIC_KEYS:
                    long_rows.append({"candidate": cand, "pitch": pitch["gmf_label"],
                                       "metric": k, "value": None, "n_frames": 0})
                    pivot[f"{pitch['gmf_label']}_{k}"] = None
                continue
            stats = visual_stats(recon_dir)
            n_frames = len(list(recon_dir.glob("*.bmp")))
            print(f"{cand:<14} {pitch['short']:<22} {n_frames:>8} "
                  f"{stats['gradient_magnitude_mean']:>10.4f} "
                  f"{stats['edge_steepness_p95']:>10.4f} "
                  f"{stats['contrast_std']:>10.4f} "
                  f"{stats['edge_contrast_p99_minus_p1']:>10.4f}")
            for k, v in stats.items():
                long_rows.append({"candidate": cand, "pitch": pitch["gmf_label"],
                                   "metric": k, "value": v, "n_frames": n_frames})
                pivot[f"{pitch['gmf_label']}_{k}"] = v
                if v == v:  # not NaN
                    avg_accs[k].append(v)
        pivot_rows.append(pivot)
        avg = {"candidate": cand}
        for k in METRIC_KEYS:
            avg[f"avg_{k}"] = sum(avg_accs[k]) / len(avg_accs[k]) if avg_accs[k] else None
        avg_rows.append(avg)

    # write long
    with open(OUT_ROOT / "visual_metrics_table.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["candidate", "pitch", "metric", "value", "n_frames"])
        w.writeheader()
        w.writerows(long_rows)
    # write pivot
    if pivot_rows:
        fields = ["candidate"] + sorted(set(k for r in pivot_rows for k in r if k != "candidate"))
        with open(OUT_ROOT / "visual_metrics_pivot.csv", "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=fields)
            w.writeheader()
            w.writerows(pivot_rows)
    # write avg
    if avg_rows:
        fields = ["candidate"] + [f"avg_{k}" for k in METRIC_KEYS]
        with open(OUT_ROOT / "visual_metrics_avg.csv", "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=fields)
            w.writeheader()
            w.writerows(avg_rows)

    print(f"\nwrote:")
    print(f"  {OUT_ROOT / 'visual_metrics_table.csv'}")
    print(f"  {OUT_ROOT / 'visual_metrics_pivot.csv'}")
    print(f"  {OUT_ROOT / 'visual_metrics_avg.csv'}")


if __name__ == "__main__":
    main()

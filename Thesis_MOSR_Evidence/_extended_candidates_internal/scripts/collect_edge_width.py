"""Collect edge-width μ_w + CV_w from existing 720-angle per_frame_metrics.json.

Corresponds to 論文 4.8.3 (邊界寬度一致性).

For each (candidate, pitch, boundary), extracts the per-frame
output_<bdy>_edge_width_mean series and computes:
  - mu_w   = mean across frames        (邊界銳利度,越小越銳)
  - cv_w   = std/mean across frames    (跨幀一致性,越小越穩定)

Sources:
  R30/R33/R38v2/COMBO  -> Experiments/R38v2SeqFixed/results/720angle_analysis/<cand>/<pitch>/per_frame_metrics.json
  4 ablation           -> Thesis_MOSR_Evidence/method_ablations/_ablation_720angle/<TAG>/<pitch>/per_frame_metrics.json
  5 extended           -> Thesis_MOSR_Evidence/_extended_candidates_internal/_720angle/<TAG>/<pitch>/per_frame_metrics.json

Output:
  results/edge_width_table.csv  — (candidate, pitch, boundary, n_frames, input_mu_w, output_mu_w, input_cv_w, output_cv_w)

Usage:
    python collect_edge_width.py
"""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

import numpy as np


REPO_ROOT = Path(__file__).resolve().parents[3]
OUT_ROOT = REPO_ROOT / "Thesis_MOSR_Evidence" / "_extended_candidates_internal" / "results"

SOURCES = {
    # baseline 4 candidates
    "R30":   REPO_ROOT / "Experiments/R38v2SeqFixed/results/720angle_analysis/R30",
    "R33":   REPO_ROOT / "Experiments/R38v2SeqFixed/results/720angle_analysis/R33",
    "R38v2": REPO_ROOT / "Experiments/R38v2SeqFixed/results/720angle_analysis/R38v2",
    "COMBO": REPO_ROOT / "Experiments/R38v2SeqFixed/results/720angle_analysis/COMBO",
    # 4 ablation
    "ABLA_NO_SEQ":  REPO_ROOT / "Thesis_MOSR_Evidence/method_ablations/_ablation_720angle/NO_SEQ",
    "ABLA_NO_EQ":   REPO_ROOT / "Thesis_MOSR_Evidence/method_ablations/_ablation_720angle/NO_EQ",
    "ABLA_NO_EDGE": REPO_ROOT / "Thesis_MOSR_Evidence/method_ablations/_ablation_720angle/NO_EDGE",
    "ABLA_NO_FREQ": REPO_ROOT / "Thesis_MOSR_Evidence/method_ablations/_ablation_720angle/NO_FREQ",
    # 5 extended (populated after run_extended_inference_720angle.py finishes)
    "a030":         REPO_ROOT / "Thesis_MOSR_Evidence/_extended_candidates_internal/_720angle/a030",
    "a025":         REPO_ROOT / "Thesis_MOSR_Evidence/_extended_candidates_internal/_720angle/a025",
    "R40_a045":     REPO_ROOT / "Thesis_MOSR_Evidence/_extended_candidates_internal/_720angle/R40_a045",
    "R42_r41best":  REPO_ROOT / "Thesis_MOSR_Evidence/_extended_candidates_internal/_720angle/R42_r41best",
    "R46":          REPO_ROOT / "Thesis_MOSR_Evidence/_extended_candidates_internal/_720angle/R46",
}

PITCHES = [
    ("pitch1um_y_100", "8 px"),
    ("pitch0p1um_y_60", "0.8 px"),
    ("pitch0p01um_y_40", "0.08 px"),
]

BOUNDARIES = ("outer", "inner")


def mu_cv(values):
    """Return (mean, cv_pct, n). Skips NaN."""
    arr = np.asarray([v for v in values if v is not None and not (isinstance(v, float) and (v != v))], dtype=float)
    arr = arr[np.isfinite(arr)]
    n = len(arr)
    if n < 2:
        return (float("nan"), float("nan"), n)
    mu = float(arr.mean())
    if abs(mu) < 1e-12:
        cv = float("nan")
    else:
        cv = float(arr.std(ddof=1) / mu * 100.0)
    return (mu, cv, n)


def main():
    OUT_ROOT.mkdir(parents=True, exist_ok=True)
    rows = []
    print(f"{'cand':<14} {'pitch':<10} {'bdy':<6} {'n':>4} {'in_mu_w':>8} {'out_mu_w':>9} {'in_cv_w%':>9} {'out_cv_w%':>10} {'mu_drop%':>9}")
    print("-" * 90)

    for cand, base in SOURCES.items():
        for pitch_short, pitch_label in PITCHES:
            json_path = base / pitch_short / "per_frame_metrics.json"
            if not json_path.exists():
                for bdy in BOUNDARIES:
                    print(f"{cand:<14} {pitch_label:<10} {bdy:<6} {'-':>4} {'MISSING':>8}")
                    rows.append({
                        "candidate": cand, "pitch": pitch_label, "boundary": bdy,
                        "status": "MISSING_JSON",
                    })
                continue
            try:
                with open(json_path, encoding="utf-8") as f:
                    data = json.load(f)
            except Exception as e:
                print(f"{cand:<14} {pitch_label:<10} {'PARSE_ERR':<6} {str(e)[:30]}")
                continue
            inp = data.get("input", [])
            out = data.get("output", [])
            for bdy in BOUNDARIES:
                key = f"{bdy}_edge_width_mean"
                in_vals = [r.get(key) for r in inp]
                out_vals = [r.get(key) for r in out]
                in_mu, in_cv, n_in = mu_cv(in_vals)
                out_mu, out_cv, n_out = mu_cv(out_vals)
                mu_drop = (1 - out_mu / in_mu) * 100 if in_mu and not np.isnan(in_mu) and not np.isnan(out_mu) else float("nan")
                print(f"{cand:<14} {pitch_label:<10} {bdy:<6} {n_out:>4d} "
                      f"{in_mu:>8.3f} {out_mu:>9.3f} {in_cv:>8.2f}% {out_cv:>9.2f}% {mu_drop:>8.1f}%")
                rows.append({
                    "candidate": cand, "pitch": pitch_label, "boundary": bdy, "status": "OK",
                    "n_frames": n_out,
                    "input_mu_w": in_mu, "input_cv_w_pct": in_cv,
                    "output_mu_w": out_mu, "output_cv_w_pct": out_cv,
                    "mu_w_drop_pct": mu_drop,
                })

    fields = ["candidate", "pitch", "boundary", "status", "n_frames",
              "input_mu_w", "input_cv_w_pct", "output_mu_w", "output_cv_w_pct", "mu_w_drop_pct"]
    out_csv = OUT_ROOT / "edge_width_table.csv"
    with open(out_csv, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)
    print(f"\nwrote {out_csv}")


if __name__ == "__main__":
    main()

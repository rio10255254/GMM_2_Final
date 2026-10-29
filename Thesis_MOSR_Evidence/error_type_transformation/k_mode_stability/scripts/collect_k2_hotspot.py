"""Collect k=2 stability + hotspot persistence + center-offset drift
from existing 720-angle analysis JSON.

Source: Experiments/R38v2SeqFixed/results/720angle_analysis/<cand>/<pitch>/sequence_summary.json

This script does not re-run circle fitting; it consolidates already-computed
metrics into a single CSV/markdown table for C3 (k=2 CV) and C4 (hotspot)
verification of the thesis main claim.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path
PROJECT_ROOT = Path(__file__).resolve().parents[4]


ROOT = Path(str(PROJECT_ROOT))
SOURCE = ROOT / "Experiments/R38v2SeqFixed/results/720angle_analysis"
OUT_K = ROOT / "Thesis_MOSR_Evidence/error_type_transformation/k_mode_stability/results"
OUT_H = ROOT / "Thesis_MOSR_Evidence/error_type_transformation/residual_hotspot/results"

CANDIDATES = ["R30", "R33", "R38v2", "COMBO"]
PITCHES = [
    ("pitch0p01um_y_40", "0.08 px"),
    ("pitch0p1um_y_60", "0.8 px"),
    ("pitch1um_y_100", "8 px"),
]


def main():
    rows_k2 = []
    rows_hp = []
    rows_drift = []

    for cand in CANDIDATES:
        for pitch_dir, pitch_label in PITCHES:
            p = SOURCE / cand / pitch_dir / "sequence_summary.json"
            if not p.exists():
                continue
            with open(p, encoding="utf-8") as f:
                d = json.load(f)

            k2 = d.get("k2_stability", {})
            hp = d.get("hotspot_persistence", {})
            cd = d.get("center_offset_drift", {})

            for boundary in ["outer", "inner"]:
                # k=2 stability: compare input vs output
                ki = k2.get(f"input_{boundary}", {}) or {}
                ko = k2.get(f"output_{boundary}", {}) or {}
                rows_k2.append({
                    "candidate": cand,
                    "scale": pitch_label,
                    "boundary": boundary,
                    "input_k2_amp_mean": ki.get("k2_amp_mean"),
                    "input_k2_amp_cv_pct": ki.get("k2_amp_cv_pct"),
                    "input_k2_phase_std_deg": ki.get("k2_phase_circ_std_deg"),
                    "output_k2_amp_mean": ko.get("k2_amp_mean"),
                    "output_k2_amp_cv_pct": ko.get("k2_amp_cv_pct"),
                    "output_k2_phase_std_deg": ko.get("k2_phase_circ_std_deg"),
                    "k2_cv_reduction_pct": (
                        (1 - ko.get("k2_amp_cv_pct") / ki.get("k2_amp_cv_pct")) * 100
                        if ki.get("k2_amp_cv_pct") and ko.get("k2_amp_cv_pct") is not None
                        else None
                    ),
                    "verdict": k2.get("verdict"),
                })

                # hotspot persistence
                hi = hp.get(f"input_{boundary}", {}) or {}
                ho = hp.get(f"output_{boundary}", {}) or {}
                rows_hp.append({
                    "candidate": cand,
                    "scale": pitch_label,
                    "boundary": boundary,
                    "input_n_persistent_angles": hi.get("n_persistent_angles_gt50pct"),
                    "input_persist_fraction": hi.get("persistent_angle_fraction_gt50pct"),
                    "input_mean_persistence": hi.get("mean_persistence"),
                    "input_max_persistence": hi.get("max_persistence"),
                    "output_n_persistent_angles": ho.get("n_persistent_angles_gt50pct"),
                    "output_persist_fraction": ho.get("persistent_angle_fraction_gt50pct"),
                    "output_mean_persistence": ho.get("mean_persistence"),
                    "output_max_persistence": ho.get("max_persistence"),
                    "persist_amplification": (
                        ho.get("persistent_angle_fraction_gt50pct") / hi.get("persistent_angle_fraction_gt50pct")
                        if hi.get("persistent_angle_fraction_gt50pct") and ho.get("persistent_angle_fraction_gt50pct")
                        else None
                    ),
                })

            # drift
            di = cd.get("input", {}) or {}
            do = cd.get("output", {}) or {}
            rows_drift.append({
                "candidate": cand,
                "scale": pitch_label,
                "input_drift_mean_px": di.get("mean"),
                "input_drift_std_px": di.get("std"),
                "input_trend_px_per_frame": di.get("trend_px_per_frame"),
                "output_drift_mean_px": do.get("mean"),
                "output_drift_std_px": do.get("std"),
                "output_trend_px_per_frame": do.get("trend_px_per_frame"),
                "drift_verdict": cd.get("verdict"),
            })

    # write k=2 CSV
    OUT_K.mkdir(parents=True, exist_ok=True)
    with open(OUT_K / "k2_stability_table.csv", "w", newline="", encoding="utf-8") as f:
        if rows_k2:
            w = csv.DictWriter(f, fieldnames=list(rows_k2[0].keys()))
            w.writeheader()
            w.writerows(rows_k2)
    print(f"wrote {OUT_K / 'k2_stability_table.csv'} ({len(rows_k2)} rows)")

    # write hotspot CSV
    OUT_H.mkdir(parents=True, exist_ok=True)
    with open(OUT_H / "hotspot_persistence_table.csv", "w", newline="", encoding="utf-8") as f:
        if rows_hp:
            w = csv.DictWriter(f, fieldnames=list(rows_hp[0].keys()))
            w.writeheader()
            w.writerows(rows_hp)
    print(f"wrote {OUT_H / 'hotspot_persistence_table.csv'} ({len(rows_hp)} rows)")

    # write drift CSV (next to k2)
    with open(OUT_K / "center_offset_drift_table.csv", "w", newline="", encoding="utf-8") as f:
        if rows_drift:
            w = csv.DictWriter(f, fieldnames=list(rows_drift[0].keys()))
            w.writeheader()
            w.writerows(rows_drift)
    print(f"wrote {OUT_K / 'center_offset_drift_table.csv'} ({len(rows_drift)} rows)")

    # print summary to stdout for quick scan
    print("\n=== k=2 CV summary (output side, what model produces) ===")
    print(f"{'cand':<8} {'scale':<8} {'bound':<6} {'in_cv%':>8} {'out_cv%':>8} {'reduction%':>11} {'verdict':<15}")
    print("-" * 70)
    for r in rows_k2:
        print(f"{r['candidate']:<8} {r['scale']:<8} {r['boundary']:<6} "
              f"{r['input_k2_amp_cv_pct'] or 0:>8.2f} "
              f"{r['output_k2_amp_cv_pct'] or 0:>8.2f} "
              f"{r['k2_cv_reduction_pct'] or 0:>10.1f}% "
              f"{r['verdict'] or 'n/a':<15}")

    print("\n=== hotspot persistence (output side) ===")
    print(f"{'cand':<8} {'scale':<8} {'bound':<6} {'in_pf':>7} {'out_pf':>7} {'amplify':>8}")
    print("-" * 60)
    for r in rows_hp:
        amp = r['persist_amplification']
        amp_str = f"{amp:>7.1f}x" if amp else "    n/a"
        print(f"{r['candidate']:<8} {r['scale']:<8} {r['boundary']:<6} "
              f"{r['input_persist_fraction'] or 0:>7.3f} "
              f"{r['output_persist_fraction'] or 0:>7.3f} "
              f"{amp_str}")


if __name__ == "__main__":
    main()

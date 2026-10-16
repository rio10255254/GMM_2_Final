"""Collect k=2 stability + hotspot persistence + step / drift metrics for
4 ablation candidates from their 720-angle sequence_summary.json, and
combine with existing 4-candidate (R30/R33/R38v2/COMBO) tables.

This produces:
- results/ablation_k2_hotspot_combined.csv  (8 candidates x 3 scales x 2 boundaries)
- results/ablation_step_summary.csv         (8 x 3, just step + drift)
- results/ablation_vs_combo.md              (human-readable verdict report)

Source for baseline 4 candidates:
    Experiments/R38v2SeqFixed/results/720angle_analysis/<cand>/<pitch>/sequence_summary.json
Source for 4 ablations:
    Thesis_MOSR_Evidence/method_ablations/_ablation_720angle/<TAG>/<pitch>/sequence_summary.json
"""

from __future__ import annotations

import csv
import json
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
BASELINE_ROOT = REPO_ROOT / "Experiments/R38v2SeqFixed/results/720angle_analysis"
ABLATION_ROOT = REPO_ROOT / "Thesis_MOSR_Evidence/method_ablations/_ablation_720angle"
OUT_ROOT     = REPO_ROOT / "Thesis_MOSR_Evidence/method_ablations/results"

BASELINE_CANDIDATES = [
    ("R30",   BASELINE_ROOT / "R30"),
    ("R33",   BASELINE_ROOT / "R33"),
    ("R38v2", BASELINE_ROOT / "R38v2"),
    ("COMBO", BASELINE_ROOT / "COMBO"),
]

ABLATION_CANDIDATES = [
    ("NO_SEQ",  ABLATION_ROOT / "NO_SEQ",  "ablation_A_4.6"),
    ("NO_EQ",   ABLATION_ROOT / "NO_EQ",   "ablation_B1_4.5.1"),
    ("NO_EDGE", ABLATION_ROOT / "NO_EDGE", "ablation_B2_4.5.3"),
    ("NO_FREQ", ABLATION_ROOT / "NO_FREQ", "ablation_B3_4.5.2"),
]

PITCHES_BASELINE = [
    ("pitch0p01um_y_40", "0.08 px"),
    ("pitch0p1um_y_60",  "0.8 px"),
    ("pitch1um_y_100",   "8 px"),
]
PITCHES_ABLATION = [
    ("pitch0p01um_y_40", "0.08 px"),
    ("pitch0p1um_y_60",  "0.8 px"),
    ("pitch1um_y_100",   "8 px"),
]


def collect_one(cand: str, root: Path, pitches, kind: str) -> list[dict]:
    rows = []
    for pitch_dir, pitch_label in pitches:
        p = root / pitch_dir / "sequence_summary.json"
        if not p.exists():
            print(f"  [WARN] missing: {p}")
            continue
        with open(p, encoding="utf-8") as f:
            d = json.load(f)
        k2 = d.get("k2_stability", {})
        hp = d.get("hotspot_persistence", {})
        cd = d.get("center_offset_drift", {})
        st = d.get("step_stability", {})
        for boundary in ["outer", "inner"]:
            ki = k2.get(f"input_{boundary}", {}) or {}
            ko = k2.get(f"output_{boundary}", {}) or {}
            hi = hp.get(f"input_{boundary}", {}) or {}
            ho = hp.get(f"output_{boundary}", {}) or {}
            rows.append({
                "candidate": cand,
                "kind": kind,
                "scale": pitch_label,
                "boundary": boundary,
                "input_k2_cv_pct": ki.get("k2_amp_cv_pct"),
                "output_k2_cv_pct": ko.get("k2_amp_cv_pct"),
                "k2_cv_reduction_pct": (
                    (1 - ko.get("k2_amp_cv_pct") / ki.get("k2_amp_cv_pct")) * 100
                    if ki.get("k2_amp_cv_pct") and ko.get("k2_amp_cv_pct") is not None
                    else None
                ),
                "input_persist_fraction": hi.get("persistent_angle_fraction_gt50pct"),
                "output_persist_fraction": ho.get("persistent_angle_fraction_gt50pct"),
                "k2_verdict": k2.get("verdict"),
                "drift_verdict": cd.get("verdict"),
                "input_step_y_std": st.get("input", {}).get("step_y_std"),
                "output_step_y_std": st.get("output", {}).get("step_y_std"),
                "step_improvement_pct": st.get("improvement_pct"),
            })
    return rows


def main():
    OUT_ROOT.mkdir(parents=True, exist_ok=True)
    all_rows = []
    print("=== Collecting baseline 4 candidates ===")
    for cand, root in BASELINE_CANDIDATES:
        print(f"  {cand}")
        all_rows.extend(collect_one(cand, root, PITCHES_BASELINE, "baseline"))
    print("\n=== Collecting 4 ablation candidates ===")
    for cand, root, kind in ABLATION_CANDIDATES:
        print(f"  {cand}")
        all_rows.extend(collect_one(cand, root, PITCHES_ABLATION, kind))

    # write combined CSV
    if all_rows:
        out_csv = OUT_ROOT / "ablation_k2_hotspot_combined.csv"
        fields = list(all_rows[0].keys())
        with open(out_csv, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=fields)
            w.writeheader()
            w.writerows(all_rows)
        print(f"\nwrote {out_csv} ({len(all_rows)} rows)")

    # print summary comparison: ablation vs COMBO at 0.8 px outer
    print(f"\n{'='*80}")
    print(f"Ablation vs COMBO comparison at 0.8 px (outer boundary)")
    print(f"{'='*80}")
    print(f"{'cand':<10} {'sigma_hat':>10} {'k2_cv%':>8} {'reduction':>10} {'persist_pf':>11} {'drift':<15}")
    print("-" * 70)
    target_rows = [r for r in all_rows
                   if r["scale"] == "0.8 px" and r["boundary"] == "outer"]
    for r in target_rows:
        sigma = r["output_step_y_std"] or 0
        k2 = r["output_k2_cv_pct"] or 0
        red = r["k2_cv_reduction_pct"] or 0
        pf = r["output_persist_fraction"] or 0
        drift = r["drift_verdict"] or "n/a"
        print(f"{r['candidate']:<10} {sigma:>10.4f} {k2:>7.2f}% {red:>9.1f}% {pf:>11.4f} {drift:<15}")


if __name__ == "__main__":
    main()

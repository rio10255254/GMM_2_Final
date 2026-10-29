"""Post-training ablation analyzer — runs after each ablation finishes.

For each completed ablation, this script:
1. Locates the latest Traing_Progress dir matching the ablation tag
2. Reports best_tradeoff.pth.tar location for downstream external GMF
3. Reports training summary (final epoch metrics)

This is a thin wrapper; full sigma+b / k=2 / hotspot evaluation still
requires running the candidate through external GMF + 720-angle pipeline,
then adding the candidate to existing collectors.

Usage:
    python Thesis_MOSR_Evidence/method_ablations/analyze_ablation.py
    python Thesis_MOSR_Evidence/method_ablations/analyze_ablation.py --tag NO_SEQ
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


_REPO_ROOT = Path(__file__).resolve().parents[2]
PROGRESS_ROOT = _REPO_ROOT / "Traing_Progress"


ABLATION_TAGS = [
    ("NO_SEQ", "Ablation A: single-frame baseline (4.6)"),
    ("NO_EQ", "Ablation B1: no equivariance residual (4.5.1)"),
    ("NO_EDGE", "Ablation B2: no edge differential residual (4.5.3)"),
    ("NO_FREQ", "Ablation B3: no frequency-domain residual (4.5.2)"),
]


def find_latest_run(tag: str):
    """Find the latest Traing_Progress dir matching tag."""
    candidates = sorted(
        PROGRESS_ROOT.glob(f"training_progress_GESR_v1_v5_ST0p8_SWP_*{tag}*"),
        key=lambda p: p.stat().st_mtime if p.exists() else 0,
    )
    return candidates[-1] if candidates else None


def report_run(tag: str, description: str):
    print(f"\n--- {tag} ---")
    print(f"  {description}")
    run_dir = find_latest_run(tag)
    if run_dir is None:
        print(f"  status: NOT_STARTED (no Traing_Progress dir matches *{tag}*)")
        return None
    print(f"  dir:    {run_dir}")
    ckpt = run_dir / "weights" / "best_tradeoff.pth.tar"
    if ckpt.exists():
        size_mb = ckpt.stat().st_size / (1024 * 1024)
        print(f"  ckpt:   {ckpt}  ({size_mb:.1f} MB)")
    else:
        print(f"  ckpt:   NOT FOUND (training may not have reached best epoch yet)")
    # try to find a metrics csv or json
    for fname in ["metrics_log.csv", "training_progress.csv", "metrics.json"]:
        f = run_dir / fname
        if f.exists():
            print(f"  log:    {f}")
            break
    return run_dir


def main():
    parser = argparse.ArgumentParser(description="Ablation post-training analyzer")
    parser.add_argument("--tag", type=str, default=None,
                        help="Report only this ablation tag (NO_SEQ / NO_EQ / NO_EDGE / NO_FREQ)")
    args = parser.parse_args()

    print(f"\n{'='*70}")
    print(f"Ablation runs registry")
    print(f"  Traing_Progress root: {PROGRESS_ROOT}")
    print(f"{'='*70}")

    queue = ABLATION_TAGS
    if args.tag:
        queue = [t for t in ABLATION_TAGS if t[0] == args.tag.upper()]

    for tag, desc in queue:
        report_run(tag, desc)

    print(f"\n{'='*70}")
    print(f"Next steps after each ablation finishes:")
    print(f"  1. Run external GMF on the ablation's best checkpoint:")
    print(f"     - Use existing inference scripts to produce recon BMP")
    print(f"     - Run GMF tool on recon to produce GMF_score.txt")
    print(f"  2. Add candidate to sigma_b decompose script:")
    print(f"     Thesis_MOSR_Evidence/error_type_transformation/sigma_hat_decomposition/scripts/decompose_sigma_b.py")
    print(f"  3. Run 720-angle analysis on recon:")
    print(f"     Analyses/AnalysisLab/r26/sequence/scripts/run_sequence_analysis.py")
    print(f"  4. Re-run collector for k=2 / hotspot:")
    print(f"     Thesis_MOSR_Evidence/error_type_transformation/k_mode_stability/scripts/collect_k2_hotspot.py")
    print(f"  5. Write verification report comparing ablation vs COMBO")
    print(f"{'='*70}\n")


if __name__ == "__main__":
    main()

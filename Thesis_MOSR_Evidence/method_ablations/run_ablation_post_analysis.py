"""Ablation post-training analysis runner.

For a completed ablation, this script:
1. Locates the latest Traing_Progress dir matching the ablation tag
2. Reports best_tradeoff.pth.tar location
3. Reports final-epoch internal validation metrics (PSNR/SSIM/Rec/Edge)
4. Prints the next manual steps (external GMF recon + sigma_b update +
   720-angle analysis) so the user can chain them

This script does NOT run external GMF (which requires a separate GMF
measurement tool) nor mutate the existing sigma_hat / k_mode / hotspot
collectors. It surfaces what the user needs to do next.

Usage:
    python run_ablation_post_analysis.py --tag NO_SEQ
    python run_ablation_post_analysis.py --tag NO_SEQ --weights <explicit path>
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path


_REPO_ROOT = Path(__file__).resolve().parents[2]
PROGRESS_ROOT = _REPO_ROOT / "Traing_Progress"


ABLATION_REGISTRY = {
    "NO_SEQ": {
        "long_name": "Ablation A: single-frame baseline",
        "thesis_section": "4.6",
        "controlled_flag": "SEQ_ENABLE=False",
        "expected_pattern": (
            "sigma_hat at 0.8px should rise vs COMBO (random component returns); "
            "k=2 outer CV may rise; b drift becomes irregular"
        ),
    },
    "NO_EQ": {
        "long_name": "Ablation B1: no translation equivariance",
        "thesis_section": "4.5.1",
        "controlled_flag": "EQ_PROB=0",
        "expected_pattern": (
            "sigma_hat may rise modestly; b drift becomes irregular; "
            "k=2 CV may rise on inner boundary"
        ),
    },
    "NO_EDGE": {
        "long_name": "Ablation B2: no edge differential residual",
        "thesis_section": "4.5.3",
        "controlled_flag": "W_GRADMAG=W_EDGE_ORI_SIMPLE=W_EDGELOCAL_LAP_*=0",
        "expected_pattern": (
            "boundary position drifts; |b| rises; k=2 amplitude itself increases"
        ),
    },
    "NO_FREQ": {
        "long_name": "Ablation B3: no frequency-domain feasibility residual",
        "thesis_section": "4.5.2",
        "controlled_flag": "W_HF_LAP=0, FFT_W_PHASE=0",
        "expected_pattern": (
            "visually sharper but measurement-worse: sigma_hat may rise, "
            "false high-frequency content appears"
        ),
    },
}


def find_latest_run(tag: str) -> Path | None:
    """Find the latest Traing_Progress dir matching tag (e.g. 'NO_SEQ')."""
    candidates = sorted(
        PROGRESS_ROOT.glob(f"training_progress_GESR_v1_v5_ST0p8_SWP_*{tag}*"),
        key=lambda p: p.stat().st_mtime if p.exists() else 0,
    )
    return candidates[-1] if candidates else None


def find_best_epoch_metrics(run_dir: Path) -> dict | None:
    """Try to extract best-epoch metrics from training logs."""
    # try common metric log filenames
    for fname in ["metrics.csv", "training_progress.csv", "metrics_log.csv"]:
        csv_path = run_dir / fname
        if csv_path.exists():
            try:
                with open(csv_path) as f:
                    rows = list(csv.DictReader(f))
                if not rows:
                    continue
                return {"source": fname, "rows": len(rows), "last_row": rows[-1]}
            except Exception:
                continue
    # try summary JSON
    for fname in ["best_summary.json", "summary.json"]:
        json_path = run_dir / fname
        if json_path.exists():
            try:
                with open(json_path) as f:
                    return {"source": fname, "data": json.load(f)}
            except Exception:
                continue
    return None


def report(tag: str, weights_override: Path | None = None) -> int:
    tag = tag.upper()
    if tag not in ABLATION_REGISTRY:
        print(f"[ERR] unknown tag: {tag}")
        print(f"      valid: {list(ABLATION_REGISTRY)}")
        return 1

    info = ABLATION_REGISTRY[tag]
    print(f"\n{'='*70}")
    print(f"{info['long_name']}")
    print(f"  Thesis section : {info['thesis_section']}")
    print(f"  Ablation point : {info['controlled_flag']}")
    print(f"  Expected       : {info['expected_pattern']}")
    print(f"{'='*70}")

    if weights_override is not None:
        ckpt = weights_override
        run_dir = ckpt.parent.parent
    else:
        run_dir = find_latest_run(tag)
        if run_dir is None:
            print(f"\n[STATUS] NOT_FOUND — no Traing_Progress dir matches *{tag}*")
            print(f"  -> training may not have started or has been moved")
            return 2
        ckpt = run_dir / "weights" / "best_tradeoff.pth.tar"

    print(f"\n[LOCATION]")
    print(f"  run_dir : {run_dir}")

    if not ckpt.exists():
        print(f"  ckpt    : NOT_FOUND  ({ckpt})")
        print(f"  -> training in progress or did not reach min-best epoch")
    else:
        size_mb = ckpt.stat().st_size / (1024 * 1024)
        print(f"  ckpt    : {ckpt}  ({size_mb:.1f} MB)")

    metrics = find_best_epoch_metrics(run_dir)
    if metrics:
        print(f"\n[INTERNAL METRICS]  source={metrics['source']}")
        if "last_row" in metrics:
            for k, v in metrics["last_row"].items():
                print(f"  {k}: {v}")
        elif "data" in metrics:
            for k, v in metrics["data"].items():
                if isinstance(v, (str, int, float)):
                    print(f"  {k}: {v}")
    else:
        print(f"\n[INTERNAL METRICS]  no metrics CSV/JSON found in run_dir")

    print(f"\n[NEXT MANUAL STEPS]")
    print(f"  1. External GMF recon (3 pitches: 0.08 / 0.8 / 8 px)")
    print(f"     This requires the GMF measurement tool on real-system BMPs.")
    print(f"     Result: {tag} candidate's GMF_score.txt per pitch")
    print(f"")
    print(f"  2. Add candidate to sigma_b decompose script:")
    print(f"     edit: Thesis_MOSR_Evidence/error_type_transformation/")
    print(f"             sigma_hat_decomposition/scripts/decompose_sigma_b.py")
    print(f"     add CANDIDATES entry with paths to {tag} GMF_score.txt")
    print(f"     then re-run to extend sigma_b_table.csv")
    print(f"")
    print(f"  3. (Optional) 720-angle analysis on {tag} recon:")
    print(f"     Analyses/AnalysisLab/r26/sequence/scripts/run_sequence_analysis.py")
    print(f"     -> sequence_summary.json -> extend k=2 / hotspot tables")
    print(f"")
    print(f"  4. Write verification report:")
    print(f"     Thesis_MOSR_Evidence/method_ablations/<subdir>/reports/")
    print(f"             ablation_{tag.lower()}_verification.md")
    print(f"     compare sigma_hat / b / k=2 CV / hotspot vs COMBO")
    return 0


def main():
    parser = argparse.ArgumentParser(description="Ablation post-training analysis")
    parser.add_argument("--tag", type=str, required=True,
                        help="Ablation tag: NO_SEQ / NO_EQ / NO_EDGE / NO_FREQ")
    parser.add_argument("--weights", type=Path, default=None,
                        help="Explicit weights path (overrides auto-detection)")
    sys.exit(report(parser.parse_args().tag, parser.parse_args().weights))


if __name__ == "__main__":
    main()

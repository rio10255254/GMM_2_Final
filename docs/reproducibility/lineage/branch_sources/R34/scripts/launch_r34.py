"""
Round 34 — Frequency-Split Robust Loss Launcher

Usage:
    python Experiments/R34FreqSplit/scripts/launch_r34.py --candidate r34_freq_s15_p95
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_REPO_ROOT / "Model"))

CANDIDATES = {
    "r34_freq_s15_p95": {
        "ROBUST_LOSS_PERCENTILE": 0.95, "ROBUST_LOSS_WARMUP": 10,
        "ROBUST_FREQ_SPLIT": True, "ROBUST_FREQ_SIGMA": 1.5,
        "ROBUST_FREQ_W_LO": 0.5, "ROBUST_FREQ_W_HI": 0.5,
    },
    "r34_freq_s20_p95": {
        "ROBUST_LOSS_PERCENTILE": 0.95, "ROBUST_LOSS_WARMUP": 10,
        "ROBUST_FREQ_SPLIT": True, "ROBUST_FREQ_SIGMA": 2.0,
        "ROBUST_FREQ_W_LO": 0.5, "ROBUST_FREQ_W_HI": 0.5,
    },
    "r34_freq_s15_p90": {
        "ROBUST_LOSS_PERCENTILE": 0.90, "ROBUST_LOSS_WARMUP": 10,
        "ROBUST_FREQ_SPLIT": True, "ROBUST_FREQ_SIGMA": 1.5,
        "ROBUST_FREQ_W_LO": 0.5, "ROBUST_FREQ_W_HI": 0.5,
    },
}


def main():
    parser = argparse.ArgumentParser(description="R34 Frequency-Split launcher")
    parser.add_argument("--candidate", required=True, choices=list(CANDIDATES.keys()))
    parser.add_argument("--num-epoch", type=int, default=100)
    parser.add_argument("--device", type=str, default="cuda:0")
    args, remaining = parser.parse_known_args()

    sys.argv = [sys.argv[0]] + remaining

    import GeoEdgeAlignSR_v1_Train_v5_NoCoord_return_v2_SimpleTest as trainer
    CFG = trainer.CFG

    overrides = CANDIDATES[args.candidate]
    for key, val in overrides.items():
        setattr(CFG, key, val)

    CFG.MODEL_NAME = f"GESR_v1_v5_ST0p8_SWP_{args.candidate}"
    CFG.NUM_EPOCH = args.num_epoch
    CFG.DEVICE = args.device

    print(f"\n{'='*60}")
    print(f"R34 Freq-Split — Candidate: {args.candidate}")
    print(f"  ROBUST_LOSS_PERCENTILE = {CFG.ROBUST_LOSS_PERCENTILE}")
    print(f"  ROBUST_LOSS_WARMUP     = {CFG.ROBUST_LOSS_WARMUP}")
    print(f"  ROBUST_FREQ_SPLIT      = {CFG.ROBUST_FREQ_SPLIT}")
    print(f"  ROBUST_FREQ_SIGMA      = {CFG.ROBUST_FREQ_SIGMA}")
    print(f"  ROBUST_FREQ_W_LO       = {CFG.ROBUST_FREQ_W_LO}")
    print(f"  ROBUST_FREQ_W_HI       = {CFG.ROBUST_FREQ_W_HI}")
    print(f"  NUM_EPOCH              = {CFG.NUM_EPOCH}")
    print(f"  MODEL_NAME             = {CFG.MODEL_NAME}")
    print(f"{'='*60}\n")

    trainer.main()


if __name__ == "__main__":
    main()

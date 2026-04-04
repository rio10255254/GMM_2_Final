"""
Round 33 — Robust Loss Experiment Launcher

Usage:
    python Experiments/R33RobustLoss/scripts/launch_r33.py --candidate r33_robust_p90
    python Experiments/R33RobustLoss/scripts/launch_r33.py --candidate r33_robust_p85
    python Experiments/R33RobustLoss/scripts/launch_r33.py --candidate r33_robust_p95

Each candidate uses the R30 B1 dironly recipe with ONLY the
ROBUST_LOSS_PERCENTILE parameter changed.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Ensure Model/ is importable
_REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_REPO_ROOT / "Model"))

CANDIDATES = {
    "r33_robust_p90": {"ROBUST_LOSS_PERCENTILE": 0.90, "ROBUST_LOSS_WARMUP": 10},
    "r33_robust_p85": {"ROBUST_LOSS_PERCENTILE": 0.85, "ROBUST_LOSS_WARMUP": 10},
    "r33_robust_p95": {"ROBUST_LOSS_PERCENTILE": 0.95, "ROBUST_LOSS_WARMUP": 10},
}


def main():
    # Parse our own args first, pass the rest to the trainer
    parser = argparse.ArgumentParser(description="R33 Robust Loss launcher")
    parser.add_argument(
        "--candidate",
        required=True,
        choices=list(CANDIDATES.keys()),
        help="Which candidate config to run",
    )
    parser.add_argument("--num-epoch", type=int, default=100)
    parser.add_argument("--device", type=str, default="cuda:0")
    args, remaining = parser.parse_known_args()

    # Patch sys.argv so trainer.parse_args() only sees remaining args
    sys.argv = [sys.argv[0]] + remaining

    # Import training module (triggers CFG creation)
    import GeoEdgeAlignSR_v1_Train_v5_NoCoord_return_v2_SimpleTest as trainer

    CFG = trainer.CFG

    # Apply candidate-specific overrides
    overrides = CANDIDATES[args.candidate]
    for key, val in overrides.items():
        setattr(CFG, key, val)

    # Set run tag for output dir naming
    CFG.MODEL_NAME = f"GESR_v1_v5_ST0p8_SWP_{args.candidate}"
    CFG.NUM_EPOCH = args.num_epoch
    CFG.DEVICE = args.device

    print(f"\n{'='*60}")
    print(f"R33 Robust Loss — Candidate: {args.candidate}")
    print(f"  ROBUST_LOSS_PERCENTILE = {CFG.ROBUST_LOSS_PERCENTILE}")
    print(f"  ROBUST_LOSS_WARMUP     = {CFG.ROBUST_LOSS_WARMUP}")
    print(f"  NUM_EPOCH              = {CFG.NUM_EPOCH}")
    print(f"  DEVICE                 = {CFG.DEVICE}")
    print(f"  MODEL_NAME             = {CFG.MODEL_NAME}")
    print(f"{'='*60}\n")

    trainer.main()


if __name__ == "__main__":
    main()

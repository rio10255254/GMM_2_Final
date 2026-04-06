"""R33 Contrast Fix — Restore dynamic range while keeping Winsorize stability"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_REPO_ROOT / "Model"))

CANDIDATES = {
    "r33c_stat03": {
        "ROBUST_LOSS_PERCENTILE": 0.95, "ROBUST_LOSS_WARMUP": 10,
        "W_STAT": 0.30,      # up from 0.05
    },
    "r33c_stat03_ssim15": {
        "ROBUST_LOSS_PERCENTILE": 0.95, "ROBUST_LOSS_WARMUP": 10,
        "W_STAT": 0.30,
        "W_SSIM_START": 0.15, "W_SSIM_END": 0.15,  # up from 0.05
    },
    "r33c_stat05": {
        "ROBUST_LOSS_PERCENTILE": 0.95, "ROBUST_LOSS_WARMUP": 10,
        "W_STAT": 0.50,      # aggressive
    },
}


def main():
    parser = argparse.ArgumentParser(description="R33 Contrast Fix launcher")
    parser.add_argument("--candidate", required=True, choices=list(CANDIDATES.keys()))
    parser.add_argument("--num-epoch", type=int, default=100)
    parser.add_argument("--device", type=str, default="cuda:0")
    args, remaining = parser.parse_known_args()
    sys.argv = [sys.argv[0]] + remaining

    import GeoEdgeAlignSR_v1_Train_v5_NoCoord_return_v2_SimpleTest as trainer
    CFG = trainer.CFG
    for key, val in CANDIDATES[args.candidate].items():
        setattr(CFG, key, val)
    CFG.MODEL_NAME = f"GESR_v1_v5_ST0p8_SWP_{args.candidate}"
    CFG.NUM_EPOCH = args.num_epoch
    CFG.DEVICE = args.device

    print(f"\n{'='*60}")
    print(f"R33 Contrast Fix — {args.candidate}")
    print(f"  W_STAT                 = {CFG.W_STAT}")
    print(f"  W_SSIM_START           = {CFG.W_SSIM_START}")
    print(f"  W_SSIM_END             = {CFG.W_SSIM_END}")
    print(f"  ROBUST_LOSS_PERCENTILE = {CFG.ROBUST_LOSS_PERCENTILE}")
    print(f"{'='*60}\n")
    trainer.main()


if __name__ == "__main__":
    main()

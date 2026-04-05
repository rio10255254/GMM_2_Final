"""
Round 35 — Alpha Boost + R33 Winsorize Launcher
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_REPO_ROOT / "Model"))

CANDIDATES = {
    "r35_alpha025_p95": {
        "ROBUST_LOSS_PERCENTILE": 0.95, "ROBUST_LOSS_WARMUP": 10,
        "PSF_PHYS_ALPHA_INIT": 0.25,
    },
    "r35_alpha020_p95": {
        "ROBUST_LOSS_PERCENTILE": 0.95, "ROBUST_LOSS_WARMUP": 10,
        "PSF_PHYS_ALPHA_INIT": 0.20,
    },
}


def main():
    parser = argparse.ArgumentParser(description="R35 Alpha Boost launcher")
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
    print(f"R35 Alpha Boost — Candidate: {args.candidate}")
    print(f"  PSF_PHYS_ALPHA_INIT    = {CFG.PSF_PHYS_ALPHA_INIT}")
    print(f"  ROBUST_LOSS_PERCENTILE = {CFG.ROBUST_LOSS_PERCENTILE}")
    print(f"  ROBUST_LOSS_WARMUP     = {CFG.ROBUST_LOSS_WARMUP}")
    print(f"  NUM_EPOCH              = {CFG.NUM_EPOCH}")
    print(f"{'='*60}\n")

    trainer.main()


if __name__ == "__main__":
    main()

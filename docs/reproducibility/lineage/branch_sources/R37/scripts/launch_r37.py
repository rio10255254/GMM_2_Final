"""Round 37 — Frequency-Dependent PSF Regularization Launcher"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_REPO_ROOT / "Model"))

CANDIDATES = {
    "r37_freqreg_p95": {
        "PSF_FREQ_REG_ENABLE": True,
        "PSF_FREQ_REG_SIGMA": 0.15,
        "PSF_FREQ_REG_LO_MULT": 2.0,
        "PSF_FREQ_REG_HI_FLOOR": 0.3,
        "ROBUST_LOSS_PERCENTILE": 0.95,
        "ROBUST_LOSS_WARMUP": 10,
    },
    "r37_freqreg_only": {
        "PSF_FREQ_REG_ENABLE": True,
        "PSF_FREQ_REG_SIGMA": 0.15,
        "PSF_FREQ_REG_LO_MULT": 2.0,
        "PSF_FREQ_REG_HI_FLOOR": 0.3,
        "ROBUST_LOSS_PERCENTILE": 1.0,
    },
}


def main():
    parser = argparse.ArgumentParser(description="R37 Freq-Reg launcher")
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
    print(f"R37 Freq-Reg — Candidate: {args.candidate}")
    print(f"  PSF_FREQ_REG_ENABLE    = {CFG.PSF_FREQ_REG_ENABLE}")
    print(f"  PSF_FREQ_REG_SIGMA     = {CFG.PSF_FREQ_REG_SIGMA}")
    print(f"  PSF_FREQ_REG_LO_MULT   = {CFG.PSF_FREQ_REG_LO_MULT}")
    print(f"  PSF_FREQ_REG_HI_FLOOR  = {CFG.PSF_FREQ_REG_HI_FLOOR}")
    print(f"  ROBUST_LOSS_PERCENTILE = {CFG.ROBUST_LOSS_PERCENTILE}")
    print(f"  NUM_EPOCH              = {CFG.NUM_EPOCH}")
    print(f"{'='*60}\n")
    trainer.main()


if __name__ == "__main__":
    main()

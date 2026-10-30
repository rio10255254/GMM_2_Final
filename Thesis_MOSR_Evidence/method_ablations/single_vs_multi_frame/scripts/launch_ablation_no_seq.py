"""Ablation A — Single-frame baseline (SEQ_ENABLE=False).

Tests论文 4.6 claim: multi-frame sequence consistency is the key
architectural mechanism separating sigma_hat from b.

This launcher inherits COMBO (r38v2_8px_gate_p95) settings exactly,
with the ONLY difference being SEQ_ENABLE=False. Any divergence from
COMBO results in the error-type-transformation metrics is attributable
to the multi-frame training protocol.

Training output goes to:
    Experiments/Training_Runs/training_progress_GESR_v1_v5_ST0p8_SWP_<tag>_<timestamp>/

Usage:
    python launch_ablation_no_seq.py --num-epoch 50 --device cuda:0
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


_REPO_ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(_REPO_ROOT / "Model"))


# COMBO (r38v2_8px_gate_p95) baseline settings, with SEQ_ENABLE flipped to False.
# All other hyperparameters preserved exactly as in R38v2SeqFixed/scripts/launch_r38v2.py
# CANDIDATES["r38v2_8px_gate_p95"].
ABLATION_CFG = {
    # ============= SEQ ABLATED OUT =============
    "SEQ_ENABLE": False,           # <-- the only intentional difference vs COMBO
    "SEQ_LOSS_WEIGHT": 0.0,        # zero out to be safe
    "SEQ_GRAD_WEIGHT": 0.0,
    # ============= COMBO baseline rest =============
    "ROBUST_LOSS_PERCENTILE": 0.95,
    "ROBUST_LOSS_WARMUP": 10,
    # NOTE: SEQ_SRC_DIR / SEQ_LBL_DIR / SEQ_INCLUDE_SUBDIRS are unused when
    # SEQ_ENABLE=False, no need to set.
    # NOTE: Other physics-residual weights (W_GRADMAG, W_EDGE_ORI_SIMPLE,
    # W_HF_LAP, EQ_PROB) inherit trainer CFG defaults which match COMBO recipe.
}


def main():
    parser = argparse.ArgumentParser(
        description="Ablation A: single-frame baseline (no SEQ)"
    )
    parser.add_argument("--num-epoch", type=int, default=50,
                        help="50 = adequate to see trend; 100 = full COMBO parity")
    parser.add_argument("--device", type=str, default="cuda:0")
    parser.add_argument("--tag", type=str,
                        default="r38v2_8px_gate_p95_ABLA_NO_SEQ",
                        help="Candidate tag; appears in Traing_Progress dir name")
    args, remaining = parser.parse_known_args()
    sys.argv = [sys.argv[0]] + remaining

    import GeoEdgeAlignSR_v1_Train_v5_NoCoord_return_v2_SimpleTest as trainer
    CFG = trainer.CFG
    for key, val in ABLATION_CFG.items():
        setattr(CFG, key, val)
    CFG.MODEL_NAME = f"GESR_v1_v5_ST0p8_SWP_{args.tag}"
    trainer.MODEL_NAME_BASE = CFG.MODEL_NAME
    CFG.NUM_EPOCH = args.num_epoch
    # SIMPLETEST_MODE controls the actual epoch loop in trainer,
    # so we must override SIMPLETEST_MAX_EPOCH too.
    CFG.SIMPLETEST_MAX_EPOCH = args.num_epoch
    CFG.DEVICE = args.device

    print(f"\n{'='*60}")
    print(f"Ablation A — {args.tag}")
    print(f"  SEQ_ENABLE             = {CFG.SEQ_ENABLE}  <-- ABLATION POINT")
    print(f"  ROBUST_LOSS_PERCENTILE = {CFG.ROBUST_LOSS_PERCENTILE}")
    print(f"  NUM_EPOCH              = {CFG.NUM_EPOCH}")
    print(f"  DEVICE                 = {CFG.DEVICE}")
    print(f"  Output to              = Experiments/Training_Runs/training_progress_{CFG.MODEL_NAME}_<timestamp>/")
    print(f"{'='*60}\n")
    trainer.main()


if __name__ == "__main__":
    main()

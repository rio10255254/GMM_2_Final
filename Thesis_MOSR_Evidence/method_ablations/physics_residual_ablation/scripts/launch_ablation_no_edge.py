"""Ablation B2 — Edge differential residual off.

Tests论文 4.5.3 claim: edge differential residual constrains boundary
position. Without it, expect k=2 amplitude CV to blow up and |b|
to rise.

Inherits COMBO recipe; only edge-related weights set to 0.
"""

from __future__ import annotations
import argparse
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(_REPO_ROOT / "Model"))


ABLATION_CFG = {
    # COMBO baseline
    "SEQ_ENABLE": True,
    "SEQ_SRC_DIR": str(_REPO_ROOT / "Training_Data" / "generated_convolved"),
    "SEQ_LBL_DIR": str(_REPO_ROOT / "Training_Data" / "generated"),
    "SEQ_INCLUDE_SUBDIRS": (
        "stage_25_annulus_gmf_sequence_macro_clean",
        "stage_26_annulus_gmf_sequence_macro_defect",
    ),
    "SEQ_LOSS_WEIGHT": 0.3,
    "SEQ_GRAD_WEIGHT": 0.1,
    "SEQ_EVERY_N_BATCH": 2,
    "SEQ_MIN_DELTA_THRESHOLD": 0.002,
    "SEQ_WARMUP_EPOCH": 15,
    "ROBUST_LOSS_PERCENTILE": 0.95,
    "ROBUST_LOSS_WARMUP": 10,
    # ============= ABLATION POINT =============
    # Disable all edge differential residual subcomponents
    "W_GRADMAG": 0.0,            # first-order gradient magnitude
    "W_EDGE_ORI_SIMPLE": 0.0,    # edge orientation (simple)
    "W_EDGELOCAL_LAP_START": 0.0,  # edge-local Laplacian (start)
    "W_EDGELOCAL_LAP_END": 0.0,    # edge-local Laplacian (end)
}


def main():
    parser = argparse.ArgumentParser(description="Ablation B2: no edge residual")
    parser.add_argument("--num-epoch", type=int, default=50)
    parser.add_argument("--device", type=str, default="cuda:0")
    parser.add_argument("--tag", type=str,
                        default="r38v2_8px_gate_p95_ABLA_NO_EDGE")
    args, remaining = parser.parse_known_args()
    sys.argv = [sys.argv[0]] + remaining

    import GeoEdgeAlignSR_v1_Train_v5_NoCoord_return_v2_SimpleTest as trainer
    CFG = trainer.CFG
    for k, v in ABLATION_CFG.items():
        setattr(CFG, k, v)
    CFG.MODEL_NAME = f"GESR_v1_v5_ST0p8_SWP_{args.tag}"
    trainer.MODEL_NAME_BASE = CFG.MODEL_NAME
    CFG.NUM_EPOCH = args.num_epoch
    CFG.SIMPLETEST_MAX_EPOCH = args.num_epoch
    CFG.DEVICE = args.device

    print(f"\n{'='*60}")
    print(f"Ablation B2 (no_edge) — {args.tag}")
    print(f"  W_GRADMAG              = {CFG.W_GRADMAG}  <-- ABLATION POINT")
    print(f"  W_EDGE_ORI_SIMPLE      = {CFG.W_EDGE_ORI_SIMPLE}")
    print(f"  W_EDGELOCAL_LAP_END    = {CFG.W_EDGELOCAL_LAP_END}")
    print(f"  SEQ_ENABLE             = {CFG.SEQ_ENABLE}  (kept on)")
    print(f"  EQ_PROB                = {CFG.EQ_PROB}  (kept default)")
    print(f"  NUM_EPOCH              = {CFG.NUM_EPOCH}")
    print(f"{'='*60}\n")
    trainer.main()


if __name__ == "__main__":
    main()

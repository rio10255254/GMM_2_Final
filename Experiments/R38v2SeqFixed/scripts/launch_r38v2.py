"""R38v2 — Sequence Consistency Training (Fixed) Launcher"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_REPO_ROOT / "Model"))

_SEQ_8PX = (
    "stage_25_annulus_gmf_sequence_macro_clean",
    "stage_26_annulus_gmf_sequence_macro_defect",
)
_SEQ_ALL = (
    "stage_19_annulus_microstep_sequence_clean",
    "stage_20_annulus_microstep_sequence_defect",
    "stage_21_annulus_gmf_sequence_clean",
    "stage_22_annulus_gmf_sequence_defect",
    "stage_23_annulus_gmf_sequence_mid_clean",
    "stage_24_annulus_gmf_sequence_mid_defect",
    "stage_25_annulus_gmf_sequence_macro_clean",
    "stage_26_annulus_gmf_sequence_macro_defect",
    "stage_27_annulus_gmf_sequence_midwide_clean",
    "stage_28_annulus_gmf_sequence_midwide_defect",
)

CANDIDATES = {
    "r38v2_8px_gate": {
        "SEQ_ENABLE": True,
        "SEQ_SRC_DIR": str(_REPO_ROOT / "Training_Data" / "generated_convolved"),
        "SEQ_LBL_DIR": str(_REPO_ROOT / "Training_Data" / "generated"),
        "SEQ_INCLUDE_SUBDIRS": _SEQ_8PX,
        "SEQ_LOSS_WEIGHT": 0.3,
        "SEQ_GRAD_WEIGHT": 0.1,
        "SEQ_EVERY_N_BATCH": 2,
        "SEQ_MIN_DELTA_THRESHOLD": 0.002,
        "SEQ_WARMUP_EPOCH": 15,
        "ROBUST_LOSS_PERCENTILE": 1.0,
    },
    "r38v2_all_gate": {
        "SEQ_ENABLE": True,
        "SEQ_SRC_DIR": str(_REPO_ROOT / "Training_Data" / "generated_convolved"),
        "SEQ_LBL_DIR": str(_REPO_ROOT / "Training_Data" / "generated"),
        "SEQ_INCLUDE_SUBDIRS": _SEQ_ALL,
        "SEQ_LOSS_WEIGHT": 0.3,
        "SEQ_GRAD_WEIGHT": 0.1,
        "SEQ_EVERY_N_BATCH": 2,
        "SEQ_MIN_DELTA_THRESHOLD": 0.002,
        "SEQ_WARMUP_EPOCH": 15,
        "ROBUST_LOSS_PERCENTILE": 1.0,
    },
    "r38v2_8px_gate_p95": {
        "SEQ_ENABLE": True,
        "SEQ_SRC_DIR": str(_REPO_ROOT / "Training_Data" / "generated_convolved"),
        "SEQ_LBL_DIR": str(_REPO_ROOT / "Training_Data" / "generated"),
        "SEQ_INCLUDE_SUBDIRS": _SEQ_8PX,
        "SEQ_LOSS_WEIGHT": 0.3,
        "SEQ_GRAD_WEIGHT": 0.1,
        "SEQ_EVERY_N_BATCH": 2,
        "SEQ_MIN_DELTA_THRESHOLD": 0.002,
        "SEQ_WARMUP_EPOCH": 15,
        "ROBUST_LOSS_PERCENTILE": 0.95,
        "ROBUST_LOSS_WARMUP": 10,
    },
}


def main():
    parser = argparse.ArgumentParser(description="R38v2 Seq Fixed launcher")
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
    print(f"R38v2 Seq Fixed — {args.candidate}")
    print(f"  SEQ stages             = {len(CFG.SEQ_INCLUDE_SUBDIRS)}")
    print(f"  SEQ_MIN_DELTA_THRESHOLD= {CFG.SEQ_MIN_DELTA_THRESHOLD}")
    print(f"  SEQ_WARMUP_EPOCH       = {CFG.SEQ_WARMUP_EPOCH}")
    print(f"  SEQ_LOSS_WEIGHT        = {CFG.SEQ_LOSS_WEIGHT}")
    print(f"  ROBUST_LOSS_PERCENTILE = {CFG.ROBUST_LOSS_PERCENTILE}")
    print(f"{'='*60}\n")
    trainer.main()


if __name__ == "__main__":
    main()

"""Round 46 — a025 邊角細節微調 launcher(路徑 B:既有 hyperparam 強化版)

設計:
- 起點:a025 best_tradeoff(R39 a030 與 R40 a043 在 α=0.25 的權重平均)
- 訓練資料:r40_micro_capacity_train(R40 微調 a043 的 profile,1300 對)
- 低學習率(4e-6)、短訓練輪數(15 epoch)
- 強化既有的邊緣銳度 / 高頻保留權重,不加新 loss(不動 trainer 主檔)

設計來源見 ../README.md;前三輪 Rayleigh 診斷紀錄見
Experiments/R39_ShapeGeneralization/results/a030_x_a043_sweep/reports/R39R40_AVG_a025_RAYLEIGH_*.md
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


_REPO_ROOT = Path(__file__).resolve().parents[3]
_SCRIPT_DIR = Path(__file__).resolve().parent
_R40_SCRIPT_DIR = _REPO_ROOT / "Experiments" / "R40_MicroscopyFeatureCoverage" / "scripts"

sys.path.insert(0, str(_SCRIPT_DIR))
sys.path.insert(0, str(_R40_SCRIPT_DIR))
sys.path.insert(0, str(_REPO_ROOT / "Model"))

# 借用 R40 的資料封裝邏輯
from launch_r40 import ensure_data_package  # noqa: E402
from r40_micro_data import DEFAULT_OUTPUT_ROOT  # noqa: E402


A025_CHECKPOINT = (
    _REPO_ROOT
    / "Experiments"
    / "R39_ShapeGeneralization"
    / "results"
    / "a030_x_a043_sweep"
    / "checkpoints"
    / "a025"
    / "best_tradeoff.pth.tar"
)


PROFILE_BY_CANDIDATE = {
    "r46_a025_corner_finetune": "r40_micro_capacity_train",
}

BASE_CHECKPOINT_BY_CANDIDATE = {
    "r46_a025_corner_finetune": A025_CHECKPOINT,
}

CANDIDATE_NOTES = {
    "r46_a025_corner_finetune": (
        "fine-tune from a025 with strengthened edge-sharpness and high-frequency weights; "
        "no new loss terms, no trainer modification"
    ),
}


# R46 配方:在 a025 weight averaging checkpoint 之上,
# 用低 LR + 強化邊緣銳度 / 高頻保留 / 邊緣局部 Laplacian 權重。
BASE_OVERRIDES = {
    # === Checkpoint 載入 ===
    "LOAD_MODEL": True,
    "LOAD_RESET_OPTIMIZER": True,  # a025 是 weight averaging,沒對應 optimizer state
    "LOAD_RESET_EPOCH": True,

    # === 低 LR 微調 ===
    "LR": 4.0e-6,

    # === 強化邊緣銳度 / 高頻保留(SimpleTest 核心 weights)===
    "W_REC": 1.0,             # 重建 weight 維持
    "W_GRADMAG": 1.0,         # 0.8 → 1.0,梯度幅值(邊緣銳度)
    "W_EDGE_ORI_SIMPLE": 0.4, # 0.3 → 0.4,邊緣方向(直邊保留)
    "W_HF_LAP": 0.20,         # 0.15 → 0.20,高頻 Laplacian(細節保留)

    # === 邊緣局部 Laplacian(對應 corner-aware loss 替代)===
    "ENABLE_EDGELOCAL_LAPLACIAN": True,
    "W_EDGELOCAL_LAP_START": 0.0,
    "W_EDGELOCAL_LAP_END": 0.08,    # 0.06 → 0.08,提高邊緣局部高頻權重
    "EDGELOCAL_LAP_RAMP_E1": 2,      # 6 → 2,早一點開始 ramp
    "EDGELOCAL_LAP_RAMP_E2": 10,     # 20 → 10,早一點達到 end weight

    # === 關閉複雜訓練線 ===
    "BOUNDARY_GEOM_ENABLE": False,  # R40 train profile 不含 boundary geom 資料
    "MOTION_ENABLE": False,
    "SEQ_ENABLE": False,
    "SEQ_GEOM_ENABLE": False,
    "KD_ENABLE": False,
    "REGION_KD_ENABLE": False,

    # === robust loss ===
    "ROBUST_LOSS_PERCENTILE": 0.95,
    "ROBUST_LOSS_WARMUP": 5,

    # === best checkpoint min-epoch(預設 20,微調短訓練要降下來才會產 best_tradeoff)===
    "BEST_EPOCH_MIN": 5,

    # === 物理 forward(維持 R44 BASE 同設定,可隨需要關)===
    "PHYS_FORWARD_ENABLE": True,
    "W_PHYS_MAX": 0.05,
    "PHYS_WARMUP_END": 5,    # 短訓練輪數需要早一點 warmup 完成
    "PHYS_RAMP_END": 10,

    # === 訓練資料 stage ===
    "TRAIN_INCLUDE_SUBDIRS": (),  # 用 R40 train profile 全部 stages
    "TRAIN_EXCLUDE_SUBDIRS": (),
}


CANDIDATE_OVERRIDES: dict[str, dict] = {
    "r46_a025_corner_finetune": {},  # 主候選沒額外 override
}


def configure_trainer(trainer, args: argparse.Namespace, data_dir: Path) -> None:
    CFG = trainer.CFG
    for key, val in BASE_OVERRIDES.items():
        setattr(CFG, key, val)
    for key, val in CANDIDATE_OVERRIDES.get(args.candidate, {}).items():
        setattr(CFG, key, val)

    checkpoint = Path(args.base_checkpoint).resolve()
    if not checkpoint.exists():
        raise FileNotFoundError(f"base checkpoint not found: {checkpoint}")

    CFG.RESUME_CHECKPOINT = str(checkpoint)
    CFG.MODEL_NAME = f"GESR_v1_v5_ST0p8_SWP_{args.candidate}"
    trainer.MODEL_NAME_BASE = CFG.MODEL_NAME
    CFG.NUM_EPOCH = int(args.num_epoch)
    # trainer 用 SIMPLETEST_MAX_EPOCH 控制 outer loop,要同步設
    CFG.SIMPLETEST_MAX_EPOCH = int(args.num_epoch)
    CFG.DEVICE = str(args.device)

    if args.max_train_batches is not None:
        CFG.MAX_TRAIN_BATCHES_PER_EPOCH = int(args.max_train_batches)
    if args.val_ratio is not None:
        CFG.VAL_RATIO = float(args.val_ratio)
    if args.batch_size is not None:
        CFG.BATCH_SIZE = int(args.batch_size)
    if args.val_batch_size is not None:
        CFG.VAL_BATCH_SIZE = int(args.val_batch_size)

    trainer.TRAIN_SRC_DIR = str(data_dir / "src")
    trainer.TRAIN_LBL_DIR = str(data_dir / "lbl")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="R46 a025 corner-aware fine-tune launcher (path B)")
    parser.add_argument("--candidate", default="r46_a025_corner_finetune",
                        choices=sorted(PROFILE_BY_CANDIDATE))
    parser.add_argument("--num-epoch", type=int, default=15)
    parser.add_argument("--device", default="cuda:0")
    parser.add_argument("--base-checkpoint", type=Path, default=None)
    parser.add_argument("--data-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--max-train-batches", type=int, default=None,
                        help="若指定,限制每 epoch 訓練 batch 數量(smoke test 用)")
    parser.add_argument("--val-ratio", type=float, default=None)
    parser.add_argument("--batch-size", type=int, default=None)
    parser.add_argument("--val-batch-size", type=int, default=None)
    parser.add_argument("--build-data", action="store_true")
    parser.add_argument("--force-data", action="store_true")
    parser.add_argument("--link-mode", choices=["auto", "hardlink", "copy"], default="auto")
    parser.add_argument("--dry-run", action="store_true")
    args, remaining = parser.parse_known_args(argv)
    sys.argv = [sys.argv[0]] + remaining

    if args.base_checkpoint is None:
        args.base_checkpoint = BASE_CHECKPOINT_BY_CANDIDATE[args.candidate]

    profile_name = PROFILE_BY_CANDIDATE[args.candidate]
    data_dir, manifest = ensure_data_package(
        profile_name,
        args.data_root,
        build_data=args.build_data,
        force_data=args.force_data,
        link_mode=args.link_mode,
    )

    import GeoEdgeAlignSR_v1_Train_v5_NoCoord_return_v2_SimpleTest as trainer

    configure_trainer(trainer, args, data_dir)
    CFG = trainer.CFG
    summary = {
        "candidate": args.candidate,
        "note": CANDIDATE_NOTES[args.candidate],
        "profile": profile_name,
        "data_dir": str(data_dir),
        "total_pairs": manifest["total_pairs"],
        "count_by_role": manifest.get("count_by_role", "n/a"),
        "base_checkpoint": str(Path(args.base_checkpoint).resolve()),
        "base_checkpoint_exists": Path(args.base_checkpoint).resolve().exists(),
        "model_name": CFG.MODEL_NAME,
        "num_epoch": CFG.NUM_EPOCH,
        "device": CFG.DEVICE,
        "lr": CFG.LR,
        "edge_sharpness_weights": {
            "w_gradmag": CFG.W_GRADMAG,
            "w_edge_ori_simple": CFG.W_EDGE_ORI_SIMPLE,
            "w_hf_lap": CFG.W_HF_LAP,
            "w_edgelocal_lap_end": CFG.W_EDGELOCAL_LAP_END,
            "edgelocal_lap_ramp": (CFG.EDGELOCAL_LAP_RAMP_E1, CFG.EDGELOCAL_LAP_RAMP_E2),
        },
        "complex_lines_disabled": {
            "boundary_geom": CFG.BOUNDARY_GEOM_ENABLE,
            "motion": CFG.MOTION_ENABLE,
            "seq": CFG.SEQ_ENABLE,
            "kd": CFG.KD_ENABLE,
        },
        "max_train_batches": CFG.MAX_TRAIN_BATCHES_PER_EPOCH,
    }
    print(json.dumps(summary, indent=2, ensure_ascii=False))

    if args.dry_run:
        print("[R46] dry run complete; training was not started.")
        return 0

    trainer.main()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

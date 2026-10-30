"""V42 soft-label + image-quality gate experiment launcher."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


EXPERIMENT_DIR = Path(__file__).resolve().parents[1]
LAB_ROOT = Path(__file__).resolve().parents[3]
V41_SCRIPT_DIR = LAB_ROOT / "Experiments" / "V41_Standalone" / "scripts"
R61_SCRIPT_DIR = LAB_ROOT / "Experiments" / "R61_BoundaryGeneralizationUniversal" / "scripts"

sys.path.insert(0, str(V41_SCRIPT_DIR))
sys.path.insert(0, str(R61_SCRIPT_DIR))

import launch_r61 as r61  # noqa: E402
import launch_v41_standalone as v41  # noqa: E402


V42_CANDIDATE = "v42_softlabel_snr_smoke"
V42_PROFILE = "r62_target_sample_boost_v14_softlabel_snr_smoke"
DEFAULT_DATA_ROOT = LAB_ROOT / "Training_Data" / "r62_target_sample_boost" / "hs100mg_basler"
DEFAULT_BASE_CHECKPOINT = (
    LAB_ROOT
    / "Traing_Progress"
    / "training_progress_LAB_GESR_v1_v5_ST0p8_SWP_v41_standalone_long_standalone_full_e16_20260708_100223_20260708_100251"
    / "weights"
    / "best_tradeoff.pth.tar"
)

V42_SETTINGS: dict[str, Any] = dict(v41.STANDALONE_SETTINGS)
V42_SETTINGS.update(
    {
        "profile": V42_PROFILE,
        "base_checkpoint": DEFAULT_BASE_CHECKPOINT,
        "region_kd_teacher_checkpoint": DEFAULT_BASE_CHECKPOINT,
        "lr": 2.0e-7,
        "trainable_name_patterns": ("quality_gate", "boundary_adapter", "p1", "out"),
        "quality_gate_enable": True,
        "quality_gate_hidden": 8,
        "quality_gate_scale_min": 0.78,
        "quality_gate_scale_max": 1.08,
        "external_selection_gate": "v42_softlabel_snr_smoke_gate",
    }
)

PROFILE_BY_CANDIDATE = {V42_CANDIDATE: V42_PROFILE}
REQUIRED_ROLES_BY_CANDIDATE = {V42_CANDIDATE: v41.STANDALONE_REQUIRED_ROLES}


def patch_r61_registry() -> None:
    r61.DEFAULT_DATA_ROOT = DEFAULT_DATA_ROOT
    r61.CANDIDATE_SETTINGS.clear()
    r61.CANDIDATE_SETTINGS[V42_CANDIDATE] = dict(V42_SETTINGS)
    r61.PROFILE_BY_CANDIDATE.clear()
    r61.PROFILE_BY_CANDIDATE.update(PROFILE_BY_CANDIDATE)
    r61.REQUIRED_ROLES_BY_CANDIDATE.clear()
    r61.REQUIRED_ROLES_BY_CANDIDATE.update(REQUIRED_ROLES_BY_CANDIDATE)


def profile_dir(data_root: Path = DEFAULT_DATA_ROOT) -> Path:
    return Path(data_root) / V42_PROFILE


def load_manifest(data_root: Path = DEFAULT_DATA_ROOT) -> dict[str, Any]:
    with (profile_dir(data_root) / "manifest.json").open("r", encoding="utf-8") as f:
        return json.load(f)


def build_summary(data_root: Path = DEFAULT_DATA_ROOT) -> dict[str, Any]:
    manifest = load_manifest(data_root)
    return {
        "candidate": V42_CANDIDATE,
        "profile": V42_PROFILE,
        "source": "V41 standalone data with edge-band soft labels",
        "base_checkpoint": str(DEFAULT_BASE_CHECKPOINT),
        "total_pairs": int(manifest.get("total_pairs", 0)),
        "role_counts": manifest.get("role_counts", {}),
        "quality_gate_enable": True,
        "quality_gate_scale_min": V42_SETTINGS["quality_gate_scale_min"],
        "quality_gate_scale_max": V42_SETTINGS["quality_gate_scale_max"],
        "trainable_name_patterns": list(V42_SETTINGS["trainable_name_patterns"]),
    }


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="V42 soft-label/SNR smoke training launcher")
    parser.add_argument("--candidate", default=V42_CANDIDATE, choices=[V42_CANDIDATE])
    parser.add_argument("--num-epoch", type=int, default=1)
    parser.add_argument("--device", default="cuda:0")
    parser.add_argument("--base-checkpoint", type=Path, default=None)
    parser.add_argument("--scratch", action="store_true")
    parser.add_argument("--data-root", type=Path, default=DEFAULT_DATA_ROOT)
    parser.add_argument("--run-suffix", default="softlabel_snr_smoke_e1")
    parser.add_argument("--max-train-batches", type=int, default=20)
    parser.add_argument("--val-ratio", type=float, default=0.12)
    parser.add_argument("--lr", type=float, default=None)
    parser.add_argument("--batch-size", type=int, default=2)
    parser.add_argument("--val-batch-size", type=int, default=1)
    parser.add_argument("--num-workers", type=int, default=0)
    parser.add_argument("--crop-size", type=int, default=256)
    parser.add_argument("--seq-batch-size", type=int, default=1)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--print-summary", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    if args.print_summary:
        print(json.dumps(build_summary(args.data_root), indent=2, ensure_ascii=False))
        return 0
    patch_r61_registry()
    forwarded = [
        "--candidate",
        args.candidate,
        "--num-epoch",
        str(args.num_epoch),
        "--device",
        args.device,
        "--data-root",
        str(args.data_root),
        "--run-suffix",
        args.run_suffix,
        "--val-ratio",
        str(args.val_ratio),
        "--batch-size",
        str(args.batch_size),
        "--val-batch-size",
        str(args.val_batch_size),
        "--num-workers",
        str(args.num_workers),
        "--crop-size",
        str(args.crop_size),
        "--seq-batch-size",
        str(args.seq_batch_size),
    ]
    if args.base_checkpoint is not None:
        forwarded.extend(["--base-checkpoint", str(args.base_checkpoint)])
    if args.scratch:
        forwarded.append("--scratch")
    if args.max_train_batches is not None:
        forwarded.extend(["--max-train-batches", str(args.max_train_batches)])
    if args.lr is not None:
        forwarded.extend(["--lr", str(args.lr)])
    if args.dry_run:
        forwarded.append("--dry-run")
    return r61.main(forwarded)


if __name__ == "__main__":
    raise SystemExit(main())

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any

import torch


def _validate_anchor_args(*, mode: str, alpha: float, sigma: float, detail_gain: float) -> None:
    if mode not in {"none", "blend", "detail"}:
        raise ValueError("mode must be none, blend, or detail")
    if not 0.0 <= float(alpha) <= 1.0:
        raise ValueError("alpha must be between 0 and 1")
    if float(sigma) <= 0.0:
        raise ValueError("sigma must be positive")
    if float(detail_gain) < 0.0:
        raise ValueError("detail_gain must be non-negative")


def patch_anchor_output_checkpoint(
    source_checkpoint: Path,
    output_checkpoint: Path,
    *,
    mode: str,
    alpha: float = 0.10,
    sigma: float = 2.0,
    detail_gain: float = 0.35,
) -> dict[str, Any]:
    _validate_anchor_args(mode=mode, alpha=alpha, sigma=sigma, detail_gain=detail_gain)
    source_checkpoint = Path(source_checkpoint)
    output_checkpoint = Path(output_checkpoint)
    if not source_checkpoint.is_file():
        raise FileNotFoundError(source_checkpoint)
    checkpoint = torch.load(str(source_checkpoint), map_location="cpu")
    if not isinstance(checkpoint, dict):
        raise TypeError("checkpoint must be a dictionary")
    patched = dict(checkpoint)
    model_config = dict(patched.get("model_config") or {})
    model_config["raw_anchor_output"] = {
        "mode": str(mode),
        "alpha": float(alpha),
        "sigma": float(sigma),
        "detail_gain": float(detail_gain),
    }
    patched["model_config"] = model_config
    patch_info = {
        "source_checkpoint": str(source_checkpoint),
        "output_checkpoint": str(output_checkpoint),
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "raw_anchor_output": dict(model_config["raw_anchor_output"]),
        "note": "Only checkpoint metadata/model_config is changed; model weights are preserved.",
    }
    patched["anchor_output_checkpoint_patch"] = patch_info
    output_checkpoint.parent.mkdir(parents=True, exist_ok=True)
    torch.save(patched, str(output_checkpoint))
    return patch_info


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Patch a checkpoint with raw-anchor output metadata.")
    parser.add_argument("--source-checkpoint", required=True)
    parser.add_argument("--output-checkpoint", required=True)
    parser.add_argument("--mode", choices=("none", "blend", "detail"), default="blend")
    parser.add_argument("--alpha", type=float, default=0.10)
    parser.add_argument("--sigma", type=float, default=2.0)
    parser.add_argument("--detail-gain", type=float, default=0.35)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    info = patch_anchor_output_checkpoint(
        Path(args.source_checkpoint),
        Path(args.output_checkpoint),
        mode=str(args.mode),
        alpha=float(args.alpha),
        sigma=float(args.sigma),
        detail_gain=float(args.detail_gain),
    )
    print(json.dumps(info, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()

"""Build an R62 fixed raw-anchor checkpoint from an existing frozen model.

This copies model tensors unchanged and records the output-only anchor mode in
checkpoint metadata. It performs no training or inference and refuses to
overwrite an existing output.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import torch


def sha256(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def build(source: Path, output: Path, mode: str, alpha: float,
          sigma: float, detail_gain: float) -> dict:
    source = source.resolve()
    output = output.resolve()
    if not source.is_file():
        raise FileNotFoundError(source)
    if output.exists():
        raise FileExistsError(output)
    if mode not in {"blend", "detail"}:
        raise ValueError("mode must be blend or detail")
    if not 0.0 <= alpha <= 1.0 or sigma <= 0.0 or detail_gain < 0.0:
        raise ValueError("invalid anchor settings")

    original = torch.load(source, map_location="cpu", weights_only=False)
    if not isinstance(original, dict) or not isinstance(original.get("state_dict"), dict):
        raise TypeError("expected a checkpoint dictionary with state_dict")
    result = copy.deepcopy(original)
    config = copy.deepcopy(result.get("model_config") or {})
    anchor = {
        "mode": mode,
        "alpha": float(alpha),
        "sigma": float(sigma),
        "detail_gain": float(detail_gain),
    }
    config["raw_anchor_output"] = anchor
    result["model_config"] = config
    result["anchor_output_checkpoint_patch"] = {
        "source_checkpoint": str(source),
        "output_checkpoint": str(output),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "raw_anchor_output": anchor,
        "note": "Only checkpoint metadata/model_config is changed; model weights are preserved.",
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    torch.save(result, output)
    return {
        "status": "PASS",
        "source": str(source),
        "source_sha256": sha256(source),
        "output": str(output),
        "output_sha256": sha256(output),
        "raw_anchor_output": anchor,
        "training_or_inference": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--mode", choices=["blend", "detail"], required=True)
    parser.add_argument("--alpha", type=float, default=0.1)
    parser.add_argument("--sigma", type=float, default=2.0)
    parser.add_argument("--detail-gain", type=float, default=0.35)
    args = parser.parse_args()
    print(json.dumps(build(args.source, args.output, args.mode, args.alpha,
                           args.sigma, args.detail_gain), ensure_ascii=False))


if __name__ == "__main__":
    main()

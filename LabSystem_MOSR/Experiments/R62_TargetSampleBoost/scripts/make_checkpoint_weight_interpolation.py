from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any

import torch


def _validate_alpha(alpha: float) -> None:
    if not 0.0 <= float(alpha) <= 1.0:
        raise ValueError("alpha must be between 0 and 1")


def _is_interpolatable(base: torch.Tensor, trained: torch.Tensor) -> bool:
    return (
        torch.is_floating_point(base)
        and torch.is_floating_point(trained)
        and tuple(base.shape) == tuple(trained.shape)
    )


def _interpolate_tensor_dict(
    base_values: dict[str, Any],
    trained_values: dict[str, Any],
    *,
    alpha: float,
) -> tuple[dict[str, Any], int, int, list[str]]:
    mixed: dict[str, Any] = {}
    interpolated = 0
    preserved = 0
    skipped: list[str] = []
    for key, base_value in base_values.items():
        trained_value = trained_values.get(key)
        if isinstance(base_value, torch.Tensor) and isinstance(trained_value, torch.Tensor):
            if _is_interpolatable(base_value, trained_value):
                mixed[key] = base_value * (1.0 - float(alpha)) + trained_value * float(alpha)
                interpolated += 1
            else:
                mixed[key] = base_value
                preserved += 1
                skipped.append(key)
        else:
            mixed[key] = base_value
            preserved += 1
            skipped.append(key)
    return mixed, interpolated, preserved, skipped


def interpolate_checkpoints(
    base_checkpoint: Path,
    trained_checkpoint: Path,
    output_checkpoint: Path,
    *,
    alpha: float,
) -> dict[str, Any]:
    _validate_alpha(alpha)
    base_checkpoint = Path(base_checkpoint)
    trained_checkpoint = Path(trained_checkpoint)
    output_checkpoint = Path(output_checkpoint)
    if not base_checkpoint.is_file():
        raise FileNotFoundError(base_checkpoint)
    if not trained_checkpoint.is_file():
        raise FileNotFoundError(trained_checkpoint)

    base = torch.load(str(base_checkpoint), map_location="cpu")
    trained = torch.load(str(trained_checkpoint), map_location="cpu")
    if not isinstance(base, dict) or not isinstance(trained, dict):
        raise TypeError("checkpoints must be dictionaries")

    mixed = dict(base)
    total_interpolated = 0
    total_preserved = 0
    skipped_by_section: dict[str, list[str]] = {}
    for section in ("state_dict", "ema_state_dict"):
        base_values = base.get(section)
        trained_values = trained.get(section)
        if isinstance(base_values, dict) and isinstance(trained_values, dict):
            section_mixed, interpolated, preserved, skipped = _interpolate_tensor_dict(
                base_values,
                trained_values,
                alpha=float(alpha),
            )
            mixed[section] = section_mixed
            total_interpolated += interpolated
            total_preserved += preserved
            if skipped:
                skipped_by_section[section] = skipped

    info = {
        "base_checkpoint": str(base_checkpoint),
        "trained_checkpoint": str(trained_checkpoint),
        "output_checkpoint": str(output_checkpoint),
        "alpha": float(alpha),
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "interpolated_tensors": int(total_interpolated),
        "preserved_tensors": int(total_preserved),
        "skipped_by_section": skipped_by_section,
        "note": "Floating tensors are interpolated as base*(1-alpha)+trained*alpha; checkpoint metadata is preserved from the base checkpoint.",
    }
    mixed["checkpoint_weight_interpolation"] = info
    output_checkpoint.parent.mkdir(parents=True, exist_ok=True)
    torch.save(mixed, str(output_checkpoint))
    return info


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Interpolate two compatible checkpoint weight files.")
    parser.add_argument("--base-checkpoint", required=True)
    parser.add_argument("--trained-checkpoint", required=True)
    parser.add_argument("--output-checkpoint", required=True)
    parser.add_argument("--alpha", type=float, required=True)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    info = interpolate_checkpoints(
        Path(args.base_checkpoint),
        Path(args.trained_checkpoint),
        Path(args.output_checkpoint),
        alpha=float(args.alpha),
    )
    print(json.dumps(info, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()

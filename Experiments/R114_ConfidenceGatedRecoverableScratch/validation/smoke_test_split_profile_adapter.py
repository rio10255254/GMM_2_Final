"""Small end-to-end smoke test for the split-profile validation adapter."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

import numpy as np
import torch


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from validation.r114_split_profile_adapter import (
    SPLIT_PROFILE_REQUIRED_MAPS,
    canonical_tile_config,
    load_model,
    predict_canonical_tiled,
)
from validation.validation_core import tensor_image, write_gray
from inference.tiled_runtime import save_internal_maps


def main() -> int:
    parser = argparse.ArgumentParser(description="Smoke-test R114 split-profile validation loading and tiling")
    parser.add_argument("--checkpoint", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--device", default="cpu")
    args = parser.parse_args()

    device = torch.device(args.device)
    model = load_model(args.checkpoint, device)
    height, width = 48, 56
    yy, xx = np.mgrid[:height, :width]
    radius = np.sqrt((xx - 28.0) ** 2 + (yy - 24.0) ** 2)
    image = 0.22 + 0.06 * xx / width + 0.48 * (radius < 14.0)
    image = torch.from_numpy(image.astype(np.float32))[None, None].to(device)

    # A small core keeps the output fixture compact.  The halo remains the
    # model-declared 192 px, so this exercises the same physical context rule
    # as large-image deployment rather than a relaxed smoke-only path.
    tile = canonical_tile_config(model, core=64)
    prediction = predict_canonical_tiled(model, image, tile)
    maps = prediction.maps
    output = Path(args.output).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    write_gray(output.parent / "input.png", tensor_image(image))
    write_gray(output.parent / "reconstruction.png", tensor_image(prediction.output))
    map_summary = save_internal_maps(output.parent / "internal_maps", maps)
    saved_arrays = list((output.parent / "internal_maps").glob("*.npy"))
    saved_previews = list((output.parent / "internal_maps").glob("*.png"))

    checks = {
        "checkpoint_loaded": True,
        "scratch_model_frozen": not any(parameter.requires_grad for parameter in model.parameters()),
        "canonical_grid_unshifted_nonoverlap": (
            tile.origin_y == 0 and tile.origin_x == 0 and tile.overlap == 0
        ),
        "halo_meets_model_contract": tile.halo >= model.minimum_halo_px,
        "output_shape_preserved": tuple(prediction.output.shape) == tuple(image.shape),
        "complete_coverage": bool((prediction.coverage >= 1).all()),
        "one_tile_for_fixture": prediction.tile_count == 1,
        "all_required_maps_present": set(SPLIT_PROFILE_REQUIRED_MAPS).issubset(maps),
        "all_outputs_finite": bool(torch.isfinite(prediction.output).all())
        and all(bool(torch.isfinite(value).all()) for value in maps.values()),
        "all_required_maps_match_spatial_shape": all(
            tuple(maps[name].shape[-2:]) == (height, width)
            for name in SPLIT_PROFILE_REQUIRED_MAPS
        ),
        "reconstruction_written": (output.parent / "reconstruction.png").is_file(),
        "all_maps_written_losslessly": len(saved_arrays) == len(maps),
        "all_map_previews_written": len(saved_previews) == len(maps),
        "saved_map_statistics_complete": set(map_summary) == set(maps),
    }
    summary = {
        "status": "complete" if all(checks.values()) else "failed",
        "checkpoint": str(Path(args.checkpoint).resolve()),
        "device": str(device),
        "minimum_halo_px": model.minimum_halo_px,
        "tile": vars(tile),
        "tile_count": prediction.tile_count,
        "output_shape": list(prediction.output.shape),
        "map_count": len(maps),
        "maps": sorted(maps),
        "checks": checks,
    }
    output.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2), flush=True)
    return 0 if summary["status"] == "complete" else 1


if __name__ == "__main__":
    raise SystemExit(main())

"""Command-line entry point for the fixed R114 validation scaffold."""
from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path

import torch

ROOT = Path(__file__).resolve().parents[1]
if str(Path(__file__).parent) not in sys.path:
    sys.path.insert(0, str(Path(__file__).parent))
from validation_core import DEFAULT_MAPS, TileConfig, resolve_record_paths, run_validation


DEFAULT_TILES = [
    TileConfig("grid_a", core=128, halo=64, overlap=0, origin_y=0, origin_x=0),
    TileConfig("grid_b_shifted_overlap", core=128, halo=64, overlap=32, origin_y=31, origin_x=47),
    TileConfig("grid_c_large_core", core=192, halo=96, overlap=64, origin_y=53, origin_x=71),
]


def load_module(path: Path):
    specification = importlib.util.spec_from_file_location("r114_validation_adapter", path)
    if specification is None or specification.loader is None:
        raise RuntimeError(f"Cannot import adapter: {path}")
    module = importlib.util.module_from_spec(specification)
    sys.modules[specification.name] = module
    specification.loader.exec_module(module)
    return module


def main() -> int:
    parser = argparse.ArgumentParser(description="Run R114 finite/identity/family/tile/internal-map validation")
    parser.add_argument("--adapter", required=True, help="Python file exposing load_model(checkpoint, device)")
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--checkpoint", default="")
    parser.add_argument("--device", default="cuda:0" if torch.cuda.is_available() else "cpu")
    args = parser.parse_args()

    manifest_path = Path(args.manifest).resolve()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    project_validation = json.loads((ROOT / "config" / "validation.json").read_text(encoding="utf-8"))
    records = resolve_record_paths(list(manifest["records"]), manifest_path.parent)
    tile_payload = manifest.get("tile_configs") or project_validation.get("tile_tests", {}).get("profiles", [])
    tiles = [TileConfig.from_mapping(item) for item in tile_payload] or DEFAULT_TILES
    required_maps = tuple(manifest.get("required_internal_maps", project_validation.get("required_internal_maps", DEFAULT_MAPS)))
    tolerances = project_validation.get("structural_tolerances_gray", {})
    thresholds = {
        "max_tile_mean_gray": tolerances.get("tile_mean", .05),
        "max_tile_p99_gray": tolerances.get("tile_p99", .25),
        "max_tile_absolute_gray": tolerances.get("tile_absolute", 1.0),
        **manifest.get("thresholds", {}),
    }
    adapter = load_module(Path(args.adapter).resolve())
    device = torch.device(args.device)
    model = adapter.load_model(args.checkpoint or None, device)
    summary = run_validation(
        model=model,
        records=records,
        output_dir=Path(args.output).resolve(),
        device=device,
        tile_configs=tiles,
        required_maps=required_maps,
        thresholds=thresholds,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2), flush=True)
    return 0 if summary["status"] == "complete" else 1


if __name__ == "__main__":
    raise SystemExit(main())

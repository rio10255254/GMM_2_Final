from __future__ import annotations

import argparse
import importlib.util
import json
import os
import sys
from pathlib import Path
from typing import Any


ADAPTER_PATH = Path(__file__).resolve()
MODEL_ROOT = ADAPTER_PATH.parent
INTERNAL_ROOT = MODEL_ROOT.parent


def _load_module(module_path: Path, module_name: str):
    if str(MODEL_ROOT) not in sys.path:
        sys.path.insert(0, str(MODEL_ROOT))
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load module from {module_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def _coerce_value(template: Any, value: Any) -> Any:
    if isinstance(template, tuple) and isinstance(value, list):
        return tuple(value)
    return value


def _resolve_internal(relative_text: str) -> Path:
    return (INTERNAL_ROOT / relative_text).resolve()


def _resolved_recipe(recipe_path: Path) -> dict:
    data = json.loads(recipe_path.read_text(encoding="utf-8"))
    deployed_ckpt = _resolve_internal(data["deploy_checkpoint_relative"])
    seed_ckpt = _resolve_internal(data["seed_checkpoint_relative"])
    psf_path = _resolve_internal(data["formal_psf_relative"])
    train_src = _resolve_internal(data["train_source_root_relative"])
    train_lbl = _resolve_internal(data["train_label_root_relative"])
    payload = {
        **data,
        "recipe_path": str(recipe_path.resolve()),
        "deploy_checkpoint": str(deployed_ckpt),
        "seed_checkpoint": str(seed_ckpt),
        "formal_psf": str(psf_path),
        "train_source_root": str(train_src),
        "train_label_root": str(train_lbl),
    }
    return payload


def _apply_recipe(train_mod, recipe: dict) -> None:
    train_mod.CFG = train_mod.TrainConfig()
    cfg = train_mod.CFG

    cfg.SPLIT_SEED = int(recipe["seed"])
    cfg.REPRO_SEED = int(recipe["seed"])
    cfg.SEED_DETERMINISTIC = bool(recipe["deterministic"])
    cfg.REPRO_MODE = bool(recipe["deterministic"])
    cfg.REPRO_DETERMINISTIC = bool(recipe["deterministic"])
    cfg.REPRO_DISABLE_TF32 = bool(recipe["deterministic"])

    for key, value in recipe["overrides"].items():
        if key == "PRETRAINED_PATH":
            value = recipe["seed_checkpoint"]
        elif key == "PSF_FITTED_PATH":
            value = recipe["formal_psf"]
        current = getattr(cfg, key, None)
        setattr(cfg, key, _coerce_value(current, value))

    train_mod.TRAIN_SRC_DIR = recipe["train_source_root"]
    train_mod.TRAIN_LBL_DIR = recipe["train_label_root"]


def build_payload(recipe_path: Path, progress_root: Path, device: str | None) -> dict:
    recipe = _resolved_recipe(recipe_path)
    return {
        "winner_name": recipe["winner_name"],
        "winner_tag": recipe["winner_tag"],
        "model_name": recipe["model_name"],
        "recipe_path": recipe["recipe_path"],
        "seed": recipe["seed"],
        "deterministic": recipe["deterministic"],
        "progress_root": str(progress_root.resolve()),
        "device": device,
        "deploy_checkpoint": recipe["deploy_checkpoint"],
        "seed_checkpoint": recipe["seed_checkpoint"],
        "formal_psf": recipe["formal_psf"],
        "train_source_root": recipe["train_source_root"],
        "train_label_root": recipe["train_label_root"],
        "train_include_subdirs": recipe["train_include_subdirs"],
        "seq_include_subdirs": recipe["seq_include_subdirs"],
        "hashes": recipe.get("hashes", {}),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--recipe", type=Path, required=True)
    parser.add_argument("--progress-root", type=Path, required=True)
    parser.add_argument("--device", default=None)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    payload = build_payload(args.recipe, args.progress_root, args.device)
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    if args.dry_run:
        return 0

    recipe = _resolved_recipe(args.recipe)
    train_mod = _load_module(
        MODEL_ROOT / "GeoEdgeAlignSR_v1_Train_v5_NoCoord_return_v2_SimpleTest.py",
        "geoedge_formal_train_mod",
    )
    _apply_recipe(train_mod, recipe)

    argv = [
        str(MODEL_ROOT / "GeoEdgeAlignSR_v1_Train_v5_NoCoord_return_v2_SimpleTest.py"),
        "--progress-root",
        str(args.progress_root),
        "--seed_deterministic",
    ]
    if args.device:
        argv.extend(["--device", args.device])
    sys.argv = argv
    train_mod.main()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
import shutil
from pathlib import Path

import cv2
import numpy as np
import torch


ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "config" / "experiment.json"
RESULTS = ROOT / "results"
RECON = RESULTS / "reconstructions"
SCRIPT_VERSION = "r82_infer_v1"
IMAGE_EXTENSIONS = {".bmp", ".png", ".jpg", ".jpeg", ".tif", ".tiff"}


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def import_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def collect_images(config: dict, dataset: str) -> tuple[Path | None, list[tuple[Path, Path]]]:
    if dataset == "real_fov":
        root = Path(config["real_fov"]["locked_raw_root"])
        rows = [(path, path.relative_to(root)) for path in sorted(root.rglob("*.bmp"))]
        expected = int(config["real_fov"]["expected_frames"])
        if len(rows) != expected:
            raise RuntimeError(f"real_fov expected {expected} images, found {len(rows)}")
        return root, rows
    if dataset in config["external_acm_suites"]:
        root = Path(config["external_acm_suites"][dataset]["dataset_root"]) / "src"
        rows = [(path, path.relative_to(root)) for path in sorted(root.rglob("*.bmp"))]
        expected = int(config["external_acm_suites"][dataset]["expected_images"])
        if len(rows) != expected:
            raise RuntimeError(f"{dataset} expected {expected} images, found {len(rows)}")
        return root, rows
    if dataset == "sem_acm":
        root = Path(config["sem_acm"]["raw_input_dir"])
        exposures = [int(value) for value in config["sem_acm"]["optical_exposures"]]
        rows = [(root / f"{value}.bmp", Path(f"{value}.bmp")) for value in exposures]
        if not all(path.is_file() for path, _ in rows):
            raise FileNotFoundError("SEM optical exposure stack is incomplete")
        return root, rows
    if dataset == "junhua":
        rows: list[tuple[Path, Path]] = []
        for sequence, item in config["junhua"]["sequences"].items():
            root = Path(item["input_dir"])
            all_paths = sorted(
                path for path in root.iterdir()
                if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS
            )
            if len(all_paths) != int(item["source_frames"]):
                raise RuntimeError(f"{sequence}: source coverage changed")
            selected = all_paths[int(item["select_start"]): int(item["select_start"]) + int(item["select_step"]) * int(item["selected_frames"]): int(item["select_step"])]
            if len(selected) != int(item["selected_frames"]):
                raise RuntimeError(f"{sequence}: selected coverage changed")
            rows.extend((path, Path(sequence) / path.name) for path in selected)
        return None, rows
    raise KeyError(dataset)


def selection_digest(rows: list[tuple[Path, Path]]) -> str:
    payload = "\n".join(
        f"{relative.as_posix()}|{source.stat().st_size}|{source.stat().st_mtime_ns}"
        for source, relative in rows
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def read_gray(path: Path) -> np.ndarray:
    image = cv2.imdecode(np.fromfile(path, dtype=np.uint8), cv2.IMREAD_GRAYSCALE)
    if image is None:
        raise OSError(path)
    return image


def valid_existing(source: Path, target: Path) -> bool:
    if not target.is_file():
        return False
    try:
        return read_gray(source).shape == read_gray(target).shape
    except OSError:
        return False


def legacy_state(checkpoint: dict, state_key: str) -> dict:
    state = checkpoint.get(state_key)
    if not isinstance(state, dict):
        raise RuntimeError(f"checkpoint does not contain {state_key}")
    return {
        (name[7:] if name.startswith("module.") else name): value
        for name, value in state.items()
    }


def build_legacy_model(config: dict, item: dict):
    legacy = import_module(Path(config["runtime"]["legacy_inference_module"]), "r82_legacy_inference")
    checkpoint_path = Path(item["checkpoint"])
    checkpoint = torch.load(checkpoint_path, map_location="cpu")
    state = legacy_state(checkpoint, item["state_key"])
    arch = legacy.infer_arch_from_state(state, ckpt_obj=checkpoint)
    mode = item["mode"]
    cleanup_dir: Path | None = None

    if mode == "checkpoint_native":
        psf_path, cleanup_dir = legacy.build_temp_psf_mat_from_state(state)
        if psf_path is None:
            raise RuntimeError(f"{checkpoint_path}: checkpoint has no physical PSF buffer")
        weak_psf_enable = bool(arch["weak_psf_enable"])
        psf_deconv_reg = float(arch["psf_deconv_reg"])
        psf_phys_alpha = float(arch["psf_phys_alpha_init"])
        psf_source = "checkpoint_buffer"
    elif mode == "r61_psf_off":
        psf_path = Path(item["psf_fitted_path"])
        if not psf_path.is_file():
            raise FileNotFoundError(psf_path)
        weak_psf_enable = bool(item["weak_psf_enable"])
        psf_deconv_reg = float(item["psf_deconv_reg"])
        psf_phys_alpha = float(item["psf_phys_alpha"])
        psf_source = "locked_external_calibration"
    else:
        raise ValueError(mode)

    model = legacy.GeoEdgeAlignSR_v1_v5_NoCoord(
        in_ch=arch["in_ch"],
        base=arch["base"],
        use_physics_layer=arch["use_physics_layer"],
        use_sigmoid_output=True,
        use_upsample_conv=True,
        use_band_limit=arch["use_band_limit"],
        band_limit_cutoff=0.95,
        band_limit_order=8.0,
        psf_fitted_path=str(psf_path),
        psf_grid_rows=None,
        psf_grid_cols=None,
        psf_use_stack_mean=True,
        psf_deconv_reg=psf_deconv_reg,
        psf_phys_alpha_init=psf_phys_alpha,
        psf_phys_trainable_reg=False,
        weak_psf_enable=weak_psf_enable,
        weak_psf_k=int(arch["weak_psf_k"]),
        weak_psf_indices=None,
        weak_psf_reg=float(arch["weak_psf_reg"]),
        weak_psf_beta_init=float(arch["weak_psf_beta_init"]),
        weak_psf_gating_temp=float(arch["weak_psf_gating_temp"] if arch["weak_psf_gating_temp"] is not None else 2.5),
        weak_psf_psf_temp=float(arch["weak_psf_psf_temp"]),
        weak_psf_entropy_mix=float(arch["weak_psf_entropy_mix"]),
        weak_psf_trainable_reg=False,
        weak_psf_lowfreq_ratio=float(arch["weak_psf_lowfreq_ratio"]),
        weak_psf_beta_min=0.0,
        weak_psf_beta_max=0.10,
        weak_psf_beta_scale_max=float(arch["weak_psf_beta_scale_max"]),
        weak_psf_deconv_mode="clamp",
        weak_psf_inject="y2",
        boundary_residual_adapter_enable=bool(arch["boundary_residual_adapter_enable"]),
        boundary_residual_adapter_hidden=int(arch["boundary_residual_adapter_hidden"]),
        boundary_residual_adapter_max=float(arch["boundary_residual_adapter_max"]),
        boundary_residual_adapter_gate_bias=float(arch["boundary_residual_adapter_gate_bias"]),
        boundary_residual_adapter_delta_bias=bool(arch["boundary_residual_adapter_delta_bias"]),
        boundary_residual_adapter_zero_mean=bool(arch["boundary_residual_adapter_zero_mean"]),
        boundary_residual_adapter_edge_gate=bool(arch["boundary_residual_adapter_edge_gate"]),
        boundary_residual_adapter_polarity_split=bool(arch["boundary_residual_adapter_polarity_split"]),
        boundary_residual_adapter_orientation_inputs=bool(arch["boundary_residual_adapter_orientation_inputs"]),
        raw_anchor_output_mode=str(arch["raw_anchor_output_mode"]),
        raw_anchor_output_alpha=float(arch["raw_anchor_output_alpha"]),
        raw_anchor_output_sigma=float(arch["raw_anchor_output_sigma"]),
        raw_anchor_output_detail_gain=float(arch["raw_anchor_output_detail_gain"]),
        quality_gate_enable=bool(arch["quality_gate_enable"]),
        quality_gate_hidden=int(arch["quality_gate_hidden"]),
        quality_gate_scale_min=float(arch["quality_gate_scale_min"]),
        quality_gate_scale_max=float(arch["quality_gate_scale_max"]),
    )
    legacy.load_weights(model, state, strict=False)

    physics = getattr(model, "physics_layer", None)
    if physics is not None:
        if mode == "r61_psf_off":
            physics.reg.data.fill_(psf_deconv_reg)
            physics.alpha.data.fill_(psf_phys_alpha)
        physics_reg = float(physics.reg.detach().cpu().item())
        physics_alpha = float(physics.alpha.detach().cpu().item())
        physics_alpha_min = float(getattr(physics, "alpha_min", math.nan))
        physics_alpha_max = float(getattr(physics, "alpha_max", math.nan))
    else:
        physics_reg = physics_alpha = physics_alpha_min = physics_alpha_max = math.nan

    device = config["runtime"]["device"]
    model.to(device).eval()
    details = {
        "engine": "legacy",
        "mode": mode,
        "state_key": item["state_key"],
        "psf_source": psf_source,
        "weak_psf_enable": weak_psf_enable,
        "physics_reg_tensor": physics_reg,
        "physics_alpha_tensor": physics_alpha,
        "physics_alpha_min": physics_alpha_min,
        "physics_alpha_max": physics_alpha_max,
        "boundary_adapter": bool(arch["boundary_residual_adapter_enable"]),
    }
    return model, legacy, cleanup_dir, details


def build_r79_model(config: dict, item: dict):
    module = import_module(Path(config["runtime"]["r79_inference_module"]), "r82_r79_inference")
    model, state_key = module.build_model(Path(item["checkpoint"]), config["runtime"]["device"], True)
    if state_key != item["state_key"]:
        raise RuntimeError(f"R79 selected {state_key}, expected {item['state_key']}")
    checkpoint = torch.load(item["checkpoint"], map_location="cpu")
    if int(checkpoint.get("epoch", -1)) != int(item["expected_epoch"]):
        raise RuntimeError("R79 epoch identity changed")
    details = {
        "engine": "r79",
        "mode": item["mode"],
        "state_key": state_key,
        "tile_size": int(config["runtime"]["r79_full_frame_tile_size"]),
        "overlap": int(config["runtime"]["r79_overlap"]),
        "boundary_adapter": True,
    }
    return model, module, None, details


def output_root(dataset: str, model: str) -> Path:
    return RECON / dataset / model


def manifest_is_valid(path: Path, identity: dict, expected: int) -> bool:
    manifest_path = path / "inference_manifest.json"
    if not manifest_path.is_file():
        return False
    manifest = read_json(manifest_path)
    records = manifest.get("records", [])
    return (
        manifest.get("identity") == identity
        and int(manifest.get("image_count", -1)) == expected
        and len(records) == expected
        and all(Path(row["output"]).is_file() for row in records)
    )


def run(config: dict, model_label: str, dataset: str) -> dict:
    item = config["models"][model_label]
    checkpoint = Path(item["checkpoint"])
    if not checkpoint.is_file():
        raise FileNotFoundError(checkpoint)
    checkpoint_hash = sha256(checkpoint)
    if checkpoint_hash != item["checkpoint_sha256"]:
        raise RuntimeError(f"{model_label}: checkpoint hash changed")
    _, rows = collect_images(config, dataset)
    destination = output_root(dataset, model_label)
    identity = {
        "script_version": SCRIPT_VERSION,
        "model": model_label,
        "dataset": dataset,
        "checkpoint_sha256": checkpoint_hash,
        "state_key": item["state_key"],
        "engine": item["engine"],
        "mode": item["mode"],
        "selection_digest": selection_digest(rows),
        "image_count": len(rows),
    }
    if manifest_is_valid(destination, identity, len(rows)):
        print(f"[reuse] {model_label}/{dataset}: {len(rows)} images", flush=True)
        return read_json(destination / "inference_manifest.json")

    identity_path = destination / "run_identity.json"
    if identity_path.is_file() and read_json(identity_path) != identity:
        raise RuntimeError(f"Output identity conflict: {destination}")
    write_json(identity_path, identity)

    if item["engine"] == "legacy":
        model, module, cleanup_dir, details = build_legacy_model(config, item)
    elif item["engine"] == "r79":
        model, module, cleanup_dir, details = build_r79_model(config, item)
    else:
        raise ValueError(item["engine"])

    device = config["runtime"]["device"]
    records = []
    try:
        for index, (source, relative) in enumerate(rows, start=1):
            target = (destination / relative).with_suffix(".bmp")
            if not valid_existing(source, target):
                target.parent.mkdir(parents=True, exist_ok=True)
                if item["engine"] == "legacy":
                    module.run_one(
                        model,
                        torch.device(device),
                        source,
                        target,
                        int(config["runtime"]["align_factor"]),
                        gt_path=None,
                        anchor_output_mode="none",
                    )
                else:
                    image = module.read_gray(source)
                    reconstruction = module.infer_tiled(
                        model,
                        image,
                        device,
                        int(config["runtime"]["r79_full_frame_tile_size"]),
                        int(config["runtime"]["r79_overlap"]),
                    )
                    module.write_bmp(target, reconstruction)
            if not valid_existing(source, target):
                raise RuntimeError(f"Invalid output: {target}")
            records.append({
                "input": str(source.resolve()),
                "relative": relative.as_posix(),
                "output": str(target.resolve()),
                "shape": list(read_gray(source).shape),
            })
            if index == 1 or index % 10 == 0 or index == len(rows):
                print(f"[{model_label}/{dataset}] {index}/{len(rows)}", flush=True)
    finally:
        del model
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
        if cleanup_dir is not None and cleanup_dir.is_dir():
            shutil.rmtree(cleanup_dir)

    manifest = {
        "identity": identity,
        "model_details": details,
        "checkpoint": str(checkpoint.resolve()),
        "checkpoint_sha256": checkpoint_hash,
        "image_count": len(records),
        "records": records,
    }
    write_json(destination / "inference_manifest.json", manifest)
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description="R82 locked multi-model inference")
    parser.add_argument("--model", required=True)
    parser.add_argument("--dataset", choices=("real_fov", "junhua", "R73_novel_shapes", "R74_hard_microscopy", "sem_acm"))
    args = parser.parse_args()
    config = read_json(CONFIG_PATH)
    if args.model not in config["models"]:
        parser.error(f"unknown model: {args.model}")
    run(config, args.model, args.dataset)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Pre-formal GPU checks for R93 pair/bundle memory, gradients, and tiled parity."""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import time

import torch


ROOT = Path(__file__).resolve().parents[1]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def synthetic_batch(scene_batch: int, patch: int, views: int) -> dict:
    cpu_generator = torch.Generator().manual_seed(891122 + patch)
    source = torch.rand((scene_batch, views, 1, patch, patch), generator=cpu_generator)
    target = (source * 0.92 + 0.04).clamp(0, 1)
    noise_free_source = (source * 0.965 + 0.0175).clamp(0, 1)
    mask = (target > 0.5).float()
    sdf = (mask - 0.5) * 8.0
    pair_kind = torch.full((scene_batch,), 3 if views == 4 else 0, dtype=torch.int64)
    if views == 2:
        pair_kind[::3] = 1
        pair_kind[1::3] = 2
    origins = torch.zeros((scene_batch, views, 2), dtype=torch.int64)
    if views == 2:
        origins[:, 1] = torch.tensor([8, 8])
        origins[pair_kind != 0, 1] = 0
    motion = torch.zeros((scene_batch, views, 2), dtype=torch.float32)
    if views == 2:
        motion[pair_kind == 1, 0] = torch.tensor([-0.25, 0.0])
        motion[pair_kind == 1, 1] = torch.tensor([0.25, 0.0])
    return {
        "source": source,
        "noise_free_source": noise_free_source,
        "target": target,
        "mask": mask,
        "sdf": sdf,
        "origins": origins,
        "motion": motion,
        "identity": torch.zeros((scene_batch, views), dtype=torch.bool),
        "pair_kind": pair_kind,
        "observation_indices": torch.arange(views, dtype=torch.int64).repeat(scene_batch, 1),
        "exposure_path_position": torch.tensor([0.0, 0.35, 0.65, 1.0][:views], dtype=torch.float32).repeat(scene_batch, 1) if views == 4 else torch.full((scene_batch, views), -1.0),
        "consistency_confidence": torch.full((scene_batch,), 0.75),
        "detail_recoverability": torch.full((scene_batch, views), 0.72),
        "boundary_level": torch.full((scene_batch,), 0.58),
        "foreground_mean": torch.full((scene_batch,), 0.85),
        "background_mean": torch.full((scene_batch,), 0.15),
        "transition_fraction": torch.full((scene_batch,), 0.58),
        "polarity": torch.ones(scene_batch),
        "crop_foreground_fraction": torch.full((scene_batch,), 0.5),
        "crop_boundary_pixels": torch.full((scene_batch,), max(256, patch), dtype=torch.int64),
        "role": ["synthetic_benchmark"] * scene_batch,
        "scene_id": [f"benchmark_{i}" for i in range(scene_batch)],
    }


def stage_check(model_module, trainer, device: torch.device, patch: int, core: int, scene_batch: int, views: int, *, base: int = 24) -> dict:
    if device.type == "cuda":
        torch.cuda.empty_cache(); torch.cuda.reset_peak_memory_stats(device)
        free_before, total_memory = torch.cuda.mem_get_info(device)
        baseline_used_gib = (total_memory - free_before) / 2**30
    else:
        total_memory = 0
        baseline_used_gib = 0.0
    model = model_module.build_model(base=base).to(device).train()
    optimizer = torch.optim.AdamW(model.parameters(), lr=1e-4)
    batch = synthetic_batch(scene_batch, patch, views)
    flat = batch["source"].to(device).reshape(scene_batch * views, 1, patch, patch)
    started = time.perf_counter()
    with torch.autocast(device_type="cuda", dtype=torch.bfloat16, enabled=device.type == "cuda"):
        details = model(flat, return_details=True)
        total, parts, _aux = trainer.loss_components(details, batch, patch, core, 31, enable_topology=True)
    if not torch.isfinite(total):
        raise RuntimeError("Non-finite benchmark loss")
    total.backward()
    finite = all(parameter.grad is None or bool(torch.isfinite(parameter.grad).all()) for parameter in model.parameters())
    if not finite:
        raise RuntimeError("Non-finite benchmark gradient")
    optimizer.step()
    if device.type == "cuda":
        torch.cuda.synchronize(device)
    report = {
        "patch": patch,
        "core": core,
        "scene_batch": scene_batch,
        "views": views,
        "flattened_image_batch": scene_batch * views,
        "loss": float(total.detach()),
        "seconds": time.perf_counter() - started,
        "model_base": base,
        "peak_allocated_gib": torch.cuda.max_memory_allocated(device) / 2**30 if device.type == "cuda" else 0.0,
        "peak_reserved_gib": torch.cuda.max_memory_reserved(device) / 2**30 if device.type == "cuda" else 0.0,
        "gradients_finite": finite,
        "losses": {name: float(value) for name, value in parts.items()},
    }
    if device.type == "cuda":
        report["reserved_headroom_gib"] = total_memory / 2**30 - report["peak_reserved_gib"]
        report["estimated_system_peak_free_gib"] = total_memory / 2**30 - baseline_used_gib - report["peak_reserved_gib"]
        if report["reserved_headroom_gib"] < 10.0 or report["estimated_system_peak_free_gib"] < 7.0:
            raise RuntimeError(f"Unsafe GPU headroom: {report}")
    del optimizer, model, flat, details, total, parts, batch
    if device.type == "cuda":
        torch.cuda.empty_cache()
    return report


@torch.inference_mode()
def tiled_check(model_module, inference, device: torch.device) -> dict:
    torch.manual_seed(891144)
    model = model_module.build_model(base=24).to(device).eval()
    for head_name in ("low_head", "nuisance_head", "restoration_head", "edge_head"):
        final = getattr(model, head_name)[-1]
        torch.nn.init.normal_(final.weight, mean=0.0, std=0.03)
        torch.nn.init.normal_(final.bias, mean=0.0, std=0.02)
    generator = torch.Generator(device="cpu").manual_seed(891155)
    image = torch.rand((1, 1, 533, 619), generator=generator).to(device)

    def difference_metrics(reference: torch.Tensor, candidate: torch.Tensor, core: int) -> dict:
        difference = (reference - candidate).abs()
        seam = torch.zeros_like(difference, dtype=torch.bool)
        for location in range(core, difference.shape[-2], core):
            seam[..., max(0, location - 1):min(difference.shape[-2], location + 2), :] = True
        for location in range(core, difference.shape[-1], core):
            seam[..., :, max(0, location - 1):min(difference.shape[-1], location + 2)] = True
        seam_mean = float(difference[seam].mean() * 255.0) if bool(seam.any()) else 0.0
        interior_mean = float(difference[~seam].mean() * 255.0) if bool((~seam).any()) else 0.0
        return {
            "mean_abs_gray": float(difference.mean() * 255.0),
            "p99_abs_gray": float(torch.quantile(difference, 0.99) * 255.0),
            "max_abs_gray": float(difference.max() * 255.0),
            "seam_mean_abs_gray": seam_mean,
            "interior_mean_abs_gray": interior_mean,
            "seam_excess_gray": max(0.0, seam_mean - interior_mean),
        }

    cases = []
    outputs: dict[tuple[int, int, bool], torch.Tensor] = {}
    precision_modes = [("float32", False)] + ([('bfloat16', True)] if device.type == "cuda" else [])
    for precision_name, amp in precision_modes:
        for core in (256, 384, 512):
            full = inference.reconstruct_full_reference(model, image, core_size=core, halo=192, amp=amp)
            for tile_batch in (1, 2):
                tiled = inference.reconstruct_tensor(model, image, core_size=core, halo=192, tile_batch=tile_batch, amp=amp)
                outputs[(core, tile_batch, amp)] = tiled
                metrics = difference_metrics(full, tiled, core)
                row = {
                    "precision": precision_name,
                    "core": core,
                    "halo": 192,
                    "tile_batch": tile_batch,
                    "non_identity_mean_gray": float((tiled - image).abs().mean() * 255.0),
                    **metrics,
                }
                if not amp and (
                    row["mean_abs_gray"] > 0.001
                    or row["p99_abs_gray"] > 0.01
                    or row["max_abs_gray"] > 0.02
                    or row["seam_excess_gray"] > 0.01
                ):
                    raise RuntimeError(f"Float32 tiled parity failed: {row}")
                if amp and tile_batch == 1 and (
                    row["mean_abs_gray"] > 0.01
                    or row["p99_abs_gray"] > 0.05
                    or row["seam_excess_gray"] > 0.05
                ):
                    raise RuntimeError(f"Canonical bfloat16 tiled distribution failed: {row}")
                cases.append(row)
    precision_sensitivity = None
    if device.type == "cuda":
        precision_sensitivity = difference_metrics(outputs[(512, 1, False)], outputs[(512, 1, True)], 512)
    return {
        "image_shape": list(image.shape),
        "primary_contract": {"precision": "float32", "core": 512, "halo": 192, "tile_batch": 1},
        "bfloat16_policy": "opt_in_diagnostic_only",
        "cases": cases,
        "precision_sensitivity_at_primary_shape": precision_sensitivity,
        "passed": True,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--device", default="cuda:0")
    parser.add_argument("--setup-cpu", action="store_true")
    parser.add_argument("--skip-stages", action="store_true")
    parser.add_argument("--skip-tile", action="store_true")
    args = parser.parse_args()
    if not args.setup_cpu and not torch.cuda.is_available():
        raise RuntimeError("CUDA is required for the pre-formal benchmark")
    device = torch.device("cpu" if args.setup_cpu else args.device)
    model_module = load("r93_model_benchmark", ROOT / "model" / "r93_model.py")
    trainer = load("r93_trainer_benchmark", ROOT / "training" / "train_r93.py")
    inference = load("r93_inference_benchmark", ROOT / "inference" / "reconstruct.py")
    payload = {
        "benchmark_scope": "setup_cpu" if args.setup_cpu else "formal_gpu",
        "formal_gpu_benchmark_complete": not args.setup_cpu,
        "device": "CPU" if args.setup_cpu else torch.cuda.get_device_name(device),
        "total_memory_gib": 0.0 if args.setup_cpu else torch.cuda.get_device_properties(device).total_memory / 2**30,
        "architecture_sha256": sha256_file(ROOT / "model" / "r93_model.py"),
        "trainer_sha256": sha256_file(ROOT / "training" / "train_r93.py"),
        "inference_sha256": sha256_file(ROOT / "inference" / "reconstruct.py"),
        "stages": [],
    }
    if args.setup_cpu:
        for views in (2, 4):
            result = stage_check(model_module, trainer, device, 128, 64, 1, views, base=8)
            payload["stages"].append(result)
            print(json.dumps({"setup_stage_complete": result}, ensure_ascii=False), flush=True)
    elif not args.skip_stages:
        design = json.loads((ROOT / "config" / "experiment_design.json").read_text(encoding="utf-8"))
        stages = design["training"]["stages"]
        for patch, core, batch in ((int(stage["patch_size"]), int(stage["core_size"]), int(stage["scene_batch_size"])) for stage in stages):
            for views, scene_batch in ((2, batch), (4, max(1, batch // 2))):
                result = stage_check(model_module, trainer, device, patch, core, scene_batch, views)
                payload["stages"].append(result)
                print(json.dumps({"stage_complete": result}, ensure_ascii=False), flush=True)
    if not args.setup_cpu and not args.skip_tile:
        payload["tile_parity"] = tiled_check(model_module, inference, device)
        print(json.dumps({"tile_complete": payload["tile_parity"]}, ensure_ascii=False), flush=True)
    output = ROOT / "results" / ("setup_benchmark.json" if args.setup_cpu else "preformal_benchmark.json")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({"passed": True, "report": str(output)}, ensure_ascii=False), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

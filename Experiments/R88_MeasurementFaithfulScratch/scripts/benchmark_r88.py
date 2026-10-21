"""Pre-formal GPU checks for R88 memory, gradients, and tiled parity."""
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


def synthetic_batch(scene_batch: int, patch: int, device: torch.device) -> dict:
    cpu_generator = torch.Generator().manual_seed(881122 + patch)
    source = torch.rand((scene_batch, 2, 1, patch, patch), generator=cpu_generator)
    target = (source * 0.92 + 0.04).clamp(0, 1)
    mask = (target > 0.5).float()
    sdf = (mask - 0.5) * 8.0
    pair_kind = torch.zeros(scene_batch, dtype=torch.int64)
    pair_kind[::3] = 1
    origins = torch.zeros((scene_batch, 2, 2), dtype=torch.int64)
    origins[:, 1] = torch.tensor([8, 8])
    origins[pair_kind == 1, 1] = 0
    motion = torch.zeros((scene_batch, 2, 2), dtype=torch.float32)
    motion[pair_kind == 1, 0] = torch.tensor([-0.25, 0.0])
    motion[pair_kind == 1, 1] = torch.tensor([0.25, 0.0])
    return {
        "source": source,
        "target": target,
        "mask": mask,
        "sdf": sdf,
        "origins": origins,
        "motion": motion,
        "identity": torch.zeros((scene_batch, 2), dtype=torch.bool),
        "pair_kind": pair_kind,
        "midpoint": torch.full((scene_batch,), 0.5),
        "polarity": torch.ones(scene_batch),
        "role": ["synthetic_benchmark"] * scene_batch,
        "scene_id": [f"benchmark_{i}" for i in range(scene_batch)],
    }


def stage_check(model_module, trainer, device: torch.device, patch: int, core: int, scene_batch: int) -> dict:
    torch.cuda.empty_cache(); torch.cuda.reset_peak_memory_stats(device)
    model = model_module.build_model(base=24).to(device).train()
    optimizer = torch.optim.AdamW(model.parameters(), lr=1e-4)
    batch = synthetic_batch(scene_batch, patch, device)
    flat = batch["source"].to(device).reshape(scene_batch * 2, 1, patch, patch)
    started = time.perf_counter()
    with torch.autocast(device_type="cuda", dtype=torch.bfloat16):
        details = model(flat, return_details=True)
        total, parts, _aux = trainer.loss_components(details, batch, patch, core, enable_topology=True)
    if not torch.isfinite(total):
        raise RuntimeError("Non-finite benchmark loss")
    total.backward()
    finite = all(parameter.grad is None or bool(torch.isfinite(parameter.grad).all()) for parameter in model.parameters())
    if not finite:
        raise RuntimeError("Non-finite benchmark gradient")
    optimizer.step(); torch.cuda.synchronize(device)
    report = {
        "patch": patch,
        "core": core,
        "scene_batch": scene_batch,
        "flattened_image_batch": scene_batch * 2,
        "loss": float(total.detach()),
        "seconds": time.perf_counter() - started,
        "peak_allocated_gib": torch.cuda.max_memory_allocated(device) / 2**30,
        "peak_reserved_gib": torch.cuda.max_memory_reserved(device) / 2**30,
        "gradients_finite": finite,
        "losses": {name: float(value) for name, value in parts.items()},
    }
    del optimizer, model, flat, details, total, parts, batch
    torch.cuda.empty_cache()
    return report


@torch.inference_mode()
def tiled_check(model_module, inference, device: torch.device) -> dict:
    torch.manual_seed(881144)
    model = model_module.build_model(base=24).to(device).eval()
    for head_name in ("low_head", "high_head", "confidence_head"):
        final = getattr(model, head_name)[-1]
        torch.nn.init.normal_(final.weight, mean=0.0, std=0.03)
        torch.nn.init.normal_(final.bias, mean=0.0, std=0.02)
    generator = torch.Generator(device="cpu").manual_seed(881155)
    image = torch.rand((1, 1, 533, 619), generator=generator).to(device)
    full = inference.reconstruct_full_reference(model, image, core_size=256, halo=192, amp=True)
    tiled = inference.reconstruct_tensor(model, image, core_size=256, halo=192, tile_batch=2, amp=True)
    difference = (full - tiled).abs()
    report = {
        "image_shape": list(image.shape),
        "core": 256,
        "halo": 192,
        "mean_abs_gray": float(difference.mean() * 255.0),
        "p99_abs_gray": float(torch.quantile(difference, 0.99) * 255.0),
        "max_abs_gray": float(difference.max() * 255.0),
        "non_identity_mean_gray": float((tiled - image).abs().mean() * 255.0),
    }
    if report["max_abs_gray"] > 0.02:
        raise RuntimeError(f"Tiled parity failed: {report}")
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--device", default="cuda:0")
    parser.add_argument("--skip-stages", action="store_true")
    parser.add_argument("--skip-tile", action="store_true")
    args = parser.parse_args()
    if not torch.cuda.is_available():
        raise RuntimeError("CUDA is required for the pre-formal benchmark")
    device = torch.device(args.device)
    model_module = load("r88_model_benchmark", ROOT / "model" / "r88_model.py")
    trainer = load("r88_trainer_benchmark", ROOT / "training" / "train_r88.py")
    inference = load("r88_inference_benchmark", ROOT / "inference" / "reconstruct.py")
    payload = {
        "device": torch.cuda.get_device_name(device),
        "total_memory_gib": torch.cuda.get_device_properties(device).total_memory / 2**30,
        "architecture_sha256": sha256_file(ROOT / "model" / "r88_model.py"),
        "trainer_sha256": sha256_file(ROOT / "training" / "train_r88.py"),
        "inference_sha256": sha256_file(ROOT / "inference" / "reconstruct.py"),
        "stages": [],
    }
    if not args.skip_stages:
        for patch, core, batch in ((384, 256, 12), (640, 384, 6), (896, 512, 3)):
            result = stage_check(model_module, trainer, device, patch, core, batch)
            payload["stages"].append(result)
            print(json.dumps({"stage_complete": result}, ensure_ascii=False), flush=True)
    if not args.skip_tile:
        payload["tile_parity"] = tiled_check(model_module, inference, device)
        print(json.dumps({"tile_complete": payload["tile_parity"]}, ensure_ascii=False), flush=True)
    output = ROOT / "results" / "preformal_benchmark.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({"passed": True, "report": str(output)}, ensure_ascii=False), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

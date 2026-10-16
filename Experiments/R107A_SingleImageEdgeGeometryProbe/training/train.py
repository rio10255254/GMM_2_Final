"""Train R107 from scratch.  No checkpoint inheritance is supported."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import random
import time
from pathlib import Path
from typing import Any

import cv2
import numpy as np
import torch
import torch.nn.functional as F
from torch.utils.data import DataLoader


ROOT = Path(__file__).resolve().parents[1]
CONFIG = json.loads((ROOT / "config" / "experiment.json").read_text(encoding="utf-8"))
import sys
sys.path.insert(0, str(ROOT / "model")); sys.path.insert(0, str(ROOT / "training"))
from r107_model import build_model, count_parameters  # noqa: E402
from r107_dataset import R107Dataset  # noqa: E402
from losses import combine, loss_components, soft_probability  # noqa: E402


def atomic_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True); temporary = path.with_suffix(path.suffix + ".tmp"); temporary.write_text(json.dumps(payload, indent=2), encoding="utf-8"); temporary.replace(path)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""): digest.update(chunk)
    return digest.hexdigest()


def seed_all(seed: int) -> None:
    random.seed(seed); np.random.seed(seed); torch.manual_seed(seed); torch.cuda.manual_seed_all(seed)
    torch.backends.cudnn.deterministic = True; torch.backends.cudnn.benchmark = False


def worker_seed(worker_id: int) -> None:
    seed = torch.initial_seed() % 2**32; np.random.seed(seed + worker_id); random.seed(seed + worker_id)


def flatten_batch(batch: dict[str, Any], device: torch.device) -> dict[str, Any]:
    result = {}
    for name in ("source", "target", "mask", "sdf", "edge_target", "reliability_target"):
        value = batch[name]; result[name] = value.reshape(-1, *value.shape[2:]).to(device, non_blocking=True)
    for name in ("width_scale_target", "identity", "midpoint", "polarity", "blur_sigma"):
        result[name] = batch[name].reshape(-1).to(device, non_blocking=True)
    result["roles"] = batch["role"]; result["families"] = batch["family"]
    return result


def warp_tensor(x: torch.Tensor, dx: torch.Tensor, dy: torch.Tensor) -> torch.Tensor:
    n, _c, h, w = x.shape; theta = torch.zeros((n, 2, 3), device=x.device, dtype=x.dtype); theta[:, 0, 0] = 1; theta[:, 1, 1] = 1; theta[:, 0, 2] = -2 * dx / max(w - 1, 1); theta[:, 1, 2] = -2 * dy / max(h - 1, 1)
    grid = F.affine_grid(theta, x.shape, align_corners=True); return F.grid_sample(x, grid, mode="bilinear", padding_mode="reflection", align_corners=True)


def translation_loss(model, source: torch.Tensor, base_output: torch.Tensor, step: int) -> torch.Tensor:
    generator = torch.Generator(device=source.device); generator.manual_seed(int(CONFIG["data"]["seed"]) + step * 17)
    dx = torch.empty(source.shape[0], device=source.device).uniform_(-0.9, 0.9, generator=generator); dy = torch.empty(source.shape[0], device=source.device).uniform_(-0.9, 0.9, generator=generator)
    shifted_source = warp_tensor(source, dx, dy); shifted_output = model(shifted_source); expected = warp_tensor(base_output.detach(), dx, dy); margin = 12
    return F.smooth_l1_loss(shifted_output[..., margin:-margin, margin:-margin], expected[..., margin:-margin, margin:-margin], beta=1.0 / 255.0)


def exposure_loss(model, source: torch.Tensor, base_output: torch.Tensor, midpoint: torch.Tensor, polarity: torch.Tensor, step: int) -> torch.Tensor:
    scales = [0.78, 0.90, 1.12, 1.24]; scale = float(scales[step % len(scales)]); source_scaled = torch.clamp(0.5 + scale * (source - 0.5), 0, 1); output_scaled = model(source_scaled)
    midpoint_scaled = torch.clamp(0.5 + scale * (midpoint - 0.5), 0, 1); base_probability = soft_probability(base_output.detach(), midpoint, polarity); scaled_probability = soft_probability(output_scaled, midpoint_scaled, polarity)
    return F.smooth_l1_loss(scaled_probability, base_probability, beta=0.01)


def tile_loss(model, source: torch.Tensor, full_output: torch.Tensor) -> torch.Tensor:
    # A 64-pixel core with the configured 96-pixel halo exactly fills a 256 patch.
    halo, core = int(CONFIG["model"]["minimum_halo_px"]), 64
    if source.shape[-1] < core + 2 * halo or source.shape[-2] < core + 2 * halo:
        return full_output.new_zeros(())
    top = (source.shape[-2] - core - 2 * halo) // 2; left = (source.shape[-1] - core - 2 * halo) // 2
    tile = source[..., top:top + core + 2 * halo, left:left + core + 2 * halo]
    tile_output = model(tile)[..., halo:halo + core, halo:halo + core]
    reference = full_output[..., top + halo:top + halo + core, left + halo:left + halo + core].detach()
    return F.smooth_l1_loss(tile_output, reference, beta=0.25 / 255.0)


def make_loader(dataset: R107Dataset, batch_size: int, workers: int, shuffle: bool, seed: int) -> DataLoader:
    generator = torch.Generator(); generator.manual_seed(seed)
    options = dict(dataset=dataset, batch_size=batch_size, shuffle=shuffle, num_workers=workers, pin_memory=True, drop_last=shuffle, worker_init_fn=worker_seed, generator=generator)
    if workers > 0: options.update(persistent_workers=True, prefetch_factor=2)
    return DataLoader(**options)


@torch.inference_mode()
def validate(model, device: torch.device, epoch: int, limit: int = 128) -> tuple[dict[str, float], list[np.ndarray]]:
    dataset = R107Dataset("validation", epoch=0, limit=limit); loader = make_loader(dataset, int(CONFIG["training"]["batch_size"]), 0, False, int(CONFIG["data"]["seed"]) + 99)
    totals: dict[str, float] = {}; count = 0; previews = []
    model.eval()
    for batch in loader:
        flat = flatten_batch(batch, device); details = model.forward_details(flat["source"]); components = loss_components(details, flat["source"], flat["target"], flat["mask"], flat["sdf"], flat["edge_target"], flat["reliability_target"], flat["width_scale_target"], flat["identity"], flat["midpoint"], flat["polarity"])
        for name, value in components.items(): totals[name] = totals.get(name, 0.0) + float(value.cpu())
        totals["width_scale_mean"] = totals.get("width_scale_mean", 0.0) + float(details.width_scale.mean().cpu()); totals["reliability_mean"] = totals.get("reliability_mean", 0.0) + float(details.reliability.mean().cpu()); count += 1
        if len(previews) < 8:
            for index in range(min(2, details.output.shape[0])):
                previews.append(np.stack([flat["source"][index, 0].cpu().numpy(), details.output[index, 0].cpu().numpy(), flat["target"][index, 0].cpu().numpy()]))
    return {name: value / max(count, 1) for name, value in totals.items()}, previews


def save_preview(path: Path, previews: list[np.ndarray]) -> None:
    if not previews: return
    tile = 192; canvas = np.zeros((len(previews) * tile, 3 * tile), dtype=np.uint8)
    for row, triplet in enumerate(previews):
        for column in range(3):
            image = cv2.resize(triplet[column], (tile, tile), interpolation=cv2.INTER_AREA); canvas[row * tile:(row + 1) * tile, column * tile:(column + 1) * tile] = np.round(np.clip(image, 0, 1) * 255).astype(np.uint8)
    path.parent.mkdir(parents=True, exist_ok=True); cv2.imencode(".png", canvas)[1].tofile(str(path))


def save_checkpoint(path: Path, model, optimizer, epoch: int, global_step: int, validation: dict[str, float], run_id: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True); torch.save({"model": model.state_dict(), "optimizer": optimizer.state_dict(), "epoch": epoch, "global_step": global_step, "validation": validation, "run_id": run_id, "config": CONFIG, "scratch": True}, path)


def append_jsonl(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, allow_nan=False) + "\n")


def require_finite(name: str, value: torch.Tensor, *, run_dir: Path, global_step: int, context: dict[str, Any]) -> None:
    if bool(torch.isfinite(value).all()):
        return
    payload = {"status": "nonfinite", "stage": name, "global_step": global_step, **context}
    atomic_json(run_dir / "nonfinite_failure.json", payload)
    raise FloatingPointError(f"Non-finite value at {name}, step {global_step}")


def require_details_finite(details: Any, *, run_dir: Path, global_step: int, context: dict[str, Any]) -> None:
    fields = {field: bool(torch.isfinite(getattr(details, field)).all()) for field in details.__dataclass_fields__}
    if all(fields.values()):
        return
    payload = {"status": "nonfinite", "stage": "model_forward", "global_step": global_step, "detail_fields": fields, **context}
    atomic_json(run_dir / "nonfinite_failure.json", payload)
    raise FloatingPointError(f"Non-finite model detail at step {global_step}: {fields}")


def require_parameters_finite(model: torch.nn.Module, *, run_dir: Path, global_step: int, context: dict[str, Any]) -> None:
    bad = [name for name, parameter in model.named_parameters() if not bool(torch.isfinite(parameter).all())]
    if not bad:
        return
    payload = {"status": "nonfinite", "stage": "model_parameters", "global_step": global_step, "bad_parameters": bad, **context}
    atomic_json(run_dir / "nonfinite_failure.json", payload)
    raise FloatingPointError(f"Non-finite model parameters at step {global_step}: {bad}")


def run(args: argparse.Namespace) -> int:
    if not torch.cuda.is_available(): raise RuntimeError("CUDA is required")
    package = ROOT / CONFIG["data"]["package_root"]; manifest_path = package / "manifest.json"
    if not manifest_path.exists(): raise FileNotFoundError("Run data/prepare_dataset.py first")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("status") != "complete" and not args.allow_partial_data: raise RuntimeError("Dataset manifest is not complete")
    if not bool(CONFIG["source_isolation"]["checkpoint_loading_allowed"]) and args.resume: raise RuntimeError("R107 is scratch-only; resume/checkpoint inheritance is disabled")
    run_id = args.run_id or f"r107_{time.strftime('%Y%m%d_%H%M%S')}"; run_dir = ROOT / "runs" / run_id; run_dir.mkdir(parents=True, exist_ok=False)
    lock = ROOT / "runs" / "active_run.lock"; lock.parent.mkdir(parents=True, exist_ok=True)
    try: descriptor = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY); os.write(descriptor, run_id.encode()); os.close(descriptor)
    except FileExistsError as error: raise RuntimeError(f"Another R107 run is active: {lock.read_text(encoding='utf-8')}") from error
    seed_all(int(CONFIG["data"]["seed"])); device = torch.device("cuda:0"); model = build_model().to(device); optimizer = torch.optim.AdamW(model.parameters(), lr=float(CONFIG["training"]["learning_rate"]), weight_decay=float(CONFIG["training"]["weight_decay"])); scaler = torch.amp.GradScaler("cuda", enabled=bool(args.amp))
    epochs = int(args.epochs); global_step = 0; history = []
    atomic_json(run_dir / "run_state.json", {"status": "running", "run_id": run_id, "device": torch.cuda.get_device_name(0), "parameters": count_parameters(model), "dataset_manifest_sha256": sha256(manifest_path), "config_sha256": sha256(ROOT / "config" / "experiment.json")})
    try:
        for epoch in range(1, epochs + 1):
            dataset = R107Dataset("train", epoch=epoch, limit=args.data_limit); loader = make_loader(dataset, int(args.batch_size), int(args.workers), True, int(CONFIG["data"]["seed"]) + epoch); model.train(); epoch_totals: dict[str, float] = {}; batches = 0
            learning_rate = float(CONFIG["training"]["minimum_learning_rate"]) + 0.5 * (float(CONFIG["training"]["learning_rate"]) - float(CONFIG["training"]["minimum_learning_rate"])) * (1.0 + math.cos(math.pi * (epoch - 1) / max(epochs - 1, 1)))
            for group in optimizer.param_groups: group["lr"] = learning_rate
            for batch in loader:
                global_step += 1; flat = flatten_batch(batch, device); optimizer.zero_grad(set_to_none=True)
                with torch.autocast(device_type="cuda", dtype=torch.float16, enabled=bool(args.amp)):
                    details = model.forward_details(flat["source"])
                    batch_context = {"epoch": epoch, "scene_indices": batch["scene_index"].tolist(), "roles": list(batch["role"]), "families": list(batch["family"]), "amp_scale": float(scaler.get_scale())}
                    require_details_finite(details, run_dir=run_dir, global_step=global_step, context=batch_context)
                    components = loss_components(details, flat["source"], flat["target"], flat["mask"], flat["sdf"], flat["edge_target"], flat["reliability_target"], flat["width_scale_target"], flat["identity"], flat["midpoint"], flat["polarity"])
                    frequency = CONFIG["training"]["auxiliary_frequency"]
                    components["translation"] = translation_loss(model, flat["source"], details.output, global_step) if global_step % int(frequency["translation_every_steps"]) == 0 else details.output.new_zeros(())
                    components["exposure"] = exposure_loss(model, flat["source"], details.output, flat["midpoint"], flat["polarity"], global_step) if global_step % int(frequency["exposure_every_steps"]) == 0 else details.output.new_zeros(())
                    components["tile"] = tile_loss(model, flat["source"], details.output) if global_step % int(frequency["tile_every_steps"]) == 0 else details.output.new_zeros(())
                    total = combine(components, CONFIG["training"]["loss_weights"])
                component_snapshot = {name: float(value.detach().float().cpu()) for name, value in components.items()}
                require_finite("loss_total", total, run_dir=run_dir, global_step=global_step, context={"epoch": epoch, "components": component_snapshot, "amp_scale": float(scaler.get_scale())})
                scaler.scale(total).backward(); scaler.unscale_(optimizer)
                gradient_norm = torch.nn.utils.clip_grad_norm_(model.parameters(), float(CONFIG["training"]["gradient_clip"]), error_if_nonfinite=False)
                require_finite("gradient_norm", gradient_norm, run_dir=run_dir, global_step=global_step, context={"epoch": epoch, "components": component_snapshot, "amp_scale": float(scaler.get_scale())})
                scaler.step(optimizer); scaler.update(); require_parameters_finite(model, run_dir=run_dir, global_step=global_step, context=batch_context)
                if global_step % 100 == 0 or global_step == 1:
                    progress = {"epoch": epoch, "global_step": global_step, "learning_rate": learning_rate, "total": float(total.detach().float().cpu()), "gradient_norm": float(gradient_norm.detach().float().cpu()), "amp_scale": float(scaler.get_scale()), **component_snapshot}
                    append_jsonl(run_dir / "step_log.jsonl", progress); print(json.dumps({"step_progress": progress}), flush=True)
                batches += 1
                epoch_totals["total"] = epoch_totals.get("total", 0.0) + float(total.detach().cpu())
                for name, value in components.items(): epoch_totals[name] = epoch_totals.get(name, 0.0) + float(value.detach().cpu())
                if args.smoke_steps and global_step >= args.smoke_steps: break
            validation, previews = validate(model, device, epoch, limit=args.validation_limit)
            row = {"epoch": epoch, "global_step": global_step, "learning_rate": learning_rate, **{f"train_{name}": value / max(batches, 1) for name, value in epoch_totals.items()}, **{f"validation_{name}": value for name, value in validation.items()}}
            history.append(row); atomic_json(run_dir / "training_history.json", history); print(json.dumps(row), flush=True)
            if epoch % int(CONFIG["training"]["preview_every_epochs"]) == 0 or args.smoke_steps: save_preview(run_dir / "previews" / f"epoch_{epoch:03d}.png", previews)
            if epoch % int(CONFIG["training"]["save_every_epochs"]) == 0 or epoch == epochs or args.smoke_steps: save_checkpoint(run_dir / "weights" / f"epoch_{epoch:03d}.pth", model, optimizer, epoch, global_step, validation, run_id)
            if args.smoke_steps and global_step >= args.smoke_steps: break
        atomic_json(run_dir / "run_state.json", {"status": "complete", "run_id": run_id, "epochs_completed": history[-1]["epoch"], "global_step": global_step, "scratch": True, "formal": not bool(args.smoke_steps)})
    except BaseException as error:
        atomic_json(run_dir / "failure.json", {"status": "failed", "run_id": run_id, "error": repr(error), "error_type": type(error).__name__, "global_step": global_step}); atomic_json(run_dir / "run_state.json", {"status": "failed", "run_id": run_id, "global_step": global_step, "error_type": type(error).__name__}); raise
    finally:
        if lock.exists() and lock.read_text(encoding="utf-8") == run_id: lock.unlink()
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(); parser.add_argument("--run-id", default=""); parser.add_argument("--epochs", type=int, default=int(CONFIG["training"]["epochs"])); parser.add_argument("--batch-size", type=int, default=int(CONFIG["training"]["batch_size"])); parser.add_argument("--workers", type=int, default=int(CONFIG["training"]["workers"])); parser.add_argument("--amp", action=argparse.BooleanOptionalAction, default=bool(CONFIG["training"]["amp"])); parser.add_argument("--smoke-steps", type=int, default=0); parser.add_argument("--data-limit", type=int, default=0); parser.add_argument("--validation-limit", type=int, default=128); parser.add_argument("--allow-partial-data", action="store_true"); parser.add_argument("--resume", default=""); return run(parser.parse_args())


if __name__ == "__main__": raise SystemExit(main())

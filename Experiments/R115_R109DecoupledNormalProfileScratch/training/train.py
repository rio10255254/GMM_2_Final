"""Single formal scratch trainer for R115."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from pathlib import Path
import random
import time

import cv2
import numpy as np
import torch
import torch.nn.functional as F
from torch.utils.data import DataLoader, Sampler


ROOT = Path(__file__).resolve().parents[1]
import sys
sys.path.insert(0, str(ROOT))

from inference.tiled import forward_tiled
from model.r115_model import build_model, count_parameters
from training.losses import (
    combine_renderer,
    detector_components,
    profile_evidence_components,
    profile_objective,
    renderer_components,
)
from training.r115_dataset import R115Dataset


CONFIG = json.loads((ROOT / "config" / "experiment.json").read_text(encoding="utf-8"))
TRAIN = CONFIG["training"]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def atomic_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(path)


def seed_everything(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)


class FormalBatchSampler(Sampler[list[int]]):
    def __init__(self, dataset: R115Dataset, epoch: int):
        schedule = [
            json.loads(line)
            for line in (ROOT / "data" / "formal_train_bs12.jsonl").read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        lookup = {row["record_id"]: index for index, row in enumerate(dataset.records)}
        self.batches = [[lookup[record_id] for record_id in row["record_ids"]] for row in schedule]
        rng = random.Random(int(CONFIG["seed"]) + int(epoch) * 7919)
        rng.shuffle(self.batches)
        for batch in self.batches:
            rng.shuffle(batch)

    def __iter__(self):
        return iter(self.batches)

    def __len__(self) -> int:
        return len(self.batches)


def flatten(batch: dict, device: torch.device) -> dict[str, torch.Tensor]:
    result = {}
    for name in ("source", "target", "mask", "sdf", "edge"):
        value = batch[name]
        result[name] = value.reshape(-1, *value.shape[2:]).to(device, non_blocking=True)
    for name in ("identity", "midpoint", "polarity", "width_gain_target"):
        result[name] = batch[name].reshape(-1).to(device, non_blocking=True)
    return result


def slice_scenes(batch: dict, start: int, end: int) -> dict:
    result = {}
    for name, value in batch.items():
        result[name] = value[start:end] if isinstance(value, torch.Tensor) else value[start:end]
    return result


def warp(value: torch.Tensor, dx: torch.Tensor, dy: torch.Tensor) -> torch.Tensor:
    flow = torch.stack([dx, dy], dim=1)[:, :, None, None].expand(-1, -1, *value.shape[-2:])
    return build_model().warp(value, flow)


def translation_loss(model, source: torch.Tensor, base: torch.Tensor, step: int) -> torch.Tensor:
    generator = torch.Generator(device=source.device).manual_seed(int(CONFIG["seed"]) + step * 17)
    dx = torch.empty(source.shape[0], device=source.device).uniform_(-0.9, 0.9, generator=generator)
    dy = torch.empty(source.shape[0], device=source.device).uniform_(-0.9, 0.9, generator=generator)
    flow = torch.stack([dx, dy], dim=1)[:, :, None, None].expand(-1, -1, *source.shape[-2:])
    shifted_source = model.warp(source, flow)
    shifted_output = model(shifted_source)
    expected = model.warp(base.detach(), flow)
    margin = 16
    return F.smooth_l1_loss(
        shifted_output[..., margin:-margin, margin:-margin],
        expected[..., margin:-margin, margin:-margin],
        beta=0.25 / 255,
    )


def exposure_loss(model, source: torch.Tensor, base: torch.Tensor, step: int) -> torch.Tensor:
    scale = (0.78, 0.90, 1.12, 1.24)[step % 4]
    scaled = torch.clamp(0.5 + scale * (source - 0.5), 0, 1)
    prediction = model(scaled)
    expected = torch.clamp(0.5 + scale * (base.detach() - 0.5), 0, 1)
    return F.smooth_l1_loss(prediction, expected, beta=0.5 / 255)


def set_active(model, active: str) -> list[torch.nn.Parameter]:
    groups = {
        "detector": model.detector_parameters(),
        "geometry": model.geometry_parameters(),
        "profile": model.profile_parameters(),
    }
    for name, parameters in groups.items():
        for parameter in parameters:
            parameter.requires_grad_(name == active)
    return groups[active]


def stage_for_epoch(epoch: int) -> str:
    if epoch <= int(TRAIN["detector_epochs"]):
        return "detector"
    if epoch <= int(TRAIN["geometry_end_epoch"]):
        return "geometry"
    if epoch <= int(TRAIN["profile_evidence_end_epoch"]):
        return "profile"
    return "joint"


def learning_rate(stage: str, epoch: int) -> float:
    bounds = {
        "detector": (1, int(TRAIN["detector_epochs"]), float(TRAIN["detector_learning_rate"])),
        "geometry": (
            int(TRAIN["detector_epochs"]) + 1,
            int(TRAIN["geometry_end_epoch"]),
            float(TRAIN["geometry_learning_rate"]),
        ),
        "profile": (
            int(TRAIN["geometry_end_epoch"]) + 1,
            int(TRAIN["profile_evidence_end_epoch"]),
            float(TRAIN["profile_learning_rate"]),
        ),
        "joint": (
            int(TRAIN["profile_evidence_end_epoch"]) + 1,
            int(TRAIN["epochs"]),
            float(TRAIN["joint_learning_rate"]),
        ),
    }
    start, end, maximum = bounds[stage]
    position = (epoch - start) / max(end - start, 1)
    minimum = float(TRAIN["minimum_learning_rate"])
    return minimum + 0.5 * (maximum - minimum) * (1 + math.cos(math.pi * position))


def microbatch_objective(model, batch: dict, stage: str, global_step: int):
    details = model.forward_details(batch["source"])
    if stage == "detector":
        components = detector_components(details, batch["edge"])
        total = 0.55 * components["boundary_bce"] + 0.45 * components["boundary_dice"]
    elif stage == "geometry":
        components = renderer_components(
            details, batch["source"], batch["target"], batch["mask"], batch["edge"],
            batch["identity"], batch["midpoint"], batch["polarity"], batch["width_gain_target"],
        )
        total = combine_renderer(components)
        if global_step % 8 == 0:
            components["translation"] = translation_loss(model, batch["source"], details.output, global_step)
            total = total + 0.12 * components["translation"]
        if global_step % 8 == 4:
            components["exposure"] = exposure_loss(model, batch["source"], details.output, global_step)
            total = total + 0.10 * components["exposure"]
    elif stage == "profile":
        components, _shift, _width = profile_evidence_components(
            details, batch["source"], batch["target"], batch["sdf"], batch["identity"]
        )
        total = profile_objective(components)
    else:
        raise ValueError(stage)
    return total, components, details


@torch.no_grad()
def validate(model, device: torch.device, full: bool = False) -> tuple[dict, list[np.ndarray]]:
    dataset = R115Dataset("validation", epoch=0, arm="B")
    populations = json.loads((ROOT / "data" / "validation_populations.json").read_text(encoding="utf-8"))
    if not full:
        wanted = set(populations["common_record_ids"][:88] + populations["supplemental_record_ids"])
        dataset.records = [row for row in dataset.records if row["record_id"] in wanted]
    loader = DataLoader(dataset, batch_size=8, shuffle=False, num_workers=0)
    supplemental = set(populations["supplemental_record_ids"])
    totals = {name: 0.0 for name in (
        "common_count", "supplemental_count", "common_base", "common_final",
        "supplemental_base", "supplemental_final", "clear_delta",
        "shift_factor", "width_factor", "batches",
    )}
    previews = []
    model.eval()
    for raw_batch in loader:
        batch = flatten(raw_batch, device)
        details = model.forward_details(batch["source"])
        scene_count = len(raw_batch["record_id"])
        final_error = (details.output - batch["target"]).abs().flatten(1).mean(1).reshape(scene_count, 2)
        base_error = (details.baseline_output - batch["target"]).abs().flatten(1).mean(1).reshape(scene_count, 2)
        clear = (details.output - details.baseline_output).abs().flatten(1).mean(1).reshape(scene_count, 2)[:, 1]
        for index, record_id in enumerate(raw_batch["record_id"]):
            prefix = "supplemental" if record_id in supplemental else "common"
            totals[f"{prefix}_count"] += 1
            totals[f"{prefix}_base"] += float(base_error[index, 0].cpu()) * 255
            totals[f"{prefix}_final"] += float(final_error[index, 0].cpu()) * 255
            if len(previews) < 4:
                previews.append(np.stack([
                    batch["source"].reshape(scene_count, 2, 1, 256, 256)[index, 0, 0].cpu().numpy(),
                    details.output.reshape(scene_count, 2, 1, 256, 256)[index, 0, 0].cpu().numpy(),
                    batch["target"].reshape(scene_count, 2, 1, 256, 256)[index, 0, 0].cpu().numpy(),
                ]))
        totals["clear_delta"] += float(clear.sum().cpu()) * 255
        totals["shift_factor"] += float(details.shift_factor.mean().cpu())
        totals["width_factor"] += float(details.width_factor.mean().cpu())
        totals["batches"] += 1
    result = {}
    for prefix in ("common", "supplemental"):
        count = max(totals[f"{prefix}_count"], 1)
        base = totals[f"{prefix}_base"] / count
        final = totals[f"{prefix}_final"] / count
        result[f"{prefix}_scenes"] = totals[f"{prefix}_count"]
        result[f"{prefix}_base_mae_gray"] = base
        result[f"{prefix}_final_mae_gray"] = final
        result[f"{prefix}_gain_gray"] = base - final
    result["clear_delta_gray"] = totals["clear_delta"] / max(totals["common_count"] + totals["supplemental_count"], 1)
    result["shift_factor_mean"] = totals["shift_factor"] / max(totals["batches"], 1)
    result["width_factor_mean"] = totals["width_factor"] / max(totals["batches"], 1)
    return result, previews


def save_preview(path: Path, previews: list[np.ndarray]) -> None:
    tile = 192
    canvas = np.zeros((len(previews) * tile, 3 * tile), np.uint8)
    for row, triplet in enumerate(previews):
        for column, image in enumerate(triplet):
            resized = cv2.resize(image, (tile, tile), interpolation=cv2.INTER_AREA)
            canvas[row * tile:(row + 1) * tile, column * tile:(column + 1) * tile] = np.round(np.clip(resized, 0, 1) * 255).astype(np.uint8)
    path.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(path), canvas)


def run(args: argparse.Namespace) -> Path:
    if args.resume or args.checkpoint or args.initial_weights:
        raise RuntimeError("R115 formal training is scratch-only")
    if not args.authorize_formal and not args.smoke_steps:
        raise RuntimeError("formal training requires --authorize-formal")
    if not args.smoke_steps:
        authorization = json.loads(
            (ROOT / "formal_authorization.json").read_text(encoding="utf-8")
        )
        if authorization.get("authorized") is not True:
            raise RuntimeError(
                "R115 formal training is evidence-blocked: "
                + str(authorization.get("reason", "authorization is false"))
            )
    seed_everything(int(CONFIG["seed"]))
    device = torch.device(args.device)
    model = build_model().to(device)
    groups = {
        "detector": model.detector_parameters(),
        "geometry": model.geometry_parameters(),
        "profile": model.profile_parameters(),
    }
    optimizers = {
        name: torch.optim.AdamW(parameters, lr=1.0e-4, weight_decay=float(TRAIN["weight_decay"]))
        for name, parameters in groups.items()
    }
    run_id = args.run_id or f"r115_formal_scratch_{time.strftime('%Y%m%d_%H%M%S')}"
    run_root = ROOT / "runs" / run_id
    if run_root.exists():
        raise FileExistsError(run_root)
    for folder in ("weights", "previews", "validation"):
        (run_root / folder).mkdir(parents=True, exist_ok=True)
    state = {
        "status": "running",
        "run_id": run_id,
        "formal": not bool(args.smoke_steps),
        "scratch": True,
        "device": torch.cuda.get_device_name(device) if device.type == "cuda" else str(device),
        "parameters": count_parameters(model),
        "config_sha256": sha256(ROOT / "config" / "experiment.json"),
        "dataset_sha256": sha256(ROOT / "data" / "package" / "manifest.json"),
        "started_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }
    atomic_json(run_root / "run_state.json", state)
    history = []
    global_step = 0
    started = time.perf_counter()
    epochs = 4 if args.smoke_steps else int(TRAIN["epochs"])
    for epoch in range(1, epochs + 1):
        stage = ("detector", "geometry", "profile", "joint")[epoch - 1] if args.smoke_steps else stage_for_epoch(epoch)
        data_arm = "A_FULL"
        dataset = R115Dataset("train", epoch=epoch, arm=data_arm, limit=args.data_limit)
        generator = torch.Generator().manual_seed(int(CONFIG["seed"]) + epoch)
        loader = DataLoader(
            dataset,
            batch_size=args.batch_size,
            shuffle=True,
            num_workers=args.workers,
            pin_memory=True,
            drop_last=True,
            generator=generator,
        )
        epoch_totals: dict[str, float] = {}
        component_counts: dict[str, int] = {}
        logical_batches = 0
        epoch_started = time.perf_counter()
        torch.cuda.reset_peak_memory_stats(device)
        for batch_index, raw_batch in enumerate(loader, start=1):
            global_step += 1
            active = stage
            if stage == "joint":
                active = "geometry" if batch_index % 2 else "profile"
            parameters = set_active(model, active)
            optimizer = optimizers[active]
            lr = learning_rate(stage, epoch)
            for group in optimizer.param_groups:
                group["lr"] = lr
            optimizer.zero_grad(set_to_none=True)
            scene_count = int(raw_batch["source"].shape[0])
            micro = min(int(TRAIN["microbatch_size"]), scene_count)
            components_sum: dict[str, float] = {}
            loss_sum = 0.0
            for start in range(0, scene_count, micro):
                end = min(scene_count, start + micro)
                batch = flatten(slice_scenes(raw_batch, start, end), device)
                total, components, _details = microbatch_objective(
                    model, batch, active, global_step
                )
                weight = (end - start) / scene_count
                (total * weight).backward()
                loss_sum += float(total.detach().cpu()) * weight
                for name, value in components.items():
                    components_sum[name] = components_sum.get(name, 0.0) + float(value.detach().cpu()) * weight
            norm = torch.nn.utils.clip_grad_norm_(parameters, float(TRAIN["gradient_clip"]))
            if not bool(torch.isfinite(norm)):
                raise FloatingPointError("non-finite R115 gradient")
            optimizer.step()
            logical_batches += 1
            epoch_totals["loss"] = epoch_totals.get("loss", 0.0) + loss_sum
            for name, value in components_sum.items():
                epoch_totals[name] = epoch_totals.get(name, 0.0) + value
                component_counts[name] = component_counts.get(name, 0) + 1
            if batch_index % 25 == 0:
                print(json.dumps({
                    "progress": "running", "run_id": run_id, "epoch": epoch,
                    "epochs": epochs, "stage": stage, "active": active,
                    "batch": batch_index, "batches": len(loader), "loss": loss_sum,
                }), flush=True)
            if args.smoke_steps and logical_batches >= args.smoke_steps:
                break
        do_full = epoch == epochs
        validation, previews = validate(model, device, full=do_full)
        row = {
            "epoch": epoch,
            "stage": stage,
            "data_arm": data_arm,
            "global_step": global_step,
            "logical_batches": logical_batches,
            "duration_seconds": time.perf_counter() - epoch_started,
            "gpu_peak_allocated_gib": torch.cuda.max_memory_allocated(device) / 2**30,
            "gpu_peak_reserved_gib": torch.cuda.max_memory_reserved(device) / 2**30,
            **{
                f"train_{name}": value / max(
                    logical_batches if name == "loss" else component_counts.get(name, 1),
                    1,
                )
                for name, value in epoch_totals.items()
            },
            **{f"validation_{name}": value for name, value in validation.items()},
        }
        history.append(row)
        atomic_json(run_root / "training_history.json", history)
        print(json.dumps(row), flush=True)
        if epoch % int(TRAIN["preview_every_epochs"]) == 0 or args.smoke_steps:
            save_preview(run_root / "previews" / f"epoch_{epoch:03d}.png", previews)
        if epoch % int(TRAIN["validation_every_epochs"]) == 0 or epoch == epochs:
            atomic_json(run_root / "validation" / f"epoch_{epoch:03d}.json", validation)
        if epoch % int(TRAIN["save_every_epochs"]) == 0 or epoch == epochs or args.smoke_steps:
            torch.save({
                "model": model.state_dict(), "epoch": epoch, "stage": stage,
                "global_step": global_step, "run_id": run_id, "scratch": True,
                "formal": not bool(args.smoke_steps), "validation": validation,
                "config": CONFIG,
            }, run_root / "weights" / f"epoch_{epoch:03d}.pth")
    state.update({
        "status": "complete",
        "epochs_completed": epochs,
        "global_step": global_step,
        "elapsed_seconds": time.perf_counter() - started,
    })
    atomic_json(run_root / "run_state.json", state)
    with (run_root / "training_log.csv").open("w", newline="", encoding="utf-8") as stream:
        fieldnames = []
        for row in history:
            for name in row:
                if name not in fieldnames:
                    fieldnames.append(name)
        writer = csv.DictWriter(stream, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(history)
    return run_root


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", default="")
    parser.add_argument("--device", default="cuda")
    parser.add_argument("--batch-size", type=int, default=int(TRAIN["batch_size"]))
    parser.add_argument("--workers", type=int, default=int(TRAIN["workers"]))
    parser.add_argument("--data-limit", type=int, default=0)
    parser.add_argument("--smoke-steps", type=int, default=0)
    parser.add_argument("--authorize-formal", action="store_true")
    parser.add_argument("--resume", default="")
    parser.add_argument("--checkpoint", default="")
    parser.add_argument("--initial-weights", default="")
    return parser.parse_args()


if __name__ == "__main__":
    print(run(parse_args()))

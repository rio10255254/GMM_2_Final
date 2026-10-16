"""Matched scratch training entrypoint. Formal mode needs explicit confirmation."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import random
import sys
import time
from collections import defaultdict
from pathlib import Path

import cv2
import numpy as np
os.environ.setdefault("CUBLAS_WORKSPACE_CONFIG", ":4096:8")
import torch
import torch.nn.functional as F
from scipy.ndimage import distance_transform_edt
from scipy.stats import spearmanr
from torch.utils.data import DataLoader


ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "config" / "experiment.json"
CONFIG = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
sys.path.insert(0, str(ROOT / "model")); sys.path.insert(0, str(ROOT / "training"))
from model import build_model, count_parameters
from dataset import ProbeDataset
from losses import combine, detector_components, renderer_components
from supervision import (build_supervision_target, build_supervision_targets, carrier_supervision_loss,
                         detail_supervision_loss, renderer_epoch_weight, supervision_statistics)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def state_hash(model) -> str:
    digest = hashlib.sha256()
    for name, tensor in sorted(model.state_dict().items()):
        digest.update(name.encode("utf-8")); digest.update(tensor.detach().cpu().contiguous().numpy().tobytes())
    return digest.hexdigest()


def atomic_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False), encoding="utf-8")
    temporary.replace(path)


def seed_all(seed: int) -> None:
    random.seed(seed); np.random.seed(seed); torch.manual_seed(seed); torch.cuda.manual_seed_all(seed)
    torch.backends.cudnn.benchmark = False; torch.backends.cudnn.deterministic = True
    torch.backends.cuda.matmul.allow_tf32 = False; torch.backends.cudnn.allow_tf32 = False
    torch.use_deterministic_algorithms(True, warn_only=True)


def worker_seed(worker_id: int) -> None:
    seed = torch.initial_seed() % 2 ** 32
    np.random.seed(seed + worker_id); random.seed(seed + worker_id)


def loader(dataset, batch: int, workers: int, shuffle: bool, seed: int):
    generator = torch.Generator(); generator.manual_seed(seed)
    options = dict(dataset=dataset, batch_size=batch, shuffle=shuffle, num_workers=workers,
                   pin_memory=True, drop_last=shuffle, worker_init_fn=worker_seed, generator=generator)
    if workers > 0:
        options.update(persistent_workers=True, prefetch_factor=2)
    return DataLoader(**options)


def flatten(batch, device):
    result = {}
    for name in ("source", "target", "mask", "sdf", "edge"):
        result[name] = batch[name].reshape(-1, *batch[name].shape[2:]).to(device, non_blocking=True)
    for name in ("identity", "midpoint", "polarity", "width_gain_target"):
        result[name] = batch[name].reshape(-1).to(device, non_blocking=True)
    return result


def finite(name: str, value: torch.Tensor) -> None:
    if not bool(torch.isfinite(value).all()):
        raise FloatingPointError(name)


def warp(value, dx, dy):
    n, _, h, w = value.shape
    theta = torch.zeros((n, 2, 3), device=value.device, dtype=value.dtype)
    theta[:, 0, 0] = 1; theta[:, 1, 1] = 1
    theta[:, 0, 2] = -2 * dx / max(w - 1, 1); theta[:, 1, 2] = -2 * dy / max(h - 1, 1)
    grid = F.affine_grid(theta, value.shape, align_corners=True)
    return F.grid_sample(value, grid, mode="bilinear", padding_mode="reflection", align_corners=True)


def translation_loss(model, source, base, step):
    generator = torch.Generator(device=source.device).manual_seed(int(CONFIG["seed"]) + step * 17)
    dx = torch.empty(source.shape[0], device=source.device).uniform_(-.9, .9, generator=generator)
    dy = torch.empty(source.shape[0], device=source.device).uniform_(-.9, .9, generator=generator)
    shifted = model(warp(source, dx, dy)); expected = warp(base.detach(), dx, dy); margin = 16
    return F.smooth_l1_loss(shifted[..., margin:-margin, margin:-margin],
                            expected[..., margin:-margin, margin:-margin], beta=.25 / 255)


def exposure_loss(model, source, base, step):
    scale = (.78, .90, 1.12, 1.24)[step % 4]
    scaled = torch.clamp(.5 + scale * (source - .5), 0, 1)
    prediction = model(scaled); expected = torch.clamp(.5 + scale * (base.detach() - .5), 0, 1)
    return F.smooth_l1_loss(prediction, expected, beta=.5 / 255)


def tile_loss(model, source, full):
    halo, core = 96, 64
    if min(source.shape[-2:]) < core + 2 * halo:
        return full.new_zeros(())
    top = (source.shape[-2] - core - 2 * halo) // 2
    left = (source.shape[-1] - core - 2 * halo) // 2
    tile = source[..., top:top + core + 2 * halo, left:left + core + 2 * halo]
    value = model(tile)[..., halo:halo + core, halo:halo + core]
    reference = full[..., top + halo:top + halo + core, left + halo:left + halo + core].detach()
    return F.smooth_l1_loss(value, reference, beta=.25 / 255)


def save_preview(path: Path, rows: list[np.ndarray]) -> None:
    if not rows:
        return
    tile = 160; canvas = np.zeros((len(rows) * tile, 3 * tile), np.uint8)
    for row_index, triplet in enumerate(rows):
        for column, image in enumerate(triplet):
            resized = cv2.resize(image, (tile, tile), interpolation=cv2.INTER_AREA)
            canvas[row_index * tile:(row_index + 1) * tile, column * tile:(column + 1) * tile] = np.rint(
                np.clip(resized, 0, 1) * 255).astype(np.uint8)
    path.parent.mkdir(parents=True, exist_ok=True); cv2.imencode(".png", canvas)[1].tofile(str(path))


@torch.inference_mode()
def validate_internal(model, device, limit: int, batch_size: int):
    dataset = ProbeDataset("validation", epoch=0, limit=limit)
    totals = defaultdict(float); count = 0; previews = []
    model.eval()
    for batch_data in loader(dataset, batch_size, 0, False, int(CONFIG["seed"]) + 99):
        batch = flatten(batch_data, device); details = model.forward_details(batch["source"])
        components = renderer_components(details, batch["source"], batch["target"], batch["mask"], batch["edge"],
                                         batch["identity"], batch["midpoint"], batch["polarity"], batch["width_gain_target"])
        target_detail = build_supervision_target(model, details, batch["target"], batch["identity"])
        supervision = supervision_statistics(details, target_detail)
        for name, value in components.items(): totals[name] += float(value.cpu())
        for name, value in supervision.items(): totals[name] += value
        totals["detail_abs_mean_gray"] += float(details.detail.abs().mean().cpu()) * 255
        totals["detail_local_mean_gray"] += float(F.avg_pool2d(details.detail, 9, 1, 4).abs().mean().cpu()) * 255
        totals["width_gain_mean"] += float(details.width_gain.mean().cpu())
        totals["normal_shift_abs_mean"] += float(details.normal_shift.abs().mean().cpu())
        count += 1
        if len(previews) < 6:
            for index in range(min(2, len(details.output))):
                previews.append(np.stack([batch["source"][index, 0].cpu().numpy(),
                                          details.output[index, 0].cpu().numpy(),
                                          batch["target"][index, 0].cpu().numpy()]))
    return {name: value / max(count, 1) for name, value in totals.items()}, previews


def binary_boundary(mask: np.ndarray) -> np.ndarray:
    return cv2.morphologyEx(mask.astype(np.uint8), cv2.MORPH_GRADIENT, np.ones((3, 3), np.uint8)).astype(bool)


def contour_distance(first: np.ndarray, second: np.ndarray) -> tuple[float, float]:
    a = binary_boundary(first); b = binary_boundary(second)
    if not a.any() or not b.any(): return 1e3, 1e3
    da = distance_transform_edt(~a); db = distance_transform_edt(~b)
    values = np.concatenate([db[a], da[b]])
    return .5 * (float(db[a].mean()) + float(da[b].mean())), float(np.percentile(values, 95))


def mask_iou(first, second):
    return float(np.logical_and(first, second).sum() / max(np.logical_or(first, second).sum(), 1))


@torch.inference_mode()
def evaluate_locked_challenge(model, device, run_dir: Path, batch_size: int):
    arrays_path = (ROOT / CONFIG["locked_challenge"]["arrays"]).resolve()
    manifest_path = (ROOT / CONFIG["locked_challenge"]["manifest"]).resolve()
    arrays = np.load(arrays_path)
    with manifest_path.open("r", newline="", encoding="utf-8-sig") as handle:
        metadata = list(csv.DictReader(handle))
    raw, target, masks = arrays["raw"], arrays["target"], arrays["mask"]
    if len(raw) != int(CONFIG["locked_challenge"]["expected_scenes"]): raise RuntimeError("Locked challenge count changed")
    outputs, details_abs, detail_dc, target_abs, supervision_mae = [], [], [], [], []
    model.eval()
    for start in range(0, len(raw), batch_size):
        source = torch.from_numpy(raw[start:start + batch_size, None]).to(device)
        truth = torch.from_numpy(target[start:start + batch_size, None]).to(device)
        details = model.forward_details(source)
        identity = torch.zeros(len(source), dtype=torch.bool, device=device)
        target_detail = build_supervision_target(model, details, truth, identity)
        outputs.extend(details.output[:, 0].cpu().numpy())
        details_abs.extend((details.detail.abs().mean((1, 2, 3)) * 255).cpu().numpy())
        detail_dc.extend((F.avg_pool2d(details.detail, 9, 1, 4).abs().mean((1, 2, 3)) * 255).cpu().numpy())
        target_abs.extend((target_detail.abs().mean((1, 2, 3)) * 255).cpu().numpy())
        supervision_mae.extend(((details.detail - target_detail).abs().mean((1, 2, 3)) * 255).cpu().numpy())
    outputs = np.asarray(outputs, np.float32)
    rows = []
    predicted_masks = []
    for index, meta in enumerate(metadata):
        polarity = int(meta["polarity"]); truth = masks[index] >= .5
        prediction = polarity * (outputs[index] - .5) >= 0; predicted_masks.append(prediction)
        assd, hd95 = contour_distance(prediction, truth); iou = mask_iou(prediction, truth)
        band = distance_transform_edt(~binary_boundary(truth)) <= 4
        boundary_mae = float(np.mean(np.abs(outputs[index][band] - target[index][band])) * 255)
        output_hp = outputs[index] - cv2.GaussianBlur(outputs[index], (0, 0), 2)
        target_hp = target[index] - cv2.GaussianBlur(target[index], (0, 0), 2)
        rows.append({
            "scene_id": meta["scene_id"], "latent_shape_id": meta["latent_shape_id"],
            "shape": meta["shape"], "degradation": meta["degradation"], "polarity": polarity,
            "assd_px": assd, "hd95_px": hd95, "iou": iou, "boundary_mae_gray": boundary_mae,
            "high_frequency_rmse_gray": float(np.sqrt(np.mean((output_hp - target_hp) ** 2)) * 255),
            "detail_abs_mean_gray": float(details_abs[index]), "detail_local_mean_gray": float(detail_dc[index]),
            "detail_target_abs_mean_gray": float(target_abs[index]),
            "detail_supervision_mae_gray": float(supervision_mae[index]),
        })
    with (run_dir / "locked_challenge_metrics.csv").open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0])); writer.writeheader(); writer.writerows(rows)

    by_latent = defaultdict(list)
    for index, row in enumerate(rows): by_latent[row["latent_shape_id"]].append(index)
    within_assd, within_iou_distance = [], []
    for indices in by_latent.values():
        for position, first in enumerate(indices):
            for second in indices[position + 1:]:
                within_assd.append(contour_distance(predicted_masks[first], predicted_masks[second])[0])
                within_iou_distance.append(1 - mask_iou(predicted_masks[first], predicted_masks[second]))
    latent_names = sorted(by_latent)
    truth_consensus = {name: np.mean(np.stack([masks[i] >= .5 for i in by_latent[name]]), 0) >= .5 for name in latent_names}
    pred_consensus = {name: np.mean(np.stack([predicted_masks[i] for i in by_latent[name]]), 0) >= .5 for name in latent_names}
    truth_distances, pred_distances = [], []
    for index, first in enumerate(latent_names):
        for second in latent_names[index + 1:]:
            truth_distances.append(1 - mask_iou(truth_consensus[first], truth_consensus[second]))
            pred_distances.append(1 - mask_iou(pred_consensus[first], pred_consensus[second]))
    summary = {
        "scene_count": len(rows), "assd_median_px": float(np.median([r["assd_px"] for r in rows])),
        "assd_p95_px": float(np.percentile([r["assd_px"] for r in rows], 95)),
        "assd_worst_px": float(max(r["assd_px"] for r in rows)),
        "iou_mean": float(np.mean([r["iou"] for r in rows])), "iou_worst": float(min(r["iou"] for r in rows)),
        "boundary_mae_mean_gray": float(np.mean([r["boundary_mae_gray"] for r in rows])),
        "high_frequency_rmse_mean_gray": float(np.mean([r["high_frequency_rmse_gray"] for r in rows])),
        "same_shape_condition_assd_mean_px": float(np.mean(within_assd)),
        "same_shape_condition_iou_distance_mean": float(np.mean(within_iou_distance)),
        "shape_retention_ratio": float(np.mean(pred_distances) / max(np.mean(truth_distances), 1e-8)),
        "shape_distance_spearman": float(spearmanr(truth_distances, pred_distances).statistic),
        "detail_abs_mean_gray": float(np.mean(details_abs)), "detail_local_mean_gray": float(np.mean(detail_dc)),
        "detail_target_abs_mean_gray": float(np.mean(target_abs)),
        "detail_supervision_mae_gray": float(np.mean(supervision_mae)),
        "detail_target_utilization_ratio": float(np.mean(details_abs) / max(np.mean(target_abs), 1e-8)),
        "worst_scene_id": max(rows, key=lambda row: row["assd_px"])["scene_id"],
    }
    atomic_json(run_dir / "locked_challenge_summary.json", summary)
    return summary


def train_arm(arm: str, mode: str, options: dict, run_id: str) -> Path:
    seed_all(int(CONFIG["seed"])); device = torch.device("cuda:0")
    free_start, total = torch.cuda.mem_get_info(device)
    minimum_free = float(CONFIG["training"]["minimum_gpu_free_before_start_gib"])
    if free_start / 2 ** 30 < minimum_free:
        raise RuntimeError(f"Only {free_start / 2 ** 30:.2f} GiB GPU memory free; need {minimum_free:.2f} GiB")
    run_dir = ROOT / "runs" / run_id
    run_dir.mkdir(parents=True, exist_ok=False)
    model = build_model(arm).to(device); initial_hash = state_hash(model)
    detector_parameters = model.detector_parameters(); renderer_parameters = model.renderer_parameters()
    detector_optimizer = torch.optim.AdamW(detector_parameters, lr=float(CONFIG["training"]["detector_learning_rate"]),
                                            weight_decay=float(CONFIG["training"]["weight_decay"]))
    renderer_optimizer = torch.optim.AdamW(renderer_parameters, lr=float(CONFIG["training"]["renderer_learning_rate"]),
                                            weight_decay=float(CONFIG["training"]["weight_decay"]))
    history = []; global_step = 0; started = time.perf_counter(); detector_hash = None
    torch.cuda.reset_peak_memory_stats(device)
    atomic_json(run_dir / "run_state.json", {
        "status": "running", "mode": mode, "arm": arm, "run_id": run_id, "scratch": True,
        "resume": False, "parameters": count_parameters(model), "initial_state_sha256": initial_hash,
        "selection_sha256": sha256_file(ROOT / CONFIG["data"]["selection_file"]),
        "config_sha256": sha256_file(CONFIG_PATH), "gpu_start_free_gib": free_start / 2 ** 30,
    })
    for epoch in range(1, options["epochs"] + 1):
        stage = "detector" if epoch <= options["detector_epochs"] else "renderer"
        model.train()
        for parameter in detector_parameters: parameter.requires_grad_(stage == "detector")
        for parameter in renderer_parameters: parameter.requires_grad_(stage == "renderer")
        optimizer = detector_optimizer if stage == "detector" else renderer_optimizer
        base_lr = float(CONFIG["training"]["detector_learning_rate"] if stage == "detector" else CONFIG["training"]["renderer_learning_rate"])
        stage_start = 1 if stage == "detector" else options["detector_epochs"] + 1
        stage_total = options["detector_epochs"] if stage == "detector" else options["epochs"] - options["detector_epochs"]
        stage_epoch = epoch - stage_start + 1; minimum_lr = float(CONFIG["training"]["minimum_learning_rate"])
        learning_rate = minimum_lr + .5 * (base_lr - minimum_lr) * (1 + math.cos(math.pi * (stage_epoch - 1) / max(stage_total - 1, 1)))
        for group in optimizer.param_groups: group["lr"] = learning_rate
        dataset = ProbeDataset("train", epoch=epoch, limit=options["data_limit"])
        totals = defaultdict(float); batches = 0; epoch_started = time.perf_counter()
        for batch_data in loader(dataset, options["batch_size"], options["workers"], True, int(CONFIG["seed"]) + epoch):
            global_step += 1; batch = flatten(batch_data, device); optimizer.zero_grad(set_to_none=True)
            details = model.forward_details(batch["source"])
            for name in details.__dataclass_fields__: finite(f"details.{name}", getattr(details, name))
            if stage == "detector":
                components = detector_components(details, batch["edge"])
                total_loss = .55 * components["boundary_bce"] + .45 * components["boundary_dice"]
            else:
                components = renderer_components(details, batch["source"], batch["target"], batch["mask"], batch["edge"],
                                                 batch["identity"], batch["midpoint"], batch["polarity"], batch["width_gain_target"])
                target_carrier, target_detail = build_supervision_targets(
                    model, details, batch["target"], batch["identity"])
                components["detail_supervision"] = detail_supervision_loss(details, target_detail)
                components["detail_carrier_supervision"] = carrier_supervision_loss(details, target_carrier)
                renderer_epoch = epoch - options["detector_epochs"]
                supervision_weight = renderer_epoch_weight(arm, renderer_epoch)
                frequency = CONFIG["training"]["auxiliary_frequency"]
                components["translation"] = translation_loss(model, batch["source"], details.output, global_step) if global_step % int(frequency["translation_every_steps"]) == 0 else details.output.new_zeros(())
                components["exposure"] = exposure_loss(model, batch["source"], details.output, global_step) if global_step % int(frequency["exposure_every_steps"]) == 0 else details.output.new_zeros(())
                components["tile"] = tile_loss(model, batch["source"], details.output) if global_step % int(frequency["tile_every_steps"]) == 0 else details.output.new_zeros(())
                carrier_weight = float(CONFIG["training"]["bounded_detail_supervision"]["carrier_auxiliary_weight"])
                total_loss = (combine(components, CONFIG["training"]["loss_weights"])
                              + supervision_weight * (components["detail_supervision"]
                                                       + carrier_weight * components["detail_carrier_supervision"]))
                components["detail_supervision_weight"] = details.output.new_tensor(supervision_weight)
                statistics = supervision_statistics(details, target_detail)
                for name, numeric in statistics.items():
                    components[name] = details.output.new_tensor(numeric)
            finite("loss", total_loss); total_loss.backward()
            norm = torch.nn.utils.clip_grad_norm_(detector_parameters if stage == "detector" else renderer_parameters,
                                                  float(CONFIG["training"]["gradient_clip"]))
            finite("gradient", norm); optimizer.step(); batches += 1
            totals["total"] += float(total_loss.detach().cpu())
            for name, value in components.items(): totals[name] += float(value.detach().cpu())
            if options["steps_per_epoch"] and batches >= options["steps_per_epoch"]: break
        if epoch == options["detector_epochs"]: detector_hash = state_hash(model)
        validation, previews = validate_internal(model, device, options["validation_limit"], options["batch_size"])
        row = {
            "epoch": epoch, "stage": stage, "global_step": global_step, "learning_rate": learning_rate,
            "duration_seconds": time.perf_counter() - epoch_started,
            "gpu_peak_allocated_gib": torch.cuda.max_memory_allocated(device) / 2 ** 30,
            "gpu_peak_reserved_gib": torch.cuda.max_memory_reserved(device) / 2 ** 30,
            **{f"train_{name}": value / max(batches, 1) for name, value in totals.items()},
            **{f"validation_{name}": value for name, value in validation.items()},
        }
        history.append(row); atomic_json(run_dir / "training_history.json", history)
        save_preview(run_dir / "previews" / f"epoch_{epoch:03d}.png", previews)
        torch.save({"model": model.state_dict(), "arm": arm, "epoch": epoch, "scratch": True,
                    "initial_state_sha256": initial_hash, "config": CONFIG}, run_dir / f"epoch_{epoch:03d}.pth")
        print(json.dumps({"arm": arm, **row}), flush=True)
    locked = evaluate_locked_challenge(model, device, run_dir, options["batch_size"])
    free_end, _ = torch.cuda.mem_get_info(device); peak_reserved = torch.cuda.max_memory_reserved(device) / 2 ** 30
    state = {
        "status": "complete", "mode": mode, "arm": arm, "run_id": run_id, "scratch": True,
        "epochs_completed": options["epochs"], "global_step": global_step, "parameters": count_parameters(model),
        "initial_state_sha256": initial_hash, "post_detector_state_sha256": detector_hash,
        "final_state_sha256": state_hash(model), "elapsed_seconds": time.perf_counter() - started,
        "gpu_start_free_gib": free_start / 2 ** 30, "gpu_end_free_gib": free_end / 2 ** 30,
        "gpu_peak_reserved_gib": peak_reserved,
        "estimated_minimum_free_gib": free_start / 2 ** 30 - peak_reserved,
        "locked_challenge": locked,
    }
    atomic_json(run_dir / "run_state.json", state)
    del model
    torch.cuda.empty_cache()
    return run_dir


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("smoke", "formal"), default="smoke")
    parser.add_argument("--arm", choices=("width_shift", "bounded_detail", "bounded_detail_supervised", "both", "all"), default="both")
    parser.add_argument("--confirm-formal", action="store_true")
    parser.add_argument("--run-prefix", default="")
    args = parser.parse_args()
    if args.mode == "formal" and (not args.confirm_formal or not bool(CONFIG["formal_training_authorized"])):
        raise RuntimeError("Formal training is blocked. It needs new explicit authorization and --confirm-formal.")
    selection = ROOT / CONFIG["data"]["selection_file"]
    if not selection.exists(): raise FileNotFoundError("Run scripts/prepare_selection.py first")
    if args.mode == "smoke":
        smoke = CONFIG["smoke"]
        options = {"epochs": int(smoke["epochs"]), "detector_epochs": int(smoke["detector_epochs"]),
                   "steps_per_epoch": int(smoke["steps_per_epoch"]), "data_limit": int(smoke["data_limit"]),
                   "validation_limit": int(smoke["validation_limit"]), "batch_size": int(smoke["batch_size"]),
                   "workers": int(smoke["workers"])}
    else:
        training = CONFIG["training"]
        options = {"epochs": int(training["formal_epochs"]), "detector_epochs": int(training["detector_epochs"]),
                   "steps_per_epoch": 0, "data_limit": int(CONFIG["data"]["train_count"]),
                   "validation_limit": int(CONFIG["data"]["validation_count"]),
                   "batch_size": int(training["batch_size"]), "workers": int(training["workers"])}
    if args.arm == "both":
        arms = list(CONFIG["reference_arms"])
    elif args.arm == "all":
        arms = list(CONFIG["arms"])
    else:
        arms = [args.arm]
    stamp = time.strftime("%Y%m%d_%H%M%S"); registry = []
    for arm in arms:
        prefix = args.run_prefix or f"{args.mode}_{stamp}"
        run_dir = train_arm(arm, args.mode, options, f"{prefix}_{arm}")
        registry.append({"arm": arm, "run_dir": str(run_dir), "run_state": str(run_dir / "run_state.json")})
    registry_name = (f"latest_supervised_{args.mode}_registry.json"
                     if arms == ["bounded_detail_supervised"] else f"latest_{args.mode}_registry.json")
    atomic_json(ROOT / "runs" / registry_name, {
        "status": "complete", "mode": args.mode, "formal_confirmed": bool(args.confirm_formal), "runs": registry,
    })
    print(json.dumps({"status": "complete", "mode": args.mode, "runs": registry}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

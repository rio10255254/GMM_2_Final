"""Run the fair, scratch-only A/B/C R101 short experiment."""
from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.util
import json
import math
import os
import random
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

import cv2
import numpy as np
import torch
from torch import nn
import torch.nn.functional as F


ROOT = Path(__file__).resolve().parents[1]
MODEL_PATH = ROOT / "model" / "prototype_models.py"


def load_model_module():
    spec = importlib.util.spec_from_file_location("r101_prototype_models", MODEL_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load prototype models: {MODEL_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


MODELS = load_model_module()


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    os.replace(temporary, path)


def state_hash(model: nn.Module, common_only: bool = False) -> str:
    digest = hashlib.sha256()
    for name, value in sorted(model.state_dict().items()):
        if common_only and name.startswith("renderer_"):
            continue
        digest.update(name.encode("utf-8"))
        digest.update(value.detach().cpu().contiguous().numpy().tobytes())
    return digest.hexdigest()


def file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def set_seed(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)


def sobel(x: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
    kernel_x = torch.tensor([[-1.0, 0.0, 1.0], [-2.0, 0.0, 2.0], [-1.0, 0.0, 1.0]], device=x.device, dtype=x.dtype).view(1, 1, 3, 3) / 8.0
    kernel_y = kernel_x.transpose(-1, -2).contiguous()
    gx = F.conv2d(F.pad(x, (1, 1, 1, 1), mode="reflect"), kernel_x)
    gy = F.conv2d(F.pad(x, (1, 1, 1, 1), mode="reflect"), kernel_y)
    return gx, gy, torch.sqrt(gx.square() + gy.square() + 1e-8)


def blur3(x: torch.Tensor) -> torch.Tensor:
    vector = torch.tensor([1.0, 2.0, 1.0], device=x.device, dtype=x.dtype) / 4.0
    kh = vector.view(1, 1, 1, 3)
    kv = vector.view(1, 1, 3, 1)
    y = F.conv2d(F.pad(x, (1, 1, 0, 0), mode="reflect"), kh)
    return F.conv2d(F.pad(y, (0, 0, 1, 1), mode="reflect"), kv)


def gaussian_blur(x: torch.Tensor, sigma: float) -> torch.Tensor:
    if sigma <= 0.05:
        return x
    radius = max(1, int(math.ceil(4.0 * sigma)))
    coordinate = torch.arange(-radius, radius + 1, device=x.device, dtype=x.dtype)
    vector = torch.exp(-0.5 * (coordinate / sigma).square())
    vector = vector / vector.sum()
    kh = vector.view(1, 1, 1, -1)
    kv = vector.view(1, 1, -1, 1)
    y = F.conv2d(F.pad(x, (radius, radius, 0, 0), mode="reflect"), kh)
    return F.conv2d(F.pad(y, (0, 0, radius, radius), mode="reflect"), kv)


def forward_optics(
    output: torch.Tensor,
    source_sigma: torch.Tensor,
    exposure: torch.Tensor,
    gamma: torch.Tensor,
    bias: torch.Tensor,
    reference_sigma: float,
) -> torch.Tensor:
    result = torch.empty_like(output)
    for sigma_value in torch.unique(source_sigma.detach()).tolist():
        selected = torch.isclose(source_sigma, torch.tensor(float(sigma_value), device=source_sigma.device), atol=1e-5)
        residual = math.sqrt(max(float(sigma_value) ** 2 - reference_sigma ** 2, 0.0))
        result[selected] = gaussian_blur(output[selected], residual).float()
    result = torch.clamp(result * exposure[:, None, None, None] + bias[:, None, None, None], 0.0, 1.0)
    return torch.pow(result.clamp_min(1e-6), gamma[:, None, None, None])


def complex_frequency_loss(output: torch.Tensor, target: torch.Tensor) -> torch.Tensor:
    output_f = torch.fft.rfft2(output.float(), norm="ortho")
    target_f = torch.fft.rfft2(target.float(), norm="ortho")
    height, width_half = output_f.shape[-2:]
    fy = torch.fft.fftfreq(height, device=output.device).abs().view(height, 1)
    fx = torch.fft.rfftfreq((width_half - 1) * 2, device=output.device).abs().view(1, width_half)
    radius = torch.sqrt(fx.square() + fy.square())
    weight = torch.clamp((radius - 0.08) / 0.32, 0.0, 1.0)
    return torch.mean(torch.abs(output_f - target_f) * weight)


def loss_components(
    arm: str,
    details: dict[str, torch.Tensor],
    batch: dict[str, torch.Tensor],
    stream: str,
    reference_sigma: float,
) -> tuple[torch.Tensor, dict[str, float]]:
    output = details["output"]
    target = batch["target"]
    boundary = batch["boundary"]
    pixel = torch.mean(torch.sqrt((output - target).square() + 1e-6))
    boundary_l1 = torch.sum(torch.abs(output - target) * (0.25 + boundary)) / torch.sum(0.25 + boundary)
    out_gx, out_gy, _out_mag = sobel(output)
    target_gx, target_gy, _target_mag = sobel(target)
    gradient = torch.mean(torch.abs(out_gx - target_gx) + torch.abs(out_gy - target_gy))
    out_band, target_band = output - blur3(output), target - blur3(target)
    detail = torch.sum(torch.abs(out_band - target_band) * (0.35 + boundary)) / torch.sum(0.35 + boundary)
    frequency = complex_frequency_loss(output, target)
    local_max = F.max_pool2d(target, 5, stride=1, padding=2)
    local_min = -F.max_pool2d(-target, 5, stride=1, padding=2)
    halo = torch.mean(F.relu(output - local_max - 0.01) + F.relu(local_min - output - 0.01))

    polarity = batch["foreground"] - batch["background"]
    normalized = (output[:, 0] - batch["background"][:, None, None]) / (polarity[:, None, None] + torch.sign(polarity)[:, None, None] * 1e-5)
    occupancy = torch.sum(torch.abs(normalized.clamp(-0.2, 1.2) - batch["mask"][:, 0]) * boundary[:, 0]) / torch.sum(boundary[:, 0])
    identity_selected = batch["identity"] > 0
    identity = torch.mean(torch.abs(output[identity_selected] - batch["source"][identity_selected])) if bool(identity_selected.any()) else output.new_tensor(0.0)

    consistency = output.new_tensor(0.0)
    if arm == "C":
        predicted_source = forward_optics(
            output.float(), batch["source_sigma"], batch["exposure"], batch["gamma"], batch["bias"], reference_sigma,
        )
        consistency = torch.mean(torch.sqrt((predicted_source - batch["source_clean"].float()).square() + 1e-6))

    if stream == "boundary":
        total = 0.55 * pixel + 1.00 * boundary_l1 + 0.55 * gradient + 0.32 * occupancy + 0.12 * frequency + 0.12 * halo
    elif stream == "detail":
        total = 0.45 * pixel + 0.42 * boundary_l1 + 0.30 * gradient + 0.72 * detail + 0.46 * frequency + 0.12 * halo
    else:
        total = 0.85 * pixel + 0.22 * boundary_l1 + 0.18 * gradient + 0.30 * identity + (0.65 * consistency if arm == "C" else 0.0)
    parts = {
        "total": float(total.detach()),
        "pixel": float(pixel.detach()),
        "boundary": float(boundary_l1.detach()),
        "gradient": float(gradient.detach()),
        "detail": float(detail.detach()),
        "frequency": float(frequency.detach()),
        "halo": float(halo.detach()),
        "occupancy": float(occupancy.detach()),
        "identity": float(identity.detach()),
        "consistency": float(consistency.detach()),
    }
    return total, parts


def tensor_batch(arrays: dict[str, np.ndarray], indices: np.ndarray, device: torch.device) -> dict[str, torch.Tensor]:
    image_names = {"source", "source_clean", "target", "mask", "boundary"}
    scalar_names = {"source_sigma", "exposure", "gamma", "bias", "foreground", "background", "identity", "scene_id", "observation", "dx", "dy"}
    result: dict[str, torch.Tensor] = {}
    for name in image_names:
        value = torch.from_numpy(np.asarray(arrays[name][indices], dtype=np.float32))[:, None]
        result[name] = value.to(device, non_blocking=True)
    for name in scalar_names:
        value = torch.from_numpy(np.asarray(arrays[name][indices]))
        result[name] = value.to(device, non_blocking=True)
    return result


@torch.inference_mode()
def save_preview(model: nn.Module, arrays: dict[str, np.ndarray], device: torch.device, path: Path, step: int) -> None:
    selected = np.flatnonzero(arrays["split"] == 1)[:4]
    source = torch.from_numpy(np.asarray(arrays["source"][selected], dtype=np.float32))[:, None].to(device)
    model.eval()
    output = model(source).float().cpu().numpy()[:, 0]
    panels = []
    for row, index in enumerate(selected):
        raw = np.clip(arrays["source"][index].astype(np.float32) * 255.0, 0, 255).astype(np.uint8)
        prediction = np.clip(output[row] * 255.0, 0, 255).astype(np.uint8)
        target = np.clip(arrays["target"][index].astype(np.float32) * 255.0, 0, 255).astype(np.uint8)
        difference = cv2.applyColorMap(np.clip(np.abs(output[row] - arrays["target"][index].astype(np.float32)) * 800.0, 0, 255).astype(np.uint8), cv2.COLORMAP_TURBO)
        gray_row = np.concatenate([raw, prediction, target], axis=1)
        gray_row = cv2.cvtColor(gray_row, cv2.COLOR_GRAY2BGR)
        panels.append(np.concatenate([gray_row, difference], axis=1))
    canvas = np.concatenate(panels, axis=0)
    path.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(path), canvas)


def run_arm(
    arm: str,
    config: dict[str, Any],
    arrays: dict[str, np.ndarray],
    schedule: np.ndarray,
    device: torch.device,
) -> dict[str, Any]:
    training = config["training"]
    seed = int(training["seed"])
    set_seed(seed)
    model = MODELS.build_model(arm, base=int(training["model_width"])).to(device)
    model = model.to(memory_format=torch.channels_last)
    initial_hash = state_hash(model)
    common_initial_hash = state_hash(model, common_only=True)
    optimizer = torch.optim.AdamW(
        model.parameters(), lr=float(training["learning_rate"]), weight_decay=float(training["weight_decay"]), fused=(device.type == "cuda"),
    )
    steps = int(training["steps_per_arm"])
    streams = list(training["stream_cycle"])
    checkpoint_steps = set(map(int, training["checkpoint_steps"]))
    run_dir = ROOT / "runs" / f"ablation_seed{seed}" / f"arm_{arm}"
    weight_dir = ROOT / "weights" / f"arm_{arm}"
    preview_dir = ROOT / "results" / "training_previews" / f"arm_{arm}"
    if (run_dir / "run_summary.json").exists():
        raise RuntimeError(f"Arm {arm} already has a completed summary; refusing to overwrite it.")
    run_dir.mkdir(parents=True, exist_ok=True)
    weight_dir.mkdir(parents=True, exist_ok=True)
    preview_dir.mkdir(parents=True, exist_ok=True)
    log_path = run_dir / "training_log.csv"
    fields = ["step", "stream", "lr", "seconds", "gpu_peak_gib", "gpu_free_gib", "total", "pixel", "boundary", "gradient", "detail", "frequency", "halo", "occupancy", "identity", "consistency"]
    with log_path.open("w", newline="", encoding="utf-8") as handle:
        csv.DictWriter(handle, fieldnames=fields).writeheader()

    torch.save({"arm": arm, "step": 0, "model": model.state_dict(), "initial_hash": initial_hash, "common_initial_hash": common_initial_hash}, weight_dir / "step_000.pth.tar")
    save_preview(model, arrays, device, preview_dir / "step_000.png", 0)
    started = time.perf_counter()
    recent_seconds: list[float] = []
    amp_enabled = device.type == "cuda" and str(training["precision"]).lower() == "bfloat16"
    reference_sigma = float(config["data"]["reference_psf_sigma_px"])
    model.train()
    if device.type == "cuda":
        torch.cuda.reset_peak_memory_stats(device)

    try:
        for step in range(1, steps + 1):
            step_started = time.perf_counter()
            lr_fraction = (step - 1) / max(steps - 1, 1)
            lr = float(training["minimum_learning_rate"]) + 0.5 * (float(training["learning_rate"]) - float(training["minimum_learning_rate"])) * (1.0 + math.cos(math.pi * lr_fraction))
            for group in optimizer.param_groups:
                group["lr"] = lr
            batch = tensor_batch(arrays, schedule[step - 1], device)
            source = batch["source"].contiguous(memory_format=torch.channels_last)
            stream = streams[(step - 1) % len(streams)]
            optimizer.zero_grad(set_to_none=True)
            with torch.autocast(device_type="cuda", dtype=torch.bfloat16, enabled=amp_enabled):
                details = model(source, return_details=True)
                total, parts = loss_components(arm, details, batch, stream, reference_sigma)
            if not bool(torch.isfinite(total)):
                raise FloatingPointError(f"Non-finite loss in arm {arm} step {step}")
            total.backward()
            gradient_norm = torch.nn.utils.clip_grad_norm_(model.parameters(), float(training["gradient_clip"]))
            if not bool(torch.isfinite(gradient_norm)):
                raise FloatingPointError(f"Non-finite gradient in arm {arm} step {step}")
            optimizer.step()
            if device.type == "cuda":
                torch.cuda.synchronize(device)
            elapsed_step = time.perf_counter() - step_started
            recent_seconds.append(elapsed_step)
            recent_seconds = recent_seconds[-30:]
            gpu_peak = torch.cuda.max_memory_allocated(device) / 2**30 if device.type == "cuda" else 0.0
            free_bytes, _total_bytes = torch.cuda.mem_get_info(device) if device.type == "cuda" else (0, 0)
            row = {"step": step, "stream": stream, "lr": lr, "seconds": elapsed_step, "gpu_peak_gib": gpu_peak, "gpu_free_gib": free_bytes / 2**30, **parts}
            with log_path.open("a", newline="", encoding="utf-8") as handle:
                csv.DictWriter(handle, fieldnames=fields).writerow(row)

            if step % 10 == 0 or step == 1 or step in checkpoint_steps:
                mean_step = float(np.median(recent_seconds))
                progress = {
                    "status": "active",
                    "arm": arm,
                    "step": step,
                    "planned_steps": steps,
                    "stream": stream,
                    "loss": parts,
                    "seconds_per_step_recent_median": mean_step,
                    "eta_seconds": mean_step * (steps - step),
                    "gpu_peak_gib": gpu_peak,
                    "gpu_free_gib": free_bytes / 2**30,
                    "updated_at": datetime.now().isoformat(),
                }
                write_json(run_dir / "progress.json", progress)
                write_json(ROOT / "runs" / "active_run.json", progress)
                print(json.dumps(progress, ensure_ascii=False), flush=True)
            if step in checkpoint_steps:
                checkpoint = {
                    "arm": arm,
                    "step": step,
                    "model": model.state_dict(),
                    "optimizer": optimizer.state_dict(),
                    "initial_hash": initial_hash,
                    "common_initial_hash": common_initial_hash,
                    "config": config,
                }
                torch.save(checkpoint, weight_dir / f"step_{step:03d}.pth.tar")
                torch.save(checkpoint, weight_dir / "latest.pth.tar")
                save_preview(model, arrays, device, preview_dir / f"step_{step:03d}.png", step)

        summary = {
            "status": "complete",
            "arm": arm,
            "steps": steps,
            "initial_hash": initial_hash,
            "common_initial_hash": common_initial_hash,
            "final_hash": state_hash(model),
            "elapsed_seconds": time.perf_counter() - started,
            "gpu_peak_gib": torch.cuda.max_memory_allocated(device) / 2**30 if device.type == "cuda" else 0.0,
            "training_log": str(log_path),
            "final_checkpoint": str(weight_dir / "latest.pth.tar"),
            "finished_at": datetime.now().isoformat(),
        }
        write_json(run_dir / "run_summary.json", summary)
        return summary
    except BaseException as exc:
        failure = {"status": "failed", "arm": arm, "error": repr(exc), "failed_at": datetime.now().isoformat()}
        write_json(run_dir / "failure.json", failure)
        write_json(ROOT / "runs" / "active_run.json", failure)
        raise


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=ROOT / "config" / "experiment.json")
    parser.add_argument("--device", default="cuda:0")
    args = parser.parse_args()
    config = json.loads(args.config.read_text(encoding="utf-8"))
    if bool(config.get("full_r101_training_authorized")):
        raise RuntimeError("This script is only for the short A/B/C experiment.")
    if config["source_isolation"]["checkpoint_loading_allowed"] or config["source_isolation"]["resume_allowed"]:
        raise RuntimeError("Scratch isolation is not active.")
    data_path = ROOT / "data" / "continuous_pairs.npz"
    manifest_path = ROOT / "data" / "dataset_manifest.json"
    schedule_path = ROOT / "data" / "batch_schedule.npy"
    if not data_path.is_file() or not manifest_path.is_file() or not schedule_path.is_file():
        raise FileNotFoundError("The continuous paired dataset is incomplete.")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest["contains_real_sem_or_hs100mg_pixels"] or not manifest["source_and_target_share_latent_geometry_and_texture_phase"]:
        raise RuntimeError("Dataset isolation or phase-consistency contract failed.")

    with np.load(data_path) as loaded:
        arrays = {name: loaded[name] for name in loaded.files}
    schedule = np.load(schedule_path)
    expected_shape = (int(config["training"]["steps_per_arm"]), int(config["training"]["batch_size"]))
    if tuple(schedule.shape) != expected_shape:
        raise RuntimeError(f"Batch schedule mismatch: {schedule.shape} != {expected_shape}")
    device = torch.device(args.device if torch.cuda.is_available() else "cpu")
    if device.type == "cuda":
        torch.backends.cuda.matmul.allow_tf32 = True
        torch.backends.cudnn.allow_tf32 = True
        torch.set_float32_matmul_precision("high")

    experiment_state = {
        "status": "active",
        "experiment_id": config["experiment_id"],
        "started_at": datetime.now().isoformat(),
        "trainer_pid": os.getpid(),
        "device": str(device),
        "gpu": torch.cuda.get_device_name(device) if device.type == "cuda" else "cpu",
        "dataset_sha256": file_hash(data_path),
        "schedule_sha256": file_hash(schedule_path),
        "model_source_sha256": file_hash(MODEL_PATH),
        "reference_model_sha256": file_hash(Path(config["reference_model_path"])),
    }
    write_json(ROOT / "runs" / "experiment_state.json", experiment_state)
    summaries = []
    for arm in ("A", "B", "C"):
        write_json(ROOT / "runs" / "active_run.json", {**experiment_state, "current_arm": arm, "status": "active"})
        summaries.append(run_arm(arm, config, arrays, schedule, device))
        if device.type == "cuda":
            torch.cuda.empty_cache()
    common_hashes = {row["common_initial_hash"] for row in summaries}
    if len(common_hashes) != 1:
        raise RuntimeError("A/B/C common initialization hashes differ.")
    complete = {**experiment_state, "status": "training_complete", "arm_summaries": summaries, "common_initial_hash": next(iter(common_hashes)), "finished_at": datetime.now().isoformat()}
    write_json(ROOT / "runs" / "training_summary.json", complete)
    write_json(ROOT / "runs" / "active_run.json", complete)
    print(json.dumps(complete, indent=2, ensure_ascii=False), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

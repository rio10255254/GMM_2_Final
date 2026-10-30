from __future__ import annotations

import argparse
import csv
import json
import math
import random
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path

import cv2
import numpy as np
import torch
import torch.nn.functional as F
from torch.cuda.amp import GradScaler, autocast
from torch.utils.data import DataLoader


EXPERIMENT = Path(__file__).resolve().parent
BASE_EXPERIMENT = EXPERIMENT.parent / "BaseUNet_Baseline_20260718"
if str(BASE_EXPERIMENT) not in sys.path:
    sys.path.insert(0, str(BASE_EXPERIMENT))

from train_base_unet import (  # noqa: E402
    PairedPatchDataset,
    build_fixed_psf_layer,
    load_split,
    read_gray_u8,
    ssim_value,
)

from models_modern import (  # noqa: E402
    MODEL_SPECS,
    build_model,
    serializable_spec,
    trainable_parameter_count,
)


DEFAULT_PACKAGE = (
    EXPERIMENT.parents[1]
    / ".."
    / "Deliverables"
    / "Standalone_Models"
    / "V42_SoftLabelSNR_FullStandalone_20260709"
)


@dataclass(frozen=True)
class TrainConfig:
    model_key: str
    seed: int = 1261200
    epochs: int = 30
    crop_size: int = 256
    micro_batch_size: int = 32
    effective_batch_size: int = 32
    train_repeats: int = 1
    learning_rate: float = 2.0e-4
    min_learning_rate: float = 2.0e-6
    weight_decay: float = 1.0e-4
    ssim_weight: float = 0.20
    validate_every: int = 3
    patience_validations: int = 10
    fixed_psf: bool = True
    psf_path: str = ""
    psf_reg: float = 10.0
    psf_alpha: float = 0.10
    amp: bool = True

    @property
    def accumulation_steps(self) -> int:
        if self.effective_batch_size % self.micro_batch_size != 0:
            raise ValueError("effective batch must be divisible by micro batch")
        return self.effective_batch_size // self.micro_batch_size


def seed_everything(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)
    torch.backends.cudnn.benchmark = True


def reconstruction_loss(
    prediction: torch.Tensor,
    target: torch.Tensor,
    ssim_weight: float,
) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
    l1 = F.l1_loss(prediction, target)
    ssim = ssim_value(prediction.clamp(0.0, 1.0), target)
    total = l1 + float(ssim_weight) * (1.0 - ssim)
    return total, l1, ssim


@torch.inference_mode()
def validate(
    model: torch.nn.Module,
    source_paths: list[Path],
    source_root: Path,
    label_root: Path,
    device: torch.device,
    ssim_weight: float,
    amp_enabled: bool,
) -> dict[str, float]:
    model.eval()
    totals: list[float] = []
    l1s: list[float] = []
    rmses: list[float] = []
    ssims: list[float] = []
    for source_path in source_paths:
        relative = source_path.relative_to(source_root)
        source_np = read_gray_u8(source_path).astype(np.float32) / 255.0
        label_np = read_gray_u8(label_root / relative).astype(np.float32) / 255.0
        source = torch.from_numpy(source_np)[None, None].to(device)
        target = torch.from_numpy(label_np)[None, None].to(device)
        with autocast(enabled=amp_enabled):
            prediction = model(source)
            total, l1, ssim = reconstruction_loss(prediction, target, ssim_weight)
        clipped = prediction.float().clamp(0.0, 1.0)
        rmse = torch.sqrt(F.mse_loss(clipped, target.float()))
        totals.append(float(total))
        l1s.append(float(F.l1_loss(clipped, target.float())))
        rmses.append(float(rmse))
        ssims.append(float(ssim))
    return {
        "loss": float(np.mean(totals)),
        "l1": float(np.mean(l1s)),
        "rmse": float(np.mean(rmses)),
        "ssim": float(np.mean(ssims)),
    }


@torch.inference_mode()
def write_validation_examples(
    model: torch.nn.Module,
    paths: list[Path],
    source_root: Path,
    label_root: Path,
    output_dir: Path,
    device: torch.device,
    amp_enabled: bool,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    model.eval()
    for index, source_path in enumerate(paths[:8]):
        relative = source_path.relative_to(source_root)
        source_np = read_gray_u8(source_path)
        label_np = read_gray_u8(label_root / relative)
        source = torch.from_numpy(source_np.astype(np.float32) / 255.0)[None, None].to(device)
        with autocast(enabled=amp_enabled):
            prediction = model(source)
        result = np.clip(
            np.rint(prediction[0, 0].float().clamp(0.0, 1.0).cpu().numpy() * 255.0),
            0,
            255,
        ).astype(np.uint8)
        joined = np.concatenate([source_np, result, label_np], axis=1)
        success, encoded = cv2.imencode(".png", joined)
        if not success:
            raise RuntimeError("Could not encode validation example")
        encoded.tofile(str(output_dir / f"example_{index + 1:02d}_raw_model_label.png"))


def build_training_model(
    package: Path,
    config: TrainConfig,
    device: torch.device,
) -> torch.nn.Module:
    input_adapter = None
    if config.fixed_psf:
        psf_path = (
            Path(config.psf_path)
            if config.psf_path
            else package / "psf" / "PSF_fitted_2D_FOVstack.mat"
        )
        input_adapter = build_fixed_psf_layer(
            package,
            psf_path,
            reg=config.psf_reg,
            alpha=config.psf_alpha,
        )
    model = build_model(config.model_key, input_adapter=input_adapter).to(device)
    if input_adapter is not None:
        for parameter in model.input_adapter.parameters():
            parameter.requires_grad_(False)
        model.input_adapter.eval()
    return model


def train(
    package: Path,
    output: Path,
    config: TrainConfig,
    resume: bool,
    smoke_steps: int,
) -> None:
    output.mkdir(parents=True, exist_ok=True)
    seed_everything(config.seed)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    amp_enabled = bool(config.amp and device.type == "cuda")
    source_root, label_root, train_paths, validation_paths = load_split(package)
    dataset = PairedPatchDataset(
        source_root,
        label_root,
        train_paths,
        crop_size=config.crop_size,
        repeats=config.train_repeats,
        augment=True,
    )
    generator = torch.Generator().manual_seed(config.seed)
    loader = DataLoader(
        dataset,
        batch_size=config.micro_batch_size,
        shuffle=True,
        num_workers=0,
        pin_memory=device.type == "cuda",
        drop_last=False,
        generator=generator,
    )

    model = build_training_model(package, config, device)
    parameter_count = trainable_parameter_count(model)
    trainable_parameters = [p for p in model.parameters() if p.requires_grad]
    optimizer = torch.optim.AdamW(
        trainable_parameters,
        lr=config.learning_rate,
        weight_decay=config.weight_decay,
    )
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(
        optimizer,
        T_max=config.epochs,
        eta_min=config.min_learning_rate,
    )
    scaler = GradScaler(enabled=amp_enabled)
    best_loss = math.inf
    best_epoch = 0
    stale_validations = 0
    history: list[dict[str, float | int]] = []
    start_epoch = 1
    checkpoint_last = output / "last_checkpoint.pth.tar"

    if resume and checkpoint_last.exists():
        checkpoint = torch.load(checkpoint_last, map_location=device)
        model.load_state_dict(checkpoint["state_dict"], strict=True)
        optimizer.load_state_dict(checkpoint["optimizer"])
        scheduler.load_state_dict(checkpoint["scheduler"])
        scaler.load_state_dict(checkpoint["scaler"])
        best_loss = float(checkpoint["best_loss"])
        best_epoch = int(checkpoint["best_epoch"])
        stale_validations = int(checkpoint["stale_validations"])
        history = list(checkpoint.get("history", []))
        start_epoch = int(checkpoint["epoch"]) + 1

    metadata = {
        "purpose": "Parameter-comparable modern learned restoration baseline",
        "model_key": config.model_key,
        "model_spec": serializable_spec(config.model_key),
        "common_training_rule": (
            "Same paired dataset, grouped split, 256-pixel crops, fixed optical input adapter, "
            "L1+SSIM objective, optimizer family, effective batch, validation rule, and best-checkpoint rule; "
            "training stops after validation convergence."
        ),
        "loss_definition": "L1 + 0.20 * (1 - SSIM); output clipping is used for SSIM and reported validation metrics",
        "package": str(package),
        "source_root": str(source_root),
        "label_root": str(label_root),
        "train_count": len(train_paths),
        "validation_count": len(validation_paths),
        "parameter_count": parameter_count,
        "device": str(device),
        "gpu": torch.cuda.get_device_name(0) if device.type == "cuda" else None,
        "torch_version": torch.__version__,
        "config": asdict(config),
        "accumulation_steps": config.accumulation_steps,
    }
    (output / "run_manifest.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(metadata, ensure_ascii=False, indent=2), flush=True)

    if smoke_steps > 0:
        model.train()
        optimizer.zero_grad(set_to_none=True)
        for step, (source, target) in enumerate(loader, start=1):
            source = source.to(device, non_blocking=True)
            target = target.to(device, non_blocking=True)
            with autocast(enabled=amp_enabled):
                prediction = model(source)
                loss, _, _ = reconstruction_loss(prediction, target, config.ssim_weight)
                scaled_loss = loss / config.accumulation_steps
            scaler.scale(scaled_loss).backward()
            if step % config.accumulation_steps == 0:
                scaler.step(optimizer)
                scaler.update()
                optimizer.zero_grad(set_to_none=True)
            print(
                f"smoke_step={step} loss={float(loss.detach()):.6f} "
                f"allocated_gb={torch.cuda.max_memory_allocated() / 2**30:.3f}",
                flush=True,
            )
            if step >= smoke_steps:
                break
        return

    start_time = time.time()
    for epoch in range(start_epoch, config.epochs + 1):
        model.train()
        model.input_adapter.eval()
        optimizer.zero_grad(set_to_none=True)
        epoch_losses: list[float] = []
        epoch_l1s: list[float] = []
        epoch_ssims: list[float] = []
        optimizer_steps = 0

        for step, (source, target) in enumerate(loader, start=1):
            source = source.to(device, non_blocking=True)
            target = target.to(device, non_blocking=True)
            with autocast(enabled=amp_enabled):
                prediction = model(source)
                loss, l1, ssim = reconstruction_loss(
                    prediction, target, config.ssim_weight
                )
                scaled_loss = loss / config.accumulation_steps
            scaler.scale(scaled_loss).backward()
            is_update = (
                step % config.accumulation_steps == 0 or step == len(loader)
            )
            if is_update:
                scaler.step(optimizer)
                scaler.update()
                optimizer.zero_grad(set_to_none=True)
                optimizer_steps += 1
            epoch_losses.append(float(loss.detach()))
            epoch_l1s.append(float(l1.detach()))
            epoch_ssims.append(float(ssim.detach()))

        scheduler.step()
        record: dict[str, float | int] = {
            "epoch": epoch,
            "lr": float(optimizer.param_groups[0]["lr"]),
            "optimizer_steps": optimizer_steps,
            "train_loss": float(np.mean(epoch_losses)),
            "train_l1": float(np.mean(epoch_l1s)),
            "train_ssim": float(np.mean(epoch_ssims)),
            "elapsed_seconds": time.time() - start_time,
        }
        should_validate = (
            epoch == 1
            or epoch % config.validate_every == 0
            or epoch == config.epochs
        )
        if should_validate:
            metrics = validate(
                model,
                validation_paths,
                source_root,
                label_root,
                device,
                config.ssim_weight,
                amp_enabled,
            )
            record.update({f"val_{key}": value for key, value in metrics.items()})
            if metrics["loss"] < best_loss - 1.0e-5:
                best_loss = metrics["loss"]
                best_epoch = epoch
                stale_validations = 0
                torch.save(
                    {
                        "state_dict": model.state_dict(),
                        "epoch": epoch,
                        "validation": metrics,
                        "model_key": config.model_key,
                        "model_spec": serializable_spec(config.model_key),
                        "parameter_count": parameter_count,
                        "training_config": asdict(config),
                    },
                    output / f"best_{config.model_key}.pth.tar",
                )
            else:
                stale_validations += 1
            print(
                f"epoch={epoch:03d} train={record['train_loss']:.6f} "
                f"val={metrics['loss']:.6f} l1={metrics['l1']:.6f} "
                f"ssim={metrics['ssim']:.5f} best={best_epoch:03d} "
                f"elapsed_min={(time.time() - start_time) / 60.0:.1f}",
                flush=True,
            )
        else:
            print(
                f"epoch={epoch:03d} train={record['train_loss']:.6f} "
                f"l1={record['train_l1']:.6f} ssim={record['train_ssim']:.5f} "
                f"elapsed_min={(time.time() - start_time) / 60.0:.1f}",
                flush=True,
            )
        history.append(record)

        torch.save(
            {
                "state_dict": model.state_dict(),
                "optimizer": optimizer.state_dict(),
                "scheduler": scheduler.state_dict(),
                "scaler": scaler.state_dict(),
                "epoch": epoch,
                "best_loss": best_loss,
                "best_epoch": best_epoch,
                "stale_validations": stale_validations,
                "history": history,
                "training_config": asdict(config),
            },
            checkpoint_last,
        )

        if stale_validations >= config.patience_validations and epoch >= 24:
            print(f"Early stopping at epoch {epoch}; best epoch {best_epoch}", flush=True)
            break

    with (output / "training_history.csv").open(
        "w", newline="", encoding="utf-8-sig"
    ) as handle:
        fieldnames = sorted({key for row in history for key in row})
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(history)

    best_checkpoint_path = output / f"best_{config.model_key}.pth.tar"
    checkpoint = torch.load(best_checkpoint_path, map_location=device)
    model.load_state_dict(checkpoint["state_dict"], strict=True)
    final_metrics = validate(
        model,
        validation_paths,
        source_root,
        label_root,
        device,
        config.ssim_weight,
        amp_enabled,
    )
    write_validation_examples(
        model,
        validation_paths,
        source_root,
        label_root,
        output / "validation_examples",
        device,
        amp_enabled,
    )
    summary = {
        **metadata,
        "best_epoch": int(checkpoint["epoch"]),
        "best_validation": final_metrics,
        "elapsed_seconds": time.time() - start_time,
        "checkpoint": str(best_checkpoint_path),
    }
    (output / "training_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2), flush=True)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", choices=sorted(MODEL_SPECS), required=True)
    parser.add_argument("--package", type=Path, default=DEFAULT_PACKAGE)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--epochs", type=int, default=30)
    parser.add_argument("--micro-batch-size", type=int)
    parser.add_argument("--effective-batch-size", type=int, default=32)
    parser.add_argument("--validate-every", type=int, default=3)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--smoke-steps", type=int, default=0)
    return parser.parse_args()


if __name__ == "__main__":
    arguments = parse_args()
    micro_defaults = {"nafnet": 64, "edsr": 16}
    micro_batch_size = (
        arguments.micro_batch_size
        if arguments.micro_batch_size is not None
        else micro_defaults[arguments.model]
    )
    output = (
        arguments.output
        if arguments.output is not None
        else EXPERIMENT / "results" / arguments.model
    )
    configuration = TrainConfig(
        model_key=arguments.model,
        epochs=arguments.epochs,
        micro_batch_size=micro_batch_size,
        effective_batch_size=arguments.effective_batch_size,
        validate_every=arguments.validate_every,
    )
    train(
        arguments.package.resolve(),
        output.resolve(),
        configuration,
        resume=arguments.resume,
        smoke_steps=arguments.smoke_steps,
    )

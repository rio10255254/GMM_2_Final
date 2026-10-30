from __future__ import annotations

import argparse
import csv
import importlib.util
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
import torch.nn as nn
import torch.nn.functional as F
from torch.cuda.amp import GradScaler, autocast
from torch.utils.data import DataLoader, Dataset
PROJECT_ROOT = Path(__file__).resolve().parents[3]


DEFAULT_PACKAGE = Path(
    str(PROJECT_ROOT / 'Deliverables/Standalone_Models/V42_SoftLabelSNR_Standalone_20260709')
)
DEFAULT_OUTPUT = Path(
    str(PROJECT_ROOT / 'LabSystem_MOSR/Experiments/BaseUNet_Baseline_20260718/results')
)


@dataclass(frozen=True)
class TrainConfig:
    seed: int = 1261200
    epochs: int = 80
    crop_size: int = 256
    batch_size: int = 8
    train_repeats: int = 2
    learning_rate: float = 1.0e-3
    min_learning_rate: float = 2.0e-5
    weight_decay: float = 1.0e-5
    ssim_weight: float = 0.20
    base_channels: int = 48
    validate_every: int = 4
    patience_validations: int = 8
    fixed_psf: bool = False
    psf_path: str = ""
    psf_reg: float = 10.0
    psf_alpha: float = 0.10


def seed_everything(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)
    torch.backends.cudnn.benchmark = True


def read_gray_u8(path: Path) -> np.ndarray:
    data = np.fromfile(str(path), dtype=np.uint8)
    image = cv2.imdecode(data, cv2.IMREAD_UNCHANGED)
    if image is None:
        raise RuntimeError(f"Failed to read image: {path}")
    if image.ndim == 3:
        image = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    if image.dtype == np.uint16:
        image = np.rint(image.astype(np.float32) / 257.0).clip(0, 255).astype(np.uint8)
    elif image.dtype != np.uint8:
        image = np.rint(image.astype(np.float32)).clip(0, 255).astype(np.uint8)
    return image


class PairedPatchDataset(Dataset):
    def __init__(
        self,
        src_root: Path,
        lbl_root: Path,
        paths: list[Path],
        crop_size: int,
        repeats: int,
        augment: bool,
    ) -> None:
        self.src_root = src_root
        self.lbl_root = lbl_root
        self.paths = list(paths)
        self.crop_size = int(crop_size)
        self.repeats = max(1, int(repeats))
        self.augment = bool(augment)
        self.cache: dict[Path, tuple[np.ndarray, np.ndarray]] = {}

    def __len__(self) -> int:
        return len(self.paths) * self.repeats

    def _load(self, path: Path) -> tuple[np.ndarray, np.ndarray]:
        if path not in self.cache:
            rel = path.relative_to(self.src_root)
            label_path = self.lbl_root / rel
            if not label_path.exists():
                raise FileNotFoundError(f"Label is missing for {rel}")
            source = read_gray_u8(path)
            label = read_gray_u8(label_path)
            if source.shape != label.shape:
                raise RuntimeError(f"Shape mismatch for {rel}: {source.shape} vs {label.shape}")
            self.cache[path] = (source, label)
        return self.cache[path]

    def __getitem__(self, index: int) -> tuple[torch.Tensor, torch.Tensor]:
        source, label = self._load(self.paths[index % len(self.paths)])
        height, width = source.shape
        crop = self.crop_size
        if min(height, width) < crop:
            pad_y = max(0, crop - height)
            pad_x = max(0, crop - width)
            source = np.pad(source, ((0, pad_y), (0, pad_x)), mode="reflect")
            label = np.pad(label, ((0, pad_y), (0, pad_x)), mode="reflect")
            height, width = source.shape

        if self.augment:
            y0 = random.randint(0, height - crop)
            x0 = random.randint(0, width - crop)
        else:
            y0 = (height - crop) // 2
            x0 = (width - crop) // 2

        source = source[y0 : y0 + crop, x0 : x0 + crop]
        label = label[y0 : y0 + crop, x0 : x0 + crop]

        if self.augment:
            rotations = random.randrange(4)
            if rotations:
                source = np.rot90(source, rotations)
                label = np.rot90(label, rotations)
            if random.random() < 0.5:
                source = np.fliplr(source)
                label = np.fliplr(label)
            if random.random() < 0.5:
                source = np.flipud(source)
                label = np.flipud(label)

        source = np.ascontiguousarray(source, dtype=np.float32) / 255.0
        label = np.ascontiguousarray(label, dtype=np.float32) / 255.0
        return torch.from_numpy(source)[None], torch.from_numpy(label)[None]


class ConvBlock(nn.Module):
    def __init__(self, in_channels: int, out_channels: int, activate: bool = True) -> None:
        super().__init__()
        self.conv = nn.Conv2d(in_channels, out_channels, 3, padding=1)
        self.norm = nn.GroupNorm(min(8, out_channels), out_channels)
        self.activate = nn.SiLU() if activate else nn.Identity()

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.activate(self.norm(self.conv(x)))


class ResidualBlock(nn.Module):
    def __init__(self, channels: int) -> None:
        super().__init__()
        self.first = ConvBlock(channels, channels)
        self.second = ConvBlock(channels, channels, activate=False)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return F.silu(x + self.second(self.first(x)))


class NormalUpsample(nn.Module):
    def __init__(self, in_channels: int, out_channels: int) -> None:
        super().__init__()
        self.conv = nn.Conv2d(in_channels, out_channels, 3, padding=1)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.conv(F.interpolate(x, scale_factor=2, mode="bilinear", align_corners=False))


def build_fixed_psf_layer(
    package: Path,
    psf_path: Path,
    reg: float = 10.0,
    alpha: float = 0.10,
) -> nn.Module:
    model_path = package / "model_v42.py"
    spec = importlib.util.spec_from_file_location("v42_model_for_fixed_psf", model_path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    assert spec.loader is not None
    spec.loader.exec_module(module)
    layer = module.PSFDeconvPhysics(
        psf_path=str(psf_path),
        use_stack_mean=True,
        reg_init=float(reg),
        trainable_reg=False,
        alpha_init=float(alpha),
        alpha_min=float(alpha),
        alpha_max=float(alpha),
    )
    for parameter in layer.parameters():
        parameter.requires_grad_(False)
    layer.eval()
    return layer


class BaseUNet(nn.Module):
    """Parameter-matched U-like baseline without optical or metrology modules."""

    def __init__(self, base: int = 48, input_adapter: nn.Module | None = None) -> None:
        super().__init__()
        self.input_adapter = input_adapter if input_adapter is not None else nn.Identity()
        self.encoder1 = nn.Sequential(ConvBlock(1, base), ResidualBlock(base))
        self.down1 = nn.Conv2d(base, base, 3, stride=2, padding=1)
        self.encoder2 = nn.Sequential(ConvBlock(base, base * 2), ResidualBlock(base * 2))
        self.down2 = nn.Conv2d(base * 2, base * 2, 3, stride=2, padding=1)
        self.encoder3 = nn.Sequential(ConvBlock(base * 2, base * 4), ResidualBlock(base * 4))
        self.down3 = nn.Conv2d(base * 4, base * 4, 3, stride=2, padding=1)
        self.middle = nn.Sequential(
            ConvBlock(base * 4, base * 4),
            ResidualBlock(base * 4),
            ResidualBlock(base * 4),
        )
        self.up3 = NormalUpsample(base * 4, base * 2)
        self.decoder3 = nn.Sequential(ConvBlock(base * 6, base * 2), ResidualBlock(base * 2))
        self.up2 = NormalUpsample(base * 2, base)
        self.decoder2 = nn.Sequential(ConvBlock(base * 3, base), ResidualBlock(base))
        self.up1 = NormalUpsample(base, base)
        self.decoder1 = nn.Sequential(ConvBlock(base * 2, base), ResidualBlock(base))
        self.output = nn.Conv2d(base, 1, 1)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        x = self.input_adapter(x)
        feature1 = self.encoder1(x)
        feature2 = self.encoder2(self.down1(feature1))
        feature3 = self.encoder3(self.down2(feature2))
        middle = self.middle(self.down3(feature3))
        decoded3 = self.decoder3(torch.cat([self.up3(middle), feature3], dim=1))
        decoded2 = self.decoder2(torch.cat([self.up2(decoded3), feature2], dim=1))
        decoded1 = self.decoder1(torch.cat([self.up1(decoded2), feature1], dim=1))
        return torch.sigmoid(self.output(decoded1))


def gaussian_kernel(window: int, sigma: float, device: torch.device) -> torch.Tensor:
    coord = torch.arange(window, dtype=torch.float32, device=device) - (window - 1) / 2
    vector = torch.exp(-(coord**2) / (2 * sigma**2))
    vector /= vector.sum()
    return (vector[:, None] * vector[None, :])[None, None]


def ssim_value(prediction: torch.Tensor, target: torch.Tensor) -> torch.Tensor:
    kernel = gaussian_kernel(7, 1.5, prediction.device)
    mean_p = F.conv2d(prediction, kernel, padding=3)
    mean_t = F.conv2d(target, kernel, padding=3)
    var_p = F.conv2d(prediction * prediction, kernel, padding=3) - mean_p * mean_p
    var_t = F.conv2d(target * target, kernel, padding=3) - mean_t * mean_t
    covar = F.conv2d(prediction * target, kernel, padding=3) - mean_p * mean_t
    c1 = 0.01**2
    c2 = 0.03**2
    numerator = (2 * mean_p * mean_t + c1) * (2 * covar + c2)
    denominator = (mean_p.square() + mean_t.square() + c1) * (var_p + var_t + c2)
    return (numerator / (denominator + 1.0e-8)).mean()


def reconstruction_loss(
    prediction: torch.Tensor, target: torch.Tensor, ssim_weight: float
) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
    l1 = F.l1_loss(prediction, target)
    ssim = ssim_value(prediction, target)
    total = l1 + float(ssim_weight) * (1.0 - ssim)
    return total, l1, ssim


@torch.inference_mode()
def validate(
    model: nn.Module,
    source_paths: list[Path],
    source_root: Path,
    label_root: Path,
    device: torch.device,
    ssim_weight: float,
) -> dict[str, float]:
    model.eval()
    totals: list[float] = []
    l1s: list[float] = []
    rmses: list[float] = []
    ssims: list[float] = []
    for source_path in source_paths:
        rel = source_path.relative_to(source_root)
        source_np = read_gray_u8(source_path).astype(np.float32) / 255.0
        label_np = read_gray_u8(label_root / rel).astype(np.float32) / 255.0
        source = torch.from_numpy(source_np)[None, None].to(device)
        target = torch.from_numpy(label_np)[None, None].to(device)
        with autocast(enabled=device.type == "cuda"):
            prediction = model(source)
            total, l1, ssim = reconstruction_loss(prediction, target, ssim_weight)
        rmse = torch.sqrt(F.mse_loss(prediction.float(), target.float()))
        totals.append(float(total))
        l1s.append(float(l1))
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
    model: nn.Module,
    paths: list[Path],
    source_root: Path,
    label_root: Path,
    output_dir: Path,
    device: torch.device,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    model.eval()
    for index, source_path in enumerate(paths[:6]):
        rel = source_path.relative_to(source_root)
        source_np = read_gray_u8(source_path)
        label_np = read_gray_u8(label_root / rel)
        source = torch.from_numpy(source_np.astype(np.float32) / 255.0)[None, None].to(device)
        with autocast(enabled=device.type == "cuda"):
            prediction = model(source)
        result = np.clip(prediction[0, 0].float().cpu().numpy() * 255.0, 0, 255).astype(np.uint8)
        joined = np.concatenate([source_np, result, label_np], axis=1)
        success, encoded = cv2.imencode(".png", joined)
        if not success:
            raise RuntimeError("Could not encode validation example")
        encoded.tofile(str(output_dir / f"example_{index + 1:02d}_raw_base_label.png"))


def load_split(package: Path) -> tuple[Path, Path, list[Path], list[Path]]:
    data_root = package / "training_data"
    source_root = data_root / "src"
    label_root = data_root / "lbl"
    split_root = data_root / "splits" / "grouped_seed1337_val120"
    extensions = {".bmp", ".png", ".jpg", ".jpeg", ".tif", ".tiff"}
    all_paths = [
        Path(path)
        for path in sorted(
            str(p) for p in source_root.rglob("*") if p.is_file() and p.suffix.lower() in extensions
        )
    ]
    train_indices = np.load(split_root / "train_idx.npy").astype(np.int64)
    val_indices = np.load(split_root / "val_idx.npy").astype(np.int64)
    if len(train_indices) + len(val_indices) != len(all_paths):
        raise RuntimeError(
            f"Split/image count mismatch: train={len(train_indices)}, val={len(val_indices)}, "
            f"images={len(all_paths)}"
        )
    if max(np.max(train_indices), np.max(val_indices)) >= len(all_paths):
        raise RuntimeError("Split index exceeds the discovered source-image list")
    overlap = set(train_indices.tolist()) & set(val_indices.tolist())
    if overlap:
        raise RuntimeError(f"Train/validation overlap: {sorted(overlap)[:10]}")
    train_paths = [all_paths[int(index)] for index in train_indices]
    val_paths = [all_paths[int(index)] for index in val_indices]
    return source_root, label_root, train_paths, val_paths


def train(package: Path, output: Path, config: TrainConfig) -> None:
    output.mkdir(parents=True, exist_ok=True)
    seed_everything(config.seed)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    source_root, label_root, train_paths, val_paths = load_split(package)
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
        batch_size=config.batch_size,
        shuffle=True,
        num_workers=0,
        pin_memory=device.type == "cuda",
        drop_last=False,
        generator=generator,
    )
    input_adapter = None
    if config.fixed_psf:
        psf_path = Path(config.psf_path) if config.psf_path else package / "psf" / "PSF_fitted_2D_FOVstack.mat"
        input_adapter = build_fixed_psf_layer(
            package,
            psf_path,
            reg=config.psf_reg,
            alpha=config.psf_alpha,
        )
    model = BaseUNet(config.base_channels, input_adapter=input_adapter).to(device)
    parameter_count = sum(parameter.numel() for parameter in model.parameters())
    optimizer = torch.optim.AdamW(
        model.parameters(), lr=config.learning_rate, weight_decay=config.weight_decay
    )
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(
        optimizer, T_max=config.epochs, eta_min=config.min_learning_rate
    )
    scaler = GradScaler(enabled=device.type == "cuda")
    best_loss = math.inf
    best_epoch = 0
    stale_validations = 0
    history: list[dict[str, float | int]] = []
    start = time.time()

    metadata = {
        "purpose": "Parameter-matched base U-Net learning baseline",
        "model_definition": (
            "Same-width three-level U-like encoder-decoder with ordinary bilinear upsampling; "
            + ("the same frozen fixed PSF input prior; " if config.fixed_psf else "no PSF input prior; ")
            + "no anti-alias blur, position-anchor output, boundary adapter, quality gate, "
            "or metrology-specific losses."
        ),
        "loss_definition": "L1 + 0.20 * (1 - SSIM)",
        "package": str(package),
        "source_root": str(source_root),
        "label_root": str(label_root),
        "train_count": len(train_paths),
        "validation_count": len(val_paths),
        "parameter_count": parameter_count,
        "device": str(device),
        "gpu": torch.cuda.get_device_name(0) if device.type == "cuda" else None,
        "config": asdict(config),
    }
    (output / "run_manifest.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(metadata, ensure_ascii=False, indent=2), flush=True)

    for epoch in range(1, config.epochs + 1):
        model.train()
        epoch_losses: list[float] = []
        epoch_l1s: list[float] = []
        epoch_ssims: list[float] = []
        for source, target in loader:
            source = source.to(device, non_blocking=True)
            target = target.to(device, non_blocking=True)
            optimizer.zero_grad(set_to_none=True)
            with autocast(enabled=device.type == "cuda"):
                prediction = model(source)
                loss, l1, ssim = reconstruction_loss(prediction, target, config.ssim_weight)
            scaler.scale(loss).backward()
            scaler.step(optimizer)
            scaler.update()
            epoch_losses.append(float(loss.detach()))
            epoch_l1s.append(float(l1.detach()))
            epoch_ssims.append(float(ssim.detach()))
        scheduler.step()

        record: dict[str, float | int] = {
            "epoch": epoch,
            "lr": float(optimizer.param_groups[0]["lr"]),
            "train_loss": float(np.mean(epoch_losses)),
            "train_l1": float(np.mean(epoch_l1s)),
            "train_ssim": float(np.mean(epoch_ssims)),
        }
        should_validate = epoch == 1 or epoch % config.validate_every == 0 or epoch == config.epochs
        if should_validate:
            metrics = validate(
                model, val_paths, source_root, label_root, device, config.ssim_weight
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
                        "model_config": {
                            "base_channels": config.base_channels,
                            "fixed_psf": config.fixed_psf,
                            "psf_path": config.psf_path,
                            "psf_reg": config.psf_reg,
                            "psf_alpha": config.psf_alpha,
                        },
                        "parameter_count": parameter_count,
                        "training_config": asdict(config),
                    },
                    output / "best_base_unet.pth.tar",
                )
            else:
                stale_validations += 1
            print(
                f"epoch={epoch:03d} train={record['train_loss']:.6f} "
                f"val={metrics['loss']:.6f} l1={metrics['l1']:.6f} "
                f"ssim={metrics['ssim']:.5f} best={best_epoch:03d}",
                flush=True,
            )
        else:
            print(
                f"epoch={epoch:03d} train={record['train_loss']:.6f} "
                f"l1={record['train_l1']:.6f} ssim={record['train_ssim']:.5f}",
                flush=True,
            )
        history.append(record)

        if stale_validations >= config.patience_validations and epoch >= 32:
            print(f"Early stopping at epoch {epoch}; best epoch {best_epoch}", flush=True)
            break

    with (output / "training_history.csv").open("w", newline="", encoding="utf-8-sig") as handle:
        fieldnames = sorted({key for row in history for key in row})
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(history)

    checkpoint = torch.load(output / "best_base_unet.pth.tar", map_location=device)
    model.load_state_dict(checkpoint["state_dict"], strict=True)
    final_metrics = validate(
        model, val_paths, source_root, label_root, device, config.ssim_weight
    )
    write_validation_examples(
        model, val_paths, source_root, label_root, output / "validation_examples", device
    )
    summary = {
        **metadata,
        "best_epoch": int(checkpoint["epoch"]),
        "best_validation": final_metrics,
        "elapsed_seconds": time.time() - start,
        "checkpoint": str(output / "best_base_unet.pth.tar"),
    }
    (output / "training_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2), flush=True)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--package", type=Path, default=DEFAULT_PACKAGE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--epochs", type=int, default=80)
    parser.add_argument("--fixed-psf", action="store_true")
    parser.add_argument("--batch-size", type=int, default=8)
    parser.add_argument("--train-repeats", type=int, default=2)
    parser.add_argument("--validate-every", type=int, default=4)
    parser.add_argument("--patience-validations", type=int, default=8)
    return parser.parse_args()


if __name__ == "__main__":
    arguments = parse_args()
    configuration = TrainConfig(
        epochs=arguments.epochs,
        fixed_psf=arguments.fixed_psf,
        batch_size=arguments.batch_size,
        train_repeats=arguments.train_repeats,
        validate_every=arguments.validate_every,
        patience_validations=arguments.patience_validations,
    )
    train(arguments.package.resolve(), arguments.output.resolve(), configuration)

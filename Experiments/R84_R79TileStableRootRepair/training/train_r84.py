"""Targeted R84 recovery training on procedural pairs only."""
from __future__ import annotations

import argparse
import copy
import hashlib
import importlib.util
import json
import math
import random
import sys
import time
from pathlib import Path

import cv2
import numpy as np
import torch
import torch.nn.functional as F
from torch import nn
from torch.utils.data import DataLoader, Dataset


ROOT = Path(__file__).resolve().parents[1]
CONFIG = json.loads((ROOT / "config" / "experiment.json").read_text(encoding="utf-8"))
DEFAULT_SEED = ROOT / "weights" / "seed" / "r79e23_ema_seed.pth.tar"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_inference_module():
    path = ROOT / "inference" / "infer_r84.py"
    spec = importlib.util.spec_from_file_location("r84_inference_training", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def read_gray(path: Path) -> np.ndarray:
    image = cv2.imdecode(np.fromfile(path, dtype=np.uint8), cv2.IMREAD_GRAYSCALE)
    if image is None:
        raise OSError(path)
    return image


class ProceduralPairs(Dataset):
    def __init__(self, package: Path, rows: list[dict]):
        self.package = package
        self.rows = rows

    def __len__(self) -> int:
        return len(self.rows)

    def __getitem__(self, index: int):
        row = self.rows[index]
        source = read_gray(self.package / row["package_src"]).astype(np.float32) / 255.0
        label = read_gray(self.package / row["package_lbl"]).astype(np.float32) / 255.0
        return torch.from_numpy(source)[None], torch.from_numpy(label)[None]


def gradient_magnitude(image: torch.Tensor) -> torch.Tensor:
    kernel_x = image.new_tensor([[-1, 0, 1], [-2, 0, 2], [-1, 0, 1]]).view(1, 1, 3, 3)
    kernel_y = image.new_tensor([[-1, -2, -1], [0, 0, 0], [1, 2, 1]]).view(1, 1, 3, 3)
    gx = F.conv2d(image, kernel_x, padding=1)
    gy = F.conv2d(image, kernel_y, padding=1)
    return torch.sqrt(gx * gx + gy * gy + 1e-6)


def reconstruction_loss(
    prediction: torch.Tensor,
    target: torch.Tensor,
    *,
    edge_weight: float = 0.45,
    lap_weight: float = 0.02,
) -> tuple[torch.Tensor, dict[str, float]]:
    rec = F.l1_loss(prediction, target)
    edge = F.l1_loss(gradient_magnitude(prediction), gradient_magnitude(target))
    lap_kernel = prediction.new_tensor([[0, 1, 0], [1, -4, 1], [0, 1, 0]]).view(1, 1, 3, 3)
    lap = F.l1_loss(
        F.conv2d(prediction, lap_kernel, padding=1),
        F.conv2d(target, lap_kernel, padding=1),
    )
    total = rec + edge_weight * edge + lap_weight * lap
    return total, {"rec": float(rec.detach()), "edge": float(edge.detach()), "lap": float(lap.detach())}


def set_trainable(model: nn.Module, candidate: str) -> dict:
    for parameter in model.parameters():
        parameter.requires_grad_(False)
    allowed = []
    for name, module in model.named_modules():
        if module.__class__.__name__ == "PixelGroupNorm":
            for parameter in module.parameters(recurse=False):
                parameter.requires_grad_(True)
            allowed.append(name)
    if candidate == "norm_tail":
        patterns = ("boundary_adapter", "p1", "out")
        for name, parameter in model.named_parameters():
            if any(pattern in name for pattern in patterns):
                parameter.requires_grad_(True)
    elif candidate == "all_low_lr":
        for name, parameter in model.named_parameters():
            if not name.startswith("physics_layer.") and not name.startswith("weak_psf_block."):
                parameter.requires_grad_(True)
    else:
        raise ValueError(candidate)
    names = [name for name, parameter in model.named_parameters() if parameter.requires_grad]
    count = sum(parameter.numel() for parameter in model.parameters() if parameter.requires_grad)
    if not names:
        raise RuntimeError("No R84 parameters were selected for training.")
    return {"candidate": candidate, "trainable_parameter_count": int(count), "trainable_names": names, "local_norm_modules": allowed}


def seed_everything(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)
    torch.backends.cudnn.benchmark = False
    torch.backends.cudnn.deterministic = True


def update_ema(ema: nn.Module, model: nn.Module, decay: float) -> None:
    with torch.no_grad():
        model_params = dict(model.named_parameters())
        for name, ema_parameter in ema.named_parameters():
            source = model_params[name]
            if source.requires_grad:
                ema_parameter.mul_(decay).add_(source, alpha=1.0 - decay)
            else:
                ema_parameter.copy_(source)
        model_buffers = dict(model.named_buffers())
        for name, ema_buffer in ema.named_buffers():
            ema_buffer.copy_(model_buffers[name])


def evaluate(
    model: nn.Module,
    loader: DataLoader,
    device: str,
    *,
    edge_weight: float = 0.45,
    lap_weight: float = 0.02,
) -> dict[str, float]:
    model.eval()
    totals = {"total": 0.0, "rec": 0.0, "edge": 0.0, "lap": 0.0}
    count = 0
    with torch.no_grad():
        for source, target in loader:
            source = source.to(device)
            target = target.to(device)
            prediction = model(source).clamp(0.0, 1.0)
            total, parts = reconstruction_loss(
                prediction, target, edge_weight=edge_weight, lap_weight=lap_weight
            )
            batch = int(source.shape[0])
            totals["total"] += float(total) * batch
            for key in ("rec", "edge", "lap"):
                totals[key] += parts[key] * batch
            count += batch
    return {key: value / max(count, 1) for key, value in totals.items()}


def checkpoint_payload(model: nn.Module, ema: nn.Module, optimizer, epoch: int, metadata: dict) -> dict:
    return {
        "epoch": int(epoch),
        "state_dict": {name: value.detach().cpu() for name, value in model.state_dict().items()},
        "ema_state_dict": {name: value.detach().cpu() for name, value in ema.state_dict().items()},
        "optimizer": optimizer.state_dict(),
        "r84_metadata": metadata,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="R84 targeted procedural recovery training")
    parser.add_argument("--profile", choices=("pilot", "formal"), default="pilot")
    parser.add_argument("--candidate", choices=("norm_tail", "all_low_lr"), default="norm_tail")
    parser.add_argument("--epochs", type=int, default=5)
    parser.add_argument("--lr", type=float, default=None)
    parser.add_argument("--edge-weight", type=float, default=0.45)
    parser.add_argument("--lap-weight", type=float, default=0.02)
    parser.add_argument("--batch-size", type=int, default=8)
    parser.add_argument("--val-batch-size", type=int, default=4)
    parser.add_argument("--num-workers", type=int, default=4)
    parser.add_argument("--device", default="cuda:0")
    parser.add_argument("--seed", type=int, default=840917)
    parser.add_argument("--checkpoint", type=Path, default=DEFAULT_SEED)
    parser.add_argument("--run-name", default="")
    parser.add_argument("--max-train-batches", type=int, default=0)
    args = parser.parse_args(argv)

    seed_everything(args.seed)
    package = Path(CONFIG["data"][f"{args.profile}_package"])
    expected_manifest_hash = CONFIG["data"][f"{args.profile}_manifest_sha256"]
    manifest_path = package / "manifest.json"
    if sha256(manifest_path) != expected_manifest_hash:
        raise RuntimeError(f"{args.profile} manifest hash changed")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    train_rows = [row for row in manifest["pairs"] if row["split"] == "train"]
    validation_rows = [row for row in manifest["pairs"] if row["split"] == "validation"]
    if not train_rows or not validation_rows:
        raise RuntimeError("Training or validation split is empty.")

    generator = torch.Generator().manual_seed(args.seed)
    train_loader = DataLoader(
        ProceduralPairs(package, train_rows), batch_size=args.batch_size, shuffle=True,
        num_workers=args.num_workers, pin_memory=True, generator=generator, persistent_workers=False,
    )
    validation_loader = DataLoader(
        ProceduralPairs(package, validation_rows), batch_size=args.val_batch_size, shuffle=False,
        num_workers=args.num_workers, pin_memory=True, persistent_workers=False,
    )

    module = load_inference_module()
    checkpoint = args.checkpoint.resolve()
    if args.profile == "pilot" and sha256(checkpoint) != CONFIG["parent"]["checkpoint_sha256"]:
        raise RuntimeError("Pilot must start from the exact locked R79 seed.")
    model, state_key = module.build_model(checkpoint, args.device, tile_stable=True, use_ema=True)
    audit = set_trainable(model, args.candidate)
    ema = copy.deepcopy(model).to(args.device).eval()
    for parameter in ema.parameters():
        parameter.requires_grad_(False)
    learning_rate = args.lr if args.lr is not None else CONFIG["training"]["learning_rates"][args.candidate]
    optimizer = torch.optim.AdamW(
        [parameter for parameter in model.parameters() if parameter.requires_grad],
        lr=float(learning_rate), weight_decay=0.0,
    )

    timestamp = time.strftime("%Y%m%d_%H%M%S")
    suffix = args.run_name or f"{args.candidate}_{args.profile}_seed{args.seed}_{timestamp}"
    run_dir = ROOT / "runs" / suffix
    weight_dir = ROOT / "weights" / args.profile / args.candidate / suffix
    run_dir.mkdir(parents=True, exist_ok=False)
    weight_dir.mkdir(parents=True, exist_ok=False)
    metadata = {
        "experiment_id": CONFIG["experiment_id"], "profile": args.profile,
        "candidate": args.candidate, "seed": args.seed, "source_checkpoint": str(checkpoint),
        "source_checkpoint_sha256": sha256(checkpoint), "source_state_key": state_key,
        "dataset_manifest_sha256": expected_manifest_hash, "real_training_pixels": False,
        "teacher_or_pseudo_labels": False, "architecture": "local_pixel_group_norm_global_paths_bypassed",
        "trainable_audit": audit, "learning_rate": learning_rate,
        "loss_weights": {"rec": 1.0, "edge": args.edge_weight, "lap": args.lap_weight},
    }
    (run_dir / "run_meta.json").write_text(json.dumps(metadata, indent=2, ensure_ascii=False), encoding="utf-8")

    history = []
    best_value = math.inf
    best_epoch = 0
    for epoch in range(1, args.epochs + 1):
        model.train()
        sums = {"total": 0.0, "rec": 0.0, "edge": 0.0, "lap": 0.0}
        seen = 0
        for batch_index, (source, target) in enumerate(train_loader, start=1):
            source = source.to(args.device, non_blocking=True)
            target = target.to(args.device, non_blocking=True)
            optimizer.zero_grad(set_to_none=True)
            prediction = model(source).clamp(0.0, 1.0)
            total, parts = reconstruction_loss(
                prediction, target, edge_weight=args.edge_weight, lap_weight=args.lap_weight
            )
            total.backward()
            torch.nn.utils.clip_grad_norm_([p for p in model.parameters() if p.requires_grad], 1.0)
            optimizer.step()
            update_ema(ema, model, 0.995)
            batch = int(source.shape[0])
            sums["total"] += float(total.detach()) * batch
            for key in ("rec", "edge", "lap"):
                sums[key] += parts[key] * batch
            seen += batch
            if args.max_train_batches and batch_index >= args.max_train_batches:
                break
        train_metrics = {key: value / max(seen, 1) for key, value in sums.items()}
        validation_metrics = evaluate(
            ema,
            validation_loader,
            args.device,
            edge_weight=args.edge_weight,
            lap_weight=args.lap_weight,
        )
        row = {"epoch": epoch, "train": train_metrics, "validation": validation_metrics}
        history.append(row)
        print(json.dumps(row), flush=True)
        payload = checkpoint_payload(model, ema, optimizer, epoch, metadata)
        torch.save(payload, weight_dir / "latest.pth.tar")
        if args.profile == "formal" and (epoch % 5 == 0 or epoch == args.epochs):
            torch.save(payload, weight_dir / f"epoch_{epoch:03d}.pth.tar")
        if validation_metrics["total"] < best_value:
            best_value = validation_metrics["total"]
            best_epoch = epoch
            torch.save(payload, weight_dir / "best.pth.tar")
        (run_dir / "history.json").write_text(json.dumps(history, indent=2), encoding="utf-8")

    summary = {
        **metadata, "status": "complete", "epochs": args.epochs,
        "best_epoch": best_epoch, "best_validation_total": best_value,
        "weights_dir": str(weight_dir), "history": history,
    }
    (run_dir / "run_summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    (weight_dir / "selection_metrics.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({"run_dir": str(run_dir), "weights_dir": str(weight_dir), "best_epoch": best_epoch, "best_validation_total": best_value}, indent=2), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

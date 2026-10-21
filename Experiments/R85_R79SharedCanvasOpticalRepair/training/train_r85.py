"""R85 procedural adaptation with shared optical input and R79 behavior preservation."""
from __future__ import annotations

import argparse
import copy
import hashlib
import importlib.util
import json
import math
import random
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


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_inference_module():
    path = ROOT / "inference" / "infer_r85.py"
    spec = importlib.util.spec_from_file_location("r85_training_inference", path)
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


def pad_canonical(tensor: torch.Tensor, size: int = 512) -> torch.Tensor:
    height, width = tensor.shape[-2:]
    pad_bottom = (-height) % size
    pad_right = (-width) % size
    first_bottom = min(pad_bottom, height - 1)
    first_right = min(pad_right, width - 1)
    padded = F.pad(tensor, (0, first_right, 0, first_bottom), mode="reflect")
    remaining_bottom = pad_bottom - first_bottom
    remaining_right = pad_right - first_right
    if remaining_bottom or remaining_right:
        padded = F.pad(padded, (0, remaining_right, 0, remaining_bottom), mode="reflect")
    return padded


def gradient_magnitude(image: torch.Tensor) -> torch.Tensor:
    kernel_x = image.new_tensor([[-1, 0, 1], [-2, 0, 2], [-1, 0, 1]]).view(1, 1, 3, 3)
    kernel_y = image.new_tensor([[-1, -2, -1], [0, 0, 0], [1, 2, 1]]).view(1, 1, 3, 3)
    gx = F.conv2d(image, kernel_x, padding=1)
    gy = F.conv2d(image, kernel_y, padding=1)
    return torch.sqrt(gx * gx + gy * gy + 1e-6)


def losses(prediction: torch.Tensor, target: torch.Tensor, teacher: torch.Tensor) -> tuple[torch.Tensor, dict[str, float]]:
    rec = F.l1_loss(prediction, target)
    edge = F.l1_loss(gradient_magnitude(prediction), gradient_magnitude(target))
    lap_kernel = prediction.new_tensor([[0, 1, 0], [1, -4, 1], [0, 1, 0]]).view(1, 1, 3, 3)
    lap = F.l1_loss(F.conv2d(prediction, lap_kernel, padding=1), F.conv2d(target, lap_kernel, padding=1))
    teacher_rec = F.l1_loss(prediction, teacher)
    teacher_edge = F.l1_loss(gradient_magnitude(prediction), gradient_magnitude(teacher))
    analytic = rec + 0.9 * edge + 0.02 * lap
    preservation = teacher_rec + 0.5 * teacher_edge
    total = analytic + preservation
    return total, {
        "analytic_rec": float(rec.detach()),
        "analytic_edge": float(edge.detach()),
        "analytic_lap": float(lap.detach()),
        "teacher_rec": float(teacher_rec.detach()),
        "teacher_edge": float(teacher_edge.detach()),
    }


def set_trainable(model: nn.Module) -> dict:
    names = []
    for name, parameter in model.named_parameters():
        allowed = not name.startswith("physics_layer.") and not name.startswith("weak_psf_block.")
        parameter.requires_grad_(allowed)
        if allowed:
            names.append(name)
    count = sum(parameter.numel() for parameter in model.parameters() if parameter.requires_grad)
    return {"trainable_parameter_count": int(count), "trainable_names": names}


def seed_everything(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)
    torch.backends.cudnn.benchmark = False
    torch.backends.cudnn.deterministic = True


def update_ema(ema: nn.Module, model: nn.Module, decay: float = 0.995) -> None:
    with torch.no_grad():
        model_parameters = dict(model.named_parameters())
        for name, target in ema.named_parameters():
            source = model_parameters[name]
            if source.requires_grad:
                target.mul_(decay).add_(source, alpha=1.0 - decay)
            else:
                target.copy_(source)
        buffers = dict(model.named_buffers())
        for name, target in ema.named_buffers():
            target.copy_(buffers[name])


def forward_triplet(student: nn.Module, teacher: nn.Module, source: torch.Tensor, target: torch.Tensor):
    source_canvas = pad_canonical(source)
    target_canvas = pad_canonical(target)
    with torch.no_grad(), torch.cuda.amp.autocast(enabled=False):
        conditioned = student.physics_layer(source_canvas).float()
        teacher_output = teacher(source_canvas).float().clamp(0.0, 1.0)
    prediction = student(conditioned).float().clamp(0.0, 1.0)
    return prediction, target_canvas, teacher_output


def evaluate(student: nn.Module, teacher: nn.Module, loader: DataLoader, device: str, max_batches: int = 0) -> dict:
    student.eval()
    teacher.eval()
    totals = {key: 0.0 for key in ["total", "analytic_rec", "analytic_edge", "analytic_lap", "teacher_rec", "teacher_edge"]}
    seen = 0
    with torch.no_grad():
        for batch_index, (source, target) in enumerate(loader, start=1):
            source = source.to(device, non_blocking=True)
            target = target.to(device, non_blocking=True)
            prediction, target_canvas, teacher_output = forward_triplet(student, teacher, source, target)
            total, parts = losses(prediction, target_canvas, teacher_output)
            batch = int(source.shape[0])
            totals["total"] += float(total) * batch
            for key, value in parts.items():
                totals[key] += value * batch
            seen += batch
            if max_batches and batch_index >= max_batches:
                break
    return {key: value / max(seen, 1) for key, value in totals.items()}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Train the locked R85 adaptation")
    parser.add_argument("--epochs", type=int, default=10)
    parser.add_argument("--batch-size", type=int, default=4)
    parser.add_argument("--val-batch-size", type=int, default=4)
    parser.add_argument("--num-workers", type=int, default=6)
    parser.add_argument("--device", default="cuda:0")
    parser.add_argument("--lr", type=float, default=0.000001)
    parser.add_argument("--seed", type=int, default=850917)
    parser.add_argument("--run-name", default="formal_shared_canvas_e10")
    parser.add_argument("--max-train-batches", type=int, default=0)
    parser.add_argument("--max-val-batches", type=int, default=0)
    args = parser.parse_args(argv)
    seed_everything(args.seed)

    package = Path(CONFIG["data"]["formal_package"])
    manifest_path = package / "manifest.json"
    if sha256(manifest_path) != CONFIG["data"]["formal_manifest_sha256"]:
        raise RuntimeError("Formal procedural manifest changed.")
    subset_path = ROOT / CONFIG["data"]["training_subset_lock"]
    if sha256(subset_path) != CONFIG["data"]["training_subset_lock_sha256"]:
        raise RuntimeError("Locked training subset changed.")
    subset = json.loads(subset_path.read_text(encoding="utf-8"))
    selected_ids = set(subset["pair_ids"])
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    training_rows = [row for row in manifest["pairs"] if row["pair_id"] in selected_ids]
    validation_rows = [row for row in manifest["pairs"] if row["split"] == "validation"]
    if len(training_rows) != 1024 or len(validation_rows) != 512:
        raise RuntimeError(f"Unexpected train/validation counts: {len(training_rows)}/{len(validation_rows)}")

    generator = torch.Generator().manual_seed(args.seed)
    train_loader = DataLoader(
        ProceduralPairs(package, training_rows), batch_size=args.batch_size, shuffle=True,
        num_workers=args.num_workers, pin_memory=True, generator=generator, persistent_workers=False,
    )
    validation_loader = DataLoader(
        ProceduralPairs(package, validation_rows), batch_size=args.val_batch_size, shuffle=False,
        num_workers=args.num_workers, pin_memory=True, persistent_workers=False,
    )

    inference = load_inference_module()
    parent_path = ROOT / CONFIG["parent"]["checkpoint"]
    teacher_path = ROOT / CONFIG["teacher"]["checkpoint"]
    if sha256(parent_path) != CONFIG["parent"]["checkpoint_sha256"] or sha256(teacher_path) != CONFIG["teacher"]["checkpoint_sha256"]:
        raise RuntimeError("Parent or teacher checkpoint changed.")
    student, parent_key = inference.build_model(parent_path, args.device, tile_stable=True, use_ema=True)
    teacher, teacher_key = inference.build_model(teacher_path, args.device, tile_stable=False, use_ema=True)
    teacher.eval()
    for parameter in teacher.parameters():
        parameter.requires_grad_(False)
    trainable = set_trainable(student)
    ema = copy.deepcopy(student).to(args.device).eval()
    for parameter in ema.parameters():
        parameter.requires_grad_(False)
    optimizer = torch.optim.AdamW(
        [parameter for parameter in student.parameters() if parameter.requires_grad], lr=args.lr, weight_decay=0.0
    )

    run_dir = ROOT / "runs" / args.run_name
    weights_dir = ROOT / "weights" / "formal" / args.run_name
    run_dir.mkdir(parents=True, exist_ok=False)
    weights_dir.mkdir(parents=True, exist_ok=False)
    metadata = {
        "experiment_id": CONFIG["experiment_id"],
        "source_checkpoint": str(parent_path),
        "source_checkpoint_sha256": sha256(parent_path),
        "source_state_key": parent_key,
        "teacher_checkpoint": str(teacher_path),
        "teacher_checkpoint_sha256": sha256(teacher_path),
        "teacher_state_key": teacher_key,
        "training_subset_lock_sha256": sha256(subset_path),
        "training_pairs": len(training_rows),
        "validation_pairs": len(validation_rows),
        "real_or_sem_training_pixels": False,
        "analytic_label_is_primary": True,
        "teacher_role": "auxiliary behavior preservation on procedural inputs",
        "shared_canvas_preconditioner_strength": 1.0,
        "learning_rate": args.lr,
        "trainable_audit": trainable,
    }
    (run_dir / "run_meta.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")

    history = []
    best_value = math.inf
    best_epoch = 0
    for epoch in range(1, args.epochs + 1):
        student.train()
        sums = {key: 0.0 for key in ["total", "analytic_rec", "analytic_edge", "analytic_lap", "teacher_rec", "teacher_edge"]}
        seen = 0
        for batch_index, (source, target) in enumerate(train_loader, start=1):
            source = source.to(args.device, non_blocking=True)
            target = target.to(args.device, non_blocking=True)
            optimizer.zero_grad(set_to_none=True)
            prediction, target_canvas, teacher_output = forward_triplet(student, teacher, source, target)
            total, parts = losses(prediction, target_canvas, teacher_output)
            total.backward()
            torch.nn.utils.clip_grad_norm_([p for p in student.parameters() if p.requires_grad], 1.0)
            optimizer.step()
            update_ema(ema, student)
            batch = int(source.shape[0])
            sums["total"] += float(total.detach()) * batch
            for key, value in parts.items():
                sums[key] += value * batch
            seen += batch
            if args.max_train_batches and batch_index >= args.max_train_batches:
                break
        train_metrics = {key: value / max(seen, 1) for key, value in sums.items()}
        validation_metrics = evaluate(ema, teacher, validation_loader, args.device, args.max_val_batches)
        row = {"epoch": epoch, "train": train_metrics, "validation": validation_metrics}
        history.append(row)
        print(json.dumps(row), flush=True)
        payload = {
            "epoch": epoch,
            "state_dict": {name: value.detach().cpu() for name, value in student.state_dict().items()},
            "ema_state_dict": {name: value.detach().cpu() for name, value in ema.state_dict().items()},
            "optimizer": optimizer.state_dict(),
            "r85_metadata": metadata,
        }
        torch.save(payload, weights_dir / "latest.pth.tar")
        if epoch in CONFIG["training"]["eligible_epochs"]:
            torch.save(payload, weights_dir / f"epoch_{epoch:03d}.pth.tar")
        if validation_metrics["total"] < best_value:
            best_value = validation_metrics["total"]
            best_epoch = epoch
            torch.save(payload, weights_dir / "best.pth.tar")
        (run_dir / "history.json").write_text(json.dumps(history, indent=2), encoding="utf-8")

    summary = {**metadata, "status": "complete", "epochs": args.epochs, "best_epoch": best_epoch, "best_validation_total": best_value, "history": history}
    (run_dir / "run_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps({"run_dir": str(run_dir), "weights_dir": str(weights_dir), "best_epoch": best_epoch}, indent=2), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

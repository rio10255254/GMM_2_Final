"""R87 one-run scratch trainer.

There is intentionally no checkpoint or resume argument.  Every invocation
creates a new random model, optimizer, EMA state, and output directory.
"""
from __future__ import annotations

import argparse
import copy
import csv
import hashlib
import importlib.util
import json
import math
import os
import random
import sys
import time
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import cv2
import numpy as np
import torch
from torch import nn
import torch.nn.functional as F
from torch.utils.data import DataLoader, Dataset


EXPERIMENT_DIR = Path(__file__).resolve().parents[1]
CONFIG_PATH = EXPERIMENT_DIR / "config" / "experiment.json"
CONFIG = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
MODEL_PATH = EXPERIMENT_DIR / "model" / "r87_model.py"
DATASET_DIR = EXPERIMENT_DIR / "data" / CONFIG["dataset"]["package_name"]
RUNS_DIR = EXPERIMENT_DIR / "runs"
WEIGHTS_DIR = EXPERIMENT_DIR / "weights" / "formal" / f"seed_{CONFIG['training']['seed']}"
RESULTS_DIR = EXPERIMENT_DIR / "results"


@dataclass
class RuntimeConfig:
    MODEL_NAME: str = "TileNativeMOSR_R87_scratch_seed870031"


CFG = RuntimeConfig()
MODEL_NAME_BASE = CFG.MODEL_NAME


def json_dump(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    os.replace(temporary, path)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def state_sha256(model: nn.Module) -> str:
    digest = hashlib.sha256()
    for name, value in sorted(model.state_dict().items()):
        digest.update(name.encode("utf-8"))
        digest.update(value.detach().cpu().contiguous().numpy().tobytes())
    return digest.hexdigest()


def load_model_module():
    spec = importlib.util.spec_from_file_location("r87_model_runtime", MODEL_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load model module: {MODEL_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def stage_for_epoch(epoch: int) -> dict[str, int]:
    for stage in CONFIG["training"]["stages"]:
        if int(stage["epoch_start"]) <= epoch <= int(stage["epoch_end"]):
            return {key: int(value) for key, value in stage.items()}
    raise ValueError(f"No stage for epoch {epoch}")


class ScenePairDataset(Dataset):
    def __init__(
        self,
        manifest: dict[str, Any],
        split: str,
        patch_size: int,
        core_size: int,
        epoch: int,
        *,
        include_both_renderings: bool,
    ):
        grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for record in manifest["records"]:
            if record["split"] == split:
                grouped[record["scene_id"]].append(record)
        self.scenes = []
        for scene_id, rows in sorted(grouped.items()):
            rows = sorted(rows, key=lambda row: int(row["rendering"]))
            if len(rows) != 2:
                raise RuntimeError(f"Scene does not have two renderings: {scene_id}")
            self.scenes.append(rows)
        self.patch_size = int(patch_size)
        self.core_size = int(core_size)
        self.halo = (self.patch_size - self.core_size) // 2
        self.epoch = int(epoch)
        self.include_both = bool(include_both_renderings)
        self.canvas_size = int(manifest["canvas_size"])
        if self.patch_size > self.canvas_size or (self.patch_size - self.core_size) % 2:
            raise ValueError("Invalid patch/core sizes")
        self.index_map = (
            [(scene_index, rendering) for scene_index in range(len(self.scenes)) for rendering in range(2)]
            if self.include_both else list(range(len(self.scenes)))
        )

    def __len__(self) -> int:
        return len(self.index_map)

    @staticmethod
    def _aligned_random(rng: np.random.Generator, maximum: int) -> int:
        values = maximum // 8 + 1
        return int(rng.integers(0, values)) * 8

    def _origins(self, scene_index: int, rendering: int) -> np.ndarray:
        seed = (
            int(CONFIG["dataset"]["master_seed"]) * 1000003
            + scene_index * 10007
            + rendering * 1009
            + self.epoch * 7919
            + self.patch_size * 17
        )
        rng = np.random.default_rng(seed)
        maximum = self.canvas_size - self.patch_size
        y0 = self._aligned_random(rng, maximum)
        x0 = self._aligned_random(rng, maximum)
        maximum_offset = max(8, min(self.core_size // 2, maximum))
        choices = np.arange(8, maximum_offset + 1, 8, dtype=np.int32)
        for _ in range(32):
            dy = int(rng.choice(choices)) * int(rng.choice([-1, 1]))
            dx = int(rng.choice(choices)) * int(rng.choice([-1, 1]))
            y1 = int(np.clip(y0 + dy, 0, maximum) // 8 * 8)
            x1 = int(np.clip(x0 + dx, 0, maximum) // 8 * 8)
            if y1 != y0 or x1 != x0:
                overlap_h = self.core_size - abs(y1 - y0)
                overlap_w = self.core_size - abs(x1 - x0)
                if overlap_h >= self.core_size // 2 and overlap_w >= self.core_size // 2:
                    return np.asarray([[y0, x0], [y1, x1]], dtype=np.int64)
        y1 = min(maximum, y0 + min(64, maximum - y0)) // 8 * 8
        if y1 == y0:
            y1 = max(0, y0 - min(64, y0)) // 8 * 8
        return np.asarray([[y0, x0], [y1, x0]], dtype=np.int64)

    def __getitem__(self, index: int):
        if self.include_both:
            scene_index, rendering = self.index_map[index]
        else:
            scene_index = int(self.index_map[index])
            rendering = (self.epoch + scene_index) % 2
        record = self.scenes[scene_index][rendering]
        source = np.load(DATASET_DIR / record["source"], mmap_mode="r", allow_pickle=False)
        target = np.load(DATASET_DIR / record["target"], mmap_mode="r", allow_pickle=False)
        origins = self._origins(scene_index, rendering)
        source_views = []
        target_views = []
        for y0, x0 in origins.tolist():
            source_views.append(np.asarray(source[y0:y0 + self.patch_size, x0:x0 + self.patch_size]).copy())
            target_views.append(np.asarray(target[y0:y0 + self.patch_size, x0:x0 + self.patch_size]).copy())
        source_tensor = torch.from_numpy(np.stack(source_views)).unsqueeze(1).float().div_(255.0)
        target_tensor = torch.from_numpy(np.stack(target_views)).unsqueeze(1).float().div_(255.0)
        identity = record["degradation_family"] == "identity_and_near_identity"
        return source_tensor, target_tensor, torch.from_numpy(origins), torch.tensor(identity), record["role"]


def gradient_magnitude(x: torch.Tensor) -> torch.Tensor:
    kx = torch.tensor([[-1, 0, 1], [-2, 0, 2], [-1, 0, 1]], device=x.device, dtype=x.dtype).view(1, 1, 3, 3) / 8.0
    ky = kx.transpose(-1, -2)
    mode = "reflect" if x.shape[-2] > 1 and x.shape[-1] > 1 else "replicate"
    padded = F.pad(x, (1, 1, 1, 1), mode=mode)
    gx = F.conv2d(padded, kx)
    gy = F.conv2d(padded, ky)
    return torch.sqrt(gx.square() + gy.square() + 1e-8)


def laplacian(x: torch.Tensor) -> torch.Tensor:
    kernel = torch.tensor([[0, 1, 0], [1, -4, 1], [0, 1, 0]], device=x.device, dtype=x.dtype).view(1, 1, 3, 3)
    mode = "reflect" if x.shape[-2] > 1 and x.shape[-1] > 1 else "replicate"
    return F.conv2d(F.pad(x, (1, 1, 1, 1), mode=mode), kernel)


def loss_components(
    prediction: torch.Tensor,
    target: torch.Tensor,
    source: torch.Tensor,
    origins: torch.Tensor,
    identity: torch.Tensor,
    patch_size: int,
    core_size: int,
) -> tuple[torch.Tensor, dict[str, torch.Tensor]]:
    weights = CONFIG["training"]["loss_weights"]
    batch = int(origins.shape[0])
    if prediction.shape[0] != batch * 2:
        raise RuntimeError(f"Expected two views per scene, got prediction={prediction.shape[0]}, scenes={batch}")
    prediction = prediction.reshape(batch, 2, 1, patch_size, patch_size).float()
    target = target.reshape(batch, 2, 1, patch_size, patch_size).float()
    source = source.reshape(batch, 2, 1, patch_size, patch_size).float()
    halo = (patch_size - core_size) // 2
    core_slice = slice(halo, halo + core_size)
    pred_core = prediction[..., core_slice, core_slice].reshape(batch * 2, 1, core_size, core_size)
    target_core = target[..., core_slice, core_slice].reshape(batch * 2, 1, core_size, core_size)
    source_core = source[..., core_slice, core_slice].reshape(batch * 2, 1, core_size, core_size)

    reconstruction = F.smooth_l1_loss(pred_core, target_core, beta=0.01)
    pred_grad = gradient_magnitude(pred_core)
    target_grad = gradient_magnitude(target_core)
    edge = F.l1_loss(pred_grad, target_grad)
    lap = F.l1_loss(laplacian(pred_core), laplacian(target_core))
    pred_edge = pred_grad / (pred_grad.amax(dim=(-2, -1), keepdim=True) + 1e-6)
    target_edge = target_grad / (target_grad.amax(dim=(-2, -1), keepdim=True) + 1e-6)
    contour = 1.0 - ((2.0 * (pred_edge * target_edge).sum(dim=(-2, -1)) + 1e-5) /
                     (pred_edge.sum(dim=(-2, -1)) + target_edge.sum(dim=(-2, -1)) + 1e-5)).mean()

    consistency_terms = []
    origins_cpu = origins.detach().cpu().numpy()
    for item in range(batch):
        y0a, x0a = origins_cpu[item, 0]
        y0b, x0b = origins_cpu[item, 1]
        a_y0, a_x0 = int(y0a + halo), int(x0a + halo)
        b_y0, b_x0 = int(y0b + halo), int(x0b + halo)
        iy0, ix0 = max(a_y0, b_y0), max(a_x0, b_x0)
        iy1, ix1 = min(a_y0 + core_size, b_y0 + core_size), min(a_x0 + core_size, b_x0 + core_size)
        if iy1 <= iy0 or ix1 <= ix0:
            raise RuntimeError("Paired cores do not overlap")
        a = prediction[item, 0, :, iy0 - int(y0a):iy1 - int(y0a), ix0 - int(x0a):ix1 - int(x0a)]
        b = prediction[item, 1, :, iy0 - int(y0b):iy1 - int(y0b), ix0 - int(x0b):ix1 - int(x0b)]
        consistency_terms.append(F.l1_loss(a, b))
    consistency = torch.stack(consistency_terms).mean()

    identity_mask = identity.to(pred_core.device).bool().repeat_interleave(2)
    identity_loss = (
        F.l1_loss(pred_core[identity_mask], source_core[identity_mask])
        if bool(identity_mask.any()) else pred_core.new_zeros(())
    )
    total = (
        float(weights["reconstruction"]) * reconstruction
        + float(weights["edge"]) * edge
        + float(weights["laplacian"]) * lap
        + float(weights["soft_contour"]) * contour
        + float(weights["paired_view_consistency"]) * consistency
        + float(weights["identity_guard"]) * identity_loss
    )
    return total, {
        "total": total.detach(),
        "reconstruction": reconstruction.detach(),
        "edge": edge.detach(),
        "laplacian": lap.detach(),
        "soft_contour": contour.detach(),
        "consistency": consistency.detach(),
        "identity": identity_loss.detach(),
    }


@torch.no_grad()
def update_ema(model: nn.Module, ema: nn.Module, decay: float = 0.999) -> None:
    model_state = model.state_dict()
    for name, value in ema.state_dict().items():
        source = model_state[name].detach()
        if value.dtype.is_floating_point:
            value.mul_(decay).add_(source, alpha=1.0 - decay)
        else:
            value.copy_(source)


@torch.no_grad()
def evaluate(
    model: nn.Module,
    loader: DataLoader,
    device: torch.device,
    patch_size: int,
    core_size: int,
    amp_enabled: bool,
    max_batches: int = 0,
) -> dict[str, float]:
    model.eval()
    sums: defaultdict[str, float] = defaultdict(float)
    count = 0
    for batch_index, (source, target, origins, identity, _roles) in enumerate(loader, start=1):
        batch = int(source.shape[0])
        source = source.to(device, non_blocking=True)
        target = target.to(device, non_blocking=True)
        flat_source = source.reshape(batch * 2, 1, patch_size, patch_size)
        flat_target = target.reshape(batch * 2, 1, patch_size, patch_size)
        with torch.autocast(device_type="cuda", dtype=torch.bfloat16, enabled=amp_enabled):
            prediction = model(flat_source)
        _, parts = loss_components(prediction, flat_target, flat_source, origins, identity, patch_size, core_size)
        for name, value in parts.items():
            sums[name] += float(value) * batch
        count += batch
        if max_batches and batch_index >= max_batches:
            break
    return {name: value / max(count, 1) for name, value in sums.items()}


def image_to_float(image: np.ndarray) -> np.ndarray:
    if image.dtype == np.uint16:
        return image.astype(np.float32) / 65535.0
    if image.dtype == np.uint8:
        return image.astype(np.float32) / 255.0
    array = image.astype(np.float32)
    maximum = float(np.max(array))
    return array / maximum if maximum > 1.0 else array


@torch.no_grad()
def tiled_predict(model: nn.Module, image: np.ndarray, device: torch.device, patch: int = 896, core: int = 512, amp_enabled: bool = True) -> np.ndarray:
    halo = (patch - core) // 2
    h, w = image.shape
    full_h = int(math.ceil(h / core) * core)
    full_w = int(math.ceil(w / core) * core)
    pad_bottom = halo + full_h - h
    pad_right = halo + full_w - w
    mode = "reflect" if h > halo and w > halo else "edge"
    padded = np.pad(image, ((halo, pad_bottom), (halo, pad_right)), mode=mode)
    output = np.zeros((full_h, full_w), dtype=np.float32)
    model.eval()
    for y0 in range(0, full_h, core):
        for x0 in range(0, full_w, core):
            crop = padded[y0:y0 + patch, x0:x0 + patch]
            tensor = torch.from_numpy(crop.copy()).to(device=device, dtype=torch.float32).unsqueeze(0).unsqueeze(0)
            with torch.autocast(device_type="cuda", dtype=torch.bfloat16, enabled=amp_enabled):
                pred = model(tensor)[0, 0, halo:halo + core, halo:halo + core]
            output[y0:y0 + core, x0:x0 + core] = pred.float().cpu().numpy()
    return np.clip(output[:h, :w], 0.0, 1.0)


def live_validation(model: nn.Module, device: torch.device, epoch: int, amp_enabled: bool) -> list[str]:
    source_dir = EXPERIMENT_DIR / "data" / "live_validation"
    output_dir = RESULTS_DIR / "live_validation" / f"epoch_{epoch:03d}"
    output_dir.mkdir(parents=True, exist_ok=True)
    outputs: list[str] = []
    for path in sorted(source_dir.glob("*")):
        if path.suffix.lower() not in {".bmp", ".png", ".tif", ".tiff"}:
            continue
        raw = cv2.imread(str(path), cv2.IMREAD_UNCHANGED)
        if raw is None:
            continue
        if raw.ndim == 3:
            raw = cv2.cvtColor(raw, cv2.COLOR_BGR2GRAY)
        normalized = image_to_float(raw)
        reconstructed = tiled_predict(model, normalized, device, amp_enabled=amp_enabled)
        recon_u8 = np.rint(reconstructed * 255.0).astype(np.uint8)
        raw_u8 = np.rint(np.clip(normalized, 0.0, 1.0) * 255.0).astype(np.uint8)
        out_path = output_dir / f"{path.stem}_recon.bmp"
        cv2.imwrite(str(out_path), recon_u8)
        sheet = np.concatenate([raw_u8, recon_u8], axis=1)
        cv2.putText(sheet, "RAW", (8, 24), cv2.FONT_HERSHEY_SIMPLEX, 0.7, 255, 2, cv2.LINE_AA)
        cv2.putText(sheet, f"R87 E{epoch}", (raw_u8.shape[1] + 8, 24), cv2.FONT_HERSHEY_SIMPLEX, 0.7, 255, 2, cv2.LINE_AA)
        cv2.imwrite(str(output_dir / f"{path.stem}_compare.png"), sheet)
        outputs.append(str(out_path))
    return outputs


def learning_rate(epoch: int) -> float:
    maximum = float(CONFIG["training"]["learning_rate"])
    minimum = float(CONFIG["training"]["minimum_learning_rate"])
    total = int(CONFIG["training"]["epochs"])
    if epoch <= 3:
        return maximum * epoch / 3.0
    progress = (epoch - 3) / max(total - 3, 1)
    return minimum + 0.5 * (maximum - minimum) * (1.0 + math.cos(math.pi * progress))


def checkpoint_payload(model: nn.Module, ema: nn.Module, epoch: int, metrics: dict[str, Any], metadata: dict[str, Any]) -> dict[str, Any]:
    return {
        "experiment_id": CONFIG["experiment_id"],
        "epoch": int(epoch),
        "model_state_dict": model.state_dict(),
        "ema_state_dict": ema.state_dict(),
        "metrics": metrics,
        "metadata": metadata,
        "checkpoint_loaded": False,
        "resume_source": None,
    }


def run(args: argparse.Namespace) -> int:
    if any(token in " ".join(sys.argv).lower() for token in ("checkpoint", "resume", "pretrain", "teacher")):
        raise RuntimeError("Scratch guard rejected a forbidden launcher token")
    if args.run_kind == "formal":
        active_guard = RUNS_DIR / "launcher_logs" / "active_formal_run.json"
        if active_guard.is_file():
            previous = json.loads(active_guard.read_text(encoding="utf-8"))
            if previous.get("status") == "active":
                raise RuntimeError("A formal R87 run is already marked active")
        for summary_path in RUNS_DIR.glob("training_progress_*/run_summary.json"):
            previous = json.loads(summary_path.read_text(encoding="utf-8"))
            if previous.get("status") == "complete" and int(previous.get("completed_epoch", 0)) == 100:
                raise RuntimeError("The single authorized formal R87 run already exists")
    manifest_path = DATASET_DIR / "manifest.json"
    audit_path = DATASET_DIR / "audit.json"
    if not manifest_path.is_file() or not audit_path.is_file():
        raise FileNotFoundError("Formal dataset and audit must exist before training")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    audit = json.loads(audit_path.read_text(encoding="utf-8"))
    if not audit.get("passed"):
        raise RuntimeError("Dataset audit did not pass")
    if int(manifest["scene_count"]) != 1280 or int(manifest["total_views"]) != 5120:
        raise RuntimeError("Formal dataset count lock failed")

    seed = int(args.seed)
    random.seed(seed); np.random.seed(seed); torch.manual_seed(seed); torch.cuda.manual_seed_all(seed)
    torch.backends.cuda.matmul.allow_tf32 = True
    torch.backends.cudnn.allow_tf32 = True
    torch.backends.cudnn.benchmark = True
    device = torch.device(args.device)
    if device.type == "cuda" and not torch.cuda.is_available():
        raise RuntimeError("CUDA was requested but is unavailable")

    module = load_model_module()
    model = module.build_model(base=int(CONFIG["architecture"]["base_channels"])).to(device)
    initial_hash = state_sha256(model)
    ema = copy.deepcopy(model).eval().requires_grad_(False)
    optimizer = torch.optim.AdamW(
        model.parameters(),
        lr=float(CONFIG["training"]["learning_rate"]),
        weight_decay=float(CONFIG["training"]["weight_decay"]),
    )
    parameter_count = int(module.count_parameters(model))

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_name = f"training_progress_{MODEL_NAME_BASE}_{timestamp}"
    weights_root = EXPERIMENT_DIR / "weights" / str(args.run_kind) / f"seed_{seed}"
    run_dir = weights_root / run_name
    if run_dir.exists():
        raise FileExistsError(f"Scratch output directory already exists: {run_dir}")
    weight_dir = run_dir / "weights"
    weight_dir.mkdir(parents=True)
    run_record_dir = RUNS_DIR / (run_name if args.run_kind == "formal" else f"smoke_{run_name}")
    run_record_dir.mkdir(parents=True)
    active_name = "active_formal_run.json" if args.run_kind == "formal" else "active_smoke_run.json"
    active_path = RUNS_DIR / "launcher_logs" / active_name

    metadata = {
        "experiment_id": CONFIG["experiment_id"],
        "model_name": MODEL_NAME_BASE,
        "seed": seed,
        "device": str(device),
        "parameter_count": parameter_count,
        "initial_parameter_sha256": initial_hash,
        "architecture_sha256": sha256_file(MODEL_PATH),
        "trainer_sha256": sha256_file(Path(__file__)),
        "config_sha256": sha256_file(CONFIG_PATH),
        "dataset_content_sha256": manifest["content_sha256"],
        "checkpoint_loaded": False,
        "resume_source": None,
        "teacher_used": False,
        "real_training_pixels": False,
        "optimizer_fresh": True,
        "ema_initialized_from_random_model": True,
        "started_at": datetime.now().isoformat(),
        "run_dir": str(run_dir),
        "run_kind": str(args.run_kind),
    }
    json_dump(run_record_dir / "scratch_initialization_audit.json", metadata)
    json_dump(active_path, {**metadata, "status": "active", "planned_epochs": int(args.epochs), "completed_epoch": 0})

    amp_enabled = device.type == "cuda" and not args.no_amp
    log_path = run_record_dir / "training_log.csv"
    fieldnames = ["epoch", "lr", "seconds", "patch", "core", "scene_batch", "accumulation", "gpu_peak_gib",
                  "train_total", "train_reconstruction", "train_edge", "train_laplacian", "train_soft_contour", "train_consistency", "train_identity",
                  "val_total", "val_reconstruction", "val_edge", "val_laplacian", "val_soft_contour", "val_consistency", "val_identity"]
    with log_path.open("w", newline="", encoding="utf-8") as handle:
        csv.DictWriter(handle, fieldnames=fieldnames).writeheader()

    best_value = float("inf")
    best_epoch = 0
    latest_validation: dict[str, float] = {}
    for epoch in range(1, int(args.epochs) + 1):
        epoch_start = time.perf_counter()
        stage = stage_for_epoch(epoch)
        patch_size = stage["patch_size"]
        core_size = stage["core_size"]
        scene_batch = stage["scene_batch_size"]
        accumulation = stage["gradient_accumulation"]
        dataset = ScenePairDataset(manifest, "train", patch_size, core_size, epoch, include_both_renderings=False)
        loader_generator = torch.Generator().manual_seed(seed + epoch * 101)
        loader = DataLoader(
            dataset,
            batch_size=scene_batch,
            shuffle=True,
            generator=loader_generator,
            num_workers=int(args.num_workers),
            pin_memory=device.type == "cuda",
            persistent_workers=False,
            drop_last=False,
        )
        lr = learning_rate(epoch)
        for group in optimizer.param_groups:
            group["lr"] = lr
        model.train()
        optimizer.zero_grad(set_to_none=True)
        sums: defaultdict[str, float] = defaultdict(float)
        seen = 0
        if device.type == "cuda":
            torch.cuda.reset_peak_memory_stats(device)
        for batch_index, (source, target, origins, identity, _roles) in enumerate(loader, start=1):
            batch = int(source.shape[0])
            source = source.to(device, non_blocking=True)
            target = target.to(device, non_blocking=True)
            flat_source = source.reshape(batch * 2, 1, patch_size, patch_size)
            flat_target = target.reshape(batch * 2, 1, patch_size, patch_size)
            with torch.autocast(device_type="cuda", dtype=torch.bfloat16, enabled=amp_enabled):
                prediction = model(flat_source)
                total, parts = loss_components(prediction, flat_target, flat_source, origins, identity, patch_size, core_size)
                scaled = total / accumulation
            scaled.backward()
            should_step = batch_index % accumulation == 0 or batch_index == len(loader)
            if should_step:
                torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
                optimizer.step()
                optimizer.zero_grad(set_to_none=True)
                update_ema(model, ema)
            for name, value in parts.items():
                sums[name] += float(value) * batch
            seen += batch
            if args.max_train_batches and batch_index >= args.max_train_batches:
                break
        train_metrics = {name: value / max(seen, 1) for name, value in sums.items()}

        validate_now = epoch % int(CONFIG["training"]["validation_every"]) == 0 or epoch == int(args.epochs) or epoch == 1
        if validate_now:
            validation_dataset = ScenePairDataset(manifest, "validation", 896, 512, 0, include_both_renderings=True)
            validation_loader = DataLoader(
                validation_dataset,
                batch_size=2,
                shuffle=False,
                num_workers=int(args.num_workers),
                pin_memory=device.type == "cuda",
                persistent_workers=False,
            )
            latest_validation = evaluate(
                ema, validation_loader, device, 896, 512, amp_enabled,
                max_batches=int(args.max_validation_batches),
            )

        gpu_peak = torch.cuda.max_memory_allocated(device) / (1024 ** 3) if device.type == "cuda" else 0.0
        elapsed = time.perf_counter() - epoch_start
        row: dict[str, Any] = {
            "epoch": epoch, "lr": lr, "seconds": elapsed, "patch": patch_size, "core": core_size,
            "scene_batch": scene_batch, "accumulation": accumulation, "gpu_peak_gib": gpu_peak,
        }
        for name in ("total", "reconstruction", "edge", "laplacian", "soft_contour", "consistency", "identity"):
            row[f"train_{name}"] = train_metrics.get(name, "")
            row[f"val_{name}"] = latest_validation.get(name, "") if validate_now else ""
        with log_path.open("a", newline="", encoding="utf-8") as handle:
            csv.DictWriter(handle, fieldnames=fieldnames).writerow(row)

        metrics = {"train": train_metrics, "validation": latest_validation if validate_now else None, "stage": stage, "lr": lr, "seconds": elapsed, "gpu_peak_gib": gpu_peak}
        save_now = epoch % int(CONFIG["training"]["checkpoint_every"]) == 0 or epoch == int(args.epochs)
        if save_now:
            torch.save(checkpoint_payload(model, ema, epoch, metrics, metadata), weight_dir / f"epoch_{epoch:03d}.pth.tar")
        if validate_now and latest_validation["total"] < best_value:
            best_value = latest_validation["total"]
            best_epoch = epoch
            torch.save(checkpoint_payload(model, ema, epoch, metrics, metadata), weight_dir / "best_validation.pth.tar")
        torch.save(checkpoint_payload(model, ema, epoch, metrics, metadata), weight_dir / "latest.pth.tar")

        live_outputs = []
        if epoch % int(CONFIG["training"]["live_validation_every"]) == 0 or epoch == 1 or epoch == int(args.epochs):
            live_outputs = live_validation(ema, device, epoch, amp_enabled)
        active_payload = {
            **metadata, "status": "active", "planned_epochs": int(args.epochs), "completed_epoch": epoch,
            "best_epoch": best_epoch, "best_validation_total": best_value, "latest_metrics": metrics,
            "live_outputs": live_outputs,
        }
        json_dump(active_path, active_payload)
        json_dump(run_record_dir / "run_progress.json", active_payload)
        print(json.dumps({"epoch": epoch, "stage": stage, "train": train_metrics, "validation": latest_validation if validate_now else None,
                          "seconds": elapsed, "gpu_peak_gib": gpu_peak, "best_epoch": best_epoch, "best_validation_total": best_value}), flush=True)

        if args.max_train_batches:
            break

    completed_epoch = epoch
    complete = completed_epoch == int(args.epochs) and not args.max_train_batches
    summary = {
        **metadata,
        "status": "complete" if complete else "smoke_complete",
        "planned_epochs": int(args.epochs),
        "completed_epoch": completed_epoch,
        "best_epoch": best_epoch,
        "best_validation_total": best_value,
        "final_validation": latest_validation,
        "finished_at": datetime.now().isoformat(),
        "weights_dir": str(weight_dir),
        "training_log": str(log_path),
    }
    json_dump(run_record_dir / "run_summary.json", summary)
    json_dump(active_path, summary)
    print(json.dumps(summary, indent=2), flush=True)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--device", default="cuda:0")
    parser.add_argument("--seed", type=int, default=int(CONFIG["training"]["seed"]))
    parser.add_argument("--epochs", type=int, default=int(CONFIG["training"]["epochs"]))
    parser.add_argument("--num-workers", type=int, default=int(CONFIG["training"]["num_workers"]))
    parser.add_argument("--run-kind", choices=("smoke", "formal"), default="formal")
    parser.add_argument("--no-amp", action="store_true")
    parser.add_argument("--max-train-batches", type=int, default=0)
    parser.add_argument("--max-validation-batches", type=int, default=0)
    args = parser.parse_args()
    return run(args)


if __name__ == "__main__":
    raise SystemExit(main())

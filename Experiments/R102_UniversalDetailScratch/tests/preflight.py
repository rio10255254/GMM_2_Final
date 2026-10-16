"""Executable delivery gate before the one formal R102 training run."""
from __future__ import annotations

import gc
import json
import math
import sys
import time
from datetime import datetime
from pathlib import Path

import cv2
import numpy as np
import torch
from torch.utils.data._utils.collate import default_collate


ROOT = Path(__file__).resolve().parents[1]
for folder in (ROOT / "model", ROOT / "training", ROOT / "inference"):
    sys.path.insert(0, str(folder))

from r102_model import build_model, count_parameters  # noqa: E402
from r102_dataset import R102Dataset  # noqa: E402
from losses import loss_components, warp_tensor  # noqa: E402
from reconstruct import reconstruct_full_reference, reconstruct_tensor  # noqa: E402


CONFIG = json.loads((ROOT / "config" / "experiment.json").read_text(encoding="utf-8"))


def save_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, allow_nan=False), encoding="utf-8")


def make_batch(dataset: R102Dataset, indices: list[int], device: torch.device) -> dict[str, object]:
    batch = default_collate([dataset[index] for index in indices])
    for key in ("source", "target", "mask", "motion", "identity", "mode", "midpoint", "polarity"):
        batch[key] = batch[key].to(device)
    return batch


def flatten_batch(batch: dict[str, object]):
    source = batch["source"]
    target = batch["target"]
    mask = batch["mask"]
    b, v, c, h, w = source.shape
    return {
        "source": source.reshape(b * v, c, h, w).contiguous(memory_format=torch.channels_last),
        "target": target.reshape(b * v, c, h, w),
        "mask": mask.reshape(b * v, c, h, w),
        "motion": batch["motion"].reshape(-1, 2),
        "identity": batch["identity"].reshape(-1),
        "mode": batch["mode"].repeat_interleave(v),
        "midpoint": batch["midpoint"].repeat_interleave(v),
        "polarity": batch["polarity"].repeat_interleave(v),
    }


def data_preview(dataset: R102Dataset) -> str:
    panels = []
    for index in (0, 2, 3, 4, 8, 10):
        sample = dataset[index]
        raw = np.clip(sample["source"][0, 0].numpy() * 255.0 + 0.5, 0, 255).astype(np.uint8)
        target = np.clip(sample["target"][0, 0].numpy() * 255.0 + 0.5, 0, 255).astype(np.uint8)
        row = np.concatenate([raw, target], axis=1)
        row = cv2.cvtColor(row, cv2.COLOR_GRAY2BGR)
        cv2.rectangle(row, (0, 0), (row.shape[1], 25), (15, 15, 15), -1)
        label = f"mode={R102Dataset.mode_names[int(sample['mode'])]}  role={sample['role']}  RAW | TRUTH"
        cv2.putText(row, label, (6, 18), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (245, 245, 245), 1, cv2.LINE_AA)
        panels.append(row)
    path = ROOT / "reports" / "data_preview.png"
    path.parent.mkdir(parents=True, exist_ok=True)
    if not cv2.imwrite(str(path), np.concatenate(panels, axis=0)):
        raise RuntimeError("Unable to save data preview")
    return str(path)


def loss_for_batch(model, flat, core_size: int):
    details = model.forward_details(flat["source"])
    components = loss_components(
        details, flat["source"], flat["target"], flat["mask"], flat["midpoint"], flat["polarity"],
        flat["mode"], flat["identity"], flat["motion"], core_size,
    )
    total = (
        components["reconstruction"] + 0.25 * components["gradient"]
        + 0.55 * components["high_frequency"] + 0.25 * components["contour"]
        + 0.30 * components["branch_targets"] + 0.15 * components["identity"]
        + 0.12 * components["flat_negative"]
    )
    return total, details, components


def benchmark_stages(device: torch.device) -> list[dict[str, float]]:
    rows = []
    if device.type != "cuda":
        return rows
    for stage in CONFIG["training"]["stages"]:
        patch = int(stage["patch_size"])
        scene_batch = int(stage["batch_size"])
        views = scene_batch * 2
        model = build_model(base=int(CONFIG["model"]["base_channels"])).to(device).to(memory_format=torch.channels_last)
        optimizer = torch.optim.AdamW(model.parameters(), lr=1e-4)
        source = torch.rand((views, 1, patch, patch), device=device).contiguous(memory_format=torch.channels_last)
        target = torch.rand_like(source)
        torch.cuda.reset_peak_memory_stats(device)
        started = time.perf_counter()
        optimizer.zero_grad(set_to_none=True)
        with torch.autocast(device_type="cuda", dtype=torch.bfloat16):
            prediction = model(source)
            loss = (prediction.float() - target).abs().mean()
        loss.backward()
        optimizer.step()
        torch.cuda.synchronize(device)
        rows.append({
            "patch_size": patch,
            "scene_batch": scene_batch,
            "flattened_views": views,
            "seconds": time.perf_counter() - started,
            "peak_allocated_gib": torch.cuda.max_memory_allocated(device) / (1024**3),
            "free_after_gib": torch.cuda.mem_get_info(device)[0] / (1024**3),
        })
        del model, optimizer, source, target, prediction, loss
        gc.collect()
        torch.cuda.empty_cache()
    return rows


def main() -> int:
    device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")
    audit = json.loads((ROOT / "data" / "source_audit.json").read_text(encoding="utf-8"))
    if not audit.get("passed") or not audit.get("source_isolation_pass"):
        raise RuntimeError("Source audit has not passed")
    dataset = R102Dataset("validation", 192, 0, validation_limit=32)
    preview = data_preview(dataset)

    model = build_model(base=int(CONFIG["model"]["base_channels"]))
    parameters = count_parameters(model)
    identity_input = torch.rand(2, 1, 192, 192)
    with torch.no_grad():
        identity_error = float((model(identity_input) - identity_input).abs().max())
    if identity_error != 0.0:
        raise RuntimeError(f"Fresh model is not exact identity: {identity_error}")
    model = model.to(device).to(memory_format=torch.channels_last)
    batch = make_batch(dataset, [3, 4, 8, 10], device)
    flat = flatten_batch(batch)
    optimizer = torch.optim.AdamW(model.parameters(), lr=6e-4)
    losses = []
    branch_gradients: dict[str, float] = {}
    for step in range(42):
        optimizer.zero_grad(set_to_none=True)
        with torch.autocast(device_type="cuda", dtype=torch.bfloat16, enabled=device.type == "cuda"):
            total, _details, _components = loss_for_batch(model, flat, 128)
        if not bool(torch.isfinite(total)):
            raise RuntimeError("Non-finite short-overfit loss")
        total.backward()
        if step == 3:
            for name in ("low_head", "contour_head", "texture_head", "e1"):
                module = getattr(model, name)
                values = [p.grad.detach().float().norm() for p in module.parameters() if p.grad is not None]
                branch_gradients[name] = float(torch.stack(values).norm()) if values else 0.0
        torch.nn.utils.clip_grad_norm_(model.parameters(), 3.0)
        optimizer.step()
        losses.append(float(total.detach()))
    if losses[-1] >= losses[0] * 0.94:
        raise RuntimeError(f"Short overfit did not improve enough: {losses[0]} -> {losses[-1]}")
    if min(branch_gradients.values()) <= 0.0:
        raise RuntimeError(f"A model branch has no gradient: {branch_gradients}")

    model.eval()
    source = R102Dataset("validation", 320, 0, validation_limit=8)[3]["source"][0:1].to(device)
    with torch.inference_mode():
        full = reconstruct_full_reference(model, source, core_size=128, halo=128)
        tiled = reconstruct_tensor(model, source, core_size=128, halo=128, tile_batch=2)
        tile_mean = float((full - tiled).abs().mean())
        tile_max = float((full - tiled).abs().max())
        dx = source.new_tensor([0.625])
        dy = source.new_tensor([-0.375])
        shifted_source = warp_tensor(source, dx, dy)
        shifted_prediction = model(shifted_source).float()
        reference = warp_tensor(model(source).float(), dx, dy)
        shift_error = float((shifted_prediction[..., 32:-32, 32:-32] - reference[..., 32:-32, 32:-32]).abs().mean())
    if tile_mean > 2e-4 or tile_max > 0.01:
        raise RuntimeError(f"Tile contract failed: mean={tile_mean}, max={tile_max}")
    if not math.isfinite(shift_error) or shift_error > 0.035:
        raise RuntimeError(f"Translation response is unstable: {shift_error}")

    del model, optimizer, batch, flat, source, full, tiled
    gc.collect()
    if device.type == "cuda":
        torch.cuda.empty_cache()
    stage_benchmark = benchmark_stages(device)
    report = {
        "schema_version": 1,
        "experiment_id": CONFIG["experiment_id"],
        "passed": True,
        "created_at": datetime.now().isoformat(),
        "device": str(device),
        "gpu": torch.cuda.get_device_name(device) if device.type == "cuda" else None,
        "parameter_count": parameters,
        "source_isolation_pass": True,
        "fresh_model_identity_max_abs": identity_error,
        "short_overfit_initial": losses[0],
        "short_overfit_final": losses[-1],
        "short_overfit_improvement_fraction": 1.0 - losses[-1] / losses[0],
        "branch_gradient_norms": branch_gradients,
        "tile_mean_abs": tile_mean,
        "tile_max_abs": tile_max,
        "subpixel_translation_mean_abs": shift_error,
        "stage_memory_benchmark": stage_benchmark,
        "data_preview": preview,
    }
    save_json(ROOT / "reports" / "formal_preflight.json", report)
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

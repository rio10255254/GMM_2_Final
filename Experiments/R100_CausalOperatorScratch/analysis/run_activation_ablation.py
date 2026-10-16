"""Compare early operator activation strategies before freezing R100 training."""
from __future__ import annotations

import copy
import importlib.util
import json
import sys
from pathlib import Path

import numpy as np
import torch
from torch.utils.data import DataLoader


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "reports" / "operator_activation_ablation.json"


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


TRAINER = load_module("r100_ablation_trainer", ROOT / "training" / "train_r100.py")
MODEL = load_module("r100_ablation_model", ROOT / "model" / "r100_model.py")
DESIGN = TRAINER.DESIGN
ROLES = [
    "identity_and_detail_guard",
    "textured_general_geometry",
    "difficult_contour",
    "cross_tile_and_dense",
    "signed_subpixel_motion",
    "clean_contour_anchor",
]
SCENARIOS = {
    "cold_equal": {
        "biases": (-5.0, -5.0, -5.0),
        "lr_scales": (1.15, 1.15, 1.15, 1.25),
        "weight_updates": {},
    },
    "warm_separated": {
        "biases": (-4.2, -4.0, -3.5),
        "lr_scales": (0.85, 1.10, 1.40, 1.80),
        "weight_updates": {},
    },
    "warm_detail_supervision": {
        "biases": (-4.2, -4.0, -3.5),
        "lr_scales": (0.85, 1.10, 1.40, 1.80),
        "weight_updates": {
            "detail_branch_target": 0.25,
            "edge_branch_target": 0.18,
            "denoise_branch_target": 0.12,
            "texture_boundary_exclusion": 0.18,
            "material_detail_recovery": 0.24,
            "detail_recovery_view_output": 1.20,
            "detail_recovery_view_branch": 1.50,
        },
    },
}


def move_batch(batch: dict, device: torch.device) -> dict:
    return batch


def main() -> int:
    torch.backends.cuda.matmul.allow_tf32 = True
    torch.backends.cudnn.allow_tf32 = True
    torch.backends.cudnn.benchmark = True
    package, manifest, audit = TRAINER.preflight("smoke")
    if not audit.get("passed"):
        raise RuntimeError("Locked data audit failed")
    dataset = TRAINER.R100SceneDataset(package, manifest, "train", 128, 64, 3)
    role_indices = {role: [i for i in range(len(dataset)) if dataset.role_at(i) == role and dataset.view_count_at(i) == 2] for role in ROLES}
    batch_lists = [[role_indices[role][round_index] for role in ROLES] for round_index in range(6)]
    eval_indices = [role_indices[role][8] for role in ROLES]
    detail_eval_indices = [
        next(index for index in reversed(role_indices[role]) if dataset.detail_recovery_at(index) and index not in {value for batch in batch_lists for value in batch})
        for role in ("textured_general_geometry", "difficult_contour", "clean_contour_anchor")
    ]
    detail_pool = [index for role in ("textured_general_geometry", "difficult_contour", "clean_contour_anchor") for index in role_indices[role] if dataset.detail_recovery_at(index) and index not in detail_eval_indices]
    detail_batch_lists = [detail_pool[start:start + 6] for start in range(0, 18, 6)]
    train_batches = [next(iter(DataLoader(dataset, batch_sampler=[indices], num_workers=0, pin_memory=True))) for indices in batch_lists]
    detail_train_batches = [next(iter(DataLoader(dataset, batch_sampler=[indices], num_workers=0, pin_memory=True))) for indices in detail_batch_lists]
    eval_batch = next(iter(DataLoader(dataset, batch_sampler=[eval_indices], num_workers=0, pin_memory=True)))
    detail_eval_batch = next(iter(DataLoader(dataset, batch_sampler=[detail_eval_indices], num_workers=0, pin_memory=True)))
    device = torch.device("cuda:0")
    original_weights = copy.deepcopy(DESIGN["training"]["loss_weights"])
    results: dict[str, dict] = {}

    def measure(model: torch.nn.Module, batch: dict) -> dict[str, float]:
        model.eval()
        scenes, views = batch["source"].shape[:2]
        source = batch["source"].to(device).reshape(scenes * views, 1, 128, 128).contiguous(memory_format=torch.channels_last)
        target = batch["target"].to(device).reshape(scenes * views, 1, 128, 128)
        core = slice(32, 96)
        with torch.inference_mode():
            details = model(source.float(), return_details=True)
            total, parts, _ = TRAINER.loss_components(details, batch, 128, 64, 12, enable_topology=True)
            pred = details["output"][..., core, core]
            raw = source[..., core, core]
            truth = target[..., core, core]
            pred_fine = pred - TRAINER.lowpass(pred, 3)
            raw_fine = raw - TRAINER.lowpass(raw, 3)
            truth_fine = truth - TRAINER.lowpass(truth, 3)
            identity = batch["identity"].to(device).reshape(-1)
            midpoint = batch["boundary_level"].to(device).repeat_interleave(views)
            polarity = batch["polarity"].to(device).repeat_interleave(views)
            pred_centroid = TRAINER.centroid(TRAINER.foreground_probability(pred, midpoint, polarity))
            raw_centroid = TRAINER.centroid(TRAINER.foreground_probability(raw, midpoint, polarity))
            mask = batch["mask"].to(device).reshape(scenes * views, 1, 128, 128)[..., core, core]
            target_centroid = TRAINER.centroid(mask)
            raw_detail_error = (raw_fine - truth_fine).abs().mean()
            pred_detail_error = (pred_fine - truth_fine).abs().mean()
            return {
                "total": float(total),
                "pixel_gray": float((pred - truth).abs().mean() * 255.0),
                "raw_pixel_gray": float((raw - truth).abs().mean() * 255.0),
                "detail_error_ratio_to_raw": float(pred_detail_error / raw_detail_error.clamp_min(1e-6)),
                "identity_change_gray": float((pred[identity] - raw[identity]).abs().mean() * 255.0) if bool(identity.any()) else 0.0,
                "raw_centroid_error_px": float(torch.linalg.vector_norm(raw_centroid - target_centroid, dim=1).mean()),
                "model_centroid_error_px": float(torch.linalg.vector_norm(pred_centroid - target_centroid, dim=1).mean()),
                "centroid_change_px": float(torch.linalg.vector_norm(pred_centroid - raw_centroid, dim=1).mean()),
                "radiometry_gray": float(details["low_delta"][..., core, core].abs().mean() * 255.0),
                "denoise_gray": float(details["denoise_delta"][..., core, core].abs().mean() * 255.0),
                "edge_gray": float(details["edge_delta"][..., core, core].abs().mean() * 255.0),
                "texture_gray": float(details["texture_delta"][..., core, core].abs().mean() * 255.0),
                "material_detail_recovery": float(parts["material_detail_recovery"]),
                "transport_abs": float(details["transport_delta"].abs().max()),
            }

    for name, scenario in SCENARIOS.items():
        torch.manual_seed(1000053)
        np.random.seed(1000053)
        DESIGN["training"]["loss_weights"] = copy.deepcopy(original_weights)
        DESIGN["training"]["loss_weights"].update(scenario["weight_updates"])
        model = MODEL.build_model(base=24).to(device, memory_format=torch.channels_last).train()
        denoise_bias, edge_bias, texture_bias = scenario["biases"]
        with torch.no_grad():
            model.denoise_head[-1].bias.fill_(denoise_bias)
            model.edge_head[-1].bias.fill_(edge_bias)
            model.texture_head[-1].bias.fill_(texture_bias)
        radio_lr, denoise_lr, edge_lr, texture_lr = scenario["lr_scales"]
        grouped = [
            {"params": list(model.radiometry_head.parameters()), "lr": 1.6e-4 * radio_lr},
            {"params": list(model.denoise_head.parameters()), "lr": 1.6e-4 * denoise_lr},
            {"params": list(model.edge_head.parameters()), "lr": 1.6e-4 * edge_lr},
            {"params": list(model.texture_head.parameters()), "lr": 1.6e-4 * texture_lr},
        ]
        grouped_ids = {id(p) for group in grouped for p in group["params"]}
        grouped.append({"params": [p for p in model.parameters() if id(p) not in grouped_ids], "lr": 1.6e-4})
        optimizer = torch.optim.AdamW(grouped, weight_decay=1e-4, fused=True)
        initial = measure(model, eval_batch)
        initial_detail = measure(model, detail_eval_batch)
        losses: list[float] = []
        model.train()
        for step in range(160):
            batch = detail_train_batches[(step // 5) % len(detail_train_batches)] if step % 5 == 0 else train_batches[step % len(train_batches)]
            scenes, views = batch["source"].shape[:2]
            source = batch["source"].to(device, non_blocking=True).reshape(scenes * views, 1, 128, 128).contiguous(memory_format=torch.channels_last)
            optimizer.zero_grad(set_to_none=True)
            with torch.autocast(device_type="cuda", dtype=torch.bfloat16):
                details = model(source, return_details=True)
                total, _parts, _ = TRAINER.loss_components(details, batch, 128, 64, 12, enable_topology=(step % 4 == 0))
            if not bool(torch.isfinite(total)):
                raise FloatingPointError(f"{name} became non-finite at step {step + 1}")
            total.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            optimizer.step()
            losses.append(float(total.detach()))
        final = measure(model, eval_batch)
        final_detail = measure(model, detail_eval_batch)
        results[name] = {
            "configuration": scenario,
            "initial": initial,
            "final": final,
            "initial_detail_recovery": initial_detail,
            "final_detail_recovery": final_detail,
            "training_loss_last_over_first": float(np.mean(losses[-20:]) / np.mean(losses[:20])),
            "finite": bool(np.isfinite(losses).all()),
        }
        del optimizer, model
        torch.cuda.empty_cache()

    DESIGN["training"]["loss_weights"] = original_weights
    report = {
        "experiment_id": DESIGN["experiment_id"],
        "purpose": "Early operator activation ablation; all models start random and no weights are retained.",
        "steps_per_scenario": 160,
        "train_batches": len(train_batches),
        "detail_train_batches": len(detail_train_batches),
        "detail_update_share": 0.20,
        "heldout_roles": ROLES,
        "results": results,
    }
    OUTPUT.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Falsify R100 learnability on a tiny locked-data subset without saving weights."""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import cv2
import numpy as np
import torch
from torch.utils.data import DataLoader


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "reports" / "learnability_probe.json"
PREVIEW = ROOT / "reports" / "learnability_probe.png"


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


TRAINER = load_module("r100_probe_trainer", ROOT / "training" / "train_r100.py")
MODEL = load_module("r100_probe_model", ROOT / "model" / "r100_model.py")
DESIGN = TRAINER.DESIGN


def to_u8(tensor: torch.Tensor) -> np.ndarray:
    return np.clip(np.rint(tensor.detach().float().cpu().numpy() * 255.0), 0, 255).astype(np.uint8)


def main() -> int:
    torch.manual_seed(1000053)
    np.random.seed(1000053)
    torch.backends.cuda.matmul.allow_tf32 = True
    torch.backends.cudnn.allow_tf32 = True
    torch.backends.cudnn.benchmark = True
    package, manifest, audit = TRAINER.preflight("smoke")
    if not audit.get("passed"):
        raise RuntimeError("Locked dataset audit did not pass")

    dataset = TRAINER.R100SceneDataset(package, manifest, "train", 128, 64, 1)
    roles = ["identity_and_detail_guard", "textured_general_geometry", "difficult_contour", "signed_subpixel_motion"]
    indices = [next(i for i in range(len(dataset)) if dataset.role_at(i) == role and dataset.view_count_at(i) == 2) for role in roles]
    batch = next(iter(DataLoader(dataset, batch_sampler=[indices], num_workers=0, pin_memory=True)))
    device = torch.device("cuda:0")
    model = MODEL.build_model(base=int(DESIGN["architecture"]["model_width"])).to(device, memory_format=torch.channels_last).train()
    optimizer = torch.optim.AdamW(model.parameters(), lr=1.6e-4, weight_decay=1e-4, fused=True)
    scenes, views = batch["source"].shape[:2]
    source = batch["source"].to(device).reshape(scenes * views, 1, 128, 128).contiguous(memory_format=torch.channels_last)
    target = batch["target"].to(device).reshape(scenes * views, 1, 128, 128)
    halo, core = 32, slice(32, 96)

    def evaluate() -> tuple[dict[str, float], dict[str, torch.Tensor]]:
        model.eval()
        with torch.inference_mode():
            details = model(source.float(), return_details=True)
            total, parts, _ = TRAINER.loss_components(details, batch, 128, 64, 8, enable_topology=True)
            pred_core = details["output"][..., core, core]
            src_core = source[..., core, core]
            tgt_core = target[..., core, core]
            midpoint = batch["boundary_level"].to(device).repeat_interleave(views)
            polarity = batch["polarity"].to(device).repeat_interleave(views)
            src_prob = TRAINER.foreground_probability(src_core, midpoint, polarity)
            pred_prob = TRAINER.foreground_probability(pred_core, midpoint, polarity)
            target_prob = batch["mask"].to(device).reshape(scenes * views, 1, 128, 128)[..., core, core]
            src_centroid = TRAINER.centroid(src_prob)
            pred_centroid = TRAINER.centroid(pred_prob)
            target_centroid = TRAINER.centroid(target_prob)
            identity = batch["identity"].to(device).reshape(-1)
            metrics = {
                "total": float(total),
                "pixel": float(parts["pixel"]),
                "material_detail_recovery": float(parts["material_detail_recovery"]),
                "raw_target_mae_gray": float((src_core - tgt_core).abs().mean() * 255.0),
                "model_target_mae_gray": float((pred_core - tgt_core).abs().mean() * 255.0),
                "output_change_gray": float((pred_core - src_core).abs().mean() * 255.0),
                "identity_change_gray": float((pred_core[identity] - src_core[identity]).abs().mean() * 255.0) if bool(identity.any()) else 0.0,
                "raw_centroid_error_px": float(torch.linalg.vector_norm(src_centroid - target_centroid, dim=1).mean()),
                "model_centroid_error_px": float(torch.linalg.vector_norm(pred_centroid - target_centroid, dim=1).mean()),
                "centroid_change_px": float(torch.linalg.vector_norm(pred_centroid - src_centroid, dim=1).mean()),
                "radiometry_gray": float(details["low_delta"][..., core, core].abs().mean() * 255.0),
                "denoise_gray": float(details["denoise_delta"][..., core, core].abs().mean() * 255.0),
                "edge_gray": float(details["edge_delta"][..., core, core].abs().mean() * 255.0),
                "texture_gray": float(details["texture_delta"][..., core, core].abs().mean() * 255.0),
                "transport_abs": float(details["transport_delta"].abs().max()),
            }
        return metrics, {key: value.detach().cpu() for key, value in details.items()}

    initial, initial_details = evaluate()
    losses: list[float] = []
    model.train()
    for step in range(200):
        optimizer.zero_grad(set_to_none=True)
        with torch.autocast(device_type="cuda", dtype=torch.bfloat16):
            details = model(source, return_details=True)
            total, _parts, _ = TRAINER.loss_components(details, batch, 128, 64, 8, enable_topology=(step % 4 == 0))
        if not bool(torch.isfinite(total)):
            raise FloatingPointError(f"Non-finite loss at step {step + 1}")
        total.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
        optimizer.step()
        losses.append(float(total.detach()))
    final, final_details = evaluate()

    role_index = roles.index("textured_general_geometry") * views
    raw = to_u8(source[role_index, 0, core, core])
    before = to_u8(initial_details["output"][role_index, 0, core, core])
    after = to_u8(final_details["output"][role_index, 0, core, core])
    truth = to_u8(target[role_index, 0, core, core])
    diff = np.clip(np.abs(after.astype(np.int16) - raw.astype(np.int16)) * 8, 0, 255).astype(np.uint8)
    panel = np.hstack([raw, before, after, truth, diff])
    panel = cv2.resize(panel, None, fx=3, fy=3, interpolation=cv2.INTER_NEAREST)
    cv2.imwrite(str(PREVIEW), panel)

    result = {
        "experiment_id": DESIGN["experiment_id"],
        "purpose": "Architecture learnability falsification only; no probe weights are retained or reused.",
        "steps": 200,
        "learning_rate": 1.6e-4,
        "roles": roles,
        "initial": initial,
        "final": final,
        "loss_first_20_mean": float(np.mean(losses[:20])),
        "loss_last_20_mean": float(np.mean(losses[-20:])),
        "loss_last_over_first": float(np.mean(losses[-20:]) / np.mean(losses[:20])),
        "finite": bool(np.isfinite(losses).all()),
        "transport_remained_exact_zero": final["transport_abs"] == 0.0,
        "weights_saved": False,
        "preview": str(PREVIEW),
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

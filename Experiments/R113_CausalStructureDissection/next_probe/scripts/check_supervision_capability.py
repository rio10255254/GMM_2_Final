"""Small fixed-batch check that the staged target can actually train the branch."""
from __future__ import annotations

import json
import random
import sys
from pathlib import Path

import numpy as np
import torch
from torch.utils.data import DataLoader


ROOT = Path(__file__).resolve().parents[1]
CONFIG = json.loads((ROOT / "config" / "experiment.json").read_text(encoding="utf-8"))
sys.path.insert(0, str(ROOT / "model")); sys.path.insert(0, str(ROOT / "training"))
from model import build_model
from dataset import ProbeDataset
from supervision import build_supervision_targets, carrier_supervision_loss, detail_supervision_loss


def measure(details, target_carrier, target_detail, total_loss):
    return {
        "combined_supervision_loss": float(total_loss.detach().cpu()),
        "detail_abs_mean_gray": float(details.detail.abs().mean().detach().cpu()) * 255,
        "detail_target_abs_mean_gray": float(target_detail.abs().mean().cpu()) * 255,
        "detail_mae_gray": float((details.detail - target_detail).abs().mean().detach().cpu()) * 255,
        "carrier_abs_mean_gray": float(details.detail_carrier.abs().mean().detach().cpu()) * 255,
        "carrier_target_abs_mean_gray": float(target_carrier.abs().mean().cpu()) * 255,
        "carrier_mae_gray": float((details.detail_carrier - target_carrier).abs().mean().detach().cpu()) * 255,
        "detail_max_abs_gray": float(details.detail.abs().max().detach().cpu()) * 255,
    }


def main() -> int:
    seed = int(CONFIG["seed"]); random.seed(seed); np.random.seed(seed); torch.manual_seed(seed); torch.cuda.manual_seed_all(seed)
    if not torch.cuda.is_available(): raise RuntimeError("CUDA required")
    model = build_model("bounded_detail_supervised").cuda().train()
    for parameter in model.detector_parameters(): parameter.requires_grad_(False)
    parameters = model.renderer_parameters()
    optimizer = torch.optim.Adam(parameters, lr=float(CONFIG["training"]["renderer_learning_rate"]))
    batch = next(iter(DataLoader(ProbeDataset("train", epoch=3, limit=6), batch_size=2, shuffle=False)))
    source = batch["source"].reshape(-1, *batch["source"].shape[2:])[..., 64:192, 64:192].cuda()
    target = batch["target"].reshape(-1, *batch["target"].shape[2:])[..., 64:192, 64:192].cuda()
    identity = batch["identity"].reshape(-1).cuda()
    carrier_weight = float(CONFIG["training"]["bounded_detail_supervision"]["carrier_auxiliary_weight"])
    snapshots = {}
    steps = 120
    for step in range(steps + 1):
        details = model.forward_details(source)
        target_carrier, target_detail = build_supervision_targets(model, details, target, identity)
        loss = detail_supervision_loss(details, target_detail) + carrier_weight * carrier_supervision_loss(details, target_carrier)
        if step in (0, steps): snapshots[str(step)] = measure(details, target_carrier, target_detail, loss)
        if step == steps: break
        optimizer.zero_grad(set_to_none=True); loss.backward()
        torch.nn.utils.clip_grad_norm_(parameters, float(CONFIG["training"]["gradient_clip"])); optimizer.step()
    initial, final = snapshots["0"], snapshots[str(steps)]
    loss_reduction = 100 * (initial["combined_supervision_loss"] - final["combined_supervision_loss"]) / initial["combined_supervision_loss"]
    carrier_mae_reduction = 100 * (initial["carrier_mae_gray"] - final["carrier_mae_gray"]) / initial["carrier_mae_gray"]
    bound = float(CONFIG["model"]["detail"]["maximum_amplitude_gray_levels"])
    checks = {
        "loss_reduction_at_least_4_percent": loss_reduction >= 4.0,
        "carrier_mae_reduction_at_least_1_percent": carrier_mae_reduction >= 1.0,
        "detail_activated_above_0p2_gray": final["detail_abs_mean_gray"] >= .2,
        "detail_bound_preserved": final["detail_max_abs_gray"] <= bound + 1e-4,
    }
    result = {
        "status": "PASS" if all(checks.values()) else "FAIL", "purpose": "learning-signal capability only",
        "formal_training": False,
        "steps": steps, "crop_size": 128, "optimizer_learning_rate": float(CONFIG["training"]["renderer_learning_rate"]),
        "initial": initial, "final": final, "loss_reduction_percent": loss_reduction,
        "carrier_mae_reduction_percent": carrier_mae_reduction, "checks": checks,
    }
    output = ROOT / "results" / "supervision_learning_capability.json"
    output.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())

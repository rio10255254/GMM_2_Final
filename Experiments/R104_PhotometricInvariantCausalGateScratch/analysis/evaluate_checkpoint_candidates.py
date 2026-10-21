"""Independent internal-test comparison for the locked R104 checkpoint candidates."""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import torch
from torch.utils.data import DataLoader

ROOT = Path(__file__).resolve().parents[1]
for folder in (ROOT / "model", ROOT / "training"):
    sys.path.insert(0, str(folder))

from r104_model import build_model  # noqa: E402
from r104_dataset import R104Dataset  # noqa: E402
from losses import central_crop, highpass, loss_components  # noqa: E402

CONFIG = json.loads((ROOT / "config" / "experiment.json").read_text(encoding="utf-8"))
RUN = json.loads((ROOT / "runs" / "active_run.json").read_text(encoding="utf-8"))
OUTPUT = ROOT / "results" / "posttraining_validation" / "candidate_selection"
CANDIDATES = tuple(int(value) for value in CONFIG["validation"]["checkpoint_candidates"])


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def build_r104() -> torch.nn.Module:
    bounds = CONFIG["model"]["branch_bounds"]
    return build_model(
        base=int(CONFIG["model"]["base_channels"]),
        low_bound=float(bounds["radiometry"]),
        illumination_bound=float(bounds["illumination"]),
        contour_bound=float(bounds["contour_proposal"]),
        texture_bound=float(bounds["texture_proposal"]),
        combined_bound=float(bounds["combined"]),
        gate_initial_probability=float(CONFIG["model"]["gate_initial_probability"]),
    )


def flatten(batch: dict, device: torch.device) -> dict[str, torch.Tensor]:
    source = batch["source"].to(device, non_blocking=True)
    b, v, c, h, w = source.shape
    return {
        "source": source.reshape(b * v, c, h, w).contiguous(memory_format=torch.channels_last),
        "target": batch["target"].to(device, non_blocking=True).reshape(b * v, c, h, w),
        "mask": batch["mask"].to(device, non_blocking=True).reshape(b * v, c, h, w),
        "sdf": batch["sdf"].to(device, non_blocking=True).reshape(b * v, c, h, w),
        "illumination_target": batch["illumination_target"].to(device, non_blocking=True).reshape(b * v, c, h, w),
        "identity": batch["identity"].to(device, non_blocking=True).reshape(-1),
        "mode": batch["mode"].to(device, non_blocking=True).repeat_interleave(v),
        "pair_type": batch["pair_type"].to(device, non_blocking=True).repeat_interleave(v),
        "motion": batch["motion"].to(device, non_blocking=True).reshape(-1, 2),
    }


@torch.inference_mode()
def evaluate(model: torch.nn.Module, loader: DataLoader, device: torch.device) -> tuple[dict[str, float], pd.DataFrame]:
    totals: dict[str, float] = {}
    count_total = 0
    slices: list[dict[str, object]] = []
    model.eval()
    for batch in loader:
        data = flatten(batch, device)
        with torch.autocast("cuda", dtype=torch.bfloat16, enabled=device.type == "cuda"):
            details = model.forward_details(data["source"])
            components = loss_components(details, **data, core_size=288)
        prediction = central_crop(details.output.float(), 288)
        source = central_crop(data["source"].float(), 288)
        target = central_crop(data["target"].float(), 288)
        sdf = central_crop(data["sdf"].float(), 288)
        mask = central_crop(data["mask"].float(), 288)
        predicted_sdf = central_crop(details.signed_distance.float(), 288)
        error = (prediction - target).abs()
        raw_error = (source - target).abs()
        boundary_weight = torch.exp(-sdf.abs() / 4.0)
        gates = torch.stack([
            central_crop(details.low_gate.float(), 288), central_crop(details.illumination_gate.float(), 288),
            central_crop(details.contour_gate.float(), 288), central_crop(details.texture_gate.float(), 288),
        ]).mean(0)
        identity, active = data["identity"], ~data["identity"]
        intersection = ((predicted_sdf > 0) & (mask > .5)).float().sum()
        union = ((predicted_sdf > 0) | (mask > .5)).float().sum().clamp_min(1.0)
        n = prediction.shape[0]
        count_total += n
        metrics = {
            "mae": error.mean(), "raw_mae": raw_error.mean(),
            "psnr_db": -10.0 * torch.log10((prediction - target).square().mean().clamp_min(1e-12)),
            "boundary_mae": (error * boundary_weight).sum() / boundary_weight.sum().clamp_min(1.0),
            "raw_boundary_mae": (raw_error * boundary_weight).sum() / boundary_weight.sum().clamp_min(1.0),
            "texture_mae": (highpass(prediction, 3) - highpass(target, 3)).abs().mean(),
            "raw_texture_mae": (highpass(source, 3) - highpass(target, 3)).abs().mean(),
            "shape_iou": intersection / union,
            "identity_change": (prediction[identity] - source[identity]).abs().mean() if bool(identity.any()) else error.new_zeros(()),
            "active_gate": gates[active].mean() if bool(active.any()) else gates.new_zeros(()),
            "identity_gate": gates[identity].mean() if bool(identity.any()) else gates.new_zeros(()),
            "illumination_mae": (central_crop(details.illumination_delta.float(), 288) - central_crop(data["illumination_target"].float(), 288)).abs().mean(),
        }
        metrics.update({f"objective_{name}": value.float() for name, value in components.items()})
        for name, value in metrics.items():
            totals[name] = totals.get(name, 0.0) + float(value) * n
        for mode in range(6):
            selected = data["mode"] == mode
            if bool(selected.any()):
                slices.append({
                    "mode": mode, "count": int(selected.sum()),
                    "mae": float(error[selected].mean()), "raw_mae": float(raw_error[selected].mean()),
                    "boundary_mae": float((error[selected] * boundary_weight[selected]).sum() / boundary_weight[selected].sum().clamp_min(1.0)),
                    "raw_boundary_mae": float((raw_error[selected] * boundary_weight[selected]).sum() / boundary_weight[selected].sum().clamp_min(1.0)),
                    "texture_mae": float((highpass(prediction[selected], 3) - highpass(target[selected], 3)).abs().mean()),
                    "raw_texture_mae": float((highpass(source[selected], 3) - highpass(target[selected], 3)).abs().mean()),
                })
    result = {name: value / count_total for name, value in totals.items()}
    result["gate_separation"] = result["active_gate"] - result["identity_gate"]
    result["mae_improvement_fraction"] = (result["raw_mae"] - result["mae"]) / result["raw_mae"]
    result["boundary_improvement_fraction"] = (result["raw_boundary_mae"] - result["boundary_mae"]) / result["raw_boundary_mae"]
    result["texture_improvement_fraction"] = (result["raw_texture_mae"] - result["texture_mae"]) / result["raw_texture_mae"]
    return result, pd.DataFrame(slices)


def main() -> None:
    if RUN.get("status") != "completed" or int(RUN.get("completed_epoch", 0)) != 48:
        raise RuntimeError("R104 formal training is incomplete")
    OUTPUT.mkdir(parents=True, exist_ok=True)
    device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")
    dataset = R104Dataset("internal_test", 384, 48)
    loader = DataLoader(dataset, batch_size=5, shuffle=False, num_workers=2, pin_memory=True)
    rows, slice_frames, manifest = [], [], []
    for epoch in CANDIDATES:
        checkpoint = Path(RUN["weights_dir"]) / f"epoch_{epoch:03d}.pth.tar"
        payload = torch.load(checkpoint, map_location="cpu", weights_only=False)
        model = build_r104()
        model.load_state_dict(payload["ema_state_dict"], strict=True)
        model = model.to(device).to(memory_format=torch.channels_last).eval()
        metrics, slices = evaluate(model, loader, device)
        rows.append({"epoch": epoch, **metrics})
        slices.insert(0, "epoch", epoch)
        slice_frames.append(slices)
        manifest.append({"epoch": epoch, "path": str(checkpoint), "sha256": sha256(checkpoint)})
        del model
        if device.type == "cuda":
            torch.cuda.empty_cache()
        print(json.dumps({"epoch": epoch, "mae": metrics["mae"], "boundary": metrics["boundary_mae"], "texture": metrics["texture_mae"]}), flush=True)
    table = pd.DataFrame(rows)
    table.to_csv(OUTPUT / "internal_test_metrics.csv", index=False)
    pd.concat(slice_frames, ignore_index=True).to_csv(OUTPUT / "internal_test_by_mode.csv", index=False)
    preference = table.sort_values(["mae", "boundary_mae", "texture_mae"], ascending=True).iloc[0]
    result = {
        "status": "complete", "internal_test_scenes": len(dataset), "candidate_epochs": list(CANDIDATES),
        "selected_by_internal_test": int(preference["epoch"]), "checkpoint_manifest": manifest,
        "table": str(OUTPUT / "internal_test_metrics.csv"), "by_mode": str(OUTPUT / "internal_test_by_mode.csv"),
    }
    (OUTPUT / "summary.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2), flush=True)


if __name__ == "__main__":
    main()

"""Verify that R100's positive texture operator improves recoverable-detail views."""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import numpy as np
import torch
from torch.utils.data import DataLoader


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "reports" / "texture_operator_sweep.json"


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


TRAINER = load_module("r100_texture_sweep_trainer", ROOT / "training" / "train_r100.py")
MODEL = load_module("r100_texture_sweep_model", ROOT / "model" / "r100_model.py")


def main() -> int:
    package, manifest, audit = TRAINER.preflight("smoke")
    if not audit.get("passed"):
        raise RuntimeError("Locked data audit failed")
    dataset = TRAINER.R100SceneDataset(package, manifest, "train", 128, 64, 1)
    indices: list[int] = []
    for index in range(len(dataset)):
        if dataset.role_at(index) not in {"textured_general_geometry", "difficult_contour", "clean_contour_anchor"}:
            continue
        item = dataset[index]
        if bool(item["detail_recovery_view"].all()):
            indices.append(index)
        if len(indices) == 12:
            break
    batch = next(iter(DataLoader(dataset, batch_sampler=[indices], num_workers=0)))
    device = torch.device("cuda:0")
    scenes, views = batch["source"].shape[:2]
    source = batch["source"].to(device).reshape(scenes * views, 1, 128, 128)
    target = batch["target"].to(device).reshape(scenes * views, 1, 128, 128)
    sdf = batch["sdf"].to(device).reshape(scenes * views, 1, 128, 128)
    core = slice(32, 96)
    rows = []
    for logit in (-12.0, -5.0, -3.5, -2.5, -1.5, -0.5, 0.5, 2.0):
        torch.manual_seed(1000053)
        model = MODEL.build_model(base=24).to(device).eval()
        with torch.no_grad():
            model.radiometry_head[-1].weight.zero_(); model.radiometry_head[-1].bias.zero_()
            model.denoise_head[-1].weight.zero_(); model.denoise_head[-1].bias.fill_(-12.0)
            model.edge_head[-1].weight.zero_(); model.edge_head[-1].bias.fill_(-12.0)
            model.texture_head[-1].weight.zero_(); model.texture_head[-1].bias.fill_(logit)
            details = model(source, return_details=True)
            pred = details["output"][..., core, core]
            raw = source[..., core, core]
            truth = target[..., core, core]
            material = (torch.abs(sdf[..., core, core]) >= 7.0).float()
            pred_fine = pred - TRAINER.lowpass(pred, 3)
            raw_fine = raw - TRAINER.lowpass(raw, 3)
            truth_fine = truth - TRAINER.lowpass(truth, 3)
            def weighted(error: torch.Tensor) -> float:
                return float((error * material).sum() / material.sum().clamp_min(1.0))
            rows.append({
                "texture_logit": logit,
                "coefficient_sum_mean": float(details["texture_coefficients"].sum(dim=1).mean()),
                "texture_change_gray": float(details["texture_delta"][..., core, core].abs().mean() * 255.0),
                "pixel_mae_gray": float((pred - truth).abs().mean() * 255.0),
                "material_pixel_mae_gray": weighted((pred - truth).abs()) * 255.0,
                "material_fine_mae_gray": weighted((pred_fine - truth_fine).abs()) * 255.0,
                "raw_material_fine_mae_gray": weighted((raw_fine - truth_fine).abs()) * 255.0,
            })
        del model
    best = min(rows, key=lambda row: row["material_fine_mae_gray"])
    report = {
        "experiment_id": TRAINER.DESIGN["experiment_id"],
        "detail_recovery_scene_count": len(indices),
        "views": int(scenes * views),
        "rows": rows,
        "best": best,
        "positive_texture_operation_is_useful": best["texture_logit"] > -10.0 and best["material_fine_mae_gray"] < rows[0]["material_fine_mae_gray"],
        "weights_saved": False,
    }
    OUTPUT.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

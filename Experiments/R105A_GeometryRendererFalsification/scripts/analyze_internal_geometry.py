from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import numpy as np
import torch


ROOT = Path(__file__).resolve().parents[1]
RUN_ALL_PATH = ROOT / "scripts" / "run_all.py"


def load_probe_module():
    spec = importlib.util.spec_from_file_location("r105a_run_all_internal", RUN_ALL_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot import {RUN_ALL_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def load_renderer(module, device: torch.device):
    steps = int(module.CONFIG["training"]["steps"])
    checkpoint = torch.load(
        ROOT / "weights" / f"renderer_step{steps:04d}.pth",
        map_location=device,
        weights_only=False,
    )
    model = module.ProbeModel("renderer").to(device)
    model.load_state_dict(checkpoint["model"], strict=True)
    model.eval()
    return model


@torch.inference_mode()
def predict_details(model, population, device):
    chunks = {name: [] for name in ["output", "sdf", "width", "inside", "outside"]}
    for start in range(0, population.source.shape[0], 16):
        indices = np.arange(start, min(population.source.shape[0], start + 16))
        batch = population.batch(indices, device)
        details = model(batch["source"])
        for name in chunks:
            chunks[name].append(details[name].cpu().numpy()[:, 0])
    return {name: np.concatenate(values, axis=0) for name, values in chunks.items()}


def correlation(x, y):
    x = np.asarray(x, dtype=np.float64)
    y = np.asarray(y, dtype=np.float64)
    valid = np.isfinite(x) & np.isfinite(y)
    if valid.sum() < 3 or np.std(x[valid]) < 1e-12 or np.std(y[valid]) < 1e-12:
        return 0.0
    return float(np.corrcoef(x[valid], y[valid])[0, 1])


def analyze_split(module, model, population, device):
    details = predict_details(model, population, device)
    true_sdf = population.sdf.numpy()[:, 0]
    true_mask = population.mask.numpy()[:, 0] >= 0.5
    true_width = population.width.numpy()[:, 0, 0, 0]
    true_inside = population.inside.numpy()[:, 0, 0, 0]
    true_outside = population.outside.numpy()[:, 0, 0, 0]
    output_rows = module.summarize_outputs({"renderer": details["output"]}, population)["renderer"]["per_image"]
    rows = []
    for index in range(population.source.shape[0]):
        band = np.abs(true_sdf[index]) <= 0.75
        inner = true_sdf[index] >= 2.0
        outer = true_sdf[index] <= -2.0
        predicted_mask = details["sdf"][index] >= 0.0
        intersection = np.logical_and(predicted_mask, true_mask[index]).sum()
        union = np.logical_or(predicted_mask, true_mask[index]).sum()
        rows.append(
            {
                "family": population.families[index],
                "boundary_sdf_signed_bias_px": float(np.median(details["sdf"][index][band])),
                "boundary_sdf_abs_error_px": float(np.median(np.abs(details["sdf"][index][band] - true_sdf[index][band]))),
                "sdf_zero_mask_iou": float(intersection / max(int(union), 1)),
                "width_abs_error_px": float(np.median(np.abs(details["width"][index][band] - true_width[index]))),
                "inside_level_abs_error_gray": float(np.median(np.abs(details["inside"][index][inner] - true_inside[index])) * 255.0),
                "outside_level_abs_error_gray": float(np.median(np.abs(details["outside"][index][outer] - true_outside[index])) * 255.0),
                "output_boundary_distance_px": output_rows[index]["boundary_distance_px"],
                "output_transition_center_error_px": output_rows[index]["transition_center_error_px"],
            }
        )

    keys = [key for key in rows[0] if key != "family"]
    def aggregate(subset):
        return {key: float(np.median([row[key] for row in subset])) for key in keys}
    family_summary = {
        family: aggregate([row for row in rows if row["family"] == family])
        for family in sorted(set(population.families))
    }
    abs_bias = [abs(row["boundary_sdf_signed_bias_px"]) for row in rows]
    return {
        "images": len(rows),
        "summary": aggregate(rows),
        "families": family_summary,
        "correlations": {
            "abs_boundary_sdf_bias_vs_output_center_error": correlation(
                abs_bias,
                [row["output_transition_center_error_px"] for row in rows],
            ),
            "boundary_sdf_abs_error_vs_output_boundary_distance": correlation(
                [row["boundary_sdf_abs_error_px"] for row in rows],
                [row["output_boundary_distance_px"] for row in rows],
            ),
        },
    }


def main() -> int:
    module = load_probe_module()
    device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")
    model = load_renderer(module, device)
    validation = module.build_population(int(module.CONFIG["data"]["validation_samples"]), "validation")
    test = module.build_population(int(module.CONFIG["data"]["test_samples"]), "test")
    result = {
        "status": "complete",
        "validation_seen_families": analyze_split(module, model, validation, device),
        "heldout_unseen_families": analyze_split(module, model, test, device),
    }
    output = ROOT / "results" / "internal_geometry_analysis.json"
    output.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Measure how each bounded R100 operator changes representative real images."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys

import cv2
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import torch
import torch.nn.functional as F
PROJECT_ROOT = Path(__file__).resolve().parents[3]


ROOT = Path(__file__).resolve().parents[1]
PROTOCOL_PATH = ROOT / "config" / "posttraining_validation_protocol.json"
DESIGN_PATH = ROOT / "config" / "experiment_design.json"
MODEL_PATH = ROOT / "model" / "r100_model.py"
OUTPUT = ROOT / "results" / "posttraining_validation" / "model_internal"


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


MODEL = load_module("r100_post_internal_model", MODEL_PATH)


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(path)


def read_gray(path: Path) -> np.ndarray:
    image = cv2.imdecode(np.fromfile(path, dtype=np.uint8), cv2.IMREAD_GRAYSCALE)
    if image is None:
        raise RuntimeError(path)
    return image


def mean_abs_gray(tensor: torch.Tensor) -> float:
    return float(tensor.abs().mean() * 255.0)


def energy_ratio(raw: np.ndarray, output: np.ndarray, sigma: float) -> float:
    raw_fine = raw - cv2.GaussianBlur(raw, (0, 0), sigma)
    out_fine = output - cv2.GaussianBlur(output, (0, 0), sigma)
    return float(np.mean(np.abs(out_fine)) / max(np.mean(np.abs(raw_fine)), 1e-9))


def main() -> None:
    if OUTPUT.exists() and any(OUTPUT.iterdir()):
        raise RuntimeError(f"Refusing to overwrite model-internal output: {OUTPUT}")
    OUTPUT.mkdir(parents=True, exist_ok=True)
    protocol = read_json(PROTOCOL_PATH)
    design = read_json(DESIGN_PATH)
    checkpoint = torch.load(Path(PROJECT_ROOT / protocol["checkpoint"]), map_location="cpu", weights_only=False)
    model = MODEL.build_model(base=int(design["architecture"]["model_width"]))
    model.load_state_dict(checkpoint[protocol["checkpoint_state"]], strict=True)
    device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")
    model.eval().to(device)
    halo = int(design["architecture"]["tile_contract"]["minimum_halo_px"])
    rows: list[dict[str, object]] = []
    for path in sorted((ROOT / "data" / "live_validation").glob("*.bmp")):
        raw_u8 = read_gray(path)
        raw = raw_u8.astype(np.float32) / 255.0
        source = torch.from_numpy(raw)[None, None].to(device)
        padded = F.pad(source, (halo, halo, halo, halo), mode="reflect")
        with torch.inference_mode():
            padded_details = model(padded, return_details=True)
        details = {name: value[..., halo:halo + raw.shape[0], halo:halo + raw.shape[1]] for name, value in padded_details.items()}
        output = details["output"]
        correction = details["correction"]
        edge_support = details["edge_support"]
        flat_mask = edge_support < 0.10
        edge_mask = edge_support > 0.50
        branch_names = ["low_delta", "denoise_delta", "edge_delta", "texture_delta"]
        branch_abs = {name: mean_abs_gray(details[name]) for name in branch_names}
        total_branch_abs = sum(branch_abs.values())
        correction_abs = mean_abs_gray(correction)
        raw_np = raw
        output_np = output[0, 0].cpu().numpy()
        row: dict[str, object] = {
            "image": path.stem,
            "height": raw.shape[0], "width": raw.shape[1],
            **{f"mean_abs_{name}_gray": value for name, value in branch_abs.items()},
            "mean_abs_correction_gray": correction_abs,
            "operator_cancellation_fraction": float(1.0 - correction_abs / max(total_branch_abs, 1e-9)),
            "fraction_abs_change_below_half_gray": float((correction.abs() * 255.0 < 0.5).float().mean()),
            "fraction_abs_change_above_one_gray": float((correction.abs() * 255.0 > 1.0).float().mean()),
            "flat_pixel_fraction": float(flat_mask.float().mean()),
            "edge_pixel_fraction": float(edge_mask.float().mean()),
            "flat_mean_abs_correction_gray": float(correction.abs()[flat_mask].mean() * 255.0) if flat_mask.any() else 0.0,
            "edge_mean_abs_correction_gray": float(correction.abs()[edge_mask].mean() * 255.0) if edge_mask.any() else 0.0,
            "mean_denoise_strength": float(details["denoise_strength"].mean()),
            "mean_edge_strength": float(details["edge_strength"].mean()),
            "mean_texture_coefficient_sum": float(details["texture_coefficients"].sum(dim=1).mean()),
            "fine_detail_ratio_sigma1": energy_ratio(raw_np, output_np, 1.0),
            "medium_detail_ratio_sigma2": energy_ratio(raw_np, output_np, 2.0),
            "output_low_clip_fraction": float((output <= 0.0).float().mean()),
            "output_high_clip_fraction": float((output >= 1.0).float().mean()),
            "transport_nonzero": int(torch.count_nonzero(details["transport_delta"])),
        }
        rows.append(row)
        print(json.dumps({"image": path.stem, "correction_gray": correction_abs, "branches": branch_abs, "fine_detail_ratio": row["fine_detail_ratio_sigma1"]}), flush=True)
    table = pd.DataFrame(rows)
    table.to_csv(OUTPUT / "operator_metrics.csv", index=False)

    plot_columns = ["mean_abs_low_delta_gray", "mean_abs_denoise_delta_gray", "mean_abs_edge_delta_gray", "mean_abs_texture_delta_gray", "mean_abs_correction_gray"]
    labels = ["Radiometry", "Denoise", "Edge", "Texture", "Net"]
    figure, axes = plt.subplots(2, 2, figsize=(11, 7), sharey=True)
    for axis, row in zip(axes.flat, rows):
        values = [float(row[column]) for column in plot_columns]
        axis.bar(labels, values, color=["#64748B", "#0EA5E9", "#F97316", "#8B5CF6", "#111827"])
        axis.set_title(str(row["image"]))
        axis.set_ylabel("mean absolute change (gray levels)")
        axis.tick_params(axis="x", rotation=20)
    figure.tight_layout()
    figure.savefig(OUTPUT / "operator_corrections.png", dpi=170)
    plt.close(figure)

    result = {
        "status": "complete", "checkpoint_epoch": int(checkpoint["epoch"]),
        "checkpoint_state": protocol["checkpoint_state"], "images": rows,
        "aggregate_median": {column: float(table[column].median()) for column in table.columns if column not in {"image"} and pd.api.types.is_numeric_dtype(table[column])},
        "notes": [
            "Operator magnitudes are measured on four representative real images with the formal reflect halo.",
            "Cancellation compares the sum of absolute operator changes with the final net change.",
            "Fine-detail ratios below one mean the final output contains less source-supported high-frequency energy than Raw.",
        ],
    }
    write_json(OUTPUT / "summary.json", result)


if __name__ == "__main__":
    main()

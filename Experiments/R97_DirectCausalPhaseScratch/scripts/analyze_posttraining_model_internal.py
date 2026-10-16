"""Inspect R97 checkpoint trajectory, final branch behavior, detail ROIs, and tiling parity."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys

import cv2
import numpy as np
import pandas as pd
from scipy.optimize import linear_sum_assignment
import torch


ROOT = Path(__file__).resolve().parents[1]
MODEL_PATH = ROOT / "model" / "r97_model.py"
INFERENCE_PATH = ROOT / "inference" / "reconstruct.py"
DESIGN_PATH = ROOT / "config" / "experiment_design.json"
PROTOCOL_PATH = ROOT / "config" / "posttraining_validation_protocol.json"
OUTPUT = ROOT / "results" / "posttraining_validation" / "model_internal"
LIVE = ROOT / "data" / "live_validation"
WEIGHTS = ROOT / "weights" / "formal" / "seed_970043" / "R97_scratch_seed970043_20260813_200802" / "weights"
TRAJECTORY_EPOCHS = [1, 4, 8, 12, 16, 20, 24, 28, 32, 36, 40, 44, 48]
IMAGE_NAMES = ["5x_dense_raw.bmp", "20x_mixed_raw.bmp", "50x_array_raw.bmp", "pillar_center9_50x_raw.bmp"]
ROI_SPECS = [
    ("5x_fine_grid", "5x_dense_raw.bmp", (80, 70, 150, 150)),
    ("5x_parallel_lines", "5x_dense_raw.bmp", (70, 320, 300, 130)),
    ("20x_square_edges", "20x_mixed_raw.bmp", (20, 35, 245, 220)),
    ("20x_round_and_lines", "20x_mixed_raw.bmp", (275, 20, 220, 455)),
    ("50x_pillar_defect", "50x_array_raw.bmp", (285, 0, 210, 185)),
    ("center9_pillars", "pillar_center9_50x_raw.bmp", (8, 25, 216, 195)),
]
BRANCHES = ["nuisance_delta", "radiometry_delta", "local_contrast_delta", "boundary_delta", "texture_delta"]


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


MODEL = load_module("r97_post_internal_model", MODEL_PATH)
INFERENCE = load_module("r97_post_internal_inference", INFERENCE_PATH)


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


def gradient_magnitude(image: np.ndarray) -> np.ndarray:
    smooth = cv2.GaussianBlur(image.astype(np.float32), (0, 0), 1.0)
    gx = cv2.Sobel(smooth, cv2.CV_32F, 1, 0, ksize=3)
    gy = cv2.Sobel(smooth, cv2.CV_32F, 0, 1, ksize=3)
    return cv2.magnitude(gx, gy)


def appearance_metrics(raw: np.ndarray, output: np.ndarray) -> dict[str, float]:
    raw_f, out_f = raw.astype(np.float32), output.astype(np.float32)
    difference = out_f - raw_f
    raw_edge, out_edge = gradient_magnitude(raw), gradient_magnitude(output)
    support = raw_edge >= float(np.percentile(raw_edge, 85))
    raw_fine = raw_f - cv2.GaussianBlur(raw_f, (0, 0), 2.0)
    out_fine = out_f - cv2.GaussianBlur(out_f, (0, 0), 2.0)
    return {
        "mean_signed_change_gray": float(difference.mean()),
        "mean_abs_change_gray": float(np.abs(difference).mean()),
        "p99_abs_change_gray": float(np.percentile(np.abs(difference), 99)),
        "edge_gain": float(np.median(out_edge[support]) / max(float(np.median(raw_edge[support])), 1e-9)),
        "fine_detail_energy_ratio": float(np.std(out_fine) / max(float(np.std(raw_fine)), 1e-9)),
        "dark_edge_fraction_over_10": float(np.mean(difference[support] < -10.0)),
        "bright_edge_fraction_over_10": float(np.mean(difference[support] > 10.0)),
    }


def load_model(epoch: int, device: torch.device, base: int):
    checkpoint = torch.load(WEIGHTS / f"epoch_{epoch:03d}.pth.tar", map_location="cpu", weights_only=False)
    if int(checkpoint["epoch"]) != epoch:
        raise RuntimeError(f"Checkpoint epoch mismatch: {epoch}")
    model = MODEL.build_model(base=base)
    model.load_state_dict(checkpoint["ema_state_dict"], strict=True)
    return model.eval().to(device)


def reconstruct(model, image: np.ndarray, device: torch.device) -> tuple[np.ndarray, torch.Tensor]:
    tensor = torch.from_numpy(image.astype(np.float32) / 255.0)[None, None].to(device)
    with torch.inference_mode():
        prediction = INFERENCE.reconstruct_tensor(model, tensor, core_size=512, halo=192, tile_batch=1)[0, 0]
    output = np.rint(prediction.clamp(0, 1).cpu().numpy() * 255.0).astype(np.uint8)
    return output, tensor


def exact_details(model, tensor: torch.Tensor) -> tuple[dict[str, np.ndarray], float, float]:
    canvas, (height, width, _grid_h, _grid_w) = INFERENCE.canonical_canvas(tensor, 512, 192)
    with torch.inference_mode():
        details_t = model(canvas, return_details=True)
        tiled = INFERENCE.reconstruct_tensor(model, tensor, core_size=512, halo=192, tile_batch=1)
    cropped = {
        name: value[..., 192:192 + height, 192:192 + width][0].float().cpu().numpy()
        for name, value in details_t.items()
    }
    direct_output = cropped["output"][0]
    tiled_output = tiled[0, 0].float().cpu().numpy()
    return cropped, float(np.max(np.abs(direct_output - tiled_output))), float(np.mean(np.abs(direct_output - tiled_output)))


def branch_records(image_name: str, raw: np.ndarray, details: dict[str, np.ndarray]) -> tuple[list[dict], dict]:
    raw_edge = gradient_magnitude(raw)
    edge = raw_edge >= float(np.percentile(raw_edge, 85))
    flat = raw_edge <= float(np.percentile(raw_edge, 35))
    rows: list[dict] = []
    arrays: list[np.ndarray] = []
    for branch in BRANCHES:
        delta = details[branch][0]
        arrays.append(delta)
        rows.append({
            "image": image_name,
            "branch": branch,
            "mean_signed_gray": float(delta.mean() * 255.0),
            "mean_abs_gray": float(np.abs(delta).mean() * 255.0),
            "p95_abs_gray": float(np.percentile(np.abs(delta), 95) * 255.0),
            "max_abs_gray": float(np.max(np.abs(delta)) * 255.0),
            "edge_mean_abs_gray": float(np.abs(delta[edge]).mean() * 255.0),
            "flat_mean_abs_gray": float(np.abs(delta[flat]).mean() * 255.0),
        })
    stack = np.stack(arrays)
    summed = stack.sum(axis=0)
    total_abs = np.abs(stack).sum(axis=0)
    mean_total_abs = float(total_abs.mean())
    cancellation = 1.0 - float(np.abs(summed).mean()) / max(mean_total_abs, 1e-12)
    correction = details["correction"][0]
    output = details["output"][0]
    raw_f = raw.astype(np.float32) / 255.0
    pairwise: dict[str, float] = {}
    for i, first in enumerate(BRANCHES):
        for j in range(i + 1, len(BRANCHES)):
            second = BRANCHES[j]
            a, b = stack[i].ravel(), stack[j].ravel()
            denominator = float(a.std() * b.std())
            pairwise[f"{first}__{second}"] = float(np.corrcoef(a, b)[0, 1]) if denominator > 1e-12 else 0.0
    summary = {
        "image": image_name,
        "mean_abs_sum_of_branches_gray": mean_total_abs * 255.0,
        "mean_abs_net_before_global_bound_gray": float(np.abs(summed).mean() * 255.0),
        "mean_abs_final_correction_gray": float(np.abs(correction).mean() * 255.0),
        "cancellation_fraction": cancellation,
        "global_correction_bound_fraction": float(np.mean(np.abs(summed) >= 0.34 - 1e-7)),
        "output_low_clip_fraction": float(np.mean(output <= 0.0)),
        "output_high_clip_fraction": float(np.mean(output >= 1.0)),
        "identity_exact_fraction": float(np.mean(np.abs(output - raw_f) < (0.5 / 255.0))),
        "boundary_support_edge_median": float(np.median(details["boundary_support"][0][edge])),
        "boundary_support_flat_median": float(np.median(details["boundary_support"][0][flat])),
        "pairwise_branch_correlations": pairwise,
    }
    return rows, summary


def display_delta(delta: np.ndarray, gain: float = 5.0) -> np.ndarray:
    return np.clip(128.0 + delta * 255.0 * gain, 0, 255).astype(np.uint8)


def label(image: np.ndarray, text: str) -> np.ndarray:
    panel = cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)
    cv2.rectangle(panel, (0, 0), (panel.shape[1], 36), (0, 0, 0), -1)
    cv2.putText(panel, text, (7, 27), cv2.FONT_HERSHEY_SIMPLEX, .65, (255, 255, 255), 2, cv2.LINE_AA)
    return panel


def save_branch_panel(path: Path, raw: np.ndarray, details: dict[str, np.ndarray]) -> None:
    output = np.rint(np.clip(details["output"][0], 0, 1) * 255.0).astype(np.uint8)
    difference = np.clip(np.abs(output.astype(np.int16) - raw.astype(np.int16)) * 8, 0, 255).astype(np.uint8)
    panels = [label(raw, "Raw"), label(output, "R97 E48"), label(difference, "Abs diff x8")]
    for branch in BRANCHES:
        panels.append(label(display_delta(details[branch][0]), branch.replace("_delta", " x5")))
    path.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(path), np.concatenate(panels, axis=1))


def components(image: np.ndarray, threshold: float, area_min: float, area_max: float) -> tuple[np.ndarray, np.ndarray]:
    mask = (image.astype(np.float32) < threshold).astype(np.uint8)
    count, _labels, stats, centroids = cv2.connectedComponentsWithStats(mask, connectivity=8)
    areas = stats[1:, cv2.CC_STAT_AREA].astype(float)
    centers = centroids[1:].astype(float)
    keep = (areas >= area_min) & (areas <= area_max)
    return centers[keep], areas[keep]


def component_geometry(
    image_name: str,
    raw: np.ndarray,
    output: np.ndarray,
    expected: int,
    area_min: float,
    area_max: float,
) -> dict:
    threshold, _ = cv2.threshold(raw, 0, 255, cv2.THRESH_BINARY_INV | cv2.THRESH_OTSU)
    raw_centers, raw_areas = components(raw, float(threshold), area_min, area_max)
    out_centers, out_areas = components(output, float(threshold), area_min, area_max)
    if len(raw_centers) != expected or len(out_centers) != expected:
        return {
            "image": image_name,
            "status": "component_count_mismatch",
            "threshold": float(threshold),
            "expected": expected,
            "raw_components": len(raw_centers),
            "output_components": len(out_centers),
        }
    distances = np.linalg.norm(raw_centers[:, None, :] - out_centers[None, :, :], axis=2)
    raw_index, out_index = linear_sum_assignment(distances)
    displacement = out_centers[out_index] - raw_centers[raw_index]
    shift = np.linalg.norm(displacement, axis=1)
    area_change = (out_areas[out_index] - raw_areas[raw_index]) / raw_areas[raw_index] * 100.0
    return {
        "image": image_name,
        "status": "complete",
        "threshold": float(threshold),
        "components": expected,
        "mean_centroid_shift_px": float(shift.mean()),
        "max_centroid_shift_px": float(shift.max()),
        "mean_dx_px": float(displacement[:, 0].mean()),
        "mean_dy_px": float(displacement[:, 1].mean()),
        "mean_area_change_pct": float(area_change.mean()),
        "max_abs_area_change_pct": float(np.abs(area_change).max()),
    }


def roi_metrics(name: str, raw: np.ndarray, output: np.ndarray, roi: tuple[int, int, int, int]) -> dict:
    x, y, width, height = roi
    a = raw[y:y + height, x:x + width]
    b = output[y:y + height, x:x + width]
    raw_edge, out_edge = gradient_magnitude(a), gradient_magnitude(b)
    raw_fine = a.astype(np.float32) - cv2.GaussianBlur(a.astype(np.float32), (0, 0), 2.0)
    out_fine = b.astype(np.float32) - cv2.GaussianBlur(b.astype(np.float32), (0, 0), 2.0)
    return {
        "region": name,
        "roi_xywh": list(roi),
        "mae_gray": float(np.mean(np.abs(b.astype(np.float32) - a.astype(np.float32)))),
        "p99_change_gray": float(np.percentile(np.abs(b.astype(np.float32) - a.astype(np.float32)), 99)),
        "edge_strength_change_percent": float((out_edge.mean() / max(float(raw_edge.mean()), 1e-9) - 1.0) * 100.0),
        "fine_content_change_percent": float((np.std(out_fine) / max(float(np.std(raw_fine)), 1e-9) - 1.0) * 100.0),
    }


def save_roi_panel(path: Path, raw: np.ndarray, output: np.ndarray, roi: tuple[int, int, int, int]) -> np.ndarray:
    x, y, width, height = roi
    a = raw[y:y + height, x:x + width]
    b = output[y:y + height, x:x + width]
    difference = np.clip(np.abs(b.astype(np.int16) - a.astype(np.int16)) * 8, 0, 255).astype(np.uint8)
    scale = max(1, int(420 / max(width, height)))
    size = (width * scale, height * scale)
    panels = [
        label(cv2.resize(a, size, interpolation=cv2.INTER_NEAREST), "Raw"),
        label(cv2.resize(b, size, interpolation=cv2.INTER_NEAREST), "R97 E48"),
        label(cv2.resize(difference, size, interpolation=cv2.INTER_NEAREST), "Abs diff x8"),
    ]
    sheet = np.concatenate(panels, axis=1)
    path.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(path), sheet)
    return sheet


def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    protocol = read_json(PROTOCOL_PATH)
    if int(protocol["primary_checkpoint_epoch"]) != 48:
        raise RuntimeError("R97 endpoint is not fixed at E48")
    design = read_json(DESIGN_PATH)
    base = int(design["architecture"]["model_width"])
    device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")
    images = {name: read_gray(LIVE / name) for name in IMAGE_NAMES}
    trajectory: list[dict] = []
    previous_outputs: dict[str, np.ndarray] = {}
    for epoch in TRAJECTORY_EPOCHS:
        model = load_model(epoch, device, base)
        for image_name, raw in images.items():
            output, _tensor = reconstruct(model, raw, device)
            row = {"epoch": epoch, "image": image_name, **appearance_metrics(raw, output)}
            row["mean_abs_change_from_previous_checkpoint_gray"] = (
                0.0 if image_name not in previous_outputs
                else float(np.mean(np.abs(output.astype(np.float32) - previous_outputs[image_name].astype(np.float32))))
            )
            trajectory.append(row)
            previous_outputs[image_name] = output
        del model
        if device.type == "cuda":
            torch.cuda.empty_cache()
        print(f"[internal] trajectory epoch {epoch}", flush=True)
    pd.DataFrame(trajectory).to_csv(OUTPUT / "checkpoint_trajectory.csv", index=False)

    model = load_model(48, device, base)
    outputs: dict[str, np.ndarray] = {}
    branch_rows: list[dict] = []
    branch_summaries: list[dict] = []
    parity: list[dict] = []
    for image_name, raw in images.items():
        output, tensor = reconstruct(model, raw, device)
        outputs[image_name] = output
        details, maximum, mean = exact_details(model, tensor)
        parity.append({"image": image_name, "max_abs_float_difference": maximum, "mean_abs_float_difference": mean})
        rows, summary = branch_records(image_name, raw, details)
        branch_rows.extend(rows)
        branch_summaries.append(summary)
        save_branch_panel(OUTPUT / "figures" / f"{Path(image_name).stem}_branches.png", raw, details)
    pd.DataFrame(branch_rows).to_csv(OUTPUT / "branch_metrics.csv", index=False)
    write_json(OUTPUT / "branch_summary.json", branch_summaries)

    roi_rows: list[dict] = []
    roi_panels: list[np.ndarray] = []
    for name, image_name, roi in ROI_SPECS:
        raw, output = images[image_name], outputs[image_name]
        roi_rows.append({"image": image_name, **roi_metrics(name, raw, output, roi)})
        roi_panels.append(save_roi_panel(OUTPUT / "figures" / "detail_rois" / f"{name}.png", raw, output, roi))
    target_width = max(panel.shape[1] for panel in roi_panels)
    normalized = [cv2.copyMakeBorder(panel, 0, 0, 0, target_width - panel.shape[1], cv2.BORDER_CONSTANT) for panel in roi_panels]
    cv2.imwrite(str(OUTPUT / "figures" / "detail_roi_contact_sheet.png"), np.concatenate(normalized, axis=0))
    pd.DataFrame(roi_rows).to_csv(OUTPUT / "detail_roi_metrics.csv", index=False)

    geometry = [
        component_geometry("50x_array_raw.bmp", images["50x_array_raw.bmp"], outputs["50x_array_raw.bmp"], 49, 450.0, 2200.0),
        component_geometry("pillar_center9_50x_raw.bmp", images["pillar_center9_50x_raw.bmp"], outputs["pillar_center9_50x_raw.bmp"], 9, 450.0, 2200.0),
    ]
    write_json(OUTPUT / "component_geometry.json", geometry)

    large_path = Path(r"D:\GMM_2_Final\20260704_20x_5x_analysis\raw_inputs\5x_0p5um\bmp\frame_0000.bmp")
    large = read_gray(large_path)
    crop = large[256:1280, 512:1536]
    tensor = torch.from_numpy(crop.astype(np.float32) / 255.0)[None, None].to(device)
    with torch.inference_mode():
        tiled = INFERENCE.reconstruct_tensor(model, tensor, core_size=512, halo=192, tile_batch=1)
        full = INFERENCE.reconstruct_full_reference(model, tensor, core_size=512, halo=192)
    difference = (tiled.float() - full.float()).abs().cpu().numpy()[0, 0]
    seam = np.zeros(difference.shape, dtype=bool)
    seam[:, 510:515] = True
    seam[510:515, :] = True
    reference = np.ones(difference.shape, dtype=bool)
    reference[:, 500:525] = False
    reference[500:525, :] = False
    large_parity = {
        "source": str(large_path),
        "crop_xywh": [512, 256, 1024, 1024],
        "max_abs_float_difference": float(difference.max()),
        "mean_abs_float_difference": float(difference.mean()),
        "seam_mean_abs_difference": float(difference[seam].mean()),
        "nonseam_mean_abs_difference": float(difference[reference].mean()),
    }
    summary = {
        "status": "complete",
        "checkpoint_epoch": 48,
        "checkpoint_state": protocol["checkpoint_state"],
        "small_image_full_vs_tiled": parity,
        "large_real_crop_full_vs_tiled": large_parity,
        "component_geometry": geometry,
        "branch_summaries": branch_summaries,
        "trajectory_epochs": TRAJECTORY_EPOCHS,
    }
    write_json(OUTPUT / "summary.json", summary)
    print(json.dumps({"status": "complete", "large_real_crop_full_vs_tiled": large_parity}, indent=2), flush=True)


if __name__ == "__main__":
    main()

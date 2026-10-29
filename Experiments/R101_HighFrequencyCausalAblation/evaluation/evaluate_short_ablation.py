"""Evaluate R101 A/B/C on held-out synthetic, real microscopy, motion and tiling."""
from __future__ import annotations

import argparse
import csv
import importlib.util
import json
import math
import os
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

import cv2
import matplotlib.pyplot as plt
import numpy as np
import torch
from torch import nn
PROJECT_ROOT = Path(__file__).resolve().parents[3]


ROOT = Path(__file__).resolve().parents[1]
MODEL_PATH = ROOT / "model" / "prototype_models.py"
RECONSTRUCT_PATH = Path(str(PROJECT_ROOT / 'Experiments/R100_CausalOperatorScratch/inference/reconstruct.py'))


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load module: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


MODELS = load_module("r101_eval_models", MODEL_PATH)
RECONSTRUCT = load_module("r101_eval_reconstruct", RECONSTRUCT_PATH)


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    os.replace(temporary, path)


def read_gray(path: Path) -> np.ndarray:
    # cv2.imread uses the active Windows code page and can fail on Chinese paths.
    encoded = np.fromfile(path, dtype=np.uint8)
    image = cv2.imdecode(encoded, cv2.IMREAD_UNCHANGED)
    if image is None:
        raise FileNotFoundError(path)
    if image.ndim == 3:
        image = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    if image.dtype == np.uint16:
        return image.astype(np.float32) / 65535.0
    return image.astype(np.float32) / 255.0


def highpass(image: np.ndarray, sigma: float = 1.0) -> np.ndarray:
    return image - cv2.GaussianBlur(image, (0, 0), sigma, borderType=cv2.BORDER_REFLECT_101)


def fine_ratio(reference: np.ndarray, candidate: np.ndarray, mask: np.ndarray | None = None) -> float:
    left, right = highpass(reference), highpass(candidate)
    if mask is not None:
        left, right = left[mask], right[mask]
    return float(np.sqrt(np.mean(right * right) + 1e-12) / np.sqrt(np.mean(left * left) + 1e-12))


def complex_error(target: np.ndarray, output: np.ndarray) -> float:
    tf = np.fft.rfft2(target)
    of = np.fft.rfft2(output)
    fy = np.abs(np.fft.fftfreq(target.shape[0]))[:, None]
    fx = np.abs(np.fft.rfftfreq(target.shape[1]))[None, :]
    radius = np.sqrt(fx * fx + fy * fy)
    selected = radius >= 0.12
    return float(np.mean(np.abs(of[selected] - tf[selected])) / (np.mean(np.abs(tf[selected])) + 1e-8))


def crossing(x: np.ndarray, y: np.ndarray, level: float) -> float:
    if len(x) < 2:
        return float("nan")
    y = np.maximum.accumulate(y)
    if level < float(y[0]) or level > float(y[-1]):
        return float("nan")
    return float(np.interp(level, y, x))


def profile_metrics(sdf: np.ndarray, occupancy: np.ndarray) -> dict[str, float]:
    centers = np.arange(-5.0, 5.0001, 0.20)
    profile = []
    valid_centers = []
    for center in centers:
        selected = np.abs(sdf - center) < 0.10
        if int(np.sum(selected)) >= 24:
            valid_centers.append(center)
            profile.append(float(np.median(occupancy[selected])))
    x = np.asarray(valid_centers, np.float32)
    y = np.asarray(profile, np.float32)
    if len(y):
        y = cv2.GaussianBlur(y.reshape(1, -1), (0, 0), 0.8, borderType=cv2.BORDER_REPLICATE).reshape(-1)
    d10, d50, d90 = crossing(x, y, 0.10), crossing(x, y, 0.50), crossing(x, y, 0.90)
    return {"d10": d10, "d50": d50, "d90": d90, "width": d90 - d10 if np.isfinite(d10 + d90) else float("nan")}


def contour_distance(mask: np.ndarray, occupancy: np.ndarray) -> float:
    truth = (mask >= 0.5).astype(np.uint8)
    predicted = (occupancy >= 0.5).astype(np.uint8)
    kernel = np.ones((3, 3), np.uint8)
    truth_edge = cv2.morphologyEx(truth, cv2.MORPH_GRADIENT, kernel) > 0
    pred_edge = cv2.morphologyEx(predicted, cv2.MORPH_GRADIENT, kernel) > 0
    if not truth_edge.any() or not pred_edge.any():
        return 99.0
    distance_to_truth = cv2.distanceTransform((~truth_edge).astype(np.uint8), cv2.DIST_L2, 5)
    distance_to_pred = cv2.distanceTransform((~pred_edge).astype(np.uint8), cv2.DIST_L2, 5)
    return float(0.5 * (np.mean(distance_to_truth[pred_edge]) + np.mean(distance_to_pred[truth_edge])))


def normalized_occupancy(image: np.ndarray, foreground: float, background: float) -> np.ndarray:
    return (image - background) / (foreground - background + math.copysign(1e-6, foreground - background))


@torch.inference_mode()
def predict_array(model: nn.Module, images: np.ndarray, device: torch.device, batch_size: int = 8) -> np.ndarray:
    outputs = []
    model.eval()
    for start in range(0, len(images), batch_size):
        tensor = torch.from_numpy(np.asarray(images[start:start + batch_size], dtype=np.float32))[:, None].to(device)
        tensor = tensor.contiguous(memory_format=torch.channels_last)
        outputs.append(model(tensor).float().cpu().numpy()[:, 0])
    return np.concatenate(outputs, axis=0)


def load_models(config: dict[str, Any], device: torch.device) -> dict[str, nn.Module]:
    result = {}
    for arm in ("A", "B", "C"):
        checkpoint_path = ROOT / "weights" / f"arm_{arm}" / "latest.pth.tar"
        if not checkpoint_path.is_file():
            raise FileNotFoundError(checkpoint_path)
        checkpoint = torch.load(checkpoint_path, map_location="cpu", weights_only=False)
        if checkpoint.get("arm") != arm or int(checkpoint.get("step", -1)) != int(config["training"]["steps_per_arm"]):
            raise RuntimeError(f"Invalid final checkpoint for arm {arm}")
        model = MODELS.build_model(arm, base=int(config["training"]["model_width"]))
        model.load_state_dict(checkpoint["model"], strict=True)
        result[arm] = model.to(device).to(memory_format=torch.channels_last).eval()
    return result


def synthetic_evaluation(
    models: dict[str, nn.Module], arrays: dict[str, np.ndarray], device: torch.device,
) -> tuple[dict[str, Any], list[dict[str, Any]], dict[str, np.ndarray]]:
    indices = np.flatnonzero(arrays["split"] == 1)
    outputs = {arm: predict_array(model, arrays["source"][indices], device) for arm, model in models.items()}
    rows: list[dict[str, Any]] = []
    for local_index, array_index in enumerate(indices):
        target = arrays["target"][array_index].astype(np.float32)
        source = arrays["source"][array_index].astype(np.float32)
        mask = arrays["mask"][array_index].astype(np.float32)
        sdf = arrays["sdf"][array_index].astype(np.float32)
        foreground = float(arrays["foreground"][array_index])
        background = float(arrays["background"][array_index])
        target_occ = normalized_occupancy(target, foreground, background)
        target_profile = profile_metrics(sdf, target_occ)
        for arm in ("A", "B", "C"):
            output = outputs[arm][local_index]
            occupancy = normalized_occupancy(output, foreground, background)
            output_profile = profile_metrics(sdf, occupancy)
            boundary_region = np.abs(sdf) <= 4.0
            row = {
                "arm": arm,
                "scene_id": int(arrays["scene_id"][array_index]),
                "observation": int(arrays["observation"][array_index]),
                "identity": int(arrays["identity"][array_index]),
                "shape_family": int(arrays["shape_family"][array_index]),
                "mae_gray": float(np.mean(np.abs(output - target)) * 255.0),
                "boundary_center_bias_px": float(output_profile["d50"] - target_profile["d50"]),
                "boundary_center_abs_px": float(abs(output_profile["d50"] - target_profile["d50"])),
                "contour_distance_px": contour_distance(mask, occupancy),
                "transition_width_px": float(output_profile["width"]),
                "target_transition_width_px": float(target_profile["width"]),
                "transition_width_abs_error_px": float(abs(output_profile["width"] - target_profile["width"])),
                "complex_high_frequency_error": complex_error(target, output),
                "fine_energy_ratio_to_target": fine_ratio(target, output),
                "fine_energy_ratio_to_source": fine_ratio(source, output),
                "halo_fraction": float(np.mean(((occupancy < -0.05) | (occupancy > 1.05)) & boundary_region)),
            }
            rows.append(row)

    aggregates: dict[str, Any] = {}
    lower_metrics = ["mae_gray", "boundary_center_abs_px", "contour_distance_px", "transition_width_abs_error_px", "complex_high_frequency_error", "halo_fraction"]
    for arm in ("A", "B", "C"):
        selected = [row for row in rows if row["arm"] == arm]
        aggregates[arm] = {
            metric: float(np.nanmedian([row[metric] for row in selected])) for metric in lower_metrics
        }
        aggregates[arm].update({
            "boundary_center_bias_px": float(np.nanmedian([row["boundary_center_bias_px"] for row in selected])),
            "transition_width_px": float(np.nanmedian([row["transition_width_px"] for row in selected])),
            "target_transition_width_px": float(np.nanmedian([row["target_transition_width_px"] for row in selected])),
            "fine_energy_ratio_to_target": float(np.nanmedian([row["fine_energy_ratio_to_target"] for row in selected])),
            "fine_energy_ratio_to_source": float(np.nanmedian([row["fine_energy_ratio_to_source"] for row in selected])),
            "sample_count": len(selected),
        })

    motion_rows = []
    for scene_id in sorted(set(int(value) for value in arrays["scene_id"][indices])):
        local_positions = [position for position, array_index in enumerate(indices) if int(arrays["scene_id"][array_index]) == scene_id]
        if len(local_positions) != 2:
            continue
        p0, p1 = local_positions
        t0 = arrays["target"][indices[p0]].astype(np.float32)
        t1 = arrays["target"][indices[p1]].astype(np.float32)
        target_shift, target_response = cv2.phaseCorrelate(t0, t1)
        for arm in ("A", "B", "C"):
            measured, response = cv2.phaseCorrelate(outputs[arm][p0], outputs[arm][p1])
            error = math.hypot(measured[0] - target_shift[0], measured[1] - target_shift[1])
            motion_rows.append({"arm": arm, "scene_id": scene_id, "target_dx": target_shift[0], "target_dy": target_shift[1], "measured_dx": measured[0], "measured_dy": measured[1], "step_error_px": error, "response": response, "target_response": target_response})
    for arm in ("A", "B", "C"):
        selected = [row for row in motion_rows if row["arm"] == arm]
        aggregates[arm]["known_motion_step_mae_px"] = float(np.mean([row["step_error_px"] for row in selected]))
        aggregates[arm]["known_motion_step_p95_px"] = float(np.quantile([row["step_error_px"] for row in selected], 0.95))
    return aggregates, rows + motion_rows, outputs


def letterbox(image: np.ndarray, size: int = 384) -> np.ndarray:
    gray = np.clip(image * 255.0, 0, 255).astype(np.uint8)
    scale = min(size / gray.shape[1], size / gray.shape[0])
    resized = cv2.resize(gray, (max(1, int(gray.shape[1] * scale)), max(1, int(gray.shape[0] * scale))), interpolation=cv2.INTER_AREA)
    canvas = np.zeros((size, size), np.uint8)
    y0, x0 = (size - resized.shape[0]) // 2, (size - resized.shape[1]) // 2
    canvas[y0:y0 + resized.shape[0], x0:x0 + resized.shape[1]] = resized
    return canvas


def labeled_panel(image: np.ndarray, label: str, size: int = 384) -> np.ndarray:
    panel = cv2.cvtColor(letterbox(image, size), cv2.COLOR_GRAY2BGR)
    cv2.rectangle(panel, (0, 0), (size, 28), (0, 0, 0), -1)
    cv2.putText(panel, label, (8, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 1, cv2.LINE_AA)
    return panel


def real_evaluation(models: dict[str, nn.Module], config: dict[str, Any], device: torch.device) -> tuple[dict[str, Any], dict[str, list[np.ndarray]]]:
    directory = Path(config["evaluation"]["real_live_validation_dir"])
    paths = sorted(path for path in directory.iterdir() if path.suffix.lower() in {".bmp", ".png", ".tif", ".tiff"})
    per_arm: dict[str, list[dict[str, float]]] = defaultdict(list)
    outputs_by_image: dict[str, list[np.ndarray]] = {}
    montage_rows = []
    for path in paths:
        raw = read_gray(path)
        arm_outputs = {}
        for arm, model in models.items():
            arm_outputs[arm] = predict_array(model, raw[None], device, batch_size=1)[0]
            gx = cv2.Sobel(cv2.GaussianBlur(raw, (0, 0), 0.8), cv2.CV_32F, 1, 0, ksize=3)
            gy = cv2.Sobel(cv2.GaussianBlur(raw, (0, 0), 0.8), cv2.CV_32F, 0, 1, ksize=3)
            magnitude = np.sqrt(gx * gx + gy * gy)
            strong = magnitude >= np.quantile(magnitude, 0.90)
            nonedge = ~strong
            out = arm_outputs[arm]
            per_arm[arm].append({
                "fine_ratio_to_raw": fine_ratio(raw, out),
                "nonedge_fine_ratio_to_raw": fine_ratio(raw, out, nonedge),
                "strong_edge_fine_ratio_to_raw": fine_ratio(raw, out, strong),
                "mean_abs_change_gray": float(np.mean(np.abs(out - raw)) * 255.0),
                "off_range_fraction": float(np.mean((out <= 1e-5) | (out >= 1.0 - 1e-5))),
            })
        outputs_by_image[path.name] = [raw, arm_outputs["A"], arm_outputs["B"], arm_outputs["C"]]
        montage_rows.append(np.concatenate([labeled_panel(raw, f"{path.stem} Raw"), labeled_panel(arm_outputs["A"], "Arm A"), labeled_panel(arm_outputs["B"], "Arm B"), labeled_panel(arm_outputs["C"], "Arm C")], axis=1))
    montage_path = ROOT / "results" / "real_live_comparison.png"
    montage_path.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(montage_path), np.concatenate(montage_rows, axis=0))
    summary = {}
    for arm in ("A", "B", "C"):
        summary[arm] = {metric: float(np.median([row[metric] for row in per_arm[arm]])) for metric in per_arm[arm][0]}
        summary[arm]["image_count"] = len(per_arm[arm])
    return summary, outputs_by_image


def motion_sequence_evaluation(models: dict[str, nn.Module], config: dict[str, Any], device: torch.device) -> dict[str, Any]:
    directory = Path(config["evaluation"]["real_motion_sequence_dir"])
    paths = sorted(path for path in directory.iterdir() if path.is_file() and path.suffix.lower() in {".bmp", ".png", ".tif", ".tiff"})
    if len(paths) < 2:
        return {"status": "unavailable", "reason": "fewer than two top-level images"}
    raw_images = [read_gray(path) for path in paths]
    sequence_outputs = {"Raw": raw_images}
    for arm, model in models.items():
        sequence_outputs[arm] = [predict_array(model, image[None], device, batch_size=1)[0] for image in raw_images]
    summary: dict[str, Any] = {"status": "complete", "image_count": len(paths), "external_gmf_used": False, "method": "phase correlation on consecutive full frames", "paths": [str(path) for path in paths]}
    for method, images in sequence_outputs.items():
        steps = []
        responses = []
        for left, right in zip(images[:-1], images[1:]):
            shift, response = cv2.phaseCorrelate(left, right)
            steps.append([float(shift[0]), float(shift[1])])
            responses.append(float(response))
        vectors = np.asarray(steps, np.float64)
        magnitudes = np.linalg.norm(vectors, axis=1)
        summary[method] = {
            "median_dx_px": float(np.median(vectors[:, 0])),
            "median_dy_px": float(np.median(vectors[:, 1])),
            "step_magnitude_median_px": float(np.median(magnitudes)),
            "step_magnitude_std_px": float(np.std(magnitudes, ddof=1)) if len(magnitudes) > 1 else 0.0,
            "response_median": float(np.median(responses)),
            "steps": steps,
        }
    raw_vectors = np.asarray(summary["Raw"]["steps"])
    for arm in ("A", "B", "C"):
        vectors = np.asarray(summary[arm]["steps"])
        summary[arm]["paired_vector_difference_from_raw_median_px"] = float(np.median(np.linalg.norm(vectors - raw_vectors, axis=1)))
    return summary


@torch.inference_mode()
def tiling_evaluation(models: dict[str, nn.Module], config: dict[str, Any], device: torch.device) -> dict[str, Any]:
    directory = Path(config["evaluation"]["real_live_validation_dir"])
    path = sorted(path for path in directory.iterdir() if path.suffix.lower() in {".bmp", ".png", ".tif", ".tiff"})[0]
    raw = read_gray(path)
    tensor = torch.from_numpy(raw)[None, None].to(device)
    core = int(config["evaluation"]["tile_core_size"])
    halo = int(config["evaluation"]["tile_halo"])
    summary = {"image": str(path), "core_size": core, "halo": halo}
    for arm, model in models.items():
        full = RECONSTRUCT.reconstruct_full_reference(model, tensor, core_size=core, halo=halo)
        tiled = RECONSTRUCT.reconstruct_tensor(model, tensor, core_size=core, halo=halo, tile_batch=1)
        difference = (full - tiled).abs().float()
        summary[arm] = {"max_difference_gray": float(difference.max() * 255.0), "mean_difference_gray": float(difference.mean() * 255.0)}
    return summary


def save_rows(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        return
    fields = sorted(set().union(*(row.keys() for row in rows)))
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def plot_training(config: dict[str, Any]) -> str:
    seed = int(config["training"]["seed"])
    figure, axes = plt.subplots(1, 3, figsize=(15, 4.5), dpi=160)
    for arm in ("A", "B", "C"):
        path = ROOT / "runs" / f"ablation_seed{seed}" / f"arm_{arm}" / "training_log.csv"
        rows = list(csv.DictReader(path.open("r", encoding="utf-8")))
        step = np.asarray([int(row["step"]) for row in rows])
        for axis, metric in zip(axes, ("total", "boundary", "detail")):
            values = np.asarray([float(row[metric]) for row in rows])
            kernel = np.ones(15) / 15.0
            smooth = np.convolve(values, kernel, mode="same")
            axis.plot(step[7:-7], smooth[7:-7], label=f"Arm {arm}")
            axis.set_title(metric)
            axis.set_xlabel("step")
            axis.grid(alpha=0.25)
    axes[0].legend()
    figure.tight_layout()
    path = ROOT / "results" / "training_curves.png"
    figure.savefig(path)
    plt.close(figure)
    return str(path)


def continuous_rank_score(summary: dict[str, Any]) -> tuple[str, dict[str, float]]:
    lower = [
        ("synthetic", "boundary_center_abs_px"),
        ("synthetic", "transition_width_abs_error_px"),
        ("synthetic", "complex_high_frequency_error"),
        ("synthetic", "halo_fraction"),
        ("synthetic", "known_motion_step_mae_px"),
        ("tile", "mean_difference_gray"),
    ]
    higher = [("real", "fine_ratio_to_raw"), ("real", "nonedge_fine_ratio_to_raw")]
    scores = {arm: 0.0 for arm in ("A", "B", "C")}
    for section, metric in lower:
        values = {arm: float(summary[section][arm][metric]) for arm in scores}
        ordered = sorted(values, key=values.get)
        for rank, arm in enumerate(ordered):
            scores[arm] += rank
    for section, metric in higher:
        values = {arm: float(summary[section][arm][metric]) for arm in scores}
        ordered = sorted(values, key=values.get, reverse=True)
        for rank, arm in enumerate(ordered):
            scores[arm] += rank
    recommended = min(scores, key=scores.get)
    return recommended, scores


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=ROOT / "config" / "experiment.json")
    parser.add_argument("--device", default="cuda:0")
    args = parser.parse_args()
    config = json.loads(args.config.read_text(encoding="utf-8"))
    device = torch.device(args.device if torch.cuda.is_available() else "cpu")
    with np.load(ROOT / "data" / "continuous_pairs.npz") as loaded:
        arrays = {name: loaded[name] for name in loaded.files}
    models = load_models(config, device)

    synthetic, rows, _synthetic_outputs = synthetic_evaluation(models, arrays, device)
    save_rows(ROOT / "results" / "synthetic_per_sample.csv", [row for row in rows if "mae_gray" in row])
    save_rows(ROOT / "results" / "synthetic_motion_pairs.csv", [row for row in rows if "step_error_px" in row])
    real, _real_outputs = real_evaluation(models, config, device)
    motion = motion_sequence_evaluation(models, config, device)
    tile = tiling_evaluation(models, config, device)
    curves = plot_training(config)
    combined = {"synthetic": synthetic, "real": real, "tile": tile}
    recommended, rank_scores = continuous_rank_score(combined)
    comparison = {
        "status": "complete",
        "experiment_id": config["experiment_id"],
        "completed_at": datetime.now().isoformat(),
        "arms_share_data_schedule_and_common_initialization": True,
        "full_r101_training_started": False,
        "synthetic": synthetic,
        "real": real,
        "real_motion_sequence": motion,
        "tile": tile,
        "continuous_rank_scores_lower_is_better": rank_scores,
        "recommended_arm_for_full_design": recommended,
        "recommendation_is_continuous_not_a_hard_gate": True,
        "figures": {
            "training_curves": curves,
            "real_live_comparison": str(ROOT / "results" / "real_live_comparison.png"),
            "training_previews": str(ROOT / "results" / "training_previews"),
        },
        "limitations": [
            "The experiment is a 400-step mechanism falsification, not a full generalization claim.",
            "Real microscopy has no clean high-frequency truth and is used only as a falsification view.",
            "The x_1um check uses internal phase correlation; external GMF was not rerun.",
            "The subpixel renderer is a bounded prototype and may be refined before full R101 training."
        ],
    }
    write_json(ROOT / "results" / "comparison_summary.json", comparison)
    write_json(ROOT / "runs" / "active_run.json", {"status": "complete", "completed_at": comparison["completed_at"], "summary": str(ROOT / "results" / "comparison_summary.json")})
    print(json.dumps(comparison, indent=2, ensure_ascii=False), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

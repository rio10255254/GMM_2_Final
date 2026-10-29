"""Run falsification experiments before fixing the next model design.

This script is deliberately unable to train a model.  It reuses frozen R99
checkpoints, procedural truth, and read-only real microscope images.
"""
from __future__ import annotations

import csv
import importlib.util
import json
import math
import sys
import time
from collections import defaultdict
from pathlib import Path
from typing import Any

import cv2
import numpy as np
import torch
PROJECT_ROOT = Path(__file__).resolve().parents[3]


ROOT = Path(__file__).resolve().parents[1]
R99 = Path(str(PROJECT_ROOT / 'Experiments/R99_GeometryTextureCoherentScratch'))
R92_PACKAGE = Path(str(PROJECT_ROOT / 'Experiments/R92_PhysicalTransitionBalancedScratch/data/r92_formal'))
R96_MOTION = Path(str(PROJECT_ROOT / 'Experiments/R96_LocalizedEvidenceProtectedScratch/results/x1um_counterfactual_reconstruction'))
REAL_SETS = {
    "5x": Path(str(PROJECT_ROOT / '20260704_5x')),
    "20x": Path(str(PROJECT_ROOT / '20260704_20x')),
    "50x": Path(str(PROJECT_ROOT / '20260702_100MG_位移_50x')),
}
X1UM = Path(str(PROJECT_ROOT / '20260702_100MG_位移_50x/x_1um'))
RUN_ID = "R99_scratch_seed990053_20260814_105831"
R99_WEIGHTS = R99 / "weights" / "formal" / "seed_990053" / RUN_ID / "weights"
RESULTS = ROOT / "results"
ACM_INPUTS = RESULTS / "acm_photometric_inputs"
PATCH = 256
CORE = 128
HALO = (PATCH - CORE) // 2
ROLE_CAP = 28
BOOST_GAINS = (0.15, 0.30, 0.45, 0.60)
IMAGE_EXTENSIONS = {".bmp", ".png", ".tif", ".tiff", ".jpg", ".jpeg"}


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2, ensure_ascii=False, allow_nan=False), encoding="utf-8")
    temporary.replace(path)


def read_gray(path: Path) -> np.ndarray:
    image = cv2.imdecode(np.fromfile(str(path), dtype=np.uint8), cv2.IMREAD_GRAYSCALE)
    if image is None:
        raise RuntimeError(f"Could not decode {path}")
    return image


def write_gray(path: Path, image: np.ndarray) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    suffix = path.suffix if path.suffix else ".png"
    ok, encoded = cv2.imencode(suffix, np.asarray(image, dtype=np.uint8))
    if not ok:
        raise RuntimeError(path)
    encoded.tofile(str(path))


def summary(values: list[float] | np.ndarray) -> dict[str, float | int]:
    array = np.asarray(values, dtype=np.float64)
    if not array.size:
        return {"count": 0, "mean": 0.0, "median": 0.0, "p10": 0.0, "p90": 0.0, "p95": 0.0, "maximum": 0.0}
    if not np.isfinite(array).all():
        raise RuntimeError("A summary received non-finite values")
    return {
        "count": int(array.size),
        "mean": float(array.mean()),
        "median": float(np.median(array)),
        "p10": float(np.percentile(array, 10)),
        "p90": float(np.percentile(array, 90)),
        "p95": float(np.percentile(array, 95)),
        "maximum": float(array.max()),
    }


def gaussian(image: np.ndarray, sigma: float, radius: int) -> np.ndarray:
    return cv2.GaussianBlur(
        image.astype(np.float32),
        (2 * radius + 1, 2 * radius + 1),
        sigmaX=sigma,
        sigmaY=sigma,
        borderType=cv2.BORDER_REFLECT_101,
    )


def band_stack(image: np.ndarray) -> np.ndarray:
    source = image.astype(np.float32)
    g07 = gaussian(source, 0.7, 3)
    g14 = gaussian(source, 1.4, 6)
    g28 = gaussian(source, 2.8, 12)
    return np.stack([source - g07, g07 - g14, g14 - g28], axis=-1)


def fit_band_coefficients(source: np.ndarray, target: np.ndarray, ridge_fraction: float = 2e-4) -> np.ndarray:
    features = band_stack(source).reshape(-1, 3).astype(np.float64)
    response = (target - source).reshape(-1).astype(np.float64)
    xtx = features.T @ features
    ridge = max(float(np.trace(xtx)) / 3.0 * ridge_fraction, 1e-8)
    coefficients = np.linalg.solve(xtx + ridge * np.eye(3), features.T @ response)
    return np.clip(coefficients, -0.75, 1.50).astype(np.float32)


def fit_global_coefficients(samples: list[dict[str, Any]]) -> tuple[np.ndarray, dict[str, Any]]:
    xtx = np.zeros((3, 3), dtype=np.float64)
    xty = np.zeros(3, dtype=np.float64)
    per_view: list[list[float]] = []
    core = np.s_[HALO : HALO + CORE, HALO : HALO + CORE]
    for sample in samples:
        source = sample["source"][core]
        target = sample["target"][core]
        features = band_stack(source).reshape(-1, 3).astype(np.float64)
        response = (target - source).reshape(-1).astype(np.float64)
        xtx += features.T @ features
        xty += features.T @ response
        per_view.append(fit_band_coefficients(source, target).tolist())
    ridge = max(float(np.trace(xtx)) / 3.0 * 2e-4, 1e-8)
    raw = np.linalg.solve(xtx + ridge * np.eye(3), xty)
    fitted = np.clip(raw, -0.75, 1.50).astype(np.float32)
    per_array = np.asarray(per_view, dtype=np.float64)
    return fitted, {
        "unclipped_coefficients": raw.tolist(),
        "clipped_coefficients": fitted.tolist(),
        "per_view_coefficient_median": np.median(per_array, axis=0).tolist(),
        "per_view_coefficient_p10": np.percentile(per_array, 10, axis=0).tolist(),
        "per_view_coefficient_p90": np.percentile(per_array, 90, axis=0).tolist(),
        "positive_fine_coefficient_fraction": float(np.mean(per_array[:, 0] > 0)),
        "negative_fine_coefficient_fraction": float(np.mean(per_array[:, 0] < 0)),
    }


def apply_band_operator(image: np.ndarray, coefficients: np.ndarray) -> tuple[np.ndarray, float]:
    source = image.astype(np.float32)
    unbounded = source + np.tensordot(band_stack(source), np.asarray(coefficients, dtype=np.float32), axes=([-1], [0]))
    clip_fraction = float(np.mean((unbounded < 0.0) | (unbounded > 1.0)))
    return np.clip(unbounded, 0.0, 1.0).astype(np.float32), clip_fraction


def boost_coefficients(gain: float) -> np.ndarray:
    return np.asarray([gain, 0.70 * gain, 0.20 * gain], dtype=np.float32)


def gradient_magnitude(image: np.ndarray) -> np.ndarray:
    smooth = gaussian(image, 0.8, 3)
    gx = cv2.Sobel(smooth, cv2.CV_32F, 1, 0, ksize=3)
    gy = cv2.Sobel(smooth, cv2.CV_32F, 0, 1, ksize=3)
    return cv2.magnitude(gx, gy)


def binary_boundary(mask: np.ndarray) -> np.ndarray:
    binary = (mask > 0).astype(np.uint8)
    return cv2.morphologyEx(binary, cv2.MORPH_GRADIENT, np.ones((3, 3), np.uint8)).astype(bool)


def mean_symmetric_boundary_distance(first: np.ndarray, second: np.ndarray) -> float:
    first_boundary = binary_boundary(first)
    second_boundary = binary_boundary(second)
    if not first_boundary.any() or not second_boundary.any():
        return float(max(first.shape))
    distance_to_second = cv2.distanceTransform((~second_boundary).astype(np.uint8), cv2.DIST_L2, 5)
    distance_to_first = cv2.distanceTransform((~first_boundary).astype(np.uint8), cv2.DIST_L2, 5)
    return 0.5 * (float(distance_to_second[first_boundary].mean()) + float(distance_to_first[second_boundary].mean()))


def sigmoid_probability(image: np.ndarray, midpoint: float, polarity: float) -> np.ndarray:
    argument = np.clip(polarity * (image.astype(np.float32) - midpoint) / 0.04, -20.0, 20.0)
    return 1.0 / (1.0 + np.exp(-argument))


def centroid(mask_or_weight: np.ndarray) -> tuple[float, float]:
    weight = np.asarray(mask_or_weight, dtype=np.float64)
    mass = max(float(weight.sum()), 1e-8)
    yy, xx = np.indices(weight.shape, dtype=np.float64)
    return float((weight * xx).sum() / mass), float((weight * yy).sum() / mass)


def connected_components(mask: np.ndarray) -> int:
    count, _labels = cv2.connectedComponents(mask.astype(np.uint8), connectivity=8)
    return max(int(count) - 1, 0)


def image_metrics(
    source: np.ndarray,
    target: np.ndarray,
    truth_mask: np.ndarray,
    output: np.ndarray,
    midpoint: float,
    polarity: float,
    clip_fraction: float,
) -> dict[str, float]:
    truth = truth_mask >= 0.5
    probability = sigmoid_probability(output, midpoint, polarity)
    prediction = probability >= 0.5
    intersection = int(np.count_nonzero(prediction & truth))
    union = int(np.count_nonzero(prediction | truth))
    iou = (intersection + 1e-6) / (union + 1e-6)
    source_detail = source - gaussian(source, 2.0, 8)
    target_detail = target - gaussian(target, 2.0, 8)
    output_detail = output - gaussian(output, 2.0, 8)
    target_gradient = gradient_magnitude(target)
    output_gradient = gradient_magnitude(output)
    source_p01, source_p99 = np.percentile(source, [1, 99])
    threshold_centroids = []
    for threshold in (0.35, 0.50, 0.65):
        threshold_centroids.append(centroid(probability >= threshold))
    truth_centroid = centroid(truth)
    midpoint_centroid = threshold_centroids[1]
    threshold_spread = max(
        math.hypot(left[0] - right[0], left[1] - right[1])
        for left in threshold_centroids
        for right in threshold_centroids
    )
    return {
        "pixel_mae_gray": float(np.mean(np.abs(output - target)) * 255.0),
        "detail_mae_gray": float(np.mean(np.abs(output_detail - target_detail)) * 255.0),
        "gradient_mae_gray": float(np.mean(np.abs(output_gradient - target_gradient)) * 255.0),
        "detail_energy_ratio_to_source": float(np.sqrt(np.mean(output_detail * output_detail)) / max(np.sqrt(np.mean(source_detail * source_detail)), 1e-8)),
        "contour_iou": float(iou),
        "boundary_distance_px": mean_symmetric_boundary_distance(prediction, truth),
        "signed_area_error_fraction": float((prediction.sum() - truth.sum()) / max(int(truth.sum()), 1)),
        "centroid_error_px": float(math.hypot(midpoint_centroid[0] - truth_centroid[0], midpoint_centroid[1] - truth_centroid[1])),
        "threshold_centroid_spread_px": float(threshold_spread),
        "topology_component_error": float(abs(connected_components(prediction) - connected_components(truth))),
        "identity_change_gray": float(np.mean(np.abs(output - source)) * 255.0),
        "source_range_overshoot_fraction": float(np.mean((output < source_p01 - 0.02) | (output > source_p99 + 0.02))),
        "clip_fraction": float(clip_fraction),
    }


def collect_samples(trainer: Any, manifest: dict[str, Any], split: str) -> list[dict[str, Any]]:
    dataset = trainer.R99SceneDataset(R92_PACKAGE, manifest, split, PATCH, CORE, 0, all_observations=True)
    counts: defaultdict[str, int] = defaultdict(int)
    seen: set[tuple[Any, ...]] = set()
    samples: list[dict[str, Any]] = []
    roles = sorted({str(row["role"]) for row in manifest["records"] if row["split"] == split})
    for index in range(len(dataset)):
        item = dataset[index]
        role = str(item["role"])
        if counts[role] >= ROLE_CAP:
            continue
        observations = item["observation_indices"].tolist()
        for view, observation in enumerate(observations):
            origin = tuple(int(value) for value in item["origins"][view].tolist())
            key = (str(item["scene_id"]), int(observation), origin)
            if key in seen or counts[role] >= ROLE_CAP:
                continue
            seen.add(key)
            samples.append({
                "sample_id": f"{item['scene_id']}|o{observation}|{origin[0]},{origin[1]}",
                "scene_id": str(item["scene_id"]),
                "role": role,
                "observation": int(observation),
                "source": item["source"][view, 0].numpy().astype(np.float32),
                "target": item["target"][view, 0].numpy().astype(np.float32),
                "mask": item["mask"][view, 0].numpy().astype(np.float32),
                "midpoint": float(item["boundary_level"]),
                "polarity": float(item["polarity"]),
                "identity": bool(item["identity"][view]),
            })
            counts[role] += 1
        if roles and all(counts[role] >= ROLE_CAP for role in roles):
            break
    if any(counts[role] < min(ROLE_CAP, 8) for role in roles):
        raise RuntimeError(f"Insufficient balanced {split} sample: {dict(counts)}")
    print(f"[{split}] collected {len(samples)} views: {dict(counts)}", flush=True)
    return samples


def load_r99_models(model_module: Any, device: torch.device) -> dict[str, torch.nn.Module]:
    models: dict[str, torch.nn.Module] = {}
    for epoch in (24, 40):
        checkpoint = torch.load(R99_WEIGHTS / f"epoch_{epoch:03d}.pth.tar", map_location="cpu", weights_only=False)
        model = model_module.build_model().to(device).eval()
        model.load_state_dict(checkpoint["ema_state_dict"], strict=True)
        models[f"r99_e{epoch:03d}"] = model
    return models


def infer_models(models: dict[str, torch.nn.Module], samples: list[dict[str, Any]], device: torch.device) -> dict[str, list[np.ndarray]]:
    result = {name: [] for name in models}
    batch_size = 20 if device.type == "cuda" else 4
    arrays = [sample["source"] for sample in samples]
    for start in range(0, len(arrays), batch_size):
        tensor = torch.from_numpy(np.stack(arrays[start : start + batch_size])).unsqueeze(1).to(device)
        with torch.inference_mode():
            for name, model in models.items():
                output = model(tensor).detach().float().cpu().numpy()[:, 0]
                result[name].extend(output)
    return result


def evaluate_synthetic_operators(
    samples: list[dict[str, Any]],
    models: dict[str, torch.nn.Module],
    global_coefficients: np.ndarray,
    device: torch.device,
) -> dict[str, Any]:
    model_outputs = infer_models(models, samples, device)
    methods = ["raw", "band_global", "band_oracle"] + [f"boost_{int(gain * 100):02d}" for gain in BOOST_GAINS] + list(models)
    rows: dict[str, list[dict[str, float]]] = {name: [] for name in methods}
    roles: dict[str, dict[str, list[dict[str, float]]]] = {name: defaultdict(list) for name in methods}
    core = np.s_[HALO : HALO + CORE, HALO : HALO + CORE]
    for index, sample in enumerate(samples):
        source_full = sample["source"]
        source = source_full[core]
        target = sample["target"][core]
        mask = sample["mask"][core]
        outputs: dict[str, tuple[np.ndarray, float]] = {"raw": (source, 0.0)}
        global_output, global_clip = apply_band_operator(source_full, global_coefficients)
        outputs["band_global"] = (global_output[core], global_clip)
        oracle_coefficients = fit_band_coefficients(source, target)
        oracle_output, oracle_clip = apply_band_operator(source_full, oracle_coefficients)
        outputs["band_oracle"] = (oracle_output[core], oracle_clip)
        for gain in BOOST_GAINS:
            output, clip_fraction = apply_band_operator(source_full, boost_coefficients(gain))
            outputs[f"boost_{int(gain * 100):02d}"] = (output[core], clip_fraction)
        for name in models:
            outputs[name] = (model_outputs[name][index][core], 0.0)
        for name, (output, clip_fraction) in outputs.items():
            metric = image_metrics(source, target, mask, output, sample["midpoint"], sample["polarity"], clip_fraction)
            if not sample["identity"]:
                metric["identity_change_gray"] = 0.0
            rows[name].append(metric)
            roles[name][sample["role"]].append(metric)

    metric_names = list(rows["raw"][0])
    summaries: dict[str, Any] = {}
    for name in methods:
        summaries[name] = {
            metric: summary([row[metric] for row in rows[name]])
            for metric in metric_names
        }
        summaries[name]["by_role"] = {
            role: {metric: summary([row[metric] for row in role_rows]) for metric in metric_names}
            for role, role_rows in roles[name].items()
        }
        if name != "raw":
            summaries[name]["paired_improvement_fraction"] = {
                "pixel_mae_gray": float(np.mean([right["pixel_mae_gray"] < left["pixel_mae_gray"] for left, right in zip(rows["raw"], rows[name])])),
                "detail_mae_gray": float(np.mean([right["detail_mae_gray"] < left["detail_mae_gray"] for left, right in zip(rows["raw"], rows[name])])),
                "boundary_distance_px": float(np.mean([right["boundary_distance_px"] < left["boundary_distance_px"] for left, right in zip(rows["raw"], rows[name])])),
                "contour_iou": float(np.mean([right["contour_iou"] > left["contour_iou"] for left, right in zip(rows["raw"], rows[name])])),
            }
    return {"evaluation_view_count": len(samples), "methods": summaries}


def phase_shift(first: np.ndarray, second: np.ndarray) -> tuple[np.ndarray, float]:
    a = first.astype(np.float32)
    b = second.astype(np.float32)
    a = a - gaussian(a, 3.0, 12)
    b = b - gaussian(b, 3.0, 12)
    a /= max(float(np.sqrt(np.mean(a * a))), 1e-6)
    b /= max(float(np.sqrt(np.mean(b * b))), 1e-6)
    window = cv2.createHanningWindow((a.shape[1], a.shape[0]), cv2.CV_32F)
    shift, response = cv2.phaseCorrelate(a, b, window)
    return np.asarray([float(shift[0]), float(shift[1])], dtype=np.float64), float(response)


def edge_centroid(image: np.ndarray, midpoint: float, polarity: float, support: np.ndarray) -> np.ndarray:
    probability = sigmoid_probability(image, midpoint, polarity).astype(np.float32)
    maximum = cv2.dilate(probability, np.ones((5, 5), np.uint8))
    minimum = cv2.erode(probability, np.ones((5, 5), np.uint8))
    edge = np.clip(maximum - minimum, 0.0, 1.0) * support.astype(np.float32)
    x, y = centroid(edge + 1e-6 * support)
    return np.asarray([x, y], dtype=np.float64)


def truth_edge_centroid(mask: np.ndarray, support: np.ndarray) -> np.ndarray:
    edge = binary_boundary(mask >= 0.5).astype(np.float32) * support.astype(np.float32)
    x, y = centroid(edge + 1e-6 * support)
    return np.asarray([x, y], dtype=np.float64)


def synthetic_motion_audit(
    trainer: Any,
    manifest: dict[str, Any],
    models: dict[str, torch.nn.Module],
    global_coefficients: np.ndarray,
    device: torch.device,
) -> dict[str, Any]:
    dataset = trainer.R99SceneDataset(R92_PACKAGE, manifest, "internal_test", PATCH, CORE, 0, all_observations=True)
    method_names = ["raw", "band_global"] + [f"boost_{int(g * 100):02d}" for g in BOOST_GAINS] + list(models)
    centroid_errors: dict[str, list[np.ndarray]] = {name: [] for name in method_names}
    phase_errors: dict[str, list[np.ndarray]] = {name: [] for name in method_names}
    responses: dict[str, list[float]] = {name: [] for name in method_names}
    pair_count = 0
    core = np.s_[HALO : HALO + CORE, HALO : HALO + CORE]
    for index in range(len(dataset)):
        item = dataset[index]
        if str(item["role"]) != "signed_subpixel_motion" or int(item["pair_kind"]) != 1:
            continue
        source_full = item["source"][:, 0].numpy().astype(np.float32)
        target = item["target"][:, 0].numpy().astype(np.float32)[:, core[0], core[1]]
        mask = item["mask"][:, 0].numpy().astype(np.float32)[:, core[0], core[1]]
        midpoint, polarity = float(item["boundary_level"]), float(item["polarity"])
        union = np.maximum(mask[0], mask[1]) >= 0.2
        support = cv2.dilate(union.astype(np.uint8), np.ones((49, 49), np.uint8)).astype(np.float32)
        target_centers = [truth_edge_centroid(mask[view], support) for view in range(2)]
        target_delta = target_centers[1] - target_centers[0]
        target_phase, _ = phase_shift(target[0], target[1])
        outputs: dict[str, list[np.ndarray]] = {"raw": [source_full[0][core], source_full[1][core]]}
        outputs["band_global"] = [apply_band_operator(source_full[view], global_coefficients)[0][core] for view in range(2)]
        for gain in BOOST_GAINS:
            outputs[f"boost_{int(gain * 100):02d}"] = [apply_band_operator(source_full[view], boost_coefficients(gain))[0][core] for view in range(2)]
        tensor = torch.from_numpy(source_full).unsqueeze(1).to(device)
        with torch.inference_mode():
            for name, model in models.items():
                outputs[name] = list(model(tensor).detach().float().cpu().numpy()[:, 0, core[0], core[1]])
        for name, pair in outputs.items():
            centers = [edge_centroid(pair[view], midpoint, polarity, support) for view in range(2)]
            centroid_errors[name].append((centers[1] - centers[0]) - target_delta)
            measured_phase, response = phase_shift(pair[0], pair[1])
            phase_errors[name].append(measured_phase - target_phase)
            responses[name].append(response)
        pair_count += 1
    result: dict[str, Any] = {"pair_count": pair_count, "methods": {}}
    for name in method_names:
        centroid_array = np.asarray(centroid_errors[name], dtype=np.float64)
        phase_array = np.asarray(phase_errors[name], dtype=np.float64)
        result["methods"][name] = {
            "centroid_axis_mae_px": float(np.abs(centroid_array).mean()),
            "centroid_axis_p95_px": float(np.percentile(np.abs(centroid_array), 95)),
            "centroid_signed_bias_xy_px": centroid_array.mean(axis=0).tolist(),
            "phase_axis_mae_px": float(np.abs(phase_array).mean()),
            "phase_axis_p95_px": float(np.percentile(np.abs(phase_array), 95)),
            "phase_signed_bias_xy_px": phase_array.mean(axis=0).tolist(),
            "phase_response": summary(responses[name]),
        }
    return result


def make_irregular_mask(seed: int, size: int = 256, supersample: int = 4) -> np.ndarray:
    rng = np.random.default_rng(seed)
    high = size * supersample
    center = np.asarray([high / 2, high / 2], dtype=np.float64)
    angles = np.linspace(0, 2 * np.pi, 72, endpoint=False)
    harmonics = np.zeros_like(angles)
    for frequency in range(2, 9):
        harmonics += rng.uniform(0.015, 0.06) * np.sin(frequency * angles + rng.uniform(0, 2 * np.pi))
    base_radius = rng.uniform(0.21, 0.28) * high
    radius = base_radius * (1.0 + harmonics)
    points = np.stack([center[0] + radius * np.cos(angles), center[1] + radius * np.sin(angles)], axis=1)
    canvas = np.zeros((high, high), dtype=np.uint8)
    cv2.fillPoly(canvas, [np.rint(points).astype(np.int32)], 255, lineType=cv2.LINE_AA)
    coverage = cv2.resize(canvas.astype(np.float32) / 255.0, (size, size), interpolation=cv2.INTER_AREA)
    return (coverage >= 0.5).astype(np.uint8)


def signed_distance(mask: np.ndarray) -> np.ndarray:
    inside = cv2.distanceTransform(mask.astype(np.uint8), cv2.DIST_L2, 5)
    outside = cv2.distanceTransform((1 - mask.astype(np.uint8)), cv2.DIST_L2, 5)
    return inside - outside


def geometry_target_audit() -> dict[str, Any]:
    rows: defaultdict[str, list[dict[str, float]]] = defaultdict(list)
    for seed in range(32):
        target = make_irregular_mask(1000 + seed)
        target_sdf = signed_distance(target)
        variants: list[tuple[str, np.ndarray, float, float, float]] = [
            ("identity", target.copy(), 0.0, 0.0, 0.0),
            ("translate", cv2.warpAffine(target, np.asarray([[1, 0, 1], [0, 1, 0]], np.float32), (256, 256), flags=cv2.INTER_NEAREST, borderMode=cv2.BORDER_REFLECT_101), 1.0, 0.0, 0.0),
            ("translate", cv2.warpAffine(target, np.asarray([[1, 0, -1], [0, 1, 0]], np.float32), (256, 256), flags=cv2.INTER_NEAREST, borderMode=cv2.BORDER_REFLECT_101), -1.0, 0.0, 0.0),
            ("translate", cv2.warpAffine(target, np.asarray([[1, 0, 0], [0, 1, 2]], np.float32), (256, 256), flags=cv2.INTER_NEAREST, borderMode=cv2.BORDER_REFLECT_101), 0.0, 2.0, 0.0),
            ("translate", cv2.warpAffine(target, np.asarray([[1, 0, 0], [0, 1, -2]], np.float32), (256, 256), flags=cv2.INTER_NEAREST, borderMode=cv2.BORDER_REFLECT_101), 0.0, -2.0, 0.0),
            ("dilate", cv2.dilate(target, np.ones((3, 3), np.uint8)), 0.0, 0.0, -1.0),
            ("erode", cv2.erode(target, np.ones((3, 3), np.uint8)), 0.0, 0.0, 1.0),
        ]
        for family, source, dx, dy, radial_expected in variants:
            source_sdf = signed_distance(source)
            support = np.abs(source_sdf) <= 3.5
            current = np.clip(target_sdf, -1.5, 1.5)
            difference = np.clip(target_sdf - source_sdf, -1.5, 1.5)
            if family == "translate":
                gx = cv2.Sobel(source_sdf, cv2.CV_32F, 1, 0, ksize=3)
                gy = cv2.Sobel(source_sdf, cv2.CV_32F, 0, 1, ksize=3)
                norm = np.sqrt(gx * gx + gy * gy) + 1e-6
                expected = np.clip(dx * gx / norm + dy * gy / norm, -1.5, 1.5)
            else:
                expected = np.full_like(source_sdf, radial_expected, dtype=np.float32)
            rows[family].append({
                "current_target_abs_px": float(np.mean(np.abs(current[support]))),
                "difference_target_abs_px": float(np.mean(np.abs(difference[support]))),
                "current_mae_to_known_px": float(np.mean(np.abs(current[support] - expected[support]))),
                "difference_mae_to_known_px": float(np.mean(np.abs(difference[support] - expected[support]))),
                "current_within_band_std_px": float(np.std(current[support] - expected[support])),
                "difference_within_band_std_px": float(np.std(difference[support] - expected[support])),
            })
    return {
        family: {metric: summary([row[metric] for row in family_rows]) for metric in family_rows[0]}
        for family, family_rows in rows.items()
    }


def real_metrics(raw: np.ndarray, output: np.ndarray) -> dict[str, float]:
    raw = raw.astype(np.float32)
    output = output.astype(np.float32)
    raw_gradient = gradient_magnitude(raw)
    output_gradient = gradient_magnitude(output)
    raw_detail = raw - gaussian(raw, 2.0, 8)
    output_detail = output - gaussian(output, 2.0, 8)
    raw_lap = cv2.Laplacian(raw, cv2.CV_32F, ksize=3)
    output_lap = cv2.Laplacian(output, cv2.CV_32F, ksize=3)
    shift, response = phase_shift(raw, output)
    raw_low, raw_high = np.percentile(raw, [1, 99])
    output_strong = output_gradient >= np.percentile(output_gradient, 95)
    raw_weak = raw_gradient <= np.percentile(raw_gradient, 50)
    return {
        "mean_abs_change_gray": float(np.mean(np.abs(output - raw)) * 255.0),
        "edge_energy_ratio": float(np.mean(output_gradient) / max(float(np.mean(raw_gradient)), 1e-8)),
        "fine_detail_rms_ratio": float(np.sqrt(np.mean(output_detail * output_detail)) / max(np.sqrt(np.mean(raw_detail * raw_detail)), 1e-8)),
        "laplacian_energy_ratio": float(np.mean(np.abs(output_lap)) / max(float(np.mean(np.abs(raw_lap))), 1e-8)),
        "contrast_ratio": float((np.percentile(output, 95) - np.percentile(output, 5)) / max(np.percentile(raw, 95) - np.percentile(raw, 5), 1e-8)),
        "source_range_overshoot_fraction": float(np.mean((output < raw_low - 0.02) | (output > raw_high + 0.02))),
        "off_source_strong_edge_fraction": float(np.mean(output_strong & raw_weak)),
        "self_phase_shift_px": float(np.hypot(shift[0], shift[1])),
        "self_phase_response": float(response),
    }


def save_contact_sheet(path: Path, panels: list[tuple[str, np.ndarray]]) -> None:
    rendered = []
    for label, image in panels:
        panel = np.rint(np.clip(image, 0.0, 1.0) * 255.0).astype(np.uint8)
        panel = panel.copy()
        cv2.rectangle(panel, (0, 0), (180, 34), 0, thickness=-1)
        cv2.putText(panel, label, (8, 24), cv2.FONT_HERSHEY_SIMPLEX, 0.65, 255, 2, cv2.LINE_AA)
        rendered.append(panel)
    write_gray(path, np.concatenate(rendered, axis=1))


def real_probe(global_coefficients: np.ndarray) -> dict[str, Any]:
    centers = ((448, 448), (448, 1600), (768, 1024), (1088, 448), (1088, 1600))
    method_coefficients = {"band_global": global_coefficients}
    method_coefficients.update({f"boost_{int(g * 100):02d}": boost_coefficients(g) for g in BOOST_GAINS})
    rows: dict[str, dict[str, list[dict[str, float]]]] = {
        method: {set_name: [] for set_name in REAL_SETS}
        for method in method_coefficients
    }
    representative: dict[str, tuple[np.ndarray, dict[str, np.ndarray]]] = {}
    for set_name, folder in REAL_SETS.items():
        files = sorted(path for path in folder.rglob("*") if path.suffix.lower() in IMAGE_EXTENSIONS)
        indices = np.linspace(0, len(files) - 1, 12, dtype=int)
        for frame_position, file_index in enumerate(indices):
            image = read_gray(files[int(file_index)]).astype(np.float32) / 255.0
            for center_position, (cy, cx) in enumerate(centers):
                patch = image[cy - 448 : cy + 448, cx - 448 : cx + 448]
                if patch.shape != (896, 896):
                    raise RuntimeError(f"Unexpected patch {patch.shape} from {files[int(file_index)]}")
                core = patch[192:704, 192:704]
                outputs: dict[str, np.ndarray] = {}
                for method, coefficients in method_coefficients.items():
                    output, _clip = apply_band_operator(patch, coefficients)
                    outputs[method] = output[192:704, 192:704]
                    rows[method][set_name].append(real_metrics(core, outputs[method]))
                if frame_position == 6 and center_position == 2:
                    representative[set_name] = (core, outputs)
        raw, outputs = representative[set_name]
        save_contact_sheet(
            RESULTS / f"real_contact_{set_name}.png",
            [("Raw", raw), ("Global fit", outputs["band_global"]), ("Boost 0.30", outputs["boost_30"]), ("Boost 0.60", outputs["boost_60"])],
        )
    compact = {
        method: {
            set_name: {metric: summary([row[metric] for row in set_rows]) for metric in set_rows[0]}
            for set_name, set_rows in sets.items()
        }
        for method, sets in rows.items()
    }
    prior = json.loads((R99 / "reports" / "deep_dive" / "broad_real_probe.json").read_text(encoding="utf-8"))
    return {
        "sampling": {"frames_per_set": 12, "patches_per_frame": 5, "patches_per_set": 60, "patch_size": 896, "evaluated_core": 512},
        "symmetric_operators": compact,
        "frozen_r99_reference": {
            epoch: {
                set_name: {
                    metric: prior["epochs"][epoch][set_name][metric]["mean"]
                    for metric in ("mean_abs_gray", "edge_ratio", "laplacian_ratio", "contrast_ratio", "overshoot_fraction")
                }
                for set_name in REAL_SETS
            }
            for epoch in ("24", "40")
        },
    }


def candidate_tiled(image: np.ndarray, coefficients: np.ndarray, core: int = 256, halo: int = 16) -> np.ndarray:
    height, width = image.shape
    grid_h = int(math.ceil(height / core) * core)
    grid_w = int(math.ceil(width / core) * core)
    padded = cv2.copyMakeBorder(
        image.astype(np.float32),
        halo,
        halo + grid_h - height,
        halo,
        halo + grid_w - width,
        cv2.BORDER_REFLECT_101,
    )
    output = np.empty((grid_h, grid_w), dtype=np.float32)
    for y in range(0, grid_h, core):
        for x in range(0, grid_w, core):
            tile = padded[y : y + core + 2 * halo, x : x + core + 2 * halo]
            restored, _clip = apply_band_operator(tile, coefficients)
            output[y : y + core, x : x + core] = restored[halo : halo + core, halo : halo + core]
    return output[:height, :width]


def tiling_audit(
    models: dict[str, torch.nn.Module],
    inference: Any,
    global_coefficients: np.ndarray,
    device: torch.device,
) -> dict[str, float]:
    first = sorted(path for path in REAL_SETS["20x"].rglob("*") if path.suffix.lower() in IMAGE_EXTENSIONS)[0]
    image = read_gray(first).astype(np.float32) / 255.0
    patch = image[320:1216, 576:1472]
    full, _clip = apply_band_operator(patch, global_coefficients)
    tiled = candidate_tiled(patch, global_coefficients)
    result: dict[str, float] = {
        "symmetric_operator_mean_abs_gray": float(np.mean(np.abs(full - tiled)) * 255.0),
        "symmetric_operator_max_abs_gray": float(np.max(np.abs(full - tiled)) * 255.0),
    }
    tensor = torch.from_numpy(patch[192:704, 192:704]).unsqueeze(0).unsqueeze(0).to(device)
    for name, model in models.items():
        with torch.inference_mode():
            reference = inference.reconstruct_full_reference(model, tensor, core_size=256, halo=192)
            reconstructed = inference.reconstruct_tensor(model, tensor, core_size=256, halo=192, tile_batch=4)
        difference = torch.abs(reference - reconstructed)
        result[f"{name}_mean_abs_gray"] = float(difference.mean().cpu() * 255.0)
        result[f"{name}_max_abs_gray"] = float(difference.max().cpu() * 255.0)
    return result


def phase_preprocess(image: np.ndarray) -> np.ndarray:
    u8 = np.rint(np.clip(image, 0.0, 1.0) * 255.0).astype(np.uint8)
    _threshold, binary = cv2.threshold(u8, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    array = binary.astype(np.float32)
    array -= float(array.mean())
    scale = float(array.std())
    return array / scale if scale > 1e-6 else array


def summarize_real_steps(steps_px: np.ndarray, responses: np.ndarray) -> dict[str, Any]:
    steps_um = np.abs(steps_px[:, 0]) * 0.069
    error = steps_um - 1.0
    return {
        "step_count": int(len(steps_um)),
        "mean_absolute_step_um": float(steps_um.mean()),
        "median_absolute_step_um": float(np.median(steps_um)),
        "step_std_um": float(steps_um.std(ddof=1)),
        "rmse_from_1um": float(np.sqrt(np.mean(error * error))),
        "p95_abs_error_from_1um": float(np.percentile(np.abs(error), 95)),
        "median_abs_y_step_um": float(np.median(np.abs(steps_px[:, 1])) * 0.069),
        "phase_response": summary(responses),
    }


def x1um_motion_audit(
    models: dict[str, torch.nn.Module],
    inference: Any,
    global_coefficients: np.ndarray,
    device: torch.device,
) -> dict[str, Any]:
    files = sorted(path for path in X1UM.iterdir() if path.suffix.lower() in IMAGE_EXTENSIONS)
    if len(files) != 50:
        raise RuntimeError(f"Expected 50 x1um frames, found {len(files)}")
    raw = [read_gray(path)[780:1536, 0:1050].astype(np.float32) / 255.0 for path in files]
    methods: dict[str, list[np.ndarray]] = {"raw": raw}
    methods["band_global"] = [apply_band_operator(image, global_coefficients)[0] for image in raw]
    for gain in BOOST_GAINS:
        methods[f"boost_{int(gain * 100):02d}"] = [apply_band_operator(image, boost_coefficients(gain))[0] for image in raw]
    for name, model in models.items():
        outputs: list[np.ndarray] = []
        for index, image in enumerate(raw):
            tensor = torch.from_numpy(image).unsqueeze(0).unsqueeze(0).to(device)
            with torch.inference_mode():
                output = inference.reconstruct_tensor(model, tensor, core_size=384, halo=192, tile_batch=3)
            outputs.append(output[0, 0].detach().float().cpu().numpy())
            if (index + 1) % 10 == 0:
                print(f"[{name}] x1um {index + 1}/50", flush=True)
        methods[name] = outputs
    summaries: dict[str, Any] = {}
    step_tables: dict[str, np.ndarray] = {}
    for name, images in methods.items():
        prepared = [phase_preprocess(image) for image in images]
        window = cv2.createHanningWindow((prepared[0].shape[1], prepared[0].shape[0]), cv2.CV_32F)
        steps, responses = [], []
        for first, second in zip(prepared, prepared[1:]):
            shift, response = cv2.phaseCorrelate(first, second, window)
            steps.append([float(shift[0]), float(shift[1])])
            responses.append(float(response))
        step_array = np.asarray(steps, dtype=np.float64)
        response_array = np.asarray(responses, dtype=np.float64)
        step_tables[name] = step_array
        summaries[name] = summarize_real_steps(step_array, response_array)
    raw_steps = step_tables["raw"]
    for name in summaries:
        if name == "raw":
            continue
        delta_um = (np.abs(step_tables[name][:, 0]) - np.abs(raw_steps[:, 0])) * 0.069
        summaries[name]["paired_step_difference_vs_raw_um"] = {
            "mean": float(delta_um.mean()),
            "median_abs": float(np.median(np.abs(delta_um))),
            "p95_abs": float(np.percentile(np.abs(delta_um), 95)),
            "std": float(delta_um.std(ddof=1)),
        }
    external = json.loads((R96_MOTION / "external_gmf_analysis.json").read_text(encoding="utf-8"))
    raw_external = next(row for row in external["arm_summary"] if row["arm"] == "00_raw")
    save_contact_sheet(
        RESULTS / "x1um_frame25_contact.png",
        [("Raw", methods["raw"][25]), ("Global fit", methods["band_global"][25]), ("Boost 0.30", methods["boost_30"][25]), ("R99 E24", methods["r99_e024"][25]), ("R99 E40", methods["r99_e040"][25])],
    )
    return {
        "frame_count": 50,
        "roi": [0, 780, 1050, 1536],
        "calibration_um_per_px": 0.069,
        "methods": summaries,
        "external_gmf_raw_reference": {
            key: raw_external[key]
            for key in ("mean_x_step_um", "x_step_std_um", "rmse_from_1um", "p95_abs_error_from_1um", "median_score_trusted")
        },
        "claim_boundary": "The new methods use a fixed phase-based proxy. External GMF is included only as a Raw calibration reference; it was not rerun for these new outputs.",
    }


def generate_acm_inputs() -> dict[str, Any]:
    ACM_INPUTS.mkdir(parents=True, exist_ok=True)
    for old in ACM_INPUTS.glob("*.png"):
        old.unlink()
    rows: list[dict[str, Any]] = []
    variants = ("reference", "low_contrast", "dark_exposure", "gamma_dark", "gamma_bright", "uneven_illumination")
    yy, xx = np.mgrid[:256, :256].astype(np.float32)
    for shape_index in range(8):
        mask = make_irregular_mask(7000 + shape_index)
        bright_foreground = bool(shape_index % 2)
        for variant_index, variant in enumerate(variants):
            foreground, background = ((0.78, 0.22) if bright_foreground else (0.22, 0.78))
            if variant == "low_contrast":
                foreground, background = ((0.54, 0.46) if bright_foreground else (0.46, 0.54))
            image = np.where(mask > 0, foreground, background).astype(np.float32)
            image = gaussian(image, 1.4, 6)
            if variant == "dark_exposure":
                image = 0.06 + 0.52 * image
            elif variant == "gamma_dark":
                image = np.power(np.clip(image, 0, 1), 1.8)
            elif variant == "gamma_bright":
                image = np.power(np.clip(image, 0, 1), 0.58)
            elif variant == "uneven_illumination":
                field = 0.68 + 0.64 * (0.65 * xx / 255.0 + 0.35 * yy / 255.0)
                image = image * field
            rng = np.random.default_rng(8000 + shape_index * 100 + variant_index)
            image = np.clip(image + rng.normal(0.0, 0.0035, image.shape).astype(np.float32), 0.0, 1.0)
            stem = f"shape_{shape_index:02d}_{variant}"
            write_gray(ACM_INPUTS / f"{stem}.png", np.rint(image * 255.0).astype(np.uint8))
            write_gray(ACM_INPUTS / f"{stem}_mask.png", mask * 255)
            rows.append({
                "image_id": stem,
                "shape_index": shape_index,
                "variant": variant,
                "bright_foreground": int(bright_foreground),
                "image_file": f"{stem}.png",
                "mask_file": f"{stem}_mask.png",
            })
    manifest_path = ACM_INPUTS / "manifest.csv"
    with manifest_path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    return {"shape_count": 8, "variants": list(variants), "image_count": len(rows), "manifest": str(manifest_path)}


def main() -> int:
    started = time.perf_counter()
    RESULTS.mkdir(parents=True, exist_ok=True)
    torch.set_num_threads(4)
    device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")
    print(f"device={device}", flush=True)
    trainer = load_module("r100_validation_r99_trainer", R99 / "training" / "train_r99.py")
    model_module = load_module("r100_validation_r99_model", R99 / "model" / "r99_model.py")
    inference = load_module("r100_validation_r99_inference", R99 / "inference" / "reconstruct.py")
    manifest = json.loads((R92_PACKAGE / "manifest.json").read_text(encoding="utf-8"))

    print("geometry target audit", flush=True)
    geometry = geometry_target_audit()
    print("balanced synthetic samples", flush=True)
    fitting_samples = collect_samples(trainer, manifest, "validation")
    evaluation_samples = collect_samples(trainer, manifest, "internal_test")
    global_coefficients, coefficient_audit = fit_global_coefficients(fitting_samples)
    print(f"global band coefficients={global_coefficients.tolist()}", flush=True)
    models = load_r99_models(model_module, device)

    print("synthetic operator audit", flush=True)
    synthetic = evaluate_synthetic_operators(evaluation_samples, models, global_coefficients, device)
    print("synthetic motion audit", flush=True)
    motion = synthetic_motion_audit(trainer, manifest, models, global_coefficients, device)
    print("real 5x/20x/50x probe", flush=True)
    real = real_probe(global_coefficients)
    print("tiling audit", flush=True)
    tiling = tiling_audit(models, inference, global_coefficients, device)
    print("real x1um motion audit", flush=True)
    x1um = x1um_motion_audit(models, inference, global_coefficients, device)
    print("prepare ACM photometric inputs", flush=True)
    acm_inputs = generate_acm_inputs()

    response = json.loads((R99 / "reports" / "deep_dive" / "response_probe.json").read_text(encoding="utf-8"))
    transport = json.loads((R99 / "reports" / "deep_dive" / "transport_target_audit.json").read_text(encoding="utf-8"))
    payload = {
        "status": "complete",
        "analysis_only_no_training": True,
        "device": str(device),
        "elapsed_seconds": float(time.perf_counter() - started),
        "geometry_target_audit": geometry,
        "band_operator_fit": {
            "fitting_view_count": len(fitting_samples),
            **coefficient_audit,
        },
        "synthetic_operator_audit": synthetic,
        "synthetic_motion_audit": motion,
        "real_probe": real,
        "tiling_audit": tiling,
        "x1um_motion_audit": x1um,
        "acm_input_generation": acm_inputs,
        "frozen_r99_white_box_evidence": {
            "current_transport_target_audit": transport,
            "frequency_response": {epoch: response[epoch]["frequency_response"] for epoch in ("24", "40")},
            "step_response": {epoch: response[epoch]["step_response"] for epoch in ("24", "40")},
        },
    }
    write_json(RESULTS / "core_validation.json", payload)
    print(json.dumps({
        "status": payload["status"],
        "elapsed_seconds": round(payload["elapsed_seconds"], 1),
        "geometry_identity_current": geometry["identity"]["current_target_abs_px"]["mean"],
        "geometry_identity_difference": geometry["identity"]["difference_target_abs_px"]["mean"],
        "global_coefficients": global_coefficients.tolist(),
        "synthetic_views": synthetic["evaluation_view_count"],
        "motion_pairs": motion["pair_count"],
        "tile_max_gray": tiling["symmetric_operator_max_abs_gray"],
    }, indent=2, ensure_ascii=False), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


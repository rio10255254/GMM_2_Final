"""Measure whether the implemented R94 branch constraints can contain their targets."""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
from collections import defaultdict
from pathlib import Path
import sys
from typing import Any

import cv2
import numpy as np


ROOT = Path(__file__).resolve().parents[1]
R93 = Path(r"D:\GMM_2_Final\Experiments\R93_RecoverableDetailSeparatedScratch")


def load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def summarize(values: list[float]) -> dict[str, float]:
    array = np.asarray(values, np.float64)
    return {
        "count": int(array.size),
        "mean": float(array.mean()) if array.size else 0.0,
        "median": float(np.median(array)) if array.size else 0.0,
        "p95": float(np.percentile(array, 95)) if array.size else 0.0,
        "max": float(array.max()) if array.size else 0.0,
    }


def filter2d(image: np.ndarray, kernel: np.ndarray) -> np.ndarray:
    return cv2.filter2D(image, -1, kernel, borderType=cv2.BORDER_REFLECT_101)


def actual_boundary_candidates(image: np.ndarray, kernels: list[np.ndarray]) -> np.ndarray:
    return np.stack([image - filter2d(image, kernel) for kernel in kernels], axis=0)


def local_contrast_candidates(image: np.ndarray) -> np.ndarray:
    rows = []
    for sigma in (3.0, 6.0, 10.0, 15.0):
        rows.append(
            image - cv2.GaussianBlur(
                image, (0, 0), sigmaX=sigma, borderType=cv2.BORDER_REFLECT_101
            )
        )
    return np.stack(rows, axis=0)


def boundary_capacity(
    target: np.ndarray,
    image: np.ndarray,
    candidates: np.ndarray,
    *,
    output_amplitude: float,
    response_slope: float,
    envelope_size: int,
    envelope_scale: float = 1.0,
) -> dict[str, float]:
    active = np.abs(target) > (0.20 / 255.0)
    if not np.any(active):
        return {
            "active_pixels": 0,
            "sign_coverage": 1.0,
            "amplitude_coverage": 1.0,
            "optimistic_error_ratio": 0.0,
        }
    target_values = target[active]
    image_values = image[active]
    max_abs_candidate = np.max(np.abs(candidates[:, active]), axis=0)

    # The implemented coefficient vector has L1 norm <= 1 and signed entries,
    # so a pixelwise optimistic mixed response spans +/- max(abs(candidate)).
    # This deliberately ignores the 17-pixel coefficient smoothness and is an
    # upper bound, not a model-performance estimate.
    nonlinear_limit = output_amplitude * np.tanh(response_slope * max_abs_candidate)
    envelope_kernel = np.ones((envelope_size, envelope_size), np.uint8)
    local_max = cv2.dilate(image, envelope_kernel, borderType=cv2.BORDER_REFLECT_101)[active]
    local_min = cv2.erode(image, envelope_kernel, borderType=cv2.BORDER_REFLECT_101)[active]
    midpoint = 0.5 * (local_max + local_min)
    half_range = 0.5 * (local_max - local_min) * float(envelope_scale)
    positive_limit = np.minimum(
        nonlinear_limit, np.maximum(midpoint + half_range - image_values, 0.0)
    )
    negative_limit = np.minimum(
        nonlinear_limit, np.maximum(image_values - (midpoint - half_range), 0.0)
    )
    reachable = np.where(target_values >= 0.0, positive_limit, negative_limit)
    sign_coverage = reachable > (0.02 / 255.0)
    amplitude_coverage = reachable + 1e-8 >= np.abs(target_values)
    best = np.sign(target_values) * np.minimum(np.abs(target_values), reachable)
    denominator = float(np.mean(np.abs(target_values)))
    return {
        "active_pixels": int(target_values.size),
        "sign_coverage": float(np.mean(sign_coverage)),
        "amplitude_coverage": float(np.mean(amplitude_coverage)),
        "optimistic_error_ratio": float(np.mean(np.abs(best - target_values))) / max(denominator, 1e-8),
    }


def bounded_capacity(target: np.ndarray, bound: float) -> dict[str, float]:
    active = np.abs(target) > (0.20 / 255.0)
    if not np.any(active):
        return {"active_pixels": 0, "amplitude_coverage": 1.0, "clipping_error_ratio": 0.0}
    values = target[active]
    best = np.clip(values, -bound, bound)
    return {
        "active_pixels": int(values.size),
        "amplitude_coverage": float(np.mean(np.abs(values) <= bound + 1e-8)),
        "clipping_error_ratio": float(np.mean(np.abs(best - values))) / max(float(np.mean(np.abs(values))), 1e-8),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--patch", type=int, default=256)
    parser.add_argument("--core", type=int, default=128)
    parser.add_argument("--report", default=str(ROOT / "reports" / "branch_expressivity_analysis.json"))
    args = parser.parse_args()
    trainer = load("r93_branch_capacity_dataset_v2", R93 / "training" / "train_r93.py")
    replay = load("r94_branch_capacity_replay_v2", ROOT / "training" / "causal_stage_replay.py")
    model_module = load("r94_branch_capacity_model_v2", ROOT / "model" / "r94_model.py")
    model = model_module.build_model(base=8)
    kernels = [operator.effective_kernel().detach().cpu().numpy() for operator in model.boundary_filters]
    legacy_kernels = list(kernels[:20])
    dense_reference_kernels = list(legacy_kernels)
    gaussian_33 = cv2.getGaussianKernel(33, 5.5, cv2.CV_32F)
    dense_reference_kernels.append(gaussian_33 @ gaussian_33.T)
    dense_reference_kernels.extend(
        model_module._line_kernel(33, angle).detach().cpu().numpy()
        for angle in (0.0, 22.5, 45.0, 67.5, 90.0, 112.5, 135.0, 157.5)
    )
    designs = {
        "legacy20": (legacy_kernels, 0.32, 4.0, 17),
        "implemented_sparse33": (kernels, 0.45, 12.0, 49),
        "dense33_reference": (dense_reference_kernels, 0.45, 12.0, 49),
    }

    package = R93 / "data" / "r93_formal"
    manifest = json.loads((package / "manifest.json").read_text(encoding="utf-8"))
    record_lookup = {str(record["scene_id"]): record for record in manifest["records"]}
    observation_lookup = {
        (str(record["scene_id"]), int(observation["observation"])): observation
        for record in manifest["records"] for observation in record["observations"]
    }
    dataset = trainer.R93SceneDataset(package, manifest, "validation", args.patch, args.core, 0, all_observations=True)
    halo = (args.patch - args.core) // 2
    core = np.s_[halo : halo + args.core, halo : halo + args.core]
    hidden_cache: dict[tuple[str, int], dict[str, Any]] = {}

    global_values: dict[str, list[float]] = defaultdict(list)
    role_values: dict[str, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
    for item_index in range(len(dataset)):
        batch = dataset[item_index]
        scene_id = str(batch["scene_id"])
        role = str(batch["role"])
        record = record_lookup[scene_id]
        canvas_shape = (int(record["canvas_size"]), int(record["canvas_size"]))
        for view, observation_index in enumerate(batch["observation_indices"].tolist()):
            observation = observation_lookup[(scene_id, int(observation_index))]
            cache_key = (scene_id, int(observation_index))
            hidden = hidden_cache.get(cache_key)
            if hidden is None:
                if observation["degradation"].get("requested_source_contrast_gray") is not None:
                    target_canvas = np.load(package / record["target"], mmap_mode="r", allow_pickle=False)
                    mask_canvas = np.load(package / record["mask"], mmap_mode="r", allow_pickle=False)
                    hidden = replay.replay_causal_stages(
                        np.asarray(target_canvas), np.asarray(mask_canvas), observation["degradation"],
                        int(observation["degradation_parameter_seed"]),
                    ).hidden_parameters
                else:
                    hidden = replay.recover_hidden_parameters(
                        observation["degradation"], int(observation["degradation_parameter_seed"]), canvas_shape,
                    )
                hidden_cache[cache_key] = hidden

            y0, x0 = (int(value) for value in batch["origins"][view].tolist())
            target_u8 = (batch["target"][view, 0].numpy() * 255.0).round().astype(np.uint8)
            mask_u8 = (batch["mask"][view, 0].numpy() * 255.0).round().astype(np.uint8)
            layers = replay.decompose_optical_layers(
                target_u8,
                mask_u8,
                record["texture"],
                observation["degradation"],
                int(observation["degradation_parameter_seed"]),
                canvas_shape=canvas_shape,
                crop_yx=(y0, x0),
                hidden_parameters=hidden,
            )
            optical = layers.shape_optical + layers.texture_optical
            prefade = layers.shape_prefade + layers.texture_prefade
            candidate_cache = {
                id(legacy_kernels): actual_boundary_candidates(prefade, legacy_kernels),
                id(kernels): actual_boundary_candidates(prefade, kernels),
                id(dense_reference_kernels): actual_boundary_candidates(prefade, dense_reference_kernels),
            }
            design_results: dict[str, dict[str, float]] = {}
            for design_name, (design_kernels, amplitude, slope, envelope) in designs.items():
                candidates = candidate_cache[id(design_kernels)]
                design_results[design_name] = boundary_capacity(
                    layers.boundary_target[core],
                    prefade[core],
                    candidates[:, core[0], core[1]],
                    output_amplitude=amplitude,
                    response_slope=slope,
                    envelope_size=envelope,
                )
            local_contrast = boundary_capacity(
                layers.local_contrast_target[core],
                optical[core],
                local_contrast_candidates(optical)[:, core[0], core[1]],
                output_amplitude=0.30,
                response_slope=8.0,
                envelope_size=49,
                envelope_scale=1.0,
            )
            local_contrast_expanded = boundary_capacity(
                layers.local_contrast_target[core],
                optical[core],
                local_contrast_candidates(optical)[:, core[0], core[1]],
                output_amplitude=0.32,
                response_slope=8.0,
                envelope_size=49,
                envelope_scale=2.0,
            )
            texture = bounded_capacity(layers.texture_target[core], 0.18)
            nuisance_target = (
                batch["noise_free_source"][view, 0].numpy() - batch["source"][view, 0].numpy()
            )[core]
            nuisance = bounded_capacity(nuisance_target, 0.18)
            radiometry_target = (
                optical - batch["noise_free_source"][view, 0].numpy()
            )[core]
            radiometry = bounded_capacity(radiometry_target, 0.34)

            inverse_gamma = 1.0 / max(float(observation["degradation"].get("gamma", 1.0)), 1e-8)
            inverse_exposure = 1.0 / max(float(observation["degradation"].get("exposure", 1.0)), 1e-8)
            values = {
                "texture_amplitude_coverage": texture["amplitude_coverage"],
                "texture_clipping_error_ratio": texture["clipping_error_ratio"],
                "local_contrast_sign_coverage": local_contrast["sign_coverage"],
                "local_contrast_amplitude_coverage": local_contrast["amplitude_coverage"],
                "local_contrast_optimistic_error_ratio": local_contrast["optimistic_error_ratio"],
                "local_contrast_expanded2_amplitude_coverage": local_contrast_expanded["amplitude_coverage"],
                "local_contrast_expanded2_optimistic_error_ratio": local_contrast_expanded["optimistic_error_ratio"],
                "nuisance_amplitude_coverage": nuisance["amplitude_coverage"],
                "nuisance_clipping_error_ratio": nuisance["clipping_error_ratio"],
                "radiometry_amplitude_coverage": radiometry["amplitude_coverage"],
                "radiometry_clipping_error_ratio": radiometry["clipping_error_ratio"],
                "inverse_gamma_inside_parameter_range": float(np.exp(-0.35) <= inverse_gamma <= np.exp(0.35)),
                "inverse_exposure_inside_parameter_range": float(np.exp(-0.55) <= inverse_exposure <= np.exp(0.55)),
            }
            for design_name, result in design_results.items():
                values[f"boundary_{design_name}_sign_coverage"] = result["sign_coverage"]
                values[f"boundary_{design_name}_amplitude_coverage"] = result["amplitude_coverage"]
                values[f"boundary_{design_name}_optimistic_error_ratio"] = result["optimistic_error_ratio"]
            for name, value in values.items():
                global_values[name].append(value)
                role_values[role][name].append(value)

    report: dict[str, Any] = {
        "analysis_id": "R94_BRANCH_EXPRESSIVITY_V2",
        "meaning": (
            "Necessary optimistic containment checks for the implemented branch bounds and exact causal layer targets; "
            "not trained-model performance. Boundary results ignore the required 17-pixel coefficient smoothness."
        ),
        "boundary_filter_count_implemented": len(kernels),
        "boundary_filter_count_dense_reference": len(dense_reference_kernels),
        "boundary_designs": {
            name: {
                "filter_count": len(design[0]),
                "output_amplitude": design[1],
                "response_slope": design[2],
                "envelope_size": design[3],
            }
            for name, design in designs.items()
        },
        "evaluated_views": len(global_values["boundary_implemented_sparse33_sign_coverage"]),
        "global": {name: summarize(values) for name, values in global_values.items()},
        "roles": {role: {name: summarize(values) for name, values in rows.items()} for role, rows in role_values.items()},
    }
    report["recommendation"] = {
        "boundary_bank_requires_redesign_before_training": (
            report["global"]["boundary_implemented_sparse33_amplitude_coverage"]["mean"] < 0.90
            or report["global"]["boundary_implemented_sparse33_optimistic_error_ratio"]["mean"] > 0.03
        ),
        "sparse_boundary_loses_material_capacity_vs_dense_reference": (
            report["global"]["boundary_implemented_sparse33_optimistic_error_ratio"]["mean"]
            > report["global"]["boundary_dense33_reference_optimistic_error_ratio"]["mean"] + 0.01
        ),
        "local_contrast_path_requires_redesign": (
            report["global"]["local_contrast_expanded2_amplitude_coverage"]["mean"] < 0.90
            or report["global"]["local_contrast_expanded2_optimistic_error_ratio"]["mean"] > 0.08
        ),
        "texture_bound_requires_expansion": report["global"]["texture_clipping_error_ratio"]["p95"] > 0.01,
        "nuisance_bound_requires_expansion": report["global"]["nuisance_clipping_error_ratio"]["p95"] > 0.01,
        "radiometry_bound_requires_expansion": report["global"]["radiometry_clipping_error_ratio"]["p95"] > 0.01,
        "radiometry_parameter_range_requires_expansion": (
            report["global"]["inverse_gamma_inside_parameter_range"]["mean"] < 1.0
            or report["global"]["inverse_exposure_inside_parameter_range"]["mean"] < 1.0
        ),
    }
    output = Path(args.report)
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(output.suffix + ".tmp")
    temporary.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    os.replace(temporary, output)
    print(json.dumps({
        "evaluated_views": report["evaluated_views"],
        "boundary_filter_count_implemented": report["boundary_filter_count_implemented"],
        "boundary_filter_count_dense_reference": report["boundary_filter_count_dense_reference"],
        "boundary_designs": {
            name: {
                "coverage_mean": report["global"][f"boundary_{name}_amplitude_coverage"]["mean"],
                "error_mean": report["global"][f"boundary_{name}_optimistic_error_ratio"]["mean"],
                "error_p95": report["global"][f"boundary_{name}_optimistic_error_ratio"]["p95"],
            }
            for name in designs
        },
        "non_boundary_global": {
            name: value for name, value in report["global"].items() if not name.startswith("boundary_")
        },
        "recommendation": report["recommendation"],
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

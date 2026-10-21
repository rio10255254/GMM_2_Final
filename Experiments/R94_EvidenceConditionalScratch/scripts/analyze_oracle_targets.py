"""Validate R94 target semantics before asking a model to learn them."""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
from collections import defaultdict
from pathlib import Path
import sys
from typing import Any

import numpy as np
import torch
import torch.nn.functional as F
import cv2


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
    array = np.asarray(values, dtype=np.float64)
    return {
        "count": int(array.size),
        "mean": float(array.mean()) if array.size else 0.0,
        "median": float(np.median(array)) if array.size else 0.0,
        "p95": float(np.percentile(array, 95)) if array.size else 0.0,
        "max": float(array.max()) if array.size else 0.0,
    }


def load_observation_lookup(manifest: dict[str, Any]) -> dict[tuple[str, int], dict[str, Any]]:
    lookup: dict[tuple[str, int], dict[str, Any]] = {}
    for record in manifest["records"]:
        for observation in record["observations"]:
            lookup[(str(record["scene_id"]), int(observation["observation"]))] = observation
    return lookup


def phase_shift(first: np.ndarray, second: np.ndarray) -> tuple[np.ndarray, float]:
    """Contrast-normalized Fourier shift; used only as an independent readout."""
    first = first.astype(np.float32)
    second = second.astype(np.float32)
    first = first - cv2.GaussianBlur(first, (0, 0), 3.0, borderType=cv2.BORDER_REFLECT_101)
    second = second - cv2.GaussianBlur(second, (0, 0), 3.0, borderType=cv2.BORDER_REFLECT_101)
    scale_first = float(np.sqrt(np.mean(first * first)))
    scale_second = float(np.sqrt(np.mean(second * second)))
    first /= max(scale_first, 1e-6)
    second /= max(scale_second, 1e-6)
    window = cv2.createHanningWindow((first.shape[1], first.shape[0]), cv2.CV_32F)
    shift, response = cv2.phaseCorrelate(first, second, window)
    return np.asarray([float(shift[0]), float(shift[1])], np.float64), float(response)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--patch", type=int, default=256)
    parser.add_argument("--core", type=int, default=128)
    parser.add_argument("--report", default=str(ROOT / "reports" / "oracle_target_validation.json"))
    args = parser.parse_args()
    torch.set_num_threads(2)
    trainer = load("r93_oracle_support", R93 / "training" / "train_r93.py")
    targets = load("r94_oracle_targets", ROOT / "training" / "counterfactual_targets.py")
    replay = load("r94_oracle_replay", ROOT / "training" / "causal_stage_replay.py")
    package = R93 / "data" / "r93_formal"
    manifest = json.loads((package / "manifest.json").read_text(encoding="utf-8"))
    observation_lookup = load_observation_lookup(manifest)
    record_lookup = {str(record["scene_id"]): record for record in manifest["records"]}
    hidden_cache: dict[tuple[str, int], dict[str, Any]] = {}
    dataset = trainer.R93SceneDataset(package, manifest, "validation", args.patch, args.core, 0, all_observations=True)
    halo = (args.patch - args.core) // 2
    core_slice = (slice(None), slice(None), slice(halo, halo + args.core), slice(halo, halo + args.core))

    global_values: dict[str, list[float]] = defaultdict(list)
    roles: dict[str, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
    motion_raw: list[np.ndarray] = []
    motion_oracle: list[np.ndarray] = []
    motion_target: list[np.ndarray] = []
    phase_motion_raw: list[np.ndarray] = []
    phase_motion_oracle: list[np.ndarray] = []
    phase_responses_raw: list[float] = []
    phase_responses_oracle: list[float] = []
    identity_change: list[float] = []
    identity_raw_error: list[float] = []
    identity_oracle_error: list[float] = []
    signed_motion_records = 0
    motion_records: list[dict[str, Any]] = []

    for item_index in range(len(dataset)):
        batch = dataset[item_index]
        source = batch["source"]
        noise_free = batch["noise_free_source"]
        target = batch["target"]
        mask = batch["mask"][core_slice]
        optical_views = []
        support_views = []
        boundary_component_views = []
        texture_component_views = []
        local_contrast_component_views = []
        local_contrast_clean_views = []
        local_contrast_optical_views = []
        boundary_clean_views = []
        boundary_optical_views = []
        texture_clean_views = []
        texture_optical_views = []
        scene_id = str(batch["scene_id"])
        record = record_lookup[scene_id]
        for view, observation_index in enumerate(batch["observation_indices"].tolist()):
            observation = observation_lookup[(scene_id, int(observation_index))]
            cache_key = (scene_id, int(observation_index))
            hidden = hidden_cache.get(cache_key)
            if hidden is None:
                if observation["degradation"].get("requested_source_contrast_gray") is not None:
                    target_canvas = np.load(package / record["target"], mmap_mode="r", allow_pickle=False)
                    mask_canvas = np.load(package / record["mask"], mmap_mode="r", allow_pickle=False)
                    replayed = replay.replay_causal_stages(
                        np.asarray(target_canvas),
                        np.asarray(mask_canvas),
                        observation["degradation"],
                        int(observation["degradation_parameter_seed"]),
                    )
                    hidden = replayed.hidden_parameters
                else:
                    hidden = replay.recover_hidden_parameters(
                        observation["degradation"],
                        int(observation["degradation_parameter_seed"]),
                        (int(record["canvas_size"]), int(record["canvas_size"])),
                    )
                hidden_cache[cache_key] = hidden
            y0, x0 = (int(value) for value in batch["origins"][view].tolist())
            target_u8 = (target[view, 0].numpy() * 255.0).round().astype(np.uint8)
            mask_u8 = (batch["mask"][view, 0].numpy() * 255.0).round().astype(np.uint8)
            layers = replay.decompose_optical_layers(
                target_u8,
                mask_u8,
                record["texture"],
                observation["degradation"],
                int(observation["degradation_parameter_seed"]),
                canvas_shape=(int(record["canvas_size"]), int(record["canvas_size"])),
                crop_yx=(y0, x0),
                hidden_parameters=hidden,
            )
            optical_crop = layers.shape_optical + layers.texture_optical
            support_crop = replay.boundary_support_from_metadata(
                mask_u8,
                observation["degradation"],
            )
            optical_views.append(torch.from_numpy(optical_crop)[None])
            support_views.append(torch.from_numpy(support_crop)[None])
            boundary_component_views.append(torch.from_numpy(layers.boundary_target)[None])
            texture_component_views.append(torch.from_numpy(layers.texture_target)[None])
            local_contrast_component_views.append(torch.from_numpy(layers.local_contrast_target)[None])
            local_contrast_clean_views.append(torch.from_numpy(
                layers.shape_prefade + layers.texture_prefade
            )[None])
            local_contrast_optical_views.append(torch.from_numpy(
                layers.shape_optical + layers.texture_optical
            )[None])
            boundary_clean_views.append(torch.from_numpy(layers.shape_clean)[None])
            boundary_optical_views.append(torch.from_numpy(layers.shape_prefade)[None])
            texture_clean_views.append(torch.from_numpy(layers.texture_clean)[None])
            texture_optical_views.append(torch.from_numpy(layers.texture_prefade)[None])
        optical_source = torch.stack(optical_views, dim=0).to(target)
        boundary_support = torch.stack(support_views, dim=0).to(target)
        views = targets.build_counterfactual_views(
            target, noise_free, source, boundary_support=boundary_support,
            optical_source=optical_source,
            local_contrast_component=torch.stack(local_contrast_component_views, dim=0).to(target),
            boundary_component=torch.stack(boundary_component_views, dim=0).to(target),
            texture_component=torch.stack(texture_component_views, dim=0).to(target),
            local_contrast_clean=torch.stack(local_contrast_clean_views, dim=0).to(target),
            local_contrast_optical=torch.stack(local_contrast_optical_views, dim=0).to(target),
            boundary_clean=torch.stack(boundary_clean_views, dim=0).to(target),
            boundary_optical=torch.stack(boundary_optical_views, dim=0).to(target),
            texture_clean=torch.stack(texture_clean_views, dim=0).to(target),
            texture_optical=torch.stack(texture_optical_views, dim=0).to(target),
        )
        oracle = views["S_noisy"].target[core_slice]
        raw = source[core_slice]
        truth = target[core_slice]
        view_count = int(raw.shape[0])
        boundary_level = batch["boundary_level"].repeat_interleave(view_count)
        polarity = batch["polarity"].repeat_interleave(view_count)
        raw_probability = trainer.foreground_probability(raw, boundary_level, polarity)
        oracle_probability = trainer.foreground_probability(oracle, boundary_level, polarity)
        truth_boundary = trainer.soft_boundary(mask)
        role = str(batch["role"])

        raw_pixel = torch.abs(raw - truth).mean(dim=(1, 2, 3))
        oracle_pixel = torch.abs(oracle - truth).mean(dim=(1, 2, 3))
        raw_fine = raw - trainer.lowpass(raw, 9)
        oracle_fine = oracle - trainer.lowpass(oracle, 9)
        truth_fine = truth - trainer.lowpass(truth, 9)
        raw_texture = torch.abs(raw_fine - truth_fine).mean(dim=(1, 2, 3))
        oracle_texture = torch.abs(oracle_fine - truth_fine).mean(dim=(1, 2, 3))
        raw_boundary = torch.abs(trainer.soft_boundary(raw_probability) - truth_boundary).mean(dim=(1, 2, 3))
        oracle_boundary = torch.abs(trainer.soft_boundary(oracle_probability) - truth_boundary).mean(dim=(1, 2, 3))

        for view in range(view_count):
            values = {
                "raw_pixel": float(raw_pixel[view]),
                "oracle_pixel": float(oracle_pixel[view]),
                "raw_texture": float(raw_texture[view]),
                "oracle_texture": float(oracle_texture[view]),
                "raw_boundary": float(raw_boundary[view]),
                "oracle_boundary": float(oracle_boundary[view]),
                "oracle_change_gray": float(torch.abs(oracle[view] - raw[view]).mean() * 255.0),
            }
            values["pixel_ratio"] = values["oracle_pixel"] / max(values["raw_pixel"], 1e-8)
            values["texture_ratio"] = values["oracle_texture"] / max(values["raw_texture"], 1e-8)
            values["boundary_ratio"] = values["oracle_boundary"] / max(values["raw_boundary"], 1e-8)
            for name, value in values.items():
                global_values[name].append(value)
                roles[role][name].append(value)

        identity = batch["identity"].numpy().astype(bool)
        for view in np.flatnonzero(identity):
            identity_change.append(float(torch.abs(oracle[view] - raw[view]).mean() * 255.0))
            identity_raw_error.append(float(raw_pixel[view] * 255.0))
            identity_oracle_error.append(float(oracle_pixel[view] * 255.0))

        if int(batch["pair_kind"]) == 1 and view_count == 2:
            support = F.max_pool2d(mask, 49, stride=1, padding=24)
            raw_centers = trainer.supported_edge_centroid(raw_probability, support).reshape(2, 2)
            oracle_centers = trainer.supported_edge_centroid(oracle_probability, support).reshape(2, 2)
            target_centers = trainer.supported_edge_centroid(mask, support).reshape(2, 2)
            motion_raw.append(((raw_centers[1] - raw_centers[0]) - (target_centers[1] - target_centers[0])).numpy())
            motion_oracle.append(((oracle_centers[1] - oracle_centers[0]) - (target_centers[1] - target_centers[0])).numpy())
            motion_target.append((target_centers[1] - target_centers[0]).numpy())
            motion_records.append({
                "scene_id": str(batch["scene_id"]),
                "observation_indices": batch["observation_indices"].tolist(),
                "target_delta_xy_px": (target_centers[1] - target_centers[0]).tolist(),
                "raw_error_xy_px": motion_raw[-1].tolist(),
                "oracle_error_xy_px": motion_oracle[-1].tolist(),
            })
            raw_arrays = raw[:, 0].numpy()
            oracle_arrays = oracle[:, 0].numpy()
            truth_arrays = truth[:, 0].numpy()
            raw_phase, raw_response = phase_shift(raw_arrays[0], raw_arrays[1])
            oracle_phase, oracle_response = phase_shift(oracle_arrays[0], oracle_arrays[1])
            target_phase, _target_response = phase_shift(truth_arrays[0], truth_arrays[1])
            phase_motion_raw.append(raw_phase - target_phase)
            phase_motion_oracle.append(oracle_phase - target_phase)
            phase_responses_raw.append(raw_response)
            phase_responses_oracle.append(oracle_response)
            signed_motion_records += 1

    raw_motion = np.asarray(motion_raw, dtype=np.float64)
    oracle_motion = np.asarray(motion_oracle, dtype=np.float64)
    raw_absolute = np.abs(raw_motion).reshape(-1)
    oracle_absolute = np.abs(oracle_motion).reshape(-1)
    axis_regression = oracle_absolute - raw_absolute
    positive_regression = axis_regression[axis_regression > 1e-7]
    raw_phase_motion = np.asarray(phase_motion_raw, dtype=np.float64)
    oracle_phase_motion = np.asarray(phase_motion_oracle, dtype=np.float64)
    raw_phase_absolute = np.abs(raw_phase_motion).reshape(-1)
    oracle_phase_absolute = np.abs(oracle_phase_motion).reshape(-1)
    report: dict[str, Any] = {
        "analysis_id": "R94_ORACLE_TARGET_VALIDATION_V1",
        "meaning": "Tests target semantics with truth-derived branches; this is not trained-model performance.",
        "evaluated_dataset_items": len(dataset),
        "evaluated_views": len(global_values["raw_pixel"]),
        "global": {name: summarize(values) for name, values in global_values.items()},
        "roles": {role: {name: summarize(values) for name, values in rows.items()} for role, rows in roles.items()},
        "identity": {
            "count": len(identity_change),
            "change_gray": summarize(identity_change),
            "raw_error_gray": summarize(identity_raw_error),
            "oracle_error_gray": summarize(identity_oracle_error),
        },
        "motion": {
            "pair_count": signed_motion_records,
            "raw_mae_px": float(raw_absolute.mean()) if raw_absolute.size else 0.0,
            "oracle_mae_px": float(oracle_absolute.mean()) if oracle_absolute.size else 0.0,
            "raw_p95_px": float(np.percentile(raw_absolute, 95)) if raw_absolute.size else 0.0,
            "oracle_p95_px": float(np.percentile(oracle_absolute, 95)) if oracle_absolute.size else 0.0,
            "raw_signed_bias_xy_px": np.mean(raw_motion, axis=0).tolist() if raw_motion.size else [0.0, 0.0],
            "oracle_signed_bias_xy_px": np.mean(oracle_motion, axis=0).tolist() if oracle_motion.size else [0.0, 0.0],
            "per_axis_regression_fraction": float(np.mean(oracle_absolute > raw_absolute + 1e-7)) if raw_absolute.size else 0.0,
            "positive_axis_regression_mean_px": float(positive_regression.mean()) if positive_regression.size else 0.0,
            "positive_axis_regression_p95_px": float(np.percentile(positive_regression, 95)) if positive_regression.size else 0.0,
            "positive_axis_regression_max_px": float(positive_regression.max()) if positive_regression.size else 0.0,
            "axis_regression_records": motion_records,
        },
        "phase_motion": {
            "pair_count": int(len(phase_motion_raw)),
            "raw_mae_px": float(raw_phase_absolute.mean()) if raw_phase_absolute.size else 0.0,
            "oracle_mae_px": float(oracle_phase_absolute.mean()) if oracle_phase_absolute.size else 0.0,
            "raw_p95_px": float(np.percentile(raw_phase_absolute, 95)) if raw_phase_absolute.size else 0.0,
            "oracle_p95_px": float(np.percentile(oracle_phase_absolute, 95)) if oracle_phase_absolute.size else 0.0,
            "raw_signed_bias_xy_px": np.mean(raw_phase_motion, axis=0).tolist() if raw_phase_motion.size else [0.0, 0.0],
            "oracle_signed_bias_xy_px": np.mean(oracle_phase_motion, axis=0).tolist() if oracle_phase_motion.size else [0.0, 0.0],
            "raw_response": summarize(phase_responses_raw),
            "oracle_response": summarize(phase_responses_oracle),
        },
    }
    raw_pixel_total = float(np.sum(global_values["raw_pixel"]))
    oracle_pixel_total = float(np.sum(global_values["oracle_pixel"]))
    raw_texture_total = float(np.sum(global_values["raw_texture"]))
    oracle_texture_total = float(np.sum(global_values["oracle_texture"]))
    raw_boundary_total = float(np.sum(global_values["raw_boundary"]))
    oracle_boundary_total = float(np.sum(global_values["oracle_boundary"]))
    report["stable_improvement"] = {
        "pixel_total_error_ratio": oracle_pixel_total / max(raw_pixel_total, 1e-8),
        "texture_total_error_ratio": oracle_texture_total / max(raw_texture_total, 1e-8),
        "boundary_total_error_ratio": oracle_boundary_total / max(raw_boundary_total, 1e-8),
        "pixel_improved_view_fraction": float(np.mean(np.asarray(global_values["oracle_pixel"]) < np.asarray(global_values["raw_pixel"]))),
        "texture_improved_view_fraction": float(np.mean(np.asarray(global_values["oracle_texture"]) < np.asarray(global_values["raw_texture"]))),
        "boundary_improved_view_fraction": float(np.mean(np.asarray(global_values["oracle_boundary"]) < np.asarray(global_values["raw_boundary"]))),
        "pixel_ratio_p95": report["global"]["pixel_ratio"]["p95"],
        "texture_ratio_p95": report["global"]["texture_ratio"]["p95"],
        "boundary_ratio_p95": report["global"]["boundary_ratio"]["p95"],
        "note": "Ratios of total error control the decision. Mean per-view ratios are diagnostic only because near-zero Raw denominators are unstable.",
    }
    report["oracle_semantics_support_joint_improvement"] = bool(
        report["stable_improvement"]["pixel_total_error_ratio"] < 1.0
        and report["stable_improvement"]["texture_total_error_ratio"] < 1.0
        and report["stable_improvement"]["boundary_total_error_ratio"] < 1.0
        and report["stable_improvement"]["pixel_ratio_p95"] < 1.0
        and report["stable_improvement"]["texture_ratio_p95"] < 1.0
        and report["motion"]["oracle_mae_px"] <= report["motion"]["raw_mae_px"]
        and report["motion"]["oracle_p95_px"] <= report["motion"]["raw_p95_px"]
        and report["phase_motion"]["oracle_mae_px"] <= report["phase_motion"]["raw_mae_px"]
        and report["phase_motion"]["oracle_p95_px"] <= report["phase_motion"]["raw_p95_px"]
    )
    output = Path(args.report)
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(output.suffix + ".tmp")
    temporary.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    os.replace(temporary, output)
    print(json.dumps({
        "joint_improvement": report["oracle_semantics_support_joint_improvement"],
        "views": report["evaluated_views"],
        "pixel_ratio_mean": report["global"]["pixel_ratio"]["mean"],
        "texture_ratio_mean": report["global"]["texture_ratio"]["mean"],
        "boundary_ratio_mean": report["global"]["boundary_ratio"]["mean"],
        "motion": report["motion"],
        "phase_motion": report["phase_motion"],
        "identity": report["identity"],
        "stable_improvement": report["stable_improvement"],
    }, indent=2, ensure_ascii=False))
    return 0 if report["oracle_semantics_support_joint_improvement"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

"""Read-only causal audit of R114C E024, with R114B E024 as a control.

The script never changes training code, model code, source data, or checkpoints.
It replays the fixed 128-scene validation population, reconstructs the exact
runtime gate used by each checkpoint, and tests direction, calibration,
coordinate, action-scale, and oracle counterfactuals.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
import csv
import hashlib
import json
import math
from pathlib import Path
import sys
from typing import Any, Iterable

import numpy as np
from scipy import stats
import torch
from torch.utils.data import DataLoader


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from model.r114_split_profile_model import build_split_profile_model  # noqa: E402
from training.dataset import R114Dataset  # noqa: E402
from training.split_profile_targets import build_split_profile_targets  # noqa: E402


RUNS = {
    "R114B_E24": ROOT / "runs" / "r114b_split_profile_probe_scratch_20260830",
    "R114C_E24": ROOT / "runs" / "r114c_split_profile_repair_scratch_20260830",
}
DEFAULT_OUTPUT = ROOT / "results" / "split_profile_repair" / "E024_deep_failure_diagnosis"
OLD_B_DIAGNOSIS = ROOT / "results" / "split_profile_probe" / "E024_failure_diagnosis" / "diagnosis.json"
ALPHAS = np.linspace(0.0, 1.0, 41, dtype=np.float64)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def atomic_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, allow_nan=False),
        encoding="utf-8",
    )
    temporary.replace(path)


def finite(value: Any) -> float | None:
    result = float(value)
    return result if math.isfinite(result) else None


def scene_mean(value: torch.Tensor) -> torch.Tensor:
    return value.flatten(1).mean(1)


def weighted_scene_mean(value: torch.Tensor, weight: torch.Tensor) -> torch.Tensor:
    numerator = (value * weight).flatten(1).sum(1)
    denominator = weight.flatten(1).sum(1).clamp_min(1.0e-8)
    return numerator / denominator


def apply_delta(base: torch.Tensor, delta: torch.Tensor) -> torch.Tensor:
    return (base + delta).clamp(0.0, 1.0)


def analytic_proposal(
    cue: torch.Tensor,
    midpoint_offset: torch.Tensor,
    contrast: torch.Tensor,
    coordinate: torch.Tensor,
    width: torch.Tensor,
) -> torch.Tensor:
    midpoint = (cue + midpoint_offset).clamp(0.0, 1.0)
    return (
        midpoint
        + 0.5 * contrast * torch.tanh(coordinate / width.clamp(0.8, 3.5))
    ).clamp(0.0, 1.0)


def bounded_proposal_delta(proposal: torch.Tensor, base: torch.Tensor) -> torch.Tensor:
    return (proposal - base).clamp(-48.0 / 255.0, 48.0 / 255.0)


def optimal_visibility(residual: torch.Tensor, unit_delta: torch.Tensor) -> torch.Tensor:
    safe = torch.where(
        unit_delta.abs() > 1.0e-8,
        unit_delta,
        torch.ones_like(unit_delta),
    )
    return torch.where(
        residual * unit_delta > 0,
        (residual / safe).clamp(0.0, 1.0),
        torch.zeros_like(unit_delta),
    )


class Reservoir:
    """Deterministic bounded pixel sample used only for correlations/calibration."""

    def __init__(self, maximum: int, seed: int):
        self.maximum = int(maximum)
        self.rng = np.random.default_rng(seed)
        self.matrix = np.empty((0, 0), np.float32)
        self.eligible = 0

    def add(self, columns: Iterable[torch.Tensor], mask: torch.Tensor) -> None:
        arrays = [column.detach()[mask].float().cpu().numpy().reshape(-1) for column in columns]
        if not arrays or not arrays[0].size:
            return
        incoming = np.stack(arrays, axis=1)
        self.eligible += int(incoming.shape[0])
        if self.matrix.size == 0:
            combined = incoming
        else:
            combined = np.concatenate([self.matrix, incoming], axis=0)
        if combined.shape[0] > self.maximum:
            selected = self.rng.choice(combined.shape[0], self.maximum, replace=False)
            combined = combined[selected]
        self.matrix = combined


def correlation(target: np.ndarray, prediction: np.ndarray) -> dict[str, Any]:
    valid = np.isfinite(target) & np.isfinite(prediction)
    target = target[valid]
    prediction = prediction[valid]
    if target.size < 3 or np.std(target) < 1.0e-12 or np.std(prediction) < 1.0e-12:
        return {
            "count": int(target.size),
            "pearson": None,
            "spearman": None,
            "prediction_from_target_slope": None,
            "prediction_from_target_intercept": None,
        }
    slope, intercept = np.polyfit(target, prediction, 1)
    return {
        "count": int(target.size),
        "pearson": finite(stats.pearsonr(target, prediction).statistic),
        "spearman": finite(stats.spearmanr(target, prediction).statistic),
        "prediction_from_target_slope": finite(slope),
        "prediction_from_target_intercept": finite(intercept),
    }


def visibility_calibration(matrix: np.ndarray, eligible: int) -> dict[str, Any]:
    # Columns: target, prediction, support weight.
    target = matrix[:, 0].astype(np.float64)
    prediction = matrix[:, 1].astype(np.float64)
    weight = matrix[:, 2].astype(np.float64)
    valid = np.isfinite(target) & np.isfinite(prediction) & np.isfinite(weight) & (weight > 0)
    target, prediction, weight = target[valid], prediction[valid], weight[valid]
    weight_sum = max(float(weight.sum()), 1.0e-12)
    result = correlation(target, prediction)
    result.update(
        {
            "eligible_pixel_count": int(eligible),
            "sampled_pixel_count": int(target.size),
            "weighted_target_mean": finite(np.sum(weight * target) / weight_sum),
            "weighted_prediction_mean": finite(np.sum(weight * prediction) / weight_sum),
            "weighted_mae": finite(np.sum(weight * np.abs(prediction - target)) / weight_sum),
            "weighted_brier": finite(np.sum(weight * np.square(prediction - target)) / weight_sum),
        }
    )
    near_zero = target <= 0.05
    if near_zero.any():
        zero_weight = weight[near_zero]
        zero_sum = max(float(zero_weight.sum()), 1.0e-12)
        result["prediction_when_target_le_0_05"] = finite(
            np.sum(zero_weight * prediction[near_zero]) / zero_sum
        )
        result["fraction_prediction_ge_0_50_when_target_le_0_05"] = finite(
            np.sum(zero_weight * (prediction[near_zero] >= 0.50)) / zero_sum
        )
    bins: list[dict[str, Any]] = []
    for lower, upper in zip(np.linspace(0, 1, 11)[:-1], np.linspace(0, 1, 11)[1:]):
        selected = (prediction >= lower) & (prediction < upper if upper < 1 else prediction <= upper)
        if not selected.any():
            continue
        selected_weight = weight[selected]
        mass = float(selected_weight.sum())
        bins.append(
            {
                "predicted_range": [finite(lower), finite(upper)],
                "sample_count": int(selected.sum()),
                "weight_mass": mass,
                "prediction_mean": finite(np.sum(selected_weight * prediction[selected]) / mass),
                "target_mean": finite(np.sum(selected_weight * target[selected]) / mass),
            }
        )
    result["prediction_bins"] = bins
    return result


def aggregate(rows: list[dict[str, Any]], group_key: str) -> dict[str, Any]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[str(row[group_key])].append(row)
    result: dict[str, Any] = {}
    excluded = {"checkpoint", "record_id", "family", "role", "challenge"}
    for group, items in sorted(grouped.items()):
        summary: dict[str, Any] = {"scenes": len(items)}
        for key in sorted(set().union(*(item.keys() for item in items)) - excluded):
            values = [item.get(key) for item in items]
            values = np.asarray([value for value in values if value is not None], np.float64)
            if values.size:
                summary[key + "_mean"] = finite(values.mean())
                summary[key + "_median"] = finite(np.median(values))
                summary[key + "_p10"] = finite(np.quantile(values, 0.10))
                summary[key + "_p90"] = finite(np.quantile(values, 0.90))
        result[group] = summary
    return result


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    fields = sorted(set().union(*(row.keys() for row in rows)))
    with path.open("w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


@torch.no_grad()
def audit_checkpoint(
    name: str,
    checkpoint_path: Path,
    device: torch.device,
    batch_size: int,
    workers: int,
    pixel_sample: int,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    payload = torch.load(checkpoint_path, map_location="cpu", weights_only=False)
    if int(payload.get("epoch", -1)) != 24:
        raise RuntimeError(f"{checkpoint_path} is not E024")
    model = build_split_profile_model(compact=False).to(device)
    model.load_state_dict(payload["model"], strict=True)
    model.eval()

    dataset = R114Dataset("validation", epoch=0, limit=128)
    loader = DataLoader(
        dataset,
        batch_size=batch_size,
        shuffle=False,
        num_workers=workers,
        pin_memory=device.type == "cuda",
    )
    parameter_samples = {
        "midpoint_offset": Reservoir(pixel_sample, 11401),
        "signed_contrast": Reservoir(pixel_sample, 11402),
        "profile_width": Reservoir(pixel_sample, 11403),
        "profile_visibility": Reservoir(pixel_sample, 11404),
        "signed_sdf_px": Reservoir(pixel_sample, 11405),
    }
    rows: list[dict[str, Any]] = []
    scale_global_error = np.zeros_like(ALPHAS)
    scale_band_error = np.zeros_like(ALPHAS)
    scale_band_mass = 0.0
    scale_pixel_mass = 0

    for batch_index, cpu_batch in enumerate(loader, start=1):
        batch = {
            key: value.to(device, non_blocking=True) if isinstance(value, torch.Tensor) else value
            for key, value in cpu_batch.items()
        }
        source = batch["source"].float()
        target = batch["target"].float()
        true_sdf = batch["sdf"].float()
        details = model.forward_details(source)
        targets = build_split_profile_targets(
            source,
            target,
            true_sdf,
            batch["identity"],
            batch["flat"],
            base_output=details.base_output.detach(),
            midpoint_source=details.shifted_base.detach(),
            deployment_sdf_px=details.predicted_sdf_px.detach(),
            deployment_boundary_confidence=details.boundary_confidence.detach(),
            midpoint_cue_window_px=model.config.local_range_window_px,
        )
        true_coordinate_targets = build_split_profile_targets(
            source,
            target,
            true_sdf,
            batch["identity"],
            batch["flat"],
            base_output=details.base_output.detach(),
            midpoint_source=details.shifted_base.detach(),
            deployment_sdf_px=true_sdf,
            deployment_boundary_confidence=details.boundary_confidence.detach(),
            midpoint_cue_window_px=model.config.local_range_window_px,
        )

        base = details.base_output
        residual = target - base
        base_error = residual.abs()
        true_band = targets.boundary_band
        predicted_band = details.profile_band
        boundary = details.boundary_confidence
        need = details.correction_need
        recoverability = details.recoverability
        visibility = details.profile_visibility
        learned_proposal_delta = details.profile_proposal_delta

        current_delta = boundary * visibility * predicted_band * learned_proposal_delta
        old_triple_delta = (
            boundary * need * recoverability * visibility * predicted_band * learned_proposal_delta
        )
        # R114B was trained and validated with the old triple controller gate;
        # R114C was trained and validated with the boundary-only controller gate.
        runtime_delta = old_triple_delta if name == "R114B_E24" else current_delta
        runtime_output = apply_delta(base, runtime_delta)
        runtime_effective_delta = runtime_output - base

        target_pred_proposal = targets.oracle_profile_proposal
        target_pred_delta = bounded_proposal_delta(target_pred_proposal, base)
        learned_true_proposal = analytic_proposal(
            details.profile_midpoint_cue,
            details.midpoint_offset,
            details.signed_plateau_contrast,
            true_sdf,
            details.profile_width,
        )
        learned_true_delta = bounded_proposal_delta(learned_true_proposal, base)
        target_true_proposal = true_coordinate_targets.oracle_profile_proposal
        target_true_delta = bounded_proposal_delta(target_true_proposal, base)
        true_band_runtime = model._profile_band(true_sdf)

        learned_unit_pred = boundary * predicted_band * learned_proposal_delta
        target_unit_pred = boundary * predicted_band * target_pred_delta
        target_unit_true = boundary * true_band_runtime * target_true_delta
        learned_optimal_visibility = optimal_visibility(residual, learned_unit_pred)
        target_pred_optimal_visibility = optimal_visibility(residual, target_unit_pred)
        target_true_optimal_visibility = optimal_visibility(residual, target_unit_true)

        variants: dict[str, torch.Tensor] = {
            "runtime_actual": runtime_delta,
            "current_boundary_gate": current_delta,
            "old_triple_gate": old_triple_delta,
            "add_need_only": boundary * need * visibility * predicted_band * learned_proposal_delta,
            "add_recoverability_only": boundary * recoverability * visibility * predicted_band * learned_proposal_delta,
            "remove_boundary": visibility * predicted_band * learned_proposal_delta,
            "boundary_with_visibility_one": boundary * predicted_band * learned_proposal_delta,
            "oracle_visibility_learned_pred_coordinate": (
                boundary * targets.profile_visibility * predicted_band * learned_proposal_delta
            ),
            "oracle_parameters_pred_coordinate_pred_visibility": (
                boundary * visibility * predicted_band * target_pred_delta
            ),
            "oracle_parameters_visibility_pred_coordinate": (
                boundary * targets.profile_visibility * predicted_band * target_pred_delta
            ),
            "oracle_coordinate_learned_pred_visibility": (
                boundary * visibility * true_band_runtime * learned_true_delta
            ),
            "oracle_coordinate_parameters_pred_visibility": (
                boundary * visibility * true_band_runtime * target_true_delta
            ),
            "oracle_coordinate_parameters_visibility": (
                boundary
                * true_coordinate_targets.profile_visibility
                * true_band_runtime
                * target_true_delta
            ),
            "oracle_coordinate_parameters_visibility_no_boundary": (
                true_coordinate_targets.profile_visibility * true_band_runtime * target_true_delta
            ),
            "optimal_visibility_learned_pred_coordinate": (
                learned_optimal_visibility * learned_unit_pred
            ),
            "optimal_visibility_parameters_pred_coordinate": (
                target_pred_optimal_visibility * target_unit_pred
            ),
            "optimal_visibility_parameters_true_coordinate": (
                target_true_optimal_visibility * target_unit_true
            ),
        }

        action_mask = (runtime_delta.abs() * 255.0 >= 0.10) & (residual.abs() * 255.0 >= 0.10)
        direction_weight = runtime_effective_delta.abs() * action_mask
        runtime_gain = base_error - (runtime_output - target).abs()
        scene_scale_global: list[torch.Tensor] = []
        scene_scale_band: list[torch.Tensor] = []
        for alpha in ALPHAS:
            scaled_error = (apply_delta(base, runtime_delta * float(alpha)) - target).abs()
            scene_scale_global.append(scene_mean(scaled_error))
            scene_scale_band.append(weighted_scene_mean(scaled_error, true_band))
        scene_scale_global_tensor = torch.stack(scene_scale_global, dim=0)
        scene_scale_band_tensor = torch.stack(scene_scale_band, dim=0)
        scene_best_global_index = scene_scale_global_tensor.argmin(dim=0)
        scene_best_band_index = scene_scale_band_tensor.argmin(dim=0)
        alpha_tensor = torch.as_tensor(ALPHAS, device=device, dtype=base.dtype)
        measurements: dict[str, torch.Tensor] = {
            "base_mae": scene_mean(base_error),
            "runtime_mae": scene_mean((runtime_output - target).abs()),
            "runtime_gain_global": scene_mean(runtime_gain),
            "runtime_gain_true_band": weighted_scene_mean(runtime_gain, true_band),
            "runtime_harmful_fraction_true_band": weighted_scene_mean(
                (runtime_gain < 0).float(), true_band
            ),
            "runtime_direction_agreement_weighted": weighted_scene_mean(
                (torch.sign(runtime_effective_delta) == torch.sign(residual)).float(), direction_weight
            ),
            "runtime_direction_agreement_unweighted": weighted_scene_mean(
                (torch.sign(runtime_effective_delta) == torch.sign(residual)).float(), action_mask.float()
            ),
            "runtime_action_fraction": scene_mean(action_mask.float()),
            "runtime_preclamp_profile_delta_abs_gray_global": 255.0 * scene_mean(runtime_delta.abs()),
            "runtime_preclamp_profile_delta_abs_gray_true_band": 255.0 * weighted_scene_mean(runtime_delta.abs(), true_band),
            "runtime_effective_profile_delta_abs_gray_global": 255.0 * scene_mean(runtime_effective_delta.abs()),
            "runtime_effective_profile_delta_abs_gray_true_band": 255.0 * weighted_scene_mean(runtime_effective_delta.abs(), true_band),
            "geometry_delta_abs_gray_global": 255.0 * scene_mean((base - source).abs()),
            "total_reconstruction_delta_abs_gray_global": 255.0 * scene_mean((runtime_output - source).abs()),
            "proposal_delta_abs_gray_true_band": 255.0 * weighted_scene_mean(
                learned_proposal_delta.abs(), true_band
            ),
            "per_scene_best_global_alpha": alpha_tensor[scene_best_global_index],
            "per_scene_best_true_band_alpha": alpha_tensor[scene_best_band_index],
            "per_scene_best_global_improvement": (
                scene_scale_global_tensor[0] - scene_scale_global_tensor.gather(
                    0, scene_best_global_index.unsqueeze(0)
                ).squeeze(0)
            ),
            "visibility_global": scene_mean(visibility),
            "visibility_true_band": weighted_scene_mean(visibility, true_band),
            "visibility_target_true_band": weighted_scene_mean(targets.profile_visibility, true_band),
            "visibility_error_true_band": weighted_scene_mean(
                (visibility - targets.profile_visibility).abs(), true_band
            ),
            "boundary_true_band": weighted_scene_mean(boundary, true_band),
            "boundary_global": scene_mean(boundary),
            "need_true_band": weighted_scene_mean(need, true_band),
            "recoverability_true_band": weighted_scene_mean(recoverability, true_band),
            "predicted_band_support_fraction": scene_mean((predicted_band > 0.05).float()),
            "true_band_support_fraction": scene_mean((true_band > 0.05).float()),
            "predicted_visibility_positive_fraction": scene_mean((visibility > 0.05).float()),
            "target_visibility_positive_fraction": scene_mean(
                (targets.profile_visibility > 0.05).float()
            ),
            "visibility_supervision_support_fraction": scene_mean(
                (targets.profile_visibility_weight > 0.05).float()
            ),
            "current_gate_true_band": weighted_scene_mean(
                boundary * visibility * predicted_band, true_band
            ),
            "old_triple_gate_true_band": weighted_scene_mean(
                boundary * need * recoverability * visibility * predicted_band, true_band
            ),
            "predicted_sdf_sign_agreement_true_band": weighted_scene_mean(
                (torch.sign(details.predicted_sdf_px) == torch.sign(true_sdf)).float(), true_band
            ),
            "predicted_sdf_mae_true_band_px": weighted_scene_mean(
                (details.predicted_sdf_px - true_sdf).abs(), true_band
            ),
            "predicted_boundary_offset_abs_px": weighted_scene_mean(
                details.predicted_sdf_px.abs(), targets.boundary_binary
            ),
            "midpoint_abs_error_gray": 255.0 * weighted_scene_mean(
                (details.midpoint_offset - targets.midpoint_offset).abs(), targets.profile_weight
            ),
            "contrast_abs_error_gray": 255.0 * weighted_scene_mean(
                (details.signed_plateau_contrast - targets.signed_plateau_contrast).abs(),
                targets.profile_weight,
            ),
            "contrast_sign_agreement": weighted_scene_mean(
                (
                    torch.sign(details.signed_plateau_contrast)
                    == torch.sign(targets.signed_plateau_contrast)
                ).float(),
                targets.profile_weight,
            ),
            "profile_width_abs_error_px": weighted_scene_mean(
                (details.profile_width - targets.profile_width).abs(), targets.profile_weight
            ),
        }
        for variant_name, variant_delta in variants.items():
            variant_output = apply_delta(base, variant_delta)
            variant_gain = base_error - (variant_output - target).abs()
            measurements[f"{variant_name}_mae"] = scene_mean((variant_output - target).abs())
            measurements[f"{variant_name}_gain_true_band"] = weighted_scene_mean(
                variant_gain, true_band
            )
            measurements[f"{variant_name}_delta_abs_gray_true_band"] = (
                255.0 * weighted_scene_mean(variant_delta.abs(), true_band)
            )

        for scene_index in range(source.shape[0]):
            row: dict[str, Any] = {
                "checkpoint": name,
                "record_id": str(batch["record_id"][scene_index]),
                "family": str(batch["family"][scene_index]),
                "role": str(batch["role"][scene_index]),
                "challenge": str(batch["challenge"][scene_index]),
            }
            for metric_name, values in measurements.items():
                row[metric_name] = finite(values[scene_index].cpu())
            rows.append(row)

        for alpha_index, _alpha in enumerate(ALPHAS):
            scaled_error = (
                scene_scale_global_tensor[alpha_index]
                .reshape(-1, 1, 1, 1)
                .expand_as(target)
            )
            # Global error can be recovered exactly from the per-scene means
            # because every fixed-validation scene has the same 256x256 size.
            scale_global_error[alpha_index] += float(scaled_error.sum().cpu())
            # The band aggregate requires the original weighted numerator.
            scaled_output = apply_delta(base, runtime_delta * float(ALPHAS[alpha_index]))
            scale_band_error[alpha_index] += float(
                (((scaled_output - target).abs()) * true_band).sum().cpu()
            )
        scale_pixel_mass += int(target.numel())
        scale_band_mass += float(true_band.sum().cpu())

        parameter_mask = (targets.profile_weight > 0.05) & (true_band > 0.05)
        visibility_mask = targets.profile_visibility_weight > 0.05
        sdf_mask = true_band > 0.05
        parameter_samples["midpoint_offset"].add(
            [targets.midpoint_offset, details.midpoint_offset], parameter_mask
        )
        parameter_samples["signed_contrast"].add(
            [targets.signed_plateau_contrast, details.signed_plateau_contrast], parameter_mask
        )
        parameter_samples["profile_width"].add(
            [targets.profile_width, details.profile_width], parameter_mask
        )
        parameter_samples["profile_visibility"].add(
            [targets.profile_visibility, visibility, targets.profile_visibility_weight],
            visibility_mask,
        )
        parameter_samples["signed_sdf_px"].add(
            [true_sdf, details.predicted_sdf_px], sdf_mask
        )
        print(f"{name}: batch {batch_index}/{len(loader)}", flush=True)

    numeric_fields = sorted(
        key
        for key in set().union(*(row.keys() for row in rows))
        if key not in {"checkpoint", "record_id", "family", "role", "challenge"}
    )
    overall = {
        key: finite(np.mean([row[key] for row in rows if row.get(key) is not None]))
        for key in numeric_fields
    }
    scale_curve = []
    for alpha_index, alpha in enumerate(ALPHAS):
        global_mae = scale_global_error[alpha_index] / max(scale_pixel_mass, 1)
        band_mae = scale_band_error[alpha_index] / max(scale_band_mass, 1.0e-12)
        scale_curve.append(
            {
                "alpha": finite(alpha),
                "global_mae": finite(global_mae),
                "true_band_mae": finite(band_mae),
            }
        )
    best_global = min(scale_curve, key=lambda row: row["global_mae"])
    best_band = min(scale_curve, key=lambda row: row["true_band_mae"])

    correlations: dict[str, Any] = {}
    for parameter_name in ("midpoint_offset", "signed_contrast", "profile_width", "signed_sdf_px"):
        reservoir = parameter_samples[parameter_name]
        correlations[parameter_name] = correlation(reservoir.matrix[:, 0], reservoir.matrix[:, 1])
        correlations[parameter_name]["eligible_pixel_count"] = reservoir.eligible
    visibility_reservoir = parameter_samples["profile_visibility"]
    correlations["profile_visibility"] = visibility_calibration(
        visibility_reservoir.matrix, visibility_reservoir.eligible
    )

    stored = payload["validation"]
    return (
        {
            "checkpoint": {
                "name": name,
                "path": str(checkpoint_path.resolve()),
                "sha256": sha256(checkpoint_path),
                "epoch": int(payload["epoch"]),
                "stage": str(payload["stage"]),
                "scratch": bool(payload["scratch"]),
                "source_sha256": payload.get("source_sha256", {}),
            },
            "stored_validation": stored,
            "overall": overall,
            "scale_sweep_0_to_1": {
                "curve": scale_curve,
                "best_global": best_global,
                "best_true_band": best_band,
            },
            "correlations_and_calibration": correlations,
            "by_role": aggregate(rows, "role"),
            "by_challenge": aggregate(rows, "challenge"),
            "by_family": aggregate(rows, "family"),
        },
        rows,
    )


def build_comparison(audits: dict[str, Any]) -> dict[str, Any]:
    b = audits["R114B_E24"]["overall"]
    c = audits["R114C_E24"]["overall"]
    b_old = json.loads(OLD_B_DIAGNOSIS.read_text(encoding="utf-8"))
    b_old_overall = b_old["overall"]
    return {
        "stored_validation": {
            name: audit["stored_validation"] for name, audit in audits.items()
        },
        "exact_runtime_replay_error": {
            name: finite(
                abs(audit["overall"]["runtime_actual_mae"] - audit["stored_validation"]["mae"])
            )
            for name, audit in audits.items()
        },
        "r114c_vs_r114b": {
            "whole_image_visibility_ratio_c_over_b": finite(c["visibility_global"] / max(b["visibility_global"], 1e-12)),
            "true_band_visibility_ratio_c_over_b": finite(c["visibility_true_band"] / max(b["visibility_true_band"], 1e-12)),
            "true_band_proposal_magnitude_ratio_c_over_b": finite(
                c["proposal_delta_abs_gray_true_band"] / max(b["proposal_delta_abs_gray_true_band"], 1e-12)
            ),
            "true_band_runtime_delta_ratio_c_over_b": finite(
                c["runtime_effective_profile_delta_abs_gray_true_band"]
                / max(b["runtime_effective_profile_delta_abs_gray_true_band"], 1e-12)
            ),
            "current_gate_ratio_c_over_b_old_runtime_gate": finite(
                c["current_gate_true_band"] / max(b["old_triple_gate_true_band"], 1e-12)
            ),
            "mae_regression_c": finite(c["runtime_actual_mae"] - c["base_mae"]),
            "mae_regression_b": finite(b["runtime_actual_mae"] - b["base_mae"]),
        },
        "r114c_gate_causal_decomposition": {
            "base_mae": c["base_mae"],
            "current_boundary_gate_mae": c["current_boundary_gate_mae"],
            "add_need_only_mae": c["add_need_only_mae"],
            "add_recoverability_only_mae": c["add_recoverability_only_mae"],
            "old_triple_gate_mae": c["old_triple_gate_mae"],
            "fraction_of_current_regression_removed_by_old_triple_gate": finite(
                1.0
                - (c["old_triple_gate_mae"] - c["base_mae"])
                / max(c["current_boundary_gate_mae"] - c["base_mae"], 1e-12)
            ),
        },
        "r114b_original_forensic_reference": {
            "path": str(OLD_B_DIAGNOSIS.resolve()),
            "sha256": sha256(OLD_B_DIAGNOSIS),
            "runtime_mae": b_old_overall["output_mae"],
            "base_mae": b_old_overall["base_mae"],
            "direction_agreement": b_old_overall["direction_sign_agreement_action"],
            "gain_true_band": b_old_overall["profile_gain_band"],
            "visibility_pred_true_band": b_old_overall["visibility_pred_band"],
            "visibility_target_old_true_band": b_old_overall["visibility_target_band"],
            "runtime_gate_true_band": b_old_overall["profile_gate_band"],
            "runtime_delta_abs_gray_true_band": b_old_overall["profile_delta_abs_gray_band"],
            "predicted_sdf_sign_agreement": b_old_overall["predicted_sdf_sign_agreement_band"],
            "predicted_boundary_offset_abs_px": b_old_overall["predicted_boundary_offset_abs_px"],
            "parameter_correlations": b_old["correlations"],
        },
    }


@torch.no_grad()
def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--device", default="cuda" if torch.cuda.is_available() else "cpu")
    parser.add_argument("--batch-size", type=int, default=8)
    parser.add_argument("--workers", type=int, default=0)
    parser.add_argument("--pixel-sample", type=int, default=400_000)
    args = parser.parse_args()

    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    device = torch.device(args.device)
    audits: dict[str, Any] = {}
    all_rows: list[dict[str, Any]] = []
    for name, run in RUNS.items():
        checkpoint = run / "weights" / "epoch_024.pth"
        audit, rows = audit_checkpoint(
            name,
            checkpoint,
            device,
            args.batch_size,
            args.workers,
            args.pixel_sample,
        )
        audits[name] = audit
        all_rows.extend(rows)
        if device.type == "cuda":
            torch.cuda.empty_cache()

    relevant_sources = [
        ROOT / "model" / "r114_split_profile_model.py",
        ROOT / "training" / "split_profile_targets.py",
        ROOT / "training" / "split_profile_losses.py",
        ROOT / "training" / "train_split_profile.py",
        Path(__file__).resolve(),
    ]
    diagnosis = {
        "schema_version": 1,
        "read_only_forensics": True,
        "fixed_validation_contract": {
            "split": "validation",
            "dataset_epoch": 0,
            "limit": 128,
            "image_shape": [256, 256],
            "scale_sweep": [finite(value) for value in ALPHAS],
        },
        "source_hashes_at_analysis": {
            str(path.relative_to(ROOT)): sha256(path) for path in relevant_sources
        },
        "audits": audits,
        "comparison": build_comparison(audits),
    }
    write_csv(output / "scene_metrics.csv", all_rows)
    atomic_json(output / "diagnosis.json", diagnosis)
    print(
        json.dumps(
            {
                "output": str(output),
                "R114B": audits["R114B_E24"]["overall"],
                "R114C": audits["R114C_E24"]["overall"],
                "comparison": diagnosis["comparison"],
            },
            indent=2,
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()

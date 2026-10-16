"""Reproducible forensic audit for the E024 bounded-profile regression.

This probe is intentionally read-only with respect to the active run, source
data, model code, and trainer.  It loads the frozen E024 checkpoint, replays the
same 128-scene epoch-0 validation schedule, and decomposes the profile action
into direction, magnitude, parameter, gate, and runtime/training-coordinate
effects.
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
import torch
from scipy import stats


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from model.r114_split_profile_model import build_split_profile_model  # noqa: E402
from training.dataset import R114Dataset  # noqa: E402
from training.split_profile_targets import build_split_profile_targets  # noqa: E402
from torch.utils.data import DataLoader  # noqa: E402


DEFAULT_RUN = ROOT / "runs" / "r114b_split_profile_probe_scratch_20260830"
DEFAULT_CHECKPOINT = DEFAULT_RUN / "weights" / "epoch_024.pth"
DEFAULT_OUTPUT = ROOT / "results" / "split_profile_probe" / "E024_failure_diagnosis"


def atomic_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, allow_nan=False),
        encoding="utf-8",
    )
    temporary.replace(path)


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def finite_float(value: float | np.floating[Any]) -> float | None:
    result = float(value)
    return result if math.isfinite(result) else None


def weighted_mean(value: torch.Tensor, weight: torch.Tensor) -> torch.Tensor:
    numerator = (value * weight).flatten(1).sum(1)
    denominator = weight.flatten(1).sum(1).clamp_min(1.0e-8)
    return numerator / denominator


def scene_mean(value: torch.Tensor) -> torch.Tensor:
    return value.flatten(1).mean(1)


def smooth_band(sdf_px: torch.Tensor, inner: float = 10.0, outer: float = 14.0) -> torch.Tensor:
    phase = ((outer - sdf_px.abs()) / (outer - inner)).clamp(0.0, 1.0)
    return phase.square() * (3.0 - 2.0 * phase)


def proposal(
    cue: torch.Tensor,
    midpoint_offset: torch.Tensor,
    contrast: torch.Tensor,
    sdf_px: torch.Tensor,
    width: torch.Tensor,
) -> torch.Tensor:
    midpoint = (cue + midpoint_offset).clamp(0.0, 1.0)
    return (
        midpoint + 0.5 * contrast * torch.tanh(sdf_px / width.clamp(0.8, 3.5))
    ).clamp(0.0, 1.0)


def apply_bounded(
    base: torch.Tensor,
    proposed: torch.Tensor,
    gate: torch.Tensor,
    maximum_gray: float = 48.0,
) -> tuple[torch.Tensor, torch.Tensor]:
    delta = gate * (proposed - base).clamp(-maximum_gray / 255.0, maximum_gray / 255.0)
    return (base + delta).clamp(0.0, 1.0), delta


class Reservoir:
    """Deterministic bounded sample for correlations without retaining all pixels."""

    def __init__(self, maximum: int, seed: int):
        self.maximum = int(maximum)
        self.rng = np.random.default_rng(seed)
        self.values: list[np.ndarray] = []
        self.count = 0

    def add(self, columns: Iterable[torch.Tensor], mask: torch.Tensor) -> None:
        arrays = [item.detach()[mask].float().cpu().numpy().reshape(-1) for item in columns]
        if not arrays or arrays[0].size == 0:
            return
        matrix = np.stack(arrays, axis=1)
        self.count += int(matrix.shape[0])
        self.values.append(matrix)
        current = np.concatenate(self.values, axis=0)
        if current.shape[0] > self.maximum:
            keep = self.rng.choice(current.shape[0], self.maximum, replace=False)
            current = current[keep]
        self.values = [current]

    def array(self) -> np.ndarray:
        if not self.values:
            return np.empty((0, 0), np.float32)
        return self.values[0]


def correlations(x: np.ndarray, y: np.ndarray) -> dict[str, float | None]:
    finite = np.isfinite(x) & np.isfinite(y)
    x, y = x[finite], y[finite]
    if x.size < 3 or float(np.std(x)) < 1.0e-12 or float(np.std(y)) < 1.0e-12:
        return {"count": int(x.size), "pearson": None, "spearman": None, "slope": None, "intercept": None}
    pearson = stats.pearsonr(x, y).statistic
    spearman = stats.spearmanr(x, y).statistic
    slope, intercept = np.polyfit(x, y, 1)
    result = {
        "count": int(x.size),
        "pearson": finite_float(pearson),
        "spearman": finite_float(spearman),
        "slope_prediction_from_target": finite_float(slope),
        "intercept_prediction_from_target": finite_float(intercept),
    }
    if float(np.min(x)) >= -1.0e-8 and float(np.max(x)) <= 1.0 + 1.0e-8:
        low = x <= 0.05
        high = x >= 0.50
        result["prediction_mean_when_target_le_0_05"] = (
            finite_float(y[low].mean()) if bool(low.any()) else None
        )
        result["prediction_mean_when_target_ge_0_50"] = (
            finite_float(y[high].mean()) if bool(high.any()) else None
        )
        result["fraction_prediction_ge_0_50_when_target_le_0_05"] = (
            finite_float((y[low] >= 0.50).mean()) if bool(low.any()) else None
        )
    return result


def aggregate(rows: list[dict[str, Any]], key: str) -> dict[str, dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[str(row[key])].append(row)
    result: dict[str, dict[str, Any]] = {}
    excluded = {"record_id", "family", "role", "challenge"}
    for name, items in sorted(grouped.items()):
        fields = sorted(set().union(*(item.keys() for item in items)) - excluded)
        summary: dict[str, Any] = {"scenes": len(items)}
        for field in fields:
            values = np.asarray([item[field] for item in items if item.get(field) is not None], np.float64)
            if values.size:
                summary[field + "_mean"] = finite_float(values.mean())
                summary[field + "_median"] = finite_float(np.median(values))
                summary[field + "_p10"] = finite_float(np.quantile(values, 0.10))
                summary[field + "_p90"] = finite_float(np.quantile(values, 0.90))
        result[name] = summary
    return result


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = sorted(set().union(*(row.keys() for row in rows))) if rows else []
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


@torch.no_grad()
def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--checkpoint", type=Path, default=DEFAULT_CHECKPOINT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--device", default="cuda" if torch.cuda.is_available() else "cpu")
    parser.add_argument("--batch-size", type=int, default=4)
    parser.add_argument("--workers", type=int, default=0)
    parser.add_argument("--pixel-sample", type=int, default=350_000)
    parser.add_argument("--validation-limit", type=int, default=128)
    args = parser.parse_args()

    checkpoint_path = args.checkpoint.resolve()
    output_dir = args.output.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    device = torch.device(args.device)

    payload = torch.load(checkpoint_path, map_location="cpu", weights_only=False)
    if int(payload.get("epoch", -1)) != 24:
        raise RuntimeError(f"expected E024 checkpoint, got epoch={payload.get('epoch')}")
    model = build_split_profile_model(compact=False).to(device)
    model.load_state_dict(payload["model"], strict=True)
    model.eval()

    # The trainer interprets --validation-limit 0 as a stratified limit of 128,
    # so this reconstructs the exact E024 validation population and ordering.
    dataset = R114Dataset("validation", epoch=0, limit=args.validation_limit)
    loader = DataLoader(
        dataset,
        batch_size=args.batch_size,
        shuffle=False,
        num_workers=args.workers,
        pin_memory=(device.type == "cuda"),
    )

    midpoint_sample = Reservoir(args.pixel_sample, 2401)
    contrast_sample = Reservoir(args.pixel_sample, 2402)
    width_sample = Reservoir(args.pixel_sample, 2403)
    visibility_sample = Reservoir(args.pixel_sample, 2404)
    sdf_sample = Reservoir(args.pixel_sample, 2405)
    scene_rows: list[dict[str, Any]] = []

    totals: dict[str, float] = defaultdict(float)
    total_scenes = 0
    for batch_index, cpu_batch in enumerate(loader, start=1):
        batch = {
            key: value.to(device, non_blocking=True) if isinstance(value, torch.Tensor) else value
            for key, value in cpu_batch.items()
        }
        source = batch["source"].float()
        target = batch["target"].float()
        details = model.forward_details(source)
        targets = build_split_profile_targets(
            source,
            target,
            batch["sdf"].float(),
            batch["identity"],
            batch["flat"],
            base_output=details.base_output.detach(),
            midpoint_source=details.shifted_base.detach(),
            midpoint_cue_window_px=model.config.local_range_window_px,
        )

        base = details.base_output
        actual = details.output
        actual_delta = details.profile_delta
        desired = target - base
        base_error = (base - target).abs()
        actual_error = (actual - target).abs()
        actual_gain = base_error - actual_error
        action_mask = (actual_delta.abs() * 255.0 >= 0.10) & (desired.abs() * 255.0 >= 0.10)
        action_weight = actual_delta.abs() * action_mask.to(actual_delta.dtype)
        truth_band = targets.boundary_band
        band_mask = truth_band >= 0.05

        oracle_delta = torch.sign(desired) * torch.minimum(actual_delta.abs(), desired.abs())
        oracle_output = (base + oracle_delta).clamp(0.0, 1.0)
        oracle_gain = base_error - (oracle_output - target).abs()
        same_magnitude_delta = torch.sign(desired) * actual_delta.abs()
        same_magnitude_output = (base + same_magnitude_delta).clamp(0.0, 1.0)
        same_magnitude_gain = base_error - (same_magnitude_output - target).abs()

        controller_factor = (
            details.boundary_confidence * details.correction_need * details.recoverability
        )
        predicted_sdf = details.predicted_sdf_px
        true_sdf = targets.sdf
        current_gate = details.profile_gate
        current_proposal = proposal(
            details.profile_midpoint_cue,
            details.midpoint_offset,
            details.signed_plateau_contrast,
            predicted_sdf,
            details.profile_width,
        )
        base_midpoint_cue = model._profile_midpoint_cue(base)
        source_midpoint_cue = model._profile_midpoint_cue(source)
        base_cue_proposal = proposal(
            base_midpoint_cue,
            details.midpoint_offset,
            details.signed_plateau_contrast,
            predicted_sdf,
            details.profile_width,
        )
        source_cue_proposal = proposal(
            source_midpoint_cue,
            details.midpoint_offset,
            details.signed_plateau_contrast,
            predicted_sdf,
            details.profile_width,
        )
        true_sdf_proposal = proposal(
            details.profile_midpoint_cue,
            details.midpoint_offset,
            details.signed_plateau_contrast,
            true_sdf,
            details.profile_width,
        )
        flipped_proposal = proposal(
            details.profile_midpoint_cue,
            details.midpoint_offset,
            -details.signed_plateau_contrast,
            predicted_sdf,
            details.profile_width,
        )
        target_param_pred_sdf = proposal(
            targets.raw_midpoint_cue,
            targets.midpoint_offset,
            targets.signed_plateau_contrast,
            predicted_sdf,
            targets.profile_width,
        )
        target_param_true_sdf = proposal(
            targets.raw_midpoint_cue,
            targets.midpoint_offset,
            targets.signed_plateau_contrast,
            true_sdf,
            targets.profile_width,
        )
        true_band = smooth_band(true_sdf)
        current_visibility_true_band_gate = (
            controller_factor * details.profile_visibility * true_band
        )
        target_visibility_gate = controller_factor * targets.profile_visibility * details.profile_band
        target_visibility_true_band_gate = controller_factor * targets.profile_visibility * true_band
        target_profile_all_controller_gate = (
            controller_factor * targets.profile_visibility * true_band
        )
        target_profile_without_recoverability_gate = (
            details.boundary_confidence
            * details.correction_need
            * targets.profile_visibility
            * true_band
        )
        target_profile_boundary_only_gate = (
            details.boundary_confidence * targets.profile_visibility * true_band
        )
        oracle_controller_gate = targets.profile_visibility * true_band

        variants: dict[str, tuple[torch.Tensor, torch.Tensor]] = {
            "actual": (actual, actual_delta),
            "learned_params_true_sdf": apply_bounded(base, true_sdf_proposal, current_gate),
            "learned_params_true_sdf_true_band": apply_bounded(
                base, true_sdf_proposal, current_visibility_true_band_gate
            ),
            "learned_params_base_midpoint_cue": apply_bounded(base, base_cue_proposal, current_gate),
            "learned_params_source_midpoint_cue": apply_bounded(base, source_cue_proposal, current_gate),
            "flipped_contrast": apply_bounded(base, flipped_proposal, current_gate),
            "target_params_pred_sdf": apply_bounded(base, target_param_pred_sdf, current_gate),
            "target_params_true_sdf": apply_bounded(base, target_param_true_sdf, current_gate),
            "target_visibility_pred_sdf": apply_bounded(base, current_proposal, target_visibility_gate),
            "target_visibility_true_band": apply_bounded(base, true_sdf_proposal, target_visibility_true_band_gate),
            "target_params_all_controller": apply_bounded(
                base, target_param_true_sdf, target_profile_all_controller_gate
            ),
            "target_params_without_recoverability": apply_bounded(
                base, target_param_true_sdf, target_profile_without_recoverability_gate
            ),
            "target_params_boundary_only": apply_bounded(
                base, target_param_true_sdf, target_profile_boundary_only_gate
            ),
            "target_params_oracle_gate": apply_bounded(base, target_param_true_sdf, oracle_controller_gate),
        }

        batch_count = int(source.shape[0])
        total_scenes += batch_count
        total_scenes_tensor = torch.ones(batch_count, device=device)
        measurements: dict[str, torch.Tensor] = {
            "base_mae": scene_mean(base_error),
            "output_mae": scene_mean(actual_error),
            "profile_gain_global": scene_mean(actual_gain),
            "profile_gain_band": weighted_mean(actual_gain, truth_band),
            "profile_delta_abs_gray_band": 255.0 * weighted_mean(actual_delta.abs(), truth_band),
            "profile_harmful_fraction_band": weighted_mean((actual_gain < 0).float(), truth_band),
            "direction_sign_agreement_action": weighted_mean(
                (torch.sign(actual_delta) == torch.sign(desired)).float(), action_weight
            ),
            "direction_sign_agreement_band": weighted_mean(
                (torch.sign(actual_delta) == torch.sign(desired)).float(), truth_band * action_mask.float()
            ),
            "oracle_same_magnitude_gain_band": weighted_mean(same_magnitude_gain, truth_band),
            "oracle_clipped_gain_band": weighted_mean(oracle_gain, truth_band),
            "directional_headroom_band": weighted_mean(oracle_gain - actual_gain, truth_band),
            "visibility_pred_band": weighted_mean(details.profile_visibility, truth_band),
            "visibility_target_band": weighted_mean(targets.profile_visibility, truth_band),
            "visibility_abs_error_band": weighted_mean(
                (details.profile_visibility - targets.profile_visibility).abs(), truth_band
            ),
            "profile_gate_band": weighted_mean(details.profile_gate, truth_band),
            "controller_factor_band": weighted_mean(controller_factor, truth_band),
            "need_band": weighted_mean(details.correction_need, truth_band),
            "recoverability_band": weighted_mean(details.recoverability, truth_band),
            "boundary_confidence_band": weighted_mean(details.boundary_confidence, truth_band),
            "width_gate_band": weighted_mean(details.width_gate, truth_band),
            "shift_gate_band": weighted_mean(details.shift_gate, truth_band),
            "midpoint_abs_error_gray_band": 255.0 * weighted_mean(
                (details.midpoint_offset - targets.midpoint_offset).abs(), targets.profile_weight
            ),
            "contrast_abs_error_gray_band": 255.0 * weighted_mean(
                (details.signed_plateau_contrast - targets.signed_plateau_contrast).abs(),
                targets.profile_weight,
            ),
            "contrast_sign_agreement_band": weighted_mean(
                (
                    torch.sign(details.signed_plateau_contrast)
                    == torch.sign(targets.signed_plateau_contrast)
                ).float(),
                targets.profile_weight,
            ),
            "profile_width_abs_error_px_band": weighted_mean(
                (details.profile_width - targets.profile_width).abs(), targets.profile_weight
            ),
            "predicted_sdf_sign_agreement_band": weighted_mean(
                (torch.sign(predicted_sdf) == torch.sign(true_sdf)).float(), truth_band
            ),
            "predicted_boundary_offset_abs_px": weighted_mean(predicted_sdf.abs(), targets.boundary_binary),
            "action_pixel_fraction": action_mask.float().flatten(1).mean(1),
        }
        for name, (variant_output, _variant_delta) in variants.items():
            measurements[f"{name}_mae"] = scene_mean((variant_output - target).abs())
            measurements[f"{name}_gain_band"] = weighted_mean(
                base_error - (variant_output - target).abs(), truth_band
            )

        for scene_index in range(batch_count):
            row: dict[str, Any] = {
                "record_id": str(batch["record_id"][scene_index]),
                "family": str(batch["family"][scene_index]),
                "role": str(batch["role"][scene_index]),
                "challenge": str(batch["challenge"][scene_index]),
            }
            for name, values in measurements.items():
                row[name] = finite_float(values[scene_index].detach().cpu())
                if row[name] is not None:
                    totals[name] += float(row[name])
            scene_rows.append(row)

        parameter_mask = (targets.profile_weight > 0.05) & band_mask
        midpoint_sample.add(
            [targets.midpoint_offset, details.midpoint_offset], parameter_mask
        )
        contrast_sample.add(
            [targets.signed_plateau_contrast, details.signed_plateau_contrast], parameter_mask
        )
        width_sample.add(
            [targets.profile_width, details.profile_width], parameter_mask
        )
        visibility_sample.add(
            [targets.profile_visibility, details.profile_visibility], band_mask
        )
        sdf_sample.add([true_sdf, predicted_sdf], band_mask)
        print(f"diagnostic batch {batch_index}/{len(loader)}", flush=True)

    correlation_payload: dict[str, Any] = {}
    for name, reservoir in {
        "midpoint_offset": midpoint_sample,
        "signed_contrast": contrast_sample,
        "profile_width": width_sample,
        "profile_visibility": visibility_sample,
        "signed_sdf_px": sdf_sample,
    }.items():
        array = reservoir.array()
        correlation_payload[name] = correlations(array[:, 0], array[:, 1])
        correlation_payload[name]["eligible_pixel_count"] = reservoir.count

    overall = {name: value / max(total_scenes, 1) for name, value in totals.items()}
    overall["scenes"] = total_scenes
    overall["profile_mae_regression_vs_base"] = overall["output_mae"] - overall["base_mae"]
    overall["profile_mae_regression_pct_vs_base"] = (
        100.0 * overall["profile_mae_regression_vs_base"] / max(overall["base_mae"], 1.0e-12)
    )

    identity_rows = [row for row in scene_rows if row["role"] == "identity"]
    degraded_rows = [row for row in scene_rows if row["role"] != "identity"]
    identity_gate = float(np.mean([row["profile_gate_band"] for row in identity_rows])) if identity_rows else None
    degraded_gate = float(np.mean([row["profile_gate_band"] for row in degraded_rows])) if degraded_rows else None
    evidence = {
        "actual_profile_is_net_harmful": overall["profile_gain_global"] < 0,
        "actual_direction_is_below_chance": overall["direction_sign_agreement_action"] < 0.5,
        "direction_has_material_headroom": overall["directional_headroom_band"] > abs(overall["profile_gain_band"]),
        "true_sdf_improves_over_predicted_sdf": (
            overall["learned_params_true_sdf_mae"] < overall["actual_mae"]
        ),
        "contrast_flip_improves": overall["flipped_contrast_mae"] < overall["actual_mae"],
        "target_parameters_improve": overall["target_params_pred_sdf_mae"] < overall["actual_mae"],
        "target_sdf_and_parameters_improve": overall["target_params_true_sdf_mae"] < overall["actual_mae"],
        "visibility_target_improves": overall["target_visibility_pred_sdf_mae"] < overall["actual_mae"],
        "identity_gate_below_degraded": (
            identity_gate is not None and degraded_gate is not None and identity_gate < degraded_gate
        ),
    }
    root_cause_ranking = [
        {
            "rank": 1,
            "cause": "profile heads do not learn the oracle parameters because the profile optimizer freezes their renderer backbone",
            "evidence": {
                "profile_optimizer_includes_renderer_backbone": False,
                "midpoint_spearman": correlation_payload["midpoint_offset"]["spearman"],
                "contrast_spearman": correlation_payload["signed_contrast"]["spearman"],
                "contrast_slope": correlation_payload["signed_contrast"]["slope_prediction_from_target"],
                "width_spearman": correlation_payload["profile_width"]["spearman"],
                "target_parameters_mae": overall["target_params_pred_sdf_mae"],
                "learned_parameters_mae": overall["actual_mae"],
            },
        },
        {
            "rank": 2,
            "cause": "training uses true SDF coordinates while deployment uses an inaccurate predicted SDF",
            "evidence": {
                "sdf_spearman": correlation_payload["signed_sdf_px"]["spearman"],
                "sdf_sign_agreement_band": overall["predicted_sdf_sign_agreement_band"],
                "predicted_boundary_offset_abs_px": overall["predicted_boundary_offset_abs_px"],
                "target_parameters_predicted_sdf_mae": overall["target_params_pred_sdf_mae"],
                "target_parameters_true_sdf_mae": overall["target_params_true_sdf_mae"],
            },
        },
        {
            "rank": 3,
            "cause": "visibility head is over-open and is not calibrated to the final controller gate",
            "evidence": {
                "predicted_visibility_band": overall["visibility_pred_band"],
                "target_visibility_band": overall["visibility_target_band"],
                "visibility_intercept": correlation_payload["profile_visibility"]["intercept_prediction_from_target"],
                "prediction_when_target_near_zero": correlation_payload["profile_visibility"].get(
                    "prediction_mean_when_target_le_0_05"
                ),
                "target_visibility_variant_mae": overall["target_visibility_pred_sdf_mae"],
                "learned_visibility_mae": overall["actual_mae"],
            },
        },
        {
            "rank": 4,
            "cause": "profile objectives supervise an ungated proposal instead of the deployed final output",
            "evidence": {
                "actual_gain_band": overall["actual_gain_band"],
                "oracle_clipped_gain_band": overall["oracle_clipped_gain_band"],
                "action_direction_agreement": overall["direction_sign_agreement_action"],
                "controller_factor_band": overall["controller_factor_band"],
                "target_parameters_oracle_gate_mae": overall["target_params_oracle_gate_mae"],
                "target_parameters_all_controller_mae": overall["target_params_all_controller_mae"],
                "target_parameters_without_recoverability_mae": overall[
                    "target_params_without_recoverability_mae"
                ],
                "target_parameters_boundary_only_mae": overall[
                    "target_params_boundary_only_mae"
                ],
            },
        },
    ]

    diagnosis = {
        "schema_version": 1,
        "read_only_forensics": True,
        "checkpoint": {
            "path": str(checkpoint_path),
            "sha256": file_sha256(checkpoint_path),
            "epoch": int(payload["epoch"]),
            "stage": str(payload["stage"]),
            "scratch": bool(payload["scratch"]),
        },
        "validation_contract": {
            "split": "validation",
            "dataset_epoch": 0,
            "schedule_batch_size": 12,
            "rebatched_for_audit": args.batch_size,
            "scenes": total_scenes,
            "expected_training_validation_scenes": args.validation_limit,
        },
        "overall": overall,
        "correlations": correlation_payload,
        "by_role": aggregate(scene_rows, "role"),
        "by_challenge": aggregate(scene_rows, "challenge"),
        "by_family": aggregate(scene_rows, "family"),
        "evidence_tests": evidence,
        "root_cause_ranking": root_cause_ranking,
        "implementation_mismatch_hypotheses": {
            "profile_optimizer_freezes_renderer_backbone_even_though_model_profile_parameters_includes_it": True,
            "training_profile_uses_true_sdf_but_runtime_uses_predicted_sdf": True,
            "profile_render_loss_scores_ungated_analytic_proposal_not_final_output": True,
            "profile_guards_use_source_relative_delta_not_runtime_base_relative_delta": True,
            "visibility_target_is_not_calibrated_to_controller_factor": True,
        },
    }

    write_csv(output_dir / "scene_metrics.csv", scene_rows)
    atomic_json(output_dir / "diagnosis.json", diagnosis)
    print(json.dumps({"overall": overall, "correlations": correlation_payload, "evidence_tests": evidence}, indent=2))


if __name__ == "__main__":
    main()

"""Independent gate for the R114B width/shift reliability probe."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

import numpy as np
from scipy.stats import spearmanr
import torch
from sklearn.metrics import roc_auc_score
from torch.utils.data import DataLoader


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from model.r114_split_profile_model import build_split_profile_model
from training.dataset import R114Dataset
from training.split_profile_targets import build_split_profile_targets
from training.targets import build_spatial_targets


def safe_spearman(target: np.ndarray, prediction: np.ndarray) -> float | None:
    if target.size < 8 or target.std() < 1e-8 or prediction.std() < 1e-8:
        return None
    value = spearmanr(target, prediction).statistic
    return float(value) if np.isfinite(value) else None


def safe_auc(target: np.ndarray, prediction: np.ndarray) -> float | None:
    keep = (target <= 0.15) | (target >= 0.40)
    truth = (target[keep] >= 0.40).astype(np.uint8)
    if truth.size < 8 or np.unique(truth).size < 2:
        return None
    return float(roc_auc_score(truth, prediction[keep]))


def load(run_dir: Path, device: torch.device):
    checkpoints = sorted((run_dir / "weights").glob("epoch_*.pth"))
    if not checkpoints:
        raise RuntimeError("missing reliability checkpoint")
    payload = torch.load(checkpoints[-1], map_location="cpu")
    if not payload.get("scratch") or payload.get("foreign_checkpoint_loaded"):
        raise RuntimeError("checkpoint violates scratch contract")
    model = build_split_profile_model()
    model.load_state_dict(payload["model"], strict=True)
    return model.to(device).eval(), checkpoints[-1], payload


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", required=True)
    args = parser.parse_args()
    run_dir = Path(args.run_dir).resolve()
    state = json.loads((run_dir / "run_state.json").read_text(encoding="utf-8"))
    if state.get("status") != "complete" or state.get("campaign") != "reliability_probe":
        raise RuntimeError("reliability probe is not complete")
    device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")
    model, checkpoint, payload = load(run_dir, device)
    dataset = R114Dataset("validation", epoch=0)
    loader = DataLoader(dataset, batch_size=4, shuffle=False, num_workers=2, pin_memory=True)
    rows = []
    point_targets = {"width": [], "shift": []}
    point_predictions = {"width": [], "shift": []}
    with torch.inference_mode():
        for batch in loader:
            values = {key: value.to(device, non_blocking=True) if isinstance(value, torch.Tensor) else value for key, value in batch.items()}
            predicted = model.controller(values["source"])
            target = build_split_profile_targets(
                values["source"], values["target"], values["sdf"], values["identity"], values["flat"]
            )
            base = build_spatial_targets(
                values["source"], values["target"], values["mask"], values["sdf"], values["identity"], values["flat"]
            )
            for index in range(values["source"].shape[0]):
                support = (target.boundary_band[index, 0] > 0.5).cpu().numpy()
                width_target = target.width_reliability[index, 0].cpu().numpy()[support]
                shift_target = target.shift_reliability[index, 0].cpu().numpy()[support]
                width_pred = predicted.width_reliability[index, 0].cpu().numpy()[support]
                shift_pred = predicted.shift_reliability[index, 0].cpu().numpy()[support]
                if width_target.size > 2000:
                    take = np.linspace(0, width_target.size - 1, 2000).round().astype(int)
                    width_target, shift_target = width_target[take], shift_target[take]
                    width_pred, shift_pred = width_pred[take], shift_pred[take]
                point_targets["width"].append(width_target)
                point_targets["shift"].append(shift_target)
                point_predictions["width"].append(width_pred)
                point_predictions["shift"].append(shift_pred)
                boundary = base.boundary[index:index + 1]
                denominator = boundary.sum().clamp_min(1e-6)
                weighted_need = float((predicted.correction_need[index:index + 1] * boundary).sum().cpu() / denominator.cpu())
                rows.append({
                    "record_id": batch["record_id"][index],
                    "family": batch["family"][index],
                    "role": batch["role"][index],
                    "challenge": batch["challenge"][index],
                    "width_target_mean": float(width_target.mean()) if width_target.size else 0.0,
                    "width_predicted_mean": float(width_pred.mean()) if width_pred.size else 0.0,
                    "width_spearman": safe_spearman(width_target, width_pred),
                    "width_auc": safe_auc(width_target, width_pred),
                    "shift_target_mean": float(shift_target.mean()) if shift_target.size else 0.0,
                    "shift_predicted_mean": float(shift_pred.mean()) if shift_pred.size else 0.0,
                    "shift_spearman": safe_spearman(shift_target, shift_pred),
                    "shift_auc": safe_auc(shift_target, shift_pred),
                    "need_boundary_mean": weighted_need,
                    "boundary_std": float(predicted.boundary_confidence[index].std().cpu()),
                })

    aggregate = {}
    for name in ("width", "shift"):
        truth = np.concatenate(point_targets[name])
        pred = np.concatenate(point_predictions[name])
        aggregate[name] = {
            "point_spearman": safe_spearman(truth, pred),
            "point_auc": safe_auc(truth, pred),
            "calibration_mae": float(np.mean(np.abs(truth - pred))),
            "prediction_std": float(pred.std()),
            "target_std": float(truth.std()),
            "points": int(truth.size),
        }
    families = {}
    for family in sorted({row["family"] for row in rows}):
        subset = [row for row in rows if row["family"] == family]
        families[family] = {
            key: float(np.median([row[key] for row in subset if row[key] is not None]))
            for key in (
                "width_target_mean", "width_predicted_mean", "shift_target_mean",
                "shift_predicted_mean", "need_boundary_mean", "boundary_std",
            )
        }
    roles = {}
    for role in sorted({row["role"] for row in rows}):
        subset = [row for row in rows if row["role"] == role]
        roles[role] = {
            "count": len(subset),
            "width_predicted_mean": float(np.mean([row["width_predicted_mean"] for row in subset])),
            "shift_predicted_mean": float(np.mean([row["shift_predicted_mean"] for row in subset])),
            "need_boundary_mean": float(np.mean([row["need_boundary_mean"] for row in subset])),
        }
    challenges = {}
    for challenge in sorted({row["challenge"] for row in rows}):
        subset = [row for row in rows if row["challenge"] == challenge]
        challenges[challenge] = {
            key: float(np.median([row[key] for row in subset if row[key] is not None]))
            for key in (
                "width_target_mean", "width_predicted_mean", "shift_target_mean",
                "shift_predicted_mean", "need_boundary_mean", "boundary_std",
            )
        }

    # One explicit input-sensitivity audit prevents a second constant-head pass.
    sample = dataset[0]["source"].unsqueeze(0).to(device).requires_grad_(True)
    output = model.controller(sample)
    gradients = {}
    for position, (name, tensor) in enumerate({
        "width_reliability": output.width_reliability,
        "shift_reliability": output.shift_reliability,
    }.items()):
        spatial = torch.linspace(0.5, 1.5, tensor.numel(), device=device).reshape_as(tensor)
        gradient = torch.autograd.grad((tensor * spatial).mean(), sample, retain_graph=position == 0)[0]
        gradients[name] = float(gradient.abs().sum().detach().cpu())

    low = challenges.get("low_contrast", {})
    uneven = challenges.get("uneven_illumination", {})
    evidence = {
        "width_spatially_alive": aggregate["width"]["prediction_std"] > 0.02 and gradients["width_reliability"] > 1e-8,
        "shift_spatially_alive": aggregate["shift"]["prediction_std"] > 0.02 and gradients["shift_reliability"] > 1e-8,
        "width_tracks_oracle": (aggregate["width"]["point_spearman"] or 0.0) > 0.30 and (aggregate["width"]["point_auc"] or 0.0) > 0.70,
        "shift_tracks_oracle": (aggregate["shift"]["point_spearman"] or 0.0) > 0.30 and (aggregate["shift"]["point_auc"] or 0.0) > 0.75,
        "low_contrast_shift_below_uneven": bool(low and uneven and low["shift_predicted_mean"] < uneven["shift_predicted_mean"]),
        "flat_is_safely_low": roles.get("flat_negative", {}).get("shift_predicted_mean", 1.0) < 0.15,
    }
    decision = "advance_to_split_profile_probe" if sum(evidence.values()) >= 5 and evidence["shift_tracks_oracle"] else "stop_and_repair_reliability"
    result = {
        "status": "complete",
        "decision": decision,
        "evidence_bundle": evidence,
        "aggregate": aggregate,
        "families": families,
        "challenges": challenges,
        "roles": roles,
        "input_gradient_abs_sum": gradients,
        "checkpoint": str(checkpoint),
        "checkpoint_epoch": int(payload["epoch"]),
        "scratch_verified": True,
    }
    output_path = run_dir / "reliability_probe_decision.json"
    output_path.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if decision == "advance_to_split_profile_probe" else 2


if __name__ == "__main__":
    raise SystemExit(main())

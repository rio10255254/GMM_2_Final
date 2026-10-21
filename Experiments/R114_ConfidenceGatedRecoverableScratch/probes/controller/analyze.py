"""Evidence-bundle decision for the R114 controller viability probe."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

import numpy as np
import torch


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from model.r114_model import build_model
from training.dataset import R114Dataset


def load_model(checkpoint: Path, device: torch.device):
    payload = torch.load(checkpoint, map_location="cpu")
    if not payload.get("scratch") or payload.get("foreign_checkpoint_loaded"):
        raise RuntimeError("controller probe checkpoint violates scratch contract")
    model = build_model()
    model.load_state_dict(payload["model"], strict=True)
    return model.to(device).eval(), payload


def tensor_sample(dataset: R114Dataset, index: int, device: torch.device) -> torch.Tensor:
    return dataset[index]["source"].unsqueeze(0).to(device)


def stability(model, device: torch.device, limit: int = 24) -> dict:
    datasets = [R114Dataset("validation", epoch=epoch, limit=limit) for epoch in (1, 2, 3)]
    correlations = []
    need_ranges = []
    with torch.inference_mode():
        for index in range(min(limit, *(len(dataset) for dataset in datasets))):
            maps = [model(tensor_sample(dataset, index, device)) for dataset in datasets]
            boundaries = [item.boundary_confidence[0, 0].float().cpu().numpy().reshape(-1) for item in maps]
            for first, second in ((0, 1), (0, 2), (1, 2)):
                if boundaries[first].std() > 1e-8 and boundaries[second].std() > 1e-8:
                    correlations.append(float(np.corrcoef(boundaries[first], boundaries[second])[0, 1]))
            needs = [float(item.correction_need.mean().cpu()) for item in maps]
            need_ranges.append(max(needs) - min(needs))
    return {
        "boundary_cross_degradation_correlation_median": float(np.median(correlations)) if correlations else 0.0,
        "need_cross_degradation_range_median": float(np.median(need_ranges)) if need_ranges else 0.0,
        "records": min(limit, len(datasets[0])),
    }


def input_gradients(model, device: torch.device) -> dict:
    value = tensor_sample(R114Dataset("validation", epoch=2, limit=1), 0, device).requires_grad_(True)
    output = model(value)
    results = {}
    maps = {
        "boundary": output.boundary_confidence,
        "need": output.correction_need,
        "recoverability": output.recoverability,
        "sdf": output.normalized_sdf,
    }
    for position, (name, tensor) in enumerate(maps.items()):
        weight = torch.linspace(0.5, 1.5, tensor.numel(), device=device).reshape_as(tensor)
        gradient = torch.autograd.grad((tensor * weight).mean(), value, retain_graph=position < len(maps) - 1)[0]
        results[f"{name}_input_gradient_abs_sum"] = float(gradient.abs().sum().detach().cpu())
    return results


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", required=True)
    args = parser.parse_args()
    run_dir = Path(args.run_dir).resolve()
    state = json.loads((run_dir / "run_state.json").read_text(encoding="utf-8"))
    if state.get("status") != "complete" or state.get("campaign") != "controller_probe":
        raise RuntimeError("controller probe is not complete")
    checkpoints = sorted((run_dir / "weights").glob("epoch_*.pth"))
    if not checkpoints:
        raise RuntimeError("missing controller checkpoint")
    validation_path = run_dir / "validation" / f"epoch_{int(state['epochs_completed']):03d}.json"
    validation = json.loads(validation_path.read_text(encoding="utf-8"))
    summary = validation["summary"]
    device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")
    model, checkpoint = load_model(checkpoints[-1], device)
    stable = stability(model, device)
    gradients = input_gradients(model, device)

    roles = summary["roles"]
    degraded_counts = sum(roles.get(name, {}).get("count", 0) for name in ("edge", "textured_edge"))
    degraded_need = sum(roles.get(name, {}).get("need_mean", 0) * roles.get(name, {}).get("count", 0) for name in ("edge", "textured_edge")) / max(degraded_counts, 1)
    identity_need = roles.get("identity", {}).get("need_mean", 1.0)
    flat_need = roles.get("flat_negative", {}).get("need_mean", 1.0)
    diagnosis_path = run_dir / "controller_target_diagnosis.json"
    diagnosis = json.loads(diagnosis_path.read_text(encoding="utf-8")) if diagnosis_path.is_file() else None
    if diagnosis:
        role_diagnosis = diagnosis["roles"]
        degraded_counts = sum(role_diagnosis.get(name, {}).get("count", 0) for name in ("edge", "textured_edge"))
        degraded_need = sum(
            role_diagnosis.get(name, {}).get("predicted_need_boundary_mean", 0) * role_diagnosis.get(name, {}).get("count", 0)
            for name in ("edge", "textured_edge")
        ) / max(degraded_counts, 1)
        identity_need = role_diagnosis.get("identity", {}).get("predicted_need_boundary_mean", 1.0)
        flat_need = role_diagnosis.get("flat_negative", {}).get("predicted_need_boundary_mean", 1.0)
    valid_non_dense_auc = [
        value["boundary_auc_median"]
        for name, value in summary["families"].items()
        if name not in {"dense_array", "flat_negative"} and value["boundary_auc_median"] is not None
    ]
    dense_gate_ratio = None
    if diagnosis:
        dense_gate = diagnosis["diagnosis"].get("dense_predicted_geometry_gate")
        normal_gate = diagnosis["diagnosis"].get("non_dense_predicted_geometry_gate_median")
        if dense_gate is not None and normal_gate:
            dense_gate_ratio = dense_gate / normal_gate

    evidence = {
        "boundary_not_constant": summary["boundary_std_median"] > 0.01 and summary["boundary_on_minus_off_median"] > 0.03,
        "boundary_cross_family": summary["boundary_auc_median"] > 0.72 and min(valid_non_dense_auc, default=0) > 0.75,
        "dense_unrecoverable_is_safely_gated": dense_gate_ratio is not None and dense_gate_ratio < 0.40,
        "need_separates_safe_inputs": degraded_need > identity_need * 3.0 and degraded_need > max(flat_need, 1.0e-4) * 3.0,
        "cross_degradation_stability": stable["boundary_cross_degradation_correlation_median"] > 0.60,
        "all_control_maps_input_sensitive": min(gradients.values()) > 1.0e-8,
    }
    degeneracy = {
        "r109_like_auc": summary["boundary_auc_median"] <= 0.58,
        "near_constant_boundary": summary["boundary_std_median"] <= 0.002,
        "wrong_boundary_direction": summary["boundary_on_minus_off_median"] <= 0,
        "dead_input_gradient": min(gradients.values()) <= 1.0e-10,
    }
    passed_count = sum(evidence.values())
    decision = "advance_to_geometry_probe" if not any(degeneracy.values()) and passed_count >= 5 else "stop_and_repair_controller"
    result = {
        "status": "complete",
        "decision": decision,
        "evidence_bundle": evidence,
        "degeneracy_checks": degeneracy,
        "passed_evidence_count": passed_count,
        "reference": {"r109_boundary_auc": 0.4962, "fixed_local_cue_linear_probe_auc": 0.8699},
        "metrics": {
            "boundary_auc_median": summary["boundary_auc_median"],
            "boundary_auc_worst_family": summary["boundary_auc_worst_family"],
            "boundary_auc_worst_recoverable_family": min(valid_non_dense_auc, default=0),
            "boundary_std_median": summary["boundary_std_median"],
            "boundary_on_minus_off_median": summary["boundary_on_minus_off_median"],
            "degraded_need_mean": degraded_need,
            "identity_need_mean": identity_need,
            "flat_need_mean": flat_need,
            "dense_to_non_dense_geometry_gate_ratio": dense_gate_ratio,
            **stable,
            **gradients,
        },
        "checkpoint": str(checkpoints[-1]),
        "checkpoint_epoch": int(checkpoint["epoch"]),
        "scratch_verified": bool(checkpoint.get("scratch")) and not bool(checkpoint.get("foreign_checkpoint_loaded")),
    }
    output = run_dir / "controller_probe_decision.json"
    output.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if decision == "advance_to_geometry_probe" else 2


if __name__ == "__main__":
    raise SystemExit(main())

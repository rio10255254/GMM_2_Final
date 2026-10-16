"""Diagnose dense-boundary and need/recoverability supervision after Probe 1."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

import numpy as np
import torch
from sklearn.metrics import roc_auc_score
from torch.utils.data import DataLoader


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from model.r114_model import build_model
from training.dataset import R114Dataset
from training.targets import build_spatial_targets, finite_differences


def safe_auc(truth: np.ndarray, score: np.ndarray) -> float | None:
    if np.unique(truth).size < 2:
        return None
    stride = max(1, truth.size // 20000)
    return float(roc_auc_score(truth.reshape(-1)[::stride], score.reshape(-1)[::stride]))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", required=True)
    args = parser.parse_args()
    run_dir = Path(args.run_dir).resolve()
    checkpoint = sorted((run_dir / "weights").glob("epoch_*.pth"))[-1]
    payload = torch.load(checkpoint, map_location="cpu")
    model = build_model()
    model.load_state_dict(payload["model"], strict=True)
    device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")
    model = model.to(device).eval()
    dataset = R114Dataset("validation", epoch=0)
    loader = DataLoader(dataset, batch_size=12, shuffle=False, num_workers=2, pin_memory=True)
    rows = []
    with torch.inference_mode():
        for batch in loader:
            tensors = {key: value.to(device, non_blocking=True) if isinstance(value, torch.Tensor) else value for key, value in batch.items()}
            targets = build_spatial_targets(
                tensors["source"], tensors["target"], tensors["mask"], tensors["sdf"],
                tensors["identity"], tensors["flat"],
            )
            output = model(tensors["source"])
            gx, gy = finite_differences(tensors["source"])
            raw_edge = torch.sqrt(gx.square() + gy.square() + 1e-8)
            boundary_density = torch.nn.functional.avg_pool2d(targets.boundary_binary, 21, stride=1, padding=10)
            for index in range(tensors["source"].shape[0]):
                boundary = targets.boundary_binary[index, 0].cpu().numpy().astype(np.uint8)
                soft_boundary = targets.boundary[index:index + 1]
                weight_sum = soft_boundary.sum().clamp_min(1e-6)
                def weighted(value):
                    return float((value[index:index + 1] * soft_boundary).sum().cpu() / weight_sum.cpu())
                rows.append({
                    "record_id": batch["record_id"][index],
                    "family": batch["family"][index],
                    "role": batch["role"][index],
                    "challenge": batch["challenge"][index],
                    "boundary_fraction": float(boundary.mean()),
                    "raw_edge_auc": safe_auc(boundary, raw_edge[index, 0].cpu().numpy()),
                    "target_need_boundary_mean": weighted(targets.need),
                    "predicted_need_boundary_mean": weighted(output.correction_need),
                    "target_recoverability_boundary_mean": weighted(targets.recoverability),
                    "predicted_recoverability_boundary_mean": weighted(output.recoverability),
                    "target_boundary_confidence_boundary_mean": weighted(targets.boundary_confidence),
                    "predicted_boundary_confidence_boundary_mean": weighted(output.boundary_confidence),
                    "predicted_geometry_gate_boundary_mean": weighted(output.geometry_gate),
                    "boundary_density_mean": weighted(boundary_density),
                    "predicted_boundary_auc": safe_auc(boundary, output.boundary_confidence[index, 0].cpu().numpy()),
                })
    families = {}
    for family in sorted({row["family"] for row in rows}):
        subset = [row for row in rows if row["family"] == family]
        fields = [key for key in rows[0] if key not in {"record_id", "family", "role", "challenge"}]
        families[family] = {
            "count": len(subset),
            **{
                key + "_median": float(np.median([row[key] for row in subset if row[key] is not None]))
                if any(row[key] is not None for row in subset) else None
                for key in fields
            },
        }
    roles = {}
    for role in sorted({row["role"] for row in rows}):
        subset = [row for row in rows if row["role"] == role]
        roles[role] = {
            "count": len(subset),
            "target_need_boundary_mean": float(np.mean([row["target_need_boundary_mean"] for row in subset])),
            "predicted_need_boundary_mean": float(np.mean([row["predicted_need_boundary_mean"] for row in subset])),
        }
    dense = families.get("dense_array", {})
    non_dense = [value for name, value in families.items() if name not in {"dense_array", "flat_negative"}]
    result = {
        "status": "complete",
        "records": len(rows),
        "families": families,
        "roles": roles,
        "diagnosis": {
            "dense_raw_edge_detectability": dense.get("raw_edge_auc_median"),
            "dense_predicted_boundary_auc": dense.get("predicted_boundary_auc_median"),
            "dense_target_recoverability": dense.get("target_recoverability_boundary_mean_median"),
            "dense_predicted_recoverability": dense.get("predicted_recoverability_boundary_mean_median"),
            "dense_predicted_boundary_confidence": dense.get("predicted_boundary_confidence_boundary_mean_median"),
            "dense_predicted_geometry_gate": dense.get("predicted_geometry_gate_boundary_mean_median"),
            "non_dense_target_recoverability_median": float(np.median([value["target_recoverability_boundary_mean_median"] for value in non_dense])),
            "non_dense_predicted_boundary_confidence_median": float(np.median([value["predicted_boundary_confidence_boundary_mean_median"] for value in non_dense])),
            "non_dense_predicted_geometry_gate_median": float(np.median([value["predicted_geometry_gate_boundary_mean_median"] for value in non_dense])),
            "dense_boundary_density": dense.get("boundary_density_mean_median"),
            "non_dense_boundary_density_median": float(np.median([value["boundary_density_mean_median"] for value in non_dense])),
            "identity_target_need": roles.get("identity", {}).get("target_need_boundary_mean"),
            "identity_predicted_need": roles.get("identity", {}).get("predicted_need_boundary_mean"),
        },
    }
    output_path = run_dir / "controller_target_diagnosis.json"
    output_path.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(result["diagnosis"], indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

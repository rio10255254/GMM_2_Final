"""Evaluate Raw and frozen model references on the common synthetic bank."""
from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
from pathlib import Path
import sys

import cv2
import numpy as np
import torch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "data"))
sys.path.insert(0, str(ROOT / "validation"))
from sequence_bank import SequenceBank, sha
from sequence_metrics import estimate_position, summarize_sequence
from inference.run import load as load_r118

R118_CHECKPOINT = Path(r"D:/GMM_2_Final/Experiments/R118_PhysicalCoordinateRepairScratch/runs/verified_physical_repair/weights/epoch_012.pth")
R109_CHECKPOINT = Path(r"D:/GMM_2_Final/Experiments/R109_StagedMidpointWidthScratch/weights/selected/R109.pth")
R109_SOURCE = Path(r"D:/GMM_2_Final/Experiments/R109_StagedMidpointWidthScratch/model/r109_model.py")


def load_r109(device):
    spec = importlib.util.spec_from_file_location("r109_reference_model", R109_SOURCE)
    module = importlib.util.module_from_spec(spec); assert spec.loader is not None; spec.loader.exec_module(module)
    saved = torch.load(R109_CHECKPOINT, map_location="cpu", weights_only=False)
    model = module.build_model(); model.load_state_dict(saved["model"], strict=True)
    return model.to(device).eval().requires_grad_(False)


def write_csv(path: Path, rows: list[dict]):
    path.parent.mkdir(parents=True, exist_ok=True)
    keys = list(dict.fromkeys(key for row in rows for key in row))
    with path.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=keys); writer.writeheader(); writer.writerows(rows)


def evaluate(output_root: Path, batch_size: int = 12, device_name: str = "auto") -> dict:
    bank = SequenceBank(ROOT / "data/development_sequences")
    if len(bank) != 4368:
        raise ValueError(f"expected 4368 bank rows, got {len(bank)}")
    device = torch.device("cuda" if device_name == "auto" and torch.cuda.is_available() else device_name if device_name != "auto" else "cpu")
    frozen = {
        "Raw": None,
        "R118_E12": load_r118(R118_CHECKPOINT, str(device)),
        "R109_E48": load_r109(device),
    }
    positions, shape_rows, representatives = [], [], {}
    # Keep only one image per family for the visual panel. Every numeric row is
    # consumed and discarded per batch, avoiding the previous multi-GB buffer.
    for method, model in frozen.items():
        for start in range(0, len(bank.records), batch_size):
            records = bank.records[start:start + batch_size]
            sources, references = [], []
            for row in records:
                source, reference, _mask = bank.load(row)
                sources.append(np.rint(source * 255).astype(np.uint8)); references.append(reference)
            if model is None:
                output_values = [source.astype(np.float32) / 255.0 for source in sources]
            else:
                tensor = torch.from_numpy(np.stack(sources).astype(np.float32) / 255.0)[:, None].to(device)
                with torch.inference_mode():
                    output_values = model(tensor).float().clamp(0, 1).cpu().numpy()[:, 0]
            for row, source, reference, output in zip(records, sources, references, output_values):
                image = source.astype(np.float32) / 255.0 if method == "Raw" else output.astype(np.float32)
                roi = None if row["complete_object_in_roi"] else (20, 20, 236, 236)
                estimate = estimate_position(image, reference, roi)
                positions.append({"method": method, "sequence_id": row["sequence_id"], "scene_id": row["scene_id"], "family": row["family"], "protocol": row["protocol"], "condition_id": row["condition_id"], "frame_index": row["frame_index"], "feature_id": row["scene_id"], "estimator": "fixed_reference_registration_v1", "true_x_px": row["true_x_px"], "true_y_px": row["true_y_px"], "estimated_x_px": estimate.x_px, "estimated_y_px": estimate.y_px, "valid": estimate.valid, "failure_reason": None if estimate.valid else estimate.reason, "source_sha256": row["source_sha256"], "reference_sha256": row["reference_sha256"], "phase_response": estimate.diagnostics.get("phase_response"), "complete_object_in_roi": row["complete_object_in_roi"]})
                difference = image - reference
                gradient_y, gradient_x = np.gradient(difference)
                shape_rows.append({"method": method, "scene_id": row["scene_id"], "sequence_id": row["sequence_id"], "condition_id": row["condition_id"], "frame_index": row["frame_index"], "boundary_distance_proxy_px": float(np.mean(np.abs(difference) > .08)), "image_mae_gray": float(np.mean(np.abs(difference)) * 255), "reference_gradient_error": float(np.mean(np.abs(gradient_x)) + np.mean(np.abs(gradient_y))), "output_min": float(image.min()), "output_max": float(image.max())})
                representatives.setdefault(row["family"], {})[method] = (source, output, np.rint(reference * 255).astype(np.uint8))
            del sources, references, output_values
    summary_rows = []
    groups = {}
    for row in positions:
        groups.setdefault((row["method"], row["sequence_id"], row["protocol"], row["condition_id"]), []).append(row)
    for (method, sequence_id, protocol, condition), rows in groups.items():
        summary = summarize_sequence(rows)
        first = rows[0]
        summary_rows.append({"method": method, "sequence_id": sequence_id, "scene_id": first["scene_id"], "family": first["family"], "protocol": protocol, "condition_id": condition, "estimator": "fixed_reference_registration_v1", **summary})
    step_rows = []
    for (method, sequence_id, protocol, condition), rows in groups.items():
        if protocol not in {"motion_x", "motion_y", "motion_diag"}: continue
        ordered = sorted((r for r in rows if r["valid"]), key=lambda x: x["frame_index"])
        for a, b in zip(ordered, ordered[1:]):
            step_rows.append({"method": method, "sequence_id": sequence_id, "start_frame": a["frame_index"], "end_frame": b["frame_index"], "feature_id": a["feature_id"], "true_dx_px": b["true_x_px"] - a["true_x_px"], "true_dy_px": b["true_y_px"] - a["true_y_px"], "measured_dx_px": None if not (a["valid"] and b["valid"]) else b["estimated_x_px"] - a["estimated_x_px"], "measured_dy_px": None if not (a["valid"] and b["valid"]) else b["estimated_y_px"] - a["estimated_y_px"], "error_dx_px": None if not (a["valid"] and b["valid"]) else (b["estimated_x_px"] - a["estimated_x_px"]) - (b["true_x_px"] - a["true_x_px"]), "error_dy_px": None if not (a["valid"] and b["valid"]) else (b["estimated_y_px"] - a["estimated_y_px"]) - (b["true_y_px"] - a["true_y_px"]), "valid": bool(a["valid"] and b["valid"]), "failure_reason": None if a["valid"] and b["valid"] else "invalid_endpoint"})
    out = Path(output_root); out.mkdir(parents=True, exist_ok=True)
    write_csv(out / "positions.csv", positions); write_csv(out / "steps.csv", step_rows); write_csv(out / "sequence_summary.csv", summary_rows); write_csv(out / "shape_detail.csv", shape_rows)
    # Same-scale representative visual panels (Raw / each frozen method / target)
    panel_items = []
    seen_families = set()
    for family in sorted(representatives):
        if family in seen_families: continue
        seen_families.add(family)
        values = representatives[family]
        raw = values["Raw"][0]; target = values["Raw"][2]
        tiles = [cv2.resize(v, (160, 160), interpolation=cv2.INTER_AREA) for v in [raw, np.rint(values["R118_E12"][1] * 255).astype(np.uint8), np.rint(values["R109_E48"][1] * 255).astype(np.uint8), target]]
        panel_items.append(np.concatenate(tiles, axis=1))
    cv2.imwrite(str(out / "representative_panels.png"), np.concatenate(panel_items, axis=0))
    audit = {"schema_version": 1, "status": "complete", "created_at_utc": datetime.now(timezone.utc).isoformat(), "bank_manifest_sha256": sha(ROOT / "data/development_sequences/manifest.json"), "models": {"Raw": {"source": "bank source", "checkpoint": None}, "R118_E12": {"checkpoint": str(R118_CHECKPOINT), "checkpoint_sha256": sha(R118_CHECKPOINT)}, "R109_E48": {"checkpoint": str(R109_CHECKPOINT), "checkpoint_sha256": sha(R109_CHECKPOINT)}}, "device": str(device), "bank_count": len(bank), "positions_rows": len(positions), "steps_rows": len(step_rows), "sequence_summary_rows": len(summary_rows), "shape_detail_rows": len(shape_rows), "expected": {"positions": len(bank) * 3, "protocol_observations": 4368}, "population": "development; same bank for all methods; not sealed confirmation", "invalid_rows_retained": True, "method_identity_resolved_by_checkpoint": True}
    (out / "audit.json").write_text(json.dumps(audit, indent=2), encoding="utf-8")
    return audit


def main():
    parser = argparse.ArgumentParser(); parser.add_argument("--output", type=Path, default=ROOT / "results/frozen_sequences"); parser.add_argument("--batch-size", type=int, default=12); parser.add_argument("--device", default="auto")
    args = parser.parse_args(); result = evaluate(args.output, args.batch_size, args.device); print(json.dumps(result, indent=2)); return 0


if __name__ == "__main__": raise SystemExit(main())

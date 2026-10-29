"""Matched R118 path interventions on the common development bank.

Each intervention changes one forward-path control in memory via a hook; R118
weights and source files are never edited or saved. The same source batch,
reference, ROI and fixed-reference locator are used for every variant.
"""
from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
import json
from pathlib import Path
import sys

import numpy as np
import torch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / "data")); sys.path.insert(0, str(ROOT / "validation"))
from sequence_bank import SequenceBank, sha
from sequence_metrics import estimate_position, summarize_sequence
from inference.run import load as load_r118
PROJECT_ROOT = Path(__file__).resolve().parents[3]

CHECKPOINT = Path(str(PROJECT_ROOT / 'Experiments/R118_PhysicalCoordinateRepairScratch/runs/verified_physical_repair/weights/epoch_012.pth'))
VARIANTS = ("base", "zero_normal_shift", "neutral_width_gain", "no_detail", "attenuation_matched")


def write_csv(path: Path, rows: list[dict]):
    keys = list(dict.fromkeys(key for row in rows for key in row))
    with path.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=keys); writer.writeheader(); writer.writerows(rows)


def zero_channel(index):
    def hook(_module, _inputs, output):
        value = output.clone(); value[:, index:index + 1] = 0; return value
    return hook


def evaluate(output_root: Path, batch_size: int = 12, device_name: str = "auto"):
    bank = SequenceBank(ROOT / "data/development_sequences")
    device = torch.device("cuda" if device_name == "auto" and torch.cuda.is_available() else device_name if device_name != "auto" else "cpu")
    model = load_r118(CHECKPOINT, str(device))
    positions, stats = [], []
    for start in range(0, len(bank.records), batch_size):
        records = bank.records[start:start + batch_size]
        sources, refs = [], []
        for row in records:
            source, reference, _ = bank.load(row); sources.append(np.rint(source * 255).astype(np.uint8)); refs.append(reference)
        tensor = torch.from_numpy(np.stack(sources).astype(np.float32) / 255.0)[:, None].to(device)
        with torch.inference_mode():
            model.detail_enabled = True; base = model.forward_details(tensor).output.float().clamp(0, 1).cpu().numpy()[:, 0]
        zero_hook = model.action_head.register_forward_hook(zero_channel(0))
        with torch.inference_mode():
            model.detail_enabled = True; zero = model.forward_details(tensor).output.float().clamp(0, 1).cpu().numpy()[:, 0]
        zero_hook.remove()
        neutral_hook = model.action_head.register_forward_hook(zero_channel(1))
        with torch.inference_mode():
            neutral = model.forward_details(tensor).output.float().clamp(0, 1).cpu().numpy()[:, 0]
            model.detail_enabled = False; nodetail = model.forward_details(tensor).output.float().clamp(0, 1).cpu().numpy()[:, 0]
            model.detail_enabled = True
        neutral_hook.remove()
        raw_values = np.stack(sources).astype(np.float32) / 255.0
        base_change = np.mean(np.abs(base - raw_values), axis=(1, 2))
        zero_change = np.mean(np.abs(zero - raw_values), axis=(1, 2))
        scale = np.clip(zero_change / np.maximum(base_change, 1e-7), 0, 2)[:, None, None]
        attenuation = np.clip(raw_values + scale * (base - raw_values), 0, 1)
        values = {"base": base, "zero_normal_shift": zero, "neutral_width_gain": neutral, "no_detail": nodetail, "attenuation_matched": attenuation}
        for variant, output in values.items():
            for row, source, reference, image in zip(records, sources, refs, output):
                image = image.astype(np.float32)
                roi = None if row["complete_object_in_roi"] else (20, 20, 236, 236)
                estimate = estimate_position(image, reference, roi)
                positions.append({"variant": variant, "sequence_id": row["sequence_id"], "scene_id": row["scene_id"], "family": row["family"], "protocol": row["protocol"], "condition_id": row["condition_id"], "frame_index": row["frame_index"], "true_x_px": row["true_x_px"], "true_y_px": row["true_y_px"], "estimated_x_px": estimate.x_px, "estimated_y_px": estimate.y_px, "valid": estimate.valid, "failure_reason": None if estimate.valid else estimate.reason})
                raw = source.astype(np.float32) / 255.0
                diff = image - raw
                stats.append({"variant": variant, "sequence_id": row["sequence_id"], "protocol": row["protocol"], "condition_id": row["condition_id"], "family": row["family"], "change_gray_mean": float(np.mean(np.abs(diff)) * 255), "change_gray_p95": float(np.percentile(np.abs(diff), 95) * 255), "output_min": float(image.min()), "output_max": float(image.max())})
        del tensor, sources, refs, base, zero, neutral, nodetail
    groups = {}
    for row in positions: groups.setdefault((row["variant"], row["sequence_id"], row["protocol"], row["condition_id"]), []).append(row)
    summaries = []
    for (variant, sequence_id, protocol, condition), rows in groups.items():
        first = rows[0]; summaries.append({"variant": variant, "sequence_id": sequence_id, "scene_id": first["scene_id"], "family": first["family"], "protocol": protocol, "condition_id": condition, **summarize_sequence(rows)})
    root = Path(output_root); root.mkdir(parents=True, exist_ok=True)
    write_csv(root / "positions.csv", positions); write_csv(root / "stats.csv", stats); write_csv(root / "sequence_summary.csv", summaries)
    audit = {"schema_version": 1, "status": "complete", "created_at_utc": datetime.now(timezone.utc).isoformat(), "checkpoint": str(CHECKPOINT), "checkpoint_sha256": sha(CHECKPOINT), "bank_manifest_sha256": sha(ROOT / "data/development_sequences/manifest.json"), "variants": list(VARIANTS), "rows": {"positions": len(positions), "stats": len(stats), "sequence_summary": len(summaries)}, "same_bank_and_reference": True, "weights_saved_or_modified": False, "amplitude_control": "calculated from per-image output change in stats; no intervention weights saved", "device": str(device)}
    (root / "audit.json").write_text(json.dumps(audit, indent=2), encoding="utf-8")
    return audit


def main():
    parser = argparse.ArgumentParser(); parser.add_argument("--output", type=Path, default=ROOT / "results/interventions"); parser.add_argument("--batch-size", type=int, default=12); parser.add_argument("--device", default="auto")
    args = parser.parse_args(); result = evaluate(args.output, args.batch_size, args.device); print(json.dumps(result, indent=2)); return 0


if __name__ == "__main__": raise SystemExit(main())

"""R87 versus Raw on the frozen R73/R74 ACM stress sets."""
from __future__ import annotations

import argparse
import csv
import importlib.util
import json
import math
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

import cv2
import numpy as np
import torch
PROJECT_ROOT = Path(__file__).resolve().parents[3]


EXPERIMENT_DIR = Path(__file__).resolve().parents[1]
OUTPUT_DIR = EXPERIMENT_DIR / "results" / "external_acm_stress"
SETS = {
    "R73_novel_shapes": Path(str(PROJECT_ROOT / 'Experiments/R73_R61ExpandedSyntheticACMGeneralization/data/r73_synthetic_acm_val/manifest.json')),
    "R74_hard_microscopy": Path(str(PROJECT_ROOT / 'Experiments/R74_R61HardMicroscopyACMGeneralization/data/r74_hard_acm_val/manifest.json')),
}


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def json_dump(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def gate(row: dict[str, Any], prefix: str = "") -> bool:
    distance = float(row[f"{prefix}boundary_distance_px"])
    iou = float(row[f"{prefix}iou"])
    return math.isfinite(distance) and distance <= 1.0 and iou >= 0.90


def catastrophic(row: dict[str, Any], prefix: str = "") -> bool:
    distance = float(row[f"{prefix}boundary_distance_px"])
    iou = float(row[f"{prefix}iou"])
    return (not math.isfinite(distance)) or distance > 10.0 or iou < 0.50


def finite_median(values: list[float]) -> float:
    finite = [value for value in values if math.isfinite(value)]
    return float(np.median(finite)) if finite else float("inf")


def summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    by_family: dict[str, Any] = {}
    for family in sorted({str(row["family"]) for row in rows}):
        family_rows = [row for row in rows if row["family"] == family]
        by_family[family] = {
            "count": len(family_rows),
            "model_gate_pass_count": sum(gate(row) for row in family_rows),
            "raw_gate_pass_count": sum(gate(row, "raw_") for row in family_rows),
            "model_median_iou": float(np.median([row["iou"] for row in family_rows])),
            "raw_median_iou": float(np.median([row["raw_iou"] for row in family_rows])),
            "model_median_boundary_px": finite_median([row["boundary_distance_px"] for row in family_rows]),
            "raw_median_boundary_px": finite_median([row["raw_boundary_distance_px"] for row in family_rows]),
        }
    return {
        "count": len(rows),
        "accuracy_gate": {"maximum_boundary_distance_px": 1.0, "minimum_iou": 0.90},
        "model_gate_pass_count": sum(gate(row) for row in rows),
        "model_gate_pass_rate": float(np.mean([gate(row) for row in rows])),
        "raw_gate_pass_count": sum(gate(row, "raw_") for row in rows),
        "raw_gate_pass_rate": float(np.mean([gate(row, "raw_") for row in rows])),
        "model_catastrophic_count": sum(catastrophic(row) for row in rows),
        "raw_catastrophic_count": sum(catastrophic(row, "raw_") for row in rows),
        "model_median_iou": float(np.median([row["iou"] for row in rows])),
        "raw_median_iou": float(np.median([row["raw_iou"] for row in rows])),
        "model_median_boundary_px": finite_median([row["boundary_distance_px"] for row in rows]),
        "raw_median_boundary_px": finite_median([row["raw_boundary_distance_px"] for row in rows]),
        "model_only_pass_count": sum(gate(row) and not gate(row, "raw_") for row in rows),
        "raw_only_pass_count": sum(gate(row, "raw_") and not gate(row) for row in rows),
        "family_summary": by_family,
    }


def evaluate_set(name: str, manifest_path: Path, model, trainer, evaluator, device: torch.device, limit: int | None) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    records = list(manifest["records"])
    if limit is not None:
        records = records[:limit]
    rows: list[dict[str, Any]] = []
    recon_root = OUTPUT_DIR / "reconstructions" / name
    overlay_cache: dict[str, np.ndarray] = {}
    for index, record in enumerate(records):
        source_u8 = cv2.imread(str(record["src"]), cv2.IMREAD_GRAYSCALE)
        truth_u8 = cv2.imread(str(record["mask"]), cv2.IMREAD_GRAYSCALE)
        if source_u8 is None or truth_u8 is None:
            raise FileNotFoundError(record["src"] if source_u8 is None else record["mask"])
        source = source_u8.astype(np.float32) / 255.0
        truth = truth_u8 >= 128
        reconstruction = trainer.tiled_predict(model, source, device, patch=896, core=512, amp_enabled=False)
        bright = str(record["polarity"]).lower() == "bright"
        model_mask = evaluator.acm_mask(reconstruction, bright)
        raw_mask = evaluator.acm_mask(source, bright)
        model_metrics = evaluator.boundary_metrics(model_mask, truth)
        raw_metrics = evaluator.boundary_metrics(raw_mask, truth)
        row = {
            "dataset": name,
            "image_id": record["image_id"],
            "family": record["family"],
            "polarity": record["polarity"],
            "iou": float(model_metrics["iou"]),
            "boundary_distance_px": float(model_metrics["symmetric_boundary_distance_px"]),
            "raw_iou": float(raw_metrics["iou"]),
            "raw_boundary_distance_px": float(raw_metrics["symmetric_boundary_distance_px"]),
        }
        rows.append(row)
        recon_path = recon_root / record["stage"] / record["filename"]
        recon_path.parent.mkdir(parents=True, exist_ok=True)
        cv2.imwrite(str(recon_path), np.rint(np.clip(reconstruction, 0.0, 1.0) * 255.0).astype(np.uint8))
        if catastrophic(row) or index < 4:
            overlay_cache[record["image_id"]] = evaluator.contour_overlay(reconstruction, model_mask, truth)
        print(json.dumps({"dataset": name, "completed": index + 1, "total": len(records)}, ensure_ascii=False), flush=True)

    fields = list(rows[0].keys())
    table_path = OUTPUT_DIR / "tables" / f"{name}.csv"
    table_path.parent.mkdir(parents=True, exist_ok=True)
    with table_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields); writer.writeheader(); writer.writerows(rows)

    worst = sorted(rows, key=lambda row: (not math.isfinite(row["boundary_distance_px"]), row["boundary_distance_px"]), reverse=True)[:12]
    diagnostic_rows = []
    for row in worst:
        record = next(record for record in records if record["image_id"] == row["image_id"])
        source_u8 = cv2.imread(str(record["src"]), cv2.IMREAD_GRAYSCALE)
        truth_u8 = cv2.imread(str(record["mask"]), cv2.IMREAD_GRAYSCALE)
        recon_u8 = cv2.imread(str(recon_root / record["stage"] / record["filename"]), cv2.IMREAD_GRAYSCALE)
        overlay = overlay_cache.get(record["image_id"])
        if overlay is None:
            bright = str(record["polarity"]).lower() == "bright"
            mask = evaluator.acm_mask(recon_u8.astype(np.float32) / 255.0, bright)
            overlay = evaluator.contour_overlay(recon_u8.astype(np.float32) / 255.0, mask, truth_u8 >= 128)
        panels = [cv2.cvtColor(image, cv2.COLOR_GRAY2BGR) for image in (source_u8, recon_u8, truth_u8)] + [overlay]
        for panel, label in zip(panels, ("RAW", "R87", "TRUTH", "ACM red / truth green")):
            cv2.putText(panel, label, (8, 24), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2, cv2.LINE_AA)
        diagnostic_rows.append(np.concatenate(panels, axis=1))
    if diagnostic_rows:
        cv2.imwrite(str(OUTPUT_DIR / f"{name}_worst_cases.png"), np.concatenate(diagnostic_rows, axis=0))
    return rows, summarize(rows)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--device", default="cuda:0")
    parser.add_argument("--limit", type=int)
    args = parser.parse_args()
    device = torch.device(args.device)
    evaluator = load_module("r87_external_eval", EXPERIMENT_DIR / "scripts" / "evaluate_r87.py")
    trainer = load_module("r87_external_trainer", EXPERIMENT_DIR / "training" / "train_r87.py")
    _, run_summary = evaluator.find_completed_run()
    checkpoint = Path(run_summary["weights_dir"]) / "best_validation.pth.tar"
    model, payload = evaluator.load_checkpoint(checkpoint, device)
    results: dict[str, Any] = {
        "checkpoint": str(checkpoint),
        "checkpoint_epoch": int(payload["epoch"]),
        "development_status": "independent_of_R87_training_but_not_claimed_blind_external",
        "datasets": {},
    }
    for name, manifest_path in SETS.items():
        _, summary = evaluate_set(name, manifest_path, model, trainer, evaluator, device, args.limit)
        results["datasets"][name] = summary
    json_dump(OUTPUT_DIR / "external_acm_stress_summary.json", results)
    print(json.dumps(results, indent=2, ensure_ascii=False), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Locked post-training evaluation for R87."""
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
import matplotlib.pyplot as plt
import numpy as np
import torch
from scipy.ndimage import binary_erosion, distance_transform_edt
from skimage.filters import threshold_otsu
from skimage.segmentation import morphological_chan_vese
from torch.utils.data import DataLoader


EXPERIMENT_DIR = Path(__file__).resolve().parents[1]
CONFIG = json.loads((EXPERIMENT_DIR / "config" / "experiment.json").read_text(encoding="utf-8"))
DATASET_DIR = EXPERIMENT_DIR / "data" / CONFIG["dataset"]["package_name"]
OUTPUT_DIR = EXPERIMENT_DIR / "results" / "final_evaluation"


def json_dump(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def write_progress(stage: str, completed: int, total: int, **extra: Any) -> None:
    payload = {"stage": stage, "completed": int(completed), "total": int(total), **extra}
    json_dump(OUTPUT_DIR / "evaluation_progress.json", payload)
    print(json.dumps(payload, ensure_ascii=False), flush=True)


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def find_completed_run() -> tuple[Path, dict[str, Any]]:
    summaries = sorted((EXPERIMENT_DIR / "runs").glob("training_progress_*/run_summary.json"), key=lambda path: path.stat().st_mtime)
    completed = []
    for path in summaries:
        payload = json.loads(path.read_text(encoding="utf-8"))
        if payload.get("status") == "complete" and int(payload.get("completed_epoch", 0)) == 100:
            completed.append((path, payload))
    if not completed:
        raise FileNotFoundError("No completed 100-epoch R87 run")
    return completed[-1]


def load_checkpoint(checkpoint: Path, device: torch.device):
    model_module = load_module("r87_eval_model", EXPERIMENT_DIR / "model" / "r87_model.py")
    model = model_module.build_model(base=int(CONFIG["architecture"]["base_channels"])).to(device)
    payload = torch.load(checkpoint, map_location=device)
    if payload.get("checkpoint_loaded") is not False or payload.get("resume_source") is not None:
        raise RuntimeError("Checkpoint scratch provenance failed")
    model.load_state_dict(payload["ema_state_dict"], strict=True)
    model.eval()
    return model, payload


def boundary_metrics(predicted: np.ndarray, truth: np.ndarray) -> dict[str, float]:
    predicted = predicted.astype(bool)
    truth = truth.astype(bool)
    intersection = int(np.logical_and(predicted, truth).sum())
    union = int(np.logical_or(predicted, truth).sum())
    iou = intersection / max(union, 1)
    pred_boundary = np.logical_xor(predicted, binary_erosion(predicted))
    truth_boundary = np.logical_xor(truth, binary_erosion(truth))
    if not pred_boundary.any() or not truth_boundary.any():
        return {"iou": iou, "symmetric_boundary_distance_px": float("inf"), "acm_success": 0.0}
    distance_to_truth = distance_transform_edt(~truth_boundary)
    distance_to_pred = distance_transform_edt(~pred_boundary)
    symmetric = 0.5 * (float(distance_to_truth[pred_boundary].mean()) + float(distance_to_pred[truth_boundary].mean()))
    return {"iou": iou, "symmetric_boundary_distance_px": symmetric, "acm_success": 1.0}


def acm_mask(image: np.ndarray, bright_foreground: bool) -> np.ndarray:
    image = np.asarray(image, dtype=np.float32)
    low, high = float(np.percentile(image, 1)), float(np.percentile(image, 99))
    normalized = np.clip((image - low) / max(high - low, 1e-6), 0.0, 1.0)
    threshold = float(threshold_otsu(normalized))
    initial = normalized >= threshold if bright_foreground else normalized <= threshold
    if initial.mean() < 0.002 or initial.mean() > 0.998:
        initial = normalized >= 0.5 if bright_foreground else normalized <= 0.5
    return morphological_chan_vese(normalized, num_iter=35, init_level_set=initial, smoothing=1, lambda1=1.0, lambda2=1.0).astype(bool)


def contour_overlay(gray: np.ndarray, acm: np.ndarray, truth: np.ndarray) -> np.ndarray:
    base = np.rint(np.clip(gray, 0.0, 1.0) * 255.0).astype(np.uint8)
    canvas = cv2.cvtColor(base, cv2.COLOR_GRAY2BGR)
    acm_edge = np.logical_xor(acm, binary_erosion(acm))
    truth_edge = np.logical_xor(truth, binary_erosion(truth))
    canvas[truth_edge] = (0, 255, 0)
    canvas[acm_edge] = (0, 0, 255)
    return canvas


@torch.no_grad()
def model_patch(model, source: np.ndarray, device: torch.device, amp: bool = True) -> np.ndarray:
    tensor = torch.from_numpy(source.copy()).to(device=device, dtype=torch.float32)[None, None]
    with torch.autocast(device_type="cuda", dtype=torch.bfloat16, enabled=amp and device.type == "cuda"):
        output = model(tensor)
    return output[0, 0].float().cpu().numpy()


def run_acm(model, manifest: dict[str, Any], device: torch.device) -> dict[str, Any]:
    allowed_roles = ("basic_geometry", "noncircular_complex", "cross_tile_large", "known_subpixel_motion")
    selected: list[dict[str, Any]] = []
    role_seen: defaultdict[str, int] = defaultdict(int)
    origin = (int(manifest["canvas_size"]) - 896) // 2
    halo = 192
    excluded_empty_truth = 0
    for record in manifest["records"]:
        if record["split"] != "internal_test" or int(record["rendering"]) != 0 or record["role"] not in allowed_roles:
            continue
        if role_seen[record["role"]] >= 16:
            continue
        target = np.load(DATASET_DIR / record["target"], mmap_mode="r", allow_pickle=False)
        target_core = np.asarray(target[origin + halo:origin + halo + 512, origin + halo:origin + halo + 512]).astype(np.float32) / 255.0
        threshold = 0.5 * (float(record["target_background"]) + float(record["target_foreground"]))
        truth = target_core >= threshold if bool(record["bright_foreground"]) else target_core <= threshold
        foreground_fraction = float(truth.mean())
        if foreground_fraction < 0.002 or foreground_fraction > 0.998:
            excluded_empty_truth += 1
            continue
        selected.append(record)
        role_seen[record["role"]] += 1
    rows = []
    overlays = []
    table_dir = OUTPUT_DIR / "tables"
    table_dir.mkdir(parents=True, exist_ok=True)
    partial_path = table_dir / "acm_contour_metrics.partial.csv"
    write_progress("acm_contour", 0, len(selected))
    for index, record in enumerate(selected):
        source = np.load(DATASET_DIR / record["source"], mmap_mode="r", allow_pickle=False)
        target = np.load(DATASET_DIR / record["target"], mmap_mode="r", allow_pickle=False)
        source_patch = np.asarray(source[origin:origin + 896, origin:origin + 896]).astype(np.float32) / 255.0
        target_patch = np.asarray(target[origin:origin + 896, origin:origin + 896]).astype(np.float32) / 255.0
        prediction = model_patch(model, source_patch, device)
        source_core = source_patch[halo:halo + 512, halo:halo + 512]
        pred_core = prediction[halo:halo + 512, halo:halo + 512]
        target_core = target_patch[halo:halo + 512, halo:halo + 512]
        threshold = 0.5 * (float(record["target_background"]) + float(record["target_foreground"]))
        truth = target_core >= threshold if bool(record["bright_foreground"]) else target_core <= threshold
        try:
            segmentation = acm_mask(pred_core, bool(record["bright_foreground"]))
            metrics = boundary_metrics(segmentation, truth)
        except Exception as error:
            metrics = {"iou": 0.0, "symmetric_boundary_distance_px": float("inf"), "acm_success": 0.0, "error": str(error)}
            segmentation = np.zeros_like(truth)
        try:
            raw_segmentation = acm_mask(source_core, bool(record["bright_foreground"]))
            raw_metrics = boundary_metrics(raw_segmentation, truth)
        except Exception as error:
            raw_metrics = {"iou": 0.0, "symmetric_boundary_distance_px": float("inf"), "acm_success": 0.0, "error": str(error)}
        rows.append({
            "scene_id": record["scene_id"],
            "role": record["role"],
            **metrics,
            "raw_iou": raw_metrics["iou"],
            "raw_symmetric_boundary_distance_px": raw_metrics["symmetric_boundary_distance_px"],
            "raw_acm_success": raw_metrics["acm_success"],
            "raw_error": raw_metrics.get("error", ""),
        })
        acm_fields = [
            "scene_id", "role", "iou", "symmetric_boundary_distance_px", "acm_success", "error",
            "raw_iou", "raw_symmetric_boundary_distance_px", "raw_acm_success", "raw_error",
        ]
        with partial_path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=acm_fields, extrasaction="ignore")
            writer.writeheader(); writer.writerows(rows)
        write_progress("acm_contour", index + 1, len(selected), scene_id=record["scene_id"], role=record["role"])
        if index < 16:
            overlay = contour_overlay(pred_core, segmentation, truth)
            cv2.putText(overlay, record["role"], (6, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.48, (255, 255, 0), 1, cv2.LINE_AA)
            overlays.append(overlay)

    with (table_dir / "acm_contour_metrics.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=acm_fields, extrasaction="ignore")
        writer.writeheader(); writer.writerows(rows)
    if overlays:
        grid_rows = []
        blank = np.zeros_like(overlays[0])
        for index in range(0, len(overlays), 4):
            group = overlays[index:index + 4]
            grid_rows.append(np.concatenate(group + [blank] * (4 - len(group)), axis=1))
        cv2.imwrite(str(OUTPUT_DIR / "acm_contour_overlays.png"), np.concatenate(grid_rows, axis=0))
    finite = [row["symmetric_boundary_distance_px"] for row in rows if math.isfinite(row["symmetric_boundary_distance_px"])]
    def gate_pass(row: dict[str, Any], prefix: str = "") -> bool:
        distance = float(row[f"{prefix}symmetric_boundary_distance_px"])
        iou = float(row[f"{prefix}iou"])
        return math.isfinite(distance) and distance <= 1.0 and iou >= 0.90

    role_quality = {}
    for role in allowed_roles:
        role_rows = [row for row in rows if row["role"] == role]
        if not role_rows:
            continue
        role_quality[role] = {
            "count": len(role_rows),
            "model_gate_pass_count": sum(gate_pass(row) for row in role_rows),
            "raw_gate_pass_count": sum(gate_pass(row, "raw_") for row in role_rows),
        }
    return {
        "count": len(rows),
        "excluded_empty_truth_count": excluded_empty_truth,
        "role_counts": dict(role_seen),
        "segmentation_nonempty_rate": float(np.mean([row["acm_success"] for row in rows])) if rows else 0.0,
        "accuracy_gate": {"maximum_boundary_distance_px": 1.0, "minimum_iou": 0.90},
        "model_gate_pass_count": sum(gate_pass(row) for row in rows),
        "model_gate_pass_rate": float(np.mean([gate_pass(row) for row in rows])) if rows else 0.0,
        "raw_gate_pass_count": sum(gate_pass(row, "raw_") for row in rows),
        "raw_gate_pass_rate": float(np.mean([gate_pass(row, "raw_") for row in rows])) if rows else 0.0,
        "model_catastrophic_count": sum(
            (not math.isfinite(float(row["symmetric_boundary_distance_px"])))
            or float(row["symmetric_boundary_distance_px"]) > 10.0
            or float(row["iou"]) < 0.50
            for row in rows
        ),
        "role_quality": role_quality,
        "median_iou": float(np.median([row["iou"] for row in rows])) if rows else 0.0,
        "median_symmetric_boundary_distance_px": float(np.median(finite)) if finite else float("inf"),
        "worst_role_median_boundary_px": max(
            (float(np.median([row["symmetric_boundary_distance_px"] for row in rows if row["role"] == role and math.isfinite(row["symmetric_boundary_distance_px"])])) for role in allowed_roles),
            default=float("inf"),
        ),
    }


@torch.no_grad()
def run_tile_consistency(model, manifest: dict[str, Any], trainer, device: torch.device) -> dict[str, Any]:
    selected = []
    role_seen: defaultdict[str, int] = defaultdict(int)
    for record in manifest["records"]:
        if record["split"] == "internal_test" and int(record["rendering"]) == 0 and role_seen[record["role"]] < 2:
            selected.append(record); role_seen[record["role"]] += 1
    rows = []
    for record in selected:
        source = np.load(DATASET_DIR / record["source"], mmap_mode="r", allow_pickle=False).astype(np.float32) / 255.0
        full = model_patch(model, source, device, amp=False)
        tiled = trainer.tiled_predict(model, source, device, patch=896, core=512, amp_enabled=False)
        difference = np.abs(full[192:-192, 192:-192] - tiled[192:-192, 192:-192]) * 255.0
        rows.append({
            "scene_id": record["scene_id"], "role": record["role"],
            "mean_abs_gray": float(difference.mean()),
            "p99_abs_gray": float(np.percentile(difference, 99)),
            "max_abs_gray": float(difference.max()),
        })
        write_progress("tile_consistency", len(rows), len(selected), scene_id=record["scene_id"], role=record["role"])
    table_dir = OUTPUT_DIR / "tables"; table_dir.mkdir(parents=True, exist_ok=True)
    with (table_dir / "full_vs_tiled.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys())); writer.writeheader(); writer.writerows(rows)
    return {
        "count": len(rows),
        "mean_abs_gray": float(np.mean([row["mean_abs_gray"] for row in rows])),
        "worst_p99_abs_gray": float(max(row["p99_abs_gray"] for row in rows)),
        "worst_max_abs_gray": float(max(row["max_abs_gray"] for row in rows)),
        "gate": {"mean_max": 0.10, "p99_max": 1.0, "absolute_max": 3.0},
        "passed": (
            float(np.mean([row["mean_abs_gray"] for row in rows])) <= 0.10
            and max(row["p99_abs_gray"] for row in rows) <= 1.0
            and max(row["max_abs_gray"] for row in rows) <= 3.0
        ),
    }


def make_training_curve(summary: dict[str, Any]) -> str | None:
    log_path = Path(summary["training_log"])
    if not log_path.is_file():
        return None
    epochs, train, val = [], [], []
    with log_path.open("r", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            epochs.append(int(row["epoch"])); train.append(float(row["train_total"])); val.append(float(row["val_total"]) if row["val_total"] else np.nan)
    plt.figure(figsize=(9, 5))
    plt.plot(epochs, train, label="train")
    plt.plot(epochs, val, "o-", label="validation every 5 epochs", markersize=3)
    plt.xlabel("Epoch"); plt.ylabel("Locked total loss"); plt.grid(alpha=0.25); plt.legend(); plt.tight_layout()
    path = OUTPUT_DIR / "training_curve.png"; plt.savefig(path, dpi=160); plt.close()
    return str(path)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--device", default="cuda:0")
    args = parser.parse_args()
    device = torch.device(args.device)
    summary_path, run_summary = find_completed_run()
    checkpoint = Path(run_summary["weights_dir"]) / "best_validation.pth.tar"
    model, checkpoint_payload = load_checkpoint(checkpoint, device)
    trainer = load_module("r87_eval_trainer", EXPERIMENT_DIR / "training" / "train_r87.py")
    manifest = json.loads((DATASET_DIR / "manifest.json").read_text(encoding="utf-8"))

    write_progress("synthetic_internal_test", 0, 1)
    internal_dataset = trainer.ScenePairDataset(manifest, "internal_test", 896, 512, 0, include_both_renderings=True)
    # The trainer module is loaded dynamically above. On Windows, spawned data
    # workers cannot import that transient module name, so evaluation must read
    # the locked dataset in the main process.
    internal_loader = DataLoader(internal_dataset, batch_size=2, shuffle=False, num_workers=0, pin_memory=device.type == "cuda")
    synthetic = trainer.evaluate(model, internal_loader, device, 896, 512, amp_enabled=device.type == "cuda")
    write_progress("synthetic_internal_test", 1, 1)
    acm = run_acm(model, manifest, device)
    write_progress("tile_consistency", 0, 16)
    tile = run_tile_consistency(model, manifest, trainer, device)
    write_progress("live_validation", 0, 3)
    curve = make_training_curve(run_summary)

    live_dir = OUTPUT_DIR / "live_validation"
    live_dir.mkdir(parents=True, exist_ok=True)
    live_outputs = []
    live_paths = sorted((EXPERIMENT_DIR / "data" / "live_validation").glob("*.bmp"))
    for index, path in enumerate(live_paths):
        raw = cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)
        normalized = raw.astype(np.float32) / 255.0
        recon = trainer.tiled_predict(model, normalized, device, amp_enabled=False)
        recon_path = live_dir / f"{path.stem}_recon.bmp"
        cv2.imwrite(str(recon_path), np.rint(recon * 255.0).astype(np.uint8))
        sheet = np.concatenate([raw, np.rint(recon * 255.0).astype(np.uint8)], axis=1)
        cv2.imwrite(str(live_dir / f"{path.stem}_compare.png"), sheet)
        live_outputs.append(str(recon_path))
        write_progress("live_validation", index + 1, len(live_paths), image=path.name)

    result = {
        "experiment_id": CONFIG["experiment_id"],
        "run_summary": str(summary_path),
        "checkpoint": str(checkpoint),
        "checkpoint_epoch": int(checkpoint_payload["epoch"]),
        "scratch_provenance": {
            "checkpoint_loaded_before_training": checkpoint_payload.get("checkpoint_loaded"),
            "resume_source": checkpoint_payload.get("resume_source"),
            "initial_parameter_sha256": checkpoint_payload["metadata"]["initial_parameter_sha256"],
        },
        "synthetic_internal_test": synthetic,
        "acm_contour": acm,
        "tile_consistency": tile,
        "live_validation_outputs": live_outputs,
        "training_curve": curve,
    }
    json_dump(OUTPUT_DIR / "evaluation_summary.json", result)
    write_progress("complete", 1, 1, summary=str(OUTPUT_DIR / "evaluation_summary.json"))
    print(json.dumps(result, indent=2), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

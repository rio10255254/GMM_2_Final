from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
import shutil
import subprocess
import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

import cv2
import numpy as np
import pandas as pd
import torch
from skimage.metrics import structural_similarity


ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "config" / "experiment.json"
RESULTS = ROOT / "results"
TABLES = RESULTS / "tables"
RECON = RESULTS / "reconstructions"
LOGS = RESULTS / "logs"
STATUS = RESULTS / "run_status.json"


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def require_hash(path: Path, expected: str) -> str:
    if not path.is_file():
        raise FileNotFoundError(path)
    actual = sha256(path)
    if actual.lower() != expected.lower():
        raise RuntimeError(f"Locked file changed: {path}\nexpected={expected}\nactual={actual}")
    return actual


def read_gray(path: Path) -> np.ndarray:
    image = cv2.imdecode(np.fromfile(path, dtype=np.uint8), cv2.IMREAD_GRAYSCALE)
    if image is None:
        raise OSError(f"Could not decode image: {path}")
    return image


def write_bmp(path: Path, image: np.ndarray) -> None:
    path = path.with_suffix(".bmp")
    path.parent.mkdir(parents=True, exist_ok=True)
    ok, encoded = cv2.imencode(".bmp", np.asarray(image, dtype=np.uint8))
    if not ok:
        raise OSError(path)
    encoded.tofile(path)


def image_paths(directory: Path) -> list[Path]:
    return sorted(path for path in directory.glob("*.bmp") if path.is_file())


def update_status(stage: str, state: str, detail: str = "") -> None:
    payload = read_json(STATUS) if STATUS.is_file() else {
        "experiment_id": "R80_R79E23vsE100GeneralizationValidation",
        "started_at": datetime.now().astimezone().isoformat(),
        "history": [],
    }
    payload.update({
        "current_stage": stage,
        "state": state,
        "detail": detail,
        "updated_at": datetime.now().astimezone().isoformat(),
    })
    payload["history"].append({
        "stage": stage,
        "state": state,
        "detail": detail,
        "at": payload["updated_at"],
    })
    write_json(STATUS, payload)


def checkpoint_audit(config: dict) -> dict:
    records = {}
    for label, item in config["models"].items():
        checkpoint = Path(item["checkpoint"])
        actual_hash = require_hash(checkpoint, item["checkpoint_sha256"])
        payload = torch.load(checkpoint, map_location="cpu")
        epoch = int(payload.get("epoch", -1))
        if epoch != int(item["expected_epoch"]):
            raise RuntimeError(f"{label}: expected epoch {item['expected_epoch']}, found {epoch}")
        if not payload.get(item["state_key"]):
            raise RuntimeError(f"{label}: missing {item['state_key']}")
        records[label] = {
            "checkpoint": str(checkpoint.resolve()),
            "checkpoint_sha256": actual_hash,
            "epoch": epoch,
            "state_key": item["state_key"],
        }
        del payload
    return records


def audit_internal_test(config: dict) -> tuple[dict, list[dict]]:
    item = config["internal_test"]
    manifest_path = Path(item["manifest"])
    require_hash(manifest_path, item["manifest_sha256"])
    manifest = read_json(manifest_path)
    if manifest.get("content_sha256") != item["dataset_content_sha256"]:
        raise RuntimeError("R79 dataset content identity changed")
    rows = [row for row in manifest["pairs"] if row["split"] == item["split"]]
    if len(rows) != int(item["expected_images"]):
        raise RuntimeError(f"Expected {item['expected_images']} internal-test rows, found {len(rows)}")
    geometry_ids = {row["geometry_id"] for row in rows}
    if len(geometry_ids) != int(item["expected_geometry_ids"]):
        raise RuntimeError("Internal-test geometry count changed")
    train_ids = {row["geometry_id"] for row in manifest["pairs"] if row["split"] == "train"}
    validation_ids = {row["geometry_id"] for row in manifest["pairs"] if row["split"] == "validation"}
    overlap = geometry_ids & (train_ids | validation_ids)
    if overlap:
        raise RuntimeError(f"Internal-test geometry leakage: {sorted(overlap)[:5]}")
    roles = Counter(row["training_role"] for row in rows)
    package = Path(item["package_root"])
    for row in rows:
        for key in ("package_src", "package_lbl", "geometry_mask", "geometry_mask_aa"):
            if not (package / row[key]).is_file():
                raise FileNotFoundError(package / row[key])
    audit = {
        "images": len(rows),
        "geometry_ids": len(geometry_ids),
        "role_counts": dict(sorted(roles.items())),
        "geometry_overlap_with_train_or_validation": len(overlap),
        "manifest_sha256": item["manifest_sha256"],
        "dataset_content_sha256": item["dataset_content_sha256"],
    }
    return audit, rows


def audit_real_fov(config: dict) -> dict:
    item = config["real_fov"]
    require_hash(Path(item["r78_input_audit"]), item["r78_input_audit_sha256"])
    require_hash(Path(item["locked_measurements"]), item["locked_measurements_sha256"])
    raw_root = Path(item["locked_raw_root"])
    audit = {"total_frames": 0, "sequences": {}, "exact_duplicate_groups": []}
    hash_to_paths: dict[str, list[str]] = defaultdict(list)
    for sequence, settings in item["sequences"].items():
        paths = image_paths(raw_root / sequence)
        expected = int(settings["frame_count"])
        if len(paths) != expected:
            raise RuntimeError(f"{sequence}: expected {expected} frames, found {len(paths)}")
        if [path.name for path in paths] != [f"frame_{index:04d}.bmp" for index in range(expected)]:
            raise RuntimeError(f"{sequence}: filenames are not the locked contiguous sequence")
        shapes = Counter(tuple(read_gray(path).shape) for path in paths)
        if set(shapes) != {(1536, 2048)}:
            raise RuntimeError(f"{sequence}: unexpected shapes {dict(shapes)}")
        for path in paths:
            hash_to_paths[sha256(path)].append(f"{sequence}/{path.name}")
        audit["sequences"][sequence] = {
            "frames": len(paths),
            "shape": [1536, 2048],
            "magnification": settings["magnification"],
            "nominal_step_um": settings["nominal_step_um"],
        }
        audit["total_frames"] += len(paths)
    if audit["total_frames"] != int(item["expected_frames"]):
        raise RuntimeError("Locked real-frame total changed")
    audit["exact_duplicate_groups"] = [paths for paths in hash_to_paths.values() if len(paths) > 1]
    audit["exact_duplicate_frame_count"] = sum(len(paths) for paths in audit["exact_duplicate_groups"])
    return audit


def audit_external_suites(config: dict) -> dict:
    result = {}
    all_source_hashes: dict[str, list[str]] = defaultdict(list)
    for suite, item in config["external_acm_suites"].items():
        manifest_path = Path(item["manifest"])
        require_hash(manifest_path, item["manifest_sha256"])
        source_config = read_json(Path(item["source_config"]))
        root = Path(item["dataset_root"])
        families = source_config["dataset"]["families"]
        expected_per = int(source_config["dataset"]["images_per_family"])
        expected_names = [f"{index:04d}.bmp" for index in range(expected_per)]
        records = []
        for family in families:
            stage = family["stage"]
            grouped = {kind: image_paths(root / kind / stage) for kind in ("src", "lbl", "mask")}
            for kind, paths in grouped.items():
                if [path.name for path in paths] != expected_names:
                    raise RuntimeError(f"{suite}/{stage}/{kind}: coverage changed")
            for index, name in enumerate(expected_names):
                images = {kind: read_gray(root / kind / stage / name) for kind in grouped}
                if any(image.shape != (512, 512) for image in images.values()):
                    raise RuntimeError(f"{suite}/{stage}/{name}: shape changed")
                mask = images["mask"] > 0
                if set(np.unique(images["mask"]).tolist()) - {0, 255}:
                    raise RuntimeError(f"{suite}/{stage}/{name}: mask is not binary")
                components, _ = cv2.connectedComponents(mask.astype(np.uint8), 8)
                if components != 2:
                    raise RuntimeError(f"{suite}/{stage}/{name}: mask is not one connected object")
                source_hash = sha256(root / "src" / stage / name)
                all_source_hashes[source_hash].append(f"{suite}/{stage}/{name}")
                records.append({"family": family["name"], "stage": stage, "filename": name})
        if len(records) != int(item["expected_images"]):
            raise RuntimeError(f"{suite}: expected {item['expected_images']} images, found {len(records)}")
        result[suite] = {
            "images": len(records),
            "families": len(families),
            "manifest_sha256": item["manifest_sha256"],
            "image_shape": [512, 512],
            "binary_single_object_masks": True,
        }
    cross_suite_duplicates = [paths for paths in all_source_hashes.values() if len(paths) > 1]
    if cross_suite_duplicates:
        raise RuntimeError(f"External suites contain exact duplicate inputs: {cross_suite_duplicates[:3]}")
    result["cross_suite_exact_duplicate_groups"] = 0
    return result


def audit_sem(config: dict) -> dict:
    item = config["sem_acm"]
    require_hash(Path(item["ordering_manifest"]), item["ordering_manifest_sha256"])
    ordering_manifest = read_json(Path(item["ordering_manifest"]))
    if ordering_manifest.get("status") != "verified" or int(ordering_manifest.get("exact_copy_count", -1)) != 18:
        raise RuntimeError("SEM ordering evidence is not verified")
    mapping = pd.read_csv(item["ordering_mapping"])
    if len(mapping) != 36 or mapping["global_pillar_id"].nunique() != 36:
        raise RuntimeError("SEM 36-pillar mapping is incomplete")
    raw_dir = Path(item["raw_input_dir"])
    source_dir = Path(item["raw_source_dir"])
    checks = []
    for exposure in item["optical_exposures"]:
        locked = raw_dir / f"{exposure}.bmp"
        source = source_dir / f"{exposure}.bmp"
        locked_hash = sha256(locked)
        source_hash = sha256(source)
        if locked_hash != source_hash:
            raise RuntimeError(f"SEM optical input differs from source: {exposure}.bmp")
        if read_gray(locked).shape != (821, 821):
            raise RuntimeError(f"SEM optical image shape changed: {exposure}.bmp")
        checks.append({"exposure": exposure, "sha256": locked_hash})
    sem_dir = Path(item["sem_dir"])
    sem_files = [sem_dir / f"P-{index:02d}.tiff" for index in range(1, 10)]
    if not all(path.is_file() for path in sem_files):
        raise FileNotFoundError("One or more SEM P files are missing")
    return {
        "optical_exposures": len(checks),
        "physical_pillars": int(mapping["global_pillar_id"].nunique()),
        "sem_truth_files": len(sem_files),
        "ordering_verified": True,
        "optical_checks": checks,
    }


def audit_all(config: dict) -> dict:
    update_status("audit", "running")
    checkpoints = checkpoint_audit(config)
    internal, _ = audit_internal_test(config)
    real = audit_real_fov(config)
    external = audit_external_suites(config)
    sem = audit_sem(config)
    audit = {
        "status": "pass",
        "experiment_id": config["experiment_id"],
        "comparison_lock": config["comparison_lock"],
        "checkpoints": checkpoints,
        "internal_test": internal,
        "real_fov": real,
        "external_acm_suites": external,
        "sem_acm": sem,
        "audited_at": datetime.now().astimezone().isoformat(),
    }
    write_json(RESULTS / "input_audit.json", audit)
    update_status("audit", "complete", "All locked inputs and both checkpoints passed")
    print(json.dumps({
        "checkpoints": {key: value["epoch"] for key, value in checkpoints.items()},
        "internal_images": internal["images"],
        "real_frames": real["total_frames"],
        "external_images": sum(value.get("images", 0) for value in external.values() if isinstance(value, dict)),
        "sem_pillars": sem["physical_pillars"],
    }, ensure_ascii=False, indent=2), flush=True)
    return audit


def manifest_valid(output: Path, checkpoint_hash: str, expected_count: int) -> bool:
    path = output / "inference_manifest.json"
    if not path.is_file():
        return False
    manifest = read_json(path)
    outputs = [Path(row["output"]) for row in manifest.get("records", [])]
    return (
        manifest.get("checkpoint_sha256") == checkpoint_hash
        and manifest.get("state_key") == "ema_state_dict"
        and int(manifest.get("image_count", -1)) == expected_count
        and len(outputs) == expected_count
        and all(path.is_file() for path in outputs)
    )


def quarantine_partial(output: Path) -> None:
    if not output.exists() or not any(output.rglob("*")):
        return
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    target = RESULTS / "quarantine" / f"{output.name}_partial_{stamp}"
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(output), str(target))


def run_inference(config: dict, label: str, input_path: Path, output: Path, count: int, tile: int, overlap: int) -> None:
    model = config["models"][label]
    if manifest_valid(output, model["checkpoint_sha256"], count):
        print(f"[infer] reuse {label}: {output}", flush=True)
        return
    quarantine_partial(output)
    output.mkdir(parents=True, exist_ok=True)
    command = [
        config["runtime"]["python"],
        config["runtime"]["inference_script"],
        "--checkpoint", model["checkpoint"],
        "--input", str(input_path),
        "--output", str(output),
        "--device", config["runtime"]["device"],
        "--tile-size", str(tile),
        "--overlap", str(overlap),
    ]
    print("RUN:", subprocess.list2cmdline(command), flush=True)
    subprocess.run(command, check=True, cwd=ROOT)
    if not manifest_valid(output, model["checkpoint_sha256"], count):
        raise RuntimeError(f"Incomplete inference output: {output}")


def infer_all(config: dict) -> None:
    update_status("inference", "running")
    runtime = config["runtime"]
    real = config["real_fov"]
    raw_root = Path(real["locked_raw_root"])
    for label in config["models"]:
        run_inference(
            config, label, raw_root, RECON / "real_tile1024" / label,
            int(real["expected_frames"]), int(runtime["primary_tile_size"]), int(runtime["primary_overlap"]),
        )
        for sequence in ("5x_0p5um", "5x_1um"):
            count = int(real["sequences"][sequence]["frame_count"])
            run_inference(
                config, label, raw_root / sequence, RECON / "real_5x_tile512" / label / sequence,
                count, int(runtime["secondary_5x_tile_size"]), int(runtime["secondary_5x_overlap"]),
            )
        for suite, item in config["external_acm_suites"].items():
            run_inference(
                config, label, Path(item["dataset_root"]) / "src", RECON / "external" / suite / label,
                int(item["expected_images"]), int(runtime["primary_tile_size"]), int(runtime["primary_overlap"]),
            )
        sem = config["sem_acm"]
        run_inference(
            config, label, Path(sem["raw_input_dir"]), RECON / "sem" / label,
            len(sem["optical_exposures"]), int(sem["tile_size"]), int(sem["overlap"]),
        )
    update_status("inference", "complete", "Primary, 5x sensitivity, external ACM, and SEM reconstructions complete")


def load_inference_module(config: dict):
    path = Path(config["runtime"]["inference_script"])
    spec = importlib.util.spec_from_file_location("r79_inference", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def tolerant_edge_f1(pred: np.ndarray, truth: np.ndarray, tolerance: int = 2) -> tuple[float, float, float]:
    pred_edge = cv2.Canny(pred, 20, 50) > 0
    truth_edge = cv2.Canny(truth, 20, 50) > 0
    kernel = np.ones((2 * tolerance + 1, 2 * tolerance + 1), np.uint8)
    truth_dilated = cv2.dilate(truth_edge.astype(np.uint8), kernel) > 0
    pred_dilated = cv2.dilate(pred_edge.astype(np.uint8), kernel) > 0
    precision = float(np.mean(truth_dilated[pred_edge])) if pred_edge.any() else 0.0
    recall = float(np.mean(pred_dilated[truth_edge])) if truth_edge.any() else 0.0
    f1 = 2 * precision * recall / max(precision + recall, 1e-12)
    return precision, recall, f1


def highpass_energy(image: np.ndarray) -> float:
    floating = image.astype(np.float32) / 255.0
    high = floating - cv2.GaussianBlur(floating, (0, 0), 2.0)
    return float(np.sqrt(np.mean(high * high)))


def internal_metrics_for_image(pred: np.ndarray, source: np.ndarray, truth: np.ndarray) -> dict:
    pred_f = pred.astype(np.float32) / 255.0
    truth_f = truth.astype(np.float32) / 255.0
    source_f = source.astype(np.float32) / 255.0
    difference = pred_f - truth_f
    mse = float(np.mean(difference * difference))
    precision, recall, f1 = tolerant_edge_f1(pred, truth)
    return {
        "mae": float(np.mean(np.abs(difference))),
        "rmse": math.sqrt(mse),
        "psnr_db": float(10.0 * math.log10(1.0 / max(mse, 1e-12))),
        "ssim": float(structural_similarity(pred_f, truth_f, data_range=1.0)),
        "edge_precision": precision,
        "edge_recall": recall,
        "edge_f1": f1,
        "fine_detail_energy_ratio": highpass_energy(pred) / max(highpass_energy(truth), 1e-12),
        "output_vs_source_mae": float(np.mean(np.abs(pred_f - source_f))),
        "target_vs_source_mae": float(np.mean(np.abs(truth_f - source_f))),
    }


def evaluate_internal(config: dict) -> None:
    update_status("internal_test", "running")
    _, rows = audit_internal_test(config)
    package = Path(config["internal_test"]["package_root"])
    module = load_inference_module(config)
    device = config["runtime"]["device"]
    records = []
    for label, item in config["models"].items():
        model, state_key = module.build_model(Path(item["checkpoint"]), device, True)
        if state_key != "ema_state_dict":
            raise RuntimeError(f"{label}: EMA weights were not selected")
        output_root = RECON / "internal_test" / label
        batch_size = 16
        for start in range(0, len(rows), batch_size):
            batch_rows = rows[start:start + batch_size]
            sources = [read_gray(package / row["package_src"]) for row in batch_rows]
            tensor = torch.from_numpy(np.stack(sources).astype(np.float32) / 255.0)[:, None].to(device)
            with torch.no_grad(), torch.cuda.amp.autocast(enabled=str(device).startswith("cuda")):
                predictions = model(tensor).float().clamp(0.0, 1.0)[:, 0].cpu().numpy()
            for row, source, pred_f in zip(batch_rows, sources, predictions):
                pred = np.clip(np.rint(pred_f * 255.0), 0, 255).astype(np.uint8)
                truth = read_gray(package / row["package_lbl"])
                relative = Path(row["package_src"]).relative_to("src")
                write_bmp(output_root / relative, pred)
                records.append({
                    "model": label,
                    "pair_id": row["pair_id"],
                    "geometry_id": row["geometry_id"],
                    "training_role": row["training_role"],
                    "shape_family": row["shape_family"],
                    "degradation_family": row["degradation_family"],
                    "exposure_level": row["exposure_level"],
                    "polarity": row["polarity"],
                    "identity_mode": row["identity_mode"],
                    "source": str(package / row["package_src"]),
                    "truth": str(package / row["package_lbl"]),
                    "output": str((output_root / relative).with_suffix(".bmp")),
                    **internal_metrics_for_image(pred, source, truth),
                })
            print(f"[internal] {label} {min(start + batch_size, len(rows))}/{len(rows)}", flush=True)
        del model
        torch.cuda.empty_cache()
    frame = pd.DataFrame(records)
    TABLES.mkdir(parents=True, exist_ok=True)
    frame.to_csv(TABLES / "internal_test_per_image.csv", index=False)
    summaries = []
    for (label, role), group in frame.groupby(["model", "training_role"]):
        summaries.append({
            "model": label,
            "training_role": role,
            "images": len(group),
            "median_mae": float(group["mae"].median()),
            "p95_mae": float(group["mae"].quantile(0.95)),
            "median_psnr_db": float(group["psnr_db"].median()),
            "median_ssim": float(group["ssim"].median()),
            "median_edge_f1": float(group["edge_f1"].median()),
            "median_fine_detail_energy_ratio": float(group["fine_detail_energy_ratio"].median()),
        })
    for label, group in frame.groupby("model"):
        summaries.append({
            "model": label,
            "training_role": "ALL",
            "images": len(group),
            "median_mae": float(group["mae"].median()),
            "p95_mae": float(group["mae"].quantile(0.95)),
            "median_psnr_db": float(group["psnr_db"].median()),
            "median_ssim": float(group["ssim"].median()),
            "median_edge_f1": float(group["edge_f1"].median()),
            "median_fine_detail_energy_ratio": float(group["fine_detail_energy_ratio"].median()),
        })
    pd.DataFrame(summaries).to_csv(TABLES / "internal_test_summary.csv", index=False)
    update_status("internal_test", "complete", f"{len(frame)} paired model-image measurements")


def edge_image(image: np.ndarray) -> np.ndarray:
    gray = cv2.GaussianBlur(image.astype(np.float32), (0, 0), 1.0)
    gx = cv2.Sobel(gray, cv2.CV_32F, 1, 0, ksize=3)
    gy = cv2.Sobel(gray, cv2.CV_32F, 0, 1, ksize=3)
    edge = cv2.magnitude(gx, gy)
    edge -= float(edge.mean())
    std = float(edge.std())
    return edge / std if std > 1e-6 else edge


def phase_shift(a: np.ndarray, b: np.ndarray) -> tuple[float, float, float]:
    a_edge, b_edge = edge_image(a), edge_image(b)
    window = cv2.createHanningWindow((a.shape[1], a.shape[0]), cv2.CV_32F)
    (dx, dy), response = cv2.phaseCorrelate(a_edge, b_edge, window)
    return float(dx), float(dy), float(response)


def bounded_ecc_shift(a: np.ndarray, b: np.ndarray, initial_dx: float, initial_dy: float) -> tuple[float, float, float]:
    a_float = cv2.GaussianBlur(a.astype(np.float32) / 255.0, (0, 0), 1.0)
    b_float = cv2.GaussianBlur(b.astype(np.float32) / 255.0, (0, 0), 1.0)
    warp = np.array([[1.0, 0.0, initial_dx], [0.0, 1.0, initial_dy]], dtype=np.float32)
    criteria = (cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 60, 1e-6)
    correlation, refined = cv2.findTransformECC(
        a_float, b_float, warp, cv2.MOTION_TRANSLATION, criteria, None, 1
    )
    return float(refined[0, 2]), float(refined[1, 2]), float(correlation)


def as_bool(series: pd.Series) -> pd.Series:
    if series.dtype == bool:
        return series
    return series.astype(str).str.lower().eq("true")


def compute_motion_rows(config: dict, locked: pd.DataFrame, label: str) -> pd.DataFrame:
    records = []
    real = config["real_fov"]
    tile_h = 1536 // int(real["grid_rows"])
    tile_w = 2048 // int(real["grid_columns"])
    recon_root = RECON / "real_tile1024" / label
    for sequence, sequence_rows in locked.groupby("sequence", sort=False):
        paths = image_paths(recon_root / sequence)
        print(f"[motion] {label} {sequence}", flush=True)
        for step_index, step_rows in sequence_rows.groupby("step_index", sort=True):
            index = int(step_index)
            image_a, image_b = read_gray(paths[index]), read_gray(paths[index + 1])
            for _, row in step_rows.iterrows():
                tile_row, tile_column = int(row["tile_row"]), int(row["tile_column"])
                y0, x0 = tile_row * tile_h, tile_column * tile_w
                tile_a = image_a[y0:y0 + tile_h, x0:x0 + tile_w]
                tile_b = image_b[y0:y0 + tile_h, x0:x0 + tile_w]
                phase_dx, phase_dy, response = phase_shift(tile_a, tile_b)
                try:
                    dx, dy, ecc = bounded_ecc_shift(tile_a, tile_b, float(row["raw_dx_px"]), float(row["raw_dy_px"]))
                    ecc_ok = math.isfinite(ecc)
                except cv2.error:
                    dx, dy, ecc, ecc_ok = math.nan, math.nan, math.nan, False
                expected_px = float(row["expected_dx_px"])
                shift_limit = max(12.0, expected_px * 2.5)
                raw_valid = bool(row["raw_reference_valid"])
                evaluable = bool(ecc_ok and ecc >= 0.75 and abs(dx) <= shift_limit and abs(dy) <= shift_limit)
                valid = raw_valid and evaluable
                raw_dx, raw_dy = float(row["raw_dx_px"]), float(row["raw_dy_px"])
                direction = bool(np.sign(raw_dx) == np.sign(dx)) if valid and abs(raw_dx) > 0.05 and abs(dx) > 0.05 else False
                object_um_per_px = float(row["object_um_per_px"])
                difference_um = math.hypot(dx - raw_dx, dy - raw_dy) * object_um_per_px if valid else math.nan
                scale = abs(dx) / max(abs(raw_dx), 1e-9) if valid else math.nan
                records.append({
                    "sequence": sequence,
                    "method": label,
                    "magnification": float(row["magnification"]),
                    "nominal_step_um": float(row["nominal_step_um"]),
                    "object_um_per_px": object_um_per_px,
                    "expected_dx_px": expected_px,
                    "step_index": index,
                    "time_gap_s": row["time_gap_s"],
                    "tile_id": row["tile_id"],
                    "tile_row": tile_row,
                    "tile_column": tile_column,
                    "edge_score": float(row["edge_score"]),
                    "raw_dx_px": raw_dx,
                    "raw_dy_px": raw_dy,
                    "raw_response": float(row["raw_response"]),
                    "model_phase_dx_px": phase_dx,
                    "model_phase_dy_px": phase_dy,
                    "model_response": response,
                    "model_dx_px": dx,
                    "model_dy_px": dy,
                    "model_ecc": ecc,
                    "raw_reference_valid": raw_valid,
                    "model_evaluable": evaluable,
                    "valid": valid,
                    "direction_agreement": direction,
                    "model_over_raw_abs_dx": scale,
                    "vector_difference_um": difference_um,
                })
    return pd.DataFrame(records)


def summarize_motion(table: pd.DataFrame, gates: dict) -> pd.DataFrame:
    summaries = []
    for (sequence, method), group in table.groupby(["sequence", "method"], sort=False):
        reference = group.loc[group["raw_reference_valid"]]
        valid = group.loc[group["valid"]]
        if reference.empty or valid.empty:
            raise RuntimeError(f"{sequence}/{method}: no valid motion measurements")
        response_ratio = valid["model_response"] / valid["raw_response"].clip(lower=1e-9)
        scale = float(valid["model_over_raw_abs_dx"].median())
        row = {
            "sequence": sequence,
            "method": method,
            "magnification": float(group["magnification"].iloc[0]),
            "nominal_step_um": float(group["nominal_step_um"].iloc[0]),
            "selected_tiles": int(group["tile_id"].nunique()),
            "used_steps": int(group["step_index"].nunique()),
            "tile_measurements": int(len(group)),
            "raw_reference_measurements": int(len(reference)),
            "valid_measurements": int(len(valid)),
            "valid_fraction": float(len(valid) / len(reference)),
            "direction_agreement_fraction": float(valid["direction_agreement"].mean()),
            "median_model_over_raw_abs_dx": scale,
            "median_scale_error_fraction": abs(scale - 1.0),
            "median_vector_difference_um": float(valid["vector_difference_um"].median()),
            "p95_vector_difference_um": float(valid["vector_difference_um"].quantile(0.95)),
            "median_difference_of_step": float(valid["vector_difference_um"].median() / valid["nominal_step_um"].iloc[0]),
            "p95_difference_of_step": float(valid["vector_difference_um"].quantile(0.95) / valid["nominal_step_um"].iloc[0]),
            "median_response_ratio": float(response_ratio.median()),
            "median_model_ecc": float(valid["model_ecc"].median()),
        }
        row["pass_valid_fraction"] = row["valid_fraction"] >= gates["minimum_valid_fraction"]
        row["pass_direction"] = row["direction_agreement_fraction"] >= gates["minimum_direction_agreement"]
        row["pass_scale"] = row["median_scale_error_fraction"] <= gates["maximum_median_scale_error_fraction"]
        row["pass_median_difference"] = row["median_difference_of_step"] <= gates["maximum_median_difference_of_step"]
        row["pass_p95_difference"] = row["p95_difference_of_step"] <= gates["maximum_p95_difference_of_step"]
        row["pass_response"] = row["median_response_ratio"] >= gates["minimum_median_response_ratio"]
        row["pass_ecc"] = row["median_model_ecc"] >= gates["minimum_median_ecc"]
        row["sequence_pass"] = all(value for key, value in row.items() if key.startswith("pass_"))
        summaries.append(row)
    return pd.DataFrame(summaries)


def gradient_magnitude(image: np.ndarray) -> np.ndarray:
    smooth = cv2.GaussianBlur(image.astype(np.float32), (0, 0), 1.0)
    gx = cv2.Sobel(smooth, cv2.CV_32F, 1, 0, ksize=3)
    gy = cv2.Sobel(smooth, cv2.CV_32F, 0, 1, ksize=3)
    return cv2.magnitude(gx, gy)


def correlation(a: np.ndarray, b: np.ndarray) -> float:
    a_f = a.astype(np.float64).ravel()
    b_f = b.astype(np.float64).ravel()
    if a_f.std() < 1e-12 or b_f.std() < 1e-12:
        return 1.0 if np.array_equal(a, b) else 0.0
    return float(np.corrcoef(a_f, b_f)[0, 1])


def frame_fidelity(raw: np.ndarray, model: np.ndarray) -> dict:
    return {
        "raw_output_correlation": correlation(raw, model),
        "fine_detail_energy_ratio": highpass_energy(model) / max(highpass_energy(raw), 1e-12),
        "mean_absolute_change": float(np.mean(np.abs(model.astype(np.float32) - raw.astype(np.float32))) / 255.0),
    }


def off_source_metric(raw: np.ndarray, model: np.ndarray, settings: dict) -> dict:
    raw_gradient = gradient_magnitude(raw)
    model_gradient = gradient_magnitude(model)
    raw_threshold = float(np.percentile(raw_gradient, settings["raw_edge_percentile"]))
    raw_support = raw_gradient >= raw_threshold
    distance = cv2.distanceTransform((~raw_support).astype(np.uint8), cv2.DIST_L2, 5)
    model_threshold = float(np.percentile(model_gradient, settings["model_edge_percentile"]))
    strong_model_edge = model_gradient >= model_threshold
    off_source = float(np.mean(distance[strong_model_edge] > float(settings["distance_px"])))
    edge_gain = float(np.median(model_gradient[raw_support]) / max(float(np.median(raw_gradient[raw_support])), 1e-9))
    return {"off_source_strong_edge_fraction": off_source, "edge_gain_on_raw_support": edge_gain}


def evaluate_real(config: dict) -> None:
    update_status("real_fov_analysis", "running")
    item = config["real_fov"]
    locked = pd.read_csv(item["locked_measurements"])
    locked["raw_reference_valid"] = as_bool(locked["raw_reference_valid"])
    motion = pd.concat([compute_motion_rows(config, locked, label) for label in config["models"]], ignore_index=True)
    TABLES.mkdir(parents=True, exist_ok=True)
    motion.to_csv(TABLES / "real_motion_per_tile.csv", index=False)
    summary = summarize_motion(motion, item["motion_gates"])
    summary.to_csv(TABLES / "real_motion_summary.csv", index=False)

    raw_root = Path(item["locked_raw_root"])
    fidelity_rows = []
    artifact_rows = []
    for sequence, sequence_item in item["sequences"].items():
        raw_paths = image_paths(raw_root / sequence)
        frozen_indices = [len(raw_paths) - 1 if index == -1 else int(index) for index in item["artifact_frame_indices"]]
        for label in config["models"]:
            model_paths = image_paths(RECON / "real_tile1024" / label / sequence)
            if [path.name for path in raw_paths] != [path.name for path in model_paths]:
                raise RuntimeError(f"{label}/{sequence}: reconstruction coverage mismatch")
            for index, (raw_path, model_path) in enumerate(zip(raw_paths, model_paths)):
                raw, model = read_gray(raw_path), read_gray(model_path)
                fidelity_rows.append({
                    "sequence": sequence,
                    "magnification": sequence_item["magnification"],
                    "frame_index": index,
                    "method": label,
                    "tile_size": 1024,
                    **frame_fidelity(raw, model),
                })
                if index in frozen_indices:
                    artifact_rows.append({
                        "sequence": sequence,
                        "magnification": sequence_item["magnification"],
                        "frame_index": index,
                        "method": label,
                        "tile_size": 1024,
                        **off_source_metric(raw, model, item["artifact_metric"]),
                    })
    fidelity = pd.DataFrame(fidelity_rows)
    artifact = pd.DataFrame(artifact_rows)
    fidelity.to_csv(TABLES / "real_frame_fidelity.csv", index=False)
    artifact.to_csv(TABLES / "real_artifact_frozen_frames.csv", index=False)

    sensitivity_rows = []
    for sequence in ("5x_0p5um", "5x_1um"):
        raw_paths = image_paths(raw_root / sequence)
        for label in config["models"]:
            settings = {
                1024: RECON / "real_tile1024" / label / sequence,
                512: RECON / "real_5x_tile512" / label / sequence,
            }
            for tile_size, directory in settings.items():
                model_paths = image_paths(directory)
                if [path.name for path in raw_paths] != [path.name for path in model_paths]:
                    raise RuntimeError(f"5x sensitivity coverage mismatch: {label}/{sequence}/{tile_size}")
                for index, (raw_path, model_path) in enumerate(zip(raw_paths, model_paths)):
                    raw, model = read_gray(raw_path), read_gray(model_path)
                    sensitivity_rows.append({
                        "sequence": sequence,
                        "frame_index": index,
                        "method": label,
                        "tile_size": tile_size,
                        **frame_fidelity(raw, model),
                        **off_source_metric(raw, model, item["artifact_metric"]),
                    })
    pd.DataFrame(sensitivity_rows).to_csv(TABLES / "real_5x_tile_sensitivity.csv", index=False)
    update_status("real_fov_analysis", "complete", f"{len(motion)} motion measurements and {len(fidelity)} frame checks")


def external_arm_ready(root: Path, expected_images: int) -> bool:
    primary = root / "results" / "tables" / "primary_contour_metrics.csv"
    sensitivity = root / "results" / "tables" / "acm_sensitivity_metrics.csv"
    if not primary.is_file() or not sensitivity.is_file():
        return False
    primary_frame = pd.read_csv(primary)
    sensitivity_frame = pd.read_csv(sensitivity)
    return (
        len(primary_frame) == expected_images * 3 * 2
        and set(primary_frame["method"]) == {"Raw", "R79E23", "R79E100"}
        and not primary_frame.isna().any().any()
        and set(sensitivity_frame["method"]) == {"Raw", "R79E23", "R79E100"}
        and not sensitivity_frame.isna().any().any()
    )


def prepare_external_acm_arm(config: dict, suite: str, item: dict) -> Path:
    source_config = read_json(Path(item["source_config"]))
    arm = RESULTS / "acm_external" / suite
    arm_config = {
        "experiment_id": f"R80_{suite}_R79E23_vs_R79E100",
        "dataset": {**source_config["dataset"], "root": item["dataset_root"]},
        "acm": {
            **source_config["acm"],
            "iterations": item["iterations"],
            "smooth_factor": item["smooth_factor"],
            "initialization_mode": item["initialization_mode"],
            "seed_radius_fraction": item["seed_radius_fraction"],
        },
    }
    write_json(arm / "config" / "experiment.json", arm_config)
    output_dirs_e23 = {}
    output_dirs_e100 = {}
    for family in source_config["dataset"]["families"]:
        name, stage = family["name"], family["stage"]
        output_dirs_e23[name] = str((RECON / "external" / suite / "R79E23" / stage).resolve())
        output_dirs_e100[name] = str((RECON / "external" / suite / "R79E100" / stage).resolve())
    write_json(arm / "results" / "inference_manifest.json", {
        "suite": suite,
        "methods": ["R79E23", "R79E100"],
        "output_dirs_e23": output_dirs_e23,
        "output_dirs_e100": output_dirs_e100,
    })
    return arm


def run_external_acm(config: dict) -> None:
    update_status("external_acm", "running")
    matlab = config["runtime"]["matlab"]
    script_dir = (ROOT / "scripts").as_posix().replace("'", "''")
    for suite, item in config["external_acm_suites"].items():
        arm = prepare_external_acm_arm(config, suite, item)
        if external_arm_ready(arm, int(item["expected_images"])):
            print(f"[acm] reuse {suite}", flush=True)
            continue
        expression = f"addpath('{script_dir}'); run_acm_multimethod('{arm.as_posix()}')"
        print(f"[acm] {suite}", flush=True)
        subprocess.run([matlab, "-batch", expression], check=True, cwd=ROOT)
        if not external_arm_ready(arm, int(item["expected_images"])):
            raise RuntimeError(f"External ACM output incomplete: {suite}")
    update_status("external_acm", "complete", "R73 and R74 ACM completed for Raw, epoch 23, and epoch 100")


def sem_arm_ready(root: Path, label: str) -> bool:
    primary = root / "results" / "tables" / "primary_contour_metrics.csv"
    sensitivity = root / "results" / "tables" / "acm_sensitivity_metrics.csv"
    if not primary.is_file() or not sensitivity.is_file():
        return False
    primary_frame = pd.read_csv(primary)
    sensitivity_frame = pd.read_csv(sensitivity)
    return (
        len(primary_frame) == 864
        and len(sensitivity_frame) == 648
        and set(primary_frame["method"]) == {"Raw", label}
        and set(sensitivity_frame["method"]) == {"Raw", label}
        and not primary_frame.isna().any().any()
        and not sensitivity_frame.isna().any().any()
    )


def run_sem_acm(config: dict) -> None:
    update_status("sem_acm", "running")
    item = config["sem_acm"]
    matlab = config["runtime"]["matlab"]
    shared = Path(item["shared_acm_script"])
    script_dir = shared.parent.as_posix().replace("'", "''")
    raw_dir = Path(item["raw_input_dir"]).as_posix().replace("'", "''")
    for label in config["models"]:
        arm = RESULTS / "acm_sem" / label
        if sem_arm_ready(arm, label):
            print(f"[sem acm] reuse {label}", flush=True)
            continue
        reconstruction = (RECON / "sem" / label).as_posix().replace("'", "''")
        expression = (
            f"addpath('{script_dir}'); run_acm_extraction('{arm.as_posix()}',"
            f"'{raw_dir}','{reconstruction}','{label}')"
        )
        print(f"[sem acm] {label}", flush=True)
        subprocess.run([matlab, "-batch", expression], check=True, cwd=ROOT)
        if not sem_arm_ready(arm, label):
            raise RuntimeError(f"SEM ACM output incomplete: {label}")
    update_status("sem_acm", "complete", "Both checkpoints completed 36-pillar SEM contour evaluation")


def run_analysis(config: dict) -> None:
    update_status("analysis", "running")
    subprocess.run([config["runtime"]["python"], str(ROOT / "scripts" / "analyze_r80.py")], check=True, cwd=ROOT)
    update_status("analysis", "complete", "Decision, report, tables, and figures generated")


def run_tests(config: dict) -> None:
    update_status("tests", "running")
    subprocess.run(
        [config["runtime"]["python"], "-m", "unittest", "discover", "-s", str(ROOT / "tests"), "-p", "test_*.py", "-v"],
        check=True,
        cwd=ROOT,
    )
    update_status("complete", "complete", "All R80 validation stages and integrity tests passed")


def main() -> int:
    parser = argparse.ArgumentParser(description="R80 R79 epoch 23 versus epoch 100 generalization validation")
    parser.add_argument(
        "--stage",
        choices=("audit", "infer", "internal", "real", "external-acm", "sem-acm", "analysis", "test", "all"),
        default="all",
    )
    args = parser.parse_args()
    config = read_json(CONFIG_PATH)
    for path in (RESULTS, TABLES, RECON, LOGS, ROOT / "reports", ROOT / "tests"):
        path.mkdir(parents=True, exist_ok=True)
    try:
        if args.stage in ("audit", "all"):
            audit_all(config)
        elif not (RESULTS / "input_audit.json").is_file():
            audit_all(config)
        if args.stage in ("infer", "all"):
            infer_all(config)
        if args.stage in ("internal", "all"):
            evaluate_internal(config)
        if args.stage in ("real", "all"):
            evaluate_real(config)
        if args.stage in ("external-acm", "all"):
            run_external_acm(config)
        if args.stage in ("sem-acm", "all"):
            run_sem_acm(config)
        if args.stage in ("analysis", "all"):
            run_analysis(config)
        if args.stage in ("test", "all"):
            run_tests(config)
    except Exception as exc:
        update_status(args.stage, "failed", repr(exc))
        raise
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

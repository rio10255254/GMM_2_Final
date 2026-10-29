from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
import subprocess
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

import cv2
import numpy as np
import pandas as pd
import torch
PROJECT_ROOT = Path(__file__).resolve().parents[3]


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


def update_status(stage: str, state: str, detail: str = "") -> None:
    payload = read_json(STATUS) if STATUS.is_file() else {
        "experiment_id": "R82_R39R40CrossSceneGeneralizationBenchmark",
        "started_at": datetime.now().astimezone().isoformat(),
        "history": [],
    }
    record = {
        "stage": stage,
        "state": state,
        "detail": detail,
        "at": datetime.now().astimezone().isoformat(),
    }
    payload.update({"current_stage": stage, "state": state, "detail": detail, "updated_at": record["at"]})
    payload["history"].append(record)
    write_json(STATUS, payload)


def read_gray(path: Path) -> np.ndarray:
    image = cv2.imdecode(np.fromfile(path, dtype=np.uint8), cv2.IMREAD_GRAYSCALE)
    if image is None:
        raise OSError(path)
    return image


def image_paths(directory: Path) -> list[Path]:
    return sorted(path for path in directory.glob("*.bmp") if path.is_file())


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def audit_models(config: dict) -> dict:
    records = {}
    for label, item in config["models"].items():
        checkpoint = Path(PROJECT_ROOT / item["checkpoint"])
        checkpoint_hash = require_hash(checkpoint, item["checkpoint_sha256"])
        payload = torch.load(checkpoint, map_location="cpu")
        state = payload.get(item["state_key"]) if isinstance(payload, dict) else None
        if not isinstance(state, dict) or not state:
            raise RuntimeError(f"{label}: missing {item['state_key']}")
        if "expected_epoch" in item and int(payload.get("epoch", -1)) != int(item["expected_epoch"]):
            raise RuntimeError(f"{label}: checkpoint epoch changed")
        names = [name[7:] if name.startswith("module.") else name for name in state]
        records[label] = {
            "checkpoint": str(checkpoint.resolve()),
            "checkpoint_sha256": checkpoint_hash,
            "state_key": item["state_key"],
            "parameter_and_buffer_keys": len(names),
            "has_physical_psf": any(name.startswith("physics_layer.") for name in names),
            "has_weak_psf": any(name.startswith("weak_psf_block.") for name in names),
            "has_boundary_adapter": any(name.startswith("boundary_adapter.") for name in names),
            "role": item["role"],
        }
        del payload
    return records


def audit_real(config: dict) -> dict:
    item = config["real_fov"]
    require_hash(Path(PROJECT_ROOT / item["locked_measurements"]), item["locked_measurements_sha256"])
    root = Path(PROJECT_ROOT / item["locked_raw_root"])
    total = 0
    sequences = {}
    hashes: dict[str, list[str]] = defaultdict(list)
    for name, settings in item["sequences"].items():
        paths = image_paths(root / name)
        expected = int(settings["frame_count"])
        if len(paths) != expected or [path.name for path in paths] != [f"frame_{index:04d}.bmp" for index in range(expected)]:
            raise RuntimeError(f"{name}: locked real sequence coverage changed")
        shapes = {tuple(read_gray(path).shape) for path in paths}
        if shapes != {(1536, 2048)}:
            raise RuntimeError(f"{name}: shape changed: {shapes}")
        for path in paths:
            hashes[sha256(path)].append(f"{name}/{path.name}")
        sequences[name] = {"frames": len(paths), "shape": [1536, 2048], **settings}
        total += len(paths)
    if total != int(item["expected_frames"]):
        raise RuntimeError("Real-FOV total changed")
    duplicates = [values for values in hashes.values() if len(values) > 1]
    return {"total_frames": total, "sequences": sequences, "exact_duplicate_groups": duplicates}


def audit_external(config: dict) -> dict:
    result = {}
    global_hashes: dict[str, list[str]] = defaultdict(list)
    for suite, item in config["external_acm_suites"].items():
        require_hash(Path(PROJECT_ROOT / item["manifest"]), item["manifest_sha256"])
        source_config = read_json(Path(PROJECT_ROOT / item["source_config"]))
        root = Path(PROJECT_ROOT / item["dataset_root"])
        count = 0
        for family in source_config["dataset"]["families"]:
            stage = family["stage"]
            expected_names = [f"{index:04d}.bmp" for index in range(source_config["dataset"]["images_per_family"])]
            for kind in ("src", "lbl", "mask"):
                paths = image_paths(root / kind / stage)
                if [path.name for path in paths] != expected_names:
                    raise RuntimeError(f"{suite}/{stage}/{kind}: coverage changed")
            for name in expected_names:
                source = root / "src" / stage / name
                mask = read_gray(root / "mask" / stage / name)
                if source.suffix.lower() != ".bmp" or mask.shape != (512, 512):
                    raise RuntimeError(f"{suite}/{stage}/{name}: shape changed")
                if set(np.unique(mask).tolist()) - {0, 255}:
                    raise RuntimeError(f"{suite}/{stage}/{name}: truth mask is not binary")
                components, _ = cv2.connectedComponents((mask > 0).astype(np.uint8), 8)
                if components != 2:
                    raise RuntimeError(f"{suite}/{stage}/{name}: truth is not one component")
                global_hashes[sha256(source)].append(f"{suite}/{stage}/{name}")
                count += 1
        if count != int(item["expected_images"]):
            raise RuntimeError(f"{suite}: expected {item['expected_images']}, found {count}")
        result[suite] = {
            "images": count,
            "families": len(source_config["dataset"]["families"]),
            "manifest_sha256": item["manifest_sha256"],
            "development_evidence_for": item["development_evidence_for"],
        }
    duplicates = [values for values in global_hashes.values() if len(values) > 1]
    if duplicates:
        raise RuntimeError(f"External ACM suites contain exact duplicate inputs: {duplicates[:3]}")
    result["cross_suite_exact_duplicate_groups"] = 0
    return result


def audit_sem(config: dict) -> dict:
    item = config["sem_acm"]
    require_hash(Path(PROJECT_ROOT / item["ordering_manifest"]), item["ordering_manifest_sha256"])
    ordering = read_json(Path(PROJECT_ROOT / item["ordering_manifest"]))
    if ordering.get("status") != "verified" or int(ordering.get("exact_copy_count", -1)) != 18:
        raise RuntimeError("SEM ordering is not verified")
    mapping = pd.read_csv(str(PROJECT_ROOT / item["ordering_mapping"]))
    if len(mapping) != 36 or mapping["global_pillar_id"].nunique() != 36:
        raise RuntimeError("SEM mapping is incomplete")
    raw = Path(PROJECT_ROOT / item["raw_input_dir"])
    source = Path(item["raw_source_dir"])
    checks = []
    for exposure in item["optical_exposures"]:
        locked = raw / f"{exposure}.bmp"
        original = source / f"{exposure}.bmp"
        if sha256(locked) != sha256(original):
            raise RuntimeError(f"SEM optical input differs from source: {exposure}")
        if read_gray(locked).shape != (821, 821):
            raise RuntimeError(f"SEM optical shape changed: {exposure}")
        checks.append({"exposure": exposure, "sha256": sha256(locked)})
    sem_files = [Path(item["sem_dir"]) / f"P-{index:02d}.tiff" for index in range(1, 10)]
    if not all(path.is_file() for path in sem_files):
        raise FileNotFoundError("SEM truth stack is incomplete")
    return {"optical_exposures": len(checks), "physical_pillars": 36, "sem_truth_files": 9, "ordering_verified": True, "optical_checks": checks}


def audit_junhua(config: dict) -> dict:
    sequences = {}
    global_hashes: dict[str, list[str]] = defaultdict(list)
    for name, item in config["junhua"]["sequences"].items():
        root = Path(PROJECT_ROOT / item["input_dir"])
        paths = sorted(path for path in root.iterdir() if path.suffix.lower() == ".bmp")
        if len(paths) != int(item["source_frames"]):
            raise RuntimeError(f"{name}: source frame count changed")
        selected = paths[int(item["select_start"]): int(item["select_start"]) + int(item["select_step"]) * int(item["selected_frames"]): int(item["select_step"])]
        if len(selected) != int(item["selected_frames"]):
            raise RuntimeError(f"{name}: selected frame count changed")
        for path in selected:
            global_hashes[sha256(path)].append(f"{name}/{path.name}")
        sequences[name] = {
            "source_frames": len(paths),
            "selected_frames": len(selected),
            "first_filename": selected[0].name,
            "last_filename": selected[-1].name,
            "shape": list(read_gray(selected[0]).shape),
            "expected_step_px": item["expected_step_px"],
        }
    duplicates = [values for values in global_hashes.values() if len(values) > 1]
    if duplicates:
        raise RuntimeError(f"JunHua selected inputs contain duplicates: {duplicates[:3]}")
    return {"sequences": sequences, "selected_frames": sum(item["selected_frames"] for item in sequences.values()), "exact_duplicate_groups": 0}


def audit_all(config: dict) -> dict:
    update_status("audit", "running")
    audit = {
        "experiment_id": config["experiment_id"],
        "comparison_lock": config["comparison_lock"],
        "models": audit_models(config),
        "real_fov": audit_real(config),
        "junhua": audit_junhua(config),
        "external_acm_suites": audit_external(config),
        "sem_acm": audit_sem(config),
        "evidence_eligibility": config["evidence_eligibility"],
        "audited_at": datetime.now().astimezone().isoformat(),
    }
    write_json(RESULTS / "input_audit.json", audit)
    update_status("audit", "complete", "All checkpoints, inputs, pairings, and truth mappings passed")
    print(json.dumps({
        "models": len(audit["models"]),
        "real_frames": audit["real_fov"]["total_frames"],
        "junhua_frames": audit["junhua"]["selected_frames"],
        "external_acm_images": sum(value.get("images", 0) for value in audit["external_acm_suites"].values() if isinstance(value, dict)),
        "sem_pillars": audit["sem_acm"]["physical_pillars"],
    }, ensure_ascii=False, indent=2), flush=True)
    return audit


def run_inference(config: dict) -> None:
    update_status("inference", "running")
    script = ROOT / "scripts" / "infer_r82.py"
    datasets = ["real_fov", "junhua", *config["external_acm_suites"].keys(), "sem_acm"]
    for label in config["models"]:
        for dataset in datasets:
            print(f"[dispatch] {label}/{dataset}", flush=True)
            subprocess.run([config["runtime"]["python"], str(script), "--model", label, "--dataset", dataset], check=True, cwd=ROOT)
    update_status("inference", "complete", f"{len(config['models'])} models x {len(datasets)} locked datasets complete")


def as_bool(series: pd.Series) -> pd.Series:
    if series.dtype == bool:
        return series
    return series.astype(str).str.lower().eq("true")


def r80_helpers():
    path = Path(str(PROJECT_ROOT / 'Experiments/R80_R79E23vsE100GeneralizationValidation/scripts/run_r80.py'))
    return load_module(path, "r82_r80_helpers")


def compute_real_motion_rows(config: dict, locked: pd.DataFrame, label: str, helpers) -> pd.DataFrame:
    records = []
    item = config["real_fov"]
    tile_h = 1536 // int(item["grid_rows"])
    tile_w = 2048 // int(item["grid_columns"])
    root = RECON / "real_fov" / label
    for sequence, sequence_rows in locked.groupby("sequence", sort=False):
        paths = image_paths(root / sequence)
        print(f"[real motion] {label} {sequence}", flush=True)
        for step_index, step_rows in sequence_rows.groupby("step_index", sort=True):
            index = int(step_index)
            image_a, image_b = read_gray(paths[index]), read_gray(paths[index + 1])
            for _, row in step_rows.iterrows():
                tile_row, tile_column = int(row["tile_row"]), int(row["tile_column"])
                y0, x0 = tile_row * tile_h, tile_column * tile_w
                tile_a = image_a[y0:y0 + tile_h, x0:x0 + tile_w]
                tile_b = image_b[y0:y0 + tile_h, x0:x0 + tile_w]
                phase_dx, phase_dy, response = helpers.phase_shift(tile_a, tile_b)
                try:
                    dx, dy, ecc = helpers.bounded_ecc_shift(tile_a, tile_b, float(row["raw_dx_px"]), float(row["raw_dy_px"]))
                    ecc_ok = math.isfinite(ecc)
                except cv2.error:
                    dx, dy, ecc, ecc_ok = math.nan, math.nan, math.nan, False
                expected_px = float(row["expected_dx_px"])
                limit = max(12.0, expected_px * 2.5)
                raw_valid = bool(row["raw_reference_valid"])
                evaluable = bool(ecc_ok and ecc >= 0.75 and abs(dx) <= limit and abs(dy) <= limit)
                valid = raw_valid and evaluable
                raw_dx, raw_dy = float(row["raw_dx_px"]), float(row["raw_dy_px"])
                direction = bool(np.sign(raw_dx) == np.sign(dx)) if valid and abs(raw_dx) > 0.05 and abs(dx) > 0.05 else False
                um_per_px = float(row["object_um_per_px"])
                difference_um = math.hypot(dx - raw_dx, dy - raw_dy) * um_per_px if valid else math.nan
                scale = abs(dx) / max(abs(raw_dx), 1e-9) if valid else math.nan
                records.append({
                    "sequence": sequence, "method": label,
                    "magnification": float(row["magnification"]), "nominal_step_um": float(row["nominal_step_um"]),
                    "object_um_per_px": um_per_px, "expected_dx_px": expected_px,
                    "step_index": index, "time_gap_s": row["time_gap_s"], "tile_id": row["tile_id"],
                    "tile_row": tile_row, "tile_column": tile_column, "edge_score": float(row["edge_score"]),
                    "raw_dx_px": raw_dx, "raw_dy_px": raw_dy, "raw_response": float(row["raw_response"]),
                    "model_phase_dx_px": phase_dx, "model_phase_dy_px": phase_dy, "model_response": response,
                    "model_dx_px": dx, "model_dy_px": dy, "model_ecc": ecc,
                    "raw_reference_valid": raw_valid, "model_evaluable": evaluable, "valid": valid,
                    "direction_agreement": direction, "model_over_raw_abs_dx": scale,
                    "vector_difference_um": difference_um,
                })
    return pd.DataFrame(records)


def add_step_stability(summary: pd.DataFrame, motion: pd.DataFrame, locked: pd.DataFrame) -> pd.DataFrame:
    values = []
    raw_valid = locked.loc[as_bool(locked["raw_reference_valid"])].copy()
    for sequence, group in raw_valid.groupby("sequence", sort=False):
        per_step = group.assign(step_um=group["raw_dx_px"] * group["object_um_per_px"]).groupby("step_index")["step_um"].median()
        values.append({"sequence": sequence, "method": "Raw", "step_std_um": float(per_step.std(ddof=1)), "median_signed_step_um": float(per_step.median()), "step_count_for_std": len(per_step)})
    for (sequence, method), group in motion.loc[motion["valid"]].groupby(["sequence", "method"], sort=False):
        step_values = group.assign(step_um=group["model_dx_px"] * group["object_um_per_px"]).groupby("step_index")["step_um"].median()
        values.append({"sequence": sequence, "method": method, "step_std_um": float(step_values.std(ddof=1)), "median_signed_step_um": float(step_values.median()), "step_count_for_std": len(step_values)})
    stability = pd.DataFrame(values)
    stability.to_csv(TABLES / "real_step_stability.csv", index=False)
    model_stability = stability.loc[stability["method"] != "Raw"]
    return summary.merge(model_stability, on=["sequence", "method"], how="left")


def evaluate_real(config: dict) -> None:
    update_status("real_motion", "running")
    helpers = r80_helpers()
    item = config["real_fov"]
    locked = pd.read_csv(str(PROJECT_ROOT / item["locked_measurements"]))
    locked["raw_reference_valid"] = as_bool(locked["raw_reference_valid"])
    motion = pd.concat([compute_real_motion_rows(config, locked, label, helpers) for label in config["models"]], ignore_index=True)
    TABLES.mkdir(parents=True, exist_ok=True)
    motion.to_csv(TABLES / "real_motion_per_tile.csv", index=False)
    summary = helpers.summarize_motion(motion, item["motion_gates"])
    summary = add_step_stability(summary, motion, locked)
    summary.to_csv(TABLES / "real_motion_summary.csv", index=False)

    raw_root = Path(PROJECT_ROOT / item["locked_raw_root"])
    fidelity_rows = []
    artifact_rows = []
    for sequence in item["sequences"]:
        raw_paths = image_paths(raw_root / sequence)
        frozen = [len(raw_paths) - 1 if index == -1 else int(index) for index in item["artifact_frame_indices"]]
        for label in config["models"]:
            model_paths = image_paths(RECON / "real_fov" / label / sequence)
            if [path.name for path in raw_paths] != [path.name for path in model_paths]:
                raise RuntimeError(f"{label}/{sequence}: real coverage mismatch")
            for index, (raw_path, model_path) in enumerate(zip(raw_paths, model_paths)):
                raw, model = read_gray(raw_path), read_gray(model_path)
                fidelity_rows.append({"sequence": sequence, "frame_index": index, "method": label, **helpers.frame_fidelity(raw, model)})
                if index in frozen:
                    artifact_rows.append({"sequence": sequence, "frame_index": index, "method": label, **helpers.off_source_metric(raw, model, item["artifact_metric"])})
    pd.DataFrame(fidelity_rows).to_csv(TABLES / "real_frame_fidelity.csv", index=False)
    pd.DataFrame(artifact_rows).to_csv(TABLES / "real_artifact_frozen_frames.csv", index=False)
    update_status("real_motion", "complete", f"{len(motion)} tile-pair measurements across six sequences")


def selected_junhua_paths(item: dict) -> list[Path]:
    paths = sorted(path for path in Path(PROJECT_ROOT / item["input_dir"]).iterdir() if path.suffix.lower() == ".bmp")
    start, step, count = int(item["select_start"]), int(item["select_step"]), int(item["selected_frames"])
    return paths[start:start + step * count:step]


def center_crop(image: np.ndarray, size: int) -> np.ndarray:
    height, width = image.shape
    crop = min(int(size), height, width)
    y0 = (height - crop) // 2
    x0 = (width - crop) // 2
    return image[y0:y0 + crop, x0:x0 + crop]


def evaluate_junhua(config: dict) -> None:
    update_status("junhua_motion", "running")
    helpers = r80_helpers()
    per_pair = []
    methods = ["Raw", *config["models"].keys()]
    crop_size = int(config["junhua"]["local_evaluator"]["fixed_center_crop_px"])
    for sequence, item in config["junhua"]["sequences"].items():
        raw_paths = selected_junhua_paths(item)
        expected = float(item["expected_step_px"])
        for method in methods:
            paths = raw_paths if method == "Raw" else image_paths(RECON / "junhua" / method / sequence)
            if [path.name for path in raw_paths] != [path.name for path in paths]:
                raise RuntimeError(f"{sequence}/{method}: JunHua coverage mismatch")
            for index, (path_a, path_b) in enumerate(zip(paths[:-1], paths[1:])):
                image_a = center_crop(read_gray(path_a), crop_size)
                image_b = center_crop(read_gray(path_b), crop_size)
                phase_dx, phase_dy, response = helpers.phase_shift(image_a, image_b)
                try:
                    dx, dy, ecc = helpers.bounded_ecc_shift(image_a, image_b, -expected, 0.0)
                    finite = all(math.isfinite(value) for value in (dx, dy, ecc))
                except cv2.error:
                    dx, dy, ecc, finite = math.nan, math.nan, math.nan, False
                limit = max(12.0, expected * 2.5)
                valid = bool(finite and ecc >= 0.75 and abs(dx) <= limit and abs(dy) <= limit)
                per_pair.append({
                    "sequence": sequence, "method": method, "pair_index": index,
                    "expected_signed_step_px": -expected,
                    "phase_dx_px": phase_dx, "phase_dy_px": phase_dy, "phase_response": response,
                    "ecc_dx_px": dx, "ecc_dy_px": dy, "ecc": ecc, "valid": valid,
                    "direction_agreement": bool(valid and dx < 0),
                    "absolute_step_error_px": abs(dx + expected) if valid else math.nan,
                })
            print(f"[JunHua] {sequence}/{method}", flush=True)
    frame = pd.DataFrame(per_pair)
    frame.to_csv(TABLES / "junhua_local_per_pair.csv", index=False)
    rows = []
    for (sequence, method), group in frame.groupby(["sequence", "method"], sort=False):
        valid = group.loc[group["valid"]]
        rows.append({
            "sequence": sequence, "method": method, "pairs": len(group), "valid_pairs": len(valid),
            "valid_fraction": float(len(valid) / len(group)),
            "direction_agreement_fraction": float(valid["direction_agreement"].mean()) if len(valid) else 0.0,
            "median_signed_step_px": float(valid["ecc_dx_px"].median()) if len(valid) else math.nan,
            "step_std_px": float(valid["ecc_dx_px"].std(ddof=1)) if len(valid) > 1 else math.nan,
            "median_absolute_step_error_px": float(valid["absolute_step_error_px"].median()) if len(valid) else math.nan,
            "median_ecc": float(valid["ecc"].median()) if len(valid) else math.nan,
            "median_phase_response": float(valid["phase_response"].median()) if len(valid) else math.nan,
        })
    pd.DataFrame(rows).to_csv(TABLES / "junhua_local_summary.csv", index=False)
    external_rows = []
    for method, source in config["junhua"]["external_gmf"].items():
        if "step_std_px" in source:
            values = source["step_std_px"]
        else:
            payload = read_json(Path(PROJECT_ROOT / source["source_json"]))
            headline = payload["headline_step_std"]
            values = {"pitch8px": headline["8px"], "pitch0p8px": headline["0p8px"], "pitch0p08px": headline["0p08px"]}
        for sequence, value in values.items():
            external_rows.append({"sequence": sequence, "method": method, "external_gmf_step_std_px": float(value)})
    pd.DataFrame(external_rows).to_csv(TABLES / "junhua_external_gmf_summary.csv", index=False)
    update_status("junhua_motion", "complete", f"{len(frame)} local adjacent-pair measurements plus locked external GMF evidence")


def external_arm_ready(arm: Path, expected_images: int, method_count: int) -> bool:
    summary = arm / "results" / "tables" / "acm_extraction_summary.json"
    primary = arm / "results" / "tables" / "primary_contour_metrics.csv"
    sensitivity = arm / "results" / "tables" / "acm_sensitivity_metrics.csv"
    if not (summary.is_file() and primary.is_file() and sensitivity.is_file()):
        return False
    payload = read_json(summary)
    return (
        int(payload.get("primary_row_count", -1)) == expected_images * method_count * 2
        and len(pd.read_csv(primary)) == expected_images * method_count * 2
        and len(pd.read_csv(sensitivity)) == 5 * 3 * 3 * method_count
    )


def prepare_external_arm(config: dict, suite: str, item: dict) -> Path:
    source = read_json(Path(PROJECT_ROOT / item["source_config"]))
    arm = RESULTS / "acm_external" / suite
    acm = dict(source["acm"])
    acm["initialization_mode"] = item["initialization_mode"]
    acm.setdefault("seed_radius_fraction", 0.2)
    arm_config = {"experiment_id": f"R82_{suite}", "dataset": {**source["dataset"], "root": str(PROJECT_ROOT / item["dataset_root"])}, "acm": acm}
    write_json(arm / "config" / "experiment.json", arm_config)
    methods = ["Raw", *config["models"].keys()]
    output_dirs = {}
    for method in methods:
        output_dirs[method] = {}
        for family in source["dataset"]["families"]:
            stage, name = family["stage"], family["name"]
            directory = Path(PROJECT_ROOT / item["dataset_root"]) / "src" / stage if method == "Raw" else RECON / suite / method / stage
            output_dirs[method][name] = str(directory.resolve())
    write_json(arm / "results" / "inference_manifest.json", {"suite": suite, "methods": methods, "output_dirs": output_dirs})
    return arm


def run_external_acm(config: dict) -> None:
    update_status("external_acm", "running")
    script_dir = (ROOT / "scripts").as_posix().replace("'", "''")
    matlab = config["runtime"]["matlab"]
    method_count = 1 + len(config["models"])
    for suite, item in config["external_acm_suites"].items():
        arm = prepare_external_arm(config, suite, item)
        if external_arm_ready(arm, int(item["expected_images"]), method_count):
            print(f"[ACM reuse] {suite}", flush=True)
            continue
        expression = f"addpath('{script_dir}'); run_acm_multimethod('{arm.as_posix()}')"
        print(f"[ACM] {suite}", flush=True)
        subprocess.run([matlab, "-batch", expression], check=True, cwd=ROOT)
        if not external_arm_ready(arm, int(item["expected_images"]), method_count):
            raise RuntimeError(f"Incomplete external ACM: {suite}")
    update_status("external_acm", "complete", "R73 and R74 completed for Raw plus six models")


def sem_acm_ready(config: dict) -> bool:
    root = RESULTS / "acm_sem" / "tables"
    summary = root / "acm_extraction_summary.json"
    if not summary.is_file():
        return False
    methods = 1 + len(config["models"])
    payload = read_json(summary)
    return (
        int(payload.get("primary_record_count", -1)) == 12 * 36 * methods
        and int(payload.get("sensitivity_record_count", -1)) == 3 * 3 * 36 * methods
    )


def run_sem_acm(config: dict) -> None:
    update_status("sem_acm", "running")
    if sem_acm_ready(config):
        print("[SEM ACM reuse] complete", flush=True)
    else:
        script_dir = (ROOT / "scripts").as_posix().replace("'", "''")
        expression = f"addpath('{script_dir}'); run_sem_acm_multimethod('{ROOT.as_posix()}')"
        subprocess.run([config["runtime"]["matlab"], "-batch", expression], check=True, cwd=ROOT)
        if not sem_acm_ready(config):
            raise RuntimeError("Incomplete SEM ACM output")
    update_status("sem_acm", "complete", "36 physical pillars x 12 exposures complete for Raw plus six models")


def run_analysis(config: dict) -> None:
    update_status("analysis", "running")
    subprocess.run([config["runtime"]["python"], str(ROOT / "scripts" / "analyze_r82.py")], check=True, cwd=ROOT)
    update_status("analysis", "complete", "Tables, figures, decision, and report generated")


def run_validation(config: dict) -> None:
    update_status("validation", "running")
    subprocess.run([config["runtime"]["python"], str(ROOT / "scripts" / "validate_r82.py")], check=True, cwd=ROOT)
    update_status("complete", "complete", "All locked validation stages and integrity checks passed")


def main() -> int:
    parser = argparse.ArgumentParser(description="R82 R39/R40 cross-scene benchmark")
    parser.add_argument("--stage", choices=("audit", "infer", "real", "junhua", "external-acm", "sem-acm", "analysis", "validate", "all"), default="all")
    args = parser.parse_args()
    config = read_json(CONFIG_PATH)
    for path in (RESULTS, TABLES, RECON, LOGS, ROOT / "reports"):
        path.mkdir(parents=True, exist_ok=True)
    try:
        if args.stage in ("audit", "all"):
            audit_all(config)
        elif not (RESULTS / "input_audit.json").is_file():
            audit_all(config)
        if args.stage in ("infer", "all"):
            run_inference(config)
        if args.stage in ("real", "all"):
            evaluate_real(config)
        if args.stage in ("junhua", "all"):
            evaluate_junhua(config)
        if args.stage in ("external-acm", "all"):
            run_external_acm(config)
        if args.stage in ("sem-acm", "all"):
            run_sem_acm(config)
        if args.stage in ("analysis", "all"):
            run_analysis(config)
        if args.stage in ("validate", "all"):
            run_validation(config)
    except Exception as exc:
        update_status(args.stage, "failed", repr(exc))
        raise
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

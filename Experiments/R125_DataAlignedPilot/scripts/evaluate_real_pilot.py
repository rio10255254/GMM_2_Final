"""Frozen, bounded real-image evaluation for R125's exploratory data pilot.

All optics remain an explicit diagnostic assumption. These reused real sources
are evaluation-only here; no claimed unseen generalization or stage truth.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import sys
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path

sys.dont_write_bytecode = True
import cv2
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
EXPS = ROOT.parent
R124 = EXPS / "R124_RealFirstPrototype"
R123 = EXPS / "R123_RealFirstModelDesign"
OLD = EXPS / "R119_SequenceGeometryValidation" / "analysis" / "R109_comparison_20260907"
OLD_PRIMARY = EXPS / "R119_SequenceGeometryValidation" / "results" / "formal_sem" / "results" / "masks" / "acm_primary_masks.mat"
PROFILE = R124 / "config" / "gaussian_diagnostic.json"
PANEL = ROOT / "results" / "real_panel" / "frozen_panel.json"
REFS = {"historical": "truth_historical", "global_pitch_matched": "truth_pitch_matched"}


def now():
    return datetime.now(timezone.utc).isoformat()


def sha(path):
    result = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            result.update(block)
    return result.hexdigest()


def record(path):
    path = Path(path).resolve()
    return {"path": str(path), "sha256": sha(path), "bytes": path.stat().st_size}


def save(path, value):
    def plain(item):
        if isinstance(item, dict):
            return {str(k): plain(v) for k, v in item.items()}
        if isinstance(item, (list, tuple)):
            return [plain(v) for v in item]
        if isinstance(item, np.generic):
            item = item.item()
        if isinstance(item, float) and not np.isfinite(item):
            return None
        return item
    with Path(path).open("x", encoding="utf-8") as stream:
        json.dump(plain(value), stream, indent=2, ensure_ascii=False, allow_nan=False)
        stream.write("\n")


def module_from(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def gray(path):
    image = cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)
    if image is None:
        raise OSError(path)
    return image.astype(np.float64) / 255.0


def edge_phase(a, b):
    """R68 edge-magnitude phase correlation; results are relative to Raw only."""
    def edges(image):
        image = cv2.GaussianBlur(image.astype(np.float32), (0, 0), 1.0)
        edge = cv2.magnitude(cv2.Sobel(image, cv2.CV_32F, 1, 0, ksize=3), cv2.Sobel(image, cv2.CV_32F, 0, 1, ksize=3))
        edge -= float(edge.mean())
        std = float(edge.std())
        return edge / std if std > 1e-6 else edge
    window = cv2.createHanningWindow((a.shape[1], a.shape[0]), cv2.CV_32F)
    (dx, dy), response = cv2.phaseCorrelate(edges(a), edges(b), window)
    finite = bool(np.isfinite([dx, dy, response]).all())
    return {"dx_px": float(dx) if finite else None, "dy_px": float(dy) if finite else None,
            "response": float(response) if finite else None, "finite": finite,
            "response_at_least_0p1": bool(finite and response >= 0.1), "reference_role": "Raw-relative consistency; no absolute stage truth"}


def crop(image, box):
    x0, y0, x1, y1 = box
    return image[y0:y1, x0:x1]


def freeze_panel():
    if PANEL.exists():
        panel = json.loads(PANEL.read_text(encoding="utf-8"))
        verify_panel(panel)
        print(f"Existing frozen panel verified, not rewritten: {PANEL}", flush=True)
        return panel
    smoke = module_from(R124 / "scripts" / "run_real_smoke.py", "r124_real_smoke_source_list")
    full = [{"name": name, "source": record(path), "description": description,
             "shape_hw": list(gray(path).shape)} for name, path, description in smoke.SOURCES]
    rois_file = R123 / "config" / "frozen_real_rois.json"
    rois = json.loads(rois_file.read_text(encoding="utf-8"))["rois"]
    first = {}
    for roi in rois:
        first.setdefault(roi["sequence"], roi)
    if len(first) != 6:
        raise ValueError("Expected six fixed motion suites")
    motion = []
    for sequence, roi in first.items():
        paths = [Path(roi["first_raw"]), Path(roi["first_raw"]).with_name("frame_0001.bmp")]
        if sha(paths[0]) != roi["first_raw_sha256"]:
            raise ValueError(f"R123 source hash changed: {sequence}")
        images = [gray(path) for path in paths]
        if images[0].shape != images[1].shape:
            raise ValueError(f"Sequence frame shape changed: {sequence}")
        h, w = images[0].shape
        x0 = int(roi["x0"] + (roi["width"] - 128) // 2)
        y0 = int(roi["y0"] + (roi["height"] - 128) // 2)
        core = [x0, y0, x0 + 128, y0 + 128]
        context = [max(0, x0 - 256), max(0, y0 - 256), min(w, x0 + 384), min(h, y0 + 384)]
        core_local = [core[0] - context[0], core[1] - context[1], core[2] - context[0], core[3] - context[1]]
        if any(crop(image, core).shape != (128, 128) for image in images):
            raise ValueError(f"Invalid frozen core: {sequence}")
        motion.append({"sequence": sequence, "frozen_R123_first_record": roi,
                       "sources": [record(path) for path in paths], "shape_hw": [h, w],
                       "core_xyxy": core, "context_xyxy": context, "core_in_context_xyxy": core_local,
                       "context_halo_requested": 256, "core_size": 128,
                       "raw_edge_phase": edge_phase(crop(images[0], core), crop(images[1], core))})
    panel = {"status": "frozen_before_R125_model_outputs", "frozen_utc": now(), "version": 1,
             "purpose": "Exploratory data-admission and end-to-end first pilot, not the full R123 comparison",
             "selection": "Six immutable R124 real previews; first existing R123 Raw-selected ROI record per suite, first two frames, center128 core, halo256",
             "real_training_inputs": False, "unseen_holdout": False, "full301_or364_evaluation": False,
             "calibration_qualified": False, "uncertainty_calibrated": False, "absolute_stage_truth_available": False,
             "profile": record(PROFILE), "R123_roi_manifest": record(rois_file),
             "source_list": record(R124 / "scripts" / "run_real_smoke.py"),
             "full_images": full, "motion_pairs": motion,
             "sem_contract": {"exposures": [13, 24], "physical_objects": 36, "references": list(REFS),
                              "normals_per_object": 720, "readout": "Archived half-contrast, fixed Raw alignment and plateaus",
                              "per_checkpoint_population": "Raw AND candidate", "aggregate_population": "Raw AND every requested checkpoint",
                              "floor_active": "Retained in archived metrics; separate no-floor common-population sensitivity"},
             "motion_contract": {"method": "R68 Gaussian1/Sobel-magnitude standardized edge phase correlation with Hanning window",
                                 "domain": "Fixed native128 core, extracted after context-image inference",
                                 "population": "All six preselected pairs; failures and low responses retained, no result-dependent replacement"}}
    PANEL.parent.mkdir(parents=True, exist_ok=False)
    save(PANEL, panel)
    print(f"Frozen six full images and six two-frame motion pairs: {PANEL}", flush=True)
    return panel


def verify_panel(panel):
    files = [panel["profile"], panel["R123_roi_manifest"], panel["source_list"]]
    files += [item["source"] for item in panel["full_images"]]
    files += [source for item in panel["motion_pairs"] for source in item["sources"]]
    for item in files:
        if sha(item["path"]) != item["sha256"]:
            raise ValueError(f"Frozen panel source changed: {item['path']}")
    return files


def output_dir(path):
    path = Path(path).resolve()
    relative = path.relative_to(ROOT / "results")
    if not relative.parts or not relative.parts[0].startswith("real_"):
        raise ValueError("Outputs must be inside R125/results/real_*; existing directories are refused")
    path.mkdir(parents=True, exist_ok=False)
    return path


def stat(values, mask, op=np.mean):
    return float(op(values[mask])) if mask.any() else None


def model_tensor_hash(state):
    digest = hashlib.sha256()
    for name, tensor in sorted(state.items()):
        digest.update(name.encode())
        digest.update(str(tuple(tensor.shape)).encode())
        digest.update(str(tensor.dtype).encode())
        digest.update(tensor.detach().cpu().contiguous().numpy().tobytes())
    return digest.hexdigest()


def sem_evaluate(images, out):
    """Fixed archived readout; independent interpolation and saved arrays retained."""
    from scipy.io import loadmat
    from scipy.ndimage import distance_transform_edt, map_coordinates
    helper = module_from(R124 / "scripts" / "measure_sem_smoke.py", "r124_sem_pure_helpers")
    readout = module_from(OLD / "profiles.py", "r119_sem_frozen_readout")
    source_paths = [OLD_PRIMARY, OLD / "acm_arrays.mat", OLD / "acm_measurements.csv", OLD / "profile_measurements.csv",
                    R124 / "scripts" / "measure_sem_smoke.py", OLD / "profiles.py"]
    source_paths += [OLD / "profile_arrays" / f"{ref}_p{pid:02d}_e{exposure}.npz"
                     for ref in REFS for pid in range(1, 37) for exposure in (13, 24)]
    sources = [record(path) for path in source_paths]
    mask_data = loadmat(OLD / "acm_arrays.mat", variable_names=list(REFS.values()))
    geometry = loadmat(OLD_PRIMARY, variable_names=["global_index", "opt_centers"])
    alignment = pd.read_csv(OLD / "acm_measurements.csv")
    alignment = alignment[(alignment.method == "Raw") & alignment.exposure.isin([13, 24])].set_index(["reference", "exposure", "pillar"], verify_integrity=True)
    historical = pd.read_csv(OLD / "profile_measurements.csv")
    historical = historical[(historical.method == "Raw") & (historical.readout == "half") & historical.exposure.isin([13, 24])].set_index(["reference", "exposure", "pillar"], verify_integrity=True)
    centers = {int(geometry["global_index"][r, c]): np.floor(geometry["opt_centers"][r * 6 + c] + 0.5).astype(int) - 1 for r in range(6) for c in range(6)}
    yy, xx = np.mgrid[:104, :104]
    radius = np.hypot(xx - 51.5, yy - 51.5)
    directory = out / "sem"
    directory.mkdir()
    (directory / "arrays").mkdir()
    rows, parity, floor_rows = [], [], []
    ordinary_max = 0.0
    accounting_max = 0.0
    for reference, mask_key in REFS.items():
        for pillar in range(1, 37):
            mask = mask_data[mask_key][:, :, pillar - 1].astype(bool)
            coords, targets = readout.geometry_profiles(mask)
            target, target_valid = targets["half"]
            inside = distance_transform_edt(mask) > 8
            outside = (distance_transform_edt(~mask) > 8) & (radius < 50)
            for exposure in (13, 24):
                key = (reference, exposure, pillar)
                fixed, previous_row = alignment.loc[key], historical.loc[key]
                offset = np.array([int(fixed.raw_offset_y), int(fixed.raw_offset_x)])
                if not np.array_equal(offset, [int(previous_row.raw_offset_y), int(previous_row.raw_offset_x)]):
                    raise ValueError(f"Archived alignment disagreement: {key}")
                shifted = coords + (offset + 12)[:, None, None]
                cx, cy = centers[pillar]
                crops = {method: images[exposure, method][cy - 64:cy + 64, cx - 64:cx + 64] for method in ("Raw", "candidate")}
                if any(value.shape != (128, 128) for value in crops.values()):
                    raise ValueError("SEM crop is outside fixed source image")
                raw104 = crops["Raw"][12:-12, 12:-12]
                low, high = np.median(raw104[inside]), np.median(raw104[outside])
                if not high > low:
                    raise ValueError(f"Frozen Raw plateau contract fails: {key}")
                result, arrays, failure_counts = {}, {}, {}
                for method in ("Raw", "candidate"):
                    normalized = (map_coordinates(crops[method], shifted, order=1, mode="nearest") - low) / (high - low)
                    position, valid = readout.crossing(normalized)
                    alternative, alt_valid = helper.independent_crossing(normalized, readout.T)
                    if not np.array_equal(valid, alt_valid):
                        raise ValueError(f"Independent crossing validity differs: {key}/{method}")
                    hit = ((normalized[:, :-1] < .5) & (normalized[:, 1:] >= .5)).argmax(1)
                    increment = normalized[np.arange(720), hit + 1] - normalized[np.arange(720), hit]
                    floor = valid & (increment < 1e-12)
                    ordinary = valid & ~floor
                    if ordinary.any():
                        delta = float(np.max(np.abs(position[ordinary] - alternative[ordinary])))
                        ordinary_max = max(ordinary_max, delta)
                        if delta > 1e-10:
                            raise ValueError(f"Independent ordinary-interval mismatch: {key}/{method}")
                    for index in np.flatnonzero(floor):
                        floor_rows.append({"reference": reference, "exposure": exposure, "pillar": pillar, "method": method,
                                           "normal": int(index), "increment": float(increment[index]),
                                           "archived_position_px": float(position[index]), "unfloored_position_px": float(alternative[index]),
                                           "difference_px": float(abs(position[index] - alternative[index])), "retained_in_original_metrics": True})
                    error, valid = position - target, valid & target_valid
                    result[method] = error, valid, floor
                    failure_counts[method] = helper.failure_counts(normalized, valid)
                    arrays.update({f"{method}_error": error, f"{method}_valid": valid, f"{method}_floor": floor})
                raw_error, raw_valid, raw_floor = result["Raw"]
                with np.load(OLD / "profile_arrays" / f"{reference}_p{pillar:02d}_e{exposure}.npz") as previous:
                    if not np.array_equal(previous["Raw_half_valid"], raw_valid):
                        raise ValueError(f"Raw validity replay failed: {key}")
                    delta = float(np.max(np.abs(previous["Raw_half_error"][raw_valid] - raw_error[raw_valid]))) if raw_valid.any() else 0.0
                table_delta = abs(np.abs(raw_error[raw_valid]).mean() - previous_row.mean_absolute_error_px)
                if max(delta, table_delta) > 1e-10:
                    raise ValueError(f"Raw numeric replay failed: {key}")
                parity.append({"reference": reference, "exposure": exposure, "pillar": pillar,
                               "validity_equal": True, "max_normal_difference_px": delta, "table_mae_difference_px": table_delta})
                common = result["Raw"][1] & result["candidate"][1]
                strict = common & ~raw_floor & ~result["candidate"][2]
                arrays.update(common=common, strict_common=strict)
                array_path = directory / "arrays" / f"{reference}_p{pillar:02d}_e{exposure}.npz"
                np.savez_compressed(array_path, **arrays)
                for method in ("Raw", "candidate"):
                    error, valid, floor = result[method]
                    row = {"reference": reference, "exposure": exposure, "pillar": pillar, "method": method,
                           "valid_profiles": int(valid.sum()), "invalid_profiles": int((~valid).sum()), "common_profiles": int(common.sum()),
                           "floor_active_profiles": int(floor.sum()), "strict_common_profiles": int(strict.sum()),
                           "own_mae_px": stat(np.abs(error), valid), "common_mae_px": stat(np.abs(error), common),
                           "common_signed_median_px": stat(error, common, np.median), "common_max_abs_px": stat(np.abs(error), common, np.max),
                           "strict_common_mae_px": stat(np.abs(error), strict),
                           "common_mae_change_vs_Raw_px": stat(np.abs(error) - np.abs(raw_error), common),
                           "raw_offset_y": int(offset[0]), "raw_offset_x": int(offset[1])}
                    row.update({f"failure_{reason}": count for reason, count in failure_counts[method].items() if reason != "valid"})
                    rows.append(row)
                with np.load(array_path) as check:
                    if not np.array_equal(check["common"], check["Raw_valid"] & check["candidate_valid"]):
                        raise ValueError("Saved shared population changed")
                    for row in rows[-2:]:
                        if common.any():
                            accounting_max = max(accounting_max, abs(np.abs(check[f"{row['method']}_error"])[common].mean() - row["common_mae_px"]))
        print(f"SEM readout complete: {reference}", flush=True)
    frame = pd.DataFrame(rows)
    failed_columns = [column for column in frame if column.startswith("failure_")]
    frame[failed_columns] = frame[failed_columns].fillna(0).astype(int)
    frame.to_csv(directory / "per_pillar.csv", index=False, mode="x")
    pd.DataFrame(parity).to_csv(directory / "raw_parity.csv", index=False, mode="x")
    pd.DataFrame(floor_rows, columns=["reference", "exposure", "pillar", "method", "normal", "increment", "archived_position_px", "unfloored_position_px", "difference_px", "retained_in_original_metrics"]).to_csv(directory / "floor_active.csv", index=False, mode="x")
    summary = {"rows": len(rows), "raw_parity_cases": len(parity), "max_raw_normal_parity_px": max(row["max_normal_difference_px"] for row in parity),
               "max_raw_table_parity_px": max(row["table_mae_difference_px"] for row in parity), "independent_ordinary_interval_max_px": ordinary_max,
               "saved_array_accounting_max_px": accounting_max, "floor_active_crossings": len(floor_rows),
               "common_population": "Raw AND this candidate", "full_ACM": False, "physical_accuracy_qualified": False}
    for item in sources:
        if sha(item["path"]) != item["sha256"]:
            raise ValueError(f"SEM evidence source changed: {item['path']}")
    save(directory / "verification.json", dict(summary, protected_sources=sources, protected_sources_unchanged=True))
    return summary


def evaluate(checkpoint_path, output, device_arg):
    import torch
    out = output_dir(output)
    started = time.perf_counter()
    try:
        panel = json.loads(PANEL.read_text(encoding="utf-8"))
        sources = verify_panel(panel)
        checkpoint_path = checkpoint_path.resolve()
        sources += [record(PANEL), record(checkpoint_path), record(Path(__file__))]
        sources += [record(path) for name in ("model", "inference") for path in sorted((R124 / name).glob("*.py"))]
        save(out / "protected_sources_before.json", sources)
        checkpoint = torch.load(checkpoint_path, map_location="cpu", weights_only=False)
        required = {"model_state", "model_config", "arm", "step", "training_source_manifest_sha256"}
        if not required.issubset(checkpoint):
            raise ValueError(f"Missing checkpoint fields: {required - checkpoint.keys()}")
        seed = checkpoint.get("model_seed", checkpoint.get("seed"))
        if seed is None or ("model_seed" in checkpoint and "seed" in checkpoint and checkpoint["model_seed"] != checkpoint["seed"]):
            raise ValueError("Missing or conflicting checkpoint seed")
        if checkpoint.get("calibration_qualified", False) is not False:
            raise ValueError("A pilot checkpoint cannot qualify instrument calibration")
        device = torch.device("cuda" if device_arg == "auto" and torch.cuda.is_available() else "cpu" if device_arg == "auto" else device_arg)
        torch.set_num_threads(min(8, torch.get_num_threads()))
        if device.type == "cuda":
            torch.backends.cudnn.benchmark = False
            torch.backends.cudnn.deterministic = True
        sys.path.insert(0, str(R124))
        from model.calibration import load_observation
        from model.network import build_model
        from inference.tiling import tiled_forward
        observation = load_observation(PROFILE, device="cpu")
        model = build_model(checkpoint["model_config"], observation=observation)
        expected = {name: value for name, value in model.state_dict().items() if not name.startswith("observation.")}
        learned = {name: value for name, value in checkpoint["model_state"].items() if not name.startswith("observation.")}
        if set(expected) != set(learned):
            raise ValueError(f"Learned state names differ: missing={set(expected)-set(learned)}, extra={set(learned)-set(expected)}")
        for name, value in learned.items():
            if not isinstance(value, torch.Tensor) or value.shape != expected[name].shape or value.dtype != expected[name].dtype:
                raise ValueError(f"Checkpoint tensor contract differs: {name}")
        observation_before = {name: value.clone() for name, value in model.observation.state_dict().items() if isinstance(value, torch.Tensor)}
        loaded = model.load_state_dict(learned, strict=False)
        if loaded.unexpected_keys or set(loaded.missing_keys) != {name for name in model.state_dict() if name.startswith("observation.")}:
            raise ValueError("Unexpected checkpoint loading omission")
        if any(not torch.equal(model.state_dict()[name], value) for name, value in learned.items()):
            raise ValueError("Learned tensors do not exactly reproduce checkpoint")
        if any(not torch.equal(model.observation.state_dict()[name], value) for name, value in observation_before.items()):
            raise ValueError("Training observation state replaced frozen real diagnostic optics")
        model = model.to(device).eval()
        halo = int(model.required_halo)
        identity = {"checkpoint": record(checkpoint_path), "arm": checkpoint["arm"], "seed": int(seed), "step": int(checkpoint["step"]),
                    "training_source_manifest_sha256": checkpoint["training_source_manifest_sha256"], "model_config": checkpoint["model_config"],
                    "learned_tensor_sha256": model_tensor_hash(learned), "learned_state_names": sorted(learned),
                    "excluded_checkpoint_observation_keys": sorted(name for name in checkpoint["model_state"] if name.startswith("observation.")),
                    "observation_rebound": record(PROFILE), "observation_rebind_reason": "Explicit fixed diagnostic Gaussian for all real evaluation, never last training kernel",
                    "calibration_qualified": False, "uncertainty_calibrated": False, "network_untrained": int(checkpoint["step"]) == 0,
                    "device": str(device), "required_halo": halo, "panel_sha256": sha(PANEL)}
        save(out / "checkpoint_binding.json", identity)
        output_records, sem_images, motion_rows = [], {}, []
        def infer(array, destination, metadata):
            destination.mkdir(parents=True, exist_ok=False)
            raw = torch.from_numpy(array.astype(np.float32))[None, None].to(device)
            if device.type == "cuda":
                torch.cuda.synchronize(device)
            then = time.perf_counter()
            with torch.inference_mode():
                native = tiled_forward(model, raw, core=256, halo=halo)
            if device.type == "cuda":
                torch.cuda.synchronize(device)
            native = native[0, 0].cpu().numpy().astype(np.float32, copy=False)
            if native.shape != array.shape or not np.isfinite(native).all():
                raise ValueError("Native inference contract failed")
            np.savez_compressed(destination / "output_float.npz", output=native)
            display = np.rint(np.clip(native, 0, 1) * 255).astype(np.uint8)
            if not cv2.imwrite(str(destination / "output_uint8.png"), display):
                raise IOError(destination / "output_uint8.png")
            delta = np.abs(native.astype(float) - array) * 255
            entry = dict(metadata, shape_hw=list(native.shape), seconds=time.perf_counter()-then,
                         mean_absolute_gray_change=float(delta.mean()), p95_absolute_gray_change=float(np.percentile(delta, 95)),
                         max_absolute_gray_change=float(delta.max()), output_float=record(destination / "output_float.npz"),
                         calibration_qualified=False, uncertainty_calibrated=False, interpretation="Modification readout, not quality improvement")
            save(destination / "metadata.json", entry)
            output_records.append(entry)
            return native.astype(float)
        for item in panel["full_images"]:
            raw = gray(item["source"]["path"])
            prediction = infer(raw, out / "full_images" / item["name"], {"source": item["source"], "name": item["name"]})
            for exposure in (13, 24):
                if item["name"] == f"sem_optical_exposure{exposure}":
                    sem_images[exposure, "Raw"] = raw
                    sem_images[exposure, "candidate"] = prediction
            print(f"Saved full-image output: {item['name']}", flush=True)
        for item in panel["motion_pairs"]:
            core, context = item["core_xyxy"], item["context_xyxy"]
            h, w = item["shape_hw"]
            margins = [core[0]-context[0], core[1]-context[1], context[2]-core[2], context[3]-core[3]]
            physical = [context[0] == 0, context[1] == 0, context[2] == w, context[3] == h]
            if any(margin < halo and not is_physical for margin, is_physical in zip(margins, physical)):
                raise ValueError("Frozen context is too small for checkpoint architecture")
            outputs, raw_cores = [], []
            for frame_index, source in enumerate(item["sources"]):
                raw = gray(source["path"])
                raw_cores.append(crop(raw, core))
                prediction = infer(crop(raw, context), out / "motion" / item["sequence"] / f"frame{frame_index}",
                                   {"source": source, "sequence": item["sequence"], "context_xyxy": context, "core_xyxy": core,
                                    "core_in_context_xyxy": item["core_in_context_xyxy"]})
                outputs.append(crop(prediction, item["core_in_context_xyxy"]))
            raw_shift, candidate_shift = edge_phase(*raw_cores), edge_phase(*outputs)
            if raw_shift != item["raw_edge_phase"]:
                raise ValueError(f"Frozen Raw motion replay changed: {item['sequence']}")
            row = {"sequence": item["sequence"], "raw": raw_shift, "candidate": candidate_shift,
                   "candidate_minus_Raw_dx_px": candidate_shift["dx_px"]-raw_shift["dx_px"] if raw_shift["finite"] and candidate_shift["finite"] else None,
                   "candidate_minus_Raw_dy_px": candidate_shift["dy_px"]-raw_shift["dy_px"] if raw_shift["finite"] and candidate_shift["finite"] else None,
                   "population_fixed_before_outputs": True, "absolute_stage_accuracy_evaluated": False}
            if row["candidate_minus_Raw_dx_px"] is not None:
                row["candidate_minus_Raw_vector_px"] = float(np.hypot(row["candidate_minus_Raw_dx_px"], row["candidate_minus_Raw_dy_px"]))
            else:
                row["candidate_minus_Raw_vector_px"] = None
            motion_rows.append(row)
            print(f"Saved fixed context pair: {item['sequence']}", flush=True)
        save(out / "motion_measurements.json", motion_rows)
        sem_summary = sem_evaluate(sem_images, out)
        for item in sources:
            if sha(item["path"]) != item["sha256"]:
                raise ValueError(f"Protected evaluation input changed: {item['path']}")
        save(out / "summary.json", {"status": "bounded_real_pilot_evaluation_complete", "completed_utc": now(), "seconds": time.perf_counter()-started,
                                    "checkpoint_identity": identity, "full_image_outputs": 6, "motion_context_outputs": 12,
                                    "output_records": output_records, "sem": sem_summary, "motion": motion_rows,
                                    "protected_sources_unchanged": True, "calibration_qualified": False, "uncertainty_calibrated": False,
                                    "full_ACM": False, "new_holdout": False, "scientific_promotion": False})
        print(f"Completed bounded real pilot evaluation: {out}", flush=True)
    except BaseException as error:
        save(out / "failure.json", {"status": "failed", "utc": now(), "error": str(error), "traceback": traceback.format_exc()})
        raise


def aggregate(input_directories, output):
    out = output_dir(output)
    try:
        panel = json.loads(PANEL.read_text(encoding="utf-8"))
        verify_panel(panel)
        evaluations = {}
        protected = [record(PANEL), record(Path(__file__))]
        for directory in input_directories:
            directory = directory.resolve()
            summary_path = directory / "summary.json"
            summary = json.loads(summary_path.read_text(encoding="utf-8"))
            if summary["status"] != "bounded_real_pilot_evaluation_complete":
                raise ValueError(f"Incomplete input evaluation: {directory}")
            ident = summary["checkpoint_identity"]
            key = (ident["arm"], ident["seed"], ident["step"])
            if key in evaluations or ident["panel_sha256"] != sha(PANEL) or ident["observation_rebound"]["sha256"] != sha(PROFILE):
                raise ValueError("Duplicate checkpoint identity or inconsistent real panel/assumed observation")
            evaluations[key] = {"directory": directory, "summary": summary, "identity": ident}
            protected.append(record(summary_path))
        combinations = {(arm, seed) for arm, seed, step in evaluations}
        if len(evaluations) != 12 or len(combinations) != 6 or {arm for arm, _ in combinations} != {"A", "B", "C"}:
            raise ValueError("Final aggregation requires all three arms, two seeds, each initial and step64 separately (12 evaluations)")
        if any({step for a, s, step in evaluations if (a, s) == pair} != {0, 64} for pair in combinations):
            raise ValueError("Every arm/seed requires its own step0 and step64 evaluation")
        for arm, seed in combinations:
            initial, final = evaluations[arm, seed, 0]["identity"], evaluations[arm, seed, 64]["identity"]
            if initial["model_config"] != final["model_config"]:
                raise ValueError("Model configuration changed between paired initial/final evaluation")
        save(out / "population_contract.json", {
            "frozen_panel_sha256": sha(PANEL), "evaluations": [item["identity"] for _, item in sorted(evaluations.items())],
            "primary_shared_population": "Per SEM reference/exposure/object: Raw AND all12 evaluated checkpoints, retained even if sparse/empty",
            "sensitivity_population": "Primary shared population excluding any Raw or candidate floor-active crossing",
            "comparisons": "Each checkpoint vs Raw and each arm/seed vs its own step0, on the exact same all12 shared normals",
            "motion": "Same six fixed core pairs; candidate-minus-Raw and step64-minus-own-step0 changes; no absolute commanded-motion score",
            "interpretation": "Exploratory first data-pipeline pilot; not the complete R123 study, not promotion"})
        rows, coverage, accounting = [], [], []
        ordered_keys = sorted(evaluations)
        for reference in REFS:
            for exposure in (13, 24):
                for pillar in range(1, 37):
                    values = {}
                    raw = None
                    raw_valid = None
                    raw_floor = None
                    for key in ordered_keys:
                        path = evaluations[key]["directory"] / "sem" / "arrays" / f"{reference}_p{pillar:02d}_e{exposure}.npz"
                        protected.append(record(path))
                        with np.load(path) as arrays:
                            current_raw, current_valid, current_floor = arrays["Raw_error"], arrays["Raw_valid"], arrays["Raw_floor"]
                            if raw is None:
                                raw, raw_valid, raw_floor = current_raw.copy(), current_valid.copy(), current_floor.copy()
                            elif not np.array_equal(raw, current_raw, equal_nan=True) or not np.array_equal(raw_valid, current_valid) or not np.array_equal(raw_floor, current_floor):
                                raise ValueError("Raw readout changed between checkpoint evaluations")
                            values[key] = (arrays["candidate_error"].copy(), arrays["candidate_valid"].copy(), arrays["candidate_floor"].copy())
                    common = raw_valid & np.logical_and.reduce([values[key][1] for key in ordered_keys])
                    strict = common & ~raw_floor & ~np.logical_or.reduce([values[key][2] for key in ordered_keys])
                    coverage.append({"reference": reference, "exposure": exposure, "pillar": pillar, "total_profiles": 720,
                                     "raw_valid": int(raw_valid.sum()), "all12_common": int(common.sum()), "strict_common": int(strict.sum()),
                                     "empty_common": not common.any(), "below90pct_common": int(common.sum()) < 648})
                    raw_mae = stat(np.abs(raw), common)
                    for key in ordered_keys:
                        arm, seed, step = key
                        error, valid, floor = values[key]
                        initial_error = values[arm, seed, 0][0]
                        row = {"reference": reference, "exposure": exposure, "pillar": pillar, "arm": arm, "seed": seed, "step": step,
                               "own_valid_profiles": int(valid.sum()), "common_profiles": int(common.sum()), "strict_common_profiles": int(strict.sum()),
                               "floor_active_profiles": int(floor.sum()), "raw_common_mae_px": raw_mae,
                               "common_mae_px": stat(np.abs(error), common), "common_median_signed_px": stat(error, common, np.median),
                               "common_p95_abs_px": stat(np.abs(error), common, lambda x: np.percentile(x, 95)),
                               "common_max_abs_px": stat(np.abs(error), common, np.max),
                               "common_mae_change_vs_Raw_px": stat(np.abs(error)-np.abs(raw), common),
                               "common_mae_change_vs_own_step0_px": stat(np.abs(error)-np.abs(initial_error), common),
                               "strict_common_mae_px": stat(np.abs(error), strict)}
                        if common.any():
                            difference = abs(row["common_mae_change_vs_own_step0_px"] - (row["common_mae_px"] - np.abs(initial_error[common]).mean()))
                            if difference > 1e-12:
                                raise ValueError("Independent aggregate paired-mean accounting failed")
                            accounting.append(difference)
                        rows.append(row)
        frame = pd.DataFrame(rows)
        frame.to_csv(out / "all12_common_sem_per_pillar.csv", index=False, mode="x")
        pd.DataFrame(coverage).to_csv(out / "all12_common_coverage.csv", index=False, mode="x")
        summaries = []
        for (arm, seed, step, reference, exposure), subset in frame.groupby(["arm", "seed", "step", "reference", "exposure"], sort=False):
            summaries.append({"arm": arm, "seed": int(seed), "step": int(step), "reference": reference, "exposure": int(exposure),
                              "physical_objects": int(len(subset)), "objects_with_nonempty_common": int(subset.common_mae_px.notna().sum()),
                              "minimum_common_profiles": int(subset.common_profiles.min()), "total_common_profiles": int(subset.common_profiles.sum()),
                              "median_pillar_common_mae_px": subset.common_mae_px.median(),
                              "median_pillar_Raw_mae_px": subset.raw_common_mae_px.median(),
                              "median_pillar_change_vs_Raw_px": subset.common_mae_change_vs_Raw_px.median(),
                              "median_pillar_change_vs_own_step0_px": subset.common_mae_change_vs_own_step0_px.median(),
                              "worst_pillar_common_mae_px": subset.common_mae_px.max(), "worst_normal_abs_px": subset.common_max_abs_px.max(),
                              "median_pillar_strict_common_mae_px": subset.strict_common_mae_px.median()})
        pd.DataFrame(summaries).to_csv(out / "sem_exposure_comparison.csv", index=False, mode="x")
        motion = []
        for key in ordered_keys:
            arm, seed, step = key
            initial = {item["sequence"]: item for item in evaluations[arm, seed, 0]["summary"]["motion"]}
            for item in evaluations[key]["summary"]["motion"]:
                first = initial[item["sequence"]]
                if item["raw"] != first["raw"]:
                    raise ValueError("Raw motion reference changed between paired checkpoints")
                dx = item["candidate"]["dx_px"]-first["candidate"]["dx_px"] if item["candidate"]["finite"] and first["candidate"]["finite"] else None
                dy = item["candidate"]["dy_px"]-first["candidate"]["dy_px"] if dx is not None else None
                motion.append({"arm": arm, "seed": seed, "step": step, "sequence": item["sequence"],
                               "Raw_phase_response": item["raw"]["response"], "candidate_phase_response": item["candidate"]["response"],
                               "Raw_response_at_least0p1": item["raw"]["response_at_least_0p1"],
                               "candidate_response_at_least0p1": item["candidate"]["response_at_least_0p1"],
                               "candidate_minus_Raw_dx_px": item["candidate_minus_Raw_dx_px"],
                               "candidate_minus_Raw_dy_px": item["candidate_minus_Raw_dy_px"],
                               "candidate_minus_Raw_vector_px": item["candidate_minus_Raw_vector_px"],
                               "change_from_own_step0_dx_px": dx, "change_from_own_step0_dy_px": dy,
                               "change_from_own_step0_vector_px": float(np.hypot(dx, dy)) if dx is not None else None,
                               "absolute_stage_accuracy_evaluated": False})
        pd.DataFrame(motion).to_csv(out / "motion_comparison.csv", index=False, mode="x")
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        chart, axes = plt.subplots(2, 2, figsize=(11, 8))
        comparison = pd.DataFrame(summaries)
        colors = {"A": "#32638a", "B": "#d98b27", "C": "#6b8b3d"}
        for r, reference in enumerate(REFS):
            for c, exposure in enumerate((13, 24)):
                axis = axes[r, c]
                for arm, seed in sorted(combinations):
                    subset = comparison[(comparison.arm == arm) & (comparison.seed == seed) & (comparison.reference == reference) & (comparison.exposure == exposure)].sort_values("step")
                    axis.plot(subset.step, subset.median_pillar_common_mae_px, "o-", color=colors[arm], alpha=.8, label=f"{arm} / {seed}")
                raw_value = comparison[(comparison.reference == reference) & (comparison.exposure == exposure)].median_pillar_Raw_mae_px.iloc[0]
                axis.axhline(raw_value, color="0.3", linestyle="--", label="Raw")
                axis.set_title(f"{reference} / exposure {exposure}")
                axis.set_xticks([0, 64], ["Initial", "64 updates"])
                axis.set_ylabel("Half-contrast distance to digital SEM (px)")
                axis.grid(alpha=.2)
        axes[0, 0].legend(fontsize=7)
        chart.suptitle("R125 bounded exploratory pilot — same all12 common normals\nAssumed Gaussian optics; reused real images; no physical-accuracy qualification", fontsize=12)
        chart.tight_layout(rect=(0, 0, 1, .93))
        chart.savefig(out / "bounded_sem_comparison.png", dpi=150)
        plt.close(chart)
        for item in protected:
            if sha(item["path"]) != item["sha256"]:
                raise ValueError(f"Aggregate source changed: {item['path']}")
        save(out / "verification.json", {"protected_sources": protected, "protected_sources_unchanged": True,
                                         "aggregate_rows": len(rows), "profile_populations": len(coverage),
                                         "max_independent_paired_accounting_px": max(accounting, default=0),
                                         "all_input_Raw_profiles_equal": True, "all12_population_recomputed": True})
        save(out / "summary.json", {"status": "bounded_real_pilot_comparison_complete", "completed_utc": now(),
                                    "checkpoint_evaluations": len(evaluations), "paired_arm_seed_runs": len(combinations),
                                    "sem_rows": len(rows), "motion_rows": len(motion),
                                    "empty_common_cases": sum(item["empty_common"] for item in coverage),
                                    "below90pct_common_cases": sum(item["below90pct_common"] for item in coverage),
                                    "sem_exposure_results": summaries, "motion_results": motion,
                                    "calibration_qualified": False, "uncertainty_calibrated": False, "scientific_promotion": False,
                                    "interpretation": "First data-pipeline pilot with shared real readouts and own initial controls; not full R123 comparison or unseen real generalization"})
        print(f"Aggregated all12 checkpoints with fixed shared populations: {out}", flush=True)
    except BaseException as error:
        save(out / "failure.json", {"status": "failed", "utc": now(), "error": str(error), "traceback": traceback.format_exc()})
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--freeze-panel", action="store_true")
    parser.add_argument("--checkpoint", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--device", choices=("auto", "cpu", "cuda"), default="auto")
    parser.add_argument("--aggregate", nargs="+", type=Path)
    args = parser.parse_args()
    if args.freeze_panel:
        freeze_panel()
    elif args.aggregate:
        if args.output is None:
            parser.error("--aggregate requires --output")
        aggregate(args.aggregate, args.output)
    else:
        if args.checkpoint is None or args.output is None:
            parser.error("Evaluation requires --checkpoint and --output")
        evaluate(args.checkpoint, args.output, args.device)


if __name__ == "__main__":
    main()

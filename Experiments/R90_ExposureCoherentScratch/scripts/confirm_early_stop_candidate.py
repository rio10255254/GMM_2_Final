"""Confirm the frozen R90 early-stop candidate on all real frames and tiling."""
from __future__ import annotations

import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
import time
from typing import Any

import cv2
import numpy as np
import pandas as pd
import torch


ROOT = Path(__file__).resolve().parents[1]
SELECTION = ROOT / "config" / "early_stop_confirmation.json"
R78_CONFIG = Path(r"D:\GMM_2_Final\Experiments\R78_R75v2_BroadRealMicroscopeGeneralization\config\experiment.json")
LOCKED_MOTION = Path(r"D:\GMM_2_Final\Experiments\R68_R61_RealFOVFeatureGeneralization\results\tables\tile_motion_measurements.csv")
LOCKED_MOTION_SHA256 = "3f48cdebfd032e3231c6b1ba6315fd10535125675d99dbbb0f92dfe8a49fb7d4"
INFERENCE = ROOT / "inference" / "reconstruct.py"
VALIDATION = ROOT / "scripts" / "validate_real_generalization_epoch055.py"
RESULTS = ROOT / "results" / "early_stop_confirmation"
REPORTS = ROOT / "reports" / "early_stop_confirmation"
RECON = RESULTS / "reconstructions" / "E045"
TABLES = RESULTS / "tables"
PREVIOUS_TABLES = ROOT / "results" / "full_validation_epoch055" / "tables"


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    os.replace(temporary, path)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_gray(path: Path) -> np.ndarray:
    image = cv2.imdecode(np.fromfile(path, dtype=np.uint8), cv2.IMREAD_GRAYSCALE)
    if image is None:
        raise RuntimeError(path)
    return image


def write_bmp(path: Path, image: np.ndarray) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    success, encoded = cv2.imencode(".bmp", image)
    if not success:
        raise RuntimeError(path)
    encoded.tofile(path)


def image_paths(directory: Path) -> list[Path]:
    return sorted(directory.glob("frame_*.bmp"))


def seam_mask(height: int, width: int, core: int, radius: int = 2) -> np.ndarray:
    mask = np.zeros((height, width), dtype=bool)
    for y in range(core, height, core):
        mask[max(0, y - radius):min(height, y + radius + 1), :] = True
    for x in range(core, width, core):
        mask[:, max(0, x - radius):min(width, x + radius + 1)] = True
    return mask


def reconstruct_all(inference, model, device: torch.device, config: dict[str, Any]) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    total = sum(int(item["frame_count"]) for item in config["sequences"].values())
    completed = 0
    for sequence, item in config["sequences"].items():
        sources = image_paths(Path(item["raw_dir"]))
        if len(sources) != int(item["frame_count"]):
            raise RuntimeError(f"{sequence}: source count mismatch")
        for source in sources:
            destination = RECON / sequence / source.name
            started = time.perf_counter()
            if destination.is_file() and read_gray(destination).shape == read_gray(source).shape:
                seconds = 0.0
            else:
                raw, dtype = inference.read_gray(source)
                prediction = inference.reconstruct_tensor(
                    model, inference.image_tensor(raw, device),
                    core_size=512, halo=192, tile_batch=1, amp=True,
                )
                write_bmp(destination, inference.output_array(prediction, dtype))
                seconds = time.perf_counter() - started
            records.append({
                "sequence": sequence,
                "source": str(source),
                "source_sha256": sha256_file(source),
                "output": str(destination),
                "output_sha256": sha256_file(destination),
                "seconds": seconds,
            })
            completed += 1
            if completed % 10 == 0 or completed == total:
                print(json.dumps({"phase": "reconstruction", "completed": completed, "total": total, "sequence": sequence}, ensure_ascii=False), flush=True)
    return records


def evaluate_appearance(validation, config: dict[str, Any]) -> tuple[pd.DataFrame, pd.DataFrame]:
    rows: list[dict[str, Any]] = []
    for sequence, item in config["sequences"].items():
        raw_paths = image_paths(Path(item["raw_dir"]))
        recon_paths = image_paths(RECON / sequence)
        if [path.name for path in raw_paths] != [path.name for path in recon_paths]:
            raise RuntimeError(f"{sequence}: reconstruction identities mismatch")
        for index, (raw_path, output_path) in enumerate(zip(raw_paths, recon_paths)):
            rows.append({
                "sequence": sequence,
                "method": "E045",
                "magnification": float(item["magnification"]),
                "nominal_step_um": float(item["nominal_step_um"]),
                "frame_index": index,
                "filename": raw_path.name,
                **validation.appearance_metrics(read_gray(raw_path), read_gray(output_path)),
            })
        print(json.dumps({"phase": "appearance", "sequence": sequence, "frames": len(raw_paths)}, ensure_ascii=False), flush=True)
    table = pd.DataFrame(rows)
    dimensions = {"sequence", "method", "magnification", "nominal_step_um", "frame_index", "filename"}
    metrics = [column for column in table.columns if column not in dimensions]
    summaries: list[dict[str, Any]] = []
    for (sequence, method), group in table.groupby(["sequence", "method"], sort=False):
        row: dict[str, Any] = {
            "sequence": sequence,
            "method": method,
            "frames": int(len(group)),
            "magnification": float(group["magnification"].iloc[0]),
            "nominal_step_um": float(group["nominal_step_um"].iloc[0]),
        }
        for metric in metrics:
            row[f"median_{metric}"] = float(group[metric].median())
            row[f"p95_{metric}"] = float(group[metric].quantile(0.95))
        summaries.append(row)
    return table, pd.DataFrame(summaries)


def tile_consistency(inference, model, device: torch.device, config: dict[str, Any]) -> dict[str, Any]:
    sources = {
        "5x_0p5um": image_paths(Path(config["sequences"]["5x_0p5um"]["raw_dir"]))[24],
        "50x_1um": image_paths(Path(config["sequences"]["50x_1um"]["raw_dir"]))[24],
    }
    report: dict[str, Any] = {"status": "complete", "halo": 192, "images": {}}
    if device.type == "cuda":
        torch.cuda.reset_peak_memory_stats(device)
    started = time.perf_counter()
    for label, source in sources.items():
        raw = read_gray(source)
        tensor = inference.image_tensor(raw, device)
        outputs: dict[int, np.ndarray] = {}
        schemes: dict[str, Any] = {}
        for core in (256, 384, 512):
            full = inference.reconstruct_full_reference(model, tensor, core_size=core, halo=192, amp=True)
            tiled = inference.reconstruct_tensor(model, tensor, core_size=core, halo=192, tile_batch=1, amp=True)
            difference = (tiled - full).abs()[0, 0].float().cpu().numpy() * 255.0
            output = tiled[0, 0].float().cpu().numpy()
            outputs[core] = output
            seam = seam_mask(*raw.shape, core)
            schemes[str(core)] = {
                "mean_abs_gray_tiled_vs_full": float(difference.mean()),
                "p99_abs_gray_tiled_vs_full": float(np.percentile(difference, 99)),
                "max_abs_gray_tiled_vs_full": float(difference.max()),
                "mean_abs_gray_on_seam_band": float(difference[seam].mean()) if seam.any() else 0.0,
                "mean_abs_gray_off_seam_band": float(difference[~seam].mean()),
                "non_identity_mean_abs_gray": float(np.mean(np.abs(output - raw.astype(np.float32) / 255.0)) * 255.0),
            }
            del full, tiled
        cross: dict[str, Any] = {}
        for core in (256, 384):
            difference = np.abs(outputs[core] - outputs[512]) * 255.0
            cross[f"core_{core}_vs_512"] = {
                "mean_abs_gray": float(difference.mean()),
                "p99_abs_gray": float(np.percentile(difference, 99)),
                "max_abs_gray": float(difference.max()),
            }
        report["images"][label] = {
            "source": str(source), "source_sha256": sha256_file(source),
            "shape": list(raw.shape), "schemes": schemes, "cross_scheme": cross,
        }
    report["seconds"] = time.perf_counter() - started
    report["gpu_peak_gib"] = torch.cuda.max_memory_allocated(device) / 2**30 if device.type == "cuda" else 0.0
    full_values = [value["max_abs_gray_tiled_vs_full"] for item in report["images"].values() for value in item["schemes"].values()]
    cross_values = [value["max_abs_gray"] for item in report["images"].values() for value in item["cross_scheme"].values()]
    report["exactness"] = {
        "maximum_tiled_vs_full_gray": float(max(full_values)),
        "maximum_cross_scheme_gray": float(max(cross_values)),
        "visually_lossless_below_0p1_gray": bool(max(full_values + cross_values) < 0.1),
    }
    return report


def comparison_to_existing(motion: pd.DataFrame, appearance: pd.DataFrame) -> dict[str, Any]:
    existing_motion = pd.read_csv(PREVIOUS_TABLES / "real_motion_sequence_summary.csv")
    existing_appearance = pd.read_csv(PREVIOUS_TABLES / "real_appearance_sequence_summary.csv")
    output: dict[str, Any] = {"motion": {}, "appearance": {}}
    for comparator in ("R61v16", "R90E55"):
        motion_rows = []
        appearance_rows = []
        for sequence in motion["sequence"]:
            selected = motion.loc[motion["sequence"] == sequence].iloc[0]
            other = existing_motion.loc[(existing_motion["sequence"] == sequence) & (existing_motion["method"] == comparator)].iloc[0]
            motion_rows.append({
                "sequence": sequence,
                "candidate_minus_comparator_p95_vector_difference_um": float(selected["p95_vector_difference_um"] - other["p95_vector_difference_um"]),
                "candidate_minus_comparator_step_std_um": float(selected["model_step_std_um"] - other["model_step_std_um"]),
                "candidate_minus_comparator_abs_systematic_shift_um": float(abs(selected["mean_signed_model_minus_raw_step_um"]) - abs(other["mean_signed_model_minus_raw_step_um"])),
            })
            selected_appearance = appearance.loc[appearance["sequence"] == sequence].iloc[0]
            other_appearance = existing_appearance.loc[(existing_appearance["sequence"] == sequence) & (existing_appearance["method"] == comparator)].iloc[0]
            appearance_rows.append({
                "sequence": sequence,
                "candidate_minus_comparator_detail_ratio": float(selected_appearance["median_fine_detail_energy_ratio"] - other_appearance["median_fine_detail_energy_ratio"]),
                "candidate_minus_comparator_dark_edge_fraction": float(selected_appearance["median_dark_change_fraction_on_raw_edge_band"] - other_appearance["median_dark_change_fraction_on_raw_edge_band"]),
                "candidate_minus_comparator_off_source_edge_fraction": float(selected_appearance["median_off_source_strong_edge_fraction"] - other_appearance["median_off_source_strong_edge_fraction"]),
            })
        output["motion"][f"E045_vs_{comparator}"] = motion_rows
        output["appearance"][f"E045_vs_{comparator}"] = appearance_rows
    return output


def main() -> int:
    selection = read_json(SELECTION)
    config = read_json(R78_CONFIG)
    checkpoint = Path(selection["checkpoint"])
    if sha256_file(checkpoint) != selection["checkpoint_sha256"]:
        raise RuntimeError("Selected checkpoint hash mismatch")
    if sha256_file(LOCKED_MOTION) != LOCKED_MOTION_SHA256:
        raise RuntimeError("Locked motion table changed")
    if not torch.cuda.is_available():
        raise RuntimeError("CUDA is required")
    device = torch.device("cuda:0")
    free_before, total = torch.cuda.mem_get_info(device)
    if free_before < 8 * 2**30:
        raise RuntimeError("Less than 8 GiB GPU memory is free")
    inference = load_module("r90_confirmation_inference", INFERENCE)
    validation = load_module("r90_confirmation_metrics", VALIDATION)
    model, payload = inference.load_model(checkpoint, device)
    if int(payload.get("epoch", -1)) != int(selection["selected_epoch"]):
        raise RuntimeError("Checkpoint epoch mismatch")
    started = time.perf_counter()
    write_json(RESULTS / "state.json", {"status": "running", "checkpoint_sha256": selection["checkpoint_sha256"]})

    inventory = reconstruct_all(inference, model, device, config)
    TABLES.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(inventory).to_csv(TABLES / "reconstruction_inventory.csv", index=False, encoding="utf-8-sig")

    validation.RECON_ROOT = RESULTS / "reconstructions"
    locked = pd.read_csv(LOCKED_MOTION)
    locked["raw_reference_valid"] = validation.as_bool(locked["raw_reference_valid"])
    motion_table = validation.compute_model_rows("E045", config, locked)
    motion_summary = validation.summarize_motion(motion_table)
    motion_table.to_csv(TABLES / "motion_measurements.csv", index=False, encoding="utf-8-sig")
    motion_summary.to_csv(TABLES / "motion_by_sequence.csv", index=False, encoding="utf-8-sig")

    appearance_table, appearance_summary = evaluate_appearance(validation, config)
    appearance_table.to_csv(TABLES / "appearance_all_frames.csv", index=False, encoding="utf-8-sig")
    appearance_summary.to_csv(TABLES / "appearance_by_sequence.csv", index=False, encoding="utf-8-sig")

    tile_report = tile_consistency(inference, model, device, config)
    write_json(RESULTS / "tile_consistency.json", tile_report)
    comparison = comparison_to_existing(motion_summary, appearance_summary)
    free_after, _ = torch.cuda.mem_get_info(device)
    summary = {
        "status": "complete",
        "confirmation_id": selection["confirmation_id"],
        "checkpoint_epoch": int(payload["epoch"]),
        "checkpoint_sha256": selection["checkpoint_sha256"],
        "source_frames": 301,
        "reconstruction_inventory_rows": len(inventory),
        "locked_motion_table_sha256": LOCKED_MOTION_SHA256,
        "motion_sequences": int(len(motion_summary)),
        "all_sequences_fully_evaluable": bool((motion_summary["valid_fraction_within_raw_reference"] == 1.0).all()),
        "all_sequences_direction_agreement": bool((motion_summary["direction_agreement_fraction"] == 1.0).all()),
        "maximum_median_scale_error_fraction": float(motion_summary["median_scale_error_fraction"].max()),
        "maximum_abs_mean_systematic_shift_um": float(motion_summary["mean_signed_model_minus_raw_step_um"].abs().max()),
        "maximum_p95_vector_difference_um": float(motion_summary["p95_vector_difference_um"].max()),
        "tile_consistency": tile_report["exactness"],
        "comparison_to_existing": comparison,
        "gpu": {
            "name": torch.cuda.get_device_name(device),
            "free_before_gib": free_before / 2**30,
            "total_gib": total / 2**30,
            "free_after_gib": free_after / 2**30,
            "tile_test_peak_gib": tile_report["gpu_peak_gib"],
        },
        "seconds": time.perf_counter() - started,
        "scientific_delivery_blocker_still_open": "SEM exposure 18 edge expansion from early-stop development comparison",
        "claim_limit": "Motion uses the locked Raw reference and is a stability/consistency test, not independent absolute stage truth.",
    }
    write_json(REPORTS / "summary.json", summary)
    write_json(RESULTS / "state.json", {"status": "complete", "summary": str(REPORTS / "summary.json")})
    print(json.dumps(summary, ensure_ascii=False), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Full 5x/20x/50x real-sequence appearance, tiling, and motion audit for R103."""
from __future__ import annotations

import hashlib
import importlib.util
import json
import math
import sys
import time
from pathlib import Path

import cv2
import numpy as np
import pandas as pd
import torch


ROOT = Path(__file__).resolve().parents[1]
for folder in (ROOT / "model", ROOT / "inference"):
    if str(folder) not in sys.path:
        sys.path.insert(0, str(folder))

from r103_model import build_model  # noqa: E402
from reconstruct import reconstruct_tensor  # noqa: E402
PROJECT_ROOT = Path(__file__).resolve().parents[3]


HELPER_PATH = Path(str(PROJECT_ROOT / 'Experiments/R96_LocalizedEvidenceProtectedScratch/scripts/evaluate_real_holdout.py'))
SEQUENCE_CONFIG = Path(str(PROJECT_ROOT / 'Experiments/R68_R61_RealFOVFeatureGeneralization/config/sequences.json'))
LOCKED_MOTION = Path(str(PROJECT_ROOT / 'Experiments/R68_R61_RealFOVFeatureGeneralization/results/tables/tile_motion_measurements.csv'))
OUTPUT = ROOT / "results" / "posttraining_validation" / "real_sequences"


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


HELPERS = load_module("r103_real_helpers", HELPER_PATH)
CONFIG = json.loads((ROOT / "config" / "experiment.json").read_text(encoding="utf-8"))
RUN = json.loads((ROOT / "runs" / "active_run.json").read_text(encoding="utf-8"))
SEQUENCES = json.loads(SEQUENCE_CONFIG.read_text(encoding="utf-8"))


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = json.dumps(payload, ensure_ascii=False, indent=2)
    last_error: PermissionError | None = None
    for attempt in range(12):
        temporary = path.with_name(f"{path.name}.{attempt}.tmp")
        temporary.write_text(encoded, encoding="utf-8")
        try:
            temporary.replace(path)
            return
        except PermissionError as error:
            last_error = error
            temporary.unlink(missing_ok=True)
            time.sleep(.05 * (attempt + 1))
    assert last_error is not None
    raise last_error


def bool_series(series: pd.Series) -> pd.Series:
    if series.dtype == bool:
        return series
    return series.astype(str).str.lower().isin({"true", "1"})


def robust_mad(values: pd.Series) -> float:
    array = values.to_numpy(float)
    median = float(np.median(array))
    return float(1.4826 * np.median(np.abs(array - median)))


def label_panel(image: np.ndarray, label: str) -> np.ndarray:
    panel = cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)
    cv2.rectangle(panel, (0, 0), (panel.shape[1], 38), (0, 0, 0), -1)
    cv2.putText(panel, label, (8, 27), cv2.FONT_HERSHEY_SIMPLEX, .7, (255, 255, 255), 2, cv2.LINE_AA)
    return panel


def save_montage(path: Path, rows: list[tuple[int, np.ndarray, np.ndarray, np.ndarray]]) -> None:
    sheets: list[np.ndarray] = []
    for index, raw, r61, r103 in rows:
        scale = min(1.0, 512.0 / raw.shape[1])
        size = (int(raw.shape[1] * scale), int(raw.shape[0] * scale))
        difference = np.clip(np.abs(r103.astype(np.int16) - raw.astype(np.int16)) * 8, 0, 255).astype(np.uint8)
        panels = [
            label_panel(cv2.resize(raw, size, interpolation=cv2.INTER_AREA), f"Raw frame {index}"),
            label_panel(cv2.resize(r61, size, interpolation=cv2.INTER_AREA), "R61v16"),
            label_panel(cv2.resize(r103, size, interpolation=cv2.INTER_AREA), "R103 E48"),
            label_panel(cv2.resize(difference, size, interpolation=cv2.INTER_AREA), "R103 abs diff x8"),
        ]
        sheets.append(np.concatenate(panels, axis=1))
    path.parent.mkdir(parents=True, exist_ok=True)
    if not cv2.imwrite(str(path), np.concatenate(sheets, axis=0)):
        raise RuntimeError(path)


def load_model(device: torch.device) -> tuple[torch.nn.Module, Path, dict]:
    checkpoint = Path(RUN["weights_dir"]) / "epoch_048.pth.tar"
    payload = torch.load(checkpoint, map_location="cpu", weights_only=False)
    if int(payload["epoch"]) != 48:
        raise RuntimeError("R103 final checkpoint mismatch")
    bounds = CONFIG["model"]["branch_bounds"]
    model = build_model(
        base=int(CONFIG["model"]["base_channels"]),
        low_bound=float(bounds["radiometry"]),
        contour_bound=float(bounds["contour"]),
        texture_bound=float(bounds["texture"]),
        combined_bound=float(bounds["combined"]),
    )
    model.load_state_dict(payload["ema_state_dict"], strict=True)
    return model.to(device).eval(), checkpoint, payload


def motion_summary(wide: pd.DataFrame) -> pd.DataFrame:
    methods = {
        "Raw": ("raw_dx_px", "raw_dy_px", "raw_response", None),
        "R61v16": ("r61_dx_px", "r61_dy_px", "r61_response", "r61_ecc"),
        "R103E48": ("r103_dx_px", "r103_dy_px", "r103_response", "r103_ecc"),
    }
    rows: list[dict[str, object]] = []
    for sequence, group in wide.groupby("sequence", sort=False):
        common = group.loc[bool_series(group["common_valid"])]
        scale_um = float(group["object_um_per_px"].iloc[0])
        nominal = float(group["nominal_step_um"].iloc[0])
        for method, (dx_name, dy_name, response_name, ecc_name) in methods.items():
            dx = common[dx_name].astype(float)
            dy = common[dy_name].astype(float)
            step = dx.abs() * scale_um
            raw_step = common["raw_dx_px"].astype(float).abs() * scale_um
            vector_delta = np.hypot(
                dx.to_numpy() - common["raw_dx_px"].astype(float).to_numpy(),
                dy.to_numpy() - common["raw_dy_px"].astype(float).to_numpy(),
            ) * scale_um
            response_ratio = common[response_name].astype(float) / common["raw_response"].astype(float).clip(lower=1e-9)
            ratio = step / raw_step.clip(lower=1e-9)
            rows.append({
                "sequence": sequence,
                "method": method,
                "magnification": float(group["magnification"].iloc[0]),
                "nominal_step_um": nominal,
                "common_measurements": int(len(common)),
                "common_fraction_of_raw_reference": float(len(common) / max(int(bool_series(group["raw_reference_valid"]).sum()), 1)),
                "median_abs_dx_um": float(step.median()),
                "signed_bias_to_nominal_um": float(step.median() - nominal),
                "step_std_um": float(step.std(ddof=1)),
                "step_robust_mad_um": robust_mad(step),
                "median_model_over_raw_abs_dx": float(ratio.median()),
                "median_scale_error_fraction": float(abs(ratio.median() - 1.0)),
                "median_vector_difference_from_raw_um": float(np.median(vector_delta)),
                "p95_vector_difference_from_raw_um": float(np.quantile(vector_delta, .95)),
                "median_response_ratio": float(response_ratio.median()),
                "median_ecc": 1.0 if ecc_name is None else float(common[ecc_name].astype(float).median()),
            })
    return pd.DataFrame(rows)


def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")
    torch.set_num_threads(6)
    model, checkpoint, payload = load_model(device)
    locked = pd.read_csv(LOCKED_MOTION)
    appearance_records: list[dict[str, object]] = []
    reconstruction_records: list[dict[str, object]] = []
    reconstructed: dict[tuple[str, int], Path] = {}
    selected_sequences = list(SEQUENCES["sequences"])
    total_frames = sum(int(SEQUENCES["sequences"][name]["frame_count"]) for name in selected_sequences)
    completed = 0
    started = time.perf_counter()

    for sequence in selected_sequences:
        item = SEQUENCES["sequences"][sequence]
        raw_paths = sorted(Path(PROJECT_ROOT / item["raw_dir"]).glob("frame_*.bmp"))
        r61_paths = sorted(Path(PROJECT_ROOT / item["recon_dir"]).glob("frame_*.bmp"))
        if len(raw_paths) != int(item["frame_count"]) or len(r61_paths) != len(raw_paths):
            raise RuntimeError(f"{sequence}: frame inventory mismatch")
        fixed = {0, 12, 24, 36, len(raw_paths) - 1}
        montage: list[tuple[int, np.ndarray, np.ndarray, np.ndarray]] = []
        for index, (raw_path, r61_path) in enumerate(zip(raw_paths, r61_paths)):
            raw = HELPERS.read_gray(raw_path)
            r61 = HELPERS.read_gray(r61_path)
            destination = OUTPUT / "reconstructions" / sequence / raw_path.name
            frame_started = time.perf_counter()
            if destination.is_file():
                r103 = HELPERS.read_gray(destination)
                if r103.shape != raw.shape:
                    raise RuntimeError(f"Resume output shape mismatch: {destination}")
                minimum, maximum = float(r103.min() / 255.0), float(r103.max() / 255.0)
                low_clip = float((r103 <= 0).mean())
                high_clip = float((r103 >= 255).mean())
                inference_seconds = 0.0
            else:
                tensor = torch.from_numpy(raw.astype(np.float32) / 255.0)[None, None].to(device)
                with torch.inference_mode(), torch.autocast(
                    device_type=device.type, dtype=torch.bfloat16, enabled=device.type == "cuda"
                ):
                    prediction = reconstruct_tensor(model, tensor, core_size=512, halo=128, tile_batch=4)[0, 0].float()
                minimum, maximum = float(prediction.min()), float(prediction.max())
                low_clip = float((prediction <= 0).float().mean())
                high_clip = float((prediction >= 1).float().mean())
                r103 = np.rint(prediction.clamp(0, 1).cpu().numpy() * 255.0).astype(np.uint8)
                HELPERS.write_gray(destination, r103)
                inference_seconds = time.perf_counter() - frame_started
            reconstructed[(sequence, index)] = destination
            reconstruction_records.append({
                "sequence": sequence, "frame_index": index,
                "source": str(raw_path), "source_sha256": sha256(raw_path),
                "output": str(destination), "output_sha256": sha256(destination),
                "seconds": inference_seconds,
                "unbounded_min": minimum, "unbounded_max": maximum,
                "low_clip_fraction": low_clip,
                "high_clip_fraction": high_clip,
            })
            base = {
                "sequence": sequence, "frame_index": index,
                "magnification": float(item["magnification"]),
                "nominal_step_um": float(item["nominal_step_um"]),
            }
            appearance_records.append({**base, "method": "R61v16", **HELPERS.appearance_metrics(raw, r61, 512)})
            appearance_records.append({**base, "method": "R103E48", **HELPERS.appearance_metrics(raw, r103, 512)})
            if index in fixed:
                montage.append((index, raw, r61, r103))
            completed += 1
            elapsed = time.perf_counter() - started
            write_json(OUTPUT / "progress.json", {
                "status": "running", "completed_frames": completed, "total_frames": total_frames,
                "sequence": sequence, "frame_index": index, "elapsed_seconds": elapsed,
                "estimated_remaining_seconds": elapsed / completed * (total_frames - completed),
            })
            if completed % 10 == 0 or completed == total_frames:
                print(f"[real] {completed}/{total_frames} {sequence} frame {index}", flush=True)
        save_montage(OUTPUT / "figures" / f"{sequence}_comparison.png", montage)

    pd.DataFrame(reconstruction_records).to_csv(OUTPUT / "reconstruction_manifest.csv", index=False)
    appearance = pd.DataFrame(appearance_records)
    appearance.to_csv(OUTPUT / "appearance_per_frame.csv", index=False)
    appearance_summary = appearance.groupby(["sequence", "method"], sort=False).agg({
        "mean_signed_change_gray": "median",
        "mean_abs_change_gray": "median",
        "p95_abs_change_gray": "median",
        "ssim_to_raw": "median",
        "edge_gain_on_raw_support": "median",
        "fine_detail_energy_ratio": "median",
        "off_source_strong_edge_fraction": "median",
        "dark_change_fraction_on_edge_band": "median",
        "bright_change_fraction_on_edge_band": "median",
        "mean_abs_change_flat_region_gray": "median",
        "tile_seam_residual_ratio": "median",
    }).reset_index()
    appearance_summary.to_csv(OUTPUT / "appearance_sequence_summary.csv", index=False)

    motion_records: list[dict[str, object]] = []
    for _, row in locked.iterrows():
        sequence, step = str(row["sequence"]), int(row["step_index"])
        first = HELPERS.read_gray(reconstructed[(sequence, step)])
        second = HELPERS.read_gray(reconstructed[(sequence, step + 1)])
        tile_h, tile_w = first.shape[0] // 6, first.shape[1] // 8
        tile_row, tile_col = int(row["tile_row"]), int(row["tile_column"])
        y0, x0 = tile_row * tile_h, tile_col * tile_w
        a = first[y0:y0 + tile_h, x0:x0 + tile_w]
        b = second[y0:y0 + tile_h, x0:x0 + tile_w]
        phase_dx, phase_dy, response = HELPERS.phase_shift(a, b)
        try:
            dx, dy, ecc = HELPERS.bounded_ecc_shift(a, b, float(row["raw_dx_px"]), float(row["raw_dy_px"]))
            finite = all(math.isfinite(value) for value in (dx, dy, ecc))
        except cv2.error:
            dx = dy = ecc = math.nan
            finite = False
        limit = max(12.0, abs(float(row["expected_dx_px"])) * 2.5)
        evaluable = finite and ecc >= .75 and abs(dx) <= limit and abs(dy) <= limit
        raw_valid = str(row["raw_reference_valid"]).lower() in {"true", "1"}
        valid = bool(raw_valid and evaluable)
        motion_records.append({
            **row.to_dict(),
            "r103_phase_dx_px": phase_dx, "r103_phase_dy_px": phase_dy,
            "r103_response": response, "r103_dx_px": dx, "r103_dy_px": dy,
            "r103_ecc": ecc, "r103_evaluable": evaluable, "r103_valid": valid,
            "r103_direction_agreement": bool(valid and np.sign(dx) == np.sign(float(row["raw_dx_px"]))),
            "r103_over_raw_abs_dx": abs(dx) / max(abs(float(row["raw_dx_px"])), 1e-9) if valid else math.nan,
        })
    motion = pd.DataFrame(motion_records)
    motion["common_valid"] = (
        bool_series(motion["raw_reference_valid"])
        & bool_series(motion["valid"])
        & bool_series(motion["r103_valid"])
    )
    motion.to_csv(OUTPUT / "motion_measurements.csv", index=False)
    summary = motion_summary(motion)
    summary.to_csv(OUTPUT / "motion_sequence_summary.csv", index=False)

    gates = SEQUENCES["gates"]
    decisions: list[dict[str, object]] = []
    r103_rows = summary.loc[summary["method"] == "R103E48"]
    for _, row in r103_rows.iterrows():
        subset = motion.loc[motion["sequence"] == row["sequence"]]
        valid_subset = subset.loc[bool_series(subset["r103_valid"])]
        direction = float(bool_series(valid_subset["r103_direction_agreement"]).mean()) if len(valid_subset) else 0.0
        checks = {
            "valid_fraction": float(row["common_fraction_of_raw_reference"]) >= float(gates["minimum_valid_fraction"]),
            "direction": direction >= float(gates["minimum_direction_agreement"]),
            "scale": float(row["median_scale_error_fraction"]) <= float(gates["maximum_median_scale_error_fraction"]),
            "median_difference": float(row["median_vector_difference_from_raw_um"]) / float(row["nominal_step_um"]) <= float(gates["maximum_median_difference_of_step"]),
            "p95_difference": float(row["p95_vector_difference_from_raw_um"]) / float(row["nominal_step_um"]) <= float(gates["maximum_p95_difference_of_step"]),
            "response": float(row["median_response_ratio"]) >= float(gates["minimum_median_response_ratio"]),
            "ecc": float(row["median_ecc"]) >= float(gates["minimum_median_ecc"]),
        }
        decisions.append({"sequence": row["sequence"], "pass": all(checks.values()), "checks": checks})

    result = {
        "status": "complete",
        "checkpoint": str(checkpoint), "checkpoint_sha256": sha256(checkpoint),
        "checkpoint_epoch": int(payload["epoch"]), "formal_run_id": RUN["run_id"],
        "frames": total_frames, "motion_measurements": int(len(motion)),
        "all_sequences_pass": all(item["pass"] for item in decisions),
        "sequence_decisions": decisions,
        "elapsed_seconds": time.perf_counter() - started,
    }
    write_json(OUTPUT / "summary.json", result)
    write_json(OUTPUT / "progress.json", {**result, "status": "complete"})
    print(json.dumps(result, indent=2), flush=True)


if __name__ == "__main__":
    main()

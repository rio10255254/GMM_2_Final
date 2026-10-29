"""Validate counterfactual x_1um outputs before external GMF."""
from __future__ import annotations

import hashlib
import importlib.util
import json
import math
from pathlib import Path
import sys

import cv2
import numpy as np
import pandas as pd
PROJECT_ROOT = Path(__file__).resolve().parents[3]


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "results" / "x1um_counterfactual_reconstruction"
SOURCE = Path(str(PROJECT_ROOT / 'Shared_Sources/Real_Sample_Captures/20260702_100MG_位移_50x/x_1um'))
LOCKED = Path(str(PROJECT_ROOT / 'Experiments/R68_R61_RealFOVFeatureGeneralization/results/tables/tile_motion_measurements.csv'))
HELPERS_PATH = ROOT / "scripts" / "evaluate_real_holdout.py"
ARMS = ("00_raw", "01_r96", "02_detail_gate_open", "03_all_gate_open", "04_phase_safe_detail")


def read(path: Path) -> np.ndarray:
    value = cv2.imdecode(np.fromfile(path, dtype=np.uint8), cv2.IMREAD_GRAYSCALE)
    if value is None:
        raise RuntimeError(path)
    return value


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


HELPERS = load_module("x1um_validation_helpers", HELPERS_PATH)


def robust_mad(values: pd.Series) -> float:
    array = values.to_numpy(float)
    median = np.median(array)
    return float(1.4826 * np.median(np.abs(array - median)))


def as_bool(value: object) -> bool:
    if isinstance(value, str):
        return value.strip().lower() == "true"
    return bool(value)


def edge_energy(image: np.ndarray) -> float:
    value = image.astype(np.float32)
    gx = cv2.Sobel(value, cv2.CV_32F, 1, 0, ksize=3)
    gy = cv2.Sobel(value, cv2.CV_32F, 0, 1, ksize=3)
    return float(np.mean(np.hypot(gx, gy)))


def detail_energy(image: np.ndarray) -> float:
    value = image.astype(np.float32)
    low = cv2.GaussianBlur(value, (0, 0), 1.0, borderType=cv2.BORDER_REFLECT_101)
    return float(np.mean(np.abs(value - low)))


def main() -> None:
    source_paths = sorted(SOURCE.glob("*.bmp"))
    inventory = {}
    for arm in ARMS:
        paths = sorted((OUTPUT / arm).glob("frame_*.bmp"))
        inventory[arm] = len(paths)
        if len(paths) != len(source_paths):
            raise RuntimeError(f"{arm}: {len(paths)} files")
    raw_hash_equal = all(
        sha256(source) == sha256(OUTPUT / "00_raw" / f"frame_{index:04d}.bmp")
        for index, source in enumerate(source_paths)
    )
    if not raw_hash_equal:
        raise RuntimeError("Raw copy is not bit-identical")

    appearance = []
    for index in range(len(source_paths)):
        raw = read(OUTPUT / "00_raw" / f"frame_{index:04d}.bmp")
        for arm in ARMS:
            image = read(OUTPUT / arm / f"frame_{index:04d}.bmp")
            if image.shape != raw.shape or image.dtype != np.uint8:
                raise RuntimeError(f"{arm} frame {index}: invalid shape/dtype")
            canonical = HELPERS.appearance_metrics(raw, image, 512)
            appearance.append({
                "arm": arm, "frame": index,
                "mean_abs_change_gray": float(np.mean(np.abs(image.astype(np.float32) - raw.astype(np.float32)))),
                "edge_energy_ratio": edge_energy(image) / max(edge_energy(raw), 1e-9),
                "detail_energy_ratio": detail_energy(image) / max(detail_energy(raw), 1e-9),
                "minimum": int(image.min()), "maximum": int(image.max()),
                **canonical,
            })
    appearance_table = pd.DataFrame(appearance)
    appearance_table.to_csv(OUTPUT / "validation_appearance.csv", index=False)

    # Reuse the exact R68 Raw-locked 24-tile eligibility.  Full-frame phase
    # correlation is invalid here because the four quadrants contain different
    # structures and can cancel one another.
    locked = pd.read_csv(LOCKED)
    locked = locked.loc[locked["sequence"] == "50x_1um"].copy()
    if len(locked) != 1128 or locked["tile_id"].nunique() != 24:
        raise RuntimeError("Unexpected locked 50x_1um protocol")
    motion = []
    for arm in ARMS:
        frames = [read(OUTPUT / arm / f"frame_{index:04d}.bmp") for index in range(len(source_paths))]
        for _, row in locked.iterrows():
            step = int(row["step_index"])
            image_a, image_b = frames[step], frames[step + 1]
            tile_h, tile_w = image_a.shape[0] // 6, image_a.shape[1] // 8
            tile_row, tile_column = int(row["tile_row"]), int(row["tile_column"])
            y0, x0 = tile_row * tile_h, tile_column * tile_w
            tile_a = image_a[y0:y0 + tile_h, x0:x0 + tile_w]
            tile_b = image_b[y0:y0 + tile_h, x0:x0 + tile_w]
            phase_dx, phase_dy, response = HELPERS.phase_shift(tile_a, tile_b)
            raw_dx, raw_dy = float(row["raw_dx_px"]), float(row["raw_dy_px"])
            raw_valid = as_bool(row["raw_reference_valid"])
            if arm == "00_raw":
                dx, dy, ecc, evaluable = raw_dx, raw_dy, math.nan, raw_valid
            else:
                try:
                    dx, dy, ecc = HELPERS.bounded_ecc_shift(tile_a, tile_b, raw_dx, raw_dy)
                    finite = all(math.isfinite(value) for value in (dx, dy, ecc))
                except cv2.error:
                    dx, dy, ecc, finite = math.nan, math.nan, math.nan, False
                limit = max(12.0, float(row["expected_dx_px"]) * 2.5)
                evaluable = bool(finite and ecc >= 0.75 and abs(dx) <= limit and abs(dy) <= limit)
            valid = raw_valid and evaluable
            um_per_px = float(row["object_um_per_px"])
            motion.append({
                "arm": arm, "step": step, "tile_id": str(row["tile_id"]),
                "tile_row": tile_row, "tile_column": tile_column,
                "dx_px": dx, "dy_px": dy, "phase_dx_px": phase_dx, "phase_dy_px": phase_dy,
                "response": response, "ecc": ecc,
                "raw_dx_px": raw_dx, "raw_dy_px": raw_dy, "raw_response": float(row["raw_response"]),
                "raw_reference_valid": raw_valid, "evaluable": evaluable, "valid": valid,
                "scale": abs(dx) / max(abs(raw_dx), 1e-9) if valid else math.nan,
                "vector_difference_um": float(np.hypot(dx - raw_dx, dy - raw_dy) * um_per_px) if valid else math.nan,
                "direction_matches_raw": bool(np.sign(dx) == np.sign(raw_dx)) if valid and abs(raw_dx) > .05 and abs(dx) > .05 else False,
            })
        print(f"[locked motion] {arm}: {len(locked)} tile measurements", flush=True)
    motion_table = pd.DataFrame(motion)
    motion_table.to_csv(OUTPUT / "validation_locked_tile_motion.csv", index=False)
    appearance_summary = appearance_table.groupby("arm", sort=False).agg(
        mean_abs_change_gray=("mean_abs_change_gray", "median"),
        edge_energy_ratio=("edge_energy_ratio", "median"),
        detail_energy_ratio=("detail_energy_ratio", "median"),
        edge_gain_on_raw_support=("edge_gain_on_raw_support", "median"),
        fine_detail_energy_ratio=("fine_detail_energy_ratio", "median"),
        off_source_strong_edge_fraction=("off_source_strong_edge_fraction", "median"),
        dark_change_fraction_on_edge_band=("dark_change_fraction_on_edge_band", "median"),
        mean_abs_change_flat_region_gray=("mean_abs_change_flat_region_gray", "median"),
        tile_seam_residual_ratio=("tile_seam_residual_ratio", "median"),
        minimum=("minimum", "min"), maximum=("maximum", "max"),
    ).reset_index()
    motion_summaries = []
    for arm, group in motion_table.groupby("arm", sort=False):
        reference = group.loc[group["raw_reference_valid"]]
        valid = group.loc[group["valid"]]
        raw_step = valid["raw_dx_px"].abs() * .069
        model_step = valid["dx_px"].abs() * .069
        vector = valid["vector_difference_um"]
        scale = float(valid["scale"].median())
        motion_summaries.append({
            "arm": arm, "selected_tiles": int(group["tile_id"].nunique()),
            "used_steps": int(group["step"].nunique()), "tile_measurements": int(len(group)),
            "raw_reference_measurements": int(len(reference)), "valid_measurements": int(len(valid)),
            "valid_fraction_within_raw_reference": float(len(valid) / max(len(reference), 1)),
            "direction_agreement_fraction": float(valid["direction_matches_raw"].mean()),
            "median_model_over_raw_abs_dx": scale, "median_scale_error_fraction": abs(scale - 1.0),
            "raw_median_abs_dx_um": float(raw_step.median()), "model_median_abs_dx_um": float(model_step.median()),
            "raw_step_std_um": float(raw_step.std(ddof=1)), "model_step_std_um": float(model_step.std(ddof=1)),
            "raw_step_robust_mad_um": robust_mad(raw_step), "model_step_robust_mad_um": robust_mad(model_step),
            "median_vector_difference_um": float(vector.median()), "p95_vector_difference_um": float(vector.quantile(.95)),
            "median_difference_of_commanded_step": float(vector.median()),
            "p95_difference_of_commanded_step": float(vector.quantile(.95)),
            "median_response": float(valid["response"].median()),
            "median_ecc": float(valid["ecc"].median()) if arm != "00_raw" else math.nan,
        })
    motion_summary = pd.DataFrame(motion_summaries)
    appearance_summary.to_csv(OUTPUT / "validation_appearance_summary.csv", index=False)
    motion_summary.to_csv(OUTPUT / "validation_locked_tile_motion_summary.csv", index=False)
    payload = {
        "status": "complete",
        "inventory": inventory,
        "raw_bit_identical": raw_hash_equal,
        "appearance": appearance_summary.to_dict(orient="records"),
        "locked_tile_motion": motion_summary.to_dict(orient="records"),
        "claim_boundary": "The locked 24-tile tracker is an internal integrity guard; external GMF remains the independent coordinate result.",
    }
    (OUTPUT / "validation_summary.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()

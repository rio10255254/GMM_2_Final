"""Read-only diagnostic: test whether symmetric detail gain must hurt locked motion."""
from __future__ import annotations

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
FINAL = ROOT / "results" / "final_validation" / "real_generalization"
OUTPUT = ROOT / "results" / "deep_diagnosis" / "sharpness_motion_compatibility"
CONFIG = Path(str(PROJECT_ROOT / 'Experiments/R68_R61_RealFOVFeatureGeneralization/config/sequences.json'))
LOCKED = Path(str(PROJECT_ROOT / 'Experiments/R68_R61_RealFOVFeatureGeneralization/results/tables/tile_motion_measurements.csv'))
PREDECLARED_STEPS = {0, 12, 24, 36, 48}


def load_helpers():
    path = ROOT / "scripts" / "evaluate_real_holdout.py"
    spec = importlib.util.spec_from_file_location("r96_compat_helpers", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


H = load_helpers()


def symmetric_detail_gain(image: np.ndarray, amount: float) -> np.ndarray:
    value = image.astype(np.float32)
    low = cv2.GaussianBlur(value, (0, 0), 1.0, borderType=cv2.BORDER_REFLECT_101)
    detail = value - low
    local_min = cv2.erode(value, np.ones((5, 5), np.uint8), borderType=cv2.BORDER_REFLECT_101)
    local_max = cv2.dilate(value, np.ones((5, 5), np.uint8), borderType=cv2.BORDER_REFLECT_101)
    strengthened = np.clip(value + float(amount) * detail, local_min, local_max)
    return np.rint(strengthened).clip(0, 255).astype(np.uint8)


def read(path: Path) -> np.ndarray:
    return H.read_gray(path)


def measure_pair(a: np.ndarray, b: np.ndarray, row: pd.Series) -> dict[str, float | bool]:
    tile_h, tile_w = a.shape[0] // 6, a.shape[1] // 8
    y0, x0 = int(row.tile_row) * tile_h, int(row.tile_column) * tile_w
    first = a[y0:y0 + tile_h, x0:x0 + tile_w]
    second = b[y0:y0 + tile_h, x0:x0 + tile_w]
    _phase_x, _phase_y, response = H.phase_shift(first, second)
    try:
        dx, dy, ecc = H.bounded_ecc_shift(first, second, float(row.raw_dx_px), float(row.raw_dy_px))
        finite = all(math.isfinite(v) for v in (dx, dy, ecc))
    except cv2.error:
        dx = dy = ecc = math.nan
        finite = False
    limit = max(12.0, float(row.expected_dx_px) * 2.5)
    evaluable = bool(finite and ecc >= 0.75 and abs(dx) <= limit and abs(dy) <= limit)
    valid = bool(row.raw_reference_valid) and evaluable
    vector = math.hypot(dx - float(row.raw_dx_px), dy - float(row.raw_dy_px)) * float(row.object_um_per_px) if valid else math.nan
    return {"valid": valid, "direction": bool(np.sign(dx) == np.sign(float(row.raw_dx_px))) if valid else False,
            "vector_difference_um": vector, "response": response, "ecc": ecc,
            "scale": abs(dx) / max(abs(float(row.raw_dx_px)), 1e-9) if valid else math.nan}


def main() -> None:
    if OUTPUT.exists() and any(OUTPUT.iterdir()):
        raise RuntimeError(f"Refusing to overwrite {OUTPUT}")
    OUTPUT.mkdir(parents=True, exist_ok=True)
    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    locked = pd.read_csv(LOCKED)
    locked = locked.loc[locked["step_index"].isin(PREDECLARED_STEPS)].copy()
    amounts = [0.0, 0.20, 0.35]
    rows: list[dict[str, object]] = []
    appearance: list[dict[str, object]] = []
    cache: dict[tuple[str, int, float], np.ndarray] = {}
    required_frames = {
        sequence: sorted({int(step) + offset for step in locked.loc[locked.sequence == sequence, "step_index"] for offset in (0, 1)})
        for sequence in config["sequences"]
    }
    for sequence, item in config["sequences"].items():
        raw_paths = sorted(Path(PROJECT_ROOT / item["raw_dir"]).glob("frame_*.bmp"))
        r96_paths = sorted((FINAL / "reconstructions" / sequence).glob("frame_*.bmp"))
        if len(raw_paths) != len(r96_paths):
            raise RuntimeError(f"{sequence}: inventory mismatch")
        for index in required_frames[sequence]:
            raw_path, r96_path = raw_paths[index], r96_paths[index]
            raw, base = read(raw_path), read(r96_path)
            for amount in amounts:
                candidate = base if amount == 0.0 else symmetric_detail_gain(base, amount)
                cache[(sequence, index, amount)] = candidate
                metric = H.appearance_metrics(raw, candidate, 512)
                appearance.append({"sequence": sequence, "frame": index, "amount": amount, **metric})
    for row in locked.itertuples(index=False):
        for amount in amounts:
            result = measure_pair(cache[(row.sequence, int(row.step_index), amount)],
                                  cache[(row.sequence, int(row.step_index) + 1, amount)], row)
            rows.append({"sequence": row.sequence, "step": int(row.step_index), "tile_id": row.tile_id,
                         "amount": amount, "nominal_step_um": float(row.nominal_step_um), **result})
    motion = pd.DataFrame(rows)
    app = pd.DataFrame(appearance)
    motion.to_csv(OUTPUT / "motion_measurements.csv", index=False)
    app.to_csv(OUTPUT / "appearance_metrics.csv", index=False)
    summaries = []
    for (sequence, amount), group in motion.groupby(["sequence", "amount"], sort=False):
        valid = group[group.valid]
        summaries.append({"sequence": sequence, "amount": amount,
                          "valid_fraction": float(group.valid.mean()),
                          "direction_fraction": float(valid.direction.mean()),
                          "median_difference_of_step": float(valid.vector_difference_um.median() / valid.nominal_step_um.iloc[0]),
                          "p95_difference_of_step": float(valid.vector_difference_um.quantile(.95) / valid.nominal_step_um.iloc[0]),
                          "median_scale_error": abs(float(valid.scale.median()) - 1.0),
                          "median_response": float(valid.response.median()), "median_ecc": float(valid.ecc.median())})
    summary = pd.DataFrame(summaries)
    summary.to_csv(OUTPUT / "motion_summary.csv", index=False)
    app_summary = app.groupby(["sequence", "amount"], sort=False).agg(
        edge_gain=("edge_gain_on_raw_support", "median"),
        detail_energy=("fine_detail_energy_ratio", "median"),
        dark_edge=("dark_change_fraction_on_edge_band", "median"),
        off_source_edge=("off_source_strong_edge_fraction", "median"),
    ).reset_index()
    app_summary.to_csv(OUTPUT / "appearance_summary.csv", index=False)
    payload = {"status": "complete", "operation": "symmetric zero-phase local detail gain on fixed R96 E44 outputs",
               "selection": "predeclared epoch-32 holdout steps 0,12,24,36,48 with all locked tiles",
               "amounts": amounts, "motion": summary.to_dict(orient="records"),
               "appearance": app_summary.to_dict(orient="records")}
    (OUTPUT / "summary.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()

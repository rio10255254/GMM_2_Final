"""Compare SEM-truth-normal profiles for Raw, R61, R79, and R108F variants."""
from __future__ import annotations

import json
from pathlib import Path

import cv2
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.io import loadmat
PROJECT_ROOT = Path(__file__).resolve().parents[3]


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "results" / "sem_signed_profile_analysis"
SOURCES = {
    "R61v16": Path(str(PROJECT_ROOT / 'Experiments/R69_ACMContourSEMValidation/results/masks/acm_primary_masks.mat')),
    "R79E23": Path(str(PROJECT_ROOT / 'Experiments/R80_R79E23vsE100GeneralizationValidation/results/acm_sem/R79E23/results/masks/acm_primary_masks.mat')),
    "R108F_full": ROOT / "results" / "acm" / "SEM" / "results" / "masks" / "acm_primary_masks.mat",
    "R108F_flow_only": ROOT / "results" / "acm" / "SEM_operator_ablation" / "flow_only" / "results" / "masks" / "acm_primary_masks.mat",
    "R108F_sharpen_only": ROOT / "results" / "acm" / "SEM_operator_ablation" / "sharpen_only" / "results" / "masks" / "acm_primary_masks.mat",
}
DISTANCE_CENTERS = np.arange(-16.0, 16.1, 1.0)


def signed_distance(mask: np.ndarray) -> np.ndarray:
    binary = mask.astype(np.uint8)
    inside = cv2.distanceTransform(binary, cv2.DIST_L2, 5)
    outside = cv2.distanceTransform(1 - binary, cv2.DIST_L2, 5)
    return outside - inside


def normalized_profile(image: np.ndarray, distance: np.ndarray) -> np.ndarray:
    image = image.astype(np.float32)
    inside = image[distance <= -8.0]
    outside = image[(distance >= 8.0) & (distance <= 16.0)]
    foreground = float(np.median(inside))
    background = float(np.median(outside))
    denominator = foreground - background
    if abs(denominator) < 1e-6:
        return np.full_like(DISTANCE_CENTERS, np.nan, dtype=np.float32)
    objectness = (image - background) / denominator
    profile = []
    for center in DISTANCE_CENTERS:
        selection = (distance >= center - 0.5) & (distance < center + 0.5)
        profile.append(float(np.median(objectness[selection])) if np.any(selection) else np.nan)
    return np.asarray(profile, np.float32)


def crossing(profile: np.ndarray, level: float) -> float:
    valid = np.isfinite(profile)
    x, y = DISTANCE_CENTERS[valid], profile[valid]
    candidates = []
    for index in range(len(x) - 1):
        first, second = y[index] - level, y[index + 1] - level
        if first == 0:
            candidates.append(float(x[index]))
        elif first * second <= 0 and y[index] != y[index + 1]:
            fraction = (level - y[index]) / (y[index + 1] - y[index])
            candidates.append(float(x[index] + fraction * (x[index + 1] - x[index])))
    return min(candidates, key=abs) if candidates else float("nan")


def profile_metrics(profile: np.ndarray) -> dict[str, float]:
    midpoint = crossing(profile, 0.5)
    inner = crossing(profile, 0.9)
    outer = crossing(profile, 0.1)
    valid = profile[np.isfinite(profile)]
    return {
        "midpoint_offset_px": midpoint,
        "transition_width_px": float(outer - inner) if np.isfinite(inner) and np.isfinite(outer) else float("nan"),
        "inside_overshoot": float(max(0.0, np.nanmax(profile[DISTANCE_CENTERS <= 0]) - 1.0)),
        "outside_overshoot": float(max(0.0, -np.nanmin(profile[DISTANCE_CENTERS >= 0]))),
        "monotonic_violation": float(np.maximum(np.diff(valid), 0.0).sum()) if len(valid) > 1 else float("nan"),
    }


def main() -> int:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    loaded = {name: loadmat(path) for name, path in SOURCES.items()}
    authority = loaded["R79E23"]
    truth_masks = authority["truth_masks"].astype(bool)
    truth_cells = authority["truth_cells"]
    raw_cells = authority["raw_cells"]
    exposures = authority["exposures"].reshape(-1).astype(int)
    methods = {"SEM_truth": np.repeat(truth_cells[..., None], len(exposures), axis=3), "Raw": raw_cells}
    for name, payload in loaded.items():
        methods[name] = payload["recon_cells"]
        if payload["recon_cells"].shape != raw_cells.shape:
            raise RuntimeError(f"{name} shape mismatch")
    rows = []
    profiles = {name: [] for name in methods}
    distances = [signed_distance(truth_masks[..., pillar]) for pillar in range(36)]
    for name, cells in methods.items():
        for exposure_index, exposure in enumerate(exposures):
            for pillar in range(36):
                profile = normalized_profile(cells[..., pillar, exposure_index], distances[pillar])
                profiles[name].append(profile)
                rows.append({"method": name, "exposure": int(exposure), "pillar_id": pillar + 1, **profile_metrics(profile)})
    frame = pd.DataFrame(rows)
    frame.to_csv(OUTPUT / "per_observation.csv", index=False)
    summary = frame.groupby("method")[["midpoint_offset_px", "transition_width_px", "inside_overshoot", "outside_overshoot", "monotonic_violation"]].median().reset_index()
    summary.to_csv(OUTPUT / "summary.csv", index=False)
    plt.figure(figsize=(10, 6))
    colors = {"SEM_truth": "black", "Raw": "#777777", "R61v16": "#2878b5", "R79E23": "#2ca02c", "R108F_full": "#d62728", "R108F_flow_only": "#9467bd", "R108F_sharpen_only": "#ff7f0e"}
    for name, values in profiles.items():
        median = np.nanmedian(np.stack(values), axis=0)
        plt.plot(DISTANCE_CENTERS, median, label=name, linewidth=2.0, color=colors[name])
    plt.axvline(0.0, color="black", linewidth=0.8, linestyle="--")
    plt.axhline(0.5, color="black", linewidth=0.8, linestyle=":")
    plt.xlabel("Signed distance from SEM truth boundary (pixels; inside is negative)")
    plt.ylabel("Normalized object intensity")
    plt.title("Median optical transition relative to the SEM truth contour")
    plt.legend(ncol=2)
    plt.tight_layout()
    plt.savefig(OUTPUT / "median_profiles.png", dpi=180)
    plt.close()
    result = {"status": "complete", "observations_per_method": 432, "methods": list(methods), "summary": summary.to_dict(orient="records")}
    (OUTPUT / "state.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

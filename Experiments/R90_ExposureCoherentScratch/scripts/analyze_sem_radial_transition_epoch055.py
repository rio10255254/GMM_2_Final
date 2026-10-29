"""Diagnose whether SEM/ACM exposure failures reflect a real optical-edge shift."""
from __future__ import annotations

import json
from pathlib import Path

import cv2
import numpy as np
import pandas as pd
from scipy.io import loadmat
PROJECT_ROOT = Path(__file__).resolve().parents[3]


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "reports" / "full_validation_epoch055" / "sem_acm"
BASE_MASK = Path(str(PROJECT_ROOT / 'Experiments/R89_MeasurementNativeScratch/results/final_validation/sem_acm_epoch100/acm_validation/results/masks/acm_primary_masks.mat'))
ROOTS = {
    "Raw": ROOT / "results" / "full_validation_epoch055" / "sem_acm" / "locked_optical_inputs",
    "R61v16": Path(str(PROJECT_ROOT / 'Experiments/R69_ACMContourSEMValidation/results/inference_runs/reconstruct_progress_best_tradeoff_in_sem_paired_50x_exposure_stack_20260623_200020/r61v16_psfoff_sem_paired_50x')),
    "R89E100": Path(str(PROJECT_ROOT / 'Experiments/R89_MeasurementNativeScratch/results/final_validation/sem_acm_epoch100/reconstruction')),
    "R90E55": ROOT / "results" / "full_validation_epoch055" / "sem_acm" / "stage_root" / "R90E55" / "reconstruction",
}


def read_gray(path: Path) -> np.ndarray:
    image = cv2.imdecode(np.fromfile(path, dtype=np.uint8), cv2.IMREAD_GRAYSCALE)
    if image is None:
        raise RuntimeError(path)
    return image


def extract_cell(image: np.ndarray, center: np.ndarray, half: int) -> np.ndarray:
    cx, cy = np.rint(center).astype(int)
    padded = np.pad(image, half, mode="symmetric")
    cx += half
    cy += half
    return padded[cy - half:cy + half, cx - half:cx + half].astype(np.float64)


def crossing(profile: np.ndarray, value: float) -> float:
    indices = np.flatnonzero(profile[25:51] >= value)
    return float(25 + indices[0]) if len(indices) else np.nan


def main() -> int:
    base = loadmat(BASE_MASK, variable_names=["opt_centers", "cell_half"])
    centers = np.asarray(base["opt_centers"], dtype=float)
    half = int(np.asarray(base["cell_half"]).squeeze())
    yy, xx = np.mgrid[:2 * half, :2 * half]
    radius = np.hypot(xx - (2 * half - 1) / 2, yy - (2 * half - 1) / 2)
    records = []
    for exposure in range(13, 25):
        for method, directory in ROOTS.items():
            image = read_gray(directory / f"{exposure}.bmp")
            for position, center in enumerate(centers, start=1):
                cell = extract_cell(image, center, half)
                low, high = np.percentile(cell, [1, 99])
                normalized = np.clip((cell - low) / max(high - low, 1e-9), 0, 1)
                profile = np.asarray([
                    normalized[(radius >= value) & (radius < value + 1)].mean()
                    for value in range(52)
                ])
                inside, outside = np.median(profile[10:25]), np.median(profile[47:51])
                amplitude = outside - inside
                q25, q50, q75 = inside + 0.25 * amplitude, inside + 0.50 * amplitude, inside + 0.75 * amplitude
                derivative = np.gradient(profile)
                records.append({
                    "exposure": exposure, "method": method, "grid_position": position,
                    "midpoint_radius_px": crossing(profile, q50),
                    "gradient_peak_radius_px": float(25 + np.argmax(derivative[25:51])),
                    "transition_width_px": crossing(profile, q75) - crossing(profile, q25),
                    "normalized_contrast": float(amplitude),
                    "inside_mean_gray": float(cell[radius < 25].mean()),
                    "edge_annulus_mean_gray": float(cell[(radius >= 35) & (radius < 42)].mean()),
                    "outside_mean_gray": float(cell[(radius >= 47) & (radius < 51)].mean()),
                })
    table = pd.DataFrame(records)
    summary = table.groupby(["exposure", "method"], observed=True)[
        ["midpoint_radius_px", "gradient_peak_radius_px", "transition_width_px", "normalized_contrast",
         "inside_mean_gray", "edge_annulus_mean_gray", "outside_mean_gray"]
    ].median().reset_index()
    raw = summary.loc[summary["method"] == "Raw"].set_index("exposure")
    summary["midpoint_minus_raw_px"] = summary.apply(
        lambda row: row["midpoint_radius_px"] - raw.loc[int(row["exposure"]), "midpoint_radius_px"], axis=1
    )
    summary["gradient_peak_minus_raw_px"] = summary.apply(
        lambda row: row["gradient_peak_radius_px"] - raw.loc[int(row["exposure"]), "gradient_peak_radius_px"], axis=1
    )
    OUTPUT.mkdir(parents=True, exist_ok=True)
    table.to_csv(OUTPUT / "radial_transition_per_position.csv", index=False, encoding="utf-8-sig")
    summary.to_csv(OUTPUT / "radial_transition_summary.csv", index=False, encoding="utf-8-sig")
    r90 = summary.loc[summary["method"] == "R90E55"].set_index("exposure")
    raw_summary = summary.loc[summary["method"] == "Raw"].set_index("exposure")
    def region_changes(exposure: int) -> dict[str, float]:
        return {
            "inside_change_gray": float(r90.loc[exposure, "inside_mean_gray"] - raw_summary.loc[exposure, "inside_mean_gray"]),
            "edge_annulus_change_gray": float(r90.loc[exposure, "edge_annulus_mean_gray"] - raw_summary.loc[exposure, "edge_annulus_mean_gray"]),
            "outside_change_gray": float(r90.loc[exposure, "outside_mean_gray"] - raw_summary.loc[exposure, "outside_mean_gray"]),
        }
    report = {
        "status": "complete",
        "role": "diagnostic independent of ACM segmentation",
        "exposure_18": {
            "midpoint_shift_outward_px": float(r90.loc[18, "midpoint_minus_raw_px"]),
            "gradient_peak_shift_outward_px": float(r90.loc[18, "gradient_peak_minus_raw_px"]),
            "transition_width_px": float(r90.loc[18, "transition_width_px"]),
            "regional_photometric_change": region_changes(18),
        },
        "exposure_19": {
            "midpoint_shift_outward_px": float(r90.loc[19, "midpoint_minus_raw_px"]),
            "gradient_peak_shift_outward_px": float(r90.loc[19, "gradient_peak_minus_raw_px"]),
            "transition_width_px": float(r90.loc[19, "transition_width_px"]),
            "regional_photometric_change": region_changes(19),
        },
        "exposure_17_control": {"regional_photometric_change": region_changes(17)},
        "acm_exposure_18_failure_has_independent_edge_shift_support": bool(
            r90.loc[18, "midpoint_minus_raw_px"] >= 2 and r90.loc[18, "gradient_peak_minus_raw_px"] >= 2
        ),
        "claim_limit": "Radial profiles summarize the optical transition around approximately round pillars; SEM ACM remains the primary non-circular contour comparison.",
    }
    (OUTPUT / "radial_transition_diagnostic.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

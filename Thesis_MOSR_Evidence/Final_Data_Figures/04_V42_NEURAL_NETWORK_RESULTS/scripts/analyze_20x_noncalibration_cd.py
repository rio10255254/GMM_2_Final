"""Supplementary 20x CD consistency check on a non-PSF-calibration frame."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
from PIL import Image
from scipy.io import savemat

from analyze_wiener_three_way_results import (
    _measure_half_height_width,
    _measure_radial_width,
)
PROJECT_ROOT = Path(__file__).resolve().parents[4]


PACKAGE = Path(__file__).resolve().parents[1]
EVIDENCE = PACKAGE.parent
CURRENT = EVIDENCE / "01_CURRENT_THESIS_RESULTS_V42_CENTER9"
WIENER = PACKAGE / "source_validation" / "wiener_baseline_20260715"
OUTPUT = WIENER / "supplementary_20x_cd"
TABLES = OUTPUT / "tables"
TABLES.mkdir(parents=True, exist_ok=True)

RAW_PATH = Path(
    str(PROJECT_ROOT / 'Analyses/20260704_20x_5x_analysis/raw_inputs/20x_1um/bmp/frame_0049.bmp')
)
WIENER_PATH = WIENER / "reconstructions" / "x20x_1um" / "frame_0049.bmp"
MOSR_PATH = (
    EVIDENCE
    / "02_V42_E120_SOURCE_MATERIAL"
    / "reconstructions"
    / "20x_1um"
    / "frame_0049.bmp"
)


def read_gray(path: Path) -> np.ndarray:
    if not path.is_file():
        raise FileNotFoundError(path)
    with Image.open(path) as image:
        return np.asarray(image.convert("L"), dtype=np.float64)


def common_center_refinement(
    raw: np.ndarray, centers: np.ndarray, radius_px: float
) -> tuple[np.ndarray, np.ndarray]:
    """Estimate one shared subpixel grid shift from Raw; reuse it for all methods."""
    shifts: list[list[float]] = []
    half_window = int(np.ceil(radius_px + 4.0))
    for center_x, center_y in centers:
        x0 = int(np.floor(center_x)) - half_window
        x1 = int(np.floor(center_x)) + half_window + 1
        y0 = int(np.floor(center_y)) - half_window
        y1 = int(np.floor(center_y)) + half_window + 1
        yy, xx = np.mgrid[y0:y1, x0:x1]
        radius = np.hypot(xx - center_x, yy - center_y)
        values = raw[y0:y1, x0:x1]
        background = float(
            np.median(values[(radius >= radius_px + 1.4) & (radius <= radius_px + 3.4)])
        )
        weights = np.maximum(background - values, 0.0) * (radius <= radius_px + 0.9)
        total = float(weights.sum())
        if total <= 1e-9:
            raise RuntimeError("A Raw pillar did not provide a valid darkness centroid")
        shifts.append(
            [
                float((weights * (xx - center_x)).sum() / total),
                float((weights * (yy - center_y)).sum() / total),
            ]
        )
    shared_shift = np.median(np.asarray(shifts, dtype=float), axis=0)
    return centers + shared_shift, shared_shift


def main() -> None:
    config = json.loads(
        (CURRENT / "config" / "sequence_center9_50x20x.json").read_text(
            encoding="utf-8"
        )
    )["sequences"]["20x_1um"]
    object_um_per_px = float(config["object_um_per_px"])
    radius_px = float(config["radius_px"])
    pillar_ids = np.asarray([int(row[0]) for row in config["centers"]], dtype=int)
    centers = np.asarray([[row[1], row[2]] for row in config["centers"]], dtype=float)

    audit = pd.read_csv(
        WIENER / "displacement_audit" / "tables" / "all_adjacent_pairs_audit.csv"
    )
    sequence_steps = audit.loc[audit["sequence"].eq("20x_1um")].copy()
    if len(sequence_steps) != 49 or not sequence_steps["raw_boundary_dx_um"].notna().all():
        raise RuntimeError("Expected 49 finite Raw displacement steps for 20x_1um")
    cumulative_dx_px = float(sequence_steps["raw_boundary_dx_um"].sum()) / object_um_per_px
    centers[:, 0] += cumulative_dx_px

    images = {
        "raw": read_gray(RAW_PATH),
        "wiener": read_gray(WIENER_PATH),
        "mosr": read_gray(MOSR_PATH),
    }
    centers, shared_shift = common_center_refinement(images["raw"], centers, radius_px)

    sem_table = pd.read_csv(CURRENT / "cd" / "tables" / "center9_cd_per_pillar.csv")
    sem_by_id = sem_table.set_index("sem_index")["sem_diameter_um"].to_dict()
    missing = sorted(set(pillar_ids) - set(sem_by_id))
    if missing:
        raise RuntimeError(f"Missing SEM identities: {missing}")

    methods = {
        "horizontal_strip": _measure_half_height_width,
        "radial_mean": _measure_radial_width,
    }
    thresholds = np.round(np.arange(0.35, 0.651, 0.05), 2)
    records: list[dict[str, object]] = []
    for case, image in images.items():
        for measurement_mode, measure in methods.items():
            for threshold_fraction in thresholds:
                for position, (pillar_id, center) in enumerate(
                    zip(pillar_ids, centers), start=1
                ):
                    result = measure(
                        image,
                        float(center[0]),
                        float(center[1]),
                        radius_px,
                        float(threshold_fraction),
                    )
                    diameter_um = float(result.get("width_px", np.nan)) * object_um_per_px
                    sem_diameter_um = float(sem_by_id[int(pillar_id)])
                    signed_error_nm = (diameter_um - sem_diameter_um) * 1000.0
                    records.append(
                        {
                            "case": case,
                            "measurement_mode": measurement_mode,
                            "threshold_fraction": float(threshold_fraction),
                            "center9_position": position,
                            "sem_index": int(pillar_id),
                            "center_x_px": float(center[0]),
                            "center_y_px": float(center[1]),
                            "sem_diameter_um": sem_diameter_um,
                            "diameter_um": diameter_um,
                            "signed_error_nm": signed_error_nm,
                            "abs_error_nm": abs(signed_error_nm),
                            "status": str(result["status"]),
                        }
                    )
    per_measurement = pd.DataFrame(records)
    if not (per_measurement["status"] == "ok").all():
        failed = per_measurement.loc[per_measurement["status"] != "ok"]
        raise RuntimeError(f"Supplementary 20x CD has {len(failed)} failed crossings")
    if not np.isfinite(
        per_measurement[["diameter_um", "signed_error_nm", "abs_error_nm"]].to_numpy(float)
    ).all():
        raise RuntimeError("Supplementary 20x CD contains non-finite values")

    summary_records: list[dict[str, object]] = []
    for case, group in per_measurement.groupby("case", sort=False):
        error = group["signed_error_nm"].to_numpy(float)
        summary_records.append(
            {
                "case": case,
                "observation_count": len(group),
                "pillar_count": group["sem_index"].nunique(),
                "measurement_mode_count": group["measurement_mode"].nunique(),
                "threshold_count": group["threshold_fraction"].nunique(),
                "pooled_median_abs_error_nm": float(np.median(np.abs(error))),
                "pooled_mean_abs_error_nm": float(np.mean(np.abs(error))),
                "pooled_rmse_nm": float(np.sqrt(np.mean(np.square(error)))),
                "pooled_mean_signed_bias_nm": float(np.mean(error)),
            }
        )
    summary = pd.DataFrame(summary_records)

    range_records: list[dict[str, object]] = []
    for (case, position, sem_index), group in per_measurement.groupby(
        ["case", "center9_position", "sem_index"], sort=False
    ):
        range_records.append(
            {
                "case": case,
                "center9_position": int(position),
                "sem_index": int(sem_index),
                "sem_diameter_um": float(group["sem_diameter_um"].iloc[0]),
                "diameter_min_um": float(group["diameter_um"].min()),
                "diameter_max_um": float(group["diameter_um"].max()),
                "diameter_median_um": float(group["diameter_um"].median()),
                "median_abs_error_nm": float(group["abs_error_nm"].median()),
            }
        )
    per_pillar_range = pd.DataFrame(range_records)

    per_measurement.to_csv(
        TABLES / "20x_frame49_cd_per_measurement.csv", index=False, float_format="%.12g"
    )
    summary.to_csv(TABLES / "20x_frame49_cd_summary.csv", index=False, float_format="%.12g")
    per_pillar_range.to_csv(
        TABLES / "20x_frame49_cd_per_pillar_range.csv", index=False, float_format="%.12g"
    )

    savemat(
        OUTPUT / "20x_frame49_cd_plot_data.mat",
        {
            "pillar_ids": pillar_ids.astype(float),
            "centers_xy": centers,
            "shared_center_shift_xy_px": shared_shift,
            "cumulative_dx_px": cumulative_dx_px,
        },
    )
    manifest = {
        "purpose": "supplementary same-system 20x CD consistency check",
        "frame_rule": "frame 49 of the 20x 1.0 um sequence; not the frame used to fit the 20x PSF",
        "center_rule": "one Raw-derived shared grid shift, reused unchanged for Raw, Wiener, and MOSR",
        "measurement_rule": "35-65 percent thresholds with horizontal-strip and radial-mean profiles",
        "scope": "same sample and imaging domain; not an independent generalization test",
        "raw_image": str(RAW_PATH),
        "wiener_image": str(WIENER_PATH),
        "mosr_image": str(MOSR_PATH),
        "cumulative_raw_dx_px": cumulative_dx_px,
        "shared_center_shift_xy_px": shared_shift.tolist(),
    }
    (OUTPUT / "manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(summary.to_string(index=False))
    print(OUTPUT)


if __name__ == "__main__":
    main()

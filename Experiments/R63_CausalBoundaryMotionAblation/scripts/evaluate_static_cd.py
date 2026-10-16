"""Evaluate threshold-robust SEM-referenced CD at 50x and 20x."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from PIL import Image
from scipy.ndimage import map_coordinates


EXPERIMENT_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = EXPERIMENT_ROOT.parents[1]
FIG_ROOT = REPO_ROOT / "Thesis_MOSR_Evidence" / "Final_Data_Figures"
CURRENT = FIG_ROOT / "01_CURRENT_THESIS_RESULTS_V42_CENTER9"
CHAPTER = FIG_ROOT / "04_V42_NEURAL_NETWORK_RESULTS"
SOURCE_TABLE = CURRENT / "cd" / "tables" / "center9_cd_per_pillar.csv"
SEQUENCE_CONFIG = CURRENT / "config" / "sequence_center9_50x20x.json"
FIXED_20X_MANIFEST = (
    CHAPTER
    / "source_validation"
    / "wiener_baseline_20260715"
    / "supplementary_20x_cd"
    / "manifest.json"
)
MEASURE_SCRIPT_ROOT = CHAPTER / "scripts"
sys.path.insert(0, str(MEASURE_SCRIPT_ROOT))
from analyze_wiener_three_way_results import (  # noqa: E402
    _measure_half_height_width,
    _measure_radial_width,
)


def read_gray(path: Path) -> np.ndarray:
    if not path.is_file():
        raise FileNotFoundError(path)
    with Image.open(path) as image:
        return np.asarray(image.convert("L"), dtype=np.float64)


def radial_edge_guardrails(
    image: np.ndarray, center_x: float, center_y: float, radius_px: float
) -> dict[str, float]:
    max_radius = max(18.0, radius_px * 2.2)
    radii = np.arange(0.0, max_radius + 0.051, 0.05)
    angles = np.linspace(0.0, 2.0 * np.pi, 720, endpoint=False)
    xx = center_x + np.outer(np.cos(angles), radii)
    yy = center_y + np.outer(np.sin(angles), radii)
    darkness = 1.0 - image / 255.0
    samples = map_coordinates(darkness, [yy.ravel(), xx.ravel()], order=1, mode="nearest")
    profile = samples.reshape(xx.shape).mean(axis=0)
    high = float(np.percentile(profile[radii <= max(2.0, radius_px * 0.42)], 80))
    background_mask = radii >= radius_px * 1.45
    low = float(np.percentile(profile[background_mask], 20))
    contrast = high - low
    if contrast <= 1e-6:
        raise RuntimeError("Invalid radial contrast")

    def crossing(fraction: float) -> float:
        threshold = low + fraction * contrast
        indices = np.where((profile[:-1] >= threshold) & (profile[1:] < threshold))[0]
        if not len(indices):
            return float("nan")
        index = int(indices[np.argmin(np.abs(radii[indices] - radius_px))])
        y0, y1 = float(profile[index]), float(profile[index + 1])
        if abs(y1 - y0) < 1e-12:
            return float((radii[index] + radii[index + 1]) * 0.5)
        fraction_between = np.clip((threshold - y0) / (y1 - y0), 0.0, 1.0)
        return float(radii[index] + fraction_between * (radii[index + 1] - radii[index]))

    r90, r50, r10 = crossing(0.9), crossing(0.5), crossing(0.1)
    if not np.isfinite([r90, r50, r10]).all():
        raise RuntimeError("Missing radial edge crossing")
    outer = profile[(radii >= r10 + max(0.5, radius_px * 0.10)) & (radii <= max_radius)]
    ringing = float(np.mean(np.abs(np.diff(outer)))) if len(outer) >= 2 else 0.0
    return {
        "edge_radius_50_px": r50,
        "edge_width_10_90_px": r10 - r90,
        "contrast": contrast,
        "outer_ringing_energy": ringing,
    }


def build_populations(recon_root: Path) -> list[dict[str, object]]:
    sem = pd.read_csv(SOURCE_TABLE)
    sem_by_id = sem.set_index("sem_index")["sem_diameter_um"].to_dict()
    raw_50 = Path(sem["raw_source_image"].iloc[0])
    method_50 = recon_root / "static_50x_sem" / raw_50.name
    if not method_50.is_file():
        method_50 = recon_root / "100mg_static" / raw_50.name
    pop50 = {
        "magnification": "50x",
        "object_um_per_px": 0.069,
        "radius_px": float(np.median(sem["reference_radius_px"])),
        "pillar_ids": sem["sem_index"].astype(int).to_numpy(),
        "centers": sem[["raw_x_px", "raw_y_px"]].to_numpy(float),
        "sem_diameters": np.asarray([sem_by_id[int(value)] for value in sem["sem_index"]], dtype=float),
        "raw_path": raw_50,
        "method_path": method_50,
        "independence": "package-manifest-unseen capture family; earlier checkpoint ancestry not proven",
    }

    config = json.loads(SEQUENCE_CONFIG.read_text(encoding="utf-8"))["sequences"]["20x_1um"]
    fixed = json.loads(FIXED_20X_MANIFEST.read_text(encoding="utf-8"))
    pillar_ids = np.asarray([int(row[0]) for row in config["centers"]], dtype=int)
    centers = np.asarray([[row[1], row[2]] for row in config["centers"]], dtype=float)
    centers[:, 0] += float(fixed["cumulative_raw_dx_px"])
    centers += np.asarray(fixed["shared_center_shift_xy_px"], dtype=float)
    raw_20 = Path(fixed["raw_image"])
    method_20 = recon_root / "20x_1um" / raw_20.name
    pop20 = {
        "magnification": "20x",
        "object_um_per_px": float(config["object_um_per_px"]),
        "radius_px": float(config["radius_px"]),
        "pillar_ids": pillar_ids,
        "centers": centers,
        "sem_diameters": np.asarray([sem_by_id[int(value)] for value in pillar_ids], dtype=float),
        "raw_path": raw_20,
        "method_path": method_20,
        "independence": "same capture family represented in training",
    }
    return [pop50, pop20]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--variant", required=True)
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--recon-root", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()

    modes = {
        "horizontal_strip": _measure_half_height_width,
        "radial_mean": _measure_radial_width,
    }
    thresholds = np.round(np.arange(0.35, 0.651, 0.05), 2)
    measurement_records: list[dict[str, object]] = []
    edge_records: list[dict[str, object]] = []
    populations = build_populations(args.recon_root)
    for population in populations:
        images = {
            "Raw": read_gray(Path(population["raw_path"])),
            "Method": read_gray(Path(population["method_path"])),
        }
        for method, image in images.items():
            for position, (pillar_id, center, sem_diameter) in enumerate(
                zip(population["pillar_ids"], population["centers"], population["sem_diameters"]),
                start=1,
            ):
                guard = radial_edge_guardrails(
                    image,
                    float(center[0]),
                    float(center[1]),
                    float(population["radius_px"]),
                )
                edge_records.append(
                    {
                        "variant": args.variant,
                        "seed": args.seed,
                        "magnification": population["magnification"],
                        "method": method,
                        "center9_position": position,
                        "pillar_id": int(pillar_id),
                        "sem_reference_radius_px": float(sem_diameter)
                        / (2.0 * float(population["object_um_per_px"])),
                        "edge_radius_50_px": guard["edge_radius_50_px"],
                        "edge_radius_signed_error_nm": (
                            guard["edge_radius_50_px"]
                            * float(population["object_um_per_px"])
                            - float(sem_diameter) / 2.0
                        )
                        * 1000.0,
                        "edge_radius_abs_error_nm": abs(
                            guard["edge_radius_50_px"]
                            * float(population["object_um_per_px"])
                            - float(sem_diameter) / 2.0
                        )
                        * 1000.0,
                        "edge_width_10_90_px": guard["edge_width_10_90_px"],
                        "edge_width_10_90_nm": guard["edge_width_10_90_px"] * float(population["object_um_per_px"]) * 1000.0,
                        "outer_ringing_energy": guard["outer_ringing_energy"],
                        "contrast": guard["contrast"],
                    }
                )
                for mode, measure in modes.items():
                    for threshold in thresholds:
                        result = measure(
                            image,
                            float(center[0]),
                            float(center[1]),
                            float(population["radius_px"]),
                            float(threshold),
                        )
                        diameter_um = float(result.get("width_px", np.nan)) * float(population["object_um_per_px"])
                        signed_error_nm = (diameter_um - float(sem_diameter)) * 1000.0
                        measurement_records.append(
                            {
                                "variant": args.variant,
                                "seed": args.seed,
                                "magnification": population["magnification"],
                                "independence": population["independence"],
                                "method": method,
                                "measurement_mode": mode,
                                "threshold_fraction": float(threshold),
                                "center9_position": position,
                                "pillar_id": int(pillar_id),
                                "sem_diameter_um": float(sem_diameter),
                                "diameter_um": diameter_um,
                                "signed_error_nm": signed_error_nm,
                                "abs_error_nm": abs(signed_error_nm),
                                "status": str(result["status"]),
                            }
                        )

    measurements = pd.DataFrame(measurement_records)
    edges = pd.DataFrame(edge_records)
    failed = measurements.loc[measurements["status"].ne("ok")]
    if len(failed):
        raise RuntimeError(f"Static CD has {len(failed)} failed crossings")
    if not np.isfinite(measurements[["diameter_um", "signed_error_nm", "abs_error_nm"]].to_numpy(float)).all():
        raise RuntimeError("Static CD contains non-finite values")

    summary_records: list[dict[str, object]] = []
    for (magnification, method), group in measurements.groupby(["magnification", "method"], sort=False):
        error = group["signed_error_nm"].to_numpy(float)
        edge_group = edges.loc[edges["magnification"].eq(magnification) & edges["method"].eq(method)]
        pillar_ranges = group.groupby("pillar_id")["diameter_um"].agg(lambda values: float(values.max() - values.min()))
        summary_records.append(
            {
                "variant": args.variant,
                "seed": args.seed,
                "magnification": magnification,
                "method": method,
                "observation_count": len(group),
                "pillar_count": group["pillar_id"].nunique(),
                "pooled_median_abs_error_nm": float(np.median(np.abs(error))),
                "pooled_mean_abs_error_nm": float(np.mean(np.abs(error))),
                "pooled_rmse_nm": float(np.sqrt(np.mean(np.square(error)))),
                "max_abs_error_nm": float(np.max(np.abs(error))),
                "median_cd_bound_width_nm": float(np.median(pillar_ranges.to_numpy(float)) * 1000.0),
                "median_edge_width_10_90_nm": float(edge_group["edge_width_10_90_nm"].median()),
                "median_edge_radius_abs_error_nm": float(
                    edge_group["edge_radius_abs_error_nm"].median()
                ),
                "median_outer_ringing_energy": float(edge_group["outer_ringing_energy"].median()),
                "median_contrast": float(edge_group["contrast"].median()),
            }
        )
    summary = pd.DataFrame(summary_records)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    measurements.to_csv(args.output_dir / "static_cd_per_measurement.csv", index=False, float_format="%.12g")
    edges.to_csv(args.output_dir / "static_edge_guardrails.csv", index=False, float_format="%.12g")
    summary.to_csv(args.output_dir / "static_cd_summary.csv", index=False, float_format="%.12g")
    metadata = {
        "variant": args.variant,
        "seed": args.seed,
        "thresholds": thresholds.tolist(),
        "measurement_modes": list(modes),
        "profiles_per_radial_sample": 720,
        "sem_value_interpretation": "provided values are radii and are doubled to diameter in the locked source table",
        "edge_radius_50_role": "diagnostic only; excluded from claim decisions in favor of the locked 35-65 percent bounds",
        "display_adjustment": "none",
    }
    (args.output_dir / "metadata.json").write_text(
        json.dumps(metadata, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(summary.to_string(index=False))


if __name__ == "__main__":
    main()

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import cv2
import numpy as np
import pandas as pd
from scipy.ndimage import gaussian_filter1d, map_coordinates
PROJECT_ROOT = Path(__file__).resolve().parents[4]


EXPERIMENT = Path(__file__).resolve().parent
MANIFEST_PATH = EXPERIMENT / "evaluation_manifest.json"
PILLAR_SEM_META = {
    "50x": Path(
        str(PROJECT_ROOT / 'PSF_Fitting/output/deconvolution_baseline_psf_20260715/50x/selected_frame.json')
    ),
    "20x": Path(
        str(PROJECT_ROOT / 'PSF_Fitting/output/deconvolution_baseline_psf_20260715/20x/selected_frame.json')
    ),
}
STATIC_SEQUENCES = {"50x": "50x_x_0p5um", "20x": "20x_0p5um"}
CONTRAST_FRACTIONS = tuple(np.arange(0.35, 0.6501, 0.05).round(2))


@dataclass(frozen=True)
class RadialMeasurement:
    cd_px: float
    angular_mad_px: float
    edge_width_px: float
    ringing_ratio: float
    core_level: float
    background_level: float
    michelson_contrast: float
    valid_angle_fraction: float


def read_gray(path: Path) -> np.ndarray:
    image = cv2.imdecode(np.fromfile(path, dtype=np.uint8), cv2.IMREAD_GRAYSCALE)
    if image is None:
        raise FileNotFoundError(path)
    return image.astype(np.float64) / 255.0


def crossing_radius(profile: np.ndarray, radii: np.ndarray, threshold: float) -> float:
    smoothed = gaussian_filter1d(profile, sigma=6.0, mode="nearest")
    above = smoothed >= threshold
    crossings = np.flatnonzero((~above[:-1]) & above[1:])
    if crossings.size == 0:
        return float("nan")
    index = int(crossings[0])
    y0 = float(smoothed[index])
    y1 = float(smoothed[index + 1])
    if y1 == y0:
        return float(radii[index])
    fraction = (threshold - y0) / (y1 - y0)
    return float(radii[index] + fraction * (radii[index + 1] - radii[index]))


def measure_radial_feature_sweep(
    image: np.ndarray,
    center_xy: tuple[float, float],
    pitch_px: float,
    polarity: str,
    contrast_fractions: tuple[float, ...],
) -> dict[float, RadialMeasurement]:
    if polarity not in {"dark", "bright"}:
        raise ValueError(polarity)
    signal = image if polarity == "dark" else -image
    radial_step = 0.05
    radii = np.arange(0.0, 0.38 * pitch_px + radial_step, radial_step)
    angles = np.linspace(0.0, 2.0 * np.pi, 360, endpoint=False)
    x = float(center_xy[0]) + np.cos(angles)[:, None] * radii[None, :]
    y = float(center_xy[1]) + np.sin(angles)[:, None] * radii[None, :]
    samples = map_coordinates(signal, [y, x], order=3, mode="reflect")
    core_mask = radii <= 0.07 * pitch_px
    background_mask = (radii >= 0.30 * pitch_px) & (radii <= 0.36 * pitch_px)
    core = float(np.median(samples[:, core_mask]))
    background = float(np.median(samples[:, background_mask]))
    contrast = background - core
    if not np.isfinite(contrast) or contrast <= 1.0e-4:
        raise RuntimeError("Feature polarity or contrast is invalid")

    def crossings(fraction: float) -> np.ndarray:
        threshold = core + fraction * contrast
        return np.asarray(
            [crossing_radius(profile, radii, threshold) for profile in samples],
            dtype=float,
        )

    edge_low = crossings(0.10)
    edge_high = crossings(0.90)
    widths = edge_high - edge_low
    widths = widths[np.isfinite(widths) & (widths >= 0.0)]
    if len(widths) < 324:
        raise RuntimeError("Fewer than 90% of angular traces produced a valid edge width")

    median_profile = gaussian_filter1d(np.median(samples, axis=0), sigma=6.0, mode="nearest")
    normalized = (median_profile - core) / contrast
    changes = np.diff(normalized[radii <= 0.30 * pitch_px])
    outward = float(np.sum(changes[changes > 0]))
    inward = float(-np.sum(changes[changes < 0]))
    original_core = -core if polarity == "bright" else core
    original_background = -background if polarity == "bright" else background
    michelson = abs(original_background - original_core) / max(
        abs(original_background + original_core), np.finfo(float).eps
    )
    edge_width = float(np.median(widths))
    ringing_ratio = inward / max(outward, np.finfo(float).eps)
    results: dict[float, RadialMeasurement] = {}
    for fraction in contrast_fractions:
        edge_selected = crossings(float(fraction))
        valid = np.isfinite(edge_selected)
        if np.count_nonzero(valid) < 324:
            raise RuntimeError(
                f"Fewer than 90% of angular traces crossed threshold {fraction:.2f}"
            )
        paired = edge_selected[:180] + edge_selected[180:]
        paired = paired[np.isfinite(paired)]
        median_cd = float(np.median(paired))
        angular_mad = float(np.median(np.abs(paired - median_cd)))
        results[float(fraction)] = RadialMeasurement(
            cd_px=median_cd,
            angular_mad_px=angular_mad,
            edge_width_px=edge_width,
            ringing_ratio=ringing_ratio,
            core_level=original_core,
            background_level=original_background,
            michelson_contrast=float(michelson),
            valid_angle_fraction=float(np.mean(valid)),
        )
    return results


def method_sequence_dir(
    manifest: dict[str, Any],
    method: str,
    sequence_name: str,
    raw_dir: Path,
) -> Path:
    if method == "Raw":
        return raw_dir
    root = Path(PROJECT_ROOT / manifest["methods"][method]["sequence_root"])
    mapped = manifest["sequence_name_map"][sequence_name][method]
    return root / mapped


def circular_references(
    manifest: dict[str, Any],
    magnification: str,
) -> tuple[dict[str, Any], dict[str, list[dict[str, Any]]]]:
    pillar_config = json.loads(Path(PROJECT_ROOT / manifest["pillar_config"]).read_text(encoding="utf-8"))
    via_config = json.loads(Path(PROJECT_ROOT / manifest["via_config"]).read_text(encoding="utf-8"))
    sequence_name = STATIC_SEQUENCES[magnification]
    pillar_sequence = pillar_config["sequences"][sequence_name]
    via_sequence = via_config["sequences"][sequence_name]
    pillar_meta = json.loads(PILLAR_SEM_META[magnification].read_text(encoding="utf-8"))
    pillar_sem = np.asarray(pillar_meta["image_oriented_sem_cd_nm"], dtype=float).reshape(-1)
    pillar_centers = [
        {
            "feature_id": f"P{int(center[0])}",
            "sem_cell": "",
            "x": float(center[1]),
            "y": float(center[2]),
            "sem_cd_nm": float(sem_cd),
        }
        for center, sem_cd in zip(pillar_sequence["centers"], pillar_sem)
    ]
    via_centers = [
        {
            "feature_id": str(center["sem_cell"]),
            "sem_cell": str(center["sem_cell"]),
            "x": float(center["x"]),
            "y": float(center["y"]),
            "sem_cd_nm": float(center["sem_diameter_um"]) * 1000.0,
        }
        for center in via_sequence["centers"]
    ]
    return pillar_sequence, {"pillar": pillar_centers, "via": via_centers}


def interval_summary(table: pd.DataFrame) -> pd.DataFrame:
    records: list[dict[str, object]] = []
    grouping = ["magnification", "morphology", "method", "feature_id"]
    for keys, group in table.groupby(grouping, sort=False):
        sem_cd = float(group["sem_cd_nm"].iloc[0])
        lower = float(group["apparent_cd_nm"].min())
        upper = float(group["apparent_cd_nm"].max())
        midpoint = 0.5 * (lower + upper)
        distance = max(lower - sem_cd, 0.0, sem_cd - upper)
        first = group.iloc[0]
        records.append(
            {
                "magnification": keys[0],
                "morphology": keys[1],
                "method": keys[2],
                "feature_id": keys[3],
                "sem_cell": first["sem_cell"],
                "sem_cd_nm": sem_cd,
                "cd_lower_nm": lower,
                "cd_upper_nm": upper,
                "cd_interval_midpoint_nm": midpoint,
                "cd_interval_width_nm": upper - lower,
                "sem_inside_interval": bool(lower <= sem_cd <= upper),
                "distance_from_interval_nm": distance,
                "midpoint_error_nm": midpoint - sem_cd,
                "midpoint_absolute_error_nm": abs(midpoint - sem_cd),
                "edge_width_nm": float(group["edge_width_nm"].median()),
                "ringing_ratio": float(group["ringing_ratio"].median()),
                "michelson_contrast": float(group["michelson_contrast"].median()),
                "angular_mad_nm": float(group["angular_mad_nm"].median()),
            }
        )
    return pd.DataFrame(records)


def method_summary(intervals: pd.DataFrame) -> pd.DataFrame:
    records: list[dict[str, object]] = []
    grouping = ["magnification", "morphology", "method"]
    for keys, group in intervals.groupby(grouping, sort=False):
        error = group["midpoint_error_nm"].to_numpy(dtype=float)
        records.append(
            {
                "magnification": keys[0],
                "morphology": keys[1],
                "method": keys[2],
                "n_features": len(group),
                "sem_interval_coverage_count": int(group["sem_inside_interval"].sum()),
                "sem_interval_coverage_fraction": float(group["sem_inside_interval"].mean()),
                "mean_distance_from_interval_nm": float(group["distance_from_interval_nm"].mean()),
                "median_distance_from_interval_nm": float(group["distance_from_interval_nm"].median()),
                "midpoint_bias_nm": float(np.mean(error)),
                "midpoint_mae_nm": float(np.mean(np.abs(error))),
                "midpoint_rmse_nm": float(np.sqrt(np.mean(error**2))),
                "mean_cd_interval_width_nm": float(group["cd_interval_width_nm"].mean()),
                "mean_edge_width_nm": float(group["edge_width_nm"].mean()),
                "median_edge_width_nm": float(group["edge_width_nm"].median()),
                "mean_ringing_ratio": float(group["ringing_ratio"].mean()),
                "max_ringing_ratio": float(group["ringing_ratio"].max()),
                "mean_michelson_contrast": float(group["michelson_contrast"].mean()),
                "mean_angular_mad_nm": float(group["angular_mad_nm"].mean()),
            }
        )
    return pd.DataFrame(records)


def main(output_root: Path, allow_missing: bool) -> None:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    methods = list(manifest["methods"])
    rows: list[dict[str, object]] = []
    missing: list[str] = []
    for magnification, sequence_name in STATIC_SEQUENCES.items():
        sequence, references = circular_references(manifest, magnification)
        raw_dir = Path(sequence["raw_dir"])
        um_per_px = float(sequence["object_um_per_px"])
        pitch_px = float(sequence["pitch_px"])
        for method in methods:
            directory = method_sequence_dir(
                manifest,
                method,
                sequence_name,
                raw_dir,
            )
            image_path = directory / str(sequence["first_frame"])
            if not image_path.is_file():
                message = f"{method} {magnification}: {image_path}"
                if allow_missing:
                    missing.append(message)
                    print(f"Skipping {message}", flush=True)
                    continue
                raise FileNotFoundError(image_path)
            image = read_gray(image_path)
            for morphology, centers in references.items():
                polarity = "dark" if morphology == "pillar" else "bright"
                for center in centers:
                    measurements = measure_radial_feature_sweep(
                        image,
                        (float(center["x"]), float(center["y"])),
                        pitch_px,
                        polarity,
                        CONTRAST_FRACTIONS,
                    )
                    for fraction in CONTRAST_FRACTIONS:
                        measurement = measurements[float(fraction)]
                        rows.append(
                            {
                                "magnification": magnification,
                                "morphology": morphology,
                                "method": method,
                                "feature_id": center["feature_id"],
                                "sem_cell": center["sem_cell"],
                                "sem_cd_nm": center["sem_cd_nm"],
                                "contrast_fraction": float(fraction),
                                "apparent_cd_nm": measurement.cd_px * um_per_px * 1000.0,
                                "angular_mad_nm": measurement.angular_mad_px * um_per_px * 1000.0,
                                "edge_width_nm": measurement.edge_width_px * um_per_px * 1000.0,
                                "ringing_ratio": measurement.ringing_ratio,
                                "core_level": measurement.core_level,
                                "background_level": measurement.background_level,
                                "michelson_contrast": measurement.michelson_contrast,
                                "valid_angle_fraction": measurement.valid_angle_fraction,
                                "image_path": str(image_path),
                            }
                        )
            print(f"{magnification} {method}: measured pillar and via", flush=True)

    detailed = pd.DataFrame(rows)
    intervals = interval_summary(detailed)
    summary = method_summary(intervals)
    output_root.mkdir(parents=True, exist_ok=True)
    detailed.to_csv(output_root / "circular_feature_threshold_measurements.csv", index=False)
    intervals.to_csv(output_root / "circular_feature_cd_intervals.csv", index=False)
    summary.to_csv(output_root / "circular_feature_method_summary.csv", index=False)
    metadata = {
        "purpose": "SEM-referenced CD and sharpness comparison for pillar and via",
        "methods": sorted(detailed["method"].unique().tolist()),
        "magnifications": sorted(detailed["magnification"].unique().tolist()),
        "contrast_thresholds": list(CONTRAST_FRACTIONS),
        "cd_primary_readout": "Lower and upper apparent CD across the fixed 35%-65% contrast thresholds",
        "cd_measurement": "Median of 180 opposite-angle paired radial diameters",
        "edge_width": "Median 10%-90% radial transition width; lower is sharper",
        "ringing": "Inward variation divided by outward transition variation on the median radial profile",
        "center_rule": "The same Raw-defined center coordinates are used for every method",
        "sem_rule": "Both workbook pillar and via values are radii and are doubled before CD comparison",
        "missing_during_run": missing,
    }
    (output_root / "metadata.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(summary.to_string(index=False), flush=True)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output-root",
        type=Path,
        default=EXPERIMENT / "evaluation" / "circular_cd_sharpness",
    )
    parser.add_argument("--allow-missing", action="store_true")
    return parser.parse_args()


if __name__ == "__main__":
    arguments = parse_args()
    main(arguments.output_root.resolve(), arguments.allow_missing)

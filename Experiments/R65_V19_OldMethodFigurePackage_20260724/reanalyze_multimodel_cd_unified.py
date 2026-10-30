"""Recalculate the modern-model CD benchmark with the thesis CD protocol.

The protocol matches the earlier Raw/Wiener/MOSR CD checks:
- nine Raw-defined feature centers per condition;
- fixed 35%-65% local-contrast thresholds;
- horizontal-strip and azimuthally averaged radial measurements;
- SEM diameter reference;
- pooled median absolute error as the primary readout.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from PIL import Image
from scipy.ndimage import map_coordinates
PROJECT_ROOT = Path(__file__).resolve().parents[2]


EXPERIMENT = Path(
    str(PROJECT_ROOT / 'LabSystem_MOSR/Experiments/Modern_Restoration_Benchmarks_20260719')
)
LEGACY_SCRIPTS = Path(
    str(PROJECT_ROOT / 'Thesis_MOSR_Evidence/Final_Data_Figures/04_V42_NEURAL_NETWORK_RESULTS/scripts')
)
sys.path.insert(0, str(EXPERIMENT))
sys.path.insert(0, str(LEGACY_SCRIPTS))

from analyze_wiener_three_way_results import (  # noqa: E402
    _interpolate_crossing,
    _measure_half_height_width,
)


METHODS = ("Raw", "NAFNet", "EDSR", "MOSR")
MAGNIFICATIONS = ("50x", "20x")
MORPHOLOGIES = ("pillar", "via")
THRESHOLDS = tuple(np.round(np.arange(0.35, 0.651, 0.05), 2))
MANIFEST_PATH = EXPERIMENT / "evaluation_manifest.json"
STATIC_SEQUENCES = {"50x": "50x_x_0p5um", "20x": "20x_0p5um"}
PILLAR_SEM_TABLE = Path(
    str(PROJECT_ROOT / 'Thesis_MOSR_Evidence/Final_Data_Figures/01_CURRENT_THESIS_RESULTS_V42_CENTER9/cd/tables/center9_cd_per_pillar.csv')
)


def read_gray_8bit(path: Path) -> np.ndarray:
    with Image.open(path) as image:
        return np.asarray(image.convert("L"), dtype=np.float64)


def adaptive_radial_width(
    image: np.ndarray,
    center_x: float,
    center_y: float,
    radius_px: float,
    threshold_fraction: float,
) -> dict[str, float | str]:
    """Legacy radial-mean rule with an edge-safe outer sampling radius."""
    margin = max(28.0, radius_px * 1.35)
    requested_limit = radius_px + margin
    available_limit = min(
        center_x,
        center_y,
        image.shape[1] - 1.0 - center_x,
        image.shape[0] - 1.0 - center_y,
    ) - 0.25
    radial_limit = min(requested_limit, available_limit)
    if radial_limit < radius_px * 1.55:
        return {"status": "bad_window"}
    radii = np.arange(0.0, radial_limit + 0.125, 0.25, dtype=np.float64)
    angles = np.linspace(0.0, 2.0 * np.pi, 720, endpoint=False)
    sample_x = center_x + np.outer(np.cos(angles), radii)
    sample_y = center_y + np.outer(np.sin(angles), radii)
    darkness = 1.0 - image / 255.0
    samples = map_coordinates(
        darkness,
        [sample_y.ravel(), sample_x.ravel()],
        order=1,
        mode="nearest",
    ).reshape(sample_y.shape)
    profile = samples.mean(axis=0)
    center_mask = radii <= max(3.0, radius_px * 0.42)
    background_mask = radii >= radius_px * 1.45
    if center_mask.sum() < 3 or background_mask.sum() < 3:
        return {"status": "bad_window"}
    high = float(np.percentile(profile[center_mask], 80))
    low = float(np.percentile(profile[background_mask], 20))
    if high <= low + 1e-5:
        return {"status": "bad_contrast"}
    threshold = low + threshold_fraction * (high - low)
    candidates = np.where(
        (profile[:-1] >= threshold) & (profile[1:] < threshold)
    )[0]
    if len(candidates) == 0:
        return {"status": "bad_crossing"}
    edge_index = int(candidates[np.argmin(np.abs(radii[candidates] - radius_px))])
    edge_radius = _interpolate_crossing(
        radii, profile, edge_index, edge_index + 1, threshold
    )
    if edge_radius <= 0:
        return {"status": "bad_crossing"}
    return {
        "status": "ok",
        "edge_radius_px": edge_radius,
        "width_px": 2.0 * edge_radius,
        "threshold": threshold,
    }


MODES = {
    "horizontal_strip": _measure_half_height_width,
    "radial_mean": adaptive_radial_width,
}


def load_references(
    manifest: dict[str, object], magnification: str
) -> tuple[dict[str, object], dict[str, dict[str, object]]]:
    pillar_config = json.loads(
        Path(str(str(PROJECT_ROOT / manifest["pillar_config"]))).read_text(encoding="utf-8")
    )
    via_config = json.loads(
        Path(str(str(PROJECT_ROOT / manifest["via_config"]))).read_text(encoding="utf-8")
    )
    sequence_name = STATIC_SEQUENCES[magnification]
    pillar_sequence = pillar_config["sequences"][sequence_name]
    via_sequence = via_config["sequences"][sequence_name]

    pillar_sem = pd.read_csv(PILLAR_SEM_TABLE)
    pillar_sem_nm_by_id = (
        pillar_sem.set_index("sem_index")["sem_diameter_um"] * 1000.0
    ).to_dict()
    pillar_sem_cell_by_id = (
        pillar_sem.set_index("sem_index")["sem_excel_cell"].astype(str).to_dict()
    )
    pillar_centers = [
        {
            "feature_id": f"P{int(center[0])}",
            "sem_cell": pillar_sem_cell_by_id[int(center[0])],
            "x": float(center[1]),
            "y": float(center[2]),
            "sem_cd_nm": float(pillar_sem_nm_by_id[int(center[0])]),
        }
        for center in pillar_sequence["centers"]
    ]
    via_centers = [
        {
            "feature_id": str(center["sem_cell"]),
            "sem_cell": str(center["sem_cell"]),
            "x": float(center["x"]),
            "y": float(center["y"]),
            "sem_cd_nm": float(center["sem_radius_nm"]) * 2.0,
        }
        for center in via_sequence["centers"]
    ]
    references = {
        "pillar": {
            "polarity": "dark",
            "radius_px": float(pillar_sequence["radius_px"]),
            "centers": pillar_centers,
        },
        "via": {
            "polarity": "bright",
            "radius_px": float(via_sequence["radius_px"]),
            "centers": via_centers,
        },
    }
    return pillar_sequence, references


def method_image(
    manifest: dict[str, object],
    method: str,
    sequence_name: str,
    sequence: dict[str, object],
) -> Path:
    raw_dir = Path(str(sequence["raw_dir"]))
    if method == "Raw":
        directory = raw_dir
    else:
        root = Path(str(str(PROJECT_ROOT / manifest["methods"][method]["sequence_root"])))
        mapped = str(manifest["sequence_name_map"][sequence_name][method])
        directory = root / mapped
    return directory / str(sequence["first_frame"])


def measure_all() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    records: list[dict[str, object]] = []

    for magnification in MAGNIFICATIONS:
        sequence_name = STATIC_SEQUENCES[magnification]
        sequence, references = load_references(manifest, magnification)
        um_per_px = float(sequence["object_um_per_px"])
        for method in METHODS:
            image_path = method_image(manifest, method, sequence_name, sequence)
            if not image_path.is_file():
                raise FileNotFoundError(image_path)
            original = read_gray_8bit(image_path)
            for morphology in MORPHOLOGIES:
                reference = references[morphology]
                # The legacy functions expect a dark feature. Inverting a bright-via
                # image preserves the identical crossing and threshold rules.
                image = (
                    original
                    if reference["polarity"] == "dark"
                    else 255.0 - original
                )
                radius_px = float(reference["radius_px"])
                for center_position, center in enumerate(
                    reference["centers"], start=1
                ):
                    for mode, measure in MODES.items():
                        for threshold in THRESHOLDS:
                            result = measure(
                                image,
                                float(center["x"]),
                                float(center["y"]),
                                radius_px,
                                float(threshold),
                            )
                            width_px = float(result.get("width_px", np.nan))
                            diameter_nm = width_px * um_per_px * 1000.0
                            sem_cd_nm = float(center["sem_cd_nm"])
                            signed_error_nm = diameter_nm - sem_cd_nm
                            records.append(
                                {
                                    "magnification": magnification,
                                    "morphology": morphology,
                                    "method": method,
                                    "feature_position": center_position,
                                    "feature_id": center["feature_id"],
                                    "sem_cell": center["sem_cell"],
                                    "sem_cd_nm": sem_cd_nm,
                                    "measurement_mode": mode,
                                    "threshold_fraction": float(threshold),
                                    "diameter_nm": diameter_nm,
                                    "signed_error_nm": signed_error_nm,
                                    "abs_error_nm": abs(signed_error_nm),
                                    "status": str(result["status"]),
                                    "center_x_px": float(center["x"]),
                                    "center_y_px": float(center["y"]),
                                    "reference_radius_px": radius_px,
                                    "object_um_per_px": um_per_px,
                                    "image_path": str(image_path),
                                }
                            )

    per_measurement = pd.DataFrame(records)
    expected = (
        len(MAGNIFICATIONS)
        * len(MORPHOLOGIES)
        * len(METHODS)
        * 9
        * len(MODES)
        * len(THRESHOLDS)
    )
    if len(per_measurement) != expected:
        raise RuntimeError(f"Expected {expected} rows, obtained {len(per_measurement)}")
    failures = per_measurement.loc[per_measurement["status"] != "ok"]
    if not failures.empty:
        details = failures.groupby(
            ["magnification", "morphology", "method", "status"]
        ).size()
        raise RuntimeError(f"Unified CD crossings failed:\n{details}")
    numeric = per_measurement[
        ["diameter_nm", "signed_error_nm", "abs_error_nm"]
    ].to_numpy(float)
    if not np.isfinite(numeric).all():
        raise RuntimeError("Unified CD table contains non-finite values")

    feature_records: list[dict[str, object]] = []
    feature_keys = [
        "magnification",
        "morphology",
        "method",
        "feature_position",
        "feature_id",
        "sem_cell",
    ]
    for keys, group in per_measurement.groupby(feature_keys, sort=False):
        sem_cd_nm = float(group["sem_cd_nm"].iloc[0])
        diameters = group["diameter_nm"].to_numpy(float)
        signed = group["signed_error_nm"].to_numpy(float)
        absolute = np.abs(signed)
        feature_records.append(
            {
                "magnification": keys[0],
                "morphology": keys[1],
                "method": keys[2],
                "feature_position": keys[3],
                "feature_id": keys[4],
                "sem_cell": keys[5],
                "sem_cd_nm": sem_cd_nm,
                "observation_count": len(group),
                "cd_lower_nm": float(np.min(diameters)),
                "cd_upper_nm": float(np.max(diameters)),
                "median_diameter_nm": float(np.median(diameters)),
                "mean_diameter_nm": float(np.mean(diameters)),
                "median_signed_error_nm": float(np.median(signed)),
                "median_abs_error_nm": float(np.median(absolute)),
                "mean_abs_error_nm": float(np.mean(absolute)),
                "max_abs_error_nm": float(np.max(absolute)),
            }
        )
    per_feature = pd.DataFrame(feature_records)

    summary_records: list[dict[str, object]] = []
    summary_keys = ["magnification", "morphology", "method"]
    for keys, group in per_measurement.groupby(summary_keys, sort=False):
        signed = group["signed_error_nm"].to_numpy(float)
        absolute = np.abs(signed)
        features = per_feature[
            (per_feature["magnification"] == keys[0])
            & (per_feature["morphology"] == keys[1])
            & (per_feature["method"] == keys[2])
        ]
        summary_records.append(
            {
                "magnification": keys[0],
                "morphology": keys[1],
                "method": keys[2],
                "feature_count": int(group["feature_id"].nunique()),
                "measurement_mode_count": int(
                    group["measurement_mode"].nunique()
                ),
                "threshold_count": int(group["threshold_fraction"].nunique()),
                "observation_count": len(group),
                "pooled_median_abs_error_nm": float(np.median(absolute)),
                "pooled_mean_abs_error_nm": float(np.mean(absolute)),
                "mean_of_feature_median_abs_error_nm": float(
                    features["median_abs_error_nm"].mean()
                ),
                "pooled_rmse_nm": float(np.sqrt(np.mean(np.square(signed)))),
                "pooled_mean_signed_bias_nm": float(np.mean(signed)),
                "pooled_max_abs_error_nm": float(np.max(absolute)),
            }
        )
    summary = pd.DataFrame(summary_records)

    raw_lookup = summary.loc[summary["method"] == "Raw"].set_index(
        ["magnification", "morphology"]
    )
    improvements_nm: list[float] = []
    improvements_pct: list[float] = []
    for row in summary.itertuples(index=False):
        raw_error = float(
            raw_lookup.loc[
                (row.magnification, row.morphology),
                "pooled_median_abs_error_nm",
            ]
        )
        improvement_nm = raw_error - float(row.pooled_median_abs_error_nm)
        improvements_nm.append(improvement_nm)
        improvements_pct.append(100.0 * improvement_nm / raw_error)
    summary["median_abs_improvement_vs_raw_nm"] = improvements_nm
    summary["median_abs_improvement_vs_raw_pct"] = improvements_pct
    return per_measurement, per_feature, summary


def main(output_root: Path) -> None:
    per_measurement, per_feature, summary = measure_all()
    output_root.mkdir(parents=True, exist_ok=True)
    per_measurement.to_csv(
        output_root / "unified_cd_per_measurement.csv", index=False
    )
    per_feature.to_csv(output_root / "unified_cd_per_feature.csv", index=False)
    summary.to_csv(output_root / "unified_cd_summary.csv", index=False)
    metadata = {
        "purpose": "Modern-model CD comparison using the same thesis protocol as the earlier CD checks",
        "methods": list(METHODS),
        "magnifications": list(MAGNIFICATIONS),
        "morphologies": list(MORPHOLOGIES),
        "center_rule": "One Raw-defined center set is reused unchanged by every method",
        "sem_rule": "SEM values are diameters; source radii are doubled before comparison",
        "pillar_orientation_rule": "The capture-specific center order supplies the stable pillar ID; SEM diameter is looked up by that ID so 20x flip-y and 50x identity views retain the same physical reference",
        "radial_edge_rule": "The legacy radial profile is retained; only the unused outer background radius is shortened when a center is close to an image edge",
        "measurement_modes": list(MODES),
        "thresholds": list(THRESHOLDS),
        "primary_metric": "pooled_median_abs_error_nm",
        "expected_observations_per_method_condition": 126,
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
        default=EXPERIMENT / "evaluation" / "unified_cd_protocol",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    main(args.output_root.resolve())

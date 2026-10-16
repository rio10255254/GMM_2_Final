"""Measure boundary-position equivariance on the package-manifest-unseen 50x shift set."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd
from PIL import Image
from scipy.ndimage import map_coordinates


EXPERIMENT_ROOT = Path(__file__).resolve().parents[1]
INPUT_ROOT = EXPERIMENT_ROOT / "results" / "synthetic_shift_inputs" / "50x_unseen"
MANIFEST = INPUT_ROOT / "shift_manifest.csv"


def read_gray(path: Path) -> np.ndarray:
    with Image.open(path) as image:
        return np.asarray(image.convert("L"), dtype=np.float64)


def darkness_centroid(image: np.ndarray, expected_x: float, expected_y: float) -> np.ndarray:
    yy, xx = np.mgrid[: image.shape[0], : image.shape[1]]
    radius = np.hypot(xx - expected_x, yy - expected_y)
    background = float(np.median(image[(radius >= 27.0) & (radius <= 36.0)]))
    weights = np.maximum(background - image, 0.0) * (radius <= 26.0)
    total = float(weights.sum())
    if total <= 1e-9:
        raise RuntimeError("Invalid darkness centroid")
    return np.asarray(
        [(weights * xx).sum() / total, (weights * yy).sum() / total], dtype=float
    )


def radial_metrics(image: np.ndarray, expected_x: float, expected_y: float) -> dict[str, float]:
    radii = np.arange(0.0, 44.01, 0.125)
    angles = np.linspace(0.0, 2.0 * np.pi, 720, endpoint=False)
    xx = expected_x + np.outer(np.cos(angles), radii)
    yy = expected_y + np.outer(np.sin(angles), radii)
    darkness = 1.0 - image / 255.0
    samples = map_coordinates(darkness, [yy.ravel(), xx.ravel()], order=1, mode="nearest")
    profile = samples.reshape(xx.shape).mean(axis=0)
    high = float(np.percentile(profile[radii <= 8.0], 80))
    low = float(np.percentile(profile[(radii >= 30.0) & (radii <= 40.0)], 20))
    contrast = high - low
    if contrast <= 1e-6:
        raise RuntimeError("Invalid radial contrast")

    def crossing(fraction: float) -> float:
        threshold = low + fraction * contrast
        indices = np.where((profile[:-1] >= threshold) & (profile[1:] < threshold))[0]
        if not len(indices):
            return float("nan")
        index = int(indices[np.argmin(np.abs(radii[indices] - 19.4))])
        y0, y1 = float(profile[index]), float(profile[index + 1])
        if abs(y1 - y0) < 1e-12:
            return float((radii[index] + radii[index + 1]) * 0.5)
        t = np.clip((threshold - y0) / (y1 - y0), 0.0, 1.0)
        return float(radii[index] + t * (radii[index + 1] - radii[index]))

    r90 = crossing(0.9)
    r50 = crossing(0.5)
    r10 = crossing(0.1)
    if not np.isfinite([r90, r50, r10]).all():
        raise RuntimeError("Missing radial crossing")
    outer = profile[(radii >= r10 + 2.0) & (radii <= 40.0)]
    outer_diff = np.diff(outer)
    ringing = float(np.mean(np.abs(outer_diff))) if len(outer_diff) else 0.0
    return {
        "edge_radius_50_px": r50,
        "edge_width_10_90_px": r10 - r90,
        "contrast": contrast,
        "outer_ringing_energy": ringing,
    }


def evaluate_case_set(image_root: Path, method: str) -> pd.DataFrame:
    manifest = pd.read_csv(MANIFEST)
    references = manifest.loc[manifest["case"].eq("reference")].set_index("pillar_id")
    reference_metrics: dict[int, dict[str, object]] = {}
    for pillar_id, row in references.iterrows():
        image = read_gray(image_root / str(row["file"]))
        center = darkness_centroid(image, 127.5, 127.5)
        reference_metrics[int(pillar_id)] = {
            "center": center,
            **radial_metrics(image, 127.5, 127.5),
        }

    records: list[dict[str, object]] = []
    shifted = manifest.loc[manifest["case"].eq("shifted")]
    for row in shifted.itertuples(index=False):
        image = read_gray(image_root / str(row.file))
        expected_x = 127.5 + float(row.true_dx_px)
        expected_y = 127.5 + float(row.true_dy_px)
        center = darkness_centroid(image, expected_x, expected_y)
        ref = reference_metrics[int(row.pillar_id)]
        measured = center - np.asarray(ref["center"], dtype=float)
        true = np.asarray([float(row.true_dx_px), float(row.true_dy_px)], dtype=float)
        error = measured - true
        radial = radial_metrics(image, expected_x, expected_y)
        records.append(
            {
                "method": method,
                "pillar_id": int(row.pillar_id),
                "magnitude_px": float(row.magnitude_px),
                "direction_deg": int(row.direction_deg),
                "true_dx_px": true[0],
                "true_dy_px": true[1],
                "measured_dx_px": measured[0],
                "measured_dy_px": measured[1],
                "error_dx_px": error[0],
                "error_dy_px": error[1],
                "vector_error_px": float(np.linalg.norm(error)),
                "edge_radius_change_px": radial["edge_radius_50_px"] - float(ref["edge_radius_50_px"]),
                "edge_width_change_px": radial["edge_width_10_90_px"] - float(ref["edge_width_10_90_px"]),
                "ringing_change": radial["outer_ringing_energy"] - float(ref["outer_ringing_energy"]),
                "contrast_change": radial["contrast"] - float(ref["contrast"]),
            }
        )
    return pd.DataFrame(records)


def summarize(per_case: pd.DataFrame) -> pd.DataFrame:
    records: list[dict[str, object]] = []
    for (method, magnitude), group in per_case.groupby(["method", "magnitude_px"], sort=False):
        error = group["vector_error_px"].to_numpy(float)
        records.append(
            {
                "method": method,
                "magnitude_px": magnitude,
                "case_count": len(group),
                "median_vector_error_px": float(np.median(error)),
                "mean_vector_error_px": float(np.mean(error)),
                "p95_vector_error_px": float(np.percentile(error, 95)),
                "median_abs_edge_radius_change_px": float(np.median(np.abs(group["edge_radius_change_px"]))),
                "median_abs_edge_width_change_px": float(np.median(np.abs(group["edge_width_change_px"]))),
                "median_abs_ringing_change": float(np.median(np.abs(group["ringing_change"]))),
            }
        )
    return pd.DataFrame(records)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--recon-dir", type=Path, required=True)
    parser.add_argument("--method", required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    expected = len(pd.read_csv(MANIFEST))
    if sum(1 for _ in args.recon_dir.glob("*.bmp")) != expected:
        raise RuntimeError(f"Expected {expected} reconstructed images in {args.recon_dir}")
    raw = evaluate_case_set(INPUT_ROOT, "Raw")
    method = evaluate_case_set(args.recon_dir, args.method)
    per_case = pd.concat([raw, method], ignore_index=True)
    summary = summarize(per_case)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    per_case.to_csv(args.output_dir / "synthetic_shift_per_case.csv", index=False, float_format="%.12g")
    summary.to_csv(args.output_dir / "synthetic_shift_summary.csv", index=False, float_format="%.12g")
    metadata = {
        "method": args.method,
        "recon_dir": str(args.recon_dir.resolve()),
        "case_count_per_method": int(len(raw)),
        "pillar_count": int(raw["pillar_id"].nunique()),
        "magnitudes_px": sorted(raw["magnitude_px"].unique().tolist()),
        "directions_deg": sorted(raw["direction_deg"].unique().tolist()),
        "center_estimator": "local darkness centroid in predeclared expected window",
        "radial_samples_per_radius": 720,
    }
    (args.output_dir / "metadata.json").write_text(
        json.dumps(metadata, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(summary.to_string(index=False))


if __name__ == "__main__":
    main()

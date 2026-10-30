"""Measure R57 candidate CD using the verified 100MG template centers."""
from __future__ import annotations

import argparse
import csv
import json
from datetime import datetime
from pathlib import Path
from typing import Iterable

import cv2
import numpy as np


LAB_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_TEMPLATE_CSV = (
    LAB_ROOT
    / "Reconstruct_Progress"
    / "20260618_100MG_user_recon"
    / "cd_measurement_20260620_basler_ace"
    / "cd_measurement_per_feature_basler_50x.csv"
)
DEFAULT_REFERENCE_SUMMARY_CSV = (
    LAB_ROOT
    / "Reconstruct_Progress"
    / "20260618_100MG_user_recon"
    / "cd_measurement_20260620_basler_ace"
    / "cd_measurement_summary_basler_50x.csv"
)
DEFAULT_OUTPUT_DIR = (
    LAB_ROOT
    / "Reconstruct_Progress"
    / "20260618_100MG_user_recon"
    / "cd_measurement_20260620_r57"
)
DEFAULT_CANDIDATE_IMAGE = (
    LAB_ROOT
    / "Reconstruct_Progress"
    / "20260618_100MG_user_recon"
    / "reconstruct_progress_best_tradeoff_in_20260618_100MG_20260620_152604"
    / "r57_gc_pilot_e006_b004_mtb040_psf_off"
    / "Image__2026-06-18__17-10-31.bmp"
)


def _read_gray(path: Path) -> np.ndarray:
    data = np.fromfile(str(path), dtype=np.uint8)
    img = cv2.imdecode(data, cv2.IMREAD_GRAYSCALE)
    if img is None:
        raise RuntimeError(f"failed to read image: {path}")
    return img


def _read_csv(path: Path) -> list[dict]:
    if not path.exists():
        raise FileNotFoundError(path)
    with path.open("r", newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def _to_float(row: dict, key: str, default: float = float("nan")) -> float:
    value = row.get(key, default)
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _bilinear_sample(img: np.ndarray, xs: np.ndarray, ys: np.ndarray) -> np.ndarray:
    h, w = img.shape
    xs = np.clip(xs.astype(np.float32), 0, w - 1)
    ys = np.clip(ys.astype(np.float32), 0, h - 1)
    return cv2.remap(img.astype(np.float32), xs.reshape(1, -1), ys.reshape(1, -1), cv2.INTER_LINEAR).reshape(-1)


def estimate_radius_px(
    image: np.ndarray,
    *,
    x_px: float,
    y_px: float,
    expected_radius_px: float,
    radial_window: float = 0.35,
    radius_step_px: float = 0.05,
    angle_count: int = 240,
) -> float:
    img = image.astype(np.float32) / 255.0
    gx = cv2.Sobel(img, cv2.CV_32F, 1, 0, ksize=3)
    gy = cv2.Sobel(img, cv2.CV_32F, 0, 1, ksize=3)
    mag = cv2.magnitude(gx, gy)
    r0 = max(2.0, float(expected_radius_px))
    r_min = max(2.0, r0 * (1.0 - float(radial_window)))
    r_max = max(r_min + radius_step_px, r0 * (1.0 + float(radial_window)))
    radii = np.arange(r_min, r_max + radius_step_px * 0.5, radius_step_px, dtype=np.float32)
    theta = np.linspace(0.0, 2.0 * np.pi, int(angle_count), endpoint=False, dtype=np.float32)
    cos_t = np.cos(theta)
    sin_t = np.sin(theta)
    scores = []
    for radius in radii:
        xs = float(x_px) + float(radius) * cos_t
        ys = float(y_px) + float(radius) * sin_t
        scores.append(float(_bilinear_sample(mag, xs, ys).mean()))
    best_idx = int(np.argmax(np.asarray(scores, dtype=np.float32)))
    return float(radii[best_idx])


def _sem_reference_by_feature(reference_summary_rows: list[dict], reference_image: str = "原圖") -> dict[str, float]:
    refs: dict[str, float] = {}
    for row in reference_summary_rows:
        if str(row.get("image", "")).strip() != reference_image:
            continue
        feature = str(row.get("feature", "")).strip()
        if feature:
            refs[feature] = _to_float(row, "sem_radius_mean_nm")
    if not refs:
        raise RuntimeError(f"no SEM references found for image={reference_image!r}")
    return refs


def _write_csv(path: Path, rows: list[dict], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _summarize(rows: list[dict], sem_refs: dict[str, float]) -> list[dict]:
    out: list[dict] = []
    features = sorted({str(row["feature"]) for row in rows})
    for feature in features:
        clean = [row for row in rows if row["feature"] == feature and int(row["clean_for_summary"]) == 1]
        if not clean:
            continue
        radii = np.asarray([float(row["radius_nm_basler_50x"]) for row in clean], dtype=np.float64)
        sem_radius = float(sem_refs[feature])
        radius_mean = float(np.mean(radii))
        radius_median = float(np.median(radii))
        radius_std = float(np.std(radii, ddof=1)) if len(radii) > 1 else 0.0
        radius_error = radius_mean - sem_radius
        out.append(
            {
                "image": clean[0]["image"],
                "feature": feature,
                "n": len(clean),
                "radius_mean_nm": radius_mean,
                "radius_median_nm": radius_median,
                "radius_std_nm": radius_std,
                "diameter_mean_nm": radius_mean * 2.0,
                "sem_radius_mean_nm": sem_radius,
                "radius_error_vs_sem_nm": radius_error,
                "abs_radius_error_vs_sem_nm": abs(radius_error),
                "diameter_error_vs_sem_nm": radius_error * 2.0,
                "abs_diameter_error_vs_sem_nm": abs(radius_error * 2.0),
            }
        )
    return out


def measure_candidate(
    *,
    candidate_image: Path,
    candidate_label: str,
    template_csv: Path = DEFAULT_TEMPLATE_CSV,
    reference_summary_csv: Path = DEFAULT_REFERENCE_SUMMARY_CSV,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    nm_per_px: float = 69.0,
    template_image_label: str = "原圖",
) -> dict:
    image = _read_gray(Path(candidate_image))
    template_rows = [
        row for row in _read_csv(Path(template_csv))
        if str(row.get("image", "")).strip() == template_image_label
    ]
    if not template_rows:
        raise RuntimeError(f"no template rows found for image={template_image_label!r}")
    reference_rows = _read_csv(Path(reference_summary_csv))
    sem_refs = _sem_reference_by_feature(reference_rows, reference_image=template_image_label)

    per_feature: list[dict] = []
    for row in template_rows:
        feature = str(row["feature"]).strip()
        x_px = _to_float(row, "x_px")
        y_px = _to_float(row, "y_px")
        expected = _to_float(row, "radius_px")
        radius_px = estimate_radius_px(image, x_px=x_px, y_px=y_px, expected_radius_px=expected)
        radius_nm = radius_px * float(nm_per_px)
        per_feature.append(
            {
                "image": candidate_label,
                "feature": feature,
                "id": int(round(_to_float(row, "id"))),
                "x_px": x_px,
                "y_px": y_px,
                "radius_px": radius_px,
                "clean_for_summary": int(round(_to_float(row, "clean_for_summary", 0.0))),
                "radius_nm_basler_50x": radius_nm,
                "diameter_nm_basler_50x": radius_nm * 2.0,
            }
        )

    summary_rows = _summarize(per_feature, sem_refs)
    output_dir = Path(output_dir)
    per_fields = [
        "image",
        "feature",
        "id",
        "x_px",
        "y_px",
        "radius_px",
        "clean_for_summary",
        "radius_nm_basler_50x",
        "diameter_nm_basler_50x",
    ]
    summary_fields = [
        "image",
        "feature",
        "n",
        "radius_mean_nm",
        "radius_median_nm",
        "radius_std_nm",
        "diameter_mean_nm",
        "sem_radius_mean_nm",
        "radius_error_vs_sem_nm",
        "abs_radius_error_vs_sem_nm",
        "diameter_error_vs_sem_nm",
        "abs_diameter_error_vs_sem_nm",
    ]
    _write_csv(output_dir / "cd_measurement_per_feature.csv", per_feature, per_fields)
    _write_csv(output_dir / "cd_measurement_summary.csv", summary_rows, summary_fields)
    combined_rows = reference_rows + summary_rows
    _write_csv(output_dir / "cd_measurement_summary_with_reference.csv", combined_rows, summary_fields)
    meta = {
        "candidate_image": str(Path(candidate_image)),
        "candidate_label": candidate_label,
        "template_csv": str(Path(template_csv)),
        "reference_summary_csv": str(Path(reference_summary_csv)),
        "nm_per_px": float(nm_per_px),
        "template_image_label": template_image_label,
        "generated_at": datetime.now().replace(microsecond=0).isoformat(),
    }
    (output_dir / "measurement_meta.json").write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")
    return {
        "candidate_label": candidate_label,
        "output_dir": str(output_dir),
        "per_feature_rows": len(per_feature),
        "summary_rows": summary_rows,
    }


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Measure an R57 candidate CD from verified 100MG template centers")
    parser.add_argument("--candidate-image", type=Path, default=DEFAULT_CANDIDATE_IMAGE)
    parser.add_argument("--candidate-label", default="R57_pilot")
    parser.add_argument("--template-csv", type=Path, default=DEFAULT_TEMPLATE_CSV)
    parser.add_argument("--reference-summary-csv", type=Path, default=DEFAULT_REFERENCE_SUMMARY_CSV)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--nm-per-px", type=float, default=69.0)
    parser.add_argument("--template-image-label", default="原圖")
    return parser


def main(argv: Iterable[str] | None = None) -> int:
    args = build_arg_parser().parse_args(list(argv) if argv is not None else None)
    result = measure_candidate(
        candidate_image=args.candidate_image,
        candidate_label=args.candidate_label,
        template_csv=args.template_csv,
        reference_summary_csv=args.reference_summary_csv,
        output_dir=args.output_dir,
        nm_per_px=args.nm_per_px,
        template_image_label=args.template_image_label,
    )
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


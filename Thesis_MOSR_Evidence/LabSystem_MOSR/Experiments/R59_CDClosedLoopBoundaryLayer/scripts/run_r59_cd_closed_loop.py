"""R59 CD-closed-loop boundary calibration layer for the 100MG MOSR sample."""
from __future__ import annotations

import argparse
import csv
import json
from datetime import datetime
from pathlib import Path
from typing import Iterable

import cv2
import numpy as np


EXPERIMENT_DIR = Path(__file__).resolve().parents[1]
LAB_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_RECON_ROOT = LAB_ROOT / "Reconstruct_Progress" / "20260618_100MG_user_recon"
DEFAULT_IMAGE_NAME = "Image__2026-06-18__17-10-31.bmp"
DEFAULT_TEMPLATE_CSV = DEFAULT_RECON_ROOT / "cd_measurement_20260620_basler_ace" / "cd_measurement_per_feature_basler_50x.csv"
DEFAULT_REFERENCE_SUMMARY_CSV = DEFAULT_RECON_ROOT / "cd_measurement_20260620_basler_ace" / "cd_measurement_summary_basler_50x.csv"
DEFAULT_OUTPUT_ROOT = EXPERIMENT_DIR / "reports" / "r59_cd_closed_loop"
NM_PER_PX = 69.0
REFERENCE_ORIGINAL_MEAN_ABS_RADIUS_ERROR_NM = 38.59


def _read_gray(path: Path) -> np.ndarray:
    data = np.fromfile(str(path), dtype=np.uint8)
    img = cv2.imdecode(data, cv2.IMREAD_GRAYSCALE)
    if img is None:
        raise RuntimeError(f"failed to read image: {path}")
    return img


def _write_gray(path: Path, img: np.ndarray) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    ok, encoded = cv2.imencode(path.suffix or ".bmp", np.clip(img, 0, 255).astype(np.uint8))
    if not ok:
        raise RuntimeError(f"failed to encode image: {path}")
    path.write_bytes(encoded.tobytes())


def _read_csv(path: Path) -> list[dict]:
    with Path(path).open("r", newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def _write_csv(path: Path, rows: list[dict], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with Path(path).open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _to_float(row: dict, key: str, default: float = float("nan")) -> float:
    try:
        return float(row.get(key, default))
    except (TypeError, ValueError):
        return float(default)


def _to_int(row: dict, key: str, default: int = 0) -> int:
    try:
        return int(round(float(row.get(key, default))))
    except (TypeError, ValueError):
        return int(default)


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


def _smoothstep(x: np.ndarray) -> np.ndarray:
    x = np.clip(x, 0.0, 1.0)
    return x * x * (3.0 - 2.0 * x)


def apply_radial_boundary_shift(
    image: np.ndarray,
    *,
    x_px: float,
    y_px: float,
    current_radius_px: float,
    shift_px: float,
    edge_band_px: float = 4.0,
    feather_px: float = 2.5,
) -> np.ndarray:
    shift = float(shift_px)
    if abs(shift) < 1e-6:
        return image.copy()

    img = image.astype(np.float32, copy=False)
    h, w = img.shape
    current_radius = max(2.0, float(current_radius_px))
    target_radius = max(2.0, current_radius + shift)
    r_min = max(0.5, min(current_radius, target_radius) - float(edge_band_px))
    r_max = max(current_radius, target_radius) + float(edge_band_px)
    margin = int(np.ceil(r_max + float(feather_px) + abs(shift) + 3.0))
    cx = float(x_px)
    cy = float(y_px)
    x0 = max(0, int(np.floor(cx - margin)))
    x1 = min(w, int(np.ceil(cx + margin + 1)))
    y0 = max(0, int(np.floor(cy - margin)))
    y1 = min(h, int(np.ceil(cy + margin + 1)))
    if x1 <= x0 + 1 or y1 <= y0 + 1:
        return image.copy()

    roi = img[y0:y1, x0:x1]
    yy, xx = np.mgrid[y0:y1, x0:x1].astype(np.float32)
    dx = xx - cx
    dy = yy - cy
    rr = np.sqrt(dx * dx + dy * dy)
    rr_safe = np.maximum(rr, 1e-3)

    inner = _smoothstep((rr - r_min) / max(float(feather_px), 1e-3))
    outer = 1.0 - _smoothstep((rr - (r_max - float(feather_px))) / max(float(feather_px), 1e-3))
    weight = np.clip(inner * outer, 0.0, 1.0).astype(np.float32)
    if float(weight.max()) <= 0.0:
        return image.copy()

    src_r = np.clip(rr - shift, 0.0, max(h, w))
    scale = src_r / rr_safe
    map_x = (cx + dx * scale - x0).astype(np.float32)
    map_y = (cy + dy * scale - y0).astype(np.float32)
    shifted = cv2.remap(roi, map_x, map_y, cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT101)
    out = img.copy()
    out_roi = out[y0:y1, x0:x1]
    out[y0:y1, x0:x1] = shifted * weight + out_roi * (1.0 - weight)
    return np.clip(out, 0, 255).astype(np.uint8)


def _sem_refs_from_summary(rows: list[dict], *, reference_image: str = "原圖") -> dict[str, float]:
    refs: dict[str, float] = {}
    for row in rows:
        if str(row.get("image", "")).strip() != reference_image:
            continue
        feature = str(row.get("feature", "")).strip()
        if feature:
            refs[feature] = _to_float(row, "sem_radius_mean_nm")
    if not refs:
        raise RuntimeError(f"no SEM references found for image={reference_image!r}")
    return refs


def measure_rows_from_template(
    image: np.ndarray,
    *,
    template_rows: list[dict],
    sem_refs: dict[str, float],
    candidate_label: str,
    nm_per_px: float = NM_PER_PX,
) -> list[dict]:
    rows: list[dict] = []
    for row in template_rows:
        feature = str(row.get("feature", "")).strip()
        if feature not in sem_refs:
            continue
        x_px = _to_float(row, "x_px")
        y_px = _to_float(row, "y_px")
        expected_radius_px = _to_float(row, "radius_px")
        radius_px = estimate_radius_px(image, x_px=x_px, y_px=y_px, expected_radius_px=expected_radius_px)
        radius_nm = radius_px * float(nm_per_px)
        sem_nm = float(sem_refs[feature])
        rows.append(
            {
                "image": candidate_label,
                "feature": feature,
                "id": _to_int(row, "id"),
                "x_px": x_px,
                "y_px": y_px,
                "expected_radius_px": expected_radius_px,
                "radius_px": radius_px,
                "clean_for_summary": _to_int(row, "clean_for_summary"),
                "radius_nm_basler_50x": radius_nm,
                "diameter_nm_basler_50x": radius_nm * 2.0,
                "sem_radius_mean_nm": sem_nm,
                "radius_error_vs_sem_nm": radius_nm - sem_nm,
                "abs_radius_error_vs_sem_nm": abs(radius_nm - sem_nm),
            }
        )
    return rows


def summarize_measurement_rows(rows: list[dict], *, candidate_label: str) -> list[dict]:
    out: list[dict] = []
    for feature in sorted({str(row["feature"]) for row in rows}):
        clean = [row for row in rows if row["feature"] == feature and int(row["clean_for_summary"]) == 1]
        if not clean:
            clean = [row for row in rows if row["feature"] == feature]
        radii = np.asarray([float(row["radius_nm_basler_50x"]) for row in clean], dtype=np.float64)
        sem_radius = float(clean[0]["sem_radius_mean_nm"])
        radius_mean = float(np.mean(radii))
        radius_median = float(np.median(radii))
        radius_std = float(np.std(radii, ddof=1)) if len(radii) > 1 else 0.0
        radius_error = radius_mean - sem_radius
        out.append(
            {
                "image": candidate_label,
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


def fit_class_radius_shifts(
    rows: list[dict],
    *,
    nm_per_px: float = NM_PER_PX,
    max_abs_shift_px: float = 3.0,
) -> dict[str, dict]:
    shifts: dict[str, dict] = {}
    for feature in sorted({str(row.get("feature", "")).strip() for row in rows}):
        feature_rows = [
            row for row in rows
            if str(row.get("feature", "")).strip() == feature and int(float(row.get("clean_for_summary", 1))) == 1
        ]
        if not feature_rows:
            feature_rows = [row for row in rows if str(row.get("feature", "")).strip() == feature]
        deltas_px = []
        errors_nm = []
        for row in feature_rows:
            sem_nm = _to_float(row, "sem_radius_mean_nm")
            measured_nm = _to_float(row, "radius_nm_basler_50x")
            if not np.isfinite(sem_nm) or not np.isfinite(measured_nm):
                continue
            errors_nm.append(measured_nm - sem_nm)
            deltas_px.append((sem_nm - measured_nm) / float(nm_per_px))
        if not deltas_px:
            continue
        raw_shift = float(np.median(np.asarray(deltas_px, dtype=np.float64)))
        shift = float(np.clip(raw_shift, -float(max_abs_shift_px), float(max_abs_shift_px)))
        shifts[feature] = {
            "shift_px": shift,
            "raw_shift_px": raw_shift,
            "median_radius_error_nm": float(np.median(np.asarray(errors_nm, dtype=np.float64))),
            "n": len(deltas_px),
            "clipped": bool(abs(shift - raw_shift) > 1e-9),
        }
    return shifts


def _mean_abs_radius_error(summary_rows: list[dict]) -> float:
    vals = [float(row["abs_radius_error_vs_sem_nm"]) for row in summary_rows]
    return float(np.mean(vals)) if vals else float("nan")


def _summary_fieldnames() -> list[str]:
    return [
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


def _per_feature_fieldnames() -> list[str]:
    return [
        "image",
        "feature",
        "id",
        "x_px",
        "y_px",
        "expected_radius_px",
        "radius_px",
        "clean_for_summary",
        "radius_nm_basler_50x",
        "diameter_nm_basler_50x",
        "sem_radius_mean_nm",
        "radius_error_vs_sem_nm",
        "abs_radius_error_vs_sem_nm",
    ]


def calibrate_image_from_rows(
    *,
    candidate_image: Path,
    candidate_label: str,
    template_rows: list[dict],
    sem_refs: dict[str, float],
    output_dir: Path,
    nm_per_px: float = NM_PER_PX,
    max_abs_shift_px: float = 3.0,
) -> dict:
    output_dir = Path(output_dir)
    image = _read_gray(Path(candidate_image))
    pre_rows = measure_rows_from_template(
        image,
        template_rows=template_rows,
        sem_refs=sem_refs,
        candidate_label=f"{candidate_label}_pre",
        nm_per_px=nm_per_px,
    )
    pre_summary = summarize_measurement_rows(pre_rows, candidate_label=f"{candidate_label}_pre")
    class_shifts = fit_class_radius_shifts(pre_rows, nm_per_px=nm_per_px, max_abs_shift_px=max_abs_shift_px)

    current_by_id = {(_to_int(row, "id"), str(row["feature"])): float(row["radius_px"]) for row in pre_rows}
    corrected = image.copy()
    for row in template_rows:
        feature = str(row.get("feature", "")).strip()
        if feature not in class_shifts:
            continue
        key = (_to_int(row, "id"), feature)
        current_radius_px = current_by_id.get(key, _to_float(row, "radius_px"))
        corrected = apply_radial_boundary_shift(
            corrected,
            x_px=_to_float(row, "x_px"),
            y_px=_to_float(row, "y_px"),
            current_radius_px=current_radius_px,
            shift_px=float(class_shifts[feature]["shift_px"]),
        )

    corrected_image = output_dir / f"{candidate_label}_r59_cd_closed_loop.bmp"
    _write_gray(corrected_image, corrected)
    post_rows = measure_rows_from_template(
        corrected,
        template_rows=template_rows,
        sem_refs=sem_refs,
        candidate_label=f"{candidate_label}_r59",
        nm_per_px=nm_per_px,
    )
    post_summary = summarize_measurement_rows(post_rows, candidate_label=f"{candidate_label}_r59")

    pre_per_csv = output_dir / "pre_cd_measurement_per_feature.csv"
    post_per_csv = output_dir / "post_cd_measurement_per_feature.csv"
    pre_summary_csv = output_dir / "pre_cd_measurement_summary.csv"
    post_summary_csv = output_dir / "post_cd_measurement_summary.csv"
    _write_csv(pre_per_csv, pre_rows, _per_feature_fieldnames())
    _write_csv(post_per_csv, post_rows, _per_feature_fieldnames())
    _write_csv(pre_summary_csv, pre_summary, _summary_fieldnames())
    _write_csv(post_summary_csv, post_summary, _summary_fieldnames())

    calibration = {
        "candidate_image": str(Path(candidate_image)),
        "candidate_label": candidate_label,
        "corrected_image": str(corrected_image),
        "nm_per_px": float(nm_per_px),
        "class_shifts_px": class_shifts,
        "pre_mean_abs_radius_error_nm": _mean_abs_radius_error(pre_summary),
        "post_mean_abs_radius_error_nm": _mean_abs_radius_error(post_summary),
        "reference_original_mean_abs_radius_error_nm": REFERENCE_ORIGINAL_MEAN_ABS_RADIUS_ERROR_NM,
        "generated_at": datetime.now().replace(microsecond=0).isoformat(),
    }
    calibration_json = output_dir / "r59_cd_closed_loop_model.json"
    calibration_json.parent.mkdir(parents=True, exist_ok=True)
    calibration_json.write_text(json.dumps(calibration, indent=2, ensure_ascii=False), encoding="utf-8")

    report = output_dir / "R59_CD_CLOSED_LOOP_STATUS.md"
    lines = [
        "# R59 CD Closed Loop Status",
        "",
        f"- Candidate: {candidate_label}",
        f"- Pre mean abs radius error: {calibration['pre_mean_abs_radius_error_nm']:.2f} nm",
        f"- Post mean abs radius error: {calibration['post_mean_abs_radius_error_nm']:.2f} nm",
        f"- Original reference mean abs radius error: {REFERENCE_ORIGINAL_MEAN_ABS_RADIUS_ERROR_NM:.2f} nm",
        "",
        "| Feature | Shift (px) | Median pre error (nm) |",
        "| --- | ---: | ---: |",
    ]
    for feature, info in class_shifts.items():
        lines.append(f"| {feature} | {float(info['shift_px']):.3f} | {float(info['median_radius_error_nm']):.2f} |")
    lines.append("")
    report.write_text("\n".join(lines), encoding="utf-8")

    return {
        "corrected_image": str(corrected_image),
        "calibration_json": str(calibration_json),
        "report": str(report),
        "pre_summary_csv": str(pre_summary_csv),
        "post_summary_csv": str(post_summary_csv),
        "pre_mean_abs_radius_error_nm": calibration["pre_mean_abs_radius_error_nm"],
        "post_mean_abs_radius_error_nm": calibration["post_mean_abs_radius_error_nm"],
        "class_shifts_px": class_shifts,
    }


def find_default_candidate_image() -> Path:
    patterns = [
        "*/r58_frac050_pilot_e008_mtb080*_weakpsf_off/" + DEFAULT_IMAGE_NAME,
        "*/r58_frac025_pilot_e008_mtb080*_weakpsf_off/" + DEFAULT_IMAGE_NAME,
        "*/r58_frac050*_weakpsf_off/" + DEFAULT_IMAGE_NAME,
    ]
    candidates: list[Path] = []
    for pattern in patterns:
        candidates.extend(DEFAULT_RECON_ROOT.glob(pattern))
    candidates = [p for p in candidates if p.exists()]
    if not candidates:
        raise FileNotFoundError(f"no default R58 candidate image found under {DEFAULT_RECON_ROOT}")
    return max(candidates, key=lambda p: p.stat().st_mtime)


def _load_template_rows(path: Path, *, template_image_label: str = "原圖") -> list[dict]:
    rows = [row for row in _read_csv(path) if str(row.get("image", "")).strip() == template_image_label]
    if not rows:
        raise RuntimeError(f"no template rows found for image={template_image_label!r}")
    return rows


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run R59 CD-closed-loop boundary calibration")
    parser.add_argument("--candidate-image", type=Path, default=None)
    parser.add_argument("--candidate-label", default="r59_candidate")
    parser.add_argument("--template-csv", type=Path, default=DEFAULT_TEMPLATE_CSV)
    parser.add_argument("--reference-summary-csv", type=Path, default=DEFAULT_REFERENCE_SUMMARY_CSV)
    parser.add_argument("--output-dir", type=Path, default=None)
    parser.add_argument("--nm-per-px", type=float, default=NM_PER_PX)
    parser.add_argument("--template-image-label", default="原圖")
    parser.add_argument("--max-abs-shift-px", type=float, default=3.0)
    return parser


def main(argv: Iterable[str] | None = None) -> int:
    args = build_arg_parser().parse_args(list(argv) if argv is not None else None)
    candidate_image = Path(args.candidate_image) if args.candidate_image is not None else find_default_candidate_image()
    candidate_label = str(args.candidate_label)
    if candidate_label == "r59_candidate":
        candidate_label = candidate_image.parent.name
    output_dir = Path(args.output_dir) if args.output_dir is not None else DEFAULT_OUTPUT_ROOT / candidate_label
    template_rows = _load_template_rows(Path(args.template_csv), template_image_label=str(args.template_image_label))
    sem_refs = _sem_refs_from_summary(_read_csv(Path(args.reference_summary_csv)), reference_image=str(args.template_image_label))
    result = calibrate_image_from_rows(
        candidate_image=candidate_image,
        candidate_label=candidate_label,
        template_rows=template_rows,
        sem_refs=sem_refs,
        output_dir=output_dir,
        nm_per_px=float(args.nm_per_px),
        max_abs_shift_px=float(args.max_abs_shift_px),
    )
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

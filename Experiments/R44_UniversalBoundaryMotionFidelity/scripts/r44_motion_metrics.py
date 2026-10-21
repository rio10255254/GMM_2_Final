"""R44 universal boundary-motion metrics."""
from __future__ import annotations

import argparse
import csv
import json
import math
from collections import defaultdict
from pathlib import Path

import cv2
import numpy as np


REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_DATA_ROOT = REPO_ROOT / "Training_Data" / "r44_universal_boundary_motion"
DEFAULT_RECON_ROOT = REPO_ROOT / "Experiments" / "R44_UniversalBoundaryMotionFidelity" / "results" / "motion_recon"
IMAGE_EXTENSIONS = {".bmp", ".png", ".tif", ".tiff"}


def _read_gray(path: Path) -> np.ndarray:
    img = cv2.imread(str(path), cv2.IMREAD_UNCHANGED)
    if img is None:
        raise RuntimeError(f"failed to read image: {path}")
    if img.ndim == 3:
        img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    return img


def _to_float32(img: np.ndarray) -> np.ndarray:
    arr = np.asarray(img)
    if arr.dtype == np.uint16:
        return arr.astype(np.float32) / 65535.0
    if arr.dtype == np.uint8:
        return arr.astype(np.float32) / 255.0
    arr = arr.astype(np.float32)
    maxv = float(np.nanmax(arr)) if arr.size else 1.0
    return arr / maxv if maxv > 1.5 else arr


def _as_mask(mask_or_img: np.ndarray) -> np.ndarray:
    arr = np.asarray(mask_or_img)
    if arr.dtype == bool:
        return arr
    return arr > 0


def _distance_to_mask(mask: np.ndarray) -> np.ndarray:
    inv = np.where(_as_mask(mask), 0, 255).astype(np.uint8)
    return cv2.distanceTransform(inv, cv2.DIST_L2, 5).astype(np.float32)


def _warp_mask(mask: np.ndarray, *, dx: float, dy: float) -> np.ndarray:
    h, w = mask.shape[:2]
    mat = np.asarray([[1.0, 0.0, float(dx)], [0.0, 1.0, float(dy)]], dtype=np.float32)
    return cv2.warpAffine(
        mask.astype(np.uint8),
        mat,
        (w, h),
        flags=cv2.INTER_NEAREST,
        borderMode=cv2.BORDER_CONSTANT,
        borderValue=0,
    )


def _gradient_magnitude(img: np.ndarray) -> np.ndarray:
    f = _to_float32(img)
    gx = cv2.Sobel(f, cv2.CV_32F, 1, 0, ksize=3)
    gy = cv2.Sobel(f, cv2.CV_32F, 0, 1, ksize=3)
    return np.sqrt(gx * gx + gy * gy)


def matched_gradient_boundary(img: np.ndarray, *, target_count: int | None = None) -> np.ndarray:
    mag = _gradient_magnitude(img)
    if float(mag.max()) <= 1e-12:
        return np.zeros_like(img, dtype=np.uint8)
    if target_count is None or int(target_count) <= 0:
        target_count = max(1, int(round(mag.size * 0.03)))
    target_count = max(1, min(int(target_count), int(mag.size)))
    flat = mag.reshape(-1)
    kth = flat.size - target_count
    threshold = float(np.partition(flat, kth)[kth])
    return (mag >= threshold).astype(np.uint8) * 255


def estimate_translation_px(frame_a: np.ndarray, frame_b: np.ndarray) -> tuple[float, float, float]:
    a = _to_float32(frame_a)
    b = _to_float32(frame_b)
    if float(np.std(a)) <= 1e-8 or float(np.std(b)) <= 1e-8:
        return 0.0, 0.0, 0.0
    window = cv2.createHanningWindow((a.shape[1], a.shape[0]), cv2.CV_32F)
    (dx, dy), response = cv2.phaseCorrelate(a, b, window)
    return float(dx), float(dy), float(response)


def motion_pair_metrics(
    frame_a: np.ndarray,
    frame_b: np.ndarray,
    *,
    expected_dx: float,
    expected_dy: float,
) -> dict:
    dx, dy, response = estimate_translation_px(frame_a, frame_b)
    err = math.sqrt((dx - float(expected_dx)) ** 2 + (dy - float(expected_dy)) ** 2)
    return {
        "estimated_dx_px": float(dx),
        "estimated_dy_px": float(dy),
        "expected_dx_px": float(expected_dx),
        "expected_dy_px": float(expected_dy),
        "motion_vector_error_px": float(err),
        "phasecorr_response": float(response),
    }


def boundary_motion_error(
    boundary_a: np.ndarray,
    boundary_b: np.ndarray,
    *,
    expected_dx: float,
    expected_dy: float,
) -> dict:
    expected = _warp_mask((_as_mask(boundary_a).astype(np.uint8) * 255), dx=expected_dx, dy=expected_dy)
    pred = _as_mask(boundary_b)
    gt = _as_mask(expected)
    if int(pred.sum()) == 0 and int(gt.sum()) == 0:
        dist = 0.0
    elif int(pred.sum()) == 0 or int(gt.sum()) == 0:
        dist = float("inf")
    else:
        dist_to_gt = _distance_to_mask(gt)
        dist_to_pred = _distance_to_mask(pred)
        dist = float(np.mean(np.concatenate([dist_to_gt[pred], dist_to_pred[gt]])))
    return {
        "boundary_motion_distance_px": dist,
        "boundary_pred_px": int(pred.sum()),
        "boundary_expected_px": int(gt.sum()),
    }


def _peak_positions(mask: np.ndarray, axis: int) -> np.ndarray:
    m = _as_mask(mask)
    profile = m.sum(axis=0 if axis == 1 else 1).astype(np.float64)
    if profile.max() <= 0:
        return np.asarray([], dtype=np.float64)
    active = profile >= max(1.0, profile.max() * 0.45)
    runs = []
    start = None
    for i, val in enumerate(active.tolist() + [False]):
        if val and start is None:
            start = i
        elif (not val) and start is not None:
            runs.append((start, i - 1))
            start = None
    return np.asarray([(a + b) / 2.0 for a, b in runs], dtype=np.float64)


def _median_pitch(peaks: np.ndarray) -> float:
    if peaks.size < 2:
        return float("nan")
    return float(np.median(np.diff(peaks)))


def grid_phase_motion_error(grid_a: np.ndarray, grid_b: np.ndarray, *, expected_dx: float, axis: int = 1) -> dict:
    peaks_a = _peak_positions(grid_a, axis=axis)
    peaks_b = _peak_positions(grid_b, axis=axis)
    if peaks_a.size == 0 or peaks_b.size == 0:
        return {
            "grid_phase_motion_error_px": float("inf"),
            "grid_estimated_shift_px": float("nan"),
            "grid_pitch_px": float("nan"),
            "grid_peak_count_a": int(peaks_a.size),
            "grid_peak_count_b": int(peaks_b.size),
        }
    pitch = _median_pitch(peaks_a)
    if not np.isfinite(pitch) or pitch <= 0:
        pitch = max(1.0, float(abs(peaks_a[-1] - peaks_a[0])))
    observed = float((peaks_b[0] - peaks_a[0]) % pitch)
    expected = float(expected_dx % pitch)
    raw = abs(observed - expected)
    err = min(raw, float(pitch) - raw)
    return {
        "grid_phase_motion_error_px": float(err),
        "grid_estimated_shift_px": float(observed),
        "grid_expected_shift_px": float(expected),
        "grid_pitch_px": float(pitch),
        "grid_peak_count_a": int(peaks_a.size),
        "grid_peak_count_b": int(peaks_b.size),
    }


def _load_manifest(profile_dir: Path) -> dict:
    manifest_path = profile_dir / "manifest.json"
    if not manifest_path.exists():
        raise FileNotFoundError(f"missing data package manifest: {manifest_path}")
    return json.loads(manifest_path.read_text(encoding="utf-8"))


def _latest_stage_output(recon_root: Path, profile: str, stage: str) -> Path:
    candidates: list[Path] = []
    for run_dir in recon_root.glob(f"reconstruct_progress_*_in_{stage}_*"):
        if not run_dir.is_dir():
            continue
        for child in run_dir.iterdir():
            if child.is_dir() and child.name.startswith(f"{profile}_{stage}_"):
                candidates.append(child)
    if not candidates:
        raise FileNotFoundError(f"no reconstruction output found for {profile}/{stage}")
    return max(candidates, key=lambda p: p.stat().st_mtime)


def _avg(rows: list[dict], key: str) -> float:
    vals = [float(r[key]) for r in rows if key in r and np.isfinite(float(r[key]))]
    return float(sum(vals) / len(vals)) if vals else float("nan")


def summarize(profile: str, data_root: Path, recon_root: Path) -> dict:
    profile_dir = data_root / profile
    manifest = _load_manifest(profile_dir)
    rows = []
    by_stage: dict[str, list[dict]] = defaultdict(list)
    frames = sorted(manifest["frames"], key=lambda r: (r["stage"], r["sequence_id"], r["frame_index"]))
    grouped: dict[tuple[str, int], list[dict]] = defaultdict(list)
    for frame in frames:
        grouped[(frame["stage"], int(frame["sequence_id"]))].append(frame)

    for (stage, _seq), seq_frames in grouped.items():
        out_dir = _latest_stage_output(recon_root, profile, stage)
        seq_frames = sorted(seq_frames, key=lambda r: int(r["frame_index"]))
        for a, b in zip(seq_frames, seq_frames[1:]):
            pred_a = _read_gray(out_dir / Path(a["package_lbl"]).name)
            pred_b = _read_gray(out_dir / Path(b["package_lbl"]).name)
            boundary_a = _read_gray(profile_dir / a["package_boundary"])
            boundary_b_gt = _read_gray(profile_dir / b["package_boundary"])
            pred_b_boundary = matched_gradient_boundary(
                pred_b,
                target_count=int(_as_mask(boundary_b_gt).sum()),
            )
            expected = b["delta_from_prev_px"]
            row = {
                "stage": stage,
                "feature_family": b["feature_family"],
                "sequence_id": int(b["sequence_id"]),
                "frame_a": int(a["frame_index"]),
                "frame_b": int(b["frame_index"]),
            }
            row.update(motion_pair_metrics(pred_a, pred_b, expected_dx=float(expected["dx"]), expected_dy=float(expected["dy"])))
            row.update(boundary_motion_error(boundary_a, pred_b_boundary, expected_dx=float(expected["dx"]), expected_dy=float(expected["dy"])))
            if b["feature_family"] in {"grids", "mixed_fields"}:
                center_a = _read_gray(profile_dir / a["package_centerline"])
                center_b = _read_gray(profile_dir / b["package_centerline"])
                row.update(grid_phase_motion_error(center_a, center_b, expected_dx=float(expected["dx"])))
            rows.append(row)
            by_stage[stage].append(row)

    stage_rows = []
    for stage, stage_data in sorted(by_stage.items()):
        stage_rows.append(
            {
                "stage": stage,
                "feature_family": stage_data[0]["feature_family"],
                "pair_count": len(stage_data),
                "avg_motion_vector_error_px": _avg(stage_data, "motion_vector_error_px"),
                "avg_boundary_motion_distance_px": _avg(stage_data, "boundary_motion_distance_px"),
                "avg_grid_phase_motion_error_px": _avg(stage_data, "grid_phase_motion_error_px"),
            }
        )
    return {
        "profile": profile,
        "data_root": str(data_root.resolve()),
        "recon_root": str(recon_root.resolve()),
        "total_pairs": len(rows),
        "overall_motion_vector_error_px": _avg(rows, "motion_vector_error_px"),
        "overall_boundary_motion_distance_px": _avg(rows, "boundary_motion_distance_px"),
        "overall_grid_phase_motion_error_px": _avg(rows, "grid_phase_motion_error_px"),
        "stages": stage_rows,
        "rows": rows,
    }


def write_csv(rows: list[dict], path: Path) -> None:
    if not rows:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = sorted({key for row in rows for key in row})
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Summarize R44 motion reconstruction metrics.")
    parser.add_argument("--profile", default="motion_val_unseen")
    parser.add_argument("--data-root", type=Path, default=DEFAULT_DATA_ROOT)
    parser.add_argument("--recon-root", type=Path, default=DEFAULT_RECON_ROOT)
    parser.add_argument("--output-json", type=Path, default=DEFAULT_RECON_ROOT / "motion_val_unseen_summary.json")
    parser.add_argument("--output-csv", type=Path, default=DEFAULT_RECON_ROOT / "motion_val_unseen_rows.csv")
    args = parser.parse_args(argv)

    summary = summarize(args.profile, args.data_root, args.recon_root)
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    write_csv(summary["rows"], args.output_csv)
    print(json.dumps({k: v for k, v in summary.items() if k != "rows"}, indent=2, ensure_ascii=False))
    print(f"[R44] summary written to {args.output_json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

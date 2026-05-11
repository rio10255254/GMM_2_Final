"""R42 boundary-fidelity metrics."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import cv2
import numpy as np


REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_DATA_ROOT = REPO_ROOT / "Training_Data" / "r42_microscopy_boundary_fidelity"
DEFAULT_RECON_ROOT = REPO_ROOT / "Experiments" / "R42_MicroscopyBoundaryFidelity" / "results" / "boundary_recon"
IMAGE_EXTENSIONS = {".bmp", ".png", ".tif", ".tiff"}


def _read_gray(path: Path) -> np.ndarray:
    img = cv2.imread(str(path), cv2.IMREAD_UNCHANGED)
    if img is None:
        raise RuntimeError(f"failed to read image: {path}")
    if img.ndim == 3:
        img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    return img


def _to_float01(img: np.ndarray) -> np.ndarray:
    if img.dtype == np.uint16:
        return img.astype(np.float64) / 65535.0
    return img.astype(np.float64) / 255.0


def _image_paths(root: Path) -> list[Path]:
    return sorted(p for p in root.iterdir() if p.is_file() and p.suffix.lower() in IMAGE_EXTENSIONS)


def _as_mask(mask_or_img: np.ndarray) -> np.ndarray:
    arr = np.asarray(mask_or_img)
    if arr.dtype == bool:
        return arr
    return arr > 0


def _distance_to_mask(mask: np.ndarray) -> np.ndarray:
    mask = _as_mask(mask)
    inv = np.where(mask, 0, 255).astype(np.uint8)
    return cv2.distanceTransform(inv, cv2.DIST_L2, 5).astype(np.float32)


def _tol_key(tolerance: float) -> str:
    text = f"{float(tolerance):.1f}".replace(".", "p")
    return f"fscore_t{text}"


def binary_boundary_metrics(pred_boundary: np.ndarray, gt_boundary: np.ndarray, *, tolerances=(0.5, 1.0, 2.0)) -> dict:
    pred = _as_mask(pred_boundary)
    gt = _as_mask(gt_boundary)
    pred_count = int(pred.sum())
    gt_count = int(gt.sum())
    out = {"pred_boundary_px": pred_count, "gt_boundary_px": gt_count}
    if pred_count == 0 and gt_count == 0:
        out.update({"mean_symmetric_boundary_distance_px": 0.0, "p95_symmetric_boundary_distance_px": 0.0})
        for tol in tolerances:
            out[_tol_key(tol)] = 1.0
        return out
    if pred_count == 0 or gt_count == 0:
        out.update({"mean_symmetric_boundary_distance_px": float("inf"), "p95_symmetric_boundary_distance_px": float("inf")})
        for tol in tolerances:
            out[_tol_key(tol)] = 0.0
        return out

    dist_to_gt = _distance_to_mask(gt)
    dist_to_pred = _distance_to_mask(pred)
    pred_dist = dist_to_gt[pred]
    gt_dist = dist_to_pred[gt]
    sym = np.concatenate([pred_dist, gt_dist])
    out["mean_symmetric_boundary_distance_px"] = float(np.mean(sym))
    out["p95_symmetric_boundary_distance_px"] = float(np.percentile(sym, 95))
    for tol in tolerances:
        precision = float(np.mean(pred_dist <= float(tol)))
        recall = float(np.mean(gt_dist <= float(tol)))
        out[_tol_key(tol)] = 0.0 if precision + recall <= 1e-12 else float(2.0 * precision * recall / (precision + recall))
    return out


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


def grid_pitch_phase_error(pred_centerline: np.ndarray, gt_centerline: np.ndarray, *, axis: int = 1) -> dict:
    pred_peaks = _peak_positions(pred_centerline, axis=axis)
    gt_peaks = _peak_positions(gt_centerline, axis=axis)
    pred_pitch = _median_pitch(pred_peaks)
    gt_pitch = _median_pitch(gt_peaks)
    if pred_peaks.size == 0 or gt_peaks.size == 0:
        return {
            "grid_pred_peak_count": int(pred_peaks.size),
            "grid_gt_peak_count": int(gt_peaks.size),
            "grid_pitch_error_px": float("inf"),
            "grid_phase_error_px": float("inf"),
        }
    pitch_error = abs(pred_pitch - gt_pitch) if np.isfinite(pred_pitch) and np.isfinite(gt_pitch) else float("inf")
    period = gt_pitch if np.isfinite(gt_pitch) and gt_pitch > 0 else max(1.0, float(abs(gt_peaks[-1] - gt_peaks[0])))
    raw_phase = abs((pred_peaks[0] - gt_peaks[0]) % period)
    phase_error = min(raw_phase, period - raw_phase)
    return {
        "grid_pred_peak_count": int(pred_peaks.size),
        "grid_gt_peak_count": int(gt_peaks.size),
        "grid_pred_pitch_px": float(pred_pitch),
        "grid_gt_pitch_px": float(gt_pitch),
        "grid_pitch_error_px": float(pitch_error),
        "grid_phase_error_px": float(phase_error),
    }


def _components(mask: np.ndarray) -> list[dict]:
    m = _as_mask(mask).astype(np.uint8)
    n, labels, stats, centroids = cv2.connectedComponentsWithStats(m, connectivity=8)
    comps = []
    for idx in range(1, n):
        area = int(stats[idx, cv2.CC_STAT_AREA])
        if area <= 0:
            continue
        comps.append({"area": area, "centroid": np.asarray(centroids[idx], dtype=np.float64)})
    return comps


def component_detection_metrics(pred_mask: np.ndarray, gt_mask: np.ndarray, *, centroid_tolerance_px: float = 3.0) -> dict:
    pred = _components(pred_mask)
    gt = _components(gt_mask)
    if not gt:
        recall = 1.0
    elif not pred:
        recall = 0.0
    else:
        hits = 0
        pred_centroids = np.stack([c["centroid"] for c in pred], axis=0)
        for comp in gt:
            d = np.sqrt(np.sum((pred_centroids - comp["centroid"]) ** 2, axis=1))
            hits += int(np.any(d <= float(centroid_tolerance_px)))
        recall = hits / len(gt)
    if not pred:
        precision = 1.0 if not gt else 0.0
    elif not gt:
        precision = 0.0
    else:
        gt_centroids = np.stack([c["centroid"] for c in gt], axis=0)
        hits = 0
        for comp in pred:
            d = np.sqrt(np.sum((gt_centroids - comp["centroid"]) ** 2, axis=1))
            hits += int(np.any(d <= float(centroid_tolerance_px)))
        precision = hits / len(pred)
    return {
        "pred_component_count": len(pred),
        "gt_component_count": len(gt),
        "component_precision": float(precision),
        "component_recall": float(recall),
    }


def compute_psnr(pred: np.ndarray, gt: np.ndarray) -> float:
    p = _to_float01(pred)
    g = _to_float01(gt)
    mse = float(np.mean((p - g) ** 2))
    if mse <= 1e-12:
        return 99.0
    return float(20.0 * np.log10(1.0 / np.sqrt(mse)))


def high_frequency_ratio(img: np.ndarray, cutoff: float = 0.28) -> float:
    f = _to_float01(img)
    f = f - float(f.mean())
    power = np.abs(np.fft.fftshift(np.fft.fft2(f))) ** 2
    total = float(power.sum())
    if total <= 1e-12:
        return 0.0
    h, w = power.shape
    yy, xx = np.mgrid[0:h, 0:w]
    rr = np.sqrt(((yy - h / 2) / (h / 2)) ** 2 + ((xx - w / 2) / (w / 2)) ** 2)
    return float(power[rr >= cutoff].sum() / total)


def _gradient_magnitude(img: np.ndarray) -> np.ndarray:
    f = _to_float01(img).astype(np.float32)
    gx = cv2.Sobel(f, cv2.CV_32F, 1, 0, ksize=3)
    gy = cv2.Sobel(f, cv2.CV_32F, 0, 1, ksize=3)
    return np.sqrt(gx * gx + gy * gy)


def _matched_gradient_boundary(img: np.ndarray, *, target_count: int | None = None) -> np.ndarray:
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


def image_metric_row(pred: np.ndarray, gt: np.ndarray, *, boundary: np.ndarray | None = None, centerline: np.ndarray | None = None) -> dict:
    row = {
        "psnr": compute_psnr(pred, gt),
        "pred_high_frequency_ratio": high_frequency_ratio(pred),
        "gt_high_frequency_ratio": high_frequency_ratio(gt),
    }
    row["high_frequency_retention"] = 0.0 if row["gt_high_frequency_ratio"] <= 1e-12 else float(row["pred_high_frequency_ratio"] / row["gt_high_frequency_ratio"])
    gt_boundary = boundary if boundary is not None else _matched_gradient_boundary(gt)
    pred_boundary = _matched_gradient_boundary(pred, target_count=int(_as_mask(gt_boundary).sum()))
    row.update(binary_boundary_metrics(pred_boundary, gt_boundary, tolerances=(0.5, 1.0, 2.0)))
    if centerline is not None and int(_as_mask(centerline).sum()) > 0:
        pred_center = _matched_gradient_boundary(pred, target_count=int(_as_mask(centerline).sum()))
        center_metrics = binary_boundary_metrics(pred_center, centerline, tolerances=(1.0, 2.0))
        row["centerline_mean_distance_px"] = center_metrics["mean_symmetric_boundary_distance_px"]
        row["centerline_fscore_t1p0"] = center_metrics["fscore_t1p0"]
        row.update(grid_pitch_phase_error(pred_center, centerline, axis=1))
    return row


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
    stages = [stage for stage in manifest["count_by_stage"] if stage.startswith("stage_34") or stage.startswith("stage_35") or stage.startswith("stage_36") or stage.startswith("stage_37") or stage.startswith("stage_38") or stage.startswith("stage_39") or stage.startswith("stage_40")]
    stage_results = []
    all_rows: list[dict] = []
    for stage in stages:
        out_dir = _latest_stage_output(recon_root, profile, stage)
        gt_dir = profile_dir / "lbl" / stage
        boundary_dir = profile_dir / "geom" / "boundary" / stage
        center_dir = profile_dir / "geom" / "centerline" / stage
        rows = []
        for gt_path in _image_paths(gt_dir):
            pred_path = out_dir / gt_path.name
            if not pred_path.exists():
                raise FileNotFoundError(f"missing reconstruction: {pred_path}")
            pred = _read_gray(pred_path)
            gt = _read_gray(gt_path)
            boundary = _read_gray(boundary_dir / gt_path.name)
            centerline = _read_gray(center_dir / gt_path.name)
            row = image_metric_row(pred, gt, boundary=boundary, centerline=centerline)
            row["filename"] = gt_path.name
            rows.append(row)
        all_rows.extend(rows)
        stage_results.append(
            {
                "stage": stage,
                "count": len(rows),
                "avg_psnr": _avg(rows, "psnr"),
                "avg_hf_retention": _avg(rows, "high_frequency_retention"),
                "avg_boundary_distance_px": _avg(rows, "mean_symmetric_boundary_distance_px"),
                "avg_boundary_fscore_t1p0": _avg(rows, "fscore_t1p0"),
                "avg_centerline_distance_px": _avg(rows, "centerline_mean_distance_px"),
                "avg_grid_pitch_error_px": _avg(rows, "grid_pitch_error_px"),
                "output_dir": str(out_dir),
            }
        )
    return {
        "profile": profile,
        "data_root": str(data_root.resolve()),
        "recon_root": str(recon_root.resolve()),
        "total_count": len(all_rows),
        "overall_avg_psnr": _avg(all_rows, "psnr"),
        "overall_hf_retention": _avg(all_rows, "high_frequency_retention"),
        "overall_boundary_distance_px": _avg(all_rows, "mean_symmetric_boundary_distance_px"),
        "overall_boundary_fscore_t1p0": _avg(all_rows, "fscore_t1p0"),
        "stages": stage_results,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Summarize R42 boundary-fidelity reconstruction metrics.")
    parser.add_argument("--profile", default="boundary_val_unseen")
    parser.add_argument("--data-root", type=Path, default=DEFAULT_DATA_ROOT)
    parser.add_argument("--recon-root", type=Path, default=DEFAULT_RECON_ROOT)
    parser.add_argument("--output-json", type=Path, default=DEFAULT_RECON_ROOT / "boundary_val_unseen_summary.json")
    args = parser.parse_args(argv)

    summary = summarize(args.profile, args.data_root, args.recon_root)
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    print(f"[R42] summary written to {args.output_json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

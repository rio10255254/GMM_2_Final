"""R41 microscopy-feature reconstruction metrics."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import cv2
import numpy as np


_REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_DATA_ROOT = _REPO_ROOT / "Training_Data" / "r41_ring_distillation"
DEFAULT_RECON_ROOT = _REPO_ROOT / "Experiments" / "R41_RingDistillation" / "results" / "micro_recon"
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


def compute_psnr(pred: np.ndarray, gt: np.ndarray) -> float:
    p = _to_float01(pred)
    g = _to_float01(gt)
    mse = float(np.mean((p - g) ** 2))
    if mse <= 1e-12:
        return 99.0
    return float(20.0 * np.log10(1.0 / np.sqrt(mse)))


def compute_ssim(pred: np.ndarray, gt: np.ndarray) -> float:
    p = _to_float01(pred)
    g = _to_float01(gt)
    c1 = 0.01 ** 2
    c2 = 0.03 ** 2
    mu_p = float(p.mean())
    mu_g = float(g.mean())
    var_p = float(p.var())
    var_g = float(g.var())
    cov = float(((p - mu_p) * (g - mu_g)).mean())
    num = (2 * mu_p * mu_g + c1) * (2 * cov + c2)
    den = (mu_p ** 2 + mu_g ** 2 + c1) * (var_p + var_g + c2)
    return float(num / den) if den else 0.0


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


def edge_energy(img: np.ndarray) -> float:
    f = _to_float01(img).astype(np.float32)
    gx = cv2.Sobel(f, cv2.CV_32F, 1, 0, ksize=3)
    gy = cv2.Sobel(f, cv2.CV_32F, 0, 1, ksize=3)
    return float(np.sqrt(gx * gx + gy * gy).mean())


def contrast_std(img: np.ndarray) -> float:
    return float(_to_float01(img).std())


def _ratio(pred_value: float, gt_value: float) -> float:
    if gt_value <= 1e-12:
        return 0.0
    return float(pred_value / gt_value)


def image_metric_row(pred: np.ndarray, gt: np.ndarray) -> dict:
    pred_hf = high_frequency_ratio(pred)
    gt_hf = high_frequency_ratio(gt)
    pred_edge = edge_energy(pred)
    gt_edge = edge_energy(gt)
    pred_contrast = contrast_std(pred)
    gt_contrast = contrast_std(gt)
    return {
        "psnr": compute_psnr(pred, gt),
        "ssim": compute_ssim(pred, gt),
        "pred_high_frequency_ratio": pred_hf,
        "gt_high_frequency_ratio": gt_hf,
        "high_frequency_retention": _ratio(pred_hf, gt_hf),
        "pred_edge_energy": pred_edge,
        "gt_edge_energy": gt_edge,
        "edge_retention": _ratio(pred_edge, gt_edge),
        "pred_contrast_std": pred_contrast,
        "gt_contrast_std": gt_contrast,
        "contrast_retention": _ratio(pred_contrast, gt_contrast),
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
    return float(sum(float(r[key]) for r in rows) / len(rows))


def summarize(profile: str, data_root: Path, recon_root: Path) -> dict:
    profile_dir = data_root / profile
    manifest = _load_manifest(profile_dir)
    families = manifest.get("micro_stage_families", {})
    stages = [stage for stage in manifest["count_by_stage"] if stage != "ring"]

    stage_results = []
    all_rows: list[dict] = []
    for stage in stages:
        out_dir = _latest_stage_output(recon_root, profile, stage)
        gt_dir = profile_dir / "lbl" / stage
        rows: list[dict] = []
        missing = []
        for gt_path in _image_paths(gt_dir):
            pred_path = out_dir / gt_path.name
            if not pred_path.exists():
                missing.append(gt_path.name)
                continue
            pred = _read_gray(pred_path)
            gt = _read_gray(gt_path)
            if pred.shape != gt.shape:
                raise RuntimeError(f"shape mismatch for {stage}/{gt_path.name}: pred={pred.shape}, gt={gt.shape}")
            row = image_metric_row(pred, gt)
            row["filename"] = gt_path.name
            rows.append(row)
        if missing:
            raise FileNotFoundError(f"{stage} missing reconstructions: {missing[:5]}")
        if not rows:
            raise RuntimeError(f"{stage} produced no comparable reconstructions")
        all_rows.extend(rows)
        stage_results.append(
            {
                "stage": stage,
                "feature_family": families.get(stage, "unknown"),
                "count": len(rows),
                "avg_psnr": _avg(rows, "psnr"),
                "avg_ssim": _avg(rows, "ssim"),
                "avg_high_frequency_retention": _avg(rows, "high_frequency_retention"),
                "avg_edge_retention": _avg(rows, "edge_retention"),
                "avg_contrast_retention": _avg(rows, "contrast_retention"),
                "output_dir": str(out_dir),
            }
        )

    return {
        "profile": profile,
        "data_root": str(data_root.resolve()),
        "recon_root": str(recon_root.resolve()),
        "total_count": len(all_rows),
        "overall_avg_psnr": _avg(all_rows, "psnr"),
        "overall_avg_ssim": _avg(all_rows, "ssim"),
        "overall_high_frequency_retention": _avg(all_rows, "high_frequency_retention"),
        "overall_edge_retention": _avg(all_rows, "edge_retention"),
        "overall_contrast_retention": _avg(all_rows, "contrast_retention"),
        "stages": stage_results,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Summarize R41 microscopy-feature reconstruction metrics.")
    parser.add_argument("--profile", default="micro_val_unseen")
    parser.add_argument("--data-root", type=Path, default=DEFAULT_DATA_ROOT)
    parser.add_argument("--recon-root", type=Path, default=DEFAULT_RECON_ROOT)
    parser.add_argument(
        "--output-json",
        type=Path,
        default=DEFAULT_RECON_ROOT / "micro_val_unseen_summary.json",
    )
    args = parser.parse_args(argv)

    summary = summarize(args.profile, args.data_root, args.recon_root)
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    print(f"[R41] summary written to {args.output_json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

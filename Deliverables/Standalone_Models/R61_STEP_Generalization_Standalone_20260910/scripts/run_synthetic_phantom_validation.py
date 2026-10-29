"""Synthetic phantom boundary validation for R60 boundary-focus checkpoints."""
from __future__ import annotations

import argparse
import csv
import json
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np


PACKAGE_ROOT = Path(__file__).resolve().parents[1]
EXPERIMENT_DIR = PACKAGE_ROOT
LAB_ROOT = PACKAGE_ROOT
PROJECT_ROOT = PACKAGE_ROOT
MODEL_DIR = PACKAGE_ROOT
INFER_SCRIPT = PACKAGE_ROOT / "infer_r61.py"
LAB_PSF_PATH = PACKAGE_ROOT / "psf" / "PSF_fitted_2D_FOVstack.mat"
DEFAULT_WEIGHTS = PACKAGE_ROOT / "weights" / "best_tradeoff.pth.tar"
DEFAULT_OUTPUT_ROOT = PACKAGE_ROOT / "results" / "validation" / "synthetic_phantom_validation"
PHANTOM_FILENAME = "synthetic_mixed_phantom.bmp"


@dataclass(frozen=True)
class PhantomRegion:
    name: str
    shape: str
    polarity: str
    truth_mask: np.ndarray


@dataclass(frozen=True)
class SyntheticPhantom:
    truth_image: np.ndarray
    input_image: np.ndarray
    regions: tuple[PhantomRegion, ...]


def _python() -> str:
    return sys.executable or "python"


def _kernel(radius_px: float) -> np.ndarray:
    r = max(1, int(round(float(radius_px))))
    k = 2 * r + 1
    return cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k, k))


def _draw_rotated_rect(mask: np.ndarray, center: tuple[float, float], size: tuple[float, float], angle: float) -> None:
    rect = (center, size, angle)
    points = cv2.boxPoints(rect).astype(np.int32)
    cv2.fillPoly(mask, [points], 255)


def _draw_polygon(mask: np.ndarray, points: list[tuple[float, float]]) -> None:
    arr = np.asarray(points, dtype=np.int32)
    cv2.fillPoly(mask, [arr], 255)


def _empty_mask(size: int) -> np.ndarray:
    return np.zeros((int(size), int(size)), dtype=np.uint8)


def _make_regions(size: int) -> tuple[PhantomRegion, ...]:
    s = float(size)
    specs = []

    m = _empty_mask(size)
    cv2.circle(m, (int(0.18 * s), int(0.18 * s)), int(0.060 * s), 255, -1)
    specs.append(PhantomRegion("dark_circle", "circle", "dark", m))

    m = _empty_mask(size)
    cv2.ellipse(m, (int(0.44 * s), int(0.18 * s)), (int(0.082 * s), int(0.050 * s)), 25, 0, 360, 255, -1)
    specs.append(PhantomRegion("dark_ellipse", "ellipse", "dark", m))

    m = _empty_mask(size)
    _draw_rotated_rect(m, (0.72 * s, 0.20 * s), (0.17 * s, 0.070 * s), -18)
    specs.append(PhantomRegion("dark_rotated_rect", "rotated_rect", "dark", m))

    m = _empty_mask(size)
    cv2.circle(m, (int(0.20 * s), int(0.53 * s)), int(0.055 * s), 255, -1)
    specs.append(PhantomRegion("bright_circle", "circle", "bright", m))

    m = _empty_mask(size)
    cv2.ellipse(m, (int(0.45 * s), int(0.55 * s)), (int(0.075 * s), int(0.045 * s)), -35, 0, 360, 255, -1)
    specs.append(PhantomRegion("bright_ellipse", "ellipse", "bright", m))

    m = _empty_mask(size)
    _draw_polygon(
        m,
        [
            (0.70 * s, 0.48 * s),
            (0.78 * s, 0.54 * s),
            (0.73 * s, 0.64 * s),
            (0.62 * s, 0.60 * s),
            (0.62 * s, 0.51 * s),
        ],
    )
    specs.append(PhantomRegion("bright_irregular", "irregular", "bright", m))

    m = _empty_mask(size)
    _draw_rotated_rect(m, (0.34 * s, 0.82 * s), (0.48 * s, 0.050 * s), 8)
    specs.append(PhantomRegion("dark_slanted_bar", "slanted_bar", "dark", m))

    m = _empty_mask(size)
    _draw_rotated_rect(m, (0.73 * s, 0.82 * s), (0.34 * s, 0.045 * s), -13)
    specs.append(PhantomRegion("bright_slanted_bar", "slanted_bar", "bright", m))

    return tuple(specs)


def _biased_mask(mask: np.ndarray, polarity: str, bias_px: float) -> np.ndarray:
    k = _kernel(abs(float(bias_px)))
    if polarity == "dark":
        return cv2.erode(mask, k)
    return cv2.dilate(mask, k)


def _render_from_regions(regions: tuple[PhantomRegion, ...], *, source: bool, bias_px: float) -> np.ndarray:
    size = int(regions[0].truth_mask.shape[0])
    img = np.full((size, size), 138, dtype=np.float32)
    for region in regions:
        mask = _biased_mask(region.truth_mask, region.polarity, bias_px) if source else region.truth_mask
        if region.polarity == "dark":
            img[mask > 0] = 42
        else:
            img[mask > 0] = 218
    return img


def render_synthetic_phantom(
    *,
    size: int = 512,
    bias_px: float = 2.0,
    blur_sigma: float = 1.35,
    noise_sigma: float = 2.0,
    seed: int = 1337,
) -> SyntheticPhantom:
    regions = _make_regions(int(size))
    truth = _render_from_regions(regions, source=False, bias_px=bias_px)
    source = _render_from_regions(regions, source=True, bias_px=bias_px)

    if blur_sigma > 0:
        source = cv2.GaussianBlur(source, (0, 0), float(blur_sigma))

    yy, xx = np.mgrid[0:size, 0:size].astype(np.float32)
    gradient = 1.0 + 0.040 * ((xx / max(1, size - 1)) - 0.5) - 0.025 * ((yy / max(1, size - 1)) - 0.5)
    source = source * gradient

    if noise_sigma > 0:
        rng = np.random.default_rng(int(seed))
        source = source + rng.normal(0.0, float(noise_sigma), size=source.shape)

    return SyntheticPhantom(
        truth_image=np.clip(truth, 0, 255).astype(np.uint8),
        input_image=np.clip(source, 0, 255).astype(np.uint8),
        regions=regions,
    )


def _bbox_from_mask(mask: np.ndarray, pad: int = 10) -> tuple[int, int, int, int]:
    ys, xs = np.where(mask > 0)
    if len(xs) == 0:
        raise ValueError("empty region mask")
    h, w = mask.shape
    x0 = max(0, int(xs.min()) - pad)
    x1 = min(w, int(xs.max()) + pad + 1)
    y0 = max(0, int(ys.min()) - pad)
    y1 = min(h, int(ys.max()) + pad + 1)
    return x0, y0, x1, y1


def _segment_roi(roi: np.ndarray, polarity: str) -> np.ndarray:
    roi_u8 = np.clip(roi, 0, 255).astype(np.uint8)
    _threshold, otsu = cv2.threshold(roi_u8, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    if polarity == "dark":
        return (otsu == 0).astype(np.uint8) * 255
    return (otsu > 0).astype(np.uint8) * 255


def _boundary(mask: np.ndarray) -> np.ndarray:
    mask_u8 = (mask > 0).astype(np.uint8)
    k = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
    grad = cv2.morphologyEx(mask_u8, cv2.MORPH_GRADIENT, k)
    return grad > 0


def _chamfer_px(pred_mask: np.ndarray, truth_mask: np.ndarray) -> float:
    pred_b = _boundary(pred_mask)
    truth_b = _boundary(truth_mask)
    if not pred_b.any() or not truth_b.any():
        return float("nan")
    dt_truth = cv2.distanceTransform((~truth_b).astype(np.uint8), cv2.DIST_L2, 3)
    dt_pred = cv2.distanceTransform((~pred_b).astype(np.uint8), cv2.DIST_L2, 3)
    pred_to_truth = float(dt_truth[pred_b].mean())
    truth_to_pred = float(dt_pred[truth_b].mean())
    return 0.5 * (pred_to_truth + truth_to_pred)


def measure_boundary_table(phantom: SyntheticPhantom, image: np.ndarray, *, image_label: str) -> list[dict]:
    rows: list[dict] = []
    for region in phantom.regions:
        x0, y0, x1, y1 = _bbox_from_mask(region.truth_mask, pad=14)
        truth_roi = region.truth_mask[y0:y1, x0:x1]
        img_roi = image[y0:y1, x0:x1]
        pred_roi = _segment_roi(img_roi, region.polarity)
        true_area = float((truth_roi > 0).sum())
        pred_area = float((pred_roi > 0).sum())
        rows.append(
            {
                "image": image_label,
                "region": region.name,
                "shape": region.shape,
                "polarity": region.polarity,
                "chamfer_px": float(_chamfer_px(pred_roi, truth_roi)),
                "area_error_px2": float(pred_area - true_area),
                "abs_area_error_px2": float(abs(pred_area - true_area)),
            }
        )
    return rows


def build_reconstruct_command(
    *,
    weights: Path,
    input_dir: Path,
    recon_root: Path,
    output_name: str,
    device: str,
) -> list[str]:
    return [
        _python(),
        "-u",
        str(INFER_SCRIPT),
        "--weights",
        str(Path(weights)),
        "--input-dir",
        str(Path(input_dir)),
        "--recon-root",
        str(Path(recon_root)),
        "--output-name",
        str(output_name),
        "--device",
        str(device),
        "--align-factor",
        "64",
        "--exts",
        ".bmp",
        "--psf-fitted-path",
        str(LAB_PSF_PATH),
        "--no-psf-from-ckpt",
        "--weak-psf-disable",
        "--psf-deconv-reg",
        "30.0",
        "--psf-phys-alpha",
        "0.0",
    ]


def _run_command(command: list[str], *, log_path: Path) -> None:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("w", encoding="utf-8", errors="replace") as log:
        proc = subprocess.run(command, stdout=log, stderr=subprocess.STDOUT, text=True)
    if proc.returncode != 0:
        raise RuntimeError(f"command failed with code {proc.returncode}: {log_path}")


def find_reconstructed_image(*, recon_root: Path, output_name: str, target_image: str = PHANTOM_FILENAME) -> Path:
    direct = sorted(Path(recon_root).glob(f"*/{output_name}/{target_image}"), key=lambda p: p.stat().st_mtime, reverse=True)
    if direct:
        return direct[0]
    fallback = [p for p in Path(recon_root).rglob(target_image) if p.parent.name == output_name or output_name in str(p.parent)]
    if fallback:
        return max(fallback, key=lambda p: p.stat().st_mtime)
    raise FileNotFoundError(f"no reconstructed {target_image} found for {output_name} under {recon_root}")


def _write_rows_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = ["image", "region", "shape", "polarity", "chamfer_px", "area_error_px2", "abs_area_error_px2"]
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _mean_chamfer(rows: list[dict]) -> float:
    vals = [float(row["chamfer_px"]) for row in rows if np.isfinite(float(row["chamfer_px"]))]
    return float(np.mean(vals)) if vals else float("nan")


def _make_boundary_overlay(phantom: SyntheticPhantom, image: np.ndarray) -> np.ndarray:
    rgb = cv2.cvtColor(np.clip(image, 0, 255).astype(np.uint8), cv2.COLOR_GRAY2BGR)
    for region in phantom.regions:
        x0, y0, x1, y1 = _bbox_from_mask(region.truth_mask, pad=14)
        truth_roi = region.truth_mask[y0:y1, x0:x1]
        pred_roi = _segment_roi(image[y0:y1, x0:x1], region.polarity)
        truth_b = _boundary(truth_roi)
        pred_b = _boundary(pred_roi)
        crop = rgb[y0:y1, x0:x1]
        crop[truth_b] = (0, 220, 0)
        crop[pred_b] = (0, 0, 255)
        rgb[y0:y1, x0:x1] = crop
    return rgb


def _label_panel(image: np.ndarray, label: str) -> np.ndarray:
    if image.ndim == 2:
        panel = cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)
    else:
        panel = image.copy()
    header = np.full((36, panel.shape[1], 3), 245, dtype=np.uint8)
    cv2.putText(header, label, (8, 24), cv2.FONT_HERSHEY_SIMPLEX, 0.58, (0, 0, 0), 1, cv2.LINE_AA)
    return np.vstack([header, panel])


def write_comparison_image(path: Path, phantom: SyntheticPhantom, recon_image: np.ndarray | None) -> None:
    panels = [
        _label_panel(phantom.truth_image, "truth sharp image"),
        _label_panel(_make_boundary_overlay(phantom, phantom.input_image), "input: red=measured, green=truth"),
    ]
    if recon_image is not None:
        panels.append(_label_panel(_make_boundary_overlay(phantom, recon_image), "model recon: red=measured, green=truth"))
    h = max(p.shape[0] for p in panels)
    padded = []
    for panel in panels:
        if panel.shape[0] < h:
            pad = np.full((h - panel.shape[0], panel.shape[1], 3), 245, dtype=np.uint8)
            panel = np.vstack([panel, pad])
        padded.append(panel)
    gap = np.full((h, 12, 3), 245, dtype=np.uint8)
    montage = padded[0]
    for panel in padded[1:]:
        montage = np.hstack([montage, gap, panel])
    path.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(path), montage)


def write_manifest(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def run_validation(args: argparse.Namespace) -> dict:
    stamp = time.strftime("%Y%m%d_%H%M%S")
    output_root = Path(args.output_root).resolve()
    run_dir = output_root / f"phantom_validation_{stamp}"
    input_dir = run_dir / "input"
    input_dir.mkdir(parents=True, exist_ok=True)

    phantom = render_synthetic_phantom(
        size=int(args.size),
        bias_px=float(args.bias_px),
        blur_sigma=float(args.blur_sigma),
        noise_sigma=float(args.noise_sigma),
        seed=int(args.seed),
    )
    truth_path = run_dir / "truth_sharp.bmp"
    input_path = input_dir / PHANTOM_FILENAME
    cv2.imwrite(str(truth_path), phantom.truth_image)
    cv2.imwrite(str(input_path), phantom.input_image)

    rows = []
    truth_rows = measure_boundary_table(phantom, phantom.truth_image, image_label="truth")
    input_rows = measure_boundary_table(phantom, phantom.input_image, image_label="input_biased_blurred")
    rows.extend(truth_rows)
    rows.extend(input_rows)

    recon_image = None
    recon_path = None
    if not bool(args.skip_reconstruct):
        output_name = "synthetic_phantom_boundary_focus_recon"
        command = build_reconstruct_command(
            weights=Path(args.weights).resolve(),
            input_dir=input_dir,
            recon_root=run_dir / "recon",
            output_name=output_name,
            device=str(args.device),
        )
        _run_command(command, log_path=run_dir / "logs" / "reconstruct.log")
        recon_path = find_reconstructed_image(recon_root=run_dir / "recon", output_name=output_name)
        recon_image = cv2.imread(str(recon_path), cv2.IMREAD_GRAYSCALE)
        if recon_image is None:
            raise RuntimeError(f"failed to read reconstructed phantom: {recon_path}")
        recon_rows = measure_boundary_table(phantom, recon_image, image_label="model_recon")
        rows.extend(recon_rows)
    else:
        recon_rows = []

    metrics_csv = run_dir / "boundary_metrics.csv"
    _write_rows_csv(metrics_csv, rows)

    comparison_path = run_dir / "phantom_boundary_overlay.png"
    write_comparison_image(comparison_path, phantom, recon_image)

    input_mean = _mean_chamfer(input_rows)
    recon_mean = _mean_chamfer(recon_rows) if recon_rows else float("nan")
    summary = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "weights": str(Path(args.weights).resolve()),
        "run_dir": str(run_dir),
        "truth_image": str(truth_path),
        "input_image": str(input_path),
        "reconstructed_image": str(recon_path) if recon_path is not None else "",
        "metrics_csv": str(metrics_csv),
        "comparison_image": str(comparison_path),
        "phantom_size_px": int(args.size),
        "input_bias_px": float(args.bias_px),
        "blur_sigma_px": float(args.blur_sigma),
        "noise_sigma": float(args.noise_sigma),
        "truth_mean_chamfer_px": _mean_chamfer(truth_rows),
        "input_mean_chamfer_px": input_mean,
        "recon_mean_chamfer_px": recon_mean,
        "mean_improvement_px": float(input_mean - recon_mean) if np.isfinite(recon_mean) else float("nan"),
        "regions": rows,
    }
    write_manifest(run_dir / "summary.json", summary)
    return summary


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run synthetic phantom boundary validation")
    parser.add_argument("--weights", type=Path, default=DEFAULT_WEIGHTS)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--device", default="cuda:0")
    parser.add_argument("--size", type=int, default=512)
    parser.add_argument("--bias-px", type=float, default=2.0)
    parser.add_argument("--blur-sigma", type=float, default=1.35)
    parser.add_argument("--noise-sigma", type=float, default=2.0)
    parser.add_argument("--seed", type=int, default=1337)
    parser.add_argument("--skip-reconstruct", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    summary = run_validation(args)
    printable = {k: v for k, v in summary.items() if k != "regions"}
    print(json.dumps(printable, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

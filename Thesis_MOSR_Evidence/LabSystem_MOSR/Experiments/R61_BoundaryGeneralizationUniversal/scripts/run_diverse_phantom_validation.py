"""Diverse synthetic phantom validation for R61 boundary generalization."""
from __future__ import annotations

import argparse
import csv
import json
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import cv2
import numpy as np


EXPERIMENT_DIR = Path(__file__).resolve().parents[1]
LAB_ROOT = Path(__file__).resolve().parents[3]
PROJECT_ROOT = Path(__file__).resolve().parents[5]
MODEL_DIR = PROJECT_ROOT / "Model"
R60_SCRIPT_DIR = LAB_ROOT / "Experiments" / "R60_SEMTruthBoundaryTraining" / "scripts"
INFER_SCRIPT = MODEL_DIR / "GeoEdgeAlignSR_v1_Infer_v5_NoCoord_return_v2_SimpleTest.py"
LAB_PSF_PATH = (
    LAB_ROOT
    / "psf_calibration"
    / "results"
    / "20250605_inner_circle_roi_fine_prealign_fit"
    / "PSF_fitted_2D_FOVstack.mat"
)
DEFAULT_OUTPUT_ROOT = EXPERIMENT_DIR / "reports" / "diverse_phantom_validation"
DEFAULT_WEIGHTS = (
    LAB_ROOT
    / "Traing_Progress"
    / "training_progress_LAB_GESR_v1_v5_ST0p8_SWP_r60_semtruth_boundary_focus_boundary_focus_e008_mtb064_20260622_20260622_020906"
    / "epoch_005.pth.tar"
)

sys.path.insert(0, str(R60_SCRIPT_DIR))
from run_synthetic_phantom_validation import (  # noqa: E402
    PhantomRegion,
    SyntheticPhantom,
    _bbox_from_mask,
    _boundary,
    _chamfer_px,
    _segment_roi,
)


@dataclass(frozen=True)
class DiverseCase:
    case_id: str
    seed: int
    bias_px: float
    blur_sigma: float
    noise_sigma: float


def _python() -> str:
    return sys.executable or "python"


def _parse_float_list(text: str) -> list[float]:
    values = [float(part.strip()) for part in str(text).split(",") if part.strip()]
    if not values:
        raise ValueError("empty numeric list")
    return values


def _parse_int_list(text: str) -> list[int]:
    values = [int(part.strip()) for part in str(text).split(",") if part.strip()]
    if not values:
        raise ValueError("empty seed list")
    return values


def _kernel_radius(radius_px: float) -> np.ndarray | None:
    radius = max(0, int(round(float(radius_px))))
    if radius <= 0:
        return None
    return cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * radius + 1, 2 * radius + 1))


def _biased_mask(mask: np.ndarray, polarity: str, bias_px: float) -> np.ndarray:
    kernel = _kernel_radius(abs(float(bias_px)))
    if kernel is None:
        return mask.copy()
    if polarity == "dark":
        return cv2.erode(mask, kernel)
    return cv2.dilate(mask, kernel)


def _draw_rotated_rect(mask: np.ndarray, center: tuple[float, float], size: tuple[float, float], angle: float) -> None:
    points = cv2.boxPoints((center, size, angle)).astype(np.int32)
    cv2.fillPoly(mask, [points], 255, lineType=cv2.LINE_AA)


def _draw_polygon(mask: np.ndarray, rng: np.random.Generator, center: tuple[float, float], radius: float, n: int) -> None:
    angles = np.linspace(0, 2 * np.pi, int(n), endpoint=False)
    angles += float(rng.uniform(-0.12, 0.12))
    points = []
    for angle in angles:
        rr = radius * float(rng.uniform(0.72, 1.18))
        points.append((center[0] + rr * np.cos(angle), center[1] + rr * np.sin(angle)))
    cv2.fillPoly(mask, [np.asarray(points, dtype=np.int32)], 255, lineType=cv2.LINE_AA)


def _region_mask(
    *,
    size: int,
    shape: str,
    center: tuple[float, float],
    scale: float,
    angle: float,
    rng: np.random.Generator,
) -> np.ndarray:
    mask = np.zeros((int(size), int(size)), dtype=np.uint8)
    if shape == "circle":
        cv2.circle(mask, (int(center[0]), int(center[1])), int(scale), 255, -1, lineType=cv2.LINE_AA)
    elif shape == "ellipse":
        axes = (int(scale * rng.uniform(1.25, 1.75)), int(scale * rng.uniform(0.62, 0.92)))
        cv2.ellipse(mask, (int(center[0]), int(center[1])), axes, float(angle), 0, 360, 255, -1, lineType=cv2.LINE_AA)
    elif shape == "rotated_rect":
        _draw_rotated_rect(mask, center, (scale * rng.uniform(2.0, 2.8), scale * rng.uniform(0.8, 1.25)), angle)
    elif shape == "polygon":
        _draw_polygon(mask, rng, center, scale * rng.uniform(1.25, 1.65), int(rng.integers(5, 8)))
    elif shape == "thin_bar":
        _draw_rotated_rect(mask, center, (scale * rng.uniform(3.0, 4.4), scale * rng.uniform(0.35, 0.58)), angle)
    elif shape == "annulus":
        outer = int(scale * rng.uniform(1.18, 1.42))
        inner = max(2, int(outer * rng.uniform(0.42, 0.58)))
        cv2.circle(mask, (int(center[0]), int(center[1])), outer, 255, -1, lineType=cv2.LINE_AA)
        cv2.circle(mask, (int(center[0]), int(center[1])), inner, 0, -1, lineType=cv2.LINE_AA)
    else:
        raise ValueError(f"unknown shape: {shape}")
    return mask


def _render_from_regions(
    regions: tuple[PhantomRegion, ...],
    *,
    source: bool,
    bias_px: float,
    bg: float,
    dark_fg: float,
    bright_fg: float,
) -> np.ndarray:
    size = int(regions[0].truth_mask.shape[0])
    img = np.full((size, size), float(bg), dtype=np.float32)
    for region in regions:
        mask = _biased_mask(region.truth_mask, region.polarity, bias_px) if source else region.truth_mask
        alpha = (mask.astype(np.float32) / 255.0).clip(0, 1)
        fg = float(dark_fg if region.polarity == "dark" else bright_fg)
        img = img * (1.0 - alpha) + fg * alpha
    return img


def render_diverse_phantom(
    *,
    size: int = 512,
    bias_px: float = 1.5,
    blur_sigma: float = 1.25,
    noise_sigma: float = 2.0,
    seed: int = 7001,
) -> SyntheticPhantom:
    rng = np.random.default_rng(int(seed))
    shapes = ["circle", "ellipse", "rotated_rect", "polygon", "thin_bar", "annulus"]
    regions: list[PhantomRegion] = []
    cols = 4
    rows = 3
    cell_w = float(size) / cols
    cell_h = float(size) / rows
    for idx in range(12):
        row = idx // cols
        col = idx % cols
        shape = shapes[idx % len(shapes)]
        polarity = "dark" if idx % 2 == 0 else "bright"
        cx = (col + 0.5 + float(rng.uniform(-0.16, 0.16))) * cell_w
        cy = (row + 0.5 + float(rng.uniform(-0.16, 0.16))) * cell_h
        scale = min(cell_w, cell_h) * float(rng.uniform(0.16, 0.24))
        angle = float(rng.uniform(-60, 60))
        mask = _region_mask(size=int(size), shape=shape, center=(cx, cy), scale=scale, angle=angle, rng=rng)
        regions.append(PhantomRegion(f"{polarity}_{shape}_{idx:02d}", shape, polarity, mask))

    bg = float(rng.uniform(118, 148))
    dark_fg = float(rng.uniform(28, 60))
    bright_fg = float(rng.uniform(196, 232))
    truth = _render_from_regions(tuple(regions), source=False, bias_px=bias_px, bg=bg, dark_fg=42, bright_fg=218)
    source = _render_from_regions(tuple(regions), source=True, bias_px=bias_px, bg=bg, dark_fg=dark_fg, bright_fg=bright_fg)
    if blur_sigma > 0:
        source = cv2.GaussianBlur(source, (0, 0), float(blur_sigma))
    yy, xx = np.mgrid[0:size, 0:size].astype(np.float32)
    source *= 1.0 + float(rng.uniform(-0.055, 0.055)) * ((xx / max(1, size - 1)) - 0.5)
    source *= 1.0 + float(rng.uniform(-0.045, 0.045)) * ((yy / max(1, size - 1)) - 0.5)
    if noise_sigma > 0:
        source += rng.normal(0.0, float(noise_sigma), size=source.shape)
    return SyntheticPhantom(
        truth_image=np.clip(truth, 0, 255).astype(np.uint8),
        input_image=np.clip(source, 0, 255).astype(np.uint8),
        regions=tuple(regions),
    )


def build_case_plan(
    *,
    seeds: Iterable[int],
    biases: Iterable[float],
    blur_sigmas: Iterable[float],
    noise_sigmas: Iterable[float],
) -> list[DiverseCase]:
    cases: list[DiverseCase] = []
    for seed in seeds:
        for bias in biases:
            for blur in blur_sigmas:
                for noise in noise_sigmas:
                    case_id = f"seed{int(seed)}_bias{float(bias):0.1f}_blur{float(blur):0.1f}_noise{float(noise):0.1f}"
                    case_id = case_id.replace(".", "p")
                    cases.append(DiverseCase(case_id, int(seed), float(bias), float(blur), float(noise)))
    return cases


def measure_case_rows(phantom: SyntheticPhantom, image: np.ndarray, *, image_label: str, case: DiverseCase) -> list[dict]:
    rows: list[dict] = []
    for region in phantom.regions:
        x0, y0, x1, y1 = _bbox_from_mask(region.truth_mask, pad=16)
        truth_roi = region.truth_mask[y0:y1, x0:x1]
        img_roi = image[y0:y1, x0:x1]
        pred_roi = _segment_roi(img_roi, region.polarity)
        true_area = float((truth_roi > 0).sum())
        pred_area = float((pred_roi > 0).sum())
        rows.append(
            {
                "case_id": case.case_id,
                "seed": case.seed,
                "bias_px": case.bias_px,
                "blur_sigma": case.blur_sigma,
                "noise_sigma": case.noise_sigma,
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


def _write_rows_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "case_id",
        "seed",
        "bias_px",
        "blur_sigma",
        "noise_sigma",
        "image",
        "region",
        "shape",
        "polarity",
        "chamfer_px",
        "area_error_px2",
        "abs_area_error_px2",
    ]
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _mean_chamfer(rows: list[dict], *, image: str | None = None) -> float | None:
    vals = []
    for row in rows:
        if image is not None and row.get("image") != image:
            continue
        val = float(row["chamfer_px"])
        if np.isfinite(val):
            vals.append(val)
    if not vals:
        return None
    return float(np.mean(vals))


def _run_command(command: list[str], *, log_path: Path) -> None:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("w", encoding="utf-8", errors="replace") as log:
        proc = subprocess.run(command, stdout=log, stderr=subprocess.STDOUT, text=True)
    if proc.returncode != 0:
        raise RuntimeError(f"command failed with code {proc.returncode}: {log_path}")


def _patch_infer_script_text(text: str, *, original_script_dir: Path) -> str:
    script_dir_line = f'SCRIPT_DIR = Path(r"{Path(original_script_dir)}")'
    replacements = {
        "SCRIPT_DIR = Path(__file__).resolve().parent": script_dir_line,
        'MANUAL_SELECT_MODE = "odd"': "MANUAL_SELECT_MODE = None",
        "MANUAL_SELECT_MODE = 'odd'": "MANUAL_SELECT_MODE = None",
    }
    patched = text
    for old, new in replacements.items():
        patched = patched.replace(old, new)
    if "MANUAL_SELECT_MODE = None" not in patched:
        raise RuntimeError("failed to disable MANUAL_SELECT_MODE in inference script copy")
    return patched


def _prepare_infer_script(run_dir: Path, *, source_script: Path = INFER_SCRIPT) -> Path:
    source_script = Path(source_script).resolve()
    runtime_dir = Path(run_dir) / "runtime"
    runtime_dir.mkdir(parents=True, exist_ok=True)
    patched_script = runtime_dir / source_script.name
    source_text = source_script.read_text(encoding="utf-8")
    patched_text = _patch_infer_script_text(source_text, original_script_dir=source_script.parent)
    patched_script.write_text(patched_text, encoding="utf-8")
    return patched_script


def _build_reconstruct_command(
    *,
    weights: Path,
    input_dir: Path,
    recon_root: Path,
    output_name: str,
    device: str,
    infer_script: Path = INFER_SCRIPT,
) -> list[str]:
    return [
        _python(),
        "-u",
        str(Path(infer_script)),
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
        "--select-mode",
        "all",
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


def _find_recon_output_dir(recon_root: Path, output_name: str) -> Path:
    candidates = [p for p in Path(recon_root).glob(f"*/{output_name}") if p.is_dir()]
    if candidates:
        return max(candidates, key=lambda p: p.stat().st_mtime)
    fallback = [p for p in Path(recon_root).rglob(output_name) if p.is_dir()]
    if fallback:
        return max(fallback, key=lambda p: p.stat().st_mtime)
    raise FileNotFoundError(f"no reconstruction output folder named {output_name} under {recon_root}")


def _write_case_manifest(path: Path, cases: list[DiverseCase]) -> None:
    payload = [case.__dict__ for case in cases]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def run_validation(args: argparse.Namespace) -> dict:
    stamp = time.strftime("%Y%m%d_%H%M%S")
    output_root = Path(args.output_root).resolve()
    run_dir = output_root / f"diverse_phantom_validation_{stamp}"
    input_dir = run_dir / "input"
    truth_dir = run_dir / "truth"
    input_dir.mkdir(parents=True, exist_ok=True)
    truth_dir.mkdir(parents=True, exist_ok=True)
    cases = build_case_plan(
        seeds=_parse_int_list(args.seeds),
        biases=_parse_float_list(args.biases),
        blur_sigmas=_parse_float_list(args.blur_sigmas),
        noise_sigmas=_parse_float_list(args.noise_sigmas),
    )
    case_manifest = run_dir / "case_manifest.json"
    _write_case_manifest(case_manifest, cases)

    phantoms: dict[str, SyntheticPhantom] = {}
    rows: list[dict] = []
    for case in cases:
        phantom = render_diverse_phantom(
            size=int(args.size),
            bias_px=case.bias_px,
            blur_sigma=case.blur_sigma,
            noise_sigma=case.noise_sigma,
            seed=case.seed,
        )
        phantoms[case.case_id] = phantom
        cv2.imwrite(str(input_dir / f"{case.case_id}.bmp"), phantom.input_image)
        cv2.imwrite(str(truth_dir / f"{case.case_id}.bmp"), phantom.truth_image)
        rows.extend(measure_case_rows(phantom, phantom.input_image, image_label="input_biased_blurred", case=case))

    recon_dir = None
    if not bool(args.skip_reconstruct):
        output_name = "diverse_phantom_recon"
        infer_script = _prepare_infer_script(run_dir)
        command = _build_reconstruct_command(
            weights=Path(args.weights).resolve(),
            input_dir=input_dir,
            recon_root=run_dir / "recon",
            output_name=output_name,
            device=str(args.device),
            infer_script=infer_script,
        )
        _run_command(command, log_path=run_dir / "logs" / "reconstruct.log")
        recon_dir = _find_recon_output_dir(run_dir / "recon", output_name)
        for case in cases:
            recon_path = recon_dir / f"{case.case_id}.bmp"
            recon = cv2.imread(str(recon_path), cv2.IMREAD_GRAYSCALE)
            if recon is None:
                raise RuntimeError(f"failed to read reconstructed image: {recon_path}")
            rows.extend(measure_case_rows(phantoms[case.case_id], recon, image_label="model_recon", case=case))

    metrics_csv = run_dir / "boundary_metrics.csv"
    _write_rows_csv(metrics_csv, rows)
    summary = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "weights": str(Path(args.weights).resolve()),
        "run_dir": str(run_dir),
        "case_count": len(cases),
        "case_manifest": str(case_manifest),
        "metrics_csv": str(metrics_csv),
        "input_dir": str(input_dir),
        "truth_dir": str(truth_dir),
        "recon_dir": str(recon_dir) if recon_dir is not None else "",
        "skip_reconstruct": bool(args.skip_reconstruct),
        "input_mean_chamfer_px": _mean_chamfer(rows, image="input_biased_blurred"),
        "recon_mean_chamfer_px": _mean_chamfer(rows, image="model_recon"),
        "size": int(args.size),
        "seeds": _parse_int_list(args.seeds),
        "biases": _parse_float_list(args.biases),
        "blur_sigmas": _parse_float_list(args.blur_sigmas),
        "noise_sigmas": _parse_float_list(args.noise_sigmas),
    }
    (run_dir / "summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    return summary


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run diverse synthetic phantom validation")
    parser.add_argument("--weights", type=Path, default=DEFAULT_WEIGHTS)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--device", default="cuda:0")
    parser.add_argument("--size", type=int, default=512)
    parser.add_argument("--seeds", default="7001,7002,7003")
    parser.add_argument("--biases", default="0.0,0.5,1.0,1.5,2.0,2.5")
    parser.add_argument("--blur-sigmas", default="0.9,1.35")
    parser.add_argument("--noise-sigmas", default="1.0,3.0")
    parser.add_argument("--skip-reconstruct", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    summary = run_validation(args)
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

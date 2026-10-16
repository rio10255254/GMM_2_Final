#!/usr/bin/env python
"""Validate the lab inner-circle PSF fit by forward-model reconstruction."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

import cv2
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.io import loadmat
from scipy.ndimage import binary_dilation, shift as ndi_shift
from scipy.signal import fftconvolve


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG_PATH = ROOT / "configs" / "inner_circle_roi_fine_prealign_20250608.json"
DEFAULT_OUTPUT_DIR = ROOT / "results" / "20250605_inner_circle_roi_fine_prealign_validation"
ACCEPTANCE_RULES = {
    "image_count": 25,
    "min_edge_improvement_vs_sharp_pct": 10.0,
    "max_global_gaussian_edge_gap_pct": 15.0,
    "max_psf_centroid_span_px": 2.0,
    "max_psf_mass_span_pct": 2.0,
}


def _resolve(path_text: str) -> Path:
    path = Path(path_text)
    if path.is_absolute():
        return path
    if path_text.startswith("LabSystem_MOSR/"):
        return ROOT.parents[1] / path_text
    return ROOT / path_text


def _resolve_cli_path(path_text: str) -> Path:
    path = Path(path_text)
    if path.is_absolute():
        return path
    if path_text.startswith("LabSystem_MOSR/"):
        return ROOT.parents[1] / path
    return ROOT / path


def _repo_rel(path: Path) -> str:
    resolved = path.resolve()
    thesis_root = ROOT.parents[1].resolve()
    try:
        return resolved.relative_to(thesis_root).as_posix()
    except ValueError:
        return resolved.as_posix()


def load_config(config_path: Path = DEFAULT_CONFIG_PATH) -> dict:
    return json.loads(config_path.read_text(encoding="utf-8"))


def load_gt(config: dict) -> np.ndarray:
    img = cv2.imread(str(_resolve(config["gt_path"])), cv2.IMREAD_GRAYSCALE)
    if img is None:
        raise FileNotFoundError(config["gt_path"])
    return img.astype(np.float64) / 255.0


def load_measurements(config: dict) -> list[tuple[str, np.ndarray]]:
    measured_dir = _resolve(config["measurement_input_dir"])
    files = sorted(measured_dir.glob("VisionTop_*.bmp"))
    if len(files) != ACCEPTANCE_RULES["image_count"]:
        raise ValueError(f"Expected 25 measured ROI images, found {len(files)}")
    images = []
    for path in files:
        img = cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)
        if img is None:
            raise FileNotFoundError(path)
        images.append((path.name, img.astype(np.float64) / 255.0))
    return images


def load_psf_grid(config: dict) -> np.ndarray:
    mat = loadmat(_resolve(config["psf_output"]))
    psf = np.asarray(mat["psf_grid"], dtype=np.float64)
    if psf.shape != (101, 101, 5, 5):
        raise ValueError(f"Unexpected psf_grid shape: {psf.shape}")
    return psf


def gaussian_kernel(size: int, sigma: float) -> np.ndarray:
    ax = np.arange(size) - (size - 1) / 2.0
    yy, xx = np.meshgrid(ax, ax)
    kernel = np.exp(-(xx**2 + yy**2) / (2.0 * sigma**2))
    return kernel / kernel.sum()


def convolve_same(img: np.ndarray, kernel: np.ndarray) -> np.ndarray:
    return fftconvolve(img, kernel, mode="same")


def build_masks(gt: np.ndarray, target_diameter_px: float) -> dict[str, np.ndarray]:
    h, w = gt.shape
    cy = (h - 1) / 2.0
    cx = (w - 1) / 2.0
    yy, xx = np.indices(gt.shape)
    rr = np.sqrt((xx - cx) ** 2 + (yy - cy) ** 2)
    radius = target_diameter_px / 2.0

    gt_u8 = (gt * 255).astype(np.uint8)
    edge = cv2.Canny(gt_u8, 40, 120) > 0
    edge = binary_dilation(edge, iterations=4)
    circle_edge = edge & (np.abs(rr - radius) <= 12)
    block_edge = edge & (rr < 190)
    eval_mask = rr <= radius + 65
    background = (rr >= radius + 18) & (rr <= radius + 60)

    return {
        "eval": eval_mask,
        "edge": edge & eval_mask,
        "circle_edge": circle_edge,
        "block_edge": block_edge,
        "background": background,
    }


def affine_fit(pred: np.ndarray, target: np.ndarray, mask: np.ndarray) -> np.ndarray:
    x = pred[mask].reshape(-1)
    y = target[mask].reshape(-1)
    a, b = np.linalg.lstsq(np.column_stack([x, np.ones_like(x)]), y, rcond=None)[0]
    return np.clip(a * pred + b, 0.0, 1.0)


def rmse(a: np.ndarray, b: np.ndarray, mask: np.ndarray) -> float:
    diff = a[mask] - b[mask]
    return float(np.sqrt(np.mean(diff**2)))


def grad_mag(img: np.ndarray) -> np.ndarray:
    gx = cv2.Sobel(img, cv2.CV_64F, 1, 0, ksize=3)
    gy = cv2.Sobel(img, cv2.CV_64F, 0, 1, ksize=3)
    mag = np.sqrt(gx**2 + gy**2)
    denom = np.percentile(mag, 99) + 1e-12
    return np.clip(mag / denom, 0.0, 1.0)


def best_shifted_fit(pred: np.ndarray, target: np.ndarray, masks: dict[str, np.ndarray]) -> tuple[np.ndarray, tuple[float, float]]:
    best_score = np.inf
    best_img = None
    best_shift = (0.0, 0.0)
    for dy in np.arange(-1.5, 1.51, 0.5):
        for dx in np.arange(-1.5, 1.51, 0.5):
            shifted = ndi_shift(pred, shift=(dy, dx), order=1, mode="nearest")
            fitted = affine_fit(shifted, target, masks["eval"])
            score = rmse(fitted, target, masks["edge"])
            if score < best_score:
                best_score = score
                best_img = fitted
                best_shift = (float(dy), float(dx))
    return best_img, best_shift


def metric_row(name: str, model: str, pred: np.ndarray, measured: np.ndarray, masks: dict[str, np.ndarray], shift: tuple[float, float]) -> dict:
    pred_grad = grad_mag(pred)
    measured_grad = grad_mag(measured)
    return {
        "filename": name,
        "model": model,
        "shift_y": shift[0],
        "shift_x": shift[1],
        "eval_rmse": rmse(pred, measured, masks["eval"]),
        "edge_rmse": rmse(pred, measured, masks["edge"]),
        "circle_edge_rmse": rmse(pred, measured, masks["circle_edge"]),
        "block_edge_rmse": rmse(pred, measured, masks["block_edge"]),
        "background_rmse": rmse(pred, measured, masks["background"]),
        "gradient_rmse": rmse(pred_grad, measured_grad, masks["eval"]),
    }


def choose_global_gaussian_sigma(gt: np.ndarray, measurements: list[tuple[str, np.ndarray]], masks: dict[str, np.ndarray]) -> tuple[float, dict[float, float]]:
    scores = {}
    for sigma in np.arange(1.0, 8.01, 0.5):
        pred = convolve_same(gt, gaussian_kernel(101, float(sigma)))
        image_scores = []
        for _, measured in measurements:
            fitted = affine_fit(pred, measured, masks["eval"])
            image_scores.append(rmse(fitted, measured, masks["edge"]))
        scores[float(sigma)] = float(np.median(image_scores))
    best_sigma = min(scores, key=scores.get)
    return best_sigma, scores


def psf_stats(psf_grid: np.ndarray) -> dict:
    masses = []
    cx_values = []
    cy_values = []
    sigma_eff = np.zeros((5, 5), dtype=np.float64)
    mass_map = np.zeros((5, 5), dtype=np.float64)
    for r in range(5):
        for c in range(5):
            psf = psf_grid[:, :, r, c]
            yy, xx = np.indices(psf.shape)
            mass = psf.sum()
            cx = float((xx * psf).sum() / mass)
            cy = float((yy * psf).sum() / mass)
            var = ((xx - cx) ** 2 * psf + (yy - cy) ** 2 * psf).sum() / (2.0 * mass)
            masses.append(float(mass))
            cx_values.append(cx)
            cy_values.append(cy)
            sigma_eff[r, c] = float(np.sqrt(max(var, 0.0)))
            mass_map[r, c] = float(mass)
    masses_arr = np.asarray(masses)
    return {
        "mass_min": float(masses_arr.min()),
        "mass_max": float(masses_arr.max()),
        "mass_span_pct": float((masses_arr.max() - masses_arr.min()) / masses_arr.mean() * 100.0),
        "center_x_span_px": float(max(cx_values) - min(cx_values)),
        "center_y_span_px": float(max(cy_values) - min(cy_values)),
        "centroid_span_px": float(max(max(cx_values) - min(cx_values), max(cy_values) - min(cy_values))),
        "sigma_eff_min": float(sigma_eff.min()),
        "sigma_eff_median": float(np.median(sigma_eff)),
        "sigma_eff_max": float(sigma_eff.max()),
        "sigma_eff_map": sigma_eff,
        "mass_map": mass_map,
    }


def write_comparison_contact(samples: list[dict], output_path: Path) -> None:
    chosen = [0, 6, 12, 18, 24]
    fig, axes = plt.subplots(len(chosen), 5, figsize=(12, 12))
    columns = ["measured", "bads", "bads_residual", "gaussian_residual", "sharp_residual"]
    for row_idx, sample_idx in enumerate(chosen):
        sample = samples[sample_idx]
        measured = sample["measured"]
        bads = sample["bads_fitted"]
        gaussian = sample["global_gaussian"]
        sharp = sample["sharp_gt"]
        images = [
            measured,
            bads,
            np.abs(measured - bads),
            np.abs(measured - gaussian),
            np.abs(measured - sharp),
        ]
        for col_idx, img in enumerate(images):
            ax = axes[row_idx, col_idx]
            ax.imshow(img, cmap="gray" if col_idx < 2 else "magma", vmin=0, vmax=1)
            ax.axis("off")
            if row_idx == 0:
                ax.set_title(columns[col_idx], fontsize=9)
            if col_idx == 0:
                ax.text(8, 28, f"{sample_idx + 1:02d}", color="red", fontsize=10, weight="bold")
    fig.tight_layout(pad=0.2)
    fig.savefig(output_path, dpi=160)
    plt.close(fig)


def write_psf_consistency_map(stats: dict, metrics_df: pd.DataFrame, output_path: Path) -> None:
    bads_edge = metrics_df[metrics_df["model"] == "bads_fitted"]["edge_rmse"].to_numpy().reshape(5, 5)
    fig, axes = plt.subplots(1, 3, figsize=(12, 4))
    panels = [
        (stats["sigma_eff_map"], "PSF width"),
        (stats["mass_map"], "PSF mass"),
        (bads_edge, "BADS edge RMSE"),
    ]
    for ax, (arr, title) in zip(axes, panels):
        im = ax.imshow(arr, cmap="viridis")
        ax.set_title(title)
        ax.set_xticks(range(5))
        ax.set_yticks(range(5))
        for r in range(5):
            for c in range(5):
                ax.text(c, r, f"{arr[r, c]:.3f}", ha="center", va="center", color="white", fontsize=7)
        fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
    fig.tight_layout()
    fig.savefig(output_path, dpi=160)
    plt.close(fig)


def update_config_with_validation(summary: dict, config_path: Path) -> None:
    config = load_config(config_path)
    config["validation"] = {
        "verdict": summary["verdict"],
        "summary": summary["artifacts"]["summary_json"],
        "report": summary["artifacts"]["report"],
        "next_action": summary["next_action"],
    }
    if summary["verdict"] == "validated":
        config["status"] = "validated_ready_for_lab_data_generation"
    else:
        config["status"] = "fit_complete_validation_needs_review"
    config_path.write_text(json.dumps(config, indent=2), encoding="utf-8")


def write_markdown_report(summary: dict, output_path: Path) -> None:
    lines = [
        "# Inner-Circle PSF Fit Validation",
        "",
        f"Verdict: `{summary['verdict']}`",
        f"Next action: `{summary['next_action']}`",
        "",
        "## Main Comparisons",
        "",
        f"- BADS vs sharp GT edge improvement: `{summary['bads_vs_sharp_edge_rmse_improvement_pct']:.2f}%`",
        f"- BADS vs global Gaussian edge gap: `{summary['bads_vs_gaussian_edge_rmse_gap_pct']:.2f}%`",
        f"- Best global Gaussian sigma: `{summary['best_global_gaussian_sigma_px']:.2f} px`",
        "",
        "## Median Edge RMSE",
        "",
        f"- Sharp GT: `{summary['median_edge_rmse']['sharp_gt']:.6f}`",
        f"- Global Gaussian: `{summary['median_edge_rmse']['global_gaussian']:.6f}`",
        f"- BADS fitted: `{summary['median_edge_rmse']['bads_fitted']:.6f}`",
        "",
        "## PSF Consistency",
        "",
        f"- Mass span: `{summary['psf_stats']['mass_span_pct']:.3f}%`",
        f"- Centroid span: `{summary['psf_stats']['centroid_span_px']:.3f} px`",
        f"- Median width: `{summary['psf_stats']['sigma_eff_median']:.3f} px`",
        "",
        "## Artifacts",
        "",
        f"- Metrics: `{summary['artifacts']['metrics_csv']}`",
        f"- Forward comparison: `{summary['artifacts']['comparison_contact']}`",
        f"- PSF consistency map: `{summary['artifacts']['psf_consistency_map']}`",
    ]
    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def validate(
    config_path: Path = DEFAULT_CONFIG_PATH,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    update_config: bool = True,
) -> dict:
    output_dir.mkdir(parents=True, exist_ok=True)
    config = load_config(config_path)
    gt = load_gt(config)
    measurements = load_measurements(config)
    psf_grid = load_psf_grid(config)
    masks = build_masks(gt, float(config["target_diameter_px"]))

    best_sigma, gaussian_scores = choose_global_gaussian_sigma(gt, measurements, masks)
    gaussian_pred = convolve_same(gt, gaussian_kernel(101, best_sigma))
    sharp_pred = gt.copy()

    rows = []
    samples = []
    for idx, (name, measured) in enumerate(measurements):
        r = idx // 5
        c = idx % 5
        bads_pred = convolve_same(gt, psf_grid[:, :, r, c])
        model_preds = {
            "sharp_gt": sharp_pred,
            "global_gaussian": gaussian_pred,
            "bads_fitted": bads_pred,
        }
        sample = {"filename": name, "measured": measured}
        for model, raw_pred in model_preds.items():
            fitted, model_shift = best_shifted_fit(raw_pred, measured, masks)
            rows.append(metric_row(name, model, fitted, measured, masks, model_shift))
            sample[model] = fitted
        samples.append(sample)

    metrics_df = pd.DataFrame(rows)
    metrics_csv = output_dir / "validation_metrics.csv"
    metrics_df.to_csv(metrics_csv, index=False)

    psf_consistency = psf_stats(psf_grid)
    comparison_contact = output_dir / "forward_model_comparison_contact.png"
    psf_consistency_map = output_dir / "psf_consistency_map.png"
    write_comparison_contact(samples, comparison_contact)
    write_psf_consistency_map(psf_consistency, metrics_df, psf_consistency_map)

    median_edge = {
        model: float(metrics_df[metrics_df["model"] == model]["edge_rmse"].median())
        for model in ["sharp_gt", "global_gaussian", "bads_fitted"]
    }
    improvement_vs_sharp = (median_edge["sharp_gt"] - median_edge["bads_fitted"]) / median_edge["sharp_gt"] * 100.0
    gap_vs_gaussian = (median_edge["bads_fitted"] - median_edge["global_gaussian"]) / median_edge["global_gaussian"] * 100.0

    rule_results = {
        "image_count": len(measurements) == ACCEPTANCE_RULES["image_count"],
        "edge_improvement_vs_sharp": improvement_vs_sharp >= ACCEPTANCE_RULES["min_edge_improvement_vs_sharp_pct"],
        "global_gaussian_competitive": gap_vs_gaussian <= ACCEPTANCE_RULES["max_global_gaussian_edge_gap_pct"],
        "psf_centroid_consistent": psf_consistency["centroid_span_px"] <= ACCEPTANCE_RULES["max_psf_centroid_span_px"],
        "psf_mass_consistent": psf_consistency["mass_span_pct"] <= ACCEPTANCE_RULES["max_psf_mass_span_pct"],
    }
    if not rule_results["image_count"] or not rule_results["edge_improvement_vs_sharp"]:
        verdict = "failed"
    elif all(rule_results.values()):
        verdict = "validated"
    else:
        verdict = "needs_review"

    next_action = (
        "advance_to_lab_data_generation_psf_ready"
        if verdict == "validated"
        else "inspect_validation_artifacts_before_training"
    )

    summary = {
        "run_id": output_dir.name,
        "validated_fit_run_id": config["run_id"],
        "verdict": verdict,
        "next_action": next_action,
        "acceptance_rules": ACCEPTANCE_RULES,
        "rule_results": rule_results,
        "image_count": len(measurements),
        "best_global_gaussian_sigma_px": float(best_sigma),
        "bads_vs_sharp_edge_rmse_improvement_pct": float(improvement_vs_sharp),
        "bads_vs_gaussian_edge_rmse_gap_pct": float(gap_vs_gaussian),
        "median_edge_rmse": median_edge,
        "median_eval_rmse": {
            model: float(metrics_df[metrics_df["model"] == model]["eval_rmse"].median())
            for model in ["sharp_gt", "global_gaussian", "bads_fitted"]
        },
        "median_circle_edge_rmse": {
            model: float(metrics_df[metrics_df["model"] == model]["circle_edge_rmse"].median())
            for model in ["sharp_gt", "global_gaussian", "bads_fitted"]
        },
        "median_block_edge_rmse": {
            model: float(metrics_df[metrics_df["model"] == model]["block_edge_rmse"].median())
            for model in ["sharp_gt", "global_gaussian", "bads_fitted"]
        },
        "psf_stats": {k: v for k, v in psf_consistency.items() if not isinstance(v, np.ndarray)},
        "gaussian_sigma_scores": gaussian_scores,
        "artifacts": {
            "summary_json": _repo_rel(output_dir / "validation_summary.json"),
            "metrics_csv": _repo_rel(metrics_csv),
            "comparison_contact": _repo_rel(comparison_contact),
            "psf_consistency_map": _repo_rel(psf_consistency_map),
            "report": _repo_rel(output_dir / "VALIDATION_REPORT.md"),
        },
    }
    summary_path = output_dir / "validation_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    write_markdown_report(summary, output_dir / "VALIDATION_REPORT.md")
    if update_config:
        update_config_with_validation(summary, config_path)
    return summary


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--config",
        default=str(DEFAULT_CONFIG_PATH),
        help="PSF fit config to validate. Relative paths are resolved from psf_calibration/.",
    )
    parser.add_argument(
        "--output-dir",
        default=str(DEFAULT_OUTPUT_DIR),
        help="Validation output directory. Relative paths are resolved from psf_calibration/.",
    )
    parser.add_argument(
        "--no-update-config",
        action="store_true",
        help="Write validation artifacts without updating the fit config JSON.",
    )
    return parser


def main() -> None:
    parser = build_arg_parser()
    args = parser.parse_args()
    summary = validate(
        config_path=_resolve_cli_path(args.config),
        output_dir=_resolve_cli_path(args.output_dir),
        update_config=not args.no_update_config,
    )
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()

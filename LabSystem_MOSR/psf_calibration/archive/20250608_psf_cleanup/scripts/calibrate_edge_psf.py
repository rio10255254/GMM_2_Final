#!/usr/bin/env python
"""Estimate a first-pass lab-system PSF from sharp calibration-target edges."""

from __future__ import annotations

import argparse
import csv
import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
from PIL import Image
from scipy.io import savemat
from scipy.ndimage import gaussian_filter1d


IMAGE_EXTENSIONS = (".bmp", ".png", ".jpg", ".jpeg", ".tif", ".tiff")


@dataclass(frozen=True)
class EdgeProfile:
    offsets: np.ndarray
    values: np.ndarray
    x: float
    y: float
    contrast: float
    gradient: float


def load_grayscale_image(path: Path) -> np.ndarray:
    image = Image.open(path).convert("L")
    arr = np.asarray(image, dtype=np.float64)
    if arr.max() > 1.0:
        arr /= 255.0
    return arr


def bilinear_sample(image: np.ndarray, xs: np.ndarray, ys: np.ndarray) -> np.ndarray:
    h, w = image.shape
    x0 = np.floor(xs).astype(np.int64)
    y0 = np.floor(ys).astype(np.int64)
    x1 = x0 + 1
    y1 = y0 + 1

    valid = (x0 >= 0) & (y0 >= 0) & (x1 < w) & (y1 < h)
    values = np.full(xs.shape, np.nan, dtype=np.float64)
    if not np.any(valid):
        return values

    xv = xs[valid]
    yv = ys[valid]
    x0v = x0[valid]
    y0v = y0[valid]
    x1v = x1[valid]
    y1v = y1[valid]

    dx = xv - x0v
    dy = yv - y0v
    top = image[y0v, x0v] * (1.0 - dx) + image[y0v, x1v] * dx
    bottom = image[y1v, x0v] * (1.0 - dx) + image[y1v, x1v] * dx
    values[valid] = top * (1.0 - dy) + bottom * dy
    return values


def estimate_sigma_from_edge_profile(offsets: np.ndarray, values: np.ndarray) -> dict[str, float]:
    offsets = np.asarray(offsets, dtype=np.float64)
    values = np.asarray(values, dtype=np.float64)
    finite = np.isfinite(offsets) & np.isfinite(values)
    offsets = offsets[finite]
    values = values[finite]
    if offsets.size < 9:
        return _invalid_sigma_result()

    smoothed = gaussian_filter1d(values, sigma=1.0, mode="nearest")
    lo = float(np.percentile(smoothed, 5))
    hi = float(np.percentile(smoothed, 95))
    if hi - lo <= 1e-6:
        return _invalid_sigma_result()
    smoothed = np.clip((smoothed - lo) / (hi - lo), 0.0, 1.0)

    deriv = np.gradient(smoothed, offsets)
    deriv = np.clip(deriv, 0.0, None)
    mass = float(deriv.sum())
    if mass <= 1e-8:
        return _invalid_sigma_result()

    center = float(np.sum(offsets * deriv) / mass)
    variance = float(np.sum(((offsets - center) ** 2) * deriv) / mass)
    sigma_deriv = math.sqrt(max(variance, 0.0))

    monotonic = np.maximum.accumulate(smoothed)
    span = float(monotonic[-1] - monotonic[0])
    sigma_1090 = float("nan")
    width_1090 = float("nan")
    if span > 1e-6:
        monotonic = (monotonic - monotonic[0]) / span
        unique, unique_idx = np.unique(monotonic, return_index=True)
        if unique.size >= 4 and unique[0] <= 0.1 and unique[-1] >= 0.9:
            sorted_idx = np.argsort(unique)
            unique = unique[sorted_idx]
            unique_offsets = offsets[unique_idx][sorted_idx]
            x10 = float(np.interp(0.1, unique, unique_offsets))
            x90 = float(np.interp(0.9, unique, unique_offsets))
            width_1090 = max(x90 - x10, 0.0)
            sigma_1090 = width_1090 / (2.0 * 1.2815515655446004)

    sigma_candidates = [sigma_deriv]
    if np.isfinite(sigma_1090) and sigma_1090 > 0:
        sigma_candidates.append(sigma_1090)
    sigma_px = float(np.median(sigma_candidates))

    return {
        "sigma_px": sigma_px,
        "fwhm_px": 2.354820045 * sigma_px,
        "center_offset_px": center,
        "width_10_90_px": width_1090,
    }


def _invalid_sigma_result() -> dict[str, float]:
    return {
        "sigma_px": float("nan"),
        "fwhm_px": float("nan"),
        "center_offset_px": float("nan"),
        "width_10_90_px": float("nan"),
    }


def sample_edge_profiles(
    image: np.ndarray,
    *,
    radius: int = 12,
    edge_percentile: float = 98.5,
    max_profiles: int = 700,
    random_seed: int = 0,
    min_contrast: float = 0.20,
) -> list[EdgeProfile]:
    gy, gx = np.gradient(image)
    mag = np.hypot(gx, gy)
    h, w = image.shape

    valid_margin = np.zeros_like(image, dtype=bool)
    valid_margin[radius + 2 : h - radius - 2, radius + 2 : w - radius - 2] = True
    valid_signal = (image > 0.03) & (image < 0.97)
    candidate_mask = valid_margin & valid_signal & np.isfinite(mag)
    if not np.any(candidate_mask):
        return []

    threshold = float(np.percentile(mag[candidate_mask], edge_percentile))
    candidate_mask &= mag >= threshold
    candidates = np.argwhere(candidate_mask)
    if candidates.size == 0:
        return []

    rng = np.random.default_rng(random_seed)
    order = rng.permutation(len(candidates))
    offsets = np.linspace(-float(radius), float(radius), radius * 4 + 1)
    profiles: list[EdgeProfile] = []

    for idx in order[: max_profiles * 30]:
        y, x = candidates[idx]
        gradient = float(mag[y, x])
        if gradient <= 1e-8:
            continue
        nx = float(gx[y, x] / gradient)
        ny = float(gy[y, x] / gradient)
        xs = x + nx * offsets
        ys = y + ny * offsets
        values = bilinear_sample(image, xs, ys)
        if np.any(~np.isfinite(values)):
            continue

        endpoint_n = max(3, len(values) // 8)
        left = float(np.median(values[:endpoint_n]))
        right = float(np.median(values[-endpoint_n:]))
        contrast = right - left
        if abs(contrast) < min_contrast:
            continue
        if contrast < 0:
            values = values[::-1]
            contrast = -contrast

        lo = float(np.median(values[:endpoint_n]))
        hi = float(np.median(values[-endpoint_n:]))
        if hi - lo < min_contrast:
            continue
        normalized = np.clip((values - lo) / (hi - lo), 0.0, 1.0)
        sigma = estimate_sigma_from_edge_profile(offsets, normalized)["sigma_px"]
        if not np.isfinite(sigma) or sigma <= 0.2 or sigma > radius:
            continue

        profiles.append(
            EdgeProfile(
                offsets=offsets.copy(),
                values=normalized,
                x=float(x),
                y=float(y),
                contrast=float(contrast),
                gradient=gradient,
            )
        )
        if len(profiles) >= max_profiles:
            break

    return profiles


def build_gaussian_psf_grid(sigma_grid: np.ndarray, *, kernel_size: int = 101) -> np.ndarray:
    if kernel_size % 2 != 1:
        raise ValueError("kernel_size must be odd")
    sigma_grid = np.asarray(sigma_grid, dtype=np.float64)
    yy, xx = np.mgrid[:kernel_size, :kernel_size]
    center = (kernel_size - 1) / 2.0
    rr2 = (xx - center) ** 2 + (yy - center) ** 2
    kernels = []
    for sigma in sigma_grid.reshape(-1):
        sigma = float(sigma)
        if not np.isfinite(sigma) or sigma <= 0:
            raise ValueError("sigma_grid contains invalid sigma values")
        kernel = np.exp(-0.5 * rr2 / (sigma * sigma))
        kernel /= kernel.sum()
        kernels.append(kernel)
    return np.stack(kernels, axis=-1)[:, :, np.newaxis, :]


def iter_image_files(input_dir: Path) -> Iterable[Path]:
    for path in sorted(input_dir.iterdir()):
        if path.suffix.lower() in IMAGE_EXTENSIONS:
            yield path


def calibrate_from_edges(
    input_dir: Path,
    output_dir: Path,
    *,
    grid_rows: int = 10,
    grid_cols: int = 10,
    kernel_size: int = 101,
    max_profiles_per_image: int = 700,
    radius: int = 12,
    edge_percentile: float = 98.5,
    random_seed: int = 42,
) -> dict:
    input_dir = Path(input_dir)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    image_files = list(iter_image_files(input_dir))
    if not image_files:
        raise FileNotFoundError(f"No calibration images found in {input_dir}")

    profile_rows = []
    image_rows = []
    first_shape: tuple[int, int] | None = None

    for image_index, path in enumerate(image_files):
        image = load_grayscale_image(path)
        if first_shape is None:
            first_shape = image.shape
        profiles = sample_edge_profiles(
            image,
            radius=radius,
            edge_percentile=edge_percentile,
            max_profiles=max_profiles_per_image,
            random_seed=random_seed + image_index,
        )
        image_sigmas = []
        for profile_index, profile in enumerate(profiles):
            estimate = estimate_sigma_from_edge_profile(profile.offsets, profile.values)
            sigma = estimate["sigma_px"]
            fwhm = estimate["fwhm_px"]
            if not np.isfinite(sigma):
                continue
            tile_col = min(grid_cols - 1, max(0, int(profile.x / image.shape[1] * grid_cols)))
            tile_row = min(grid_rows - 1, max(0, int(profile.y / image.shape[0] * grid_rows)))
            image_sigmas.append(sigma)
            profile_rows.append(
                {
                    "image": path.name,
                    "image_index": image_index,
                    "profile_index": profile_index,
                    "x": profile.x,
                    "y": profile.y,
                    "tile_row": tile_row,
                    "tile_col": tile_col,
                    "sigma_px": sigma,
                    "fwhm_px": fwhm,
                    "width_10_90_px": estimate["width_10_90_px"],
                    "contrast": profile.contrast,
                    "gradient": profile.gradient,
                }
            )
        image_rows.append(
            {
                "image": path.name,
                "profiles": len(image_sigmas),
                "median_sigma_px": float(np.median(image_sigmas)) if image_sigmas else float("nan"),
                "median_fwhm_px": float(2.354820045 * np.median(image_sigmas)) if image_sigmas else float("nan"),
            }
        )

    if not profile_rows:
        raise RuntimeError("No usable edge profiles were found")

    sigmas = np.array([row["sigma_px"] for row in profile_rows], dtype=np.float64)
    global_sigma = float(np.median(sigmas))
    sigma_grid = np.full((grid_rows, grid_cols), global_sigma, dtype=np.float64)
    tile_counts = np.zeros((grid_rows, grid_cols), dtype=np.int64)

    for row in range(grid_rows):
        for col in range(grid_cols):
            vals = [
                item["sigma_px"]
                for item in profile_rows
                if item["tile_row"] == row and item["tile_col"] == col
            ]
            tile_counts[row, col] = len(vals)
            if vals:
                sigma_grid[row, col] = float(np.median(vals))

    fwhm_grid = 2.354820045 * sigma_grid
    psf_grid = build_gaussian_psf_grid(sigma_grid, kernel_size=kernel_size)

    profile_csv = output_dir / "edge_profiles.csv"
    image_csv = output_dir / "image_summary.csv"
    tile_csv = output_dir / "tile_summary.csv"
    write_csv(profile_csv, profile_rows)
    write_csv(image_csv, image_rows)
    write_csv(
        tile_csv,
        [
            {
                "tile_row": r,
                "tile_col": c,
                "profiles": int(tile_counts[r, c]),
                "sigma_px": float(sigma_grid[r, c]),
                "fwhm_px": float(fwhm_grid[r, c]),
                "filled_from_global": bool(tile_counts[r, c] == 0),
            }
            for r in range(grid_rows)
            for c in range(grid_cols)
        ],
    )

    mat_path = output_dir / "lab_edge_gaussian_psf_10x10.mat"
    savemat(
        mat_path,
        {
            "psf_grid": psf_grid,
            "grid_rows": np.array([[grid_rows]], dtype=np.uint16),
            "grid_cols": np.array([[grid_cols]], dtype=np.uint16),
            "sigma_grid_px": sigma_grid,
            "fwhm_grid_px": fwhm_grid,
            "tile_profile_counts": tile_counts,
            "source_image_count": np.array([[len(image_files)]], dtype=np.uint16),
            "kernel_model": np.array(["edge_fit_isotropic_gaussian"], dtype=object),
        },
    )

    plot_sigma_heatmap(sigma_grid, tile_counts, output_dir / "sigma_heatmap.png")
    plot_fwhm_histogram(sigmas, output_dir / "sigma_histogram.png")
    plot_representative_profiles(profile_rows, image_files, input_dir, output_dir / "representative_edge_profiles.png")

    summary = {
        "input_dir": str(input_dir),
        "output_dir": str(output_dir),
        "image_count": len(image_files),
        "image_shape_hw": list(first_shape) if first_shape else None,
        "profile_count": len(profile_rows),
        "grid_rows": grid_rows,
        "grid_cols": grid_cols,
        "kernel_size": kernel_size,
        "global_median_sigma_px": global_sigma,
        "global_median_fwhm_px": 2.354820045 * global_sigma,
        "sigma_p10_px": float(np.percentile(sigmas, 10)),
        "sigma_p90_px": float(np.percentile(sigmas, 90)),
        "empty_tiles": int(np.sum(tile_counts == 0)),
        "psf_mat": str(mat_path),
        "notes": [
            "This is a first-pass edge-derived isotropic Gaussian PSF.",
            "It is suitable for calibration review and pipeline bring-up.",
            "Before final model training, compare against a richer PSF fit or validation target if available.",
        ],
    }
    (output_dir / "analysis_summary.json").write_text(
        json.dumps(summary, indent=2),
        encoding="utf-8",
    )
    write_report(output_dir / "PSF_CALIBRATION_REPORT.md", summary)
    return summary


def write_csv(path: Path, rows: list[dict]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def plot_sigma_heatmap(sigma_grid: np.ndarray, tile_counts: np.ndarray, path: Path) -> None:
    fig, ax = plt.subplots(figsize=(8, 6), constrained_layout=True)
    im = ax.imshow(sigma_grid, cmap="viridis")
    ax.set_title("Lab edge-derived PSF sigma by FOV tile")
    ax.set_xlabel("FOV tile column")
    ax.set_ylabel("FOV tile row")
    for r in range(sigma_grid.shape[0]):
        for c in range(sigma_grid.shape[1]):
            label = f"{sigma_grid[r, c]:.2f}\n(n={tile_counts[r, c]})"
            ax.text(c, r, label, ha="center", va="center", color="white", fontsize=6)
    fig.colorbar(im, ax=ax, label="sigma (px)")
    fig.savefig(path, dpi=180)
    plt.close(fig)


def plot_fwhm_histogram(sigmas: np.ndarray, path: Path) -> None:
    fig, ax = plt.subplots(figsize=(7, 4), constrained_layout=True)
    ax.hist(sigmas, bins=40, color="#4C78A8", edgecolor="white")
    ax.axvline(float(np.median(sigmas)), color="#F58518", linewidth=2, label="median")
    ax.set_title("Edge profile sigma distribution")
    ax.set_xlabel("sigma (px)")
    ax.set_ylabel("edge profiles")
    ax.legend()
    fig.savefig(path, dpi=180)
    plt.close(fig)


def plot_representative_profiles(
    profile_rows: list[dict],
    image_files: list[Path],
    input_dir: Path,
    path: Path,
) -> None:
    first_image = load_grayscale_image(input_dir / image_files[0].name)
    profiles = sample_edge_profiles(
        first_image,
        radius=12,
        edge_percentile=98.5,
        max_profiles=80,
        random_seed=123,
    )
    if not profiles:
        return

    offsets = profiles[0].offsets
    values = np.stack([p.values for p in profiles], axis=0)
    median = np.median(values, axis=0)
    p10 = np.percentile(values, 10, axis=0)
    p90 = np.percentile(values, 90, axis=0)

    fig, ax = plt.subplots(figsize=(7, 4), constrained_layout=True)
    for row in values[:30]:
        ax.plot(offsets, row, color="#999999", alpha=0.2, linewidth=0.8)
    ax.fill_between(offsets, p10, p90, color="#4C78A8", alpha=0.2, label="p10-p90")
    ax.plot(offsets, median, color="#1F4E79", linewidth=2, label="median")
    ax.set_title("Representative normalized edge-spread profiles")
    ax.set_xlabel("offset normal to edge (px)")
    ax.set_ylabel("normalized intensity")
    ax.legend()
    fig.savefig(path, dpi=180)
    plt.close(fig)


def write_report(path: Path, summary: dict) -> None:
    lines = [
        "# Lab System PSF Calibration Report",
        "",
        "## Scope",
        "",
        "This report is the first PSF calibration pass for the lab-system MOSR line.",
        "It uses sharp black-white calibration target edges to estimate an edge-derived",
        "isotropic Gaussian PSF across the field of view.",
        "",
        "## Results",
        "",
        f"- Source images: {summary['image_count']}",
        f"- Usable edge profiles: {summary['profile_count']}",
        f"- Median sigma: {summary['global_median_sigma_px']:.4f} px",
        f"- Median FWHM: {summary['global_median_fwhm_px']:.4f} px",
        f"- Sigma p10-p90: {summary['sigma_p10_px']:.4f} to {summary['sigma_p90_px']:.4f} px",
        f"- Empty FOV tiles filled from global median: {summary['empty_tiles']}",
        "",
        "## Generated Files",
        "",
        "- `lab_edge_gaussian_psf_10x10.mat`: MATLAB PSF package with `psf_grid`.",
        "- `sigma_heatmap.png`: FOV tile map of estimated blur width.",
        "- `sigma_histogram.png`: distribution of accepted edge-profile estimates.",
        "- `representative_edge_profiles.png`: sampled edge-spread profiles.",
        "- `edge_profiles.csv`, `tile_summary.csv`, `image_summary.csv`: detailed tables.",
        "",
        "## Interpretation",
        "",
        "This output is an initial lab-system PSF proxy, not yet the final training PSF.",
        "It is meant to establish the separated LabSystem_MOSR calibration flow and",
        "give a measurable first target for follow-up validation.",
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-dir", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--grid-rows", default=10, type=int)
    parser.add_argument("--grid-cols", default=10, type=int)
    parser.add_argument("--kernel-size", default=101, type=int)
    parser.add_argument("--max-profiles-per-image", default=700, type=int)
    parser.add_argument("--radius", default=12, type=int)
    parser.add_argument("--edge-percentile", default=98.5, type=float)
    parser.add_argument("--random-seed", default=42, type=int)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    summary = calibrate_from_edges(
        args.input_dir,
        args.output_dir,
        grid_rows=args.grid_rows,
        grid_cols=args.grid_cols,
        kernel_size=args.kernel_size,
        max_profiles_per_image=args.max_profiles_per_image,
        radius=args.radius,
        edge_percentile=args.edge_percentile,
        random_seed=args.random_seed,
    )
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()

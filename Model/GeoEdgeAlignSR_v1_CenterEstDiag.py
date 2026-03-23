"""
GeoEdgeAlignSR_v1_CenterEstDiag.py
===================================
Purpose
-------
Quantify the center-estimation inconsistency between the training-loss
geometry (`soft_centroid`) and the external GMF geometry (edge-based
fitting).

The core hypothesis is that the soft weighted centroid used inside the
training loss and the edge-fitting method used by the external GMF
produce systematically different annulus-center estimates at the
0.1 um / 0.8 px scale, causing GMF instability after reconstruction.
This script measures that gap directly on real image sequences.

Usage
-----
    python GeoEdgeAlignSR_v1_CenterEstDiag.py \\
        --input_dir  /path/to/sequences \\
        --expected_step_px 0.8 \\
        --top_edge_pct 0.15 \\
        --output_report center_diag_report.json

    # Flat directory with fixed-length sequences
    python GeoEdgeAlignSR_v1_CenterEstDiag.py \\
        --input_dir /path/to/flat_dir \\
        --seq_len 20 \\
        --output_report report.json

Input directory layouts supported
----------------------------------
1. Subdirectory layout: each `seq*` subdirectory is one sequence.
2. Flat layout: all images in one directory; chunk with ``--seq_len``,
   or treat the whole directory as a single sequence.

Output interpretation
---------------------
- ``std_step``          : lower is better; measures jitter in the
                          per-frame step estimate.
- ``mean_abs_err``      : mean |step - expected_step_px|; lower means
                          the method tracks the true motion more
                          accurately.
- ``neg_step_rate``     : fraction of frames where the direction is
                          wrong; should be near 0.
- ``center_consistency``: detrended std of center_y; residual jitter
                          after removing the linear motion trend.

A large discrepancy between ``soft_centroid`` and ``algebraic_fit``
in any of these metrics is a strong indicator that the geometry
mismatch is the root cause of GMF instability.
"""

import argparse
import glob
import json
import math
import os
from typing import Optional

import numpy as np

try:
    import cv2
except ImportError:
    cv2 = None  # type: ignore[assignment]


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
TOP_EDGE_PCT_DEFAULT: float = 0.15
SOBEL_KSIZE: int = 3
MIN_EDGELS_FOR_CIRCLE_FIT: int = 10
EDGE_WEIGHT_INTERIOR_ALPHA: float = 0.10


# ---------------------------------------------------------------------------
# Image loading
# ---------------------------------------------------------------------------

def _normalize_image(img: np.ndarray) -> np.ndarray:
    """Normalize an arbitrary integer or float array to float32 in [0, 1]."""
    arr = np.asarray(img)
    if arr.ndim == 3:
        arr = np.mean(arr[..., :3], axis=2)
    arr = arr.astype(np.float32, copy=False)
    if np.issubdtype(img.dtype, np.integer):
        max_value = float(np.iinfo(img.dtype).max)
        if max_value > 0.0:
            arr = arr / max_value
    else:
        max_value = float(np.max(arr)) if arr.size else 0.0
        if max_value > 1.0:
            arr = arr / max_value
    return np.clip(arr, 0.0, 1.0).astype(np.float32, copy=False)


def load_image(path: str) -> np.ndarray:
    """Load a grayscale image and normalize it to float32 in [0, 1].

    Tries cv2 first; falls back to PIL if cv2 is unavailable or fails.
    """
    if cv2 is not None:
        raw = cv2.imread(path, cv2.IMREAD_UNCHANGED)
        if raw is not None:
            return _normalize_image(raw)

    try:
        from PIL import Image  # type: ignore[import]
    except ImportError as exc:
        raise RuntimeError(
            f"Cannot load image '{path}': cv2 failed and PIL is not installed."
        ) from exc

    with Image.open(path) as pil_img:
        return _normalize_image(np.array(pil_img))


# ---------------------------------------------------------------------------
# Edge detection
# ---------------------------------------------------------------------------

def _conv3x3(img: np.ndarray, kernel: np.ndarray) -> np.ndarray:
    """Apply a 3x3 convolution with reflect padding (pure NumPy fallback)."""
    padded = np.pad(img.astype(np.float32), 1, mode="reflect")
    out = np.zeros_like(img, dtype=np.float32)
    h, w = img.shape
    for ky in range(3):
        for kx in range(3):
            out += kernel[ky, kx] * padded[ky : ky + h, kx : kx + w]
    return out


def compute_sobel_magnitude(img: np.ndarray) -> np.ndarray:
    """Compute 3x3 Sobel edge magnitude, normalized to [0, 1]."""
    if cv2 is not None:
        gx = cv2.Sobel(img, cv2.CV_32F, 1, 0, ksize=SOBEL_KSIZE)
        gy = cv2.Sobel(img, cv2.CV_32F, 0, 1, ksize=SOBEL_KSIZE)
    else:
        kx = np.array([[-1, 0, 1], [-2, 0, 2], [-1, 0, 1]], dtype=np.float32)
        ky = np.array([[-1, -2, -1], [0, 0, 0], [1, 2, 1]], dtype=np.float32)
        gx = _conv3x3(img, kx)
        gy = _conv3x3(img, ky)

    mag = np.sqrt(gx * gx + gy * gy).astype(np.float32, copy=False)
    mag_max = float(np.max(mag)) if mag.size else 0.0
    if mag_max > 0.0:
        mag = mag / mag_max
    return mag


# ---------------------------------------------------------------------------
# Shared centroid helper
# ---------------------------------------------------------------------------

def _weighted_centroid(weight_map: np.ndarray) -> tuple:
    """Return the weighted centroid of a 2D map as (center_y, center_x)."""
    w = np.asarray(weight_map, dtype=np.float64)
    total = float(np.sum(w))
    h, wid = w.shape
    if total <= 1e-12:
        return (h - 1) / 2.0, (wid - 1) / 2.0

    ys, xs = np.meshgrid(
        np.arange(h, dtype=np.float64),
        np.arange(wid, dtype=np.float64),
        indexing="ij",
    )
    cy = float(np.sum(ys * w) / total)
    cx = float(np.sum(xs * w) / total)
    return cy, cx


# ---------------------------------------------------------------------------
# Method 1: soft_centroid
# ---------------------------------------------------------------------------

def estimate_center_soft_centroid(
    img: np.ndarray, edge_mag: np.ndarray
) -> tuple:
    """Weighted centroid with edge magnitude plus weak interior weighting.

    Replicates the training-loss geometry:
        weight_map = edge_mag + ALPHA * |img|
    """
    weight_map = edge_mag + EDGE_WEIGHT_INTERIOR_ALPHA * np.abs(img)
    return _weighted_centroid(weight_map)


# ---------------------------------------------------------------------------
# Method 2: edge_centroid
# ---------------------------------------------------------------------------

def estimate_center_edge_centroid(edge_mag: np.ndarray) -> tuple:
    """Weighted centroid using edge magnitude only (no interior component)."""
    return _weighted_centroid(edge_mag)


# ---------------------------------------------------------------------------
# Method 3 helpers: edgel selection and circle fitting
# ---------------------------------------------------------------------------

def select_top_edgels(
    edge_mag: np.ndarray, top_pct: float
) -> tuple:
    """Return (ys, xs) coordinates of the strongest edge pixels.

    ``top_pct`` is the fraction to keep, e.g. 0.15 keeps the top 15%.
    """
    if edge_mag.size == 0:
        return np.array([], dtype=np.float64), np.array([], dtype=np.float64)

    top_pct = float(np.clip(top_pct, 1e-6, 1.0))
    threshold = float(np.percentile(edge_mag, (1.0 - top_pct) * 100.0))
    ys, xs = np.where(edge_mag >= threshold)
    return ys.astype(np.float64), xs.astype(np.float64)


def kasa_circle_fit(
    ys: np.ndarray, xs: np.ndarray
) -> Optional[tuple]:
    """Kasa algebraic least-squares circle fit.

    Solves  [2x, 2y, 1] * [cx, cy, c0]^T = x^2 + y^2  in the
    least-squares sense. Returns (cy, cx, radius) or None on failure.
    """
    if len(ys) < 3:
        return None

    x = xs.astype(np.float64, copy=False)
    y = ys.astype(np.float64, copy=False)
    a_mat = np.column_stack((2.0 * x, 2.0 * y, np.ones_like(x)))
    b_vec = x * x + y * y

    try:
        sol, _, _, _ = np.linalg.lstsq(a_mat, b_vec, rcond=None)
    except np.linalg.LinAlgError:
        return None

    cx_fit, cy_fit, c0 = (float(v) for v in sol)
    radius_sq = cx_fit * cx_fit + cy_fit * cy_fit + c0
    if not np.isfinite(radius_sq) or radius_sq <= 0.0:
        return None
    return cy_fit, cx_fit, math.sqrt(radius_sq)


def _circle_from_conic(
    a_coef: float, b_coef: float, c_coef: float, d_coef: float
) -> Optional[tuple]:
    """Convert conic coefficients A(x²+y²)+Bx+Cy+D=0 to (cy, cx, radius)."""
    if not np.isfinite(a_coef) or abs(a_coef) < 1e-12:
        return None

    cx = -b_coef / (2.0 * a_coef)
    cy = -c_coef / (2.0 * a_coef)
    radius_sq = (b_coef * b_coef + c_coef * c_coef - 4.0 * a_coef * d_coef) / (
        4.0 * a_coef * a_coef
    )
    if not np.isfinite(radius_sq) or radius_sq <= 0.0:
        return None
    return float(cy), float(cx), math.sqrt(radius_sq)


def taubin_circle_fit(
    ys: np.ndarray, xs: np.ndarray
) -> Optional[tuple]:
    """Taubin algebraic circle fit with curvature regularization.

    Solves the generalized eigenvalue problem M*v = lambda*B*v and
    returns (cy, cx, radius) for the smallest positive eigenvalue, or
    None if the fit fails.
    """
    if len(ys) < 3:
        return None

    x = xs.astype(np.float64, copy=False)
    y = ys.astype(np.float64, copy=False)
    z = x * x + y * y
    n = float(len(x))

    mx = float(np.sum(x))
    my = float(np.sum(y))
    mz = float(np.sum(z))
    mxx = float(np.sum(x * x))
    myy = float(np.sum(y * y))
    mxy = float(np.sum(x * y))
    mxz = float(np.sum(x * z))
    myz = float(np.sum(y * z))
    mzz = float(np.sum(z * z))

    m_mat = np.array(
        [
            [mzz, mxz, myz, mz],
            [mxz, mxx, mxy, mx],
            [myz, mxy, myy, my],
            [mz,  mx,  my,  n ],
        ],
        dtype=np.float64,
    )
    b_mat = np.array(
        [
            [8.0 * mz, 0.0, 0.0, 2.0 * n],
            [0.0,      1.0, 0.0, 0.0    ],
            [0.0,      0.0, 1.0, 0.0    ],
            [2.0 * n,  0.0, 0.0, 0.0    ],
        ],
        dtype=np.float64,
    )

    try:
        eigvals, eigvecs = np.linalg.eig(np.linalg.solve(b_mat, m_mat))
    except np.linalg.LinAlgError:
        return None

    candidates = []
    for idx, eigval in enumerate(eigvals):
        if abs(eigval.imag) > 1e-6 or eigval.real <= 0.0:
            continue
        vec = eigvecs[:, idx]
        if np.max(np.abs(vec.imag)) > 1e-6:
            continue
        circle = _circle_from_conic(*[float(v) for v in vec.real])
        if circle is not None:
            candidates.append((float(eigval.real), circle))

    if not candidates:
        return None
    candidates.sort(key=lambda item: item[0])
    return candidates[0][1]


# ---------------------------------------------------------------------------
# Method 3: algebraic_fit (entry point)
# ---------------------------------------------------------------------------

def estimate_center_algebraic_fit(
    img: np.ndarray, edge_mag: np.ndarray, top_pct: float
) -> tuple:
    """Estimate annulus center via algebraic circle fit over strong edgels.

    Falls back to edge_centroid if there are too few edgels or the fit
    is numerically degenerate.
    """
    _ = img  # reserved for future use (e.g., intensity-weighted edgels)
    if edge_mag.size == 0 or float(np.max(edge_mag)) <= 0.0:
        return estimate_center_edge_centroid(edge_mag)

    ys, xs = select_top_edgels(edge_mag, top_pct)
    if len(ys) < MIN_EDGELS_FOR_CIRCLE_FIT:
        return estimate_center_edge_centroid(edge_mag)

    fit = taubin_circle_fit(ys, xs)
    if fit is None:
        fit = kasa_circle_fit(ys, xs)
    if fit is None:
        return estimate_center_edge_centroid(edge_mag)

    cy, cx, _radius = fit
    return cy, cx


# ---------------------------------------------------------------------------
# Statistics helpers
# ---------------------------------------------------------------------------

def compute_step_series(centers_y: list) -> np.ndarray:
    """Return per-frame y-axis motion increments (np.diff)."""
    if len(centers_y) < 2:
        return np.array([], dtype=np.float64)
    return np.diff(np.asarray(centers_y, dtype=np.float64))


def detrended_std(values: list) -> float:
    """Compute std of residuals after removing a linear trend."""
    if len(values) < 2:
        return 0.0
    y = np.asarray(values, dtype=np.float64)
    x = np.arange(len(y), dtype=np.float64)
    slope, intercept = np.polyfit(x, y, 1)
    residuals = y - (slope * x + intercept)
    return float(np.std(residuals))


def compute_method_stats(centers_y: list, expected_step_px: float) -> dict:
    """Compute motion-quality statistics for one center-estimation method.

    Keys returned:
        mean_step, std_step, mean_abs_err, neg_step_rate, center_consistency
    """
    steps = compute_step_series(centers_y)
    expected_sign = (
        0.0 if abs(expected_step_px) < 1e-12
        else math.copysign(1.0, expected_step_px)
    )

    if steps.size:
        mean_step = float(np.mean(steps))
        std_step = float(np.std(steps))
        mean_abs_err = float(np.mean(np.abs(steps - expected_step_px)))
        neg_step_rate = float(np.mean(np.sign(steps) != expected_sign))
    else:
        mean_step = std_step = mean_abs_err = neg_step_rate = 0.0

    return {
        "mean_step": mean_step,
        "std_step": std_step,
        "mean_abs_err": mean_abs_err,
        "neg_step_rate": neg_step_rate,
        "center_consistency": detrended_std(centers_y),
    }


# ---------------------------------------------------------------------------
# Sequence processing
# ---------------------------------------------------------------------------

def process_sequence(
    image_paths: list,
    expected_step_px: float,
    top_edge_pct: float,
) -> dict:
    """Process one image sequence and compare all three center estimators.

    Returns a dict with keys ``frames`` (per-frame raw data) and
    ``stats`` (per-method statistics).
    """
    tracks: dict = {
        "soft_centroid": {"y": [], "x": []},
        "edge_centroid": {"y": [], "x": []},
        "algebraic_fit": {"y": [], "x": []},
    }
    frames = []

    for frame_idx, path in enumerate(image_paths):
        img = load_image(path)
        edge_mag = compute_sobel_magnitude(img)

        soft_y, soft_x = estimate_center_soft_centroid(img, edge_mag)
        edge_y, edge_x = estimate_center_edge_centroid(edge_mag)
        alg_y, alg_x = estimate_center_algebraic_fit(img, edge_mag, top_edge_pct)

        for method, (cy, cx) in [
            ("soft_centroid", (soft_y, soft_x)),
            ("edge_centroid", (edge_y, edge_x)),
            ("algebraic_fit", (alg_y, alg_x)),
        ]:
            tracks[method]["y"].append(cy)
            tracks[method]["x"].append(cx)

        frames.append(
            {
                "frame_index": frame_idx,
                "path": os.path.abspath(path),
                "soft_centroid": {"center_y": float(soft_y), "center_x": float(soft_x)},
                "edge_centroid": {"center_y": float(edge_y), "center_x": float(edge_x)},
                "algebraic_fit": {"center_y": float(alg_y), "center_x": float(alg_x)},
            }
        )

    stats = {
        method: compute_method_stats(track["y"], expected_step_px)
        for method, track in tracks.items()
    }
    return {"frames": frames, "stats": stats}


# ---------------------------------------------------------------------------
# Sequence discovery
# ---------------------------------------------------------------------------

def _collect_image_paths(directory: str) -> list:
    """Collect sorted absolute paths of tif/png images in one directory."""
    patterns = ["*.tif", "*.tiff", "*.png", "*.bmp"]
    paths: list = []
    for pattern in patterns:
        paths.extend(glob.glob(os.path.join(directory, pattern)))
    return [os.path.abspath(p) for p in sorted(paths)]


def discover_sequences(input_dir: str, seq_len: Optional[int]) -> list:
    """Return a list of sequences, each sequence being a list of image paths.

    Checks for ``seq*`` subdirectories first; otherwise uses the flat
    directory, optionally chunked by ``seq_len``.
    """
    abs_dir = os.path.abspath(input_dir)
    seq_dirs = sorted(
        p for p in glob.glob(os.path.join(abs_dir, "seq*")) if os.path.isdir(p)
    )
    if seq_dirs:
        return [paths for d in seq_dirs for paths in [_collect_image_paths(d)] if paths]

    all_paths = _collect_image_paths(abs_dir)
    if not all_paths:
        return []
    if seq_len is None or seq_len <= 0:
        return [all_paths]
    return [all_paths[i : i + seq_len] for i in range(0, len(all_paths), seq_len)]


# ---------------------------------------------------------------------------
# Reporting helpers
# ---------------------------------------------------------------------------

def _aggregate_method_comparison(sequence_results: list) -> dict:
    """Average per-method statistics across all processed sequences."""
    methods = ["soft_centroid", "edge_centroid", "algebraic_fit"]
    metrics = ["mean_step", "std_step", "mean_abs_err", "neg_step_rate", "center_consistency"]
    comparison: dict = {}

    for method in methods:
        comparison[method] = {}
        for metric in metrics:
            values = [
                seq["stats"][method][metric]
                for seq in sequence_results
                if method in seq.get("stats", {})
            ]
            comparison[method][metric] = float(np.mean(values)) if values else 0.0

    return comparison


def _print_summary(method_comparison: dict) -> None:
    """Print a formatted summary table to stdout."""
    col = [18, 12, 12, 15, 16]
    header = (
        f"{'method':<{col[0]}}"
        f"{'mean_step':>{col[1]}}"
        f"{'std_step':>{col[2]}}"
        f"{'mean_abs_err':>{col[3]}}"
        f"{'neg_step_rate':>{col[4]}}"
    )
    print("\n" + header)
    print("-" * len(header))
    for method in ["soft_centroid", "edge_centroid", "algebraic_fit"]:
        s = method_comparison.get(method, {})
        print(
            f"{method:<{col[0]}}"
            f"{s.get('mean_step', 0.0):>{col[1]}.4f}"
            f"{s.get('std_step', 0.0):>{col[2]}.4f}"
            f"{s.get('mean_abs_err', 0.0):>{col[3]}.4f}"
            f"{s.get('neg_step_rate', 0.0):>{col[4]}.4f}"
        )
    print()


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main() -> None:
    """Parse arguments, process all sequences, and write the JSON report."""
    parser = argparse.ArgumentParser(
        description="Diagnose annulus center-estimation inconsistency (GMF alignment).",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--input_dir",
        required=True,
        help="Directory containing images or seq* subdirectories.",
    )
    parser.add_argument(
        "--expected_step_px",
        type=float,
        default=0.8,
        help="Expected per-frame y-displacement in pixels.",
    )
    parser.add_argument(
        "--top_edge_pct",
        type=float,
        default=TOP_EDGE_PCT_DEFAULT,
        help="Fraction of strongest edge pixels used for circle fitting.",
    )
    parser.add_argument(
        "--output_report",
        default="center_diag_report.json",
        help="Output path for the JSON diagnostic report.",
    )
    parser.add_argument(
        "--seq_len",
        type=int,
        default=None,
        help="Chunk size for flat directories (omit to use whole dir as one sequence).",
    )
    args = parser.parse_args()

    if not (0.0 < args.top_edge_pct <= 1.0):
        parser.error("--top_edge_pct must be in the range (0, 1].")

    sequences = discover_sequences(args.input_dir, args.seq_len)
    if not sequences:
        raise FileNotFoundError(
            f"No .tif/.tiff/.png/.bmp images found in: {os.path.abspath(args.input_dir)}"
        )

    print(f"Found {len(sequences)} sequence(s). Processing...")
    sequence_results = []
    for seq_idx, image_paths in enumerate(sequences):
        print(f"  Sequence {seq_idx}: {len(image_paths)} frames")
        result = process_sequence(image_paths, args.expected_step_px, args.top_edge_pct)
        sequence_results.append(
            {
                "sequence_index": seq_idx,
                "num_frames": len(image_paths),
                "image_paths": image_paths,
                "frames": result["frames"],
                "stats": result["stats"],
            }
        )

    method_comparison = _aggregate_method_comparison(sequence_results)
    report = {
        "input_dir": os.path.abspath(args.input_dir),
        "expected_step_px": float(args.expected_step_px),
        "top_edge_pct": float(args.top_edge_pct),
        "num_sequences": len(sequence_results),
        "method_comparison": method_comparison,
        "sequences": sequence_results,
    }

    output_path = os.path.abspath(args.output_report)
    with open(output_path, "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=2)

    print(f"Report written to: {output_path}")
    _print_summary(method_comparison)


if __name__ == "__main__":
    main()

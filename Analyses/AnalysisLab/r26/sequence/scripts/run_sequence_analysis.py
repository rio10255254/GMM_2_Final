"""
GeoEdge R26 Multi-Frame Sequence Analysis
==========================================
Analyzes frame-to-frame geometric stability across three pitch-step
sequences, answering the five open questions from the single-image report.
"""
from __future__ import annotations

import importlib.util
import json
import platform
import re
import sys
import time
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from scipy import stats as sp_stats

# ---------------------------------------------------------------------------
# Import reusable functions from single-image analysis
# ---------------------------------------------------------------------------
_SINGLE_IMAGE_SCRIPT = (
    Path(__file__).resolve().parents[2]
    / "single_image"
    / "scripts"
    / "run_single_image_analysis.py"
)
_spec = importlib.util.spec_from_file_location("single_image_analysis", _SINGLE_IMAGE_SCRIPT)
_sia = importlib.util.module_from_spec(_spec)
assert _spec is not None and _spec.loader is not None
_spec.loader.exec_module(_sia)

load_image = _sia.load_image
detect_annulus_reference = _sia.detect_annulus_reference
refine_annulus_reference = _sia.refine_annulus_reference
extract_radial_edge_candidates = _sia.extract_radial_edge_candidates
summarize_circle_fits = _sia.summarize_circle_fits
compute_residual_harmonics = _sia.compute_residual_harmonics
compute_hotspot_clusters = _sia.compute_hotspot_clusters
measure_edge_width = _sia.measure_edge_width

def _collect_env_versions() -> dict:
    """Return pinned dependency versions for reproducibility tracking."""
    versions: dict[str, str] = {"python": platform.python_version()}
    for pkg in ("numpy", "scipy", "matplotlib", "cv2"):
        try:
            mod = importlib.import_module(pkg)
            versions[pkg.replace("cv2", "opencv")] = getattr(mod, "__version__", "unknown")
        except ImportError:
            versions[pkg.replace("cv2", "opencv")] = "not_installed"
    return versions


# Local config
ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR / "configs"))
from dataset_config import DATASETS, DatasetConfig

RESULTS_ROOT = ROOT_DIR / "results"

# Style constants (match single-image analysis)
CLR_INPUT = "steelblue"
CLR_OUTPUT = "crimson"

# ---------------------------------------------------------------------------
# GMF score file parser
# ---------------------------------------------------------------------------

def parse_gmf_score(path: Path) -> list[dict]:
    """Parse external GMF_score.txt into a list of per-frame dicts."""
    rows: list[dict] = []
    if not path.exists():
        return rows
    text = path.read_text(encoding="utf-8", errors="replace")
    for line in text.strip().splitlines():
        parts = [p.strip() for p in line.split(",")]
        if len(parts) < 12 or parts[0] != "FileName":
            continue
        rows.append({
            "filename": parts[1].strip(),
            "posx": float(parts[5]),
            "posy": float(parts[7]),
            "scale": float(parts[9]),
            "score": float(parts[11]),
        })
    return rows


# ---------------------------------------------------------------------------
# Per-frame analysis
# ---------------------------------------------------------------------------

def analyze_frame(
    img: np.ndarray,
    *,
    ref_hint: dict | None = None,
) -> dict:
    """Run full geometric analysis on a single frame.

    Returns ~35 scalar metrics + residual signal arrays.
    """
    # Annulus detection (with optional hint from previous frame)
    if ref_hint is not None:
        ref = refine_annulus_reference(img, ref_hint)
        ref["method"] = "prev_frame_hint+local_refine"
        ref["warnings"] = list(ref.get("warnings", []))
        if ref["status"] == "failed":
            ref = detect_annulus_reference(img)
    else:
        ref = detect_annulus_reference(img)

    result: dict = {
        "annulus_cx": float(ref["cx"]),
        "annulus_cy": float(ref["cy"]),
        "annulus_r_inner": float(ref["r_inner"]),
        "annulus_r_outer": float(ref["r_outer"]),
        "annulus_status": ref["status"],
    }

    # Edge extraction + circle fit (720 angles for lower circle-fit noise floor)
    edge_data = extract_radial_edge_candidates(
        img, ref["cx"], ref["cy"], ref["r_inner"], ref["r_outer"],
        n_angles=720,
    )
    fits = summarize_circle_fits(edge_data, ref["cx"], ref["cy"])

    result["center_offset_px"] = float(fits["center_offset_px"])

    for boundary in ("outer", "inner"):
        fb = fits[boundary]
        prefix = f"{boundary}_"
        result[prefix + "fit_cx"] = float(fb["center"][0])
        result[prefix + "fit_cy"] = float(fb["center"][1])
        result[prefix + "fit_r"] = float(fb["radius"])
        result[prefix + "residual_std"] = float(fb["residual_std_px"])
        result[prefix + "residual_max"] = float(fb["residual_max_px"])
        result[prefix + "coverage"] = float(fb["coverage_ratio"])
        result[prefix + "status"] = fb["status"]

        # Harmonic decomposition
        hdata = compute_residual_harmonics(fb)
        result[prefix + "dominant_k"] = hdata["dominant_k"]
        result[prefix + "lo_energy_pct"] = hdata["energy_split"]["lo_pct"]
        result[prefix + "hi_energy_pct"] = hdata["energy_split"]["hi_pct"]

        # Extract k=2 amplitude and phase specifically
        if len(hdata["amplitudes"]) > 2:
            result[prefix + "k2_amplitude"] = float(hdata["amplitudes"][2])
            result[prefix + "k2_phase_deg"] = float(hdata["phases_deg"][2])
        else:
            result[prefix + "k2_amplitude"] = 0.0
            result[prefix + "k2_phase_deg"] = 0.0

        # Hotspot clusters
        cl = compute_hotspot_clusters(fb)
        result[prefix + "n_clusters"] = cl["n_clusters"]
        result[prefix + "total_arc_deg"] = cl["total_arc_deg"]
        result[prefix + "max_cluster_deg"] = cl["max_cluster_deg"]

        # Store 360-point residual signal for hotspot persistence heatmap
        residuals_360 = np.full(360, np.nan)
        angles_deg = np.asarray(fb.get("angles_deg", []), dtype=np.float64)
        residuals = np.asarray(fb.get("residuals", []), dtype=np.float64)
        for theta, res in zip(angles_deg, residuals):
            idx = int(round(theta)) % 360
            residuals_360[idx] = res
        result[prefix + "residual_signal"] = residuals_360.tolist()

    # Edge width (outer only for speed — inner is similar)
    w_out, _ = measure_edge_width(img, ref["cx"], ref["cy"], ref["r_outer"])
    w_in, _ = measure_edge_width(img, ref["cx"], ref["cy"], ref["r_inner"])
    result["outer_edge_width_mean"] = float(np.nanmean(w_out)) if len(w_out) > 0 else float("nan")
    result["inner_edge_width_mean"] = float(np.nanmean(w_in)) if len(w_in) > 0 else float("nan")

    return result


# ---------------------------------------------------------------------------
# Image pairing
# ---------------------------------------------------------------------------

def match_input_recon_pairs(config: DatasetConfig) -> list[tuple[Path, Path]]:
    """Match input and recon images by filename. Returns sorted pairs."""
    recon_files = {p.name: p for p in sorted(config.recon_dir.glob("*.bmp"))}
    input_files = {p.name: p for p in sorted(config.input_dir.glob("*.bmp"))}
    common = sorted(set(recon_files) & set(input_files))
    return [(input_files[name], recon_files[name]) for name in common]


# ---------------------------------------------------------------------------
# Sequence processing
# ---------------------------------------------------------------------------

def process_sequence(
    image_paths: list[Path],
    *,
    label: str = "input",
    log=print,
) -> list[dict]:
    """Process all frames in order, returning per-frame metrics."""
    metrics: list[dict] = []
    prev_ref: dict | None = None
    n = len(image_paths)

    for i, path in enumerate(image_paths):
        t0 = time.time()
        img = load_image(str(path))
        m = analyze_frame(img, ref_hint=prev_ref)
        m["frame_index"] = i
        m["filename"] = path.name
        del img

        # Build hint for next frame
        prev_ref = {
            "cx": m["annulus_cx"],
            "cy": m["annulus_cy"],
            "r_inner": m["annulus_r_inner"],
            "r_outer": m["annulus_r_outer"],
        }
        metrics.append(m)
        elapsed = time.time() - t0
        if (i + 1) % 10 == 0 or i == 0 or i == n - 1:
            log(f"  [{label}] frame {i+1}/{n}  ({elapsed:.1f}s)  "
                f"cx={m['annulus_cx']:.1f} cy={m['annulus_cy']:.1f} "
                f"outer_std={m['outer_residual_std']:.3f}")

    return metrics


# ---------------------------------------------------------------------------
# Circular statistics for phase stability
# ---------------------------------------------------------------------------

def circular_std_deg(angles_deg: list[float]) -> float:
    """Compute circular standard deviation in degrees."""
    if len(angles_deg) < 2:
        return 0.0
    rads = np.deg2rad(angles_deg)
    R = np.abs(np.mean(np.exp(1j * rads)))
    R = min(R, 1.0)
    return float(np.degrees(np.sqrt(-2.0 * np.log(R))))


def unwrap_phase_for_plot(angles_deg: np.ndarray | list[float]) -> np.ndarray:
    """Unwrap phase angles so plots do not jump at the +/-180 degree boundary."""
    angles = np.asarray(angles_deg, dtype=np.float64)
    if angles.size == 0:
        return angles.copy()
    return np.rad2deg(np.unwrap(np.deg2rad(angles)))


def phase_deviation_for_plot(angles_deg: np.ndarray | list[float]) -> np.ndarray:
    """Express phase relative to its circular mean for a readable stability plot."""
    angles = np.asarray(angles_deg, dtype=np.float64)
    if angles.size == 0:
        return angles.copy()
    mean_vec = np.mean(np.exp(1j * np.deg2rad(angles)))
    mean_angle = np.rad2deg(np.angle(mean_vec))
    return (angles - mean_angle + 180.0) % 360.0 - 180.0


def compute_hotspot_persistence(
    signals: np.ndarray,
    *,
    hot_percentile: float = 90.0,
    persistence_cutoff: float = 0.5,
) -> dict:
    """Measure how often strong residual hotspots recur at the same angles."""
    arr = np.asarray(signals, dtype=np.float64)
    if arr.ndim != 2:
        raise ValueError("signals must be a 2D array shaped [frame, angle]")
    if arr.shape[1] == 0:
        raise ValueError("signals must include at least one angle column")

    abs_arr = np.abs(arr)
    valid_mask = np.isfinite(abs_arr)
    valid_values = abs_arr[valid_mask]

    if valid_values.size == 0:
        empty_profile = np.zeros(arr.shape[1], dtype=np.float64)
        return {
            "threshold_px": 0.0,
            "hot_mask": np.zeros_like(arr, dtype=bool),
            "persistence": empty_profile,
            "mean_persistence": 0.0,
            "max_persistence": 0.0,
            "n_persistent_angles_gt50pct": 0,
            "persistent_angle_fraction_gt50pct": 0.0,
        }

    threshold = float(np.nanpercentile(valid_values, hot_percentile))
    hot_mask = valid_mask & (abs_arr > threshold)
    valid_counts = np.sum(valid_mask, axis=0)
    hot_counts = np.sum(hot_mask, axis=0)

    persistence = np.divide(
        hot_counts,
        valid_counts,
        out=np.zeros(arr.shape[1], dtype=np.float64),
        where=valid_counts > 0,
    )
    active_mask = hot_counts > 0
    mean_persistence = float(np.mean(persistence[active_mask])) if np.any(active_mask) else 0.0
    max_persistence = float(np.max(persistence)) if persistence.size else 0.0
    n_persistent = int(np.sum(persistence > persistence_cutoff))
    persistent_fraction = float(n_persistent / max(int(np.sum(valid_counts > 0)), 1))

    return {
        "threshold_px": threshold,
        "hot_mask": hot_mask,
        "persistence": persistence,
        "mean_persistence": mean_persistence,
        "max_persistence": max_persistence,
        "n_persistent_angles_gt50pct": n_persistent,
        "persistent_angle_fraction_gt50pct": persistent_fraction,
    }


# ---------------------------------------------------------------------------
# Sequence summary computation
# ---------------------------------------------------------------------------

def compute_sequence_summary(
    inp_metrics: list[dict],
    out_metrics: list[dict],
    config: DatasetConfig,
) -> dict:
    """Compute the five core answers + supporting statistics."""
    n = len(inp_metrics)

    def _extract(metrics, key):
        return np.array([m[key] for m in metrics], dtype=np.float64)

    # ---- Q1: Step stability ----
    step_data: dict = {}
    for label, metrics in [("input", inp_metrics), ("output", out_metrics)]:
        cy = _extract(metrics, "outer_fit_cy")
        cx = _extract(metrics, "outer_fit_cx")
        steps_y = np.diff(cy)
        steps_x = np.diff(cx)
        step_data[label] = {
            "step_y_mean": round(float(np.mean(steps_y)), 4),
            "step_y_std": round(float(np.std(steps_y)), 4),
            "step_y_cv_pct": round(float(np.std(steps_y) / max(abs(np.mean(steps_y)), 1e-6) * 100), 2),
            "step_x_mean": round(float(np.mean(steps_x)), 4),
            "step_x_std": round(float(np.std(steps_x)), 4),
            "internal_step_std_y": round(float(np.std(steps_y)), 4),
        }
    if step_data["input"]["internal_step_std_y"] > 0:
        step_improvement = round(
            (1 - step_data["output"]["internal_step_std_y"]
             / step_data["input"]["internal_step_std_y"]) * 100, 2
        )
    else:
        step_improvement = 0.0

    # GMF cross-validation (if available)
    gmf_step_std = None
    if config.gmf_score_path and config.gmf_score_path.exists():
        gmf_rows = parse_gmf_score(config.gmf_score_path)
        if len(gmf_rows) >= 2:
            gmf_posy = np.array([r["posy"] for r in gmf_rows])
            gmf_steps = np.diff(gmf_posy)
            gmf_step_std = round(float(np.std(gmf_steps)), 6)

    # ---- Q2: k=2 stability ----
    k2_data: dict = {}
    for label, metrics in [("input", inp_metrics), ("output", out_metrics)]:
        for boundary in ("outer", "inner"):
            key = f"{label}_{boundary}"
            amps = _extract(metrics, f"{boundary}_k2_amplitude")
            phases = [m[f"{boundary}_k2_phase_deg"] for m in metrics]
            mean_amp = float(np.mean(amps))
            k2_data[key] = {
                "k2_amp_mean": round(mean_amp, 4),
                "k2_amp_std": round(float(np.std(amps)), 4),
                "k2_amp_cv_pct": round(float(np.std(amps) / max(mean_amp, 1e-6) * 100), 2),
                "k2_phase_circ_std_deg": round(circular_std_deg(phases), 2),
            }

    # Verdict: inner boundary output is the one we care about most
    out_inner_cv = k2_data["output_inner"]["k2_amp_cv_pct"]
    if out_inner_cv < 15:
        k2_verdict = "stable_offset"
    elif out_inner_cv < 30:
        k2_verdict = "moderate"
    else:
        k2_verdict = "volatile_risk"

    # ---- Q3: Center offset drift ----
    offset_data: dict = {}
    for label, metrics in [("input", inp_metrics), ("output", out_metrics)]:
        offsets = _extract(metrics, "center_offset_px")
        if len(offsets) >= 3:
            slope = float(sp_stats.linregress(range(len(offsets)), offsets).slope)
        else:
            slope = 0.0
        offset_data[label] = {
            "mean": round(float(np.mean(offsets)), 4),
            "std": round(float(np.std(offsets)), 4),
            "trend_px_per_frame": round(slope, 6),
        }
    out_offset_std = offset_data["output"]["std"]
    out_offset_mean = offset_data["output"]["mean"]
    if out_offset_std < 0.3 * max(out_offset_mean, 0.01) and abs(offset_data["output"]["trend_px_per_frame"]) < 0.01:
        offset_verdict = "fixed_bias"
    else:
        offset_verdict = "dynamic_drift"

    # ---- Q4: Residual improvement consistency ----
    residual_data: dict = {}
    for boundary in ("outer", "inner"):
        inp_stds = _extract(inp_metrics, f"{boundary}_residual_std")
        out_stds = _extract(out_metrics, f"{boundary}_residual_std")
        improvements = (1.0 - out_stds / np.maximum(inp_stds, 1e-6)) * 100
        residual_data[boundary] = {
            "input_mean": round(float(np.mean(inp_stds)), 4),
            "output_mean": round(float(np.mean(out_stds)), 4),
            "improvement_mean_pct": round(float(np.mean(improvements)), 2),
            "improvement_std_pct": round(float(np.std(improvements)), 2),
            "improvement_min_pct": round(float(np.min(improvements)), 2),
            "improvement_max_pct": round(float(np.max(improvements)), 2),
        }

    # ---- Q5: Hotspot persistence ----
    hotspot_data: dict = {}
    for label, metrics in [("input", inp_metrics), ("output", out_metrics)]:
        for boundary in ("outer", "inner"):
            key = f"{label}_{boundary}"
            signals = np.array([m[f"{boundary}_residual_signal"] for m in metrics])
            hotspot = compute_hotspot_persistence(signals)
            hotspot_data[key] = {
                "threshold_px": round(float(hotspot["threshold_px"]), 4),
                "n_persistent_angles_gt50pct": hotspot["n_persistent_angles_gt50pct"],
                "persistent_angle_fraction_gt50pct": round(float(hotspot["persistent_angle_fraction_gt50pct"]), 4),
                "mean_persistence": round(float(hotspot["mean_persistence"]), 4),
                "max_persistence": round(float(hotspot["max_persistence"]), 4),
                "persistence_profile": [round(float(v), 3) for v in hotspot["persistence"]],
            }

    return {
        "dataset": config.name,
        "short_name": config.short_name,
        "n_frames": n,
        "expected_step_px": config.expected_step_px,
        "step_stability": {
            **step_data,
            "improvement_pct": step_improvement,
            "gmf_step_std": gmf_step_std,
            "gmf_baseline_step_std": config.gmf_baseline_step_std,
        },
        "k2_stability": {
            **k2_data,
            "verdict": k2_verdict,
        },
        "center_offset_drift": {
            **offset_data,
            "verdict": offset_verdict,
        },
        "residual_consistency": residual_data,
        "hotspot_persistence": hotspot_data,
    }


# ---------------------------------------------------------------------------
# Plot functions
# ---------------------------------------------------------------------------

def _save(fig, path):
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)


def plot_01_center_trajectory(inp, out, summary, out_path):
    """Center (cx,cy) trajectory scatter, colored by frame index.
    An 'Output range' rectangle is overlaid on the Input panel so readers
    can directly see how much the scatter compressed."""
    fig, axes = plt.subplots(1, 2, figsize=(18, 9))
    fig.suptitle(f"Center Trajectory — {summary['dataset']}", fontsize=14)

    # Gather data for both conditions first
    panel_data: list[tuple] = []
    for metrics, label, clr in [
        (inp, "Input", CLR_INPUT),
        (out, "Output", CLR_OUTPUT),
    ]:
        cx = np.array([m["outer_fit_cx"] for m in metrics])
        cy = np.array([m["outer_fit_cy"] for m in metrics])
        panel_data.append((cx, cy, label, clr))

    for ax_idx, (cx, cy, label, clr) in enumerate(panel_data):
        ax = axes[ax_idx]
        idx = np.arange(len(cx))
        sc = ax.scatter(cx, cy, c=idx, cmap="viridis", s=18, alpha=0.8, edgecolors="none")
        ax.plot(cx, cy, color=clr, alpha=0.25, linewidth=0.7)
        ax.plot(cx[0], cy[0], "o", markersize=7, markerfacecolor="none", markeredgecolor="black",
                label="Start frame")
        ax.plot(cx[-1], cy[-1], "s", markersize=7, markerfacecolor="none", markeredgecolor="black",
                label="End frame")
        plt.colorbar(sc, ax=ax, label="Frame index")

        # 2-sigma ellipse
        mean_cx, mean_cy = np.mean(cx), np.mean(cy)
        std_cx, std_cy = np.std(cx), np.std(cy)
        theta = np.linspace(0, 2 * np.pi, 200)
        ax.plot(mean_cx + 2 * std_cx * np.cos(theta),
                mean_cy + 2 * std_cy * np.sin(theta),
                "--", color=clr, alpha=0.6, label="2σ ellipse")
        ax.plot(mean_cx, mean_cy, "x", color=clr, markersize=12, markeredgewidth=2)

        steps_y = np.diff(cy)
        step_std = np.std(steps_y)
        span_x = np.ptp(cx)
        span_y = np.ptp(cy)
        ax.set_title(
            f"{label}  (step_std_y = {step_std:.4f} px, "
            f"span_x = {span_x:.2f} px, span_y = {span_y:.2f} px)",
            fontsize=11,
        )
        ax.set_xlabel("cx (px)")
        ax.set_ylabel("cy (px)")
        ax.legend(fontsize=9)
        ax.grid(True, alpha=0.25)
        x_pad = max(span_x * 0.2, 1.0)
        y_pad = max(span_y * 0.05, 1.0)
        ax.set_xlim(float(np.min(cx) - x_pad), float(np.max(cx) + x_pad))
        ax.set_ylim(float(np.min(cy) - y_pad), float(np.max(cy) + y_pad))
        ax.set_aspect("auto")

    # Overlay output extent rectangle on input panel for scale comparison.
    # Clip the rectangle to the input panel limits so it always draws even
    # when the output trajectory extends beyond the input view.
    from matplotlib.patches import Rectangle
    out_cx, out_cy = panel_data[1][0], panel_data[1][1]
    rect_x0, rect_x1 = float(np.min(out_cx)), float(np.max(out_cx))
    rect_y0, rect_y1 = float(np.min(out_cy)), float(np.max(out_cy))
    inp_xlim = axes[0].get_xlim()
    inp_ylim = axes[0].get_ylim()
    # Clamp to visible area
    vis_x0 = max(rect_x0, inp_xlim[0])
    vis_x1 = min(rect_x1, inp_xlim[1])
    vis_y0 = max(rect_y0, inp_ylim[0])
    vis_y1 = min(rect_y1, inp_ylim[1])
    if vis_x1 > vis_x0 and vis_y1 > vis_y0:
        rect = Rectangle(
            (vis_x0, vis_y0), vis_x1 - vis_x0, vis_y1 - vis_y0,
            linewidth=2, edgecolor=CLR_OUTPUT, facecolor=CLR_OUTPUT,
            alpha=0.15, linestyle="-", zorder=6, clip_on=True,
        )
        axes[0].add_patch(rect)
        # Place label inside the visible rectangle area
        label_x = (vis_x0 + vis_x1) / 2
        label_y = vis_y0 + (vis_y1 - vis_y0) * 0.15
        axes[0].text(
            label_x, label_y, "Output range",
            ha="center", va="bottom", fontsize=9, color=CLR_OUTPUT,
            fontweight="bold", zorder=7,
        )

    _save(fig, out_path)


def plot_02_step_stability(inp, out, summary, out_path):
    """2x2: Y/X step for input/output.  Rows share y-limits so the
    dramatic variance compression from input→output is visually obvious."""
    fig, axes = plt.subplots(2, 2, figsize=(18, 12))
    fig.suptitle(f"Frame-to-Frame Step Stability — {summary['dataset']}", fontsize=14)

    # Pre-compute steps for both conditions so we can find shared limits
    all_steps: dict[str, dict[str, np.ndarray]] = {}
    for label, metrics in [("Input", inp), ("Output", out)]:
        cy = np.array([m["outer_fit_cy"] for m in metrics])
        cx = np.array([m["outer_fit_cx"] for m in metrics])
        all_steps[label] = {"Y": np.diff(cy), "X": np.diff(cx)}

    for col, (label, clr) in enumerate([("Input", CLR_INPUT), ("Output", CLR_OUTPUT)]):
        for row, axis_label in enumerate(["Y", "X"]):
            ax = axes[row, col]
            steps = all_steps[label][axis_label]
            idx = np.arange(len(steps))
            mean_s = np.mean(steps)
            std_s = np.std(steps)
            ax.plot(idx, steps, "-o", color=clr, markersize=2.5, alpha=0.7, linewidth=0.8)
            ax.axhline(mean_s, color=clr, linestyle="--", alpha=0.6, linewidth=1.2)
            ax.fill_between(idx, mean_s - std_s, mean_s + std_s, color=clr, alpha=0.12)
            ax.set_title(f"{label} — {axis_label} step  (μ={mean_s:.4f}, σ={std_s:.4f})", fontsize=11)
            ax.set_xlabel("Frame pair index")
            ax.set_ylabel(f"Δ{axis_label} (px)")
            ax.grid(True, alpha=0.25)

    # Share y-limits within each row so input vs output scale is directly comparable
    for row, axis_label in enumerate(["Y", "X"]):
        all_vals = np.concatenate([all_steps["Input"][axis_label],
                                   all_steps["Output"][axis_label]])
        pad = (np.max(all_vals) - np.min(all_vals)) * 0.08
        shared_lo = float(np.min(all_vals) - pad)
        shared_hi = float(np.max(all_vals) + pad)
        axes[row, 0].set_ylim(shared_lo, shared_hi)
        axes[row, 1].set_ylim(shared_lo, shared_hi)

    plt.tight_layout()
    _save(fig, out_path)


def plot_03_residual_timeseries(inp, out, summary, out_path):
    """Residual std time series for outer/inner."""
    fig, axes = plt.subplots(2, 1, figsize=(16, 10))
    fig.suptitle(f"Circle-Fit Residual Std Over Frames — {summary['dataset']}", fontsize=14)

    for row, boundary in enumerate(["outer", "inner"]):
        ax = axes[row]
        key = f"{boundary}_residual_std"
        inp_vals = np.array([m[key] for m in inp])
        out_vals = np.array([m[key] for m in out])
        idx = np.arange(len(inp_vals))

        ax.plot(idx, inp_vals, "-o", color=CLR_INPUT, markersize=2.5, alpha=0.7,
                linewidth=0.8, label=f"Input (μ={np.mean(inp_vals):.3f})")
        ax.plot(idx, out_vals, "-o", color=CLR_OUTPUT, markersize=2.5, alpha=0.7,
                linewidth=0.8, label=f"Output (μ={np.mean(out_vals):.3f})")

        # Improvement on secondary axis
        ax2 = ax.twinx()
        improvement = (1 - out_vals / np.maximum(inp_vals, 1e-6)) * 100
        ax2.fill_between(idx, improvement, alpha=0.15, color="green")
        ax2.plot(idx, improvement, "-", color="green", alpha=0.5, linewidth=0.7)
        ax2.set_ylabel("Improvement %", color="green", fontsize=10)
        ax2.tick_params(axis="y", labelcolor="green")

        ax.set_title(f"{boundary.capitalize()} Boundary — Residual Std", fontsize=12)
        ax.set_xlabel("Frame index")
        ax.set_ylabel("Residual std (px)")
        ax.legend(fontsize=9, loc="upper left")
        ax.grid(True, alpha=0.25)

    plt.tight_layout()
    _save(fig, out_path)


def plot_04_k2_timeseries(inp, out, summary, out_path):
    """k=2 amplitude and phase time series for outer/inner."""
    fig, axes = plt.subplots(2, 2, figsize=(18, 12))
    fig.suptitle(f"k=2 Elliptical Mode Stability — {summary['dataset']}", fontsize=14)

    for row, boundary in enumerate(["outer", "inner"]):
        ax_amp = axes[row, 0]
        ax_phase = axes[row, 1]

        for metrics, label, clr in [(inp, "Input", CLR_INPUT), (out, "Output", CLR_OUTPUT)]:
            amps = np.array([m[f"{boundary}_k2_amplitude"] for m in metrics])
            phases = np.array([m[f"{boundary}_k2_phase_deg"] for m in metrics])
            phases_display = phase_deviation_for_plot(phases)
            idx = np.arange(len(amps))
            cv = np.std(amps) / max(np.mean(amps), 1e-6) * 100
            phase_std = circular_std_deg(phases.tolist())

            ax_amp.plot(idx, amps, "-o", color=clr, markersize=2.5, alpha=0.7,
                        linewidth=0.8, label=f"{label} (CV={cv:.1f}%)")
            ax_amp.axhline(np.mean(amps), color=clr, linestyle="--", alpha=0.4)

            ax_phase.plot(idx, phases_display, "-o", color=clr, markersize=2.5, alpha=0.7,
                          linewidth=0.8, label=f"{label} (circ σ={phase_std:.1f}°)")

        ax_amp.set_title(f"{boundary.capitalize()} — k=2 Amplitude", fontsize=11)
        ax_amp.set_xlabel("Frame index")
        ax_amp.set_ylabel("k=2 amplitude (px)")
        ax_amp.legend(fontsize=9)
        ax_amp.grid(True, alpha=0.25)

        ax_phase.set_title(f"{boundary.capitalize()} — k=2 Phase", fontsize=11)
        ax_phase.set_xlabel("Frame index")
        ax_phase.set_ylabel("Phase deviation from circular mean (deg)")
        ax_phase.legend(fontsize=9)
        ax_phase.grid(True, alpha=0.25)

    plt.tight_layout()
    _save(fig, out_path)


def plot_05_hotspot_persistence(inp, out, summary, out_path):
    """2x2 heatmap of sequence-global hotspot masks for input/output and outer/inner."""
    fig, axes = plt.subplots(2, 2, figsize=(18, 12))
    fig.suptitle(f"Residual Hotspot Persistence Heatmap — {summary['dataset']}", fontsize=14)

    for col, (metrics, label) in enumerate([(inp, "Input"), (out, "Output")]):
        for row, boundary in enumerate(["outer", "inner"]):
            ax = axes[row, col]
            signals = np.array([m[f"{boundary}_residual_signal"] for m in metrics])
            hotspot = compute_hotspot_persistence(signals)
            hot_mask = hotspot["hot_mask"].astype(np.float64)

            im = ax.imshow(
                hot_mask, aspect="auto", cmap="Reds",
                vmin=0, vmax=1,
                extent=[0, 360, len(metrics) - 0.5, -0.5],
                interpolation="nearest",
            )
            ax.set_title(f"{label} — {boundary.capitalize()}", fontsize=11)
            ax.set_xlabel("Angle (deg)")
            ax.set_ylabel("Frame index")
            ax.text(
                0.99,
                0.01,
                f"hot > {hotspot['threshold_px']:.2f} px\n"
                f"persistent angles: {hotspot['n_persistent_angles_gt50pct']}\n"
                f"max persistence: {hotspot['max_persistence']:.2f}",
                transform=ax.transAxes,
                ha="right",
                va="bottom",
                fontsize=9,
                bbox=dict(boxstyle="round,pad=0.25", facecolor="white", alpha=0.85),
            )
            plt.colorbar(im, ax=ax, label="Hotspot mask", fraction=0.046, pad=0.04)

    plt.tight_layout()
    _save(fig, out_path)


def plot_06_edge_width_consistency(inp, out, summary, out_path):
    """Edge width time series for outer/inner."""
    fig, axes = plt.subplots(2, 1, figsize=(16, 10))
    fig.suptitle(f"Edge Width Consistency Over Frames — {summary['dataset']}", fontsize=14)

    for row, boundary in enumerate(["outer", "inner"]):
        ax = axes[row]
        key = f"{boundary}_edge_width_mean"
        inp_vals = np.array([m[key] for m in inp])
        out_vals = np.array([m[key] for m in out])
        idx = np.arange(len(inp_vals))

        ax.plot(idx, inp_vals, "-o", color=CLR_INPUT, markersize=2.5, alpha=0.7,
                linewidth=0.8, label=f"Input (μ={np.nanmean(inp_vals):.2f})")
        ax.plot(idx, out_vals, "-o", color=CLR_OUTPUT, markersize=2.5, alpha=0.7,
                linewidth=0.8, label=f"Output (μ={np.nanmean(out_vals):.2f})")

        ax.set_title(f"{boundary.capitalize()} Boundary — Mean Edge Width (10-90%)", fontsize=12)
        ax.set_xlabel("Frame index")
        ax.set_ylabel("Edge width (px)")
        ax.legend(fontsize=9)
        ax.grid(True, alpha=0.25)

    plt.tight_layout()
    _save(fig, out_path)


def plot_07_center_offset_drift(inp, out, summary, out_path):
    """Center offset (inner-outer mismatch) time series + trend line."""
    fig, ax = plt.subplots(figsize=(14, 7))
    fig.suptitle(f"Inner-Outer Center Offset Drift — {summary['dataset']}", fontsize=14)

    for metrics, label, clr in [(inp, "Input", CLR_INPUT), (out, "Output", CLR_OUTPUT)]:
        offsets = np.array([m["center_offset_px"] for m in metrics])
        idx = np.arange(len(offsets))
        ax.plot(idx, offsets, "-o", color=clr, markersize=2.5, alpha=0.7,
                linewidth=0.8, label=f"{label} (μ={np.mean(offsets):.3f}, σ={np.std(offsets):.3f})")

        # Linear trend
        if len(offsets) >= 3:
            slope, intercept = sp_stats.linregress(idx, offsets)[:2]
            ax.plot(idx, intercept + slope * idx, "--", color=clr, alpha=0.5,
                    label=f"{label} trend ({slope:.4f} px/frame)")

    ax.set_xlabel("Frame index")
    ax.set_ylabel("Center offset (px)")
    ax.legend(fontsize=9)
    ax.grid(True, alpha=0.25)

    verdict = summary["center_offset_drift"]["verdict"]
    ax.text(0.98, 0.98, f"Verdict: {verdict}",
            transform=ax.transAxes, ha="right", va="top", fontsize=12,
            bbox=dict(boxstyle="round,pad=0.3", facecolor="lightyellow", alpha=0.9))

    _save(fig, out_path)


def plot_08_cross_scale_step_std(summaries, out_path):
    """Grouped bar: 3 datasets x input/output step_std."""
    fig, ax = plt.subplots(figsize=(12, 7))
    fig.suptitle("Cross-Scale Internal Step Std Comparison", fontsize=14)

    names = [s["short_name"] for s in summaries]
    x = np.arange(len(names))
    w = 0.3

    inp_vals = [s["step_stability"]["input"]["internal_step_std_y"] for s in summaries]
    out_vals = [s["step_stability"]["output"]["internal_step_std_y"] for s in summaries]
    baseline_vals = [s["step_stability"].get("gmf_baseline_step_std") for s in summaries]

    ax.bar(x - w/2, inp_vals, w, color=CLR_INPUT, alpha=0.8, label="Input")
    ax.bar(x + w/2, out_vals, w, color=CLR_OUTPUT, alpha=0.8, label="Output")

    # GMF cross-validation values
    for i, s in enumerate(summaries):
        gmf = s["step_stability"].get("gmf_step_std")
        if gmf is not None:
            ax.plot(i + w/2 + 0.05, gmf, "D", color="darkorange", markersize=8,
                    zorder=5, label="GMF actual" if i == 0 else "")
        baseline = baseline_vals[i]
        if baseline is not None:
            ax.hlines(
                baseline,
                i + 0.02,
                i + 0.32,
                colors="darkorange",
                linestyles="--",
                linewidth=2.0,
                alpha=0.8,
                label="GMF baseline" if i == 0 else "",
            )

    # Annotate values with staggered vertical offsets to avoid overlap in log scale.
    # In log space the output bar, GMF diamond, and baseline line are very close,
    # so we use fixed point offsets rather than multiplicative offsets.
    for i, (iv, ov) in enumerate(zip(inp_vals, out_vals)):
        # Input label — above the tall bar, plenty of room
        ax.annotate(f"{iv:.4f}", xy=(i - w/2, iv), xytext=(0, 6),
                    textcoords="offset points", ha="center", va="bottom",
                    fontsize=8, color=CLR_INPUT)
        # Output label — shift upward enough to clear GMF markers
        ax.annotate(f"out {ov:.4f}", xy=(i + w/2, ov), xytext=(0, 28),
                    textcoords="offset points", ha="center", va="bottom",
                    fontsize=7.5, color=CLR_OUTPUT,
                    arrowprops=dict(arrowstyle="-", color=CLR_OUTPUT, lw=0.6, alpha=0.5))
        gmf = summaries[i]["step_stability"].get("gmf_step_std")
        if gmf is not None:
            ax.annotate(f"GMF {gmf:.4f}", xy=(i + w/2 + 0.05, gmf), xytext=(22, 14),
                        textcoords="offset points", ha="left", va="bottom",
                        fontsize=7.5, color="darkorange",
                        arrowprops=dict(arrowstyle="-", color="darkorange", lw=0.6, alpha=0.5))
        baseline = baseline_vals[i]
        if baseline is not None:
            ax.annotate(f"base {baseline:.4f}", xy=(i + 0.17, baseline), xytext=(0, -14),
                        textcoords="offset points", ha="center", va="top",
                        fontsize=7.5, color="darkorange", fontstyle="italic")

    ax.set_xticks(x)
    ax.set_xticklabels(names, fontsize=10)
    ax.set_ylabel("Internal step_std_y (px)")
    ax.set_yscale("log")
    ax.legend(fontsize=9)
    ax.grid(True, axis="y", alpha=0.25)

    _save(fig, out_path)


def plot_09_cross_scale_residual(summaries, out_path):
    """Grouped bar: residual improvement % across scales."""
    fig, ax = plt.subplots(figsize=(12, 7))
    fig.suptitle("Cross-Scale Residual Improvement Consistency", fontsize=14)

    names = [s["short_name"] for s in summaries]
    x = np.arange(len(names))
    w = 0.3

    outer_vals = [s["residual_consistency"]["outer"]["improvement_mean_pct"] for s in summaries]
    inner_vals = [s["residual_consistency"]["inner"]["improvement_mean_pct"] for s in summaries]

    ax.bar(x - w/2, outer_vals, w, color=CLR_OUTPUT, alpha=0.8, label="Outer boundary")
    ax.bar(x + w/2, inner_vals, w, color=CLR_OUTPUT, alpha=0.5, label="Inner boundary",
           hatch="//")

    # Error bars from std
    outer_err = [s["residual_consistency"]["outer"]["improvement_std_pct"] for s in summaries]
    inner_err = [s["residual_consistency"]["inner"]["improvement_std_pct"] for s in summaries]
    ax.errorbar(x - w/2, outer_vals, yerr=outer_err, fmt="none", ecolor="black", capsize=4)
    ax.errorbar(x + w/2, inner_vals, yerr=inner_err, fmt="none", ecolor="black", capsize=4)

    for i, (ov, iv) in enumerate(zip(outer_vals, inner_vals)):
        oe = outer_err[i]
        ie = inner_err[i]
        ax.text(i - w/2, ov + oe + 1.5, f"{ov:.1f}%", ha="center", va="bottom", fontsize=9)
        ax.text(i + w/2, iv + ie + 1.5, f"{iv:.1f}%", ha="center", va="bottom", fontsize=9)

    ax.set_xticks(x)
    ax.set_xticklabels(names, fontsize=10)
    ax.set_ylabel("Residual std improvement (%)")
    ax.legend(fontsize=9)
    ax.grid(True, axis="y", alpha=0.25)

    _save(fig, out_path)


def plot_10_cross_scale_k2(summaries, out_path):
    """Grouped bar: k=2 amplitude CV% across scales."""
    fig, ax = plt.subplots(figsize=(12, 7))
    fig.suptitle("Cross-Scale k=2 Elliptical Mode Stability (CV%)", fontsize=14)

    names = [s["short_name"] for s in summaries]
    x = np.arange(len(names))
    w = 0.2

    for i, (label, clr, offset) in enumerate([
        ("Input outer", CLR_INPUT, -1.5 * w),
        ("Input inner", CLR_INPUT, -0.5 * w),
        ("Output outer", CLR_OUTPUT, 0.5 * w),
        ("Output inner", CLR_OUTPUT, 1.5 * w),
    ]):
        name_key = label.split()[0].lower()
        boundary = label.split()[1]
        vals = [s["k2_stability"][f"{name_key}_{boundary}"]["k2_amp_cv_pct"] for s in summaries]
        hatch = "//" if "inner" in label else ""
        ax.bar(x + offset, vals, w, color=clr, alpha=0.7 if "inner" in label else 0.9,
               label=label, hatch=hatch)

    ax.set_xticks(x)
    ax.set_xticklabels(names, fontsize=10)
    ax.set_ylabel("k=2 amplitude CV%")
    ax.legend(fontsize=8, ncol=2)
    ax.grid(True, axis="y", alpha=0.25)

    _save(fig, out_path)


# ---------------------------------------------------------------------------
# Main orchestrator
# ---------------------------------------------------------------------------

def main(
    *,
    datasets: list[DatasetConfig] | None = None,
    out_root: Path = RESULTS_ROOT,
    verbose: bool = True,
) -> dict:
    datasets = datasets or DATASETS
    log = print if verbose else (lambda *a, **k: None)
    all_summaries: list[dict] = []
    all_per_frame: dict[str, dict] = {}

    for config in datasets:
        log(f"\n{'='*70}")
        log(f"DATASET: {config.name}  (expected step = {config.expected_step_px} px)")
        log(f"{'='*70}")

        pairs = match_input_recon_pairs(config)
        log(f"Matched {len(pairs)} input/output frame pairs")
        if not pairs:
            log("  [SKIP] No matched frames found")
            continue

        input_paths = [p[0] for p in pairs]
        recon_paths = [p[1] for p in pairs]

        log(f"\nProcessing INPUT frames...")
        inp_metrics = process_sequence(input_paths, label="input", log=log)

        log(f"\nProcessing OUTPUT frames...")
        out_metrics = process_sequence(recon_paths, label="output", log=log)

        log(f"\nComputing sequence summary...")
        summary = compute_sequence_summary(inp_metrics, out_metrics, config)
        all_summaries.append(summary)
        all_per_frame[config.short_name] = {
            "input": inp_metrics,
            "output": out_metrics,
        }

        # Save JSON outputs
        ds_dir = out_root / config.short_name
        ds_dir.mkdir(parents=True, exist_ok=True)

        # Strip residual_signal from per_frame for JSON (too large)
        def _strip_signals(metrics):
            stripped = []
            for m in metrics:
                s = {k: v for k, v in m.items() if not k.endswith("_residual_signal")}
                stripped.append(s)
            return stripped

        env_versions = _collect_env_versions()

        with open(ds_dir / "per_frame_metrics.json", "w", encoding="utf-8") as f:
            json.dump({
                "environment": env_versions,
                "input": _strip_signals(inp_metrics),
                "output": _strip_signals(out_metrics),
            }, f, indent=2, ensure_ascii=False)

        # Strip persistence_profile from summary for readability
        summary_clean = json.loads(json.dumps(summary))
        summary_clean["environment"] = env_versions
        for key in list(summary_clean.get("hotspot_persistence", {}).keys()):
            summary_clean["hotspot_persistence"][key].pop("persistence_profile", None)
        with open(ds_dir / "sequence_summary.json", "w", encoding="utf-8") as f:
            json.dump(summary_clean, f, indent=2, ensure_ascii=False)

        # Generate per-dataset plots
        log(f"\nGenerating plots...")
        plot_01_center_trajectory(inp_metrics, out_metrics, summary, ds_dir / "01_center_trajectory.png")
        log("  -> 01_center_trajectory.png")
        plot_02_step_stability(inp_metrics, out_metrics, summary, ds_dir / "02_step_stability.png")
        log("  -> 02_step_stability.png")
        plot_03_residual_timeseries(inp_metrics, out_metrics, summary, ds_dir / "03_residual_std_timeseries.png")
        log("  -> 03_residual_std_timeseries.png")
        plot_04_k2_timeseries(inp_metrics, out_metrics, summary, ds_dir / "04_k2_amplitude_timeseries.png")
        log("  -> 04_k2_amplitude_timeseries.png")
        plot_05_hotspot_persistence(inp_metrics, out_metrics, summary, ds_dir / "05_hotspot_persistence.png")
        log("  -> 05_hotspot_persistence.png")
        plot_06_edge_width_consistency(inp_metrics, out_metrics, summary, ds_dir / "06_edge_width_consistency.png")
        log("  -> 06_edge_width_consistency.png")
        plot_07_center_offset_drift(inp_metrics, out_metrics, summary, ds_dir / "07_center_offset_drift.png")
        log("  -> 07_center_offset_drift.png")

        log(f"\n  Step std (Y): input={summary['step_stability']['input']['internal_step_std_y']}"
            f"  output={summary['step_stability']['output']['internal_step_std_y']}"
            f"  improvement={summary['step_stability']['improvement_pct']}%")
        gmf = summary["step_stability"].get("gmf_step_std")
        if gmf is not None:
            log(f"  GMF step std (cross-validation): {gmf}")
        log(f"  k=2 verdict: {summary['k2_stability']['verdict']}")
        log(f"  Center offset verdict: {summary['center_offset_drift']['verdict']}")

    # Cross-dataset plots
    if len(all_summaries) >= 2:
        cross_dir = out_root / "cross_dataset"
        cross_dir.mkdir(parents=True, exist_ok=True)

        with open(cross_dir / "cross_dataset_comparison.json", "w", encoding="utf-8") as f:
            clean = []
            for s in all_summaries:
                sc = json.loads(json.dumps(s))
                for key in list(sc.get("hotspot_persistence", {}).keys()):
                    sc["hotspot_persistence"][key].pop("persistence_profile", None)
                clean.append(sc)
            json.dump({
                "environment": _collect_env_versions(),
                "datasets": clean,
            }, f, indent=2, ensure_ascii=False)

        plot_08_cross_scale_step_std(all_summaries, cross_dir / "08_cross_scale_step_std.png")
        log("\n  -> cross_dataset/08_cross_scale_step_std.png")
        plot_09_cross_scale_residual(all_summaries, cross_dir / "09_cross_scale_residual_improvement.png")
        log("  -> cross_dataset/09_cross_scale_residual_improvement.png")
        plot_10_cross_scale_k2(all_summaries, cross_dir / "10_cross_scale_k2_stability.png")
        log("  -> cross_dataset/10_cross_scale_k2_stability.png")

    log(f"\n{'='*70}")
    log("ALL SEQUENCE ANALYSES COMPLETE")
    log(f"{'='*70}")
    log(f"Results saved to: {out_root}")

    return {"summaries": all_summaries}


if __name__ == "__main__":
    main()

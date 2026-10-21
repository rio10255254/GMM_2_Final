from __future__ import annotations

import csv
import json
import math
from pathlib import Path
from typing import Any

import cv2
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from skimage.registration import phase_cross_correlation


ROOT = Path(__file__).resolve().parent
TRUSTED_ROOT = ROOT / "trusted_full_sequences"
ALL_ROOT = ROOT / "all_sequences"
OUT = ROOT / "boundary_projection_tuning_20x1um_5x0p5um_5x1um_20260706"
MANUAL_ROI_ROOT = (
    Path("D:/GMM_2_Final/Thesis_MOSR_Evidence")
    / "Displacement_3Mag_ManualRun_20260705"
    / "manual_roi_runs"
)
DATASET = "20260704_20x_5x"
VARIANTS = ["raw", "v28", "v31", "v35", "v41"]
GROUP_SOURCES = {
    "20x_1um": TRUSTED_ROOT,
    "5x_0p5um": TRUSTED_ROOT,
    "5x_1um": ALL_ROOT,
}
ROI_SCALES = [1.0, 0.9, 0.75]
EDGE_MODES = ["mag", "gx_abs"]
SIGMAS = [0.8, 1.2]
ESTIMATORS = ["parabola", "phase_profile", "phase_guarded"]


def read_manifest(root: Path) -> list[dict[str, str]]:
    with (root / "case_manifest.csv").open("r", newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def load_group_config(group: str) -> dict[str, Any]:
    summary_path = MANUAL_ROI_ROOT / f"{group}_raw" / "edge_phase_summary.json"
    payload = json.loads(summary_path.read_text(encoding="utf-8"))
    nominal = float(payload["expected_step_um"])
    pixel = float(payload["pixel_size_um"])
    roi = tuple(int(v) for v in payload["roi_x_y_width_height"])
    return {
        "group": group,
        "magnification": float(payload["magnification"]),
        "nominal_step_um": nominal,
        "object_um_per_px": pixel,
        "expected_step_px": nominal / pixel,
        "base_roi_x_y_width_height": roi,
        "roi_source": str(summary_path),
        "prior_manual_edge_phase": {
            "gap30_step_count": payload.get("gap30_step_count"),
            "median_abs_dx_um_gap30": payload.get("median_abs_dx_um_gap30"),
            "std_abs_dx_um_gap30": payload.get("std_abs_dx_um_gap30"),
            "median_abs_error_um_gap30": payload.get("median_abs_error_um_gap30"),
        },
    }


def build_case_map() -> dict[str, dict[str, dict[str, str]]]:
    by_root = {TRUSTED_ROOT: read_manifest(TRUSTED_ROOT), ALL_ROOT: read_manifest(ALL_ROOT)}
    case_map: dict[str, dict[str, dict[str, str]]] = {}
    for group, root in GROUP_SOURCES.items():
        variants: dict[str, dict[str, str]] = {}
        for row in by_root[root]:
            if row.get("dataset") != DATASET:
                continue
            if row.get("group") != group:
                continue
            if row.get("segment") != "full":
                continue
            if row.get("variant") not in VARIANTS:
                continue
            variants[row["variant"]] = row
        missing = sorted(set(VARIANTS) - set(variants))
        if missing:
            raise ValueError(f"missing variants for {group}: {missing}")
        case_map[group] = variants
    return case_map


def scaled_roi(
    roi: tuple[int, int, int, int], scale: float, image_shape: tuple[int, int]
) -> tuple[int, int, int, int]:
    x, y, w, h = roi
    cx = x + w / 2.0
    cy = y + h / 2.0
    nw = max(64, int(round(w * scale)))
    nh = max(64, int(round(h * scale)))
    nx = int(round(cx - nw / 2.0))
    ny = int(round(cy - nh / 2.0))
    height, width = image_shape
    nx = max(0, min(width - nw, nx))
    ny = max(0, min(height - nh, ny))
    return nx, ny, nw, nh


def list_images(folder: Path) -> list[Path]:
    files = sorted(folder.glob("*.bmp"))
    if len(files) < 2 and (folder / "bmp").is_dir():
        files = sorted((folder / "bmp").glob("*.bmp"))
    if len(files) < 2:
        raise ValueError(f"not enough BMP images in {folder}")
    return files


def read_gray(path: Path) -> np.ndarray:
    image = cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)
    if image is None:
        raise ValueError(f"cannot read image: {path}")
    return image


def normalize01(image: np.ndarray) -> np.ndarray:
    arr = image.astype(np.float32)
    lo = float(np.percentile(arr, 1.0))
    hi = float(np.percentile(arr, 99.0))
    if hi <= lo:
        lo, hi = float(arr.min()), float(arr.max())
    if hi <= lo:
        return np.zeros_like(arr, dtype=np.float32)
    return np.clip((arr - lo) / (hi - lo), 0.0, 1.0).astype(np.float32)


def edge_profile(
    image: np.ndarray,
    roi: tuple[int, int, int, int],
    *,
    edge_mode: str,
    sigma: float,
    axis: str,
) -> np.ndarray:
    x, y, w, h = roi
    crop = normalize01(image[y : y + h, x : x + w])
    crop = cv2.GaussianBlur(crop, (0, 0), sigma)
    gx = cv2.Sobel(crop, cv2.CV_32F, 1, 0, ksize=3)
    gy = cv2.Sobel(crop, cv2.CV_32F, 0, 1, ksize=3)
    if edge_mode == "gx_abs":
        edge = np.abs(gx)
    elif edge_mode == "mag":
        edge = cv2.magnitude(gx, gy)
    else:
        raise ValueError(f"unknown edge_mode: {edge_mode}")
    if axis == "x":
        vec = edge.sum(axis=0)
    elif axis == "y":
        vec = edge.sum(axis=1)
    else:
        raise ValueError("axis must be x or y")
    vec = vec.astype(np.float64)
    vec = vec - float(np.mean(vec))
    scale = float(np.std(vec))
    if scale > 1e-12:
        vec = vec / scale
    return vec * np.hanning(len(vec))


def corr_at_shift(reference: np.ndarray, moving: np.ndarray, shift: int) -> float:
    n = len(reference)
    if shift >= 0:
        ref = reference[: n - shift]
        mov = moving[shift:]
    else:
        ref = reference[-shift:]
        mov = moving[: n + shift]
    if len(ref) < max(16, n // 5):
        return -math.inf
    ref = ref - float(np.mean(ref))
    mov = mov - float(np.mean(mov))
    denom = float(np.linalg.norm(ref) * np.linalg.norm(mov))
    if denom <= 1e-12:
        return -math.inf
    return float(np.dot(ref, mov) / denom)


def corr_at_fractional_shift(reference: np.ndarray, moving: np.ndarray, shift: float) -> float:
    n = len(reference)
    if shift >= 0:
        xs = np.arange(0, max(0, int(math.floor(n - shift))), dtype=np.float64)
    else:
        xs = np.arange(int(math.ceil(-shift)), n, dtype=np.float64)
    if len(xs) < max(16, n // 5):
        return -math.inf
    mov_x = xs + shift
    ref = reference[xs.astype(np.int64)]
    mov = np.interp(mov_x, np.arange(n, dtype=np.float64), moving)
    ref = ref - float(np.mean(ref))
    mov = mov - float(np.mean(mov))
    denom = float(np.linalg.norm(ref) * np.linalg.norm(mov))
    if denom <= 1e-12:
        return -math.inf
    return float(np.dot(ref, mov) / denom)


def estimate_parabola(
    reference: np.ndarray,
    moving: np.ndarray,
    *,
    expected_shift: float,
    half_width: int,
) -> tuple[float, float]:
    center = int(round(expected_shift))
    candidates = list(range(center - half_width, center + half_width + 1))
    scores = {shift: corr_at_shift(reference, moving, shift) for shift in candidates}
    best = max(candidates, key=lambda shift: scores[shift])
    refined = float(best)
    if best - 1 in scores and best + 1 in scores:
        y0, y1, y2 = scores[best - 1], scores[best], scores[best + 1]
        denom = y0 - 2 * y1 + y2
        if math.isfinite(denom) and abs(denom) > 1e-12:
            refined = float(best + 0.5 * (y0 - y2) / denom)
            refined = max(float(best - 1), min(float(best + 1), refined))
    return refined, float(corr_at_fractional_shift(reference, moving, refined))


def estimate_phase_profile(
    reference: np.ndarray, moving: np.ndarray, *, axis: str
) -> tuple[float, float]:
    if axis == "x":
        shift, _, _ = phase_cross_correlation(
            reference.reshape(1, -1).astype(np.float32),
            moving.reshape(1, -1).astype(np.float32),
            upsample_factor=100,
            normalization=None,
        )
        dx = -float(shift[1])
    else:
        shift, _, _ = phase_cross_correlation(
            reference.reshape(-1, 1).astype(np.float32),
            moving.reshape(-1, 1).astype(np.float32),
            upsample_factor=100,
            normalization=None,
        )
        dx = -float(shift[0])
    return dx, float(corr_at_fractional_shift(reference, moving, dx))


def estimate_phase_guarded(
    reference: np.ndarray,
    moving: np.ndarray,
    *,
    axis: str,
    expected_shift: float,
    half_width: int,
    expected_abs_px: float,
) -> tuple[float, float, bool]:
    dx, quality = estimate_phase_profile(reference, moving, axis=axis)
    tolerance = max(0.75, expected_abs_px * 0.45)
    if abs(abs(dx) - expected_abs_px) <= tolerance:
        return dx, quality, False
    fallback_dx, fallback_quality = estimate_parabola(
        reference,
        moving,
        expected_shift=expected_shift,
        half_width=half_width,
    )
    return fallback_dx, fallback_quality, True


def search_half_width(expected_step_px: float) -> int:
    if expected_step_px < 1.2:
        return 2
    if expected_step_px < 3.5:
        return 3
    if expected_step_px < 8.0:
        return 4
    return 5


def choose_signed_dx(
    files: list[Path],
    cfg: dict[str, Any],
    method: dict[str, Any],
    roi: tuple[int, int, int, int],
) -> tuple[float, list[dict[str, Any]]]:
    images = [read_gray(path) for path in files[:16]]
    x_profiles = [
        edge_profile(
            image,
            roi,
            edge_mode=method["edge_mode"],
            sigma=method["sigma"],
            axis="x",
        )
        for image in images
    ]
    half_width = search_half_width(float(cfg["expected_step_px"]))
    candidates = [-float(cfg["expected_step_px"]), float(cfg["expected_step_px"])]
    diagnostics: list[dict[str, Any]] = []
    for expected_shift in candidates:
        values = []
        errors = []
        qualities = []
        for index in range(1, len(x_profiles)):
            dx, quality = estimate_parabola(
                x_profiles[index - 1],
                x_profiles[index],
                expected_shift=expected_shift,
                half_width=half_width,
            )
            step_um = abs(dx) * float(cfg["object_um_per_px"])
            values.append(step_um)
            errors.append(abs(step_um - float(cfg["nominal_step_um"])))
            qualities.append(quality)
        diagnostics.append(
            {
                "group": cfg["group"],
                "method_id": method["method_id"],
                "candidate_expected_signed_dx_px": expected_shift,
                "median_step_um_first15": float(np.median(values)),
                "median_abs_error_um_first15": float(np.median(errors)),
                "std_step_um_first15": sample_std(values),
                "mean_quality_first15": float(np.mean(qualities)),
            }
        )
    diagnostics.sort(
        key=lambda item: (
            item["median_abs_error_um_first15"],
            item["std_step_um_first15"],
            -item["mean_quality_first15"],
        )
    )
    return float(diagnostics[0]["candidate_expected_signed_dx_px"]), diagnostics


def method_grid() -> list[dict[str, Any]]:
    candidates = [
        (1.0, "mag", 0.8, "parabola"),
        (1.0, "mag", 0.8, "phase_profile"),
        (1.0, "mag", 0.8, "phase_guarded"),
        (1.0, "gx_abs", 0.8, "phase_profile"),
        (1.0, "gx_abs", 0.8, "phase_guarded"),
        (0.9, "mag", 0.8, "phase_profile"),
        (0.9, "mag", 0.8, "phase_guarded"),
        (0.9, "gx_abs", 0.8, "phase_profile"),
        (0.9, "gx_abs", 0.8, "phase_guarded"),
        (0.75, "gx_abs", 0.8, "phase_profile"),
        (0.75, "gx_abs", 0.8, "phase_guarded"),
        (0.9, "mag", 1.2, "phase_profile"),
        (0.9, "mag", 1.2, "phase_guarded"),
    ]
    methods = []
    for roi_scale, edge_mode, sigma, estimator in candidates:
        method_id = (
            f"roi{int(round(roi_scale * 100))}_"
            f"{edge_mode}_sigma{str(sigma).replace('.', 'p')}_{estimator}"
        )
        methods.append(
            {
                "method_id": method_id,
                "roi_scale": roi_scale,
                "edge_mode": edge_mode,
                "sigma": sigma,
                "estimator": estimator,
            }
        )
    return methods


def sample_std(values: list[float]) -> float:
    if len(values) <= 1:
        return 0.0
    return float(np.std(np.asarray(values, dtype=np.float64), ddof=1))


def summarize_rows(
    rows: list[dict[str, Any]],
    *,
    group: str,
    method_id: str,
    case_name: str,
    variant: str,
    selection: str,
) -> dict[str, Any]:
    steps = [float(row["x_step_um"]) for row in rows]
    errors = [float(row["abs_error_um"]) for row in rows]
    y_abs = [float(row["y_abs_um"]) for row in rows]
    qualities = [float(row["x_quality"]) for row in rows]
    return {
        "group": group,
        "method_id": method_id,
        "selection": selection,
        "case": case_name,
        "variant": variant,
        "n_steps": len(rows),
        "mean_step_um": float(np.mean(steps)) if steps else None,
        "median_step_um": float(np.median(steps)) if steps else None,
        "std_step_um": sample_std(steps),
        "median_abs_error_um": float(np.median(errors)) if errors else None,
        "mean_abs_error_um": float(np.mean(errors)) if errors else None,
        "max_abs_error_um": float(np.max(errors)) if errors else None,
        "median_y_abs_um": float(np.median(y_abs)) if y_abs else None,
        "mean_x_quality": float(np.mean(qualities)) if qualities else None,
        "min_x_quality": float(np.min(qualities)) if qualities else None,
    }


def measure_case(
    group: str,
    variant: str,
    row: dict[str, str],
    cfg: dict[str, Any],
    method: dict[str, Any],
    roi: tuple[int, int, int, int],
    expected_signed_dx_px: float,
) -> tuple[list[dict[str, Any]], dict[str, Any], list[str]]:
    files = list_images(Path(row["image_folder"]))
    images = [read_gray(path) for path in files]
    x_profiles = [
        edge_profile(
            image,
            roi,
            edge_mode=method["edge_mode"],
            sigma=method["sigma"],
            axis="x",
        )
        for image in images
    ]
    y_profiles = [
        edge_profile(
            image,
            roi,
            edge_mode=method["edge_mode"],
            sigma=method["sigma"],
            axis="y",
        )
        for image in images
    ]
    half_width = search_half_width(float(cfg["expected_step_px"]))
    y_half_width = max(3, half_width)
    rows: list[dict[str, Any]] = []
    for index in range(1, len(files)):
        x_used_fallback = False
        y_used_fallback = False
        if method["estimator"] == "phase_profile":
            dx, x_quality = estimate_phase_profile(
                x_profiles[index - 1], x_profiles[index], axis="x"
            )
            dy, y_quality = estimate_phase_profile(
                y_profiles[index - 1], y_profiles[index], axis="y"
            )
        elif method["estimator"] == "phase_guarded":
            dx, x_quality, x_used_fallback = estimate_phase_guarded(
                x_profiles[index - 1],
                x_profiles[index],
                axis="x",
                expected_shift=expected_signed_dx_px,
                half_width=half_width,
                expected_abs_px=float(cfg["expected_step_px"]),
            )
            dy, y_quality, y_used_fallback = estimate_phase_guarded(
                y_profiles[index - 1],
                y_profiles[index],
                axis="y",
                expected_shift=0.0,
                half_width=y_half_width,
                expected_abs_px=0.0,
            )
        else:
            dx, x_quality = estimate_parabola(
                x_profiles[index - 1],
                x_profiles[index],
                expected_shift=expected_signed_dx_px,
                half_width=half_width,
            )
            dy, y_quality = estimate_parabola(
                y_profiles[index - 1],
                y_profiles[index],
                expected_shift=0.0,
                half_width=y_half_width,
            )
        step_um = abs(dx) * float(cfg["object_um_per_px"])
        rows.append(
            {
                "group": group,
                "method_id": method["method_id"],
                "variant": variant,
                "case": row["case"],
                "step_index": index,
                "ref_frame": files[index - 1].name,
                "frame": files[index].name,
                "signed_dx_px": dx,
                "signed_dy_px": dy,
                "abs_dx_px": abs(dx),
                "abs_dy_px": abs(dy),
                "x_step_um": step_um,
                "y_abs_um": abs(dy) * float(cfg["object_um_per_px"]),
                "abs_error_um": abs(step_um - float(cfg["nominal_step_um"])),
                "x_quality": x_quality,
                "y_quality": y_quality,
                "roi_x": roi[0],
                "roi_y": roi[1],
                "roi_width": roi[2],
                "roi_height": roi[3],
                "roi_scale": method["roi_scale"],
                "edge_mode": method["edge_mode"],
                "edge_sigma_px": method["sigma"],
                "estimator": method["estimator"],
                "x_used_fallback": x_used_fallback,
                "y_used_fallback": y_used_fallback,
                "object_um_per_px": cfg["object_um_per_px"],
                "nominal_step_um": cfg["nominal_step_um"],
                "expected_step_px": cfg["expected_step_px"],
            }
        )
    summary = summarize_rows(
        rows,
        group=group,
        method_id=method["method_id"],
        case_name=row["case"],
        variant=variant,
        selection="all_steps",
    )
    return rows, summary, [path.name for path in files]


def select_step_indices(rows: list[dict[str, Any]], keep_count: int = 30) -> list[int]:
    ranked = sorted(
        rows,
        key=lambda row: (
            float(row["abs_error_um"]),
            abs(float(row["signed_dy_px"])),
            -float(row["x_quality"]),
        ),
    )
    return [int(row["step_index"]) for row in ranked[: min(keep_count, len(ranked))]]


def select_common_stable_steps(
    rows: list[dict[str, Any]], case_count: int, keep_count: int = 30
) -> list[int]:
    by_step: dict[int, list[dict[str, Any]]] = {}
    for row in rows:
        by_step.setdefault(int(row["step_index"]), []).append(row)
    scored = []
    for step, step_rows in sorted(by_step.items()):
        if len(step_rows) != case_count:
            continue
        errors = np.asarray([float(row["abs_error_um"]) for row in step_rows], dtype=np.float64)
        values = np.asarray([float(row["x_step_um"]) for row in step_rows], dtype=np.float64)
        y_abs = np.asarray([float(row["y_abs_um"]) for row in step_rows], dtype=np.float64)
        score = float(np.mean(errors) + 0.5 * np.std(values, ddof=1) + 0.1 * np.median(y_abs))
        scored.append((score, step))
    scored.sort()
    return [step for _, step in scored[: min(keep_count, len(scored))]]


def build_filtered_summaries(
    all_rows: list[dict[str, Any]], case_count: int
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    summaries: list[dict[str, Any]] = []
    selected_rows: list[dict[str, Any]] = []
    groups = sorted({str(row["group"]) for row in all_rows})
    methods = sorted({str(row["method_id"]) for row in all_rows})
    for group in groups:
        for method_id in methods:
            gm_rows = [
                row for row in all_rows if row["group"] == group and row["method_id"] == method_id
            ]
            if not gm_rows:
                continue
            common_steps = set(select_common_stable_steps(gm_rows, case_count, keep_count=30))
            raw_rows = [row for row in gm_rows if row["variant"] == "raw"]
            raw_anchor_steps = set(select_step_indices(raw_rows, keep_count=30))

            by_variant: dict[str, list[dict[str, Any]]] = {}
            for row in gm_rows:
                by_variant.setdefault(str(row["variant"]), []).append(row)
            for variant, rows in by_variant.items():
                case_name = str(rows[0]["case"])
                for selection, steps in [
                    ("common_best30", common_steps),
                    ("raw_anchor_best30", raw_anchor_steps),
                ]:
                    subset = [row for row in rows if int(row["step_index"]) in steps]
                    summaries.append(
                        summarize_rows(
                            subset,
                            group=group,
                            method_id=method_id,
                            case_name=case_name,
                            variant=variant,
                            selection=selection,
                        )
                    )
                    for row in subset:
                        selected = dict(row)
                        selected["stable_selection"] = selection
                        selected_rows.append(selected)
    return summaries, selected_rows


def build_comparison(summary_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    by_key: dict[tuple[str, str, str], dict[str, dict[str, Any]]] = {}
    for row in summary_rows:
        key = (str(row["group"]), str(row["method_id"]), str(row["selection"]))
        by_key.setdefault(key, {})[str(row["variant"])] = row
    for (group, method_id, selection), rows_by_variant in sorted(by_key.items()):
        raw = rows_by_variant.get("raw")
        if raw is None:
            continue
        raw_std = float(raw["std_step_um"])
        raw_err = float(raw["median_abs_error_um"])
        for variant in VARIANTS:
            row = rows_by_variant.get(variant)
            if row is None:
                continue
            std = float(row["std_step_um"])
            err = float(row["median_abs_error_um"])
            out.append(
                {
                    "group": group,
                    "method_id": method_id,
                    "selection": selection,
                    "variant": variant,
                    "n_steps": row["n_steps"],
                    "median_step_um": row["median_step_um"],
                    "std_step_um": std,
                    "median_abs_error_um": err,
                    "std_improvement_vs_raw_pct": 0.0
                    if variant == "raw" or raw_std <= 1e-12
                    else (raw_std - std) / raw_std * 100.0,
                    "median_error_change_vs_raw_um": 0.0
                    if variant == "raw"
                    else err - raw_err,
                    "mean_x_quality": row["mean_x_quality"],
                    "min_x_quality": row["min_x_quality"],
                }
            )
    return out


def summarize_method_rankings(comparison_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rankings: list[dict[str, Any]] = []
    groups = sorted({str(row["group"]) for row in comparison_rows})
    for group in groups:
        for selection in ["all_steps", "common_best30", "raw_anchor_best30"]:
            rows = [
                row
                for row in comparison_rows
                if row["group"] == group and row["selection"] == selection
            ]
            if not rows:
                continue
            method_ids = sorted({str(row["method_id"]) for row in rows})
            for method_id in method_ids:
                mrows = [row for row in rows if row["method_id"] == method_id]
                raw = next(row for row in mrows if row["variant"] == "raw")
                best_any = sorted(mrows, key=lambda row: float(row["std_step_um"]))[0]
                best_model_candidates = [row for row in mrows if row["variant"] != "raw"]
                best_model = sorted(best_model_candidates, key=lambda row: float(row["std_step_um"]))[0]
                rankings.append(
                    {
                        "group": group,
                        "selection": selection,
                        "method_id": method_id,
                        "raw_std_step_um": raw["std_step_um"],
                        "raw_median_abs_error_um": raw["median_abs_error_um"],
                        "best_any_variant": best_any["variant"],
                        "best_any_std_step_um": best_any["std_step_um"],
                        "best_model_variant": best_model["variant"],
                        "best_model_std_step_um": best_model["std_step_um"],
                        "best_model_improvement_vs_raw_pct": best_model[
                            "std_improvement_vs_raw_pct"
                        ],
                        "best_model_median_abs_error_um": best_model["median_abs_error_um"],
                    }
                )
    return rankings


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields: list[str] = []
    for row in rows:
        for key in row:
            if key not in fields:
                fields.append(key)
    with path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def draw_roi_previews(
    case_map: dict[str, dict[str, dict[str, str]]],
    configs: dict[str, dict[str, Any]],
) -> None:
    for group, variants in case_map.items():
        first = list_images(Path(variants["raw"]["image_folder"]))[0]
        image = read_gray(first)
        rgb = cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)
        colors = {
            1.0: (0, 0, 255),
            0.9: (0, 255, 255),
            0.75: (0, 255, 0),
        }
        for scale in ROI_SCALES:
            roi = scaled_roi(configs[group]["base_roi_x_y_width_height"], scale, image.shape)
            x, y, w, h = roi
            cv2.rectangle(rgb, (x, y), (x + w, y + h), colors[scale], 3)
        cv2.imwrite(str(OUT / f"roi_tuning_preview_{group}.png"), rgb)


def plot_best_method_bars(rankings: list[dict[str, Any]]) -> None:
    for group in sorted({str(row["group"]) for row in rankings}):
        rows = [
            row
            for row in rankings
            if row["group"] == group and row["selection"] == "raw_anchor_best30"
        ]
        top = sorted(rows, key=lambda row: float(row["best_model_std_step_um"]))[:10]
        labels = [f"{row['best_model_variant']}\\n{row['method_id']}" for row in top]
        raw_stds = [float(row["raw_std_step_um"]) for row in top]
        model_stds = [float(row["best_model_std_step_um"]) for row in top]
        x = np.arange(len(top))
        fig, ax = plt.subplots(figsize=(14, 6))
        ax.bar(x - 0.2, raw_stds, width=0.4, label="Raw")
        ax.bar(x + 0.2, model_stds, width=0.4, label="Best model")
        ax.set_xticks(x)
        ax.set_xticklabels(labels, rotation=45, ha="right", fontsize=8)
        ax.set_ylabel("Step standard deviation (um)")
        ax.set_title(f"{group}: top method candidates under Raw-anchor stable steps")
        ax.grid(True, axis="y", alpha=0.25)
        ax.legend()
        fig.tight_layout()
        fig.savefig(OUT / f"top_methods_raw_anchor_{group}.png", dpi=170)
        plt.close(fig)


def write_report(
    configs: dict[str, dict[str, Any]],
    rankings: list[dict[str, Any]],
    comparison_rows: list[dict[str, Any]],
) -> None:
    lines = [
        "# Boundary projection tuning readout",
        "",
        "Groups: 20x_1um and 5x_0p5um from trusted_full_sequences; 5x_1um from all_sequences as a diagnostic group.",
        "Variants: Raw, V28, V31, V35, V41.",
        "",
        "## Group setup",
        "",
        "| group | source status | nominal step um | pixel size um/px | expected px/step | base ROI | prior manual median um | prior manual std um |",
        "|---|---|---:|---:|---:|---|---:|---:|",
    ]
    for group, cfg in configs.items():
        prior = cfg["prior_manual_edge_phase"]
        source_status = "diagnostic all_sequences" if group == "5x_1um" else "trusted"
        roi = cfg["base_roi_x_y_width_height"]
        lines.append(
            f"| {group} | {source_status} | {cfg['nominal_step_um']:.3f} | "
            f"{cfg['object_um_per_px']:.6f} | {cfg['expected_step_px']:.6f} | "
            f"{roi[0]},{roi[1]},{roi[2]},{roi[3]} | "
            f"{float(prior['median_abs_dx_um_gap30']):.6f} | "
            f"{float(prior['std_abs_dx_um_gap30']):.6f} |"
        )
    lines.extend(
        [
            "",
            "## Best method per group, Raw-anchor stable 30 steps",
            "",
            "Raw-anchor means the 30 step indices are selected using Raw only, then every model is evaluated on those same steps.",
            "",
            "| group | best model | method | Raw std um | model std um | improvement | model median error um |",
            "|---|---|---|---:|---:|---:|---:|",
        ]
    )
    for group in sorted(configs):
        rows = [
            row
            for row in rankings
            if row["group"] == group and row["selection"] == "raw_anchor_best30"
        ]
        best = sorted(rows, key=lambda row: float(row["best_model_std_step_um"]))[0]
        lines.append(
            f"| {group} | {best['best_model_variant']} | {best['method_id']} | "
            f"{float(best['raw_std_step_um']):.6f} | "
            f"{float(best['best_model_std_step_um']):.6f} | "
            f"{float(best['best_model_improvement_vs_raw_pct']):+.2f}% | "
            f"{float(best['best_model_median_abs_error_um']):.6f} |"
        )
    lines.extend(
        [
            "",
            "## Fair Raw-only method check",
            "",
            "This chooses the method with the lowest Raw std inside each group, then reports the best model under that same method.",
            "",
            "| group | Raw-selected method | Raw std um | best model | model std um | improvement |",
            "|---|---|---:|---|---:|---:|",
        ]
    )
    for group in sorted(configs):
        rows = [
            row
            for row in rankings
            if row["group"] == group and row["selection"] == "raw_anchor_best30"
        ]
        raw_best = sorted(rows, key=lambda row: float(row["raw_std_step_um"]))[0]
        lines.append(
            f"| {group} | {raw_best['method_id']} | {float(raw_best['raw_std_step_um']):.6f} | "
            f"{raw_best['best_model_variant']} | {float(raw_best['best_model_std_step_um']):.6f} | "
            f"{float(raw_best['best_model_improvement_vs_raw_pct']):+.2f}% |"
        )
    lines.extend(
        [
            "",
            "## Outputs",
            "",
            "- tuning_all_steps.csv: every measurement under every tested method.",
            "- tuning_summary.csv: all-step and filtered summaries.",
            "- tuning_raw_comparison.csv: model-vs-Raw comparison.",
            "- tuning_method_rankings.csv: method-level ranking and best model under each method.",
            "- roi_tuning_preview_*.png: ROI scale previews.",
            "- top_methods_raw_anchor_*.png: top candidate method charts.",
        ]
    )
    (OUT / "BOUNDARY_PROJECTION_TUNING_READOUT.md").write_text(
        "\n".join(lines) + "\n", encoding="utf-8"
    )


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    case_map = build_case_map()
    configs = {group: load_group_config(group) for group in sorted(case_map)}
    methods = method_grid()

    all_rows: list[dict[str, Any]] = []
    summary_rows: list[dict[str, Any]] = []
    direction_diagnostics: list[dict[str, Any]] = []
    frame_names: dict[tuple[str, str], list[str]] = {}

    for group, variants in case_map.items():
        cfg = configs[group]
        raw_files = list_images(Path(variants["raw"]["image_folder"]))
        sample_image = read_gray(raw_files[0])
        for method in methods:
            roi = scaled_roi(
                cfg["base_roi_x_y_width_height"], float(method["roi_scale"]), sample_image.shape
            )
            expected_signed_dx_px, diagnostics = choose_signed_dx(raw_files, cfg, method, roi)
            direction_diagnostics.extend(diagnostics)
            for variant in VARIANTS:
                rows, summary, names = measure_case(
                    group,
                    variant,
                    variants[variant],
                    cfg,
                    method,
                    roi,
                    expected_signed_dx_px,
                )
                all_rows.extend(rows)
                summary_rows.append(summary)
                frame_names[(group, variant)] = names
            base_names = frame_names[(group, "raw")]
            for variant in VARIANTS:
                if frame_names[(group, variant)] != base_names:
                    raise ValueError(f"frame order mismatch: {group} {variant}")

    filtered_summaries, selected_rows = build_filtered_summaries(all_rows, len(VARIANTS))
    summary_rows.extend(filtered_summaries)
    comparison_rows = build_comparison(summary_rows)
    rankings = summarize_method_rankings(comparison_rows)

    write_csv(OUT / "tuning_all_steps.csv", all_rows)
    write_csv(OUT / "tuning_summary.csv", summary_rows)
    write_csv(OUT / "tuning_raw_comparison.csv", comparison_rows)
    write_csv(OUT / "tuning_selected_steps.csv", selected_rows)
    write_csv(OUT / "tuning_method_rankings.csv", rankings)
    write_csv(OUT / "tuning_direction_diagnostics.csv", direction_diagnostics)
    draw_roi_previews(case_map, configs)
    plot_best_method_bars(rankings)
    write_report(configs, rankings, comparison_rows)

    run_manifest = {
        "algorithm": "fixed_roi_boundary_projection_tuning",
        "groups": sorted(case_map),
        "group_sources": {group: str(root) for group, root in GROUP_SOURCES.items()},
        "variants": VARIANTS,
        "roi_scales": ROI_SCALES,
        "edge_modes": EDGE_MODES,
        "sigmas": SIGMAS,
        "estimators": ESTIMATORS,
        "method_count": len(methods),
        "output_dir": str(OUT),
        "rows": {
            "all_steps": len(all_rows),
            "summary": len(summary_rows),
            "comparison": len(comparison_rows),
            "rankings": len(rankings),
            "selected_steps": len(selected_rows),
        },
    }
    write_json(OUT / "tuning_manifest.json", run_manifest)
    print(json.dumps(run_manifest, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()

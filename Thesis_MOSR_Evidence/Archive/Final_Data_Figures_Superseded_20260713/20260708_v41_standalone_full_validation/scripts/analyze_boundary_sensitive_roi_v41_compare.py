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
PROJECT_ROOT = Path(__file__).resolve().parents[5]


ROOT = Path(str(PROJECT_ROOT / 'Thesis_MOSR_Evidence'))
VALIDATION_ROOT = ROOT / "Final_Data_Figures" / "20260708_v41_standalone_full_validation"
SOURCE_TABLE = VALIDATION_ROOT / "tables" / "displacement_all_profiles_all_cases.csv"
OUT = VALIDATION_ROOT / "boundary_sensitive_roi_v41_compare"
MANUAL_ROI_ROOT = ROOT / "Displacement_3Mag_ManualRun_20260705" / "manual_roi_runs"

CASES = ["raw", "v41_old", "v41_standalone"]
CASE_LABELS = {
    "raw": "Raw",
    "v41_old": "Old V41",
    "v41_standalone": "V41-Standalone",
}
GROUP_MANUAL_KEYS = {
    ("20260702_100MG", "x_1um"): "50x_1um",
    ("20260702_100MG", "x_0p5um"): "50x_0p5um",
    ("20260704_20x_5x", "20x_1um"): "20x_1um",
    ("20260704_20x_5x", "20x_0p5um"): "20x_0p5um",
    ("20260704_20x_5x", "5x_1um"): "5x_1um",
    ("20260704_20x_5x", "5x_0p5um"): "5x_0p5um",
}


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


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


def sample_std(values: list[float]) -> float:
    if len(values) <= 1:
        return 0.0
    return float(np.std(np.asarray(values, dtype=np.float64), ddof=1))


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
    axis: str,
    sigma: float = 0.8,
) -> np.ndarray:
    x, y, w, h = roi
    if x < 0 or y < 0 or x + w > image.shape[1] or y + h > image.shape[0]:
        raise ValueError(f"ROI {roi} outside image shape {image.shape}")
    crop = normalize01(image[y : y + h, x : x + w])
    crop = cv2.GaussianBlur(crop, (0, 0), sigma)
    gx = cv2.Sobel(crop, cv2.CV_32F, 1, 0, ksize=3)
    gy = cv2.Sobel(crop, cv2.CV_32F, 0, 1, ksize=3)
    edge = cv2.magnitude(gx, gy)
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


def estimate_shift_1d(
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
    return refined, corr_at_fractional_shift(reference, moving, refined)


def search_half_width(expected_step_px: float) -> int:
    if expected_step_px < 1.2:
        return 2
    if expected_step_px < 3.5:
        return 3
    if expected_step_px < 8.0:
        return 4
    return 5


def load_roi_config(dataset: str, group: str) -> dict[str, Any]:
    key = GROUP_MANUAL_KEYS[(dataset, group)]
    summary_path = MANUAL_ROI_ROOT / f"{key}_raw" / "edge_phase_summary.json"
    payload = json.loads(summary_path.read_text(encoding="utf-8"))
    nominal = float(payload["expected_step_um"])
    pixel = float(payload["pixel_size_um"])
    roi = tuple(int(v) for v in payload["roi_x_y_width_height"])
    return {
        "dataset": dataset,
        "group": group,
        "manual_key": key,
        "roi": roi,
        "roi_source": str(summary_path),
        "magnification": float(payload["magnification"]),
        "nominal_step_um": nominal,
        "object_um_per_px": pixel,
        "expected_step_px": nominal / pixel,
    }


def build_case_map(source_rows: list[dict[str, str]]) -> dict[tuple[str, str], dict[str, str]]:
    case_map: dict[tuple[str, str], dict[str, str]] = {}
    for row in source_rows:
        case = row["case"]
        if case not in CASES:
            continue
        key = (row["dataset"], row["group"])
        if key not in GROUP_MANUAL_KEYS:
            continue
        if key not in case_map:
            case_map[key] = {}
        case_map[key][case] = row["input_dir"]
    missing = {
        key: sorted(set(CASES) - set(cases))
        for key, cases in case_map.items()
        if set(cases) != set(CASES)
    }
    if missing:
        raise ValueError(f"missing cases: {missing}")
    return dict(sorted(case_map.items()))


def choose_signed_dx(
    files: list[Path],
    cfg: dict[str, Any],
) -> tuple[float, list[dict[str, Any]]]:
    roi = cfg["roi"]
    images = [read_gray(path) for path in files[: min(16, len(files))]]
    x_profiles = [edge_profile(image, roi, axis="x") for image in images]
    half_width = search_half_width(float(cfg["expected_step_px"]))
    diagnostics: list[dict[str, Any]] = []
    for expected_shift in [-float(cfg["expected_step_px"]), float(cfg["expected_step_px"])]:
        values: list[float] = []
        errors: list[float] = []
        qualities: list[float] = []
        for index in range(1, len(x_profiles)):
            dx, quality = estimate_shift_1d(
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
                "dataset": cfg["dataset"],
                "group": cfg["group"],
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


def measure_case(
    dataset: str,
    group: str,
    case: str,
    folder: Path,
    cfg: dict[str, Any],
    expected_signed_dx_px: float,
) -> tuple[list[dict[str, Any]], dict[str, Any], list[str]]:
    files = list_images(folder)
    images = [read_gray(path) for path in files]
    roi = cfg["roi"]
    x_profiles = [edge_profile(image, roi, axis="x") for image in images]
    y_profiles = [edge_profile(image, roi, axis="y") for image in images]
    half_width = search_half_width(float(cfg["expected_step_px"]))
    y_half_width = max(3, half_width)
    rows: list[dict[str, Any]] = []
    for index in range(1, len(files)):
        dx, x_quality = estimate_shift_1d(
            x_profiles[index - 1],
            x_profiles[index],
            expected_shift=expected_signed_dx_px,
            half_width=half_width,
        )
        dy, y_quality = estimate_shift_1d(
            y_profiles[index - 1],
            y_profiles[index],
            expected_shift=0.0,
            half_width=y_half_width,
        )
        step_um = abs(dx) * float(cfg["object_um_per_px"])
        rows.append(
            {
                "dataset": dataset,
                "group": group,
                "case": case,
                "case_label": CASE_LABELS[case],
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
                "object_um_per_px": cfg["object_um_per_px"],
                "nominal_step_um": cfg["nominal_step_um"],
                "expected_step_px": cfg["expected_step_px"],
                "expected_signed_dx_px": expected_signed_dx_px,
                "search_half_width_px": half_width,
                "input_dir": str(folder),
            }
        )
    return rows, summarize_rows(rows, "all_steps"), [path.name for path in files]


def summarize_rows(rows: list[dict[str, Any]], selection: str) -> dict[str, Any]:
    if not rows:
        raise ValueError("cannot summarize empty rows")
    steps = [float(row["x_step_um"]) for row in rows]
    errors = [float(row["abs_error_um"]) for row in rows]
    y_abs = [float(row["y_abs_um"]) for row in rows]
    qualities = [float(row["x_quality"]) for row in rows]
    first = rows[0]
    return {
        "dataset": first["dataset"],
        "group": first["group"],
        "case": first["case"],
        "case_label": first["case_label"],
        "selection": selection,
        "n_steps": len(rows),
        "nominal_step_um": first["nominal_step_um"],
        "object_um_per_px": first["object_um_per_px"],
        "median_step_um": float(np.median(steps)),
        "mean_step_um": float(np.mean(steps)),
        "std_step_um": sample_std(steps),
        "median_abs_error_um": float(np.median(errors)),
        "mean_abs_error_um": float(np.mean(errors)),
        "p90_abs_error_um": float(np.percentile(errors, 90)),
        "max_abs_error_um": float(np.max(errors)),
        "median_y_abs_um": float(np.median(y_abs)),
        "mean_x_quality": float(np.mean(qualities)),
        "min_x_quality": float(np.min(qualities)),
        "roi_x": first["roi_x"],
        "roi_y": first["roi_y"],
        "roi_width": first["roi_width"],
        "roi_height": first["roi_height"],
        "input_dir": first["input_dir"],
    }


def select_common_best30(rows: list[dict[str, Any]], case_count: int) -> set[int]:
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
    return {step for _, step in scored[: min(30, len(scored))]}


def select_raw_anchor_best30(rows: list[dict[str, Any]]) -> set[int]:
    raw_rows = [row for row in rows if row["case"] == "raw"]
    ranked = sorted(
        raw_rows,
        key=lambda row: (
            float(row["abs_error_um"]),
            float(row["y_abs_um"]),
            -float(row["x_quality"]),
        ),
    )
    return {int(row["step_index"]) for row in ranked[: min(30, len(ranked))]}


def build_filtered_summaries(all_rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    summary_rows: list[dict[str, Any]] = []
    selected_rows: list[dict[str, Any]] = []
    step_diag_rows: list[dict[str, Any]] = []
    keys = sorted({(row["dataset"], row["group"]) for row in all_rows})
    for dataset, group in keys:
        group_rows = [row for row in all_rows if row["dataset"] == dataset and row["group"] == group]
        common_steps = select_common_best30(group_rows, len(CASES))
        raw_anchor_steps = select_raw_anchor_best30(group_rows)
        for selection, steps in [
            ("common_best30", common_steps),
            ("raw_anchor_best30", raw_anchor_steps),
        ]:
            for case in CASES:
                rows = [
                    row
                    for row in group_rows
                    if row["case"] == case and int(row["step_index"]) in steps
                ]
                if rows:
                    summary_rows.append(summarize_rows(rows, selection))
                    for row in rows:
                        out_row = dict(row)
                        out_row["selection"] = selection
                        selected_rows.append(out_row)
        for step in sorted({int(row["step_index"]) for row in group_rows}):
            rows = [row for row in group_rows if int(row["step_index"]) == step]
            if len(rows) != len(CASES):
                continue
            values = [float(row["x_step_um"]) for row in rows]
            errors = [float(row["abs_error_um"]) for row in rows]
            step_diag_rows.append(
                {
                    "dataset": dataset,
                    "group": group,
                    "step_index": step,
                    "is_common_best30": step in common_steps,
                    "is_raw_anchor_best30": step in raw_anchor_steps,
                    "mean_abs_error_um_across_cases": float(np.mean(errors)),
                    "std_step_um_across_cases": sample_std(values),
                    "range_step_um_across_cases": float(np.max(values) - np.min(values)),
                }
            )
    return summary_rows, selected_rows, step_diag_rows


def build_comparison(summary_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    by_key: dict[tuple[str, str, str], dict[str, dict[str, Any]]] = {}
    for row in summary_rows:
        key = (row["dataset"], row["group"], row["selection"])
        by_key.setdefault(key, {})[row["case"]] = row
    for (dataset, group, selection), cases in sorted(by_key.items()):
        raw = cases["raw"]
        raw_std = float(raw["std_step_um"])
        raw_err = float(raw["median_abs_error_um"])
        for case in CASES:
            row = cases[case]
            std = float(row["std_step_um"])
            err = float(row["median_abs_error_um"])
            out.append(
                {
                    "dataset": dataset,
                    "group": group,
                    "selection": selection,
                    "case": case,
                    "case_label": CASE_LABELS[case],
                    "n_steps": row["n_steps"],
                    "median_step_um": row["median_step_um"],
                    "std_step_um": std,
                    "median_abs_error_um": err,
                    "std_improvement_vs_raw_pct": 0.0
                    if case == "raw" or raw_std <= 1e-12
                    else (raw_std - std) / raw_std * 100.0,
                    "median_error_change_vs_raw_um": 0.0 if case == "raw" else err - raw_err,
                    "mean_x_quality": row["mean_x_quality"],
                    "min_x_quality": row["min_x_quality"],
                }
            )
    return out


def build_advantage_summary(comparison_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    keys = sorted({(row["dataset"], row["group"], row["selection"]) for row in comparison_rows})
    for dataset, group, selection in keys:
        subset = [
            row
            for row in comparison_rows
            if row["dataset"] == dataset and row["group"] == group and row["selection"] == selection
        ]
        by_case = {row["case"]: row for row in subset}
        raw = by_case["raw"]
        old = by_case["v41_old"]
        new = by_case["v41_standalone"]
        best_v41 = min([old, new], key=lambda row: float(row["std_step_um"]))
        rows.append(
            {
                "dataset": dataset,
                "group": group,
                "selection": selection,
                "raw_std_um": raw["std_step_um"],
                "old_v41_std_um": old["std_step_um"],
                "v41_standalone_std_um": new["std_step_um"],
                "old_v41_improvement_vs_raw_pct": old["std_improvement_vs_raw_pct"],
                "v41_standalone_improvement_vs_raw_pct": new["std_improvement_vs_raw_pct"],
                "best_v41_case": best_v41["case_label"],
                "best_v41_std_um": best_v41["std_step_um"],
                "best_v41_improvement_vs_raw_pct": best_v41["std_improvement_vs_raw_pct"],
                "old_v41_median_error_um": old["median_abs_error_um"],
                "v41_standalone_median_error_um": new["median_abs_error_um"],
                "raw_median_error_um": raw["median_abs_error_um"],
                "old_v41_error_change_vs_raw_um": old["median_error_change_vs_raw_um"],
                "v41_standalone_error_change_vs_raw_um": new["median_error_change_vs_raw_um"],
                "both_v41_better_than_raw_std": (
                    float(old["std_improvement_vs_raw_pct"]) > 0
                    and float(new["std_improvement_vs_raw_pct"]) > 0
                ),
            }
        )
    return rows


def draw_roi_preview(dataset: str, group: str, raw_folder: Path, roi: tuple[int, int, int, int]) -> None:
    image = read_gray(list_images(raw_folder)[0])
    rgb = cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)
    x, y, w, h = roi
    cv2.rectangle(rgb, (x, y), (x + w, y + h), (0, 0, 255), 4)
    cv2.imwrite(str(OUT / "figures" / f"roi_preview_{dataset}_{group}.png"), rgb)


def plot_step_traces(all_rows: list[dict[str, Any]], step_diag_rows: list[dict[str, Any]]) -> None:
    for dataset, group in sorted({(row["dataset"], row["group"]) for row in all_rows}):
        group_rows = [row for row in all_rows if row["dataset"] == dataset and row["group"] == group]
        common_steps = {
            int(row["step_index"])
            for row in step_diag_rows
            if row["dataset"] == dataset and row["group"] == group and row["is_common_best30"]
        }
        nominal = float(group_rows[0]["nominal_step_um"])
        plt.figure(figsize=(13.0, 6.5))
        for case in CASES:
            rows = [row for row in group_rows if row["case"] == case]
            plt.plot(
                [int(row["step_index"]) for row in rows],
                [float(row["x_step_um"]) for row in rows],
                marker="o",
                markersize=3,
                linewidth=1.2,
                label=CASE_LABELS[case],
            )
        for step in sorted(common_steps):
            plt.axvspan(step - 0.45, step + 0.45, color="0.9", alpha=0.20, linewidth=0)
        plt.axhline(nominal, linestyle="--", color="black", linewidth=1.0, label=f"nominal {nominal:g} um")
        plt.xlabel("Step index")
        plt.ylabel("Measured X displacement (um)")
        plt.title(f"Boundary-sensitive ROI displacement: {dataset} {group}")
        plt.grid(True, alpha=0.25)
        plt.legend(ncol=3)
        plt.tight_layout()
        plt.savefig(OUT / "figures" / f"boundary_sensitive_steps_{dataset}_{group}.png", dpi=170)
        plt.close()


def plot_summary(comparison_rows: list[dict[str, Any]]) -> None:
    for selection in ["all_steps", "common_best30", "raw_anchor_best30"]:
        rows = [row for row in comparison_rows if row["selection"] == selection]
        if not rows:
            continue
        labels = [f"{row['dataset']}\n{row['group']}\n{row['case_label']}" for row in rows]
        stds = [float(row["std_step_um"]) for row in rows]
        x = np.arange(len(rows))
        fig, ax = plt.subplots(figsize=(max(12, 0.56 * len(rows)), 6.5))
        colors = ["#7f7f7f" if row["case"] == "raw" else "#1f77b4" if row["case"] == "v41_old" else "#d62728" for row in rows]
        ax.bar(x, stds, color=colors)
        ax.set_xticks(x)
        ax.set_xticklabels(labels, rotation=45, ha="right", fontsize=8)
        ax.set_ylabel("Step standard deviation (um)")
        ax.set_title(f"Boundary-sensitive ROI method: {selection}")
        ax.grid(True, axis="y", alpha=0.25)
        fig.tight_layout()
        fig.savefig(OUT / "figures" / f"boundary_sensitive_std_{selection}.png", dpi=170)
        plt.close(fig)


def plot_advantage(advantage_rows: list[dict[str, Any]]) -> None:
    for selection in ["all_steps", "common_best30", "raw_anchor_best30"]:
        rows = [row for row in advantage_rows if row["selection"] == selection]
        labels = [f"{row['dataset']}\n{row['group']}" for row in rows]
        old_values = [float(row["old_v41_improvement_vs_raw_pct"]) for row in rows]
        new_values = [float(row["v41_standalone_improvement_vs_raw_pct"]) for row in rows]
        x = np.arange(len(rows))
        fig, ax = plt.subplots(figsize=(max(12, 1.05 * len(rows)), 6.0))
        ax.bar(x - 0.18, old_values, width=0.36, label="Old V41", color="#1f77b4")
        ax.bar(x + 0.18, new_values, width=0.36, label="V41-Standalone", color="#d62728")
        ax.axhline(0, color="black", linewidth=1.0)
        ax.set_xticks(x)
        ax.set_xticklabels(labels, rotation=35, ha="right", fontsize=9)
        ax.set_ylabel("Std improvement vs Raw (%)")
        ax.set_title(f"Boundary-sensitive ROI V41 advantage: {selection}")
        ax.grid(True, axis="y", alpha=0.25)
        ax.legend()
        fig.tight_layout()
        fig.savefig(OUT / "figures" / f"boundary_sensitive_v41_advantage_{selection}.png", dpi=170)
        plt.close(fig)


def write_report(
    comparison_rows: list[dict[str, Any]],
    advantage_rows: list[dict[str, Any]],
    run_manifest: dict[str, Any],
) -> None:
    lines = [
        "# Boundary-sensitive ROI V41 comparison",
        "",
        "Method: fixed manual ROI, Sobel edge projection, one-dimensional profile matching, and subpixel parabolic refinement.",
        "Compared cases: Raw, Old V41, and V41-Standalone. The same ROI and frame order are used inside each dataset/group.",
        "",
        "## Main all-step comparison",
        "",
        "| dataset | group | case | steps | std um | median error um | improvement vs Raw |",
        "|---|---|---|---:|---:|---:|---:|",
    ]
    for row in comparison_rows:
        if row["selection"] != "all_steps":
            continue
        lines.append(
            f"| {row['dataset']} | {row['group']} | {row['case_label']} | {row['n_steps']} | "
            f"{float(row['std_step_um']):.6f} | {float(row['median_abs_error_um']):.6f} | "
            f"{float(row['std_improvement_vs_raw_pct']):+.2f}% |"
        )
    lines.extend(
        [
            "",
            "## Common best-30 comparison",
            "",
            "Common best-30 uses the same 30 step indices for Raw, Old V41, and V41-Standalone inside each group.",
            "",
            "| dataset | group | case | steps | std um | median error um | improvement vs Raw |",
            "|---|---|---|---:|---:|---:|---:|",
        ]
    )
    for row in comparison_rows:
        if row["selection"] != "common_best30":
            continue
        lines.append(
            f"| {row['dataset']} | {row['group']} | {row['case_label']} | {row['n_steps']} | "
            f"{float(row['std_step_um']):.6f} | {float(row['median_abs_error_um']):.6f} | "
            f"{float(row['std_improvement_vs_raw_pct']):+.2f}% |"
        )
    lines.extend(
        [
            "",
            "## Best V41 reading by group",
            "",
            "| selection | dataset | group | best V41 | improvement vs Raw | both V41 better than Raw |",
            "|---|---|---|---|---:|---|",
        ]
    )
    for row in advantage_rows:
        lines.append(
            f"| {row['selection']} | {row['dataset']} | {row['group']} | {row['best_v41_case']} | "
            f"{float(row['best_v41_improvement_vs_raw_pct']):+.2f}% | "
            f"{row['both_v41_better_than_raw_std']} |"
        )
    lines.extend(
        [
            "",
            "## Data integrity",
            "",
            f"- Groups analyzed: {len(run_manifest['groups'])}",
            f"- Cases per group: {', '.join(CASES)}",
            "- Frame-name order is checked before calculation.",
            "- All source image folders are recorded in the manifest.",
            "",
            "## Output files",
            "",
            "- tables/boundary_sensitive_all_steps.csv",
            "- tables/boundary_sensitive_summary.csv",
            "- tables/boundary_sensitive_comparison.csv",
            "- tables/boundary_sensitive_selected_steps.csv",
            "- tables/boundary_sensitive_v41_advantage_summary.csv",
            "- figures/boundary_sensitive_steps_*.png",
            "- figures/boundary_sensitive_std_*.png",
            "- figures/boundary_sensitive_v41_advantage_*.png",
        ]
    )
    (OUT / "BOUNDARY_SENSITIVE_ROI_V41_COMPARE_REPORT.md").write_text(
        "\n".join(lines) + "\n", encoding="utf-8"
    )


def main() -> None:
    (OUT / "tables").mkdir(parents=True, exist_ok=True)
    (OUT / "figures").mkdir(parents=True, exist_ok=True)
    source_rows = read_csv(SOURCE_TABLE)
    case_map = build_case_map(source_rows)
    all_rows: list[dict[str, Any]] = []
    summary_rows: list[dict[str, Any]] = []
    direction_rows: list[dict[str, Any]] = []
    integrity_rows: list[dict[str, Any]] = []
    group_configs: dict[str, Any] = {}

    for (dataset, group), cases in case_map.items():
        cfg = load_roi_config(dataset, group)
        group_configs[f"{dataset}/{group}"] = cfg
        raw_files = list_images(Path(cases["raw"]))
        expected_signed_dx_px, diagnostics = choose_signed_dx(raw_files, cfg)
        direction_rows.extend(diagnostics)
        frame_names: dict[str, list[str]] = {}
        for case in CASES:
            rows, summary, names = measure_case(
                dataset,
                group,
                case,
                Path(cases[case]),
                cfg,
                expected_signed_dx_px,
            )
            all_rows.extend(rows)
            summary_rows.append(summary)
            frame_names[case] = names
            integrity_rows.append(
                {
                    "dataset": dataset,
                    "group": group,
                    "case": case,
                    "image_count": len(names),
                    "step_count": len(names) - 1,
                    "input_dir": cases[case],
                    "frame_order_matches_raw": names == frame_names["raw"] if "raw" in frame_names else True,
                }
            )
        for case in CASES:
            if frame_names[case] != frame_names["raw"]:
                raise ValueError(f"frame order mismatch: {dataset} {group} {case}")
        draw_roi_preview(dataset, group, Path(cases["raw"]), cfg["roi"])

    filtered_summaries, selected_rows, step_diag_rows = build_filtered_summaries(all_rows)
    summary_rows.extend(filtered_summaries)
    comparison_rows = build_comparison(summary_rows)
    advantage_rows = build_advantage_summary(comparison_rows)
    plot_step_traces(all_rows, step_diag_rows)
    plot_summary(comparison_rows)
    plot_advantage(advantage_rows)

    run_manifest = {
        "algorithm": "manual_roi_boundary_sensitive_projection",
        "source_table": str(SOURCE_TABLE),
        "output_dir": str(OUT),
        "cases": CASES,
        "groups": [f"{dataset}/{group}" for dataset, group in case_map],
        "group_configs": group_configs,
        "row_counts": {
            "all_steps": len(all_rows),
            "summary": len(summary_rows),
            "comparison": len(comparison_rows),
            "advantage": len(advantage_rows),
            "selected_steps": len(selected_rows),
            "step_diagnostics": len(step_diag_rows),
        },
    }
    write_csv(OUT / "tables" / "boundary_sensitive_all_steps.csv", all_rows)
    write_csv(OUT / "tables" / "boundary_sensitive_summary.csv", summary_rows)
    write_csv(OUT / "tables" / "boundary_sensitive_comparison.csv", comparison_rows)
    write_csv(OUT / "tables" / "boundary_sensitive_v41_advantage_summary.csv", advantage_rows)
    write_csv(OUT / "tables" / "boundary_sensitive_selected_steps.csv", selected_rows)
    write_csv(OUT / "tables" / "boundary_sensitive_step_diagnostics.csv", step_diag_rows)
    write_csv(OUT / "tables" / "boundary_sensitive_direction_diagnostics.csv", direction_rows)
    write_csv(OUT / "tables" / "boundary_sensitive_integrity_checks.csv", integrity_rows)
    write_json(OUT / "boundary_sensitive_manifest.json", run_manifest)
    write_report(comparison_rows, advantage_rows, run_manifest)
    print(json.dumps(run_manifest, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()

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
PROJECT_ROOT = Path(__file__).resolve().parents[4]


ROOT = Path(__file__).resolve().parent
OUT = ROOT / "boundary_projection_analysis_20x_5x_raw_v28_v31_v35_v41_20260706"
MANUAL_ROI_ROOT = (
    Path(str(PROJECT_ROOT / 'Thesis_MOSR_Evidence'))
    / "Displacement_3Mag_ManualRun_20260705"
    / "manual_roi_runs"
)
DATASET = "20260704_20x_5x"
VARIANTS = ["raw", "v28", "v31", "v35", "v41"]


def read_manifest() -> list[dict[str, str]]:
    manifest_path = ROOT / "case_manifest.csv"
    with manifest_path.open("r", newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def load_group_configs(groups: list[str]) -> dict[str, dict[str, Any]]:
    configs: dict[str, dict[str, Any]] = {}
    for group in groups:
        summary_path = MANUAL_ROI_ROOT / f"{group}_raw" / "edge_phase_summary.json"
        if not summary_path.exists():
            raise FileNotFoundError(f"missing manual ROI summary for {group}: {summary_path}")
        payload = json.loads(summary_path.read_text(encoding="utf-8"))
        roi = tuple(int(v) for v in payload["roi_x_y_width_height"])
        configs[group] = {
            "group": group,
            "magnification": float(payload["magnification"]),
            "nominal_step_um": float(payload["expected_step_um"]),
            "object_um_per_px": float(payload["pixel_size_um"]),
            "expected_step_px": float(payload["expected_step_um"])
            / float(payload["pixel_size_um"]),
            "roi_x_y_width_height": roi,
            "roi_source": str(summary_path),
        }
    return configs


def build_case_map(rows: list[dict[str, str]]) -> dict[str, dict[str, dict[str, str]]]:
    case_map: dict[str, dict[str, dict[str, str]]] = {}
    for row in rows:
        if row.get("dataset") != DATASET:
            continue
        if row.get("segment") != "full":
            continue
        if row.get("trusted_sequence") != "yes":
            continue
        if row.get("variant") not in VARIANTS:
            continue
        group = row["group"]
        variant = row["variant"]
        case_map.setdefault(group, {})[variant] = row
    complete = {
        group: variants
        for group, variants in sorted(case_map.items())
        if all(variant in variants for variant in VARIANTS)
    }
    return complete


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


def edge_image(image: np.ndarray, roi: tuple[int, int, int, int]) -> np.ndarray:
    x, y, w, h = roi
    if x < 0 or y < 0 or x + w > image.shape[1] or y + h > image.shape[0]:
        raise ValueError(f"ROI {roi} outside image shape {image.shape}")
    crop = image[y : y + h, x : x + w]
    crop = normalize01(crop)
    crop = cv2.GaussianBlur(crop, (0, 0), 0.8)
    gx = cv2.Sobel(crop, cv2.CV_32F, 1, 0, ksize=3)
    gy = cv2.Sobel(crop, cv2.CV_32F, 0, 1, ksize=3)
    edge = cv2.magnitude(gx, gy)
    if float(edge.max()) > 1e-8:
        edge = edge / float(edge.max())
    return edge.astype(np.float32, copy=False)


def profile(edge: np.ndarray, axis: str) -> np.ndarray:
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
    return refined, float(scores[best])


def search_half_width(expected_step_px: float) -> int:
    if expected_step_px < 1.2:
        return 2
    if expected_step_px < 3.5:
        return 3
    if expected_step_px < 8.0:
        return 4
    return 5


def case_profiles(
    row: dict[str, str], roi: tuple[int, int, int, int]
) -> tuple[list[Path], list[np.ndarray], list[np.ndarray]]:
    files = list_images(Path(row["image_folder"]))
    edges = [edge_image(read_gray(path), roi) for path in files]
    x_profiles = [profile(edge, "x") for edge in edges]
    y_profiles = [profile(edge, "y") for edge in edges]
    return files, x_profiles, y_profiles


def choose_signed_dx(
    raw_row: dict[str, str], cfg: dict[str, Any]
) -> tuple[float, list[dict[str, Any]]]:
    files, x_profiles, _ = case_profiles(raw_row, cfg["roi_x_y_width_height"])
    half_width = search_half_width(float(cfg["expected_step_px"]))
    candidates = [-float(cfg["expected_step_px"]), float(cfg["expected_step_px"])]
    diagnostics: list[dict[str, Any]] = []
    for expected_shift in candidates:
        values = []
        errors = []
        corrs = []
        for index in range(1, min(len(files), 16)):
            dx, corr = estimate_shift_1d(
                x_profiles[index - 1],
                x_profiles[index],
                expected_shift=expected_shift,
                half_width=half_width,
            )
            step_um = abs(dx) * float(cfg["object_um_per_px"])
            values.append(step_um)
            errors.append(abs(step_um - float(cfg["nominal_step_um"])))
            corrs.append(corr)
        diagnostics.append(
            {
                "group": cfg["group"],
                "candidate_expected_signed_dx_px": expected_shift,
                "median_step_um_first15": float(np.median(values)),
                "median_abs_error_um_first15": float(np.median(errors)),
                "std_step_um_first15": sample_std(values),
                "mean_corr_first15": float(np.mean(corrs)),
            }
        )
    diagnostics.sort(
        key=lambda item: (
            item["median_abs_error_um_first15"],
            item["std_step_um_first15"],
            -item["mean_corr_first15"],
        )
    )
    return float(diagnostics[0]["candidate_expected_signed_dx_px"]), diagnostics


def sample_std(values: list[float]) -> float:
    if len(values) <= 1:
        return 0.0
    return float(np.std(np.asarray(values, dtype=np.float64), ddof=1))


def summarize_case(
    group: str,
    case_name: str,
    variant: str,
    rows: list[dict[str, Any]],
    *,
    selection_label: str,
) -> dict[str, Any]:
    steps = [float(row["x_step_um"]) for row in rows]
    errors = [float(row["abs_error_um"]) for row in rows]
    y_abs = [float(row["y_abs_um"]) for row in rows]
    corrs = [float(row["x_corr"]) for row in rows]
    return {
        "group": group,
        "selection": selection_label,
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
        "mean_x_corr": float(np.mean(corrs)) if corrs else None,
        "min_x_corr": float(np.min(corrs)) if corrs else None,
    }


def measure_case(
    group: str,
    variant: str,
    row: dict[str, str],
    cfg: dict[str, Any],
    expected_signed_dx_px: float,
) -> tuple[list[dict[str, Any]], dict[str, Any], list[str]]:
    files, x_profiles, y_profiles = case_profiles(row, cfg["roi_x_y_width_height"])
    half_width = search_half_width(float(cfg["expected_step_px"]))
    y_half_width = max(3, half_width)

    out_rows: list[dict[str, Any]] = []
    for index in range(1, len(files)):
        dx, x_corr = estimate_shift_1d(
            x_profiles[index - 1],
            x_profiles[index],
            expected_shift=expected_signed_dx_px,
            half_width=half_width,
        )
        dy, y_corr = estimate_shift_1d(
            y_profiles[index - 1],
            y_profiles[index],
            expected_shift=0.0,
            half_width=y_half_width,
        )
        step_um = abs(dx) * float(cfg["object_um_per_px"])
        out_rows.append(
            {
                "group": group,
                "case": row["case"],
                "variant": variant,
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
                "x_corr": x_corr,
                "y_corr": y_corr,
                "roi_x": cfg["roi_x_y_width_height"][0],
                "roi_y": cfg["roi_x_y_width_height"][1],
                "roi_width": cfg["roi_x_y_width_height"][2],
                "roi_height": cfg["roi_x_y_width_height"][3],
                "object_um_per_px": cfg["object_um_per_px"],
                "nominal_step_um": cfg["nominal_step_um"],
                "expected_step_px": cfg["expected_step_px"],
                "expected_signed_dx_px": expected_signed_dx_px,
                "search_half_width_px": half_width,
            }
        )

    summary = summarize_case(
        group, row["case"], variant, out_rows, selection_label="all_steps"
    )
    summary.update(
        {
            "image_count": len(files),
            "step_count": len(out_rows),
            "image_folder": row["image_folder"],
            "object_um_per_px": cfg["object_um_per_px"],
            "nominal_step_um": cfg["nominal_step_um"],
            "expected_step_px": cfg["expected_step_px"],
            "expected_signed_dx_px": expected_signed_dx_px,
        }
    )
    return out_rows, summary, [path.name for path in files]


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


def select_common_stable_steps(
    group_rows: list[dict[str, Any]], case_count: int, keep_count: int = 30
) -> list[int]:
    by_step: dict[int, list[dict[str, Any]]] = {}
    for row in group_rows:
        by_step.setdefault(int(row["step_index"]), []).append(row)
    scored = []
    for step, step_rows in sorted(by_step.items()):
        if len(step_rows) != case_count:
            continue
        errors = np.asarray([float(row["abs_error_um"]) for row in step_rows], dtype=np.float64)
        values = np.asarray([float(row["x_step_um"]) for row in step_rows], dtype=np.float64)
        y_abs = np.asarray([float(row["y_abs_um"]) for row in step_rows], dtype=np.float64)
        score = float(np.mean(errors) + 0.5 * np.std(values, ddof=1) + 0.1 * np.median(y_abs))
        scored.append((score, step, float(np.mean(errors)), float(np.std(values, ddof=1))))
    scored.sort()
    return [step for _, step, _, _ in scored[: min(keep_count, len(scored))]]


def select_own_stable_steps(rows: list[dict[str, Any]], keep_count: int = 30) -> list[int]:
    ranked = sorted(
        rows,
        key=lambda row: (
            float(row["abs_error_um"]),
            abs(float(row["signed_dy_px"])),
            -float(row["x_corr"]),
        ),
    )
    return [int(row["step_index"]) for row in ranked[: min(keep_count, len(ranked))]]


def build_filtered_outputs(
    all_rows: list[dict[str, Any]], case_map: dict[str, dict[str, dict[str, str]]]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    summaries: list[dict[str, Any]] = []
    stable_rows: list[dict[str, Any]] = []
    common_step_rows: list[dict[str, Any]] = []

    for group, variant_rows in case_map.items():
        group_rows = [row for row in all_rows if row["group"] == group]
        case_count = len(variant_rows)
        common_steps = set(select_common_stable_steps(group_rows, case_count, keep_count=30))

        for row in group_rows:
            if int(row["step_index"]) in common_steps:
                stable_row = dict(row)
                stable_row["stable_selection"] = "common_best30"
                stable_rows.append(stable_row)

        by_case: dict[str, list[dict[str, Any]]] = {}
        for row in group_rows:
            by_case.setdefault(str(row["case"]), []).append(row)

        for case_name, rows in by_case.items():
            variant = str(rows[0]["variant"])
            common_case_rows = [row for row in rows if int(row["step_index"]) in common_steps]
            summaries.append(
                summarize_case(
                    group,
                    case_name,
                    variant,
                    common_case_rows,
                    selection_label="common_best30",
                )
            )
            own_steps = set(select_own_stable_steps(rows, keep_count=30))
            own_case_rows = [row for row in rows if int(row["step_index"]) in own_steps]
            summaries.append(
                summarize_case(
                    group,
                    case_name,
                    variant,
                    own_case_rows,
                    selection_label="own_best30_diagnostic",
                )
            )
            for row in own_case_rows:
                stable_row = dict(row)
                stable_row["stable_selection"] = "own_best30_diagnostic"
                stable_rows.append(stable_row)

        for step in sorted({int(row["step_index"]) for row in group_rows}):
            rows = [row for row in group_rows if int(row["step_index"]) == step]
            if len(rows) != case_count:
                continue
            errors = [float(row["abs_error_um"]) for row in rows]
            steps = [float(row["x_step_um"]) for row in rows]
            y_abs = [float(row["y_abs_um"]) for row in rows]
            common_step_rows.append(
                {
                    "group": group,
                    "step_index": step,
                    "is_common_best30": step in common_steps,
                    "mean_abs_error_um_across_cases": float(np.mean(errors)),
                    "std_step_um_across_cases": sample_std(steps),
                    "median_y_abs_um_across_cases": float(np.median(y_abs)),
                    "min_step_um_across_cases": float(np.min(steps)),
                    "max_step_um_across_cases": float(np.max(steps)),
                    "range_step_um_across_cases": float(np.max(steps) - np.min(steps)),
                }
            )
    return summaries, stable_rows, common_step_rows


def build_comparison(summary_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    by_group_selection: dict[tuple[str, str], dict[str, dict[str, Any]]] = {}
    for row in summary_rows:
        key = (str(row["group"]), str(row["selection"]))
        by_group_selection.setdefault(key, {})[str(row["variant"])] = row
    for (group, selection), rows_by_variant in sorted(by_group_selection.items()):
        raw = rows_by_variant.get("raw")
        if not raw:
            continue
        raw_std = float(raw["std_step_um"])
        raw_err = float(raw["median_abs_error_um"])
        for variant in VARIANTS:
            row = rows_by_variant.get(variant)
            if not row:
                continue
            std = float(row["std_step_um"])
            err = float(row["median_abs_error_um"])
            out.append(
                {
                    "group": group,
                    "selection": selection,
                    "variant": variant,
                    "n_steps": row["n_steps"],
                    "mean_step_um": row["mean_step_um"],
                    "median_step_um": row["median_step_um"],
                    "std_step_um": std,
                    "median_abs_error_um": err,
                    "std_improvement_vs_raw_pct": 0.0
                    if variant == "raw"
                    else (raw_std - std) / raw_std * 100.0
                    if raw_std > 1e-12
                    else 0.0,
                    "median_error_change_vs_raw_um": 0.0
                    if variant == "raw"
                    else err - raw_err,
                    "median_y_abs_um": row["median_y_abs_um"],
                    "mean_x_corr": row["mean_x_corr"],
                    "min_x_corr": row["min_x_corr"],
                }
            )
    return out


def draw_roi_preview(group: str, raw_row: dict[str, str], roi: tuple[int, int, int, int]) -> None:
    first_raw = list_images(Path(raw_row["image_folder"]))[0]
    image = read_gray(first_raw)
    rgb = cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)
    x, y, w, h = roi
    cv2.rectangle(rgb, (x, y), (x + w, y + h), (0, 0, 255), 4)
    cv2.imwrite(str(OUT / f"fixed_roi_preview_{group}.png"), rgb)


def plot_step_trace(
    group: str,
    all_rows: list[dict[str, Any]],
    common_steps: set[int],
    nominal_step_um: float,
) -> None:
    rows_for_group = [row for row in all_rows if row["group"] == group]
    plt.figure(figsize=(13.5, 7.2))
    for variant in VARIANTS:
        rows = [row for row in rows_for_group if row["variant"] == variant]
        if not rows:
            continue
        steps = [int(row["step_index"]) for row in rows]
        values = [float(row["x_step_um"]) for row in rows]
        plt.plot(steps, values, marker="o", linewidth=1.2, markersize=3, label=variant)
    for step in sorted(common_steps):
        plt.axvspan(step - 0.45, step + 0.45, color="0.9", alpha=0.25, linewidth=0)
    plt.axhline(
        nominal_step_um,
        linestyle="--",
        color="black",
        linewidth=1.2,
        label=f"nominal {nominal_step_um:g} um",
    )
    plt.xlabel("Step index")
    plt.ylabel("Measured X step (um)")
    plt.title(f"Boundary projection displacement: {group}")
    plt.grid(True, alpha=0.25)
    plt.legend(ncol=3)
    plt.tight_layout()
    plt.savefig(OUT / f"boundary_projection_step_trace_{group}.png", dpi=170)
    plt.close()


def plot_summary(comparison_rows: list[dict[str, Any]]) -> None:
    for group in sorted({str(row["group"]) for row in comparison_rows}):
        for selection in ["all_steps", "common_best30", "own_best30_diagnostic"]:
            rows = [
                row
                for row in comparison_rows
                if row["group"] == group and row["selection"] == selection
            ]
            if not rows:
                continue
            rows = sorted(rows, key=lambda row: float(row["std_step_um"]))
            labels = [row["variant"] for row in rows]
            stds = [float(row["std_step_um"]) for row in rows]
            errs = [float(row["median_abs_error_um"]) for row in rows]
            x = np.arange(len(rows))
            fig, axes = plt.subplots(1, 2, figsize=(12.0, 5.0))
            axes[0].bar(x, stds)
            axes[0].set_xticks(x)
            axes[0].set_xticklabels(labels)
            axes[0].set_ylabel("Step standard deviation (um)")
            axes[0].set_title(f"{group} {selection}: stability")
            axes[0].grid(True, axis="y", alpha=0.25)
            axes[1].bar(x, errs)
            axes[1].set_xticks(x)
            axes[1].set_xticklabels(labels)
            axes[1].set_ylabel("Median absolute error (um)")
            axes[1].set_title(f"{group} {selection}: accuracy")
            axes[1].grid(True, axis="y", alpha=0.25)
            fig.tight_layout()
            fig.savefig(OUT / f"boundary_projection_{group}_{selection}_ranking.png", dpi=170)
            plt.close(fig)


def write_report(
    case_map: dict[str, dict[str, dict[str, str]]],
    configs: dict[str, dict[str, Any]],
    comparison_rows: list[dict[str, Any]],
    common_step_rows: list[dict[str, Any]],
    sign_diagnostics: list[dict[str, Any]],
) -> None:
    lines = [
        "# 20x and 5x boundary projection readout",
        "",
        "Compared cases: Raw, V28, V31, V35, V41.",
        "Method: fixed manual ROI, boundary projection profile matching, and the same common stable 30 steps inside each group.",
        "",
        "## Available groups",
        "",
        "| group | nominal step um | pixel size um/px | expected px/step | ROI x,y,w,h |",
        "|---|---:|---:|---:|---|",
    ]
    for group in sorted(case_map):
        cfg = configs[group]
        roi = cfg["roi_x_y_width_height"]
        lines.append(
            f"| {group} | {cfg['nominal_step_um']:.3f} | "
            f"{cfg['object_um_per_px']:.6f} | {cfg['expected_step_px']:.6f} | "
            f"{roi[0]},{roi[1]},{roi[2]},{roi[3]} |"
        )
    lines.extend(
        [
            "",
            "Note: 5x_1um had a manual ROI record, but it is not present in this trusted full-sequence package.",
            "",
            "## Raw comparison",
            "",
            "| group | selection | variant | steps | median step um | std um | median abs error um | std improvement vs Raw | mean x corr |",
            "|---|---|---|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for row in comparison_rows:
        lines.append(
            f"| {row['group']} | {row['selection']} | {row['variant']} | {row['n_steps']} | "
            f"{float(row['median_step_um']):.6f} | {float(row['std_step_um']):.6f} | "
            f"{float(row['median_abs_error_um']):.6f} | "
            f"{float(row['std_improvement_vs_raw_pct']):+.2f}% | "
            f"{float(row['mean_x_corr']):.4f} |"
        )
    lines.extend(["", "## Common stable steps", ""])
    for group in sorted(case_map):
        common_steps = [
            int(row["step_index"])
            for row in common_step_rows
            if row["group"] == group and row.get("is_common_best30") is True
        ]
        lines.append(f"- {group}: {', '.join(str(step) for step in sorted(common_steps))}")
    lines.extend(
        [
            "",
            "## Direction check",
            "",
            "| group | candidate signed dx px | median step first15 um | median abs error first15 um | std first15 um | mean corr first15 |",
            "|---|---:|---:|---:|---:|---:|",
        ]
    )
    for row in sign_diagnostics:
        lines.append(
            f"| {row['group']} | {float(row['candidate_expected_signed_dx_px']):.6f} | "
            f"{float(row['median_step_um_first15']):.6f} | "
            f"{float(row['median_abs_error_um_first15']):.6f} | "
            f"{float(row['std_step_um_first15']):.6f} | "
            f"{float(row['mean_corr_first15']):.4f} |"
        )
    lines.extend(
        [
            "",
            "## Outputs",
            "",
            "- boundary_projection_all_steps.csv: every consecutive step for every available group and version.",
            "- boundary_projection_summary.csv: all-step, common stable-step, and diagnostic filtered summaries.",
            "- boundary_projection_raw_comparison.csv: direct comparison against Raw inside each group.",
            "- boundary_projection_stable_steps.csv: selected stable-step measurements.",
            "- boundary_projection_common_step_diagnostics.csv: selected and rejected step diagnostics.",
            "- fixed_roi_preview_*.png: the ROI used in each group.",
            "- boundary_projection_step_trace_*.png: step-by-step measured displacement traces.",
            "- boundary_projection_*_ranking.png: stability and accuracy ranking charts.",
        ]
    )
    (OUT / "BOUNDARY_PROJECTION_20X_5X_READOUT.md").write_text(
        "\n".join(lines) + "\n", encoding="utf-8"
    )


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    manifest_rows = read_manifest()
    case_map = build_case_map(manifest_rows)
    if not case_map:
        raise ValueError("no complete 20x/5x cases found")
    configs = load_group_configs(sorted(case_map))

    all_rows: list[dict[str, Any]] = []
    summary_rows: list[dict[str, Any]] = []
    sign_diagnostics: list[dict[str, Any]] = []
    selected_signs: dict[str, float] = {}
    frame_names: dict[tuple[str, str], list[str]] = {}

    for group, variant_rows in case_map.items():
        cfg = configs[group]
        expected_signed_dx_px, diagnostics = choose_signed_dx(variant_rows["raw"], cfg)
        selected_signs[group] = expected_signed_dx_px
        sign_diagnostics.extend(diagnostics)
        for variant in VARIANTS:
            rows, summary, names = measure_case(
                group,
                variant,
                variant_rows[variant],
                cfg,
                expected_signed_dx_px,
            )
            all_rows.extend(rows)
            summary_rows.append(summary)
            frame_names[(group, variant)] = names
        first_names = frame_names[(group, "raw")]
        for variant in VARIANTS:
            if frame_names[(group, variant)] != first_names:
                raise ValueError(f"frame order mismatch in {group} {variant}")
        draw_roi_preview(group, variant_rows["raw"], cfg["roi_x_y_width_height"])

    filtered_summaries, stable_measurement_rows, common_step_rows = build_filtered_outputs(
        all_rows, case_map
    )
    summary_rows.extend(filtered_summaries)
    comparison_rows = build_comparison(summary_rows)

    write_csv(OUT / "boundary_projection_all_steps.csv", all_rows)
    write_csv(OUT / "boundary_projection_summary.csv", summary_rows)
    write_csv(OUT / "boundary_projection_raw_comparison.csv", comparison_rows)
    write_csv(OUT / "boundary_projection_stable_steps.csv", stable_measurement_rows)
    write_csv(OUT / "boundary_projection_common_step_diagnostics.csv", common_step_rows)
    write_csv(OUT / "boundary_projection_direction_diagnostics.csv", sign_diagnostics)

    for group in sorted(case_map):
        common_steps = {
            int(row["step_index"])
            for row in common_step_rows
            if row["group"] == group and row.get("is_common_best30") is True
        }
        plot_step_trace(group, all_rows, common_steps, float(configs[group]["nominal_step_um"]))
    plot_summary(comparison_rows)
    write_report(case_map, configs, comparison_rows, common_step_rows, sign_diagnostics)

    missing_expected_groups = sorted(
        set(["20x_1um", "20x_0p5um", "5x_1um", "5x_0p5um"]) - set(case_map)
    )
    run_manifest = {
        "algorithm": "fixed_roi_boundary_projection_1d_profile_match",
        "dataset": DATASET,
        "variants": VARIANTS,
        "groups": sorted(case_map),
        "missing_expected_groups_in_trusted_package": missing_expected_groups,
        "configs": configs,
        "selected_expected_signed_dx_px": selected_signs,
        "output_dir": str(OUT),
        "image_count_per_case": {
            f"{group}_{variant}": len(frame_names[(group, variant)])
            for group in sorted(case_map)
            for variant in VARIANTS
        },
        "step_count_per_case": {
            f"{group}_{variant}": len(frame_names[(group, variant)]) - 1
            for group in sorted(case_map)
            for variant in VARIANTS
        },
    }
    write_json(OUT / "boundary_projection_manifest.json", run_manifest)
    print(json.dumps(run_manifest, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()

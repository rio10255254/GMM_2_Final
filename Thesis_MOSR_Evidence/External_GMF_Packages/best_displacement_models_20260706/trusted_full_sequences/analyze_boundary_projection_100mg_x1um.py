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


ROOT = Path(__file__).resolve().parent
OUT = ROOT / "boundary_projection_analysis_100MG_x1um_manualroi_raw_v28_v31_v35_v41_20260706"
CASE_NAMES = [
    "100MG_x_1um_full_raw",
    "100MG_x_1um_full_v28",
    "100MG_x_1um_full_v31",
    "100MG_x_1um_full_v35",
    "100MG_x_1um_full_v41",
]
ROI = (685, 453, 746, 758)  # x, y, width, height from the prior manual ROI run
CAMERA_PIXEL_UM = 3.45
MAGNIFICATION = 50.0
OBJECT_UM_PER_PX = CAMERA_PIXEL_UM / MAGNIFICATION
NOMINAL_STEP_UM = 1.0
EXPECTED_STEP_PX = NOMINAL_STEP_UM / OBJECT_UM_PER_PX
EXPECTED_SIGNED_DX_PX = -EXPECTED_STEP_PX


def read_manifest() -> dict[str, dict[str, str]]:
    manifest_path = ROOT / "case_manifest.csv"
    with manifest_path.open("r", newline="", encoding="utf-8-sig") as handle:
        rows = list(csv.DictReader(handle))
    return {row["case"]: row for row in rows}


def list_images(folder: Path) -> list[Path]:
    files = sorted(folder.glob("*.bmp"))
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
    window = np.hanning(len(vec))
    return vec * window


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


def measure_case(case_name: str, info: dict[str, str]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    folder = Path(info["image_folder"])
    files = list_images(folder)
    edges = [edge_image(read_gray(path), ROI) for path in files]
    x_profiles = [profile(edge, "x") for edge in edges]
    y_profiles = [profile(edge, "y") for edge in edges]

    rows: list[dict[str, Any]] = []
    for index in range(1, len(files)):
        dx, x_corr = estimate_shift_1d(
            x_profiles[index - 1],
            x_profiles[index],
            expected_shift=EXPECTED_SIGNED_DX_PX,
            half_width=4,
        )
        dy, y_corr = estimate_shift_1d(
            y_profiles[index - 1],
            y_profiles[index],
            expected_shift=0.0,
            half_width=4,
        )
        step_um = abs(dx) * OBJECT_UM_PER_PX
        row = {
            "case": case_name,
            "variant": info["variant"],
            "step_index": index,
            "ref_frame": files[index - 1].name,
            "frame": files[index].name,
            "signed_dx_px": dx,
            "signed_dy_px": dy,
            "abs_dx_px": abs(dx),
            "abs_dy_px": abs(dy),
            "x_step_um": step_um,
            "y_abs_um": abs(dy) * OBJECT_UM_PER_PX,
            "abs_error_um": abs(step_um - NOMINAL_STEP_UM),
            "x_corr": x_corr,
            "y_corr": y_corr,
            "roi_x": ROI[0],
            "roi_y": ROI[1],
            "roi_width": ROI[2],
            "roi_height": ROI[3],
        }
        rows.append(row)

    summary = summarize_case(case_name, info["variant"], rows, selection_label="all_steps")
    summary.update(
        {
            "image_count": len(files),
            "step_count": len(rows),
            "image_folder": str(folder),
        }
    )
    return rows, summary


def sample_std(values: list[float]) -> float:
    if len(values) <= 1:
        return 0.0
    return float(np.std(np.asarray(values, dtype=np.float64), ddof=1))


def summarize_case(
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


def select_common_stable_steps(rows: list[dict[str, Any]], keep_count: int = 30) -> list[int]:
    by_step: dict[int, list[dict[str, Any]]] = {}
    for row in rows:
        by_step.setdefault(int(row["step_index"]), []).append(row)
    scored = []
    for step, step_rows in sorted(by_step.items()):
        if len(step_rows) != len(CASE_NAMES):
            continue
        errors = np.asarray([float(row["abs_error_um"]) for row in step_rows], dtype=np.float64)
        values = np.asarray([float(row["x_step_um"]) for row in step_rows], dtype=np.float64)
        y_abs = np.asarray([float(row["y_abs_um"]) for row in step_rows], dtype=np.float64)
        score = float(np.mean(errors) + 0.5 * np.std(values, ddof=1) + 0.1 * np.median(y_abs))
        scored.append((score, step, float(np.mean(errors)), float(np.std(values, ddof=1))))
    scored.sort()
    return [step for _, step, _, _ in scored[:keep_count]]


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
    all_rows: list[dict[str, Any]]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    summaries: list[dict[str, Any]] = []
    stable_rows: list[dict[str, Any]] = []

    common_steps = set(select_common_stable_steps(all_rows, keep_count=30))
    for row in all_rows:
        if int(row["step_index"]) in common_steps:
            stable_row = dict(row)
            stable_row["stable_selection"] = "common_best30"
            stable_rows.append(stable_row)

    by_case: dict[str, list[dict[str, Any]]] = {}
    for row in all_rows:
        by_case.setdefault(str(row["case"]), []).append(row)

    for case_name, rows in by_case.items():
        variant = str(rows[0]["variant"])
        common_case_rows = [row for row in rows if int(row["step_index"]) in common_steps]
        summaries.append(
            summarize_case(case_name, variant, common_case_rows, selection_label="common_best30")
        )
        own_steps = set(select_own_stable_steps(rows, keep_count=30))
        own_case_rows = [row for row in rows if int(row["step_index"]) in own_steps]
        summaries.append(
            summarize_case(case_name, variant, own_case_rows, selection_label="own_best30_diagnostic")
        )
        for row in own_case_rows:
            stable_row = dict(row)
            stable_row["stable_selection"] = "own_best30_diagnostic"
            stable_rows.append(stable_row)

    common_step_rows = []
    for step in sorted({int(row["step_index"]) for row in all_rows}):
        rows = [row for row in all_rows if int(row["step_index"]) == step]
        if len(rows) != len(CASE_NAMES):
            continue
        errors = [float(row["abs_error_um"]) for row in rows]
        steps = [float(row["x_step_um"]) for row in rows]
        common_step_rows.append(
            {
                "step_index": step,
                "is_common_best30": step in common_steps,
                "mean_abs_error_um_across_cases": float(np.mean(errors)),
                "std_step_um_across_cases": sample_std(steps),
                "min_step_um_across_cases": float(np.min(steps)),
                "max_step_um_across_cases": float(np.max(steps)),
                "range_step_um_across_cases": float(np.max(steps) - np.min(steps)),
            }
        )
    return summaries, stable_rows, common_step_rows


def build_comparison(summary_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    by_selection: dict[str, dict[str, dict[str, Any]]] = {}
    for row in summary_rows:
        by_selection.setdefault(str(row["selection"]), {})[str(row["variant"])] = row
    for selection, rows_by_variant in by_selection.items():
        raw = rows_by_variant.get("raw")
        if not raw:
            continue
        raw_std = float(raw["std_step_um"])
        raw_err = float(raw["median_abs_error_um"])
        for variant, row in rows_by_variant.items():
            std = float(row["std_step_um"])
            err = float(row["median_abs_error_um"])
            out.append(
                {
                    "selection": selection,
                    "variant": variant,
                    "n_steps": row["n_steps"],
                    "mean_step_um": row["mean_step_um"],
                    "median_step_um": row["median_step_um"],
                    "std_step_um": std,
                    "median_abs_error_um": err,
                    "std_improvement_vs_raw_pct": 0.0
                    if variant == "raw"
                    else (raw_std - std) / raw_std * 100.0,
                    "median_error_change_vs_raw_um": 0.0
                    if variant == "raw"
                    else err - raw_err,
                    "median_y_abs_um": row["median_y_abs_um"],
                    "mean_x_corr": row["mean_x_corr"],
                    "min_x_corr": row["min_x_corr"],
                }
            )
    return out


def draw_roi_preview(first_raw: Path) -> None:
    image = read_gray(first_raw)
    rgb = cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)
    x, y, w, h = ROI
    cv2.rectangle(rgb, (x, y), (x + w, y + h), (0, 0, 255), 4)
    cv2.imwrite(str(OUT / "fixed_roi_preview.png"), rgb)


def plot_step_trace(all_rows: list[dict[str, Any]], common_steps: set[int]) -> None:
    plt.figure(figsize=(13.5, 7.2))
    for case_name in CASE_NAMES:
        rows = [row for row in all_rows if row["case"] == case_name]
        variant = rows[0]["variant"]
        steps = [int(row["step_index"]) for row in rows]
        values = [float(row["x_step_um"]) for row in rows]
        plt.plot(steps, values, marker="o", linewidth=1.2, markersize=3, label=variant)
    for step in sorted(common_steps):
        plt.axvspan(step - 0.45, step + 0.45, color="0.9", alpha=0.25, linewidth=0)
    plt.axhline(NOMINAL_STEP_UM, linestyle="--", color="black", linewidth=1.2, label="nominal 1 um")
    plt.xlabel("Step index")
    plt.ylabel("Measured X step (um)")
    plt.title("Boundary projection displacement: Raw vs V28/V31/V35/V41")
    plt.grid(True, alpha=0.25)
    plt.legend(ncol=3)
    plt.tight_layout()
    plt.savefig(OUT / "boundary_projection_step_trace.png", dpi=170)
    plt.close()


def plot_summary(comparison_rows: list[dict[str, Any]]) -> None:
    for selection in ["all_steps", "common_best30", "own_best30_diagnostic"]:
        rows = [row for row in comparison_rows if row["selection"] == selection]
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
        axes[0].set_title(f"{selection}: stability")
        axes[0].grid(True, axis="y", alpha=0.25)
        axes[1].bar(x, errs)
        axes[1].set_xticks(x)
        axes[1].set_xticklabels(labels)
        axes[1].set_ylabel("Median absolute error (um)")
        axes[1].set_title(f"{selection}: accuracy to 1 um")
        axes[1].grid(True, axis="y", alpha=0.25)
        fig.tight_layout()
        fig.savefig(OUT / f"boundary_projection_{selection}_ranking.png", dpi=170)
        plt.close(fig)


def write_report(
    summary_rows: list[dict[str, Any]],
    comparison_rows: list[dict[str, Any]],
    common_step_rows: list[dict[str, Any]],
) -> None:
    common_steps = [
        int(row["step_index"])
        for row in common_step_rows
        if row.get("is_common_best30") is True
    ]
    common_steps = sorted(set(common_steps))
    x, y, w, h = ROI
    lines = [
        "# 100MG x 1um boundary projection readout",
        "",
        f"Fixed ROI: x={x}, y={y}, width={w}, height={h} on 2048x1536 frames.",
        "This ROI is the same manually selected 50x 1um ROI used in the prior thesis manual-run package and is reused for Raw, V28, V31, V35, and V41.",
        "",
        f"Object-plane pixel size: {OBJECT_UM_PER_PX:.6f} um/px. Nominal step: {NOMINAL_STEP_UM:.3f} um.",
        "Scale note: this 20260702 100MG image sequence behaves as the 50x dataset used in the thesis manual-run package; 1 um is about 14.49 px in the image.",
        "",
        "## Raw comparison",
        "",
        "| selection | variant | steps | median step um | std um | median abs error um | std improvement vs Raw |",
        "|---|---|---:|---:|---:|---:|---:|",
    ]
    for row in comparison_rows:
        lines.append(
            f"| {row['selection']} | {row['variant']} | {row['n_steps']} | "
            f"{float(row['median_step_um']):.6f} | {float(row['std_step_um']):.6f} | "
            f"{float(row['median_abs_error_um']):.6f} | "
            f"{float(row['std_improvement_vs_raw_pct']):+.2f}% |"
        )
    lines.extend(
        [
            "",
            "## Common stable steps",
            "",
            "The common stable set uses the same 30 step indices for every version.",
            "",
            ", ".join(str(step) for step in common_steps),
            "",
            "## Outputs",
            "",
            "- boundary_projection_all_steps.csv: every consecutive step for every version.",
            "- boundary_projection_summary.csv: all-step and filtered summaries.",
            "- boundary_projection_raw_comparison.csv: direct comparison against Raw.",
            "- boundary_projection_stable_steps.csv: selected stable-step measurements for every version.",
            "- boundary_projection_common_step_diagnostics.csv: the shared stable-step selection and rejected unstable steps.",
            "- fixed_roi_preview.png: ROI used for all versions.",
        ]
    )
    (OUT / "BOUNDARY_PROJECTION_100MG_X1UM_READOUT.md").write_text(
        "\n".join(lines) + "\n", encoding="utf-8"
    )


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    manifest = read_manifest()
    missing = [case for case in CASE_NAMES if case not in manifest]
    if missing:
        raise ValueError(f"missing cases in manifest: {missing}")

    all_rows: list[dict[str, Any]] = []
    summary_rows: list[dict[str, Any]] = []
    frame_names: dict[str, list[str]] = {}
    for case_name in CASE_NAMES:
        rows, summary = measure_case(case_name, manifest[case_name])
        all_rows.extend(rows)
        summary_rows.append(summary)
        frame_names[case_name] = [row["ref_frame"] for row in rows[:1]] + [row["frame"] for row in rows]

    first_names = next(iter(frame_names.values()))
    for case_name, names in frame_names.items():
        if names != first_names:
            raise ValueError(f"frame order mismatch in {case_name}")

    filtered_summaries, stable_measurement_rows, common_step_rows = build_filtered_outputs(all_rows)
    summary_rows.extend(filtered_summaries)
    comparison_rows = build_comparison(summary_rows)
    common_steps = {
        int(row["step_index"])
        for row in common_step_rows
        if row.get("is_common_best30") is True
    }

    write_csv(OUT / "boundary_projection_all_steps.csv", all_rows)
    write_csv(OUT / "boundary_projection_summary.csv", summary_rows)
    write_csv(OUT / "boundary_projection_raw_comparison.csv", comparison_rows)
    write_csv(OUT / "boundary_projection_stable_steps.csv", stable_measurement_rows)
    write_csv(OUT / "boundary_projection_common_step_diagnostics.csv", common_step_rows)
    draw_roi_preview(Path(manifest["100MG_x_1um_full_raw"]["image_folder"]) / "frame_0000.bmp")
    plot_step_trace(all_rows, common_steps)
    plot_summary(comparison_rows)
    write_report(summary_rows, comparison_rows, common_step_rows)

    run_manifest = {
        "algorithm": "fixed_roi_boundary_projection_1d_profile_match",
        "cases": CASE_NAMES,
        "roi_x_y_width_height": ROI,
        "object_um_per_px": OBJECT_UM_PER_PX,
        "scale_note": "20260702 100MG x_1um treated as 50x, 0.069 um/px; the package case_manifest has older 20x-assumed expected_px metadata.",
        "nominal_step_um": NOMINAL_STEP_UM,
        "expected_signed_dx_px": EXPECTED_SIGNED_DX_PX,
        "image_count_per_case": len(first_names),
        "step_count_per_case": len(first_names) - 1,
        "output_dir": str(OUT),
        "common_stable_step_count": len(common_steps),
        "common_stable_steps": sorted(common_steps),
    }
    write_json(OUT / "boundary_projection_manifest.json", run_manifest)
    print(json.dumps(run_manifest, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()

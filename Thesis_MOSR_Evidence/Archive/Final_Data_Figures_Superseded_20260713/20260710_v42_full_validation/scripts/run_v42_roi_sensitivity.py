from __future__ import annotations

import argparse
import json
import sys
from collections import OrderedDict
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from PIL import Image, ImageDraw, ImageFont
PROJECT_ROOT = Path(__file__).resolve().parents[5]


ROOT = Path(str(PROJECT_ROOT / 'Thesis_MOSR_Evidence'))
PACKAGE_ROOT = ROOT / "Final_Data_Figures" / "20260710_v42_full_validation"
SOURCE_ALL = PACKAGE_ROOT / "boundary_sensitive_roi" / "tables" / "all_steps.csv"
SOURCE_SELECTED = PACKAGE_ROOT / "boundary_sensitive_roi" / "tables" / "selected_steps.csv"
OUT_ROOT = PACKAGE_ROOT / "roi_sensitivity_revalidation"
TABLE_DIR = OUT_ROOT / "tables"
VIS_DIR = OUT_ROOT / "visual_audit"
TRACE_DIR = OUT_ROOT / "step_traces"
SUMMARY_FIG_DIR = OUT_ROOT / "summary_figures"

CORE_DIR = (
    ROOT
    / "Final_Data_Figures"
    / "20260708_v41_standalone_full_validation"
    / "local_edge_band_optimized_anti_mismatch"
    / "scripts"
)
sys.path.insert(0, str(CORE_DIR))

from local_edge_band_core import (  # noqa: E402
    choose_vertical_edge_centers,
    measure_pair_local_edge_displacement,
    normalize_image,
    row_weighted_profile,
)
from run_v42_local_edge_validation import (  # noqa: E402
    CASES,
    CASE_LABEL,
    select_case_symmetric_steps,
    total_uncertainty_nm,
)


CASE_COLOR = {
    "raw": "#69737d",
    "v41_standalone": "#d96b00",
    "v42_e120": "#12866f",
}
ROI_COLOR = {
    "legacy_cross": "#d1495b",
    "clean_pillar_grid": "#2878b5",
    "clean_vertical_lines": "#d9a521",
    "clean_outer_grid": "#2878b5",
    "clean_center_microgrid": "#d9a521",
}
ROI_LABEL = {
    "legacy_cross": "A Legacy cross-pattern ROI",
    "clean_pillar_grid": "B Clean pillar-grid ROI",
    "clean_vertical_lines": "C Clean vertical-line ROI",
    "clean_outer_grid": "B Clean outer-grid ROI",
    "clean_center_microgrid": "C Clean center micro-grid ROI",
}
FULL_IMAGE_CACHE: OrderedDict[str, np.ndarray] = OrderedDict()
MAX_CACHE_IMAGES = 8


def build_roi_catalog(
    group: str,
    legacy_roi: tuple[int, int, int, int],
    image_size: tuple[int, int],
) -> dict[str, tuple[int, int, int, int]]:
    if group.startswith("x_"):
        catalog = {
            "legacy_cross": legacy_roi,
            "clean_pillar_grid": (1050, 90, 700, 560),
            "clean_vertical_lines": (100, 90, 700, 560),
        }
    elif group.startswith("20x_"):
        catalog = {
            "legacy_cross": legacy_roi,
            "clean_pillar_grid": (520, 100, 650, 540),
            "clean_vertical_lines": (520, 880, 620, 450),
        }
    elif group.startswith("5x_"):
        catalog = {
            "legacy_cross": legacy_roi,
            "clean_outer_grid": (1280, 120, 480, 300),
            "clean_center_microgrid": (1320, 850, 300, 280),
        }
    else:
        raise ValueError(f"unknown group: {group}")

    image_width, image_height = image_size
    for name, (x, y, width, height) in catalog.items():
        if x < 0 or y < 0 or width <= 0 or height <= 0:
            raise ValueError(f"invalid ROI {name}: {catalog[name]}")
        if x + width > image_width or y + height > image_height:
            raise ValueError(f"ROI {name} exceeds image bounds: {catalog[name]}")
    return catalog


def classify_roi_sensitivity(improvement_values: list[float]) -> str:
    values = np.asarray(improvement_values, dtype=np.float64)
    finite = values[np.isfinite(values)]
    if len(finite) == 0:
        return "failed"
    if len(finite) != len(values):
        return "incomplete"
    if np.all(finite > 0):
        return "robust_improvement"
    if np.all(finite < 0):
        return "robust_degradation"
    return "roi_sensitive"


def error_aware_total_nm(step_rmse_nm: float, localization_nm: float) -> float:
    return float(np.hypot(float(step_rmse_nm), float(localization_nm)))


def is_search_boundary_saturated(
    signed_dx_px: float,
    expected_signed_dx_px: float,
    tolerance_px: float = 0.015,
) -> bool:
    if not np.isfinite(signed_dx_px) or not np.isfinite(expected_signed_dx_px):
        return False
    shift_tolerance = max(
        0.75,
        min(2.35, abs(float(expected_signed_dx_px)) * 0.20 + 0.45),
    )
    profile_search_radius = max(0.75, min(1.45, shift_tolerance))
    distance_from_expected = abs(float(signed_dx_px) - float(expected_signed_dx_px))
    return abs(distance_from_expected - profile_search_radius) <= tolerance_px


def add_analysis_validity_flags(rows: pd.DataFrame) -> pd.DataFrame:
    output = rows.copy()
    output["ok"] = output.ok.astype(str).str.lower().eq("true")
    output["search_boundary_saturated"] = [
        is_search_boundary_saturated(signed, expected)
        for signed, expected in zip(output.signed_dx_px, output.expected_signed_dx_px)
    ]
    output["analysis_valid"] = output.ok & ~output.search_boundary_saturated
    return output


def enforce_common_analysis_validity(rows: pd.DataFrame) -> pd.DataFrame:
    output = rows.copy()
    key_cols = ["selection", "dataset", "group", "roi_name", "step_index"]
    output["common_analysis_valid"] = output.groupby(key_cols)["analysis_valid"].transform(
        lambda values: len(values) == len(CASES) and bool(values.all())
    )
    return output


def ensure_dirs() -> None:
    for folder in [TABLE_DIR, VIS_DIR, TRACE_DIR, SUMMARY_FIG_DIR]:
        folder.mkdir(parents=True, exist_ok=True)


def to_uint8(image: np.ndarray) -> np.ndarray:
    arr = np.asarray(image, dtype=np.float64)
    lo, hi = np.nanpercentile(arr, [1.0, 99.0])
    if not np.isfinite(lo) or not np.isfinite(hi) or hi <= lo:
        return np.zeros(arr.shape, dtype=np.uint8)
    return np.clip((arr - lo) / (hi - lo) * 255.0, 0, 255).astype(np.uint8)


def read_full_image(path: Path) -> np.ndarray:
    key = str(path)
    cached = FULL_IMAGE_CACHE.get(key)
    if cached is not None:
        FULL_IMAGE_CACHE.move_to_end(key)
        return cached
    with Image.open(path) as img:
        arr = np.asarray(img.convert("F"), dtype=np.float32)
    FULL_IMAGE_CACHE[key] = arr
    FULL_IMAGE_CACHE.move_to_end(key)
    while len(FULL_IMAGE_CACHE) > MAX_CACHE_IMAGES:
        FULL_IMAGE_CACHE.popitem(last=False)
    return arr


def crop_array(image: np.ndarray, roi: tuple[int, int, int, int]) -> np.ndarray:
    x, y, width, height = roi
    return np.asarray(image[y : y + height, x : x + width], dtype=np.float64)


def load_source_rows() -> pd.DataFrame:
    rows = pd.read_csv(SOURCE_ALL)
    rows = rows[rows.case.isin(CASES)].copy()
    rows["step_index"] = pd.to_numeric(rows.step_index, errors="raise").astype(int)
    rows = select_case_symmetric_steps(rows, CASES, chosen_keys=None)
    return rows.sort_values(["dataset", "group", "step_index", "case"])


def first_rows_by_group(rows: pd.DataFrame) -> dict[tuple[str, str], dict[str, pd.Series]]:
    output: dict[tuple[str, str], dict[str, pd.Series]] = {}
    for (dataset, group), part in rows.groupby(["dataset", "group"], sort=False):
        first_step = int(part.step_index.min())
        step_rows = part[part.step_index == first_step]
        output[(str(dataset), str(group))] = {
            str(row.case): row for _, row in step_rows.iterrows()
        }
    return output


def image_path(row: pd.Series, frame_field: str) -> Path:
    return Path(str(row.input_dir)) / str(row[frame_field])


def get_legacy_roi(row: pd.Series) -> tuple[int, int, int, int]:
    return (
        int(row.roi_x),
        int(row.roi_y),
        int(row.roi_width),
        int(row.roi_height),
    )


def draw_full_overlay(
    image: np.ndarray,
    catalog: dict[str, tuple[int, int, int, int]],
    title: str,
    output_path: Path,
) -> None:
    canvas = Image.fromarray(to_uint8(image), mode="L").convert("RGB")
    draw = ImageDraw.Draw(canvas)
    font = ImageFont.load_default(size=18)
    for roi_name, (x, y, width, height) in catalog.items():
        color = ROI_COLOR[roi_name]
        draw.rectangle((x, y, x + width, y + height), outline=color, width=6)
        label = ROI_LABEL[roi_name]
        box = draw.textbbox((x + 5, y + 5), label, font=font)
        draw.rectangle(box, fill="white")
        draw.text((x + 5, y + 5), label, fill=color, font=font)
    title_font = ImageFont.load_default(size=22)
    title_box = draw.textbbox((15, 15), title, font=title_font)
    draw.rectangle(title_box, fill="white")
    draw.text((15, 15), title, fill="black", font=title_font)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(output_path)


def save_crop_image(image: np.ndarray, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(to_uint8(image), mode="L").save(output_path)


def plot_crop_comparison(
    crops: dict[str, np.ndarray],
    title: str,
    output_path: Path,
) -> None:
    fig, axes = plt.subplots(1, 3, figsize=(13.2, 4.4), dpi=170)
    for ax, case in zip(axes, CASES):
        ax.imshow(crops[case], cmap="gray", vmin=np.percentile(crops[case], 1), vmax=np.percentile(crops[case], 99))
        ax.set_title(CASE_LABEL[case])
        ax.set_axis_off()
    fig.suptitle(title, fontsize=13)
    fig.tight_layout()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, facecolor="white", transparent=False, bbox_inches="tight")
    plt.close(fig)


def choose_shared_centers(v41_ref_crop: np.ndarray, expected_signed_dx_px: float) -> tuple[int, ...]:
    centers = choose_vertical_edge_centers(
        normalize_image(v41_ref_crop),
        expected_signed_dx_px=expected_signed_dx_px,
        max_edges=12,
    )
    return tuple(int(center) for center in centers)


def plot_edge_overlay(
    v41_ref: np.ndarray,
    candidate_centers: tuple[int, ...],
    usable_positions: tuple[float, ...],
    title: str,
    output_path: Path,
) -> None:
    fig, ax = plt.subplots(figsize=(8.0, 5.8), dpi=180)
    ax.imshow(v41_ref, cmap="gray", vmin=np.percentile(v41_ref, 1), vmax=np.percentile(v41_ref, 99))
    for index, center in enumerate(candidate_centers):
        ax.axvline(center, color="#d9a521", linestyle="--", linewidth=1.0, alpha=0.75)
        ax.text(center + 2, 18, str(index + 1), color="#7a5700", fontsize=7, rotation=90, va="top")
    for position in usable_positions:
        ax.axvline(position, color="#0072b2", linewidth=2.0, alpha=0.9)
    ax.set_title(title)
    ax.set_xlabel("Horizontal position inside ROI (pixel)")
    ax.set_ylabel("Vertical position inside ROI (pixel)")
    ax.plot([], [], color="#d9a521", linestyle="--", label="Candidate edge")
    ax.plot([], [], color="#0072b2", linewidth=2, label="Used edge")
    ax.legend(frameon=True, loc="lower right")
    fig.tight_layout()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, facecolor="white", transparent=False, bbox_inches="tight")
    plt.close(fig)


def plot_representative_pair(
    images: dict[str, tuple[np.ndarray, np.ndarray]],
    centers: tuple[int, ...],
    expected_signed_dx_px: float,
    title: str,
    output_path: Path,
) -> None:
    fig, axes = plt.subplots(3, 2, figsize=(10.5, 10.5), dpi=160)
    for row_index, case in enumerate(CASES):
        ref, mov = images[case]
        for col_index, (frame, frame_title) in enumerate([(ref, "Reference"), (mov, "Next frame")]):
            ax = axes[row_index, col_index]
            ax.imshow(frame, cmap="gray", vmin=np.percentile(frame, 1), vmax=np.percentile(frame, 99))
            offset = 0.0 if col_index == 0 else expected_signed_dx_px
            for center in centers:
                ax.axvline(center + offset, color="#d9a521", linewidth=1.0, alpha=0.75)
            ax.set_title(f"{CASE_LABEL[case]} - {frame_title}")
            ax.set_axis_off()
    fig.suptitle(f"{title}\nGold lines show the same shared edges; next-frame lines include expected motion")
    fig.tight_layout()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, facecolor="white", transparent=False, bbox_inches="tight")
    plt.close(fig)


def plot_edge_profile_process(
    reference_crops: dict[str, np.ndarray],
    centers: tuple[int, ...],
    title: str,
    output_path: Path,
) -> None:
    if not centers:
        return
    center = int(centers[len(centers) // 2])
    half_window = 18
    fig, axes = plt.subplots(1, 2, figsize=(11.5, 4.5), dpi=175)
    for case in CASES:
        normalized = normalize_image(reference_crops[case])
        profile, _ = row_weighted_profile(normalized, center, band_half_width_px=6)
        lo = max(1, center - half_window)
        hi = min(len(profile) - 1, center + half_window + 1)
        x = np.arange(lo, hi) - center
        local = profile[lo:hi]
        local_lo, local_hi = np.nanmin(local), np.nanmax(local)
        scaled = (local - local_lo) / max(local_hi - local_lo, 1e-12)
        gradient = np.abs(np.gradient(scaled))
        axes[0].plot(x, scaled, label=CASE_LABEL[case], color=CASE_COLOR[case], linewidth=1.8)
        axes[1].plot(x, gradient, label=CASE_LABEL[case], color=CASE_COLOR[case], linewidth=1.8)
    axes[0].set_title("Normalized intensity across one shared edge")
    axes[0].set_ylabel("Local normalized intensity")
    axes[1].set_title("Absolute edge slope")
    axes[1].set_ylabel("Absolute intensity gradient")
    for ax in axes:
        ax.axvline(0, color="black", linestyle="--", linewidth=1.0)
        ax.set_xlabel("Position relative to shared edge (pixel)")
        ax.grid(alpha=0.25)
    axes[0].legend(frameon=False)
    fig.suptitle(title)
    fig.tight_layout()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, facecolor="white", transparent=False, bbox_inches="tight")
    plt.close(fig)


def export_visual_audit(rows: pd.DataFrame) -> pd.DataFrame:
    catalog_rows: list[dict[str, object]] = []
    groups = first_rows_by_group(rows)
    for (dataset, group), by_case in groups.items():
        raw_row = by_case["raw"]
        raw_ref_path = image_path(raw_row, "ref_frame")
        raw_image = read_full_image(raw_ref_path)
        image_size = (int(raw_image.shape[1]), int(raw_image.shape[0]))
        catalog = build_roi_catalog(group, get_legacy_roi(raw_row), image_size)
        group_dir = VIS_DIR / f"{dataset}_{group}"

        for roi_name, roi in catalog.items():
            catalog_rows.append(
                {
                    "dataset": dataset,
                    "group": group,
                    "roi_name": roi_name,
                    "roi_label": ROI_LABEL[roi_name],
                    "roi_x": roi[0],
                    "roi_y": roi[1],
                    "roi_width": roi[2],
                    "roi_height": roi[3],
                }
            )

        reference_crops: dict[str, dict[str, np.ndarray]] = {name: {} for name in catalog}
        for case in CASES:
            row = by_case[case]
            ref = read_full_image(image_path(row, "ref_frame"))
            draw_full_overlay(
                ref,
                catalog,
                f"{dataset} / {group} / {CASE_LABEL[case]}",
                group_dir / "01_full_frame_overlays" / f"{case}_roi_overlay.png",
            )
            for roi_name, roi in catalog.items():
                crop = crop_array(ref, roi)
                reference_crops[roi_name][case] = crop
                save_crop_image(
                    crop,
                    group_dir / "02_individual_roi_crops" / roi_name / f"{case}_reference.png",
                )

        for roi_name, roi in catalog.items():
            plot_crop_comparison(
                reference_crops[roi_name],
                f"{dataset} / {group} / {ROI_LABEL[roi_name]}",
                group_dir / "03_roi_case_comparisons" / f"{roi_name}_raw_v41_v42.png",
            )
            expected = float(raw_row.expected_signed_dx_px)
            centers = choose_shared_centers(reference_crops[roi_name]["v41_standalone"], expected)
            pair_images: dict[str, tuple[np.ndarray, np.ndarray]] = {}
            for case in CASES:
                row = by_case[case]
                pair_images[case] = (
                    crop_array(read_full_image(image_path(row, "ref_frame")), roi),
                    crop_array(read_full_image(image_path(row, "frame")), roi),
                )
            first_measurement = measure_pair_local_edge_displacement(
                pair_images["v41_standalone"][0],
                pair_images["v41_standalone"][1],
                expected_signed_dx_px=expected,
                roi=(0, 0, roi[2], roi[3]),
                max_edges=12,
                min_edges=3,
                band_half_width_px=6,
                edge_search_radius_px=8,
                edge_centers=centers,
            )
            plot_edge_overlay(
                pair_images["v41_standalone"][0],
                centers,
                first_measurement.edge_positions_px,
                f"{dataset} / {group} / {ROI_LABEL[roi_name]}\nFrozen-V41 shared edge selection",
                group_dir / "04_edge_selection" / f"{roi_name}_edge_overlay.png",
            )
            plot_representative_pair(
                pair_images,
                centers,
                expected,
                f"{dataset} / {group} / {ROI_LABEL[roi_name]}",
                group_dir / "05_reference_next_pair" / f"{roi_name}_pair_process.png",
            )
            plot_edge_profile_process(
                reference_crops[roi_name],
                centers,
                f"{dataset} / {group} / {ROI_LABEL[roi_name]}",
                group_dir / "06_edge_profiles" / f"{roi_name}_edge_profile.png",
            )
    catalog_df = pd.DataFrame(catalog_rows)
    catalog_df.to_csv(TABLE_DIR / "roi_catalog.csv", index=False, encoding="utf-8-sig")
    return catalog_df


def measurement_row(
    row: pd.Series,
    roi_name: str,
    roi: tuple[int, int, int, int],
    centers: tuple[int, ...],
    ref_crop: np.ndarray,
    mov_crop: np.ndarray,
) -> dict[str, object]:
    base = {
        "dataset": row.dataset,
        "group": row.group,
        "case": row.case,
        "case_label": CASE_LABEL[str(row.case)],
        "step_index": int(row.step_index),
        "ref_frame": row.ref_frame,
        "frame": row.frame,
        "input_dir": row.input_dir,
        "roi_name": roi_name,
        "roi_label": ROI_LABEL[roi_name],
        "roi_x": roi[0],
        "roi_y": roi[1],
        "roi_width": roi[2],
        "roi_height": roi[3],
        "object_um_per_px": float(row.object_um_per_px),
        "nominal_step_um": float(row.nominal_step_um),
        "expected_signed_dx_px": float(row.expected_signed_dx_px),
        "candidate_edge_centers_px": ";".join(str(value) for value in centers),
    }
    try:
        measurement = measure_pair_local_edge_displacement(
            ref_crop,
            mov_crop,
            expected_signed_dx_px=float(row.expected_signed_dx_px),
            roi=(0, 0, roi[2], roi[3]),
            max_edges=12,
            min_edges=3,
            band_half_width_px=6,
            edge_search_radius_px=8,
            edge_centers=centers,
        )
        scale = float(row.object_um_per_px)
        x_step_um = abs(float(measurement.signed_dx_px)) * scale
        base.update(
            {
                "ok": bool(np.isfinite(measurement.signed_dx_px)),
                "signed_dx_px": float(measurement.signed_dx_px),
                "x_step_um": x_step_um,
                "abs_error_um": abs(x_step_um - float(row.nominal_step_um)),
                "usable_edges": int(measurement.usable_edges),
                "candidate_edges": int(measurement.candidate_edges),
                "rejected_edges": int(measurement.rejected_edges),
                "ambiguity_score": float(measurement.ambiguity_score),
                "consensus_mad_px": float(measurement.consensus_mad_px),
                "boundary_confidence": float(measurement.boundary_confidence),
                "localization_uncertainty_px": float(measurement.localization_uncertainty_px),
                "localization_uncertainty_nm": float(
                    measurement.localization_uncertainty_px * scale * 1000.0
                ),
                "edge_shift_mad_nm": float(measurement.consensus_mad_px * scale * 1000.0),
                "used_edge_positions_px": ";".join(
                    f"{value:.4f}" for value in measurement.edge_positions_px
                ),
                "error": "",
            }
        )
        base["search_boundary_saturated"] = is_search_boundary_saturated(
            float(measurement.signed_dx_px), float(row.expected_signed_dx_px)
        )
        base["analysis_valid"] = bool(base["ok"] and not base["search_boundary_saturated"])
    except Exception as exc:
        base.update(
            {
                "ok": False,
                "signed_dx_px": np.nan,
                "x_step_um": np.nan,
                "abs_error_um": np.nan,
                "usable_edges": 0,
                "candidate_edges": len(centers),
                "rejected_edges": len(centers),
                "ambiguity_score": np.inf,
                "consensus_mad_px": np.inf,
                "boundary_confidence": 0.0,
                "localization_uncertainty_px": np.inf,
                "localization_uncertainty_nm": np.inf,
                "edge_shift_mad_nm": np.nan,
                "used_edge_positions_px": "",
                "error": repr(exc),
                "search_boundary_saturated": False,
                "analysis_valid": False,
            }
        )
    return base


def measure_all_rois(rows: pd.DataFrame) -> pd.DataFrame:
    results: list[dict[str, object]] = []
    key_cols = ["dataset", "group", "step_index"]
    grouped_steps = list(rows.groupby(key_cols, sort=False))
    total = len(grouped_steps)
    partial_path = TABLE_DIR / "all_steps_roi_measurements_partial.csv"
    for step_number, (key, step_rows) in enumerate(grouped_steps, start=1):
        if step_number == 1 or step_number % 10 == 0 or step_number == total:
            print(f"ROI sensitivity: {step_number}/{total} {key[0]}/{key[1]}", flush=True)
        by_case = {str(row.case): row for _, row in step_rows.iterrows()}
        raw_row = by_case["raw"]
        raw_ref = read_full_image(image_path(raw_row, "ref_frame"))
        catalog = build_roi_catalog(
            str(raw_row.group),
            get_legacy_roi(raw_row),
            image_size=(raw_ref.shape[1], raw_ref.shape[0]),
        )
        full_pairs: dict[str, tuple[np.ndarray, np.ndarray]] = {}
        for case in CASES:
            row = by_case[case]
            full_pairs[case] = (
                read_full_image(image_path(row, "ref_frame")),
                read_full_image(image_path(row, "frame")),
            )
        for roi_name, roi in catalog.items():
            cropped_pairs = {
                case: (crop_array(pair[0], roi), crop_array(pair[1], roi))
                for case, pair in full_pairs.items()
            }
            centers = choose_shared_centers(
                cropped_pairs["v41_standalone"][0],
                float(raw_row.expected_signed_dx_px),
            )
            for case in CASES:
                row = by_case[case]
                ref_crop, mov_crop = cropped_pairs[case]
                results.append(
                    measurement_row(row, roi_name, roi, centers, ref_crop, mov_crop)
                )
        if step_number % 10 == 0 or step_number == total:
            pd.DataFrame(results).to_csv(partial_path, index=False, encoding="utf-8-sig")
    output = pd.DataFrame(results)
    output.to_csv(TABLE_DIR / "all_steps_roi_measurements.csv", index=False, encoding="utf-8-sig")
    return output


def attach_selections(measurements: pd.DataFrame) -> pd.DataFrame:
    measurements = add_analysis_validity_flags(measurements)
    selected_source = pd.read_csv(SOURCE_SELECTED)
    outputs: list[pd.DataFrame] = []
    for selection in ["all_steps", "common_best30"]:
        chosen = None
        if selection == "common_best30":
            chosen = selected_source[selected_source.selection == selection][
                ["dataset", "group", "step_index"]
            ].drop_duplicates()
        for roi_name, roi_rows in measurements.groupby("roi_name", sort=False):
            part = select_case_symmetric_steps(roi_rows, CASES, chosen)
            part["selection"] = selection
            outputs.append(part)
    return enforce_common_analysis_validity(pd.concat(outputs, ignore_index=True))


def summarize(measurements: pd.DataFrame) -> pd.DataFrame:
    group_cols = ["selection", "dataset", "group", "roi_name", "roi_label", "case", "case_label"]
    rows: list[dict[str, object]] = []
    for keys, part in measurements.groupby(group_cols, sort=False):
        valid = part[part.common_analysis_valid.astype(str).str.lower().eq("true")].copy()
        finite_unc = valid.localization_uncertainty_nm.replace([np.inf, -np.inf], np.nan)
        step_sd = float(valid.x_step_um.std(ddof=1) * 1000.0)
        localization = float(finite_unc.median())
        nominal_step_um = float(part.nominal_step_um.median())
        step_errors_um = valid.x_step_um - nominal_step_um
        mean_bias_nm = float(step_errors_um.mean() * 1000.0)
        rmse_step_error_nm = float(np.sqrt(np.mean(np.square(step_errors_um))) * 1000.0)
        rows.append(
            {
                **dict(zip(group_cols, keys)),
                "n_requested": int(len(part)),
                "n_valid": int(len(valid)),
                "valid_rate_pct": float(len(valid) / max(len(part), 1) * 100.0),
                "nominal_step_um": nominal_step_um,
                "std_step_nm": step_sd,
                "median_step_nm": float(valid.x_step_um.median() * 1000.0),
                "median_abs_error_nm": float(valid.abs_error_um.median() * 1000.0),
                "mean_bias_nm": mean_bias_nm,
                "rmse_step_error_nm": rmse_step_error_nm,
                "median_localization_uncertainty_nm": localization,
                "total_uncertainty_nm": total_uncertainty_nm(step_sd, localization),
                "error_aware_total_nm": error_aware_total_nm(rmse_step_error_nm, localization),
                "median_boundary_confidence": float(valid.boundary_confidence.median()),
                "median_usable_edges": float(valid.usable_edges.median()),
                "median_ambiguity_score": float(
                    valid.ambiguity_score.replace([np.inf, -np.inf], np.nan).median()
                ),
            }
        )
    return pd.DataFrame(rows)


def improvement_pct(raw_value: float, model_value: float) -> float:
    if not np.isfinite(raw_value) or raw_value == 0:
        return float("nan")
    return float((raw_value - model_value) / raw_value * 100.0)


def build_comparison(summary: pd.DataFrame) -> pd.DataFrame:
    keys = ["selection", "dataset", "group", "roi_name", "roi_label"]
    indexed = {case: summary[summary.case == case].set_index(keys) for case in CASES}
    rows: list[dict[str, object]] = []
    for key in indexed["v42_e120"].index:
        if not all(key in indexed[case].index for case in CASES):
            continue
        raw = indexed["raw"].loc[key]
        v41 = indexed["v41_standalone"].loc[key]
        v42 = indexed["v42_e120"].loc[key]
        result: dict[str, object] = {
            "selection": key[0],
            "dataset": key[1],
            "group": key[2],
            "roi_name": key[3],
            "roi_label": key[4],
            "nominal_step_um": float(v42.nominal_step_um),
        }
        for metric in [
            "n_valid",
            "std_step_nm",
            "median_abs_error_nm",
            "mean_bias_nm",
            "rmse_step_error_nm",
            "median_localization_uncertainty_nm",
            "total_uncertainty_nm",
            "error_aware_total_nm",
            "median_boundary_confidence",
            "median_usable_edges",
            "median_ambiguity_score",
        ]:
            result[f"raw_{metric}"] = float(raw[metric])
            result[f"v41_{metric}"] = float(v41[metric])
            result[f"v42_{metric}"] = float(v42[metric])
        for metric in [
            "std_step_nm",
            "rmse_step_error_nm",
            "median_localization_uncertainty_nm",
            "total_uncertainty_nm",
            "error_aware_total_nm",
        ]:
            result[f"v42_{metric}_improvement_vs_raw_pct"] = improvement_pct(
                float(raw[metric]), float(v42[metric])
            )
        rows.append(result)
    return pd.DataFrame(rows)


def build_sensitivity_table(comparison: pd.DataFrame) -> pd.DataFrame:
    part = comparison[comparison.selection == "common_best30"].copy()
    rows: list[dict[str, object]] = []
    for (dataset, group), group_rows in part.groupby(["dataset", "group"], sort=False):
        total_values = group_rows.v42_total_uncertainty_nm_improvement_vs_raw_pct.tolist()
        error_aware_values = (
            group_rows.v42_error_aware_total_nm_improvement_vs_raw_pct.tolist()
        )
        sd_values = group_rows.v42_std_step_nm_improvement_vs_raw_pct.tolist()
        rows.append(
            {
                "dataset": dataset,
                "group": group,
                "roi_count": int(len(group_rows)),
                "total_uncertainty_status": classify_roi_sensitivity(total_values),
                "error_aware_status": classify_roi_sensitivity(error_aware_values),
                "step_sd_status": classify_roi_sensitivity(sd_values),
                "total_improvement_min_pct": float(np.nanmin(total_values)),
                "total_improvement_median_pct": float(np.nanmedian(total_values)),
                "total_improvement_max_pct": float(np.nanmax(total_values)),
                "error_aware_improvement_min_pct": float(np.nanmin(error_aware_values)),
                "error_aware_improvement_median_pct": float(np.nanmedian(error_aware_values)),
                "error_aware_improvement_max_pct": float(np.nanmax(error_aware_values)),
                "step_sd_improvement_min_pct": float(np.nanmin(sd_values)),
                "step_sd_improvement_median_pct": float(np.nanmedian(sd_values)),
                "step_sd_improvement_max_pct": float(np.nanmax(sd_values)),
            }
        )
    return pd.DataFrame(rows)


def build_cross_roi_consistency(
    measurements: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    part = measurements[
        (measurements.selection == "common_best30")
        & measurements.common_analysis_valid.astype(str).str.lower().eq("true")
    ].copy()
    detail_rows: list[dict[str, object]] = []
    for (dataset, group, case, step_index), step_rows in part.groupby(
        ["dataset", "group", "case", "step_index"], sort=False
    ):
        if len(step_rows) < 2:
            continue
        detail_rows.append(
            {
                "dataset": dataset,
                "group": group,
                "case": case,
                "case_label": CASE_LABEL[str(case)],
                "step_index": int(step_index),
                "roi_count": int(len(step_rows)),
                "cross_roi_sd_nm": float(step_rows.x_step_um.std(ddof=1) * 1000.0),
                "cross_roi_range_nm": float(
                    (step_rows.x_step_um.max() - step_rows.x_step_um.min()) * 1000.0
                ),
            }
        )
    detail = pd.DataFrame(detail_rows)
    summary_rows: list[dict[str, object]] = []
    for (dataset, group, case), case_rows in detail.groupby(
        ["dataset", "group", "case"], sort=False
    ):
        summary_rows.append(
            {
                "dataset": dataset,
                "group": group,
                "case": case,
                "n_steps": int(len(case_rows)),
                "roi_count_min": int(case_rows.roi_count.min()),
                "roi_count_max": int(case_rows.roi_count.max()),
                "median_cross_roi_sd_nm": float(case_rows.cross_roi_sd_nm.median()),
                "mean_cross_roi_sd_nm": float(case_rows.cross_roi_sd_nm.mean()),
                "median_cross_roi_range_nm": float(case_rows.cross_roi_range_nm.median()),
            }
        )
    summary = pd.DataFrame(summary_rows)
    comparison_rows: list[dict[str, object]] = []
    for (dataset, group), group_rows in summary.groupby(["dataset", "group"], sort=False):
        by_case = group_rows.set_index("case")
        if not all(case in by_case.index for case in CASES):
            continue
        raw = float(by_case.loc["raw", "median_cross_roi_sd_nm"])
        v41 = float(by_case.loc["v41_standalone", "median_cross_roi_sd_nm"])
        v42 = float(by_case.loc["v42_e120", "median_cross_roi_sd_nm"])
        comparison_rows.append(
            {
                "dataset": dataset,
                "group": group,
                "n_steps": int(by_case.loc["v42_e120", "n_steps"]),
                "roi_count_min": int(by_case.loc["v42_e120", "roi_count_min"]),
                "roi_count_max": int(by_case.loc["v42_e120", "roi_count_max"]),
                "raw_median_cross_roi_sd_nm": raw,
                "v41_median_cross_roi_sd_nm": v41,
                "v42_median_cross_roi_sd_nm": v42,
                "v42_improvement_vs_raw_pct": improvement_pct(raw, v42),
            }
        )
    return detail, pd.DataFrame(comparison_rows)


def plot_cross_roi_consistency(comparison: pd.DataFrame) -> None:
    fig, ax = plt.subplots(figsize=(10.5, 5.0), dpi=175)
    x = np.arange(len(comparison))
    width = 0.24
    for offset, column, label, color in [
        (-width, "raw_median_cross_roi_sd_nm", "Raw", CASE_COLOR["raw"]),
        (0.0, "v41_median_cross_roi_sd_nm", "V41", CASE_COLOR["v41_standalone"]),
        (width, "v42_median_cross_roi_sd_nm", "V42 E120", CASE_COLOR["v42_e120"]),
    ]:
        ax.bar(x + offset, comparison[column], width=width, label=label, color=color)
    ax.set_xticks(x, comparison.group, rotation=18, ha="right")
    ax.set_ylabel("Median within-step SD across ROIs (nm)")
    ax.set_title("Cross-structure displacement agreement")
    ax.grid(axis="y", alpha=0.25)
    ax.legend(frameon=False)
    fig.tight_layout()
    fig.savefig(
        SUMMARY_FIG_DIR / "cross_roi_structure_consistency.png",
        facecolor="white",
        transparent=False,
        bbox_inches="tight",
    )
    plt.close(fig)


def plot_step_traces(measurements: pd.DataFrame) -> None:
    part = measurements[measurements.selection == "common_best30"].copy()
    for (dataset, group), group_rows in part.groupby(["dataset", "group"], sort=False):
        roi_names = group_rows.roi_name.drop_duplicates().tolist()
        fig, axes = plt.subplots(len(roi_names), 1, figsize=(12.0, 3.3 * len(roi_names)), dpi=170)
        axes = np.atleast_1d(axes)
        nominal = float(group_rows.nominal_step_um.median())
        for ax, roi_name in zip(axes, roi_names):
            roi_rows = group_rows[group_rows.roi_name == roi_name]
            for case in CASES:
                case_rows = roi_rows[roi_rows.case == case].sort_values("step_index")
                valid_mask = case_rows.common_analysis_valid.astype(str).str.lower().eq("true")
                trace_values = case_rows.x_step_um.where(valid_mask, np.nan)
                ax.plot(
                    case_rows.step_index,
                    trace_values,
                    marker="o",
                    markersize=3,
                    linewidth=1.2,
                    label=CASE_LABEL[case],
                    color=CASE_COLOR[case],
                )
                rejected = case_rows[~valid_mask & case_rows.x_step_um.notna()]
                if not rejected.empty:
                    ax.scatter(
                        rejected.step_index,
                        rejected.x_step_um,
                        marker="x",
                        s=34,
                        linewidths=1.5,
                        color="#9c2f2f",
                        label="Rejected search-boundary result" if case == "raw" else None,
                    )
            ax.axhline(nominal, color="black", linestyle="--", linewidth=1.0, label="Nominal")
            ax.set_title(ROI_LABEL[roi_name])
            ax.set_ylabel("Measured step (um)")
            ax.grid(alpha=0.25)
        axes[-1].set_xlabel("Acquisition step index")
        axes[0].legend(ncol=4, frameon=False, loc="upper center")
        fig.suptitle(f"{dataset} / {group} - identical common-best-30 frame pairs")
        fig.tight_layout()
        fig.savefig(
            TRACE_DIR / f"{dataset}_{group}_common30_step_traces.png",
            facecolor="white",
            transparent=False,
            bbox_inches="tight",
        )
        plt.close(fig)


def plot_sensitivity_matrix(comparison: pd.DataFrame, metric: str, output_name: str, title: str) -> None:
    part = comparison[comparison.selection == "common_best30"].copy()
    part["roi_slot"] = part.roi_label.str.slice(0, 1)
    pivot = part.pivot(index="group", columns="roi_slot", values=metric)
    group_order = ["x_0p5um", "x_1um", "20x_0p5um", "20x_1um", "5x_0p5um", "5x_1um"]
    pivot = pivot.reindex([group for group in group_order if group in pivot.index])
    pivot = pivot.reindex(columns=["A", "B", "C"])
    values = pivot.to_numpy(dtype=float)
    limit = max(10.0, float(np.nanpercentile(np.abs(values), 90)))
    fig, ax = plt.subplots(figsize=(10.8, 5.7), dpi=180)
    cmap = plt.get_cmap("RdBu").copy()
    cmap.set_bad("#eeeeee")
    image = ax.imshow(
        np.ma.masked_invalid(values), cmap=cmap, vmin=-limit, vmax=limit, aspect="auto"
    )
    for row in range(values.shape[0]):
        for col in range(values.shape[1]):
            value = values[row, col]
            label = "FAIL" if not np.isfinite(value) else f"{value:+.1f}%"
            ax.text(col, row, label, ha="center", va="center", color="black", fontsize=9)
    ax.set_xticks(
        np.arange(3),
        ["A Original cross-pattern", "B Alternative clean structure", "C Independent clean structure"],
        rotation=12,
        ha="right",
    )
    ax.set_yticks(np.arange(len(pivot.index)), pivot.index)
    ax.set_title(title)
    ax.set_xlabel("Region of interest")
    ax.set_ylabel("Dataset")
    colorbar = fig.colorbar(image, ax=ax)
    colorbar.set_label("V42 improvement versus Raw (%)")
    fig.tight_layout()
    fig.savefig(SUMMARY_FIG_DIR / output_name, facecolor="white", transparent=False, bbox_inches="tight")
    plt.close(fig)


def write_visual_index(catalog: pd.DataFrame) -> None:
    lines = [
        "# ROI visual audit index",
        "",
        "Each dataset folder follows the same sequence:",
        "",
        "1. `01_full_frame_overlays`: the exact three ROI rectangles on Raw, V41, and V42.",
        "2. `02_individual_roi_crops`: individual reference crops used by the detector.",
        "3. `03_roi_case_comparisons`: Raw/V41/V42 crop comparison.",
        "4. `04_edge_selection`: candidate and actually used frozen-V41 edge positions.",
        "5. `05_reference_next_pair`: reference and next-frame process view for all three cases.",
        "6. `06_edge_profiles`: one representative shared edge shown as intensity and slope profiles.",
        "",
        "## ROI coordinates",
        "",
        catalog.to_markdown(index=False),
    ]
    (VIS_DIR / "VISUAL_INDEX.md").write_text("\n".join(lines), encoding="utf-8")


def write_report(
    comparison: pd.DataFrame,
    sensitivity: pd.DataFrame,
    cross_roi_comparison: pd.DataFrame,
) -> None:
    preferred = comparison[comparison.selection == "common_best30"].copy()
    display = preferred[
        [
            "group",
            "roi_label",
            "raw_std_step_nm",
            "v42_std_step_nm",
            "v42_std_step_nm_improvement_vs_raw_pct",
            "raw_mean_bias_nm",
            "v42_mean_bias_nm",
            "raw_error_aware_total_nm",
            "v42_error_aware_total_nm",
            "v42_error_aware_total_nm_improvement_vs_raw_pct",
            "raw_n_valid",
            "v42_n_valid",
        ]
    ]
    lines = [
        "# V42 ROI sensitivity revalidation",
        "",
        "Raw, V41, and V42 use identical frame pairs, identical ROI coordinates, and frozen-V41 shared edge positions. Three ROIs are reported for every dataset; no per-model ROI is selected.",
        "Measurements pinned to the edge-search boundary are treated as detector failures, not as zero-variance subpixel results. A step enters a comparison only when Raw, V41, and V42 all pass this rule.",
        "The primary error-aware total combines step RMSE to the commanded motion with boundary-localization uncertainty, so a stable but biased result cannot appear artificially strong.",
        "",
        "## Common-best-30 exact results",
        "",
        display.to_markdown(index=False, floatfmt=".2f"),
        "",
        "## ROI sensitivity classification",
        "",
        sensitivity.to_markdown(index=False, floatfmt=".2f"),
        "",
        "## Cross-structure displacement agreement",
        "",
        "This table measures how much the result changes when the same frame pair is measured on different structures. Lower cross-ROI SD is better.",
        "",
        cross_roi_comparison.to_markdown(index=False, floatfmt=".2f"),
        "",
        "## Interpretation rules",
        "",
        "- `robust_improvement`: V42 improves versus Raw in all three ROIs.",
        "- `robust_degradation`: V42 is worse in all three ROIs.",
        "- `roi_sensitive`: the sign changes when the ROI changes; no single headline number is robust.",
        "- `incomplete`: at least one ROI failed the detector validity gate and cannot support a three-ROI conclusion.",
        "- Step SD and total uncertainty are classified separately.",
        "- `error_aware_status` is the primary conclusion because it includes both accuracy and localization uncertainty.",
        "",
        "## Traceability",
        "",
        "See `visual_audit/VISUAL_INDEX.md` for full-frame ROI overlays, independent crops, actual edge locations, and representative frame-pair process images.",
    ]
    (OUT_ROOT / "REPORT.md").write_text("\n".join(lines), encoding="utf-8")


def verify_outputs(
    base: pd.DataFrame,
    selected: pd.DataFrame,
    summary: pd.DataFrame,
    comparison: pd.DataFrame,
) -> dict[str, int]:
    expected_base = 295 * 3 * len(CASES)
    if len(base) != expected_base:
        raise AssertionError(f"expected {expected_base} base rows, got {len(base)}")
    if base.duplicated(["dataset", "group", "step_index", "roi_name", "case"]).any():
        raise AssertionError("duplicate base measurement keys")
    for (selection, roi_name), part in selected.groupby(["selection", "roi_name"], sort=False):
        counts = part.groupby(["dataset", "group", "step_index"]).case.nunique()
        if not (counts == len(CASES)).all():
            raise AssertionError(f"case mismatch in {selection}/{roi_name}")
    return {
        "base_rows": int(len(base)),
        "base_numerically_valid_rows": int(base.ok.astype(str).str.lower().eq("true").sum()),
        "base_analysis_valid_rows": int(
            base.analysis_valid.astype(str).str.lower().eq("true").sum()
        ),
        "search_boundary_saturated_rows": int(
            base.search_boundary_saturated.astype(str).str.lower().eq("true").sum()
        ),
        "selected_rows": int(len(selected)),
        "summary_rows": int(len(summary)),
        "comparison_rows": int(len(comparison)),
    }


def run_measurement_stage(rows: pd.DataFrame) -> None:
    base = measure_all_rois(rows)
    run_summary_stage(base)


def run_summary_stage(base: pd.DataFrame) -> None:
    base = add_analysis_validity_flags(base)
    base.to_csv(TABLE_DIR / "all_steps_roi_measurements.csv", index=False, encoding="utf-8-sig")
    selected = attach_selections(base)
    summary = summarize(selected)
    comparison = build_comparison(summary)
    sensitivity = build_sensitivity_table(comparison)
    cross_roi_detail, cross_roi_comparison = build_cross_roi_consistency(selected)
    selected.to_csv(TABLE_DIR / "selected_roi_measurements.csv", index=False, encoding="utf-8-sig")
    summary.to_csv(TABLE_DIR / "roi_summary_by_case.csv", index=False, encoding="utf-8-sig")
    comparison.to_csv(TABLE_DIR / "roi_comparison_vs_raw.csv", index=False, encoding="utf-8-sig")
    sensitivity.to_csv(TABLE_DIR / "roi_sensitivity_classification.csv", index=False, encoding="utf-8-sig")
    cross_roi_detail.to_csv(
        TABLE_DIR / "cross_roi_consistency_by_step.csv", index=False, encoding="utf-8-sig"
    )
    cross_roi_comparison.to_csv(
        TABLE_DIR / "cross_roi_consistency_comparison.csv", index=False, encoding="utf-8-sig"
    )
    with pd.ExcelWriter(TABLE_DIR / "v42_roi_sensitivity_validation.xlsx") as writer:
        sensitivity.to_excel(writer, sheet_name="classification", index=False)
        cross_roi_comparison.to_excel(writer, sheet_name="cross_roi", index=False)
        comparison.to_excel(writer, sheet_name="comparison", index=False)
        summary.to_excel(writer, sheet_name="summary", index=False)
        selected.to_excel(writer, sheet_name="steps", index=False)
    plot_step_traces(selected)
    plot_cross_roi_consistency(cross_roi_comparison)
    plot_sensitivity_matrix(
        comparison,
        "v42_total_uncertainty_nm_improvement_vs_raw_pct",
        "total_uncertainty_roi_sensitivity.png",
        "Total displacement uncertainty sensitivity to ROI",
    )
    plot_sensitivity_matrix(
        comparison,
        "v42_error_aware_total_nm_improvement_vs_raw_pct",
        "error_aware_total_roi_sensitivity.png",
        "Accuracy- and localization-aware sensitivity to ROI",
    )
    plot_sensitivity_matrix(
        comparison,
        "v42_std_step_nm_improvement_vs_raw_pct",
        "step_sd_roi_sensitivity.png",
        "Step-repeatability sensitivity to ROI",
    )
    write_report(comparison, sensitivity, cross_roi_comparison)
    counts = verify_outputs(base, selected, summary, comparison)
    manifest = {
        "title": "V42 ROI sensitivity revalidation",
        "source_all_steps": str(SOURCE_ALL),
        "source_selected_steps": str(SOURCE_SELECTED),
        "shared_edge_guide": "frozen V41 standalone",
        "invalid_rule": "reject measurements pinned to the profile-search boundary",
        "selections": ["all_steps", "common_best30"],
        "counts": counts,
        "generated_at": pd.Timestamp.now().isoformat(timespec="seconds"),
    }
    (OUT_ROOT / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(counts, indent=2), flush=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--stage", choices=["visuals", "measure", "summarize", "all"], default="all"
    )
    args = parser.parse_args()
    ensure_dirs()
    rows = load_source_rows()
    if args.stage in ["visuals", "all"]:
        catalog = export_visual_audit(rows)
        write_visual_index(catalog)
        print(f"visual audit: {VIS_DIR}", flush=True)
    if args.stage in ["measure", "all"]:
        run_measurement_stage(rows)
        print(f"ROI sensitivity result: {OUT_ROOT}", flush=True)
    if args.stage == "summarize":
        base = pd.read_csv(TABLE_DIR / "all_steps_roi_measurements.csv")
        run_summary_stage(base)
        print(f"ROI sensitivity summary refreshed: {OUT_ROOT}", flush=True)


if __name__ == "__main__":
    main()

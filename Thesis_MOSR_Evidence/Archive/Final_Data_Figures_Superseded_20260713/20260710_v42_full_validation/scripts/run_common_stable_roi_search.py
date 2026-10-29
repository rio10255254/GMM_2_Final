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
PACKAGE = ROOT / "Final_Data_Figures" / "20260710_v42_full_validation"
SOURCE_ALL = PACKAGE / "boundary_sensitive_roi" / "tables" / "all_steps.csv"
SOURCE_SELECTED = PACKAGE / "boundary_sensitive_roi" / "tables" / "selected_steps.csv"
OUT = PACKAGE / "common_stable_roi_search"
TABLES = OUT / "tables"
FIGURES = OUT / "figures"
VISUALS = OUT / "selected_roi_visuals"

CORE_DIR = (
    ROOT
    / "Final_Data_Figures"
    / "20260708_v41_standalone_full_validation"
    / "local_edge_band_optimized_anti_mismatch"
    / "scripts"
)
sys.path.insert(0, str(CORE_DIR))
sys.path.insert(0, str(PACKAGE / "scripts"))

from local_edge_band_core import (  # noqa: E402
    choose_vertical_edge_centers,
    measure_pair_local_edge_displacement,
    normalize_image,
)
from search_common_stable_roi import (  # noqa: E402
    build_candidate_grid,
    candidate_id_for_roi,
    candidate_fold_summary,
    candidate_group_summary,
    classify_final_roi_status,
    choose_common_candidate,
    choose_strict_common_candidate,
    roi_inside_bounds,
)
from run_v42_roi_sensitivity import is_search_boundary_saturated  # noqa: E402


ALL_CASES = ("raw", "v41_standalone", "v42_e120")
MEASURE_CASES = ("raw", "v42_e120")
CASE_LABELS = {"raw": "Raw", "v41_standalone": "V41", "v42_e120": "V42"}
FAMILIES = OrderedDict(
    {
        "50x": {
            "dataset": "20260702_100MG",
            "groups": ("x_0p5um", "x_1um"),
            "roi_size": (360, 320),
            "stride": (280, 240),
            "sample_bounds": None,
        },
        "20x": {
            "dataset": "20260704_20x_5x",
            "groups": ("20x_0p5um", "20x_1um"),
            "roi_size": (360, 320),
            "stride": (280, 240),
            "sample_bounds": None,
        },
        "5x": {
            "dataset": "20260704_20x_5x",
            "groups": ("5x_0p5um", "5x_1um"),
            "roi_size": (360, 320),
            "stride": (280, 240),
            "sample_bounds": (520, 80, 1500, 1450),
        },
    }
)

IMAGE_CACHE: OrderedDict[str, np.ndarray] = OrderedDict()
MAX_CACHE = 12


def ensure_dirs() -> None:
    for folder in [OUT, TABLES, FIGURES, VISUALS]:
        folder.mkdir(parents=True, exist_ok=True)


def cleanup_stale_intermediates() -> None:
    stale_names = [
        "candidate_search_measurements.csv",
        "candidate_search_measurements_partial.csv",
        "coarse_candidate_group_summary.csv",
        "coarse_candidate_four_fold_summary.csv",
        "coarse_candidate_ranking.csv",
        "refinement_candidate_catalog.csv",
        "refined_candidate_search_measurements.csv",
        "refined_candidate_search_measurements_partial.csv",
    ]
    for name in stale_names:
        path = TABLES / name
        if path.exists():
            path.unlink()


def read_image(path: Path) -> np.ndarray:
    key = str(path)
    cached = IMAGE_CACHE.get(key)
    if cached is not None:
        IMAGE_CACHE.move_to_end(key)
        return cached
    with Image.open(path) as image:
        array = np.asarray(image.convert("F"), dtype=np.float32)
    IMAGE_CACHE[key] = array
    IMAGE_CACHE.move_to_end(key)
    while len(IMAGE_CACHE) > MAX_CACHE:
        IMAGE_CACHE.popitem(last=False)
    return array


def image_path(row: pd.Series, field: str) -> Path:
    return Path(str(row.input_dir)) / str(row[field])


def crop(image: np.ndarray, roi: tuple[int, int, int, int]) -> np.ndarray:
    x, y, width, height = roi
    return np.asarray(image[y : y + height, x : x + width], dtype=np.float64)


def load_rows(selected_only: bool) -> pd.DataFrame:
    rows = pd.read_csv(SOURCE_ALL)
    rows = rows[rows.case.isin(ALL_CASES)].copy()
    rows["step_index"] = pd.to_numeric(rows.step_index, errors="raise").astype(int)
    if selected_only:
        selected = pd.read_csv(SOURCE_SELECTED)
        selected = selected[selected.selection == "common_best30"][
            ["dataset", "group", "step_index"]
        ].drop_duplicates()
        rows = rows.merge(selected, on=["dataset", "group", "step_index"], how="inner")
    return rows.sort_values(["dataset", "group", "step_index", "case"])


def first_raw_row(rows: pd.DataFrame, dataset: str, group: str) -> pd.Series:
    return rows[
        (rows.dataset == dataset) & (rows.group == group) & (rows.case == "raw")
    ].iloc[0]


def candidate_catalog(rows: pd.DataFrame) -> pd.DataFrame:
    records: list[dict[str, object]] = []
    for family, config in FAMILIES.items():
        row = first_raw_row(rows, str(config["dataset"]), str(config["groups"][0]))
        image = read_image(image_path(row, "ref_frame"))
        width, height = int(image.shape[1]), int(image.shape[0])
        roi_width, roi_height = config["roi_size"]
        stride_x, stride_y = config["stride"]
        grid = build_candidate_grid(
            width,
            height,
            int(roi_width),
            int(roi_height),
            int(stride_x),
            int(stride_y),
            margin=32,
        )
        sample_bounds = config.get("sample_bounds")
        if sample_bounds is not None:
            grid = [roi for roi in grid if roi_inside_bounds(roi, sample_bounds)]
        for roi in grid:
            records.append(
                {
                    "family": family,
                    "candidate_id": candidate_id_for_roi(family, roi),
                    "roi_x": roi[0],
                    "roi_y": roi[1],
                    "roi_width": roi[2],
                    "roi_height": roi[3],
                    "image_width": width,
                    "image_height": height,
                }
            )
    return pd.DataFrame(records)


def measure_one(
    ref: np.ndarray,
    mov: np.ndarray,
    centers: tuple[int, ...],
    expected: float,
    scale: float,
    max_edges: int,
) -> dict[str, object]:
    try:
        result = measure_pair_local_edge_displacement(
            ref,
            mov,
            expected_signed_dx_px=expected,
            roi=(0, 0, ref.shape[1], ref.shape[0]),
            max_edges=max_edges,
            min_edges=3,
            band_half_width_px=6,
            edge_search_radius_px=8,
            edge_centers=centers,
        )
        signed = float(result.signed_dx_px)
        saturated = is_search_boundary_saturated(signed, expected)
        valid = bool(np.isfinite(signed) and not saturated and result.usable_edges >= 3)
        return {
            "analysis_valid": valid,
            "signed_dx_px": signed,
            "x_step_um": abs(signed) * scale,
            "usable_edges": int(result.usable_edges),
            "localization_uncertainty_nm": float(result.localization_uncertainty_px * scale * 1000.0),
            "search_boundary_saturated": bool(saturated),
            "error": "",
        }
    except Exception as exc:
        return {
            "analysis_valid": False,
            "signed_dx_px": np.nan,
            "x_step_um": np.nan,
            "usable_edges": 0,
            "localization_uncertainty_nm": np.inf,
            "search_boundary_saturated": False,
            "error": repr(exc),
        }


def add_common_validity(measurements: pd.DataFrame) -> pd.DataFrame:
    output = measurements.copy()
    keys = ["family", "candidate_id", "dataset", "group", "step_index"]
    output["common_valid"] = output.groupby(keys)["analysis_valid"].transform(
        lambda values: len(values) == len(MEASURE_CASES) and bool(values.all())
    )
    output["fold"] = output.step_index.astype(int) % 4
    return output


def scan_candidates(
    rows: pd.DataFrame,
    catalog: pd.DataFrame,
    max_edges: int = 6,
    output_stem: str = "candidate_search",
) -> pd.DataFrame:
    records: list[dict[str, object]] = []
    partial_path = TABLES / f"{output_stem}_measurements_partial.csv"
    for family, config in FAMILIES.items():
        family_candidates = catalog[catalog.family == family]
        dataset = str(config["dataset"])
        for group in config["groups"]:
            group_rows = rows[(rows.dataset == dataset) & (rows.group == group)]
            grouped_steps = list(group_rows.groupby("step_index", sort=True))
            for step_number, (step_index, step_rows) in enumerate(grouped_steps, start=1):
                print(
                    f"Search {family} {group}: {step_number}/{len(grouped_steps)}",
                    flush=True,
                )
                by_case = {str(row.case): row for _, row in step_rows.iterrows()}
                full_pairs = {
                    case: (
                        read_image(image_path(by_case[case], "ref_frame")),
                        read_image(image_path(by_case[case], "frame")),
                    )
                    for case in ALL_CASES
                }
                expected = float(by_case["raw"].expected_signed_dx_px)
                scale = float(by_case["raw"].object_um_per_px)
                nominal = float(by_case["raw"].nominal_step_um)
                for _, candidate in family_candidates.iterrows():
                    roi = (
                        int(candidate.roi_x),
                        int(candidate.roi_y),
                        int(candidate.roi_width),
                        int(candidate.roi_height),
                    )
                    v41_ref = crop(full_pairs["v41_standalone"][0], roi)
                    centers = tuple(
                        choose_vertical_edge_centers(
                            normalize_image(v41_ref),
                            expected_signed_dx_px=expected,
                            max_edges=max_edges,
                        )
                    )
                    for case in MEASURE_CASES:
                        ref = crop(full_pairs[case][0], roi)
                        mov = crop(full_pairs[case][1], roi)
                        result = measure_one(ref, mov, centers, expected, scale, max_edges=max_edges)
                        records.append(
                            {
                                "family": family,
                                "candidate_id": candidate.candidate_id,
                                "dataset": dataset,
                                "group": group,
                                "step_index": int(step_index),
                                "case": case,
                                "nominal_step_um": nominal,
                                "expected_signed_dx_px": expected,
                                **result,
                            }
                        )
            pd.DataFrame(records).to_csv(
                partial_path,
                index=False,
                encoding="utf-8-sig",
            )
    output = add_common_validity(pd.DataFrame(records))
    output.to_csv(TABLES / f"{output_stem}_measurements.csv", index=False, encoding="utf-8-sig")
    if partial_path.exists():
        partial_path.unlink()
    return output


def refine_catalog(ranking: pd.DataFrame, catalog: pd.DataFrame, top_n: int = 8) -> pd.DataFrame:
    selected_ids: set[str] = set()
    for family in FAMILIES:
        part = ranking[ranking.family == family].head(top_n)
        selected_ids.update(part.candidate_id.astype(str))
        strict = ranking[(ranking.family == family) & ranking.strict_pass.astype(bool)]
        selected_ids.update(strict.candidate_id.astype(str))
    return catalog[catalog.candidate_id.astype(str).isin(selected_ids)].copy()


def select_rois(
    measurements: pd.DataFrame,
    catalog: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    group_summaries: list[pd.DataFrame] = []
    fold_summaries: list[pd.DataFrame] = []
    rankings: list[pd.DataFrame] = []
    selected_rows: list[dict[str, object]] = []
    for family, config in FAMILIES.items():
        family_rows = measurements[measurements.family == family]
        group_summary = candidate_group_summary(family_rows, min_valid_per_group=24)
        fold_summary = candidate_fold_summary(family_rows, min_valid_per_fold=5)
        selected, ranking = choose_common_candidate(group_summary, expected_groups=2)
        strict_selected, strict_ranking = choose_strict_common_candidate(
            fold_summary, expected_cells=8
        )
        group_summary.insert(0, "family", family)
        fold_summary.insert(0, "family", family)
        ranking.insert(0, "family", family)
        ranking = ranking.merge(
            strict_ranking[["candidate_id", "strict_pass", "min_improvement_pct"]].rename(
                columns={"min_improvement_pct": "min_fold_improvement_pct"}
            ),
            on="candidate_id",
            how="left",
        )
        ranking = ranking.merge(catalog[catalog.family == family], on=["family", "candidate_id"], how="left")
        if selected is None:
            selected = str(ranking.iloc[0].candidate_id)
        chosen = ranking[ranking.candidate_id == selected].iloc[0]
        selected_rows.append(
            {
                "family": family,
                "dataset": config["dataset"],
                "groups": ";".join(config["groups"]),
                "candidate_id": selected,
                "common30_pass": bool(chosen.common_pass),
                "strict_four_fold_pass": bool(chosen.strict_pass),
                "strict_four_fold_candidate": strict_selected or "",
                "roi_x": int(chosen.roi_x),
                "roi_y": int(chosen.roi_y),
                "roi_width": int(chosen.roi_width),
                "roi_height": int(chosen.roi_height),
                "min_common30_improvement_pct": float(chosen.min_improvement_pct),
                "median_common30_improvement_pct": float(chosen.median_improvement_pct),
                "min_fold_improvement_pct": float(chosen.min_fold_improvement_pct),
            }
        )
        group_summaries.append(group_summary)
        fold_summaries.append(fold_summary)
        rankings.append(ranking)
    return (
        pd.concat(group_summaries, ignore_index=True),
        pd.concat(fold_summaries, ignore_index=True),
        pd.concat(rankings, ignore_index=True),
        pd.DataFrame(selected_rows),
    )


def validate_selected(all_rows: pd.DataFrame, selected: pd.DataFrame) -> pd.DataFrame:
    records: list[dict[str, object]] = []
    total_groups = sum(len(config["groups"]) for config in FAMILIES.values())
    group_counter = 0
    for family, config in FAMILIES.items():
        chosen = selected[selected.family == family].iloc[0]
        roi = (
            int(chosen.roi_x),
            int(chosen.roi_y),
            int(chosen.roi_width),
            int(chosen.roi_height),
        )
        dataset = str(config["dataset"])
        for group in config["groups"]:
            group_counter += 1
            group_rows = all_rows[(all_rows.dataset == dataset) & (all_rows.group == group)]
            grouped_steps = list(group_rows.groupby("step_index", sort=True))
            for step_number, (step_index, step_rows) in enumerate(grouped_steps, start=1):
                if step_number == 1 or step_number % 10 == 0 or step_number == len(grouped_steps):
                    print(
                        f"Validate {group_counter}/{total_groups} {family} {group}: "
                        f"{step_number}/{len(grouped_steps)}",
                        flush=True,
                    )
                by_case = {str(row.case): row for _, row in step_rows.iterrows()}
                full_pairs = {
                    case: (
                        read_image(image_path(by_case[case], "ref_frame")),
                        read_image(image_path(by_case[case], "frame")),
                    )
                    for case in ALL_CASES
                }
                expected = float(by_case["raw"].expected_signed_dx_px)
                scale = float(by_case["raw"].object_um_per_px)
                centers = tuple(
                    choose_vertical_edge_centers(
                        normalize_image(crop(full_pairs["v41_standalone"][0], roi)),
                        expected_signed_dx_px=expected,
                        max_edges=12,
                    )
                )
                for case in MEASURE_CASES:
                    result = measure_one(
                        crop(full_pairs[case][0], roi),
                        crop(full_pairs[case][1], roi),
                        centers,
                        expected,
                        scale,
                        max_edges=12,
                    )
                    records.append(
                        {
                            "family": family,
                            "candidate_id": chosen.candidate_id,
                            "dataset": dataset,
                            "group": group,
                            "step_index": int(step_index),
                            "case": case,
                            "nominal_step_um": float(by_case["raw"].nominal_step_um),
                            "expected_signed_dx_px": expected,
                            "roi_x": roi[0],
                            "roi_y": roi[1],
                            "roi_width": roi[2],
                            "roi_height": roi[3],
                            **result,
                        }
                    )
    output = add_common_validity(pd.DataFrame(records))
    output.to_csv(TABLES / "locked_roi_all_step_measurements.csv", index=False, encoding="utf-8-sig")
    return output


def summarize_validation(validation: pd.DataFrame) -> pd.DataFrame:
    selected_keys = pd.read_csv(SOURCE_SELECTED)
    selected_keys = set(
        tuple(value)
        for value in selected_keys[selected_keys.selection == "common_best30"]
        [["dataset", "group", "step_index"]]
        .drop_duplicates()
        .itertuples(index=False, name=None)
    )
    work = validation.copy()
    work["is_search_step"] = [
        (row.dataset, row.group, int(row.step_index)) in selected_keys
        for row in work.itertuples(index=False)
    ]
    selections = {
        "search_common30": work.is_search_step,
        "heldout_remaining": ~work.is_search_step,
        "all_steps": pd.Series(True, index=work.index),
    }
    rows: list[dict[str, object]] = []
    for selection, mask in selections.items():
        part = work[mask & work.common_valid]
        for keys, case_rows in part.groupby(["family", "dataset", "group", "case"], sort=False):
            values = case_rows.x_step_um.to_numpy(dtype=np.float64)
            nominal = float(case_rows.nominal_step_um.median())
            error_nm = (values - nominal) * 1000.0
            rows.append(
                {
                    "selection": selection,
                    "family": keys[0],
                    "dataset": keys[1],
                    "group": keys[2],
                    "case": keys[3],
                    "n_valid": int(len(values)),
                    "step_sd_nm": float(np.std(values, ddof=1) * 1000.0),
                    "mean_bias_nm": float(np.mean(error_nm)),
                    "rmse_nm": float(np.sqrt(np.mean(np.square(error_nm)))),
                    "median_localization_nm": float(case_rows.localization_uncertainty_nm.median()),
                }
            )
    summary = pd.DataFrame(rows)
    comparisons: list[dict[str, object]] = []
    for keys, part in summary.groupby(["selection", "family", "dataset", "group"], sort=False):
        by_case = {str(row.case): row for _, row in part.iterrows()}
        if not all(case in by_case for case in MEASURE_CASES):
            continue
        raw, v42 = by_case["raw"], by_case["v42_e120"]
        improvement = (raw.step_sd_nm - v42.step_sd_nm) / raw.step_sd_nm * 100.0
        comparisons.append(
            {
                "selection": keys[0],
                "family": keys[1],
                "dataset": keys[2],
                "group": keys[3],
                "n_common_valid": int(min(raw.n_valid, v42.n_valid)),
                "raw_step_sd_nm": float(raw.step_sd_nm),
                "v42_step_sd_nm": float(v42.step_sd_nm),
                "v42_improvement_pct": float(improvement),
                "raw_mean_bias_nm": float(raw.mean_bias_nm),
                "v42_mean_bias_nm": float(v42.mean_bias_nm),
                "raw_rmse_nm": float(raw.rmse_nm),
                "v42_rmse_nm": float(v42.rmse_nm),
                "raw_localization_nm": float(raw.median_localization_nm),
                "v42_localization_nm": float(v42.median_localization_nm),
                "v42_more_stable": bool(improvement > 0.0),
            }
        )
    comparison = pd.DataFrame(comparisons)
    summary.to_csv(TABLES / "locked_roi_validation_summary_by_case.csv", index=False, encoding="utf-8-sig")
    comparison.to_csv(TABLES / "locked_roi_raw_v42_comparison.csv", index=False, encoding="utf-8-sig")
    return comparison


def build_final_status(selected: pd.DataFrame, comparison: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for _, chosen in selected.iterrows():
        family = str(chosen.family)
        search = comparison[
            (comparison.family == family) & (comparison.selection == "search_common30")
        ]
        heldout = comparison[
            (comparison.family == family) & (comparison.selection == "heldout_remaining")
        ]
        all_steps = comparison[
            (comparison.family == family) & (comparison.selection == "all_steps")
        ]
        status = classify_final_roi_status(
            bool(chosen.common30_pass),
            heldout.v42_improvement_pct.astype(float).tolist(),
            all_steps.v42_improvement_pct.astype(float).tolist(),
            heldout.n_common_valid.astype(int).tolist(),
        )
        rows.append(
            {
                "family": family,
                "candidate_id": chosen.candidate_id,
                "status": status,
                "search_common30_pass": bool(chosen.common30_pass),
                "four_fold_pass": bool(chosen.strict_four_fold_pass),
                "heldout_both_improve": bool(
                    len(heldout) == 2 and (heldout.v42_improvement_pct.astype(float) > 0).all()
                ),
                "heldout_min_valid": int(heldout.n_common_valid.astype(int).min()),
                "all_steps_both_improve": bool(
                    len(all_steps) == 2 and (all_steps.v42_improvement_pct.astype(float) > 0).all()
                ),
                "minimum_heldout_improvement_pct": float(
                    heldout.v42_improvement_pct.astype(float).min()
                ),
                "minimum_all_step_improvement_pct": float(
                    all_steps.v42_improvement_pct.astype(float).min()
                ),
                "roi_x": int(chosen.roi_x),
                "roi_y": int(chosen.roi_y),
                "roi_width": int(chosen.roi_width),
                "roi_height": int(chosen.roi_height),
            }
        )
    output = pd.DataFrame(rows)
    output.to_csv(TABLES / "final_common_roi_status.csv", index=False, encoding="utf-8-sig")
    return output


def to_uint8(image: np.ndarray) -> np.ndarray:
    lo, hi = np.percentile(image, [1, 99])
    return np.clip((image - lo) / max(hi - lo, 1e-9) * 255.0, 0, 255).astype(np.uint8)


def export_visuals(rows: pd.DataFrame, selected: pd.DataFrame) -> None:
    font = ImageFont.load_default(size=20)
    for _, chosen in selected.iterrows():
        family = str(chosen.family)
        config = FAMILIES[family]
        roi = (int(chosen.roi_x), int(chosen.roi_y), int(chosen.roi_width), int(chosen.roi_height))
        for group in config["groups"]:
            subset = rows[
                (rows.dataset == config["dataset"]) & (rows.group == group)
            ]
            step_index = int(subset.step_index.min())
            by_case = {
                str(row.case): row
                for _, row in subset[subset.step_index == step_index].iterrows()
            }
            raw = read_image(image_path(by_case["raw"], "ref_frame"))
            canvas = Image.fromarray(to_uint8(raw), mode="L").convert("RGB")
            draw = ImageDraw.Draw(canvas)
            x, y, width, height = roi
            draw.rectangle((x, y, x + width, y + height), outline="#e31a1c", width=7)
            label = f"Locked common ROI {family}: ({x}, {y}, {width}, {height})"
            box = draw.textbbox((x + 5, y + 5), label, font=font)
            draw.rectangle(box, fill="white")
            draw.text((x + 5, y + 5), label, fill="#b00000", font=font)
            canvas.save(VISUALS / f"{family}_{group}_full_frame_locked_roi.png")

            fig, axes = plt.subplots(1, 3, figsize=(12, 4.2), dpi=170)
            for ax, case in zip(axes, ALL_CASES):
                image = read_image(image_path(by_case[case], "ref_frame"))
                roi_image = crop(image, roi)
                ax.imshow(roi_image, cmap="gray", vmin=np.percentile(roi_image, 1), vmax=np.percentile(roi_image, 99))
                ax.set_title(CASE_LABELS[case])
                ax.set_axis_off()
            fig.suptitle(f"{family} / {group} / locked common ROI")
            fig.tight_layout()
            fig.savefig(VISUALS / f"{family}_{group}_raw_v41_v42_crop.png", facecolor="white")
            plt.close(fig)


def plot_results(comparison: pd.DataFrame) -> None:
    for selection in ["search_common30", "heldout_remaining", "all_steps"]:
        part = comparison[comparison.selection == selection].copy()
        if part.empty:
            continue
        labels = [str(value).replace("x_", "50x_") for value in part.group]
        x = np.arange(len(part))
        width = 0.36
        fig, ax = plt.subplots(figsize=(11.5, 5.2), dpi=180)
        ax.bar(x - width / 2, part.raw_step_sd_nm, width, label="Raw", color="#69737d")
        ax.bar(x + width / 2, part.v42_step_sd_nm, width, label="V42", color="#12866f")
        ax.set_xticks(x, labels, rotation=25, ha="right")
        ax.set_ylabel("Step standard deviation (nm, lower is better)")
        ax.set_title(f"Locked common ROI displacement stability - {selection}")
        ax.grid(axis="y", alpha=0.25)
        ax.legend(frameon=False)
        fig.tight_layout()
        fig.savefig(FIGURES / f"locked_roi_{selection}_step_sd.png", facecolor="white")
        plt.close(fig)


def write_report(
    selected: pd.DataFrame,
    comparison: pd.DataFrame,
    catalog: pd.DataFrame,
    final_status: pd.DataFrame,
) -> None:
    heldout = comparison[comparison.selection == "heldout_remaining"]
    all_steps = comparison[comparison.selection == "all_steps"]
    heldout_pass = int(heldout.v42_more_stable.sum())
    all_pass = int(all_steps.v42_more_stable.sum())
    robust_count = int((final_status.status == "robust_common").sum())
    conclusion = (
        "A robust common ROI was found for every magnification."
        if robust_count == len(final_status)
        else "No ROI satisfied the complete common-stability requirement across all magnifications and both step sizes."
    )
    lines = [
        "# Common stable ROI search",
        "",
        f"## Final conclusion: {conclusion}",
        "",
        "The ROI was searched on the shared common-best-30 steps. One fixed ROI was required for both 0.5 and 1 um sequences at each magnification. The locked ROI was then checked on steps that were not used in the search and on the complete sequence.",
        "",
        f"- Candidate rectangles searched: {len(catalog)}",
        f"- Held-out groups where V42 SD is lower than Raw: {heldout_pass}/{len(heldout)}",
        f"- Full-sequence groups where V42 SD is lower than Raw: {all_pass}/{len(all_steps)}",
        "- This is an internal ROI search, not an external independent validation.",
        "",
        "## Final ROI status",
        "",
        final_status.to_markdown(index=False),
        "",
        "## Locked ROIs",
        "",
        selected.to_markdown(index=False),
        "",
        "## Raw versus V42",
        "",
        comparison.to_markdown(index=False),
        "",
    ]
    (OUT / "REPORT.md").write_text("\n".join(lines), encoding="utf-8")


def verify_outputs(selected: pd.DataFrame, comparison: pd.DataFrame) -> None:
    if len(selected) != 3:
        raise RuntimeError(f"expected three locked ROIs, got {len(selected)}")
    if len(comparison[comparison.selection == "all_steps"]) != 6:
        raise RuntimeError("all-step comparison does not contain all six displacement groups")
    if comparison[["raw_step_sd_nm", "v42_step_sd_nm"]].isna().any().any():
        raise RuntimeError("comparison contains NaN step SD")
    expected_visuals = 3 * 2 * 2
    actual_visuals = len(list(VISUALS.glob("*.png")))
    if actual_visuals != expected_visuals:
        raise RuntimeError(f"expected {expected_visuals} ROI visuals, got {actual_visuals}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--reuse-search", action="store_true")
    args = parser.parse_args()
    ensure_dirs()
    cleanup_stale_intermediates()

    selected_rows = load_rows(selected_only=True)
    catalog = candidate_catalog(selected_rows)
    catalog.to_csv(TABLES / "candidate_roi_catalog.csv", index=False, encoding="utf-8-sig")
    search_path = TABLES / "final_candidate_search_measurements.csv"
    if args.reuse_search and search_path.exists():
        search_measurements = pd.read_csv(search_path)
    else:
        search_measurements = scan_candidates(
            selected_rows,
            catalog,
            max_edges=12,
            output_stem="final_candidate_search",
        )
    group_summary, fold_summary, ranking, selected = select_rois(search_measurements, catalog)
    group_summary.to_csv(TABLES / "candidate_group_summary.csv", index=False, encoding="utf-8-sig")
    fold_summary.to_csv(TABLES / "candidate_four_fold_summary.csv", index=False, encoding="utf-8-sig")
    ranking.to_csv(TABLES / "candidate_ranking.csv", index=False, encoding="utf-8-sig")
    selected.to_csv(TABLES / "locked_common_rois.csv", index=False, encoding="utf-8-sig")

    all_rows = load_rows(selected_only=False)
    validation = validate_selected(all_rows, selected)
    comparison = summarize_validation(validation)
    final_status = build_final_status(selected, comparison)
    export_visuals(all_rows, selected)
    plot_results(comparison)
    write_report(selected, comparison, catalog, final_status)
    verify_outputs(selected, comparison)

    manifest = {
        "search_source": str(SOURCE_SELECTED),
        "validation_source": str(SOURCE_ALL),
        "candidate_count": int(len(catalog)),
        "locked_roi_count": int(len(selected)),
        "search_rule": "same fixed ROI for 0.5 and 1 um at each magnification",
        "search_steps": "common_best30",
        "independent_check": "remaining steps not used by common_best30",
        "comparison": "Raw versus V42 epoch 120",
        "sample_constraint": "5x candidates must be fully inside the calibration sample",
        "final_detector_edges": 12,
    }
    (OUT / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"Completed: {OUT}", flush=True)


if __name__ == "__main__":
    main()

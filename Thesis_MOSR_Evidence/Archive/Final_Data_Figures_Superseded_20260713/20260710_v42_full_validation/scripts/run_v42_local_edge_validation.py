from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from PIL import Image


ROOT = Path("D:/GMM_2_Final/Thesis_MOSR_Evidence")
PACKAGE_ROOT = ROOT / "Final_Data_Figures" / "20260710_v42_full_validation"
SOURCE_ALL = PACKAGE_ROOT / "boundary_sensitive_roi" / "tables" / "all_steps.csv"
SOURCE_SELECTED = PACKAGE_ROOT / "boundary_sensitive_roi" / "tables" / "selected_steps.csv"
OUT_ROOT = PACKAGE_ROOT / "local_edge_preferred"
TABLE_DIR = OUT_ROOT / "tables"
FIG_DIR = OUT_ROOT / "figures"

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
)


CASES = ["raw", "v41_standalone", "v42_e120"]
CASE_LABEL = {
    "raw": "Raw",
    "v41_standalone": "V41 standalone",
    "v42_e120": "V42 epoch 120",
}
CASE_COLOR = {
    "raw": "#707880",
    "v41_standalone": "#d95f02",
    "v42_e120": "#168f77",
}
EDGE_MODES = [
    "self_detected_edges",
    "v41_standalone_guided_edges",
    "v42_e120_guided_edges",
]
MODE_LABEL = {
    "self_detected_edges": "Independent self-detected edges",
    "v41_standalone_guided_edges": "Shared edges guided by V41",
    "v42_e120_guided_edges": "Shared edges guided by V42",
}
SELECTIONS = ["all_steps", "common_best30", "raw_anchor_best30"]
SELECTION_LABEL = {
    "all_steps": "All valid acquisition steps",
    "common_best30": "Common best 30 steps",
    "raw_anchor_best30": "Raw-anchored best 30 steps",
}
MAG_ORDER = {"50x": 0, "20x": 1, "5x": 2}


def total_uncertainty_nm(step_repeatability_sd_nm: float, localization_nm: float) -> float:
    """Combine acquisition repeatability and boundary-localization uncertainty."""
    return float(math.hypot(float(step_repeatability_sd_nm), float(localization_nm)))


def select_case_symmetric_steps(
    rows: pd.DataFrame,
    cases: list[str],
    chosen_keys: pd.DataFrame | None,
) -> pd.DataFrame:
    """Keep only step keys represented exactly once by every requested case."""
    key_cols = ["dataset", "group", "step_index"]
    selected = rows.copy()
    selected["step_index"] = pd.to_numeric(selected["step_index"], errors="raise").astype(int)
    selected = selected[selected["case"].isin(cases)].copy()
    if chosen_keys is not None:
        keys = chosen_keys[key_cols].drop_duplicates().copy()
        keys["step_index"] = pd.to_numeric(keys["step_index"], errors="raise").astype(int)
        selected = selected.merge(keys, on=key_cols, how="inner")

    complete_keys: list[tuple[object, object, int]] = []
    expected = set(cases)
    for key, part in selected.groupby(key_cols, sort=False):
        case_counts = part.groupby("case").size()
        if (
            set(part["case"]) == expected
            and len(case_counts) == len(cases)
            and case_counts.nunique() == 1
        ):
            complete_keys.append((key[0], key[1], int(key[2])))
    if not complete_keys:
        return selected.iloc[0:0].copy()
    complete = pd.DataFrame(complete_keys, columns=key_cols)
    return selected.merge(complete, on=key_cols, how="inner")


def ensure_dirs() -> None:
    TABLE_DIR.mkdir(parents=True, exist_ok=True)
    FIG_DIR.mkdir(parents=True, exist_ok=True)
    for folder in [TABLE_DIR, FIG_DIR]:
        for path in folder.iterdir():
            if path.is_file() and path.name != "all_steps_base_measurements.csv":
                path.unlink()


def infer_magnification(dataset: str, group: str) -> str:
    if dataset == "20260702_100MG":
        return "50x"
    if group.startswith("20x_"):
        return "20x"
    if group.startswith("5x_"):
        return "5x"
    raise ValueError(f"cannot infer magnification for {dataset}/{group}")


def read_roi(path: Path, roi: tuple[int, int, int, int]) -> np.ndarray:
    x, y, w, h = roi
    with Image.open(path) as img:
        return np.asarray(
            img.convert("F").crop((x, y, x + w, y + h)), dtype=np.float64
        )


def load_source_rows() -> pd.DataFrame:
    rows = pd.read_csv(SOURCE_ALL)
    rows = rows[rows["case"].isin(CASES)].copy()
    numeric = [
        "step_index",
        "roi_x",
        "roi_y",
        "roi_width",
        "roi_height",
        "object_um_per_px",
        "nominal_step_um",
        "expected_signed_dx_px",
    ]
    for col in numeric:
        rows[col] = pd.to_numeric(rows[col], errors="raise")
    rows["step_index"] = rows["step_index"].astype(int)
    rows = select_case_symmetric_steps(rows, CASES, chosen_keys=None)
    rows["magnification"] = [
        infer_magnification(str(dataset), str(group))
        for dataset, group in zip(rows["dataset"], rows["group"])
    ]
    rows["step_label"] = rows["nominal_step_um"].map(
        lambda value: f"{float(value):g} um/step"
    )
    rows["dataset_label"] = rows["magnification"] + " " + rows["step_label"]
    rows["case_label"] = rows["case"].map(CASE_LABEL)
    rows["mag_order"] = rows["magnification"].map(MAG_ORDER)
    rows["case_order"] = rows["case"].map({case: idx for idx, case in enumerate(CASES)})
    rows = rows.sort_values(
        ["mag_order", "nominal_step_um", "dataset", "group", "step_index", "case_order"]
    ).drop(columns=["mag_order", "case_order"])

    counts = rows.groupby(["dataset", "group", "step_index"])["case"].nunique()
    if not (counts == len(CASES)).all():
        raise ValueError("source rows are not case symmetric")
    return rows


def choose_centers(image: np.ndarray, expected_signed_dx_px: float) -> tuple[int, ...]:
    centers = choose_vertical_edge_centers(
        normalize_image(image),
        expected_signed_dx_px=expected_signed_dx_px,
        max_edges=12,
    )
    return tuple(int(center) for center in centers)


def measurement_base(row: pd.Series, edge_mode: str) -> dict[str, object]:
    return {
        "edge_mode": edge_mode,
        "edge_mode_label": MODE_LABEL[edge_mode],
        "dataset": row["dataset"],
        "group": row["group"],
        "magnification": row["magnification"],
        "dataset_label": row["dataset_label"],
        "step_label": row["step_label"],
        "case": row["case"],
        "case_label": CASE_LABEL[str(row["case"])],
        "step_index": int(row["step_index"]),
        "ref_frame": row["ref_frame"],
        "frame": row["frame"],
        "input_dir": row["input_dir"],
        "roi_x": int(row["roi_x"]),
        "roi_y": int(row["roi_y"]),
        "roi_width": int(row["roi_width"]),
        "roi_height": int(row["roi_height"]),
        "object_um_per_px": float(row["object_um_per_px"]),
        "nominal_step_um": float(row["nominal_step_um"]),
        "expected_signed_dx_px": float(row["expected_signed_dx_px"]),
    }


def measure_all_steps(rows: pd.DataFrame) -> pd.DataFrame:
    results: list[dict[str, object]] = []
    key_cols = ["dataset", "group", "step_index"]
    groups = list(rows.groupby(key_cols, sort=False))
    total = len(groups)
    for group_index, (key, step_rows) in enumerate(groups, start=1):
        if group_index == 1 or group_index % 10 == 0 or group_index == total:
            print(f"local-edge steps: {group_index}/{total} ({key[0]}/{key[1]})", flush=True)

        by_case = {str(row["case"]): row for _, row in step_rows.iterrows()}
        images: dict[str, tuple[np.ndarray, np.ndarray]] = {}
        for case in CASES:
            row = by_case[case]
            roi = (
                int(row["roi_x"]),
                int(row["roi_y"]),
                int(row["roi_width"]),
                int(row["roi_height"]),
            )
            base_dir = Path(str(row["input_dir"]))
            images[case] = (
                read_roi(base_dir / str(row["ref_frame"]), roi),
                read_roi(base_dir / str(row["frame"]), roi),
            )

        expected = float(step_rows.iloc[0]["expected_signed_dx_px"])
        centers_by_mode = {
            "self_detected_edges": None,
            "v41_standalone_guided_edges": choose_centers(images["v41_standalone"][0], expected),
            "v42_e120_guided_edges": choose_centers(images["v42_e120"][0], expected),
        }
        for edge_mode in EDGE_MODES:
            shared_centers = centers_by_mode[edge_mode]
            for case in CASES:
                row = by_case[case]
                base = measurement_base(row, edge_mode)
                try:
                    ref_image, mov_image = images[case]
                    measurement = measure_pair_local_edge_displacement(
                        ref_image,
                        mov_image,
                        expected_signed_dx_px=float(row["expected_signed_dx_px"]),
                        roi=(0, 0, int(row["roi_width"]), int(row["roi_height"])),
                        max_edges=12,
                        min_edges=3,
                        band_half_width_px=6,
                        edge_search_radius_px=8,
                        edge_centers=shared_centers,
                    )
                    scale = float(row["object_um_per_px"])
                    x_step_um = abs(float(measurement.signed_dx_px)) * scale
                    base.update(
                        {
                            "ok": bool(np.isfinite(measurement.signed_dx_px)),
                            "signed_dx_px": float(measurement.signed_dx_px),
                            "x_step_um": x_step_um,
                            "abs_error_um": abs(x_step_um - float(row["nominal_step_um"])),
                            "usable_edges": int(measurement.usable_edges),
                            "candidate_edges": int(measurement.candidate_edges),
                            "rejected_edges": int(measurement.rejected_edges),
                            "ambiguity_score": float(measurement.ambiguity_score),
                            "consensus_mad_px": float(measurement.consensus_mad_px),
                            "boundary_confidence": float(measurement.boundary_confidence),
                            "localization_uncertainty_px": float(
                                measurement.localization_uncertainty_px
                            ),
                            "localization_uncertainty_nm": float(
                                measurement.localization_uncertainty_px * scale * 1000.0
                            ),
                            "edge_shift_mad_nm": float(
                                measurement.consensus_mad_px * scale * 1000.0
                            ),
                            "error": "",
                        }
                    )
                except Exception as exc:
                    base.update(
                        {
                            "ok": False,
                            "signed_dx_px": np.nan,
                            "x_step_um": np.nan,
                            "abs_error_um": np.nan,
                            "usable_edges": 0,
                            "candidate_edges": 0,
                            "rejected_edges": 0,
                            "ambiguity_score": np.inf,
                            "consensus_mad_px": np.inf,
                            "boundary_confidence": 0.0,
                            "localization_uncertainty_px": np.inf,
                            "localization_uncertainty_nm": np.inf,
                            "edge_shift_mad_nm": np.nan,
                            "error": repr(exc),
                        }
                    )
                results.append(base)
    return pd.DataFrame(results)


def attach_selections(measurements: pd.DataFrame) -> pd.DataFrame:
    selected_source = pd.read_csv(SOURCE_SELECTED)
    outputs: list[pd.DataFrame] = []
    for selection in SELECTIONS:
        if selection == "all_steps":
            chosen = None
        else:
            chosen = selected_source[selected_source["selection"] == selection][
                ["dataset", "group", "step_index"]
            ].drop_duplicates()
        part = select_case_symmetric_steps(measurements, CASES, chosen)
        part["selection"] = selection
        part["selection_label"] = SELECTION_LABEL[selection]
        outputs.append(part)
    out = pd.concat(outputs, ignore_index=True)
    return out


def summarize(measurements: pd.DataFrame) -> pd.DataFrame:
    group_cols = [
        "selection",
        "selection_label",
        "edge_mode",
        "edge_mode_label",
        "magnification",
        "dataset",
        "group",
        "dataset_label",
        "step_label",
        "case",
        "case_label",
    ]
    rows: list[dict[str, object]] = []
    for keys, part in measurements.groupby(group_cols, sort=False):
        valid = part[part["ok"]].copy()
        finite_unc = valid["localization_uncertainty_nm"].replace([np.inf, -np.inf], np.nan)
        step_sd = float(valid["x_step_um"].std(ddof=1) * 1000.0)
        localization = float(finite_unc.median())
        rows.append(
            {
                **dict(zip(group_cols, keys)),
                "n_requested": int(len(part)),
                "n_valid": int(len(valid)),
                "valid_rate_pct": float(len(valid) / max(len(part), 1) * 100.0),
                "nominal_step_um": float(part["nominal_step_um"].median()),
                "std_step_nm": step_sd,
                "median_step_nm": float(valid["x_step_um"].median() * 1000.0),
                "median_abs_error_nm": float(valid["abs_error_um"].median() * 1000.0),
                "p90_abs_error_nm": float(valid["abs_error_um"].quantile(0.90) * 1000.0),
                "median_localization_uncertainty_nm": localization,
                "total_uncertainty_nm": total_uncertainty_nm(step_sd, localization),
                "median_boundary_confidence": float(valid["boundary_confidence"].median()),
                "median_usable_edges": float(valid["usable_edges"].median()),
                "median_rejected_edges": float(valid["rejected_edges"].median()),
                "median_ambiguity_score": float(
                    valid["ambiguity_score"].replace([np.inf, -np.inf], np.nan).median()
                ),
                "median_edge_shift_mad_nm": float(valid["edge_shift_mad_nm"].median()),
            }
        )
    summary = pd.DataFrame(rows)
    summary["mag_order"] = summary["magnification"].map(MAG_ORDER)
    summary["case_order"] = summary["case"].map({case: idx for idx, case in enumerate(CASES)})
    return summary.sort_values(
        ["selection", "edge_mode", "mag_order", "nominal_step_um", "case_order"]
    ).drop(columns=["mag_order", "case_order"])


def improvement_pct(raw_value: float, model_value: float) -> float:
    if not np.isfinite(raw_value) or raw_value == 0:
        return float("nan")
    return float((raw_value - model_value) / raw_value * 100.0)


def build_comparison(summary: pd.DataFrame) -> pd.DataFrame:
    keys = [
        "selection",
        "edge_mode",
        "magnification",
        "dataset",
        "group",
        "dataset_label",
        "step_label",
    ]
    indexed = {case: summary[summary["case"] == case].set_index(keys) for case in CASES}
    rows: list[dict[str, object]] = []
    for key in indexed["v42_e120"].index:
        if not all(key in indexed[case].index for case in CASES):
            continue
        raw = indexed["raw"].loc[key]
        v41 = indexed["v41_standalone"].loc[key]
        v42 = indexed["v42_e120"].loc[key]
        result = {
            "selection": key[0],
            "selection_label": SELECTION_LABEL[key[0]],
            "edge_mode": key[1],
            "edge_mode_label": MODE_LABEL[key[1]],
            "magnification": key[2],
            "dataset": key[3],
            "group": key[4],
            "dataset_label": key[5],
            "step_label": key[6],
        }
        for metric in [
            "n_valid",
            "std_step_nm",
            "median_abs_error_nm",
            "median_localization_uncertainty_nm",
            "total_uncertainty_nm",
            "median_boundary_confidence",
            "median_usable_edges",
            "median_ambiguity_score",
        ]:
            result[f"raw_{metric}"] = float(raw[metric])
            result[f"v41_{metric}"] = float(v41[metric])
            result[f"v42_{metric}"] = float(v42[metric])
        for metric in [
            "std_step_nm",
            "median_abs_error_nm",
            "median_localization_uncertainty_nm",
            "total_uncertainty_nm",
        ]:
            result[f"v42_{metric}_improvement_vs_raw_pct"] = improvement_pct(
                float(raw[metric]), float(v42[metric])
            )
            result[f"v42_{metric}_improvement_vs_v41_pct"] = improvement_pct(
                float(v41[metric]), float(v42[metric])
            )
        rows.append(result)
    comparison = pd.DataFrame(rows)
    comparison["mag_order"] = comparison["magnification"].map(MAG_ORDER)
    return comparison.sort_values(
        ["selection", "edge_mode", "mag_order", "step_label"]
    ).drop(columns=["mag_order"])


def plot_comparison(comparison: pd.DataFrame, selection: str, edge_mode: str) -> None:
    part = comparison[
        (comparison["selection"] == selection) & (comparison["edge_mode"] == edge_mode)
    ].copy()
    part["mag_order"] = part["magnification"].map(MAG_ORDER)
    part = part.sort_values(["mag_order", "step_label"])
    labels = part["dataset_label"].tolist()
    x = np.arange(len(labels))
    width = 0.24
    fig, axes = plt.subplots(1, 2, figsize=(14.0, 5.3), dpi=170)
    for offset, prefix, label, color in [
        (-width, "raw", "Raw", CASE_COLOR["raw"]),
        (0.0, "v41", "V41", CASE_COLOR["v41_standalone"]),
        (width, "v42", "V42 E120", CASE_COLOR["v42_e120"]),
    ]:
        axes[0].bar(x + offset, part[f"{prefix}_std_step_nm"], width, label=label, color=color)
        axes[1].bar(
            x + offset, part[f"{prefix}_total_uncertainty_nm"], width, label=label, color=color
        )
    axes[0].set_title("Displacement repeatability")
    axes[0].set_ylabel("Standard deviation (nm)")
    axes[1].set_title("Repeatability + boundary localization")
    axes[1].set_ylabel("Total uncertainty (nm)")
    for ax in axes:
        ax.set_xticks(x)
        ax.set_xticklabels(labels, rotation=22, ha="right")
        ax.grid(axis="y", alpha=0.25)
    axes[0].legend(frameon=False)
    fig.suptitle(f"{SELECTION_LABEL[selection]} | {MODE_LABEL[edge_mode]}")
    fig.tight_layout()
    fig.savefig(FIG_DIR / f"{selection}_{edge_mode}_comparison.png")
    plt.close(fig)


def markdown_table(data: pd.DataFrame) -> str:
    return data.to_markdown(index=False, floatfmt=".2f")


def write_report(comparison: pd.DataFrame, measurements: pd.DataFrame) -> None:
    mode = "v41_standalone_guided_edges"
    lines = [
        "# V42 preferred local-edge displacement validation",
        "",
        "This package uses the optimized local boundary method with subpixel localization, repeated-pattern mismatch rejection, and multi-edge consensus.",
        "",
        "The main display mode follows the established thesis protocol: one shared set of local edge positions is detected from the frozen V41 reference and then applied unchanged to Raw, V41, and V42. Independent self-detected and V42-guided modes are retained as controls.",
        "",
    ]
    for selection in ["all_steps", "common_best30", "raw_anchor_best30"]:
        part = comparison[
            (comparison["selection"] == selection) & (comparison["edge_mode"] == mode)
        ].copy()
        display = part[
            [
                "dataset_label",
                "raw_std_step_nm",
                "v41_std_step_nm",
                "v42_std_step_nm",
                "v42_std_step_nm_improvement_vs_raw_pct",
                "raw_total_uncertainty_nm",
                "v42_total_uncertainty_nm",
                "v42_total_uncertainty_nm_improvement_vs_raw_pct",
            ]
        ].rename(
            columns={
                "dataset_label": "Dataset",
                "raw_std_step_nm": "Raw SD (nm)",
                "v41_std_step_nm": "V41 SD (nm)",
                "v42_std_step_nm": "V42 SD (nm)",
                "v42_std_step_nm_improvement_vs_raw_pct": "V42 SD improvement vs Raw (%)",
                "raw_total_uncertainty_nm": "Raw total uncertainty (nm)",
                "v42_total_uncertainty_nm": "V42 total uncertainty (nm)",
                "v42_total_uncertainty_nm_improvement_vs_raw_pct": "V42 total improvement vs Raw (%)",
            }
        )
        lines.extend([f"## {SELECTION_LABEL[selection]}", "", markdown_table(display), ""])

    valid = measurements.groupby(["selection", "edge_mode", "case"])["ok"].agg(["sum", "count"])
    lines.extend(
        [
            "## Validation notes",
            "",
            f"- Source acquisition steps: {measurements[measurements['selection'] == 'all_steps'][['dataset', 'group', 'step_index']].drop_duplicates().shape[0]}",
            "- Every reported step is case symmetric: Raw, V41, and V42 use the same frame pair and ROI.",
            "- Frozen-V41-guided shared edges are the primary thesis display because this was the established protocol before V42 was evaluated.",
            "- V42-guided and independent self-detected edges are retained as supplementary controls.",
            "- Total uncertainty is the root-sum-square of step repeatability SD and median boundary-localization uncertainty.",
            "",
            "## Valid measurement counts",
            "",
            valid.reset_index().to_markdown(index=False),
        ]
    )
    (OUT_ROOT / "REPORT.md").write_text("\n".join(lines), encoding="utf-8")


def verify_outputs(
    base_measurements: pd.DataFrame,
    selected_measurements: pd.DataFrame,
    summary: pd.DataFrame,
    comparison: pd.DataFrame,
) -> dict[str, object]:
    expected_base = 295 * len(CASES) * len(EDGE_MODES)
    if len(base_measurements) != expected_base:
        raise AssertionError(f"expected {expected_base} base measurements, got {len(base_measurements)}")
    expected_summary = len(SELECTIONS) * len(EDGE_MODES) * 6 * len(CASES)
    if len(summary) != expected_summary:
        raise AssertionError(f"expected {expected_summary} summary rows, got {len(summary)}")
    expected_comparison = len(SELECTIONS) * len(EDGE_MODES) * 6
    if len(comparison) != expected_comparison:
        raise AssertionError(
            f"expected {expected_comparison} comparison rows, got {len(comparison)}"
        )
    for (selection, edge_mode), part in selected_measurements.groupby(
        ["selection", "edge_mode"], sort=False
    ):
        counts = part.groupby(["dataset", "group", "step_index"])["case"].nunique()
        if not (counts == len(CASES)).all():
            raise AssertionError(f"case mismatch in {selection}/{edge_mode}")
    return {
        "base_measurement_rows": int(len(base_measurements)),
        "selected_measurement_rows": int(len(selected_measurements)),
        "valid_measurement_rows": int(selected_measurements["ok"].sum()),
        "summary_rows": int(len(summary)),
        "comparison_rows": int(len(comparison)),
        "source_unique_steps": 295,
    }


def main() -> None:
    ensure_dirs()
    source = load_source_rows()
    base_path = TABLE_DIR / "all_steps_base_measurements.csv"
    if base_path.exists():
        cached = pd.read_csv(base_path)
        expected_rows = 295 * len(CASES) * len(EDGE_MODES)
        if len(cached) == expected_rows:
            print(f"reusing {len(cached)} completed base measurements", flush=True)
            base_measurements = cached
        else:
            base_measurements = measure_all_steps(source)
    else:
        base_measurements = measure_all_steps(source)
    base_measurements.to_csv(
        base_path, index=False, encoding="utf-8-sig"
    )
    selected_measurements = attach_selections(base_measurements)
    summary = summarize(selected_measurements)
    comparison = build_comparison(summary)
    preferred = comparison[
        comparison["edge_mode"] == "v41_standalone_guided_edges"
    ].copy()
    v42_guided_control = comparison[
        comparison["edge_mode"] == "v42_e120_guided_edges"
    ].copy()

    selected_measurements.to_csv(
        TABLE_DIR / "step_measurements.csv", index=False, encoding="utf-8-sig"
    )
    summary.to_csv(TABLE_DIR / "summary_by_case.csv", index=False, encoding="utf-8-sig")
    comparison.to_csv(TABLE_DIR / "comparison_vs_raw.csv", index=False, encoding="utf-8-sig")
    preferred.to_csv(
        TABLE_DIR / "recommended_established_shared_edges.csv",
        index=False,
        encoding="utf-8-sig",
    )
    v42_guided_control.to_csv(
        TABLE_DIR / "supplement_v42_guided_edges.csv",
        index=False,
        encoding="utf-8-sig",
    )
    with pd.ExcelWriter(TABLE_DIR / "v42_local_edge_validation.xlsx") as writer:
        preferred.to_excel(writer, sheet_name="preferred", index=False)
        comparison.to_excel(writer, sheet_name="comparison", index=False)
        summary.to_excel(writer, sheet_name="summary", index=False)
        selected_measurements.to_excel(writer, sheet_name="steps", index=False)

    for selection in SELECTIONS:
        for edge_mode in EDGE_MODES:
            plot_comparison(comparison, selection, edge_mode)
    write_report(comparison, selected_measurements)
    counts = verify_outputs(base_measurements, selected_measurements, summary, comparison)
    manifest = {
        "title": "V42 preferred local-edge displacement validation",
        "source_all_steps": str(SOURCE_ALL),
        "source_selected_steps": str(SOURCE_SELECTED),
        "optimized_core": str(CORE_DIR / "local_edge_band_core.py"),
        "cases": CASES,
        "edge_modes": EDGE_MODES,
        "selections": SELECTIONS,
        "preferred_display": {
            "edge_mode": "v41_standalone_guided_edges",
            "selection": "common_best30",
        },
        "counts": counts,
        "generated_at": pd.Timestamp.now().isoformat(timespec="seconds"),
    }
    (OUT_ROOT / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(counts, indent=2), flush=True)
    print(OUT_ROOT, flush=True)


if __name__ == "__main__":
    main()

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import wilcoxon


ROOT = Path(__file__).resolve().parents[1]
TABLES = ROOT / "tables"
TABLES.mkdir(parents=True, exist_ok=True)

SOURCE_ANALYSIS = Path(
    r"D:\GMM_2_Final\Thesis_MOSR_Evidence\Final_Data_Figures"
    r"\04_V42_NEURAL_NETWORK_RESULTS\source_validation"
    r"\100mg_linewidth_generalization_20260719\scripts"
    r"\analyze_100mg_linewidth_generalization.py"
)
WIENER_ROOT = ROOT / "wiener_crops"


def load_source_module():
    spec = importlib.util.spec_from_file_location("linewidth_source_analysis", SOURCE_ANALYSIS)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not import {SOURCE_ANALYSIS}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def build_stability_summary(step_table: pd.DataFrame, scope: str) -> pd.DataFrame:
    rows: list[dict] = []
    group_columns = ["sequence", "method"] if scope == "by_sequence" else ["method"]
    for keys, group in step_table.groupby(group_columns, sort=False):
        if scope == "by_sequence":
            sequence, method = keys
        else:
            sequence, method = "pooled", keys[0] if isinstance(keys, tuple) else keys
        boundary = group.boundary_signed_error_nm.dropna().to_numpy(float)
        profile = group.profile_signed_error_nm.dropna().to_numpy(float)
        rows.append(
            {
                "scope": sequence,
                "method": method,
                "step_rows": int(len(group)),
                "boundary_valid_steps": int(len(boundary)),
                "boundary_mae_nm": float(np.mean(np.abs(boundary))),
                "boundary_residual_sd_nm": float(np.std(boundary, ddof=1)),
                "boundary_median_abs_error_nm": float(np.median(np.abs(boundary))),
                "profile_valid_steps": int(len(profile)),
                "profile_mae_nm": float(np.mean(np.abs(profile))),
                "profile_residual_sd_nm": float(np.std(profile, ddof=1)),
                "profile_median_abs_error_nm": float(np.median(np.abs(profile))),
                "median_within_edge_mad_nm": float(group.within_edge_mad_nm.median()),
                "median_usable_edges": float(group.usable_edges.median()),
            }
        )
    return pd.DataFrame(rows)


def build_reconstruction_vs_raw(step_table: pd.DataFrame, methods: tuple[str, ...]) -> pd.DataFrame:
    rows: list[dict] = []
    for estimator, column in (
        ("shared_edge", "boundary_step_um"),
        ("full_profile", "profile_step_um"),
    ):
        wide = step_table.pivot_table(
            index=["sequence", "end_frame_index"], columns="method", values=column
        )
        for method in methods:
            paired = wide[["Raw", method]].dropna()
            differences_nm = (paired[method] - paired["Raw"]) * 1000.0
            for sequence in sorted(paired.index.get_level_values("sequence").unique()):
                values = differences_nm.xs(sequence, level="sequence").to_numpy(float)
                rows.append(
                    {
                        "scope": sequence,
                        "estimator": estimator,
                        "candidate_method": method,
                        "paired_step_count": int(len(values)),
                        "mean_absolute_difference_from_raw_nm": float(np.mean(np.abs(values))),
                        "median_absolute_difference_from_raw_nm": float(np.median(np.abs(values))),
                        "mean_signed_difference_from_raw_nm": float(np.mean(values)),
                    }
                )
            values = differences_nm.to_numpy(float)
            rows.append(
                {
                    "scope": "pooled_all_available_steps",
                    "estimator": estimator,
                    "candidate_method": method,
                    "paired_step_count": int(len(values)),
                    "mean_absolute_difference_from_raw_nm": float(np.mean(np.abs(values))),
                    "median_absolute_difference_from_raw_nm": float(np.median(np.abs(values))),
                    "mean_signed_difference_from_raw_nm": float(np.mean(values)),
                }
            )
    return pd.DataFrame(rows)


def build_mosr_pairwise(step_table: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict] = []
    for metric in (
        "boundary_abs_error_nm",
        "profile_abs_error_nm",
        "within_edge_mad_nm",
    ):
        wide = step_table.pivot_table(
            index=["sequence", "end_frame_index"], columns="method", values=metric
        )
        for competitor in ("Base U-Net", "Wiener"):
            paired = wide[["MOSR", competitor]].dropna()
            mosr = paired["MOSR"].to_numpy(float)
            comparison = paired[competitor].to_numpy(float)
            try:
                statistic, p_value = wilcoxon(mosr, comparison, zero_method="wilcox")
            except ValueError:
                statistic, p_value = float("nan"), float("nan")
            rows.append(
                {
                    "metric": metric,
                    "competitor": competitor,
                    "paired_step_count": int(len(paired)),
                    "mosr_mean_nm": float(np.mean(mosr)),
                    "competitor_mean_nm": float(np.mean(comparison)),
                    "mosr_minus_competitor_mean_nm": float(np.mean(mosr - comparison)),
                    "mosr_better_step_fraction": float(np.mean(mosr < comparison)),
                    "wilcoxon_statistic": float(statistic),
                    "wilcoxon_p_value": float(p_value),
                }
            )
    return pd.DataFrame(rows)


def main() -> None:
    source = load_source_module()
    methods = ("Raw", "Wiener", "Base U-Net", "MOSR")
    source.METHODS = methods
    source.SEQUENCES["50x_x_0p5um"]["wiener"] = WIENER_ROOT / "50x_x_0p5um"
    source.SEQUENCES["50x_x_1um"]["wiener"] = WIENER_ROOT / "50x_x_1um"

    original_roi = dict(source.ROIS["vertical_lines"])
    source.ROIS["vertical_lines"] = {
        "label": "Vertical-line region",
        "x": 0,
        "y": 0,
        "width": int(original_roi["width"]),
        "height": int(original_roi["height"]),
        "profile_axis": 0,
    }

    original_read = source.read_gray

    def read_line_crop(path: Path) -> np.ndarray:
        image = original_read(path)
        if image.shape == (int(original_roi["height"]), int(original_roi["width"])):
            return image
        return source.crop_image(image, original_roi)

    def method_directory(sequence: dict, method: str) -> Path:
        return {
            "Raw": sequence["raw"],
            "Wiener": sequence["wiener"],
            "Base U-Net": sequence["base"],
            "MOSR": sequence["mosr"],
        }[method]

    source.read_gray = read_line_crop
    source.method_directory = method_directory

    selection = pd.read_csv(source.SELECTION_PATH)
    selection = selection.loc[
        source.truthy(selection.top30_raw_motion_selected)
        & selection.sequence.isin(source.SEQUENCES),
        :,
    ].copy()
    if len(selection) != 60:
        raise RuntimeError(f"Expected 60 pre-locked steps, found {len(selection)}")

    for sequence_name, sequence in source.SEQUENCES.items():
        required_frames = range(0, 51 if sequence_name == "50x_x_0p5um" else 50)
        for method in methods:
            missing = [
                frame
                for frame in required_frames
                if not source.frame_path(sequence, method, frame).is_file()
            ]
            if missing:
                raise FileNotFoundError(
                    f"{sequence_name} {method} is missing {len(missing)} frames"
                )

    selected_edge, selected_step = source.analyze_displacement(selection)
    all_selection = source.all_available_step_selection()
    all_edge, all_step = source.analyze_displacement(all_selection)

    expected_selected_rows = 60 * len(methods)
    expected_all_rows = 99 * len(methods)
    if len(selected_step) != expected_selected_rows:
        raise RuntimeError(
            f"Expected {expected_selected_rows} selected-step rows, found {len(selected_step)}"
        )
    if len(all_step) != expected_all_rows:
        raise RuntimeError(f"Expected {expected_all_rows} all-step rows, found {len(all_step)}")
    selected_valid = selected_step[["boundary_step_um", "profile_step_um"]].notna().all(axis=1)
    if not selected_valid.all():
        raise RuntimeError("A selected displacement step is missing")
    all_valid_fraction = float(
        all_step[["boundary_step_um", "profile_step_um"]].notna().all(axis=1).mean()
    )
    if all_valid_fraction < 0.95:
        raise RuntimeError(f"All-step valid fraction is only {all_valid_fraction:.1%}")

    selected_by_sequence = build_stability_summary(selected_step, "by_sequence")
    selected_pooled = build_stability_summary(selected_step, "pooled")
    all_by_sequence = build_stability_summary(all_step, "by_sequence")
    all_pooled = build_stability_summary(all_step, "pooled")
    all_agreement = build_reconstruction_vs_raw(all_step, methods[1:])
    pairwise = build_mosr_pairwise(selected_step)

    outputs = {
        "selected_steps.csv": selection,
        "selected_displacement_per_edge.csv": selected_edge,
        "selected_displacement_per_step.csv": selected_step,
        "selected_stability_by_sequence.csv": selected_by_sequence,
        "selected_stability_pooled.csv": selected_pooled,
        "selected_mosr_pairwise.csv": pairwise,
        "all_available_displacement_per_edge.csv": all_edge,
        "all_available_displacement_per_step.csv": all_step,
        "all_available_stability_by_sequence.csv": all_by_sequence,
        "all_available_stability_pooled.csv": all_pooled,
        "all_available_reconstruction_vs_raw.csv": all_agreement,
    }
    for filename, table in outputs.items():
        table.to_csv(TABLES / filename, index=False, encoding="utf-8-sig")

    manifest = {
        "purpose": "Four-way displacement-stability comparison on the 100MG vertical-line region",
        "methods": list(methods),
        "object_um_per_pixel": source.PIXEL_UM,
        "line_roi": original_roi,
        "selected_step_count": int(len(selection)),
        "all_available_step_count": int(len(all_selection)),
        "wiener": json.loads((ROOT / "wiener_linewidth_manifest.json").read_text(encoding="utf-8")),
        "measurement": {
            "primary": "shared Raw-guided individual 50 percent line-edge crossings",
            "independent_check": "subpixel correlation of the full median line profile",
            "stability": "standard deviation of step residuals after subtracting the sequence nominal increment",
        },
        "qa": {
            "selected_step_rows": int(len(selected_step)),
            "selected_edge_rows": int(len(selected_edge)),
            "all_available_step_rows": int(len(all_step)),
            "all_available_edge_rows": int(len(all_edge)),
            "selected_rows_valid": bool(selected_valid.all()),
            "all_available_row_valid_fraction": all_valid_fraction,
        },
    }
    (ROOT / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    print("SELECTED POOLED")
    print(selected_pooled.to_string(index=False))
    print("\nSELECTED BY SEQUENCE")
    print(selected_by_sequence.to_string(index=False))
    print("\nALL-STEP AGREEMENT WITH RAW")
    print(all_agreement[all_agreement.scope == "pooled_all_available_steps"].to_string(index=False))
    print("\nMOSR PAIRWISE")
    print(pairwise.to_string(index=False))
    print("\nQA")
    print(json.dumps(manifest["qa"], indent=2))


if __name__ == "__main__":
    main()

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
PROJECT_ROOT = Path(__file__).resolve().parents[4]


EXPERIMENT = Path(__file__).resolve().parent
RESULTS = EXPERIMENT / "results"
OUTPUT = RESULTS / "analysis"
FIGURES = Path(str(PROJECT_ROOT / 'Thesis_MOSR_Evidence/Final_Data_Figures'))
CURRENT = FIGURES / "01_CURRENT_THESIS_RESULTS_V42_CENTER9"
NETWORK = FIGURES / "04_V42_NEURAL_NETWORK_RESULTS"
WIENER = NETWORK / "source_validation" / "wiener_baseline_20260715"
ANALYSIS_SCRIPT = NETWORK / "scripts" / "analyze_wiener_three_way_results.py"


def load_shared_measurement_module():
    spec = importlib.util.spec_from_file_location("shared_three_way_analysis", ANALYSIS_SCRIPT)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def measure_base_cd(
    module,
    image_path: Path,
    centers: pd.DataFrame,
    radius_px: float | str,
    object_um_per_px: float,
) -> pd.DataFrame:
    image = module._read_gray(image_path)
    rows: list[dict] = []
    thresholds = np.round(np.arange(0.35, 0.651, 0.05), 2)
    measurement_functions = {
        "horizontal_strip": module._measure_half_height_width,
        "radial_mean": module._measure_radial_width,
    }
    for _, center in centers.iterrows():
        local_radius = float(center[radius_px]) if isinstance(radius_px, str) else float(radius_px)
        for threshold in thresholds:
            for mode, function in measurement_functions.items():
                result = function(
                    image,
                    float(center.center_x_px),
                    float(center.center_y_px),
                    local_radius,
                    float(threshold),
                )
                row = {
                    "method": "Base U-Net",
                    "measurement_mode": mode,
                    "threshold_fraction": threshold,
                    "center9_position": int(center.center9_position),
                    "sem_index": int(center.sem_index),
                    "center_x_px": float(center.center_x_px),
                    "center_y_px": float(center.center_y_px),
                    "sem_diameter_um": float(center.sem_diameter_um),
                    "status": result["status"],
                }
                if result["status"] == "ok":
                    diameter_um = float(result["width_px"]) * object_um_per_px
                    signed_error_nm = (diameter_um - float(center.sem_diameter_um)) * 1000.0
                    row.update(
                        {
                            "diameter_um": diameter_um,
                            "signed_error_nm": signed_error_nm,
                            "abs_error_nm": abs(signed_error_nm),
                        }
                    )
                rows.append(row)
    output = pd.DataFrame(rows)
    if len(output) != 126 or not (output.status == "ok").all():
        failed = output.loc[output.status != "ok"]
        raise RuntimeError(f"Base U-Net CD measurement failed: rows={len(output)}, failed={len(failed)}")
    return output


def build_base_cd_tables(module) -> tuple[pd.DataFrame, pd.DataFrame]:
    source50 = pd.read_csv(CURRENT / "cd" / "tables" / "center9_cd_per_pillar.csv")
    centers50 = source50.rename(
        columns={"raw_x_px": "center_x_px", "raw_y_px": "center_y_px"}
    )[
        [
            "center9_position",
            "sem_index",
            "center_x_px",
            "center_y_px",
            "reference_radius_px",
            "sem_diameter_um",
        ]
    ].copy()
    base50 = measure_base_cd(
        module,
        RESULTS / "real_inference" / "static" / "static_50x_center9_base_unet.bmp",
        centers50,
        "reference_radius_px",
        0.069,
    )

    source20 = pd.read_csv(
        WIENER / "supplementary_20x_cd" / "tables" / "20x_frame49_cd_per_measurement.csv"
    )
    centers20 = (
        source20[
            [
                "center9_position",
                "sem_index",
                "center_x_px",
                "center_y_px",
                "sem_diameter_um",
            ]
        ]
        .drop_duplicates()
        .sort_values("center9_position")
        .reset_index(drop=True)
    )
    base20 = measure_base_cd(
        module,
        RESULTS / "real_inference" / "static" / "static_20x_frame49_base_unet.bmp",
        centers20,
        7.6,
        0.1725,
    )
    return base50, base20


def truthy(series: pd.Series) -> pd.Series:
    if series.dtype == bool:
        return series
    return series.astype(str).str.lower().isin({"true", "1", "yes"})


def build_base_displacement_table() -> tuple[pd.DataFrame, dict[str, float]]:
    selection = pd.read_csv(NETWORK / "tables" / "top30_raw_motion_selection.csv")
    selection = selection.loc[truthy(selection.top30_raw_motion_selected)].copy()
    audit = pd.read_csv(
        RESULTS / "displacement_audit" / "tables" / "all_adjacent_pairs_audit.csv"
    )
    table = selection[["sequence", "end_frame_index"]].merge(
        audit,
        on=["sequence", "end_frame_index"],
        how="left",
        validate="one_to_one",
    )
    if len(table) != 120 or table.groupby("sequence").size().nunique() != 1:
        raise RuntimeError("The locked top-30 displacement population was not reproduced")
    if not truthy(table.v42_evaluable).all():
        raise RuntimeError("At least one Base U-Net top-30 displacement pair is not evaluable")
    table = table.rename(
        columns={
            "v42_boundary_dx_um": "base_unet_boundary_dx_um",
            "v42_within_grid_nm": "base_unet_within_grid_nm",
            "v42_boundary_valid_pillars": "base_unet_valid_pillars",
        }
    )
    table["base_unet_reference_abs_error_nm"] = (
        table.base_unet_boundary_dx_um - table.expected_signed_step_um
    ).abs() * 1000.0
    summary = {
        "paired_step_count": int(len(table)),
        "reference_mae_nm": float(table.base_unet_reference_abs_error_nm.mean()),
        "nine_pillar_inconsistency_mean_nm": float(table.base_unet_within_grid_nm.mean()),
        "nine_pillar_inconsistency_median_nm": float(table.base_unet_within_grid_nm.median()),
    }
    return table, summary


def pooled_cd_summary(table: pd.DataFrame) -> dict[str, float]:
    per_pillar = table.groupby("center9_position", sort=True)
    return {
        "observation_count": int(len(table)),
        "pillar_count": int(table.center9_position.nunique()),
        "pooled_median_abs_error_nm": float(table.abs_error_nm.median()),
        "pooled_mean_abs_error_nm": float(table.abs_error_nm.mean()),
        "median_pillar_range_nm": float(
            (per_pillar.diameter_um.max() - per_pillar.diameter_um.min()).median() * 1000.0
        ),
    }


def build_method_summary(
    base50: pd.DataFrame,
    base20: pd.DataFrame,
    base_displacement: dict[str, float],
) -> pd.DataFrame:
    cd50 = pd.read_csv(WIENER / "tables" / "three_way_cd_robust_summary.csv").set_index("case")
    cd20 = pd.read_csv(
        WIENER / "supplementary_20x_cd" / "tables" / "20x_frame49_cd_summary.csv"
    ).set_index("case")
    displacement = pd.read_csv(
        WIENER / "tables" / "three_way_displacement_pooled.csv"
    ).set_index("population").loc["All paired steps"]
    base50_summary = pooled_cd_summary(base50)
    base20_summary = pooled_cd_summary(base20)

    rows = [
        {
            "method": "Raw",
            "cd_50x_median_abs_error_nm": float(cd50.loc["raw", "pooled_median_abs_error_nm"]),
            "cd_20x_median_abs_error_nm": float(cd20.loc["raw", "pooled_median_abs_error_nm"]),
            "displacement_reference_mae_nm": float(displacement.raw_command_mae_nm),
            "nine_pillar_inconsistency_mean_nm": float(displacement.raw_within_mean_nm),
        },
        {
            "method": "Wiener",
            "cd_50x_median_abs_error_nm": float(cd50.loc["wiener", "pooled_median_abs_error_nm"]),
            "cd_20x_median_abs_error_nm": float(cd20.loc["wiener", "pooled_median_abs_error_nm"]),
            "displacement_reference_mae_nm": float(displacement.wiener_command_mae_nm),
            "nine_pillar_inconsistency_mean_nm": float(displacement.wiener_within_mean_nm),
        },
        {
            "method": "Base U-Net",
            "cd_50x_median_abs_error_nm": base50_summary["pooled_median_abs_error_nm"],
            "cd_20x_median_abs_error_nm": base20_summary["pooled_median_abs_error_nm"],
            "displacement_reference_mae_nm": base_displacement["reference_mae_nm"],
            "nine_pillar_inconsistency_mean_nm": base_displacement[
                "nine_pillar_inconsistency_mean_nm"
            ],
        },
        {
            "method": "MOSR",
            "cd_50x_median_abs_error_nm": float(cd50.loc["v42_e120", "pooled_median_abs_error_nm"]),
            "cd_20x_median_abs_error_nm": float(cd20.loc["mosr", "pooled_median_abs_error_nm"]),
            "displacement_reference_mae_nm": float(displacement.v42_command_mae_nm),
            "nine_pillar_inconsistency_mean_nm": float(displacement.v42_within_mean_nm),
        },
    ]
    return pd.DataFrame(rows)


def main(results_root: Path) -> None:
    global RESULTS, OUTPUT
    RESULTS = results_root
    OUTPUT = results_root / "analysis"
    OUTPUT.mkdir(parents=True, exist_ok=True)
    module = load_shared_measurement_module()
    base50, base20 = build_base_cd_tables(module)
    displacement_table, displacement_summary = build_base_displacement_table()
    method_summary = build_method_summary(base50, base20, displacement_summary)

    base50.to_csv(OUTPUT / "base_unet_cd_50x_per_measurement.csv", index=False, encoding="utf-8-sig")
    base20.to_csv(OUTPUT / "base_unet_cd_20x_per_measurement.csv", index=False, encoding="utf-8-sig")
    displacement_table.to_csv(
        OUTPUT / "base_unet_displacement_top30_per_step.csv", index=False, encoding="utf-8-sig"
    )
    method_summary.to_csv(
        OUTPUT / "learning_baseline_method_summary.csv", index=False, encoding="utf-8-sig"
    )

    manifest = {
        "purpose": "Same-ruler learning baseline comparison for thesis Section 6.2.6",
        "cd_50x": pooled_cd_summary(base50),
        "cd_20x": pooled_cd_summary(base20),
        "displacement": displacement_summary,
        "method_summary": method_summary.to_dict(orient="records"),
        "qa": {
            "cd_50x_rows": int(len(base50)),
            "cd_20x_rows": int(len(base20)),
            "top30_displacement_rows": int(len(displacement_table)),
            "all_cd_status_ok": bool((base50.status == "ok").all() and (base20.status == "ok").all()),
            "all_displacement_evaluable": bool(truthy(displacement_table.v42_evaluable).all()),
        },
    }
    (OUTPUT / "analysis_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(method_summary.to_string(index=False))
    print(json.dumps(manifest["qa"], indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--results-root", type=Path, default=RESULTS)
    arguments = parser.parse_args()
    main(arguments.results_root.resolve())

from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from scipy.stats import wilcoxon


EXPERIMENT = Path(__file__).resolve().parent
MANIFEST_PATH = EXPERIMENT / "evaluation_manifest.json"
SOURCE_SCRIPT = Path(
    r"D:\GMM_2_Final\Thesis_MOSR_Evidence\Final_Data_Figures"
    r"\04_V42_NEURAL_NETWORK_RESULTS\source_validation"
    r"\100mg_linewidth_generalization_20260719\scripts"
    r"\analyze_100mg_linewidth_generalization.py"
)


def load_source_module():
    spec = importlib.util.spec_from_file_location("line_source_analysis", SOURCE_SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not import {SOURCE_SCRIPT}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def build_sequences(manifest: dict[str, Any], methods: list[str]) -> dict[str, dict[str, Any]]:
    source_config = json.loads(Path(manifest["pillar_config"]).read_text(encoding="utf-8"))
    output: dict[str, dict[str, Any]] = {}
    for sequence_name in ("50x_x_0p5um", "50x_x_1um"):
        sequence = source_config["sequences"][sequence_name]
        directories: dict[str, Path] = {"Raw": Path(sequence["raw_dir"])}
        for method in methods:
            if method == "Raw":
                continue
            root = Path(manifest["methods"][method]["sequence_root"])
            mapped = manifest["sequence_name_map"][sequence_name][method]
            directories[method] = root / mapped
        output[sequence_name] = {
            "nominal_step_um": float(sequence["nominal_step_um"]),
            "directories": directories,
        }
    return output


def available_methods(
    manifest: dict[str, Any],
    allow_missing: bool,
) -> list[str]:
    methods: list[str] = []
    for method in manifest["methods"]:
        if method == "Raw":
            methods.append(method)
            continue
        root = Path(manifest["methods"][method]["sequence_root"])
        required = [
            root / manifest["sequence_name_map"][sequence][method] / "frame_0000.bmp"
            for sequence in ("50x_x_0p5um", "50x_x_1um")
        ]
        if all(path.is_file() for path in required):
            methods.append(method)
        elif allow_missing:
            print(f"Skipping unavailable line method: {method}", flush=True)
        else:
            raise FileNotFoundError(next(path for path in required if not path.is_file()))
    return methods


def displacement_summary(step_table: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    per_sequence: list[dict[str, object]] = []
    for (sequence, method), group in step_table.groupby(["sequence", "method"], sort=False):
        error = group["boundary_signed_error_nm"].dropna().to_numpy(dtype=float)
        profile_error = group["profile_signed_error_nm"].dropna().to_numpy(dtype=float)
        per_sequence.append(
            {
                "sequence": sequence,
                "nominal_step_um": float(group["nominal_step_um"].iloc[0]),
                "method": method,
                "step_count": len(group),
                "boundary_valid_steps": int(group["boundary_step_um"].notna().sum()),
                "boundary_bias_nm": float(np.mean(error)),
                "boundary_mae_nm": float(np.mean(np.abs(error))),
                "boundary_rmse_nm": float(np.sqrt(np.mean(error**2))),
                "boundary_error_sd_nm": float(np.std(error, ddof=1)),
                "median_within_edge_mad_nm": float(group["within_edge_mad_nm"].median()),
                "profile_valid_steps": int(group["profile_step_um"].notna().sum()),
                "profile_bias_nm": float(np.mean(profile_error)),
                "profile_mae_nm": float(np.mean(np.abs(profile_error))),
                "profile_rmse_nm": float(np.sqrt(np.mean(profile_error**2))),
                "profile_error_sd_nm": float(np.std(profile_error, ddof=1)),
            }
        )
    pooled: list[dict[str, object]] = []
    for method, group in step_table.groupby("method", sort=False):
        error = group["boundary_signed_error_nm"].dropna().to_numpy(dtype=float)
        profile_error = group["profile_signed_error_nm"].dropna().to_numpy(dtype=float)
        pooled.append(
            {
                "method": method,
                "step_count": len(group),
                "boundary_valid_steps": int(group["boundary_step_um"].notna().sum()),
                "boundary_bias_nm": float(np.mean(error)),
                "boundary_mae_nm": float(np.mean(np.abs(error))),
                "boundary_median_absolute_error_nm": float(np.median(np.abs(error))),
                "boundary_rmse_nm": float(np.sqrt(np.mean(error**2))),
                "boundary_error_sd_nm": float(np.std(error, ddof=1)),
                "median_within_edge_mad_nm": float(group["within_edge_mad_nm"].median()),
                "profile_valid_steps": int(group["profile_step_um"].notna().sum()),
                "profile_bias_nm": float(np.mean(profile_error)),
                "profile_mae_nm": float(np.mean(np.abs(profile_error))),
                "profile_median_absolute_error_nm": float(np.median(np.abs(profile_error))),
                "profile_rmse_nm": float(np.sqrt(np.mean(profile_error**2))),
                "profile_error_sd_nm": float(np.std(profile_error, ddof=1)),
            }
        )
    return pd.DataFrame(per_sequence), pd.DataFrame(pooled)


def paired_tests(step_table: pd.DataFrame, methods: list[str]) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for metric in ("boundary_abs_error_nm", "profile_abs_error_nm"):
        wide = step_table.pivot_table(
            index=["sequence", "end_frame_index"],
            columns="method",
            values=metric,
        ).reindex(columns=methods)
        common = wide.dropna()
        for reference in ("Raw", "MOSR"):
            if reference not in common:
                continue
            for candidate in methods:
                if candidate == reference:
                    continue
                difference = common[candidate] - common[reference]
                try:
                    statistic, p_value = wilcoxon(
                        common[candidate], common[reference], zero_method="wilcox"
                    )
                except ValueError:
                    statistic, p_value = np.nan, np.nan
                rows.append(
                    {
                        "metric": metric,
                        "reference_method": reference,
                        "candidate_method": candidate,
                        "common_step_count": len(common),
                        "reference_mean_nm": float(common[reference].mean()),
                        "candidate_mean_nm": float(common[candidate].mean()),
                        "candidate_minus_reference_mean_nm": float(difference.mean()),
                        "candidate_minus_reference_median_nm": float(difference.median()),
                        "wilcoxon_statistic": float(statistic),
                        "wilcoxon_p_value": float(p_value),
                    }
                )
    return pd.DataFrame(rows)


def main(output_root: Path, allow_missing: bool) -> None:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    methods = available_methods(manifest, allow_missing)
    sequences = build_sequences(manifest, methods)
    module = load_source_module()
    module.OUTPUT = output_root
    module.TABLES = output_root / "tables"
    module.CROPS = output_root / "images"
    module.METHODS = tuple(methods)
    module.SEQUENCES = sequences

    def method_directory(sequence: dict[str, Any], method: str) -> Path:
        return sequence["directories"][method]

    module.method_directory = method_directory
    module.TABLES.mkdir(parents=True, exist_ok=True)
    module.CROPS.mkdir(parents=True, exist_ok=True)
    selection = pd.read_csv(manifest["top30_selection"])
    selection = selection.loc[
        module.truthy(selection["top30_raw_motion_selected"])
        & selection["sequence"].isin(sequences),
        :,
    ].copy()
    module.validate_inputs(selection)
    module.export_reference_images()
    edge_table, frame_table = module.analyze_sharpness(selection)
    edge_shift_table, step_table = module.analyze_displacement(selection)
    sharpness = module.build_sharpness_summary(frame_table)
    by_sequence, pooled = displacement_summary(step_table)
    tests = paired_tests(step_table, methods)

    expected_frame_rows = 60 * 2 * len(methods)
    expected_step_rows = 60 * len(methods)
    if len(frame_table) != expected_frame_rows:
        raise RuntimeError(f"Expected {expected_frame_rows} frame rows, found {len(frame_table)}")
    if len(step_table) != expected_step_rows:
        raise RuntimeError(f"Expected {expected_step_rows} step rows, found {len(step_table)}")
    if frame_table["valid_edges"].min() < 10:
        raise RuntimeError("At least one line frame has fewer than ten valid edges")
    if (step_table["usable_edges"] < 8).any():
        raise RuntimeError("At least one line step has fewer than eight usable edges")
    if step_table[["boundary_step_um", "profile_step_um"]].isna().any().any():
        raise RuntimeError("At least one line displacement result is missing")

    outputs = {
        "locked_50x_steps.csv": selection,
        "line_edge_measurements.csv": edge_table,
        "line_frame_metrics.csv": frame_table,
        "line_sharpness_summary.csv": sharpness,
        "line_displacement_per_edge.csv": edge_shift_table,
        "line_displacement_per_step.csv": step_table,
        "line_displacement_by_sequence.csv": by_sequence,
        "line_displacement_pooled.csv": pooled,
        "line_displacement_paired_tests.csv": tests,
    }
    for name, table in outputs.items():
        table.to_csv(module.TABLES / name, index=False, encoding="utf-8-sig")
    metadata = {
        "purpose": "Five-method line-pattern sharpness and displacement comparison",
        "methods": methods,
        "selection": "Same pre-locked best 30 Raw-motion steps per 50x sequence",
        "step_count": 60,
        "object_um_per_px": module.PIXEL_UM,
        "rois": module.ROIS,
        "measurement": {
            "sharpness": "Raw-defined shared edge candidates and native 10%-90% edge width",
            "boundary_displacement": "Median shift of common individual 50% line-edge crossings",
            "profile_displacement": "Independent subpixel correlation of the full median line profile",
        },
        "qa": {
            "frame_metric_rows": len(frame_table),
            "step_rows": len(step_table),
            "minimum_valid_edges_per_frame": int(frame_table["valid_edges"].min()),
            "minimum_usable_edges_per_step": int(step_table["usable_edges"].min()),
            "all_steps_valid": True,
        },
    }
    (output_root / "metadata.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(sharpness.to_string(index=False), flush=True)
    print(pooled.to_string(index=False), flush=True)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output-root",
        type=Path,
        default=EXPERIMENT / "evaluation" / "line",
    )
    parser.add_argument("--allow-missing", action="store_true")
    return parser.parse_args()


if __name__ == "__main__":
    arguments = parse_args()
    main(arguments.output_root.resolve(), arguments.allow_missing)

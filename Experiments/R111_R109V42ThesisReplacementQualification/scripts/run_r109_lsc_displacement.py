"""Run the exact R80 ACM-inflection-LSC displacement pipeline on R109 E48."""
from __future__ import annotations

import importlib.util
import json
import sys
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
PROJECT_ROOT = Path(__file__).resolve().parents[3]


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "results" / "lsc_displacement"
TABLES = OUTPUT / "tables"
FIGURES = OUTPUT / "figures"
QA = OUTPUT / "qa"
for directory in (TABLES, FIGURES, QA):
    directory.mkdir(parents=True, exist_ok=True)

R80_ROOT = Path(str(PROJECT_ROOT / 'Experiments/R80_InflectionReferenceCircleSEMValidation'))
R80_SCRIPT = R80_ROOT / "scripts" / "run_displacement_lsc.py"
R109_CONFIG = ROOT / "config" / "r109_thesis_sequence_config.json"
TOP30 = Path(
    str(PROJECT_ROOT / 'Thesis_MOSR_Evidence/Final_Data_Figures/04_V42_NEURAL_NETWORK_RESULTS/tables/top30_raw_motion_selection.csv')
)


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot import {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def truthy(values: pd.Series) -> pd.Series:
    if values.dtype == bool:
        return values
    return values.astype(str).str.lower().isin({"true", "1", "yes"})


def main() -> int:
    sys.path.insert(0, str(R80_ROOT / "scripts"))
    module = load_module(R80_SCRIPT, "r111_r109_lsc")
    module.RESULTS = OUTPUT
    module.TABLES = TABLES
    module.FIGURES = FIGURES
    module.QA = QA
    module.CONFIG_PATH = R109_CONFIG
    module.COLORS = {"Raw": "#555555", "Wiener": "#D97904", "MOSR": "#1464F4"}

    config = json.loads(R109_CONFIG.read_text(encoding="utf-8"))
    sequences = ["50x_x_0p5um", "50x_x_1um", "20x_0p5um", "20x_1um"]
    centers_all: list[pd.DataFrame] = []
    pairs_all: list[pd.DataFrame] = []
    selection_all: list[pd.DataFrame] = []
    for sequence in sequences:
        print(f"processing {sequence}", flush=True)
        selection = module.selected_pairs(sequence, limit_pairs=30)
        selection_all.append(selection.assign(sequence_locked=sequence))
        centers, pairs = module.process_sequence(sequence, config, 30)
        centers_all.append(centers)
        pairs_all.append(pairs)
        print(
            json.dumps(
                {
                    "sequence": sequence,
                    "frames": int(centers["frame_index"].nunique()),
                    "centers": len(centers),
                    "pairs": len(pairs),
                }
            ),
            flush=True,
        )

    centers = pd.concat(centers_all, ignore_index=True)
    per_pair = pd.concat(pairs_all, ignore_index=True)
    selection = pd.concat(selection_all, ignore_index=True)
    summary = module.summarize_pairs(per_pair)

    expected_selection = pd.read_csv(
        R80_ROOT / "results" / "tables" / "displacement_raw_locked_selection_all.csv"
    )[["sequence", "start_frame_index", "end_frame_index"]]
    actual_keys = selection[["sequence", "start_frame_index", "end_frame_index"]]
    joined = expected_selection.merge(actual_keys, on=["sequence", "start_frame_index", "end_frame_index"], how="outer", indicator=True)
    if len(expected_selection) != 120 or len(actual_keys) != 120 or not (joined["_merge"] == "both").all():
        raise RuntimeError("R109 LSC selection differs from the historical R80 LSC list")

    current_top30 = pd.read_csv(TOP30)
    current_top30 = current_top30.loc[truthy(current_top30["top30_raw_motion_selected"]), ["sequence", "end_frame_index"]].copy()
    current_top30["start_frame_index"] = current_top30["end_frame_index"].astype(int) - 1
    current_top30 = current_top30[["sequence", "start_frame_index", "end_frame_index"]]
    overlap = current_top30.merge(actual_keys, on=["sequence", "start_frame_index", "end_frame_index"], how="inner")

    centers["method"] = centers["method"].replace({"MOSR": "R109 E48"})
    per_pair["method"] = per_pair["method"].replace({"MOSR": "R109 E48"})
    summary["method"] = summary["method"].replace({"MOSR": "R109 E48"})
    centers.to_csv(TABLES / "r109_lsc_centers_all.csv", index=False, encoding="utf-8-sig")
    per_pair.to_csv(TABLES / "r109_lsc_per_pair_all.csv", index=False, encoding="utf-8-sig")
    selection.to_csv(TABLES / "r109_lsc_raw_locked_selection_all.csv", index=False, encoding="utf-8-sig")
    summary.to_csv(TABLES / "r109_lsc_summary_all.csv", index=False, encoding="utf-8-sig")

    historical_pairs = pd.read_csv(R80_ROOT / "results" / "tables" / "displacement_lsc_per_pair_all.csv", encoding="utf-8-sig")
    historical_summary = pd.read_csv(R80_ROOT / "results" / "tables" / "displacement_lsc_summary_all.csv", encoding="utf-8-sig")
    keys = ["sequence", "start_frame_index", "end_frame_index", "method"]
    reproduced = per_pair.loc[per_pair["method"].isin(["Raw", "Wiener"])].copy()
    historical_rw = historical_pairs.loc[historical_pairs["method"].isin(["Raw", "Wiener"])].copy()
    check = historical_rw.merge(reproduced, on=keys, suffixes=("_historical", "_reproduced"), validate="one_to_one")
    numeric_fields = ["aggregate_dx_um", "aggregate_dy_um", "measured_step_um", "nominal_abs_error_nm", "within_grid_sd_nm", "cross_axis_abs_nm"]
    max_differences = {
        field: float(np.max(np.abs(check[f"{field}_historical"] - check[f"{field}_reproduced"])))
        for field in numeric_fields
    }
    if any(value > 1e-10 for value in max_differences.values()):
        raise RuntimeError(f"Raw/Wiener LSC reproduction mismatch: {max_differences}")

    v42_pairs = historical_pairs.loc[historical_pairs["method"] == "MOSR"].copy()
    v42_pairs["method"] = "V42 E120"
    combined_pairs = pd.concat(
        [
            historical_pairs.loc[historical_pairs["method"].isin(["Raw", "Wiener"])],
            v42_pairs,
            per_pair.loc[per_pair["method"] == "R109 E48"],
        ],
        ignore_index=True,
    )
    combined_summary = module.summarize_pairs(
        combined_pairs.assign(method=combined_pairs["method"].replace({"V42 E120": "V42 E120", "R109 E48": "R109 E48"}))
    )
    combined_pairs.to_csv(TABLES / "four_method_lsc_per_pair_all.csv", index=False, encoding="utf-8-sig")
    combined_summary.to_csv(TABLES / "four_method_lsc_summary_all.csv", index=False, encoding="utf-8-sig")

    combined = combined_summary.loc[combined_summary["scope"] == "all_four_sequences"].set_index("method")
    decision = {
        "status": "complete",
        "generated_local": datetime.now().astimezone().isoformat(),
        "method": "ACM coarse contour + maximum-gradient inflection points + least-squares-circle center",
        "grayscale_threshold_used": False,
        "selection": "historical R80 LSC Raw-ranked 30 pairs per sequence",
        "selection_matches_historical_r80": True,
        "overlap_with_current_chapter62_top30": int(len(overlap)),
        "current_chapter62_top30_total": int(len(current_top30)),
        "pairs_per_sequence": 30,
        "total_pairs": 120,
        "raw_wiener_reproduction_max_differences": max_differences,
        "v42": {
            "step_sd_nm": float(combined.loc["V42 E120", "step_sd_nm"]),
            "mean_nominal_abs_error_nm": float(combined.loc["V42 E120", "mean_nominal_abs_error_nm"]),
            "median_within_grid_sd_nm": float(combined.loc["V42 E120", "median_within_grid_sd_nm"]),
            "median_cross_axis_abs_nm": float(combined.loc["V42 E120", "median_cross_axis_abs_nm"]),
        },
        "r109": {
            "step_sd_nm": float(combined.loc["R109 E48", "step_sd_nm"]),
            "mean_nominal_abs_error_nm": float(combined.loc["R109 E48", "mean_nominal_abs_error_nm"]),
            "median_within_grid_sd_nm": float(combined.loc["R109 E48", "median_within_grid_sd_nm"]),
            "median_cross_axis_abs_nm": float(combined.loc["R109 E48", "median_cross_axis_abs_nm"]),
        },
    }
    decision["comparison"] = {
        "step_sd_change_r109_vs_v42_pct": (decision["r109"]["step_sd_nm"] / decision["v42"]["step_sd_nm"] - 1.0) * 100.0,
        "nominal_mae_change_r109_vs_v42_pct": (decision["r109"]["mean_nominal_abs_error_nm"] / decision["v42"]["mean_nominal_abs_error_nm"] - 1.0) * 100.0,
        "within_grid_change_r109_vs_v42_pct": (decision["r109"]["median_within_grid_sd_nm"] / decision["v42"]["median_within_grid_sd_nm"] - 1.0) * 100.0,
        "cross_axis_change_r109_vs_v42_pct": (decision["r109"]["median_cross_axis_abs_nm"] / decision["v42"]["median_cross_axis_abs_nm"] - 1.0) * 100.0,
    }
    decision["winner_by_metric"] = {
        metric: "R109 E48" if decision["r109"][metric] < decision["v42"][metric] else "V42 E120"
        for metric in decision["v42"]
    }
    (OUTPUT / "lsc_comparison_summary.json").write_text(json.dumps(decision, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(decision, ensure_ascii=False, indent=2), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

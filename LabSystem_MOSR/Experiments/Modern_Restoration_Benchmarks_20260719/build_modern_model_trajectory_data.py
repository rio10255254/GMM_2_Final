from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd


EXPERIMENT = Path(__file__).resolve().parent
INPUT = EXPERIMENT / "evaluation" / "displacement_50x20x_edrs_nafnet_refresh_20260724"
OUTPUT = INPUT / "modern_50x20x_report" / "trajectory_figures"
METHODS = ["Raw", "EDSR", "NAFNet", "MOSR"]
METHOD_LABELS = {"Raw": "Raw", "EDSR": "EDSR-x1", "NAFNet": "NAFNet", "MOSR": "MOSR"}
SEQUENCES = ["50x_x_0p5um", "50x_x_1um", "20x_0p5um", "20x_1um"]


def to_bool(values: pd.Series) -> pd.Series:
    return values.astype(str).str.strip().str.lower().isin({"true", "1", "yes"})


def main() -> None:
    source = INPUT / "displacement_step_measurements.csv"
    if not source.is_file():
        raise FileNotFoundError(source)
    output = OUTPUT
    output.mkdir(parents=True, exist_ok=True)

    table = pd.read_csv(source)
    table = table.loc[table["method"].isin(METHODS)].copy()
    table["evaluable"] = to_bool(table["evaluable"])
    output_rows: list[pd.DataFrame] = []
    availability_rows: list[dict[str, object]] = []

    for morphology in ["pillar", "via"]:
        for sequence in SEQUENCES:
            subset = table.loc[
                table["morphology"].eq(morphology) & table["sequence"].eq(sequence)
            ].copy()
            sequence_keys = (
                subset.loc[subset["method"].eq("Raw"), ["end_frame_index", "raw_motion_quality_rank"]]
                .sort_values("end_frame_index")
                .reset_index(drop=True)
            )
            if len(sequence_keys) != 30:
                raise RuntimeError(f"Expected 30 selected steps for {morphology} {sequence}, found {len(sequence_keys)}")
            sequence_keys["selected_step"] = np.arange(1, len(sequence_keys) + 1)
            for method in METHODS:
                method_rows = subset.loc[subset["method"].eq(method)].merge(
                    sequence_keys, on=["end_frame_index", "raw_motion_quality_rank"], how="inner", validate="one_to_one"
                ).sort_values("selected_step")
                if len(method_rows) != 30:
                    raise RuntimeError(f"Expected 30 rows for {morphology} {sequence} {method}")
                converted = method_rows.loc[:, [
                    "morphology", "sequence", "selected_step", "end_frame_index",
                    "raw_motion_quality_rank", "evaluable", "signed_step_um", "expected_signed_step_um",
                ]].copy()
                converted["method"] = METHOD_LABELS[method]
                converted["measured_amplitude_um"] = np.abs(converted["signed_step_um"].astype(float))
                converted["pi_reference_amplitude_um"] = np.abs(converted["expected_signed_step_um"].astype(float))
                converted.loc[~converted["evaluable"], "measured_amplitude_um"] = np.nan
                output_rows.append(converted)
                availability_rows.append({
                    "morphology": morphology,
                    "sequence": sequence,
                    "method": METHOD_LABELS[method],
                    "selected_steps": 30,
                    "plotted_steps": int(converted["evaluable"].sum()),
                    "missing_steps": int((~converted["evaluable"]).sum()),
                })

    output_table = pd.concat(output_rows, ignore_index=True)
    output_table.to_csv(output / "modern_model_displacement_trajectories.csv", index=False, encoding="utf-8-sig")
    availability = pd.DataFrame(availability_rows)
    availability.to_csv(output / "modern_model_trajectory_availability.csv", index=False, encoding="utf-8-sig")
    metadata = {
        "purpose": "Thirty-step trajectory figures for Raw, EDSR-x1, NAFNet, and MOSR",
        "x_axis": "The selected 30 adjacent-pair measurements in chronological end-frame order; the original raw-motion quality ranks are retained as data but are not used as the x-axis.",
        "y_axis": "Absolute measured displacement amplitude in um; the dashed reference is the absolute PI displacement reference.",
        "selection": "Exactly the same 30 Raw-motion-ranked adjacent pairs used by all methods in each sequence.",
        "missing_data": "A method is plotted as a gap when a selected step is not evaluable; it is never interpolated.",
    }
    (output / "trajectory_metadata.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
    print(availability.to_string(index=False))


if __name__ == "__main__":
    main()

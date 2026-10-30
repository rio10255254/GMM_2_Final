from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import cv2
import numpy as np
import pandas as pd
PROJECT_ROOT = Path(__file__).resolve().parents[3]


EXPERIMENT = Path(__file__).resolve().parent
MANIFEST_PATH = EXPERIMENT / "evaluation_manifest.json"
AUDIT_SCRIPTS = Path(
    str(PROJECT_ROOT / 'Thesis_MOSR_Evidence/Final_Data_Figures/01_CURRENT_THESIS_RESULTS_V42_CENTER9/scripts')
)
if str(AUDIT_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(AUDIT_SCRIPTS))

from audit_all_displacement_sequences import (  # noqa: E402
    APPROVED_SEQUENCES,
    _join_v42,
    _load_mapping,
    _raw_segment_measurements,
)


def read_gray(path: Path) -> np.ndarray:
    image = cv2.imdecode(np.fromfile(path, dtype=np.uint8), cv2.IMREAD_GRAYSCALE)
    if image is None:
        raise FileNotFoundError(path)
    return image


def load_config(path: Path, morphology: str) -> dict[str, dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))["sequences"]
    if morphology == "pillar":
        return payload
    if morphology != "via":
        raise ValueError(morphology)
    converted: dict[str, dict[str, Any]] = {}
    for sequence_name, sequence in payload.items():
        item = dict(sequence)
        item["min_valid_pillars"] = int(item.pop("min_valid_features"))
        item["min_edge_strength"] = 1.0
        item["centers"] = [
            [index, center["x"], center["y"]]
            for index, center in enumerate(item["centers"], start=1)
        ]
        converted[sequence_name] = item
    return converted


def method_sequence_dir(
    manifest: dict[str, Any],
    method: str,
    sequence_name: str,
    raw_dir: Path,
) -> Path:
    if method == "Raw":
        return raw_dir
    root = Path(PROJECT_ROOT / manifest["methods"][method]["sequence_root"])
    mapped_name = manifest["sequence_name_map"][sequence_name][method]
    return root / mapped_name


def load_frames(directory: Path, frame_count: int) -> list[np.ndarray]:
    paths = [directory / f"frame_{index:04d}.bmp" for index in range(frame_count)]
    missing = [path for path in paths if not path.is_file()]
    if missing:
        raise FileNotFoundError(
            f"{directory} is missing {len(missing)} frame(s); first missing: {missing[0].name}"
        )
    return [read_gray(path) for path in paths]


def raw_long_table(sequence_name: str, table: pd.DataFrame) -> pd.DataFrame:
    output = pd.DataFrame(
        {
            "sequence": sequence_name,
            "end_frame_index": table["end_frame_index"].astype(int),
            "method": "Raw",
            "evaluable": table["raw_boundary_valid"].astype(bool)
            & table["raw_boundary_valid_pillars"].eq(9),
            "valid_features": table["raw_boundary_valid_pillars"].astype(int),
            "signed_step_um": table["raw_boundary_dx_um"],
            "within_grid_nm": table["raw_within_grid_nm"],
            "expected_signed_step_um": table["expected_signed_step_um"],
        }
    )
    return output


def learned_long_table(
    sequence_name: str,
    method: str,
    table: pd.DataFrame,
) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "sequence": sequence_name,
            "end_frame_index": table["end_frame_index"].astype(int),
            "method": method,
            "evaluable": table["v42_evaluable"].astype(bool),
            "valid_features": table["v42_boundary_valid_pillars"].astype(int),
            "signed_step_um": table["v42_boundary_dx_um"],
            "within_grid_nm": table["v42_within_grid_nm"],
            "expected_signed_step_um": table["expected_signed_step_um"],
        }
    )


def metric_record(
    morphology: str,
    sequence: str,
    method: str,
    population: str,
    table: pd.DataFrame,
) -> dict[str, object]:
    values = table.loc[
        table["evaluable"].astype(bool)
        & table["signed_step_um"].notna()
        & table["within_grid_nm"].notna()
    ].copy()
    error_nm = (
        values["signed_step_um"].to_numpy(dtype=float)
        - values["expected_signed_step_um"].to_numpy(dtype=float)
    ) * 1000.0
    signed_nm = values["signed_step_um"].to_numpy(dtype=float) * 1000.0
    within = values["within_grid_nm"].to_numpy(dtype=float)
    n = len(values)
    return {
        "morphology": morphology,
        "sequence": sequence,
        "method": method,
        "population": population,
        "n": n,
        "mean_signed_step_nm": float(np.mean(signed_nm)) if n else np.nan,
        "signed_step_sd_nm": float(np.std(signed_nm, ddof=1)) if n > 1 else np.nan,
        "mean_error_nm": float(np.mean(error_nm)) if n else np.nan,
        "error_sd_nm": float(np.std(error_nm, ddof=1)) if n > 1 else np.nan,
        "mae_nm": float(np.mean(np.abs(error_nm))) if n else np.nan,
        "median_absolute_error_nm": float(np.median(np.abs(error_nm))) if n else np.nan,
        "rmse_nm": float(np.sqrt(np.mean(error_nm**2))) if n else np.nan,
        "p95_absolute_error_nm": float(np.percentile(np.abs(error_nm), 95.0)) if n else np.nan,
        "mean_within_grid_nm": float(np.mean(within)) if n else np.nan,
        "median_within_grid_nm": float(np.median(within)) if n else np.nan,
    }


def build_summaries(
    morphology: str,
    long_table: pd.DataFrame,
    method_order: list[str],
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    availability = (
        long_table.groupby(["morphology", "sequence", "method"], sort=False)["evaluable"]
        .agg(selected_count="size", evaluable_count="sum")
        .reset_index()
    )
    availability["evaluable_fraction"] = (
        availability["evaluable_count"] / availability["selected_count"]
    )

    sequence_rows: list[dict[str, object]] = []
    common_rows: list[dict[str, object]] = []
    for sequence in APPROVED_SEQUENCES:
        selected = long_table.loc[long_table["sequence"] == sequence].copy()
        for method in method_order:
            sequence_rows.append(
                metric_record(
                    morphology,
                    sequence,
                    method,
                    "method-valid within Raw-selected top 30",
                    selected.loc[selected["method"] == method],
                )
            )
        validity = selected.pivot(
            index="end_frame_index", columns="method", values="evaluable"
        )
        common_indices = validity.index[
            validity.reindex(columns=method_order).fillna(False).all(axis=1)
        ]
        for method in method_order:
            common_rows.append(
                metric_record(
                    morphology,
                    sequence,
                    method,
                    "common-valid intersection within Raw-selected top 30",
                    selected.loc[
                        selected["method"].eq(method)
                        & selected["end_frame_index"].isin(common_indices)
                    ],
                )
            )

    common = pd.DataFrame(common_rows)
    pooled_rows: list[dict[str, object]] = []
    common_key_table = common.loc[:, ["sequence", "method", "n"]]
    del common_key_table
    for method in method_order:
        pieces: list[pd.DataFrame] = []
        for sequence in APPROVED_SEQUENCES:
            selected = long_table.loc[long_table["sequence"] == sequence]
            validity = selected.pivot(
                index="end_frame_index", columns="method", values="evaluable"
            )
            common_indices = validity.index[
                validity.reindex(columns=method_order).fillna(False).all(axis=1)
            ]
            pieces.append(
                selected.loc[
                    selected["method"].eq(method)
                    & selected["end_frame_index"].isin(common_indices)
                ]
            )
        pooled = pd.concat(pieces, ignore_index=True)
        pooled_rows.append(
            metric_record(
                morphology,
                "all_four_sequences",
                method,
                "pooled common-valid intersection",
                pooled,
            )
        )
    combined = pd.concat(
        [pd.DataFrame(sequence_rows), common, pd.DataFrame(pooled_rows)],
        ignore_index=True,
    )
    return availability, combined, pd.DataFrame(pooled_rows)


def main(
    output_root: Path,
    allow_missing: bool,
    manifest_path: Path = MANIFEST_PATH,
) -> None:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    method_order = list(manifest["methods"])
    top30 = pd.read_csv(manifest["top30_selection"])
    top30 = top30.loc[top30["top30_raw_motion_selected"].astype(bool)].copy()
    if top30.groupby("sequence").size().ne(30).any():
        raise RuntimeError("The locked Raw selection does not contain exactly 30 steps per sequence")

    all_long: list[pd.DataFrame] = []
    all_availability: list[pd.DataFrame] = []
    all_summaries: list[pd.DataFrame] = []
    all_pooled: list[pd.DataFrame] = []

    for morphology, config_key in (("pillar", "pillar_config"), ("via", "via_config")):
        configs = load_config(Path(manifest[config_key]), morphology)
        morphology_long: list[pd.DataFrame] = []
        for sequence_name in APPROVED_SEQUENCES:
            sequence = configs[sequence_name]
            frame_count = int(sequence["frame_count"])
            sessions = _load_mapping(sequence_name)
            raw_dir = Path(sequence["raw_dir"])
            raw_images = load_frames(raw_dir, frame_count)
            raw_pairs, runtime = _raw_segment_measurements(
                sequence_name,
                sequence,
                sessions,
                raw_images,
            )
            sequence_tables = [raw_long_table(sequence_name, raw_pairs)]
            for method in method_order:
                if method == "Raw":
                    continue
                directory = method_sequence_dir(
                    manifest,
                    method,
                    sequence_name,
                    raw_dir,
                )
                try:
                    images = load_frames(directory, frame_count)
                except FileNotFoundError as error:
                    if allow_missing:
                        print(f"Skipping {method} {sequence_name}: {error}", flush=True)
                        continue
                    raise
                joined = _join_v42(raw_pairs, sequence, images, runtime, sessions)
                sequence_tables.append(
                    learned_long_table(sequence_name, method, joined)
                )
            combined = pd.concat(sequence_tables, ignore_index=True)
            selection = top30.loc[
                top30["sequence"].eq(sequence_name),
                ["sequence", "end_frame_index", "raw_motion_quality_rank"],
            ]
            combined = combined.merge(
                selection,
                on=["sequence", "end_frame_index"],
                how="inner",
                validate="many_to_one",
            )
            combined["morphology"] = morphology
            morphology_long.append(combined)
            print(
                f"{morphology} {sequence_name}: "
                f"{combined['method'].nunique()} method(s), {len(selection)} locked steps",
                flush=True,
            )

        long_table = pd.concat(morphology_long, ignore_index=True)
        available_methods = [
            method for method in method_order if method in set(long_table["method"])
        ]
        availability, summaries, pooled = build_summaries(
            morphology,
            long_table,
            available_methods,
        )
        all_long.append(long_table)
        all_availability.append(availability)
        all_summaries.append(summaries)
        all_pooled.append(pooled)

    output_root.mkdir(parents=True, exist_ok=True)
    long_output = pd.concat(all_long, ignore_index=True)
    availability_output = pd.concat(all_availability, ignore_index=True)
    summary_output = pd.concat(all_summaries, ignore_index=True)
    pooled_output = pd.concat(all_pooled, ignore_index=True)
    long_output.to_csv(output_root / "displacement_step_measurements.csv", index=False)
    availability_output.to_csv(output_root / "displacement_availability.csv", index=False)
    summary_output.to_csv(output_root / "displacement_summary.csv", index=False)
    pooled_output.to_csv(output_root / "displacement_pooled_common_valid.csv", index=False)
    metadata = {
        "purpose": "Fair multimethod displacement comparison across pillar and via",
        "manifest": str(manifest_path),
        "methods": sorted(long_output["method"].unique().tolist()),
        "morphologies": sorted(long_output["morphology"].unique().tolist()),
        "selection": "Exactly 30 Raw-motion-ranked adjacent pairs per sequence",
        "primary_population": "Common-valid intersection across all available methods",
        "stage_reference": "PI commanded displacement is treated as the experimental position reference",
        "files": {
            "long": "displacement_step_measurements.csv",
            "availability": "displacement_availability.csv",
            "summary": "displacement_summary.csv",
            "pooled": "displacement_pooled_common_valid.csv",
        },
    }
    (output_root / "metadata.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(pooled_output.to_string(index=False), flush=True)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output-root",
        type=Path,
        default=EXPERIMENT / "evaluation" / "displacement",
    )
    parser.add_argument("--allow-missing", action="store_true")
    parser.add_argument(
        "--manifest",
        type=Path,
        default=MANIFEST_PATH,
        help="Evaluation manifest; defaults to the formal benchmark manifest.",
    )
    return parser.parse_args()


if __name__ == "__main__":
    arguments = parse_args()
    main(
        arguments.output_root.resolve(),
        arguments.allow_missing,
        arguments.manifest.resolve(),
    )

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

import analyze_multimethod_displacement as displacement
PROJECT_ROOT = Path(__file__).resolve().parents[4]


EXPERIMENT = Path(__file__).resolve().parent
MANIFEST_PATH = EXPERIMENT / "evaluation_manifest.json"
RULES_30 = ("formal_raw_ranked30", "time_regular30", "central_acquisition30")


def selection_keys(
    raw_pairs: pd.DataFrame,
    formal: pd.DataFrame,
    sequence: str,
) -> dict[str, set[int]]:
    formal_indices = set(
        formal.loc[formal["sequence"].eq(sequence), "end_frame_index"].astype(int)
    )
    within = raw_pairs.loc[~raw_pairs["cross_session"].astype(bool)].copy()
    if len(within) < 30:
        raise RuntimeError(f"{sequence} has fewer than 30 within-session pairs")
    median_gap = float(within["gap_seconds"].median())
    time_regular = within.assign(
        gap_deviation=(within["gap_seconds"] - median_gap).abs()
    ).sort_values(["gap_deviation", "end_frame_index"]).head(30)
    ordered = within.sort_values("end_frame_index")
    start = max(0, (len(ordered) - 30) // 2)
    central = ordered.iloc[start : start + 30]
    return {
        "formal_raw_ranked30": formal_indices,
        "time_regular30": set(time_regular["end_frame_index"].astype(int)),
        "central_acquisition30": set(central["end_frame_index"].astype(int)),
        "all_within_session": set(within["end_frame_index"].astype(int)),
    }


def metric_rows(
    morphology: str,
    rule: str,
    table: pd.DataFrame,
    method_order: list[str],
) -> list[dict[str, object]]:
    pieces: dict[str, pd.DataFrame] = {}
    for sequence in displacement.APPROVED_SEQUENCES:
        selected = table.loc[
            table["sequence"].eq(sequence) & table[f"selected__{rule}"].astype(bool)
        ].copy()
        validity = selected.pivot(
            index="end_frame_index", columns="method", values="evaluable"
        ).reindex(columns=method_order)
        common = validity.index[validity.fillna(False).all(axis=1)]
        pieces[sequence] = selected.loc[selected["end_frame_index"].isin(common)]
    rows: list[dict[str, object]] = []
    for method in method_order:
        pooled = pd.concat(
            [piece.loc[piece["method"].eq(method)] for piece in pieces.values()],
            ignore_index=True,
        )
        row = displacement.metric_record(
            morphology,
            "all_four_sequences",
            method,
            f"selection sensitivity: {rule}",
            pooled,
        )
        row["selection_rule"] = rule
        rows.append(row)
    return rows


def main(output_root: Path) -> None:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    method_order = list(manifest["methods"])
    formal = pd.read_csv(str(PROJECT_ROOT / manifest["top30_selection"]))
    formal = formal.loc[formal["top30_raw_motion_selected"].astype(bool)].copy()
    long_outputs: list[pd.DataFrame] = []
    selection_records: list[dict[str, object]] = []
    summary_records: list[dict[str, object]] = []

    for morphology, config_key in (("pillar", "pillar_config"), ("via", "via_config")):
        configs = displacement.load_config(Path(PROJECT_ROOT / manifest[config_key]), morphology)
        morphology_tables: list[pd.DataFrame] = []
        for sequence_name in displacement.APPROVED_SEQUENCES:
            sequence = configs[sequence_name]
            frame_count = int(sequence["frame_count"])
            sessions = displacement._load_mapping(sequence_name)
            raw_dir = Path(sequence["raw_dir"])
            raw_images = displacement.load_frames(raw_dir, frame_count)
            raw_pairs, runtime = displacement._raw_segment_measurements(
                sequence_name, sequence, sessions, raw_images
            )
            tables = [displacement.raw_long_table(sequence_name, raw_pairs)]
            for method in method_order:
                if method == "Raw":
                    continue
                directory = displacement.method_sequence_dir(
                    manifest, method, sequence_name, raw_dir
                )
                images = displacement.load_frames(directory, frame_count)
                joined = displacement._join_v42(
                    raw_pairs, sequence, images, runtime, sessions
                )
                tables.append(
                    displacement.learned_long_table(sequence_name, method, joined)
                )
            combined = pd.concat(tables, ignore_index=True)
            raw_meta = raw_pairs[
                [
                    "end_frame_index",
                    "gap_seconds",
                    "end_session_id",
                    "cross_session",
                    "raw_local_dx_um",
                    "raw_local_dy_um",
                    "expected_signed_step_um",
                ]
            ].copy()
            combined = combined.merge(
                raw_meta, on=["end_frame_index", "expected_signed_step_um"], how="left"
            )
            keys = selection_keys(raw_pairs, formal, sequence_name)
            for rule, indices in keys.items():
                combined[f"selected__{rule}"] = combined["end_frame_index"].isin(indices)
                selection_records.append(
                    {
                        "morphology": morphology,
                        "sequence": sequence_name,
                        "selection_rule": rule,
                        "selected_pair_count": len(indices),
                    }
                )
            combined["morphology"] = morphology
            morphology_tables.append(combined)
            print(f"{morphology} {sequence_name}: all pairs measured", flush=True)
        morphology_table = pd.concat(morphology_tables, ignore_index=True)
        long_outputs.append(morphology_table)
        for rule in (*RULES_30, "all_within_session"):
            summary_records.extend(
                metric_rows(morphology, rule, morphology_table, method_order)
            )

    long_table = pd.concat(long_outputs, ignore_index=True)
    summary = pd.DataFrame(summary_records)
    selection_table = pd.DataFrame(selection_records)
    output_root.mkdir(parents=True, exist_ok=True)
    long_table.to_csv(output_root / "all_pair_measurements.csv", index=False)
    summary.to_csv(output_root / "selection_sensitivity_summary.csv", index=False)
    selection_table.to_csv(output_root / "selection_rule_counts.csv", index=False)
    metadata: dict[str, Any] = {
        "purpose": "Diagnose displacement sensitivity to the preselected 30-step rule",
        "formal_raw_ranked30": "Existing Raw local-motion error ranking; favors Raw by construction",
        "time_regular30": "Thirty non-cross-session pairs with timestamp gaps closest to the sequence median",
        "central_acquisition30": "Central thirty non-cross-session pairs in acquisition order; session-boundary pairs remain excluded",
        "all_within_session": "All adjacent pairs that do not cross an acquisition-session boundary",
        "important_limit": "All absolute errors still use the nominal commanded step because no per-frame numeric position-feedback column is present in the supplied mappings.",
    }
    (output_root / "metadata.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(summary.to_string(index=False), flush=True)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output-root",
        type=Path,
        default=EXPERIMENT / "evaluation" / "selection_sensitivity",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    main(args.output_root.resolve())

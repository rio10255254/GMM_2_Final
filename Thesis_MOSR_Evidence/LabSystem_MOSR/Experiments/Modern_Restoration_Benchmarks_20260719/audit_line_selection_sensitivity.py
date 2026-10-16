from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

import analyze_line_multimethod as line_analysis


EXPERIMENT = Path(__file__).resolve().parent
MANIFEST_PATH = EXPERIMENT / "evaluation_manifest.json"
SELECTION_AUDIT = EXPERIMENT / "evaluation" / "selection_sensitivity"
RULES = (
    "formal_raw_ranked30",
    "time_regular30",
    "central_acquisition30",
    "all_within_session",
)


def main(output_root: Path) -> None:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    methods = line_analysis.available_methods(manifest, allow_missing=False)
    sequences = line_analysis.build_sequences(manifest, methods)
    module = line_analysis.load_source_module()
    module.METHODS = tuple(methods)
    module.SEQUENCES = sequences

    def method_directory(sequence: dict, method: str) -> Path:
        return sequence["directories"][method]

    module.method_directory = method_directory
    all_pairs = pd.read_csv(SELECTION_AUDIT / "all_pair_measurements.csv")
    base = all_pairs.loc[
        all_pairs["morphology"].eq("pillar")
        & all_pairs["method"].eq("Raw")
        & all_pairs["sequence"].isin(("50x_x_0p5um", "50x_x_1um"))
    ].copy()
    summaries: list[pd.DataFrame] = []
    steps: list[pd.DataFrame] = []
    for rule in RULES:
        selected = base.loc[base[f"selected__{rule}"].astype(bool)].copy()
        selected = selected[["sequence", "end_frame_index"]].drop_duplicates()
        selected["raw_motion_quality_rank"] = selected.groupby("sequence").cumcount() + 1
        _, step_table = module.analyze_displacement(selected)
        _, pooled = line_analysis.displacement_summary(step_table)
        pooled.insert(0, "selection_rule", rule)
        step_table.insert(0, "selection_rule", rule)
        summaries.append(pooled)
        steps.append(step_table)
        print(f"{rule}: {len(step_table)} method-step rows", flush=True)
    output_root.mkdir(parents=True, exist_ok=True)
    pd.concat(summaries, ignore_index=True).to_csv(
        output_root / "line_selection_sensitivity_summary.csv", index=False
    )
    pd.concat(steps, ignore_index=True).to_csv(
        output_root / "line_selection_sensitivity_steps.csv", index=False
    )
    metadata = {
        "purpose": "Test whether the line-displacement ranking depends on Raw-ranked step selection",
        "selection_source": str(SELECTION_AUDIT / "all_pair_measurements.csv"),
        "metric": "Shared individual 50% line-edge crossing displacement",
        "limit": "Absolute error remains relative to nominal commanded motion, not a stored per-frame feedback value.",
    }
    (output_root / "metadata.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(pd.concat(summaries, ignore_index=True).to_string(index=False), flush=True)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output-root",
        type=Path,
        default=EXPERIMENT / "evaluation" / "line_selection_sensitivity",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    main(args.output_root.resolve())

"""Paired family-stratified uncertainty for R73/R74 intervention ACM."""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "results" / "physical_validation" / "synthetic_acm"
CANDIDATES = ("no_shift", "no_width", "learned_support_only", "smoothed_controls")
METRICS = {"mean_boundary_distance_px": "lower", "perimeter_error_pct": "lower", "area_error_pct": "lower", "iou": "higher"}


def analyze_suite(suite: str, repetitions: int = 20_000) -> dict[str, object]:
    path = BASE / f"{suite}_contract" / "results" / "tables" / "primary_contour_metrics.csv"
    table = pd.read_csv(path)
    table = table.loc[table.alignment.eq("translation_only")].copy()
    full = table.loc[table.method.eq("full")].set_index("image_id")
    rng = np.random.default_rng(113700 + sum(ord(value) for value in suite))
    comparisons = []
    for candidate in CANDIDATES:
        other = table.loc[table.method.eq(candidate)].set_index("image_id")
        if set(full.index) != set(other.index):
            raise RuntimeError(f"{suite}/{candidate}: image population mismatch")
        paired = full.reset_index().merge(other.reset_index(), on=["image_id", "family"], suffixes=("_full", "_candidate"), validate="one_to_one")
        group_indices = [group.index.to_numpy() for _, group in paired.groupby("family", sort=False)]
        metrics = {}
        for metric, direction in METRICS.items():
            difference = paired[f"{metric}_candidate"].to_numpy(float) - paired[f"{metric}_full"].to_numpy(float)
            sampled = np.empty(repetitions, float)
            for index in range(repetitions):
                draw = np.concatenate([indices[rng.integers(0, len(indices), len(indices))] for indices in group_indices])
                sampled[index] = np.median(difference[draw])
            low, high = np.percentile(sampled, [2.5, 97.5])
            improved = difference < 0 if direction == "lower" else difference > 0
            family_medians = paired.assign(_difference=difference).groupby("family")["_difference"].median()
            family_improved = family_medians < 0 if direction == "lower" else family_medians > 0
            metrics[metric] = {
                "direction": direction,
                "observed_median_candidate_minus_full": float(np.median(difference)),
                "ci95": [float(low), float(high)],
                "improved_images": int(improved.sum()),
                "images": len(difference),
                "improved_families": int(family_improved.sum()),
                "families": len(family_medians),
                "interval_excludes_zero": bool(high < 0 or low > 0),
            }
        comparisons.append({"candidate": candidate, "metrics": metrics})
    return {"suite": suite, "images": len(full), "families": int(table.family.nunique()), "comparisons": comparisons}


def main() -> int:
    payload = {
        "status": "complete",
        "generated_local": datetime.now().astimezone().isoformat(),
        "independent_unit": "synthetic image; bootstrap stratified by shape/degradation family",
        "repetitions": 20_000,
        "suites": [analyze_suite("R73"), analyze_suite("R74")],
    }
    (BASE / "uncertainty.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

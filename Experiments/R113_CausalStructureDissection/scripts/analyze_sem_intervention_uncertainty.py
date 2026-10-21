"""Paired physical-pillar uncertainty for SEM causal interventions."""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "results" / "physical_validation" / "sem_acm_contract"
TABLE = CONTRACT / "results" / "acm_sem" / "tables" / "primary_contour_metrics.csv"
OUTPUT = CONTRACT / "results" / "uncertainty.json"
CANDIDATES = ("no_shift", "no_width", "learned_support_only", "smoothed_controls")
METRICS = {
    "mean_boundary_distance_pitch_pct": "lower",
    "perimeter_error_pct": "lower",
    "area_error_pct": "lower",
    "iou": "higher",
}


def main() -> int:
    table = pd.read_csv(TABLE)
    per_pillar = table.groupby(["method", "pillar_id"], as_index=False)[list(METRICS)].median()
    rng = np.random.default_rng(113604)
    repetitions = 20_000
    comparisons = []
    full = per_pillar.loc[per_pillar.method.eq("full")].sort_values("pillar_id").reset_index(drop=True)
    for candidate in CANDIDATES:
        other = per_pillar.loc[per_pillar.method.eq(candidate)].sort_values("pillar_id").reset_index(drop=True)
        if not np.array_equal(full.pillar_id, other.pillar_id):
            raise RuntimeError(f"{candidate}: pillar population mismatch")
        indices = rng.integers(0, len(full), size=(repetitions, len(full)))
        metrics = {}
        for metric, direction in METRICS.items():
            difference = other[metric].to_numpy(float) - full[metric].to_numpy(float)
            sampled = np.median(difference[indices], axis=1)
            low, high = np.percentile(sampled, [2.5, 97.5])
            improved = difference < 0 if direction == "lower" else difference > 0
            metrics[metric] = {
                "direction": direction,
                "observed_median_candidate_minus_full": float(np.median(difference)),
                "ci95": [float(low), float(high)],
                "improved_pillars": int(improved.sum()),
                "pillars": len(difference),
                "interval_excludes_zero": bool(high < 0 or low > 0),
            }
        comparisons.append({"candidate": candidate, "metrics": metrics})
    exposure = table.groupby(["method", "exposure"], as_index=False)["mean_boundary_distance_pitch_pct"].median()
    pivot = exposure.pivot(index="exposure", columns="method", values="mean_boundary_distance_pitch_pct")
    exposure_counts = {candidate: int((pivot[candidate] < pivot["full"]).sum()) for candidate in CANDIDATES}
    payload = {
        "status": "complete",
        "generated_local": datetime.now().astimezone().isoformat(),
        "independent_unit": "physical pillar",
        "pillars": 36,
        "repeated_exposures": 12,
        "bootstrap_repetitions": repetitions,
        "comparisons": comparisons,
        "boundary_improved_exposure_counts_out_of_12": exposure_counts,
    }
    OUTPUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

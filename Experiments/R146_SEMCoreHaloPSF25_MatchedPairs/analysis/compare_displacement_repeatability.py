"""Resample complete real scans for adjacent and start-relative repeatability."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from utils import now, save, sha


def main() -> None:
    table = pd.read_csv(ROOT / "results/comparison/all_displacements.csv")
    new = "R146-SEMCoreHaloPSF25-MatchedPairs"
    references = ["R145-Center9PSF25-CorrectedPairs", "R140v2-StableUNet"]
    rng = np.random.default_rng(146136)
    draw = rng.integers(0, 30, size=(5000, 30))
    output = {}
    for kind in ("adjacent", "start"):
        sampled = {}
        observed = {}
        for model in [new, *references]:
            values = (table[(table.model == model) & (table.kind == kind)]
                      .pivot(index="run", columns="j", values="error_nm")
                      .sort_index().to_numpy())
            assert values.shape == (30, 30)
            observed[model] = float(values.std(axis=0, ddof=1).mean())
            sampled[model] = values[draw].std(axis=1, ddof=1).mean(axis=1)
        output[kind] = {}
        for reference in references:
            delta = sampled[new] - sampled[reference]
            output[kind][reference] = dict(
                R146_repeatability_nm=observed[new], reference_repeatability_nm=observed[reference],
                difference_nm=observed[new] - observed[reference],
                whole_scan_bootstrap_ci95_nm=np.quantile(delta, [.025, .975]).tolist())
    result = dict(scans=30, positions=30, resamples=5000, comparisons=output,
                  script_sha256=sha(Path(__file__)), completed_utc=now())
    save(ROOT / "results/displacement_repeatability_intervals.json", result)
    print(result, flush=True)


if __name__ == "__main__":
    main()

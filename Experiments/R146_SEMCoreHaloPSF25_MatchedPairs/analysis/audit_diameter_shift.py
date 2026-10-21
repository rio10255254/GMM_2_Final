"""Check R146 diameter changes at pillar and complete-scan levels."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from utils import now, save, sha


def main() -> None:
    circles = pd.read_csv(ROOT / "results/comparison/all_circles.csv",
                          usecols=["model", "run", "pillar_id", "diameter_nm"])
    new = "R146-SEMCoreHaloPSF25-MatchedPairs"
    rng = np.random.default_rng(14624)
    draw = rng.integers(0, 30, size=(10000, 30))
    by_scan = circles.groupby(["model", "run"]).diameter_nm.mean().unstack(0)
    by_pillar = circles.groupby(["model", "pillar_id"]).diameter_nm.mean().unstack(0)
    result = {}
    for reference in ("R145-Center9PSF25-CorrectedPairs", "Raw"):
        scan_delta = (by_scan[new] - by_scan[reference]).to_numpy()
        pillar_delta = (by_pillar[new] - by_pillar[reference]).to_numpy()
        assert len(scan_delta) == 30 and len(pillar_delta) == 9
        result[reference] = dict(mean_diameter_change_nm=float(scan_delta.mean()),
                                 positive_scans=int((scan_delta > 0).sum()),
                                 positive_pillars=int((pillar_delta > 0).sum()),
                                 pillar_change_range_nm=[float(pillar_delta.min()), float(pillar_delta.max())],
                                 whole_scan_bootstrap_ci95_nm=np.quantile(scan_delta[draw].mean(axis=1),
                                                                         [.025, .975]).tolist())
    output = dict(scans=30, pillars=9, comparisons=result,
                  script_sha256=sha(Path(__file__)), completed_utc=now())
    save(ROOT / "results/diameter_shift_intervals.json", output)
    print(output, flush=True)


if __name__ == "__main__":
    main()

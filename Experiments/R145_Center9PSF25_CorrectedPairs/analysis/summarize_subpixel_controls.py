"""Compare identical controlled-shift frames under three frozen models."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OLD = ROOT.parent / "R143_PSF25_MatchedPairs/results/stability_diagnosis"
sys.path.insert(0, str(ROOT))
from utils import load, now, save, sha


def read(name: str, kind: str) -> pd.DataFrame:
    directory = ROOT / "results/deep_diagnosis" if name == "r145" else OLD
    path = directory / f"subpixel_{kind}_{name}.json"
    return pd.DataFrame(load(path)["rows"])


def main() -> None:
    summary = {}
    for kind, shifts in (("fourier_broad", [.25, .5, .75]),
                         ("cubic", [.2, .4, .6, .8])):
        tables = {name: read(name, kind).query("shift_x_px in @shifts")
                  for name in ("r140", "r143", "r145")}
        for model, table in tables.items():
            if kind == "fourier_broad":
                assert len(table) == 36 and table.frame_no.nunique() == 12
            else:
                assert len(table) == 12 and table.frame_no.nunique() == 3
        scores = {name: float(np.sqrt(np.mean(table.model_shift_error_nm.to_numpy()**2)))
                  for name, table in tables.items()}
        summary[kind] = dict(RMS_nm=scores, frames=int(tables["r145"].frame_no.nunique()),
                             shifts_per_frame=len(shifts))
        if kind == "fourier_broad":
            per_frame = {}
            for name, table in tables.items():
                per_frame[name] = table.groupby(["frame_no", "run"]).model_shift_error_nm.apply(
                    lambda x: float(np.sqrt(np.mean(x.to_numpy()**2)))).rename(name)
            merged = pd.concat(per_frame.values(), axis=1).reset_index()
            rng = np.random.default_rng(145998)
            paired = {}
            for reference in ("r140", "r143"):
                delta = merged["r145"] - merged[reference]
                by_run = merged.assign(delta=delta).groupby("run").delta.mean().to_numpy()
                draw = rng.integers(0, len(by_run), size=(5000, len(by_run)))
                paired[reference] = dict(mean_frame_RMS_difference_nm=float(delta.mean()),
                                         worse_frames=int((delta > 0).sum()),
                                         whole_run_bootstrap_ci95_nm=np.quantile(by_run[draw].mean(axis=1),
                                                                              [.025, .975]).tolist())
            summary[kind]["paired_R145_minus_reference"] = paired
    out = ROOT / "results/deep_diagnosis/subpixel_comparison.json"
    save(out, dict(summary=summary, script_sha256=sha(Path(__file__)), completed_utc=now()))
    print(summary, flush=True)


if __name__ == "__main__":
    main()

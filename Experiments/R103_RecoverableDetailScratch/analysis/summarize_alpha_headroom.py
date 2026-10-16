"""Summarize the already-computed residual-strength counterfactuals."""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
PROBE = ROOT / "results" / "causal_diagnostics" / "alpha_probe"


def summarize_wide(wide: pd.DataFrame) -> dict[str, object]:
    oracle = wide.max(axis=1)
    best = wide.idxmax(axis=1)
    improvement = oracle - wide["Raw"]
    return {
        "samples": int(len(wide)),
        "raw_median_iou": float(wide["Raw"].median()),
        "oracle_median_iou": float(oracle.median()),
        "oracle_mean_improvement": float(improvement.mean()),
        "oracle_median_improvement": float(improvement.median()),
        "oracle_p90_improvement": float(improvement.quantile(0.90)),
        "fraction_oracle_improves_over_raw": float((improvement > 1e-12).mean()),
        "best_method_fraction": {str(key): float(value) for key, value in best.value_counts(normalize=True).items()},
    }


def main() -> None:
    result: dict[str, object] = {"status": "complete", "meaning": "diagnostic oracle only; not a deployable selector"}
    for suite in ("R73_novel_shapes", "R74_hard_microscopy"):
        table = pd.read_csv(
            PROBE / "external_alpha" / suite / "results" / "tables" / "primary_contour_metrics.csv"
        )
        fixed = table.loc[table["alignment"] == "fixed_pixel_coordinates"]
        wide = fixed.pivot(index="image_id", columns="method", values="iou")
        result[suite] = summarize_wide(wide)
        families = {}
        for family, group in fixed.groupby("family"):
            families[str(family)] = summarize_wide(group.pivot(index="image_id", columns="method", values="iou"))
        result[suite]["families"] = families

    sem = pd.read_csv(
        PROBE / "sem_alpha" / "results" / "acm_sem" / "tables" / "primary_contour_metrics.csv"
    )
    sem_wide = sem.pivot(index=["exposure", "pillar_id"], columns="method", values="iou")
    result["SEM"] = summarize_wide(sem_wide)
    exposures = {}
    for exposure, group in sem.groupby("exposure"):
        exposures[str(int(exposure))] = summarize_wide(group.pivot(index="pillar_id", columns="method", values="iou"))
    result["SEM"]["exposures"] = exposures
    destination = PROBE / "oracle_alpha_headroom.json"
    destination.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()

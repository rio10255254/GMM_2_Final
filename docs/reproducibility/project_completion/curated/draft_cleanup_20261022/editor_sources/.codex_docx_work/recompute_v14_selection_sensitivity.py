from __future__ import annotations

import json
import math
from pathlib import Path
from statistics import NormalDist

import numpy as np
import pandas as pd
PROJECT_ROOT = Path(__file__).resolve().parents[7]


SOURCE = Path(
    str(PROJECT_ROOT / 'LabSystem_MOSR/Experiments/Modern_Restoration_Benchmarks_20260719/evaluation/selection_sensitivity/all_pair_measurements.csv')
)
OUTPUT = Path(
    str(PROJECT_ROOT / 'PSF_Fitting/.codex_docx_work/v14_selection_sensitivity_raw_mosr')
)

METHODS = ("Raw", "MOSR")
RULES = (
    "formal_raw_ranked30",
    "time_regular30",
    "central_acquisition30",
    "all_within_session",
)


def paired_population(table: pd.DataFrame, morphology: str, rule: str) -> pd.DataFrame:
    selected = table.loc[
        table["morphology"].eq(morphology)
        & table[f"selected__{rule}"].astype(bool)
        & table["method"].isin(METHODS)
    ].copy()
    validity = selected.pivot_table(
        index=["sequence", "end_frame_index"],
        columns="method",
        values="evaluable",
        aggfunc="first",
    ).reindex(columns=METHODS)
    common = validity.index[validity.fillna(False).all(axis=1)]
    common_keys = pd.DataFrame(common.tolist(), columns=["sequence", "end_frame_index"])
    paired = selected.merge(common_keys, on=["sequence", "end_frame_index"], how="inner")
    paired["absolute_deviation_nm"] = (
        (paired["signed_step_um"] - paired["expected_signed_step_um"]).abs() * 1000.0
    )
    return paired


def summarize(table: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for morphology in ("pillar", "via"):
        for rule in RULES:
            paired = paired_population(table, morphology, rule)
            counts = paired.groupby("method").size()
            if counts.nunique() != 1:
                raise RuntimeError(f"Unpaired population for {morphology}/{rule}: {counts.to_dict()}")
            for method in METHODS:
                part = paired.loc[paired["method"].eq(method)]
                rows.append(
                    {
                        "morphology": morphology,
                        "selection_rule": rule,
                        "method": method,
                        "n": int(len(part)),
                        "mae_nm": float(part["absolute_deviation_nm"].mean()),
                        "median_absolute_deviation_nm": float(
                            part["absolute_deviation_nm"].median()
                        ),
                        "p90_absolute_deviation_nm": float(
                            part["absolute_deviation_nm"].quantile(0.90)
                        ),
                        "mean_within_grid_nm": float(part["within_grid_nm"].mean()),
                    }
                )
    return pd.DataFrame(rows)


def paired_inference(table: pd.DataFrame) -> dict[str, object]:
    paired = paired_population(table, "pillar", "formal_raw_ranked30")
    wide = paired.pivot(
        index=["sequence", "end_frame_index"],
        columns="method",
        values="absolute_deviation_nm",
    ).dropna(subset=list(METHODS))
    improvement = wide["Raw"] - wide["MOSR"]
    rng = np.random.default_rng(20260720)
    values = improvement.to_numpy(dtype=float)
    bootstrap = np.empty(20000, dtype=float)
    for index in range(len(bootstrap)):
        sample = rng.choice(values, size=len(values), replace=True)
        bootstrap[index] = sample.mean()
    nonzero = values[values != 0]
    ranks = pd.Series(np.abs(nonzero)).rank(method="average").to_numpy(dtype=float)
    w_plus = float(ranks[nonzero > 0].sum())
    expected = float(ranks.sum() / 2.0)
    variance = float(np.square(ranks).sum() / 4.0)
    z_score = (w_plus - expected - 0.5) / math.sqrt(variance)
    one_sided_p = 1.0 - NormalDist().cdf(z_score)
    return {
        "population": "pillar formal Raw-ranked 30; Raw/MOSR common-valid pairs only",
        "n": int(len(values)),
        "mean_raw_minus_mosr_nm": float(values.mean()),
        "bootstrap_95_ci_nm": [
            float(np.quantile(bootstrap, 0.025)),
            float(np.quantile(bootstrap, 0.975)),
        ],
        "wilcoxon_normal_approx_z": z_score,
        "wilcoxon_one_sided_p": one_sided_p,
    }


def main() -> None:
    table = pd.read_csv(SOURCE)
    OUTPUT.mkdir(parents=True, exist_ok=True)
    summary = summarize(table)
    summary.to_csv(OUTPUT / "selection_sensitivity_raw_mosr_summary.csv", index=False)
    inference = paired_inference(table)
    (OUTPUT / "paired_inference.json").write_text(
        json.dumps(inference, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(summary.to_string(index=False))
    print(json.dumps(inference, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

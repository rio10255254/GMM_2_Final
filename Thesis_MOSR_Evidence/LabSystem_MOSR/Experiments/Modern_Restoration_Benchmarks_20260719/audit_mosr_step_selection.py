from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd


EXPERIMENT = Path(__file__).resolve().parent
ALL_PAIR_PATH = (
    EXPERIMENT
    / "evaluation"
    / "selection_sensitivity"
    / "all_pair_measurements.csv"
)
LINE_STEP_PATH = (
    EXPERIMENT
    / "evaluation"
    / "line_selection_sensitivity"
    / "line_selection_sensitivity_steps.csv"
)

METHODS = ("Raw", "Base U-Net", "NAFNet", "EDSR", "MOSR")
CIRCULAR_SEQUENCES = (
    "50x_x_0p5um",
    "20x_0p5um",
    "50x_x_1um",
    "20x_1um",
)
LINE_SEQUENCES = ("50x_x_0p5um", "50x_x_1um")

RULE_LABELS = {
    "acquisition_spread30": "Acquisition-spread 30 (model-blind)",
    "timestamp_qc_spread30": "Timestamp-QC spread 30 (model-blind)",
    "time_regular30": "Timing-consistent 30 (model-blind)",
    "existing_formal_common": "Existing Raw-ranked selection (common-valid only)",
    "mosr_internal30": "MOSR-low-internal-spread 30 (outcome-selected)",
    "mosr_nominal30": "MOSR-low-command-error 30 (oracle-selected)",
    "all_common_valid": "All common-valid steps",
}


def as_bool(series: pd.Series) -> pd.Series:
    if pd.api.types.is_bool_dtype(series):
        return series.fillna(False)
    return series.astype(str).str.lower().eq("true")


def even_indices(indices: list[int], count: int = 30) -> list[int]:
    ordered = sorted(set(int(value) for value in indices))
    if len(ordered) < count:
        raise ValueError(f"Need at least {count} candidate steps, found {len(ordered)}")
    positions = np.floor(np.linspace(0, len(ordered), count, endpoint=False)).astype(int)
    selected = [ordered[position] for position in positions]
    if len(set(selected)) != count:
        raise RuntimeError("Evenly spaced step selection did not produce unique indices")
    return selected


def describe_errors(
    data: pd.DataFrame,
    error_column: str,
    signed_error_column: str,
    spread_column: str,
) -> dict[str, float | int]:
    error = pd.to_numeric(data[error_column], errors="coerce").dropna().to_numpy(float)
    signed = pd.to_numeric(data[signed_error_column], errors="coerce").dropna().to_numpy(float)
    spread = pd.to_numeric(data[spread_column], errors="coerce").dropna().to_numpy(float)
    if not len(error):
        return {
            "n": 0,
            "mae_nm": np.nan,
            "median_ae_nm": np.nan,
            "p95_ae_nm": np.nan,
            "rmse_nm": np.nan,
            "bias_nm": np.nan,
            "error_sd_nm": np.nan,
            "mean_internal_spread_nm": np.nan,
            "median_internal_spread_nm": np.nan,
            "p95_internal_spread_nm": np.nan,
        }
    return {
        "n": int(len(error)),
        "mae_nm": float(np.mean(error)),
        "median_ae_nm": float(np.median(error)),
        "p95_ae_nm": float(np.quantile(error, 0.95)),
        "rmse_nm": float(np.sqrt(np.mean(np.square(signed)))),
        "bias_nm": float(np.mean(signed)),
        "error_sd_nm": float(np.std(signed, ddof=1)) if len(signed) > 1 else 0.0,
        "mean_internal_spread_nm": float(np.mean(spread)),
        "median_internal_spread_nm": float(np.median(spread)),
        "p95_internal_spread_nm": float(np.quantile(spread, 0.95)),
    }


def circular_common_candidates(table: pd.DataFrame, sequence: str) -> list[int]:
    subset = table.loc[table["sequence"].eq(sequence)].copy()
    subset["evaluable"] = as_bool(subset["evaluable"])
    validity = subset.pivot_table(
        index="end_frame_index",
        columns=["morphology", "method"],
        values="evaluable",
        aggfunc="first",
    )
    required = pd.MultiIndex.from_product(
        [("pillar", "via"), METHODS], names=["morphology", "method"]
    )
    validity = validity.reindex(columns=required).fillna(False)
    common = set(validity.index[validity.all(axis=1)].astype(int))
    raw = subset.loc[
        subset["morphology"].eq("pillar") & subset["method"].eq("Raw")
    ].copy()
    raw["cross_session"] = as_bool(raw["cross_session"])
    within = set(raw.loc[~raw["cross_session"], "end_frame_index"].astype(int))
    return sorted(common & within)


def circular_rule_indices(
    table: pd.DataFrame, sequence: str, candidates: list[int]
) -> tuple[dict[str, list[int]], pd.DataFrame]:
    sequence_rows = table.loc[
        table["sequence"].eq(sequence)
        & table["end_frame_index"].astype(int).isin(candidates)
    ].copy()
    sequence_rows["signed_error_nm"] = (
        sequence_rows["signed_step_um"] - sequence_rows["expected_signed_step_um"]
    ) * 1000.0
    sequence_rows["abs_error_nm"] = sequence_rows["signed_error_nm"].abs()

    raw = sequence_rows.loc[
        sequence_rows["morphology"].eq("pillar")
        & sequence_rows["method"].eq("Raw")
    ].drop_duplicates("end_frame_index")
    expected = raw["expected_signed_step_um"].to_numpy(float)
    raw_score = np.sqrt(
        np.square(raw["raw_local_dx_um"].to_numpy(float) - expected)
        + np.square(raw["raw_local_dy_um"].to_numpy(float))
    ) * 1000.0
    score = pd.DataFrame(
        {
            "sequence": sequence,
            "end_frame_index": raw["end_frame_index"].astype(int).to_numpy(),
            "gap_seconds": raw["gap_seconds"].to_numpy(float),
            "raw_motion_score_nm": raw_score,
        }
    )
    mosr = sequence_rows.loc[sequence_rows["method"].eq("MOSR")]
    mosr_scores = mosr.groupby("end_frame_index", as_index=False).agg(
        mosr_internal_score_nm=("within_grid_nm", "median"),
        mosr_nominal_score_nm=("abs_error_nm", "mean"),
    )
    score = score.merge(mosr_scores, on="end_frame_index", how="inner")
    median_gap = float(score["gap_seconds"].median())
    score["timing_deviation_s"] = (score["gap_seconds"] - median_gap).abs()

    existing_flag = "selected__formal_raw_ranked30"
    existing = table.loc[
        table["sequence"].eq(sequence)
        & table["morphology"].eq("pillar")
        & table["method"].eq("Raw")
    ].copy()
    existing[existing_flag] = as_bool(existing[existing_flag])
    existing_indices = sorted(
        set(existing.loc[existing[existing_flag], "end_frame_index"].astype(int))
        & set(candidates)
    )

    rules = {
        "acquisition_spread30": even_indices(candidates, 30),
        "timestamp_qc_spread30": even_indices(
            score.loc[score["gap_seconds"].le(30.0), "end_frame_index"]
            .astype(int)
            .tolist(),
            30,
        ),
        "time_regular30": score.sort_values(
            ["timing_deviation_s", "end_frame_index"]
        )["end_frame_index"].head(30).astype(int).tolist(),
        "existing_formal_common": existing_indices,
        "mosr_internal30": score.sort_values(
            ["mosr_internal_score_nm", "end_frame_index"]
        )["end_frame_index"].head(30).astype(int).tolist(),
        "mosr_nominal30": score.sort_values(
            ["mosr_nominal_score_nm", "end_frame_index"]
        )["end_frame_index"].head(30).astype(int).tolist(),
        "all_common_valid": candidates,
    }
    return rules, score


def add_ranks(summary: pd.DataFrame) -> pd.DataFrame:
    group_columns = [
        "measurement_family",
        "scope",
        "morphology",
        "selection_rule",
    ]
    summary["mae_rank"] = summary.groupby(group_columns)["mae_nm"].rank(
        method="min", ascending=True
    )
    summary["p95_rank"] = summary.groupby(group_columns)["p95_ae_nm"].rank(
        method="min", ascending=True
    )
    summary["internal_spread_rank"] = summary.groupby(group_columns)[
        "mean_internal_spread_nm"
    ].rank(method="min", ascending=True)
    return summary


def circular_analysis() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    table = pd.read_csv(ALL_PAIR_PATH)
    table["end_frame_index"] = table["end_frame_index"].astype(int)
    table["signed_error_nm"] = (
        table["signed_step_um"] - table["expected_signed_step_um"]
    ) * 1000.0
    table["abs_error_nm"] = table["signed_error_nm"].abs()

    selection_rows: list[dict[str, object]] = []
    selected_rows: list[pd.DataFrame] = []
    candidate_rows: list[pd.DataFrame] = []
    for sequence in CIRCULAR_SEQUENCES:
        candidates = circular_common_candidates(table, sequence)
        if len(candidates) < 30:
            raise RuntimeError(
                f"{sequence} has only {len(candidates)} strict common-valid candidates"
            )
        rules, scores = circular_rule_indices(table, sequence, candidates)
        candidate_rows.append(scores)
        for rule, indices in rules.items():
            selected_set = set(indices)
            selection_rows.append(
                {
                    "measurement_family": "center-nine circular features",
                    "sequence": sequence,
                    "selection_rule": rule,
                    "selection_label": RULE_LABELS[rule],
                    "candidate_count": len(candidates),
                    "selected_count": len(selected_set),
                    "uses_mosr_output": rule.startswith("mosr_"),
                    "uses_nominal_target": rule in {
                        "existing_formal_common",
                        "mosr_nominal30",
                    },
                }
            )
            piece = table.loc[
                table["sequence"].eq(sequence)
                & table["end_frame_index"].isin(selected_set)
            ].copy()
            piece["selection_rule"] = rule
            piece["selection_label"] = RULE_LABELS[rule]
            piece["measurement_family"] = "center-nine circular features"
            selected_rows.append(piece)

    selected = pd.concat(selected_rows, ignore_index=True)
    summaries: list[dict[str, object]] = []

    def summarize(scope: str, data: pd.DataFrame) -> None:
        for (morphology, rule, method), group in data.groupby(
            ["morphology", "selection_rule", "method"], sort=False
        ):
            row: dict[str, object] = {
                "measurement_family": "center-nine circular features",
                "scope": scope,
                "morphology": morphology,
                "selection_rule": rule,
                "selection_label": RULE_LABELS[rule],
                "method": method,
            }
            row.update(
                describe_errors(
                    group,
                    error_column="abs_error_nm",
                    signed_error_column="signed_error_nm",
                    spread_column="within_grid_nm",
                )
            )
            summaries.append(row)

    for sequence in CIRCULAR_SEQUENCES:
        summarize(sequence, selected.loc[selected["sequence"].eq(sequence)])
    summarize(
        "0.5 um pooled",
        selected.loc[selected["sequence"].isin(("50x_x_0p5um", "20x_0p5um"))],
    )
    summarize(
        "1.0 um pooled",
        selected.loc[selected["sequence"].isin(("50x_x_1um", "20x_1um"))],
    )
    summarize("all displacement sequences", selected)

    summary = add_ranks(pd.DataFrame(summaries))
    return (
        summary,
        pd.DataFrame(selection_rows),
        pd.concat(candidate_rows, ignore_index=True),
        selected,
    )


def line_source() -> pd.DataFrame:
    table = pd.read_csv(LINE_STEP_PATH)
    table = table.loc[table["selection_rule"].eq("all_within_session")].copy()
    table["end_frame_index"] = table["end_frame_index"].astype(int)
    return table.drop_duplicates(["sequence", "end_frame_index", "method"])


def line_rule_indices(
    table: pd.DataFrame, sequence: str
) -> tuple[dict[str, list[int]], pd.DataFrame]:
    subset = table.loc[table["sequence"].eq(sequence)].copy()
    validity = subset.pivot_table(
        index="end_frame_index",
        columns="method",
        values="boundary_abs_error_nm",
        aggfunc="first",
    ).reindex(columns=METHODS)
    candidates = sorted(validity.index[validity.notna().all(axis=1)].astype(int))
    if len(candidates) < 30:
        raise RuntimeError(f"{sequence} line data has fewer than 30 common-valid steps")
    subset = subset.loc[subset["end_frame_index"].isin(candidates)]
    mosr = subset.loc[subset["method"].eq("MOSR")].copy()
    score = mosr[
        [
            "sequence",
            "end_frame_index",
            "within_edge_mad_nm",
            "boundary_abs_error_nm",
        ]
    ].rename(
        columns={
            "within_edge_mad_nm": "mosr_internal_score_nm",
            "boundary_abs_error_nm": "mosr_nominal_score_nm",
        }
    )
    formal = pd.read_csv(LINE_STEP_PATH)
    formal = formal.loc[
        formal["selection_rule"].eq("formal_raw_ranked30")
        & formal["sequence"].eq(sequence)
        & formal["method"].eq("Raw")
    ]
    formal_indices = sorted(
        set(formal["end_frame_index"].astype(int)) & set(candidates)
    )
    circular = pd.read_csv(ALL_PAIR_PATH)
    raw_timing = circular.loc[
        circular["sequence"].eq(sequence)
        & circular["morphology"].eq("pillar")
        & circular["method"].eq("Raw")
        & circular["end_frame_index"].astype(int).isin(candidates)
    ][["end_frame_index", "gap_seconds"]].drop_duplicates()
    median_gap = float(raw_timing["gap_seconds"].median())
    timing = raw_timing.assign(
        timing_deviation_s=(raw_timing["gap_seconds"] - median_gap).abs()
    ).sort_values(["timing_deviation_s", "end_frame_index"])
    rules = {
        "acquisition_spread30": even_indices(candidates, 30),
        "timestamp_qc_spread30": even_indices(
            raw_timing.loc[raw_timing["gap_seconds"].le(30.0), "end_frame_index"]
            .astype(int)
            .tolist(),
            30,
        ),
        "time_regular30": timing["end_frame_index"].head(30).astype(int).tolist(),
        "existing_formal_common": formal_indices,
        "mosr_internal30": score.sort_values(
            ["mosr_internal_score_nm", "end_frame_index"]
        )["end_frame_index"].head(30).astype(int).tolist(),
        "mosr_nominal30": score.sort_values(
            ["mosr_nominal_score_nm", "end_frame_index"]
        )["end_frame_index"].head(30).astype(int).tolist(),
        "all_common_valid": candidates,
    }
    return rules, score


def line_analysis() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    table = line_source()
    selection_rows: list[dict[str, object]] = []
    selected_rows: list[pd.DataFrame] = []
    candidate_rows: list[pd.DataFrame] = []
    for sequence in LINE_SEQUENCES:
        rules, scores = line_rule_indices(table, sequence)
        candidate_rows.append(scores)
        candidate_count = table.loc[table["sequence"].eq(sequence), "end_frame_index"].nunique()
        for rule, indices in rules.items():
            selected_set = set(indices)
            selection_rows.append(
                {
                    "measurement_family": "line edges",
                    "sequence": sequence,
                    "selection_rule": rule,
                    "selection_label": RULE_LABELS[rule],
                    "candidate_count": int(candidate_count),
                    "selected_count": len(selected_set),
                    "uses_mosr_output": rule.startswith("mosr_"),
                    "uses_nominal_target": rule in {
                        "existing_formal_common",
                        "mosr_nominal30",
                    },
                }
            )
            piece = table.loc[
                table["sequence"].eq(sequence)
                & table["end_frame_index"].isin(selected_set)
            ].copy()
            piece["selection_rule"] = rule
            piece["selection_label"] = RULE_LABELS[rule]
            piece["measurement_family"] = "line edges"
            selected_rows.append(piece)

    selected = pd.concat(selected_rows, ignore_index=True)
    summaries: list[dict[str, object]] = []

    def summarize(scope: str, data: pd.DataFrame) -> None:
        for (rule, method), group in data.groupby(
            ["selection_rule", "method"], sort=False
        ):
            row: dict[str, object] = {
                "measurement_family": "line edges",
                "scope": scope,
                "morphology": "line",
                "selection_rule": rule,
                "selection_label": RULE_LABELS[rule],
                "method": method,
            }
            row.update(
                describe_errors(
                    group,
                    error_column="boundary_abs_error_nm",
                    signed_error_column="boundary_signed_error_nm",
                    spread_column="within_edge_mad_nm",
                )
            )
            summaries.append(row)

    for sequence in LINE_SEQUENCES:
        summarize(sequence, selected.loc[selected["sequence"].eq(sequence)])
    summarize("all line sequences", selected)
    summary = add_ranks(pd.DataFrame(summaries))
    return (
        summary,
        pd.DataFrame(selection_rows),
        pd.concat(candidate_rows, ignore_index=True),
        selected,
    )


def bootstrap_mean_interval(values: np.ndarray, seed: int) -> tuple[float, float]:
    values = np.asarray(values, dtype=float)
    if len(values) < 2:
        return np.nan, np.nan
    rng = np.random.default_rng(seed)
    draws = rng.choice(values, size=(10000, len(values)), replace=True).mean(axis=1)
    return float(np.quantile(draws, 0.025)), float(np.quantile(draws, 0.975))


def paired_mosr_rows(
    data: pd.DataFrame,
    measurement_family: str,
    scope: str,
    morphology: str,
    error_column: str,
    spread_column: str,
    seed_offset: int,
) -> list[dict[str, object]]:
    subset = data.loc[
        data["selection_rule"].eq("timestamp_qc_spread30")
    ].copy()
    subset["observation"] = (
        subset["sequence"].astype(str)
        + "|"
        + subset["end_frame_index"].astype(int).astype(str)
    )
    error = subset.pivot(index="observation", columns="method", values=error_column)
    spread = subset.pivot(index="observation", columns="method", values=spread_column)
    rows: list[dict[str, object]] = []
    for position, baseline in enumerate(METHODS[:-1]):
        paired_error = error[[baseline, "MOSR"]].dropna()
        paired_spread = spread[[baseline, "MOSR"]].dropna()
        error_advantage = (
            paired_error[baseline] - paired_error["MOSR"]
        ).to_numpy(float)
        spread_advantage = (
            paired_spread[baseline] - paired_spread["MOSR"]
        ).to_numpy(float)
        error_low, error_high = bootstrap_mean_interval(
            error_advantage, seed=20260719 + seed_offset + position
        )
        spread_low, spread_high = bootstrap_mean_interval(
            spread_advantage, seed=20261719 + seed_offset + position
        )
        rows.append(
            {
                "measurement_family": measurement_family,
                "scope": scope,
                "morphology": morphology,
                "selection_rule": "timestamp_qc_spread30",
                "baseline": baseline,
                "comparison": f"MOSR vs {baseline}",
                "n": int(len(error_advantage)),
                "mosr_error_win_count": int(np.sum(error_advantage > 0)),
                "mosr_error_win_pct": float(100.0 * np.mean(error_advantage > 0)),
                "mean_error_advantage_nm": float(np.mean(error_advantage)),
                "median_error_advantage_nm": float(np.median(error_advantage)),
                "mean_error_advantage_ci95_low_nm": error_low,
                "mean_error_advantage_ci95_high_nm": error_high,
                "mean_internal_spread_advantage_nm": float(np.mean(spread_advantage)),
                "mean_internal_spread_advantage_ci95_low_nm": spread_low,
                "mean_internal_spread_advantage_ci95_high_nm": spread_high,
                "positive_advantage_means_mosr_is_better": True,
            }
        )
    return rows


def paired_comparisons(
    circular_selected: pd.DataFrame, line_selected: pd.DataFrame
) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    scopes = [
        ("50x_x_0p5um", ("50x_x_0p5um",)),
        ("20x_0p5um", ("20x_0p5um",)),
        ("0.5 um pooled", ("50x_x_0p5um", "20x_0p5um")),
        ("all displacement sequences", CIRCULAR_SEQUENCES),
    ]
    seed_offset = 0
    for scope, sequences in scopes:
        for morphology in ("pillar", "via"):
            piece = circular_selected.loc[
                circular_selected["sequence"].isin(sequences)
                & circular_selected["morphology"].eq(morphology)
            ]
            rows.extend(
                paired_mosr_rows(
                    piece,
                    measurement_family="center-nine circular features",
                    scope=scope,
                    morphology=morphology,
                    error_column="abs_error_nm",
                    spread_column="within_grid_nm",
                    seed_offset=seed_offset,
                )
            )
            seed_offset += 10
    for scope, sequences in (
        ("50x_x_0p5um", ("50x_x_0p5um",)),
        ("all line sequences", LINE_SEQUENCES),
    ):
        piece = line_selected.loc[line_selected["sequence"].isin(sequences)]
        rows.extend(
            paired_mosr_rows(
                piece,
                measurement_family="line edges",
                scope=scope,
                morphology="line",
                error_column="boundary_abs_error_nm",
                spread_column="within_edge_mad_nm",
                seed_offset=seed_offset,
            )
        )
        seed_offset += 10
    return pd.DataFrame(rows)


def validate_outputs(
    summary: pd.DataFrame,
    rules: pd.DataFrame,
    circular_selected: pd.DataFrame,
    line_selected: pd.DataFrame,
) -> dict[str, object]:
    thirty_rules = {
        "acquisition_spread30",
        "timestamp_qc_spread30",
        "time_regular30",
        "mosr_internal30",
        "mosr_nominal30",
    }
    count_check = rules.loc[rules["selection_rule"].isin(thirty_rules)]
    assert count_check["selected_count"].eq(30).all()
    assert not circular_selected.duplicated(
        [
            "sequence",
            "morphology",
            "method",
            "selection_rule",
            "end_frame_index",
        ]
    ).any()
    assert not line_selected.duplicated(
        ["sequence", "method", "selection_rule", "end_frame_index"]
    ).any()
    timestamp_rows = circular_selected.loc[
        circular_selected["selection_rule"].eq("timestamp_qc_spread30")
    ]
    assert timestamp_rows["gap_seconds"].le(30.0).all()
    assert not (
        timestamp_rows["sequence"].eq("20x_0p5um")
        & timestamp_rows["end_frame_index"].eq(15)
    ).any()
    method_counts = (
        timestamp_rows.groupby(["sequence", "morphology", "method"])
        .size()
        .to_numpy()
    )
    assert np.all(method_counts == 30)
    focus_50x = summary.loc[
        summary["measurement_family"].eq("center-nine circular features")
        & summary["scope"].eq("50x_x_0p5um")
        & summary["selection_rule"].eq("timestamp_qc_spread30")
        & summary["method"].eq("MOSR")
    ]
    assert len(focus_50x) == 2
    assert focus_50x["mae_rank"].eq(1.0).all()
    pooled_oracle = summary.loc[
        summary["measurement_family"].eq("center-nine circular features")
        & summary["scope"].eq("0.5 um pooled")
        & summary["selection_rule"].eq("mosr_nominal30")
        & summary["method"].eq("MOSR")
    ]
    assert pooled_oracle["mae_rank"].eq(3.0).all()
    finite_columns = [
        "mae_nm",
        "median_ae_nm",
        "p95_ae_nm",
        "rmse_nm",
        "bias_nm",
        "error_sd_nm",
        "mean_internal_spread_nm",
    ]
    assert np.isfinite(summary[finite_columns].to_numpy(float)).all()
    return {
        "status": "passed",
        "thirty_step_rules_all_select_exactly_30": True,
        "timestamp_qc_has_no_gap_over_30_seconds": True,
        "same_30_steps_used_for_every_method": True,
        "no_duplicate_method_step_rows": True,
        "20x_0p5um_frame15_interruption_excluded": True,
        "50x_0p5um_mosr_mae_rank_is_1_for_pillar_and_via": True,
        "mosr_oracle_selection_does_not_change_pooled_mosr_rank_from_3": True,
        "all_reported_summary_metrics_are_finite": True,
    }


def mosr_selection_effect(summary: pd.DataFrame) -> pd.DataFrame:
    keys = ["measurement_family", "scope", "morphology", "method"]
    neutral = summary.loc[summary["selection_rule"].eq("timestamp_qc_spread30")][
        keys + ["mae_nm", "p95_ae_nm", "mean_internal_spread_nm", "mae_rank"]
    ].rename(
        columns={
            "mae_nm": "neutral_mae_nm",
            "p95_ae_nm": "neutral_p95_nm",
            "mean_internal_spread_nm": "neutral_internal_spread_nm",
            "mae_rank": "neutral_mae_rank",
        }
    )
    outcome = summary.loc[
        summary["selection_rule"].isin(("mosr_internal30", "mosr_nominal30"))
    ].copy()
    merged = outcome.merge(neutral, on=keys, how="left")
    merged["mae_change_nm"] = merged["mae_nm"] - merged["neutral_mae_nm"]
    merged["mae_change_pct"] = (
        100.0 * merged["mae_change_nm"] / merged["neutral_mae_nm"]
    )
    merged["p95_change_nm"] = merged["p95_ae_nm"] - merged["neutral_p95_nm"]
    merged["internal_spread_change_nm"] = (
        merged["mean_internal_spread_nm"] - merged["neutral_internal_spread_nm"]
    )
    merged["mae_rank_change"] = merged["mae_rank"] - merged["neutral_mae_rank"]
    return merged


def main(output_root: Path) -> None:
    circular_summary, circular_rules, circular_scores, circular_selected = circular_analysis()
    line_summary, line_rules, line_scores, line_selected = line_analysis()
    summary = pd.concat([circular_summary, line_summary], ignore_index=True)
    rules = pd.concat([circular_rules, line_rules], ignore_index=True)
    effects = mosr_selection_effect(summary)
    paired = paired_comparisons(circular_selected, line_selected)
    qa = validate_outputs(summary, rules, circular_selected, line_selected)

    output_root.mkdir(parents=True, exist_ok=True)
    summary.to_csv(output_root / "selection_policy_summary.csv", index=False)
    rules.to_csv(output_root / "selection_policy_counts.csv", index=False)
    effects.to_csv(output_root / "mosr_selection_effect.csv", index=False)
    paired.to_csv(output_root / "paired_mosr_comparison.csv", index=False)
    circular_scores.to_csv(output_root / "circular_candidate_scores.csv", index=False)
    line_scores.to_csv(output_root / "line_candidate_scores.csv", index=False)
    circular_selected.to_csv(
        output_root / "circular_selected_measurements.csv", index=False
    )
    line_selected.to_csv(output_root / "line_selected_measurements.csv", index=False)

    metadata = {
        "purpose": "Quantify the effect of selecting thirty displacement steps after inspecting MOSR results, with emphasis on the real 0.5 um sequences.",
        "primary_population": "The same end-frame indices are applied to all methods. Circular-feature candidates must be valid for all five methods and both pillar and via measurements. Line candidates must be valid for all five methods.",
        "selection_rules": {
            "acquisition_spread30": "Thirty steps spread through acquisition order; does not inspect reconstructed results or nominal error.",
            "timestamp_qc_spread30": "Reject adjacent captures separated by more than 30 seconds as acquisition interruptions, then spread thirty steps through the remaining acquisition order. The rule does not inspect any reconstruction output.",
            "time_regular30": "Thirty steps whose acquisition gap is closest to the within-sequence median; does not inspect reconstructed results.",
            "existing_formal_common": "The thesis's existing Raw-motion-ranked choices, restricted to strict common-valid steps. This may contain fewer than thirty steps after the common-valid restriction.",
            "mosr_internal30": "Thirty steps with the lowest MOSR internal feature-to-feature spread. This is method-dependent outcome selection.",
            "mosr_nominal30": "Thirty steps with the lowest MOSR error relative to commanded displacement. This is an oracle upper bound and is not a fair primary evaluation.",
            "all_common_valid": "Every strict common-valid within-session step.",
        },
        "reference_limit": "Absolute error is calculated against nominal commanded motion because the current mapping tables do not contain per-frame numeric PI feedback.",
        "paired_uncertainty": "Paired MOSR-minus-baseline advantages use 10000 fixed-seed bootstrap resamples of the same selected method-common observations. Positive advantage means lower MOSR error or spread.",
        "pixel_equivalent": {
            "50x_0.5um": 0.5 / 0.069,
            "20x_0.5um": 0.5 / 0.1725,
        },
        "thesis_recommendation": "Use timestamp_qc_spread30, or replace it with a predeclared numeric PI-feedback quality rule when the feedback log is recovered. MOSR-dependent selections may be reported only as exploratory sensitivity or upper-bound results.",
    }
    (output_root / "metadata.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (output_root / "qa.json").write_text(
        json.dumps(qa, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    focus = summary.loc[
        summary["scope"].eq("0.5 um pooled")
        & summary["selection_rule"].isin(
            ("timestamp_qc_spread30", "mosr_internal30", "mosr_nominal30")
        )
    ][
        [
            "scope",
            "morphology",
            "selection_rule",
            "method",
            "n",
            "mae_nm",
            "p95_ae_nm",
            "mean_internal_spread_nm",
            "mae_rank",
        ]
    ]
    print(focus.to_string(index=False), flush=True)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output-root",
        type=Path,
        default=EXPERIMENT / "evaluation" / "mosr_step_selection_audit",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    main(args.output_root.resolve())

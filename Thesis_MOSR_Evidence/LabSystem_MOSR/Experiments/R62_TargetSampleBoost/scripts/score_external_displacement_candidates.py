from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path
from statistics import mean
from typing import Iterable


DEFAULT_PRIMARY_GROUPS = {
    ("20260702_100MG", "x_1um"),
    ("20260702_100MG", "x_0p5um"),
}
DEFAULT_BASELINE_CASE = "raw"
DEFAULT_PRIMARY_WORSE_COUNT_PENALTY_PCT = 100.0
DEFAULT_PRIMARY_REGRESSION_TOLERANCE_PCT = 0.02
DEFAULT_GUARDRAIL_WORSE_COUNT_PENALTY_PCT = 30.0
DEFAULT_STEP_ERROR_PENALTY_PCT_PER_UM = 100.0
DEFAULT_GUARDRAIL_STEP_ERROR_WEIGHT = 0.5


def _round6(value: float) -> float:
    return round(float(value), 6)


def _group_key(row: dict[str, object]) -> tuple[str, str]:
    return str(row["dataset"]), str(row["group"])


def _case_key(row: dict[str, object]) -> tuple[str, str, str]:
    dataset, group = _group_key(row)
    return dataset, group, str(row["case"])


def _is_ok(row: dict[str, object]) -> bool:
    return str(row.get("status", "ok")).lower() == "ok"


def _as_float(row: dict[str, object], key: str) -> float:
    value = row.get(key, "")
    if value is None or value == "":
        return 0.0
    return float(value)


def read_results_csv(path: Path) -> list[dict[str, object]]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        return [dict(row) for row in reader]


def load_result_rows(paths: Iterable[Path]) -> list[dict[str, object]]:
    merged: dict[tuple[str, str, str], dict[str, object]] = {}
    for path in paths:
        for row in read_results_csv(path):
            if not _is_ok(row):
                continue
            key = _case_key(row)
            merged[key] = row
    return list(merged.values())


def discover_results_csvs(report_dirs: Iterable[Path]) -> list[Path]:
    csvs: list[Path] = []
    for report_dir in report_dirs:
        path = report_dir / "gmf_like_thesis_gate_results.csv"
        if not path.exists():
            raise FileNotFoundError(f"missing GMF-like result CSV: {path}")
        csvs.append(path)
    return csvs


def improvement_pct(baseline_std: float, candidate_std: float) -> float:
    if baseline_std <= 0:
        return 0.0
    return _round6((baseline_std - candidate_std) / baseline_std * 100.0)


def build_group_rows(
    rows: Iterable[dict[str, object]],
    *,
    baseline_case: str = DEFAULT_BASELINE_CASE,
    primary_groups: set[tuple[str, str]] | None = None,
) -> list[dict[str, object]]:
    primary_groups = primary_groups or DEFAULT_PRIMARY_GROUPS
    by_group: dict[tuple[str, str], list[dict[str, object]]] = defaultdict(list)
    for row in rows:
        if _is_ok(row):
            by_group[_group_key(row)].append(row)

    output: list[dict[str, object]] = []
    for group_key in sorted(by_group):
        group_rows = by_group[group_key]
        baseline = next((row for row in group_rows if str(row["case"]) == baseline_case), None)
        if baseline is None:
            continue
        baseline_std = _as_float(baseline, "std_um")
        best = min(group_rows, key=lambda row: _as_float(row, "std_um"))
        tier = "primary" if group_key in primary_groups else "guardrail"
        for row in sorted(group_rows, key=lambda item: str(item["case"])):
            std_um = _as_float(row, "std_um")
            output.append(
                {
                    "dataset": group_key[0],
                    "group": group_key[1],
                    "tier": tier,
                    "case": str(row["case"]),
                    "std_um": _round6(std_um),
                    "step_um": _round6(_as_float(row, "step_um")),
                    "step_error_um": _round6(_as_float(row, "step_error_um")),
                    "best_case": str(best["case"]),
                    "improvement_vs_raw_pct": improvement_pct(baseline_std, std_um),
                }
            )
    return output


def _candidate_cases(rows: Iterable[dict[str, object]], baseline_case: str) -> list[str]:
    cases = {str(row["case"]) for row in rows if _is_ok(row)}
    cases.discard(baseline_case)
    return sorted(cases)


def score_cases(
    rows: Iterable[dict[str, object]],
    *,
    candidate_cases: Iterable[str] | None = None,
    baseline_case: str = DEFAULT_BASELINE_CASE,
    primary_groups: set[tuple[str, str]] | None = None,
    primary_worse_count_penalty_pct: float = DEFAULT_PRIMARY_WORSE_COUNT_PENALTY_PCT,
    primary_regression_tolerance_pct: float = DEFAULT_PRIMARY_REGRESSION_TOLERANCE_PCT,
    guardrail_worse_count_penalty_pct: float = DEFAULT_GUARDRAIL_WORSE_COUNT_PENALTY_PCT,
    step_error_penalty_pct_per_um: float = DEFAULT_STEP_ERROR_PENALTY_PCT_PER_UM,
    guardrail_step_error_weight: float = DEFAULT_GUARDRAIL_STEP_ERROR_WEIGHT,
) -> list[dict[str, object]]:
    primary_groups = primary_groups or DEFAULT_PRIMARY_GROUPS
    rows = [row for row in rows if _is_ok(row)]
    by_key = {_case_key(row): row for row in rows}
    cases = list(candidate_cases) if candidate_cases is not None else _candidate_cases(rows, baseline_case)

    all_groups = sorted({_group_key(row) for row in rows})
    scored: list[dict[str, object]] = []
    for case in cases:
        primary_improvements: list[float] = []
        guardrail_improvements: list[float] = []
        primary_step_errors: list[float] = []
        guardrail_step_errors: list[float] = []
        missing_groups: list[str] = []
        for dataset, group in all_groups:
            baseline = by_key.get((dataset, group, baseline_case))
            candidate = by_key.get((dataset, group, str(case)))
            if baseline is None or candidate is None:
                missing_groups.append(f"{dataset}/{group}")
                continue
            change = improvement_pct(_as_float(baseline, "std_um"), _as_float(candidate, "std_um"))
            if (dataset, group) in primary_groups:
                primary_improvements.append(change)
                primary_step_errors.append(_as_float(candidate, "step_error_um"))
            else:
                guardrail_improvements.append(change)
                guardrail_step_errors.append(_as_float(candidate, "step_error_um"))

        primary_regressions = [
            value for value in primary_improvements if value < -float(primary_regression_tolerance_pct)
        ]
        guardrail_regressions = [value for value in guardrail_improvements if value < 0]
        worst_primary_regression = min(primary_regressions) if primary_regressions else 0.0
        worst_regression = min(guardrail_regressions) if guardrail_regressions else 0.0
        primary_mean = mean(primary_improvements) if primary_improvements else 0.0
        guardrail_mean = mean(guardrail_improvements) if guardrail_improvements else 0.0
        primary_step_error_mean = mean(primary_step_errors) if primary_step_errors else 0.0
        guardrail_step_error_mean = mean(guardrail_step_errors) if guardrail_step_errors else 0.0
        step_error_penalty = (
            primary_step_error_mean
            + float(guardrail_step_error_weight) * guardrail_step_error_mean
        ) * float(step_error_penalty_pct_per_um)
        selection = (
            primary_mean
            + min(0.0, worst_primary_regression)
            - len(primary_regressions) * float(primary_worse_count_penalty_pct)
            + min(0.0, worst_regression)
            - len(guardrail_regressions) * guardrail_worse_count_penalty_pct
            - step_error_penalty
        )
        scored.append(
            {
                "case": str(case),
                "primary_case_count": len(primary_improvements),
                "guardrail_case_count": len(guardrail_improvements),
                "missing_group_count": len(missing_groups),
                "missing_groups": ";".join(missing_groups),
                "primary_mean_improvement_pct": _round6(primary_mean),
                "guardrail_mean_improvement_pct": _round6(guardrail_mean),
                "primary_worse_count": len(primary_regressions),
                "primary_worst_regression_pct": _round6(worst_primary_regression),
                "guardrail_worse_count": len(guardrail_regressions),
                "guardrail_worst_regression_pct": _round6(worst_regression),
                "primary_mean_step_error_um": _round6(primary_step_error_mean),
                "guardrail_mean_step_error_um": _round6(guardrail_step_error_mean),
                "step_error_penalty_pct": _round6(step_error_penalty),
                "selection_score_pct": _round6(selection),
            }
        )
    return sorted(scored, key=lambda row: float(row["selection_score_pct"]), reverse=True)


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def write_report(path: Path, candidate_scores: list[dict[str, object]], group_rows: list[dict[str, object]]) -> None:
    lines = [
        "# GMF-like candidate score report",
        "",
        "This report merges GMF-like displacement readouts and ranks candidate reconstructions against Raw.",
        "",
        "## Candidate Ranking",
        "",
        "| rank | case | primary mean % | primary worse | guardrail mean % | guardrail worse | worst guardrail % | step err penalty | score |",
        "|---:|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for idx, row in enumerate(candidate_scores, start=1):
        lines.append(
            "| {rank} | {case} | {primary:.3f} | {primary_worse} | {guard:.3f} | {worse} | {worst:.3f} | {step_penalty:.3f} | {score:.3f} |".format(
                rank=idx,
                case=row["case"],
                primary=float(row["primary_mean_improvement_pct"]),
                primary_worse=row["primary_worse_count"],
                guard=float(row["guardrail_mean_improvement_pct"]),
                worse=row["guardrail_worse_count"],
                worst=float(row["guardrail_worst_regression_pct"]),
                step_penalty=float(row["step_error_penalty_pct"]),
                score=float(row["selection_score_pct"]),
            )
        )

    lines.extend(
        [
            "",
            "## Group Winners",
            "",
            "| dataset | group | tier | best case |",
            "|---|---|---|---|",
        ]
    )
    seen: set[tuple[str, str]] = set()
    for row in group_rows:
        key = (str(row["dataset"]), str(row["group"]))
        if key in seen:
            continue
        seen.add(key)
        lines.append(f"| {row['dataset']} | {row['group']} | {row['tier']} | {row['best_case']} |")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Score GMF-like displacement candidate reports.")
    parser.add_argument(
        "--report-dir",
        action="append",
        type=Path,
        default=[],
        help="Report folder containing gmf_like_thesis_gate_results.csv. Can be passed multiple times.",
    )
    parser.add_argument(
        "--results-csv",
        action="append",
        type=Path,
        default=[],
        help="Direct GMF-like results CSV. Can be passed multiple times.",
    )
    parser.add_argument(
        "--candidate-case",
        action="append",
        default=None,
        help="Candidate case to score. Defaults to every non-raw case found.",
    )
    parser.add_argument("--baseline-case", default=DEFAULT_BASELINE_CASE)
    parser.add_argument(
        "--output-dir",
        type=Path,
        required=True,
        help="Output folder for merged group rows, candidate scores, and markdown report.",
    )
    parser.add_argument(
        "--primary-worse-count-penalty-pct",
        type=float,
        default=DEFAULT_PRIMARY_WORSE_COUNT_PENALTY_PCT,
    )
    parser.add_argument(
        "--primary-regression-tolerance-pct",
        type=float,
        default=DEFAULT_PRIMARY_REGRESSION_TOLERANCE_PCT,
    )
    parser.add_argument(
        "--guardrail-worse-count-penalty-pct",
        type=float,
        default=DEFAULT_GUARDRAIL_WORSE_COUNT_PENALTY_PCT,
    )
    parser.add_argument(
        "--step-error-penalty-pct-per-um",
        type=float,
        default=DEFAULT_STEP_ERROR_PENALTY_PCT_PER_UM,
    )
    parser.add_argument(
        "--guardrail-step-error-weight",
        type=float,
        default=DEFAULT_GUARDRAIL_STEP_ERROR_WEIGHT,
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    result_csvs = list(args.results_csv) + discover_results_csvs(args.report_dir)
    if not result_csvs:
        raise SystemExit("pass at least one --report-dir or --results-csv")

    rows = load_result_rows(result_csvs)
    group_rows = build_group_rows(rows, baseline_case=args.baseline_case)
    candidate_scores = score_cases(
        rows,
        candidate_cases=args.candidate_case,
        baseline_case=args.baseline_case,
        primary_worse_count_penalty_pct=args.primary_worse_count_penalty_pct,
        primary_regression_tolerance_pct=args.primary_regression_tolerance_pct,
        guardrail_worse_count_penalty_pct=args.guardrail_worse_count_penalty_pct,
        step_error_penalty_pct_per_um=args.step_error_penalty_pct_per_um,
        guardrail_step_error_weight=args.guardrail_step_error_weight,
    )

    args.output_dir.mkdir(parents=True, exist_ok=True)
    write_csv(args.output_dir / "gmf_like_candidate_group_rows.csv", group_rows)
    write_csv(args.output_dir / "gmf_like_candidate_scores.csv", candidate_scores)
    write_report(args.output_dir / "GMF_LIKE_CANDIDATE_SCORE_REPORT.md", candidate_scores, group_rows)
    manifest = {
        "algorithm": "gmf_like_candidate_score_merger",
        "baseline_case": args.baseline_case,
        "primary_worse_count_penalty_pct": args.primary_worse_count_penalty_pct,
        "primary_regression_tolerance_pct": args.primary_regression_tolerance_pct,
        "guardrail_worse_count_penalty_pct": args.guardrail_worse_count_penalty_pct,
        "step_error_penalty_pct_per_um": args.step_error_penalty_pct_per_um,
        "guardrail_step_error_weight": args.guardrail_step_error_weight,
        "input_csvs": [str(path) for path in result_csvs],
        "candidate_count": len(candidate_scores),
        "group_row_count": len(group_rows),
        "outputs": {
            "group_rows": str(args.output_dir / "gmf_like_candidate_group_rows.csv"),
            "candidate_scores": str(args.output_dir / "gmf_like_candidate_scores.csv"),
            "report": str(args.output_dir / "GMF_LIKE_CANDIDATE_SCORE_REPORT.md"),
        },
    }
    (args.output_dir / "gmf_like_candidate_score_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

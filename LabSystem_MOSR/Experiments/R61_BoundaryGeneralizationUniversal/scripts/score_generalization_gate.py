"""Conservative gate for diverse phantom boundary generalization results."""
from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path
from statistics import mean


DEFAULT_GROUP_SCOPES = ("polarity", "bias_px", "shape")
OVERALL_METRICS = ("mean_chamfer_px", "p95_chamfer_px", "max_chamfer_px")
GROUP_METRICS = ("mean_chamfer_px",)


def _as_float(value: object) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return float("nan")


def _canonical_value(value: object) -> str:
    numeric = _as_float(value)
    if math.isfinite(numeric):
        return f"{numeric:g}"
    return str(value)


def _percentile(values: list[float], percentile: float) -> float:
    if not values:
        return float("nan")
    sorted_values = sorted(values)
    if len(sorted_values) == 1:
        return float(sorted_values[0])
    rank = (len(sorted_values) - 1) * float(percentile) / 100.0
    low = int(math.floor(rank))
    high = int(math.ceil(rank))
    if low == high:
        return float(sorted_values[low])
    fraction = rank - low
    return float(sorted_values[low] * (1.0 - fraction) + sorted_values[high] * fraction)


def load_metric_rows(path: Path, *, image: str = "model_recon") -> list[dict]:
    rows: list[dict] = []
    with Path(path).open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for raw in reader:
            if raw.get("image") != image:
                continue
            chamfer_px = _as_float(raw.get("chamfer_px"))
            if not math.isfinite(chamfer_px):
                continue
            row = dict(raw)
            row["chamfer_px"] = chamfer_px
            rows.append(row)
    if not rows:
        raise ValueError(f"no metric rows for image={image!r}: {path}")
    return rows


def _group_values(rows: list[dict], scope: str) -> dict[str, list[float]]:
    groups: dict[str, list[float]] = {}
    for row in rows:
        group = "all" if scope == "overall" else _canonical_value(row.get(scope, ""))
        groups.setdefault(group, []).append(float(row["chamfer_px"]))
    return groups


def _stats(values: list[float]) -> dict:
    finite = [float(v) for v in values if math.isfinite(float(v))]
    if not finite:
        return {
            "count": 0,
            "mean_chamfer_px": None,
            "p95_chamfer_px": None,
            "max_chamfer_px": None,
        }
    return {
        "count": len(finite),
        "mean_chamfer_px": float(mean(finite)),
        "p95_chamfer_px": _percentile(finite, 95.0),
        "max_chamfer_px": float(max(finite)),
    }


def summarize_rows(rows: list[dict], *, group_scopes: tuple[str, ...] = DEFAULT_GROUP_SCOPES) -> dict:
    summary: dict[str, dict[str, dict]] = {}
    for scope in ("overall", *group_scopes):
        summary[scope] = {}
        for group, values in sorted(_group_values(rows, scope).items(), key=lambda item: item[0]):
            summary[scope][group] = _stats(values)
    return summary


def _check_metric(
    *,
    scope: str,
    group: str,
    metric: str,
    baseline_stats: dict | None,
    candidate_stats: dict | None,
    tolerance_px: float,
) -> dict:
    baseline = None if baseline_stats is None else baseline_stats.get(metric)
    candidate = None if candidate_stats is None else candidate_stats.get(metric)
    passed = (
        baseline is not None
        and candidate is not None
        and float(candidate) <= float(baseline) + float(tolerance_px)
    )
    return {
        "scope": scope,
        "group": group,
        "metric": metric,
        "baseline": baseline,
        "candidate": candidate,
        "delta": None if baseline is None or candidate is None else float(candidate) - float(baseline),
        "passed": bool(passed),
    }


def evaluate_gate(
    baseline_rows: list[dict],
    candidate_rows: list[dict],
    *,
    tolerance_px: float = 0.0,
    group_scopes: tuple[str, ...] = DEFAULT_GROUP_SCOPES,
    baseline_name: str = "baseline",
    candidate_name: str = "candidate",
) -> dict:
    baseline_summary = summarize_rows(baseline_rows, group_scopes=group_scopes)
    candidate_summary = summarize_rows(candidate_rows, group_scopes=group_scopes)

    checks: list[dict] = []
    for metric in OVERALL_METRICS:
        checks.append(
            _check_metric(
                scope="overall",
                group="all",
                metric=metric,
                baseline_stats=baseline_summary["overall"].get("all"),
                candidate_stats=candidate_summary["overall"].get("all"),
                tolerance_px=tolerance_px,
            )
        )

    for scope in group_scopes:
        for group in sorted(baseline_summary.get(scope, {})):
            for metric in GROUP_METRICS:
                checks.append(
                    _check_metric(
                        scope=scope,
                        group=group,
                        metric=metric,
                        baseline_stats=baseline_summary[scope].get(group),
                        candidate_stats=candidate_summary.get(scope, {}).get(group),
                        tolerance_px=tolerance_px,
                    )
                )

    failures = [check for check in checks if not check["passed"]]
    return {
        "pass": not failures,
        "baseline_name": baseline_name,
        "candidate_name": candidate_name,
        "tolerance_px": float(tolerance_px),
        "required_group_scopes": list(group_scopes),
        "checks": checks,
        "failures": failures,
        "summary": {
            "overall": {
                "baseline": baseline_summary["overall"]["all"],
                "candidate": candidate_summary["overall"]["all"],
            },
            "baseline": baseline_summary,
            "candidate": candidate_summary,
        },
    }


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Score a candidate against a conservative generalization gate")
    parser.add_argument("--baseline-csv", type=Path, required=True)
    parser.add_argument("--candidate-csv", type=Path, required=True)
    parser.add_argument("--baseline-name", default="baseline")
    parser.add_argument("--candidate-name", default="candidate")
    parser.add_argument("--output-json", type=Path, required=True)
    parser.add_argument("--image", default="model_recon")
    parser.add_argument("--tolerance-px", type=float, default=0.0)
    parser.add_argument("--group-scopes", default="polarity,bias_px,shape")
    parser.add_argument("--no-fail-exit", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    group_scopes = tuple(part.strip() for part in str(args.group_scopes).split(",") if part.strip())
    report = evaluate_gate(
        load_metric_rows(args.baseline_csv, image=args.image),
        load_metric_rows(args.candidate_csv, image=args.image),
        tolerance_px=float(args.tolerance_px),
        group_scopes=group_scopes,
        baseline_name=str(args.baseline_name),
        candidate_name=str(args.candidate_name),
    )
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({"pass": report["pass"], "failures": len(report["failures"])}, indent=2))
    if report["pass"] or bool(args.no_fail_exit):
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())

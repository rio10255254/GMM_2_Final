"""R53 real-checkboard corner stability gate."""
from __future__ import annotations

import argparse
import csv
import json
from dataclasses import dataclass
from pathlib import Path


DEFAULT_SUMMARY = (
    Path(__file__).resolve().parents[3]
    / "Reconstruct_Progress"
    / "20250605_checkboard_external_gmf_prepare"
    / "corner_geometry_validation_r53_20260616"
    / "corner_metrics_summary.csv"
)


@dataclass(frozen=True)
class CornerMetrics:
    case: str
    median_px: float
    p90_px: float
    over_5px_pct: float


def evaluate_candidate(
    candidate: CornerMetrics,
    control: CornerMetrics,
    *,
    median_margin_px: float = 0.0,
    tail_tolerance_px: float = 0.0,
    large_error_tolerance_pct: float = 0.0,
) -> dict[str, object]:
    passed: list[str] = []
    failed: list[str] = []
    if candidate.median_px < control.median_px - median_margin_px:
        passed.append("median_improved")
    else:
        failed.append("median_not_improved")

    if candidate.over_5px_pct <= control.over_5px_pct + large_error_tolerance_pct:
        passed.append("large_error_rate_not_worse")
    else:
        failed.append("large_error_rate_regressed")

    if candidate.p90_px <= control.p90_px + tail_tolerance_px:
        passed.append("tail_not_worse")
    else:
        failed.append("tail_regressed")

    return {
        "candidate": candidate.case,
        "control": control.case,
        "pass": not failed,
        "passed_rules": passed,
        "failed_rules": failed,
        "candidate_metrics": {
            "median_px": candidate.median_px,
            "p90_px": candidate.p90_px,
            "over_5px_pct": candidate.over_5px_pct,
        },
        "control_metrics": {
            "median_px": control.median_px,
            "p90_px": control.p90_px,
            "over_5px_pct": control.over_5px_pct,
        },
    }


def _row_to_metrics(row: dict[str, str]) -> CornerMetrics:
    return CornerMetrics(
        case=row["case"],
        median_px=float(row["median_corner_peak_shift_px"]),
        p90_px=float(row.get("p90_corner_peak_shift_px") or row.get("p75_corner_peak_shift_px")),
        over_5px_pct=float(row["pct_peak_shift_gt_5px"]),
    )


def load_summary(path: Path) -> dict[str, CornerMetrics]:
    with path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        return {row["case"]: _row_to_metrics(row) for row in reader}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Evaluate R53 candidate against the Lab R40 real-corner guard.")
    parser.add_argument("--summary", type=Path, default=DEFAULT_SUMMARY)
    parser.add_argument("--candidate", required=True)
    parser.add_argument("--control", default="lab_r40_best_tradeoff")
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args(argv)

    rows = load_summary(args.summary)
    if args.control not in rows:
        raise KeyError(f"control case not found: {args.control}")
    if args.candidate not in rows:
        raise KeyError(f"candidate case not found: {args.candidate}")
    result = evaluate_candidate(rows[args.candidate], rows[args.control])
    text = json.dumps(result, indent=2, ensure_ascii=False)
    print(text)
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text + "\n", encoding="utf-8")
    return 0 if result["pass"] else 2


if __name__ == "__main__":
    raise SystemExit(main())

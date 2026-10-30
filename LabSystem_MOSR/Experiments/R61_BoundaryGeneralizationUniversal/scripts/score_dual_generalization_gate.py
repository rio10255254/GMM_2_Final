"""Dual gate for boundary generalization and real-sequence motion stability."""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path


def _as_float(value: object) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return float("nan")


def _case_by_name(summary: dict, case_name: str) -> dict:
    for row in summary.get("cases", []):
        if row.get("case") == case_name:
            return row
    raise KeyError(f"case not found in motion summary: {case_name}")


def evaluate_motion_gate(
    motion_summary: dict,
    *,
    baseline_case: str,
    candidate_case: str,
    metric: str = "tail_std_dy_px",
    tolerance_px: float = 0.0,
) -> dict:
    baseline_row = _case_by_name(motion_summary, baseline_case)
    candidate_row = _case_by_name(motion_summary, candidate_case)
    baseline = _as_float(baseline_row.get(metric))
    candidate = _as_float(candidate_row.get(metric))
    passed = math.isfinite(baseline) and math.isfinite(candidate) and candidate <= baseline + float(tolerance_px)
    return {
        "pass": bool(passed),
        "metric": metric,
        "baseline_case": baseline_case,
        "candidate_case": candidate_case,
        "baseline": None if not math.isfinite(baseline) else baseline,
        "candidate": None if not math.isfinite(candidate) else candidate,
        "delta": None if not math.isfinite(baseline) or not math.isfinite(candidate) else candidate - baseline,
        "tolerance_px": float(tolerance_px),
    }


def evaluate_dual_gate(
    *,
    boundary_report: dict,
    motion_summary: dict,
    motion_baseline_case: str,
    motion_candidate_case: str,
    motion_metric: str = "tail_std_dy_px",
    motion_tolerance_px: float = 0.0,
) -> dict:
    boundary_pass = bool(boundary_report.get("pass"))
    motion_gate = evaluate_motion_gate(
        motion_summary,
        baseline_case=motion_baseline_case,
        candidate_case=motion_candidate_case,
        metric=motion_metric,
        tolerance_px=motion_tolerance_px,
    )
    boundary_failures = boundary_report.get("failures", [])
    return {
        "pass": bool(boundary_pass and motion_gate["pass"]),
        "boundary_gate": {
            "pass": boundary_pass,
            "candidate_name": boundary_report.get("candidate_name"),
            "failure_count": len(boundary_failures) if isinstance(boundary_failures, list) else None,
            "failures": boundary_failures,
        },
        "motion_gate": motion_gate,
    }


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Score a candidate with simulated-boundary and real-motion gates.")
    parser.add_argument("--boundary-gate-json", type=Path, required=True)
    parser.add_argument("--motion-summary-json", type=Path, required=True)
    parser.add_argument("--motion-baseline-case", required=True)
    parser.add_argument("--motion-candidate-case", required=True)
    parser.add_argument("--motion-metric", default="tail_std_dy_px")
    parser.add_argument("--motion-tolerance-px", type=float, default=0.0)
    parser.add_argument("--output-json", type=Path, required=True)
    parser.add_argument("--no-fail-exit", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    boundary_report = json.loads(Path(args.boundary_gate_json).read_text(encoding="utf-8"))
    motion_summary = json.loads(Path(args.motion_summary_json).read_text(encoding="utf-8"))
    report = evaluate_dual_gate(
        boundary_report=boundary_report,
        motion_summary=motion_summary,
        motion_baseline_case=str(args.motion_baseline_case),
        motion_candidate_case=str(args.motion_candidate_case),
        motion_metric=str(args.motion_metric),
        motion_tolerance_px=float(args.motion_tolerance_px),
    )
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({"pass": report["pass"], "motion_pass": report["motion_gate"]["pass"]}, indent=2))
    if report["pass"] or bool(args.no_fail_exit):
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())

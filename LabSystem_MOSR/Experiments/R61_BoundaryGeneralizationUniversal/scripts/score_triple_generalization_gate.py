"""Triple gate for boundary, 20260603 real motion, and Step small-displacement stability."""
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
    raise KeyError(f"case not found in summary: {case_name}")


def evaluate_case_metric_gate(
    summary: dict,
    *,
    baseline_case: str,
    candidate_case: str,
    metric: str,
    tolerance_px: float = 0.0,
) -> dict[str, object]:
    baseline_row = _case_by_name(summary, baseline_case)
    candidate_row = _case_by_name(summary, candidate_case)
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


def evaluate_triple_gate(
    *,
    boundary_report: dict,
    real_motion_summary: dict,
    real_motion_baseline_case: str,
    real_motion_candidate_case: str,
    step_summary: dict,
    step_baseline_case: str,
    step_candidate_case: str,
    real_motion_metric: str = "tail_std_dy_px",
    step_metric: str = "step_std_dx_px",
    real_motion_tolerance_px: float = 0.0,
    step_tolerance_px: float = 0.0,
) -> dict[str, object]:
    boundary_pass = bool(boundary_report.get("pass"))
    real_gate = evaluate_case_metric_gate(
        real_motion_summary,
        baseline_case=real_motion_baseline_case,
        candidate_case=real_motion_candidate_case,
        metric=real_motion_metric,
        tolerance_px=real_motion_tolerance_px,
    )
    step_gate = evaluate_case_metric_gate(
        step_summary,
        baseline_case=step_baseline_case,
        candidate_case=step_candidate_case,
        metric=step_metric,
        tolerance_px=step_tolerance_px,
    )
    boundary_failures = boundary_report.get("failures", [])
    return {
        "pass": bool(boundary_pass and real_gate["pass"] and step_gate["pass"]),
        "boundary_gate": {
            "pass": boundary_pass,
            "candidate_name": boundary_report.get("candidate_name"),
            "failure_count": len(boundary_failures) if isinstance(boundary_failures, list) else None,
            "failures": boundary_failures,
        },
        "real_motion_gate": real_gate,
        "step_gate": step_gate,
    }


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Score a candidate with boundary, real-motion, and Step gates.")
    parser.add_argument("--boundary-gate-json", type=Path, required=True)
    parser.add_argument("--real-motion-summary-json", type=Path, required=True)
    parser.add_argument("--real-motion-baseline-case", required=True)
    parser.add_argument("--real-motion-candidate-case", required=True)
    parser.add_argument("--real-motion-metric", default="tail_std_dy_px")
    parser.add_argument("--real-motion-tolerance-px", type=float, default=0.0)
    parser.add_argument("--step-summary-json", type=Path, required=True)
    parser.add_argument("--step-baseline-case", required=True)
    parser.add_argument("--step-candidate-case", required=True)
    parser.add_argument("--step-metric", default="step_std_dx_px")
    parser.add_argument("--step-tolerance-px", type=float, default=0.0)
    parser.add_argument("--output-json", type=Path, required=True)
    parser.add_argument("--no-fail-exit", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    boundary_report = json.loads(Path(args.boundary_gate_json).read_text(encoding="utf-8"))
    real_motion_summary = json.loads(Path(args.real_motion_summary_json).read_text(encoding="utf-8"))
    step_summary = json.loads(Path(args.step_summary_json).read_text(encoding="utf-8"))
    report = evaluate_triple_gate(
        boundary_report=boundary_report,
        real_motion_summary=real_motion_summary,
        real_motion_baseline_case=str(args.real_motion_baseline_case),
        real_motion_candidate_case=str(args.real_motion_candidate_case),
        real_motion_metric=str(args.real_motion_metric),
        real_motion_tolerance_px=float(args.real_motion_tolerance_px),
        step_summary=step_summary,
        step_baseline_case=str(args.step_baseline_case),
        step_candidate_case=str(args.step_candidate_case),
        step_metric=str(args.step_metric),
        step_tolerance_px=float(args.step_tolerance_px),
    )
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(
        json.dumps(
            {
                "pass": report["pass"],
                "boundary_pass": report["boundary_gate"]["pass"],
                "real_motion_pass": report["real_motion_gate"]["pass"],
                "step_pass": report["step_gate"]["pass"],
            },
            indent=2,
        )
    )
    if report["pass"] or bool(args.no_fail_exit):
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())

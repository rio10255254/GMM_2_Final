from __future__ import annotations

import argparse
import csv
import json
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

import numpy as np

from displacement_common import write_csv, write_json
from measure_gmf_template import measure_sequence
_PROJECT_ROOT = Path(__file__).resolve().parents[3]


PROJECT_ROOT = Path(str(_PROJECT_ROOT))
CAMERA_PIXEL_UM = 3.45


@dataclass(frozen=True)
class GateSpec:
    dataset: str
    group: str
    root: Path
    cases: dict[str, str]
    nominal_um: float
    object_um_per_px: float
    roi: tuple[int, int, int, int] | None
    roi_label: str
    polarity: str
    mode: str = "multi"
    signal_mode: str = "intensity"
    pattern: str = "*.bmp"
    blur_sigma: float = 0.8
    threshold_quantile: float = 0.65
    min_area: int = 20
    max_components: int = 60
    local_radius: int = 24
    cluster_radius: float = 1.5


def _case_templates_100mg() -> dict[str, str]:
    return {
        "raw": r"raw_inputs\{group}\bmp",
        "r61": r"r61_v16_psfoff_{group}\bmp",
        "v7": r"r62_v7_seqgeom_noamp_lr3e7_psfoff_{group}\bmp",
    }


def _case_templates_20x_5x() -> dict[str, str]:
    return {
        "raw": r"raw_inputs\{group}\bmp",
        "r61": r"r61_v16_psfoff_{group}\bmp",
        "v7": r"r62_v7_seqgeom_noamp_lr3e7_psfoff_{group}\bmp",
    }


def default_case_specs() -> list[GateSpec]:
    root_100mg = PROJECT_ROOT / "20260702_100MG_displacement_analysis"
    root_20x_5x = PROJECT_ROOT / "20260704_20x_5x_analysis"
    specs: list[GateSpec] = []
    for group, nominal in (("x_1um", 1.0), ("x_0p5um", 0.5)):
        specs.append(
            GateSpec(
                dataset="20260702_100MG",
                group=group,
                root=root_100mg,
                cases=_case_templates_100mg(),
                nominal_um=nominal,
                object_um_per_px=CAMERA_PIXEL_UM / 50.0,
                roi=(1080, 40, 820, 700),
                roi_label="top_right_dark_pillar_array",
                polarity="dark",
                mode="multi",
                local_radius=24,
                cluster_radius=1.5,
            )
        )
    for mag, scale in (("20x", CAMERA_PIXEL_UM / 20.0), ("5x", CAMERA_PIXEL_UM / 5.0)):
        for suffix, nominal in (("1um", 1.0), ("0p5um", 0.5)):
            specs.append(
                GateSpec(
                    dataset="20260704_20x_5x",
                    group=f"{mag}_{suffix}",
                    root=root_20x_5x,
                    cases=_case_templates_20x_5x(),
                    nominal_um=nominal,
                    object_um_per_px=scale,
                    roi=(650, 150, 520, 360),
                    roi_label="small_bright_dot_grid",
                    polarity="bright",
                    mode="multi",
                    local_radius=10,
                    cluster_radius=1.0,
                )
            )
    return specs


def _safe_token(text: str) -> str:
    return "".join(ch if ch.isalnum() else "_" for ch in text).strip("_") or "case"


def apply_extra_case_templates(specs: list[GateSpec], extra_cases: list[str] | None) -> list[GateSpec]:
    if not extra_cases:
        return specs

    parsed: dict[str, str] = {}
    for item in extra_cases:
        if "=" not in item:
            raise ValueError(
                f"Invalid extra case {item!r}; expected case=relative_template, "
                r"for example v8=r62_v8_gmfgate_psfoff_{group}\bmp"
            )
        name, template = item.split("=", 1)
        name = name.strip()
        template = template.strip()
        if not name or not template:
            raise ValueError(
                f"Invalid extra case {item!r}; expected case=relative_template with non-empty values"
            )
        parsed[name] = template

    out: list[GateSpec] = []
    for spec in specs:
        cases = dict(spec.cases)
        cases.update(parsed)
        out.append(replace(spec, cases=cases))
    return out


def apply_mode_override(specs: list[GateSpec], mode: str | None) -> list[GateSpec]:
    if not mode:
        return specs
    if mode not in {"single", "multi", "pairwise"}:
        raise ValueError("mode override must be single, multi, or pairwise")
    return [replace(spec, mode=mode) for spec in specs]


def apply_signal_mode_override(specs: list[GateSpec], signal_mode: str | None) -> list[GateSpec]:
    if not signal_mode:
        return specs
    if signal_mode not in {"intensity", "edge"}:
        raise ValueError("signal mode override must be intensity or edge")
    return [replace(spec, signal_mode=signal_mode) for spec in specs]


def resolve_case_dir(spec: GateSpec, case: str) -> Path:
    if case not in spec.cases:
        raise KeyError(f"case {case!r} is not configured for {spec.dataset}/{spec.group}")
    return spec.root / spec.cases[case].format(group=spec.group)


def summarize_measurement(spec: GateSpec, case: str, summary: dict[str, Any]) -> dict[str, Any]:
    std_px = summary.get("std_dx_px")
    mean_dx_px = summary.get("mean_dx_px")
    std_um = None if std_px is None else float(std_px) * float(spec.object_um_per_px)
    step_um = None if mean_dx_px is None else abs(float(mean_dx_px)) * float(spec.object_um_per_px)
    step_error_um = None if step_um is None else abs(float(step_um) - float(spec.nominal_um))
    failed = int(summary.get("failed_step_count", 0) or 0)
    valid_steps = int(summary.get("valid_step_count", 0) or 0)
    status = "ok" if valid_steps > 0 and failed == 0 and std_um is not None else "check"
    return {
        "dataset": spec.dataset,
        "group": spec.group,
        "case": case,
        "roi_label": spec.roi_label,
        "polarity": spec.polarity,
        "mode": spec.mode,
        "signal_mode": spec.signal_mode,
        "nominal_um": float(spec.nominal_um),
        "object_um_per_px": float(spec.object_um_per_px),
        "valid_step_count": valid_steps,
        "failed_step_count": failed,
        "mean_dx_px": mean_dx_px,
        "std_dx_px": std_px,
        "std_um": std_um,
        "step_um": step_um,
        "step_error_um": step_error_um,
        "status": status,
        "input_dir": summary.get("input_dir", ""),
    }


def evaluate_spec(spec: GateSpec, output_dir: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for case in spec.cases:
        input_dir = resolve_case_dir(spec, case)
        token = f"{_safe_token(spec.dataset)}_{_safe_token(spec.group)}_{_safe_token(case)}"
        steps_csv = output_dir / f"{token}_steps.csv"
        summary_json = output_dir / f"{token}_summary.json"
        step_rows, summary = measure_sequence(
            input_dir,
            crop=spec.roi,
            polarity=spec.polarity,
            mode=spec.mode,
            signal_mode=spec.signal_mode,
            pattern=spec.pattern,
            blur_sigma=spec.blur_sigma,
            threshold_quantile=spec.threshold_quantile,
            min_area=spec.min_area,
            max_components=spec.max_components,
            local_radius=spec.local_radius,
            cluster_radius=spec.cluster_radius,
        )
        summary["steps_csv"] = str(steps_csv)
        fields = [
            "frame_index",
            "filename",
            "ref_filename",
            "mode",
            "dx_px",
            "dy_px",
            "cumulative_dx_px",
            "cumulative_dy_px",
            "feature_count",
            "tracked_feature_count",
            "median_feature_weight",
            "status",
            "message",
        ]
        write_csv(steps_csv, step_rows, fields)
        write_json(summary_json, summary)
        row = summarize_measurement(spec, case, summary)
        row["steps_csv"] = str(steps_csv)
        row["summary_json"] = str(summary_json)
        rows.append(row)
    return rows


def build_comparison(
    rows: list[dict[str, Any]],
    *,
    baseline_case: str = "raw",
    candidate_case: str = "v7",
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    keys = sorted({(str(row["dataset"]), str(row["group"])) for row in rows})
    for dataset, group in keys:
        group_rows = [
            row
            for row in rows
            if str(row["dataset"]) == dataset and str(row["group"]) == group and row.get("std_um") is not None
        ]
        if not group_rows:
            continue
        by_case = {str(row["case"]): row for row in group_rows}
        if baseline_case not in by_case or candidate_case not in by_case:
            continue
        best = min(group_rows, key=lambda row: float(row["std_um"]))
        baseline_std = float(by_case[baseline_case]["std_um"])
        candidate_std = float(by_case[candidate_case]["std_um"])
        improvement = (
            (baseline_std - candidate_std) / baseline_std * 100.0
            if baseline_std > 0.0
            else 0.0
        )
        out.append(
            {
                "dataset": dataset,
                "group": group,
                "baseline_case": baseline_case,
                "candidate_case": candidate_case,
                "best_case": str(best["case"]),
                "baseline_std_um": baseline_std,
                "candidate_std_um": candidate_std,
                "candidate_vs_baseline_improvement_pct": round(float(improvement), 6),
            }
        )
    return out


def build_selection_summary(
    rows: list[dict[str, Any]],
    *,
    candidate_case: str,
    primary_keys: set[tuple[str, str]],
    baseline_case: str = "raw",
) -> dict[str, Any]:
    improvements: list[float] = []
    guardrail_improvements: list[float] = []
    keys = sorted({(str(row["dataset"]), str(row["group"])) for row in rows})
    for dataset, group in keys:
        group_rows = [
            row
            for row in rows
            if str(row["dataset"]) == dataset and str(row["group"]) == group and row.get("std_um") is not None
        ]
        by_case = {str(row["case"]): row for row in group_rows}
        if baseline_case not in by_case or candidate_case not in by_case:
            continue
        baseline_std = float(by_case[baseline_case]["std_um"])
        candidate_std = float(by_case[candidate_case]["std_um"])
        improvement = (
            (baseline_std - candidate_std) / baseline_std * 100.0
            if baseline_std > 0.0
            else 0.0
        )
        if (dataset, group) in primary_keys:
            improvements.append(improvement)
        else:
            guardrail_improvements.append(improvement)

    guardrail_regressions = [value for value in guardrail_improvements if value < 0.0]
    primary_mean = float(np.mean(improvements)) if improvements else 0.0
    guardrail_mean = float(np.mean(guardrail_improvements)) if guardrail_improvements else 0.0
    worst_regression = min(guardrail_regressions) if guardrail_regressions else 0.0
    return {
        "candidate_case": candidate_case,
        "baseline_case": baseline_case,
        "primary_case_count": len(improvements),
        "guardrail_case_count": len(guardrail_improvements),
        "primary_mean_improvement_pct": round(primary_mean, 6),
        "guardrail_mean_improvement_pct": round(guardrail_mean, 6),
        "guardrail_worse_count": len(guardrail_regressions),
        "guardrail_worst_regression_pct": round(float(worst_regression), 6),
        "selection_score_pct": round(primary_mean + min(0.0, worst_regression), 6),
    }


def _write_report(output_dir: Path, rows: list[dict[str, Any]], comparison: list[dict[str, Any]]) -> Path:
    report_path = output_dir / "GMF_LIKE_THESIS_GATE_REPORT.md"
    lines = [
        "# GMF-like thesis displacement gate",
        "",
        "This gate uses fixed ROIs and the open GMF-like local fitting tool.",
        "It is intended for model selection on thesis displacement behavior, not for training loss by itself.",
        "",
        "## Case Results",
        "",
        "| dataset | group | case | std um | step um | status |",
        "|---|---|---|---:|---:|---|",
    ]
    for row in rows:
        std_um = "" if row.get("std_um") is None else f"{float(row['std_um']):.6f}"
        step_um = "" if row.get("step_um") is None else f"{float(row['step_um']):.6f}"
        lines.append(
            f"| {row['dataset']} | {row['group']} | {row['case']} | {std_um} | {step_um} | {row['status']} |"
        )
    lines.extend(
        [
            "",
            "## Raw vs Candidate",
            "",
            "| dataset | group | best | candidate improvement vs Raw |",
            "|---|---|---|---:|",
        ]
    )
    for row in comparison:
        lines.append(
            f"| {row['dataset']} | {row['group']} | {row['best_case']} | "
            f"{float(row['candidate_vs_baseline_improvement_pct']):.2f}% |"
        )
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return report_path


def _fields_for_rows(rows: list[dict[str, Any]]) -> list[str]:
    fields: list[str] = []
    for row in rows:
        for key in row:
            if key not in fields:
                fields.append(key)
    return fields


def run_gate(
    output_dir: Path,
    *,
    candidate_case: str = "v7",
    extra_cases: list[str] | None = None,
    mode_override: str | None = None,
    signal_mode_override: str | None = None,
) -> dict[str, str]:
    output_dir.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, Any]] = []
    specs = apply_extra_case_templates(default_case_specs(), extra_cases)
    specs = apply_mode_override(specs, mode_override)
    specs = apply_signal_mode_override(specs, signal_mode_override)
    for spec in specs:
        rows.extend(evaluate_spec(spec, output_dir))
    comparison = build_comparison(rows, baseline_case="raw", candidate_case=candidate_case)
    selection_summary = build_selection_summary(
        rows,
        candidate_case=candidate_case,
        primary_keys={("20260702_100MG", "x_1um"), ("20260702_100MG", "x_0p5um")},
        baseline_case="raw",
    )
    results_csv = output_dir / "gmf_like_thesis_gate_results.csv"
    comparison_csv = output_dir / "gmf_like_thesis_gate_comparison.csv"
    selection_json = output_dir / "gmf_like_thesis_gate_selection_summary.json"
    write_csv(results_csv, rows, _fields_for_rows(rows))
    write_csv(comparison_csv, comparison, _fields_for_rows(comparison))
    write_json(selection_json, selection_summary)
    report = _write_report(output_dir, rows, comparison)
    manifest = {
        "algorithm": "gmf_like_gaussian_template_fixed_thesis_gate",
        "output_dir": str(output_dir),
        "results_csv": str(results_csv),
        "comparison_csv": str(comparison_csv),
        "selection_summary_json": str(selection_json),
        "report": str(report),
        "candidate_case": candidate_case,
        "extra_cases": extra_cases or [],
        "mode_override": mode_override or "",
        "signal_mode_override": signal_mode_override or "",
        "case_count": len(rows),
        "comparison_count": len(comparison),
    }
    manifest_path = output_dir / "gmf_like_thesis_gate_manifest.json"
    write_json(manifest_path, manifest)
    manifest["manifest"] = str(manifest_path)
    return {key: str(value) for key, value in manifest.items()}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run fixed GMF-like thesis displacement gate.")
    parser.add_argument(
        "--output-dir",
        default=str(
            PROJECT_ROOT
            / "Thesis_MOSR_Evidence"
            / "LabSystem_MOSR"
            / "Experiments"
            / "R62_TargetSampleBoost"
            / "reports"
            / "thesis_gmf_like_fixed_gate_latest"
        ),
    )
    parser.add_argument("--candidate-case", default="v7")
    parser.add_argument("--mode-override", choices=["single", "multi", "pairwise"])
    parser.add_argument("--signal-mode", choices=["intensity", "edge"])
    parser.add_argument(
        "--extra-case",
        action="append",
        default=[],
        help=(
            "Additional case template to evaluate, as case=relative_template. "
            r"Example: --extra-case v8=r62_v8_gmfgate_psfoff_{group}\bmp"
        ),
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()
    manifest = run_gate(
        Path(args.output_dir),
        candidate_case=str(args.candidate_case),
        extra_cases=list(args.extra_case),
        mode_override=args.mode_override,
        signal_mode_override=args.signal_mode,
    )
    print(json.dumps(manifest, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()

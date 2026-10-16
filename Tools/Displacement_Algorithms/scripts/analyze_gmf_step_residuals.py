from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path
from typing import Any, Iterable

import numpy as np

from displacement_common import write_csv, write_json


def _sample_std(values: list[float]) -> float:
    if len(values) <= 1:
        return 0.0
    return float(np.std(np.asarray(values, dtype=np.float64), ddof=1))


def best_contiguous_window(values: list[float], window_size: int) -> dict[str, float | int | None]:
    if not values:
        return {
            "best_window_count": 0,
            "best_window_start_step": None,
            "best_window_end_step": None,
            "best_window_mean_um": None,
            "best_window_std_um": None,
        }
    size = min(max(1, int(window_size)), len(values))
    best_start = 0
    best_std = math.inf
    best_mean = 0.0
    for start in range(0, len(values) - size + 1):
        window = values[start : start + size]
        std = _sample_std(window)
        if std < best_std:
            best_start = start
            best_std = std
            best_mean = float(np.mean(np.asarray(window, dtype=np.float64)))
    return {
        "best_window_count": size,
        "best_window_start_step": best_start + 1,
        "best_window_end_step": best_start + size,
        "best_window_mean_um": best_mean,
        "best_window_std_um": 0.0 if best_std is math.inf else float(best_std),
    }


def summarize_step_series(
    values_um: Iterable[float],
    *,
    trim_fraction: float = 0.10,
    window_size: int = 30,
) -> dict[str, float | int | None]:
    values = [float(value) for value in values_um if math.isfinite(float(value))]
    if not values:
        return {
            "count": 0,
            "all_mean_um": None,
            "all_std_um": None,
            "median_um": None,
            "trimmed_count": 0,
            "trimmed_mean_um": None,
            "trimmed_std_um": None,
            "max_abs_deviation_from_median_um": None,
            **best_contiguous_window([], window_size),
        }

    median = float(np.median(np.asarray(values, dtype=np.float64)))
    trim_count = int(math.floor(len(values) * max(0.0, min(0.49, float(trim_fraction)))))
    ranked = sorted(values, key=lambda value: abs(value - median))
    trimmed = ranked[: len(values) - trim_count] if trim_count > 0 else list(values)
    deviations = [abs(value - median) for value in values]
    return {
        "count": len(values),
        "all_mean_um": float(np.mean(np.asarray(values, dtype=np.float64))),
        "all_std_um": _sample_std(values),
        "median_um": median,
        "trimmed_count": len(trimmed),
        "trimmed_mean_um": float(np.mean(np.asarray(trimmed, dtype=np.float64))),
        "trimmed_std_um": _sample_std(trimmed),
        "max_abs_deviation_from_median_um": max(deviations) if deviations else 0.0,
        **best_contiguous_window(values, window_size),
    }


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def _valid_step_values_um(steps_csv: Path, object_um_per_px: float) -> list[float]:
    rows = _read_csv(steps_csv)
    values: list[float] = []
    for row in rows:
        if row.get("status") != "ok":
            continue
        if str(row.get("frame_index", "")) == "0":
            continue
        dx_text = row.get("dx_px", "")
        if dx_text == "":
            continue
        values.append(abs(float(dx_text)) * float(object_um_per_px))
    return values


def summarize_gate_results(
    results_csv: Path,
    *,
    trim_fraction: float = 0.10,
    window_size: int = 30,
) -> list[dict[str, Any]]:
    rows = _read_csv(results_csv)
    out: list[dict[str, Any]] = []
    for row in rows:
        steps_csv = Path(str(row["steps_csv"]))
        object_um_per_px = float(row["object_um_per_px"])
        values = _valid_step_values_um(steps_csv, object_um_per_px)
        summary = summarize_step_series(values, trim_fraction=trim_fraction, window_size=window_size)
        out.append(
            {
                "dataset": row["dataset"],
                "group": row["group"],
                "case": row["case"],
                "nominal_um": float(row.get("nominal_um") or 0.0),
                "source_steps_csv": str(steps_csv),
                **summary,
            }
        )
    return out


def _improvement_pct(baseline: float | None, candidate: float | None) -> float | None:
    if baseline is None or candidate is None or baseline <= 0.0:
        return None
    return round((float(baseline) - float(candidate)) / float(baseline) * 100.0, 6)


def build_case_comparison(
    rows: list[dict[str, Any]],
    *,
    baseline_case: str = "raw",
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    keys = sorted({(str(row["dataset"]), str(row["group"])) for row in rows})
    for dataset, group in keys:
        group_rows = [row for row in rows if row["dataset"] == dataset and row["group"] == group]
        by_case = {str(row["case"]): row for row in group_rows}
        if baseline_case not in by_case:
            continue
        baseline = by_case[baseline_case]
        for case, row in sorted(by_case.items()):
            if case == baseline_case:
                continue
            out.append(
                {
                    "dataset": dataset,
                    "group": group,
                    "case": case,
                    "all_improvement_pct": _improvement_pct(
                        baseline.get("all_std_um"), row.get("all_std_um")
                    ),
                    "trimmed_improvement_pct": _improvement_pct(
                        baseline.get("trimmed_std_um"), row.get("trimmed_std_um")
                    ),
                    "best_window_improvement_pct": _improvement_pct(
                        baseline.get("best_window_std_um"), row.get("best_window_std_um")
                    ),
                    "all_std_um": row.get("all_std_um"),
                    "trimmed_std_um": row.get("trimmed_std_um"),
                    "best_window_std_um": row.get("best_window_std_um"),
                    "baseline_all_std_um": baseline.get("all_std_um"),
                    "baseline_trimmed_std_um": baseline.get("trimmed_std_um"),
                    "baseline_best_window_std_um": baseline.get("best_window_std_um"),
                }
            )
    return out


def _fields(rows: list[dict[str, Any]]) -> list[str]:
    fields: list[str] = []
    for row in rows:
        for key in row:
            if key not in fields:
                fields.append(key)
    return fields


def run_analysis(
    results_csv: Path,
    output_dir: Path,
    *,
    trim_fraction: float,
    window_size: int,
    baseline_case: str,
) -> dict[str, str]:
    output_dir.mkdir(parents=True, exist_ok=True)
    summary_rows = summarize_gate_results(
        results_csv,
        trim_fraction=trim_fraction,
        window_size=window_size,
    )
    comparison_rows = build_case_comparison(summary_rows, baseline_case=baseline_case)
    summary_csv = output_dir / "gmf_step_residual_summary.csv"
    comparison_csv = output_dir / "gmf_step_residual_comparison.csv"
    manifest_json = output_dir / "gmf_step_residual_manifest.json"
    write_csv(summary_csv, summary_rows, _fields(summary_rows))
    write_csv(comparison_csv, comparison_rows, _fields(comparison_rows))
    manifest = {
        "results_csv": str(results_csv),
        "output_dir": str(output_dir),
        "summary_csv": str(summary_csv),
        "comparison_csv": str(comparison_csv),
        "trim_fraction": trim_fraction,
        "window_size": window_size,
        "baseline_case": baseline_case,
        "summary_count": len(summary_rows),
        "comparison_count": len(comparison_rows),
    }
    write_json(manifest_json, manifest)
    manifest["manifest_json"] = str(manifest_json)
    return {key: str(value) for key, value in manifest.items()}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Analyze per-step GMF stability residuals.")
    parser.add_argument("--results-csv", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--trim-fraction", type=float, default=0.10)
    parser.add_argument("--window-size", type=int, default=30)
    parser.add_argument("--baseline-case", default="raw")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    manifest = run_analysis(
        Path(args.results_csv),
        Path(args.output_dir),
        trim_fraction=float(args.trim_fraction),
        window_size=int(args.window_size),
        baseline_case=str(args.baseline_case),
    )
    print(json.dumps(manifest, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()

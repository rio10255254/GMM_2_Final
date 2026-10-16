"""Audit row counts and keys emitted by evaluate_sequence_bank.py."""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]


def audit(folder: Path) -> dict:
    errors = []
    positions = pd.read_csv(folder / "positions.csv")
    steps = pd.read_csv(folder / "steps.csv")
    summaries = pd.read_csv(folder / "sequence_summary.csv")
    shapes = pd.read_csv(folder / "shape_detail.csv")
    expected = {"positions": 13104, "steps": 6912, "sequence_summary": 1728, "shape_detail": 13104}
    observed = {"positions": len(positions), "steps": len(steps), "sequence_summary": len(summaries), "shape_detail": len(shapes)}
    for key, value in expected.items():
        if observed[key] != value:
            errors.append(f"{key} row count {observed[key]} != {value}")
    position_key = ["method", "sequence_id", "frame_index", "feature_id", "estimator"]
    step_key = ["method", "sequence_id", "start_frame", "end_frame", "feature_id"]
    summary_key = ["method", "sequence_id", "estimator"]
    shape_key = ["method", "scene_id", "condition_id", "frame_index"]
    duplicates = {}
    for name, frame, key in (("positions", positions, position_key), ("steps", steps, step_key), ("sequence_summary", summaries, summary_key), ("shape_detail", shapes, shape_key)):
        duplicate_count = int(frame.duplicated(key).sum()); duplicates[name] = duplicate_count
        if duplicate_count: errors.append(f"{name} duplicate keys: {duplicate_count}")
    for name, frame in (("positions", positions), ("steps", steps), ("sequence_summary", summaries), ("shape_detail", shapes)):
        numeric = frame.select_dtypes(include=[np.number])
        if not np.isfinite(numeric.to_numpy(dtype=float, na_value=np.nan)[~np.isnan(numeric.to_numpy(dtype=float, na_value=np.nan))]).all():
            errors.append(f"{name} contains nonfinite numeric values")
    method_counts = positions.groupby("method").size().to_dict()
    if method_counts != {"Raw": 4368, "R118_E12": 4368, "R109_E48": 4368}:
        errors.append(f"method population mismatch: {method_counts}")
    invalid_reasons = positions.loc[~positions["valid"].astype(bool), "failure_reason"].fillna("missing").value_counts().to_dict()
    return {"schema_version": 1, "status": "pass" if not errors else "blocked", "created_at_utc": datetime.now(timezone.utc).isoformat(), "expected": expected, "observed": observed, "duplicates": duplicates, "method_counts": method_counts, "invalid_reasons": invalid_reasons, "errors": errors, "population": "development common bank; no confirmation inputs", "meaning": "Mechanical result audit only; scientific effects require the paired summaries and reports."}


def main():
    parser = argparse.ArgumentParser(); parser.add_argument("--folder", type=Path, default=ROOT / "results/frozen_sequences"); parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args(); result = audit(args.folder); output = args.output or args.folder / "audit_verified.json"
    if output.exists(): raise FileExistsError(output)
    output.write_text(json.dumps(result, indent=2), encoding="utf-8"); print(json.dumps(result, indent=2)); return 0 if result["status"] == "pass" else 2


if __name__ == "__main__": raise SystemExit(main())

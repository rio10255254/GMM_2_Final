"""Run the locked center-nine audit and summarize the predeclared Raw-ranked 30 steps."""

from __future__ import annotations

import argparse
import hashlib
import json
import statistics
import sys
from pathlib import Path

import numpy as np
import pandas as pd


EXPERIMENT_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = EXPERIMENT_ROOT.parents[1]
CHAPTER_ROOT = (
    REPO_ROOT
    / "Thesis_MOSR_Evidence"
    / "Final_Data_Figures"
    / "04_V42_NEURAL_NETWORK_RESULTS"
)
CURRENT_ROOT = CHAPTER_ROOT.parent / "01_CURRENT_THESIS_RESULTS_V42_CENTER9"
AUDIT_SCRIPT_ROOT = CURRENT_ROOT / "scripts"
SOURCE_CONFIG = CURRENT_ROOT / "config" / "sequence_center9_50x20x.json"
SELECTION_LOCK = CHAPTER_ROOT / "tables" / "top30_raw_motion_selection.csv"
SEQUENCE_ORDER = ("50x_x_0p5um", "50x_x_1um", "20x_0p5um", "20x_1um")
RECON_ALIASES = {
    "50x_x_0p5um": "50x_0p5um",
    "50x_x_1um": "50x_1um",
    "20x_0p5um": "20x_0p5um",
    "20x_1um": "20x_1um",
}

sys.path.insert(0, str(AUDIT_SCRIPT_ROOT))
from audit_all_displacement_sequences import run_unified_audit  # noqa: E402


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    digest.update(path.read_bytes())
    return digest.hexdigest()


def logical(series: pd.Series) -> pd.Series:
    if series.dtype == bool:
        return series
    return series.astype(str).str.lower().isin({"true", "1", "yes"})


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--variant", required=True)
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--recon-root", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()

    config = json.loads(SOURCE_CONFIG.read_text(encoding="utf-8"))
    for sequence in SEQUENCE_ORDER:
        directory = args.recon_root / sequence
        if not directory.is_dir():
            directory = args.recon_root / RECON_ALIASES[sequence]
        expected = int(config["sequences"][sequence]["frame_count"])
        actual = sum(1 for _ in directory.glob("*.bmp"))
        if actual != expected:
            raise RuntimeError(f"{sequence}: expected {expected} frames, found {actual}")
        config["sequences"][sequence]["v42_dir"] = directory.as_posix()

    args.output_dir.mkdir(parents=True, exist_ok=True)
    config_path = args.output_dir / "audit_config.json"
    config_path.write_text(json.dumps(config, indent=2, ensure_ascii=False), encoding="utf-8")
    audit_root = args.output_dir / "audit"
    run_unified_audit(
        output_root=audit_root,
        candidate_root=audit_root / "candidate",
        config_path=config_path,
    )

    all_pairs = pd.read_csv(audit_root / "tables" / "all_adjacent_pairs_audit.csv")
    selection = pd.read_csv(SELECTION_LOCK)
    selection = selection.loc[logical(selection["top30_raw_motion_selected"])].copy()
    if selection.groupby("sequence").size().to_dict() != {name: 30 for name in SEQUENCE_ORDER}:
        raise RuntimeError("Selection lock does not contain exactly 30 steps per sequence")
    locked = selection[["sequence", "end_frame_index", "raw_motion_quality_rank"]].merge(
        all_pairs,
        on=["sequence", "end_frame_index"],
        how="left",
        validate="one_to_one",
    )
    if len(locked) != 120:
        raise RuntimeError(f"Expected 120 locked steps, found {len(locked)}")

    records: list[dict[str, object]] = []
    per_step_records: list[dict[str, object]] = []
    for sequence in SEQUENCE_ORDER:
        group = locked.loc[locked["sequence"].eq(sequence)].copy()
        nominal = float(group["nominal_step_um"].iloc[0])
        valid = logical(group["v42_evaluable"]) & logical(group["v42_boundary_valid"])
        valid &= group["v42_boundary_valid_pillars"].fillna(0).astype(float).eq(9)
        raw_dx = group["raw_boundary_dx_um"].to_numpy(float)
        method_dx = group.loc[valid, "v42_boundary_dx_um"].to_numpy(float)
        raw_within = group["raw_within_grid_nm"].to_numpy(float)
        method_within = group.loc[valid, "v42_within_grid_nm"].to_numpy(float)
        if not np.isfinite(raw_dx).all() or not np.isfinite(raw_within).all():
            raise RuntimeError(f"{sequence}: Raw lock contains non-finite values")

        def step_sd_nm(values: np.ndarray) -> float:
            return float(statistics.stdev(np.abs(values).tolist()) * 1000.0) if len(values) >= 2 else float("nan")

        def command_mae_nm(values: np.ndarray) -> float:
            return float(np.mean(np.abs(np.abs(values) - nominal)) * 1000.0) if len(values) else float("nan")

        raw_sd = step_sd_nm(raw_dx)
        method_sd = step_sd_nm(method_dx)
        raw_command = command_mae_nm(raw_dx)
        method_command = command_mae_nm(method_dx)
        raw_grid = float(np.mean(raw_within))
        method_grid = float(np.mean(method_within)) if len(method_within) else float("nan")
        records.append(
            {
                "variant": args.variant,
                "seed": args.seed,
                "sequence": sequence,
                "magnification": str(group["magnification"].iloc[0]),
                "nominal_step_um": nominal,
                "locked_step_count": len(group),
                "method_valid_step_count": int(valid.sum()),
                "method_invalid_step_count": int((~valid).sum()),
                "raw_step_sd_nm": raw_sd,
                "method_step_sd_nm": method_sd,
                "step_sd_reduction_vs_raw_pct": 100.0 * (raw_sd - method_sd) / raw_sd,
                "raw_command_mae_nm": raw_command,
                "method_command_mae_nm": method_command,
                "command_mae_reduction_vs_raw_pct": 100.0 * (raw_command - method_command) / raw_command,
                "raw_within_grid_nm": raw_grid,
                "method_within_grid_nm": method_grid,
                "within_grid_reduction_vs_raw_pct": 100.0 * (raw_grid - method_grid) / raw_grid,
            }
        )
        for row, is_valid in zip(group.itertuples(index=False), valid.tolist()):
            per_step_records.append(
                {
                    "variant": args.variant,
                    "seed": args.seed,
                    "sequence": sequence,
                    "end_frame_index": int(row.end_frame_index),
                    "raw_motion_quality_rank": int(row.raw_motion_quality_rank),
                    "method_valid": bool(is_valid),
                    "nominal_step_um": nominal,
                    "raw_boundary_dx_um": float(row.raw_boundary_dx_um),
                    "method_boundary_dx_um": float(row.v42_boundary_dx_um) if is_valid else float("nan"),
                    "raw_within_grid_nm": float(row.raw_within_grid_nm),
                    "method_within_grid_nm": float(row.v42_within_grid_nm) if is_valid else float("nan"),
                    "method_valid_pillars": int(row.v42_boundary_valid_pillars) if is_valid else 0,
                    "method_failure_reason": "" if is_valid else str(row.v42_failure_reason),
                }
            )

    summary = pd.DataFrame(records)
    per_step = pd.DataFrame(per_step_records)
    summary.to_csv(args.output_dir / "displacement_summary_top30.csv", index=False, float_format="%.12g")
    per_step.to_csv(args.output_dir / "displacement_per_step_top30.csv", index=False, float_format="%.12g")
    metadata = {
        "variant": args.variant,
        "seed": args.seed,
        "recon_root": str(args.recon_root.resolve()),
        "selection_lock": str(SELECTION_LOCK.resolve()),
        "selection_lock_sha256": sha256(SELECTION_LOCK),
        "locked_step_count": 120,
        "selection_role_of_candidate": "none",
        "claim_limit": "nominal-command consistency and repeatability, not independent stage truth",
    }
    (args.output_dir / "metadata.json").write_text(
        json.dumps(metadata, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(summary.to_string(index=False))


if __name__ == "__main__":
    main()

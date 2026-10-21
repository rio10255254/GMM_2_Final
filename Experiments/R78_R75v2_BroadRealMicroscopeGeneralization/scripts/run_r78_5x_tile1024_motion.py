from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import run_r78 as primary


def main() -> None:
    config = primary.read_json(primary.CONFIG_PATH)
    locked = pd.read_csv(config["locked_r68_evidence"]["measurements"])
    locked["raw_reference_valid"] = primary.as_bool(locked["raw_reference_valid"])
    locked = locked.loc[locked["sequence"].isin(["5x_0p5um", "5x_1um"])].copy()
    original_recon = primary.R75_RECON
    try:
        primary.R75_RECON = ROOT / "results" / "diagnostics" / "5x_tile1024_full"
        large_rows = primary.compute_r75_rows(config, locked)
    finally:
        primary.R75_RECON = original_recon
    large_rows["method"] = "R75v2E100_tile1024"
    primary_table = pd.read_csv(primary.TABLES / "tile_motion_measurements.csv")
    primary_table = primary_table.loc[
        primary_table["sequence"].isin(["5x_0p5um", "5x_1um"])
    ].copy()
    combined = pd.concat([primary_table, large_rows], ignore_index=True)
    summary = primary.summarize_motion(combined, config["motion_gates"])
    summary.to_csv(primary.TABLES / "followup_5x_tile1024_motion_summary.csv", index=False)
    primary.write_json(
        primary.RESULTS / "followup_5x_tile1024_motion_decision.json",
        {
            "status": "complete",
            "evidence_role": "post_hoc_inference_setting_check",
            "tile1024_both_5x_sequences_pass_motion": bool(
                summary.loc[
                    summary["method"] == "R75v2E100_tile1024", "sequence_pass"
                ].all()
            ),
            "claim_limit": "The larger-tile setting was chosen after the locked primary run and is not a replacement for a fresh predeclared validation.",
        },
    )
    print(summary.to_string(index=False))


if __name__ == "__main__":
    main()

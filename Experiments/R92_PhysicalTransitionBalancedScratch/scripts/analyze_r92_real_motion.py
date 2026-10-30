"""Evaluate R92 E80 on the pre-locked 50x / 1 um real-motion sequence."""
from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import sys

import numpy as np
import pandas as pd
PROJECT_ROOT = Path(__file__).resolve().parents[3]


ROOT = Path(__file__).resolve().parents[1]
PROTOCOL = ROOT / "config" / "capability_validation_20260812.json"
R91_ANALYZER = Path(str(PROJECT_ROOT / 'Experiments/R91_DetailDecoupledScratch/scripts/analyze_r91_real_motion.py'))
ISO_SCRIPT = Path(str(PROJECT_ROOT / 'LabSystem_MOSR/Experiments/Modern_Restoration_Benchmarks_20260719/analyze_isocontour_boundary_displacement.py'))
SEQUENCE_NAME = "50x_x_1um"


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    os.replace(temporary, path)


def main() -> int:
    protocol = json.loads(PROTOCOL.read_text(encoding="utf-8"))
    arm = protocol["arms"]["real_motion"]
    results = Path(PROJECT_ROOT / protocol["output_root"])
    recon_root = results / "reconstructions_fp32"
    output = results / "motion_analysis_fp32"
    tables = output / "tables"
    figures = output / "figures"
    helper = load_module("r92_motion_helpers", R91_ANALYZER)
    helper.RECON_ROOT = recon_root
    helper.FIGURES = figures
    helper.SEQUENCE_NAME = SEQUENCE_NAME

    method_dirs = {
        "Raw": Path(PROJECT_ROOT / arm["ordered_source"]),
        "R92_E80": recon_root / "motion" / "E080",
    }
    sequence = json.loads(Path(PROJECT_ROOT / arm["sequence_config"]).read_text(encoding="utf-8"))["sequences"][SEQUENCE_NAME]
    frame_count = int(sequence["frame_count"])
    for directory in method_dirs.values():
        helper.method_paths(directory, frame_count)
    selected = helper.locked_steps(Path(PROJECT_ROOT / arm["locked_steps"]))
    audit = helper.source_and_manifest_audit(protocol, method_dirs, frame_count)
    if not audit["requested_and_ordered_sources_are_same_files"] or not audit["all_stage_manifests_pass"]:
        raise RuntimeError(f"Motion input audit failed: {audit}")

    iso = load_module("r92_external_isocontour", ISO_SCRIPT)
    iso_steps, iso_summary, tracking, positions = helper.run_isocontour(sequence, iso, selected, method_dirs)
    phase_steps, phase_summary = helper.run_phase(sequence, selected, method_dirs)
    iso_summary = helper.add_relative_columns(iso_summary)
    phase_summary = helper.add_relative_columns(phase_summary)
    common = int(iso_steps.loc[iso_steps["common_valid_locked"], "end_frame_index"].nunique())
    if common != 30:
        raise RuntimeError(f"Only {common}/30 locked steps are common-valid")

    tables.mkdir(parents=True, exist_ok=True)
    iso_steps.to_csv(tables / "isocontour_steps.csv", index=False, encoding="utf-8-sig")
    positions.to_csv(tables / "isocontour_positions.csv", index=False, encoding="utf-8-sig")
    iso_summary.to_csv(tables / "isocontour_summary.csv", index=False, encoding="utf-8-sig")
    phase_steps.to_csv(tables / "gmf_like_phase_steps.csv", index=False, encoding="utf-8-sig")
    phase_summary.to_csv(tables / "gmf_like_phase_summary.csv", index=False, encoding="utf-8-sig")
    old_sheet = helper.make_contact_sheet(method_dirs, tracking)
    sheet = old_sheet.with_name("r92_motion_center9_contact_sheet.png")
    if old_sheet != sheet:
        os.replace(old_sheet, sheet)

    payload = {
        "status": "complete",
        "protocol_id": protocol["protocol_id"],
        "audit": audit,
        "frame_count_per_method": frame_count,
        "locked_steps": 30,
        "common_valid_locked_steps": common,
        "isocontour_summary": iso_summary.replace({np.nan: None}).to_dict(orient="records"),
        "gmf_like_phase_summary": phase_summary.replace({np.nan: None}).to_dict(orient="records"),
        "contact_sheet": str(sheet),
        "external_gmf_used": False,
        "claim_limit": "Conditional stability on this locked real sequence, not independent absolute stage truth.",
    }
    write_json(output / "summary.json", payload)
    print(iso_summary.to_string(index=False))
    print(phase_summary.to_string(index=False))
    print(json.dumps({"status": "complete", "common_valid_locked_steps": common, "output": str(output)}), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

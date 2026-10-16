"""Write a compact, hash-backed R83 closeout inventory."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "reports" / "closeout_manifest.json"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def entry(relative: str) -> dict:
    path = ROOT / relative
    if not path.is_file():
        raise FileNotFoundError(path)
    return {"path": relative.replace("\\", "/"), "bytes": path.stat().st_size, "sha256": sha256(path)}


def main() -> int:
    decision = json.loads((ROOT / "results" / "final_confirmation" / "final_decision.json").read_text(encoding="utf-8"))
    if decision["recommended_mode"] != "R79":
        raise RuntimeError("Closeout decision unexpectedly changed.")
    formal = json.loads((ROOT / "data" / "r83_formal_severe_microscopy" / "manifest.json").read_text(encoding="utf-8"))
    holdout = json.loads((ROOT / "data" / "r83_locked_holdout_severe_microscopy" / "manifest.json").read_text(encoding="utf-8"))
    synthetic = pd.read_csv(ROOT / "results" / "final_confirmation" / "tables" / "locked_synthetic_per_pair.csv")
    real = pd.read_csv(ROOT / "results" / "final_confirmation" / "tables" / "real_motion_summary_with_r79.csv")
    sem = pd.read_csv(ROOT / "results" / "final_confirmation" / "SEM_reserved" / "results" / "acm_sem" / "tables" / "primary_contour_metrics.csv")
    invalidated = sorted(path.parent.name for path in (ROOT / "runs").glob("*/INVALIDATED.json"))
    valid_runs = sorted(path.name for path in (ROOT / "runs").iterdir() if path.is_dir() and not (path / "INVALIDATED.json").is_file())

    key_files = [
        "config/experiment.json",
        "config/architecture_contract.json",
        "README.md",
        "MANIFEST.md",
        "reports/R83_DESIGN.md",
        "reports/R83_RESULTS.md",
        "reports/final_confirmation_lock.json",
        "reports/formal_selection_lock.json",
        "reports/figures/r83_final_r74_comparison.png",
        "inference/infer_r83.py",
        "weights/selected/r83_model.pth.tar",
        "weights/selected/selection_manifest.json",
        "results/final_confirmation/final_decision.json",
        "results/final_confirmation/confirmation_manifest.json",
        "results/final_confirmation/tables/final_contour_image_summary.csv",
        "results/final_confirmation/tables/real_motion_summary_with_r79.csv",
        "results/final_confirmation/tables/tile_consistency.csv",
        "results/tile_context_diagnosis/tile_context_ablation_summary.csv",
    ]
    manifest = {
        "experiment_id": "R83_R79SevereMicroscopyStrengthening",
        "status": "complete_not_promoted",
        "completed_date": "2026-08-09",
        "recommended_mode": decision["recommended_mode"],
        "formal_baseline_unchanged": decision["formal_baseline_unchanged"],
        "selected_weight_sha256": sha256(ROOT / "weights" / "selected" / "r83_model.pth.tar"),
        "counts": {
            "formal_pairs": int(formal["total_pairs"]),
            "locked_holdout_pairs": int(holdout["total_pairs"]),
            "locked_synthetic_metric_rows": int(len(synthetic)),
            "locked_synthetic_methods": sorted(synthetic["method"].unique().tolist()),
            "real_motion_sequences_per_method": real.groupby("method")["sequence"].nunique().astype(int).to_dict(),
            "reserved_sem_pillars": int(sem["pillar_id"].nunique()),
            "reserved_sem_exposures": int(sem["exposure"].nunique()),
            "invalidated_runs": len(invalidated),
            "valid_diagnostic_or_pilot_runs": len(valid_runs),
        },
        "invalidated_runs": invalidated,
        "valid_diagnostic_or_pilot_runs": valid_runs,
        "key_files": [entry(relative) for relative in key_files],
    }
    OUTPUT.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(manifest["counts"], indent=2, ensure_ascii=False))
    print(OUTPUT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

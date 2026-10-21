"""Hash the locked R63 analysis specification before candidate scoring begins."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path


EXPERIMENT_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = EXPERIMENT_ROOT.parents[1]
OUTPUT = EXPERIMENT_ROOT / "results" / "analysis_freeze.json"
METRIC_ROOT = EXPERIMENT_ROOT / "results" / "evaluation" / "metrics"


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def main() -> None:
    candidate_metrics = list(METRIC_ROOT.rglob("*.csv")) if METRIC_ROOT.is_dir() else []
    if candidate_metrics:
        raise RuntimeError(
            "Analysis freeze must precede candidate metric generation: "
            + ", ".join(str(path) for path in candidate_metrics[:5])
        )
    files = [
        EXPERIMENT_ROOT / "PROTOCOL.md",
        EXPERIMENT_ROOT / "PROTOCOL_REVISION_LOG.md",
        EXPERIMENT_ROOT / "scripts" / "launch_r63.py",
        EXPERIMENT_ROOT / "scripts" / "evaluate_static_cd.py",
        EXPERIMENT_ROOT / "scripts" / "evaluate_displacement.py",
        EXPERIMENT_ROOT / "scripts" / "evaluate_synthetic_shifts.py",
        EXPERIMENT_ROOT / "scripts" / "aggregate_r63_results.py",
        EXPERIMENT_ROOT / "scripts" / "audit_claim_support.py",
        EXPERIMENT_ROOT / "scripts" / "audit_full_vs_raw.py",
        EXPERIMENT_ROOT / "scripts" / "build_r63_figures.m",
        REPO_ROOT
        / "Thesis_MOSR_Evidence"
        / "Final_Data_Figures"
        / "04_V42_NEURAL_NETWORK_RESULTS"
        / "tables"
        / "top30_raw_motion_selection.csv",
        REPO_ROOT
        / "Thesis_MOSR_Evidence"
        / "Final_Data_Figures"
        / "01_CURRENT_THESIS_RESULTS_V42_CENTER9"
        / "cd"
        / "tables"
        / "center9_cd_per_pillar.csv",
    ]
    missing = [str(path) for path in files if not path.is_file()]
    if missing:
        raise FileNotFoundError(f"Missing freeze input: {missing}")
    payload = {
        "frozen_at_utc": datetime.now(timezone.utc).isoformat(),
        "candidate_metric_files_present_at_freeze": False,
        "candidate_metric_root": str(METRIC_ROOT),
        "files": [
            {
                "logical_name": path.name,
                "path": str(path),
                "sha256": digest(path),
                "size_bytes": path.stat().st_size,
            }
            for path in files
        ],
    }
    OUTPUT.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(payload, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()

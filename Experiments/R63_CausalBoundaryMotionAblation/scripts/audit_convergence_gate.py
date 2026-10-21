"""Apply the pre-registered global 40-to-60 epoch escalation rule."""

from __future__ import annotations

import csv
import json
from pathlib import Path

import torch


EXPERIMENT_ROOT = Path(__file__).resolve().parents[1]
RUN_ROOT = EXPERIMENT_ROOT / "results" / "training_runs"
EXCLUSION_PATH = EXPERIMENT_ROOT / "results" / "excluded_training_runs.json"
VARIANTS = (
    "full_control",
    "no_geometry_anchor",
    "no_motion_consistency",
    "no_geometry_no_motion",
    "shift_safe_matched",
    "standard_upsample_matched",
)
SEED = 1261200


def completed_run(variant: str) -> Path:
    excluded = set()
    if EXCLUSION_PATH.is_file():
        payload = json.loads(EXCLUSION_PATH.read_text(encoding="utf-8"))
        excluded = {str(name) for name in payload.get("excluded_run_names", [])}
    runs = sorted(
        (
            path
            for path in RUN_ROOT.glob(f"training_progress_R63_MOSR_{variant}_s{SEED}_*")
            if path.name not in excluded
        ),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    for run in runs:
        if (run / "epoch_040.pth.tar").is_file():
            return run
    raise FileNotFoundError(f"Missing 40-epoch screening run: {variant}")


def main() -> None:
    records = []
    for variant in VARIANTS:
        run = completed_run(variant)
        checkpoint = run / "weights" / "best_tradeoff.pth.tar"
        if not checkpoint.is_file():
            raise FileNotFoundError(checkpoint)
        payload = torch.load(checkpoint, map_location="cpu")
        best_epoch = int(payload.get("epoch", -1))
        records.append(
            {
                "variant": variant,
                "seed": SEED,
                "run": str(run.resolve()),
                "best_epoch": best_epoch,
                "in_final_five_epochs": 36 <= best_epoch <= 40,
                "tradeoff_score": float(payload.get("tradeoff_score", float("nan"))),
                "best_val_rec": float(payload.get("best_val_rec", float("nan"))),
            }
        )
    late_count = sum(bool(record["in_final_five_epochs"]) for record in records)
    extend = late_count >= 3
    result = {
        "rule": "extend every condition and both seeds to epoch 60 when at least three of six seed-1261200 best checkpoints are in epochs 36-40",
        "late_best_count": late_count,
        "extend_to_epoch60": extend,
        "records": records,
    }
    table_root = EXPERIMENT_ROOT / "results" / "tables"
    table_root.mkdir(parents=True, exist_ok=True)
    with (table_root / "convergence_gate.csv").open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(records[0]))
        writer.writeheader()
        writer.writerows(records)
    output = EXPERIMENT_ROOT / "results" / "convergence_gate.json"
    output.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()

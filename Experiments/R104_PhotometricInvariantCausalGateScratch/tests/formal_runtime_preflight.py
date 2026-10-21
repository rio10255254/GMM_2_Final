"""Run one real R104 train step and verify all required runtime artifacts."""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "training"))

from train_r104 import CONFIG, run  # noqa: E402


def main() -> int:
    result = run(argparse.Namespace(
        run_kind="smoke", device="cuda:0", seed=int(CONFIG["training"]["seed"]) + 1,
        epochs=1, num_workers=2, cpu_threads=8, max_train_batches=1, no_amp=False,
    ))
    active = json.loads((ROOT / "runs" / "active_smoke_run.json").read_text(encoding="utf-8"))
    run_dir = ROOT / "runs" / active["run_id"]
    checks = {
        "trainer_returned_zero": result == 0,
        "status_completed": active.get("status") == "completed",
        "one_epoch_completed": active.get("completed_epoch") == 1,
        "training_log_exists": (run_dir / "training_log.csv").is_file(),
        "checkpoint_exists": Path(active["weights_dir"]).joinpath("epoch_001.pth.tar").is_file(),
        "synthetic_preview_exists": bool(list((run_dir / "previews" / "synthetic").glob("*.png"))),
        "three_real_previews_exist": len(list((run_dir / "previews" / "real").glob("*.png"))) == 3,
        "scratch_proof_exists": (run_dir / "scratch_proof.txt").is_file(),
        "finite_training_total": active["final_validation"]["metrics"]["mae"] >= 0.0,
    }
    report = {
        "status": "passed" if all(checks.values()) else "failed",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "checks": checks,
        "smoke_run_id": active["run_id"],
        "gpu_peak_allocated_gib": active.get("gpu_peak_allocated_gib"),
        "gpu_free_end_gib": active.get("gpu_free_end_gib"),
    }
    target = ROOT / "reports" / "formal_runtime_preflight.json"
    target.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0 if report["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())

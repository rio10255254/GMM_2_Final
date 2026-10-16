"""Run the fixed R143 validation phases after full training, with receipts."""
from __future__ import annotations

import subprocess
import sys
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from utils import load, now, save, sha


PHASES = (
    ("synthetic_selector", "scripts/evaluate_selector.py", "results/selector_evaluation.json"),
    ("real_reconstruction_and_measurement", "scripts/evaluate_real.py", "results/measurement_complete.json"),
    ("full_comparison", "scripts/compare_measurements.py", "results/comparison/complete.json"),
    ("real_optical_sensitivity", "scripts/probe_real_psf_effect.py", "results/real_psf_effect.json"),
    ("final_audit", "scripts/final_audit.py", "results/final_audit.json"),
    ("report", "scripts/write_report.py", "reports/R143_RESULTS.md"),
    ("figures", "scripts/plot_results.py", "reports/figures/training_and_short_step.png"),
)


def main() -> None:
    train = load(ROOT / "runs/formal_8192/training_complete.json")
    if train["updates"] != 8192 or sha(train["checkpoint"]["path"]) != train["checkpoint"]["sha256"]:
        raise RuntimeError("Full training has not been verified")
    status_path = ROOT / "runs/evaluation_status.json"
    for phase, script, output in PHASES:
        if (ROOT / output).is_file():
            print("EXISTING", phase, output, flush=True)
            continue
        save(status_path, dict(state="running", phase=phase, script=script,
                               script_sha256=sha(ROOT / script), updated_utc=now()))
        print("PHASE", phase, flush=True)
        try:
            subprocess.run([sys.executable, "-u", "-B", str(ROOT / script)], cwd=ROOT, check=True)
            if not (ROOT / output).is_file():
                raise RuntimeError("Expected phase output missing: " + output)
        except BaseException:
            save(status_path, dict(state="failed", phase=phase, error=traceback.format_exc(),
                                   updated_utc=now()))
            raise
    audit = load(ROOT / "results/final_audit.json")
    if not audit["passed"]:
        raise RuntimeError("Final audit did not pass")
    save(status_path, dict(state="complete", updates=8192, images=930, circles=8370,
                           completed_utc=now()))
    print("EVALUATION_COMPLETE", flush=True)


if __name__ == "__main__":
    main()

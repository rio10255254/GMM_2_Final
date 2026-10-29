"""Launch one complete scratch run of native-grid fixed-PSF consistency."""
from __future__ import annotations

import sys
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import train as trainer
from utils import load, now, save, sha
from verify_package import verify_source_lock
PROJECT_ROOT = Path(__file__).resolve().parents[3]


def main() -> None:
    preflight = load(ROOT / "results/preflight.json")
    verify_source_lock()
    if not preflight["passed"] or preflight["unchanged_R146_data_manifest_sha256"] != sha(ROOT / "data/manifest.json"):
        raise RuntimeError("Data preflight has not passed for this exact manifest")
    if not (ROOT / "data/generation_complete.json").is_file():
        raise RuntimeError("Generated data incomplete")
    trainer.MODEL_NAME_BASE = trainer.CFG.MODEL_NAME
    if trainer.MODEL_NAME_BASE != "R147-FullResPSFConsistency":
        raise RuntimeError("Unexpected model artifact identity")
    marker = ROOT / "runs/launcher_logs/active_formal_run.json"
    status = dict(state="training", model=trainer.MODEL_NAME_BASE, run="formal_8192",
                  updates_expected=8192, data_manifest_sha256=preflight["unchanged_R146_data_manifest_sha256"],
                  bank_sha256=preflight["fixed_bank_sha256"],
                  psf_mode=preflight["psf_mode"], started_utc=now())
    save(marker, status)
    previous_args = sys.argv
    try:
        sys.argv = [str(ROOT / "train.py"), "--run-name", "formal_8192", "--init", "scratch"]
        trainer.main()
        complete = load(ROOT / "runs/formal_8192/training_complete.json")
        assert complete["updates"] == 8192
        checkpoint = complete["checkpoint"]
        assert checkpoint["step"] == 8192 and sha(str(PROJECT_ROOT / checkpoint["path"])) == checkpoint["sha256"]
        save(marker, dict(status, state="training_complete", checkpoint=checkpoint, completed_utc=now()))
    except BaseException:
        save(marker, dict(status, state="failed", error=traceback.format_exc(), failed_utc=now()))
        raise
    finally:
        sys.argv = previous_args


if __name__ == "__main__":
    main()

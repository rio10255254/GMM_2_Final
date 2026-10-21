from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


R81_ROOT = Path(__file__).resolve().parents[1]
EVALUATE = Path(__file__).resolve().parent / "evaluate_model.py"
DEFAULT_ORDER = (
    "srcnn", "vdsr", "dncnn", "unet", "edsr", "rdn",
    "rcan", "swinir", "nafnet", "restormer", "pft", "ucan",
)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--models", nargs="+", default=list(DEFAULT_ORDER))
    arguments = parser.parse_args()
    log_root = R81_ROOT / "results" / "logs"
    log_root.mkdir(parents=True, exist_ok=True)
    for key in arguments.models:
        output = R81_ROOT / "results" / "evaluation" / key
        if (output / "evaluation_manifest.json").exists():
            print(f"skip completed evaluation: {key}", flush=True)
            continue
        checkpoint = R81_ROOT / "results" / "training" / key / f"best_{key}.pth.tar"
        if not checkpoint.exists():
            raise FileNotFoundError(checkpoint)
        print(f"start evaluation: {key}", flush=True)
        with (log_root / f"evaluate_{key}.out.log").open("a", encoding="utf-8") as out, (
            log_root / f"evaluate_{key}.err.log"
        ).open("a", encoding="utf-8") as err:
            completed = subprocess.run(
                [
                    sys.executable,
                    str(EVALUATE),
                    "--model",
                    key,
                    "--checkpoint",
                    str(checkpoint),
                    "--output",
                    str(output),
                ],
                cwd=R81_ROOT,
                stdout=out,
                stderr=err,
                check=False,
            )
        if completed.returncode != 0:
            raise SystemExit(f"evaluation failed for {key}: {completed.returncode}")
        print(f"completed evaluation: {key}", flush=True)


if __name__ == "__main__":
    main()

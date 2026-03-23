import argparse
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
GENERIC_AUDIT = PROJECT_ROOT / "Model" / "process_probe_audit_base.py"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidate", required=True)
    parser.add_argument("--checkpoint", required=True)
    parser.add_argument("--geom-method", default="")
    parser.add_argument("--expect-dy", type=float, default=0.8)
    parser.add_argument("--output-json", required=True)
    parser.add_argument("--output-md", required=True)
    parser.add_argument("--seed", type=int, default=1261202)
    parser.add_argument("--model-base", type=int, default=48)
    args = parser.parse_args()

    cmd = [
        sys.executable,
        "-u",
        str(GENERIC_AUDIT),
        "--candidate", str(args.candidate),
        "--checkpoint", str(args.checkpoint),
        "--geom-method", str(args.geom_method or ""),
        "--expect-dy", str(float(args.expect_dy)),
        "--output-json", str(args.output_json),
        "--output-md", str(args.output_md),
        "--seed", str(int(args.seed)),
        "--model-base", str(int(args.model_base)),
    ]
    raise SystemExit(subprocess.call(cmd, cwd=str(PROJECT_ROOT)))


if __name__ == "__main__":
    main()

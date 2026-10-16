"""Sequential R119 probe supervisor; one process at a time, no hidden resume."""
from __future__ import annotations
import argparse, json, subprocess, sys, time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PYTHON = Path(r"C:/Users/Rio/anaconda3/python.exe")


def run_matrix(output: Path, seeds: list[int], candidates: list[str]):
    output.mkdir(parents=True, exist_ok=True); rows = []
    for candidate in candidates:
        for seed in seeds:
            run_id = f"probe_{candidate}_s{seed}"
            command = [str(PYTHON if PYTHON.is_file() else sys.executable), str(ROOT / "training/train_r119.py"), "--mode", "probe", "--candidate", candidate, "--run-id", run_id, "--model-seed", str(seed), "--data-seed", "1196001", "--sampler-seed", "1197001", "--epochs", "12", "--limit", "512", "--batch", "8", "--workers", "2"]
            started = time.time(); result = subprocess.run(command, cwd=ROOT, text=True); row = {"candidate": candidate, "model_seed": seed, "run_id": run_id, "returncode": result.returncode, "elapsed_seconds": time.time() - started, "run_path": str(ROOT / "runs" / run_id)}; rows.append(row); (output / f"{run_id}.json").write_text(json.dumps(row, indent=2), encoding="utf-8")
            if result.returncode != 0: raise RuntimeError(f"probe failed: {run_id}")
    (output / "matrix.json").write_text(json.dumps({"status": "complete", "rows": rows}, indent=2), encoding="utf-8"); return rows


def main():
    parser = argparse.ArgumentParser(); parser.add_argument("--output", type=Path, default=ROOT / "results/probe_matrix"); parser.add_argument("--candidates", nargs="+", default=["A", "B", "D"]); parser.add_argument("--seeds", nargs="+", type=int, default=[1185001, 1185002]); parser.add_argument("--check-only", action="store_true"); args = parser.parse_args()
    if args.check_only: print(json.dumps({"status": "ready", "candidates": args.candidates, "seeds": args.seeds})); return 0
    print(json.dumps(run_matrix(args.output, args.seeds, args.candidates), indent=2)); return 0


if __name__ == "__main__": raise SystemExit(main())

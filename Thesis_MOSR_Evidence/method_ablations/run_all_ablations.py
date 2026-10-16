"""Sequential ablation runner — fires A -> B1 -> B2 -> B3 back to back.

Usage:
    python Thesis_MOSR_Evidence/method_ablations/run_all_ablations.py \
        --num-epoch 50 --device cuda:0

Runs four subprocesses sequentially. If any one fails (non-zero exit),
the runner stops and reports which ablation failed.

Each ablation writes to its own Traing_Progress dir; logs to stdout
plus the trainer's own logging files.

Estimated total wall time: 4 x ~12h ~ 48h GPU at 50 epoch.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import time
from pathlib import Path


_REPO_ROOT = Path(__file__).resolve().parents[2]
ABLATION_ROOT = _REPO_ROOT / "Thesis_MOSR_Evidence" / "method_ablations"


ABLATIONS = [
    ("A_no_seq",   ABLATION_ROOT / "single_vs_multi_frame" / "scripts" / "launch_ablation_no_seq.py"),
    ("B1_no_eq",   ABLATION_ROOT / "physics_residual_ablation" / "scripts" / "launch_ablation_no_eq.py"),
    ("B2_no_edge", ABLATION_ROOT / "physics_residual_ablation" / "scripts" / "launch_ablation_no_edge.py"),
    ("B3_no_freq", ABLATION_ROOT / "physics_residual_ablation" / "scripts" / "launch_ablation_no_freq.py"),
]


def main():
    parser = argparse.ArgumentParser(description="Sequential ablation runner")
    parser.add_argument("--num-epoch", type=int, default=50,
                        help="Per-ablation epoch count (50 = adequate, 100 = full COMBO parity)")
    parser.add_argument("--device", type=str, default="cuda:0")
    parser.add_argument("--start-from", type=str, default=None,
                        choices=[None, "A_no_seq", "B1_no_eq", "B2_no_edge", "B3_no_freq"],
                        help="Skip preceding ablations; resume from this one")
    parser.add_argument("--only", type=str, default=None,
                        choices=[None, "A_no_seq", "B1_no_eq", "B2_no_edge", "B3_no_freq"],
                        help="Run only this one ablation and stop")
    args = parser.parse_args()

    queue = ABLATIONS
    if args.only is not None:
        queue = [a for a in ABLATIONS if a[0] == args.only]
    elif args.start_from is not None:
        idx = [i for i, a in enumerate(ABLATIONS) if a[0] == args.start_from]
        if idx:
            queue = ABLATIONS[idx[0]:]

    total_start = time.time()
    print(f"\n{'='*70}")
    print(f"Sequential ablation runner")
    print(f"  queue: {[a[0] for a in queue]}")
    print(f"  per-ablation epoch: {args.num_epoch}")
    print(f"  device: {args.device}")
    print(f"{'='*70}\n")

    for i, (tag, launcher) in enumerate(queue, start=1):
        print(f"\n{'='*70}")
        print(f"[{i}/{len(queue)}] Starting {tag}")
        print(f"  launcher: {launcher}")
        print(f"  start time: {time.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"{'='*70}\n", flush=True)

        if not launcher.exists():
            print(f"[ERROR] launcher not found: {launcher}")
            sys.exit(2)

        t0 = time.time()
        result = subprocess.run(
            [sys.executable, str(launcher),
             "--num-epoch", str(args.num_epoch),
             "--device", args.device],
            cwd=str(_REPO_ROOT),
        )
        elapsed = time.time() - t0

        if result.returncode != 0:
            print(f"\n[FAIL] {tag} exited with code {result.returncode} after {elapsed/60:.1f} min")
            print(f"  Remaining ablations not started: "
                  f"{[a[0] for a in queue[i:]]}")
            sys.exit(result.returncode)

        print(f"\n[OK] {tag} finished in {elapsed/60:.1f} min")

    total_elapsed = time.time() - total_start
    print(f"\n{'='*70}")
    print(f"All ablations completed in {total_elapsed/3600:.2f} h")
    print(f"{'='*70}\n")


if __name__ == "__main__":
    main()

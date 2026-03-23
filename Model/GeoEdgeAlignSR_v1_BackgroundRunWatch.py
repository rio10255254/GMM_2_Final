#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Foreground watcher for one background process + one log file.

It streams appended log text and prints a clear completion banner when
the watched PID exits.
"""

import argparse
import subprocess
import sys
import time
from pathlib import Path


def _pid_alive(pid: int) -> bool:
    proc = subprocess.run(
        ["tasklist", "/FI", f"PID eq {pid}", "/FO", "CSV", "/NH"],
        capture_output=True,
        text=True,
        check=False,
    )
    out = (proc.stdout or "").strip()
    return bool(out) and "No tasks are running" not in out and f'"{pid}"' in out


def _tail_last_lines(path: Path, num_lines: int) -> str:
    if not path.exists():
        return ""
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except Exception:
        return ""
    if num_lines <= 0:
        return ""
    return "\n".join(lines[-num_lines:]) + ("\n" if lines else "")


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--pid", type=int, required=True)
    p.add_argument("--log", type=str, required=True)
    p.add_argument("--label", type=str, default="Background Run")
    p.add_argument("--interval-sec", type=float, default=1.0)
    p.add_argument("--tail-lines", type=int, default=60)
    args = p.parse_args()

    log_path = Path(args.log).resolve()
    current_pos = 0
    missing_announced = False

    sys.stdout.write(
        "\n"
        + "=" * 80
        + "\n"
        + f"[WATCH] label={args.label}\n"
        + f"[WATCH] pid={int(args.pid)}\n"
        + f"[WATCH] log={log_path}\n"
        + "=" * 80
        + "\n"
    )
    sys.stdout.flush()

    if log_path.exists():
        tail_text = _tail_last_lines(log_path, int(args.tail_lines))
        if tail_text:
            sys.stdout.write(tail_text)
        try:
            current_pos = log_path.stat().st_size
        except OSError:
            current_pos = 0
        sys.stdout.flush()

    try:
        while True:
            if log_path.exists():
                try:
                    stat = log_path.stat()
                    if stat.st_size < current_pos:
                        current_pos = 0
                    with open(log_path, "r", encoding="utf-8", errors="replace") as f:
                        f.seek(current_pos)
                        chunk = f.read()
                        current_pos = f.tell()
                    if chunk:
                        sys.stdout.write(chunk)
                        sys.stdout.flush()
                except OSError:
                    pass
            else:
                if not missing_announced:
                    sys.stdout.write(f"[WATCH] waiting for log file: {log_path}\n")
                    sys.stdout.flush()
                    missing_announced = True

            alive = _pid_alive(int(args.pid))
            if not alive:
                # Flush any last bytes written just before process exit.
                if log_path.exists():
                    try:
                        stat = log_path.stat()
                        if stat.st_size > current_pos:
                            with open(log_path, "r", encoding="utf-8", errors="replace") as f:
                                f.seek(current_pos)
                                chunk = f.read()
                                current_pos = f.tell()
                            if chunk:
                                sys.stdout.write(chunk)
                                sys.stdout.flush()
                    except OSError:
                        pass
                sys.stdout.write(
                    "\n"
                    + "=" * 80
                    + "\n"
                    + f"[WATCH][COMPLETED] label={args.label} pid={int(args.pid)} finished at "
                    + time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
                    + "\n"
                    + "=" * 80
                    + "\n"
                )
                sys.stdout.flush()
                return 0

            time.sleep(max(0.2, float(args.interval_sec)))
    except KeyboardInterrupt:
        return 0
    except OSError:
        return 0


if __name__ == "__main__":
    sys.exit(main())

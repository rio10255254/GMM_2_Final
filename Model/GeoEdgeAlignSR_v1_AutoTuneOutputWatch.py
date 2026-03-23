#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Foreground watcher for the active autotune raw output log.

It follows the `active_out_log` path in the root `000_AUTOTUNE_STATUS.json`,
so it keeps working across chained rounds.
"""

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any, Dict, Optional


def _project_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _load_status(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}

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
    p.add_argument("--interval-sec", type=float, default=1.0)
    p.add_argument("--tail-lines", type=int, default=60)
    args = p.parse_args()

    status_path = _project_root() / "000_AUTOTUNE_STATUS.json"
    current_log: Optional[Path] = None
    current_pos = 0
    announced_missing = False

    try:
        while True:
            status = _load_status(status_path)
            active_out_log = str(status.get("active_out_log", "")).strip()
            next_log = Path(active_out_log) if active_out_log else None

            if next_log != current_log:
                current_log = next_log
                current_pos = 0
                announced_missing = False
                if current_log:
                    header = (
                        "\n"
                        + "=" * 80
                        + "\n"
                        + f"[WATCH] switched to: {current_log}\n"
                        + "=" * 80
                        + "\n"
                    )
                    sys.stdout.write(header)
                    if current_log.exists():
                        tail_text = _tail_last_lines(current_log, int(args.tail_lines))
                        if tail_text:
                            sys.stdout.write(tail_text)
                        try:
                            current_pos = current_log.stat().st_size
                        except OSError:
                            current_pos = 0
                    sys.stdout.flush()

            if current_log and current_log.exists():
                try:
                    stat = current_log.stat()
                    if stat.st_size < current_pos:
                        current_pos = 0
                    with open(current_log, "r", encoding="utf-8", errors="replace") as f:
                        f.seek(current_pos)
                        chunk = f.read()
                        current_pos = f.tell()
                    if chunk:
                        sys.stdout.write(chunk)
                        sys.stdout.flush()
                except OSError:
                    pass
            else:
                if not announced_missing:
                    msg = "[WATCH] waiting for active_out_log in 000_AUTOTUNE_STATUS.json\n"
                    sys.stdout.write(msg)
                    sys.stdout.flush()
                    announced_missing = True

            time.sleep(max(0.2, float(args.interval_sec)))
    except KeyboardInterrupt:
        return 0
    except OSError:
        return 0


if __name__ == "__main__":
    sys.exit(main())

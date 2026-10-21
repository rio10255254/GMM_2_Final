#!/usr/bin/env python
import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict


def _project_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _load_status(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _clear_screen() -> None:
    os.system("cls")


def _fmt(v: Any, default: str = "") -> str:
    if v is None:
        return default
    return str(v)


def _render(status: Dict[str, Any], status_path: Path, interval_sec: int) -> str:
    lines = [
        "=== Round6 Pipeline Watch ===",
        "",
        f"status_file      : {status_path}",
        f"updated_at       : {_fmt(status.get('updated_at'), '')}",
        f"state            : {_fmt(status.get('state'), 'missing')}",
        f"step             : {_fmt(status.get('step'), '-')}",
        f"message          : {_fmt(status.get('message'), '-')}",
        f"log_path         : {_fmt(status.get('log_path'), '-')}",
        "",
        f"refresh_interval : {interval_sec}s",
        "stop            : Ctrl+C",
    ]
    return "\n".join(lines) + "\n"


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--interval-sec", type=int, default=5)
    p.add_argument("--no-clear", action="store_true")
    args = p.parse_args()

    status_path = _project_root() / "000_ROUND6_PIPELINE_STATUS.json"
    try:
        while True:
            status = _load_status(status_path)
            if not args.no_clear:
                _clear_screen()
            try:
                sys.stdout.write(_render(status, status_path, int(args.interval_sec)))
                sys.stdout.flush()
            except OSError:
                return 0
            time.sleep(max(1, int(args.interval_sec)))
    except KeyboardInterrupt:
        return 0


if __name__ == "__main__":
    sys.exit(main())

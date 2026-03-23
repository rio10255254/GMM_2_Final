#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Foreground terminal watcher for the root-level autotune status files.

Usage:
    python Model/GeoEdgeAlignSR_v1_AutoTuneStatusWatch.py
"""

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
    state = _fmt(status.get("state"), "missing")
    updated = _fmt(status.get("updated_at"), "")
    notify = bool(status.get("user_should_notify_codex", False))
    next_action = _fmt(status.get("next_action"), "")
    active_pid = _fmt(status.get("active_pid"), "-")
    active_log = _fmt(status.get("active_out_log"), "-")
    status_line = _fmt(status.get("status_line"), "-")
    plan_total = status.get("plan_total")
    plan_remaining = status.get("plan_remaining")
    best_score = status.get("best_score")
    improved = status.get("improved")

    lines = [
        "=== AutoTune Foreground Watch ===",
        "",
        f"status_file      : {status_path}",
        f"updated_at       : {updated}",
        f"state            : {state}",
        f"notify_codex     : {'YES' if notify else 'NO'}",
        f"next_action      : {next_action}",
        f"active_pid       : {active_pid}",
        f"active_out_log   : {active_log}",
    ]
    if plan_total is not None:
        lines.append(f"plan_progress    : total={plan_total} remaining={plan_remaining}")
    if best_score is not None:
        lines.append(f"best_score       : {best_score}")
    if improved is not None:
        lines.append(f"improved         : {improved}")

    lines.extend(
        [
            "",
            "latest_status",
            "-------------",
            status_line,
            "",
            f"refresh_interval : {interval_sec}s",
            "stop            : Ctrl+C",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--interval-sec", type=int, default=5)
    p.add_argument("--no-clear", action="store_true")
    args = p.parse_args()

    status_path = _project_root() / "000_AUTOTUNE_STATUS.json"
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

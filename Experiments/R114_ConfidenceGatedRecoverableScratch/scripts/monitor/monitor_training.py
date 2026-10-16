"""Compact, robust R114 foreground monitor with dynamic ETA and GPU telemetry."""
from __future__ import annotations

import argparse
import csv
import json
import math
import os
import statistics
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any


def read_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except (json.JSONDecodeError, OSError):
        return default


def atomic_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(temporary, path)


def parse_number(value: Any) -> float | None:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None


def read_history(run_dir: Path) -> tuple[list[dict[str, Any]], Path | None]:
    csv_candidates = (run_dir / "training_log.csv", run_dir / "metrics.csv")
    for path in csv_candidates:
        if path.exists():
            try:
                with path.open("r", newline="", encoding="utf-8-sig") as handle:
                    return list(csv.DictReader(handle)), path
            except (OSError, csv.Error):
                pass
    for path in (run_dir / "training_history.json", run_dir / "history.json"):
        payload = read_json(path)
        if isinstance(payload, list):
            return payload, path
        if isinstance(payload, dict) and isinstance(payload.get("epochs"), list):
            return payload["epochs"], path
    return [], None


def epoch_number(row: dict[str, Any]) -> int:
    for key in ("epoch", "epoch_index", "completed_epoch"):
        value = parse_number(row.get(key))
        if value is not None:
            return int(value)
    return 0


def robust_epoch_seconds(rows: list[dict[str, Any]]) -> tuple[float | None, float | None, float | None, int]:
    valid = []
    for row in rows:
        value = parse_number(row.get("duration_seconds"))
        if value is not None and value > 0:
            valid.append((str(row.get("stage", "")), value))
    if not valid:
        return None, None, None, 0
    latest_stage = valid[-1][0]
    same_stage = [value for stage, value in valid if stage == latest_stage][-12:]
    sample = same_stage if len(same_stage) >= 3 else [value for _, value in valid][-12:]
    median = statistics.median(sample)
    deviations = [abs(value - median) for value in sample]
    mad = statistics.median(deviations)
    trimmed = [value for value in sample if mad <= 1e-9 or abs(value - median) <= 3.5 * 1.4826 * mad]
    if not trimmed:
        trimmed = sample
    estimate = trimmed[0]
    alpha = .35
    for value in trimmed[1:]:
        estimate = alpha * value + (1.0 - alpha) * estimate
    ordered = sorted(trimmed)
    low = ordered[max(0, int(.2 * (len(ordered) - 1)))]
    high = ordered[min(len(ordered) - 1, int(math.ceil(.8 * (len(ordered) - 1))))]
    return estimate, low, high, len(trimmed)


def format_duration(seconds: float | None) -> str:
    if seconds is None or not math.isfinite(seconds):
        return "--:--:--"
    seconds = max(0, int(round(seconds)))
    hours, remainder = divmod(seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"


def gpu_status() -> list[dict[str, Any]]:
    command = [
        "nvidia-smi",
        "--query-gpu=index,name,memory.total,memory.used,memory.free,utilization.gpu,temperature.gpu",
        "--format=csv,noheader,nounits",
    ]
    try:
        completed = subprocess.run(command, check=True, capture_output=True, text=True, timeout=4)
    except (OSError, subprocess.SubprocessError):
        return []
    rows = []
    for line in completed.stdout.splitlines():
        fields = [item.strip() for item in line.split(",")]
        if len(fields) != 7:
            continue
        rows.append({
            "index": int(fields[0]),
            "name": fields[1],
            "total_mib": float(fields[2]),
            "used_mib": float(fields[3]),
            "free_mib": float(fields[4]),
            "utilization_percent": float(fields[5]),
            "temperature_c": float(fields[6]),
        })
    return rows


def process_alive(pid: Any) -> bool | None:
    value = parse_number(pid)
    if value is None or int(value) <= 0:
        return None
    try:
        os.kill(int(value), 0)
        return True
    except PermissionError:
        return True
    except OSError:
        return False


def select_metrics(row: dict[str, Any]) -> list[tuple[str, float]]:
    priority = (
        "train_total", "loss", "validation_loss", "boundary_auc", "boundary_dice",
        "need_separation", "identity_mae_gray", "tile_mean_gray",
    )
    result = []
    for key in priority:
        value = parse_number(row.get(key))
        if value is not None:
            result.append((key, value))
    if len(result) < 4:
        for key, raw_value in row.items():
            if key in {name for name, _ in result} or key in {"epoch", "duration_seconds"}:
                continue
            value = parse_number(raw_value)
            if value is not None and any(token in key.lower() for token in ("loss", "auc", "dice", "identity", "tile")):
                result.append((key, value))
            if len(result) >= 4:
                break
    return result[:4]


def snapshot(root: Path) -> dict[str, Any]:
    active = read_json(root / "runs" / "active_run.json") or {}
    launcher = read_json(root / "logs" / "launcher_state.json") or {}
    run_id = active.get("run_id") or launcher.get("run_id")
    if not run_id:
        return {
            "status": "idle",
            "timestamp": datetime.now().astimezone().isoformat(),
            "gpu": gpu_status(),
            "message": "No active or latest formal run is registered.",
        }
    run_dir = Path(active.get("run_dir") or root / "runs" / str(run_id))
    rows, history_path = read_history(run_dir)
    rows = sorted(rows, key=epoch_number)
    last = rows[-1] if rows else {}
    current_epoch = epoch_number(last) or int(active.get("latest_epoch", 0) or 0)
    total_epochs = int(active.get("total_epochs") or launcher.get("epochs") or 0)
    estimate, low, high, samples = robust_epoch_seconds(rows)
    remaining_epochs = max(0, total_epochs - current_epoch) if total_epochs else 0
    trainer_pid = active.get("trainer_pid") or launcher.get("trainer_pid") or launcher.get("process_id")
    failure = read_json(run_dir / "failure.json")
    stderr_path = Path(launcher["stderr"]) if launcher.get("stderr") else root / "logs" / "formal_stderr.log"
    stderr_tail = ""
    if stderr_path.exists():
        try:
            stderr_tail = "\n".join(stderr_path.read_text(encoding="utf-8", errors="replace").splitlines()[-5:])
        except OSError:
            pass
    nonfinite_fields = [key for key, value in last.items() if parse_number(value) is None and str(value).lower() in {"nan", "inf", "-inf"}]
    return {
        "status": str(active.get("status") or launcher.get("status") or "unknown"),
        "timestamp": datetime.now().astimezone().isoformat(),
        "run_id": run_id,
        "run_dir": str(run_dir),
        "stage": last.get("stage") or active.get("stage"),
        "current_epoch": current_epoch,
        "total_epochs": total_epochs,
        "remaining_epochs": remaining_epochs,
        "last_epoch_seconds": parse_number(last.get("duration_seconds")),
        "dynamic_epoch_seconds": estimate,
        "eta_seconds": estimate * remaining_epochs if estimate is not None else None,
        "eta_low_seconds": low * remaining_epochs if low is not None else None,
        "eta_high_seconds": high * remaining_epochs if high is not None else None,
        "eta_sample_epochs": samples,
        "trainer_pid": trainer_pid,
        "trainer_alive": process_alive(trainer_pid),
        "history_path": str(history_path) if history_path else None,
        "latest_metrics": {name: value for name, value in select_metrics(last)},
        "nonfinite_latest_fields": nonfinite_fields,
        "failure": failure,
        "stderr_tail": stderr_tail,
        "gpu": gpu_status(),
    }


def render(payload: dict[str, Any]) -> str:
    lines = ["R114 Training Monitor", datetime.now().strftime("%Y-%m-%d %H:%M:%S")]
    if payload["status"] == "idle":
        lines.append("Status  idle - no registered run")
    else:
        current, total = int(payload["current_epoch"]), int(payload["total_epochs"])
        ratio = current / total if total else 0.0
        width = 28
        filled = min(width, max(0, int(round(ratio * width))))
        progress = "#" * filled + "." * (width - filled)
        lines.extend([
            f"Run     {payload['run_id']}",
            f"Status  {payload['status']}  Stage {payload.get('stage') or '-'}  PID {payload.get('trainer_pid') or '-'} "
            f"({'alive' if payload.get('trainer_alive') else 'not confirmed'})",
            f"Epoch   [{progress}] {current}/{total or '?'} ({ratio * 100:5.1f}%)",
            f"Time    last {format_duration(payload.get('last_epoch_seconds'))}  smoothed {format_duration(payload.get('dynamic_epoch_seconds'))}",
            f"ETA     {format_duration(payload.get('eta_seconds'))}  range {format_duration(payload.get('eta_low_seconds'))} - {format_duration(payload.get('eta_high_seconds'))} "
            f"({payload.get('eta_sample_epochs', 0)} epochs)",
        ])
        metrics = payload.get("latest_metrics", {})
        if metrics:
            lines.append("Metrics " + "  ".join(f"{name}={value:.6g}" for name, value in metrics.items()))
        if payload.get("nonfinite_latest_fields"):
            lines.append("ALERT   non-finite fields: " + ", ".join(payload["nonfinite_latest_fields"]))
        if payload.get("failure"):
            lines.append("ALERT   failure.json is present")
        if payload.get("stderr_tail"):
            lines.append("Stderr  " + payload["stderr_tail"].replace("\n", " | "))
    if payload.get("gpu"):
        for gpu in payload["gpu"]:
            lines.append(
                f"GPU {gpu['index']}   {gpu['used_mib'] / 1024:.1f}/{gpu['total_mib'] / 1024:.1f} GiB  "
                f"free {gpu['free_mib'] / 1024:.1f} GiB  util {gpu['utilization_percent']:.0f}%  {gpu['temperature_c']:.0f} C"
            )
    else:
        lines.append("GPU     telemetry unavailable")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="R114 foreground monitor")
    parser.add_argument("--root", required=True)
    parser.add_argument("--refresh", type=float, default=5.0)
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args()
    root = Path(args.root).resolve()
    while True:
        payload = snapshot(root)
        atomic_json(root / "logs" / "monitor_snapshot.json", payload)
        if not args.once and sys.stdout.isatty():
            os.system("cls" if os.name == "nt" else "clear")
        print(render(payload), flush=True)
        if args.once:
            return 0
        time.sleep(max(1.0, args.refresh))


if __name__ == "__main__":
    raise SystemExit(main())

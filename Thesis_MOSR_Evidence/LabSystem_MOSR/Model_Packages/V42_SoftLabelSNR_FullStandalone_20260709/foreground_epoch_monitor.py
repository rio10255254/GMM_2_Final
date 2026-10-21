from __future__ import annotations

import argparse
import csv
import json
import os
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class BatchProgress:
    epoch: int
    batch: int


def completed_epoch_from_weights(run_dir: Path) -> int:
    best = 0
    for path in Path(run_dir).glob("epoch_*.pth.tar"):
        stem = path.name
        try:
            epoch = int(stem.split("_", 1)[1].split(".", 1)[0])
        except (IndexError, ValueError):
            continue
        best = max(best, epoch)
    return best


def latest_batch_progress(run_dir: Path) -> BatchProgress | None:
    csv_paths = sorted(Path(run_dir).glob("*_batch_log_v5.csv"), key=lambda p: p.stat().st_mtime if p.exists() else 0)
    if not csv_paths:
        return None
    latest = csv_paths[-1]
    last_row: dict[str, str] | None = None
    with latest.open("r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row:
                last_row = row
    if not last_row:
        return None
    try:
        return BatchProgress(epoch=int(float(last_row["epoch"])), batch=int(float(last_row["batch"])))
    except (KeyError, TypeError, ValueError):
        return None


def expected_train_batches(train_count: int, batch_size: int, sample_mult: float = 1.25) -> int:
    if train_count <= 0 or batch_size <= 0:
        return 0
    sampled = max(1, int(round(int(train_count) * float(sample_mult))))
    return max(1, sampled // int(batch_size))


def read_json(path: Path) -> dict:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8-sig"))


def find_latest_training_run(training_results_dir: Path, run_prefix: str) -> Path | None:
    candidates = [
        p for p in Path(training_results_dir).iterdir()
        if p.is_dir() and p.name.startswith(f"training_progress_{run_prefix}")
    ]
    if not candidates:
        return None
    return max(candidates, key=lambda p: p.stat().st_mtime)


def count_train_split(package_root: Path) -> int:
    split_root = package_root / "training_data" / "splits"
    for candidate in (
        split_root / "grouped_seed1337_val120" / "train_idx.npy",
        split_root / "grouped_seed1337_val100" / "train_idx.npy",
    ):
        if candidate.exists():
            try:
                import numpy as np
                return int(len(np.load(candidate)))
            except Exception:
                pass
    src_root = package_root / "training_data" / "src"
    return sum(1 for p in src_root.rglob("*") if p.is_file() and p.suffix.lower() in {".bmp", ".png", ".tif", ".tiff"})


def process_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    if os.name == "nt":
        try:
            import ctypes
            handle = ctypes.windll.kernel32.OpenProcess(0x1000, False, int(pid))
            if handle:
                ctypes.windll.kernel32.CloseHandle(handle)
                return True
            return False
        except Exception:
            return False
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def gpu_summary() -> str:
    try:
        out = subprocess.check_output(
            [
                "nvidia-smi",
                "--query-gpu=utilization.gpu,memory.used,memory.total",
                "--format=csv,noheader,nounits",
            ],
            text=True,
            stderr=subprocess.DEVNULL,
            timeout=3,
        ).strip()
        if not out:
            return "GPU: unavailable"
        util, used, total = [part.strip() for part in out.splitlines()[0].split(",")[:3]]
        return f"GPU: {util}% | VRAM: {used}/{total} MiB"
    except Exception:
        return "GPU: unavailable"


def make_bar(value: float, width: int = 36) -> str:
    value = max(0.0, min(1.0, float(value)))
    filled = int(round(value * width))
    return "[" + "#" * filled + "-" * (width - filled) + "]"


def render_status(
    *,
    run_name: str,
    run_dir: Path | None,
    train_pid: int,
    total_epochs: int,
    expected_batches: int,
) -> str:
    if run_dir is None:
        return "\n".join([
            "V42 foreground epoch monitor",
            f"Run: {run_name}",
            "Status: waiting for training folder...",
            gpu_summary(),
        ])

    completed = completed_epoch_from_weights(run_dir)
    batch = latest_batch_progress(run_dir)
    current_epoch = completed + 1 if completed < total_epochs else completed
    current_batch = 0
    if batch is not None and batch.epoch >= current_epoch:
        current_epoch = batch.epoch
        current_batch = batch.batch

    epoch_fraction = min(1.0, completed / max(1, total_epochs))
    if expected_batches > 0 and current_epoch <= total_epochs:
        epoch_fraction = min(
            1.0,
            (max(0, current_epoch - 1) + min(current_batch, expected_batches) / expected_batches) / max(1, total_epochs),
        )

    epoch_bar = make_bar(epoch_fraction)
    batch_bar = make_bar((current_batch / expected_batches) if expected_batches > 0 else 0.0)
    alive_text = "running" if process_alive(train_pid) else "not running"
    demo_log = run_dir / "epoch_demo_inference" / "epoch_demo_log.csv"
    demo_rows = 0
    if demo_log.exists():
        with demo_log.open("r", encoding="utf-8", newline="") as f:
            demo_rows = max(0, sum(1 for _ in f) - 1)

    lines = [
        "V42 foreground epoch monitor",
        f"Run: {run_name}",
        f"Training PID: {train_pid} ({alive_text})",
        f"Epoch: {completed}/{total_epochs} {epoch_bar} {epoch_fraction * 100:5.1f}%",
        f"Current epoch batch: {current_batch}/{expected_batches} {batch_bar}",
        f"100MG demo inference rows: {demo_rows}",
        gpu_summary(),
        f"Folder: {run_dir}",
        "",
        "Ctrl+C closes this monitor only; training keeps running.",
    ]
    return "\n".join(lines)


def build_arg_parser() -> argparse.ArgumentParser:
    root = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser(description="Foreground progress monitor for V42 full training.")
    parser.add_argument("--package-root", type=Path, default=root)
    parser.add_argument("--manifest", type=Path, default=root / "CURRENT_FULL_TRAINING_RUN.json")
    parser.add_argument("--poll-sec", type=float, default=5.0)
    parser.add_argument("--batch-size", type=int, default=8)
    parser.add_argument("--sample-mult", type=float, default=1.25)
    return parser


def main() -> int:
    args = build_arg_parser().parse_args()
    package_root = args.package_root.resolve()
    manifest_path = args.manifest.resolve()
    train_count = count_train_split(package_root)
    expected_batches = expected_train_batches(train_count, int(args.batch_size), float(args.sample_mult))
    while True:
        manifest = read_json(manifest_path)
        run_name = str(manifest.get("run_name", "unknown"))
        run_prefix = str(manifest.get("run_prefix", ""))
        total_epochs = int(manifest.get("epochs", 0) or 0)
        train_pid = int(manifest.get("train_pid", 0) or 0)
        training_results_dir = package_root / "results" / "training_results"
        run_dir = find_latest_training_run(training_results_dir, run_prefix) if run_prefix else None

        os.system("cls" if os.name == "nt" else "clear")
        print(render_status(
            run_name=run_name,
            run_dir=run_dir,
            train_pid=train_pid,
            total_epochs=total_epochs,
            expected_batches=expected_batches,
        ), flush=True)
        time.sleep(max(1.0, float(args.poll_sec)))


if __name__ == "__main__":
    raise SystemExit(main())

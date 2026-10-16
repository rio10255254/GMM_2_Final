from __future__ import annotations

import argparse
import csv
import ctypes
import json
import os
import re
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path


IMAGE_EXTS = {".bmp", ".png", ".tif", ".tiff", ".jpg", ".jpeg"}
EPOCH_RE = re.compile(r"^epoch_(\d{3,})\.pth\.tar$")
REQUIRED_DEMO_LABELS = ("100MG_50x", "100MG_20x", "100MG_5x")


@dataclass(frozen=True)
class DemoSet:
    label: str
    input_dir: Path
    image_count: int


def epoch_from_checkpoint(path: Path) -> int | None:
    match = EPOCH_RE.match(Path(path).name)
    if match is None:
        return None
    return int(match.group(1))


def find_epoch_checkpoints(run_dir: Path, seen_epochs: set[int] | None = None) -> list[Path]:
    seen_epochs = seen_epochs or set()
    found: list[tuple[int, Path]] = []
    for path in Path(run_dir).glob("epoch_*.pth.tar"):
        epoch = epoch_from_checkpoint(path)
        if epoch is None or epoch in seen_epochs:
            continue
        found.append((epoch, path))
    return [p for _, p in sorted(found, key=lambda item: item[0])]


def collect_demo_sets(demo_root: Path) -> list[DemoSet]:
    sets: list[DemoSet] = []
    missing: list[str] = []
    for label in REQUIRED_DEMO_LABELS:
        input_dir = Path(demo_root) / label
        if not input_dir.is_dir():
            missing.append(label)
            continue
        count = sum(1 for p in input_dir.iterdir() if p.is_file() and p.suffix.lower() in IMAGE_EXTS)
        if count <= 0:
            missing.append(label)
            continue
        sets.append(DemoSet(label=label, input_dir=input_dir, image_count=count))
    if missing:
        raise FileNotFoundError(f"missing demo image set(s): {', '.join(missing)}")
    return sets


def is_file_stable(path: Path, wait_sec: float = 2.0) -> bool:
    if not path.exists():
        return False
    stat1 = path.stat()
    time.sleep(max(0.0, wait_sec))
    if not path.exists():
        return False
    stat2 = path.stat()
    return stat1.st_size == stat2.st_size and stat1.st_mtime_ns == stat2.st_mtime_ns


def find_latest_run(training_results_dir: Path, run_prefix: str) -> Path | None:
    candidates = [
        p
        for p in Path(training_results_dir).iterdir()
        if p.is_dir() and p.name.startswith(f"training_progress_{run_prefix}")
    ]
    if not candidates:
        return None
    return max(candidates, key=lambda p: p.stat().st_mtime)


def process_epoch(
    *,
    package_root: Path,
    run_dir: Path,
    checkpoint: Path,
    demo_sets: list[DemoSet],
    device: str,
    python_exe: str,
    csv_writer: csv.writer,
    csv_file,
) -> None:
    epoch = epoch_from_checkpoint(checkpoint)
    if epoch is None:
        return
    epoch_root = run_dir / "epoch_demo_inference" / f"epoch_{epoch:03d}"
    epoch_root.mkdir(parents=True, exist_ok=True)
    infer_script = package_root / "infer_v42.py"
    for demo in demo_sets:
        log_path = epoch_root / f"{demo.label}_infer.log"
        cmd = [
            python_exe,
            str(infer_script),
            "--weights",
            str(checkpoint),
            "--input-dir",
            str(demo.input_dir),
            "--recon-root",
            str(epoch_root),
            "--output-name",
            demo.label,
            "--device",
            device,
            "--psf-from-ckpt",
        ]
        start = time.time()
        with log_path.open("w", encoding="utf-8") as log:
            proc = subprocess.run(
                cmd,
                cwd=str(package_root),
                text=True,
                stdout=log,
                stderr=subprocess.STDOUT,
            )
        elapsed = time.time() - start
        csv_writer.writerow(
            [
                time.strftime("%Y-%m-%d %H:%M:%S"),
                epoch,
                demo.label,
                str(checkpoint),
                str(demo.input_dir),
                str(epoch_root),
                demo.image_count,
                proc.returncode,
                f"{elapsed:.3f}",
                str(log_path),
            ]
        )
        csv_file.flush()
        if proc.returncode != 0:
            raise RuntimeError(f"inference failed for epoch {epoch:03d} {demo.label}; see {log_path}")


def read_seen_epochs(log_csv: Path) -> set[int]:
    if not log_csv.exists():
        return set()
    seen: set[int] = set()
    with log_csv.open("r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row.get("returncode") == "0":
                try:
                    seen.add(int(row.get("epoch", "")))
                except ValueError:
                    pass
    return seen


def is_process_alive(pid: int | None) -> bool:
    if pid is None or pid <= 0:
        return True
    if os.name == "nt":
        process_query_limited_information = 0x1000
        handle = ctypes.windll.kernel32.OpenProcess(process_query_limited_information, False, int(pid))
        if handle:
            ctypes.windll.kernel32.CloseHandle(handle)
            return True
        return False
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run per-epoch 100MG demo inference for V42 full training.")
    root = Path(__file__).resolve().parent
    parser.add_argument("--package-root", type=Path, default=root)
    parser.add_argument("--training-results-dir", type=Path, default=root / "results" / "training_results")
    parser.add_argument("--run-prefix", required=True)
    parser.add_argument("--demo-root", type=Path, default=root / "demo_inputs")
    parser.add_argument("--device", default="cpu")
    parser.add_argument("--python-exe", default=sys.executable)
    parser.add_argument("--poll-sec", type=float, default=20.0)
    parser.add_argument("--stable-wait-sec", type=float, default=2.0)
    parser.add_argument("--training-pid", type=int, default=0)
    parser.add_argument("--idle-exit-sec", type=float, default=300.0)
    parser.add_argument("--once", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    package_root = args.package_root.resolve()
    demo_sets = collect_demo_sets(args.demo_root.resolve())
    monitor_root = args.training_results_dir.resolve() / "_epoch_demo_monitor"
    monitor_root.mkdir(parents=True, exist_ok=True)
    monitor_meta = {
        "package_root": str(package_root),
        "run_prefix": args.run_prefix,
        "demo_sets": [demo.__dict__ | {"input_dir": str(demo.input_dir)} for demo in demo_sets],
        "device": args.device,
        "started_at": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    (monitor_root / f"{args.run_prefix}_monitor_meta.json").write_text(
        json.dumps(monitor_meta, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    run_dir: Path | None = None
    idle_start: float | None = None
    while True:
        if run_dir is None:
            run_dir = find_latest_run(args.training_results_dir.resolve(), args.run_prefix)
            if run_dir is None:
                if args.once:
                    return 2
                time.sleep(max(1.0, args.poll_sec))
                continue

        log_csv = run_dir / "epoch_demo_inference" / "epoch_demo_log.csv"
        log_csv.parent.mkdir(parents=True, exist_ok=True)
        seen_epochs = read_seen_epochs(log_csv)
        checkpoints = find_epoch_checkpoints(run_dir, seen_epochs=seen_epochs)
        processed_any = False

        with log_csv.open("a", newline="", encoding="utf-8") as csv_file:
            writer = csv.writer(csv_file)
            if log_csv.stat().st_size == 0:
                writer.writerow(
                    [
                        "timestamp",
                        "epoch",
                        "demo_label",
                        "checkpoint",
                        "input_dir",
                        "output_root",
                        "image_count",
                        "returncode",
                        "elapsed_sec",
                        "log_path",
                    ]
                )
            for checkpoint in checkpoints:
                if not is_file_stable(checkpoint, wait_sec=float(args.stable_wait_sec)):
                    continue
                process_epoch(
                    package_root=package_root,
                    run_dir=run_dir,
                    checkpoint=checkpoint,
                    demo_sets=demo_sets,
                    device=str(args.device),
                    python_exe=str(args.python_exe),
                    csv_writer=writer,
                    csv_file=csv_file,
                )
                processed_any = True

        if args.once:
            return 0
        if processed_any:
            idle_start = None
        elif not is_process_alive(int(args.training_pid)):
            if idle_start is None:
                idle_start = time.time()
            elif (time.time() - idle_start) >= float(args.idle_exit_sec):
                return 0
        time.sleep(max(1.0, float(args.poll_sec)))


if __name__ == "__main__":
    raise SystemExit(main())

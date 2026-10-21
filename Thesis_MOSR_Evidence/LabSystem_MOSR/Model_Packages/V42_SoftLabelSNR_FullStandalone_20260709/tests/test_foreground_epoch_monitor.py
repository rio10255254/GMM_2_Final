from __future__ import annotations

import csv
import sys
from pathlib import Path


PACKAGE_ROOT = Path(__file__).resolve().parents[1]
if str(PACKAGE_ROOT) not in sys.path:
    sys.path.insert(0, str(PACKAGE_ROOT))

import foreground_epoch_monitor as mon  # noqa: E402


def test_completed_epoch_reads_epoch_checkpoints(tmp_path: Path) -> None:
    (tmp_path / "epoch_001.pth.tar").write_bytes(b"one")
    (tmp_path / "epoch_012.pth.tar").write_bytes(b"twelve")
    (tmp_path / "latest.pth.tar").write_bytes(b"latest")

    assert mon.completed_epoch_from_weights(tmp_path) == 12


def test_latest_batch_progress_reads_last_csv_row(tmp_path: Path) -> None:
    csv_path = tmp_path / "run_batch_log_v5.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["epoch", "batch", "loss_total"])
        writer.writeheader()
        writer.writerow({"epoch": 1, "batch": 5, "loss_total": 1.2})
        writer.writerow({"epoch": 1, "batch": 10, "loss_total": 1.1})

    progress = mon.latest_batch_progress(tmp_path)

    assert progress == mon.BatchProgress(epoch=1, batch=10)


def test_expected_batches_matches_weighted_sampler_drop_last() -> None:
    assert mon.expected_train_batches(train_count=100, batch_size=8, sample_mult=1.25) == 15
    assert mon.expected_train_batches(train_count=100, batch_size=4, sample_mult=1.25) == 31

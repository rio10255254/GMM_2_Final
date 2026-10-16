from __future__ import annotations

import sys
from pathlib import Path


PACKAGE_ROOT = Path(__file__).resolve().parents[1]
if str(PACKAGE_ROOT) not in sys.path:
    sys.path.insert(0, str(PACKAGE_ROOT))

import epoch_demo_monitor as monitor  # noqa: E402


def test_epoch_from_checkpoint_name() -> None:
    assert monitor.epoch_from_checkpoint(Path("epoch_001.pth.tar")) == 1
    assert monitor.epoch_from_checkpoint(Path("epoch_120.pth.tar")) == 120
    assert monitor.epoch_from_checkpoint(Path("latest.pth.tar")) is None


def test_find_epoch_checkpoints_filters_seen(tmp_path: Path) -> None:
    (tmp_path / "epoch_001.pth.tar").write_bytes(b"one")
    (tmp_path / "epoch_002.pth.tar").write_bytes(b"two")
    (tmp_path / "latest.pth.tar").write_bytes(b"latest")
    (tmp_path / "epoch_bad.pth.tar").write_bytes(b"bad")

    found = monitor.find_epoch_checkpoints(tmp_path, seen_epochs={1})

    assert [p.name for p in found] == ["epoch_002.pth.tar"]


def test_collect_demo_sets_requires_three_magnifications(tmp_path: Path) -> None:
    for name in ("100MG_50x", "100MG_20x", "100MG_5x"):
        d = tmp_path / name
        d.mkdir()
        (d / "sample.bmp").write_bytes(b"x")

    sets = monitor.collect_demo_sets(tmp_path)

    assert [s.label for s in sets] == ["100MG_50x", "100MG_20x", "100MG_5x"]
    assert all(s.image_count == 1 for s in sets)

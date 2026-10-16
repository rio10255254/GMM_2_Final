from __future__ import annotations

from pathlib import Path
import sys

import torch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from training.dataset import R116Dataset


def test_dataset_is_deterministic_and_has_three_views() -> None:
    first = R116Dataset("validation", epoch=3, limit=2)
    second = R116Dataset("validation", epoch=3, limit=2)
    left = first[0]
    right = second[0]
    for name in ("source", "target", "mask", "sdf", "edge", "pair_shift_px"):
        assert torch.equal(left[name], right[name]), name
    assert tuple(left["source"].shape) == (3, 1, 256, 256)
    assert tuple(left["pair_shift_px"].shape) == (2,)
    assert bool(left["identity"][2])
    assert torch.equal(left["source"][2], left["target"][2])


def test_dataset_epoch_changes_degradation_but_not_scene_identity() -> None:
    first = R116Dataset("train", epoch=1, limit=1)[0]
    second = R116Dataset("train", epoch=2, limit=1)[0]
    assert int(first["scene_index"]) == int(second["scene_index"])
    assert not torch.equal(first["source"][0], second["source"][0])
    assert torch.equal(first["target"][0], second["target"][0])


def test_known_pair_shift_moves_the_target() -> None:
    row = R116Dataset("validation", epoch=0, limit=1)[0]
    assert float(row["pair_shift_px"].abs().max()) <= 1.25 + 1.0e-6
    assert not torch.equal(row["target"][0], row["target"][1])
    assert torch.equal(row["target"][0], row["target"][2])


def test_validation_can_be_locked_to_one_challenge_and_role() -> None:
    degraded = R116Dataset(
        "validation", epoch=0, limit=2,
        challenge_override="mixed_hard", role_filter="degraded",
    )
    identity = R116Dataset(
        "validation", epoch=0, limit=2,
        challenge_override="identity", role_filter="identity",
    )
    flat = R116Dataset(
        "validation", epoch=0, limit=2,
        challenge_override="mixed_hard", role_filter="flat_negative",
    )
    assert len(degraded) == 2 and degraded[0]["challenge"] == "mixed_hard"
    assert len(identity) == 2 and bool(identity[0]["identity"].all())
    assert len(flat) == 2 and bool(flat[0]["flat"].all())

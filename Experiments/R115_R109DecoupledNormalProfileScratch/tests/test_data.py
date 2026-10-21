from __future__ import annotations

from pathlib import Path
import json
import sys

import torch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from training.r115_dataset import R115Dataset


def test_prepared_counts_and_ablation_populations() -> None:
    result = json.loads((ROOT / "data" / "preparation_result.json").read_text(encoding="utf-8"))
    assert result["counts"] == {"train": 5000, "validation": 512}
    assert result["probe_a_count"] == 2048
    assert result["probe_b_count"] == 2048
    assert result["probe_b_supplemental_count"] == 200
    assert result["common_validation_count"] == 472
    assert result["supplemental_validation_count"] == 40


def test_arm_sizes_and_supplemental_coverage() -> None:
    arm_a = R115Dataset("train", arm="A")
    arm_b = R115Dataset("train", arm="B")
    formal = R115Dataset("train", arm="formal")
    original_full = R115Dataset("train", arm="A_FULL")
    mixed = R115Dataset("train", arm="MIXED")
    appended_probe = R115Dataset("train", arm="C")
    half_appended_probe = R115Dataset("train", arm="D")
    assert len(arm_a) == 2048
    assert len(arm_b) == 2048
    assert len(formal) == 5000
    assert len(original_full) == 5000
    assert len(mixed) == 5200
    assert len(appended_probe) == 2248
    assert len(half_appended_probe) == 2148
    families = {row["family"] for row in arm_b.records}
    assert set(json.loads((ROOT / "config" / "experiment.json").read_text())["data"]["supplemental_families"]).issubset(families)


def test_representative_samples_are_finite_and_antialiased() -> None:
    dataset = R115Dataset("train", epoch=1, arm="B")
    indices = [0, len(dataset) // 3, 2 * len(dataset) // 3, len(dataset) - 1]
    for index in indices:
        row = dataset[index]
        for name in ("source", "target", "mask", "sdf", "edge"):
            assert torch.isfinite(row[name]).all(), (index, name)
        assert tuple(row["source"].shape) == (2, 1, 256, 256)
        assert float(row["source"].min()) >= 0.0
        assert float(row["source"].max()) <= 1.0
        assert torch.equal(row["source"][1], row["target"][1])
        assert bool(row["identity"][1])

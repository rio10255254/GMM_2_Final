import json
from pathlib import Path
import sys
import numpy as np

ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT))
from training.r119_dataset import R119Scenes


def test_candidate_shapes_and_two_view_contract():
    for candidate in ("A", "B", "D"):
        sample = R119Scenes("train", 1, 4, candidate, 1196001, set())[0]
        assert sample["source"].shape == (2, 1, 256, 256)
        assert sample["target"].shape == sample["source"].shape
        assert np.isfinite(sample["source"].numpy()).all()


def test_b_shared_policy_is_deterministic():
    a = R119Scenes("train", 3, 4, "B", 1196001, set())[0]
    b = R119Scenes("train", 3, 4, "B", 1196001, set())[0]
    assert np.array_equal(a["source"].numpy(), b["source"].numpy())


def test_d_requires_explicit_enrichment_ids():
    a = R119Scenes("train", 1, 4, "D", 1196001, set())[0]
    b = R119Scenes("train", 1, 4, "D", 1196001, {a["scene_index"]})[0]
    assert not np.array_equal(a["source"].numpy(), b["source"].numpy())

import json
from pathlib import Path
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "data"))
from sequence_bank import SequenceBank


def test_bank_inventory_and_replay():
    bank = SequenceBank(ROOT / "data/development_sequences")
    assert len(bank) == 48 * 91
    groups = bank.group()
    assert len(groups) == 48 * 12  # static + 3 motion + 5 exposure + 3 blur conditions
    first = bank.records[0]
    source, reference, mask = bank.load(first)
    assert source.shape == reference.shape == mask.shape == (256, 256)
    assert np.isfinite(source).all() and np.isfinite(reference).all()


def test_bank_protocol_counts():
    bank = SequenceBank(ROOT / "data/development_sequences")
    counts = {}
    for row in bank.records:
        counts[row["protocol"]] = counts.get(row["protocol"], 0) + 1
    assert counts == {"static_repeat": 48 * 8, "motion_x": 48 * 17, "motion_y": 48 * 17,
                      "motion_diag": 48 * 17, "exposure_static": 48 * 20, "blur_static": 48 * 12}


def test_manifest_does_not_include_real_or_confirmation_paths():
    text = (ROOT / "data/development_sequences/manifest.json").read_text(encoding="utf-8")
    assert "SEM_data" not in text and "confirmation" not in text.lower()

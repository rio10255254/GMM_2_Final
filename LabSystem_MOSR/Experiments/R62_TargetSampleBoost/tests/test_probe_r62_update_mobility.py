from __future__ import annotations

import importlib.util
from pathlib import Path

import torch


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "probe_r62_update_mobility.py"


def load_module():
    spec = importlib.util.spec_from_file_location("probe_r62_update_mobility", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_summarize_parameter_delta_groups_changed_and_unchanged_tensors():
    module = load_module()
    before = {
        "p1.weight": torch.tensor([1.0, 2.0]),
        "p1.bias": torch.tensor([0.5]),
        "boundary_adapter.delta.weight": torch.tensor([1.0]),
        "out.weight": torch.tensor([3.0]),
    }
    after = {
        "p1.weight": torch.tensor([1.0, 2.25]),
        "p1.bias": torch.tensor([0.5]),
        "boundary_adapter.delta.weight": torch.tensor([1.5]),
        "out.weight": torch.tensor([3.0]),
    }

    rows = module.summarize_parameter_delta(before, after)
    by_group = {row["group"]: row for row in rows}

    assert by_group["p1"]["changed_tensors"] == 1
    assert by_group["p1"]["changed_elements"] == 1
    assert by_group["p1"]["max_abs_delta"] == 0.25
    assert by_group["boundary_adapter"]["changed_elements"] == 1
    assert by_group["boundary_adapter"]["max_abs_delta"] == 0.5
    assert by_group["out"]["changed_elements"] == 0


def test_trainer_motion_regex_accepts_selfshift_patch_id_between_sequence_and_frame():
    module = load_module()
    name = "r62self_20260702_100MG_x_0p5um_seq00060_p000_f001.bmp"

    motion_match = module.trainer.MotionPairGrayFolder._SEQ_RE.search(name)
    sequence_match = module.trainer.SequencePairGrayFolder._SEQ_RE.search(name)

    assert motion_match is not None
    assert sequence_match is not None
    assert motion_match.group("seq") == "00060"
    assert motion_match.group("frame") == "001"
    assert sequence_match.group("seq") == "00060"
    assert sequence_match.group("frame") == "001"

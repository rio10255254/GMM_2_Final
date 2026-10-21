from __future__ import annotations

from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from dataclasses import fields

import torch

from model.r116_model import R116Details
from training.train import PROBE_PLAN, formal_stage, stage_for_epoch, take_details
from training.continue_calibration import calibration_batch_plan


def test_probe_exercises_every_independent_path() -> None:
    groups = [stage.group for stage in PROBE_PLAN]
    assert set(groups) == {"detector", "width", "shift", "detail"}
    assert any(stage.paired and stage.group == "width" for stage in PROBE_PLAN)
    assert any(stage.paired and stage.group == "shift" for stage in PROBE_PLAN)
    assert stage_for_epoch("probe", 1) == PROBE_PLAN[0]


def test_formal_schedule_covers_exact_contract() -> None:
    stages = [formal_stage(epoch) for epoch in range(1, 49)]
    assert all(stage.group == "detector" for stage in stages[:6])
    assert all(stage.name == "boundary_map" for stage in stages[:3])
    assert all(stage.name == "boundary_coordinate" for stage in stages[3:6])
    assert {stage.group for stage in stages[6:20]} == {"width", "shift"}
    assert all(stage.paired for stage in stages[20:30])
    assert all(stage.group == "detail" for stage in stages[30:42])
    assert {stage.group for stage in stages[42:]} == {"detector", "width", "shift", "detail"}


def test_paired_detail_slicing_is_view_based_and_noncopying() -> None:
    tensors = [torch.arange(6.0).view(6, 1, 1, 1) + index for index, _ in enumerate(fields(R116Details))]
    details = R116Details(*tensors)
    first = take_details(details, slice(0, 6, 3))
    second = take_details(details, slice(1, 6, 3))
    assert first.output[:, 0, 0, 0].tolist() == [0.0, 3.0]
    assert second.output[:, 0, 0, 0].tolist() == [1.0, 4.0]
    assert first.output.untyped_storage().data_ptr() == details.output.untyped_storage().data_ptr()


def test_calibration_microbatch_preserves_effective_batch() -> None:
    assert calibration_batch_plan("detector") == (12, 3)
    for group in ("width", "shift", "detail"):
        assert calibration_batch_plan(group) == (36, 1)
    assert 12 * 3 == 36

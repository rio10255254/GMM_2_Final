from pathlib import Path
import sys

import torch
from torch import nn


REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT_DIR = REPO_ROOT / "Experiments" / "R41_RingDistillation" / "scripts"
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))


class OffsetTeacher(nn.Module):
    def __init__(self, offset: float):
        super().__init__()
        self.offset = nn.Parameter(torch.tensor(float(offset)))

    def forward(self, x):
        return x + self.offset


def test_role_gated_kd_uses_only_matching_teachers_and_freezes_them():
    import r41_kd_module

    src = torch.zeros(3, 1, 4, 4)
    pred = torch.zeros_like(src, requires_grad=True)
    role = torch.tensor([
        r41_kd_module.ROLE_RING,
        r41_kd_module.ROLE_SHAPE,
        r41_kd_module.ROLE_MICRO,
    ])
    combo = OffsetTeacher(1.0)
    micro = OffsetTeacher(0.5)

    r41_kd_module.freeze_teacher(combo)
    r41_kd_module.freeze_teacher(micro)
    loss, parts = r41_kd_module.role_gated_kd_loss(
        pred,
        src,
        role,
        teacher_combo=combo,
        teacher_r40=micro,
        weight_combo=0.10,
        weight_r40=0.05,
    )
    loss.backward()

    expected = 0.10 * 1.0 + 0.05 * 0.25
    assert torch.isclose(loss.detach(), torch.tensor(expected))
    assert torch.isclose(parts["combo"], torch.tensor(0.10))
    assert torch.isclose(parts["r40"], torch.tensor(0.0125))
    assert combo.offset.grad is None
    assert micro.offset.grad is None
    assert pred.grad is not None


def test_role_gated_kd_skips_shape_samples_by_default():
    import r41_kd_module

    src = torch.zeros(1, 1, 4, 4)
    pred = torch.zeros_like(src, requires_grad=True)
    role = torch.tensor([r41_kd_module.ROLE_SHAPE])
    combo = OffsetTeacher(1.0)
    micro = OffsetTeacher(2.0)

    loss, parts = r41_kd_module.role_gated_kd_loss(
        pred,
        src,
        role,
        teacher_combo=combo,
        teacher_r40=micro,
        weight_combo=0.10,
        weight_r40=0.05,
    )

    assert loss.item() == 0.0
    assert parts["combo"].item() == 0.0
    assert parts["r40"].item() == 0.0

from __future__ import annotations

from pathlib import Path
import sys

import torch
from torch import nn


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from model.full_model import build_full_model


def sample(height: int = 80, width: int = 88) -> torch.Tensor:
    yy, xx = torch.meshgrid(torch.linspace(-1, 1, height), torch.linspace(-1, 1, width), indexing="ij")
    shape = (((xx / 0.55) ** 2 + (yy / 0.37) ** 2) < 1).float()
    return (0.2 + 0.58 * shape + 0.03 * torch.sin(21 * xx)).clamp(0, 1)[None, None]


def test_full_model_contract_and_gradients() -> None:
    torch.manual_seed(11410)
    model = build_full_model(detail_enabled=True, compact=True)
    value = sample().requires_grad_(True)
    details = model.forward_details(value)
    assert details.output.shape == value.shape
    assert details.flow.shape == (1, 2, 80, 88)
    assert torch.isfinite(details.output).all()
    assert float(details.output.min()) >= 0 and float(details.output.max()) <= 1
    assert float(details.width_gain.min()) >= 1.0 and float(details.width_gain.max()) <= 3.5
    assert float(details.normal_shift.abs().max()) <= 1.5
    assert torch.allclose(details.geometry_gate, details.boundary_confidence * details.correction_need)
    assert torch.allclose(details.detail_gate, details.geometry_gate * details.recoverability)
    details.output.mean().backward()
    assert value.grad is not None and float(value.grad.abs().sum()) > 0


def test_detail_is_bounded_and_disableable() -> None:
    torch.manual_seed(11411)
    model = build_full_model(detail_enabled=True, compact=True).eval()
    value = sample()
    with torch.inference_mode():
        enabled = model.forward_details(value)
        model.set_detail_enabled(False)
        disabled = model.forward_details(value)
    assert torch.count_nonzero(disabled.detail) == 0
    assert torch.allclose(disabled.output, disabled.base_output.clamp(0, 1))
    assert float(enabled.detail.abs().max()) <= 18.0 / 255.0 + 1e-6


def test_no_forbidden_global_or_spatial_modules() -> None:
    model = build_full_model(compact=True)
    forbidden = (nn.GroupNorm, nn.BatchNorm2d, nn.InstanceNorm2d, nn.AdaptiveAvgPool2d)
    assert not any(isinstance(module, forbidden) for module in model.modules())
    names = " ".join(model.state_dict()).lower()
    assert "raw_anchor" not in names
    assert "global" not in names

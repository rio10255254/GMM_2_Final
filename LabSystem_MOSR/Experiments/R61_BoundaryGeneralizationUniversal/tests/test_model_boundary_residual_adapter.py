from __future__ import annotations

import sys
from pathlib import Path

import torch


MODEL_DIR = Path(__file__).resolve().parents[4] / "Model"
sys.path.insert(0, str(MODEL_DIR))

from GeoEdgeAlignSR_v1_ModelA_v5_NoCoord import GeoEdgeAlignSR_v1_v5_NoCoord  # noqa: E402


def build_model(*, adapter: bool) -> GeoEdgeAlignSR_v1_v5_NoCoord:
    torch.manual_seed(123)
    return GeoEdgeAlignSR_v1_v5_NoCoord(
        in_ch=1,
        base=8,
        use_physics_layer=False,
        use_sigmoid_output=True,
        weak_psf_enable=False,
        boundary_residual_adapter_enable=adapter,
        boundary_residual_adapter_hidden=4,
        boundary_residual_adapter_max=0.025,
    ).eval()


def build_edge_limited_model() -> GeoEdgeAlignSR_v1_v5_NoCoord:
    torch.manual_seed(123)
    return GeoEdgeAlignSR_v1_v5_NoCoord(
        in_ch=1,
        base=8,
        use_physics_layer=False,
        use_sigmoid_output=True,
        weak_psf_enable=False,
        boundary_residual_adapter_enable=True,
        boundary_residual_adapter_hidden=4,
        boundary_residual_adapter_max=0.025,
        boundary_residual_adapter_delta_bias=False,
        boundary_residual_adapter_zero_mean=True,
        boundary_residual_adapter_edge_gate=True,
    ).eval()


def build_polarity_split_model() -> GeoEdgeAlignSR_v1_v5_NoCoord:
    torch.manual_seed(123)
    return GeoEdgeAlignSR_v1_v5_NoCoord(
        in_ch=1,
        base=8,
        use_physics_layer=False,
        use_sigmoid_output=True,
        weak_psf_enable=False,
        boundary_residual_adapter_enable=True,
        boundary_residual_adapter_hidden=4,
        boundary_residual_adapter_max=0.025,
        boundary_residual_adapter_polarity_split=True,
    ).eval()


def build_orientation_model() -> GeoEdgeAlignSR_v1_v5_NoCoord:
    torch.manual_seed(123)
    return GeoEdgeAlignSR_v1_v5_NoCoord(
        in_ch=1,
        base=8,
        use_physics_layer=False,
        use_sigmoid_output=True,
        weak_psf_enable=False,
        boundary_residual_adapter_enable=True,
        boundary_residual_adapter_hidden=4,
        boundary_residual_adapter_max=0.025,
        boundary_residual_adapter_orientation_inputs=True,
    ).eval()


def test_boundary_residual_adapter_starts_as_exact_noop_for_old_weights():
    base_model = build_model(adapter=False)
    adapter_model = build_model(adapter=True)
    incompatible = adapter_model.load_state_dict(base_model.state_dict(), strict=False)
    assert all(key.startswith("boundary_adapter.") for key in incompatible.missing_keys)
    assert incompatible.unexpected_keys == []

    x = torch.rand(2, 1, 64, 64)
    with torch.no_grad():
        base_out = base_model(x)
        adapter_out = adapter_model(x)

    assert torch.allclose(adapter_out, base_out, atol=0.0, rtol=0.0)


def test_boundary_residual_adapter_has_trainable_local_parameters():
    model = build_model(adapter=True)

    trainable_names = {name for name, param in model.named_parameters() if param.requires_grad}

    assert any(name.startswith("boundary_adapter.") for name in trainable_names)
    assert "boundary_adapter.delta.weight" in trainable_names
    assert "boundary_adapter.delta.bias" in trainable_names


def test_boundary_residual_adapter_can_disable_global_delta_bias():
    model = build_edge_limited_model()

    assert model.boundary_adapter.delta.bias is None
    assert model.boundary_adapter.zero_mean_delta is True
    assert model.boundary_adapter.edge_gate_enable is True


def test_edge_limited_boundary_residual_adapter_is_also_initial_noop():
    base_model = build_model(adapter=False)
    adapter_model = build_edge_limited_model()
    incompatible = adapter_model.load_state_dict(base_model.state_dict(), strict=False)
    assert all(key.startswith("boundary_adapter.") for key in incompatible.missing_keys)
    assert incompatible.unexpected_keys == []

    x = torch.rand(2, 1, 64, 64)
    with torch.no_grad():
        base_out = base_model(x)
        adapter_out = adapter_model(x)

    assert torch.allclose(adapter_out, base_out, atol=0.0, rtol=0.0)


def test_polarity_split_boundary_adapter_has_two_zero_initialized_delta_modes():
    base_model = build_model(adapter=False)
    adapter_model = build_polarity_split_model()
    incompatible = adapter_model.load_state_dict(base_model.state_dict(), strict=False)
    assert all(key.startswith("boundary_adapter.") for key in incompatible.missing_keys)
    assert incompatible.unexpected_keys == []

    assert adapter_model.boundary_adapter.polarity_split is True
    assert adapter_model.boundary_adapter.delta.weight.shape[0] == 2
    assert adapter_model.boundary_adapter.polarity_gate.weight.shape[0] == 2

    x = torch.rand(2, 1, 64, 64)
    with torch.no_grad():
        base_out = base_model(x)
        adapter_out = adapter_model(x)

    assert torch.allclose(adapter_out, base_out, atol=0.0, rtol=0.0)


def test_orientation_boundary_adapter_adds_direction_inputs_but_starts_as_noop():
    base_model = build_model(adapter=False)
    adapter_model = build_orientation_model()
    incompatible = adapter_model.load_state_dict(base_model.state_dict(), strict=False)
    assert all(key.startswith("boundary_adapter.") for key in incompatible.missing_keys)
    assert incompatible.unexpected_keys == []

    assert adapter_model.boundary_adapter.orientation_inputs is True
    assert adapter_model.boundary_adapter.body[0].weight.shape[1] == 8 + 1 + 3

    x = torch.rand(2, 1, 64, 64)
    with torch.no_grad():
        base_out = base_model(x)
        adapter_out = adapter_model(x)

    assert torch.allclose(adapter_out, base_out, atol=0.0, rtol=0.0)

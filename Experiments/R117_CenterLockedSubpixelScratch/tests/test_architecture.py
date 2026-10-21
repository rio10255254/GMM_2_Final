from pathlib import Path
import sys
import torch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from inference.tiled import forward_tiled
from model.r117_model import build_model


def test_identity_initialization_and_finite():
    model = build_model().eval()
    value = torch.rand(1, 1, 64, 72)
    with torch.inference_mode():
        details = model.forward_details(value)
    assert torch.isfinite(details.output).all()
    assert torch.equal(details.output, value)
    assert details.high_predicted_sdf_px.shape[-2:] == (128, 144)


def test_independent_shift_path_and_parameter_groups():
    model = build_model()
    names = set(dict(model.named_parameters()))
    assert any("shift_tower" in name for name in names)
    assert set(model.parameter_groups()) == {"detector", "width", "shift", "detail"}


def test_tile_contract_matches_full_frame():
    model = build_model().eval()
    value = torch.rand(1, 1, 96, 104)
    with torch.inference_mode():
        direct = model(value)
        tiled = forward_tiled(model, value, core_size=48, halo=224)
    assert (direct - tiled).abs().max().item() < 1.0e-6

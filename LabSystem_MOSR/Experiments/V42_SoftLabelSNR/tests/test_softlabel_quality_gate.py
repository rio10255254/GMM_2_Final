from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import torch


EXPERIMENT_DIR = Path(__file__).resolve().parents[1]
SCRIPT_DIR = EXPERIMENT_DIR / "scripts"
MODEL_DIR = Path(__file__).resolve().parents[4] / "Model"
sys.path.insert(0, str(SCRIPT_DIR))
sys.path.insert(0, str(MODEL_DIR))

from prepare_v42_softlabel_snr_package import (  # noqa: E402
    edge_softness_score,
    soften_label_array,
)
from GeoEdgeAlignSR_v1_ModelA_v5_NoCoord import (  # noqa: E402
    GeoEdgeAlignSR_v1_v5_NoCoord,
    ImageQualityGate,
)


def _disk_mask(size: int = 64, radius: int = 17) -> np.ndarray:
    yy, xx = np.mgrid[:size, :size]
    center = (size - 1) / 2.0
    mask = ((xx - center) ** 2 + (yy - center) ** 2) <= radius**2
    return (mask.astype(np.uint8) * 255)


def test_soften_label_array_adds_antialiasing_only_near_edges() -> None:
    hard = _disk_mask()
    soft = soften_label_array(hard, sigma=0.75, edge_band_px=2, blend=1.0)

    assert soft.dtype == np.uint8
    assert soft.shape == hard.shape
    assert int(soft[32, 32]) >= 252
    assert int(soft[0, 0]) <= 3
    assert np.count_nonzero((soft > 0) & (soft < 255)) > 0
    assert edge_softness_score(soft) > edge_softness_score(hard)


def test_image_quality_gate_scores_noisy_image_lower_than_clean_edge() -> None:
    clean = torch.zeros(1, 1, 64, 64)
    clean[:, :, 18:46, 18:46] = 1.0
    torch.manual_seed(123)
    noisy = (clean + torch.randn_like(clean) * 0.18).clamp(0.0, 1.0)

    clean_score = ImageQualityGate.estimate_quality_score(clean)
    noisy_score = ImageQualityGate.estimate_quality_score(noisy)

    assert clean_score.shape == (1, 1, 1, 1)
    assert noisy_score.shape == (1, 1, 1, 1)
    assert float(clean_score.item()) > float(noisy_score.item())


def test_quality_gate_model_branch_is_backward_compatible_and_shape_safe() -> None:
    torch.manual_seed(123)
    base_model = GeoEdgeAlignSR_v1_v5_NoCoord(
        in_ch=1,
        base=8,
        use_physics_layer=False,
        use_sigmoid_output=True,
        weak_psf_enable=False,
    ).eval()
    gated_model = GeoEdgeAlignSR_v1_v5_NoCoord(
        in_ch=1,
        base=8,
        use_physics_layer=False,
        use_sigmoid_output=True,
        weak_psf_enable=False,
        quality_gate_enable=True,
        quality_gate_hidden=4,
    ).eval()

    incompatible = gated_model.load_state_dict(base_model.state_dict(), strict=False)
    assert all(key.startswith("quality_gate.") for key in incompatible.missing_keys)
    assert incompatible.unexpected_keys == []

    x = torch.rand(2, 1, 64, 64)
    with torch.no_grad():
        y = gated_model(x)

    assert y.shape == x.shape
    assert gated_model.last_quality_gate is not None
    assert gated_model.last_quality_gate.shape == (2, 1, 1, 1)
    assert torch.all(gated_model.last_quality_gate >= 0.0)
    assert torch.all(gated_model.last_quality_gate <= 1.0)

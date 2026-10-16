from __future__ import annotations

import sys
from pathlib import Path

import torch


SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from model_zoo import MODEL_SPECS, TRAINABLE_KEYS, build_backbone  # noqa: E402


def test_roster_contains_twelve_external_architectures() -> None:
    expected = {
        "srcnn", "vdsr", "dncnn", "unet", "edsr", "rdn", "rcan",
        "swinir", "nafnet", "restormer", "pft", "ucan",
    }
    assert expected == set(MODEL_SPECS)
    assert len(TRAINABLE_KEYS) == 12
    assert MODEL_SPECS["pft"].year == 2025
    assert MODEL_SPECS["ucan"].year == 2026
    assert "official UCAN code" in MODEL_SPECS["ucan"].source


def test_non_pft_backbones_preserve_grayscale_shape() -> None:
    source = torch.rand(1, 1, 32, 32)
    for key in MODEL_SPECS:
        if key == "pft":
            continue
        model = build_backbone(key).eval()
        with torch.inference_mode():
            result = model(source)
        assert result.shape == source.shape, key
        assert torch.isfinite(result).all(), key

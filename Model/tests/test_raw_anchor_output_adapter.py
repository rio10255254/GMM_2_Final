from __future__ import annotations

from pathlib import Path
import sys

import torch


MODEL_DIR = Path(__file__).resolve().parents[1]
if str(MODEL_DIR) not in sys.path:
    sys.path.insert(0, str(MODEL_DIR))


def test_raw_anchor_output_detail_preserves_raw_low_frequency_and_keeps_detail():
    from GeoEdgeAlignSR_v1_ModelA_v5_NoCoord import RawAnchorOutputAdapter

    yy, xx = torch.meshgrid(torch.arange(64), torch.arange(64), indexing="ij")
    raw = (0.20 + 0.004 * xx.float() + 0.002 * yy.float()).view(1, 1, 64, 64)
    pred = (0.20 + 0.004 * (xx.float() - 6.0) + 0.002 * yy.float()).view(1, 1, 64, 64)
    pred[:, :, :, 32:] = pred[:, :, :, 32:] + 0.25
    adapter = RawAnchorOutputAdapter(mode="detail", sigma=2.5, detail_gain=1.0)

    anchored = adapter(raw, pred)

    assert anchored.shape == raw.shape
    assert torch.mean(torch.abs(anchored[:, :, :, :16] - raw[:, :, :, :16])).item() < 0.01
    assert torch.std(anchored - raw).item() > 0.005


def test_raw_anchor_output_blend_uses_reconstruction_fraction():
    from GeoEdgeAlignSR_v1_ModelA_v5_NoCoord import RawAnchorOutputAdapter

    raw = torch.full((1, 1, 8, 8), 0.2)
    pred = torch.full((1, 1, 8, 8), 0.8)
    adapter = RawAnchorOutputAdapter(mode="blend", alpha=0.25)

    anchored = adapter(raw, pred)

    torch.testing.assert_close(anchored, torch.full_like(raw, 0.35))


def test_raw_anchor_output_none_returns_prediction():
    from GeoEdgeAlignSR_v1_ModelA_v5_NoCoord import RawAnchorOutputAdapter

    raw = torch.full((1, 1, 8, 8), 0.2)
    pred = torch.full((1, 1, 8, 8), 0.8)
    adapter = RawAnchorOutputAdapter(mode="none")

    anchored = adapter(raw, pred)

    torch.testing.assert_close(anchored, pred)

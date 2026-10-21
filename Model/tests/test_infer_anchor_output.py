from __future__ import annotations

import importlib.util
from pathlib import Path

import numpy as np
import pytest


INFER_PATH = Path(__file__).resolve().parents[1] / "GeoEdgeAlignSR_v1_Infer_v5_NoCoord_return_v2_SimpleTest.py"


def load_infer_module():
    spec = importlib.util.spec_from_file_location("geoedge_infer_for_anchor_test", INFER_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_anchor_output_detail_preserves_raw_low_frequency_position():
    infer = load_infer_module()
    yy, xx = np.mgrid[0:96, 0:96].astype(np.float32)
    raw = 0.20 + 0.0035 * xx + 0.0015 * yy
    shifted_recon = 0.20 + 0.0035 * (xx - 8.0) + 0.0015 * yy
    shifted_recon[:, 48:] += 0.25

    anchored = infer.apply_anchor_output(
        raw,
        shifted_recon,
        mode="detail",
        sigma=3.0,
        detail_gain=1.0,
    )

    assert anchored.shape == raw.shape
    assert abs(float(np.mean(anchored)) - float(np.mean(raw))) < 0.01
    assert abs(float(np.mean(anchored[:, :24])) - float(np.mean(raw[:, :24]))) < 0.01
    assert float(np.std(anchored - raw)) > 0.005


def test_anchor_output_blend_uses_alpha_as_reconstruction_fraction():
    infer = load_infer_module()
    raw = np.full((4, 4), 0.2, dtype=np.float32)
    recon = np.full((4, 4), 0.8, dtype=np.float32)

    anchored = infer.apply_anchor_output(raw, recon, mode="blend", alpha=0.25)

    np.testing.assert_allclose(anchored, 0.35, atol=1e-6)


def test_anchor_output_none_keeps_model_prediction():
    infer = load_infer_module()
    raw = np.full((4, 4), 0.2, dtype=np.float32)
    recon = np.full((4, 4), 0.8, dtype=np.float32)

    anchored = infer.apply_anchor_output(raw, recon, mode="none")

    np.testing.assert_allclose(anchored, recon, atol=1e-6)


def test_anchor_output_rejects_shape_mismatch():
    infer = load_infer_module()
    raw = np.zeros((4, 4), dtype=np.float32)
    recon = np.zeros((4, 5), dtype=np.float32)

    with pytest.raises(ValueError, match="shape mismatch"):
        infer.apply_anchor_output(raw, recon, mode="blend", alpha=0.1)


def test_inference_default_does_not_force_odd_frame_selection():
    infer = load_infer_module()

    assert infer.MANUAL_SELECT_MODE is None


def test_infer_arch_reads_raw_anchor_output_from_checkpoint_config():
    infer = load_infer_module()
    ckpt = {
        "model_config": {
            "raw_anchor_output": {
                "mode": "detail",
                "alpha": 0.1,
                "sigma": 2.0,
                "detail_gain": 0.35,
            }
        }
    }

    arch = infer.infer_arch_from_state({}, ckpt_obj=ckpt)

    assert arch["raw_anchor_output_mode"] == "detail"
    assert arch["raw_anchor_output_alpha"] == 0.1
    assert arch["raw_anchor_output_sigma"] == 2.0
    assert arch["raw_anchor_output_detail_gain"] == 0.35

from __future__ import annotations

from pathlib import Path

import torch

from probes.r114d_action_selector.adapter import (
    R114D_REQUIRED_MAPS,
    canonical_tile_config,
    load_model,
    load_selector_model,
    predict_canonical_tiled,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]
EPOCH_ONE = (
    Path(__file__).resolve().parent
    / "runs"
    / "r114d_selector_short_probe_20260831"
    / "weights"
    / "epoch_001.pth"
)


def test_load_epoch_one_is_strict_read_only_and_pinned_to_e24() -> None:
    model = load_selector_model(EPOCH_ONE, torch.device("cpu"))
    assert not any(parameter.requires_grad for parameter in model.parameters())
    metadata = model.checkpoint_metadata
    assert metadata["selector_epoch"] == 1
    assert metadata["proposal"]["epoch"] == 24
    assert metadata["proposal"]["checkpoint_sha256"] == (
        "909439fad61df63da628db33ed2f93974c2fdc2b18ac11da98d3058bb595e311"
    )


def test_adapter_matches_core_model_and_exposes_locked_runner_maps() -> None:
    core = load_selector_model(EPOCH_ONE, torch.device("cpu"))
    wrapped = load_model(str(EPOCH_ONE), torch.device("cpu"))
    torch.manual_seed(1145201)
    image = torch.rand(1, 1, 63, 69)
    with torch.inference_mode():
        expected = core.forward_details(image)
        actual = wrapped(image)
    assert torch.allclose(actual["output"], expected.output, atol=1.0e-7, rtol=0)
    assert set(R114D_REQUIRED_MAPS) <= set(actual)
    assert torch.allclose(
        actual["causal_gate"],
        actual["boundary_confidence"]
        * actual["correction_need"]
        * actual["recoverability"]
        * actual["acceptance"]
        * actual["amount"],
        atol=0,
        rtol=0,
    )


def test_canonical_tiled_adapter_small_cpu_smoke() -> None:
    wrapped = load_model(str(EPOCH_ONE), torch.device("cpu"))
    torch.manual_seed(1145202)
    image = torch.rand(1, 1, 72, 75)
    config = canonical_tile_config(wrapped, core=96)
    prediction = predict_canonical_tiled(wrapped, image, config)
    assert prediction.output.shape == image.shape
    assert prediction.tile_count == 1
    assert set(R114D_REQUIRED_MAPS) <= set(prediction.maps)
    assert torch.isfinite(prediction.output).all()

from __future__ import annotations

from pathlib import Path

import torch

from probes.r114e_decoupled_hybrid.adapter import (
    REQUIRED_MAPS,
    canonical_tile_config,
    load_model,
    load_selector_model,
    predict_canonical_tiled,
)


SMOKE_CHECKPOINT = (
    Path(__file__).resolve().parent
    / "runs" / "gpu_trainer_smoke" / "weights" / "epoch_001.pth"
)


def test_smoke_checkpoint_loads_strict_and_read_only() -> None:
    model = load_selector_model(SMOKE_CHECKPOINT, "cpu")
    assert not any(parameter.requires_grad for parameter in model.parameters())
    assert model.checkpoint_metadata["source_provenance"]["geometry"]["epoch"] == 20
    assert model.checkpoint_metadata["source_provenance"]["profile"]["epoch"] == 24


def test_adapter_matches_core_and_exposes_locked_maps() -> None:
    core = load_selector_model(SMOKE_CHECKPOINT, "cpu")
    wrapped = load_model(str(SMOKE_CHECKPOINT), torch.device("cpu"))
    torch.manual_seed(1146201)
    image = torch.rand(1, 1, 63, 69)
    with torch.inference_mode():
        expected = core.forward_details(image)
        actual = wrapped(image)
    assert torch.allclose(actual["output"], expected.output, atol=1e-7, rtol=0)
    assert set(REQUIRED_MAPS) <= set(actual)
    required_gate = (
        actual["boundary_confidence"] * actual["correction_need"]
        * actual["recoverability"] * actual["acceptance"] * actual["amount"]
    )
    assert torch.equal(actual["causal_gate"], required_gate)


def test_canonical_one_tile_adapter_smoke() -> None:
    wrapped = load_model(str(SMOKE_CHECKPOINT), torch.device("cpu"))
    image = torch.rand(1, 1, 72, 75)
    prediction = predict_canonical_tiled(
        wrapped, image, canonical_tile_config(wrapped, core=96)
    )
    assert prediction.output.shape == image.shape
    assert prediction.tile_count == 1
    assert set(REQUIRED_MAPS) <= set(prediction.maps)
    assert torch.isfinite(prediction.output).all()


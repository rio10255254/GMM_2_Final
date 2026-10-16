from __future__ import annotations

from pathlib import Path
import sys

import torch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from model.r116_model import R116Config, build_model
from validation.adapter import Wrapper, canonical_tile_config, predict_canonical_tiled


def test_validation_adapter_has_required_maps_and_exact_coverage() -> None:
    config = R116Config(
        base_channels=8, action_channels=8, detail_channels=8,
        detector_dilations=(1,), action_dilations=(1,), detail_dilations=(1,),
        blur_scales_px=(0.5, 0.8, 1.1, 1.4),
        profile_offsets_px=(-2, 0, 2), coherence_offsets_px=(-1, 0, 1),
        coherence_sigma_px=1.0, maximum_predicted_sdf_px=3.0,
        local_range_window_px=5, low_frequency_anchor_sigma_px=0.8,
        minimum_halo_px=24,
    )
    model = Wrapper(build_model(config).eval())
    image = torch.rand(1, 1, 72, 80)
    result = predict_canonical_tiled(
        model, image, canonical_tile_config(model, core=40, halo=24),
    )
    assert torch.equal(result.output, image)
    assert bool((result.coverage == 1).all())
    assert {"width_gate", "shift_gate", "profile_visibility"} <= set(result.maps)

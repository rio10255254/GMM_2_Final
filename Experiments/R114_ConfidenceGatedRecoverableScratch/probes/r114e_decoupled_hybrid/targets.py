"""R114E selector labels, reusing the audited causal-direction definition."""

from __future__ import annotations

import json

from probes.r114d_action_selector.targets import (
    SelectorTargets,
    TargetConfig,
    build_selector_targets,
)

from .model import PROBE_ROOT


def load_target_config() -> TargetConfig:
    payload = json.loads((PROBE_ROOT / "config.json").read_text(encoding="utf-8"))
    return TargetConfig(**{
        key: payload[key]
        for key in (
            "boundary_band_px",
            "gain_margin_gray_squared",
            "clear_error_gray",
            "minimum_candidate_delta_gray",
            "minimum_positive_alpha",
            "identity_hard_negative_max_ratio_to_true_band",
        )
    })


__all__ = [
    "SelectorTargets",
    "TargetConfig",
    "build_selector_targets",
    "load_target_config",
]


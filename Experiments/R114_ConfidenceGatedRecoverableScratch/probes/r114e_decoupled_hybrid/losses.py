"""R114E selector losses with the isolated probe's pinned weights."""

from probes.r114d_action_selector.losses import (
    LossConfig,
    SelectorLosses,
    selector_loss,
)

from .model import PROBE_ROOT


def load_loss_config() -> LossConfig:
    return LossConfig.from_json(PROBE_ROOT / "config.json")


__all__ = ["LossConfig", "SelectorLosses", "selector_loss", "load_loss_config"]


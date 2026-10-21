"""Independent R114D causal action-selector probe.

Nothing in this package is imported by the main R114 model or trainer.  The
package deliberately treats the sealed R114C E24 checkpoint as a frozen,
read-only proposal generator and trains only a new local selector.
"""

from .model import (
    R114DActionSelector,
    R114DOutput,
    SelectorConfig,
    forward_tiled_selector,
    load_frozen_e24_proposal,
)
from .targets import SelectorTargets, build_selector_targets

__all__ = [
    "R114DActionSelector",
    "R114DOutput",
    "SelectorConfig",
    "SelectorTargets",
    "build_selector_targets",
    "forward_tiled_selector",
    "load_frozen_e24_proposal",
]

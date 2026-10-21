"""Small deterministic common-descent primitive for grouped R96 objectives."""
from __future__ import annotations

from collections.abc import Sequence

import torch


def common_descent_direction(
    gradients: Sequence[torch.Tensor],
    *,
    passes: int = 4,
    eps: float = 1e-12,
) -> torch.Tensor:
    """Return an update gradient whose dot product with every task is nonnegative.

    Optimizers subtract this vector.  A nonnegative dot product therefore gives
    a non-increasing first-order step for every supplied objective.  If repeated
    half-space projections collapse the common direction, a zero shared update
    is returned instead of sacrificing one objective.
    """
    if not gradients:
        raise ValueError("At least one gradient is required")
    shape = gradients[0].shape
    if any(gradient.shape != shape for gradient in gradients):
        raise ValueError("All gradients must have the same shape")
    tasks = [gradient.detach() for gradient in gradients]
    direction = torch.stack(tasks).mean(dim=0)
    for _ in range(int(passes)):
        changed = False
        for task in tasks:
            dot = torch.dot(direction.reshape(-1), task.reshape(-1))
            if dot < 0:
                direction = direction - dot * task / task.square().sum().clamp_min(eps)
                changed = True
        if not changed:
            break
    dots = torch.stack([torch.dot(direction.reshape(-1), task.reshape(-1)) for task in tasks])
    if not torch.isfinite(direction).all() or bool((dots < -1e-7).any()):
        return torch.zeros_like(direction)
    return direction



"""Training policy for fixed native-image PSF consistency."""
from __future__ import annotations

import torch


def optimizer(model, base_lr=3e-4, weight_decay=1e-5,
              optical_lr_multiplier=0.2):
    main = []
    optical_step = []
    for name, parameter in model.named_parameters():
        (optical_step if name == "optical_step_logits" else main).append(parameter)
    assert len(optical_step) == 1 and main
    return torch.optim.AdamW([
        {"params": main, "lr": base_lr, "name": "main"},
        {"params": optical_step, "lr": base_lr*optical_lr_multiplier,
         "name": "optical_step"},
    ], weight_decay=weight_decay)


def apply_epoch_policy(model, epoch: int):
    if epoch < 0:
        raise ValueError("Epoch must be nonnegative")
    model.optical_enabled = True
    return {"optical_active": True, "psf_mode": model.cfg["psf_mode"]}


def project_beta_after_step(model):
    # The positive physical step is bounded by sigmoid in Model.forward.
    return None

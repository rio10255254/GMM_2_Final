"""Provisional R140v2 training policy; no formal run has begun."""
import torch

def optimizer(model, base_lr=1e-3, weight_decay=1e-5, optical_lr_multiplier=0.05):
    optical = []
    main = []
    for name, parameter in model.named_parameters():
        (optical if name.startswith("refiner.optics.") else main).append(parameter)
    assert optical and main
    return torch.optim.AdamW([
        {"params": main, "lr": base_lr, "name": "main"},
        {"params": optical, "lr": base_lr * optical_lr_multiplier, "name": "optical"},
    ], weight_decay=weight_decay)

def apply_epoch_policy(model, epoch: int):
    if epoch < 0:
        raise ValueError("Epoch must be nonnegative")
    if epoch < 2:
        model.refiner.optics.set_beta_scale(0.0)
        for parameter in model.refiner.optics.parameters():
            parameter.requires_grad_(False)
        return {"optical_active": False, "beta_scale": 0.0}
    scale = 0.12 + 0.16 * min(max((epoch-2)/6, 0.0), 1.0)
    model.refiner.optics.set_beta_scale(scale)
    for parameter in model.refiner.optics.parameters():
        parameter.requires_grad_(True)
    return {"optical_active": True, "beta_scale": scale}

def project_beta_after_step(model):
    # The original V42 forward clamps beta. Keep the raw parameter inside that
    # interval so a negative optimizer overshoot cannot permanently kill its gradient.
    block = model.refiner.optics
    with torch.no_grad():
        block.beta.clamp_(block.beta_min, block.beta_max)

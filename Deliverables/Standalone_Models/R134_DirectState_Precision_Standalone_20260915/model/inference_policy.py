"""Native input boundary retention; same policy as the saved pilot."""
import torch

def guard(raw, pred):
    h, w = raw.shape[-2:]
    y = torch.arange(h, device=raw.device)[:, None]
    x = torch.arange(w, device=raw.device)[None, :]
    d = torch.minimum(torch.minimum(y, h - 1 - y), torch.minimum(x, w - 1 - x)).float()
    weight = ((d - 16) / 16).clamp(0, 1)
    return raw + (pred - raw) * weight

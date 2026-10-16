"""Original-image reference, bounded quality scaling, and brightness correction."""
import torch
from torch.nn import functional as F

def anchored_output(raw, neural, kernel):
    k = kernel
    low = F.conv2d(torch.cat([neural[..., 1:7].flip(-1), neural, neural[..., -7:-1].flip(-1)], -1), k[None, None, None, :])
    low = F.conv2d(torch.cat([low[..., 1:7, :].flip(-2), low, low[..., -7:-1, :].flip(-2)], -2), k[None, None, :, None])
    dx = raw[..., 1:] - raw[..., :-1]
    dy = raw[..., 1:, :] - raw[..., :-1, :]
    signal = (dx.abs().mean((1, 2, 3)) + dy.abs().mean((1, 2, 3))) * 0.5
    smooth = F.avg_pool2d(raw, 5, 1, 2, count_include_pad=False)
    noise = (raw - smooth).abs().mean((1, 2, 3))
    q = signal / (signal + 3 * noise + 1e-08)
    strength = 0.78 + 0.3 * q
    result = raw + 0.35 * strength[:, None, None, None] * (neural - low)
    result = result - result.mean((2, 3), keepdim=True) + raw.mean((2, 3), keepdim=True)
    return (result.clamp(0, 1), q)

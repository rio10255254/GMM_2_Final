"""One shared reconstruction network, reused four times."""
import torch
from torch import nn
from torch.nn import functional as F
from torch.utils.checkpoint import checkpoint
from .operators import reflect_pad, replicate_one, Bilinear2x

class Block(nn.Module):

    def __init__(self, c, d):
        super().__init__()
        self.a = nn.Conv2d(c, c, 3, padding=d, dilation=d)
        self.b = nn.Conv2d(c, c, 3, padding=d, dilation=d)

    def forward(self, x):
        return x + 0.1 * self.b(F.silu(self.a(x)))

class SharedDecoder(nn.Module):

    def __init__(self, channels=64, aa=True):
        super().__init__()
        self.aa = aa
        self.stem = nn.Conv2d(7, channels, 3, padding=1)
        self.blocks = nn.ModuleList((Block(channels, d) for d in (1, 2, 4, 2)))
        self.head = nn.Conv2d(channels, 1, 3, padding=1)
        kernel = torch.tensor([[1, 2, 1], [2, 4, 2], [1, 2, 1]], dtype=torch.float32) / 16
        self.register_buffer('blur_kernel', kernel[None, None].repeat(channels, 1, 1, 1))

    def forward(self, x):
        h = F.silu(self.stem(x))
        for block in self.blocks:
            h = checkpoint(block, h, use_reentrant=False) if self.training and torch.is_grad_enabled() else block(h)
        h = Bilinear2x.apply(h)
        if self.aa:
            h = F.conv2d(reflect_pad(h, 1), self.blur_kernel, groups=h.shape[1])
        return torch.tanh(self.head(h))

def refine(raw, prior, step_logits, step_observer=None):
    lift = lambda x, f: x.repeat_interleave(f, -2).repeat_interleave(f, -1)
    original = lift(raw, 4)
    o2 = lift(raw, 2)
    state = original
    p = replicate_one(raw)
    dx = (p[..., 1:-1, 2:] - p[..., 1:-1, :-2]) * 0.5
    dy = (p[..., 2:, 1:-1] - p[..., :-2, 1:-1]) * 0.5
    lap = p[..., 1:-1, 2:] + p[..., 1:-1, :-2] + p[..., 2:, 1:-1] + p[..., :-2, 1:-1] - 4 * raw
    mean = F.avg_pool2d(raw, 5, 1, 2, count_include_pad=False)
    fixed = [lift(v, 2) for v in [dx, dy, lap, mean]]
    for i in range(4):
        native = raw + F.avg_pool2d(state - original, 4)
        features = torch.cat([F.avg_pool2d(state, 2), o2, lift(raw - native, 2), *fixed], 1)
        state = (state + 0.25 * torch.sigmoid(step_logits[i]) * prior(features)).clamp(0, 1)
        if step_observer is not None:
            step_observer(i + 1, state.detach().clone())
    return ((raw + F.avg_pool2d(state - original, 4)).clamp(0, 1), state)

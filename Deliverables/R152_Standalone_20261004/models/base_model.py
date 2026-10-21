"""One-pass multi-scale context with independent native-grid boundary stages."""
from __future__ import annotations
import math
from pathlib import Path
import torch
from torch import nn
from torch.nn import functional as F
from torch.utils.checkpoint import checkpoint
from .fullres_psf import FullResPSF

def reflect_pad(x, p):
    if not p:
        return x
    x = torch.cat((x[..., 1:p + 1].flip(-1), x, x[..., -p - 1:-1].flip(-1)), -1)
    return torch.cat((x[..., 1:p + 1, :].flip(-2), x, x[..., -p - 1:-1, :].flip(-2)), -2)

class LocalConv(nn.Conv2d):

    def __init__(self, cin, cout, d=1):
        super().__init__(cin, cout, 3, padding=0, dilation=d)
        self.radius = d

    def forward(self, x):
        return super().forward(reflect_pad(x, self.radius))

class PixelNorm(nn.Module):

    def __init__(self, c):
        super().__init__()
        self.s = nn.Parameter(torch.ones(1, c, 1, 1))
        self.b = nn.Parameter(torch.zeros(1, c, 1, 1))

    def forward(self, x):
        q = x - x.mean(1, keepdim=True)
        return q * torch.rsqrt(q.square().mean(1, keepdim=True) + 0.0001) * self.s + self.b

class Block(nn.Module):

    def __init__(self, c, d=1):
        super().__init__()
        self.a = LocalConv(c, c, d)
        self.na = PixelNorm(c)
        self.z = LocalConv(c, c, d)
        self.nz = PixelNorm(c)

    def forward(self, x):
        return x + 0.1 * self.nz(self.z(F.silu(self.na(self.a(x)))))

class Down(nn.Module):

    def __init__(self, cin, cout):
        super().__init__()
        k = torch.tensor(((1, 2, 1), (2, 4, 2), (1, 2, 1)), dtype=torch.float32) / 16
        self.register_buffer('k', k[None, None].repeat(cin, 1, 1, 1))
        self.p = LocalConv(cin, cout)
        self.n = PixelNorm(cout)

    def forward(self, x):
        return F.silu(self.n(self.p(F.conv2d(reflect_pad(x, 1), self.k, stride=2, groups=x.shape[1]))))

class Up(nn.Module):

    def __init__(self, cin, cout):
        super().__init__()
        k = torch.tensor(((1, 2, 1), (2, 4, 2), (1, 2, 1)), dtype=torch.float32) / 16
        self.register_buffer('k', k[None, None].repeat(cin, 1, 1, 1))
        self.p = LocalConv(cin, cout)
        self.n = PixelNorm(cout)

    def forward(self, x, ref):
        x = F.interpolate(x, size=ref.shape[-2:], mode='bilinear', align_corners=False)
        x = F.conv2d(reflect_pad(x, 1), self.k, groups=x.shape[1])
        return self.n(self.p(x))

class ContextUNet(nn.Module):

    def __init__(self, cfg):
        super().__init__()
        a, b, c = cfg['context_channels']
        o = cfg['context_output_channels']
        self.stem = LocalConv(6, a)
        self.n = PixelNorm(a)
        self.e0 = Block(a)
        self.d1 = Down(a, b)
        self.e1 = Block(b)
        self.d2 = Down(b, c)
        self.mid = Block(c)
        self.u2 = Up(c, b)
        self.p1 = LocalConv(2 * b, b)
        self.n1 = PixelNorm(b)
        self.b1 = Block(b)
        self.u1 = Up(b, a)
        self.p0 = LocalConv(2 * a, a)
        self.n0 = PixelNorm(a)
        self.b0 = Block(a)
        self.head = LocalConv(a, o)
        nn.init.zeros_(self.head.weight)
        nn.init.zeros_(self.head.bias)
        q = torch.tensor([1, 8, 28, 56, 70, 56, 28, 8, 1], dtype=torch.float32) / 256
        k = q[:, None] * q[None, :]
        self.register_buffer('smooth', k[None, None].repeat(o, 1, 1, 1))
        self.dependency_radius = 47

    def forward(self, x):
        e0 = self.e0(F.silu(self.n(self.stem(x))))
        e1 = self.e1(self.d1(e0))
        m = self.mid(self.d2(e1))
        d1 = self.b1(F.silu(self.n1(self.p1(torch.cat((self.u2(m, e1), e1), 1)))))
        d0 = self.b0(F.silu(self.n0(self.p0(torch.cat((self.u1(d1, e0), e0), 1)))))
        v = self.head(d0)
        return F.conv2d(reflect_pad(v, 4), self.smooth, groups=v.shape[1])

class NativeStage(nn.Module):

    def __init__(self, cfg):
        super().__init__()
        c = cfg['native_channels']
        self.checkpoint_blocks = cfg['checkpoint_blocks']
        self.stem = LocalConv(8 + cfg['context_output_channels'], c)
        self.n = PixelNorm(c)
        self.blocks = nn.ModuleList((Block(c, d) for d in cfg['native_dilations']))
        self.head = LocalConv(c, 1)
        nn.init.zeros_(self.head.weight)
        nn.init.zeros_(self.head.bias)
        self.dependency_radius = 2 + 2 * sum(cfg['native_dilations'])

    def forward(self, x):
        h = F.silu(self.n(self.stem(x)))
        for b in self.blocks:
            h = checkpoint(b, h, use_reentrant=False) if self.checkpoint_blocks and self.training and torch.is_grad_enabled() else b(h)
        return self.head(h)

class Model(nn.Module):

    def __init__(self, cfg, root: Path | None=None):
        super().__init__()
        self.cfg = dict(cfg)
        root = Path(root) if root else Path(__file__).resolve().parent.parent
        if cfg['native_stages'] != 3:
            raise ValueError('R148v2 requires three independent native stages')
        self.optics = FullResPSF(root / cfg['psf_bank'])
        self.context = ContextUNet(cfg)
        self.stages = nn.ModuleList((NativeStage(cfg) for _ in range(3)))
        q = cfg['eta_initial'] / cfg['eta_max']
        self.step_logits = nn.Parameter(torch.full((3,), math.log(q / (1 - q))))
        self.context_enabled = True

    def raw_features(self, x):
        p = reflect_pad(x, 1)
        dx = (p[..., 1:-1, 2:] - p[..., 1:-1, :-2]) * 0.5
        dy = (p[..., 2:, 1:-1] - p[..., :-2, 1:-1]) * 0.5
        lap = p[..., 1:-1, 2:] + p[..., 1:-1, :-2] + p[..., 2:, 1:-1] + p[..., :-2, 1:-1] - 4 * x
        mean = F.avg_pool2d(reflect_pad(x, 2), 5, 1)
        return (dx, dy, lap, mean)

    def prepare(self, x, indices):
        fixed = self.raw_features(x)
        cue = x - self.optics.blur(x, indices)
        context = self.context(torch.cat((x, self.cfg['optical_feature_gain'] * cue, *fixed), 1)) if self.context_enabled else torch.zeros((x.shape[0], self.cfg['context_output_channels'], *x.shape[-2:]), device=x.device, dtype=x.dtype)
        return (fixed, cue, context)

    def forward(self, x, psf_indices=None, return_states=False):
        if x.ndim != 4 or x.shape[1] != 1 or x.dtype != torch.float32 or (min(x.shape[-2:]) < 202):
            raise ValueError('Expected FP32 N1HW')
        fixed, cue, context = self.prepare(x, psf_indices)
        z = x
        r = torch.zeros_like(x)
        states = []
        for i, stage in enumerate(self.stages):
            f = torch.cat((z, x, z - x, self.cfg['optical_feature_gain'] * cue, *fixed, self.cfg['context_gain'] * context), 1)
            eta = self.cfg['eta_max'] * torch.sigmoid(self.step_logits[i])
            r = (r + eta * torch.tanh(self.cfg['output_logit_gain'] * stage(f))).clamp(-self.cfg['r_max'], self.cfg['r_max'])
            z = (x + r).clamp(0, 1)
            states.append(z)
        return (z, states) if return_states else z

    def _stage_tiled(self, stage, features):
        core = self.cfg['inference_core']
        halo = self.cfg['inference_halo']
        assert halo >= stage.dependency_radius
        n, c, h, w = features.shape
        assert n == 1
        out = torch.empty((1, 1, h, w), device=features.device)
        for y in range(0, h, core):
            for x in range(0, w, core):
                y1 = min(h, y + core)
                x1 = min(w, x + core)
                a = max(0, y - halo)
                b = min(h, y1 + halo)
                l = max(0, x - halo)
                rr = min(w, x1 + halo)
                v = stage(features[..., a:b, l:rr])
                out[..., y:y1, x:x1] = v[..., y - a:y1 - a, x - l:x1 - l]
        return out

    def forward_tiled(self, x, return_states=False):
        fixed, cue, context = self.prepare(x, None)
        z = x
        r = torch.zeros_like(x)
        states = []
        for i, stage in enumerate(self.stages):
            f = torch.cat((z, x, z - x, self.cfg['optical_feature_gain'] * cue, *fixed, self.cfg['context_gain'] * context), 1)
            delta = self._stage_tiled(stage, f)
            eta = self.cfg['eta_max'] * torch.sigmoid(self.step_logits[i])
            r = (r + eta * torch.tanh(self.cfg['output_logit_gain'] * delta)).clamp(-self.cfg['r_max'], self.cfg['r_max'])
            z = (x + r).clamp(0, 1)
            states.append(z)
        return (z, states) if return_states else z

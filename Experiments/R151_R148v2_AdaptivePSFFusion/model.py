"""R148v2 hybrid model with restored adaptive Fourier PSF fusion."""
from __future__ import annotations

import math
from pathlib import Path

import torch
from torch import nn
from torch.nn import functional as F
from torch.utils.checkpoint import checkpoint

from optical.adaptive_fourier_psf import AdaptiveFourierPSFFusion
from optical.fullres_psf import FullResPSF


def reflect_pad(x, p):
    if not p:
        return x
    x = torch.cat((x[..., 1:p+1].flip(-1), x, x[..., -p-1:-1].flip(-1)), -1)
    return torch.cat((x[..., 1:p+1, :].flip(-2), x, x[..., -p-1:-1, :].flip(-2)), -2)


class LocalConv(nn.Conv2d):
    def __init__(self, cin, cout, d=1):
        super().__init__(cin, cout, 3, padding=0, dilation=d)
        self.radius = d

    def forward(self, x):
        return super().forward(reflect_pad(x, self.radius))


class PixelNorm(nn.Module):
    def __init__(self, channels):
        super().__init__()
        self.scale = nn.Parameter(torch.ones(1, channels, 1, 1))
        self.bias = nn.Parameter(torch.zeros(1, channels, 1, 1))

    def forward(self, x):
        centered = x - x.mean(1, keepdim=True)
        return centered * torch.rsqrt(centered.square().mean(1, keepdim=True) + 1e-4) * self.scale + self.bias


class Block(nn.Module):
    def __init__(self, channels, dilation=1):
        super().__init__()
        self.a = LocalConv(channels, channels, dilation)
        self.na = PixelNorm(channels)
        self.b = LocalConv(channels, channels, dilation)
        self.nb = PixelNorm(channels)

    def forward(self, x):
        return x + 0.1 * self.nb(self.b(F.silu(self.na(self.a(x)))))


class Down(nn.Module):
    def __init__(self, cin, cout):
        super().__init__()
        kernel = torch.tensor(((1, 2, 1), (2, 4, 2), (1, 2, 1)), dtype=torch.float32) / 16
        self.register_buffer("kernel", kernel[None, None].repeat(cin, 1, 1, 1))
        self.projection = LocalConv(cin, cout)
        self.norm = PixelNorm(cout)

    def forward(self, x):
        value = F.conv2d(reflect_pad(x, 1), self.kernel, stride=2, groups=x.shape[1])
        return F.silu(self.norm(self.projection(value)))


class Up(nn.Module):
    def __init__(self, cin, cout):
        super().__init__()
        kernel = torch.tensor(((1, 2, 1), (2, 4, 2), (1, 2, 1)), dtype=torch.float32) / 16
        self.register_buffer("kernel", kernel[None, None].repeat(cin, 1, 1, 1))
        self.projection = LocalConv(cin, cout)
        self.norm = PixelNorm(cout)

    def forward(self, x, reference):
        x = F.interpolate(x, size=reference.shape[-2:], mode="bilinear", align_corners=False)
        x = F.conv2d(reflect_pad(x, 1), self.kernel, groups=x.shape[1])
        return self.norm(self.projection(x))


class ContextUNet(nn.Module):
    def __init__(self, cfg):
        super().__init__()
        a, b, c = cfg["context_channels"]
        out = cfg["context_output_channels"]
        self.stem = LocalConv(6, a)
        self.norm = PixelNorm(a)
        self.enc0 = Block(a)
        self.down1 = Down(a, b)
        self.enc1 = Block(b)
        self.down2 = Down(b, c)
        self.middle = Block(c)
        self.up2 = Up(c, b)
        self.project1 = LocalConv(2*b, b)
        self.norm1 = PixelNorm(b)
        self.dec1 = Block(b)
        self.up1 = Up(b, a)
        self.project0 = LocalConv(2*a, a)
        self.norm0 = PixelNorm(a)
        self.dec0 = Block(a)
        self.head = LocalConv(a, out)
        # The context is a feature carrier rather than a direct image output.
        # A small nonzero start lets PSF supervision reach the encoder on the
        # first update while native-stage output heads still start at zero.
        nn.init.normal_(self.head.weight, mean=0.0, std=1e-3)
        nn.init.zeros_(self.head.bias)
        q = torch.tensor([1, 8, 28, 56, 70, 56, 28, 8, 1], dtype=torch.float32) / 256
        smooth = q[:, None] * q[None, :]
        self.register_buffer("smooth", smooth[None, None].repeat(out, 1, 1, 1))

    def forward(self, x):
        e0 = self.enc0(F.silu(self.norm(self.stem(x))))
        e1 = self.enc1(self.down1(e0))
        middle = self.middle(self.down2(e1))
        d1 = self.dec1(F.silu(self.norm1(self.project1(torch.cat((self.up2(middle, e1), e1), 1)))))
        d0 = self.dec0(F.silu(self.norm0(self.project0(torch.cat((self.up1(d1, e0), e0), 1)))))
        value = self.head(d0)
        return F.conv2d(reflect_pad(value, 4), self.smooth, groups=value.shape[1])


class NativeStage(nn.Module):
    def __init__(self, cfg):
        super().__init__()
        channels = cfg["native_channels"]
        self.checkpoint_blocks = cfg["checkpoint_blocks"]
        self.stem = LocalConv(8 + cfg["context_output_channels"], channels)
        self.norm = PixelNorm(channels)
        self.blocks = nn.ModuleList(Block(channels, dilation) for dilation in cfg["native_dilations"])
        self.head = LocalConv(channels, 1)
        nn.init.zeros_(self.head.weight)
        nn.init.zeros_(self.head.bias)
        self.dependency_radius = 2 + 2 * sum(cfg["native_dilations"])

    def forward(self, x):
        value = F.silu(self.norm(self.stem(x)))
        for block in self.blocks:
            value = checkpoint(block, value, use_reentrant=False) if self.checkpoint_blocks and self.training and torch.is_grad_enabled() else block(value)
        return self.head(value)


class Model(nn.Module):
    def __init__(self, cfg, root: Path | None = None):
        super().__init__()
        self.cfg = dict(cfg)
        root = Path(root) if root else Path(__file__).resolve().parent
        if cfg["native_stages"] != 3:
            raise ValueError("R151 keeps the three independent R148v2 native stages")
        bank = root / cfg["psf_bank"]
        self.optics = FullResPSF(bank)
        self.psf_fusion = AdaptiveFourierPSFFusion(cfg, bank)
        self.context = ContextUNet(cfg)
        self.stages = nn.ModuleList(NativeStage(cfg) for _ in range(3))
        fraction = cfg["eta_initial"] / cfg["eta_max"]
        self.step_logits = nn.Parameter(torch.full((3,), math.log(fraction / (1-fraction))))
        self.context_enabled = True
        self.adaptive_feature_enabled = True
        self.adaptive_direct_enabled = True

    @staticmethod
    def raw_features(x):
        p = reflect_pad(x, 1)
        dx = (p[..., 1:-1, 2:] - p[..., 1:-1, :-2]) * 0.5
        dy = (p[..., 2:, 1:-1] - p[..., :-2, 1:-1]) * 0.5
        lap = p[..., 1:-1, 2:] + p[..., 1:-1, :-2] + p[..., 2:, 1:-1] + p[..., :-2, 1:-1] - 4*x
        mean = F.avg_pool2d(reflect_pad(x, 2), 5, 1)
        return dx, dy, lap, mean

    def base_context(self, x, indices):
        fixed = self.raw_features(x)
        fixed_cue = x - self.optics.blur(x, indices)
        context_input = torch.cat((x, self.cfg["optical_feature_gain"] * fixed_cue, *fixed), 1)
        if self.context_enabled:
            context = self.context(context_input)
        else:
            context = torch.zeros((x.shape[0], self.cfg["context_output_channels"], *x.shape[-2:]), device=x.device, dtype=x.dtype)
        return fixed, fixed_cue, context

    def prepare(self, x, indices):
        fixed, fixed_cue, context = self.base_context(x, indices)
        anchor, adaptive_correction = self.psf_fusion(x, context)
        adaptive_cue = self.cfg["adaptive_feature_gain"] * adaptive_correction if self.adaptive_feature_enabled else torch.zeros_like(x)
        cue = fixed_cue + adaptive_cue
        if not self.adaptive_direct_enabled:
            anchor = x
        return fixed, cue, context, anchor

    def forward(self, x, psf_indices=None, return_states=False):
        if x.ndim != 4 or x.shape[1] != 1 or x.dtype != torch.float32 or min(x.shape[-2:]) < 202:
            raise ValueError("Expected FP32 N1HW input with at least 202 pixels per side")
        if not torch.isfinite(x).all() or x.min() < 0 or x.max() > 1:
            raise ValueError("Input must be finite and normalized to [0,1]")
        fixed, cue, context, anchor = self.prepare(x, psf_indices)
        z = anchor
        residual = (anchor - x).clamp(-self.cfg["r_max"], self.cfg["r_max"])
        states = []
        for i, stage in enumerate(self.stages):
            features = torch.cat((z, x, z-x, self.cfg["optical_feature_gain"]*cue, *fixed, self.cfg["context_gain"]*context), 1)
            delta = stage(features)
            eta = self.cfg["eta_max"] * torch.sigmoid(self.step_logits[i])
            residual = (residual + eta * torch.tanh(self.cfg["output_logit_gain"] * delta)).clamp(-self.cfg["r_max"], self.cfg["r_max"])
            z = (x + residual).clamp(0, 1)
            states.append(z)
        return (z, states) if return_states else z

    def _stage_tiled(self, stage, features):
        core = self.cfg["inference_core"]
        halo = self.cfg["inference_halo"]
        if halo < stage.dependency_radius:
            raise ValueError("Inference halo is smaller than native-stage dependency")
        n, _, height, width = features.shape
        if n != 1:
            raise ValueError("Tiled inference expects one image")
        out = torch.empty((1, 1, height, width), device=features.device, dtype=features.dtype)
        for y0 in range(0, height, core):
            for x0 in range(0, width, core):
                y1, x1 = min(height, y0+core), min(width, x0+core)
                top, bottom = max(0, y0-halo), min(height, y1+halo)
                left, right = max(0, x0-halo), min(width, x1+halo)
                value = stage(features[..., top:bottom, left:right])
                out[..., y0:y1, x0:x1] = value[..., y0-top:y1-top, x0-left:x1-left]
        return out

    def forward_tiled(self, x, return_states=False):
        fixed, cue, context, anchor = self.prepare(x, None)
        z = anchor
        residual = (anchor-x).clamp(-self.cfg["r_max"], self.cfg["r_max"])
        states = []
        for i, stage in enumerate(self.stages):
            features = torch.cat((z, x, z-x, self.cfg["optical_feature_gain"]*cue, *fixed, self.cfg["context_gain"]*context), 1)
            delta = self._stage_tiled(stage, features)
            eta = self.cfg["eta_max"] * torch.sigmoid(self.step_logits[i])
            residual = (residual + eta * torch.tanh(self.cfg["output_logit_gain"]*delta)).clamp(-self.cfg["r_max"], self.cfg["r_max"])
            z = (x+residual).clamp(0, 1)
            states.append(z)
        return (z, states) if return_states else z

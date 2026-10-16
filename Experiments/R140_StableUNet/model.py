"""R140: native-input recurrent U-Net with one V42-style decoder PSF insertion.

This is an untrained architecture prototype. No historical neural checkpoint is loaded.
"""
from __future__ import annotations
import math
from pathlib import Path
import torch
from torch import nn
from torch.nn import functional as F
from torch.utils.checkpoint import checkpoint
from optical.feature import WeakPSFDeconvBlock


def reflect_pad(x: torch.Tensor, p: int) -> torch.Tensor:
    """Deterministic reflect padding without CUDA reflect-pad backward."""
    if p == 0:
        return x
    if min(x.shape[-2:]) <= p:
        raise ValueError("Image smaller than required reflect support")
    x = torch.cat((x[..., 1:p+1].flip(-1), x, x[..., -p-1:-1].flip(-1)), dim=-1)
    return torch.cat((x[..., 1:p+1, :].flip(-2), x, x[..., -p-1:-1, :].flip(-2)), dim=-2)


class LocalConv(nn.Conv2d):
    def __init__(self, input_channels: int, output_channels: int):
        super().__init__(input_channels, output_channels, 3, padding=0)
    def forward(self, x):
        return super().forward(reflect_pad(x, 1))


class PixelChannelNorm(nn.Module):
    """Normalize channels at each pixel without spatial/global statistics."""
    def __init__(self, channels, epsilon=1e-4):
        super().__init__()
        self.scale = nn.Parameter(torch.ones(1,channels,1,1))
        self.bias = nn.Parameter(torch.zeros(1,channels,1,1))
        self.epsilon = float(epsilon)
    def forward(self, x):
        centered = x - x.mean(dim=1,keepdim=True)
        var = centered.square().mean(dim=1,keepdim=True)
        return centered * torch.rsqrt(var+self.epsilon) * self.scale + self.bias


class ResidualBlock(nn.Module):
    def __init__(self, channels: int):
        super().__init__()
        self.a = LocalConv(channels, channels)
        self.na = PixelChannelNorm(channels)
        self.b = LocalConv(channels, channels)
        self.nb = PixelChannelNorm(channels)
    def forward(self, x):
        return x + 0.1 * self.nb(self.b(F.silu(self.na(self.a(x)))))


class BlurDown(nn.Module):
    def __init__(self, input_channels: int, output_channels: int):
        super().__init__()
        base = torch.tensor(((1, 2, 1), (2, 4, 2), (1, 2, 1)), dtype=torch.float32) / 16
        self.register_buffer("kernel", base[None, None].repeat(input_channels, 1, 1, 1))
        self.projection = LocalConv(input_channels, output_channels)
        self.norm = PixelChannelNorm(output_channels)
    def forward(self, x):
        y = F.conv2d(reflect_pad(x, 1), self.kernel, stride=2, groups=x.shape[1])
        return F.silu(self.norm(self.projection(y)))


class ShiftSafeUp(nn.Module):
    def __init__(self, input_channels: int, output_channels: int):
        super().__init__()
        base = torch.tensor(((1, 2, 1), (2, 4, 2), (1, 2, 1)), dtype=torch.float32) / 16
        self.register_buffer("kernel", base[None, None].repeat(input_channels, 1, 1, 1))
        self.projection = LocalConv(input_channels, output_channels)
        self.norm = PixelChannelNorm(output_channels)
    def forward(self, x, reference):
        y = F.interpolate(x, size=reference.shape[-2:], mode="bilinear", align_corners=False)
        y = F.conv2d(reflect_pad(y, 1), self.kernel, groups=y.shape[1])
        return self.norm(self.projection(y))


class UNetRefiner(nn.Module):
    def __init__(self, channels, psf_bank: Path, checkpoint_blocks: bool = True, logit_gain: float = 0.1):
        super().__init__()
        c0, c1, c2, c3 = channels
        self.checkpoint_blocks = bool(checkpoint_blocks)
        self.logit_gain = float(logit_gain)
        self.stem = LocalConv(7, c0)
        self.stem_norm = PixelChannelNorm(c0)
        self.enc0 = ResidualBlock(c0)
        self.down1 = BlurDown(c0, c1)
        self.enc1 = ResidualBlock(c1)
        self.down2 = BlurDown(c1, c2)
        self.enc2 = ResidualBlock(c2)
        self.down3 = BlurDown(c2, c3)
        self.bottleneck = ResidualBlock(c3)
        self.up3 = ShiftSafeUp(c3, c2)
        self.dec2_projection = LocalConv(c2 * 2, c2)
        self.dec2_norm = PixelChannelNorm(c2)
        self.dec2 = ResidualBlock(c2)
        self.up2 = ShiftSafeUp(c2, c1)
        self.dec1_projection = LocalConv(c1 * 2, c1)
        self.dec1_norm = PixelChannelNorm(c1)
        self.dec1 = ResidualBlock(c1)
        self.optics = WeakPSFDeconvBlock(
            in_ch=c1, psf_path=str(psf_bank), k=8, psf_indices=None,
            reg_init=30.0, beta_init=0.02, gating_temp=2.5,
            psf_temp=2.5, entropy_mix=0.0, deconv_mode="clamp",
            trainable_reg=False, lowfreq_ratio=0.25, beta_min=0.0,
            beta_max=0.1, beta_scale_max=0.35,
        )
        # A fresh gate starts as an equal mixture; its weights must be trained.
        nn.init.zeros_(self.optics.gating[-1].weight)
        nn.init.zeros_(self.optics.gating[-1].bias)
        self.optics.set_beta_scale(0.0)
        self.up1 = ShiftSafeUp(c1, c0)
        self.dec0_projection = LocalConv(c0 * 2, c0)
        self.dec0_norm = PixelChannelNorm(c0)
        self.dec0 = ResidualBlock(c0)
        self.head = LocalConv(c0, 1)
        nn.init.zeros_(self.head.weight)
        nn.init.zeros_(self.head.bias)

    def block(self, module, x):
        if self.checkpoint_blocks and self.training and torch.is_grad_enabled():
            return checkpoint(module, x, use_reentrant=False)
        return module(x)

    def forward(self, features, use_optics: bool, trace: bool = False):
        e0 = self.block(self.enc0, F.silu(self.stem_norm(self.stem(features))))
        e1 = self.block(self.enc1, self.down1(e0))
        e2 = self.block(self.enc2, self.down2(e1))
        h = self.block(self.bottleneck, self.down3(e2))
        d2 = self.block(self.dec2, F.silu(self.dec2_norm(self.dec2_projection(torch.cat((self.up3(h, e2), e2), dim=1)))))
        d1 = self.block(self.dec1, F.silu(self.dec1_norm(self.dec1_projection(torch.cat((self.up2(d2, e1), e1), dim=1)))))
        if use_optics:
            d1 = self.optics(d1)  # V42-style y2: one half-resolution decoder insertion.
        d0 = self.block(self.dec0, F.silu(self.dec0_norm(self.dec0_projection(torch.cat((self.up1(d1, e0), e0), dim=1)))))
        logits = self.logit_gain * self.head(d0)
        if trace:
            return logits, {"full_skip": e0.detach(), "half_skip": e1.detach(),
                            "quarter_skip": e2.detach(), "decoder_half": d1.detach()}
        return logits


class Model(nn.Module):
    def __init__(self, cfg, root: Path | None = None):
        super().__init__()
        if cfg["iterations"] != 4 or len(cfg["channels"]) != 4:
            raise ValueError("R140 prototype uses four shared iterations and four U-Net levels")
        if not 0 < cfg["eta_initial"] < cfg["eta_max"] or cfg["r_max"] <= 0:
            raise ValueError("Invalid bounded update")
        self.cfg = dict(cfg)
        root = Path(root) if root is not None else Path(__file__).resolve().parent
        self.refiner = UNetRefiner(cfg["channels"], root / cfg["psf_bank"], cfg.get("checkpoint_blocks", True), cfg.get("output_logit_gain",0.1))
        fraction = cfg["eta_initial"] / cfg["eta_max"]
        self.step_logits = nn.Parameter(torch.full((4,), math.log(fraction / (1 - fraction))))
        self.optical_enabled = True
        self.optical_iteration = 3

    def raw_features(self, x):
        p = reflect_pad(x, 1)
        dx = (p[..., 1:-1, 2:] - p[..., 1:-1, :-2]) * 0.5
        dy = (p[..., 2:, 1:-1] - p[..., :-2, 1:-1]) * 0.5
        lap = p[..., 1:-1, 2:] + p[..., 1:-1, :-2] + p[..., 2:, 1:-1] + p[..., :-2, 1:-1] - 4*x
        mean = F.avg_pool2d(reflect_pad(x, 2), 5, stride=1)
        return dx, dy, lap, mean

    def forward(self, x, trace: bool = False):
        if x.ndim != 4 or x.shape[1] != 1 or x.dtype != torch.float32:
            raise ValueError("Expected FP32 N1HW image")
        if min(x.shape[-2:]) < 202:
            raise ValueError("PSF kernel needs at least 101 pixels at the half-resolution decoder")
        if not torch.isfinite(x).all() or x.min() < 0 or x.max() > 1:
            raise ValueError("Image must be finite and normalized to [0,1]")
        fixed = self.raw_features(x)
        r = torch.zeros_like(x)
        z = x
        states = []
        for i in range(4):
            f = torch.cat((z, x, z-x, *fixed), dim=1)
            use_psf = bool(self.optical_enabled and i == self.optical_iteration and float(self.refiner.optics.beta_scale) > 0)
            result = self.refiner(f, use_psf, trace=trace)
            logits, features = result if trace else (result, None)
            eta = self.cfg["eta_max"] * torch.sigmoid(self.step_logits[i])
            r = (r + eta * torch.tanh(logits)).clamp(-self.cfg["r_max"], self.cfg["r_max"])
            z = (x + r).clamp(0, 1)
            if trace:
                states.append({"iteration": i+1, "output": z.detach(), "residual": r.detach(),
                               "psf_applied": use_psf, "features": features})
        return (z, states) if trace else z

"""Measured optical conditioning, evaluated once per input."""
import math
import torch
from torch import nn
from torch.nn import functional as F
from .operators import reflect_pad

class MeasuredOptics(nn.Module):

    def __init__(self, mean_psf, candidates):
        super().__init__()
        self.register_buffer('mean_psf', mean_psf / mean_psf.sum())
        self.register_buffer('candidates', candidates / candidates.sum((-2, -1), keepdim=True))
        self.gating = nn.Sequential(nn.Linear(4, 8), nn.SiLU(), nn.Linear(8, len(candidates)))
        self.alpha = nn.Parameter(torch.tensor(0.1))
        self.beta = nn.Parameter(torch.tensor(0.02))
        self.reg = 0.0565
        self.last_weights = None

    def otf(self, kernel, h, w):
        kh, kw = kernel.shape
        yy, xx = torch.meshgrid(torch.arange(kh, device=kernel.device), torch.arange(kw, device=kernel.device), indexing='ij')
        cy = (kernel * yy).sum() / kernel.sum()
        cx = (kernel * xx).sum() / kernel.sum()
        padded = F.pad(kernel, (0, w - kw, 0, h - kh))
        H = torch.fft.rfft2(padded)
        fy = torch.fft.fftfreq(h, device=kernel.device)[:, None]
        fx = torch.fft.rfftfreq(w, device=kernel.device)[None, :]
        return H * torch.exp(2j * math.pi * (fy * cy + fx * cx))

    def forward(self, x, enabled=True, trace=False):
        if not enabled:
            return (x, dict(enabled=False))
        pad = max(self.mean_psf.shape) // 2
        if min(x.shape[-2:]) <= pad:
            raise ValueError('Full image needs more optical context')
        xp = reflect_pad(x, pad)
        h, w = xp.shape[-2:]
        X = torch.fft.rfft2(xp)

        def inv(k):
            H = self.otf(k, h, w)
            G = (1 + self.reg) * H.conj() / (H.abs().square() + self.reg)
            return torch.fft.irfft2(X * G, s=(h, w))[..., pad:-pad, pad:-pad]
        mean = inv(self.mean_psf)
        dx = x[..., 1:] - x[..., :-1]
        dy = x[..., 1:, :] - x[..., :-1, :]
        stats = torch.stack([x.mean((1, 2, 3)), x.std((1, 2, 3), unbiased=False), dx.abs().mean((1, 2, 3)), dy.abs().mean((1, 2, 3))], 1)
        weights = torch.softmax(self.gating(stats) / 2.5, 1)
        mix = sum((weights[:, i, None, None, None] * inv(k) for i, k in enumerate(self.candidates)))
        alpha = self.alpha.clamp(0.05, 0.35)
        beta = self.beta.clamp(0.005, 0.1)
        result = (x + alpha * (mean - x) + beta * (mix - x)).clamp(0, 1)
        self.last_weights = weights.detach()
        info = dict(enabled=True, weights=weights, mean_residual=mean - x, adaptive_residual=mix - x, alpha=alpha, beta=beta) if trace else dict(enabled=True)
        return (result, info)

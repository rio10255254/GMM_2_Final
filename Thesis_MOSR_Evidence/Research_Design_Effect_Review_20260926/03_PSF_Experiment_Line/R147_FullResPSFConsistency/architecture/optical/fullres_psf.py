"""Fixed measured-PSF forward model on native image pixels.

The bank mean is used on every image because the previous top-four selector
failed its known-index test. The full-resolution operator is linear, preserves
constant intensity, and puts the kernel center at the FFT origin.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import torch
from torch import nn
from torch.nn import functional as F


def reflect_pad(x: torch.Tensor, width: int) -> torch.Tensor:
    if min(x.shape[-2:]) <= width:
        raise ValueError("Image smaller than PSF reflection support")
    x = torch.cat((x[..., 1:width+1].flip(-1), x,
                   x[..., -width-1:-1].flip(-1)), dim=-1)
    return torch.cat((x[..., 1:width+1, :].flip(-2), x,
                      x[..., -width-1:-1, :].flip(-2)), dim=-2)


class FullResPSF(nn.Module):
    def __init__(self, bank_path: str | Path):
        super().__init__()
        with np.load(bank_path, allow_pickle=False) as z:
            bank = z["all_kernels"].astype(np.float64)
        if bank.shape != (25, 101, 101) or not np.isfinite(bank).all() or (bank < 0).any():
            raise ValueError("Expected 25 finite nonnegative 101x101 measured PSFs")
        kernel = bank.mean(axis=0)
        kernel /= kernel.sum()
        if np.max(np.abs(kernel-kernel[::-1, ::-1])) > 1e-7:
            raise ValueError("The fixed mean PSF must be centrosymmetric")
        self.register_buffer("kernel", torch.from_numpy(kernel.astype(np.float32))[None, None])
        self.register_buffer("bank_count", torch.tensor(25, dtype=torch.int32))
        self._frequency_cache: dict[tuple[int, int, str], torch.Tensor] = {}

    def _apply(self, fn):
        self._frequency_cache.clear()
        return super()._apply(fn)

    def _transfer(self, height: int, width: int, device: torch.device) -> torch.Tensor:
        key = (height, width, str(device))
        previous = self._frequency_cache.get(key)
        if previous is not None:
            return previous
        y = height - 101
        x = width - 101
        if min(y, x) < 0:
            raise ValueError("PSF support exceeds padded image")
        top, left = y//2, x//2
        # Dev/inference can populate this cache before training. Keep the
        # transfer a normal no-grad tensor, never an inference-only tensor.
        with torch.inference_mode(False), torch.no_grad():
            placed = F.pad(self.kernel.to(device=device),
                           (left, x-left, top, y-top))
            # FFT circular convolution requires the physical center at (0,0).
            origin = torch.roll(placed, shifts=(-(top+50), -(left+50)), dims=(-2, -1))
            transfer = torch.fft.rfft2(origin)
        self._frequency_cache[key] = transfer
        return transfer

    def blur(self, image: torch.Tensor) -> torch.Tensor:
        if image.ndim != 4 or image.shape[1] != 1 or image.dtype != torch.float32:
            raise ValueError("Expected FP32 N1HW image")
        padded = reflect_pad(image, 50)
        height, width = padded.shape[-2:]
        transfer = self._transfer(height, width, image.device)
        prediction = torch.fft.irfft2(torch.fft.rfft2(padded)*transfer,
                                      s=(height, width))
        return prediction[..., 50:-50, 50:-50]

    def consistency(self, estimate: torch.Tensor,
                    observation: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
        if estimate.shape != observation.shape:
            raise ValueError("Estimate and observation must share the native grid")
        residual = observation - self.blur(estimate)
        # The mean two-Gaussian PSF is symmetric; this is the interior
        # backprojection of the native-image observation residual.
        backprojection = self.blur(residual)
        return residual, backprojection

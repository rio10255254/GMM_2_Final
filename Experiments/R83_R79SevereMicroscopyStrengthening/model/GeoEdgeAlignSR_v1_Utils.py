# GeoEdgeAlignSR_v1_Utils.py
# Utilities for I/O, padding, subpixel shifting, and phase-preprocessing helpers.
#
# v3.2 critical robustness:
# - Safe type annotations (no import-time NameError)
# - shift_tensor_subpixel supports padding_mode {"border","zeros","reflection"} and return_mask
# - apply_hann_and_mask supports (mask + Hann + remove-mean + std-normalize) with detached stats
#
# NOTE:
# - For training/warping use padding_mode="border" to avoid black-border collapse.
# - For valid-region mask use padding_mode="zeros", return_mask=True.

from __future__ import annotations

import os
from typing import Dict, Tuple, Optional

import numpy as np
import cv2
import torch
import torch.nn.functional as F


# ----------------------------
# Basic I/O
# ----------------------------
def imread_unicode(path: str, flags: int = cv2.IMREAD_UNCHANGED) -> np.ndarray | None:
    try:
        data = np.fromfile(path, dtype=np.uint8)
    except Exception:
        return None
    if data.size == 0:
        return None
    return cv2.imdecode(data, flags)


def imwrite_unicode(path: str, img: np.ndarray) -> bool:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    ext = os.path.splitext(path)[1]
    if not ext:
        ext = ".png"
        path = path + ext
    ok, encoded = cv2.imencode(ext, img)
    if not ok:
        return False
    encoded.tofile(path)
    return True


def read_gray_u8(path: str) -> np.ndarray:
    img = imread_unicode(path, cv2.IMREAD_UNCHANGED)
    if img is None:
        raise FileNotFoundError(path)
    if img.ndim == 3:
        img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    if img.dtype != np.uint8:
        img = img.astype(np.float32)
        img = img - float(img.min())
        mx = float(img.max())
        if mx > 0:
            img = img / mx
        img = (img * 255.0).clip(0, 255).astype(np.uint8)
    return img


def write_gray_u8(path: str, img_u8: np.ndarray) -> None:
    if not imwrite_unicode(path, img_u8):
        raise OSError(f"Failed to write image: {path}")


# ----------------------------
# Padding helpers
# ----------------------------
def pad_to_multiple(x: torch.Tensor, multiple: int = 8, mode: str = "reflect") -> Tuple[torch.Tensor, Tuple[int, int]]:
    """
    x: [B,C,H,W]
    returns: x_pad, (pad_h, pad_w)
    """
    b, c, h, w = x.shape
    pad_h = (multiple - h % multiple) % multiple
    pad_w = (multiple - w % multiple) % multiple
    if pad_h == 0 and pad_w == 0:
        return x, (0, 0)
    x_pad = F.pad(x, (0, pad_w, 0, pad_h), mode=mode)
    return x_pad, (pad_h, pad_w)


def unpad(x: torch.Tensor, pad_h: int, pad_w: int) -> torch.Tensor:
    if pad_h == 0 and pad_w == 0:
        return x
    return x[..., : x.shape[-2] - pad_h, : x.shape[-1] - pad_w]


# ----------------------------
# Subpixel shift (grid_sample)
# ----------------------------
def shift_tensor_subpixel(
    x: torch.Tensor,
    dx: torch.Tensor,
    dy: torch.Tensor,
    *,
    padding_mode: str = "border",
    mode: str = "bilinear",
    align_corners: bool = True,
    return_mask: bool = False,
):
    """
    Subpixel shift using grid_sample.

    x:  [B,C,H,W]
    dx: [B] pixels (positive -> right)
    dy: [B] pixels (positive -> down)

    padding_mode:
      - "border": replicate border (recommended for training warps)
      - "zeros":  zero padding (recommended ONLY for mask computation)
      - "reflection": reflect padding
    return_mask:
      - If True: also returns valid mask [B,1,H,W] indicating pixels originating from inside image.
        This mask is computed by shifting a ones-map with padding_mode="zeros".
    """
    if x.ndim != 4:
        raise ValueError(f"shift_tensor_subpixel expects x as [B,C,H,W], got {tuple(x.shape)}")
    b, c, h, w = x.shape
    device = x.device
    dx = dx.to(device=device, dtype=torch.float32).view(b, 1, 1)
    dy = dy.to(device=device, dtype=torch.float32).view(b, 1, 1)

    # Base grid in [-1,1]
    yy, xx = torch.meshgrid(
        torch.linspace(-1.0, 1.0, h, device=device, dtype=torch.float32),
        torch.linspace(-1.0, 1.0, w, device=device, dtype=torch.float32),
        indexing="ij",
    )
    grid = torch.stack([xx, yy], dim=-1).unsqueeze(0).repeat(b, 1, 1, 1)  # [B,H,W,2]

    # Convert pixel shift to normalized coords
    sx = 2.0 * dx / max(1.0, float(w - 1))
    sy = 2.0 * dy / max(1.0, float(h - 1))

    # grid_sample: output(y,x) samples input at grid(y,x)
    grid[..., 0] = grid[..., 0] - sx
    grid[..., 1] = grid[..., 1] - sy

    y = F.grid_sample(
        x,
        grid,
        mode=mode,
        padding_mode=padding_mode,
        align_corners=align_corners,
    )

    if not return_mask:
        return y

    # Valid mask: shift ones with ZERO padding
    ones = torch.ones((b, 1, h, w), device=device, dtype=torch.float32)
    m = F.grid_sample(
        ones,
        grid,
        mode="nearest",
        padding_mode="zeros",
        align_corners=align_corners,
    )
    # grid_sample with nearest on ones gives {0,1} ideally; keep it clean
    m = (m > 0.5).float()
    return y, m


# ----------------------------
# Edges (Sobel)
# ----------------------------
def sobel_magnitude(x: torch.Tensor) -> torch.Tensor:
    """
    x: [B,1,H,W] expected in [0,1]
    returns: [B,1,H,W]
    """
    if x.ndim != 4 or x.shape[1] != 1:
        raise ValueError(f"sobel_magnitude expects [B,1,H,W], got {tuple(x.shape)}")

    device = x.device
    kx = torch.tensor([[-1., 0., 1.],
                       [-2., 0., 2.],
                       [-1., 0., 1.]], device=device, dtype=torch.float32).view(1, 1, 3, 3)
    ky = torch.tensor([[-1., -2., -1.],
                       [ 0.,  0.,  0.],
                       [ 1.,  2.,  1.]], device=device, dtype=torch.float32).view(1, 1, 3, 3)
    gx = F.conv2d(x, kx, padding=1)
    gy = F.conv2d(x, ky, padding=1)
    mag = torch.sqrt(gx * gx + gy * gy + 1e-12)
    return mag


# ----------------------------
# Phase-preprocessing (Mask + Hann + normalize)
# ----------------------------
_HANN_CACHE: Dict[Tuple[int, int, torch.device], torch.Tensor] = {}


def _hann2d(h: int, w: int, device: torch.device) -> torch.Tensor:
    key = (h, w, device)
    if key in _HANN_CACHE:
        return _HANN_CACHE[key]
    wy = torch.hann_window(h, periodic=False, device=device, dtype=torch.float32)
    wx = torch.hann_window(w, periodic=False, device=device, dtype=torch.float32)
    win = (wy[:, None] * wx[None, :]).view(1, 1, h, w)
    _HANN_CACHE[key] = win
    return win


def apply_hann_and_mask(
    x: torch.Tensor,
    mask: Optional[torch.Tensor] = None,
    *,
    remove_mean: bool = True,
    normalize_std: bool = True,
    eps: float = 1e-6,
    detach_stats: bool = True,
) -> torch.Tensor:
    """
    x:    [B,1,H,W] in [0,1]
    mask: [B,1,H,W] or [B,H,W] or None
      - if provided: multiply x by mask before computing stats

    Operations:
      1) apply mask
      2) optional remove mean (masked mean)
      3) optional normalize by std (masked std)
      4) apply Hann window
    Stats (mean/std) can be detached to avoid DC-collapse gradients.
    """
    if x.ndim != 4 or x.shape[1] != 1:
        raise ValueError(f"apply_hann_and_mask expects [B,1,H,W], got {tuple(x.shape)}")

    B, _, H, W = x.shape
    device = x.device
    y = x

    if mask is not None:
        if mask.ndim == 3:
            mask = mask.unsqueeze(1)
        if mask.shape != (B, 1, H, W):
            raise ValueError(f"mask shape mismatch: expected {(B,1,H,W)}, got {tuple(mask.shape)}")
        y = y * mask
    else:
        mask = torch.ones((B, 1, H, W), device=device, dtype=y.dtype)

    # masked mean/std
    if remove_mean or normalize_std:
        denom = mask.sum(dim=(-2, -1), keepdim=True).clamp_min(1.0)
        mean = (y.sum(dim=(-2, -1), keepdim=True) / denom)
        if detach_stats:
            mean = mean.detach()
        if remove_mean:
            y = y - mean

        if normalize_std:
            var = ((y * mask) ** 2).sum(dim=(-2, -1), keepdim=True) / denom
            std = torch.sqrt(var + eps)
            if detach_stats:
                std = std.detach()
            y = y / std.clamp_min(eps)

    # Hann
    win = _hann2d(H, W, device=device).to(dtype=y.dtype)
    y = y * win
    return y

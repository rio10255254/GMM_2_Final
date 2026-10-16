# GeoEdgeAlignSR_v1_ModelA_v5.py
# Boundary-faithful reconstruction model with translation-equivariance bias.
# NOTE: Added optional "use_sigmoid_output" for better high-frequency learning.
# Default keeps original behavior (sigmoid).

import math
from pathlib import Path
from typing import Optional, Tuple

import numpy as np
import scipy.io
import torch
import torch.nn as nn
from deterministic_ops import functional as F, ReflectPad, BilinearUpsample2x
import torch.fft as fft


class PSFDeconvPhysics(nn.Module):
    '''
    Optional "physics_layer" kept for compatibility with your split-LR & freeze strategy.
    This block is intentionally conservative:
      - PSF-guided Wiener-style inverse filtering in frequency domain
      - small residual strength alpha
    '''
    def __init__(
        self,
        psf_path: str,
        psf_grid_rows: Optional[int] = None,
        psf_grid_cols: Optional[int] = None,
        use_stack_mean: bool = True,
        reg_init: float = 10.0,
        trainable_reg: bool = False,
        alpha_init: float = 0.10,
        alpha_min: float = 0.05,
        alpha_max: float = 0.35,
    ):
        super().__init__()
        if not psf_path:
            raise ValueError("psf_path must be provided for PSF-guided deconvolution.")

        psf_stack, grid_rows, grid_cols = self._load_psf_stack(
            psf_path, psf_grid_rows, psf_grid_cols
        )
        self.psf_grid_rows = grid_rows
        self.psf_grid_cols = grid_cols
        self.use_stack_mean = bool(use_stack_mean)

        psf_tensor = torch.from_numpy(psf_stack).unsqueeze(0)  # [1, N, H, W]
        self.register_buffer("PSFs", psf_tensor)
        self.register_buffer("PSF_mean", psf_tensor.mean(dim=1, keepdim=True))
        self.register_buffer("PSF_center", self._select_center_psf(psf_tensor))

        if trainable_reg:
            self.reg = nn.Parameter(torch.tensor(float(reg_init)))
        else:
            self.register_buffer("reg", torch.tensor(float(reg_init)))

        self.alpha = nn.Parameter(torch.tensor(float(alpha_init)))
        self.alpha_min = float(alpha_min)
        self.alpha_max = float(alpha_max)

    @staticmethod
    def _load_psf_stack(
        psf_path: str,
        grid_rows: Optional[int],
        grid_cols: Optional[int],
    ) -> Tuple[np.ndarray, Optional[int], Optional[int]]:
        path = Path(psf_path)
        if not path.exists():
            raise FileNotFoundError(f"PSF file not found: {path}")

        mat = scipy.io.loadmat(str(path))
        if "psf_grid" in mat:
            psf_grid = mat["psf_grid"]
        elif "fitted_psf" in mat:
            psf_grid = mat["fitted_psf"]
        else:
            keys = [k for k in mat.keys() if not k.startswith("__")]
            raise KeyError(f"Expected 'psf_grid' or 'fitted_psf' in {path}. Found: {keys}")

        if psf_grid.ndim == 4:
            h, w, rows, cols = psf_grid.shape
            psf_stack = psf_grid.reshape(h, w, -1)
            grid_rows = rows if grid_rows is None else grid_rows
            grid_cols = cols if grid_cols is None else grid_cols
        elif psf_grid.ndim == 3:
            psf_stack = psf_grid
        elif psf_grid.ndim == 2:
            psf_stack = psf_grid[:, :, None]
        else:
            raise ValueError(f"Unsupported PSF shape: {psf_grid.shape}")

        psf_stack = np.transpose(psf_stack.astype(np.float32), (2, 0, 1))
        psf_sum = np.sum(psf_stack, axis=(1, 2), keepdims=True)
        psf_sum[psf_sum == 0] = 1.0
        psf_stack /= psf_sum
        return psf_stack, grid_rows, grid_cols

    def _select_center_psf(self, psf_tensor: torch.Tensor) -> torch.Tensor:
        n = psf_tensor.shape[1]
        if self.psf_grid_rows and self.psf_grid_cols:
            if n == int(self.psf_grid_rows) * int(self.psf_grid_cols):
                row = int(self.psf_grid_rows) // 2
                col = int(self.psf_grid_cols) // 2
                center_idx = row * int(self.psf_grid_cols) + col
                return psf_tensor[:, center_idx:center_idx+1, :, :]
        center_idx = n // 2
        return psf_tensor[:, center_idx:center_idx+1, :, :]

    def _select_psf(self, psf_rc: Optional[Tuple[int, int]]) -> torch.Tensor:
        if psf_rc is None:
            return self.PSF_mean if self.use_stack_mean else self.PSF_center
        if self.psf_grid_rows is None or self.psf_grid_cols is None:
            raise ValueError("psf_rc provided but psf_grid_rows/cols are not set.")
        row, col = psf_rc
        idx = int(row) * int(self.psf_grid_cols) + int(col)
        return self.PSFs[:, idx:idx+1, :, :]

    def _get_reg(self, device: torch.device) -> torch.Tensor:
        reg = torch.clamp(self.reg, min=1e-6)
        return reg.to(device=device, dtype=torch.float32)

    def forward(self, x: torch.Tensor, psf_rc: Optional[Tuple[int, int]] = None) -> torch.Tensor:
        psf = self._select_psf(psf_rc)
        b, c, h, w = x.shape
        _, _, ph, pw = psf.shape
        if ph > h or pw > w:
            raise ValueError(f"PSF size {ph}x{pw} exceeds input size {h}x{w}.")

        pad_w = w - pw
        pad_h = h - ph
        pad_l = pad_w // 2
        pad_r = pad_w - pad_l
        pad_t = pad_h // 2
        pad_b = pad_h - pad_t

        x_dtype = x.dtype
        x_float = x.float()
        with torch.cuda.amp.autocast(enabled=False):
            psf_pad = F.pad(
                psf.to(device=x.device, dtype=torch.float32),
                (int(pad_l), int(pad_r), int(pad_t), int(pad_b)),
                mode="constant",
                value=0.0,
            )
            psf_f = fft.rfft2(psf_pad)
            img_f = fft.rfft2(x_float)
            reg = self._get_reg(x.device)
            denom = torch.conj(psf_f) * psf_f + reg + 1e-6
            g = torch.conj(psf_f) / denom
            deconv = fft.irfft2(img_f * g, s=(h, w))

        deconv = torch.clamp(deconv, min=-100.0, max=100.0)
        deconv = deconv + 1e-6

        alpha = torch.clamp(self.alpha, min=self.alpha_min, max=self.alpha_max).to(device=x.device, dtype=torch.float32)
        out = x_float + alpha * (deconv - x_float)
        return out.to(dtype=x_dtype)


DepthwiseDeblurPhysics = PSFDeconvPhysics


class WeakPSFDeconvBlock(nn.Module):
    '''
    Weak PSF mixing deconvolution block (single injection):
      - selects K representative fitted PSFs (K=4 or 8)
      - softmax gating over K deconvolved features
      - conservative residual mixing with small beta
    '''
    def __init__(
        self,
        in_ch: int,
        psf_path: str,
        psf_grid_rows: Optional[int] = None,
        psf_grid_cols: Optional[int] = None,
        psf_indices: Optional[Tuple[int, ...]] = None,
        k: int = 4,
        reg_init: float = 30.0,
        beta_init: float = 0.02,
        gating_temp: float = 1.5,
        psf_temp: Optional[float] = None,
        entropy_mix: float = 0.0,
        deconv_mode: str = "clamp",
        trainable_reg: bool = False,
        lowfreq_ratio: float = 0.25,
        beta_min: float = 0.0,
        beta_max: float = 0.10,
        beta_scale_max: float = 0.8,
    ):
        super().__init__()
        if k not in (4, 8):
            raise ValueError("WeakPSFDeconvBlock supports k=4 or k=8 only.")
        if not psf_path:
            raise ValueError("psf_path must be provided for WeakPSFDeconvBlock.")

        psf_stack, grid_rows, grid_cols = PSFDeconvPhysics._load_psf_stack(
            psf_path, psf_grid_rows, psf_grid_cols
        )
        self.psf_grid_rows = grid_rows
        self.psf_grid_cols = grid_cols
        self.k = int(k)

        indices = self._select_psf_indices(psf_stack.shape[0], psf_indices)
        self.psf_indices = tuple(indices)

        psf_sel = psf_stack[indices, :, :]
        psf_tensor = torch.from_numpy(psf_sel).unsqueeze(0)  # [1, K, H, W]
        self.register_buffer("PSFs", psf_tensor)

        hidden = max(8, int(in_ch // 4))
        self.gating = nn.Sequential(
            nn.AdaptiveAvgPool2d(1),
            nn.Conv2d(in_ch, hidden, kernel_size=1, padding=0, bias=True),
            nn.SiLU(),
            nn.Conv2d(hidden, self.k, kernel_size=1, padding=0, bias=True),
        )
        if deconv_mode not in ("clamp", "abs"):
            raise ValueError("deconv_mode must be 'clamp' or 'abs'.")
        self.deconv_mode = deconv_mode
        self.beta = nn.Parameter(torch.tensor(float(beta_init)))
        self.register_buffer("beta_scale", torch.tensor(1.0))
        temp = gating_temp if psf_temp is None else psf_temp
        self.register_buffer("psf_temp", torch.tensor(float(temp)))
        self.gating_temp = self.psf_temp
        self.register_buffer("entropy_mix", torch.tensor(float(entropy_mix)))
        self.register_buffer("lowfreq_ratio", torch.tensor(float(lowfreq_ratio)))
        self.register_buffer("beta_scale_max", torch.tensor(float(beta_scale_max)))
        self.beta_min = float(beta_min)
        self.beta_max = float(beta_max)

        if trainable_reg:
            self.reg = nn.Parameter(torch.tensor(float(reg_init)))
        else:
            self.register_buffer("reg", torch.tensor(float(reg_init)))

        self.last_entropy = float("nan")
        self.last_top1_ratio = float("nan")
        self.last_beta = float("nan")
        self.last_bypass = True
        self.last_logits_mean = float("nan")
        self.last_weight_mean = float("nan")
        self._top1_tensor = None
        self._entropy_tensor = None

    def _select_psf_indices(self, n_psf: int, psf_indices: Optional[Tuple[int, ...]]):
        if psf_indices is not None:
            if len(psf_indices) != self.k:
                raise ValueError(f"psf_indices must have length {self.k}.")
            if min(psf_indices) < 0 or max(psf_indices) >= n_psf:
                raise ValueError("psf_indices out of range.")
            return list(psf_indices)

        if self.psf_grid_rows and self.psf_grid_cols and n_psf == int(self.psf_grid_rows) * int(self.psf_grid_cols):
            rows = int(self.psf_grid_rows)
            cols = int(self.psf_grid_cols)
            def idx(r, c):
                return int(r) * cols + int(c)
            candidates = [
                idx(rows // 2, cols // 2),
                idx(0, 0),
                idx(0, cols - 1),
                idx(rows - 1, 0),
                idx(rows - 1, cols - 1),
                idx(0, cols // 2),
                idx(rows - 1, cols // 2),
                idx(rows // 2, 0),
                idx(rows // 2, cols - 1),
            ]
            indices = []
            for i in candidates:
                if i not in indices:
                    indices.append(i)
                if len(indices) >= self.k:
                    break
            if len(indices) < self.k:
                for i in range(n_psf):
                    if i not in indices:
                        indices.append(i)
                    if len(indices) >= self.k:
                        break
            return indices[:self.k]

        if n_psf <= 0:
            raise ValueError("Empty PSF stack.")
        if n_psf == 1:
            return [0] * self.k
        lin = np.linspace(0, n_psf - 1, num=self.k)
        indices = [int(round(v)) for v in lin.tolist()]
        return indices

    def set_beta_scale(self, value: float):
        self.beta_scale.fill_(float(value))

    def set_gating_temp(self, value: float):
        self.set_psf_temp(value)

    def set_psf_temp(self, value: float):
        self.psf_temp.fill_(float(value))

    def set_entropy_mix(self, value: float):
        self.entropy_mix.fill_(float(value))

    def set_lowfreq_ratio(self, value: float):
        self.lowfreq_ratio.fill_(float(value))

    def entropy_loss(self, weight: float = 1.0):
        if self._entropy_tensor is None:
            return None
        return -float(weight) * self._entropy_tensor

    def collapse_loss(self, weight: float, r_max: float, h_min: float):
        if self._top1_tensor is None or self._entropy_tensor is None:
            return None
        penalty = torch.relu(self._top1_tensor - float(r_max)) ** 2 + torch.relu(float(h_min) - self._entropy_tensor) ** 2
        return float(weight) * penalty

    def _get_reg(self, device: torch.device) -> torch.Tensor:
        reg = torch.clamp(self.reg, min=1e-6)
        return reg.to(device=device, dtype=torch.float32)

    def _lowfreq_mask(self, h: int, w: int, device: torch.device) -> torch.Tensor:
        ratio = float(torch.clamp(self.lowfreq_ratio, min=0.0, max=1.0).item())
        if ratio >= 1.0:
            return torch.ones((h, w // 2 + 1), device=device, dtype=torch.float32)
        if ratio <= 0.0:
            return torch.zeros((h, w // 2 + 1), device=device, dtype=torch.float32)
        fy = torch.fft.fftfreq(h, d=1.0, device=device).unsqueeze(1)
        fx = torch.fft.rfftfreq(w, d=1.0, device=device).unsqueeze(0)
        rad = torch.sqrt(fy * fy + fx * fx) / 0.5
        return (rad <= ratio).to(dtype=torch.float32)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        x_dtype = x.dtype
        x_float = x.float()
        b, c, h, w = x.shape

        psf = self.PSFs.to(device=x.device, dtype=torch.float32)
        _, _, ph, pw = psf.shape
        if ph > h or pw > w:
            self.last_entropy = self.last_top1_ratio = float("nan")
            self.last_beta = 0.0
            self.last_bypass = True
            self._entropy_tensor = self._top1_tensor = None
            return x

        logits = self.gating(x).view(b, self.k)
        temp = max(float(self.psf_temp.item()), 1e-6)
        weights = torch.softmax(logits / temp, dim=1).float()
        mix = float(self.entropy_mix.item())
        if mix > 0.0:
            weights = weights * (1.0 - mix) + mix / float(self.k)

        ent = -(weights * torch.log(weights + 1e-6)).sum(dim=1).mean()
        self._entropy_tensor = ent
        self.last_entropy = float(ent.detach().item())
        top1 = weights.max(dim=1).values.mean()
        self._top1_tensor = top1
        self.last_top1_ratio = float(top1.detach().item())
        self.last_logits_mean = float(logits.mean().detach().item())
        self.last_weight_mean = float(weights.mean().detach().item())

        pad_w = w - pw
        pad_h = h - ph
        pad_l = pad_w // 2
        pad_r = pad_w - pad_l
        pad_t = pad_h // 2
        pad_b = pad_h - pad_t

        f_psf = x_float.new_zeros((b, c, h, w))
        with torch.cuda.amp.autocast(enabled=False):
            img_f = fft.rfft2(x_float)
            reg = self._get_reg(x.device)
            lf_mask = self._lowfreq_mask(h, w, x.device)
            for k_idx in range(self.k):
                psf_k = psf[:, k_idx:k_idx+1, :, :]
                psf_pad = F.pad(
                    psf_k,
                    (int(pad_l), int(pad_r), int(pad_t), int(pad_b)),
                    mode="constant",
                    value=0.0,
                )
                psf_f = fft.rfft2(psf_pad)
                denom = torch.conj(psf_f) * psf_f + reg + 1e-6
                g = torch.conj(psf_f) / denom
                filt = g * lf_mask + (1.0 - lf_mask)
                deconv = fft.irfft2(img_f * filt, s=(h, w))
                if self.deconv_mode == "abs":
                    deconv = torch.abs(deconv)
                    deconv = torch.clamp(deconv, min=0.0, max=100.0)
                else:
                    deconv = torch.clamp(deconv, min=-100.0, max=100.0)
                w_k = weights[:, k_idx].view(b, 1, 1, 1)
                f_psf = f_psf + w_k.float() * deconv

        beta_scale = torch.clamp(self.beta_scale, min=0.0, max=float(self.beta_scale_max.item()))
        beta = torch.clamp(self.beta, min=self.beta_min, max=self.beta_max) * beta_scale
        beta = beta.to(device=x.device, dtype=torch.float32)
        self.last_beta = float(beta.item())
        self.last_bypass = (-1e-12 <= self.last_beta <= 1e-12)

        out = x_float + beta * (f_psf - x_float)
        return out.to(dtype=x_dtype)


class ConvBlock(nn.Module):
    def __init__(self, c_in: int, c_out: int, k: int = 3, act: bool = True):
        super().__init__()
        p = k // 2
        self.conv = nn.Conv2d(c_in, c_out, k, padding=p)
        self.gn = nn.GroupNorm(num_groups=min(8, c_out), num_channels=c_out)
        self.act = nn.SiLU() if act else nn.Identity()

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.act(self.gn(self.conv(x)))


class ResBlock(nn.Module):
    def __init__(self, c: int):
        super().__init__()
        self.b1 = ConvBlock(c, c, 3, act=True)
        self.b2 = ConvBlock(c, c, 3, act=False)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return F.silu(x + self.b2(self.b1(x)))


class UpsampleConv(nn.Module):
    def __init__(self, c_in: int, c_out: int):
        super().__init__()
        self.up = BilinearUpsample2x()
        self.conv = nn.Conv2d(c_in, c_out, 3, padding=1, bias=True)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.conv(self.up(x))


class ShiftSafeUpsample(nn.Module):
    """
    Decoupled Upsampling: Bilinear Interpolate -> Depthwise Anti-Aliasing Blur -> Conv

    When learnable_blur=True (A1), the depthwise blur kernel is initialized to
    the same Gaussian but allowed to train, enabling the model to learn
    scale-appropriate anti-aliasing instead of fixed blurring.
    """
    def __init__(self, in_ch: int, out_ch: int, kernel_size: int = 3,
                 learnable_blur: bool = False):
        super().__init__()
        self.up = BilinearUpsample2x()
        self.pad = ReflectPad(1)
        self.blur = nn.Conv2d(in_ch, in_ch, 3, stride=1, padding=0, groups=in_ch, bias=False)
        blur_k = torch.tensor(
            [[1, 2, 1], [2, 4, 2], [1, 2, 1]], dtype=torch.float32
        ) / 16.0
        blur_k = blur_k.view(1, 1, 3, 3).repeat(in_ch, 1, 1, 1)
        with torch.no_grad():
            self.blur.weight.copy_(blur_k)
        self.blur.weight.requires_grad = learnable_blur
        self.conv = nn.Conv2d(in_ch, out_ch, kernel_size, padding=kernel_size // 2)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.conv(self.blur(self.pad(self.up(x))))


class SqueezeExcitation(nn.Module):
    """Squeeze-Excitation channel attention (A5).
    Placed after bottleneck to capture global geometric consistency."""
    def __init__(self, channels: int, reduction: int = 4):
        super().__init__()
        mid = max(channels // reduction, 8)
        self.fc = nn.Sequential(
            nn.AdaptiveAvgPool2d(1),
            nn.Flatten(),
            nn.Linear(channels, mid),
            nn.SiLU(inplace=True),
            nn.Linear(mid, channels),
            nn.Sigmoid(),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        w = self.fc(x).unsqueeze(-1).unsqueeze(-1)
        return x * w


class RawAnchorOutputAdapter(nn.Module):
    """Keep raw low-frequency position while allowing bounded reconstruction detail."""
    def __init__(
        self,
        mode: str = "none",
        alpha: float = 0.10,
        sigma: float = 2.0,
        detail_gain: float = 0.35,
    ):
        super().__init__()
        if mode not in {"none", "blend", "detail"}:
            raise ValueError("mode must be none, blend, or detail")
        if not 0.0 <= float(alpha) <= 1.0:
            raise ValueError("alpha must be between 0 and 1")
        if float(sigma) <= 0.0:
            raise ValueError("sigma must be positive")
        self.mode = str(mode)
        self.alpha = float(alpha)
        self.sigma = float(sigma)
        self.detail_gain = float(detail_gain)

    def _gaussian_blur(self, x: torch.Tensor) -> torch.Tensor:
        sigma = max(float(self.sigma), 1e-6)
        radius = max(1, int(math.ceil(3.0 * sigma)))
        k = 2 * radius + 1
        coords = torch.arange(k, device=x.device, dtype=x.dtype) - radius
        kernel_1d = torch.exp(-(coords * coords) / (2.0 * sigma * sigma))
        kernel_1d = kernel_1d / kernel_1d.sum().clamp_min(1e-12)
        c = int(x.shape[1])
        ky = kernel_1d.view(1, 1, k, 1).repeat(c, 1, 1, 1)
        kx = kernel_1d.view(1, 1, 1, k).repeat(c, 1, 1, 1)
        pad_mode = "reflect" if x.shape[-2] > radius and x.shape[-1] > radius else "replicate"
        y = F.pad(x, (0, 0, radius, radius), mode=pad_mode)
        y = F.conv2d(y, ky, groups=c)
        y = F.pad(y, (radius, radius, 0, 0), mode=pad_mode)
        return F.conv2d(y, kx, groups=c)

    def forward(self, raw: torch.Tensor, pred: torch.Tensor) -> torch.Tensor:
        if raw.shape != pred.shape:
            raise ValueError(f"shape mismatch: raw={tuple(raw.shape)} pred={tuple(pred.shape)}")
        if self.mode == "none":
            return pred
        raw_f = raw.float()
        pred_f = pred.float()
        if self.mode == "blend":
            out = (1.0 - self.alpha) * raw_f + self.alpha * pred_f
        else:
            pred_low = self._gaussian_blur(pred_f)
            pred_high = pred_f - pred_low
            out = raw_f + self.detail_gain * pred_high
            out = out + (raw_f.mean(dim=(-2, -1), keepdim=True) - out.mean(dim=(-2, -1), keepdim=True))
        return torch.clamp(out, 0.0, 1.0).to(dtype=pred.dtype)


class BoundaryResidualAdapter(nn.Module):
    """Small local correction head initialized as an exact no-op."""
    def __init__(
        self,
        feature_ch: int,
        hidden_ch: int = 16,
        max_residual: float = 0.025,
        gate_bias: float = -2.0,
        delta_bias: bool = True,
        zero_mean_delta: bool = False,
        edge_gate_enable: bool = False,
        polarity_split: bool = False,
        orientation_inputs: bool = False,
    ):
        super().__init__()
        hidden_ch = max(4, int(hidden_ch))
        self.zero_mean_delta = bool(zero_mean_delta)
        self.edge_gate_enable = bool(edge_gate_enable)
        self.polarity_split = bool(polarity_split)
        self.orientation_inputs = bool(orientation_inputs)
        self.register_buffer("max_residual", torch.tensor(float(max_residual)))
        sobel_x = torch.tensor(
            [[-1, 0, 1], [-2, 0, 2], [-1, 0, 1]], dtype=torch.float32
        ).view(1, 1, 3, 3) / 8.0
        sobel_y = torch.tensor(
            [[-1, -2, -1], [0, 0, 0], [1, 2, 1]], dtype=torch.float32
        ).view(1, 1, 3, 3) / 8.0
        self.register_buffer("_sobel_x", sobel_x, persistent=False)
        self.register_buffer("_sobel_y", sobel_y, persistent=False)
        extra_ch = 3 if self.orientation_inputs else 0
        self.body = nn.Sequential(
            nn.Conv2d(feature_ch + 1 + extra_ch, hidden_ch, 3, padding=1),
            nn.SiLU(inplace=True),
            nn.Conv2d(hidden_ch, hidden_ch, 3, padding=1),
            nn.SiLU(inplace=True),
        )
        self.gate = nn.Conv2d(hidden_ch, 1, 1)
        delta_modes = 2 if self.polarity_split else 1
        self.delta = nn.Conv2d(hidden_ch, delta_modes, 1, bias=bool(delta_bias))
        if self.polarity_split:
            self.polarity_gate = nn.Conv2d(hidden_ch, 2, 1)
            nn.init.zeros_(self.polarity_gate.weight)
            nn.init.zeros_(self.polarity_gate.bias)
        else:
            self.polarity_gate = None
        nn.init.zeros_(self.delta.weight)
        if self.delta.bias is not None:
            nn.init.zeros_(self.delta.bias)
        nn.init.zeros_(self.gate.weight)
        nn.init.constant_(self.gate.bias, float(gate_bias))

    def _fixed_edge_gate(self, base_out: torch.Tensor) -> torch.Tensor:
        x = base_out.float()
        kx = self._sobel_x.to(device=x.device, dtype=x.dtype)
        ky = self._sobel_y.to(device=x.device, dtype=x.dtype)
        gx = F.conv2d(x, kx, padding=1)
        gy = F.conv2d(x, ky, padding=1)
        mag = torch.sqrt(gx * gx + gy * gy + 1e-12)
        denom = torch.amax(mag, dim=(-2, -1), keepdim=True).clamp_min(1e-6)
        return (mag / denom).clamp(0.0, 1.0).to(dtype=base_out.dtype)

    def _orientation_features(self, base_out: torch.Tensor) -> torch.Tensor:
        x = base_out.float()
        kx = self._sobel_x.to(device=x.device, dtype=x.dtype)
        ky = self._sobel_y.to(device=x.device, dtype=x.dtype)
        gx = F.conv2d(x, kx, padding=1)
        gy = F.conv2d(x, ky, padding=1)
        mag = torch.sqrt(gx * gx + gy * gy + 1e-12)
        norm = mag.clamp_min(1e-6)
        nx = gx / norm
        ny = gy / norm
        mag_norm = mag / torch.amax(mag, dim=(-2, -1), keepdim=True).clamp_min(1e-6)
        return torch.cat([nx, ny, mag_norm.clamp(0.0, 1.0)], dim=1).to(dtype=base_out.dtype)

    def forward(self, features: torch.Tensor, base_out: torch.Tensor) -> torch.Tensor:
        body_inputs = [features, base_out]
        if self.orientation_inputs:
            body_inputs.append(self._orientation_features(base_out))
        h = self.body(torch.cat(body_inputs, dim=1))
        gate = torch.sigmoid(self.gate(h))
        if self.edge_gate_enable:
            gate = gate * self._fixed_edge_gate(base_out)
        delta_logits = self.delta(h)
        if self.zero_mean_delta:
            delta_logits = delta_logits - delta_logits.mean(dim=(-2, -1), keepdim=True)
        delta = torch.tanh(delta_logits) * self.max_residual.to(device=base_out.device, dtype=base_out.dtype)
        if self.polarity_split:
            mix = torch.softmax(self.polarity_gate(h), dim=1)
            delta = torch.sum(delta * mix, dim=1, keepdim=True)
        return torch.clamp(base_out + gate * delta, 0.0, 1.0)


class ImageQualityGate(nn.Module):
    """SNR-inspired scalar gate for conservative output residual scaling."""

    def __init__(
        self,
        in_ch: int = 1,
        hidden_ch: int = 8,
        scale_min: float = 0.75,
        scale_max: float = 1.08,
    ):
        super().__init__()
        self.scale_min = float(scale_min)
        self.scale_max = float(scale_max)
        hidden_ch = max(2, int(hidden_ch))
        self.offset = nn.Sequential(
            nn.Conv2d(1, hidden_ch, 1),
            nn.SiLU(),
            nn.Conv2d(hidden_ch, 1, 1),
        )
        nn.init.zeros_(self.offset[-1].weight)
        nn.init.zeros_(self.offset[-1].bias)
        self.last_quality_score: Optional[torch.Tensor] = None

    @staticmethod
    def estimate_quality_score(x: torch.Tensor) -> torch.Tensor:
        x_f = x.float().clamp(0.0, 1.0)
        b, c, _, _ = x_f.shape
        sobel_x = torch.tensor(
            [[-1, 0, 1], [-2, 0, 2], [-1, 0, 1]],
            dtype=torch.float32,
            device=x_f.device,
        ).view(1, 1, 3, 3) / 8.0
        sobel_y = sobel_x.transpose(-1, -2)
        sobel_x = sobel_x.repeat(c, 1, 1, 1)
        sobel_y = sobel_y.repeat(c, 1, 1, 1)
        gx = F.conv2d(x_f, sobel_x, padding=1, groups=c)
        gy = F.conv2d(x_f, sobel_y, padding=1, groups=c)
        mag = torch.sqrt(gx * gx + gy * gy + 1e-8)

        flat_mag = mag.flatten(2)
        k = max(1, int(flat_mag.shape[-1] * 0.05))
        signal = torch.topk(flat_mag, k=k, dim=-1).values.mean(dim=-1, keepdim=True)
        signal = signal.mean(dim=1, keepdim=True).view(b, 1, 1, 1)

        local_mean = F.avg_pool2d(x_f, kernel_size=5, stride=1, padding=2)
        high = torch.abs(x_f - local_mean)
        mag_mean = mag.mean(dim=(-2, -1), keepdim=True)
        interior_weight = torch.exp(-8.0 * mag / (mag_mean + 1e-6)).detach()
        noise = (high * interior_weight).sum(dim=(-2, -1), keepdim=True)
        noise = noise / (interior_weight.sum(dim=(-2, -1), keepdim=True) + 1e-6)
        noise = noise.mean(dim=1, keepdim=True)

        score = signal / (signal + 3.0 * noise + 1e-6)
        return score.clamp(0.0, 1.0)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        base_score = self.estimate_quality_score(x)
        learned_offset = 0.20 * torch.tanh(self.offset(base_score))
        quality = (base_score + learned_offset).clamp(0.0, 1.0)
        self.last_quality_score = quality.detach()
        scale = self.scale_min + (self.scale_max - self.scale_min) * quality
        return scale.to(dtype=x.dtype)


class GeoEdgeAlignSR_v1_v5_NoCoord(nn.Module):
    '''
    Practical U-like encoder-decoder designed to preserve boundary geometry:
      - conservative inductive bias (no aggressive sharpening by default)
      - optional physics_layer (trainable, can be frozen early)

    Update (minimal):
      - allow bypassing sigmoid at output for better high-frequency learning.
        You can clamp outside the model for stability.
    '''
    def __init__(
        self,
        in_ch: int = 1,
        base: int = 48,
        use_physics_layer: bool = True,
        use_sigmoid_output: bool = True,
        use_upsample_conv: bool = True,
        use_band_limit: bool = False,
        band_limit_cutoff: float = 0.95,
        band_limit_order: float = 8.0,
        psf_fitted_path: Optional[str] = None,
        psf_grid_rows: Optional[int] = None,
        psf_grid_cols: Optional[int] = None,
        psf_use_stack_mean: bool = True,
        psf_deconv_reg: float = 10.0,
        psf_phys_alpha_init: float = 0.10,
        psf_phys_trainable_reg: bool = False,
        psf_phys_alpha_min: float = 0.05,
        psf_phys_alpha_max: float = 0.35,
        weak_psf_enable: bool = True,
        weak_psf_k: int = 4,
        weak_psf_indices: Optional[Tuple[int, ...]] = None,
        weak_psf_reg: float = 30.0,
        weak_psf_beta_init: float = 0.02,
        weak_psf_gating_temp: float = 1.5,
        weak_psf_psf_temp: Optional[float] = None,
        weak_psf_entropy_mix: float = 0.0,
        weak_psf_deconv_mode: str = "clamp",
        weak_psf_inject: str = "y2",
        weak_psf_trainable_reg: bool = False,
        weak_psf_lowfreq_ratio: float = 0.25,
        weak_psf_beta_min: float = 0.0,
        weak_psf_beta_max: float = 0.10,
        weak_psf_beta_scale_max: float = 0.8,
        # A1: learnable anti-aliasing blur in ShiftSafeUpsample
        learnable_blur: bool = False,
        # A5: Squeeze-Excitation attention after bottleneck
        use_bottleneck_se: bool = False,
        bottleneck_se_reduction: int = 4,
        boundary_residual_adapter_enable: bool = False,
        boundary_residual_adapter_hidden: int = 16,
        boundary_residual_adapter_max: float = 0.025,
        boundary_residual_adapter_gate_bias: float = -2.0,
        boundary_residual_adapter_delta_bias: bool = True,
        boundary_residual_adapter_zero_mean: bool = False,
        boundary_residual_adapter_edge_gate: bool = False,
        boundary_residual_adapter_polarity_split: bool = False,
        boundary_residual_adapter_orientation_inputs: bool = False,
        raw_anchor_output_mode: str = "none",
        raw_anchor_output_alpha: float = 0.10,
        raw_anchor_output_sigma: float = 2.0,
        raw_anchor_output_detail_gain: float = 0.35,
        quality_gate_enable: bool = False,
        quality_gate_hidden: int = 8,
        quality_gate_scale_min: float = 0.75,
        quality_gate_scale_max: float = 1.08,
    ):
        super().__init__()
        self.use_physics_layer = bool(use_physics_layer)
        self.use_sigmoid_output = bool(use_sigmoid_output)
        self.use_upsample_conv = bool(use_upsample_conv)
        self.use_band_limit = bool(use_band_limit)
        self.learnable_blur = bool(learnable_blur)
        self.use_bottleneck_se = bool(use_bottleneck_se)
        self.boundary_residual_adapter_enable = bool(boundary_residual_adapter_enable)
        self.raw_anchor_output_mode = str(raw_anchor_output_mode)
        self.quality_gate_enable = bool(quality_gate_enable)
        self.last_quality_gate: Optional[torch.Tensor] = None

        if use_physics_layer:
            self.physics_layer = DepthwiseDeblurPhysics(
                psf_path=psf_fitted_path,
                psf_grid_rows=psf_grid_rows,
                psf_grid_cols=psf_grid_cols,
                use_stack_mean=psf_use_stack_mean,
                reg_init=psf_deconv_reg,
                trainable_reg=psf_phys_trainable_reg,
                alpha_init=psf_phys_alpha_init,
                alpha_min=psf_phys_alpha_min,
                alpha_max=psf_phys_alpha_max,
            )
        else:
            self.physics_layer = nn.Identity()

        if weak_psf_inject not in ("y2", "y1"):
            raise ValueError("weak_psf_inject must be 'y2' or 'y1'.")
        self.weak_psf_inject = weak_psf_inject

        if weak_psf_enable:
            self.weak_psf_block = WeakPSFDeconvBlock(
                in_ch=base,
                psf_path=psf_fitted_path,
                psf_grid_rows=psf_grid_rows,
                psf_grid_cols=psf_grid_cols,
                psf_indices=weak_psf_indices,
                k=weak_psf_k,
                reg_init=weak_psf_reg,
                beta_init=weak_psf_beta_init,
                gating_temp=weak_psf_gating_temp,
                psf_temp=weak_psf_psf_temp,
                entropy_mix=weak_psf_entropy_mix,
                deconv_mode=weak_psf_deconv_mode,
                trainable_reg=weak_psf_trainable_reg,
                lowfreq_ratio=weak_psf_lowfreq_ratio,
                beta_min=weak_psf_beta_min,
                beta_max=weak_psf_beta_max,
                beta_scale_max=weak_psf_beta_scale_max,
            )
        else:
            self.weak_psf_block = None

        if self.use_band_limit:
            self.band_limit = OpticalBandpassFilter(
                cutoff_ratio=band_limit_cutoff,
                order=band_limit_order,
            )
        else:
            self.band_limit = nn.Identity()

        # Encoder
        self.e1 = nn.Sequential(ConvBlock(in_ch, base), ResBlock(base))
        self.d1 = nn.Conv2d(base, base, 3, stride=2, padding=1)

        self.e2 = nn.Sequential(ConvBlock(base, base * 2), ResBlock(base * 2))
        self.d2 = nn.Conv2d(base * 2, base * 2, 3, stride=2, padding=1)

        self.e3 = nn.Sequential(ConvBlock(base * 2, base * 4), ResBlock(base * 4))
        self.d3 = nn.Conv2d(base * 4, base * 4, 3, stride=2, padding=1)

        # Bottleneck
        self.mid = nn.Sequential(
            ConvBlock(base * 4, base * 4),
            ResBlock(base * 4),
            ResBlock(base * 4)
        )

        # A5: Optional SE attention after bottleneck
        if use_bottleneck_se:
            self.mid_se = SqueezeExcitation(base * 4, reduction=bottleneck_se_reduction)
        else:
            self.mid_se = None

        # Decoder
        self.u3 = ShiftSafeUpsample(base * 4, base * 2, learnable_blur=learnable_blur)
        self.p3 = nn.Sequential(ConvBlock(base * 2 + base * 4, base * 2), ResBlock(base * 2))

        self.u2 = ShiftSafeUpsample(base * 2, base, learnable_blur=learnable_blur)
        self.p2 = nn.Sequential(ConvBlock(base + base * 2, base), ResBlock(base))

        self.u1 = ShiftSafeUpsample(base, base, learnable_blur=learnable_blur)
        self.p1 = nn.Sequential(ConvBlock(base + base, base), ResBlock(base))

        self.out = nn.Conv2d(base, 1, 1)
        if self.boundary_residual_adapter_enable:
            self.boundary_adapter = BoundaryResidualAdapter(
                feature_ch=base,
                hidden_ch=boundary_residual_adapter_hidden,
                max_residual=boundary_residual_adapter_max,
                gate_bias=boundary_residual_adapter_gate_bias,
                delta_bias=boundary_residual_adapter_delta_bias,
                zero_mean_delta=boundary_residual_adapter_zero_mean,
                edge_gate_enable=boundary_residual_adapter_edge_gate,
                polarity_split=boundary_residual_adapter_polarity_split,
                orientation_inputs=boundary_residual_adapter_orientation_inputs,
            )
        else:
            self.boundary_adapter = None
        self.raw_anchor_output = RawAnchorOutputAdapter(
            mode=raw_anchor_output_mode,
            alpha=raw_anchor_output_alpha,
            sigma=raw_anchor_output_sigma,
            detail_gain=raw_anchor_output_detail_gain,
        )
        if self.quality_gate_enable:
            self.quality_gate = ImageQualityGate(
                in_ch=in_ch,
                hidden_ch=quality_gate_hidden,
                scale_min=quality_gate_scale_min,
                scale_max=quality_gate_scale_max,
            )
        else:
            self.quality_gate = None

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        x0 = self.physics_layer(x)
        f1 = self.e1(x0)          # [B, base, H, W]
        x1 = self.d1(f1)          # [B, base, H/2, W/2]

        f2 = self.e2(x1)          # [B, 2b, H/2, W/2]
        x2 = self.d2(f2)          # [B, 2b, H/4, W/4]

        f3 = self.e3(x2)          # [B, 4b, H/4, W/4]
        x3 = self.d3(f3)          # [B, 4b, H/8, W/8]

        m = self.mid(x3)
        if self.mid_se is not None:
            m = self.mid_se(m)

        y3 = self.u3(m)           # [B, 2b, H/4, W/4]
        y3 = self.p3(torch.cat([y3, f3], dim=1))

        y2 = self.u2(y3)          # [B, b, H/2, W/2]
        y2 = self.p2(torch.cat([y2, f2], dim=1))
        if self.weak_psf_block is not None and self.weak_psf_inject == "y2":
            y2 = self.weak_psf_block(y2)

        y1 = self.u1(y2)          # [B, b, H, W]
        y1 = self.p1(torch.cat([y1, f1], dim=1))
        if self.weak_psf_block is not None and self.weak_psf_inject == "y1":
            y1 = self.weak_psf_block(y1)

        out = self.out(y1)
        out = self.band_limit(out)

        if self.use_sigmoid_output:
            out = torch.sigmoid(out)

        if self.boundary_adapter is not None:
            out = self.boundary_adapter(y1, out)

        out = self.raw_anchor_output(x, out)
        if self.quality_gate is not None:
            scale = self.quality_gate(x)
            self.last_quality_gate = self.quality_gate.last_quality_score
            out = torch.clamp(x + scale * (out - x), 0.0, 1.0)
        else:
            self.last_quality_gate = None
        return out


class OpticalBandpassFilter(nn.Module):
    """
    Simulates the physical optical cutoff (MTF) to prevent aliasing and
    non-physical high-frequency artifacts that confuse PM algorithms.
    """
    def __init__(self, cutoff_ratio: float = 0.95, order: float = 8.0):
        super().__init__()
        self.cutoff_ratio = float(cutoff_ratio)
        self.order = float(order)
        self.register_buffer("filter_mask", None)

    def _get_mask(self, h: int, w: int, device: torch.device) -> torch.Tensor:
        target_shape = (h, w // 2 + 1)
        if (self.filter_mask is not None) and (self.filter_mask.shape[-2:] == target_shape):
            return self.filter_mask

        fy = torch.fft.fftfreq(h, d=1.0, device=device).unsqueeze(1)
        fx = torch.fft.rfftfreq(w, d=1.0, device=device).unsqueeze(0)
        rho = torch.sqrt(fy * fy + fx * fx) * 2.0
        cutoff = max(self.cutoff_ratio, 1e-6)
        mask = 1.0 / (1.0 + (rho / cutoff) ** (2.0 * self.order))
        self.filter_mask = mask[None, None, ...]
        return self.filter_mask

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        if not self.training:
            return x

        _, _, h, w = x.shape
        x_dtype = x.dtype
        x_float = x.float()
        mask = self._get_mask(h, w, x.device)
        fft_x = torch.fft.rfft2(x_float)
        filtered_fft = fft_x * mask
        out = torch.fft.irfft2(filtered_fft, s=(h, w))
        return out.to(dtype=x_dtype)

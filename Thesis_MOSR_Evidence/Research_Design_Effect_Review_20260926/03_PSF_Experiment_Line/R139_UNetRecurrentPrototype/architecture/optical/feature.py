"""V42 WeakPSFDeconvBlock unchanged; only the bank reader supports the supplied25-PSF NPZ."""
from pathlib import Path
from typing import Optional,Tuple
import numpy as np
import torch
from torch import nn
import torch.nn.functional as F
import torch.fft as fft
class PSFDeconvPhysics:
 @staticmethod
 def _load_psf_stack(psf_path,grid_rows,grid_cols):
  if grid_rows is not None or grid_cols is not None:raise ValueError('No spatial grid is inferred in this copy')
  with np.load(psf_path,allow_pickle=False) as z:
   if 'all_kernels' not in z.files:raise ValueError('NPZ must contain all_kernels')
   a=z['all_kernels']
   if a.dtype.kind not in 'fiu' or a.shape!=(25,101,101):raise ValueError('Expected25 real101x101 PSFs')
   a=a.astype(np.float32)
  if not np.isfinite(a).all() or (a<0).any():raise ValueError('PSFs must be finite and nonnegative')
  sums=a.sum((1,2),keepdims=True)
  if not np.isfinite(sums).all() or (sums<=0).any():raise ValueError('Each PSF needs a finite positive sum')
  return a/sums,None,None

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

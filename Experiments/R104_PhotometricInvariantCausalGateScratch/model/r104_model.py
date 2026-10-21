"""R104 prototype: R103 backbone plus causal gates and invariant shape cues."""
from __future__ import annotations

from dataclasses import dataclass
import math

import torch
from torch import nn
import torch.nn.functional as F


def _safe_pad(x: torch.Tensor, amount: int) -> torch.Tensor:
    mode = "reflect" if x.shape[-2] > amount and x.shape[-1] > amount else "replicate"
    return F.pad(x, (amount, amount, amount, amount), mode=mode)


class SeparableBinomialBlur(nn.Module):
    def __init__(self, channels: int, size: int):
        super().__init__()
        if size < 3 or size % 2 == 0:
            raise ValueError("blur size must be odd and at least 3")
        row = torch.tensor([math.comb(size - 1, index) for index in range(size)], dtype=torch.float32)
        row /= row.sum()
        self.channels = int(channels)
        self.size = int(size)
        self.register_buffer("horizontal", row.view(1, 1, 1, size).repeat(channels, 1, 1, 1))
        self.register_buffer("vertical", row.view(1, 1, size, 1).repeat(channels, 1, 1, 1))

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        radius = self.size // 2
        mode = "reflect" if x.shape[-2] > radius and x.shape[-1] > radius else "replicate"
        y = F.conv2d(
            F.pad(x, (radius, radius, 0, 0), mode=mode),
            self.horizontal.to(dtype=x.dtype), groups=self.channels,
        )
        y = F.conv2d(
            F.pad(y, (0, 0, radius, radius), mode=mode),
            self.vertical.to(dtype=x.dtype), groups=self.channels,
        )
        return y


class ConvBlock(nn.Module):
    def __init__(self, c_in: int, c_out: int, dilation: int = 1, activate: bool = True):
        super().__init__()
        self.conv = nn.Conv2d(c_in, c_out, 3, padding=dilation, dilation=dilation)
        self.act = nn.SiLU() if activate else nn.Identity()

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.act(self.conv(x))


class ResBlock(nn.Module):
    def __init__(self, channels: int, dilation: int = 1):
        super().__init__()
        self.a = ConvBlock(channels, channels, dilation=dilation)
        self.b = ConvBlock(channels, channels, dilation=dilation, activate=False)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return F.silu(x + self.b(self.a(x)))


class LocalCues(nn.Module):
    """Raw-amplitude and local-relative cues remain separate and observable."""

    raw_channels = 13
    invariant_channels = 5

    def __init__(self):
        super().__init__()
        self.blur3 = SeparableBinomialBlur(1, 3)
        self.blur9 = SeparableBinomialBlur(1, 9)
        self.blur33 = SeparableBinomialBlur(1, 33)
        self.blur65 = SeparableBinomialBlur(1, 65)
        sobel = torch.tensor([[-1, 0, 1], [-2, 0, 2], [-1, 0, 1]], dtype=torch.float32) / 8.0
        self.register_buffer("sobel_x", sobel.view(1, 1, 3, 3))
        self.register_buffer("sobel_y", sobel.t().contiguous().view(1, 1, 3, 3))

    def forward(self, x: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
        b3, b9, b33, b65 = self.blur3(x), self.blur9(x), self.blur33(x), self.blur65(x)
        gx = F.conv2d(_safe_pad(x, 1), self.sobel_x.to(dtype=x.dtype))
        gy = F.conv2d(_safe_pad(x, 1), self.sobel_y.to(dtype=x.dtype))
        gradient = torch.sqrt(gx.square() + gy.square() + 1e-8)
        centered = x - b33
        local_scale = torch.sqrt(self.blur33(centered.square()) + (2.0 / 255.0) ** 2)
        normalized = (centered / (2.5 * local_scale + 2.0 / 255.0)).clamp(-1.0, 1.0)
        relative = (x / (b33 + 8.0 / 255.0) - 1.0).clamp(-1.0, 1.0)
        relative_gx = (gx / (2.5 * local_scale + 2.0 / 255.0)).clamp(-1.0, 1.0)
        relative_gy = (gy / (2.5 * local_scale + 2.0 / 255.0)).clamp(-1.0, 1.0)
        fine_relative = ((b3 - b9) / (2.0 * local_scale + 2.0 / 255.0)).clamp(-1.0, 1.0)
        long_centered = b33 - b65
        long_scale = torch.sqrt(self.blur65((x - b65).square()) + (2.0 / 255.0) ** 2)
        long_relative = (long_centered / (2.5 * long_scale + 2.0 / 255.0)).clamp(-1.0, 1.0)
        inverse = (x + 0.7 * (x - b9)).clamp(0.0, 1.0)
        raw = torch.cat([
            x, b3, b9, b33, b65, x - b3, x - b9,
            gx, gy, gradient, normalized, relative, inverse,
        ], dim=1)
        invariant = torch.cat([
            normalized, relative_gx, relative_gy, fine_relative, long_relative,
        ], dim=1)
        return raw, invariant


class AntiAliasDown(nn.Module):
    def __init__(self, c_in: int, c_out: int):
        super().__init__()
        self.blur = SeparableBinomialBlur(c_in, 3)
        self.conv = nn.Conv2d(c_in, c_out, 3, stride=2, padding=1)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.conv(self.blur(x))


class ShiftSafeUp(nn.Module):
    def __init__(self, c_in: int, c_out: int):
        super().__init__()
        self.blur = SeparableBinomialBlur(c_in, 3)
        self.conv = nn.Conv2d(c_in, c_out, 3, padding=1)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.conv(self.blur(F.interpolate(x, scale_factor=2, mode="bilinear", align_corners=False)))


class ParallelDilatedBody(nn.Module):
    def __init__(self, channels: int):
        super().__init__()
        branch = max(8, channels // 2)
        self.a = ConvBlock(channels, branch, dilation=1)
        self.b = ConvBlock(channels, branch, dilation=2)
        self.c = ConvBlock(channels, branch, dilation=3)
        self.merge = nn.Sequential(ConvBlock(branch * 3, channels), ResBlock(channels))

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.merge(torch.cat([self.a(x), self.b(x), self.c(x)], dim=1))


@dataclass
class R104Details:
    output: torch.Tensor
    low_proposal: torch.Tensor
    low_gate: torch.Tensor
    low_delta: torch.Tensor
    illumination_proposal: torch.Tensor
    illumination_gate: torch.Tensor
    illumination_delta: torch.Tensor
    contour_proposal: torch.Tensor
    texture_proposal: torch.Tensor
    contour_gate: torch.Tensor
    texture_gate: torch.Tensor
    contour_delta: torch.Tensor
    texture_delta: torch.Tensor
    signed_distance: torch.Tensor
    total_delta: torch.Tensor


class PhotometricInvariantCausalGateMOSR(nn.Module):
    alignment_multiple = 8
    minimum_halo_px = 160

    def __init__(
        self,
        base: int = 32,
        low_bound: float = 0.14,
        illumination_bound: float = 0.12,
        contour_bound: float = 0.18,
        texture_bound: float = 0.16,
        combined_bound: float = 0.38,
        gate_initial_probability: float = 0.12,
    ):
        super().__init__()
        self.base = int(base)
        self.low_bound = float(low_bound)
        self.illumination_bound = float(illumination_bound)
        self.contour_bound = float(contour_bound)
        self.texture_bound = float(texture_bound)
        self.combined_bound = float(combined_bound)
        self.cues = LocalCues()

        self.e1 = nn.Sequential(ConvBlock(LocalCues.raw_channels, base), ResBlock(base))
        self.d1 = AntiAliasDown(base, base * 2)
        self.e2 = nn.Sequential(ConvBlock(base * 2, base * 2), ResBlock(base * 2))
        self.d2 = AntiAliasDown(base * 2, base * 4)
        self.e3 = nn.Sequential(ConvBlock(base * 4, base * 4), ResBlock(base * 4))
        self.d3 = AntiAliasDown(base * 4, base * 4)
        self.mid = nn.Sequential(
            ResBlock(base * 4, dilation=1), ResBlock(base * 4, dilation=2), ResBlock(base * 4, dilation=3)
        )
        self.u3 = ShiftSafeUp(base * 4, base * 2)
        self.p3 = nn.Sequential(ConvBlock(base * 6, base * 2), ResBlock(base * 2))
        self.u2 = ShiftSafeUp(base * 2, base)
        self.p2 = nn.Sequential(ConvBlock(base * 3, base), ResBlock(base))
        self.u1 = ShiftSafeUp(base, base)
        self.p1 = nn.Sequential(ConvBlock(base * 2, base), ResBlock(base))

        invariant_width = max(12, base // 2)
        self.invariant_body = nn.Sequential(
            ConvBlock(LocalCues.invariant_channels, invariant_width),
            ResBlock(invariant_width, dilation=2),
            ResBlock(invariant_width, dilation=4),
        )
        self.shape_body = nn.Sequential(ConvBlock(invariant_width, base), ResBlock(base, dilation=2))
        self.proposal_fusion = nn.Sequential(ConvBlock(base * 2, base), ResBlock(base))
        self.gate_context = nn.Sequential(ConvBlock(base, base, dilation=2), ResBlock(base, dilation=3))

        self.low_body = nn.Sequential(ConvBlock(base, base), ResBlock(base))
        self.low_head = nn.Conv2d(base, 1, 1)
        self.low_gate_head = nn.Conv2d(base, 1, 1)
        self.illumination_body = nn.Sequential(ConvBlock(base, base), ResBlock(base, dilation=2))
        self.illumination_head = nn.Conv2d(base, 1, 1)
        self.illumination_gate_head = nn.Conv2d(base, 1, 1)

        self.contour_body = ParallelDilatedBody(base)
        self.contour_head = nn.Conv2d(base, 1, 1)
        self.contour_gate_head = nn.Conv2d(base, 1, 1)
        self.texture_body = ParallelDilatedBody(base)
        self.texture_head = nn.Conv2d(base, 1, 1)
        self.texture_gate_head = nn.Conv2d(base, 1, 1)
        self.sdf_body = nn.Sequential(ConvBlock(base, base), ResBlock(base, dilation=2))
        self.sdf_head = nn.Conv2d(base, 1, 1)

        self.blur3 = SeparableBinomialBlur(1, 3)
        self.blur5 = SeparableBinomialBlur(1, 5)
        self.blur9 = SeparableBinomialBlur(1, 9)
        self.blur17 = SeparableBinomialBlur(1, 17)
        self.blur65 = SeparableBinomialBlur(1, 65)
        self._initialize_heads(float(gate_initial_probability))

    def _initialize_heads(self, gate_probability: float) -> None:
        for head in (
            self.low_head, self.illumination_head, self.contour_head,
            self.texture_head,
        ):
            nn.init.normal_(head.weight, mean=0.0, std=0.0015)
            nn.init.zeros_(head.bias)
        nn.init.normal_(self.sdf_head.weight, mean=0.0, std=0.00035)
        nn.init.zeros_(self.sdf_head.bias)
        gate_bias = math.log(gate_probability / max(1.0 - gate_probability, 1e-6))
        for head in (
            self.low_gate_head, self.illumination_gate_head,
            self.contour_gate_head, self.texture_gate_head,
        ):
            nn.init.zeros_(head.weight)
            nn.init.constant_(head.bias, gate_bias)

    def _features(self, raw: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        raw_cues, invariant_cues = self.cues(raw)
        f1 = self.e1(raw_cues)
        f2 = self.e2(self.d1(f1))
        f3 = self.e3(self.d2(f2))
        mid = self.mid(self.d3(f3))
        y3 = self.p3(torch.cat([self.u3(mid), f3], dim=1))
        y2 = self.p2(torch.cat([self.u2(y3), f2], dim=1))
        features = self.p1(torch.cat([self.u1(y2), f1], dim=1))
        invariant = self.invariant_body(invariant_cues)
        shape_features = self.shape_body(invariant)
        proposal_features = self.proposal_fusion(torch.cat([features, shape_features], dim=1))
        return features, shape_features, proposal_features

    def _forward_aligned(self, x: torch.Tensor) -> R104Details:
        raw = x.clamp(0.0, 1.0)
        features, shape_features, proposal_features = self._features(raw)

        gate_features = self.gate_context(shape_features)

        low_logits = self.low_head(self.low_body(features))
        low_proposal = self.low_bound * torch.tanh(self.blur9(low_logits))
        low_gate = 1.15 * torch.sigmoid(self.low_gate_head(gate_features))
        low_delta = low_gate * low_proposal

        illumination_logits = self.illumination_head(self.illumination_body(proposal_features))
        # The training target has no arbitrary global exposure correction, so a
        # directly supervised smooth proposal can represent broad gradients.
        # A difference-of-blurs would annihilate the very slow fields that
        # caused R103's uneven-illumination failure.
        illumination_proposal = self.illumination_bound * torch.tanh(self.blur17(illumination_logits))
        illumination_gate = 1.15 * torch.sigmoid(self.illumination_gate_head(gate_features))
        illumination_delta = illumination_gate * illumination_proposal

        contour_features = self.contour_body(proposal_features)
        contour_logits = torch.tanh(self.contour_head(contour_features))
        contour_proposal = self.contour_bound * (contour_logits - self.blur3(contour_logits))
        contour_gate = 1.15 * torch.sigmoid(self.contour_gate_head(gate_features))
        contour_delta = contour_gate * contour_proposal

        texture_features = self.texture_body(proposal_features)
        texture_logits = torch.tanh(self.texture_head(texture_features))
        texture_proposal = self.texture_bound * (texture_logits - self.blur5(texture_logits))
        texture_gate = 1.15 * torch.sigmoid(self.texture_gate_head(gate_features))
        texture_delta = texture_gate * texture_proposal

        signed_distance = 24.0 * torch.tanh(self.sdf_head(self.sdf_body(shape_features)))
        total = low_delta + illumination_delta + contour_delta + texture_delta
        total = self.combined_bound * torch.tanh(total / max(self.combined_bound, 1e-6))
        output = (raw + total).clamp(0.0, 1.0)
        return R104Details(
            output, low_proposal, low_gate, low_delta,
            illumination_proposal, illumination_gate, illumination_delta,
            contour_proposal, texture_proposal,
            contour_gate, texture_gate, contour_delta, texture_delta, signed_distance, total,
        )

    def forward_details(self, x: torch.Tensor) -> R104Details:
        h, w = x.shape[-2:]
        pad_h, pad_w = (-h) % self.alignment_multiple, (-w) % self.alignment_multiple
        if pad_h or pad_w:
            mode = "reflect" if h > pad_h and w > pad_w else "replicate"
            details = self._forward_aligned(F.pad(x, (0, pad_w, 0, pad_h), mode=mode))
            values = [getattr(details, field)[..., :h, :w] for field in details.__dataclass_fields__]
            return R104Details(*values)
        return self._forward_aligned(x)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.forward_details(x).output


def build_model(base: int = 32, **kwargs: float) -> PhotometricInvariantCausalGateMOSR:
    return PhotometricInvariantCausalGateMOSR(base=base, **kwargs)


def count_parameters(model: nn.Module) -> int:
    return sum(parameter.numel() for parameter in model.parameters())

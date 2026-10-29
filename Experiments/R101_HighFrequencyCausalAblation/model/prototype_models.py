"""A/B/C prototype models for the R101 causal high-frequency experiment."""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import torch
from torch import nn
import torch.nn.functional as F
PROJECT_ROOT = Path(__file__).resolve().parents[3]


R100_PATH = Path(str(PROJECT_ROOT / 'Experiments/R100_CausalOperatorScratch/model/r100_model.py'))


def _load_r100():
    spec = importlib.util.spec_from_file_location("r101_r100_reference", R100_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load R100 reference model: {R100_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


R100 = _load_r100()


class PrototypeNet(R100.CausalOperatorNet):
    """R100 operator with arm-specific weak-edge support and boundary renderer."""

    def __init__(self, arm: str, base: int = 16):
        super().__init__(base=base)
        self.arm = str(arm).upper()
        if self.arm not in {"A", "B", "C"}:
            raise ValueError(f"Unknown arm: {arm}")
        self.multi_scale_edge_support = self.arm in {"B", "C"}
        self.subpixel_boundary_renderer = self.arm == "C"
        self.renderer_scale = 4
        if self.subpixel_boundary_renderer:
            self.renderer_head = nn.Sequential(
                R100.ConvAct(base + 6, base),
                R100.ResidualBlock(base, scale=0.08),
                nn.Conv2d(base, 3, 1),
            )
            nn.init.zeros_(self.renderer_head[-1].weight)
            with torch.no_grad():
                self.renderer_head[-1].bias.copy_(torch.tensor([0.0, -2.4, -2.0]))
            self.renderer_blur = R100.FixedFilter(R100._binomial_kernel(17))

    @staticmethod
    def _gradient_coherence(
        gx_a: torch.Tensor,
        gy_a: torch.Tensor,
        mag_a: torch.Tensor,
        gx_b: torch.Tensor,
        gy_b: torch.Tensor,
        mag_b: torch.Tensor,
    ) -> torch.Tensor:
        cosine = (gx_a * gx_b + gy_a * gy_b) / (mag_a * mag_b + 1e-6)
        return cosine.clamp(0.0, 1.0)

    def _edge_support(
        self,
        b3: torch.Tensor,
        b7: torch.Tensor,
        b15: torch.Tensor,
    ) -> tuple[torch.Tensor, tuple[torch.Tensor, ...]]:
        gx3, gy3, mag3 = self.optical.gradients(b3)
        gx7, gy7, mag7 = self.optical.gradients(b7)
        gx15, gy15, mag15 = self.optical.gradients(b15)
        if not self.multi_scale_edge_support:
            support = mag15.square() / (mag15.square() + 0.012 ** 2)
            support = self.blur5(support).clamp(0.0, 1.0)
            return support, (gx3, gy3, mag3, gx7, gy7, mag7, gx15, gy15, mag15)

        coherence_37 = self._gradient_coherence(gx3, gy3, mag3, gx7, gy7, mag7)
        coherence_715 = self._gradient_coherence(gx7, gy7, mag7, gx15, gy15, mag15)
        fine = (mag3.square() / (mag3.square() + 0.0065 ** 2)) * coherence_37
        medium = (mag7.square() / (mag7.square() + 0.0085 ** 2)) * torch.sqrt(coherence_37 * coherence_715 + 1e-6)
        coarse = mag15.square() / (mag15.square() + 0.012 ** 2)
        support = 1.0 - (1.0 - fine.clamp(0.0, 1.0)) * (1.0 - medium.clamp(0.0, 1.0)) * (1.0 - coarse.clamp(0.0, 1.0))
        support = self.blur3(support).clamp(0.0, 1.0)
        return support, (gx3, gy3, mag3, gx7, gy7, mag7, gx15, gy15, mag15)

    def _render_boundary(
        self,
        denoised: torch.Tensor,
        features: torch.Tensor,
        even_cues: torch.Tensor,
        edge_support: torch.Tensor,
        gx7: torch.Tensor,
        gy7: torch.Tensor,
        mag7: torch.Tensor,
    ) -> tuple[torch.Tensor, dict[str, torch.Tensor]]:
        parameters = self.blur7(self.renderer_head(torch.cat([features, even_cues], dim=1)))
        normal_offset_px = 0.40 * torch.tanh(parameters[:, 0:1])
        width_strength = 1.50 * torch.sigmoid(parameters[:, 1:2])
        render_blend = torch.sigmoid(parameters[:, 2:3])
        nx = gx7 / (mag7 + 1e-5)
        ny = gy7 / (mag7 + 1e-5)

        scale = self.renderer_scale
        high = F.interpolate(denoised, scale_factor=scale, mode="bilinear", align_corners=False)
        high_h, high_w = high.shape[-2:]
        nx_high = F.interpolate(nx, size=(high_h, high_w), mode="bilinear", align_corners=False)
        ny_high = F.interpolate(ny, size=(high_h, high_w), mode="bilinear", align_corners=False)
        offset_high = F.interpolate(normal_offset_px, size=(high_h, high_w), mode="bilinear", align_corners=False) * scale
        support_high = F.interpolate(edge_support, size=(high_h, high_w), mode="bilinear", align_corners=False)
        strength_high = F.interpolate(width_strength, size=(high_h, high_w), mode="bilinear", align_corners=False)

        grid_y = torch.linspace(-1.0, 1.0, high_h, device=high.device, dtype=high.dtype)
        grid_x = torch.linspace(-1.0, 1.0, high_w, device=high.device, dtype=high.dtype)
        yy, xx = torch.meshgrid(grid_y, grid_x, indexing="ij")
        grid = torch.stack([xx, yy], dim=-1).unsqueeze(0).expand(high.shape[0], -1, -1, -1).clone()
        grid[..., 0] -= (offset_high[:, 0] * nx_high[:, 0]) * (2.0 / max(high_w - 1, 1))
        grid[..., 1] -= (offset_high[:, 0] * ny_high[:, 0]) * (2.0 / max(high_h - 1, 1))
        shifted = F.grid_sample(high, grid, mode="bilinear", padding_mode="reflection", align_corners=True)
        high_band = shifted - self.renderer_blur(shifted)
        rendered_high = torch.clamp(shifted + support_high * strength_high * high_band, 0.0, 1.0)
        rendered = F.avg_pool2d(rendered_high, scale, stride=scale)
        blend = (edge_support * render_blend).clamp(0.0, 1.0)
        edge_base = torch.clamp(denoised * (1.0 - blend) + rendered * blend, 0.0, 1.0)
        return edge_base, {
            "normal_offset_px": normal_offset_px,
            "width_strength": width_strength,
            "render_blend": render_blend,
            "renderer_delta": edge_base - denoised,
        }

    def _forward_aligned(self, x: torch.Tensor) -> dict[str, torch.Tensor]:
        if self.arm == "A":
            details = super()._forward_aligned(x)
            zero = torch.zeros_like(details["output"])
            details.update(normal_offset_px=zero, width_strength=zero, render_blend=zero, renderer_delta=zero)
            return details

        raw = x.clamp(0.0, 1.0)
        features = self._aligned_features(raw)
        radiometry_small = self.radiometry_head(F.avg_pool2d(features, 4, stride=4))
        radiometry_params = F.interpolate(radiometry_small, size=raw.shape[-2:], mode="bilinear", align_corners=False)
        radiometry_params = self.blur17(radiometry_params)
        gain_delta = 0.22 * torch.tanh(radiometry_params[:, :1])
        bias_delta = 0.16 * torch.tanh(radiometry_params[:, 1:2])
        radiometry = torch.clamp(raw * (1.0 + gain_delta) + bias_delta, 0.0, 1.0)
        low_delta = radiometry - raw

        b3, b7, b15 = self.blur3(radiometry), self.blur7(radiometry), self.blur15(radiometry)
        edge_support, gradients = self._edge_support(b3, b7, b15)
        gx3, gy3, mag3, gx7, gy7, mag7, gx15, gy15, mag15 = gradients
        material_support = (1.0 - edge_support).square()
        even_cues = torch.cat([b3, b7, b15, mag3, mag15, torch.abs(b3 - b7)], dim=1)

        denoise_logits = self.blur7(self.denoise_head(torch.cat([features, even_cues], dim=1)))
        denoise_strength = 0.45 * torch.sigmoid(denoise_logits)
        denoise_delta = -material_support * denoise_strength * (radiometry - b3)
        denoised = torch.clamp(radiometry + denoise_delta, 0.0, 1.0)

        if self.subpixel_boundary_renderer:
            edge_base, renderer = self._render_boundary(denoised, features, even_cues, edge_support, gx7, gy7, mag7)
            edge_delta = renderer["renderer_delta"]
            edge_strength = renderer["width_strength"]
        else:
            edge_strength = 1.10 * torch.sigmoid(self.blur7(self.edge_head(even_cues)))
            edge_candidate = denoised - self.blur7(denoised)
            edge_delta = torch.clamp(edge_support * edge_strength * edge_candidate, -0.12, 0.12)
            edge_base = torch.clamp(denoised + edge_delta, 0.0, 1.0)
            zero = torch.zeros_like(raw)
            renderer = {"normal_offset_px": zero, "width_strength": zero, "render_blend": zero, "renderer_delta": zero}

        t3, t7, t15 = self.blur3(edge_base), self.blur7(edge_base), self.blur15(edge_base)
        texture_candidates = torch.cat([edge_base - t3, t3 - t7, t7 - t15], dim=1)
        texture_features = torch.cat(
            [features, edge_base, texture_candidates.abs(), material_support, denoise_strength, edge_support], dim=1,
        )
        texture_logits = self.blur15(self.texture_head(texture_features))
        texture_coefficients = 1.20 * torch.sigmoid(texture_logits)
        coefficient_sum = texture_coefficients.sum(dim=1, keepdim=True).clamp_min(1.20)
        texture_coefficients = texture_coefficients * (1.20 / coefficient_sum)
        texture_delta = torch.clamp(
            material_support * (texture_coefficients * texture_candidates).sum(dim=1, keepdim=True), -0.18, 0.18,
        )
        detail_delta = denoise_delta + texture_delta
        output = torch.clamp(edge_base + texture_delta, 0.0, 1.0)
        correction = torch.clamp(output - raw, -0.35, 0.35)
        output = torch.clamp(raw + correction, 0.0, 1.0)
        zero = torch.zeros_like(raw)
        return {
            "output": output,
            "low_delta": low_delta,
            "denoise_delta": denoise_delta,
            "detail_delta": detail_delta,
            "texture_delta": texture_delta,
            "edge_delta": edge_delta,
            "correction": correction,
            "gain_delta": gain_delta,
            "bias_delta": bias_delta,
            "denoise_strength": denoise_strength,
            "edge_strength": edge_strength,
            "edge_support": edge_support,
            "material_support": material_support,
            "texture_coefficients": texture_coefficients,
            "texture_candidates": texture_candidates,
            "transport_delta": zero,
            "transport_offset_px": zero,
            "transport_dx_px": zero,
            "transport_dy_px": zero,
            "geometry_logits": zero,
            "geometry_probability": zero,
            "geometry_boundary_support": edge_support,
            "raw_low": b15,
            **renderer,
        }


def build_model(arm: str, base: int = 16) -> PrototypeNet:
    return PrototypeNet(arm=arm, base=base)


def common_parameter_names(model: nn.Module) -> list[str]:
    return sorted(name for name, _value in model.named_parameters() if not name.startswith("renderer_head."))


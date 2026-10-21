"""Identity-safe, phase-symmetric repairs tested after the A/B/C falsification."""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import torch
from torch import nn


PROTOTYPE_PATH = Path(__file__).resolve().with_name("prototype_models.py")


def _load_prototypes():
    spec = importlib.util.spec_from_file_location("r101_repair_prototypes", PROTOTYPE_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(PROTOTYPE_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


PROTOTYPES = _load_prototypes()
R100 = PROTOTYPES.R100


class RepairedGateNet(PROTOTYPES.PrototypeNet):
    """Arm D: same operator directions, but usable gate initialization."""

    def __init__(self, base: int = 16):
        super().__init__(arm="A", base=base)
        self.arm = "D"
        nn.init.constant_(self.denoise_head[-1].bias, -3.0)
        nn.init.constant_(self.edge_head[-1].bias, -0.75)
        nn.init.constant_(self.texture_head[-1].bias, -1.2)


class MultiBandRepairNet(RepairedGateNet):
    """Arm E: D plus independently controlled, zero-phase edge bands."""

    def __init__(self, base: int = 16):
        super().__init__(base=base)
        self.arm = "E"
        self.edge_mix_head = nn.Sequential(
            R100.ConvAct(6, 16),
            R100.ConvAct(16, 16),
            nn.Conv2d(16, 3, 1),
        )
        nn.init.zeros_(self.edge_mix_head[-1].weight)
        nn.init.constant_(self.edge_mix_head[-1].bias, -1.0)

    def _forward_aligned(self, x: torch.Tensor) -> dict[str, torch.Tensor]:
        raw = x.clamp(0.0, 1.0)
        features = self._aligned_features(raw)
        radiometry_small = self.radiometry_head(torch.nn.functional.avg_pool2d(features, 4, stride=4))
        radiometry_params = torch.nn.functional.interpolate(
            radiometry_small, size=raw.shape[-2:], mode="bilinear", align_corners=False,
        )
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

        e3, e7, e15 = self.blur3(denoised), self.blur7(denoised), self.blur15(denoised)
        edge_candidates = torch.cat([denoised - e3, e3 - e7, e7 - e15], dim=1)
        edge_coefficients = 2.0 * torch.sigmoid(self.blur7(self.edge_mix_head(even_cues)))
        edge_delta = torch.clamp(
            edge_support * (edge_coefficients * edge_candidates).sum(dim=1, keepdim=True), -0.18, 0.18,
        )
        edge_base = torch.clamp(denoised + edge_delta, 0.0, 1.0)

        t3, t7, t15 = self.blur3(edge_base), self.blur7(edge_base), self.blur15(edge_base)
        texture_candidates = torch.cat([edge_base - t3, t3 - t7, t7 - t15], dim=1)
        texture_features = torch.cat(
            [features, edge_base, texture_candidates.abs(), material_support, denoise_strength, edge_support], dim=1,
        )
        texture_coefficients = 1.8 * torch.sigmoid(self.blur15(self.texture_head(texture_features)))
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
            "edge_strength": edge_coefficients.sum(dim=1, keepdim=True),
            "edge_coefficients": edge_coefficients,
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
            "normal_offset_px": zero,
            "width_strength": zero,
            "render_blend": zero,
            "renderer_delta": zero,
        }


class ParallelBandSynthesisNet(RepairedGateNet):
    """Arm F: one parallel band decision replaces serial denoise-then-restore."""

    def __init__(self, base: int = 16):
        super().__init__(base=base)
        self.arm = "F"
        self.band_gain_head = nn.Sequential(
            R100.ConvAct(base + 11, base),
            R100.ResidualBlock(base, scale=0.08),
            nn.Conv2d(base, 6, 1),
        )
        nn.init.zeros_(self.band_gain_head[-1].weight)
        nn.init.constant_(self.band_gain_head[-1].bias, -0.69314718056)

    def _forward_aligned(self, x: torch.Tensor) -> dict[str, torch.Tensor]:
        raw = x.clamp(0.0, 1.0)
        features = self._aligned_features(raw)
        radiometry_small = self.radiometry_head(torch.nn.functional.avg_pool2d(features, 4, stride=4))
        radiometry_params = torch.nn.functional.interpolate(
            radiometry_small, size=raw.shape[-2:], mode="bilinear", align_corners=False,
        )
        radiometry_params = self.blur17(radiometry_params)
        gain_delta = 0.22 * torch.tanh(radiometry_params[:, :1])
        bias_delta = 0.16 * torch.tanh(radiometry_params[:, 1:2])
        radiometry = torch.clamp(raw * (1.0 + gain_delta) + bias_delta, 0.0, 1.0)
        low_delta = radiometry - raw

        b3, b7, b15 = self.blur3(radiometry), self.blur7(radiometry), self.blur15(radiometry)
        edge_support, gradients = self._edge_support(b3, b7, b15)
        gx3, gy3, mag3, gx7, gy7, mag7, gx15, gy15, mag15 = gradients
        even_cues = torch.cat([b3, b7, b15, mag3, mag15, torch.abs(b3 - b7)], dim=1)
        bands = torch.cat([radiometry - b3, b3 - b7, b7 - b15], dim=1)
        noise_proxy = self.blur3(torch.abs(bands[:, :1] - self.blur3(bands[:, :1])))
        gain_input = torch.cat([features, even_cues, bands.abs(), edge_support, noise_proxy], dim=1)
        gain_logits = self.blur7(self.band_gain_head(gain_input))
        gains = 3.0 * torch.sigmoid(gain_logits)
        edge_gains, material_gains = gains[:, :3], gains[:, 3:]
        mix = edge_support
        combined_gains = mix * edge_gains + (1.0 - mix) * material_gains
        output = torch.clamp(b15 + (combined_gains * bands).sum(dim=1, keepdim=True), 0.0, 1.0)
        edge_delta = mix * ((edge_gains - 1.0) * bands).sum(dim=1, keepdim=True)
        texture_delta = (1.0 - mix) * ((material_gains - 1.0) * bands).sum(dim=1, keepdim=True)
        correction = torch.clamp(output - raw, -0.35, 0.35)
        output = torch.clamp(raw + correction, 0.0, 1.0)
        zero = torch.zeros_like(raw)
        return {
            "output": output,
            "low_delta": low_delta,
            "denoise_delta": zero,
            "detail_delta": edge_delta + texture_delta,
            "texture_delta": texture_delta,
            "edge_delta": edge_delta,
            "correction": correction,
            "gain_delta": gain_delta,
            "bias_delta": bias_delta,
            "denoise_strength": zero,
            "edge_strength": edge_gains.sum(dim=1, keepdim=True),
            "edge_coefficients": edge_gains,
            "edge_support": edge_support,
            "material_support": 1.0 - edge_support,
            "texture_coefficients": material_gains,
            "texture_candidates": bands,
            "band_gains": combined_gains,
            "transport_delta": zero,
            "transport_offset_px": zero,
            "transport_dx_px": zero,
            "transport_dy_px": zero,
            "geometry_logits": zero,
            "geometry_probability": zero,
            "geometry_boundary_support": edge_support,
            "raw_low": b15,
            "normal_offset_px": zero,
            "width_strength": zero,
            "render_blend": zero,
            "renderer_delta": zero,
        }


class HighFrequencyInnovationNet(ParallelBandSynthesisNet):
    """Arm G: F plus a zero-mean learned high-frequency innovation path."""

    def __init__(self, base: int = 16):
        super().__init__(base=base)
        self.arm = "G"
        self.innovation_head = nn.Sequential(
            R100.ConvAct(base + 5, base),
            R100.ResidualBlock(base, scale=0.08),
            nn.Conv2d(base, 1, 1),
        )
        nn.init.zeros_(self.innovation_head[-1].weight)
        nn.init.zeros_(self.innovation_head[-1].bias)

    def _forward_aligned(self, x: torch.Tensor) -> dict[str, torch.Tensor]:
        details = super()._forward_aligned(x)
        raw = x.clamp(0.0, 1.0)
        features = self._aligned_features(raw)
        cues = torch.cat(
            [features, raw, details["texture_candidates"].abs(), details["edge_support"]], dim=1,
        )
        innovation = 0.12 * torch.tanh(self.innovation_head(cues))
        innovation = torch.clamp(innovation - self.blur3(innovation), -0.12, 0.12)
        edge_innovation = details["edge_support"] * innovation
        material_innovation = (1.0 - details["edge_support"]) * innovation
        output = torch.clamp(details["output"] + innovation, 0.0, 1.0)
        correction = torch.clamp(output - raw, -0.35, 0.35)
        details.update(
            output=torch.clamp(raw + correction, 0.0, 1.0),
            correction=correction,
            edge_delta=details["edge_delta"] + edge_innovation,
            texture_delta=details["texture_delta"] + material_innovation,
            detail_delta=details["detail_delta"] + innovation,
            innovation_delta=innovation,
        )
        return details


def build_model(arm: str, base: int = 16) -> nn.Module:
    arm = arm.upper()
    if arm == "D":
        return RepairedGateNet(base=base)
    if arm == "E":
        return MultiBandRepairNet(base=base)
    if arm == "F":
        return ParallelBandSynthesisNet(base=base)
    if arm == "G":
        return HighFrequencyInnovationNet(base=base)
    raise ValueError(arm)

"""Disposable R103 architecture candidate used only by causal preflight."""
from __future__ import annotations

from dataclasses import dataclass

import torch
from torch import nn

from r102_model import ParallelInnovationMOSR


@dataclass
class CandidateDetails:
    output: torch.Tensor
    low_delta: torch.Tensor
    contour_delta: torch.Tensor
    texture_delta: torch.Tensor
    total_delta: torch.Tensor
    contour_confidence: torch.Tensor
    texture_confidence: torch.Tensor
    need_confidence: torch.Tensor


class GatedNoNormMOSR(ParallelInnovationMOSR):
    """R102 body with information-preserving features and a real off gate."""

    def __init__(self, base: int = 16, **kwargs: float):
        super().__init__(base=base, **kwargs)
        for module in self.modules():
            if hasattr(module, "norm") and module.norm.__class__.__name__ == "PixelGroupNorm":
                module.norm = nn.Identity()
        self.need_body = nn.Sequential(
            nn.Conv2d(9, base, 5, padding=2),
            nn.SiLU(),
            nn.Conv2d(base, base, 3, padding=2, dilation=2),
            nn.SiLU(),
            nn.Conv2d(base, 1, 1),
        )
        nn.init.kaiming_normal_(self.need_body[0].weight, nonlinearity="relu")
        nn.init.zeros_(self.need_body[0].bias)
        nn.init.kaiming_normal_(self.need_body[2].weight, nonlinearity="relu")
        nn.init.zeros_(self.need_body[2].bias)
        nn.init.zeros_(self.need_body[4].weight)
        nn.init.constant_(self.need_body[4].bias, -1.35)
        self.force_need: float | None = None
        for head in (self.low_head, self.contour_head, self.texture_head):
            nn.init.normal_(head.weight, mean=0.0, std=0.00035)
            nn.init.zeros_(head.bias)

    def _forward_aligned(self, x: torch.Tensor) -> CandidateDetails:
        raw = x.clamp(0.0, 1.0)
        features = self._features(raw)
        # Blur/clear discrimination lives in a few gray levels.  Keep this tiny
        # path in FP32 even when the reconstruction body uses BF16.
        with torch.autocast(device_type=raw.device.type, enabled=False):
            learned_need = torch.sigmoid(self.need_body(self.cues(raw.float())))
        selected_need = learned_need if self.force_need is None else torch.full_like(learned_need, float(self.force_need))
        need = selected_need.to(dtype=features.dtype)

        low_logits = self.low_head(self.low_body(features))
        low_delta = need * self.low_bound * torch.tanh(self.low_project(low_logits))

        contour_features = self.contour_body(features)
        contour_logits = torch.tanh(self.contour_head(contour_features))
        contour_high = contour_logits - self.contour_project(contour_logits)
        contour_delta = need * self.contour_bound * contour_high

        texture_features = self.texture_body(features)
        texture_logits = torch.tanh(self.texture_head(texture_features))
        texture_high = texture_logits - self.texture_project(texture_logits)
        texture_delta = need * self.texture_bound * texture_high

        total = low_delta + contour_delta + texture_delta
        total = self.combined_bound * torch.tanh(total / max(self.combined_bound, 1e-6))
        output = (raw + total).clamp(0.0, 1.0)
        return CandidateDetails(output, low_delta, contour_delta, texture_delta, total, need, need, need)

    def forward_details(self, x: torch.Tensor) -> CandidateDetails:
        h, w = x.shape[-2:]
        pad_h = (-h) % self.alignment_multiple
        pad_w = (-w) % self.alignment_multiple
        if pad_h or pad_w:
            mode = "reflect" if h > pad_h and w > pad_w else "replicate"
            padded = torch.nn.functional.pad(x, (0, pad_w, 0, pad_h), mode=mode)
            details = self._forward_aligned(padded)
            values = [getattr(details, field)[:, :, :h, :w] for field in details.__dataclass_fields__]
            return CandidateDetails(*values)
        return self._forward_aligned(x)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.forward_details(x).output


def build_candidate(base: int = 16, **kwargs: float) -> GatedNoNormMOSR:
    return GatedNoNormMOSR(base=base, **kwargs)

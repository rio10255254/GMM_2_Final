"""Same-scene T/B/S targets for R94 causal routing supervision."""
from __future__ import annotations

from dataclasses import dataclass

import torch
import torch.nn.functional as F


def _binomial_kernel(size: int, device: torch.device, dtype: torch.dtype) -> torch.Tensor:
    rows = {
        3: [1.0, 2.0, 1.0],
        5: [1.0, 4.0, 6.0, 4.0, 1.0],
        7: [1.0, 6.0, 15.0, 20.0, 15.0, 6.0, 1.0],
        17: [1, 16, 120, 560, 1820, 4368, 8008, 11440, 12870, 11440, 8008, 4368, 1820, 560, 120, 16, 1],
    }
    vector = torch.tensor(rows[int(size)], device=device, dtype=dtype)
    kernel = torch.outer(vector, vector)
    kernel = kernel / kernel.sum()
    return kernel.view(1, 1, size, size)


def lowpass(x: torch.Tensor, size: int) -> torch.Tensor:
    kernel = _binomial_kernel(size, x.device, x.dtype).repeat(x.shape[1], 1, 1, 1)
    radius = size // 2
    mode = "reflect" if x.shape[-2] > radius and x.shape[-1] > radius else "replicate"
    return F.conv2d(F.pad(x, (radius, radius, radius, radius), mode=mode), kernel, groups=x.shape[1])


def local_energy(x: torch.Tensor, size: int = 7) -> torch.Tensor:
    return torch.sqrt(lowpass(x.square(), size) + 1e-8)


def soft_need(target: torch.Tensor, reference_gray: float = 1.0) -> torch.Tensor:
    scale = max(float(reference_gray) / 255.0, 1e-6)
    return 1.0 - torch.exp(-local_energy(target) / scale)


def exact_gate_target(target: torch.Tensor, reference_gray: float = 1.0) -> torch.Tensor:
    """Supervise zero exactly while opening decisively for nonzero correction."""
    return torch.where(
        local_energy(target) <= (1e-7 / 255.0),
        torch.zeros_like(target),
        soft_need(target, reference_gray=reference_gray),
    )


def local_recoverability(clean_target: torch.Tensor, noise_free: torch.Tensor) -> torch.Tensor:
    target_fine = clean_target - lowpass(clean_target, 7)
    visible_fine = noise_free - lowpass(noise_free, 7)
    mean_target = lowpass(target_fine, 7)
    mean_visible = lowpass(visible_fine, 7)
    centered_target = target_fine - mean_target
    centered_visible = visible_fine - mean_visible
    covariance = lowpass(centered_target * centered_visible, 7)
    target_energy = lowpass(centered_target.square(), 7).clamp_min(1e-8)
    visible_energy = lowpass(centered_visible.square(), 7).clamp_min(1e-8)
    correlation = (covariance / torch.sqrt(target_energy * visible_energy)).clamp(0.0, 1.0)
    energy_ratio = torch.sqrt(visible_energy / target_energy).clamp(0.0, 1.0)
    # Correlation is the primary evidence that phase-bearing detail survived;
    # visible energy modulates how aggressively it can be restored.  A small
    # continuous floor prevents exact dead zones without turning this into a
    # binary gate.
    return (0.08 + 0.92 * (0.68 * correlation + 0.32 * energy_ratio)).clamp(0.08, 1.0)


@dataclass
class ViewTargets:
    source: torch.Tensor
    target: torch.Tensor
    radiometry_component: torch.Tensor
    nuisance_component: torch.Tensor
    local_contrast_component: torch.Tensor
    boundary_component: torch.Tensor
    texture_component: torch.Tensor
    radiometry_effective: torch.Tensor
    nuisance_effective: torch.Tensor
    local_contrast_effective: torch.Tensor
    boundary_effective: torch.Tensor
    texture_effective: torch.Tensor
    restoration_raw: torch.Tensor
    restoration_effective: torch.Tensor
    need_radiometry: torch.Tensor
    need_noise: torch.Tensor
    need_local_contrast: torch.Tensor
    local_contrast_evidence: torch.Tensor
    need_boundary: torch.Tensor
    boundary_evidence: torch.Tensor
    need_texture: torch.Tensor
    texture_recoverability: torch.Tensor
    boundary_support: torch.Tensor


def gradient_components(x: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
    sobel = torch.tensor([[-1.0, 0.0, 1.0], [-2.0, 0.0, 2.0], [-1.0, 0.0, 1.0]], device=x.device, dtype=x.dtype) / 8.0
    kernel_x = sobel.view(1, 1, 3, 3).repeat(x.shape[1], 1, 1, 1)
    kernel_y = sobel.t().contiguous().view(1, 1, 3, 3).repeat(x.shape[1], 1, 1, 1)
    mode = "reflect" if x.shape[-2] > 1 and x.shape[-1] > 1 else "replicate"
    padded = F.pad(x, (1, 1, 1, 1), mode=mode)
    return F.conv2d(padded, kernel_x, groups=x.shape[1]), F.conv2d(padded, kernel_y, groups=x.shape[1])


def local_boundary_evidence(clean_target: torch.Tensor, noise_free: torch.Tensor) -> torch.Tensor:
    tx, ty = gradient_components(clean_target)
    bx, by = gradient_components(noise_free)
    target_magnitude = torch.sqrt(tx.square() + ty.square() + 1e-8)
    visible_magnitude = torch.sqrt(bx.square() + by.square() + 1e-8)
    direction = ((tx * bx + ty * by) / (target_magnitude * visible_magnitude)).clamp(0.0, 1.0)
    energy = (visible_magnitude / target_magnitude).clamp(0.0, 1.0)
    return (0.08 + 0.92 * (0.72 * direction + 0.28 * energy)).clamp(0.08, 1.0)


def inferred_boundary_support(clean_target: torch.Tensor) -> torch.Tensor:
    gx, gy = gradient_components(clean_target)
    magnitude = torch.sqrt(gx.square() + gy.square() + 1e-8)
    scale = magnitude.flatten(1).quantile(0.90, dim=1).clamp_min(1.0 / 255.0).view(-1, 1, 1, 1)
    return (1.0 - torch.exp(-magnitude / scale)).clamp(0.0, 1.0)


def boundary_support_from_mask(mask: torch.Tensor, radius: int = 7) -> torch.Tensor:
    """Create a soft structural-boundary band from an anti-aliased mask."""
    if radius < 1:
        raise ValueError("radius must be positive")
    local_max = F.max_pool2d(mask, 3, stride=1, padding=1)
    local_min = -F.max_pool2d(-mask, 3, stride=1, padding=1)
    edge = (local_max - local_min).clamp(0.0, 1.0)
    width = 2 * int(radius) + 1
    spread = F.max_pool2d(edge, width, stride=1, padding=radius)
    return lowpass(spread, 7).clamp(0.0, 1.0)


def build_counterfactual_views(
    clean_target: torch.Tensor,
    noise_free_source: torch.Tensor,
    noisy_source: torch.Tensor,
    *,
    boundary_support: torch.Tensor | None = None,
    optical_source: torch.Tensor | None = None,
    local_contrast_component: torch.Tensor | None = None,
    boundary_component: torch.Tensor | None = None,
    texture_component: torch.Tensor | None = None,
    local_contrast_clean: torch.Tensor | None = None,
    local_contrast_optical: torch.Tensor | None = None,
    boundary_clean: torch.Tensor | None = None,
    boundary_optical: torch.Tensor | None = None,
    texture_clean: torch.Tensor | None = None,
    texture_optical: torch.Tensor | None = None,
) -> dict[str, ViewTargets]:
    if not (clean_target.shape == noise_free_source.shape == noisy_source.shape):
        raise ValueError("T, B and S must have identical shapes")

    support = inferred_boundary_support(clean_target) if boundary_support is None else boundary_support.to(clean_target).clamp(0.0, 1.0)
    optical = noise_free_source if optical_source is None else optical_source.to(clean_target).clamp(0.0, 1.0)
    if optical.shape != clean_target.shape:
        raise ValueError("optical_source must match T/B/S shapes")
    explicit_layers = any(layer is not None for layer in (local_contrast_component, boundary_component, texture_component))
    if explicit_layers:
        if local_contrast_component is None or boundary_component is None or texture_component is None:
            raise ValueError("local-contrast, boundary and texture components must be supplied together")
        explicit_local_contrast = local_contrast_component.to(clean_target)
        explicit_boundary = boundary_component.to(clean_target)
        explicit_texture = texture_component.to(clean_target)
        if any(layer.shape != clean_target.shape for layer in (explicit_local_contrast, explicit_boundary, explicit_texture)):
            raise ValueError("explicit optical layer targets must match T/B/S shapes")
        layer_error = (
            explicit_local_contrast + explicit_boundary + explicit_texture - (clean_target - optical)
        ).abs().max()
        if float(layer_error) > 2e-5:
            raise ValueError(f"explicit optical layers do not recompose: {float(layer_error)}")
    else:
        explicit_local_contrast = explicit_boundary = explicit_texture = None
    evidence_layers = (
        local_contrast_clean, local_contrast_optical,
        boundary_clean, boundary_optical, texture_clean, texture_optical,
    )
    if any(layer is not None for layer in evidence_layers):
        if any(layer is None for layer in evidence_layers):
            raise ValueError("all six clean/optical evidence layers must be supplied together")
        evidence_layers = tuple(layer.to(clean_target) for layer in evidence_layers)  # type: ignore[union-attr]
        if any(layer.shape != clean_target.shape for layer in evidence_layers):
            raise ValueError("evidence layers must match T/B/S shapes")
        (
            local_contrast_clean_tensor, local_contrast_optical_tensor,
            boundary_clean_tensor, boundary_optical_tensor,
            texture_clean_tensor, texture_optical_tensor,
        ) = evidence_layers
    else:
        local_contrast_clean_tensor = local_contrast_optical_tensor = None
        boundary_clean_tensor = boundary_optical_tensor = None
        texture_clean_tensor = texture_optical_tensor = None

    def make(source: torch.Tensor, nuisance: torch.Tensor, restoration: torch.Tensor, *, exact_clear: bool) -> ViewTargets:
        nuisance_component = nuisance
        if exact_clear:
            zero = torch.zeros_like(source)
            # A clear observation retains all evidence but needs no repair.
            # This counterexample prevents the two concepts from collapsing.
            one = torch.ones_like(source)
            return ViewTargets(
                source, source,
                zero, zero, zero, zero, zero,
                zero, zero, zero, zero, zero,
                zero, zero,
                zero, zero, zero, one, zero, one, zero, one,
                support,
            )
        # Cause-based ownership: stochastic B-S, radiometry O-B, then optical
        # O-T divided spatially into structure boundary and material interior.
        radiometry_component = optical - noise_free_source
        optical_restoration = clean_target - optical
        if boundary_clean_tensor is None:
            texture_recoverability = local_recoverability(clean_target, optical)
            boundary_evidence = local_boundary_evidence(clean_target, optical)
            local_contrast_evidence = local_recoverability(clean_target, optical)
        else:
            texture_recoverability = local_recoverability(texture_clean_tensor, texture_optical_tensor)
            boundary_evidence = local_boundary_evidence(boundary_clean_tensor, boundary_optical_tensor)
            local_contrast_evidence = local_recoverability(
                local_contrast_clean_tensor, local_contrast_optical_tensor
            )
        local_contrast_owned = torch.zeros_like(optical_restoration) if explicit_local_contrast is None else explicit_local_contrast
        boundary_owned = support * optical_restoration if explicit_boundary is None else explicit_boundary
        texture_owned = (1.0 - support) * optical_restoration if explicit_texture is None else explicit_texture
        need_radiometry = exact_gate_target(radiometry_component, reference_gray=1.5)
        need_noise = exact_gate_target(nuisance_component, reference_gray=0.75)
        need_local_contrast = exact_gate_target(local_contrast_owned, reference_gray=0.75)
        need_boundary = exact_gate_target(boundary_owned, reference_gray=0.75)
        need_texture = exact_gate_target(texture_owned, reference_gray=0.75)
        # Need opens or closes a correction path; it must not attenuate the
        # amplitude of a correction that is already supported by evidence.
        # Output heads learn the conditional amplitude while these effective
        # targets retain the full known low/noise correction and only taper
        # genuinely ambiguous restoration content by physical evidence.
        radiometry_effective = radiometry_component
        nuisance_effective = nuisance_component
        local_contrast_effective = local_contrast_evidence * local_contrast_owned
        boundary_effective = boundary_evidence * boundary_owned
        texture_effective = texture_recoverability * texture_owned
        restoration_effective = local_contrast_effective + boundary_effective + texture_effective
        supervised_target = (
            source + radiometry_effective + nuisance_effective + restoration_effective
        ).clamp(0.0, 1.0)
        return ViewTargets(
            source,
            supervised_target,
            radiometry_component,
            nuisance_component,
            local_contrast_owned,
            boundary_owned,
            texture_owned,
            radiometry_effective,
            nuisance_effective,
            local_contrast_effective,
            boundary_effective,
            texture_effective,
            local_contrast_owned + boundary_owned + texture_owned,
            restoration_effective,
            need_radiometry,
            need_noise,
            need_local_contrast,
            local_contrast_evidence,
            need_boundary,
            boundary_evidence,
            need_texture,
            texture_recoverability,
            support,
        )

    return {
        "T_clear": make(clean_target, torch.zeros_like(clean_target), torch.zeros_like(clean_target), exact_clear=True),
        "B_noise_free": make(noise_free_source, torch.zeros_like(noisy_source), clean_target - noise_free_source, exact_clear=False),
        "S_noisy": make(noisy_source, noise_free_source - noisy_source, clean_target - noise_free_source, exact_clear=False),
    }

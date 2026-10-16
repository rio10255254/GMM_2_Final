"""Oracle normal-profile targets for the independent R114 scratch probe.

The existing ``training.targets`` module describes the completed E020 probe
and is intentionally left untouched.  This module implements the replacement
contract recorded by the E020 diagnosis:

* width and normal shift use independent identifiability targets;
* all geometric labels come from paired synthetic source/target/SDF data;
* the profile action is a bounded analytic tanh profile, never a free residual;
* clear and flat scenes have exactly neutral action targets;
* target construction is dense and local, so it remains compatible with
  single-image tiled inference.

Images are expected in ``[0, 1]`` with shape ``[B, 1, H, W]``.  The supplied
SDF must be positive inside the known synthetic mask.  Profile samples are
centred on the nearest SDF zero crossing and follow the true SDF normal from
``-12`` to ``+12`` pixels.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
import warnings

import torch
import torch.nn.functional as F


# PyTorch 2.3 probes an unsupported cuDNN execution plan for the legal
# B*H*W-by-25 short convolution below, then selects a correct fast fallback.
# Filter only that known warning when it originates from this target module;
# other CUDA/runtime warnings remain visible.
warnings.filterwarnings(
    "ignore",
    message="Plan failed with a cudnnException.*",
    category=UserWarning,
    module=r"(?:training\.)?split_profile_targets",
)


PROFILE_RADIUS_PX = 12
PROFILE_STEP_PX = 1
PROFILE_OFFSETS = tuple(float(value) for value in range(-PROFILE_RADIUS_PX, PROFILE_RADIUS_PX + 1))
PROFILE_SMOOTHING_SIGMAS_PX = (0.85, 1.45)
FULL_ACTION_RADIUS_PX = 10.0
OUTER_ACTION_RADIUS_PX = 14.0
MAXIMUM_ACTION_GRAY = 48.0
MAXIMUM_MIDPOINT_OFFSET_GRAY = 24.0
MINIMUM_CONTRAST_GRAY = 4.0
MAXIMUM_CONTRAST_GRAY = 72.0
MINIMUM_PROFILE_WIDTH_PX = 0.8
MAXIMUM_PROFILE_WIDTH_PX = 3.5
NEUTRAL_PROFILE_WIDTH_PX = 1.35
PROFILE_MIDPOINT_CUE_WINDOW_PX = 21
MINIMUM_WIDTH_GAIN = 1.0
MAXIMUM_WIDTH_GAIN = 3.5
MAXIMUM_NORMAL_SHIFT_PX = 1.5
_TANH_10_90_SPAN = 2.0 * math.atanh(0.8)


@dataclass(frozen=True)
class SplitProfileTargets:
    """Dense target maps for split reliability and bounded profile actions."""

    normalized_sdf: torch.Tensor
    normal_x: torch.Tensor
    normal_y: torch.Tensor
    boundary_band: torch.Tensor
    boundary_binary: torch.Tensor
    profile_sample_validity: torch.Tensor

    width_gain: torch.Tensor
    width_gain_raw: torch.Tensor
    normal_shift: torch.Tensor
    normal_shift_unclipped: torch.Tensor
    width_reliability: torch.Tensor
    shift_reliability: torch.Tensor
    width_weight: torch.Tensor
    shift_weight: torch.Tensor

    raw_midpoint_cue: torch.Tensor
    midpoint_offset: torch.Tensor
    signed_plateau_contrast: torch.Tensor
    profile_width: torch.Tensor
    profile_visibility: torch.Tensor
    profile_reliability: torch.Tensor
    profile_weight: torch.Tensor
    profile_visibility_weight: torch.Tensor
    coordinate_reliability: torch.Tensor
    deployment_sdf: torch.Tensor
    deployment_band: torch.Tensor
    oracle_profile_proposal: torch.Tensor
    oracle_profile_output: torch.Tensor

    source_image: torch.Tensor
    base_image: torch.Tensor
    target_image: torch.Tensor
    sdf: torch.Tensor
    identity: torch.Tensor
    flat: torch.Tensor

    # Explicit contract aliases keep integration code readable without storing
    # duplicate tensors.
    @property
    def width_gain_target(self) -> torch.Tensor:
        return self.width_gain

    @property
    def normal_shift_target(self) -> torch.Tensor:
        return self.normal_shift

    @property
    def midpoint_offset_target(self) -> torch.Tensor:
        return self.midpoint_offset

    @property
    def signed_contrast_target(self) -> torch.Tensor:
        return self.signed_plateau_contrast

    @property
    def profile_width_target(self) -> torch.Tensor:
        return self.profile_width

    @property
    def profile_visibility_target(self) -> torch.Tensor:
        return self.profile_visibility

    @property
    def profile_reliability_weight(self) -> torch.Tensor:
        """Oracle loss weight, not a fifth deployable action head."""

        return self.profile_reliability


def _validate_inputs(
    source: torch.Tensor,
    target: torch.Tensor,
    sdf: torch.Tensor,
    identity: torch.Tensor,
    flat: torch.Tensor | None,
) -> tuple[torch.Tensor, torch.Tensor]:
    if source.ndim != 4 or source.shape[1] != 1:
        raise ValueError("source must have shape [batch, 1, height, width]")
    if target.shape != source.shape or sdf.shape != source.shape:
        raise ValueError("source, target, and sdf must have identical shapes")
    if not source.is_floating_point() or not target.is_floating_point() or not sdf.is_floating_point():
        raise TypeError("source, target, and sdf must be floating point")
    batch = source.shape[0]
    identity_vector = identity.reshape(-1).bool()
    if identity_vector.numel() != batch:
        raise ValueError("identity must contain one flag per scene")
    flat_vector = torch.zeros_like(identity_vector) if flat is None else flat.reshape(-1).bool()
    if flat_vector.numel() != batch:
        raise ValueError("flat must contain one flag per scene")
    return identity_vector, flat_vector


def _central_differences(value: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
    padded = F.pad(value, (1, 1, 1, 1), mode="replicate")
    gx = 0.5 * (padded[..., 1:-1, 2:] - padded[..., 1:-1, :-2])
    gy = 0.5 * (padded[..., 2:, 1:-1] - padded[..., :-2, 1:-1])
    return gx, gy


def _sdf_normals(sdf: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
    gx, gy = _central_differences(sdf)
    magnitude = torch.sqrt(gx.square() + gy.square() + 1.0e-8)
    return gx / magnitude, gy / magnitude


def _cosine_action_band(sdf: torch.Tensor) -> torch.Tensor:
    distance = sdf.abs()
    phase = ((distance - FULL_ACTION_RADIUS_PX) / (OUTER_ACTION_RADIUS_PX - FULL_ACTION_RADIUS_PX)).clamp(0, 1)
    feather = 0.5 * (1.0 + torch.cos(math.pi * phase))
    return torch.where(
        distance <= FULL_ACTION_RADIUS_PX,
        torch.ones_like(distance),
        torch.where(distance < OUTER_ACTION_RADIUS_PX, feather, torch.zeros_like(distance)),
    )


def _boundary_centred_profiles(
    value: torch.Tensor,
    sdf: torch.Tensor,
    normal_x: torch.Tensor,
    normal_y: torch.Tensor,
    offsets: torch.Tensor,
) -> tuple[torch.Tensor, torch.Tensor]:
    """Sample profiles about each pixel's nearest SDF zero crossing.

    The returned profile tensor is ``[B, L, H, W]``.  The validity map is one
    only where every requested normal sample lies inside the image.  Reflection
    padding keeps all intermediate values finite, while validity prevents a
    reflected border from becoming synthetic geometry evidence.
    """

    batch, _channels, height, width = value.shape
    yy, xx = torch.meshgrid(
        torch.arange(height, device=value.device, dtype=value.dtype),
        torch.arange(width, device=value.device, dtype=value.dtype),
        indexing="ij",
    )
    xx = xx.reshape(1, 1, height, width).expand(batch, -1, -1, -1)
    yy = yy.reshape(1, 1, height, width).expand(batch, -1, -1, -1)
    boundary_x = xx - normal_x * sdf
    boundary_y = yy - normal_y * sdf

    sampled: list[torch.Tensor] = []
    valid = torch.ones_like(value, dtype=torch.bool)
    for offset in offsets:
        sample_x = boundary_x + offset * normal_x
        sample_y = boundary_y + offset * normal_y
        valid = valid & (sample_x >= 0.0) & (sample_x <= float(width - 1))
        valid = valid & (sample_y >= 0.0) & (sample_y <= float(height - 1))
        grid_x = 2.0 * sample_x[:, 0] / max(width - 1, 1) - 1.0
        grid_y = 2.0 * sample_y[:, 0] / max(height - 1, 1) - 1.0
        grid = torch.stack((grid_x, grid_y), dim=-1)
        sample = F.grid_sample(
            value,
            grid,
            mode="bilinear",
            padding_mode="reflection",
            align_corners=True,
        )
        sampled.append(sample)
    return torch.cat(sampled, dim=1), valid.to(value.dtype)


def _smooth_profiles(profile: torch.Tensor, sigma: float) -> torch.Tensor:
    radius = max(int(math.ceil(3.0 * sigma)), 1)
    positions = torch.arange(-radius, radius + 1, device=profile.device, dtype=profile.dtype)
    kernel = torch.exp(-0.5 * (positions / sigma).square())
    kernel = (kernel / kernel.sum()).reshape(1, 1, -1)
    batch, samples, height, width = profile.shape
    rows = profile.permute(0, 2, 3, 1).reshape(batch * height * width, 1, samples)
    rows = F.pad(rows, (radius, radius), mode="replicate")
    smoothed = F.conv1d(rows, kernel)
    return smoothed.reshape(batch, height, width, samples).permute(0, 3, 1, 2)


def _profile_noise(profile: torch.Tensor) -> torch.Tensor:
    left = profile[:, :4]
    right = profile[:, -4:]
    left_median = left.median(dim=1, keepdim=True).values
    right_median = right.median(dim=1, keepdim=True).values
    residual = torch.cat((left - left_median, right - right_median), dim=1)
    mad = 1.4826 * residual.abs().median(dim=1, keepdim=True).values
    plateaus = torch.cat((left, right), dim=1)
    return torch.maximum(mad, torch.full_like(mad, 1.5 / 255.0)) + 0.05 * plateaus.std(
        dim=1, keepdim=True, unbiased=False
    )


def _normalize_profiles(source: torch.Tensor, target: torch.Tensor) -> dict[str, torch.Tensor]:
    source_left = source[:, :4].median(dim=1, keepdim=True).values
    source_right = source[:, -4:].median(dim=1, keepdim=True).values
    target_left = target[:, :4].median(dim=1, keepdim=True).values
    target_right = target[:, -4:].median(dim=1, keepdim=True).values
    source_delta = source_right - source_left
    target_delta = target_right - target_left
    source_sign = torch.where(source_delta >= 0, torch.ones_like(source_delta), -torch.ones_like(source_delta))
    target_sign = torch.where(target_delta >= 0, torch.ones_like(target_delta), -torch.ones_like(target_delta))
    source_norm = ((source - source_left) / (source_delta + source_sign * 1.0e-6)).clamp(-1, 2)
    target_norm = ((target - target_left) / (target_delta + target_sign * 1.0e-6)).clamp(-1, 2)
    source_noise = _profile_noise(source)
    target_noise = _profile_noise(target)
    source_snr = source_delta.abs() / (2.0 * source_noise + 1.0 / 255.0)
    target_snr = target_delta.abs() / (2.0 * target_noise + 1.0 / 255.0)
    return {
        "source": source_norm,
        "target": target_norm,
        "source_left": source_left,
        "source_right": source_right,
        "target_left": target_left,
        "target_right": target_right,
        "source_delta": source_delta,
        "target_delta": target_delta,
        "source_contrast": source_delta.abs(),
        "target_contrast": target_delta.abs(),
        "source_snr": source_snr,
        "target_snr": target_snr,
        "polarity": (source_delta * target_delta > 0).to(source.dtype),
    }


def _edge_moments(profile: torch.Tensor, sigma: float, offsets: torch.Tensor) -> dict[str, torch.Tensor]:
    smoothed = _smooth_profiles(profile, sigma)
    derivative = smoothed[:, 1:] - smoothed[:, :-1]
    positive = derivative.clamp_min(0)
    negative = (-derivative).clamp_min(0)
    positive_mass = positive.sum(dim=1, keepdim=True)
    total_variation = (positive + negative).sum(dim=1, keepdim=True)
    mass = positive_mass.clamp_min(1.0e-8)
    mid_offsets = 0.5 * (offsets[:-1] + offsets[1:]).reshape(1, -1, 1, 1)
    location = (positive * mid_offsets).sum(dim=1, keepdim=True) / mass
    variance = (positive * (mid_offsets - location).square()).sum(dim=1, keepdim=True) / mass
    width_10_90 = 2.563103 * torch.sqrt(variance.clamp_min(1.0e-4))
    monotonicity = (positive_mass / total_variation.clamp_min(1.0e-8)).clamp(0, 1)
    radius = torch.maximum(torch.full_like(width_10_90, 2.0), 0.75 * width_10_90)
    central = ((mid_offsets - location).abs() <= radius).to(profile.dtype)
    concentration = ((positive * central).sum(dim=1, keepdim=True) / mass).clamp(0, 1)
    return {
        "location": location,
        "width_10_90": width_10_90,
        "monotonicity": monotonicity,
        "concentration": concentration,
        "positive_mass": positive_mass,
    }


def _gaussian_blur_map(value: torch.Tensor, sigma: float) -> torch.Tensor:
    radius = max(int(math.ceil(3.0 * sigma)), 1)
    positions = torch.arange(-radius, radius + 1, device=value.device, dtype=value.dtype)
    kernel = torch.exp(-0.5 * (positions / sigma).square())
    kernel = kernel / kernel.sum()
    horizontal = kernel.reshape(1, 1, 1, -1)
    vertical = kernel.reshape(1, 1, -1, 1)
    result = F.conv2d(F.pad(value, (radius, radius, 0, 0), mode="reflect"), horizontal)
    result = F.conv2d(F.pad(result, (0, 0, radius, radius), mode="reflect"), vertical)
    return result


def _runtime_midpoint_cue(value: torch.Tensor, window_px: int) -> torch.Tensor:
    """Match ``R114SplitProfileModel._profile_midpoint_cue`` exactly."""

    if window_px < 3 or window_px % 2 != 1:
        raise ValueError("midpoint_cue_window_px must be an odd integer >= 3")
    radius = window_px // 2
    padded = F.pad(value, (radius, radius, radius, radius), mode="replicate")
    local_max = F.max_pool2d(padded, window_px, stride=1)
    local_min = -F.max_pool2d(-padded, window_px, stride=1)
    return 0.5 * (local_max + local_min)


@torch.no_grad()
def build_split_profile_targets(
    source: torch.Tensor,
    target: torch.Tensor,
    sdf: torch.Tensor,
    identity: torch.Tensor,
    flat: torch.Tensor | None = None,
    base_output: torch.Tensor | None = None,
    midpoint_source: torch.Tensor | None = None,
    deployment_sdf_px: torch.Tensor | None = None,
    deployment_boundary_confidence: torch.Tensor | None = None,
    midpoint_cue_window_px: int = PROFILE_MIDPOINT_CUE_WINDOW_PX,
) -> SplitProfileTargets:
    """Build independent width/shift and bounded analytic-profile targets.

    ``base_output`` may be supplied when visibility should compare against a
    frozen geometry-stage result.  ``midpoint_source`` should be that model's
    exact cue input (currently ``shifted_base``); it defaults to ``base_output``
    and then source.  When ``deployment_sdf_px`` is supplied, visibility is
    labelled by a counterfactual using the same predicted coordinate, band,
    and bounded action that inference will use.  True SDF remains supervision
    only; it no longer substitutes for the deployment coordinate in the
    render/visibility target.
    """

    identity_vector, flat_vector = _validate_inputs(source, target, sdf, identity, flat)
    if base_output is not None and base_output.shape != source.shape:
        raise ValueError("base_output must have the same shape as source")
    if midpoint_source is not None and midpoint_source.shape != source.shape:
        raise ValueError("midpoint_source must have the same shape as source")
    if deployment_sdf_px is not None and deployment_sdf_px.shape != source.shape:
        raise ValueError("deployment_sdf_px must have the same shape as source")
    if (
        deployment_boundary_confidence is not None
        and deployment_boundary_confidence.shape != source.shape
    ):
        raise ValueError("deployment_boundary_confidence must have the same shape as source")
    source = source.detach().float().clamp(0, 1)
    target = target.detach().float().clamp(0, 1)
    sdf = sdf.detach().float()
    baseline = source if base_output is None else base_output.detach().float().clamp(0, 1)
    cue_source = baseline if midpoint_source is None else midpoint_source.detach().float().clamp(0, 1)
    deployment_sdf = (
        sdf
        if deployment_sdf_px is None
        else deployment_sdf_px.detach().float()
    )
    deployment_boundary = (
        torch.ones_like(source)
        if deployment_boundary_confidence is None
        else deployment_boundary_confidence.detach().float().clamp(0, 1)
    )
    identity_map = identity_vector.reshape(-1, 1, 1, 1)
    flat_map = flat_vector.reshape(-1, 1, 1, 1)

    normal_x, normal_y = _sdf_normals(sdf)
    band = _cosine_action_band(sdf)
    band = torch.where(flat_map, torch.zeros_like(band), band)
    boundary_binary = ((sdf.abs() <= 1.05) & ~flat_map).to(source.dtype)
    offsets = torch.tensor(PROFILE_OFFSETS, device=source.device, dtype=source.dtype)
    source_profile, source_valid = _boundary_centred_profiles(source, sdf, normal_x, normal_y, offsets)
    target_profile, target_valid = _boundary_centred_profiles(target, sdf, normal_x, normal_y, offsets)
    baseline_profile, baseline_valid = _boundary_centred_profiles(baseline, sdf, normal_x, normal_y, offsets)
    validity = source_valid * target_valid * baseline_valid
    evidence_band = band * validity

    normalized = _normalize_profiles(source_profile, target_profile)
    src_a = _edge_moments(normalized["source"], PROFILE_SMOOTHING_SIGMAS_PX[0], offsets)
    src_b = _edge_moments(normalized["source"], PROFILE_SMOOTHING_SIGMAS_PX[1], offsets)
    tgt_a = _edge_moments(normalized["target"], PROFILE_SMOOTHING_SIGMAS_PX[0], offsets)
    tgt_b = _edge_moments(normalized["target"], PROFILE_SMOOTHING_SIGMAS_PX[1], offsets)

    polarity = normalized["polarity"]
    source_snr = normalized["source_snr"]
    target_snr = normalized["target_snr"]
    snr_score = torch.sigmoid((source_snr - 2.6) / 1.15)
    target_score = torch.sigmoid((target_snr - 4.0) / 1.5)
    source_monotonicity = ((src_a["monotonicity"] - 0.50) / 0.42).clamp(0, 1)
    target_monotonicity = ((tgt_a["monotonicity"] - 0.55) / 0.38).clamp(0, 1)
    width_stability = torch.exp(
        -torch.abs(torch.log((src_a["width_10_90"] + 0.25) / (src_b["width_10_90"] + 0.25))) / 0.42
    )
    ratio_a = src_a["width_10_90"] / tgt_a["width_10_90"].clamp_min(0.25)
    ratio_b = src_b["width_10_90"] / tgt_b["width_10_90"].clamp_min(0.25)
    width_ratio_stability = torch.exp(-torch.abs(torch.log((ratio_a + 0.1) / (ratio_b + 0.1))) / 0.55)
    contrast_visibility = torch.sqrt(
        (normalized["source_contrast"] / normalized["target_contrast"].clamp_min(2.0 / 255.0)).clamp(0, 1)
    )

    width_reliability_raw = polarity * torch.sqrt((snr_score * target_score).clamp_min(0))
    width_reliability_raw *= torch.sqrt((source_monotonicity * target_monotonicity).clamp_min(0))
    width_reliability_raw *= torch.sqrt((width_stability * width_ratio_stability).clamp_min(0))
    width_reliability_raw *= 0.35 + 0.65 * contrast_visibility
    width_reliability_raw = width_reliability_raw.clamp(0, 1)

    width_ratio = (src_a["width_10_90"] / tgt_a["width_10_90"].clamp_min(0.45)).clamp(
        MINIMUM_WIDTH_GAIN, MAXIMUM_WIDTH_GAIN
    )
    width_gain = MINIMUM_WIDTH_GAIN + width_reliability_raw * (width_ratio - MINIMUM_WIDTH_GAIN)

    shift_a = src_a["location"] - tgt_a["location"]
    shift_b = src_b["location"] - tgt_b["location"]
    shift_stability = torch.exp(-(shift_a - shift_b).abs() / 0.40)
    representable = torch.exp(-(shift_a.abs() - 1.20).clamp_min(0) / 0.22)
    localization_sigma = src_a["width_10_90"] / source_snr.clamp_min(0.25)
    localization_score = 1.0 / (1.0 + (localization_sigma / 2.3).square())
    unique_edge = torch.sqrt((src_a["concentration"] * src_b["concentration"]).clamp_min(0))
    shift_reliability_raw = polarity * snr_score * source_monotonicity
    shift_reliability_raw *= torch.sqrt((target_score * target_monotonicity).clamp_min(0))
    shift_reliability_raw *= shift_stability * representable * localization_score * unique_edge
    shift_reliability_raw = torch.sqrt(shift_reliability_raw.clamp(0, 1))

    width_reliability = (width_reliability_raw * evidence_band).clamp(0, 1)
    shift_reliability = (shift_reliability_raw * evidence_band).clamp(0, 1)
    width_reliability = torch.where(flat_map, torch.zeros_like(width_reliability), width_reliability)
    shift_reliability = torch.where(flat_map, torch.zeros_like(shift_reliability), shift_reliability)

    width_gain = torch.where(
        identity_map | flat_map | (band <= 0),
        torch.ones_like(width_gain),
        width_gain,
    ).clamp(MINIMUM_WIDTH_GAIN, MAXIMUM_WIDTH_GAIN)
    normal_shift = shift_a.clamp(-MAXIMUM_NORMAL_SHIFT_PX, MAXIMUM_NORMAL_SHIFT_PX)
    normal_shift = torch.where(
        identity_map | flat_map | (band <= 0), torch.zeros_like(normal_shift), normal_shift
    )

    # Width reliability is already encoded once by attenuating the target
    # toward one.  Keep width_weight as pure valid support so fitting does not
    # suppress the same evidence a second time.  Shift is different: its
    # signed oracle target must never be attenuated toward zero, so reliability
    # belongs exactly once in shift_weight instead.
    width_weight = evidence_band
    shift_weight = evidence_band * shift_reliability_raw
    width_weight = torch.where(flat_map, torch.zeros_like(width_weight), width_weight)
    shift_weight = torch.where(flat_map, torch.zeros_like(shift_weight), shift_weight)

    # Match the deployable model's cue exactly.  Plateau medians remain the
    # clean oracle parameter, but the learned head predicts an offset from the
    # local max/min midpoint that exists at inference.
    runtime_midpoint_cue = _runtime_midpoint_cue(cue_source, midpoint_cue_window_px)
    target_midpoint = 0.5 * (normalized["target_left"] + normalized["target_right"])
    midpoint_offset = (target_midpoint - runtime_midpoint_cue).clamp(
        -MAXIMUM_MIDPOINT_OFFSET_GRAY / 255.0,
        MAXIMUM_MIDPOINT_OFFSET_GRAY / 255.0,
    )
    target_contrast = normalized["target_delta"]
    target_sign = torch.where(target_contrast >= 0, torch.ones_like(target_contrast), -torch.ones_like(target_contrast))
    signed_contrast = target_sign * target_contrast.abs().clamp(
        MINIMUM_CONTRAST_GRAY / 255.0,
        MAXIMUM_CONTRAST_GRAY / 255.0,
    )
    # ``edge_moments`` returns a 10-to-90 span.  The renderer parameter is the
    # tanh scale, so convert before applying the contractual 0.8..3.5 px bound.
    profile_width = (tgt_a["width_10_90"] / _TANH_10_90_SPAN).clamp(
        MINIMUM_PROFILE_WIDTH_PX, MAXIMUM_PROFILE_WIDTH_PX
    )

    target_unique_edge = torch.sqrt((tgt_a["concentration"] * tgt_b["concentration"]).clamp_min(0))
    profile_reliability_raw = torch.sqrt(
        (
            width_reliability_raw
            * target_score
            * target_monotonicity
            * target_unique_edge
        ).clamp(0, 1)
    )
    profile_reliability = (profile_reliability_raw * evidence_band).clamp(0, 1)

    representable_midpoint = (runtime_midpoint_cue + midpoint_offset).clamp(0, 1)
    deployment_band = _cosine_action_band(deployment_sdf)
    deployment_band = torch.where(flat_map, torch.zeros_like(deployment_band), deployment_band)
    oracle_profile_proposal = (
        representable_midpoint
        + 0.5
        * signed_contrast
        * torch.tanh(deployment_sdf / profile_width.clamp_min(MINIMUM_PROFILE_WIDTH_PX))
    ).clamp(0, 1)
    maximum_delta = MAXIMUM_ACTION_GRAY / 255.0
    oracle_proposal_delta = (oracle_profile_proposal - baseline).clamp(
        -maximum_delta,
        maximum_delta,
    )

    # The deployable profile gate deliberately contains only locally predicted
    # boundary confidence, predicted-coordinate support, and learned
    # visibility.  Build the visibility label by asking whether that *actual*
    # unit action lowers base-to-target error.  A wrong SDF sign or misplaced
    # zero crossing therefore creates an explicit negative example instead of
    # being hidden by a true-SDF oracle renderer.
    unit_action = deployment_boundary * deployment_band * oracle_proposal_delta
    residual = target - baseline
    same_direction = residual * unit_action > 0
    safe_unit_action = torch.where(
        unit_action.abs() > 1.0e-7,
        unit_action,
        torch.ones_like(unit_action),
    )
    optimal_visibility = torch.where(
        same_direction,
        (residual / safe_unit_action).clamp(0, 1),
        torch.zeros_like(unit_action),
    )
    oracle_profile_output = (baseline + optimal_visibility * unit_action).clamp(0, 1)
    base_error = (baseline - target).abs()
    oracle_error = (oracle_profile_output - target).abs()
    relative_gain = ((base_error - oracle_error) / base_error.clamp_min(1.0 / 255.0)).clamp(0, 1)
    visibility_seed = optimal_visibility * (relative_gain / 0.10).clamp(0, 1)
    visibility_seed = _gaussian_blur_map(visibility_seed, 0.75)
    counterfactual_support = (deployment_band * evidence_band).clamp(0, 1)
    profile_visibility = (visibility_seed * counterfactual_support).clamp(0, 1)

    coordinate_error = (deployment_sdf - sdf).abs()
    coordinate_reliability = torch.exp(-coordinate_error / 2.0)
    coordinate_reliability *= torch.where(
        (deployment_sdf * sdf >= 0) | (sdf.abs() <= 0.75),
        torch.ones_like(coordinate_reliability),
        torch.full_like(coordinate_reliability, 0.10),
    )
    coordinate_reliability = (coordinate_reliability * counterfactual_support).clamp(0, 1)
    profile_visibility_weight = (deployment_band + evidence_band).clamp(0, 1)
    profile_visibility_weight = torch.where(
        flat_map,
        torch.ones_like(profile_visibility_weight),
        profile_visibility_weight,
    )

    neutral = identity_map | flat_map | (band <= 0)
    midpoint_offset = torch.where(neutral, torch.zeros_like(midpoint_offset), midpoint_offset)
    signed_contrast = torch.where(flat_map | (band <= 0), torch.zeros_like(signed_contrast), signed_contrast)
    profile_width = torch.where(
        flat_map | (band <= 0),
        torch.full_like(profile_width, NEUTRAL_PROFILE_WIDTH_PX),
        profile_width,
    )
    profile_visibility = torch.where(identity_map | flat_map, torch.zeros_like(profile_visibility), profile_visibility)
    # Coordinate reliability already contains the valid true/predicted band
    # intersection, so apply that support exactly once.
    profile_reliability = (profile_reliability_raw * coordinate_reliability).clamp(0, 1)
    profile_reliability = torch.where(flat_map, torch.zeros_like(profile_reliability), profile_reliability)
    profile_weight = counterfactual_support * (
        0.05 + 0.95 * profile_reliability_raw * coordinate_reliability
    )
    profile_weight = torch.where(flat_map, torch.zeros_like(profile_weight), profile_weight)

    values = (
        normalized_sdf := (sdf / PROFILE_RADIUS_PX).clamp(-1, 1),
        normal_x,
        normal_y,
        band,
        validity,
        width_gain,
        normal_shift,
        width_reliability,
        shift_reliability,
        width_weight,
        shift_weight,
        runtime_midpoint_cue,
        midpoint_offset,
        signed_contrast,
        profile_width,
        profile_visibility,
        profile_reliability,
        profile_weight,
        profile_visibility_weight,
        coordinate_reliability,
        deployment_sdf,
        deployment_band,
        oracle_profile_proposal,
        oracle_profile_output,
    )
    if not all(bool(torch.isfinite(value).all()) for value in values):
        raise FloatingPointError("non-finite split-profile target detected")

    return SplitProfileTargets(
        normalized_sdf=normalized_sdf,
        normal_x=normal_x,
        normal_y=normal_y,
        boundary_band=band,
        boundary_binary=boundary_binary,
        profile_sample_validity=validity,
        width_gain=width_gain,
        width_gain_raw=width_ratio,
        normal_shift=normal_shift,
        normal_shift_unclipped=shift_a,
        width_reliability=width_reliability,
        shift_reliability=shift_reliability,
        width_weight=width_weight,
        shift_weight=shift_weight,
        raw_midpoint_cue=runtime_midpoint_cue,
        midpoint_offset=midpoint_offset,
        signed_plateau_contrast=signed_contrast,
        profile_width=profile_width,
        profile_visibility=profile_visibility,
        profile_reliability=profile_reliability,
        profile_weight=profile_weight,
        profile_visibility_weight=profile_visibility_weight,
        coordinate_reliability=coordinate_reliability,
        deployment_sdf=deployment_sdf,
        deployment_band=deployment_band,
        oracle_profile_proposal=oracle_profile_proposal,
        oracle_profile_output=oracle_profile_output,
        source_image=source,
        base_image=baseline,
        target_image=target,
        sdf=sdf,
        identity=identity_vector,
        flat=flat_vector,
    )


__all__ = [
    "SplitProfileTargets",
    "build_split_profile_targets",
    "PROFILE_OFFSETS",
    "PROFILE_RADIUS_PX",
    "OUTER_ACTION_RADIUS_PX",
    "MAXIMUM_ACTION_GRAY",
    "MAXIMUM_MIDPOINT_OFFSET_GRAY",
    "MINIMUM_CONTRAST_GRAY",
    "MAXIMUM_CONTRAST_GRAY",
    "MINIMUM_PROFILE_WIDTH_PX",
    "MAXIMUM_PROFILE_WIDTH_PX",
    "MINIMUM_WIDTH_GAIN",
    "MAXIMUM_WIDTH_GAIN",
    "MAXIMUM_NORMAL_SHIFT_PX",
    "PROFILE_MIDPOINT_CUE_WINDOW_PX",
]

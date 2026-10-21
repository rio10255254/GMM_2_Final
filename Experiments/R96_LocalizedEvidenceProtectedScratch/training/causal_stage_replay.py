"""Deterministically replay the causal stages that produced an R93/R96 view.

The source package stores T (clean), B (noise-free degraded), S (sensor-noisy)
and the full deterministic degradation record.  This module replays the
pre-photometric optical stage O.  R96 can therefore supervise the exact chain

    S --sensor correction--> B --radiometric correction--> O
      --boundary/texture restoration--> T

without assigning optical blur or halo correction to the illumination branch.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any
import math

import cv2
import numpy as np


@dataclass(frozen=True)
class ReplayResult:
    optical_source: np.ndarray
    replayed_noise_free_u8: np.ndarray
    boundary_support: np.ndarray
    hidden_parameters: dict[str, Any]


@dataclass(frozen=True)
class OpticalLayerTargets:
    boundary_target: np.ndarray
    texture_target: np.ndarray
    local_contrast_target: np.ndarray
    shape_clean: np.ndarray
    shape_prefade: np.ndarray
    shape_optical: np.ndarray
    texture_clean: np.ndarray
    texture_prefade: np.ndarray
    texture_optical: np.ndarray
    recomposition_max_abs: float


def _motion_kernel(length: int, angle: float) -> np.ndarray:
    length = max(1, int(length) | 1)
    kernel = np.zeros((length, length), dtype=np.float32)
    center = length // 2
    radians = math.radians(float(angle))
    dx, dy = math.cos(radians) * center, math.sin(radians) * center
    cv2.line(
        kernel,
        (int(round(center - dx)), int(round(center - dy))),
        (int(round(center + dx)), int(round(center + dy))),
        1.0,
        1,
        cv2.LINE_AA,
    )
    return kernel / max(float(kernel.sum()), 1e-8)


def _advance_and_recover_hidden(
    metadata: dict[str, Any], parameter_seed: int, shape: tuple[int, int]
) -> dict[str, Any]:
    """Follow the frozen generator's RNG calls and retain unrecorded geometry."""
    family = str(metadata["family"])
    rng = np.random.default_rng(int(parameter_seed))
    rng.uniform()  # blur sigma draw
    rng.uniform()  # read-noise draw
    if float(metadata.get("blur_sigma_x", 0.0)) > 0.04:
        rng.uniform()  # anisotropic sigma ratio
    if family in {"motion_blur_low_noise", "severe_but_recoverable"}:
        choices = [3, 5] if family == "motion_blur_low_noise" else [3, 5, 7, 9]
        rng.choice(choices)
        rng.uniform()  # motion angle
    if family in {
        "boundary_halo_and_local_fade",
        "tile_mixed_recoverable",
        "severe_but_recoverable",
    }:
        rng.uniform()  # wide halo sigma
        rng.uniform()  # halo amplitude

    hidden: dict[str, Any] = {}
    if family in {"boundary_halo_and_local_fade", "severe_but_recoverable"}:
        h, w = shape
        center = rng.uniform(0.18, 0.82, 2) * np.asarray([w, h])
        rng.uniform()  # envelope radius, preserved in metadata
        hidden["fade_center_xy"] = [float(center[0]), float(center[1])]
        hidden["fade_blur_sigma"] = float(rng.uniform(5.0, 12.0))
        hidden["fade_local_base_sigma"] = float(rng.uniform(7.0, 15.0))
        rng.uniform()  # fade amount, preserved in metadata

    if family in {
        "exposure_and_illumination_path",
        "tile_mixed_recoverable",
        "severe_but_recoverable",
    }:
        rng.uniform()  # illumination strength, preserved in metadata
        hidden["illumination_angle"] = float(rng.uniform(0.0, 2.0 * np.pi))
        illumination_center = rng.uniform(-0.55, 0.55, 2)
        hidden["illumination_center_xy"] = [
            float(illumination_center[0]),
            float(illumination_center[1]),
        ]

    if metadata.get("exposure_coherent_profile") is None:
        rng.uniform()  # exposure
        rng.uniform()  # gamma
    return hidden


def recover_hidden_parameters(
    metadata: dict[str, Any], parameter_seed: int, canvas_shape: tuple[int, int]
) -> dict[str, Any]:
    """Public compact replay state; does not render or allocate a full image."""
    return _advance_and_recover_hidden(metadata, parameter_seed, canvas_shape)


def _illumination_field(
    shape: tuple[int, int], strength: float, angle: float, center_xy: list[float]
) -> np.ndarray:
    h, w = shape
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    xx = xx / max(w - 1, 1) * 2.0 - 1.0
    yy = yy / max(h - 1, 1) * 2.0 - 1.0
    gradient = math.cos(angle) * xx + math.sin(angle) * yy
    cx, cy = center_xy
    radius = np.sqrt((xx - cx) ** 2 + (yy - cy) ** 2)
    return 1.0 + float(strength) * (0.55 * gradient - 0.45 * radius)


def illumination_crop(
    *,
    canvas_shape: tuple[int, int],
    crop_yx: tuple[int, int],
    crop_shape: tuple[int, int],
    strength: float,
    angle: float,
    center_xy: list[float],
) -> np.ndarray:
    """Evaluate the frozen full-canvas illumination field on one crop."""
    canvas_h, canvas_w = canvas_shape
    y0, x0 = crop_yx
    crop_h, crop_w = crop_shape
    yy, xx = np.mgrid[y0 : y0 + crop_h, x0 : x0 + crop_w].astype(np.float32)
    xx = xx / max(canvas_w - 1, 1) * 2.0 - 1.0
    yy = yy / max(canvas_h - 1, 1) * 2.0 - 1.0
    gradient = math.cos(float(angle)) * xx + math.sin(float(angle)) * yy
    cx, cy = center_xy
    radius = np.sqrt((xx - cx) ** 2 + (yy - cy) ** 2)
    return 1.0 + float(strength) * (0.55 * gradient - 0.45 * radius)


def invert_radiometry(
    noise_free_u8: np.ndarray,
    metadata: dict[str, Any],
    hidden_parameters: dict[str, Any],
    *,
    canvas_shape: tuple[int, int],
    crop_yx: tuple[int, int] = (0, 0),
) -> np.ndarray:
    """Invert B to a compact on-demand estimate of the optical-only stage O."""
    image = noise_free_u8.astype(np.float32) / 255.0
    contrast_scale = hidden_parameters.get("contrast_scale")
    if contrast_scale is not None:
        center = float(hidden_parameters["contrast_center"])
        image = center + (image - center) / max(float(contrast_scale), 1e-8)
    gamma = float(metadata["gamma"])
    exposure = float(metadata["exposure"])
    image = np.clip(image, 0.0, 1.0) ** (1.0 / gamma)
    image = image / max(exposure, 1e-8)
    if "illumination_angle" in hidden_parameters:
        field = illumination_crop(
            canvas_shape=canvas_shape,
            crop_yx=crop_yx,
            crop_shape=image.shape,
            strength=float(metadata["illumination_strength"]),
            angle=float(hidden_parameters["illumination_angle"]),
            center_xy=list(hidden_parameters["illumination_center_xy"]),
        )
        image = image / np.maximum(field, 1e-6)
    return np.clip(image, 0.0, 1.0).astype(np.float32)


def _boundary_support(
    mask_u8: np.ndarray,
    metadata: dict[str, Any],
    fade: np.ndarray | None,
) -> np.ndarray:
    binary = (mask_u8 >= 128).astype(np.uint8)
    edge = cv2.morphologyEx(binary, cv2.MORPH_GRADIENT, np.ones((3, 3), np.uint8))
    sigma = max(
        float(metadata.get("blur_sigma_x", 0.0)),
        float(metadata.get("blur_sigma_y", 0.0)),
    )
    motion_half = max((int(metadata.get("motion_length", 1)) - 1) / 2.0, 0.0)
    halo = float(metadata.get("halo_sigma", 0.0))
    radius = int(np.clip(np.ceil(max(5.0, 3.0 * sigma, motion_half + 3.0, 2.0 * halo)), 5, 28))
    width = 2 * radius + 1
    spread = cv2.dilate(edge, np.ones((width, width), np.uint8)).astype(np.float32)
    spread = cv2.GaussianBlur(spread, (0, 0), sigmaX=2.0, borderType=cv2.BORDER_REFLECT_101)
    if fade is not None:
        spread = np.maximum(spread, fade.astype(np.float32))
    return np.clip(spread, 0.0, 1.0).astype(np.float32)


def boundary_support_from_metadata(
    mask_u8: np.ndarray,
    metadata: dict[str, Any],
) -> np.ndarray:
    """Create a cause-width-aware support on a crop with no full-canvas replay."""
    return _boundary_support(mask_u8, metadata, fade=None)


def shape_only_target(mask_u8: np.ndarray, texture_metadata: dict[str, Any]) -> np.ndarray:
    """Rebuild the anti-aliased mean-intensity geometry without material texture."""
    alpha_geometry = mask_u8.astype(np.float32) / 255.0
    epsilon = 1e-5
    clipped = np.clip(alpha_geometry, epsilon, 1.0 - epsilon)
    fraction = float(texture_metadata["physical_boundary_intensity_fraction"])
    bias = math.log(fraction / (1.0 - fraction))
    alpha = 1.0 / (1.0 + np.exp(-(np.log(clipped / (1.0 - clipped)) + bias)))
    alpha[alpha_geometry <= 0.0] = 0.0
    alpha[alpha_geometry >= 1.0] = 1.0
    foreground = float(texture_metadata["foreground_mean"])
    background = float(texture_metadata["background_mean"])
    shape = background * (1.0 - alpha) + foreground * alpha
    return cv2.GaussianBlur(
        shape.astype(np.float32), (0, 0), sigmaX=0.36,
        borderType=cv2.BORDER_REFLECT_101,
    )


def _phase_safe_optical_operator(
    image: np.ndarray,
    metadata: dict[str, Any],
) -> np.ndarray:
    """Apply blur, motion and symmetric halo before the local-fade stage."""
    family = str(metadata["family"])
    output = image.astype(np.float32).copy()
    sigma_x = float(metadata.get("blur_sigma_x", 0.0))
    sigma_y = float(metadata.get("blur_sigma_y", sigma_x))
    if sigma_x > 0.04:
        output = cv2.GaussianBlur(
            output, (0, 0), sigmaX=sigma_x, sigmaY=sigma_y,
            borderType=cv2.BORDER_REFLECT_101,
        )
    if family in {"motion_blur_low_noise", "severe_but_recoverable"}:
        output = cv2.filter2D(
            output, -1,
            _motion_kernel(int(metadata["motion_length"]), float(metadata["motion_angle"])),
            borderType=cv2.BORDER_REFLECT_101,
        )
    if family in {
        "boundary_halo_and_local_fade", "tile_mixed_recoverable", "severe_but_recoverable"
    }:
        wide = cv2.GaussianBlur(
            output, (0, 0), sigmaX=float(metadata["halo_sigma"]),
            borderType=cv2.BORDER_REFLECT_101,
        )
        output = output + float(metadata["halo_amplitude"]) * (output - wide)
    return output.astype(np.float32)


def _local_fade_operator(
    image: np.ndarray,
    mask_u8: np.ndarray,
    metadata: dict[str, Any],
    hidden: dict[str, Any],
    *,
    crop_yx: tuple[int, int] = (0, 0),
) -> np.ndarray:
    """Apply only the spatially varying local boundary-fade stage."""
    family = str(metadata["family"])
    output = image.astype(np.float32).copy()
    if family in {"boundary_halo_and_local_fade", "severe_but_recoverable"}:
        boundary = cv2.morphologyEx(
            (mask_u8 >= 128).astype(np.uint8), cv2.MORPH_GRADIENT,
            np.ones((5, 5), np.uint8),
        ).astype(np.float32)
        h, w = output.shape
        y0, x0 = crop_yx
        yy, xx = np.mgrid[y0 : y0 + h, x0 : x0 + w].astype(np.float32)
        cx, cy = hidden["fade_center_xy"]
        radius = float(metadata["boundary_fade_radius"])
        envelope = np.exp(-((xx - cx) ** 2 + (yy - cy) ** 2) / max(2.0 * radius * radius, 1.0))
        fade = cv2.GaussianBlur(
            boundary * envelope, (0, 0), float(hidden["fade_blur_sigma"]),
            borderType=cv2.BORDER_REFLECT_101,
        )
        fade_normalizer = float(hidden.get("fade_normalizer", float(fade.max())))
        fade /= max(fade_normalizer, 1e-6)
        local_base = cv2.GaussianBlur(
            output, (0, 0), float(hidden["fade_local_base_sigma"]),
            borderType=cv2.BORDER_REFLECT_101,
        )
        amount = float(metadata["boundary_fade_amount"])
        output = output * (1.0 - amount * fade) + local_base * (amount * fade)
    return output.astype(np.float32)


def _optical_linear_operator(
    image: np.ndarray,
    mask_u8: np.ndarray,
    metadata: dict[str, Any],
    hidden: dict[str, Any],
    *,
    canvas_shape: tuple[int, int] | None = None,
    crop_yx: tuple[int, int] = (0, 0),
) -> np.ndarray:
    """Apply the frozen pre-radiometric optical degradation stages."""
    del canvas_shape  # Geometry is expressed by global crop coordinates below.
    prefade = _phase_safe_optical_operator(image, metadata)
    return _local_fade_operator(prefade, mask_u8, metadata, hidden, crop_yx=crop_yx)


def decompose_optical_layers(
    target_u8: np.ndarray,
    mask_u8: np.ndarray,
    texture_metadata: dict[str, Any],
    degradation_metadata: dict[str, Any],
    parameter_seed: int,
    *,
    canvas_shape: tuple[int, int] | None = None,
    crop_yx: tuple[int, int] = (0, 0),
    hidden_parameters: dict[str, Any] | None = None,
) -> OpticalLayerTargets:
    """Exact additive geometry-versus-material optical correction targets."""
    clean = target_u8.astype(np.float32) / 255.0
    full_shape = clean.shape if canvas_shape is None else canvas_shape
    hidden = (
        _advance_and_recover_hidden(degradation_metadata, parameter_seed, full_shape)
        if hidden_parameters is None
        else hidden_parameters
    )
    shape_clean = shape_only_target(mask_u8, texture_metadata)
    texture_clean = clean - shape_clean
    operator_args = {
        "canvas_shape": full_shape,
        "crop_yx": crop_yx,
    }
    shape_prefade = _phase_safe_optical_operator(shape_clean, degradation_metadata)
    texture_prefade = _phase_safe_optical_operator(texture_clean, degradation_metadata)
    shape_optical = _local_fade_operator(
        shape_prefade, mask_u8, degradation_metadata, hidden, crop_yx=crop_yx
    )
    texture_optical = _local_fade_operator(
        texture_prefade, mask_u8, degradation_metadata, hidden, crop_yx=crop_yx
    )
    total_optical = _optical_linear_operator(
        clean, mask_u8, degradation_metadata, hidden, **operator_args
    )
    boundary_target = shape_clean - shape_prefade
    texture_target = texture_clean - texture_prefade
    local_contrast_target = (shape_prefade + texture_prefade) - (shape_optical + texture_optical)
    recomposed = shape_optical + texture_optical
    return OpticalLayerTargets(
        boundary_target.astype(np.float32),
        texture_target.astype(np.float32),
        local_contrast_target.astype(np.float32),
        shape_clean.astype(np.float32),
        shape_prefade.astype(np.float32),
        shape_optical.astype(np.float32),
        texture_clean.astype(np.float32),
        texture_prefade.astype(np.float32),
        texture_optical.astype(np.float32),
        float(np.max(np.abs(recomposed - total_optical))),
    )


def replay_causal_stages(
    target_u8: np.ndarray,
    mask_u8: np.ndarray,
    metadata: dict[str, Any],
    parameter_seed: int,
) -> ReplayResult:
    """Replay O and B exactly from one shifted procedural target and mask."""
    if target_u8.shape != mask_u8.shape or target_u8.ndim != 2:
        raise ValueError("target and mask must be equally sized grayscale arrays")
    family = str(metadata["family"])
    hidden = _advance_and_recover_hidden(metadata, parameter_seed, target_u8.shape)
    image = target_u8.astype(np.float32) / 255.0

    sigma_x = float(metadata.get("blur_sigma_x", 0.0))
    sigma_y = float(metadata.get("blur_sigma_y", sigma_x))
    if sigma_x > 0.04:
        image = cv2.GaussianBlur(
            image, (0, 0), sigmaX=sigma_x, sigmaY=sigma_y,
            borderType=cv2.BORDER_REFLECT_101,
        )

    if family in {"motion_blur_low_noise", "severe_but_recoverable"}:
        image = cv2.filter2D(
            image,
            -1,
            _motion_kernel(int(metadata["motion_length"]), float(metadata["motion_angle"])),
            borderType=cv2.BORDER_REFLECT_101,
        )

    if family in {
        "boundary_halo_and_local_fade",
        "tile_mixed_recoverable",
        "severe_but_recoverable",
    }:
        wide = cv2.GaussianBlur(
            image, (0, 0), sigmaX=float(metadata["halo_sigma"]),
            borderType=cv2.BORDER_REFLECT_101,
        )
        image = image + float(metadata["halo_amplitude"]) * (image - wide)

    fade: np.ndarray | None = None
    if family in {"boundary_halo_and_local_fade", "severe_but_recoverable"}:
        boundary = cv2.morphologyEx(
            (mask_u8 >= 128).astype(np.uint8),
            cv2.MORPH_GRADIENT,
            np.ones((5, 5), np.uint8),
        ).astype(np.float32)
        h, w = image.shape
        yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
        cx, cy = hidden["fade_center_xy"]
        radius = float(metadata["boundary_fade_radius"])
        envelope = np.exp(
            -((xx - cx) ** 2 + (yy - cy) ** 2) / max(2.0 * radius * radius, 1.0)
        )
        fade = cv2.GaussianBlur(
            boundary * envelope,
            (0, 0),
            float(hidden["fade_blur_sigma"]),
            borderType=cv2.BORDER_REFLECT_101,
        )
        fade_normalizer = float(fade.max())
        hidden["fade_normalizer"] = fade_normalizer
        fade /= max(fade_normalizer, 1e-6)
        local_base = cv2.GaussianBlur(
            image,
            (0, 0),
            float(hidden["fade_local_base_sigma"]),
            borderType=cv2.BORDER_REFLECT_101,
        )
        amount = float(metadata["boundary_fade_amount"])
        image = image * (1.0 - amount * fade) + local_base * (amount * fade)

    optical = image.astype(np.float32).copy()

    if family in {
        "exposure_and_illumination_path",
        "tile_mixed_recoverable",
        "severe_but_recoverable",
    }:
        image *= _illumination_field(
            image.shape,
            float(metadata["illumination_strength"]),
            float(hidden["illumination_angle"]),
            list(hidden["illumination_center_xy"]),
        )

    image = np.power(
        np.clip(image * float(metadata["exposure"]), 0.0, 1.0),
        float(metadata["gamma"]),
    )
    requested = metadata.get("requested_source_contrast_gray")
    if requested is not None:
        current = float(np.percentile(image, 95) - np.percentile(image, 5))
        if current > 1e-6:
            center = float(np.median(image))
            deterministic_target = max(float(requested) / 255.0 - 8.0 / 255.0, 0.02)
            contrast_scale = deterministic_target / current
            hidden["contrast_center"] = center
            hidden["contrast_scale"] = float(contrast_scale)
            image = center + contrast_scale * (image - center)
    image = np.clip(image, 0.0, 1.0)
    replayed_b = np.rint(image * 255.0).astype(np.uint8)
    support = _boundary_support(mask_u8, metadata, fade)
    return ReplayResult(optical, replayed_b, support, hidden)


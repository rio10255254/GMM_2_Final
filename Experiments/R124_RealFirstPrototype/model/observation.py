"""Fixed local acquisition operator with an exact, boundary-aware transpose.

``kernel`` uses the literal PyTorch correlation convention: forward applies
``conv2d(x, kernel, padding=radius)`` followed by non-overlapping cell averaging,
then a constant calibrated gain and bias.  An asymmetric kernel's impulse
response therefore has the *opposite* centroid from its array coordinates. A
physical impulse-response PSF must be flipped once by the calibration loader.
This module never recenters, symmetrizes, normalizes, or fits calibration data.

The image is zero outside its finite domain. This deliberate boundary rule makes
the transpose exact; it is not a claim that a real field of view is dark outside
the sensor. Tiled inference must supply the declared surrounding context and
discard the affected artificial boundaries. Inputs/outputs use NCHW coordinates.

All calibration values are non-trainable buffers. Their provenance/qualification
is explicit; mathematical consistency does not qualify a real instrument model.
"""

from __future__ import annotations

import math
from numbers import Integral
from typing import Any

import torch
from torch import Tensor, nn
from torch.nn import functional as F


def _scalar(value: Any, name: str, *, positive: bool = False) -> float:
    if isinstance(value, bool):
        raise ValueError(f"{name} must be a finite real scalar, not bool")
    if isinstance(value, Tensor):
        if value.numel() != 1 or value.ndim != 0 or value.is_complex():
            raise ValueError(f"{name} must be a finite real scalar")
        value = value.detach().cpu().item()
    try:
        result = float(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError(f"{name} must be a finite real scalar") from exc
    if not math.isfinite(result) or (positive and result <= 0):
        requirement = "finite and positive" if positive else "finite"
        raise ValueError(f"{name} must be {requirement}")
    return result


class LinearObservation(nn.Module):
    """Affine acquisition ``gain * P(Kx) + bias`` and its linear adjoint.

    The quadratic observation objective is **a sum**, not a per-pixel mean:
    ``0.5 * sum((forward(x) - y)**2 / noise_variance)``. For spatially constant
    positive gain and variance, an independent curvature upper bound is
    ``gain**2 * ||kernel||_1**2 / (factor**2 * noise_variance)``. This follows
    from the finite zero-extension convolution norm bound and from the exact
    norm ``1/factor`` of two-dimensional non-overlapping area averaging. The
    returned bound includes a small floating-point margin. A gradient step
    with ``0 < eta < 2 / bound`` cannot increase the exact quadratic objective
    in exact arithmetic; this says nothing about a preceding learned proposal
    or whether the acquisition assumptions match the specimen.
    """

    kernel_convention = "correlation"
    boundary_mode = "zero"

    def __init__(
        self,
        kernel: Tensor,
        sampling_factor: int = 2,
        gain: float = 1.0,
        bias: float = 0.0,
        noise_variance: float = 1.0,
        calibration_id: str = "unspecified_diagnostic",
        qualification: str = "unqualified_diagnostic",
    ) -> None:
        super().__init__()
        if isinstance(sampling_factor, bool) or not isinstance(sampling_factor, Integral):
            raise ValueError("sampling_factor must be a positive integer")
        if sampling_factor <= 0:
            raise ValueError("sampling_factor must be a positive integer")
        self.sampling_factor = int(sampling_factor)
        if not isinstance(kernel, Tensor) or not kernel.is_floating_point():
            raise ValueError("kernel must be a real floating-point Tensor")
        if kernel.ndim != 2 or kernel.shape[0] != kernel.shape[1] or kernel.shape[0] % 2 != 1:
            raise ValueError("kernel must be a nonempty odd square 2D Tensor")
        if kernel.shape[0] == 0:
            raise ValueError("kernel must be nonempty")
        if (kernel.shape[0] - 1) // 2 > 16 * self.sampling_factor:
            raise ValueError("kernel radius must not exceed 16 native pixels")
        checked = kernel.detach().to(device="cpu", dtype=torch.float64)
        if not bool(torch.isfinite(checked).all()) or bool((checked < 0).any()):
            raise ValueError("kernel must contain finite nonnegative coefficients")
        # Do not silently renormalize a calibration. Allow only its storage error.
        tolerance = max(1e-12, 8 * torch.finfo(kernel.dtype).eps)
        if not math.isclose(float(checked.sum()), 1.0, rel_tol=tolerance, abs_tol=tolerance):
            raise ValueError("kernel must already sum to one; no automatic normalization")
        for name, value in (("calibration_id", calibration_id), ("qualification", qualification)):
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{name} must be a nonempty string")
        self.calibration_id = calibration_id
        self.qualification = qualification
        self.register_buffer("kernel", kernel.detach().clone())
        for name, value, positive in (
            ("gain", gain, True),
            ("bias", bias, False),
            ("noise_variance", noise_variance, True),
        ):
            numeric = _scalar(value, name, positive=positive)
            stored = self.kernel.new_tensor(numeric)
            if not bool(torch.isfinite(stored)) or (positive and not bool(stored > 0)):
                raise ValueError(f"{name} is not representable in the kernel dtype")
            self.register_buffer(name, stored)
        bound = self.curvature_bound()
        if not bool(torch.isfinite(bound)) or not bool(bound > 0):
            raise ValueError("calibration produces a nonfinite or zero curvature bound")

    @property
    def kernel_radius_internal(self) -> int:
        return (int(self.kernel.shape[0]) - 1) // 2

    @property
    def kernel_centroid_internal_xy(self) -> Tensor:
        """Centroid of stored coefficients, relative to the central pixel."""
        coordinates = torch.arange(
            -self.kernel_radius_internal,
            self.kernel_radius_internal + 1,
            dtype=self.kernel.dtype,
            device=self.kernel.device,
        )
        mass = self.kernel.sum()
        return torch.stack(
            ((self.kernel * coordinates[None, :]).sum() / mass,
             (self.kernel * coordinates[:, None]).sum() / mass)
        )

    @property
    def impulse_centroid_internal_xy(self) -> Tensor:
        """Centroid displacement of an impulse sufficiently far from the border."""
        return -self.kernel_centroid_internal_xy

    def get_extra_state(self) -> dict[str, str | int]:
        return {
            "calibration_id": self.calibration_id,
            "qualification": self.qualification,
            "sampling_factor": self.sampling_factor,
            "kernel_convention": self.kernel_convention,
            "boundary_mode": self.boundary_mode,
        }

    def set_extra_state(self, state: dict[str, Any]) -> None:
        if not isinstance(state, dict):
            raise ValueError("observation provenance state must be a dictionary")
        for name in ("sampling_factor", "kernel_convention", "boundary_mode"):
            if state.get(name) != getattr(self, name):
                raise ValueError(f"checkpoint observation {name} does not match construction")
        for name in ("calibration_id", "qualification"):
            value = state.get(name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"checkpoint {name} must be a nonempty string")
            setattr(self, name, value)

    def _check_image(self, value: Tensor, name: str, *, internal: bool = False) -> None:
        if not isinstance(value, Tensor) or value.ndim != 4 or any(size < 1 for size in value.shape):
            raise ValueError(f"{name} must be a nonempty NCHW Tensor")
        if value.dtype != self.kernel.dtype or value.device != self.kernel.device:
            raise ValueError(f"{name} dtype/device must match the observation module")
        if internal and any(size % self.sampling_factor for size in value.shape[-2:]):
            raise ValueError(f"{name} internal height and width must be divisible by sampling_factor")

    def _weights(self, channels: int) -> Tensor:
        return self.kernel[None, None, :, :].expand(channels, 1, -1, -1)

    def integrate(self, x: Tensor) -> Tensor:
        """Area-average internal cells into native pixels, without optics or gain."""
        self._check_image(x, "x", internal=True)
        return F.avg_pool2d(x, self.sampling_factor, stride=self.sampling_factor)

    def lift(self, y: Tensor) -> Tensor:
        """Repeat a native pixel average into its cells; P(lift(y)) equals y.

        This is an initialization, not the transpose of averaging. That
        transpose is ``lift(y) / sampling_factor**2``.
        """
        self._check_image(y, "y")
        return y.repeat_interleave(self.sampling_factor, dim=-2).repeat_interleave(
            self.sampling_factor, dim=-1
        )

    def forward(self, x: Tensor) -> Tensor:
        self._check_image(x, "x", internal=True)
        blurred = F.conv2d(
            x, self._weights(x.shape[1]), padding=self.kernel_radius_internal, groups=x.shape[1]
        )
        return self.gain * self.integrate(blurred) + self.bias

    def adjoint(self, y: Tensor) -> Tensor:
        """Exact transpose of the linear part; the additive bias has no adjoint."""
        lifted = self.lift(y) * (self.gain / self.sampling_factor**2)
        return F.conv_transpose2d(
            lifted,
            self._weights(y.shape[1]),
            padding=self.kernel_radius_internal,
            groups=y.shape[1],
        )

    def residual_gradient(self, x: Tensor, y: Tensor) -> Tensor:
        self._check_image(y, "y")
        prediction = self.forward(x)
        if prediction.shape != y.shape:
            raise ValueError("observed y must have exactly the forward output shape; broadcasting is forbidden")
        return self.adjoint((prediction - y) / self.noise_variance)

    def curvature_bound(self) -> Tensor:
        """Analytic global upper bound for the sum-of-squares Hessian norm."""
        # A small guard covers rounding in accumulation and arithmetic. No power
        # iteration, learned bound, per-image statistics, or periodic FFT is used.
        margin = 1.0 + 64.0 * torch.finfo(self.kernel.dtype).eps
        return (
            self.gain.square() * self.kernel.abs().sum().square()
            / (self.sampling_factor**2 * self.noise_variance)
        ) * margin

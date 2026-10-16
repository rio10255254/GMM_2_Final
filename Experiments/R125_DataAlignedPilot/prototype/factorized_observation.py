"""Fixed low-rank implementation of an unchanged, explicitly retained PSF.

The implemented kernel is an approximation, with a declared L1 bound of 1e-6.
No refitting, normalization, recentering, clipping, or Fourier boundary wrapping
is performed.  The transpose is exact for the implemented finite-domain factors
(up to floating-point arithmetic), not claimed exact for the original kernel.
"""
from __future__ import annotations

import copy
import math
import sys
from pathlib import Path

import torch
from torch import Tensor
from torch.nn import functional as F
from torch.utils.checkpoint import checkpoint

BASE = Path(__file__).resolve().parents[2] / "R124_RealFirstPrototype"
if str(BASE) not in sys.path:
    sys.path.insert(0, str(BASE))
from model.observation import LinearObservation

KERNEL_L1_TOLERANCE = 1e-6
FACTORIZATION_ALGORITHM = "float64_svd_minimum_rank_dtype_stored_L1_v1"


class FixedFactorizedObservation(LinearObservation):
    """Grouped horizontal/vertical passes with frozen, auditable coefficients."""

    def __init__(self, kernel: Tensor, sampling_factor: int = 4, gain: float = 1.0,
                 bias: float = 0.0, noise_variance: float = 1.0,
                 calibration_id: str = "unspecified_diagnostic",
                 qualification: str = "unqualified_diagnostic", *,
                 checkpoint_ops: bool = True):
        if type(checkpoint_ops) is not bool:
            raise ValueError("checkpoint_ops must be bool")
        # LinearObservation validates and retains the original provided kernel.
        # Its constructor invokes curvature_bound before factors are installed.
        super().__init__(kernel, sampling_factor, gain, bias, noise_variance,
                         calibration_id, qualification)
        self.checkpoint_ops = checkpoint_ops
        self._provenance_extras = {}
        self._install_factors()

    @classmethod
    def from_observation(cls, base: LinearObservation, *, checkpoint_ops: bool = True):
        if not isinstance(base, LinearObservation):
            raise TypeError("Expected a LinearObservation-compatible calibrated operator")
        result = cls(base.kernel, base.sampling_factor, float(base.gain), float(base.bias),
                     float(base.noise_variance), base.calibration_id, base.qualification,
                     checkpoint_ops=checkpoint_ops)
        result._provenance_extras = copy.deepcopy(base.get_extra_state())
        result._provenance_extras.pop("factorization", None)
        if hasattr(base, "profile"):
            result.profile = copy.deepcopy(base.profile)
        result.train(base.training)
        return result

    def _install_factors(self):
        original = self.kernel.detach().to(device="cpu", dtype=torch.float64)
        u, singular, vh = torch.linalg.svd(original, full_matrices=False)
        selected = None
        for rank in range(1, len(singular) + 1):
            root = singular[:rank].clamp_min(0).sqrt()
            # Balanced scaling limits unnecessary factor storage dynamic range.
            vertical64 = u[:, :rank].T * root[:, None]
            horizontal64 = vh[:rank] * root[:, None]
            vertical = vertical64.to(dtype=self.kernel.dtype)
            horizontal = horizontal64.to(dtype=self.kernel.dtype)
            implemented = vertical.double().T @ horizontal.double()
            error = float((implemented - original).abs().sum())
            if error <= KERNEL_L1_TOLERANCE:
                selected = (rank, vertical, horizontal,
                            float(((vertical64.T @ horizontal64) - original).abs().sum()))
                break
        if selected is None:
            raise ValueError("No stored-factor rank satisfies the fixed kernel L1 tolerance")
        rank, vertical, horizontal, truncation_error = selected
        vertical = vertical.to(device=self.kernel.device)
        horizontal = horizontal.to(device=self.kernel.device)
        if "vertical_factors" in self._buffers:
            self.vertical_factors = vertical
            self.horizontal_factors = horizontal
        else:
            self.register_buffer("vertical_factors", vertical)
            self.register_buffer("horizontal_factors", horizontal)
        self.rank = rank
        self.float64_truncation_L1_error = truncation_error
        self._refresh_diagnostics()

    def _refresh_diagnostics(self):
        """Called only at construction/dtype conversion/state loading, not per image."""
        original = self.kernel.detach().to(device="cpu", dtype=torch.float64)
        v = self.vertical_factors.detach().to(device="cpu", dtype=torch.float64)
        h = self.horizontal_factors.detach().to(device="cpu", dtype=torch.float64)
        implemented = v.T @ h
        self.original_kernel_L1 = float(original.abs().sum())
        self.measured_kernel_L1_error = float((implemented-original).abs().sum())
        if self.measured_kernel_L1_error > KERNEL_L1_TOLERANCE:
            raise ValueError("Stored factors exceed declared original-kernel L1 tolerance")
        self.factor_product_L1_sum = float((v.abs().sum(1) * h.abs().sum(1)).sum())
        self.implemented_kernel_minimum = float(implemented.min())
        self.implemented_kernel_mass = float(implemented.sum())
        radius = self.kernel_radius_internal
        coordinates = torch.arange(-radius, radius+1, dtype=torch.float64)
        def centroid(kernel):
            return torch.stack(((kernel*coordinates[None, :]).sum(), (kernel*coordinates[:, None]).sum())) / kernel.sum()
        source_centroid, actual_centroid = centroid(original), centroid(implemented)
        self.original_centroid_internal_xy = source_centroid.tolist()
        self.implemented_centroid_internal_xy = actual_centroid.tolist()
        self.centroid_difference_internal_xy = (actual_centroid-source_centroid).tolist()
        self.centroid_difference_native_xy = ((actual_centroid-source_centroid)/self.sampling_factor).tolist()

    def _apply(self, fn, recurse=True):
        before = self.kernel.dtype
        result = super()._apply(fn, recurse=recurse)
        # An explicit dtype conversion changes storage error. Re-factor the same
        # converted original instead of retaining stale error/centroid claims.
        if self.kernel.dtype != before and "vertical_factors" in self._buffers:
            self._install_factors()
        return result

    def _factor_weights(self, channels: int):
        width = self.kernel.shape[0]
        horizontal = self.horizontal_factors.repeat(channels, 1).reshape(channels*self.rank, 1, 1, width)
        vertical = self.vertical_factors[None, :, :, None].expand(channels, -1, -1, -1)
        return horizontal, vertical

    def _blur(self, image: Tensor):
        horizontal, vertical = self._factor_weights(image.shape[1])
        r = self.kernel_radius_internal
        temporary = F.conv2d(image, horizontal, padding=(0, r), groups=image.shape[1])
        return F.conv2d(temporary, vertical, padding=(r, 0), groups=image.shape[1])

    def _blur_transpose(self, image: Tensor):
        horizontal, vertical = self._factor_weights(image.shape[1])
        r = self.kernel_radius_internal
        temporary = F.conv_transpose2d(image, vertical, padding=(r, 0), groups=image.shape[1])
        return F.conv_transpose2d(temporary, horizontal, padding=(0, r), groups=image.shape[1])

    def _fixed_operation(self, operation, image):
        if self.checkpoint_ops and torch.is_grad_enabled() and image.requires_grad:
            return checkpoint(operation, image, use_reentrant=False)
        return operation(image)

    def forward(self, x: Tensor) -> Tensor:
        self._check_image(x, "x", internal=True)
        blurred = self._fixed_operation(self._blur, x)
        return self.gain*self.integrate(blurred)+self.bias

    def adjoint(self, y: Tensor) -> Tensor:
        lifted = self.lift(y)*(self.gain/self.sampling_factor**2)
        return self._fixed_operation(self._blur_transpose, lifted)

    def numerical_factor_reconstruction_margin(self):
        eps = torch.finfo(self.kernel.dtype).eps
        # Covers rank accumulation and factor-product rounding; this changes the
        # safe curvature bound only, never factors or the retained source kernel.
        return 8.0*(self.rank+2)*eps*(self.factor_product_L1_sum+self.original_kernel_L1)

    def curvature_bound(self) -> Tensor:
        if not hasattr(self, "rank"):
            return LinearObservation.curvature_bound(self)
        eps = torch.finfo(self.kernel.dtype).eps
        upper_l1 = self.kernel.abs().sum() + self.measured_kernel_L1_error + self.numerical_factor_reconstruction_margin()
        return self.gain.square()*upper_l1.square()/(self.sampling_factor**2*self.noise_variance)*(1+64*eps)

    def factorization_metadata(self):
        return {"algorithm": FACTORIZATION_ALGORITHM, "rank": self.rank,
                "kernel_L1_tolerance": KERNEL_L1_TOLERANCE,
                "measured_kernel_L1_error": self.measured_kernel_L1_error,
                "float64_truncation_L1_error": self.float64_truncation_L1_error,
                "implemented_kernel_mass": self.implemented_kernel_mass,
                "implemented_kernel_minimum": self.implemented_kernel_minimum,
                "original_centroid_internal_xy": self.original_centroid_internal_xy,
                "implemented_centroid_internal_xy": self.implemented_centroid_internal_xy,
                "centroid_difference_internal_xy": self.centroid_difference_internal_xy,
                "centroid_difference_native_xy": self.centroid_difference_native_xy,
                "numerical_factor_reconstruction_margin": self.numerical_factor_reconstruction_margin(),
                "checkpoint_ops": self.checkpoint_ops,
                "original_kernel_retained": True, "exact_original_kernel_claimed": False,
                "transpose_target": "implemented_finite_domain_factor_operator",
                "kernel_convention": "correlation", "boundary_mode": "zero"}

    def get_extra_state(self):
        state = copy.deepcopy(getattr(self, "_provenance_extras", {}))
        state.update(super().get_extra_state())
        state["factorization"] = self.factorization_metadata()
        return state

    def set_extra_state(self, state):
        super().set_extra_state(state)
        metadata = state.get("factorization")
        if not isinstance(metadata, dict) or metadata.get("algorithm") != FACTORIZATION_ALGORITHM:
            raise ValueError("Missing or incompatible fixed-factor provenance")
        if metadata.get("kernel_L1_tolerance") != KERNEL_L1_TOLERANCE or metadata.get("rank") != self.rank:
            raise ValueError("Factor rank/tolerance differs from constructed operator")
        self._refresh_diagnostics()
        if abs(metadata.get("measured_kernel_L1_error", math.inf)-self.measured_kernel_L1_error) > 1e-12:
            raise ValueError("Serialized factor error does not describe restored factors")
        self._provenance_extras = copy.deepcopy(state)
        self._provenance_extras.pop("factorization", None)
        self.float64_truncation_L1_error = float(metadata["float64_truncation_L1_error"])
        checkpoint_ops = metadata.get("checkpoint_ops")
        if type(checkpoint_ops) is not bool:
            raise ValueError("Invalid serialized checkpoint setting")
        self.checkpoint_ops = checkpoint_ops


def from_observation(base: LinearObservation, *, checkpoint_ops: bool = True):
    return FixedFactorizedObservation.from_observation(base, checkpoint_ops=checkpoint_ops)

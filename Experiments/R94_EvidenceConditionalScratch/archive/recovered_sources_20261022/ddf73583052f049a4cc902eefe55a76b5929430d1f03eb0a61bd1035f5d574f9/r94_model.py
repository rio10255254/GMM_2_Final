"""Evidence-conditional, measurement-preserving R94 reconstruction model."""
from __future__ import annotations

from typing import Any

import torch
from torch import nn
import torch.nn.functional as F


def _pad_local(x: torch.Tensor, amount: int) -> torch.Tensor:
    if amount <= 0:
        return x
    mode = "reflect" if x.shape[-2] > amount and x.shape[-1] > amount else "replicate"
    return F.pad(x, (amount, amount, amount, amount), mode=mode)


def _binomial_kernel(size: int) -> torch.Tensor:
    rows = {
        3: torch.tensor([1.0, 2.0, 1.0]),
        5: torch.tensor([1.0, 4.0, 6.0, 4.0, 1.0]),
        7: torch.tensor([1.0, 6.0, 15.0, 20.0, 15.0, 6.0, 1.0]),
        17: torch.tensor([1, 16, 120, 560, 1820, 4368, 8008, 11440, 12870, 11440, 8008, 4368, 1820, 560, 120, 16, 1], dtype=torch.float32),
    }
    vector = rows[int(size)]
    kernel = torch.outer(vector, vector)
    return kernel / kernel.sum()


class FixedFilter(nn.Module):
    def __init__(self, kernel: torch.Tensor, *, dilation: int = 1):
        super().__init__()
        self.dilation = int(dilation)
        if self.dilation < 1:
            raise ValueError("dilation must be positive")
        self.radius_y = int(kernel.shape[0] // 2) * self.dilation
        self.radius_x = int(kernel.shape[1] // 2) * self.dilation
        self.register_buffer("kernel", kernel.float().view(1, 1, *kernel.shape))

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        channels = int(x.shape[1])
        kernel = self.kernel.to(dtype=x.dtype).repeat(channels, 1, 1, 1)
        mode = (
            "reflect"
            if x.shape[-2] > self.radius_y and x.shape[-1] > self.radius_x
            else "replicate"
        )
        padded = F.pad(
            x,
            (self.radius_x, self.radius_x, self.radius_y, self.radius_y),
            mode=mode,
        )
        return F.conv2d(padded, kernel, groups=channels, dilation=self.dilation)

    def effective_kernel(self) -> torch.Tensor:
        kernel = self.kernel[0, 0]
        if self.dilation == 1:
            return kernel
        height = (int(kernel.shape[0]) - 1) * self.dilation + 1
        width = (int(kernel.shape[1]) - 1) * self.dilation + 1
        effective = torch.zeros((height, width), dtype=kernel.dtype, device=kernel.device)
        effective[:: self.dilation, :: self.dilation] = kernel
        return effective


def _directional_kernel(size: int, axis: str) -> torch.Tensor:
    vector = _binomial_kernel(size)[size // 2]
    vector = vector / vector.sum()
    if axis == "x":
        return vector.view(1, size)
    if axis == "y":
        return vector.view(size, 1)
    raise ValueError(f"Unsupported axis: {axis}")


def _line_kernel(size: int, angle_degrees: float, width: float = 0.48) -> torch.Tensor:
    """Symmetric anti-aliased line kernel for zero-phase directional blur."""
    radius = (size - 1) / 2.0
    coordinate = torch.arange(size, dtype=torch.float32) - radius
    yy, xx = torch.meshgrid(coordinate, coordinate, indexing="ij")
    angle = torch.tensor(float(angle_degrees) * torch.pi / 180.0)
    along = torch.cos(angle) * xx + torch.sin(angle) * yy
    perpendicular = -torch.sin(angle) * xx + torch.cos(angle) * yy
    support = (along.abs() <= radius + 0.25).to(torch.float32)
    kernel = torch.exp(-0.5 * (perpendicular / float(width)).square()) * support
    kernel = 0.5 * (kernel + torch.flip(kernel, dims=(0, 1)))
    return kernel / kernel.sum().clamp_min(1e-8)


def _gaussian_kernel(size: int, sigma: float) -> torch.Tensor:
    radius = (int(size) - 1) / 2.0
    coordinate = torch.arange(int(size), dtype=torch.float32) - radius
    vector = torch.exp(-0.5 * (coordinate / float(sigma)).square())
    vector = vector / vector.sum().clamp_min(1e-8)
    return torch.outer(vector, vector)


class FixedSeparableGaussian(nn.Module):
    """Efficient large local-average operator with symmetric zero-phase kernels."""

    def __init__(self, sigma: float, radius: int | None = None):
        super().__init__()
        selected_radius = (
            int(torch.ceil(torch.tensor(3.0 * float(sigma))).item())
            if radius is None
            else int(radius)
        )
        coordinate = torch.arange(-selected_radius, selected_radius + 1, dtype=torch.float32)
        vector = torch.exp(-0.5 * (coordinate / float(sigma)).square())
        vector = vector / vector.sum().clamp_min(1e-8)
        self.radius = selected_radius
        self.register_buffer("kernel_x", vector.view(1, 1, 1, -1))
        self.register_buffer("kernel_y", vector.view(1, 1, -1, 1))

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        channels = int(x.shape[1])
        mode = "reflect" if x.shape[-2] > self.radius and x.shape[-1] > self.radius else "replicate"
        kernel_x = self.kernel_x.to(dtype=x.dtype).repeat(channels, 1, 1, 1)
        kernel_y = self.kernel_y.to(dtype=x.dtype).repeat(channels, 1, 1, 1)
        horizontal = F.conv2d(
            F.pad(x, (self.radius, self.radius, 0, 0), mode=mode),
            kernel_x,
            groups=channels,
        )
        return F.conv2d(
            F.pad(horizontal, (0, 0, self.radius, self.radius), mode=mode),
            kernel_y,
            groups=channels,
        )

    def effective_kernel(self) -> torch.Tensor:
        vector = self.kernel_x[0, 0, 0]
        return torch.outer(vector, vector)


class ConvAct(nn.Module):
    def __init__(self, c_in: int, c_out: int, *, activate: bool = True):
        super().__init__()
        self.conv = nn.Conv2d(c_in, c_out, 3, padding=1)
        self.act = nn.SiLU(inplace=True) if activate else nn.Identity()

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.act(self.conv(x))


class ResidualBlock(nn.Module):
    def __init__(self, channels: int, scale: float = 0.1):
        super().__init__()
        self.a = ConvAct(channels, channels)
        self.b = ConvAct(channels, channels, activate=False)
        self.scale = float(scale)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return F.silu(x + self.scale * self.b(self.a(x)))


class AntiAliasedDownsample(nn.Module):
    def __init__(self, c_in: int, c_out: int):
        super().__init__()
        self.blur = FixedFilter(_binomial_kernel(5))
        self.conv = nn.Conv2d(c_in, c_out, 3, stride=2, padding=1)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.conv(self.blur(x))


class AntiAliasedUpsample(nn.Module):
    def __init__(self, c_in: int, c_out: int):
        super().__init__()
        self.blur = FixedFilter(_binomial_kernel(3))
        self.conv = nn.Conv2d(c_in, c_out, 3, padding=1)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.conv(self.blur(F.interpolate(x, scale_factor=2, mode="bilinear", align_corners=False)))


class LocalOpticalMeasurements(nn.Module):
    """Fixed, translation-equivariant measurements shared without learned weights."""

    def __init__(self):
        super().__init__()
        self.g3 = FixedFilter(_binomial_kernel(3))
        self.g5 = FixedFilter(_binomial_kernel(5))
        self.g7 = FixedFilter(_binomial_kernel(7))
        sobel = torch.tensor([[-1.0, 0.0, 1.0], [-2.0, 0.0, 2.0], [-1.0, 0.0, 1.0]]) / 8.0
        self.register_buffer("sobel_x", sobel.view(1, 1, 3, 3))
        self.register_buffer("sobel_y", sobel.t().contiguous().view(1, 1, 3, 3))
        lap = torch.tensor([[0.0, 1.0, 0.0], [1.0, -4.0, 1.0], [0.0, 1.0, 0.0]])
        self.register_buffer("laplacian", lap.view(1, 1, 3, 3))

    @staticmethod
    def _filter(x: torch.Tensor, kernel: torch.Tensor) -> torch.Tensor:
        return F.conv2d(_pad_local(x, 1), kernel.to(dtype=x.dtype))

    def forward(self, x: torch.Tensor) -> dict[str, torch.Tensor]:
        g3, g5, g7 = self.g3(x), self.g5(x), self.g7(x)
        gx, gy = self._filter(x, self.sobel_x), self._filter(x, self.sobel_y)
        lap = self._filter(x, self.laplacian)
        features = torch.cat([x, g3, g5, g7, x - g3, g3 - g7, gx.abs(), gy.abs(), lap], dim=1)
        return {"features": features, "g3": g3, "g7": g7, "gx": gx, "gy": gy, "lap": lap}


class PrivateUNet(nn.Module):
    """Small normalization-free U-Net.  Instances never share learned parameters."""

    def __init__(self, c_in: int, base: int):
        super().__init__()
        self.e1 = nn.Sequential(ConvAct(c_in, base), ResidualBlock(base), ResidualBlock(base))
        self.d1 = AntiAliasedDownsample(base, base * 2)
        self.e2 = nn.Sequential(ResidualBlock(base * 2), ResidualBlock(base * 2))
        self.d2 = AntiAliasedDownsample(base * 2, base * 4)
        self.mid = nn.Sequential(ResidualBlock(base * 4), ResidualBlock(base * 4))
        self.u2 = AntiAliasedUpsample(base * 4, base * 2)
        self.f2 = nn.Sequential(ConvAct(base * 4, base * 2), ResidualBlock(base * 2))
        self.u1 = AntiAliasedUpsample(base * 2, base)
        self.f1 = nn.Sequential(ConvAct(base * 2, base), ResidualBlock(base))

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        e1 = self.e1(x)
        e2 = self.e2(self.d1(e1))
        mid = self.mid(self.d2(e2))
        y2 = self.f2(torch.cat([self.u2(mid), e2], dim=1))
        return self.f1(torch.cat([self.u1(y2), e1], dim=1))


class EvidenceConditionalTileNet(nn.Module):
    alignment_multiple = 8
    minimum_halo_px = 192

    def __init__(self, base: int = 16):
        super().__init__()
        self.base = int(base)
        self.optical = LocalOpticalMeasurements()
        feature_channels = 9

        self.need_tower = PrivateUNet(feature_channels, base)
        self.evidence_tower = PrivateUNet(feature_channels, base)
        self.geometry_tower = PrivateUNet(feature_channels, base)
        self.radiometry_tower = PrivateUNet(feature_channels, base)
        self.nuisance_tower = PrivateUNet(feature_channels, base)
        restoration_feature_channels = feature_channels + 2
        self.local_contrast_tower = PrivateUNet(restoration_feature_channels, base)
        self.boundary_tower = PrivateUNet(restoration_feature_channels, base)
        self.texture_tower = PrivateUNet(restoration_feature_channels, base)

        self.need_head = nn.Conv2d(base, 5, 1)
        self.evidence_head = nn.Conv2d(base, 3, 1)
        self.geometry_head = nn.Conv2d(base, 2, 1)
        self.radiometry_head = nn.Conv2d(base, 3, 1)
        self.nuisance_head = nn.Conv2d(base, 4, 1)
        self.local_contrast_filters = nn.ModuleList(
            FixedSeparableGaussian(sigma) for sigma in (3.0, 6.0, 10.0, 15.0)
        )
        self.local_contrast_head = nn.Conv2d(base, len(self.local_contrast_filters), 1)
        boundary_kernels = [_binomial_kernel(size) for size in (3, 5, 7, 17)]
        boundary_kernels.extend(
            _line_kernel(size, angle)
            for size in (7, 17)
            for angle in (0.0, 22.5, 45.0, 67.5, 90.0, 112.5, 135.0, 157.5)
        )
        boundary_filters: list[nn.Module] = [FixedFilter(kernel) for kernel in boundary_kernels]
        boundary_filters.append(FixedSeparableGaussian(5.5, radius=16))
        boundary_filters.extend(
            FixedFilter(_line_kernel(9, angle), dilation=4)
            for angle in (0.0, 22.5, 45.0, 67.5, 90.0, 112.5, 135.0, 157.5)
        )
        self.boundary_filters = nn.ModuleList(boundary_filters)
        self.boundary_head = nn.Conv2d(base, len(boundary_filters), 1)
        self.texture_head = nn.Conv2d(base, 3, 1)

        self.blur3 = FixedFilter(_binomial_kernel(3))
        self.blur5 = FixedFilter(_binomial_kernel(5))
        self.blur7 = FixedFilter(_binomial_kernel(7))
        self.blur17 = FixedFilter(_binomial_kernel(17))
        self.blur_x17 = FixedFilter(_directional_kernel(17, "x"))
        self.blur_y17 = FixedFilter(_directional_kernel(17, "y"))
        self._initialize_identity()

    def _initialize_identity(self) -> None:
        # Corrections are exactly zero at initialization.  Controls start closed;
        # direct control supervision, not reconstruction pressure, opens them.
        for head in (
            self.radiometry_head,
            self.nuisance_head,
            self.local_contrast_head,
            self.boundary_head,
            self.texture_head,
        ):
            nn.init.zeros_(head.weight)
            nn.init.zeros_(head.bias)
        nn.init.zeros_(self.need_head.weight)
        nn.init.zeros_(self.evidence_head.weight)
        with torch.no_grad():
            # Need begins closed.  Recoverability is a different physical
            # quantity and begins neutral, not as a copy of intervention need.
            self.need_head.bias.copy_(torch.tensor([-5.0, -5.0, -5.0, -5.0, -5.0]))
            self.evidence_head.bias.zero_()
        nn.init.zeros_(self.geometry_head.weight)
        nn.init.zeros_(self.geometry_head.bias)

    def _controls_aligned(self, x: torch.Tensor) -> dict[str, torch.Tensor]:
        raw = x.clamp(0.0, 1.0)
        features = self.optical(raw)["features"]
        need = torch.sigmoid(self.need_head(self.need_tower(features)))
        evidence = torch.sigmoid(self.evidence_head(self.evidence_tower(features)))
        geometry = self.geometry_head(self.geometry_tower(features))
        need_radiometry, need_noise, need_local_contrast, need_boundary, need_texture = need.chunk(5, dim=1)
        local_contrast_evidence, boundary_evidence, texture_recoverability = evidence.chunk(3, dim=1)
        return {
            "need_radiometry": need_radiometry,
            "need_noise": need_noise,
            "need_local_contrast": need_local_contrast,
            "need_boundary": need_boundary,
            "need_texture": need_texture,
            "local_contrast_evidence": local_contrast_evidence,
            "boundary_evidence": boundary_evidence,
            "texture_recoverability": texture_recoverability,
            "geometry_logits": geometry[:, 0:1],
            "geometry_probability": torch.sigmoid(geometry[:, 0:1]),
            "boundary_logits": geometry[:, 1:2],
            "boundary_support": torch.sigmoid(geometry[:, 1:2]),
        }

    def forward_controls(self, x: torch.Tensor) -> dict[str, torch.Tensor]:
        """Evaluate only directly supervised controls and procedural geometry."""
        h, w = x.shape[-2:]
        pad_h, pad_w = (-h) % self.alignment_multiple, (-w) % self.alignment_multiple
        if pad_h or pad_w:
            mode = "reflect" if h > pad_h and w > pad_w else "replicate"
            x = F.pad(x, (0, pad_w, 0, pad_h), mode=mode)
        return {
            name: value[..., :h, :w]
            for name, value in self._controls_aligned(x).items()
        }

    @staticmethod
    def _zero_dc_fine(x: torch.Tensor, blur: FixedFilter) -> torch.Tensor:
        return x - blur(x)

    @staticmethod
    def _open_need(need: torch.Tensor) -> torch.Tensor:
        """Continuous near-binary opening without a hard decision boundary."""
        return 1.0 - torch.exp(-need / 0.06)

    @staticmethod
    def _teacher_mix(
        predicted: torch.Tensor,
        truth: torch.Tensor | None,
        fraction: float,
    ) -> torch.Tensor:
        if truth is None or fraction <= 0.0:
            return predicted
        weight = float(max(0.0, min(1.0, fraction)))
        return predicted * (1.0 - weight) + truth.to(predicted) * weight

    def _forward_aligned(
        self,
        x: torch.Tensor,
        *,
        stage_truth: dict[str, torch.Tensor] | None = None,
        stage_truth_fraction: float = 0.0,
    ) -> dict[str, torch.Tensor]:
        raw = x.clamp(0.0, 1.0)
        optical = self.optical(raw)
        features = optical["features"]

        need_features = self.need_tower(features)
        need_radiometry, need_noise, need_local_contrast, need_boundary, need_texture = torch.sigmoid(
            self.need_head(need_features)
        ).chunk(5, dim=1)
        evidence_features = self.evidence_tower(features)
        local_contrast_evidence, boundary_evidence, texture_recoverability = torch.sigmoid(
            self.evidence_head(evidence_features)
        ).chunk(3, dim=1)

        # The auxiliary geometry map is trained from procedural masks only.  Its
        # detached value controls how restoration is represented; final-image
        # losses cannot turn it into an intensity-painting shortcut.
        geometry_features = self.geometry_tower(features)
        geometry_outputs = self.geometry_head(geometry_features)
        geometry_logits = geometry_outputs[:, 0:1]
        boundary_logits = geometry_outputs[:, 1:2]
        geometry_probability = torch.sigmoid(geometry_logits)
        boundary_support = torch.sigmoid(boundary_logits)

        # Stage 1: remove stochastic sensor effects from the raw measurement.
        nuisance_features = self.nuisance_tower(features)
        nuisance_bands = self.nuisance_head(nuisance_features)
        nuisance_fine = self._zero_dc_fine(0.060 * torch.tanh(nuisance_bands[:, 0:1]), self.blur3)
        nuisance_medium_raw = 0.065 * torch.tanh(nuisance_bands[:, 1:2])
        nuisance_medium = self.blur3(nuisance_medium_raw) - self.blur17(nuisance_medium_raw)
        # Sensor fixed-pattern noise has legitimate row/column components that
        # must not be discarded or reassigned to radiometry.
        nuisance_column = self.blur_y17(0.060 * torch.tanh(nuisance_bands[:, 2:3]))
        nuisance_row = self.blur_x17(0.060 * torch.tanh(nuisance_bands[:, 3:4]))
        nuisance_raw = torch.clamp(
            nuisance_fine + nuisance_medium + nuisance_column + nuisance_row,
            -0.18,
            0.18,
        )

        detached_need_noise = self._open_need(need_noise.detach())
        # B-S is exact sensor supervision, including legitimate row/column
        # pattern components; it is not forced into a high-pass-only space.
        gated_nuisance = detached_need_noise * nuisance_raw
        nuisance_delta = gated_nuisance

        predicted_sensor_clean_base = (raw + nuisance_delta).clamp(0.0, 1.0)
        sensor_clean_base = self._teacher_mix(
            predicted_sensor_clean_base,
            None if stage_truth is None else stage_truth.get("sensor_clean_base"),
            stage_truth_fraction,
        )

        # Stage 2: correct only radiometry/illumination on the denoised image.
        radiometry_optical = self.optical(sensor_clean_base.detach())
        radiometry_features = self.radiometry_tower(radiometry_optical["features"])
        radiometry_parameters = self.radiometry_head(
            F.avg_pool2d(radiometry_features, 4, stride=4)
        )
        radiometry_parameters = F.interpolate(
            radiometry_parameters,
            size=raw.shape[-2:],
            mode="bilinear",
            align_corners=False,
        )
        radiometry_parameters = self.blur17(radiometry_parameters)
        inverse_gamma = torch.exp(0.35 * torch.tanh(radiometry_parameters[:, 0:1]))
        inverse_gain = torch.exp(0.55 * torch.tanh(radiometry_parameters[:, 1:2]))
        radiometry_bias = 0.12 * torch.tanh(radiometry_parameters[:, 2:3])
        # Express the power law relative to the measured value.  At neutral
        # parameters this is bit-exact identity even for a true zero pixel;
        # clamping is used only inside the logarithm, never on the signal.
        gamma_adjusted = sensor_clean_base * torch.exp(
            (inverse_gamma - 1.0) * torch.log(sensor_clean_base.clamp_min(1e-6))
        )
        radiometry_candidate = torch.clamp(
            gamma_adjusted * inverse_gain + radiometry_bias,
            0.0,
            1.0,
        )
        radiometry_raw = radiometry_candidate - sensor_clean_base
        detached_need_radiometry = self.blur17(self._open_need(need_radiometry.detach()))
        radiometry_delta = detached_need_radiometry * radiometry_raw
        predicted_restoration_base = (sensor_clean_base + radiometry_delta).clamp(0.0, 1.0)
        restoration_base = self._teacher_mix(
            predicted_restoration_base,
            None if stage_truth is None else stage_truth.get("restoration_base"),
            stage_truth_fraction,
        )

        # Stage 3 reverses spatially varying contrast fade.  It is separate
        # from sharpening because the frozen generator applies these causes in
        # different steps and their exact counterfactual targets differ.
        contrast_optical = self.optical(restoration_base.detach())
        contrast_features = torch.cat(
            [
                contrast_optical["features"],
                geometry_probability.detach(),
                boundary_support.detach(),
            ],
            dim=1,
        )
        local_contrast_features = self.local_contrast_tower(contrast_features)
        local_contrast_outputs = self.local_contrast_head(local_contrast_features)
        local_contrast_coefficients = torch.tanh(self.blur17(local_contrast_outputs))
        local_contrast_norm = local_contrast_coefficients.abs().sum(dim=1, keepdim=True).clamp_min(1.0)
        local_contrast_coefficients = local_contrast_coefficients / local_contrast_norm
        contrast_measurement = restoration_base.detach()
        local_contrast_candidates = torch.cat(
            [contrast_measurement - operator(contrast_measurement) for operator in self.local_contrast_filters],
            dim=1,
        )
        mixed_local_contrast = (
            local_contrast_coefficients * local_contrast_candidates
        ).sum(dim=1, keepdim=True)
        local_contrast_raw = 0.32 * torch.tanh(mixed_local_contrast * 8.0)
        local_max_49 = F.max_pool2d(contrast_measurement, 49, stride=1, padding=24)
        local_min_49 = -F.max_pool2d(-contrast_measurement, 49, stride=1, padding=24)
        local_mid_49 = 0.5 * (local_max_49 + local_min_49)
        expanded_half_range = local_max_49 - local_min_49
        local_contrast_candidate = contrast_measurement + local_contrast_raw
        local_contrast_candidate = torch.maximum(
            local_mid_49 - expanded_half_range,
            torch.minimum(local_mid_49 + expanded_half_range, local_contrast_candidate),
        )
        local_contrast_raw = local_contrast_candidate - contrast_measurement
        local_contrast_intervention = (
            self._open_need(need_local_contrast) * local_contrast_evidence
        ).detach()
        local_contrast_delta = local_contrast_intervention * local_contrast_raw
        predicted_contrast_restored_base = (restoration_base + local_contrast_delta).clamp(0.0, 1.0)
        contrast_restored_base = self._teacher_mix(
            predicted_contrast_restored_base,
            None if stage_truth is None else stage_truth.get("contrast_restored_base"),
            stage_truth_fraction,
        )

        # Stages 4/5 see the cleaned, illumination- and local-contrast-corrected measurement.
        # The base is detached so boundary/texture objectives cannot solve
        # their task by rewriting the low or nuisance branches.
        restoration_optical = self.optical(contrast_restored_base.detach())
        restoration_features = torch.cat(
            [
                restoration_optical["features"],
                geometry_probability.detach(),
                boundary_support.detach(),
            ],
            dim=1,
        )

        boundary_features = self.boundary_tower(restoration_features)
        boundary_outputs = self.boundary_head(boundary_features)
        # Coefficients vary only slowly relative to the edge transition.  This
        # preserves the zero-phase character of the symmetric filter bank.
        kernel_coefficients = torch.tanh(self.blur17(boundary_outputs))
        coefficient_norm = kernel_coefficients.abs().sum(dim=1, keepdim=True).clamp_min(1.0)
        kernel_coefficients = kernel_coefficients / coefficient_norm
        restoration_measurement = contrast_restored_base.detach()
        symmetric_candidates = torch.cat(
            [restoration_measurement - operator(restoration_measurement) for operator in self.boundary_filters],
            dim=1,
        )
        mixed_boundary = (kernel_coefficients * symmetric_candidates).sum(dim=1, keepdim=True)
        boundary_raw = 0.45 * torch.tanh(mixed_boundary * 12.0)
        # Symmetric sharpening can still overshoot.  Keep its candidate inside
        # the observed local intensity envelope so it cannot create a new dark
        # or bright extremum that was absent from the measurement.
        local_max = F.max_pool2d(restoration_measurement, 49, stride=1, padding=24)
        local_min = -F.max_pool2d(-restoration_measurement, 49, stride=1, padding=24)
        boundary_candidate = torch.maximum(
            local_min,
            torch.minimum(local_max, restoration_measurement + boundary_raw),
        )
        boundary_raw = boundary_candidate - restoration_measurement
        texture_features = self.texture_tower(restoration_features)
        texture_outputs = self.texture_head(texture_features)
        texture_fine = self._zero_dc_fine(0.075 * torch.tanh(texture_outputs[:, 0:1]), self.blur3)
        texture_medium_raw = 0.085 * torch.tanh(texture_outputs[:, 1:2])
        texture_medium = self.blur3(texture_medium_raw) - self.blur17(texture_medium_raw)
        texture_broad = self.blur17(0.070 * torch.tanh(texture_outputs[:, 2:3]))
        texture_raw = torch.clamp(texture_fine + texture_medium + texture_broad, -0.18, 0.18)

        boundary_intervention = self.blur7(
            (self._open_need(need_boundary) * boundary_evidence).detach()
        )
        texture_intervention = (
            self._open_need(need_texture) * texture_recoverability
        ).detach()
        boundary_delta = boundary_intervention * boundary_raw
        texture_delta = texture_intervention * texture_raw
        restoration_raw = boundary_raw + texture_raw
        restoration_delta = boundary_delta + texture_delta

        correction = torch.clamp(
            radiometry_delta + nuisance_delta + local_contrast_delta + restoration_delta,
            -0.34,
            0.34,
        )
        output = torch.clamp(raw + correction, 0.0, 1.0)
        return {
            "output": output,
            "correction": correction,
            "radiometry_delta": radiometry_delta,
            "nuisance_delta": nuisance_delta,
            "restoration_delta": restoration_delta,
            "local_contrast_delta": local_contrast_delta,
            "sensor_clean_base": sensor_clean_base,
            "predicted_sensor_clean_base": predicted_sensor_clean_base,
            "restoration_base": restoration_base,
            "predicted_restoration_base": predicted_restoration_base,
            "contrast_restored_base": contrast_restored_base,
            "predicted_contrast_restored_base": predicted_contrast_restored_base,
            "radiometry_raw": radiometry_raw,
            "nuisance_raw": nuisance_raw,
            "local_contrast_raw": local_contrast_raw,
            "restoration_raw": restoration_raw,
            "boundary_restoration_raw": boundary_raw,
            "texture_restoration_raw": texture_raw,
            "need_radiometry": need_radiometry,
            "need_noise": need_noise,
            "need_local_contrast": need_local_contrast,
            "local_contrast_evidence": local_contrast_evidence,
            "need_boundary": need_boundary,
            "boundary_evidence": boundary_evidence,
            "need_texture": need_texture,
            "texture_recoverability": texture_recoverability,
            "boundary_intervention": boundary_intervention,
            "texture_intervention": texture_intervention,
            "local_contrast_intervention": local_contrast_intervention,
            "boundary_delta": boundary_delta,
            "texture_delta": texture_delta,
            "geometry_logits": geometry_logits,
            "geometry_probability": geometry_probability,
            "boundary_logits": boundary_logits,
            "boundary_support": boundary_support,
            "kernel_coefficients": kernel_coefficients,
        }

    def forward(
        self,
        x: torch.Tensor,
        *,
        return_details: bool = False,
        stage_truth: dict[str, torch.Tensor] | None = None,
        stage_truth_fraction: float = 0.0,
    ) -> torch.Tensor | dict[str, torch.Tensor]:
        h, w = x.shape[-2:]
        pad_h, pad_w = (-h) % self.alignment_multiple, (-w) % self.alignment_multiple
        if pad_h or pad_w:
            mode = "reflect" if h > pad_h and w > pad_w else "replicate"
            x = F.pad(x, (0, pad_w, 0, pad_h), mode=mode)
            if stage_truth is not None:
                stage_truth = {
                    name: F.pad(value, (0, pad_w, 0, pad_h), mode=mode)
                    for name, value in stage_truth.items()
                }
        details = self._forward_aligned(
            x,
            stage_truth=stage_truth,
            stage_truth_fraction=stage_truth_fraction,
        )
        details = {name: value[..., :h, :w] for name, value in details.items()}
        return details if return_details else details["output"]

    def parameter_groups(self) -> dict[str, list[nn.Parameter]]:
        return {
            "need_control": list(self.need_tower.parameters()) + list(self.need_head.parameters()),
            "evidence_control": list(self.evidence_tower.parameters()) + list(self.evidence_head.parameters()),
            "geometry": list(self.geometry_tower.parameters()) + list(self.geometry_head.parameters()),
            "radiometry": list(self.radiometry_tower.parameters()) + list(self.radiometry_head.parameters()),
            "nuisance": list(self.nuisance_tower.parameters()) + list(self.nuisance_head.parameters()),
            "local_contrast": list(self.local_contrast_tower.parameters()) + list(self.local_contrast_head.parameters()),
            "boundary": list(self.boundary_tower.parameters()) + list(self.boundary_head.parameters()),
            "texture": list(self.texture_tower.parameters()) + list(self.texture_head.parameters()),
        }


def build_model(base: int = 16) -> EvidenceConditionalTileNet:
    return EvidenceConditionalTileNet(base=base)


def count_parameters(model: nn.Module) -> int:
    return sum(parameter.numel() for parameter in model.parameters())


def architecture_contract(model: EvidenceConditionalTileNet) -> dict[str, Any]:
    groups = model.parameter_groups()
    ids = {name: {id(p) for p in parameters} for name, parameters in groups.items()}
    overlap = any(ids[a] & ids[b] for i, a in enumerate(ids) for b in list(ids)[i + 1 :])
    return {
        "class_name": type(model).__name__,
        "parameter_count": count_parameters(model),
        "normalization_layers": 0,
        "global_pooling_layers": 0,
        "alignment_multiple": model.alignment_multiple,
        "minimum_halo_px": model.minimum_halo_px,
        "raw_identity_at_initialization": True,
        "need_and_recoverability_are_distinct": True,
        "need_and_evidence_learned_towers_are_distinct": True,
        "boundary_and_texture_controls_are_distinct": True,
        "boundary_and_texture_learned_towers_are_distinct": True,
        "local_contrast_has_private_learned_tower": True,
        "all_correction_paths_controlled": True,
        "control_detached_from_reconstruction": True,
        "geometry_detached_from_reconstruction": True,
        "independent_edge_painting_branch": False,
        "phase_safe_boundary_filter_bank": True,
        "learned_parameter_group_overlap": overlap,
        "parameter_group_counts": {name: sum(p.numel() for p in parameters) for name, parameters in groups.items()},
    }

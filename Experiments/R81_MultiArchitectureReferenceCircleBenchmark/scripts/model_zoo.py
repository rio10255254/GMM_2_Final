from __future__ import annotations

"""Model registry for the R81 same-task architecture benchmark.

Every trainable baseline accepts one-channel input and returns a one-channel,
same-resolution reconstruction.  The fixed optical input adapter is attached
outside each backbone so the measurement input is identical across models.
"""

import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import torch
import torch.nn as nn
import torch.nn.functional as F
PROJECT_ROOT = Path(__file__).resolve().parents[3]


R81_ROOT = Path(__file__).resolve().parents[1]
MODERN_ROOT = (
    Path(str(PROJECT_ROOT / 'Thesis_MOSR_Evidence/LabSystem_MOSR/Experiments'))
    / "Modern_Restoration_Benchmarks_20260719"
)
BASE_UNET_ROOT = MODERN_ROOT.parent / "BaseUNet_Baseline_20260718"
PFT_ROOT = R81_ROOT / "third_party" / "pft_sr"
UCAN_ROOT = R81_ROOT / "third_party" / "ucan"

for import_root in (MODERN_ROOT, BASE_UNET_ROOT, PFT_ROOT, UCAN_ROOT):
    if str(import_root) not in sys.path:
        sys.path.insert(0, str(import_root))

from models_modern import (  # noqa: E402
    EDSRX1,
    NAFNet,
    Restormer,
    RestorationWithAdapter,
)
from train_base_unet import BaseUNet  # noqa: E402


class SRCNNX1(nn.Module):
    """Original three-layer SRCNN pattern adapted to grayscale x1 restoration."""

    def __init__(self, features1: int = 64, features2: int = 32) -> None:
        super().__init__()
        self.conv1 = nn.Conv2d(1, features1, 9, padding=4)
        self.conv2 = nn.Conv2d(features1, features2, 5, padding=2)
        self.conv3 = nn.Conv2d(features2, 1, 5, padding=2)

    def forward(self, source: torch.Tensor) -> torch.Tensor:
        residual = F.relu(self.conv1(source), inplace=True)
        residual = F.relu(self.conv2(residual), inplace=True)
        return source + self.conv3(residual)


class VDSRX1(nn.Module):
    """Twenty-layer VDSR pattern adapted to grayscale x1 restoration."""

    def __init__(self, features: int = 64, depth: int = 20) -> None:
        super().__init__()
        if depth < 3:
            raise ValueError("VDSR depth must be at least three")
        layers: list[nn.Module] = [nn.Conv2d(1, features, 3, padding=1), nn.ReLU(True)]
        for _ in range(depth - 2):
            layers.extend([nn.Conv2d(features, features, 3, padding=1), nn.ReLU(True)])
        layers.append(nn.Conv2d(features, 1, 3, padding=1))
        self.body = nn.Sequential(*layers)

    def forward(self, source: torch.Tensor) -> torch.Tensor:
        return source + self.body(source)


class DnCNNX1(nn.Module):
    """Seventeen-layer grayscale DnCNN used as a residual restoration baseline."""

    def __init__(self, features: int = 64, depth: int = 17) -> None:
        super().__init__()
        if depth < 3:
            raise ValueError("DnCNN depth must be at least three")
        layers: list[nn.Module] = [nn.Conv2d(1, features, 3, padding=1), nn.ReLU(True)]
        for _ in range(depth - 2):
            layers.extend(
                [
                    nn.Conv2d(features, features, 3, padding=1, bias=False),
                    nn.BatchNorm2d(features),
                    nn.ReLU(True),
                ]
            )
        layers.append(nn.Conv2d(features, 1, 3, padding=1))
        self.body = nn.Sequential(*layers)

    def forward(self, source: torch.Tensor) -> torch.Tensor:
        return source + self.body(source)


class DenseLayer(nn.Module):
    def __init__(self, input_channels: int, growth_rate: int) -> None:
        super().__init__()
        self.conv = nn.Conv2d(input_channels, growth_rate, 3, padding=1)

    def forward(self, source: torch.Tensor) -> torch.Tensor:
        added = F.relu(self.conv(source), inplace=True)
        return torch.cat((source, added), dim=1)


class ResidualDenseBlock(nn.Module):
    def __init__(self, features: int, growth_rate: int, layers: int) -> None:
        super().__init__()
        self.layers = nn.ModuleList(
            [DenseLayer(features + index * growth_rate, growth_rate) for index in range(layers)]
        )
        self.local_fusion = nn.Conv2d(features + layers * growth_rate, features, 1)

    def forward(self, source: torch.Tensor) -> torch.Tensor:
        features = source
        for layer in self.layers:
            features = layer(features)
        return source + self.local_fusion(features)


class RDNX1(nn.Module):
    """Residual Dense Network trunk adapted to same-resolution grayscale output."""

    def __init__(
        self,
        features: int = 64,
        growth_rate: int = 32,
        blocks: int = 8,
        layers_per_block: int = 6,
    ) -> None:
        super().__init__()
        self.shallow1 = nn.Conv2d(1, features, 3, padding=1)
        self.shallow2 = nn.Conv2d(features, features, 3, padding=1)
        self.blocks = nn.ModuleList(
            [ResidualDenseBlock(features, growth_rate, layers_per_block) for _ in range(blocks)]
        )
        self.global_fusion = nn.Sequential(
            nn.Conv2d(features * blocks, features, 1),
            nn.Conv2d(features, features, 3, padding=1),
        )
        self.output = nn.Conv2d(features, 1, 3, padding=1)

    def forward(self, source: torch.Tensor) -> torch.Tensor:
        shallow1 = self.shallow1(source)
        features = self.shallow2(shallow1)
        block_outputs: list[torch.Tensor] = []
        for block in self.blocks:
            features = block(features)
            block_outputs.append(features)
        fused = self.global_fusion(torch.cat(block_outputs, dim=1)) + shallow1
        return source + self.output(fused)


class GrayRCAN(nn.Module):
    """Use the reference RCAN implementation while keeping the benchmark grayscale."""

    def __init__(self, **kwargs: Any) -> None:
        super().__init__()
        from basicsr.archs.rcan_arch import RCAN

        self.rcan = RCAN(num_in_ch=3, num_out_ch=3, **kwargs)

    def forward(self, source: torch.Tensor) -> torch.Tensor:
        tripled = source.repeat(1, 3, 1, 1)
        return self.rcan(tripled).mean(dim=1, keepdim=True)


def build_swinir(**kwargs: Any) -> nn.Module:
    from basicsr.archs.swinir_arch import SwinIR

    return SwinIR(**kwargs)


def build_pft(**kwargs: Any) -> nn.Module:
    from pft_arch import PFT

    return PFT(**kwargs)


def build_ucan(**kwargs: Any) -> nn.Module:
    from ucan_arch import UCAN

    return UCAN(**kwargs)


@dataclass(frozen=True)
class ModelSpec:
    name: str
    family: str
    year: int
    category: str
    kwargs: dict[str, Any]
    source: str
    adaptation: str


MODEL_SPECS: dict[str, ModelSpec] = {
    "srcnn": ModelSpec(
        "SRCNN-x1", "SRCNN", 2014, "classic CNN", {"features1": 64, "features2": 32},
        "Dong et al., ECCV 2014 / TPAMI 2016",
        "one-channel same-resolution residual output",
    ),
    "vdsr": ModelSpec(
        "VDSR-x1", "VDSR", 2016, "classic deep CNN", {"features": 64, "depth": 20},
        "Kim et al., CVPR 2016", "one-channel same-resolution output",
    ),
    "dncnn": ModelSpec(
        "DnCNN", "DnCNN", 2017, "classic restoration CNN", {"features": 64, "depth": 17},
        "Zhang et al., TIP 2017", "one-channel residual restoration",
    ),
    "unet": ModelSpec(
        "Base U-Net", "U-Net", 2015, "classic encoder-decoder CNN", {"base": 48},
        "Ronneberger et al., MICCAI 2015; existing MOSR base-U-Net definition",
        "ordinary three-level U-like network without metrology-specific modules",
    ),
    "edsr": ModelSpec(
        "Compact EDSR-x1", "EDSR", 2017, "classic residual SR CNN",
        {"input_channels": 1, "output_channels": 1, "features": 96, "blocks": 24, "residual_scale": 0.1},
        "Lim et al., CVPR Workshops 2017", "existing MOSR benchmark checkpoint",
    ),
    "rdn": ModelSpec(
        "Compact RDN-x1", "RDN", 2018, "classic dense SR CNN",
        {"features": 64, "growth_rate": 32, "blocks": 8, "layers_per_block": 6},
        "Zhang et al., CVPR 2018", "one-channel same-resolution compact configuration",
    ),
    "rcan": ModelSpec(
        "Compact RCAN-x1", "RCAN", 2018, "classic attention SR CNN",
        {"num_feat": 64, "num_group": 4, "num_block": 12, "squeeze_factor": 16,
         "upscale": 1, "res_scale": 1.0, "img_range": 1.0,
         "rgb_mean": (0.0, 0.0, 0.0)},
        "Zhang et al., ECCV 2018; BasicSR reference implementation",
        "three tied grayscale channels with x1 output",
    ),
    "swinir": ModelSpec(
        "Compact SwinIR-x1", "SwinIR", 2021, "transformer restoration",
        {"img_size": 128, "patch_size": 1, "in_chans": 1, "embed_dim": 60,
         "depths": (2, 2, 2, 2), "num_heads": (6, 6, 6, 6), "window_size": 8,
         "mlp_ratio": 2.0, "upscale": 1, "img_range": 1.0, "upsampler": "",
         "resi_connection": "1conv"},
        "Liang et al., ICCV Workshops 2021; BasicSR reference implementation",
        "one-channel same-resolution compact configuration",
    ),
    "nafnet": ModelSpec(
        "Compact NAFNet", "NAFNet", 2022, "modern restoration CNN",
        {"image_channels": 1, "width": 20, "middle_blocks": 4,
         "encoder_blocks": (1, 1, 2, 2), "decoder_blocks": (1, 1, 1, 1)},
        "Chen et al., ECCV 2022", "existing MOSR benchmark checkpoint",
    ),
    "restormer": ModelSpec(
        "Compact Restormer", "Restormer", 2022, "transformer restoration",
        {"input_channels": 1, "output_channels": 1, "dim": 16,
         "blocks": (1, 1, 1, 2), "refinement_blocks": 1,
         "heads": (1, 2, 4, 8), "expansion": 2.66, "bias": False,
         "with_norm_bias": True},
        "Zamir et al., CVPR 2022", "one-channel parameter-controlled configuration",
    ),
    "pft": ModelSpec(
        "Compact PFT-SR-x1 adaptation", "PFT-SR", 2025, "recent transformer SR",
        {"img_size": 128, "patch_size": 1, "in_chans": 1, "embed_dim": 32,
         "depths": (2, 2, 2), "num_heads": 4,
         "num_topk": (64, 64, 32, 32, 16, 16),
         "window_size": 8, "convffn_kernel_size": 5, "mlp_ratio": 1.0,
         "upscale": 1, "img_range": 1.0, "upsampler": "pixelshuffledirect",
         "resi_connection": "1conv", "use_checkpoint": False},
        "Long et al., CVPR 2025; official PFT-SR code",
        "official progressive-focused core reduced to six layers and adapted to one-channel x1 restoration; trained from scratch",
    ),
    "ucan": ModelSpec(
        "UCAN-x1 adaptation", "UCAN", 2026, "latest hybrid lightweight SR",
        {"img_size": 128, "patch_size": 1, "in_chans": 1, "embed_dim": 48,
         "window_size": 16, "mlp_ratio": 1.0, "conv_depth": 5,
         "share": ("N", "F", "N", "F"), "mhsa_num_heads": 2,
         "dfl_num_heads": 1, "use_checkpoint": False, "upscale": 1,
         "img_range": 1.0, "upsampler": None, "resi_connection": "1conv"},
        "Tan et al., CVPR 2026; official UCAN code",
        "official convolution-attention core adapted to one-channel x1 restoration; trained from scratch",
    ),
}


TRAINABLE_KEYS = (
    "srcnn", "vdsr", "dncnn", "unet", "edsr", "rdn",
    "rcan", "swinir", "nafnet", "restormer", "pft", "ucan",
)


def build_backbone(model_key: str) -> nn.Module:
    spec = MODEL_SPECS[model_key]
    if model_key == "srcnn":
        return SRCNNX1(**spec.kwargs)
    if model_key == "vdsr":
        return VDSRX1(**spec.kwargs)
    if model_key == "dncnn":
        return DnCNNX1(**spec.kwargs)
    if model_key == "unet":
        return BaseUNet(input_adapter=None, **spec.kwargs)
    if model_key == "edsr":
        return EDSRX1(**spec.kwargs)
    if model_key == "rdn":
        return RDNX1(**spec.kwargs)
    if model_key == "rcan":
        return GrayRCAN(**spec.kwargs)
    if model_key == "swinir":
        return build_swinir(**spec.kwargs)
    if model_key == "nafnet":
        return NAFNet(**spec.kwargs)
    if model_key == "restormer":
        return Restormer(**spec.kwargs)
    if model_key == "pft":
        return build_pft(**spec.kwargs)
    if model_key == "ucan":
        return build_ucan(**spec.kwargs)
    raise KeyError(f"Unknown model: {model_key}")


def build_model(model_key: str, input_adapter: nn.Module | None = None) -> nn.Module:
    return RestorationWithAdapter(build_backbone(model_key), input_adapter=input_adapter)


def trainable_parameter_count(model: nn.Module) -> int:
    return sum(parameter.numel() for parameter in model.parameters() if parameter.requires_grad)


def serializable_spec(model_key: str) -> dict[str, Any]:
    return asdict(MODEL_SPECS[model_key])

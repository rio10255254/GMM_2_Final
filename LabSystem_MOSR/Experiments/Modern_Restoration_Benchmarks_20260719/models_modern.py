from __future__ import annotations

"""Compact, same-resolution restoration baselines for the MOSR benchmark.

NAFNet blocks are adapted from the official MIT-licensed implementation at
https://github.com/megvii-research/NAFNet (commit
2b4af71ebe098a92a75910c233a3965a3e93ede4).

Restormer blocks are adapted from the official MIT-licensed implementation at
https://github.com/swz30/Restormer (commit
68dc6ac472db26f16361150cb7a96a1bc87da93f).

The EDSR residual trunk follows the official MIT-licensed implementation at
https://github.com/sanghyun-son/EDSR-PyTorch (commit
8dba5581a7502b92de9641eb431130d6c8ca5d7f) and is configured for one-channel,
same-resolution restoration rather than spatial upscaling.
"""

from dataclasses import asdict, dataclass
from typing import Any

import torch
import torch.nn as nn
import torch.nn.functional as F
from einops import rearrange


class LayerNormFunction(torch.autograd.Function):
    @staticmethod
    def forward(ctx, x: torch.Tensor, weight: torch.Tensor, bias: torch.Tensor, eps: float):
        ctx.eps = eps
        mean = x.mean(1, keepdim=True)
        variance = (x - mean).pow(2).mean(1, keepdim=True)
        normalized = (x - mean) / torch.sqrt(variance + eps)
        ctx.save_for_backward(normalized, variance, weight)
        return weight.view(1, -1, 1, 1) * normalized + bias.view(1, -1, 1, 1)

    @staticmethod
    def backward(ctx, grad_output: torch.Tensor):
        eps = ctx.eps
        normalized, variance, weight = ctx.saved_tensors
        gradient = grad_output * weight.view(1, -1, 1, 1)
        mean_gradient = gradient.mean(dim=1, keepdim=True)
        mean_gradient_normalized = (gradient * normalized).mean(dim=1, keepdim=True)
        grad_input = (
            gradient - normalized * mean_gradient_normalized - mean_gradient
        ) / torch.sqrt(variance + eps)
        grad_weight = (grad_output * normalized).sum(dim=(0, 2, 3))
        grad_bias = grad_output.sum(dim=(0, 2, 3))
        return grad_input, grad_weight, grad_bias, None


class LayerNorm2d(nn.Module):
    def __init__(self, channels: int, eps: float = 1.0e-6) -> None:
        super().__init__()
        self.weight = nn.Parameter(torch.ones(channels))
        self.bias = nn.Parameter(torch.zeros(channels))
        self.eps = float(eps)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return LayerNormFunction.apply(x, self.weight, self.bias, self.eps)


class SimpleGate(nn.Module):
    def forward(self, x: torch.Tensor) -> torch.Tensor:
        first, second = x.chunk(2, dim=1)
        return first * second


class NAFBlock(nn.Module):
    def __init__(
        self,
        channels: int,
        dw_expand: int = 2,
        ffn_expand: int = 2,
        dropout: float = 0.0,
    ) -> None:
        super().__init__()
        dw_channels = channels * int(dw_expand)
        ffn_channels = channels * int(ffn_expand)
        self.norm1 = LayerNorm2d(channels)
        self.conv1 = nn.Conv2d(channels, dw_channels, 1)
        self.conv2 = nn.Conv2d(
            dw_channels, dw_channels, 3, padding=1, groups=dw_channels
        )
        self.gate1 = SimpleGate()
        self.sca = nn.Sequential(
            nn.AdaptiveAvgPool2d(1),
            nn.Conv2d(dw_channels // 2, dw_channels // 2, 1),
        )
        self.conv3 = nn.Conv2d(dw_channels // 2, channels, 1)
        self.dropout1 = nn.Dropout(dropout) if dropout > 0 else nn.Identity()

        self.norm2 = LayerNorm2d(channels)
        self.conv4 = nn.Conv2d(channels, ffn_channels, 1)
        self.gate2 = SimpleGate()
        self.conv5 = nn.Conv2d(ffn_channels // 2, channels, 1)
        self.dropout2 = nn.Dropout(dropout) if dropout > 0 else nn.Identity()

        self.beta = nn.Parameter(torch.zeros((1, channels, 1, 1)))
        self.gamma = nn.Parameter(torch.zeros((1, channels, 1, 1)))

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        residual = self.conv1(self.norm1(x))
        residual = self.conv2(residual)
        residual = self.gate1(residual)
        residual = residual * self.sca(residual)
        residual = self.dropout1(self.conv3(residual))
        y = x + residual * self.beta

        residual = self.conv4(self.norm2(y))
        residual = self.gate2(residual)
        residual = self.dropout2(self.conv5(residual))
        return y + residual * self.gamma


class NAFNet(nn.Module):
    def __init__(
        self,
        image_channels: int = 1,
        width: int = 20,
        middle_blocks: int = 4,
        encoder_blocks: tuple[int, ...] = (1, 1, 2, 2),
        decoder_blocks: tuple[int, ...] = (1, 1, 1, 1),
    ) -> None:
        super().__init__()
        if len(encoder_blocks) != len(decoder_blocks):
            raise ValueError("NAFNet encoder and decoder depths must match")
        self.intro = nn.Conv2d(image_channels, width, 3, padding=1)
        self.ending = nn.Conv2d(width, image_channels, 3, padding=1)
        self.encoders = nn.ModuleList()
        self.decoders = nn.ModuleList()
        self.downs = nn.ModuleList()
        self.ups = nn.ModuleList()

        channels = int(width)
        for block_count in encoder_blocks:
            self.encoders.append(
                nn.Sequential(*[NAFBlock(channels) for _ in range(block_count)])
            )
            self.downs.append(nn.Conv2d(channels, channels * 2, 2, stride=2))
            channels *= 2

        self.middle = nn.Sequential(
            *[NAFBlock(channels) for _ in range(int(middle_blocks))]
        )

        for block_count in decoder_blocks:
            self.ups.append(
                nn.Sequential(
                    nn.Conv2d(channels, channels * 2, 1, bias=False),
                    nn.PixelShuffle(2),
                )
            )
            channels //= 2
            self.decoders.append(
                nn.Sequential(*[NAFBlock(channels) for _ in range(block_count)])
            )

        self.padder_size = 2 ** len(self.encoders)

    def _pad(self, x: torch.Tensor) -> torch.Tensor:
        height, width = x.shape[-2:]
        pad_height = (-height) % self.padder_size
        pad_width = (-width) % self.padder_size
        return F.pad(x, (0, pad_width, 0, pad_height), mode="reflect")

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        original_height, original_width = x.shape[-2:]
        x = self._pad(x)
        source = x
        x = self.intro(x)
        skips: list[torch.Tensor] = []
        for encoder, down in zip(self.encoders, self.downs):
            x = encoder(x)
            skips.append(x)
            x = down(x)
        x = self.middle(x)
        for decoder, up, skip in zip(self.decoders, self.ups, reversed(skips)):
            x = decoder(up(x) + skip)
        x = self.ending(x) + source
        return x[..., :original_height, :original_width]


class RestormerLayerNorm(nn.Module):
    def __init__(self, channels: int, with_bias: bool = True) -> None:
        super().__init__()
        self.weight = nn.Parameter(torch.ones(channels))
        self.bias = nn.Parameter(torch.zeros(channels)) if with_bias else None

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        height, width = x.shape[-2:]
        flattened = rearrange(x, "b c h w -> b (h w) c")
        if self.bias is None:
            variance = flattened.var(-1, keepdim=True, unbiased=False)
            normalized = flattened / torch.sqrt(variance + 1.0e-5)
            normalized = normalized * self.weight
        else:
            mean = flattened.mean(-1, keepdim=True)
            variance = flattened.var(-1, keepdim=True, unbiased=False)
            normalized = (flattened - mean) / torch.sqrt(variance + 1.0e-5)
            normalized = normalized * self.weight + self.bias
        return rearrange(
            normalized, "b (h w) c -> b c h w", h=height, w=width
        )


class RestormerFeedForward(nn.Module):
    def __init__(self, channels: int, expansion: float, bias: bool) -> None:
        super().__init__()
        hidden = int(channels * float(expansion))
        self.project_in = nn.Conv2d(channels, hidden * 2, 1, bias=bias)
        self.depthwise = nn.Conv2d(
            hidden * 2,
            hidden * 2,
            3,
            padding=1,
            groups=hidden * 2,
            bias=bias,
        )
        self.project_out = nn.Conv2d(hidden, channels, 1, bias=bias)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        first, second = self.depthwise(self.project_in(x)).chunk(2, dim=1)
        return self.project_out(F.gelu(first) * second)


class RestormerAttention(nn.Module):
    def __init__(self, channels: int, heads: int, bias: bool) -> None:
        super().__init__()
        if channels % heads != 0:
            raise ValueError("Restormer channels must be divisible by heads")
        self.heads = int(heads)
        self.temperature = nn.Parameter(torch.ones(heads, 1, 1))
        self.qkv = nn.Conv2d(channels, channels * 3, 1, bias=bias)
        self.qkv_depthwise = nn.Conv2d(
            channels * 3,
            channels * 3,
            3,
            padding=1,
            groups=channels * 3,
            bias=bias,
        )
        self.project_out = nn.Conv2d(channels, channels, 1, bias=bias)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        height, width = x.shape[-2:]
        query, key, value = self.qkv_depthwise(self.qkv(x)).chunk(3, dim=1)
        query = rearrange(
            query, "b (head c) h w -> b head c (h w)", head=self.heads
        )
        key = rearrange(
            key, "b (head c) h w -> b head c (h w)", head=self.heads
        )
        value = rearrange(
            value, "b (head c) h w -> b head c (h w)", head=self.heads
        )
        query = F.normalize(query, dim=-1)
        key = F.normalize(key, dim=-1)
        attention = (query @ key.transpose(-2, -1)) * self.temperature
        attention = attention.softmax(dim=-1)
        out = attention @ value
        out = rearrange(
            out,
            "b head c (h w) -> b (head c) h w",
            head=self.heads,
            h=height,
            w=width,
        )
        return self.project_out(out)


class RestormerBlock(nn.Module):
    def __init__(
        self,
        channels: int,
        heads: int,
        expansion: float,
        bias: bool,
        with_norm_bias: bool,
    ) -> None:
        super().__init__()
        self.norm1 = RestormerLayerNorm(channels, with_bias=with_norm_bias)
        self.attention = RestormerAttention(channels, heads, bias)
        self.norm2 = RestormerLayerNorm(channels, with_bias=with_norm_bias)
        self.feed_forward = RestormerFeedForward(channels, expansion, bias)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        x = x + self.attention(self.norm1(x))
        return x + self.feed_forward(self.norm2(x))


class RestormerDownsample(nn.Module):
    def __init__(self, channels: int) -> None:
        super().__init__()
        self.body = nn.Sequential(
            nn.Conv2d(channels, channels // 2, 3, padding=1, bias=False),
            nn.PixelUnshuffle(2),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.body(x)


class RestormerUpsample(nn.Module):
    def __init__(self, channels: int) -> None:
        super().__init__()
        self.body = nn.Sequential(
            nn.Conv2d(channels, channels * 2, 3, padding=1, bias=False),
            nn.PixelShuffle(2),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.body(x)


class Restormer(nn.Module):
    def __init__(
        self,
        input_channels: int = 1,
        output_channels: int = 1,
        dim: int = 26,
        blocks: tuple[int, int, int, int] = (2, 3, 3, 4),
        refinement_blocks: int = 2,
        heads: tuple[int, int, int, int] = (1, 2, 4, 8),
        expansion: float = 2.66,
        bias: bool = False,
        with_norm_bias: bool = True,
    ) -> None:
        super().__init__()

        def make_blocks(channels: int, count: int, head_count: int) -> nn.Sequential:
            return nn.Sequential(
                *[
                    RestormerBlock(
                        channels,
                        head_count,
                        expansion,
                        bias,
                        with_norm_bias,
                    )
                    for _ in range(count)
                ]
            )

        self.patch_embed = nn.Conv2d(input_channels, dim, 3, padding=1, bias=bias)
        self.encoder1 = make_blocks(dim, blocks[0], heads[0])
        self.down1 = RestormerDownsample(dim)
        self.encoder2 = make_blocks(dim * 2, blocks[1], heads[1])
        self.down2 = RestormerDownsample(dim * 2)
        self.encoder3 = make_blocks(dim * 4, blocks[2], heads[2])
        self.down3 = RestormerDownsample(dim * 4)
        self.latent = make_blocks(dim * 8, blocks[3], heads[3])

        self.up3 = RestormerUpsample(dim * 8)
        self.reduce3 = nn.Conv2d(dim * 8, dim * 4, 1, bias=bias)
        self.decoder3 = make_blocks(dim * 4, blocks[2], heads[2])
        self.up2 = RestormerUpsample(dim * 4)
        self.reduce2 = nn.Conv2d(dim * 4, dim * 2, 1, bias=bias)
        self.decoder2 = make_blocks(dim * 2, blocks[1], heads[1])
        self.up1 = RestormerUpsample(dim * 2)
        self.decoder1 = make_blocks(dim * 2, blocks[0], heads[0])
        self.refinement = make_blocks(dim * 2, refinement_blocks, heads[0])
        self.output = nn.Conv2d(dim * 2, output_channels, 3, padding=1, bias=bias)
        self.padder_size = 8

    def _pad(self, x: torch.Tensor) -> torch.Tensor:
        height, width = x.shape[-2:]
        pad_height = (-height) % self.padder_size
        pad_width = (-width) % self.padder_size
        return F.pad(x, (0, pad_width, 0, pad_height), mode="reflect")

    def forward(self, source: torch.Tensor) -> torch.Tensor:
        original_height, original_width = source.shape[-2:]
        source = self._pad(source)
        enc1 = self.encoder1(self.patch_embed(source))
        enc2 = self.encoder2(self.down1(enc1))
        enc3 = self.encoder3(self.down2(enc2))
        latent = self.latent(self.down3(enc3))

        dec3 = self.up3(latent)
        dec3 = self.decoder3(self.reduce3(torch.cat([dec3, enc3], dim=1)))
        dec2 = self.up2(dec3)
        dec2 = self.decoder2(self.reduce2(torch.cat([dec2, enc2], dim=1)))
        dec1 = self.up1(dec2)
        dec1 = self.decoder1(torch.cat([dec1, enc1], dim=1))
        output = self.output(self.refinement(dec1)) + source
        return output[..., :original_height, :original_width]


class EDSRResidualBlock(nn.Module):
    def __init__(self, channels: int, residual_scale: float = 0.1) -> None:
        super().__init__()
        self.first = nn.Conv2d(channels, channels, 3, padding=1)
        self.second = nn.Conv2d(channels, channels, 3, padding=1)
        self.residual_scale = float(residual_scale)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        residual = self.second(F.relu(self.first(x), inplace=True))
        return x + residual * self.residual_scale


class EDSRX1(nn.Module):
    """EDSR trunk adapted to same-resolution grayscale restoration."""

    def __init__(
        self,
        input_channels: int = 1,
        output_channels: int = 1,
        features: int = 96,
        blocks: int = 24,
        residual_scale: float = 0.1,
    ) -> None:
        super().__init__()
        self.head = nn.Conv2d(input_channels, features, 3, padding=1)
        self.body = nn.Sequential(
            *[
                EDSRResidualBlock(features, residual_scale=residual_scale)
                for _ in range(blocks)
            ]
        )
        self.body_tail = nn.Conv2d(features, features, 3, padding=1)
        self.output = nn.Conv2d(features, output_channels, 3, padding=1)

    def forward(self, source: torch.Tensor) -> torch.Tensor:
        features = self.head(source)
        restored = self.body_tail(self.body(features)) + features
        return self.output(restored) + source


class RestorationWithAdapter(nn.Module):
    def __init__(self, backbone: nn.Module, input_adapter: nn.Module | None = None) -> None:
        super().__init__()
        self.input_adapter = input_adapter if input_adapter is not None else nn.Identity()
        self.backbone = backbone

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.backbone(self.input_adapter(x))


@dataclass(frozen=True)
class ModelSpec:
    name: str
    family: str
    kwargs: dict[str, Any]


MODEL_SPECS = {
    "nafnet": ModelSpec(
        name="Compact NAFNet",
        family="NAFNet",
        kwargs={
            "image_channels": 1,
            "width": 20,
            "middle_blocks": 4,
            "encoder_blocks": (1, 1, 2, 2),
            "decoder_blocks": (1, 1, 1, 1),
        },
    ),
    "edsr": ModelSpec(
        name="Compact EDSR-x1",
        family="EDSR",
        kwargs={
            "input_channels": 1,
            "output_channels": 1,
            "features": 96,
            "blocks": 24,
            "residual_scale": 0.1,
        },
    ),
}


def build_backbone(model_key: str) -> nn.Module:
    if model_key not in MODEL_SPECS:
        raise KeyError(f"Unknown model: {model_key}")
    spec = MODEL_SPECS[model_key]
    if model_key == "nafnet":
        return NAFNet(**spec.kwargs)
    if model_key == "edsr":
        return EDSRX1(**spec.kwargs)
    raise AssertionError(model_key)


def build_model(model_key: str, input_adapter: nn.Module | None = None) -> nn.Module:
    return RestorationWithAdapter(build_backbone(model_key), input_adapter=input_adapter)


def trainable_parameter_count(model: nn.Module) -> int:
    return sum(parameter.numel() for parameter in model.parameters() if parameter.requires_grad)


def serializable_spec(model_key: str) -> dict[str, Any]:
    return asdict(MODEL_SPECS[model_key])

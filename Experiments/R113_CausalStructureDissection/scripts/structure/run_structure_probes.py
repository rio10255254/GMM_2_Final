"""Causal internal-structure probes for frozen V42, R61, and R109.

This script is intentionally read-only with respect to source checkpoints and
datasets.  Every generated artifact lives under R113/results/structure.
"""
from __future__ import annotations

import contextlib
import hashlib
import importlib.util
import json
import math
import shutil
import sys
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Iterator

import cv2
import numpy as np
import pandas as pd
import torch
from torch import nn
import torch.nn.functional as F

from r109_interventions import render_variant_aligned
PROJECT_ROOT = Path(__file__).resolve().parents[4]


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "results" / "structure"
IMAGE_OUT = OUT / "outputs"
MONTAGE_OUT = OUT / "montages"
OUT.mkdir(parents=True, exist_ok=True)
IMAGE_OUT.mkdir(parents=True, exist_ok=True)
MONTAGE_OUT.mkdir(parents=True, exist_ok=True)

EXPERIMENT_CONFIG = json.loads((ROOT / "config" / "experiment.json").read_text(encoding="utf-8"))
V42_LOADER = Path(
    str(PROJECT_ROOT / 'Experiments/R111_R109V42ThesisReplacementQualification/scripts/build_v42_external_gmf.py')
)
V42_MODEL_FILE = Path(
    str(PROJECT_ROOT / 'Deliverables/Standalone_Models/V42_SoftLabelSNR_FullStandalone_20260709/model_v42.py')
)
R61_MODEL_FILE = Path(str(PROJECT_ROOT / 'Model/GeoEdgeAlignSR_v1_ModelA_v5_NoCoord.py'))
R109_ROOT = Path(str(PROJECT_ROOT / 'Experiments/R109_StagedMidpointWidthScratch'))

EXPECTED_HASHES = {
    name: entry["sha256"] for name, entry in EXPERIMENT_CONFIG["models"].items()
}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot import {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def read_gray(path: Path) -> np.ndarray:
    image = cv2.imdecode(np.fromfile(str(path), np.uint8), cv2.IMREAD_GRAYSCALE)
    if image is None:
        raise RuntimeError(f"Cannot read {path}")
    return image


def write_png(path: Path, image: np.ndarray) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    ok, encoded = cv2.imencode(".png", image)
    if not ok:
        raise RuntimeError(f"Cannot encode {path}")
    encoded.tofile(str(path))


def to_tensor(image: np.ndarray, device: torch.device) -> torch.Tensor:
    return torch.from_numpy(image.astype(np.float32)[None, None] / 255.0).to(device)


def to_u8(value: torch.Tensor) -> np.ndarray:
    return np.round(value.detach().float().clamp(0, 1)[0, 0].cpu().numpy() * 255).astype(np.uint8)


def parse_gmf_coordinate(path: Path, frame: int) -> tuple[float, float]:
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        parts = [part.strip() for part in line.split(",")]
        values = {parts[index]: parts[index + 1] for index in range(0, len(parts), 2)}
        if int(values["FileName"][6:10]) == frame:
            return float(values["PosX"]), float(values["PosY"])
    raise RuntimeError(f"No GMF coordinate for frame {frame}")


def crop_at(image: np.ndarray, size: int, center: tuple[float, float]) -> tuple[np.ndarray, dict[str, int]]:
    height, width = image.shape
    size = min(size, height, width)
    x0 = int(round(center[0] - size / 2))
    y0 = int(round(center[1] - size / 2))
    x0 = max(0, min(width - size, x0))
    y0 = max(0, min(height - size, y0))
    return image[y0 : y0 + size, x0 : x0 + size].copy(), {"x": x0, "y": y0, "width": size, "height": size}


def content_crop(image: np.ndarray, size: int = 512) -> tuple[np.ndarray, dict[str, int]]:
    height, width = image.shape
    if height <= size or width <= size:
        return crop_at(image, min(size, height, width), (width / 2, height / 2))
    small = cv2.resize(image, (max(1, width // 8), max(1, height // 8)), interpolation=cv2.INTER_AREA)
    gx = cv2.Sobel(small.astype(np.float32), cv2.CV_32F, 1, 0, ksize=3)
    gy = cv2.Sobel(small.astype(np.float32), cv2.CV_32F, 0, 1, ksize=3)
    energy = cv2.GaussianBlur(np.sqrt(gx * gx + gy * gy), (0, 0), max(2.0, size / 32))
    margin = max(1, size // 16)
    y_small, x_small = np.unravel_index(int(np.argmax(energy[margin:-margin, margin:-margin])), energy[margin:-margin, margin:-margin].shape)
    x_small += margin
    y_small += margin
    return crop_at(image, size, (x_small * width / small.shape[1], y_small * height / small.shape[0]))


def build_samples() -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    definitions: list[dict[str, Any]] = [
        {
            "case": "junhua_pitch100",
            "family": "JunHua real 100x",
            "source": Path(str(PROJECT_ROOT / 'Thesis_MOSR_Evidence/External_GMF_Packages/Pitch1um_Y_100_Raw_Even_R109E48/pitch1um_y100_raw/bmp/frame_0050.bmp')),
            "coordinate_score": Path(str(PROJECT_ROOT / 'Thesis_MOSR_Evidence/External_GMF_Packages/Pitch1um_Y_100_Raw_Even_R109E48/_gmf_scores/pitch1um_y100_raw/GMF_score.txt')),
            "frame": 50,
            "size": 1536,
        },
        {
            "case": "real_5x",
            "family": "real microscope 5x",
            "source": Path(str(PROJECT_ROOT / 'Analyses/20260704_20x_5x_analysis/raw_inputs/5x_1um/bmp/frame_0025.bmp')),
            "size": 512,
            "fixed_center": True,
        },
        {
            "case": "real_20x",
            "family": "real microscope 20x",
            "source": Path(str(PROJECT_ROOT / 'Analyses/20260704_20x_5x_analysis/raw_inputs/20x_1um/bmp/frame_0025.bmp')),
            "size": 512,
            "fixed_center": True,
        },
        {
            "case": "real_50x",
            "family": "real microscope 50x",
            "source": Path(str(PROJECT_ROOT / 'Analyses/20260702_100MG_displacement_analysis/raw_inputs/x_1um/bmp/frame_0025.bmp')),
            "size": 512,
            "fixed_center": True,
        },
        {
            "case": "sem_paired_optical",
            "family": "SEM-paired optical exposure",
            "source": Path(str(PROJECT_ROOT / 'Experiments/R69_ACMContourSEMValidation/inputs/sem_paired_50x_exposure_stack/20.bmp')),
            "size": 512,
        },
        {
            "case": "synthetic_lines",
            "family": "synthetic known truth lines",
            "source": Path(str(PROJECT_ROOT / 'Training_Data/r40_microscopy_feature_coverage/micro_val_unseen/src/stage_29_micro_lines_grid/0087.bmp')),
            "label": Path(str(PROJECT_ROOT / 'Training_Data/r40_microscopy_feature_coverage/micro_val_unseen/lbl/stage_29_micro_lines_grid/0087.bmp')),
            "size": 512,
        },
        {
            "case": "synthetic_texture",
            "family": "synthetic known truth texture",
            "source": Path(str(PROJECT_ROOT / 'Training_Data/r40_microscopy_feature_coverage/micro_val_unseen/src/stage_31_micro_textures/0087.bmp')),
            "label": Path(str(PROJECT_ROOT / 'Training_Data/r40_microscopy_feature_coverage/micro_val_unseen/lbl/stage_31_micro_textures/0087.bmp')),
            "size": 512,
        },
        {
            "case": "synthetic_edge_defect",
            "family": "synthetic known truth edge defect",
            "source": Path(str(PROJECT_ROOT / 'Training_Data/r40_microscopy_feature_coverage/micro_val_unseen/src/stage_32_micro_edge_defects/0087.bmp')),
            "label": Path(str(PROJECT_ROOT / 'Training_Data/r40_microscopy_feature_coverage/micro_val_unseen/lbl/stage_32_micro_edge_defects/0087.bmp')),
            "size": 512,
        },
    ]
    samples: list[dict[str, Any]] = []
    manifest: list[dict[str, Any]] = []
    for definition in definitions:
        source = definition["source"]
        if not source.is_file():
            raise FileNotFoundError(source)
        full = read_gray(source)
        if "coordinate_score" in definition:
            center = parse_gmf_coordinate(definition["coordinate_score"], definition["frame"])
            image, rectangle = crop_at(full, definition["size"], center)
            selection = "external_GMF_coordinate_fixed_before_model_comparison"
        elif definition.get("fixed_center", False):
            image, rectangle = crop_at(full, definition["size"], (full.shape[1] / 2, full.shape[0] / 2))
            selection = "fixed_image_center_before_model_comparison"
        else:
            image, rectangle = content_crop(full, definition["size"])
            selection = "raw_gradient_energy_fixed_before_model_comparison"
        label = None
        label_path = definition.get("label")
        if label_path is not None:
            label_full = read_gray(label_path)
            label = label_full[
                rectangle["y"] : rectangle["y"] + rectangle["height"],
                rectangle["x"] : rectangle["x"] + rectangle["width"],
            ].copy()
            if label.shape != image.shape:
                raise RuntimeError(f"Label crop mismatch for {definition['case']}")
        samples.append({**definition, "image": image, "label_image": label, "rectangle": rectangle})
        write_png(OUT / "inputs" / f"{definition['case']}_raw.png", image)
        if label is not None:
            write_png(OUT / "inputs" / f"{definition['case']}_label.png", label)
        manifest.append(
            {
                "case": definition["case"],
                "family": definition["family"],
                "source": str(source),
                "source_sha256": sha256_file(source),
                "source_shape": list(full.shape),
                "crop": rectangle,
                "selection": selection,
                "label": str(label_path) if label_path else None,
                "label_sha256": sha256_file(label_path) if label_path else None,
            }
        )
    return samples, manifest


def geo_args() -> SimpleNamespace:
    return SimpleNamespace(
        psf_fitted_path=None,
        psf_from_ckpt=True,
        psf_grid_rows=None,
        psf_grid_cols=None,
        psf_use_stack_mean=True,
        psf_deconv_reg=None,
        psf_phys_alpha=None,
        psf_phys_trainable_reg=False,
        use_band_limit=None,
        band_limit_cutoff=0.95,
        band_limit_order=8.0,
        weak_psf_enable=None,
        weak_psf_k=None,
        weak_psf_indices=None,
        weak_psf_reg=None,
        weak_psf_beta_init=None,
        weak_psf_beta_min=0.0,
        weak_psf_beta_max=0.10,
        weak_psf_beta_scale_max=None,
        weak_psf_beta_scale=None,
        weak_psf_gating_temp=None,
        weak_psf_psf_temp=None,
        weak_psf_entropy_mix=None,
        weak_psf_trainable_reg=False,
        weak_psf_lowfreq_ratio=None,
        weak_psf_inject="y2",
        weak_psf_deconv_mode="clamp",
        strict_load=False,
        print_model_config=False,
    )


def instantiate_geo(module, checkpoint_path: Path, device: torch.device):
    checkpoint = torch.load(checkpoint_path, map_location="cpu", weights_only=False)
    state = module.extract_state_dict(checkpoint)
    arch = module.infer_arch_from_state(state, ckpt_obj=checkpoint)
    args = geo_args()
    psf_path, temp_psf_dir, psf_source = module.resolve_psf_path(args, checkpoint, state)
    if psf_path is None or not psf_path.exists():
        raise RuntimeError(f"Cannot recover checkpoint PSF for {checkpoint_path}")
    weak_indices = module.parse_indices(None, int(arch["weak_psf_k"]))
    model = module.GeoEdgeAlignSR_v1_v5_NoCoord(
        in_ch=arch["in_ch"],
        base=arch["base"],
        use_physics_layer=arch["use_physics_layer"],
        use_sigmoid_output=True,
        use_upsample_conv=True,
        use_band_limit=arch["use_band_limit"],
        band_limit_cutoff=0.95,
        band_limit_order=8.0,
        psf_fitted_path=str(psf_path),
        psf_grid_rows=None,
        psf_grid_cols=None,
        psf_use_stack_mean=True,
        psf_deconv_reg=float(arch["psf_deconv_reg"] if arch["psf_deconv_reg"] is not None else 10.0),
        psf_phys_alpha_init=float(arch["psf_phys_alpha_init"] if arch["psf_phys_alpha_init"] is not None else 0.10),
        psf_phys_trainable_reg=False,
        weak_psf_enable=bool(arch["weak_psf_enable"]),
        weak_psf_k=int(arch["weak_psf_k"]),
        weak_psf_indices=weak_indices,
        weak_psf_reg=float(arch["weak_psf_reg"] if arch["weak_psf_reg"] is not None else 30.0),
        weak_psf_beta_init=float(arch["weak_psf_beta_init"] if arch["weak_psf_beta_init"] is not None else 0.02),
        weak_psf_gating_temp=float(arch["weak_psf_gating_temp"] if arch["weak_psf_gating_temp"] is not None else 2.5),
        weak_psf_psf_temp=float(arch["weak_psf_psf_temp"] if arch["weak_psf_psf_temp"] is not None else 2.5),
        weak_psf_entropy_mix=float(arch["weak_psf_entropy_mix"] if arch["weak_psf_entropy_mix"] is not None else 0.0),
        weak_psf_trainable_reg=False,
        weak_psf_lowfreq_ratio=float(arch["weak_psf_lowfreq_ratio"] if arch["weak_psf_lowfreq_ratio"] is not None else 0.25),
        weak_psf_beta_min=0.0,
        weak_psf_beta_max=0.10,
        weak_psf_beta_scale_max=float(arch["weak_psf_beta_scale_max"] if arch["weak_psf_beta_scale_max"] is not None else 0.35),
        weak_psf_deconv_mode="clamp",
        weak_psf_inject="y2",
        boundary_residual_adapter_enable=bool(arch["boundary_residual_adapter_enable"]),
        boundary_residual_adapter_hidden=int(arch["boundary_residual_adapter_hidden"]),
        boundary_residual_adapter_max=float(arch["boundary_residual_adapter_max"]),
        boundary_residual_adapter_gate_bias=float(arch["boundary_residual_adapter_gate_bias"]),
        boundary_residual_adapter_delta_bias=bool(arch["boundary_residual_adapter_delta_bias"]),
        boundary_residual_adapter_zero_mean=bool(arch["boundary_residual_adapter_zero_mean"]),
        boundary_residual_adapter_edge_gate=bool(arch["boundary_residual_adapter_edge_gate"]),
        boundary_residual_adapter_polarity_split=bool(arch["boundary_residual_adapter_polarity_split"]),
        boundary_residual_adapter_orientation_inputs=bool(arch["boundary_residual_adapter_orientation_inputs"]),
        raw_anchor_output_mode=str(arch["raw_anchor_output_mode"]),
        raw_anchor_output_alpha=float(arch["raw_anchor_output_alpha"]),
        raw_anchor_output_sigma=float(arch["raw_anchor_output_sigma"]),
        raw_anchor_output_detail_gain=float(arch["raw_anchor_output_detail_gain"]),
        quality_gate_enable=bool(arch["quality_gate_enable"]),
        quality_gate_hidden=int(arch["quality_gate_hidden"]),
        quality_gate_scale_min=float(arch["quality_gate_scale_min"]),
        quality_gate_scale_max=float(arch["quality_gate_scale_max"]),
    ).to(device)
    module.load_weights(model, state, strict=False)
    model.eval()
    return model, checkpoint, state, arch, temp_psf_dir, psf_source


@contextlib.contextmanager
def temporary_attributes(model: nn.Module, **changes: Any) -> Iterator[None]:
    old: dict[str, Any] = {}
    try:
        for name, value in changes.items():
            old[name] = getattr(model, name)
            setattr(model, name, value)
        yield
    finally:
        for name, value in old.items():
            setattr(model, name, value)


@contextlib.contextmanager
def temporary_scalar(parameter: torch.Tensor, value: float) -> Iterator[None]:
    old = parameter.detach().clone()
    try:
        parameter.data.fill_(value)
        yield
    finally:
        parameter.data.copy_(old)


def tensor_pair_stats(model: str, case: str, module: str, before: torch.Tensor, after: torch.Tensor) -> dict[str, Any]:
    before_f = before.detach().float()
    after_f = after.detach().float()
    delta = after_f - before_f
    return {
        "model": model,
        "case": case,
        "module": module,
        "input_shape": "x".join(str(value) for value in before_f.shape),
        "output_shape": "x".join(str(value) for value in after_f.shape),
        "input_mean": float(before_f.mean().cpu()),
        "input_std": float(before_f.std(unbiased=False).cpu()),
        "output_mean": float(after_f.mean().cpu()),
        "output_std": float(after_f.std(unbiased=False).cpu()),
        "mean_abs_effect": float(delta.abs().mean().cpu()),
        "rms_effect": float(torch.sqrt(torch.mean(delta.square())).cpu()),
        "effect_over_input_std": float(delta.abs().mean().cpu() / before_f.std(unbiased=False).clamp_min(1e-8).cpu()),
    }


def register_geo_hooks(model: nn.Module, store: dict[str, Any]):
    handles = []

    def hook(name: str):
        def capture(_module, inputs, output):
            store[name] = {
                "inputs": tuple(value.detach() for value in inputs if isinstance(value, torch.Tensor)),
                "output": output.detach() if isinstance(output, torch.Tensor) else output,
            }
        return capture

    for name, attribute in [
        ("physics", "physics_layer"),
        ("weak_psf", "weak_psf_block"),
        ("boundary", "boundary_adapter"),
        ("raw_anchor", "raw_anchor_output"),
        ("quality_gate", "quality_gate"),
    ]:
        value = getattr(model, attribute, None)
        if value is not None:
            handles.append(value.register_forward_hook(hook(name)))
    return handles


def gaussian_map(value: torch.Tensor, sigma: float = 2.0) -> torch.Tensor:
    radius = max(1, int(math.ceil(3 * sigma)))
    axis = torch.arange(-radius, radius + 1, device=value.device, dtype=value.dtype)
    kernel = torch.exp(-0.5 * (axis / sigma) ** 2)
    kernel /= kernel.sum()
    horizontal = kernel.view(1, 1, 1, -1)
    vertical = kernel.view(1, 1, -1, 1)
    result = F.conv2d(F.pad(value, (radius, radius, 0, 0), mode="reflect"), horizontal)
    return F.conv2d(F.pad(result, (0, 0, radius, radius), mode="reflect"), vertical)


def r109_render(model, raw: torch.Tensor, details, variant: str):
    if variant == "identity":
        return raw, {"support": torch.zeros_like(details.support), "width": torch.ones_like(details.width_gain), "shift": torch.zeros_like(details.normal_shift)}
    cues = model.cues(raw)
    magnitude = cues["magnitude"].float()
    local_scale = cues["local_scale"].float()
    source_support = ((magnitude / (local_scale + 2 / 255) - 0.05) / 1.10).clamp(0, 1)
    learned_support = (0.85 * F.max_pool2d(details.boundary.float(), 9, 1, 4)).clamp(0, 1)
    support = torch.maximum(source_support, learned_support).clamp(0, 1)
    if variant == "learned_support_only":
        support = learned_support
    elif variant == "source_support_only":
        support = source_support
    width = details.width_gain.float()
    shift = details.normal_shift.float()
    if variant in {"shift_only", "no_width"}:
        width = torch.ones_like(width)
    if variant in {"width_only", "no_shift"}:
        shift = torch.zeros_like(shift)
    if variant == "smoothed_controls":
        width = gaussian_map(width, 2.0)
        shift = gaussian_map(shift, 2.0)
    smooth_gx, smooth_gy = sys.modules[model.__class__.__module__].gradients(cues["blurred"][1].float())
    smooth_magnitude = torch.sqrt(smooth_gx.square() + smooth_gy.square() + 1e-8)
    normal_x, normal_y = smooth_gx / smooth_magnitude, smooth_gy / smooth_magnitude
    flow = torch.cat([shift * normal_x, shift * normal_y], 1)
    warped = model.warp(raw.float(), flow * support)
    window = int(sys.modules[model.__class__.__module__].MCFG["local_range_window_px"])
    radius = window // 2
    local_max = F.max_pool2d(warped, window, 1, radius)
    local_min = -F.max_pool2d(-warped, window, 1, radius)
    dynamic = (local_max - local_min).clamp_min(2 / 255)
    unit = ((warped - local_min) / dynamic).clamp(1e-3, 1 - 1e-3)
    corrected = torch.sigmoid(width * (torch.log(unit) - torch.log1p(-unit)))
    proposal = local_min + dynamic * corrected
    output = (raw.float() + support * (proposal - raw.float())).clamp(0, 1)
    return output, {"support": support, "source_support": source_support, "learned_support": learned_support, "width": width, "shift": shift, "flow": flow}


def gradient_magnitude(image: np.ndarray) -> np.ndarray:
    value = image.astype(np.float32)
    gx = cv2.Sobel(value, cv2.CV_32F, 1, 0, ksize=3)
    gy = cv2.Sobel(value, cv2.CV_32F, 0, 1, ksize=3)
    return np.sqrt(gx * gx + gy * gy)


def safe_ncc(left: np.ndarray, right: np.ndarray) -> float:
    a = left.astype(np.float64).ravel()
    b = right.astype(np.float64).ravel()
    a -= a.mean()
    b -= b.mean()
    denom = np.linalg.norm(a) * np.linalg.norm(b)
    return float(np.dot(a, b) / denom) if denom > 1e-12 else float("nan")


def edge_chamfer(left: np.ndarray, right: np.ndarray) -> float:
    a = cv2.Canny(left, 40, 100) > 0
    b = cv2.Canny(right, 40, 100) > 0
    if not a.any() or not b.any():
        return float("nan")
    distance_a = cv2.distanceTransform((~a).astype(np.uint8), cv2.DIST_L2, 5)
    distance_b = cv2.distanceTransform((~b).astype(np.uint8), cv2.DIST_L2, 5)
    return float(0.5 * (np.mean(distance_a[b]) + np.mean(distance_b[a])))


def image_metrics(raw: np.ndarray, output: np.ndarray, label: np.ndarray | None) -> dict[str, float]:
    raw_f = raw.astype(np.float32)
    out_f = output.astype(np.float32)
    residual = out_f - raw_f
    low = cv2.GaussianBlur(residual, (0, 0), 8.0)
    high = residual - low
    raw_gradient = gradient_magnitude(raw)
    out_gradient = gradient_magnitude(output)
    threshold = float(np.percentile(raw_gradient, 75))
    edge_mask = raw_gradient >= threshold
    result = {
        "mae_from_raw_gray": float(np.mean(np.abs(residual))),
        "low_frequency_residual_mae_gray": float(np.mean(np.abs(low))),
        "high_frequency_residual_rms_gray": float(np.sqrt(np.mean(high * high))),
        "mean_shift_gray": float(np.mean(residual)),
        "raw_output_ncc": safe_ncc(raw, output),
        "gradient_rms": float(np.sqrt(np.mean(out_gradient * out_gradient))),
        "gradient_ratio_to_raw": float(np.sqrt(np.mean(out_gradient * out_gradient)) / max(np.sqrt(np.mean(raw_gradient * raw_gradient)), 1e-8)),
        "raw_top_quartile_edge_mae_gray": float(np.mean(np.abs(residual[edge_mask]))),
    }
    if label is not None:
        error = out_f - label.astype(np.float32)
        mse = float(np.mean(error * error))
        result.update(
            {
                "label_mae_gray": float(np.mean(np.abs(error))),
                "label_psnr_db": float(20 * math.log10(255) - 10 * math.log10(max(mse, 1e-12))),
                "label_edge_chamfer_px": edge_chamfer(output, label),
            }
        )
    else:
        result.update({"label_mae_gray": float("nan"), "label_psnr_db": float("nan"), "label_edge_chamfer_px": float("nan")})
    return result


def annotated_panel(image: np.ndarray, label: str, target: int = 384) -> np.ndarray:
    panel = cv2.resize(image, (target, target), interpolation=cv2.INTER_AREA if image.shape[0] > target else cv2.INTER_NEAREST)
    panel = cv2.cvtColor(panel, cv2.COLOR_GRAY2BGR)
    cv2.rectangle(panel, (0, 0), (target, 30), (0, 0, 0), -1)
    cv2.putText(panel, label, (8, 21), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 1, cv2.LINE_AA)
    return panel


def make_montage(case: str, model: str, raw: np.ndarray, variants: dict[str, np.ndarray], order: list[str]) -> None:
    panels = [annotated_panel(raw, "Raw")]
    panels.extend(annotated_panel(variants[name], name) for name in order if name in variants)
    columns = 3
    rows = math.ceil(len(panels) / columns)
    blank = np.zeros_like(panels[0])
    panels.extend([blank] * (rows * columns - len(panels)))
    image = np.vstack([np.hstack(panels[index : index + columns]) for index in range(0, len(panels), columns)])
    write_png(MONTAGE_OUT / f"{case}_{model}.png", image)


def state_architecture(name: str, model: nn.Module, checkpoint: dict[str, Any], state: dict[str, torch.Tensor], arch: dict[str, Any], source: Path, checkpoint_path: Path, psf_source: str) -> dict[str, Any]:
    module_counts: dict[str, int] = {}
    for module in model.modules():
        key = module.__class__.__name__
        module_counts[key] = module_counts.get(key, 0) + 1
    simple_arch = {key: value for key, value in arch.items() if isinstance(value, (str, int, float, bool, type(None)))}
    return {
        "name": name,
        "checkpoint": str(checkpoint_path),
        "checkpoint_sha256": sha256_file(checkpoint_path),
        "epoch": checkpoint.get("epoch"),
        "source_model_file": str(source),
        "source_model_sha256": sha256_file(source),
        "parameters": int(sum(parameter.numel() for parameter in model.parameters())),
        "state_tensor_count": len(state),
        "module_counts": module_counts,
        "inferred_architecture": simple_arch,
        "checkpoint_model_config": checkpoint.get("model_config"),
        "psf_source": psf_source,
        "actual_module_presence": {
            "physics_layer": not isinstance(getattr(model, "physics_layer", None), nn.Identity),
            "weak_psf": getattr(model, "weak_psf_block", None) is not None,
            "boundary_adapter": getattr(model, "boundary_adapter", None) is not None,
            "raw_anchor_mode": getattr(getattr(model, "raw_anchor_output", None), "mode", None),
            "quality_gate": getattr(model, "quality_gate", None) is not None,
        },
    }


def compare_geo_states(r61: dict[str, torch.Tensor], v42: dict[str, torch.Tensor]) -> dict[str, Any]:
    shared = [key for key in r61 if key in v42 and tuple(r61[key].shape) == tuple(v42[key].shape)]
    exact = [key for key in shared if torch.equal(r61[key], v42[key])]
    groups = ["physics_layer", "weak_psf_block", "e1", "e2", "e3", "mid", "u3", "p3", "u2", "p2", "u1", "p1", "out", "boundary_adapter"]
    group_rows = []
    for prefix in groups:
        keys = [key for key in shared if key.startswith(prefix) and r61[key].is_floating_point()]
        if not keys:
            continue
        left = torch.cat([r61[key].float().reshape(-1) for key in keys])
        right = torch.cat([v42[key].float().reshape(-1) for key in keys])
        group_rows.append(
            {
                "group": prefix,
                "tensors": len(keys),
                "values": int(left.numel()),
                "exact_tensors": sum(torch.equal(r61[key], v42[key]) for key in keys),
                "cosine_similarity": float(F.cosine_similarity(left, right, dim=0).cpu()),
                "relative_l2_difference": float(torch.linalg.vector_norm(left - right).cpu() / torch.linalg.vector_norm(left).clamp_min(1e-12).cpu()),
            }
        )
    return {
        "shared_same_shape_tensors": len(shared),
        "exact_shared_tensors": len(exact),
        "exact_shared_fraction": len(exact) / len(shared),
        "only_r61": sorted(set(r61) - set(v42)),
        "only_v42": sorted(set(v42) - set(r61)),
        "group_comparison": group_rows,
    }


def canonical_reference(case: str, model: str) -> Path | None:
    mapping = {
        ("junhua_pitch100", "V42_E120"): Path(str(PROJECT_ROOT / 'Experiments/R111_R109V42ThesisReplacementQualification/external_gmf_v42/pitch1um_y100_v42_e120_tiled/bmp/frame_0050.bmp')),
        ("junhua_pitch100", "R109_E48"): Path(str(PROJECT_ROOT / 'Thesis_MOSR_Evidence/External_GMF_Packages/Pitch1um_Y_100_Raw_Even_R109E48/pitch1um_y100_r109_e48/bmp/frame_0050.bmp')),
        ("real_5x", "R61_v16"): Path(str(PROJECT_ROOT / 'Analyses/20260704_20x_5x_analysis/r61_v16_psfoff_5x_1um/bmp/frame_0025.bmp')),
        ("real_20x", "R61_v16"): Path(str(PROJECT_ROOT / 'Analyses/20260704_20x_5x_analysis/r61_v16_psfoff_20x_1um/bmp/frame_0025.bmp')),
        ("real_50x", "R61_v16"): Path(str(PROJECT_ROOT / 'Analyses/20260702_100MG_displacement_analysis/r61_v16_psfoff_x_1um/bmp/frame_0025.bmp')),
    }
    return mapping.get((case, model))


def canonical_crop(reference: Path, rectangle: dict[str, int]) -> np.ndarray:
    full = read_gray(reference)
    return full[
        rectangle["y"] : rectangle["y"] + rectangle["height"],
        rectangle["x"] : rectangle["x"] + rectangle["width"],
    ].copy()


def main() -> int:
    torch.manual_seed(113)
    np.random.seed(113)
    device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")
    checkpoint_paths = {name: Path(PROJECT_ROOT / entry["checkpoint"]) for name, entry in EXPERIMENT_CONFIG["models"].items()}
    hash_records = {}
    for name, path in checkpoint_paths.items():
        actual = sha256_file(path)
        expected = EXPECTED_HASHES[name]
        hash_records[name] = {"path": str(path), "expected": expected, "actual": actual, "pass": actual == expected}
        if actual != expected:
            raise RuntimeError(f"Checkpoint hash mismatch for {name}")
    samples, sample_manifest = build_samples()
    (OUT / "sample_manifest.json").write_text(json.dumps(sample_manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    loader = load_module(V42_LOADER, "r113_v42_loader")
    geo_module = load_module(V42_MODEL_FILE.parent / "infer_v42.py", "r113_geo_inference")
    temp_dirs: list[Path] = []
    v42, v42_checkpoint, v42_state, v42_arch, v42_temp, v42_psf_source = instantiate_geo(geo_module, checkpoint_paths["V42_E120"], device)
    r61, r61_checkpoint, r61_state, r61_arch, r61_temp, r61_psf_source = instantiate_geo(geo_module, checkpoint_paths["R61_v16"], device)
    for value in (v42_temp, r61_temp):
        if value is not None:
            temp_dirs.append(Path(value))
    sys.path.insert(0, str(R109_ROOT / "model"))
    import r109_model

    r109_checkpoint = torch.load(checkpoint_paths["R109_E48"], map_location="cpu", weights_only=False)
    r109 = r109_model.build_model().to(device)
    r109.load_state_dict(r109_checkpoint["model"], strict=True)
    r109.eval()

    architecture = {
        "generated_local": datetime.now().astimezone().isoformat(),
        "device": str(device),
        "checkpoint_hashes": hash_records,
        "source_model_identity": {
            "r61_model_sha256": sha256_file(R61_MODEL_FILE),
            "v42_model_sha256": sha256_file(V42_MODEL_FILE),
            "files_byte_identical": R61_MODEL_FILE.read_bytes() == V42_MODEL_FILE.read_bytes(),
        },
        "models": {
            "V42_E120": state_architecture("V42_E120", v42, v42_checkpoint, v42_state, v42_arch, V42_MODEL_FILE, checkpoint_paths["V42_E120"], v42_psf_source),
            "R61_v16": state_architecture("R61_v16", r61, r61_checkpoint, r61_state, r61_arch, R61_MODEL_FILE, checkpoint_paths["R61_v16"], r61_psf_source),
            "R109_E48": {
                "name": "R109_E48",
                "checkpoint": str(checkpoint_paths["R109_E48"]),
                "checkpoint_sha256": sha256_file(checkpoint_paths["R109_E48"]),
                "epoch": r109_checkpoint.get("epoch"),
                "source_model_file": str(R109_ROOT / "model" / "r109_model.py"),
                "source_model_sha256": sha256_file(R109_ROOT / "model" / "r109_model.py"),
                "parameters": int(sum(parameter.numel() for parameter in r109.parameters())),
                "state_tensor_count": len(r109_checkpoint["model"]),
                "module_counts": {name: sum(module.__class__.__name__ == name for module in r109.modules()) for name in sorted({module.__class__.__name__ for module in r109.modules()})},
                "config": r109_checkpoint.get("config", {}).get("model"),
                "actual_module_presence": {"detector": True, "source_support": True, "learned_support": True, "width_control": True, "normal_shift_control": True},
            },
        },
        "r61_v42_weight_inheritance": compare_geo_states(r61_state, v42_state),
        "r61_locked_deployment_policy": {
            "physics_alpha": 0.0,
            "weak_psf_enabled": False,
            "evidence": "R61 real-sample validation manifests use psf_mode=off and weak_psf=false; checkpoint-native modules are inventoried separately.",
        },
    }
    (OUT / "architecture_inventory.json").write_text(json.dumps(architecture, ensure_ascii=False, indent=2), encoding="utf-8")
    pd.DataFrame(architecture["r61_v42_weight_inheritance"]["group_comparison"]).to_csv(OUT / "r61_v42_weight_group_comparison.csv", index=False, encoding="utf-8-sig")

    metric_rows: list[dict[str, Any]] = []
    internal_rows: list[dict[str, Any]] = []
    reproduction_rows: list[dict[str, Any]] = []

    try:
        for sample_index, sample in enumerate(samples, start=1):
            case = sample["case"]
            raw = sample["image"]
            label = sample["label_image"]
            tensor = to_tensor(raw, device)
            print(json.dumps({"case": case, "index": sample_index, "total": len(samples)}), flush=True)

            # V42: capture the natural full path, then intervene on one module at a time.
            hook_store: dict[str, Any] = {}
            handles = register_geo_hooks(v42, hook_store)
            with torch.inference_mode():
                v42_full_tensor = v42(tensor)
            for handle in handles:
                handle.remove()
            v42_quality_score_full = (
                float(v42.quality_gate.last_quality_score.float().mean().cpu())
                if getattr(v42, "quality_gate", None) is not None and v42.quality_gate.last_quality_score is not None
                else float("nan")
            )
            v42_variants: dict[str, np.ndarray] = {"full": to_u8(v42_full_tensor)}
            if "raw_anchor" in hook_store:
                v42_variants["pre_anchor_output"] = to_u8(hook_store["raw_anchor"]["inputs"][-1])
                v42_variants["post_anchor_pre_quality"] = to_u8(hook_store["raw_anchor"]["output"])
            with temporary_attributes(v42, physics_layer=nn.Identity()):
                with torch.inference_mode():
                    v42_variants["no_main_physics"] = to_u8(v42(tensor))
            with temporary_attributes(v42, weak_psf_block=None):
                with torch.inference_mode():
                    v42_variants["no_weak_psf"] = to_u8(v42(tensor))
            with temporary_attributes(v42, boundary_adapter=None):
                with torch.inference_mode():
                    v42_variants["no_boundary_adapter"] = to_u8(v42(tensor))
            old_anchor_mode = v42.raw_anchor_output.mode
            v42.raw_anchor_output.mode = "none"
            with torch.inference_mode():
                v42_variants["no_raw_anchor"] = to_u8(v42(tensor))
            v42.raw_anchor_output.mode = old_anchor_mode
            with temporary_attributes(v42, quality_gate=None):
                with torch.inference_mode():
                    v42_variants["no_quality_gate"] = to_u8(v42(tensor))
            for module_name, captured in hook_store.items():
                if module_name == "quality_gate":
                    internal_rows.append({"model": "V42_E120", "case": case, "module": module_name, "scale_mean": float(captured["output"].float().mean().cpu()), "quality_score": v42_quality_score_full})
                elif captured["inputs"] and isinstance(captured["output"], torch.Tensor):
                    before = captured["inputs"][-1]
                    after = captured["output"]
                    if before.shape == after.shape:
                        internal_rows.append(tensor_pair_stats("V42_E120", case, module_name, before, after))
            if getattr(v42, "weak_psf_block", None) is not None:
                internal_rows.append({"model": "V42_E120", "case": case, "module": "weak_psf_state", "beta_scale": float(v42.weak_psf_block.beta_scale.detach().cpu()), "last_beta": float(v42.weak_psf_block.last_beta), "last_bypass": bool(v42.weak_psf_block.last_bypass)})

            # R61: distinguish checkpoint-native modules from the locked PSF-off deployment.
            hook_store = {}
            handles = register_geo_hooks(r61, hook_store)
            with torch.inference_mode():
                r61_native_tensor = r61(tensor)
            for handle in handles:
                handle.remove()
            r61_variants: dict[str, np.ndarray] = {"checkpoint_native_full": to_u8(r61_native_tensor)}
            with temporary_attributes(r61, physics_layer=nn.Identity()):
                with torch.inference_mode():
                    r61_variants["native_no_main_physics"] = to_u8(r61(tensor))
            with temporary_attributes(r61, weak_psf_block=None):
                with torch.inference_mode():
                    r61_variants["native_no_weak_psf"] = to_u8(r61(tensor))
            with temporary_attributes(r61, boundary_adapter=None):
                with torch.inference_mode():
                    r61_variants["native_no_boundary_adapter"] = to_u8(r61(tensor))
            with temporary_scalar(r61.physics_layer.alpha, 0.0):
                with temporary_attributes(r61, weak_psf_block=None):
                    with torch.inference_mode():
                        r61_locked_tensor = r61(tensor)
                    r61_variants["locked_psf_off_full"] = to_u8(r61_locked_tensor)
                    with temporary_attributes(r61, boundary_adapter=None):
                        with torch.inference_mode():
                            r61_variants["locked_psf_off_no_boundary"] = to_u8(r61(tensor))
            for module_name, captured in hook_store.items():
                if captured["inputs"] and isinstance(captured["output"], torch.Tensor):
                    before = captured["inputs"][-1]
                    after = captured["output"]
                    if before.shape == after.shape:
                        internal_rows.append(tensor_pair_stats("R61_v16_checkpoint_native", case, module_name, before, after))
            if getattr(r61, "weak_psf_block", None) is not None:
                internal_rows.append({"model": "R61_v16_checkpoint_native", "case": case, "module": "weak_psf_state", "beta_scale": float(r61.weak_psf_block.beta_scale.detach().cpu()), "last_beta": float(r61.weak_psf_block.last_beta), "last_bypass": bool(r61.weak_psf_block.last_bypass)})

            # R109: replay its renderer exactly, then replace one learned control at a time.
            with torch.inference_mode():
                details = r109.forward_details(tensor)
                r109_variants: dict[str, np.ndarray] = {}
                r109_maps: dict[str, dict[str, torch.Tensor]] = {}
                for variant in ["full", "identity", "width_only", "shift_only", "no_shift", "no_width", "learned_support_only", "source_support_only", "smoothed_controls"]:
                    output, maps = render_variant_aligned(r109, tensor, details, variant)
                    r109_variants[variant] = to_u8(output)
                    r109_maps[variant] = maps
                reproduction_error = float(torch.max(torch.abs(torch.from_numpy(r109_variants["full"].astype(np.int16)) - torch.from_numpy(to_u8(details.output).astype(np.int16)))).item())
                reproduction_rows.append({"case": case, "model": "R109_E48", "comparison_scope": "renderer_exact", "renderer_reproduction_max_gray": reproduction_error})
                raw_gradient = gradient_magnitude(raw)
                edge_mask_np = raw_gradient >= np.percentile(raw_gradient, 75)
                edge_mask = torch.from_numpy(edge_mask_np).to(device).reshape(1, 1, *edge_mask_np.shape)
                full_maps = r109_maps["full"]
                for map_name in ["support", "source_support", "learned_support", "width", "shift"]:
                    value = full_maps[map_name]
                    internal_rows.append(
                        {
                            "model": "R109_E48",
                            "case": case,
                            "module": map_name,
                            "full_mean": float(value.mean().cpu()),
                            "full_std": float(value.std(unbiased=False).cpu()),
                            "raw_top_quartile_edge_mean": float(value[edge_mask].mean().cpu()),
                            "raw_top_quartile_edge_std": float(value[edge_mask].std(unbiased=False).cpu()),
                            "p05": float(torch.quantile(value.reshape(-1), 0.05).cpu()),
                            "p95": float(torch.quantile(value.reshape(-1), 0.95).cpu()),
                            "mask_definition": "top quartile of Raw Sobel gradient, fixed before model output",
                        }
                    )

            all_models = {"V42_E120": v42_variants, "R61_v16": r61_variants, "R109_E48": r109_variants}
            reference_variants = {"V42_E120": "full", "R61_v16": "locked_psf_off_full", "R109_E48": "full"}
            for model_name, variants in all_models.items():
                reference_name = reference_variants[model_name]
                reference = variants[reference_name].astype(np.float32)
                for variant, output in variants.items():
                    output_path = IMAGE_OUT / case / model_name / f"{variant}.png"
                    write_png(output_path, output)
                    contrast = output.astype(np.float32) - reference
                    metric_rows.append(
                        {
                            "case": case,
                            "family": sample["family"],
                            "model": model_name,
                            "variant": variant,
                            "causal_reference_variant": reference_name,
                            "causal_mae_from_reference_gray": float(np.mean(np.abs(contrast))),
                            "causal_max_from_reference_gray": float(np.max(np.abs(contrast))),
                            "output_path": str(output_path),
                            "output_sha256": sha256_file(output_path),
                            **image_metrics(raw, output, label),
                        }
                    )
                canonical = canonical_reference(case, model_name)
                if canonical is not None and canonical.is_file():
                    expected = canonical_crop(canonical, sample["rectangle"])
                    actual = variants[reference_name]
                    margin = min(128, actual.shape[0] // 4, actual.shape[1] // 4)
                    difference = np.abs(actual.astype(np.int16) - expected.astype(np.int16))
                    core = difference[margin:-margin, margin:-margin]
                    reproduction_rows.append(
                        {
                            "case": case,
                            "model": model_name,
                            "comparison_scope": "crop_inference_vs_full_or_tiled_context",
                            "canonical_reference": str(canonical),
                            "canonical_reference_sha256": sha256_file(canonical),
                            "reference_variant": reference_name,
                            "center_core_margin": margin,
                            "center_core_mae_gray": float(core.mean()),
                            "center_core_max_gray": int(core.max()),
                        }
                    )
            make_montage(case, "V42_E120", raw, v42_variants, ["full", "no_main_physics", "no_weak_psf", "no_boundary_adapter", "no_raw_anchor", "no_quality_gate"])
            make_montage(case, "R61_v16", raw, r61_variants, ["locked_psf_off_full", "locked_psf_off_no_boundary", "checkpoint_native_full", "native_no_main_physics", "native_no_weak_psf"])
            make_montage(case, "R109_E48", raw, r109_variants, ["full", "identity", "width_only", "shift_only", "source_support_only", "learned_support_only", "smoothed_controls"])

        # One exact-size R61 replay separates loader correctness from its known
        # spatial-context sensitivity (GroupNorm uses the whole inference area).
        r61_full_source = Path(str(PROJECT_ROOT / 'Analyses/20260704_20x_5x_analysis/raw_inputs/5x_1um/bmp/frame_0025.bmp'))
        r61_full_reference = Path(str(PROJECT_ROOT / 'Analyses/20260704_20x_5x_analysis/r61_v16_psfoff_5x_1um/bmp/frame_0025.bmp'))
        r61_full_raw = read_gray(r61_full_source)
        r61_full_tensor = to_tensor(r61_full_raw, device)
        with temporary_scalar(r61.physics_layer.alpha, 0.0):
            with temporary_attributes(r61, weak_psf_block=None):
                with torch.inference_mode():
                    r61_full_replay = to_u8(r61(r61_full_tensor))
        r61_full_expected = read_gray(r61_full_reference)
        r61_full_difference = np.abs(r61_full_replay.astype(np.int16) - r61_full_expected.astype(np.int16))
        reproduction_rows.append(
            {
                "case": "real_5x",
                "model": "R61_v16",
                "comparison_scope": "full_frame_exact_runtime",
                "canonical_reference": str(r61_full_reference),
                "canonical_reference_sha256": sha256_file(r61_full_reference),
                "reference_variant": "locked_psf_off_full",
                "center_core_margin": 0,
                "center_core_mae_gray": float(r61_full_difference.mean()),
                "center_core_max_gray": int(r61_full_difference.max()),
            }
        )

        metrics = pd.DataFrame(metric_rows)
        internals = pd.DataFrame(internal_rows)
        reproductions = pd.DataFrame(reproduction_rows)
        metrics.to_csv(OUT / "per_case_variant_metrics.csv", index=False, encoding="utf-8-sig")
        internals.to_csv(OUT / "internal_module_statistics.csv", index=False, encoding="utf-8-sig")
        reproductions.to_csv(OUT / "reproduction_checks.csv", index=False, encoding="utf-8-sig")

        causal = (
            metrics.groupby(["model", "variant", "causal_reference_variant"], as_index=False)
            .agg(
                cases=("case", "count"),
                median_causal_mae_gray=("causal_mae_from_reference_gray", "median"),
                max_causal_mae_gray=("causal_mae_from_reference_gray", "max"),
                median_low_frequency_change_gray=("low_frequency_residual_mae_gray", "median"),
                median_high_frequency_residual_rms_gray=("high_frequency_residual_rms_gray", "median"),
                median_gradient_ratio=("gradient_ratio_to_raw", "median"),
                median_raw_ncc=("raw_output_ncc", "median"),
                synthetic_label_mae_gray=("label_mae_gray", "median"),
                synthetic_edge_chamfer_px=("label_edge_chamfer_px", "median"),
            )
        )
        causal.to_csv(OUT / "causal_contrast_summary.csv", index=False, encoding="utf-8-sig")
        summary = {
            "status": "complete",
            "generated_local": datetime.now().astimezone().isoformat(),
            "device": str(device),
            "cases": [sample["case"] for sample in samples],
            "case_count": len(samples),
            "variant_output_count": len(metrics),
            "architecture_inventory": str(OUT / "architecture_inventory.json"),
            "causal_summary": json.loads(causal.to_json(orient="records")),
            "reproduction_checks": json.loads(reproductions.to_json(orient="records")),
            "interpretation_boundaries": [
                "Intervention effects are causal for the frozen model output on this bounded matched set.",
                "Real-image appearance metrics are not geometric ground truth.",
                "Synthetic label metrics are known-truth checks but do not substitute for SEM ACM.",
                "R61 checkpoint-native PSF modules are separated from the locked PSF-off deployment used by prior real-sample validation.",
                "No external GMF score is inferred from internal or appearance metrics.",
            ],
        }
        (OUT / "analysis_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
        print(json.dumps({"status": "complete", "cases": len(samples), "variant_outputs": len(metrics)}), flush=True)
        return 0
    finally:
        for directory in temp_dirs:
            shutil.rmtree(directory, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())

"""Probe V42 and R109 component effects on representative JunHua target crops."""
from __future__ import annotations

import importlib.util
import json
import shutil
import sys
from datetime import datetime
from pathlib import Path

import cv2
import numpy as np
import pandas as pd
import torch
from torch import nn
PROJECT_ROOT = Path(__file__).resolve().parents[3]


ROOT = Path(__file__).resolve().parents[1]
CONFIG = json.loads((ROOT / "config" / "experiment.json").read_text(encoding="utf-8"))
OUTPUT = ROOT / "results" / "component_probes"
OUTPUT.mkdir(parents=True, exist_ok=True)
FRAMES = [1, 25, 50, 75, 100]
CROP_SIZE = 1536

R111_V42_LOADER = Path(
    str(PROJECT_ROOT / 'Experiments/R111_R109V42ThesisReplacementQualification/scripts/build_v42_external_gmf.py')
)
R109_MODEL_ROOT = Path(str(PROJECT_ROOT / 'Experiments/R109_StagedMidpointWidthScratch'))


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


def parse_coordinates(path: Path) -> pd.DataFrame:
    rows: list[dict[str, float | int]] = []
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        parts = [part.strip() for part in line.split(",")]
        values = {parts[index]: parts[index + 1] for index in range(0, len(parts), 2)}
        rows.append(
            {
                "frame_index": int(values["FileName"][6:10]),
                "x": float(values["PosX"]),
                "y": float(values["PosY"]),
            }
        )
    return pd.DataFrame(rows).set_index("frame_index")


def to_tensor(image: np.ndarray, device: torch.device) -> torch.Tensor:
    return torch.from_numpy(image.astype(np.float32)[None, None] / 255.0).to(device)


def to_u8(tensor: torch.Tensor) -> np.ndarray:
    return np.round(tensor.detach().float().clamp(0, 1)[0, 0].cpu().numpy() * 255.0).astype(np.uint8)


def radial_features(image: np.ndarray) -> dict[str, float]:
    small = cv2.resize(image, (384, 384), interpolation=cv2.INTER_AREA)
    yy, xx = np.indices(small.shape, dtype=np.float32)
    radius = np.sqrt((xx - 191.5) ** 2 + (yy - 191.5) ** 2)
    index = np.floor(radius).astype(np.int32)
    sums = np.bincount(index.ravel(), weights=small.astype(np.float64).ravel(), minlength=192)
    counts = np.bincount(index.ravel(), minlength=192)
    profile = sums[:192] / np.maximum(counts[:192], 1)
    search = profile[100:170]
    peak = int(np.argmax(search)) + 100
    baseline = 0.5 * (float(np.median(profile[30:95])) + float(np.median(profile[175:188])))
    peak_value = float(profile[peak])
    threshold = baseline + 0.5 * (peak_value - baseline)
    inner_candidates = np.flatnonzero(profile[:peak] <= threshold)
    outer_candidates = np.flatnonzero(profile[peak:] <= threshold)
    inner = float(inner_candidates[-1]) if len(inner_candidates) else np.nan
    outer = float(peak + outer_candidates[0]) if len(outer_candidates) else np.nan
    scale = CROP_SIZE / 384.0
    return {
        "ring_peak_radius_px": peak * scale,
        "ring_width_px": (outer - inner) * scale,
        "ring_contrast_gray": peak_value - baseline,
    }


def image_metrics(raw: np.ndarray, output: np.ndarray, canonical: np.ndarray) -> dict[str, float]:
    raw_f = raw.astype(np.float32)
    output_f = output.astype(np.float32)
    residual = output_f - raw_f
    low_residual = cv2.GaussianBlur(residual, (0, 0), 8.0)
    high = output_f - cv2.GaussianBlur(output_f, (0, 0), 1.5)
    return {
        "mean_abs_change_gray": float(np.mean(np.abs(residual))),
        "low_frequency_residual_mae_gray": float(np.mean(np.abs(low_residual))),
        "high_frequency_rms_gray": float(np.sqrt(np.mean(high**2))),
        "canonical_crop_mae_gray": float(np.mean(np.abs(output_f - canonical.astype(np.float32)))),
        **radial_features(output),
    }


def v42_raw_anchor(raw: np.ndarray, pred: np.ndarray) -> np.ndarray:
    raw_f = raw.astype(np.float32)
    pred_f = pred.astype(np.float32)
    pred_low = cv2.GaussianBlur(pred_f, (0, 0), 2.0)
    output = raw_f + 0.35 * (pred_f - pred_low)
    output += raw_f.mean() - output.mean()
    return np.clip(np.round(output), 0, 255).astype(np.uint8)


def main() -> int:
    coordinates = parse_coordinates(Path(PROJECT_ROOT / CONFIG["models"]["Raw"]["score"]))
    raw_dir = Path(PROJECT_ROOT / CONFIG["models"]["Raw"]["image_dir"])
    v42_dir = Path(PROJECT_ROOT / CONFIG["models"]["V42 E120"]["image_dir"])
    r109_dir = Path(PROJECT_ROOT / CONFIG["models"]["R109 E48"]["image_dir"])

    v42_loader = load_module(R111_V42_LOADER, "r112_v42_loader")
    _, v42_model, device, temp_psf_dir, _, _ = v42_loader.load_model()
    sys.path.insert(0, str(R109_MODEL_ROOT / "model"))
    from r109_model import build_model

    r109_payload = torch.load(Path(PROJECT_ROOT / CONFIG["models"]["R109 E48"]["checkpoint"]), map_location=device, weights_only=False)
    r109_model = build_model().to(device)
    r109_model.load_state_dict(r109_payload["model"])
    r109_model.eval()

    rows: list[dict[str, object]] = []
    internal_rows: list[dict[str, object]] = []
    hooks: dict[str, torch.Tensor | tuple[torch.Tensor, ...]] = {}

    def capture(name: str):
        def hook(_module, inputs, output):
            hooks[f"{name}_inputs"] = tuple(value.detach() for value in inputs if isinstance(value, torch.Tensor))
            hooks[f"{name}_output"] = output.detach() if isinstance(output, torch.Tensor) else output
        return hook

    handles = [
        v42_model.physics_layer.register_forward_hook(capture("physics")),
        v42_model.boundary_adapter.register_forward_hook(capture("boundary")),
        v42_model.raw_anchor_output.register_forward_hook(capture("anchor")),
        v42_model.quality_gate.register_forward_hook(capture("quality")),
    ]

    try:
        for frame_index in FRAMES:
            name = f"frame_{frame_index:04d}.bmp"
            center = (float(coordinates.loc[frame_index, "x"]), float(coordinates.loc[frame_index, "y"]))
            raw_full = read_gray(raw_dir / name)
            raw = cv2.getRectSubPix(raw_full, (CROP_SIZE, CROP_SIZE), center)
            v42_canonical = cv2.getRectSubPix(read_gray(v42_dir / name), (CROP_SIZE, CROP_SIZE), center)
            r109_canonical = cv2.getRectSubPix(read_gray(r109_dir / name), (CROP_SIZE, CROP_SIZE), center)
            tensor = to_tensor(raw, device)

            hooks.clear()
            with torch.inference_mode():
                v42_full_tensor = v42_model(tensor)
            v42_full = to_u8(v42_full_tensor)
            physics = hooks["physics_output"]
            boundary_inputs = hooks["boundary_inputs"]
            boundary_base = boundary_inputs[-1]
            boundary_output = hooks["boundary_output"]
            anchor_inputs = hooks["anchor_inputs"]
            anchor_pred = anchor_inputs[-1]
            anchor_output = hooks["anchor_output"]
            quality_scale = hooks["quality_output"]
            quality_score = v42_model.last_quality_gate
            internal_rows.append(
                {
                    "frame_index": frame_index,
                    "model": "V42 E120",
                    "physics_mae_from_raw": float(torch.mean(torch.abs(physics.float() - tensor.float())).cpu() * 255.0),
                    "boundary_adapter_mae": float(torch.mean(torch.abs(boundary_output.float() - boundary_base.float())).cpu() * 255.0),
                    "raw_anchor_mae_from_pre_anchor": float(torch.mean(torch.abs(anchor_output.float() - anchor_pred.float())).cpu() * 255.0),
                    "raw_anchor_lowfreq_mae_from_raw": float(np.mean(np.abs(cv2.GaussianBlur(to_u8(anchor_output).astype(np.float32), (0, 0), 8.0) - cv2.GaussianBlur(raw.astype(np.float32), (0, 0), 8.0)))),
                    "quality_score": float(quality_score.mean().cpu()),
                    "quality_scale": float(quality_scale.mean().cpu()),
                    "weak_psf_beta_scale": float(v42_model.weak_psf_block.beta_scale.detach().cpu()),
                }
            )

            original_anchor_mode = v42_model.raw_anchor_output.mode
            v42_model.raw_anchor_output.mode = "none"
            with torch.inference_mode():
                v42_no_anchor = to_u8(v42_model(tensor))
            v42_model.raw_anchor_output.mode = original_anchor_mode

            original_quality = v42_model.quality_gate
            v42_model.quality_gate = None
            with torch.inference_mode():
                v42_no_quality = to_u8(v42_model(tensor))
            v42_model.quality_gate = original_quality

            original_boundary = v42_model.boundary_adapter
            v42_model.boundary_adapter = None
            with torch.inference_mode():
                v42_no_boundary = to_u8(v42_model(tensor))
            v42_model.boundary_adapter = original_boundary

            original_physics = v42_model.physics_layer
            v42_model.physics_layer = nn.Identity()
            with torch.inference_mode():
                v42_no_physics = to_u8(v42_model(tensor))
            v42_model.physics_layer = original_physics

            with torch.inference_mode():
                r109_details = r109_model.forward_details(tensor)
            r109_full = to_u8(r109_details.output)
            support = r109_details.support.detach().float()
            width = r109_details.width_gain.detach().float()
            shift = r109_details.normal_shift.detach().float()
            internal_rows.append(
                {
                    "frame_index": frame_index,
                    "model": "R109 E48",
                    "support_mean": float(support.mean().cpu()),
                    "support_fraction_over_0p5": float((support > 0.5).float().mean().cpu()),
                    "width_gain_mean": float(width.mean().cpu()),
                    "width_gain_p95": float(torch.quantile(width.flatten(), 0.95).cpu()),
                    "normal_shift_abs_mean_px": float(torch.mean(torch.abs(shift)).cpu()),
                    "normal_shift_abs_p95_px": float(torch.quantile(torch.abs(shift).flatten(), 0.95).cpu()),
                }
            )

            shift_weight = r109_model.shift_head.weight.detach().clone()
            shift_bias = r109_model.shift_head.bias.detach().clone()
            r109_model.shift_head.weight.data.zero_()
            r109_model.shift_head.bias.data.zero_()
            with torch.inference_mode():
                r109_no_shift = to_u8(r109_model(tensor))
            r109_model.shift_head.weight.data.copy_(shift_weight)
            r109_model.shift_head.bias.data.copy_(shift_bias)

            width_weight = r109_model.width_head.weight.detach().clone()
            width_bias = r109_model.width_head.bias.detach().clone()
            r109_model.width_head.weight.data.zero_()
            r109_model.width_head.bias.data.fill_(-20.0)
            with torch.inference_mode():
                r109_shift_only = to_u8(r109_model(tensor))
            r109_model.width_head.weight.data.copy_(width_weight)
            r109_model.width_head.bias.data.copy_(width_bias)
            r109_anchor = v42_raw_anchor(raw, r109_full)

            variants = {
                "V42 full crop": (v42_full, v42_canonical),
                "V42 no raw anchor": (v42_no_anchor, v42_canonical),
                "V42 no quality gate": (v42_no_quality, v42_canonical),
                "V42 no boundary adapter": (v42_no_boundary, v42_canonical),
                "V42 no physics": (v42_no_physics, v42_canonical),
                "R109 full crop": (r109_full, r109_canonical),
                "R109 no normal shift": (r109_no_shift, r109_canonical),
                "R109 shift only": (r109_shift_only, r109_canonical),
                "R109 V42-like raw anchor": (r109_anchor, r109_canonical),
            }
            for variant, (output, canonical) in variants.items():
                rows.append({"frame_index": frame_index, "variant": variant, **image_metrics(raw, output, canonical)})
            print(json.dumps({"frame": frame_index, "variants": len(variants)}), flush=True)
    finally:
        for handle in handles:
            handle.remove()
        if temp_psf_dir is not None:
            shutil.rmtree(temp_psf_dir, ignore_errors=True)

    table = pd.DataFrame(rows)
    internals = pd.DataFrame(internal_rows)
    table.to_csv(OUTPUT / "component_probe_per_frame.csv", index=False, encoding="utf-8-sig")
    internals.to_csv(OUTPUT / "internal_state_per_frame.csv", index=False, encoding="utf-8-sig")
    summary = (
        table.groupby("variant", as_index=False)
        .agg(
            frames=("frame_index", "count"),
            residual_mae_gray=("mean_abs_change_gray", "median"),
            low_frequency_residual_mae_gray=("low_frequency_residual_mae_gray", "median"),
            high_frequency_rms_gray=("high_frequency_rms_gray", "median"),
            canonical_crop_mae_gray=("canonical_crop_mae_gray", "median"),
            ring_peak_radius_std_px=("ring_peak_radius_px", "std"),
            ring_width_std_px=("ring_width_px", "std"),
            ring_contrast_std_gray=("ring_contrast_gray", "std"),
        )
    )
    summary.to_csv(OUTPUT / "component_probe_summary.csv", index=False, encoding="utf-8-sig")
    result = {
        "status": "complete",
        "generated_local": datetime.now().astimezone().isoformat(),
        "frames": FRAMES,
        "crop_size": CROP_SIZE,
        "summary": summary.to_dict(orient="records"),
        "internal_state": internals.to_dict(orient="records"),
        "interpretation_boundary": "Crop-level component probes are directional and are not external-GMF scores.",
    }
    (OUTPUT / "analysis_summary.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"status": "complete", "frames": len(FRAMES), "variants": len(summary)}), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

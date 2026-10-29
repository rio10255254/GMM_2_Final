from __future__ import annotations

import argparse
import csv
import json
import math
import shutil
import sys
import tempfile
import time
from contextlib import contextmanager
from pathlib import Path

import cv2
import matplotlib
import numpy as np
import scipy.io
import torch

matplotlib.use("Agg")
import matplotlib.pyplot as plt
PROJECT_ROOT = Path(__file__).resolve().parents[8]


ROOT = Path(str(PROJECT_ROOT / 'Thesis_MOSR_Evidence'))
PACKAGE = ROOT / "LabSystem_MOSR" / "Model_Packages" / "V42_SoftLabelSNR_FullStandalone_20260709"
FINAL_CHECKPOINT = (
    PACKAGE
    / "results"
    / "training_results"
    / "training_progress_V42_SoftLabelSNR_full_training_20260709_202710_20260709_202713"
    / "epoch_120.pth.tar"
)
BASE_CHECKPOINT = PACKAGE / "weights" / "base_v41_standalone_best_tradeoff.pth.tar"
FORMAL_ROOT = ROOT / "Final_Data_Figures" / "02_V42_E120_SOURCE_MATERIAL" / "reconstructions"
OUTPUT_ROOT = ROOT / "Final_Data_Figures" / "05_ABLATION_DIAGNOSTICS" / "boundary_position_diagnostic"
SEQUENCE_CONFIG = (
    ROOT
    / "Final_Data_Figures"
    / "01_CURRENT_THESIS_RESULTS_V42_CENTER9"
    / "config"
    / "sequence_center9_50x20x.json"
)

SEQUENCE_OUTPUT_NAMES = {
    "50x_x_0p5um": "50x_0p5um",
    "50x_x_1um": "50x_1um",
    "20x_0p5um": "20x_0p5um",
    "20x_1um": "20x_1um",
}

STATIC_INPUTS = {
    "50x": ROOT
    / "Final_Data_Figures"
    / "03_PSF_EXPERIMENT_RESULTS"
    / "01_global_bads_fit"
    / "source_data"
    / "center9_pillar_fit_20x_50x"
    / "v42_crop_rerun"
    / "inputs"
    / "50x_original_pillar_3x3.bmp",
    "20x": ROOT
    / "Final_Data_Figures"
    / "03_PSF_EXPERIMENT_RESULTS"
    / "01_global_bads_fit"
    / "source_data"
    / "center9_pillar_fit_20x_50x"
    / "v42_crop_rerun"
    / "inputs"
    / "20x_original_pillar_3x3.bmp",
}

if str(PACKAGE) not in sys.path:
    sys.path.insert(0, str(PACKAGE))

import infer_v42 as infer  # noqa: E402
from model_v42 import GeoEdgeAlignSR_v1_v5_NoCoord  # noqa: E402


def clean_state_dict(checkpoint: dict) -> dict[str, torch.Tensor]:
    state = checkpoint.get("state_dict", checkpoint)
    return {
        (key[7:] if key.startswith("module.") else key): value
        for key, value in state.items()
    }


@contextmanager
def checkpoint_psf_file(state: dict[str, torch.Tensor]):
    psfs = state.get("physics_layer.PSFs")
    if not isinstance(psfs, torch.Tensor) or psfs.ndim != 4:
        raise RuntimeError("The checkpoint does not contain a usable fixed optical kernel stack.")
    stack = psfs.detach().cpu().float().numpy()[0]
    fitted = stack[0] if stack.shape[0] == 1 else np.transpose(stack, (1, 2, 0))
    folder = Path(tempfile.mkdtemp(prefix="mosr_ablation_psf_"))
    path = folder / "fixed_optics_from_checkpoint.mat"
    scipy.io.savemat(path, {"fitted_psf": fitted})
    try:
        yield path
    finally:
        shutil.rmtree(folder, ignore_errors=True)


def build_model(
    checkpoint_path: Path,
    device: torch.device,
    *,
    boundary_enabled: bool = True,
) -> tuple[torch.nn.Module, dict]:
    checkpoint = torch.load(checkpoint_path, map_location="cpu")
    state = clean_state_dict(checkpoint)
    arch = infer.infer_arch_from_state(state, ckpt_obj=checkpoint)
    model_config = checkpoint.get("model_config", {}) if isinstance(checkpoint, dict) else {}
    raw_anchor = model_config.get("raw_anchor_output", {})
    quality_gate = model_config.get("quality_gate", {})

    with checkpoint_psf_file(state) as psf_path:
        model = GeoEdgeAlignSR_v1_v5_NoCoord(
            in_ch=int(arch["in_ch"]),
            base=int(arch["base"]),
            use_physics_layer=bool(arch["use_physics_layer"]),
            use_sigmoid_output=True,
            use_upsample_conv=True,
            use_band_limit=bool(arch["use_band_limit"]),
            band_limit_cutoff=0.95,
            band_limit_order=8.0,
            psf_fitted_path=str(psf_path),
            psf_grid_rows=None,
            psf_grid_cols=None,
            psf_use_stack_mean=True,
            psf_deconv_reg=float(arch["psf_deconv_reg"] or 10.0),
            psf_phys_alpha_init=float(arch["psf_phys_alpha_init"] or 0.10),
            psf_phys_trainable_reg=False,
            # The locked thesis inference disabled the adaptive branch.  It is
            # held disabled in every diagnostic condition; this is not an
            # optical-module ablation.
            weak_psf_enable=False,
            boundary_residual_adapter_enable=bool(arch["boundary_residual_adapter_enable"]),
            boundary_residual_adapter_hidden=int(arch["boundary_residual_adapter_hidden"]),
            boundary_residual_adapter_max=float(arch["boundary_residual_adapter_max"]),
            boundary_residual_adapter_gate_bias=float(arch["boundary_residual_adapter_gate_bias"]),
            boundary_residual_adapter_delta_bias=bool(arch["boundary_residual_adapter_delta_bias"]),
            boundary_residual_adapter_zero_mean=bool(arch["boundary_residual_adapter_zero_mean"]),
            boundary_residual_adapter_edge_gate=bool(arch["boundary_residual_adapter_edge_gate"]),
            boundary_residual_adapter_polarity_split=bool(arch["boundary_residual_adapter_polarity_split"]),
            boundary_residual_adapter_orientation_inputs=bool(arch["boundary_residual_adapter_orientation_inputs"]),
            raw_anchor_output_mode=str(raw_anchor.get("mode", "none")),
            raw_anchor_output_alpha=float(raw_anchor.get("alpha", 0.10)),
            raw_anchor_output_sigma=float(raw_anchor.get("sigma", 2.0)),
            raw_anchor_output_detail_gain=float(raw_anchor.get("detail_gain", 0.35)),
            quality_gate_enable=bool(quality_gate.get("enable", arch["quality_gate_enable"])),
            quality_gate_hidden=int(quality_gate.get("hidden", arch["quality_gate_hidden"])),
            quality_gate_scale_min=float(quality_gate.get("scale_min", arch["quality_gate_scale_min"])),
            quality_gate_scale_max=float(quality_gate.get("scale_max", arch["quality_gate_scale_max"])),
        )

    filtered_state = {
        key: value for key, value in state.items() if not key.startswith("weak_psf_block.")
    }
    result = model.load_state_dict(filtered_state, strict=False)
    unexpected = [key for key in result.unexpected_keys if key != "band_limit.filter_mask"]
    missing = [key for key in result.missing_keys if key != "band_limit.filter_mask"]
    if missing or unexpected:
        raise RuntimeError(f"Checkpoint mismatch. missing={missing}, unexpected={unexpected}")
    if not boundary_enabled:
        model.boundary_adapter = None
    model = model.to(device).eval()
    return model, {
        "checkpoint": str(checkpoint_path),
        "epoch": checkpoint.get("epoch") if isinstance(checkpoint, dict) else None,
        "boundary_enabled": bool(boundary_enabled),
        "quality_gate_enabled": model.quality_gate is not None,
        "fixed_optics_enabled": bool(arch["use_physics_layer"]),
        "adaptive_optics_enabled": False,
        "raw_anchor_mode": str(raw_anchor.get("mode", "none")),
    }


def read_gray01(path: Path) -> tuple[np.ndarray, np.dtype]:
    raw = cv2.imread(str(path), cv2.IMREAD_UNCHANGED)
    if raw is None:
        raise FileNotFoundError(path)
    if raw.ndim == 3:
        raw = cv2.cvtColor(raw, cv2.COLOR_BGR2GRAY)
    dtype = raw.dtype
    if np.issubdtype(dtype, np.integer):
        info = np.iinfo(dtype)
        image = (raw.astype(np.float32) - info.min) / float(info.max - info.min)
    else:
        image = raw.astype(np.float32)
        if float(image.max()) > 1.5:
            image /= 255.0
    return np.clip(image, 0.0, 1.0), dtype


@torch.inference_mode()
def infer_array(model: torch.nn.Module, image01: np.ndarray, device: torch.device) -> np.ndarray:
    h, w = image01.shape
    hp = int(math.ceil(h / 64.0) * 64)
    wp = int(math.ceil(w / 64.0) * 64)
    padded = np.pad(image01, ((0, hp - h), (0, wp - w)), mode="reflect")
    tensor = torch.from_numpy(padded.astype(np.float32)).unsqueeze(0).unsqueeze(0).to(device)
    output = model(tensor).clamp(0.0, 1.0)[0, 0, :h, :w]
    return output.detach().cpu().numpy().astype(np.float32)


def to_uint8(image01: np.ndarray) -> np.ndarray:
    return np.clip(np.rint(np.clip(image01, 0.0, 1.0) * 255.0), 0, 255).astype(np.uint8)


def calibrate_formal_reproduction(device: torch.device) -> dict:
    model, model_meta = build_model(FINAL_CHECKPOINT, device, boundary_enabled=True)
    raw_path = Path(
        str(PROJECT_ROOT / '20260702_100MG_displacement_analysis/raw_inputs/x_0p5um/bmp/frame_0000.bmp')
    )
    formal_path = FORMAL_ROOT / "50x_0p5um" / "frame_0000.bmp"
    image01, _ = read_gray01(raw_path)
    predicted = to_uint8(infer_array(model, image01, device))
    formal = cv2.imread(str(formal_path), cv2.IMREAD_GRAYSCALE)
    if formal is None:
        raise FileNotFoundError(formal_path)
    delta = predicted.astype(np.int16) - formal.astype(np.int16)
    result = {
        **model_meta,
        "raw_image": str(raw_path),
        "formal_output": str(formal_path),
        "mean_absolute_gray_difference": float(np.mean(np.abs(delta))),
        "maximum_absolute_gray_difference": int(np.max(np.abs(delta))),
        "exact_pixel_match_percent": float(np.mean(delta == 0) * 100.0),
        "within_one_gray_level_percent": float(np.mean(np.abs(delta) <= 1) * 100.0),
    }
    del model
    torch.cuda.empty_cache()
    return result


def reconstruct_sequences(
    model: torch.nn.Module,
    device: torch.device,
    condition: str,
    *,
    overwrite: bool,
) -> dict:
    config = json.loads(SEQUENCE_CONFIG.read_text(encoding="utf-8"))["sequences"]
    condition_root = OUTPUT_ROOT / "reconstructions" / condition
    records = []
    started = time.perf_counter()
    for sequence_name, sequence in config.items():
        input_dir = Path(PROJECT_ROOT / sequence["raw_dir"])
        output_dir = condition_root / SEQUENCE_OUTPUT_NAMES[sequence_name]
        output_dir.mkdir(parents=True, exist_ok=True)
        frame_count = int(sequence["frame_count"])
        for index in range(frame_count):
            input_path = input_dir / f"frame_{index:04d}.bmp"
            output_path = output_dir / input_path.name
            if output_path.exists() and not overwrite:
                records.append({"condition": condition, "sequence": sequence_name, "frame": index, "status": "reused"})
                continue
            image01, _ = read_gray01(input_path)
            output = to_uint8(infer_array(model, image01, device))
            if not cv2.imwrite(str(output_path), output):
                raise OSError(output_path)
            records.append({"condition": condition, "sequence": sequence_name, "frame": index, "status": "written"})
        print(f"[{condition}] {sequence_name}: {frame_count} frames ready", flush=True)
    elapsed = time.perf_counter() - started
    return {
        "condition": condition,
        "root": str(condition_root),
        "frame_records": records,
        "frame_count": len(records),
        "elapsed_seconds": elapsed,
    }


def translate(image: np.ndarray, dx: float, dy: float) -> np.ndarray:
    matrix = np.float32([[1.0, 0.0, dx], [0.0, 1.0, dy]])
    return cv2.warpAffine(
        image.astype(np.float32),
        matrix,
        (image.shape[1], image.shape[0]),
        flags=cv2.INTER_CUBIC,
        borderMode=cv2.BORDER_REFLECT_101,
    )


def gradient_magnitude(image: np.ndarray) -> np.ndarray:
    gx = cv2.Sobel(image.astype(np.float32), cv2.CV_32F, 1, 0, ksize=3)
    gy = cv2.Sobel(image.astype(np.float32), cv2.CV_32F, 0, 1, ksize=3)
    return cv2.magnitude(gx, gy)


def shift_metrics(reference: np.ndarray, shifted: np.ndarray, dx: float, dy: float) -> dict:
    aligned = translate(shifted, -dx, -dy)
    margin = max(8, int(round(min(reference.shape) * 0.10)))
    region = np.s_[margin:-margin, margin:-margin]
    ref_crop = reference[region]
    aligned_crop = aligned[region]
    ref_grad = gradient_magnitude(ref_crop)
    aligned_grad = gradient_magnitude(aligned_crop)
    gray_mae = float(np.mean(np.abs(aligned_crop - ref_crop)) * 255.0)
    grad_mae = float(np.mean(np.abs(aligned_grad - ref_grad)))
    grad_scale = float(np.mean(np.abs(ref_grad)) + 1e-9)

    full_ref_grad = gradient_magnitude(reference)
    full_shift_grad = gradient_magnitude(shifted)
    window = cv2.createHanningWindow((reference.shape[1], reference.shape[0]), cv2.CV_32F)
    measured, response = cv2.phaseCorrelate(full_ref_grad, full_shift_grad, window)
    measured_dx, measured_dy = float(measured[0]), float(measured[1])
    return {
        "aligned_gray_mae_levels": gray_mae,
        "aligned_gradient_mae_normalized": grad_mae / grad_scale,
        "measured_dx_px": measured_dx,
        "measured_dy_px": measured_dy,
        "translation_error_px": float(math.hypot(measured_dx - dx, measured_dy - dy)),
        "phase_response": float(response),
        "reference_gradient_mean": float(np.mean(ref_grad)),
    }


def synthetic_shift_diagnostic(
    models: dict[str, torch.nn.Module], device: torch.device
) -> tuple[list[dict], list[dict]]:
    shifts = [
        (-0.75, 0.0),
        (-0.50, 0.0),
        (-0.25, 0.0),
        (0.25, 0.0),
        (0.50, 0.0),
        (0.75, 0.0),
        (0.0, -0.50),
        (0.0, -0.25),
        (0.0, 0.25),
        (0.0, 0.50),
        (-0.50, -0.50),
        (0.50, 0.50),
    ]
    rows: list[dict] = []
    for magnification, path in STATIC_INPUTS.items():
        raw, _ = read_gray01(path)
        method_references = {"Raw": raw}
        for method, model in models.items():
            method_references[method] = infer_array(model, raw, device)
        for dx, dy in shifts:
            shifted_raw = translate(raw, dx, dy)
            method_shifted = {"Raw": shifted_raw}
            for method, model in models.items():
                method_shifted[method] = infer_array(model, shifted_raw, device)
            for method in method_references:
                metrics = shift_metrics(method_references[method], method_shifted[method], dx, dy)
                rows.append(
                    {
                        "magnification": magnification,
                        "method": method,
                        "dx_px": dx,
                        "dy_px": dy,
                        **metrics,
                    }
                )
        print(f"[synthetic] {magnification}: {len(shifts)} shifts complete", flush=True)

    summary = []
    methods = sorted({row["method"] for row in rows})
    for magnification in STATIC_INPUTS:
        for method in methods:
            selected = [r for r in rows if r["magnification"] == magnification and r["method"] == method]
            errors = np.asarray([r["translation_error_px"] for r in selected], dtype=float)
            gray = np.asarray([r["aligned_gray_mae_levels"] for r in selected], dtype=float)
            grad = np.asarray([r["aligned_gradient_mae_normalized"] for r in selected], dtype=float)
            summary.append(
                {
                    "magnification": magnification,
                    "method": method,
                    "shift_count": len(selected),
                    "translation_error_median_px": float(np.median(errors)),
                    "translation_error_p95_px": float(np.percentile(errors, 95)),
                    "aligned_gray_mae_median_levels": float(np.median(gray)),
                    "aligned_gradient_mae_median_normalized": float(np.median(grad)),
                }
            )
    return rows, summary


def write_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        raise ValueError(f"No rows for {path}")
    with path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def plot_synthetic_summary(summary: list[dict], path: Path) -> None:
    methods = ["Raw", "Pre-strengthening model", "MOSR without boundary correction", "Full MOSR"]
    colors = ["#7f7f7f", "#9467bd", "#cc8a00", "#1f6fae"]
    fig, axes = plt.subplots(1, 2, figsize=(8.6, 3.5), dpi=180, constrained_layout=True)
    for axis, magnification in zip(axes, ("50x", "20x")):
        values = []
        for method in methods:
            match = next(
                item for item in summary if item["magnification"] == magnification and item["method"] == method
            )
            values.append(match["translation_error_median_px"])
        axis.bar(np.arange(len(methods)), values, color=colors, width=0.68)
        axis.set_title(f"{magnification} center-nine pillars", fontsize=9)
        axis.set_ylabel("Median translation error (pixel)", fontsize=8)
        axis.set_xticks(np.arange(len(methods)))
        axis.set_xticklabels(["Raw", "Before\nstrengthening", "Without\nboundary correction", "Full MOSR"], fontsize=7)
        axis.tick_params(axis="y", labelsize=7)
        axis.grid(axis="y", color="#d9d9d9", linewidth=0.6)
        axis.set_axisbelow(True)
        axis.spines[["top", "right"]].set_visible(False)
    fig.suptitle("Subpixel translation consistency diagnostic", fontsize=10)
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--calibrate-only", action="store_true")
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    if device.type != "cuda":
        raise RuntimeError("The formal-size reconstruction diagnostic requires CUDA.")

    calibration = calibrate_formal_reproduction(device)
    (OUTPUT_ROOT / "calibration.json").write_text(
        json.dumps(calibration, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(calibration, indent=2), flush=True)
    if calibration["mean_absolute_gray_difference"] > 0.05 or calibration["maximum_absolute_gray_difference"] > 1:
        raise RuntimeError("The local inference path does not reproduce the locked formal output closely enough.")
    if args.calibrate_only:
        return

    full_model, full_meta = build_model(FINAL_CHECKPOINT, device, boundary_enabled=True)
    no_boundary_model, no_boundary_meta = build_model(FINAL_CHECKPOINT, device, boundary_enabled=False)
    base_model, base_meta = build_model(BASE_CHECKPOINT, device, boundary_enabled=True)

    synthetic_rows, synthetic_summary = synthetic_shift_diagnostic(
        {
            "Full MOSR": full_model,
            "MOSR without boundary correction": no_boundary_model,
            "Pre-strengthening model": base_model,
        },
        device,
    )
    write_csv(OUTPUT_ROOT / "tables" / "synthetic_shift_per_case.csv", synthetic_rows)
    write_csv(OUTPUT_ROOT / "tables" / "synthetic_shift_summary.csv", synthetic_summary)
    plot_synthetic_summary(
        synthetic_summary, OUTPUT_ROOT / "figures" / "synthetic_translation_consistency.png"
    )

    no_boundary_run = reconstruct_sequences(
        no_boundary_model,
        device,
        "without_boundary_correction",
        overwrite=args.overwrite,
    )
    base_run = reconstruct_sequences(
        base_model,
        device,
        "pre_strengthening_model",
        overwrite=args.overwrite,
    )

    metadata = {
        "purpose": "Position-stability diagnostic only; not inserted into the thesis.",
        "calibration": calibration,
        "conditions": {
            "full_mosr": full_meta,
            "without_boundary_correction": no_boundary_meta,
            "pre_strengthening_model": base_meta,
        },
        "reconstruction_runs": [no_boundary_run, base_run],
        "selection_policy_for_later_summary": (
            "Use only Raw-eligible pairs; rank by Raw measurements only; compare all methods on common-valid pairs."
        ),
    }
    (OUTPUT_ROOT / "run_metadata.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"Results: {OUTPUT_ROOT}")


if __name__ == "__main__":
    main()

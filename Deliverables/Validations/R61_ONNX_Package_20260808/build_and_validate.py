from __future__ import annotations

import hashlib
import importlib.util
import json
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import cv2
import numpy as np
import onnx
import onnxruntime as ort
import torch
from scipy import fft
PROJECT_ROOT = Path(__file__).resolve().parents[3]


PROJECT = Path(str(PROJECT_ROOT))
PACKAGE = PROJECT / "Deliverables" / "Company_Packages" / "MOSR_R61_ONNX"
CHECKPOINT = (
    PROJECT
    / "LabSystem_MOSR"
    / "Traing_Progress"
    / "training_progress_LAB_GESR_v1_v5_ST0p8_SWP_r61_motion_texture_stepguard_v16_dualgate_boundary_focus_full_e8_20260623_20260623_200020"
    / "weights"
    / "best_tradeoff.pth.tar"
)
MODEL_SOURCE = PROJECT / "Model" / "GeoEdgeAlignSR_v1_ModelA_v5_NoCoord.py"
REFERENCE_INPUT = (
    Path(str(PROJECT_ROOT / 'Shared_Sources/NTU_Originals/Pitch1um_Y_100/external_gmf_r61_v16_psfoff_20260627'))
    / "00_raw_input"
    / "bmp"
    / "VisionTop_20251029182653732.bmp"
)
REFERENCE_OUTPUT = (
    Path(str(PROJECT_ROOT / 'Shared_Sources/NTU_Originals/Pitch1um_Y_100/external_gmf_r61_v16_psfoff_20260627'))
    / "01_r61_v16_best_tradeoff_psfoff"
    / "bmp"
    / REFERENCE_INPUT.name
)
EXAMPLE_SOURCE = PROJECT / "Deliverables" / "Company_Packages" / "MOSR_ONNX" / "example" / "input.bmp"
VALIDATION_DIR = Path(__file__).resolve().parent
ONNX_PATH = PACKAGE / "model.onnx"
OPTICS_PATH = PACKAGE / "optics.npz"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_gray(path: Path) -> np.ndarray:
    encoded = np.fromfile(path, dtype=np.uint8)
    image = cv2.imdecode(encoded, cv2.IMREAD_GRAYSCALE)
    if image is None:
        raise OSError(path)
    return image


def write_bmp(path: Path, image: np.ndarray) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    ok, encoded = cv2.imencode(".bmp", np.asarray(image, dtype=np.uint8))
    if not ok:
        raise OSError(path)
    encoded.tofile(path)


def pad_to_multiple(image: np.ndarray, multiple: int = 64) -> tuple[np.ndarray, int, int]:
    height, width = image.shape
    pad_bottom = (-height) % multiple
    pad_right = (-width) % multiple
    padded = cv2.copyMakeBorder(
        image,
        0,
        pad_bottom,
        0,
        pad_right,
        cv2.BORDER_REFLECT_101,
    )
    return padded, height, width


def load_model_class():
    spec = importlib.util.spec_from_file_location("r61_model_source", MODEL_SOURCE)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load {MODEL_SOURCE}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.GeoEdgeAlignSR_v1_v5_NoCoord


def build_psf_off_model() -> tuple[torch.nn.Module, dict[str, object]]:
    checkpoint = torch.load(CHECKPOINT, map_location="cpu")
    state = checkpoint["state_dict"]
    model_config = checkpoint.get("model_config", {}).get("boundary_residual_adapter", {})
    boundary_weight = state["boundary_adapter.body.0.weight"]
    model_class = load_model_class()
    model = model_class(
        in_ch=int(state["e1.0.conv.weight"].shape[1]),
        base=int(state["e1.0.conv.weight"].shape[0]),
        use_physics_layer=False,
        use_sigmoid_output=True,
        use_upsample_conv=True,
        use_band_limit=False,
        weak_psf_enable=False,
        learnable_blur=False,
        use_bottleneck_se=False,
        boundary_residual_adapter_enable=True,
        boundary_residual_adapter_hidden=int(boundary_weight.shape[0]),
        boundary_residual_adapter_max=float(state["boundary_adapter.max_residual"].item()),
        boundary_residual_adapter_gate_bias=float(state["boundary_adapter.gate.bias"].item()),
        boundary_residual_adapter_delta_bias="boundary_adapter.delta.bias" in state,
        boundary_residual_adapter_zero_mean=bool(model_config.get("zero_mean", False)),
        boundary_residual_adapter_edge_gate=bool(model_config.get("edge_gate", False)),
        boundary_residual_adapter_polarity_split=bool(model_config.get("polarity_split", False)),
        boundary_residual_adapter_orientation_inputs=bool(model_config.get("orientation_inputs", True)),
        raw_anchor_output_mode="none",
        quality_gate_enable=False,
    )
    load_result = model.load_state_dict(state, strict=False)
    unexpected = sorted(load_result.unexpected_keys)
    missing = sorted(load_result.missing_keys)
    allowed_prefixes = ("physics_layer.", "weak_psf_block.")
    disallowed = [key for key in unexpected if not key.startswith(allowed_prefixes)]
    if missing or disallowed:
        raise RuntimeError({"missing": missing, "unexpected": unexpected})
    model.eval()
    details = {
        "checkpoint_epoch": int(checkpoint["epoch"]),
        "state_key": "state_dict",
        "ignored_psf_state_keys": unexpected,
        "missing_keys": missing,
    }
    return model, details


def run_torch(model: torch.nn.Module, image: np.ndarray) -> np.ndarray:
    padded, height, width = pad_to_multiple(image)
    tensor = torch.from_numpy(padded.astype(np.float32) / np.float32(255.0))[None, None]
    with torch.inference_mode():
        output = model(tensor).clamp(0.0, 1.0)[0, 0, :height, :width].numpy()
    return output


def create_session() -> ort.InferenceSession:
    options = ort.SessionOptions()
    options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
    return ort.InferenceSession(str(ONNX_PATH), sess_options=options, providers=["CPUExecutionProvider"])


def optical_preprocess(image: np.ndarray) -> np.ndarray:
    optics = np.load(OPTICS_PATH)
    psf = optics["psf"].astype(np.float32)[None, None]
    reg = np.float32(optics["reg"])
    alpha = np.float32(optics["alpha"])
    _, _, height, width = image.shape
    _, _, psf_height, psf_width = psf.shape
    pad_height = height - psf_height
    pad_width = width - psf_width
    psf = np.pad(
        psf,
        (
            (0, 0),
            (0, 0),
            (pad_height // 2, pad_height - pad_height // 2),
            (pad_width // 2, pad_width - pad_width // 2),
        ),
        mode="constant",
    )
    psf_frequency = fft.rfft2(psf, axes=(-2, -1))
    image_frequency = fft.rfft2(image.astype(np.float32), axes=(-2, -1))
    denominator = np.conj(psf_frequency) * psf_frequency + reg + np.float32(1e-6)
    inverse_filter = np.conj(psf_frequency) / denominator
    restored = fft.irfft2(
        image_frequency * inverse_filter,
        s=(height, width),
        axes=(-2, -1),
    ).astype(np.float32)
    restored = np.clip(restored, -100.0, 100.0) + np.float32(1e-6)
    return image.astype(np.float32) + alpha * (restored - image.astype(np.float32))


def run_onnx(session: ort.InferenceSession, image: np.ndarray) -> np.ndarray:
    padded, height, width = pad_to_multiple(image)
    tensor = padded.astype(np.float32)[None, None] / np.float32(255.0)
    tensor = optical_preprocess(tensor)
    output = session.run(["output"], {"image": tensor})[0]
    return np.clip(output[0, 0, :height, :width], 0.0, 1.0)


def image_metrics(actual: np.ndarray, expected: np.ndarray) -> dict[str, float]:
    actual_f = actual.astype(np.float64)
    expected_f = expected.astype(np.float64)
    difference = np.abs(actual_f - expected_f)
    correlation = float(np.corrcoef(actual_f.ravel(), expected_f.ravel())[0, 1])
    return {
        "mae": float(difference.mean()),
        "p95_absolute_difference": float(np.percentile(difference, 95)),
        "max_absolute_difference": float(difference.max()),
        "exact_pixel_fraction": float(np.mean(difference == 0)),
        "correlation": correlation,
    }


def main() -> int:
    required = [CHECKPOINT, MODEL_SOURCE, REFERENCE_INPUT, REFERENCE_OUTPUT, EXAMPLE_SOURCE]
    missing = [str(path) for path in required if not path.is_file()]
    if missing:
        raise FileNotFoundError(missing)
    PACKAGE.mkdir(parents=True, exist_ok=True)
    (PACKAGE / "example").mkdir(parents=True, exist_ok=True)
    VALIDATION_DIR.mkdir(parents=True, exist_ok=True)

    model, load_details = build_psf_off_model()
    checkpoint = torch.load(CHECKPOINT, map_location="cpu")
    source_state = checkpoint["state_dict"]
    np.savez_compressed(
        OPTICS_PATH,
        psf=source_state["physics_layer.PSF_mean"].detach().cpu().numpy()[0, 0].astype(np.float32),
        reg=np.float32(30.0),
        alpha=np.float32(0.05),
    )
    dummy = torch.linspace(0.0, 1.0, 256 * 256, dtype=torch.float32).reshape(1, 1, 256, 256)
    torch.onnx.export(
        model,
        dummy,
        ONNX_PATH,
        input_names=["image"],
        output_names=["output"],
        dynamic_axes={
            "image": {0: "batch", 2: "height", 3: "width"},
            "output": {0: "batch", 2: "height", 3: "width"},
        },
        opset_version=17,
        do_constant_folding=True,
    )
    onnx_model = onnx.load(ONNX_PATH)
    onnx.checker.check_model(onnx_model)
    session = create_session()

    example_input = PACKAGE / "example" / "input.bmp"
    shutil.copy2(EXAMPLE_SOURCE, example_input)
    example_image = read_gray(example_input)
    padded_example, example_height, example_width = pad_to_multiple(example_image)
    example_tensor = padded_example.astype(np.float32)[None, None] / np.float32(255.0)
    example_tensor = optical_preprocess(example_tensor)
    with torch.inference_mode():
        torch_float = model(torch.from_numpy(example_tensor)).clamp(0.0, 1.0)[
            0, 0, :example_height, :example_width
        ].numpy()
    onnx_float = run_onnx(session, example_image)
    float_difference = np.abs(torch_float - onnx_float)
    torch_u8 = np.clip(np.rint(torch_float * 255.0), 0, 255).astype(np.uint8)
    onnx_u8 = np.clip(np.rint(onnx_float * 255.0), 0, 255).astype(np.uint8)
    small_parity = {
        "shape": list(example_image.shape),
        "max_float_difference": float(float_difference.max()),
        "mean_float_difference": float(float_difference.mean()),
        "max_pixel_difference": int(np.abs(torch_u8.astype(np.int16) - onnx_u8.astype(np.int16)).max()),
        "exact_pixel_fraction": float(np.mean(torch_u8 == onnx_u8)),
    }

    reference_input = read_gray(REFERENCE_INPUT)
    reference_expected = read_gray(REFERENCE_OUTPUT)
    reference_float = run_onnx(session, reference_input)
    reference_actual = np.clip(np.rint(reference_float * 255.0), 0, 255).astype(np.uint8)
    reference_reconstruction = VALIDATION_DIR / "r61_onnx_reference_reconstruction.bmp"
    write_bmp(reference_reconstruction, reference_actual)
    reference_metrics = image_metrics(reference_actual, reference_expected)

    example_output_dir = VALIDATION_DIR / "runner_example_output"
    if example_output_dir.exists():
        shutil.rmtree(example_output_dir)
    subprocess.run(
        [
            sys.executable,
            str(PACKAGE / "run.py"),
            "--input",
            str(example_input),
            "--output",
            str(example_output_dir),
            "--cpu",
        ],
        check=True,
    )
    runner_output = example_output_dir / "input.bmp"
    runner_image = read_gray(runner_output)
    runner_exact = bool(np.array_equal(runner_image, onnx_u8))
    if not runner_exact:
        raise RuntimeError("Packaged runner output differs from direct ONNX output")
    shutil.copy2(runner_output, PACKAGE / "example" / "output.bmp")

    pass_small = small_parity["max_pixel_difference"] <= 1
    pass_reference = (
        reference_metrics["max_absolute_difference"] <= 1.0
        and reference_metrics["mae"] <= 0.5
        and reference_metrics["correlation"] >= 0.9998
    )
    passed = bool(pass_small and pass_reference and runner_exact)
    report = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "passed": passed,
        "source": {
            "checkpoint": str(CHECKPOINT),
            "checkpoint_sha256": sha256(CHECKPOINT),
            "checkpoint_epoch": load_details["checkpoint_epoch"],
            "state_key": load_details["state_key"],
            "inference_mode": "R61 v16 locked real-sample mode",
            "weak_psf": "disabled",
            "physical_psf_effective_alpha": 0.05,
            "physical_psf_reg": 30.0,
            "model_source": str(MODEL_SOURCE),
            "model_source_sha256": sha256(MODEL_SOURCE),
        },
        "onnx": {
            "path": str(ONNX_PATH),
            "opset": 17,
            "structure_check": "pass",
            "dynamic_height_width": True,
        },
        "small_image_parity": small_parity,
        "locked_reference": {
            "input": str(REFERENCE_INPUT),
            "expected_output": str(REFERENCE_OUTPUT),
            "actual_output": str(reference_reconstruction),
            "input_shape": list(reference_input.shape),
            "padding_alignment": 64,
            **reference_metrics,
        },
        "packaged_runner": {
            "example_execution": "pass",
            "direct_output_exact_match": runner_exact,
            "default_mode": "full image",
        },
        "load_details": load_details,
    }
    (VALIDATION_DIR / "validation_report.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    if not passed:
        raise RuntimeError(json.dumps(report, indent=2, ensure_ascii=False))
    package_files = [
        "model.onnx",
        "optics.npz",
        "run.py",
        "requirements.txt",
        "README.md",
        "example/input.bmp",
        "example/output.bmp",
    ]
    manifest = {
        "name": "MOSR R61",
        "version": "1.0",
        "format": "ONNX",
        "opset": 17,
        "source_checkpoint_sha256": sha256(CHECKPOINT),
        "mode": "locked measurement reconstruction",
        "input": {
            "image": "8-bit grayscale or color",
            "minimum_size": [101, 101],
        },
        "output": {
            "image": "8-bit grayscale BMP",
            "same_size_as_input": True,
        },
        "defaults": {
            "processing": "full image",
            "tile_size": 0,
        },
        "validation": {
            "onnx_structure": "pass",
            "example_execution": "pass",
            "cpu_reference_max_pixel_difference": int(reference_metrics["max_absolute_difference"]),
            "cpu_reference_mean_pixel_difference": reference_metrics["mae"],
            "cpu_reference_correlation": reference_metrics["correlation"],
            "tested_full_image_size": list(reference_input.shape),
        },
        "files": {
            relative: {
                "bytes": (PACKAGE / relative).stat().st_size,
                "sha256": sha256(PACKAGE / relative),
            }
            for relative in package_files
        },
    }
    (PACKAGE / "manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

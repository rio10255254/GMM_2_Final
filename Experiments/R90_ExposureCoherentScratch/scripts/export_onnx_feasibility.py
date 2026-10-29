"""Export and parity-test the frozen E45 candidate without creating a delivery ZIP."""
from __future__ import annotations

import hashlib
import importlib.util
import json
import math
from pathlib import Path
import sys
import time
from typing import Any

import cv2
import numpy as np
import onnx
import onnxruntime as ort
import torch
PROJECT_ROOT = Path(__file__).resolve().parents[3]


ROOT = Path(__file__).resolve().parents[1]
SELECTION = ROOT / "config" / "early_stop_confirmation.json"
INFERENCE = ROOT / "inference" / "reconstruct.py"
OUTPUT = ROOT / "results" / "early_stop_confirmation" / "onnx_feasibility"
MODEL_PATH = OUTPUT / "model.onnx"
REPORT_PATH = OUTPUT / "report.json"
CORE = 512
HALO = 192
TILE = CORE + 2 * HALO
SOURCES = {
    "5x": Path(str(PROJECT_ROOT / '20260704_20x_5x_analysis/raw_inputs/5x_0p5um/bmp/frame_0024.bmp')),
    "20x": Path(str(PROJECT_ROOT / '20260704_20x_5x_analysis/raw_inputs/20x_0p5um/bmp/frame_0024.bmp')),
    "50x": Path(str(PROJECT_ROOT / '20260702_100MG_displacement_analysis/raw_inputs/x_1um/bmp/frame_0024.bmp')),
    "sem18": ROOT / "results" / "full_validation_epoch055" / "sem_acm" / "locked_optical_inputs" / "18.bmp",
    "junhua_example": Path(str(PROJECT_ROOT / 'Deliverables/MOSR_R61_ONNX/example/input.bmp')),
}


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_gray(path: Path) -> np.ndarray:
    image = cv2.imdecode(np.fromfile(path, dtype=np.uint8), cv2.IMREAD_GRAYSCALE)
    if image is None:
        raise RuntimeError(path)
    return image


def metrics(reference: np.ndarray, candidate: np.ndarray) -> dict[str, float]:
    difference = np.abs(reference.astype(np.float64) - candidate.astype(np.float64))
    flat_a = reference.astype(np.float64).ravel()
    flat_b = candidate.astype(np.float64).ravel()
    correlation = float(np.corrcoef(flat_a, flat_b)[0, 1]) if flat_a.std() > 0 and flat_b.std() > 0 else 1.0
    return {
        "mean_absolute_difference": float(difference.mean()),
        "p99_absolute_difference": float(np.percentile(difference, 99)),
        "maximum_absolute_difference": float(difference.max()),
        "correlation": correlation,
    }


def first_canonical_tile(inference, image: np.ndarray) -> np.ndarray:
    tensor = torch.from_numpy(np.ascontiguousarray(image)).float().div(255.0)[None, None]
    canvas, _ = inference.canonical_canvas(tensor, CORE, HALO)
    tile = canvas[..., :TILE, :TILE]
    if tuple(tile.shape) != (1, 1, TILE, TILE):
        raise RuntimeError(f"Unexpected tile shape {tuple(tile.shape)}")
    return tile.numpy().astype(np.float32)


def reconstruct_onnx(inference, session: ort.InferenceSession, image: np.ndarray) -> np.ndarray:
    tensor = torch.from_numpy(np.ascontiguousarray(image)).float().div(255.0)[None, None]
    canvas, (height, width, grid_h, grid_w) = inference.canonical_canvas(tensor, CORE, HALO)
    canvas_np = canvas.numpy().astype(np.float32)
    output = np.empty((grid_h, grid_w), dtype=np.float32)
    for y in range(0, grid_h, CORE):
        for x in range(0, grid_w, CORE):
            tile = canvas_np[..., y:y + TILE, x:x + TILE]
            prediction = session.run(["output"], {"image": tile})[0]
            output[y:y + CORE, x:x + CORE] = prediction[0, 0, HALO:HALO + CORE, HALO:HALO + CORE]
    return output[:height, :width]


def main() -> int:
    selection = json.loads(SELECTION.read_text(encoding="utf-8"))
    checkpoint = Path(PROJECT_ROOT / selection["checkpoint"])
    if sha256_file(checkpoint) != selection["checkpoint_sha256"]:
        raise RuntimeError("Checkpoint hash mismatch")
    for label, source in SOURCES.items():
        if not source.is_file():
            raise FileNotFoundError(f"{label}: {source}")
    inference = load_module("r90_onnx_feasibility_inference", INFERENCE)
    device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")
    model, payload = inference.load_model(checkpoint, device)
    if int(payload["epoch"]) != 45:
        raise RuntimeError("Expected epoch 45")
    model = model.float().eval()
    class OnnxWrapper(torch.nn.Module):
        def __init__(self, inner: torch.nn.Module):
            super().__init__()
            self.inner = inner

        def forward(self, image: torch.Tensor) -> torch.Tensor:
            return self.inner(image)

    export_model = OnnxWrapper(model).eval()
    OUTPUT.mkdir(parents=True, exist_ok=True)

    example = torch.zeros((1, 1, TILE, TILE), dtype=torch.float32, device=device)
    started = time.perf_counter()
    torch.onnx.export(
        export_model,
        example,
        MODEL_PATH,
        export_params=True,
        opset_version=17,
        do_constant_folding=True,
        input_names=["image"],
        output_names=["output"],
        dynamic_axes=None,
    )
    export_seconds = time.perf_counter() - started
    exported = onnx.load(str(MODEL_PATH))
    onnx.checker.check_model(exported)
    input_shape = [dimension.dim_value for dimension in exported.graph.input[0].type.tensor_type.shape.dim]
    output_shape = [dimension.dim_value for dimension in exported.graph.output[0].type.tensor_type.shape.dim]
    if input_shape != [1, 1, TILE, TILE]:
        raise RuntimeError(f"Unexpected ONNX input contract: {input_shape}")

    options = ort.SessionOptions()
    options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
    session = ort.InferenceSession(str(MODEL_PATH), sess_options=options, providers=["CPUExecutionProvider"])
    runtime_probe = session.run(["output"], {"image": np.zeros((1, 1, TILE, TILE), dtype=np.float32)})[0]
    runtime_output_shape = list(runtime_probe.shape)
    if runtime_output_shape != [1, 1, TILE, TILE]:
        raise RuntimeError(f"Unexpected ONNX runtime output: {runtime_output_shape}")
    tile_rows: dict[str, Any] = {}
    with torch.inference_mode():
        generator = np.random.default_rng(450041)
        test_tiles = {"synthetic": generator.random((1, 1, TILE, TILE), dtype=np.float32)}
        test_tiles.update({label: first_canonical_tile(inference, read_gray(path)) for label, path in SOURCES.items()})
        for label, tile in test_tiles.items():
            reference = model(torch.from_numpy(tile).to(device)).float().cpu().numpy()
            candidate = session.run(["output"], {"image": tile})[0]
            float_result = metrics(reference, candidate)
            ref_u8 = np.rint(np.clip(reference[0, 0, HALO:HALO + CORE, HALO:HALO + CORE], 0, 1) * 255).astype(np.uint8)
            onnx_u8 = np.rint(np.clip(candidate[0, 0, HALO:HALO + CORE, HALO:HALO + CORE], 0, 1) * 255).astype(np.uint8)
            tile_rows[label] = {
                "source": str(SOURCES[label]) if label in SOURCES else "deterministic synthetic tile",
                "float": float_result,
                "uint8_center_core": metrics(ref_u8, onnx_u8),
            }

    end_to_end: dict[str, Any] = {}
    for label in ("sem18", "junhua_example"):
        image = read_gray(SOURCES[label])
        onnx_result = reconstruct_onnx(inference, session, image)
        tensor = torch.from_numpy(np.ascontiguousarray(image)).to(device=device, dtype=torch.float32).div(255.0)[None, None]
        with torch.inference_mode():
            torch_result = inference.reconstruct_tensor(model, tensor, core_size=CORE, halo=HALO, tile_batch=1, amp=False)[0, 0].cpu().numpy()
            deployed_bf16 = inference.reconstruct_tensor(model, tensor, core_size=CORE, halo=HALO, tile_batch=1, amp=device.type == "cuda")[0, 0].cpu().numpy()
        torch_u8 = np.rint(np.clip(torch_result, 0, 1) * 255).astype(np.uint8)
        onnx_u8 = np.rint(np.clip(onnx_result, 0, 1) * 255).astype(np.uint8)
        deployed_u8 = np.rint(np.clip(deployed_bf16, 0, 1) * 255).astype(np.uint8)
        end_to_end[label] = {
            "source": str(SOURCES[label]),
            "source_sha256": sha256_file(SOURCES[label]),
            "shape": list(image.shape),
            "onnx_vs_torch_float32_uint8": metrics(torch_u8, onnx_u8),
            "onnx_vs_current_bf16_deployment_uint8": metrics(deployed_u8, onnx_u8),
        }
        cv2.imencode(".bmp", onnx_u8)[1].tofile(OUTPUT / f"{label}_onnx.bmp")

    max_float = max(row["float"]["maximum_absolute_difference"] for row in tile_rows.values())
    max_tile_u8 = max(row["uint8_center_core"]["maximum_absolute_difference"] for row in tile_rows.values())
    max_e2e_fp32_u8 = max(row["onnx_vs_torch_float32_uint8"]["maximum_absolute_difference"] for row in end_to_end.values())
    max_e2e_deployed_u8 = max(row["onnx_vs_current_bf16_deployment_uint8"]["maximum_absolute_difference"] for row in end_to_end.values())
    max_e2e_deployed_mean = max(row["onnx_vs_current_bf16_deployment_uint8"]["mean_absolute_difference"] for row in end_to_end.values())
    fp32_parity_pass = bool(max_e2e_fp32_u8 <= 1 and max_tile_u8 <= 1)
    current_deployment_close = bool(max_e2e_deployed_u8 <= 2 and max_e2e_deployed_mean <= 0.25)
    technical_pass = fp32_parity_pass and current_deployment_close
    report = {
        "status": "technical_pass_delivery_blocked" if technical_pass else "technical_fail",
        "role": "technical ONNX feasibility only; not an enterprise delivery approval",
        "checkpoint_epoch": 45,
        "checkpoint_sha256": selection["checkpoint_sha256"],
        "onnx": {
            "path": str(MODEL_PATH),
            "sha256": sha256_file(MODEL_PATH),
            "bytes": MODEL_PATH.stat().st_size,
            "opset": 17,
            "input_shape": input_shape,
            "declared_output_shape": output_shape,
            "runtime_output_shape": runtime_output_shape,
            "core": CORE,
            "halo": HALO,
            "export_seconds": export_seconds,
            "checker": "pass",
            "runtime_provider": session.get_providers()[0],
        },
        "tile_parity": tile_rows,
        "end_to_end_parity": end_to_end,
        "maximum_float_difference": max_float,
        "maximum_tile_uint8_difference": max_tile_u8,
        "maximum_end_to_end_float32_uint8_difference": max_e2e_fp32_u8,
        "maximum_end_to_end_current_deployment_uint8_difference": max_e2e_deployed_u8,
        "maximum_end_to_end_current_deployment_mean_difference": max_e2e_deployed_mean,
        "fp32_parity_pass": fp32_parity_pass,
        "current_bf16_deployment_close": current_deployment_close,
        "scientific_delivery_blocker": "Exposure 18 SEM edge expansion remains unresolved even if ONNX parity passes.",
    }
    REPORT_PATH.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False))
    return 0 if technical_pass else 1


if __name__ == "__main__":
    raise SystemExit(main())

"""Validate ONNX E45 against the measured BF16 SEM contour outputs."""
from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import time

import cv2
import numpy as np
import onnxruntime as ort


ROOT = Path(__file__).resolve().parents[1]
MODEL = ROOT / "results" / "early_stop_confirmation" / "onnx_feasibility" / "model.onnx"
MODEL_REPORT = ROOT / "results" / "early_stop_confirmation" / "onnx_feasibility" / "report.json"
INFERENCE = ROOT / "inference" / "reconstruct.py"
RAW = ROOT / "results" / "full_validation_epoch055" / "sem_acm" / "locked_optical_inputs"
OUTPUT = ROOT / "results" / "early_stop_confirmation" / "onnx_sem_parity"
RECON = OUTPUT / "stage_root" / "ONNX" / "reconstruction"
CORE, HALO = 512, 192
TILE = CORE + 2 * HALO


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


def write_bmp(path: Path, image: np.ndarray) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    success, encoded = cv2.imencode(".bmp", image)
    if not success:
        raise RuntimeError(path)
    encoded.tofile(path)


def reconstruct(inference, session: ort.InferenceSession, image: np.ndarray) -> np.ndarray:
    import torch
    tensor = torch.from_numpy(np.ascontiguousarray(image)).float().div(255.0)[None, None]
    canvas, (height, width, grid_h, grid_w) = inference.canonical_canvas(tensor, CORE, HALO)
    canvas_np = canvas.numpy().astype(np.float32)
    output = np.empty((grid_h, grid_w), dtype=np.float32)
    for y in range(0, grid_h, CORE):
        for x in range(0, grid_w, CORE):
            tile = canvas_np[..., y:y + TILE, x:x + TILE]
            prediction = session.run(["output"], {"image": tile})[0]
            output[y:y + CORE, x:x + CORE] = prediction[0, 0, HALO:HALO + CORE, HALO:HALO + CORE]
    return np.rint(np.clip(output[:height, :width], 0, 1) * 255).astype(np.uint8)


def main() -> int:
    report = json.loads(MODEL_REPORT.read_text(encoding="utf-8"))
    if sha256_file(MODEL) != report["onnx"]["sha256"]:
        raise RuntimeError("ONNX hash mismatch")
    inference = load_module("r90_onnx_sem_inference", INFERENCE)
    options = ort.SessionOptions()
    options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
    session = ort.InferenceSession(str(MODEL), sess_options=options, providers=["CPUExecutionProvider"])
    records = []
    started = time.perf_counter()
    for exposure in range(13, 25):
        source = RAW / f"{exposure}.bmp"
        output = RECON / f"{exposure}.bmp"
        reconstruction = reconstruct(inference, session, read_gray(source))
        write_bmp(output, reconstruction)
        records.append({
            "exposure": exposure,
            "source": str(source),
            "source_sha256": sha256_file(source),
            "output": str(output),
            "output_sha256": sha256_file(output),
        })
        print(json.dumps({"completed": exposure - 12, "total": 12, "exposure": exposure}), flush=True)
    payload = {
        "status": "reconstruction_complete",
        "model_sha256": sha256_file(MODEL),
        "provider": session.get_providers()[0],
        "seconds": time.perf_counter() - started,
        "records": records,
        "next_step": "Run frozen ACM extraction with stage label ONNX and compare against E045.",
    }
    (OUTPUT / "reconstruction_manifest.json").write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

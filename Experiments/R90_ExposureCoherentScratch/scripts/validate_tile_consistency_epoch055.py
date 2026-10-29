"""Check full-canvas and tiled parity for the frozen R90 E55 checkpoint."""
from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
import time
from pathlib import Path

import cv2
import numpy as np
import torch
PROJECT_ROOT = Path(__file__).resolve().parents[3]


ROOT = Path(__file__).resolve().parents[1]
PROTOCOL_PATH = ROOT / "reports" / "full_validation_epoch055" / "validation_protocol.json"
R78_CONFIG = Path(str(PROJECT_ROOT / 'Experiments/R78_R75v2_BroadRealMicroscopeGeneralization/config/experiment.json'))
OUTPUT = ROOT / "results" / "full_validation_epoch055" / "tile_consistency.json"
INFERENCE_PATH = ROOT / "inference" / "reconstruct.py"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def read_gray(path: Path) -> np.ndarray:
    image = cv2.imdecode(np.fromfile(path, dtype=np.uint8), cv2.IMREAD_GRAYSCALE)
    if image is None:
        raise RuntimeError(path)
    return image


def seam_mask(height: int, width: int, core: int, radius: int = 2) -> np.ndarray:
    mask = np.zeros((height, width), dtype=bool)
    for y in range(core, height, core):
        mask[max(0, y - radius):min(height, y + radius + 1), :] = True
    for x in range(core, width, core):
        mask[:, max(0, x - radius):min(width, x + radius + 1)] = True
    return mask


def main() -> int:
    protocol = json.loads(PROTOCOL_PATH.read_text(encoding="utf-8"))
    config = json.loads(R78_CONFIG.read_text(encoding="utf-8"))
    record = protocol["comparison_models"]["R90E55"]
    checkpoint = Path(record["checkpoint"])
    if sha256_file(checkpoint) != record["checkpoint_sha256"]:
        raise RuntimeError("Checkpoint hash mismatch")
    inference = load_module("r90_tile_validation_inference", INFERENCE_PATH)
    device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")
    model, payload = inference.load_model(checkpoint, device)
    if int(payload.get("epoch", -1)) != 55:
        raise RuntimeError("Expected epoch 55")
    source_paths = {
        "5x_0p5um": sorted(Path(PROJECT_ROOT / config["sequences"]["5x_0p5um"]["raw_dir"]).glob("frame_*.bmp"))[24],
        "50x_1um": sorted(Path(PROJECT_ROOT / config["sequences"]["50x_1um"]["raw_dir"]).glob("frame_*.bmp"))[24],
    }
    report = {
        "status": "complete", "checkpoint_sha256": record["checkpoint_sha256"],
        "checkpoint_epoch": 55, "halo": 192, "images": {},
    }
    started = time.perf_counter()
    if device.type == "cuda":
        torch.cuda.reset_peak_memory_stats(device)
    for label, path in source_paths.items():
        raw = read_gray(path)
        tensor = inference.image_tensor(raw, device)
        outputs: dict[int, np.ndarray] = {}
        schemes = {}
        for core in (256, 384, 512):
            full = inference.reconstruct_full_reference(model, tensor, core_size=core, halo=192, amp=device.type == "cuda")
            tiled = inference.reconstruct_tensor(model, tensor, core_size=core, halo=192, tile_batch=1, amp=device.type == "cuda")
            difference = (tiled - full).abs()[0, 0].float().cpu().numpy() * 255.0
            output = tiled[0, 0].float().cpu().numpy()
            outputs[core] = output
            seam = seam_mask(*raw.shape, core)
            schemes[str(core)] = {
                "mean_abs_gray_tiled_vs_full": float(difference.mean()),
                "p99_abs_gray_tiled_vs_full": float(np.percentile(difference, 99)),
                "max_abs_gray_tiled_vs_full": float(difference.max()),
                "mean_abs_gray_on_seam_band": float(difference[seam].mean()) if seam.any() else 0.0,
                "mean_abs_gray_off_seam_band": float(difference[~seam].mean()),
                "non_identity_mean_abs_gray": float(np.mean(np.abs(output - raw.astype(np.float32) / 255.0)) * 255.0),
            }
            del full, tiled
        cross = {}
        reference = outputs[512]
        for core in (256, 384):
            difference = np.abs(outputs[core] - reference) * 255.0
            cross[f"core_{core}_vs_512"] = {
                "mean_abs_gray": float(difference.mean()),
                "p99_abs_gray": float(np.percentile(difference, 99)),
                "max_abs_gray": float(difference.max()),
            }
        report["images"][label] = {
            "source": str(path), "source_sha256": sha256_file(path), "shape": list(raw.shape),
            "schemes": schemes, "cross_scheme": cross,
        }
    report["seconds"] = time.perf_counter() - started
    report["gpu_peak_gib"] = torch.cuda.max_memory_allocated(device) / 2**30 if device.type == "cuda" else 0.0
    all_full = [row["max_abs_gray_tiled_vs_full"] for image in report["images"].values() for row in image["schemes"].values()]
    all_cross = [row["max_abs_gray"] for image in report["images"].values() for row in image["cross_scheme"].values()]
    report["exactness"] = {
        "maximum_tiled_vs_full_gray": float(max(all_full)),
        "maximum_cross_scheme_gray": float(max(all_cross)),
        "visually_lossless_below_0p1_gray": bool(max(all_full + all_cross) < 0.1),
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

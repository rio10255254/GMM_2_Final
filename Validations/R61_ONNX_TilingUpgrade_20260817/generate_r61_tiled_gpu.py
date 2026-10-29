from __future__ import annotations

import argparse
import importlib.util
import time
from pathlib import Path

import cv2
import numpy as np
import torch
import torch.nn.functional as F
PROJECT_ROOT = Path(__file__).resolve().parents[2]


PROJECT = Path(str(PROJECT_ROOT))
PACKAGE = PROJECT / "Deliverables" / "MOSR_R61_ONNX"
CHECKPOINT = (
    PROJECT
    / "Thesis_MOSR_Evidence"
    / "LabSystem_MOSR"
    / "Traing_Progress"
    / "training_progress_LAB_GESR_v1_v5_ST0p8_SWP_r61_motion_texture_stepguard_v16_dualgate_boundary_focus_full_e8_20260623_20260623_200020"
    / "weights"
    / "best_tradeoff.pth.tar"
)
MODEL_SOURCE = PROJECT / "Model" / "GeoEdgeAlignSR_v1_ModelA_v5_NoCoord.py"
ALIGNMENT = 64
HALO = 192
CORE = 640


def load_builder():
    path = PROJECT / "Validations" / "R61_ONNX_Package_20260808" / "build_and_validate.py"
    spec = importlib.util.spec_from_file_location("r61_onnx_builder", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def read_gray(path: Path) -> np.ndarray:
    encoded = np.fromfile(path, dtype=np.uint8)
    image = cv2.imdecode(encoded, cv2.IMREAD_GRAYSCALE)
    if image is None or image.dtype != np.uint8:
        raise OSError(path)
    return image


def write_bmp(path: Path, image: np.ndarray) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    ok, encoded = cv2.imencode(".bmp", image.astype(np.uint8))
    if not ok:
        raise OSError(path)
    encoded.tofile(path)


def load_model(device: torch.device) -> torch.nn.Module:
    builder = load_builder()
    model, _ = builder.build_psf_off_model()
    model.to(device).eval()
    return model


def make_psf(device: torch.device, height: int, width: int) -> torch.Tensor:
    optics = np.load(PACKAGE / "optics.npz")
    psf = torch.from_numpy(optics["psf"].astype(np.float32))[None, None].to(device)
    pad_height = height - int(psf.shape[-2])
    pad_width = width - int(psf.shape[-1])
    if pad_height < 0 or pad_width < 0:
        raise ValueError("tile is smaller than the PSF")
    return F.pad(
        psf,
        (pad_width // 2, pad_width - pad_width // 2, pad_height // 2, pad_height - pad_height // 2),
        mode="constant",
        value=0.0,
    )


def optical_preprocess(batch: torch.Tensor, psf: torch.Tensor, reg: float, alpha: float) -> torch.Tensor:
    psf_frequency = torch.fft.rfft2(psf, dim=(-2, -1))
    image_frequency = torch.fft.rfft2(batch.float(), dim=(-2, -1))
    denominator = psf_frequency.conj() * psf_frequency + reg + 1e-6
    inverse_filter = psf_frequency.conj() / denominator
    restored = torch.fft.irfft2(
        image_frequency * inverse_filter,
        s=batch.shape[-2:],
        dim=(-2, -1),
    ).float()
    restored = restored.clamp(-100.0, 100.0) + 1e-6
    return batch.float() + alpha * (restored - batch.float())


@torch.inference_mode()
def reconstruct_one(model: torch.nn.Module, image: np.ndarray, device: torch.device, tile_batch: int) -> np.ndarray:
    height, width = image.shape
    pad_bottom = (-height) % ALIGNMENT
    pad_right = (-width) % ALIGNMENT
    aligned = cv2.copyMakeBorder(image, 0, pad_bottom, 0, pad_right, cv2.BORDER_REFLECT_101)
    normalized = aligned.astype(np.float32) / 255.0
    grid_height = ((normalized.shape[0] + CORE - 1) // CORE) * CORE
    grid_width = ((normalized.shape[1] + CORE - 1) // CORE) * CORE
    canvas = np.pad(
        normalized,
        ((HALO, HALO + grid_height - normalized.shape[0]), (HALO, HALO + grid_width - normalized.shape[1])),
        mode="reflect",
    )
    locations = [(top, left) for top in range(0, grid_height, CORE) for left in range(0, grid_width, CORE)]
    region_size = CORE + 2 * HALO
    psf = make_psf(device, region_size, region_size)
    output = np.empty((grid_height, grid_width), dtype=np.float32)
    optics = np.load(PACKAGE / "optics.npz")
    reg = float(optics["reg"])
    alpha = float(optics["alpha"])
    for start in range(0, len(locations), tile_batch):
        selected = locations[start : start + tile_batch]
        batch_np = np.stack(
            [canvas[top : top + region_size, left : left + region_size] for top, left in selected],
            axis=0,
        )[:, None]
        batch = torch.from_numpy(batch_np).to(device=device, dtype=torch.float32)
        batch = optical_preprocess(batch, psf, reg, alpha)
        predictions = model(batch).float().clamp(0.0, 1.0).cpu().numpy()[:, 0]
        for prediction, (top, left) in zip(predictions, selected):
            output[top : top + CORE, left : left + CORE] = prediction[HALO : HALO + CORE, HALO : HALO + CORE]
    return np.rint(output[:height, :width] * 255.0).clip(0, 255).astype(np.uint8)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--tile-batch", type=int, default=8)
    args = parser.parse_args()
    if not torch.cuda.is_available():
        raise RuntimeError("CUDA is required for this acceleration helper")
    device = torch.device("cuda:0")
    model = load_model(device)
    paths = sorted(p for p in args.input_dir.iterdir() if p.is_file() and p.suffix.lower() in {".bmp", ".png", ".jpg", ".jpeg", ".tif", ".tiff"})
    if args.limit > 0:
        paths = paths[: args.limit]
    args.output_dir.mkdir(parents=True, exist_ok=True)
    started = time.perf_counter()
    for index, source in enumerate(paths, start=1):
        image = reconstruct_one(model, read_gray(source), device, args.tile_batch)
        write_bmp(args.output_dir / source.name, image)
        print(f"{index}/{len(paths)} {source.name}", flush=True)
    torch.cuda.synchronize()
    print(f"completed={len(paths)} seconds={time.perf_counter() - started:.3f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

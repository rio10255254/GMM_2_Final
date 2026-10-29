from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import cv2
import numpy as np
import onnxruntime as ort


PACKAGE_ROOT = Path(__file__).resolve().parent
DEFAULT_MODEL = PACKAGE_ROOT / "model" / "geoedge_combo_body.onnx"
DEFAULT_CONFIG = PACKAGE_ROOT / "assets" / "preprocess_config.json"
DEFAULT_PSF = PACKAGE_ROOT / "assets" / "psf_mean.npy"
IMAGE_EXTS = {".bmp", ".png", ".tif", ".tiff", ".jpg", ".jpeg"}


def imread_unicode(path: Path) -> np.ndarray:
    data = np.fromfile(str(path), dtype=np.uint8)
    img = cv2.imdecode(data, cv2.IMREAD_UNCHANGED)
    if img is None:
        raise ValueError(f"Failed to read image: {path}")
    if img.ndim == 3:
        img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    return img


def imwrite_unicode(path: Path, image: np.ndarray) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    ok, encoded = cv2.imencode(path.suffix or ".bmp", image)
    if not ok:
        raise OSError(f"Failed to encode image: {path}")
    encoded.tofile(str(path))


def normalize_to_01(raw: np.ndarray) -> tuple[np.ndarray, np.dtype]:
    dtype = raw.dtype
    raw_f = raw.astype(np.float32)
    if np.issubdtype(dtype, np.integer):
        info = np.iinfo(dtype)
        denom = float(info.max - info.min) if info.max != info.min else 255.0
        out = (raw_f - float(info.min)) / denom
        return np.clip(out, 0.0, 1.0).astype(np.float32), dtype
    mx = float(np.max(raw_f)) if raw_f.size else 1.0
    out = raw_f / 255.0 if mx > 1.5 else raw_f
    return np.clip(out, 0.0, 1.0).astype(np.float32), dtype


def denormalize_to_dtype(pred01: np.ndarray, dtype: np.dtype) -> np.ndarray:
    pred01 = np.clip(pred01, 0.0, 1.0)
    if np.issubdtype(dtype, np.integer):
        info = np.iinfo(dtype)
        out = pred01 * float(info.max - info.min) + float(info.min)
        return np.clip(np.rint(out), info.min, info.max).astype(dtype)
    return pred01.astype(np.float32)


def pad_to_multiple(img: np.ndarray, factor: int) -> tuple[np.ndarray, int, int]:
    h, w = img.shape
    new_h = math.ceil(h / factor) * factor
    new_w = math.ceil(w / factor) * factor
    if new_h == h and new_w == w:
        return img, h, w
    pad_h = new_h - h
    pad_w = new_w - w
    return np.pad(img, ((0, pad_h), (0, pad_w)), mode="reflect"), h, w


def physics_preprocess(x01: np.ndarray, psf_mean: np.ndarray, reg: float, alpha: float) -> np.ndarray:
    if x01.ndim != 2:
        raise ValueError("physics_preprocess expects a 2D grayscale image.")
    psf = np.asarray(psf_mean, dtype=np.float32)
    if psf.ndim == 4:
        psf = psf[0, 0]
    elif psf.ndim == 3:
        psf = psf[0]
    if psf.ndim != 2:
        raise ValueError(f"Unsupported PSF shape: {psf_mean.shape}")

    h, w = x01.shape
    ph, pw = psf.shape
    if ph > h or pw > w:
        raise ValueError(f"PSF size {ph}x{pw} exceeds input size {h}x{w}.")

    pad_w = w - pw
    pad_h = h - ph
    pad_l = pad_w // 2
    pad_r = pad_w - pad_l
    pad_t = pad_h // 2
    pad_b = pad_h - pad_t
    psf_pad = np.pad(psf, ((pad_t, pad_b), (pad_l, pad_r)), mode="constant")

    img_f = np.fft.rfft2(x01.astype(np.float32))
    psf_f = np.fft.rfft2(psf_pad.astype(np.float32))
    denom = np.conj(psf_f) * psf_f + float(reg) + 1e-6
    filt = np.conj(psf_f) / denom
    deconv = np.fft.irfft2(img_f * filt, s=(h, w)).astype(np.float32)
    deconv = np.clip(deconv, -100.0, 100.0) + np.float32(1e-6)
    return (x01.astype(np.float32) + float(alpha) * (deconv - x01.astype(np.float32))).astype(np.float32)


def iter_images(input_path: Path) -> list[Path]:
    if input_path.is_file():
        return [input_path]
    if not input_path.is_dir():
        raise FileNotFoundError(f"Input path not found: {input_path}")
    return sorted(p for p in input_path.iterdir() if p.is_file() and p.suffix.lower() in IMAGE_EXTS)


def run_one(session: ort.InferenceSession, psf_mean: np.ndarray, config: dict, input_path: Path, output_path: Path) -> None:
    raw = imread_unicode(input_path)
    x01, dtype = normalize_to_01(raw)
    x_pad, h0, w0 = pad_to_multiple(x01, int(config.get("align_factor", 8)))
    x_phys = physics_preprocess(
        x_pad,
        psf_mean,
        float(config["physics_reg"]),
        float(config["physics_alpha"]),
    )
    onnx_input = x_phys[None, None, :, :].astype(np.float32)
    pred = session.run(None, {"input": onnx_input})[0][0, 0]
    pred = np.clip(pred[:h0, :w0], 0.0, 1.0)
    out = denormalize_to_dtype(pred, dtype)
    imwrite_unicode(output_path, out)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run GeoEdge COMBO ONNX inference.")
    parser.add_argument("--input", required=True, type=Path, help="Input image or directory.")
    parser.add_argument("--output", required=True, type=Path, help="Output directory.")
    parser.add_argument("--model", default=DEFAULT_MODEL, type=Path, help="ONNX model path.")
    parser.add_argument("--config", default=DEFAULT_CONFIG, type=Path, help="Preprocess config JSON.")
    parser.add_argument("--psf", default=DEFAULT_PSF, type=Path, help="PSF mean .npy path.")
    args = parser.parse_args()

    with args.config.open("r", encoding="utf-8") as f:
        config = json.load(f)
    psf_mean = np.load(args.psf).astype(np.float32)
    session = ort.InferenceSession(str(args.model), providers=["CPUExecutionProvider"])

    image_paths = iter_images(args.input)
    if not image_paths:
        raise FileNotFoundError(f"No supported images found in: {args.input}")

    args.output.mkdir(parents=True, exist_ok=True)
    for image_path in image_paths:
        out_path = args.output / image_path.name
        run_one(session, psf_mean, config, image_path, out_path)
        print(f"wrote {out_path}")


if __name__ == "__main__":
    main()

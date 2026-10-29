from __future__ import annotations

import argparse
import sys
from pathlib import Path

import cv2
import numpy as np
import onnxruntime as ort
from scipy import fft


ROOT = Path(__file__).resolve().parent
MODEL_PATH = ROOT / "model.onnx"
OPTICS_PATH = ROOT / "optics.npz"
IMAGE_EXTENSIONS = {".bmp", ".png", ".jpg", ".jpeg", ".tif", ".tiff"}
MIN_SIDE = 21
MAX_SIDE = 2180
MAX_PIXELS = 2180 * 1520


def read_image(path: Path) -> np.ndarray:
    encoded = np.fromfile(path, dtype=np.uint8)
    image = cv2.imdecode(encoded, cv2.IMREAD_UNCHANGED)
    if image is None:
        raise OSError(f"無法讀取影像：{path}")
    if image.dtype != np.uint8:
        raise ValueError(f"目前只支援 8 位元影像：{path}")
    if image.ndim == 3:
        code = cv2.COLOR_BGRA2GRAY if image.shape[2] == 4 else cv2.COLOR_BGR2GRAY
        image = cv2.cvtColor(image, code)
    if image.ndim != 2:
        raise ValueError(f"影像格式不支援：{path}")
    return image


def write_bmp(path: Path, image: np.ndarray) -> None:
    path = path.with_suffix(".bmp")
    path.parent.mkdir(parents=True, exist_ok=True)
    ok, encoded = cv2.imencode(".bmp", np.asarray(image, dtype=np.uint8))
    if not ok:
        raise OSError(f"無法輸出影像：{path}")
    encoded.tofile(path)


def collect_images(input_path: Path) -> tuple[Path, list[Path]]:
    input_path = input_path.resolve()
    if input_path.is_file():
        if input_path.suffix.lower() not in IMAGE_EXTENSIONS:
            raise ValueError(f"不支援的影像格式：{input_path}")
        return input_path.parent, [input_path]
    if not input_path.is_dir():
        raise FileNotFoundError(input_path)
    images = sorted(
        path for path in input_path.rglob("*")
        if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS
    )
    if not images:
        raise FileNotFoundError(f"找不到可處理的影像：{input_path}")
    return input_path, images


def validate_image_size(image: np.ndarray, path: Path | None = None) -> None:
    height, width = image.shape
    label = f"：{path}" if path is not None else ""
    if height < MIN_SIDE or width < MIN_SIDE:
        raise ValueError(f"影像寬與高至少需要 {MIN_SIDE} 像素{label}")
    if max(height, width) > MAX_SIDE or height * width > MAX_PIXELS:
        raise ValueError(
            "影像超出已驗證的全圖範圍；寬與高都不可超過 "
            f"{MAX_SIDE} 像素，總像素不可超過 {MAX_PIXELS}{label}"
        )


class MosrModel:
    def __init__(self, force_cpu: bool = False) -> None:
        if not MODEL_PATH.is_file() or not OPTICS_PATH.is_file():
            raise FileNotFoundError("模型檔不完整，請確認 model.onnx 與 optics.npz 都在同一資料夾。")
        optics = np.load(OPTICS_PATH)
        self.psf = optics["psf"].astype(np.float32)[None, None]
        self.reg = np.float32(optics["reg"])
        self.alpha = np.float32(optics["alpha"])
        available = ort.get_available_providers()
        providers = ["CPUExecutionProvider"]
        if not force_cpu and "CUDAExecutionProvider" in available:
            providers = ["CUDAExecutionProvider", "CPUExecutionProvider"]
        self.session = ort.InferenceSession(str(MODEL_PATH), providers=providers)
        self.input_name = self.session.get_inputs()[0].name
        self.output_name = self.session.get_outputs()[0].name
        self.provider = self.session.get_providers()[0]

    def optical_preprocess(self, image: np.ndarray) -> np.ndarray:
        _, _, height, width = image.shape
        _, _, psf_height, psf_width = self.psf.shape
        if psf_height > height or psf_width > width:
            raise ValueError("影像尺寸太小。寬與高至少需要 21 像素。")
        pad_height = height - psf_height
        pad_width = width - psf_width
        psf = np.pad(
            self.psf,
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
        denominator = np.conj(psf_frequency) * psf_frequency + self.reg + np.float32(1e-6)
        inverse_filter = np.conj(psf_frequency) / denominator
        restored = fft.irfft2(
            image_frequency * inverse_filter,
            s=(height, width),
            axes=(-2, -1),
        ).astype(np.float32)
        restored = np.clip(restored, -100.0, 100.0) + np.float32(1e-6)
        return image.astype(np.float32) + self.alpha * (restored - image.astype(np.float32))

    def reconstruct(self, image: np.ndarray) -> np.ndarray:
        validate_image_size(image)
        height, width = image.shape
        pad_bottom = (-height) % 8
        pad_right = (-width) % 8
        padded = cv2.copyMakeBorder(image, 0, pad_bottom, 0, pad_right, cv2.BORDER_REFLECT_101)
        tensor = padded.astype(np.float32)[None, None] / np.float32(255.0)
        tensor = self.optical_preprocess(tensor)
        output = self.session.run([self.output_name], {self.input_name: tensor})[0]
        output = np.clip(output[0, 0, :height, :width], 0.0, 1.0)
        return np.clip(np.rint(output * np.float32(255.0)), 0, 255).astype(np.uint8)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="MOSR 顯微影像重建")
    parser.add_argument("--input", type=Path, required=True, help="輸入影像或資料夾")
    parser.add_argument("--output", type=Path, default=Path("output"), help="輸出資料夾")
    parser.add_argument("--cpu", action="store_true", help="固定使用 CPU")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    input_root, images = collect_images(args.input)
    output_root = args.output.resolve()
    if args.input.resolve().is_dir() and output_root.is_relative_to(args.input.resolve()):
        raise ValueError("輸出資料夾不可放在輸入資料夾內，以免重複處理輸出影像。")
    for source in images:
        validate_image_size(read_image(source), source)
    model = MosrModel(force_cpu=args.cpu)
    print(f"使用：{model.provider}")
    for source in images:
        relative = source.relative_to(input_root)
        target = output_root / relative
        if target.with_suffix(".bmp").resolve() == source.resolve():
            raise ValueError(f"輸出不可覆蓋輸入影像：{source}")
        reconstruction = model.reconstruct(read_image(source))
        write_bmp(target, reconstruction)
        print(f"完成：{relative.with_suffix('.bmp')}")
    print(f"共完成 {len(images)} 張影像。")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (FileNotFoundError, OSError, ValueError) as error:
        print(f"錯誤：{error}", file=sys.stderr)
        raise SystemExit(2) from None

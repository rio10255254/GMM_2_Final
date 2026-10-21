from __future__ import annotations

import argparse
from pathlib import Path

import cv2
import numpy as np
import onnxruntime as ort
from scipy import fft


ROOT = Path(__file__).resolve().parent
MODEL_PATH = ROOT / "model.onnx"
OPTICS_PATH = ROOT / "optics.npz"
IMAGE_EXTENSIONS = {".bmp", ".png", ".jpg", ".jpeg", ".tif", ".tiff"}
ALIGNMENT = 64
MIN_TILE_HALO = 192


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
        path
        for path in input_path.rglob("*")
        if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS
    )
    if not images:
        raise FileNotFoundError(f"找不到可處理的影像：{input_path}")
    return input_path, images


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
        options = ort.SessionOptions()
        options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
        self.session = ort.InferenceSession(str(MODEL_PATH), sess_options=options, providers=providers)
        self.provider = self.session.get_providers()[0]

    def optical_preprocess(self, image: np.ndarray) -> np.ndarray:
        _, _, height, width = image.shape
        _, _, psf_height, psf_width = self.psf.shape
        if psf_height > height or psf_width > width:
            raise ValueError("影像尺寸太小。寬與高至少需要 101 像素。")
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

    def run_network(self, tensor: np.ndarray) -> np.ndarray:
        tensor = np.ascontiguousarray(tensor, dtype=np.float32)
        output = self.session.run(["output"], {"image": tensor})[0]
        return np.clip(output, 0.0, 1.0)

    def run_region(self, image: np.ndarray) -> np.ndarray:
        height, width = image.shape
        pad_bottom = (-height) % ALIGNMENT
        pad_right = (-width) % ALIGNMENT
        padded = cv2.copyMakeBorder(
            image,
            0,
            pad_bottom,
            0,
            pad_right,
            cv2.BORDER_REFLECT_101,
        )
        tensor = padded.astype(np.float32)[None, None] / np.float32(255.0)
        tensor = self.optical_preprocess(tensor)
        output = self.run_network(tensor)
        return np.clip(output[0, 0, :height, :width], 0.0, 1.0)

    def reconstruct_tiled(
        self,
        image: np.ndarray,
        core_size: int,
        halo: int,
        tile_batch: int,
    ) -> np.ndarray:
        """Phase-aligned core/halo inference for memory-bounded large images.

        A canonical reflected canvas is created once. Every tile receives the same
        phase-aligned halo, optical correction and network path, and only its central
        core is retained. This avoids weighted-blend geometry drift while keeping the
        FFT memory bounded. R61 still contains spatial GroupNorm layers and an FFT
        optical stage, so exact whole-frame parity cannot be guaranteed.
        """
        if core_size < ALIGNMENT or core_size % ALIGNMENT:
            raise ValueError(f"分塊核心尺寸必須是 {ALIGNMENT} 的倍數。")
        if halo < MIN_TILE_HALO or halo % ALIGNMENT:
            raise ValueError(
                f"halo 至少需要 {MIN_TILE_HALO} 像素，且必須是 {ALIGNMENT} 的倍數。"
            )
        if tile_batch < 1:
            raise ValueError("tile-batch 至少需要 1。")

        height, width = image.shape
        pad_bottom = (-height) % ALIGNMENT
        pad_right = (-width) % ALIGNMENT
        aligned = cv2.copyMakeBorder(
            image,
            0,
            pad_bottom,
            0,
            pad_right,
            cv2.BORDER_REFLECT_101,
        )

        normalized = aligned.astype(np.float32) / np.float32(255.0)
        aligned_height, aligned_width = normalized.shape
        grid_height = ((aligned_height + core_size - 1) // core_size) * core_size
        grid_width = ((aligned_width + core_size - 1) // core_size) * core_size
        canvas = np.pad(
            normalized,
            (
                (halo, halo + grid_height - aligned_height),
                (halo, halo + grid_width - aligned_width),
            ),
            mode="reflect",
        ).astype(np.float32, copy=False)

        locations = [
            (top, left)
            for top in range(0, grid_height, core_size)
            for left in range(0, grid_width, core_size)
        ]
        print(
            f"分塊模式：{len(locations)} 塊，核心 {core_size}，halo {halo}，"
            f"batch {tile_batch}"
        )
        output = np.empty((grid_height, grid_width), dtype=np.float32)
        region_size = core_size + 2 * halo
        for start in range(0, len(locations), tile_batch):
            selected = locations[start : start + tile_batch]
            batch = np.stack(
                [
                    canvas[top : top + region_size, left : left + region_size]
                    for top, left in selected
                ],
                axis=0,
            )[:, None]
            batch = self.optical_preprocess(batch)
            predictions = self.run_network(batch)[:, 0]
            for prediction, (top, left) in zip(predictions, selected):
                output[top : top + core_size, left : left + core_size] = prediction[
                    halo : halo + core_size,
                    halo : halo + core_size,
                ]

        return np.clip(output[:height, :width], 0.0, 1.0)

    def reconstruct(
        self,
        image: np.ndarray,
        tile_size: int,
        halo: int,
        tile_batch: int,
    ) -> np.ndarray:
        height, width = image.shape
        if min(height, width) < 101:
            raise ValueError("影像寬與高至少需要 101 像素。")
        if tile_size <= 0 or (height <= tile_size and width <= tile_size):
            output = self.run_region(image)
            return np.clip(np.rint(output * np.float32(255.0)), 0, 255).astype(np.uint8)
        output = self.reconstruct_tiled(image, tile_size, halo, tile_batch)
        return np.clip(np.rint(output * np.float32(255.0)), 0, 255).astype(np.uint8)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="MOSR 顯微影像重建")
    parser.add_argument("--input", type=Path, required=True, help="輸入影像或資料夾")
    parser.add_argument("--output", type=Path, default=Path("output"), help="輸出資料夾")
    parser.add_argument("--tile-size", type=int, default=0, help="0 為整張處理；5120 大圖建議設為 640")
    parser.add_argument("--halo", type=int, default=192, help="分塊核心外保留的上下文，至少 192")
    parser.add_argument("--tile-batch", type=int, default=1, help="同時處理的分塊數量")
    parser.add_argument("--overlap", type=int, default=None, help=argparse.SUPPRESS)
    parser.add_argument("--cpu", action="store_true", help="固定使用 CPU")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    input_root, images = collect_images(args.input)
    output_root = args.output.resolve()
    model = MosrModel(force_cpu=args.cpu)
    print(f"使用：{model.provider}")
    halo = args.halo if args.overlap is None else args.overlap
    if args.overlap is not None:
        print("提醒：--overlap 已改名為 --halo；本次仍按相同數值執行。")
    for source in images:
        relative = source.relative_to(input_root)
        reconstruction = model.reconstruct(
            read_image(source),
            args.tile_size,
            halo,
            args.tile_batch,
        )
        write_bmp(output_root / relative, reconstruction)
        print(f"完成：{relative.with_suffix('.bmp')}")
    print(f"共完成 {len(images)} 張影像。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

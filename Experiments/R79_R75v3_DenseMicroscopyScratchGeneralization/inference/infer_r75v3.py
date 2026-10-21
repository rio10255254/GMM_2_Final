"""R75-v3 手動推論入口。

訓練完成後，把影像放進 data/inference_input，直接按執行即可。
也可以在下方指定單一影像、資料夾、權重與輸出位置。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

import cv2
import numpy as np
import torch


# =====================================================================
# 可手動調整的設定
# =====================================================================
CHECKPOINT_PATH = ""          # 空白時自動使用 weights/formal 內最新的正式權重
INPUT_PATH = ""               # 空白時使用 data/inference_input
OUTPUT_PATH = ""              # 空白時使用 results/inference_output
DEVICE = "cuda:0"
USE_EMA_WEIGHTS = True
MIN_SIDE = 21
MAX_SIDE = 2180
MAX_PIXELS = 2180 * 1520


EXPERIMENT_DIR = Path(__file__).resolve().parents[1]
MODEL_DIR = EXPERIMENT_DIR / "model"
DEFAULT_INPUT = EXPERIMENT_DIR / "data" / "inference_input"
DEFAULT_OUTPUT = EXPERIMENT_DIR / "results" / "inference_output"
ANALYTIC_PSF = MODEL_DIR / "analytic_psf_bank.mat"
IMAGE_EXTENSIONS = {".bmp", ".png", ".jpg", ".jpeg", ".tif", ".tiff"}

sys.path.insert(0, str(MODEL_DIR))
from GeoEdgeAlignSR_v1_ModelA_v5_NoCoord import GeoEdgeAlignSR_v1_v5_NoCoord  # noqa: E402


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def find_latest_formal_checkpoint() -> Path:
    candidates = list((EXPERIMENT_DIR / "weights" / "formal").glob("**/best_tradeoff.pth.tar"))
    if not candidates:
        raise FileNotFoundError(
            "找不到正式權重。請先執行 training/train_r75v3.py，"
            "或在 CHECKPOINT_PATH 指定權重。"
        )
    return max(candidates, key=lambda path: path.stat().st_mtime_ns)


def collect_images(input_path: Path) -> tuple[Path, list[Path]]:
    input_path = input_path.resolve()
    if input_path.is_file():
        if input_path.suffix.lower() not in IMAGE_EXTENSIONS:
            raise ValueError(f"不支援的影像格式：{input_path}")
        return input_path.parent, [input_path]
    input_path.mkdir(parents=True, exist_ok=True)
    images = sorted(
        path for path in input_path.rglob("*")
        if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS
    )
    if not images:
        raise FileNotFoundError(f"輸入資料夾沒有影像：{input_path}")
    return input_path, images


def read_gray(path: Path) -> np.ndarray:
    image = cv2.imdecode(np.fromfile(path, dtype=np.uint8), cv2.IMREAD_GRAYSCALE)
    if image is None:
        raise OSError(f"無法讀取影像：{path}")
    return image


def write_bmp(path: Path, image: np.ndarray) -> None:
    path = path.with_suffix(".bmp")
    path.parent.mkdir(parents=True, exist_ok=True)
    ok, encoded = cv2.imencode(".bmp", np.asarray(image, dtype=np.uint8))
    if not ok:
        raise OSError(f"無法寫出影像：{path}")
    encoded.tofile(path)


def build_model(checkpoint_path: Path, device: str, use_ema: bool) -> tuple[torch.nn.Module, str]:
    if not ANALYTIC_PSF.is_file():
        raise FileNotFoundError(f"缺少模型內建的數學模糊核心：{ANALYTIC_PSF}")
    model = GeoEdgeAlignSR_v1_v5_NoCoord(
        psf_fitted_path=str(ANALYTIC_PSF),
        psf_grid_rows=3,
        psf_grid_cols=3,
        psf_use_stack_mean=True,
        psf_deconv_reg=30.0,
        psf_phys_alpha_init=0.05,
        psf_phys_alpha_min=0.0,
        psf_phys_alpha_max=0.20,
        use_upsample_conv=True,
        use_band_limit=False,
        weak_psf_enable=True,
        weak_psf_k=4,
        weak_psf_beta_init=0.0,
        weak_psf_beta_scale_max=0.0,
        learnable_blur=False,
        use_bottleneck_se=False,
        boundary_residual_adapter_enable=True,
        boundary_residual_adapter_hidden=16,
        boundary_residual_adapter_max=0.018,
        boundary_residual_adapter_gate_bias=-2.0,
        boundary_residual_adapter_delta_bias=True,
        boundary_residual_adapter_zero_mean=False,
        boundary_residual_adapter_edge_gate=False,
        boundary_residual_adapter_polarity_split=False,
        boundary_residual_adapter_orientation_inputs=True,
        raw_anchor_output_mode="none",
        quality_gate_enable=False,
    )
    checkpoint = torch.load(checkpoint_path, map_location="cpu")
    state_key = "ema_state_dict" if use_ema and checkpoint.get("ema_state_dict") else "state_dict"
    state = checkpoint.get(state_key, checkpoint)
    cleaned = {
        (name[7:] if name.startswith("module.") else name): value
        for name, value in state.items()
    }
    model.load_state_dict(cleaned, strict=True)
    model.to(device).eval()
    return model, state_key


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


def infer_full_frame(model: torch.nn.Module, image: np.ndarray, device: str) -> np.ndarray:
    validate_image_size(image)
    height, width = image.shape
    pad_bottom = (-height) % 8
    pad_right = (-width) % 8
    padded = cv2.copyMakeBorder(image, 0, pad_bottom, 0, pad_right, cv2.BORDER_REFLECT_101)
    tensor = torch.from_numpy(padded.astype(np.float32) / 255.0)[None, None].to(device)
    use_amp = str(device).lower().startswith("cuda")
    with torch.no_grad(), torch.cuda.amp.autocast(enabled=use_amp):
        output = model(tensor).float().clamp(0.0, 1.0)
    output = output[0, 0, :height, :width].cpu().numpy()
    return np.clip(np.rint(output * 255.0), 0, 255).astype(np.uint8)


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="R75-v3 manual inference")
    parser.add_argument("--checkpoint", type=Path, default=Path(CHECKPOINT_PATH) if CHECKPOINT_PATH else None)
    parser.add_argument("--input", type=Path, default=Path(INPUT_PATH) if INPUT_PATH else DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=Path(OUTPUT_PATH) if OUTPUT_PATH else DEFAULT_OUTPUT)
    parser.add_argument("--device", default=DEVICE)
    parser.add_argument("--no-ema", action="store_true", default=not USE_EMA_WEIGHTS)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    checkpoint = args.checkpoint.resolve() if args.checkpoint else find_latest_formal_checkpoint().resolve()
    if not checkpoint.is_file():
        raise FileNotFoundError(checkpoint)
    input_root, images = collect_images(args.input)
    output_root = args.output.resolve()
    if args.input.resolve().is_dir() and output_root.is_relative_to(args.input.resolve()):
        raise ValueError("輸出資料夾不可放在輸入資料夾內，以免重複處理輸出影像。")
    for source_path in images:
        validate_image_size(read_gray(source_path), source_path)
    model, state_key = build_model(checkpoint, args.device, not args.no_ema)
    records = []
    for source_path in images:
        relative = source_path.relative_to(input_root)
        target = (output_root / relative).with_suffix(".bmp")
        if target.resolve() == source_path.resolve():
            raise ValueError(f"輸出不可覆蓋輸入影像：{source_path}")
        source = read_gray(source_path)
        reconstruction = infer_full_frame(model, source, args.device)
        write_bmp(target, reconstruction)
        records.append(
            {
                "input": str(source_path),
                "output": str(target),
                "shape": list(source.shape),
            }
        )
        print(f"完成：{relative}")
    manifest = {
        "experiment_id": "R79_R75v3_DenseMicroscopyScratchGeneralization",
        "checkpoint": str(checkpoint),
        "checkpoint_sha256": sha256(checkpoint),
        "state_key": state_key,
        "device": args.device,
        "inference_mode": "single_full_frame_only",
        "maximum_side": MAX_SIDE,
        "maximum_pixels": MAX_PIXELS,
        "image_count": len(records),
        "records": records,
    }
    output_root.mkdir(parents=True, exist_ok=True)
    (output_root / "inference_manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print(f"共完成 {len(records)} 張，輸出位置：{output_root}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (FileNotFoundError, OSError, ValueError) as error:
        print(f"錯誤：{error}", file=sys.stderr)
        raise SystemExit(2) from None

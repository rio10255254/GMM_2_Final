from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import cv2
import numpy as np


def _as_float_gray(image: np.ndarray) -> np.ndarray:
    if image.ndim == 3:
        image = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    return image.astype(np.float32)


def _clip_like(image: np.ndarray, reference: np.ndarray) -> np.ndarray:
    if np.issubdtype(reference.dtype, np.integer):
        info = np.iinfo(reference.dtype)
        return np.clip(image, info.min, info.max).round().astype(reference.dtype)
    return image.astype(reference.dtype, copy=False)


def blend_with_raw(raw: np.ndarray, recon: np.ndarray, *, alpha: float) -> np.ndarray:
    if not 0.0 <= alpha <= 1.0:
        raise ValueError("alpha must be between 0 and 1")
    raw_f = raw.astype(np.float32)
    recon_f = recon.astype(np.float32)
    if raw_f.shape != recon_f.shape:
        raise ValueError(f"shape mismatch: raw={raw_f.shape}, recon={recon_f.shape}")
    return (1.0 - float(alpha)) * raw_f + float(alpha) * recon_f


def motion_preserving_detail(
    raw: np.ndarray,
    recon: np.ndarray,
    *,
    sigma: float = 2.0,
    detail_gain: float = 0.35,
) -> np.ndarray:
    if sigma <= 0:
        raise ValueError("sigma must be positive")
    raw_f = raw.astype(np.float32)
    recon_f = recon.astype(np.float32)
    if raw_f.shape != recon_f.shape:
        raise ValueError(f"shape mismatch: raw={raw_f.shape}, recon={recon_f.shape}")

    recon_low = cv2.GaussianBlur(recon_f, (0, 0), float(sigma))
    recon_high = recon_f - recon_low
    fused = raw_f + float(detail_gain) * recon_high
    fused += float(np.mean(raw_f) - np.mean(fused))
    return fused


def _sorted_images(folder: Path, pattern: str) -> list[Path]:
    files = sorted(Path(folder).glob(pattern))
    if not files:
        raise FileNotFoundError(f"no images matching {pattern!r} in {folder}")
    return files


def fuse_folder(
    raw_dir: Path,
    recon_dir: Path,
    output_dir: Path,
    *,
    mode: str,
    alpha: float = 0.2,
    sigma: float = 2.0,
    detail_gain: float = 0.35,
    pattern: str = "*.bmp",
) -> dict[str, Any]:
    raw_files = _sorted_images(Path(raw_dir), pattern)
    recon_files = _sorted_images(Path(recon_dir), pattern)
    if len(raw_files) != len(recon_files):
        raise ValueError(f"image count mismatch: raw={len(raw_files)}, recon={len(recon_files)}")

    Path(output_dir).mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, Any]] = []
    for raw_path, recon_path in zip(raw_files, recon_files):
        raw = cv2.imread(str(raw_path), cv2.IMREAD_UNCHANGED)
        recon = cv2.imread(str(recon_path), cv2.IMREAD_UNCHANGED)
        if raw is None:
            raise ValueError(f"failed to read raw image: {raw_path}")
        if recon is None:
            raise ValueError(f"failed to read reconstruction image: {recon_path}")
        raw_gray = _as_float_gray(raw)
        recon_gray = _as_float_gray(recon)
        if mode == "blend":
            fused = blend_with_raw(raw_gray, recon_gray, alpha=alpha)
        elif mode == "detail":
            fused = motion_preserving_detail(raw_gray, recon_gray, sigma=sigma, detail_gain=detail_gain)
        else:
            raise ValueError("mode must be blend or detail")
        output = _clip_like(fused, raw if raw.ndim == 2 else raw[..., 0])
        out_path = Path(output_dir) / raw_path.name
        ok = cv2.imwrite(str(out_path), output)
        if not ok:
            raise ValueError(f"failed to write output image: {out_path}")
        rows.append(
            {
                "raw": str(raw_path),
                "recon": str(recon_path),
                "output": str(out_path),
                "raw_name": raw_path.name,
                "recon_name": recon_path.name,
            }
        )

    manifest = {
        "algorithm": "motion_preserving_fusion",
        "mode": mode,
        "alpha": float(alpha),
        "sigma": float(sigma),
        "detail_gain": float(detail_gain),
        "raw_dir": str(Path(raw_dir)),
        "recon_dir": str(Path(recon_dir)),
        "output_dir": str(Path(output_dir)),
        "image_count": len(rows),
        "pattern": pattern,
        "rows": rows,
    }
    with (Path(output_dir).parent / f"{Path(output_dir).name}_manifest.json").open("w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)
    return manifest


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Fuse raw low-frequency position with reconstruction detail.")
    parser.add_argument("--raw-dir", required=True)
    parser.add_argument("--recon-dir", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--mode", choices=["blend", "detail"], required=True)
    parser.add_argument("--alpha", type=float, default=0.2)
    parser.add_argument("--sigma", type=float, default=2.0)
    parser.add_argument("--detail-gain", type=float, default=0.35)
    parser.add_argument("--pattern", default="*.bmp")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    manifest = fuse_folder(
        Path(args.raw_dir),
        Path(args.recon_dir),
        Path(args.output_dir),
        mode=args.mode,
        alpha=args.alpha,
        sigma=args.sigma,
        detail_gain=args.detail_gain,
        pattern=args.pattern,
    )
    print(f"Wrote {manifest['image_count']} fused images to {manifest['output_dir']}")


if __name__ == "__main__":
    main()

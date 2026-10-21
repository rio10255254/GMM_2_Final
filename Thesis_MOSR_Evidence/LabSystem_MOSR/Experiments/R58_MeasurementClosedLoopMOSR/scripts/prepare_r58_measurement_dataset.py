"""Prepare R58 measurement-closed-loop MOSR training packages."""
from __future__ import annotations

import argparse
import json
import os
import shutil
from datetime import datetime
from pathlib import Path
from typing import Iterable

import cv2
import numpy as np


LAB_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_BASE_PACKAGE = (
    LAB_ROOT
    / "Training_Data"
    / "r55_source_style_rebuild"
    / "r53_realistic_dataset_calibration"
    / "r53_realistic_calibrated_train_6000"
)
DEFAULT_OUTPUT_ROOT = LAB_ROOT / "Training_Data" / "r58_measurement_closed_loop" / "hs100mg_basler"
DEFAULT_PACKAGE_NAME = "r58_frac050_train"
ANCHOR_ROLE_DIR = "stage_58_hs100mg_anchor"

CAMERA_NAME = "Basler ace acA2040-120um"
NM_PER_PX = 69.0
PITCH_NM = 5000.0
SEM_RADIUS_NM = {
    "pillar": 1321.8820022050588,
    "via": 1641.9986465187549,
}
SOURCE_RADIUS_BIAS_NM = {
    "pillar": 11.043151807599543,
    "via": -66.13489918240407,
}
CORRECTION_DIRECTION = {
    "pillar": "shrink_pillar",
    "via": "expand_via",
}


def _read_manifest(package: Path) -> dict:
    manifest_path = package / "manifest.json"
    if not manifest_path.exists():
        raise FileNotFoundError(manifest_path)
    return json.loads(manifest_path.read_text(encoding="utf-8"))


def _read_gray(path: Path) -> np.ndarray:
    data = np.fromfile(str(path), dtype=np.uint8)
    img = cv2.imdecode(data, cv2.IMREAD_GRAYSCALE)
    if img is None:
        raise RuntimeError(f"failed to read image: {path}")
    return img


def _write_image(path: Path, img: np.ndarray) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    ok, encoded = cv2.imencode(path.suffix or ".bmp", img.astype(np.uint8, copy=False))
    if not ok:
        raise RuntimeError(f"failed to encode image: {path}")
    path.write_bytes(encoded.tobytes())


def _gradient_p95(img: np.ndarray) -> float:
    gray = img.astype(np.uint8, copy=False)
    blur = cv2.GaussianBlur(gray, (3, 3), 0)
    gx = cv2.Sobel(blur, cv2.CV_32F, 1, 0, ksize=3)
    gy = cv2.Sobel(blur, cv2.CV_32F, 0, 1, ksize=3)
    mag = cv2.magnitude(gx, gy)
    return float(np.percentile(mag, 95))


def compute_geometry_from_label(img: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    gray = img.astype(np.uint8, copy=False)
    blur = cv2.GaussianBlur(gray, (3, 3), 0)
    gx = cv2.Sobel(blur, cv2.CV_32F, 1, 0, ksize=3)
    gy = cv2.Sobel(blur, cv2.CV_32F, 0, 1, ksize=3)
    mag = cv2.magnitude(gx, gy)
    threshold = max(5.0, float(np.percentile(mag, 88)))
    centerline = (mag >= threshold).astype(np.uint8) * 255
    centerline = cv2.morphologyEx(centerline, cv2.MORPH_OPEN, np.ones((2, 2), np.uint8))
    if np.count_nonzero(centerline) == 0:
        centerline = cv2.Canny(gray, 40, 120)
    boundary = cv2.dilate(centerline, np.ones((3, 3), np.uint8), iterations=1)
    distance = cv2.distanceTransform((boundary == 0).astype(np.uint8), cv2.DIST_L2, 3).astype(np.float32)
    return boundary.astype(np.uint8), centerline.astype(np.uint8), distance


def _link_or_copy_file(src: Path, dst: Path, mode: str) -> str:
    dst.parent.mkdir(parents=True, exist_ok=True)
    if dst.exists():
        return "exists"
    if mode in {"hardlink", "auto"}:
        try:
            os.link(src, dst)
            return "hardlink"
        except OSError:
            if mode == "hardlink":
                raise
    shutil.copy2(src, dst)
    return "copy"


def _manifest_rel(record: dict, key: str, prefix: str) -> Path | None:
    value = str(record.get(key, "") or "").replace("\\", "/")
    if not value:
        return None
    path = Path(value)
    parts = path.parts
    if parts and parts[0].lower() == prefix.lower():
        return Path(*parts[1:])
    return path


def _record_source_path(base_package: Path, record: dict, package_key: str, absolute_key: str) -> Path:
    package_value = str(record.get(package_key, "") or "")
    if package_value:
        path = Path(package_value)
        if not path.is_absolute():
            path = base_package / path
        if path.exists():
            return path
    absolute_value = str(record.get(absolute_key, "") or "")
    if absolute_value:
        path = Path(absolute_value)
        if path.exists():
            return path
    raise FileNotFoundError(f"cannot resolve {package_key}/{absolute_key} in base manifest")


def _write_geometry_for_label(lbl_path: Path, geom_root: Path, rel: Path) -> dict:
    boundary, centerline, distance = compute_geometry_from_label(_read_gray(lbl_path))
    boundary_rel = Path("geom") / "boundary" / rel
    centerline_rel = Path("geom") / "centerline" / rel
    distance_rel = Path("geom") / "distance" / rel.with_suffix(".npy")
    _write_image(geom_root.parent / boundary_rel, boundary)
    _write_image(geom_root.parent / centerline_rel, centerline)
    distance_path = geom_root.parent / distance_rel
    distance_path.parent.mkdir(parents=True, exist_ok=True)
    np.save(distance_path, distance.astype(np.float32, copy=False))
    return {
        "geometry_boundary": boundary_rel.as_posix(),
        "geometry_centerline": centerline_rel.as_posix(),
        "geometry_distance": distance_rel.as_posix(),
    }


def _copy_or_generate_base_geometry(
    *,
    base_package: Path,
    package_dir: Path,
    record: dict,
    lbl_dst: Path,
    geom_rel: Path,
    link_mode: str,
) -> dict:
    geom_keys = {
        "geometry_boundary": ("boundary", ".bmp"),
        "geometry_centerline": ("centerline", ".bmp"),
        "geometry_distance": ("distance", ".npy"),
    }
    out: dict[str, str] = {}
    all_copied = True
    for key, (leaf, suffix) in geom_keys.items():
        value = str(record.get(key, "") or "")
        if not value:
            all_copied = False
            break
        src = Path(value)
        if not src.is_absolute():
            src = base_package / src
        if not src.exists():
            all_copied = False
            break
        rel = Path("geom") / leaf / geom_rel.with_suffix(suffix)
        _link_or_copy_file(src, package_dir / rel, link_mode)
        out[key] = rel.as_posix()
    if all_copied:
        return out
    return _write_geometry_for_label(lbl_dst, package_dir / "geom", geom_rel)


def _copy_base_pairs(
    *,
    base_package: Path,
    package_dir: Path,
    base_limit: int | None,
    link_mode: str,
) -> list[dict]:
    manifest = _read_manifest(base_package)
    pairs = list(manifest.get("pairs", []))
    if not pairs:
        raise RuntimeError(f"base manifest contains no pairs: {base_package / 'manifest.json'}")
    if base_limit is not None:
        pairs = pairs[: max(0, int(base_limit))]

    out_records: list[dict] = []
    for idx, record in enumerate(pairs):
        src_path = _record_source_path(base_package, record, "package_src", "src")
        lbl_path = _record_source_path(base_package, record, "package_lbl", "lbl")
        src_rel_base = _manifest_rel(record, "package_src", "src") or Path(src_path.name)
        lbl_rel_base = _manifest_rel(record, "package_lbl", "lbl") or Path(lbl_path.name)
        src_rel = Path("r55_base") / src_rel_base
        lbl_rel = Path("r55_base") / lbl_rel_base
        _link_or_copy_file(src_path, package_dir / "src" / src_rel, link_mode)
        _link_or_copy_file(lbl_path, package_dir / "lbl" / lbl_rel, link_mode)
        geom_record = _copy_or_generate_base_geometry(
            base_package=base_package,
            package_dir=package_dir,
            record=record,
            lbl_dst=package_dir / "lbl" / lbl_rel,
            geom_rel=lbl_rel,
            link_mode=link_mode,
        )
        out_records.append(
            {
                "package_src": (Path("src") / src_rel).as_posix(),
                "package_lbl": (Path("lbl") / lbl_rel).as_posix(),
                "source_group": "r55_base",
                "source_index": idx,
                **geom_record,
            }
        )
    return out_records


def _sample_circle_style(*, feature: str, rng: np.random.Generator) -> dict[str, int]:
    if feature == "pillar":
        bg = int(rng.integers(58, 82))
        fg = int(rng.integers(150, 188))
    else:
        bg = int(rng.integers(140, 176))
        fg = int(rng.integers(48, 80))
    return {"bg": bg, "fg": fg}


def _sample_circle_layout(
    *,
    image_size: int,
    pitch_px: float,
    rng: np.random.Generator,
) -> list[tuple[float, float, float]]:
    layout: list[tuple[float, float, float]] = []
    offset_x = image_size / 2.0 - pitch_px
    offset_y = image_size / 2.0 - pitch_px
    for yy in range(4):
        for xx in range(4):
            cx = offset_x + xx * pitch_px + float(rng.normal(0.0, 0.28))
            cy = offset_y + yy * pitch_px + float(rng.normal(0.0, 0.28))
            if 8 <= cx < image_size - 8 and 8 <= cy < image_size - 8:
                layout.append((cx, cy, float(rng.uniform(0.99, 1.01))))
    return layout


def _draw_circle_layout(
    *,
    feature: str,
    image_size: int,
    radius_px: float,
    layout: list[tuple[float, float, float]],
    style: dict[str, int],
) -> np.ndarray:
    del feature
    img = np.full((image_size, image_size), int(style["bg"]), np.uint8)
    for cx, cy, radius_scale in layout:
        radius = max(1.0, float(radius_px) * float(radius_scale))
        cv2.circle(
            img,
            (int(round(cx)), int(round(cy))),
            int(round(radius)),
            int(style["fg"]),
            -1,
            lineType=cv2.LINE_AA,
        )
    return img


def _feature_centroid(img: np.ndarray, feature: str) -> tuple[float, float]:
    if feature == "pillar":
        mask = img > np.percentile(img, 70)
    else:
        mask = img < np.percentile(img, 30)
    ys, xs = np.nonzero(mask)
    if len(xs) == 0:
        return float(img.shape[1] / 2.0), float(img.shape[0] / 2.0)
    return float(xs.mean()), float(ys.mean())


def _make_real_style_source(
    label: np.ndarray,
    *,
    rng: np.random.Generator,
    target_grad95: float = 64.0,
) -> np.ndarray:
    sigma = float(rng.uniform(2.2, 3.1))
    blurred = cv2.GaussianBlur(label.astype(np.uint8, copy=False), (0, 0), sigmaX=sigma, sigmaY=sigma)
    h, w = label.shape
    x_grad = np.linspace(-1.0, 1.0, w, dtype=np.float32)[None, :]
    y_grad = np.linspace(-1.0, 1.0, h, dtype=np.float32)[:, None]
    illum = 1.0 + float(rng.uniform(-0.07, 0.07)) * x_grad + float(rng.uniform(-0.05, 0.05)) * y_grad
    out = blurred.astype(np.float32) * illum
    out += rng.normal(0.0, float(rng.uniform(1.8, 4.2)), size=label.shape)
    out = np.clip(out, 0, 255).astype(np.uint8)

    grad = _gradient_p95(out)
    if grad > 1e-6 and np.isfinite(grad):
        contrast_scale = float(np.clip(float(target_grad95) / grad, 0.55, 1.15))
        mean = float(np.mean(out))
        out = np.clip((out.astype(np.float32) - mean) * contrast_scale + mean, 0, 255).astype(np.uint8)
    return out


def _target_radius_from_fraction(feature: str, correction_fraction: float) -> tuple[float, float, float]:
    sem_radius_nm = float(SEM_RADIUS_NM[feature])
    source_radius_nm = max(NM_PER_PX * 2.0, sem_radius_nm + float(SOURCE_RADIUS_BIAS_NM[feature]))
    fraction = float(np.clip(correction_fraction, 0.0, 1.0))
    target_radius_nm = source_radius_nm + (sem_radius_nm - source_radius_nm) * fraction
    return source_radius_nm, target_radius_nm, sem_radius_nm


def _write_anchor_pair(
    *,
    package_dir: Path,
    feature: str,
    idx: int,
    image_size: int,
    correction_fraction: float,
    rng: np.random.Generator,
) -> dict:
    source_radius_nm, target_radius_nm, sem_radius_nm = _target_radius_from_fraction(feature, correction_fraction)
    source_radius_px = source_radius_nm / NM_PER_PX
    target_radius_px = target_radius_nm / NM_PER_PX
    pitch_px = PITCH_NM / NM_PER_PX
    style = _sample_circle_style(feature=feature, rng=rng)
    layout = _sample_circle_layout(image_size=image_size, pitch_px=pitch_px, rng=rng)
    target_label = _draw_circle_layout(
        feature=feature,
        image_size=image_size,
        radius_px=target_radius_px,
        layout=layout,
        style=style,
    )
    source_geometry = _draw_circle_layout(
        feature=feature,
        image_size=image_size,
        radius_px=source_radius_px,
        layout=layout,
        style=style,
    )
    source = _make_real_style_source(source_geometry, rng=rng, target_grad95=64.0)
    stem = f"hs100mg_{feature}_{idx:04d}.bmp"
    rel = Path(ANCHOR_ROLE_DIR) / feature / stem
    _write_image(package_dir / "src" / rel, source)
    _write_image(package_dir / "lbl" / rel, target_label)
    geom = _write_geometry_for_label(package_dir / "lbl" / rel, package_dir / "geom", rel)
    return {
        "package_src": (Path("src") / rel).as_posix(),
        "package_lbl": (Path("lbl") / rel).as_posix(),
        "source_group": "hs100mg_basler_anchor",
        "feature": feature,
        "sem_radius_nm": sem_radius_nm,
        "source_radius_nm": source_radius_nm,
        "target_radius_nm": target_radius_nm,
        "source_radius_bias_nm": source_radius_nm - sem_radius_nm,
        "target_radius_bias_nm": target_radius_nm - sem_radius_nm,
        "source_radius_px": source_radius_px,
        "target_radius_px": target_radius_px,
        "applied_correction_fraction": float(np.clip(correction_fraction, 0.0, 1.0)),
        "correction_direction": CORRECTION_DIRECTION[feature],
        "source_grad_p95": _gradient_p95(source),
        "target_grad_p95": _gradient_p95(target_label),
        **geom,
    }


def _write_anchor_pairs(
    *,
    package_dir: Path,
    anchor_count: int,
    image_size: int,
    correction_fraction: float,
    seed: int,
) -> list[dict]:
    rng = np.random.default_rng(int(seed))
    records: list[dict] = []
    for idx in range(max(0, int(anchor_count))):
        feature = "pillar" if idx % 2 == 0 else "via"
        records.append(
            _write_anchor_pair(
                package_dir=package_dir,
                feature=feature,
                idx=idx,
                image_size=image_size,
                correction_fraction=correction_fraction,
                rng=rng,
            )
        )
    return records


def _count_files(root: Path) -> int:
    if not root.exists():
        return 0
    return sum(1 for p in root.rglob("*") if p.is_file())


def _safe_clean_package_dir(package_dir: Path, output_root: Path) -> None:
    package_resolved = package_dir.resolve()
    output_resolved = output_root.resolve()
    try:
        within_output = package_resolved.is_relative_to(output_resolved)
    except AttributeError:
        within_output = str(package_resolved).lower().startswith(str(output_resolved).lower() + os.sep)
    if not within_output or package_resolved == output_resolved:
        raise RuntimeError(f"refusing to clean package outside output root: {package_resolved}")
    if package_dir.exists():
        shutil.rmtree(package_dir)


def prepare_package(
    *,
    base_package: Path = DEFAULT_BASE_PACKAGE,
    output_root: Path = DEFAULT_OUTPUT_ROOT,
    package_name: str = DEFAULT_PACKAGE_NAME,
    base_limit: int | None = None,
    anchor_count: int = 2048,
    image_size: int = 256,
    correction_fraction: float = 0.5,
    link_mode: str = "auto",
    seed: int = 5800,
) -> dict:
    base_package = Path(base_package).resolve()
    output_root = Path(output_root).resolve()
    package_dir = output_root / package_name
    if not base_package.exists():
        raise FileNotFoundError(f"base package not found: {base_package}")
    if link_mode not in {"auto", "hardlink", "copy"}:
        raise ValueError(f"unknown link mode: {link_mode}")
    _safe_clean_package_dir(package_dir, output_root)
    package_dir.mkdir(parents=True, exist_ok=True)

    base_records = _copy_base_pairs(
        base_package=base_package,
        package_dir=package_dir,
        base_limit=base_limit,
        link_mode=link_mode,
    )
    anchor_records = _write_anchor_pairs(
        package_dir=package_dir,
        anchor_count=anchor_count,
        image_size=image_size,
        correction_fraction=correction_fraction,
        seed=seed,
    )
    pairs = [*base_records, *anchor_records]
    manifest = {
        "profile": package_name,
        "r58_measurement_closed_loop": True,
        "camera": CAMERA_NAME,
        "nm_per_px": NM_PER_PX,
        "pitch_nm": PITCH_NM,
        "sem_radius_nm": SEM_RADIUS_NM,
        "source_radius_bias_nm": SOURCE_RADIUS_BIAS_NM,
        "correction_direction": CORRECTION_DIRECTION,
        "correction_fraction": float(np.clip(correction_fraction, 0.0, 1.0)),
        "anchor_role_dir": ANCHOR_ROLE_DIR,
        "base_package": str(base_package),
        "base_pairs": len(base_records),
        "anchor_pairs": len(anchor_records),
        "total_pairs": len(pairs),
        "pairs": pairs,
        "geometry_sidecars": True,
        "geometry_count": len(pairs),
        "geom_dir": str(package_dir / "geom"),
        "generator": "prepare_r58_measurement_dataset_v1",
        "generated_at": datetime.now().replace(microsecond=0).isoformat(),
    }
    (package_dir / "manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    return {
        "package_dir": str(package_dir),
        "base_package": str(base_package),
        "base_pairs": len(base_records),
        "anchor_pairs": len(anchor_records),
        "total_pairs": len(pairs),
        "correction_fraction": float(np.clip(correction_fraction, 0.0, 1.0)),
        "geometry_boundary_files": _count_files(package_dir / "geom" / "boundary"),
        "geometry_centerline_files": _count_files(package_dir / "geom" / "centerline"),
        "geometry_distance_files": _count_files(package_dir / "geom" / "distance"),
        "manifest": str(package_dir / "manifest.json"),
    }


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Prepare R58 measurement-closed-loop MOSR training data")
    parser.add_argument("--base-package", type=Path, default=DEFAULT_BASE_PACKAGE)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--package-name", default=DEFAULT_PACKAGE_NAME)
    parser.add_argument("--base-limit", type=int, default=None)
    parser.add_argument("--anchor-count", type=int, default=2048)
    parser.add_argument("--image-size", type=int, default=256)
    parser.add_argument("--correction-fraction", type=float, default=0.5)
    parser.add_argument("--link-mode", choices=("auto", "hardlink", "copy"), default="auto")
    parser.add_argument("--seed", type=int, default=5800)
    return parser


def main(argv: Iterable[str] | None = None) -> int:
    args = build_arg_parser().parse_args(list(argv) if argv is not None else None)
    summary = prepare_package(
        base_package=args.base_package,
        output_root=args.output_root,
        package_name=args.package_name,
        base_limit=args.base_limit,
        anchor_count=args.anchor_count,
        image_size=args.image_size,
        correction_fraction=args.correction_fraction,
        link_mode=args.link_mode,
        seed=args.seed,
    )
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

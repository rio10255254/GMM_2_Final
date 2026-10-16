"""Prepare R55 source-style packages for the standard Lab trainer.

The R55 rebuild repairs unrealistic label style but does not create the
geometry sidecars expected by the R53/R55 boundary-aware training launcher.
This script adds the same boundary, centerline, and distance sidecars used by
the previous Lab experiments.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path

import cv2
import numpy as np


LAB_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_DATA_ROOT = LAB_ROOT / "Training_Data" / "r55_source_style_rebuild" / "r53_realistic_dataset_calibration"
DEFAULT_PACKAGES = (
    DEFAULT_DATA_ROOT / "r53_realistic_calibrated_train_6000",
    DEFAULT_DATA_ROOT / "r53_realistic_calibrated_val",
)


def _read_gray_image(path: Path) -> np.ndarray:
    data = np.fromfile(str(path), dtype=np.uint8)
    image = cv2.imdecode(data, cv2.IMREAD_GRAYSCALE)
    if image is None:
        raise RuntimeError(f"failed to read image: {path}")
    return image


def _write_image(path: Path, image: np.ndarray) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    ok, encoded = cv2.imencode(path.suffix, image)
    if not ok:
        raise RuntimeError(f"failed to encode image: {path}")
    path.write_bytes(encoded.tobytes())


def compute_geometry_from_label(img: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    gray = img
    if gray.ndim == 3:
        gray = cv2.cvtColor(gray, cv2.COLOR_BGR2GRAY)
    gray = gray.astype(np.uint8, copy=False)
    blur = cv2.GaussianBlur(gray, (0, 0), sigmaX=0.65)
    grad_x = cv2.Sobel(blur, cv2.CV_32F, 1, 0, ksize=3)
    grad_y = cv2.Sobel(blur, cv2.CV_32F, 0, 1, ksize=3)
    mag = cv2.magnitude(grad_x, grad_y)
    threshold = max(8.0, float(np.percentile(mag, 84.0)))
    centerline = (mag >= threshold).astype(np.uint8) * 255
    centerline = cv2.morphologyEx(centerline, cv2.MORPH_OPEN, np.ones((2, 2), np.uint8))
    if np.count_nonzero(centerline) == 0:
        centerline = cv2.Canny(gray, 40, 120)
    boundary = cv2.dilate(centerline, np.ones((3, 3), np.uint8), iterations=1)
    distance = cv2.distanceTransform((boundary == 0).astype(np.uint8), cv2.DIST_L2, 3).astype(np.float32)
    return boundary.astype(np.uint8), centerline.astype(np.uint8), distance


def _relative_label_path(record: dict, package_dir: Path) -> Path:
    package_lbl = record.get("package_lbl")
    if package_lbl:
        rel = Path(str(package_lbl).replace("\\", "/"))
        parts = rel.parts
        if parts and parts[0] == "lbl":
            return Path(*parts[1:])
        return rel

    lbl_path = Path(str(record["lbl"]))
    try:
        return lbl_path.relative_to(package_dir / "lbl")
    except ValueError as exc:
        raise RuntimeError(f"cannot infer label-relative path for {lbl_path}") from exc


def _package_label_path(record: dict, package_dir: Path) -> Path:
    package_lbl = record.get("package_lbl")
    if package_lbl:
        return package_dir / Path(str(package_lbl).replace("/", "\\"))
    lbl_path = Path(str(record["lbl"]))
    if lbl_path.is_absolute():
        return lbl_path
    return package_dir / lbl_path


def _write_geometry_sidecars(lbl_path: Path, geom_dir: Path, rel_path: Path) -> tuple[Path, Path, Path]:
    img = _read_gray_image(lbl_path)
    boundary, centerline, distance = compute_geometry_from_label(img)
    boundary_path = geom_dir / "boundary" / rel_path
    centerline_path = geom_dir / "centerline" / rel_path
    distance_path = geom_dir / "distance" / rel_path.with_suffix(".npy")
    _write_image(boundary_path, boundary)
    _write_image(centerline_path, centerline)
    distance_path.parent.mkdir(parents=True, exist_ok=True)
    np.save(distance_path, distance.astype(np.float32, copy=False))
    return boundary_path, centerline_path, distance_path


def prepare_package(package_dir: Path, *, force: bool = False, limit: int | None = None) -> dict:
    package_dir = package_dir.resolve()
    manifest_path = package_dir / "manifest.json"
    if not manifest_path.exists():
        raise FileNotFoundError(manifest_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    pairs = list(manifest.get("pairs", []))
    if not pairs:
        raise RuntimeError(f"manifest contains no pairs: {manifest_path}")

    total = len(pairs) if limit is None else min(int(limit), len(pairs))
    geom_dir = package_dir / "geom"
    written = 0
    skipped = 0
    missing = []

    for idx, record in enumerate(pairs[:total], start=1):
        rel_path = _relative_label_path(record, package_dir)
        lbl_path = _package_label_path(record, package_dir)
        if not lbl_path.exists():
            missing.append(str(lbl_path))
            continue

        boundary_rel = Path("geom") / "boundary" / rel_path
        centerline_rel = Path("geom") / "centerline" / rel_path
        distance_rel = Path("geom") / "distance" / rel_path.with_suffix(".npy")
        boundary_path = package_dir / boundary_rel
        centerline_path = package_dir / centerline_rel
        distance_path = package_dir / distance_rel

        if (
            not force
            and boundary_path.exists()
            and centerline_path.exists()
            and distance_path.exists()
        ):
            skipped += 1
        else:
            _write_geometry_sidecars(lbl_path, geom_dir, rel_path)
            written += 1

        record["geometry_boundary"] = boundary_rel.as_posix()
        record["geometry_centerline"] = centerline_rel.as_posix()
        record["geometry_distance"] = distance_rel.as_posix()

        if idx % 500 == 0:
            print(f"[R55][geometry] {package_dir.name}: {idx}/{total} ready")

    if missing:
        preview = "\n".join(missing[:10])
        raise RuntimeError(f"missing {len(missing)} label files; first entries:\n{preview}")

    if limit is None:
        manifest["pairs"] = pairs
        manifest["profile"] = manifest.get("profile") or package_dir.name
        manifest["geometry_sidecars"] = True
        manifest["geom_dir"] = str(geom_dir)
        manifest["geometry_count"] = int(len(pairs))
        manifest["geometry_generator"] = "prepare_r55_geometry_v1"
        manifest["geometry_generated_at"] = datetime.now().replace(microsecond=0).isoformat()
        manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")

    return {
        "package_dir": str(package_dir),
        "manifest": str(manifest_path),
        "total_pairs": int(len(pairs)),
        "processed_pairs": int(total),
        "written": int(written),
        "skipped_existing": int(skipped),
        "geometry_dir": str(geom_dir),
        "manifest_updated": limit is None,
    }


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Prepare geometry sidecars for R55 source-style packages")
    parser.add_argument("--package-dir", type=Path, action="append", default=None)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--limit", type=int, default=None)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    packages = tuple(args.package_dir) if args.package_dir else DEFAULT_PACKAGES
    summaries = []
    for package_dir in packages:
        summaries.append(prepare_package(package_dir, force=args.force, limit=args.limit))
    print(json.dumps({"packages": summaries}, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

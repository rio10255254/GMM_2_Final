#!/usr/bin/env python
"""Prepare the lab inner-circle ROI batch for the copied Whole-FOV fitter."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

import cv2
import numpy as np
PROJECT_ROOT = Path(__file__).resolve().parents[4]


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = ROOT / "configs" / "lab_optical_setup_20250605.json"


def load_optical_setup(path: str | Path = DEFAULT_CONFIG) -> dict:
    with Path(path).open("r", encoding="utf-8") as f:
        return json.load(f)


def effective_pixel_size_um(setup: dict) -> float:
    denominator = (
        float(setup["objective"]["magnification"])
        * float(setup["optical_path"]["relay_lens_magnification"])
        * float(setup["optical_path"]["tube_lens_magnification"])
    )
    numerator = (
        float(setup["camera"]["pixel_size_um"])
        * float(setup["acquisition"]["binning"])
        / float(setup["acquisition"]["software_scaling"])
    )
    return numerator / denominator


def target_diameter_px(setup: dict) -> float:
    return float(setup["target"]["nominal_diameter_um"]) / effective_pixel_size_um(setup)


def _resolve(path_text: str) -> Path:
    path = Path(path_text)
    if path.is_absolute():
        return path
    return ROOT / path


def _load_template(setup: dict) -> np.ndarray:
    path = _resolve(str(PROJECT_ROOT / setup["template"]["source_gt_path"]))
    img = cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)
    if img is None:
        raise FileNotFoundError(f"Unable to read source GT template: {path}")
    return img


def build_inner_circle_gt(setup: dict) -> np.ndarray:
    template = _load_template(setup)
    output_size = int(setup["outputs"]["gt_size_px"])
    source_diameter = float(setup["template"]["source_circle_diameter_px"])
    scale = target_diameter_px(setup) / source_diameter

    if template.shape != (output_size, output_size):
        template = cv2.resize(template, (output_size, output_size), interpolation=cv2.INTER_NEAREST)

    background = int(template.min())
    center = ((output_size - 1) / 2.0, (output_size - 1) / 2.0)
    matrix = cv2.getRotationMatrix2D(center, 0, scale)
    warped = cv2.warpAffine(
        template,
        matrix,
        (output_size, output_size),
        flags=cv2.INTER_NEAREST,
        borderValue=background,
    )

    threshold = (int(template.min()) + int(template.max())) / 2.0
    return np.where(warped > threshold, 255, 20).astype(np.uint8)


def load_detected_centers(setup: dict) -> list[dict]:
    csv_path = _resolve(setup["target"]["detected_inner_circle_csv"])
    rows: list[dict] = []
    with csv_path.open("r", encoding="ascii", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(
                {
                    "index": int(row["index"]),
                    "file": row["file"],
                    "x_px": float(row["x_px"]),
                    "y_px": float(row["y_px"]),
                    "r_px": float(row["r_px"]),
                }
            )
    if len(rows) != 25:
        raise ValueError(f"Expected 25 detected centers, found {len(rows)}")
    return rows


def _crop_centered_with_padding(img: np.ndarray, center_x: float, center_y: float, size: int, pad_value: int) -> np.ndarray:
    half = size // 2
    cx = int(round(center_x))
    cy = int(round(center_y))
    src_x0 = cx - half
    src_y0 = cy - half
    src_x1 = src_x0 + size
    src_y1 = src_y0 + size

    dst = np.full((size, size), pad_value, dtype=img.dtype)
    copy_x0 = max(src_x0, 0)
    copy_y0 = max(src_y0, 0)
    copy_x1 = min(src_x1, img.shape[1])
    copy_y1 = min(src_y1, img.shape[0])

    dst_x0 = copy_x0 - src_x0
    dst_y0 = copy_y0 - src_y0
    dst[
        dst_y0 : dst_y0 + (copy_y1 - copy_y0),
        dst_x0 : dst_x0 + (copy_x1 - copy_x0),
    ] = img[copy_y0:copy_y1, copy_x0:copy_x1]
    return dst


def prepare_roi_images(setup: dict) -> list[dict]:
    raw_dir = _resolve(setup["inputs"]["raw_dir"])
    output_dir = _resolve(setup["outputs"]["measured_roi_dir"])
    output_dir.mkdir(parents=True, exist_ok=True)
    size = int(setup["outputs"]["gt_size_px"])
    centers = load_detected_centers(setup)
    manifest_rows: list[dict] = []

    for row in centers:
        src_path = raw_dir / row["file"]
        img = cv2.imread(str(src_path), cv2.IMREAD_GRAYSCALE)
        if img is None:
            raise FileNotFoundError(f"Unable to read lab image: {src_path}")
        pad_value = int(np.percentile(img, 5))
        roi = _crop_centered_with_padding(img, row["x_px"], row["y_px"], size, pad_value)
        dst_name = f"VisionTop_LabSystem_20260605_inner_circle_{row['index']:02d}.bmp"
        dst_path = output_dir / dst_name
        cv2.imwrite(str(dst_path), roi)
        manifest_rows.append(
            {
                "index": row["index"],
                "source_file": row["file"],
                "roi_file": dst_name,
                "center_x_px": row["x_px"],
                "center_y_px": row["y_px"],
                "detected_radius_px": row["r_px"],
            }
        )
    return manifest_rows


def write_overlay_contact(setup: dict, manifest_rows: list[dict]) -> None:
    measured_dir = _resolve(setup["outputs"]["measured_roi_dir"])
    output_path = _resolve(setup["outputs"]["overlay_contact_path"])
    output_path.parent.mkdir(parents=True, exist_ok=True)
    size = int(setup["outputs"]["gt_size_px"])
    radius = int(round(target_diameter_px(setup) / 2.0))
    center = (size // 2, size // 2)
    thumbs = []

    for row in manifest_rows:
        img = cv2.imread(str(measured_dir / row["roi_file"]), cv2.IMREAD_GRAYSCALE)
        rgb = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
        cv2.circle(rgb, center, radius, (0, 0, 255), 3)
        cv2.putText(
            rgb,
            f"{row['index']:02d}",
            (18, 52),
            cv2.FONT_HERSHEY_SIMPLEX,
            1.4,
            (0, 0, 255),
            3,
            cv2.LINE_AA,
        )
        thumbs.append(cv2.resize(rgb, (270, 270), interpolation=cv2.INTER_AREA))

    sheet = np.vstack([np.hstack(thumbs[i * 5 : (i + 1) * 5]) for i in range(5)])
    cv2.imwrite(str(output_path), sheet)


def write_manifest(setup: dict, manifest_rows: list[dict]) -> None:
    manifest_path = _resolve(setup["outputs"]["manifest_path"])
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest = {
        "run_id": setup["run_id"],
        "effective_pixel_size_um": effective_pixel_size_um(setup),
        "target_diameter_px": target_diameter_px(setup),
        "gt_path": setup["outputs"]["gt_path"],
        "measured_roi_dir": setup["outputs"]["measured_roi_dir"],
        "image_count": len(manifest_rows),
        "rows": manifest_rows,
    }
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")


def prepare(config_path: str | Path = DEFAULT_CONFIG) -> dict:
    setup = load_optical_setup(config_path)
    gt = build_inner_circle_gt(setup)
    gt_path = _resolve(setup["outputs"]["gt_path"])
    gt_path.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(gt_path), gt)
    manifest_rows = prepare_roi_images(setup)
    write_overlay_contact(setup, manifest_rows)
    write_manifest(setup, manifest_rows)
    return {
        "gt_path": str(gt_path),
        "measured_roi_dir": str(_resolve(setup["outputs"]["measured_roi_dir"])),
        "overlay_contact_path": str(_resolve(setup["outputs"]["overlay_contact_path"])),
        "image_count": len(manifest_rows),
        "effective_pixel_size_um": effective_pixel_size_um(setup),
        "target_diameter_px": target_diameter_px(setup),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default=str(DEFAULT_CONFIG))
    args = parser.parse_args()
    result = prepare(args.config)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()

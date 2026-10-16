from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

import cv2
import numpy as np


EXPERIMENT = Path(__file__).resolve().parent
MANIFEST_PATH = EXPERIMENT / "evaluation_manifest.json"
STATIC_SEQUENCES = {"50x": "50x_x_0p5um", "20x": "20x_0p5um"}
LINE_ROIS = {
    "vertical_lines": (100, 90, 700, 560),
    "horizontal_lines": (1050, 850, 700, 560),
}


def read_gray(path: Path) -> np.ndarray:
    image = cv2.imdecode(np.fromfile(path, dtype=np.uint8), cv2.IMREAD_GRAYSCALE)
    if image is None:
        raise FileNotFoundError(path)
    return image


def write_png(path: Path, image: np.ndarray) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    success, encoded = cv2.imencode(".png", image)
    if not success:
        raise RuntimeError(f"Could not encode {path}")
    encoded.tofile(str(path))


def method_directory(
    manifest: dict[str, Any],
    method: str,
    sequence_name: str,
    raw_dir: Path,
) -> Path:
    if method == "Raw":
        return raw_dir
    root = Path(manifest["methods"][method]["sequence_root"])
    mapped = manifest["sequence_name_map"][sequence_name][method]
    return root / mapped


def tight_bounds(
    centers: list[tuple[float, float]],
    pitch_px: float,
    image_shape: tuple[int, int],
) -> tuple[int, int, int, int]:
    xs = np.asarray([center[0] for center in centers])
    ys = np.asarray([center[1] for center in centers])
    margin = int(round(pitch_px * 0.48))
    x0 = max(0, int(np.floor(xs.min())) - margin)
    x1 = min(image_shape[1], int(np.ceil(xs.max())) + margin + 1)
    y0 = max(0, int(np.floor(ys.min())) - margin)
    y1 = min(image_shape[0], int(np.ceil(ys.max())) + margin + 1)
    return x0, y0, x1 - x0, y1 - y0


def add_scale_bar(
    crop: np.ndarray,
    um_per_px: float,
    magnification: str,
) -> np.ndarray:
    canvas = cv2.cvtColor(crop, cv2.COLOR_GRAY2BGR)
    maximum_length = int(canvas.shape[1] * 0.55)
    candidates = (20.0, 10.0, 5.0, 2.0, 1.0)
    bar_um = next(
        value for value in candidates if int(round(value / um_per_px)) <= maximum_length
    )
    length = int(round(bar_um / um_per_px))
    margin = max(8, int(round(canvas.shape[0] * 0.045)))
    y = canvas.shape[0] - margin
    x1 = canvas.shape[1] - margin
    x0 = x1 - length
    cv2.line(canvas, (x0, y), (x1, y), (0, 0, 0), 7, cv2.LINE_AA)
    cv2.line(canvas, (x0, y), (x1, y), (255, 255, 255), 3, cv2.LINE_AA)
    label = f"{bar_um:g} um"
    cv2.putText(
        canvas,
        label,
        (x0, y - 9),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.42,
        (0, 0, 0),
        3,
        cv2.LINE_AA,
    )
    cv2.putText(
        canvas,
        label,
        (x0, y - 9),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.42,
        (255, 255, 255),
        1,
        cv2.LINE_AA,
    )
    return canvas


def main(output_root: Path, allow_missing: bool) -> None:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    pillar_config = json.loads(Path(manifest["pillar_config"]).read_text(encoding="utf-8"))
    via_config = json.loads(Path(manifest["via_config"]).read_text(encoding="utf-8"))
    rows: list[dict[str, object]] = []
    for magnification, sequence_name in STATIC_SEQUENCES.items():
        pillar_sequence = pillar_config["sequences"][sequence_name]
        via_sequence = via_config["sequences"][sequence_name]
        raw_dir = Path(pillar_sequence["raw_dir"])
        first_frame = str(pillar_sequence["first_frame"])
        sample = read_gray(raw_dir / first_frame)
        circular_bounds = {
            "pillar": tight_bounds(
                [(float(row[1]), float(row[2])) for row in pillar_sequence["centers"]],
                float(pillar_sequence["pitch_px"]),
                sample.shape,
            ),
            "via": tight_bounds(
                [(float(row["x"]), float(row["y"])) for row in via_sequence["centers"]],
                float(via_sequence["pitch_px"]),
                sample.shape,
            ),
        }
        regions = dict(circular_bounds)
        if magnification == "50x":
            regions.update(LINE_ROIS)
        for method in manifest["methods"]:
            directory = method_directory(
                manifest,
                method,
                sequence_name,
                raw_dir,
            )
            image_path = directory / first_frame
            if not image_path.is_file():
                if allow_missing:
                    print(f"Skipping {method} {magnification}: {image_path}", flush=True)
                    continue
                raise FileNotFoundError(image_path)
            image = read_gray(image_path)
            if image.shape != sample.shape:
                raise RuntimeError(f"Image shape mismatch for {method} {magnification}")
            safe_method = method.lower().replace(" ", "_").replace("-", "_")
            for region_name, (x, y, width, height) in regions.items():
                crop = image[y : y + height, x : x + width]
                native_path = output_root / f"{magnification}_{region_name}_{safe_method}_native.png"
                scale_path = output_root / f"{magnification}_{region_name}_{safe_method}_scale_bar.png"
                write_png(native_path, crop)
                write_png(
                    scale_path,
                    add_scale_bar(
                        crop,
                        float(pillar_sequence["object_um_per_px"]),
                        magnification,
                    ),
                )
                rows.append(
                    {
                        "magnification": magnification,
                        "region": region_name,
                        "method": method,
                        "source": str(image_path),
                        "output_native": str(native_path),
                        "output_scale_bar": str(scale_path),
                        "x": x,
                        "y": y,
                        "width": width,
                        "height": height,
                        "native_min": int(crop.min()),
                        "native_max": int(crop.max()),
                        "native_mean": float(crop.mean()),
                        "native_std": float(crop.std(ddof=1)),
                        "clipped_low_percent": float(np.mean(crop <= 1) * 100.0),
                        "clipped_high_percent": float(np.mean(crop >= 254) * 100.0),
                    }
                )
    output_root.mkdir(parents=True, exist_ok=True)
    with (output_root / "crop_manifest.csv").open(
        "w", newline="", encoding="utf-8-sig"
    ) as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    metadata = {
        "purpose": "Native-intensity single-image comparison crops",
        "display_rule": "All methods retain their native 8-bit values; no per-image contrast stretching",
        "crop_rule": "The same Raw-defined coordinates and dimensions are used for every method",
        "scale_bar_rule": "Scale bars use the calibrated object-space sampling for each magnification",
    }
    (output_root / "metadata.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"Exported {len(rows)} native comparison crops", flush=True)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output-root",
        type=Path,
        default=EXPERIMENT / "evaluation" / "images",
    )
    parser.add_argument("--allow-missing", action="store_true")
    return parser.parse_args()


if __name__ == "__main__":
    arguments = parse_args()
    main(arguments.output_root.resolve(), arguments.allow_missing)

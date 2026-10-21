from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path

import cv2
import numpy as np


ROOT = Path(__file__).resolve().parent
DESIGN_PATH = ROOT / "predeclared_design.json"
PILLAR_CONFIG = Path(
    r"D:\GMM_2_Final\Thesis_MOSR_Evidence\Final_Data_Figures"
    r"\01_CURRENT_THESIS_RESULTS_V42_CENTER9\config\sequence_center9_50x20x.json"
)
VIA_CONFIG = Path(
    r"D:\GMM_2_Final\Thesis_MOSR_Evidence\LabSystem_MOSR\Experiments"
    r"\Modern_Restoration_Benchmarks_20260719\evaluation\via_reference"
    r"\via_center9_reference.json"
)


def read_gray_u8(path: Path) -> np.ndarray:
    data = np.fromfile(str(path), dtype=np.uint8)
    image = cv2.imdecode(data, cv2.IMREAD_GRAYSCALE)
    if image is None:
        raise RuntimeError(f"Could not read image: {path}")
    if image.dtype != np.uint8:
        raise RuntimeError(f"Expected uint8 source, got {image.dtype}: {path}")
    return image


def write_gray(path: Path, image: np.ndarray) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    ok, encoded = cv2.imencode(path.suffix or ".bmp", image)
    if not ok:
        raise RuntimeError(f"Could not encode image: {path}")
    encoded.tofile(str(path))


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def shift_code(value: float) -> str:
    if abs(value) < 1.0e-12:
        return "z0p00"
    prefix = "p" if value > 0 else "m"
    return prefix + f"{abs(value):.2f}".replace(".", "p")


def translate_lanczos(image_u16: np.ndarray, dx: float, dy: float) -> np.ndarray:
    image = image_u16.astype(np.float32) / 65535.0
    matrix = np.asarray([[1.0, 0.0, float(dx)], [0.0, 1.0, float(dy)]], dtype=np.float32)
    shifted = cv2.warpAffine(
        image,
        matrix,
        (image.shape[1], image.shape[0]),
        flags=cv2.INTER_LANCZOS4,
        borderMode=cv2.BORDER_REFLECT_101,
    )
    return np.clip(np.rint(np.clip(shifted, 0.0, 1.0) * 65535.0), 0, 65535).astype(np.uint16)


def resolve_source(case: dict, pillar_sequences: dict) -> Path:
    sequence = pillar_sequences[case["source_sequence"]]
    return Path(sequence["raw_dir"]) / case["source_frame"]


def feature_metadata(case: dict, pillar_sequences: dict, via_sequences: dict) -> dict:
    x0, y0, _, _ = [int(value) for value in case["crop_xywh"]]
    morphology = case["morphology"]
    if morphology == "pillar":
        sequence = pillar_sequences[case["source_sequence"]]
        centers = [
            {
                "feature_id": str(item[0]),
                "x": float(item[1]) - x0,
                "y": float(item[2]) - y0,
            }
            for item in sequence["centers"]
        ]
        return {
            "polarity": str(sequence["polarity"]),
            "radius_px": float(sequence["radius_px"]),
            "pitch_px": float(sequence["pitch_px"]),
            "search_radius_px": float(sequence["search_radius_px"]),
            "min_edge_strength": float(sequence["min_edge_strength"]),
            "centers": centers,
        }
    if morphology == "via":
        sequence = via_sequences[case["source_sequence"]]
        centers = [
            {
                "feature_id": str(item["sem_cell"]),
                "x": float(item["x"]) - x0,
                "y": float(item["y"]) - y0,
            }
            for item in sequence["centers"]
        ]
        return {
            "polarity": str(sequence["polarity"]),
            "radius_px": float(sequence["radius_px"]),
            "pitch_px": float(sequence["pitch_px"]),
            "search_radius_px": float(sequence["search_radius_px"]),
            "min_edge_strength": 2.0,
            "centers": centers,
        }
    return {
        "measured_shift_axis": str(case["measured_shift_axis"]),
        "minimum_valid_edges": 10,
    }


def operator_qa(output_path: Path, shifts: list[float]) -> list[dict[str, float | str]]:
    yy, xx = np.mgrid[:512, :512]
    baseline = 20.0 / 255.0
    phantom_float = baseline + (220.0 / 255.0) * np.exp(
        -((xx - 256.37) ** 2 + (yy - 255.63) ** 2) / (2.0 * 18.0**2)
    )
    phantom = np.rint(np.clip(phantom_float, 0.0, 1.0) * 65535.0).astype(np.uint16)

    def centroid(image: np.ndarray) -> tuple[float, float]:
        weights = np.clip(image.astype(np.float64) / 65535.0 - baseline, 0.0, None)
        total = float(weights.sum())
        return float((weights * xx).sum() / total), float((weights * yy).sum() / total)

    reference_centroid = centroid(phantom)
    records: list[dict[str, float | str]] = []
    for axis in ("x", "y"):
        for value in shifts:
            if abs(value) < 1.0e-12:
                continue
            dx = value if axis == "x" else 0.0
            dy = value if axis == "y" else 0.0
            shifted = translate_lanczos(phantom, dx, dy)
            measured_centroid = centroid(shifted)
            measured = (
                measured_centroid[0] - reference_centroid[0],
                measured_centroid[1] - reference_centroid[1],
            )
            records.append(
                {
                    "axis": axis,
                    "imposed_shift_px": value,
                    "measured_dx_px": float(measured[0]),
                    "measured_dy_px": float(measured[1]),
                    "commanded_axis_error_px": float(
                        (measured[0] - dx) if axis == "x" else (measured[1] - dy)
                    ),
                    "cross_axis_error_px": float(measured[1] if axis == "x" else measured[0]),
                    "centroid_qa": 1.0,
                }
            )
    with output_path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(records[0]))
        writer.writeheader()
        writer.writerows(records)
    max_commanded = max(abs(float(row["commanded_axis_error_px"])) for row in records)
    max_cross = max(abs(float(row["cross_axis_error_px"])) for row in records)
    if max_commanded > 0.02 or max_cross > 0.002:
        raise RuntimeError(
            f"Shift-operator QA failed: commanded={max_commanded:.5f}, cross={max_cross:.5f} px"
        )
    return records


def main(root: Path) -> None:
    design = json.loads(DESIGN_PATH.read_text(encoding="utf-8"))
    if not bool(design.get("locked_before_inference")):
        raise RuntimeError("Experiment design is not locked")
    pillar_sequences = json.loads(PILLAR_CONFIG.read_text(encoding="utf-8"))["sequences"]
    via_sequences = json.loads(VIA_CONFIG.read_text(encoding="utf-8"))["sequences"]
    input_dir = root / "inputs" / "shifted"
    qa_dir = root / "qa"
    input_dir.mkdir(parents=True, exist_ok=True)
    qa_dir.mkdir(parents=True, exist_ok=True)

    shifts = [float(value) for value in design["imposed_shifts_px"]]
    operator_rows = operator_qa(qa_dir / "shift_operator_qa.csv", shifts)
    records: list[dict[str, object]] = []
    case_records: list[dict[str, object]] = []
    expected_names: set[str] = set()

    for case in design["cases"]:
        source_path = resolve_source(case, pillar_sequences)
        source = read_gray_u8(source_path)
        x0, y0, width, height = [int(value) for value in case["crop_xywh"]]
        if width != int(design["crop_size_px"]) or height != int(design["crop_size_px"]):
            raise RuntimeError(f"Unexpected crop size for {case['case_id']}")
        if x0 < 0 or y0 < 0 or x0 + width > source.shape[1] or y0 + height > source.shape[0]:
            raise RuntimeError(f"Crop outside source for {case['case_id']}")
        crop_u8 = source[y0 : y0 + height, x0 : x0 + width].copy()
        crop = (crop_u8.astype(np.uint16) * np.uint16(257)).astype(np.uint16)
        metadata = feature_metadata(case, pillar_sequences, via_sequences)
        for center in metadata.get("centers", []):
            margin = float(metadata["radius_px"]) + 12.0
            if not (
                margin <= float(center["x"]) <= width - 1 - margin
                and margin <= float(center["y"]) <= height - 1 - margin
            ):
                raise RuntimeError(
                    f"Feature {center['feature_id']} in {case['case_id']} lacks the locked analysis margin"
                )

        case_records.append(
            {
                **case,
                "source_path": str(source_path),
                "source_sha256": sha256_file(source_path),
                "source_shape": [int(source.shape[0]), int(source.shape[1])],
                "crop_min_8bit": int(crop_u8.min()),
                "crop_max_8bit": int(crop_u8.max()),
                "crop_mean_8bit": float(crop_u8.mean()),
                "crop_std_8bit": float(crop_u8.std()),
                "measurement": metadata,
            }
        )

        reference_name = f"{case['case_id']}__ref.png"
        write_gray(input_dir / reference_name, crop)
        expected_names.add(reference_name)
        records.append(
            {
                "case_id": case["case_id"],
                "magnification": case["magnification"],
                "morphology": case["morphology"],
                "axis": "reference",
                "shift_px": 0.0,
                "dx_px": 0.0,
                "dy_px": 0.0,
                "object_um_per_px": float(case["object_um_per_px"]),
                "filename": reference_name,
                "source_path": str(source_path),
                "crop_x": x0,
                "crop_y": y0,
                "crop_width": width,
                "crop_height": height,
            }
        )
        for axis in ("x", "y"):
            for value in shifts:
                if abs(value) < 1.0e-12:
                    continue
                dx = value if axis == "x" else 0.0
                dy = value if axis == "y" else 0.0
                filename = f"{case['case_id']}__{axis}_{shift_code(value)}.png"
                write_gray(input_dir / filename, translate_lanczos(crop, dx, dy))
                expected_names.add(filename)
                records.append(
                    {
                        "case_id": case["case_id"],
                        "magnification": case["magnification"],
                        "morphology": case["morphology"],
                        "axis": axis,
                        "shift_px": value,
                        "dx_px": dx,
                        "dy_px": dy,
                        "object_um_per_px": float(case["object_um_per_px"]),
                        "filename": filename,
                        "source_path": str(source_path),
                        "crop_x": x0,
                        "crop_y": y0,
                        "crop_width": width,
                        "crop_height": height,
                    }
                )

    actual_names = {path.name for path in input_dir.glob("*.png")}
    extras = sorted(actual_names - expected_names)
    missing = sorted(expected_names - actual_names)
    if extras or missing:
        raise RuntimeError(f"Input-folder mismatch: extras={extras}, missing={missing}")

    manifest_csv = root / "inputs" / "input_manifest.csv"
    with manifest_csv.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(records[0]))
        writer.writeheader()
        writer.writerows(records)
    payload = {
        "design": str(DESIGN_PATH),
        "design_sha256": sha256_file(DESIGN_PATH),
        "input_directory": str(input_dir),
        "input_count": len(records),
        "case_count": len(case_records),
        "cases": case_records,
        "shift_operator_qa": {
            "row_count": len(operator_rows),
            "max_commanded_axis_error_px": max(
                abs(float(row["commanded_axis_error_px"])) for row in operator_rows
            ),
            "max_cross_axis_error_px": max(
                abs(float(row["cross_axis_error_px"])) for row in operator_rows
            ),
        },
    }
    (root / "inputs" / "input_manifest.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(payload["shift_operator_qa"], indent=2))
    print(f"Prepared {len(records)} inputs across {len(case_records)} locked real-image cases")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=ROOT)
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    main(args.root.resolve())

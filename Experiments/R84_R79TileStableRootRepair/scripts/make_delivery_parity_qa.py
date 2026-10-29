from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np
PROJECT_ROOT = Path(__file__).resolve().parents[3]


ROOT = Path(str(PROJECT_ROOT / 'Experiments/R84_R79TileStableRootRepair/results/delivery_root_fix'))
OUTPUT = ROOT / "delivery_parity_visual_qa.png"
CELL = 420
CAPTION = 44


CASES = [
    (
        "Package example 512x512",
        Path(str(PROJECT_ROOT / 'Deliverables/MOSR_ONNX/example/input.bmp')),
        ROOT / "smoke_example_fixed" / "input.bmp",
        ROOT / "pytorch_reference_example" / "input.bmp",
    ),
    (
        "Customer image 1520x2180",
        Path(str(PROJECT_ROOT / 'Shared_Sources/NTU_Originals/Pitch1um_Y_100/Cropped_Output/VisionTop_20251029182653732.bmp')),
        ROOT / "real_max_2180x1520" / "VisionTop_20251029182653732.bmp",
        ROOT / "pytorch_reference_max" / "VisionTop_20251029182653732.bmp",
    ),
    (
        "SEM P-01 1024x788",
        Path(str(PROJECT_ROOT / 'Shared_Sources/SEM_Originals/P-01.tiff')),
        ROOT / "sem_raw" / "P-01.bmp",
        ROOT / "pytorch_reference_sem" / "P-01.bmp",
    ),
]


def read_gray(path: Path) -> np.ndarray:
    image = cv2.imdecode(np.fromfile(path, dtype=np.uint8), cv2.IMREAD_GRAYSCALE)
    if image is None:
        raise OSError(path)
    return image


def fit(image: np.ndarray) -> np.ndarray:
    height, width = image.shape
    scale = min(CELL / width, CELL / height)
    resized = cv2.resize(
        image,
        (max(1, round(width * scale)), max(1, round(height * scale))),
        interpolation=cv2.INTER_AREA,
    )
    canvas = np.full((CELL, CELL), 18, dtype=np.uint8)
    top = (CELL - resized.shape[0]) // 2
    left = (CELL - resized.shape[1]) // 2
    canvas[top : top + resized.shape[0], left : left + resized.shape[1]] = resized
    return cv2.cvtColor(canvas, cv2.COLOR_GRAY2BGR)


def main() -> int:
    headers = ["Raw", "ONNX full frame", "PyTorch R79", "Absolute diff x255"]
    rows = []
    for case_name, raw_path, onnx_path, torch_path in CASES:
        raw = read_gray(raw_path)
        onnx = read_gray(onnx_path)
        torch = read_gray(torch_path)
        if raw.shape != onnx.shape or raw.shape != torch.shape:
            raise RuntimeError(f"Shape mismatch: {case_name}")
        diff = np.abs(onnx.astype(np.int16) - torch.astype(np.int16)).astype(np.uint8) * 255
        cells = [fit(raw), fit(onnx), fit(torch), fit(diff)]
        row = np.full((CELL + CAPTION, CELL * 4, 3), 245, dtype=np.uint8)
        for index, cell in enumerate(cells):
            row[:CELL, index * CELL : (index + 1) * CELL] = cell
            cv2.putText(
                row,
                headers[index],
                (index * CELL + 10, CELL + 29),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.66,
                (20, 20, 20),
                1,
                cv2.LINE_AA,
            )
        cv2.putText(row, case_name, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.76, (0, 80, 230), 2, cv2.LINE_AA)
        rows.append(row)
    image = np.vstack(rows)
    ok, encoded = cv2.imencode(".png", image)
    if not ok:
        raise OSError(OUTPUT)
    encoded.tofile(OUTPUT)
    print(OUTPUT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Make an original-scale visual comparison for the x_1um reconstruction arms."""
from pathlib import Path

import cv2
import numpy as np


ROOT = Path(__file__).resolve().parents[1]
RESULT = ROOT / "results" / "x1um_counterfactual_reconstruction"
ARMS = (
    ("00_raw", "Raw"),
    ("01_r96", "R96 E44"),
    ("02_detail_gate_open", "Detail gate open"),
    ("03_all_gate_open", "All gates open"),
    ("04_phase_safe_detail", "Phase-safe detail"),
)


def read(path: Path) -> np.ndarray:
    value = cv2.imdecode(np.fromfile(path, np.uint8), cv2.IMREAD_GRAYSCALE)
    if value is None:
        raise RuntimeError(path)
    return value


def label(image: np.ndarray, title: str) -> np.ndarray:
    panel = cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)
    cv2.rectangle(panel, (0, 0), (panel.shape[1], 40), (255, 255, 255), -1)
    cv2.putText(panel, title, (10, 29), cv2.FONT_HERSHEY_SIMPLEX, .65, (0, 0, 0), 2, cv2.LINE_AA)
    return panel


def main() -> None:
    frame = 25
    # One pillar field and one line/defect field, kept at one source pixel per output pixel.
    crops = ((900, 40, 1320, 400), (900, 760, 1320, 1120))
    rows = []
    for crop_index, (x0, y0, x1, y1) in enumerate(crops):
        panels = []
        for arm, title in ARMS:
            image = read(RESULT / arm / f"frame_{frame:04d}.bmp")
            crop = image[y0:y1, x0:x1]
            panels.append(label(crop, title if crop_index == 0 else title))
        rows.append(np.hstack(panels))
    sheet = np.vstack(rows)
    target = RESULT / "preview" / f"frame_{frame:04d}_zoom_1to1.png"
    encoded, buffer = cv2.imencode(".png", sheet)
    if not encoded:
        raise RuntimeError(target)
    buffer.tofile(target)
    if not target.is_file() or target.stat().st_size == 0:
        raise RuntimeError(target)
    print(target)


if __name__ == "__main__":
    main()

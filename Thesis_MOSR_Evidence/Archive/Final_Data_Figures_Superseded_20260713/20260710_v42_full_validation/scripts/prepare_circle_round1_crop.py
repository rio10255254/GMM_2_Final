from __future__ import annotations

import json
from pathlib import Path

import cv2
PROJECT_ROOT = Path(__file__).resolve().parents[5]


ROOT = Path(str(PROJECT_ROOT / 'Thesis_MOSR_Evidence/Final_Data_Figures/20260710_v42_full_validation/circle_round1'))
SOURCE = ROOT / "inputs_first50"
OUTPUT = ROOT / "inputs_first50_crop2048"
CROP_XYWH = (0, 0, 2048, 2048)


def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    files = sorted(SOURCE.glob("*.bmp"))
    if len(files) != 50:
        raise RuntimeError(f"Expected 50 source frames, found {len(files)}")
    x, y, w, h = CROP_XYWH
    records = []
    for path in files:
        image = cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)
        if image is None or image.shape[0] < y + h or image.shape[1] < x + w:
            raise RuntimeError(f"Cannot crop {path}")
        crop = image[y:y + h, x:x + w]
        if not cv2.imwrite(str(OUTPUT / path.name), crop):
            raise RuntimeError(f"Cannot write {path.name}")
        records.append({"file": path.name, "source_shape": list(image.shape), "crop_shape": list(crop.shape)})
    (ROOT / "crop_manifest.json").write_text(json.dumps({
        "selection": "first 50 filename-sorted Circle_Round1 captures",
        "crop_xywh": list(CROP_XYWH),
        "resizing": False,
        "records": records,
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Prepared {len(records)} fixed 2048x2048 crops")


if __name__ == "__main__":
    main()

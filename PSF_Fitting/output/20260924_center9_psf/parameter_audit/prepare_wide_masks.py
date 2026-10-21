"""Split the widened real-image loss region without changing pillar IDs."""

from __future__ import annotations

import json
from pathlib import Path

import cv2
import numpy as np


ROOT = Path(__file__).resolve().parent
WIDE = ROOT / "wide_input"
SPLITS = {"A": [0, 4, 8], "B": [2, 3, 7]}
IDS = [36, 35, 34, 30, 29, 28, 24, 23, 22]


def main():
    full = cv2.imread(str(WIDE / "loss_mask.bmp"), 0) > 0
    yy, xx = np.ogrid[:301, :301]
    summary = {}
    for name, heldout in SPLITS.items():
        train = np.zeros_like(full)
        hold = np.zeros_like(full)
        for index in range(9):
            row, col = divmod(index, 3)
            x, y = [69, 150, 231][col], [69, 150, 231][row]
            disk = (xx - x)**2 + (yy - y)**2 <= 12**2
            (hold if index in heldout else train)[disk] = full[disk]
        assert np.array_equal(train | hold, full)
        assert not np.any(train & hold)
        assert cv2.imwrite(str(WIDE / f"loss_mask_train6_{name}.bmp"), train.astype(np.uint8) * 255)
        assert cv2.imwrite(str(WIDE / f"loss_mask_hold3_{name}.bmp"), hold.astype(np.uint8) * 255)
        summary[name] = {"heldout_ids": [IDS[i] for i in heldout], "train_pixels": int(train.sum()),
                         "heldout_pixels": int(hold.sum())}
    (ROOT / "wide_mask_manifest.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()

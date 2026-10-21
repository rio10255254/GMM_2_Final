"""Reserve new pillars and view positions for confirmation after tuning."""

from __future__ import annotations

import json
from pathlib import Path

import cv2
import numpy as np


ROOT = Path(__file__).resolve().parent
INPUT = ROOT.parent / "fit_input"
IDS = [36, 35, 34, 30, 29, 28, 24, 23, 22]
HELDOUT = [2, 3, 7]  # SEM 34, 30, 23; not used as held-out pillars in tuning
FRAMES = [4, 7, 12, 18, 23]  # disjoint from tuned frames 1, 13, 25


def main():
    original = cv2.imread(str(INPUT / "loss_mask.bmp"), 0) > 0
    train = np.zeros_like(original)
    hold = np.zeros_like(original)
    yy, xx = np.ogrid[:301, :301]
    for index in range(9):
        row, col = divmod(index, 3)
        x, y = [69, 150, 231][col], [69, 150, 231][row]
        region = (xx - x)**2 + (yy - y)**2 <= 100
        (hold if index in HELDOUT else train)[region] = original[region]
    assert np.array_equal(train | hold, original)
    assert not np.any(train & hold)
    assert train.sum() == 6 * 317 and hold.sum() == 3 * 317
    assert cv2.imwrite(str(INPUT / "loss_mask_train6_B.bmp"), train.astype(np.uint8) * 255)
    assert cv2.imwrite(str(INPUT / "loss_mask_hold3_B.bmp"), hold.astype(np.uint8) * 255)
    payload = {
        "selection_frozen_before_confirmation": True,
        "confirmation_frames": FRAMES,
        "heldout_sem_ids": [IDS[i] for i in HELDOUT],
        "training_sem_ids": [IDS[i] for i in range(9) if i not in HELDOUT],
        "train_pixels": int(train.sum()),
        "holdout_pixels": int(hold.sum()),
    }
    (ROOT / "confirmation_split.json").write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()

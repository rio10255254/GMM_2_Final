"""Freeze untouched confirmation views and pillar identities before model search."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import cv2
import numpy as np


ROOT = Path(__file__).resolve().parent
RUN = ROOT.parent
IDS = [36, 35, 34, 30, 29, 28, 24, 23, 22]
FOLDS = {
    "A_development": {"frames": [1, 13, 25], "heldout_ids": [36, 29, 22]},
    "B_development": {"frames": [4, 7, 12, 18, 23], "heldout_ids": [34, 30, 23]},
    "C_frozen_confirmation": {"frames": [3, 8, 14, 20, 22], "heldout_ids": [35, 28, 24]},
}


def main():
    ROOT.mkdir(parents=True, exist_ok=True)
    original = cv2.imread(str(RUN / "fit_input" / "loss_mask.bmp"), 0) > 0
    yy, xx = np.ogrid[:301, :301]
    frozen = {}
    for name, fold in FOLDS.items():
        hold = np.zeros_like(original)
        train = np.zeros_like(original)
        for i, pillar_id in enumerate(IDS):
            row, col = divmod(i, 3)
            x, y = [69, 150, 231][col], [69, 150, 231][row]
            circle = (xx - x)**2 + (yy - y)**2 <= 100
            (hold if pillar_id in fold["heldout_ids"] else train)[circle] = original[circle]
        assert np.array_equal(train | hold, original)
        assert not np.any(train & hold)
        assert train.sum() == 6 * 317 and hold.sum() == 3 * 317
        if name == "C_frozen_confirmation":
            assert cv2.imwrite(str(ROOT / "loss_mask_train6_C.bmp"), train.astype(np.uint8) * 255)
            assert cv2.imwrite(str(ROOT / "loss_mask_hold3_C.bmp"), hold.astype(np.uint8) * 255)
        frozen[name] = {**fold, "train_ids": [i for i in IDS if i not in fold["heldout_ids"]],
                        "training_pixel_count": int(train.sum()), "heldout_pixel_count": int(hold.sum())}
    assert len(set(FOLDS["A_development"]["frames"] + FOLDS["B_development"]["frames"] +
                   FOLDS["C_frozen_confirmation"]["frames"])) == 13
    assert len(set(sum([v["heldout_ids"] for v in FOLDS.values()], []))) == 9
    text = json.dumps({"frozen_before_model_selection": True, "folds": frozen}, indent=2) + "\n"
    (ROOT / "frozen_folds.json").write_text(text, encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()

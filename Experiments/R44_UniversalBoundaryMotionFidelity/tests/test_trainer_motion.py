from pathlib import Path
import sys

import cv2
import numpy as np
import torch


REPO_ROOT = Path(__file__).resolve().parents[3]
MODEL_DIR = REPO_ROOT / "Model"
if str(MODEL_DIR) not in sys.path:
    sys.path.insert(0, str(MODEL_DIR))


def _write_motion_pair(root: Path) -> None:
    stage = "stage_41_motion_lines"
    for frame, dx in [(0, 0.0), (1, 2.0)]:
        rel = Path(stage) / f"0000_seq0000_f{frame:02d}.bmp"
        src_path = root / "src" / rel
        lbl_path = root / "lbl" / rel
        boundary_path = root / "geom" / "boundary" / rel
        center_path = root / "geom" / "centerline" / rel
        distance_path = root / "geom" / "distance" / rel.with_suffix(".npy")
        meta_path = root / "geom" / "meta" / rel.with_suffix(".json")
        for p in (src_path, lbl_path, boundary_path, center_path, distance_path, meta_path):
            p.parent.mkdir(parents=True, exist_ok=True)
        img = np.zeros((32, 32), dtype=np.uint8)
        x0 = 10 + int(dx)
        img[:, x0:x0 + 2] = 255
        cv2.imwrite(str(src_path), img)
        cv2.imwrite(str(lbl_path), img)
        cv2.imwrite(str(boundary_path), img)
        cv2.imwrite(str(center_path), img)
        np.save(distance_path, np.ones((32, 32), dtype=np.float32))
        meta_path.write_text(
            (
                "{"
                f"\"sequence_id\": 0, \"frame_index\": {frame}, "
                f"\"delta_from_prev_px\": {{\"dx\": {dx if frame else 0.0}, \"dy\": 0.0}}, "
                f"\"cumulative_shift_px\": {{\"dx\": {dx}, \"dy\": 0.0}}, "
                "\"feature_family\": \"thin_lines\""
                "}"
            ),
            encoding="utf-8",
        )


def test_motion_pair_folder_returns_known_shift_and_geometry(tmp_path):
    import GeoEdgeAlignSR_v1_Train_v5_NoCoord_return_v2_SimpleTest as trainer

    _write_motion_pair(tmp_path)
    ds = trainer.MotionPairGrayFolder(
        str(tmp_path / "src"),
        str(tmp_path / "lbl"),
        str(tmp_path / "geom"),
        crop_size=16,
        include_subdirs=("stage_41_motion_lines",),
        random_crop=False,
    )

    sample = ds[0]

    assert set(sample) >= {"src_a", "src_b", "lbl_a", "lbl_b", "dx", "dy", "geom_a", "geom_b", "feature_family"}
    assert sample["src_a"].shape == (1, 16, 16)
    assert float(sample["dx"].item()) == 2.0
    assert float(sample["dy"].item()) == 0.0
    assert sample["geom_a"]["boundary"].shape == (1, 16, 16)


def test_generic_motion_consistency_loss_is_small_for_matching_shift_and_positive_for_drift():
    import GeoEdgeAlignSR_v1_Train_v5_NoCoord_return_v2_SimpleTest as trainer

    pred_a = torch.zeros(1, 1, 32, 32)
    pred_a[:, :, :, 10:12] = 1.0
    pred_b_ok = torch.zeros_like(pred_a)
    pred_b_ok[:, :, :, 12:14] = 1.0
    pred_b_bad = pred_a.clone()
    dx = torch.tensor([2.0])
    dy = torch.tensor([0.0])

    ok = trainer.generic_motion_consistency_loss(pred_a, pred_b_ok, dx, dy)
    bad = trainer.generic_motion_consistency_loss(pred_a, pred_b_bad, dx, dy)

    assert ok.item() < 1e-4
    assert bad.item() > 0.01

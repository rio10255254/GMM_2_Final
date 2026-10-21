from pathlib import Path
import sys

import cv2
import numpy as np
import torch


REPO_ROOT = Path(__file__).resolve().parents[3]
MODEL_DIR = REPO_ROOT / "Model"
if str(MODEL_DIR) not in sys.path:
    sys.path.insert(0, str(MODEL_DIR))


def _write_r42_pair(root: Path) -> None:
    rel = Path("stage_34_boundary_lines") / "0000.bmp"
    src_path = root / "src" / rel
    lbl_path = root / "lbl" / rel
    boundary_path = root / "geom" / "boundary" / rel
    center_path = root / "geom" / "centerline" / rel
    distance_path = root / "geom" / "distance" / rel.with_suffix(".npy")
    for p in (src_path, lbl_path, boundary_path, center_path, distance_path):
        p.parent.mkdir(parents=True, exist_ok=True)

    src = np.zeros((32, 32), dtype=np.uint8)
    lbl = np.zeros((32, 32), dtype=np.uint8)
    boundary = np.zeros((32, 32), dtype=np.uint8)
    lbl[:, 15:17] = 255
    src[:, 15:17] = 160
    boundary[:, 15:17] = 255
    cv2.imwrite(str(src_path), src)
    cv2.imwrite(str(lbl_path), lbl)
    cv2.imwrite(str(boundary_path), boundary)
    cv2.imwrite(str(center_path), boundary)
    np.save(distance_path, np.ones((32, 32), dtype=np.float32))


def test_paired_folder_returns_geometry_dict_for_r42_package(tmp_path):
    import GeoEdgeAlignSR_v1_Train_v5_NoCoord_return_v2_SimpleTest as trainer

    _write_r42_pair(tmp_path)
    ds = trainer.PairedGrayFolder(
        str(tmp_path / "src"),
        str(tmp_path / "lbl"),
        crop_size=16,
        random_crop=False,
        geom_dir=str(tmp_path / "geom"),
    )

    sample = ds[0]
    assert isinstance(sample, dict)
    src, lbl, role, geom = trainer._unpack_batch(sample)

    assert src.shape == (1, 16, 16)
    assert lbl.shape == (1, 16, 16)
    assert int(role.item()) == trainer.DATA_ROLE_BOUNDARY
    assert set(geom) == {"boundary", "centerline", "distance"}
    assert geom["boundary"].shape == (1, 16, 16)


def test_boundary_geometry_loss_is_zero_for_matching_edges_and_positive_for_blank_prediction():
    import GeoEdgeAlignSR_v1_Train_v5_NoCoord_return_v2_SimpleTest as trainer

    lbl = torch.zeros(1, 1, 32, 32)
    lbl[:, :, :, 15:17] = 1.0
    pred_same = lbl.clone()
    pred_blank = torch.zeros_like(lbl)
    geom = {
        "boundary": lbl.clone(),
        "centerline": lbl.clone(),
        "distance": torch.ones_like(lbl),
    }

    old_enable = trainer.CFG.BOUNDARY_GEOM_ENABLE
    old_boundary = trainer.CFG.BOUNDARY_LOSS_WEIGHT
    old_center = trainer.CFG.CENTERLINE_LOSS_WEIGHT
    old_distance = trainer.CFG.DISTANCE_EDGE_LOSS_WEIGHT
    try:
        trainer.CFG.BOUNDARY_GEOM_ENABLE = True
        trainer.CFG.BOUNDARY_LOSS_WEIGHT = 1.0
        trainer.CFG.CENTERLINE_LOSS_WEIGHT = 0.5
        trainer.CFG.DISTANCE_EDGE_LOSS_WEIGHT = 0.25
        same_loss, same_parts = trainer.boundary_geometry_loss(pred_same, lbl, geom)
        blank_loss, blank_parts = trainer.boundary_geometry_loss(pred_blank, lbl, geom)
    finally:
        trainer.CFG.BOUNDARY_GEOM_ENABLE = old_enable
        trainer.CFG.BOUNDARY_LOSS_WEIGHT = old_boundary
        trainer.CFG.CENTERLINE_LOSS_WEIGHT = old_center
        trainer.CFG.DISTANCE_EDGE_LOSS_WEIGHT = old_distance

    assert same_loss.item() < 1e-6
    assert blank_loss.item() > 0.1
    assert blank_parts["boundary"].item() > 0.0


def test_kd_role_masks_anchor_legacy_and_capacity_roles():
    import GeoEdgeAlignSR_v1_Train_v5_NoCoord_return_v2_SimpleTest as trainer

    roles = torch.tensor(
        [
            trainer.DATA_ROLE_RING,
            trainer.DATA_ROLE_SHAPE,
            trainer.DATA_ROLE_MICRO,
            trainer.DATA_ROLE_BOUNDARY,
        ],
        dtype=torch.long,
    )

    combo_mask, capacity_mask = trainer.kd_role_masks(roles)

    assert combo_mask.tolist() == [True, True, False, False]
    assert capacity_mask.tolist() == [False, False, True, True]

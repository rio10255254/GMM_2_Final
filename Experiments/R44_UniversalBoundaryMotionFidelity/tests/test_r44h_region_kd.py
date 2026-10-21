from pathlib import Path
import sys

import torch


REPO_ROOT = Path(__file__).resolve().parents[3]
MODEL_DIR = REPO_ROOT / "Model"
if str(MODEL_DIR) not in sys.path:
    sys.path.insert(0, str(MODEL_DIR))


def test_region_kd_boundary_band_mask_uses_distance_sidecar():
    import GeoEdgeAlignSR_v1_Train_v5_NoCoord_return_v2_SimpleTest as trainer

    pred_like = torch.zeros(1, 1, 2, 4)
    distance = torch.tensor(
        [[[[0.0, 1.0, 2.0, 3.0], [4.0, 1.5, 2.5, 0.0]]]],
        dtype=torch.float32,
    )
    mask = trainer.region_kd_boundary_band_mask({"distance": distance}, pred_like, band_px=2.0)

    expected = torch.tensor(
        [[[[1.0, 1.0, 1.0, 0.0], [0.0, 1.0, 0.0, 1.0]]]],
        dtype=torch.float32,
    )
    assert torch.equal(mask, expected)


def test_region_masked_teacher_mse_backprops_only_masked_pixels():
    import GeoEdgeAlignSR_v1_Train_v5_NoCoord_return_v2_SimpleTest as trainer

    pred = torch.zeros(1, 1, 2, 2, requires_grad=True)
    teacher_pred = torch.ones(1, 1, 2, 2)
    mask = torch.tensor([[[[1.0, 0.0], [0.0, 0.0]]]], dtype=torch.float32)

    loss = trainer.region_masked_teacher_mse(pred, teacher_pred, mask)
    assert torch.isclose(loss, torch.tensor(1.0))

    loss.backward()
    assert pred.grad[0, 0, 0, 0].abs() > 0
    assert pred.grad[0, 0, 0, 1].item() == 0.0
    assert pred.grad[0, 0, 1, 0].item() == 0.0
    assert pred.grad[0, 0, 1, 1].item() == 0.0


def test_region_masked_teacher_mse_zero_mask_is_zero():
    import GeoEdgeAlignSR_v1_Train_v5_NoCoord_return_v2_SimpleTest as trainer

    pred = torch.zeros(1, 1, 2, 2, requires_grad=True)
    teacher_pred = torch.ones(1, 1, 2, 2)
    mask = torch.zeros(1, 1, 2, 2)

    loss = trainer.region_masked_teacher_mse(pred, teacher_pred, mask)
    assert loss.item() == 0.0

from pathlib import Path
import sys
from types import SimpleNamespace

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


def test_motion_edge_center_consistency_loss_tracks_known_shift():
    import GeoEdgeAlignSR_v1_Train_v5_NoCoord_return_v2_SimpleTest as trainer

    pred_a = torch.zeros(1, 1, 32, 32)
    pred_a[:, :, 9:15, 10:14] = 1.0
    pred_b_ok = torch.zeros_like(pred_a)
    pred_b_ok[:, :, 9:15, 12:16] = 1.0
    pred_b_bad = torch.zeros_like(pred_a)
    pred_b_bad[:, :, 9:15, 15:19] = 1.0

    geom_a = {"boundary": (pred_a > 0.5).float(), "centerline": (pred_a > 0.5).float()}
    geom_b = {"boundary": (pred_b_ok > 0.5).float(), "centerline": (pred_b_ok > 0.5).float()}
    dx = torch.tensor([2.0])
    dy = torch.tensor([0.0])

    ok = trainer.motion_edge_center_consistency_loss(pred_a, pred_b_ok, dx, dy, geom_a=geom_a, geom_b=geom_b)
    bad = trainer.motion_edge_center_consistency_loss(pred_a, pred_b_bad, dx, dy, geom_a=geom_a, geom_b=geom_b)

    assert ok.item() < 1e-4
    assert bad.item() > 0.01


def test_motion_local_edge_center_loss_catches_balanced_local_drift():
    import GeoEdgeAlignSR_v1_Train_v5_NoCoord_return_v2_SimpleTest as trainer

    pred_a = torch.zeros(1, 1, 32, 32)
    pred_a[:, :, 10:16, 7:11] = 1.0
    pred_a[:, :, 10:16, 21:25] = 1.0
    pred_b_ok = torch.zeros_like(pred_a)
    pred_b_ok[:, :, 10:16, 9:13] = 1.0
    pred_b_ok[:, :, 10:16, 23:27] = 1.0
    pred_b_bad = torch.zeros_like(pred_a)
    pred_b_bad[:, :, 10:16, 7:11] = 1.0
    pred_b_bad[:, :, 10:16, 25:29] = 1.0

    geom_a = {"boundary": (pred_a > 0.5).float(), "centerline": (pred_a > 0.5).float()}
    geom_b = {"boundary": (pred_b_ok > 0.5).float(), "centerline": (pred_b_ok > 0.5).float()}
    dx = torch.tensor([2.0])
    dy = torch.tensor([0.0])

    global_bad = trainer.motion_edge_center_consistency_loss(
        pred_a,
        pred_b_bad,
        dx,
        dy,
        geom_a=geom_a,
        geom_b=geom_b,
    )
    local_ok = trainer.motion_local_edge_center_consistency_loss(
        pred_a,
        pred_b_ok,
        dx,
        dy,
        geom_a=geom_a,
        geom_b=geom_b,
        grid_size=2,
    )
    local_bad = trainer.motion_local_edge_center_consistency_loss(
        pred_a,
        pred_b_bad,
        dx,
        dy,
        geom_a=geom_a,
        geom_b=geom_b,
        grid_size=2,
    )

    assert global_bad.item() < 1e-4
    assert local_ok.item() < 1e-4
    assert local_bad.item() > 0.01


def test_motion_input_lowfreq_consistency_allows_detail_but_rejects_body_shift():
    import GeoEdgeAlignSR_v1_Train_v5_NoCoord_return_v2_SimpleTest as trainer

    yy, xx = torch.meshgrid(torch.arange(48), torch.arange(48), indexing="ij")
    yy = yy.float().view(1, 1, 48, 48)
    xx = xx.float().view(1, 1, 48, 48)
    src = torch.exp(-(((xx - 22.0) ** 2) + ((yy - 24.0) ** 2)) / (2.0 * 5.0 * 5.0))
    detail = 0.06 * torch.sin(xx * 2.7) * torch.sin(yy * 2.3)
    pred_detail_only = (src + detail).clamp(0.0, 1.0)
    pred_shifted_body = torch.exp(-(((xx - 25.0) ** 2) + ((yy - 24.0) ** 2)) / (2.0 * 5.0 * 5.0))

    detail_loss = trainer.motion_input_lowfreq_consistency_loss(pred_detail_only, src, sigma=2.0)
    shifted_loss = trainer.motion_input_lowfreq_consistency_loss(pred_shifted_body, src, sigma=2.0)

    assert detail_loss.item() < 0.01
    assert shifted_loss.item() > detail_loss.item() * 4.0


def test_motion_supervision_is_active_when_only_lowfreq_anchor_is_enabled():
    import GeoEdgeAlignSR_v1_Train_v5_NoCoord_return_v2_SimpleTest as trainer

    cfg = SimpleNamespace(
        MOTION_LOSS_WEIGHT=0.0,
        MOTION_RECON_WEIGHT=0.0,
        MOTION_CENTER_WEIGHT=0.0,
        MOTION_LOCAL_CENTER_WEIGHT=0.0,
        MOTION_INPUT_LOWFREQ_WEIGHT=0.2,
    )

    assert trainer.motion_supervision_has_enabled_loss(cfg)


def test_checkpoint_config_records_raw_anchor_output_settings(monkeypatch):
    import GeoEdgeAlignSR_v1_Train_v5_NoCoord_return_v2_SimpleTest as trainer

    monkeypatch.setattr(trainer.CFG, "RAW_ANCHOR_OUTPUT_MODE", "detail", raising=False)
    monkeypatch.setattr(trainer.CFG, "RAW_ANCHOR_OUTPUT_ALPHA", 0.1, raising=False)
    monkeypatch.setattr(trainer.CFG, "RAW_ANCHOR_OUTPUT_SIGMA", 2.0, raising=False)
    monkeypatch.setattr(trainer.CFG, "RAW_ANCHOR_OUTPUT_DETAIL_GAIN", 0.35, raising=False)

    config = trainer._checkpoint_model_config()

    assert config["raw_anchor_output"] == {
        "mode": "detail",
        "alpha": 0.1,
        "sigma": 2.0,
        "detail_gain": 0.35,
    }

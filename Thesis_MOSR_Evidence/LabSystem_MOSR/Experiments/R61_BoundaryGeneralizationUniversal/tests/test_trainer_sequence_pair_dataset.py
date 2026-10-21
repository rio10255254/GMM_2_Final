from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


MODEL_DIR = Path(__file__).resolve().parents[5] / "Model"
TRAINER_PATH = MODEL_DIR / "GeoEdgeAlignSR_v1_Train_v5_NoCoord_return_v2_SimpleTest.py"


def load_trainer_module():
    sys.path.insert(0, str(MODEL_DIR))
    spec = importlib.util.spec_from_file_location("geoedge_trainer_sequence_pair_test", TRAINER_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_sequence_pair_builder_accepts_hs100mg_trailing_frame_numbers(tmp_path: Path):
    trainer = load_trainer_module()

    pillar_dir = tmp_path / "stage_35_r61_sequence_guard" / "stage_58_hs100mg_anchor" / "pillar"
    via_dir = tmp_path / "stage_35_r61_sequence_guard" / "stage_58_hs100mg_anchor" / "via"
    pillar_dir.mkdir(parents=True)
    via_dir.mkdir(parents=True)
    paths = [
        pillar_dir / "hs100mg_pillar_0000.bmp",
        pillar_dir / "hs100mg_pillar_0002.bmp",
        pillar_dir / "hs100mg_pillar_0004.bmp",
        via_dir / "hs100mg_via_0001.bmp",
        via_dir / "hs100mg_via_0003.bmp",
    ]

    pairs = trainer.SequencePairGrayFolder._build_pairs([str(path) for path in paths])

    assert [(Path(a).name, Path(b).name) for a, b in pairs] == [
        ("hs100mg_pillar_0000.bmp", "hs100mg_pillar_0002.bmp"),
        ("hs100mg_pillar_0002.bmp", "hs100mg_pillar_0004.bmp"),
        ("hs100mg_via_0001.bmp", "hs100mg_via_0003.bmp"),
    ]


def test_motion_consistency_can_penalize_shifted_gradient_mismatch():
    import torch

    trainer = load_trainer_module()

    pred_a = torch.zeros((1, 1, 32, 32), dtype=torch.float32)
    pred_a[:, :, 10:22, 10:22] = 1.0
    pred_b_aligned = trainer.warp_tensor_by_dxdy(
        pred_a,
        torch.tensor([2.0], dtype=torch.float32),
        torch.tensor([0.0], dtype=torch.float32),
    )
    pred_b_flat = pred_b_aligned.clone()
    pred_b_flat[:, :, 12:20, 12:20] = 0.5

    pix_only = trainer.generic_motion_consistency_loss(
        pred_a,
        pred_b_flat,
        torch.tensor([2.0], dtype=torch.float32),
        torch.tensor([0.0], dtype=torch.float32),
        gradient_weight=0.0,
    )
    with_grad = trainer.generic_motion_consistency_loss(
        pred_a,
        pred_b_flat,
        torch.tensor([2.0], dtype=torch.float32),
        torch.tensor([0.0], dtype=torch.float32),
        gradient_weight=1.0,
    )

    assert with_grad > pix_only

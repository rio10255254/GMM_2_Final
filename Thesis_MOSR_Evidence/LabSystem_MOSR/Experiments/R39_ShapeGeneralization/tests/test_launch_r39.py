from __future__ import annotations

import argparse
import importlib.util
import sys
from pathlib import Path

import torch


LAB_ROOT = Path(__file__).resolve().parents[3]
SCRIPT_PATH = LAB_ROOT / "Experiments" / "R39_ShapeGeneralization" / "scripts" / "launch_r39.py"


def load_module():
    script_dir = SCRIPT_PATH.parent
    sys.path.insert(0, str(script_dir))
    spec = importlib.util.spec_from_file_location("lab_launch_r39", SCRIPT_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class FakeCFG:
    pass


class FakeTrainer:
    CFG = FakeCFG()
    MODEL_NAME_BASE = ""
    TRAIN_SRC_DIR = ""
    TRAIN_LBL_DIR = ""
    TRAINING_PROGRESS_ROOT = ""

    @classmethod
    def _set_training_progress_root(cls, root: str) -> None:
        cls.TRAINING_PROGRESS_ROOT = root


def _write_checkpoint(path: Path) -> None:
    payload = {
        "state_dict": {
            "physics_layer.PSFs": torch.zeros(1, 100, 3, 3),
            "physics_layer.PSF_mean": torch.zeros(1, 1, 3, 3),
            "physics_layer.PSF_center": torch.zeros(1, 1, 3, 3),
            "weak_psf_block.PSFs": torch.zeros(1, 4, 3, 3),
            "encoder.weight": torch.ones(1),
        },
        "ema_state_dict": {
            "physics_layer.PSFs": torch.zeros(1, 100, 3, 3),
            "physics_layer.PSF_mean": torch.zeros(1, 1, 3, 3),
            "physics_layer.PSF_center": torch.zeros(1, 1, 3, 3),
            "weak_psf_block.PSFs": torch.zeros(1, 4, 3, 3),
            "encoder.weight": torch.ones(1),
        },
        "epoch": 7,
    }
    torch.save(payload, path)


def test_configure_trainer_mounts_lab_psf_data_and_output(tmp_path: Path) -> None:
    module = load_module()
    checkpoint = tmp_path / "combo.pth.tar"
    _write_checkpoint(checkpoint)
    data_dir = tmp_path / "package"
    (data_dir / "src").mkdir(parents=True)
    (data_dir / "lbl").mkdir(parents=True)
    args = argparse.Namespace(
        candidate="r39_shape_mix_safe",
        combo_checkpoint=checkpoint,
        num_epoch=3,
        device="cpu",
    )

    module.configure_trainer(FakeTrainer, args, data_dir)
    cfg = FakeTrainer.CFG

    assert Path(cfg.PSF_FITTED_PATH) == module.LAB_PSF_PATH
    assert Path(cfg.SEQ_SRC_DIR).is_relative_to(module.LAB_ROOT)
    assert Path(cfg.SEQ_LBL_DIR).is_relative_to(module.LAB_ROOT)
    assert Path(FakeTrainer.TRAINING_PROGRESS_ROOT) == module.LAB_TRAINING_PROGRESS_ROOT
    assert Path(FakeTrainer.TRAIN_SRC_DIR) == data_dir / "src"
    assert Path(FakeTrainer.TRAIN_LBL_DIR) == data_dir / "lbl"
    assert FakeTrainer.MODEL_NAME_BASE == cfg.MODEL_NAME
    assert cfg.MODEL_NAME.startswith("LAB_")
    assert Path(cfg.RESUME_CHECKPOINT).is_relative_to(module.LAB_CHECKPOINT_CACHE)
    filtered = torch.load(cfg.RESUME_CHECKPOINT, map_location="cpu")
    for section in ("state_dict", "ema_state_dict"):
        assert "encoder.weight" in filtered[section]
        for key in module.PSF_BUFFER_KEYS:
            assert key not in filtered[section]


def test_default_roots_stay_inside_lab_system() -> None:
    module = load_module()
    assert module.LAB_ROOT.name == "LabSystem_MOSR"
    assert module.DEFAULT_OUTPUT_ROOT.is_relative_to(module.LAB_ROOT)
    assert module.LAB_TRAINING_PROGRESS_ROOT.is_relative_to(module.LAB_ROOT)
    assert module.LAB_PSF_PATH.is_relative_to(module.LAB_ROOT)
    assert module.MODEL_DIR.name == "Model"
    assert module.MODEL_DIR.parent.name == "GMM_2_Final"

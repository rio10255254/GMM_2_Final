from __future__ import annotations

import argparse
import importlib.util
import sys
from pathlib import Path

import torch


LAB_ROOT = Path(__file__).resolve().parents[3]
SCRIPT_PATH = LAB_ROOT / "Experiments" / "R40_MicroscopyFeatureCoverage" / "scripts" / "launch_r40.py"


def load_module():
    script_dir = SCRIPT_PATH.parent
    sys.path.insert(0, str(script_dir))
    spec = importlib.util.spec_from_file_location("lab_launch_r40", SCRIPT_PATH)
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
    checkpoint = tmp_path / "base.pth.tar"
    _write_checkpoint(checkpoint)
    data_dir = tmp_path / "package"
    (data_dir / "src").mkdir(parents=True)
    (data_dir / "lbl").mkdir(parents=True)
    args = argparse.Namespace(
        candidate="r40_micro_capacity_combo",
        base_checkpoint=checkpoint,
        num_epoch=4,
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


def test_dry_run_reports_missing_data_without_starting_trainer(tmp_path: Path, capsys) -> None:
    module = load_module()
    checkpoint = tmp_path / "base.pth.tar"
    _write_checkpoint(checkpoint)

    rc = module.main(
        [
            "--candidate",
            "r40_micro_capacity_combo",
            "--base-checkpoint",
            str(checkpoint),
            "--data-root",
            str(tmp_path / "missing_data_root"),
            "--dry-run",
        ]
    )

    out = capsys.readouterr().out
    assert rc == 0
    assert '"training_ready": false' in out
    assert "data package is not ready" in out
    assert "missing_data_root" in out

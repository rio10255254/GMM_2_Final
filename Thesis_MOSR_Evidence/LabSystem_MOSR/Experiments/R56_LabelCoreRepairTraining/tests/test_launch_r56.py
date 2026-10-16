from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "launch_r56.py"


def load_module():
    spec = importlib.util.spec_from_file_location("launch_r56", SCRIPT_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_dry_run_reports_missing_r56_data_without_requiring_checkpoint(tmp_path: Path, capsys):
    module = load_module()

    rc = module.main(
        [
            "--candidate",
            "r56_label_core_repair_r53_scratch",
            "--data-root",
            str(tmp_path / "missing_data_root"),
            "--num-epoch",
            "50",
            "--dry-run",
        ]
    )

    out = capsys.readouterr().out
    assert rc == 0
    assert '"training_ready": false' in out
    assert "data package is not ready" in out
    assert '"r53_realistic_calibrated_train_6000"' in out
    assert '"num_epoch": 50' in out
    assert '"scratch_training": true' in out
    assert '"batch_size": 16' in out


def test_configure_trainer_defaults_to_scratch_and_sets_artifact_identity(tmp_path: Path):
    module = load_module()

    cfg = type("CFG", (), {})()

    class Trainer:
        CFG = cfg

        @staticmethod
        def _set_training_progress_root(path: str) -> None:
            Trainer.TRAINING_PROGRESS_ROOT_SET = path

    args = module.build_arg_parser().parse_args(
        [
            "--candidate",
            "r56_label_core_repair_r53_scratch",
            "--data-root",
            str(tmp_path),
            "--num-epoch",
            "50",
        ]
    )
    data_dir = tmp_path / "r53_realistic_calibrated_train_6000"
    module.configure_trainer(Trainer, args, data_dir)

    assert Trainer.CFG.LOAD_MODEL is False
    assert Trainer.CFG.RESUME_CHECKPOINT == ""
    assert Trainer.CFG.MODEL_NAME == "LAB_GESR_v1_v5_ST0p8_SWP_r56_label_core_repair_r53_scratch"
    assert Trainer.MODEL_NAME_BASE == Trainer.CFG.MODEL_NAME
    assert Trainer.CFG.BATCH_SIZE == 16
    assert Trainer.CFG.VAL_BATCH_SIZE == 4
    assert Trainer.CFG.NUM_WORKERS == 4
    assert Trainer.CFG.DATALOADER_PERSISTENT_WORKERS is False
    assert Trainer.CFG.DATALOADER_PREFETCH_FACTOR == 2
    assert Trainer.CFG.PHYS_FORWARD_ENABLE is False
    assert Trainer.CFG.W_PHYS_MAX == 0.0
    assert Trainer.TRAIN_SRC_DIR == str(data_dir / "src")
    assert Trainer.TRAIN_LBL_DIR == str(data_dir / "lbl")
    assert Trainer.TRAIN_GEOM_DIR == str(data_dir / "geom")

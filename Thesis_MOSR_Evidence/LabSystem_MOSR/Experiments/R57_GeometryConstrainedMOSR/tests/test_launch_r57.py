from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "launch_r57.py"


def load_module():
    spec = importlib.util.spec_from_file_location("launch_r57", SCRIPT_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_dry_run_reports_missing_r57_data_without_requiring_checkpoint(tmp_path: Path, capsys):
    module = load_module()

    rc = module.main(
        [
            "--candidate",
            "r57_geom_cd_anchor_finetune",
            "--data-root",
            str(tmp_path / "missing_data_root"),
            "--num-epoch",
            "20",
            "--scratch",
            "--dry-run",
        ]
    )

    out = capsys.readouterr().out
    assert rc == 0
    assert '"training_ready": false' in out
    assert "data package is not ready" in out
    assert '"r57_hs100mg_r55_finetune_train"' in out
    assert '"geometry_constrained": true' in out
    assert '"cd_gate_required": true' in out
    assert '"scratch_training": true' in out


def test_configure_trainer_sets_r55_finetune_and_geometry_weights(tmp_path: Path, monkeypatch):
    module = load_module()
    monkeypatch.setattr(module, "_require_lab_assets", lambda: None)

    base_checkpoint = tmp_path / "r55_best_tradeoff.pth.tar"
    base_checkpoint.write_bytes(b"fake")
    lab_checkpoint = tmp_path / "lab_compatible.pth.tar"
    lab_checkpoint.write_bytes(b"fake")
    monkeypatch.setattr(module, "prepare_lab_checkpoint", lambda path: lab_checkpoint)

    cfg = type("CFG", (), {})()

    class Trainer:
        CFG = cfg

        @staticmethod
        def _set_training_progress_root(path: str) -> None:
            Trainer.TRAINING_PROGRESS_ROOT_SET = path

    args = module.build_arg_parser().parse_args(
        [
            "--candidate",
            "r57_geom_cd_anchor_finetune",
            "--data-root",
            str(tmp_path),
            "--base-checkpoint",
            str(base_checkpoint),
            "--num-epoch",
            "20",
            "--batch-size",
            "8",
            "--val-batch-size",
            "2",
            "--num-workers",
            "1",
            "--run-suffix",
            "smoke",
            "--anchor-focus",
        ]
    )
    data_dir = tmp_path / "r57_hs100mg_r55_finetune_train"
    module.configure_trainer(Trainer, args, data_dir)

    assert Trainer.CFG.LOAD_MODEL is True
    assert Trainer.CFG.LOAD_RESET_OPTIMIZER is True
    assert Trainer.CFG.LOAD_RESET_EPOCH is True
    assert Trainer.CFG.RESUME_CHECKPOINT == str(lab_checkpoint)
    assert Trainer.CFG.LAB_SOURCE_CHECKPOINT == str(base_checkpoint.resolve())
    assert Trainer.CFG.MODEL_NAME == "LAB_GESR_v1_v5_ST0p8_SWP_r57_geom_cd_anchor_finetune_smoke"
    assert Trainer.MODEL_NAME_BASE == Trainer.CFG.MODEL_NAME
    assert Trainer.CFG.LR == 7.5e-6
    assert Trainer.CFG.BATCH_SIZE == 8
    assert Trainer.CFG.VAL_BATCH_SIZE == 2
    assert Trainer.CFG.PHYS_FORWARD_ENABLE is False
    assert Trainer.CFG.W_PHYS_MAX == 0.0
    assert Trainer.CFG.BOUNDARY_GEOM_ENABLE is True
    assert Trainer.CFG.BOUNDARY_LOSS_WEIGHT == 0.045
    assert Trainer.CFG.DISTANCE_EDGE_LOSS_WEIGHT == 0.025
    assert Trainer.CFG.SEQ_ENABLE is True
    assert Trainer.CFG.SEQ_GEOM_ENABLE is True
    assert Trainer.CFG.TRAIN_INCLUDE_SUBDIRS == ("stage_34_hs100mg_anchor",)
    assert Trainer.CFG.R57_ANCHOR_FOCUS is True
    assert Trainer.TRAIN_SRC_DIR == str(data_dir / "src")
    assert Trainer.TRAIN_LBL_DIR == str(data_dir / "lbl")
    assert Trainer.TRAIN_GEOM_DIR == str(data_dir / "geom")


def test_r57_1_candidate_defaults_to_anchor_focus_and_asymmetric_cd(tmp_path: Path, monkeypatch):
    module = load_module()
    monkeypatch.setattr(module, "_require_lab_assets", lambda: None)

    base_checkpoint = tmp_path / "r55_best_tradeoff.pth.tar"
    base_checkpoint.write_bytes(b"fake")
    lab_checkpoint = tmp_path / "lab_compatible.pth.tar"
    lab_checkpoint.write_bytes(b"fake")
    monkeypatch.setattr(module, "prepare_lab_checkpoint", lambda path: lab_checkpoint)

    cfg = type("CFG", (), {})()

    class Trainer:
        CFG = cfg

        @staticmethod
        def _set_training_progress_root(path: str) -> None:
            Trainer.TRAINING_PROGRESS_ROOT_SET = path

    args = module.build_arg_parser().parse_args(
        [
            "--candidate",
            "r57_1_asym_cd_anchor_finetune",
            "--data-root",
            str(tmp_path),
            "--base-checkpoint",
            str(base_checkpoint),
            "--num-epoch",
            "4",
        ]
    )
    data_dir = tmp_path / "r57_hs100mg_r55_finetune_train"
    module.configure_trainer(Trainer, args, data_dir)

    assert Trainer.CFG.R57_ASYMMETRIC_CD_CORRECTION is True
    assert Trainer.CFG.R57_ANCHOR_FOCUS is True
    assert Trainer.CFG.TRAIN_INCLUDE_SUBDIRS == ("stage_34_hs100mg_anchor",)
    assert Trainer.CFG.MODEL_NAME == "LAB_GESR_v1_v5_ST0p8_SWP_r57_1_asym_cd_anchor_finetune"
    assert Trainer.CFG.LR == 3e-6

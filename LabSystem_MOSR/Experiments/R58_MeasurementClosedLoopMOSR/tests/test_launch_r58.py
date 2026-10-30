from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "launch_r58.py"


def load_module():
    spec = importlib.util.spec_from_file_location("launch_r58", SCRIPT_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_dry_run_reports_missing_r58_data_without_checkpoint_requirement(tmp_path: Path, capsys):
    module = load_module()

    rc = module.main(
        [
            "--candidate",
            "r58_frac025",
            "--data-root",
            str(tmp_path / "missing"),
            "--scratch",
            "--dry-run",
        ]
    )

    out = capsys.readouterr().out
    assert rc == 0
    assert '"training_ready": false' in out
    assert '"profile": "r58_frac025_train"' in out
    assert '"measurement_closed_loop": true' in out
    assert '"cd_gate_required": true' in out
    assert '"scratch_training": true' in out


def test_configure_trainer_sets_measurement_closed_loop_defaults(tmp_path: Path, monkeypatch):
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
            "r58_frac050",
            "--data-root",
            str(tmp_path),
            "--base-checkpoint",
            str(base_checkpoint),
            "--num-epoch",
            "6",
            "--batch-size",
            "4",
            "--val-batch-size",
            "2",
            "--num-workers",
            "1",
            "--run-suffix",
            "smoke",
        ]
    )
    data_dir = tmp_path / "r58_frac050_train"
    module.configure_trainer(Trainer, args, data_dir)

    assert Trainer.CFG.LOAD_MODEL is True
    assert Trainer.CFG.RESUME_CHECKPOINT == str(lab_checkpoint)
    assert Trainer.CFG.LAB_SOURCE_CHECKPOINT == str(base_checkpoint.resolve())
    assert Trainer.CFG.MODEL_NAME == "LAB_GESR_v1_v5_ST0p8_SWP_r58_frac050_smoke"
    assert Trainer.CFG.LR == module.CANDIDATE_SETTINGS["r58_frac050"]["lr"]
    assert Trainer.CFG.PHYS_FORWARD_ENABLE is False
    assert Trainer.CFG.W_PHYS_MAX == 0.0
    assert Trainer.CFG.BOUNDARY_GEOM_ENABLE is True
    assert Trainer.CFG.BOUNDARY_LOSS_WARMUP_EPOCH <= 1
    assert Trainer.CFG.BOUNDARY_LOSS_WEIGHT > 0.0
    assert Trainer.CFG.DISTANCE_EDGE_LOSS_WEIGHT > 0.0
    assert Trainer.CFG.TRAIN_INCLUDE_SUBDIRS == ("stage_58_hs100mg_anchor",)
    assert Trainer.CFG.R58_MEASUREMENT_CLOSED_LOOP is True
    assert Trainer.CFG.R58_CORRECTION_FRACTION == 0.5
    assert Trainer.TRAIN_SRC_DIR == str(data_dir / "src")
    assert Trainer.TRAIN_LBL_DIR == str(data_dir / "lbl")
    assert Trainer.TRAIN_GEOM_DIR == str(data_dir / "geom")


def test_ensure_data_package_accepts_r58_manifest(tmp_path: Path):
    module = load_module()
    package = tmp_path / "r58_frac075_train"
    (package / "src").mkdir(parents=True)
    (package / "lbl").mkdir()
    (package / "geom" / "boundary").mkdir(parents=True)
    (package / "geom" / "centerline").mkdir(parents=True)
    (package / "geom" / "distance").mkdir(parents=True)
    (package / "src" / "a.bmp").write_bytes(b"src")
    (package / "lbl" / "a.bmp").write_bytes(b"lbl")
    (package / "geom" / "boundary" / "a.bmp").write_bytes(b"boundary")
    (package / "geom" / "centerline" / "a.bmp").write_bytes(b"centerline")
    (package / "geom" / "distance" / "a.npy").write_bytes(b"distance")
    manifest = {
        "profile": "r58_frac075_train",
        "total_pairs": 1,
        "pairs": [{"package_src": "src/a.bmp", "package_lbl": "lbl/a.bmp"}],
        "r58_measurement_closed_loop": True,
        "geometry_sidecars": True,
        "geometry_count": 1,
        "geom_dir": str(package / "geom"),
    }
    (package / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")

    data_dir, loaded = module.ensure_data_package("r58_frac075_train", tmp_path)

    assert data_dir == package
    assert loaded["r58_measurement_closed_loop"] is True

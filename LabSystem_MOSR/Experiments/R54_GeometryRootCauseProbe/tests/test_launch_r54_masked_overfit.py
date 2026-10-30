from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "launch_r54_masked_overfit.py"


def load_module():
    script_dir = SCRIPT_PATH.parent
    sys.path.insert(0, str(script_dir))
    spec = importlib.util.spec_from_file_location("launch_r54_masked_overfit", SCRIPT_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _write_package(root: Path, profile: str, label_policy: str, total_pairs: int = 2) -> Path:
    package_dir = root / profile
    for leaf in ("src", "lbl", "geom"):
        (package_dir / leaf).mkdir(parents=True, exist_ok=True)
    manifest = {
        "profile": profile,
        "total_pairs": total_pairs,
        "geometry_sidecars": True,
        "geometry_count": total_pairs,
        "geom_dir": str(package_dir / "geom"),
        "label_policy": label_policy,
        "count_by_role": {"masked_real_cad_probe": total_pairs},
    }
    (package_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return package_dir


def test_ensure_data_package_accepts_r54_masked_manifest(tmp_path: Path):
    module = load_module()
    profile = module.PROFILE_BY_CANDIDATE["r54_masked_overfit_from_r40"]
    package_dir = _write_package(tmp_path, profile, module.LABEL_POLICY, total_pairs=3)

    data_dir, manifest = module.ensure_data_package(profile, tmp_path, build_data=False, force_data=False)

    assert data_dir == package_dir
    assert manifest["profile"] == profile
    assert manifest["total_pairs"] == 3


def test_configure_trainer_uses_lab_r40_tradeoff_and_sets_artifact_identity(tmp_path: Path):
    module = load_module()
    package_dir = _write_package(
        tmp_path,
        module.PROFILE_BY_CANDIDATE["r54_masked_overfit_from_r40"],
        module.LABEL_POLICY,
    )
    base = tmp_path / "base" / "best_tradeoff.pth.tar"
    base.parent.mkdir(parents=True)
    base.write_bytes(b"fake")
    cached = tmp_path / "cache" / "best_tradeoff_labpsf.pth.tar"
    cached.parent.mkdir(parents=True)
    cached.write_bytes(b"fake-cache")
    module.prepare_lab_checkpoint = lambda checkpoint: cached

    cfg = type("CFG", (), {})()

    class Trainer:
        CFG = cfg

        @staticmethod
        def _set_training_progress_root(path: str) -> None:
            Trainer.TRAINING_PROGRESS_ROOT_SET = path

    args = module.build_arg_parser().parse_args(
        [
            "--candidate",
            "r54_masked_overfit_from_r40",
            "--data-root",
            str(tmp_path),
            "--base-checkpoint",
            str(base),
            "--num-epoch",
            "7",
            "--run-suffix",
            "unit",
            "--batch-size",
            "4",
            "--val-ratio",
            "0",
        ]
    )

    module.configure_trainer(Trainer, args, package_dir)

    assert Trainer.CFG.LOAD_MODEL is True
    assert Trainer.CFG.LAB_SOURCE_CHECKPOINT == str(base.resolve())
    assert Trainer.CFG.RESUME_CHECKPOINT == str(cached)
    assert Trainer.CFG.MODEL_NAME == "LAB_GESR_v1_v5_ST0p8_SWP_r54_masked_overfit_from_r40_unit"
    assert Trainer.MODEL_NAME_BASE == Trainer.CFG.MODEL_NAME
    assert Trainer.CFG.NUM_EPOCH == 7
    assert Trainer.CFG.VAL_RATIO == 0.0
    assert Trainer.CFG.SEQ_ENABLE is False
    assert Trainer.CFG.PHYS_FORWARD_ENABLE is False
    assert Trainer.CFG.BOUNDARY_GEOM_ENABLE is True
    assert Trainer.CFG.BATCH_SIZE == 4
    assert Trainer.TRAIN_SRC_DIR == str(package_dir / "src")
    assert Trainer.TRAIN_LBL_DIR == str(package_dir / "lbl")
    assert Trainer.TRAIN_GEOM_DIR == str(package_dir / "geom")
    assert Trainer.CFG.BOUNDARY_GEOM_DIR == str(package_dir / "geom")

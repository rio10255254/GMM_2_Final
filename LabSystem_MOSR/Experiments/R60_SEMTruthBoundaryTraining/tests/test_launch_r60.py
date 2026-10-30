from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import numpy as np


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "launch_r60.py"


def load_module():
    spec = importlib.util.spec_from_file_location("launch_r60", SCRIPT_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _write_r60_manifest(package: Path) -> None:
    (package / "src" / "stage_60_hs100mg_real_crop").mkdir(parents=True)
    (package / "src" / "stage_60_hs100mg_sem_anchor").mkdir(parents=True)
    (package / "lbl").mkdir()
    (package / "geom" / "boundary").mkdir(parents=True)
    (package / "geom" / "centerline").mkdir(parents=True)
    (package / "geom" / "distance").mkdir(parents=True)
    (package / "src" / "stage_60_hs100mg_real_crop" / "a.bmp").write_bytes(b"src")
    (package / "lbl" / "a.bmp").write_bytes(b"lbl")
    (package / "geom" / "boundary" / "a.bmp").write_bytes(b"boundary")
    (package / "geom" / "centerline" / "a.bmp").write_bytes(b"centerline")
    (package / "geom" / "distance" / "a.npy").write_bytes(b"distance")
    manifest = {
        "profile": package.name,
        "r60_sem_truth_boundary_training": True,
        "target_is_sem_truth": True,
        "total_pairs": 1,
        "real_crop_pairs": 1,
        "anchor_pairs": 1,
        "pairs": [{"package_src": "src/stage_60_hs100mg_real_crop/a.bmp", "package_lbl": "lbl/a.bmp"}],
        "geometry_sidecars": True,
        "geometry_count": 1,
        "geom_dir": str(package / "geom"),
    }
    (package / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")


def _touch_pair(package: Path, rel_src: str, rel_lbl: str | None = None) -> None:
    rel_lbl = rel_lbl or rel_src.replace("src/", "lbl/", 1)
    (package / rel_src).parent.mkdir(parents=True, exist_ok=True)
    (package / rel_src).write_bytes(b"src")
    (package / rel_lbl).parent.mkdir(parents=True, exist_ok=True)
    (package / rel_lbl).write_bytes(b"lbl")


def _make_repeat_manifest_package(package: Path) -> dict:
    pairs = []
    for repeat in range(3):
        rel_src = f"src/stage_60_hs100mg_real_crop/pillar/real_pillar_002_r{repeat:02d}_{repeat:04d}.bmp"
        _touch_pair(package, rel_src)
        pairs.append(
            {
                "package_src": rel_src,
                "package_lbl": rel_src.replace("src/", "lbl/", 1),
                "source_group": "hs100mg_real_crop",
                "domain": "real_microscope_crop",
                "feature": "pillar",
                "template_id": 2,
                "sem_reference_id": 2,
                "repeat_index": repeat,
            }
        )
    for repeat in range(2):
        rel_src = f"src/stage_60_hs100mg_real_crop/via/real_via_010_r{repeat:02d}_{repeat:04d}.bmp"
        _touch_pair(package, rel_src)
        pairs.append(
            {
                "package_src": rel_src,
                "package_lbl": rel_src.replace("src/", "lbl/", 1),
                "source_group": "hs100mg_real_crop",
                "domain": "real_microscope_crop",
                "feature": "via",
                "template_id": 10,
                "sem_reference_id": 10,
                "repeat_index": repeat,
            }
        )
    for idx in range(4):
        feature = "pillar" if idx < 2 else "via"
        sem_id = 100 + (idx % 2)
        rel_src = f"src/stage_60_hs100mg_sem_anchor/{feature}/anchor_{feature}_{idx:04d}.bmp"
        _touch_pair(package, rel_src)
        pairs.append(
            {
                "package_src": rel_src,
                "package_lbl": rel_src.replace("src/", "lbl/", 1),
                "source_group": "hs100mg_sem_anchor",
                "domain": "synthetic_sem_anchor",
                "feature": feature,
                "sem_reference_id": sem_id,
            }
        )
    manifest = {
        "profile": package.name,
        "r60_sem_truth_boundary_training": True,
        "target_is_sem_truth": True,
        "total_pairs": len(pairs),
        "real_crop_pairs": 5,
        "anchor_pairs": 4,
        "pairs": pairs,
        "geometry_sidecars": True,
        "geometry_count": len(pairs),
    }
    return manifest


def test_dry_run_reports_missing_r60_data_without_checkpoint_requirement(tmp_path: Path, capsys):
    module = load_module()

    rc = module.main(
        [
            "--candidate",
            "r60_semtruth_realcrop_anchor",
            "--data-root",
            str(tmp_path / "missing"),
            "--scratch",
            "--dry-run",
        ]
    )

    out = capsys.readouterr().out
    assert rc == 0
    assert '"training_ready": false' in out
    assert '"sem_truth_boundary_training": true' in out
    assert '"target_is_sem_truth": true' in out
    assert '"cd_selection_required": true' in out
    assert '"scratch_training": true' in out


def test_configure_trainer_uses_real_crop_and_anchor_without_fractional_correction(tmp_path: Path, monkeypatch):
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
            "r60_semtruth_realcrop_anchor",
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
    data_dir = tmp_path / "r60_sem_truth_realcrop_anchor_train"
    module.configure_trainer(Trainer, args, data_dir)

    assert Trainer.CFG.LOAD_MODEL is True
    assert Trainer.CFG.RESUME_CHECKPOINT == str(lab_checkpoint)
    assert Trainer.CFG.LAB_SOURCE_CHECKPOINT == str(base_checkpoint.resolve())
    assert Trainer.CFG.MODEL_NAME == "LAB_GESR_v1_v5_ST0p8_SWP_r60_semtruth_realcrop_anchor_smoke"
    assert Trainer.CFG.PHYS_FORWARD_ENABLE is False
    assert Trainer.CFG.W_PHYS_MAX == 0.0
    assert Trainer.CFG.BOUNDARY_GEOM_ENABLE is True
    assert Trainer.CFG.BOUNDARY_LOSS_WEIGHT > 0.05
    assert Trainer.CFG.TRAIN_INCLUDE_SUBDIRS == (
        "stage_60_hs100mg_real_crop",
        "stage_60_hs100mg_sem_anchor",
    )
    assert Trainer.CFG.R60_SEM_TRUTH_BOUNDARY is True
    assert Trainer.CFG.R60_TARGET_IS_SEM_TRUTH is True
    assert Trainer.CFG.R60_CD_SELECTION_REQUIRED is True
    assert not hasattr(Trainer.CFG, "R58_CORRECTION_FRACTION")
    assert Trainer.TRAIN_SRC_DIR == str(data_dir / "src")
    assert Trainer.TRAIN_LBL_DIR == str(data_dir / "lbl")
    assert Trainer.TRAIN_GEOM_DIR == str(data_dir / "geom")


def test_prepare_grouped_fixed_split_keeps_repeated_real_crops_together(tmp_path: Path):
    module = load_module()
    package = tmp_path / "r60_sem_truth_realcrop_anchor_train"
    manifest = _make_repeat_manifest_package(package)

    split = module.prepare_grouped_fixed_split(
        package_dir=package,
        manifest=manifest,
        include_subdirs=("stage_60_hs100mg_real_crop", "stage_60_hs100mg_sem_anchor"),
        val_ratio=0.4,
        seed=7,
    )

    split_dir = Path(split["split_dir"])
    train_idx = np.load(split_dir / "train_idx.npy")
    val_idx = np.load(split_dir / "val_idx.npy")
    meta = json.loads((split_dir / "split_meta.json").read_text(encoding="utf-8"))

    assert len(train_idx) > 0
    assert len(val_idx) > 0
    assert meta["group_overlap_count"] == 0
    assert meta["source_path_count"] == len(manifest["pairs"])
    assert meta["train_count"] + meta["val_count"] == len(manifest["pairs"])

    path_to_group = {
        item["package_src"]: module.group_key_for_manifest_pair(item)
        for item in manifest["pairs"]
    }
    sorted_rel = sorted(path_to_group)
    train_groups = {path_to_group[sorted_rel[int(i)]] for i in train_idx}
    val_groups = {path_to_group[sorted_rel[int(i)]] for i in val_idx}

    assert train_groups.isdisjoint(val_groups)


def test_prepare_grouped_fixed_split_stratifies_validation_sources(tmp_path: Path):
    module = load_module()
    package = tmp_path / "r60_sem_truth_realcrop_anchor_train"
    manifest = _make_repeat_manifest_package(package)

    split = module.prepare_grouped_fixed_split(
        package_dir=package,
        manifest=manifest,
        include_subdirs=("stage_60_hs100mg_real_crop", "stage_60_hs100mg_sem_anchor"),
        val_ratio=0.2,
        seed=1337,
    )

    assert set(split["val_strata"]) == {
        "hs100mg_real_crop:pillar",
        "hs100mg_real_crop:via",
        "hs100mg_sem_anchor:pillar",
        "hs100mg_sem_anchor:via",
    }


def test_configure_trainer_uses_external_grouped_split(tmp_path: Path, monkeypatch):
    module = load_module()
    monkeypatch.setattr(module, "_require_lab_assets", lambda: None)

    cfg = type("CFG", (), {})()

    class Trainer:
        CFG = cfg

        @staticmethod
        def _set_training_progress_root(path: str) -> None:
            Trainer.TRAINING_PROGRESS_ROOT_SET = path

    split_dir = tmp_path / "splits" / "grouped_seed0007_val040"
    split_dir.mkdir(parents=True)
    args = module.build_arg_parser().parse_args(
        [
            "--candidate",
            "r60_semtruth_realcrop_anchor",
            "--scratch",
            "--data-root",
            str(tmp_path),
            "--num-epoch",
            "2",
        ]
    )
    data_dir = tmp_path / "r60_sem_truth_realcrop_anchor_train"

    module.configure_trainer(Trainer, args, data_dir, fixed_split_dir=split_dir)

    assert Trainer.CFG.REPRO_MODE is True
    assert Trainer.CFG.REPRO_FORCE_FIXED_SPLIT is False
    assert Trainer.CFG.FIXED_SPLIT_DIR == str(split_dir.resolve())


def test_boundary_focus_candidate_prioritizes_sem_geometry_over_sequence(tmp_path: Path, monkeypatch):
    module = load_module()
    monkeypatch.setattr(module, "_require_lab_assets", lambda: None)

    cfg = type("CFG", (), {})()

    class Trainer:
        CFG = cfg

        @staticmethod
        def _set_training_progress_root(path: str) -> None:
            Trainer.TRAINING_PROGRESS_ROOT_SET = path

    args = module.build_arg_parser().parse_args(
        [
            "--candidate",
            "r60_semtruth_boundary_focus",
            "--scratch",
            "--data-root",
            str(tmp_path),
            "--num-epoch",
            "4",
        ]
    )

    module.configure_trainer(Trainer, args, tmp_path / "r60_sem_truth_realcrop_anchor_train")

    assert Trainer.CFG.BOUNDARY_LOSS_WEIGHT >= 0.12
    assert Trainer.CFG.CENTERLINE_LOSS_WEIGHT >= 0.07
    assert Trainer.CFG.DISTANCE_EDGE_LOSS_WEIGHT >= 0.07
    assert Trainer.CFG.SEQ_ENABLE is False
    assert Trainer.CFG.SEQ_LOSS_WEIGHT == 0.0


def test_ensure_data_package_accepts_only_sem_truth_manifest(tmp_path: Path):
    module = load_module()
    package = tmp_path / "r60_sem_truth_realcrop_anchor_train"
    _write_r60_manifest(package)

    data_dir, loaded = module.ensure_data_package("r60_sem_truth_realcrop_anchor_train", tmp_path)

    assert data_dir == package
    assert loaded["r60_sem_truth_boundary_training"] is True
    assert loaded["target_is_sem_truth"] is True

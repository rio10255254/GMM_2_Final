from __future__ import annotations

import csv
import importlib.util
import sys
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "run_r60_automated_rounds.py"


def load_module():
    spec = importlib.util.spec_from_file_location("run_r60_automated_rounds", SCRIPT_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _touch(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"ckpt")


def _write_summary(path: Path, label: str, via_err: float, pillar_err: float) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = [
        {"image": label, "feature": "圓孔", "n": 119, "abs_radius_error_vs_sem_nm": via_err},
        {"image": label, "feature": "圓柱", "n": 130, "abs_radius_error_vs_sem_nm": pillar_err},
    ]
    with path.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=["image", "feature", "n", "abs_radius_error_vs_sem_nm"])
        writer.writeheader()
        writer.writerows(rows)


def test_discover_checkpoints_includes_best_latest_and_epochs(tmp_path: Path):
    module = load_module()
    run_dir = tmp_path / "training_progress_R60"
    _touch(run_dir / "weights" / "best_tradeoff.pth.tar")
    _touch(run_dir / "weights" / "latest.pth.tar")
    _touch(run_dir / "epoch_002.pth.tar")
    _touch(run_dir / "epoch_004.pth.tar")

    checkpoints = module.discover_checkpoints(run_dir, mode="all")
    labels = [item.label for item in checkpoints]

    assert labels == ["best_tradeoff", "latest", "epoch_002", "epoch_004"]
    assert len({item.path for item in checkpoints}) == 4


def test_build_reconstruct_command_disables_uncalibrated_psf_and_weak_psf(tmp_path: Path):
    module = load_module()
    checkpoint = tmp_path / "weights" / "latest.pth.tar"
    _touch(checkpoint)

    command = module.build_reconstruct_command(
        checkpoint=checkpoint,
        output_name="r60_eval_latest",
        input_dir=tmp_path / "input",
        recon_root=tmp_path / "recon",
        device="cuda:0",
    )

    joined = " ".join(command)
    assert "--weights" in command
    assert str(checkpoint) in command
    assert "--no-psf-from-ckpt" in command
    assert "--weak-psf-disable" in command
    assert "--psf-phys-alpha" in command
    assert "r60_eval_latest" in joined


def test_rank_cd_results_prefers_lower_mean_and_checks_reference_gate(tmp_path: Path):
    module = load_module()
    reference_summary = tmp_path / "reference.csv"
    _write_summary(reference_summary, "原圖", via_err=66.13, pillar_err=11.04)
    worse = tmp_path / "worse.csv"
    better = tmp_path / "better.csv"
    _write_summary(worse, "worse", via_err=86.0, pillar_err=45.0)
    _write_summary(better, "better", via_err=30.0, pillar_err=7.0)

    results = [
        module.MeasurementResult(label="worse", checkpoint_label="latest", summary_csv=worse),
        module.MeasurementResult(label="better", checkpoint_label="epoch_004", summary_csv=better),
    ]
    ranked = module.rank_cd_results(results, reference_summary_csv=reference_summary, reference_image="原圖")

    assert ranked[0].label == "better"
    assert ranked[0].mean_abs_radius_error_nm == 18.5
    assert ranked[0].beats_reference is True
    assert ranked[1].label == "worse"
    assert ranked[1].beats_reference is False

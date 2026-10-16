from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import torch


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "collect_training_runs.py"


def load_module():
    spec = importlib.util.spec_from_file_location("collect_training_runs", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def write_run(root: Path, name: str, terminal_epoch: int, best_epoch: int, score: float) -> Path:
    run = root / name
    weights = run / "weights"
    weights.mkdir(parents=True)
    (run / f"epoch_{terminal_epoch:03d}.pth.tar").write_bytes(b"complete")
    torch.save(
        {"epoch": best_epoch, "tradeoff_score": score, "state_dict": {}},
        weights / "best_tradeoff.pth.tar",
    )
    return run


def test_global_budget_selection_keeps_better_pre_extension_checkpoint(tmp_path):
    module = load_module()
    module.RUN_ROOT = tmp_path
    original = write_run(
        tmp_path,
        "training_progress_R63_MOSR_full_control_s1261200_original",
        terminal_epoch=40,
        best_epoch=40,
        score=150.0,
    )
    write_run(
        tmp_path,
        "training_progress_R63_MOSR_full_control_s1261200_extension",
        terminal_epoch=60,
        best_epoch=56,
        score=149.0,
    )
    role, checkpoint, selected_run = module.checkpoint_for("full_control", 1261200, 60)
    assert role == "best_tradeoff_global_budget"
    assert checkpoint == original / "weights" / "best_tradeoff.pth.tar"
    assert selected_run == original


def test_excluded_completed_run_is_not_selected(tmp_path):
    module = load_module()
    module.RUN_ROOT = tmp_path / "runs"
    module.RUN_ROOT.mkdir()
    excluded = write_run(
        module.RUN_ROOT,
        "training_progress_R63_MOSR_no_motion_consistency_s1261200_old",
        terminal_epoch=40,
        best_epoch=40,
        score=999.0,
    )
    valid = write_run(
        module.RUN_ROOT,
        "training_progress_R63_MOSR_no_motion_consistency_s1261200_new",
        terminal_epoch=40,
        best_epoch=36,
        score=100.0,
    )
    module.EXCLUSION_PATH = tmp_path / "excluded.json"
    module.EXCLUSION_PATH.write_text(
        json.dumps({"excluded_run_names": [excluded.name]}),
        encoding="utf-8",
    )
    selected = module.select_completed_run("no_motion_consistency", 1261200, 40)
    assert selected == valid

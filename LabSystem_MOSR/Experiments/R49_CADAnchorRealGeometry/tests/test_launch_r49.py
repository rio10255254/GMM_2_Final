from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "launch_r49.py"


def load_module():
    script_dir = SCRIPT_PATH.parent
    sys.path.insert(0, str(script_dir))
    spec = importlib.util.spec_from_file_location("launch_r49", SCRIPT_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_dry_run_reports_missing_r49_data_without_starting_trainer(tmp_path: Path, capsys):
    module = load_module()
    checkpoint = tmp_path / "best_tradeoff.pth.tar"
    checkpoint.write_bytes(b"fake")

    rc = module.main(
        [
            "--candidate",
            "r49_cad_anchor_r40_tradeoff",
            "--base-checkpoint",
            str(checkpoint),
            "--data-root",
            str(tmp_path / "missing_data_root"),
            "--num-epoch",
            "100",
            "--dry-run",
        ]
    )

    out = capsys.readouterr().out
    assert rc == 0
    assert '"training_ready": false' in out
    assert "data package is not ready" in out
    assert "missing_data_root" in out
    assert '"r49_cad_anchor_train_4000"' in out
    assert '"num_epoch": 100' in out
    assert '"boundary_geom_enable": true' in out

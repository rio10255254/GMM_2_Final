"""The trainer writes its runs under Experiments/Training_Runs when it runs from the project."""
from __future__ import annotations

import ast
import os
from pathlib import Path

TRAINER = Path(__file__).resolve().parents[1] / "GeoEdgeAlignSR_v1_Train_v5_NoCoord_return_v2_SimpleTest.py"


def test_default_training_output_dir():
    tree = ast.parse(TRAINER.read_text(encoding="utf-8"))
    func = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "_default_training_progress_root")
    project_root = Path(__file__).resolve().parents[2]
    scope = {"Path": Path, "os": os, "PROJECT_ROOT": str(project_root), "PACKAGE_ROOT": str(project_root.parent)}
    exec(compile(ast.Module(body=[func], type_ignores=[]), str(TRAINER), "exec"), scope)
    assert Path(scope["_default_training_progress_root"]()) == project_root / "Experiments" / "Training_Runs"

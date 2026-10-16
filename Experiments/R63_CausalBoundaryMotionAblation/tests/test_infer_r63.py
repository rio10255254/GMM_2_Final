from __future__ import annotations

import importlib.util
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "infer_r63.py"


def test_wrapper_imports_without_loading_model():
    spec = importlib.util.spec_from_file_location("infer_r63", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module.DEFAULT_PACKAGE_ROOT.name == "V42_SoftLabelSNR_FullStandalone_20260709"

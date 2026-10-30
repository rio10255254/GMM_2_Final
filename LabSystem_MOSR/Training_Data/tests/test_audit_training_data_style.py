from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import numpy as np


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "audit_training_data_style.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("audit_training_data_style", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_hard_binary_label_is_flagged_as_fake_style() -> None:
    mod = _load_module()
    src = np.full((32, 32), 120, dtype=np.uint8)
    src[:, 16:] = 160
    lbl = np.zeros((32, 32), dtype=np.uint8)
    lbl[:, 16:] = 255

    metrics = mod.measure_pair_style(src, lbl)
    verdict = mod.classify_pair_style(metrics)

    assert metrics["lbl_saturation_frac"] > 0.95
    assert "hard_binary_label" in verdict["flags"]
    assert verdict["risk"] == "high"


def test_source_style_label_is_not_flagged_as_hard_binary() -> None:
    mod = _load_module()
    x = np.linspace(95, 175, 32, dtype=np.float32)
    src = np.tile(x, (32, 1)).astype(np.uint8)
    lbl = np.clip(src.astype(np.int16) + 4, 0, 255).astype(np.uint8)

    metrics = mod.measure_pair_style(src, lbl)
    verdict = mod.classify_pair_style(metrics)

    assert metrics["lbl_saturation_frac"] == 0
    assert "hard_binary_label" not in verdict["flags"]
    assert verdict["risk"] in {"low", "medium"}

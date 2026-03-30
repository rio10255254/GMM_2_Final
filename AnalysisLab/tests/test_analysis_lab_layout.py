from __future__ import annotations

import json
from pathlib import Path


def test_analysis_lab_root_contract():
    root = Path(__file__).resolve().parents[1]

    assert (root / "README.md").exists()
    index_path = root / "index.json"
    assert index_path.exists()
    assert root.parent.name != "Experiments"

    data = json.loads(index_path.read_text(encoding="utf-8"))
    assert "versions" in data
    assert "r26" in data["versions"]
    assert data["entry_point"] == "AnalysisLab/README.md"


def test_r26_single_image_and_sequence_contract():
    root = Path(__file__).resolve().parents[1] / "r26"

    for analysis_kind in ("single_image", "sequence"):
        analysis_root = root / analysis_kind
        assert (analysis_root / "README.md").exists()
        assert (analysis_root / "scripts").is_dir()
        assert (analysis_root / "tests").is_dir()
        assert (analysis_root / "results").is_dir()
        assert (analysis_root / "reports").is_dir()

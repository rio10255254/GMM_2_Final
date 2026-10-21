from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path

import pandas as pd
import pytest


PACKAGE = Path(__file__).resolve().parents[1]
SCRIPTS = PACKAGE / "scripts"
sys.path.insert(0, str(SCRIPTS))

from build_thesis_50x20x_package import build_thesis_package  # noqa: E402


EXPECTED_SEQUENCES = {
    "50x_x_0p5um",
    "50x_x_1um",
    "20x_0p5um",
    "20x_1um",
}


def _protected_digest() -> str:
    files = [PACKAGE / "REPORT.md", PACKAGE / "manifest.json", PACKAGE / "reproducibility_sha256.csv"]
    files.extend(path for root in (PACKAGE / "cd", PACKAGE / "displacement") for path in root.rglob("*") if path.is_file())
    digest = hashlib.sha256()
    for path in sorted(files, key=lambda item: str(item).lower()):
        digest.update(str(path.relative_to(PACKAGE)).encode("utf-8"))
        digest.update(path.read_bytes())
    return digest.hexdigest()


def test_thesis_package_contains_only_the_four_approved_sequences(tmp_path: Path) -> None:
    before = _protected_digest()
    outputs = build_thesis_package(output_root=tmp_path)
    after = _protected_digest()

    assert before == after
    summary = pd.read_csv(outputs["summary"])
    assert len(summary) == 4
    assert set(summary["sequence"]) == EXPECTED_SEQUENCES
    assert summary["sequence"].is_unique

    corrected = summary.set_index("sequence").loc["50x_x_0p5um"]
    assert corrected["raw_valid_steps"] == 48
    assert corrected["v42_valid_steps"] == 48
    assert corrected["raw_signed_step_sd_nm"] == pytest.approx(8.03105, abs=0.02)
    assert corrected["v42_signed_step_sd_nm"] == pytest.approx(6.18281, abs=0.02)
    assert corrected["excluded_cross_session_pairs"] == 2
    assert corrected["session_count"] == 3

    manifest = json.loads(outputs["manifest"].read_text(encoding="utf-8"))
    assert set(manifest["sequences"]) == EXPECTED_SEQUENCES
    assert manifest["corrected_sequence"] == "50x_x_0p5um"


def test_thesis_package_has_no_low_magnification_reference(tmp_path: Path) -> None:
    build_thesis_package(output_root=tmp_path)
    forbidden = re.compile(r"(?<![0-9])5x(?![0-9])", re.IGNORECASE)

    for path in tmp_path.rglob("*"):
        assert not forbidden.search(path.name), path
        if path.suffix.lower() in {".csv", ".json", ".md", ".txt"}:
            assert not forbidden.search(path.read_text(encoding="utf-8")), path


def test_thesis_package_exports_required_tables_figures_and_report(tmp_path: Path) -> None:
    outputs = build_thesis_package(output_root=tmp_path)

    required = {
        "summary",
        "corrected_steps",
        "pair_audit",
        "before_after",
        "stability_figure",
        "grid_figure",
        "before_after_figure",
        "corrected_trace_figure",
        "gap_figure",
        "anchor_figure",
        "report",
        "manifest",
    }
    assert required.issubset(outputs)
    assert all(outputs[name].is_file() for name in required)
    pairs = pd.read_csv(outputs["pair_audit"])
    assert len(pairs) == 50
    assert int(pairs["included_within_session"].sum()) == 48
    before_after = pd.read_csv(outputs["before_after"])
    assert set(before_after["analysis_version"]) == {
        "old_unsegmented",
        "corrected_timestamp_sessions",
    }

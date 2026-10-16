from __future__ import annotations

import csv
import gzip
import importlib.util
import json
import sys
from pathlib import Path


REPO = Path(__file__).resolve().parents[2]
MODULE_PATH = REPO / "Tools" / "project_file_inventory.py"


def load_module():
    spec = importlib.util.spec_from_file_location("project_file_inventory", MODULE_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_extension_and_category_classification():
    module = load_module()
    assert module.normalized_extension("model.pth.tar") == ".pth.tar"
    assert module.normalized_extension("README") == "[no extension]"
    assert module.classify_category(".git/objects/aa/bb", "[no extension]") == "version_history"
    assert module.classify_category("Experiments/R99/results/x.csv", ".csv") == "experiments"
    assert module.classify_category("docs/operations/policy.md", ".md") == "documentation_and_governance"
    assert module.classify_category("a/__pycache__/x.pyc", ".pyc") == "cache_or_temporary"


def test_complete_inventory_writes_searchable_artifacts(tmp_path):
    module = load_module()
    root = tmp_path / "project"
    output = tmp_path / "inventory"
    (root / "docs").mkdir(parents=True)
    (root / "Training_Data").mkdir()
    (root / ".git" / "objects").mkdir(parents=True)
    (root / "docs" / "guide.md").write_text("# Guide title\n\nBody\n", encoding="utf-8")
    (root / "Training_Data" / "sample.bin").write_bytes(b"12345")
    (root / ".git" / "objects" / "item").write_bytes(b"git")

    summary = module.scan(root, output, largest_limit=10, duplicate_min_bytes=1)

    assert summary["totals"]["files"] == 3
    assert summary["totals"]["documents"] == 1
    assert summary["totals"]["scan_errors"] == 0
    assert (output / "summary.json").exists()
    assert (output / "artifact_checksums_sha256.csv").exists()

    parsed = json.loads((output / "summary.json").read_text(encoding="utf-8"))
    assert parsed["scope"]["includes_git_internals"] is True
    assert parsed["scope"]["follows_reparse_points"] is False

    with gzip.open(output / "documents.csv.gz", "rt", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert rows == [
        {
            "relative_path": "docs/guide.md",
            "extension": ".md",
            "size_bytes": str((root / "docs" / "guide.md").stat().st_size),
            "modified_utc": rows[0]["modified_utc"],
            "category": "documentation_and_governance",
            "title_hint": "Guide title",
        }
    ]


def test_output_must_be_outside_project(tmp_path):
    module = load_module()
    root = tmp_path / "project"
    root.mkdir()
    try:
        module.scan(root, root / "inventory", largest_limit=10, duplicate_min_bytes=1)
    except ValueError as exc:
        assert "outside" in str(exc)
    else:
        raise AssertionError("Expected output-inside-project guard to reject the scan")


def test_existing_output_is_never_overwritten(tmp_path):
    module = load_module()
    root = tmp_path / "project"
    output = tmp_path / "inventory"
    root.mkdir()
    output.mkdir()
    marker = output / "keep.txt"
    marker.write_text("existing", encoding="utf-8")

    try:
        module.scan(root, output, largest_limit=10, duplicate_min_bytes=1)
    except FileExistsError:
        pass
    else:
        raise AssertionError("Expected an existing output directory to be rejected")

    assert marker.read_text(encoding="utf-8") == "existing"


def test_same_size_large_files_are_candidates_not_declared_duplicates(tmp_path):
    module = load_module()
    root = tmp_path / "project"
    output = tmp_path / "inventory"
    root.mkdir()
    (root / "a.bin").write_bytes(b"A" * 64)
    (root / "b.bin").write_bytes(b"B" * 64)

    summary = module.scan(root, output, largest_limit=10, duplicate_min_bytes=64)

    assert summary["large_same_size_candidates"]["groups"] == 1
    assert summary["large_same_size_candidates"]["files"] == 2
    with (output / "large_same_size_candidates.csv").open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert [row["relative_path"] for row in rows] == ["a.bin", "b.bin"]
    assert "not proof" in summary["large_same_size_candidates"]["note"]

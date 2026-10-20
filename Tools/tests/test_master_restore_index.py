"""Exercise original-path preservation, especially relocated current results."""
import gzip
import hashlib
import importlib.util
import json
import sys
from pathlib import Path

import pytest

TOOLS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOLS))
spec = importlib.util.spec_from_file_location("master_builder", TOOLS / "build_project_restore_index.py")
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)


def dump(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.suffix == ".gz":
        with gzip.open(path, "wt", encoding="utf-8") as stream:
            json.dump(value, stream)
    else:
        path.write_text(json.dumps(value), encoding="utf-8")


def item(path, content, **extra):
    value = content.encode()
    return {"path": path, "bytes": len(value), "sha256": hashlib.sha256(value).hexdigest(), **extra}


def fixture(tmp_path, monkeypatch, conflicting_git_source=False):
    root, op, out = tmp_path / "source", tmp_path / "operation", tmp_path / "master"
    current = item("README.md", "current guide")
    old_guide = item("README.md", "earlier guide")
    older_guide = item("README.md", "oldest guide")
    old_array = item("data/fixed.npy", "old array")
    current_array = item("__archive_objects__/new_array", "current array")
    old_image = item("results/centers/image.bmp", "old image")
    current_image = item("__archive_objects__/new_image", "current image")
    files = [old_guide, older_guide, old_array, current_array, old_image, current_image]
    for row in files:
        row["asset"] = "fixture.zip"
    archive_manifest = {"state": "complete", "files": files, "assets": [{"name": "fixture.zip", "sha256": "f" * 64, "bytes": 100}]}
    dump(op / "training_history_bundle/RESEARCH_ASSETS.json.gz", archive_manifest)
    dump(op / "context_batch_001_bundle/RESEARCH_ASSETS.json.gz", {"state": "complete", "files": [], "assets": []})
    dump(op / "GITHUB_CONTEXT_FAST_ISOLATED_GUARD.json", {"status": "PASS"})
    dump(op / "FIRST_SOURCE_COMMIT.json", {"files": []})
    dump(root / "docs/reproducibility/REPOSITORY_FILES.json.gz", {"source_snapshot_commit": "fixture", "files": [current]})
    dump(root / "docs/reproducibility/experiment_index.json", [])
    archive = Path(r"H:\GMM_2_Final_Archive")
    target = archive / "active_runs/test_current/centers"
    dump(root / "docs/reproducibility/project_completion/HISTORICAL_PATH_PROJECTIONS.json", {"projections": [{
        "archive_relative_prefix": "active_runs/test_current/centers", "project_prefix": "results/centers",
        "scope": "test", "projection_role": "current_registered_H_reference"}]})

    def captured(original, logical, source, origin):
        return {**original, "logical_path": logical, "source": str(source), "origin": origin,
                "scope": "test", "kind": "result_numeric"}

    rows = {
        "context": [captured(old_guide, "README.md", root / "README.md", "D_worktree")] if conflicting_git_source else [],
        "models": [],
        # A later current H reference must win over older archived contents,
        # while retaining that older content at a distinct historical path.
        "numeric": [captured(old_array, "data/fixed.npy", archive / "experiments/old/snapshot/fixed.npy", "H_snapshot"),
                    captured(current_array, "data/fixed.npy", archive / "active_runs/test_current/fixed.npy", "registered_H_reference")],
        # One physical H target is used through two original result paths.
        "images": [captured(current_image, "results_local/centers/image.bmp", target / "image.bmp", "registered_H_reference")],
        "packages": [],
    }
    for family, values in rows.items():
        with gzip.open(op / ("HASHED_" + family.upper() + "_FILES.jsonl.gz"), "wt", encoding="utf-8") as stream:
            for value in values:
                stream.write(json.dumps(value) + "\n")
    dump(op / "ALL_RESEARCH_CONTENT_HASHED.json", {"status": "ALL_REQUESTED_FAMILIES_CONTENT_CHECKED",
         "families": [{"family": family, "files": len(values)} for family, values in rows.items()]})
    for family in ["model", "numeric", "image", "package"]:
        dump(op / (family + "_batches") / "PLAN.json", {"tag": "fixture-" + family, "batches": []})
    monkeypatch.setattr(builder, "known_manifests", lambda root, archive: [])
    monkeypatch.setattr(builder, "git_tree", lambda root, ref: {"README.md": "a" * 40})
    monkeypatch.setattr(builder.subprocess, "check_output", lambda *args, **kwargs: gzip.compress(json.dumps({"source_snapshot_commit": "fixture-old", "files": [old_guide]}).encode()))
    monkeypatch.setattr(sys, "argv", ["builder", "--root", str(root), "--operation", str(op), "--output", str(out)])
    return out, current_array, current_image, old_guide, older_guide


def test_current_relocated_results_and_both_older_source_versions_survive(tmp_path, monkeypatch):
    out, array, image, old_guide, older_guide = fixture(tmp_path, monkeypatch)
    builder.main()
    rows = []
    for path in out.glob("RESTORE_*.json.gz"):
        rows.extend(builder.read(path)["files"])
    aliases = builder.read(out / "REPOSITORY_CONTENT_ALIASES.json.gz")["files"]
    locations = {row["path"]: row["sha256"] for row in rows + aliases}
    assert locations["data/fixed.npy"] == array["sha256"]
    assert locations["results/centers/image.bmp"] == image["sha256"]
    assert locations["results_local/centers/image.bmp"] == image["sha256"]
    assert {old_guide["sha256"], older_guide["sha256"]} <= {
        sha for path, sha in locations.items() if path.startswith("Historical_Publications/") and path.endswith("README.md")
    }
    assert not any(path.startswith("__archive_objects__/") for path in locations)


def test_changed_current_source_requires_review(tmp_path, monkeypatch):
    fixture(tmp_path, monkeypatch, conflicting_git_source=True)
    with pytest.raises(ValueError, match="Current Git source differs"):
        builder.main()


def test_receipt_from_a_different_object_set_cannot_approve_a_component():
    row = item("data/original.npy", "original observation")
    part = {"name": "original.zip", "bytes": 123, "sha256": "a" * 64}
    manifest = {"files": [row], "assets": [part]}
    valid = {"status": "PASS_FILE_IDENTITY_AND_RESTORATION", "assets": [part],
             "checks": [{**row, "exact_file_bytes_restored": True}]}
    builder.verify_exact_batch_receipt(manifest, valid)
    wrong = {**valid, "checks": [{**item("data/other.npy", "different observation"), "exact_file_bytes_restored": True}]}
    with pytest.raises(ValueError, match="exact declared objects"):
        builder.verify_exact_batch_receipt(manifest, wrong)

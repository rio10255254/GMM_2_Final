from __future__ import annotations

import csv
import importlib.util
import os
import sys
from pathlib import Path

import pytest


REPO = Path(__file__).resolve().parents[2]
GUARD_PATH = REPO / "Tools" / "project_storage_guard.py"


def load_guard_module():
    spec = importlib.util.spec_from_file_location("project_storage_guard", GUARD_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_classify_free_space_uses_two_guardrails():
    guard = load_guard_module()

    assert guard.classify_free_space(350, warning=300, critical=150) == "OK"
    assert guard.classify_free_space(250, warning=300, critical=150) == "WARN"
    assert guard.classify_free_space(100, warning=300, critical=150) == "CRITICAL"


def test_resolve_inside_rejects_escape(tmp_path: Path):
    guard = load_guard_module()

    assert guard.resolve_inside(tmp_path, "inside") == (tmp_path / "inside").resolve()
    with pytest.raises(ValueError):
        guard.resolve_inside(tmp_path, "../outside")


def test_parse_git_count_objects_reads_numeric_fields():
    guard = load_guard_module()

    parsed = guard.parse_git_count_objects("count: 10\nsize: 20\ngarbage: 1\nsize-garbage: 30\n")

    assert parsed == {"count": 10, "size": 20, "garbage": 1, "size-garbage": 30}


def test_process_exists_detects_current_process():
    guard = load_guard_module()

    assert guard.process_exists(os.getpid()) is True


def test_iter_files_skips_directory_symlinks_when_available(tmp_path: Path):
    guard = load_guard_module()
    source = tmp_path / "source"
    target = tmp_path / "target"
    source.mkdir()
    target.mkdir()
    (source / "kept.txt").write_text("kept", encoding="utf-8")
    (target / "linked.txt").write_text("linked", encoding="utf-8")
    link = source / "linked_dir"
    try:
        link.symlink_to(target, target_is_directory=True)
    except OSError:
        pytest.skip("directory symlinks are unavailable on this Windows setup")

    files = [path.relative_to(source).as_posix() for path in guard.iter_files(source)]

    assert files == ["kept.txt"]


def test_archive_storage_requires_separate_ready_root(tmp_path: Path):
    guard = load_guard_module()
    archive = tmp_path / "archive"
    archive.mkdir()

    result = guard.archive_storage(tmp_path, {"archive": {"root": str(archive), "minimum_free_gib": 0}})

    assert result["configured"] is True
    assert result["exists"] is True
    assert result["same_device_as_repository"] is True
    assert result["ready"] is False


def test_manifest_roundtrip_and_mismatch_detection(tmp_path: Path):
    guard = load_guard_module()
    source = tmp_path / "source"
    source.mkdir()
    (source / "a.txt").write_text("alpha", encoding="utf-8")
    nested = source / "nested"
    nested.mkdir()
    (nested / "b.txt").write_text("beta", encoding="utf-8")
    manifest = tmp_path / "manifest.csv"

    assert guard.create_manifest(source, manifest, use_hash=True) == 2
    result = guard.verify_manifest(manifest, source)
    assert result == {"status": "PASS", "checked": 2, "missing": [], "mismatched": []}

    (nested / "b.txt").write_text("changed", encoding="utf-8")
    result = guard.verify_manifest(manifest, source)
    assert result["status"] == "FAIL"
    assert result["mismatched"] == ["nested/b.txt"]

    with manifest.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert {row["relative_path"] for row in rows} == {"a.txt", "nested/b.txt"}


def test_find_active_runs_recognizes_live_marker(tmp_path: Path):
    guard = load_guard_module()
    marker = tmp_path / "Experiments" / "R1" / "runs" / "launcher_logs" / "active_formal_run.json"
    marker.parent.mkdir(parents=True)
    marker.write_text(
        '{"experiment_id":"R1","status":"running","process_id":%d}' % os.getpid(),
        encoding="utf-8",
    )

    runs = guard.find_active_runs(
        tmp_path,
        {"active_marker_globs": ["Experiments/*/runs/launcher_logs/active_formal_run.json"]},
    )

    assert runs[0]["marker_state"] == "ACTIVE"
    assert guard.active_run_ids(runs) == ["R1"]
    assert guard.blocking_run_ids(runs) == ["R1"]


def test_active_marker_without_pid_is_unverified_and_blocks(tmp_path: Path):
    guard = load_guard_module()
    marker = tmp_path / "Experiments" / "R2" / "runs" / "active_run.json"
    marker.parent.mkdir(parents=True)
    marker.write_text(
        '{"experiment_id":"R2","status":"active","completed_epoch":9,"planned_epochs":48}',
        encoding="utf-8",
    )
    policy = {"active_marker_globs": ["Experiments/*/runs/active_run.json"]}

    runs = guard.find_active_runs(tmp_path, policy)

    assert runs[0]["marker_state"] == "UNVERIFIED_ACTIVE"
    assert guard.active_run_ids(runs) == []
    assert guard.blocking_run_ids(runs) == ["R2"]


@pytest.mark.parametrize("content", ['{"status":"running"}', "{invalid json"])
def test_external_junction_marker_keeps_logical_path_and_blocks(tmp_path: Path, content: str):
    guard = load_guard_module()
    repo = tmp_path / "repo"
    external = tmp_path / "external"
    external.mkdir()
    marker = external / "active_formal_run.json"
    marker.write_text(content, encoding="utf-8")
    alias = repo / "Experiments" / "R147" / "runs" / "launcher_logs"
    alias.parent.mkdir(parents=True)
    if os.name == "nt":
        import _winapi
        _winapi.CreateJunction(str(external), str(alias))
    else:
        alias.symlink_to(external, target_is_directory=True)
    runs = guard.find_active_runs(
        repo, {"active_marker_globs": ["Experiments/*/runs/launcher_logs/active_formal_run.json"]}
    )
    assert len(runs) == 1
    assert runs[0]["marker"] == str(Path("Experiments/R147/runs/launcher_logs/active_formal_run.json"))
    assert runs[0]["physical_marker"] == str(marker.resolve())
    assert runs[0]["external_marker"] is True
    assert runs[0]["marker_state"] in {"UNVERIFIED_ACTIVE", "ERROR"}
    assert guard.blocking_run_ids(runs)


@pytest.mark.parametrize(
    ("status", "expected_state", "blocks"),
    [
        ("complete", "INACTIVE", False),
        ("stopped_by_user", "INCOMPLETE", True),
        ("unexpected_state", "UNKNOWN", True),
    ],
)
def test_marker_terminal_and_unresolved_states(status: str, expected_state: str, blocks: bool):
    guard = load_guard_module()

    state = guard.classify_run_marker(status, pid=0, process_alive=False, policy={})
    runs = [{"experiment_id": "R3", "marker_state": state}]

    assert state == expected_state
    assert bool(guard.blocking_run_ids(runs)) is blocks


def test_lifecycle_audit_blocks_bulk_actions_during_active_run(tmp_path: Path):
    guard = load_guard_module()
    (tmp_path / "payload").mkdir()
    marker = tmp_path / "Experiments" / "R1" / "runs" / "launcher_logs" / "active_formal_run.json"
    marker.parent.mkdir(parents=True)
    marker.write_text(
        '{"experiment_id":"R1","status":"running","process_id":%d}' % os.getpid(),
        encoding="utf-8",
    )
    policy = {
        "active_marker_globs": ["Experiments/*/runs/launcher_logs/active_formal_run.json"],
        "bulk_action_guard": {
            "block_when_active_run": True,
            "blocked_actions": ["archive_by_round"],
        },
    }
    registry = {
        "allowed_tiers": ["archive"],
        "entries": [
            {
                "id": "payload",
                "path": "payload",
                "tier": "archive",
                "action": "archive_by_round",
            }
        ],
    }

    result = guard.lifecycle_audit(tmp_path, policy, registry)

    assert result["status"] == "PASS"
    assert result["bulk_actions_blocked"] is True
    assert result["active_runs"] == ["R1"]
    assert result["run_blockers"] == ["R1"]
    assert result["entries"][0]["blocked_by_active_run"] is True


def test_lifecycle_audit_blocks_unverified_compatibility_marker(tmp_path: Path):
    guard = load_guard_module()
    (tmp_path / "payload").mkdir()
    marker = tmp_path / "Experiments" / "R2" / "runs" / "active_run.json"
    marker.parent.mkdir(parents=True)
    marker.write_text('{"experiment_id":"R2","status":"active"}', encoding="utf-8")
    policy = {
        "active_marker_globs": ["Experiments/*/runs/active_run.json"],
        "bulk_action_guard": {
            "block_when_active_run": True,
            "blocked_actions": ["archive_by_round"],
        },
    }
    registry = {
        "allowed_tiers": ["archive"],
        "entries": [
            {"id": "payload", "path": "payload", "tier": "archive", "action": "archive_by_round"}
        ],
    }

    result = guard.lifecycle_audit(tmp_path, policy, registry)

    assert result["active_runs"] == []
    assert result["run_blockers"] == ["R2"]
    assert result["bulk_actions_blocked"] is True
    assert result["entries"][0]["blocked_by_active_run"] is True


def test_validate_registry_rejects_duplicate_ids_and_paths():
    guard = load_guard_module()
    registry = {
        "allowed_tiers": ["formal"],
        "entries": [
            {"id": "same", "path": "one", "tier": "formal"},
            {"id": "same", "path": "one", "tier": "wrong"},
        ],
    }

    errors = guard.validate_registry(registry)

    assert "duplicate id: same" in errors
    assert "duplicate path: one" in errors
    assert "entry same has invalid tier: wrong" in errors


def test_lifecycle_audit_labels_expected_removal(tmp_path: Path):
    guard = load_guard_module()
    policy = {"active_marker_globs": [], "bulk_action_guard": {}}
    registry = {
        "allowed_tiers": ["rebuildable"],
        "entries": [
            {
                "id": "removed",
                "path": "removed",
                "tier": "rebuildable",
                "action": "quarantine_complete",
                "expected_exists": False,
            }
        ],
    }

    result = guard.lifecycle_audit(tmp_path, policy, registry)

    assert result["entries"][0]["presence_state"] == "removed_as_planned"


@pytest.mark.parametrize("declaration", ["correct", "missing", "mismatch"])
def test_lifecycle_audit_external_junction_requires_exact_registration(tmp_path: Path, declaration: str):
    guard = load_guard_module()
    repo = tmp_path / "repo"
    archive = tmp_path / "archive"
    physical = archive / "payload"
    repo.mkdir()
    physical.mkdir(parents=True)
    alias = repo / "linked_payload"
    if os.name == "nt":
        import _winapi
        _winapi.CreateJunction(str(physical), str(alias))
    else:
        alias.symlink_to(physical, target_is_directory=True)
    item = {"id": "linked", "path": "linked_payload", "tier": "archive", "action": "protect"}
    if declaration != "missing":
        item["physical_path"] = str(physical if declaration == "correct" else archive / "wrong")
    policy = {"active_marker_globs": [], "archive": {"root": str(archive)}}
    result = guard.lifecycle_audit(repo, policy, {"allowed_tiers": ["archive"], "entries": [item]})
    if declaration == "correct":
        assert result["status"] == "PASS"
        assert result["entries"][0]["external_storage"] is True
        assert result["entries"][0]["exists"] is True
    else:
        assert result["status"] == "FAIL"
    with pytest.raises(ValueError):
        guard.resolve_inside(repo, "linked_payload")

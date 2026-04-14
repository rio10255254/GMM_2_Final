from __future__ import annotations

import importlib.util
from pathlib import Path


REPO = Path(__file__).resolve().parents[2]
CONTROL_CENTER_PATH = REPO / "Tools" / "project_control_center.py"


def load_control_center_module():
    spec = importlib.util.spec_from_file_location("project_control_center", CONTROL_CENTER_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec is not None
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_default_cli_overview_uses_quick_health_summary():
    module = load_control_center_module()

    args = module.parse_args([])

    assert args.view == "overview"
    assert args.format == "text"
    assert module.resolve_health_level(args) == "quick"
    assert module.resolve_requested_modules(args) == []


def test_health_view_defaults_to_standard_and_preserves_modules():
    module = load_control_center_module()

    args = module.parse_args(["--view", "health", "--module", "docs", "--module", "python"])

    assert args.view == "health"
    assert module.resolve_health_level(args) == "standard"
    assert module.resolve_requested_modules(args) == ["docs", "python"]


def test_payload_always_exposes_fixed_top_level_keys():
    module = load_control_center_module()

    payload = module.build_payload(REPO, view="truth", health_level="quick", requested_modules=[])

    assert set(payload) == {
        "summary",
        "truth_sources",
        "architecture",
        "entrypoints",
        "risks",
        "health",
    }


def test_docs_scan_detects_stale_legacy_runtime_path(tmp_path: Path):
    module = load_control_center_module()

    sample = tmp_path / "sample.md"
    sample.write_text(
        "legacy snapshot: docs/runtime/legacy/root_status/000_LONGRUN_ROUND32_STATUS.md\n",
        encoding="utf-8",
    )

    findings = module.scan_files_for_legacy_runtime_refs([sample])

    assert len(findings) == 1
    assert findings[0]["path"] == sample
    assert findings[0]["line_number"] == 1


def test_health_runner_keeps_collecting_results_after_failure():
    module = load_control_center_module()

    def fail_runner():
        return {
            "module": "docs",
            "status": "FAIL",
            "checks": [{"name": "legacy_runtime_refs", "status": "FAIL", "details": "stale path"}],
            "issues": ["stale path"],
        }

    def pass_runner():
        return {
            "module": "python",
            "status": "PASS",
            "checks": [{"name": "python_tests", "status": "PASS", "details": "ok"}],
            "issues": [],
        }

    results = module.run_health_modules(["docs", "python"], {"docs": fail_runner, "python": pass_runner})

    assert [item["module"] for item in results] == ["docs", "python"]
    assert results[0]["status"] == "FAIL"
    assert results[1]["status"] == "PASS"


def test_finalize_health_status_warns_for_dirty_start_and_fails_for_new_changes():
    module = load_control_center_module()

    warn_status = module.finalize_health_status(
        [
            {"module": "docs", "status": "PASS", "checks": [], "issues": []},
        ],
        started_dirty=True,
        new_tracked_changes=[],
    )
    assert warn_status["status"] == "WARN"

    fail_status = module.finalize_health_status(
        [
            {"module": "docs", "status": "PASS", "checks": [], "issues": []},
        ],
        started_dirty=False,
        new_tracked_changes=["README.md"],
    )
    assert fail_status["status"] == "FAIL"
    assert fail_status["new_tracked_changes"] == ["README.md"]

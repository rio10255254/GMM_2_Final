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


def test_command_preserves_utf8_and_native_windows_output(monkeypatch):
    """Native Big5 stderr must not crash a UTF-8 parent's reader thread."""
    import sys

    module = load_control_center_module()
    monkeypatch.setattr(module.locale, "getencoding", lambda: "cp950")
    result = module.run_command([
        sys.executable, "-c",
        "import sys;sys.stdout.buffer.write('原始照片'.encode('utf-8'));"
        "sys.stderr.buffer.write('位置紀錄'.encode('cp950'))",
    ])
    assert result["returncode"] == 0
    assert result["stdout"] == "原始照片"
    assert result["stderr"] == "位置紀錄"


def test_recent_direct_report_record_is_available_in_both_views():
    module = load_control_center_module()
    policy = {
        "formal_baseline": {
            "candidate_id": "COMBO", "model_name": "combo",
            "decision_effective_date": "2026-04-08",
            "reports": {"results_md": "Experiments/R38v2SeqFixed/reports/COMBO_RESULTS.md"},
        },
        "approved_alternates": [], "closed_lines": [],
        "open_side_tracks": [{"candidate_id": "R139", "status": "complete_degenerate_not_adopted",
                              "report": "Experiments/R139_UNetRecurrentPrototype/reports/R139_RESULTS.md"}],
    }
    truth = module.build_truth_sources(REPO, policy, {"versions": {}})
    assert truth["open_side_tracks"][0]["report"].endswith("/R139_RESULTS.md")
    architecture = module.build_architecture_view(policy)
    assert architecture["side_tracks"][0]["location"] == "Experiments/R139_UNetRecurrentPrototype"
    assert architecture["side_tracks"][0]["status"] == "complete_degenerate_not_adopted"


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
    requested_modules = module.resolve_requested_modules(args)
    assert module.resolve_health_level(args, requested_modules) == "standard"
    assert requested_modules == ["docs", "python"]


def test_health_view_promotes_matlab_module_to_deep():
    module = load_control_center_module()

    args = module.parse_args(["--view", "health", "--module", "matlab"])

    requested_modules = module.resolve_requested_modules(args)
    assert requested_modules == ["matlab"]
    assert module.resolve_health_level(args, requested_modules) == "deep"


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


def test_storage_guard_is_a_declared_entrypoint():
    module = load_control_center_module()

    entrypoints = module.build_entrypoints_view()["items"]
    storage = next(item for item in entrypoints if item["id"] == "storage_guard")

    assert storage["exists"] is True
    assert storage["path"] == "Tools/project_storage_guard.py"


def test_archive_index_is_a_core_document():
    module = load_control_center_module()

    assert module.ARCHIVE_INDEX_PATH in module.CORE_DOC_PATHS
    assert module.ARCHIVE_INDEX_PATH.is_file()


def test_storage_registry_and_lifecycle_are_core_documents():
    module = load_control_center_module()

    assert module.STORAGE_REGISTRY_PATH in module.CORE_DOC_PATHS
    assert module.STORAGE_LIFECYCLE_PATH in module.CORE_DOC_PATHS
    assert module.STORAGE_REGISTRY_PATH.is_file()
    assert module.STORAGE_LIFECYCLE_PATH.is_file()
    assert module.QUARANTINE_INDEX_PATH in module.CORE_DOC_PATHS
    assert module.QUARANTINE_INDEX_PATH.is_file()


def test_truth_sources_expose_analysis_summary():
    module = load_control_center_module()

    payload = module.build_payload(REPO, view="truth", health_level="quick", requested_modules=[])

    analysis = payload["truth_sources"]["analysis"]
    assert analysis["entry_point"] == "AnalysisLab/README.md"
    assert analysis["layout_policy"] == "version_first"
    assert analysis["versions"][0]["version"] == "r26"
    assert analysis["versions"][0]["analysis_count"] >= 1


def test_truth_sources_accept_open_side_track_results_report():
    module = load_control_center_module()

    policy = {
        "formal_baseline": {
            "candidate_id": "COMBO",
            "model_name": "combo",
            "decision_effective_date": "2026-04-08",
            "reports": {"results_md": "Experiments/R38v2SeqFixed/reports/COMBO_RESULTS.md"},
        },
        "approved_alternates": [],
        "open_side_tracks": [
            {
                "candidate_id": "R41_direct_best",
                "status": "weight_sweep_complete_no_guarded_tradeoff",
                "reports": {"results_md": "Experiments/R41_RingDistillation/reports/R41_RESULTS.md"},
            }
        ],
    }
    analysis_index = {"entry_point": "AnalysisLab/README.md", "layout_policy": "version_first", "versions": {}}

    sources = module.build_truth_sources(REPO, policy, analysis_index)

    assert sources["open_side_tracks"][0]["report"] == "Experiments/R41_RingDistillation/reports/R41_RESULTS.md"


def test_truth_sources_accept_approved_alternate_capability_eval_report():
    module = load_control_center_module()

    policy = {
        "formal_baseline": {
            "candidate_id": "COMBO",
            "model_name": "combo",
            "decision_effective_date": "2026-04-08",
            "reports": {"results_md": "Experiments/R38v2SeqFixed/reports/COMBO_RESULTS.md"},
        },
        "approved_alternates": [
            {
                "candidate_id": "R39R40_avg_a025",
                "model_name": "r39r40_complementary_avg_a025",
                "reports": {
                    "capability_eval_md": (
                        "Experiments/R39_ShapeGeneralization/results/a030_x_a043_sweep/"
                        "reports/R39R40_AVG_a025_CAPABILITY_EVAL.md"
                    ),
                    "external_compare_md": (
                        "Experiments/R39_ShapeGeneralization/results/a030_x_a043_sweep/"
                        "reports/R39R40_AVG_a025_EXTERNAL_COMPARE.md"
                    ),
                },
            }
        ],
        "open_side_tracks": [],
    }
    analysis_index = {"entry_point": "AnalysisLab/README.md", "layout_policy": "version_first", "versions": {}}

    sources = module.build_truth_sources(REPO, policy, analysis_index)

    assert sources["approved_alternates"][0]["report"] == (
        "Experiments/R39_ShapeGeneralization/results/a030_x_a043_sweep/"
        "reports/R39R40_AVG_a025_CAPABILITY_EVAL.md"
    )


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


def test_risks_view_requires_exact_control_commands(tmp_path: Path, monkeypatch):
    module = load_control_center_module()

    workflow = tmp_path / "validate-governance.yml"
    workflow.write_text(
        "run: python Tools/project_control_center.py --view health\n",
        encoding="utf-8",
    )
    hook = tmp_path / "pre-commit"
    hook.write_text(
        "python Tools/validate_project_structure.py\n",
        encoding="utf-8",
    )
    aggregate = tmp_path / "vlab_aggregate_existing_results.m"
    aggregate.write_text(
        "parser.addParameter('output_root', fullfile(char(lab_root), 'outputs'));\n",
        encoding="utf-8",
    )
    smoke = tmp_path / "run_matlab_smoke_tests.m"
    smoke.write_text(
        "% smoke tests without isolated output override\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(module, "WORKFLOW_PATH", workflow)
    monkeypatch.setattr(module, "PRE_COMMIT_TEMPLATE_PATH", hook)
    monkeypatch.setattr(module, "MATLAB_AGGREGATE_SCRIPT_PATH", aggregate)
    monkeypatch.setattr(module, "MATLAB_SMOKE_TEST_PATH", smoke)

    risks = module.build_risks_view(REPO)
    items = {item["id"]: item for item in risks["items"]}

    assert items["ci_scope"]["status"] == "ACTIVE"
    assert items["local_guardrail_scope"]["status"] == "ACTIVE"
    assert items["matlab_tracked_output_coupling"]["status"] == "ACTIVE"

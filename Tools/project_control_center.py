from __future__ import annotations

import argparse
import contextlib
import importlib.util
import io
import json
import locale
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Sequence


REPO = Path(__file__).resolve().parents[1]
VALIDATOR_PATH = REPO / "Tools" / "validate_project_structure.py"
POLICY_ACCESSOR_PATH = REPO / "Model" / "GeoEdgeAlignSR_v1_PolicyAccess.py"
POLICY_PATH = REPO / "ESTIMATOR_POLICY.json"
CONTROL_CENTER_DOC = REPO / "docs" / "operations" / "PROJECT_CONTROL_CENTER.md"
STORAGE_POLICY_PATH = REPO / "docs" / "operations" / "PROJECT_STORAGE_POLICY.json"
STORAGE_POLICY_DOC = REPO / "docs" / "operations" / "PROJECT_STORAGE_AND_ARCHIVE_POLICY.md"
ARCHIVE_INDEX_PATH = REPO / "docs" / "operations" / "PROJECT_ARCHIVE_INDEX.md"
STORAGE_REGISTRY_PATH = REPO / "docs" / "operations" / "PROJECT_STORAGE_REGISTRY.json"
STORAGE_LIFECYCLE_PATH = REPO / "docs" / "operations" / "PROJECT_STORAGE_LIFECYCLE_PLAN.md"
QUARANTINE_INDEX_PATH = REPO / "docs" / "operations" / "PROJECT_QUARANTINE_INDEX.md"
STORAGE_GUARD_PATH = REPO / "Tools" / "project_storage_guard.py"
ANALYSIS_INDEX_PATH = REPO / "Analyses" / "AnalysisLab" / "index.json"
EVIDENCE_MAP_PATH = REPO / "docs" / "evidence" / "EVIDENCE_MAP.md"
WORKFLOW_PATH = REPO / ".github" / "workflows" / "validate-governance.yml"
PRE_COMMIT_TEMPLATE_PATH = REPO / "Tools" / "hooks" / "pre-commit"
MATLAB_AGGREGATE_SCRIPT_PATH = (
    REPO
    / "PSF_Fitting"
    / "PSF_Fitting_ValidationLab"
    / "scripts"
    / "vlab_aggregate_existing_results.m"
)
MATLAB_SMOKE_TEST_PATH = REPO / "PSF_Fitting" / "tests" / "run_matlab_smoke_tests.m"
LEGACY_RUNTIME_OLD_ROOT = "docs/runtime/legacy/root_status/"
LEGACY_RUNTIME_ARCHIVE_ROOT = "docs/archive/legacy_runtime_status/"
OFFICIAL_STANDARD_HEALTH_COMMAND = (
    "python Tools/project_control_center.py --view health --health-level standard"
)
DOCS_SCAN_PATHS = [
    REPO / "PROJECT_STATE.md",
    REPO / "README.md",
    REPO / "REPO_GOVERNANCE.md",
    REPO / "docs" / "README.md",
    REPO / "docs" / "operations" / "SOURCE_OF_TRUTH_POLICY.md",
]
CORE_DOC_PATHS = [
    REPO / "PROJECT_STATE.md",
    REPO / "PROJECT_ARCHITECTURE.md",
    POLICY_PATH,
    EVIDENCE_MAP_PATH,
    ANALYSIS_INDEX_PATH,
    CONTROL_CENTER_DOC,
    STORAGE_POLICY_PATH,
    STORAGE_POLICY_DOC,
    ARCHIVE_INDEX_PATH,
    STORAGE_REGISTRY_PATH,
    STORAGE_LIFECYCLE_PATH,
    QUARANTINE_INDEX_PATH,
]
HEALTH_LEVEL_MODULES = {
    "quick": ["docs", "entrypoints"],
    "standard": ["docs", "entrypoints", "python"],
    "deep": ["docs", "entrypoints", "python", "matlab"],
}
PYTEST_TARGETS = [
    "Analyses/AnalysisLab/tests",
    "Analyses/AnalysisLab/r26/performance/tests",
    "Analyses/AnalysisLab/r26/sequence/tests",
    "Analyses/AnalysisLab/r26/single_image/tests",
    "Experiments/R26NewPSFCheck/package_repro_validation/tests",
    "Experiments/R26NewPSFCheck/pure_psf_control/tests",
    "Experiments/R26NewPSFCheck/root_cause_centering/tests",
    "PSF_Fitting/tests/python",
    "Tools/tests",
]
COMPILE_TARGETS = [
    "Model",
    "AnalysisLab",
    "Experiments",
    "Tools",
    "Training_Data",
]
ENTRYPOINT_SPECS = [
    {
        "id": "train_main",
        "label": "standard training entry",
        "role": "mainline training",
        "path": REPO / "Model" / "GeoEdgeAlignSR_v1_Train_v5_NoCoord_return_v2_SimpleTest.py",
        "help_command": [sys.executable, "Model/GeoEdgeAlignSR_v1_Train_v5_NoCoord_return_v2_SimpleTest.py", "--help"],
    },
    {
        "id": "infer_main",
        "label": "standard inference entry",
        "role": "mainline inference",
        "path": REPO / "Model" / "GeoEdgeAlignSR_v1_Infer_v5_NoCoord_return_v2_SimpleTest.py",
        "help_command": [sys.executable, "Model/GeoEdgeAlignSR_v1_Infer_v5_NoCoord_return_v2_SimpleTest.py", "--help"],
    },
    {
        "id": "infer_tta",
        "label": "TTA inference entry",
        "role": "TTA inference",
        "path": REPO / "Model" / "GeoEdgeAlignSR_v1_Infer_TTA.py",
        "help_command": [sys.executable, "Model/GeoEdgeAlignSR_v1_Infer_TTA.py", "--help"],
    },
    {
        "id": "psf_formal",
        "label": "formal Whole-FOV PSF entry",
        "role": "PSF fitting mainline",
        "path": REPO / "PSF_Fitting" / "HDR_fitting_2D_WholeFOV.m",
        "help_command": None,
    },
    {
        "id": "analysis_hub",
        "label": "analysis hub",
        "role": "analysis entry",
        "path": REPO / "Analyses" / "AnalysisLab" / "README.md",
        "help_command": None,
    },
    {
        "id": "control_guide",
        "label": "control center guide",
        "role": "human guide",
        "path": CONTROL_CENTER_DOC,
        "help_command": None,
    },
    {
        "id": "storage_guard",
        "label": "storage and archive guard",
        "role": "capacity monitoring and archive verification",
        "path": STORAGE_GUARD_PATH,
        "help_command": [sys.executable, "Tools/project_storage_guard.py", "--help"],
    },
]
MATLAB_SMOKE_TEST_BATCH = (
    f"cd('{(REPO / 'PSF_Fitting').as_posix()}'); run('tests/run_matlab_smoke_tests.m')"
)


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Project control center")
    parser.add_argument(
        "--view",
        choices=["overview", "truth", "architecture", "entrypoints", "risks", "health"],
        default="overview",
    )
    parser.add_argument("--format", choices=["text", "json"], default="text")
    parser.add_argument("--health-level", choices=["quick", "standard", "deep"])
    parser.add_argument(
        "--module",
        action="append",
        choices=["docs", "entrypoints", "python", "matlab"],
        default=[],
    )
    return parser.parse_args(list(argv) if argv is not None else None)


def resolve_health_level(
    args: argparse.Namespace,
    requested_modules: Sequence[str] | None = None,
) -> str:
    if args.health_level:
        level = args.health_level
    elif args.view == "health":
        level = "standard"
    else:
        level = "quick"

    if args.view == "health" and requested_modules and "matlab" in requested_modules:
        return "deep"
    return level


def resolve_requested_modules(args: argparse.Namespace) -> list[str]:
    if args.view != "health":
        return []
    return list(args.module)


def load_module_from_path(path: Path, module_name: str):
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec is not None
    assert spec.loader is not None
    sys.modules.setdefault(module_name, module)
    spec.loader.exec_module(module)
    return module


def load_policy() -> dict[str, Any]:
    accessor = load_module_from_path(POLICY_ACCESSOR_PATH, "GeoEdgeAlignSR_v1_PolicyAccess")
    return accessor.load_estimator_policy(POLICY_PATH)


def load_analysis_index() -> dict[str, Any]:
    return json.loads(ANALYSIS_INDEX_PATH.read_text(encoding="utf-8"))


def summarize_analysis_index(index: dict[str, Any]) -> dict[str, Any]:
    versions: list[dict[str, Any]] = []
    for version_name, version_data in index.get("versions", {}).items():
        analyses = version_data.get("analyses", {})
        versions.append(
            {
                "version": version_name,
                "readme": version_data.get("readme"),
                "analysis_count": len(analyses),
                "analysis_names": sorted(analyses.keys()),
            }
        )
    return {
        "entry_point": index.get("entry_point"),
        "layout_policy": index.get("layout_policy"),
        "versions": versions,
    }


def relpath(path: Path) -> str:
    try:
        return path.relative_to(REPO).as_posix()
    except ValueError:
        return str(path)


def scan_files_for_legacy_runtime_refs(paths: Sequence[Path]) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    for path in paths:
        if not path.exists():
            continue
        for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            if LEGACY_RUNTIME_OLD_ROOT in line:
                findings.append(
                    {
                        "path": path,
                        "line_number": line_number,
                        "line": line.strip(),
                    }
                )
    return findings


def run_command(
    command: Sequence[str],
    *,
    cwd: Path = REPO,
    env: dict[str, str] | None = None,
    timeout: int = 300_000,
) -> dict[str, Any]:
    completed = subprocess.run(
        list(command),
        cwd=cwd,
        env=env,
        capture_output=True,
        text=False,
        check=False,
        timeout=timeout,
    )
    def decode_output(value: bytes | str | None) -> str:
        if value is None:
            return ""
        if isinstance(value, str):
            return value.strip()
        try:
            return value.decode("utf-8").strip()
        except UnicodeDecodeError:
            # Windows native programs and Python children without UTF-8 mode
            # can emit the system code page even when this parent uses -X utf8.
            return value.decode(locale.getencoding(), errors="replace").strip()

    return {
        "returncode": completed.returncode,
        "stdout": decode_output(completed.stdout),
        "stderr": decode_output(completed.stderr),
        "command": list(command),
    }


def get_tracked_status_lines() -> list[str]:
    result = run_command(["git", "status", "--short", "--untracked-files=no"], timeout=30_000)
    if result["returncode"] != 0 or not result["stdout"]:
        return []
    return [line.strip() for line in result["stdout"].splitlines() if line.strip()]


def run_structure_validator() -> dict[str, Any]:
    validator = load_module_from_path(VALIDATOR_PATH, "validate_project_structure")
    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer):
        results = validator.run_validator()
    return {
        "errors": list(results["errors"]),
        "warnings": list(results["warnings"]),
        "output": buffer.getvalue().strip(),
    }


def run_docs_checks(level: str) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    issues: list[str] = []

    missing_docs = [relpath(path) for path in CORE_DOC_PATHS if not path.exists()]
    if missing_docs:
        checks.append(
            {
                "name": "core_docs_exist",
                "status": "FAIL",
                "details": f"Missing: {', '.join(missing_docs)}",
            }
        )
        issues.extend([f"missing core doc: {item}" for item in missing_docs])
    else:
        checks.append(
            {
                "name": "core_docs_exist",
                "status": "PASS",
                "details": "All control-center source docs exist.",
            }
        )

    stale_refs = scan_files_for_legacy_runtime_refs(DOCS_SCAN_PATHS)
    if stale_refs:
        summary = ", ".join(
            f"{relpath(item['path'])}:{item['line_number']}" for item in stale_refs
        )
        checks.append(
            {
                "name": "legacy_runtime_refs",
                "status": "FAIL",
                "details": summary,
            }
        )
        issues.append(f"stale legacy runtime refs: {summary}")
    else:
        checks.append(
            {
                "name": "legacy_runtime_refs",
                "status": "PASS",
                "details": f"Formal docs now point to {LEGACY_RUNTIME_ARCHIVE_ROOT}",
            }
        )

    if level in {"standard", "deep"}:
        validator_result = run_structure_validator()
        if validator_result["errors"]:
            checks.append(
                {
                    "name": "structure_validator",
                    "status": "FAIL",
                    "details": "; ".join(validator_result["errors"]),
                }
            )
            issues.extend(validator_result["errors"])
        elif validator_result["warnings"]:
            checks.append(
                {
                    "name": "structure_validator",
                    "status": "WARN",
                    "details": "; ".join(validator_result["warnings"]),
                }
            )
            issues.extend(validator_result["warnings"])
        else:
            checks.append(
                {
                    "name": "structure_validator",
                    "status": "PASS",
                    "details": "Project structure validator passed.",
                }
            )

    module_status = "PASS"
    if any(check["status"] == "FAIL" for check in checks):
        module_status = "FAIL"
    elif any(check["status"] == "WARN" for check in checks):
        module_status = "WARN"

    return {
        "module": "docs",
        "status": module_status,
        "checks": checks,
        "issues": issues,
    }


def run_entrypoint_checks(_: str) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    issues: list[str] = []

    missing = [item for item in ENTRYPOINT_SPECS if not item["path"].exists()]
    if missing:
        missing_labels = ", ".join(relpath(item["path"]) for item in missing)
        checks.append(
            {
                "name": "entrypoint_files",
                "status": "FAIL",
                "details": missing_labels,
            }
        )
        issues.append(f"missing entrypoints: {missing_labels}")
    else:
        checks.append(
            {
                "name": "entrypoint_files",
                "status": "PASS",
                "details": "All declared entrypoints exist.",
            }
        )

    for item in ENTRYPOINT_SPECS:
        help_command = item["help_command"]
        if help_command is None or not item["path"].exists():
            continue
        result = run_command(help_command, timeout=120_000)
        status = "PASS" if result["returncode"] == 0 else "FAIL"
        details = "help opened successfully" if status == "PASS" else (
            result["stderr"] or result["stdout"] or "command failed"
        )
        checks.append(
            {
                "name": f"{item['id']}_help",
                "status": status,
                "details": details,
            }
        )
        if status == "FAIL":
            issues.append(f"{item['label']} help failed: {details}")

    module_status = "PASS"
    if any(check["status"] == "FAIL" for check in checks):
        module_status = "FAIL"

    return {
        "module": "entrypoints",
        "status": module_status,
        "checks": checks,
        "issues": issues,
    }


def run_python_checks(_: str) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    issues: list[str] = []

    pytest_result = run_command(
        [sys.executable, "-m", "pytest", "-q", *PYTEST_TARGETS],
        timeout=600_000,
    )
    pytest_status = "PASS" if pytest_result["returncode"] == 0 else "FAIL"
    pytest_details = pytest_result["stdout"] or pytest_result["stderr"] or "pytest produced no output"
    checks.append(
        {
            "name": "python_tests",
            "status": pytest_status,
            "details": pytest_details.splitlines()[-1] if pytest_details else "ok",
        }
    )
    if pytest_status == "FAIL":
        issues.append("python white-list tests failed")

    compile_result = run_command(
        [sys.executable, "-m", "compileall", "-q", *COMPILE_TARGETS],
        timeout=600_000,
    )
    compile_status = "PASS" if compile_result["returncode"] == 0 else "FAIL"
    checks.append(
        {
            "name": "compileall",
            "status": compile_status,
            "details": "compileall passed" if compile_status == "PASS" else (
                compile_result["stderr"] or compile_result["stdout"] or "compileall failed"
            ),
        }
    )
    if compile_status == "FAIL":
        issues.append("compileall failed")

    module_status = "PASS"
    if any(check["status"] == "FAIL" for check in checks):
        module_status = "FAIL"

    return {
        "module": "python",
        "status": module_status,
        "checks": checks,
        "issues": issues,
    }


def find_matlab_executable() -> str | None:
    candidates = [
        Path(r"C:\Program Files\MATLAB\R2025b\bin\matlab.exe"),
        Path(r"C:\Program Files\MATLAB\R2025a\bin\matlab.exe"),
    ]
    for candidate in candidates:
        if candidate.exists():
            return str(candidate)
    return shutil.which("matlab")


def run_matlab_checks(level: str) -> dict[str, Any]:
    if level != "deep":
        return {
            "module": "matlab",
            "status": "FAIL",
            "checks": [
                {
                    "name": "matlab_smoke_tests",
                    "status": "FAIL",
                    "details": "MATLAB checks only run at deep level.",
                }
            ],
            "issues": ["MATLAB checks require deep level"],
        }

    matlab_exe = find_matlab_executable()
    if matlab_exe is None:
        return {
            "module": "matlab",
            "status": "FAIL",
            "checks": [
                {
                    "name": "matlab_smoke_tests",
                    "status": "FAIL",
                    "details": "MATLAB executable not found.",
                }
            ],
            "issues": ["MATLAB executable not found"],
        }

    temp_output_root = Path(tempfile.mkdtemp(prefix="project_control_center_vlab_"))
    env = os.environ.copy()
    env["VLAB_TEST_OUTPUT_ROOT"] = temp_output_root.as_posix()
    result = run_command(
        [matlab_exe, "-batch", MATLAB_SMOKE_TEST_BATCH],
        env=env,
        timeout=3_600_000,
    )
    status = "PASS" if result["returncode"] == 0 else "FAIL"
    details = (
        f"MATLAB smoke tests completed with isolated output root {temp_output_root.as_posix()}"
        if status == "PASS"
        else (result["stderr"] or result["stdout"] or "MATLAB smoke tests failed")
    )
    return {
        "module": "matlab",
        "status": status,
        "checks": [
            {
                "name": "matlab_smoke_tests",
                "status": status,
                "details": details,
            }
        ],
        "issues": [] if status == "PASS" else ["MATLAB smoke tests failed"],
    }


def run_health_modules(
    selected_modules: Sequence[str],
    runners: dict[str, Any],
) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for module_name in selected_modules:
        runner = runners[module_name]
        try:
            results.append(runner())
        except Exception as exc:  # pragma: no cover - defensive fallback
            results.append(
                {
                    "module": module_name,
                    "status": "FAIL",
                    "checks": [
                        {
                            "name": f"{module_name}_runner",
                            "status": "FAIL",
                            "details": str(exc),
                        }
                    ],
                    "issues": [str(exc)],
                }
            )
    return results


def finalize_health_status(
    module_results: Sequence[dict[str, Any]],
    *,
    started_dirty: bool,
    new_tracked_changes: Sequence[str],
) -> dict[str, Any]:
    any_fail = any(item["status"] == "FAIL" for item in module_results)
    any_warn = any(item["status"] == "WARN" for item in module_results)

    if any_fail or new_tracked_changes:
        status = "FAIL"
    elif started_dirty or any_warn:
        status = "WARN"
    else:
        status = "PASS"

    issues: list[str] = []
    for item in module_results:
        issues.extend(item.get("issues", []))
    if started_dirty:
        issues.append("tracked worktree was already dirty at start")
    if new_tracked_changes:
        issues.append("health check introduced new tracked changes")

    return {
        "status": status,
        "started_dirty": started_dirty,
        "new_tracked_changes": list(new_tracked_changes),
        "issues": issues,
        "modules": list(module_results),
    }


def run_health(level: str, requested_modules: Sequence[str] | None = None) -> dict[str, Any]:
    start_status = get_tracked_status_lines()
    started_dirty = bool(start_status)
    selected_modules = list(requested_modules) if requested_modules else list(HEALTH_LEVEL_MODULES[level])
    runners = {
        "docs": lambda: run_docs_checks(level),
        "entrypoints": lambda: run_entrypoint_checks(level),
        "python": lambda: run_python_checks(level),
        "matlab": lambda: run_matlab_checks(level),
    }
    module_results = run_health_modules(selected_modules, runners)
    end_status = get_tracked_status_lines()
    new_tracked_changes = sorted(set(end_status) - set(start_status))
    summary = finalize_health_status(
        module_results,
        started_dirty=started_dirty,
        new_tracked_changes=new_tracked_changes,
    )
    summary["level"] = level
    summary["selected_modules"] = selected_modules
    summary["start_tracked_status"] = start_status
    summary["end_tracked_status"] = end_status
    return summary


def build_truth_sources(repo: Path, policy: dict[str, Any], analysis_index: dict[str, Any]) -> dict[str, Any]:
    formal = policy["formal_baseline"]

    def preferred_report_path(item: dict[str, Any]) -> str:
        def format_report(value: str) -> str:
            path = Path(value)
            if path.is_absolute():
                return relpath(path)
            return path.as_posix()

        reports = item.get("reports", {})
        for key in (
            "status_md",
            "results_md",
            "capability_eval_md",
            "summary_md",
            "external_compare_md",
            "sweep_results_md",
            "weight_sweep_summary_md",
        ):
            if key in reports:
                return format_report(str(REPO / reports[key]))
        if reports:
            return format_report(next(iter(reports.values())))
        if item.get("report"):
            return format_report(item["report"])
        return ""

    return {
        "formal_baseline": {
            "candidate_id": formal["candidate_id"],
            "model_name": formal["model_name"],
            "decision_effective_date": formal["decision_effective_date"],
            "machine_truth": relpath(POLICY_PATH),
            "report": relpath(Path(REPO / formal["reports"]["results_md"])),
            "evidence_map": relpath(EVIDENCE_MAP_PATH),
        },
        "approved_alternates": [
            {
                "candidate_id": item["candidate_id"],
                "model_name": item["model_name"],
                "report": preferred_report_path(item),
            }
            for item in policy["approved_alternates"]
        ],
        "open_side_tracks": [
            {
                "candidate_id": item["candidate_id"],
                "status": item["status"],
                "report": preferred_report_path(item),
            }
            for item in policy["open_side_tracks"]
        ],
        "source_docs": [
            {"label": "project state", "path": relpath(repo / "PROJECT_STATE.md")},
            {"label": "architecture", "path": relpath(repo / "PROJECT_ARCHITECTURE.md")},
            {"label": "evidence map", "path": relpath(EVIDENCE_MAP_PATH)},
            {"label": "analysis index", "path": relpath(ANALYSIS_INDEX_PATH)},
            {"label": "storage policy", "path": relpath(STORAGE_POLICY_PATH)},
            {"label": "storage registry", "path": relpath(STORAGE_REGISTRY_PATH)},
            {"label": "storage lifecycle", "path": relpath(STORAGE_LIFECYCLE_PATH)},
            {"label": "quarantine index", "path": relpath(QUARANTINE_INDEX_PATH)},
        ],
        "analysis": summarize_analysis_index(analysis_index),
    }


def build_architecture_view(policy: dict[str, Any]) -> dict[str, Any]:
    def experiment_location(item: dict[str, Any]) -> str:
        if item.get("experiment"):
            return item["experiment"]
        # Recent research records also use a direct canonical report field.
        # Derive a location only from that explicit reports directory.
        report = str(item.get("report", "")).replace("\\", "/")
        return report.split("/reports/", 1)[0] if "/reports/" in report else ""

    return {
        "mainline": {
            "label": "root shared mainline",
            "formal_baseline": policy["formal_baseline"]["candidate_id"],
            "description": "Root Model/ and formal PSF fitting remain the shared mainline.",
        },
        "side_tracks": [
            {
                "candidate_id": item["candidate_id"],
                "status": item["status"],
                "location": experiment_location(item),
            }
            for item in policy["open_side_tracks"]
        ],
        "closed_lines": [
            {
                "candidate_id": item["candidate_id"],
                "status": item["status"],
                "verdict": item.get("verdict", ""),
            }
            for item in policy["closed_lines"]
        ],
        "boundaries": [
            "Do not treat side tracks as the active mainline.",
            "Archived historical surfaces stay preserved and should not be day-to-day editable truth.",
            "Validation should not overwrite formal tracked outputs.",
            "Machine-readable baseline truth stays in ESTIMATOR_POLICY.json.",
        ],
    }


def build_entrypoints_view() -> dict[str, Any]:
    return {
        "items": [
            {
                "id": spec["id"],
                "label": spec["label"],
                "role": spec["role"],
                "path": relpath(spec["path"]),
                "exists": spec["path"].exists(),
            }
            for spec in ENTRYPOINT_SPECS
        ]
    }


def build_risks_view(repo: Path) -> dict[str, Any]:
    stale_refs = scan_files_for_legacy_runtime_refs(DOCS_SCAN_PATHS)
    workflow_text = WORKFLOW_PATH.read_text(encoding="utf-8") if WORKFLOW_PATH.exists() else ""
    hook_text = (
        PRE_COMMIT_TEMPLATE_PATH.read_text(encoding="utf-8")
        if PRE_COMMIT_TEMPLATE_PATH.exists()
        else ""
    )
    aggregate_text = (
        MATLAB_AGGREGATE_SCRIPT_PATH.read_text(encoding="utf-8")
        if MATLAB_AGGREGATE_SCRIPT_PATH.exists()
        else ""
    )
    smoke_text = (
        MATLAB_SMOKE_TEST_PATH.read_text(encoding="utf-8")
        if MATLAB_SMOKE_TEST_PATH.exists()
        else ""
    )
    model_tests_exist = any((repo / "Model").glob("test_*.py")) or (repo / "Model" / "tests").exists()
    ci_uses_official_standard = OFFICIAL_STANDARD_HEALTH_COMMAND in workflow_text
    local_hook_uses_official_standard = OFFICIAL_STANDARD_HEALTH_COMMAND in hook_text
    matlab_output_isolated = (
        "parser.addParameter('output_root'" in aggregate_text
        and "VLAB_TEST_OUTPUT_ROOT" in smoke_text
    )

    return {
        "items": [
            {
                "id": "legacy_runtime_doc_drift",
                "status": "ACTIVE" if stale_refs else "MANAGED",
                "details": (
                    ", ".join(f"{relpath(item['path'])}:{item['line_number']}" for item in stale_refs)
                    if stale_refs
                    else f"Formal docs now point to {LEGACY_RUNTIME_ARCHIVE_ROOT}."
                ),
            },
            {
                "id": "root_pytest_collection_trap",
                "status": "KNOWN",
                "details": "Bare repo-root pytest is still not the official health gate because archive outputs can break collection.",
            },
            {
                "id": "ci_scope",
                "status": "MANAGED" if ci_uses_official_standard else "ACTIVE",
                "details": "GitHub validation should run the control center standard health path.",
            },
            {
                "id": "local_guardrail_scope",
                "status": "MANAGED" if local_hook_uses_official_standard else "ACTIVE",
                "details": "The tracked pre-commit hook should match the same official standard health path as CI.",
            },
            {
                "id": "matlab_tracked_output_coupling",
                "status": "MANAGED" if matlab_output_isolated else "ACTIVE",
                "details": "Deep health checks must isolate ValidationLab report outputs away from tracked summaries.",
            },
            {
                "id": "model_direct_coverage_gap",
                "status": "ACTIVE" if not model_tests_exist else "MANAGED",
                "details": "Mainline model scripts still rely mainly on help checks and compile/load guards rather than dedicated tests.",
            },
        ]
    }


def build_health_placeholder(level: str) -> dict[str, Any]:
    return {
        "status": "NOT_RUN",
        "level": level,
        "selected_modules": list(HEALTH_LEVEL_MODULES[level]),
        "modules": [],
        "issues": [],
        "new_tracked_changes": [],
        "started_dirty": False,
    }


def build_summary(
    policy: dict[str, Any],
    view: str,
    health: dict[str, Any],
    requested_modules: Sequence[str],
) -> dict[str, Any]:
    formal = policy["formal_baseline"]
    return {
        "view": view,
        "official_entry": relpath(REPO / "Tools" / "project_control_center.py"),
        "guide": relpath(CONTROL_CENTER_DOC),
        "formal_baseline": f"{formal['candidate_id']} / {formal['model_name']}",
        "health_status": health["status"],
        "health_level": health["level"],
        "requested_modules": list(requested_modules),
    }


def build_payload(
    repo: Path,
    *,
    view: str,
    health_level: str,
    requested_modules: Sequence[str],
) -> dict[str, Any]:
    policy = load_policy()
    analysis_index = load_analysis_index()
    if view in {"overview", "health"}:
        health = run_health(health_level, requested_modules)
    else:
        health = build_health_placeholder(health_level)
    return {
        "summary": build_summary(policy, view, health, requested_modules),
        "truth_sources": build_truth_sources(repo, policy, analysis_index),
        "architecture": build_architecture_view(policy),
        "entrypoints": build_entrypoints_view(),
        "risks": build_risks_view(repo),
        "health": health,
    }


def render_text(payload: dict[str, Any], view: str) -> str:
    lines: list[str] = []
    summary = payload["summary"]
    lines.append("Project Control Center")
    lines.append(f"Official entry: {summary['official_entry']}")
    lines.append(f"Guide: {summary['guide']}")
    lines.append(f"Formal baseline: {summary['formal_baseline']}")
    lines.append(f"Health: {summary['health_status']} ({summary['health_level']})")

    if view in {"overview", "truth"}:
        truth = payload["truth_sources"]
        lines.append("")
        lines.append("Truth")
        lines.append(f"- Formal baseline report: {truth['formal_baseline']['report']}")
        lines.append(f"- Machine truth: {truth['formal_baseline']['machine_truth']}")
        lines.append(
            f"- Analysis hub: {truth['analysis']['entry_point']} ({truth['analysis']['layout_policy']})"
        )
        lines.append(
            "- Analysis versions: "
            + ", ".join(
                f"{item['version']} ({item['analysis_count']} analyses)"
                for item in truth["analysis"]["versions"]
            )
        )
        lines.append(
            "- Approved alternates: "
            + ", ".join(item["candidate_id"] for item in truth["approved_alternates"])
        )
        lines.append(
            "- Open side tracks: "
            + ", ".join(item["candidate_id"] for item in truth["open_side_tracks"])
        )

    if view in {"overview", "architecture"}:
        architecture = payload["architecture"]
        lines.append("")
        lines.append("Architecture")
        lines.append(f"- Mainline: {architecture['mainline']['description']}")
        lines.append(
            "- Side tracks: "
            + ", ".join(item["candidate_id"] for item in architecture["side_tracks"])
        )
        lines.append(
            "- Closed lines: "
            + ", ".join(item["candidate_id"] for item in architecture["closed_lines"][:4])
        )

    if view in {"overview", "entrypoints"}:
        lines.append("")
        lines.append("Entrypoints")
        for item in payload["entrypoints"]["items"]:
            state = "ok" if item["exists"] else "missing"
            lines.append(f"- {item['label']}: {item['path']} ({state})")

    if view in {"overview", "risks"}:
        lines.append("")
        lines.append("Risks")
        for item in payload["risks"]["items"]:
            lines.append(f"- {item['id']}: {item['status']} - {item['details']}")

    if view in {"overview", "health"}:
        lines.append("")
        lines.append("Health")
        lines.append("- Modules: " + ", ".join(payload["health"]["selected_modules"]))
        for item in payload["health"]["modules"]:
            lines.append(f"- {item['module']}: {item['status']}")
            for check in item["checks"]:
                lines.append(f"  {check['name']}: {check['status']} - {check['details']}")
        if payload["health"]["started_dirty"]:
            lines.append("- Worktree started dirty.")
        if payload["health"]["new_tracked_changes"]:
            lines.append(
                "- New tracked changes: "
                + ", ".join(payload["health"]["new_tracked_changes"])
            )
    return "\n".join(lines)


def to_jsonable(value: Any) -> Any:
    if isinstance(value, Path):
        return value.as_posix()
    if isinstance(value, dict):
        return {key: to_jsonable(item) for key, item in value.items()}
    if isinstance(value, list):
        return [to_jsonable(item) for item in value]
    return value


def determine_exit_code(payload: dict[str, Any], view: str) -> int:
    if view not in {"overview", "health"}:
        return 0
    return 1 if payload["health"]["status"] == "FAIL" else 0


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    requested_modules = resolve_requested_modules(args)
    health_level = resolve_health_level(args, requested_modules)
    payload = build_payload(
        REPO,
        view=args.view,
        health_level=health_level,
        requested_modules=requested_modules,
    )

    if args.format == "json":
        print(json.dumps(to_jsonable(payload), ensure_ascii=False, indent=2))
    else:
        print(render_text(payload, args.view))

    return determine_exit_code(payload, args.view)


if __name__ == "__main__":
    raise SystemExit(main())

"""
Project structure validator.

Checks:
1. Every Experiments/ subdir has MANIFEST.md and README.md
2. Every MANIFEST.md is referenced in Experiments/INDEX.md
3. Key cross-references in INDEX.md point to existing files
4. CLAUDE.md and AGENTS.md have identical convention sections
5. Inference script copies are in sync (quantization fix)

Run: python Tools/validate_project_structure.py
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
ERRORS: list[str] = []
WARNINGS: list[str] = []
LEGACY_BATCH_SPECS = {
    "organized_20260313": [
        "root_status_legacy",
        "round16",
        "round17",
        "round18",
        "round19",
    ],
    "organized_20260314": [
        "round20",
        "diagnostics",
        "branch_e",
    ],
    "organized_20260315": [
        "round21",
        "round22",
        "pairwise_delta_probe",
        "branch_e_followup",
        "estimator_formula_probe",
    ],
    "organized_20260316": [
        "round23",
        "round24",
        "round25",
        "round26",
        "round27",
        "round28",
        "round29",
        "round30",
        "round31",
        "external_compare_round18_round22",
        "external_compare_r18_r22_r25",
        "external_compare_r18_r22_r25_r26",
        "external_compare_r18_r22_r25_r26_r27",
        "external_compare_r18_r22_r25_r26_r27_r28",
        "external_compare_r18_r22_r25_r26_r27_r28_r29",
        "external_compare_r18_r22_r25_r26r18_highcenter",
        "external_compare_r18_r22_r25_r26r22_hold",
        "external_compare_r18_r22_r25_r26r25_sw010",
        "external_compare_r18_r22_r25_r26r26_sm035",
        "analysis",
        "tta_experiment",
        "tta_experiment/r26_tta_cross5",
    ],
}


def error(msg: str):
    ERRORS.append(msg)
    print(f"  ERROR: {msg}")


def warn(msg: str):
    WARNINGS.append(msg)
    print(f"  WARN:  {msg}")


def check_experiment_dirs():
    print("=== Check 1: Experiment directories ===")
    exp_root = REPO / "Experiments"
    for d in sorted(exp_root.iterdir()):
        if not d.is_dir() or d.name.startswith("."):
            continue
        if not (d / "README.md").exists():
            error(f"{d.name}/ missing README.md")
        if not (d / "MANIFEST.md").exists():
            error(f"{d.name}/ missing MANIFEST.md")


def check_index_references():
    print("=== Check 2: INDEX.md references ===")
    index_path = REPO / "Experiments" / "INDEX.md"
    if not index_path.exists():
        error("Experiments/INDEX.md does not exist")
        return
    index_text = index_path.read_text(encoding="utf-8")
    # Check that every experiment dir is mentioned
    exp_root = REPO / "Experiments"
    for d in sorted(exp_root.iterdir()):
        if not d.is_dir() or d.name.startswith(".") or d.name == "__pycache__":
            continue
        if d.name not in index_text:
            warn(f"{d.name}/ not referenced in INDEX.md")


def check_report_links():
    print("=== Check 3: Report file links ===")
    index_path = REPO / "Experiments" / "INDEX.md"
    if not index_path.exists():
        return
    index_text = index_path.read_text(encoding="utf-8")
    # Find all backtick-quoted relative paths
    paths = re.findall(r"`([^`]+\.md)`", index_text)
    for p in paths:
        # Try resolving from Experiments/ and from repo root
        candidates = [REPO / "Experiments" / p, REPO / p]
        if not any(c.exists() for c in candidates):
            # Could be a relative path from inside an experiment dir
            for exp_dir in (REPO / "Experiments").iterdir():
                if exp_dir.is_dir() and (exp_dir / p).exists():
                    break
            else:
                warn(f"INDEX.md references `{p}` but file not found")


def check_claude_agents_sync():
    print("=== Check 4: CLAUDE.md / AGENTS.md sync ===")
    claude = (REPO / "CLAUDE.md").read_text(encoding="utf-8")
    agents = (REPO / "AGENTS.md").read_text(encoding="utf-8")
    # Extract convention sections
    def extract_section(text: str, header: str) -> str:
        lines = text.split("\n")
        start = None
        for i, line in enumerate(lines):
            if header in line:
                start = i
            elif start is not None and line.startswith("## ") and i > start:
                return "\n".join(lines[start:i])
        if start is not None:
            return "\n".join(lines[start:])
        return ""

    for section in ["Experiment conventions", "Documentation update policy",
                    "Source of truth policy", "Known quirks"]:
        c = extract_section(claude, section)
        a = extract_section(agents, section)
        if c != a:
            error(f"CLAUDE.md and AGENTS.md diverge in '{section}' section")


def check_inference_quantfix():
    print("=== Check 5: Inference quantization fix consistency ===")
    # Check all Infer_v5 copies
    infer_files = list(REPO.rglob("GeoEdgeAlignSR_v1_Infer_v5_NoCoord_return_v2_SimpleTest.py"))
    # Also check TTA canonical script
    tta = REPO / "Model" / "GeoEdgeAlignSR_v1_Infer_TTA.py"
    if tta.exists():
        infer_files.append(tta)
    # Exclude .claude worktrees
    infer_files = [f for f in infer_files if ".claude" not in str(f)]
    for f in infer_files:
        text = f.read_text(encoding="utf-8", errors="replace")
        if "np.rint" not in text and "denormalize_to_dtype" in text:
            error(f"Missing np.rint in {f.relative_to(REPO)}")


def check_legacy_governance():
    guide = REPO / "docs" / "index" / "LEGACY_ROUNDS_OPERATIONS.md"

    print("=== Check 6: Legacy batch governance ===")
    if not guide.exists():
        error("docs/index/LEGACY_ROUNDS_OPERATIONS.md is missing")
    guide_text = guide.read_text(encoding="utf-8") if guide.exists() else ""
    tracked_targets: list[Path] = []
    for batch_name, surfaces in LEGACY_BATCH_SPECS.items():
        legacy_root = REPO / "Traing_Progress" / batch_name
        if not legacy_root.is_dir():
            error(f"Legacy batch missing: Traing_Progress/{batch_name}")
            continue
        batch_readme = legacy_root / "README.md"
        batch_manifest = legacy_root / "MANIFEST.md"
        if not batch_readme.exists():
            error(f"Traing_Progress/{batch_name}/README.md is missing")
        if not batch_manifest.exists():
            error(f"Traing_Progress/{batch_name}/MANIFEST.md is missing")
        tracked_targets.extend([batch_readme, batch_manifest])
        if guide_text and batch_name not in guide_text:
            warn(f"LEGACY_ROUNDS_OPERATIONS.md does not mention batch {batch_name}")

        for dirname in surfaces:
            surface = legacy_root / dirname
            if not surface.is_dir():
                error(f"Legacy surface missing: Traing_Progress/{batch_name}/{dirname}")
                continue
            readme = surface / "README.md"
            manifest = surface / "MANIFEST.md"
            if not readme.exists():
                error(f"Traing_Progress/{batch_name}/{dirname}/README.md is missing")
            if not manifest.exists():
                error(f"Traing_Progress/{batch_name}/{dirname}/MANIFEST.md is missing")
            tracked_targets.extend([readme, manifest])
            surface_name = Path(dirname).name
            if guide_text and surface_name not in guide_text:
                warn(f"LEGACY_ROUNDS_OPERATIONS.md does not mention {batch_name}/{dirname}")

    for target in tracked_targets:
        result = subprocess.run(
            ["git", "check-ignore", "-q", str(target)],
            cwd=REPO,
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode == 0:
            error(f"Legacy governance file is ignored by git: {target.relative_to(REPO)}")

    blocked_targets = [
        REPO / "Traing_Progress" / "organized_20260313" / "round18" / "external_validation" / "future_note" / "README.md",
        REPO / "Traing_Progress" / "organized_20260314" / "branch_e" / "archive" / "future_note" / "MANIFEST.md",
        REPO / "Traing_Progress" / "organized_20260315" / "round22" / "selected" / "reports" / "extra" / "README.md",
        REPO / "Traing_Progress" / "organized_20260316" / "round23" / "archive" / "future_note" / "README.md",
        REPO / "Traing_Progress" / "organized_20260316" / "round31" / "archive" / "future_note" / "README.md",
        REPO / "Traing_Progress" / "organized_20260316" / "round30" / "gmf_results" / "raw" / "r30_b1_dironly" / "pitch8px" / "MANIFEST.md",
    ]
    for target in blocked_targets:
        result = subprocess.run(
            ["git", "check-ignore", "-q", str(target)],
            cwd=REPO,
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            error(f"Legacy artifact-side doc is unexpectedly trackable: {target.relative_to(REPO)}")


def main():
    check_experiment_dirs()
    check_index_references()
    check_report_links()
    check_claude_agents_sync()
    check_inference_quantfix()
    check_legacy_governance()

    print()
    print(f"Results: {len(ERRORS)} errors, {len(WARNINGS)} warnings")
    if ERRORS:
        print("ERRORS must be fixed before committing.")
        sys.exit(1)
    elif WARNINGS:
        print("Warnings are advisory — review but not blocking.")
        sys.exit(0)
    else:
        print("All checks passed.")
        sys.exit(0)


if __name__ == "__main__":
    main()

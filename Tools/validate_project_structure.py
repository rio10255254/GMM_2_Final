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
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
ERRORS: list[str] = []
WARNINGS: list[str] = []


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


def main():
    check_experiment_dirs()
    check_index_references()
    check_report_links()
    check_claude_agents_sync()
    check_inference_quantfix()

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

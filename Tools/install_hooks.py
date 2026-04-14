"""Install git hooks from Tools/hooks/ into .git/hooks/.

Run once per local clone:
    python Tools/install_hooks.py

What it does:
- Copies Tools/hooks/pre-commit to .git/hooks/pre-commit
- Makes it executable (Unix perms; no-op on Windows NTFS but git-for-Windows respects shebang)
- Overwrites any existing pre-commit hook (after a warning + confirmation)

Uninstall: rm .git/hooks/pre-commit
"""
from __future__ import annotations

import shutil
import stat
import sys
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
HOOKS_SRC = REPO / "Tools" / "hooks"
HOOKS_DST = REPO / ".git" / "hooks"


def install(name: str) -> int:
    src = HOOKS_SRC / name
    dst = HOOKS_DST / name

    if not src.exists():
        print(f"ERROR: source hook not found: {src}")
        return 1

    if not HOOKS_DST.exists():
        print(f"ERROR: .git/hooks/ not found. Is this a git repo?")
        return 1

    if dst.exists():
        existing = dst.read_text(encoding="utf-8", errors="replace")
        new = src.read_text(encoding="utf-8")
        if existing == new:
            print(f"[{name}] already installed and up to date.")
            return 0
        print(f"[{name}] WARNING: existing hook differs from source.")
        answer = input(f"Overwrite {dst}? [y/N] ").strip().lower()
        if answer != "y":
            print(f"[{name}] skipped (kept existing).")
            return 0

    shutil.copy(src, dst)
    # Make executable (on Unix; harmless on Windows).
    mode = dst.stat().st_mode
    dst.chmod(mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
    print(f"[{name}] installed -> {dst.relative_to(REPO)}")
    return 0


def main() -> int:
    exit_code = 0
    for name in ("pre-commit",):
        exit_code |= install(name)
    return exit_code


if __name__ == "__main__":
    sys.exit(main())

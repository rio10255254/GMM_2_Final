"""Show R119 phase progress without starting work."""
from __future__ import annotations
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
PHASES = [f"P{i:02d}" for i in range(13)]


def main() -> int:
    receipts = ROOT / "reports/handoff_receipts"
    completed = []
    for phase in PHASES:
        path = receipts / f"{phase}.json"
        if path.is_file():
            try:
                data = json.loads(path.read_text(encoding="utf-8-sig"))
                if data.get("status") == "complete":
                    completed.append(phase)
            except (OSError, json.JSONDecodeError):
                pass
    next_phase = next((p for p in PHASES[1:] if p not in completed), None)
    print(json.dumps({"root": str(ROOT), "completed_receipts": completed,
                      "next_phase": next_phase or "none",
                      "status": "complete" if len(completed) == 12 else "receipts recorded",
                      "trainer_launch": "not performed by status.py"}, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

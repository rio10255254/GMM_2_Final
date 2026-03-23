import json
import os
import time
from pathlib import Path


SANDBOX_ROOT = Path(__file__).resolve().parents[1]
STATUS_JSON = SANDBOX_ROOT / "runtime" / "R32_STATUS.json"
STATUS_MD = SANDBOX_ROOT / "runtime" / "R32_STATUS.md"


def load_round32_status() -> dict:
    if not STATUS_JSON.exists():
        return {}
    try:
        return json.loads(STATUS_JSON.read_text(encoding="utf-8"))
    except Exception:
        return {}


def process_alive(pid: int | None) -> bool:
    if not pid:
        return False
    try:
        os.kill(int(pid), 0)
        return True
    except Exception:
        return False


def write_round32_status(
    *,
    state: str,
    step_index: int,
    active_label: str,
    active_command: str,
    plan_done: int,
    plan_total: int,
    last_report: str = "",
    last_exit: str = "",
    note: str = "",
    selected_candidate: str = "",
    selected_checkpoint: str = "",
    active_pid: int | None = None,
    active_log: str = "",
    active_err_log: str = "",
) -> None:
    payload = {
        "state": state,
        "step_index": int(step_index),
        "active_label": active_label,
        "active_command": active_command,
        "plan_done": int(plan_done),
        "plan_total": int(plan_total),
        "last_report": last_report,
        "last_exit": last_exit,
        "note": note,
        "selected_candidate": selected_candidate,
        "selected_checkpoint": selected_checkpoint,
        "active_pid": int(active_pid) if active_pid else 0,
        "active_log": active_log,
        "active_err_log": active_err_log,
        "updated_at": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime()),
    }
    STATUS_JSON.parent.mkdir(parents=True, exist_ok=True)
    STATUS_JSON.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    STATUS_MD.write_text(
        "\n".join(
            [
                f"state: {state}",
                f"step_index: {step_index}",
                f"active_label: {active_label}",
                f"active_command: {active_command}",
                f"plan_done: {plan_done}",
                f"plan_total: {plan_total}",
                f"last_report: {last_report}",
                f"last_exit: {last_exit}",
                f"selected_candidate: {selected_candidate}",
                f"selected_checkpoint: {selected_checkpoint}",
                f"active_pid: {payload['active_pid']}",
                f"active_log: {active_log}",
                f"active_err_log: {active_err_log}",
                f"note: {note}",
                f"updated_at: {payload['updated_at']}",
            ]
        ),
        encoding="utf-8",
    )

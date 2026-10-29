import json
import os
import subprocess
import sys
import time
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
REPORT_ROOT = PROJECT_ROOT / "Traing_Progress" / "auto_tune_reports"
LOG_ROOT = PROJECT_ROOT / "Traing_Progress" / "organized_20260310" / "pending" / "logs"
STATUS_MD = PROJECT_ROOT / "000_LONGRUN_ROUND9_STATUS.md"
STATUS_JSON = PROJECT_ROOT / "000_LONGRUN_ROUND9_STATUS.json"
RUN_FLAG = PROJECT_ROOT / "000_LONGRUN_ROUND9_RUNNING.txt"
NOTIFY_FLAG = PROJECT_ROOT / "000_NOTIFY_CODEX_NOW.txt"


PLAN = [
    {
        "label": "round9_seqval_0p08",
        "args": [
            "Model\\GeoEdgeAlignSR_v1_AutoTuneTrain.py",
            "--profile", "round9_sequence_val_align",
            "--expect-dy", "0.08",
            "--proxy-source", "seq_val",
            "--sweep-epochs", "4",
            "--final-epochs", "6",
            "--skip-final",
            "--deterministic",
        ],
    },
    {
        "label": "round10_seqval_0p8",
        "args": [
            "Model\\GeoEdgeAlignSR_v1_AutoTuneTrain.py",
            "--profile", "round10_crossscale_seqval",
            "--expect-dy", "0.8",
            "--proxy-source", "seq_val",
            "--sweep-epochs", "4",
            "--final-epochs", "6",
            "--skip-final",
            "--deterministic",
        ],
    },
    {
        "label": "round10_seqval_8px",
        "args": [
            "Model\\GeoEdgeAlignSR_v1_AutoTuneTrain.py",
            "--profile", "round10_crossscale_seqval",
            "--expect-dy", "8.0",
            "--proxy-source", "seq_val",
            "--sweep-epochs", "5",
            "--final-epochs", "6",
            "--skip-final",
            "--deterministic",
        ],
    },
    {
        "label": "round9_seqval_0p08_deeper",
        "args": [
            "Model\\GeoEdgeAlignSR_v1_AutoTuneTrain.py",
            "--profile", "round9_sequence_val_align",
            "--expect-dy", "0.08",
            "--proxy-source", "seq_val",
            "--sweep-epochs", "6",
            "--final-epochs", "6",
            "--skip-final",
            "--deterministic",
        ],
    },
]


def _write_status(*, state: str, step_index: int, active_label: str, active_command: str, plan_done: int, plan_total: int, last_report: str = "", last_exit: str = "", note: str = ""):
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
        "updated_at": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime()),
    }
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
                f"note: {note}",
                f"updated_at: {payload['updated_at']}",
            ]
        ),
        encoding="utf-8",
    )


def _latest_report(before_ts: float) -> str:
    best = None
    best_mtime = before_ts
    if not REPORT_ROOT.exists():
        return ""
    for path in REPORT_ROOT.glob("auto_tune_report_*.json"):
        try:
            mtime = path.stat().st_mtime
        except OSError:
            continue
        if mtime >= best_mtime:
            best_mtime = mtime
            best = path
    return str(best) if best is not None else ""


def main():
    LOG_ROOT.mkdir(parents=True, exist_ok=True)
    REPORT_ROOT.mkdir(parents=True, exist_ok=True)
    RUN_FLAG.write_text("RUNNING\n", encoding="utf-8")
    if NOTIFY_FLAG.exists():
        NOTIFY_FLAG.unlink()

    total = len(PLAN)
    _write_status(
        state="running",
        step_index=0,
        active_label="bootstrap",
        active_command="",
        plan_done=0,
        plan_total=total,
        note="starting long-run sequence-aware experiments",
    )

    try:
        for idx, step in enumerate(PLAN, start=1):
            label = str(step["label"])
            cmd = [sys.executable, "-u", *step["args"]]
            cmd_text = " ".join(cmd)
            _write_status(
                state="running",
                step_index=idx,
                active_label=label,
                active_command=cmd_text,
                plan_done=idx - 1,
                plan_total=total,
                note="step running",
            )
            print(f"[LONGRUN] step {idx}/{total} start label={label}")
            print(f"[LONGRUN] cmd={cmd_text}")
            before_ts = time.time()
            proc = subprocess.Popen(
                cmd,
                cwd=str(PROJECT_ROOT),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
            )
            assert proc.stdout is not None
            for line in proc.stdout:
                print(line, end="")
            rc = proc.wait()
            latest_report = _latest_report(before_ts - 1.0)
            if rc != 0:
                _write_status(
                    state="error",
                    step_index=idx,
                    active_label=label,
                    active_command=cmd_text,
                    plan_done=idx - 1,
                    plan_total=total,
                    last_report=latest_report,
                    last_exit=str(rc),
                    note="step failed",
                )
                NOTIFY_FLAG.write_text("LONGRUN FAILED\n", encoding="utf-8")
                print(f"[LONGRUN] step failed rc={rc} label={label}")
                sys.exit(rc)
            print(f"[LONGRUN] step {idx}/{total} done label={label} report={latest_report}")
            _write_status(
                state="running",
                step_index=idx,
                active_label=label,
                active_command=cmd_text,
                plan_done=idx,
                plan_total=total,
                last_report=latest_report,
                last_exit="0",
                note="step completed",
            )

        _write_status(
            state="completed",
            step_index=total,
            active_label="",
            active_command="",
            plan_done=total,
            plan_total=total,
            last_exit="0",
            note="all steps completed",
        )
        print("[LONGRUN] COMPLETED")
    finally:
        if RUN_FLAG.exists():
            RUN_FLAG.unlink()


if __name__ == "__main__":
    main()

#!/usr/bin/env python
import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional


PROJECT_ROOT = Path(__file__).resolve().parents[1]
ORGANIZED_ROOT = PROJECT_ROOT / "Traing_Progress" / "organized_20260309"
PENDING_ROOT = ORGANIZED_ROOT / "pending"
PENDING_LOGS = PENDING_ROOT / "logs"
PENDING_REPORTS = PENDING_ROOT / "reports"
SELECTED_MULTI = ORGANIZED_ROOT / "selected" / "multiscale"
ROOT_STATUS_JSON = PROJECT_ROOT / "000_LONGRUN_STATUS.json"
ROOT_STATUS_MD = PROJECT_ROOT / "000_LONGRUN_STATUS.md"
ROOT_RUNNING_TXT = PROJECT_ROOT / "000_LONGRUN_RUNNING.txt"
ROOT_NOTIFY_TXT = PROJECT_ROOT / "000_NOTIFY_CODEX_NOW.txt"


def _now() -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())


def _ensure_dirs() -> None:
    PENDING_LOGS.mkdir(parents=True, exist_ok=True)
    PENDING_REPORTS.mkdir(parents=True, exist_ok=True)
    SELECTED_MULTI.mkdir(parents=True, exist_ok=True)


def _safe_float(v: Any, default: float = float("nan")) -> float:
    try:
        x = float(v)
    except Exception:
        return float(default)
    if x != x or x in (float("inf"), float("-inf")):
        return float(default)
    return float(x)


def _pid_alive(pid: int) -> bool:
    proc = subprocess.run(
        ["tasklist", "/FI", f"PID eq {pid}", "/FO", "CSV", "/NH"],
        capture_output=True,
        text=True,
        check=False,
    )
    out = (proc.stdout or "").strip()
    return bool(out) and "No tasks are running" not in out and f'"{pid}"' in out


def _read_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _write_root_status(payload: Dict[str, Any]) -> None:
    ROOT_STATUS_JSON.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    lines = [
        "# LongRun 狀態",
        "",
        f"- updated_at: `{payload.get('updated_at', '')}`",
        f"- state: `{payload.get('state', '')}`",
        f"- step: `{payload.get('step', '')}`",
        f"- message: `{payload.get('message', '')}`",
    ]
    if payload.get("active_command"):
        lines.append(f"- active_command: `{payload.get('active_command')}`")
    if payload.get("active_pid") is not None:
        lines.append(f"- active_pid: `{payload.get('active_pid')}`")
    if payload.get("active_out_log"):
        lines.append(f"- active_out_log: `{payload.get('active_out_log')}`")
    if payload.get("plan_total") is not None:
        lines.append(f"- plan_total: `{payload.get('plan_total')}`")
    if payload.get("plan_done") is not None:
        lines.append(f"- plan_done: `{payload.get('plan_done')}`")
    if payload.get("last_report"):
        lines.append(f"- last_report: `{payload.get('last_report')}`")
    ROOT_STATUS_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")

    if ROOT_NOTIFY_TXT.exists():
        ROOT_NOTIFY_TXT.unlink()
    if ROOT_RUNNING_TXT.exists():
        ROOT_RUNNING_TXT.unlink()
    if str(payload.get("state")) in {"running", "waiting_current"}:
        ROOT_RUNNING_TXT.write_text(
            "LongRun 自動化流程仍在執行中。\n查看 000_LONGRUN_STATUS.md。\n",
            encoding="utf-8",
        )
    else:
        ROOT_NOTIFY_TXT.write_text(
            "LongRun 自動化流程已結束或需要檢查。\n查看 000_LONGRUN_STATUS.md。\n",
            encoding="utf-8",
        )


def _report_summary_lines(report: Dict[str, Any]) -> List[str]:
    best = dict(report.get("best_candidate") or {})
    final_run = dict(report.get("final_run") or {})
    recommended = dict(report.get("recommended_deploy") or {})
    lines = [
        f"- profile: `{report.get('profile', '')}`",
        f"- timestamp: `{report.get('timestamp', '')}`",
    ]
    if best:
        lines.extend(
            [
                f"- best_candidate: `{best.get('name', '')}`",
                f"- best_score: `{_safe_float(best.get('score_shift_first'), float('nan')):.6f}`",
                f"- best_progress_dir: `{best.get('progress_dir', '')}`",
            ]
        )
    if final_run:
        lines.extend(
            [
                f"- final_score: `{_safe_float(final_run.get('score_shift_first'), float('nan')):.6f}`",
                f"- final_progress_dir: `{final_run.get('progress_dir', '')}`",
            ]
        )
    if recommended:
        lines.extend(
            [
                f"- recommended_kind: `{recommended.get('kind', '')}`",
                f"- recommended_score: `{_safe_float(recommended.get('score_shift_first'), float('nan')):.6f}`",
                f"- recommended_checkpoint: `{recommended.get('checkpoint_path', '')}`",
            ]
        )
    return lines


def _latest_report_since(since_ts: float) -> Optional[Path]:
    reports = sorted((PROJECT_ROOT / "Traing_Progress" / "auto_tune_reports").glob("auto_tune_report_*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    for report in reports:
        if report.stat().st_mtime >= since_ts - 2.0:
            return report
    return None


def _sanitize_step_key(expect_dy: float) -> str:
    return f"{expect_dy:g}".replace("-", "m").replace(".", "p")


def _multiscale_manifest_path(expect_dy: float) -> Path:
    return SELECTED_MULTI / f"best_step_{_sanitize_step_key(expect_dy)}.json"


def _maybe_update_multiscale_best(expect_dy: float, report_path: Path, report: Dict[str, Any]) -> None:
    best = dict(report.get("best_candidate") or {})
    recommended = dict(report.get("recommended_deploy") or {})
    chosen = recommended or best
    score = _safe_float(chosen.get("score_shift_first"), float("-inf"))
    manifest_path = _multiscale_manifest_path(expect_dy)
    current = _read_json(manifest_path)
    baseline = _safe_float(current.get("best_score"), float("-inf"))
    if score <= baseline:
        return
    payload = {
        "updated_at": _now(),
        "expect_dy": float(expect_dy),
        "profile": report.get("profile", ""),
        "best_score": float(score),
        "best_candidate": chosen.get("candidate", best.get("name", "")),
        "best_kind": chosen.get("kind", "sweep"),
        "best_progress_dir": chosen.get("progress_dir", best.get("progress_dir", "")),
        "best_checkpoint_path": chosen.get("checkpoint_path", best.get("best_checkpoint_path", "")),
        "report_path": str(report_path),
    }
    manifest_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def _write_run_summary(report_path: Path, report: Dict[str, Any]) -> Path:
    summary_path = PENDING_REPORTS / f"LONGRUN_RESULT_{report_path.stem}.md"
    lines = [f"# LongRun 結果 {report_path.stem}", ""]
    lines.extend(_report_summary_lines(report))
    summary_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return summary_path


def _launch_command(command: str, tag: str) -> Dict[str, Any]:
    ts = time.strftime("%Y%m%d_%H%M%S", time.localtime())
    out_path = PENDING_LOGS / f"longrun_{ts}_{tag}.out.log"
    err_path = PENDING_LOGS / f"longrun_{ts}_{tag}.err.log"
    with open(out_path, "w", encoding="utf-8", errors="replace") as out_f, open(err_path, "w", encoding="utf-8", errors="replace") as err_f:
        proc = subprocess.Popen(
            command,
            cwd=str(PROJECT_ROOT),
            stdout=out_f,
            stderr=err_f,
            text=True,
            shell=True,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    return {
        "pid": int(proc.pid),
        "out_log": out_path,
        "err_log": err_path,
        "command": command,
        "start_ts": time.time(),
    }


def _wait_pid(pid: int, poll_sec: int = 20) -> None:
    while _pid_alive(pid):
        time.sleep(max(3, int(poll_sec)))


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--watch-pid", type=int, required=True)
    p.add_argument("--plan-json", type=str, required=True)
    args = p.parse_args()

    _ensure_dirs()
    plan_path = Path(args.plan_json).resolve()
    plan = _read_json(plan_path)
    commands = list(plan.get("commands", []))
    plan_total = len(commands)

    _write_root_status(
        {
            "updated_at": _now(),
            "state": "waiting_current",
            "step": "watch_round6_pipeline",
            "message": f"等待目前 round6 pipeline (pid={int(args.watch_pid)}) 完成",
            "plan_total": plan_total,
            "plan_done": 0,
        }
    )

    while _pid_alive(int(args.watch_pid)):
        _write_root_status(
            {
                "updated_at": _now(),
                "state": "waiting_current",
                "step": "watch_round6_pipeline",
                "message": f"等待目前 round6 pipeline (pid={int(args.watch_pid)}) 完成",
                "plan_total": plan_total,
                "plan_done": 0,
            }
        )
        time.sleep(30)

    done = 0
    for item in commands:
        command = str(item.get("command", "")).strip()
        tag = str(item.get("tag", f"job{done+1}")).strip() or f"job{done+1}"
        expect_dy = float(item.get("expect_dy", 0.0))
        if not command:
            done += 1
            continue

        launched = _launch_command(command, tag)
        _write_root_status(
            {
                "updated_at": _now(),
                "state": "running",
                "step": f"run_{tag}",
                "message": f"執行 {tag}",
                "active_command": command,
                "active_pid": launched["pid"],
                "active_out_log": str(launched["out_log"]),
                "plan_total": plan_total,
                "plan_done": done,
            }
        )
        _wait_pid(int(launched["pid"]))

        report_path = _latest_report_since(float(launched["start_ts"]))
        if report_path is not None:
            report = _read_json(report_path)
            _maybe_update_multiscale_best(expect_dy, report_path, report)
            summary_path = _write_run_summary(report_path, report)
            _write_root_status(
                {
                    "updated_at": _now(),
                    "state": "running",
                    "step": f"done_{tag}",
                    "message": f"{tag} 已完成，準備下一個",
                    "last_report": str(report_path),
                    "active_command": command,
                    "active_out_log": str(launched["out_log"]),
                    "plan_total": plan_total,
                    "plan_done": done + 1,
                    "summary_path": str(summary_path),
                }
            )
        else:
            _write_root_status(
                {
                    "updated_at": _now(),
                    "state": "running",
                    "step": f"done_{tag}",
                    "message": f"{tag} 完成但未找到新 report",
                    "active_command": command,
                    "active_out_log": str(launched["out_log"]),
                    "plan_total": plan_total,
                    "plan_done": done + 1,
                }
            )

        done += 1
        time.sleep(5)

    _write_root_status(
        {
            "updated_at": _now(),
            "state": "stopped",
            "step": "done",
            "message": "LongRun 續跑計畫已全部完成，現在可以通知 Codex 檢查結果",
            "plan_total": plan_total,
            "plan_done": done,
        }
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())

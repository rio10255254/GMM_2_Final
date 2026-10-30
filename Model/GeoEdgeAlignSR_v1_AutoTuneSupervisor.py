#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Monitor an active autotune process, then post-process its report and optionally
launch one chained continuation round when the internal seed improves.
"""

import argparse
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

_CREATE_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


def _now_str() -> str:
    return time.strftime("%Y%m%d_%H%M%S", time.localtime())


def _read_meta(meta_path: Path) -> Dict[str, str]:
    data: Dict[str, str] = {}
    for line in meta_path.read_text(encoding="utf-8").splitlines():
        if "=" not in line:
            continue
        k, v = line.split("=", 1)
        data[k.strip()] = v.strip()
    return data


def _pid_alive(pid: int) -> bool:
    proc = subprocess.run(
        ["tasklist", "/FI", f"PID eq {pid}", "/FO", "CSV", "/NH"],
        capture_output=True,
        text=True,
        check=False,
    )
    out = (proc.stdout or "").strip()
    return bool(out) and "No tasks are running" not in out and f'"{pid}"' in out


def _tail_text(path: Path, max_lines: int = 20) -> str:
    if not path.exists():
        return ""
    text = path.read_text(encoding="utf-8", errors="replace")
    lines = [ln for ln in text.splitlines() if ln.strip()]
    return "\n".join(lines[-max_lines:])


def _pick_status_line(tail_text: str) -> str:
    lines = [ln.strip() for ln in tail_text.splitlines() if ln.strip()]
    for prefix in (
        "[AUTO][FINAL][DONE]",
        "[AUTO][FINAL] start",
        "[AUTO][SWEEP][DONE]",
        "[GMF_SUMMARY]",
        "Starting Epoch",
    ):
        for line in reversed(lines):
            if prefix in line:
                return line
    return lines[-1] if lines else ""


def _wait_for_report(report_root: Path, since_ts: float, timeout_sec: int) -> Optional[Path]:
    deadline = time.time() + max(5, int(timeout_sec))
    while time.time() < deadline:
        reports = sorted(report_root.glob("auto_tune_report_*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
        for path in reports:
            if path.stat().st_mtime >= since_ts - 2.0:
                return path
        time.sleep(5)
    return None


def _load_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _safe_float(v: Any, default: float) -> float:
    try:
        x = float(v)
    except Exception:
        return float(default)
    if x != x or x in (float("inf"), float("-inf")):
        return float(default)
    return float(x)


def _ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def _write_status_files(status_root: Path, payload: Dict[str, Any]) -> None:
    _ensure_dir(status_root)
    json_path = status_root / "CURRENT_AUTOTUNE_STATUS.json"
    md_path = status_root / "CURRENT_AUTOTUNE_STATUS.md"

    json_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

    lines = [
        f"# AutoTune 狀態",
        "",
        f"- state: `{payload.get('state', '')}`",
        f"- updated_at: `{payload.get('updated_at', '')}`",
        f"- user_should_notify_codex: `{str(bool(payload.get('user_should_notify_codex', False))).lower()}`",
        f"- next_action: `{payload.get('next_action', '')}`",
        "",
    ]
    if payload.get("active_pid") is not None:
        lines.append(f"- active_pid: `{payload.get('active_pid')}`")
    if payload.get("active_meta"):
        lines.append(f"- active_meta: `{payload.get('active_meta')}`")
    if payload.get("active_out_log"):
        lines.append(f"- active_out_log: `{payload.get('active_out_log')}`")
    if payload.get("status_line"):
        lines.extend(["", "## 最新狀態行", "", f"`{payload.get('status_line')}`", ""])
    if payload.get("report_path"):
        lines.append(f"- report_path: `{payload.get('report_path')}`")
    if payload.get("summary_path"):
        lines.append(f"- summary_path: `{payload.get('summary_path')}`")
    if payload.get("current_seed_path"):
        lines.append(f"- current_seed_path: `{payload.get('current_seed_path')}`")
    if payload.get("chain_plan_path"):
        lines.append(f"- chain_plan_path: `{payload.get('chain_plan_path')}`")
    if payload.get("plan_total") is not None:
        lines.append(f"- plan_total: `{int(payload.get('plan_total'))}`")
    if payload.get("plan_remaining") is not None:
        lines.append(f"- plan_remaining: `{int(payload.get('plan_remaining'))}`")
    if payload.get("baseline_score") is not None:
        lines.append(f"- baseline_score: `{float(payload.get('baseline_score')):.6f}`")
    if payload.get("best_score") is not None:
        lines.append(f"- best_score: `{float(payload.get('best_score')):.6f}`")
    if payload.get("improved") is not None:
        lines.append(f"- improved: `{str(bool(payload.get('improved'))).lower()}`")

    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_root_visible_flags(project_root: Path, payload: Dict[str, Any]) -> None:
    status_md = project_root / "000_AUTOTUNE_STATUS.md"
    status_json = project_root / "000_AUTOTUNE_STATUS.json"
    running_txt = project_root / "000_AUTOTUNE_RUNNING.txt"
    notify_txt = project_root / "000_NOTIFY_CODEX_NOW.txt"

    status_json.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

    notify = bool(payload.get("user_should_notify_codex", False))
    state = str(payload.get("state", ""))
    next_action = str(payload.get("next_action", ""))
    updated_at = str(payload.get("updated_at", ""))
    status_line = str(payload.get("status_line", ""))

    lines = [
        "# AutoTune 即時狀態",
        "",
        f"- state: `{state}`",
        f"- updated_at: `{updated_at}`",
        f"- 現在是否要通知 Codex: `{'是' if notify else '否'}`",
        "",
    ]
    if notify:
        lines.append("## 現在要做的事")
        lines.append("")
        lines.append("請現在回到對話中通知 Codex。")
    else:
        lines.append("## 現在要做的事")
        lines.append("")
        lines.append("目前不需要通知 Codex，內部流程仍在跑或仍在自動收尾。")
    lines.extend(["", f"- next_action: `{next_action}`"])
    if payload.get("active_pid") is not None:
        lines.append(f"- active_pid: `{payload.get('active_pid')}`")
    if payload.get("active_out_log"):
        lines.append(f"- active_out_log: `{payload.get('active_out_log')}`")
    if payload.get("chain_plan_path"):
        lines.append(f"- chain_plan_path: `{payload.get('chain_plan_path')}`")
    if payload.get("plan_total") is not None:
        lines.append(f"- plan_total: `{int(payload.get('plan_total'))}`")
    if payload.get("plan_remaining") is not None:
        lines.append(f"- plan_remaining: `{int(payload.get('plan_remaining'))}`")
    if status_line:
        lines.extend(["", "## 最新狀態行", "", f"`{status_line}`"])
    status_md.write_text("\n".join(lines) + "\n", encoding="utf-8")

    if running_txt.exists():
        running_txt.unlink()
    if notify_txt.exists():
        notify_txt.unlink()

    if notify:
        notify_txt.write_text(
            "請現在通知 Codex。\n查看 000_AUTOTUNE_STATUS.md 了解詳情。\n",
            encoding="utf-8",
        )
    else:
        running_txt.write_text(
            "AutoTune 仍在執行或仍在自動收尾，現在不用通知 Codex。\n查看 000_AUTOTUNE_STATUS.md 了解詳情。\n",
            encoding="utf-8",
        )


def _move_tree(src: Path, dst_parent: Path) -> Optional[Path]:
    if not src.exists():
        return None
    dst = dst_parent / src.name
    if src.resolve() == dst.resolve():
        return dst
    if dst.exists():
        return dst
    _ensure_dir(dst_parent)
    shutil.move(str(src), str(dst))
    return dst


def _copy_file(src: Path, dst: Path) -> Path:
    _ensure_dir(dst.parent)
    if not dst.exists():
        shutil.copy2(src, dst)
    return dst


def _load_seed_manifest(manifest_path: Path) -> Dict[str, Any]:
    if manifest_path.exists():
        return _load_json(manifest_path)
    return {}


def _write_seed_manifest(manifest_path: Path, payload: Dict[str, Any]) -> None:
    _ensure_dir(manifest_path.parent)
    manifest_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def _load_chain_plan(plan_path: Optional[Path]) -> Dict[str, Any]:
    if not plan_path or not plan_path.exists():
        return {"commands": [], "next_index": 0}
    data = _load_json(plan_path)
    if isinstance(data, list):
        return {"commands": [str(x) for x in data], "next_index": 0}
    commands = [str(x) for x in data.get("commands", [])]
    next_index = int(data.get("next_index", 0))
    return {"commands": commands, "next_index": next_index}


def _save_chain_plan(plan_path: Optional[Path], state: Dict[str, Any]) -> None:
    if not plan_path:
        return
    _ensure_dir(plan_path.parent)
    plan_path.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")


def _pop_next_chain_command(plan_path: Optional[Path]) -> Tuple[str, int, int]:
    state = _load_chain_plan(plan_path)
    commands = [str(x) for x in state.get("commands", [])]
    next_index = int(state.get("next_index", 0))
    total = len(commands)
    if next_index >= total:
        return "", total, 0
    cmd = commands[next_index]
    state["next_index"] = next_index + 1
    _save_chain_plan(plan_path, state)
    remaining = total - state["next_index"]
    return str(cmd), total, int(remaining)


def _normalize_entries(report: Dict[str, Any]) -> List[Dict[str, Any]]:
    entries: List[Dict[str, Any]] = []
    for item in report.get("candidates", []):
        if "score_shift_first" not in item:
            continue
        entries.append(
            {
                "kind": "candidate",
                "name": str(item.get("candidate", "")),
                "score": _safe_float(item.get("score_shift_first"), -1.0e9),
                "progress_dir": str(item.get("progress_dir", "")),
                "summary": dict(item.get("summary", {})),
            }
        )
    final_run = report.get("final_run") or {}
    if final_run and "score_shift_first" in final_run:
        entries.append(
            {
                "kind": "final_run",
                "name": str(final_run.get("candidate", "final_run")),
                "score": _safe_float(final_run.get("score_shift_first"), -1.0e9),
                "progress_dir": str(final_run.get("progress_dir", "")),
                "summary": dict(final_run.get("summary", {})),
            }
        )
    entries.sort(key=lambda x: x["score"], reverse=True)
    return entries


def _format_summary_lines(entry: Dict[str, Any]) -> List[str]:
    s = entry.get("summary", {})
    return [
        f"- 類型: `{entry['kind']}`",
        f"- 名稱: `{entry['name']}`",
        f"- 內部分數: `{entry['score']:.6f}`",
        f"- step_err: `{_safe_float(s.get('best_step_err'), float('nan')):.6f}`",
        f"- pos_std_sum: `{_safe_float(s.get('best_pos_std_sum'), float('nan')):.6f}`",
        f"- kpi_step_std: `{_safe_float(s.get('best_kpi_step_std'), float('nan')):.6f}`",
        f"- kpi_outlier_rate: `{_safe_float(s.get('best_kpi_outlier_rate'), float('nan')):.6f}`",
        f"- kpi_step_mean_err: `{_safe_float(s.get('best_kpi_step_mean_err'), float('nan')):.6f}`",
        f"- gmf_obj: `{_safe_float(s.get('best_gmf_obj'), float('nan')):.6f}`",
        f"- run: `{entry['progress_dir']}`",
    ]


def _postprocess_report(
    *,
    report_path: Path,
    organized_root: Path,
    promote_threshold: float,
    log_fn,
) -> Tuple[bool, Optional[Path], float, Optional[Path]]:
    selected_root = organized_root / "selected"
    rejected_root = organized_root / "rejected"
    pending_root = organized_root / "pending"
    manifest_path = selected_root / "current_seed.json"
    current_manifest = _load_seed_manifest(manifest_path)
    baseline_score = _safe_float(current_manifest.get("internal_best_score"), -1.0e9)

    report = _load_json(report_path)
    entries = _normalize_entries(report)
    if not entries:
        log_fn(f"[POST] no valid entries in report {report_path}")
        return False, None, baseline_score, None

    best_entry = entries[0]
    best_run_src = Path(best_entry["progress_dir"])
    best_score = float(best_entry["score"])
    improved = best_score > (baseline_score + float(promote_threshold))

    summary_md = pending_root / "reports" / f"AUTO_TUNE_RESULT_{report.get('timestamp', _now_str())}.md"
    lines = [
        f"# AutoTune 完成摘要 {report.get('timestamp', _now_str())}",
        "",
        f"- report: `{report_path}`",
        f"- baseline_score: `{baseline_score:.6f}`",
        f"- best_score: `{best_score:.6f}`",
        f"- improved: `{str(improved).lower()}`",
        "",
        "## 最佳內部結果",
        "",
        *_format_summary_lines(best_entry),
        "",
        "## 所有有效候選",
        "",
    ]
    for item in entries:
        lines.extend(_format_summary_lines(item))
        lines.append("")
    _ensure_dir(summary_md.parent)
    summary_md.write_text("\n".join(lines), encoding="utf-8")

    chosen_weights: Optional[Path] = None
    promoted_run_path: Optional[Path] = None
    chosen_report_copy: Optional[Path] = None

    if improved:
        promoted_run_path = _move_tree(best_run_src, selected_root / "runs")
        chosen_weights = (promoted_run_path / "weights" / "best_tradeoff.pth.tar") if promoted_run_path else None
        chosen_report_copy = _copy_file(
            report_path,
            selected_root / "reports" / f"{report_path.stem}_auto.json",
        )
        current_seed_payload = {
            "timestamp": report.get("timestamp", _now_str()),
            "seed_label": best_entry["name"],
            "source_kind": best_entry["kind"],
            "source_run": str(promoted_run_path) if promoted_run_path else str(best_run_src),
            "weights_path": str(chosen_weights) if chosen_weights else "",
            "internal_best_score": float(best_score),
            "origin_report": str(chosen_report_copy),
        }
        _write_seed_manifest(manifest_path, current_seed_payload)
        log_fn(f"[POST] promoted new current_seed score={best_score:.6f} run={current_seed_payload['source_run']}")
    else:
        log_fn(f"[POST] no seed promotion; baseline_score={baseline_score:.6f} best_score={best_score:.6f}")

    selected_path_norm = ""
    if promoted_run_path:
        selected_path_norm = str(promoted_run_path.resolve())
    for item in entries:
        run_src = Path(item["progress_dir"])
        if not run_src.exists():
            continue
        run_norm = str(run_src.resolve())
        if selected_path_norm and run_norm == selected_path_norm:
            continue
        if promoted_run_path and best_run_src.exists():
            try:
                if run_src.resolve() == best_run_src.resolve():
                    continue
            except Exception:
                pass
        _move_tree(run_src, rejected_root / "runs")

    report_bucket = selected_root / "reports" if improved else rejected_root / "reports"
    if not chosen_report_copy:
        chosen_report_copy = _copy_file(report_path, report_bucket / f"{report_path.stem}_auto.json")
    else:
        _copy_file(report_path, report_bucket / f"{report_path.stem}_auto.json")

    return improved, chosen_weights, best_score, summary_md


def _launch_next_round(
    *,
    project_root: Path,
    pending_root: Path,
    command: str,
    generation: int,
    log_fn,
) -> Path:
    ts = _now_str()
    label = f"chain{generation:02d}"
    logs_root = _ensure_dir(pending_root / "logs")
    out_path = logs_root / f"auto_tune_console_{ts}_{label}.out.log"
    err_path = logs_root / f"auto_tune_console_{ts}_{label}.err.log"
    meta_path = logs_root / f"auto_tune_console_{ts}_{label}.meta.txt"

    out_f = open(out_path, "w", encoding="utf-8")
    err_f = open(err_path, "w", encoding="utf-8")
    proc = subprocess.Popen(
        command,
        cwd=str(project_root),
        stdout=out_f,
        stderr=err_f,
        shell=True,
        creationflags=_CREATE_NO_WINDOW,
    )
    meta_path.write_text(
        "\n".join(
            [
                f"pid={proc.pid}",
                f"out={out_path.relative_to(project_root)}",
                f"err={err_path.relative_to(project_root)}",
                f"cmd={command}",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    log_fn(f"[CHAIN] launched pid={proc.pid} cmd={command}")
    return meta_path


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--meta", required=True, help="Path to the active auto_tune meta.txt")
    p.add_argument("--organized-root", default="Experiments/Legacy/organized_20260309")
    p.add_argument("--watch-interval-sec", type=int, default=30)
    p.add_argument("--report-timeout-sec", type=int, default=900)
    p.add_argument("--promote-threshold", type=float, default=0.25)
    p.add_argument("--chain-command", default="")
    p.add_argument("--chain-plan", default="")
    p.add_argument("--max-generations", type=int, default=1)
    args = p.parse_args()

    project_root = Path(__file__).resolve().parents[1]
    organized_root = (project_root / args.organized_root).resolve()
    pending_root = organized_root / "pending"
    report_root = project_root / "Experiments" / "Legacy" / "auto_tune_reports"
    meta_path = Path(args.meta).resolve()
    status_root = pending_root / "status"
    chain_plan_path = Path(args.chain_plan).resolve() if str(args.chain_plan).strip() else None
    chain_state = _load_chain_plan(chain_plan_path)
    chain_total = len(chain_state.get("commands", []))
    chain_remaining = max(0, chain_total - int(chain_state.get("next_index", 0)))

    sup_log = _ensure_dir(pending_root / "logs") / f"auto_tune_supervisor_{_now_str()}.log"

    def log_fn(msg: str) -> None:
        line = f"{time.strftime('%Y-%m-%d %H:%M:%S')} {msg}"
        with open(sup_log, "a", encoding="utf-8") as f:
            f.write(line + "\n")

    def publish_status(payload: Dict[str, Any]) -> None:
        _write_status_files(status_root, payload)
        _write_root_visible_flags(project_root, payload)

    log_fn(f"[SUP] start meta={meta_path}")
    publish_status(
        {
            "state": "starting",
            "updated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "user_should_notify_codex": False,
            "next_action": "等待 supervisor 接手監看目前 round。",
            "active_meta": str(meta_path),
            "chain_plan_path": str(chain_plan_path) if chain_plan_path else "",
            "plan_total": int(chain_total) if chain_plan_path else None,
            "plan_remaining": int(chain_remaining) if chain_plan_path else None,
        },
    )

    generation = 0
    current_meta = meta_path
    while True:
        meta = _read_meta(current_meta)
        pid = int(meta["pid"])
        out_path = (project_root / meta["out"]).resolve()
        since_ts = current_meta.stat().st_mtime
        log_fn(f"[SUP] monitoring pid={pid} out={out_path}")
        publish_status(
            {
                "state": "running",
                "updated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                "user_should_notify_codex": False,
                "next_action": "內部 autotune 仍在執行，不需要通知 Codex。",
                "active_pid": pid,
                "active_meta": str(current_meta),
                "active_out_log": str(out_path),
                "current_seed_path": str(organized_root / "selected" / "current_seed.json"),
                "chain_plan_path": str(chain_plan_path) if chain_plan_path else "",
                "plan_total": int(chain_total) if chain_plan_path else None,
                "plan_remaining": int(chain_remaining) if chain_plan_path else None,
            },
        )

        while _pid_alive(pid):
            tail = _tail_text(out_path, max_lines=30)
            status_line = _pick_status_line(tail)
            try:
                out_stat = out_path.stat()
                log_fn(
                    f"[HEARTBEAT] pid={pid} size={out_stat.st_size} "
                    f"mtime={time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(out_stat.st_mtime))} "
                    f"status={status_line}"
                )
                publish_status(
                    {
                        "state": "running",
                        "updated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                        "user_should_notify_codex": False,
                        "next_action": "內部 autotune 仍在執行，不需要通知 Codex。",
                        "active_pid": pid,
                        "active_meta": str(current_meta),
                        "active_out_log": str(out_path),
                        "status_line": status_line,
                        "current_seed_path": str(organized_root / "selected" / "current_seed.json"),
                        "chain_plan_path": str(chain_plan_path) if chain_plan_path else "",
                        "plan_total": int(chain_total) if chain_plan_path else None,
                        "plan_remaining": int(chain_remaining) if chain_plan_path else None,
                    },
                )
            except FileNotFoundError:
                log_fn(f"[HEARTBEAT] pid={pid} out_missing status={status_line}")
                publish_status(
                    {
                        "state": "running",
                        "updated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                        "user_should_notify_codex": False,
                        "next_action": "程序仍在跑，但 log 暫時不可用。",
                        "active_pid": pid,
                        "active_meta": str(current_meta),
                        "active_out_log": str(out_path),
                        "status_line": status_line,
                        "current_seed_path": str(organized_root / "selected" / "current_seed.json"),
                        "chain_plan_path": str(chain_plan_path) if chain_plan_path else "",
                        "plan_total": int(chain_total) if chain_plan_path else None,
                        "plan_remaining": int(chain_remaining) if chain_plan_path else None,
                    },
                )
            time.sleep(max(5, int(args.watch_interval_sec)))

        log_fn(f"[SUP] pid={pid} exited; waiting for report")
        publish_status(
            {
                "state": "waiting_report",
                "updated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                "user_should_notify_codex": False,
                "next_action": "程序已結束，supervisor 正在等待 autotune report 落盤。",
                "active_pid": pid,
                "active_meta": str(current_meta),
                "active_out_log": str(out_path),
                "current_seed_path": str(organized_root / "selected" / "current_seed.json"),
                "chain_plan_path": str(chain_plan_path) if chain_plan_path else "",
                "plan_total": int(chain_total) if chain_plan_path else None,
                "plan_remaining": int(chain_remaining) if chain_plan_path else None,
            },
        )
        report_path = _wait_for_report(report_root, since_ts=since_ts, timeout_sec=int(args.report_timeout_sec))
        if report_path is None:
            log_fn("[SUP][WARN] no report found after process exit")
            publish_status(
                {
                    "state": "error_no_report",
                    "updated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                    "user_should_notify_codex": True,
                    "next_action": "autotune 程序已結束但沒有找到 report，請通知 Codex 介入。",
                    "active_meta": str(current_meta),
                    "active_out_log": str(out_path),
                    "current_seed_path": str(organized_root / "selected" / "current_seed.json"),
                    "chain_plan_path": str(chain_plan_path) if chain_plan_path else "",
                    "plan_total": int(chain_total) if chain_plan_path else None,
                    "plan_remaining": int(chain_remaining) if chain_plan_path else None,
                },
            )
            return 1

        log_fn(f"[SUP] report={report_path}")
        improved, chosen_weights, best_score, summary_md = _postprocess_report(
            report_path=report_path,
            organized_root=organized_root,
            promote_threshold=float(args.promote_threshold),
            log_fn=log_fn,
        )
        if summary_md:
            log_fn(f"[SUP] summary={summary_md}")

        generation += 1
        next_command = ""
        plan_total = 0
        plan_remaining = 0
        if chain_plan_path:
            next_command, plan_total, plan_remaining = _pop_next_chain_command(chain_plan_path)
            chain_total = int(plan_total)
            chain_remaining = int(plan_remaining)
        elif args.chain_command and generation <= int(args.max_generations):
            next_command = str(args.chain_command)

        if not next_command or (not chain_plan_path and generation > int(args.max_generations)):
            reason_bits = []
            if not next_command:
                reason_bits.append("no_next_command")
            if (not chain_plan_path) and generation > int(args.max_generations):
                reason_bits.append("generation_limit")
            log_fn(f"[SUP] stop reason={','.join(reason_bits)} best_score={best_score:.6f}")
            publish_status(
                {
                    "state": "stopped",
                    "updated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                    "user_should_notify_codex": True,
                    "next_action": "內部 autotune 已停下，現在可以通知 Codex 看結果，或在需要時再提供外部 GMF_score.txt。",
                    "report_path": str(report_path),
                    "summary_path": str(summary_md) if summary_md else "",
                    "current_seed_path": str(organized_root / "selected" / "current_seed.json"),
                    "chain_plan_path": str(chain_plan_path) if chain_plan_path else "",
                    "plan_total": int(chain_total) if chain_plan_path else None,
                    "plan_remaining": int(chain_remaining) if chain_plan_path else None,
                    "best_score": float(best_score),
                    "improved": bool(improved),
                },
            )
            return 0

        current_meta = _launch_next_round(
            project_root=project_root,
            pending_root=pending_root,
            command=str(next_command),
            generation=generation,
            log_fn=log_fn,
        )
        publish_status(
            {
                "state": "chaining_next_round",
                "updated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                "user_should_notify_codex": False,
                "next_action": "已自動啟動下一輪 autotune，不需要通知 Codex。",
                "active_meta": str(current_meta),
                "report_path": str(report_path),
                "summary_path": str(summary_md) if summary_md else "",
                "current_seed_path": str(organized_root / "selected" / "current_seed.json"),
                "chain_plan_path": str(chain_plan_path) if chain_plan_path else "",
                "plan_total": int(plan_total),
                "plan_remaining": int(plan_remaining),
                "best_score": float(best_score),
                "improved": bool(improved),
            },
        )


if __name__ == "__main__":
    sys.exit(main())

"""
GeoEdgeAlignSR_v1_LongRunRound20.py

Round20 process-probe orchestrator.

Goal:
- falsify or support the hypothesis that Epoch0 baseline is suppressing newer losses
- run only 0.8px process-probe sweeps
- avoid data rebuild and external reconstruction
"""
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
REPORT_ROOT = PROJECT_ROOT / "Traing_Progress" / "auto_tune_reports"
ORG_ROOT = PROJECT_ROOT / "Traing_Progress" / "organized_20260314" / "round20"
LOG_ROOT = ORG_ROOT / "pending" / "logs"
SUMMARY_DIR = ORG_ROOT / "selected" / "reports"
SELECTED_DIR = ORG_ROOT / "selected"
STATUS_MD = PROJECT_ROOT / "000_LONGRUN_ROUND20_STATUS.md"
STATUS_JSON = PROJECT_ROOT / "000_LONGRUN_ROUND20_STATUS.json"
RUN_FLAG = PROJECT_ROOT / "000_LONGRUN_ROUND20_RUNNING.txt"
NOTIFY_FLAG = PROJECT_ROOT / "000_NOTIFY_CODEX_NOW.txt"
PROFILE_NAME = "round20_process_probe"
SUMMARY_PREFIX = "ROUND20_PROCESS_PROBE"
RUN_SEED = 1261202
CONTROL_CANDIDATE = "r20_ctrl_r19aa"


PLAN = [
    {
        "label": "round20_process_probe_0p8",
        "args": [
            "Model\\GeoEdgeAlignSR_v1_AutoTuneTrain.py",
            "--profile", PROFILE_NAME,
            "--expect-dy", "0.8",
            "--sweep-epochs", "8",
            "--final-epochs", "6",
            "--seed", str(RUN_SEED),
            "--skip-final",
            "--deterministic",
        ],
    },
]


def _write_status(
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
                f"selected_candidate: {selected_candidate}",
                f"selected_checkpoint: {selected_checkpoint}",
                f"note: {note}",
                f"updated_at: {payload['updated_at']}",
            ]
        ),
        encoding="utf-8",
    )


def _safe_float(v, default=float("nan")):
    try:
        if v is None:
            return default
        return float(v)
    except Exception:
        return default


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


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


def _run_subprocess(cmd: list[str], cwd: Path) -> int:
    proc = subprocess.Popen(
        cmd,
        cwd=str(cwd),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )
    assert proc.stdout is not None
    for line in proc.stdout:
        print(line, end="")
    return proc.wait()


def _process_family_score(summary: dict) -> float:
    center = _safe_float(summary.get("best_ann_seq_center_err_px"), 10.0)
    step = _safe_float(summary.get("best_ann_seq_step_err_rel"), 10.0)
    ann_sign = _safe_float(summary.get("best_ann_seq_sign_acc"), 0.0)
    seq_sign = _safe_float(summary.get("best_seq_val_sign_acc"), 0.0)
    tradeoff = _safe_float(summary.get("best_tradeoff_score"), float("-inf"))
    baseline_pen = 12.0 if bool(summary.get("best_epoch_is_baseline", False)) else 0.0
    return float(
        tradeoff
        + 10.0 * ann_sign
        + 6.0 * seq_sign
        - 90.0 * center
        - 60.0 * step
        - baseline_pen
    )


def _summarize_report(report_path: str) -> tuple[dict, Path, Path]:
    payload = _load_json(Path(report_path))
    rows = []
    for cand in payload.get("candidates", []):
        summary = cand.get("summary", {})
        overrides = cand.get("overrides", {})
        rows.append(
            {
                "candidate": str(cand.get("candidate", "")),
                "effective_sweep_epochs": int(cand.get("effective_sweep_epochs", payload.get("sweep_epochs", 0))),
                "baseline_eligible_for_best": bool(overrides.get("BASELINE_ELIGIBLE_FOR_BEST", True)),
                "best_proxy_min_epoch": int(overrides.get("BEST_PROXY_MIN_EPOCH", 0)),
                "geom_method": str(overrides.get("SEQ_GEOM_METHOD", "")),
                "abs_center_w": _safe_float(overrides.get("SEQ_ABS_CENTER_WEIGHT"), 0.0),
                "center_w": _safe_float(overrides.get("SEQ_GEOM_CENTER_WEIGHT"), 0.0),
                "step_mag_w": _safe_float(overrides.get("SEQ_STEP_MAG_WEIGHT"), 0.0),
                "drift_w": _safe_float(overrides.get("SEQ_GEOM_DRIFT_WEIGHT"), 0.0),
                "best_epoch": int(summary.get("best_epoch", -1)) if summary.get("best_epoch") is not None else -1,
                "best_epoch_is_baseline": bool(summary.get("best_epoch_is_baseline", False)),
                "epoch0_tradeoff_score": _safe_float(summary.get("epoch0_tradeoff_score"), float("nan")),
                "epoch0_center_err": _safe_float(summary.get("epoch0_ann_seq_center_err_px"), float("nan")),
                "epoch0_step_err": _safe_float(summary.get("epoch0_ann_seq_step_err_rel"), float("nan")),
                "best_center_err": _safe_float(summary.get("best_ann_seq_center_err_px"), float("nan")),
                "best_step_err": _safe_float(summary.get("best_ann_seq_step_err_rel"), float("nan")),
                "best_ann_sign": _safe_float(summary.get("best_ann_seq_sign_acc"), float("nan")),
                "best_seq_sign": _safe_float(summary.get("best_seq_val_sign_acc"), float("nan")),
                "best_minus_epoch0_center_err": _safe_float(summary.get("best_minus_epoch0_center_err"), float("nan")),
                "best_minus_epoch0_step_err": _safe_float(summary.get("best_minus_epoch0_step_err"), float("nan")),
                "score_shift_first": _safe_float(cand.get("score_shift_first"), float("-inf")),
                "family_probe_score": _process_family_score(summary),
                "progress_dir": str(cand.get("progress_dir", "")),
                "best_checkpoint_path": str(cand.get("best_checkpoint_path", "")),
            }
        )
    if not rows:
        raise RuntimeError("Round20 report contained no candidates.")
    rows.sort(key=lambda x: x["family_probe_score"], reverse=True)
    result = {
        "report_path": report_path,
        "rows": rows,
        "best_family_candidate": rows[0]["candidate"],
        "selection_policy": "single-scale process probe rank: 0.8px center_err primary, step_err secondary, sign accuracy tertiary, baseline-best penalized",
    }
    ts = time.strftime("%Y%m%d_%H%M%S", time.localtime())
    SUMMARY_DIR.mkdir(parents=True, exist_ok=True)
    json_path = SUMMARY_DIR / f"{SUMMARY_PREFIX}_SUMMARY_{ts}.json"
    md_path = SUMMARY_DIR / f"{SUMMARY_PREFIX}_SUMMARY_{ts}.md"
    json_path.write_text(json.dumps(result, indent=2), encoding="utf-8")
    lines = [
        f"# {SUMMARY_PREFIX} Summary",
        "",
        f"- best_family_candidate: {rows[0]['candidate']}",
        f"- selection_policy: {result['selection_policy']}",
        "",
        "| candidate | epochs | base-best | c0 | cbest | dc | sbest | ds | ann | seq | family |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in rows:
        lines.append(
            f"| {row['candidate']} | {row['effective_sweep_epochs']} | {int(row['best_epoch_is_baseline'])} | "
            f"{row['epoch0_center_err']:.4f} | {row['best_center_err']:.4f} | {row['best_minus_epoch0_center_err']:.4f} | "
            f"{row['best_step_err']:.4f} | {row['best_minus_epoch0_step_err']:.4f} | "
            f"{row['best_ann_sign']:.4f} | {row['best_seq_sign']:.4f} | {row['family_probe_score']:.3f} |"
        )
    md_path.write_text("\n".join(lines), encoding="utf-8")
    return result, json_path, md_path


def _run_process_audit(summary_result: dict) -> tuple[dict, Path, Path]:
    rows = list(summary_result["rows"])
    ts = time.strftime("%Y%m%d_%H%M%S", time.localtime())
    audits = []
    for idx, row in enumerate(rows, start=1):
        candidate = str(row["candidate"])
        json_path = SUMMARY_DIR / f"{SUMMARY_PREFIX}_AUDIT_{candidate}_{ts}.json"
        md_path = SUMMARY_DIR / f"{SUMMARY_PREFIX}_AUDIT_{candidate}_{ts}.md"
        cmd = [
            sys.executable,
            "-u",
            str(PROJECT_ROOT / "Model" / "GeoEdgeAlignSR_v1_ProcessProbeAudit.py"),
            "--candidate", candidate,
            "--checkpoint", str(row["best_checkpoint_path"]),
            "--output-json", str(json_path),
            "--output-md", str(md_path),
            "--seed", str(RUN_SEED),
        ]
        print(f"[ROUND20][AUDIT] {idx}/{len(rows)} candidate={candidate}")
        rc = _run_subprocess(cmd, PROJECT_ROOT)
        if rc != 0:
            raise RuntimeError(f"Process audit failed for {candidate} rc={rc}")
        audit_payload = _load_json(json_path)
        s = audit_payload["summary"]
        audits.append(
            {
                "candidate": candidate,
                "effective_sweep_epochs": int(row["effective_sweep_epochs"]),
                "baseline_eligible_for_best": bool(row["baseline_eligible_for_best"]),
                "best_proxy_min_epoch": int(row["best_proxy_min_epoch"]),
                "geom_method": row["geom_method"],
                "abs_center_w": float(row["abs_center_w"]),
                "center_w": float(row["center_w"]),
                "step_mag_w": float(row["step_mag_w"]),
                "family_probe_score": float(row["family_probe_score"]),
                "audit_json": str(json_path),
                "audit_md": str(md_path),
                "best_epoch": int(s.get("best_epoch", -1)) if s.get("best_epoch") is not None else -1,
                "best_epoch_is_baseline": bool(s.get("best_epoch_is_baseline", False)),
                "epoch0_center_err": _safe_float(s.get("epoch0_ann_seq_center_err_px"), float("nan")),
                "epoch0_step_err": _safe_float(s.get("epoch0_ann_seq_step_err_rel"), float("nan")),
                "best_center_err": _safe_float(s.get("best_ann_seq_center_err_px"), float("nan")),
                "best_step_err": _safe_float(s.get("best_ann_seq_step_err_rel"), float("nan")),
                "best_ann_sign": _safe_float(s.get("best_ann_seq_sign_acc"), float("nan")),
                "best_seq_sign": _safe_float(s.get("best_seq_val_sign_acc"), float("nan")),
                "best_minus_epoch0_center_err": _safe_float(s.get("best_minus_epoch0_center_err"), float("nan")),
                "best_minus_epoch0_step_err": _safe_float(s.get("best_minus_epoch0_step_err"), float("nan")),
                "process_score": float(audit_payload["process_score"]),
                "checkpoint_path": str(audit_payload["checkpoint_path"]),
                "passes_target": bool(audit_payload["passes_target"]),
            }
        )

    audits.sort(
        key=lambda x: (
            x["best_center_err"],
            x["best_step_err"],
            -x["best_ann_sign"],
            -x["best_seq_sign"],
            -x["process_score"],
        )
    )
    best = audits[0]
    control = next((row for row in audits if row["candidate"] == CONTROL_CANDIDATE), None)
    if control is None:
        raise RuntimeError(f"Missing control candidate {CONTROL_CANDIDATE} in process audit.")
    center_improvement = float(control["best_center_err"] - best["best_center_err"])
    supports_hypothesis = (
        best["candidate"] != CONTROL_CANDIDATE
        and center_improvement >= 0.02
        and best["best_step_err"] < 0.40
    )
    result = {
        "audits": audits,
        "control_candidate": CONTROL_CANDIDATE,
        "best_candidate": best["candidate"],
        "selected_checkpoint": best["checkpoint_path"],
        "control_center_err": float(control["best_center_err"]),
        "best_center_err": float(best["best_center_err"]),
        "center_improvement_vs_control": center_improvement,
        "supports_baseline_lock_hypothesis": bool(supports_hypothesis),
        "selection_policy": "single-scale process audit: center_err primary, step_err secondary, signs tertiary",
    }
    final_json = SUMMARY_DIR / f"{SUMMARY_PREFIX}_AUDIT_SUMMARY_{ts}.json"
    final_md = SUMMARY_DIR / f"{SUMMARY_PREFIX}_AUDIT_SUMMARY_{ts}.md"
    final_json.write_text(json.dumps(result, indent=2), encoding="utf-8")
    md_lines = [
        f"# {SUMMARY_PREFIX} Audit Summary",
        "",
        f"- control_candidate: {CONTROL_CANDIDATE}",
        f"- best_candidate: {best['candidate']}",
        f"- selected_checkpoint: {best['checkpoint_path']}",
        f"- center_improvement_vs_control: {center_improvement:.6f}",
        f"- supports_baseline_lock_hypothesis: {supports_hypothesis}",
        "",
        "| candidate | epochs | base-best | c0 | cbest | dc | sbest | ds | ann | seq | score |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in audits:
        md_lines.append(
            f"| {row['candidate']} | {row['effective_sweep_epochs']} | {int(row['best_epoch_is_baseline'])} | "
            f"{row['epoch0_center_err']:.4f} | {row['best_center_err']:.4f} | {row['best_minus_epoch0_center_err']:.4f} | "
            f"{row['best_step_err']:.4f} | {row['best_minus_epoch0_step_err']:.4f} | "
            f"{row['best_ann_sign']:.4f} | {row['best_seq_sign']:.4f} | {row['process_score']:.3f} |"
        )
    final_md.write_text("\n".join(md_lines), encoding="utf-8")
    manifest = {
        "candidate": best["candidate"],
        "weights_path": best["checkpoint_path"],
        "summary_json": str(final_json),
        "summary_md": str(final_md),
        "updated_at": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime()),
    }
    (SELECTED_DIR / "current_process_probe_seed.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return result, final_json, final_md


def main() -> None:
    LOG_ROOT.mkdir(parents=True, exist_ok=True)
    SUMMARY_DIR.mkdir(parents=True, exist_ok=True)
    SELECTED_DIR.mkdir(parents=True, exist_ok=True)
    RUN_FLAG.write_text("RUNNING\n", encoding="utf-8")
    if NOTIFY_FLAG.exists():
        NOTIFY_FLAG.unlink()

    total = len(PLAN) + 2
    _write_status(
        state="running",
        step_index=0,
        active_label="bootstrap",
        active_command="",
        plan_done=0,
        plan_total=total,
        note="starting round20 process probe long-run",
    )
    try:
        report_paths = []
        step_done = 0
        for idx, step in enumerate(PLAN, start=1):
            cmd = [sys.executable, "-u", *step["args"]]
            cmd_text = " ".join(cmd)
            _write_status(
                state="running",
                step_index=idx,
                active_label=str(step["label"]),
                active_command=cmd_text,
                plan_done=step_done,
                plan_total=total,
                note="process probe training step running",
            )
            before_ts = time.time()
            rc = _run_subprocess(cmd, PROJECT_ROOT)
            latest_report = _latest_report(before_ts - 1.0)
            if rc != 0:
                _write_status(
                    state="error",
                    step_index=idx,
                    active_label=str(step["label"]),
                    active_command=cmd_text,
                    plan_done=step_done,
                    plan_total=total,
                    last_report=latest_report,
                    last_exit=str(rc),
                    note="process probe training step failed",
                )
                NOTIFY_FLAG.write_text("LONGRUN ROUND20 FAILED\n", encoding="utf-8")
                sys.exit(rc)
            if latest_report:
                report_paths.append(latest_report)
            step_done += 1
            _write_status(
                state="running",
                step_index=idx,
                active_label=str(step["label"]),
                active_command=cmd_text,
                plan_done=step_done,
                plan_total=total,
                last_report=latest_report,
                last_exit="0",
                note="process probe training step completed",
            )

        idx = len(PLAN) + 1
        _write_status(
            state="running",
            step_index=idx,
            active_label="aggregate_process_summary",
            active_command="internal aggregate",
            plan_done=step_done,
            plan_total=total,
            note="aggregating round20 process report",
            last_report=report_paths[-1] if report_paths else "",
        )
        summary_result, summary_json, summary_md = _summarize_report(report_paths[-1])
        step_done += 1
        _write_status(
            state="running",
            step_index=idx,
            active_label="aggregate_process_summary",
            active_command="internal aggregate",
            plan_done=step_done,
            plan_total=total,
            last_report=str(summary_json),
            last_exit="0",
            note="process summary completed",
            selected_candidate=str(summary_result["best_family_candidate"]),
        )

        idx = len(PLAN) + 2
        _write_status(
            state="running",
            step_index=idx,
            active_label="process_audit",
            active_command="internal audit",
            plan_done=step_done,
            plan_total=total,
            last_report=str(summary_json),
            last_exit="0",
            note="auditing 0.8px checkpoints for process probe",
            selected_candidate=str(summary_result["best_family_candidate"]),
        )
        audit_result, audit_json, audit_md = _run_process_audit(summary_result)
        step_done += 1
        note = (
            "process audit completed | "
            + (
                "baseline-lock hypothesis supported"
                if audit_result["supports_baseline_lock_hypothesis"]
                else "baseline-lock hypothesis not supported; plateau likely not caused primarily by baseline selection"
            )
        )
        _write_status(
            state="completed",
            step_index=idx,
            active_label="process_audit",
            active_command="internal audit",
            plan_done=step_done,
            plan_total=total,
            last_report=str(audit_json),
            last_exit="0",
            note=note,
            selected_candidate=str(audit_result["best_candidate"]),
            selected_checkpoint=str(audit_result["selected_checkpoint"]),
        )
        print(f"[ROUND20] COMPLETED | {note}")
    finally:
        if RUN_FLAG.exists():
            RUN_FLAG.unlink()


if __name__ == "__main__":
    main()

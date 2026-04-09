"""
GeoEdgeAlignSR_v1_LongRunRound26.py

Round26 step recovery probe:
1. run 0.8px step_recovery sweep (full sweep + final training)
2. aggregate family summary
3. run 0.8px audits with pairmix_algblend
4. run 8px guard audits with frozen macro estimator policy
5. write decision memo and seed manifest
6. archive new runs
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import time
from pathlib import Path

from GeoEdgeAlignSR_v1_PolicyAccess import load_probe_policy_pack


PROJECT_ROOT = Path(__file__).resolve().parents[1]
REPORT_ROOT = PROJECT_ROOT / "Traing_Progress" / "auto_tune_reports"
ORG_ROOT = PROJECT_ROOT / "Traing_Progress" / "organized_20260316" / "round26"
LOG_ROOT = ORG_ROOT / "pending" / "logs"
SELECTED_DIR = ORG_ROOT / "selected"
REPORT_DIR = SELECTED_DIR / "reports"
ARCHIVE_DIR = ORG_ROOT / "archive"
STATUS_MD = PROJECT_ROOT / "000_LONGRUN_ROUND26_STATUS.md"
STATUS_JSON = PROJECT_ROOT / "000_LONGRUN_ROUND26_STATUS.json"
RUN_FLAG = PROJECT_ROOT / "000_LONGRUN_ROUND26_RUNNING.txt"
PROFILE_NAME = "round26_step_recovery_probe"
SUMMARY_PREFIX = "ROUND26_STEP_RECOVERY"
RUN_SEED = 1261620
CONTROL_CANDIDATE = "r25_sw010"
CONTROL_CHECKPOINT = Path(r"D:\GMM_2_Final\Traing_Progress\organized_20260316\round25\archive\runs\training_progress_GESR_v1_v5_ST0p8_SWP_r25sw010_20260316_173027\weights\best_tradeoff.pth.tar")
POLICY_PATH = PROJECT_ROOT / "ESTIMATOR_POLICY.json"

PLAN = [
    {
        "label": "round26_step_recovery_probe_0p8",
        "args": [
            "Model\\GeoEdgeAlignSR_v1_AutoTuneTrain.py",
            "--profile", PROFILE_NAME,
            "--expect-dy", "0.8",
            "--sweep-epochs", "12",
            "--final-epochs", "8",
            "--seed", str(RUN_SEED),
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


def _load_policy() -> dict:
    return load_probe_policy_pack(POLICY_PATH)


def _family_score(summary: dict) -> float:
    center = _safe_float(summary.get("best_ann_seq_center_err_px"), 10.0)
    step = _safe_float(summary.get("best_ann_seq_step_err_rel"), 10.0)
    ann_sign = _safe_float(summary.get("best_ann_seq_sign_acc"), 0.0)
    seq_sign = _safe_float(summary.get("best_seq_val_sign_acc"), 0.0)
    tradeoff = _safe_float(summary.get("best_tradeoff_score"), float("-inf"))
    baseline_pen = 4.0 if bool(summary.get("best_epoch_is_baseline", False)) else 0.0
    return float(
        tradeoff
        + 10.0 * ann_sign
        + 6.0 * seq_sign
        - 90.0 * center
        - 70.0 * step
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
                "geom_method": str(overrides.get("SEQ_GEOM_METHOD", "")),
                "step_mag_w": _safe_float(overrides.get("SEQ_STEP_MAG_WEIGHT"), 0.0),
                "center_w": _safe_float(overrides.get("SEQ_GEOM_CENTER_WEIGHT"), 0.0),
                "drift_w": _safe_float(overrides.get("SEQ_GEOM_DRIFT_WEIGHT"), 0.0),
                "best_epoch": int(summary.get("best_epoch", -1)) if summary.get("best_epoch") is not None else -1,
                "best_epoch_is_baseline": bool(summary.get("best_epoch_is_baseline", False)),
                "epoch0_center_err": _safe_float(summary.get("epoch0_ann_seq_center_err_px"), float("nan")),
                "epoch0_step_err": _safe_float(summary.get("epoch0_ann_seq_step_err_rel"), float("nan")),
                "best_center_err": _safe_float(summary.get("best_ann_seq_center_err_px"), float("nan")),
                "best_step_err": _safe_float(summary.get("best_ann_seq_step_err_rel"), float("nan")),
                "best_ann_sign": _safe_float(summary.get("best_ann_seq_sign_acc"), float("nan")),
                "best_seq_sign": _safe_float(summary.get("best_seq_val_sign_acc"), float("nan")),
                "best_minus_epoch0_center_err": _safe_float(summary.get("best_minus_epoch0_center_err"), float("nan")),
                "best_minus_epoch0_step_err": _safe_float(summary.get("best_minus_epoch0_step_err"), float("nan")),
                "family_score": _family_score(summary),
                "progress_dir": str(cand.get("progress_dir", "")),
                "best_checkpoint_path": str(cand.get("best_checkpoint_path", "")),
            }
        )
    if not rows:
        raise RuntimeError("Round26 report contained no candidates.")
    rows.sort(key=lambda x: x["family_score"], reverse=True)
    result = {
        "report_path": report_path,
        "rows": rows,
        "best_family_candidate": rows[0]["candidate"],
        "selection_policy": "mid-only hybrid estimator rank: step primary, center secondary, signs tertiary",
    }
    ts = time.strftime("%Y%m%d_%H%M%S", time.localtime())
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    json_path = REPORT_DIR / f"{SUMMARY_PREFIX}_SUMMARY_{ts}.json"
    md_path = REPORT_DIR / f"{SUMMARY_PREFIX}_SUMMARY_{ts}.md"
    json_path.write_text(json.dumps(result, indent=2), encoding="utf-8")
    lines = [
        f"# {SUMMARY_PREFIX} Summary",
        "",
        f"- best_family_candidate: {rows[0]['candidate']}",
        f"- selection_policy: {result['selection_policy']}",
        "",
        "| candidate | method | step_w | center_w | drift_w | base-best | c0 | s0 | cbest | sbest | ann | seq | family |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in rows:
        lines.append(
            f"| {row['candidate']} | {row['geom_method']} | {row['step_mag_w']:.2f} | {row['center_w']:.2f} | {row['drift_w']:.2f} | "
            f"{int(row['best_epoch_is_baseline'])} | {row['epoch0_center_err']:.4f} | {row['epoch0_step_err']:.4f} | "
            f"{row['best_center_err']:.4f} | {row['best_step_err']:.4f} | {row['best_ann_sign']:.4f} | {row['best_seq_sign']:.4f} | "
            f"{row['family_score']:.3f} |"
        )
    md_path.write_text("\n".join(lines), encoding="utf-8")
    return result, json_path, md_path


def _run_process_audits(rows: list[dict], *, expect_dy: float, geom_method_override: str | None = None, label: str) -> tuple[list[dict], Path, Path]:
    ts = time.strftime("%Y%m%d_%H%M%S", time.localtime())
    audits = []
    for idx, row in enumerate(rows, start=1):
        candidate = str(row["candidate"])
        geom_method = str(geom_method_override if geom_method_override else row["geom_method"])
        json_path = REPORT_DIR / f"{SUMMARY_PREFIX}_{label}_{candidate}_{ts}.json"
        md_path = REPORT_DIR / f"{SUMMARY_PREFIX}_{label}_{candidate}_{ts}.md"
        cmd = [
            sys.executable,
            "-u",
            str(PROJECT_ROOT / "Model" / "GeoEdgeAlignSR_v1_ProcessProbeAudit.py"),
            "--candidate", candidate,
            "--checkpoint", str(row["best_checkpoint_path"]),
            "--geom-method", geom_method,
            "--expect-dy", str(float(expect_dy)),
            "--output-json", str(json_path),
            "--output-md", str(md_path),
            "--seed", str(RUN_SEED),
        ]
        print(f"[ROUND26][AUDIT] {label} {idx}/{len(rows)} candidate={candidate} geom={geom_method}")
        rc = _run_subprocess(cmd, PROJECT_ROOT)
        if rc != 0:
            raise RuntimeError(f"{label} audit failed for {candidate} rc={rc}")
        payload = _load_json(json_path)
        s = payload["summary"]
        audits.append(
            {
                "candidate": candidate,
                "geom_method": geom_method,
                "audit_json": str(json_path),
                "audit_md": str(md_path),
                "best_epoch": int(s.get("best_epoch", -1)) if s.get("best_epoch") is not None else -1,
                "best_epoch_is_baseline": bool(s.get("best_epoch_is_baseline", False)),
                "best_center_err": _safe_float(s.get("best_ann_seq_center_err_px"), float("nan")),
                "best_step_err": _safe_float(s.get("best_ann_seq_step_err_rel"), float("nan")),
                "best_ann_sign": _safe_float(s.get("best_ann_seq_sign_acc"), float("nan")),
                "best_seq_sign": _safe_float(s.get("best_seq_val_sign_acc"), float("nan")),
                "process_score": _safe_float(payload.get("process_score"), float("-inf")),
                "checkpoint_path": str(payload.get("checkpoint_path", "")),
            }
        )
    summary = {
        "expect_dy": float(expect_dy),
        "label": label,
        "rows": audits,
        "selection_policy": "center primary, step secondary, signs tertiary" if abs(float(expect_dy) - 8.0) >= 1.0e-6 else "macro guard raw rows",
    }
    final_json = REPORT_DIR / f"{SUMMARY_PREFIX}_{label}_SUMMARY_{ts}.json"
    final_md = REPORT_DIR / f"{SUMMARY_PREFIX}_{label}_SUMMARY_{ts}.md"
    final_json.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    lines = [
        f"# {SUMMARY_PREFIX} {label} Summary",
        "",
        f"- expect_dy: {float(expect_dy):.2f}",
        f"- selection_policy: {summary['selection_policy']}",
        "",
        "| candidate | method | base-best | center | step | ann | seq | score |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in audits:
        lines.append(
            f"| {row['candidate']} | {row['geom_method']} | {int(row['best_epoch_is_baseline'])} | "
            f"{row['best_center_err']:.4f} | {row['best_step_err']:.4f} | {row['best_ann_sign']:.4f} | "
            f"{row['best_seq_sign']:.4f} | {row['process_score']:.3f} |"
        )
    final_md.write_text("\n".join(lines), encoding="utf-8")
    return audits, final_json, final_md


def _write_decision(summary_result: dict, audit08: list[dict], audit8: list[dict], policy_pack: dict) -> tuple[str, str, Path]:
    control_center_ref = policy_pack["control_center_ref"]
    mid_center_ratio_min = policy_pack["mid_center_ratio_min"]
    mid_step_max = policy_pack["mid_step_max"]
    macro_step_max = policy_pack["macro_step_max"]
    macro_seq_sign_min = policy_pack["macro_seq_sign_min"]
    macro_by_candidate = {row["candidate"]: row for row in audit8}

    scored_rows = []
    for row in audit08:
        center = _safe_float(row["best_center_err"], 1e9)
        step = _safe_float(row["best_step_err"], 1e9)
        ratio = 0.0
        if control_center_ref > 1.0e-9 and center == center:
            ratio = max(0.0, (control_center_ref - center) / control_center_ref)
        mid_pass = ratio >= mid_center_ratio_min and step <= mid_step_max
        macro_row = macro_by_candidate.get(row["candidate"])
        macro_pass = False
        if macro_row is not None:
            macro_pass = (
                _safe_float(macro_row["best_step_err"], 1e9) <= macro_step_max
                and _safe_float(macro_row["best_seq_sign"], 0.0) >= macro_seq_sign_min
            )
        final_pass = bool(mid_pass and macro_pass)
        scored_rows.append(
            {
                **row,
                "center_improvement_ratio": float(ratio),
                "mid_pass": bool(mid_pass),
                "macro_pass": bool(macro_pass),
                "final_pass": bool(final_pass),
                "macro_step_err": _safe_float(macro_row["best_step_err"], float("nan")) if macro_row else float("nan"),
                "macro_seq_sign": _safe_float(macro_row["best_seq_sign"], float("nan")) if macro_row else float("nan"),
            }
        )

    scored_rows.sort(
        key=lambda x: (
            0 if x["final_pass"] else 1,
            0 if x["mid_pass"] else 1,
            x["best_step_err"],
            x["best_center_err"],
            -x["best_ann_sign"],
            -x["best_seq_sign"],
        )
    )
    winner = scored_rows[0]
    confirmed = bool(winner["final_pass"])
    selected_candidate = winner["candidate"] if confirmed else CONTROL_CANDIDATE
    selected_checkpoint = next(
        (row["checkpoint_path"] for row in audit08 if row["candidate"] == selected_candidate),
        str(CONTROL_CHECKPOINT if selected_candidate == CONTROL_CANDIDATE else winner["checkpoint_path"]),
    )

    ts = time.strftime("%Y%m%d_%H%M%S", time.localtime())
    memo_path = REPORT_DIR / f"{SUMMARY_PREFIX}_DECISION_{ts}.md"
    memo_json = REPORT_DIR / f"{SUMMARY_PREFIX}_DECISION_{ts}.json"
    memo = {
        "winner_candidate": winner["candidate"],
        "selected_candidate": selected_candidate,
        "selected_checkpoint": selected_checkpoint,
        "confirmed": confirmed,
        "control_center_ref": control_center_ref,
        "mid_center_ratio_min": mid_center_ratio_min,
        "mid_step_max": mid_step_max,
        "macro_step_max": macro_step_max,
        "macro_seq_sign_min": macro_seq_sign_min,
        "macro_estimator": policy_pack["macro_estimator"],
        "rows": scored_rows,
    }
    memo_json.write_text(json.dumps(memo, indent=2), encoding="utf-8")
    lines = [
        f"# {SUMMARY_PREFIX} Decision Memo",
        "",
        f"- winner_candidate: {winner['candidate']}",
        f"- selected_candidate: {selected_candidate}",
        f"- confirmed: {confirmed}",
        f"- selected_checkpoint: {selected_checkpoint}",
        f"- macro_estimator: {policy_pack['macro_estimator']}",
        f"- mid_center_ratio_min: {mid_center_ratio_min:.4f}",
        f"- mid_step_max: {mid_step_max:.4f}",
        f"- macro_step_max: {macro_step_max:.4f}",
        f"- macro_seq_sign_min: {macro_seq_sign_min:.4f}",
        "",
        "| candidate | mid_center | mid_step | ratio | mid_pass | macro_step | macro_seq | macro_pass | final_pass |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in scored_rows:
        lines.append(
            f"| {row['candidate']} | {row['best_center_err']:.4f} | {row['best_step_err']:.4f} | "
            f"{row['center_improvement_ratio']:.4f} | {int(row['mid_pass'])} | {row['macro_step_err']:.4f} | "
            f"{row['macro_seq_sign']:.4f} | {int(row['macro_pass'])} | {int(row['final_pass'])} |"
        )
    memo_path.write_text("\n".join(lines), encoding="utf-8")

    manifest = {
        "candidate": selected_candidate,
        "weights_path": selected_checkpoint,
        "confirmed": confirmed,
        "macro_estimator": policy_pack["macro_estimator"],
        "decision_json": str(memo_json),
        "decision_md": str(memo_path),
        "updated_at": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime()),
    }
    (SELECTED_DIR / "current_round26_step_recovery_seed.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return selected_candidate, selected_checkpoint, memo_path


def _move_new_runs(start_ts: float, selected_candidate: str) -> None:
    selected_root = SELECTED_DIR / "runs"
    archive_runs = ARCHIVE_DIR / "runs"
    archive_audit = ARCHIVE_DIR / "audit_runs"
    archive_logs = ARCHIVE_DIR / "logs"
    for path in (selected_root, archive_runs, archive_audit, archive_logs):
        path.mkdir(parents=True, exist_ok=True)

    for path in (PROJECT_ROOT / "Traing_Progress").glob("training_progress_GESR_v1_v5_ST0p8_SWP_r26*"):
        try:
            mtime = path.stat().st_mtime
        except OSError:
            continue
        if mtime < start_ts:
            continue
        target_dir = selected_root if selected_candidate in path.name else archive_runs
        target = target_dir / path.name
        if target.exists():
            shutil.rmtree(target, ignore_errors=True)
        shutil.move(str(path), str(target))

    for path in (PROJECT_ROOT / "Traing_Progress").glob("training_progress_process_probe_r26*"):
        try:
            mtime = path.stat().st_mtime
        except OSError:
            continue
        if mtime < start_ts:
            continue
        target = archive_audit / path.name
        if target.exists():
            shutil.rmtree(target, ignore_errors=True)
        shutil.move(str(path), str(target))

    for path in LOG_ROOT.glob("*.log"):
        try:
            mtime = path.stat().st_mtime
        except OSError:
            continue
        if mtime < start_ts:
            continue
        target = archive_logs / path.name
        if target.exists():
            target.unlink()
        shutil.copy2(path, target)


def main() -> None:
    LOG_ROOT.mkdir(parents=True, exist_ok=True)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    SELECTED_DIR.mkdir(parents=True, exist_ok=True)
    if not CONTROL_CHECKPOINT.exists():
        raise FileNotFoundError(f"Round26 control checkpoint missing: {CONTROL_CHECKPOINT}")
    RUN_FLAG.write_text("RUNNING\n", encoding="utf-8")

    total = len(PLAN) + 3
    _write_status(
        state="running",
        step_index=0,
        active_label="bootstrap",
        active_command="",
        plan_done=0,
        plan_total=total,
        note="starting Round26 step_recovery estimator probe",
    )
    flow_start_ts = time.time()
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
                note="running Round26 step_recovery training probe",
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
                    note="Round26 step_recovery training probe failed",
                )
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
                note="Round26 step_recovery training probe completed",
            )

        idx = len(PLAN) + 1
        _write_status(
            state="running",
            step_index=idx,
            active_label="aggregate_round26_summary",
            active_command="internal aggregate",
            plan_done=step_done,
            plan_total=total,
            last_report=report_paths[-1] if report_paths else "",
            note="aggregating Round26 training report",
        )
        summary_result, summary_json, _ = _summarize_report(report_paths[-1])
        step_done += 1

        policy_pack = _load_policy()

        idx = len(PLAN) + 2
        _write_status(
            state="running",
            step_index=idx,
            active_label="round26_audit_0p8",
            active_command="internal audit",
            plan_done=step_done,
            plan_total=total,
            last_report=str(summary_json),
            note="running 0.8px pairmix audits",
        )
        audit08_rows, audit08_json, _ = _run_process_audits(
            summary_result["rows"],
            expect_dy=0.8,
            geom_method_override="pairmix_algblend",
            label="AUDIT_0P8",
        )
        step_done += 1

        idx = len(PLAN) + 3
        _write_status(
            state="running",
            step_index=idx,
            active_label="round26_guard_8px",
            active_command="internal audit",
            plan_done=step_done,
            plan_total=total,
            last_report=str(audit08_json),
            note=f"running 8px macro guard audits with {policy_pack['macro_estimator']}",
        )
        audit8_rows, audit8_json, _ = _run_process_audits(
            summary_result["rows"],
            expect_dy=8.0,
            geom_method_override=policy_pack["macro_estimator"],
            label="AUDIT_8P0",
        )

        selected_candidate, selected_checkpoint, memo_path = _write_decision(
            summary_result,
            audit08_rows,
            audit8_rows,
            policy_pack,
        )
        _move_new_runs(flow_start_ts, selected_candidate)

        confirmed = selected_candidate != CONTROL_CANDIDATE
        note = (
            "Round26 passed calibrated pairmix gate"
            if confirmed
            else "Round26 still blocked; pairmix training did not preserve calibrated gate"
        )
        _write_status(
            state="completed",
            step_index=idx,
            active_label="round26_guard_8px",
            active_command="internal audit",
            plan_done=total,
            plan_total=total,
            last_report=str(memo_path),
            last_exit="0",
            note=note,
            selected_candidate=selected_candidate,
            selected_checkpoint=selected_checkpoint,
        )
        print(f"[ROUND26] COMPLETED | {note}")
    finally:
        if RUN_FLAG.exists():
            RUN_FLAG.unlink()


if __name__ == "__main__":
    main()


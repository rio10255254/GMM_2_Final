"""
GeoEdgeAlignSR_v1_LongRunBranchE.py

Branch E estimator-side automation:
1. benchmark estimator candidates against generator replay truth
2. auto-select probe candidates
3. run 0.8px estimator probe
4. run single-scale process audit
5. write decision memo
"""
import json
import subprocess
import sys
import time
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
REPORT_ROOT = PROJECT_ROOT / "Traing_Progress" / "auto_tune_reports"
ORG_ROOT = PROJECT_ROOT / "Traing_Progress" / "organized_20260314" / "branch_e"
BENCHMARK_DIR = ORG_ROOT / "benchmark"
LOG_ROOT = ORG_ROOT / "pending" / "logs"
SUMMARY_DIR = ORG_ROOT / "selected" / "reports"
SELECTED_DIR = ORG_ROOT / "selected"
ARCHIVE_DIR = ORG_ROOT / "archive"
STATUS_MD = PROJECT_ROOT / "000_LONGRUN_BRANCH_E_STATUS.md"
STATUS_JSON = PROJECT_ROOT / "000_LONGRUN_BRANCH_E_STATUS.json"
RUN_FLAG = PROJECT_ROOT / "000_LONGRUN_BRANCH_E_RUNNING.txt"
NOTIFY_FLAG = PROJECT_ROOT / "000_NOTIFY_CODEX_NOW.txt"
PROFILE_NAME = "branchE_estimator_probe"
SUMMARY_PREFIX = "BRANCH_E_ESTIMATOR_PROBE"
RUN_SEED = 1261205
CONTROL_CANDIDATE = "be_ctrl_edge"


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


def _latest_matching(root: Path, pattern: str, before_ts: float) -> str:
    best = None
    best_mtime = before_ts
    for path in root.glob(pattern):
        try:
            mtime = path.stat().st_mtime
        except OSError:
            continue
        if mtime >= best_mtime:
            best = path
            best_mtime = mtime
    return str(best) if best is not None else ""


def _latest_report(before_ts: float) -> str:
    return _latest_matching(REPORT_ROOT, "auto_tune_report_*.json", before_ts)


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


def _estimator_family_score(summary: dict) -> float:
    center = _safe_float(summary.get("best_ann_seq_center_err_px"), 10.0)
    step = _safe_float(summary.get("best_ann_seq_step_err_rel"), 10.0)
    ann_sign = _safe_float(summary.get("best_ann_seq_sign_acc"), 0.0)
    seq_sign = _safe_float(summary.get("best_seq_val_sign_acc"), 0.0)
    tradeoff = _safe_float(summary.get("best_tradeoff_score"), float("-inf"))
    baseline_pen = 6.0 if bool(summary.get("best_epoch_is_baseline", False)) else 0.0
    return float(
        tradeoff
        + 8.0 * ann_sign
        + 5.0 * seq_sign
        - 95.0 * center
        - 55.0 * step
        - baseline_pen
    )


def _summarize_report(report_path: str, benchmark_payload: dict) -> tuple[dict, Path, Path]:
    payload = _load_json(Path(report_path))
    bench_rank = {
        row["probe_candidate"]: row
        for row in benchmark_payload["decision"]["estimator_ranking_0p8_clean_conv"]
        if row.get("probe_candidate")
    }
    rows = []
    for cand in payload.get("candidates", []):
        summary = cand.get("summary", {})
        overrides = cand.get("overrides", {})
        candidate_name = str(cand.get("candidate", ""))
        bench = bench_rank.get(candidate_name, {})
        rows.append(
            {
                "candidate": candidate_name,
                "geom_method": str(overrides.get("SEQ_GEOM_METHOD", "")),
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
                "family_probe_score": _estimator_family_score(summary),
                "score_shift_first": _safe_float(cand.get("score_shift_first"), float("-inf")),
                "progress_dir": str(cand.get("progress_dir", "")),
                "best_checkpoint_path": str(cand.get("best_checkpoint_path", "")),
                "benchmark_avg_abs": _safe_float(bench.get("avg_clean_conv_abs_center_err_px"), float("nan")),
                "benchmark_avg_delta": _safe_float(bench.get("avg_clean_conv_delta_center_err_px"), float("nan")),
                "benchmark_avg_step": _safe_float(bench.get("avg_clean_conv_step_err_rel"), float("nan")),
            }
        )
    if not rows:
        raise RuntimeError("Branch E report contained no candidates.")
    rows.sort(key=lambda x: x["family_probe_score"], reverse=True)
    result = {
        "report_path": report_path,
        "rows": rows,
        "best_family_candidate": rows[0]["candidate"],
        "selection_policy": "0.8px estimator probe rank: center_err primary, step_err secondary, sign tertiary, baseline-best lightly penalized",
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
        "| candidate | method | base-best | c0 | cbest | dc | sbest | ds | ann | seq | bench_abs | family |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in rows:
        lines.append(
            f"| {row['candidate']} | {row['geom_method']} | {int(row['best_epoch_is_baseline'])} | "
            f"{row['epoch0_center_err']:.4f} | {row['best_center_err']:.4f} | {row['best_minus_epoch0_center_err']:.4f} | "
            f"{row['best_step_err']:.4f} | {row['best_minus_epoch0_step_err']:.4f} | "
            f"{row['best_ann_sign']:.4f} | {row['best_seq_sign']:.4f} | {row['benchmark_avg_abs']:.4f} | "
            f"{row['family_probe_score']:.3f} |"
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
            "--candidate",
            candidate,
            "--checkpoint",
            str(row["best_checkpoint_path"]),
            "--geom-method",
            str(row["geom_method"]),
            "--output-json",
            str(json_path),
            "--output-md",
            str(md_path),
            "--seed",
            str(RUN_SEED),
        ]
        print(f"[BRANCH_E][AUDIT] {idx}/{len(rows)} candidate={candidate}")
        rc = _run_subprocess(cmd, PROJECT_ROOT)
        if rc != 0:
            raise RuntimeError(f"Process audit failed for {candidate} rc={rc}")
        audit_payload = _load_json(json_path)
        s = audit_payload["summary"]
        audits.append(
            {
                "candidate": candidate,
                "geom_method": row["geom_method"],
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
        raise RuntimeError(f"Missing control candidate {CONTROL_CANDIDATE} in audit rows.")
    center_improvement = float(control["best_center_err"] - best["best_center_err"])
    estimator_probe_success = (
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
        "estimator_probe_success": bool(estimator_probe_success),
        "selection_policy": "single-scale estimator probe audit: center_err primary, step_err secondary, signs tertiary",
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
        f"- estimator_probe_success: {estimator_probe_success}",
        "",
        "| candidate | method | base-best | c0 | cbest | dc | sbest | ds | ann | seq | score |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in audits:
        md_lines.append(
            f"| {row['candidate']} | {row['geom_method']} | {int(row['best_epoch_is_baseline'])} | "
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
    (SELECTED_DIR / "current_branch_e_probe_seed.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return result, final_json, final_md


def _write_decision_memo(benchmark_payload: dict, audit_payload: dict) -> tuple[Path, Path]:
    ts = time.strftime("%Y%m%d_%H%M%S", time.localtime())
    best_probe = audit_payload["best_candidate"]
    best_non_control = benchmark_payload["decision"]["best_non_control_estimator"]
    if audit_payload["estimator_probe_success"]:
        next_action = "Estimator-side probe succeeded. Promote the winning estimator to the next guarded multiscale branch."
    elif best_probe == CONTROL_CANDIDATE:
        next_action = "Benchmark candidates did not translate into a better trained 0.8px probe. Stay in Branch E and inspect estimator/loss coupling before naming Round21."
    else:
        next_action = "A non-control estimator won family ranking but did not clear the audit gate. Keep Branch E active and refine estimator formulation before any new round."
    payload = {
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime()),
        "benchmark_best_non_control_estimator": best_non_control,
        "benchmark_probe_candidates": benchmark_payload["decision"]["chosen_probe_candidates"],
        "audit_best_candidate": best_probe,
        "center_improvement_vs_control": audit_payload["center_improvement_vs_control"],
        "estimator_probe_success": audit_payload["estimator_probe_success"],
        "next_action": next_action,
    }
    json_path = SUMMARY_DIR / f"{SUMMARY_PREFIX}_DECISION_{ts}.json"
    md_path = SUMMARY_DIR / f"{SUMMARY_PREFIX}_DECISION_{ts}.md"
    json_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    md_lines = [
        f"# {SUMMARY_PREFIX} Decision Memo",
        "",
        f"- benchmark_best_non_control_estimator: `{best_non_control}`",
        f"- benchmark_probe_candidates: `{', '.join(benchmark_payload['decision']['chosen_probe_candidates'])}`",
        f"- audit_best_candidate: `{best_probe}`",
        f"- center_improvement_vs_control: {audit_payload['center_improvement_vs_control']:.6f}",
        f"- estimator_probe_success: {audit_payload['estimator_probe_success']}",
        "",
        "## Next Action",
        next_action,
    ]
    md_path.write_text("\n".join(md_lines), encoding="utf-8")
    return json_path, md_path


def main() -> None:
    LOG_ROOT.mkdir(parents=True, exist_ok=True)
    BENCHMARK_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY_DIR.mkdir(parents=True, exist_ok=True)
    SELECTED_DIR.mkdir(parents=True, exist_ok=True)
    ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
    RUN_FLAG.write_text("RUNNING\n", encoding="utf-8")
    if NOTIFY_FLAG.exists():
        NOTIFY_FLAG.unlink()

    total = 5
    _write_status(
        state="running",
        step_index=0,
        active_label="bootstrap",
        active_command="",
        plan_done=0,
        plan_total=total,
        note="starting Branch E estimator automation",
    )
    try:
        step_done = 0

        # Step 1: benchmark
        cmd = [
            sys.executable,
            "-u",
            "Model\\GeoEdgeAlignSR_v1_BranchEEstimatorBenchmark.py",
            "--output-root",
            str(BENCHMARK_DIR),
            "--top-k-trainable",
            "3",
        ]
        cmd_text = " ".join(cmd)
        _write_status(
            state="running",
            step_index=1,
            active_label="branch_e_benchmark",
            active_command=cmd_text,
            plan_done=step_done,
            plan_total=total,
            note="running estimator benchmark against generator replay truth",
        )
        before_ts = time.time()
        rc = _run_subprocess(cmd, PROJECT_ROOT)
        benchmark_summary = _latest_matching(BENCHMARK_DIR, "BRANCH_E_ESTIMATOR_BENCHMARK_SUMMARY_*.json", before_ts - 1.0)
        if rc != 0 or not benchmark_summary:
            _write_status(
                state="error",
                step_index=1,
                active_label="branch_e_benchmark",
                active_command=cmd_text,
                plan_done=step_done,
                plan_total=total,
                last_report=benchmark_summary,
                last_exit=str(rc),
                note="branch E benchmark failed",
            )
            NOTIFY_FLAG.write_text("LONGRUN BRANCH E FAILED\n", encoding="utf-8")
            sys.exit(rc if rc != 0 else 1)
        benchmark_payload = _load_json(Path(benchmark_summary))
        step_done += 1
        _write_status(
            state="running",
            step_index=1,
            active_label="branch_e_benchmark",
            active_command=cmd_text,
            plan_done=step_done,
            plan_total=total,
            last_report=benchmark_summary,
            last_exit="0",
            note=f"benchmark completed | probe candidates={','.join(benchmark_payload['decision']['chosen_probe_candidates'])}",
        )

        # Step 2: 0.8px estimator probe
        candidate_filter = ",".join(benchmark_payload["decision"]["chosen_probe_candidates"])
        cmd = [
            sys.executable,
            "-u",
            "Model\\GeoEdgeAlignSR_v1_AutoTuneTrain.py",
            "--profile",
            PROFILE_NAME,
            "--expect-dy",
            "0.8",
            "--candidate-filter",
            candidate_filter,
            "--sweep-epochs",
            "6",
            "--final-epochs",
            "6",
            "--seed",
            str(RUN_SEED),
            "--skip-final",
            "--deterministic",
        ]
        cmd_text = " ".join(cmd)
        _write_status(
            state="running",
            step_index=2,
            active_label="branch_e_probe_0p8",
            active_command=cmd_text,
            plan_done=step_done,
            plan_total=total,
            last_report=benchmark_summary,
            note=f"running 0.8px estimator probe for {candidate_filter}",
        )
        before_ts = time.time()
        rc = _run_subprocess(cmd, PROJECT_ROOT)
        latest_report = _latest_report(before_ts - 1.0)
        if rc != 0 or not latest_report:
            _write_status(
                state="error",
                step_index=2,
                active_label="branch_e_probe_0p8",
                active_command=cmd_text,
                plan_done=step_done,
                plan_total=total,
                last_report=latest_report,
                last_exit=str(rc),
                note="branch E estimator probe failed",
            )
            NOTIFY_FLAG.write_text("LONGRUN BRANCH E FAILED\n", encoding="utf-8")
            sys.exit(rc if rc != 0 else 1)
        step_done += 1
        _write_status(
            state="running",
            step_index=2,
            active_label="branch_e_probe_0p8",
            active_command=cmd_text,
            plan_done=step_done,
            plan_total=total,
            last_report=latest_report,
            last_exit="0",
            note="estimator probe training completed",
        )

        # Step 3: process summary
        _write_status(
            state="running",
            step_index=3,
            active_label="aggregate_probe_summary",
            active_command="internal aggregate",
            plan_done=step_done,
            plan_total=total,
            last_report=latest_report,
            note="aggregating branch E probe report",
        )
        summary_result, summary_json, _summary_md = _summarize_report(latest_report, benchmark_payload)
        step_done += 1
        _write_status(
            state="running",
            step_index=3,
            active_label="aggregate_probe_summary",
            active_command="internal aggregate",
            plan_done=step_done,
            plan_total=total,
            last_report=str(summary_json),
            last_exit="0",
            note=f"probe summary completed | best_family={summary_result['best_family_candidate']}",
        )

        # Step 4: process audit
        _write_status(
            state="running",
            step_index=4,
            active_label="probe_audit",
            active_command="internal audit",
            plan_done=step_done,
            plan_total=total,
            last_report=str(summary_json),
            note="auditing 0.8px estimator probe checkpoints",
        )
        audit_result, audit_json, _audit_md = _run_process_audit(summary_result)
        step_done += 1
        _write_status(
            state="running",
            step_index=4,
            active_label="probe_audit",
            active_command="internal audit",
            plan_done=step_done,
            plan_total=total,
            last_report=str(audit_json),
            last_exit="0",
            note=f"audit completed | best={audit_result['best_candidate']}",
            selected_candidate=str(audit_result["best_candidate"]),
            selected_checkpoint=str(audit_result["selected_checkpoint"]),
        )

        # Step 5: decision memo
        _write_status(
            state="running",
            step_index=5,
            active_label="decision_memo",
            active_command="internal decision",
            plan_done=step_done,
            plan_total=total,
            last_report=str(audit_json),
            note="writing Branch E decision memo",
            selected_candidate=str(audit_result["best_candidate"]),
            selected_checkpoint=str(audit_result["selected_checkpoint"]),
        )
        decision_json, decision_md = _write_decision_memo(benchmark_payload, audit_result)
        step_done += 1
        note = (
            "Branch E automation completed | "
            + (
                "estimator probe found a promoted candidate"
                if audit_result["estimator_probe_success"]
                else "no estimator candidate cleared the 0.8px probe gate"
            )
        )
        _write_status(
            state="completed",
            step_index=5,
            active_label="decision_memo",
            active_command="internal decision",
            plan_done=step_done,
            plan_total=total,
            last_report=str(decision_json),
            last_exit="0",
            note=note,
            selected_candidate=str(audit_result["best_candidate"]),
            selected_checkpoint=str(audit_result["selected_checkpoint"]),
        )
        print(f"[BRANCH_E] COMPLETED | {note}")
        print(f"[BRANCH_E] decision_md={decision_md}")
    finally:
        if RUN_FLAG.exists():
            RUN_FLAG.unlink()


if __name__ == "__main__":
    main()

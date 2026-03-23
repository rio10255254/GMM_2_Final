"""
GeoEdgeAlignSR_v1_LongRunBranchEPhase2.py

Follow-up automation after the current Branch E rerun:
1. wait for the active Branch E rerun to complete
2. pick control + top estimator-side challengers from the benchmark
3. run an extended 0.8px estimator probe
4. run 0.8px process audits for all follow-up candidates
5. run 8.0px guard audits for control and the 0.8px winner
6. write a decision memo
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import time
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
REPORT_ROOT = PROJECT_ROOT / "Traing_Progress" / "auto_tune_reports"
SOURCE_BRANCH_ROOT = PROJECT_ROOT / "Traing_Progress" / "organized_20260314" / "branch_e"
ORG_ROOT = PROJECT_ROOT / "Traing_Progress" / "organized_20260315" / "branch_e_followup"
LOG_ROOT = ORG_ROOT / "pending" / "logs"
SELECTED_DIR = ORG_ROOT / "selected"
REPORT_DIR = SELECTED_DIR / "reports"
ARCHIVE_DIR = ORG_ROOT / "archive"
STATUS_MD = PROJECT_ROOT / "000_LONGRUN_BRANCH_E_PHASE2_STATUS.md"
STATUS_JSON = PROJECT_ROOT / "000_LONGRUN_BRANCH_E_PHASE2_STATUS.json"
RUN_FLAG = PROJECT_ROOT / "000_LONGRUN_BRANCH_E_PHASE2_RUNNING.txt"
PROFILE_NAME = "branchE_estimator_probe"
RUN_SEED = 1261206
CONTROL_CANDIDATE = "be_ctrl_edge"
PHASE2_SWEEP_EPOCHS = 10
WAIT_TIMEOUT_SECONDS = 4 * 60 * 60
POLL_SECONDS = 30
SUMMARY_PREFIX = "BRANCH_E_PHASE2"


def _safe_float(v, default=float("nan")):
    try:
        if v is None:
            return default
        return float(v)
    except Exception:
        return default


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _latest_matching(root: Path, pattern: str, after_ts: float = 0.0) -> Path | None:
    best = None
    best_mtime = after_ts
    for path in root.glob(pattern):
        try:
            mtime = path.stat().st_mtime
        except OSError:
            continue
        if mtime >= best_mtime:
            best = path
            best_mtime = mtime
    return best


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
    selected_candidate: str = "",
    selected_checkpoint: str = "",
    note: str = "",
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
        "selected_candidate": selected_candidate,
        "selected_checkpoint": selected_checkpoint,
        "note": note,
        "updated_at": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime()),
    }
    STATUS_JSON.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    STATUS_MD.write_text(
        "\n".join(
            [
                f"state: {payload['state']}",
                f"step_index: {payload['step_index']}",
                f"active_label: {payload['active_label']}",
                f"active_command: {payload['active_command']}",
                f"plan_done: {payload['plan_done']}",
                f"plan_total: {payload['plan_total']}",
                f"last_report: {payload['last_report']}",
                f"last_exit: {payload['last_exit']}",
                f"selected_candidate: {payload['selected_candidate']}",
                f"selected_checkpoint: {payload['selected_checkpoint']}",
                f"note: {payload['note']}",
                f"updated_at: {payload['updated_at']}",
            ]
        ),
        encoding="utf-8",
    )


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


def _wait_for_branch_e_completion() -> tuple[Path, dict]:
    status_json = PROJECT_ROOT / "000_LONGRUN_BRANCH_E_STATUS.json"
    deadline = time.time() + WAIT_TIMEOUT_SECONDS
    while time.time() < deadline:
        if status_json.exists():
            payload = _load_json(status_json)
            state = str(payload.get("state", "")).lower()
            if state == "completed":
                return status_json, payload
            if state in {"failed", "aborted"}:
                raise RuntimeError(f"Branch E ended with state={state}")
        time.sleep(POLL_SECONDS)
    raise TimeoutError("Timed out waiting for Branch E completion")


def _select_followup_candidates(benchmark_payload: dict) -> list[str]:
    decision = benchmark_payload["decision"]
    ranking = list(decision["estimator_ranking_0p8_clean_conv"])
    control = str(decision.get("control_probe_candidate", CONTROL_CANDIDATE))
    best_non_control = str(decision.get("best_non_control_probe_candidate", ""))
    chosen = [control]
    if best_non_control and best_non_control not in chosen:
        chosen.append(best_non_control)
    challengers = [
        row for row in ranking
        if bool(row.get("trainable", False))
        and str(row.get("probe_candidate", "")) not in chosen
        and str(row.get("probe_candidate", "")) != ""
    ]
    challengers.sort(
        key=lambda row: (
            _safe_float(row.get("avg_clean_conv_step_err_rel"), 1e9),
            -_safe_float(row.get("avg_clean_conv_sign_acc"), -1e9),
            _safe_float(row.get("avg_clean_conv_abs_center_err_px"), 1e9),
        )
    )
    for row in challengers:
        candidate = str(row.get("probe_candidate", ""))
        if candidate and candidate not in chosen:
            chosen.append(candidate)
        if len(chosen) >= 3:
            break
    return chosen[:3]


def _candidate_report_score(summary: dict, benchmark_abs: float) -> float:
    center = _safe_float(summary.get("best_ann_seq_center_err_px"), 10.0)
    step = _safe_float(summary.get("best_ann_seq_step_err_rel"), 10.0)
    ann_sign = _safe_float(summary.get("best_ann_seq_sign_acc"), 0.0)
    seq_sign = _safe_float(summary.get("best_seq_val_sign_acc"), 0.0)
    tradeoff = _safe_float(summary.get("best_tradeoff_score"), float("-inf"))
    baseline_pen = 4.0 if bool(summary.get("best_epoch_is_baseline", False)) else 0.0
    benchmark_pen = 0.15 * benchmark_abs if benchmark_abs == benchmark_abs else 0.0
    return float(
        tradeoff
        + 8.0 * ann_sign
        + 5.0 * seq_sign
        - 110.0 * center
        - 75.0 * step
        - baseline_pen
        - benchmark_pen
    )


def _summarize_followup_report(report_path: Path, benchmark_payload: dict) -> tuple[dict, Path, Path]:
    payload = _load_json(report_path)
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
                "best_center_err": _safe_float(summary.get("best_ann_seq_center_err_px"), float("nan")),
                "best_step_err": _safe_float(summary.get("best_ann_seq_step_err_rel"), float("nan")),
                "best_ann_sign": _safe_float(summary.get("best_ann_seq_sign_acc"), float("nan")),
                "best_seq_sign": _safe_float(summary.get("best_seq_val_sign_acc"), float("nan")),
                "best_minus_epoch0_center_err": _safe_float(summary.get("best_minus_epoch0_center_err"), float("nan")),
                "best_minus_epoch0_step_err": _safe_float(summary.get("best_minus_epoch0_step_err"), float("nan")),
                "score_shift_first": _safe_float(cand.get("score_shift_first"), float("-inf")),
                "progress_dir": str(cand.get("progress_dir", "")),
                "best_checkpoint_path": str(cand.get("best_checkpoint_path", "")),
                "benchmark_avg_abs": _safe_float(bench.get("avg_clean_conv_abs_center_err_px"), float("nan")),
                "benchmark_avg_step": _safe_float(bench.get("avg_clean_conv_step_err_rel"), float("nan")),
                "followup_score": _candidate_report_score(
                    summary, _safe_float(bench.get("avg_clean_conv_abs_center_err_px"), float("nan"))
                ),
            }
        )
    if not rows:
        raise RuntimeError("Branch E phase2 report contained no candidates.")
    rows.sort(key=lambda x: x["followup_score"], reverse=True)
    result = {
        "report_path": str(report_path),
        "rows": rows,
        "selection_policy": "0.8px extended probe rank: center primary, step secondary, sign tertiary, benchmark abs-center used as weak prior",
        "best_family_candidate": rows[0]["candidate"],
    }
    ts = time.strftime("%Y%m%d_%H%M%S", time.localtime())
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    json_path = REPORT_DIR / f"{SUMMARY_PREFIX}_EXTENDED_SUMMARY_{ts}.json"
    md_path = REPORT_DIR / f"{SUMMARY_PREFIX}_EXTENDED_SUMMARY_{ts}.md"
    json_path.write_text(json.dumps(result, indent=2), encoding="utf-8")
    lines = [
        f"# {SUMMARY_PREFIX} Extended Probe Summary",
        "",
        f"- best_family_candidate: {rows[0]['candidate']}",
        f"- selection_policy: {result['selection_policy']}",
        "",
        "| candidate | method | base-best | c0 | cbest | dcenter | sbest | ann | seq | bench_abs | score |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in rows:
        lines.append(
            f"| {row['candidate']} | {row['geom_method']} | {int(row['best_epoch_is_baseline'])} | "
            f"{row['epoch0_center_err']:.4f} | {row['best_center_err']:.4f} | {row['best_minus_epoch0_center_err']:.4f} | "
            f"{row['best_step_err']:.4f} | {row['best_ann_sign']:.4f} | {row['best_seq_sign']:.4f} | "
            f"{row['benchmark_avg_abs']:.4f} | {row['followup_score']:.3f} |"
        )
    md_path.write_text("\n".join(lines), encoding="utf-8")
    return result, json_path, md_path


def _run_process_audits(rows: list[dict], *, expect_dy: float, label: str) -> tuple[list[dict], Path, Path]:
    ts = time.strftime("%Y%m%d_%H%M%S", time.localtime())
    results = []
    for idx, row in enumerate(rows, start=1):
        candidate = str(row["candidate"])
        json_path = REPORT_DIR / f"{SUMMARY_PREFIX}_{label}_{candidate}_{ts}.json"
        md_path = REPORT_DIR / f"{SUMMARY_PREFIX}_{label}_{candidate}_{ts}.md"
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
            "--expect-dy",
            str(expect_dy),
            "--output-json",
            str(json_path),
            "--output-md",
            str(md_path),
            "--seed",
            str(RUN_SEED),
        ]
        print(f"[BRANCH_E_PHASE2][AUDIT] {label} {idx}/{len(rows)} candidate={candidate}")
        rc = _run_subprocess(cmd, PROJECT_ROOT)
        if rc != 0:
            raise RuntimeError(f"{label} audit failed for {candidate} rc={rc}")
        payload = _load_json(json_path)
        summary = payload["summary"]
        results.append(
            {
                "candidate": candidate,
                "geom_method": str(payload.get("geom_method", "")),
                "expect_dy": float(payload.get("expect_dy", expect_dy)),
                "process_score": _safe_float(payload.get("process_score"), float("-inf")),
                "passes_target": bool(payload.get("passes_target", False)),
                "best_epoch": int(summary.get("best_epoch", -1)) if summary.get("best_epoch") is not None else -1,
                "best_epoch_is_baseline": bool(summary.get("best_epoch_is_baseline", False)),
                "epoch0_center_err": _safe_float(summary.get("epoch0_ann_seq_center_err_px"), float("nan")),
                "best_center_err": _safe_float(summary.get("best_ann_seq_center_err_px"), float("nan")),
                "best_step_err": _safe_float(summary.get("best_ann_seq_step_err_rel"), float("nan")),
                "best_ann_sign": _safe_float(summary.get("best_ann_seq_sign_acc"), float("nan")),
                "best_seq_sign": _safe_float(summary.get("best_seq_val_sign_acc"), float("nan")),
                "best_checkpoint_path": str(row["best_checkpoint_path"]),
            }
        )
    if abs(expect_dy - 8.0) < 1.0e-6:
        results.sort(key=lambda x: (x["best_step_err"], -x["best_ann_sign"], -x["best_seq_sign"]))
    else:
        results.sort(key=lambda x: (x["best_center_err"], x["best_step_err"], -x["best_ann_sign"], -x["best_seq_sign"]))
    summary_payload = {
        "expect_dy": float(expect_dy),
        "label": label,
        "rows": results,
        "selection_policy": (
            "8.0 guard rank: step_err primary, sign secondary"
            if abs(expect_dy - 8.0) < 1.0e-6
            else "0.8 process rank: center_err primary, step_err secondary, sign tertiary"
        ),
    }
    json_summary = REPORT_DIR / f"{SUMMARY_PREFIX}_{label}_SUMMARY_{ts}.json"
    md_summary = REPORT_DIR / f"{SUMMARY_PREFIX}_{label}_SUMMARY_{ts}.md"
    json_summary.write_text(json.dumps(summary_payload, indent=2), encoding="utf-8")
    lines = [
        f"# {SUMMARY_PREFIX} {label} Summary",
        "",
        f"- expect_dy: {expect_dy}",
        f"- selection_policy: {summary_payload['selection_policy']}",
        "",
        "| candidate | method | base-best | center | step | ann | seq | score | pass |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |",
    ]
    for row in results:
        lines.append(
            f"| {row['candidate']} | {row['geom_method']} | {int(row['best_epoch_is_baseline'])} | "
            f"{row['best_center_err']:.4f} | {row['best_step_err']:.4f} | {row['best_ann_sign']:.4f} | "
            f"{row['best_seq_sign']:.4f} | {row['process_score']:.3f} | {row['passes_target']} |"
        )
    md_summary.write_text("\n".join(lines), encoding="utf-8")
    return results, json_summary, md_summary


def _write_seed_manifest(selected_candidate: str, selected_checkpoint: str, confirmed: bool, memo_path: Path) -> Path:
    manifest = SELECTED_DIR / "current_branch_e_phase2_seed.json"
    payload = {
        "selected_candidate": selected_candidate,
        "selected_checkpoint": selected_checkpoint,
        "confirmed_estimator_side_win": bool(confirmed),
        "decision_memo": str(memo_path),
        "updated_at": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime()),
    }
    manifest.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return manifest


def _move_new_runs(start_ts: float, selected_candidate: str) -> None:
    root = PROJECT_ROOT / "Traing_Progress"
    selected_root = SELECTED_DIR / "runs"
    archive_runs = ARCHIVE_DIR / "runs"
    archive_audits = ARCHIVE_DIR / "audit_runs"
    selected_root.mkdir(parents=True, exist_ok=True)
    archive_runs.mkdir(parents=True, exist_ok=True)
    archive_audits.mkdir(parents=True, exist_ok=True)
    for path in root.glob("training_progress_GESR_v1_v5_ST0p8_SWP_be*"):
        try:
            mtime = path.stat().st_mtime
        except OSError:
            continue
        if mtime < start_ts:
            continue
        target_dir = selected_root if selected_candidate in path.name else archive_runs
        target = target_dir / path.name
        if not target.exists():
            shutil.move(str(path), str(target))
    for path in root.glob("training_progress_process_probe_*"):
        try:
            mtime = path.stat().st_mtime
        except OSError:
            continue
        if mtime < start_ts:
            continue
        target = archive_audits / path.name
        if not target.exists():
            shutil.move(str(path), str(target))


def _write_decision_memo(
    *,
    benchmark_payload: dict,
    followup_summary: dict,
    audit08: list[dict],
    audit8: list[dict],
) -> tuple[str, str, Path]:
    control08 = next(row for row in audit08 if row["candidate"] == CONTROL_CANDIDATE)
    winner08 = audit08[0]
    improvement = control08["best_center_err"] - winner08["best_center_err"]
    control8 = next((row for row in audit8 if row["candidate"] == CONTROL_CANDIDATE), None)
    winner8 = next((row for row in audit8 if row["candidate"] == winner08["candidate"]), None)
    guard_pass = False
    if winner8 is not None:
        guard_pass = winner8["best_step_err"] <= 0.04
        if control8 is not None:
            guard_pass = guard_pass and (winner8["best_step_err"] <= control8["best_step_err"] + 0.01)
    confirmed = (
        winner08["candidate"] != CONTROL_CANDIDATE
        and improvement >= 0.02
        and winner08["best_step_err"] < 0.40
        and guard_pass
    )
    ts = time.strftime("%Y%m%d_%H%M%S", time.localtime())
    memo_path = REPORT_DIR / f"{SUMMARY_PREFIX}_DECISION_{ts}.md"
    decision = "confirmed" if confirmed else "not_confirmed"
    lines = [
        f"# {SUMMARY_PREFIX} Decision Memo",
        "",
        f"- benchmark_control: {benchmark_payload['decision']['control_probe_candidate']}",
        f"- benchmark_best_non_control: {benchmark_payload['decision']['best_non_control_probe_candidate']}",
        f"- followup_best_family_candidate: {followup_summary['best_family_candidate']}",
        f"- best_0p8_audit_candidate: {winner08['candidate']}",
        f"- best_0p8_center_err: {winner08['best_center_err']:.6f}",
        f"- control_0p8_center_err: {control08['best_center_err']:.6f}",
        f"- center_improvement_vs_control: {improvement:.6f}",
        f"- best_0p8_step_err: {winner08['best_step_err']:.6f}",
        f"- guard_pass_8px: {guard_pass}",
        f"- decision: {decision}",
        "",
        "## Interpretation",
        "",
    ]
    if confirmed:
        lines.extend(
            [
                "Estimator-side improvement is confirmed under the follow-up probe.",
                "The winning non-control estimator improved 0.8px center_err by at least 0.02 px while keeping 8px guard within tolerance.",
            ]
        )
    else:
        lines.extend(
            [
                "Estimator-side improvement is not yet confirmed.",
                "Current evidence is insufficient to replace the control edge estimator under the stricter 0.8px + 8px guard rule.",
            ]
        )
    memo_path.write_text("\n".join(lines), encoding="utf-8")
    selected_candidate = winner08["candidate"] if confirmed else CONTROL_CANDIDATE
    selected_checkpoint = next(
        (row["best_checkpoint_path"] for row in audit08 if row["candidate"] == selected_candidate),
        "",
    )
    return selected_candidate, selected_checkpoint, memo_path


def _write_readme() -> None:
    readme = ORG_ROOT / "README.md"
    readme.parent.mkdir(parents=True, exist_ok=True)
    readme.write_text(
        "\n".join(
            [
                "# Branch E Follow-up",
                "",
                "- waits for the active Branch E rerun to finish",
                "- runs extended 0.8px estimator-side probe",
                "- runs 0.8px process audit for all follow-up candidates",
                "- runs 8px guard audit for control and the 0.8px winner",
                "- writes a decision memo without triggering external recon",
            ]
        ),
        encoding="utf-8",
    )


def main() -> int:
    flow_start_ts = time.time()
    ORG_ROOT.mkdir(parents=True, exist_ok=True)
    LOG_ROOT.mkdir(parents=True, exist_ok=True)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
    RUN_FLAG.write_text("running\n", encoding="utf-8")
    _write_readme()
    try:
        _write_status(
            state="running",
            step_index=1,
            active_label="wait_branch_e_completion",
            active_command="wait for 000_LONGRUN_BRANCH_E_STATUS.json -> completed",
            plan_done=0,
            plan_total=5,
            note="queued follow-up after current Branch E rerun",
        )
        _, branch_payload = _wait_for_branch_e_completion()

        benchmark_json = _latest_matching(SOURCE_BRANCH_ROOT / "benchmark", "BRANCH_E_ESTIMATOR_BENCHMARK_SUMMARY_*.json")
        if benchmark_json is None:
            raise FileNotFoundError("No Branch E benchmark summary found after completion.")
        benchmark_payload = _load_json(benchmark_json)
        candidates = _select_followup_candidates(benchmark_payload)

        probe_cmd = [
            sys.executable,
            "-u",
            str(PROJECT_ROOT / "Model" / "GeoEdgeAlignSR_v1_AutoTuneTrain.py"),
            "--profile",
            PROFILE_NAME,
            "--expect-dy",
            "0.8",
            "--candidate-filter",
            ",".join(candidates),
            "--sweep-epochs",
            str(PHASE2_SWEEP_EPOCHS),
            "--final-epochs",
            "6",
            "--seed",
            str(RUN_SEED),
            "--skip-final",
            "--deterministic",
        ]
        _write_status(
            state="running",
            step_index=2,
            active_label="branch_e_followup_probe_0p8",
            active_command=" ".join(probe_cmd),
            plan_done=1,
            plan_total=5,
            last_report=str(benchmark_json),
            note=f"extended 0.8px follow-up probe for {','.join(candidates)}",
        )
        report_ts = time.time()
        rc = _run_subprocess(probe_cmd, PROJECT_ROOT)
        if rc != 0:
            raise RuntimeError(f"Follow-up probe failed rc={rc}")
        report_path = _latest_matching(REPORT_ROOT, "auto_tune_report_*.json", report_ts)
        if report_path is None:
            raise FileNotFoundError("Failed to locate follow-up auto_tune_report")
        followup_summary, followup_json, _ = _summarize_followup_report(report_path, benchmark_payload)

        _write_status(
            state="running",
            step_index=3,
            active_label="branch_e_followup_audit_0p8",
            active_command="GeoEdgeAlignSR_v1_ProcessProbeAudit.py --expect-dy 0.8",
            plan_done=2,
            plan_total=5,
            last_report=str(followup_json),
            note="running 0.8px process audits for all follow-up candidates",
        )
        audit08_rows, audit08_json, _ = _run_process_audits(followup_summary["rows"], expect_dy=0.8, label="AUDIT_0P8")

        top_candidate = audit08_rows[0]["candidate"]
        audit8_input = [next(row for row in followup_summary["rows"] if row["candidate"] == CONTROL_CANDIDATE)]
        if top_candidate != CONTROL_CANDIDATE:
            audit8_input.append(next(row for row in followup_summary["rows"] if row["candidate"] == top_candidate))

        _write_status(
            state="running",
            step_index=4,
            active_label="branch_e_followup_guard_8px",
            active_command="GeoEdgeAlignSR_v1_ProcessProbeAudit.py --expect-dy 8.0",
            plan_done=3,
            plan_total=5,
            last_report=str(audit08_json),
            note=f"running 8px guard audit for {','.join(row['candidate'] for row in audit8_input)}",
        )
        audit8_rows, audit8_json, _ = _run_process_audits(audit8_input, expect_dy=8.0, label="AUDIT_8P0")

        selected_candidate, selected_checkpoint, memo_path = _write_decision_memo(
            benchmark_payload=benchmark_payload,
            followup_summary=followup_summary,
            audit08=audit08_rows,
            audit8=audit8_rows,
        )
        _write_seed_manifest(
            selected_candidate=selected_candidate,
            selected_checkpoint=selected_checkpoint,
            confirmed=(selected_candidate != CONTROL_CANDIDATE),
            memo_path=memo_path,
        )
        _move_new_runs(flow_start_ts, selected_candidate)

        _write_status(
            state="completed",
            step_index=5,
            active_label="completed",
            active_command="",
            plan_done=5,
            plan_total=5,
            last_report=str(memo_path),
            last_exit="0",
            selected_candidate=selected_candidate,
            selected_checkpoint=selected_checkpoint,
            note="branch_e follow-up completed",
        )
        return 0
    except Exception as exc:
        _write_status(
            state="failed",
            step_index=0,
            active_label="failed",
            active_command="",
            plan_done=0,
            plan_total=5,
            last_exit=str(exc),
            note="branch_e follow-up failed",
        )
        print(f"[BRANCH_E_PHASE2] ERROR: {exc}")
        return 1
    finally:
        if RUN_FLAG.exists():
            RUN_FLAG.unlink()


if __name__ == "__main__":
    raise SystemExit(main())

"""
GeoEdgeAlignSR_v1_LongRunRound32.py

Round32 domain adaptation + long training + capacity probe (from Round30 B1-only seed):
  A: Real-domain EQ fine-tuning (REAL_EQ_ENABLE)
  B: Long training from R25 seed (40 epochs)
  C: Wider model base=64 from scratch (30 epochs)

1. run 0.8px domain/capacity sweep + final training
2. aggregate family summary
3. run 0.8px audits with pairmix_algblend
4. run 8px guard audits with frozen macro estimator policy
5. write decision memo and seed manifest
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import time
from pathlib import Path

from r32_status import load_round32_status, process_alive, write_round32_status

SANDBOX_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = SANDBOX_ROOT
SHARED_ROOT = Path(__file__).resolve().parents[3]
SHARED_MODEL_ROOT = SHARED_ROOT / "Model"
if str(SHARED_MODEL_ROOT) not in sys.path:
    sys.path.insert(0, str(SHARED_MODEL_ROOT))

from GeoEdgeAlignSR_v1_PolicyAccess import load_probe_policy_pack

REPORT_ROOT = SANDBOX_ROOT / "reports"
LOG_ROOT = SANDBOX_ROOT / "runtime" / "logs"
SELECTED_DIR = SANDBOX_ROOT / "runtime"
REPORT_DIR = SANDBOX_ROOT / "reports"
ARCHIVE_DIR = SANDBOX_ROOT / "archive"
STATUS_MD = SANDBOX_ROOT / "runtime" / "R32_STATUS.md"
STATUS_JSON = SANDBOX_ROOT / "runtime" / "R32_STATUS.json"
RUN_FLAG = SANDBOX_ROOT / "runtime" / "R32_RUNNING.txt"
PROFILE_NAME = "round32_domain_capacity_probe"
SUMMARY_PREFIX = "ROUND32_DOMAIN_CAPACITY"
MERGED_PROFILE_JSON = REPORT_DIR / f"{SUMMARY_PREFIX}_MERGED_PROFILE_REPORT.json"
RUN_SEED = 1261830
CONTROL_CANDIDATE = "r30_b1_dironly"
CONTROL_CHECKPOINT = Path(str(SHARED_ROOT / 'Traing_Progress/organized_20260316/round30/archive/runs/training_progress_GESR_v1_v5_ST0p8_SWP_r30b1dir_20260317_152913/weights/best_tradeoff.pth.tar'))
POLICY_PATH = SHARED_ROOT / "ESTIMATOR_POLICY.json"
ROUND32_REAL_EQ_DIR = SHARED_ROOT / "Training_Data" / "generated_convolved" / "Real_Image"

PLAN = [
    {
        "label": "round32_domain_capacity_0p8",
        "args": [
            "Experiments\\R32Sandbox\\Model\\autotune_r32.py",
            "--profile", PROFILE_NAME,
            "--expect-dy", "0.8",
            "--sweep-epochs", "40",
            "--final-epochs", "20",
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
    active_pid: int | None = None,
    active_log: str = "",
    active_err_log: str = "",
) -> None:
    write_round32_status(
        state=state,
        step_index=step_index,
        active_label=active_label,
        active_command=active_command,
        plan_done=plan_done,
        plan_total=plan_total,
        last_report=last_report,
        last_exit=last_exit,
        note=note,
        selected_candidate=selected_candidate,
        selected_checkpoint=selected_checkpoint,
        active_pid=active_pid,
        active_log=active_log,
        active_err_log=active_err_log,
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


def _load_status() -> dict:
    return load_round32_status()


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


def _latest_profile_report(profile_name: str) -> str:
    best = None
    best_mtime = -1.0
    if not REPORT_ROOT.exists():
        return ""
    for path in REPORT_ROOT.glob("auto_tune_report_*.json"):
        try:
            payload = _load_json(path)
            mtime = path.stat().st_mtime
        except Exception:
            continue
        if str(payload.get("profile", "")) != str(profile_name):
            continue
        if mtime > best_mtime:
            best = path
            best_mtime = mtime
    return str(best) if best is not None else ""


def _profile_reports(profile_name: str) -> list[Path]:
    items: list[tuple[float, Path]] = []
    if not REPORT_ROOT.exists():
        return []
    for path in REPORT_ROOT.glob("auto_tune_report_*.json"):
        try:
            payload = _load_json(path)
            mtime = path.stat().st_mtime
        except Exception:
            continue
        if str(payload.get("profile", "")) != str(profile_name):
            continue
        items.append((mtime, path))
    items.sort(key=lambda x: x[0], reverse=True)
    return [path for _, path in items]


def _merged_profile_report(profile_name: str) -> str:
    reports = _profile_reports(profile_name)
    if not reports:
        return ""

    merged_payload = None
    candidate_map: dict[str, dict] = {}
    for path in reports:
        payload = _load_json(path)
        if merged_payload is None:
            merged_payload = dict(payload)
            merged_payload["candidates"] = []
            merged_payload["source_reports"] = []
        merged_payload["source_reports"].append(str(path))
        for cand in payload.get("candidates", []):
            name = str(cand.get("candidate") or cand.get("name") or "")
            if not name or name in candidate_map:
                continue
            candidate_map[name] = cand

    assert merged_payload is not None
    merged_payload["candidates"] = list(candidate_map.values())
    MERGED_PROFILE_JSON.parent.mkdir(parents=True, exist_ok=True)
    MERGED_PROFILE_JSON.write_text(json.dumps(merged_payload, indent=2), encoding="utf-8")
    return str(MERGED_PROFILE_JSON)


def _latest_selected_json(pattern: str) -> str:
    best = None
    best_mtime = -1.0
    if not REPORT_DIR.exists():
        return ""
    for path in REPORT_DIR.glob(pattern):
        try:
            mtime = path.stat().st_mtime
        except OSError:
            continue
        if mtime > best_mtime:
            best = path
            best_mtime = mtime
    return str(best) if best is not None else ""


def _mtime(path_str: str) -> float:
    if not path_str:
        return -1.0
    try:
        return Path(path_str).stat().st_mtime
    except OSError:
        return -1.0


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


def _preflight_real_eq_dir() -> None:
    if not ROUND32_REAL_EQ_DIR.exists():
        raise FileNotFoundError(f"Round32 real-domain EQ dir missing: {ROUND32_REAL_EQ_DIR}")
    image_count = len(list(ROUND32_REAL_EQ_DIR.glob("*.bmp")))
    if image_count <= 0:
        raise RuntimeError(f"Round32 real-domain EQ dir has no BMP images: {ROUND32_REAL_EQ_DIR}")
    print(f"[ROUND32][PREFLIGHT] REAL_EQ_DIR ready: {ROUND32_REAL_EQ_DIR} ({image_count} bmp)")


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
        # Skip candidates that failed during sweep (no summary or no checkpoint)
        if not summary or not cand.get("best_checkpoint_path", ""):
            print(f"[ROUND32][SKIP] candidate={cand.get('candidate','?')} has no summary/checkpoint, skipping audit")
            continue
        rows.append(
            {
                "candidate": str(cand.get("candidate", "")),
                "geom_method": str(overrides.get("SEQ_GEOM_METHOD", "")),
                "step_mag_w": _safe_float(overrides.get("SEQ_STEP_MAG_WEIGHT"), 0.0),
                "abs_center_w": _safe_float(overrides.get("SEQ_SINGLE_ABS_CENTER_WEIGHT"), 0.0),
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
                "model_base": int(overrides.get("MODEL_BASE", 48)),
            }
        )
    if not rows:
        raise RuntimeError("Round32 report contained no candidates.")
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
        "| candidate | method | sm_w | ac_w | center_w | drift_w | base-best | c0 | s0 | cbest | sbest | ann | seq | family |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in rows:
        lines.append(
            f"| {row['candidate']} | {row['geom_method']} | {row['step_mag_w']:.3f} | {row['abs_center_w']:.3f} | "
            f"{row['center_w']:.2f} | {row['drift_w']:.2f} | "
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
            str(SANDBOX_ROOT / "Model" / "process_probe_audit_r32.py"),
            "--candidate", candidate,
            "--checkpoint", str(row["best_checkpoint_path"]),
            "--geom-method", geom_method,
            "--expect-dy", str(float(expect_dy)),
            "--output-json", str(json_path),
            "--output-md", str(md_path),
            "--seed", str(RUN_SEED),
            "--model-base", str(int(row.get("model_base", 48))),
        ]
        print(f"[ROUND32][AUDIT] {label} {idx}/{len(rows)} candidate={candidate} geom={geom_method}")
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
    (SELECTED_DIR / "current_round32_domain_capacity_seed.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return selected_candidate, selected_checkpoint, memo_path


def _infer_flow_start_ts(report_path: str = "", summary_result: dict | None = None) -> float:
    mtimes: list[float] = []

    def _collect(path_str: str) -> None:
        if not path_str:
            return
        try:
            mtimes.append(Path(path_str).stat().st_mtime)
        except OSError:
            return

    _collect(report_path)
    if report_path:
        try:
            payload = _load_json(Path(report_path))
        except Exception:
            payload = {}
        for cand in payload.get("candidates", []):
            _collect(str(cand.get("progress_dir", "")))
            _collect(str(cand.get("best_checkpoint_path", "")))
    if summary_result is not None:
        for row in summary_result.get("rows", []):
            _collect(str(row.get("progress_dir", "")))
            _collect(str(row.get("best_checkpoint_path", "")))
    return (min(mtimes) - 1.0) if mtimes else time.time()


def _candidate_path_token(candidate: str) -> str:
    return str(candidate).replace("_", "")


def _move_new_runs(start_ts: float, selected_candidate: str) -> None:
    # Sandbox runs already write into sandbox-local artifact directories.
    return


def _resolve_selected_checkpoint(selected_candidate: str, selected_checkpoint: str) -> str:
    if selected_candidate == CONTROL_CANDIDATE:
        return selected_checkpoint
    selected_token = _candidate_path_token(selected_candidate)
    for root in (SANDBOX_ROOT / "artifacts",):
        if not root.exists():
            continue
        for path in root.glob(f"*{selected_token}*"):
            checkpoint = path / "weights" / "best_tradeoff.pth.tar"
            if checkpoint.exists():
                return str(checkpoint)
    return selected_checkpoint


def _refresh_selected_artifacts(memo_path: Path, selected_checkpoint: str) -> None:
    memo_json = memo_path.with_suffix(".json")
    if memo_json.exists():
        payload = _load_json(memo_json)
        payload["selected_checkpoint"] = selected_checkpoint
        selected_candidate = str(payload.get("selected_candidate", ""))
        for row in payload.get("rows", []):
            if str(row.get("candidate", "")) == selected_candidate:
                row["checkpoint_path"] = selected_checkpoint
        memo_json.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    if memo_path.exists():
        lines = []
        for line in memo_path.read_text(encoding="utf-8").splitlines():
            if line.startswith("- selected_checkpoint: "):
                lines.append(f"- selected_checkpoint: {selected_checkpoint}")
            else:
                lines.append(line)
        memo_path.write_text("\n".join(lines), encoding="utf-8")

    seed_path = SELECTED_DIR / "current_round32_domain_capacity_seed.json"
    if seed_path.exists():
        seed_payload = _load_json(seed_path)
        seed_payload["weights_path"] = selected_checkpoint
        seed_path.write_text(json.dumps(seed_payload, indent=2), encoding="utf-8")


def main() -> None:
    LOG_ROOT.mkdir(parents=True, exist_ok=True)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    SELECTED_DIR.mkdir(parents=True, exist_ok=True)
    if not CONTROL_CHECKPOINT.exists():
        raise FileNotFoundError(f"Round32 control checkpoint missing: {CONTROL_CHECKPOINT}")
    total = len(PLAN) + 3
    status_payload = _load_status()
    active_pid = int(status_payload.get("active_pid", 0) or 0)
    if str(status_payload.get("state", "")).strip().lower() == "running" and active_pid and not process_alive(active_pid):
        _write_status(
            state="error",
            step_index=int(status_payload.get("step_index", 0) or 0),
            active_label=str(status_payload.get("active_label", "") or ""),
            active_command=str(status_payload.get("active_command", "") or ""),
            plan_done=int(status_payload.get("plan_done", 0) or 0),
            plan_total=int(status_payload.get("plan_total", total) or total),
            last_report=str(str(SHARED_ROOT / status_payload.get("last_report", "")) or ""),
            last_exit="1",
            note="recorded active_pid is not alive; marking stale running state as error",
            selected_candidate=str(status_payload.get("selected_candidate", "") or ""),
            selected_checkpoint=str(str(SHARED_ROOT / status_payload.get("selected_checkpoint", "")) or ""),
        )
        status_payload = _load_status()
    latest_report = str(str(SHARED_ROOT / status_payload.get("last_report", "")) or "")
    latest_merged_report = _merged_profile_report(PROFILE_NAME)
    if latest_merged_report and Path(latest_merged_report).exists():
        latest_report = latest_merged_report
    elif not latest_report or not Path(latest_report).exists():
        latest_report = _latest_profile_report(PROFILE_NAME)

    existing_summary_json = _latest_selected_json(f"{SUMMARY_PREFIX}_SUMMARY_*.json")
    existing_audit08_json = _latest_selected_json(f"{SUMMARY_PREFIX}_AUDIT_0P8_SUMMARY_*.json")
    existing_audit8_json = _latest_selected_json(f"{SUMMARY_PREFIX}_AUDIT_8P0_SUMMARY_*.json")
    existing_decision_json = _latest_selected_json(f"{SUMMARY_PREFIX}_DECISION_*.json")

    latest_report_mtime = _mtime(latest_report)
    if latest_report_mtime > _mtime(existing_summary_json):
        existing_summary_json = ""
        existing_audit08_json = ""
        existing_audit8_json = ""
        existing_decision_json = ""
    elif _mtime(existing_summary_json) > _mtime(existing_audit08_json):
        existing_audit08_json = ""
        existing_audit8_json = ""
        existing_decision_json = ""
    elif _mtime(existing_audit08_json) > _mtime(existing_audit8_json):
        existing_audit8_json = ""
        existing_decision_json = ""
    elif _mtime(existing_audit8_json) > _mtime(existing_decision_json):
        existing_decision_json = ""

    if existing_decision_json and Path(existing_decision_json).exists():
        decision_payload = _load_json(Path(existing_decision_json))
        selected_candidate = str(decision_payload.get("selected_candidate", ""))
        selected_checkpoint = _resolve_selected_checkpoint(
            selected_candidate,
            str(decision_payload.get("selected_checkpoint", "")),
        )
        _refresh_selected_artifacts(Path(existing_decision_json).with_suffix(".md"), selected_checkpoint)
        confirmed = bool(decision_payload.get("confirmed", False))
        note = (
            "Round32 domain capacity probe passed calibrated pairmix gate"
            if confirmed and selected_candidate != CONTROL_CANDIDATE
            else "Round32 domain capacity probe did not improve over Round30 B1 control"
        )
        _write_status(
            state="completed",
            step_index=total,
            active_label="round32_guard_8px",
            active_command="internal audit",
            plan_done=total,
            plan_total=total,
            last_report=existing_decision_json,
            last_exit="0",
            note=note,
            selected_candidate=selected_candidate,
            selected_checkpoint=selected_checkpoint,
        )
        print(f"[ROUND32] {note}")
        return

    resume_mode = any(
        [
            latest_report and Path(latest_report).exists(),
            existing_summary_json and Path(existing_summary_json).exists(),
            existing_audit08_json and Path(existing_audit08_json).exists(),
            existing_audit8_json and Path(existing_audit8_json).exists(),
        ]
    ) and not RUN_FLAG.exists()

    RUN_FLAG.write_text("RUNNING\n", encoding="utf-8")
    _write_status(
        state="running",
        step_index=0,
        active_label="bootstrap",
        active_command="",
        plan_done=0,
        plan_total=total,
        note="resuming Round32 from existing artifacts" if resume_mode else "starting Round32 domain capacity probe",
    )

    flow_start_ts = time.time()
    current_step_index = 0
    current_active_label = "bootstrap"
    current_active_command = ""
    current_last_report = latest_report
    step_done = 0
    try:
        report_paths: list[str] = []
        summary_result: dict | None = None
        summary_json: Path | None = None

        if latest_report and Path(latest_report).exists():
            report_paths.append(latest_report)
            flow_start_ts = _infer_flow_start_ts(latest_report)
            step_done = len(PLAN)
            current_last_report = latest_report

        if existing_summary_json and Path(existing_summary_json).exists():
            summary_json = Path(existing_summary_json)
            summary_result = _load_json(summary_json)
            flow_start_ts = _infer_flow_start_ts(latest_report, summary_result)
            step_done = len(PLAN) + 1
            current_last_report = str(summary_json)
        else:
            for idx, step in enumerate(PLAN, start=1):
                if step_done >= idx:
                    continue
                _preflight_real_eq_dir()
                cmd = [sys.executable, "-u", *step["args"]]
                cmd_text = " ".join(cmd)
                current_step_index = idx
                current_active_label = str(step["label"])
                current_active_command = cmd_text
                _write_status(
                    state="running",
                    step_index=idx,
                    active_label=str(step["label"]),
                    active_command=cmd_text,
                    plan_done=step_done,
                    plan_total=total,
                    note="running Round32 domain capacity probe",
                )
                before_ts = time.time()
                rc = _run_subprocess(cmd, PROJECT_ROOT)
                latest_report = _latest_report(before_ts - 1.0)
                current_last_report = latest_report
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
                        note="Round32 domain capacity probe failed",
                    )
                    sys.exit(rc)
                if latest_report:
                    report_paths = [latest_report]
                    flow_start_ts = _infer_flow_start_ts(latest_report)
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
                    note="Round32 domain capacity probe completed",
                )

            if not report_paths:
                raise RuntimeError("Round32 could not locate its auto-tune report for aggregation.")

            idx = len(PLAN) + 1
            current_step_index = idx
            current_active_label = "aggregate_round32_summary"
            current_active_command = "internal aggregate"
            _write_status(
                state="running",
                step_index=idx,
                active_label="aggregate_round32_summary",
                active_command="internal aggregate",
                plan_done=step_done,
                plan_total=total,
                last_report=report_paths[-1],
                note="aggregating Round32 training report",
            )
            summary_result, summary_json, _ = _summarize_report(report_paths[-1])
            flow_start_ts = _infer_flow_start_ts(report_paths[-1], summary_result)
            step_done += 1
            current_last_report = str(summary_json)

        assert summary_result is not None
        assert summary_json is not None
        policy_pack = _load_policy()

        if existing_audit08_json and Path(existing_audit08_json).exists():
            audit08_json = Path(existing_audit08_json)
            audit08_rows = _load_json(audit08_json).get("rows", [])
            step_done = max(step_done, len(PLAN) + 2)
        else:
            idx = len(PLAN) + 2
            current_step_index = idx
            current_active_label = "round32_audit_0p8"
            current_active_command = "internal audit"
            _write_status(
                state="running",
                step_index=idx,
                active_label="round32_audit_0p8",
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
            current_last_report = str(audit08_json)

        if existing_audit8_json and Path(existing_audit8_json).exists():
            audit8_json = Path(existing_audit8_json)
            audit8_rows = _load_json(audit8_json).get("rows", [])
        else:
            idx = len(PLAN) + 3
            current_step_index = idx
            current_active_label = "round32_guard_8px"
            current_active_command = "internal audit"
            _write_status(
                state="running",
                step_index=idx,
                active_label="round32_guard_8px",
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
            current_last_report = str(audit8_json)

        idx = len(PLAN) + 3
        current_step_index = idx
        current_active_label = "round32_guard_8px"
        current_active_command = "internal audit"
        selected_candidate, selected_checkpoint, memo_path = _write_decision(
            summary_result,
            audit08_rows,
            audit8_rows,
            policy_pack,
        )
        _move_new_runs(flow_start_ts, selected_candidate)
        selected_checkpoint = _resolve_selected_checkpoint(selected_candidate, selected_checkpoint)
        _refresh_selected_artifacts(memo_path, selected_checkpoint)

        confirmed = selected_candidate != CONTROL_CANDIDATE
        note = (
            "Round32 domain capacity probe passed calibrated pairmix gate"
            if confirmed
            else "Round32 domain capacity probe did not improve over Round30 B1 control"
        )
        _write_status(
            state="completed",
            step_index=idx,
            active_label="round32_guard_8px",
            active_command="internal audit",
            plan_done=total,
            plan_total=total,
            last_report=str(memo_path),
            last_exit="0",
            note=note,
            selected_candidate=selected_candidate,
            selected_checkpoint=selected_checkpoint,
        )
        print(f"[ROUND32] COMPLETED | {note}")
    except Exception as exc:
        _write_status(
            state="error",
            step_index=current_step_index,
            active_label=current_active_label,
            active_command=current_active_command,
            plan_done=step_done,
            plan_total=total,
            last_report=str(current_last_report or ""),
            last_exit="1",
            note=f"Round32 failed: {exc}",
        )
        raise
    finally:
        if RUN_FLAG.exists():
            RUN_FLAG.unlink()


if __name__ == "__main__":
    main()

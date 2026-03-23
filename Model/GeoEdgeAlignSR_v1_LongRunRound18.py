"""
GeoEdgeAlignSR_v1_LongRunRound18.py

Round 18 long-run orchestrator.
Inherits the center-lock design from round17_stepfix_centerlock and introduces:
  - push center_err below 0.82 hard-penalty threshold while maintaining step_err<0.40
  - center_w raised to 0.83-0.86 across all candidates
  - step_mag_w maintained at 0.30-0.38 to prevent step_err regression

round17 result: r17_ec_stepmag achieved center_err=0.8508 (historical low), step_err=0.3157.

round18 goal: push center_err below 0.82 while keeping step_err<0.40.

Stages rebuilt: 23, 24, 27, 28 (same as centerlock longrun).
Sweep structure: 3-scale (0.08px / 0.8px / 8px), skip-final mode.
Checkpoint audit mode: centerlock0p8.
"""
import json
import os
import subprocess
import sys
import time
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
REPORT_ROOT = PROJECT_ROOT / "Traing_Progress" / "auto_tune_reports"
ORG_ROOT = PROJECT_ROOT / "Traing_Progress" / "organized_20260313" / "round18"
LOG_ROOT = ORG_ROOT / "pending" / "logs"
STATUS_MD = PROJECT_ROOT / "000_LONGRUN_ROUND18_STATUS.md"
STATUS_JSON = PROJECT_ROOT / "000_LONGRUN_ROUND18_STATUS.json"
RUN_FLAG = PROJECT_ROOT / "000_LONGRUN_ROUND18_RUNNING.txt"
NOTIFY_FLAG = PROJECT_ROOT / "000_NOTIFY_CODEX_NOW.txt"
SUMMARY_DIR = ORG_ROOT / "selected" / "reports"
SELECTED_DIR = ORG_ROOT / "selected"
RECON_ROOT = ORG_ROOT / "external_validation" / "centerpush_r18_longrun_candidate"
PROFILE_NAME = "round18_centerpush"
SUMMARY_PREFIX = "ROUND18_CENTERPUSH"
AUDIT_TOP_K = 4
RUN_SEED = 1261201
RESUME_FROM_CHECKPOINT: "str | None" = r"D:\GMM_2_Final\Traing_Progress\training_progress_GESR_v1_v5_ST8_SWP_r17es_20260313_130154\weights\best_tradeoff.pth.tar"


PLAN = [
    {
        "label": "rebuild_centerlock_stages",
        "collect_report": False,
        "args": [
            "Tools\\RebuildMicrostepStages.py",
            "--stage-ids", "23", "24", "27", "28",
        ],
    },
    {
        "label": "round18_centerpush_0p08",
        "expect_dy": 0.08,
        "args": [
            "Model\\GeoEdgeAlignSR_v1_AutoTuneTrain.py",
            "--profile", PROFILE_NAME,
            "--expect-dy", "0.08",
            "--sweep-epochs", "4",
            "--final-epochs", "6",
            "--seed", str(RUN_SEED),
            "--skip-final",
            "--deterministic",
        ],
    },
    {
        "label": "round18_centerpush_0p8",
        "expect_dy": 0.8,
        "args": [
            "Model\\GeoEdgeAlignSR_v1_AutoTuneTrain.py",
            "--profile", PROFILE_NAME,
            "--expect-dy", "0.8",
            "--sweep-epochs", "4",
            "--final-epochs", "6",
            "--seed", str(RUN_SEED),
            "--skip-final",
            "--deterministic",
        ],
    },
    {
        "label": "round18_centerpush_8px",
        "expect_dy": 8.0,
        "args": [
            "Model\\GeoEdgeAlignSR_v1_AutoTuneTrain.py",
            "--profile", PROFILE_NAME,
            "--expect-dy", "8.0",
            "--sweep-epochs", "4",
            "--final-epochs", "6",
            "--seed", str(RUN_SEED),
            "--skip-final",
            "--deterministic",
        ],
    },
]


DATASETS = [
    {
        "label": "pitch1um_y_100",
        "input_dir": r"C:\Users\Rio\Downloads\NTU_ImageDataset\Pitch1um_Y_100\Cropped_Output",
    },
    {
        "label": "pitch0p1um_y_60",
        "input_dir": r"C:\Users\Rio\Downloads\NTU_ImageDataset\Pitch0.1um_Y_60\Cropped_Output",
    },
    {
        "label": "pitch0p01um_y_40",
        "input_dir": r"C:\Users\Rio\Downloads\NTU_ImageDataset\Pitch0.01um_Y_40\Cropped_Output",
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


def _safe_float(v, default=float("nan")):
    try:
        if v is None:
            return default
        return float(v)
    except Exception:
        return default


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _summarize_reports(report_paths: list[str]) -> tuple[dict, Path, Path]:
    reports = [_load_json(Path(p)) for p in report_paths]
    by_scale = {}
    for report in reports:
        expect_dy = _safe_float(report.get("common_overrides", {}).get("GMF_EXPECT_DY_PX", float("nan")), float("nan"))
        by_scale[expect_dy] = report

    candidate_map: dict[str, dict] = {}
    required_scales = [0.08, 0.8, 8.0]
    for scale in required_scales:
        report = by_scale.get(scale)
        if report is None:
            continue
        for cand in report.get("candidates", []):
            name = str(cand.get("candidate") or cand.get("name") or "")
            if not name:
                continue
            candidate_map.setdefault(name, {})[scale] = cand

    rows = []
    for name, per_scale in candidate_map.items():
        if not all(scale in per_scale for scale in required_scales):
            continue
        score_0p08 = _safe_float(per_scale[0.08]["score_shift_first"], float("-inf"))
        score_0p8 = _safe_float(per_scale[0.8]["score_shift_first"], float("-inf"))
        score_8px = _safe_float(per_scale[8.0]["score_shift_first"], float("-inf"))
        score_span = max(score_0p08, score_0p8, score_8px) - min(score_0p08, score_0p8, score_8px)

        ann_sign_0p08 = _safe_float(per_scale[0.08]["summary"].get("best_ann_seq_sign_acc"), 0.0)
        seq_sign_0p08 = _safe_float(per_scale[0.08]["summary"].get("best_seq_val_sign_acc"), 0.0)
        center_0p08 = _safe_float(per_scale[0.08]["summary"].get("best_ann_seq_center_err_px"), 1e3)
        step_0p08 = _safe_float(per_scale[0.08]["summary"].get("best_ann_seq_step_err_rel"), 1e3)
        thick_0p08 = _safe_float(per_scale[0.08]["summary"].get("best_ann_seq_thickness_err_rel"), 1e3)

        ann_sign_0p8 = _safe_float(per_scale[0.8]["summary"].get("best_ann_seq_sign_acc"), 0.0)
        seq_sign_0p8 = _safe_float(per_scale[0.8]["summary"].get("best_seq_val_sign_acc"), 0.0)
        center_0p8 = _safe_float(per_scale[0.8]["summary"].get("best_ann_seq_center_err_px"), 1e3)
        step_0p8 = _safe_float(per_scale[0.8]["summary"].get("best_ann_seq_step_err_rel"), 1e3)
        thick_0p8 = _safe_float(per_scale[0.8]["summary"].get("best_ann_seq_thickness_err_rel"), 1e3)

        ann_sign_8px = _safe_float(per_scale[8.0]["summary"].get("best_ann_seq_sign_acc"), 0.0)
        seq_sign_8px = _safe_float(per_scale[8.0]["summary"].get("best_seq_val_sign_acc"), 0.0)
        center_8px = _safe_float(per_scale[8.0]["summary"].get("best_ann_seq_center_err_px"), 1e3)
        step_8px = _safe_float(per_scale[8.0]["summary"].get("best_ann_seq_step_err_rel"), 1e3)
        thick_8px = _safe_float(per_scale[8.0]["summary"].get("best_ann_seq_thickness_err_rel"), 1e3)

        corridor_score = (
            0.20 * score_0p08
            + 7.0 * score_0p8
            + 2.2 * score_8px
            + 18.0 * ann_sign_0p8
            + 12.0 * seq_sign_0p8
            + 5.0 * min(ann_sign_0p8, ann_sign_8px)
            + 4.0 * min(seq_sign_0p8, seq_sign_8px)
            - 44.0 * center_0p8
            - 40.0 * step_0p8
            - 18.0 * thick_0p8
            - 8.0 * max(0.0, center_8px - 0.78)
            - 10.0 * max(0.0, step_8px - 0.18)
            - 8.0 * max(0.0, thick_8px - 0.08)
            - 1.5 * max(0.0, center_0p08 - 0.72)
            - 2.0 * max(0.0, step_0p08 - 0.62)
            - 1.0 * max(0.0, thick_0p08 - 0.05)
            - 1.0 * score_span
        )
        if score_0p8 < 34.0:
            corridor_score -= 90.0
        if ann_sign_0p8 < 0.87:
            corridor_score -= 70.0
        if seq_sign_0p8 < 0.68:
            corridor_score -= 55.0
        if center_0p8 > 0.82:
            corridor_score -= 85.0
        if step_0p8 > 0.40:
            corridor_score -= 65.0
        if thick_0p8 > 0.024:
            corridor_score -= 30.0
        if score_8px < 56.0:
            corridor_score -= 30.0
        if ann_sign_8px < 0.90:
            corridor_score -= 20.0
        if seq_sign_8px < 0.76:
            corridor_score -= 18.0
        if ann_sign_0p08 < 0.72:
            corridor_score -= 10.0
        if seq_sign_0p08 < 0.56:
            corridor_score -= 8.0
        rows.append(
            {
                "candidate": name,
                "score_0p08": score_0p08,
                "score_0p8": score_0p8,
                "score_8px": score_8px,
                "ann_sign_0p08": ann_sign_0p08,
                "ann_sign_0p8": ann_sign_0p8,
                "ann_sign_8px": ann_sign_8px,
                "seq_sign_0p08": seq_sign_0p08,
                "seq_sign_0p8": seq_sign_0p8,
                "seq_sign_8px": seq_sign_8px,
                "center_0p08": center_0p08,
                "center_0p8": center_0p8,
                "center_8px": center_8px,
                "step_0p08": step_0p08,
                "step_0p8": step_0p8,
                "step_8px": step_8px,
                "thick_0p08": thick_0p08,
                "thick_0p8": thick_0p8,
                "thick_8px": thick_8px,
                "score_span": score_span,
                "corridor_score": corridor_score,
                "checkpoint_0p08": per_scale[0.08].get("best_checkpoint_path", ""),
                "checkpoint_0p8": per_scale[0.8].get("best_checkpoint_path", ""),
                "checkpoint_8px": per_scale[8.0].get("best_checkpoint_path", ""),
            }
        )

    rows.sort(key=lambda x: x["corridor_score"], reverse=True)
    if not rows:
        raise RuntimeError("No candidate appears in all three scales.")

    result = {
        "report_paths": report_paths,
        "required_scales": required_scales,
        "rows": rows,
        "best_candidate": rows[0]["candidate"],
        "selection_policy": "center-lock rank: 0.8px center stability primary gate, 8px non-regression gate, 0.08px secondary tie-breaker; deployment checkpoint chosen by center-lock audit",
    }

    ts = time.strftime("%Y%m%d_%H%M%S", time.localtime())
    SUMMARY_DIR.mkdir(parents=True, exist_ok=True)
    SELECTED_DIR.mkdir(parents=True, exist_ok=True)
    json_path = SUMMARY_DIR / f"{SUMMARY_PREFIX}_MULTISCALE_SUMMARY_{ts}.json"
    md_path = SUMMARY_DIR / f"{SUMMARY_PREFIX}_MULTISCALE_SUMMARY_{ts}.md"
    json_path.write_text(json.dumps(result, indent=2), encoding="utf-8")
    lines = [
        f"# {SUMMARY_PREFIX} Multiscale Summary",
        "",
        f"- best_candidate_family: {rows[0]['candidate']}",
        f"- selection_policy: center-lock rank uses 0.8px center stability primary gate, 8px non-regression gate, 0.08px secondary tie-breaker; deployment checkpoint chosen by center-lock audit",
        "",
        "| candidate | s0.08 | s0.8 | s8 | ann0.8 | seq0.8 | c0.8 | step0.8 | thick0.8 | corridor |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in rows:
        lines.append(
            f"| {row['candidate']} | {row['score_0p08']:.3f} | {row['score_0p8']:.3f} | {row['score_8px']:.3f} | "
            f"{row['ann_sign_0p8']:.4f} | {row['seq_sign_0p8']:.4f} | {row['center_0p8']:.4f} | "
            f"{row['step_0p8']:.4f} | {row['thick_0p8']:.4f} | {row['corridor_score']:.3f} |"
        )
    md_path.write_text("\n".join(lines), encoding="utf-8")
    return result, json_path, md_path


def _run_checkpoint_audit(summary_result: dict) -> tuple[dict, Path, Path]:
    rows = list(summary_result["rows"])
    if not rows:
        raise RuntimeError("No rows available for checkpoint audit.")
    audit_rows = rows[: max(1, int(AUDIT_TOP_K))]
    ts = time.strftime("%Y%m%d_%H%M%S", time.localtime())
    audits = []
    for idx, row in enumerate(audit_rows, start=1):
        candidate = str(row["candidate"])
        json_path = SUMMARY_DIR / f"{SUMMARY_PREFIX}_CHECKPOINT_AUDIT_{candidate}_{ts}.json"
        md_path = SUMMARY_DIR / f"{SUMMARY_PREFIX}_CHECKPOINT_AUDIT_{candidate}_{ts}.md"
        cmd = [
            sys.executable,
            "-u",
            str(PROJECT_ROOT / "Model" / "GeoEdgeAlignSR_v1_UniversalCheckpointAudit.py"),
            "--candidate", candidate,
            "--checkpoint-0p08", str(row["checkpoint_0p08"]),
            "--checkpoint-0p8", str(row["checkpoint_0p8"]),
            "--checkpoint-8px", str(row["checkpoint_8px"]),
            "--output-json", str(json_path),
            "--output-md", str(md_path),
            "--seed", str(RUN_SEED),
            "--mode", "centerlock0p8",
        ]
        print(f"[CORRIDOR][AUDIT] {idx}/{len(audit_rows)} candidate={candidate}")
        rc = _run_subprocess(cmd, PROJECT_ROOT)
        if rc != 0:
            raise RuntimeError(f"Checkpoint audit failed for {candidate} rc={rc}")
        audit_payload = _load_json(json_path)
        audits.append(
            {
                "candidate": candidate,
                "family_score": float(row["corridor_score"]),
                "audit_json": str(json_path),
                "audit_md": str(md_path),
                "best_checkpoint_label": str(audit_payload["best_checkpoint_label"]),
                "best_checkpoint_path": str(audit_payload["best_checkpoint_path"]),
                "best_deployment_score": float(audit_payload["best_deployment_score"]),
                "audit_results": audit_payload["results"],
            }
        )
    audits.sort(key=lambda x: x["best_deployment_score"], reverse=True)
    best = audits[0]
    result = {
        "audits": audits,
        "best_candidate": best["candidate"],
        "selected_checkpoint": best["best_checkpoint_path"],
        "selection_policy": "center-lock checkpoint audit across 0.08/0.8/8.0 after 0.8px center-stability pre-rank",
    }
    final_json = SUMMARY_DIR / f"{SUMMARY_PREFIX}_CHECKPOINT_AUDIT_SUMMARY_{ts}.json"
    final_md = SUMMARY_DIR / f"{SUMMARY_PREFIX}_CHECKPOINT_AUDIT_SUMMARY_{ts}.md"
    final_json.write_text(json.dumps(result, indent=2), encoding="utf-8")
    md_lines = [
        f"# {SUMMARY_PREFIX} Checkpoint Audit Summary",
        "",
        f"- best_candidate: {best['candidate']}",
        f"- selected_checkpoint: {best['best_checkpoint_path']}",
        f"- selection_policy: center-lock checkpoint audit across 0.08/0.8/8.0 after 0.8px center-stability pre-rank",
        "",
        "| candidate | family | deploy | checkpoint |",
        "| --- | ---: | ---: | --- |",
    ]
    for row in audits:
        md_lines.append(
            f"| {row['candidate']} | {row['family_score']:.3f} | {row['best_deployment_score']:.3f} | "
            f"{row['best_checkpoint_label']} |"
        )
    final_md.write_text("\n".join(md_lines), encoding="utf-8")

    manifest = {
        "candidate": best["candidate"],
        "weights_path": best["best_checkpoint_path"],
        "summary_json": str(final_json),
        "summary_md": str(final_md),
        "updated_at": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime()),
    }
    (SELECTED_DIR / "current_centerpush_seed.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest, final_json, final_md


def _run_subprocess(cmd: list[str], cwd: Path, live_prefix: str = "") -> int:
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
        if live_prefix:
            print(f"{live_prefix}{line}", end="")
        else:
            print(line, end="")
    return proc.wait()


def _run_reconstructions(weights_path: str) -> Path:
    recon_root = RECON_ROOT / "reconstructions"
    log_root = RECON_ROOT / "logs"
    recon_root.mkdir(parents=True, exist_ok=True)
    log_root.mkdir(parents=True, exist_ok=True)
    manifest = {
        "weights_path": weights_path,
        "runs": [],
    }
    for item in DATASETS:
        label = item["label"]
        input_dir = item["input_dir"]
        cmd = [
            sys.executable,
            "-u",
            str(PROJECT_ROOT / "Model" / "GeoEdgeAlignSR_v1_Infer_v5_NoCoord_return_v2_SimpleTest.py"),
            "--weights",
            weights_path,
            "--input-dir",
            input_dir,
            "--recon-root",
            str(recon_root),
            "--output-name",
            f"{label}_odd",
            "--select-mode",
            "odd",
        ]
        log_path = log_root / f"{label}.out.log"
        err_path = log_root / f"{label}.err.log"
        with open(log_path, "w", encoding="utf-8") as fout, open(err_path, "w", encoding="utf-8") as ferr:
            proc = subprocess.Popen(cmd, cwd=str(PROJECT_ROOT), stdout=fout, stderr=ferr, text=True)
            rc = proc.wait()
        manifest["runs"].append(
            {
                "label": label,
                "input_dir": input_dir,
                "rc": rc,
                "stdout": str(log_path),
                "stderr": str(err_path),
            }
        )
        if rc != 0:
            raise RuntimeError(f"Reconstruction failed for {label} rc={rc}")
    manifest_path = RECON_ROOT / "recon_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest_path


def main() -> None:
    LOG_ROOT.mkdir(parents=True, exist_ok=True)
    REPORT_ROOT.mkdir(parents=True, exist_ok=True)
    SUMMARY_DIR.mkdir(parents=True, exist_ok=True)
    RUN_FLAG.write_text("RUNNING\n", encoding="utf-8")
    if NOTIFY_FLAG.exists():
        NOTIFY_FLAG.unlink()

    if RESUME_FROM_CHECKPOINT is not None:
        import shutil
        resume_src = Path(RESUME_FROM_CHECKPOINT)
        if not resume_src.exists():
            print(f"[ROUND18] WARNING: RESUME_FROM_CHECKPOINT={RESUME_FROM_CHECKPOINT!r} does not exist, ignoring.")
        else:
            resume_dst = PROJECT_ROOT / "weights" / "round18_resume_init.pth.tar"
            resume_dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(str(resume_src), str(resume_dst))
            print(f"[ROUND18] Copied resume checkpoint -> {resume_dst}")

    total = len(PLAN) + 3
    report_paths: list[str] = []
    _write_status(
        state="running",
        step_index=0,
        active_label="bootstrap",
        active_command="",
        plan_done=0,
        plan_total=total,
        note=f"starting {PROFILE_NAME} 0.8px corridor long-run",
    )
    try:
        step_done = 0
        for idx, step in enumerate(PLAN, start=1):
            label = str(step["label"])
            cmd = [sys.executable, "-u", *step["args"]]
            cmd_text = " ".join(cmd)
            _write_status(
                state="running",
                step_index=idx,
                active_label=label,
                active_command=cmd_text,
                plan_done=step_done,
                plan_total=total,
                note="training step running",
            )
            print(f"[CORRIDOR] step {idx}/{total} start label={label}")
            before_ts = time.time()
            rc = _run_subprocess(cmd, PROJECT_ROOT)
            latest_report = _latest_report(before_ts - 1.0) if bool(step.get("collect_report", True)) else ""
            if rc != 0:
                _write_status(
                    state="error",
                    step_index=idx,
                    active_label=label,
                    active_command=cmd_text,
                    plan_done=step_done,
                    plan_total=total,
                    last_report=latest_report,
                    last_exit=str(rc),
                    note="training step failed",
                )
                NOTIFY_FLAG.write_text("LONGRUN CORRIDOR FAILED\n", encoding="utf-8")
                sys.exit(rc)
            if latest_report:
                report_paths.append(latest_report)
            step_done += 1
            _write_status(
                state="running",
                step_index=idx,
                active_label=label,
                active_command=cmd_text,
                plan_done=step_done,
                plan_total=total,
                last_report=latest_report,
                last_exit="0",
                note="training step completed",
            )

        idx = len(PLAN) + 1
        _write_status(
            state="running",
            step_index=idx,
            active_label="aggregate_corridor_summary",
            active_command="internal aggregate",
            plan_done=step_done,
            plan_total=total,
            note="aggregating multiscale reports",
        )
        summary_result, summary_json, summary_md = _summarize_reports(report_paths)
        step_done += 1
        _write_status(
            state="running",
            step_index=idx,
            active_label="aggregate_corridor_summary",
            active_command="internal aggregate",
            plan_done=step_done,
            plan_total=total,
            last_report=str(summary_json),
            last_exit="0",
            note="aggregate completed",
            selected_candidate=str(summary_result["best_candidate"]),
            selected_checkpoint="",
        )

        idx = len(PLAN) + 2
        _write_status(
            state="running",
            step_index=idx,
            active_label="checkpoint_audit",
            active_command="internal audit",
            plan_done=step_done,
            plan_total=total,
            last_report=str(summary_json),
            last_exit="0",
            note="auditing candidate checkpoints across 0.08/0.8/8.0",
            selected_candidate=str(summary_result["best_candidate"]),
            selected_checkpoint="",
        )
        manifest, audit_json, audit_md = _run_checkpoint_audit(summary_result)
        step_done += 1
        _write_status(
            state="running",
            step_index=idx,
            active_label="checkpoint_audit",
            active_command="internal audit",
            plan_done=step_done,
            plan_total=total,
            last_report=str(audit_json),
            last_exit="0",
            note="checkpoint audit completed",
            selected_candidate=str(manifest["candidate"]),
            selected_checkpoint=str(manifest["weights_path"]),
        )

        idx = len(PLAN) + 3
        _write_status(
            state="running",
            step_index=idx,
            active_label="reconstruct_external_datasets",
            active_command="infer x3 datasets",
            plan_done=step_done,
            plan_total=total,
            note="running reconstructions for external validation",
            selected_candidate=str(manifest["candidate"]),
            selected_checkpoint=str(manifest["weights_path"]),
        )
        recon_manifest = _run_reconstructions(str(manifest["weights_path"]))
        step_done += 1
        _write_status(
            state="completed",
            step_index=idx,
            active_label="",
            active_command="",
            plan_done=step_done,
            plan_total=total,
            last_report=str(audit_json),
            last_exit="0",
            note=f"all steps completed | family={summary_md} | audit={audit_md} | recon={recon_manifest}",
            selected_candidate=str(manifest["candidate"]),
            selected_checkpoint=str(manifest["weights_path"]),
        )
        print("[CORRIDOR] COMPLETED")
    finally:
        if RUN_FLAG.exists():
            RUN_FLAG.unlink()


if __name__ == "__main__":
    main()

import argparse
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path

from GeoEdgeAlignSR_v1_PolicyAccess import (
    get_legacy_sources,
    get_macro_estimator,
    get_measurement_guardrails,
    load_estimator_policy,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
PROCESS_AUDIT = PROJECT_ROOT / "Model" / "GeoEdgeAlignSR_v1_ProcessProbeAudit.py"
ROUND18_MANIFEST = (
    PROJECT_ROOT
    / "Traing_Progress"
    / "organized_20260313"
    / "round18"
    / "selected"
    / "current_centerpush_seed.json"
)
POLICY_JSON = PROJECT_ROOT / "ESTIMATOR_POLICY.json"
DEFAULT_OUTPUT_ROOT = PROJECT_ROOT / "Traing_Progress" / "organized_20260315" / "estimator_formula_probe"


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    p.add_argument("--expect-dy", type=float, default=0.8)
    p.add_argument("--seed", type=int, default=1261210)
    return p.parse_args()


def resolve_round18_checkpoint() -> str:
    payload = json.loads(ROUND18_MANIFEST.read_text(encoding="utf-8"))
    ckpt = payload.get("checkpoint") or payload.get("weights_path")
    if not ckpt:
        raise FileNotFoundError(f"Checkpoint unresolved from {ROUND18_MANIFEST}")
    return str(ckpt)


def read_policy() -> dict:
    policy = load_estimator_policy(POLICY_JSON)
    sources = get_legacy_sources(policy)
    macro_guard_pass = True
    reevaluation_json = str(PROJECT_ROOT / sources.get("phase2_reevaluation_json"))
    if reevaluation_json:
        try:
            macro_guard_pass = bool(
                json.loads(Path(str(reevaluation_json)).read_text(encoding="utf-8")).get("macro_guard_pass", True)
            )
        except Exception:
            macro_guard_pass = True
    return {
        "policy": policy,
        "guardrails": get_measurement_guardrails(policy),
        "macro_estimator": get_macro_estimator(policy),
        "macro_guard_pass": macro_guard_pass,
    }


def move_new_audit_runs(before: set[str], archive_dir: Path) -> None:
    archive_dir.mkdir(parents=True, exist_ok=True)
    now = {
        p.name
        for p in (PROJECT_ROOT / "Traing_Progress").glob("training_progress_process_probe_*")
        if p.is_dir()
    }
    new_names = sorted(now - before)
    for name in new_names:
        src = PROJECT_ROOT / "Traing_Progress" / name
        dst = archive_dir / name
        if dst.exists():
            shutil.rmtree(dst)
        shutil.move(str(src), str(dst))


def run_audit(
    *,
    candidate: str,
    geom_method: str,
    checkpoint: str,
    expect_dy: float,
    output_root: Path,
    seed: int,
) -> dict:
    reports = output_root / "selected" / "reports"
    archive_audits = output_root / "archive" / "audit_runs"
    reports.mkdir(parents=True, exist_ok=True)
    before = {
        p.name
        for p in (PROJECT_ROOT / "Traing_Progress").glob("training_progress_process_probe_*")
        if p.is_dir()
    }
    out_json = reports / f"ESTIMATOR_FORMULA_AUDIT_{candidate}.json"
    out_md = reports / f"ESTIMATOR_FORMULA_AUDIT_{candidate}.md"
    cmd = [
        sys.executable,
        str(PROCESS_AUDIT),
        "--candidate", candidate,
        "--checkpoint", checkpoint,
        "--geom-method", geom_method,
        "--expect-dy", str(float(expect_dy)),
        "--output-json", str(out_json),
        "--output-md", str(out_md),
        "--seed", str(int(seed)),
    ]
    subprocess.run(cmd, check=True, cwd=str(PROJECT_ROOT))
    move_new_audit_runs(before, archive_audits)
    return json.loads(out_json.read_text(encoding="utf-8"))


def main() -> None:
    args = parse_args()
    output_root = args.output_root
    output_root.mkdir(parents=True, exist_ok=True)
    checkpoint = resolve_round18_checkpoint()
    policy_pack = read_policy()
    macro_ready = bool(policy_pack["macro_guard_pass"])
    control_relative = policy_pack["guardrails"]["mid_0p8"]
    center_improvement_min = float(control_relative["center_improvement_ratio_min"])
    step_err_max = float(control_relative["step_err_max"])

    candidates = [
        ("edge_ctrl", "edge_centroid"),
        ("soft_band", "soft_band_refine"),
        ("soft_band_light", "soft_band_light"),
        ("soft_band_sharp", "soft_band_sharp"),
        ("soft_band_stepmix", "soft_band_stepmix"),
        ("soft_band_stepmix_sharp", "soft_band_stepmix_sharp"),
    ]

    results = []
    for offset, (name, method) in enumerate(candidates):
        payload = run_audit(
            candidate=name,
            geom_method=method,
            checkpoint=checkpoint,
            expect_dy=float(args.expect_dy),
            output_root=output_root,
            seed=int(args.seed) + offset,
        )
        results.append(payload)

    control = next(r for r in results if r["candidate"] == "edge_ctrl")
    control_center = float(control["summary"]["best_ann_seq_center_err_px"])

    ranked = []
    for row in results:
        center = float(row["summary"]["best_ann_seq_center_err_px"])
        step = float(row["summary"]["best_ann_seq_step_err_rel"])
        sign_acc = float(row["summary"]["best_seq_val_sign_acc"])
        if row["candidate"] == "edge_ctrl":
            improve_ratio = 0.0
        else:
            improve_ratio = (control_center - center) / max(control_center, 1e-6)
        passes_mid = (improve_ratio >= center_improvement_min) and (step <= step_err_max)
        ranked.append(
            {
                "candidate": row["candidate"],
                "geom_method": row["geom_method"],
                "checkpoint_path": row["checkpoint_path"],
                "center_err": center,
                "step_err": step,
                "seq_sign_acc": sign_acc,
                "center_improvement_ratio": improve_ratio,
                "passes_mid_gate": passes_mid,
            }
        )

    ranked.sort(key=lambda r: (not r["passes_mid_gate"], r["step_err"], r["center_err"], -r["seq_sign_acc"]))
    best = ranked[0]
    round21_ready = bool(best["passes_mid_gate"] and macro_ready and best["candidate"] != "edge_ctrl")

    summary = {
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "checkpoint": checkpoint,
        "macro_policy_estimator": policy_pack["macro_estimator"],
        "macro_guard_pass": macro_ready,
        "mid_gate": {
            "center_improvement_ratio_min": center_improvement_min,
            "step_err_max": step_err_max,
        },
        "results": ranked,
        "best_candidate": best,
        "round21_ready": round21_ready,
        "blocked_reason": None if round21_ready else (
            "No mid-scale estimator variant passed the calibrated center+step gate."
            if best["candidate"] == "edge_ctrl" or not best["passes_mid_gate"]
            else "Macro guard remains blocked."
        ),
    }

    reports = output_root / "selected" / "reports"
    reports.mkdir(parents=True, exist_ok=True)
    ts = time.strftime("%Y%m%d_%H%M%S")
    out_json = reports / f"ESTIMATOR_FORMULA_PROBE_SUMMARY_{ts}.json"
    out_md = reports / f"ESTIMATOR_FORMULA_PROBE_SUMMARY_{ts}.md"
    out_json.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    lines = [
        "# Estimator Formula Probe Summary",
        "",
        f"- generated_at: {summary['generated_at']}",
        f"- checkpoint: `{checkpoint}`",
        f"- macro_policy_estimator: `{summary['macro_policy_estimator']}`",
        f"- macro_guard_pass: `{summary['macro_guard_pass']}`",
        f"- round21_ready: `{summary['round21_ready']}`",
        f"- blocked_reason: {summary['blocked_reason'] or 'none'}",
        "",
        "| candidate | geom_method | center_err | step_err | seq_sign | center_improve | passes_mid_gate |",
        "| --- | --- | ---: | ---: | ---: | ---: | --- |",
    ]
    for row in ranked:
        lines.append(
            f"| {row['candidate']} | {row['geom_method']} | {row['center_err']:.4f} | "
            f"{row['step_err']:.4f} | {row['seq_sign_acc']:.4f} | "
            f"{row['center_improvement_ratio']:.4f} | {row['passes_mid_gate']} |"
        )
    out_md.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"[FORMULA_PROBE] summary_json={out_json}")
    print(f"[FORMULA_PROBE] summary_md={out_md}")
    print(f"[FORMULA_PROBE] round21_ready={round21_ready}")


if __name__ == "__main__":
    main()

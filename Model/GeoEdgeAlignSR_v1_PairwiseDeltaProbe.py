import argparse
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path

from GeoEdgeAlignSR_v1_PolicyAccess import get_macro_estimator, get_measurement_guardrails, load_estimator_policy


PROJECT_ROOT = Path(__file__).resolve().parents[1]
PROCESS_AUDIT = PROJECT_ROOT / "Model" / "GeoEdgeAlignSR_v1_ProcessProbeAudit.py"
ROUND18_MANIFEST = (
    PROJECT_ROOT
    / "Experiments"
    / "Legacy"
    / "organized_20260313"
    / "round18"
    / "selected"
    / "current_centerpush_seed.json"
)
POLICY_JSON = PROJECT_ROOT / "ESTIMATOR_POLICY.json"
DEFAULT_OUTPUT_ROOT = PROJECT_ROOT / "Experiments" / "Legacy" / "organized_20260315" / "pairwise_delta_probe"


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    p.add_argument("--seed", type=int, default=1261211)
    return p.parse_args()


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def resolve_round18_checkpoint() -> str:
    payload = _load_json(ROUND18_MANIFEST)
    ckpt = payload.get("checkpoint") or payload.get("weights_path")
    if not ckpt:
        raise FileNotFoundError(f"Checkpoint unresolved from {ROUND18_MANIFEST}")
    return str(ckpt)


def move_new_audit_runs(before: set[str], archive_dir: Path) -> None:
    archive_dir.mkdir(parents=True, exist_ok=True)
    now = {
        p.name
        for p in (PROJECT_ROOT / "Experiments" / "Training_Runs").glob("training_progress_process_probe_*")
        if p.is_dir()
    }
    new_names = sorted(now - before)
    for name in new_names:
        src = PROJECT_ROOT / "Experiments" / "Training_Runs" / name
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
        for p in (PROJECT_ROOT / "Experiments" / "Training_Runs").glob("training_progress_process_probe_*")
        if p.is_dir()
    }
    suffix = str(float(expect_dy)).replace(".", "p")
    out_json = reports / f"PAIRWISE_DELTA_AUDIT_{candidate}_{suffix}.json"
    out_md = reports / f"PAIRWISE_DELTA_AUDIT_{candidate}_{suffix}.md"
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
    return _load_json(out_json)


def main() -> None:
    args = parse_args()
    output_root = args.output_root
    output_root.mkdir(parents=True, exist_ok=True)
    checkpoint = resolve_round18_checkpoint()
    policy = load_estimator_policy(POLICY_JSON)
    guardrails = get_measurement_guardrails(policy)

    mid_center_ratio_min = float(guardrails["mid_0p8"]["center_improvement_ratio_min"])
    mid_step_max = float(guardrails["mid_0p8"]["step_err_max"])
    macro_step_max = float(guardrails["macro_8px"]["step_err_max"])
    macro_seq_sign_min = float(guardrails["macro_8px"]["seq_sign_acc_min"])
    macro_geom_method = get_macro_estimator(policy)

    candidates = [
        ("edge_ctrl", "edge_centroid"),
        ("soft_band", "soft_band_refine"),
        ("pairmix_softcentroid", "pairmix_softcentroid"),
        ("pairmix_softblend", "pairmix_softblend"),
        ("pairmix_algblend", "pairmix_algblend"),
    ]

    mid_results = []
    for offset, (name, method) in enumerate(candidates):
        payload = run_audit(
            candidate=name,
            geom_method=method,
            checkpoint=checkpoint,
            expect_dy=0.8,
            output_root=output_root,
            seed=int(args.seed) + offset,
        )
        mid_results.append(payload)

    macro_payload = run_audit(
        candidate="macro_guard_ref",
        geom_method=macro_geom_method,
        checkpoint=checkpoint,
        expect_dy=8.0,
        output_root=output_root,
        seed=int(args.seed) + 99,
    )
    macro_step = float(macro_payload["summary"]["best_ann_seq_step_err_rel"])
    macro_seq_sign = float(macro_payload["summary"]["best_seq_val_sign_acc"])
    macro_guard_pass = bool(macro_step <= macro_step_max and macro_seq_sign >= macro_seq_sign_min)

    control = next(r for r in mid_results if r["candidate"] == "edge_ctrl")
    control_center = float(control["summary"]["best_ann_seq_center_err_px"])

    ranked = []
    for row in mid_results:
        center = float(row["summary"]["best_ann_seq_center_err_px"])
        step = float(row["summary"]["best_ann_seq_step_err_rel"])
        sign_acc = float(row["summary"]["best_seq_val_sign_acc"])
        improve_ratio = 0.0 if row["candidate"] == "edge_ctrl" else (control_center - center) / max(control_center, 1.0e-6)
        is_pairmix = str(row["candidate"]).startswith("pairmix_")
        passes_mid = (improve_ratio >= mid_center_ratio_min) and (step <= mid_step_max)
        passes_final = bool(is_pairmix and passes_mid and macro_guard_pass)
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
                "macro_guard_pass": macro_guard_pass,
                "macro_step_err": macro_step,
                "macro_seq_sign_acc": macro_seq_sign,
                "passes_final_gate": passes_final,
            }
        )

    ranked.sort(
        key=lambda r: (
            not r["passes_final_gate"],
            not r["passes_mid_gate"],
            r["step_err"],
            r["center_err"],
            -r["seq_sign_acc"],
        )
    )
    pairmix_rows = [row for row in ranked if row["candidate"].startswith("pairmix_")]
    best_pairmix = pairmix_rows[0] if pairmix_rows else None
    round22_ready = bool(best_pairmix and best_pairmix["passes_final_gate"])

    summary = {
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "checkpoint": checkpoint,
        "macro_policy_estimator": macro_geom_method,
        "macro_guard": {
            "step_err_max": macro_step_max,
            "seq_sign_acc_min": macro_seq_sign_min,
            "observed_step_err": macro_step,
            "observed_seq_sign_acc": macro_seq_sign,
            "passes": macro_guard_pass,
        },
        "mid_gate": {
            "center_improvement_ratio_min": mid_center_ratio_min,
            "step_err_max": mid_step_max,
        },
        "results": ranked,
        "best_pairmix_candidate": best_pairmix,
        "round22_ready": round22_ready,
        "blocked_reason": None if round22_ready else (
            "No pairmix estimator cleared the calibrated mid+macro gate."
        ),
    }

    reports = output_root / "selected" / "reports"
    reports.mkdir(parents=True, exist_ok=True)
    ts = time.strftime("%Y%m%d_%H%M%S")
    out_json = reports / f"PAIRWISE_DELTA_PROBE_SUMMARY_{ts}.json"
    out_md = reports / f"PAIRWISE_DELTA_PROBE_SUMMARY_{ts}.md"
    out_json.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    lines = [
        "# Pairwise Delta Probe Summary",
        "",
        f"- generated_at: {summary['generated_at']}",
        f"- checkpoint: `{checkpoint}`",
        f"- macro_policy_estimator: `{macro_geom_method}`",
        f"- macro_guard_pass: `{macro_guard_pass}`",
        f"- round22_ready: `{round22_ready}`",
        f"- blocked_reason: {summary['blocked_reason'] or 'none'}",
        "",
        "| candidate | geom_method | center_err | step_err | seq_sign | center_improve | mid_pass | macro_pass | final_pass |",
        "| --- | --- | ---: | ---: | ---: | ---: | --- | --- | --- |",
    ]
    for row in ranked:
        lines.append(
            f"| {row['candidate']} | {row['geom_method']} | {row['center_err']:.4f} | "
            f"{row['step_err']:.4f} | {row['seq_sign_acc']:.4f} | "
            f"{row['center_improvement_ratio']:.4f} | {row['passes_mid_gate']} | "
            f"{row['macro_guard_pass']} | {row['passes_final_gate']} |"
        )
    out_md.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"[PAIRWISE_DELTA_PROBE] summary_json={out_json}")
    print(f"[PAIRWISE_DELTA_PROBE] summary_md={out_md}")
    print(f"[PAIRWISE_DELTA_PROBE] round22_ready={round22_ready}")


if __name__ == "__main__":
    main()

"""
GeoEdgeAlignSR_v1_BranchEPhase2Reevaluate.py

Re-evaluate Branch E Phase2 with control-relative 8px guard:
- 0.8px: center improvement vs control must be >= 25%
- 0.8px: step_err must be <= 0.45
- 8px: step_err <= control step + 0.12
- 8px: seq sign >= control seq sign - 0.05

Outputs:
- BRANCH_E_PHASE2_REEVALUATION_{ts}.json/.md
- ESTIMATOR_POLICY.json
"""

from __future__ import annotations

import json
import time
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
PHASE2_REPORT_ROOT = (
    PROJECT_ROOT
    / "Traing_Progress"
    / "organized_20260315"
    / "branch_e_followup"
    / "selected"
    / "reports"
)
BENCHMARK_ROOT = (
    PROJECT_ROOT
    / "Traing_Progress"
    / "organized_20260314"
    / "branch_e"
    / "benchmark"
)
POLICY_PATH = PROJECT_ROOT / "ESTIMATOR_POLICY.json"
PHASE2_MANIFEST = (
    PROJECT_ROOT
    / "Traing_Progress"
    / "organized_20260315"
    / "branch_e_followup"
    / "selected"
    / "current_branch_e_phase2_seed.json"
)


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _latest(path: Path, pattern: str) -> Path:
    matches = sorted(path.glob(pattern), key=lambda p: p.stat().st_mtime, reverse=True)
    if not matches:
        raise FileNotFoundError(f"No file matched {pattern} under {path}")
    return matches[0]


def _safe_float(v, default=float("nan")):
    try:
        if v is None:
            return default
        return float(v)
    except Exception:
        return default


def _benchmark_macro_policy(raw_payload: dict) -> dict:
    rows = [
        row for row in raw_payload.get("rows", [])
        if _safe_float(row.get("scale_px"), -1.0) == 8.0
        and str(row.get("domain", "")) in {"clean", "convolved"}
        and str(row.get("estimator", "")) in {"edge_centroid", "edge_band_refine"}
    ]
    grouped: dict[str, list[dict]] = {}
    for row in rows:
        grouped.setdefault(str(row["estimator"]), []).append(row)
    agg = {}
    for estimator, estimator_rows in grouped.items():
        count = float(len(estimator_rows))
        agg[estimator] = {
            "avg_step_err_rel": sum(_safe_float(r["step_err_rel"], 0.0) for r in estimator_rows) / count,
            "avg_sign_acc": sum(_safe_float(r["sign_acc"], 0.0) for r in estimator_rows) / count,
            "avg_abs_center_err_px": sum(_safe_float(r["abs_center_err_px"], 0.0) for r in estimator_rows) / count,
        }
    control = agg["edge_centroid"]
    edge_band = agg["edge_band_refine"]
    use_edge_band = (
        edge_band["avg_step_err_rel"] <= (control["avg_step_err_rel"] - 0.02)
        and edge_band["avg_sign_acc"] >= (control["avg_sign_acc"] - 0.05)
    )
    return {
        "control_8px_benchmark": control,
        "edge_band_8px_benchmark": edge_band,
        "macro_policy_estimator": "edge_band_refine" if use_edge_band else "edge_centroid",
        "macro_policy_reason": (
            "edge_band_refine beat control on 8px benchmark step_err by at least 0.02 with acceptable sign_acc"
            if use_edge_band
            else "edge_band_refine did not clear the 8px benchmark replacement rule; keep edge_centroid"
        ),
    }


def main() -> int:
    audit_08_path = _latest(PHASE2_REPORT_ROOT, "BRANCH_E_PHASE2_AUDIT_0P8_SUMMARY_*.json")
    audit_8_path = _latest(PHASE2_REPORT_ROOT, "BRANCH_E_PHASE2_AUDIT_8P0_SUMMARY_*.json")
    benchmark_raw_path = _latest(BENCHMARK_ROOT, "BRANCH_E_ESTIMATOR_BENCHMARK_RAW_*.json")

    audit_08 = _load_json(audit_08_path)
    audit_8 = _load_json(audit_8_path)
    benchmark_raw = _load_json(benchmark_raw_path)

    rows_08 = list(audit_08["rows"])
    rows_8 = list(audit_8["rows"])
    control_08 = next(row for row in rows_08 if row["candidate"] == "be_ctrl_edge")
    control_8 = next(row for row in rows_8 if row["candidate"] == "be_ctrl_edge")
    best_08 = rows_08[0]
    best_8 = next((row for row in rows_8 if row["candidate"] == best_08["candidate"]), None)

    center_improvement_abs = _safe_float(control_08["best_center_err"]) - _safe_float(best_08["best_center_err"])
    center_improvement_ratio = (
        center_improvement_abs / max(_safe_float(control_08["best_center_err"]), 1.0e-9)
    )
    mid_step_pass = _safe_float(best_08["best_step_err"]) <= 0.45
    mid_center_pass = center_improvement_ratio >= 0.25

    control_guard_step = _safe_float(control_8["best_step_err"])
    control_guard_seq_sign = _safe_float(control_8["best_seq_sign"])
    guard_step_limit = control_guard_step + 0.12
    guard_seq_sign_floor = control_guard_seq_sign - 0.05
    macro_guard_pass = False
    if best_8 is not None:
        macro_guard_pass = (
            _safe_float(best_8["best_step_err"]) <= guard_step_limit
            and _safe_float(best_8["best_seq_sign"]) >= guard_seq_sign_floor
        )

    reevaluation_pass = (
        best_08["candidate"] != "be_ctrl_edge"
        and mid_center_pass
        and mid_step_pass
        and macro_guard_pass
    )

    macro_policy = _benchmark_macro_policy(benchmark_raw)

    ts = time.strftime("%Y%m%d_%H%M%S", time.localtime())
    reeval_payload = {
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime()),
        "audit_0p8_summary": str(audit_08_path),
        "audit_8p0_summary": str(audit_8_path),
        "benchmark_raw": str(benchmark_raw_path),
        "control_0p8": control_08,
        "best_0p8_candidate": best_08,
        "best_8p0_candidate_row": best_8,
        "center_improvement_abs_px": center_improvement_abs,
        "center_improvement_ratio": center_improvement_ratio,
        "mid_center_pass": mid_center_pass,
        "mid_step_threshold": 0.45,
        "mid_step_pass": mid_step_pass,
        "control_guard_step": control_guard_step,
        "control_guard_seq_sign": control_guard_seq_sign,
        "guard_step_limit": guard_step_limit,
        "guard_seq_sign_floor": guard_seq_sign_floor,
        "macro_guard_pass": macro_guard_pass,
        "reevaluation_pass": reevaluation_pass,
        "macro_policy": macro_policy,
    }

    reeval_json = PHASE2_REPORT_ROOT / f"BRANCH_E_PHASE2_REEVALUATION_{ts}.json"
    reeval_md = PHASE2_REPORT_ROOT / f"BRANCH_E_PHASE2_REEVALUATION_{ts}.md"
    reeval_json.write_text(json.dumps(reeval_payload, indent=2), encoding="utf-8")

    md_lines = [
        "# BRANCH_E_PHASE2 Reevaluation",
        "",
        f"- best_0p8_candidate: `{best_08['candidate']}`",
        f"- control_0p8_center_err: `{_safe_float(control_08['best_center_err']):.6f}`",
        f"- best_0p8_center_err: `{_safe_float(best_08['best_center_err']):.6f}`",
        f"- center_improvement_abs_px: `{center_improvement_abs:.6f}`",
        f"- center_improvement_ratio: `{center_improvement_ratio:.4%}`",
        f"- best_0p8_step_err: `{_safe_float(best_08['best_step_err']):.6f}`",
        f"- mid_center_pass: `{mid_center_pass}`",
        f"- mid_step_pass: `{mid_step_pass}`",
        f"- control_guard_step: `{control_guard_step:.6f}`",
        f"- guard_step_limit: `{guard_step_limit:.6f}`",
        f"- control_guard_seq_sign: `{control_guard_seq_sign:.6f}`",
        f"- guard_seq_sign_floor: `{guard_seq_sign_floor:.6f}`",
        f"- macro_guard_pass: `{macro_guard_pass}`",
        f"- reevaluation_pass: `{reevaluation_pass}`",
        "",
        "## Interpretation",
        "",
    ]
    if reevaluation_pass:
        md_lines.extend(
            [
                "Branch E Phase2 passes the calibrated control-relative guard.",
                "A hybrid estimator Round21 is justified under the new rules.",
            ]
        )
    else:
        fail_reasons = []
        if not mid_center_pass:
            fail_reasons.append("0.8px center improvement did not reach the 25% threshold")
        if not mid_step_pass:
            fail_reasons.append("0.8px step_err remained above 0.45")
        if not macro_guard_pass:
            fail_reasons.append("8px control-relative guard did not pass")
        md_lines.extend(
            [
                "Branch E Phase2 does not yet justify launching Round21.",
                "The original absolute 8px <= 0.04 guard is discarded for this harness, but the reevaluation still fails for the reasons below:",
                "",
            ]
        )
        for reason in fail_reasons:
            md_lines.append(f"- {reason}")
    md_lines.extend(
        [
            "",
            "## Frozen Estimator Policy",
            "",
            f"- tiny_0p08: `edge_centroid`",
            f"- mid_0p8_candidate: `soft_band_refine`",
            f"- macro_8px: `{macro_policy['macro_policy_estimator']}`",
            f"- macro_policy_reason: {macro_policy['macro_policy_reason']}",
        ]
    )
    reeval_md.write_text("\n".join(md_lines), encoding="utf-8")

    policy_payload = {
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime()),
        "source": {
            "phase2_reevaluation_json": str(reeval_json),
            "phase2_reevaluation_md": str(reeval_md),
        },
        "active_baseline_policy": {
            "status": "current_adopted_baseline",
            "tiny_0p08": "edge_centroid",
            "mid_0p8": "edge_centroid",
            "macro_8px": "edge_centroid",
            "notes": "Round18 remains current adopted baseline until a hybrid policy clears the calibrated internal gate.",
        },
        "provisional_hybrid_policy": {
            "status": "not_confirmed",
            "round21_ready": bool(reevaluation_pass),
            "mid_0p8": "soft_band_refine",
            "macro_8px": str(macro_policy["macro_policy_estimator"]),
            "tiny_0p08": "edge_centroid",
            "mid_center_improvement_ratio": center_improvement_ratio,
            "mid_step_err": _safe_float(best_08["best_step_err"]),
            "macro_guard_pass": bool(macro_guard_pass),
            "blocked_reason": (
                ""
                if reevaluation_pass
                else "soft_band_refine has strong 0.8px center advantage, but the candidate still fails the calibrated Round21 gate."
            ),
        },
        "control_relative_guard": {
            "mid_0p8": {
                "center_improvement_ratio_min": 0.25,
                "step_err_max": 0.45,
            },
            "macro_8px": {
                "control_step_err": control_guard_step,
                "step_err_max": guard_step_limit,
                "control_seq_sign_acc": control_guard_seq_sign,
                "seq_sign_acc_min": guard_seq_sign_floor,
            },
        },
    }
    POLICY_PATH.write_text(json.dumps(policy_payload, indent=2), encoding="utf-8")

    if PHASE2_MANIFEST.exists():
        manifest = _load_json(PHASE2_MANIFEST)
        manifest["reevaluation_json"] = str(reeval_json)
        manifest["reevaluation_md"] = str(reeval_md)
        manifest["estimator_policy_json"] = str(POLICY_PATH)
        manifest["calibrated_decision"] = "confirmed" if reevaluation_pass else "not_confirmed"
        manifest["updated_at"] = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
        PHASE2_MANIFEST.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    print("[BRANCH_E_REEVALUATION] COMPLETED")
    print(str(reeval_md))
    print(str(POLICY_PATH))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

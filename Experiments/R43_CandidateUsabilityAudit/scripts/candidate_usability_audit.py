from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[3]
EXPERIMENT_ROOT = Path(__file__).resolve().parents[1]
RESULTS_DIR = EXPERIMENT_ROOT / "results" / "candidate_usability"
REPORT_PATH = EXPERIMENT_ROOT / "reports" / "R43A_USABILITY_AUDIT.md"

COMBO_EXTERNAL = {"8px": 0.154515, "0p8px": 0.131560, "0p08px": 0.099891}
COMBO_LOCAL = {"8px": 0.1389, "0p8px": 0.1509, "0p08px": 0.1185}
LOCAL_LIMIT_PCT = {"8px": 3.0, "0p8px": 7.0, "0p08px": 7.0}
EXTERNAL_LIMIT_PCT = {"8px": 3.0, "0p8px": 7.0, "0p08px": 7.0}


class Candidate:
    def __init__(
        self,
        *,
        candidate_id: str,
        display_name: str,
        source_round: str,
        role: str,
        external: dict[str, float] | None = None,
        local_ring: dict[str, float] | None = None,
        shape: dict[str, float] | None = None,
        micro: dict[str, float] | None = None,
        boundary: dict[str, float] | None = None,
        evidence: dict[str, str] | None = None,
        note: str = "",
    ) -> None:
        self.candidate_id = candidate_id
        self.display_name = display_name
        self.source_round = source_round
        self.role = role
        self.external = external or {}
        self.local_ring = local_ring or {}
        self.shape = shape or {}
        self.micro = micro or {}
        self.boundary = boundary or {}
        self.evidence = evidence or {}
        self.note = note


class GateStatus:
    def __init__(self, label: str, pass_gate: bool | None, deltas_pct: dict[str, float] | None = None) -> None:
        self.label = label
        self.pass_gate = pass_gate
        self.deltas_pct = deltas_pct or {}


class Classification:
    def __init__(self, category: str, recommended_use: str, reason: str) -> None:
        self.category = category
        self.recommended_use = recommended_use
        self.reason = reason


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _safe_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        value = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(value):
        return None
    return value


def _delta_pct(value: float, baseline: float) -> float:
    return 100.0 * (value - baseline) / baseline


def external_status(external: dict[str, float] | None) -> GateStatus:
    if not external:
        return GateStatus("NOT_SENT", None)
    deltas = {scale: _delta_pct(float(external[scale]), COMBO_EXTERNAL[scale]) for scale in COMBO_EXTERNAL if scale in external}
    if not deltas:
        return GateStatus("NOT_SENT", None)
    failed: list[str] = []
    for scale in ("8px", "0p8px", "0p08px"):
        if scale in deltas and deltas[scale] > EXTERNAL_LIMIT_PCT[scale]:
            label_scale = {"8px": "8PX", "0p8px": "0P8PX", "0p08px": "0P08PX"}[scale]
            failed.append(label_scale)
    if failed:
        return GateStatus(f"FAIL_{'_'.join(failed)}_REGRESSION", False, deltas)
    if any(delta < 0.0 for delta in deltas.values()) and any(delta > 0.0 for delta in deltas.values()):
        return GateStatus("PASS_TRADEOFF", True, deltas)
    return GateStatus("PASS", True, deltas)


def local_ring_status(local_ring: dict[str, float] | None) -> GateStatus:
    if not local_ring:
        return GateStatus("NOT_RUN", None)
    deltas = {scale: _delta_pct(float(local_ring[scale]), COMBO_LOCAL[scale]) for scale in COMBO_LOCAL if scale in local_ring}
    failed = [scale for scale, delta in deltas.items() if delta > LOCAL_LIMIT_PCT[scale]]
    if failed:
        return GateStatus("FAIL_" + "_".join(failed), False, deltas)
    return GateStatus("PASS", True, deltas)


def shape_gain(candidate: Candidate) -> bool:
    psnr = _safe_float(candidate.shape.get("psnr"))
    return psnr is not None and psnr >= 24.84


def micro_gain(candidate: Candidate) -> bool:
    psnr = _safe_float(candidate.micro.get("psnr"))
    hf = _safe_float(candidate.micro.get("hf"))
    return psnr is not None and hf is not None and psnr >= 26.0 and hf >= 0.30


def boundary_gain(candidate: Candidate) -> bool:
    psnr = _safe_float(candidate.boundary.get("psnr"))
    f1 = _safe_float(candidate.boundary.get("f1"))
    distance = _safe_float(candidate.boundary.get("distance"))
    return (
        psnr is not None
        and f1 is not None
        and distance is not None
        and psnr >= 30.0
        and f1 >= 0.85
        and distance <= 4.0
    )


def classify_candidate(candidate: Candidate) -> Classification:
    external = external_status(candidate.external)
    local = local_ring_status(candidate.local_ring)
    has_shape = shape_gain(candidate)
    has_micro = micro_gain(candidate)
    has_boundary = boundary_gain(candidate)

    if candidate.role == "formal_baseline":
        return Classification("formal_baseline", "正式 baseline", "目前最均衡，仍是正式預設。")
    if candidate.role == "approved_alternate":
        return Classification("approved_alternate", "已核准特化替代", "已經通過外部驗證，但用途比 COMBO 更特化。")
    if external.pass_gate is True and local.pass_gate is True and has_shape:
        return Classification(
            "alternate_grade",
            "可列入替代候選討論",
            "外部守門在可接受範圍內，且形狀泛化確實比 COMBO 好。",
        )
    if (has_boundary or has_micro) and local.pass_gate is False:
        return Classification(
            "specialist_research_use",
            "顯微重建研究或人工檢查用",
            "顯微能力明顯變好，但舊守門失敗，不能當正式量測替代。",
        )
    if has_micro or has_boundary or has_shape:
        return Classification(
            "capacity_source",
            "下一輪訓練或分析起點",
            "有明確能力增益，但缺少完整守門證據。",
        )
    if local.pass_gate is True:
        return Classification(
            "not_useful_tradeoff",
            "不建議使用",
            "守住舊能力，但新能力提升太小，沒有實際替換價值。",
        )
    return Classification("not_recommended", "不建議使用", "沒有形成清楚可用價值。")


def _bounded_gain(value: float | None, low: float, high: float) -> float:
    if value is None:
        return 0.0
    if high <= low:
        return 0.0
    return max(0.0, min(1.0, (value - low) / (high - low)))


def usability_score(candidate: Candidate) -> float:
    external = external_status(candidate.external)
    local = local_ring_status(candidate.local_ring)
    score = 0.0
    if candidate.role == "formal_baseline":
        score += 2.0
    elif candidate.role == "approved_alternate":
        score += 1.5
    if external.pass_gate is True:
        score += 4.0
    if local.pass_gate is True:
        score += 2.0
    score += 2.0 * _bounded_gain(_safe_float(candidate.shape.get("psnr")), 22.84, 30.0)
    score += 2.5 * _bounded_gain(_safe_float(candidate.micro.get("psnr")), 22.73, 30.0)
    score += 1.5 * _bounded_gain(_safe_float(candidate.micro.get("hf")), 0.22, 0.85)
    score += 3.0 * _bounded_gain(_safe_float(candidate.boundary.get("psnr")), 20.55, 34.2)
    score += 2.5 * _bounded_gain(_safe_float(candidate.boundary.get("f1")), 0.63, 0.87)
    distance = _safe_float(candidate.boundary.get("distance"))
    if distance is not None:
        score += 2.0 * _bounded_gain(7.82 - distance, 0.0, 4.5)
    return round(score, 4)


def _round_or_none(value: Any, ndigits: int = 4) -> float | None:
    value = _safe_float(value)
    if value is None:
        return None
    return round(value, ndigits)


def _pick_r39_row(tag: str) -> dict[str, Any]:
    sweep = read_json(REPO_ROOT / "Experiments" / "R39_ShapeGeneralization" / "results" / "weight_sweep" / "sweep_summary.json")
    for row in sweep["rows"]:
        if row["alpha_tag"] == tag:
            return row
    raise KeyError(tag)


def _pick_row(path: Path, tag: str) -> dict[str, Any]:
    sweep = read_json(path)
    for row in sweep["rows"]:
        if row["alpha_tag"] == tag:
            return row
    raise KeyError(tag)


def _micro_from_summary(path: Path) -> dict[str, float]:
    data = read_json(path)
    return {
        "psnr": float(data["overall_avg_psnr"]),
        "ssim": float(data.get("overall_avg_ssim", 0.0)),
        "hf": float(data["overall_high_frequency_retention"]),
        "edge": float(data.get("overall_edge_retention", 0.0)),
    }


def _boundary_from_summary(path: Path) -> dict[str, float]:
    data = read_json(path)
    return {
        "psnr": float(data["overall_avg_psnr"]),
        "hf": float(data["overall_hf_retention"]),
        "distance": float(data["overall_boundary_distance_px"]),
        "f1": float(data["overall_boundary_fscore_t1p0"]),
    }


def _ring_from_summary(path: Path, prefix: str | None = None) -> dict[str, float]:
    data = read_json(path)
    if "datasets" in data:
        out: dict[str, float] = {}
        for row in data["datasets"]:
            if row["short_name"] == "pitch1um_y_100":
                out["8px"] = float(row.get(f"{prefix}_internal_step_std_y" if prefix else "r42_internal_step_std_y"))
            elif row["short_name"] == "pitch0p1um_y_60":
                out["0p8px"] = float(row.get(f"{prefix}_internal_step_std_y" if prefix else "r42_internal_step_std_y"))
            elif row["short_name"] == "pitch0p01um_y_40":
                out["0p08px"] = float(row.get(f"{prefix}_internal_step_std_y" if prefix else "r42_internal_step_std_y"))
        return out
    return {}


def _policy_external(metrics: dict[str, Any]) -> dict[str, float]:
    if "8px" in metrics:
        return {"8px": float(metrics["8px"]), "0p8px": float(metrics["0p8px"]), "0p08px": float(metrics["0p08px"])}
    return {
        "8px": float(metrics["step_std_8px"]),
        "0p8px": float(metrics["step_std_0p8px"]),
        "0p08px": float(metrics["step_std_0p08px"]),
    }


def _optional_r42_external(tag: str) -> dict[str, float] | None:
    path = (
        REPO_ROOT
        / "Experiments"
        / "R42_MicroscopyBoundaryFidelity"
        / "results"
        / "external_gmf"
        / tag
        / "external_compare_summary.json"
    )
    if not path.exists():
        return None
    return read_json(path)["headline_step_std"]


def build_candidates() -> list[Candidate]:
    policy = read_json(REPO_ROOT / "ESTIMATOR_POLICY.json")
    r39_a030 = _pick_r39_row("a030")
    r40_a045 = _pick_row(
        REPO_ROOT / "Experiments" / "R40_MicroscopyFeatureCoverage" / "results" / "weight_sweep" / "combo_best_low_alpha" / "sweep_summary.json",
        "a045",
    )
    r41_a045 = _pick_row(
        REPO_ROOT / "Experiments" / "R41_RingDistillation" / "results" / "weight_sweep_ext_high_alpha" / "sweep_summary.json",
        "a045",
    )
    r41_a050 = _pick_row(
        REPO_ROOT / "Experiments" / "R41_RingDistillation" / "results" / "weight_sweep_ext_high_alpha" / "sweep_summary.json",
        "a050",
    )
    r42_low = read_json(
        REPO_ROOT / "Experiments" / "R42_MicroscopyBoundaryFidelity" / "results" / "weight_sweep" / "r42_r41_best_lowalpha" / "sweep_summary.json"
    )
    r42_low_rows = {row["alpha_tag"]: row for row in r42_low["rows"]}

    combo_boundary = _boundary_from_summary(
        REPO_ROOT / "Experiments" / "R42_MicroscopyBoundaryFidelity" / "results" / "boundary_recon" / "combo" / "summary.json"
    )
    candidates = [
        Candidate(
            candidate_id="COMBO",
            display_name="COMBO",
            source_round="COMBO",
            role="formal_baseline",
            external=_policy_external(policy["formal_baseline"]["external_gmf"]),
            local_ring=COMBO_LOCAL,
            shape={"psnr": 22.8411, "ssim": 0.8502},
            micro=_micro_from_summary(
                REPO_ROOT / "Experiments" / "R40_MicroscopyFeatureCoverage" / "results" / "micro_recon" / "combo_micro_summary.json"
            ),
            boundary=combo_boundary,
            evidence={"report": "Experiments/R38v2SeqFixed/reports/COMBO_RESULTS.md"},
        ),
        Candidate(
            candidate_id="R33",
            display_name="R33 robust p95",
            source_round="R33",
            role="approved_alternate",
            external=_policy_external(policy["approved_alternates"][0]["external_gmf"]),
            evidence={"report": "Experiments/R33RobustLoss/reports/R33_EXPERIMENT_SUMMARY.md"},
            note="GMF 極致型，視覺較軟。",
        ),
        Candidate(
            candidate_id="R38v2",
            display_name="R38v2 8px gate",
            source_round="R38v2",
            role="approved_alternate",
            external=_policy_external(policy["approved_alternates"][1]["external_gmf"]),
            evidence={"report": "Experiments/R38v2SeqFixed/reports/R38v2_RESULTS.md"},
            note="視覺優先型已核准替代。",
        ),
        Candidate(
            candidate_id="R39_a030",
            display_name="R39 a030",
            source_round="R39",
            role="shape_generalization",
            external=read_json(
                REPO_ROOT / "Experiments" / "R39_ShapeGeneralization" / "results" / "external_gmf_a030" / "external_compare_summary.json"
            )["headline_step_std"],
            local_ring={
                "8px": r39_a030["ring_8px_step_std"],
                "0p8px": r39_a030["ring_0p8px_step_std"],
                "0p08px": r39_a030["ring_0p08px_step_std"],
            },
            shape={"psnr": r39_a030["shape_overall_psnr"], "ssim": r39_a030["shape_overall_ssim"]},
            micro=_micro_from_summary(
                REPO_ROOT / "Experiments" / "R40_MicroscopyFeatureCoverage" / "results" / "micro_recon" / "a030_micro_summary.json"
            ),
            boundary=_boundary_from_summary(
                REPO_ROOT / "Experiments" / "R42_MicroscopyBoundaryFidelity" / "results" / "boundary_recon" / "r39_a030" / "summary.json"
            ),
            evidence={"report": "Experiments/R39_ShapeGeneralization/reports/R39_RESULTS.md"},
        ),
        Candidate(
            candidate_id="R40_a045",
            display_name="R40 a045",
            source_round="R40",
            role="micro_feature_tradeoff",
            external=read_json(
                REPO_ROOT / "Experiments" / "R40_MicroscopyFeatureCoverage" / "results" / "external_gmf" / "external_compare_summary.json"
            )["headline_step_std"],
            local_ring={
                "8px": r40_a045["ring_8px_step_std"],
                "0p8px": r40_a045["ring_0p8px_step_std"],
                "0p08px": r40_a045["ring_0p08px_step_std"],
            },
            micro={
                "psnr": r40_a045["micro_overall_psnr"],
                "ssim": r40_a045["micro_overall_ssim"],
                "hf": r40_a045["micro_high_frequency_retention"],
                "edge": r40_a045["micro_edge_retention"],
            },
            boundary=_boundary_from_summary(
                REPO_ROOT / "Experiments" / "R42_MicroscopyBoundaryFidelity" / "results" / "boundary_recon" / "r40_a045" / "summary.json"
            ),
            evidence={"report": "Experiments/R40_MicroscopyFeatureCoverage/reports/R40_RESULTS.md"},
        ),
        Candidate(
            candidate_id="R41_direct",
            display_name="R41 direct",
            source_round="R41",
            role="micro_feature_endpoint",
            local_ring=_ring_from_summary(
                REPO_ROOT / "Experiments" / "R41_RingDistillation" / "results" / "ring_guard" / "r41_kd_from_a045_best_ring_guard_summary.json",
                prefix="r41",
            ),
            micro=_micro_from_summary(
                REPO_ROOT / "Experiments" / "R41_RingDistillation" / "results" / "micro_recon" / "r41_kd_from_a045_best_summary.json"
            ),
            boundary=_boundary_from_summary(
                REPO_ROOT / "Experiments" / "R42_MicroscopyBoundaryFidelity" / "results" / "boundary_recon" / "r41_direct" / "summary.json"
            ),
            evidence={"report": "Experiments/R41_RingDistillation/reports/R41_RESULTS.md"},
        ),
        Candidate(
            candidate_id="R41_a045",
            display_name="R41 a045",
            source_round="R41",
            role="micro_feature_avg",
            local_ring={"8px": r41_a045["ring_8px_step_std"], "0p8px": r41_a045["ring_0p8px_step_std"], "0p08px": r41_a045["ring_0p08px_step_std"]},
            micro={"psnr": r41_a045["micro_overall_psnr"], "ssim": r41_a045["micro_overall_ssim"], "hf": r41_a045["micro_high_frequency_retention"], "edge": r41_a045["micro_edge_retention"]},
            evidence={"report": "Experiments/R41_RingDistillation/reports/R41_RESULTS.md"},
        ),
        Candidate(
            candidate_id="R41_a050",
            display_name="R41 a050",
            source_round="R41",
            role="micro_feature_avg",
            local_ring={"8px": r41_a050["ring_8px_step_std"], "0p8px": r41_a050["ring_0p8px_step_std"], "0p08px": r41_a050["ring_0p08px_step_std"]},
            micro={"psnr": r41_a050["micro_overall_psnr"], "ssim": r41_a050["micro_overall_ssim"], "hf": r41_a050["micro_high_frequency_retention"], "edge": r41_a050["micro_edge_retention"]},
            evidence={"report": "Experiments/R41_RingDistillation/reports/R41_RESULTS.md"},
        ),
    ]

    for tag, name in [
        ("r42_combo_best", "R42 combo best"),
        ("r42_combo_latest", "R42 combo latest"),
        ("r42_r41_best", "R42 r41 best"),
        ("r42_r41_latest", "R42 r41 latest"),
    ]:
        candidates.append(
            Candidate(
                candidate_id=tag.upper(),
                display_name=name,
                source_round="R42",
                role="boundary_specialist",
                external=_optional_r42_external(tag),
                local_ring=_ring_from_summary(
                    REPO_ROOT / "Experiments" / "R42_MicroscopyBoundaryFidelity" / "results" / "ring_guard" / f"{tag}_ring_guard_summary.json"
                ),
                boundary=_boundary_from_summary(
                    REPO_ROOT / "Experiments" / "R42_MicroscopyBoundaryFidelity" / "results" / "boundary_recon" / tag / "summary.json"
                ),
                evidence={"report": "Experiments/R42_MicroscopyBoundaryFidelity/reports/R42_RESULTS.md"},
            )
        )

    for tag in ("a001", "a002", "a003", "a005"):
        row = r42_low_rows[tag]
        candidates.append(
            Candidate(
                candidate_id=f"R42_low_{tag}",
                display_name=f"R42 low alpha {tag}",
                source_round="R42",
                role="low_alpha_probe",
                local_ring={"8px": row["ring_8px_step_std"], "0p8px": row["ring_0p8px_step_std"], "0p08px": row["ring_0p08px_step_std"]},
                boundary={
                    "psnr": row["boundary_overall_psnr"],
                    "hf": row["boundary_high_frequency_retention"],
                    "distance": row["boundary_distance_px"],
                    "f1": row["boundary_fscore_t1p0"],
                },
                evidence={"report": "Experiments/R42_MicroscopyBoundaryFidelity/reports/R42_RESULTS.md"},
            )
        )

    candidates.append(
        Candidate(
            candidate_id="R42_guarded_kd_probe",
            display_name="R42 guarded KD probe",
            source_round="R42",
            role="boundary_specialist",
            local_ring=_ring_from_summary(
                REPO_ROOT
                / "Experiments"
                / "R42_MicroscopyBoundaryFidelity"
                / "results"
                / "ring_guard_guarded_kd_probe"
                / "r42_guarded_kd_probe_latest_ring_guard_summary.json"
            ),
            boundary=_boundary_from_summary(
                REPO_ROOT
                / "Experiments"
                / "R42_MicroscopyBoundaryFidelity"
                / "results"
                / "boundary_recon_guarded_kd_probe"
                / "r42_guarded_kd_probe_latest_summary.json"
            ),
            evidence={"report": "Experiments/R42_MicroscopyBoundaryFidelity/reports/R42_RESULTS.md"},
        )
    )
    return candidates


def candidate_row(candidate: Candidate) -> dict[str, Any]:
    ext = external_status(candidate.external)
    local = local_ring_status(candidate.local_ring)
    cls = classify_candidate(candidate)
    return {
        "candidate_id": candidate.candidate_id,
        "display_name": candidate.display_name,
        "source_round": candidate.source_round,
        "category": cls.category,
        "recommended_use": cls.recommended_use,
        "reason": cls.reason,
        "score": usability_score(candidate),
        "external_status": ext.label,
        "local_ring_status": local.label,
        "external_8px": _round_or_none(candidate.external.get("8px"), 6),
        "external_0p8px": _round_or_none(candidate.external.get("0p8px"), 6),
        "external_0p08px": _round_or_none(candidate.external.get("0p08px"), 6),
        "local_8px": _round_or_none(candidate.local_ring.get("8px"), 4),
        "local_0p8px": _round_or_none(candidate.local_ring.get("0p8px"), 4),
        "local_0p08px": _round_or_none(candidate.local_ring.get("0p08px"), 4),
        "shape_psnr": _round_or_none(candidate.shape.get("psnr"), 4),
        "micro_psnr": _round_or_none(candidate.micro.get("psnr"), 4),
        "micro_hf": _round_or_none(candidate.micro.get("hf"), 4),
        "boundary_psnr": _round_or_none(candidate.boundary.get("psnr"), 4),
        "boundary_hf": _round_or_none(candidate.boundary.get("hf"), 4),
        "boundary_distance": _round_or_none(candidate.boundary.get("distance"), 4),
        "boundary_f1": _round_or_none(candidate.boundary.get("f1"), 4),
        "note": candidate.note,
        "evidence": candidate.evidence,
    }


def _fmt(value: Any) -> str:
    if value is None:
        return "—"
    if isinstance(value, float):
        return f"{value:.4f}"
    return str(value)


def _delta_text(value: float | None, baseline: float) -> str:
    if value is None:
        return "—"
    return f"{_delta_pct(value, baseline):+.1f}%"


def write_json_csv(rows: list[dict[str, Any]], out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "usability_scorecard.json").write_text(json.dumps(rows, indent=2, ensure_ascii=False), encoding="utf-8")
    flat_rows = []
    for row in rows:
        flat = dict(row)
        flat["evidence"] = "; ".join(f"{k}={v}" for k, v in row.get("evidence", {}).items())
        flat_rows.append(flat)
    with (out_dir / "usability_scorecard.csv").open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(flat_rows[0]))
        writer.writeheader()
        writer.writerows(flat_rows)


def _best(rows: list[dict[str, Any]], key: str, *, reverse: bool = True) -> dict[str, Any] | None:
    valid = [row for row in rows if row.get(key) is not None]
    if not valid:
        return None
    return sorted(valid, key=lambda row: row[key], reverse=reverse)[0]


def write_report(rows: list[dict[str, Any]], report_path: Path) -> None:
    report_path.parent.mkdir(parents=True, exist_ok=True)
    top_score = sorted(rows, key=lambda row: row["score"], reverse=True)[:8]
    external_rows = [row for row in rows if row["external_status"] != "NOT_SENT"]
    specialist_rows = [row for row in rows if row["category"] == "specialist_research_use"]
    not_useful_rows = [row for row in rows if row["category"] in {"not_useful_tradeoff", "not_recommended"}]

    best_shape = _best(rows, "shape_psnr")
    best_micro = _best(rows, "micro_psnr")
    best_boundary = _best(rows, "boundary_psnr")
    best_boundary_dist = _best(rows, "boundary_distance", reverse=False)

    lines: list[str] = []
    lines.append("# R43A Usability Audit — 近期候選堪用性分析")
    lines.append("")
    lines.append("## 摘要")
    lines.append("")
    lines.append("這份分析把 COMBO、已核准替代、R39、R40、R41、R42 的主要候選放到同一張表。目的不是重新訓練，而是回答一個實務問題：近期模型到底有沒有哪一些已經堪用。")
    lines.append("")
    lines.append("結論很直接：**沒有任何新候選可以全面取代 COMBO；但不是全部都不能用。R39 a030 是目前最接近正式替代討論的候選，R40/R41/R42 則是顯微特徵與邊界重建的研究材料。**")
    lines.append("")
    lines.append("2026-05-06 補上 R42 外部 GMF 後，R42 最好的外部候選仍在三個尺度都明顯退步：8px `+24.6%`、0.8px `+94.3%`、0.08px `+98.9%`。所以 R42 可以拿來看顯微邊界能力，但不適合拿去做正式量測。")
    lines.append("")
    lines.append("## 完成標準")
    lines.append("")
    lines.append("- 正式替代：外部三尺度守門不能明顯輸 COMBO。")
    lines.append("- 顯微堪用：格線、缺陷、邊界或高頻細節要明顯比 COMBO 好。")
    lines.append("- 實驗起點：即使不能部署，也要提供清楚能力來源。")
    lines.append("- 不堪用：守住舊能力但沒有新能力，或新能力變好但失去太多舊守門且沒有明確用途。")
    lines.append("")
    lines.append("## 核心排名")
    lines.append("")
    lines.append("| Rank | 候選 | 類別 | 建議用途 | score | 判讀 |")
    lines.append("|---:|---|---|---|---:|---|")
    for idx, row in enumerate(top_score, 1):
        lines.append(
            f"| {idx} | `{row['display_name']}` | {row['category']} | {row['recommended_use']} | {row['score']:.2f} | {row['reason']} |"
        )
    lines.append("")
    lines.append("分數只是排序輔助，不是升級標準。升級仍以正式外部守門為準。")
    lines.append("")
    lines.append("## 正式替代視角")
    lines.append("")
    lines.append("| 候選 | external 8px | vs COMBO | external 0.8px | vs COMBO | external 0.08px | vs COMBO | 判讀 |")
    lines.append("|---|---:|---:|---:|---:|---:|---:|---|")
    for row in external_rows:
        lines.append(
            "| "
            + f"`{row['display_name']}` | "
            + f"{_fmt(row['external_8px'])} | {_delta_text(row['external_8px'], COMBO_EXTERNAL['8px'])} | "
            + f"{_fmt(row['external_0p8px'])} | {_delta_text(row['external_0p8px'], COMBO_EXTERNAL['0p8px'])} | "
            + f"{_fmt(row['external_0p08px'])} | {_delta_text(row['external_0p08px'], COMBO_EXTERNAL['0p08px'])} | "
            + f"{row['external_status']} |"
        )
    lines.append("")
    lines.append("正式替代面最有價值的是 `R39 a030`。它不是完美：0.8px 比 COMBO 退步約 6.4%。但它 8px 與 0.08px 都比 COMBO 好，而且外部結果在替代候選容忍帶內。R40 a045 的顯微能力雖然好，外部 8px 退步太大；R42 補測後確認三尺度都退步，不能當正式替代。")
    lines.append("")
    lines.append("## 顯微與邊界能力")
    lines.append("")
    lines.append("| 候選 | shape PSNR | micro PSNR | micro HF | boundary PSNR | boundary dist | boundary F1 | local ring | 建議用途 |")
    lines.append("|---|---:|---:|---:|---:|---:|---:|---|---|")
    for row in rows:
        if row["shape_psnr"] is None and row["micro_psnr"] is None and row["boundary_psnr"] is None:
            continue
        lines.append(
            "| "
            + f"`{row['display_name']}` | {_fmt(row['shape_psnr'])} | {_fmt(row['micro_psnr'])} | {_fmt(row['micro_hf'])} | "
            + f"{_fmt(row['boundary_psnr'])} | {_fmt(row['boundary_distance'])} | {_fmt(row['boundary_f1'])} | "
            + f"{row['local_ring_status']} | {row['recommended_use']} |"
        )
    lines.append("")
    if best_shape:
        lines.append(f"- 形狀泛化最好的是 `{best_shape['display_name']}`，shape PSNR `{best_shape['shape_psnr']}`。")
    if best_micro:
        lines.append(f"- R40/R41 顯微特徵測試中，最高 micro PSNR 是 `{best_micro['display_name']}`，micro PSNR `{best_micro['micro_psnr']}`。")
    if best_boundary and best_boundary_dist:
        lines.append(f"- R42 邊界測試中，最高 boundary PSNR 是 `{best_boundary['display_name']}`；邊界位置最穩的是 `{best_boundary_dist['display_name']}`，距離 `{best_boundary_dist['boundary_distance']}` px。")
    lines.append("")
    lines.append("## 堪用性判斷")
    lines.append("")
    lines.append("### 可以拿來正式討論")
    lines.append("")
    lines.append("- `R39 a030`：目前最像「可升級替代」的近期候選。適合想要形狀泛化，同時重視 8px 與 0.08px 的場景；如果主戰場是 0.8px，仍應優先用 COMBO 或 R33。")
    lines.append("")
    lines.append("### 可以拿來顯微研究或人工檢查")
    lines.append("")
    for row in specialist_rows:
        lines.append(f"- `{row['display_name']}`：{row['reason']}")
    lines.append("")
    lines.append("這些候選不是不能用，而是不能拿來直接取代正式量測流程。它們比較適合作為顯微結構重建、人工檢查、下一輪訓練起點。")
    lines.append("")
    lines.append("## 肉眼檢查圖")
    lines.append("")
    lines.append("R43 另外整理了三張代表圖，方便直接比較顯微特徵和邊界重建質感。")
    lines.append("")
    lines.append("- 顯微特徵總覽：`Experiments/R43_CandidateUsabilityAudit/results/visual_review/micro_feature_visual_sheet.png`")
    lines.append("- 邊界特徵總覽：`Experiments/R43_CandidateUsabilityAudit/results/visual_review/boundary_feature_visual_sheet.png`")
    lines.append("- 邊界局部放大：`Experiments/R43_CandidateUsabilityAudit/results/visual_review/boundary_zoom_visual_sheet.png`")
    lines.append("")
    lines.append("肉眼判讀和數字一致：R42 的邊界、缺陷和局部細節最清楚，但連續量測穩定性不足；R40/R41 比 COMBO 更有顯微細節能力，但還不夠穩；R39 a030 是目前最平衡的近期候選。")
    lines.append("")
    lines.append("### 暫時不值得用")
    lines.append("")
    for row in not_useful_rows:
        lines.append(f"- `{row['display_name']}`：{row['reason']}")
    lines.append("")
    lines.append("低比例混合版特別值得注意：它們接近守住舊環形，但顯微邊界能力幾乎還停在 COMBO 附近，所以不是好折衷。")
    lines.append("")
    lines.append("## 深層判讀")
    lines.append("")
    lines.append("R39 到 R42 的共同現象是：模型不是沒有能力重建顯微結構，而是能力被推高時，舊的連續量測守門會掉。這代表問題不只是「影像清不清楚」，而是「同一個結構在連續位移時，輸出位置有沒有跟著真實位置穩定移動」。")
    lines.append("")
    lines.append("因此，下一步不應再只做更多資料混合、低 alpha 平均或靜態老師牽引。更該做的是已知位移測試：同一條線、同一組格線、同一個缺陷，在 0.08px、0.8px、8px 或其他小位移下，模型輸出的邊界位置是否同步移動。這會比單張 PSNR 或單張 boundary F1 更接近你真正關心的能力。")
    lines.append("")
    lines.append("## 結論")
    lines.append("")
    lines.append("- **正式預設仍是 COMBO。**")
    lines.append("- **最堪用的近期替代候選是 R39 a030。** 它可以進入 owner 決策，但不是無條件取代 COMBO。")
    lines.append("- **顯微重建最有價值的是 R42 full endpoints。** 它們對邊界、格線、缺陷的能力是真實的，但外部補測後確認不適合直接進正式量測。")
    lines.append("- **R40/R41 是能力來源。** 它們證明顯微細節可以被學到，但目前不該部署。")
    lines.append("- **低 alpha 折衷目前沒有價值。** 它守住舊能力的同時，也幾乎放棄了新能力。")
    lines.append("")
    lines.append("## 產物")
    lines.append("")
    lines.append("- JSON scorecard：`Experiments/R43_CandidateUsabilityAudit/results/candidate_usability/usability_scorecard.json`")
    lines.append("- CSV scorecard：`Experiments/R43_CandidateUsabilityAudit/results/candidate_usability/usability_scorecard.csv`")
    lines.append("- 視覺檢查圖：`Experiments/R43_CandidateUsabilityAudit/results/visual_review/`")
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run(output_dir: Path = RESULTS_DIR, report_path: Path = REPORT_PATH) -> list[dict[str, Any]]:
    candidates = build_candidates()
    rows = [candidate_row(candidate) for candidate in candidates]
    rows.sort(key=lambda row: row["score"], reverse=True)
    write_json_csv(rows, output_dir)
    write_report(rows, report_path)
    return rows


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build R43A candidate usability scorecard.")
    parser.add_argument("--output-dir", type=Path, default=RESULTS_DIR)
    parser.add_argument("--report", type=Path, default=REPORT_PATH)
    args = parser.parse_args(argv)
    rows = run(args.output_dir, args.report)
    print(json.dumps({"count": len(rows), "report": str(args.report), "output_dir": str(args.output_dir)}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

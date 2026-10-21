"""R44H Step 0/Step A：R44B 家族權重平均與乾淨度整理工具。"""
from __future__ import annotations

import argparse
import csv
import json
import math
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import torch


REPO_ROOT = Path(__file__).resolve().parents[3]
EXPERIMENT_ROOT = REPO_ROOT / "Experiments" / "R44_UniversalBoundaryMotionFidelity"
RESULT_ROOT = EXPERIMENT_ROOT / "results" / "r44h_family_average"
DEFAULT_CHECKPOINT_ROOT = RESULT_ROOT / "checkpoints"
DEFAULT_REPORT = EXPERIMENT_ROOT / "reports" / "R44H_STEPA_FAMILY_AVERAGE.md"
DEFAULT_DIAGNOSTIC_ROOT = EXPERIMENT_ROOT / "results" / "diagnostics"
DEFAULT_MOTION_RECON_ROOT = EXPERIMENT_ROOT / "results" / "motion_recon"
DEFAULT_RING_GUARD_ROOT = EXPERIMENT_ROOT / "results" / "ring_guard"

R44B_R42_CHECKPOINT = (
    REPO_ROOT
    / "Experiments"
    / "R44_UniversalBoundaryMotionFidelity"
    / "results"
    / "archive_retained_20260824"
    / "training_checkpoints"
    / "training_progress_GESR_v1_v5_ST0p8_SWP_r44_motion_from_r42_best_20260506_201801"
    / "best_tradeoff.pth.tar"
)
R44B_R40_CHECKPOINT = (
    REPO_ROOT
    / "Experiments"
    / "R44_UniversalBoundaryMotionFidelity"
    / "results"
    / "archive_retained_20260824"
    / "training_checkpoints"
    / "training_progress_GESR_v1_v5_ST0p8_SWP_r44_motion_from_r40_a045_20260506_203143"
    / "best_tradeoff.pth.tar"
)
R44B_COMBO_CHECKPOINT = (
    REPO_ROOT
    / "Experiments"
    / "R44_UniversalBoundaryMotionFidelity"
    / "results"
    / "archive_retained_20260824"
    / "training_checkpoints"
    / "training_progress_GESR_v1_v5_ST0p8_SWP_r44_motion_from_combo_20260506_204231"
    / "best_tradeoff.pth.tar"
)

SOURCE_CHECKPOINTS: dict[str, Path] = {
    "r44b_r42": R44B_R42_CHECKPOINT,
    "r44b_r40": R44B_R40_CHECKPOINT,
    "r44b_combo": R44B_COMBO_CHECKPOINT,
}

SOURCE_RECON_FOLDERS: dict[str, str] = {
    "R44B from R42": "r44_motion_from_r42_best_e24",
    "R44B from R40": "r44_motion_from_r40_a045_e24",
    "R44B from COMBO": "r44_motion_from_combo_e24",
    "R44C static heavy": "r44c_static_heavy_all_motion",
}

STEPA_CANDIDATES: dict[str, dict[str, float]] = {
    "r44h_b42_bcombo_a050": {"r44b_r42": 0.50, "r44b_combo": 0.50},
    "r44h_b42_b40_a030": {"r44b_r42": 0.70, "r44b_r40": 0.30},
    "r44h_b42_bcombo_a030": {"r44b_r42": 0.70, "r44b_combo": 0.30},
    "r44h_b42_b40_bcombo_050_025_025": {
        "r44b_r42": 0.50,
        "r44b_r40": 0.25,
        "r44b_combo": 0.25,
    },
}


def build_r44h_model_map() -> dict[str, str]:
    model_map = dict(SOURCE_RECON_FOLDERS)
    for candidate_id in STEPA_CANDIDATES:
        model_map[f"R44H {candidate_id}"] = candidate_id
    return model_map


@dataclass(frozen=True)
class StepAReferences:
    r44b_r42_target_shape_error: float = 0.3384
    r44b_r42_motion_error_px: float = 0.3813
    r44b_r40_target_shape_error: float = 0.3110
    motion_regression_cap_pct: float = 10.0
    weak_shape_improvement_pct: float = 3.0


def _clean_state_key(key: str) -> str:
    return key.replace("module.", "", 1) if key.startswith("module.") else key


def load_state_dict(path: Path) -> dict[str, torch.Tensor]:
    obj = torch.load(path, map_location="cpu", weights_only=False)
    sd = obj["state_dict"] if isinstance(obj, dict) and "state_dict" in obj else obj
    if not isinstance(sd, dict):
        raise TypeError(f"unexpected checkpoint contents: {type(sd)}")
    return {_clean_state_key(str(key)): value for key, value in sd.items()}


def validate_state_dicts_compatible(state_dicts: list[dict[str, torch.Tensor]]) -> None:
    if not state_dicts:
        raise ValueError("at least one state_dict is required")
    first_keys = set(state_dicts[0].keys())
    for idx, sd in enumerate(state_dicts[1:], start=1):
        if set(sd.keys()) != first_keys:
            missing = sorted(first_keys - set(sd.keys()))[:5]
            extra = sorted(set(sd.keys()) - first_keys)[:5]
            raise ValueError(f"state_dict keys differ at index {idx}; missing={missing}; extra={extra}")
        for key in first_keys:
            if tuple(sd[key].shape) != tuple(state_dicts[0][key].shape):
                raise ValueError(f"state_dict tensor shape differs for {key}: {tuple(state_dicts[0][key].shape)} vs {tuple(sd[key].shape)}")


def _normalize_weights(weights: Iterable[float]) -> list[float]:
    vals = [float(w) for w in weights]
    total = sum(vals)
    if total <= 0:
        raise ValueError("weights must sum to a positive value")
    return [w / total for w in vals]


def weighted_average_state_dicts(
    state_dicts: list[dict[str, torch.Tensor]],
    weights: list[float],
) -> dict[str, torch.Tensor]:
    if len(state_dicts) != len(weights):
        raise ValueError("state_dicts and weights length mismatch")
    validate_state_dicts_compatible(state_dicts)
    norm_weights = _normalize_weights(weights)
    primary = state_dicts[0]
    out: dict[str, torch.Tensor] = {}
    for key in primary:
        base = primary[key]
        if torch.is_floating_point(base):
            acc = torch.zeros_like(base, dtype=torch.float32)
            for sd, weight in zip(state_dicts, norm_weights):
                acc = acc + sd[key].detach().to(dtype=torch.float32) * float(weight)
            out[key] = acc.to(dtype=base.dtype).clone()
        else:
            out[key] = base.detach().clone()
    return out


def save_state_dict_checkpoint(
    state_dict: dict[str, torch.Tensor],
    path: Path,
    *,
    candidate_id: str,
    source_weights: dict[str, float],
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    torch.save(
        {
            "state_dict": state_dict,
            "r44h_family_average": {
                "candidate_id": candidate_id,
                "source_weights": source_weights,
                "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            },
        },
        path,
    )


def build_candidate_checkpoints(
    *,
    checkpoint_root: Path = DEFAULT_CHECKPOINT_ROOT,
    candidates: dict[str, dict[str, float]] | None = None,
    source_paths: dict[str, Path] | None = None,
    skip_existing: bool = False,
) -> list[dict]:
    candidates = candidates or STEPA_CANDIDATES
    source_paths = source_paths or SOURCE_CHECKPOINTS
    loaded: dict[str, dict[str, torch.Tensor]] = {}
    rows = []
    for candidate_id, source_weights in candidates.items():
        output_path = checkpoint_root / candidate_id / "best_tradeoff.pth.tar"
        if output_path.exists() and skip_existing:
            rows.append(
                {
                    "candidate_id": candidate_id,
                    "checkpoint_path": str(output_path),
                    "source_weights": source_weights,
                    "status": "existing",
                }
            )
            continue
        ordered_sources = list(source_weights.keys())
        for source_id in ordered_sources:
            if source_id not in loaded:
                loaded[source_id] = load_state_dict(source_paths[source_id])
        averaged = weighted_average_state_dicts(
            [loaded[source_id] for source_id in ordered_sources],
            [source_weights[source_id] for source_id in ordered_sources],
        )
        save_state_dict_checkpoint(
            averaged,
            output_path,
            candidate_id=candidate_id,
            source_weights=source_weights,
        )
        rows.append(
            {
                "candidate_id": candidate_id,
                "checkpoint_path": str(output_path),
                "source_weights": source_weights,
                "status": "created",
            }
        )
    return rows


def _safe_float(value: object) -> float:
    try:
        out = float(str(value).strip())
    except (TypeError, ValueError):
        return float("nan")
    return out


def _mean(values: Iterable[float]) -> float:
    vals = [float(v) for v in values if math.isfinite(float(v))]
    return sum(vals) / len(vals) if vals else float("nan")


def _read_csv_rows(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def _write_csv(rows: list[dict], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8-sig")
        return
    fields = sorted({key for row in rows for key in row})
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def _json_safe(value):
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, dict):
        return {key: _json_safe(val) for key, val in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    return value


def _write_json(payload: dict, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(_json_safe(payload), ensure_ascii=False, indent=2), encoding="utf-8")


def _row_for(rows: list[dict], *, model: str, family: str | None = None) -> dict | None:
    for row in rows:
        if row.get("model") != model:
            continue
        if family is not None and row.get("feature_family") != family:
            continue
        return row
    return None


def assess_r44c_cleanliness(
    *,
    motion_family_rows: list[dict],
    target_shape_rows: list[dict],
    shape_score_rows: list[dict],
    reference_model: str = "R44B from R42",
    teacher_model: str = "R44C static heavy",
    motion_regression_cap_pct: float = 10.0,
) -> dict:
    ref_shape = _row_for(target_shape_rows, model=reference_model)
    teacher_shape = _row_for(target_shape_rows, model=teacher_model)
    ref_mixed = _row_for(shape_score_rows, model=reference_model, family="mixed_fields")
    teacher_mixed = _row_for(shape_score_rows, model=teacher_model, family="mixed_fields")

    motion_regressions = []
    for family in ("grids", "mixed_fields"):
        ref_motion = _row_for(motion_family_rows, model=reference_model, family=family)
        teacher_motion = _row_for(motion_family_rows, model=teacher_model, family=family)
        if not ref_motion or not teacher_motion:
            continue
        ref_val = _safe_float(ref_motion.get("avg_motion_vector_error_px"))
        teacher_val = _safe_float(teacher_motion.get("avg_motion_vector_error_px"))
        if math.isfinite(ref_val) and ref_val > 0 and math.isfinite(teacher_val):
            motion_regressions.append(
                {
                    "feature_family": family,
                    "reference_motion_px": ref_val,
                    "teacher_motion_px": teacher_val,
                    "regression_pct": 100.0 * (teacher_val - ref_val) / ref_val,
                }
            )
    max_motion_regression_pct = max((r["regression_pct"] for r in motion_regressions), default=float("nan"))

    ref_target_shape = _safe_float(ref_shape.get("target_shape_error_score")) if ref_shape else float("nan")
    teacher_target_shape = _safe_float(teacher_shape.get("target_shape_error_score")) if teacher_shape else float("nan")
    ref_mixed_shape = _safe_float(ref_mixed.get("avg_shape_error_score")) if ref_mixed else float("nan")
    teacher_mixed_shape = _safe_float(teacher_mixed.get("avg_shape_error_score")) if teacher_mixed else float("nan")

    mixed_shape_improved = math.isfinite(ref_mixed_shape) and math.isfinite(teacher_mixed_shape) and teacher_mixed_shape < ref_mixed_shape
    target_shape_not_worse = (
        math.isfinite(ref_target_shape)
        and math.isfinite(teacher_target_shape)
        and teacher_target_shape <= ref_target_shape * 1.02
    )
    motion_clean = math.isfinite(max_motion_regression_pct) and max_motion_regression_pct <= motion_regression_cap_pct

    return {
        "reference_model": reference_model,
        "teacher_model": teacher_model,
        "clean_enough_for_mixed_teacher": bool(mixed_shape_improved and target_shape_not_worse and motion_clean),
        "mixed_shape_improved": bool(mixed_shape_improved),
        "target_shape_not_worse_within_2pct": bool(target_shape_not_worse),
        "motion_clean_within_cap": bool(motion_clean),
        "motion_regression_cap_pct": float(motion_regression_cap_pct),
        "max_motion_regression_pct": float(max_motion_regression_pct),
        "reference_target_shape_error": float(ref_target_shape),
        "teacher_target_shape_error": float(teacher_target_shape),
        "reference_mixed_shape_error": float(ref_mixed_shape),
        "teacher_mixed_shape_error": float(teacher_mixed_shape),
        "motion_regressions": motion_regressions,
    }


def stepa_gate_verdict(
    *,
    target_shape_error: float,
    motion_error_px: float,
    refs: StepAReferences = StepAReferences(),
) -> dict:
    motion_limit = refs.r44b_r42_motion_error_px * (1.0 + refs.motion_regression_cap_pct / 100.0)
    weak_shape_limit = refs.r44b_r42_target_shape_error * (1.0 - refs.weak_shape_improvement_pct / 100.0)
    if not math.isfinite(float(target_shape_error)) or not math.isfinite(float(motion_error_px)):
        verdict = "missing_metrics"
    elif float(motion_error_px) > motion_limit:
        verdict = "fail_motion_regression"
    elif float(target_shape_error) <= refs.r44b_r40_target_shape_error:
        verdict = "strong_pass"
    elif float(target_shape_error) <= weak_shape_limit:
        verdict = "weak_pass"
    else:
        verdict = "fail"
    return {
        "verdict": verdict,
        "target_shape_error": float(target_shape_error),
        "motion_error_px": float(motion_error_px),
        "strong_shape_limit": float(refs.r44b_r40_target_shape_error),
        "weak_shape_limit": float(weak_shape_limit),
        "motion_limit_px": float(motion_limit),
    }


def _load_motion_summary(candidate_folder: str, motion_recon_root: Path) -> dict:
    candidate_root = motion_recon_root / candidate_folder
    for name in ("motion_summary.json", "motion_val_unseen_summary.json"):
        path = candidate_root / name
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    rows = _read_csv_rows(candidate_root / "motion_rows.csv")
    return {
        "overall_motion_vector_error_px": _mean(_safe_float(r.get("motion_vector_error_px")) for r in rows),
        "overall_boundary_motion_distance_px": _mean(_safe_float(r.get("boundary_motion_distance_px")) for r in rows),
        "overall_grid_phase_motion_error_px": _mean(_safe_float(r.get("grid_phase_motion_error_px")) for r in rows),
    }


def _load_ring_guard_summary(candidate_folder: str, ring_guard_root: Path) -> dict:
    path = ring_guard_root / f"{candidate_folder}_ring_guard_summary.json"
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _ring_value(summary: dict, short_name: str) -> float:
    for row in summary.get("datasets", []):
        if row.get("short_name") == short_name:
            return _safe_float(row.get("r44_internal_step_std_y"))
    return float("nan")


def build_stepa_summary(
    *,
    motion_recon_root: Path = DEFAULT_MOTION_RECON_ROOT,
    diagnostic_root: Path = DEFAULT_DIAGNOSTIC_ROOT,
    ring_guard_root: Path = DEFAULT_RING_GUARD_ROOT,
    output_root: Path = RESULT_ROOT,
    refs: StepAReferences = StepAReferences(),
) -> dict:
    shape_target_rows = _read_csv_rows(diagnostic_root / "r44h_boundary_shape_target_rank.csv")
    if not shape_target_rows:
        shape_target_rows = _read_csv_rows(diagnostic_root / "r44g_boundary_shape_target_rank.csv")
    shape_score_rows = _read_csv_rows(diagnostic_root / "r44h_boundary_shape_scorecard.csv")
    if not shape_score_rows:
        shape_score_rows = _read_csv_rows(diagnostic_root / "r44g_boundary_shape_scorecard.csv")
    motion_family_rows = _read_csv_rows(diagnostic_root / "r44h_family_scorecard.csv")
    if not motion_family_rows:
        motion_family_rows = _read_csv_rows(diagnostic_root / "r44d_family_scorecard.csv")

    all_candidate_folders = build_r44h_model_map()

    rows = []
    for model, folder in all_candidate_folders.items():
        target_row = _row_for(shape_target_rows, model=model)
        motion_summary = _load_motion_summary(folder, motion_recon_root)
        ring_summary = _load_ring_guard_summary(folder, ring_guard_root)
        target_shape_error = _safe_float(target_row.get("target_shape_error_score")) if target_row else float("nan")
        motion_error = _safe_float(motion_summary.get("overall_motion_vector_error_px"))
        gate = stepa_gate_verdict(target_shape_error=target_shape_error, motion_error_px=motion_error, refs=refs)
        row = {
            "model": model,
            "recon_folder": folder,
            "target_shape_error_score": target_shape_error,
            "target_boundary_f_score": _safe_float(target_row.get("target_boundary_f_score")) if target_row else float("nan"),
            "overall_motion_error_px": motion_error,
            "overall_boundary_motion_distance_px": _safe_float(motion_summary.get("overall_boundary_motion_distance_px")),
            "overall_grid_phase_motion_error_px": _safe_float(motion_summary.get("overall_grid_phase_motion_error_px")),
            "ring_8px_step_std": _ring_value(ring_summary, "pitch1um_y_100"),
            "ring_0p8px_step_std": _ring_value(ring_summary, "pitch0p1um_y_60"),
            "ring_0p08px_step_std": _ring_value(ring_summary, "pitch0p01um_y_40"),
            **gate,
        }
        rows.append(row)

    r44c_cleanliness = assess_r44c_cleanliness(
        motion_family_rows=motion_family_rows,
        target_shape_rows=shape_target_rows,
        shape_score_rows=shape_score_rows,
    )
    rows_sorted = sorted(
        rows,
        key=lambda r: (
            0 if str(r["model"]).startswith("R44H ") else 1,
            float(r["target_shape_error_score"]) if math.isfinite(float(r["target_shape_error_score"])) else 999.0,
        ),
    )
    output_root.mkdir(parents=True, exist_ok=True)
    _write_csv(rows_sorted, output_root / "r44h_stepa_summary.csv")
    payload = {
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "references": {
            "r44b_r42_target_shape_error": refs.r44b_r42_target_shape_error,
            "r44b_r42_motion_error_px": refs.r44b_r42_motion_error_px,
            "r44b_r40_target_shape_error": refs.r44b_r40_target_shape_error,
            "motion_regression_cap_pct": refs.motion_regression_cap_pct,
            "weak_shape_improvement_pct": refs.weak_shape_improvement_pct,
        },
        "r44c_cleanliness": r44c_cleanliness,
        "rows": rows_sorted,
    }
    _write_json(payload, output_root / "r44h_stepa_summary.json")
    return payload


def refresh_r44h_diagnostics(
    *,
    motion_recon_root: Path = DEFAULT_MOTION_RECON_ROOT,
    diagnostic_root: Path = DEFAULT_DIAGNOSTIC_ROOT,
    frame_limit: int | None = None,
) -> dict:
    import r44d_family_diagnostics as r44d
    import r44g_boundary_shape_metrics as r44g

    model_map = build_r44h_model_map()
    diagnostic_root.mkdir(parents=True, exist_ok=True)

    motion_rows = r44d.load_all_rows(motion_recon_root, model_map)
    motion_diag = r44d.build_diagnostics(motion_rows)
    motion_paths = {
        "family_csv": diagnostic_root / "r44h_family_scorecard.csv",
        "shift_csv": diagnostic_root / "r44h_shift_scorecard.csv",
        "best_csv": diagnostic_root / "r44h_best_by_family.csv",
        "metric_csv": diagnostic_root / "r44h_metric_discrimination.csv",
        "summary_json": diagnostic_root / "r44h_motion_diagnostic_summary.json",
    }
    r44d.write_csv(motion_diag["family_scorecard"], motion_paths["family_csv"])
    r44d.write_csv(motion_diag["shift_scorecard"], motion_paths["shift_csv"])
    r44d.write_csv(motion_diag["best_by_family"], motion_paths["best_csv"])
    r44d.write_csv(motion_diag["metric_discrimination"], motion_paths["metric_csv"])
    motion_paths["summary_json"].write_text(json.dumps(_json_safe(motion_diag), ensure_ascii=False, indent=2), encoding="utf-8")

    shape_rows = r44g.collect_shape_rows(
        recon_root=motion_recon_root,
        model_map=model_map,
        frame_limit=frame_limit,
    )
    shape_summary = r44g.summarize_rows(shape_rows)
    target_rows = r44g.summarize_target_families(shape_summary)
    shape_paths = {
        "rows_csv": diagnostic_root / "r44h_boundary_shape_rows.csv",
        "score_csv": diagnostic_root / "r44h_boundary_shape_scorecard.csv",
        "target_csv": diagnostic_root / "r44h_boundary_shape_target_rank.csv",
        "summary_json": diagnostic_root / "r44h_boundary_shape_scorecard.json",
    }
    r44g.write_csv(shape_rows, shape_paths["rows_csv"])
    r44g.write_csv(shape_summary, shape_paths["score_csv"])
    r44g.write_csv(target_rows, shape_paths["target_csv"])
    r44g.write_json(
        {
            "model_map": model_map,
            "row_count": len(shape_rows),
            "scorecard": shape_summary,
            "target_rank": target_rows,
        },
        shape_paths["summary_json"],
    )
    return {
        "model_count": len(model_map),
        "motion_row_count": len(motion_rows),
        "shape_row_count": len(shape_rows),
        "motion_paths": {key: str(value) for key, value in motion_paths.items()},
        "shape_paths": {key: str(value) for key, value in shape_paths.items()},
    }


def _fmt(value: object, digits: int = 4) -> str:
    if isinstance(value, (float, int)):
        return f"{float(value):.{digits}f}" if math.isfinite(float(value)) else "—"
    return str(value)


def _markdown_table(rows: list[dict], columns: list[tuple[str, str]]) -> str:
    lines = [
        "| " + " | ".join(label for label, _key in columns) + " |",
        "|" + "|".join("---" for _ in columns) + "|",
    ]
    for row in rows:
        lines.append("| " + " | ".join(_fmt(row.get(key, "")) for _label, key in columns) + " |")
    return "\n".join(lines)


def write_stepa_report(
    payload: dict,
    report_path: Path = DEFAULT_REPORT,
    *,
    checkpoint_root: Path = DEFAULT_CHECKPOINT_ROOT,
    output_root: Path = RESULT_ROOT,
) -> None:
    rows = payload["rows"]
    r44h_rows = [r for r in rows if str(r["model"]).startswith("R44H ")]
    strong_rows = [r for r in r44h_rows if r.get("verdict") == "strong_pass"]
    weak_rows = [r for r in r44h_rows if r.get("verdict") == "weak_pass"]
    r44c = payload["r44c_cleanliness"]
    if strong_rows:
        decision = "Step A 通過強門檻，可以把最佳平均點拿去做 Step B 的單老師區域蒸餾概念驗證。"
    elif weak_rows:
        decision = "Step A 有弱通過，代表平均有一點用，但不夠乾淨；若要進 Step B，建議只用最保守的平均點。"
    else:
        decision = "Step A 沒有找到可用平均點；下一步應跳過平均起點，直接做 Step B 的單老師區域蒸餾。"
    lines = [
        "# R44H Step 0 / Step A — R44B 家族權重平均探測",
        "",
        "## 摘要",
        "",
        "- 本文件是 R44 內部分析，不開新 round，也不是正式升級候選。",
        "- Step 0 檢查 `R44C static heavy` 是否能作為混合場景老師。",
        "- Step A 只在 R44B 家族內做權重平均，避免跨太遠模型造成權重落到壞區域。",
        f"- 初步決策：**{decision}**",
        "",
        "## Step 0：R44C 乾淨度",
        "",
        f"- 是否足夠乾淨，可作混合場景老師：**{r44c['clean_enough_for_mixed_teacher']}**",
        f"- 混合場景形狀錯誤：R44B from R42 `{r44c['reference_mixed_shape_error']:.4f}`，R44C static heavy `{r44c['teacher_mixed_shape_error']:.4f}`。",
        f"- 大區塊/混合相關位移最大退步：`{r44c['max_motion_regression_pct']:.2f}%`（門檻 `{r44c['motion_regression_cap_pct']:.1f}%`）。",
        "- 解讀：若這裡為 True，R44C 可以在 Step C 當混合場景局部老師；若為 False，先不要把它放進多老師蒸餾。",
        "",
        "## Step A：候選結果",
        "",
        _markdown_table(
            r44h_rows,
            [
                ("候選", "model"),
                ("大區塊+混合錯誤↓", "target_shape_error_score"),
                ("位移誤差 px↓", "overall_motion_error_px"),
                ("邊界位移距離↓", "overall_boundary_motion_distance_px"),
                ("環形 8px", "ring_8px_step_std"),
                ("環形 0.8px", "ring_0p8px_step_std"),
                ("環形 0.08px", "ring_0p08px_step_std"),
                ("判定", "verdict"),
            ],
        ),
        "",
        "## 參考模型",
        "",
        _markdown_table(
            [r for r in rows if not str(r["model"]).startswith("R44H ")],
            [
                ("模型", "model"),
                ("大區塊+混合錯誤↓", "target_shape_error_score"),
                ("位移誤差 px↓", "overall_motion_error_px"),
                ("邊界位移距離↓", "overall_boundary_motion_distance_px"),
                ("環形 8px", "ring_8px_step_std"),
                ("環形 0.8px", "ring_0p8px_step_std"),
                ("環形 0.08px", "ring_0p08px_step_std"),
                ("判定", "verdict"),
            ],
        ),
        "",
        "## 判定規則",
        "",
        "- 強通過：大區塊+混合形狀錯誤優於或等於 `R44B from R40` 的 `0.3110`，且整體位移退步不超過 `R44B from R42` 的 10%。",
        "- 弱通過：形狀錯誤至少比 `R44B from R42` 改善 3%，且位移退步不超過 10%。",
        "- 失敗：形狀沒有改善，或位移退步超過 10%。",
        "",
        "## 產物",
        "",
        f"- 平均候選權重：`{checkpoint_root}`",
        f"- Step A 表格：`{output_root / 'r44h_stepa_summary.csv'}`",
        f"- Step A JSON：`{output_root / 'r44h_stepa_summary.json'}`",
        "",
        "## 下一步",
        "",
        decision,
        "",
    ]
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text("\n".join(lines), encoding="utf-8")


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build and summarize R44H Step A family-only averages.")
    parser.add_argument("--build-checkpoints", action="store_true")
    parser.add_argument("--refresh-diagnostics", action="store_true")
    parser.add_argument("--summarize", action="store_true")
    parser.add_argument("--write-report", action="store_true")
    parser.add_argument("--skip-existing", action="store_true")
    parser.add_argument("--checkpoint-root", type=Path, default=DEFAULT_CHECKPOINT_ROOT)
    parser.add_argument("--motion-recon-root", type=Path, default=DEFAULT_MOTION_RECON_ROOT)
    parser.add_argument("--diagnostic-root", type=Path, default=DEFAULT_DIAGNOSTIC_ROOT)
    parser.add_argument("--ring-guard-root", type=Path, default=DEFAULT_RING_GUARD_ROOT)
    parser.add_argument("--output-root", type=Path, default=RESULT_ROOT)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--frame-limit", type=int, default=None)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    if not (args.build_checkpoints or args.refresh_diagnostics or args.summarize or args.write_report):
        args.build_checkpoints = True
        args.refresh_diagnostics = True
        args.summarize = True
        args.write_report = True
    payload = None
    if args.build_checkpoints:
        rows = build_candidate_checkpoints(checkpoint_root=args.checkpoint_root, skip_existing=args.skip_existing)
        print(json.dumps(rows, ensure_ascii=False, indent=2))
    if args.refresh_diagnostics:
        diagnostics = refresh_r44h_diagnostics(
            motion_recon_root=args.motion_recon_root,
            diagnostic_root=args.diagnostic_root,
            frame_limit=args.frame_limit,
        )
        print(json.dumps(diagnostics, ensure_ascii=False, indent=2))
    if args.summarize or args.write_report:
        summary_path = args.output_root / "r44h_stepa_summary.json"
        if args.summarize or not summary_path.exists():
            payload = build_stepa_summary(
                motion_recon_root=args.motion_recon_root,
                diagnostic_root=args.diagnostic_root,
                ring_guard_root=args.ring_guard_root,
                output_root=args.output_root,
            )
        else:
            payload = json.loads(summary_path.read_text(encoding="utf-8"))
    if args.write_report:
        assert payload is not None
        write_stepa_report(
            payload,
            args.report,
            checkpoint_root=args.checkpoint_root,
            output_root=args.output_root,
        )
        print(json.dumps({"report": str(args.report)}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

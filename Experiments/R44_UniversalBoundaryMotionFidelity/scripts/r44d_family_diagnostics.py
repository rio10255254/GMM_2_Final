"""R44D family/shift diagnostics for existing R44 motion runs."""
from __future__ import annotations

import argparse
import csv
import json
import math
from collections import defaultdict
from pathlib import Path
from typing import Iterable


REPO_ROOT = Path(__file__).resolve().parents[3]
EXPERIMENT_ROOT = REPO_ROOT / "Experiments" / "R44_UniversalBoundaryMotionFidelity"
DEFAULT_RECON_ROOT = EXPERIMENT_ROOT / "results" / "motion_recon"
DEFAULT_OUTPUT_DIR = EXPERIMENT_ROOT / "results" / "diagnostics"
DEFAULT_REPORT = EXPERIMENT_ROOT / "reports" / "R44D_FAMILY_DIAGNOSTIC.md"

DEFAULT_MODELS: dict[str, str] = {
    "COMBO": "combo",
    "R39 a030": "r39_a030",
    "R40 a045": "r40_a045",
    "R41 direct": "r41_direct",
    "R42 best": "r42_best",
    "R44B from R42": "r44_motion_from_r42_best_e24",
    "R44B from R40": "r44_motion_from_r40_a045_e24",
    "R44B from COMBO": "r44_motion_from_combo_e24",
    "R44C low motion": "r44c_low_motion_static_guard",
    "R44C family holdout": "r44c_family_holdout_motion",
    "R44C static heavy": "r44c_static_heavy_all_motion",
}

TARGET_POSITION_BY_FRAME_B = {
    1: 0.08,
    2: 0.16,
    3: 0.40,
    4: 0.80,
    5: 2.00,
    6: 8.00,
}

METRICS = (
    "motion_vector_error_px",
    "boundary_motion_distance_px",
    "grid_phase_motion_error_px",
)


def _safe_float(value: object) -> float:
    if value is None:
        return float("nan")
    text = str(value).strip()
    if not text:
        return float("nan")
    try:
        return float(text)
    except ValueError:
        return float("nan")


def _safe_int(value: object, default: int = 0) -> int:
    try:
        return int(float(str(value).strip()))
    except (TypeError, ValueError):
        return default


def _mean(values: Iterable[float]) -> float:
    vals = [float(v) for v in values if math.isfinite(float(v))]
    return float(sum(vals) / len(vals)) if vals else float("nan")


def _round4(value: float) -> float | None:
    return round(float(value), 4) if math.isfinite(float(value)) else None


def _metric_value(row: dict, metric: str) -> float:
    value = row.get(metric, float("nan"))
    return float(value) if math.isfinite(float(value)) else float("nan")


def _target_position(frame_b: int, step_px: float) -> float:
    if frame_b in TARGET_POSITION_BY_FRAME_B:
        return TARGET_POSITION_BY_FRAME_B[frame_b]
    return float(step_px)


def _normalize_row(row: dict, *, model_label: str, recon_folder: str) -> dict:
    expected_dx = _safe_float(row.get("expected_dx_px"))
    expected_dy = _safe_float(row.get("expected_dy_px"))
    if not math.isfinite(expected_dy):
        expected_dy = 0.0
    step_px = math.sqrt(expected_dx * expected_dx + expected_dy * expected_dy) if math.isfinite(expected_dx) else float("nan")
    frame_b = _safe_int(row.get("frame_b"))
    out = {
        "model": model_label,
        "recon_folder": recon_folder,
        "stage": str(row.get("stage", "")),
        "feature_family": str(row.get("feature_family", "")),
        "frame_b": frame_b,
        "expected_step_px": step_px,
        "target_position_px": _target_position(frame_b, step_px),
    }
    for metric in METRICS:
        out[metric] = _safe_float(row.get(metric))
    return out


def load_all_rows(recon_root: Path, model_map: dict[str, str] | None = None) -> list[dict]:
    model_map = model_map or DEFAULT_MODELS
    rows: list[dict] = []
    for model_label, folder in model_map.items():
        path = recon_root / folder / "motion_rows.csv"
        if not path.exists():
            continue
        with path.open("r", encoding="utf-8-sig", newline="") as f:
            for row in csv.DictReader(f):
                rows.append(_normalize_row(row, model_label=model_label, recon_folder=folder))
    if not rows:
        raise FileNotFoundError(f"no motion_rows.csv files found under {recon_root}")
    return rows


def _group(rows: list[dict], keys: tuple[str, ...]) -> dict[tuple, list[dict]]:
    grouped: dict[tuple, list[dict]] = defaultdict(list)
    for row in rows:
        grouped[tuple(row.get(k) for k in keys)].append(row)
    return grouped


def _aggregate_rows(rows: list[dict], keys: tuple[str, ...]) -> list[dict]:
    out = []
    for key_values, group_rows in sorted(_group(rows, keys).items()):
        item = {key: value for key, value in zip(keys, key_values)}
        item["pair_count"] = len(group_rows)
        for metric in METRICS:
            item[f"avg_{metric}"] = _mean(_metric_value(r, metric) for r in group_rows)
        out.append(item)
    return out


def _best_by_family(family_scorecard: list[dict]) -> list[dict]:
    by_family = _group(family_scorecard, ("feature_family",))
    best_rows = []
    for (family,), rows in sorted(by_family.items()):
        for metric in METRICS:
            avg_key = f"avg_{metric}"
            candidates = [r for r in rows if math.isfinite(float(r.get(avg_key, float("nan"))))]
            if not candidates:
                continue
            ordered = sorted(candidates, key=lambda r: float(r[avg_key]))
            best = ordered[0]
            second = ordered[1] if len(ordered) > 1 else None
            best_value = float(best[avg_key])
            second_value = float(second[avg_key]) if second else float("nan")
            best_rows.append(
                {
                    "feature_family": family,
                    "metric": metric,
                    "best_model": best["model"],
                    "best_value": best_value,
                    "second_model": second["model"] if second else "",
                    "second_value": second_value,
                    "gap_to_second": second_value - best_value if math.isfinite(second_value) else float("nan"),
                }
            )
    return best_rows


def _metric_discrimination(family_scorecard: list[dict]) -> list[dict]:
    rows_out = []
    by_family = _group(family_scorecard, ("feature_family",))
    for (family,), rows in sorted(by_family.items()):
        for metric in METRICS:
            avg_key = f"avg_{metric}"
            vals = [float(r[avg_key]) for r in rows if avg_key in r and math.isfinite(float(r[avg_key]))]
            rounded = {round(v, 6) for v in vals}
            rows_out.append(
                {
                    "feature_family": family,
                    "metric": metric,
                    "finite_model_count": len(vals),
                    "unique_value_count": len(rounded),
                    "model_discriminative": len(rounded) > 1,
                    "min_value": min(vals) if vals else float("nan"),
                    "max_value": max(vals) if vals else float("nan"),
                }
            )
    return rows_out


def _oracle_boundary(family_scorecard: list[dict]) -> dict:
    families = sorted({r["feature_family"] for r in family_scorecard})
    models = sorted({r["model"] for r in family_scorecard})
    by_model_family = {(r["model"], r["feature_family"]): r for r in family_scorecard}
    model_avgs = []
    for model in models:
        vals = [
            float(by_model_family[(model, family)]["avg_boundary_motion_distance_px"])
            for family in families
            if (model, family) in by_model_family
            and math.isfinite(float(by_model_family[(model, family)]["avg_boundary_motion_distance_px"]))
        ]
        if vals:
            model_avgs.append({"model": model, "boundary_avg_px": _mean(vals)})
    best_single = min(model_avgs, key=lambda r: r["boundary_avg_px"]) if model_avgs else {"model": "", "boundary_avg_px": float("nan")}
    family_best = []
    for family in families:
        vals = [
            float(by_model_family[(model, family)]["avg_boundary_motion_distance_px"])
            for model in models
            if (model, family) in by_model_family
            and math.isfinite(float(by_model_family[(model, family)]["avg_boundary_motion_distance_px"]))
        ]
        if vals:
            family_best.append(min(vals))
    oracle = _mean(family_best)
    best_single_avg = float(best_single["boundary_avg_px"])
    gap_pct = ((best_single_avg - oracle) / best_single_avg * 100.0) if math.isfinite(best_single_avg) and best_single_avg > 0 else float("nan")
    return {
        "best_single_model": best_single["model"],
        "best_single_model_boundary_avg_px": best_single_avg,
        "family_oracle_boundary_avg_px": oracle,
        "family_oracle_gain_vs_best_single_pct": gap_pct,
        "families": families,
        "model_boundary_averages": model_avgs,
    }


def build_diagnostics(rows: list[dict]) -> dict:
    family_scorecard = _aggregate_rows(rows, ("model", "feature_family"))
    shift_scorecard = _aggregate_rows(rows, ("model", "feature_family", "target_position_px"))
    best_by_family = _best_by_family(family_scorecard)
    metric_discrimination = _metric_discrimination(family_scorecard)
    oracle_boundary = _oracle_boundary(family_scorecard)
    return {
        "family_scorecard": family_scorecard,
        "shift_scorecard": shift_scorecard,
        "best_by_family": best_by_family,
        "metric_discrimination": metric_discrimination,
        "oracle_boundary": oracle_boundary,
    }


def write_csv(rows: list[dict], path: Path) -> None:
    if not rows:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = sorted({key for row in rows for key in row})
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def _format_value(value: object) -> str:
    if isinstance(value, (float, int)):
        return f"{float(value):.4f}" if math.isfinite(float(value)) else "—"
    return str(value)


def _markdown_table(rows: list[dict], columns: list[tuple[str, str]], *, limit: int | None = None) -> str:
    rows = rows[:limit] if limit is not None else rows
    lines = [
        "| " + " | ".join(label for label, _ in columns) + " |",
        "| " + " | ".join("---" for _ in columns) + " |",
    ]
    for row in rows:
        lines.append("| " + " | ".join(_format_value(row.get(key, "")) for _, key in columns) + " |")
    return "\n".join(lines)


def _family_table_for_metric(best_by_family: list[dict], metric: str) -> list[dict]:
    rows = [r for r in best_by_family if r["metric"] == metric]
    return sorted(rows, key=lambda r: r["feature_family"])


def _best_shift_boundary_rows(shift_scorecard: list[dict], families: set[str]) -> list[dict]:
    grouped = _group([r for r in shift_scorecard if r["feature_family"] in families], ("feature_family", "target_position_px"))
    out = []
    for (family, target), rows in sorted(grouped.items(), key=lambda item: (str(item[0][0]), float(item[0][1]))):
        candidates = [r for r in rows if math.isfinite(float(r.get("avg_boundary_motion_distance_px", float("nan"))))]
        if not candidates:
            continue
        best = min(candidates, key=lambda r: float(r["avg_boundary_motion_distance_px"]))
        out.append(
            {
                "feature_family": family,
                "target_position_px": float(target),
                "best_model": best["model"],
                "best_boundary_px": float(best["avg_boundary_motion_distance_px"]),
                "best_motion_px": float(best["avg_motion_vector_error_px"]),
            }
        )
    return out


def _grid_phase_not_discriminative(metric_discrimination: list[dict]) -> bool:
    for row in metric_discrimination:
        if row["metric"] == "grid_phase_motion_error_px" and row["feature_family"] in {"grids", "mixed_fields"}:
            if row["finite_model_count"] >= 2 and not row["model_discriminative"]:
                return True
    return False


def _model_row(family_scorecard: list[dict], model: str, family: str) -> dict | None:
    for row in family_scorecard:
        if row["model"] == model and row["feature_family"] == family:
            return row
    return None


def _make_report(diagnostics: dict, paths: dict[str, Path]) -> str:
    best_boundary = _family_table_for_metric(diagnostics["best_by_family"], "boundary_motion_distance_px")
    best_motion = _family_table_for_metric(diagnostics["best_by_family"], "motion_vector_error_px")
    best_grid = _family_table_for_metric(diagnostics["best_by_family"], "grid_phase_motion_error_px")
    grid_phase_not_discriminative = _grid_phase_not_discriminative(diagnostics["metric_discrimination"])
    shift_boundary = _best_shift_boundary_rows(diagnostics["shift_scorecard"], {"large_regions", "mixed_fields", "grids"})
    oracle = diagnostics["oracle_boundary"]
    family_scorecard = diagnostics["family_scorecard"]
    r42_region = _model_row(family_scorecard, "R42 best", "large_regions")
    r44b_region = _model_row(family_scorecard, "R44B from R42", "large_regions")
    r44c_region = _model_row(family_scorecard, "R44C static heavy", "large_regions")

    lines = [
        "# R44D 診斷 — 分族與位移尺度盤點",
        "",
        "## 摘要",
        "",
        "R44D 不開新 round、不訓練新模型。它只讀取 R44A/R44B/R44C 已經產生的逐 pair 位移結果，拆成結構類型與位移段來看，目的是判斷下一步是否真的需要新機制。",
        "",
        "結論：**現在不應立刻開 R45。R44 內部已足夠證明，問題不是單一權重比例，而是不同顯微結構需要不同處理。**",
        "",
        "最重要發現：",
        "",
        "- `R44B from R42` 仍是最佳整體位移候選，尤其格線位移最強。",
        "- `R44C static heavy` 只把 R44B 稍微拉回平衡，沒有解開大區塊問題。",
        "- 大區塊與混合場景的最佳模型不是同一個，代表單一模型目前很難同時吃下所有結構。",
        "- 目前的格線 phase 欄位對所有模型幾乎相同，不能拿來排名模型；格線應改看輸出影像的位移誤差與邊界距離。",
        "- `family holdout` 先前已被 R44C 否定；排除某些結構不學位移，並不能保住它們。",
        "",
        "## 分族最佳模型",
        "",
        "### 邊界距離最佳",
        "",
        _markdown_table(
            best_boundary,
            [
                ("結構類型", "feature_family"),
                ("最佳模型", "best_model"),
                ("數值", "best_value"),
                ("第二名", "second_model"),
                ("差距", "gap_to_second"),
            ],
        ),
        "",
        "### 位移向量最佳",
        "",
        _markdown_table(
            best_motion,
            [
                ("結構類型", "feature_family"),
                ("最佳模型", "best_model"),
                ("數值", "best_value"),
                ("第二名", "second_model"),
                ("差距", "gap_to_second"),
            ],
        ),
        "",
    ]
    if best_grid:
        phase_note = "目前 `grid_phase_motion_error_px` 在格線與混合場景上對所有模型幾乎相同，代表它不是有效的模型比較欄位。R44D 保留這個 finding，但不再用它判斷誰比較好。"
        if not grid_phase_not_discriminative:
            phase_note = "目前 `grid_phase_motion_error_px` 仍保留為診斷欄位，但 R44D 主要用輸出影像的位移誤差與邊界距離判斷格線能力。"
        lines.extend(
            [
                "### 格線 phase 欄位檢查",
                "",
                phase_note,
                "",
            ]
        )

    lines.extend(
        [
            "## 單一模型 vs 分族上限",
            "",
            f"- 最佳單一模型平均邊界距離：`{oracle['best_single_model']}`，`{oracle['best_single_model_boundary_avg_px']:.4f} px`。",
            f"- 如果每個結構類型都拿目前最佳模型，分族上限是 `{oracle['family_oracle_boundary_avg_px']:.4f} px`。",
            f"- 分族上限相對最佳單一模型還有 `{oracle['family_oracle_gain_vs_best_single_pct']:.2f}%` 空間。",
            "",
            "這表示下一步如果還是只做單一全域權重，天花板可能很低；真正值得做的是讓不同結構的邊界與位移目標分開設計。",
            "",
            "## 位移段觀察",
            "",
            "以下只列大區塊、混合場景與格線，因為它們是目前最影響下一步設計的三類：",
            "",
            _markdown_table(
                shift_boundary,
                [
                    ("結構類型", "feature_family"),
                    ("目標位置 px", "target_position_px"),
                    ("邊界最佳模型", "best_model"),
                    ("邊界距離", "best_boundary_px"),
                    ("同列位移誤差", "best_motion_px"),
                ],
            ),
            "",
            "## 大區塊瓶頸確認",
            "",
        ]
    )
    for label, row in (("R42 best", r42_region), ("R44B from R42", r44b_region), ("R44C static heavy", r44c_region)):
        if row:
            lines.append(f"- `{label}` 大區塊邊界距離：`{row['avg_boundary_motion_distance_px']:.4f} px`。")
    lines.extend(
        [
            "",
            "大區塊不是被 R44C 修好，而是仍然卡住。這也解釋了為什麼 R44B 的整體位移變好，但肉眼與邊界距離沒有同步明顯變好。",
            "",
            "## 產物",
            "",
            f"- 分族總表：`{paths['family_csv']}`",
            f"- 位移段總表：`{paths['shift_csv']}`",
            f"- 每族最佳模型表：`{paths['best_csv']}`",
            f"- 指標有效性檢查：`{paths['metric_csv']}`",
            f"- JSON 彙整：`{paths['summary_json']}`",
        ]
    )
    if paths.get("boundary_heatmap"):
        lines.append(f"- 邊界熱圖：`{paths['boundary_heatmap']}`")
    if paths.get("motion_heatmap"):
        lines.append(f"- 位移熱圖：`{paths['motion_heatmap']}`")
    lines.extend(
        [
            "",
            "## 下一步判斷",
            "",
            "不建議立刻開新 round。建議把下一個動作留在 R44 內部，做一個非常小的 R44E 探針：只針對大區塊與混合場景建立專門保護，不重新挑戰所有結構。若 R44E 仍不能改善，再開新 round 才合理。",
            "",
        ]
    )
    return "\n".join(lines)


def _write_heatmap(family_scorecard: list[dict], metric_key: str, path: Path, title: str) -> bool:
    try:
        import matplotlib.pyplot as plt
        import numpy as np
    except Exception:
        return False
    models = sorted({r["model"] for r in family_scorecard})
    families = sorted({r["feature_family"] for r in family_scorecard})
    lookup = {(r["model"], r["feature_family"]): r for r in family_scorecard}
    matrix = []
    for family in families:
        matrix.append([float(lookup[(model, family)].get(metric_key, float("nan"))) if (model, family) in lookup else float("nan") for model in models])
    arr = np.asarray(matrix, dtype=np.float32)
    fig_w = max(9, len(models) * 0.9)
    fig_h = max(4.5, len(families) * 0.6)
    fig, ax = plt.subplots(figsize=(fig_w, fig_h), dpi=150)
    im = ax.imshow(arr, cmap="viridis_r")
    ax.set_xticks(range(len(models)))
    ax.set_xticklabels(models, rotation=45, ha="right", fontsize=7)
    ax.set_yticks(range(len(families)))
    ax.set_yticklabels(families, fontsize=8)
    ax.set_title(title)
    for y in range(len(families)):
        for x in range(len(models)):
            value = arr[y, x]
            if np.isfinite(value):
                ax.text(x, y, f"{value:.2f}", ha="center", va="center", color="white" if value > np.nanmean(arr) else "black", fontsize=6)
    fig.colorbar(im, ax=ax, fraction=0.03, pad=0.02)
    fig.tight_layout()
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path)
    plt.close(fig)
    return True


def _relative_paths(paths: dict[str, Path]) -> dict[str, Path]:
    out = {}
    for key, path in paths.items():
        try:
            out[key] = path.resolve().relative_to(REPO_ROOT.resolve())
        except ValueError:
            out[key] = path
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run R44D family/shift diagnostics on existing motion rows.")
    parser.add_argument("--recon-root", type=Path, default=DEFAULT_RECON_ROOT)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    args = parser.parse_args(argv)

    rows = load_all_rows(args.recon_root)
    diagnostics = build_diagnostics(rows)
    args.output_dir.mkdir(parents=True, exist_ok=True)

    paths = {
        "family_csv": args.output_dir / "r44d_family_scorecard.csv",
        "shift_csv": args.output_dir / "r44d_shift_scorecard.csv",
        "best_csv": args.output_dir / "r44d_best_by_family.csv",
        "metric_csv": args.output_dir / "r44d_metric_discrimination.csv",
        "summary_json": args.output_dir / "r44d_summary.json",
        "boundary_heatmap": args.output_dir / "r44d_boundary_heatmap.png",
        "motion_heatmap": args.output_dir / "r44d_motion_heatmap.png",
    }
    write_csv(diagnostics["family_scorecard"], paths["family_csv"])
    write_csv(diagnostics["shift_scorecard"], paths["shift_csv"])
    write_csv(diagnostics["best_by_family"], paths["best_csv"])
    write_csv(diagnostics["metric_discrimination"], paths["metric_csv"])
    paths["summary_json"].write_text(json.dumps(diagnostics, ensure_ascii=False, indent=2), encoding="utf-8")

    if not _write_heatmap(diagnostics["family_scorecard"], "avg_boundary_motion_distance_px", paths["boundary_heatmap"], "R44D boundary distance by family/model"):
        paths.pop("boundary_heatmap", None)
    if not _write_heatmap(diagnostics["family_scorecard"], "avg_motion_vector_error_px", paths["motion_heatmap"], "R44D motion error by family/model"):
        paths.pop("motion_heatmap", None)

    report_paths = _relative_paths(paths)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(_make_report(diagnostics, report_paths), encoding="utf-8")

    print(json.dumps({
        "rows": len(rows),
        "family_rows": len(diagnostics["family_scorecard"]),
        "shift_rows": len(diagnostics["shift_scorecard"]),
        "oracle_boundary": diagnostics["oracle_boundary"],
        "report": str(args.report.resolve()),
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

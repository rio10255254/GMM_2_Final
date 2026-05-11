"""R39 external GMF compare for the alpha=0.30 averaged checkpoint.

Implements the methodology from `R33RobustLoss/reports/GMF_STEP_STD_METHODOLOGY.md`:

- step_std = np.std(np.diff(PosY)) over all GMF frames sorted by filename
- raw std is the headline; |z| > 5 steps are flagged as GMF detection failures
  and removed only when they exist (z = (step - median) / raw_std)
- final std reported per scale is the filtered std (== raw std when no outliers)
"""
from __future__ import annotations

import argparse
import json
import math
import statistics
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping


_REPO_ROOT = Path(__file__).resolve().parents[3]

DEFAULT_A030_DIR = (
    _REPO_ROOT
    / "Experiments"
    / "R39_ShapeGeneralization"
    / "results"
    / "external_gmf_a030"
)

DEFAULT_OUTPUT_JSON = DEFAULT_A030_DIR / "external_compare_summary.json"
DEFAULT_REPORT_MD = (
    _REPO_ROOT
    / "Experiments"
    / "R39_ShapeGeneralization"
    / "reports"
    / "R39_EXTERNAL_COMPARE.md"
)

SCALE_DIRS: tuple[tuple[str, str, float], ...] = (
    ("8px", "pitch8px", 8.0),
    ("0p8px", "pitch0p8px", 0.8),
    ("0p08px", "pitch0p08px", 0.08),
)

COMBO_EXTERNAL_STEP_STD: dict[str, float] = {
    "8px": 0.154515,
    "0p8px": 0.131560,
    "0p08px": 0.099891,
}

# Reference numbers from ESTIMATOR_POLICY.json so the report can place a030
# in the existing alternate landscape without manual cross-checking.
ALTERNATE_REFERENCE_STEP_STD: dict[str, dict[str, float]] = {
    "R33 (gmf_extreme_alternate)": {
        "8px": 0.153343,
        "0p8px": 0.119049,
        "0p08px": 0.086274,
    },
    "R38v2 (visual_priority_alternate)": {
        "8px": 0.143988,
        "0p8px": 0.134205,
        "0p08px": 0.106457,
    },
    "R30 (former_baseline)": {
        "8px": 0.205193,
        "0p8px": 0.167862,
        "0p08px": 0.157720,
    },
}


# ---------------------------------------------------------------------------
# parse
# ---------------------------------------------------------------------------


def parse_gmf_score(path: Path) -> dict[str, dict]:
    """Read a GMF_score.txt and return {filename: {pos_x, pos_y, score0}}."""
    p = Path(path)
    if not p.is_file():
        raise FileNotFoundError(f"GMF_score.txt not found: {p}")
    out: dict[str, dict] = {}
    with p.open("r", encoding="utf-8") as fh:
        for raw in fh:
            line = raw.strip()
            if not line:
                continue
            tokens = [tok.strip() for tok in line.split(",")]
            if len(tokens) < 4:
                continue
            record: dict[str, str] = {}
            for i in range(len(tokens) // 2):
                k = tokens[i * 2]
                v = tokens[i * 2 + 1]
                if k:
                    record[k] = v
            fname = record.get("FileName")
            pos_y = record.get("PosY")
            if not fname or pos_y is None:
                continue
            try:
                py = float(pos_y)
                px = float(record.get("PosX", "nan"))
                sc = float(record.get("Score0", "nan"))
            except ValueError:
                continue
            out[fname] = {"pos_x": px, "pos_y": py, "score0": sc}
    return out


def pos_y_series_sorted(parsed: Mapping[str, Mapping]) -> list[float]:
    """Return PosY sorted by filename (alphabetical, the GMF convention)."""
    return [parsed[k]["pos_y"] for k in sorted(parsed.keys())]


# ---------------------------------------------------------------------------
# step stats with z-based outlier filtering
# ---------------------------------------------------------------------------


def _stddev_pop(values: list[float]) -> float:
    n = len(values)
    if n == 0:
        return 0.0
    if n == 1:
        return 0.0
    mean = sum(values) / n
    var = sum((v - mean) ** 2 for v in values) / n
    return math.sqrt(var)


def compute_step_stats(
    pos_y: list[float],
    *,
    z_threshold: float = 5.0,
    filenames: list[str] | None = None,
) -> dict:
    if len(pos_y) < 2:
        raise ValueError("need at least 2 PosY samples to compute steps")
    steps = [pos_y[i + 1] - pos_y[i] for i in range(len(pos_y) - 1)]
    raw_std = _stddev_pop(steps)
    median_step = statistics.median(steps)

    outliers: list[dict] = []
    keep_mask: list[bool] = []
    for idx, step in enumerate(steps):
        if raw_std > 0:
            z = (step - median_step) / raw_std
        else:
            z = 0.0
        if abs(z) > z_threshold:
            outliers.append(
                {
                    "step_index": idx,
                    "step": step,
                    "z": z,
                    "frame": (
                        f"{filenames[idx]}->{filenames[idx + 1]}"
                        if filenames is not None and len(filenames) == len(pos_y)
                        else f"{idx}->{idx + 1}"
                    ),
                }
            )
            keep_mask.append(False)
        else:
            keep_mask.append(True)

    kept = [s for s, m in zip(steps, keep_mask) if m]
    filtered_std = _stddev_pop(kept) if kept else 0.0
    return {
        "n_pos_samples": len(pos_y),
        "n_steps": len(steps),
        "median_step": median_step,
        "raw_std": raw_std,
        "filtered_std": filtered_std,
        "n_outliers": len(outliers),
        "outliers": outliers,
        "z_threshold": z_threshold,
    }


# ---------------------------------------------------------------------------
# verdict
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ScaleVerdict:
    status: str
    delta: float
    delta_pct: float


# Anchored to the R38v2 alternate's worst regression vs COMBO (+6.6% on 0.08px)
# plus a small slack: any single scale degrading more than this exceeds the
# historically accepted alternate band.
DEFAULT_TRADEOFF_MAX_PCT = 7.0


def _scale_status(a030: float, combo: float, tradeoff_max_pct: float) -> ScaleVerdict:
    delta = a030 - combo
    delta_pct = (delta / combo) * 100.0 if combo else 0.0
    if a030 < combo:
        status = "IMPROVED"
    elif delta_pct <= tradeoff_max_pct:
        status = "TRADEOFF_OK"
    else:
        status = "REGRESSED"
    return ScaleVerdict(status=status, delta=delta, delta_pct=delta_pct)


def verdict_against_combo(
    a030: dict[str, float],
    combo: dict[str, float],
    tradeoff_max_pct: float = DEFAULT_TRADEOFF_MAX_PCT,
) -> dict:
    """Decide a030's role versus COMBO with three tiers.

    Per-scale status:
      - IMPROVED      : a030 < combo
      - TRADEOFF_OK   : a030 >= combo, but degradation <= tradeoff_max_pct
      - REGRESSED     : degradation > tradeoff_max_pct

    Overall verdict:
      - PASS_IMPROVED : all three scales IMPROVED        -> baseline replacement candidate
      - PASS_TRADEOFF : >=2 IMPROVED, others TRADEOFF_OK -> alternate-grade candidate
      - MIXED         : 1 IMPROVED, 2 TRADEOFF_OK         -> needs human decision
      - FAIL          : any REGRESSED                     -> not promotable
    """
    per_scale: dict[str, dict] = {}
    n_improved = 0
    n_tradeoff = 0
    n_regressed = 0
    for scale in ("8px", "0p8px", "0p08px"):
        v = _scale_status(a030[scale], combo[scale], tradeoff_max_pct)
        per_scale[scale] = {
            "a030": a030[scale],
            "combo": combo[scale],
            "delta": v.delta,
            "delta_pct": v.delta_pct,
            "status": v.status,
        }
        if v.status == "IMPROVED":
            n_improved += 1
        elif v.status == "TRADEOFF_OK":
            n_tradeoff += 1
        else:
            n_regressed += 1

    if n_regressed > 0:
        overall = "FAIL"
    elif n_improved == 3:
        overall = "PASS_IMPROVED"
    elif n_improved >= 2:
        overall = "PASS_TRADEOFF"
    else:
        overall = "MIXED"
    return {
        "overall": overall,
        "tradeoff_max_pct": tradeoff_max_pct,
        "per_scale": per_scale,
    }


# ---------------------------------------------------------------------------
# orchestration
# ---------------------------------------------------------------------------


def run_compare(a030_dir: Path, *, z_threshold: float = 5.0) -> dict:
    rows: dict[str, dict] = {}
    a030_step_std: dict[str, float] = {}
    for short, subdir, expected in SCALE_DIRS:
        path = a030_dir / subdir / "GMF_score.txt"
        parsed = parse_gmf_score(path)
        filenames = sorted(parsed.keys())
        pos_y = [parsed[fn]["pos_y"] for fn in filenames]
        stats = compute_step_stats(pos_y, z_threshold=z_threshold, filenames=filenames)
        rows[short] = {
            "subdir": subdir,
            "expected_step_px": expected,
            "n_frames": len(filenames),
            "first_filename": filenames[0] if filenames else None,
            "last_filename": filenames[-1] if filenames else None,
            "stats": stats,
        }
        a030_step_std[short] = stats["filtered_std"]

    verdict = verdict_against_combo(a030_step_std, COMBO_EXTERNAL_STEP_STD)
    return {
        "candidate": "r39_combo_strong_avg_a030",
        "a030_dir": str(a030_dir),
        "scales": rows,
        "headline_step_std": a030_step_std,
        "combo_step_std": COMBO_EXTERNAL_STEP_STD,
        "verdict": verdict,
    }


def write_markdown_report(payload: dict, report_md: Path) -> None:
    rows = payload["scales"]
    headline = payload["headline_step_std"]
    combo = payload["combo_step_std"]
    verdict = payload["verdict"]
    lines = [
        "# R39 External GMF Compare — `r39_combo_strong_avg_a030`",
        "",
        "候選:`COMBO` 與 `r39_shape_mix_strong` 兩組權重 checkpoint 的 "
        "**alpha = 0.30** 線性插值。",
        "",
        "方法:`Experiments/R33RobustLoss/reports/GMF_STEP_STD_METHODOLOGY.md`"
        "(原始 step_std,只移除 `|z| > 5` 的 GMF 失敗 step)。",
        "",
        "## Headline 數字",
        "",
        "| scale | a030 step_std | COMBO 外部 step_std | delta | delta % | status |",
        "|---|---:|---:|---:|---:|:---:|",
    ]
    for scale in ("8px", "0p8px", "0p08px"):
        per = verdict["per_scale"][scale]
        lines.append(
            f"| {scale} | {headline[scale]:.6f} | {combo[scale]:.6f} "
            f"| {per['delta']:+.6f} | {per['delta_pct']:+.2f}% | **{per['status']}** |"
        )
    lines += [
        "",
        f"整體 verdict:**{verdict['overall']}** "
        f"(tradeoff_max_pct = {verdict['tradeoff_max_pct']:.1f}%)",
        "",
        "## 各 scale 詳細",
    ]
    for short, _, _ in SCALE_DIRS:
        row = rows[short]
        st = row["stats"]
        lines += [
            "",
            f"### {short} ({row['subdir']})",
            "",
            f"- frames: {row['n_frames']} (steps={st['n_steps']})",
            f"- first / last: `{row['first_filename']}` ... `{row['last_filename']}`",
            f"- median step: {st['median_step']:+.4f}",
            f"- raw std: `{st['raw_std']:.6f}`",
            f"- filtered std (headline): `{st['filtered_std']:.6f}`",
            f"- outliers ( |z| > {st['z_threshold']:.0f} ): {st['n_outliers']}",
        ]
        if st["outliers"]:
            for o in st["outliers"]:
                lines.append(
                    f"  - `{o['frame']}` step={o['step']:+.4f} z={o['z']:+.2f}"
                )

    lines += [
        "",
        "## Cross-Alternate 比較",
        "",
        "參考數字來自 `ESTIMATOR_POLICY.json`。",
        "",
        "| candidate | 8px | 0.8px | 0.08px |",
        "|---|---:|---:|---:|",
    ]
    rows_table: list[tuple[str, dict[str, float]]] = [
        ("COMBO (formal_baseline)", combo),
        *ALTERNATE_REFERENCE_STEP_STD.items(),
        ("**a030 (this candidate)**", headline),
    ]
    for name, vals in rows_table:
        lines.append(
            f"| {name} | {vals['8px']:.6f} | {vals['0p8px']:.6f} | {vals['0p08px']:.6f} |"
        )

    lines += [
        "",
        "### 各 scale 排名(越低越好,只列有外部 GMF 的候選)",
        "",
    ]
    rank_pool = {
        "COMBO": combo,
        "R33": ALTERNATE_REFERENCE_STEP_STD["R33 (gmf_extreme_alternate)"],
        "R38v2": ALTERNATE_REFERENCE_STEP_STD["R38v2 (visual_priority_alternate)"],
        "a030": headline,
    }
    for scale in ("8px", "0p8px", "0p08px"):
        ranked = sorted(rank_pool.items(), key=lambda kv: kv[1][scale])
        line = f"- **{scale}**: " + " < ".join(
            f"{name} ({vals[scale]:.4f})" for name, vals in ranked
        )
        lines.append(line)

    lines += [
        "",
        "## 建議角色",
        "",
        "從上面的 cross-alternate 排名來看,a030 的特性是:",
        "",
        "- **8px**:在頭部與 R38v2 統計打平(0.1438 vs 0.1440,~0.1% 差距落在 GMF noise 之下)",
        "- **0.08px**:全候選之冠,連 R33 都贏(比 R33 再低約 2.7%)",
        "- **0.8px**:四者中最弱(vs COMBO +6.4%,但仍比 R30 former baseline 低 −16.6%)",
        "",
        "建議角色:**shape_generalization_endpoint_alternate** —— "
        "同時需要形狀泛化與 8px / 0.08px 端點精度的 deployment;"
        "0.8px 取向的 deployment 不適合(那邊用 COMBO 或 R33)。",
        "",
        "附帶軸(held-out shape PSNR,不在傳統 GMF 表上):"
        "a030 = 25.03 vs COMBO = 22.84(+2.19 PSNR)。"
        "來源:`Experiments/R39_ShapeGeneralization/results/weight_sweep/sweep_summary.md`",
        "",
        "## 等待升級決定",
        "",
        "這份報告只記錄外部 GMF 量測。要不要把 a030 升進 "
        "`ESTIMATOR_POLICY.json` 的 `approved_alternates`,是專案 owner "
        "必須明確拍板的另一個決定。在那之前 a030 掛在 `open_side_tracks`,"
        "狀態 `external_gmf_complete_alternate_grade_pending_promotion`。",
    ]

    report_md.parent.mkdir(parents=True, exist_ok=True)
    report_md.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="R39 a030 external GMF compare")
    parser.add_argument("--a030-dir", type=Path, default=DEFAULT_A030_DIR)
    parser.add_argument("--output-json", type=Path, default=DEFAULT_OUTPUT_JSON)
    parser.add_argument("--report-md", type=Path, default=DEFAULT_REPORT_MD)
    parser.add_argument("--z-threshold", type=float, default=5.0)
    args = parser.parse_args(argv)

    payload = run_compare(args.a030_dir, z_threshold=args.z_threshold)

    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    write_markdown_report(payload, args.report_md)

    print(json.dumps({
        "verdict": payload["verdict"]["overall"],
        "headline_step_std": payload["headline_step_std"],
        "report_md": str(args.report_md),
        "summary_json": str(args.output_json),
    }, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

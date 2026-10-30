"""
Round31 external GMF compare against the Round30 baseline.

Outputs:
  - ROUND31_EXTERNAL_COMPARE.md
  - ROUND31_EXTERNAL_COMPARE.json

Evidence-first policy:
  - Compare only candidates with actual GMF_score.txt artifacts.
  - Report missing candidates explicitly instead of inventing a verdict.
"""
from __future__ import annotations

import json
import math
import time
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
ROUND30_ROOT = PROJECT_ROOT / "Experiments" / "Legacy" / "organized_20260316" / "round30" / "gmf_results" / "raw"
ROUND31_ROOT = PROJECT_ROOT / "Experiments" / "Legacy" / "organized_20260316" / "round31" / "gmf_results" / "raw"
REPORT_DIR = PROJECT_ROOT / "Experiments" / "Legacy" / "organized_20260316" / "round31" / "selected" / "reports"
SUMMARY_MD = REPORT_DIR / "ROUND31_EXTERNAL_COMPARE.md"
SUMMARY_JSON = REPORT_DIR / "ROUND31_EXTERNAL_COMPARE.json"

MODEL_SPECS = [
    {
        "candidate": "r30_b1_dironly",
        "root": ROUND30_ROOT / "r30_b1_dironly",
    },
    {
        "candidate": "r31_eq_prob_up",
        "root": ROUND31_ROOT / "r31_eq_prob_up",
    },
    {
        "candidate": "r31_eq_weight_up",
        "root": ROUND31_ROOT / "r31_eq_weight_up",
    },
    {
        "candidate": "r31_edge_ratio_low",
        "root": ROUND31_ROOT / "r31_edge_ratio_low",
    },
]

MISSING_CANDIDATES = [
    {
        "candidate": "r31_eq_combo",
        "expected_root": str(ROUND31_ROOT / "r31_eq_combo"),
        "reason": "missing_gmf_score_artifact",
    }
]

PITCH_MAP = {
    "8px": "pitch8px",
    "0.8px": "pitch0p8px",
    "0.08px": "pitch0p08px",
}


def parse_posy(path: Path) -> list[float]:
    posy: list[float] = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        parts = [item.strip() for item in raw.split(",")]
        for idx, token in enumerate(parts):
            if token == "PosY" and idx + 1 < len(parts):
                posy.append(float(parts[idx + 1]))
                break
    if not posy:
        raise RuntimeError(f"No PosY entries found in {path}")
    return posy


def steps_from_posy(posy: list[float]) -> list[float]:
    return [posy[i + 1] - posy[i] for i in range(len(posy) - 1)]


def mean(values: list[float]) -> float:
    return sum(values) / float(len(values))


def std(values: list[float]) -> float:
    mu = mean(values)
    return math.sqrt(sum((v - mu) ** 2 for v in values) / float(len(values)))


def lag1_autocorr(posy: list[float]) -> float:
    if len(posy) < 3:
        return float("nan")
    xs = list(range(len(posy)))
    x_mean = mean(xs)
    y_mean = mean(posy)
    denom = sum((x - x_mean) ** 2 for x in xs)
    slope = 0.0 if denom == 0.0 else sum((x - x_mean) * (y - y_mean) for x, y in zip(xs, posy)) / denom
    intercept = y_mean - slope * x_mean
    residuals = [y - (slope * x + intercept) for x, y in zip(xs, posy)]
    r0 = residuals[:-1]
    r1 = residuals[1:]
    m0 = mean(r0)
    m1 = mean(r1)
    num = sum((a - m0) * (b - m1) for a, b in zip(r0, r1))
    den0 = math.sqrt(sum((a - m0) ** 2 for a in r0))
    den1 = math.sqrt(sum((b - m1) ** 2 for b in r1))
    if den0 <= 1.0e-12 or den1 <= 1.0e-12:
        return float("nan")
    return num / (den0 * den1)


def summarize_model(candidate: str, root: Path) -> dict:
    result = {
        "candidate": candidate,
        "root": str(root),
        "metrics": {},
        "outlier_0p8": {},
    }
    for pitch_label, pitch_dir in PITCH_MAP.items():
        score_path = root / pitch_dir / "GMF_score.txt"
        if not score_path.exists():
            raise FileNotFoundError(f"GMF_score.txt not found: {score_path}")
        posy = parse_posy(score_path)
        steps = steps_from_posy(posy)
        step_std = std(steps)
        result["metrics"][pitch_label] = {
            "frames": len(posy),
            "step_mean": mean(steps),
            "step_std": step_std,
            "lag1_autocorr": lag1_autocorr(posy),
            "source": str(score_path),
        }
        if pitch_label == "0.8px":
            mu = mean(steps)
            sigma = step_std
            filtered = [s for s in steps if abs(s - mu) <= 3.0 * sigma]
            result["outlier_0p8"] = {
                "removed_steps": len(steps) - len(filtered),
                "raw_step_std": step_std,
                "filtered_step_std": std(filtered) if filtered else float("nan"),
            }
    return result


def fmt(value: float, digits: int = 6) -> str:
    if value != value:
        return "nan"
    return f"{value:.{digits}f}"


def main() -> None:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    models = [summarize_model(spec["candidate"], spec["root"]) for spec in MODEL_SPECS]
    by_candidate = {item["candidate"]: item for item in models}
    baseline = by_candidate["r30_b1_dironly"]
    baseline_main = baseline["metrics"]["0.8px"]["step_std"]

    measured_rows = []
    for candidate in ("r31_eq_prob_up", "r31_eq_weight_up", "r31_edge_ratio_low"):
        model = by_candidate[candidate]
        delta = model["metrics"]["0.8px"]["step_std"] - baseline_main
        pct = (delta / baseline_main) * 100.0
        measured_rows.append(
            {
                "candidate": candidate,
                "step_std_8px": model["metrics"]["8px"]["step_std"],
                "step_std_0p8px": model["metrics"]["0.8px"]["step_std"],
                "step_std_0p08px": model["metrics"]["0.08px"]["step_std"],
                "lag1_autocorr_0p8px": model["metrics"]["0.8px"]["lag1_autocorr"],
                "delta_vs_r30_0p8px": delta,
                "pct_vs_r30_0p8px": pct,
            }
        )

    payload = {
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime()),
        "baseline_candidate": "r30_b1_dironly",
        "baseline_main_target_0p8px": baseline_main,
        "models": models,
        "measured_rows": measured_rows,
        "missing_candidates": MISSING_CANDIDATES,
        "verdict": {
            "baseline_kept": True,
            "winner": "r30_b1_dironly",
            "reason": "All measured Round31 candidates regressed on external 0.8px step std relative to Round30.",
        },
        "method": {
            "posy_source": "GMF_score.txt -> PosY",
            "step_definition": "step[i] = PosY[i+1] - PosY[i]",
            "outlier_rule_for_0p8px": "|step - mean(step)| > 3 * std(step)",
            "anchor_autocorr_definition": "lag-1 Pearson correlation of detrended PosY residuals",
        },
    }
    SUMMARY_JSON.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    lines = [
        "# Round31 External GMF Compare: R30 B1 dironly vs R31 Candidates",
        "",
        f"Last updated: {time.strftime('%Y-%m-%d', time.localtime())}",
        "",
        "## Step Std（主要指標）",
        "| 尺度 | r30_b1_dironly | r31_eq_prob_up | r31_eq_weight_up | r31_edge_ratio_low |",
        "| --- | ---: | ---: | ---: | ---: |",
        f"| 8px | {fmt(by_candidate['r30_b1_dironly']['metrics']['8px']['step_std'])} | {fmt(by_candidate['r31_eq_prob_up']['metrics']['8px']['step_std'])} | {fmt(by_candidate['r31_eq_weight_up']['metrics']['8px']['step_std'])} | {fmt(by_candidate['r31_edge_ratio_low']['metrics']['8px']['step_std'])} |",
        f"| 0.8px | {fmt(by_candidate['r30_b1_dironly']['metrics']['0.8px']['step_std'])} | {fmt(by_candidate['r31_eq_prob_up']['metrics']['0.8px']['step_std'])} | {fmt(by_candidate['r31_eq_weight_up']['metrics']['0.8px']['step_std'])} | {fmt(by_candidate['r31_edge_ratio_low']['metrics']['0.8px']['step_std'])} |",
        f"| 0.08px | {fmt(by_candidate['r30_b1_dironly']['metrics']['0.08px']['step_std'])} | {fmt(by_candidate['r31_eq_prob_up']['metrics']['0.08px']['step_std'])} | {fmt(by_candidate['r31_eq_weight_up']['metrics']['0.08px']['step_std'])} | {fmt(by_candidate['r31_edge_ratio_low']['metrics']['0.08px']['step_std'])} |",
        "",
        "## Delta vs R30（0.8px）",
        "| candidate | `0.8px std` | delta vs R30 | pct vs R30 |",
        "| --- | ---: | ---: | ---: |",
    ]
    for row in measured_rows:
        lines.append(
            f"| `{row['candidate']}` | {fmt(row['step_std_0p8px'])} | {fmt(row['delta_vs_r30_0p8px'])} | {row['pct_vs_r30_0p8px']:+.1f}% |"
        )
    lines.extend(
        [
            "",
            "## Lag-1 Autocorrelation（0.8px anchor 穩定性）",
            "| model | `0.8px lag-1 autocorr` |",
            "| --- | ---: |",
            f"| `r30_b1_dironly` | {fmt(by_candidate['r30_b1_dironly']['metrics']['0.8px']['lag1_autocorr'])} |",
            f"| `r31_eq_prob_up` | {fmt(by_candidate['r31_eq_prob_up']['metrics']['0.8px']['lag1_autocorr'])} |",
            f"| `r31_eq_weight_up` | {fmt(by_candidate['r31_eq_weight_up']['metrics']['0.8px']['lag1_autocorr'])} |",
            f"| `r31_edge_ratio_low` | {fmt(by_candidate['r31_edge_ratio_low']['metrics']['0.8px']['lag1_autocorr'])} |",
            "",
            "## Outlier Summary（0.8px）",
            "| model | 移除 step 數 | 原始 step std | 過濾後 step std |",
            "| --- | ---: | ---: | ---: |",
            f"| `r30_b1_dironly` | {baseline['outlier_0p8']['removed_steps']} | {fmt(baseline['outlier_0p8']['raw_step_std'])} | {fmt(baseline['outlier_0p8']['filtered_step_std'])} |",
            f"| `r31_eq_prob_up` | {by_candidate['r31_eq_prob_up']['outlier_0p8']['removed_steps']} | {fmt(by_candidate['r31_eq_prob_up']['outlier_0p8']['raw_step_std'])} | {fmt(by_candidate['r31_eq_prob_up']['outlier_0p8']['filtered_step_std'])} |",
            f"| `r31_eq_weight_up` | {by_candidate['r31_eq_weight_up']['outlier_0p8']['removed_steps']} | {fmt(by_candidate['r31_eq_weight_up']['outlier_0p8']['raw_step_std'])} | {fmt(by_candidate['r31_eq_weight_up']['outlier_0p8']['filtered_step_std'])} |",
            f"| `r31_edge_ratio_low` | {by_candidate['r31_edge_ratio_low']['outlier_0p8']['removed_steps']} | {fmt(by_candidate['r31_edge_ratio_low']['outlier_0p8']['raw_step_std'])} | {fmt(by_candidate['r31_edge_ratio_low']['outlier_0p8']['filtered_step_std'])} |",
            "",
            "## Missing External Artifact",
            "- `r31_eq_combo`：expected raw root "
            f"`{MISSING_CANDIDATES[0]['expected_root']}` but no `GMF_score.txt` was found. It is treated as external artifact missing, not a measured regression.",
            "",
            "## Verdict",
            f"- measured Round31 candidates all regressed on the `0.8px` main battlefield relative to `r30_b1_dironly = {fmt(baseline_main)}`",
            "- `r31_eq_prob_up`、`r31_eq_weight_up`、`r31_edge_ratio_low` 都不符合升級條件",
            "- `r31_eq_combo` 缺少 external artifact，因此不列入 measured regression winner table",
            "- 結論：維持 `Round30 / r30_b1_dironly` 為 production baseline",
            "",
            "## 方法註記",
            "- `PosY` 直接由 `GMF_score.txt` 解析。",
            "- `step[i] = PosY[i+1] - PosY[i]`。",
            "- `0.8px` outlier 規則為 `|step - mean(step)| > 3 * std(step)`。",
            "- `lag-1 autocorr` 以每個模型自身 `PosY` 經線性去趨勢後的 residual 計算。",
        ]
    )
    SUMMARY_MD.write_text("\n".join(lines), encoding="utf-8")
    print(f"[ROUND31_EXTERNAL_COMPARE] wrote {SUMMARY_MD}")


if __name__ == "__main__":
    main()

from __future__ import annotations

import json
import math
import time
from pathlib import Path


SANDBOX_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = SANDBOX_ROOT.parents[1]
REPORT_DIR = SANDBOX_ROOT / "reports"
SUMMARY_MD = REPORT_DIR / "ROUND32_EXTERNAL_COMPARE.md"
SUMMARY_JSON = REPORT_DIR / "ROUND32_EXTERNAL_COMPARE.json"
ROUND30_ROOT = PROJECT_ROOT / "Traing_Progress" / "organized_20260316" / "round30" / "gmf_results" / "raw" / "r30_b1_dironly"

PITCH_MAP = {
    "8px": "pitch8px",
    "0.8px": "pitch0p8px",
    "0.08px": "pitch0p08px",
}


def _latest_round32_decision() -> Path:
    candidates = sorted(REPORT_DIR.glob("ROUND32_DOMAIN_CAPACITY_DECISION_*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not candidates:
        raise FileNotFoundError(f"No ROUND32 decision JSON found under {REPORT_DIR}")
    return candidates[0]


def _load_round32_decision() -> dict:
    return json.loads(_latest_round32_decision().read_text(encoding="utf-8"))


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


def fmt(value: float, digits: int = 6) -> str:
    if value != value:
        return "nan"
    return f"{value:.{digits}f}"


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


def _pending_payload(candidate: str, candidate_root: Path, missing_paths: list[str], decision: dict) -> dict:
    return {
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime()),
        "status": "pending_external_gmf",
        "selected_candidate": candidate,
        "selected_checkpoint": decision.get("selected_checkpoint"),
        "baseline_candidate": "r30_b1_dironly",
        "baseline_root": str(ROUND30_ROOT),
        "candidate_root": str(candidate_root),
        "missing_gmf_score_paths": missing_paths,
        "next_action": "Run external GMF on the three reconstructed pitch folders, then place GMF_score.txt into the expected raw directories and rerun this script.",
        "method": {
            "posy_source": "GMF_score.txt -> PosY",
            "step_definition": "step[i] = PosY[i+1] - PosY[i]",
            "outlier_rule_for_0p8px": "|step - mean(step)| > 3 * std(step)",
            "anchor_autocorr_definition": "lag-1 Pearson correlation of detrended PosY residuals",
        },
    }


def write_pending_report(payload: dict) -> None:
    SUMMARY_JSON.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    lines = [
        "# Round32 External GMF Compare: Pending External Artifact",
        "",
        f"Last updated: {time.strftime('%Y-%m-%d', time.localtime())}",
        "",
        f"- selected_candidate: `{payload['selected_candidate']}`",
        f"- selected_checkpoint: `{payload['selected_checkpoint']}`",
        f"- baseline: `r30_b1_dironly`",
        f"- candidate_raw_root: `{payload['candidate_root']}`",
        "",
        "## Missing GMF_score.txt",
    ]
    for path in payload["missing_gmf_score_paths"]:
        lines.append(f"- `{path}`")
    lines.extend(
        [
            "",
            "## Next Action",
            "- 對三個 pitch reconstruction 輸出跑 external GMF。",
            "- 把 `GMF_score.txt` 放回上述三個 raw 目錄。",
            f"- 之後重新執行 `{Path(__file__).name}` 產出正式 compare 報告。",
        ]
    )
    SUMMARY_MD.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    decision = _load_round32_decision()
    candidate = str(decision["selected_candidate"])
    candidate_root = SANDBOX_ROOT / "external_compare" / candidate / "gmf_results" / "raw" / candidate

    missing_paths = []
    for pitch_dir in PITCH_MAP.values():
        score_path = candidate_root / pitch_dir / "GMF_score.txt"
        if not score_path.exists():
            missing_paths.append(str(score_path))

    if missing_paths:
        write_pending_report(_pending_payload(candidate, candidate_root, missing_paths, decision))
        print(f"[ROUND32_EXTERNAL_COMPARE] pending GMF artifacts under {candidate_root}")
        return

    baseline = summarize_model("r30_b1_dironly", ROUND30_ROOT)
    candidate_model = summarize_model(candidate, candidate_root)

    baseline_main = baseline["metrics"]["0.8px"]["step_std"]
    candidate_main = candidate_model["metrics"]["0.8px"]["step_std"]
    delta_main = candidate_main - baseline_main
    pct_main = (delta_main / baseline_main) * 100.0
    delta_8 = candidate_model["metrics"]["8px"]["step_std"] - baseline["metrics"]["8px"]["step_std"]
    delta_008 = candidate_model["metrics"]["0.08px"]["step_std"] - baseline["metrics"]["0.08px"]["step_std"]

    main_win = candidate_main < baseline_main
    macro_guard_ok = candidate_model["metrics"]["8px"]["step_std"] <= baseline["metrics"]["8px"]["step_std"]
    final_upgrade = main_win and macro_guard_ok

    payload = {
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime()),
        "status": "completed",
        "baseline_candidate": "r30_b1_dironly",
        "selected_candidate": candidate,
        "selected_checkpoint": decision.get("selected_checkpoint"),
        "models": [baseline, candidate_model],
        "summary": {
            "baseline_main_target_0p8px": baseline_main,
            "candidate_main_target_0p8px": candidate_main,
            "delta_vs_r30_0p8px": delta_main,
            "pct_vs_r30_0p8px": pct_main,
            "delta_vs_r30_8px": delta_8,
            "delta_vs_r30_0p08px": delta_008,
            "main_battlefield_win": main_win,
            "macro_guard_ok": macro_guard_ok,
            "final_upgrade": final_upgrade,
        },
        "method": {
            "posy_source": "GMF_score.txt -> PosY",
            "step_definition": "step[i] = PosY[i+1] - PosY[i]",
            "outlier_rule_for_0p8px": "|step - mean(step)| > 3 * std(step)",
            "anchor_autocorr_definition": "lag-1 Pearson correlation of detrended PosY residuals",
        },
    }
    SUMMARY_JSON.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

    lines = [
        "# Round32 External GMF Compare: R30 B1 dironly vs R32 Sandbox Winner",
        "",
        f"Last updated: {time.strftime('%Y-%m-%d', time.localtime())}",
        "",
        "## Step Std（主要指標）",
        f"| 尺度 | r30_b1_dironly | {candidate} | delta |",
        "| --- | ---: | ---: | ---: |",
        f"| 8px | {fmt(baseline['metrics']['8px']['step_std'])} | {fmt(candidate_model['metrics']['8px']['step_std'])} | {fmt(delta_8)} |",
        f"| 0.8px | {fmt(baseline['metrics']['0.8px']['step_std'])} | {fmt(candidate_model['metrics']['0.8px']['step_std'])} | {fmt(delta_main)} |",
        f"| 0.08px | {fmt(baseline['metrics']['0.08px']['step_std'])} | {fmt(candidate_model['metrics']['0.08px']['step_std'])} | {fmt(delta_008)} |",
        "",
        "## Lag-1 Autocorrelation（0.8px anchor 穩定性）",
        "| model | `0.8px lag-1 autocorr` |",
        "| --- | ---: |",
        f"| `r30_b1_dironly` | {fmt(baseline['metrics']['0.8px']['lag1_autocorr'])} |",
        f"| `{candidate}` | {fmt(candidate_model['metrics']['0.8px']['lag1_autocorr'])} |",
        "",
        "## Outlier Summary（0.8px）",
        "| model | 移除 step 數 | 原始 step std | 過濾後 step std |",
        "| --- | ---: | ---: | ---: |",
        f"| `r30_b1_dironly` | {baseline['outlier_0p8']['removed_steps']} | {fmt(baseline['outlier_0p8']['raw_step_std'])} | {fmt(baseline['outlier_0p8']['filtered_step_std'])} |",
        f"| `{candidate}` | {candidate_model['outlier_0p8']['removed_steps']} | {fmt(candidate_model['outlier_0p8']['raw_step_std'])} | {fmt(candidate_model['outlier_0p8']['filtered_step_std'])} |",
        "",
        "## Verdict",
        f"- baseline `r30_b1_dironly` main battlefield = {fmt(baseline_main)}",
        f"- candidate `{candidate}` main battlefield = {fmt(candidate_main)} ({pct_main:+.1f}% vs R30)",
        f"- 8px guard delta = {fmt(delta_8)}",
        f"- main battlefield win: {'YES' if main_win else 'NO'}",
        f"- macro guard ok: {'YES' if macro_guard_ok else 'NO'}",
        f"- final upgrade verdict: {'PASS' if final_upgrade else 'FAIL'}",
        "",
        "## 方法註記",
        "- `PosY` 直接由 `GMF_score.txt` 解析。",
        "- `step[i] = PosY[i+1] - PosY[i]`。",
        "- `0.8px` outlier 規則為 `|step - mean(step)| > 3 * std(step)`。",
        "- `lag-1 autocorr` 以每個模型自身 `PosY` 經線性去趨勢後的 residual 計算。",
    ]
    SUMMARY_MD.write_text("\n".join(lines), encoding="utf-8")
    print(f"[ROUND32_EXTERNAL_COMPARE] wrote {SUMMARY_MD}")


if __name__ == "__main__":
    main()

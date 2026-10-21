"""R40 external GMF comparison helper.

Uses the R33+ methodology: raw step_std over sorted PosY steps, with only
|z| > 5 GMF failures removed.
"""
from __future__ import annotations

import argparse
import json
import math
import statistics
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping


_REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_EXTERNAL_DIR = _REPO_ROOT / "Experiments" / "R40_MicroscopyFeatureCoverage" / "results" / "external_gmf"
DEFAULT_OUTPUT_JSON = DEFAULT_EXTERNAL_DIR / "external_compare_summary.json"
DEFAULT_REPORT_MD = _REPO_ROOT / "Experiments" / "R40_MicroscopyFeatureCoverage" / "reports" / "R40_EXTERNAL_COMPARE.md"

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


def parse_gmf_score(path: Path) -> dict[str, dict]:
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
            for idx in range(len(tokens) // 2):
                key = tokens[idx * 2]
                val = tokens[idx * 2 + 1]
                if key:
                    record[key] = val
            fname = record.get("FileName")
            pos_y = record.get("PosY")
            if not fname or pos_y is None:
                continue
            try:
                out[fname] = {
                    "pos_x": float(record.get("PosX", "nan")),
                    "pos_y": float(pos_y),
                    "score0": float(record.get("Score0", "nan")),
                }
            except ValueError:
                continue
    return out


def pos_y_series_sorted(parsed: Mapping[str, Mapping]) -> list[float]:
    return [parsed[k]["pos_y"] for k in sorted(parsed.keys())]


def _stddev_pop(values: list[float]) -> float:
    if len(values) < 2:
        return 0.0
    mean = sum(values) / len(values)
    return math.sqrt(sum((v - mean) ** 2 for v in values) / len(values))


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
    keep = []
    outliers = []
    for idx, step in enumerate(steps):
        z = 0.0 if raw_std <= 0 else (step - median_step) / raw_std
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
        else:
            keep.append(step)
    return {
        "n_pos_samples": len(pos_y),
        "n_steps": len(steps),
        "median_step": median_step,
        "raw_std": raw_std,
        "filtered_std": _stddev_pop(keep) if keep else 0.0,
        "n_outliers": len(outliers),
        "outliers": outliers,
        "z_threshold": z_threshold,
    }


@dataclass(frozen=True)
class ScaleVerdict:
    status: str
    delta: float
    delta_pct: float


def _scale_status(value: float, combo: float, upgrade_cap_pct: float) -> ScaleVerdict:
    delta = value - combo
    delta_pct = (delta / combo) * 100.0 if combo else 0.0
    if value < combo:
        status = "IMPROVED"
    elif delta_pct <= upgrade_cap_pct:
        status = "TRADEOFF_OK"
    else:
        status = "REGRESSED"
    return ScaleVerdict(status=status, delta=delta, delta_pct=delta_pct)


def verdict_against_combo(
    candidate: dict[str, float],
    combo: dict[str, float],
    *,
    upgrade_cap_pct: float = 3.0,
) -> dict:
    per_scale: dict[str, dict] = {}
    n_regressed = 0
    for scale in ("8px", "0p8px", "0p08px"):
        verdict = _scale_status(candidate[scale], combo[scale], upgrade_cap_pct)
        per_scale[scale] = {
            "candidate": candidate[scale],
            "combo": combo[scale],
            "delta": verdict.delta,
            "delta_pct": verdict.delta_pct,
            "status": verdict.status,
        }
        if verdict.status == "REGRESSED":
            n_regressed += 1
    overall = "RESEARCH_CAPACITY_ONLY" if n_regressed else "PASS_UPGRADE_GUARD"
    return {
        "overall": overall,
        "upgrade_cap_pct": float(upgrade_cap_pct),
        "per_scale": per_scale,
    }


def run_compare(
    external_dir: Path,
    *,
    candidate_name: str,
    z_threshold: float = 5.0,
    upgrade_cap_pct: float = 3.0,
) -> dict:
    rows: dict[str, dict] = {}
    step_std: dict[str, float] = {}
    for short, subdir, expected in SCALE_DIRS:
        path = external_dir / subdir / "GMF_score.txt"
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
        step_std[short] = stats["filtered_std"]
    verdict = verdict_against_combo(step_std, COMBO_EXTERNAL_STEP_STD, upgrade_cap_pct=upgrade_cap_pct)
    return {
        "candidate": candidate_name,
        "external_dir": str(external_dir),
        "scales": rows,
        "headline_step_std": step_std,
        "combo_step_std": COMBO_EXTERNAL_STEP_STD,
        "verdict": verdict,
    }


def write_markdown_report(payload: dict, report_md: Path) -> None:
    headline = payload["headline_step_std"]
    combo = payload["combo_step_std"]
    verdict = payload["verdict"]
    lines = [
        f"# R40 External GMF Compare - `{payload['candidate']}`",
        "",
        "方法:原始 step_std,只移除 `|z| > 5` 的 GMF 失敗 step。",
        "",
        "| scale | candidate step_std | COMBO step_std | delta % | status |",
        "|---|---:|---:|---:|:---:|",
    ]
    for scale in ("8px", "0p8px", "0p08px"):
        per = verdict["per_scale"][scale]
        lines.append(
            f"| {scale} | {headline[scale]:.6f} | {combo[scale]:.6f} "
            f"| {per['delta_pct']:+.2f}% | **{per['status']}** |"
        )
    lines += [
        "",
        f"整體 verdict:**{verdict['overall']}**",
        "",
        "R40 是 capacity 輪。`RESEARCH_CAPACITY_ONLY` 結果仍有研究價值,"
        "但不是升級候選。",
    ]
    report_md.parent.mkdir(parents=True, exist_ok=True)
    report_md.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="R40 external GMF compare")
    parser.add_argument("--external-dir", type=Path, default=DEFAULT_EXTERNAL_DIR)
    parser.add_argument("--candidate-name", default="r40_candidate")
    parser.add_argument("--output-json", type=Path, default=DEFAULT_OUTPUT_JSON)
    parser.add_argument("--report-md", type=Path, default=DEFAULT_REPORT_MD)
    parser.add_argument("--z-threshold", type=float, default=5.0)
    parser.add_argument("--upgrade-cap-pct", type=float, default=3.0)
    args = parser.parse_args(argv)

    payload = run_compare(
        args.external_dir,
        candidate_name=args.candidate_name,
        z_threshold=args.z_threshold,
        upgrade_cap_pct=args.upgrade_cap_pct,
    )
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    write_markdown_report(payload, args.report_md)
    print(json.dumps({
        "candidate": payload["candidate"],
        "verdict": payload["verdict"]["overall"],
        "headline_step_std": payload["headline_step_std"],
        "summary_json": str(args.output_json),
        "report_md": str(args.report_md),
    }, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

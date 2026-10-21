"""R42 external GMF comparison helper."""
from __future__ import annotations

import argparse
import json
import math
import statistics
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_EXTERNAL_DIR = REPO_ROOT / "Experiments" / "R42_MicroscopyBoundaryFidelity" / "results" / "external_gmf"
DEFAULT_OUTPUT_JSON = DEFAULT_EXTERNAL_DIR / "external_compare_summary.json"
DEFAULT_REPORT_MD = REPO_ROOT / "Experiments" / "R42_MicroscopyBoundaryFidelity" / "reports" / "R42_EXTERNAL_COMPARE.md"

SCALE_DIRS: tuple[tuple[str, str, float], ...] = (
    ("8px", "pitch8px", 8.0),
    ("0p8px", "pitch0p8px", 0.8),
    ("0p08px", "pitch0p08px", 0.08),
)

COMBO_EXTERNAL_STEP_STD = {"8px": 0.154515, "0p8px": 0.131560, "0p08px": 0.099891}


def parse_gmf_score(path: Path) -> dict[str, dict]:
    if not path.is_file():
        raise FileNotFoundError(f"GMF_score.txt not found: {path}")
    out: dict[str, dict] = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        tokens = [tok.strip() for tok in raw.split(",")]
        if len(tokens) < 4:
            continue
        record = {tokens[i]: tokens[i + 1] for i in range(0, len(tokens) - 1, 2) if tokens[i]}
        fname = record.get("FileName")
        if not fname or "PosY" not in record:
            continue
        try:
            out[fname] = {"pos_y": float(record["PosY"])}
        except ValueError:
            continue
    return out


def _stddev_pop(values: list[float]) -> float:
    if len(values) < 2:
        return 0.0
    mean = sum(values) / len(values)
    return math.sqrt(sum((v - mean) ** 2 for v in values) / len(values))


def compute_step_stats(pos_y: list[float], *, z_threshold: float = 5.0) -> dict:
    if len(pos_y) < 2:
        raise ValueError("need at least 2 PosY samples")
    steps = [pos_y[i + 1] - pos_y[i] for i in range(len(pos_y) - 1)]
    raw_std = _stddev_pop(steps)
    median_step = statistics.median(steps)
    keep = []
    outliers = []
    for idx, step in enumerate(steps):
        z = 0.0 if raw_std <= 0 else (step - median_step) / raw_std
        if abs(z) > z_threshold:
            outliers.append({"step_index": idx, "step": step, "z": z})
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
        "z_threshold": float(z_threshold),
    }


def verdict_against_combo(candidate: dict[str, float], *, cap_pct: float = 3.0) -> dict:
    per_scale = {}
    regressed = 0
    for scale, combo in COMBO_EXTERNAL_STEP_STD.items():
        value = candidate[scale]
        delta_pct = ((value - combo) / combo) * 100.0 if combo else 0.0
        if value < combo:
            status = "IMPROVED"
        elif delta_pct <= cap_pct:
            status = "TRADEOFF_OK"
        else:
            status = "REGRESSED"
            regressed += 1
        per_scale[scale] = {"candidate": value, "combo": combo, "delta_pct": delta_pct, "status": status}
    return {"overall": "PASS_UPGRADE_GUARD" if regressed == 0 else "RESEARCH_ONLY_RING_REGRESSION", "per_scale": per_scale}


def run_compare(external_dir: Path, *, candidate_name: str, z_threshold: float = 5.0, cap_pct: float = 3.0) -> dict:
    rows = {}
    headline = {}
    for short, subdir, expected in SCALE_DIRS:
        parsed = parse_gmf_score(external_dir / subdir / "GMF_score.txt")
        pos_y = [parsed[name]["pos_y"] for name in sorted(parsed)]
        stats = compute_step_stats(pos_y, z_threshold=z_threshold)
        rows[short] = {"subdir": subdir, "expected_step_px": expected, "n_frames": len(pos_y), "stats": stats}
        headline[short] = stats["filtered_std"]
    return {
        "candidate": candidate_name,
        "external_dir": str(external_dir),
        "headline_step_std": headline,
        "combo_step_std": COMBO_EXTERNAL_STEP_STD,
        "scales": rows,
        "verdict": verdict_against_combo(headline, cap_pct=cap_pct),
    }


def write_markdown_report(payload: dict, report_md: Path) -> None:
    lines = [
        f"# R42 External GMF Compare - `{payload['candidate']}`",
        "",
        "方法：原始 step_std，只移除 `|z| > 5` 的 GMF 失敗 step。",
        "",
        "| scale | R42 step_std | COMBO step_std | delta % | status |",
        "|---|---:|---:|---:|:---:|",
    ]
    for scale in ("8px", "0p8px", "0p08px"):
        per = payload["verdict"]["per_scale"][scale]
        lines.append(
            f"| {scale} | {per['candidate']:.6f} | {per['combo']:.6f} | {per['delta_pct']:+.2f}% | **{per['status']}** |"
        )
    lines += [
        "",
        f"整體 verdict：**{payload['verdict']['overall']}**",
        "",
        "R42 的主要目標是通用顯微邊界忠實度；外部環形 GMF 只決定是否可升級，不否定研究價值。",
    ]
    report_md.parent.mkdir(parents=True, exist_ok=True)
    report_md.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="R42 external GMF compare")
    parser.add_argument("--external-dir", type=Path, default=DEFAULT_EXTERNAL_DIR)
    parser.add_argument("--candidate-name", default="r42_candidate")
    parser.add_argument("--output-json", type=Path, default=DEFAULT_OUTPUT_JSON)
    parser.add_argument("--report-md", type=Path, default=DEFAULT_REPORT_MD)
    parser.add_argument("--z-threshold", type=float, default=5.0)
    parser.add_argument("--cap-pct", type=float, default=3.0)
    args = parser.parse_args(argv)

    payload = run_compare(args.external_dir, candidate_name=args.candidate_name, z_threshold=args.z_threshold, cap_pct=args.cap_pct)
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    write_markdown_report(payload, args.report_md)
    print(json.dumps({"candidate": payload["candidate"], "verdict": payload["verdict"]["overall"], "headline_step_std": payload["headline_step_std"]}, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

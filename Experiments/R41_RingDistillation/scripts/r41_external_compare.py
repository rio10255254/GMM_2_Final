"""R41 external GMF comparison helper.

Methodology stays aligned with R33+: raw step_std over sorted PosY steps, with
only |z| > 5 GMF failures removed.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
R40_SCRIPT_DIR = REPO_ROOT / "Experiments" / "R40_MicroscopyFeatureCoverage" / "scripts"
if str(R40_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(R40_SCRIPT_DIR))

from r40_external_compare import (  # noqa: E402
    COMBO_EXTERNAL_STEP_STD,
    SCALE_DIRS,
    compute_step_stats,
    parse_gmf_score,
)


DEFAULT_EXTERNAL_DIR = REPO_ROOT / "Experiments" / "R41_RingDistillation" / "results" / "external_gmf"
DEFAULT_OUTPUT_JSON = DEFAULT_EXTERNAL_DIR / "external_compare_summary.json"
DEFAULT_REPORT_MD = REPO_ROOT / "Experiments" / "R41_RingDistillation" / "reports" / "R41_EXTERNAL_COMPARE.md"

R41_MAX_STEP_STD = {
    "8px": 0.159,
    "0p8px": 0.141,
    "0p08px": 0.107,
}


def _status(scale: str, value: float) -> str:
    if value < COMBO_EXTERNAL_STEP_STD[scale]:
        return "IMPROVED"
    if value <= R41_MAX_STEP_STD[scale]:
        return "PASS"
    return "REGRESSED"


def run_compare(external_dir: Path, *, candidate_name: str, z_threshold: float = 5.0) -> dict:
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

    per_scale = {}
    for scale, value in step_std.items():
        combo = COMBO_EXTERNAL_STEP_STD[scale]
        per_scale[scale] = {
            "candidate": value,
            "combo": combo,
            "max_allowed": R41_MAX_STEP_STD[scale],
            "delta": value - combo,
            "delta_pct": ((value - combo) / combo) * 100.0 if combo else 0.0,
            "status": _status(scale, value),
        }
    overall = "PASS_PROMOTION_QUEUE" if all(v["status"] in {"IMPROVED", "PASS"} for v in per_scale.values()) else "RESEARCH_ONLY"
    return {
        "candidate": candidate_name,
        "external_dir": str(external_dir),
        "scales": rows,
        "headline_step_std": step_std,
        "combo_step_std": COMBO_EXTERNAL_STEP_STD,
        "max_allowed": R41_MAX_STEP_STD,
        "verdict": {"overall": overall, "per_scale": per_scale},
    }


def write_markdown_report(payload: dict, report_md: Path) -> None:
    headline = payload["headline_step_std"]
    verdict = payload["verdict"]
    lines = [
        f"# R41 External GMF Compare - `{payload['candidate']}`",
        "",
        "方法:原始 step_std,只移除 `|z| > 5` 的 GMF 失敗 step。",
        "",
        "| scale | candidate step_std | COMBO step_std | max allowed | delta % | status |",
        "|---|---:|---:|---:|---:|:---:|",
    ]
    for scale in ("8px", "0p8px", "0p08px"):
        per = verdict["per_scale"][scale]
        lines.append(
            f"| {scale} | {headline[scale]:.6f} | {per['combo']:.6f} | "
            f"{per['max_allowed']:.6f} | {per['delta_pct']:+.2f}% | **{per['status']}** |"
        )
    lines.extend(["", f"整體 verdict:**{verdict['overall']}**", ""])
    report_md.parent.mkdir(parents=True, exist_ok=True)
    report_md.write_text("\n".join(lines), encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Compare R41 external GMF results against COMBO.")
    parser.add_argument("--external-dir", type=Path, default=DEFAULT_EXTERNAL_DIR)
    parser.add_argument("--candidate-name", default="r41_candidate")
    parser.add_argument("--output-json", type=Path, default=DEFAULT_OUTPUT_JSON)
    parser.add_argument("--report-md", type=Path, default=DEFAULT_REPORT_MD)
    parser.add_argument("--z-threshold", type=float, default=5.0)
    args = parser.parse_args(argv)

    payload = run_compare(args.external_dir, candidate_name=args.candidate_name, z_threshold=args.z_threshold)
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    write_markdown_report(payload, args.report_md)
    print(json.dumps({"output_json": str(args.output_json), "report_md": str(args.report_md), "verdict": payload["verdict"]["overall"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

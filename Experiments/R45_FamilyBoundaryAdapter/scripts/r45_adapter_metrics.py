"""R45 adapter trial metrics and verdict helpers."""
from __future__ import annotations

import argparse
import csv
import json
import math
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
EXPERIMENT_ROOT = REPO_ROOT / "Experiments" / "R45_FamilyBoundaryAdapter"
R44_SCRIPT_DIR = REPO_ROOT / "Experiments" / "R44_UniversalBoundaryMotionFidelity" / "scripts"
if str(R44_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(R44_SCRIPT_DIR))

import r44_motion_metrics  # noqa: E402
import r44g_boundary_shape_metrics as r44g  # noqa: E402


DEFAULT_DATA_ROOT = REPO_ROOT / "Training_Data" / "r44_universal_boundary_motion"
DEFAULT_R44_RECON_ROOT = REPO_ROOT / "Experiments" / "R44_UniversalBoundaryMotionFidelity" / "results" / "motion_recon"
DEFAULT_R45_RECON_ROOT = EXPERIMENT_ROOT / "results" / "motion_recon"
DEFAULT_OUTPUT_DIR = EXPERIMENT_ROOT / "results" / "diagnostics"
BASELINE_FOLDER = "r44_motion_from_r42_best_e24"


def decide_r45_trial_verdict(
    *,
    base_target_shape: float,
    trial_target_shape: float,
    base_motion: float,
    trial_motion: float,
    min_target_shape_improvement_pct: float = 3.0,
    max_motion_regression_pct: float = 10.0,
) -> dict:
    shape_improvement = ((float(base_target_shape) - float(trial_target_shape)) / float(base_target_shape)) * 100.0
    motion_regression = ((float(trial_motion) - float(base_motion)) / float(base_motion)) * 100.0
    reasons = []
    if shape_improvement < float(min_target_shape_improvement_pct):
        reasons.append("目標形狀改善不足")
    if motion_regression > float(max_motion_regression_pct):
        reasons.append("位移退步過大")
    return {
        "is_better": not reasons,
        "reason": "；".join(reasons) if reasons else "通過初步門檻",
        "target_shape_improvement_pct": float(shape_improvement),
        "motion_regression_pct": float(motion_regression),
        "min_target_shape_improvement_pct": float(min_target_shape_improvement_pct),
        "max_motion_regression_pct": float(max_motion_regression_pct),
    }


def _safe_json(value):
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, dict):
        return {k: _safe_json(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_safe_json(v) for v in value]
    return value


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


def _target_shape_score(*, recon_root: Path, folder: str, label: str, profile: str, data_root: Path) -> dict:
    rows = r44g.collect_shape_rows(
        profile=profile,
        data_root=data_root,
        recon_root=recon_root,
        model_map={label: folder},
    )
    summary = r44g.summarize_rows(rows)
    target = r44g.summarize_target_families(summary)
    if not target:
        raise RuntimeError(f"no target-family shape rows found for {label}")
    return {"rows": rows, "summary": summary, "target": target[0]}


def evaluate_trial(
    *,
    tag: str,
    profile: str = "motion_val_unseen",
    data_root: Path = DEFAULT_DATA_ROOT,
    r44_recon_root: Path = DEFAULT_R44_RECON_ROOT,
    r45_recon_root: Path = DEFAULT_R45_RECON_ROOT,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
) -> dict:
    output_dir.mkdir(parents=True, exist_ok=True)
    base_motion = r44_motion_metrics.summarize(profile, data_root, r44_recon_root / BASELINE_FOLDER)
    trial_motion = r44_motion_metrics.summarize(profile, data_root, r45_recon_root / tag)
    base_shape = _target_shape_score(
        recon_root=r44_recon_root,
        folder=BASELINE_FOLDER,
        label="R44B from R42",
        profile=profile,
        data_root=data_root,
    )
    trial_shape = _target_shape_score(
        recon_root=r45_recon_root,
        folder=tag,
        label=tag,
        profile=profile,
        data_root=data_root,
    )
    verdict = decide_r45_trial_verdict(
        base_target_shape=float(base_shape["target"]["target_shape_error_score"]),
        trial_target_shape=float(trial_shape["target"]["target_shape_error_score"]),
        base_motion=float(base_motion["overall_motion_vector_error_px"]),
        trial_motion=float(trial_motion["overall_motion_vector_error_px"]),
    )
    payload = {
        "tag": tag,
        "profile": profile,
        "baseline": {
            "folder": BASELINE_FOLDER,
            "motion": {k: v for k, v in base_motion.items() if k != "rows"},
            "target_shape": base_shape["target"],
        },
        "trial": {
            "folder": tag,
            "motion": {k: v for k, v in trial_motion.items() if k != "rows"},
            "target_shape": trial_shape["target"],
        },
        "verdict": verdict,
    }
    (output_dir / f"{tag}_metrics.json").write_text(json.dumps(_safe_json(payload), ensure_ascii=False, indent=2), encoding="utf-8")
    _write_csv(trial_motion["rows"], output_dir / f"{tag}_motion_rows.csv")
    _write_csv(trial_shape["rows"], output_dir / f"{tag}_shape_rows.csv")
    _write_csv(trial_shape["summary"], output_dir / f"{tag}_shape_summary.csv")
    return payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Evaluate an R45 adapter reconstruction tag.")
    parser.add_argument("--tag", default="r45_oracle_adapter_large_mixed")
    parser.add_argument("--profile", default="motion_val_unseen")
    parser.add_argument("--data-root", type=Path, default=DEFAULT_DATA_ROOT)
    parser.add_argument("--r44-recon-root", type=Path, default=DEFAULT_R44_RECON_ROOT)
    parser.add_argument("--r45-recon-root", type=Path, default=DEFAULT_R45_RECON_ROOT)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    args = parser.parse_args(argv)
    payload = evaluate_trial(
        tag=args.tag,
        profile=args.profile,
        data_root=args.data_root,
        r44_recon_root=args.r44_recon_root,
        r45_recon_root=args.r45_recon_root,
        output_dir=args.output_dir,
    )
    print(json.dumps(_safe_json(payload["verdict"]), ensure_ascii=False, indent=2))
    print(f"[R45] metrics written: {args.output_dir / (args.tag + '_metrics.json')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

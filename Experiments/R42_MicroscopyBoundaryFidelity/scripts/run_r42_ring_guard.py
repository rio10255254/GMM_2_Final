"""Run the R42 local ring guard using the existing 720-angle analyzer."""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
SEQ_SCRIPT_DIR = REPO_ROOT / "AnalysisLab" / "r26" / "sequence" / "scripts"
SEQ_CONFIG_DIR = REPO_ROOT / "AnalysisLab" / "r26" / "sequence" / "configs"
sys.path.insert(0, str(SEQ_SCRIPT_DIR))
sys.path.insert(0, str(SEQ_CONFIG_DIR))

from dataset_config import DatasetConfig  # noqa: E402
import run_sequence_analysis as seq  # noqa: E402


DEFAULT_INPUT_ROOT = Path(r"C:\Users\Rio\Downloads\NTU_ImageDataset")
DEFAULT_RECON_ROOT = REPO_ROOT / "Experiments" / "R42_MicroscopyBoundaryFidelity" / "results" / "ring_recon"
DEFAULT_ANALYSIS_ROOT = REPO_ROOT / "Experiments" / "R42_MicroscopyBoundaryFidelity" / "results" / "ring_guard"
DEFAULT_COMBO_CROSS_JSON = (
    REPO_ROOT
    / "Experiments"
    / "R38v2SeqFixed"
    / "results"
    / "720angle_analysis"
    / "COMBO"
    / "cross_dataset"
    / "cross_dataset_comparison.json"
)


@dataclass(frozen=True)
class RingSpec:
    name: str
    short_name: str
    input_subdir: str
    output_name: str
    expected_step_px: float
    formal_combo_external_step_std: float


RING_SPECS: tuple[RingSpec, ...] = (
    RingSpec("Pitch1um_Y_100", "pitch1um_y_100", "Pitch1um_Y_100", "pitch1um_y_100_odd", 8.0, 0.154515),
    RingSpec("Pitch0.1um_Y_60", "pitch0p1um_y_60", "Pitch0.1um_Y_60", "pitch0p1um_y_60_odd", 0.8, 0.131560),
    RingSpec("Pitch0.01um_Y_40", "pitch0p01um_y_40", "Pitch0.01um_Y_40", "pitch0p01um_y_40_odd", 0.08, 0.099891),
)
LOCAL_RELATIVE_LIMITS = {
    "pitch1um_y_100": 0.03,
    "pitch0p1um_y_60": 0.07,
    "pitch0p01um_y_40": 0.07,
}


def find_latest_recon_run(candidate: str, recon_root: Path) -> Path:
    candidate_root = recon_root / candidate
    runs = sorted(candidate_root.glob("reconstruct_progress_*"), key=lambda p: p.name)
    if not runs:
        raise FileNotFoundError(f"no reconstruction run found under: {candidate_root}")
    return runs[-1]


def build_ring_datasets(candidate: str, recon_root: Path, *, input_root: Path = DEFAULT_INPUT_ROOT) -> list[DatasetConfig]:
    run_root = find_latest_recon_run(candidate, recon_root)
    datasets: list[DatasetConfig] = []
    missing: list[Path] = []
    for spec in RING_SPECS:
        recon_dir = run_root / spec.output_name
        if not recon_dir.is_dir():
            missing.append(recon_dir)
        datasets.append(
            DatasetConfig(
                name=spec.name,
                short_name=spec.short_name,
                input_dir=input_root / spec.input_subdir / "Cropped_Output",
                recon_dir=recon_dir,
                expected_step_px=spec.expected_step_px,
                gmf_score_path=None,
                gmf_baseline_step_std=spec.formal_combo_external_step_std,
            )
        )
    if missing:
        raise FileNotFoundError("missing reconstruction folders:\n" + "\n".join(str(p) for p in missing))
    return datasets


def _load_combo_rows(combo_cross_json: Path) -> dict[str, dict]:
    data = json.loads(combo_cross_json.read_text(encoding="utf-8"))
    rows = data.get("datasets", data)
    return {row["short_name"]: row for row in rows}


def _round_or_none(value: float | None, digits: int = 4) -> float | None:
    return None if value is None else round(float(value), digits)


def make_compact_summary(*, candidate: str, result: dict, combo_cross_json: Path = DEFAULT_COMBO_CROSS_JSON) -> dict:
    combo_by_short = _load_combo_rows(combo_cross_json)
    rows: list[dict] = []
    local_passes: list[bool] = []
    for summary in result.get("summaries", []):
        short_name = summary["short_name"]
        combo = combo_by_short.get(short_name, {})
        r42_step = float(summary["step_stability"]["output"]["internal_step_std_y"])
        combo_step = combo.get("step_stability", {}).get("output", {}).get("internal_step_std_y")
        relative_limit = LOCAL_RELATIVE_LIMITS.get(short_name)
        if combo_step is None or relative_limit is None:
            relative_delta_pct = None
            row_pass = False
        else:
            combo_float = float(combo_step)
            relative_delta_pct = None if combo_float == 0 else 100.0 * (r42_step - combo_float) / combo_float
            row_pass = r42_step <= combo_float * (1.0 + relative_limit)
        local_passes.append(row_pass)
        rows.append(
            {
                "short_name": short_name,
                "n_frames": summary.get("n_frames"),
                "expected_step_px": summary.get("expected_step_px"),
                "r42_internal_step_std_y": _round_or_none(r42_step),
                "combo_internal_step_std_y": _round_or_none(combo_step),
                "delta_internal_step_std_y": _round_or_none(None if combo_step is None else r42_step - float(combo_step)),
                "relative_delta_vs_combo_pct": _round_or_none(relative_delta_pct, 1),
                "local_guard_relative_limit_pct": _round_or_none(None if relative_limit is None else relative_limit * 100.0, 1),
                "local_guard_pass": row_pass,
            }
        )
    all_local_pass = len(local_passes) == len(RING_SPECS) and all(local_passes)
    return {
        "candidate": candidate,
        "status": (
            "local_ring_guard_pass_external_gmf_required"
            if all_local_pass
            else "local_ring_guard_failed_external_gmf_not_recommended"
        ),
        "external_gmf_required_for_promotion": all_local_pass,
        "local_ring_guard_pass": all_local_pass,
        "combo_reference": str(combo_cross_json),
        "datasets": rows,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run R42 local ring guard analysis.")
    parser.add_argument("--candidate", required=True)
    parser.add_argument("--recon-root", type=Path, default=DEFAULT_RECON_ROOT)
    parser.add_argument("--analysis-root", type=Path, default=DEFAULT_ANALYSIS_ROOT)
    parser.add_argument("--combo-cross-json", type=Path, default=DEFAULT_COMBO_CROSS_JSON)
    parser.add_argument("--summary-json", type=Path, default=None)
    parser.add_argument("--quiet", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    if args.dry_run:
        plan = {
            "candidate": args.candidate,
            "analysis_root": str(args.analysis_root),
            "ring_recon_candidate_root": str(args.recon_root / args.candidate),
            "datasets": [
                {
                    "short_name": spec.short_name,
                    "input_dir": str(DEFAULT_INPUT_ROOT / spec.input_subdir / "Cropped_Output"),
                    "expected_output_name": spec.output_name,
                    "expected_step_px": spec.expected_step_px,
                }
                for spec in RING_SPECS
            ],
        }
        print(json.dumps(plan, indent=2, ensure_ascii=False))
        return 0

    datasets = build_ring_datasets(args.candidate, args.recon_root)
    candidate_out = args.analysis_root / f"{args.candidate}_sequence_analysis"
    result = seq.main(datasets=datasets, out_root=candidate_out, verbose=not args.quiet)
    compact = make_compact_summary(candidate=args.candidate, result=result, combo_cross_json=args.combo_cross_json)
    summary_json = args.summary_json or args.analysis_root / f"{args.candidate}_ring_guard_summary.json"
    summary_json.parent.mkdir(parents=True, exist_ok=True)
    summary_json.write_text(json.dumps(compact, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({"summary_json": str(summary_json)}, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

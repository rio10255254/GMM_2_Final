"""Run the R41 local ring guard using the existing 720-angle analyzer."""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path


_REPO_ROOT = Path(__file__).resolve().parents[3]
_SEQ_SCRIPT_DIR = _REPO_ROOT / "AnalysisLab" / "r26" / "sequence" / "scripts"
_SEQ_CONFIG_DIR = _REPO_ROOT / "AnalysisLab" / "r26" / "sequence" / "configs"
sys.path.insert(0, str(_SEQ_SCRIPT_DIR))
sys.path.insert(0, str(_SEQ_CONFIG_DIR))

from dataset_config import DatasetConfig
import run_sequence_analysis as seq


DEFAULT_INPUT_ROOT = Path(r"C:\Users\Rio\Downloads\NTU_ImageDataset")
DEFAULT_RECON_ROOT = _REPO_ROOT / "Experiments" / "R41_RingDistillation" / "results" / "ring_recon"
DEFAULT_ANALYSIS_ROOT = _REPO_ROOT / "Experiments" / "R41_RingDistillation" / "results" / "ring_guard"
DEFAULT_COMBO_CROSS_JSON = (
    _REPO_ROOT
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


def _formal_combo_external(short_name: str) -> float | None:
    for spec in RING_SPECS:
        if spec.short_name == short_name:
            return spec.formal_combo_external_step_std
    return None


def make_compact_summary(*, candidate: str, result: dict, combo_cross_json: Path = DEFAULT_COMBO_CROSS_JSON) -> dict:
    combo_by_short = _load_combo_rows(combo_cross_json)
    rows: list[dict] = []
    for summary in result.get("summaries", []):
        short_name = summary["short_name"]
        combo = combo_by_short.get(short_name, {})
        r41_step = float(summary["step_stability"]["output"]["internal_step_std_y"])
        combo_step = combo.get("step_stability", {}).get("output", {}).get("internal_step_std_y")
        delta_step = None if combo_step is None else r41_step - float(combo_step)
        r41_residual = summary.get("residual_consistency", {})
        combo_residual = combo.get("residual_consistency", {})
        rows.append(
            {
                "short_name": short_name,
                "n_frames": summary.get("n_frames"),
                "expected_step_px": summary.get("expected_step_px"),
                "r41_input_step_std_y": _round_or_none(summary["step_stability"]["input"]["internal_step_std_y"]),
                "r41_internal_step_std_y": _round_or_none(r41_step),
                "combo_internal_step_std_y": _round_or_none(combo_step),
                "delta_internal_step_std_y": _round_or_none(delta_step),
                "formal_combo_external_step_std": _formal_combo_external(short_name),
                "r41_outer_residual_mean": _round_or_none(r41_residual.get("outer", {}).get("output_mean")),
                "combo_outer_residual_mean": _round_or_none(combo_residual.get("outer", {}).get("output_mean")),
                "r41_inner_residual_mean": _round_or_none(r41_residual.get("inner", {}).get("output_mean")),
                "combo_inner_residual_mean": _round_or_none(combo_residual.get("inner", {}).get("output_mean")),
            }
        )
    return {
        "candidate": candidate,
        "status": "local_ring_guard_complete_external_gmf_pending",
        "external_gmf_required": True,
        "external_gmf_note": "Promotion still requires external GMF_score.txt for R41 outputs.",
        "combo_reference": str(combo_cross_json),
        "datasets": rows,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run R41 local ring guard analysis.")
    parser.add_argument("--candidate", required=True)
    parser.add_argument("--recon-root", type=Path, default=DEFAULT_RECON_ROOT)
    parser.add_argument("--analysis-root", type=Path, default=DEFAULT_ANALYSIS_ROOT)
    parser.add_argument("--combo-cross-json", type=Path, default=DEFAULT_COMBO_CROSS_JSON)
    parser.add_argument("--summary-json", type=Path, default=None)
    parser.add_argument("--quiet", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    if args.dry_run:
        candidate_root = args.recon_root / args.candidate
        plan = {
            "candidate": args.candidate,
            "analysis_root": str(args.analysis_root),
            "ring_recon_candidate_root": str(candidate_root),
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
    plan = {
        "candidate": args.candidate,
        "analysis_root": str(args.analysis_root),
        "datasets": [
            {
                "short_name": ds.short_name,
                "input_dir": str(ds.input_dir),
                "recon_dir": str(ds.recon_dir),
                "expected_step_px": ds.expected_step_px,
            }
            for ds in datasets
        ],
    }
    print(json.dumps(plan, indent=2, ensure_ascii=False))
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

"""Run the R54 edge-band probe on the real Lab checkboard sequence."""
from __future__ import annotations

import argparse
import importlib.util
import json
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path


LAB_ROOT = Path(__file__).resolve().parents[3]
CHECKBOARD_DIR = (LAB_ROOT.parent / 'Thesis_MOSR_Evidence') / "20250605_checkboard"
TRAINING_ROOT = LAB_ROOT / "Traing_Progress"
RECON_PREP_ROOT = LAB_ROOT / "Reconstruct_Progress" / "20250605_checkboard_external_gmf_prepare"
RECON_OUTPUT_ROOT = RECON_PREP_ROOT / "r54_reconstruction_outputs"
GMF_CASES_ROOT = RECON_PREP_ROOT / "gmf_cases"
INFER_SCRIPT = LAB_ROOT / "scripts" / "GeoEdgeAlignSR_v1_Infer_v5_NoCoord_return_v2_SimpleTest.py"
LAB_PSF_PATH = (
    LAB_ROOT
    / "psf_calibration"
    / "results"
    / "20250605_inner_circle_roi_fine_prealign_fit"
    / "PSF_fitted_2D_FOVstack.mat"
)

DEFAULT_CANDIDATES = ("r54_masked_overfit_from_r40_edgeband_e020",)

CANDIDATE_CONFIG = {
    "r54_masked_overfit_from_r40_edgeband_e020": {
        "run_pattern": "training_progress_*r54_masked_overfit_from_r40_edgeband_e020_*",
        "case_name": "lab_r54_edgeband_epoch020",
        "checkpoint_kind": "epoch020",
        "checkpoint_file": "epoch_020.pth.tar",
    },
}


@dataclass(frozen=True)
class CaseSpec:
    candidate: str
    case_name: str
    checkpoint_kind: str
    run_dir: Path
    weights: Path


def _latest_run_dir(training_root: Path, pattern: str) -> Path:
    matches = sorted(
        (p for p in Path(training_root).glob(pattern) if p.is_dir()),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    if not matches:
        raise FileNotFoundError(f"no R54 run matching {pattern} under {training_root}")
    return matches[0]


def build_case_specs(
    training_root: Path = TRAINING_ROOT,
    candidates: list[str] | tuple[str, ...] = DEFAULT_CANDIDATES,
) -> list[CaseSpec]:
    specs: list[CaseSpec] = []
    for candidate in candidates:
        if candidate not in CANDIDATE_CONFIG:
            raise ValueError(f"unknown R54 candidate: {candidate}")
        config = CANDIDATE_CONFIG[candidate]
        run_dir = _latest_run_dir(Path(training_root), str(config["run_pattern"]))
        weights = run_dir / str(config["checkpoint_file"])
        if not weights.exists():
            raise FileNotFoundError(weights)
        specs.append(
            CaseSpec(
                candidate=candidate,
                case_name=str(config["case_name"]),
                checkpoint_kind=str(config["checkpoint_kind"]),
                run_dir=run_dir,
                weights=weights,
            )
        )
    return specs


def build_infer_argv(spec: CaseSpec, input_dir: Path, recon_root: Path, device: str) -> list[str]:
    return [
        "--weights",
        str(spec.weights),
        "--input-dir",
        str(input_dir),
        "--recon-root",
        str(recon_root),
        "--output-name",
        spec.case_name,
        "--select-mode",
        "all",
        "--device",
        device,
        "--psf-fitted-path",
        str(LAB_PSF_PATH),
        "--no-psf-from-ckpt",
    ]


def _load_infer_module():
    spec = importlib.util.spec_from_file_location("lab_r54_infer_runtime", INFER_SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"could not load inference script: {INFER_SCRIPT}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    module.MANUAL_WEIGHTS_PATH = None
    module.MANUAL_SELECT_MODE = None
    return module


def _latest_case_output(recon_root: Path, case_name: str) -> Path:
    matches = sorted(
        (p for p in recon_root.glob(f"reconstruct_progress_*\\{case_name}") if p.is_dir()),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    if not matches:
        matches = sorted(
            (p for p in recon_root.glob(f"reconstruct_progress_*/{case_name}") if p.is_dir()),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
    if not matches:
        raise FileNotFoundError(f"no reconstruction output found for {case_name} under {recon_root}")
    return matches[0]


def _safe_remove_case_dir(path: Path) -> None:
    resolved = path.resolve()
    root = GMF_CASES_ROOT.resolve()
    if resolved == root:
        raise ValueError("refusing to remove GMF cases root")
    if not str(resolved).lower().startswith(str(root).lower()):
        raise ValueError(f"refusing to remove outside GMF cases root: {resolved}")
    if path.exists():
        shutil.rmtree(path)


def sync_case_to_gmf(output_dir: Path, case_name: str) -> dict[str, object]:
    files = sorted(Path(output_dir).glob("*.bmp"))
    if not files:
        raise FileNotFoundError(f"no BMP outputs found in {output_dir}")
    case_dir = GMF_CASES_ROOT / case_name
    _safe_remove_case_dir(case_dir)
    case_dir.mkdir(parents=True, exist_ok=True)
    for path in files:
        shutil.copy2(path, case_dir / path.name)
    return {
        "case_name": case_name,
        "source_dir": str(output_dir),
        "gmf_case_dir": str(case_dir),
        "bmp_count": len(files),
    }


def run_case(spec: CaseSpec, *, input_dir: Path, recon_root: Path, device: str) -> dict[str, object]:
    module = _load_infer_module()
    old_argv = sys.argv[:]
    try:
        sys.argv = [str(INFER_SCRIPT)] + build_infer_argv(spec, input_dir, recon_root, device)
        module.main()
    finally:
        sys.argv = old_argv
    output_dir = _latest_case_output(recon_root, spec.case_name)
    sync = sync_case_to_gmf(output_dir, spec.case_name)
    return {
        "candidate": spec.candidate,
        "checkpoint_kind": spec.checkpoint_kind,
        "weights": str(spec.weights),
        **sync,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run R54 checkboard reconstruction and sync GMF case.")
    parser.add_argument("--candidate", action="append", choices=sorted(DEFAULT_CANDIDATES), default=None)
    parser.add_argument("--checkpoint-kind", choices=["epoch020"], default="epoch020")
    parser.add_argument("--device", default="cuda:0")
    parser.add_argument("--input-dir", type=Path, default=CHECKBOARD_DIR)
    parser.add_argument("--recon-root", type=Path, default=RECON_OUTPUT_ROOT)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    candidates = args.candidate or list(DEFAULT_CANDIDATES)
    specs = build_case_specs(TRAINING_ROOT, candidates)
    specs = [spec for spec in specs if spec.checkpoint_kind == args.checkpoint_kind]

    payload = [
        {
            "candidate": spec.candidate,
            "case_name": spec.case_name,
            "checkpoint_kind": spec.checkpoint_kind,
            "run_dir": str(spec.run_dir),
            "weights": str(spec.weights),
        }
        for spec in specs
    ]
    if args.dry_run:
        print(json.dumps({"cases": payload}, indent=2, ensure_ascii=False))
        return 0

    results = []
    for spec in specs:
        print(f"[R54][reconstruct] {spec.case_name} <- {spec.weights}")
        results.append(run_case(spec, input_dir=args.input_dir, recon_root=args.recon_root, device=args.device))

    print(json.dumps({"reconstructed": results}, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

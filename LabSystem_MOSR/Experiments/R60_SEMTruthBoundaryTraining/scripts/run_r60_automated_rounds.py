"""Automate R60 training, reconstruction, CD measurement, and CD-based selection."""
from __future__ import annotations

import argparse
import csv
import json
import subprocess
import sys
from dataclasses import dataclass, replace
from datetime import datetime
from pathlib import Path
from typing import Iterable


EXPERIMENT_DIR = Path(__file__).resolve().parents[1]
LAB_ROOT = Path(__file__).resolve().parents[3]
PROJECT_ROOT = Path(__file__).resolve().parents[4]
MODEL_DIR = PROJECT_ROOT / "Model"
LAUNCH_R60 = EXPERIMENT_DIR / "scripts" / "launch_r60.py"
INFER_SCRIPT = MODEL_DIR / "GeoEdgeAlignSR_v1_Infer_v5_NoCoord_return_v2_SimpleTest.py"
MEASURE_CD_SCRIPT = LAB_ROOT / "Experiments" / "R57_GeometryConstrainedMOSR" / "scripts" / "measure_r57_cd_from_template.py"
TRAINING_PROGRESS_ROOT = LAB_ROOT / "Traing_Progress"
RECON_ROOT = LAB_ROOT / "Reconstruct_Progress" / "20260618_100MG_user_recon"
INPUT_DIR = (LAB_ROOT.parent / 'Thesis_MOSR_Evidence') / "20260618_100MG"
LAB_PSF_PATH = (
    LAB_ROOT
    / "psf_calibration"
    / "results"
    / "20250605_inner_circle_roi_fine_prealign_fit"
    / "PSF_fitted_2D_FOVstack.mat"
)
REFERENCE_SUMMARY_CSV = (
    RECON_ROOT
    / "cd_measurement_20260620_basler_ace"
    / "cd_measurement_summary_basler_50x.csv"
)
DEFAULT_TARGET_IMAGE = "Image__2026-06-18__17-10-31.bmp"
DEFAULT_REPORT_ROOT = EXPERIMENT_DIR / "reports" / "r60_automated_rounds"
DEFAULT_CANDIDATE = "r60_semtruth_realcrop_anchor"
DEFAULT_PROFILE = "r60_sem_truth_realcrop_anchor_train"


@dataclass(frozen=True)
class CheckpointCandidate:
    label: str
    path: Path


@dataclass(frozen=True)
class MeasurementResult:
    label: str
    checkpoint_label: str
    summary_csv: Path
    reconstructed_image: Path | None = None
    checkpoint_path: Path | None = None
    mean_abs_radius_error_nm: float = float("nan")
    feature_errors_nm: dict[str, float] | None = None
    reference_mean_abs_radius_error_nm: float = float("nan")
    beats_reference: bool = False


def _python() -> str:
    return sys.executable or "python"


def _read_csv(path: Path) -> list[dict]:
    if not Path(path).exists():
        raise FileNotFoundError(path)
    with Path(path).open("r", newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def _to_float(value: object, default: float = float("nan")) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _rows_for_image(summary_csv: Path, image_label: str | None = None) -> list[dict]:
    rows = _read_csv(summary_csv)
    if image_label is None:
        return rows
    return [row for row in rows if str(row.get("image", "")).strip() == str(image_label).strip()]


def _error_map(summary_csv: Path, image_label: str | None = None) -> dict[str, float]:
    rows = _rows_for_image(summary_csv, image_label)
    out: dict[str, float] = {}
    for row in rows:
        feature = str(row.get("feature", "")).strip()
        if not feature:
            continue
        err = _to_float(row.get("abs_radius_error_vs_sem_nm"))
        if err == err:
            out[feature] = float(err)
    if not out:
        raise RuntimeError(f"no CD feature errors found in {summary_csv}")
    return out


def _mean_error(errors: dict[str, float]) -> float:
    vals = list(errors.values())
    return float(sum(vals) / len(vals)) if vals else float("nan")


def discover_checkpoints(run_dir: Path, mode: str = "all") -> list[CheckpointCandidate]:
    run_dir = Path(run_dir)
    weight_dir = run_dir / "weights"
    candidates: list[CheckpointCandidate] = []
    fixed = [
        ("best_tradeoff", weight_dir / "best_tradeoff.pth.tar"),
        ("latest", weight_dir / "latest.pth.tar"),
    ]
    if mode in {"all", "best", "best_latest"}:
        candidates.extend(CheckpointCandidate(label, path) for label, path in fixed[:1] if path.exists())
    if mode in {"all", "latest", "best_latest"}:
        candidates.extend(CheckpointCandidate(label, path) for label, path in fixed[1:] if path.exists())
    if mode in {"all", "epochs"}:
        for path in sorted(run_dir.glob("epoch_*.pth.tar")):
            candidates.append(CheckpointCandidate(path.stem.replace(".pth", ""), path))

    seen: set[Path] = set()
    out: list[CheckpointCandidate] = []
    for item in candidates:
        resolved = item.path.resolve()
        if resolved in seen:
            continue
        seen.add(resolved)
        out.append(item)
    if not out:
        raise FileNotFoundError(f"no checkpoints found for mode={mode!r} in {run_dir}")
    return out


def find_latest_training_run(training_label: str, *, progress_root: Path = TRAINING_PROGRESS_ROOT) -> Path:
    progress_root = Path(progress_root)
    prefix = f"training_progress_LAB_GESR_v1_v5_ST0p8_SWP_{training_label}"
    candidates = [p for p in progress_root.glob(prefix + "*") if p.is_dir()]
    if not candidates:
        raise FileNotFoundError(f"no training run found for {training_label} under {progress_root}")
    return max(candidates, key=lambda p: p.stat().st_mtime)


def build_train_command(
    *,
    candidate: str,
    num_epoch: int,
    batch_size: int,
    val_batch_size: int,
    num_workers: int,
    max_train_batches: int | None,
    run_suffix: str,
    device: str,
) -> list[str]:
    command = [
        _python(),
        "-u",
        str(LAUNCH_R60),
        "--candidate",
        str(candidate),
        "--num-epoch",
        str(int(num_epoch)),
        "--batch-size",
        str(int(batch_size)),
        "--val-batch-size",
        str(int(val_batch_size)),
        "--num-workers",
        str(int(num_workers)),
        "--run-suffix",
        str(run_suffix),
        "--device",
        str(device),
    ]
    if max_train_batches is not None:
        command.extend(["--max-train-batches", str(int(max_train_batches))])
    return command


def build_reconstruct_command(
    *,
    checkpoint: Path,
    output_name: str,
    input_dir: Path,
    recon_root: Path,
    device: str,
) -> list[str]:
    return [
        _python(),
        "-u",
        str(INFER_SCRIPT),
        "--weights",
        str(Path(checkpoint)),
        "--input-dir",
        str(Path(input_dir)),
        "--recon-root",
        str(Path(recon_root)),
        "--output-name",
        str(output_name),
        "--device",
        str(device),
        "--align-factor",
        "64",
        "--exts",
        ".bmp",
        "--psf-fitted-path",
        str(LAB_PSF_PATH),
        "--no-psf-from-ckpt",
        "--weak-psf-disable",
        "--psf-deconv-reg",
        "30.0",
        "--psf-phys-alpha",
        "0.0",
    ]


def build_measure_command(*, candidate_image: Path, candidate_label: str, output_dir: Path) -> list[str]:
    return [
        _python(),
        "-u",
        str(MEASURE_CD_SCRIPT),
        "--candidate-image",
        str(Path(candidate_image)),
        "--candidate-label",
        str(candidate_label),
        "--output-dir",
        str(Path(output_dir)),
    ]


def find_reconstructed_image(*, recon_root: Path, output_name: str, target_image: str = DEFAULT_TARGET_IMAGE) -> Path:
    recon_root = Path(recon_root)
    direct = sorted(recon_root.glob(f"*/{output_name}/{target_image}"), key=lambda p: p.stat().st_mtime, reverse=True)
    if direct:
        return direct[0]
    fallback = [
        p
        for p in recon_root.rglob(target_image)
        if p.parent.name == output_name or output_name in str(p.parent)
    ]
    if fallback:
        return max(fallback, key=lambda p: p.stat().st_mtime)
    raise FileNotFoundError(f"no reconstructed {target_image} found for output {output_name} under {recon_root}")


def rank_cd_results(
    results: Iterable[MeasurementResult],
    *,
    reference_summary_csv: Path = REFERENCE_SUMMARY_CSV,
    reference_image: str = "原圖",
) -> list[MeasurementResult]:
    reference_errors = _error_map(Path(reference_summary_csv), reference_image)
    reference_mean = _mean_error(reference_errors)
    ranked: list[MeasurementResult] = []
    for result in results:
        errors = _error_map(Path(result.summary_csv), result.label)
        mean_error = _mean_error(errors)
        shared = set(reference_errors).intersection(errors)
        beats = bool(shared) and all(errors[feature] <= reference_errors[feature] for feature in shared)
        ranked.append(
            replace(
                result,
                mean_abs_radius_error_nm=mean_error,
                feature_errors_nm=errors,
                reference_mean_abs_radius_error_nm=reference_mean,
                beats_reference=beats,
            )
        )
    return sorted(ranked, key=lambda item: item.mean_abs_radius_error_nm)


def _run_command(command: list[str], *, log_path: Path) -> None:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    proc = subprocess.run(command, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    log_path.write_text(proc.stdout, encoding="utf-8")
    if proc.returncode != 0:
        raise RuntimeError(f"command failed with code {proc.returncode}: {log_path}")


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def _write_markdown_report(path: Path, payload: dict) -> None:
    lines = [
        "# R60 Automated Round Status",
        "",
        f"- Generated at: {payload['generated_at']}",
        f"- Training run: `{payload.get('training_run_dir', '')}`",
        f"- Reference mean abs radius error: {payload.get('reference_mean_abs_radius_error_nm', float('nan')):.2f} nm",
        "",
        "| Rank | Candidate | Checkpoint | Mean abs radius error (nm) | Beats original |",
        "| ---: | --- | --- | ---: | --- |",
    ]
    for idx, item in enumerate(payload.get("ranked_results", []), start=1):
        lines.append(
            f"| {idx} | {item['label']} | {item['checkpoint_label']} | "
            f"{float(item['mean_abs_radius_error_nm']):.2f} | {item['beats_reference']} |"
        )
    lines.append("")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def run_round(args: argparse.Namespace) -> dict:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_root = Path(args.report_root) / str(args.round_name or f"r60_round_{timestamp}")
    logs_dir = report_root / "logs"
    measurement_root = report_root / "measurements"

    training_label = str(args.training_label or "")
    training_run_dir: Path
    if args.train:
        suffix = str(args.run_suffix or f"auto_{timestamp}")
        train_command = build_train_command(
            candidate=str(args.candidate),
            num_epoch=int(args.num_epoch),
            batch_size=int(args.batch_size),
            val_batch_size=int(args.val_batch_size),
            num_workers=int(args.num_workers),
            max_train_batches=args.max_train_batches,
            run_suffix=suffix,
            device=str(args.device),
        )
        _run_command(train_command, log_path=logs_dir / "train.log")
        training_label = f"{args.candidate}_{suffix}"
        training_run_dir = find_latest_training_run(training_label)
    elif args.run_dir is not None:
        training_run_dir = Path(args.run_dir)
        training_label = training_run_dir.name.removeprefix("training_progress_LAB_GESR_v1_v5_ST0p8_SWP_")
    else:
        if not training_label:
            raise ValueError("--training-label or --run-dir is required when --train is not set")
        training_run_dir = find_latest_training_run(training_label)

    checkpoints = discover_checkpoints(training_run_dir, mode=str(args.checkpoint_mode))
    measured: list[MeasurementResult] = []
    for checkpoint in checkpoints:
        safe_label = f"{training_label}_{checkpoint.label}"
        output_name = f"r60_auto_{safe_label}_psf_off"
        candidate_label = f"R60_auto_{safe_label}"
        if args.reconstruct:
            recon_command = build_reconstruct_command(
                checkpoint=checkpoint.path,
                output_name=output_name,
                input_dir=Path(args.input_dir),
                recon_root=Path(args.recon_root),
                device=str(args.device),
            )
            _run_command(recon_command, log_path=logs_dir / f"reconstruct_{checkpoint.label}.log")
        image_path = find_reconstructed_image(recon_root=Path(args.recon_root), output_name=output_name)
        output_dir = measurement_root / checkpoint.label
        if args.measure:
            measure_command = build_measure_command(
                candidate_image=image_path,
                candidate_label=candidate_label,
                output_dir=output_dir,
            )
            _run_command(measure_command, log_path=logs_dir / f"measure_{checkpoint.label}.log")
        measured.append(
            MeasurementResult(
                label=candidate_label,
                checkpoint_label=checkpoint.label,
                checkpoint_path=checkpoint.path,
                reconstructed_image=image_path,
                summary_csv=output_dir / "cd_measurement_summary.csv",
            )
        )

    ranked = rank_cd_results(
        measured,
        reference_summary_csv=Path(args.reference_summary_csv),
        reference_image=str(args.reference_image),
    )
    payload = {
        "generated_at": datetime.now().replace(microsecond=0).isoformat(),
        "training_run_dir": str(training_run_dir),
        "training_label": training_label,
        "checkpoint_mode": str(args.checkpoint_mode),
        "reference_summary_csv": str(Path(args.reference_summary_csv)),
        "reference_image": str(args.reference_image),
        "reference_mean_abs_radius_error_nm": ranked[0].reference_mean_abs_radius_error_nm if ranked else float("nan"),
        "ranked_results": [
            {
                "label": item.label,
                "checkpoint_label": item.checkpoint_label,
                "checkpoint_path": str(item.checkpoint_path) if item.checkpoint_path else "",
                "reconstructed_image": str(item.reconstructed_image) if item.reconstructed_image else "",
                "summary_csv": str(item.summary_csv),
                "mean_abs_radius_error_nm": item.mean_abs_radius_error_nm,
                "feature_errors_nm": item.feature_errors_nm,
                "beats_reference": item.beats_reference,
            }
            for item in ranked
        ],
    }
    _write_json(report_root / "R60_AUTOMATED_ROUNDS_STATUS.json", payload)
    _write_markdown_report(report_root / "R60_AUTOMATED_ROUNDS_STATUS.md", payload)
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    if ranked and ranked[0].beats_reference:
        return payload
    if not args.allow_fail:
        raise SystemExit(2)
    return payload


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run R60 automated training/reconstruction/CD validation rounds")
    parser.add_argument("--candidate", default=DEFAULT_CANDIDATE)
    parser.add_argument("--train", action="store_true")
    parser.add_argument("--reconstruct", action="store_true")
    parser.add_argument("--measure", action="store_true")
    parser.add_argument("--allow-fail", action="store_true")
    parser.add_argument("--run-dir", type=Path, default=None)
    parser.add_argument("--training-label", default="")
    parser.add_argument("--round-name", default="")
    parser.add_argument("--run-suffix", default="")
    parser.add_argument("--num-epoch", type=int, default=4)
    parser.add_argument("--max-train-batches", type=int, default=None)
    parser.add_argument("--batch-size", type=int, default=2)
    parser.add_argument("--val-batch-size", type=int, default=1)
    parser.add_argument("--num-workers", type=int, default=0)
    parser.add_argument("--device", default="cuda:0")
    parser.add_argument("--checkpoint-mode", choices=("all", "best", "latest", "best_latest", "epochs"), default="best_latest")
    parser.add_argument("--input-dir", type=Path, default=INPUT_DIR)
    parser.add_argument("--recon-root", type=Path, default=RECON_ROOT)
    parser.add_argument("--reference-summary-csv", type=Path, default=REFERENCE_SUMMARY_CSV)
    parser.add_argument("--reference-image", default="原圖")
    parser.add_argument("--report-root", type=Path, default=DEFAULT_REPORT_ROOT)
    return parser


def main(argv: Iterable[str] | None = None) -> int:
    args = build_arg_parser().parse_args(list(argv) if argv is not None else None)
    run_round(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

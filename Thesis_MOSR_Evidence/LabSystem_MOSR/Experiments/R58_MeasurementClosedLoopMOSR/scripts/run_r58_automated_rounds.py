"""Run automated R58 measurement-closed-loop training and CD validation rounds."""
from __future__ import annotations

import argparse
import csv
import json
import subprocess
import sys
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable


SCRIPT_DIR = Path(__file__).resolve().parent
EXPERIMENT_DIR = SCRIPT_DIR.parent
LAB_ROOT = EXPERIMENT_DIR.parents[1]
PROJECT_ROOT = EXPERIMENT_DIR.parents[3]
MODEL_DIR = PROJECT_ROOT / "Model"

LAUNCH_R58 = SCRIPT_DIR / "launch_r58.py"
PREPARE_R58 = SCRIPT_DIR / "prepare_r58_measurement_dataset.py"
INFER_SCRIPT = MODEL_DIR / "GeoEdgeAlignSR_v1_Infer_v5_NoCoord_return_v2_SimpleTest.py"
MEASURE_CD_SCRIPT = (
    EXPERIMENT_DIR.parent
    / "R57_GeometryConstrainedMOSR"
    / "scripts"
    / "measure_r57_cd_from_template.py"
)

TRAINING_PROGRESS_ROOT = LAB_ROOT / "Traing_Progress"
DEFAULT_DATA_ROOT = LAB_ROOT / "Training_Data" / "r58_measurement_closed_loop" / "hs100mg_basler"
DEFAULT_INPUT_DIR = LAB_ROOT.parent / "20260618_100MG"
DEFAULT_RECON_ROOT = LAB_ROOT / "Reconstruct_Progress" / "20260618_100MG_user_recon"
DEFAULT_OUTPUT_ROOT = EXPERIMENT_DIR / "reports" / "r58_automated_rounds"
DEFAULT_TARGET_IMAGE = "Image__2026-06-18__17-10-31.bmp"
REFERENCE_ORIGINAL_MEAN_ABS_RADIUS_ERROR_NM = 38.59
LAB_PSF_PATH = (
    LAB_ROOT
    / "psf_calibration"
    / "results"
    / "20250605_inner_circle_roi_fine_prealign_fit"
    / "PSF_fitted_2D_FOVstack.mat"
)

sys.path.insert(0, str(SCRIPT_DIR))
from launch_r58 import CANDIDATE_SETTINGS, PROFILE_BY_CANDIDATE  # noqa: E402


@dataclass(frozen=True)
class CandidatePlan:
    candidate: str
    profile: str
    training_label: str
    correction_fraction: float
    data_package: str
    train_command: list[str]
    reconstruct_command: list[str] | None = None
    measure_command: list[str] | None = None
    checkpoint: str | None = None
    reconstructed_image: str | None = None
    summary_csv: str | None = None


def _safe_suffix(value: str) -> str:
    value = str(value or "").strip()
    return "".join(ch if ch.isalnum() or ch in {"_", "-"} else "_" for ch in value)


def _timestamp() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def _python() -> str:
    return sys.executable or "python"


def _read_csv(path: Path) -> list[dict]:
    with Path(path).open("r", newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def _command_to_text(command: Iterable[str]) -> str:
    return subprocess.list2cmdline([str(part) for part in command])


def build_candidate_plans(
    *,
    candidates: list[str],
    num_epoch: int,
    max_train_batches: int | None,
    batch_size: int,
    run_suffix: str,
    data_root: Path,
    output_root: Path,
    device: str,
    val_batch_size: int = 1,
    num_workers: int = 1,
    val_ratio: float = 0.02,
    seq_batch_size: int = 1,
) -> list[CandidatePlan]:
    del output_root
    safe_run_suffix = _safe_suffix(run_suffix)
    plans: list[CandidatePlan] = []
    for candidate in candidates:
        if candidate not in PROFILE_BY_CANDIDATE:
            raise ValueError(f"unknown R58 candidate: {candidate}")
        profile = PROFILE_BY_CANDIDATE[candidate]
        training_label = candidate if not safe_run_suffix else f"{candidate}_{safe_run_suffix}"
        command = [
            _python(),
            "-u",
            str(LAUNCH_R58),
            "--candidate",
            candidate,
            "--num-epoch",
            str(int(num_epoch)),
            "--device",
            str(device),
            "--data-root",
            str(Path(data_root)),
            "--run-suffix",
            safe_run_suffix,
            "--batch-size",
            str(int(batch_size)),
            "--val-batch-size",
            str(int(val_batch_size)),
            "--num-workers",
            str(int(num_workers)),
            "--val-ratio",
            str(float(val_ratio)),
            "--seq-batch-size",
            str(int(seq_batch_size)),
        ]
        if max_train_batches is not None:
            command.extend(["--max-train-batches", str(int(max_train_batches))])
        plans.append(
            CandidatePlan(
                candidate=candidate,
                profile=profile,
                training_label=training_label,
                correction_fraction=float(CANDIDATE_SETTINGS[candidate]["correction_fraction"]),
                data_package=str(Path(data_root) / profile),
                train_command=command,
            )
        )
    return plans


def build_prepare_commands(
    *,
    candidates: list[str],
    data_root: Path,
    base_limit: int,
    anchor_count: int,
    image_size: int,
    link_mode: str,
    seed_base: int,
) -> list[list[str]]:
    commands: list[list[str]] = []
    for offset, candidate in enumerate(candidates):
        if candidate not in PROFILE_BY_CANDIDATE:
            raise ValueError(f"unknown R58 candidate: {candidate}")
        settings = CANDIDATE_SETTINGS[candidate]
        commands.append(
            [
                _python(),
                "-u",
                str(PREPARE_R58),
                "--output-root",
                str(Path(data_root)),
                "--package-name",
                str(settings["profile"]),
                "--base-limit",
                str(int(base_limit)),
                "--anchor-count",
                str(int(anchor_count)),
                "--image-size",
                str(int(image_size)),
                "--correction-fraction",
                str(float(settings["correction_fraction"])),
                "--link-mode",
                str(link_mode),
                "--seed",
                str(int(seed_base) + offset),
            ]
        )
    return commands


def _run_command(command: list[str], *, cwd: Path, log_path: Path, dry_run: bool) -> dict:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    result = {
        "command": [str(part) for part in command],
        "log": str(log_path),
        "cwd": str(cwd),
        "dry_run": bool(dry_run),
        "returncode": None,
    }
    if dry_run:
        log_path.write_text(_command_to_text(command) + "\n", encoding="utf-8")
        result["returncode"] = 0
        return result

    with log_path.open("w", encoding="utf-8") as log:
        log.write(_command_to_text(command) + "\n\n")
        log.flush()
        proc = subprocess.run(
            [str(part) for part in command],
            cwd=str(cwd),
            stdout=log,
            stderr=subprocess.STDOUT,
            text=True,
        )
    result["returncode"] = int(proc.returncode)
    if proc.returncode != 0:
        raise RuntimeError(f"command failed with code {proc.returncode}: {log_path}")
    return result


def find_latest_training_run(training_label: str, *, progress_root: Path = TRAINING_PROGRESS_ROOT) -> Path:
    progress_root = Path(progress_root)
    prefix = f"training_progress_LAB_GESR_v1_v5_ST0p8_SWP_{training_label}"
    candidates = [p for p in progress_root.glob(prefix + "*") if p.is_dir()]
    if not candidates:
        raise FileNotFoundError(f"no training run found for {training_label} under {progress_root}")
    return max(candidates, key=lambda p: p.stat().st_mtime)


def find_checkpoint(run_dir: Path) -> Path:
    names = [
        "best_tradeoff.pth.tar",
        "best_ema.pth.tar",
        "best_psnr.pth.tar",
        "latest.pth.tar",
    ]
    weight_dir = Path(run_dir) / "weights"
    for name in names:
        path = weight_dir / name
        if path.exists():
            return path
    fallback = sorted(weight_dir.glob("*.pth*"), key=lambda p: p.stat().st_mtime, reverse=True)
    if fallback:
        return fallback[0]
    raise FileNotFoundError(f"no checkpoint found in {weight_dir}")


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
        output_name,
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


def find_reconstructed_image(
    *,
    recon_root: Path,
    output_name: str,
    target_image: str = DEFAULT_TARGET_IMAGE,
) -> Path:
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


def build_measure_command(
    *,
    candidate_image: Path,
    candidate_label: str,
    output_dir: Path,
) -> list[str]:
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


def _mean_abs_error(summary_path: Path) -> tuple[float, dict[str, float]]:
    rows = _read_csv(summary_path)
    values: list[float] = []
    by_feature: dict[str, float] = {}
    for row in rows:
        feature = str(row.get("feature", "")).strip()
        if feature not in {"圓孔", "圓柱"}:
            continue
        value = float(row["abs_radius_error_vs_sem_nm"])
        values.append(value)
        by_feature[feature] = value
    if not values:
        raise RuntimeError(f"summary has no CD rows: {summary_path}")
    return sum(values) / len(values), by_feature


def rank_cd_results(
    results: list[dict],
    *,
    reference_mean_abs_radius_error_nm: float = REFERENCE_ORIGINAL_MEAN_ABS_RADIUS_ERROR_NM,
) -> list[dict]:
    ranked: list[dict] = []
    for item in results:
        summary_csv = Path(str(item["summary_csv"]))
        mean_error, by_feature = _mean_abs_error(summary_csv)
        ranked.append(
            {
                **item,
                "summary_csv": str(summary_csv),
                "mean_abs_radius_error_nm": round(float(mean_error), 6),
                "via_abs_radius_error_nm": by_feature.get("圓孔"),
                "pillar_abs_radius_error_nm": by_feature.get("圓柱"),
                "beats_original_mean": float(mean_error) < float(reference_mean_abs_radius_error_nm),
                "reference_original_mean_abs_radius_error_nm": float(reference_mean_abs_radius_error_nm),
            }
        )
    ranked.sort(key=lambda row: float(row["mean_abs_radius_error_nm"]))
    return ranked


def write_status_report(report_path: Path, payload: dict) -> None:
    report_path = Path(report_path)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    ranked = payload.get("ranked_results", []) or []
    lines = [
        "# R58 Automated Rounds Status",
        "",
        f"- Status: {payload.get('status', 'unknown')}",
        f"- Generated at: {payload.get('generated_at', '')}",
        f"- Reference original mean abs radius error: {payload.get('reference_original_mean_abs_radius_error_nm', REFERENCE_ORIGINAL_MEAN_ABS_RADIUS_ERROR_NM):.2f} nm",
        "",
    ]
    if ranked:
        best = ranked[0]
        lines.extend(
            [
                f"Best candidate: {best.get('candidate')} ({float(best.get('mean_abs_radius_error_nm', 0.0)):.2f} nm)",
                "",
                "| Rank | Candidate | Mean abs radius error (nm) | Via (nm) | Pillar (nm) | Beats original |",
                "| ---: | --- | ---: | ---: | ---: | --- |",
            ]
        )
        for idx, row in enumerate(ranked, start=1):
            via = row.get("via_abs_radius_error_nm")
            pillar = row.get("pillar_abs_radius_error_nm")
            lines.append(
                "| {rank} | {candidate} | {mean:.2f} | {via} | {pillar} | {beats} |".format(
                    rank=idx,
                    candidate=row.get("candidate", ""),
                    mean=float(row.get("mean_abs_radius_error_nm", 0.0)),
                    via="" if via is None else f"{float(via):.2f}",
                    pillar="" if pillar is None else f"{float(pillar):.2f}",
                    beats="yes" if row.get("beats_original_mean") else "no",
                )
            )
        lines.append("")
    failures = payload.get("failures", []) or []
    if failures:
        lines.extend(["Failures:", ""])
        for failure in failures:
            lines.append(f"- {failure}")
        lines.append("")
    report_path.write_text("\n".join(lines), encoding="utf-8")
    _write_json(report_path.with_suffix(".json"), payload)


def _plan_to_dict(plan: CandidatePlan) -> dict:
    return asdict(plan)


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run R58 automated training and CD validation rounds")
    parser.add_argument("--candidates", nargs="+", default=sorted(PROFILE_BY_CANDIDATE))
    parser.add_argument("--prepare-data", action="store_true")
    parser.add_argument("--train", action="store_true")
    parser.add_argument("--reconstruct", action="store_true")
    parser.add_argument("--measure", action="store_true")
    parser.add_argument("--rank-only", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--num-epoch", type=int, default=2)
    parser.add_argument("--max-train-batches", type=int, default=20)
    parser.add_argument("--batch-size", type=int, default=2)
    parser.add_argument("--val-batch-size", type=int, default=1)
    parser.add_argument("--num-workers", type=int, default=1)
    parser.add_argument("--val-ratio", type=float, default=0.02)
    parser.add_argument("--seq-batch-size", type=int, default=1)
    parser.add_argument("--device", default="cuda:0")
    parser.add_argument("--run-suffix", default="")
    parser.add_argument("--data-root", type=Path, default=DEFAULT_DATA_ROOT)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--input-dir", type=Path, default=DEFAULT_INPUT_DIR)
    parser.add_argument("--recon-root", type=Path, default=DEFAULT_RECON_ROOT)
    parser.add_argument("--target-image", default=DEFAULT_TARGET_IMAGE)
    parser.add_argument("--base-limit", type=int, default=0)
    parser.add_argument("--anchor-count", type=int, default=512)
    parser.add_argument("--image-size", type=int, default=256)
    parser.add_argument("--link-mode", choices=("auto", "hardlink", "copy"), default="auto")
    parser.add_argument("--seed-base", type=int, default=5800)
    parser.add_argument("--report-name", default="R58_AUTOMATED_ROUNDS_STATUS.md")
    return parser


def main(argv: Iterable[str] | None = None) -> int:
    args = build_arg_parser().parse_args(list(argv) if argv is not None else None)
    output_root = Path(args.output_root).resolve()
    run_suffix = _safe_suffix(args.run_suffix) or f"auto_{_timestamp()}"
    logs_dir = output_root / "logs" / run_suffix
    measure_root = output_root / "measurements" / run_suffix
    report_path = output_root / args.report_name
    candidates = [str(candidate) for candidate in args.candidates]

    plans = build_candidate_plans(
        candidates=candidates,
        num_epoch=args.num_epoch,
        max_train_batches=args.max_train_batches,
        batch_size=args.batch_size,
        run_suffix=run_suffix,
        data_root=args.data_root,
        output_root=output_root,
        device=args.device,
        val_batch_size=args.val_batch_size,
        num_workers=args.num_workers,
        val_ratio=args.val_ratio,
        seq_batch_size=args.seq_batch_size,
    )
    plan_records = [_plan_to_dict(plan) for plan in plans]
    command_results: list[dict] = []
    cd_results: list[dict] = []
    failures: list[str] = []

    try:
        if args.prepare_data:
            for command in build_prepare_commands(
                candidates=candidates,
                data_root=args.data_root,
                base_limit=args.base_limit,
                anchor_count=args.anchor_count,
                image_size=args.image_size,
                link_mode=args.link_mode,
                seed_base=args.seed_base,
            ):
                package_name = command[command.index("--package-name") + 1]
                command_results.append(
                    _run_command(
                        command,
                        cwd=LAB_ROOT,
                        log_path=logs_dir / f"prepare_{package_name}.log",
                        dry_run=bool(args.dry_run),
                    )
                )

        for plan in plans:
            mutable_plan = dict(_plan_to_dict(plan))
            if args.train:
                command_results.append(
                    _run_command(
                        plan.train_command,
                        cwd=LAB_ROOT,
                        log_path=logs_dir / f"train_{plan.training_label}.log",
                        dry_run=bool(args.dry_run),
                    )
                )
            if args.dry_run:
                plan_records = [
                    {**row, "dry_run": True} if row["candidate"] == plan.candidate else row
                    for row in plan_records
                ]
                continue

            if args.reconstruct or args.measure:
                run_dir = find_latest_training_run(plan.training_label)
                checkpoint = find_checkpoint(run_dir)
                mutable_plan["checkpoint"] = str(checkpoint)
                output_name = f"{plan.training_label}_weakpsf_off"
                reconstruct_command = build_reconstruct_command(
                    checkpoint=checkpoint,
                    output_name=output_name,
                    input_dir=args.input_dir,
                    recon_root=args.recon_root,
                    device=args.device,
                )
                mutable_plan["reconstruct_command"] = reconstruct_command
                if args.reconstruct:
                    command_results.append(
                        _run_command(
                            reconstruct_command,
                            cwd=PROJECT_ROOT,
                            log_path=logs_dir / f"reconstruct_{plan.training_label}.log",
                            dry_run=False,
                        )
                    )
                image_path = find_reconstructed_image(
                    recon_root=args.recon_root,
                    output_name=output_name,
                    target_image=args.target_image,
                )
                mutable_plan["reconstructed_image"] = str(image_path)

                if args.measure:
                    measurement_dir = measure_root / plan.training_label
                    measure_command = build_measure_command(
                        candidate_image=image_path,
                        candidate_label=plan.training_label,
                        output_dir=measurement_dir,
                    )
                    mutable_plan["measure_command"] = measure_command
                    command_results.append(
                        _run_command(
                            measure_command,
                            cwd=LAB_ROOT,
                            log_path=logs_dir / f"measure_{plan.training_label}.log",
                            dry_run=False,
                        )
                    )
                    summary_csv = measurement_dir / "cd_measurement_summary.csv"
                    mutable_plan["summary_csv"] = str(summary_csv)
                    cd_results.append(
                        {
                            "candidate": plan.candidate,
                            "training_label": plan.training_label,
                            "summary_csv": str(summary_csv),
                            "checkpoint": str(checkpoint),
                            "reconstructed_image": str(image_path),
                        }
                    )
            plan_records = [
                mutable_plan if row["candidate"] == plan.candidate else row
                for row in plan_records
            ]

        if args.rank_only:
            for plan in plans:
                summary_csv = measure_root / plan.training_label / "cd_measurement_summary.csv"
                if summary_csv.exists():
                    cd_results.append(
                        {
                            "candidate": plan.candidate,
                            "training_label": plan.training_label,
                            "summary_csv": str(summary_csv),
                        }
                    )

        ranked = rank_cd_results(cd_results) if cd_results else []
        status = "dry_run" if args.dry_run else ("ready" if ranked else "commands_complete")
    except Exception as exc:
        failures.append(str(exc))
        ranked = rank_cd_results(cd_results) if cd_results else []
        status = "failed"
    payload = {
        "status": status,
        "generated_at": datetime.now().replace(microsecond=0).isoformat(),
        "run_suffix": run_suffix,
        "plans": plan_records,
        "command_results": command_results,
        "ranked_results": ranked,
        "failures": failures,
        "reference_original_mean_abs_radius_error_nm": REFERENCE_ORIGINAL_MEAN_ABS_RADIUS_ERROR_NM,
        "output_root": str(output_root),
        "logs_dir": str(logs_dir),
        "measure_root": str(measure_root),
    }
    write_status_report(report_path, payload)
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    return 1 if status == "failed" else 0


if __name__ == "__main__":
    raise SystemExit(main())

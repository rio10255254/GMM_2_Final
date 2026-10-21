from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path


PREPARE_SCRIPT = Path(
    r"D:\GMM_2_Final\Thesis_MOSR_Evidence\LabSystem_MOSR\Experiments\R61_BoundaryGeneralizationUniversal\scripts\prepare_real_sample_gmf_package.py"
)
FUSION_SCRIPT = Path(
    r"D:\GMM_2_Final\Tools\Displacement_Algorithms\scripts\motion_preserving_fusion.py"
)
DEFAULT_WEIGHTS = Path(
    r"D:\GMM_2_Final\Thesis_MOSR_Evidence\LabSystem_MOSR\Traing_Progress\training_progress_LAB_GESR_v1_v5_ST0p8_SWP_r62_target_real_pseudo_stepguard_v2_stronger_stronger_full5_20260705_20260705_205634\weights\best_tradeoff.pth.tar"
)
REPORT_DIR = Path(
    r"D:\GMM_2_Final\Thesis_MOSR_Evidence\LabSystem_MOSR\Experiments\R62_TargetSampleBoost\reports"
)

DATASETS = [
    {
        "name": "20260702_100MG",
        "analysis_root": Path(r"D:\GMM_2_Final\20260702_100MG_displacement_analysis"),
        "groups": ["x_1um", "x_0p5um"],
    },
    {
        "name": "20260704_20x_5x",
        "analysis_root": Path(r"D:\GMM_2_Final\20260704_20x_5x_analysis"),
        "groups": ["20x_1um", "20x_0p5um", "5x_1um", "5x_0p5um"],
    },
]


def build_prepare_command(
    dataset: dict[str, object],
    group: str,
    *,
    weights: Path,
    case_prefix: str,
    role: str,
    device: str,
    note_prefix: str,
    infer_anchor_output_mode: str = "none",
    infer_anchor_alpha: float = 0.10,
    infer_anchor_sigma: float = 2.0,
    infer_anchor_detail_gain: float = 0.35,
) -> tuple[list[str], Path]:
    root = Path(dataset["analysis_root"])
    case_name = f"{case_prefix}_{group}"
    command = [
        sys.executable,
        str(PREPARE_SCRIPT),
        "--package-root",
        str(root),
        "--weights",
        str(weights),
        "--input-dir",
        str(root / "raw_inputs" / group / "bmp"),
        "--recon-root",
        str(root / "reconstructions"),
        "--case-name",
        case_name,
        "--role",
        role,
        "--device",
        device,
        "--anchor-output-mode",
        str(infer_anchor_output_mode),
        "--anchor-alpha",
        str(float(infer_anchor_alpha)),
        "--anchor-sigma",
        str(float(infer_anchor_sigma)),
        "--anchor-detail-gain",
        str(float(infer_anchor_detail_gain)),
        "--note",
        f"{note_prefix} for {dataset['name']} {group}.",
    ]
    log_path = root / f"{case_name}_prepare_stdout.log"
    return command, log_path


def anchor_case_prefix(case_prefix: str, anchor_variant: str) -> str:
    parts = [part for part in str(case_prefix).split("_") if part]
    if len(parts) >= 2 and parts[0].startswith("r"):
        model_tag = "_".join(parts[:2])
    else:
        model_tag = str(case_prefix)
    return f"{model_tag}_{anchor_variant}"


def build_anchor_fusion_plan(
    dataset: dict[str, object],
    group: str,
    *,
    case_prefix: str,
    anchor_variant: str,
    mode: str,
    alpha: float,
    sigma: float,
    detail_gain: float,
) -> dict[str, object]:
    root = Path(dataset["analysis_root"])
    anchor_prefix = anchor_case_prefix(case_prefix, anchor_variant)
    case_name = f"{anchor_prefix}_{group}"
    return {
        "dataset": dataset["name"],
        "group": group,
        "case_name": case_name,
        "raw_dir": root / "raw_inputs" / group / "bmp",
        "recon_dir": root / f"{case_prefix}_{group}" / "bmp",
        "output_dir": root / case_name / "bmp",
        "mode": mode,
        "alpha": float(alpha),
        "sigma": float(sigma),
        "detail_gain": float(detail_gain),
        "fusion_script": FUSION_SCRIPT,
    }


def _jsonable(value: object) -> object:
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {key: _jsonable(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_jsonable(item) for item in value]
    return value


def run_anchor_fusion(plan: dict[str, object]) -> dict[str, object]:
    if not FUSION_SCRIPT.is_file():
        raise FileNotFoundError(f"fusion script not found: {FUSION_SCRIPT}")
    command = [
        sys.executable,
        str(FUSION_SCRIPT),
        "--raw-dir",
        str(plan["raw_dir"]),
        "--recon-dir",
        str(plan["recon_dir"]),
        "--output-dir",
        str(plan["output_dir"]),
        "--mode",
        str(plan["mode"]),
        "--alpha",
        str(plan["alpha"]),
        "--sigma",
        str(plan["sigma"]),
        "--detail-gain",
        str(plan["detail_gain"]),
    ]
    proc = subprocess.run(command, text=True, capture_output=True)
    log_path = Path(plan["output_dir"]).parent / f"{plan['case_name']}_anchor_fusion_stdout.log"
    log_path.write_text(proc.stdout + "\nSTDERR:\n" + proc.stderr, encoding="utf-8", errors="replace")
    if proc.returncode != 0:
        raise RuntimeError(f"{plan['case_name']} anchor fusion failed with code {proc.returncode}; see {log_path}")
    result = dict(plan)
    result["command"] = command
    result["anchor_fusion_stdout_log"] = log_path
    return result


def run_case(
    dataset: dict[str, object],
    group: str,
    *,
    weights: Path,
    case_prefix: str,
    role: str,
    device: str,
    note_prefix: str,
    infer_anchor_output_mode: str = "none",
    infer_anchor_alpha: float = 0.10,
    infer_anchor_sigma: float = 2.0,
    infer_anchor_detail_gain: float = 0.35,
) -> dict[str, object]:
    case_name = f"{case_prefix}_{group}"
    command, log_path = build_prepare_command(
        dataset,
        group,
        weights=weights,
        case_prefix=case_prefix,
        role=role,
        device=device,
        note_prefix=note_prefix,
        infer_anchor_output_mode=infer_anchor_output_mode,
        infer_anchor_alpha=infer_anchor_alpha,
        infer_anchor_sigma=infer_anchor_sigma,
        infer_anchor_detail_gain=infer_anchor_detail_gain,
    )
    print(f"RUN {dataset['name']} {group}", flush=True)
    proc = subprocess.run(command, text=True, capture_output=True)
    log_path.write_text(proc.stdout + "\nSTDERR:\n" + proc.stderr, encoding="utf-8", errors="replace")
    if proc.returncode != 0:
        raise RuntimeError(f"{case_name} failed with code {proc.returncode}; see {log_path}")
    try:
        result = json.loads(proc.stdout)
    except json.JSONDecodeError:
        result = {"case_name": case_name}
    result["dataset"] = dataset["name"]
    result["group"] = group
    result["prepare_stdout_log"] = str(log_path)
    return result


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Reconstruct current thesis displacement sets with an R62-family checkpoint.")
    parser.add_argument("--weights", default=str(DEFAULT_WEIGHTS))
    parser.add_argument("--case-prefix", default="r62_v2_targetboost_psfoff")
    parser.add_argument("--role", default="r62_v2_targetboost_psfoff")
    parser.add_argument("--device", default="cuda:0")
    parser.add_argument("--note-prefix", default="R62 v2 target-sample-boost PSF-off reconstruction")
    parser.add_argument("--anchor-fusion", action="store_true", help="Also create motion-preserving fused outputs.")
    parser.add_argument("--anchor-variant", default="anchor_blend10")
    parser.add_argument("--anchor-mode", choices=["blend", "detail"], default="blend")
    parser.add_argument("--anchor-alpha", type=float, default=0.10)
    parser.add_argument("--anchor-sigma", type=float, default=2.0)
    parser.add_argument("--anchor-detail-gain", type=float, default=0.35)
    parser.add_argument("--infer-anchor-output-mode", choices=["none", "blend", "detail"], default="none")
    parser.add_argument("--infer-anchor-alpha", type=float, default=0.10)
    parser.add_argument("--infer-anchor-sigma", type=float, default=2.0)
    parser.add_argument("--infer-anchor-detail-gain", type=float, default=0.35)
    parser.add_argument("--dry-run", action="store_true")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    weights = Path(args.weights)
    if not PREPARE_SCRIPT.is_file():
        raise FileNotFoundError(f"prepare script not found: {PREPARE_SCRIPT}")
    if args.anchor_fusion and not FUSION_SCRIPT.is_file():
        raise FileNotFoundError(f"fusion script not found: {FUSION_SCRIPT}")
    if not weights.is_file():
        raise FileNotFoundError(f"R62 weights not found: {weights}")

    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    results: list[dict[str, object]] = []
    for dataset in DATASETS:
        for group in dataset["groups"]:
            if args.dry_run:
                command, log_path = build_prepare_command(
                    dataset,
                    group,
                    weights=weights,
                    case_prefix=str(args.case_prefix),
                    role=str(args.role),
                    device=str(args.device),
                    note_prefix=str(args.note_prefix),
                    infer_anchor_output_mode=str(args.infer_anchor_output_mode),
                    infer_anchor_alpha=float(args.infer_anchor_alpha),
                    infer_anchor_sigma=float(args.infer_anchor_sigma),
                    infer_anchor_detail_gain=float(args.infer_anchor_detail_gain),
                )
                results.append(
                    {
                        "dataset": dataset["name"],
                        "group": group,
                        "command": command,
                        "prepare_stdout_log": str(log_path),
                    }
                )
                if args.anchor_fusion:
                    results[-1]["anchor_fusion_plan"] = _jsonable(
                        build_anchor_fusion_plan(
                            dataset,
                            group,
                            case_prefix=str(args.case_prefix),
                            anchor_variant=str(args.anchor_variant),
                            mode=str(args.anchor_mode),
                            alpha=float(args.anchor_alpha),
                            sigma=float(args.anchor_sigma),
                            detail_gain=float(args.anchor_detail_gain),
                        )
                    )
            else:
                result = run_case(
                    dataset,
                    group,
                    weights=weights,
                    case_prefix=str(args.case_prefix),
                    role=str(args.role),
                    device=str(args.device),
                    note_prefix=str(args.note_prefix),
                    infer_anchor_output_mode=str(args.infer_anchor_output_mode),
                    infer_anchor_alpha=float(args.infer_anchor_alpha),
                    infer_anchor_sigma=float(args.infer_anchor_sigma),
                    infer_anchor_detail_gain=float(args.infer_anchor_detail_gain),
                )
                if args.anchor_fusion:
                    result["anchor_fusion"] = _jsonable(
                        run_anchor_fusion(
                            build_anchor_fusion_plan(
                                dataset,
                                group,
                                case_prefix=str(args.case_prefix),
                                anchor_variant=str(args.anchor_variant),
                                mode=str(args.anchor_mode),
                                alpha=float(args.anchor_alpha),
                                sigma=float(args.anchor_sigma),
                                detail_gain=float(args.anchor_detail_gain),
                            )
                        )
                    )
                results.append(result)

    suffix = "dry_run_reconstruction_summary" if args.dry_run else "reconstruction_summary"
    summary_path = REPORT_DIR / f"{args.case_prefix}_{suffix}.json"
    summary_path.write_text(json.dumps(_jsonable(results), indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({"cases": len(results), "summary": str(summary_path)}, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()

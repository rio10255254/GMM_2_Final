"""Run an R42 low-alpha COMBO/candidate weight averaging sweep."""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path

import torch


REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from launch_r42 import COMBO_CHECKPOINT  # noqa: E402
from r42_weight_sweep import (  # noqa: E402
    DEFAULT_THRESHOLDS,
    BoundaryTradeoffThresholds,
    alpha_tag,
    combine_sweep_row,
    default_alpha_grid,
    evaluate_boundary_tradeoff,
    interpolate_state_dicts,
    parse_boundary_summary,
    parse_ring_guard_summary,
    validate_state_dicts_compatible,
)


DEFAULT_OUTPUT_DIR = REPO_ROOT / "Experiments" / "R42_MicroscopyBoundaryFidelity" / "results" / "weight_sweep"
REPRESENTATIVE_RECON_PS1 = REPO_ROOT / "Tools" / "RunRepresentativeExternalRecon.ps1"


def load_state_dict(path: Path) -> dict:
    obj = torch.load(path, map_location="cpu", weights_only=False)
    sd = obj["state_dict"] if isinstance(obj, dict) and "state_dict" in obj else obj
    if not isinstance(sd, dict):
        raise TypeError(f"unexpected checkpoint contents: {type(sd)}")
    cleaned = {}
    for key, value in sd.items():
        new_key = key.replace("module.", "", 1) if isinstance(key, str) and key.startswith("module.") else key
        cleaned[new_key] = value
    return cleaned


def save_state_dict_as_checkpoint(sd: dict, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    torch.save({"state_dict": sd}, path)


def _run(cmd: list[object], **kwargs) -> None:
    print("[r42-sweep] $", " ".join(str(c) for c in cmd), flush=True)
    subprocess.check_call([str(c) for c in cmd], **kwargs)


def run_boundary_recon(weights: Path, recon_root: Path, device: str) -> None:
    recon_root.mkdir(parents=True, exist_ok=True)
    _run(
        [
            sys.executable,
            SCRIPT_DIR / "run_r42_boundary_recon.py",
            "--profile",
            "boundary_val_unseen",
            "--weights",
            weights,
            "--recon-root",
            recon_root,
            "--device",
            device,
        ]
    )


def run_boundary_summarize(recon_root: Path, output_json: Path) -> dict:
    output_json.parent.mkdir(parents=True, exist_ok=True)
    _run(
        [
            sys.executable,
            SCRIPT_DIR / "r42_boundary_metrics.py",
            "--profile",
            "boundary_val_unseen",
            "--recon-root",
            recon_root,
            "--output-json",
            output_json,
        ]
    )
    return json.loads(output_json.read_text(encoding="utf-8"))


def _powershell_executable() -> str:
    for cand in ("pwsh", "powershell"):
        which = shutil.which(cand)
        if which:
            return which
    raise RuntimeError("no powershell executable on PATH")


def run_ring_representative_recon(weights: Path, recon_root: Path) -> None:
    recon_root.mkdir(parents=True, exist_ok=True)
    _run(
        [
            _powershell_executable(),
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            REPRESENTATIVE_RECON_PS1,
            "-WeightsPath",
            weights,
            "-ReconRoot",
            recon_root,
        ]
    )


def run_ring_guard(candidate_tag: str, ring_recon_root: Path, analysis_root: Path, summary_json: Path) -> dict:
    import run_r42_ring_guard as guard
    import run_sequence_analysis as seq

    datasets = guard.build_ring_datasets(candidate_tag, ring_recon_root)
    candidate_out = analysis_root / f"{candidate_tag}_sequence_analysis"
    result = seq.main(datasets=datasets, out_root=candidate_out, verbose=False)
    compact = guard.make_compact_summary(candidate=candidate_tag, result=result, combo_cross_json=guard.DEFAULT_COMBO_CROSS_JSON)
    summary_json.parent.mkdir(parents=True, exist_ok=True)
    summary_json.write_text(json.dumps(compact, indent=2, ensure_ascii=False), encoding="utf-8")
    return compact


def evaluate_one_alpha(
    *,
    alpha: float,
    sd_combo: dict,
    sd_candidate: dict,
    output_dir: Path,
    device: str,
    skip_existing: bool,
) -> dict:
    tag = alpha_tag(alpha)
    print(f"[r42-sweep] === alpha={alpha:.2f} ({tag}) ===", flush=True)

    ckpt_path = output_dir / "checkpoints" / tag / "best_tradeoff.pth.tar"
    if not ckpt_path.exists() or not skip_existing:
        sd_avg = interpolate_state_dicts(sd_combo, sd_candidate, alpha)
        save_state_dict_as_checkpoint(sd_avg, ckpt_path)

    boundary_recon_root = output_dir / "boundary_recon" / tag
    boundary_json = output_dir / "boundary_recon" / f"{tag}_boundary_summary.json"
    if not boundary_json.exists() or not skip_existing:
        run_boundary_recon(ckpt_path, boundary_recon_root, device)
        boundary_summary = run_boundary_summarize(boundary_recon_root, boundary_json)
    else:
        boundary_summary = json.loads(boundary_json.read_text(encoding="utf-8"))

    ring_recon_root = output_dir / "ring_recon"
    candidate_recon_dir = ring_recon_root / tag
    has_existing_recon = candidate_recon_dir.exists() and any(candidate_recon_dir.glob("reconstruct_progress_*"))
    if not has_existing_recon or not skip_existing:
        run_ring_representative_recon(ckpt_path, candidate_recon_dir)

    ring_guard_dir = output_dir / "ring_guard"
    ring_summary_json = ring_guard_dir / f"{tag}_ring_guard_summary.json"
    if not ring_summary_json.exists() or not skip_existing:
        ring_summary = run_ring_guard(tag, ring_recon_root, ring_guard_dir, ring_summary_json)
    else:
        ring_summary = json.loads(ring_summary_json.read_text(encoding="utf-8"))

    return combine_sweep_row(
        alpha,
        parse_boundary_summary(boundary_summary),
        parse_ring_guard_summary(ring_summary),
    )


def parse_alphas(spec: str | None) -> list[float]:
    if not spec:
        return default_alpha_grid()
    out = []
    for token in spec.split(","):
        token = token.strip()
        if not token:
            continue
        value = float(token)
        if value < 0.0 or value > 1.0:
            raise argparse.ArgumentTypeError(f"alpha out of range: {value}")
        out.append(round(value, 2))
    if not out:
        raise argparse.ArgumentTypeError("no alphas parsed")
    return out


def _format_table(rows: list[dict]) -> str:
    header = (
        "| alpha | boundary PSNR | HF retention | boundary dist px | F1@1px | ring 8px | ring 0.8px | ring 0.08px |\n"
        "|------:|--------------:|-------------:|-----------------:|-------:|---------:|-----------:|------------:|"
    )
    body = "\n".join(
        f"| {r['alpha']:.2f} | {r['boundary_overall_psnr']:.4f} | "
        f"{r['boundary_high_frequency_retention']:.4f} | {r['boundary_distance_px']:.4f} | "
        f"{r['boundary_fscore_t1p0']:.4f} | {r['ring_8px_step_std']:.4f} | "
        f"{r['ring_0p8px_step_std']:.4f} | {r['ring_0p08px_step_std']:.4f} |"
        for r in rows
    )
    return header + "\n" + body


def write_aggregate(
    *,
    rows: list[dict],
    output_dir: Path,
    candidate_name: str,
    combo_path: Path,
    candidate_path: Path,
    thresholds: BoundaryTradeoffThresholds,
) -> dict:
    rows_sorted = sorted(rows, key=lambda r: r["alpha"])
    verdict = evaluate_boundary_tradeoff(rows_sorted, thresholds)
    payload = {
        "candidate": candidate_name,
        "combo_checkpoint": str(combo_path),
        "candidate_checkpoint": str(candidate_path),
        "thresholds": {
            "min_boundary_psnr": thresholds.min_boundary_psnr,
            "min_high_frequency_retention": thresholds.min_high_frequency_retention,
            "max_boundary_distance_px": thresholds.max_boundary_distance_px,
            "min_boundary_fscore_t1p0": thresholds.min_boundary_fscore_t1p0,
            "max_8px": thresholds.max_8px,
            "max_0p8px": thresholds.max_0p8px,
            "max_0p08px": thresholds.max_0p08px,
        },
        "rows": rows_sorted,
        "verdict": verdict,
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "sweep_summary.json").write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    lines = [
        f"# R42 低比例權重平均 sweep - COMBO ↔ {candidate_name}",
        "",
        f"COMBO checkpoint:`{combo_path}`",
        f"候選 checkpoint:`{candidate_path}`",
        "",
        "## Trade-off 表",
        "",
        _format_table(rows_sorted),
        "",
        "## Verdict",
        "",
        f"- guarded trade-off found:**{verdict['found']}**",
        f"- 理由:{verdict['reason']}",
    ]
    if verdict.get("best") is not None:
        best = verdict["best"]
        lines.append(f"- 最佳 guarded alpha:**{best['alpha']:.2f}**")
    if verdict.get("boundary_only_best") is not None:
        best = verdict["boundary_only_best"]
        lines.append(f"- 最佳 boundary-only alpha:**{best['alpha']:.2f}**")
    (output_dir / "sweep_summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="R42 low-alpha boundary/ring weight averaging sweep runner")
    parser.add_argument("--candidate-name", required=True)
    parser.add_argument("--candidate-checkpoint", type=Path, required=True)
    parser.add_argument("--combo-checkpoint", type=Path, default=COMBO_CHECKPOINT)
    parser.add_argument("--alphas", default=None)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--device", default="cuda:0")
    parser.add_argument("--skip-existing", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--min-boundary-psnr", type=float, default=DEFAULT_THRESHOLDS.min_boundary_psnr)
    parser.add_argument("--min-high-frequency-retention", type=float, default=DEFAULT_THRESHOLDS.min_high_frequency_retention)
    parser.add_argument("--max-boundary-distance-px", type=float, default=DEFAULT_THRESHOLDS.max_boundary_distance_px)
    parser.add_argument("--min-boundary-fscore-t1p0", type=float, default=DEFAULT_THRESHOLDS.min_boundary_fscore_t1p0)
    parser.add_argument("--max-8px", type=float, default=DEFAULT_THRESHOLDS.max_8px)
    parser.add_argument("--max-0p8px", type=float, default=DEFAULT_THRESHOLDS.max_0p8px)
    parser.add_argument("--max-0p08px", type=float, default=DEFAULT_THRESHOLDS.max_0p08px)
    args = parser.parse_args(argv)

    combo_path = args.combo_checkpoint.resolve()
    candidate_path = args.candidate_checkpoint.resolve()
    if not combo_path.exists():
        raise FileNotFoundError(f"COMBO checkpoint missing: {combo_path}")
    if not candidate_path.exists():
        raise FileNotFoundError(f"candidate checkpoint missing: {candidate_path}")

    sd_combo = load_state_dict(combo_path)
    sd_candidate = load_state_dict(candidate_path)
    validate_state_dicts_compatible(sd_combo, sd_candidate)
    alphas = parse_alphas(args.alphas)
    thresholds = BoundaryTradeoffThresholds(
        min_boundary_psnr=args.min_boundary_psnr,
        min_high_frequency_retention=args.min_high_frequency_retention,
        max_boundary_distance_px=args.max_boundary_distance_px,
        min_boundary_fscore_t1p0=args.min_boundary_fscore_t1p0,
        max_8px=args.max_8px,
        max_0p8px=args.max_0p8px,
        max_0p08px=args.max_0p08px,
    )

    if args.dry_run:
        print(
            json.dumps(
                {
                    "candidate": args.candidate_name,
                    "combo_checkpoint": str(combo_path),
                    "candidate_checkpoint": str(candidate_path),
                    "alphas": alphas,
                    "output_dir": str(args.output_dir.resolve()),
                    "n_tensors": len(sd_combo),
                    "total_params": sum(int(t.numel()) for t in sd_combo.values()),
                    "device": args.device,
                },
                indent=2,
                ensure_ascii=False,
            )
        )
        print("[r42-sweep] dry run complete; no inference was started.", flush=True)
        return 0

    rows: list[dict] = []
    for alpha in alphas:
        row = evaluate_one_alpha(
            alpha=alpha,
            sd_combo=sd_combo,
            sd_candidate=sd_candidate,
            output_dir=args.output_dir,
            device=args.device,
            skip_existing=args.skip_existing,
        )
        rows.append(row)
        write_aggregate(
            rows=rows,
            output_dir=args.output_dir,
            candidate_name=args.candidate_name,
            combo_path=combo_path,
            candidate_path=candidate_path,
            thresholds=thresholds,
        )

    payload = write_aggregate(
        rows=rows,
        output_dir=args.output_dir,
        candidate_name=args.candidate_name,
        combo_path=combo_path,
        candidate_path=candidate_path,
        thresholds=thresholds,
    )
    print(json.dumps(payload["verdict"], indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

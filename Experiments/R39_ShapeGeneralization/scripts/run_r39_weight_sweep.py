"""R39 weight averaging sweep runner.

Linearly interpolates the COMBO checkpoint with an R39 candidate, evaluates
the held-out shape package and the local three-scale ring guard at each
alpha, and writes a per-run + aggregated summary.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

import torch


_REPO_ROOT = Path(__file__).resolve().parents[3]
_SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(_SCRIPT_DIR))
sys.path.insert(0, str(_REPO_ROOT / "Model"))

from r39_weight_sweep import (
    SweetSpotThresholds,
    alpha_tag,
    combine_sweep_row,
    default_alpha_grid,
    evaluate_sweet_spot,
    interpolate_state_dicts,
    parse_ring_guard_summary,
    parse_shape_summary,
    validate_state_dicts_compatible,
)
from launch_r39 import COMBO_CHECKPOINT


DEFAULT_OUTPUT_DIR = (
    _REPO_ROOT
    / "Experiments"
    / "R39_ShapeGeneralization"
    / "results"
    / "weight_sweep"
)

CANDIDATE_CHECKPOINTS = {
    "r39_shape_mix_safe": (
        _REPO_ROOT
        / "Experiments"
        / "Training_Runs"
        / "training_progress_GESR_v1_v5_ST0p8_SWP_r39_shape_mix_safe_20260428_165958"
        / "weights"
        / "best_tradeoff.pth.tar"
    ),
    "r39_shape_mix_strong": (
        _REPO_ROOT
        / "Experiments"
        / "Training_Runs"
        / "training_progress_GESR_v1_v5_ST0p8_SWP_r39_shape_mix_strong_20260428_180728"
        / "weights"
        / "best_tradeoff.pth.tar"
    ),
}

REPRESENTATIVE_RECON_PS1 = _REPO_ROOT / "Tools" / "RunRepresentativeExternalRecon.ps1"

DEFAULT_THRESHOLDS = SweetSpotThresholds(
    min_shape_psnr=24.84,
    max_8px=0.155,
    max_0p8px=0.155,
    max_0p08px=0.135,
)


# ---------------------------------------------------------------------------
# checkpoint IO
# ---------------------------------------------------------------------------


def load_state_dict(path: Path) -> dict:
    obj = torch.load(path, map_location="cpu", weights_only=False)
    if isinstance(obj, dict) and "state_dict" in obj:
        sd = obj["state_dict"]
    else:
        sd = obj
    if not isinstance(sd, dict):
        raise TypeError(f"unexpected checkpoint contents: {type(sd)}")
    cleaned: dict = {}
    for k, v in sd.items():
        nk = k.replace("module.", "", 1) if isinstance(k, str) and k.startswith("module.") else k
        cleaned[nk] = v
    return cleaned


def save_state_dict_as_checkpoint(sd: dict, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    torch.save({"state_dict": sd}, path)


# ---------------------------------------------------------------------------
# subprocess wrappers
# ---------------------------------------------------------------------------


def _run(cmd: list[str], **kwargs) -> None:
    print("[sweep] $", " ".join(str(c) for c in cmd), flush=True)
    subprocess.check_call([str(c) for c in cmd], **kwargs)


def run_shape_recon(weights: Path, recon_root: Path, device: str) -> None:
    recon_root.mkdir(parents=True, exist_ok=True)
    _run([
        sys.executable,
        _SCRIPT_DIR / "run_r39_shape_recon.py",
        "--profile", "shape_val_unseen",
        "--weights", weights,
        "--recon-root", recon_root,
        "--device", device,
    ])


def run_shape_summarize(recon_root: Path, output_json: Path) -> dict:
    output_json.parent.mkdir(parents=True, exist_ok=True)
    _run([
        sys.executable,
        _SCRIPT_DIR / "summarize_r39_shape_recon.py",
        "--profile", "shape_val_unseen",
        "--recon-root", recon_root,
        "--output-json", output_json,
    ])
    return json.loads(output_json.read_text(encoding="utf-8"))


def _powershell_executable() -> str:
    for cand in ("pwsh", "powershell"):
        which = shutil.which(cand)
        if which:
            return which
    raise RuntimeError("no powershell executable on PATH (pwsh / powershell)")


def run_ring_representative_recon(weights: Path, recon_root: Path) -> None:
    recon_root.mkdir(parents=True, exist_ok=True)
    ps_exe = _powershell_executable()
    _run([
        ps_exe,
        "-NoProfile",
        "-ExecutionPolicy", "Bypass",
        "-File", REPRESENTATIVE_RECON_PS1,
        "-WeightsPath", weights,
        "-ReconRoot", recon_root,
    ])


def run_ring_guard(
    candidate_tag: str,
    ring_recon_root: Path,
    analysis_root: Path,
    summary_json: Path,
) -> dict:
    """Use ring guard internals so candidate is not constrained to known names."""
    sys.path.insert(0, str(_REPO_ROOT / "Analyses" / "AnalysisLab" / "r26" / "sequence" / "scripts"))
    sys.path.insert(0, str(_REPO_ROOT / "Analyses" / "AnalysisLab" / "r26" / "sequence" / "configs"))
    import run_r39_ring_guard as guard
    import run_sequence_analysis as seq

    datasets = guard.build_ring_datasets(candidate_tag, ring_recon_root)
    candidate_out = analysis_root / f"{candidate_tag}_sequence_analysis"
    result = seq.main(datasets=datasets, out_root=candidate_out, verbose=False)
    compact = guard.make_compact_summary(
        candidate=candidate_tag,
        result=result,
        combo_cross_json=guard.DEFAULT_COMBO_CROSS_JSON,
    )
    summary_json.parent.mkdir(parents=True, exist_ok=True)
    summary_json.write_text(json.dumps(compact, indent=2, ensure_ascii=False), encoding="utf-8")
    return compact


# ---------------------------------------------------------------------------
# per-alpha pipeline
# ---------------------------------------------------------------------------


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
    print(f"[sweep] === alpha={alpha:.2f} ({tag}) ===", flush=True)

    ckpt_dir = output_dir / "checkpoints" / tag
    ckpt_path = ckpt_dir / "best_tradeoff.pth.tar"
    if not ckpt_path.exists() or not skip_existing:
        sd_avg = interpolate_state_dicts(sd_combo, sd_candidate, alpha)
        save_state_dict_as_checkpoint(sd_avg, ckpt_path)

    shape_recon_root = output_dir / "shape_recon" / tag
    shape_json = output_dir / "shape_recon" / f"{tag}_shape_summary.json"
    if not shape_json.exists() or not skip_existing:
        run_shape_recon(ckpt_path, shape_recon_root, device)
        shape_summary = run_shape_summarize(shape_recon_root, shape_json)
    else:
        shape_summary = json.loads(shape_json.read_text(encoding="utf-8"))

    ring_recon_root = output_dir / "ring_recon"
    candidate_recon_dir = ring_recon_root / tag
    has_existing_recon = (
        candidate_recon_dir.exists()
        and any(candidate_recon_dir.glob("reconstruct_progress_*"))
    )
    if not has_existing_recon or not skip_existing:
        run_ring_representative_recon(ckpt_path, candidate_recon_dir)

    ring_guard_dir = output_dir / "ring_guard"
    ring_summary_json = ring_guard_dir / f"{tag}_ring_guard_summary.json"
    if not ring_summary_json.exists() or not skip_existing:
        ring_summary = run_ring_guard(
            candidate_tag=tag,
            ring_recon_root=ring_recon_root,
            analysis_root=ring_guard_dir,
            summary_json=ring_summary_json,
        )
    else:
        ring_summary = json.loads(ring_summary_json.read_text(encoding="utf-8"))

    row = combine_sweep_row(
        alpha,
        parse_shape_summary(shape_summary),
        parse_ring_guard_summary(ring_summary),
    )
    return row


# ---------------------------------------------------------------------------
# aggregation + reporting
# ---------------------------------------------------------------------------


def _format_markdown_table(rows: list[dict]) -> str:
    header = (
        "| alpha | shape PSNR | shape SSIM | ring 8px | ring 0.8px | ring 0.08px |\n"
        "|------:|-----------:|-----------:|---------:|-----------:|------------:|"
    )
    body = "\n".join(
        f"| {r['alpha']:.2f} | {r['shape_overall_psnr']:.4f} "
        f"| {r['shape_overall_ssim']:.4f} | {r['ring_8px_step_std']:.4f} "
        f"| {r['ring_0p8px_step_std']:.4f} | {r['ring_0p08px_step_std']:.4f} |"
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
    thresholds: SweetSpotThresholds,
) -> dict:
    rows_sorted = sorted(rows, key=lambda r: r["alpha"])
    verdict = evaluate_sweet_spot(rows_sorted, thresholds)
    payload = {
        "candidate": candidate_name,
        "combo_checkpoint": str(combo_path),
        "candidate_checkpoint": str(candidate_path),
        "thresholds": {
            "min_shape_psnr": thresholds.min_shape_psnr,
            "max_8px": thresholds.max_8px,
            "max_0p8px": thresholds.max_0p8px,
            "max_0p08px": thresholds.max_0p08px,
        },
        "rows": rows_sorted,
        "verdict": verdict,
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    summary_path = output_dir / "sweep_summary.json"
    summary_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

    md_path = output_dir / "sweep_summary.md"
    lines = [
        f"# R39 權重平均 sweep — COMBO ↔ {candidate_name}",
        "",
        f"COMBO checkpoint:`{combo_path}`",
        f"候選 checkpoint:`{candidate_path}`",
        f"門檻:shape PSNR ≥ {thresholds.min_shape_psnr}、"
        f"8px ≤ {thresholds.max_8px}、0.8px ≤ {thresholds.max_0p8px}、"
        f"0.08px ≤ {thresholds.max_0p08px}",
        "",
        "## Trade-off 表",
        "",
        _format_markdown_table(rows_sorted),
        "",
        "## Verdict",
        "",
        f"- found:**{verdict['found']}**",
        f"- 理由:{verdict['reason']}",
    ]
    if verdict["best"] is not None:
        best = verdict["best"]
        lines.append(
            f"- 最佳 alpha:**{best['alpha']:.2f}** "
            f"(shape PSNR {best['shape_overall_psnr']:.4f}、"
            f"ring 8px {best['ring_8px_step_std']:.4f})"
        )
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return payload


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def parse_alphas(spec: str | None) -> list[float]:
    if not spec:
        return default_alpha_grid()
    out: list[float] = []
    for tok in spec.split(","):
        tok = tok.strip()
        if not tok:
            continue
        v = float(tok)
        if v < 0.0 or v > 1.0:
            raise argparse.ArgumentTypeError(f"alpha out of range: {v}")
        out.append(round(v, 2))
    if not out:
        raise argparse.ArgumentTypeError("no alphas parsed")
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="R39 weight averaging sweep runner")
    parser.add_argument(
        "--candidate",
        default="r39_shape_mix_strong",
        choices=sorted(CANDIDATE_CHECKPOINTS),
    )
    parser.add_argument("--combo-checkpoint", type=Path, default=COMBO_CHECKPOINT)
    parser.add_argument("--candidate-checkpoint", type=Path, default=None,
                        help="override the candidate checkpoint path")
    parser.add_argument("--alphas", type=str, default=None,
                        help="comma-separated alphas; default uses 0.0..1.0 step 0.1")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--device", default="cuda:0")
    parser.add_argument("--skip-existing", action="store_true",
                        help="skip alphas whose per-alpha summaries already exist")
    parser.add_argument("--dry-run", action="store_true",
                        help="validate checkpoint compatibility and print plan, then exit")
    parser.add_argument("--min-shape-psnr", type=float, default=DEFAULT_THRESHOLDS.min_shape_psnr)
    parser.add_argument("--max-8px", type=float, default=DEFAULT_THRESHOLDS.max_8px)
    parser.add_argument("--max-0p8px", type=float, default=DEFAULT_THRESHOLDS.max_0p8px)
    parser.add_argument("--max-0p08px", type=float, default=DEFAULT_THRESHOLDS.max_0p08px)
    args = parser.parse_args(argv)

    combo_path = args.combo_checkpoint.resolve()
    candidate_path = (
        args.candidate_checkpoint.resolve()
        if args.candidate_checkpoint is not None
        else CANDIDATE_CHECKPOINTS[args.candidate].resolve()
    )
    if not combo_path.exists():
        raise FileNotFoundError(f"COMBO checkpoint missing: {combo_path}")
    if not candidate_path.exists():
        raise FileNotFoundError(f"candidate checkpoint missing: {candidate_path}")

    print(f"[sweep] loading COMBO weights from {combo_path}", flush=True)
    sd_combo = load_state_dict(combo_path)
    print(f"[sweep] loading candidate weights from {candidate_path}", flush=True)
    sd_candidate = load_state_dict(candidate_path)
    validate_state_dicts_compatible(sd_combo, sd_candidate)
    print(
        f"[sweep] state_dicts compatible: {len(sd_combo)} tensors, "
        f"total params={sum(t.numel() for t in sd_combo.values()):,}",
        flush=True,
    )

    alphas = parse_alphas(args.alphas)
    print(f"[sweep] sweeping alphas: {alphas}", flush=True)

    thresholds = SweetSpotThresholds(
        min_shape_psnr=args.min_shape_psnr,
        max_8px=args.max_8px,
        max_0p8px=args.max_0p8px,
        max_0p08px=args.max_0p08px,
    )

    if args.dry_run:
        plan = {
            "candidate": args.candidate,
            "combo_checkpoint": str(combo_path),
            "candidate_checkpoint": str(candidate_path),
            "alphas": alphas,
            "output_dir": str(args.output_dir.resolve()),
            "n_tensors": len(sd_combo),
            "total_params": sum(int(t.numel()) for t in sd_combo.values()),
            "device": args.device,
        }
        print(json.dumps(plan, indent=2, ensure_ascii=False))
        print("[sweep] dry run complete; no inference was started.", flush=True)
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
        # write the aggregate after every alpha so a partial sweep is not lost
        write_aggregate(
            rows=rows,
            output_dir=args.output_dir,
            candidate_name=args.candidate,
            combo_path=combo_path,
            candidate_path=candidate_path,
            thresholds=thresholds,
        )

    payload = write_aggregate(
        rows=rows,
        output_dir=args.output_dir,
        candidate_name=args.candidate,
        combo_path=combo_path,
        candidate_path=candidate_path,
        thresholds=thresholds,
    )
    print(json.dumps(payload["verdict"], indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

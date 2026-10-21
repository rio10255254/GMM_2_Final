"""Prepare real-sample GMF package entries for R61 candidates."""
from __future__ import annotations

import argparse
import csv
import json
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path


PACKAGE_ROOT = Path(__file__).resolve().parents[1]
EXPERIMENT_DIR = PACKAGE_ROOT
LAB_ROOT = PACKAGE_ROOT
PROJECT_ROOT = PACKAGE_ROOT
MODEL_DIR = PACKAGE_ROOT
INFER_SCRIPT = PACKAGE_ROOT / "infer_r61.py"
LAB_PSF_PATH = PACKAGE_ROOT / "psf" / "PSF_fitted_2D_FOVstack.mat"
DEFAULT_PACKAGE_ROOT = PACKAGE_ROOT / "results" / "real_sample_gmf"
DEFAULT_RECON_ROOT = DEFAULT_PACKAGE_ROOT / "reconstruction_outputs"
DEFAULT_WEIGHTS = PACKAGE_ROOT / "weights" / "best_tradeoff.pth.tar"
DEFAULT_CASE_NAME = "05_r61_r39_a970_candidate"
DEFAULT_ROLE = "r61_r39_a970_candidate"
TSV_FIELDS = ["case", "role", "image_folder", "score_folder", "image_count", "note"]


@dataclass(frozen=True)
class GmfCase:
    case: str
    role: str
    image_folder: Path
    score_folder: Path
    image_count: int
    note: str

    def to_row(self) -> dict[str, str]:
        return {
            "case": self.case,
            "role": self.role,
            "image_folder": str(self.image_folder),
            "score_folder": str(self.score_folder),
            "image_count": str(int(self.image_count)),
            "note": self.note,
        }


def _python() -> str:
    return sys.executable or "python"


def _bmp_files(path: Path) -> list[Path]:
    return sorted(p for p in Path(path).glob("*.bmp") if p.is_file())


def _patch_infer_script_text(text: str, *, original_script_dir: Path) -> str:
    patched = str(text)
    replacements = {
        "SCRIPT_DIR = Path(__file__).resolve().parent": f'SCRIPT_DIR = Path(r"{Path(original_script_dir)}")',
        'MANUAL_SELECT_MODE = "odd"': "MANUAL_SELECT_MODE = None",
        "MANUAL_SELECT_MODE = 'odd'": "MANUAL_SELECT_MODE = None",
    }
    for old, new in replacements.items():
        patched = patched.replace(old, new)
    return patched


def prepare_infer_script(run_dir: Path, *, source_script: Path = INFER_SCRIPT) -> Path:
    source_script = Path(source_script).resolve()
    runtime_dir = Path(run_dir) / "runtime"
    runtime_dir.mkdir(parents=True, exist_ok=True)
    patched_script = runtime_dir / source_script.name
    patched_script.write_text(
        _patch_infer_script_text(source_script.read_text(encoding="utf-8"), original_script_dir=source_script.parent),
        encoding="utf-8",
    )
    return patched_script


def build_infer_command(
    *,
    infer_script: Path,
    weights: Path,
    input_dir: Path,
    recon_root: Path,
    output_name: str,
    device: str,
    psf_path: Path,
    anchor_output_mode: str = "none",
    anchor_alpha: float = 0.10,
    anchor_sigma: float = 2.0,
    anchor_detail_gain: float = 0.35,
) -> list[str]:
    return [
        _python(),
        str(infer_script),
        "--weights",
        str(weights),
        "--input-dir",
        str(input_dir),
        "--recon-root",
        str(recon_root),
        "--output-name",
        str(output_name),
        "--select-mode",
        "all",
        "--device",
        str(device),
        "--exts",
        ".bmp",
        "--psf-fitted-path",
        str(psf_path),
        "--no-psf-from-ckpt",
        "--weak-psf-disable",
        "--psf-deconv-reg",
        "30.0",
        "--psf-phys-alpha",
        "0.0",
        "--anchor-output-mode",
        str(anchor_output_mode),
        "--anchor-alpha",
        str(float(anchor_alpha)),
        "--anchor-sigma",
        str(float(anchor_sigma)),
        "--anchor-detail-gain",
        str(float(anchor_detail_gain)),
    ]


def _latest_case_output(recon_root: Path, case_name: str) -> Path:
    candidates = [p for p in Path(recon_root).glob(f"*/{case_name}") if p.is_dir()]
    if candidates:
        return max(candidates, key=lambda p: p.stat().st_mtime)
    fallback = [p for p in Path(recon_root).rglob(case_name) if p.is_dir()]
    if fallback:
        return max(fallback, key=lambda p: p.stat().st_mtime)
    raise FileNotFoundError(f"no reconstruction output found for {case_name} under {recon_root}")


def _safe_remove_dir(path: Path, *, allowed_root: Path) -> None:
    resolved = Path(path).resolve()
    root = Path(allowed_root).resolve()
    if resolved == root:
        raise ValueError(f"refusing to remove allowed root: {resolved}")
    if not str(resolved).lower().startswith(str(root).lower()):
        raise ValueError(f"refusing to remove outside allowed root: {resolved}")
    if resolved.exists():
        shutil.rmtree(resolved)


def sync_reconstruction_to_case(output_dir: Path, case_bmp_dir: Path) -> dict[str, object]:
    files = _bmp_files(output_dir)
    if not files:
        raise FileNotFoundError(f"no BMP outputs found in {output_dir}")
    case_bmp_dir = Path(case_bmp_dir)
    allowed_root = case_bmp_dir.parent.parent
    _safe_remove_dir(case_bmp_dir, allowed_root=allowed_root)
    case_bmp_dir.mkdir(parents=True, exist_ok=True)
    for src in files:
        shutil.copy2(src, case_bmp_dir / src.name)
    return {
        "source_dir": str(output_dir),
        "case_bmp_dir": str(case_bmp_dir),
        "bmp_count": len(files),
    }


def _read_tsv(path: Path) -> list[dict[str, str]]:
    if not Path(path).exists():
        return []
    with Path(path).open("r", encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh, delimiter="\t"))


def upsert_paths_tsv(path: Path, case: GmfCase) -> None:
    path = Path(path)
    rows = _read_tsv(path)
    new_row = case.to_row()
    replaced = False
    out_rows: list[dict[str, str]] = []
    for row in rows:
        normalized = {field: row.get(field, "") for field in TSV_FIELDS}
        if normalized["case"] == case.case:
            out_rows.append(new_row)
            replaced = True
        else:
            out_rows.append(normalized)
    if not replaced:
        out_rows.append(new_row)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=TSV_FIELDS, delimiter="\t", lineterminator="\n")
        writer.writeheader()
        writer.writerows(out_rows)


def _run_command(command: list[str], log_path: Path) -> None:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("w", encoding="utf-8", errors="replace") as log:
        proc = subprocess.run(command, stdout=log, stderr=subprocess.STDOUT, text=True)
    if proc.returncode != 0:
        raise RuntimeError(f"inference failed with code {proc.returncode}: {log_path}")


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Prepare a 20260603 GMF package entry for an R61 candidate.")
    parser.add_argument("--package-root", type=Path, default=DEFAULT_PACKAGE_ROOT)
    parser.add_argument("--weights", type=Path, default=DEFAULT_WEIGHTS)
    parser.add_argument("--input-dir", type=Path, default=None)
    parser.add_argument("--recon-root", type=Path, default=DEFAULT_RECON_ROOT)
    parser.add_argument("--case-name", default=DEFAULT_CASE_NAME)
    parser.add_argument("--role", default=DEFAULT_ROLE)
    parser.add_argument("--device", default="cuda:0")
    parser.add_argument("--psf-path", type=Path, default=LAB_PSF_PATH)
    parser.add_argument("--anchor-output-mode", choices=("none", "blend", "detail"), default="none")
    parser.add_argument("--anchor-alpha", type=float, default=0.10)
    parser.add_argument("--anchor-sigma", type=float, default=2.0)
    parser.add_argument("--anchor-detail-gain", type=float, default=0.35)
    parser.add_argument("--note", default="R61 R39 a970 candidate reconstruction; GMF score must be generated externally.")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--sync-existing-output", type=Path, default=None)
    return parser


def run_package(args: argparse.Namespace) -> dict[str, object]:
    package_root = Path(args.package_root).resolve()
    input_dir = Path(args.input_dir or (package_root / "00_raw_input" / "bmp")).resolve()
    recon_root = Path(args.recon_root).resolve()
    weights = Path(args.weights).resolve()
    psf_path = Path(args.psf_path).resolve()
    case_name = str(args.case_name)
    case_bmp_dir = package_root / case_name / "bmp"
    score_folder = package_root / "_gmf_scores" / case_name
    paths_tsv = package_root / "paths_for_gmf_tool.tsv"
    run_dir = package_root / f"_r61_real_sample_runtime_{time.strftime('%Y%m%d_%H%M%S')}"

    input_count = len(_bmp_files(input_dir))
    if input_count <= 0:
        raise FileNotFoundError(f"no BMP inputs found in {input_dir}")
    if not weights.is_file():
        raise FileNotFoundError(f"weights not found: {weights}")
    if not psf_path.is_file():
        raise FileNotFoundError(f"PSF file not found: {psf_path}")

    infer_script = prepare_infer_script(run_dir)
    command = build_infer_command(
        infer_script=infer_script,
        weights=weights,
        input_dir=input_dir,
        recon_root=recon_root,
        output_name=case_name,
        device=str(args.device),
        psf_path=psf_path,
        anchor_output_mode=str(args.anchor_output_mode),
        anchor_alpha=float(args.anchor_alpha),
        anchor_sigma=float(args.anchor_sigma),
        anchor_detail_gain=float(args.anchor_detail_gain),
    )

    if args.dry_run:
        return {
            "dry_run": True,
            "input_count": input_count,
            "command": command,
            "case_bmp_dir": str(case_bmp_dir),
            "paths_tsv": str(paths_tsv),
            "score_folder": str(score_folder),
        }

    if args.sync_existing_output is not None:
        output_dir = Path(args.sync_existing_output).resolve()
        log_path = None
    else:
        log_path = run_dir / "logs" / f"{case_name}_infer.log"
        _run_command(command, log_path)
        output_dir = _latest_case_output(recon_root, case_name)

    sync = sync_reconstruction_to_case(output_dir, case_bmp_dir)
    if int(sync["bmp_count"]) != input_count:
        raise RuntimeError(f"expected {input_count} BMP outputs, got {sync['bmp_count']}")

    score_folder.mkdir(parents=True, exist_ok=True)
    case = GmfCase(
        case=case_name,
        role=str(args.role),
        image_folder=case_bmp_dir,
        score_folder=score_folder,
        image_count=int(sync["bmp_count"]),
        note=str(args.note),
    )
    upsert_paths_tsv(paths_tsv, case)

    manifest = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "case": case.to_row(),
        "weights": str(weights),
        "input_dir": str(input_dir),
        "input_count": input_count,
        "recon_output_dir": str(output_dir),
        "recon_root": str(recon_root),
        "infer_script": str(infer_script),
        "infer_log": None if log_path is None else str(log_path),
        "command": command,
        **sync,
    }
    manifest_path = package_root / f"{case_name}_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    manifest["manifest_path"] = str(manifest_path)
    return manifest


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    result = run_package(args)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

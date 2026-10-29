"""Prepare clean Step external-GMF validation packages.

The Step source has two frames at every commanded position. External GMF tools
usually consume one filename-sorted image sequence per folder, so this script
splits the package into rep0 and rep1 sequences instead of leaving repeated
same-position frames interleaved with commanded motion frames.
"""
from __future__ import annotations

import argparse
import csv
import json
import shutil
from datetime import datetime
from pathlib import Path


CASE_SPECS = [
    ("00_raw_input", "raw_step_center2048", "center2048_bmp"),
    ("01_r39_psfoff", "r39_psfoff", "clean_recon_package/01_r39_*"),
    ("02_v14_psfoff", "v14_psfoff", "clean_recon_package/02_v14_*"),
    ("03_v16_psfoff", "v16_psfoff", "clean_recon_package/03_v16_*"),
]


def read_manifest(path: Path) -> list[dict[str, object]]:
    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        rows = list(csv.DictReader(fh))
    if not rows:
        raise ValueError(f"empty manifest: {path}")
    required = {"selected_step_index", "position_index", "rep0_file", "rep1_file"}
    missing = required - set(rows[0])
    if missing:
        raise ValueError(f"manifest missing columns: {sorted(missing)}")
    parsed: list[dict[str, object]] = []
    for row in rows:
        out = dict(row)
        out["selected_step_index"] = int(float(row["selected_step_index"]))
        out["position_index"] = int(float(row["position_index"]))
        out["rep0_file"] = str(row["rep0_file"])
        out["rep1_file"] = str(row["rep1_file"])
        parsed.append(out)
    return parsed


def resolve_case_source(audit_root: Path, source_spec: str) -> Path:
    if "*" not in source_spec:
        path = audit_root / source_spec
        if path.is_dir():
            return path
        raise FileNotFoundError(f"missing source folder: {path}")
    prefix, pattern = source_spec.split("/", 1)
    base = audit_root / prefix
    matches = sorted(p / "bmp" for p in base.glob(pattern) if (p / "bmp").is_dir())
    if len(matches) == 1:
        return matches[0]
    if not matches:
        raise FileNotFoundError(f"no source folders match {base / pattern}")
    raise FileExistsError(f"multiple source folders match {base / pattern}: {matches}")


def write_tsv(path: Path, rows: list[dict[str, object]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(
            fh,
            fieldnames=["case", "role", "image_folder", "score_folder", "image_count", "note"],
            delimiter="\t",
            lineterminator="\n",
        )
        writer.writeheader()
        writer.writerows(rows)


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def prepare_package(
    audit_root: Path,
    manifest_path: Path,
    out_root: Path,
    spacing_label: str,
    expected_step_um: float,
    camera_pixel_um: float,
    magnification: float,
) -> dict[str, object]:
    positions = read_manifest(manifest_path)
    if out_root.exists():
        raise FileExistsError(f"output already exists: {out_root}")
    out_root.mkdir(parents=True)
    score_root = out_root / "_gmf_scores"
    score_root.mkdir()

    object_pixel_um = camera_pixel_um / magnification
    expected_step_px = expected_step_um / object_pixel_um
    tsv_rows: list[dict[str, object]] = []
    seq_rows: list[dict[str, object]] = []
    case_rows: list[dict[str, object]] = []

    for base_case, role, source_spec in CASE_SPECS:
        source_dir = resolve_case_source(audit_root, source_spec)
        for rep in (0, 1):
            case_name = f"{base_case}_rep{rep}"
            case_dir = out_root / case_name / "bmp"
            case_dir.mkdir(parents=True)
            score_dir = score_root / case_name
            score_dir.mkdir()
            for seq_index, row in enumerate(positions):
                filename = str(row[f"rep{rep}_file"])
                src = source_dir / filename
                if not src.is_file():
                    raise FileNotFoundError(f"{case_name} missing {src}")
                dst = case_dir / filename
                shutil.copy2(src, dst)
                seq_rows.append(
                    {
                        "spacing_label": spacing_label,
                        "case": case_name,
                        "role": role,
                        "replicate": rep,
                        "sequence_index": seq_index,
                        "selected_step_index": row["selected_step_index"],
                        "position_index": row["position_index"],
                        "commanded_um_from_start": f"{seq_index * expected_step_um:.6f}",
                        "expected_step_um_to_next": f"{expected_step_um:.6f}" if seq_index < len(positions) - 1 else "",
                        "filename": filename,
                        "source_path": str(src),
                        "package_path": str(dst),
                    }
                )
            note = (
                f"{spacing_label} clean Step external-GMF sequence, replicate {rep}; "
                f"{expected_step_um:g}um per adjacent image, expected {expected_step_px:.6f}px."
            )
            tsv_rows.append(
                {
                    "case": case_name,
                    "role": f"{role}_rep{rep}",
                    "image_folder": str(case_dir),
                    "score_folder": str(score_dir),
                    "image_count": len(positions),
                    "note": note,
                }
            )
            case_rows.append(
                {
                    "case": case_name,
                    "role": f"{role}_rep{rep}",
                    "source_dir": str(source_dir),
                    "image_folder": str(case_dir),
                    "score_folder": str(score_dir),
                    "image_count": len(positions),
                    "replicate": rep,
                    "note": note,
                }
            )

    write_tsv(out_root / "paths_for_gmf_tool.tsv", tsv_rows)
    write_csv(out_root / "sequence_manifest.csv", seq_rows)
    write_csv(out_root / "case_manifest.csv", case_rows)
    readme = f"""# {spacing_label} Step External GMF Validation Package

This package is prepared for external GMF validation.

- Source audit root: `{audit_root}`
- Source manifest: `{manifest_path}`
- Expected adjacent step: `{expected_step_um:g} um`
- Camera pixel / objective: `{camera_pixel_um:g} um / {magnification:g}x`
- Object-plane pixel size: `{object_pixel_um:.6f} um/px`
- Expected adjacent step in image: `{expected_step_px:.6f} px`

Important: the original Step capture has two frames at each commanded position.
This package splits them into `rep0` and `rep1` folders so every GMF case is a
clean monotonic motion sequence. Do not run GMF on an interleaved two-replicate
folder unless the downstream analysis explicitly handles same-position repeats.

Use `paths_for_gmf_tool.tsv` as the external-GMF input table. The expected
output folders are already created under `_gmf_scores/<case>`.
"""
    (out_root / "README_EXTERNAL_GMF_STEP.md").write_text(readme, encoding="utf-8")
    meta = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "spacing_label": spacing_label,
        "audit_root": str(audit_root),
        "manifest_path": str(manifest_path),
        "out_root": str(out_root),
        "expected_step_um": expected_step_um,
        "camera_pixel_um": camera_pixel_um,
        "magnification": magnification,
        "object_pixel_um": object_pixel_um,
        "expected_step_px": expected_step_px,
        "positions_per_replicate": len(positions),
        "case_count": len(tsv_rows),
        "total_images_copied": len(seq_rows),
        "replicate_policy": "split into rep0 and rep1 monotonic sequences",
    }
    (out_root / "package_info.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    return meta


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--audit-root", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--out-root", type=Path, required=True)
    parser.add_argument("--spacing-label", required=True)
    parser.add_argument("--expected-step-um", type=float, required=True)
    parser.add_argument("--camera-pixel-um", type=float, default=2.5)
    parser.add_argument("--magnification", type=float, default=20.0)
    args = parser.parse_args()

    meta = prepare_package(
        audit_root=args.audit_root,
        manifest_path=args.manifest,
        out_root=args.out_root,
        spacing_label=args.spacing_label,
        expected_step_um=args.expected_step_um,
        camera_pixel_um=args.camera_pixel_um,
        magnification=args.magnification,
    )
    print(json.dumps(meta, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

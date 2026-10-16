from __future__ import annotations

import csv
import json
import os
import shutil
from datetime import datetime
from pathlib import Path


ANALYSIS_ROOT = Path(r"D:\GMM_2_Final\20260704_20x_5x_analysis")
PACKAGE_ROOT = ANALYSIS_ROOT / "external_gmf_packages"
FULL_ROOT = PACKAGE_ROOT / "gmf_20260704_20x_5x_full_sequences"
STABLE_ROOT = PACKAGE_ROOT / "gmf_20260704_20x_5x_stable_segments"
GROUPS = ["20x_1um", "20x_0p5um", "5x_1um", "5x_0p5um"]
VARIANTS = [
    ("raw", "raw_input", lambda group: ANALYSIS_ROOT / "raw_inputs" / group / "bmp"),
    ("v16", "r61_v16_psfoff", lambda group: ANALYSIS_ROOT / f"r61_v16_psfoff_{group}" / "bmp"),
]
TSV_FIELDS = ["case", "role", "image_folder", "score_folder", "image_count", "note"]
CASE_FIELDS = [
    "case",
    "group",
    "magnification",
    "role",
    "variant",
    "segment",
    "nominal_step_um",
    "expected_step_px",
    "source_folder",
    "image_folder",
    "score_folder",
    "image_count",
    "first_frame",
    "last_frame",
    "note",
]


def parse_group(group: str) -> tuple[str, float, float]:
    magnification, step = group.split("_", 1)
    nominal_um = 0.5 if "0p5" in step else 1.0
    mag = float(magnification.replace("x", ""))
    expected_px = nominal_um / (3.45 / mag)
    return magnification, nominal_um, expected_px


def bmp_files(path: Path) -> list[Path]:
    return sorted(p for p in path.glob("*.bmp") if p.is_file())


def ensure_clean_dir(path: Path) -> None:
    if path.exists():
        resolved = path.resolve()
        root = PACKAGE_ROOT.resolve()
        if resolved == root or not str(resolved).lower().startswith(str(root).lower()):
            raise ValueError(f"refusing to remove outside package root: {path}")
        shutil.rmtree(path)
    path.mkdir(parents=True, exist_ok=True)


def link_or_copy(src: Path, dst: Path) -> str:
    if dst.exists():
        dst.unlink()
    try:
        os.link(src, dst)
        return "hardlink"
    except OSError:
        shutil.copy2(src, dst)
        return "copy"


def write_tsv(path: Path, rows: list[dict[str, object]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=TSV_FIELDS, delimiter="\t", lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row[field] for field in TSV_FIELDS})


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=CASE_FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def stable_segments_for_group(group: str) -> list[tuple[int, int]]:
    motion_steps = ANALYSIS_ROOT / "motion_analysis" / "motion_steps.csv"
    with motion_steps.open("r", encoding="utf-8-sig", newline="") as fh:
        rows = list(csv.DictReader(fh))
    primary_raw = [
        row
        for row in rows
        if row["group"] == group and row["kind"] == "raw" and row["method"] == "primary_grid_area_edge"
    ]
    if not primary_raw:
        raise ValueError(f"no primary raw motion rows found for {group}")
    gaps = sorted(
        int(row["step_index"])
        for row in primary_raw
        if row["time_gap_s"] and float(row["time_gap_s"]) > 30.0
    )
    total_frames = len(primary_raw) + 1
    segments: list[tuple[int, int]] = []
    start = 0
    for gap_step in gaps:
        end = gap_step
        if end - start + 1 >= 2:
            segments.append((start, end))
        start = gap_step + 1
    if total_frames - 1 - start + 1 >= 2:
        segments.append((start, total_frames - 1))
    return segments


def add_case(
    *,
    package_root: Path,
    case_rows: list[dict[str, object]],
    link_rows: list[dict[str, object]],
    group: str,
    variant_key: str,
    role: str,
    source_folder: Path,
    segment_name: str,
    first_frame: int,
    last_frame: int,
    note_suffix: str,
) -> None:
    magnification, nominal_step_um, expected_step_px = parse_group(group)
    case = f"{group}_{segment_name}_{role}"
    image_folder = package_root / case / "bmp"
    score_folder = package_root / "_gmf_scores" / case
    image_folder.mkdir(parents=True, exist_ok=True)
    score_folder.mkdir(parents=True, exist_ok=True)

    source_files = bmp_files(source_folder)
    selected = source_files[first_frame : last_frame + 1]
    if len(selected) != last_frame - first_frame + 1:
        raise RuntimeError(f"case {case} expected frames {first_frame}-{last_frame}, got {len(selected)}")

    for out_idx, src in enumerate(selected):
        dst = image_folder / f"frame_{out_idx:04d}.bmp"
        link_mode = link_or_copy(src, dst)
        link_rows.append(
            {
                "case": case,
                "group": group,
                "variant": variant_key,
                "segment": segment_name,
                "source_frame": first_frame + out_idx,
                "package_frame": out_idx,
                "source_path": str(src),
                "package_path": str(dst),
                "link_mode": link_mode,
            }
        )

    note = (
        f"{role}; group={group}; nominal_step_um={nominal_step_um}; "
        f"expected_step_px={expected_step_px:.6f}; {note_suffix}"
    )
    case_rows.append(
        {
            "case": case,
            "group": group,
            "magnification": magnification,
            "variant": variant_key,
            "segment": segment_name,
            "nominal_step_um": nominal_step_um,
            "expected_step_px": f"{expected_step_px:.9f}",
            "source_folder": str(source_folder),
            "image_folder": str(image_folder),
            "score_folder": str(score_folder),
            "image_count": len(selected),
            "first_frame": first_frame,
            "last_frame": last_frame,
            "note": note,
            "role": role,
        }
    )


def build_full_package() -> dict[str, object]:
    ensure_clean_dir(FULL_ROOT)
    case_rows: list[dict[str, object]] = []
    link_rows: list[dict[str, object]] = []
    for group in GROUPS:
        for variant_key, role, folder_fn in VARIANTS:
            source_folder = folder_fn(group)
            files = bmp_files(source_folder)
            add_case(
                package_root=FULL_ROOT,
                case_rows=case_rows,
                link_rows=link_rows,
                group=group,
                variant_key=variant_key,
                role=role,
                source_folder=source_folder,
                segment_name="full",
                first_frame=0,
                last_frame=len(files) - 1,
                note_suffix="Full sequence; includes original pause intervals.",
            )
    return write_package_files(FULL_ROOT, case_rows, link_rows, "full")


def build_stable_package() -> dict[str, object]:
    ensure_clean_dir(STABLE_ROOT)
    case_rows: list[dict[str, object]] = []
    link_rows: list[dict[str, object]] = []
    for group in GROUPS:
        segments = stable_segments_for_group(group)
        for seg_idx, (first, last) in enumerate(segments):
            segment_name = f"seg{seg_idx:02d}_frames{first:03d}_{last:03d}"
            for variant_key, role, folder_fn in VARIANTS:
                add_case(
                    package_root=STABLE_ROOT,
                    case_rows=case_rows,
                    link_rows=link_rows,
                    group=group,
                    variant_key=variant_key,
                    role=role,
                    source_folder=folder_fn(group),
                    segment_name=segment_name,
                    first_frame=first,
                    last_frame=last,
                    note_suffix="Stable segment; intervals with time gap > 30 s are split out.",
                )
    return write_package_files(STABLE_ROOT, case_rows, link_rows, "stable_segments")


def write_package_files(
    package_root: Path, case_rows: list[dict[str, object]], link_rows: list[dict[str, object]], mode: str
) -> dict[str, object]:
    package_root.mkdir(parents=True, exist_ok=True)
    write_tsv(package_root / "paths_for_gmf_tool.tsv", case_rows)
    write_csv(package_root / "case_manifest.csv", case_rows)
    with (package_root / "link_manifest.csv").open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(link_rows[0].keys()), lineterminator="\n")
        writer.writeheader()
        writer.writerows(link_rows)

    readme = [
        f"# 20260704 20x/5x external GMF package ({mode})",
        "",
        "Use `paths_for_gmf_tool.tsv` as the case list for the external GMF tool.",
        "Each case has a `bmp` image folder and a matching empty `_gmf_scores/<case>` folder.",
        "Please save each returned score as `GMF_score.txt` in that matching score folder.",
        "",
        "Cases use identical frame ordering between Raw and R61 v16 inside the same group/segment.",
        "The image filenames are normalized to `frame_####.bmp` for stable parsing.",
        "",
        "Expected displacement uses camera pixel size 3.45 um divided by the folder magnification label.",
        "20x / 1um is expected to be about 5.797101 px; 20x / 0.5um about 2.898551 px.",
        "5x / 1um is expected to be about 1.449275 px; 5x / 0.5um about 0.724638 px.",
        "",
        "Raw and R61 v16 PSF-off cases are both included.",
    ]
    (package_root / "README_EXTERNAL_GMF.md").write_text("\n".join(readme) + "\n", encoding="utf-8")

    manifest = {
        "generated_at": datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
        "mode": mode,
        "package_root": str(package_root),
        "source_analysis_root": str(ANALYSIS_ROOT),
        "paths_for_gmf_tool": str(package_root / "paths_for_gmf_tool.tsv"),
        "case_manifest": str(package_root / "case_manifest.csv"),
        "case_count": len(case_rows),
        "total_images_linked": sum(int(row["image_count"]) for row in case_rows),
        "cases": case_rows,
    }
    (package_root / "package_manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    return manifest


def verify_package(manifest: dict[str, object]) -> None:
    package_root = Path(str(manifest["package_root"]))
    with (package_root / "paths_for_gmf_tool.tsv").open("r", encoding="utf-8-sig", newline="") as fh:
        tsv_rows = list(csv.DictReader(fh, delimiter="\t"))
    if len(tsv_rows) != int(manifest["case_count"]):
        raise RuntimeError(f"TSV case count mismatch in {package_root}")
    for row in tsv_rows:
        image_folder = Path(row["image_folder"])
        score_folder = Path(row["score_folder"])
        count = len(bmp_files(image_folder))
        expected = int(row["image_count"])
        if count != expected:
            raise RuntimeError(f"{row['case']}: expected {expected} BMP, got {count}")
        if not score_folder.is_dir():
            raise RuntimeError(f"{row['case']}: missing score folder {score_folder}")


def main() -> None:
    PACKAGE_ROOT.mkdir(parents=True, exist_ok=True)
    manifests = [build_full_package(), build_stable_package()]
    for manifest in manifests:
        verify_package(manifest)
    top_readme = [
        "# 20260704 20x/5x external GMF packages",
        "",
        "- `gmf_20260704_20x_5x_full_sequences`: all 50 frames per Raw/R61 case.",
        "- `gmf_20260704_20x_5x_stable_segments`: same data split at capture gaps greater than 30 seconds.",
        "",
        "Run the full package first if you want complete sequence behavior.",
        "Run the stable-segment package if you want to avoid pause/warm-up intervals.",
    ]
    (PACKAGE_ROOT / "README_GMF_PACKAGES.md").write_text("\n".join(top_readme) + "\n", encoding="utf-8")
    print("GMF_PACKAGE_CHECK_OK")
    for manifest in manifests:
        print(f"{manifest['mode']}: {manifest['case_count']} cases, {manifest['total_images_linked']} images")
        print(manifest["package_root"])


if __name__ == "__main__":
    main()

from __future__ import annotations

import argparse
import csv
import json
import os
import shutil
import sys
from collections import Counter
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable

import cv2
import numpy as np

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))
import audit_training_data_style as audit


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_TRAINING_ROOT = REPO_ROOT / "Training_Data"
DEFAULT_UNSAFE_CSV = (
    REPO_ROOT
    / "Reconstruct_Progress"
    / "20260617_training_data_style_audit_full"
    / "unsafe_pair_list.csv"
)
DEFAULT_OUTPUT_ROOT = DEFAULT_TRAINING_ROOT / "r55_source_style_rebuild"
CAD_PACKAGE_PREFIXES = (
    "r49_cad_anchor_source",
    "r49_cad_anchor_real_geometry",
    "r53_realistic_dataset_calibration",
)


@dataclass(frozen=True)
class UnsafeRow:
    package: str
    src: Path
    lbl: Path
    flags: str = ""


@dataclass
class RebuiltPair:
    package: str
    role: str
    stage: str
    source: str
    src: str
    lbl: str
    package_src: str
    package_lbl: str
    repaired: bool
    repair_reason: str
    mask: str = ""
    package_mask: str = ""


def read_gray(path: Path) -> np.ndarray:
    img = cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)
    if img is None:
        raise ValueError(f"Could not read image: {path}")
    return img


def write_image(path: Path, image: np.ndarray) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    ok = cv2.imwrite(str(path), image)
    if not ok:
        raise ValueError(f"Could not write image: {path}")


def _safe_remove_tree(path: Path) -> None:
    resolved = path.resolve()
    lowered = resolved.name.lower()
    if "rebuild" not in lowered and "source_style" not in lowered:
        raise ValueError(f"refusing to remove a non-rebuild directory: {resolved}")
    if resolved.anchor == str(resolved):
        raise ValueError(f"refusing to remove drive root: {resolved}")
    shutil.rmtree(resolved)


def _copy_or_link(src: Path, dst: Path) -> str:
    dst.parent.mkdir(parents=True, exist_ok=True)
    if dst.exists():
        dst.unlink()
    try:
        os.link(src, dst)
        return "hardlink"
    except OSError:
        shutil.copy2(src, dst)
        return "copy"


def _path_key(path: Path) -> str:
    return str(path.resolve()).lower()


def load_unsafe_rows(path: Path) -> list[UnsafeRow]:
    rows: list[UnsafeRow] = []
    with path.open("r", newline="", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            package = str(row.get("package", "")).strip()
            src = str(row.get("src", "")).strip()
            lbl = str(row.get("lbl", "")).strip()
            if not package or not src or not lbl:
                continue
            rows.append(
                UnsafeRow(
                    package=package,
                    src=Path(src),
                    lbl=Path(lbl),
                    flags=str(row.get("flags", "")).strip(),
                )
            )
    return rows


def _rel_after_marker(path: Path, markers: Iterable[str]) -> Path | None:
    marker_names = {name.lower() for name in markers}
    parts = path.parts
    for idx in range(len(parts) - 2, -1, -1):
        if parts[idx].lower() in marker_names:
            return Path(*parts[idx + 1 :])
    return None


def _fallback_pair_rel(record: audit.PairRecord) -> Path:
    stage = str(record.stage or "").strip()
    if stage:
        return Path(stage) / record.src.name
    return Path(record.src.name)


def _package_subrel(record: audit.PairRecord) -> Path:
    rel = _rel_after_marker(record.src, ("src", "source", "input", "lr", "blur", "generated_convolved", "generated_convolved_gaussian_control"))
    if rel is not None and rel.name:
        return rel
    return _fallback_pair_rel(record)


def _mask_subrel(record: audit.PairRecord, src_subrel: Path) -> Path | None:
    if record.mask is None:
        return None
    rel = _rel_after_marker(record.mask, ("mask", "masks"))
    if rel is not None and rel.name:
        return rel
    return src_subrel


def _soft_edge_band(structure: np.ndarray, mask: np.ndarray | None, radius: int) -> np.ndarray:
    structure8 = np.clip(structure, 0, 255).astype(np.uint8)
    if int(structure8.max()) - int(structure8.min()) < 3:
        edge = np.zeros_like(structure8, dtype=np.uint8)
    else:
        edge = cv2.Canny(structure8, 30, 90)

    if np.count_nonzero(edge) < 4 and mask is not None:
        mask8 = np.clip(mask, 0, 255).astype(np.uint8)
        edge = cv2.Canny(mask8, 30, 90)

    if mask is not None:
        mask_bin = (mask > 0).astype(np.uint8) * 255
        keep = cv2.dilate(mask_bin, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7)))
        edge = np.where(keep > 0, edge, 0).astype(np.uint8)

    if np.count_nonzero(edge) == 0:
        return np.zeros_like(structure8, dtype=np.float32)

    k = max(3, int(radius) * 2 + 1)
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k, k))
    band = cv2.dilate(edge, kernel)
    soft = cv2.GaussianBlur(band.astype(np.float32) / 255.0, (0, 0), max(0.6, radius / 2.0))
    return np.clip(soft, 0.0, 1.0)


def make_source_style_label(
    src: np.ndarray,
    structure_label: np.ndarray,
    mask: np.ndarray | None = None,
    *,
    edge_radius: int = 4,
    sharpen_amount: float = 0.65,
) -> np.ndarray:
    if src.ndim != 2:
        raise ValueError("src must be a grayscale image")
    if structure_label.shape != src.shape:
        structure_label = cv2.resize(structure_label, (src.shape[1], src.shape[0]), interpolation=cv2.INTER_NEAREST)
    if mask is not None and mask.shape != src.shape:
        mask = cv2.resize(mask, (src.shape[1], src.shape[0]), interpolation=cv2.INTER_NEAREST)

    src_f = src.astype(np.float32)
    soft = _soft_edge_band(structure_label, mask, edge_radius)
    if float(np.max(soft)) <= 0.0:
        return src.copy()

    blurred = cv2.GaussianBlur(src_f, (0, 0), 1.05)
    sharpened = np.clip(src_f + float(sharpen_amount) * (src_f - blurred), 0, 255)
    repaired = src_f * (1.0 - soft) + sharpened * soft
    return np.clip(np.rint(repaired), 0, 255).astype(np.uint8)


def _must_repair(record: audit.PairRecord, unsafe_by_lbl: dict[str, UnsafeRow]) -> tuple[bool, str]:
    lbl_key = _path_key(record.lbl)
    src_key = _path_key(record.src)
    if lbl_key in unsafe_by_lbl:
        return True, unsafe_by_lbl[lbl_key].flags or "unsafe_audit"
    if src_key in unsafe_by_lbl:
        return True, unsafe_by_lbl[src_key].flags or "unsafe_audit"
    if str(record.role) == "cad_anchor":
        return True, "cad_anchor_source_style_rebuild"
    package = str(record.package).replace("\\", "/")
    if package.startswith("r49_cad_anchor_source/"):
        return True, "cad_anchor_source_style_rebuild"
    path_text = f"{record.src} {record.lbl}".replace("\\", "/").lower()
    if "stage_57_cad_anchor_real" in path_text or "/cad_anchor/" in path_text:
        return True, "cad_anchor_source_style_rebuild"
    return False, ""


def _expanded_packages(records_by_package: dict[str, list[audit.PairRecord]], unsafe_packages: set[str]) -> set[str]:
    selected = set(unsafe_packages)
    unsafe_tops = {pkg.split("/", 1)[0] for pkg in unsafe_packages}
    for package in records_by_package:
        top = package.split("/", 1)[0]
        if top in CAD_PACKAGE_PREFIXES and top in unsafe_tops:
            selected.add(package)
    return selected


def _write_package_manifest(
    package_dir: Path,
    *,
    source_package: str,
    source_training_root: Path,
    unsafe_csv: Path,
    records: list[RebuiltPair],
    link_counts: Counter[str],
) -> None:
    count_by_stage = Counter(record.stage for record in records)
    count_by_role = Counter(record.role for record in records)
    manifest = {
        "generator": "rebuild_source_style_training_data_v1",
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "source_training_root": str(source_training_root.resolve()),
        "source_package": source_package,
        "unsafe_csv": str(unsafe_csv.resolve()),
        "output_dir": str(package_dir.resolve()),
        "total_pairs": len(records),
        "repaired_pairs": sum(1 for record in records if record.repaired),
        "label_policy": (
            "Repaired labels keep the source-image grayscale style. CAD or old label images are used only "
            "to locate edge bands, not as direct black/white target fills."
        ),
        "count_by_stage": dict(count_by_stage),
        "count_by_role": dict(count_by_role),
        "link_counts": dict(link_counts),
        "pairs": [asdict(record) for record in records],
    }
    (package_dir / "manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")


def _copy_package_pair(
    record: audit.PairRecord,
    package_dir: Path,
    unsafe_by_lbl: dict[str, UnsafeRow],
) -> tuple[RebuiltPair, Counter[str]]:
    link_counts: Counter[str] = Counter()
    src_subrel = _package_subrel(record)
    src_rel = Path("src") / src_subrel
    lbl_rel = Path("lbl") / src_subrel
    mask_subrel = _mask_subrel(record, src_subrel)
    mask_rel = Path("mask") / mask_subrel if mask_subrel is not None else None

    link_counts[_copy_or_link(record.src, package_dir / src_rel)] += 1
    repair, reason = _must_repair(record, unsafe_by_lbl)
    if repair:
        src_img = read_gray(record.src)
        old_lbl = read_gray(record.lbl)
        mask_img = read_gray(record.mask) if record.mask is not None and record.mask.exists() else None
        repaired = make_source_style_label(src_img, old_lbl, mask_img)
        write_image(package_dir / lbl_rel, repaired)
        link_counts["repaired_label"] += 1
    else:
        link_counts[_copy_or_link(record.lbl, package_dir / lbl_rel)] += 1

    package_mask = ""
    if record.mask is not None and record.mask.exists() and mask_rel is not None:
        link_counts[_copy_or_link(record.mask, package_dir / mask_rel)] += 1
        package_mask = mask_rel.as_posix()

    return (
        RebuiltPair(
            package=record.package,
            role=str(record.role or ""),
            stage=str(record.stage or ""),
            source=str(record.source or ""),
            src=str(record.src),
            lbl=str(record.lbl),
            package_src=src_rel.as_posix(),
            package_lbl=lbl_rel.as_posix(),
            repaired=repair,
            repair_reason=reason,
            mask=str(record.mask) if record.mask else "",
            package_mask=package_mask,
        ),
        link_counts,
    )


def rebuild_one_package(
    package: str,
    records: list[audit.PairRecord],
    *,
    output_root: Path,
    source_training_root: Path,
    unsafe_csv: Path,
    unsafe_by_lbl: dict[str, UnsafeRow],
) -> dict[str, Any]:
    package_dir = output_root / Path(package)
    package_dir.mkdir(parents=True, exist_ok=True)
    rebuilt: list[RebuiltPair] = []
    link_counts: Counter[str] = Counter()
    for record in sorted(records, key=lambda item: (str(item.stage), str(item.src))):
        rebuilt_pair, pair_counts = _copy_package_pair(record, package_dir, unsafe_by_lbl)
        rebuilt.append(rebuilt_pair)
        link_counts.update(pair_counts)
    _write_package_manifest(
        package_dir,
        source_package=package,
        source_training_root=source_training_root,
        unsafe_csv=unsafe_csv,
        records=rebuilt,
        link_counts=link_counts,
    )
    return {
        "package": package,
        "output_dir": str(package_dir),
        "total_pairs": len(rebuilt),
        "repaired_pairs": sum(1 for item in rebuilt if item.repaired),
        "link_counts": dict(link_counts),
    }


def _write_summary_report(output_root: Path, package_rows: list[dict[str, Any]], args: dict[str, Any]) -> None:
    total_pairs = sum(int(row["total_pairs"]) for row in package_rows)
    total_repaired = sum(int(row["repaired_pairs"]) for row in package_rows)
    lines = [
        "# Source-Style Training Data Rebuild",
        "",
        f"- generated_at: `{datetime.now().isoformat(timespec='seconds')}`",
        f"- source_training_root: `{args['training_root']}`",
        f"- unsafe_csv: `{args['unsafe_csv']}`",
        f"- rebuilt_packages: `{len(package_rows)}`",
        f"- total_pairs: `{total_pairs}`",
        f"- repaired_pairs: `{total_repaired}`",
        "",
        "## Policy",
        "",
        "CAD/old labels are used only to locate boundary bands. Repaired targets keep the source-image grayscale style.",
        "",
        "## Packages",
        "",
        "| package | pairs | repaired |",
        "|---|---:|---:|",
    ]
    for row in sorted(package_rows, key=lambda item: str(item["package"])):
        lines.append(f"| `{row['package']}` | {row['total_pairs']} | {row['repaired_pairs']} |")
    lines.append("")
    (output_root / "REBUILD_SUMMARY.md").write_text("\n".join(lines), encoding="utf-8")


def _make_preview(output_root: Path, rows: list[dict[str, Any]], limit: int = 24) -> None:
    chosen: list[tuple[Path, dict[str, Any]]] = []
    for package_row in rows:
        manifest_path = Path(str(package_row["output_dir"])) / "manifest.json"
        if not manifest_path.exists():
            continue
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        for pair in manifest.get("pairs", []):
            if pair.get("repaired"):
                chosen.append((manifest_path.parent, pair))
            if len(chosen) >= limit:
                break
        if len(chosen) >= limit:
            break
    if not chosen:
        return

    tile_h, tile_w = 150, 150
    label_h = 32
    panels: list[np.ndarray] = []
    for base, pair in chosen:
        try:
            src = read_gray(base / pair["package_src"])
            new_lbl = read_gray(base / pair["package_lbl"])
            old_lbl = read_gray(Path(pair["lbl"]))
            diff = np.clip(np.abs(src.astype(np.int16) - new_lbl.astype(np.int16)), 0, 255).astype(np.uint8)
            tiles = []
            for name, img in (("src", src), ("old", old_lbl), ("new", new_lbl), ("diff", diff)):
                bgr = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
                bgr = cv2.resize(bgr, (tile_w, tile_h), interpolation=cv2.INTER_AREA)
                cv2.putText(bgr, name, (6, 18), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 255, 255), 1, cv2.LINE_AA)
                tiles.append(bgr)
            panel = np.concatenate(tiles, axis=1)
            caption = np.full((label_h, panel.shape[1], 3), 245, dtype=np.uint8)
            text = f"{pair['package'][:60]} {pair['repair_reason'][:50]}"
            cv2.putText(caption, text, (5, 21), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (20, 20, 20), 1, cv2.LINE_AA)
            panels.append(np.concatenate([caption, panel], axis=0))
        except Exception:
            continue
    if panels:
        write_image(output_root / "repaired_pair_preview.png", np.concatenate(panels, axis=0))


def rebuild_from_audit(
    *,
    training_root: Path,
    unsafe_csv: Path,
    output_root: Path,
    force: bool = False,
    packages: list[str] | None = None,
) -> dict[str, Any]:
    training_root = Path(training_root).resolve()
    unsafe_csv = Path(unsafe_csv).resolve()
    output_root = Path(output_root).resolve()
    if output_root.exists():
        if not force:
            raise FileExistsError(f"output directory already exists: {output_root}")
        _safe_remove_tree(output_root)
    output_root.mkdir(parents=True, exist_ok=True)

    unsafe_rows = load_unsafe_rows(unsafe_csv)
    unsafe_by_lbl = {_path_key(row.lbl): row for row in unsafe_rows}
    unsafe_by_lbl.update({_path_key(row.src): row for row in unsafe_rows})
    unsafe_packages = {row.package for row in unsafe_rows}

    records = audit.discover_pairs(training_root)
    records_by_package: dict[str, list[audit.PairRecord]] = {}
    for record in records:
        if _path_key(record.src).startswith(_path_key(output_root)):
            continue
        records_by_package.setdefault(record.package, []).append(record)

    selected = set(packages) if packages else _expanded_packages(records_by_package, unsafe_packages)
    missing = sorted(package for package in selected if package not in records_by_package)
    if missing:
        raise ValueError(f"selected packages were not discovered: {missing}")

    package_rows = []
    for package in sorted(selected):
        package_rows.append(
            rebuild_one_package(
                package,
                records_by_package[package],
                output_root=output_root,
                source_training_root=training_root,
                unsafe_csv=unsafe_csv,
                unsafe_by_lbl=unsafe_by_lbl,
            )
        )

    args = {"training_root": str(training_root), "unsafe_csv": str(unsafe_csv)}
    _write_summary_report(output_root, package_rows, args)
    _make_preview(output_root, package_rows)

    summary = {
        "output_root": str(output_root),
        "unsafe_csv": str(unsafe_csv),
        "package_count": len(package_rows),
        "total_pairs": sum(int(row["total_pairs"]) for row in package_rows),
        "repaired_pairs": sum(int(row["repaired_pairs"]) for row in package_rows),
        "packages": package_rows,
    }
    (output_root / "rebuild_summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    return summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--training-root", type=Path, default=DEFAULT_TRAINING_ROOT)
    parser.add_argument("--unsafe-csv", type=Path, default=DEFAULT_UNSAFE_CSV)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--package", action="append", dest="packages", default=None)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    summary = rebuild_from_audit(
        training_root=args.training_root,
        unsafe_csv=args.unsafe_csv,
        output_root=args.output_root,
        force=args.force,
        packages=args.packages,
    )
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

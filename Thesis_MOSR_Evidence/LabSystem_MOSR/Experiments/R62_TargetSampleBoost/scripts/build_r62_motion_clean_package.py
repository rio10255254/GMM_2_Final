from __future__ import annotations

import argparse
import csv
import json
import os
import shutil
from collections import Counter
from pathlib import Path
from typing import Any, Iterable


FILE_FIELDS = (
    "package_src",
    "package_lbl",
    "geometry_boundary",
    "geometry_centerline",
    "geometry_distance",
    "motion_meta",
)


def _read_csv(path: Path) -> list[dict[str, str]]:
    with Path(path).open("r", newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def _safe_rel(path_text: str) -> Path:
    rel = Path(str(path_text).replace("\\", "/"))
    if rel.is_absolute() or any(part == ".." for part in rel.parts):
        raise ValueError(f"unsafe package-relative path: {path_text}")
    return rel


def _copy_or_link(source: Path, dest: Path, *, link_mode: str) -> None:
    if dest.exists():
        return
    if not source.exists():
        raise FileNotFoundError(f"missing package file: {source}")
    dest.parent.mkdir(parents=True, exist_ok=True)
    if link_mode == "copy":
        shutil.copy2(source, dest)
        return
    try:
        os.link(source, dest)
    except OSError:
        shutil.copy2(source, dest)


def _drop_indices_from_audit(
    affected_pairs_csv: Path,
    *,
    drop_risk_types: tuple[str, ...],
) -> tuple[set[int], Counter[str]]:
    risk_allow = {str(risk).strip() for risk in drop_risk_types if str(risk).strip()}
    indices: set[int] = set()
    by_risk: Counter[str] = Counter()
    for row in _read_csv(Path(affected_pairs_csv)):
        risk = str(row.get("risk_type") or "")
        if risk not in risk_allow:
            continue
        index_text = str(row.get("manifest_index") or "")
        if not index_text:
            continue
        index = int(index_text)
        indices.add(index)
        by_risk[risk] += 1
    return indices, by_risk


def _copy_pair_files(source_package: Path, dest_package: Path, pairs: Iterable[dict[str, Any]], *, link_mode: str) -> int:
    copied: set[str] = set()
    for pair in pairs:
        for field in FILE_FIELDS:
            rel_text = str(pair.get(field) or "").strip()
            if not rel_text:
                continue
            rel = _safe_rel(rel_text)
            key = rel.as_posix().lower()
            if key in copied:
                continue
            _copy_or_link(source_package / rel, dest_package / rel, link_mode=link_mode)
            copied.add(key)
    return len(copied)


def _role_counts(pairs: list[dict[str, Any]]) -> dict[str, int]:
    return dict(sorted(Counter(str(pair.get("role", "unknown")) for pair in pairs).items()))


def _assert_safe_overwrite(source_package: Path, dest_package: Path) -> None:
    source_resolved = source_package.resolve()
    dest_resolved = dest_package.resolve()
    if dest_resolved == source_resolved:
        raise ValueError("destination package cannot be the source package")
    if source_resolved not in dest_resolved.parents:
        raise ValueError("overwrite is only allowed for a destination inside the same package root")


def create_clean_package(
    *,
    source_package: Path,
    dest_package: Path,
    affected_pairs_csv: Path,
    new_profile: str,
    drop_risk_types: tuple[str, ...] = (
        "direct_label_conflict",
        "source_texture_only",
        "affected_context",
    ),
    link_mode: str = "hardlink",
    overwrite: bool = False,
) -> dict[str, Any]:
    source_package = Path(source_package)
    dest_package = Path(dest_package)
    manifest_path = source_package / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    pairs = list(manifest.get("pairs", []))
    drop_indices, dropped_by_risk = _drop_indices_from_audit(
        Path(affected_pairs_csv),
        drop_risk_types=drop_risk_types,
    )
    if dest_package.exists():
        if not overwrite:
            raise FileExistsError(f"destination package already exists: {dest_package}")
        _assert_safe_overwrite(source_package, dest_package)
        shutil.rmtree(dest_package)
    kept_pairs = [pair for index, pair in enumerate(pairs) if index not in drop_indices]
    copied_file_count = _copy_pair_files(
        source_package,
        dest_package,
        kept_pairs,
        link_mode=link_mode,
    )
    clean_manifest = dict(manifest)
    clean_manifest["profile"] = str(new_profile)
    clean_manifest["pairs"] = kept_pairs
    clean_manifest["total_pairs"] = len(kept_pairs)
    clean_manifest["role_counts"] = _role_counts(kept_pairs)
    clean_manifest["geometry_count"] = len(kept_pairs)
    clean_manifest["r62_motion_quality_filter"] = {
        "source_profile": manifest.get("profile"),
        "source_package": str(source_package),
        "affected_pairs_csv": str(affected_pairs_csv),
        "drop_risk_types": list(drop_risk_types),
        "dropped_pair_count": len(pairs) - len(kept_pairs),
        "kept_pair_count": len(kept_pairs),
        "dropped_by_risk": dict(sorted(dropped_by_risk.items())),
    }
    dest_package.mkdir(parents=True, exist_ok=True)
    (dest_package / "manifest.json").write_text(
        json.dumps(clean_manifest, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    summary = {
        "source_package": str(source_package),
        "dest_package": str(dest_package),
        "new_profile": str(new_profile),
        "source_pair_count": len(pairs),
        "kept_pair_count": len(kept_pairs),
        "dropped_pair_count": len(pairs) - len(kept_pairs),
        "copied_file_count": copied_file_count,
        "dropped_by_risk": dict(sorted(dropped_by_risk.items())),
        "manifest_path": str(dest_package / "manifest.json"),
    }
    (dest_package / "clean_package_summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return summary


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build an R62 motion-clean package from an audit CSV.")
    parser.add_argument("--source-package", required=True)
    parser.add_argument("--dest-package", required=True)
    parser.add_argument("--affected-pairs-csv", required=True)
    parser.add_argument("--new-profile", required=True)
    parser.add_argument(
        "--drop-risk-type",
        action="append",
        dest="drop_risk_types",
        default=None,
        help="Risk type to remove. Can be passed multiple times.",
    )
    parser.add_argument("--link-mode", choices=["hardlink", "copy"], default="hardlink")
    parser.add_argument("--overwrite", action="store_true")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    risk_types = (
        tuple(args.drop_risk_types)
        if args.drop_risk_types
        else ("direct_label_conflict", "source_texture_only", "affected_context")
    )
    summary = create_clean_package(
        source_package=Path(args.source_package),
        dest_package=Path(args.dest_package),
        affected_pairs_csv=Path(args.affected_pairs_csv),
        new_profile=str(args.new_profile),
        drop_risk_types=risk_types,
        link_mode=str(args.link_mode),
        overwrite=bool(args.overwrite),
    )
    print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()

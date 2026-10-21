r"""Create a complete, read-only metadata inventory of the project tree.

The inventory includes hidden, ignored, and Git-internal entries. It never
follows symlinks or Windows junctions and never reads large payload contents.
Small text headings are sampled only to make the document index searchable.

Example:
    python Tools/project_file_inventory.py \
        --root D:\GMM_2_Final \
        --output H:\GMM_2_Final_Archive\inventory_snapshots\20260810_full_project
"""

from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import heapq
import json
import os
import time
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, TextIO


GIB = 1024**3
MIB = 1024**2
FILE_ATTRIBUTE_REPARSE_POINT = 0x0400

DOCUMENT_EXTENSIONS = {
    ".csv",
    ".doc",
    ".docx",
    ".html",
    ".json",
    ".md",
    ".ods",
    ".odt",
    ".pdf",
    ".ppt",
    ".pptx",
    ".rst",
    ".tex",
    ".tsv",
    ".txt",
    ".xls",
    ".xlsx",
    ".xml",
    ".yaml",
    ".yml",
}

SOURCE_EXTENSIONS = {
    ".bat",
    ".c",
    ".cc",
    ".cmd",
    ".cpp",
    ".cu",
    ".h",
    ".hpp",
    ".ipynb",
    ".js",
    ".m",
    ".ps1",
    ".py",
    ".r",
    ".sh",
    ".sql",
    ".ts",
}

TEXT_TITLE_EXTENSIONS = {".md", ".rst", ".txt"}
MULTI_EXTENSIONS = (".pth.tar", ".tar.gz", ".nii.gz", ".csv.gz", ".json.gz")
CACHE_SEGMENTS = {
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    "__pycache__",
    "cache",
    "caches",
    "tmp",
    "temp",
}
TEMP_NAME_TOKENS = (".tmp", ".bak", "~", "scratch", "temporary", "temp_")


@dataclass
class Aggregate:
    files: int = 0
    directories: int = 0
    bytes: int = 0
    documents: int = 0
    source_files: int = 0

    def add_file(self, size: int, is_document: bool, is_source: bool) -> None:
        self.files += 1
        self.bytes += size
        self.documents += int(is_document)
        self.source_files += int(is_source)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def normalized_extension(name: str) -> str:
    lower = name.lower()
    for suffix in MULTI_EXTENSIONS:
        if lower.endswith(suffix):
            return suffix
    suffix = Path(lower).suffix
    return suffix or "[no extension]"


def is_document_extension(extension: str) -> bool:
    return extension in DOCUMENT_EXTENSIONS


def is_source_extension(extension: str) -> bool:
    return extension in SOURCE_EXTENSIONS


def classify_category(relative_path: str, extension: str) -> str:
    parts = [part.lower() for part in Path(relative_path).parts]
    top = parts[0] if parts else ""

    if any(part in CACHE_SEGMENTS for part in parts) or top.startswith("_tmp"):
        return "cache_or_temporary"
    if top == ".git":
        return "version_history"
    if top == "experiments":
        return "experiments"
    if top == "traing_progress":
        return "training_history"
    if top == "training_data":
        return "training_data"
    if top == "reconstruct_progress":
        return "reconstruction_history"
    if top == "step":
        return "raw_acquisition"
    if top == "psf_fitting":
        return "psf_workflow"
    if top == "model":
        return "model_mainline"
    if top == "tools":
        return "tooling"
    if top == "thesis_mosr_evidence":
        return "thesis_workspace"
    if top == "analysislab" or "analysis" in top:
        return "analysis_workspace"
    if top == "docs" or (len(parts) == 1 and is_document_extension(extension)):
        return "documentation_and_governance"
    return "other_project_content"


def age_bucket(age_days: float) -> str:
    if age_days < 0:
        return "future_timestamp"
    if age_days < 7:
        return "0_7_days"
    if age_days < 30:
        return "8_30_days"
    if age_days < 90:
        return "31_90_days"
    if age_days < 180:
        return "91_180_days"
    if age_days < 365:
        return "181_365_days"
    return "over_365_days"


def is_reparse(stat_result: os.stat_result, entry: os.DirEntry[str]) -> bool:
    attributes = int(getattr(stat_result, "st_file_attributes", 0))
    return bool(attributes & FILE_ATTRIBUTE_REPARSE_POINT) or entry.is_symlink()


def title_hint(path: Path, extension: str, max_bytes: int = 65536) -> str:
    if extension not in TEXT_TITLE_EXTENSIONS:
        return ""
    try:
        with path.open("rb") as handle:
            raw = handle.read(max_bytes)
        text = raw.decode("utf-8-sig", errors="replace")
    except OSError:
        return ""

    for line in text.splitlines():
        candidate = line.strip().lstrip("#").strip()
        if candidate:
            return candidate[:240]
    return ""


def safe_iso_timestamp(timestamp: float) -> str:
    try:
        return datetime.fromtimestamp(timestamp, timezone.utc).isoformat()
    except (OSError, OverflowError, ValueError):
        return ""


def path_inside(child: Path, parent: Path) -> bool:
    try:
        child.resolve(strict=False).relative_to(parent.resolve(strict=False))
        return True
    except ValueError:
        return False


def write_table(path: Path, header: list[str], rows: Iterable[Iterable[object]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(header)
        writer.writerows(rows)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def push_largest(heap: list[tuple[int, str]], limit: int, size: int, relative: str) -> None:
    item = (size, relative)
    if len(heap) < limit:
        heapq.heappush(heap, item)
    elif item > heap[0]:
        heapq.heapreplace(heap, item)


def scan(root: Path, output: Path, largest_limit: int, duplicate_min_bytes: int) -> dict:
    root = root.resolve(strict=True)
    output = output.resolve(strict=False)
    if path_inside(output, root):
        raise ValueError("Output directory must be outside the scanned project tree")
    if output.exists():
        raise FileExistsError(f"Output directory already exists: {output}")
    output.mkdir(parents=True)

    started_at = utc_now()
    started_epoch = time.time()

    inventory_path = output / "inventory_entries.csv.gz"
    documents_path = output / "documents.csv.gz"
    errors_path = output / "scan_errors.csv"

    extensions: dict[str, Aggregate] = defaultdict(Aggregate)
    categories: dict[str, Aggregate] = defaultdict(Aggregate)
    ages: dict[str, Aggregate] = defaultdict(Aggregate)
    tree: dict[str, Aggregate] = defaultdict(Aggregate)
    largest_heap: list[tuple[int, str]] = []
    large_sizes: dict[int, list[str]] = defaultdict(list)

    total_files = 0
    total_directories = 0
    total_other_entries = 0
    total_bytes = 0
    document_files = 0
    source_files = 0
    long_paths = 0
    temporary_name_files = 0
    reparse_entries = 0
    hardlink_entries = 0
    hardlink_logical_bytes = 0
    hardlink_unique_bytes = 0
    hardlink_keys: set[tuple[int, int]] = set()
    error_count = 0

    with (
        gzip.open(inventory_path, "wt", encoding="utf-8", newline="", compresslevel=6) as inventory_handle,
        gzip.open(documents_path, "wt", encoding="utf-8", newline="", compresslevel=6) as documents_handle,
        errors_path.open("w", encoding="utf-8", newline="") as errors_handle,
    ):
        inventory_writer = csv.writer(inventory_handle)
        inventory_writer.writerow(
            [
                "relative_path",
                "kind",
                "size_bytes",
                "mtime_ns",
                "extension",
                "top_level",
                "depth",
                "category",
                "is_document",
                "is_source",
                "link_count",
                "path_length",
            ]
        )
        documents_writer = csv.writer(documents_handle)
        documents_writer.writerow(
            [
                "relative_path",
                "extension",
                "size_bytes",
                "modified_utc",
                "category",
                "title_hint",
            ]
        )
        errors_writer = csv.writer(errors_handle)
        errors_writer.writerow(["relative_path", "operation", "error"])

        stack = [root]
        last_progress = time.monotonic()

        while stack:
            current = stack.pop()
            try:
                entries = list(os.scandir(current))
            except OSError as exc:
                error_count += 1
                relative = current.relative_to(root).as_posix() if current != root else "."
                errors_writer.writerow([relative, "scandir", str(exc)])
                continue

            entries.sort(key=lambda entry: entry.name.casefold(), reverse=True)
            for entry in entries:
                path = Path(entry.path)
                relative = path.relative_to(root).as_posix()
                parts = Path(relative).parts
                top_level = parts[0] if parts else "[root]"
                depth = len(parts)
                path_length = len(str(path))

                try:
                    stat_result = entry.stat(follow_symlinks=False)
                except OSError as exc:
                    error_count += 1
                    errors_writer.writerow([relative, "stat", str(exc)])
                    continue

                reparse = is_reparse(stat_result, entry)
                if reparse:
                    reparse_entries += 1
                    total_other_entries += 1
                    inventory_writer.writerow(
                        [
                            relative,
                            "reparse",
                            stat_result.st_size,
                            stat_result.st_mtime_ns,
                            normalized_extension(entry.name),
                            top_level,
                            depth,
                            "reparse_not_followed",
                            0,
                            0,
                            getattr(stat_result, "st_nlink", 1),
                            path_length,
                        ]
                    )
                    continue

                if entry.is_dir(follow_symlinks=False):
                    total_directories += 1
                    inventory_writer.writerow(
                        [
                            relative,
                            "directory",
                            0,
                            stat_result.st_mtime_ns,
                            "[directory]",
                            top_level,
                            depth,
                            classify_category(relative, "[directory]"),
                            0,
                            0,
                            getattr(stat_result, "st_nlink", 1),
                            path_length,
                        ]
                    )
                    for prefix_depth in range(1, min(depth, 3) + 1):
                        prefix = "/".join(parts[:prefix_depth])
                        tree[prefix].directories += 1
                    stack.append(path)
                    continue

                if not entry.is_file(follow_symlinks=False):
                    total_other_entries += 1
                    inventory_writer.writerow(
                        [
                            relative,
                            "other",
                            stat_result.st_size,
                            stat_result.st_mtime_ns,
                            normalized_extension(entry.name),
                            top_level,
                            depth,
                            "other_entry",
                            0,
                            0,
                            getattr(stat_result, "st_nlink", 1),
                            path_length,
                        ]
                    )
                    continue

                size = int(stat_result.st_size)
                extension = normalized_extension(entry.name)
                document = is_document_extension(extension)
                source = is_source_extension(extension)
                category = classify_category(relative, extension)
                link_count = int(getattr(stat_result, "st_nlink", 1))

                total_files += 1
                total_bytes += size
                document_files += int(document)
                source_files += int(source)
                long_paths += int(path_length >= 240)
                temporary_name_files += int(any(token in entry.name.lower() for token in TEMP_NAME_TOKENS))

                if link_count > 1:
                    hardlink_entries += 1
                    hardlink_logical_bytes += size
                    hardlink_key = (int(stat_result.st_dev), int(stat_result.st_ino))
                    if hardlink_key not in hardlink_keys:
                        hardlink_keys.add(hardlink_key)
                        hardlink_unique_bytes += size

                inventory_writer.writerow(
                    [
                        relative,
                        "file",
                        size,
                        stat_result.st_mtime_ns,
                        extension,
                        top_level,
                        depth,
                        category,
                        int(document),
                        int(source),
                        link_count,
                        path_length,
                    ]
                )

                if document:
                    documents_writer.writerow(
                        [
                            relative,
                            extension,
                            size,
                            safe_iso_timestamp(stat_result.st_mtime),
                            category,
                            title_hint(path, extension),
                        ]
                    )

                extensions[extension].add_file(size, document, source)
                categories[category].add_file(size, document, source)
                bucket = age_bucket((started_epoch - stat_result.st_mtime) / 86400)
                ages[bucket].add_file(size, document, source)
                for prefix_depth in range(1, min(depth, 3) + 1):
                    prefix = "/".join(parts[:prefix_depth])
                    tree[prefix].add_file(size, document, source)

                push_largest(largest_heap, largest_limit, size, relative)
                if size >= duplicate_min_bytes:
                    large_sizes[size].append(relative)

                if total_files % 100000 == 0 or time.monotonic() - last_progress >= 30:
                    print(
                        f"progress files={total_files:,} dirs={total_directories:,} "
                        f"logical_gib={total_bytes / GIB:.2f}",
                        flush=True,
                    )
                    last_progress = time.monotonic()

    write_table(
        output / "tree_depth3.csv",
        ["path", "depth", "files", "directories", "bytes", "gib", "documents", "source_files"],
        (
            [
                path,
                len(Path(path).parts),
                value.files,
                value.directories,
                value.bytes,
                f"{value.bytes / GIB:.6f}",
                value.documents,
                value.source_files,
            ]
            for path, value in sorted(tree.items(), key=lambda item: (-item[1].bytes, item[0].casefold()))
        ),
    )
    write_table(
        output / "extensions.csv",
        ["extension", "files", "bytes", "gib", "documents", "source_files"],
        (
            [key, value.files, value.bytes, f"{value.bytes / GIB:.6f}", value.documents, value.source_files]
            for key, value in sorted(extensions.items(), key=lambda item: (-item[1].bytes, item[0]))
        ),
    )
    write_table(
        output / "categories.csv",
        ["category", "files", "bytes", "gib", "documents", "source_files"],
        (
            [key, value.files, value.bytes, f"{value.bytes / GIB:.6f}", value.documents, value.source_files]
            for key, value in sorted(categories.items(), key=lambda item: (-item[1].bytes, item[0]))
        ),
    )
    write_table(
        output / "age_buckets.csv",
        ["age_bucket", "files", "bytes", "gib", "documents", "source_files"],
        (
            [key, value.files, value.bytes, f"{value.bytes / GIB:.6f}", value.documents, value.source_files]
            for key, value in sorted(ages.items())
        ),
    )
    write_table(
        output / "largest_files.csv",
        ["relative_path", "bytes", "gib", "extension", "category"],
        (
            [relative, size, f"{size / GIB:.6f}", normalized_extension(relative), classify_category(relative, normalized_extension(relative))]
            for size, relative in sorted(largest_heap, reverse=True)
        ),
    )

    duplicate_rows: list[list[object]] = []
    duplicate_group_count = 0
    duplicate_candidate_files = 0
    duplicate_candidate_bytes = 0
    for size, paths in sorted(large_sizes.items(), reverse=True):
        if len(paths) < 2:
            continue
        duplicate_group_count += 1
        duplicate_candidate_files += len(paths)
        duplicate_candidate_bytes += size * len(paths)
        group_id = f"size_{size}"
        for relative in sorted(paths, key=str.casefold):
            duplicate_rows.append([group_id, size, f"{size / GIB:.6f}", relative])
    write_table(
        output / "large_same_size_candidates.csv",
        ["group_id", "bytes_each", "gib_each", "relative_path"],
        duplicate_rows,
    )

    completed_at = utc_now()
    elapsed_seconds = time.time() - started_epoch
    summary = {
        "schema_version": 1,
        "scan_kind": "complete_metadata_inventory_non_atomic",
        "root": str(root),
        "output": str(output),
        "started_at": started_at,
        "completed_at": completed_at,
        "elapsed_seconds": round(elapsed_seconds, 3),
        "scope": {
            "includes_hidden": True,
            "includes_git_internals": True,
            "includes_gitignored": True,
            "follows_reparse_points": False,
            "content_hashes_created": False,
            "small_text_heading_sample_bytes": 65536,
            "note": "This is a planning snapshot. Active files may change while the scan is running.",
        },
        "totals": {
            "files": total_files,
            "directories": total_directories,
            "other_entries": total_other_entries,
            "logical_bytes": total_bytes,
            "logical_gib": round(total_bytes / GIB, 6),
            "documents": document_files,
            "source_files": source_files,
            "reparse_entries_not_followed": reparse_entries,
            "long_paths_240_or_more": long_paths,
            "temporary_name_files": temporary_name_files,
            "scan_errors": error_count,
        },
        "hardlinks": {
            "entries_with_multiple_links": hardlink_entries,
            "logical_bytes_in_linked_entries": hardlink_logical_bytes,
            "unique_bytes_for_linked_file_ids": hardlink_unique_bytes,
            "logical_minus_unique_bytes": hardlink_logical_bytes - hardlink_unique_bytes,
            "note": "Hardlink figures explain logical-versus-physical size differences; they are not deletion authorization.",
        },
        "large_same_size_candidates": {
            "minimum_bytes": duplicate_min_bytes,
            "groups": duplicate_group_count,
            "files": duplicate_candidate_files,
            "logical_bytes": duplicate_candidate_bytes,
            "note": "Same size is only a review candidate, not proof of identical content.",
        },
        "artifacts": [
            "inventory_entries.csv.gz",
            "documents.csv.gz",
            "tree_depth3.csv",
            "extensions.csv",
            "categories.csv",
            "age_buckets.csv",
            "largest_files.csv",
            "large_same_size_candidates.csv",
            "scan_errors.csv",
        ],
    }
    summary_path = output / "summary.json"
    summary_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    artifact_paths = [output / name for name in summary["artifacts"]] + [summary_path]
    write_table(
        output / "artifact_checksums_sha256.csv",
        ["file", "bytes", "sha256"],
        ([path.name, path.stat().st_size, sha256_file(path)] for path in artifact_paths),
    )
    return summary


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Create a complete read-only project metadata inventory")
    parser.add_argument("--root", type=Path, required=True, help="Project root to enumerate")
    parser.add_argument("--output", type=Path, required=True, help="New output directory outside the project")
    parser.add_argument("--largest", type=int, default=1000, help="Number of largest files to retain")
    parser.add_argument(
        "--duplicate-min-mib",
        type=float,
        default=32.0,
        help="Minimum file size for same-size duplicate candidate groups",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if args.largest <= 0:
        raise SystemExit("--largest must be positive")
    if args.duplicate_min_mib < 0:
        raise SystemExit("--duplicate-min-mib must be non-negative")
    summary = scan(
        args.root,
        args.output,
        largest_limit=args.largest,
        duplicate_min_bytes=int(args.duplicate_min_mib * MIB),
    )
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

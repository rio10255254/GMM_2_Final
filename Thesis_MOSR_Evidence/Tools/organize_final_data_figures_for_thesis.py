from __future__ import annotations

import argparse
import csv
import hashlib
import json
import shutil
from dataclasses import asdict, dataclass
from pathlib import Path


V42_FOLDER = "20260710_v42_full_validation"
PSF_FOLDER = "PSF_Experiment_Results_Analysis"
CURRENT_SOURCE_FOLDER = "02_V42_E120_SOURCE_MATERIAL"
PSF_CURRENT_FOLDER = "03_PSF_EXPERIMENT_RESULTS"
FORMAL_TOP_LEVEL = {
    "01_CURRENT_THESIS_RESULTS_V42_CENTER9",
    CURRENT_SOURCE_FOLDER,
    PSF_CURRENT_FOLDER,
}
V42_SEQUENCE_ROOT = Path(
    "reconstructions/reconstruct_progress_epoch_120_in_bmp_20260709_202713"
)
V42_STATIC_ROOT = Path(
    "reconstructions/"
    "reconstruct_progress_epoch_120_in_20260618_100MG_20260709_202713/"
    "100mg_static"
)
RETAINED_SEQUENCES = {"50x_0p5um", "50x_1um", "20x_0p5um", "20x_1um"}
RETAINED_LOGS = {
    "reconstruct_100mg_static.log",
    "reconstruct_50x_0p5um.log",
    "reconstruct_50x_1um.log",
    "reconstruct_20x_0p5um.log",
    "reconstruct_20x_1um.log",
}


@dataclass(frozen=True)
class OriginalFile:
    relative_path: str
    source: str
    destination_kind: str
    destination_relative_path: str
    destination: str
    size_bytes: int
    sha256: str


def sha256_file(path: Path, chunk_size: int = 8 * 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest()


def classify_relative_path(relative: Path) -> tuple[str, Path]:
    parts = relative.parts
    if not parts:
        raise ValueError("empty relative path")
    top = parts[0]
    remainder = Path(*parts[1:]) if len(parts) > 1 else Path()
    if top == PSF_FOLDER:
        return "retained", Path(PSF_CURRENT_FOLDER) / remainder
    if top != V42_FOLDER:
        return "archive", relative

    if len(remainder.parts) == 2 and remainder.parts[0] == "logs":
        if remainder.name in RETAINED_LOGS:
            return "retained", Path(CURRENT_SOURCE_FOLDER) / "logs" / remainder.name
    try:
        sub = remainder.relative_to(V42_STATIC_ROOT)
        return "retained", Path(CURRENT_SOURCE_FOLDER) / "reconstructions" / "100mg_static" / sub
    except ValueError:
        pass
    try:
        sub = remainder.relative_to(V42_SEQUENCE_ROOT)
        if sub.parts and sub.parts[0] in RETAINED_SEQUENCES:
            return (
                "retained",
                Path(CURRENT_SOURCE_FOLDER) / "reconstructions" / sub,
            )
    except ValueError:
        pass
    return "archive", relative


def build_original_inventory(source_root: Path, archive_root: Path) -> list[OriginalFile]:
    source_root = source_root.resolve()
    archive_root = archive_root.resolve()
    records: list[OriginalFile] = []
    for path in sorted(source_root.rglob("*"), key=lambda item: str(item).lower()):
        if not path.is_file():
            continue
        relative = path.relative_to(source_root)
        if relative.parts[0] in FORMAL_TOP_LEVEL or relative.name == "README_CURRENT_THESIS_RESULTS.md":
            continue
        kind, destination_relative = classify_relative_path(relative)
        destination = (
            archive_root / destination_relative
            if kind == "archive"
            else source_root / destination_relative
        )
        records.append(
            OriginalFile(
                relative_path=relative.as_posix(),
                source=str(path.resolve()),
                destination_kind=kind,
                destination_relative_path=destination_relative.as_posix(),
                destination=str(destination.resolve()),
                size_bytes=path.stat().st_size,
                sha256=sha256_file(path),
            )
        )
    return records


def _assert_destination_safe(record: OriginalFile) -> None:
    source = Path(record.source).resolve()
    destination = Path(record.destination).resolve()
    if source == destination:
        raise ValueError(f"source equals destination: {source}")


def copy_and_verify_inventory(records: list[OriginalFile]) -> None:
    for record in records:
        _assert_destination_safe(record)
        source = Path(record.source)
        destination = Path(record.destination)
        if not source.is_file():
            raise FileNotFoundError(source)
        if destination.exists():
            if not destination.is_file():
                raise FileExistsError(destination)
            if destination.stat().st_size != record.size_bytes or sha256_file(destination) != record.sha256:
                raise FileExistsError(f"different destination already exists: {destination}")
            continue
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
        if destination.stat().st_size != record.size_bytes:
            raise IOError(f"size verification failed: {destination}")
        if sha256_file(destination) != record.sha256:
            raise IOError(f"SHA-256 verification failed: {destination}")


def verify_reconciliation(records: list[OriginalFile]) -> None:
    destinations: set[str] = set()
    for record in records:
        destination = Path(record.destination)
        key = str(destination.resolve()).casefold()
        if key in destinations:
            raise ValueError(f"duplicate destination: {destination}")
        destinations.add(key)
        if not destination.is_file():
            raise FileNotFoundError(destination)
        if destination.stat().st_size != record.size_bytes:
            raise IOError(f"size mismatch: {destination}")
        if sha256_file(destination) != record.sha256:
            raise IOError(f"SHA-256 mismatch: {destination}")


def remove_verified_sources(records: list[OriginalFile]) -> None:
    verify_reconciliation(records)
    for record in records:
        source = Path(record.source)
        if not source.exists():
            continue
        if source.stat().st_size != record.size_bytes or sha256_file(source) != record.sha256:
            raise IOError(f"source changed after inventory: {source}")
        source.unlink()


def remove_empty_original_directories(source_root: Path) -> None:
    for path in sorted(
        (item for item in source_root.rglob("*") if item.is_dir()),
        key=lambda item: len(item.parts),
        reverse=True,
    ):
        if path.name in FORMAL_TOP_LEVEL:
            continue
        try:
            path.rmdir()
        except OSError:
            pass


def write_inventory(records: list[OriginalFile], csv_path: Path, json_path: Path) -> None:
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    fields = list(asdict(records[0]).keys()) if records else [
        "relative_path",
        "source",
        "destination_kind",
        "destination_relative_path",
        "destination",
        "size_bytes",
        "sha256",
    ]
    with csv_path.open("w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(asdict(record) for record in records)
    summary = {
        "original_file_count": len(records),
        "original_total_bytes": sum(record.size_bytes for record in records),
        "archive_file_count": sum(record.destination_kind == "archive" for record in records),
        "retained_original_file_count": sum(record.destination_kind == "retained" for record in records),
    }
    json_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--archive-root", type=Path, required=True)
    parser.add_argument("--inventory-csv", type=Path, required=True)
    parser.add_argument("--summary-json", type=Path, required=True)
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    records = build_original_inventory(args.source_root, args.archive_root)
    write_inventory(records, args.inventory_csv, args.summary_json)
    print(json.dumps(json.loads(args.summary_json.read_text(encoding="utf-8")), indent=2))
    if not args.execute:
        print("Dry run only; no files copied or removed.")
        return
    copy_and_verify_inventory(records)
    verify_reconciliation(records)
    remove_verified_sources(records)
    remove_empty_original_directories(args.source_root)
    print("Copy, verification, and source removal completed.")


if __name__ == "__main__":
    main()

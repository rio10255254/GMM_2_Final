"""Check the external-tool comparison bundle without changing its image data."""

from __future__ import annotations

import hashlib
import json
import re
import struct
import sys
from datetime import datetime, timezone
from pathlib import Path


PACKAGE = Path(__file__).resolve().parents[1]
MANIFEST = PACKAGE / "bundle_manifest.json"
INDEX_RE = re.compile(r"(?<!\d)(\d{4})(?=\.bmp$)", re.IGNORECASE)


def resolve_path(value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else PACKAGE / path


def frame_indices(folder: Path) -> tuple[list[Path], list[int], list[str]]:
    files = sorted((p for p in folder.glob("*.bmp") if p.is_file()), key=lambda p: p.name.lower())
    indices: list[int] = []
    bad: list[str] = []
    for path in files:
        match = INDEX_RE.search(path.name)
        if match is None:
            bad.append(path.name)
        else:
            indices.append(int(match.group(1)))
    return files, indices, bad


def bmp_header(path: Path) -> dict[str, int] | None:
    try:
        with path.open("rb") as handle:
            header = handle.read(54)
        if len(header) < 54 or header[:2] != b"BM":
            return None
        width, height, planes, bits = struct.unpack_from("<iiHH", header, 18)
        return {"width": abs(width), "height": abs(height), "planes": planes, "bits": bits}
    except OSError:
        return None


def sha256(path: Path, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(chunk_size), b""):
            digest.update(chunk)
    return digest.hexdigest()


def summarize_images(files: list[Path], expected_indices: list[int]) -> dict[str, object]:
    headers: dict[str, int] | None = None
    header_mismatches: list[str] = []
    sizes = set()
    for path in files:
        current = bmp_header(path)
        sizes.add(path.stat().st_size)
        if current is None:
            header_mismatches.append(path.name)
        elif headers is None:
            headers = current
        elif current != headers:
            header_mismatches.append(path.name)
    sample_hashes = {}
    for path in files[:1] + (files[-1:] if len(files) > 1 else []):
        sample_hashes[path.name] = sha256(path)
    return {
        "count": len(files),
        "indices": sorted(set(expected_indices)),
        "duplicate_indices": sorted({index for index in expected_indices if expected_indices.count(index) > 1}),
        "bmp_header": headers,
        "byte_sizes": sorted(sizes),
        "header_mismatch_files": header_mismatches,
        "sample_sha256": sample_hashes,
    }


def text_inventory(folder: Path) -> dict[str, object]:
    files = sorted(
        (p for p in folder.iterdir() if p.is_file() and p.suffix.lower() in {".txt", ".csv", ".tsv", ".json"}),
        key=lambda p: p.name.lower(),
    ) if folder.is_dir() else []
    nonempty = [p for p in files if p.stat().st_size > 0 and p.name.lower() != "readme.txt"]
    return {
        "files": [{"name": p.name, "bytes": p.stat().st_size} for p in files],
        "nonempty_result_files": [p.name for p in nonempty],
        "state": "present" if nonempty else "pending",
    }


def main() -> int:
    if not MANIFEST.is_file():
        print(f"missing manifest: {MANIFEST}", file=sys.stderr)
        return 2
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    expected_count = int(manifest.get("frame_count", 0))
    expected = list(range(expected_count))
    models = manifest.get("models", [])
    report: dict[str, object] = {
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "package": str(PACKAGE),
        "manifest_version": manifest.get("bundle_version"),
        "expected_frame_count": expected_count,
        "models": [],
        "structural_ok": True,
    }
    for entry in models:
        name = str(entry["model"])
        raw = resolve_path(str(entry["raw"]))
        recon = resolve_path(str(entry["recon"]))
        txt_out = resolve_path(str(entry["txt_out"]))
        raw_files, raw_indices, raw_bad = frame_indices(raw)
        recon_files, recon_indices, recon_bad = frame_indices(recon)
        model_report = {
            "model": name,
            "raw": str(raw),
            "recon": str(recon),
            "txt_out": str(txt_out),
            "raw_images": summarize_images(raw_files, raw_indices),
            "recon_images": summarize_images(recon_files, recon_indices),
            "raw_bad_names": raw_bad,
            "recon_bad_names": recon_bad,
            "text_outputs": text_inventory(txt_out),
        }
        structural_checks = {
            "raw_exists": raw.is_dir(),
            "recon_exists": recon.is_dir(),
            "txt_out_exists": txt_out.is_dir(),
            "raw_count": len(raw_files) == expected_count,
            "recon_count": len(recon_files) == expected_count,
            "raw_indices": sorted(raw_indices) == expected,
            "recon_indices": sorted(recon_indices) == expected,
            "raw_names_parse": not raw_bad,
            "recon_names_parse": not recon_bad,
            "same_bmp_header": (
                model_report["raw_images"]["bmp_header"] is not None
                and model_report["raw_images"]["bmp_header"] == model_report["recon_images"]["bmp_header"]
                and not model_report["raw_images"]["header_mismatch_files"]
                and not model_report["recon_images"]["header_mismatch_files"]
            ),
        }
        model_report["structural_checks"] = structural_checks
        model_report["structural_ok"] = all(structural_checks.values())
        report["models"].append(model_report)
        if not model_report["structural_ok"]:
            report["structural_ok"] = False

    output_dir = PACKAGE / str(manifest.get("analysis", {}).get("output_directory", "analysis"))
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "verification.json"
    output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    for model in report["models"]:
        state = "OK" if model["structural_ok"] else "FAIL"
        txt_state = model["text_outputs"]["state"]
        print(f"{state:4} {model['model']:<10} raw={model['raw_images']['count']:3} recon={model['recon_images']['count']:3} txt={txt_state}")
    print(f"verification: {output_path}")
    return 0 if report["structural_ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

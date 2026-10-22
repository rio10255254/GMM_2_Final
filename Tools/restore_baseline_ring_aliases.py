"""Restore shared baseline inputs without duplicating published image payloads.

Only the reviewed alias map is copied. No training, inference or deletion.
All sources and existing destinations are validated before any output is made.
"""
import argparse
import hashlib
import json
import shutil
from pathlib import Path


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def within(root, relative):
    if not isinstance(relative, str) or "\\" in relative or ":" in relative:
        raise ValueError("Unsafe relative path")
    rel = Path(relative)
    if rel.is_absolute() or not rel.parts or ".." in rel.parts:
        raise ValueError("Unsafe relative path")
    target = root / rel
    if not target.resolve().is_relative_to(root):
        raise ValueError("Path redirects outside the selected root")
    return target


def restore(source_root, destination, manifest):
    source_root = source_root.resolve()
    destination = destination.resolve()
    specification = json.loads(manifest.read_text(encoding="utf-8-sig"))
    if specification.get("schema") != 1 or not specification.get("files"):
        raise ValueError("Unsupported or empty alias map")
    planned = []
    seen = set()
    verified_sources = {}
    for row in specification["files"]:
        src = within(source_root, row["source"])
        dst = within(destination, row["path"])
        key = str(dst).casefold()
        if key in seen:
            raise ValueError("Duplicate output path")
        seen.add(key)
        expected = (row["bytes"], row["sha256"])
        if src not in verified_sources:
            verified_sources[src] = (src.stat().st_size, digest(src))
        if verified_sources[src] != expected:
            raise ValueError("Source content differs: " + row["source"])
        keep = dst.exists()
        if keep and (not dst.is_file() or (dst.stat().st_size, digest(dst)) != expected):
            raise FileExistsError("Existing different file is protected: " + row["path"])
        planned.append((src, dst, expected, keep))
    copied = 0
    for src, dst, expected, keep in planned:
        if keep:
            continue
        dst.parent.mkdir(parents=True, exist_ok=True)
        with src.open("rb") as reader, dst.open("xb") as writer:
            shutil.copyfileobj(reader, writer)
        if (dst.stat().st_size, digest(dst)) != expected:
            raise ValueError("Copied content differs: " + str(dst))
        copied += 1
    return {"status": "PASS", "paths": len(planned), "copied": copied,
            "identical_existing_kept": len(planned)-copied,
            "unique_source_files": len(verified_sources), "overwritten": 0}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--destination", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(restore(args.source_root, args.destination, args.manifest)))


if __name__ == "__main__":
    main()

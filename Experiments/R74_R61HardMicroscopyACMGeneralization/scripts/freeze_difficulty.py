from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "r74_hard_acm_val"
RESULTS = ROOT / "results"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> int:
    if (RESULTS / "inference_manifest.json").exists():
        raise RuntimeError("R61 inference already exists; the Raw-only difficulty freeze cannot be changed")
    summary_path = RESULTS / "tables" / "raw_difficulty_summary.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    if summary.get("uses_r61") or not summary.get("passed"):
        raise RuntimeError("Raw difficulty gate did not pass; do not freeze or reconstruct")
    manifest_path = DATA / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    frozen_files = sorted(
        DATA / kind / item["stage"] / f"{index:04d}.bmp"
        for kind in ("src", "lbl", "mask")
        for item in manifest["families"]
        for index in range(int(manifest["images_per_family"]))
    )
    manifest["difficulty_status"] = "frozen_passed_raw_only_gate"
    manifest["difficulty_summary"] = str(summary_path)
    manifest["difficulty_gate"] = summary
    manifest["frozen_file_count"] = len(frozen_files)
    manifest["frozen_content_sha256"] = hashlib.sha256(
        "".join(sha256(path) for path in frozen_files).encode("ascii")
    ).hexdigest()
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({k: manifest[k] for k in ("difficulty_status", "frozen_file_count", "frozen_content_sha256")}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

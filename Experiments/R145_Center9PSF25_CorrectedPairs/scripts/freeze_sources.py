"""Create the immutable source identity before formal training."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from utils import now, save, sha
from verify_package import FROZEN


def main() -> None:
    dest = ROOT / "config/SOURCE_LOCK.json"
    if dest.exists():
        raise FileExistsError("Source lock already exists")
    files = {rel: sha(ROOT / rel) for rel in FROZEN}
    save(dest, dict(created_utc=now(), purpose="one R145 scratch8192 run using corrected center9 PSF",
                    architecture_source="R141_PSF25_AdaptiveTop4_Standalone",
                    files=files))
    print("SOURCE_LOCKED", len(files), "files", sha(dest))


if __name__ == "__main__":
    main()

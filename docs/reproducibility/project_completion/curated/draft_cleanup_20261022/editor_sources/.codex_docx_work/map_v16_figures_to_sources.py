from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from pathlib import Path


EXTRACTED = Path(r"D:\GMM_2_Final\PSF_Fitting\.codex_docx_work\v16_ch6_figures")
ROOTS = [
    Path(r"D:\GMM_2_Final\Thesis_MOSR_Evidence\Final_Data_Figures"),
    Path(r"D:\GMM_2_Final\Experiments\R63_CausalBoundaryMotionAblation"),
]
OUT = Path(r"D:\GMM_2_Final\PSF_Fitting\.codex_docx_work\v16_figure_source_map.json")


def digest(path: Path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def main():
    targets = sorted(EXTRACTED.glob("fig6-*.png"))
    sizes = {p.stat().st_size for p in targets}
    candidates = defaultdict(list)
    scanned = 0
    for root in ROOTS:
        for path in root.rglob("*.png"):
            scanned += 1
            try:
                size = path.stat().st_size
            except OSError:
                continue
            if size in sizes:
                candidates[size].append(path)
    result = []
    for target in targets:
        sha = digest(target)
        matches = [p for p in candidates[target.stat().st_size] if digest(p) == sha]
        result.append({"figure_file": target.name, "sha256": sha, "matches": [str(p) for p in matches]})
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"targets={len(targets)} scanned_png={scanned} matched={sum(bool(x['matches']) for x in result)}")


if __name__ == "__main__":
    main()

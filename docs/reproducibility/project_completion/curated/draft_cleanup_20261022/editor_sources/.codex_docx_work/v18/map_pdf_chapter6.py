from __future__ import annotations

import json
from pathlib import Path

from pypdf import PdfReader

root = Path(r"D:\GMM_2_Final\PSF_Fitting\.codex_docx_work\v18")
pdf_path = root / "word_render" / "v18.pdf"
reader = PdfReader(str(pdf_path))

matches: dict[str, list[int]] = {}
for page_number, page in enumerate(reader.pages, start=1):
    content = page.extract_text() or ""
    for figure_number in range(1, 55):
        marker = f"圖 6-{figure_number}"
        if marker in content:
            matches.setdefault(marker, []).append(page_number)
    for table_number in range(1, 18):
        marker = f"表 6-{table_number}"
        if marker in content:
            matches.setdefault(marker, []).append(page_number)

output = root / "pdf_chapter6_caption_pages.json"
output.write_text(json.dumps(matches, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"pages={len(reader.pages)} entries={len(matches)} output={output}")

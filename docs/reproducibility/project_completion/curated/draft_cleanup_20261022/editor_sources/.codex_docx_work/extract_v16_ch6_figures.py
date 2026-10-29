from __future__ import annotations

import json
import re
from pathlib import Path

from docx import Document
from docx.oxml.ns import qn
PROJECT_ROOT = Path(__file__).resolve().parents[7]


SOURCE = Path(r"C:\Users\Rio\OneDrive\學業\碩班\論文\可用\論文完整版_20260716_v16_修訂版.docx")
OUT_DIR = Path(str(PROJECT_ROOT / 'PSF_Fitting/.codex_docx_work/v16_ch6_figures'))


def image_parts(paragraph):
    parts = []
    for blip in paragraph._p.xpath(".//a:blip"):
        rid = blip.get(qn("r:embed"))
        if rid and rid in paragraph.part.related_parts:
            parts.append((rid, paragraph.part.related_parts[rid]))
    return parts


def main():
    doc = Document(SOURCE)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    pending = []
    records = []
    in_ch6 = False
    for idx, p in enumerate(doc.paragraphs):
        text = p.text.strip()
        style = p.style.name if p.style else ""
        if style == "Heading 1" and text == "實驗結果與分析":
            in_ch6 = True
        elif in_ch6 and style == "Heading 1" and text == "結論與未來工作":
            break
        if not in_ch6:
            continue
        parts = image_parts(p)
        if parts:
            pending.extend(parts)
        match = re.match(r"^圖\s*6[-－](\d+)\s*(.*)$", text)
        if not match:
            continue
        fig_no = int(match.group(1))
        caption = match.group(2)
        saved = []
        for order, (rid, part) in enumerate(pending, start=1):
            suffix = Path(str(part.partname)).suffix or ".bin"
            name = f"fig6-{fig_no:02d}_{order:02d}{suffix}"
            (OUT_DIR / name).write_bytes(part.blob)
            saved.append({"file": name, "rid": rid, "partname": str(part.partname)})
        records.append({"figure": f"6-{fig_no}", "caption": caption, "paragraph_index": idx, "images": saved})
        pending = []
    (OUT_DIR / "manifest.json").write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"figures={len(records)} images={sum(len(x['images']) for x in records)}")


if __name__ == "__main__":
    main()

from __future__ import annotations

import json
import re
from pathlib import Path

from docx import Document
from docx.table import Table
from docx.text.paragraph import Paragraph
from docx.oxml.ns import qn


SOURCE = Path(r"C:\Users\Rio\OneDrive\學業\碩班\論文\可用\論文完整版_20260716_v16_修訂版.docx")
OUT = Path(r"D:\GMM_2_Final\PSF_Fitting\.codex_docx_work\v16_edit_targets.json")


def iter_blocks(doc: Document):
    body = doc.element.body
    p_i = -1
    t_i = -1
    for child in body.iterchildren():
        if child.tag == qn("w:p"):
            p_i += 1
            yield "paragraph", p_i, Paragraph(child, doc)
        elif child.tag == qn("w:tbl"):
            t_i += 1
            yield "table", t_i, Table(child, doc)


def paragraph_images(p: Paragraph):
    out = []
    for blip in p._p.xpath(".//a:blip"):
        rid = blip.get(qn("r:embed"))
        if not rid:
            continue
        part = p.part.related_parts.get(rid)
        out.append({"rid": rid, "partname": str(part.partname) if part else None})
    return out


def main():
    doc = Document(SOURCE)
    blocks = list(iter_blocks(doc))
    in_ch6 = False
    rows = []
    prev_texts = []
    for kind, idx, obj in blocks:
        if kind == "paragraph":
            text = obj.text.strip()
            style = obj.style.name if obj.style else ""
            if style == "Heading 1" and text == "實驗結果與分析":
                in_ch6 = True
            if in_ch6 and style == "Heading 1" and text == "結論與未來工作":
                break
            if not in_ch6:
                continue
            images = paragraph_images(obj)
            if text or images:
                rows.append(
                    {
                        "kind": kind,
                        "index": idx,
                        "style": style,
                        "text": text,
                        "images": images,
                        "preceding_text": prev_texts[-3:],
                    }
                )
            if text:
                prev_texts.append(text)
        else:
            if not in_ch6:
                continue
            data = []
            for row in obj.rows:
                data.append([cell.text.strip() for cell in row.cells])
            rows.append(
                {
                    "kind": kind,
                    "index": idx,
                    "rows": data,
                    "preceding_text": prev_texts[-3:],
                }
            )

    english_targets = []
    for row in rows:
        if row["kind"] == "paragraph":
            text = row.get("text", "")
            if re.search(r"(?:^|\s)(?:Figure|Table|Raw|Wiener|MOSR|EDSR|NAFNet|Median|Runtime|Edge|Input|Model|Parameter|Throughput|improvement)\b", text, re.I):
                english_targets.append(row)
        else:
            flat = " | ".join(x for rr in row["rows"] for x in rr)
            if re.search(r"\b(?:Model|Parameter|Runtime|Median|P95|Throughput|improvement|Method|EDSR|NAFNet)\b", flat, re.I):
                english_targets.append(row)

    payload = {"source": str(SOURCE), "chapter6_blocks": rows, "english_targets": english_targets}
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    for row in rows:
        if row["kind"] == "paragraph":
            if row.get("images") or "Caption" in row.get("style", "") or re.match(r"^(圖|表)\s*6[-－]", row.get("text", "")):
                print(json.dumps(row, ensure_ascii=False))
        else:
            print(json.dumps(row, ensure_ascii=False))


if __name__ == "__main__":
    main()

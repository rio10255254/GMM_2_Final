from __future__ import annotations

import collections
import difflib
import json
import re
import sys
import zipfile
from pathlib import Path

from lxml import etree
from pypdf import PdfReader


W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
M = "http://schemas.openxmlformats.org/officeDocument/2006/math"
NS = {"w": W, "m": M}


def qn(ns: str, name: str) -> str:
    return f"{{{ns}}}{name}"


def load_docx(path: Path) -> dict:
    with zipfile.ZipFile(path) as zf:
        bad = zf.testzip()
        names = set(zf.namelist())
        doc = etree.fromstring(zf.read("word/document.xml"))
        styles = etree.fromstring(zf.read("word/styles.xml"))
        style_names: dict[str, str] = {}
        for style in styles.xpath(".//w:style", namespaces=NS):
            sid = style.get(qn(W, "styleId"), "")
            name_nodes = style.xpath("./w:name/@w:val", namespaces=NS)
            style_names[sid] = name_nodes[0] if name_nodes else sid

        paragraphs = []
        for i, p in enumerate(doc.xpath(".//w:body//w:p", namespaces=NS)):
            chunks = p.xpath(".//w:t/text() | .//m:t/text()", namespaces=NS)
            text = "".join(chunks).strip()
            style_ids = p.xpath("./w:pPr/w:pStyle/@w:val", namespaces=NS)
            style_id = style_ids[0] if style_ids else ""
            paragraphs.append(
                {
                    "index": i,
                    "text": text,
                    "style_id": style_id,
                    "style": style_names.get(style_id, style_id),
                }
            )

        return {
            "path": str(path),
            "zip_ok": bad is None,
            "parts": len(names),
            "paragraphs": paragraphs,
            "tables": len(doc.xpath(".//w:body//w:tbl", namespaces=NS)),
            "drawings": len(doc.xpath(".//w:drawing", namespaces=NS)),
            "tracked_insertions": len(doc.xpath(".//w:ins", namespaces=NS)),
            "tracked_deletions": len(doc.xpath(".//w:del", namespaces=NS)),
            "comments_part": "word/comments.xml" in names,
            "footnotes_part": "word/footnotes.xml" in names,
            "endnotes_part": "word/endnotes.xml" in names,
        }


def clean_paragraphs(doc: dict) -> list[str]:
    return [p["text"] for p in doc["paragraphs"] if p["text"]]


def diff_docs(old: dict, new: dict, max_items: int = 300) -> list[dict]:
    a = clean_paragraphs(old)
    b = clean_paragraphs(new)
    sm = difflib.SequenceMatcher(a=a, b=b, autojunk=False)
    changes = []
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            continue
        changes.append(
            {
                "tag": tag,
                "old_range": [i1, i2],
                "new_range": [j1, j2],
                "old": a[i1:i2],
                "new": b[j1:j2],
            }
        )
        if len(changes) >= max_items:
            break
    return changes


def pdf_pages(path: Path) -> list[str]:
    reader = PdfReader(path)
    return [(page.extract_text() or "").replace("\x00", "") for page in reader.pages]


def find_pages(pages: list[str], patterns: list[str]) -> dict[str, list[int]]:
    out: dict[str, list[int]] = {}
    for pattern in patterns:
        rx = re.compile(pattern, re.I)
        out[pattern] = [i + 1 for i, text in enumerate(pages) if rx.search(text)]
    return out


def normalize_for_scan(text: str) -> str:
    return text.replace("\u00a0", " ").replace("µ", "u")


def citation_audit(paragraphs: list[str]) -> dict:
    all_text = "\n".join(paragraphs)
    # The phrase also appears in the table of contents.  The final occurrence
    # is the actual bibliography heading.
    ref_pos = all_text.rfind("參考文獻")
    body = all_text[:ref_pos] if ref_pos >= 0 else all_text
    refs = all_text[ref_pos:] if ref_pos >= 0 else ""
    cited = set()
    clusters = []
    for match in re.finditer(r"\[([0-9,，\-–—\s]+)\]", body):
        nums = [int(x) for x in re.findall(r"\d+", match.group(1))]
        if not nums:
            continue
        cited.update(nums)
        if len(nums) >= 5:
            clusters.append({"text": match.group(0), "count": len(nums), "at": match.start()})
    listed = set(int(x) for x in re.findall(r"(?:^|\n)\s*\[(\d+)\]", refs))
    return {
        "cited_count": len(cited),
        "listed_count": len(listed),
        "cited_minmax": [min(cited), max(cited)] if cited else None,
        "listed_minmax": [min(listed), max(listed)] if listed else None,
        "missing_from_references": sorted(cited - listed),
        "unused_references": sorted(listed - cited),
        "clusters_ge_5": clusters,
    }


def term_hits(paragraphs: list[str], terms: list[str]) -> dict[str, list[dict]]:
    out: dict[str, list[dict]] = {}
    for term in terms:
        rx = re.compile(term, re.I)
        hits = []
        for p in paragraphs:
            if rx.search(p["text"]):
                hits.append({"index": p["index"], "style": p["style"], "text": p["text"]})
        out[term] = hits
    return out


def heading_inventory(paragraphs: list[dict]) -> list[dict]:
    rx = re.compile(r"^(?:第\s*[一二三四五六七八九十0-9]+\s*章|\d+(?:\.\d+){0,4}\s+|摘要$|Abstract$|參考文獻$)")
    return [p for p in paragraphs if p["text"] and ("heading" in p["style"].lower() or rx.match(p["text"]))]


def main() -> None:
    if len(sys.argv) != 6:
        raise SystemExit("usage: script v14.docx v15.docx v16.docx v16.pdf outdir")
    v14_path, v15_path, v16_path, pdf_path, out_dir = map(Path, sys.argv[1:])
    out_dir.mkdir(parents=True, exist_ok=True)

    docs = {"v14": load_docx(v14_path), "v15": load_docx(v15_path), "v16": load_docx(v16_path)}
    pages = pdf_pages(pdf_path)
    paragraphs = docs["v16"]["paragraphs"]
    para_texts = [p["text"] for p in paragraphs if p["text"]]

    patterns = [
        r"第\s*1\s*章|第1章",
        r"1\.3\s*研究貢獻",
        r"第\s*4\s*章|第4章",
        r"4\.6\s*量測導向",
        r"第\s*6\s*章|第6章",
        r"6\.2\.7",
        r"6\.2\.8",
        r"第\s*7\s*章|第7章",
        r"9\.54",
        r"6\.74",
        r"123\.7",
        r"76\.1",
        r"467\.7",
        r"508\.5",
        r"224\.2",
        r"400\.2",
        r"94\.06",
        r"7\.86",
        r"PI\s*閉迴路",
        r"Raw-defined|Raw 定義|Raw定義",
        r"固定.*30",
        r"限制",
        r"未來工作",
        r"Ground Truth|ground truth",
        r"真值",
        r"Noll",
        r"OSA/ANSI",
    ]
    terms = [
        r"V\d+",
        r"R\d+",
        r"20\d{6}",
        r"基礎\s*U[- ]?Net|Base\s*U[- ]?Net",
        r"Ground Truth|ground truth",
        r"真值",
        r"訓練資料.*驗證|驗證.*訓練資料",
        r"資料洩漏|data leakage",
        r"Noll",
        r"OSA/ANSI",
        r"單一.*樣品|單一.*系統",
        r"不具.*泛化|無法.*泛化|未.*泛化",
        r"限制|侷限",
        r"僅能|只能|不足以|不宜",
        r"較佳工作點|較積極|視覺上夠強|允許保留可見",
        r"commanded displacement|Nominal command|PI feedback truth|PI回授真值",
        r"Raw-motion-ranked|held-out calibration",
    ]

    report = {
        "documents": {
            k: {x: y for x, y in v.items() if x != "paragraphs"}
            | {"nonempty_paragraphs": len(clean_paragraphs(v))}
            for k, v in docs.items()
        },
        "pdf_pages": len(pages),
        "headings": heading_inventory(paragraphs),
        "citation_audit": citation_audit(para_texts),
        "term_hits": term_hits(paragraphs, terms),
        "page_hits": find_pages([normalize_for_scan(x) for x in pages], patterns),
        "diff_v15_v16": diff_docs(docs["v15"], docs["v16"]),
        "diff_v14_v16": diff_docs(docs["v14"], docs["v16"]),
    }
    (out_dir / "v16_review.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    (out_dir / "v16_pages_text.json").write_text(
        json.dumps({str(i + 1): t for i, t in enumerate(pages)}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(json.dumps({
        "documents": report["documents"],
        "pdf_pages": report["pdf_pages"],
        "citation_audit": report["citation_audit"],
        "page_hits": report["page_hits"],
        "term_hit_counts": {k: len(v) for k, v in report["term_hits"].items()},
        "diff_v15_v16_blocks": len(report["diff_v15_v16"]),
        "diff_v14_v16_blocks": len(report["diff_v14_v16"]),
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

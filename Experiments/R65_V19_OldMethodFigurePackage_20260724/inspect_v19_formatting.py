from __future__ import annotations

import json
from pathlib import Path

from docx import Document
from docx.oxml.ns import qn


DOCX = Path(
    r"C:\Users\Rio\OneDrive\學業\碩班\論文\可用"
    r"\論文完整版_20260716_v19_第六章更新版.docx"
)
OUT = Path(__file__).with_name("v19_formatting_inspection.json")


def rgb(value):
    return str(value) if value is not None else None


def font_attrs(element):
    rpr = element.rPr if hasattr(element, "rPr") else None
    rfonts = rpr.rFonts if rpr is not None else None
    return {
        "name": element.font.name,
        "size_pt": element.font.size.pt if element.font.size else None,
        "bold": element.font.bold,
        "italic": element.font.italic,
        "color": rgb(element.font.color.rgb),
        "eastAsia": rfonts.get(qn("w:eastAsia")) if rfonts is not None else None,
        "ascii": rfonts.get(qn("w:ascii")) if rfonts is not None else None,
        "hAnsi": rfonts.get(qn("w:hAnsi")) if rfonts is not None else None,
        "hint": rfonts.get(qn("w:hint")) if rfonts is not None else None,
    }


def paragraph_info(paragraph):
    pf = paragraph.paragraph_format
    return {
        "text": paragraph.text,
        "style_name": paragraph.style.name,
        "style_id": paragraph.style.style_id,
        "alignment": str(paragraph.alignment),
        "paragraph": {
            "left_indent_pt": pf.left_indent.pt if pf.left_indent else None,
            "first_line_indent_pt": (
                pf.first_line_indent.pt if pf.first_line_indent else None
            ),
            "space_before_pt": pf.space_before.pt if pf.space_before else None,
            "space_after_pt": pf.space_after.pt if pf.space_after else None,
            "line_spacing": str(pf.line_spacing),
            "keep_with_next": pf.keep_with_next,
            "page_break_before": pf.page_break_before,
        },
        "style_font": font_attrs(paragraph.style),
        "runs": [
            {
                "text": run.text,
                **font_attrs(run),
            }
            for run in paragraph.runs
        ],
        "pPr": (
            paragraph._p.pPr.xml if paragraph._p.pPr is not None else None
        ),
    }


document = Document(DOCX)
prefixes = [
    "6.2.3 影像重建與邊緣響應",
    "6.2.4 SEM 對照之 CD 修正與閾值穩健性",
    "6.2.4.1 50 倍 pillar",
    "由圖 6-25",
    "圖 6-24 ",
    "表 6-8 ",
    "6.2.5 位移改善實驗",
    "6.2.5.1 四組序列之逐次位移",
    "本節只比較Raw",
    "圖 6-37 ",
    "表 6-9 ",
    "6.2.6 配對式消融實驗",
    "6.2.7 多模型與跨形貌比較",
    "6.2.8 綜合討論",
    "7.1 研究結論",
]

report = {}
for prefix in prefixes:
    matches = [
        paragraph_info(paragraph)
        for paragraph in document.paragraphs
        if paragraph.text.strip().startswith(prefix)
        and not paragraph.style.name.startswith("toc")
    ]
    report[prefix] = matches[:2]

style_names = [
    "Normal",
    "Heading 1",
    "Heading 2",
    "Heading 3",
    "Heading 4",
    "Figure Caption",
    "Table Caption",
]
report["styles"] = {
    name: {
        "style_id": document.styles[name].style_id,
        "font": font_attrs(document.styles[name]),
        "pPr": (
            document.styles[name]._element.pPr.xml
            if document.styles[name]._element.pPr is not None
            else None
        ),
        "rPr": (
            document.styles[name]._element.rPr.xml
            if document.styles[name]._element.rPr is not None
            else None
        ),
    }
    for name in style_names
}

OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
print(OUT)

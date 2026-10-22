from __future__ import annotations

import sys
from pathlib import Path

from docx import Document
from docx.enum.style import WD_STYLE_TYPE
from docx.oxml import OxmlElement
from docx.oxml.ns import qn


def clear(paragraph) -> None:
    for child in list(paragraph._p):
        if child.tag != qn("w:pPr"):
            paragraph._p.remove(child)


def add_field(paragraph, instruction: str) -> None:
    clear(paragraph)
    for kind, text in (
        ("begin", None),
        ("instruction", instruction),
        ("separate", None),
        ("result", "更新欄位後產生圖目錄"),
        ("end", None),
    ):
        run = OxmlElement("w:r")
        if kind in {"begin", "separate", "end"}:
            field = OxmlElement("w:fldChar")
            field.set(qn("w:fldCharType"), kind)
            if kind == "begin":
                field.set(qn("w:dirty"), "true")
            run.append(field)
        elif kind == "instruction":
            node = OxmlElement("w:instrText")
            node.set(qn("xml:space"), "preserve")
            node.text = text
            run.append(node)
        else:
            node = OxmlElement("w:t")
            node.text = text
            run.append(node)
        paragraph._p.append(run)


def main() -> None:
    path = Path(sys.argv[1])
    doc = Document(path)

    if "Figure Caption" in [style.name for style in doc.styles]:
        figure_style = doc.styles["Figure Caption"]
    else:
        figure_style = doc.styles.add_style("Figure Caption", WD_STYLE_TYPE.PARAGRAPH)
        figure_style.base_style = doc.styles["Caption"]

    caption_style_id = doc.styles["Caption"].style_id
    for paragraph in doc.element.body.xpath(".//w:p"):
        text = "".join(paragraph.xpath(".//w:t/text()") or []).strip()
        style_nodes = paragraph.xpath("./w:pPr/w:pStyle")
        if text.startswith("圖 ") and style_nodes and style_nodes[0].get(qn("w:val")) == caption_style_id:
            style_nodes[0].set(qn("w:val"), figure_style.style_id)

    title = next(p for p in doc.paragraphs if p.text.strip() == "圖目錄")
    body = title._p.getparent()
    cursor = title._p.getnext()
    while cursor is not None:
        next_cursor = cursor.getnext()
        if cursor.tag == qn("w:p") and cursor.find(qn("w:pPr") + "/" + qn("w:sectPr")) is not None:
            break
        body.remove(cursor)
        cursor = next_cursor

    field_element = OxmlElement("w:p")
    title._p.addnext(field_element)
    from docx.text.paragraph import Paragraph

    field_paragraph = Paragraph(field_element, title._parent)
    add_field(field_paragraph, ' TOC \\h \\z \\t "Figure Caption,1" ')
    doc.save(path)
    print(path)


if __name__ == "__main__":
    main()

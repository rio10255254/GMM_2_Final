from __future__ import annotations

import sys
from pathlib import Path

from docx import Document
from docx.table import Table
from docx.text.paragraph import Paragraph
from docx.oxml.ns import qn


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    doc = Document(Path(sys.argv[1]))
    p_counter = 0
    t_counter = 0
    for child in doc.element.body.iterchildren():
        if child.tag == qn("w:p"):
            i = p_counter
            p_counter += 1
            para = Paragraph(child, doc)
            text = para.text.strip().replace("\t", " ")
            drawings = len(child.xpath(".//w:drawing")) + len(child.xpath(".//w:pict"))
            style = para.style.name if para.style is not None else ""
            print(f"P\t{i}\t{style}\tdraw={drawings}\t{text}")
        elif child.tag == qn("w:tbl"):
            i = t_counter
            t_counter += 1
            table = Table(child, doc)
            preview = ""
            if table is not None and table.rows:
                preview = " | ".join(cell.text.strip().replace("\n", " ") for cell in table.rows[0].cells)
            print(f"T\t{i}\t\t\t{preview}")
        elif child.tag == qn("w:sectPr"):
            print("S\t-1\t\t\t<section properties>")


if __name__ == "__main__":
    main()

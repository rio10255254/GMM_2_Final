from __future__ import annotations

import argparse
import re
import zipfile
from pathlib import Path

from lxml import etree


NS = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
W = "{%s}" % NS["w"]


def text_of(element: etree._Element) -> str:
    return "".join(element.xpath(".//w:t/text()", namespaces=NS)).strip()


def style_of(paragraph: etree._Element) -> str:
    values = paragraph.xpath("./w:pPr/w:pStyle/@w:val", namespaces=NS)
    return values[0] if values else ""


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("docx", type=Path)
    args = parser.parse_args()

    terms = [
        "較佳工作點",
        "超解析不是",
        "不增加輸出",
        "光學解析度",
        "研究問題一",
        "研究問題二",
        "研究問題三",
        "抗混疊上採樣能否",
        "輸入參考式殘差輸出",
        "不作為研究因素",
        "不列入消融",
        "不作為獨立",
        "較積極",
        "允許保留",
        "視覺上夠強",
        "NSR",
        "固定PSF",
        "held-out calibration frame",
        "held-out",
        "120",
        "118",
        "9.54",
        "9.30",
        "Nominal command",
        "Raw-motion-ranked",
        "架構差異",
        "區分量測導向",
        "資料僅含一張",
        "較穩健的結論不是",
        "不將抗混疊",
        "補充驗證",
        "補充實驗",
        "補充分析",
        "不能單獨證明因果",
        "不延伸為所有",
        "取捨",
        "86.14",
        "15.09",
        "P90",
        "第90百分位",
        "第 90 百分位",
        "研究範圍與量測可信度",
        "可部署",
    ]

    with zipfile.ZipFile(args.docx) as archive:
        root = etree.fromstring(archive.read("word/document.xml"))

    body = root.find("w:body", namespaces=NS)
    if body is None:
        raise RuntimeError("No document body")

    for index, block in enumerate(body):
        if block.tag == W + "p":
            text = text_of(block)
            hits = [term for term in terms if term.lower() in text.lower()]
            if hits:
                print(f"P{index:04d} style={style_of(block)!r} hits={hits}")
                print(text)
                print()
        elif block.tag == W + "tbl":
            rows = []
            for row in block.xpath("./w:tr", namespaces=NS):
                cells = [text_of(cell) for cell in row.xpath("./w:tc", namespaces=NS)]
                row_text = " | ".join(cells)
                hits = [term for term in terms if term.lower() in row_text.lower()]
                if hits:
                    rows.append((hits, row_text))
            if rows:
                print(f"T{index:04d}")
                for hits, row_text in rows:
                    print(f"hits={hits}: {row_text}")
                print()


if __name__ == "__main__":
    main()

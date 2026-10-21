from pathlib import Path
import hashlib

from docx import Document
from docx.oxml.ns import qn


DOCX = Path(
    r"C:\Users\Rio\OneDrive\學業\碩班\論文\可用\論文完整版_20260716_v11.docx"
)


def formula_text_fingerprint(doc: Document) -> tuple[int, str]:
    formulas = []
    for node in doc._element.xpath(".//m:oMath"):
        formulas.append("".join((part.text or "") for part in node.iter(qn("m:t"))))
    digest = hashlib.sha256("\u241e".join(formulas).encode("utf-8")).hexdigest()
    return len(formulas), digest


def is_empty_body_paragraph(node) -> bool:
    if node.tag != qn("w:p"):
        return False
    has_text = any((part.text or "").strip() for part in node.xpath(".//w:t"))
    has_math = bool(node.xpath(".//m:oMath"))
    has_drawing = bool(node.xpath(".//w:drawing | .//w:pict | .//w:object"))
    return not has_text and not has_math and not has_drawing


def main() -> None:
    doc = Document(DOCX)
    before = formula_text_fingerprint(doc)
    body = doc._element.body
    removed = 0

    index = 0
    while index < len(body) - 1:
        node = body[index]
        is_formula_table = node.tag == qn("w:tbl") and bool(node.xpath(".//m:oMath"))
        if is_formula_table and is_empty_body_paragraph(body[index + 1]):
            body.remove(body[index + 1])
            removed += 1
            continue
        index += 1

    doc.save(DOCX)
    check = Document(DOCX)
    after = formula_text_fingerprint(check)
    if after != before:
        raise RuntimeError(f"Formula content changed: before={before}, after={after}")

    remaining = 0
    body = check._element.body
    for index, node in enumerate(body[:-1]):
        if (
            node.tag == qn("w:tbl")
            and node.xpath(".//m:oMath")
            and is_empty_body_paragraph(body[index + 1])
        ):
            remaining += 1

    if remaining:
        raise RuntimeError(f"{remaining} empty paragraphs remain after formula tables")

    print(
        {
            "removed_empty_paragraphs": removed,
            "remaining_empty_paragraphs": remaining,
            "formula_fingerprint": after,
        }
    )


if __name__ == "__main__":
    main()

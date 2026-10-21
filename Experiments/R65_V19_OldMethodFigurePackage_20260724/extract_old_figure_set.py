from __future__ import annotations

import json
from pathlib import Path

from docx import Document
from docx.oxml.ns import qn


THESIS = Path(r"C:\Users\Rio\OneDrive\學業\碩班\論文\可用")
OUT = Path(__file__).with_name("old_figure_set")
OUT.mkdir(exist_ok=True)

sources = {
    "old": THESIS / "論文完整版_20260716_v14.docx",
    "current": THESIS / "論文完整版_20260716_v19_第六章更新版.docx",
}
figure_numbers = [24, 25, 26, 28, 29, 30]


def extract(document: Document, number: int):
    caption = next(
        paragraph
        for paragraph in document.paragraphs
        if paragraph.style
        and paragraph.style.name == "Figure Caption"
        and paragraph.text.strip().startswith(f"圖 6-{number} ")
    )
    current = caption._p.getprevious()
    while current is not None:
        blips = current.xpath(".//*[local-name()='blip']")
        if blips:
            rid = blips[0].get(qn("r:embed"))
            if rid:
                return caption.text, document.part.related_parts[rid]
        current = current.getprevious()
    raise RuntimeError(f"Image not found for figure 6-{number}")


report = []
for label, source in sources.items():
    document = Document(source)
    for number in figure_numbers:
        caption, part = extract(document, number)
        extension = {
            "image/png": ".png",
            "image/jpeg": ".jpg",
        }.get(part.content_type, Path(part.partname).suffix)
        output = OUT / f"{label}_figure_6_{number}{extension}"
        output.write_bytes(part.blob)
        report.append(
            {
                "source": str(source),
                "label": label,
                "figure": number,
                "caption": caption,
                "output": str(output),
                "bytes": len(part.blob),
            }
        )

(OUT / "report.json").write_text(
    json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
)
print(json.dumps(report, ensure_ascii=False, indent=2))

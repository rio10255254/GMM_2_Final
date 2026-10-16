from __future__ import annotations

import json
from pathlib import Path

from docx import Document
from docx.oxml.ns import qn


THESIS = Path(r"C:\Users\Rio\OneDrive\學業\碩班\論文\可用")
OUT = Path(__file__).with_name("figure_6_24_versions")
OUT.mkdir(exist_ok=True)

versions = [
    "論文完整版_20260716_v11.docx",
    "論文完整版_20260716_v12.docx",
    "論文完整版_20260716_v13.docx",
    "論文完整版_20260716_v14.docx",
    "論文完整版_20260716_v15.docx",
    "論文完整版_20260716_v16_修訂版.docx",
    "論文完整版_20260716_v17_修訂版.docx",
    "論文完整版_20260716_v18_圖表整理版.docx",
    "論文完整版_20260716_v19_第六章更新版.docx",
]

report = []
for filename in versions:
    path = THESIS / filename
    document = Document(path)
    caption = next(
        (
            paragraph
            for paragraph in document.paragraphs
            if paragraph.style
            and paragraph.style.name == "Figure Caption"
            and paragraph.text.strip().startswith("圖 6-24 ")
        ),
        None,
    )
    if caption is None:
        report.append({"file": filename, "status": "caption_not_found"})
        continue

    current = caption._p.getprevious()
    image_part = None
    rid = None
    while current is not None:
        blips = current.xpath(".//*[local-name()='blip']")
        if blips:
            rid = blips[0].get(qn("r:embed"))
            if rid:
                image_part = document.part.related_parts[rid]
                break
        current = current.getprevious()

    if image_part is None:
        report.append(
            {
                "file": filename,
                "status": "image_not_found",
                "caption": caption.text,
            }
        )
        continue

    extension = {
        "image/png": ".png",
        "image/jpeg": ".jpg",
        "image/tiff": ".tif",
        "image/bmp": ".bmp",
    }.get(image_part.content_type, Path(image_part.partname).suffix)
    version = filename.split("_v")[-1].split(".docx")[0].replace("_修訂版", "").replace(
        "_圖表整理版", ""
    ).replace("_第六章更新版", "")
    output = OUT / f"{version}_figure_6_24{extension}"
    output.write_bytes(image_part.blob)
    report.append(
        {
            "file": filename,
            "status": "ok",
            "caption": caption.text,
            "content_type": image_part.content_type,
            "bytes": len(image_part.blob),
            "output": str(output),
        }
    )

(OUT / "report.json").write_text(
    json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
)
print(json.dumps(report, ensure_ascii=False, indent=2))

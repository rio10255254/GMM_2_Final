from __future__ import annotations

import copy
import hashlib
import os
import re
import tempfile
import zipfile
from pathlib import Path, PurePosixPath

from lxml import etree


BASE_DOCX = Path(
    r"C:\Users\Rio\OneDrive\學業\碩班\論文\可用\論文完整版_20260716_v5.docx"
)
CHAPTER_DOCX = Path(
    r"C:\Users\Rio\OneDrive\學業\碩班\論文\章節"
    r"\第六章 實驗結果與分析_含6.2_MOSR與反卷積CD上下界分析.docx"
)
OUTPUT_DOCX = Path(
    r"C:\Users\Rio\OneDrive\學業\碩班\論文\可用\論文完整版_20260716_v6.docx"
)

W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
R_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
WP_NS = "http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing"
PIC_NS = "http://schemas.openxmlformats.org/drawingml/2006/picture"
REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
CT_NS = "http://schemas.openxmlformats.org/package/2006/content-types"

NS = {"w": W_NS, "r": R_NS, "wp": WP_NS, "pic": PIC_NS}
W = f"{{{W_NS}}}"
R = f"{{{R_NS}}}"


def xml(data: bytes) -> etree._Element:
    return etree.fromstring(data)


def xml_bytes(root: etree._Element) -> bytes:
    return etree.tostring(
        root, xml_declaration=True, encoding="UTF-8", standalone="yes"
    )


def paragraph_text(element: etree._Element) -> str:
    return "".join(element.xpath(".//w:t/text()", namespaces=NS)).strip()


def is_paragraph(element: etree._Element) -> bool:
    return element.tag == W + "p"


def has_drawing(element: etree._Element) -> bool:
    return bool(element.xpath(".//w:drawing | .//w:pict", namespaces=NS))


def has_page_break(element: etree._Element) -> bool:
    return bool(
        element.xpath(
            "./w:pPr/w:pageBreakBefore | .//w:br[@w:type='page']", namespaces=NS
        )
    )


def get_style_id(element: etree._Element) -> str | None:
    values = element.xpath("./w:pPr/w:pStyle/@w:val", namespaces=NS)
    return values[0] if values else None


def set_paragraph_style(element: etree._Element, style_id: str) -> None:
    ppr = element.find(W + "pPr")
    if ppr is None:
        ppr = etree.Element(W + "pPr")
        element.insert(0, ppr)
    pstyle = ppr.find(W + "pStyle")
    if pstyle is None:
        pstyle = etree.Element(W + "pStyle")
        ppr.insert(0, pstyle)
    pstyle.set(W + "val", style_id)


def set_table_style(element: etree._Element, style_id: str) -> None:
    tblpr = element.find(W + "tblPr")
    if tblpr is None:
        tblpr = etree.Element(W + "tblPr")
        element.insert(0, tblpr)
    tblstyle = tblpr.find(W + "tblStyle")
    if tblstyle is None:
        tblstyle = etree.Element(W + "tblStyle")
        tblpr.insert(0, tblstyle)
    tblstyle.set(W + "val", style_id)


def prefix_text(element: etree._Element, prefix: str) -> None:
    text_nodes = element.xpath(".//w:t", namespaces=NS)
    if not text_nodes:
        raise RuntimeError(f"Cannot prefix text in paragraph: {paragraph_text(element)!r}")
    first = text_nodes[0]
    current = first.text or ""
    if not current.startswith(prefix):
        first.text = prefix + current


def replace_text(element: etree._Element, old: str, new: str) -> bool:
    for node in element.xpath(".//w:t", namespaces=NS):
        current = node.text or ""
        if old in current:
            node.text = current.replace(old, new)
            return True
    return False


def normalize_heading_spacing(element: etree._Element) -> None:
    text_nodes = element.xpath(".//w:t", namespaces=NS)
    if not text_nodes:
        return
    full_text = "".join(node.text or "" for node in text_nodes)
    match = re.match(r"^6(?:\.\d+){1,3}", full_text)
    if match is None or match.end() >= len(full_text) or full_text[match.end()] == " ":
        return
    remaining = match.end()
    for node in text_nodes:
        current = node.text or ""
        if remaining <= len(current):
            node.text = current[:remaining] + " " + current[remaining:]
            return
        remaining -= len(current)
    raise RuntimeError(f"Cannot normalize heading spacing: {full_text!r}")


def heading_level(text: str) -> int | None:
    match = re.match(r"^6((?:\.\d+){1,3})(?:\s|\S)", text)
    if not match:
        return None
    return match.group(1).count(".")


def find_body_child(
    children: list[etree._Element], *, text: str, style_id: str | None = None
) -> int:
    matches = []
    for index, child in enumerate(children):
        if not is_paragraph(child) or paragraph_text(child) != text:
            continue
        if style_id is not None and get_style_id(child) != style_id:
            continue
        matches.append(index)
    if len(matches) != 1:
        raise RuntimeError(
            f"Expected one body paragraph {text!r} with style {style_id!r}; found {matches}"
        )
    return matches[0]


def relationship_map(root: etree._Element) -> dict[str, etree._Element]:
    return {rel.get("Id"): rel for rel in root if rel.get("Id")}


def relationship_ids_used(elements: list[etree._Element]) -> set[str]:
    used: set[str] = set()
    for element in elements:
        for attribute in (R + "embed", R + "link", R + "id"):
            used.update(value for value in element.xpath(f".//@*[name()='{attribute}']") if value)
        # lxml name() does not expose Clark notation consistently, so scan attributes too.
        for node in element.iter():
            for key, value in node.attrib.items():
                if key in {R + "embed", R + "link", R + "id"}:
                    used.add(value)
    return used


def replace_relationship_ids(
    elements: list[etree._Element], mapping: dict[str, str]
) -> None:
    for element in elements:
        for node in element.iter():
            for key, value in list(node.attrib.items()):
                if key in {R + "embed", R + "link", R + "id"} and value in mapping:
                    node.set(key, mapping[value])


def next_rid(existing: set[str], counter: list[int]) -> str:
    while True:
        candidate = f"rId{counter[0]}"
        counter[0] += 1
        if candidate not in existing:
            existing.add(candidate)
            return candidate


def relationship_target_to_part(target: str) -> str:
    return str(PurePosixPath("word") / PurePosixPath(target))


def ensure_png_content_type(content_types: etree._Element) -> None:
    defaults = {
        node.get("Extension", "").lower()
        for node in content_types.findall(f"{{{CT_NS}}}Default")
    }
    if "png" not in defaults:
        node = etree.Element(f"{{{CT_NS}}}Default")
        node.set("Extension", "png")
        node.set("ContentType", "image/png")
        content_types.append(node)


def update_fields_setting(settings: etree._Element) -> None:
    update = settings.find(W + "updateFields")
    if update is None:
        update = etree.Element(W + "updateFields")
        settings.append(update)
    update.set(W + "val", "true")


def mark_fields_dirty(document: etree._Element) -> None:
    for field_char in document.xpath(".//w:fldChar[@w:fldCharType='begin']", namespaces=NS):
        field_char.set(W + "dirty", "true")


def referenced_media_parts(package_entries: dict[str, bytes]) -> set[str]:
    targets: set[str] = set()
    for name, data in package_entries.items():
        if not name.endswith(".rels"):
            continue
        try:
            root = xml(data)
        except etree.XMLSyntaxError:
            continue
        rel_base = PurePosixPath(name).parent.parent
        source_part_dir = rel_base
        for rel in root:
            if rel.get("TargetMode") == "External":
                continue
            target = rel.get("Target")
            if not target or "media/" not in target:
                continue
            resolved = source_part_dir / PurePosixPath(target)
            targets.add(str(resolved))
    return targets


def renumber_drawing_ids(
    base_root: etree._Element, imported_elements: list[etree._Element]
) -> None:
    existing = [
        int(value)
        for value in base_root.xpath(".//wp:docPr/@id", namespaces=NS)
        if str(value).isdigit()
    ]
    next_id = max(existing, default=0) + 1
    for element in imported_elements:
        for node in element.xpath(".//wp:docPr", namespaces=NS):
            node.set("id", str(next_id))
            next_id += 1
        for node in element.xpath(".//pic:cNvPr", namespaces=NS):
            node.set("id", str(next_id))
            next_id += 1


def format_imported_chapter(elements: list[etree._Element]) -> dict[str, int]:
    style_by_level = {1: "21", 2: "31", 3: "4"}
    for element in elements:
        if not is_paragraph(element):
            continue
        replace_text(element, "6-X", "6-4 與圖 6-5")
        text = paragraph_text(element)
        level = heading_level(text)
        if level is not None:
            set_paragraph_style(element, style_by_level[level])
            normalize_heading_spacing(element)

    figure_count = 0
    for index, element in enumerate(elements):
        if not is_paragraph(element) or not has_drawing(element):
            continue
        caption_index = index + 1
        if caption_index >= len(elements) or not is_paragraph(elements[caption_index]):
            raise RuntimeError(f"Missing figure caption after imported child {index}")
        caption = elements[caption_index]
        if not paragraph_text(caption):
            raise RuntimeError(f"Empty figure caption after imported child {index}")
        figure_count += 1
        prefix_text(caption, f"圖 6-{figure_count} ")
        set_paragraph_style(caption, "FigureCaption")

    table_count = 0
    for index, element in enumerate(elements):
        if element.tag != W + "tbl":
            continue
        if index == 0 or not is_paragraph(elements[index - 1]):
            raise RuntimeError(f"Missing table caption before imported child {index}")
        caption = elements[index - 1]
        if not paragraph_text(caption):
            raise RuntimeError(f"Empty table caption before imported child {index}")
        table_count += 1
        prefix_text(caption, f"表 6-{table_count} ")
        set_paragraph_style(caption, "TableCaption")
        # In the standalone chapter, style id 'af' means Table Grid. In the
        # full thesis, Table Grid is style id 'afa'.
        set_table_style(element, "afa")

    heading_count = sum(
        1
        for element in elements
        if is_paragraph(element) and heading_level(paragraph_text(element)) is not None
    )
    return {
        "figures": figure_count,
        "tables": table_count,
        "headings": heading_count,
    }


def build() -> dict[str, int | str]:
    for path in (BASE_DOCX, CHAPTER_DOCX):
        if not path.is_file():
            raise FileNotFoundError(path)

    with zipfile.ZipFile(BASE_DOCX, "r") as base_zip, zipfile.ZipFile(
        CHAPTER_DOCX, "r"
    ) as chapter_zip:
        entries = {info.filename: base_zip.read(info.filename) for info in base_zip.infolist()}
        base_root = xml(entries["word/document.xml"])
        base_body = base_root.find(W + "body")
        if base_body is None:
            raise RuntimeError("Base document has no w:body")

        chapter_root = xml(chapter_zip.read("word/document.xml"))
        chapter_body = chapter_root.find(W + "body")
        if chapter_body is None:
            raise RuntimeError("Chapter document has no w:body")

        base_children = list(base_body)
        chapter_title_index = find_body_child(
            base_children, text="實驗結果與分析", style_id="1"
        )
        chapter7_title_index = find_body_child(
            base_children, text="未來展望", style_id="1"
        )
        if chapter7_title_index <= chapter_title_index:
            raise RuntimeError("Chapter 7 title precedes Chapter 6 title")

        # Preserve the blank page-break paragraph immediately before Chapter 7.
        removal_end = chapter7_title_index
        previous = base_children[chapter7_title_index - 1]
        if (
            is_paragraph(previous)
            and not paragraph_text(previous)
            and has_page_break(previous)
        ):
            removal_end -= 1

        old_chapter_elements = base_children[chapter_title_index + 1 : removal_end]
        for element in old_chapter_elements:
            base_body.remove(element)

        source_children = list(chapter_body)
        if source_children and source_children[-1].tag == W + "sectPr":
            source_children = source_children[:-1]
        if not source_children or paragraph_text(source_children[0]) != "第六章":
            raise RuntimeError("Standalone chapter does not start with 第六章")
        imported = [copy.deepcopy(element) for element in source_children[1:]]
        format_stats = format_imported_chapter(imported)

        chapter_rels = xml(chapter_zip.read("word/_rels/document.xml.rels"))
        base_rels = xml(entries["word/_rels/document.xml.rels"])
        source_rel_by_id = relationship_map(chapter_rels)
        existing_rids = set(relationship_map(base_rels))
        numeric_ids = [
            int(match.group(1))
            for rid in existing_rids
            if (match := re.fullmatch(r"rId(\d+)", rid))
        ]
        rid_counter = [max(numeric_ids, default=0) + 1]

        media_names = {
            PurePosixPath(name).name
            for name in entries
            if name.startswith("word/media/")
        }
        imported_parts: dict[str, bytes] = {}
        rid_mapping: dict[str, str] = {}
        for old_rid in sorted(relationship_ids_used(imported)):
            source_rel = source_rel_by_id.get(old_rid)
            if source_rel is None:
                raise RuntimeError(f"Imported content references missing {old_rid}")
            new_rid = next_rid(existing_rids, rid_counter)
            rid_mapping[old_rid] = new_rid

            new_rel = copy.deepcopy(source_rel)
            new_rel.set("Id", new_rid)
            if source_rel.get("TargetMode") != "External":
                target = source_rel.get("Target")
                if not target:
                    raise RuntimeError(f"Relationship {old_rid} has no target")
                source_part = relationship_target_to_part(target)
                if source_part not in chapter_zip.namelist():
                    raise RuntimeError(f"Missing related part {source_part}")
                suffix = PurePosixPath(target).suffix.lower() or ".bin"
                digest = hashlib.sha256(chapter_zip.read(source_part)).hexdigest()[:12]
                candidate = f"chapter6v6_{digest}{suffix}"
                serial = 1
                while candidate in media_names:
                    candidate = f"chapter6v6_{digest}_{serial}{suffix}"
                    serial += 1
                media_names.add(candidate)
                destination = f"word/media/{candidate}"
                imported_parts[destination] = chapter_zip.read(source_part)
                new_rel.set("Target", f"media/{candidate}")
            base_rels.append(new_rel)

        replace_relationship_ids(imported, rid_mapping)
        renumber_drawing_ids(base_root, imported)

        insertion_index = chapter_title_index + 1
        for offset, element in enumerate(imported):
            base_body.insert(insertion_index + offset, element)

        mark_fields_dirty(base_root)
        entries["word/document.xml"] = xml_bytes(base_root)
        entries["word/_rels/document.xml.rels"] = xml_bytes(base_rels)

        settings = xml(entries["word/settings.xml"])
        update_fields_setting(settings)
        entries["word/settings.xml"] = xml_bytes(settings)

        content_types = xml(entries["[Content_Types].xml"])
        ensure_png_content_type(content_types)
        entries["[Content_Types].xml"] = xml_bytes(content_types)
        entries.update(imported_parts)

        # Remove image relationships and media files no longer referenced after
        # deleting the previous Chapter 6. Other document relationships remain.
        final_root = xml(entries["word/document.xml"])
        final_used_rids = relationship_ids_used([final_root])
        final_rels = xml(entries["word/_rels/document.xml.rels"])
        removed_targets: set[str] = set()
        for rel in list(final_rels):
            if (
                rel.get("Type", "").endswith("/image")
                and rel.get("Id") not in final_used_rids
                and rel.get("TargetMode") != "External"
            ):
                target = rel.get("Target")
                if target:
                    removed_targets.add(relationship_target_to_part(target))
                final_rels.remove(rel)
        entries["word/_rels/document.xml.rels"] = xml_bytes(final_rels)

        for part in removed_targets:
            entries.pop(part, None)

        # Retain media used by headers, footers, or any remaining relationship.
        all_media_references = referenced_media_parts(entries)
        for name in list(entries):
            if name.startswith("word/media/") and name not in all_media_references:
                entries.pop(name)

    OUTPUT_DOCX.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary_name = tempfile.mkstemp(
        prefix=OUTPUT_DOCX.stem + "_", suffix=".tmp", dir=OUTPUT_DOCX.parent
    )
    os.close(fd)
    temporary = Path(temporary_name)
    try:
        with zipfile.ZipFile(temporary, "w", zipfile.ZIP_DEFLATED) as output_zip:
            for name, data in entries.items():
                output_zip.writestr(name, data)
        with zipfile.ZipFile(temporary, "r") as check_zip:
            corrupt = check_zip.testzip()
            if corrupt:
                raise RuntimeError(f"Corrupt ZIP member: {corrupt}")
            check_root = xml(check_zip.read("word/document.xml"))
            check_body = check_root.find(W + "body")
            if check_body is None:
                raise RuntimeError("Output document has no body")
            output_children = list(check_body)
            start = find_body_child(output_children, text="實驗結果與分析", style_id="1")
            end = find_body_child(output_children, text="未來展望", style_id="1")
            chapter_slice = output_children[start + 1 : end]
            figure_captions = [
                paragraph_text(element)
                for element in chapter_slice
                if is_paragraph(element) and get_style_id(element) == "FigureCaption"
            ]
            table_captions = [
                paragraph_text(element)
                for element in chapter_slice
                if is_paragraph(element) and get_style_id(element) == "TableCaption"
            ]
            drawings = sum(
                len(element.xpath(".//w:drawing | .//w:pict", namespaces=NS))
                for element in chapter_slice
            )
            tables = sum(element.tag == W + "tbl" for element in chapter_slice)
            expected_drawings = format_stats["figures"] + 2
            if len(figure_captions) != format_stats["figures"] or drawings != expected_drawings:
                raise RuntimeError(
                    f"Figure validation failed: captions={len(figure_captions)}, drawings={drawings}"
                )
            if len(table_captions) != format_stats["tables"] or tables != format_stats["tables"]:
                raise RuntimeError(
                    f"Table validation failed: captions={len(table_captions)}, tables={tables}"
                )
            if not figure_captions[-1].endswith("20× 固定 PSF 相對校正位置距離之位移誤差"):
                raise RuntimeError(f"Unexpected final figure caption: {figure_captions[-1]!r}")
            if not any("CD 上下界" in text for text in table_captions):
                raise RuntimeError("Updated CD lower-upper bound table is missing")
            chapter_headings = [
                paragraph_text(element)
                for element in chapter_slice
                if is_paragraph(element)
                and get_style_id(element) in {"21", "31", "4"}
                and paragraph_text(element).startswith("6.")
            ]
            if len(chapter_headings) != format_stats["headings"]:
                raise RuntimeError(
                    f"Heading validation failed: {len(chapter_headings)} != {format_stats['headings']}"
                )
            malformed_headings = [
                text for text in chapter_headings if re.search(r"\d\s+\.\d", text)
            ]
            if malformed_headings:
                raise RuntimeError(f"Malformed heading numbers: {malformed_headings}")
            if chapter_headings[0] != "6.1 點擴散函數校正":
                raise RuntimeError(f"Unexpected first Chapter 6 heading: {chapter_headings[0]!r}")
            if chapter_headings[-1] != "6.2.6 綜合討論與研究限制":
                raise RuntimeError(f"Unexpected final Chapter 6 heading: {chapter_headings[-1]!r}")
            if any("6-X" in paragraph_text(element) for element in chapter_slice):
                raise RuntimeError("Unresolved Chapter 6 figure placeholder remains")
            rel_root = xml(check_zip.read("word/_rels/document.xml.rels"))
            defined_rids = set(relationship_map(rel_root))
            unresolved = relationship_ids_used([check_root]) - defined_rids
            if unresolved:
                raise RuntimeError(f"Unresolved document relationships: {sorted(unresolved)}")
        os.replace(temporary, OUTPUT_DOCX)
    finally:
        if temporary.exists():
            temporary.unlink()

    return {
        "output": str(OUTPUT_DOCX),
        "figures": format_stats["figures"],
        "drawings": format_stats["figures"] + 2,
        "tables": format_stats["tables"],
        "headings": format_stats["headings"],
        "old_chapter_elements_removed": len(old_chapter_elements),
        "new_chapter_elements_inserted": len(imported),
    }


if __name__ == "__main__":
    result = build()
    for key, value in result.items():
        print(f"{key}: {value}")

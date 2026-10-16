"""Format-only cleanup for the v20 thesis document.

The script deliberately edits only paragraph/run formatting in
word/document.xml.  All text, equations, figures, tables, relationships and
other package parts are kept byte-for-byte unchanged.  The current Chapter 6
layout is used as the visual standard:

* figure paragraphs: centred, 1.5 line spacing, kept with their caption;
* figure captions: centred, 12 pt, 1 pt before and 5 pt after, kept together;
* table captions: left aligned, 12 pt, 1 pt before and 5 pt after, kept with
  the following table and kept together.

No document content is generated or rewritten.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from copy import deepcopy
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

from lxml import etree


W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
NS = {"w": W_NS}
QN = lambda local: f"{{{W_NS}}}{local}"


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def style_ids(styles_xml: bytes) -> dict[str, str]:
    root = etree.fromstring(styles_xml)
    result: dict[str, str] = {}
    for style in root.xpath("w:style[@w:type='paragraph']", namespaces=NS):
        name = style.find("w:name", namespaces=NS)
        if name is not None and name.get(QN("val")):
            result[name.get(QN("val"))] = style.get(QN("styleId"))
    return result


def get_pstyle(p: etree._Element) -> str | None:
    ppr = p.find("w:pPr", namespaces=NS)
    if ppr is None:
        return None
    pstyle = ppr.find("w:pStyle", namespaces=NS)
    return pstyle.get(QN("val")) if pstyle is not None else None


def get_or_create(parent: etree._Element, tag: str) -> etree._Element:
    node = parent.find(tag, namespaces=NS)
    if node is None:
        node = etree.Element(QN(tag.split("}")[-1]))
        parent.insert(0, node)
    return node


def remove_children(parent: etree._Element, tag: str) -> None:
    for child in list(parent.findall(tag, namespaces=NS)):
        parent.remove(child)


def set_spacing(ppr: etree._Element, before: int | None, after: int | None) -> None:
    spacing = ppr.find("w:spacing", namespaces=NS)
    if spacing is None:
        spacing = etree.Element(QN("spacing"))
        ppr.append(spacing)
    for attr in ("before", "after", "line", "lineRule"):
        spacing.attrib.pop(QN(attr), None)
    if before is not None:
        spacing.set(QN("before"), str(before))
    if after is not None:
        spacing.set(QN("after"), str(after))
    spacing.set(QN("line"), "360")
    spacing.set(QN("lineRule"), "auto")


def set_alignment(ppr: etree._Element, value: str | None) -> None:
    remove_children(ppr, "w:jc")
    if value:
        jc = etree.Element(QN("jc"))
        jc.set(QN("val"), value)
        ppr.append(jc)


def set_bool(ppr: etree._Element, tag: str, enabled: bool) -> None:
    remove_children(ppr, f"w:{tag}")
    if enabled:
        ppr.append(etree.Element(QN(tag)))


def normalise_caption_runs(p: etree._Element) -> int:
    changed = 0
    for run in p.xpath(".//w:r", namespaces=NS):
        # Caption text is deliberately kept in its existing runs.  Only the
        # size is normalised; any intentional italic/bold/colour is retained.
        rpr = run.find("w:rPr", namespaces=NS)
        if rpr is None:
            rpr = etree.Element(QN("rPr"))
            run.insert(0, rpr)
            changed += 1
        for tag in ("sz", "szCs"):
            node = rpr.find(f"w:{tag}", namespaces=NS)
            if node is None:
                node = etree.Element(QN(tag))
                rpr.append(node)
                changed += 1
            if node.get(QN("val")) != "24":
                node.set(QN("val"), "24")
                changed += 1
    return changed


def format_document(document_xml: bytes, styles_xml: bytes) -> tuple[bytes, dict]:
    root = etree.fromstring(document_xml)
    ids = style_ids(styles_xml)
    figure_style = ids.get("Figure Caption", "FigureCaption")
    table_style = ids.get("Table Caption", "TableCaption")

    counts = {
        "figure_caption_paragraphs": 0,
        "table_caption_paragraphs": 0,
        "figure_image_paragraphs": 0,
        "caption_run_properties_updated": 0,
    }

    for p in root.xpath(".//w:p", namespaces=NS):
        style = get_pstyle(p)
        ppr = p.find("w:pPr", namespaces=NS)
        has_drawing = bool(p.xpath(".//w:drawing", namespaces=NS))

        if has_drawing:
            if ppr is None:
                ppr = etree.Element(QN("pPr"))
                p.insert(0, ppr)
            set_alignment(ppr, "center")
            set_spacing(ppr, None, None)
            set_bool(ppr, "keepNext", True)
            set_bool(ppr, "keepLines", True)
            counts["figure_image_paragraphs"] += 1

        if style == figure_style:
            if ppr is None:
                ppr = etree.Element(QN("pPr"))
                p.insert(0, ppr)
            set_alignment(ppr, "center")
            set_spacing(ppr, 20, 100)
            set_bool(ppr, "keepNext", False)
            set_bool(ppr, "keepLines", True)
            counts["figure_caption_paragraphs"] += 1
            counts["caption_run_properties_updated"] += normalise_caption_runs(p)

        if style == table_style:
            if ppr is None:
                ppr = etree.Element(QN("pPr"))
                p.insert(0, ppr)
            # No explicit jc means the document's normal left alignment.
            set_alignment(ppr, None)
            set_spacing(ppr, 20, 100)
            set_bool(ppr, "keepNext", True)
            set_bool(ppr, "keepLines", True)
            counts["table_caption_paragraphs"] += 1
            counts["caption_run_properties_updated"] += normalise_caption_runs(p)

    out = etree.tostring(root, encoding="UTF-8", xml_declaration=True, standalone=True)
    return out, counts


def text_nodes(xml: bytes) -> list[tuple[str, str]]:
    root = etree.fromstring(xml)
    result = []
    for node in root.xpath(".//w:t | .//w:instrText | .//w:delText", namespaces=NS):
        result.append((local_name(node.tag), node.text or ""))
    return result


def strip_formatting(xml: bytes) -> bytes:
    root = etree.fromstring(xml)
    for node in list(root.iter()):
        if local_name(node.tag) in {"pPr", "rPr"}:
            parent = node.getparent()
            if parent is not None:
                parent.remove(node)
                continue
        for attr in list(node.attrib):
            if local_name(attr).startswith("rsid"):
                del node.attrib[attr]
    return etree.tostring(root, method="c14n")


def copy_zip_with_document(src: Path, dst: Path, document_xml: bytes) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    with ZipFile(src, "r") as zin, ZipFile(dst, "w", compression=ZIP_DEFLATED) as zout:
        for info in zin.infolist():
            data = document_xml if info.filename == "word/document.xml" else zin.read(info.filename)
            new_info = ZipInfo(info.filename, date_time=info.date_time)
            new_info.compress_type = info.compress_type
            new_info.comment = info.comment
            new_info.extra = info.extra
            new_info.create_system = info.create_system
            new_info.create_version = info.create_version
            new_info.extract_version = info.extract_version
            new_info.flag_bits = info.flag_bits
            new_info.internal_attr = info.internal_attr
            new_info.external_attr = info.external_attr
            zout.writestr(new_info, data)


def package_audit(before: Path, after: Path, before_doc: bytes, after_doc: bytes) -> dict:
    with ZipFile(before) as za, ZipFile(after) as zb:
        names_a = za.namelist()
        names_b = zb.namelist()
        non_doc_equal = []
        non_doc_changed = []
        for name in names_a:
            if name == "word/document.xml":
                continue
            if name not in names_b:
                non_doc_changed.append(name + " (missing)")
                continue
            if za.read(name) == zb.read(name):
                non_doc_equal.append(name)
            else:
                non_doc_changed.append(name)
        for name in names_b:
            if name not in names_a:
                non_doc_changed.append(name + " (new)")

        before_media = {n: sha256(za.read(n)) for n in names_a if n.startswith("word/media/")}
        after_media = {n: sha256(zb.read(n)) for n in names_b if n.startswith("word/media/")}

    return {
        "text_nodes_identical": text_nodes(before_doc) == text_nodes(after_doc),
        "format_stripped_structure_identical": strip_formatting(before_doc) == strip_formatting(after_doc),
        "package_entries_identical_except_document_xml": not non_doc_changed,
        "media_identical": before_media == after_media,
        "before_text_node_count": len(text_nodes(before_doc)),
        "after_text_node_count": len(text_nodes(after_doc)),
        "before_document_sha256": sha256(before_doc),
        "after_document_sha256": sha256(after_doc),
        "non_document_changed_entries": non_doc_changed,
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("input", type=Path)
    ap.add_argument("output", type=Path)
    ap.add_argument("--report", type=Path, required=True)
    args = ap.parse_args()

    with ZipFile(args.input) as z:
        original_doc = z.read("word/document.xml")
        styles = z.read("word/styles.xml")
    formatted_doc, counts = format_document(original_doc, styles)
    copy_zip_with_document(args.input, args.output, formatted_doc)
    audit = package_audit(args.input, args.output, original_doc, formatted_doc)
    if not all(audit[k] for k in ("text_nodes_identical", "format_stripped_structure_identical", "package_entries_identical_except_document_xml", "media_identical")):
        raise SystemExit(json.dumps({"counts": counts, "audit": audit}, ensure_ascii=False, indent=2))
    report = {"input": str(args.input), "output": str(args.output), "counts": counts, "audit": audit}
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

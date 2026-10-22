from __future__ import annotations

import argparse
import copy
import re
import zipfile
from pathlib import Path

from lxml import etree


NS = {
    "w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
    "pr": "http://schemas.openxmlformats.org/package/2006/relationships",
}
W = "{%s}" % NS["w"]
XML_SPACE = "{http://www.w3.org/XML/1998/namespace}space"


def visible_text(element: etree._Element) -> str:
    return "".join(element.xpath(".//w:t/text()", namespaces=NS))


def paragraph_style(paragraph: etree._Element) -> str:
    values = paragraph.xpath("./w:pPr/w:pStyle/@w:val", namespaces=NS)
    return values[0] if values else ""


def set_full_text(paragraph: etree._Element, new_text: str) -> None:
    text_nodes = paragraph.xpath(".//w:t", namespaces=NS)
    if not text_nodes:
        run = etree.Element(W + "r")
        text_node = etree.SubElement(run, W + "t")
        paragraph.append(run)
        text_nodes = [text_node]
    text_nodes[0].text = new_text
    if new_text.startswith(" ") or new_text.endswith(" "):
        text_nodes[0].set(XML_SPACE, "preserve")
    for node in text_nodes[1:]:
        node.text = ""


def replace_visible_substring(paragraph: etree._Element, old: str, new: str) -> bool:
    nodes = paragraph.xpath(".//w:t", namespaces=NS)
    if not nodes:
        return False
    chunks = [node.text or "" for node in nodes]
    full = "".join(chunks)
    start = full.find(old)
    if start < 0:
        return False
    end = start + len(old)

    offsets: list[tuple[int, int]] = []
    cursor = 0
    for chunk in chunks:
        offsets.append((cursor, cursor + len(chunk)))
        cursor += len(chunk)

    start_index = next(i for i, (_, b) in enumerate(offsets) if b > start or (start == len(full) and b == start))
    end_index = next(i for i, (a, b) in enumerate(offsets) if a < end <= b)
    start_local = start - offsets[start_index][0]
    end_local = end - offsets[end_index][0]

    if start_index == end_index:
        node_text = chunks[start_index]
        nodes[start_index].text = node_text[:start_local] + new + node_text[end_local:]
    else:
        nodes[start_index].text = chunks[start_index][:start_local] + new
        for i in range(start_index + 1, end_index):
            nodes[i].text = ""
        nodes[end_index].text = chunks[end_index][end_local:]
    return True


def remove_direct_section(body: etree._Element, start_prefix: str, end_prefix: str) -> int:
    children = list(body)
    start_index = None
    end_index = None
    for index, child in enumerate(children):
        if child.tag != W + "p":
            continue
        text = visible_text(child).strip()
        if start_index is None and text.startswith(start_prefix):
            start_index = index
            continue
        if start_index is not None and text.startswith(end_prefix):
            end_index = index
            break
    if start_index is None or end_index is None:
        raise RuntimeError(f"Section not found: {start_prefix!r} -> {end_prefix!r}")
    removed = children[start_index:end_index]
    for child in removed:
        body.remove(child)
    return len(removed)


def replace_paragraph_by_prefix(root: etree._Element, prefix: str, new_text: str) -> int:
    matches = []
    for paragraph in root.xpath(".//w:p", namespaces=NS):
        text = visible_text(paragraph).strip()
        if text.startswith(prefix):
            matches.append(paragraph)
    if len(matches) != 1:
        raise RuntimeError(f"Expected one paragraph for prefix {prefix!r}, found {len(matches)}")
    set_full_text(matches[0], new_text)
    return 1


def remove_paragraphs_containing(root: etree._Element, marker: str) -> int:
    removed = 0
    for paragraph in list(root.xpath(".//w:p", namespaces=NS)):
        if marker not in visible_text(paragraph):
            continue
        parent = paragraph.getparent()
        if parent is not None:
            parent.remove(paragraph)
            removed += 1
    return removed


def remove_table_rows_containing(root: etree._Element, marker: str) -> int:
    removed = 0
    for row in list(root.xpath(".//w:tr", namespaces=NS)):
        if marker in visible_text(row):
            parent = row.getparent()
            if parent is not None:
                parent.remove(row)
                removed += 1
    return removed


def all_paragraphs(root: etree._Element):
    return root.xpath(".//w:p", namespaces=NS)


def normalized_text(text: str) -> str:
    return re.sub(r"\s+", "", text)


def set_pageref_result(root: etree._Element, marker: str, page_number: int) -> int:
    marker_norm = normalized_text(marker)
    matches = []
    for paragraph in all_paragraphs(root):
        instructions = "".join(paragraph.xpath(".//w:instrText/text()", namespaces=NS))
        if "PAGEREF" not in instructions:
            continue
        if marker_norm in normalized_text(visible_text(paragraph)):
            matches.append(paragraph)
    if len(matches) != 1:
        raise RuntimeError(
            f"Expected one PAGEREF entry for {marker!r}, found {len(matches)}"
        )
    numeric_nodes = [
        node
        for node in matches[0].xpath(".//w:t", namespaces=NS)
        if (node.text or "").strip().isdigit()
    ]
    if not numeric_nodes:
        raise RuntimeError(f"No page-number result node found for {marker!r}")
    numeric_nodes[-1].text = str(page_number)
    return 1


def remove_page_break_before_by_prefix(root: etree._Element, prefix: str) -> int:
    matches = [
        paragraph
        for paragraph in all_paragraphs(root)
        if visible_text(paragraph).strip().startswith(prefix)
        and "PAGEREF" not in "".join(
            paragraph.xpath(".//w:instrText/text()", namespaces=NS)
        )
    ]
    if len(matches) != 1:
        raise RuntimeError(
            f"Expected one body paragraph for page-break removal {prefix!r}, found {len(matches)}"
        )
    breaks = matches[0].xpath("./w:pPr/w:pageBreakBefore", namespaces=NS)
    for item in breaks:
        item.getparent().remove(item)
    return len(breaks)


def remove_empty_paragraph_before_heading(body: etree._Element, heading_text: str) -> int:
    children = list(body)
    heading_index = next(
        (
            index
            for index, child in enumerate(children)
            if child.tag == W + "p"
            and visible_text(child).strip() == heading_text
        ),
        None,
    )
    if heading_index is None or heading_index == 0:
        raise RuntimeError(f"Heading not found for empty-paragraph cleanup: {heading_text!r}")
    previous = children[heading_index - 1]
    if previous.tag != W + "p" or visible_text(previous).strip():
        raise RuntimeError(
            f"Expected an empty paragraph before heading {heading_text!r}"
        )
    body.remove(previous)
    return 1


def patch_document_xml(xml_bytes: bytes) -> tuple[bytes, dict[str, int]]:
    parser = etree.XMLParser(remove_blank_text=False, resolve_entities=False)
    root = etree.fromstring(xml_bytes, parser)
    body = root.find("w:body", namespaces=NS)
    if body is None:
        raise RuntimeError("word/document.xml has no w:body")

    stats: dict[str, int] = {}
    stats["removed_method_section_blocks"] = remove_direct_section(
        body, "5.4.6 基礎 U-Net 對照配置", "5.4.7 現代重建模型與跨形貌評估配置"
    )
    stats["removed_result_section_blocks"] = remove_direct_section(
        body,
        "6.2.6.6 基礎 U-Net 對照：視覺銳化與量測可用性的差異",
        "6.2.6.7 消融與基礎模型對照之綜合判讀",
    )

    # Remove the now-obsolete TOC and list-of-figures entries that were outside
    # the deleted body sections.
    stats["removed_method_toc_entries"] = remove_paragraphs_containing(
        root, "5.4.6 基礎 U-Net 對照配置"
    )
    stats["removed_base_figure_list_entries"] = remove_paragraphs_containing(
        root, "Fixed-scale visual comparison of Raw, Base U-Net, and MOSR"
    )

    replacements = {
        "結果顯示，Wiener能產生較窄的部分邊緣": (
            "結果顯示，Wiener能產生較窄的部分邊緣，卻具有最大的跨門檻CD誤差；MOSR並未以所有條件下的最大銳利度為目標，而是在CD門檻穩健性與多顆pillar位移一致性之間取得較佳工作點。相較Raw，MOSR使CD中位絕對誤差降低20.16%，並使九顆pillar不一致量降低63.29%；相較Wiener，兩項指標分別降低38.48%與18.31%。消融實驗顯示，以一般上採樣取代抗混疊上採樣後，四組序列合併的九顆pillar不一致量增加14.31%；移除輸入參考式殘差輸出後，20倍CD中位絕對誤差增加73.97%，兩種倍率的振鈴亦明顯增加。上述結果說明，最小邊緣過渡寬度不能單獨代表量測品質；有效的顯微影像重建必須同時維持邊界、尺寸與平移關係。補充跨形貌驗證以20倍via作為低取樣測試，MOSR將CD區間中點相對SEM的平均絕對誤差由Raw的644.0 nm降至224.2 nm，並將35%至65%門檻區間寬度由432.6 nm降至129.0 nm；此結果亦優於同參數量級的EDSR與NAFNet。水平與垂直線條的10%至90%邊緣寬度分別降低14.2%與18.0%，表觀週期變化維持在2 nm內。"
        ),
        "Wiener produced narrower edges in some conditions": (
            "Wiener produced narrower edges in some conditions but also the largest cross-threshold CD error. MOSR did not target maximum sharpness under every condition; instead, it provided a better operating point between CD threshold robustness and multi-pillar displacement consistency. Relative to Raw, MOSR reduced the median absolute CD error by 20.16% and the nine-pillar inconsistency by 63.29%; relative to Wiener, the reductions were 38.48% and 18.31%. In ablation experiments, replacing anti-aliased upsampling with conventional upsampling increased the pooled nine-pillar disagreement by 14.31%. Removing the input-referenced residual output increased the 20× median absolute CD error by 73.97% and substantially increased ringing at both magnifications. These results show that minimum edge-transition width alone does not represent metrology quality; effective microscopy reconstruction must preserve boundaries, dimensions, and translation relationships together. In a supplementary low-sampling 20× via test, MOSR reduced the CD-interval midpoint mean absolute error from 644.0 nm in Raw to 224.2 nm and narrowed the 35%-65% threshold interval from 432.6 to 129.0 nm, outperforming parameter-comparable EDSR and NAFNet in this test. For horizontal and vertical line patterns, the 10%-90% edge width decreased by 14.2% and 18.0%, respectively, while the apparent pitch changed by less than 2 nm."
        ),
        "貢獻三：建立由量測失效形式導出的共同訓練目標與配對驗證": (
            "貢獻三：建立由量測失效形式導出的共同訓練目標與配對驗證。影像內容、邊界幾何、運動一致性與輸出保守性四組目標，分別限制外觀失真、輪廓偏移、影格依賴與不必要改動[62,67,68,69,70]。Raw、Wiener、MOSR及各消融條件共用影像名單、pillar身分、物體空間尺度、中心、門檻與統計規則，讓邊緣、CD與位移結果可在同一座標下比較[80,81,82,83,84,85]。"
        ),
        "為補充一般U-Net之外的學習式比較": (
            "為建立學習式重建方法的受控比較，本研究加入EDSR-x1與NAFNet兩種代表性重建架構[44,94]。兩者均由頭訓練，不使用外部預訓練權重；訓練影像、分組切分、256×256裁切、有效批次、最佳權重選取方式與輸入前處理保持一致，並以L1與SSIM組成的一般重建目標訓練。MOSR則保留本研究提出的量測導向模型與目標，使比較能檢查一般重建架構是否足以得到相同的量測結果。"
        ),
        "EDSR-x1採24個殘差模組與96個特徵通道": (
            "EDSR-x1採24個殘差模組與96個特徵通道，共4,070,785個參數；NAFNet採20個基礎通道與四層編碼器—解碼器，共4,182,141個參數。兩者與MOSR皆約四百萬個參數，避免由模型容量差異直接決定結果。EDSR-x1與NAFNet的最佳權重皆出現在第15回合。"
        ),
        "模型部分說明實際資料數量": (
            "模型部分說明實際資料數量、分組切分、邊界軟標籤、訓練與消融設定，並加入參數量相近的EDSR-x1與NAFNet作為學習式重建對照。主要比較與補充比較皆固定影像、結構身分與量測規則，使各方法可在相同尺度下對照。"
        ),
        "本節評估MOSR在HS-100MG樣品上的重建與量測表現": (
            "本節評估MOSR在HS-100MG樣品上的重建與量測表現。第6.2.3至第6.2.5節使用同一批Raw影像、相同九顆pillar、相同120個位移步與共同量測規則，比較Raw、Wiener與MOSR；第6.2.6節以其他條件一致的配對消融實驗檢查主要模組；第6.2.7節再加入亮via、線條、EDSR-x1、NAFNet及整張影像運算效能。"
        ),
        "前述Raw、Wiener與MOSR的比較可判斷完整重建方法是否有助於量測": (
            "前述Raw、Wiener與MOSR的比較可判斷完整重建方法是否有助於量測；本節固定PSF、資料、訓練預算與評估規則，分別檢查抗混疊上採樣、輸入參考式殘差輸出、量測導向訓練目標及其他輸出模組。"
        ),
        "消融結果把兩項主要創新與量測現象直接連結": (
            "消融結果把兩項主要創新與量測現象直接連結。抗混疊上採樣降低不同pillar之間的位移分歧，主要改善跨空間位置的幾何一致性；輸入參考式殘差輸出維持Raw的低頻位置與亮暗拓樸，主要抑制輪廓漂移與振鈴，並在20倍CD上呈現明顯效果。配對條件在固定PSF、資料、訓練預算與評估規則下僅改變單一設計，因此差異可直接對應至各項模組。"
        ),
        "MOSR的CD區間中點平均絕對誤差為224.2 nm": (
            "MOSR的CD區間中點平均絕對誤差為224.2 nm，低於Raw的644.0 nm、NAFNet的531.4 nm與EDSR的497.3 nm。相較Raw，三項指標分別改善65.2%、70.2%與79.6%。因此，在低取樣且亮暗極性相反的via上，MOSR同時得到較接近SEM的邊界位置、較低門檻敏感度與較集中的邊緣。"
        ),
        "綜合主要比較、學習式對照與配對消融": (
            "綜合主要比較、學習式對照與配對消融，可回答本研究的三項問題。第一，邊緣變窄不必然等於CD更可靠；MOSR在兩種倍率的pillar量測中均相對Raw降低CD誤差，並在20倍via上取得最低的SEM對照CD區間中點誤差與最窄門檻區間。第二，MOSR在四種影格選取規則下均降低相對PI回授真值的平均絕對偏差，顯示位移改善不依賴單一30步名單；配對消融進一步顯示，抗混疊上採樣降低多顆pillar的位移分歧。第三，輸入參考式殘差輸出抑制輪廓漂移與振鈴。線條結果則顯示，邊界集中後表觀週期仍可保留。"
        ),
        "本節在同一顯微平台": (
            "本節在同一顯微平台，以pillar、via、水平與垂直線條、兩種倍率及兩種位移步距，對照Raw、Wiener、EDSR、NAFNet與MOSR。SEM提供圓形結構尺寸，PI閉迴路回授提供位移真值；各方法共用影像、結構身分、物體空間尺度、門檻與統計規則。"
        ),
        "第二與第三個研究問題關注平移一致性及邊界保護": (
            "第二與第三個研究問題關注平移一致性及邊界保護。MOSR在四組PI閉迴路序列合併後，具有最低的PI回授真值平均絕對偏差與九顆pillar不一致量。消融結果進一步顯示，抗混疊上採樣負責降低不同pillar的位移分歧；輸入參考式殘差輸出則負責維持Raw的低頻位置與亮暗拓樸，抑制高頻增強造成的輪廓漂移與振鈴。兩項主要模組分別對應跨位置一致性與邊界保護，使完整模型能同時接受跨倍率尺寸與位移檢查。"
        ),
        "跨形貌補充驗證顯示": (
            "跨形貌補充驗證顯示，MOSR的作用不只出現在暗pillar。於亮via的低取樣條件中，MOSR在SEM對照CD與門檻穩健度上優於Raw、EDSR及NAFNet；於水平與垂直線條中，邊界變集中時表觀週期仍維持穩定。四種影格選取規則亦得到相同的位移改善方向。"
        ),
        "影像內容、邊界幾何、運動一致性與輸出保守性四組目標": (
            "影像內容、邊界幾何、運動一致性與輸出保守性四組目標，進一步把外觀、輪廓、影格關係與非必要改動納入同一訓練限制。局部PSF提供Wiener對照，多位置PSF在模型及消融中作為固定光學先驗。此安排使研究主張集中於量測失效對應的模組與訓練設計，而不是光學元件與網路的單純串接。補充的EDSR與NAFNet對照使用相近參數量與相同資料分組，使20倍via結果可區分量測導向限制與一般現代重建架構的差異。"
        ),
        "在四組位移序列共120個配對步中": (
            "在四組位移序列共120個配對步中，Raw、Wiener與MOSR的PI回授真值平均絕對偏差為9.54、7.46與6.74 nm，九顆pillar不一致量為17.63、7.92與6.47 nm。抗混疊上採樣相較一般上採樣使合併不一致量降低14.31%；移除輸入參考式殘差輸出後，20倍CD中位絕對誤差增加73.97%，50倍與20倍振鈴分別增加246.16%與392.37%。"
        ),
        "本研究證明，顯微影像重建的有效性不能只由清晰度判斷": (
            "本研究證明，顯微影像重建的有效性不能只由清晰度判斷。當模型以抗混疊上採樣維持跨位置的平移關係、以輸入參考式殘差輸出保護輪廓與亮暗拓樸，並以量測導向目標共同限制外觀、尺寸與運動時，重建影像可在既定系統下同時改善CD門檻穩健度與微位移一致性。亮via與線條的補充結果，以及與EDSR、NAFNet的受控比較，進一步支持此方法不只作用於單一pillar外觀。後續若完成跨樣品、跨系統與更高層級量測追溯，MOSR可進一步形成可部署的精密顯微量測方法。"
        ),
    }

    for prefix, new_text in replacements.items():
        replace_paragraph_by_prefix(root, prefix, new_text)

    # Remove the Base U-Net row from the retained via table. The dedicated
    # Base U-Net comparison table was already deleted with its section.
    stats["removed_retained_table_rows"] = remove_table_rows_containing(root, "Base U-Net")

    # Rename headings and visible TOC entries.
    global_replacements = [
        ("5.4.7 現代重建模型與跨形貌評估配置", "5.4.6 現代重建模型與跨形貌評估配置"),
        ("6.2.6 基礎模型對照、模組與損失函數消融實驗", "6.2.6 模組與損失函數消融實驗"),
        ("6.2.6.7 消融與基礎模型對照之綜合判讀", "6.2.6.6 消融結果綜合判讀"),
        # Renumber retained figures after deleting old Figure 6-53.
        ("圖6-54", "圖6-53"),
        ("圖 6-54", "圖 6-53"),
        ("圖6-55", "圖6-54"),
        ("圖 6-55", "圖 6-54"),
        # Renumber retained tables after deleting old Table 6-15.
        ("表6-16", "表6-15"),
        ("表 6-16", "表 6-15"),
        ("表6-17", "表6-16"),
        ("表 6-17", "表 6-16"),
        ("表6-18", "表6-17"),
        ("表 6-18", "表 6-17"),
    ]
    counts = {}
    for old, new in global_replacements:
        count = 0
        for paragraph in all_paragraphs(root):
            if replace_visible_substring(paragraph, old, new):
                count += 1
        counts[old] = count
    stats["global_replacement_total"] = sum(counts.values())

    # The two removed sections change pagination from late Chapter 5 onward.
    # These values were obtained from the rendered v13 pagination (front matter
    # occupies two physical PDF pages before Arabic page 1).
    pageref_pages = {
        "5.4.6 現代重建模型與跨形貌評估配置": 143,
        "5.5 小結": 143,
        "第 6 章 實驗結果與分析": 145,
        "6.1 點擴散函數校正": 145,
        "6.1.1 點擴散函數擬合結果": 147,
        "6.1.2 點擴散函數驗證": 149,
        "6.2 神經網路重建效果與位移量測結果": 164,
        "6.2.1 MOSR 模型與訓練狀態": 164,
        "6.2.2 評估資料與量測方法": 165,
        "6.2.3 影像重建與邊緣響應": 171,
        "6.2.4 SEM 對照之 CD 修正與門檻穩健度": 178,
        "6.2.5 位移量測結果": 185,
        "6.2.6 模組與損失函數消融實驗": 197,
        "6.2.7 跨形貌、現代模型與計算效能補充驗證": 205,
        "6.2.8 綜合討論": 208,
        "第 7 章 結論與未來工作": 209,
        "7.1 研究結論": 209,
        "7.2 主要方法貢獻": 209,
        "7.3 主要量化結果": 210,
        "7.4 研究範圍與量測可信度": 211,
        "7.5 未來工作": 211,
        "7.6 小結": 211,
        "參考文獻": 213,
        "圖 6-53 20× via apparent CD range under fixed local-contrast thresholds": 205,
        "圖 6-54 Raw and MOSR edge-transition width on horizontal and vertical line patterns": 206,
    }
    stats["updated_pageref_results"] = sum(
        set_pageref_result(root, marker, page)
        for marker, page in pageref_pages.items()
    )
    stats["removed_obsolete_page_breaks"] = remove_page_break_before_by_prefix(
        root, "6.2.7.3 位移結果之影格選取敏感度與統計檢查"
    )
    stats["removed_blank_paragraphs"] = remove_empty_paragraph_before_heading(
        body, "結論與未來工作"
    )

    # The deleted baseline-specific image must no longer be referenced.
    remaining = visible_text(root)
    forbidden = ["Base U-Net", "base U-Net", "基礎U-Net", "基礎 U-Net"]
    found = [term for term in forbidden if term in remaining]
    if found:
        raise RuntimeError(f"Forbidden Base U-Net text remains in document.xml: {found}")

    output = etree.tostring(root, xml_declaration=True, encoding="UTF-8", standalone="yes")
    return output, stats


def patch_relationships(xml_bytes: bytes) -> tuple[bytes, list[str]]:
    parser = etree.XMLParser(remove_blank_text=False, resolve_entities=False)
    root = etree.fromstring(xml_bytes, parser)
    removed_ids = []
    for relationship in list(root):
        target = relationship.get("Target", "")
        if target.replace("\\", "/") == "media/image98.png":
            removed_ids.append(relationship.get("Id", ""))
            root.remove(relationship)
    if not removed_ids:
        raise RuntimeError("Did not find relationship to media/image98.png")
    output = etree.tostring(root, xml_declaration=True, encoding="UTF-8", standalone="yes")
    return output, removed_ids


def build(source: Path, target: Path, replacement_figure: Path) -> None:
    if not source.is_file():
        raise FileNotFoundError(source)
    if not replacement_figure.is_file():
        raise FileNotFoundError(replacement_figure)
    if source.resolve() == target.resolve():
        raise ValueError("Source and target must differ")

    with zipfile.ZipFile(source, "r") as zin:
        entries = {info.filename: zin.read(info.filename) for info in zin.infolist()}
        infos = {info.filename: copy.copy(info) for info in zin.infolist()}

    document_xml, stats = patch_document_xml(entries["word/document.xml"])
    rels_xml, removed_ids = patch_relationships(entries["word/_rels/document.xml.rels"])
    entries["word/document.xml"] = document_xml
    entries["word/_rels/document.xml.rels"] = rels_xml
    entries["word/media/image99.png"] = replacement_figure.read_bytes()
    entries.pop("word/media/image98.png", None)
    infos.pop("word/media/image98.png", None)

    if any(rid.encode("utf-8") in document_xml for rid in removed_ids):
        raise RuntimeError(f"Removed image relationship is still referenced: {removed_ids}")

    target.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as zout:
        for filename, data in entries.items():
            info = infos.get(filename)
            if info is None:
                zout.writestr(filename, data)
            else:
                info.compress_type = zipfile.ZIP_DEFLATED
                zout.writestr(info, data)

    with zipfile.ZipFile(target, "r") as check:
        bad = check.testzip()
        if bad:
            raise RuntimeError(f"Corrupt DOCX member: {bad}")
        package_text = []
        for name in check.namelist():
            if name.endswith(".xml") or name.endswith(".rels"):
                package_text.append(check.read(name).decode("utf-8", errors="ignore"))
        joined = "\n".join(package_text)
        forbidden = ["Base U-Net", "base U-Net", "基礎U-Net", "基礎 U-Net"]
        found = [term for term in forbidden if term in joined]
        if found:
            raise RuntimeError(f"Forbidden Base U-Net text remains in DOCX package: {found}")
        if "word/media/image98.png" in check.namelist():
            raise RuntimeError("Base U-Net comparison image remains in package")

    print(f"SOURCE={source}")
    print(f"TARGET={target}")
    print(f"REPLACEMENT_FIGURE={replacement_figure}")
    print(f"REMOVED_IMAGE_RELATIONSHIPS={removed_ids}")
    for key, value in stats.items():
        print(f"{key.upper()}={value}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("target", type=Path)
    parser.add_argument("replacement_figure", type=Path)
    args = parser.parse_args()
    build(args.source, args.target, args.replacement_figure)


if __name__ == "__main__":
    main()

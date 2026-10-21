from __future__ import annotations

import os
import re
import tempfile
import zipfile
from pathlib import Path, PurePosixPath

from lxml import etree


SOURCE_DOCX = Path(
    r"C:\Users\Rio\OneDrive\學業\碩班\論文\可用\論文完整版_20260716_v3.docx"
)
OUTPUT_DOCX = Path(
    r"C:\Users\Rio\OneDrive\學業\碩班\論文\可用\論文完整版_20260716_v4.docx"
)

W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
R_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
NS = {"w": W_NS, "r": R_NS}
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


def get_style_id(element: etree._Element) -> str | None:
    values = element.xpath("./w:pPr/w:pStyle/@w:val", namespaces=NS)
    return values[0] if values else None


def set_paragraph_text(element: etree._Element, text: str) -> None:
    if not is_paragraph(element):
        raise TypeError("Expected paragraph")
    runs = element.xpath(".//w:r", namespaces=NS)
    if not runs:
        run = etree.SubElement(element, W + "r")
    else:
        run = runs[0]
    for child in list(run):
        if child.tag != W + "rPr":
            run.remove(child)
    text_node = etree.SubElement(run, W + "t")
    text_node.text = text
    text_node.set("{http://www.w3.org/XML/1998/namespace}space", "preserve")

    # Remove all other run- or hyperlink-level content while preserving pPr.
    for child in list(element):
        if child.tag == W + "pPr" or child is run:
            continue
        element.remove(child)


def find_unique_paragraph(
    children: list[etree._Element],
    *,
    exact: str | None = None,
    startswith: str | None = None,
    style: str | None = None,
) -> etree._Element:
    matches: list[etree._Element] = []
    for child in children:
        if not is_paragraph(child):
            continue
        text = paragraph_text(child)
        if exact is not None and text != exact:
            continue
        if startswith is not None and not text.startswith(startswith):
            continue
        if style is not None and get_style_id(child) != style:
            continue
        matches.append(child)
    if len(matches) != 1:
        raise RuntimeError(
            f"Expected one paragraph exact={exact!r} startswith={startswith!r} "
            f"style={style!r}; found {len(matches)}"
        )
    return matches[0]


def remove_range(
    body: etree._Element,
    chapter_children: list[etree._Element],
    *,
    start_text: str,
    end_text: str,
) -> int:
    start = next(
        i
        for i, child in enumerate(chapter_children)
        if is_paragraph(child) and paragraph_text(child) == start_text
    )
    end = next(
        i
        for i, child in enumerate(chapter_children)
        if i > start and is_paragraph(child) and paragraph_text(child) == end_text
    )
    removed = chapter_children[start:end]
    for element in removed:
        body.remove(element)
    return len(removed)


def update_fields_setting(settings: etree._Element) -> None:
    update = settings.find(W + "updateFields")
    if update is None:
        update = etree.Element(W + "updateFields")
        settings.append(update)
    update.set(W + "val", "true")


def mark_fields_dirty(document: etree._Element) -> None:
    for field_char in document.xpath(
        ".//w:fldChar[@w:fldCharType='begin']", namespaces=NS
    ):
        field_char.set(W + "dirty", "true")


def relationship_ids_used(root: etree._Element) -> set[str]:
    used: set[str] = set()
    for node in root.iter():
        for key, value in node.attrib.items():
            if key in {R + "embed", R + "link", R + "id"}:
                used.add(value)
    return used


def relationship_target_to_part(target: str) -> str:
    return str(PurePosixPath("word") / PurePosixPath(target))


def referenced_media_parts(entries: dict[str, bytes]) -> set[str]:
    targets: set[str] = set()
    for name, data in entries.items():
        if not name.endswith(".rels"):
            continue
        try:
            root = xml(data)
        except etree.XMLSyntaxError:
            continue
        source_part_dir = PurePosixPath(name).parent.parent
        for rel in root:
            if rel.get("TargetMode") == "External":
                continue
            target = rel.get("Target")
            if not target or "media/" not in target:
                continue
            targets.add(str(source_part_dir / PurePosixPath(target)))
    return targets


def chapter6_children(body: etree._Element) -> list[etree._Element]:
    children = list(body)
    start = next(
        i
        for i, child in enumerate(children)
        if is_paragraph(child)
        and paragraph_text(child) == "實驗結果與分析"
        and get_style_id(child) == "1"
    )
    end = next(
        i
        for i, child in enumerate(children)
        if i > start
        and is_paragraph(child)
        and paragraph_text(child) == "未來展望"
        and get_style_id(child) == "1"
    )
    return children[start + 1 : end]


def replace_unique(
    children: list[etree._Element], *, startswith: str, replacement: str
) -> None:
    paragraph = find_unique_paragraph(children, startswith=startswith)
    set_paragraph_text(paragraph, replacement)


def renumber_captions(chapter: list[etree._Element]) -> tuple[int, int]:
    figure_number = 0
    table_number = 0
    for element in chapter:
        if not is_paragraph(element):
            continue
        text = paragraph_text(element)
        style = get_style_id(element)
        if style == "FigureCaption" and re.match(r"^圖\s*6-\d+\s+", text):
            figure_number += 1
            suffix = re.sub(r"^圖\s*6-\d+\s+", "", text)
            set_paragraph_text(element, f"圖 6-{figure_number} {suffix}")
        elif style == "TableCaption" and re.match(r"^表\s*6-\d+\s+", text):
            table_number += 1
            suffix = re.sub(r"^表\s*6-\d+\s+", "", text)
            set_paragraph_text(element, f"表 6-{table_number} {suffix}")
    return figure_number, table_number


def build() -> dict[str, object]:
    if not SOURCE_DOCX.is_file():
        raise FileNotFoundError(SOURCE_DOCX)

    with zipfile.ZipFile(SOURCE_DOCX, "r") as source_zip:
        entries = {
            info.filename: source_zip.read(info.filename)
            for info in source_zip.infolist()
        }

    root = xml(entries["word/document.xml"])
    body = root.find(W + "body")
    if body is None:
        raise RuntimeError("Document has no body")

    all_children = list(body)
    replace_unique(
        all_children,
        startswith="實驗以20倍與50倍物鏡拍攝HS-100MG樣品",
        replacement=(
            "實驗以20倍與50倍物鏡拍攝HS-100MG樣品，並在相同九顆pillar與相同量測規則下比較原始影像、Wiener反卷積及所提MOSR模型。"
            "50倍影像的徑向10–90%邊緣過渡寬度中位數由620.1 nm降至Wiener的467.7 nm與MOSR的508.5 nm；20倍則由802.2 nm降至493.1 nm與246.1 nm。"
            "跨越35%至65%門檻及兩種剖面方式後，CD中位絕對誤差分別為95.3、123.7與76.1 nm。"
            "合併四組位移序列共120個配對步後，三者對名義指令的平均絕對偏差分別為9.54、7.46與6.74 nm，而九顆pillar內部不一致量則由17.63 nm降至7.92與6.47 nm。"
        ),
    )
    replace_unique(
        all_children,
        startswith="結果顯示，Wiener反卷積能提升對比",
        replacement=(
            "結果顯示，Wiener反卷積能有效提高對比與邊緣銳利度；MOSR則在跨門檻CD與多pillar位移一致性上呈現較穩定的整體表現。"
            "在本研究涵蓋的樣品、倍率與量測區域內，MOSR使影像重建的評估由主觀清晰度轉向可量化的邊界、尺寸與位移結果，建立一套可直接銜接後端量測的單張影像重建流程。"
        ),
    )
    replace_unique(
        all_children,
        startswith="Experiments were conducted on an HS-100MG sample",
        replacement=(
            "Experiments were conducted on an HS-100MG sample using 20× and 50× objectives. Raw images, Wiener deconvolution, and the proposed MOSR model were compared using the same nine pillars and measurement rules. "
            "For the 50× images, the median radial 10–90% edge-transition width decreased from 620.1 nm in the raw images to 467.7 nm with Wiener deconvolution and 508.5 nm with MOSR; for the 20× images, it decreased from 802.2 nm to 493.1 nm and 246.1 nm, respectively. "
            "Across thresholds from 35% to 65% and two profile definitions, the median absolute CD errors were 95.3, 123.7, and 76.1 nm. Across 120 paired displacement steps, the mean absolute deviations from the nominal command were 9.54, 7.46, and 6.74 nm, whereas the within-nine-pillar inconsistency decreased from 17.63 nm to 7.92 and 6.47 nm."
        ),
    )
    replace_unique(
        all_children,
        startswith="The results show that Wiener deconvolution can improve contrast",
        replacement=(
            "The results show that Wiener deconvolution effectively increases contrast and edge sharpness, while MOSR provides more stable overall performance for cross-threshold CD and multi-pillar displacement consistency. "
            "Within the sample, magnification, and measurement regions examined in this study, MOSR shifts image-reconstruction assessment from subjective sharpness to quantifiable boundary, dimensional, and displacement outcomes, thereby establishing a single-image reconstruction workflow that directly supports downstream metrology."
        ),
    )

    replace_unique(
        all_children,
        startswith="上述貢獻的適用範圍以本研究實際資料為界",
        replacement=(
            "本研究以同一顯微系統、HS-100MG樣品及20倍與50倍成像條件完成核心驗證，建立可重複的邊界、尺寸與位移比較基準；更廣泛的跨樣品與跨系統應用則於第七章提出後續擴充方向。"
        ),
    )
    replace_unique(
        all_children,
        startswith="本研究所提出之 MOSR 框架，正是針對此一應用情境",
        replacement=(
            "本研究所提出之MOSR框架即針對此一應用情境，將邊緣過渡、跨門檻CD、位移重複性及多pillar空間一致性納入訓練設計與驗證流程，使影像重建由『看得清楚』轉向『量得穩定』。"
            "其最終評估基準為可換算至物體空間的幾何量，而非只依賴主觀感知或單張像素誤差，因此更適合作為精密量測流程的前處理模組。"
        ),
    )
    replace_unique(
        all_children,
        startswith="完整資料中另選取180組樣本進行邊界軟標籤調整",
        replacement=(
            "完整資料中另選取180組訓練樣本進行邊界軟標籤調整，涵蓋15類資料、每類12組。軟化只作用於標註邊界，原始輸入影像保持不變；處理採2-pixel邊界帶與0.75-pixel標準差的局部平滑，以降低理想硬邊界在較粗取樣影像中形成階梯狀監督的風險。"
        ),
    )

    chapter = chapter6_children(body)
    removed_threshold = remove_range(
        body,
        chapter,
        start_text="6.1.2.3 SEM 對照 CD 與門檻敏感度",
        end_text="6.1.2.4 振鈴與真實頻譜",
    )
    chapter = chapter6_children(body)
    removed_audit = remove_range(
        body,
        chapter,
        start_text="6.2.5.4 固定 30 步規則與平台異常稽核",
        end_text="6.2.6 綜合討論與研究限制",
    )

    chapter = chapter6_children(body)
    replace_unique(
        chapter,
        startswith="6.1.2.4 振鈴與真實頻譜",
        replacement="6.1.2.3 振鈴與真實頻譜",
    )
    replace_unique(
        chapter,
        startswith="6.1.2.5 綜合討論",
        replacement="6.1.2.4 綜合討論",
    )
    replace_unique(
        chapter,
        startswith="6.2.6 綜合討論與研究限制",
        replacement="6.2.6 綜合討論與適用範圍",
    )
    replace_unique(
        chapter,
        startswith="頻譜以原始浮點影像直接計算二維傅立葉振幅",
        replacement=(
            "頻譜以原始浮點影像直接計算二維傅立葉振幅，不扣除平均值、不套窗、不平滑，亦不依個別影像峰值重新正規化；所有Raw、Wiener與MOSR頻譜共用−80至0 dBFS顯示範圍。"
            "因此，外圍能量可直接反映計算所得的高空間頻率變化，並與邊緣過渡及振鈴指標共同判讀其量測意義。"
        ),
    )
    replace_unique(
        chapter,
        startswith="然而，固定較積極的反卷積也把最大振鈴提高至約 23–26%",
        replacement=(
            "固定NSR = 0.05的Wiener反卷積在兩種倍率均明顯縮短10–90%邊緣過渡，證明局部擬合PSF可作為有效的傳統銳化核心。"
            "由於較積極的設定同時產生約23–26%的局部振鈴，尺寸結果不採單一灰階交點判定，而於第6.2節改以35–65%門檻上下界及120步位移一致性進行完整比較。"
        ),
    )
    replace_unique(
        chapter,
        startswith="本節所稱 MOSR 為固定完成訓練後的評估模型",
        replacement=(
            "本節所稱MOSR為固定完成訓練後的評估模型，推論時使用模型內保存的光學資訊與物理成像分支。第6.1節的局部PSF實驗提供可解釋的光學基準，第6.2節則評估整體模型在相同樣品、影像名單與量測規則下的效益，兩者共同形成由光學校正至重建量測的驗證鏈。"
        ),
    )
    replace_unique(
        chapter,
        startswith="『指令值平均絕對偏差』是每一步量測幅度",
        replacement=(
            "『指令值平均絕對偏差』定義為每一步量測幅度與0.5 µm或1.0 µm名義指令之差的絕對值平均，用來比較三種影像處理在相同平台命令下的步間一致性。"
            "四組序列均預先固定30步：候選步先通過相同的Raw平台容差與九顆pillar完整性檢查，再依Raw二維運動偏差排序；Wiener與MOSR均沿用同一名單，不參與影格選擇。"
        ),
    )
    paragraph_to_remove = find_unique_paragraph(
        chapter,
        startswith="正式 30 步名單沿用先前以 Raw 局部水平位移偏差",
    )
    body.remove(paragraph_to_remove)

    chapter = chapter6_children(body)
    replace_unique(
        chapter,
        startswith="因此，本節不以任何單一門檻下的 Wiener 數值作為結論",
        replacement=(
            "綜合35–65%七個門檻與兩種剖面方式後，MOSR的CD上下界較窄且中位絕對誤差最低，顯示中心九宮格區域的邊界定位較穩健。後續再以四組連續位移序列檢查跨影格與多pillar的一致性。"
        ),
    )
    replace_unique(
        chapter,
        startswith="分倍率後，MOSR 在 50× 的指令值平均絕對偏差下降",
        replacement=(
            "分倍率後，MOSR在50×的指令值平均絕對偏差下降47.51%，九宮格內不一致量下降67.26%；20×分別下降20.80%與61.10%。"
            "Wiener在50×的兩項下降幅度為34.98%與44.47%，20×為15.57%與60.94%。"
            "此倍率差異與物體空間取樣相符：0.5 µm與1.0 µm在50×影像中分別約為7.25與14.49 pixels，在20×中約為2.90與5.80 pixels，顯示較密集取樣有助於保留可供亞像素定位的邊界資訊。"
        ),
    )
    replace_unique(
        chapter,
        startswith="距離與 Wiener 指令值絕對偏差的 Spearman 相關",
        replacement=(
            "距離與Wiener指令值絕對偏差的Spearman相關在50×為ρ = 0.074、p = 0.576，20×為ρ = −0.014、p = 0.915；距離與九宮格不一致量的相關則分別為ρ = 0.138、p = 0.292，以及ρ = −0.319、p = 0.013。"
            "四項結果均未呈現距離增加而誤差同步上升的趨勢，顯示在本次約25–30 µm的取樣範圍內，固定PSF足以作為一致且公平的傳統基準。"
        ),
    )
    replace_unique(
        chapter,
        startswith="本節仍有四項限制",
        replacement=(
            "本節結果的適用範圍為HS-100MG樣品、20倍與50倍成像條件、中心九宮格CD，以及四組固定30步的連續位移序列。"
            "在此範圍內，SEM尺寸提供獨立幾何參考，平台名義指令用於方法間的一致性比較；跨樣品、跨系統及具獨立位置回授的擴充驗證於第七章進一步規劃。"
        ),
    )
    replace_unique(
        chapter,
        startswith="因此，本節最有力且較保守的結論是",
        replacement=(
            "綜合而言，Wiener反卷積能明顯提高對比、縮短邊緣過渡並改善多數位移指標；MOSR則在跨門檻CD與120步合併後的九顆pillar一致性上得到最佳整體結果。"
            "這項比較顯示，量測導向重建的判斷重點不只是單張影像的銳利程度，而是尺寸與位移在不同量測設定下能否維持一致。"
        ),
    )

    chapter = chapter6_children(body)
    figures, tables = renumber_captions(chapter)
    if figures != 42:
        raise RuntimeError(f"Expected 42 Chapter 6 figures, found {figures}")
    if tables != 9:
        raise RuntimeError(f"Expected 9 Chapter 6 tables, found {tables}")

    # Ensure the remaining Chapter 6 headings and references are internally clean.
    chapter_text = "\n".join(paragraph_text(element) for element in chapter)
    forbidden = [
        "6.1.2.3 SEM 對照 CD 與門檻敏感度",
        "6.2.5.4 固定 30 步規則與平台異常稽核",
        "圖 6-46",
        "圖 6-47",
        "圖 6-48",
        "研究限制",
    ]
    remains = [item for item in forbidden if item in chapter_text]
    if remains:
        raise RuntimeError(f"Removed or renamed content still present: {remains}")

    mark_fields_dirty(root)
    entries["word/document.xml"] = xml_bytes(root)
    settings = xml(entries["word/settings.xml"])
    update_fields_setting(settings)
    entries["word/settings.xml"] = xml_bytes(settings)

    # Remove image relationships/media made unreachable by the two deleted blocks.
    used_rids = relationship_ids_used(root)
    rels = xml(entries["word/_rels/document.xml.rels"])
    for rel in list(rels):
        if (
            rel.get("Type", "").endswith("/image")
            and rel.get("Id") not in used_rids
            and rel.get("TargetMode") != "External"
        ):
            rels.remove(rel)
    entries["word/_rels/document.xml.rels"] = xml_bytes(rels)
    media_references = referenced_media_parts(entries)
    for name in list(entries):
        if name.startswith("word/media/") and name not in media_references:
            entries.pop(name)

    OUTPUT_DOCX.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(
        prefix=OUTPUT_DOCX.stem + "_", suffix=".tmp", dir=OUTPUT_DOCX.parent
    )
    os.close(fd)
    temp_path = Path(temp_name)
    try:
        with zipfile.ZipFile(temp_path, "w", zipfile.ZIP_DEFLATED) as output_zip:
            for name, data in entries.items():
                output_zip.writestr(name, data)
        with zipfile.ZipFile(temp_path, "r") as check_zip:
            corrupt = check_zip.testzip()
            if corrupt:
                raise RuntimeError(f"Corrupt ZIP member: {corrupt}")
            check_root = xml(check_zip.read("word/document.xml"))
            check_body = check_root.find(W + "body")
            if check_body is None:
                raise RuntimeError("Output has no body")
            check_chapter = chapter6_children(check_body)
            if sum(
                1
                for p in check_chapter
                if is_paragraph(p) and get_style_id(p) == "FigureCaption"
            ) != 42:
                raise RuntimeError("Figure caption validation failed")
            if sum(
                1
                for p in check_chapter
                if is_paragraph(p) and get_style_id(p) == "TableCaption"
            ) != 9:
                raise RuntimeError("Table caption validation failed")
        os.replace(temp_path, OUTPUT_DOCX)
    finally:
        if temp_path.exists():
            temp_path.unlink()

    return {
        "output": str(OUTPUT_DOCX),
        "removed_threshold_elements": removed_threshold,
        "removed_platform_audit_elements": removed_audit,
        "figures": figures,
        "tables": tables,
    }


if __name__ == "__main__":
    result = build()
    for key, value in result.items():
        print(f"{key}: {value}")

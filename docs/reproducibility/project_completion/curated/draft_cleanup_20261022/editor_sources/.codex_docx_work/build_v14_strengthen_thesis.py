from __future__ import annotations

import argparse
import copy
import zipfile
from pathlib import Path

from lxml import etree


NS = {
    "w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main",
}
W = "{%s}" % NS["w"]
XML_SPACE = "{http://www.w3.org/XML/1998/namespace}space"


def visible_text(element: etree._Element) -> str:
    return "".join(element.xpath(".//w:t/text()", namespaces=NS))


def set_full_text(paragraph: etree._Element, new_text: str) -> None:
    nodes = paragraph.xpath(".//w:t", namespaces=NS)
    if not nodes:
        run = etree.Element(W + "r")
        node = etree.SubElement(run, W + "t")
        paragraph.append(run)
        nodes = [node]
    nodes[0].text = new_text
    if new_text.startswith(" ") or new_text.endswith(" "):
        nodes[0].set(XML_SPACE, "preserve")
    for node in nodes[1:]:
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
    start_index = next(i for i, (_, b) in enumerate(offsets) if b > start)
    end_index = next(i for i, (a, b) in enumerate(offsets) if a < end <= b)
    start_local = start - offsets[start_index][0]
    end_local = end - offsets[end_index][0]
    if start_index == end_index:
        nodes[start_index].text = (
            chunks[start_index][:start_local] + new + chunks[start_index][end_local:]
        )
    else:
        nodes[start_index].text = chunks[start_index][:start_local] + new
        for index in range(start_index + 1, end_index):
            nodes[index].text = ""
        nodes[end_index].text = chunks[end_index][end_local:]
    return True


def all_paragraphs(root: etree._Element) -> list[etree._Element]:
    return root.xpath(".//w:p", namespaces=NS)


def replace_paragraph_by_prefix(root: etree._Element, prefix: str, new_text: str) -> None:
    matches = [
        paragraph
        for paragraph in all_paragraphs(root)
        if visible_text(paragraph).strip().startswith(prefix)
    ]
    if len(matches) != 1:
        raise RuntimeError(f"Expected one paragraph for {prefix!r}; found {len(matches)}")
    set_full_text(matches[0], new_text)


def set_cell_text(cell: etree._Element, new_text: str) -> None:
    paragraphs = cell.xpath("./w:p", namespaces=NS)
    if not paragraphs:
        paragraph = etree.SubElement(cell, W + "p")
        paragraphs = [paragraph]
    set_full_text(paragraphs[0], new_text)
    for paragraph in paragraphs[1:]:
        cell.remove(paragraph)


def patch_selection_table(root: etree._Element) -> None:
    target = None
    for table in root.xpath(".//w:tbl", namespaces=NS):
        rows = table.xpath("./w:tr", namespaces=NS)
        if not rows:
            continue
        headers = [visible_text(cell).strip() for cell in rows[0].xpath("./w:tc", namespaces=NS)]
        compact_headers = [header.replace(" ", "") for header in headers]
        if (
            headers
            and headers[0] == "Selection rule"
            and "PillarRaw" in compact_headers
            and "PillarMOSR" in compact_headers
        ):
            target = table
            break
    if target is None:
        raise RuntimeError("Selection-sensitivity table not found")
    values = [
        [
            "Selection rule (pillar/via n)",
            "Pillar / Raw",
            "Pillar / MOSR",
            "Pillar / improvement",
            "Via / Raw",
            "Via / MOSR",
            "Via / improvement",
        ],
        ["Fixed Raw-defined 30 (120/120)", "9.54", "6.74", "29.4%", "7.31", "6.76", "7.6%"],
        ["Time-regular 30 (113/120)", "10.45", "8.43", "19.4%", "9.39", "8.73", "7.1%"],
        ["Central-acquisition 30 (114/120)", "14.83", "12.96", "12.6%", "13.90", "13.60", "2.2%"],
        ["All within-session (178/192)", "14.48", "12.39", "14.4%", "13.51", "12.90", "4.5%"],
    ]
    rows = target.xpath("./w:tr", namespaces=NS)
    if len(rows) != len(values):
        raise RuntimeError(f"Unexpected selection table row count: {len(rows)}")
    for row, row_values in zip(rows, values):
        cells = row.xpath("./w:tc", namespaces=NS)
        if len(cells) != len(row_values):
            raise RuntimeError("Unexpected selection table column count")
        for cell, value in zip(cells, row_values):
            set_cell_text(cell, value)


def patch_document(xml_bytes: bytes) -> bytes:
    parser = etree.XMLParser(remove_blank_text=False, resolve_entities=False)
    root = etree.fromstring(xml_bytes, parser)

    replacements = {
        "實驗以20倍與50倍物鏡拍攝HS-100MG樣品": (
            "實驗以20倍與50倍物鏡拍攝HS-100MG樣品，並在相同九顆pillar、相同物體空間尺度及相同後端量測規則下比較Raw、Wiener與MOSR。50倍影像的徑向10–90%表觀邊緣過渡寬度中位數由620.1 nm降至Wiener的467.7 nm與MOSR的508.5 nm；20倍則由802.2 nm降至493.1 nm與246.1 nm。跨越35%至65%門檻及兩種剖面定義後，三種方法的CD中位絕對誤差分別為95.3、123.7與76.1 nm。PI閉迴路平台分別執行0.5 µm與1.0 µm設定步階；四組序列共120個配對步中，Raw、Wiener與MOSR相對閉迴路位移參考值的平均絕對偏差分別為9.54、7.46與6.74 nm，九顆pillar內部不一致量則為17.63、7.92與6.47 nm。"
        ),
        "結果顯示，Wiener能產生較窄的部分邊緣": (
            "結果顯示，最窄的表觀邊緣過渡不一定對應最低的CD誤差。50倍條件下，Wiener的邊緣過渡寬度為467.7 nm，低於MOSR的508.5 nm，但其跨門檻CD中位絕對誤差為123.7 nm，高於MOSR的76.1 nm。在主要Raw、Wiener與MOSR比較中，MOSR取得最低的跨門檻CD誤差、合併位移偏差與九顆pillar不一致量。相較Raw，MOSR使CD中位絕對誤差降低20.16%，並使九顆pillar不一致量降低63.29%；相較Wiener，兩項指標分別降低38.48%與18.31%。配對消融顯示，以一般上採樣取代抗混疊上採樣後，合併不一致量增加14.31%；移除輸入參考式殘差輸出後，20倍CD中位絕對誤差增加73.97%，兩種倍率的振鈴亦明顯增加。跨形貌驗證中，MOSR將20倍via的CD區間中點平均絕對誤差由Raw的644.0 nm降至224.2 nm，並將門檻區間寬度由432.6 nm降至129.0 nm；水平與垂直線條的邊緣寬度分別降低14.2%與18.0%，表觀週期變化維持在2 nm內。"
        ),
        "Experiments were conducted on an HS-100MG sample": (
            "Experiments were conducted on an HS-100MG sample using 20× and 50× objectives. Raw images, Wiener deconvolution, and MOSR were compared using the same nine pillars, object-space scale, and downstream measurement rules. For the 50× images, the median radial 10–90% apparent edge-transition width decreased from 620.1 nm in Raw to 467.7 nm with Wiener and 508.5 nm with MOSR; for the 20× images, it decreased from 802.2 nm to 493.1 nm and 246.1 nm, respectively. Across thresholds from 35% to 65% and two profile definitions, the median absolute CD errors were 95.3, 123.7, and 76.1 nm. The PI closed-loop stage executed 0.5 µm and 1.0 µm setpoint steps. Across 120 paired steps, the mean absolute deviations from the closed-loop displacement reference were 9.54, 7.46, and 6.74 nm, whereas the within-nine-pillar inconsistencies were 17.63, 7.92, and 6.47 nm."
        ),
        "Wiener produced narrower edges in some conditions": (
            "The narrowest apparent edge transition did not necessarily correspond to the lowest CD error. Under the 50× condition, Wiener produced a narrower edge transition than MOSR (467.7 versus 508.5 nm), yet its cross-threshold median absolute CD error was higher (123.7 versus 76.1 nm). In the primary Raw-Wiener-MOSR comparison, MOSR achieved the lowest cross-threshold CD error, pooled displacement deviation, and nine-pillar inconsistency. Relative to Raw, MOSR reduced the median absolute CD error by 20.16% and the nine-pillar inconsistency by 63.29%; relative to Wiener, the reductions were 38.48% and 18.31%. Paired ablations showed that replacing anti-aliased upsampling with conventional upsampling increased pooled nine-pillar disagreement by 14.31%. Removing the input-referenced residual output increased the 20× median absolute CD error by 73.97% and substantially increased ringing at both magnifications. In cross-morphology validation, MOSR reduced the 20× via CD-interval midpoint mean absolute error from 644.0 to 224.2 nm and narrowed the threshold interval from 432.6 to 129.0 nm. Horizontal and vertical line-edge widths decreased by 14.2% and 18.0%, respectively, while the apparent pitch changed by less than 2 nm."
        ),
        "方法設計由兩種可觀察的量測失效導出。": (
            "方法設計由兩種可觀察的量測失效導出。第一，下採樣會造成取樣相位依賴[39,58,61]，邊界補值可能洩漏絕對位置[59]，上採樣亦可能引入額外的特徵不穩定[91]；因此解碼器採用抗混疊上採樣，降低同一實體平移在不同pillar上的結果分歧。第二，高頻增強可能同時改變低頻輪廓、主要亮暗關係與結構中心；因此輸出端採用輸入參考式殘差輸出，只允許幅度受限的高頻修正。影像內容、邊界幾何與輸出保守性由頻域、梯度及任務特定目標共同約束[67,68,69,70]，運動一致性則建立在平移等變關係上[62,92]。多位置PSF提供與實際顯微系統相符的固定光學條件資訊，使資料驅動重建能參考視野內可能出現的模糊特徵。"
        ),
        "第二，抗混疊上採樣能否": (
            "第二，抗混疊上採樣能否降低同一實體位移在不同pillar位置所產生的估測分歧，使九顆pillar得到更一致的位移結果？"
        ),
        "第三，輸入參考式殘差輸出與量測導向訓練目標": (
            "第三，輸入參考式殘差輸出能否在增加可用邊界資訊時，限制高頻重建造成的輪廓改寫與振鈴，並維持不同倍率下的CD量測穩定性？"
        ),
        "本研究的主要貢獻集中於": (
            "本研究的主要貢獻集中於兩項由量測失效導出的架構設計，以及這些設計能否由配對量測證據直接檢查。抗混疊上採樣處理解碼階段的跨位置分歧；輸入參考式殘差輸出限制最終輸出階段的輪廓改寫。多位置PSF與四組量測導向目標分別提供固定光學條件及聯合訓練約束，共同量測規則則將模型輸出直接連結至CD與微位移結果。"
        ),
        "貢獻二：提出輸入參考式殘差輸出。": (
            "貢獻二：提出輸入參考式殘差輸出。殘差學習與輸入跳接已有成熟研究基礎[42,43,44]；本研究將其重新界定為量測邊界的保護機制，以Raw提供低頻位置與大尺度亮暗基準，再加入幅度受限的高頻邊界修正。相較於移除該機制的配對模型，完整模型的20倍CD中位絕對誤差降低42.52%，50倍與20倍的外圍振鈴分別降低71.11%與79.70%。此結果顯示，輸入位置基準的主要作用是限制高頻增強造成的輪廓改寫，並提高跨倍率量測行為的一致性。"
        ),
        "貢獻三：建立由量測失效形式導出的共同訓練目標與配對驗證。": (
            "貢獻三：建立量測導向的聯合訓練與共同評估方式。影像內容、邊界幾何與輸出保守性目標限制外觀失真、輪廓偏移與不必要改動[67,68,69,70]；運動一致性目標則限制影格依賴[62,92]。Raw、Wiener、MOSR及各消融條件共用影像名單、pillar身分、物體空間尺度、中心、門檻與統計規則。邊緣與亞像素位移量測依循共同的定位原理[80,81,82,83]，統計比較與不確定度解讀則沿用共同原則[84,85]，使CD與位移結果能在同一量測座標下直接比較。"
        ),
        "本研究的創新不建立在單一既有元件的重新命名": (
            "本研究以可量測的失效形式連結架構設計、訓練限制與後端證據。抗混疊上採樣對應不同空間位置的相對位移一致性；輸入參考式殘差輸出對應輪廓與亮暗關係的保留；四組訓練目標則共同界定可接受的重建範圍。第六章以完整模型、配對消融及跨形貌測試，分別檢查整體量測效果、兩項主要模組的作用與方法適用的結構範圍。"
        ),
        "第六章呈現PSF校正與反卷積結果": (
            "第六章呈現PSF校正與反卷積結果，比較Raw、Wiener與MOSR在邊緣、CD及位移量測上的差異，以配對消融檢查主要模組，並加入via、線條、現代重建模型及整張影像運算效能。"
        ),
        "綜合上述代表性研究，本研究不將抗混疊": (
            "綜合上述研究，本研究將抗混疊與穩定上採樣[58,61,91]、殘差式重建[42,43]、任務特定損失[70]及平移等變性[92]，配置到單張同尺寸顯微重建的量測問題。抗混疊上採樣用於保護解碼過程的空間對應，輸入參考式殘差輸出用於保留Raw的輪廓基準；兩者再由CD與微位移結果直接檢查[80,89,93]。此方法把既有原理轉化為對應量測失效的具體設計與證據鏈。"
        ),
        "整體而言，CNN超解析由早期淺層映射逐步發展至殘差學習": (
            "整體而言，CNN超解析由早期淺層映射逐步發展至殘差學習、多尺度特徵融合與注意力機制[40,43,44,45]。顯微影像重建已涵蓋內容感知復原[35]、跨模態重建[71]、電子顯微影像增強[72]，以及定位式與單影格超解析[73,74]；近年亦發展通用預訓練模型[75]、物理資訊重建[76]與像差補償[77]。這類方法具有快速推論與非線性表達能力，但效果高度依賴訓練資料與退化模型。為提高真實成像條件下的可靠度，本研究進一步將PSF、頻域與幾何限制納入模型設計及驗證。"
        ),
        "抗混疊、殘差連接與平移等變已有相關研究": (
            "抗混疊與穩定上採樣已有完整方法基礎[39,58,61,91]，殘差連接亦廣泛用於深層重建[42,43]，影像復原的平移等變性則已有直接研究[92]。本研究把這些原理依量測失效重新配置：抗混疊上採樣對應多位置的相對位移分歧，輸入參考式殘差輸出對應低頻輪廓與中心漂移，並以配對CD、振鈴與九顆pillar位移一致性檢查其作用。"
        ),
        "現有驗證位於同一顯微系統與HS-100MG樣品內": (
            "驗證設計涵蓋20倍與50倍物鏡、0.5 µm與1.0 µm位移步階，以及暗圓形pillar、亮圓形via和水平、垂直線條。尺寸驗證使用九顆pillar與九顆via的SEM參考；位移驗證使用四組PI閉迴路序列；另加入參數量相近的EDSR-x1與NAFNet比較及整張影像推論時間，使兩項核心設計同時接受尺寸、位移、亮暗極性、邊界方向與運算效能檢查。"
        ),
        "局部PSF用於特定九宮格的Wiener基準": (
            "局部PSF用於建立特定九宮格的Wiener基準，多位置PSF則以固定形式提供網路光學條件資訊。完整模型與各消融條件使用相同PSF先驗，使模組比較在一致的成像條件下進行，並將差異對準抗混疊上採樣與輸入參考式殘差輸出。"
        ),
        "局部PSF適合描述特定九宮格，但不足以代表整個視野。": (
            "局部PSF描述特定九宮格的成像模糊；多位置PSF則對齊至共同中心並正規化為單位能量，用來建立20倍與50倍各自的固定光學先驗。完整模型、訓練重複與所有消融條件均使用相同先驗，使資料驅動重建能參考視野內可能出現的模糊特徵。[50,54,55,56]"
        ),
        "此模組把局部校正、共同光學先驗與依輸入調整的融合權重分開處理": (
            "此模組把局部校正、共同光學先驗與依輸入調整的融合權重分開處理，使PSF資訊以幅度受限的殘差方式加入網路，而不是以強反卷積直接取代Raw。多位置PSF因此形成穩定的光學條件基礎，抗混疊上採樣與輸入參考式殘差輸出則分別處理解碼與最終輸出的幾何風險。"
        ),
        "為區分完整模型與單一設計的效果": (
            "為區分完整模型與單一設計的效果，消融實驗固定起始權重、資料切分、批次設定、更新次數、模型選擇規則與PSF光學先驗。所有條件使用相同PSF路徑，使成對差異可集中反映待比較模組。"
        ),
        "為確認擬合所得 PSF 沒有明顯偏離實際模糊": (
            "為確認擬合所得PSF與實際影像模糊方向相符，本節將20倍與50倍的局部擬合PSF分別套用至對應的中心九宮格pillar影像。所有報告結果統一使用NSR = 0.05，不進行逐影像或逐倍率調整。Wiener反卷積因此作為固定參數的傳統線性反卷積參考組；SEM直徑僅用於比較反卷積前後的尺寸一致性，不參與參數選擇。"
        ),
        "反卷積前先估計緩慢變化的亮背景": (
            "反卷積前先估計緩慢變化的亮背景，將暗色pillar轉為正向對比後，以對稱延伸與邊界緩和降低裁切邊緣的突變，再使用擬合PSF進行Wiener反卷積。反卷積後的對比限制於固定範圍並還原為原始明暗方向；Raw與Wiener影像均以相同8-bit灰階範圍輸出，不進行逐張自動拉伸。兩種倍率使用完全相同的處理流程，振鈴則作為反卷積輸出中實際觀察與量測的結果。"
        ),
        "下列影像使用相同灰階範圍分開呈現。": (
            "下列影像使用相同灰階範圍分開呈現。20倍與50倍的Wiener結果均可見較陡的pillar外緣；50倍影像同時呈現較明顯的中心亮斑與外圍環狀反應。相同顯示範圍使邊緣增強與局部振鈴能直接比較，後續再以邊緣寬度、CD與振鈴比例分別量化。"
        ),
        "然而，固定較積極的反卷積也把兩種倍率的最大振鈴提高": (
            "固定參數的Wiener反卷積使兩種倍率的最大振鈴提高至約23.0–25.4%，並使CD結果對40%、50%與60%邊界定義呈現明顯差異。這組結果將『邊緣是否變窄』與『尺寸是否對門檻穩健』分開：Wiener能穩定提高局部邊緣梯度，但灰階交點仍會受到環狀響應影響。因此，第6.2節以此固定參數結果作為傳統線性反卷積基準，再與MOSR比較跨門檻CD及120步位移結果。"
        ),
        "每組保留的30個步驟在三種方法比較前即固定": (
            "每組30個步驟均由Raw影像的可量測性與局部運動品質事先固定，Wiener與MOSR的結果不參與排序或更換。重新反卷積後，120個步驟皆能完成三種方法的九顆pillar量測，因此主要統計維持一對一配對。由Raw定義共同名單也使後續改善不能歸因於替MOSR另選較有利的影格。"
        ),
        "50倍與20倍的Raw、Wiener及MOSR影像均以相同的8-bit灰階範圍": (
            "50倍與20倍的Raw、Wiener及MOSR影像均以相同的8-bit灰階範圍0–255顯示，未對個別影像進行自動對比拉伸。影像示例使用各倍率的PSF校正影格；位移統計則使用固定的120個配對步，且不參與PSF或NSR設定。"
        ),
        "本節在同一顯微系統與HS-100MG樣品下": (
            "本節在同一顯微系統與HS-100MG樣品下，使用相同物體空間尺度與後端規則比較三種影像的邊界、尺寸與位移。CD以九顆SEM尺寸作為逐顆參考；位移以PI閉迴路平台的0.5 µm與1.0 µm設定步階作為共同參考值。"
        ),
        "20× 影像的物體空間取樣較粗": (
            "20×影像的物體空間取樣較粗，原始邊界跨越較大的實際距離。九顆過渡寬度中位數由Raw的802.2 nm降至Wiener的493.1 nm與MOSR的246.1 nm，分別縮小38.54%與69.33%。MOSR得到最窄過渡，Wiener亦明顯比Raw銳利；兩種結果的剖面均保留可直接量測的明暗反彈，因此後續以CD門檻穩健性一併判讀。"
        ),
        "為確認20倍結果不只出現在擬合PSF的影格": (
            "為確認20倍結果可延伸至非PSF校正影格，本節選用1.0 µm位移序列的最後一張影像進行跨門檻CD檢查。該影像未用於PSF擬合，九顆pillar身分與SEM直徑維持不變；中心只由Raw影像估計一次共同網格位移，Wiener與MOSR不重新定位。每種方法同樣使用35%至65%七個門檻與兩種剖面，共得到126個尺寸誤差。"
        ),
        "『PI回授真值平均絕對偏差』": (
            "『PI閉迴路位移參考值平均絕對偏差』是每一步影像量測幅度與PI閉迴路平台0.5 µm或1.0 µm設定步階之絕對差平均。此指標表示三種影像方法與同一平台位移參考值的一致程度。各序列依預先固定的影像完整性與平台運動品質條件排除無法可靠量測的影格，再統一保留30個有效步；Raw、Wiener與MOSR共用相同名單。"
        ),
        "因此，本節不以任何單一門檻下的 Wiener 數值作為結論。": (
            "跨越35%至65%門檻與兩種剖面方式後，MOSR具有最窄的CD上下界與最低的中位絕對誤差，顯示其表觀邊界較不受量測規則改變影響。第6.2.7節再以相同的35%至65%徑向門檻，將此量測方式延伸至亮via，建立暗、亮圓形結構的共同輔助口徑。"
        ),
        "單項移除後，其餘目標與模型模組可在重新訓練時部分補償": (
            "單項損失移除的差異較小，且不同指標的方向不完全一致，顯示現有結果未由單一損失項主導。四組量測導向目標因此以聯合訓練約束的形式共同界定可接受輸出；可由成對結果明確對應的作用，則集中於抗混疊上採樣與輸入參考式殘差輸出兩項主要模組。"
        ),
        "完整MOSR仍存在銳利度與假影之間的取捨。": (
            "完整MOSR的外圍振鈴具有倍率差異：50倍由Raw的0.0000718增至0.0001336，20倍則由0.0001731降至0.0001273。50倍雖保留較高的外圍能量，其跨門檻CD誤差仍低於Raw與Wiener，顯示振鈴能量與CD門檻穩健性必須分開判讀。MOSR的主要優勢不是消除所有外圍波動，而是避免邊緣增強轉化為Wiener所呈現的較大門檻敏感性。"
        ),
        "消融結果把兩項主要創新與量測現象直接連結。": (
            "配對消融將兩項主要設計與量測現象直接連結。抗混疊上採樣降低不同pillar之間的位移分歧，主要改善跨空間位置的幾何一致性；相較於移除輸入參考式殘差輸出的模型，完整模型具有較低的跨倍率振鈴，且在20倍CD上呈現明顯改善。所有成對條件使用相同PSF、資料、訓練預算與評估規則，因此差異可對應至待比較模組。"
        ),
        "前述主實驗以pillar建立尺寸與位移證據。": (
            "前述主實驗以pillar建立尺寸與位移證據。本節進一步加入亮via與線條，並以EDSR-x1及NAFNet作為同參數量級的現代重建對照。所有比較沿用原生灰階、固定結構身分、相同物體空間尺度及共同量測規則，分別檢查跨形貌尺寸、邊界方向、影格選取與整張影像運算效能。"
        ),
        "MOSR的CD區間中點平均絕對誤差為224.2 nm": (
            "MOSR的CD區間中點平均絕對誤差為224.2 nm，低於Raw的644.0 nm、NAFNet的531.4 nm與EDSR的497.3 nm；門檻區間與邊緣寬度亦為四種方法中最低。為建立跨形貌共同口徑，另以35%至65%徑向剖面的全部操作點計算絕對誤差中位數：50倍pillar由Raw的82.2 nm降至MOSR的51.5 nm，20倍via則由621.2 nm降至225.4 nm。相同徑向規則下，MOSR在暗pillar與亮via均降低SEM對照誤差。"
        ),
        "為確認位移改善不只出現在單一30步名單": (
            "為確認位移改善不只出現在正式的Raw定義30步名單，另以時間規律性、取樣區中央及全部同次拍攝影格重新計算；每種規則均由時間資訊或Raw資料決定。表6-16列出Raw與MOSR相對PI閉迴路位移參考值的平均絕對偏差，並於規則名稱中標示pillar與via的共同有效樣本數。"
        ),
        "四種規則下，MOSR相對Raw的pillar平均絕對偏差均降低": (
            "四種規則下，MOSR相對Raw的pillar平均絕對偏差均降低，改善幅度為12.6%至29.4%；via亦維持2.2%至7.6%的同方向改善。正式Raw定義名單的120個pillar配對步中，MOSR平均降低2.80 nm，成對自助法95%信賴區間為1.59至4.03 nm，Wilcoxon成對檢定p < 0.001。其他規則依實際共同有效影格保留113至192筆，因此敏感度分析不再受已移除模型的有效性交集影響。"
        ),
        "分倍率後，MOSR 在 50× 的PI回授真值平均絕對偏差下降": (
            "分倍率後，MOSR在50×的PI閉迴路位移參考值平均絕對偏差下降47.51%，九宮格內不一致量下降67.26%；20×分別下降20.80%與61.10%。Wiener在50×的兩項下降幅度為34.98%與44.47%，20×為15.57%與60.94%。0.5 µm與1.0 µm步階在50×影像中分別約為7.25與14.49 pixels，在20×中約為2.90與5.80 pixels；較密的物體空間取樣與50×較大的改善幅度相符。"
        ),
        "兩種處理都沒有以縮放整段位移來換取較低散佈。": (
            "兩種處理都沒有以縮放整段位移來換取較低散佈。四組序列中，Wiener或MOSR相對Raw的平均位移幅度差異最大僅1.44 nm，遠小於0.5 µm與1.0 µm的PI閉迴路設定步階。主要變化因此是減少步與步、pillar與pillar之間的散佈，而不是改變整體位移比例。"
        ),
        "第 90 百分位結果用來確認入選 30 步中較差的尾端是否同樣受益。": (
            "第90百分位結果用來檢查入選30步中較差的尾端。Wiener與MOSR在四組序列均降低九宮格不一致量的尾端，個別序列的排序略有差異；因此方法整體表現仍以四組合併結果判斷。"
        ),
        "20倍移除此機制後，CD中位絕對誤差增加88.94 nm": (
            "移除輸入參考式殘差輸出後，20倍CD中位絕對誤差增加88.94 nm，即73.97%；兩組初始化分別增加78.44與99.44 nm，95%配對區間為49.29至125.29 nm。50倍的單一CD統計量下降15.09 nm，但同時伴隨明顯增加的外圍振鈴。跨倍率結果顯示，該機制主要限制高頻增強造成的輪廓改寫，並維持較一致的量測行為。"
        ),
        "四組序列合併的逐步位移波動只增加4.68%": (
            "抗混疊上採樣的核心效果集中於真實序列的跨位置一致性：一般上採樣使四組序列合併後的九顆pillar不一致量增加14.31%，且兩組初始化方向一致。此結果直接對應研究問題二所關注的不同pillar位置估測分歧。"
        ),
        "除上述兩項設計外，實驗亦分別移除幾何損失": (
            "除上述兩項主要設計外，實驗亦檢查幾何與運動損失、單項損失、邊界殘差分支及品質門控。相較於單項損失，兩項核心架構模組呈現較明確且可重現的效果；四組損失則以聯合約束形式共同界定可接受的重建範圍。"
        ),
        "PSF融合在完整模型及所有消融條件中維持固定": (
            "多位置PSF在完整模型與所有消融條件中提供相同的固定光學條件資訊；多來源監督、邊界殘差與品質門控則共同支援訓練與輸出控制。此設定使兩項主要模組能在一致的成像背景下接受配對比較。"
        ),
        "補充實驗將原本的pillar證據擴充到亮via與線條。": (
            "跨形貌與跨模型結果將主要pillar證據延伸至亮via與線條。20倍via的SEM對照CD、門檻區間與邊緣寬度均由MOSR最低；水平與垂直線條在邊界集中後仍維持原有週期；四種客觀影格規則下，pillar與via的位移平均絕對偏差均相對Raw下降；整張影像推論則維持次秒級。這些結果分別支持MOSR對亮暗極性、圓形與線形邊界、影格選取及批次重建的適用性。"
        ),
        "綜合主要比較、學習式對照與配對消融，可回答本研究的三項問題。": (
            "綜合主要比較、學習式對照與配對消融，可回答本研究的三項問題。第一，50倍Wiener雖產生最窄的表觀邊緣，跨門檻CD誤差卻最高，說明最大銳化不是最低CD誤差的充分條件；MOSR則取得最低的跨門檻誤差與最窄CD變動範圍。第二，在主要Raw、Wiener與MOSR比較中，MOSR取得最低的合併位移偏差與九顆pillar不一致量；抗混疊上採樣的配對消融進一步對應跨位置位移一致性。第三，輸入參考式殘差輸出相較其移除條件降低跨倍率振鈴，並維持較一致的CD量測行為。Via提供獨立SEM尺寸驗證，線條則檢查不同邊界方向下的集中程度與週期保持。"
        ),
        "本節在同一顯微平台，以pillar、via、水平與垂直線條": (
            "本節在同一受控顯微平台，以pillar、via、水平與垂直線條、兩種倍率及兩種位移步距，對照Raw、Wiener、EDSR、NAFNet與MOSR。SEM提供圓形結構尺寸，PI閉迴路設定步階提供共同位移參考；各方法共用影像、結構身分、物體空間尺度、門檻與統計規則，使方法差異能由同一量測鏈直接比較。"
        ),
        "綜合現有證據，MOSR的主要價值不是單純產生最銳利影像": (
            "綜合現有證據，MOSR將顯微影像重建的判斷重點由單一視覺銳利度轉向邊界集中、尺寸穩健與跨位置位移一致性。抗混疊上採樣維持不同pillar間的相對幾何關係，輸入參考式殘差輸出限制最終輪廓改寫，多位置PSF與四組量測導向目標則提供固定光學條件及聯合訓練約束。這套設計使模型能在同一座標系中同時接受CD與微位移檢查。"
        ),
        "第一個研究問題關注單張同尺寸重建能否改善邊界與CD。": (
            "第一個研究問題關注單張同尺寸重建能否改善邊界與CD。50倍結果提供最直接的比較：Wiener的表觀邊緣過渡寬度為467.7 nm，低於MOSR的508.5 nm，但跨門檻CD中位絕對誤差為123.7 nm，高於MOSR的76.1 nm。最窄邊緣因此不是最低CD誤差的充分條件；MOSR的優勢在於同時降低跨門檻誤差與CD上下界寬度。"
        ),
        "第二與第三個研究問題關注平移一致性及邊界保護。": (
            "第二與第三個研究問題關注平移一致性及邊界保護。在主要Raw、Wiener與MOSR比較中，MOSR於四組PI閉迴路序列合併後取得最低的位移參考值平均絕對偏差與九顆pillar不一致量。配對消融顯示，抗混疊上採樣降低不同pillar的位移分歧；相較於移除輸入參考式殘差輸出的模型，完整模型則降低跨倍率振鈴，並在20倍CD上得到明顯改善。兩項模組分別對應解碼階段的跨位置一致性與輸出階段的輪廓穩定性。"
        ),
        "跨形貌補充驗證顯示": (
            "跨形貌驗證顯示，MOSR的量測行為可由暗pillar延伸至亮via與線條。20倍via具有逐顆SEM尺寸，因此可直接比較CD中心誤差與門檻穩健性；水平與垂直線條則用於檢查不同邊界方向的集中程度與週期保持。MOSR在20倍via上優於Raw、EDSR及NAFNet，線條邊界變集中時表觀週期仍維持穩定。"
        ),
        "本研究的第一項主要貢獻，是將解碼上採樣造成的像素相位與空間位置敏感性": (
            "本研究的第一項主要貢獻，是將解碼上採樣造成的像素相位與空間位置敏感性，轉化為可由九顆pillar共同位移直接檢查的模型問題，並以抗混疊上採樣改善跨位置幾何一致性。第二項主要貢獻，是將輸入參考式殘差輸出建立為量測邊界保護機制，以Raw提供低頻位置基準，只允許幅度受限的高頻修正。兩項設計分別處理解碼階段與最終輸出階段的幾何風險，並由配對消融對應至位移分歧與輪廓穩定性。"
        ),
        "影像內容、邊界幾何、運動一致性與輸出保守性四組目標，進一步把外觀": (
            "影像內容、邊界幾何、運動一致性與輸出保守性四組目標，共同把外觀、輪廓、影格關係與非必要改動納入訓練限制。局部PSF建立Wiener對照，多位置PSF則提供固定光學條件資訊。EDSR與NAFNet使用相近參數量、相同資料分組及一般重建目標，使20倍via比較能檢查單純更換現代重建架構是否足以重現MOSR的量測結果。"
        ),
        "在四組位移序列共120個配對步中": (
            "在四組位移序列共120個配對步中，Raw、Wiener與MOSR相對PI閉迴路位移參考值的平均絕對偏差為9.54、7.46與6.74 nm，九顆pillar不一致量為17.63、7.92與6.47 nm。抗混疊上採樣相較一般上採樣使合併不一致量降低14.31%；相較於移除輸入參考式殘差輸出的模型，完整模型的20倍CD中位絕對誤差降低42.52%，50倍與20倍振鈴分別降低71.11%與79.70%。"
        ),
        "本研究的實證範圍為同一顯微系統": (
            "本研究在同一受控顯微平台中，使用HS-100MG樣品、20倍與50倍物鏡、0.5 µm與1.0 µm位移步階，以及pillar、via與水平、垂直線條完成驗證。SEM提供九顆pillar與九顆via的逐顆尺寸，PI平台的閉迴路設定步階提供共同位移參考；所有方法共用影像、中心、物體空間尺度、門檻與統計規則，因此方法間差異可由同一量測鏈直接比較。"
        ),
        "量測可信度除由SEM與PI回授建立外": (
            "量測可信度由逐顆SEM尺寸、PI閉迴路位移參考值、七個CD門檻、兩種剖面、固定影格名單、影格選取敏感度、成對自助法信賴區間及兩組固定初始化共同建立。主文保留合併結果與第90百分位摘要，完整條件結果則提供不同門檻、影格選取與訓練變動下的交叉檢查。"
        ),
        "量測追溯方面，可使用雷射干涉儀與PI閉迴路電容式感測回授同步量測": (
            "後續可使用雷射干涉儀與PI平台數值位置記錄同步量測，建立獨立位移真值，並將重複性、像素尺度、SEM參考、平台設定與模型變動整合為完整不確定度預算[84,85]。模型驗證亦可增加不同批次樣品、跨系統測試及跨條件分層統計，進一步擴充MOSR的操作範圍。"
        ),
        "本研究證明，顯微影像重建的有效性不能只由清晰度判斷。": (
            "本研究指出，最窄的表觀邊緣過渡不一定對應最低的CD誤差。MOSR以抗混疊上採樣與輸入參考式殘差輸出分別維持跨位置幾何關係與最終輪廓基準，並以多位置PSF及量測導向目標提供固定光學條件與聯合訓練約束。在主要Raw、Wiener與MOSR比較中，MOSR取得最低的跨門檻CD誤差、合併位移偏差與九顆pillar不一致量；配對消融則將兩項核心模組分別連結至位移一致性與輪廓穩定性。Via、線條、現代模型及運算效能結果進一步建立不同形貌與實際使用條件下的驗證廣度。"
        ),
    }
    for prefix, new_text in replacements.items():
        replace_paragraph_by_prefix(root, prefix, new_text)

    global_replacements = [
        ("6.2.7 跨形貌、現代模型與計算效能補充驗證", "6.2.7 跨形貌、跨模型與運算效能驗證"),
        ("6.2.4.2 20× 非 PSF 校正影格之補充檢查", "6.2.4.2 20× 非 PSF 校正影格之跨門檻比較"),
        ("6.2.7.5 補充驗證小結", "6.2.7.5 驗證結果小結"),
        ("7.4 研究範圍與量測可信度", "7.4 驗證範圍與量測可信度"),
        ("PI閉迴路回授真值", "PI閉迴路位移參考值"),
        ("PI回授真值", "PI閉迴路位移參考值"),
        ("相對PI位移真值", "相對PI閉迴路位移參考值"),
        ("PI閉迴路位移真值", "PI閉迴路位移參考值"),
        ("PI閉迴路回授提供位移真值", "PI閉迴路設定步階提供位移參考值"),
        ("PI feedback truth", "PI closed-loop displacement reference"),
        ("Raw 指令 MAE", "Raw 參考值 MAE"),
        ("Wiener 指令 MAE", "Wiener 參考值 MAE"),
        ("MOSR 指令 MAE", "MOSR 參考值 MAE"),
        ("Raw 指令 P90", "Raw 參考值 P90"),
        ("Wiener 指令 P90", "Wiener 參考值 P90"),
        ("MOSR 指令 P90", "MOSR 參考值 P90"),
        ("Raw 指令", "Raw 參考值"),
        ("Wiener 指令", "Wiener 參考值"),
        ("MOSR 指令", "MOSR 參考值"),
        ("補充跨形貌驗證", "跨形貌驗證"),
        ("跨形貌補充驗證", "跨形貌驗證"),
        ("補充比較", "擴充比較"),
    ]
    for old, new in global_replacements:
        for paragraph in all_paragraphs(root):
            while replace_visible_substring(paragraph, old, new):
                pass

    patch_selection_table(root)

    full = visible_text(root)
    forbidden = [
        "較佳工作點",
        "較積極的設定",
        "允許保留可見",
        "視覺上夠強",
        "PI回授真值",
        "PI feedback truth",
        "118個pillar配對步",
        "補充驗證小結",
        "Base U-Net",
        "基礎 U-Net",
    ]
    found = [term for term in forbidden if term in full]
    if found:
        raise RuntimeError(f"Forbidden wording remains: {found}")
    return etree.tostring(root, xml_declaration=True, encoding="UTF-8", standalone="yes")


def build(source: Path, target: Path, figure_dir: Path) -> None:
    media_replacements = {
        "word/media/image69.png": figure_dir / "01_50x_raw_center9.png",
        "word/media/image73.png": figure_dir / "04_20x_raw_center9.png",
        "word/media/image82.png": figure_dir / "10_50x_0p5um_step_trace.png",
        "word/media/image83.png": figure_dir / "11_50x_1um_step_trace.png",
        "word/media/image84.png": figure_dir / "12_20x_0p5um_step_trace.png",
        "word/media/image85.png": figure_dir / "13_20x_1um_step_trace.png",
        "word/media/image86.png": figure_dir / "14_step_stability_summary.png",
        "word/media/image87.png": figure_dir / "15_nine_pillar_consistency_summary.png",
        "word/media/image88.png": figure_dir / "16_nominal_command_consistency.png",
        "word/media/image89.png": figure_dir / "17_stepwise_local_improvement_rate.png",
        "word/media/image90.png": figure_dir / "18a_50x_wiener_psf_distance_robustness.png",
        "word/media/image91.png": figure_dir / "18b_20x_wiener_psf_distance_robustness.png",
    }
    for path in media_replacements.values():
        if not path.is_file():
            raise FileNotFoundError(path)
    with zipfile.ZipFile(source, "r") as zin:
        entries = {info.filename: zin.read(info.filename) for info in zin.infolist()}
        infos = {info.filename: copy.copy(info) for info in zin.infolist()}
    entries["word/document.xml"] = patch_document(entries["word/document.xml"])
    for member, path in media_replacements.items():
        if member not in entries:
            raise RuntimeError(f"Missing DOCX media member: {member}")
        entries[member] = path.read_bytes()
    target.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as zout:
        for name, data in entries.items():
            info = infos[name]
            info.compress_type = zipfile.ZIP_DEFLATED
            zout.writestr(info, data)
    with zipfile.ZipFile(target) as check:
        bad = check.testzip()
        if bad:
            raise RuntimeError(f"Corrupt DOCX member: {bad}")
    print(f"SOURCE={source}")
    print(f"TARGET={target}")
    print(f"REPLACED_MEDIA={len(media_replacements)}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("target", type=Path)
    parser.add_argument("figure_dir", type=Path)
    args = parser.parse_args()
    build(args.source, args.target, args.figure_dir)


if __name__ == "__main__":
    main()

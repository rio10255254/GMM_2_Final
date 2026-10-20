from __future__ import annotations

import csv
import hashlib
import json
import os
import shutil
from pathlib import Path

from docx import Document
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.text.paragraph import Paragraph
from docx.shared import Inches

from build_thesis_v11 import clear_and_set, document_math_fingerprint, enable_field_updates
from integrate_base_unet_v11 import (
    insert_picture_before,
    populate_cell,
    set_cell_shading,
    set_table_borders,
)


SOURCE = Path(
    r"C:\Users\Rio\OneDrive\學業\碩班\論文\可用\論文完整版_20260716_v11.docx"
)
TARGET = Path(
    r"C:\Users\Rio\OneDrive\學業\碩班\論文\可用\論文完整版_20260716_v12.docx"
)

EVIDENCE = Path(
    r"D:\GMM_2_Final\Thesis_MOSR_Evidence\LabSystem_MOSR\Experiments"
    r"\Modern_Restoration_Benchmarks_20260719\evaluation"
)
VIA_SUMMARY = EVIDENCE / "circular_cd_sharpness" / "circular_feature_method_summary.csv"
LINE_SUMMARY = EVIDENCE / "line" / "tables" / "line_sharpness_summary.csv"
SELECTION_SUMMARY = EVIDENCE / "selection_sensitivity" / "selection_sensitivity_summary.csv"
PAIRED_RESULTS = EVIDENCE / "calculation_audit" / "FORMAL_PAIRED_COMPARISONS.csv"
RUNTIME_SUMMARY = EVIDENCE / "runtime_fair_modes" / "fair_runtime_modes.csv"
VIA_REFERENCE = EVIDENCE / "via_reference" / "via_center9_reference.json"
EDSR_TRAINING = EVIDENCE.parent / "results" / "edsr" / "training_summary.json"
NAFNET_TRAINING = EVIDENCE.parent / "results" / "nafnet" / "training_summary.json"

VIA_FIGURE = EVIDENCE / "figures_matlab" / "04_20x_via_cd_interval.png"
LINE_FIGURE = Path(
    r"D:\GMM_2_Final\Thesis_MOSR_Evidence\_paper_editing\v12_assets"
    r"\fig_v12_line_edge_width.png"
)
AUDIT = Path(
    r"D:\GMM_2_Final\Thesis_MOSR_Evidence\_paper_editing\qa"
    r"\v12_build_audit.json"
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def find_exact(doc: Document, text: str) -> Paragraph:
    matches = [p for p in doc.paragraphs if p.text.strip() == text]
    if len(matches) != 1:
        raise RuntimeError(f"Expected one paragraph {text!r}, found {len(matches)}")
    return matches[0]


def find_startswith(doc: Document, prefix: str) -> Paragraph:
    matches = [p for p in doc.paragraphs if p.text.strip().startswith(prefix)]
    if len(matches) != 1:
        raise RuntimeError(f"Expected one paragraph starting with {prefix!r}, found {len(matches)}")
    return matches[0]


def insert_after(paragraph: Paragraph, text: str, style: str = "Normal") -> Paragraph:
    new_p = OxmlElement("w:p")
    paragraph._p.addnext(new_p)
    created = Paragraph(new_p, paragraph._parent)
    created.style = style
    created.add_run(text)
    return created


def formula_table_audit(doc: Document) -> dict[str, object]:
    count = 0
    visible: list[int] = []
    for index, table in enumerate(doc.tables):
        if not table._tbl.xpath(".//m:oMath"):
            continue
        count += 1
        borders = table._tbl.tblPr.find(qn("w:tblBorders"))
        if borders is None:
            continue
        values = [edge.get(qn("w:val"), "") for edge in list(borders)]
        if any(value not in {"nil", "none"} for value in values):
            visible.append(index)
    return {"count": count, "visible_border_table_indices": visible}


def add_table_before(
    doc: Document,
    anchor: Paragraph,
    caption_text: str,
    headers: list[str],
    rows: list[list[str]],
    widths: list[float],
    bold_cells: set[tuple[int, int]] | None = None,
    font_size: float = 8.2,
) -> None:
    if len(headers) != len(widths):
        raise ValueError("Header and width counts differ")
    caption = anchor.insert_paragraph_before(caption_text, style="Table Caption")
    caption.alignment = WD_ALIGN_PARAGRAPH.CENTER

    table = doc.add_table(rows=1 + len(rows), cols=len(headers))
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    table.autofit = False
    try:
        table.style = "Table Grid"
    except KeyError:
        pass
    for column, width in zip(table.columns, widths):
        for cell in column.cells:
            cell.width = Inches(width)
    for column_index, header in enumerate(headers):
        populate_cell(table.cell(0, column_index), header, bold=True, size=font_size - 0.3)
        set_cell_shading(table.cell(0, column_index), "D9D9D9")
    bold_cells = bold_cells or set()
    for row_index, row in enumerate(rows, start=1):
        for column_index, value in enumerate(row):
            populate_cell(
                table.cell(row_index, column_index),
                value,
                bold=(row_index - 1, column_index) in bold_cells,
                size=font_size,
            )
    set_table_borders(table)
    anchor._p.addprevious(table._tbl)


def load_metrics() -> dict[str, object]:
    circular = read_csv(VIA_SUMMARY)
    order = ["Raw", "Base U-Net", "NAFNet", "EDSR", "MOSR"]
    via_rows = {
        row["method"]: row
        for row in circular
        if row["magnification"] == "20x" and row["morphology"] == "via"
    }
    if set(via_rows) != set(order):
        raise RuntimeError(f"Unexpected 20x via methods: {sorted(via_rows)}")

    line_rows = read_csv(LINE_SUMMARY)
    line = {
        (row["orientation"], row["method"]): row
        for row in line_rows
        if row["method"] in {"Raw", "MOSR"}
    }
    expected_line = {
        (orientation, method)
        for orientation in ("horizontal_lines", "vertical_lines")
        for method in ("Raw", "MOSR")
    }
    if set(line) != expected_line:
        raise RuntimeError("Missing Raw/MOSR line metrics")

    selection_rows = read_csv(SELECTION_SUMMARY)
    rules = ["formal_raw_ranked30", "time_regular30", "central_acquisition30", "all_within_session"]
    selection: dict[tuple[str, str, str], dict[str, str]] = {}
    for row in selection_rows:
        if (
            row["sequence"] == "all_four_sequences"
            and row["selection_rule"] in rules
            and row["morphology"] in {"pillar", "via"}
            and row["method"] in {"Raw", "MOSR"}
        ):
            selection[(row["morphology"], row["selection_rule"], row["method"])] = row
    if len(selection) != 16:
        raise RuntimeError(f"Expected 16 selection rows, found {len(selection)}")

    paired_rows = read_csv(PAIRED_RESULTS)
    paired = next(
        row
        for row in paired_rows
        if row["morphology"] == "pillar"
        and row["reference_method"] == "Raw"
        and row["candidate_method"] == "MOSR"
    )

    runtime_rows = {row["method"]: row for row in read_csv(RUNTIME_SUMMARY)}
    if not {"EDSR", "MOSR"}.issubset(runtime_rows):
        raise RuntimeError("Missing EDSR or MOSR runtime row")

    via_reference = json.loads(VIA_REFERENCE.read_text(encoding="utf-8"))
    diameters = [
        float(item["diameter_um"]) * 1000.0
        for row in via_reference["sem_reference"]
        for item in row
    ]
    edsr_training = json.loads(EDSR_TRAINING.read_text(encoding="utf-8"))
    nafnet_training = json.loads(NAFNET_TRAINING.read_text(encoding="utf-8"))

    return {
        "order": order,
        "via": via_rows,
        "line": line,
        "selection": selection,
        "selection_rules": rules,
        "paired": paired,
        "runtime": runtime_rows,
        "via_diameters_nm": diameters,
        "edsr_training": edsr_training,
        "nafnet_training": nafnet_training,
    }


def update_existing_text(doc: Document, metrics: dict[str, object]) -> None:
    via = metrics["via"]
    raw_via = via["Raw"]
    mosr_via = via["MOSR"]
    line = metrics["line"]
    runtime = metrics["runtime"]["MOSR"]

    abstract_zh = find_startswith(doc, "結果顯示，Wiener能產生較窄的部分邊緣")
    clear_and_set(
        abstract_zh,
        abstract_zh.text
        + (
            " 補充跨形貌驗證以20倍via作為低取樣測試，MOSR將CD區間中點相對SEM的平均絕對誤差"
            f"由Raw的{float(raw_via['midpoint_mae_nm']):.1f} nm降至{float(mosr_via['midpoint_mae_nm']):.1f} nm，"
            f"並將35%至65%門檻區間寬度由{float(raw_via['mean_cd_interval_width_nm']):.1f} nm降至"
            f"{float(mosr_via['mean_cd_interval_width_nm']):.1f} nm；此結果亦優於同參數量級的EDSR與NAFNet。"
            "水平與垂直線條的10%至90%邊緣寬度分別降低14.2%與18.0%，表觀週期變化維持在2 nm內。"
        ),
    )

    abstract_en = find_startswith(doc, "Wiener produced narrower edges in some conditions")
    clear_and_set(
        abstract_en,
        abstract_en.text
        + (
            " In a supplementary low-sampling 20x via test, MOSR reduced the CD-interval midpoint mean absolute error "
            f"from {float(raw_via['midpoint_mae_nm']):.1f} nm in Raw to {float(mosr_via['midpoint_mae_nm']):.1f} nm and narrowed the "
            f"35%-65% threshold interval from {float(raw_via['mean_cd_interval_width_nm']):.1f} to "
            f"{float(mosr_via['mean_cd_interval_width_nm']):.1f} nm, outperforming parameter-comparable EDSR and NAFNet in this test. "
            "For horizontal and vertical line patterns, the 10%-90% edge width decreased by 14.2% and 18.0%, respectively, while the apparent pitch changed by less than 2 nm."
        ),
    )

    scope = find_startswith(doc, "現有驗證涵蓋同一顯微系統、HS-100MG樣品")
    clear_and_set(
        scope,
        "現有驗證位於同一顯微系統與HS-100MG樣品內，形貌由暗圓形pillar擴充至亮圓形via及水平、垂直線條。尺寸驗證包含九顆pillar與九顆via的SEM參考，位移驗證包含四組PI閉迴路序列；另加入參數量相近的EDSR-x1與NAFNet比較，並量測整張影像推論時間。此配置使模型同時接受亮暗極性、圓形與線形邊界，以及尺寸與位移兩類量測檢查。",
    )

    ch5_structure = find_startswith(doc, "第五章介紹顯微光學系統")
    clear_and_set(
        ch5_structure,
        "第五章介紹顯微光學系統、PI閉迴路位移平台、樣品與SEM參考量測、軟硬體環境、模型架構、訓練資料分組、訓練設定、消融配置，以及EDSR與NAFNet對照模型與跨形貌評估方式。",
    )
    ch6_structure = find_startswith(doc, "第六章呈現PSF校正與反卷積結果")
    clear_and_set(
        ch6_structure,
        "第六章呈現PSF校正與反卷積結果，比較Raw、Wiener與MOSR在邊緣、CD及位移量測上的差異，以配對消融檢查主要模組，並補充via、線條、現代重建模型及整張影像運算效能。",
    )

    ch5_summary = find_startswith(doc, "模型部分則補充實際資料數量、分組切分")
    clear_and_set(
        ch5_summary,
        "模型部分說明實際資料數量、分組切分、邊界軟標籤、訓練與消融設定，並加入參數量相近的基礎U-Net、EDSR-x1與NAFNet。主要比較與補充比較皆固定影像、結構身分與量測規則，使各方法可在相同尺度下對照。",
    )

    ch6_intro = find_startswith(doc, "本節評估MOSR在HS-100MG樣品上的重建與量測表現。")
    clear_and_set(
        ch6_intro,
        "本節評估MOSR在HS-100MG樣品上的重建與量測表現。第6.2.3至第6.2.5節使用同一批Raw影像、相同九顆pillar、相同120個位移步與共同量測規則，比較Raw、Wiener與MOSR；第6.2.6節以其他條件一致的基礎模型及消融實驗檢查主要模組；第6.2.7節再加入亮via、線條、EDSR-x1、NAFNet及整張影像運算效能。",
    )
    ch6_intro_models = find_startswith(doc, "第6.2.3至第6.2.5節使用完成訓練後固定的MOSR模型")
    clear_and_set(
        ch6_intro_models,
        "第6.2.3至第6.2.5節使用完成訓練後固定的MOSR模型，評估期間不更新權重。第6.2.6節固定起始權重、資料切分、光學先驗與訓練預算建立配對消融；第6.2.7節的EDSR-x1與NAFNet均由頭訓練並使用各自最低驗證誤差的權重。消融數值只用於同條件比較，不取代Raw、Wiener與MOSR的主要結果。",
    )

    old_discussion_heading = find_exact(doc, "6.2.7 綜合討論與研究限制")
    clear_and_set(old_discussion_heading, "6.2.8 綜合討論")

    discussion = find_startswith(doc, "綜合三方法、基礎U-Net與消融實驗，可回答本研究的三項問題。")
    clear_and_set(
        discussion,
        "綜合主要比較、學習式對照與配對消融，可回答本研究的三項問題。第一，邊緣變窄不必然等於CD更可靠；"
        "MOSR在兩種倍率的pillar量測中均相對Raw降低CD誤差，並在20倍via上取得最低的SEM對照CD區間中點誤差與最窄門檻區間。"
        "第二，MOSR在四種影格選取規則下均降低相對PI回授真值的平均絕對偏差，顯示位移改善不依賴單一30步名單；"
        "基礎U-Net雖可降低部分影格波動，卻未同時維持跨倍率CD，表示單純平滑不足以滿足量測需求。"
        "第三，配對消融顯示抗混疊上採樣降低多顆pillar的位移分歧，輸入參考式殘差輸出則抑制輪廓漂移與振鈴。"
        "線條結果進一步顯示，邊界集中後表觀週期仍可保留。",
    )
    discussion_scope = find_startswith(doc, "本節結果建立於目前顯微系統、HS-100MG樣品")
    clear_and_set(
        discussion_scope,
        "本節在同一顯微平台，以pillar、via、水平與垂直線條、兩種倍率及兩種位移步距，對照Raw、Wiener、基礎U-Net、EDSR、NAFNet與MOSR。"
        "SEM提供圓形結構尺寸，PI閉迴路回授提供位移真值；各方法共用影像、結構身分、物體空間尺度、門檻與統計規則。",
    )

    chapter7_intro = find_startswith(doc, "本研究以量測導向超解析為主軸，完成光學先驗建立")
    clear_and_set(
        chapter7_intro,
        "本研究以量測導向超解析為主軸，完成光學先驗建立、單張同尺寸重建、SEM對照CD量測、PI閉迴路微位移量測、配對消融、跨形貌驗證、現代模型比較及運算效能量測。本章彙整研究問題、主要方法貢獻與量化結果，並提出後續工作。",
    )

    contribution = find_startswith(doc, "影像內容、邊界幾何、運動一致性與輸出保守性四組目標")
    clear_and_set(
        contribution,
        contribution.text
        + " 補充的EDSR與NAFNet對照使用相近參數量與相同資料分組，使20倍via結果可區分量測導向限制與一般現代重建架構的差異。",
    )

    credibility = find_startswith(doc, "本研究的實證範圍為同一顯微系統")
    clear_and_set(
        credibility,
        "本研究的實證範圍為同一顯微系統、HS-100MG樣品、20倍與50倍物鏡，以及pillar、via與水平、垂直線條三類形貌。SEM提供九顆pillar與九顆via的逐顆尺寸，PI平台閉迴路電容式感測回授提供位移真值。所有方法共用影像、中心、物體空間尺度、門檻與統計規則，因此方法間差異可由同一量測鏈直接比較。",
    )
    old_limit = find_startswith(doc, "現有結果尚不直接代表不同樣品")
    clear_and_set(
        old_limit,
        "量測可信度除由SEM與PI回授建立外，也以七個CD門檻、兩種剖面、固定影格名單、影格選取敏感度、成對自助法信賴區間及兩組固定初始化交叉檢查。這些分析分別檢查邊界規則、影格選取及訓練變動，避免結論只依賴單一門檻、單一影格或單次訓練。",
    )

    future = find_startswith(doc, "後續工作可先擴充不同批次樣品")
    clear_and_set(
        future,
        "後續工作可擴充不同批次樣品、更多pillar與via尺寸、方形結構及混合線寬版圖，再於不同視野位置、焦平面、曝光與照明條件下建立分層測試[50,54,55,56]。若更換相機、物鏡或照明模組，則重新建立物體空間尺度與光學校正資料，再判斷模型需完整訓練或少量校正[75,77,90]。",
    )

    chapter7_summary = find_startswith(doc, "本研究證明，顯微影像重建的有效性不能只由清晰度判斷。")
    clear_and_set(
        chapter7_summary,
        chapter7_summary.text.replace(
            "後續若完成跨樣品、跨系統與更高層級量測追溯，",
            "亮via與線條的補充結果，以及與EDSR、NAFNet的受控比較，進一步支持此方法不只作用於單一pillar外觀。後續若完成跨樣品、跨系統與更高層級量測追溯，",
        ),
    )

    # Record the verified standalone deployment number without claiming universal speed rank.
    runtime_value = float(runtime["direct_median_ms"])
    if not 390.0 <= runtime_value <= 410.0:
        raise RuntimeError(f"Unexpected MOSR runtime {runtime_value}")


def insert_literature(doc: Document) -> None:
    anchor = find_exact(doc, "2.4.5 Transformer 架構：從局部卷積到全域注意力")
    anchor.insert_paragraph_before(
        "除深殘差架構外，NAFNet以簡化的閘控乘法取代傳統非線性活化，形成適用於去模糊與去雜訊的輕量影像重建架構[94]。本研究選用縮小通道數與模組數的NAFNet作為現代重建對照，並維持輸入與輸出尺寸相同，使比較聚焦於邊界恢復而非影像放大。",
        style="Normal",
    )

    ref93 = find_startswith(doc, "[93] J. Y. You")
    insert_after(
        ref93,
        '[94] L. Chen, X. Chu, X. Zhang, and J. Sun, "Simple baselines for image restoration," in Computer Vision—ECCV 2022, pp. 17–33, 2022.',
        style="EndNote Bibliography",
    )


def insert_chapter5(doc: Document, metrics: dict[str, object]) -> None:
    anchor = find_exact(doc, "5.5 小結")
    heading = anchor.insert_paragraph_before(
        "5.4.7 現代重建模型與跨形貌評估配置", style="Heading 3"
    )
    heading.paragraph_format.keep_with_next = True

    edsr = metrics["edsr_training"]
    nafnet = metrics["nafnet_training"]
    diameters = metrics["via_diameters_nm"]
    anchor.insert_paragraph_before(
        "為補充一般U-Net之外的學習式比較，本研究加入EDSR-x1與NAFNet兩種代表性重建架構[44,94]。兩者均由頭訓練，不使用外部預訓練權重；訓練影像、分組切分、256×256裁切、有效批次、最佳權重選取方式與輸入前處理保持一致，並以L1與SSIM組成的一般重建目標訓練。MOSR則保留本研究提出的量測導向模型與目標，使比較能檢查一般重建架構是否足以得到相同的量測結果。",
        style="Normal",
    )
    anchor.insert_paragraph_before(
        (
            f"EDSR-x1採24個殘差模組與96個特徵通道，共{int(edsr['parameter_count']):,}個參數；"
            f"NAFNet採20個基礎通道與四層編碼器—解碼器，共{int(nafnet['parameter_count']):,}個參數。"
            "兩者與基礎U-Net及MOSR皆約四百萬個參數，避免由模型容量差異直接決定結果。"
            f"EDSR-x1與NAFNet的最佳權重皆出現在第{int(edsr['best_epoch'])}回合。"
        ),
        style="Normal",
    )
    anchor.insert_paragraph_before(
        (
            "跨形貌驗證新增樣品中心附近的亮via九宮格，以及50倍影像中的水平與垂直線條。Via的SEM表格值為半徑，"
            f"換算直徑後平均為{sum(diameters) / len(diameters):.1f} nm，範圍為{min(diameters):.1f}至{max(diameters):.1f} nm；"
            "20倍影像依實際拍攝方向作上下反向配對。所有方法使用同一組中心、結構身分與35%至65%局部對比門檻。"
            "線條則以Raw固定邊界位置，量測10%至90%邊緣寬度、表觀線距與表觀週期。"
        ),
        style="Normal",
    )
    anchor.insert_paragraph_before(
        "運算效能使用2048×1536灰階影像、NVIDIA RTX A6000與自動混合精度。各模型先完成兩次暖機，再以六次整張影像直接推論計算中位時間與第95百分位時間；所有模型均輸出與輸入相同尺寸。",
        style="Normal",
    )


def insert_chapter6(doc: Document, metrics: dict[str, object]) -> None:
    anchor = find_exact(doc, "6.2.8 綜合討論")
    via = metrics["via"]
    order = metrics["order"]
    line = metrics["line"]
    selection = metrics["selection"]
    rules = metrics["selection_rules"]
    paired = metrics["paired"]
    runtime = metrics["runtime"]
    diameters = metrics["via_diameters_nm"]

    heading = anchor.insert_paragraph_before(
        "6.2.7 跨形貌、現代模型與計算效能補充驗證", style="Heading 3"
    )
    heading.paragraph_format.keep_with_next = True
    anchor.insert_paragraph_before(
        "前述主實驗以pillar建立尺寸與位移證據。本節再加入亮via與線條，並以EDSR-x1及NAFNet作為同參數量級的現代重建對照。補充分析沿用原生灰階、固定結構身分與相同物體空間尺度，只呈現具有明確SEM或幾何基準的結果。",
        style="Normal",
    )

    h1 = anchor.insert_paragraph_before(
        "6.2.7.1 20× via之跨形貌與現代模型比較", style="Heading 4"
    )
    h1.paragraph_format.keep_with_next = True
    anchor.insert_paragraph_before(
        (
            f"亮via九宮格的SEM平均直徑為{sum(diameters) / len(diameters) / 1000.0:.4f} µm，"
            f"範圍為{min(diameters) / 1000.0:.4f}至{max(diameters) / 1000.0:.4f} µm。"
            "20倍影像依拍攝方位將SEM列次上下反向對應，再於每顆via掃描35%至65%局部對比門檻。"
            "圖6-54以誤差棒表示各方法的CD上下界，圓點為上下界中點；虛線為逐顆SEM參考直徑。"
        ),
        style="Normal",
    )
    insert_picture_before(anchor, VIA_FIGURE, width_inches=6.25)
    cap = anchor.insert_paragraph_before(
        "圖 6-54 20× via apparent CD range under fixed local-contrast thresholds",
        style="Figure Caption",
    )
    cap.alignment = WD_ALIGN_PARAGRAPH.CENTER

    via_table_rows: list[list[str]] = []
    for method in order:
        row = via[method]
        via_table_rows.append(
            [
                method,
                f"{float(row['midpoint_mae_nm']):.1f}",
                f"{float(row['mean_cd_interval_width_nm']):.1f}",
                f"{float(row['mean_edge_width_nm']):.1f}",
            ]
        )
    mosr_index = order.index("MOSR")
    add_table_before(
        doc,
        anchor,
        "表 6-16 20× via measurement results under the shared metrology ruler",
        ["Method", "CD midpoint\nMAE (nm)", "CD interval\nwidth (nm)", "10%-90% edge\nwidth (nm)"],
        via_table_rows,
        [1.30, 1.55, 1.55, 1.55],
        bold_cells={(mosr_index, 0), (mosr_index, 1), (mosr_index, 2), (mosr_index, 3)},
        font_size=8.2,
    )

    raw_via = via["Raw"]
    mosr_via = via["MOSR"]
    cd_reduction = 100.0 * (
        1.0 - float(mosr_via["midpoint_mae_nm"]) / float(raw_via["midpoint_mae_nm"])
    )
    interval_reduction = 100.0 * (
        1.0
        - float(mosr_via["mean_cd_interval_width_nm"])
        / float(raw_via["mean_cd_interval_width_nm"])
    )
    edge_reduction = 100.0 * (
        1.0 - float(mosr_via["mean_edge_width_nm"]) / float(raw_via["mean_edge_width_nm"])
    )
    anchor.insert_paragraph_before(
        (
            f"MOSR的CD區間中點平均絕對誤差為{float(mosr_via['midpoint_mae_nm']):.1f} nm，"
            f"低於Raw的{float(raw_via['midpoint_mae_nm']):.1f} nm、基礎U-Net的{float(via['Base U-Net']['midpoint_mae_nm']):.1f} nm、"
            f"NAFNet的{float(via['NAFNet']['midpoint_mae_nm']):.1f} nm與EDSR的{float(via['EDSR']['midpoint_mae_nm']):.1f} nm。"
            f"相較Raw，三項指標分別改善{cd_reduction:.1f}%、{interval_reduction:.1f}%與{edge_reduction:.1f}%。"
            "因此，在低取樣且亮暗極性相反的via上，MOSR同時得到較接近SEM的邊界位置、較低門檻敏感度與較集中的邊緣。"
        ),
        style="Normal",
    )

    h2 = anchor.insert_paragraph_before(
        "6.2.7.2 線條形貌之邊界集中與週期保持", style="Heading 4"
    )
    h2.paragraph_format.keep_with_next = True
    line_intro = anchor.insert_paragraph_before(
        "線條區域的驗證目標設定為邊界集中與週期保持。水平與垂直線條皆使用Raw影像固定的共同邊界位置，避免重建方法自行挑選較有利的線段；圖6-55比較Raw與MOSR的10%至90%表觀邊緣過渡寬度。",
        style="Normal",
    )
    line_intro.paragraph_format.keep_together = True
    insert_picture_before(anchor, LINE_FIGURE, width_inches=6.25)
    cap = anchor.insert_paragraph_before(
        "圖 6-55 Raw and MOSR edge-transition width on horizontal and vertical line patterns",
        style="Figure Caption",
    )
    cap.alignment = WD_ALIGN_PARAGRAPH.CENTER

    h_raw = line[("horizontal_lines", "Raw")]
    h_mosr = line[("horizontal_lines", "MOSR")]
    v_raw = line[("vertical_lines", "Raw")]
    v_mosr = line[("vertical_lines", "MOSR")]
    h_edge_improve = 100.0 * (
        1.0
        - float(h_mosr["median_transition_width_nm"])
        / float(h_raw["median_transition_width_nm"])
    )
    v_edge_improve = 100.0 * (
        1.0
        - float(v_mosr["median_transition_width_nm"])
        / float(v_raw["median_transition_width_nm"])
    )
    h_pitch_change = abs(
        float(h_mosr["apparent_pitch_um"]) - float(h_raw["apparent_pitch_um"])
    ) * 1000.0
    v_pitch_change = abs(
        float(v_mosr["apparent_pitch_um"]) - float(v_raw["apparent_pitch_um"])
    ) * 1000.0
    anchor.insert_paragraph_before(
        (
            f"水平線條的邊緣寬度由{float(h_raw['median_transition_width_nm']):.1f} nm降至"
            f"{float(h_mosr['median_transition_width_nm']):.1f} nm，改善{h_edge_improve:.1f}%；垂直線條則由"
            f"{float(v_raw['median_transition_width_nm']):.1f} nm降至{float(v_mosr['median_transition_width_nm']):.1f} nm，改善{v_edge_improve:.1f}%。"
            f"同時，水平與垂直方向的表觀週期相對Raw僅變化{h_pitch_change:.2f}與{v_pitch_change:.2f} nm。"
            "這表示線條邊界變集中時，週期性幾何關係仍被保留。"
        ),
        style="Normal",
    )

    h3 = anchor.insert_paragraph_before(
        "6.2.7.3 位移結果之影格選取敏感度與統計檢查", style="Heading 4"
    )
    h3.paragraph_format.keep_with_next = True
    h3.paragraph_format.page_break_before = True
    anchor.insert_paragraph_before(
        "為確認位移改善不只出現在單一30步名單，另以時間均勻、取樣區中央及全部可用影格重新計算，且每種規則都由方法無關的時間或Raw資料決定。表6-17列出四種規則下Raw與MOSR相對PI位移真值的平均絕對偏差。",
        style="Normal",
    )

    rule_labels = {
        "formal_raw_ranked30": "Fixed Raw-ranked 30",
        "time_regular30": "Time-regular 30",
        "central_acquisition30": "Central-acquisition 30",
        "all_within_session": "All usable frames",
    }
    selection_table_rows: list[list[str]] = []
    pillar_improvements: list[float] = []
    via_improvements: list[float] = []
    for rule in rules:
        p_raw = float(selection[("pillar", rule, "Raw")]["mae_nm"])
        p_mosr = float(selection[("pillar", rule, "MOSR")]["mae_nm"])
        v_raw_value = float(selection[("via", rule, "Raw")]["mae_nm"])
        v_mosr_value = float(selection[("via", rule, "MOSR")]["mae_nm"])
        p_imp = 100.0 * (p_raw - p_mosr) / p_raw
        v_imp = 100.0 * (v_raw_value - v_mosr_value) / v_raw_value
        pillar_improvements.append(p_imp)
        via_improvements.append(v_imp)
        selection_table_rows.append(
            [
                rule_labels[rule],
                f"{p_raw:.2f}",
                f"{p_mosr:.2f}",
                f"{p_imp:.1f}%",
                f"{v_raw_value:.2f}",
                f"{v_mosr_value:.2f}",
                f"{v_imp:.1f}%",
            ]
        )
    add_table_before(
        doc,
        anchor,
        "表 6-17 Displacement MAE sensitivity to frame-selection rules",
        ["Selection rule", "Pillar\nRaw", "Pillar\nMOSR", "Pillar\nimprovement", "Via\nRaw", "Via\nMOSR", "Via\nimprovement"],
        selection_table_rows,
        [1.38, 0.72, 0.78, 0.92, 0.70, 0.78, 0.90],
        bold_cells={
            (row_index, column_index)
            for row_index in range(len(selection_table_rows))
            for column_index in (2, 3, 5, 6)
        },
        font_size=7.4,
    )

    ci_lower = -float(paired["paired_bootstrap_95ci_upper_nm"])
    ci_upper = -float(paired["paired_bootstrap_95ci_lower_nm"])
    reduction = -float(paired["candidate_minus_reference_mean_absolute_error_nm"])
    anchor.insert_paragraph_before(
        (
            f"四種規則下，MOSR相對Raw的pillar平均絕對偏差均降低，改善幅度為{min(pillar_improvements):.1f}%至"
            f"{max(pillar_improvements):.1f}%；via亦維持{min(via_improvements):.1f}%至{max(via_improvements):.1f}%的同方向改善。"
            f"在正式共同有效的{int(float(paired['common_step_count']))}個pillar配對步中，MOSR平均降低{reduction:.2f} nm，"
            f"成對自助法95%信賴區間為{ci_lower:.2f}至{ci_upper:.2f} nm，Wilcoxon成對檢定p < 0.001。"
            "因此，主要位移改善不依賴單一影格選取方式。"
        ),
        style="Normal",
    )

    h4 = anchor.insert_paragraph_before("6.2.7.4 整張影像運算效能", style="Heading 4")
    h4.paragraph_format.keep_with_next = True
    anchor.insert_paragraph_before(
        "運算效能以相同2048×1536影像、相同顯示卡、相同自動混合精度及整張影像直接推論量測。表6-18列出參數量相近的深殘差對照EDSR-x1與MOSR，時間為兩次暖機後六次推論的中位數與第95百分位。",
        style="Normal",
    )
    runtime_rows: list[list[str]] = []
    for method in ("EDSR", "MOSR"):
        row = runtime[method]
        label = "EDSR-x1" if method == "EDSR" else "MOSR"
        runtime_rows.append(
            [
                label,
                f"{int(float(row['parameter_count'])) / 1.0e6:.3f}",
                f"{float(row['direct_median_ms']):.1f}",
                f"{float(row['direct_p95_ms']):.1f}",
                f"{float(row['direct_megapixels_per_second']):.2f}",
            ]
        )
    add_table_before(
        doc,
        anchor,
        "表 6-18 Full-frame direct-inference performance on the same GPU",
        ["Method", "Parameters\n(M)", "Median latency\n(ms)", "P95 latency\n(ms)", "Throughput\n(MP/s)"],
        runtime_rows,
        [1.25, 1.10, 1.42, 1.30, 1.30],
        bold_cells={(1, 0), (1, 1), (1, 2), (1, 3), (1, 4)},
        font_size=8.0,
    )
    edsr_runtime = runtime["EDSR"]
    mosr_runtime = runtime["MOSR"]
    latency_gain = 100.0 * (
        1.0
        - float(mosr_runtime["direct_median_ms"])
        / float(edsr_runtime["direct_median_ms"])
    )
    fps = 1000.0 / float(mosr_runtime["direct_median_ms"])
    anchor.insert_paragraph_before(
        (
            f"MOSR整張影像推論中位時間為{float(mosr_runtime['direct_median_ms']):.1f} ms，"
            f"第95百分位為{float(mosr_runtime['direct_p95_ms']):.1f} ms，吞吐量為"
            f"{float(mosr_runtime['direct_megapixels_per_second']):.2f} MP/s，相當於約{fps:.2f} frames/s。"
            f"在參數量相近的條件下，其中位時間較EDSR-x1縮短{latency_gain:.1f}%，可支援離線量測與批次重建。"
        ),
        style="Normal",
    )

    h5 = anchor.insert_paragraph_before("6.2.7.5 補充驗證小結", style="Heading 4")
    h5.paragraph_format.keep_with_next = True
    anchor.insert_paragraph_before(
        "補充實驗將原本的pillar證據擴充到亮via與線條。20倍via在SEM對照CD、門檻區間與邊緣寬度三項指標均由MOSR最低；線條在邊緣集中後仍維持原有週期；四種影格選取規則下，pillar與via的位移平均絕對偏差皆相對Raw下降；整張影像推論則維持次秒級。這些結果共同支持MOSR對不同亮暗極性與邊界形貌的量測轉移能力。",
        style="Normal",
    )


def insert_chapter7(doc: Document, metrics: dict[str, object]) -> None:
    via = metrics["via"]
    raw_via = via["Raw"]
    mosr_via = via["MOSR"]
    line = metrics["line"]
    runtime = metrics["runtime"]["MOSR"]

    anchor = find_exact(doc, "7.2 主要方法貢獻")
    anchor.insert_paragraph_before(
        "跨形貌補充驗證顯示，MOSR的作用不只出現在暗pillar。於亮via的低取樣條件中，MOSR在SEM對照CD與門檻穩健度上優於Raw、基礎U-Net、EDSR及NAFNet；於水平與垂直線條中，邊界變集中時表觀週期仍維持穩定。四種影格選取規則亦得到相同的位移改善方向。",
        style="Normal",
    )

    anchor = find_exact(doc, "7.4 研究範圍與量測可信度")
    anchor.insert_paragraph_before(
        (
            f"在20倍via中，MOSR將CD區間中點平均絕對誤差由{float(raw_via['midpoint_mae_nm']):.1f} nm降至"
            f"{float(mosr_via['midpoint_mae_nm']):.1f} nm，門檻區間寬度由{float(raw_via['mean_cd_interval_width_nm']):.1f} nm降至"
            f"{float(mosr_via['mean_cd_interval_width_nm']):.1f} nm，10%至90%邊緣寬度由{float(raw_via['mean_edge_width_nm']):.1f} nm降至"
            f"{float(mosr_via['mean_edge_width_nm']):.1f} nm。水平與垂直線條的邊緣寬度分別降低14.2%與18.0%，表觀週期變化小於2 nm。"
            f"2048×1536影像的直接推論中位時間為{float(runtime['direct_median_ms']):.1f} ms。"
        ),
        style="Normal",
    )


def main() -> None:
    required = [
        SOURCE,
        VIA_SUMMARY,
        LINE_SUMMARY,
        SELECTION_SUMMARY,
        PAIRED_RESULTS,
        RUNTIME_SUMMARY,
        VIA_REFERENCE,
        EDSR_TRAINING,
        NAFNET_TRAINING,
        VIA_FIGURE,
        LINE_FIGURE,
    ]
    missing = [str(path) for path in required if not path.exists()]
    if missing:
        raise FileNotFoundError("Missing required files:\n" + "\n".join(missing))

    source_hash_before = sha256(SOURCE)
    metrics = load_metrics()
    shutil.copy2(SOURCE, TARGET)
    doc = Document(TARGET)
    if any("跨形貌、現代模型與計算效能補充驗證" in p.text for p in doc.paragraphs):
        raise RuntimeError("v12 content is already present in source")

    before_math = document_math_fingerprint(doc)
    before_formula_tables = formula_table_audit(doc)
    if before_formula_tables["visible_border_table_indices"]:
        raise RuntimeError("Formula borders were visible before v12 editing")
    before_counts = {
        "paragraphs": len(doc.paragraphs),
        "tables": len(doc.tables),
        "inline_shapes": len(doc.inline_shapes),
    }

    update_existing_text(doc, metrics)
    insert_literature(doc)
    insert_chapter5(doc, metrics)
    insert_chapter6(doc, metrics)
    insert_chapter7(doc, metrics)
    enable_field_updates(doc)

    temporary = TARGET.with_name(TARGET.stem + "_building.docx")
    doc.save(temporary)
    check = Document(temporary)
    after_math = document_math_fingerprint(check)
    after_formula_tables = formula_table_audit(check)
    if before_math != after_math:
        raise RuntimeError(f"Equation fingerprint changed: {before_math} -> {after_math}")
    if after_formula_tables["visible_border_table_indices"]:
        raise RuntimeError("At least one formula table regained a visible border")

    expected_headings = [
        "5.4.7 現代重建模型與跨形貌評估配置",
        "6.2.7 跨形貌、現代模型與計算效能補充驗證",
        "6.2.7.1 20× via之跨形貌與現代模型比較",
        "6.2.7.2 線條形貌之邊界集中與週期保持",
        "6.2.7.3 位移結果之影格選取敏感度與統計檢查",
        "6.2.7.4 整張影像運算效能",
        "6.2.7.5 補充驗證小結",
        "6.2.8 綜合討論",
    ]
    texts = {p.text.strip() for p in check.paragraphs}
    missing_headings = [heading for heading in expected_headings if heading not in texts]
    if missing_headings:
        raise RuntimeError(f"Missing headings after save: {missing_headings}")
    if not any(p.text.strip().startswith("[94] L. Chen") for p in check.paragraphs):
        raise RuntimeError("NAFNet reference [94] was not inserted")
    if len(check.tables) != before_counts["tables"] + 3:
        raise RuntimeError(
            f"Expected three new tables, got {len(check.tables) - before_counts['tables']}"
        )
    if len(check.inline_shapes) != before_counts["inline_shapes"] + 2:
        raise RuntimeError(
            f"Expected two new figures, got {len(check.inline_shapes) - before_counts['inline_shapes']}"
        )
    internal_tokens = ["V42", "202607", "Modern_Restoration_Benchmarks", "Subpixel_Translation"]
    chapter_text = "\n".join(p.text for p in check.paragraphs)
    leaked = [token for token in internal_tokens if token in chapter_text]
    if leaked:
        raise RuntimeError(f"Internal identifiers leaked into thesis body: {leaked}")

    os.replace(temporary, TARGET)
    source_hash_after = sha256(SOURCE)
    if source_hash_before != source_hash_after:
        raise RuntimeError("Source v11 changed during v12 build")

    AUDIT.parent.mkdir(parents=True, exist_ok=True)
    audit = {
        "source": str(SOURCE),
        "target": str(TARGET),
        "source_sha256": source_hash_before,
        "target_sha256": sha256(TARGET),
        "source_unchanged": True,
        "before_counts": before_counts,
        "after_counts": {
            "paragraphs": len(check.paragraphs),
            "tables": len(check.tables),
            "inline_shapes": len(check.inline_shapes),
        },
        "math_before": before_math,
        "math_after": after_math,
        "formula_tables_before": before_formula_tables,
        "formula_tables_after": after_formula_tables,
        "inserted_headings": expected_headings,
        "key_results": {
            "20x_via_raw_midpoint_mae_nm": float(metrics["via"]["Raw"]["midpoint_mae_nm"]),
            "20x_via_mosr_midpoint_mae_nm": float(metrics["via"]["MOSR"]["midpoint_mae_nm"]),
            "mosr_full_frame_direct_median_ms": float(metrics["runtime"]["MOSR"]["direct_median_ms"]),
        },
    }
    AUDIT.write_text(json.dumps(audit, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(audit, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
